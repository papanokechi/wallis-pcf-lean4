"""
Focused PCF discovery sweep — smaller budgets for faster results.
Targets the most productive search configurations.
"""
import sys, time, json, random
sys.path.insert(0, '.')
random.seed(2026)

from ramanujan_breakthrough_generator import (
    PCFEngine, MITMSearch, DescentRepelSearch, CMFSearch,
    CONSTANTS, build_conjecture, poly_to_str
)
import mpmath

PRECISION = 60
DEPTH = 300

engine = PCFEngine(precision=PRECISION)
mpmath.mp.dps = PRECISION + 30

all_hits = {}
total_t0 = time.time()

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f"  [{ts}] {msg}", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: MITM — focused on productive parameter ranges
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72, flush=True)
print("  PHASE 1: MITM-RF Sweep", flush=True)
print("="*72, flush=True)

mitm = MITMSearch(engine)

mitm_configs = [
    # (target, deg_alpha, deg_beta, coeff_range, budget)
    ("pi",          2, 1, 5, 3000),
    ("pi",          2, 2, 3, 3000),
    ("pi",          3, 1, 3, 3000),
    ("e",           2, 1, 5, 3000),
    ("e",           2, 2, 3, 3000),
    ("zeta3",       2, 1, 5, 3000),
    ("zeta3",       2, 2, 3, 3000),
    ("catalan",     2, 1, 5, 3000),
    ("ln2",         2, 1, 5, 3000),
    ("ln2",         2, 2, 3, 3000),
    ("sqrt2",       2, 1, 5, 3000),
    ("phi",         2, 1, 5, 3000),
    ("euler_gamma", 2, 1, 5, 3000),
]

for target, da, db, cr, budget in mitm_configs:
    label = f"{CONSTANTS[target][0]:12s} deg=({da},{db}) c[-{cr},{cr}]"
    t0 = time.time()
    hits = mitm.run(target, da, db, cr, budget, DEPTH, log_fn=None)
    dt = time.time() - t0
    key = f"mitm_{target}_d{da}{db}_c{cr}"
    all_hits[key] = hits
    n = len(hits)
    sym = "✓" if n > 0 else "·"
    print(f"  {sym} {label:40s} → {n:2d} hits  ({dt:.1f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: CMF Navigator
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72, flush=True)
print("  PHASE 2: CMF Navigator", flush=True)
print("="*72, flush=True)

cmf = CMFSearch(engine)

cmf_configs = [
    ("pi",      2, 2, 8),
    ("pi",      3, 2, 5),
    ("e",       2, 2, 8),
    ("e",       3, 2, 5),
    ("zeta3",   3, 2, 5),
    ("catalan", 2, 2, 8),
    ("ln2",     2, 2, 8),
    ("sqrt2",   2, 2, 8),
    ("phi",     2, 2, 8),
    ("euler_gamma", 2, 2, 8),
]

for target, da, db, cr in cmf_configs:
    label = f"{CONSTANTS[target][0]:12s} deg=({da},{db}) c[-{cr},{cr}]"
    t0 = time.time()
    hits = cmf.run(target, da, db, cr, 500, DEPTH, log_fn=None)
    dt = time.time() - t0
    key = f"cmf_{target}_d{da}{db}_c{cr}"
    all_hits[key] = hits
    n = len(hits)
    sym = "✓" if n > 0 else "·"
    print(f"  {sym} {label:40s} → {n:2d} hits  ({dt:.1f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: Descent & Repel — fast sweeps
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72, flush=True)
print("  PHASE 3: Descent & Repel", flush=True)
print("="*72, flush=True)

dr = DescentRepelSearch(engine)

dr_configs = [
    ("pi",      2, 1, 8,  300),
    ("e",       2, 1, 8,  300),
    ("ln2",     2, 1, 8,  300),
    ("sqrt2",   2, 1, 8,  300),
    ("phi",     2, 1, 8,  300),
    ("zeta3",   2, 2, 8,  300),
    ("catalan", 2, 2, 8,  300),
]

for target, da, db, cr, budget in dr_configs:
    label = f"{CONSTANTS[target][0]:12s} deg=({da},{db}) c[-{cr},{cr}]"
    t0 = time.time()
    hits = dr.run(target, da, db, cr, budget, DEPTH, log_fn=None)
    dt = time.time() - t0
    key = f"dr_{target}_d{da}{db}_c{cr}"
    all_hits[key] = hits
    n = len(hits)
    sym = "✓" if n > 0 else "·"
    print(f"  {sym} {label:40s} → {n:2d} hits  ({dt:.1f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSOLIDATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72, flush=True)
print("  CONSOLIDATION", flush=True)
print("="*72, flush=True)

raw_hits = []
for key, hits in all_hits.items():
    parts = key.split("_")
    algo = parts[0]
    target = parts[1]
    for ac, bc, d in hits:
        raw_hits.append((target, algo, key, ac, bc, d))

print(f"  Raw hits: {len(raw_hits)}", flush=True)

# Deduplicate
seen = {}
for target, algo, key, ac, bc, d in raw_hits:
    canon = (target, tuple(ac), tuple(bc))
    canon_neg = (target, tuple(-c for c in ac), tuple(-c for c in bc))
    if canon in seen:
        if d > seen[canon][4]:
            seen[canon] = (target, algo, key, ac, bc, d)
    elif canon_neg in seen:
        if d > seen[canon_neg][4]:
            seen[canon_neg] = (target, algo, key, ac, bc, d)
    else:
        seen[canon] = (target, algo, key, ac, bc, d)

unique = list(seen.values())
print(f"  Unique PCFs: {len(unique)}", flush=True)

# Deep verify
verified = []
for target, algo, key, ac, bc, low_digits in unique:
    val, err, convs = engine.evaluate_pcf(ac, bc, DEPTH)
    if val is None:
        continue
    matched, formula, high_digits = engine.match_known_constant(val, target, PRECISION)
    fac_red = engine.check_factorial_reduction(ac, bc)
    conv_type = engine.measure_convergence(ac, bc)

    a_str = poly_to_str(ac)
    b_str = poly_to_str(bc)
    const_name = CONSTANTS[target][0]

    if high_digits >= 20:
        verified.append({
            "target": target,
            "constant": const_name,
            "alpha_coeffs": ac,
            "beta_coeffs": bc,
            "alpha_str": a_str,
            "beta_str": b_str,
            "formula_match": formula,
            "digits": high_digits,
            "convergence": conv_type,
            "factorial_reduction": fac_red,
            "algorithm": algo,
            "numerical_value": str(val)[:60],
        })

verified.sort(key=lambda x: -x["digits"])

total_time = time.time() - total_t0

# ═══════════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72, flush=True)
print(f"  DISCOVERY REPORT  ({len(verified)} verified PCFs)", flush=True)
print("="*72, flush=True)
print(f"  Total time: {total_time:.1f}s", flush=True)
print(f"  Constants: {len(CONSTANTS)}", flush=True)
print(f"  Unique evaluated: {len(unique)}", flush=True)
print(f"  Verified ≥20dp: {len(verified)}", flush=True)

by_const = {}
for v in verified:
    by_const.setdefault(v["constant"], []).append(v)

for const, items in sorted(by_const.items()):
    print(f"\n  ── {const} ──", flush=True)
    for i, v in enumerate(items, 1):
        fr = " ✦FR" if v["factorial_reduction"] else ""
        print(f"    {i}. value ≈ {v['formula_match']:25s}  {v['digits']:3d}dp  {v['convergence']:15s}{fr}", flush=True)
        print(f"       α(n) = {v['alpha_str']},  β(n) = {v['beta_str']}", flush=True)
        print(f"       α={v['alpha_coeffs']}  β={v['beta_coeffs']}", flush=True)

report = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "precision": PRECISION,
    "depth": DEPTH,
    "total_time_s": round(total_time, 1),
    "verified_count": len(verified),
    "discoveries": verified,
}
with open("discovery_sweep_results.json", "w") as f:
    json.dump(report, f, indent=2)
print(f"\n  Results → discovery_sweep_results.json", flush=True)
