#!/usr/bin/env python3
"""SelfMind — Memory Knowledge Graph Server.

Usage:
    python3 server.py                           # default port 3002
    python3 server.py 8080                      # custom port
    HERMES_HOME=~/.hermes python3 server.py     # custom hermes source
    OPENCLAW_HOME=~/.openclaw python3 server.py # custom openclaw source
"""

import os
import sys
from http.server import HTTPServer

from selfmind_app.config import SELFMIND_DIR, describe_sources, load_config, save_default_config
from selfmind_app.http_handler import SelfMindHandler, refresh_data


# ─── Main ────────────────────────────────────────────────────────────

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3002

    # Ensure data directory exists
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    save_default_config()

    config = load_config()

    print(f"🧠 SelfMind — Memory Knowledge Graph")
    print(f"   Sources: {describe_sources(config)}")
    print(f"   Parsing memory files...")

    data = refresh_data()

    print(f"   ✅ {len(data['nodes'])} nodes, {len(data['links'])} links")

    # Auto-sync meta_db from memory files
    from selfmind_app.http_handler import _meta_db
    config_for_sync = load_config()
    source_cfg = config_for_sync.get("source", {})
    active = source_cfg.get("active_profile", "hermes")
    profile = source_cfg.get("profiles", {}).get(active, {})
    home = profile.get("home", "")
    memory_path = user_path = None
    for f in profile.get("memory_files", []):
        full = os.path.join(home, f)
        if os.path.exists(full):
            if "memory" in f.lower():
                memory_path = full
            elif "user" in f.lower():
                user_path = full
    if not memory_path:
        for f in profile.get("memory_files_fallback", []):
            full = os.path.join(home, f)
            if os.path.exists(full):
                if "memory" in f.lower():
                    memory_path = full
                elif "user" in f.lower():
                    user_path = full
    if memory_path:
        sync_result = _meta_db.sync_from_memory_files(memory_path, user_path)
        _meta_db.compute_decay_scores()
        print(f"   📋 Meta sync: +{sync_result['added']} added, ~{sync_result['updated']} updated, -{sync_result['deleted']} deleted")
    else:
        print(f"   ⚠️ No memory file found for meta sync")

    print(f"   📂 Data: {SELFMIND_DIR}")
    print(f"   🌐 http://localhost:{port}")
    print(f"   Press Ctrl+C to stop\n")

    server = HTTPServer(("0.0.0.0", port), SelfMindHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        server.server_close()


if __name__ == "__main__":
    main()
