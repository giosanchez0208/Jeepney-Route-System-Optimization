import json
nb = json.load(open('results_and_discussion.ipynb', encoding='utf-8'))
with open('scratch/nb_errors.txt', 'w', encoding='utf-8') as f:
    for i, c in enumerate(nb['cells']):
        if c.get('cell_type') == 'code' and 'build_ddm' in ''.join(c.get('source', [])):
            for o in c.get('outputs', []):
                if o.get('output_type') == 'error':
                    f.write(f'Error in cell {i}: {o["ename"]} - {o["evalue"]}\n')
                    for tb in o.get('traceback', []):
                        f.write(f'  {tb}\n')
