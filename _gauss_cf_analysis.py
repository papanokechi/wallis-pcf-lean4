"""
Identify whether PCF(-n(2n-3), 3n+1) -> 4/pi is a Gauss CF specialization.
"""
from fractions import Fraction
from math import factorial, gcd
from functools import reduce
from mpmath import mp, mpf, pi, gamma, hyp2f1, nstr, log10, sqrt, fac

mp.dps = 80

# ── helpers ──────────────────────────────────────────────────────────────
def dff(n):
    """(2n-1)!! with (-1)!!=1"""
    r = 1
    for j in range(1, 2*n, 2):
        r *= j
    return r

def pochhammer_exact(a_num, a_den, n):
    """(a)_n as exact Fraction, a = a_num/a_den"""
    result = Fraction(1)
    a = Fraction(a_num, a_den)
    for k in range(n):
        result *= (a + k)
    return result

def eval_cf(a_func, b_func, N):
    """Evaluate CF b(0) + a(1)/(b(1)+a(2)/(b(2)+...)) via forward recurrence.
    Returns (p_n, q_n) as exact Fractions."""
    ps, qs = [], []
    for n in range(N+1):
        bn = Fraction(b_func(n))
        if n == 0:
            ps.append(bn)
            qs.append(Fraction(1))
        elif n == 1:
            an = Fraction(a_func(n))
            ps.append(bn * ps[0] + an)
            qs.append(bn * qs[0])
        else:
            an = Fraction(a_func(n))
            ps.append(bn * ps[-1] + an * ps[-2])
            qs.append(bn * qs[-1] + an * qs[-2])
    return ps, qs


# =====================================================================
print("=" * 70)
print("STEP 1: p_n = (2n-1)!! * (n^2+3n+1) in Pochhammer symbols")
print("=" * 70)

# (2n-1)!! = 2^n * (1/2)_n
print("\nVerify (1/2)_n * 2^n = (2n-1)!!:")
for n in range(8):
    lhs = pochhammer_exact(1, 2, n) * 2**n
    rhs = dff(n)
    print(f"  n={n}: (1/2)_{n} * 2^{n} = {lhs} = {rhs}  {'OK' if lhs == rhs else 'FAIL'}")

# n^2+3n+1 roots: (-3 +/- sqrt(5))/2  (irrational)
phi = (1 + 5**0.5) / 2  # golden ratio
r1 = (-3 + 5**0.5) / 2  # ~ -0.382
r2 = (-3 - 5**0.5) / 2  # ~ -2.618
print(f"\nn^2+3n+1 roots: {r1:.6f}, {r2:.6f}  (irrational, golden-ratio related)")
print(f"  r1 = (sqrt(5)-3)/2 = phi - 2 = {phi - 2:.6f}")
print(f"  r2 = -(sqrt(5)+3)/2 = -phi - 1 = {-phi - 1:.6f}")
print("  => n^2+3n+1 = (n - r1)(n - r2) with IRRATIONAL shifts")
print("  => NOT expressible as a ratio of Pochhammer products with rational parameters")

print("\np_n / p_{n-1} ratios:")
for n in range(1, 10):
    pn = dff(n) * (n**2 + 3*n + 1)
    pn1 = dff(n-1) * ((n-1)**2 + 3*(n-1) + 1)
    ratio = Fraction(pn, pn1)
    f1 = (2*n - 1)
    f2_num = n**2 + 3*n + 1
    f2_den = n**2 + n - 1
    print(f"  p_{n}/p_{n-1} = {f1}*{f2_num}/{f2_den} = {ratio} ~ {float(ratio):.4f}")

print("\n  Asymptotic: p_n/p_{n-1} ~ 2n (linear growth)")
print("  Gauss _2F1 at z=+-1: ratio ~ const (bounded). GROWTH MISMATCH.")


# =====================================================================
print("\n" + "=" * 70)
print("STEP 2: Exact increment sequence delta_n")
print("=" * 70)

a_func = lambda n: -n * (2*n - 3)
b_func = lambda n: 3*n + 1

ps, qs = eval_cf(a_func, b_func, 20)

print("\nConvergent table C_n = p_n/q_n:")
pi_over_4 = Fraction(0)  # will use mpmath for comparison
for n in range(16):
    cn = Fraction(ps[n], qs[n])
    print(f"  n={n:2d}: p={ps[n]}, q={qs[n]}, C_n = {cn} = {float(cn):.15f}")

print("\nIncrement delta_n = C_n - C_{n-1}:")
deltas = []
for n in range(16):
    if n == 0:
        delta = Fraction(ps[0], qs[0])
    else:
        delta = Fraction(ps[n], qs[n]) - Fraction(ps[n-1], qs[n-1])
    deltas.append(delta)
    print(f"  delta_{n:2d} = {delta}  =  {float(delta):.15e}")

# Check: delta_n = (-1)^n * det / (q_n * q_{n-1})
# For CF, p_n*q_{n-1} - p_{n-1}*q_n = prod_{k=1}^{n} (-a_k)
print("\nDeterminant D_n = p_n*q_{n-1} - p_{n-1}*q_n (should = prod(-a_k)):")
for n in range(1, 13):
    det = ps[n] * qs[n-1] - ps[n-1] * qs[n]
    prod_neg_a = Fraction(1)
    for k in range(1, n+1):
        prod_neg_a *= Fraction(-a_func(k))
    print(f"  n={n:2d}: D_n = {det},  prod(-a_k) = {prod_neg_a},  {'OK' if det == prod_neg_a else 'FAIL'}")

print("\nExact delta_n = D_n / (q_n * q_{n-1}):")
print("  D_n = prod_{k=1}^n k(2k-3) = n! * prod_{k=1}^n (2k-3)")
print("  prod_{k=1}^n (2k-3) = (-1)^n * prod_{k=1}^n (3-2k)")

# prod_{k=1}^n (2k-3): k=1:-1, k=2:1, k=3:3, k=4:5, ...
# For n>=2: = (-1) * 1 * 3 * 5 * ... * (2n-3) = (-1) * (2n-3)!! / (2*1-1 factor already included)
# Let's compute directly:
print("\nprod_{k=1}^n (2k-3):")
for n in range(1, 13):
    p = 1
    for k in range(1, n+1):
        p *= (2*k - 3)
    print(f"  n={n:2d}: {p}")
# n=1: -1, n=2: -1, n=3: -3, n=4: -15, n=5: -105, n=6: -945
# = (-1)^n * (2n-3)!! for n>=2? Let's check.
# n=2: (-1)^2 * 1!! = 1. Actual: -1. No.
# Actually: prod_{k=1}^n (2k-3) for k=1 gives -1, k=2 gives 1, k=3 gives 3...
# So prod = (-1) * 1 * 3 * 5 * ... * (2n-3)
# = (-1) * (2n-3)!! for n >= 2
# n=2: (-1)*1 = -1. YES
# n=3: (-1)*1*3 = -3. YES
# n=4: (-1)*1*3*5 = -15. YES


# =====================================================================
print("\n" + "=" * 70)
print("STEP 3: Test Gauss CF candidates")
print("=" * 70)

# The standard Gauss continued fraction for _2F1(a,b;c;z):
# _2F1(a,b;c;z) = 1/(1 - alpha_1*z/(1 - alpha_2*z/(1 - ...)))
# where alpha_{2k-1} = (a+k-1)(c-b+k-1) / ((c+2k-2)(c+2k-3))  [odd]
#       alpha_{2k}   = (b+k-1)(c-a+k-1) / ((c+2k-1)(c+2k-2))  [even]
#
# Equivalently as a standard CF:
# _2F1(a+1,b;c+1;z) / _2F1(a,b;c;z) = 1/(1 + ...)
#
# Our CF: b(0)+a(1)/(b(1)+a(2)/(b(2)+...))  with a(n)=-n(2n-3), b(n)=3n+1
# Value = 4/pi.
#
# Key: 4/pi = 1/_2F1(1/2,1/2;1;1)  (from the identity pi/4 = _2F1(1/2,1,3/2;-1) * 1)
# Actually: pi/4 = arctan(1) = _2F1(1/2, 1; 3/2; -1) [Euler's]
# So 4/pi = 1/_2F1(1/2,1;3/2;-1)
# Also: _2F1(1/2,1/2;1;1) = divergent (c-a-b=0).
#
# Several known representations of 4/pi:
# (A) 4/pi = _2F1(1/2,1/2;1;1) -- diverges
# (B) 4/pi via Ramanujan-type series
# (C) Brouncker: from _2F1(1,1;2;-1) = ln(2) -- no, Brouncker gives 4/pi.

# Let me directly test: does our CF match the Gauss CF for specific (a,b,c,z)?

candidates = [
    (Fraction(1,2), Fraction(1), Fraction(3,2), Fraction(-1)),   # arctan
    (Fraction(1), Fraction(1), Fraction(2), Fraction(-1)),       # ln(2) related
    (Fraction(3,2), Fraction(1), Fraction(5,2), Fraction(-1)),   # higher arctan
    (Fraction(1,2), Fraction(3,2), Fraction(2), Fraction(-1)),
    (Fraction(1,2), Fraction(1,2), Fraction(3,2), Fraction(-1)),
    (Fraction(1,2), Fraction(1), Fraction(3,2), Fraction(1)),
    (Fraction(1,2), Fraction(1,2), Fraction(1), Fraction(1)),    # elliptic K
    (Fraction(1,4), Fraction(3,4), Fraction(1), Fraction(1)),
]

print("\nGauss CF partial quotients for each candidate (a,b,c,z):")
print("Our CF has a(n)/b(n) = -n(2n-3)/(3n+1)")
print("First few: a(1)/b(1)=1/4, a(2)/b(2)=-2/7, a(3)/b(3)=-9/10, a(4)/b(4)=-20/13\n")

for (a, b, c, z) in candidates:
    # Gauss CF: f = b0 + a1/(b1 + a2/(b2 + ...))
    # Standard form: _2F1(a,b;c;z) has CF with
    # alpha_{2m-1} = -(a+m-1)(c-b+m-1)z / ((c+2m-2)(c+2m-3))  -- need to be careful
    # Actually, the Gauss CF is:
    # _2F1(a,b;c;z) / _2F1(a,b+1;c+1;z) or similar contiguous ratio.
    #
    # Let me use the Euler CF directly:
    # _2F1(a,b;c;z) = 1/(1 - g1*z/(1 - g2*z/(1 - ...)))
    # g_{2n-1} = (a+n-1)(c-b+n-1) / ((c+2n-3)(c+2n-2))
    # g_{2n}   = (b+n-1)(c-a+n-1) / ((c+2n-2)(c+2n-1))
    
    print(f"  (a,b,c,z) = ({a},{b},{c},{z}):")
    # Generate partial quotients of the Euler CF
    alphas = []
    for n in range(1, 9):
        if n % 2 == 1:  # odd: 2m-1, so m = (n+1)/2
            m = (n + 1) // 2
            g = (a + m - 1) * (c - b + m - 1) / ((c + 2*m - 3) * (c + 2*m - 2))
        else:  # even: 2m, so m = n//2
            m = n // 2
            g = (b + m - 1) * (c - a + m - 1) / ((c + 2*m - 2) * (c + 2*m - 1))
        alphas.append(g * z)  # The CF coefficient is g_n * z
    
    # The CF is: 1/(1 - a1/(1 - a2/(1 - ...)))
    # This is a different form from our a(n), b(n) CF.
    # Need to convert.
    print(f"    Euler alphas (g_n*z): {[f'{float(x):.4f}' for x in alphas[:6]]}")

print("\n--- Direct approach: compute Gauss CF in our b(0)+a(1)/(b(1)+...) form ---")

# The standard transformation: if _2F1 = 1/(1 - c1/(1 - c2/(1 - ...)))
# then setting A(n) = -c_n, B(n) = 1 for n>=1, B(0) = 1, we get
# value = B(0) + A(1)/(B(1) + A(2)/(B(2) + ...))
# = 1 + (-c1)/(1 + (-c2)/(1 + ...))
# But this doesn't match our b(n)=3n+1 form directly.

# Better: use an equivalence transformation to convert the Euler CF to
# our form and see if coefficients match.

# Actually, let me try a completely different approach.
# Our CF satisfies the 3-term recurrence:
# P_n = (3n+1) P_{n-1} - n(2n-3) P_{n-2}
# Q_n = (3n+1) Q_{n-1} - n(2n-3) Q_{n-2}
#
# For a Gauss CF of _2F1(a,b;c;z), the recurrence for the denominator is
# the contiguous relation for _2F1.
# Specifically: c(c-1)(z-1) f(c-1) + c[(c-1) - (2c-a-b-1)z] f(c) + (c-a)(c-b)z f(c+1) = 0
# where f(c) = _2F1(a,b;c;z).
#
# Our recurrence coefficients are polynomials of degree 1 (b(n)=3n+1) and degree 2 (a(n)=-n(2n-3)).
# The Gauss contiguous relation gives degree-1 coefficients in n for both b(n) and a(n) in 
# the "parameter-shifted" variable.
# Since our a(n) is degree 2, this already CANNOT come from a single Gauss contiguous relation.

print("\nKEY OBSERVATION:")
print("  Our a(n) = -n(2n-3) = -2n^2 + 3n  has degree 2 in n.")
print("  The Gauss CF for _2F1(a,b;c;z) has partial numerators that are")
print("  PRODUCTS of two linear factors in the step index, giving degree 2.")
print("  So degree 2 is expected! Let's match coefficients directly.")


# =====================================================================
print("\n" + "=" * 70)
print("STEP 3b: Direct coefficient matching with Gauss CF")
print("=" * 70)

# The Wall form of the Gauss CF:
# _2F1(a,b;c;z) = 1 + sum, and as a CF:
#
# Let R_n = _2F1(a, b+n; c+n; z) / _2F1(a, b+n-1; c+n-1; z)
# Then R_n = (c+n-1) / [(c+n-1) - (...)z / R_{n+1}]
# 
# More standard: the Gauss CF for _2F1(a,b;c;z) is
#   _2F1(a,b;c;z) = b0 + a1/(b1 + a2/(b2 + ...))
# with b0=1, and for the even/odd CF:
#   a_{2m+1} = -(a+m)(c-b+m) z,   b_{2m+1} = c + 2m
#   a_{2m+2} = -(b+m)(c-a+m) z,   b_{2m+2} = c + 2m + 1
#
# Wait, this is the *even contraction* of the Euler CF.
# Let me be more precise. The standard CF representation is:
#
# _2F1(a,b;c;z)/1 = c/(c - (a*b*z)/(c+1-(a+1)(c-b)z/((c+2)-(b+1)(c-a+1)z/((c+3)-...)))))
# Hmm, there are several conventions. Let me use the one from DLMF 15.7.

# DLMF 15.7.5: 
# _2F1(a,b;c;z) / _2F1(a,b+1;c+1;z) = 1 - (a(c-b)z)/((c)(c+1)) / (1 - (b+1)(c-a+1)z/((c+1)(c+2)) / (1 - ...))
# 
# DLMF 15.7.6 (Gauss's continued fraction):
# _2F1(a,b+1;c+1;z) / _2F1(a,b;c;z) = 1/(1 - t_1/(1 - t_2/(1 - ...)))
# where t_{2n-1} = (a+n-1)(c-b+n-1)z / ((c+2n-2)(c+2n-1))
#       t_{2n}   = (b+n)(c-a+n)z     / ((c+2n-1)(c+2n))
#
# This is an S-fraction. To get an equivalent general CF b0+a1/(b1+...),
# we can use an equivalence transformation.
# Let's compute the Gauss S-fraction for various (a,b,c,z) and then
# convert to our form.

# Actually, the simplest approach: the even contraction of the Gauss CF
# gives a CF where both a(n) and b(n) are rational functions of n.
# Let me check if our CF is an even part of some Gauss CF.

# ALTERNATIVELY: just evaluate _2F1(a,b;c;z) for the candidates and see which = pi/4.
print("\nNumerical check: which _2F1 equals pi/4?")
target = mp.pi / 4
print(f"  pi/4 = {nstr(target, 30)}")

test_params = [
    (0.5, 1, 1.5, -1, "arctan(1)"),
    (1, 1, 2, -1, "ln(2)"),
    (0.5, 0.5, 1.5, -1, "arcsin(1)/1"),
    (0.5, 1, 1.5, 1, "atanh(1) diverges"),
    (0.5, 0.5, 1, 1, "2K(1)/pi diverges"),
    (0.25, 0.75, 1, 1, "diverges?"),
    (0.5, 1, 2, -1, "2(1-ln2)"),
    (0.5, 0.5, 1.5, 1, "pi/4?"),  
    (1, 0.5, 1.5, 1, "diverges?"),
    (1, 0.5, 1.5, -1, "arctan-related"),
]

for params in test_params:
    a, b, c, z, label = params
    try:
        val = hyp2f1(a, b, c, z)
        diff = abs(val - target)
        match = "MATCH" if diff < mpf(10)**(-20) else f"diff={float(diff):.3e}"
        print(f"  _2F1({a},{b};{c};{z}) = {nstr(val, 20)}  [{match}]  ({label})")
    except:
        print(f"  _2F1({a},{b};{c};{z}) FAILED  ({label})")

# pi/4 = arctan(1) = _2F1(1/2, 1; 3/2; -1). So our CF -> 4/pi = 1/arctan(1)... 
# Actually 4/pi, not pi/4. Let me check 4/pi:
print(f"\n  4/pi = {nstr(4/mp.pi, 30)}")
target2 = 4 / mp.pi

# Our CF converges to 4/pi, so we need _2F1(a,b;c;z) = 4/pi
# or our CF is the ratio _2F1(a,b+1;c+1;z)/_2F1(a,b;c;z) = 4/pi for some params.

# Actually, let me reconsider. Our CF has b(0)=1, so the value is:
# 1 + a(1)/(b(1) + a(2)/(b(2) + ...))
# = 1 + 1/(4 + (-2)/(7 + (-9)/(10 + ...)))
# Let me verify:
mp.dps = 60
p0, p1 = mpf(1), mpf(1)
q0, q1 = mpf(0), mpf(1)
for n in range(1, 300):
    an = -n * (2*n - 3)
    bn = 3*n + 1
    p0, p1 = p1, bn*p1 + an*p0
    q0, q1 = q1, bn*q1 + an*q0
cf_val = p1 / q1
print(f"\n  CF value (depth 300) = {nstr(cf_val, 40)}")
print(f"  4/pi                 = {nstr(4/pi, 40)}")
print(f"  Agree to {int(-log10(abs(cf_val - 4/pi)))} digits")

# If CF = 4/pi, and 4/pi = 1/arctan(1) ... no: 4/pi != 1/arctan(1).
# arctan(1) = pi/4, so 1/arctan(1) = 4/pi. Yes!
# So CF = 1/_2F1(1/2, 1; 3/2; -1).
# But our CF is expressed directly (not as 1/something).

# Key insight: maybe our CF = ratio of contiguous _2F1.
# _2F1(a,b+1;c+1;z)/_2F1(a,b;c;z) is given by the Gauss CF.
# We need this ratio = 4/pi.
# If _2F1(a,b;c;z) = pi/4 and _2F1(a,b+1;c+1;z) = 1, then ratio = 4/pi.
# _2F1(a,b+1;c+1;z) = 1 means z=0 or a=0 or b+1=0 or ...
# That's too restrictive.
# 
# Better: just match the recurrence coefficients.

print("\n" + "=" * 70)
print("STEP 3c: Match recurrence directly")
print("=" * 70)

# The 3-term recurrence for the nth convergent of the Gauss CF
# (DLMF 15.7.6 form, after equivalence transform to b0+a1/(b1+...)):
#
# Using Wall's even contraction of the Gauss S-fraction:
# We get a CF with
#   A(n) = -f(n)*g(n)*z^2   (degree 4 in n after expansion)
#   B(n) = linear in n
#
# Our A(n) = -n(2n-3) is degree 2. So this is NOT an even contraction.
#
# What about the ORIGINAL (uncontracted) Gauss CF?
# The Gauss CF is an S-fraction: 1/(1 - t1/(1 - t2/(1 - ...)))
# where t_n are rational functions of n. Converting to our form
# b0 + a1/(b1 + a2/(b2+...)) gives:
#   b_n = 1 for all n, and a_n = -t_n.
# But our b_n = 3n+1 != 1.
#
# With equivalence transformation c_n: multiply b_n by c_n and a_n by c_n*c_{n-1}.
# Can we find c_n such that 1*c_n = 3n+1 and -t_n * c_n * c_{n-1} = -n(2n-3)?
# => c_n = 3n+1, and t_n = n(2n-3) / ((3n+1)(3n-2)).

print("If the CF is an equivalence-transformed Gauss CF:")
print("  c_n = 3n+1 (to get b_n = 3n+1 from constant 1)")
print("  Then original t_n = n(2n-3) / ((3n+1)(3(n-1)+1))")
print("  = n(2n-3) / ((3n+1)(3n-2))")
print()

print("Required Gauss CF coefficients t_n = n(2n-3)/((3n+1)(3n-2)):")
for n in range(1, 12):
    t = Fraction(n * (2*n - 3), (3*n + 1) * (3*n - 2))
    print(f"  t_{n:2d} = {t} = {float(t):.8f}")

# Now: for the Gauss CF (DLMF 15.7.6):
# t_{2m-1} = (a+m-1)(c-b+m-1) / ((c+2m-2)(c+2m-1))   [odd indices]
# t_{2m}   = (b+m)(c-a+m)     / ((c+2m-1)(c+2n))       [even indices]
# Both are rational in m of degree: deg 2 / deg 2 = bounded.
# But our t_n = n(2n-3)/((3n+1)(3n-2)) is a SINGLE formula for ALL n,
# not alternating odd/even. So it cannot be the standard Gauss CF
# (which alternates between two different formulas).

# UNLESS: our CF is already the even (or odd) part of a Gauss CF.
# The even part of a CF c0+d1/(c1+d2/(c2+...)) has the form:
# c0 + d1/(c1 + d2*d3/((c2*c3+d3) + ...))
# which gives degree-4 numerators. Our numerators are degree 2, so NO.

print("\nGauss CF has ALTERNATING formulas for t_{odd} and t_{even}.")
print("Our t_n = n(2n-3)/((3n+1)(3n-2)) is a SINGLE formula for all n.")
print("=> NOT a standard Gauss CF.")

# =====================================================================
print("\n" + "=" * 70)
print("STEP 3d: Can a SINGLE-FORMULA CF arise from _2F1?")
print("=" * 70)

# The only way to get a single formula is if t_{2m-1} = t_{2m} for all m,
# i.e., (a+m-1)(c-b+m-1)/((c+2m-2)(c+2m-1)) = (b+m)(c-a+m)/((c+2m-1)(c+2m))
# for all m. This gives:
# (a+m-1)(c-b+m-1)(c+2m) = (b+m)(c-a+m)(c+2m-2)
# Expanding both sides as cubics in m and comparing coefficients...
# This is very restrictive.

# Actually, there IS a way: if a = b + 1/2 and the CF simplifies.
# Or if we use a DIFFERENT hypergeometric CF, like the one for
# _1F1 (confluent) or _3F2.

# Let me check: does our recurrence match a _3F2 contiguous relation?
# The 3-term recurrence P_n = (3n+1)*P_{n-1} - n(2n-3)*P_{n-2}
# has coefficients of degree 1 and 2. For _2F1, the contiguous relations
# give degree <= 1 in both. For _3F2, we can get degree 2 in one coefficient.

# KEY TEST: solve for Gauss parameters assuming t_n is a single formula.
# t_n = n(2n-3)/((3n+1)(3n-2))
# 
# If this comes from Gauss with some index relabeling, say n -> 2m-1 for odd:
# t_1 = 1*(-1)/(4*1) = -1/4. Gauss t_1 = a(c-b)/((c)(c+1)) = a(c-b)/(c(c+1))
# t_2 = 2*1/(7*4) = 2/28 = 1/14. Gauss t_2 = (b+1)(c-a+1)/((c+1)(c+2))
# t_3 = 3*3/(10*7) = 9/70.  Gauss t_3 = (a+1)(c-b+1)/((c+2)(c+3))
# t_4 = 4*5/(13*10) = 20/130 = 2/13. Gauss t_4 = (b+2)(c-a+2)/((c+3)(c+4))

# From t_1 = a(c-b)/(c(c+1)) = -1/4:   a(c-b) = -c(c+1)/4
# From t_2 = (b+1)(c-a+1)/((c+1)(c+2)) = 1/14:  (b+1)(c-a+1) = (c+1)(c+2)/14
# From t_3 = (a+1)(c-b+1)/((c+2)(c+3)) = 9/70:  (a+1)(c-b+1) = 9(c+2)(c+3)/70
# From t_4 = (b+2)(c-a+2)/((c+3)(c+4)) = 2/13:  (b+2)(c-a+2) = 2(c+3)(c+4)/13

print("\nSolving Gauss equations from t_1..t_4:")
print("  t_1 = -1/4:  a(c-b) = -c(c+1)/4")
print("  t_2 =  1/14: (b+1)(c-a+1) = (c+1)(c+2)/14")
print("  t_3 =  9/70: (a+1)(c-b+1) = 9(c+2)(c+3)/70")
print("  t_4 =  2/13: (b+2)(c-a+2) = 2(c+3)(c+4)/13")

# From eq1: a(c-b) = -c(c+1)/4
# From eq3: (a+1)(c-b+1) = 9(c+2)(c+3)/70
# Expand eq3: a(c-b) + a + (c-b) + 1 = 9(c+2)(c+3)/70
# Substitute eq1: -c(c+1)/4 + a + (c-b) + 1 = 9(c+2)(c+3)/70
# So: a + (c-b) = 9(c+2)(c+3)/70 + c(c+1)/4 - 1  ... (*)

# From eq2: (b+1)(c-a+1) = (c+1)(c+2)/14
# From eq4: (b+2)(c-a+2) = 2(c+3)(c+4)/13
# Expand eq4: (b+1)(c-a+1) + (b+1) + (c-a+1) + 1 = 2(c+3)(c+4)/13
# Substitute eq2: (c+1)(c+2)/14 + (b+1) + (c-a+1) + 1 = 2(c+3)(c+4)/13
# So: (b+1) + (c-a) + 2 = 2(c+3)(c+4)/13 - (c+1)(c+2)/14  ... (**)

# Let u = a + (c-b), v = (c-a) + (b+1) + 2 = c + 3
# From (**): c + 3 = 2(c+3)(c+4)/13 - (c+1)(c+2)/14
# => 1 = 2(c+4)/13 - (c+1)(c+2)/(14(c+3))
# => 13*14(c+3) = 2*14(c+4)(c+3) - 13(c+1)(c+2)
# => 182(c+3) = 28(c+4)(c+3) - 13(c+1)(c+2)
# => 182c + 546 = 28(c^2+7c+12) - 13(c^2+3c+2)
# => 182c + 546 = 28c^2+196c+336 - 13c^2-39c-26
# => 182c + 546 = 15c^2 + 157c + 310
# => 15c^2 - 25c - 236 = 0

from mpmath import findroot, mpf as mf

# 15c^2 - 25c - 236 = 0
disc = 25**2 + 4*15*236
print(f"\n  Discriminant = {disc} = {disc}  (not a perfect square: sqrt = {disc**0.5:.4f})")
print(f"  c = (25 +/- sqrt({disc})) / 30")
import math
s = math.isqrt(disc)
print(f"  sqrt({disc}) is {'rational' if s*s == disc else 'IRRATIONAL'}")

c1 = (25 + disc**0.5) / 30
c2 = (25 - disc**0.5) / 30
print(f"  c = {c1:.6f} or {c2:.6f}")
print(f"  IRRATIONAL values of c => No rational _2F1 parameters exist!")

print("\n" + "=" * 70)
print("CONCLUSION FROM STEP 3")
print("=" * 70)
print("""
The system of 4 equations from matching t_1..t_4 to the Gauss CF yields
the quadratic 15c^2 - 25c - 236 = 0 with discriminant 14785 (not a
perfect square), giving IRRATIONAL c.

Since _2F1(a,b;c;z) requires the parameters (a,b,c) to identify the
function, and the matching forces c to be irrational, the CF
PCF(-n(2n-3), 3n+1) CANNOT arise from the Gauss continued fraction
theorem for _2F1(a,b;c;z) with any rational parameters.
""")
