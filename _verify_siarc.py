"""Verify all 17 SIARC fixes are applied."""
import ast

with open("siarc.py", "r", encoding="utf-8") as f:
    source = f.read()

checks = []

# 1. sys.path.insert module-level once
checks.append(("sys.path module-level", "if str(WORKSPACE) not in sys.path:" in source))

# 2. F->A feedback: preselected from prior cycle
checks.append(("A: F->A feedback loop", 'preselected = input_data.get("selected_gap")' in source))

# 3. B: __new__ bypass safety with hasattr loop
checks.append(("B: hasattr safety loop", "if not hasattr(agent, attr):" in source))

# 4. B: Emits numeric_lhs, numeric_rhs, target_value
checks.append(("B: emits numeric_lhs/rhs", '"numeric_lhs": getattr(hyp, "numeric_lhs", None)' in source))
checks.append(("B: emits target_value", '"target_value": getattr(hyp, "target_value", None)' in source))

# 5. C: verify_numeric reads from hypothesis (not pi==pi)
checks.append(("C: verify_numeric from hyp", 'lhs = hyp_data.get("numeric_lhs")' in source))

# 6. C: pslq_search reads target_value
checks.append(("C: pslq reads target_value", 'target_val_expr = hyp_data.get("target_value")' in source))

# 7. C: Sandbox remaining budget
checks.append(("C: sandbox budget cap", "min(300, remaining)" in source))

# 8. C: _HYP_FIELDS filter
checks.append(("C+D: _HYP_FIELDS filter", "_HYP_FIELDS" in source))

# 9. D: evaluation_obj (not 'evaluation in dir()')
checks.append(("D: evaluation_obj rename", "evaluation_obj" in source))
checks.append(("D: no in dir() bug", "'evaluation' in dir()" not in source))

# 10. D: Kill floor tunable
checks.append(("D: effective_kill_floor", "effective_kill_floor" in source))

# 11. E: full KB scan
checks.append(("E: full KB scan", "for disc in discoveries:  # full scan" in source))

# 12. E: keyword-similarity fallback
checks.append(("E: keyword analogy fallback", "domain_keywords" in source))

# 13. Chain: seed preserved across cycles
checks.append(("Chain: seed re-inject", 'result["seed"] = input_data.get("seed")' in source))

# 14. save_output: SIARC_ROOT_MIRROR
checks.append(("save_output: ROOT_MIRROR guard", "SIARC_ROOT_MIRROR" in source))

# 15. stream_progress: flush=True
checks.append(("stream_progress: flush", "flush=True" in source))

passed = sum(1 for _, ok in checks if ok)
total = len(checks)
for name, ok in checks:
    sym = "PASS" if ok else "FAIL"
    print(f"  [{sym}] {name}")
print(f"\n{passed}/{total} checks pass.")

# Syntax check
try:
    ast.parse(source)
    print("Syntax: OK")
except SyntaxError as e:
    print(f"Syntax ERROR: {e}")
