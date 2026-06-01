import json
with open('results_and_discussion.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)
for i, c in enumerate(nb.get('cells', [])):
    source = "".join(c.get('source', []))
    preview = source.split('\n')[0] if source else ""
    print(f"[{i:02d}] {c['cell_type'].upper()}: {preview}")
