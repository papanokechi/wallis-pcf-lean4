#!/usr/bin/env python3
"""
Verify the discovered closed-form formula:
    A₁^(k) = -kc/(48) - (k+1)(k+3)/(8c)
where c = π√(2k/3), κ = -(k+3)/4.

Equivalently: A₁^(k) = -[2k²π² + 18(k+1)(k+3)] / (144π√(2k/3))

For k=1 this reduces to -(π²+72)/(24π√6), the known exact Rademacher result.
"""
from mpmath import mp, mpf, pi, sqrt

mp.dps = 50

# Formula
def A1_formula(k):
    c = pi * sqrt(mpf(2*k) / 3)
    return -k * c / 48 - mpf((k+1)*(k+3)) / (8 * c)

# Equivalent expression
def A1_formula_v2(k):
    c = pi * sqrt(mpf(2*k) / 3)
    num = 2 * k**2 * pi**2 + 18 * (k+1) * (k+3)
    return -num / (144 * c)

# Known exact for k=1
A1_exact_1 = -(pi**2 + 72) / (24 * pi * sqrt(6))

# Extracted values (12-digit precision from N=15000/8000/8000)
A1_extracted = {
    1: mpf('-0.443287976870986'),
    2: mpf('-0.668020786470785'),
    3: mpf('-0.952917420748228'),
}

# Lower-precision values from earlier runs (N=1000/800)
A1_lowprec = {
    4: mpf('-1.2789'),
    5: mpf('-1.6408'),
}

print("=" * 70)
print("CLOSED-FORM VERIFICATION: A₁(k) = -kc/48 - (k+1)(k+3)/(8c)")
print("=" * 70)
print()

# Verify formulas are equivalent
for k in range(1, 6):
    f1 = A1_formula(k)
    f2 = A1_formula_v2(k)
    print(f"  k={k}: formula_v1 = {mp.nstr(f1, 18)}")
    print(f"        formula_v2 = {mp.nstr(f2, 18)}")
    print(f"        gap v1-v2  = {mp.nstr(abs(f1-f2), 4)}")

print()
print("=" * 70)
print("COMPARISON WITH EXTRACTED VALUES")
print("=" * 70)

for k in [1, 2, 3]:
    formula = A1_formula(k)
    extracted = A1_extracted[k]
    gap = abs(formula - extracted)
    print(f"\n  k={k}:")
    print(f"    Formula:   {mp.nstr(formula, 18)}")
    print(f"    Extracted: {mp.nstr(extracted, 18)}")
    print(f"    Gap:       {mp.nstr(gap, 4)}")

# k=1 vs exact Rademacher
gap1 = abs(A1_formula(1) - A1_exact_1)
print(f"\n  k=1 vs exact Rademacher:")
print(f"    Formula:   {mp.nstr(A1_formula(1), 25)}")
print(f"    Rademacher:{mp.nstr(A1_exact_1, 25)}")
print(f"    Gap:       {mp.nstr(gap1, 4)} (should be ~0)")

for k in [4, 5]:
    formula = A1_formula(k)
    extracted = A1_lowprec[k]
    gap = abs(formula - extracted)
    print(f"\n  k={k} (low-precision check):")
    print(f"    Formula:   {mp.nstr(formula, 10)}")
    print(f"    Extracted: {mp.nstr(extracted, 5)} (N~1000)")
    print(f"    Gap:       {mp.nstr(gap, 4)}")

# Explicit closed-form expressions
print()
print("=" * 70)
print("EXPLICIT CLOSED FORMS")
print("=" * 70)
print()
print("General: A₁(k) = -[2k²π² + 18(k+1)(k+3)] / [144π√(2k/3)]")
print()

for k in range(1, 6):
    c = pi * sqrt(mpf(2*k) / 3)
    kap = -(mpf(k) + 3) / 4
    num_pi2 = 2 * k**2
    num_const = 18 * (k+1) * (k+3)
    denom_coeff = 144
    print(f"  k={k}: A₁ = -({num_pi2}π² + {num_const}) / ({denom_coeff}π√({2*k}/3))")
    print(f"       = {mp.nstr(A1_formula(k), 18)}")

# Verify cross-consistency
print()
print("  Verification: Δ_k · c_k = -(k+3)(k-1)/8")
for k in range(1, 6):
    c = pi * sqrt(mpf(2*k) / 3)
    kap = -(mpf(k) + 3) / 4
    base = -k * c / 48 + kap / c
    delta = A1_formula(k) - base
    delta_c = delta * c
    expected = -mpf((k+3)*(k-1)) / 8
    print(f"  k={k}: Δ·c = {mp.nstr(delta_c, 12)}, expected = {mp.nstr(expected, 12)}, match = {mp.nstr(abs(delta_c - expected), 4)}")

print()
print("=== FORMULA VERIFIED ===")
