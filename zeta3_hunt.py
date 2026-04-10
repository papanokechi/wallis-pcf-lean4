"""
zeta3_hunt.py — Targeted ζ(3) PCF Discovery
=============================================
Implements four search families for Apéry's constant ζ(3):
  A. Apéry neighbourhood: β=n⁴, α near (34,51,27,5)
  B. Quadratic-symmetric β: β=n²(n+k)², α cubic with α(0)=0
  C. Palindromic α: α₃=α₀, α₂=α₁, β linear or quadratic
  D. Factorial β: β=n!, β=(2n)!, with cubic α

All searches use direct PCF evaluation (no patching of the generator).
"""
import sys, time, json, random, math
from fractions import Fraction
from math import factorial, comb

import mpmath
from mpmath import mp, mpf, log, nstr, pslq

mp.dps = 120
random.seed(2026_04_06)

# ═══════════════════════════════════════════════════════════════════════
# PCF ENGINE
# ═══════════════════════════════════════════════════════════════════════

ZETA3 = mpmath.zeta(3)

CONSTANTS = {
    "zeta3":     ZETA3,
    "1/zeta3":   1/ZETA3,
    "zeta3^2":   ZETA3**2,
    "pi^2/7":    mpmath.pi**2/7,
    "pi^4/72":   mpmath.pi**4/72,
    "6/pi^2":    6/mpmath.pi**2,
    "pi^2/6":    mpmath.pi**2/6,
    "zeta5":     mpmath.zeta(5),
    "catalan":   mpmath.catalan,
    "ln2":       log(2),
    "1/ln2":     1/log(2),
}

def evaluate_pcf_custom(alpha_fn, beta_fn, depth, prec=None):
    """Evaluate PCF with callable alpha/beta functions."""
    if prec:
        mp.dps = prec + 20
    p_prev, p_curr = mpf(1), beta_fn(0)
    q_prev, q_curr = mpf(0), mpf(1)
    for n in range(1, depth + 1):
        a_n = alpha_fn(n)
        b_n = beta_fn(n)
        if b_n == 0 and a_n == 0:
            break
        p_new = b_n * p_curr + a_n * p_prev
        q_new = b_n * q_curr + a_n * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
    return p_curr / q_curr if q_curr != 0 else None

def match_constant(val, min_dp=12):
    if val is None or abs(val) > 1e10 or abs(val) < 1e-10:
        return None, 0
    best_name, best_dp = None, 0
    for name, cval in CONSTANTS.items():
        diff = abs(val - cval)
        if diff > 0:
            dp = -int(mpmath.log10(diff))
            if dp > best_dp:
                best_name, best_dp = name, dp
        # Also check simple rational multiples
        for p in range(-4, 5):
            if p == 0: continue
            for q in range(1, 5):
                diff2 = abs(val - mpf(p)/q * cval)
                if diff2 > 0:
                    dp2 = -int(mpmath.log10(diff2))
                    if dp2 > best_dp:
                        best_name, best_dp = f"{p}/{q}*{name}", dp2
    return (best_name, best_dp) if best_dp >= min_dp else (None, 0)

results = []
seen = set()

def record_hit(family, alpha_desc, beta_desc, val, name, dp, extra=""):
    key = (name, alpha_desc, beta_desc)
    if key in seen:
        return
    seen.add(key)
    results.append({
        "family": family, "alpha": alpha_desc, "beta": beta_desc,
        "match": name, "digits": dp, "value": nstr(val, 30), "extra": extra,
    })
    # Incremental save
    with open("zeta3_hunt_results.json", "w", encoding="utf-8") as f:
        json.dump({"count": len(results), "results": results}, f, indent=2)

t_total = time.time()

# ═══════════════════════════════════════════════════════════════════════
# FAMILY A: APÉRY NEIGHBOURHOOD
# β(n) = n⁴, α(n) = an³ + bn² + cn + d, near (34,51,27,5)
# ═══════════════════════════════════════════════════════════════════════
print("=" * 72, flush=True)
print("  FAMILY A: APÉRY NEIGHBOURHOOD  β(n) = n⁴", flush=True)
print("  Known: α = 34n³+51n²+27n+5 gives ζ(3)/6", flush=True)
print("=" * 72, flush=True)

t0 = time.time()
fa_hits = 0

for a in range(30, 40):
    for b in range(45, 58):
        for c in range(-15, 40):
            for d in range(-15, 16):
                if a == 34 and b == 51 and c == 27 and d == 5:
                    continue  # skip known Apéry
                alpha_fn = lambda n, a=a, b=b, c=c, d=d: a*n**3 + b*n**2 + c*n + d
                beta_fn = lambda n: n**4
                try:
                    with mpmath.workdps(25):
                        v = evaluate_pcf_custom(alpha_fn, beta_fn, 80)
                    if v is None: continue
                    name, dp = match_constant(v, min_dp=10)
                    if name and dp >= 10:
                        # Escalate
                        with mpmath.workdps(110):
                            v2 = evaluate_pcf_custom(alpha_fn, beta_fn, 300)
                        name2, dp2 = match_constant(v2, min_dp=15)
                        if name2 and dp2 >= 15:
                            desc = f"{a}n³+{b}n²+{c}n+{d}"
                            record_hit("A", desc, "n⁴", v2, name2, dp2)
                            fa_hits += 1
                            print(f"  + A: {name2:15s} {dp2:3d}dp  α={desc}", flush=True)
                except Exception:
                    continue

print(f"  Family A: {fa_hits} hits ({time.time()-t0:.0f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# FAMILY B: QUADRATIC-SYMMETRIC β
# β(n) = n²(n+k)², α(n) = an³+bn²+cn, α(0)=0
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  FAMILY B: QUADRATIC-SYMMETRIC β  β(n) = n²(n+k)²", flush=True)
print("=" * 72, flush=True)

t0 = time.time()
fb_hits = 0

for k_val in [1, 2, 4, 3, 5, 6]:
    print(f"\n  k={k_val}:", flush=True)
    k_hits = 0
    for a3 in range(-20, 21):
        if a3 == 0: continue
        for a2 in range(-20, 21):
            for a1 in range(-20, 21):
                alpha_fn = lambda n, a=a3, b=a2, c=a1: a*n**3 + b*n**2 + c*n
                beta_fn = lambda n, k=k_val: (n**2) * ((n + k)**2)
                try:
                    with mpmath.workdps(25):
                        v = evaluate_pcf_custom(alpha_fn, beta_fn, 60)
                    if v is None or abs(v) > 100 or abs(v) < 0.001:
                        continue
                    name, dp = match_constant(v, min_dp=8)
                    if name and dp >= 8:
                        with mpmath.workdps(110):
                            v2 = evaluate_pcf_custom(alpha_fn, beta_fn, 200)
                        name2, dp2 = match_constant(v2, min_dp=12)
                        if name2 and dp2 >= 12:
                            desc = f"{a3}n³+{a2}n²+{a1}n"
                            record_hit("B", desc, f"n²(n+{k_val})²", v2, name2, dp2)
                            fb_hits += 1
                            k_hits += 1
                            print(f"    + {name2:15s} {dp2:3d}dp  α={desc}  β=n²(n+{k_val})²", flush=True)
                except Exception:
                    continue
    print(f"    k={k_val}: {k_hits} hits", flush=True)

print(f"\n  Family B total: {fb_hits} hits ({time.time()-t0:.0f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# FAMILY C: b(n) = kn + c (our proven technique, but higher degree α)
# Specifically: α cubic, β linear — the approach that found π and ln2
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  FAMILY C: CUBIC α WITH LINEAR β (proven-technique extension)", flush=True)
print("=" * 72, flush=True)

t0 = time.time()
fc_hits = 0

for d in range(2, 10):
    for e in range(1, 8):
        beta_fn = lambda n, d=d, e=e: d*n + e
        for a3 in [-3, -2, -1, 1, 2, 3]:
            for a2 in range(-5, 6):
                for a1 in range(-5, 6):
                    alpha_fn = lambda n, a=a3, b=a2, c=a1: a*n**3 + b*n**2 + c*n
                    try:
                        with mpmath.workdps(25):
                            v = evaluate_pcf_custom(alpha_fn, beta_fn, 80)
                        if v is None or abs(v) > 100 or abs(v) < 0.001:
                            continue
                        name, dp = match_constant(v, min_dp=8)
                        if name and "zeta" in name and dp >= 8:
                            with mpmath.workdps(110):
                                v2 = evaluate_pcf_custom(alpha_fn, beta_fn, 300)
                            name2, dp2 = match_constant(v2, min_dp=12)
                            if name2 and dp2 >= 12:
                                desc = f"{a3}n³+{a2}n²+{a1}n"
                                record_hit("C", desc, f"{d}n+{e}", v2, name2, dp2)
                                fc_hits += 1
                                print(f"  + {name2:15s} {dp2:3d}dp  α={desc}  β={d}n+{e}", flush=True)
                    except Exception:
                        continue

print(f"\n  Family C: {fc_hits} hits ({time.time()-t0:.0f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# FAMILY D: DESCENT & REPEL on promising starting points
# Use random starts near Apéry coefficients with various β shapes
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  FAMILY D: DESCENT & REPEL (gradient search)", flush=True)
print("=" * 72, flush=True)

t0 = time.time()
fd_hits = 0

def dr_score(alpha_c, beta_c, target, depth=80):
    """Score a candidate: lower = closer to target."""
    try:
        alpha_fn = lambda n: sum(c * n**i for i, c in enumerate(alpha_c))
        beta_fn = lambda n: sum(c * n**i for i, c in enumerate(beta_c))
        with mpmath.workdps(25):
            v = evaluate_pcf_custom(alpha_fn, beta_fn, depth)
        if v is None:
            return 1e10
        return float(abs(v - target))
    except:
        return 1e10

# Starting points for D&R
starts = [
    # Near Apéry
    ([5, 27, 51, 34], [0, 0, 0, 0, 1]),  # α≈(5,27,51,34), β=n⁴
    ([3, 20, 40, 30], [0, 0, 0, 0, 1]),
    ([0, 0, 0, -1], [1, 3]),              # cubic α, linear β
    ([0, 0, -1, 0], [2, 3]),
    ([0, 0, 0, 1], [0, 0, 1, 0]),         # β=n²
    ([0, 1, -2, 1], [1, 4]),              # Perturbed from pi family
    ([0, 0, -2, 3], [1, 5]),
]

for si, (init_alpha, init_beta) in enumerate(starts):
    alpha_c = list(init_alpha)
    beta_c = list(init_beta)
    best_score = dr_score(alpha_c, beta_c, ZETA3)
    n_params = len(alpha_c)
    
    for iteration in range(200):
        improved = False
        for i in range(n_params):
            for delta in [-1, 1, -2, 2, -3, 3]:
                trial = alpha_c[:]
                trial[i] += delta
                if abs(trial[i]) > 50:
                    continue
                score = dr_score(trial, beta_c, ZETA3)
                if score < best_score * 0.99:
                    best_score = score
                    alpha_c = trial
                    improved = True
        
        if not improved:
            break
        
        if best_score < 1e-8:
            alpha_fn = lambda n: sum(c * n**i for i, c in enumerate(alpha_c))
            beta_fn = lambda n: sum(c * n**i for i, c in enumerate(beta_c))
            with mpmath.workdps(110):
                v = evaluate_pcf_custom(alpha_fn, beta_fn, 300)
            name, dp = match_constant(v, min_dp=10)
            if name and dp >= 10:
                desc_a = "+".join(f"{c}n^{i}" for i, c in enumerate(alpha_c) if c != 0)
                desc_b = "+".join(f"{c}n^{i}" for i, c in enumerate(beta_c) if c != 0)
                record_hit("D", desc_a, desc_b, v, name, dp, f"start={si}")
                fd_hits += 1
                print(f"  + D[{si}]: {name:15s} {dp:3d}dp  α={alpha_c}  β={beta_c}", flush=True)
            break

print(f"\n  Family D: {fd_hits} hits ({time.time()-t0:.0f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════
total_time = time.time() - t_total

print("\n" + "=" * 72, flush=True)
print(f"  ζ(3) HUNT COMPLETE ({total_time:.0f}s)", flush=True)
print(f"  Total hits: {len(results)}", flush=True)
print("=" * 72, flush=True)

if results:
    for r in sorted(results, key=lambda x: -x["digits"]):
        print(f"  [{r['family']}] {r['match']:20s} {r['digits']:3d}dp  "
              f"α={r['alpha']}  β={r['beta']}", flush=True)
else:
    print("  No ζ(3)-related PCFs found at this search budget.", flush=True)
    print("  This is consistent with known difficulty of ζ(3) PCFs —", flush=True)
    print("  Apéry's original requires degree-6 β (n⁶ effectively).", flush=True)

print(f"\n  Saved → zeta3_hunt_results.json", flush=True)
