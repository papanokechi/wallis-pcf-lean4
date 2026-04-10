"""Run ONLY the 4 new code cells (§23-26) with minimal setup."""
import json, sys, io, traceback
import matplotlib
matplotlib.use('Agg')
import mpmath as mp
import numpy as np

mp.mp.dps = 80

def hp(val, digits=50):
    return mp.nstr(val, digits, strip_zeros=False)

def gcf_limit(a_func, b_func, depth=200, b0=None):
    t = mp.mpf(0)
    for n in range(depth, 0, -1):
        a = mp.mpf(a_func(n))
        b = mp.mpf(b_func(n))
        t = a / (b + t)
    if b0 is not None:
        return mp.mpf(b0) + t
    return t

def a_one(n):
    return mp.mpf(1)

def b_quadratic(n):
    return 3 * n**2 + n + 1

def b_linear(n):
    return 3 * n + 1

# Load notebook and find code cells 22-25 (the new §23-26)
with open('gcf_borel_verification.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

code_cells = [(i, c) for i, c in enumerate(nb['cells']) if c['cell_type'] == 'code']
print(f"Total code cells: {len(code_cells)}")

# Also load existing outputs
try:
    with open('_cell_outputs_v2.json', encoding='utf-8') as f:
        outputs = json.load(f)
except:
    outputs = {}

# Shared namespace
ns = {
    'mp': mp, 'np': np, 'hp': hp,
    'gcf_limit': gcf_limit, 'a_one': a_one,
    'b_quadratic': b_quadratic, 'b_linear': b_linear,
}

# Run cells 22-25 (indices 22, 23, 24, 25 in code_cells)
for idx in range(22, min(26, len(code_cells))):
    if idx == 22 or idx == 24:
        continue  # §23 and §25 already ran fine
    cell_idx, cell = code_cells[idx]
    src = ''.join(cell['source'])
    print(f"\n{'='*70}")
    print(f"  RUNNING Code cell {idx} (notebook cell {cell_idx+1}): §{idx+1}")
    print(f"{'='*70}")
    
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured
    
    try:
        exec(compile(src, f'cell_{idx}', 'exec'), ns)
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout = old_stdout
    
    out = captured.getvalue()
    outputs[f"cell_{idx}"] = out
    if out.strip():
        lines = out.rstrip().split('\n')
        for line in lines[:120]:
            print(line)
        if len(lines) > 120:
            print(f"  ... ({len(lines)-120} more lines)")
    else:
        print("  (no output)")

with open('_cell_outputs_v2.json', 'w', encoding='utf-8') as f:
    json.dump(outputs, f, indent=2)

print(f"\n\nDone. Updated outputs for cells 22-25 in _cell_outputs_v2.json")
