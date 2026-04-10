"""
Round 7 — Deriving the O(m^{-2}) coefficient β theoretically.

We need to carry the expansion of R_m = exp(Δ log p) to fourth order.
"""
import math
import mpmath
mpmath.mp.dps = 60

c = math.pi * math.sqrt(2.0/3.0)  # π√(2/3) = π√6/3
L = math.pi**2/12 - 1
alpha = (math.pi**2 - 24)*(4*math.pi**2 - 9)/(144*math.pi*math.sqrt(6))

# ─── Full expansion to O(ν^{-2}) ───
# We have (with ν = m - 1/24):
#
# Δ log p = Σ_k a_k · ν^{-k/2}  (for k = 1, 2, 3, 4, ...)
#
# Term-by-term contributions:
#
# 1. From c√μ: c·(√ν - √(ν-1))
#    √ν - √(ν-1) = 1/(2√ν) + 1/(8ν^{3/2}) + 1/(16ν^{5/2}) + 5/(128ν^{7/2}) + ...
#    So contributes: c/(2√ν) + c/(8ν^{3/2}) + c/(16ν^{5/2}) + ...
#
# 2. From -ln μ: -(ln ν - ln(ν-1)) = -(1/ν + 1/(2ν²) + 1/(3ν³) + ...)
#    Contributes: -1/ν - 1/(2ν²) - ...
#
# 3. From -1/(c√μ): Δ[-1/(c√μ)] = (1/c)(1/√(ν-1) - 1/√ν)
#    1/√(ν-1) - 1/√ν = 1/(2ν^{3/2}) + 3/(8ν^{5/2}) + ...
#    Contributes: 1/(2cν^{3/2}) + 3/(8cν^{5/2}) + ...
#
# 4. From -1/(2c²μ): Δ[-1/(2c²μ)] = (1/(2c²))(1/(ν-1) - 1/ν)
#    = (1/(2c²)) · 1/(ν²-ν) ≈ 1/(2c²ν²) + ...
#    Contributes: 1/(2c²ν²) + ...
#
# Collecting by power of ν:
# a₁ = c/2           (ν^{-1/2})
# a₂ = -1            (ν^{-1})
# a₃ = c/8 + 1/(2c)  (ν^{-3/2})
# a₄ = -1/2 + 1/(2c²) (ν^{-2})
#    The -1/2 from term 2, and 1/(2c²) from term 4.

a1 = c/2
a2 = -1
a3 = c/8 + 1/(2*c)
a4 = -1/2 + 1/(2*c**2)

print(f"Expansion coefficients of Δ log p:")
print(f"  a₁ = c/2 = {a1:.10f}")
print(f"  a₂ = -1")  
print(f"  a₃ = c/8 + 1/(2c) = {a3:.10f}")
print(f"  a₄ = -1/2 + 1/(2c²) = {a4:.10f}")

# Now exponentiate: R = exp(Δ) = 1 + Σ_k b_k ν^{-k/2}
# Using: exp(x) = 1 + x + x²/2 + x³/6 + x⁴/24
# with x = a₁ν^{-1/2} + a₂ν^{-1} + a₃ν^{-3/2} + a₄ν^{-2}

# b₁ = a₁
b1 = a1

# b₂ = a₂ + a₁²/2
b2 = a2 + a1**2/2

# b₃ = a₃ + a₁a₂ + a₁³/6
b3 = a3 + a1*a2 + a1**3/6

# b₄ = a₄ + a₁a₃ + a₂²/2 + a₁²a₂/2 + a₁⁴/24
b4 = a4 + a1*a3 + a2**2/2 + a1**2*a2/2 + a1**4/24

print(f"\nExpansion coefficients of R_m in ν^{{-k/2}}:")
print(f"  b₁ = {b1:.10f}  (should be π/√6 = {math.pi/math.sqrt(6):.10f})")
print(f"  b₂ = {b2:.10f}  (should be π²/12-1 = {L:.10f})")
print(f"  b₃ = {b3:.10f}  (D_ν)")
print(f"  b₄ = {b4:.10f}  (E_ν)")

# ─── Convert from ν to m ───
# ν = m - 1/24
# ν^{-1/2} = m^{-1/2}(1 + 1/(48m) + 3/(2·48²·m²) + ...)
# ν^{-1} = m^{-1}(1 + 1/(24m) + 1/(24²m²) + ...)
# ν^{-3/2} = m^{-3/2}(1 + 3/(48m) + ...) = m^{-3/2}(1 + 1/(16m) + ...)
# ν^{-2} = m^{-2}(1 + 2/(24m) + ...) = m^{-2}(1 + 1/(12m) + ...)

# R_m = 1 + b₁/√m + [b₁/(48m^{3/2}) + b₂/m] + [b₁·3/(2·48²·m^{5/2}) + b₂/(24m²) + b₃/m^{3/2}] + ...
# Let me be more systematic.

# R_m = 1 + B₁m^{-1/2} + B₂m^{-1} + B₃m^{-3/2} + B₄m^{-2} + ...
# where:
# B₁ = b₁
B1 = b1

# B₂ = b₂
B2 = b2

# B₃ = b₃ + b₁/(48)  [from ν^{-1/2} × (1/(48m)) contribution]
B3 = b3 + b1/48

# B₄ = b₄ + b₂/(24) + b₁·3/(2·48²)  [from ν^{-1} × 1/(24m) and ν^{-1/2} × second correction]
# Actually let me be more careful.
# ν^{-1/2} = m^{-1/2}(1 + s/(48m) + t/(48²m²)...) with s=1 (already used)
# The ν^{-1/2} expansion: ν^{-1/2} = m^{-1/2}·Σ (1/24)^k·binom(-1/2,k)·m^{-k}
# (1-x)^{-1/2} = 1 + x/2 + 3x²/8 + ... with x = 1/(24m)
# So ν^{-1/2} = m^{-1/2}(1 + 1/(48m) + 3/(8·576·m²) + ...)
# = m^{-1/2}(1 + 1/(48m) + 1/(1536·m²) + ...)

# Similarly ν^{-1} = m^{-1}(1-1/(24m))^{-1} = m^{-1}(1 + 1/(24m) + 1/(576m²) + ...)
# ν^{-3/2} = m^{-3/2}(1 + 3/(2·24m) + ...) = m^{-3/2}(1 + 1/(16m) + ...)

# Contributions to B₃ (m^{-3/2}):
# From b₁·ν^{-1/2}: b₁ · m^{-1/2} · 1/(48m) = b₁/(48) · m^{-3/2}
# From b₃·ν^{-3/2}: b₃ · m^{-3/2}
# Total: B₃ = b₃ + b₁/48  ✓

# Contributions to B₄ (m^{-2}):
# From b₁·ν^{-1/2}: b₁ · m^{-1/2} · 1/(1536m²) → m^{-5/2}, not m^{-2}
#   Wait, that's m^{-1/2} · m^{-2} = m^{-5/2}. No contribution to B₄.
# From b₂·ν^{-1}: b₂ · m^{-1} · 1/(24m) = b₂/24 · m^{-2}
# From b₃·ν^{-3/2}: m^{-3/2} terms → need m^{-1/2} correction from ν^{-3/2}
#   b₃ · m^{-3/2} · 1/(16m) = b₃/(16) · m^{-5/2}. Not m^{-2}.
# From b₄·ν^{-2}: b₄ · m^{-2}
# Total: B₄ = b₄ + b₂/24

B4 = b4 + b2/24

print(f"\nExpansion coefficients of R_m in m^{{-k/2}}:")
print(f"  B₁ = {B1:.10f}  (= π/√6)")
print(f"  B₂ = {B2:.10f}  (= π²/12 - 1 = L)")
print(f"  B₃ = {B3:.10f}  (= α)")
print(f"  B₄ = {B4:.10f}  (= β)")

print(f"\nComparison:")
print(f"  L_theory  = {L:.10f},  B₂ = {B2:.10f},  match = {abs(L-B2) < 1e-12}")
print(f"  α_theory  = {alpha:.10f},  B₃ = {B3:.10f},  match = {abs(alpha-B3) < 1e-10}")
print(f"  β_theory  = {B4:.10f}  (this is the NEW prediction)")

# ─── Simplify β algebraically ───
# B₄ = b₄ + b₂/24
# b₄ = a₄ + a₁a₃ + a₂²/2 + a₁²a₂/2 + a₁⁴/24
# b₂ = a₂ + a₁²/2 = -1 + c²/8
# So b₂/24 = (-1 + c²/8)/24

# a₄ = -1/2 + 1/(2c²)
# a₁a₃ = (c/2)(c/8 + 1/(2c)) = c²/16 + 1/4
# a₂² = 1
# a₁²a₂/2 = (c²/4)(-1)/2 = -c²/8
# a₁⁴/24 = c⁴/(16·24) = c⁴/384

print(f"\nBreakdown of b₄:")
print(f"  a₄ = {a4:.10f}")
print(f"  a₁a₃ = {a1*a3:.10f}")
print(f"  a₂²/2 = {a2**2/2:.10f}")
print(f"  a₁²a₂/2 = {a1**2*a2/2:.10f}")
print(f"  a₁⁴/24 = {a1**4/24:.10f}")
print(f"  Sum (b₄) = {b4:.10f}")
print(f"  b₂/24 = {b2/24:.10f}")
print(f"  B₄ = b₄ + b₂/24 = {B4:.10f}")

# ─── Numerical verification of β ───
from functools import lru_cache

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

for n in range(4002):
    p(n)

print(f"\n{'='*80}")
print(f"Numerical verification of β = {B4:.10f}")
print(f"{'='*80}")
print(f"{'m':>6} {'m²·(R-1-A/√m-L/m-α/m^1.5)':>30} {'β_theory':>12} {'error':>12}")

for m in [200, 300, 500, 1000, 1500, 2000, 3000, 4000]:
    R = float(mpmath.mpf(p(m))/mpmath.mpf(p(m-1)))
    residual = R - 1 - math.pi/math.sqrt(6*m) - L/m - alpha/m**1.5
    beta_num = residual * m**2
    err = beta_num - B4
    print(f"{m:6d} {beta_num:30.10f} {B4:12.10f} {err:12.6f}")

# ─── Express β in terms of π ───
# B₄ = b₄ + b₂/24
# Let's collect all terms symbolically.
# With c² = 2π²/3:
#
# a₁²/2 = c²/8 = π²/12
# a₁a₃ = c²/16 + 1/4
# a₁²a₂/2 = -c²/8 = -π²/12
# a₁⁴/24 = c⁴/384 = (2π²/3)²/384 = 4π⁴/(9·384) = π⁴/864
# a₂²/2 = 1/2
# a₄ = -1/2 + 1/(2c²) = -1/2 + 3/(4π²)
#
# b₄ = (-1/2 + 3/(4π²)) + (c²/16 + 1/4) + 1/2 + (-c²/8) + c⁴/384
#     = 3/(4π²) + 1/4 + c²/16 - c²/8 + c⁴/384
#     = 3/(4π²) + 1/4 - c²/16 + c⁴/384
#     = 3/(4π²) + 1/4 - π²/24 + π⁴/864
#
# Wait: c²/16 = 2π²/(3·16) = π²/24. And c²/8 = π²/12.
# c²/16 - c²/8 = π²/24 - π²/12 = -π²/24
# c⁴/384 = (2π²/3)²/384 = 4π⁴/9/384 = 4π⁴/3456 = π⁴/864

# So: b₄ = 3/(4π²) + 1/4 - π²/24 + π⁴/864
b4_formula = 3/(4*math.pi**2) + 1/4 - math.pi**2/24 + math.pi**4/864
print(f"\nb₄ via formula = {b4_formula:.10f}, direct = {b4:.10f}, match = {abs(b4_formula-b4) < 1e-12}")

# b₂/24 = (c²/8 - 1)/24 = (π²/12 - 1)/24 = (π² - 12)/288
b2_24 = (math.pi**2 - 12)/288
print(f"b₂/24 via formula = {b2_24:.10f}, direct = {b2/24:.10f}, match = {abs(b2_24-b2/24) < 1e-12}")

# B₄ = b₄ + b₂/24 = 3/(4π²) + 1/4 - π²/24 + π⁴/864 + (π²-12)/288
#     = 3/(4π²) + 1/4 - π²/24 + π⁴/864 + π²/288 - 1/24
#     = 3/(4π²) + (1/4 - 1/24) + (-π²/24 + π²/288) + π⁴/864
#     = 3/(4π²) + 5/24 + π²(-12/288 + 1/288) + π⁴/864
#     = 3/(4π²) + 5/24 - 11π²/288 + π⁴/864

# Wait: -π²/24 + π²/288 = π²(-12/288 + 1/288) = -11π²/288.
B4_formula = 3/(4*math.pi**2) + 5/24 - 11*math.pi**2/288 + math.pi**4/864
print(f"\nB₄ = 3/(4π²) + 5/24 - 11π²/288 + π⁴/864 = {B4_formula:.10f}")
print(f"B₄ (direct) = {B4:.10f}")
print(f"Match: {abs(B4_formula - B4) < 1e-12}")

# Over common denominator: multiply by 864π²
# 864π²·B₄ = 864·3/4 + 864π²·5/24 - 864π²·11π²/288 + 864π²·π⁴/864
#           = 648 + 180π² - 33π⁴ + π⁶
# So B₄ = (π⁶ - 33π⁴ + 180π² + 648) / (864π²)

B4_full = (math.pi**6 - 33*math.pi**4 + 180*math.pi**2 + 648) / (864*math.pi**2)
print(f"\nB₄ = (π⁶ - 33π⁴ + 180π² + 648)/(864π²) = {B4_full:.10f}")
print(f"Match: {abs(B4_full - B4) < 1e-12}")

# Can we factor π⁶ - 33π⁴ + 180π² + 648?
# Treat as cubic in x = π²: x³ - 33x² + 180x + 648
# Rational roots: ±1, ±2, ±3, ...±648 factors
# x=36: 46656 - 42768 + 6480 + 648 = 11016. No.
# x=3: 27 - 297 + 540 + 648 = 918. No.
# x=6: 216 - 1188 + 1080 + 648 = 756. No.
# x=-3: -27 - 297 - 540 + 648 = -216. No.
# x=-2: -8 - 132 - 360 + 648 = 148. No.
# Doesn't factor nicely.

print(f"\nNumerical value of β: {B4:.12f}")
print(f"≈ 0.020 as observed in the data table")

print(f"\n{'='*80}")
print(f"COMPLETE 4-TERM ASYMPTOTIC:")
print(f"{'='*80}")
print(f"""
R_m = p(m)/p(m-1) = 1 + A/√m + L/m + α/m^(3/2) + β/m² + O(m^(-5/2))

  A  = π/√6                                    ≈ {B1:.10f}
  L  = (π² - 12)/12                            ≈ {B2:.10f}
  α  = (π²-24)(4π²-9)/(144π√6)                ≈ {B3:.10f}
  β  = (π⁶-33π⁴+180π²+648)/(864π²)           ≈ {B4:.10f}
  
Equivalently:
  R_m - 1 = π/√(6m) + (π²-12)/(12m) + (π²-24)(4π²-9)/(144π√6·m^(3/2))
           + (π⁶-33π⁴+180π²+648)/(864π²m²) + O(m^(-5/2))
""")

# Final precision check at m=4000
m_test = 4000
R_test = float(mpmath.mpf(p(m_test))/mpmath.mpf(p(m_test-1)))
R_4term = 1 + B1/math.sqrt(m_test) + B2/m_test + B3/m_test**1.5 + B4/m_test**2
err_3term = R_test - (1 + B1/math.sqrt(m_test) + B2/m_test + B3/m_test**1.5)
err_4term = R_test - R_4term
print(f"At m={m_test}:")
print(f"  R_exact = {R_test:.15f}")
print(f"  3-term error = {err_3term:.2e}")
print(f"  4-term error = {err_4term:.2e}")
print(f"  Improvement factor: {abs(err_3term/err_4term):.1f}×")
print(f"\n=== DONE ===")
