"""V1 API handler methods: wiki data, changes, status, memories, sync."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config, get_enabled_profiles
from selfmind_app.wiki_parser import build_wiki_graph

logger = logging.getLogger(__name__)


class V1Mixin:
    """Handler methods for v1 API and wiki data."""

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
        """处理 v1 API GET 请求"""
        from datetime import datetime
        from selfmind_app.http_handler import _get_aggregation_engine

        if path == "/api/v1/changes":
            # 获取聚合变化
            since_str = self._get_query_param("since")
            since = None
            if since_str:
                try:
                    since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
                except ValueError:
                    self._json_response({"error": "Invalid since parameter"}, code=400)
                    return

            engine = _get_aggregation_engine()
            result = engine.aggregate_changes(since)

            self._json_response({
                "changes": [
                    {
                        "change_id": c.change_id,
                        "item_id": c.item_id,
                        "source": c.source,
                        "change_type": c.change_type,
                        "timestamp": c.timestamp.isoformat(),
                        "content": c.after.content[:200] if c.after else None,
                        "category": c.after.category if c.after else None,
                    }
                    for c in result.changes[:50]  # 限制返回数量
                ],
                "providers": [
                    {
                        "name": p.name,
                        "status": p.status,
                        "item_count": p.item_count,
                    }
                    for p in result.providers
                ],
                "stats": {
                    "total": result.total_count,
                    "created": result.created_count,
                    "updated": result.updated_count,
                    "deleted": result.deleted_count,
                }
            })
            return

        if path == "/api/v1/status":
            # 获取 Provider 状态
            engine = _get_aggregation_engine()
            status = engine.get_provider_status()
            self._json_response({
                "providers": status,
                "timestamp": datetime.now().isoformat()
            })
            return

        if path == "/api/v1/memories":
            # 获取所有记忆
            engine = _get_aggregation_engine()
            items = engine.get_all_memories()
            self._json_response({
                "memories": [
                    {
                        "id": m.id,
                        "source": m.source,
                        "category": m.category,
                        "content": m.content[:200],
                        "importance": m.importance,
                        "tags": m.tags,
                        "created_at": m.created_at.isoformat(),
                        "updated_at": m.updated_at.isoformat(),
                    }
                    for m in items[:100]
                ],
                "total": len(items)
            })
            return

        self._json_response({"error": "Not found"}, code=404)

    def _handle_v1_api_post(self, path: str):
        """处理 v1 API POST 请求"""
        from selfmind_app.http_handler import _get_aggregation_engine, refresh_data
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/api/v1/sync":
            # 触发同步
            try:
                body_json = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._json_response({"error": "Invalid JSON"}, code=400)
                return

            force = body_json.get("force", False)

            # 刷新数据
            data = refresh_data()
            engine = _get_aggregation_engine()

            self._json_response({
                "status": "ok",
                "message": "Sync completed",
                "nodes": len(data.get("nodes", [])),
                "links": len(data.get("links", [])),
                "providers": engine.get_provider_status()
            })
            return

        self._json_response({"error": "Not found"}, code=404)

    def _get_query_param(self, key: str) -> Optional[str]:
        """获取 URL 查询参数"""
        import urllib.parse
        if "?" in self.path:
            query = self.path.split("?")[1]
            params = urllib.parse.parse_qs(query)
            result = params.get(key, [])
            return result[0] if result else None
        return None