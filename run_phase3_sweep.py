"""
Phase 3: Generalization & Analytic Derivation Sweep
=====================================================
1. Generalized log-family: sweep for ln(3), ln(5), ln(k) using a(n)~n², b(n)=3n+c
2. Pi family c-parameter: a(n)=-n(2n-c) for c=0..20, b(n)=3n+1
3. Broader b(n)=kn+c family: k=2..8, constants including pi², zeta(3), Catalan, gamma
4. Gauss CF reverse-engineering: extract hypergeometric parameters from discovered PCFs
5. Convergence rate comparison: bits/term for each PCF vs Brouncker
"""
import sys, time, json, random, math
sys.path.insert(0, '.')
random.seed(2026)

import mpmath
from mpmath import mp, mpf, log, pi as mp_pi, nstr, pslq, workdps
mp.dps = 120

from ramanujan_breakthrough_generator import PCFEngine, poly_to_str
from sympy import Symbol, factor, Rational

DEPTH = 500
engine = PCFEngine(precision=100)

# Extended constant library
CONSTANTS = {
    "pi":       mp_pi,
    "2/pi":     2/mp_pi,
    "4/pi":     4/mp_pi,
    "pi^2":     mp_pi**2,
    "pi^2/6":   mp_pi**2/6,
    "1/pi":     1/mp_pi,
    "e":        mp.e,
    "1/e":      1/mp.e,
    "ln2":      log(2),
    "1/ln2":    1/log(2),
    "ln3":      log(3),
    "1/ln3":    1/log(3),
    "ln5":      log(5),
    "1/ln5":    1/log(5),
    "ln(3/2)":  log(mpf(3)/2),
    "1/ln(3/2)":1/log(mpf(3)/2),
    "ln(4/3)":  log(mpf(4)/3),
    "1/ln(4/3)":1/log(mpf(4)/3),
    "ln10":     log(10),
    "1/ln10":   1/log(10),
    "sqrt2":    mpmath.sqrt(2),
    "sqrt3":    mpmath.sqrt(3),
    "phi":      (1+mpmath.sqrt(5))/2,
    "catalan":  mpmath.catalan,
    "1/catalan":1/mpmath.catalan,
    "euler_gamma": mpmath.euler,
    "1/euler_gamma": 1/mpmath.euler,
    "zeta3":    mpmath.zeta(3),
    "1/zeta3":  1/mpmath.zeta(3),
    "zeta5":    mpmath.zeta(5),
}

results = []
seen = set()

def eval_poly(coeffs, n):
    return sum(mpf(c) * mpf(n)**i for i, c in enumerate(coeffs))

def evaluate_pcf_fast(ac, bc, depth=200):
    """Quick PCF evaluation at current precision."""
    alpha = lambda n: eval_poly(ac, n)
    beta = lambda n: eval_poly(bc, n)
    p_prev, p_curr = mpf(1), beta(0)
    q_prev, q_curr = mpf(0), mpf(1)
    for n in range(1, depth + 1):
        a_n, b_n = alpha(n), beta(n)
        p_new = b_n * p_curr + a_n * p_prev
        q_new = b_n * q_curr + a_n * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
    return p_curr / q_curr if q_curr != 0 else None

def match_constant(val, min_dp=12):
    """Match a value against extended constant library."""
    if val is None:
        return None, "", 0
    best = ("", 0)
    for name, cval in CONSTANTS.items():
        diff = abs(val - cval)
        if diff > 0:
            dp = -int(mpmath.log10(diff))
            if dp > best[1]:
                best = (name, dp)
    if best[1] >= min_dp:
        return best[0], best[1]
    return None, 0

def add_result(ac, bc, algo, const_name, dp, val):
    key = (const_name, tuple(ac), tuple(bc))
    nk = (const_name, tuple(-c for c in ac), tuple(-c for c in bc))
    if key in seen or nk in seen:
        return False
    seen.add(key)
    results.append({
        "constant": const_name, "alpha": ac, "beta": bc,
        "digits": dp, "algo": algo, "value": str(val)[:50],
        "alpha_str": poly_to_str(ac), "beta_str": poly_to_str(bc),
    })
    return True

t_total = time.time()

# ═══════════════════════════════════════════════════════════════════════
# PART 1: GENERALIZED LOG-FAMILY SWEEP
# a(n) = p*n^2 + q*n + r,  b(n) = 3n + c
# ═══════════════════════════════════════════════════════════════════════
print("=" * 72, flush=True)
print("  PART 1: GENERALIZED LOG-FAMILY SWEEP", flush=True)
print("  a(n) = p*n^2 + q*n + r,  b(n) = 3n + c,  c = 1..8", flush=True)
print("=" * 72, flush=True)

t0 = time.time()
p1_hits = 0

for c_val in range(1, 9):
    bc = [c_val, 3]
    for p in range(-5, 1):  # negative p for convergence (a(n) negative for large n)
        if p == 0: continue
        for q in range(-5, 6):
            for r in range(-3, 4):
                ac = [r, q, p]
                try:
                    with workdps(30):
                        v = evaluate_pcf_fast(ac, bc, 100)
                    if v is None or abs(v) > 100 or abs(v) < 0.01:
                        continue
                    name, dp = match_constant(v, min_dp=10)
                    if name:
                        # Verify at higher precision
                        with workdps(100):
                            v2 = evaluate_pcf_fast(ac, bc, DEPTH)
                        name2, dp2 = match_constant(v2, min_dp=20)
                        if name2 and dp2 >= 20:
                            if add_result(ac, bc, f"log_c{c_val}", name2, dp2, v2):
                                p1_hits += 1
                                n_sym = Symbol('n')
                                ap = sum(coeff * n_sym**i for i, coeff in enumerate(ac))
                                print(f"  + {name2:15s} {dp2:3d}dp  a(n)={factor(ap):20s}  "
                                      f"b(n)=3n+{c_val}", flush=True)
                except Exception:
                    continue

dt1 = time.time() - t0
print(f"\n  Part 1: {p1_hits} hits in {dt1:.0f}s", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# PART 2: PI FAMILY c-PARAMETER SWEEP
# a(n) = -n(2n - c), b(n) = 3n + 1, varying c
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  PART 2: PI-FAMILY c-PARAMETER SWEEP", flush=True)
print("  a(n) = -n(2n - c),  b(n) = 3n + 1,  c = -5..20", flush=True)
print("=" * 72, flush=True)

t0 = time.time()
pi_family = []

bc_pi = [1, 3]

print(f"\n  {'c':>4s}  {'a(n)':20s}  {'Value (30d)':35s}  {'Match':15s}  {'dp':>5s}  {'PSLQ':30s}", flush=True)
print(f"  {'-'*110}", flush=True)

for c_param in range(-5, 21):
    # a(n) = -n(2n - c) = -2n^2 + cn = c*n - 2*n^2
    ac = [0, c_param, -2]
    
    with workdps(100):
        v = evaluate_pcf_fast(ac, bc_pi, DEPTH)
    
    if v is None or abs(v) > 1000:
        print(f"  {c_param:4d}  a(n)=-n(2n-{c_param:+d})       {'DIVERGED':35s}", flush=True)
        continue
    
    name, dp = match_constant(v, min_dp=15)
    
    # PSLQ against [1, val, pi, ln2]
    pslq_str = ""
    try:
        rel = pslq([mpf(1), v, mp_pi, log(2)], maxcoeff=1000)
        if rel:
            pslq_str = str(rel)
    except:
        pass
    
    if not pslq_str:
        try:
            rel = pslq([mpf(1), v, mp_pi], maxcoeff=1000)
            if rel:
                pslq_str = f"pi: {rel}"
        except:
            pass
    
    n_sym = Symbol('n')
    ap = factor(sum(coeff * n_sym**i for i, coeff in enumerate(ac)))
    
    pi_family.append({"c": c_param, "alpha": ac, "value": str(v)[:50], 
                       "match": name or "?", "dp": dp, "pslq": pslq_str})
    
    marker = "*" if dp >= 20 else " "
    print(f" {marker}{c_param:4d}  {str(ap):20s}  {nstr(v, 30):35s}  {(name or '?'):15s}  {dp:5d}  {pslq_str[:30]}", flush=True)
    
    if name and dp >= 20:
        add_result(ac, bc_pi, f"pi_family_c{c_param}", name, dp, v)

dt2 = time.time() - t0
print(f"\n  Part 2: {dt2:.0f}s", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# PART 3: BROADER k-FAMILY SWEEP
# b(n) = kn + c for k=2..8, a(n) quadratic, all extended constants
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  PART 3: BROADER k-FAMILY SWEEP", flush=True)
print("  b(n) = kn + c,  k = 2..8, seeking new constants", flush=True)
print("=" * 72, flush=True)

t0 = time.time()
p3_hits = 0

for k in range(2, 9):
    for c_val in range(1, 6):
        bc = [c_val, k]
        for p in [-3, -2, -1]:
            for q in range(-4, 5):
                ac = [0, q, p]
                try:
                    with workdps(30):
                        v = evaluate_pcf_fast(ac, bc, 100)
                    if v is None or abs(v) > 100 or abs(v) < 0.01:
                        continue
                    name, dp = match_constant(v, min_dp=10)
                    if name:
                        with workdps(100):
                            v2 = evaluate_pcf_fast(ac, bc, DEPTH)
                        name2, dp2 = match_constant(v2, min_dp=20)
                        if name2 and dp2 >= 20:
                            if add_result(ac, bc, f"kfam_k{k}_c{c_val}", name2, dp2, v2):
                                p3_hits += 1
                                print(f"  + {name2:15s} {dp2:3d}dp  a(n)={poly_to_str(ac):15s}  "
                                      f"b(n)={k}n+{c_val}", flush=True)
                except Exception:
                    continue

dt3 = time.time() - t0
print(f"\n  Part 3: {p3_hits} hits in {dt3:.0f}s", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# PART 4: CONVERGENCE RATE COMPARISON
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  PART 4: CONVERGENCE RATE COMPARISON (bits/term)", flush=True)
print("=" * 72, flush=True)

ref_pcfs = {
    "Brouncker 4/pi":   ([0, 0, 1], [1, 2, 0], 4/mp_pi),
    "D1: 2/pi (3n+1)":  ([0, 1, -2], [1, 3], 2/mp_pi),
    "D2: 4/pi (3n+1)":  ([0, 3, -2], [1, 3], 4/mp_pi),
    "D3: 1/ln2 (3n+2)": ([0, 0, -2], [2, 3], 1/log(2)),
    "Euler e (n+3)":     ([0, -1, 0], [3, 1], mp.e),
}

print(f"\n  {'PCF':25s}  {'Depth':>6s}  {'Match dp':>8s}  {'bits/term':>10s}  {'dp/term':>8s}", flush=True)
print(f"  {'-'*65}", flush=True)

with workdps(200):
    for label, (ac, bc, target) in ref_pcfs.items():
        for depth in [100, 200, 500]:
            v = evaluate_pcf_fast(ac, bc, depth)
            if v is not None:
                err = abs(v - target)
                if err > 0:
                    dp = -int(mpmath.log10(err))
                    bits = dp * math.log2(10)
                    print(f"  {label:25s}  {depth:6d}  {dp:6d}dp  {bits/depth:8.2f} b/t  {dp/depth:6.2f} d/t", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# PART 5: GAUSS CF PARAMETER REVERSE-ENGINEERING
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  PART 5: GAUSS CF PARAMETER IDENTIFICATION", flush=True)
print("=" * 72, flush=True)

# The Gauss CF for _2F1(a,b;c;z) is:
#   F(a,b;c;z)/F(a,b+1;c+1;z) = 1/(1 + d_1*z/(1 + d_2*z/(1 + ...)))
# where d_{2m-1} = (a+m-1)(c-b+m-1)/((c+2m-3)(c+2m-2))
#       d_{2m}   = (b+m-1)(c-a+m-1)/((c+2m-2)(c+2m-1))
#
# But our CF has form: b(0) + a(1)/(b(1) + a(2)/(b(2) + ...))
# Not the standard 1/(1+...) form. We need to convert.
#
# Alternative: Euler-Minding CF representation
# Any _2F1 has a CF of the form:
#   _2F1(a,b;c;z) = 1 + abz/c / (1 + e_1z/(1 + e_2z/(1+...)))
#
# For our non-standard form, try direct parameter matching:
# Compare a(n)/b(n) ratios with known hypergeometric CF coefficients

n_sym = Symbol('n')

print("\n  Analyzing ratio structure a(n)/b(n-1)*b(n) for each PCF:", flush=True)

for label, (ac, bc, target) in ref_pcfs.items():
    print(f"\n  {label}:", flush=True)
    # Compute first 8 values of a(n), b(n), and the ratio a(n)/(b(n)*b(n-1))
    vals = []
    for n_val in range(1, 9):
        a_n = eval_poly(ac, n_val)
        b_n = eval_poly(bc, n_val)
        b_nm1 = eval_poly(bc, n_val - 1)
        ratio = float(a_n / (b_n * b_nm1)) if b_n * b_nm1 != 0 else float('inf')
        vals.append((n_val, float(a_n), float(b_n), ratio))
    
    print(f"    {'n':>3s}  {'a(n)':>10s}  {'b(n)':>8s}  {'a(n)/(b(n)b(n-1))':>20s}", flush=True)
    for n_val, a_n, b_n, ratio in vals:
        print(f"    {n_val:3d}  {a_n:10.1f}  {b_n:8.1f}  {ratio:20.6f}", flush=True)
    
    # Check if ratio approaches a limit (= z in Gauss CF)
    if len(vals) > 2:
        ratios = [v[3] for v in vals[2:]]
        if all(abs(r) < 10 for r in ratios):
            mean_r = sum(ratios) / len(ratios)
            print(f"    Ratio limit estimate: {mean_r:.6f}", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════
total_time = time.time() - t_total

print("\n" + "=" * 72, flush=True)
print(f"  PHASE 3 REPORT: {len(results)} total discoveries ({total_time:.0f}s)", flush=True)
print("=" * 72, flush=True)

by_const = {}
for r in results:
    by_const.setdefault(r["constant"], []).append(r)

for cname, items in sorted(by_const.items()):
    print(f"\n  {cname}:", flush=True)
    for v in sorted(items, key=lambda x: -x["digits"]):
        print(f"    {v['digits']:3d}dp  a(n)={v['alpha_str']:20s}  b(n)={v['beta_str']:10s}  [{v['algo']}]", flush=True)

# Save
with open("pcf_phase3_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "count": len(results),
        "pi_family_sweep": pi_family,
        "discoveries": results,
        "time_s": round(total_time, 1),
    }, f, indent=2, ensure_ascii=False)
print(f"\n  Saved -> pcf_phase3_results.json", flush=True)
