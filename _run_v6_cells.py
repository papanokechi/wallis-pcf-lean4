"""Run ONLY the 5 new code cells (§27-31) = code indices 26-30."""
import json, sys, io, traceback, time
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

def forward_recurrence(a_func, b_func, N):
    P_prev, P_curr = mp.mpf(1), mp.mpf(b_func(0))
    Q_prev, Q_curr = mp.mpf(0), mp.mpf(1)
    for n in range(1, N+1):
        a_n = mp.mpf(a_func(n))
        b_n = mp.mpf(b_func(n))
        P_prev, P_curr = P_curr, b_n * P_curr + a_n * P_prev
        Q_prev, Q_curr = Q_curr, b_n * Q_curr + a_n * Q_prev
    return P_curr, Q_curr

# Load notebook
with open('gcf_borel_verification.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

code_cells = [(i, c) for i, c in enumerate(nb['cells']) if c['cell_type'] == 'code']
print(f"Total code cells: {len(code_cells)}")

# Load existing outputs
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
    'forward_recurrence': forward_recurrence,
    'json': json, 'sys': sys, 'io': io, 'traceback': traceback,
    'time': time,
    '__builtins__': __builtins__,
}

# Run cells 26-30 (§27-31)
for idx in range(26, min(31, len(code_cells))):
    cell_idx, cell = code_cells[idx]
    src = ''.join(cell['source'])
    print(f"\n{'='*70}")
    print(f"  RUNNING Code cell {idx} (notebook cell {cell_idx+1}): §{idx+1}")
    print(f"{'='*70}")
    
    t0 = time.time()
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured
    
    try:
        exec(compile(src, f'cell_{idx}', 'exec'), ns)
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout = old_stdout
    
    elapsed = time.time() - t0
    out = captured.getvalue()
    outputs[f"cell_{idx}"] = out
    if out.strip():
        lines = out.rstrip().split('\n')
        for line in lines[:150]:
            print(line)
        if len(lines) > 150:
            print(f"  ... ({len(lines)-150} more lines)")
    else:
        print("  (no output)")
    print(f"\n  [Elapsed: {elapsed:.1f}s]")

with open('_cell_outputs_v2.json', 'w', encoding='utf-8') as f:
    json.dump(outputs, f, indent=2)

print(f"\n\nDone. Updated outputs for cells 26-30 in _cell_outputs_v2.json")
print(f"Keys now present: {sorted(outputs.keys())}")
