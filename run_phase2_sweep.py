"""
Phase 2 Discovery Sweep
========================
Three targeted investigations based on Phase 1 findings:

1. HYPERGEOMETRIC BACK-MATCHING: Map discovered PCFs to _2F1 / _3F2 identities
2. MODULAR SIGNATURE SWEEP: b(n) = kn+1 for k in {3,4,5,6} across all constants
3. DEEP ZETA(3) HUNT: Apery-style n^3 signatures and higher-degree a(n)
"""
import sys, time, json, random, math
sys.path.insert(0, '.')
random.seed(2026_04_05)

import mpmath
mpmath.mp.dps = 200

from ramanujan_breakthrough_generator import (
    PCFEngine, MITMSearch, CMFSearch, CONSTANTS, poly_to_str
)
from sympy import (
    Symbol, factor, simplify, Rational, hyper, gamma as Gamma,
    oo, pi as sym_pi, S, nsimplify, sqrt
)

PRECISION = 80
DEPTH = 300
engine = PCFEngine(precision=PRECISION)
mpmath.mp.dps = PRECISION + 30
mitm = MITMSearch(engine)

results = []
seen = set()

def add_hit(target, algo, ac, bc):
    key = (target, tuple(ac), tuple(bc))
    nk = (target, tuple(-c for c in ac), tuple(-c for c in bc))
    if key in seen or nk in seen:
        return None
    seen.add(key)
    val, err, _ = engine.evaluate_pcf(ac, bc, DEPTH)
    if val is None:
        return None
    matched, formula, digits = engine.match_known_constant(val, target, PRECISION)
    if digits < 15:
        return None
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
    with open("pcf_phase2_results.json", "w", encoding="utf-8") as f:
        json.dump({"count": len(results), "discoveries": results}, f, indent=2, ensure_ascii=False)
    return r

t_total = time.time()

# ═══════════════════════════════════════════════════════════════════════════════
# PART 1: HYPERGEOMETRIC BACK-MATCHING
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 72, flush=True)
print("  PART 1: HYPERGEOMETRIC BACK-MATCHING", flush=True)
print("  Mapping Phase 1 PCFs to known _2F1 / _3F2 series", flush=True)
print("=" * 72, flush=True)

# Load Phase 1 discoveries
phase1 = json.load(open("pcf_discoveries.json"))["discoveries"]
n = Symbol('n')

for i, d in enumerate(phase1, 1):
    ac = d["alpha_coeffs"]
    bc = d["beta_coeffs"]
    alpha_poly = sum(c * n**j for j, c in enumerate(ac))
    beta_poly = sum(c * n**j for j, c in enumerate(bc))
    fa = factor(alpha_poly)
    fb = factor(beta_poly)

    print(f"\n  [{i}] {d['constant']}: a(n)={fa}, b(n)={fb}", flush=True)
    print(f"      match: {d['formula']} at {d['digits']}dp", flush=True)

    # Analyze ratio a(n)/b(n) pattern & Gauss CF structure
    # A generalized CF b0 + a1/(b1 + a2/(b2+...)) with a(n)=P(n), b(n)=Q(n)
    # relates to _2F1 when a(n) ~ c*n*(n+d) and b(n) ~ linear

    # Check: is a(n) factorable as c*(n-r1)*(n-r2)?
    from sympy import roots as sym_roots
    alpha_roots = sym_roots(alpha_poly, n)
    beta_roots = sym_roots(beta_poly, n)
    print(f"      a(n) roots: {alpha_roots}", flush=True)
    print(f"      b(n) roots: {beta_roots}", flush=True)

    # Compute ratio of consecutive convergents to look for hypergeometric pattern
    # For a _2F1 CF, we expect a(n) = -n(n+a)/(something) pattern
    val = mpmath.mpf(d["value"])

    # Try mpmath.identify for hypergeometric connection
    try:
        ident = mpmath.identify(abs(val), tol=1e-25)
        if ident:
            print(f"      mpmath.identify: {ident}", flush=True)
    except Exception:
        pass

    # Specific checks for known CF forms
    # Gauss CF for _2F1(a,b;c;z): a(n) = -(a+n)(b+n)z / ((c+2n)(c+2n+1))  etc.
    # Check if our a(n),b(n) fit any Gauss pattern

    # For Brouncker: a(n)=n^2, b(n)=2n+1 is the Wallis-Euler CF for 4/pi
    # This corresponds to _2F1(1/2, 1; 3/2; 1) via arctan series
    if tuple(ac) == (0, 0, 1) and tuple(bc) == (1, 2, 0):
        print("      => Wallis-Euler CF for 4/pi = _2F1(1/2, 1; 3/2; -1) via arctan", flush=True)
        print("         Known identity: 4/pi = 1/(1+1^2/(3+2^2/(5+3^2/(7+...))))", flush=True)

    # For e: a(n)=-n, b(n)=n+3
    elif tuple(ac) == (0, -1, 0) and tuple(bc) == (3, 1):
        print("      => Euler CF variant for e", flush=True)
        # e = 2 + 1/(1 + 1/(2 + 2/(3 + 3/(4 + ...))))
        # Our form: b(0)=3, a(1)=-1, b(1)=4, a(2)=-2, b(2)=5,...
        # This is e = 3 + (-1)/(4 + (-2)/(5 + (-3)/(6 + ...)))
        # i.e. e = 3 - 1/(4 - 2/(5 - 3/(6 - ...)))
        # Relation to _1F1(1;2;1) = (e-1)/1 = e-1 ... through Kummer CF
        print("      b(0)=3: starts at e = 3 - CF_tail", flush=True)
        print("      Pattern: e = 3 - 1/(4 - 2/(5 - 3/(6 - ...)))", flush=True)
        # Verify by computing the CF from n=1 with this interpretation
        with mpmath.workdps(60):
            # CF: 3 + (-1)/(4 + (-2)/(5 + (-3)/(6 + ...)))
            v = mpmath.mpf(0)
            for k in range(200, 0, -1):
                v = (-k) / (k + 3 + v)
            v = 3 + v
            diff = abs(v - mpmath.e)
            print(f"      Direct CF check: |val - e| = {mpmath.nstr(diff, 5)}", flush=True)
        print("      => Related to Kummer's CF: _1F1(1;2;1) = e-1", flush=True)
        print("         Shifted by +3 start: likely equivalent to classical Euler CF", flush=True)

    # For phi: a(n)=(n+1)(n+2), b(n)=-(n+2)
    elif tuple(ac) == (2, 3, 1) and tuple(bc) == (-2, -1):
        print("      => a(n)=(n+1)(n+2), b(n)=-(n+2)", flush=True)
        print("      a(n)/b(n) = -(n+1):  ratio is linear!", flush=True)
        print("      This suggests a telescoping or ratio-based simplification", flush=True)
        # phi = (1+sqrt(5))/2, so -2*phi = -(1+sqrt(5))
        # The CF converges to -(1+sqrt(5))
        # Check if this is related to the standard phi CF: phi = 1+1/(1+1/(1+...))
        print("      val = -2*phi = -(1+sqrt(5))", flush=True)
        print("      Possibly related to a quadratic irrationality CF", flush=True)

    # For pi b(n)=3n+1 family
    elif tuple(bc) == (-1, -3):
        print("      => b(n)=-(3n+1) family for pi", flush=True)
        # Check: is this related to _2F1 at z=1/4 or similar?
        # The 3n+1 denominator suggests connection to cube-root or third-order series
        print("      Denominator progression: 1, 4, 7, 10, 13,... (arithmetic, d=3)", flush=True)
        print("      cf. Brouncker uses 1, 3, 5, 7,... (arithmetic, d=2)", flush=True)
        # Try matching to _2F1(a,b;c;z) with specific z
        # For a CF with b(n)=3n+1, the series parameter is related to z=1/9 or 1/3
        print("      Potential _2F1 connection: z=1/3 or z=1/9 family", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PART 2: MODULAR SIGNATURE SWEEP  b(n) = kn + c
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  PART 2: MODULAR SIGNATURE SWEEP", flush=True)
print("  b(n) = kn+c for k in {2,3,4,5,6}, targeted a(n) patterns", flush=True)
print("=" * 72, flush=True)

# Strategy: Fix b(n) = kn+1 (or kn+c for small c), sweep a(n) quadratic
# This is more targeted than random MITM — we exploit the structure found in Phase 1.

targets = ["pi", "e", "zeta3", "ln2", "catalan", "sqrt2", "phi", "euler_gamma"]

for k in [3, 4, 5, 6]:
    print(f"\n  -- b(n) = {k}n + c family --", flush=True)
    for c_offset in [1, -1, 2, -2]:
        beta_c = [c_offset, k]  # b(n) = c_offset + k*n
        # Sweep a(n) = a0 + a1*n + a2*n^2 with a0 in [-5,5], a1 in [-5,5], a2 in [-3,3]
        sweep_hits = 0
        t0 = time.time()
        for tgt in targets:
            target_val = engine._get_constant(tgt)
            if target_val is None:
                continue
            for a0 in range(-3, 4):
                for a1 in range(-5, 6):
                    for a2 in range(-3, 4):
                        if a2 == 0 and a1 == 0:
                            continue  # skip constant a(n)
                        ac = [a0, a1, a2]
                        try:
                            with mpmath.workdps(15):
                                v, _, _ = engine.evaluate_pcf(ac, beta_c, 60)
                            if v is None:
                                continue
                            # Quick match
                            matched, formula, digits = engine.match_known_constant(v, tgt, 15)
                            if digits >= 12:
                                # Full precision verify
                                r = add_hit(tgt, f"sig_k{k}_c{c_offset}", ac, beta_c)
                                if r:
                                    sweep_hits += 1
                                    fr = " FR" if r["factorial_reduction"] else ""
                                    print(f"    + {CONSTANTS[tgt][0]:6s} {r['formula']:25s} {r['digits']:3d}dp  "
                                          f"a(n)={r['alpha_str']}, b(n)={r['beta_str']}{fr}", flush=True)
                        except Exception:
                            continue
        dt = time.time() - t0
        if sweep_hits == 0:
            print(f"    b(n)={c_offset:+d}+{k}n: 0 hits ({dt:.1f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PART 3: DEEP ZETA(3) HUNT — Apery signatures
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  PART 3: DEEP ZETA(3) HUNT", flush=True)
print("  Apery-style: a(n) ~ n^3 and n^4 signatures, larger coefficients", flush=True)
print("=" * 72, flush=True)

# Apery's proof used: a(n) = -n^6 (effectively), b(n) = 34n^3 - 51n^2 + 27n - 5
# At lower degrees, we need a(n) ~ n^3 or n^4 patterns
# Also try: generalized b(n) with leading term matching Apery

zeta3_val = engine._get_constant("zeta3")
zeta3_hits = 0

# Strategy A: a(n) = c * n^3, b(n) linear or quadratic
print("\n  Strategy A: a(n) = c*n^3 + lower, b(n) linear", flush=True)
t0 = time.time()
for a3 in [-3, -2, -1, 1, 2, 3]:
    for a2 in range(-3, 4):
        for a1 in range(-3, 4):
            for a0 in range(-2, 3):
                ac = [a0, a1, a2, a3]
                for b0 in range(-5, 6):
                    for b1 in range(1, 8):  # positive b1 for convergence
                        bc = [b0, b1]
                        try:
                            with mpmath.workdps(15):
                                v, _, _ = engine.evaluate_pcf(ac, bc, 80)
                            if v is None:
                                continue
                            matched, formula, digits = engine.match_known_constant(v, "zeta3", 15)
                            if digits >= 10:
                                r = add_hit("zeta3", "apery_d31", ac, bc)
                                if r:
                                    zeta3_hits += 1
                                    print(f"    + zeta3 {r['formula']:25s} {r['digits']:3d}dp  "
                                          f"a(n)={r['alpha_str']}, b(n)={r['beta_str']}", flush=True)
                        except Exception:
                            continue
dt = time.time() - t0
print(f"    Strategy A: {zeta3_hits} hits ({dt:.1f}s)", flush=True)

# Strategy B: a(n) = c*n^3, b(n) quadratic
print("\n  Strategy B: a(n) = c*n^3 + lower, b(n) quadratic", flush=True)
t0 = time.time()
zeta3_hits_b = 0
for a3 in [-2, -1, 1, 2]:
    for a2 in range(-2, 3):
        for a1 in range(-2, 3):
            ac = [0, a1, a2, a3]
            for b0 in range(-3, 4):
                for b1 in range(-3, 8):
                    for b2 in range(1, 5):  # ensure growth
                        bc = [b0, b1, b2]
                        try:
                            with mpmath.workdps(15):
                                v, _, _ = engine.evaluate_pcf(ac, bc, 80)
                            if v is None:
                                continue
                            matched, formula, digits = engine.match_known_constant(v, "zeta3", 15)
                            if digits >= 10:
                                r = add_hit("zeta3", "apery_d32", ac, bc)
                                if r:
                                    zeta3_hits_b += 1
                                    print(f"    + zeta3 {r['formula']:25s} {r['digits']:3d}dp  "
                                          f"a(n)={r['alpha_str']}, b(n)={r['beta_str']}", flush=True)
                        except Exception:
                            continue
dt = time.time() - t0
print(f"    Strategy B: {zeta3_hits_b} hits ({dt:.1f}s)", flush=True)

# Strategy C: Try ALL 8 constants with a(n) cubic, b(n) linear, budget MITM
print("\n  Strategy C: MITM cubic alpha, all stubborn constants", flush=True)
for tgt in ["zeta3", "ln2", "sqrt2", "catalan", "euler_gamma"]:
    t0 = time.time()
    hits = mitm.run(tgt, 3, 1, 5, 5000, DEPTH)
    for ac, bc, d in hits:
        r = add_hit(tgt, "mitm_d31_c5", ac, bc)
        if r:
            print(f"    + {CONSTANTS[tgt][0]:6s} {r['formula']:25s} {r['digits']:3d}dp  "
                  f"a(n)={r['alpha_str']}, b(n)={r['beta_str']}", flush=True)
    dt = time.time() - t0
    sym = "+" if hits else " "
    print(f"  {sym} {CONSTANTS[tgt][0]:6s} MITM d(3,1) c5 -> {len(hits):2d} hits ({dt:.1f}s)  [total={len(results)}]", flush=True)

# Strategy D: Specifically try the Apery polynomial signature
# b(n) = (2n+1)(An^2+An+B) patterns for small A, B
print("\n  Strategy D: Apery-like b(n) = (2n+1)(An^2+An+B)", flush=True)
t0 = time.time()
zeta3_hits_d = 0
for A in range(1, 12):
    for B in range(-5, 6):
        # b(n) = (2n+1)(An^2 + An + B) = 2An^3 + (3A)n^2 + (A+2B)n + B
        bc = [B, A + 2*B, 3*A, 2*A]
        for a_lead in [-1, 1, -2, 2]:
            # a(n) = a_lead * n^3 (pure cubic)
            for a2 in range(-2, 3):
                ac = [0, 0, a2, a_lead]
                try:
                    with mpmath.workdps(15):
                        v, _, _ = engine.evaluate_pcf(ac, bc, 80)
                    if v is None:
                        continue
                    matched, formula, digits = engine.match_known_constant(v, "zeta3", 15)
                    if digits >= 10:
                        r = add_hit("zeta3", "apery_sig", ac, bc)
                        if r:
                            zeta3_hits_d += 1
                            print(f"    + zeta3  {r['formula']:25s} {r['digits']:3d}dp  "
                                  f"a(n)={r['alpha_str']}, b(n)={r['beta_str']}", flush=True)
                except Exception:
                    continue
        # Also try a(n) = -n^6 approximation: a(n) proportional to n^3*(n+1)^3
        # Low-degree approx: a(n) ~ n^3
dt = time.time() - t0
print(f"    Strategy D: {zeta3_hits_d} hits ({dt:.1f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════════════
total_time = time.time() - t_total

print("\n" + "=" * 72, flush=True)
print(f"  PHASE 2 FINAL REPORT: {len(results)} new discoveries ({total_time:.0f}s)", flush=True)
print("=" * 72, flush=True)

if results:
    by_c = {}
    for r in results:
        by_c.setdefault(r["constant"], []).append(r)
    for c, items in sorted(by_c.items()):
        print(f"\n  {c}:", flush=True)
        for v in sorted(items, key=lambda x: -x["digits"]):
            fr = " FR" if v["factorial_reduction"] else ""
            print(f"    {v['formula']:28s}  {v['digits']:3d}dp  {v['convergence']}{fr}", flush=True)
            print(f"       a(n)={v['alpha_str']}, b(n)={v['beta_str']}  [{v['algo']}]", flush=True)
else:
    print("  No new discoveries beyond Phase 1.", flush=True)

# Merge with Phase 1 and save combined
phase1_data = json.load(open("pcf_discoveries.json"))["discoveries"]
combined = phase1_data + results
combined_dedup = []
combined_seen = set()
for r in combined:
    key = (r["target"], tuple(r["alpha_coeffs"]), tuple(r["beta_coeffs"]))
    nk = (r["target"], tuple(-c for c in r["alpha_coeffs"]), tuple(-c for c in r["beta_coeffs"]))
    if key not in combined_seen and nk not in combined_seen:
        combined_seen.add(key)
        combined_dedup.append(r)

with open("pcf_all_discoveries.json", "w", encoding="utf-8") as f:
    json.dump({
        "phase1_count": len(phase1_data),
        "phase2_count": len(results),
        "total_unique": len(combined_dedup),
        "discoveries": combined_dedup
    }, f, indent=2, ensure_ascii=False)
print(f"\n  Combined results: {len(combined_dedup)} unique PCFs -> pcf_all_discoveries.json", flush=True)
