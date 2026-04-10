"""
Part 3: Identify the minimal hypergeometric family for PCF(-n(2n-3), 3n+1) -> 4/pi.
Given that it is NOT a Gauss _2F1 CF, check _3F2, Euler-type, and Apery-type families.
"""
from fractions import Fraction
from math import factorial
from sympy import (symbols, solve, Rational, sqrt as ssqrt, simplify, Eq,
                   Poly, Symbol, expand, collect, factor, cancel, together,
                   gamma as sgamma, binomial, Sum, oo, S, nsimplify)
from mpmath import mp, mpf, pi, hyp2f1, hyper, nstr, log10, fac2

mp.dps = 80

# =====================================================================
print("=" * 70)
print("PART A: Structure of the recurrence")
print("=" * 70)

# Our 3-term recurrence: P_n = (3n+1)*P_{n-1} - n(2n-3)*P_{n-2}
# Characteristic: b(n) = 3n+1 (degree 1), a(n) = -n(2n-3) (degree 2)
# 
# For _pF_{p-1}(;z), the contiguous relations involve coefficients of
# degree p in n. Our a(n) has degree 2, so this is consistent with p=2
# (i.e., _2F1). BUT the Gauss CF theorem requires alternating odd/even
# formulas, and ours doesn't alternate.
#
# Key distinction: the Gauss CF is for the RATIO _2F1(.;.+1;.+1;z)/_2F1(.;.;.;z).
# A DIFFERENT CF arises for _2F1 via EULER'S continued fraction:
# If sum c_n z^n = c_0 + c_1*z + c_2*z^2 + ..., then
# sum c_n z^n = c_0/(1 - (c_1/c_0)*z/(1 - ((c_2/c_1 - c_1/c_0)z)/(1 + ...)))
#
# For _2F1(a,b;c;z) = sum (a)_n(b)_n/((c)_n * n!) * z^n,
# the ratio c_{n+1}/c_n = (a+n)(b+n)/((c+n)(n+1)) * z
# This gives rise to Euler's CF with coefficients involving these ratios.

print("\nEuler CF coefficients for _2F1(a,b;c;z):")
print("  c_{n+1}/c_n = (a+n)(b+n)z / ((c+n)(n+1))")
print("  Euler CF first quotients:")
print("    e_0 = c_0 = 1")
print("    e_1 = c_1/c_0 = ab*z/c")
print("    e_2 = c_2/c_1 - c_1/c_0 = [(a+1)(b+1)z/((c+1)*2)] - [abz/c]")
print()

# Our CF has a SINGLE formula for all n, suggesting it may arise from
# a different mechanism. Let me check the EULER CF (not Gauss CF).

# The Euler CF for a power series f = sum c_n z^n is:
# f = c_0 / (1 - d_1*z / (1 + d_1*z - d_2*z / (1 + d_2*z - d_3*z / ...)))
# where d_n = c_n / c_{n-1} (ratios of successive Taylor coefficients).
#
# Actually, the standard Euler CF is:
# f(z)/f(0) = 1/(1 - a_1*z/(1 - a_2*z/(1 - ...)))
# This is an S-fraction, and for _2F1 it IS the Gauss CF.

# So the question becomes: is there a DIFFERENT CF representation of _2F1
# that uses a single formula for all partial quotients?

# YES: the NORLUND continued fraction / T-fraction / M-fraction.
# For functions satisfying a 3-term recurrence with polynomial coefficients,
# there is a corresponding CF where the coefficients come from the recurrence.

# Our recurrence P_n = (3n+1)P_{n-1} - n(2n-3)P_{n-2} with P_0=1, P_{-1}=0.
# This is the recurrence for the DENOMINATORS of our CF.
# The associated function is:
# f(x) = sum_{n=0}^inf P_n * x^n  (generating function of denominators)
# which satisfies a differential equation related to the recurrence.

print("\n" + "=" * 70)
print("PART B: Connection to _2F1 via generating function")
print("=" * 70)

# Our denominator sequence Q_n satisfies:
# Q_n = (3n+1)Q_{n-1} - n(2n-3)Q_{n-2}, Q_0=1, Q_1=4
# (from b(0)=1, b(1)=4, a(1)=1)
#
# Actually, let me recompute Q_n properly.
# CF: 1 + 1/(4 + (-2)/(7 + (-9)/(10 + ...)))
# Recurrence: Q_n = b(n)*Q_{n-1} + a(n)*Q_{n-2}
# Q_{-1} = 0, Q_0 = 1.
# Q_1 = b(1)*Q_0 + a(1)*Q_{-1} = 4*1 + 1*0 = 4
# Q_2 = b(2)*Q_1 + a(2)*Q_0 = 7*4 + (-2)*1 = 26
# Q_3 = b(3)*Q_2 + a(3)*Q_1 = 10*26 + (-9)*4 = 260 - 36 = 224

qvals = [1]  # Q_0
qm1 = 0  # Q_{-1}
for n in range(1, 20):
    bn = 3*n + 1
    an = -n * (2*n - 3)
    qn = bn * qvals[-1] + an * qm1
    qm1 = qvals[-1]
    qvals.append(qn)

print("\nQ_n sequence (CF denominators):")
for n in range(15):
    print(f"  Q_{n:2d} = {qvals[n]}")

# Factor the Q_n: try Q_n / n! or Q_n / (2n)!! etc.
print("\nQ_n / n!:")
for n in range(12):
    r = Fraction(qvals[n], factorial(n))
    print(f"  Q_{n}/n! = {r} = {float(r):.8f}")

# Q_0/0! = 1, Q_1/1! = 4, Q_2/2! = 13, Q_3/3! = 112/6 = 56/3...
# Not clean. Try Q_n / (2n+1)!!:
def dff(n):
    r = 1
    for j in range(1, 2*n+2, 2):
        r *= j
    return r

print("\nQ_n / (2n+1)!!:")
for n in range(12):
    d = dff(n)
    r = Fraction(qvals[n], d)
    print(f"  Q_{n}/(2n+1)!! = {r}")

# Not clean either. Let me try a different normalization.
# What about Q_n * (something) = _2F1-value?

# Actually, let me check: does Q_n/Q_{n-1} approach a limit?
print("\nQ_n/Q_{n-1}:")
for n in range(1, 15):
    r = Fraction(qvals[n], qvals[n-1])
    print(f"  Q_{n}/Q_{n-1} = {float(r):.10f}")
# This should approach the larger root of the characteristic equation of the
# asymptotic recurrence. For large n, recurrence ~ 3n*Q - 2n^2*Q => Q ~ 2n.

# =====================================================================
print("\n" + "=" * 70)
print("PART C: Series expansion approach")
print("=" * 70)

# If C_n = P_n/Q_n -> 4/pi, then pi/4 = lim Q_n/P_n.
# The partial sums S_n = P_n/Q_n form a sequence approaching 4/pi.
# S_n = S_0  + sum_{k=1}^{n} delta_k where delta_k = D_k/(Q_k*Q_{k-1})
# and D_k = prod_{j=1}^{k} (-a_j) = prod_{j=1}^k j(2j-3).

# Let's compute the series for pi/4 = 1/CF = 1/(4/pi):
# Actually CF = 4/pi, so our convergent S_n -> 4/pi.
# The series is: 4/pi = 1 + sum_{n=1}^inf delta_n
# where delta_n = D_n / (Q_n * Q_{n-1})
# and D_n = (-1)^n * prod_{j=1}^n a_j (scaled).

# D_n = det = P_n*Q_{n-1} - P_{n-1}*Q_n
# For our CF: D_n = prod_{k=1}^n (-a_k) = prod_{k=1}^n k(2k-3)
# = n! * prod_{k=1}^n (2k-3)

print("Series: 4/pi = sum_{n=0}^inf delta_n where delta_0 = 1")
print("  delta_n = n! * prod_{k=1}^{n}(2k-3) / (Q_n * Q_{n-1})")
print()

# Compute D_n:
for n in range(1, 15):
    Dn = factorial(n)
    p = 1
    for k in range(1, n+1):
        p *= (2*k - 3)
    Dn *= p
    delta = Fraction(Dn, qvals[n] * qvals[n-1])
    print(f"  delta_{n:2d} = {float(delta):.15e}  ({delta.numerator}/{delta.denominator})")

# Now: can we identify these delta_n as the coefficients of a known _2F1 series?
# delta_n = n! * prod(2k-3) / (Q_n*Q_{n-1})
# We need the exact Q_n to factor this.

# Let me try a completely different approach: check if Q_n satisfies
# a differential equation via generating function.

# =====================================================================
print("\n" + "=" * 70)
print("PART D: _2F1 representation via hypergeometric identity test")
print("=" * 70)

# Strategy: compute 4/pi as _2F1 values and check if our CF convergents
# match the partial sums of that series.
#
# Known: 4/pi = sum_{n=0}^inf C(2n,n)^2 * (4n+1) / 16^n  [Ramanujan-type]
# or:    4/pi = sum (-1)^n (1/2)_n^2 / (n!)^2 [this is _2F1(1/2,1/2;1;-1)]
#        Wait: _2F1(1/2,1/2;1;1) diverges but _2F1(1/2,1/2;1;-1) converges.

mp.dps = 80
# Test: _2F1(1/2, 1/2; 1; -1)
val = hyp2f1(0.5, 0.5, 1, -1)
print(f"  _2F1(1/2,1/2;1;-1)        = {nstr(val, 30)}")
print(f"  4/pi                       = {nstr(4/pi, 30)}")

# Actually: _2F1(1/2,1/2;1;z) = (2/pi)*K(z) where K is complete elliptic integral
# _2F1(1/2,1/2;1;-1) = (2/pi)*K(-1)? Let's check.
# K(k) = (pi/2) * _2F1(1/2,1/2;1;k^2), so _2F1(1/2,1/2;1;-1) is not directly K.

# Numerically: _2F1(1/2,1/2;1;-1) = 0.8346... which is not 4/pi = 1.2732...

# What about _2F1(-1/2, 1/2; 1; -1)?
val2 = hyp2f1(-0.5, 0.5, 1, -1)
print(f"  _2F1(-1/2,1/2;1;-1)       = {nstr(val2, 30)}")

# _2F1(1/2, -1/2; 1; 1)? (AGM-related)
# Gauss formula: _2F1(a,b;c;1) = Gamma(c)Gamma(c-a-b)/(Gamma(c-a)Gamma(c-b))
# when c-a-b > 0.
# _2F1(1/2,-1/2;1;1) = Gamma(1)*Gamma(1)/(Gamma(1/2)*Gamma(3/2))
# = 1 / (sqrt(pi) * sqrt(pi)/2) = 1 / (pi/2) = 2/pi
val3 = hyp2f1(0.5, -0.5, 1, 1)
print(f"  _2F1(1/2,-1/2;1;1)        = {nstr(val3, 30)}")
print(f"  2/pi                       = {nstr(2/pi, 30)}")

# So 4/pi = 2 * _2F1(1/2,-1/2;1;1)
# Also: _2F1(1/2,-1/2;1;1) = sum_{n=0}^inf (1/2)_n*(-1/2)_n/(n!)^2
# = sum_{n=0}^inf (-1)^n * (1/2)_n^2 * (-1)/(2n-1) ... no, let me compute directly.

# (1/2)_n(-1/2)_n = product_{k=0}^{n-1} (1/2+k)(-1/2+k)
# = product (k+1/2)(k-1/2) = product (k^2-1/4)
# For n=0: 1, n=1: (1/2)(-1/2) = -1/4, n=2: (-1/4)(3/2)(1/2) = (-1/4)(3/4) = -3/16
# Hmm: _2F1(1/2,-1/2;1;1) = sum (-1/4)^n * ??? Let me just use the formula.

# The series: _2F1(1/2,-1/2;1;z) = sum C(2n,n)(-z)^n/(4^n*(2n-1)) ... no.
# Actually: (1/2)_n = (2n)!/(4^n*n!), (-1/2)_n = (-1)^n(2n)!/(4^n*n!*(2n-1)*... )
# Complicated. Let me just verify numerically.

print(f"\n  2 * _2F1(1/2,-1/2;1;1)    = {nstr(2*val3, 30)}")
print(f"  4/pi                       = {nstr(4/pi, 30)}")
print(f"  Match? {abs(2*val3 - 4/pi) < mpf(10)**(-40)}")

# YES! 4/pi = 2*_2F1(1/2,-1/2;1;1). So the series for 4/pi is:
# 4/pi = 2 * sum_{n=0}^inf (1/2)_n*(-1/2)_n / (n!)^2
# = 2 * sum_{n=0}^inf (1/2)_n*(-1/2)_n / (1)_n^2  (since (1)_n = n!)

# Now check: does our CF S_n match partial sums of this series?

print("\nPartial sums of 2*_2F1(1/2,-1/2;1;1):")
from mpmath import rf  # rising factorial / Pochhammer
accum = mpf(0)
for n in range(15):
    term = 2 * rf(mpf(0.5), n) * rf(mpf(-0.5), n) / (rf(mpf(1), n))**2
    accum += term
    print(f"  S_{n:2d} = {nstr(accum, 18)}")

# Compare with CF convergents:
pvals = [1]  # P_0
pm1 = 0  # P_{-1}
qvals2 = [1]  # Q_0
qm12 = 0
for n in range(1, 20):
    bn = 3*n + 1
    an = -n * (2*n - 3)
    pn = bn * pvals[-1] + an * pm1
    qn = bn * qvals2[-1] + an * qm12
    pm1 = pvals[-1]
    qm12 = qvals2[-1]
    pvals.append(pn)
    qvals2.append(qn)

print("\nCF convergents P_n/Q_n:")
for n in range(15):
    cn = Fraction(pvals[n], qvals2[n])
    print(f"  C_{n:2d} = {float(cn):.18f}")

# These are DIFFERENT sequences! The CF convergents and the _2F1 partial sums
# converge to the same value but through different paths.

# =====================================================================
print("\n" + "=" * 70)
print("PART E: Check Apery-like / Zudilin CF families")
print("=" * 70)

# Our recurrence: P_n = (3n+1)*P_{n-1} - n(2n-3)*P_{n-2}
# Compare with Apery: P_n = (11n^2+11n+3)*P_{n-1} + n^4*P_{n-2} -> zeta(3)
# Our coefficients are much simpler: degree 1 and degree 2.

# Check: is (3n+1) a known beta-coefficient in any CF tables?
# The factor (3n+1) appears in Ramanujan's formulas for 1/pi.
# Specifically: 1/pi = sum (-1)^n (6n)!/(3n)!(n!)^3 * A / B^n
# where A involves (3n+1)-type terms.

# Also: Guillera's series for 1/pi^2 involve (3n+1).

# Let me check: is our CF the Euler CF for the series
# sum_{n=0}^inf a_n where a_n gives 4/pi?

# The WALLIS-type CF for pi:
# 4/pi = 1 + 1^2/(2 + 3^2/(2 + 5^2/(2 + ...)))  -- not our form.

# Let's try: does our CF correspond to the Stieltjes CF for some function?
# The Stieltjes CF for integral_0^inf dmu(t)/(z-t) gives a CF with
# real positive partial quotients. Ours has negative a(n), so not directly Stieltjes.

# KEY INSIGHT: Let me check if the recurrence comes from 
# summing a specific hypergeometric series term-by-term.
# If S_n = sum_{k=0}^n t_k where 4/pi = sum_{k=0}^inf t_k,
# and t_k = f(k) / [Q_k * Q_{k-1}], then the recurrence for Q_k
# encodes the ratio t_{k+1}/t_k.

# The standard connection: for a series sum t_n, the CF convergents
# C_n = S_n (partial sums) if and only if the CF comes from the
# Euler-Minding expansion of the series.
# In that case, the CF coefficients are:
# a_1 = t_1/t_0, a_n = -t_n*t_{n-2}/t_{n-1}^2 for n >= 2 (roughly).

# Let me identify: what series gives our CF via Euler's expansion?
# Our delta_n = D_n/(Q_n*Q_{n-1}) was computed above. Let me find the
# RATIO delta_{n+1}/delta_n and see if it matches a known term ratio.

print("\nRatio delta_{n+1}/delta_n:")
deltas = []
for n in range(20):
    if n == 0:
        Dn = 1  # D_0 = 1 (convention)
        delta = Fraction(1)
    else:
        Dn = factorial(n)
        p = 1
        for k in range(1, n+1):
            p *= (2*k - 3)
        Dn *= p
        delta = Fraction(Dn, qvals2[n] * qvals2[n-1])
    deltas.append(delta)

for n in range(1, 15):
    r = deltas[n] / deltas[n-1]
    print(f"  delta_{n}/delta_{n-1} = {float(r):.15f}  ({r})")

# Look for pattern in the ratios: if the ratio is (An+B)/(Cn+D), then
# the series is hypergeometric.
print("\nChecking if ratios are of the form (An^2+Bn+C)/(Dn^2+En+F):")
for n in range(1, 12):
    r = deltas[n] / deltas[n-1]
    # Try to express as polynomial ratio
    # For each n, r = P(n)/Q(n) where we know exact values
    print(f"  n={n:2d}: {r.numerator}/{r.denominator}")

# Let me try to identify the series directly.
# 4/pi = delta_0 + delta_1 + delta_2 + ...
# delta_0 = 1
# delta_1 = 1/4
# delta_2 = 1/52
# delta_3 = 9/2912
# Let me find a pattern for delta_n.

# Exact delta_n values:
print("\nExact delta_n values:")
for n in range(12):
    print(f"  delta_{n:2d} = {deltas[n]}")

# 1, 1/4, 1/52, 9/2912, 45/66976, ...
# Numerators: 1, 1, 1, 9, 45, 525, 945, 6615, 28665, ...
# Hmm, let me look at numerators differently.

# D_n = n! * prod(2k-3, k=1..n) = n! * (-1)(1)(3)(5)...(2n-3)
# For n>=2: = n! * (-1) * (2n-3)!! / 1 = -n! * (2n-3)!!
# (since (2n-3)!! for the part from k=2..n, times (-1) for k=1)

# D_1 = 1! * (-1) = -1
# |D_1| = 1
# D_2 = 2! * (-1)(1) = -2
# |D_2| = 2
# D_3 = 3! * (-1)(1)(3) = -18
# |D_3| = 18

# delta_n = D_n / (Q_n * Q_{n-1})
# The sign alternates: delta_0=1 > 0, delta_1=1/4 > 0, 
# delta_2 = 1/52... wait they're all positive from the output?
# Oh D_n = P_n*Q_{n-1} - P_{n-1}*Q_n and the signs work out.

# Let me check if the series sum delta_n matches KNOWN series for 4/pi.

# Ramanujan-type series for 4/pi:
# 4/pi = sum_{n=0}^inf (-1/4)^n * C(2n,n)^2 * (4n+1) [Bauer, 1859]
# = 1 + (-1/4)(2)(5) + (1/16)(6)(9) + ...
# = 1 - 5/4 + 54/64 + ... no that doesn't match.

# Actually: 4/pi = sum_{n=0}^inf (1/2)_n^2 / (n!)^2 * (4n+1) * (-1)^n
# Wait, let me compute this properly.

print("\n\nBauer series: 4/pi = sum (-1)^n * C(2n,n)^2 / 16^n * (4n+1)")
accum = mpf(0)
for n in range(20):
    from math import comb
    term = mpf((-1)**n * comb(2*n, n)**2) / mpf(16)**n * (4*n + 1)
    accum += term
    if n < 12:
        print(f"  n={n:2d}: term = {nstr(term, 15)},  partial sum = {nstr(accum, 18)}")

print(f"  Bauer sum (20 terms) = {nstr(accum, 30)}")
print(f"  4/pi                 = {nstr(4/pi, 30)}")

# Check: are the PARTIAL SUMS of the Bauer series equal to our CF convergents?
print("\nCompare Bauer partial sums vs CF convergents:")
bauer_sum = mpf(0)
for n in range(12):
    term = mpf((-1)**n * comb(2*n, n)**2) / mpf(16)**n * (4*n + 1)
    bauer_sum += term
    cf_conv = float(Fraction(pvals[n], qvals2[n]))
    print(f"  n={n:2d}: Bauer S_n = {nstr(bauer_sum, 15)},  CF C_n = {cf_conv:.15f}  {'MATCH' if abs(float(bauer_sum) - cf_conv) < 1e-14 else 'DIFFER'}")

# =====================================================================
print("\n" + "=" * 70)
print("PART F: Zeilberger/WZ certificate approach")
print("=" * 70)

# The CF denominator satisfies Q_n = (3n+1)Q_{n-1} - n(2n-3)Q_{n-2}.
# If Q_n = sum_k F(n,k), then the recurrence comes from a WZ pair.
# Let's check: does Q_n have a binomial sum representation?

# Q_n values: 1, 4, 26, 224, 2392, 30432, 449040, 7535616, 141690240, ...
# Factor: 1, 4, 26, 224=2^5*7, 2392=2^3*13*23, 30432=2^5*3*317.5... no
# 30432 = 2^5 * 951 = 32 * 951. 951 = 3*317. Hmm.
# 449040 = 2^4 * 3 * 5 * 11 * 17 * ... let me just factor.

print("Q_n factorizations:")
from sympy import factorint
for n in range(12):
    f = factorint(abs(qvals2[n]))
    fstr = " * ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in sorted(f.items()))
    print(f"  Q_{n:2d} = {qvals2[n]:>15d} = {fstr}")

# =====================================================================
print("\n" + "=" * 70)
print("PART G: Direct verification - is this Apery's method applied to pi?")
print("=" * 70)

# In Apery's proof of irr(zeta(3)), the key recurrence is:
# (n+1)^3 u_{n+1} = (2n+1)(17n^2+17n+5) u_n - n^3 u_{n-1}
# with u_n = sum_k C(n,k)^2*C(n+k,k)^2 (Apery numbers).
#
# Our recurrence: P_n = (3n+1)P_{n-1} - n(2n-3)P_{n-2}
# This is MUCH simpler (degree 1 and 2 vs degree 3 and 3).
#
# The recurrence (3n+1)u_n - n(2n-3)u_{n-1} = 0 is a first-order recurrence
# solved by u_n = u_0 * prod_{k=1}^n k(2k-3)/(3k+1).
# Our 3-term recurrence uses this as the "a(n)" coefficient.

# Let me check if Q_n = sum_k C(n,k) * (something).
# Try Q_n = sum_k C(n,k) * C(n+k,k) or similar.

print("Checking binomial sum representations for Q_n:")
from math import comb

# Test: Q_n = sum_{k=0}^n C(n,k)^2
for n in range(8):
    s = sum(comb(n,k)**2 for k in range(n+1))
    print(f"  n={n}: sum C(n,k)^2 = {s},  Q_n = {qvals2[n]},  {'MATCH' if s == qvals2[n] else ''}")

# Test: Q_n = sum_{k=0}^n C(n,k) * C(n+k,k)
for n in range(8):
    s = sum(comb(n,k) * comb(n+k,k) for k in range(n+1))
    print(f"  n={n}: sum C(n,k)*C(n+k,k) = {s},  Q_n = {qvals2[n]},  {'MATCH' if s == qvals2[n] else ''}")

# Test: Q_n = sum_{k=0}^n C(2k,k) * something
print("\nQ_n / C(2n,n):")
for n in range(10):
    c2n = comb(2*n, n)
    r = Fraction(qvals2[n], c2n)
    print(f"  n={n}: Q_{n}/C(2n,n) = {r}")

# Another idea: the sequence Q_n matches OEIS?
print("\nSearch: Q_n = 1, 4, 26, 224, 2392, 30432, 449040, 7535616, 141690240")
print("Likely OEIS: A??? - need to check manually")

# Let me try one more: Q_n related to (2n)!! = 2^n * n!
print("\nQ_n / (2n)!!:")
for n in range(10):
    d = 2**n * factorial(n) if n > 0 else 1
    r = Fraction(qvals2[n], d)
    print(f"  n={n}: Q_{n}/(2^n*n!) = {r}")

# Q_0 = 1, Q_1/2 = 2, Q_2/8 = 13/4, Q_3/48 = 14/3, ...
# Try: Q_n / ((2n)! / n!) = Q_n * n! / (2n)!
print("\nQ_n * n! / (2n)!:")
for n in range(10):
    d = factorial(2*n) // factorial(n) if n > 0 else 1
    r = Fraction(qvals2[n], d)
    print(f"  n={n}: Q_{n}/((2n)!/n!) = {r}")
