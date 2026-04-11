import json
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from typing import Optional

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config
from selfmind_app.parser import build_graph


def _node_signature(node: dict) -> str:
    return "|".join(
        [
            node.get("label", ""),
            node.get("category", ""),
            node.get("description", ""),
        ]
    )


def _safe_read_existing_data() -> Optional[dict]:
    if not DATA_FILE.exists():
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _apply_node_timestamps(new_data: dict, previous_data: Optional[dict]) -> dict:
    """Attach createdAt/updatedAt to nodes using previous snapshot as baseline."""
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    prev_nodes = (previous_data or {}).get("nodes", [])
    prev_by_id = {node.get("id"): node for node in prev_nodes if node.get("id")}

    for node in new_data.get("nodes", []):
        node_id = node.get("id")
        prev = prev_by_id.get(node_id)

        if not prev:
            node["createdAt"] = now_iso
            node["updatedAt"] = now_iso
            continue

        prev_created = prev.get("createdAt") or now_iso
        prev_updated = prev.get("updatedAt") or prev_created

        node["createdAt"] = prev_created
        if _node_signature(prev) != _node_signature(node):
            node["updatedAt"] = now_iso
        else:
            node["updatedAt"] = prev_updated

    return new_data


def refresh_data() -> dict:
    """Rebuild graph from memory files and write to data.json."""
    config = load_config()
    previous = _safe_read_existing_data()
    data = _apply_node_timestamps(build_graph(config), previous)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


class SelfMindHandler(SimpleHTTPRequestHandler):
    """HTTP handler for SelfMind API + static files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SELFMIND_DIR), **kwargs)

    def do_GET(self):
        clean_path = self.path.split("?")[0]
        if clean_path == "/api/data":
            self._json_response(self._load_data())
        elif clean_path == "/api/config":
            self._json_response(load_config())
        elif clean_path == "/":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/refresh":
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

        if self.path == "/api/save":
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

        if self.path == "/api/config":
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

        self._json_response({"error": "Not found"}, code=404)

    def _load_data(self):
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Backfill timestamps for old data files that predate createdAt/updatedAt.
            if any("createdAt" not in node or "updatedAt" not in node for node in data.get("nodes", [])):
                data = _apply_node_timestamps(data, None)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        return refresh_data()

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {args[0]}")
