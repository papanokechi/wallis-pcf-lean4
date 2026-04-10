#!/usr/bin/env python3
"""
Approach A: Direct closed-form investigation for the PCF family
    a_m(n) = -n(2n - (2m+1)),   b(n) = 3n + 1

Goal: Find explicit closed forms for p_n^(m) and q_n^(m) for general m,
then prove the conjecture val(m) = 2^{2m+1} / (pi * C(2m,m)).

Phase 1: Compute numerator/denominator tables for m=0..5, n=0..15
Phase 2: Factor p_n^(m) and look for Pochhammer / double-factorial structure
Phase 3: Conjecture closed form, verify against recurrence
Phase 4: Series expansion for q_n^(m) / p_n^(m) -> identify the limit series
"""
from __future__ import annotations

import sys
from fractions import Fraction
from math import comb, factorial, gcd
from functools import reduce
from mpmath import mp, mpf, pi, nstr, binomial as mpbinom

mp.dps = 200

# ─── Phase 1: Exact rational computation of convergents ─────────────────────

def compute_convergents_exact(m: int, N: int) -> tuple[list[Fraction], list[Fraction]]:
    """Compute p_n, q_n as exact Fractions for n = 0..N."""
    def a(n):
        return Fraction(-n * (2*n - (2*m + 1)))
    def b(n):
        return Fraction(3*n + 1)

    # p_{-1} = 1, p_0 = b(0), q_{-1} = 0, q_0 = 1
    p_prev, p_curr = Fraction(1), b(0)  # p_{-1}, p_0
    q_prev, q_curr = Fraction(0), Fraction(1)  # q_{-1}, q_0

    ps = [p_curr]
    qs = [q_curr]

    for n in range(1, N + 1):
        an = a(n)
        bn = b(n)
        p_next = bn * p_curr + an * p_prev
        q_next = bn * q_curr + an * q_prev
        p_prev, p_curr = p_curr, p_next
        q_prev, q_curr = q_curr, q_next
        ps.append(p_curr)
        qs.append(q_curr)

    return ps, qs


def double_factorial(n: int) -> int:
    """(2n+1)!! = 1*3*5*...*(2n+1)"""
    r = 1
    for k in range(1, 2*n + 2, 2):
        r *= k
    return r


def double_factorial_raw(k: int) -> int:
    """k!! for odd k >= -1.  (-1)!! = 1 by convention."""
    if k <= 0:
        return 1
    r = 1
    while k > 0:
        r *= k
        k -= 2
    return r


print("=" * 80)
print("PHASE 1: Convergent numerator tables  p_n^(m)")
print("=" * 80)

M_MAX = 6
N_MAX = 12

all_p: dict[int, list[int]] = {}
all_q: dict[int, list[Fraction]] = {}

for m in range(M_MAX + 1):
    ps, qs = compute_convergents_exact(m, N_MAX)
    all_p[m] = [int(p) for p in ps]
    all_q[m] = qs
    print(f"\nm={m}:  a(n) = -n(2n-{2*m+1}),  b(n) = 3n+1")
    print(f"  p_n: {all_p[m][:10]}")
    # verify limit
    mp.dps = 200
    ratio = mpf(qs[-1]) / mpf(ps[-1])
    expected = mpf(2)**(2*m+1) / (pi * mpbinom(2*m, m))
    diff = abs(mpf(ps[-1]) / mpf(qs[-1]) - expected)
    print(f"  val(m={m}) = {nstr(expected, 30)}")
    print(f"  p_N/q_N match: {int(-mp.log10(diff)) if diff > 0 else '>200'}+ digits")


# ─── Phase 2: Factor p_n^(m) ────────────────────────────────────────────────

print("\n" + "=" * 80)
print("PHASE 2: Structural analysis of p_n^(m)")
print("=" * 80)

# m=0 known: p_n = (2n+1)!!
print("\n--- m=0 verification: p_n / (2n+1)!! ---")
for n in range(N_MAX + 1):
    expected = double_factorial(n)
    actual = all_p[0][n]
    assert actual == expected, f"m=0, n={n}: {actual} != {expected}"
print("  All match (2n+1)!!  ✓")


# For m>=1, divide out (2n+1)!! and see what's left
print("\n--- Ratio r_n^(m) = p_n^(m) / (2n+1)!! ---")
for m in range(M_MAX + 1):
    print(f"\n  m={m}:")
    ratios = []
    for n in range(N_MAX + 1):
        df = double_factorial(n)
        r = Fraction(all_p[m][n], df)
        ratios.append(r)
        print(f"    n={n:2d}: p={all_p[m][n]:15d}  (2n+1)!!={df:15d}  ratio={r}")


# ─── Phase 2b: Try p_n^(m) / (2n+2m+1)!! * (2m-1)!! ────────────────────────

print("\n--- Ratio p_n^(m) * (2m-1)!! / (2n+2m+1)!! ---")
for m in range(M_MAX + 1):
    print(f"\n  m={m}:")
    dfm = double_factorial_raw(2*m - 1)  # (2m-1)!!
    for n in range(min(N_MAX + 1, 10)):
        df_top = double_factorial_raw(2*n + 2*m + 1)
        r = Fraction(all_p[m][n] * dfm, df_top)
        print(f"    n={n:2d}: p*{dfm} / (2n+{2*m+1})!! = {r}")


# ─── Phase 2c: Pochhammer / rising factorial structure ───────────────────────

def pochhammer(a: Fraction, n: int) -> Fraction:
    """(a)_n = a(a+1)...(a+n-1)"""
    result = Fraction(1)
    for k in range(n):
        result *= (a + k)
    return result


print("\n\n--- Checking Pochhammer structure ---")
print("  Try: p_n^(m) = (2n+1)!! * P_m(n) where P_m is a polynomial in n")

for m in range(M_MAX + 1):
    print(f"\n  m={m}:  P_m(n) = p_n^(m) / (2n+1)!!:")
    polys = []
    for n in range(N_MAX + 1):
        df = double_factorial(n)
        r = Fraction(all_p[m][n], df)
        polys.append(r)
    
    # Print as fractions
    for n in range(min(10, N_MAX + 1)):
        print(f"    P_{m}({n}) = {polys[n]}")
    
    # Check if this is a polynomial in n: compute finite differences
    vals = polys[:N_MAX + 1]
    diffs = [vals[:]]
    for order in range(1, min(8, len(vals))):
        new_row = []
        for i in range(len(diffs[-1]) - 1):
            new_row.append(diffs[-1][i+1] - diffs[-1][i])
        diffs.append(new_row)
        if all(v == 0 for v in new_row):
            print(f"    → Finite differences vanish at order {order}")
            print(f"    → P_{m}(n) is a polynomial of degree {order - 1}")
            break
    else:
        # Check if ratios of successive diffs are simple
        print(f"    Finite diffs (first few of each order):")
        for order in range(1, min(6, len(diffs))):
            d = diffs[order]
            print(f"      Δ^{order}: {[str(x) for x in d[:6]]}")


# ─── Phase 2d: Direct polynomial fitting ────────────────────────────────────

print("\n\n" + "=" * 80)
print("PHASE 2d: Polynomial fitting for R_m(n) = p_n^(m) / (2n+1)!!")
print("=" * 80)

# For m=0: R_0(n) = 1 (degree 0)
# For m=1: Let's see if R_1(n) = p_n^(1)/(2n+1)!! is a polynomial

# Use Lagrange interpolation over Fraction for exact polynomial coefficients
def lagrange_rational(points: list[tuple[int, Fraction]], degree: int) -> list[Fraction]:
    """Fit polynomial of given degree through points. Returns [c0, c1, ..., c_d]."""
    n = degree + 1
    if len(points) < n:
        raise ValueError("Need more points")
    pts = points[:n]
    
    # Vandermonde system
    A = [[Fraction(x**k) for k in range(n)] for x, _ in pts]
    b_vec = [y for _, y in pts]
    
    # Gaussian elimination
    for col in range(n):
        # pivot
        pivot_row = None
        for row in range(col, n):
            if A[row][col] != 0:
                pivot_row = row
                break
        if pivot_row is None:
            return None
        A[col], A[pivot_row] = A[pivot_row], A[col]
        b_vec[col], b_vec[pivot_row] = b_vec[pivot_row], b_vec[col]
        
        for row in range(n):
            if row == col:
                continue
            if A[row][col] == 0:
                continue
            factor = A[row][col] / A[col][col]
            for j in range(n):
                A[row][j] -= factor * A[col][j]
            b_vec[row] -= factor * b_vec[col]
    
    coeffs = [b_vec[i] / A[i][i] for i in range(n)]
    return coeffs


def eval_poly(coeffs: list[Fraction], x: int) -> Fraction:
    result = Fraction(0)
    for k, c in enumerate(coeffs):
        result += c * Fraction(x)**k
    return result


for m in range(M_MAX + 1):
    print(f"\nm={m}:")
    ratios = []
    for n in range(N_MAX + 1):
        df = double_factorial(n)
        r = Fraction(all_p[m][n], df)
        ratios.append((n, r))
    
    # Try increasing degrees
    for deg in range(2*m + 2):
        if deg + 1 > len(ratios):
            break
        coeffs = lagrange_rational(ratios, deg)
        if coeffs is None:
            continue
        # Verify on ALL points
        ok = True
        for n, r in ratios:
            pred = eval_poly(coeffs, n)
            if pred != r:
                ok = False
                break
        if ok:
            print(f"  R_{m}(n) is a polynomial of degree {deg}")
            print(f"  Coefficients [c0, c1, ..., c_{deg}]:")
            for k, c in enumerate(coeffs):
                print(f"    c_{k} = {c}")
            
            # Try to express in factorial form
            # Common denominator
            denoms = [c.denominator for c in coeffs if c != 0]
            lcd = reduce(lambda a, b: a * b // gcd(a, b), denoms, 1) if denoms else 1
            int_coeffs = [int(c * lcd) for c in coeffs]
            print(f"  As integer poly / {lcd}:  {int_coeffs}")
            
            # Factor the polynomial nicely
            # Check: is R_m(n) = Product_{j=1}^{m} (something involving n)?
            if m > 0 and deg == 2 * m:
                print(f"  Degree = 2m = {2*m}, checking product structure...")
                # Try to find roots
                # R_m(n) = 0 when p_n^(m) = 0, but p_n shouldn't be 0 for n>=0
                # Maybe roots are at negative half-integers?
                pass
            
            break
    else:
        print(f"  R_{m}(n) is NOT a polynomial of degree <= {2*m+1}")
        # It might involve n! or Pochhammer
        print(f"  Trying ratio-of-Pochhammer structure...")


# ─── Phase 3: Express R_m(n) using Pochhammer symbols ───────────────────────

print("\n\n" + "=" * 80)
print("PHASE 3: Pochhammer / hypergeometric structure of R_m(n)")
print("=" * 80)

# For m=0: R_0(n) = 1
# For m=1: R_1(n) = (n^2 + 3n + 1) / (2n+1)  ... or similar
# Let's check: is R_m(n) = something / (2n+1)(2n+3)...(2n+2m-1)?

print("\n--- Check: R_m(n) * (3/2)_m / (n + 3/2)_m ---")
# Pochhammer (3/2)_m = (3/2)(5/2)...(2m+1)/2 = (2m+1)!! / 2^m
# Pochhammer (n+3/2)_m = (n+3/2)(n+5/2)...(n+m+1/2)

for m in range(M_MAX + 1):
    print(f"\n  m={m}:")
    half = Fraction(1, 2)
    
    # (3/2)_m
    poch_32_m = pochhammer(Fraction(3, 2), m)
    
    for n in range(min(8, N_MAX + 1)):
        df = double_factorial(n)
        R = Fraction(all_p[m][n], df)
        
        # (n + 3/2)_m
        poch_n32_m = pochhammer(Fraction(2*n + 3, 2), m)
        
        if poch_n32_m != 0:
            val = R * poch_n32_m / poch_32_m
            print(f"    n={n}: R * (n+3/2)_m / (3/2)_m = {val}")


# ─── Phase 3b: Try R_m(n) = (1/2)_m * P(n) / (n+3/2)_m type ───────────────

print("\n\n--- Ratio analysis: p_n^(m) / p_n^(0) ---")
for m in range(M_MAX + 1):
    print(f"\n  m={m}:  p_n^({m}) / p_n^(0) = p_n^({m}) / (2n+1)!! = R_{m}(n)")
    if m == 0:
        print("    = 1 (trivially)")
        continue
    
    # Look at R_m(n) * product of (2n+2k+1) for k=0..m-1 divided by product of (2k+1)
    # i.e. R_m(n) * (2n+1)(2n+3)...(2n+2m-1) / (1)(3)...(2m-1)
    
    for n in range(min(10, N_MAX + 1)):
        df = double_factorial(n)
        R = Fraction(all_p[m][n], df)
        
        # Multiply by (2n+3)(2n+5)...(2n+2m+1) / (3)(5)...(2m+1)
        num_prod = 1
        den_prod = 1
        for k in range(1, m + 1):
            num_prod *= (2*n + 2*k + 1)
            den_prod *= (2*k + 1)
        
        val = R * Fraction(num_prod, den_prod)
        print(f"    n={n}: R_{m}(n) * prod = {val}")


# ─── Phase 3c: Systematic search for the pattern ────────────────────────────

print("\n\n" + "=" * 80)
print("PHASE 3c: Recognize R_m(n) via OEIS / known sequences")
print("=" * 80)

# For each m, print the integer numerators/denominators of R_m(n) 
for m in range(M_MAX + 1):
    print(f"\n  m={m}:")
    nums = []
    dens = []
    for n in range(min(12, N_MAX + 1)):
        df = double_factorial(n)
        R = Fraction(all_p[m][n], df)
        nums.append(R.numerator)
        dens.append(R.denominator)
    print(f"    Numerators:   {nums}")
    print(f"    Denominators: {dens}")


# ─── Phase 4: Consecutive ratio p_{n}^{(m)} / p_{n-1}^{(m)} ────────────────

print("\n\n" + "=" * 80)
print("PHASE 4: Consecutive ratios p_n^(m) / p_{n-1}^(m)")
print("=" * 80)

for m in range(min(4, M_MAX + 1)):
    print(f"\n  m={m}:")
    for n in range(1, min(10, N_MAX + 1)):
        ratio = Fraction(all_p[m][n], all_p[m][n-1])
        print(f"    p_{n}/p_{n-1} = {ratio} = {float(ratio):.6f}")


# ─── Phase 5: Try to express p_n^(m) in terms of sum formulas ───────────────

print("\n\n" + "=" * 80)
print("PHASE 5: Sum decomposition of p_n^(m)")
print("=" * 80)

# For m=0: p_n = (2n+1)!! = sum-free
# For m=1: can we write p_n^(1) = sum_{k=0}^n c_k * (2k+1)!! * something?

# Actually let's try: p_n^(m) = (2n+1)!! * sum_{j=0}^{m} A(m,j) * f_j(n)
# where f_j are simple functions of n

# Or perhaps p_n^(m) = sum_{k} (-1)^k C(m,k) * (something involving n and k)

# Let me try the Pochhammer approach more carefully.
# We have p_n^(m) / (2n+1)!! = R_m(n).
# For m=0: R_0(n) = 1
# For m=1: let's see what the polynomial is

print("\n--- Polynomial R_m(n) expressed in falling/rising factorial basis ---")

for m in range(min(5, M_MAX + 1)):
    ratios = []
    for n in range(N_MAX + 1):
        df = double_factorial(n)
        r = Fraction(all_p[m][n], df)
        ratios.append((n, r))
    
    # Determine degree
    for deg in range(20):
        if deg + 1 > len(ratios):
            break
        coeffs = lagrange_rational(ratios, deg)
        if coeffs is None:
            continue
        ok = all(eval_poly(coeffs, n) == r for n, r in ratios)
        if ok:
            break
    
    if not ok:
        print(f"\n  m={m}: R_{m}(n) is not polynomial up to degree 19")
        continue
    
    print(f"\n  m={m}: R_{m}(n) is degree {deg}")
    print(f"    Standard basis: {coeffs}")
    
    # Convert to Pochhammer basis: R_m(n) = sum c_k (n)_k / k!  (Newton forward)
    # Or better: express in terms of (n+1)_k
    # Newton forward differences: coeffs in falling factorial basis
    # Δ^k R(0) / k!
    vals = [r for _, r in ratios]
    newton_coeffs = []
    current = vals[:]
    for k in range(deg + 1):
        newton_coeffs.append(current[0])
        current = [current[i+1] - current[i] for i in range(len(current) - 1)]
    
    print(f"    Newton forward (falling factorial) basis:")
    for k, c in enumerate(newton_coeffs):
        if c != 0:
            print(f"      [{k}] {c} * C(n,{k}) * {factorial(k)}")


# ─── Phase 6: Connection to shifted double factorials ───────────────────────

print("\n\n" + "=" * 80)
print("PHASE 6: Check p_n^(m) = (2n+2m+1)!! / (2m+1)!! * Q_m(n)")
print("=" * 80)

for m in range(M_MAX + 1):
    print(f"\n  m={m}:")
    df_shift = double_factorial_raw(2*m + 1)  # (2m+1)!!
    for n in range(min(10, N_MAX + 1)):
        df_top = double_factorial_raw(2*n + 2*m + 1)  # (2n+2m+1)!!
        # Check: p_n^(m) * (2m+1)!! / (2n+2m+1)!!
        R = Fraction(all_p[m][n] * df_shift, df_top)
        print(f"    n={n}: p * (2m+1)!! / (2n+2m+1)!! = {R}")


# ─── Phase 7: Verify recursion from m to m+1 ────────────────────────────────

print("\n\n" + "=" * 80)
print("PHASE 7: Ratio p_n^(m+1) / p_n^(m)")
print("=" * 80)

for m in range(min(5, M_MAX)):
    print(f"\n  m={m} → m+1={m+1}:")
    for n in range(min(10, N_MAX + 1)):
        if all_p[m][n] != 0:
            ratio = Fraction(all_p[m+1][n], all_p[m][n])
            print(f"    n={n}: p_n^({m+1})/p_n^({m}) = {ratio} = {float(ratio):.8f}")


# ─── Phase 8: q_n analysis and limit series ─────────────────────────────────

print("\n\n" + "=" * 80)
print("PHASE 8: Limit series  val(m) = lim p_n/q_n")
print("=" * 80)

# For m=0: q_n / p_n -> pi/2,  series sum j!/(2j+1)!!
# For m=1: what is the series?

# Compute the "partial fraction" s_n^(m) = q_n^(m) / p_n^(m)
# and its increments Δ_n = s_n - s_{n-1}

for m in range(min(4, M_MAX + 1)):
    print(f"\n  m={m}:")
    prev = Fraction(0)
    for n in range(min(10, N_MAX + 1)):
        s_n = all_q[m][n] / Fraction(all_p[m][n])  # q_n / p_n (this is the reciprocal of val)
        delta = s_n - prev
        prev = s_n
        # Try to simplify delta
        print(f"    n={n}: s_n = {float(s_n):.12f}   Δ_n = {delta}")
    
    print(f"    Expected limit: pi * C(2m,m) / 2^(2m+1) = {float(mpf(pi) * comb(2*m, m) / 2**(2*m+1)):.12f}")


# ─── Phase 9: Delta_n expressed in closed form ──────────────────────────────

print("\n\n" + "=" * 80)
print("PHASE 9: Increments Δ_n = s_n - s_{n-1} = (determinant) / (p_n * p_{n-1})")
print("=" * 80)

# By standard CF theory, p_n q_{n-1} - p_{n-1} q_n = (-1)^{n+1} prod_{k=1}^{n} a(k)
# So Δ_n = q_n/p_n - q_{n-1}/p_{n-1} = (p_{n-1} q_n - p_n q_{n-1}) / (p_n p_{n-1})
#        = (-1)^n prod_{k=1}^n a(k) / (p_n p_{n-1})

for m in range(min(4, M_MAX + 1)):
    print(f"\n  m={m}:")
    for n in range(1, min(10, N_MAX + 1)):
        # prod a(k) for k=1..n
        prod_a = Fraction(1)
        for k in range(1, n + 1):
            prod_a *= Fraction(-k * (2*k - (2*m + 1)))
        
        det = (-1)**n * prod_a  # This should = p_{n-1} q_n - p_n q_{n-1}
        # Actually from recurrence: p_n q_{n-1} - p_{n-1} q_n = (-1)^{n-1} prod_{k=1}^n a_k
        
        # Verify:
        lhs = all_p[m][n] * all_q[m][n-1] - all_p[m][n-1] * all_q[m][n]
        rhs = 1
        for k in range(1, n + 1):
            rhs *= (-k * (2*k - (2*m + 1)))
        # The correct formula: prod of a_k with correct sign
        det_val = Fraction(rhs)
        
        if lhs != 0:
            check_ratio = det_val / lhs
            print(f"    n={n}: det = {lhs}    prod_a = {det_val}   ratio = {check_ratio}")
        else:
            print(f"    n={n}: det = {lhs}    prod_a = {det_val}")


# ─── Phase 10: Factor the determinant product ───────────────────────────────

print("\n\n" + "=" * 80)
print("PHASE 10: Product of a(k) = -k(2k-(2m+1)) for k=1..n")
print("=" * 80)

# prod_{k=1}^n [-k(2k-(2m+1))]
# = (-1)^n * n! * prod_{k=1}^n (2k-(2m+1))

# For m=0: prod (2k-1) = (2n-1)!! = 1*3*5*...*(2n-1)
# For m=1: prod (2k-3) = (-1)*1*3*...*(2n-3) = (-1)*(2n-3)!!
# For m=2: prod (2k-5) = (-3)(-1)(1)(3)...*(2n-5) 

for m in range(min(5, M_MAX + 1)):
    print(f"\n  m={m}: prod_{{k=1}}^n (2k-(2m+1)):")
    for n in range(1, min(10, N_MAX + 1)):
        prod_val = 1
        for k in range(1, n + 1):
            prod_val *= (2*k - (2*m + 1))
        print(f"    n={n}: {prod_val}")


# ─── Phase 11: High-precision limit verification ────────────────────────────

print("\n\n" + "=" * 80)
print("PHASE 11: High-precision limit verification (200 digits)")
print("=" * 80)

mp.dps = 250

for m in range(8):
    # Compute convergents at high depth
    N_deep = 500
    p_prev, p_curr = mpf(1), mpf(1)  # p_{-1}=1, p_0=b(0)=1
    q_prev, q_curr = mpf(0), mpf(1)
    
    for n in range(1, N_deep + 1):
        an = mpf(-n * (2*n - (2*m + 1)))
        bn = mpf(3*n + 1)
        p_next = bn * p_curr + an * p_prev
        q_next = bn * q_curr + an * q_prev
        p_prev, p_curr = p_curr, p_next
        q_prev, q_curr = q_curr, q_next
    
    val = p_curr / q_curr
    expected = mpf(2)**(2*m+1) / (pi * mpbinom(2*m, m))
    diff = abs(val - expected)
    digits = int(-mp.log10(diff)) if diff > 0 else 250
    
    cb = comb(2*m, m)
    print(f"  m={m}: val = 2^{2*m+1}/(pi*C({2*m},{m})) = {2**(2*m+1)}/{cb}*pi")
    print(f"         Match: {digits} digits")
    
    # Also verify the ratio
    if m > 0:
        # val(m) / val(m-1) should be 2m/(2m-1)
        expected_prev = mpf(2)**(2*(m-1)+1) / (pi * mpbinom(2*(m-1), m-1))
        ratio = val / expected_prev
        expected_ratio = mpf(2*m) / mpf(2*m - 1)
        ratio_diff = abs(ratio - expected_ratio)
        ratio_digits = int(-mp.log10(ratio_diff)) if ratio_diff > 0 else 200
        print(f"         val({m})/val({m-1}) = 2*{m}/{2*m-1} = {float(expected_ratio):.10f}  ({ratio_digits} digits)")


print("\n\n" + "=" * 80)
print("COMPLETE")
print("=" * 80)
