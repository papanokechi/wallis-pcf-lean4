import json, os

with open('gcf_borel_verification.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
code = [c for c in nb['cells'] if c['cell_type'] == 'code']
md = [c for c in nb['cells'] if c['cell_type'] == 'markdown']
total = len(nb['cells'])
print(f'Notebook: {total} cells ({len(code)} code, {len(md)} md)')

with open('_cell_outputs_v2.json', encoding='utf-8') as f:
    outputs = json.load(f)
print(f'Output JSON: {len(outputs)} entries')
missing = [f'cell_{i}' for i in range(31) if f'cell_{i}' not in outputs]
if missing:
    print(f'  MISSING: {missing}')
else:
    print(f'  All 31 cells have outputs')

sz = os.path.getsize('gcf-borel-peer-review.html')
print(f'HTML v6: {sz/1024:.0f} KB')
print(f'Lean 4: {os.path.getsize("GCF_Borel_Lean4.lean")/1024:.1f} KB')

if os.path.exists('V_quad_export_bundle.txt'):
    print(f'Export bundle: {os.path.getsize("V_quad_export_bundle.txt")/1024:.1f} KB')
else:
    print('Export bundle: NOT FOUND')

print(f'v4.6 summary: {os.path.getsize("ramanujan-agent-v46-summary.html")/1024:.0f} KB')
