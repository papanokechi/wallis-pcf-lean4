"""
Round 10D part 3: VERIFY β_k CLOSED FORM
==========================================

Key discovery: A₂^(k)·c_k² = (k+3)(π²k² - 9(k+1))/144
Hence: A₂^(k) = (k+3)(π²k² - 9k - 9)/(96kπ²)

And: β_k = β_struct - A₂ where β_struct = c⁴/384 + c²(1+2κ)/16 + κ(κ+1)/2 - cA₁/4

Full formula:
  864kπ² · β_k = k³π⁶ - 3k²(5k+6)π⁴ + 45k²(k+3)π² + 81(k+1)(k+3)
"""
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi
mp.dps = 50

def ck(k): return mpi * msqrt(mpf(2*k)/3)
def kk(k): return mpf(-(k+3))/4

def A1_formula(k):
    """A₁^(k) = -kc_k/48 - (k+1)(k+3)/(8c_k)"""
    c = ck(k)
    return -mpf(k)*c/48 - mpf((k+1)*(k+3))/(8*c)

def A2_formula(k):
    """A₂^(k) = (k+3)(π²k² - 9k - 9)/(96kπ²)"""
    return mpf((k+3)) * (mpi**2 * k**2 - 9*k - 9) / (96 * k * mpi**2)

def beta_formula(k):
    """Full β_k from structural decomposition."""
    c = ck(k)
    kap = kk(k)
    A1 = A1_formula(k)
    A2 = A2_formula(k)
    # β_struct - A₂
    b_struct = c**4/384 + c**2*(1+2*kap)/16 + kap*(kap+1)/2 - c*A1/4
    return b_struct - A2

def beta_direct(k):
    """β_k = [k³π⁶ - 3k²(5k+6)π⁴ + 45k²(k+3)π² + 81(k+1)(k+3)]/(864kπ²)"""
    p = mpi**2
    num = mpf(k)**3 * p**3 - 3*mpf(k)**2*(5*k+6)*p**2 + 45*mpf(k)**2*(k+3)*p + 81*mpf(k+1)*(k+3)
    return num / (864 * k * p)

# ═══ VERIFICATION ═══
print("="*70)
print("VERIFICATION: β_k CLOSED FORM")
print("="*70)

# Numerical β values from relay_round10d_beta_extraction.py
beta_numerical = {
    1: mpf('+0.02010216758643'),
    2: mpf('-0.05357990661175'),
    3: mpf('-0.13080704340662'),
    4: mpf('-0.21870338853280'),
    5: mpf('-0.31869377113434'),
}

print(f"\n{'k':>3} | {'β(formula)':>20} | {'β(direct)':>20} | {'β(numerical)':>20} | {'Gap':>12}")
print("-"*95)
for k in range(1,6):
    bf = float(beta_formula(k))
    bd = float(beta_direct(k))
    bn = float(beta_numerical[k])
    print(f"{k:>3} | {bf:>+20.12f} | {bd:>+20.12f} | {bn:>+20.12f} | {abs(bf-bn):>12.2e}")

# Check k=1 against exact Rademacher
print(f"\n{'='*70}")
print("k=1 RADEMACHER CHECK")
print("="*70)
beta1_rademacher = (mpi**6 - 33*mpi**4 + 180*mpi**2 + 648) / (864 * mpi**2)
beta1_formula = beta_direct(1)
print(f"  β₁(Rademacher) = {float(beta1_rademacher):.18f}")
print(f"  β₁(formula)    = {float(beta1_formula):.18f}")
print(f"  Gap: {abs(float(beta1_rademacher - beta1_formula)):.2e}")

# Verify the factored form of numerator at k=1
print(f"\n  At k=1: numerator = 1·π⁶ - 3·1·11·π⁴ + 45·1·4·π² + 81·2·4")
print(f"                    = π⁶ - 33π⁴ + 180π² + 648  ✓ (matches Rademacher)")

# ═══ A₂ formula verification ═══
print(f"\n{'='*70}")
print("A₂ FORMULA VERIFICATION")
print("="*70)

A2_numerical = {
    1: mpf('-0.034324221061'),
    2: mpf('+0.032925209426'),
    3: mpf('+0.111509112273'),
    4: mpf('+0.208551633214'),
    5: mpf('+0.325477601393'),
}

print(f"\n{'k':>3} | {'A₂(formula)':>20} | {'A₂(numerical)':>20} | {'Gap':>12}")
print("-"*70)
for k in range(1,6):
    af = float(A2_formula(k))
    an = float(A2_numerical[k])
    print(f"{k:>3} | {af:>+20.12f} | {an:>+20.12f} | {abs(af-an):>12.2e}")

# ═══ A₂·c² factored form verification ═══
print(f"\n{'='*70}")
print("A₂·c² = (k+3)(π²k² - 9(k+1))/144")
print("="*70)

for k in range(1,6):
    factored = mpf(k+3) * (mpi**2 * k**2 - 9*(k+1)) / 144
    direct = A2_formula(k) * ck(k)**2
    print(f"  k={k}: factored={float(factored):+.16f}, direct={float(direct):+.16f}, gap={abs(float(factored-direct)):.2e}")

# ═══ Selection rule for A₂ ═══
print(f"\n{'='*70}")
print("SELECTION RULE FOR A₂")
print("="*70)

print(f"\n  A₁ selection rule: A₁ = -kc/48 + Δ₁, where Δ₁·c = -(k+3)(k-1)/8")
print(f"  A₂ selection rule: A₂ = (k+3)k/96 + Δ₂, where Δ₂ = -9(k+1)(k+3)/(96kπ²)")

for k in range(1,6):
    base1 = -k * float(ck(k)) / 48
    delta1 = float(A1_formula(k)) - base1
    delta1c = delta1 * float(ck(k))
    pred1 = -(k+3)*(k-1)/8
    
    base2 = (k+3)*k/96.0
    delta2 = float(A2_formula(k)) - base2
    delta2_pred = -9*(k+1)*(k+3)/(96*k*float(mpi**2))
    
    print(f"  k={k}: A₁: Δ₁·c = {delta1c:.8f} (pred={(pred1):.8f})")
    print(f"         A₂: Δ₂   = {delta2:.8f} (pred={delta2_pred:.8f})")

# ═══ FULL CLOSED-FORM SUMMARY ═══
print(f"\n{'='*70}")
print("FULL CLOSED-FORM HIERARCHY (k-colored partitions)")
print("="*70)
print(f"""
  R_m = p_k(m)/p_k(m-1) = 1 + c/(2√m) + L/m + α/m^{{3/2}} + β/m² + O(m^{{-5/2}})

  Parameters:
    c_k = π√(2k/3)
    κ_k = -(k+3)/4

  Tier I — L (Theorem 1'):
    L_k = c²/8 + κ

  Tier II — α (requires A₁):
    α_k = c(c²+6)/48 + cκ/2 - A₁/2

  Tier III — β (requires A₁ AND A₂):  [NEW]
    β_k = c⁴/384 + c²(1+2κ)/16 + κ(κ+1)/2 - cA₁/4 - A₂

  Closed forms for Meinardus coefficients:
    A₁^(k) = -kc_k/48 - (k+1)(k+3)/(8c_k)
    A₂^(k) = (k+3)(π²k² - 9(k+1))/(96kπ²)

  Direct formula for β:
    β_k = [k³π⁶ − 3k²(5k+6)π⁴ + 45k²(k+3)π² + 81(k+1)(k+3)] / (864kπ²)
""")

# Numerical table
print(f"{'k':>3} | {'L_k':>14} | {'α_k':>14} | {'β_k (formula)':>14} | {'β_k (check)':>14}")
print("-"*75)
for k in range(1,6):
    c = ck(k)
    kap = kk(k)
    L = c**2/8 + kap
    A1 = A1_formula(k)
    alpha = c*(c**2+6)/48 + c*kap/2 - A1/2
    beta = beta_direct(k)
    beta_check = beta_formula(k)
    print(f"{k:>3} | {float(L):>+14.6f} | {float(alpha):>+14.6f} | {float(beta):>+14.10f} | {float(beta_check):>+14.10f}")

print("\n=== VERIFICATION COMPLETE ===")
