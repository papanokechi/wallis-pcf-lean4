"""
Comprehensive PCF discovery sweep across all 8 constants.
Runs MITM, CMF, and D&R with tuned parameters for each target.
Outputs a structured report of all discoveries.
"""
import sys, time, json, random
sys.path.insert(0, '.')
random.seed(42)

from ramanujan_breakthrough_generator import (
    PCFEngine, MITMSearch, DescentRepelSearch, CMFSearch,
    CONSTANTS, build_conjecture, poly_to_str
)
import mpmath

# ── Configuration ────────────────────────────────────────────────────────────
PRECISION = 80
MITM_BUDGET = 10000
DR_BUDGET = 600
DEPTH = 300

engine = PCFEngine(precision=PRECISION)
mpmath.mp.dps = PRECISION + 30

all_hits = {}
total_t0 = time.time()

def log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: MITM sweep — all constants, deg 1-3
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("  PHASE 1: MITM-RF Sweep  (all constants × degree combos)")
print("="*72)

mitm = MITMSearch(engine)

mitm_configs = [
    # (target, deg_alpha, deg_beta, coeff_range, budget)
    ("pi",          2, 1, 5, MITM_BUDGET),
    ("pi",          2, 2, 4, MITM_BUDGET),
    ("pi",          3, 2, 3, MITM_BUDGET),
    ("e",           2, 1, 5, MITM_BUDGET),
    ("e",           2, 2, 4, MITM_BUDGET),
    ("e",           3, 1, 3, MITM_BUDGET),
    ("zeta3",       2, 1, 5, MITM_BUDGET),
    ("zeta3",       2, 2, 4, MITM_BUDGET),
    ("zeta3",       3, 2, 3, MITM_BUDGET),
    ("catalan",     2, 1, 5, MITM_BUDGET),
    ("catalan",     2, 2, 4, MITM_BUDGET),
    ("ln2",         2, 1, 5, MITM_BUDGET),
    ("ln2",         2, 2, 4, MITM_BUDGET),
    ("sqrt2",       2, 1, 5, MITM_BUDGET),
    ("sqrt2",       2, 2, 4, MITM_BUDGET),
    ("phi",         2, 1, 5, MITM_BUDGET),
    ("phi",         2, 2, 4, MITM_BUDGET),
    ("euler_gamma", 2, 1, 5, MITM_BUDGET),
    ("euler_gamma", 2, 2, 4, MITM_BUDGET),
]

for target, da, db, cr, budget in mitm_configs:
    label = f"{CONSTANTS[target][0]:12s} deg=({da},{db}) coeff=[-{cr},{cr}]"
    t0 = time.time()
    hits = mitm.run(target, da, db, cr, budget, DEPTH, log_fn=None)
    dt = time.time() - t0
    key = f"mitm_{target}_d{da}{db}_c{cr}"
    all_hits[key] = hits
    n = len(hits)
    sym = "✓" if n > 0 else "·"
    print(f"  {sym} {label:45s} → {n:2d} hits  ({dt:.1f}s)")

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: CMF Navigator — seeded families
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("  PHASE 2: CMF Navigator  (seed family exploration)")
print("="*72)

cmf = CMFSearch(engine)

cmf_configs = [
    ("pi",      2, 2, 6),
    ("pi",      3, 2, 4),
    ("e",       2, 2, 6),
    ("e",       3, 2, 4),
    ("zeta3",   3, 2, 4),
    ("zeta3",   4, 3, 3),
    ("catalan", 2, 2, 6),
    ("catalan", 3, 2, 4),
]

for target, da, db, cr in cmf_configs:
    label = f"{CONSTANTS[target][0]:12s} deg=({da},{db}) coeff=[-{cr},{cr}]"
    t0 = time.time()
    hits = cmf.run(target, da, db, cr, 500, DEPTH, log_fn=None)
    dt = time.time() - t0
    key = f"cmf_{target}_d{da}{db}_c{cr}"
    all_hits[key] = hits
    n = len(hits)
    sym = "✓" if n > 0 else "·"
    print(f"  {sym} {label:45s} → {n:2d} hits  ({dt:.1f}s)")

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: Descent & Repel — targeted searches
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("  PHASE 3: Descent & Repel  (gradient descent on coefficient space)")
print("="*72)

dr = DescentRepelSearch(engine)

dr_configs = [
    ("pi",      2, 1, 10, DR_BUDGET),
    ("pi",      2, 2, 8,  DR_BUDGET),
    ("e",       2, 1, 10, DR_BUDGET),
    ("e",       2, 2, 8,  DR_BUDGET),
    ("ln2",     2, 1, 10, DR_BUDGET),
    ("ln2",     2, 2, 8,  DR_BUDGET),
    ("sqrt2",   2, 1, 10, DR_BUDGET),
    ("phi",     2, 1, 10, DR_BUDGET),
    ("zeta3",   2, 2, 10, DR_BUDGET),
    ("catalan", 2, 2, 10, DR_BUDGET),
]

for target, da, db, cr, budget in dr_configs:
    label = f"{CONSTANTS[target][0]:12s} deg=({da},{db}) coeff=[-{cr},{cr}]"
    t0 = time.time()
    hits = dr.run(target, da, db, cr, budget, DEPTH, log_fn=None)
    dt = time.time() - t0
    key = f"dr_{target}_d{da}{db}_c{cr}"
    all_hits[key] = hits
    n = len(hits)
    sym = "✓" if n > 0 else "·"
    print(f"  {sym} {label:45s} → {n:2d} hits  ({dt:.1f}s)")

# ═══════════════════════════════════════════════════════════════════════════════
# CONSOLIDATION: Deduplicate and build verified conjecture table
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("  CONSOLIDATION: Verifying unique discoveries at", PRECISION, "digits")
print("="*72)

# Collect all raw hits
raw_hits = []  # (target, algo_key, alpha_c, beta_c, digits)
for key, hits in all_hits.items():
    parts = key.split("_")
    algo = parts[0]
    target = parts[1]
    for ac, bc, d in hits:
        raw_hits.append((target, algo, key, ac, bc, d))

print(f"  Raw hits: {len(raw_hits)}")

# Deduplicate by (target, alpha_coeffs, beta_coeffs) — keep highest digits
seen = {}
for target, algo, key, ac, bc, d in raw_hits:
    canon = (target, tuple(ac), tuple(bc))
    # Also dedup sign-flipped: (-α, -β) converges to same value
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
print(f"  Unique PCFs: {len(unique)}")

# Deep verification at full precision
print(f"\n  Deep verification (depth={DEPTH}, {PRECISION} digits):\n")

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
        fr = "FR" if fac_red else "  "
        print(f"  ✓ {const_name:12s} ≈ {formula:25s}  {high_digits:3d}dp  {conv_type:15s} {fr}  α={a_str}  β={b_str}")

# Sort by digits descending
verified.sort(key=lambda x: -x["digits"])

total_time = time.time() - total_t0

# ═══════════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print(f"  DISCOVERY REPORT  ({len(verified)} verified PCFs)")
print("="*72)
print(f"  Total sweep time: {total_time:.1f}s")
print(f"  Constants probed: {len(CONSTANTS)}")
print(f"  Raw candidates evaluated: {sum(len(h) for h in all_hits.values())}")
print(f"  Unique after dedup: {len(unique)}")
print(f"  Verified ≥20 digits: {len(verified)}")

# Group by constant
by_const = {}
for v in verified:
    by_const.setdefault(v["constant"], []).append(v)

for const, items in sorted(by_const.items()):
    print(f"\n  {const}:")
    for i, v in enumerate(items, 1):
        fr = "✦ factorial reduction" if v["factorial_reduction"] else ""
        print(f"    {i}. {v['formula_match']:25s}  ({v['digits']}dp, {v['convergence']})  {fr}")
        print(f"       α(n) = {v['alpha_str']},  β(n) = {v['beta_str']}")

# Save full results
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
print(f"\n  Results saved → discovery_sweep_results.json")

# Also update the main registry
from ramanujan_breakthrough_generator import BreakthroughGenerator
gen = BreakthroughGenerator(precision=PRECISION)
for v in verified:
    conj = build_conjecture(
        v["alpha_coeffs"], v["beta_coeffs"], v["target"],
        v["algorithm"], engine
    )
    # Avoid duplicates
    existing = {(tuple(c.alpha_coeffs), tuple(c.beta_coeffs)) for c in gen.session.conjectures}
    if (tuple(v["alpha_coeffs"]), tuple(v["beta_coeffs"])) not in existing:
        gen.session.conjectures.append(conj)
gen._save_registry()
print(f"  Registry updated: {len(gen.session.conjectures)} total conjectures")
