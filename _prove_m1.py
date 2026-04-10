"""Prove P_n closed form by induction verification and find Q_n."""
from fractions import Fraction
from math import prod, factorial

def dbl_fac(n):
    if n <= 0: return 1
    return prod(range(n, 0, -2))

# P_n^(1) claim: P_n = (2n-1)!! * (n^2+3n+1) for n >= 1, P_0 = 1
# Recurrence: P_n = (3n+1)*P_{n-1} - n(2n-3)*P_{n-2}
# 
# INDUCTION PROOF:
# Assume P_{n-1} = (2n-3)!! * ((n-1)^2+3(n-1)+1) = (2n-3)!! * (n^2+n-1)
#        P_{n-2} = (2n-5)!! * ((n-2)^2+3(n-2)+1) = (2n-5)!! * (n^2-n-1)
#
# Then: b(n)*P_{n-1} + a(n)*P_{n-2}
#      = (3n+1)*(2n-3)!!*(n^2+n-1) - n(2n-3)*(2n-5)!!*(n^2-n-1)
#
# Factor out (2n-5)!!:
# (2n-3)!! = (2n-3)*(2n-5)!!
# = (3n+1)(2n-3)(2n-5)!!*(n^2+n-1) - n(2n-3)(2n-5)!!*(n^2-n-1)
# = (2n-3)(2n-5)!! * [(3n+1)(n^2+n-1) - n(n^2-n-1)]
# = (2n-3)(2n-5)!! * [3n^3+3n^2-3n+n^2+n-1 - n^3+n^2+n]
# = (2n-3)(2n-5)!! * [2n^3+5n^2-n-1]
#
# Factor 2n^3+5n^2-n-1:
# = (2n-1)(n^2+3n+1)  [check: (2n-1)(n^2+3n+1) = 2n^3+6n^2+2n-n^2-3n-1 = 2n^3+5n^2-n-1]
#
# So: = (2n-3)(2n-5)!! * (2n-1) * (n^2+3n+1) 
#     = (2n-1)!! * (n^2+3n+1)  
#     = P_n. QED!

# Let me verify the algebra step by step
print("=== ALGEBRAIC VERIFICATION ===")
for n in range(2, 15):
    # LHS
    lhs = (3*n+1)*(n*n+n-1) - n*(n*n-n-1)
    # Should equal (2*n-1)*(n*n+3*n+1)
    rhs = (2*n-1)*(n*n+3*n+1)
    print(f"  n={n}: (3n+1)(n^2+n-1) - n(n^2-n-1) = {lhs}  vs  (2n-1)(n^2+3n+1) = {rhs}  {'OK' if lhs==rhs else 'FAIL'}")

# Now the Q_n analysis using the determinant identity
# det_n = P_n*Q_{n-1} - P_{n-1}*Q_n = (-1)^n * prod(a(j), j=1..n)
# where a(j) = -j(2j-3)
# prod(a(j)) = prod(-j(2j-3)) = (-1)^n * n! * prod(2j-3,j=1..n)
# prod(2j-3,j=1..n): -1, 1, 3, 5, ..., 2n-3
# = (-1) * (2n-3)!! for n >= 2
# So prod(a(j)) = (-1)^n * n! * (-1) * (2n-3)!! = (-1)^{n+1} * n! * (2n-3)!!
# 
# And det_n = (-1)^n * prod(a(j)) ... wait, let me be careful.
# Standard: p_n*q_{n-1} - p_{n-1}*q_n = (-1)^{n+1} * prod_{j=1}^n a_j
# Here a_j = -j(2j-3)
# So det_n = (-1)^{n+1} * prod_{j=1}^n [-j(2j-3)]
# = (-1)^{n+1} * (-1)^n * n! * prod(2j-3)
# = (-1)^{2n+1} * n! * prod(2j-3)
# = -n! * prod(2j-3, j=1..n)
# prod(2j-3, j=1..n) for n=1: -1; n=2: -1*1=-1; n=3: -1*1*3=-3; etc.
# 
# T_n - T_{n-1} = Q_n/P_n - Q_{n-1}/P_{n-1} 
# = (Q_n*P_{n-1} - Q_{n-1}*P_n) / (P_n*P_{n-1})
# = -det_n / (P_n*P_{n-1})  [note sign]
# = n! * prod(2j-3) / (P_n*P_{n-1})

P = [Fraction(0)]*25; Q = [Fraction(0)]*25
P[0] = Fraction(1); P[1] = Fraction(1)
Q[0] = Fraction(0); Q[1] = Fraction(1)
for n in range(1, 22):
    P[n+1] = (3*n+1)*P[n] + (-n*(2*n-3))*P[n-1]
    Q[n+1] = (3*n+1)*Q[n] + (-n*(2*n-3))*Q[n-1]

print("\n=== SUMMAND FACTORING ===")
print("T_n = Q_n/P_n, delta_n = T_n - T_{n-1}")
print("Claim: delta_n = C * n! * prod(2j-3) / ((2n-1)!!*(n^2+3n+1) * (2n-3)!!*((n-1)^2+3(n-1)+1))")
accumT = Fraction(0)
for n in range(15):
    Tn = Fraction(Q[n+1], P[n+1])
    delta = Tn - accumT
    accumT = Tn
    
    # Simplify delta for small n
    if n <= 1:
        print(f"  n={n}: delta = {delta}")
        continue
    
    # Using P_n = (2n-1)!!(n^2+3n+1), P_{n-1} = (2n-3)!!((n-1)^2+3(n-1)+1) = (2n-3)!!(n^2+n-1)
    pn = dbl_fac(2*n-1) * (n*n+3*n+1)
    pn1 = dbl_fac(2*n-3) * (n*n+n-1) if n >= 2 else 1
    
    # delta = -det_n / (P_n * P_{n-1})
    # det_n = -n! * prod(2j-3, j=1..n) (from above)
    p2j3 = prod(2*j-3 for j in range(1, n+1))
    numer = factorial(n) * p2j3  # = -(-det_n)
    denom = pn * pn1
    
    ratio = Fraction(numer, denom)
    print(f"  n={n}: delta={float(delta):.15f}  n!*prod(2j-3)/(P_n*P_{{n-1}})={float(ratio):.15f}  match={delta==ratio}")

# So T_n = sum_{j=0}^{n} delta_j -> pi/4
# = 1 + (-1/5) + sum_{j=2}^{n} j! * prod(2k-3,k=1..j) / (P_j * P_{j-1})
print("\n=== LIMIT VERIFICATION ===")
from decimal import Decimal, getcontext
getcontext().prec = 50
Tn = Fraction(Q[21], P[21])
approx = float(Tn)
pi_over_4 = 3.14159265358979323846264 / 4
print(f"T_20 = {approx:.20f}")
print(f"pi/4 = {pi_over_4:.20f}")
print(f"Agreement: {-Decimal(str(abs(approx - pi_over_4))).log10():.1f} digits")
