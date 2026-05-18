#!/usr/bin/env python3
"""SelfMind — Memory Evolution Server. (auto-rebuild via dev-watch.py)

Unified data pipeline: all sources (memory files, wiki, Honcho, skills)
sync into a single SQLite store with evolution tracking.
Every sync creates a snapshot, tracks version changes, never deletes history.

Usage:
    python3 server.py                           # default port 3002
    python3 server.py 8080                      # custom port
    HERMES_HOME=~/.hermes python3 server.py     # custom hermes source
"""

import os
import sys
from http.server import HTTPServer
from pathlib import Path

from selfmind_app.config import SELFMIND_DIR, describe_sources, load_config, save_default_config


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3002

    # Ensure data directory exists
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    save_default_config()
    config = load_config()

    # ── Initialize unified store ──
    from selfmind_app.unified_store import UnifiedStore
    from selfmind_app.unified_sync import unified_sync
    from selfmind_app.parser import build_graph_from_store

    db_path = str(data_dir / "selfmind.db")
    store = UnifiedStore(db_path)

    # ── Run unified sync (all sources → SQLite) ──
    print("🧠 SelfMind — Evolution Tracking Pipeline")
    print(f"   Sources: {describe_sources(config)}")
    print(f"   Syncing all sources...")

    sync_stats = unified_sync(store, config)
    total_active = sync_stats.get("total_active", 0)
    total_inactive = sync_stats.get("total_inactive", 0)
    by_type = sync_stats.get("by_type", {})
    version_changes = sync_stats.get("version_changes", 0)
    print(f"   ✅ {total_active} active, {total_inactive} inactive, {version_changes} version changes")
    print(f"   Types: {by_type}")

    # ── Build graph from store ──
    data = build_graph_from_store(store, config)
    print(f"   📊 {len(data['nodes'])} nodes, {len(data['links'])} links")

    # ── Initialize recall scanner ──
    from selfmind_app.recall_capture import RecallScanner, HermesAdapter
    recall_scanner = RecallScanner(store, adapters=[HermesAdapter()])

    # ── Wire up http handler ──
    from selfmind_app.http_handler import SelfMindHandler
    SelfMindHandler._store = store
    SelfMindHandler._graph_data = data
    SelfMindHandler._config = config
    SelfMindHandler._recall_scanner = recall_scanner

    # ── Background sync thread (periodic sync + recall scan) ──
    import threading

    def periodic_sync():
        """Periodic sync cycle: resync data + scan recall + rebuild graph."""
        while True:
            try:
                import time
                time.sleep(300)  # 5 minutes
                
                # Step 1: Resync all sources
                sync_stats = unified_sync(store, config)
                total_active = sync_stats.get("total_active", 0)
                
                # Step 2: Scan agent recall
                recall_result = recall_scanner.scan()
                recalls = recall_result.get("recalls_recorded", 0)
                
                # Step 3: Recompute decay (now uses recall data)
                store.compute_decay_scores()
                
                # Step 4: Rebuild graph
                new_data = build_graph_from_store(store, config)
                SelfMindHandler._graph_data = new_data
                
                print(f"   [Auto-sync] {total_active} active, {recalls} recalls, graph rebuilt")
            except Exception as e:
                print(f"   [Auto-sync] Error: {e}")

    sync_thread = threading.Thread(target=periodic_sync, daemon=True)
    sync_thread.start()
    print(f"   🔄 Auto-sync thread started (5 min interval)")

    print(f"   📂 Data: {SELFMIND_DIR}")
    print(f"   🌐 http://localhost:{port}")
    print(f"   Press Ctrl+C to stop\n")

    server = HTTPServer(("0.0.0.0", port), SelfMindHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        store.close()
        server.server_close()


if __name__ == "__main__":
    main()