import json
with open('gcf_borel_verification.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
code_cells = [(i,c) for i,c in enumerate(nb['cells']) if c['cell_type'] == 'code']
total = len(nb['cells'])
print(f"Total: {total} cells ({len(code_cells)} code)")
for idx in range(max(0,len(code_cells)-6), len(code_cells)):
    ci, cell = code_cells[idx]
    src = ''.join(cell['source'])
    first = src.split('\n')[0]
    print(f"  code[{idx}] (nb[{ci}]): {first[:80]}")
