#!/usr/bin/env python3
"""SelfMind — Memory Knowledge Graph Server.

Usage:
    python3 server.py                           # default port 3002
    python3 server.py 8080                      # custom port
    HERMES_HOME=~/.hermes python3 server.py     # custom hermes source
    OPENCLAW_HOME=~/.openclaw python3 server.py # custom openclaw source
"""

import sys
from http.server import HTTPServer

from selfmind_app.config import SELFMIND_DIR, describe_sources, load_config, save_default_config
from selfmind_app.http_handler import SelfMindHandler, refresh_data


# ─── Main ────────────────────────────────────────────────────────────

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3002

    save_default_config()

    config = load_config()

    print(f"🧠 SelfMind — Memory Knowledge Graph")
    print(f"   Sources: {describe_sources(config)}")
    print(f"   Parsing memory files...")

    data = refresh_data()

    print(f"   ✅ {len(data['nodes'])} nodes, {len(data['links'])} links")
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
