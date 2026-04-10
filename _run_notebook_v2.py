"""Execute all code cells from the notebook sequentially, capture outputs."""
import json, sys, io, traceback
import matplotlib
matplotlib.use('Agg')

with open('gcf_borel_verification.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

code_cells = [(i, c) for i, c in enumerate(nb['cells']) if c['cell_type'] == 'code']
print(f"Running {len(code_cells)} code cells...")

ns = {}
outputs = {}

for idx, (cell_idx, cell) in enumerate(code_cells):
    src = ''.join(cell['source'])
    print(f"\n{'='*60}")
    print(f"  Code cell {idx} (notebook cell {cell_idx+1})")
    print(f"{'='*60}")
    
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
        # Print first 80 lines max to keep terminal manageable
        lines = out.rstrip().split('\n')
        for line in lines[:80]:
            print(line)
        if len(lines) > 80:
            print(f"  ... ({len(lines)-80} more lines)")
    else:
        print("  (no output)")

with open('_cell_outputs_v2.json', 'w', encoding='utf-8') as f:
    json.dump(outputs, f, indent=2)

print(f"\n\nDone. Saved outputs for {len(outputs)} cells to _cell_outputs_v2.json")
