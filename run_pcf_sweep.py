"""
Incremental PCF sweep — writes each result to JSON as found.
"""
import sys, time, json, random
sys.path.insert(0, '.')
random.seed(2026)

from ramanujan_breakthrough_generator import (
    PCFEngine, MITMSearch, CMFSearch, CONSTANTS, poly_to_str
)
import mpmath

PRECISION = 60
DEPTH = 300
engine = PCFEngine(precision=PRECISION)
mpmath.mp.dps = PRECISION + 30
mitm = MITMSearch(engine)
cmf = CMFSearch(engine)

results = []
seen = set()

def verify_and_add(target, algo, ac, bc):
    key = (target, tuple(ac), tuple(bc))
    negkey = (target, tuple(-c for c in ac), tuple(-c for c in bc))
    if key in seen or negkey in seen:
        return
    seen.add(key)
    val, err, _ = engine.evaluate_pcf(ac, bc, DEPTH)
    if val is None: return
    matched, formula, digits = engine.match_known_constant(val, target, PRECISION)
    if digits < 15: return
    fac = engine.check_factorial_reduction(ac, bc)
    conv = engine.measure_convergence(ac, bc)
    r = {
        "target": target, "constant": CONSTANTS[target][0],
        "alpha_coeffs": ac, "beta_coeffs": bc,
        "alpha_str": poly_to_str(ac), "beta_str": poly_to_str(bc),
        "formula": formula, "digits": digits,
        "convergence": conv, "factorial_reduction": fac,
        "algo": algo, "value": str(val)[:50],
    }
    results.append(r)
    # Incremental save
    with open("pcf_discoveries.json", "w", encoding="utf-8") as f:
        json.dump({"count": len(results), "discoveries": results}, f, indent=2, ensure_ascii=False)

def run_mitm(target, da, db, cr, budget):
    hits = mitm.run(target, da, db, cr, budget, DEPTH)
    for ac, bc, d in hits:
        verify_and_add(target, f"mitm_d{da}{db}_c{cr}", ac, bc)
    return len(hits)

def run_cmf(target, da, db, cr):
    hits = cmf.run(target, da, db, cr, 500, DEPTH)
    for ac, bc, d in hits:
        verify_and_add(target, f"cmf_d{da}{db}_c{cr}", ac, bc)
    return len(hits)

t0 = time.time()

# Run all configs and print one-line summaries
configs = [
    # MITM runs
    ("mitm", "pi",      2, 1, 3, 5000),
    ("mitm", "pi",      2, 2, 3, 5000),
    ("mitm", "pi",      3, 1, 3, 5000),
    ("mitm", "e",       2, 1, 5, 5000),
    ("mitm", "e",       2, 2, 3, 5000),
    ("mitm", "e",       3, 1, 3, 5000),
    ("mitm", "zeta3",   2, 1, 5, 5000),
    ("mitm", "zeta3",   2, 2, 3, 5000),
    ("mitm", "ln2",     2, 1, 5, 5000),
    ("mitm", "ln2",     2, 2, 3, 5000),
    ("mitm", "catalan", 2, 1, 5, 3000),
    ("mitm", "sqrt2",   2, 1, 5, 3000),
    ("mitm", "phi",     2, 1, 5, 3000),
    ("mitm", "euler_gamma", 2, 1, 5, 3000),
    # CMF runs
    ("cmf",  "pi",      2, 2, 8, 0),
    ("cmf",  "e",       2, 2, 8, 0),
    ("cmf",  "zeta3",   3, 2, 5, 0),
    ("cmf",  "catalan", 2, 2, 8, 0),
]

print(f"Running {len(configs)} search configurations...", flush=True)
for cfg in configs:
    mode = cfg[0]
    target, da, db, cr = cfg[1], cfg[2], cfg[3], cfg[4]
    budget = cfg[5] if len(cfg) > 5 else 0
    t1 = time.time()
    if mode == "mitm":
        n = run_mitm(target, da, db, cr, budget)
    else:
        n = run_cmf(target, da, db, cr)
    dt = time.time() - t1
    sym = "+" if n > 0 else " "
    cname = CONSTANTS[target][0]
    print(f"  {sym} {mode:4s} {cname:6s} d({da},{db}) c{cr} → {n:2d} hits  {dt:5.1f}s  [total: {len(results)}]", flush=True)

# Final summary
print(f"\nDone in {time.time()-t0:.0f}s — {len(results)} unique verified PCFs", flush=True)
print(f"Saved → pcf_discoveries.json\n", flush=True)

# Print discoveries grouped by constant
by_c = {}
for r in results:
    by_c.setdefault(r["constant"], []).append(r)
for c, items in sorted(by_c.items()):
    print(f"  {c}:", flush=True)
    for v in sorted(items, key=lambda x: -x["digits"]):
        fr = " FR" if v["factorial_reduction"] else ""
        print(f"    {v['formula']:28s}  {v['digits']:3d}dp  {v['convergence']:15s}{fr}  α={v['alpha_str']}  β={v['beta_str']}", flush=True)
