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

# 验证1: ID映射率
db_ids = set(e["id"] for e in entries)
graph_ids = set(n.get("id","") for n in nodes)
id_overlap = db_ids & graph_ids
id_overlap_pct = len(id_overlap)/max(len(db_ids),1)*100
print(f"ID映射率: {id_overlap_pct}% (目标>80%)")

# 验证2: 边类型分布
link_types = {}
for l in links:
    lt = l.get("type", l.get("label", "unknown"))
    link_types[lt] = link_types.get(lt, 0) + 1
print(f"边类型分布: {link_types}")
unknown_pct = link_types.get("unknown", 0) / max(len(links),1) * 100
print(f"unknown边占比: {unknown_pct}% (目标<10%)")

# 验证3: 检索命中率 - 搜索"安全"
security_nodes = [n for n in nodes if "安全" in (n.get("label","")+n.get("description","")).lower() or "security" in (n.get("label","")+n.get("description","")).lower()]
print(f"'安全'搜索结果: {len(security_nodes)} nodes (目标>0)")

# 验证4: 跨类型边数量
cross_type_links = []
for l in links:
    s_id = l.get("source","")
    t_id = l.get("target","")
    s_node = next((n for n in nodes if n.get("id")==s_id), None)
    t_node = next((n for n in nodes if n.get("id")==t_id), None)
    if s_node and t_node:
        s_type = s_node.get("entry_type", s_node.get("category",""))
        t_type = t_node.get("entry_type", t_node.get("category",""))
        if s_type != t_type and s_type not in ["center","primary","secondary","skill_category"] and t_type not in ["center","primary","secondary","skill_category"]:
            cross_type_links.append(l)
print(f"跨类型mentions边: {len(cross_type_links)}")

store.close()
print("\n✅ 验证完成")