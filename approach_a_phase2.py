#!/usr/bin/env python3
"""
Approach A — Phase 2: Treat p_n^(m) as a polynomial in m for fixed n.

Key discovery: p_n^(m) is a polynomial of degree floor(n/2) in m.
This is the tractable decomposition.
"""
from __future__ import annotations
from fractions import Fraction
from math import factorial, gcd, comb
from functools import reduce
from mpmath import mp, mpf, pi, nstr, binomial as mpbinom

mp.dps = 300

# ─── Compute p_n^(m) for a grid of (n, m) ───────────────────────────────────

def compute_p(m: int, N: int) -> list[Fraction]:
    """Compute p_0,...,p_N as Fraction for parameter m."""
    def a(n):
        return Fraction(-n * (2*n - (2*m + 1)))
    def b(n):
        return Fraction(3*n + 1)
    p_prev, p_curr = Fraction(1), b(0)
    qs = [p_curr]
    for n in range(1, N + 1):
        p_next = b(n) * p_curr + a(n) * p_prev
        p_prev, p_curr = p_curr, p_next
        qs.append(p_curr)
    return qs


def compute_pq(m: int, N: int):
    """Compute (p_n, q_n) for n=0..N as Fraction."""
    def a(n):
        return Fraction(-n * (2*n - (2*m + 1)))
    def b(n):
        return Fraction(3*n + 1)
    p_prev, p_curr = Fraction(1), b(0)
    q_prev, q_curr = Fraction(0), Fraction(1)
    ps, qs = [p_curr], [q_curr]
    for n in range(1, N + 1):
        an, bn = a(n), b(n)
        p_next = bn * p_curr + an * p_prev
        q_next = bn * q_curr + an * q_prev
        p_prev, p_curr = p_curr, p_next
        q_prev, q_curr = q_curr, q_next
        ps.append(p_curr)
        qs.append(q_curr)
    return ps, qs


N_MAX = 12
M_MAX = 20  # Need enough m values to fit polynomials in m

# Build grid: p_n_m[n][m] = p_n^(m)
p_grid: dict[int, dict[int, Fraction]] = {}
for n in range(N_MAX + 1):
    p_grid[n] = {}

for m in range(M_MAX + 1):
    ps = compute_p(m, N_MAX)
    for n in range(N_MAX + 1):
        p_grid[n][m] = ps[n]


# ─── 1. Show p_n^(m) as polynomial in m ─────────────────────────────────────

def lagrange_fit(points: list[tuple[int, Fraction]], deg: int) -> list[Fraction] | None:
    """Fit polynomial of degree deg through points. Returns [c0,c1,...,c_deg] or None."""
    n = deg + 1
    if len(points) < n:
        return None
    pts = points[:n]
    A = [[Fraction(x**k) for k in range(n)] for x, _ in pts]
    b_vec = [y for _, y in pts]
    for col in range(n):
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
            if row == col or A[row][col] == 0:
                continue
            factor = A[row][col] / A[col][col]
            for j in range(n):
                A[row][j] -= factor * A[col][j]
            b_vec[row] -= factor * b_vec[col]
    return [b_vec[i] / A[i][i] for i in range(n)]


def eval_poly(coeffs, x):
    return sum(c * Fraction(x)**k for k, c in enumerate(coeffs))


def poly_str(coeffs: list[Fraction], var: str = "m") -> str:
    terms = []
    for k, c in enumerate(coeffs):
        if c == 0:
            continue
        if k == 0:
            terms.append(str(c))
        elif k == 1:
            terms.append(f"{c}*{var}")
        else:
            terms.append(f"{c}*{var}^{k}")
    return " + ".join(terms) if terms else "0"


print("=" * 80)
print("p_n^(m) as POLYNOMIAL in m  (for fixed n)")
print("=" * 80)

poly_in_m: dict[int, list[Fraction]] = {}

for n in range(N_MAX + 1):
    points = [(m, p_grid[n][m]) for m in range(M_MAX + 1)]
    
    # Find the degree
    for deg in range(20):
        if deg + 1 > len(points):
            break
        coeffs = lagrange_fit(points, deg)
        if coeffs is None:
            continue
        ok = all(eval_poly(coeffs, m) == val for m, val in points)
        if ok:
            break
    
    poly_in_m[n] = coeffs
    
    # Find common denominator
    denoms = [c.denominator for c in coeffs if c != 0]
    lcd = reduce(lambda a, b: a * b // gcd(a, b), denoms, 1) if denoms else 1
    int_coeffs = [int(c * lcd) for c in coeffs]
    
    # Factor out GCD of int_coeffs
    g = reduce(gcd, [abs(x) for x in int_coeffs if x != 0], 0)
    
    print(f"\nn={n}: degree {deg} in m")
    print(f"  p_{n}(m) = {g}/{lcd} * {[x//g for x in int_coeffs]}")
    print(f"  Pre-factor: {Fraction(g, lcd)} = {g}/{lcd}")
    
    # Verify: the pre-factor should be related to factorials
    pf = Fraction(g, lcd)
    # Check against known: (2n+1)!! / something
    df = 1
    for k in range(1, 2*n + 2, 2):
        df *= k
    print(f"  (2n+1)!! = {df}")
    print(f"  p_{n}(0) = {coeffs[0]} = (2n+1)!! ? {'YES' if int(coeffs[0]) == df else 'NO'}")
    red = [x//g for x in int_coeffs]
    print(f"  Reduced polynomial: {red}")


# ─── 2. Factor the reduced polynomials ──────────────────────────────────────

print("\n\n" + "=" * 80)
print("STRUCTURE: Reduced polynomials and their factorizations")
print("=" * 80)

# Let me express p_n(m) with the (2n+1)!! factored out
print("\n--- R_n(m) = p_n^(m) / (2n+1)!! = polynomial in m of degree floor(n/2) ---")

from sympy import symbols, Rational as SR, factor, Poly, apart, prod as sprod

m_sym = symbols('m')

for n in range(N_MAX + 1):
    coeffs = poly_in_m[n]
    df = 1
    for k in range(1, 2*n + 2, 2):
        df *= k
    
    # R_n(m) = p_n(m) / (2n+1)!!
    R_coeffs = [c / Fraction(df) for c in coeffs]
    
    # Build sympy expression
    expr = sum(SR(c.numerator, c.denominator) * m_sym**k for k, c in enumerate(R_coeffs))
    
    factored = factor(expr)
    print(f"\n  n={n}: R_{n}(m) = p_{n}(m) / {df}")
    print(f"    = {expr}")
    print(f"    = {factored}")


# ─── 3. Look at the LIMIT as n→∞ ────────────────────────────────────────────

print("\n\n" + "=" * 80)
print("LIMIT ANALYSIS: val(m) = lim p_n/q_n")
print("=" * 80)

# val(m) = 2^{2m+1} / (pi * C(2m,m))
# This must arise from the polynomial structure of p_n and q_n in m.

# Key identity: val(m+1)/val(m) = 2(m+1)/(2m+1)
# Since p_n and q_n are polynomials in m, the ratio p_n/q_n 
# is a rational function of m that converges to val(m).

# Let's look at q_n^(m) as a polynomial in m too.

q_grid: dict[int, dict[int, Fraction]] = {}
for n in range(N_MAX + 1):
    q_grid[n] = {}

for m in range(M_MAX + 1):
    _, qs = compute_pq(m, N_MAX)
    for n in range(N_MAX + 1):
        q_grid[n][m] = qs[n]

print("\nq_n^(m) as polynomial in m:")
q_poly_in_m: dict[int, list[Fraction]] = {}

for n in range(min(8, N_MAX + 1)):
    points = [(m, q_grid[n][m]) for m in range(M_MAX + 1)]
    for deg in range(20):
        if deg + 1 > len(points):
            break
        coeffs = lagrange_fit(points, deg)
        if coeffs is None:
            continue
        ok = all(eval_poly(coeffs, m) == val for m, val in points)
        if ok:
            break
    
    q_poly_in_m[n] = coeffs
    print(f"\n  n={n}: q_{n}(m) is degree {deg} in m")
    
    expr = sum(SR(c.numerator, c.denominator) * m_sym**k for k, c in enumerate(coeffs))
    factored = factor(expr)
    print(f"    = {factored}")


# ─── 4. Ratio p_n/q_n as rational function of m ─────────────────────────────

print("\n\n" + "=" * 80)
print("RATIO: p_n(m)/q_n(m) as rational function of m")
print("=" * 80)

from sympy import simplify, cancel

for n in range(min(8, N_MAX + 1)):
    p_expr = sum(SR(c.numerator, c.denominator) * m_sym**k 
                 for k, c in enumerate(poly_in_m[n]))
    q_expr = sum(SR(c.numerator, c.denominator) * m_sym**k 
                 for k, c in enumerate(q_poly_in_m[n]))
    
    ratio = cancel(p_expr / q_expr)
    print(f"\n  n={n}: p_{n}/q_{n} = {ratio}")


# ─── 5. Key structural check: Pochhammer representation of p_n(m) ───────────

print("\n\n" + "=" * 80)
print("POCHHAMMER CHECK: Is p_n(m) / (2n+1)!! expressible as (a)_m / (b)_m * poly?")
print("=" * 80)

# For each n, check if p_n(m)/(2n+1)!! = f(m) has a nice form

# Observation: the numerator sequence n²+3n+1 for m=1 evaluated at..
# Actually, let's check p_n(m) / (2m+1) for the first values:

for n in [1, 3, 5, 7]:
    print(f"\n  n={n}: p_{n}(m) / (2m+1):")
    for m in range(8):
        val = p_grid[n][m]
        ratio = val / Fraction(2*m + 1)
        print(f"    m={m}: {val} / {2*m+1} = {ratio}")


# ─── 6. CRITICAL: Verify R_n(m) involves Pochhammer (1)_m type structures ───

print("\n\n" + "=" * 80)
print("RISING FACTORIAL TEST: p_n(m) / p_n(0) in terms of rising factorials of m")
print("=" * 80)

def pochhammer(a: Fraction, k: int) -> Fraction:
    r = Fraction(1)
    for j in range(k):
        r *= (a + j)
    return r

# p_n(m) / p_n(0) gives the "multiplier" as m increases
for n in range(N_MAX + 1):
    print(f"\n  n={n}:")
    p0 = p_grid[n][0]
    
    # Compute p_n(m)/p_n(0) for m=0..8
    ratios = []
    for m in range(min(10, M_MAX + 1)):
        r = p_grid[n][m] / p0
        ratios.append(r)
    
    print(f"    p_{n}(m)/p_{n}(0) = {[str(r) for r in ratios[:8]]}")
    
    # Check: is this (2m+1)!!/(2*0+1)!! * something?
    # Or: product_{j=1}^{m} (2j+2n+1) / (2n+1)?
    # Or: (n+1+m)! / ((n+1)! * something)?
    
    # Try (m + something)_m / (something)_m patterns
    # First check if consecutive ratios are nice
    if len(ratios) > 1 and ratios[0] != 0:
        print(f"    Consecutive ratios r(m+1)/r(m):")
        for m in range(min(8, len(ratios) - 1)):
            if ratios[m] != 0:
                cr = ratios[m+1] / ratios[m]
                print(f"      m={m}→{m+1}: {cr} = {float(cr):.8f}")


# ─── 7. THE SMOKING GUN: Look at p_n(m) at m = -1/2 ────────────────────────

print("\n\n" + "=" * 80)
print("SPECIAL VALUES: p_n(m) at m = -1/2, and at half-integer m")
print("=" * 80)

# Since val(m) = 2^{2m+1}/(pi*C(2m,m)), and C(2m,m) has a nice representation
# at half-integers via the Gamma function, let's evaluate the polynomial at m=-1/2

for n in range(min(10, N_MAX + 1)):
    coeffs = poly_in_m[n]
    val_at_neg_half = sum(c * Fraction(-1, 2)**k for k, c in enumerate(coeffs))
    print(f"  n={n}: p_{n}(-1/2) = {val_at_neg_half} = {float(val_at_neg_half):.6f}")


# ─── 8. Express the reduced polynomial coefficients systematically ───────────

print("\n\n" + "=" * 80)
print("COEFFICIENT TABLE: p_n(m) = c_0(n) + c_1(n)*m + c_2(n)*m^2 + ...")
print("=" * 80)

for n in range(N_MAX + 1):
    coeffs = poly_in_m[n]
    print(f"\n  n={n} (deg {len(coeffs)-1}):")
    for k, c in enumerate(coeffs):
        if c != 0:
            print(f"    c_{k}({n}) = {c}")


# Now look at c_k(n) as a function of n
print("\n\n" + "=" * 80)
print("c_k(n) AS FUNCTION OF n: Looking for factorial/Pochhammer patterns")
print("=" * 80)

max_k = max(len(poly_in_m[n]) for n in range(N_MAX + 1)) - 1

for k in range(max_k + 1):
    vals = []
    for n in range(N_MAX + 1):
        if k < len(poly_in_m[n]):
            vals.append((n, poly_in_m[n][k]))
        else:
            vals.append((n, Fraction(0)))
    
    nonzero = [(n, v) for n, v in vals if v != 0]
    if not nonzero:
        continue
    
    print(f"\n  c_{k}(n):")
    for n, v in nonzero:
        print(f"    n={n:2d}: {v}")
    
    # Check ratios c_k(n+1)/c_k(n)
    if len(nonzero) > 1:
        print(f"  Ratios c_{k}(n+1)/c_{k}(n):")
        for i in range(len(nonzero) - 1):
            n1, v1 = nonzero[i]
            n2, v2 = nonzero[i+1]
            if v1 != 0 and n2 == n1 + 1:
                print(f"    n={n1}→{n2}: {v2/v1} = {float(v2/v1):.6f}")


print("\n\nDONE.")
