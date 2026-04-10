#!/usr/bin/env python3
"""Compute val(m) for the Pi Family and verify ratio pattern."""
import math
from mpmath import mp, mpf, pi as mpi

mp.dps = 50

vals = []
for m in range(16):
    N = 500
    val = mpf(3*N + 1)
    for n in range(N-1, 0, -1):
        a_n1 = -mpf(n+1) * (2*(n+1) - 2*m - 1)
        b_n = mpf(3*n + 1)
        val = b_n + a_n1 / val
    a1 = -mpf(1) * (2 - 2*m - 1)
    S = mpf(1) + a1 / val
    vals.append(S)
    print(f"m={m:2d}: val(m) = {mp.nstr(S, 25)}")

print()
print("Ratios val(m+1)/val(m):")
for m in range(15):
    r = vals[m+1] / vals[m]
    expected = mpf(2*(m+1)) / mpf(2*m + 1)
    diff = abs(r - expected)
    print(f"  val({m+1})/val({m}) = {mp.nstr(r, 20)}  expected {mp.nstr(expected, 20)}  diff={mp.nstr(diff, 3)}")

print()
print("Closed form check: val(m) = (2/pi) * 2^m * m! / (2m-1)!!:")
for m in range(8):
    dff_val = 1
    for k in range(1, 2*m, 2):
        dff_val *= k
    predicted = mpf(2)/mpi * mpf(2**m * math.factorial(m)) / mpf(dff_val)
    print(f"  m={m}: val={mp.nstr(vals[m], 15)}, pred={mp.nstr(predicted, 15)}, match={abs(vals[m] - predicted) < mpf(10)**(-40)}")

# Now prove the ratio algebraically.
# The CF for family m has a_m(n) = -n(2n-2m-1).
# Consider the recurrence: P_n = (3n+1) P_{n-1} + a_m(n) P_{n-2}
# For families m and m+1, the only difference is a_m vs a_{m+1}:
#   a_m(n) = -n(2n - 2m - 1)
#   a_{m+1}(n) = -n(2n - 2m - 3) = a_m(n) + 2n
#
# Key insight: the REDUCED recurrence after P_n = (2n-2m-1)!! u_n is:
#   For family m: (2n-2m-1) u_n = (3n+1) u_{n-1} - n u_{n-2}
# Wait, the double factorial factor changes with m!
#
# Let me verify: for general m, P_n = (3n+1) P_{n-1} - n(2n-2m-1) P_{n-2}
# The polynomial solution h_n^(m) - does it change with m?
print()
print("Polynomial solutions h_n^(m) for different m:")
for m in range(5):
    # Compute p_n via recurrence, check if p_n / double_fac has polynomial form
    N = 10
    p = [1, 1]  # p_{-1}, p_0
    for n in range(1, N+1):
        a_n = -n * (2*n - 2*m - 1)
        b_n = 3*n + 1
        p.append(b_n * p[-1] + a_n * p[-2])
    # p[k+1] = p_k (offset by 1)
    # h_n = p_n / (2n-2m-1)!! -- but the double factorial changes
    # For m=0: (2n-1)!!, for m=1: (2n-3)!!, for m=2: (2n-5)!!
    print(f"  m={m}: p_n = {[p[k+1] for k in range(8)]}")
    # Compute the double factorial prefix
    dfac = []
    for n in range(8):
        d = 1
        top = 2*n - 2*m - 1
        if top >= 1:
            for k in range(1, top+1, 2):
                d *= k
        elif top <= -1:
            # (-1)!! = 1, (-3)!! = -1, etc.
            d = 1  # convention
            for k in range(-1, top-1, -2):
                d *= k
                # Actually (2n-2m-1)!! for n < m needs care
        dfac.append(d)
    print(f"         (2n-2m-1)!! = {dfac}")
    h = []
    for n in range(8):
        if dfac[n] != 0:
            h.append(p[n+1] / dfac[n])
        else:
            h.append("undef")
    print(f"         h_n = p_n/(2n-2m-1)!! = {h}")
