"""V1 API handler methods: wiki data, changes, status, memories, sync."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config, get_enabled_profiles
from selfmind_app.wiki_parser import build_wiki_graph, scan_wiki_pages_flat, parse_frontmatter

logger = logging.getLogger(__name__)


class V1Mixin:
    """Handler methods for v1 API and wiki data."""

    def _load_wiki_pages(self) -> dict:
        """Load wiki pages as flat list for library view."""
        config = load_config()
        wiki_cfg = config.get("wiki", {})
        wiki_path = wiki_cfg.get("path", "")
        if not wiki_cfg.get("enabled", False) or not wiki_path:
            return {"pages": [], "categories": {}}
        pages = scan_wiki_pages_flat(wiki_path)
        # Group by type for frontend
        categories: dict[str, list[dict]] = {}
        for p in pages:
            cat = p.get("type", "uncategorized")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(p)
        return {"pages": pages, "categories": categories, "total": len(pages)}

    def _load_wiki_data(self) -> dict:
        """Load wiki graph data, building from wiki files."""
        wiki_data_file = SELFMIND_DIR / "data" / "wiki_data.json"
        if wiki_data_file.exists():
            try:
                with open(wiki_data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return self._refresh_wiki_data()

    def _refresh_wiki_data(self) -> dict:
        """Rebuild wiki graph from wiki markdown files."""
        config = load_config()
        data = build_wiki_graph(config)
        wiki_data_file = SELFMIND_DIR / "data" / "wiki_data.json"
        with open(wiki_data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def _handle_v1_api(self, path: str):
        """Handle v1 API GET requests — now backed by UnifiedStore."""
        from selfmind_app.http_handler import _get_store

        store = _get_store()

        if path == "/api/v1/changes":
            # Return recent evolution events from operations_log
            since_str = self._get_query_param("since")
            if not store:
                self._json_response({"changes": [], "stats": {}})
                return
            ops = store.get_operations_log(limit=50)
            changes = []
            for op in ops:
                changes.append({
                    "change_id": str(op.get("id", "")),
                    "item_id": ", ".join(op.get("target_ids", [])),
                    "source": "selfmind",
                    "change_type": op.get("operation", ""),
                    "timestamp": op.get("timestamp", ""),
                    "detail": op.get("detail", {}),
                })
            stats = store.get_stats()
            self._json_response({
                "changes": changes,
                "providers": [{"name": "selfmind", "status": "active", "item_count": stats.get("total_active", 0)}],
                "stats": {
                    "total": stats.get("total_active", 0) + stats.get("total_inactive", 0),
                    "created": stats.get("total_active", 0),
                    "updated": stats.get("version_changes", 0),
                    "deleted": stats.get("total_inactive", 0),
                }
            })
            return

        if path == "/api/v1/status":
            # Return store status
            if not store:
                self._json_response({"providers": [], "timestamp": datetime.now().isoformat()})
                return
            stats = store.get_stats()
            self._json_response({
                "providers": [{"name": "selfmind-unified", "status": "active", "item_count": stats.get("total_active", 0)}],
                "timestamp": datetime.now().isoformat()
            })
            return

        if path == "/api/v1/memories":
            # Return all active memory entries
            if not store:
                self._json_response({"memories": [], "total": 0})
                return
            entries = store.get_all_entries(status="active")
            memories = [e for e in entries if e.get("type") == "memory"]
            self._json_response({
                "memories": [
                    {
                        "id": m.get("id", ""),
                        "source": m.get("source", ""),
                        "category": f"{m.get('primary_cat', '')}/{m.get('secondary_cat', '')}",
                        "content": m.get("content_preview", "")[:200],
                        "importance": m.get("importance", 0.5),
                        "decay_score": m.get("decay_score", 0.25),
                        "version": m.get("version", 1),
                        "first_seen_at": m.get("first_seen_at", ""),
                        "updated_at": m.get("updated_at", ""),
                    }
                    for m in memories[:100]
                ],
                "total": len(memories)
            })
            return

        self._json_response({"error": "Not found"}, code=404)

    def _handle_v1_api_post(self, path: str):
        """Handle v1 API POST requests."""
        from selfmind_app.http_handler import _get_store
        from selfmind_app.unified_sync import UnifiedSync

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/api/v1/sync":
            # Trigger manual sync
            store = _get_store()
            if store:
                sync = UnifiedSync(store)
                sync.run()
                data = store.get_stats()
                self._json_response({
                    "status": "ok",
                    "message": "Sync completed",
                    "total_active": data.get("total_active", 0),
                    "total_inactive": data.get("total_inactive", 0),
                    "version_changes": data.get("version_changes", 0),
                })
            else:
                self._json_response({"error": "Store not available"}, code=503)
            return

        self._json_response({"error": "Not found"}, code=404)

    def _save_wiki_page(self, body: bytes) -> dict:
        """Save edited wiki page content back to the markdown file."""
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON"}

        page_path = data.get("path", "")
        content = data.get("content", "")
        title = data.get("title", "")
        tags = data.get("tags", [])

        if not page_path:
            return {"error": "Missing path"}

        config = load_config()
        wiki_path = config.get("wiki", {}).get("path", "")
        if not wiki_path:
            return {"error": "Wiki not configured"}

        full_path = Path(wiki_path) / page_path
        if not full_path.exists():
            return {"error": f"Page not found: {page_path}"}

        # Read original file to preserve frontmatter
        original = full_path.read_text(encoding="utf-8")
        fm = parse_frontmatter(original)

        # Update frontmatter fields
        if title:
            fm["title"] = title
        if tags:
            fm["tags"] = tags
        fm["updated"] = datetime.now().strftime("%Y-%m-%d")

        # Rebuild frontmatter block
        fm_lines = ["---"]
        fm_lines.append(f"title: \"{fm.get('title', '')}\"")
        fm_lines.append(f"type: \"{fm.get('type', '')}\"")
        if fm.get("created"):
            fm_lines.append(f"created: \"{fm['created']}\"")
        fm_lines.append(f"updated: \"{fm['updated']}\"")
        if fm.get("tags"):
            fm_lines.append(f"tags: [{', '.join(fm['tags'])}]")
        if fm.get("sources"):
            fm_lines.append(f"sources: [{', '.join(fm['sources'])}]")
        fm_lines.append("---")

        # Write back: frontmatter + new body
        new_file_content = "\n".join(fm_lines) + "\n\n" + content + "\n"
        full_path.write_text(new_file_content, encoding="utf-8")

        logger.info(f"Wiki page saved: {page_path}")
        return {"status": "ok", "path": page_path, "updated": fm["updated"]}

    def _get_query_param(self, key: str) -> Optional[str]:
        """Get URL query parameter."""
        import urllib.parse
        if "?" in self.path:
            query = self.path.split("?")[1]
            params = urllib.parse.parse_qs(query)
            result = params.get(key, [])
            return result[0] if result else None
        return None