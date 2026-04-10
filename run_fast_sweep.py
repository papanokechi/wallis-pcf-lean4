"""
Direct PCF discovery runs — writes results to file from Python.
Smaller, faster experiments to get real insights.
"""
import sys, time, json, random, io
sys.path.insert(0, '.')
random.seed(2026)

from ramanujan_breakthrough_generator import (
    PCFEngine, MITMSearch, DescentRepelSearch, CMFSearch,
    CONSTANTS, poly_to_str
)
import mpmath

# Output to both console and file
outfile = open("discovery_log.txt", "w", encoding="utf-8")
def out(msg=""):
    print(msg, flush=True)
    outfile.write(msg + "\n")

PRECISION = 60
DEPTH = 300
engine = PCFEngine(precision=PRECISION)
mpmath.mp.dps = PRECISION + 30

all_verified = []

def verify_hit(target, algo, ac, bc):
    """Deep verify a hit and return dict or None."""
    val, err, _ = engine.evaluate_pcf(ac, bc, DEPTH)
    if val is None:
        return None
    matched, formula, digits = engine.match_known_constant(val, target, PRECISION)
    if digits < 15:
        return None
    fac = engine.check_factorial_reduction(ac, bc)
    conv = engine.measure_convergence(ac, bc)
    return {
        "target": target,
        "constant": CONSTANTS[target][0],
        "alpha_coeffs": ac,
        "beta_coeffs": bc,
        "alpha_str": poly_to_str(ac),
        "beta_str": poly_to_str(bc),
        "formula_match": formula,
        "digits": digits,
        "convergence": conv,
        "factorial_reduction": fac,
        "algorithm": algo,
        "value": str(val)[:60],
    }

t_total = time.time()

# ═══════════════════════════════════════════════════════════════════════
# RUN 1: MITM - π (small coeff space, exhaustive)
# ═══════════════════════════════════════════════════════════════════════
out("="*70)
out("RUN 1: MITM → π  deg(2,1) coeff[-3,3] budget=5000")
out("="*70)
t0 = time.time()
mitm = MITMSearch(engine)
hits = mitm.run("pi", 2, 1, 3, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("pi", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 2: MITM - π (quadratic both, wider)
# ═══════════════════════════════════════════════════════════════════════
out("\n" + "="*70)
out("RUN 2: MITM → π  deg(2,2) coeff[-3,3] budget=5000")
out("="*70)
t0 = time.time()
hits = mitm.run("pi", 2, 2, 3, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("pi", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 3: MITM - e
# ═══════════════════════════════════════════════════════════════════════
out("\n" + "="*70)
out("RUN 3: MITM → e  deg(2,1) coeff[-5,5] budget=5000")
out("="*70)
t0 = time.time()
hits = mitm.run("e", 2, 1, 5, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("e", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 4: MITM - e (quadratic both)
# ═══════════════════════════════════════════════════════════════════════
out("\n" + "="*70)
out("RUN 4: MITM → e  deg(2,2) coeff[-3,3] budget=5000")
out("="*70)
t0 = time.time()
hits = mitm.run("e", 2, 2, 3, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("e", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 5: MITM - ζ(3)
# ═══════════════════════════════════════════════════════════════════════
out("\n" + "="*70)
out("RUN 5: MITM → ζ(3)  deg(2,1) coeff[-5,5] budget=5000")
out("="*70)
t0 = time.time()
hits = mitm.run("zeta3", 2, 1, 5, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("zeta3", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 6: MITM - ln2
# ═══════════════════════════════════════════════════════════════════════
out("\n" + "="*70)
out("RUN 6: MITM → ln2  deg(2,1) coeff[-5,5] budget=5000")
out("="*70)
t0 = time.time()
hits = mitm.run("ln2", 2, 1, 5, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("ln2", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 7: MITM - sqrt2, phi, euler_gamma, catalan
# ═══════════════════════════════════════════════════════════════════════
for tgt in ["sqrt2", "phi", "euler_gamma", "catalan"]:
    out(f"\n{'='*70}")
    out(f"RUN: MITM → {CONSTANTS[tgt][0]}  deg(2,1) coeff[-5,5] budget=3000")
    out("="*70)
    t0 = time.time()
    hits = mitm.run(tgt, 2, 1, 5, 3000, DEPTH)
    out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
    for ac, bc, d in hits:
        v = verify_hit(tgt, "mitm", ac, bc)
        if v:
            all_verified.append(v)
            out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 8: CMF for all constants
# ═══════════════════════════════════════════════════════════════════════
cmf = CMFSearch(engine)
for tgt in ["pi", "e", "zeta3", "catalan"]:
    out(f"\n{'='*70}")
    out(f"RUN: CMF → {CONSTANTS[tgt][0]}  deg(2,2) coeff[-8,8]")
    out("="*70)
    t0 = time.time()
    hits = cmf.run(tgt, 2, 2, 8, 500, DEPTH)
    out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
    for ac, bc, d in hits:
        v = verify_hit(tgt, "cmf", ac, bc)
        if v:
            all_verified.append(v)
            out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# RUN 9: MITM cubic α for pi and e  
# ═══════════════════════════════════════════════════════════════════════
out(f"\n{'='*70}")
out("RUN 9: MITM → π  deg(3,1) coeff[-3,3] budget=5000")
out("="*70)
t0 = time.time()
hits = mitm.run("pi", 3, 1, 3, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("pi", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

out(f"\n{'='*70}")
out("RUN 10: MITM → e  deg(3,1) coeff[-3,3] budget=5000")
out("="*70)
t0 = time.time()
hits = mitm.run("e", 3, 1, 3, 5000, DEPTH)
out(f"  {len(hits)} raw hits in {time.time()-t0:.1f}s")
for ac, bc, d in hits:
    v = verify_hit("e", "mitm", ac, bc)
    if v:
        all_verified.append(v)
        out(f"  ✓ {v['formula_match']:25s} {v['digits']}dp  α={v['alpha_str']}  β={v['beta_str']}")

# ═══════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════

# Dedup
seen = set()
deduped = []
for v in all_verified:
    key = (v["target"], tuple(v["alpha_coeffs"]), tuple(v["beta_coeffs"]))
    negkey = (v["target"], tuple(-c for c in v["alpha_coeffs"]), tuple(-c for c in v["beta_coeffs"]))
    if key not in seen and negkey not in seen:
        seen.add(key)
        deduped.append(v)

deduped.sort(key=lambda x: (-x["digits"], x["target"]))

total_time = time.time() - t_total

out("\n" + "="*70)
out(f"FINAL REPORT: {len(deduped)} unique verified PCFs  ({total_time:.0f}s total)")
out("="*70)

by_const = {}
for v in deduped:
    by_const.setdefault(v["constant"], []).append(v)

for const, items in sorted(by_const.items()):
    out(f"\n  {const}:")
    for i, v in enumerate(items, 1):
        fr = " ✦FR" if v["factorial_reduction"] else ""
        out(f"    {i}. ≈ {v['formula_match']:25s}  {v['digits']:3d}dp  {v['convergence']:15s}{fr}")
        out(f"       α(n)={v['alpha_str']},  β(n)={v['beta_str']}")

# Save JSON
report = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "precision": PRECISION,
    "depth": DEPTH,
    "time_s": round(total_time, 1),
    "count": len(deduped),
    "discoveries": deduped,
}
with open("discovery_sweep_results.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
out(f"\nSaved → discovery_sweep_results.json")

outfile.close()
