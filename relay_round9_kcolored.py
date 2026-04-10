"""
Round 9 — Correcting the k-colored partition prefactor.
"""
import math
from functools import lru_cache
import mpmath
mpmath.mp.dps = 60

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

@lru_cache(maxsize=None)
def pk(n, k):
    if n < 0: return 0
    if n == 0: return 1
    total = 0
    for j in range(1, n+1):
        s1 = sum(d for d in range(1, j+1) if j % d == 0)
        total += k * s1 * pk(n - j, k)
    return total // n

# For k-colored partitions:
# p_k(n) ~ C_k * n^{-(k+1)/2} * exp(c_k * √n)   [Meinardus theorem]
# where c_k = π√(2k/3)
# 
# BUT: the prefactor involves n^{-(k+1)/2} multiplied by more terms.
# Actually, for prod(1-x^n)^{-k}, the standard asymptotic (Meinardus 1954) gives:
#   p_k(n) ~ A_k * n^{-α_k} * exp(c_k * √n)
# where α_k = (k+1)/2 and A_k is a constant.
#
# BUT the exponent might differ from -(k+1)/2 for the EXACT leading Rademacher analogue.
# For k=1: α_1 = 1 (standard). For k=2: should be α_2 = 3/2.
#
# Let's determine the prefactor NUMERICALLY by fitting log p_k(n).

K_MAX = 500
for n in range(K_MAX + 2):
    pk(n, 2)

print("="*80)
print("Determining the prefactor exponent for k-colored partitions")
print("="*80)

for kval in [1, 2]:
    c_k = math.pi * math.sqrt(2*kval/3.0)
    print(f"\n--- k = {kval}, c_k = {c_k:.10f} ---")
    
    # Fit: log p_k(n) = c_k*√n + α*log(n) + const + sub-leading
    # Extract α from: [log p_k(n) - c_k*√n] vs log(n)
    
    # Two-point estimate of α:
    ns = [200, 300, 400, 500] if kval <= 2 else [100, 200, 300]
    for i in range(len(ns)-1):
        n1, n2 = ns[i], ns[i+1]
        if kval == 1:
            logp1 = float(mpmath.log(p(n1)))
            logp2 = float(mpmath.log(p(n2)))
        else:
            logp1 = float(mpmath.log(pk(n1, kval)))
            logp2 = float(mpmath.log(pk(n2, kval)))
        
        # logp = c_k√n + α*ln(n) + const + O(1/√n)
        # Difference: logp2 - logp1 = c_k(√n2 - √n1) + α*(ln n2 - ln n1) + O(1/√n1)
        # α ≈ (logp2 - logp1 - c_k*(√n2 - √n1)) / (ln n2 - ln n1)
        delta_logp = logp2 - logp1
        delta_sqrt = math.sqrt(n2) - math.sqrt(n1)
        delta_ln = math.log(n2) - math.log(n1)
        
        alpha_est = (delta_logp - c_k * delta_sqrt) / delta_ln
        print(f"  n1={n1}, n2={n2}: α_est = {alpha_est:.6f}")
    
    # Expected: α = -(k+1)/2 for Meinardus
    print(f"  Expected α = -(k+1)/2 = {-(kval+1)/2:.1f}")

# The key insight: for k-colored partitions, the Meinardus theorem gives
# p_k(n) ~ A_k * n^{-(k+1)/4} * exp(c_k*√n)
# Wait, let me look this up more carefully.
# Actually the standard Meinardus result for prod(1-x^m)^{-alpha} gives
# an exponent related to the Dirichlet series of α*σ_0(n) at s=0.
# For prod(1-x^m)^{-k}: the "Dirichlet coefficient" is b_m = k for all m.
# The Dirichlet series is k*ζ(s). At s=0: k*ζ(0) = -k/2.
# The exponent of n in the asymptotic is -b_0/2 - 3/4 where b_0 = sum_{m=1}^∞ b_m/m = ???
# 
# Hmm, Meinardus formula: for f(x) = prod(1-x^m)^{-a_m}:
# log f(x) near x→1: ~ Γ(α+1)ζ(α+1)Γ(1-α) * (1-x)^{-α} where α=1 for our case
# And the coefficient: p(n) ~ (some function of n) * exp(...)
# 
# Let me just fit log p_k(n) more carefully.

import numpy as np

print("\n" + "="*80)
print("Precise prefactor fitting via least squares")
print("="*80)

for kval in [1, 2]:
    c_k = math.pi * math.sqrt(2*kval/3.0)
    
    ns_fit = list(range(200, 501, 5))
    logps = []
    for n in ns_fit:
        if kval == 1:
            logps.append(float(mpmath.log(p(n))))
        else:
            logps.append(float(mpmath.log(pk(n, kval))))
    
    ns_arr = np.array(ns_fit, dtype=float)
    logps_arr = np.array(logps)
    
    # Model: log p_k(n) = c_k*√n + α*log(n) + β + γ/√n
    sqrts = np.sqrt(ns_arr)
    logs = np.log(ns_arr)
    inv_sqrts = 1.0/sqrts
    
    # Subtract known exponential
    y = logps_arr - c_k * sqrts
    
    # Fit: y = α*log(n) + β + γ/√n
    A = np.column_stack([logs, np.ones_like(logs), inv_sqrts])
    result = np.linalg.lstsq(A, y, rcond=None)
    alpha_fit, beta_fit, gamma_fit = result[0]
    resid = y - A @ result[0]
    
    print(f"\nk={kval}: log p_k(n) = {c_k:.6f}√n + α·ln(n) + β + γ/√n")
    print(f"  α = {alpha_fit:.8f} (expected -(k+1)/2 = {-(kval+1)/2})")
    print(f"  β = {beta_fit:.8f}")
    print(f"  γ = {gamma_fit:.8f}")
    print(f"  Max residual: {max(abs(resid)):.2e}")

# Now with the correct prefactor, derive L_k
print("\n" + "="*80)
print("Deriving L_k from the fitted prefactor exponent")
print("="*80)

for kval in [1, 2]:
    c_k = math.pi * math.sqrt(2.0*kval/3.0)
    
    # From the fit above, the exponent α_k is the coefficient of -ln(n).
    # For k=1: α ≈ -1 (so -α = 1)
    # For k=2: α ≈ -3/2 (so -α = 3/2)
    
    # L_k = c_k²/8 + α_k
    # where α_k is the prefactor exponent (negative of what we fitted,
    # since we fitted the coefficient of +ln(n), and the contribution to
    # the ratio is -Δ(α_k·ln m) = -α_k/m)
    # Hmm, let me be precise.
    #
    # log p_k(m) ≈ c_k√m + α_k·ln m + const + ...
    # where α_k is what we fitted (expected to be -(k+1)/2).
    #
    # Δ log p_k = c_k/(2√m) + α_k/m + ...  [from Δ(ln m) = 1/m + ...]
    # Wait: α_k·(ln m - ln(m-1)) = α_k·(1/m + ...), but α_k is negative!
    # So: Δ log p_k = c_k/(2√m) + α_k/m + ...
    # 
    # Then R = exp(Δ) = 1 + c_k/(2√m) + (c_k²/8 + α_k)/m + ...
    # So: L_k = c_k²/8 + α_k
    
    L_k = c_k**2/8 + (-(kval+1)/2)  # Using theoretical α_k = -(k+1)/2
    print(f"\nk={kval}:")
    print(f"  c_k²/8 = {c_k**2/8:.10f}")
    print(f"  α_k (prefactor) = {-(kval+1)/2:.1f}")
    print(f"  L_k = c_k²/8 + α_k = {L_k:.10f}")
    print(f"  c_k² = 2kπ²/3 = {2*kval*math.pi**2/3:.10f}")
    print(f"  c_k²/8 = kπ²/12 = {kval*math.pi**2/12:.10f}")
    print(f"  So L_k = kπ²/12 - (k+1)/2 = {kval*math.pi**2/12 - (kval+1)/2:.10f}")

# Now numerically verify L_2 using the data
print("\n" + "="*80)
print("Numerical verification with CORRECT leading coefficient for k=2")
print("="*80)

# For k=2: c_2 = π√(4/3), but the RATIO has leading term c_2/(2√m)
# The prefactor is m^{-3/2}, so Δ(prefactor) contributes -3/(2m)
# L_2 = c_2²/8 - 3/2 = (2π²/3)·2/8 - 3/2 = π²/6 - 3/2

c2 = math.pi * math.sqrt(4.0/3.0)
L_2_theory = math.pi**2/6 - 3.0/2
print(f"  L_2 = π²/6 - 3/2 = {L_2_theory:.10f}")

# But wait — for k=2, the Meinardus prefactor might NOT be n^{-(k+1)/2} = n^{-3/2}.
# It could involve a different exponent. Let me check numerically.
# The ratio R_m^(2) = pk(m,2)/pk(m-1,2).
# We compute C_m = m·(R - 1 - c_2/(2√m)).
# If C_m → L_2, good. But the data showed C_m → ~0.37, not 0.145.
# So the prefactor exponent is NOT -3/2.

# What prefactor gives L_2 ≈ 0.37?
# L_2 = c_2²/8 + α_2 → α_2 = L_2 - c_2²/8
# c_2²/8 = 4π²/(3·8) = π²/6 ≈ 1.6449
# If L_2 ≈ 0.37, then α_2 = 0.37 - 1.645 = -1.275
# So the effective prefactor exponent is about -1.275, not -1.5.

# Let me fit α_2 more precisely using the numerical data
print(f"\n  Extracting effective α_2 from ratio data:")
print(f"  C_m = m·(R_m - 1 - c_2/(2√m)) should → c_2²/8 + α_2")

c2_sq_8 = c2**2/8
Cm_data = []
for m in [200, 300, 400, 500]:
    R2 = float(mpmath.mpf(pk(m, 2)) / mpmath.mpf(pk(m-1, 2)))
    Cm = m * (R2 - 1 - c2/(2*math.sqrt(m)))
    Cm_data.append((m, Cm))
    print(f"    m={m}: C_m = {Cm:.8f}")

# C_m converges slowly. Use Richardson extrapolation to estimate the limit.
# C_m = L + α/√m + ...
# Using m1=200, m2=500:
f1 = Cm_data[0][1]  # m=200
f4 = Cm_data[3][1]  # m=500
# This isn't 4× apart. Use 200 and 400.
f200 = [cm for m, cm in Cm_data if m == 200][0]
f400 = [cm for m, cm in Cm_data if m == 400][0]
# C(m) ≈ L + a/√m → 2C(4m) - C(m) ≈ L (but 400 ≠ 4×200)
# Use the general formula: C(m1), C(m2) → L ≈ [√m2·C(m2) - √m1·C(m1)]/(√m2 - √m1)
# This eliminates the 1/√m term.
# Actually: C = L + a/√m → √m·C = L√m + a → slope = L, intercept = a
# So: L = (√m2·C2 - √m1·C1)/(√m2 - √m1) ... no that gives (√m2·L + a - √m1·L - a)/(√m2-√m1) = L. 
# Hmm that's the slope interpretation. Let me just fit.
import numpy as np
ms_k2 = np.array([d[0] for d in Cm_data], dtype=float)
cs_k2 = np.array([d[1] for d in Cm_data])
A_k2 = np.column_stack([np.ones_like(ms_k2), 1.0/np.sqrt(ms_k2)])
fit_k2 = np.linalg.lstsq(A_k2, cs_k2, rcond=None)
L_2_fit, slope_k2 = fit_k2[0]
print(f"\n  Linear fit: C_m = {L_2_fit:.8f} + {slope_k2:.4f}/√m")
print(f"  → L_2 (extrapolated) = {L_2_fit:.8f}")

alpha_2_eff = L_2_fit - c2_sq_8
print(f"  c_2²/8 = {c2_sq_8:.8f}")
print(f"  → effective prefactor α_2 = L_2 - c_2²/8 = {alpha_2_eff:.8f}")
print(f"  → expected if α_2 = -3/2: L_2 = {c2_sq_8 - 1.5:.8f}")
print(f"  → expected if α_2 = -5/4: L_2 = {c2_sq_8 - 1.25:.8f}")
print(f"  → expected if α_2 = -1: L_2 = {c2_sq_8 - 1:.8f}")

# Check: for k=2, the Meinardus exponent.
# Meinardus theorem for prod(1-x^m)^{-a_m} with a_m = k:
# Dirichlet series: D(s) = k·Σ m^{-s} = k·ζ(s)
# D(0) = k·ζ(0) = -k/2
# The exponent of n in asymptotic is: -(D(0)/2 + 1/4) = -(-k/4 + 1/4) = (k-1)/4
# Wait, the Meinardus formula gives:
# p_k(n) ~ C * n^{-(D(0)/2 + 1/4)} * exp(...)
# (see Andrews, "The Theory of Partitions", Ch. 6.2)
# D(0) = -k/2
# Exponent = -(−k/4 + 1/4) = (k−1)/4
# Hmm that gives a POSITIVE exponent for k≥2. Let me recheckcl.

# Standard Meinardus (see e.g. Granville/Soundararajan or Andrews):
# If f(x) = prod_{m=1}^∞ (1-x^m)^{-a_m} = Σ r(n) x^n,
# with D(s) = Σ a_m m^{-s}, having abscissa of convergence α > 0,
# Then: r(n) ~ C_0 * n^κ * exp(n^{α/(α+1)} * stuff)
# where κ = (D(0) - 1 - α/2) / (α + 1)
# For our case: a_m = k, D(s) = k·ζ(s), α = 1.
# D(0) = k·ζ(0) = -k/2
# κ = (-k/2 - 1 - 1/2) / 2 = (-k/2 - 3/2) / 2 = -(k+3)/4
# 
# So: p_k(n) ~ C_0 * n^{-(k+3)/4} * exp(c_k√n)
# For k=1: exponent of n = -(4)/4 = -1. ✓ (matches the standard p(n) ~ n^{-1}*exp)
# For k=2: exponent = -5/4
# For k=3: exponent = -3/2

# So the prefactor is n^{-(k+3)/4}, NOT n^{-(k+1)/2}!

print(f"\n" + "="*80)
print(f"CORRECTED: Meinardus exponent is -(k+3)/4, not -(k+1)/2")
print(f"="*80)
print(f"  p_k(n) ~ C_k · n^{{-(k+3)/4}} · exp(c_k√n)")
print(f"  k=1: exponent = -1.00 (matches standard)")
print(f"  k=2: exponent = -1.25")
print(f"  k=3: exponent = -1.50")

# Redo the L_k derivation:
# log p_k(m) ≈ c_k√m - (k+3)/4 · ln m + const + ...
# Δ log p_k = c_k/(2√m) - (k+3)/(4m) + ...
# R = exp(Δ) = 1 + c_k/(2√m) + [c_k²/8 - (k+3)/4]/m + ...
# L_k = c_k²/8 - (k+3)/4 = kπ²/12 - (k+3)/4

for kval in [1, 2, 3]:
    c_k = math.pi * math.sqrt(2.0*kval/3.0)
    L_k = c_k**2/8 - (kval+3)/4.0
    print(f"\n  k={kval}: L_k = kπ²/12 - (k+3)/4 = {kval}·{math.pi**2/12:.6f} - {(kval+3)/4:.4f} = {L_k:.8f}")

# Numerical check for k=2:
L_2_meinardus = 2*math.pi**2/12 - 5/4
print(f"\n  For k=2: L_2 = π²/6 - 5/4 = {L_2_meinardus:.8f}")
print(f"  vs fitted L_2 = {L_2_fit:.8f}")
print(f"  gap = {L_2_fit - L_2_meinardus:.6f}")

# Hmm, the fitted value is ~0.39, Meinardus gives 0.3949. Reasonably close!
# The gap is because the fit hasn't fully converged (only up to m=500).

# Let me do Richardson on the k=2 data
print(f"\n  Richardson extrapolation for L_2:")
# Need C(m) at m and 4m
for m_base in [50, 100]:
    m1, m4 = m_base, 4*m_base
    if m4 <= 500:
        R1 = float(mpmath.mpf(pk(m1, 2)) / mpmath.mpf(pk(m1-1, 2)))
        R4 = float(mpmath.mpf(pk(m4, 2)) / mpmath.mpf(pk(m4-1, 2)))
        C1 = m1 * (R1 - 1 - c2/(2*math.sqrt(m1)))
        C4 = m4 * (R4 - 1 - c2/(2*math.sqrt(m4)))
        rich = 2*C4 - C1
        print(f"    m={m_base}: C({m_base})={C1:.6f}, C({m4})={C4:.6f}, Rich={rich:.8f}")
        print(f"    vs L_2 (Meinardus) = {L_2_meinardus:.8f}")

# ═══════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════
print(f"\n" + "="*80)
print(f"ROUND 9 FINAL: Universal k-colored partition formula")
print(f"="*80)
print(f"""
CONJECTURE H (k-Colored Partition Ratio Universality):
  
  For p_k(n) = coefficients of prod_m (1-q^m)^{{-k}},
  the ratio R_m^(k) = p_k(m)/p_k(m-1) satisfies:
  
  R_m^{{(k)}} = 1 + (π/√(6m))·√k + (kπ²/12 - (k+3)/4)·(1/m) + O(m^{{-3/2}})
  
  Equivalently: L_k = kπ²/12 - (k+3)/4
  
  Using the Meinardus exponent -(k+3)/4 for the prefactor.
  
  For k=1: L_1 = π²/12 - 1 ≈ {math.pi**2/12 - 1:.6f}  ✓
  For k=2: L_2 = π²/6 - 5/4 ≈ {2*math.pi**2/12 - 5/4:.6f}  [to be verified]
  For k=3: L_3 = π²/4 - 3/2 ≈ {3*math.pi**2/12 - 6/4:.6f}  [to be verified]
""")

print("=== DONE ===")
