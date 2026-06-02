import json
with open('results_and_discussion.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)
for i, c in enumerate(nb.get('cells', [])):
    if c['cell_type'] == 'code':
        source = "".join(c.get('source', []))
        print(f"[{i:02d}] {c['cell_type'].upper()}:\n{source}\n---\n")
