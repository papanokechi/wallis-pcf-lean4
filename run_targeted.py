"""
Targeted PCF discovery — only fast, productive configurations.
Focus: deg(2,1) and deg(3,1) with small coeff ranges across all 8 constants.
"""
import sys, time, json, random
sys.path.insert(0, '.')
random.seed(42)

from ramanujan_breakthrough_generator import (
    PCFEngine, MITMSearch, CMFSearch, CONSTANTS, poly_to_str
)
import mpmath

PRECISION = 60
DEPTH = 200  # faster than 300
engine = PCFEngine(precision=PRECISION)
mpmath.mp.dps = PRECISION + 30
mitm = MITMSearch(engine)
cmf = CMFSearch(engine)

results = []
seen = set()

def add_hit(target, algo, ac, bc):
    key = (target, tuple(ac), tuple(bc))
    nk = (target, tuple(-c for c in ac), tuple(-c for c in bc))
    if key in seen or nk in seen:
        return
    seen.add(key)
    val, err, _ = engine.evaluate_pcf(ac, bc, DEPTH)
    if val is None: return
    matched, formula, digits = engine.match_known_constant(val, target, PRECISION)
    if digits < 15: return
    fac = engine.check_factorial_reduction(ac, bc)
    conv = engine.measure_convergence(ac, bc)
    results.append({
        "target": target, "constant": CONSTANTS[target][0],
        "alpha_coeffs": ac, "beta_coeffs": bc,
        "alpha_str": poly_to_str(ac), "beta_str": poly_to_str(bc),
        "formula": formula, "digits": digits,
        "convergence": conv, "factorial_reduction": fac,
        "algo": algo, "value": str(val)[:50],
    })
    with open("pcf_discoveries.json", "w", encoding="utf-8") as f:
        json.dump({"count": len(results), "discoveries": results}, f, indent=2, ensure_ascii=False)

t0 = time.time()

# Fast productive configs: deg(2,1) linear beta
targets = ["pi", "e", "zeta3", "ln2", "catalan", "sqrt2", "phi", "euler_gamma"]

print("── MITM deg(2,1) coeff[-3,3] budget=3000 ──", flush=True)
for tgt in targets:
    t1 = time.time()
    hits = mitm.run(tgt, 2, 1, 3, 3000, DEPTH)
    for ac, bc, d in hits:
        add_hit(tgt, "mitm_d21", ac, bc)
    dt = time.time() - t1
    sym = "+" if hits else " "
    print(f"  {sym} {CONSTANTS[tgt][0]:6s} → {len(hits):2d} hits  {dt:5.1f}s  [total={len(results)}]", flush=True)

print("\n── MITM deg(2,1) coeff[-5,5] budget=3000 ──", flush=True)
for tgt in targets:
    t1 = time.time()
    hits = mitm.run(tgt, 2, 1, 5, 3000, DEPTH)
    for ac, bc, d in hits:
        add_hit(tgt, "mitm_d21_c5", ac, bc)
    dt = time.time() - t1
    sym = "+" if hits else " "
    print(f"  {sym} {CONSTANTS[tgt][0]:6s} → {len(hits):2d} hits  {dt:5.1f}s  [total={len(results)}]", flush=True)

print("\n── MITM deg(3,1) coeff[-3,3] budget=3000 ──", flush=True)
for tgt in ["pi", "e", "zeta3", "ln2"]:
    t1 = time.time()
    hits = mitm.run(tgt, 3, 1, 3, 3000, DEPTH)
    for ac, bc, d in hits:
        add_hit(tgt, "mitm_d31", ac, bc)
    dt = time.time() - t1
    sym = "+" if hits else " "
    print(f"  {sym} {CONSTANTS[tgt][0]:6s} → {len(hits):2d} hits  {dt:5.1f}s  [total={len(results)}]", flush=True)

print("\n── CMF seeded search ──", flush=True)
for tgt in ["pi", "e", "zeta3", "catalan"]:
    t1 = time.time()
    hits = cmf.run(tgt, 2, 2, 8, 500, DEPTH)
    for ac, bc, d in hits:
        add_hit(tgt, "cmf", ac, bc)
    dt = time.time() - t1
    sym = "+" if hits else " "
    print(f"  {sym} {CONSTANTS[tgt][0]:6s} → {len(hits):2d} hits  {dt:5.1f}s  [total={len(results)}]", flush=True)

total = time.time() - t0
print(f"\n{'='*60}", flush=True)
print(f"Done in {total:.0f}s — {len(results)} unique verified discoveries", flush=True)
print(f"{'='*60}", flush=True)

by_c = {}
for r in results:
    by_c.setdefault(r["constant"], []).append(r)
for c, items in sorted(by_c.items()):
    print(f"\n  {c}:", flush=True)
    for v in sorted(items, key=lambda x: -x["digits"]):
        fr = " ✦FR" if v["factorial_reduction"] else ""
        print(f"    {v['formula']:28s}  {v['digits']:3d}dp  {v['convergence']}{fr}", flush=True)
        print(f"       a(n)={v['alpha_str']}, b(n)={v['beta_str']}", flush=True)

print(f"\nSaved → pcf_discoveries.json", flush=True)
