import json, sys
sys.path.insert(0, '.')
from selfmind_app.parser import build_graph
from selfmind_app.config import load_config
config = load_config()
data = build_graph(config)

from collections import Counter
cats = Counter(n['category'] for n in data['nodes'])
print('=== Node categories ===')
for c, cnt in cats.most_common():
    print(f'  {c}: {cnt}')
print(f'Total nodes: {len(data["nodes"])}')
print(f'Total links: {len(data["links"])}')

prims = Counter(n.get('primary','') for n in data['nodes'] if n.get('primary'))
print()
print('=== Primary categories ===')
for p, cnt in prims.most_common():
    print(f'  {p}: {cnt}')

seen = set()
print()
print('=== Sample nodes ===')
for n in data['nodes']:
    cat = n['category']
    if cat not in seen:
        seen.add(cat)
        print(f'  [{cat}] id={n["id"]}, label={n["label"]}, primary={n.get("primary","")}, secondary={n.get("secondary","")}')
