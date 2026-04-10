"""
OEIS A002865 Relay Chain — Round 7 (Synthesizer Agent)
Goal: Derive the EXACT value of L = lim C_m, reconcile all prior claims,
check the -1 perturbation, and synthesize a unified asymptotic expansion.

Key insight: R_m = p(m)/p(m-1). Use the Rademacher-type asymptotic for p(n).
"""
import math
from functools import lru_cache
from decimal import Decimal, getcontext

# High precision for large-m work
getcontext().prec = 80

# ─── Partition function (exact integer) ───
@lru_cache(maxsize=None)
def p(n):
    if n < 0: return 0
    if n == 0: return 1
    total = 0
    k = 1
    while True:
        g1 = k * (3*k - 1) // 2
        g2 = k * (3*k + 1) // 2
        if g1 > n: break
        sign = (-1) ** (k + 1)
        total += sign * p(n - g1)
        if g2 <= n: total += sign * p(n - g2)
        k += 1
    return total

# ─── PART 1: Theoretical derivation of L ───
# 
# The leading Rademacher term gives:
#   p(n) ~ (1/(4n√3)) * exp(c√n)  where c = π√(2/3)
#
# More precisely, the k=1 Rademacher term is:
#   p(n) ~ (1/(π√2)) * d/dn [sinh(c√(n - 1/24)) / √(n - 1/24)]
#
# For large n, let μ = n - 1/24. Then:
#   p(n) ≈ (1/(4√3)) * (1/n) * exp(c√μ) * [1 + correction terms]
#
# Taking the ratio R_m = p(m)/p(m-1):
#   log R_m = log p(m) - log p(m-1)
#
# We need log p(n) to sufficient order. From the leading Rademacher term:
#   log p(n) ≈ c√(n - 1/24) - log(4n√3)/1 + sub-leading from sinh expansion
#
# Let's be precise. Define:
#   f(n) = c*√(n - 1/24) - log(n) - log(4√3) + corrections
#
# Then log R_m = f(m) - f(m-1)
#
# Let's expand f(n) and compute the difference.

c = math.pi * math.sqrt(2.0/3.0)  # π√(2/3)
print(f"c = π√(2/3) = {c:.12f}")
print(f"c² = 2π²/3 = {c**2:.12f}")
print(f"π²/6 = {math.pi**2/6:.12f}")

# ─── Exact expansion of log p(n) ───
# log p(n) ≈ c·√(n - 1/24) - log(n) - log(4√3)
#           + (higher terms from the Bessel function / sinh expansion)
#
# The k=1 Rademacher term more precisely:
#   p(n) = (2π)/(24n - 1)^(3/4) · (1/√2) · [d/dn stuff with I_{3/2}]
#
# Using the exact leading term:
#   p(n) ≈ (1/(4n√3)) · exp(c·√n) · (1 - c/(2√n) · 1/24 + ...)  [from expanding √(n-1/24)]
#        × (1 + sub-Bessel corrections)
#
# Actually, let me just use the standard result. The leading term of Rademacher is:
#   p(n) ≈ A(n) * exp(B(n))
# where
#   B(n) = π·√(2(n - 1/24)/3) = c·√(n - 1/24)
#   A(n) = 1/(4√3 · (n - 1/24))  [from the derivative of sinh/√ ...]
#
# Actually the exact Rademacher leading term is:
#   p(n) = (π/(6(24n-1))) · d/dn(sinh(...)/...) but let's work numerically.

# ─── PART 2: High-precision numerical C_m extraction ───
print("\n" + "="*70)
print("PART 2: High-precision C_m = m·(R_m - 1 - π/√(6m))")
print("="*70)

# Precompute partitions
print("Precomputing partition values...")
N_MAX = 2000
for n in range(N_MAX + 2):
    p(n)
print(f"Done. p({N_MAX}) has {len(str(p(N_MAX)))} digits.")

# Use high-precision logarithms via Decimal for large m
import mpmath
mpmath.mp.dps = 50  # 50 decimal places

def R_exact(m):
    """Exact ratio as mpmath high-precision float."""
    return mpmath.mpf(p(m)) / mpmath.mpf(p(m-1))

def C_m(m):
    """C_m = m * (R_m - 1 - π/√(6m))"""
    R = R_exact(m)
    pi = mpmath.pi
    correction = pi / mpmath.sqrt(6 * m)
    return float(m * (R - 1 - correction))

print(f"\n{'m':>6} {'R_m':>18} {'C_m':>14} {'ΔC':>10}")
prev_C = None
data_points = []
for m in list(range(30, 101, 10)) + list(range(100, 501, 50)) + list(range(500, 2001, 100)):
    R = float(R_exact(m))
    Cm = C_m(m)
    delta = Cm - prev_C if prev_C is not None else 0
    data_points.append((m, Cm))
    if m <= 100 or m % 100 == 0 or m >= 1900:
        print(f"{m:6d} {R:18.12f} {Cm:14.6f} {delta:10.6f}")
    prev_C = Cm

# ─── PART 3: Fit C_m to determine L and convergence rate ───
print("\n" + "="*70)
print("PART 3: Fitting C_m = L + α/√m + β/m + ...")
print("="*70)

import numpy as np

# Use data from m >= 200 for fitting
fit_data = [(m, cm) for m, cm in data_points if m >= 200]
ms = np.array([d[0] for d in fit_data], dtype=float)
cms = np.array([d[1] for d in fit_data], dtype=float)

# Model 1: C_m = L + α/√m
A1 = np.column_stack([np.ones_like(ms), 1.0/np.sqrt(ms)])
res1 = np.linalg.lstsq(A1, cms, rcond=None)
L1, alpha1 = res1[0]
resid1 = cms - A1 @ res1[0]
print(f"\nModel 1: C_m = L + α/√m")
print(f"  L = {L1:.8f}, α = {alpha1:.6f}")
print(f"  Max residual: {max(abs(resid1)):.2e}")

# Model 2: C_m = L + α/√m + β/m
A2 = np.column_stack([np.ones_like(ms), 1.0/np.sqrt(ms), 1.0/ms])
res2 = np.linalg.lstsq(A2, cms, rcond=None)
L2, alpha2, beta2 = res2[0]
resid2 = cms - A2 @ res2[0]
print(f"\nModel 2: C_m = L + α/√m + β/m")
print(f"  L = {L2:.8f}, α = {alpha2:.6f}, β = {beta2:.6f}")
print(f"  Max residual: {max(abs(resid2)):.2e}")

# Model 3: C_m = L + α/√m + β/m + γ/m^(3/2)
A3 = np.column_stack([np.ones_like(ms), 1.0/np.sqrt(ms), 1.0/ms, 1.0/ms**1.5])
res3 = np.linalg.lstsq(A3, cms, rcond=None)
L3, alpha3, beta3, gamma3 = res3[0]
resid3 = cms - A3 @ res3[0]
print(f"\nModel 3: C_m = L + α/√m + β/m + γ/m^(3/2)")
print(f"  L = {L3:.8f}, α = {alpha3:.6f}, β = {beta3:.6f}, γ = {gamma3:.6f}")
print(f"  Max residual: {max(abs(resid3)):.2e}")

# ─── PART 4: Theoretical derivation ───
print("\n" + "="*70)
print("PART 4: Theoretical derivation of L from log p(n) expansion")
print("="*70)

# Standard result: log p(n) = c√n - log(4n√3) + O(1/√n)
# where c = π√(2/3).
#
# More precisely, with the 1/24 correction:
# log p(n) ≈ c·√(n - 1/24) - log(4√3·(n - 1/24)) + ε(n)
#
# Let μ(n) = n - 1/24. Then:
# log p(n) ≈ c·√μ - log(4√3·μ) + O(1/√μ)
#
# Now R_m = exp(log p(m) - log p(m-1)).
# Δ log p = c·(√μ(m) - √μ(m-1)) - (log μ(m) - log μ(m-1))
#
# With μ(m) = m - 1/24, μ(m-1) = m - 1 - 1/24 = m - 25/24:
#
# √μ(m) - √μ(m-1) = √(m - 1/24) - √(m - 25/24)
#
# Let's expand around large m. Set x = m - 1/24. Then the second arg is x - 1.
# √x - √(x-1) = 1/(2√x) - 1/(8x^(3/2)) - 1/(16x^(5/2)) + ...
#
# Similarly: log(x) - log(x-1) = 1/x + 1/(2x²) + ...
#
# So: Δ log p ≈ c/(2√x) - c/(8x^(3/2)) - 1/x - 1/(2x²) + ...
#   where x = m - 1/24
#
# Now R_m = exp(Δ log p). Let's call Δ = Δ log p.
# Δ ≈ c/(2√x) + [-c/(8x^(3/2)) - 1/x] + ...
#
# R_m = 1 + Δ + Δ²/2 + ...
# The leading term: Δ₁ = c/(2√x)
# Next: Δ₂ = -c/(8x^(3/2)) - 1/x
#
# R_m ≈ 1 + c/(2√x) + [-c/(8x^(3/2)) - 1/x + c²/(8x)] + ...
#
# Wait, Δ²/2 at leading order = (c/(2√x))²/2 = c²/(8x)
#
# So R_m ≈ 1 + c/(2√x) + (c²/8 - 1)/x + O(x^(-3/2))
#
# Now c/(2√x) = π√(2/3)/(2√x) = π/(√6·√x) = π/√(6x).
# But the "standard" form uses π/√(6m), not π/√(6x) where x = m - 1/24.
#
# C_m = m·(R_m - 1 - π/√(6m))
#
# We need to reconcile π/√(6x) vs π/√(6m).
# π/√(6x) = π/√(6(m - 1/24)) = π/(√(6m)·√(1 - 1/(24m)))
#          ≈ π/√(6m) · (1 + 1/(48m) + ...)
#          = π/√(6m) + π/(48m·√(6m)) + ...
#
# So: R_m - 1 - π/√(6m) ≈ π/(48m·√(6m)) + (c²/8 - 1)/x + ...
#   ≈ π/(48m√(6m)) + (c²/8 - 1)/m + ...
#
# Therefore: 
#   C_m = m·(R_m - 1 - π/√(6m)) ≈ (c²/8 - 1) + π/(48√(6m)) + ...
#   = (π²/12 - 1) + O(1/√m)
#
# Wait! c² = 2π²/3, so c²/8 = 2π²/24 = π²/12.
# So: L = c²/8 - 1 = π²/12 - 1

L_theory = math.pi**2 / 12 - 1
print(f"\nDerived: L = π²/12 - 1 = {L_theory:.10f}")
print(f"Numerical L from Model 3 fit: {L3:.10f}")
print(f"Difference: {abs(L_theory - L3):.6e}")

# But wait — is this right? Let me verify numerically more carefully.

# ─── PART 5: Ultra-precise verification ───
print("\n" + "="*70)
print("PART 5: Verify L = π²/12 - 1 against numerical C_m")
print("="*70)

# If C_m = L + α/√m + ..., then C_m - L should go to 0 as m grows
# and √m · (C_m - L) should approach a constant α.
print(f"\n  L_theory = π²/12 - 1 = {L_theory:.10f}")
print(f"\n{'m':>6} {'C_m':>14} {'C_m - L_theory':>16} {'√m·(C_m-L)':>14}")

for m, cm in data_points:
    gap = cm - L_theory
    scaled = math.sqrt(m) * gap
    if m in [30, 50, 100, 200, 300, 500, 700, 1000, 1500, 2000]:
        print(f"{m:6d} {cm:14.6f} {gap:16.6f} {scaled:14.4f}")

# ─── PART 6: Check the 1/24 correction more carefully ───
print("\n" + "="*70)
print("PART 6: Full expansion including 1/24 correction")
print("="*70)

# My derivation above is approximate. Let me redo it more carefully.
# 
# log p(n) ≈ c·√(n - 1/24) - log(4√3) - log(n - 1/24) + sub-Bessel terms
#
# Actually the exact Rademacher k=1 term involves:
#   p(n) ≈ (2π/(24n-1)^(3/4)) · (1/√2) · I_{-3/2}(π√(2(24n-1)/3)/6)
# where I_{-3/2}(z) = √(2/(πz)) · cosh(z) [for the modified Bessel function]
#
# For large z: I_{-3/2}(z) ≈ e^z/√(2πz) · (1 + 3/(8z) + ...)
#
# Actually let me use the EXACT formula more carefully.
# The k=1 Rademacher term is:
#   p(n) = (π√2)/((24n-1)^(3/4)) · d/dn [I_{3/2}(λ_n) / λ_n^(3/2)]
# where λ_n = (π/6)√(2(24n-1)/3) = π√(2(24n-1))/(6√3) = (π/(6√3))·√(48n-2)
# Hmm, this is getting complicated. Let me just derive it from carefully expanding
# log p(n) to two more terms numerically.

# Use the ACTUAL partition values for a precise fit of log p(n).
print("\nFitting log p(n) = c·√(n - δ) - A·log(n - δ) - B + corrections")
print("Using exact partition values for n = 500..2000\n")

# First verify the standard leading form
ns_fit = list(range(500, 2001, 10))
log_ps = [float(mpmath.log(p(n))) for n in ns_fit]

# Model: log p(n) ≈ c·√(n-1/24) - log(n-1/24) - log(4√3) 
# Let's check residuals
log_4sqrt3 = math.log(4 * math.sqrt(3))
print(f"log(4√3) = {log_4sqrt3:.10f}")

residuals = []
for i, n in enumerate(ns_fit):
    mu = n - 1.0/24
    model = c * math.sqrt(mu) - math.log(mu) - log_4sqrt3
    resid = log_ps[i] - model
    residuals.append((n, resid))
    if n in [500, 700, 1000, 1500, 2000]:
        print(f"  n={n}: log p(n)={log_ps[i]:.8f}, model={model:.8f}, resid={resid:.6f}")

# The residuals should be O(1/√n). Let's fit them.
ns_r = np.array([r[0] for r in residuals], dtype=float)
rs_r = np.array([r[1] for r in residuals], dtype=float)

# Fit residual = d/√n + e/n
A_r = np.column_stack([1.0/np.sqrt(ns_r), 1.0/ns_r])
fit_r = np.linalg.lstsq(A_r, rs_r, rcond=None)
d_coeff, e_coeff = fit_r[0]
print(f"\n  Residual fit: {d_coeff:.6f}/√n + {e_coeff:.6f}/n")
print(f"  Max residual of fit: {max(abs(rs_r - A_r @ fit_r[0])):.2e}")

# ─── PART 7: Full derivation from the fitted log p(n) ───
print("\n" + "="*70)
print("PART 7: Deriving L from full log p(n) expansion")
print("="*70)

# With the correction terms:
# log p(n) = c·√μ - log μ - log(4√3) + d/√μ + e/μ + O(μ^(-3/2))
# where μ = n - 1/24
#
# Δ log p = [c·√μ_m - c·√μ_{m-1}] - [log μ_m - log μ_{m-1}] 
#         + [d/√μ_m - d/√μ_{m-1}] + [e/μ_m - e/μ_{m-1}]
#
# For the first group (√ difference):
# √μ_m - √μ_{m-1} = √(m-1/24) - √(m-25/24) 
#   = 1/(2√μ) - 1/(8μ^(3/2)) - 1/(16μ^(5/2)) + ...   [where μ = m - 1/24]
#
# For log difference:
# log(μ) - log(μ-1) = 1/μ + 1/(2μ²) + ...
#
# For d/√μ difference:
# 1/√μ - 1/√(μ-1) = -1/(2μ^(3/2)) + 3/(8μ^(5/2)) + ...
# So d-term difference = -d/(2μ^(3/2)) + O(μ^(-5/2))
#
# For e/μ difference:
# 1/μ - 1/(μ-1) = -1/μ² + O(μ^(-3))
# So e-term difference = -e/μ² + O(μ^(-3))
#
# Combining:
# Δ log p = c/(2√μ) + [-c/(8μ^(3/2)) - 1/μ - d/(2μ^(3/2))] + O(μ^(-2))
#         = c/(2√μ) - 1/μ - (c+4d)/(8μ^(3/2)) + O(μ^(-2))
#
# Now: R_m = exp(Δ) = 1 + Δ + Δ²/2 + ...
# Δ ≈ c/(2√μ) - 1/μ - (c+4d)/(8μ^(3/2))
# Δ² ≈ c²/(4μ) + ...
#
# R_m ≈ 1 + c/(2√μ) + (c²/8 - 1)/μ + O(μ^(-3/2))
#
# Note: the d term only enters at O(μ^(-3/2)), so L = c²/8 - 1 = π²/12 - 1 
# REGARDLESS of the sub-leading corrections!
#
# Now convert from μ = m - 1/24 to m:
# c/(2√μ) = c/(2√(m-1/24)) = c/(2√m) · 1/√(1-1/(24m))
#          ≈ c/(2√m) · (1 + 1/(48m) + ...)
#          = c/(2√m) + c/(96m^(3/2)) + ...
# = π/√(6m) + π/(96√(6)·m·√m) + ...
#
# C_m = m·(R_m - 1 - π/√(6m))
#     = m·[ c/(2√μ) - π/√(6m) + (c²/8 - 1)/μ + ... ]
#     = m·[ π/(96√6·m^(3/2)) + ... + (c²/8 - 1)/m + ... ]
#     = (c²/8 - 1) + π/(96√6·√m) + ...
#     = (π²/12 - 1) + O(1/√m)

L_exact = math.pi**2/12 - 1
print(f"\n  DERIVED: L = π²/12 - 1 = {L_exact:.12f}")
print(f"  This is approximately: {L_exact:.6f}")
print(f"  As a fraction: π² ≈ 9.8696, so π²/12 ≈ 0.8225, L ≈ -0.1775")

# Hmm, but Agent 6 found L ≈ -0.447. Let me check my derivation against the data more carefully.

# ─── CRITICAL CHECK ───
print("\n" + "="*70)
print("CRITICAL: Comparing L_theory vs actual C_m values")
print("="*70)

for m in [100, 200, 500, 1000, 1500, 2000]:
    cm = C_m(m)
    print(f"  m={m:5d}: C_m = {cm:.8f}")
    
print(f"\n  L = π²/12 - 1 = {L_exact:.8f}")
print(f"  L = -1/2      = {-0.5:.8f}")

# The C_m values at m=2000 are still around -0.39 to -0.40, not near -0.1775.
# So my derivation is WRONG somewhere. Let me recheck.
# 
# The issue might be: the pre-factor is not just 1/(4n√3) but involves n differently.
# 
# Let me re-derive from scratch using the actual Rademacher formula.

print("\n" + "="*70)
print("PART 8: Direct derivation from Rademacher k=1 term")
print("="*70)

# The EXACT k=1 Rademacher term is:
#   p(n) = (2π/(24n-1)) * d/dw [sinh(π√(2w/3))/π√(2w/3)]|_{w=n-1/24}
#
# Actually, the more standard form uses:
#   p(n) ~ (1/(2π√2)) * Σ_k A_k(n) * √k * d/dn [exp(c_k·√(n-1/24)) / (n-1/24)]
# where c_k = (π/k)√(2/3), A_k(n) is a Kloosterman-type sum.
#
# For k=1: A_1(n) = 1, c_1 = c = π√(2/3).
#
# The derivative is:
# d/dn [exp(c√μ)/μ] where μ = n - 1/24
# = exp(c√μ) * [c/(2μ√μ) · μ - exp...wait let me be more careful
# = exp(c√μ) · [c/(2√μ) · (1/μ) + exp(c√μ)·(-1/μ²)]  ... no
# d/dn [exp(c√μ)/μ] = [d/dn exp(c√μ)] · (1/μ) + exp(c√μ) · d/dn[1/μ]
#   = exp(c√μ)·c/(2√μ) · (1/μ) + exp(c√μ)·(-1/μ²)
#   = exp(c√μ)/μ · [c/(2√μ) - 1/μ]
#
# Hmm, let me look at this differently. Let me just numerically compute
# log p(n) very precisely and fit it.

# NUMERICAL APPROACH: compute log R_m directly from exact partition values
# and see what C_m actually converges to.
print("\nDirect numerical: extracting the TRUE asymptotics")
print(f"{'m':>6} {'C_m':>12} {'m·C_m':>12} {'C_m+0.5':>12} {'√m(C_m+0.5)':>12}")

# Maybe L = -1/2?
for m in [100, 200, 300, 500, 800, 1000, 1200, 1500, 1800, 2000]:
    cm = C_m(m)
    print(f"{m:6d} {cm:12.6f} {m*cm:12.2f} {cm+0.5:12.6f} {math.sqrt(m)*(cm+0.5):12.4f}")

# ─── Try L = -1/2 ───
print("\n--- Testing L = -1/2 ---")
print(f"{'m':>6} {'C_m + 1/2':>14} {'√m·(C_m+1/2)':>16} {'m·(C_m+1/2)':>14}")
for m in [200, 300, 500, 800, 1000, 1500, 2000]:
    cm = C_m(m)
    gap = cm + 0.5
    print(f"{m:6d} {gap:14.6f} {math.sqrt(m)*gap:16.4f} {m*gap:14.4f}")

# ─── Try other candidates ───
print("\n--- Testing various L candidates ---")
candidates = {
    "π²/12 - 1": math.pi**2/12 - 1,
    "-1/2": -0.5,
    "-π/(2√6)": -math.pi/(2*math.sqrt(6)),
    "1 - π²/12": 1 - math.pi**2/12,
    "-1 + c/2": -1 + c/2,  # c = π√(2/3)
    "c²/8 - 1": c**2/8 - 1,
    "-13/24": -13/24,
    "(1-c)/2": (1-c)/2,
    "1/2 - c/2": 0.5 - c/2,
}

# For each candidate, check if √m·(C_m - L_cand) converges
print(f"\n{'Candidate':>20} {'L':>10} {'√m·gap @ 500':>14} {'√m·gap @ 1000':>14} {'√m·gap @ 2000':>14} {'drift':>8}")
for name, L_cand in sorted(candidates.items(), key=lambda x: x[1]):
    gaps = []
    for m in [500, 1000, 2000]:
        cm = C_m(m)
        scaled_gap = math.sqrt(m) * (cm - L_cand)
        gaps.append(scaled_gap)
    drift = abs(gaps[2] - gaps[0]) / abs(gaps[0]) if gaps[0] != 0 else float('inf')
    print(f"{name:>20} {L_cand:10.6f} {gaps[0]:14.4f} {gaps[1]:14.4f} {gaps[2]:14.4f} {drift:8.4f}")

# ─── Maybe we need to go to much larger m ───
# The convergence is slow. Let me extrapolate using Richardson acceleration.
print("\n" + "="*70)
print("PART 9: Richardson extrapolation of C_m")
print("="*70)

# C_m = L + α/√m + β/m + ...
# Richardson: eliminate 1/√m term by combining C_m and C_{4m}
# C_m = L + α/√m + β/m + ...
# C_{4m} = L + α/(2√m) + β/(4m) + ...
# 2·C_{4m} - C_m = L + (2β/4 - β)/m + ... = L - β/(2m) + ...
# Wait: 2·C_{4m} - C_m = 2L + α/√m - L - α/√m + ... = L + O(1/m)
# Actually: 2·C_{4m} - C_m = 2(L + α/(2√m) + ...) - (L + α/√m + ...) = L + O(1/m)

# Richardson pairs
print("\n  Richardson extrapolation (eliminating 1/√m term):")
print(f"  {'m':>6} {'C_m':>12} {'C_4m':>12} {'Rich(m)':>12}")
for m in [100, 125, 200, 250, 500]:
    if 4*m <= N_MAX:
        cm = C_m(m)
        c4m = C_m(4*m)
        rich = 2*c4m - cm
        print(f"  {m:6d} {cm:12.6f} {c4m:12.6f} {rich:12.6f}")

# Double Richardson: use m, 4m, 16m to eliminate both 1/√m and 1/m
print("\n  Double Richardson (eliminating 1/√m and 1/m):")
for m in [50, 100, 125]:
    if 16*m <= N_MAX:
        c1 = C_m(m)
        c4 = C_m(4*m)
        c16 = C_m(16*m)
        # First round: r1 = 2*c4 - c1, r2 = 2*c16 - c4
        r1 = 2*c4 - c1
        r2 = 2*c16 - c4
        # r1 = L + O(1/m), r2 = L + O(1/(4m))
        # Second round: 4*r2 - r1 = 3L + O(1/m²)... let me think
        # r1 = L + γ/m + ..., r2 = L + γ/(4m) + ...
        # (4r2 - r1)/3 = L + O(1/m²)
        double_rich = (4*r2 - r1) / 3
        print(f"  m={m:4d}: C_m={c1:.6f}, C_4m={c4:.6f}, C_16m={c16:.6f}")
        print(f"          Rich1: {r1:.8f}, Rich2: {r2:.8f}, Double: {double_rich:.8f}")

print("\n" + "="*70)
print("PART 10: Test the -1 perturbation")
print("="*70)

# a(n) = p(n-2), so R_n^(a) = a(n)/a(n-1) = p(n-2)/p(n-3)
# But Round 1 said a(n) = p(n-1) - 1. Agent 2 (me in Round 2) refuted this and showed a(n) = p(n-2).
# Agent 6 claims a(n) = p(n-1) - 1. Who is right?

# Let me verify AGAIN with the given terms
known = [0, 0, 1, 1, 2, 3, 5, 7, 11, 15, 22, 30, 42, 56, 77, 101, 135, 176, 231, 297]

print("\nVerification of identity:")
print(f"{'n':>4} {'given':>8} {'p(n-2)':>8} {'p(n-1)-1':>10}")
for n in range(len(known)):
    pn2 = p(n-2) if n >= 2 else 0
    pn1m1 = p(n-1) - 1 if n >= 1 else -1
    match_a = "✓" if pn2 == known[n] else "✗"
    match_b = "✓" if pn1m1 == known[n] else "✗"
    print(f"{n:4d} {known[n]:8d} {pn2:8d} {match_a}  {pn1m1:10d} {match_b}")

# Now test the perturbation: R'_m = (p(m)-1)/(p(m-1)-1) vs R_m = p(m)/p(m-1)
# If a(n) = p(n-2), then R_n = p(n-2)/p(n-3) and there's NO -1 perturbation.
# But let's check the Agent 6 question anyway:
print("\n  Perturbation test: R'_m = (p(m)-1)/(p(m-1)-1) vs R_m = p(m)/p(m-1)")
print(f"  {'m':>6} {'R_m':>14} {'R_m_pert':>14} {'diff':>14}")
for m in [10, 20, 50, 100, 500, 1000, 2000]:
    Rm = float(mpmath.mpf(p(m)) / mpmath.mpf(p(m-1)))
    Rm_pert = float(mpmath.mpf(p(m)-1) / mpmath.mpf(p(m-1)-1))
    diff = Rm - Rm_pert
    print(f"  {m:6d} {Rm:14.10f} {Rm_pert:14.10f} {diff:14.2e}")

# Check strict decrease of the PERTURBATION ratio
print("\n  Strict decrease of R'_m = (p(m)-1)/(p(m-1)-1):")
pert_violations = []
for m in range(4, N_MAX + 1):
    if p(m-1) <= 1 or p(m-2) <= 1:
        continue
    Rm = (p(m)-1) / (p(m-1)-1)
    Rm_prev = (p(m-1)-1) / (p(m-2)-1)
    if Rm > Rm_prev:
        pert_violations.append((m, float(Rm_prev), float(Rm)))

print(f"  Violations of R'_m < R'_(m-1) for m in [4, {N_MAX}]: {len(pert_violations)}")
if pert_violations:
    for v in pert_violations[:15]:
        m, rp, rc = v
        print(f"    m={m}: R'({m-1})={rp:.10f} → R'({m})={rc:.10f}")
    if len(pert_violations) > 15:
        print(f"    ... last violation at m={pert_violations[-1][0]}")

print("\n=== DONE ===")
