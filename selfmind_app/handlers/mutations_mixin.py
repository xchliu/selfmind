"""Mutation handler methods: documents, memories, meta, agents, import."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config, get_enabled_profiles

logger = logging.getLogger(__name__)


def _get_store():
    """Get UnifiedStore from handler class attribute (set by server.py)."""
    from selfmind_app.http_handler import SelfMindHandler
    return getattr(SelfMindHandler, '_store', None)


class MutationsMixin:
    """Handler methods for write/mutation operations: documents, memories, meta, agents, import."""

    def _read_body(self) -> dict:
        """Read and parse JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        return json.loads(body) if body else {}

    def _handle_documents_scan(self):
        """GET /api/documents/scan?dir=... — Scan directory for documents."""
        from urllib.parse import parse_qs, urlparse
        from selfmind_app.document_importer import DocumentImporter
        _importer = DocumentImporter()
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        dir_path = params.get("dir", [""])[0]

        if not dir_path:
            config = load_config()
            dir_path = config.get("documents", {}).get("watch_dir", "")

        if not dir_path:
            self._json_response(
                {"error": "No directory specified. Use ?dir=/path or set documents.watch_dir in config."},
                code=400,
            )
            return

        files = _importer.scan_directory(dir_path)
        self._json_response({"dir": dir_path, "files": files, "count": len(files)})

    def _handle_extract_stream(self):
        """GET /api/documents/extract-stream?dir=... — SSE stream: scan + extract with progress."""
        from urllib.parse import parse_qs, urlparse
        from selfmind_app.document_importer import DocumentImporter
        _importer = DocumentImporter()
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        dir_path = params.get("dir", [""])[0]

        if not dir_path:
            config = load_config()
            dir_path = config.get("documents", {}).get("watch_dir", "")

        # Set up SSE response headers
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(data: dict):
            try:
                payload = json.dumps(data, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        if not dir_path:
            send_event({"type": "error", "message": "未指定目录路径"})
            return

        # Phase 1: Scan
        send_event({"type": "scanning", "dir": dir_path})
        files = _importer.scan_directory(dir_path)

        if not files:
            send_event({"type": "done", "total_files": 0, "total_extracted": 0,
                        "message": "未找到可导入的文档"})
            return

        send_event({"type": "scan_done", "total_files": len(files),
                    "files": [f["name"] for f in files]})

        # Phase 2: Extract file by file
        config = load_config()
        llm_config = config.get("llm", {})

        if not llm_config.get("api_key"):
            send_event({"type": "error", "message": "LLM API Key 未配置"})
            return

        total_extracted = 0
        processed = 0
        skipped = 0

        for i, file_info in enumerate(files):
            file_path = file_info["path"]
            file_name = file_info["name"]

            send_event({
                "type": "extracting",
                "file": file_name,
                "current": i + 1,
                "total": len(files),
            })

            content = _importer.read_document(file_path)
            if not content.strip():
                skipped += 1
                send_event({
                    "type": "file_skipped",
                    "file": file_name,
                    "reason": "文件内容为空",
                    "current": i + 1,
                    "total": len(files),
                })
                continue

            try:
                memories = _importer.extract_memories(content, file_name, config)
                if memories:
                    ids = _store.add_entries(memories)
                    total_extracted += len(memories)
                processed += 1

                send_event({
                    "type": "file_done",
                    "file": file_name,
                    "extracted": len(memories) if memories else 0,
                    "total_extracted": total_extracted,
                    "current": i + 1,
                    "total": len(files),
                })
            except Exception as exc:
                logger.error("Error extracting %s: %s", file_name, exc)
                send_event({
                    "type": "file_error",
                    "file": file_name,
                    "error": str(exc),
                    "current": i + 1,
                    "total": len(files),
                })

        send_event({
            "type": "done",
            "total_files": len(files),
            "processed": processed,
            "skipped": skipped,
            "total_extracted": total_extracted,
        })

    def _handle_documents_extract(self):
        """POST /api/documents/extract — Extract memories from documents.

        Body: {"dir": "/path/to/docs"} or {"file": "/path/to/file.md"}
        """
        from selfmind_app.document_importer import DocumentImporter
        _importer = DocumentImporter()
        _store = _get_store()
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        config = load_config()
        llm_config = config.get("llm", {})

        if not llm_config.get("api_key"):
            self._json_response(
                {"error": "LLM API key not configured. Set llm.api_key in config or LLM_API_KEY env var."},
                code=400,
            )
            return

        file_path = body.get("file")
        dir_path = body.get("dir")

        if file_path:
            # Single file extraction
            content = _importer.read_document(file_path)
            if not content.strip():
                self._json_response({"error": f"Could not read file: {file_path}"}, code=400)
                return
            source_name = file_path.split("/")[-1] if "/" in file_path else file_path
            memories = _importer.extract_memories(content, source_name, config)
            # Store extracted memories
            if memories:
                ids = _store.add_entries(memories)
                self._json_response({
                    "status": "ok",
                    "extracted": len(memories),
                    "ids": ids,
                    "memories": _store.get_entries({"status": "pending"}),
                })
            else:
                self._json_response({"status": "ok", "extracted": 0, "ids": [], "memories": []})

        elif dir_path:
            # Batch extraction from directory
            memories = _importer.batch_extract(dir_path, config)
            if memories:
                ids = _store.add_entries(memories)
                self._json_response({
                    "status": "ok",
                    "extracted": len(memories),
                    "ids": ids,
                    "memories": _store.get_entries({"status": "pending"}),
                })
            else:
                self._json_response({"status": "ok", "extracted": 0, "ids": [], "memories": []})
        else:
            self._json_response({"error": "Provide 'dir' or 'file' in request body"}, code=400)

    def _handle_memories_list(self):
        """GET /api/memories?status=...&primary=... — List memories with filters."""
        from urllib.parse import parse_qs, urlparse
        _store = _get_store()
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        filters = {}
        for key in ("status", "primary", "secondary", "source_file"):
            if key in params:
                val = params[key]
                filters[key] = val[0] if len(val) == 1 else val

        entries = _store.get_entries(filters if filters else None)
        self._json_response({"entries": entries, "total": len(entries)})

    def _handle_memories_add(self):
        """POST /api/memories — Add memory entries manually."""
        _store = _get_store()
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        entries = body.get("entries", [])
        if not entries:
            # Single entry
            if body.get("text"):
                entries = [body]
            else:
                self._json_response({"error": "Provide 'entries' array or a single entry object"}, code=400)
                return

        ids = _store.add_entries(entries)
        self._json_response({"status": "ok", "ids": ids, "count": len(ids)})

    def _handle_memory_update(self, entry_id: str):
        """PUT /api/memories/:id — Update a memory entry."""
        _store = _get_store()
        try:
            updates = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        result = _store.update_entry(entry_id, updates)
        if result:
            self._json_response({"status": "ok", "entry": result})
        else:
            self._json_response({"error": "Not found"}, code=404)

    def _handle_memories_sync(self):
        """POST /api/memories/sync — Sync memories to an agent system.

        Body: {"ids": [...], "agent": "hermes"} or {"ids": [...], "agent": "openclaw"}
        """
        _store = _get_store()
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        entry_ids = body.get("ids", [])
        agent = body.get("agent", "hermes")
        config = load_config()

        if not entry_ids:
            self._json_response({"error": "Provide 'ids' array"}, code=400)
            return

        profiles = config.get("source", {}).get("profiles", {})
        if agent not in profiles:
            self._json_response({"error": f"Unknown agent: {agent}. Available: {list(profiles.keys())}"}, code=400)
            return

        agent_home = profiles[agent].get("home", "")

        if agent == "hermes":
            result = _store.sync_to_hermes(entry_ids, agent_home)
        elif agent == "openclaw":
            result = _store.sync_to_openclaw(entry_ids, agent_home)
        else:
            result = _store.sync_to_hermes(entry_ids, agent_home)

        self._json_response({"status": "ok", **result})

    def _handle_memories_bulk_status(self):
        """POST /api/memories/bulk-status — Bulk update memory entry status.

        Body: {"ids": [...], "status": "approved"}
        """
        _store = _get_store()
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        entry_ids = body.get("ids", [])
        status = body.get("status", "")

        if not entry_ids or not status:
            self._json_response({"error": "Provide 'ids' array and 'status'"}, code=400)
            return

        try:
            count = _store.bulk_update_status(entry_ids, status)
            self._json_response({"status": "ok", "updated": count})
        except ValueError as exc:
            self._json_response({"error": str(exc)}, code=400)

    # ── Meta API handler methods ─────────────────────────────────────

    def _handle_meta_entries(self):
        from urllib.parse import parse_qs, urlparse
        from selfmind_app.http_handler import SelfMindHandler
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        status = params.get("status", [None])[0]
        store = getattr(SelfMindHandler, '_store', None)
        if store:
            self._json_response(store.get_all_entries(status=status))
        else:
            self._json_response({"error": "Store not available"}, code=503)

    def _handle_meta_sync(self):
        """Sync all data sources into unified store."""
        from selfmind_app.unified_sync import unified_sync
        store = getattr(SelfMindHandler, '_store', None)
        if not store:
            self._json_response({"error": "Unified store not initialized"}, code=500)
            return
        config = load_config()
        result = unified_sync(store, config)
        # Invalidate cached graph data so next request rebuilds from fresh store
        SelfMindHandler._graph_data = None
        self._json_response({"status": "ok", **result})

    def _handle_meta_create_snapshot(self):
        from selfmind_app.http_handler import SelfMindHandler
        config = load_config()
        source_cfg = config.get("source", {})
        active = source_cfg.get("active_profile", "hermes")
        profile = source_cfg.get("profiles", {}).get(active, {})
        home = profile.get("home", "")
        memory_content = user_content = ""
        for f in profile.get("memory_files", []):
            full = os.path.join(home, f)
            if os.path.exists(full):
                with open(full, "r", encoding="utf-8") as fh:
                    content = fh.read()
                if "MEMORY" in f.upper() or "memory" in f:
                    memory_content = content
                elif "USER" in f.upper() or "user" in f:
                    user_content = content
        store = getattr(SelfMindHandler, '_store', None)
        if store:
            sid = store.create_snapshot(memory_content, user_content, "manual")
            self._json_response({"status": "ok", "snapshot_id": sid})
        else:
            self._json_response({"error": "Store not available"}, code=503)

    # ========== Agent管理API ==========

    def _get_agents(self):
        """获取所有Agent"""
        config = load_config()
        
        # 从source.profiles构建agents列表
        profiles = config.get("source", {}).get("profiles", {})
        agents = []
        for pid, pdata in profiles.items():
            agents.append({
                "id": pid,
                "name": pdata.get("name", pid.title()),
                "path": pdata.get("home", "")
            })
        
        # 添加自定义agents（如果有）
        custom_agents = config.get("agents", [])
        for ca in custom_agents:
            if not any(a["id"] == ca["id"] for a in agents):
                agents.append(ca)
        
        current = config.get("source", {}).get("active_profile", "hermes")
        
        return {
            "agents": agents,
            "currentAgent": current
        }

    def _handle_agents_config_get(self):
        """获取Agent配置详情 — 只返回真实运行中的agent（有gateway的）"""
        config = load_config()
        profiles = config.get("source", {}).get("profiles", {})
        custom_agents = config.get("agents", [])
        current_agent = config.get("current_agent", config.get("source", {}).get("active_profile", "hermes"))
        
        # 只返回 config.agents 中配置的agent（真实运行中的）
        agents = []
        for ca in custom_agents:
            agent = {
                "id": ca.get("id", "unknown"),
                "name": ca.get("name", ca.get("id", "unknown").title()),
                "type": ca.get("type", "other"),
                "gateway": ca.get("gateway", ""),
            }
            # 从profiles获取home路径
            pid = ca.get("id", "unknown")
            if pid in profiles:
                pdata = profiles[pid]
                agent["path"] = pdata.get("home", "")
            # 从extensions获取详细配置
            ext = ca.get("extensions", {})
            if ext:
                agent["memory_path"] = ext.get("memory_path", "")
                agent["skills_path"] = ext.get("skills_path", "")
                agent["honcho_url"] = ext.get("honcho_api", "")
                agent["wiki_path"] = ext.get("wiki_path", "")
                agent["sync_interval"] = ext.get("sync_interval", 5)
                agent["decay_threshold"] = ext.get("decay_threshold", 0.2)
            agents.append(agent)
        
        self._json_response({
            "agents": agents,
            "current_agent": current_agent,
            "sync_interval": config.get("sync_interval", 5),
            "decay_threshold": config.get("decay_threshold", 0.2)
        })

    def _discover_gateway(self):
        """探测Gateway地址，获取Agent信息
        
        GET /api/agents/discover?gateway=http://localhost:8642
        
        探测流程：
        1. GET /health — 检查gateway是否在线
        2. GET /health/detailed — 获取详细状态（平台类型、PID、配置路径等）
        3. 尝试推断hermes_home路径（从PID或默认路径）
        """
        import urllib.request
        import urllib.error
        
        import urllib.parse as _urlparse
        gateway_url = _urlparse.unquote(self.path.split("?gateway=")[-1]) if "?gateway=" in self.path else ""
        # 也支持POST body方式
        if not gateway_url:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body)
                    gateway_url = data.get("gateway", "").strip()
                except (json.JSONDecodeError, KeyError):
                    pass
        
        if not gateway_url:
            self._json_response({"error": "Gateway URL required. Use ?gateway=http://host:port"}, code=400)
            return
        
        # Normalize URL: remove trailing slash
        gateway_url = gateway_url.rstrip("/")
        
        # Ensure scheme
        if not gateway_url.startswith("http://") and not gateway_url.startswith("https://"):
            gateway_url = "http://" + gateway_url
        
        result = {"gateway": gateway_url, "reachable": False, "agent_info": {}}
        
        # Step 1: Basic health check
        try:
            req = urllib.request.Request(gateway_url + "/health", headers={"Accept": "application/json"})
            resp = urllib.request.urlopen(req, timeout=5)
            health_data = json.loads(resp.read())
            result["reachable"] = True
            result["agent_info"]["platform"] = health_data.get("platform", "unknown")
            result["agent_info"]["status"] = health_data.get("status", "unknown")
        except urllib.error.HTTPError as e:
            # Server responded but with error code — still reachable
            result["reachable"] = True
            result["agent_info"]["status"] = f"http_error_{e.code}"
        except Exception as e:
            result["reachable"] = False
            result["error"] = str(e)
            self._json_response(result, code=200)
            return
        
        # Step 2: Detailed health check
        try:
            req = urllib.request.Request(gateway_url + "/health/detailed", headers={"Accept": "application/json"})
            resp = urllib.request.urlopen(req, timeout=5)
            detailed = json.loads(resp.read())
            result["detailed"] = detailed
            
            # Extract agent info
            platform_type = detailed.get("platform", "")
            platforms_connected = detailed.get("platforms", {})
            pid = detailed.get("pid")
            
            # Determine agent name and type from platform info
            if "hermes-agent" in platform_type or "api_server" in platforms_connected:
                result["agent_info"]["type"] = "hermes"
                result["agent_info"]["name"] = "Hermes"
                
                # Try to infer hermes home path
                # Check if HERMES_HOME env is accessible (not directly, but guess common paths)
                home_dir = str(Path.home())
                hermes_home = os.environ.get("HERMES_HOME", os.path.join(home_dir, ".hermes"))
                
                result["agent_info"]["home_path"] = hermes_home
                result["agent_info"]["memory_path"] = os.path.join(hermes_home, "memories")
                result["agent_info"]["skills_path"] = os.path.join(hermes_home, "skills")
                result["agent_info"]["wiki_path"] = os.path.join(home_dir, "Documents", "aiworkspace", "wiki")
                
                # Check if these paths actually exist
                result["paths_valid"] = {
                    "memory": os.path.isdir(result["agent_info"]["memory_path"]),
                    "skills": os.path.isdir(result["agent_info"]["skills_path"]),
                    "wiki": os.path.isdir(result["agent_info"]["wiki_path"])
                }
                
                # Check if MEMORY.md exists
                mem_file = os.path.join(result["agent_info"]["memory_path"], "MEMORY.md")
                result["agent_info"]["memory_file_exists"] = os.path.isfile(mem_file)
                
            elif "openclaw" in platform_type.lower():
                result["agent_info"]["type"] = "openclaw"
                result["agent_info"]["name"] = "OpenClaw"
                home_dir = str(Path.home())
                openclaw_home = os.path.join(home_dir, ".openclaw")
                result["agent_info"]["home_path"] = openclaw_home
                result["agent_info"]["memory_path"] = os.path.join(openclaw_home, "memories")
                result["agent_info"]["skills_path"] = os.path.join(openclaw_home, "skills")
            else:
                # Unknown platform type — still return info, user fills in paths manually
                result["agent_info"]["type"] = "other"
                result["agent_info"]["name"] = platform_type or "Unknown"
            
            # Collect connected platform names for display
            connected_platforms = [name for name, info in platforms_connected.items() 
                                   if info.get("state") == "connected"]
            result["agent_info"]["connected_platforms"] = connected_platforms
            
        except Exception as e:
            result["detailed_error"] = str(e)
            # Still return basic info
        
        self._json_response(result)

    def _add_agent(self):
        """添加新Agent — 支持gateway地址自动发现
        
        Body格式：
        - 传统模式: {name, path} — 手动指定路径
        - Gateway模式: {gateway: "http://localhost:8642", type, name(可选)} — 自动发现路径
        
        gateway模式下会自动调用discover获取hermes_home等信息
        """
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, code=400)
            return
        
        gateway = data.get("gateway", "").strip()
        name = data.get("name", "").strip()
        type_ = data.get("type", "other")
        path = data.get("path", "").strip()
        
        # Gateway模式：自动发现agent信息
        if gateway:
            import urllib.request
            import urllib.error
            
            # Normalize URL
            gateway = gateway.rstrip("/")
            if not gateway.startswith("http://") and not gateway.startswith("https://"):
                gateway = "http://" + gateway
            
            # 先探测gateway
            try:
                req = urllib.request.Request(gateway + "/health/detailed", headers={"Accept": "application/json"})
                resp = urllib.request.urlopen(req, timeout=5)
                detailed = json.loads(resp.read())
                
                platform_type = detailed.get("platform", "")
                
                # 自动推断agent类型
                if "hermes-agent" in platform_type:
                    type_ = "hermes"
                    if not name:
                        name = "Hermes"
                elif "openclaw" in platform_type.lower():
                    type_ = "openclaw"
                    if not name:
                        name = "OpenClaw"
                else:
                    if not name:
                        name = platform_type.title() or "Agent"
                
                # 自动推断home路径
                home_dir = str(Path.home())
                if type_ == "hermes":
                    inferred_home = os.environ.get("HERMES_HOME", os.path.join(home_dir, ".hermes"))
                    path = inferred_home
                elif type_ == "openclaw":
                    path = os.path.join(home_dir, ".openclaw")
                else:
                    # 其他类型，尝试用gateway host推断
                    if not path:
                        path = os.path.join(home_dir, "." + name.lower().replace(" ", "-"))
                        
            except Exception as e:
                self._json_response({"error": f"Gateway discovery failed: {str(e)}", "gateway": gateway}, code=400)
                return
        
        if not name:
            self._json_response({"error": "Name required"}, code=400)
            return
        
        if not path:
            self._json_response({"error": "Path or Gateway required to determine agent home"}, code=400)
            return
        
        # 展开路径
        path = str(Path(path).expanduser())
        
        # 构建agent配置（新格式，带gateway和extensions）
        agent_id = name.lower().replace(" ", "-")
        
        # 构建extensions（根据type自动填充）
        extensions = data.get("extensions", {})
        if type_ == "hermes" and not extensions:
            hermes_home = path
            extensions = {
                "memory_path": os.path.join(hermes_home, "memories"),
                "skills_path": os.path.join(hermes_home, "skills"),
                "honcho_api": "http://localhost:8000",
                "wiki_path": os.path.join(str(Path.home()), "Documents", "aiworkspace", "wiki"),
                "sync_interval": 5,
                "decay_threshold": 0.2
            }
        
        # 保存到config.json的agents数组（新格式）
        config = load_config()
        agents = config.get("agents", [])
        
        # 检查是否已存在
        if any(a.get("id") == agent_id for a in agents):
            self._json_response({"error": f"Agent '{agent_id}' already exists"}, code=400)
            return
        
        new_agent = {
            "id": agent_id,
            "name": name,
            "type": type_,
            "gateway": gateway,
            "extensions": extensions
        }
        agents.append(new_agent)
        config["agents"] = agents
        
        # 也保存到source.profiles（兼容旧格式，用于unified_sync）
        profiles = config.setdefault("source", {}).setdefault("profiles", {})
        if agent_id not in profiles:
            profiles[agent_id] = {
                "name": name,
                "home": path,
                "memory_files": ["memories/MEMORY.md", "memories/USER.md"],
                "memory_files_fallback": ["memory.md", "user.md"]
            }
        
        # 保存配置
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        self._json_response({"status": "ok", "agent": new_agent})

    def _delete_agent(self, agent_id):
        """删除Agent"""
        config = load_config()
        
        # 不能删除内置的agent
        if agent_id in ["hermes", "openclaw", "honcho"]:
            self._json_response({"error": "Cannot delete built-in agent"}, code=400)
            return

        profiles = config.get("source", {}).get("profiles", {})
        
        if agent_id not in profiles:
            self._json_response({"error": "Agent not found"}, code=404)
            return

        del profiles[agent_id]

        # 如果删除的是当前agent，切换到hermes
        current = config.get("source", {}).get("active_profile", "hermes")
        if current == agent_id:
            config.setdefault("source", {})["active_profile"] = "hermes"

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "message": "Agent deleted"})

    def _set_default_agent(self, agent_id):
        """设置默认Agent"""
        config = load_config()
        profiles = config.get("source", {}).get("profiles", {})

        # 验证agent存在
        if agent_id not in profiles:
            self._json_response({"error": "Agent not found"}, code=404)
            return

        config.setdefault("source", {})["active_profile"] = agent_id

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "message": "Default agent set to " + agent_id})

    def _switch_agent(self, agent_id):
        """切换当前Agent — 更新配置 + re-sync + re-build graph"""
        config = load_config()
        profiles = config.get("source", {}).get("profiles", {})

        # 验证agent存在（在profiles或custom_agents中）
        custom_agents = config.get("agents", [])
        custom_ids = [a.get("id") for a in custom_agents]
        if agent_id not in profiles and agent_id not in custom_ids:
            self._json_response({"error": "Agent not found"}, code=404)
            return

        # 更新 source.active_profile 和 current_agent
        config.setdefault("source", {})["active_profile"] = agent_id
        config["current_agent"] = agent_id

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Re-sync 数据
        store = _get_store()
        new_data = None
        agent_name = agent_id
        try:
            from selfmind_app.unified_sync import unified_sync
            from selfmind_app.parser import build_graph_from_store
            sync_stats = unified_sync(store, config)
            new_data = build_graph_from_store(store, config)
            # 从 agents 列表找名字
            for a in custom_agents:
                if a.get("id") == agent_id:
                    agent_name = a.get("name", agent_id)
            # 也可能名字在 profiles 中
            if agent_id in profiles:
                pdata = profiles[agent_id]
                # 名字优先从 custom_agents 取
                for a in custom_agents:
                    if a.get("id") == agent_id:
                        agent_name = a.get("name", agent_id)
                        break
                if agent_name == agent_id:
                    agent_name = pdata.get("name", agent_id.title())
        except Exception as e:
            logging.warning(f"Re-sync after switch failed: {e}")

        # 清除graph缓存，确保后续/api/data请求返回新agent的数据
        from selfmind_app.http_handler import SelfMindHandler
        SelfMindHandler._graph_data = None

        # 更新 state_hash 触发前端自动刷新
        if store and hasattr(store, 'state_hash'):
            store.state_hash = str(__import__('uuid').uuid4())

        self._json_response({
            "status": "ok",
            "message": "Switched to " + agent_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "graph_data": new_data or {"nodes": [], "links": []},
            "sync_stats": sync_stats if 'sync_stats' in dir() else None
        })

    def _import_memory(self):
        """导入记忆文件"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, code=400)
            return

        import_path = data.get("path", "").strip()
        if not import_path:
            self._json_response({"error": "Path required"}, code=400)
            return

        import_path = str(Path(import_path).expanduser())

        if not os.path.exists(import_path):
            self._json_response({"error": "File not found"}, code=404)
            return

        # 读取文件内容
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self._json_response({"error": str(e)}, code=500)
            return

        # 简单处理：解析为节点
        from selfmind_app.parser import parse_memory_file
        nodes, links = parse_memory_file(import_path, content)

        # 保存到当前agent的memory目录
        config = load_config()
        memory_path = config.get("memory_path", str(Path.home() / ".hermes" / "memories"))

        # 追加到现有数据
        existing = None
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        existing = existing or {"nodes": [], "links": []}
        existing["nodes"].extend(nodes)
        existing["links"].extend(links)

        # 去重
        node_ids = set()
        unique_nodes = []
        for n in existing["nodes"]:
            if n.get("id") not in node_ids:
                node_ids.add(n.get("id"))
                unique_nodes.append(n)

        existing["nodes"] = unique_nodes

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "imported": len(nodes), "message": f"Imported {len(nodes)} nodes"})