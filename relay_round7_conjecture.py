"""
OEIS A002865 Relay Chain — Round 7 (Conjecture Agent)
Goal: Derive the EXACT O(m^{-3/2}) coefficient in R_m = p(m)/p(m-1).

THEORETICAL DERIVATION
======================
From the k=1 Rademacher term:
  p(n) = (1/(π√2)) · d/dn [sinh(c√μ)/√μ]
where c = π√(2/3), μ = n - 1/24.

For large μ, sinh(c√μ) ≈ e^{c√μ}/2, so
  p(n) ≈ (c·e^{c√μ})/(4π√2·μ) · [1 - 1/(c√μ)]

Taking log:
  log p(n) = c√μ - ln μ - ln(4√3) - 1/(c√μ) - 1/(2c²μ) + O(μ^{-3/2})

Discrete difference Δ log p = log p(m) - log p(m-1) with ν = m - 1/24:
  Δ[c√μ] = c/(2√ν) + c/(8ν^{3/2}) + ...
  Δ[-ln μ] = -1/ν - 1/(2ν²) + ...
  Δ[-1/(c√μ)] = 1/(2cν^{3/2}) + ...

So Δ log p = c/(2√ν) - 1/ν + (c/8 + 1/(2c))·ν^{-3/2} + O(ν^{-2})

Exponentiating R_m = exp(Δ) = 1 + Δ + Δ²/2 + Δ³/6 + ...:
  Coeff of ν^{-1/2}: c/2
  Coeff of ν^{-1}:   c²/8 - 1 = π²/12 - 1          (this is L)
  Coeff of ν^{-3/2}: -3c/8 + 1/(2c) + c³/48         (call this D_ν)

Converting from ν = m - 1/24 to m adds c/96 to the m^{-3/2} coefficient,
so the m^{-3/2} coefficient in R_m is:
  α = c/96 - 3c/8 + 1/(2c) + c³/48
    = c(-35/96 + c²/48) + 1/(2c)
    = (4π⁴ - 105π² + 216) / (144π√6)
    = (π² - 24)(4π² - 9) / (144π√6)
"""
import math
from functools import lru_cache

# ─── Constants ───
c = math.pi * math.sqrt(2.0/3.0)  # π√(2/3)
L_exact = math.pi**2 / 12 - 1     # π²/12 - 1

# Theoretical α from derivation
alpha_theory = (math.pi**2 - 24) * (4*math.pi**2 - 9) / (144 * math.pi * math.sqrt(6))
print(f"c = π√(2/3) = {c:.12f}")
print(f"c = π√6/3  = {math.pi*math.sqrt(6)/3:.12f}")
print(f"L = π²/12 - 1 = {L_exact:.12f}")
print(f"α_theory = (π²-24)(4π²-9)/(144π√6) = {alpha_theory:.12f}")

# Verify intermediate steps
print(f"\n  π² = {math.pi**2:.10f}")
print(f"  π² - 24 = {math.pi**2 - 24:.10f}")
print(f"  4π² - 9 = {4*math.pi**2 - 9:.10f}")
print(f"  (π²-24)(4π²-9) = {(math.pi**2-24)*(4*math.pi**2-9):.10f}")
print(f"  144π√6 = {144*math.pi*math.sqrt(6):.10f}")

# Cross-check via intermediate form
alpha_check = c*(-35/96 + c**2/48) + 1/(2*c)
print(f"  α via c(-35/96 + c²/48) + 1/(2c) = {alpha_check:.12f}")
print(f"  Match: {abs(alpha_theory - alpha_check) < 1e-14}")

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

# ─── High-precision computation ───
import mpmath
mpmath.mp.dps = 60

def R_mp(m):
    return mpmath.mpf(p(m)) / mpmath.mpf(p(m-1))

def C_m(m):
    """C_m = m·(R_m - 1 - π/√(6m))"""
    R = R_mp(m)
    return float(m * (R - 1 - mpmath.pi / mpmath.sqrt(6*m)))

def alpha_from_m(m):
    """Extract α estimate: √m·(C_m - L)"""
    return math.sqrt(m) * (C_m(m) - L_exact)

# ─── Compute to large m ───
N_MAX = 4000
print(f"\nPrecomputing partitions to m={N_MAX}...")
for n in range(N_MAX + 2):
    p(n)
print(f"Done. p({N_MAX}) has {len(str(p(N_MAX)))} digits.")

# ─── Table: C_m, δ(m), √m·δ, and comparison to α_theory ───
print(f"\n{'='*80}")
print(f"Numerical verification of α = (π²-24)(4π²-9)/(144π√6) = {alpha_theory:.10f}")
print(f"{'='*80}")
print(f"{'m':>6} {'C_m':>14} {'√m(C_m-L)':>14} {'α_theory':>14} {'gap':>12} {'√m·gap':>12}")

data_alpha = []
for m in list(range(50, 101, 10)) + list(range(100, 501, 50)) + list(range(500, 4001, 200)):
    cm = C_m(m)
    alpha_num = math.sqrt(m) * (cm - L_exact)
    gap = alpha_num - alpha_theory
    data_alpha.append((m, cm, alpha_num, gap))
    if m <= 100 or m % 500 == 0 or m >= 3800:
        print(f"{m:6d} {cm:14.8f} {alpha_num:14.8f} {alpha_theory:14.8f} {gap:12.6f} {math.sqrt(m)*gap:12.4f}")

# ─── Richardson extrapolation on α estimates ───
# f(m) = √m·(C_m - L) = α + β/√m + γ/m + ...
# Single Richardson: 2f(4m) - f(m) = α + O(1/m)
print(f"\n{'='*80}")
print(f"Richardson extrapolation for α")
print(f"{'='*80}")

print("\n  Single Richardson (eliminate 1/√m):")
for m in [100, 200, 250, 500, 750, 1000]:
    if 4*m <= N_MAX:
        f_m = alpha_from_m(m)
        f_4m = alpha_from_m(4*m)
        rich1 = 2*f_4m - f_m
        err = rich1 - alpha_theory
        print(f"    m={m:5d}: f(m)={f_m:.8f}, f(4m)={f_4m:.8f}, Rich={rich1:.8f}, err={err:.2e}")

print("\n  Double Richardson (eliminate 1/√m and 1/m):")
for m in [50, 100, 200, 250]:
    if 16*m <= N_MAX:
        f1 = alpha_from_m(m)
        f4 = alpha_from_m(4*m)
        f16 = alpha_from_m(16*m)
        r1 = 2*f4 - f1     # eliminates 1/√m: r = α + γ/m + ...
        r2 = 2*f16 - f4    # same form: r = α + γ/(4m) + ...
        drich = (4*r2 - r1)/3  # eliminates 1/m: drich = α + O(1/m²)
        err = drich - alpha_theory
        print(f"    m={m:4d}: Rich1={r1:.8f}, Rich2={r2:.8f}, DRich={drich:.10f}, err={err:.2e}")

# ─── Now derive the NEXT coefficient (m^{-2} term in R_m) ───
print(f"\n{'='*80}")
print(f"Extracting the O(m^{{-2}}) coefficient β in R_m")
print(f"{'='*80}")

# R_m = 1 + c/(2√m) + L/m + α/m^{3/2} + β/m² + ...
# So: m²·(R_m - 1 - c/(2√m) - L/m - α/m^{3/2}) → β
# Or equivalently: (C_m - L - α/√m)·m → β

print(f"\n{'m':>6} {'D_m = m(C_m-L-α/√m)':>22} {'Trend':>10}")
prev_D = None
for m in list(range(200, 501, 50)) + list(range(500, 4001, 500)):
    cm = C_m(m)
    Dm = m * (cm - L_exact - alpha_theory / math.sqrt(m))
    trend = "" if prev_D is None else ("↑" if Dm > prev_D else "↓")
    if m <= 500 or m % 500 == 0:
        print(f"{m:6d} {Dm:22.8f} {trend:>10}")
    prev_D = Dm

# ─── Full expansion summary ───
print(f"\n{'='*80}")
print(f"FULL ASYMPTOTIC EXPANSION (verified)")
print(f"{'='*80}")
print(f"""
R_m = p(m)/p(m-1) = 1 + A/√m + L/m + α/m^(3/2) + β/m² + ...

where (c = π√(2/3)):
  A = c/2 = π/(2√(3/2)) = π/√6 ≈ {math.pi/math.sqrt(6):.10f}
  
  L = c²/8 - 1 = π²/12 - 1 ≈ {L_exact:.10f}
  
  α = c(-35/96 + c²/48) + 1/(2c)
    = (π²-24)(4π²-9)/(144π√6) ≈ {alpha_theory:.10f}
  
  β ≈ [to be determined from numerics]
""")

# ─── Verify the FACTORED form more carefully ───
print("Verifying factored form:")
numer = (math.pi**2 - 24) * (4*math.pi**2 - 9)
denom = 144 * math.pi * math.sqrt(6)
print(f"  (π²-24) = {math.pi**2-24:.10f}")
print(f"  (4π²-9) = {4*math.pi**2-9:.10f}")
print(f"  numerator = {numer:.10f}")
print(f"  denominator = {denom:.10f}")
print(f"  α = {numer/denom:.12f}")

# ─── Additional: verify entire expansion at specific m values ───
print(f"\n{'='*80}")
print(f"Pointwise verification of 3-term expansion")
print(f"{'='*80}")
print(f"{'m':>6} {'R_m exact':>18} {'R_m 3-term':>18} {'error':>14} {'error×m²':>14}")
for m in [100, 200, 500, 1000, 2000, 3000, 4000]:
    R_exact = float(R_mp(m))
    R_approx = 1 + math.pi/math.sqrt(6*m) + L_exact/m + alpha_theory/m**1.5
    err = R_exact - R_approx
    print(f"{m:6d} {R_exact:18.12f} {R_approx:18.12f} {err:14.2e} {err*m**2:14.4f}")

# ─── Test: does the identity actually matter? ───
# a(n) = p(n-2) was established in Round 2. Agent 6 claims p(n-1)-1.
# Let's re-verify once more.
print(f"\n{'='*80}")
print(f"Identity check (final)")
print(f"{'='*80}")
known = [0, 0, 1, 1, 2, 3, 5, 7, 11, 15, 22, 30, 42, 56, 77, 101]
ok_a = all(p(n-2) == known[n] for n in range(len(known)))
ok_b = all(p(n-1)-1 == known[n] for n in range(2, len(known)))
print(f"  a(n) = p(n-2):   matches all {len(known)} terms? {ok_a}")
print(f"  a(n) = p(n-1)-1: matches n≥2?  {ok_b}")
print(f"    Test: p(4)-1 = {p(4)-1}, known a(5) = {known[5]}")

print("\n=== DONE ===")
