"""Clean up benchmark/performance test entries from the DB."""
import sys
sys.path.insert(0, '/Users/liuxiaocheng/Documents/selfmind')
from selfmind_app.unified_store import UnifiedStore
from pathlib import Path

db_path = str(Path('/Users/liuxiaocheng/Documents/selfmind') / 'data' / 'selfmind.db')
store = UnifiedStore(db_path)
entries = store.get_all_entries()

benchmarks = [e for e in entries if 'benchmark' in (e.get('label', '') + e.get('content_preview', '') + e.get('primary_cat', '')).lower()]
print(f'Found {len(benchmarks)} benchmark entries')
for b in benchmarks:
    print(f'  id={b["id"][:12]}... label={b.get("label", "")} type={b.get("type", "")}')

# Mark them inactive
for b in benchmarks:
    store.update_entry(b["id"], {"status": "inactive"})
    print(f'  Marked inactive: {b["id"][:12]}')

store.close()
print(f'\n✅ Cleaned up {len(benchmarks)} benchmark entries')