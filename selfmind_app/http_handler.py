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
            else:
                self._json_response({"error": "Store not available"}, code=503)
        elif clean_path == "/api/decay-trend":
            store = _get_store()
            if store:
                self._json_response(store.get_overall_decay_trend(days=30))
            else:
                self._json_response({"error": "Store not available"}, code=503)
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

        if clean_path.startswith("/api/agents/") and clean_path.endswith("/switch"):
            agent_id = clean_path.split("/api/agents/")[1].replace("/switch", "")
            self._switch_agent(agent_id)
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

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        clean = self._sanitize_for_json(data)
        self.wfile.write(json.dumps(clean, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {args[0]}")