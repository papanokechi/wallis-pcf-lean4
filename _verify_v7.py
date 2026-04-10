import json, os

with open('gcf_borel_verification.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
code = [c for c in nb['cells'] if c['cell_type'] == 'code']
md = [c for c in nb['cells'] if c['cell_type'] == 'markdown']
total = len(nb['cells'])
print(f"Notebook: {total} cells ({len(code)} code, {len(md)} md)")

with open('_cell_outputs_v2.json', encoding='utf-8') as f:
    outputs = json.load(f)
print(f"Output JSON: {len(outputs)} entries")
missing = [f'cell_{i}' for i in range(35) if f'cell_{i}' not in outputs]
if missing:
    print(f"  MISSING: {missing}")
else:
    print(f"  All 35 cells have outputs")

with open('gcf-borel-peer-review.html', encoding='utf-8') as f:
    html = f.read()

checks = {
    'v7': 'Peer Review Document v7' in html,
    '35cells': '35 code cells' in html,
    'sec32': 'sec-32' in html,
    'sec33': 'sec-33' in html,
    'sec34': 'sec-34' in html,
    'sec35': 'sec-35' in html,
    'WKB': 'WKB Derivation' in html or 'Convergence Exponent' in html,
    'PCF': 'Parabolic Cylinder' in html,
    'Mahler': 'Mahler Measure' in html,
    '1449': '1449' in html or '1,449' in html,
    'no_v6': html.count('Document v6') == 0,
    'lean4': 'GCF_Borel_Lean4' in html,
}
for k,v in checks.items():
    tag = 'OK' if v else 'FAIL'
    print(f"  [{tag}] {k}")
print(f"Passed: {sum(checks.values())}/{len(checks)}")
print()
print(f"HTML v7: {os.path.getsize('gcf-borel-peer-review.html')/1024:.0f} KB")
print(f"Lean 4: {os.path.getsize('GCF_Borel_Lean4.lean')/1024:.1f} KB")
