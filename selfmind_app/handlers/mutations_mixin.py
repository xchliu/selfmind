"""Mutation handler methods: documents, memories, meta, agents, import."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config, get_enabled_profiles

logger = logging.getLogger(__name__)


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
        from selfmind_app.http_handler import _importer
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
        from selfmind_app.http_handler import _importer, _store
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
        from selfmind_app.http_handler import _importer, _store
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
        from selfmind_app.http_handler import _store
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
        from selfmind_app.http_handler import _store
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
        from selfmind_app.http_handler import _store
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
        from selfmind_app.http_handler import _store
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
        from selfmind_app.http_handler import _store
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
        from selfmind_app.http_handler import _meta_db
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        status = params.get("status", [None])[0]
        self._json_response(_meta_db.get_all_entries(status=status))

    def _handle_meta_sync(self):
        from selfmind_app.http_handler import _meta_db
        config = load_config()
        source_cfg = config.get("source", {})
        active = source_cfg.get("active_profile", "hermes")
        profile = source_cfg.get("profiles", {}).get(active, {})
        home = profile.get("home", "")
        files = profile.get("memory_files", [])
        memory_path = user_path = None
        for f in files:
            full = os.path.join(home, f)
            if os.path.exists(full):
                if "MEMORY" in f.upper() or "memory" in f:
                    memory_path = full
                elif "USER" in f.upper() or "user" in f:
                    user_path = full
        if not memory_path:
            # Try fallback
            for f in profile.get("memory_files_fallback", []):
                full = os.path.join(home, f)
                if os.path.exists(full):
                    if "memory" in f.lower():
                        memory_path = full
                    elif "user" in f.lower():
                        user_path = full
        if not memory_path:
            self._json_response({"error": "No memory file found"}, code=404)
            return
        result = _meta_db.sync_from_memory_files(memory_path, user_path)
        self._json_response({"status": "ok", **result})

    def _handle_meta_create_snapshot(self):
        from selfmind_app.http_handler import _meta_db
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
        sid = _meta_db.create_snapshot(memory_content, user_content, "manual")
        self._json_response({"status": "ok", "snapshot_id": sid})

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

    def _add_agent(self):
        """添加新Agent"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except:
            self._json_response({"error": "Invalid JSON"}, code=400)
            return

        name = data.get("name", "").strip()
        path = data.get("path", "").strip()

        if not name or not path:
            self._json_response({"error": "Name and path required"}, code=400)
            return

        # 展开路径
        path = str(Path(path).expanduser())

        config = load_config()
        profiles = config.setdefault("source", {}).setdefault("profiles", {})
        agent_id = name.lower().replace(" ", "-")

        # 检查是否已存在
        if agent_id in profiles:
            self._json_response({"error": "Agent already exists"}, code=400)
            return

        # 添加到profiles
        profiles[agent_id] = {
            "name": name,
            "home": path,
            "memory_files": ["memories/MEMORY.md", "memories/USER.md"],
            "memory_files_fallback": ["memory.md", "user.md"]
        }

        # 保存配置
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "agent": {"id": agent_id, "name": name, "path": path}})

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
        """切换当前Agent"""
        config = load_config()
        profiles = config.get("source", {}).get("profiles", {})

        # 验证agent存在
        if agent_id not in profiles:
            self._json_response({"error": "Agent not found"}, code=404)
            return

        config.setdefault("source", {})["active_profile"] = agent_id

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "message": "Switched to " + agent_id})

    def _import_memory(self):
        """导入记忆文件"""
        from selfmind_app.http_handler import _safe_read_existing_data
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except:
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
        existing = _safe_read_existing_data() or {"nodes": [], "links": []}
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