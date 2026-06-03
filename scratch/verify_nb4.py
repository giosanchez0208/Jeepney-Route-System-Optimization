import json
nb = json.load(open('results_and_discussion_4_fixed.ipynb'))
print(f"Cells: {len(nb['cells'])}")
for i, c in enumerate(nb['cells']):
    src = c['source'][0][:70].strip() if c['source'] else '(empty)'
    print(f"  [{i}] {c['cell_type']:8s} | {src}")
