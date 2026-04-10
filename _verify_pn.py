"""Verify P_n closed form for m=1 pi family."""
from fractions import Fraction
from math import prod

def dbl_fac(n):
    if n <= 0: return 1
    return prod(range(n, 0, -2))

P = [Fraction(0)]*25
P[0] = Fraction(1); P[1] = Fraction(1)
Q = [Fraction(0)]*25
Q[0] = Fraction(0); Q[1] = Fraction(1)
for n in range(1, 22):
    P[n+1] = (3*n+1)*P[n] + (-n*(2*n-3))*P[n-1]
    Q[n+1] = (3*n+1)*Q[n] + (-n*(2*n-3))*Q[n-1]

# Extract f_n where P_n/(2n+1)!! = f_n / (2n+1)
fvals = []
for n in range(15):
    r = P[n+1] / Fraction(dbl_fac(2*n+1))
    fvals.append(r.numerator)
    
print("f_n sequence:", fvals)
print("Diffs:", [fvals[i+1]-fvals[i] for i in range(13)])
# f(n) = n^2 + 3n + 1: check
print("\n=== P_n = (2n-1)!! * (n^2+3n+1) ===")
all_ok = True
for n in range(20):
    actual = int(P[n+1])
    if n == 0:
        formula = 1
    else:
        formula = dbl_fac(2*n-1) * (n*n + 3*n + 1)
    ok = (actual == formula)
    if not ok:
        all_ok = False
    if n < 12:
        print(f"  n={n:2d}: actual={actual:>18d}  formula={formula:>18d}  {'OK' if ok else 'FAIL'}")
print(f"  All n=0..19: {'ALL MATCH' if all_ok else 'FAILURES FOUND'}")

# Q_n: use determinant identity
# C_n - C_{n-1} = (-1)^{n+1} * prod(a(j), j=1..n) / (Q_n * Q_{n-1})
# For summation form T_n = Q_n / P_n -> pi/4
# T_n - T_{n-1} = det_n / (P_n * P_{n-1})
# where det_n = Q_n*P_{n-1} - Q_{n-1}*P_n = (-1)^{n-1} * prod(a(j), j=1..n)
print("\n=== Determinant analysis ===")
for n in range(1, 12):
    det = Q[n+1]*P[n] - Q[n]*P[n+1]
    # a(j) = -j*(2j-3), prod = (-1)^n * prod(j*(2j-3))
    # prod j = n!, prod(2j-3) for j=1..n: -1,1,3,5,...,2n-3
    aprod = Fraction(1)
    for j in range(1, n+1):
        aprod *= (-j*(2*j-3))
    # det should = (-1)^{n+1} * aprod? Or just aprod?
    # Standard: p_n*q_{n-1} - p_{n-1}*q_n = (-1)^{n+1} * prod(a_j)
    # So Q_n*P_{n-1} - Q_{n-1}*P_n = (-1)^n * (p_n*q_{n-1} - p_{n-1}*q_n) ... 
    # Actually it's simpler: det_n = prod(a(j), j=1..n) from the recurrence
    print(f"  n={n}: det={int(det):>18d}  prod(a(j))={int(aprod):>18d}  match={det==aprod}")

# Now T_n - T_{n-1} = det_n / (P_n * P_{n-1})
# = prod(a(j)) / (P_n * P_{n-1})
print("\n=== Summand f(n) = delta(T_n) in T_n = sum f(j) -> pi/4 ===")
for n in range(1, 12):
    delta = Fraction(Q[n+1], P[n+1]) - Fraction(Q[n], P[n])
    # Using P_n = (2n-1)!!(n^2+3n+1) for n>=1:
    # delta = prod(a(j),j=1..n) / (P_n * P_{n-1})
    # = prod(-j(2j-3)) / ((2n-1)!!(n^2+3n+1) * (2n-3)!!((n-1)^2+3(n-1)+1))
    # Simplify the product prod(-j(2j-3), j=1..n)
    # = (-1)^n * n! * prod(2j-3, j=1..n)
    # prod(2j-3) for j=1..n: when j=1: -1, j=2: 1, j=3: 3, ...j=n: 2n-3
    # = (-1) * 1 * 3 * ... * (2n-3) = -(2n-3)!! for n>=2
    print(f"  n={n}: delta = {delta}  ~= {float(delta):.15f}")
