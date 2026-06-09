"""SelfMind HTTP handler — core routing + shared module-level instances.

Handler methods are split into 4 mixins imported from selfmind_app/handlers/:
  - StatsMixin   → stats, poll, IQ, skills, data loading
  - MutationsMixin → documents, memories, meta, agents, import
  - EnginesMixin → consolidator, forgetter, analyzer
  - V1Mixin      → wiki data, v1 API (changes, status, memories, sync)

Evolution-aware: all metadata operations use UnifiedStore (no legacy meta_db).
Entries use status 'inactive' (not 'deleted') to preserve history.
"""

import json
import logging
import os
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config, get_enabled_profiles
from selfmind_app.consolidator import Consolidator
from selfmind_app.forgetter import ForgetterEngine
from selfmind_app.analyzer import AnalyzerEngine

from selfmind_app.handlers.stats_mixin import StatsMixin
from selfmind_app.handlers.mutations_mixin import MutationsMixin
from selfmind_app.handlers.engines_mixin import EnginesMixin
from selfmind_app.handlers.v1_mixin import V1Mixin

logger = logging.getLogger(__name__)


# Shared instances (created lazily)
_consolidator = None
_forgetter = None
_analyzer = None


def _get_store():
    """Get UnifiedStore from handler class attribute (set by server.py)."""
    return getattr(SelfMindHandler, '_store', None)


def _get_recall_scanner():
    """Get RecallScanner from handler class attribute (set by server.py)."""
    return getattr(SelfMindHandler, '_recall_scanner', None)


def _node_signature(node: dict) -> str:
    return "|".join(
        [
            node.get("label", ""),
            node.get("category", ""),
            node.get("description", ""),
        ]
    )


def _merge_metadata(data: dict) -> dict:
    """Merge metadata from UnifiedStore (decay_score, status, pinned) into graph nodes."""
    store = _get_store()
    if not store:
        return data

    # Get active memory entries from unified store
    store_entries = store.get_entries_by_type("memory", status="active")
    
    # Build lookup by content preview (first 80 chars, normalize ** markers)
    meta_lookup = {}
    for entry in store_entries:
        preview = entry.get('content_preview', '')[:80]
        if preview:
            normalized = preview.replace('**', '')
            meta_lookup[normalized] = entry
    
    # Merge into nodes
    merged_count = 0
    for node in data.get('nodes', []):
        if node.get('category') == 'memory':
            desc = node.get('description', '')[:80].replace('**', '')
            if desc in meta_lookup:
                meta = meta_lookup[desc]
                node['decay_score'] = meta.get('decay_score', 0.25)
                node['status'] = meta.get('status', 'active')
                node['pinned'] = bool(meta.get('pinned', 0))
                node['version'] = meta.get('version', 1)
                merged_count += 1
    
    if merged_count > 0:
        logger.info(f"✅ Merged store metadata for {merged_count} nodes")
    return data


def refresh_data() -> dict:
    """Rebuild graph from memory files and write to data.json."""
    from selfmind_app.parser import build_graph_from_store
    config = load_config()
    store = _get_store()
    if store:
        data = build_graph_from_store(store, config)
    else:
        from selfmind_app.parser import build_graph
        data = build_graph(config)
    # Merge metadata into nodes
    data = _merge_metadata(data)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


class SelfMindHandler(StatsMixin, MutationsMixin, EnginesMixin, V1Mixin, SimpleHTTPRequestHandler):
    """HTTP handler for SelfMind API + static files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SELFMIND_DIR), **kwargs)

    def _build_social_graph(self):
        """Build social graph from wiki entity files."""
        import yaml
        entities_dir = Path.home() / "aiworkspace" / "aiknowledge" / "entities"
        nodes = []
        edges = []
        node_map = {}

        # 核心节点：坦哥
        core = {
            "id": "tange",
            "name": "刘小成",
            "type": "person",
            "role": "core",
            "team": "core",
            "department": "AI部 - 负责人",
            "social_rank": "core",
            "interaction_count": 999,
            "title": "AI部门负责人"
        }
        nodes.append(core)
        node_map["tange"] = core

        # AI Agent 节点
        agents = [
            {"id": "socrates", "name": "苏格拉底", "type": "agent", "role": "ai_assistant", "team": "ai", "department": "AI助手", "social_rank": "self"},
            {"id": "aris", "name": "小亚", "type": "agent", "role": "ai_assistant", "team": "ai", "department": "AI助手", "social_rank": "peer"},
            {"id": "plato", "name": "柏拉图", "type": "agent", "role": "ai_assistant", "team": "ai", "department": "AI助手", "social_rank": "peer"},
        ]
        for a in agents:
            a["interaction_count"] = 999 if a["id"] == "socrates" else 50
            nodes.append(a)
            node_map[a["id"]] = a

        # AI→坦哥边
        for a in agents:
            edges.append({"source": a["id"], "target": "tange", "type": "ai_assistant", "weight": 5})

        # AI→AI边
        edges.append({"source": "socrates", "target": "aris", "type": "collaboration", "weight": 3})
        edges.append({"source": "socrates", "target": "plato", "type": "collaboration", "weight": 2})

        # 团队分组映射
        team_map = {
            "core": { "name": "核心", "color": "#e74c3c" },
            "ai":   { "name": "AI部门", "color": "#3498db" },
            "lab":  { "name": "实验室", "color": "#2ecc71" },
            "platform": { "name": "平台", "color": "#f39c12" },
            "product":  { "name": "产品", "color": "#9b59b6" },
            "project":  { "name": "项目", "color": "#1abc9c" },
            "external": { "name": "外部", "color": "#95a5a6" },
        }

        # 读取 entity 文件
        if entities_dir.exists():
            for fpath in sorted(entities_dir.glob("*.md")):
                fname = fpath.stem
                if fname in ("social-mechanism", "social-circle", "_template", "xiaoya", "tange"):
                    continue
                try:
                    raw_content = fpath.read_text(encoding="utf-8")
                    # 清理前端：去掉可能的编辑器污染（如首行有|遗漏）
                    content = raw_content.lstrip("|\n\t ")
                    # 提取 YAML frontmatter
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            meta = yaml.safe_load(parts[1]) or {}
                    else:
                        meta = {}
                    if not isinstance(meta, dict):
                        meta = {}
                except Exception:
                    meta = {}

                name = meta.get("title", fname).split("(")[0].strip()
                # 如果名字还是文件ID，尝试从基本信息提取
                if name == fname or not name:
                    import re as _re
                    name_match = _re.search(r'\*\*姓名\*\*[：:]\s*(.+?)(?:\n|$)', content)
                    if name_match:
                        name = name_match.group(1).strip()
                    else:
                        name = fname
                social_rank = meta.get("social_rank", "B")
                wecom_id = meta.get("wecom_id", "")
                last_interaction = meta.get("last_interaction", "")
                next_action = meta.get("next_action", "")
                interaction_count = meta.get("interaction_count", 0) or 0

                # 处理 YAML 类型转换：date → str
                if isinstance(last_interaction, datetime):
                    last_interaction = last_interaction.strftime("%Y-%m-%d")
                elif not isinstance(last_interaction, str):
                    last_interaction = str(last_interaction) if last_interaction else ""
                tags = meta.get("tags", [])

                # 推断团队
                dept_info = ""
                if "实验室" in content or fname in ("wangyue", "bi-jiankun", "qi-qiang", "wang-xiaochang"):
                    team = "lab"
                    dept_info = "实验室"
                elif "平台" in content or fname in ("zhoujinhui",):
                    team = "platform"
                    dept_info = "平台"
                elif "产品" in content or fname in ("chenxinglong",):
                    team = "product"
                    dept_info = "产品"
                elif "项目" in content or fname in ("wang-gengwu",):
                    team = "project"
                    dept_info = "项目"
                elif "外部" in content or fname in ("ning-yizhao", "wangrui", "xie-yanfei", "xu-zhuanli", "hedong", "wang-xun", "tan-jie"):
                    team = "external"
                    dept_info = "外部"
                else:
                    team = "ai"
                    dept_info = "AI部门"

                node = {
                    "id": fname,
                    "name": name,
                    "type": "person",
                    "role": "colleague",
                    "team": team,
                    "department": dept_info,
                    "social_rank": social_rank,
                    "wecom_id": wecom_id,
                    "last_interaction": last_interaction,
                    "next_action": next_action,
                    "interaction_count": interaction_count,
                    "has_interacted": bool(last_interaction),
                }
                nodes.append(node)
                node_map[fname] = node

                # 坦哥→此人边（管理/同事关系）
                edge_weight = 2 if social_rank == "A" else (1 if social_rank == "B" else 0.5)
                edges.append({"source": "tange", "target": fname, "type": "management", "weight": edge_weight})

                # 苏格拉底→此人边（社交关系）
                social_weight = interaction_count if interaction_count > 0 else (0.3 if social_rank != "C" else 0.1)
                edges.append({"source": "socrates", "target": fname, "type": "social", "weight": social_weight})

        # 团队信息附加
        result = {
            "nodes": nodes,
            "edges": edges,
            "teams": {k: v for k, v in team_map.items()},
            "total_people": len([n for n in nodes if n["type"] == "person"]),
            "total_agents": len([n for n in nodes if n["type"] == "agent"]),
            "total_interacted": len([n for n in nodes if n.get("has_interacted")]),
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        return result

    def _handle_social_entity(self, entity_name):
        """Serve parsed entity wiki file for social detail panel."""
        import yaml
        import re as _re
        entities_dir = Path.home() / "aiworkspace" / "aiknowledge" / "entities"
        fpath = entities_dir / f"{entity_name}.md"
        if not fpath.exists():
            self._send_error(404, f"Entity not found: {entity_name}")
            return

        try:
            raw = fpath.read_text(encoding="utf-8")
            content = raw.lstrip("|\n\t ")
        except Exception:
            self._send_error(500, "Failed to read entity file")
            return

        # Parse YAML frontmatter
        meta = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    if not isinstance(meta, dict):
                        meta = {}
                except Exception:
                    meta = {}
                body = parts[2].strip()

        # Parse sections from body (## SectionName)
        sections = {}
        current_section = "_pre"
        current_lines = []
        for line in body.split("\n"):
            m = _re.match(r"^##\s+(.+)$", line)
            if m:
                if current_lines:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = m.group(1).strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections[current_section] = "\n".join(current_lines).strip()

        # Build structured sections with just key-value pairs for 基本信息
        basic_info = {}
        if "基本信息" in sections:
            for line in sections["基本信息"].split("\n"):
                m = _re.match(r"-\s*\*\*(.+?)\*\*[：:]?\s*(.+)", line)
                if m:
                    basic_info[m.group(1).strip()] = m.group(2).strip()

        result = {
            "name": meta.get("title", entity_name),
            "meta": {
                k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in meta.items()
                if k in ("social_rank", "wecom_id", "tags", "created", "updated", "interaction_count", "last_interaction", "next_action")
            },
            "basic_info": basic_info,
            "sections": {k: v for k, v in sections.items() if k not in ("_pre",) and v},
        }
        self._json_response(result)

    def do_GET(self):
        clean_path = self.path.split("?")[0]
        if clean_path == "/api/data":
            self._json_response(self._load_data())
        elif clean_path == "/api/stats":
            self._handle_stats()
        elif clean_path == "/api/poll":
            self._handle_poll()
        elif clean_path == "/api/wiki/data":
            self._json_response(self._load_wiki_data())
        elif clean_path == "/api/wiki/pages":
            self._json_response(self._load_wiki_pages())
        elif clean_path == "/api/iq":
            self._json_response(self._compute_iq())
        elif clean_path == "/api/skills":
            self._json_response(self._scan_skills())
        elif clean_path.startswith("/api/skills/"):
            skill_name = clean_path.split("/api/skills/")[1]
            self._json_response(self._get_skill_detail(skill_name))
        elif clean_path == "/api/config":
            self._json_response(load_config())
        elif clean_path == "/api/documents/scan":
            self._handle_documents_scan()
        elif clean_path == "/api/documents/extract-stream":
            self._handle_extract_stream()
        elif clean_path == "/api/memories":
            self._handle_memories_list()
        elif clean_path.startswith("/api/memories/stats"):
            store = _get_store()
            if store:
                self._json_response(store.get_stats())
            else:
                self._json_response({"error": "Store not available"}, code=503)
        elif clean_path.startswith("/api/memories/"):
            entry_id = clean_path.split("/api/memories/")[1]
            store = _get_store()
            if store:
                entry = store.get_entry(entry_id)
                if entry:
                    self._json_response(entry)
                else:
                    self._json_response({"error": "Not found"}, code=404)
            else:
                self._json_response({"error": "Store not available"}, code=503)
        elif clean_path == "/api/meta/entries":
            store = _get_store()
            if store:
                entries = store.get_all_entries(status="active")
                self._json_response(entries)
            else:
                self._json_response([])
        elif clean_path.startswith("/api/meta/entries/"):
            # Check for decay-history sub-path first
            if clean_path.endswith("/decay-history"):
                entry_id = clean_path.replace("/api/meta/entries/", "").replace("/decay-history", "")
                store = _get_store()
                if store:
                    history = store.get_decay_history(entry_id)
                    self._json_response(history)
                else:
                    self._json_response({"error": "Store not available"}, code=503)
            elif clean_path.endswith("/recall-history"):
                # Recall history for a specific entry
                entry_id = clean_path.replace("/api/meta/entries/", "").replace("/recall-history", "")
                scanner = _get_recall_scanner()
                if scanner:
                    history = scanner.get_entry_recall_history(entry_id)
                    self._json_response(history)
                else:
                    self._json_response({"error": "RecallScanner not available"}, code=503)
            else:
                entry_id = clean_path.split("/api/meta/entries/")[1]
                # Skip pin/unpin paths handled elsewhere
                if entry_id.endswith("/pin") or entry_id.endswith("/unpin"):
                    pass  # handled in do_POST
                else:
                    store = _get_store()
                    if store:
                        entry = store.get_entry(entry_id)
                        if entry:
                            self._json_response(entry)
                        else:
                            self._json_response({"error": "Not found"}, code=404)
                    else:
                        self._json_response({"error": "Store not available"}, code=503)
        elif clean_path == "/api/meta/health":
            store = _get_store()
            if store:
                self._json_response(store.get_stats())
        elif clean_path == "/api/decay-trend":
            store = _get_store()
            if store:
                self._json_response(store.get_overall_decay_trend(days=30))
        elif clean_path == "/api/decay-trend-by-category":
            store = _get_store()
            if store:
                self._json_response(store.get_category_decay_trend(days=30))
        elif clean_path == "/api/decay-trend-by-agent":
            store = _get_store()
            if store:
                self._json_response(store.get_agent_decay_trend(days=30))
            else:
                self._json_response({"error": "Store not available"}, code=503)
        elif clean_path == "/api/kanban/tasks":
            self._handle_kanban_tasks()
        elif clean_path == "/api/blackboard":
            self._handle_blackboard()
        elif clean_path == "/api/wiki/index":
            self._handle_wiki_index()
        elif clean_path == "/api/proxy/agents":
            self._handle_proxy_agents()
        elif clean_path == "/api/recall/stats":
            scanner = _get_recall_scanner()
            if scanner:
                self._json_response(scanner.get_recall_stats())
            else:
                self._json_response({"error": "RecallScanner not available"}, code=503)
        elif clean_path == "/api/recall/scan":
            scanner = _get_recall_scanner()
            if scanner:
                result = scanner.scan()
                self._json_response(result)
            else:
                self._json_response({"error": "RecallScanner not available"}, code=503)
        elif clean_path == "/api/meta/snapshots":
            store = _get_store()
            if store:
                self._json_response(store.get_snapshots())
            else:
                self._json_response([])
        elif clean_path == "/api/meta/operations":
            store = _get_store()
            if store:
                self._json_response(store.get_operations_log())
            else:
                self._json_response([])
        elif clean_path == "/api/meta/evolution":
            # New endpoint: get evolution summary for an entry
            store = _get_store()
            if store:
                entry_id = self.path.split("?entry=")[1] if "entry=" in self.path else ""
                if entry_id:
                    summary = store.get_evolution_summary(entry_id)
                    if summary:
                        self._json_response(summary)
                    else:
                        self._json_response({"error": "Entry not found"}, code=404)
                else:
                    # Return overall evolution stats
                    stats = store.get_stats()
                    self._json_response({
                        "total_active": stats.get("total_active", 0),
                        "total_inactive": stats.get("total_inactive", 0),
                        "version_changes": stats.get("version_changes", 0),
                        "snapshots": stats.get("snapshots", 0),
                    })
            else:
                self._json_response({"error": "Store not available"}, code=503)
        elif clean_path == "/api/dna/timeline":
            # DNA timeline: agent evolution data for DNA visualization
            store = _get_store()
            if store:
                self._json_response(store.get_dna_timeline())
            else:
                self._json_response({"error": "Store not available"}, code=503)
        elif clean_path == "/api/consolidate/scan":
            self._handle_consolidate_scan()
        elif clean_path == "/api/consolidate/duplicates":
            self._handle_consolidate_duplicates()
        elif clean_path == "/api/consolidate/conflicts":
            self._handle_consolidate_conflicts()
        elif clean_path == "/api/consolidate/distribution":
            self._handle_consolidate_distribution()
        # 遗忘引擎 API
        elif clean_path == "/api/forget/analyze":
            self._handle_forget_analyze()
        elif clean_path == "/api/forget/execute":
            self._handle_forget_execute()
        elif clean_path == "/api/forget/restore":
            self._handle_forget_restore()
        # 分析引擎 API
        elif clean_path == "/api/analyze/patterns":
            self._handle_analyze_patterns()
        elif clean_path == "/api/analyze/graph":
            self._handle_analyze_graph()
        elif clean_path == "/api/analyze/importance":
            self._handle_analyze_importance()
        elif clean_path == "/api/analyze/completeness":
            self._handle_analyze_completeness()
        elif clean_path == "/api/analyze/full":
            self._handle_analyze_full()
        elif clean_path == "/api/social/graph":
            self._json_response(self._build_social_graph())
        elif clean_path.startswith("/api/social/entity/"):
            entity_name = clean_path.split("/api/social/entity/")[1]
            self._handle_social_entity(entity_name)
        elif clean_path == "/api/analyze/should-know-gaps":
            self._handle_should_know_gaps()
        elif clean_path == "/api/agents":
            self._json_response(self._get_agents())
        elif clean_path.startswith("/api/agents/discover"):
            self._discover_gateway()
        elif clean_path == "/api/agents/config":
            self._handle_agents_config_get()
        elif clean_path.startswith("/api/wiki/file/"):
            self._serve_wiki_file(clean_path)
        elif clean_path.startswith("/api/v1/"):
            self._handle_v1_api(clean_path)
        elif clean_path.startswith("/api/agents/"):
            # Handle /api/agents/{id}/default, /api/agents/{id}/switch
            parts = clean_path.split("/")
            if len(parts) >= 4:
                agent_id = parts[3]
                if clean_path.endswith("/default"):
                    self._set_default_agent(agent_id)
                elif clean_path.endswith("/switch"):
                    self._switch_agent(agent_id)
                else:
                    self._send_error(404, "Not found")
            else:
                self._send_error(404, "Not found")
        elif clean_path == "/api/import":
            self._json_response({"error": "Use POST"})
            self.path = "/index.html"
            super().do_GET()
        else:
            # For non-API paths, first try SelfMind static dir, then fallback to wiki dir
            target_name = clean_path.lstrip("/")
            if not target_name:
                # Root path "/" → serve index.html
                self.path = "/index.html"
                super().do_GET()
            else:
                local_file = Path(SELFMIND_DIR) / target_name
                if local_file.exists() and local_file.is_file():
                    super().do_GET()
                else:
                    # Fallback: search wiki directory for the requested filename
                    config = load_config()
                    wiki_path = config.get("wiki", {}).get("path", "")
                    if wiki_path:
                        wiki_dir = Path(wiki_path)
                        # Only search for files with an extension (html, pdf, png, etc.)
                        if Path(target_name).suffix:
                            matches = list(wiki_dir.rglob(target_name))
                            if matches:
                                rel_path = str(matches[0].relative_to(wiki_dir))
                                wiki_api_path = "/api/wiki/file/" + rel_path
                                self._serve_wiki_file(wiki_api_path)
                            else:
                                super().do_GET()
                        else:
                            super().do_GET()
                    else:
                        super().do_GET()

    def do_POST(self):
        clean_path = self.path.split("?")[0]

        if clean_path == "/api/refresh":
            data = refresh_data()
            self._json_response(
                {
                    "status": "ok",
                    "nodes": len(data["nodes"]),
                    "links": len(data["links"]),
                    "message": "Memory data refreshed",
                }
            )
            return

        if clean_path == "/api/wiki/refresh":
            data = self._refresh_wiki_data()
            self._json_response({
                "status": "ok",
                "nodes": len(data.get("nodes", [])),
                "links": len(data.get("links", [])),
                "message": "Wiki data refreshed",
            })
            return

        if clean_path == "/api/save":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                new_data = json.loads(body)
                new_data["lastUpdated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                self._json_response(
                    {
                        "status": "ok",
                        "path": str(DATA_FILE),
                        "message": "Data saved",
                    }
                )
            except Exception as exc:
                self._json_response({"status": "error", "message": str(exc)}, code=400)
            return

        if clean_path == "/api/agents/config":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                action = data.get("action", "")
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                agents = config.get("agents", [])
                
                if action == "add":
                    agents.append(data["agent"])
                    config["agents"] = agents
                elif action == "delete":
                    config["agents"] = [a for a in agents if a.get("id") != data["agent_id"]]
                elif action == "update":
                    for i, a in enumerate(agents):
                        if a.get("id") == data["agent"].get("id"):
                            agents[i] = data["agent"]
                    config["agents"] = agents
                elif action == "set_default":
                    config["current_agent"] = data["agent_id"]
                elif action == "update_global":
                    config["sync_interval"] = data.get("sync_interval", 5)
                    config["decay_threshold"] = data.get("decay_threshold", 0.2)
                
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                self._json_response({"status": "ok", "message": "Config saved"})
            except Exception as exc:
                self._json_response({"status": "error", "message": str(exc)}, code=400)
            return

        if clean_path == "/api/config":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                new_config = json.loads(body)
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, ensure_ascii=False, indent=2)
                self._json_response({"status": "ok", "message": "Config saved"})
            except Exception as exc:
                self._json_response({"status": "error", "message": str(exc)}, code=400)
            return

        if clean_path == "/api/documents/extract":
            self._handle_documents_extract()
            return

        if clean_path == "/api/memories":
            self._handle_memories_add()
            return

        if clean_path == "/api/memories/sync":
            self._handle_memories_sync()
            return

        if clean_path == "/api/memories/bulk-status":
            self._handle_memories_bulk_status()
            return

        if clean_path == "/api/meta/sync":
            self._handle_meta_sync()
            return

        if clean_path == "/api/meta/snapshots":
            self._handle_meta_create_snapshot()
            return

        if clean_path == "/api/meta/decay":
            store = _get_store()
            if store:
                count = store.compute_decay_scores()
                self._json_response({"status": "ok", "updated": count})
            else:
                self._json_response({"error": "Store not available"}, code=503)
            return

        if clean_path.startswith("/api/meta/entries/") and clean_path.endswith("/pin"):
            entry_id = clean_path.split("/api/meta/entries/")[1].replace("/pin", "")
            store = _get_store()
            if store:
                store.pin_entry(entry_id)
                self._json_response({"status": "ok", "pinned": True})
            else:
                self._json_response({"error": "Store not available"}, code=503)
            return

        if clean_path.startswith("/api/meta/entries/") and clean_path.endswith("/unpin"):
            entry_id = clean_path.split("/api/meta/entries/")[1].replace("/unpin", "")
            store = _get_store()
            if store:
                store.unpin_entry(entry_id)
                self._json_response({"status": "ok", "pinned": False})
            else:
                self._json_response({"error": "Store not available"}, code=503)
            return

        if clean_path.startswith("/api/meta/snapshots/") and clean_path.endswith("/restore"):
            sid = clean_path.split("/api/meta/snapshots/")[1].replace("/restore", "")
            store = _get_store()
            if store:
                try:
                    snap = store.restore_snapshot(int(sid))
                except (ValueError, TypeError):
                    snap = None
                if snap:
                    self._json_response(snap)
                else:
                    self._json_response({"error": "Snapshot not found"}, code=404)
            else:
                self._json_response({"error": "Store not available"}, code=503)
            return

        if clean_path == "/api/consolidate/llm":
            self._handle_consolidate_llm()
            return

        if clean_path == "/api/agents":
            self._add_agent()
            return

        if clean_path.startswith("/api/agents/discover"):
            self._discover_gateway()
            return

        if clean_path.startswith("/api/v1/"):
            self._handle_v1_api_post(clean_path)
            return

        if clean_path == "/api/import":
            self._import_memory()
            return

        if clean_path.startswith("/api/agents/") and clean_path.endswith("/switch"):
            agent_id = clean_path.split("/api/agents/")[1].replace("/switch", "")
            self._switch_agent(agent_id)
            return

        # ── Manual intervention CRUD ───────────────────────────
        if clean_path == "/api/manual/memories":
            self._handle_manual_add()
            return

        if clean_path.startswith("/api/manual/memories/") and clean_path.endswith("/delete"):
            entry_id = clean_path.split("/api/manual/memories/")[1].replace("/delete", "")
            self._handle_manual_delete(entry_id)
            return

        self._json_response({"error": "Not found"}, code=404)

    def do_PUT(self):
        clean_path = self.path.split("?")[0]
        if clean_path == "/api/wiki/page":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""
            self._json_response(self._save_wiki_page(body))
            return

        if clean_path.startswith("/api/memories/"):
            entry_id = clean_path.split("/api/memories/")[1]
            self._handle_memory_update(entry_id)
            return

        if clean_path.startswith("/api/agents/") and clean_path.endswith("/default"):
            agent_id = clean_path.split("/api/agents/")[1].replace("/default", "")
            self._set_default_agent(agent_id)
            return

        if clean_path.startswith("/api/manual/memories/"):
            entry_id = clean_path.split("/api/manual/memories/")[1]
            self._handle_manual_update(entry_id)
            return

        self._json_response({"error": "Not found"}, code=404)

    def do_DELETE(self):
        clean_path = self.path.split("?")[0]
        if clean_path.startswith("/api/memories/"):
            entry_id = clean_path.split("/api/memories/")[1]
            store = _get_store()
            if store:
                store.update_entry(entry_id, status="inactive")
                self._json_response({"status": "ok", "message": "Entry inactivated"})
            else:
                self._json_response({"error": "Store not available"}, code=503)
            return

        if clean_path.startswith("/api/agents/"):
            agent_id = clean_path.split("/api/agents/")[1]
            self._delete_agent(agent_id)
            return

        self._json_response({"error": "Not found"}, code=404)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_error(self, code, message):
        self._json_response({"error": message}, code)

    def _sanitize_for_json(self, obj):
        """Recursively clean control characters from strings for valid JSON output."""
        import re
        _ctrl_re = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
        if isinstance(obj, str):
            return _ctrl_re.sub('', obj)
        if isinstance(obj, dict):
            return {self._sanitize_for_json(k): self._sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(i) for i in obj]
        return obj

    def _handle_kanban_tasks(self):
        """Read kanban tasks from Hermes kanban.db."""
        import sqlite3
        # Priority: env var > ~/.hermes/kanban.db > ~/.hermes/kanban/kanban.db
        kanban_path = os.environ.get("HERMES_KANBAN_DB", "")
        if kanban_path and os.path.exists(kanban_path):
            pass  # use the env var path
        elif os.path.exists(os.path.expanduser("~/.hermes/kanban.db")):
            kanban_path = os.path.expanduser("~/.hermes/kanban.db")
        elif os.path.exists(os.path.expanduser("~/.hermes/kanban/kanban.db")):
            kanban_path = os.path.expanduser("~/.hermes/kanban/kanban.db")
        else:
            # Fallback: try absolute known path
            fallback = "/Users/liuxiaocheng/.hermes/kanban.db"
            if os.path.exists(fallback):
                kanban_path = fallback
            else:
                self._json_response({"tasks": [], "error": "kanban.db not found"})
                return
        try:
            conn = sqlite3.connect(kanban_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Check table schema first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            if 'tasks' not in tables:
                self._json_response({"tasks": [], "error": "no tasks table"})
                conn.close()
                return
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]
            cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            rows = cursor.fetchall()
            tasks = []
            for row in rows:
                task = {}
                for col in columns:
                    val = row[columns.index(col)]
                    # Convert datetime strings for JSON
                    if val and col in ('created_at', 'updated_at'):
                        task[col] = str(val)
                    else:
                        task[col] = val
                tasks.append(task)
            conn.close()
            self._json_response({"tasks": tasks, "total": len(tasks)})
        except Exception as e:
            self._json_response({"tasks": [], "error": str(e)})

    def _handle_blackboard(self):
        """Read blackboard notification files and return parsed notice list."""
        import re
        wiki_base = Path(os.environ.get(
            "SELFMIND_WIKI_PATH",
            "/Users/liuxiaocheng/Documents/aiworkspace/wiki"
        ))

        # Define blackboard files: owner -> file path
        board_files = [
            ("小亚", wiki_base / "blackboard" / "for-aris.md"),
            ("小亚", wiki_base / "nous" / "for-aris.md"),
            ("柏拉图", wiki_base / "nous" / "for-plato.md"),
        ]

        boards = {}
        for owner, fpath in board_files:
            if not fpath.exists():
                continue
            try:
                content = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            # Strip YAML frontmatter if present
            body = content
            fm_match = re.match(r"^---\s*$.*?^---\s*$(.*)", content, re.DOTALL | re.MULTILINE)
            if fm_match:
                body = fm_match.group(1).strip()

            # Parse sections: each ## heading is a notification
            notices = []
            sections = re.split(r"^##\s+", body, flags=re.MULTILINE)
            for sec in sections:
                sec = sec.strip()
                if not sec:
                    continue
                lines = sec.split("\n")
                header = lines[0].strip()
                body_text = "\n".join(l[2:] if l.startswith("> ") else l for l in lines[1:] if l.strip()).strip()

                # Extract date and optional emoji tag
                date_match = re.match(
                    r"(\d{4}-\d{2}-\d{2})\s+(.*)", header
                )
                if date_match:
                    date = date_match.group(1)
                    title = date_match.group(2).strip()
                else:
                    date = None
                    title = header

                notices.append({
                    "date": date,
                    "title": title,
                    "content": body_text,
                    "source": fpath.name,
                })

            boards.setdefault(owner, []).extend(notices)

        self._json_response({"boards": boards, "total_notices": sum(len(v) for v in boards.values())})

    def _handle_wiki_index(self):
        """Read wiki/index.md and return document category tree."""
        import re
        wiki_base = Path(os.environ.get(
            "SELFMIND_WIKI_PATH",
            "/Users/liuxiaocheng/Documents/aiworkspace/wiki"
        ))
        index_path = wiki_base / "index.md"

        if not index_path.exists():
            self._json_response({"categories": [], "total_pages": 0})
            return

        content = index_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        categories = []
        current_category = None
        current_docs = []

        # Parse header metadata
        header = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("> Last updated:"):
                date_part = stripped.replace("> Last updated:", "").strip()
                header["last_updated"] = date_part.split("|")[0].strip()
            if "Total pages:" in stripped:
                m = re.search(r"Total pages:\s*(\d+)", stripped)
                if m:
                    header["total_pages"] = int(m.group(1))

        for line in lines:
            stripped = line.strip()
            # Detect category heading
            if stripped.startswith("## ") and not stripped.startswith("### "):
                if current_category and current_docs:
                    categories.append({
                        "name": current_category,
                        "documents": current_docs,
                        "count": len(current_docs),
                    })
                    current_docs = []
                current_category = stripped[3:].strip()
            elif stripped.startswith("- [[") and current_category:
                # Parse: - [[PageName]] - description
                m = re.match(r"- \[\[(.+?)\]\]\s*-\s*(.*)", stripped)
                if m:
                    page_name = m.group(1).strip()
                    description = m.group(2).strip()
                else:
                    m2 = re.match(r"- \[\[(.+?)\]\]\s*(.*)", stripped)
                    page_name = m2.group(1).strip() if m2 else stripped
                    description = m2.group(2).strip() if m2 else ""
                current_docs.append({
                    "name": page_name,
                    "description": description,
                })

        # Flush last category
        if current_category and current_docs:
            categories.append({
                "name": current_category,
                "documents": current_docs,
                "count": len(current_docs),
            })

        total_pages = sum(c["count"] for c in categories)
        self._json_response({
            "categories": categories,
            "total_pages": total_pages,
            "meta": header,
        })

    def _handle_proxy_agents(self):
        """Proxy agent health checks — fetch all Hermes agent health endpoints
        and return aggregated results. Solves CORS issues when dashboard is
        served from a different origin than the agents."""
        import subprocess
        import json
        agents = [
            {"id": "socrates", "name": "苏格拉底", "port": 8642},
            {"id": "aris",     "name": "小亚",     "port": 8643},
            {"id": "plato",    "name": "柏拉图",   "port": 8645},
            {"id": "grace",    "name": "Grace",    "port": 8644},
            {"id": "gateway",  "name": "Gateway",  "port": 8000},
        ]
        results = {}
        for a in agents:
            try:
                url = f"http://localhost:{a['port']}/health"
                # Use curl with --noproxy to bypass system proxy for localhost
                proc = subprocess.run(
                    ["curl", "-s", "--max-time", "3", "--noproxy", "*", url],
                    capture_output=True, text=True, timeout=5
                )
                if proc.returncode == 0 and proc.stdout:
                    data = json.loads(proc.stdout)
                    if data.get("status") == "ok":
                        results[a["id"]] = data
                    else:
                        results[a["id"]] = None
                else:
                    results[a["id"]] = None
            except Exception:
                results[a["id"]] = None
        self._json_response(results)

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        clean = self._sanitize_for_json(data)
        self.wfile.write(json.dumps(clean, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {args[0]}")