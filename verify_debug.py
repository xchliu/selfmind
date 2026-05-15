import sys
sys.path.insert(0, '/Users/liuxiaocheng/Documents/selfmind')
from selfmind_app.unified_store import UnifiedStore
from selfmind_app.config import load_config
from selfmind_app.parser import build_graph_from_store
from pathlib import Path

store = UnifiedStore(str(Path('/Users/liuxiaocheng/Documents/selfmind') / 'data' / 'selfmind.db'))
config = load_config()
data = build_graph_from_store(store, config)

nodes = data["nodes"]
links = data["links"]
entries = store.get_all_entries(status="active")

# Debug: check entry types
from collections import Counter
type_counts = Counter(e["type"] for e in entries)
print(f"DB entry types: {type_counts}")

# Debug: check graph node entry_types
graph_type_counts = Counter(n.get("entry_type", n.get("category","")) for n in nodes)
print(f"Graph node types: {graph_type_counts}")

# Debug: which DB IDs are NOT in graph?
db_ids = set(e["id"] for e in entries)
graph_ids = set(n.get("id","") for n in nodes)
missing = db_ids - graph_ids
print(f"Missing DB IDs: {len(missing)} out of {len(db_ids)}")
# Show missing types
missing_types = Counter(e["type"] for e in entries if e["id"] in missing)
print(f"Missing by type: {missing_types}")

# Debug: check memory labels and content
memory_entries = [e for e in entries if e["type"] == "memory"]
print(f"\nMemory entries: {len(memory_entries)}")
labels = [e.get("label","") for e in memory_entries if e.get("label")]
print(f"Memory labels (sample): {labels[:10]}")

# Check if any memory label appears in another memory's content
matches = 0
for entry in memory_entries:
    content = entry.get("content", "")
    if not content:
        content = entry.get("content_preview", "")
    for other in memory_entries:
        if other["id"] == entry["id"]:
            continue
        other_label = other.get("label", "")
        if len(other_label) >= 2 and other_label in content:
            matches += 1
print(f"Memory→Memory label matches: {matches}")

# Check skill→memory cross-refs
skill_entries = [e for e in entries if e["type"] == "skill"]
print(f"\nSkill entries: {len(skill_entries)}")
for se in skill_entries[:3]:
    skill_text = se.get("content_preview", "") + " " + se.get("label", "")
    print(f"  Skill label: {se.get('label','')}, text sample: {skill_text[:80]}")

# Check honcho→memory cross-refs
honcho_entries = [e for e in entries if e["type"] in ("honcho_obs", "honcho_conc")]
print(f"\nHoncho entries: {len(honcho_entries)}")
for he in honcho_entries[:3]:
    h_text = he.get("content", "") + " " + he.get("content_preview", "")
    print(f"  Honcho type: {he['type']}, label: {he.get('label','')}, text sample: {h_text[:80]}")

store.close()
print("\n✅ Debug done")