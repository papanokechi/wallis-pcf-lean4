"""
Gauss CF analysis, Part 2: coefficient matching + alternative families.
"""
from fractions import Fraction
from math import factorial
from mpmath import mp, mpf, pi, gamma, hyp2f1, nstr, log10, sqrt, hyper

mp.dps = 80

# =====================================================================
print("=" * 70)
print("STEP 3: Direct Gauss CF coefficient matching")
print("=" * 70)

# Our CF: b(0)+a(1)/(b(1)+a(2)/(b(2)+...))
# a(n) = -n(2n-3), b(n) = 3n+1
# Apply equivalence transform c_n to convert to S-fraction form
# b_n -> b_n/c_n = 1 requires c_n = 3n+1  (or c_n = b_n)
# a_n -> a_n/(c_n*c_{n-1}) = -n(2n-3)/((3n+1)(3n-2))
# But b_0/c_0 = 1/1 = 1, and new a_1 = a_1/(c_1*c_0) = 1/(4*1) = 1/4
# So the S-fraction form is 1 + (1/4)/(1 + t_2/(1 + t_3/(1 + ...)))
# where t_n = n(2n-3)/((3n+1)(3n-2)) for n >= 2.

# Actually for an S-fraction 1/(1 - t_1/(1 - t_2/(1 - ...))) the sign differs.
# Let me be careful. Our CF in the form:
# value = 1 + (-1*(-1))/((3+1) + (-2*(2*2-3))/((3*2+1) + ...))
#       = 1 + 1/(4 + (-2)/(7 + (-9)/(10 + ...)))

# Equivalence transformation: multiply n-th b by c_n and n-th a by c_n*c_{n-1}.
# To get b_n' = 1 for n >= 1, set c_n = 1/b_n = 1/(3n+1).
# Then a_n' = a_n * c_n * c_{n-1} = -n(2n-3)/((3n+1)(3n-2))
# and b_0' = b_0 * c_0 = 1 * 1 = 1 (c_0 = 1 by convention).

# Wait, for an equivalence transformation to preserve value:
# b_0 + a_1/(b_1 + a_2/(b_2 + ...))
# = (c_0*b_0) + (c_0*c_1*a_1)/((c_1*b_1) + (c_1*c_2*a_2)/((c_2*b_2) + ...))
# So to get c_n*b_n = 1 for n >= 1: c_n = 1/(3n+1).
# Then c_0*b_0 = c_0 * 1 = c_0. Setting c_0 = 1: b_0' = 1.
# a_n' = c_{n-1}*c_n*a_n = (-n(2n-3))/((3(n-1)+1)(3n+1)) = -n(2n-3)/((3n-2)(3n+1))

print("After equivalence transform to unit-b form:")
print("  b_n' = 1 for all n")
print("  a_n' = -n(2n-3) / ((3n-2)(3n+1))")
print()

ts = []
for n in range(1, 16):
    t = Fraction(-n * (2*n - 3), (3*n - 2) * (3*n + 1))
    ts.append(t)
    print(f"  t_{n:2d} = {t} = {float(t):.10f}")

# Gauss CF (DLMF 15.7.6):
# _2F1(a,b+1;c+1;z)/_2F1(a,b;c;z) = 1/(1 - u_1*z/(1 - u_2*z/(1 - ...)))
# with u_{2m-1} = (a+m-1)(c-b+m-1)/((c+2m-2)(c+2m-1))
#      u_{2m}   = (b+m)(c-a+m)/((c+2m-1)(c+2m))
#
# Our S-fraction: value = 1 + t_1/(1 + t_2/(1 + ...))
# Converting: 1/(1 + t_1/(1 + ...)) = 1/(value)
# Actually: value = 1 + t_1/(1 + t_2/(1 + ...))
# = 1 - (-t_1)/(1 - (-t_2)/(1 - ...))
# This is 1/(1 - (-t_1)/(1 - (-t_2)/(1 - ...))) if we shift...
# Actually, value = b_0' + a_1'/(b_1' + a_2'/(b_2' + ...))
# With b_n' = 1 and a_n' = t_n (which are negative for n >= 2).
# The Stieltjes form is: 1/(1 - c_1/(1 - c_2/(1 - ...))) where c_n = -a_n' = -t_n.

# So our modified CF: 1/(1 - c_1/(1 - c_2/(1 - ...))) converges to 1/value = pi/4.
# And c_n = n(2n-3)/((3n-2)(3n+1)).

# NOTE: c_1 = 1*(-1)/(1*4) = -1/4. Hmm, c_1 is negative.
# Actually t_1 = -1*(-1)/(1*4) = 1/4. So c_1 = -t_1 = -1/4? No...
# Let me recompute: a_1' = -1*(2-3)/((3-2)(3+1)) = -1*(-1)/(1*4) = 1/4
# So t_1 = a_1' = 1/4.  c_1 = -a_1' = -1/4. That makes the CF:
# 1 + (1/4)/(1 + t_2/(1 + ...))
# Then 1/value = pi/4 means value = 4/pi. Good.

# The issue: Gauss CF coefficients alternate between two formulas.
# Ours don't. Let me check: can our SINGLE formula somehow arise?

# If we set u_n * z = c_n = -t_n = n(2n-3)/((3n-2)(3n+1)):
# For odd n=2m-1: u_{2m-1} = (a+m-1)(c-b+m-1)/((c+2m-2)(c+2m-1))
# For even n=2m:  u_{2m}   = (b+m)(c-a+m)/((c+2m-1)(c+2m))
#
# And u_n * z should equal n(2n-3)/((3n-2)(3n+1)) for all n.

# Strategy: match u_1*z, u_2*z, u_3*z, u_4*z to our formula,
# get 4 equations in 4 unknowns (a, b, c, z).

print("\n" + "-" * 50)
print("Matching Gauss CF coefficients u_n*z = n(2n-3)/((3n-2)(3n+1)):")
print("-" * 50)

# n=1 (odd, m=1): u_1*z = a(c-b)/((c)(c+1)) * z = 1*(-1)/(1*4) = -1/4
# n=2 (even, m=1): u_2*z = (b+1)(c-a+1)/((c+1)(c+2)) * z = 2*1/(4*7) = 2/28 = 1/14
# n=3 (odd, m=2): u_3*z = (a+1)(c-b+1)/((c+2)(c+3)) * z = 3*3/(7*10) = 9/70
# n=4 (even, m=2): u_4*z = (b+2)(c-a+2)/((c+3)(c+4)) * z = 4*5/(10*13) = 20/130 = 2/13

our_c = {}
for n in range(1, 9):
    val = Fraction(n * (2*n - 3), (3*n - 2) * (3*n + 1))
    our_c[n] = val
    print(f"  c_{n} = {val} = {float(val):.8f}")

# Equations:
# (E1) a(c-b)z / (c(c+1)) = -1/4
# (E2) (b+1)(c-a+1)z / ((c+1)(c+2)) = 1/14
# (E3) (a+1)(c-b+1)z / ((c+2)(c+3)) = 9/70
# (E4) (b+2)(c-a+2)z / ((c+3)(c+4)) = 2/13

# Let me use sympy for exact solution
from sympy import symbols, solve, Rational, sqrt as ssqrt, simplify, Eq

a, b, c, z = symbols('a b c z')

eqs = [
    Eq(a*(c-b)*z, Rational(-1,4) * c*(c+1)),
    Eq((b+1)*(c-a+1)*z, Rational(1,14) * (c+1)*(c+2)),
    Eq((a+1)*(c-b+1)*z, Rational(9,70) * (c+2)*(c+3)),
    Eq((b+2)*(c-a+2)*z, Rational(2,13) * (c+3)*(c+4)),
]

print("\nSolving 4 Gauss equations with sympy...")
sols = solve(eqs, [a, b, c, z], dict=True)
print(f"  Found {len(sols)} solution(s):")
for i, s in enumerate(sols):
    print(f"\n  Solution {i+1}:")
    for var in [a, b, c, z]:
        val = s[var]
        print(f"    {var} = {val}")
        try:
            print(f"        = {float(val):.10f}")
        except:
            print(f"        (cannot evaluate)")
    
    # Check: are all parameters rational?
    from sympy import nsimplify, Rational as R
    all_rational = all(s[v].is_rational for v in [a, b, c, z])
    print(f"    All rational? {all_rational}")


# =====================================================================
print("\n" + "=" * 70)
print("STEP 4: Check alternative hypergeometric families")
print("=" * 70)

# Even if Gauss CF doesn't work with rational params, let's check:
# 4a. Is value of Gauss CF at irrational params = 4/pi?
# 4b. Is this a _3F2 CF (Ramanujan-type)?
# 4c. Is this related to Euler's CF for arctan?

# 4a: Evaluate _2F1 at the irrational parameters (if they exist)
if sols:
    s = sols[0]
    mp.dps = 60
    try:
        a_val = complex(s[a]).real
        b_val = complex(s[b]).real
        c_val = complex(s[c]).real
        z_val = complex(s[z]).real
        
        print(f"\n4a. Testing _2F1({a_val:.8f}, {b_val:.8f}; {c_val:.8f}; {z_val:.8f})")
        
        # Test: does _2F1(a,b+1;c+1;z)/_2F1(a,b;c;z) = 4/pi?
        f1 = hyp2f1(a_val, b_val, c_val, z_val)
        f2 = hyp2f1(a_val, b_val+1, c_val+1, z_val)
        ratio = f2 / f1
        target = 4/pi
        print(f"  _2F1(a,b;c;z)      = {nstr(f1, 30)}")
        print(f"  _2F1(a,b+1;c+1;z)  = {nstr(f2, 30)}")
        print(f"  ratio               = {nstr(ratio, 30)}")
        print(f"  4/pi                = {nstr(target, 30)}")
        print(f"  |ratio - 4/pi|      = {float(abs(ratio - target)):.3e}")
    except Exception as e:
        print(f"  Evaluation failed: {e}")

# 4b: Check _3F2 and Ramanujan Entry 17
print("\n4b. Testing Ramanujan Entry 17 and _3F2 CFs")
print("    Entry 17: CFs from _3F2(a,b,c;d,e;z)")
print()

# Our recurrence: P_n = (3n+1)P_{n-1} - n(2n-3)P_{n-2}
# For _pF_{p-1}, the contiguous relation gives a 3-term recurrence
# where coefficients are degree p polynomials in n.
# Our b(n) = 3n+1 is degree 1, a(n) = -n(2n-3) is degree 2.
# So the sum of degrees (1+2=3) suggests _3F2 might work,
# but actually for _2F1 the contiguous relation gives
# b(n) degree 1, a(n) degree 2, matching ours!

# The KEY distinction is: the Gauss CF alternates two formulas,
# but the CONTIGUOUS RELATION for _2F1 c -> c+1 gives a SINGLE
# 3-term recurrence with polynomial coefficients.

# Let me check: does _2F1(a,b;c+n;z) satisfy our recurrence
# for some (a,b,c,z)?

# The contiguous relation for c -> c+1 (DLMF 15.5.16):
# c(c-1)(z-1) f(c-1) + c[(c-1)-(2c-a-b-1)z] f(c) + (c-a)(c-b)z f(c+1) = 0
# i.e.: f(c+1) = {c[(2c-a-b-1)z-(c-1)] f(c) - c(c-1)(z-1) f(c-1)} / ((c-a)(c-b)z)
# 
# Setting g(n) = _2F1(a,b;c+n;z), we get:
# (c+n-a)(c+n-b)z g(n+1) = (c+n)[(2(c+n)-a-b-1)z - (c+n-1)] g(n) 
#                           - (c+n)(c+n-1)(z-1) g(n-1)
#
# Shifting: let m = n+1:
# g(m) = A(m) g(m-1) + B(m) g(m-2)
# where A(m) = (c+m-1)[(2c+2m-a-b-3)z-(c+m-2)] / ((c+m-1-a)(c+m-1-b)z)
#       B(m) = -(c+m-1)(c+m-2)(z-1) / ((c+m-1-a)(c+m-1-b)z)
#
# For this to match our recurrence P_m = (3m+1)P_{m-1} - m(2m-3)P_{m-2},
# we need B(m) to be proportional to -m(2m-3).
# B(m) numerator: -(c+m-1)(c+m-2)(z-1)  -- quadratic in m
# Must equal: -lambda * m(2m-3) * ((c+m-1-a)(c+m-1-b)z)
# for some normalizing factor lambda.
# 
# This is getting complicated. Let me try a direct numerical approach.

print("\n4c. Direct search: does _2F1(a,b;c+n;z) satisfy our recurrence?")

# If g(n) = _2F1(a,b;c+n;z) and this satisfies
# g(n) = (3n+1)*g(n-1) - n(2n-3)*g(n-2) (after rescaling by (c+n-1-a)(c+n-1-b)z)
# then the ratio g(n)/g(n-1) approaches our CF value.

# The approach: for each candidate (a,b,c,z), compute
# R(n) = [(3n+1)*g(n-1) - n(2n-3)*g(n-2)] / g(n)
# If = 1 for all n, then match.

# But we're looking for agreement up to a variable normalization.
# Actually, the convergent P_n/Q_n of our CF satisfies:
# Q_n/Q_{n-1} approaches one solution of the recurrence,
# P_n/P_{n-1} approaches another.
# The RATIO approaches the CF value = a dominant/recessive ratio.

# Let me try the inverse approach: our CF value = 4/pi.
# If this arises from a contiguous ratio _2F1(a,b;c+1;z)/_2F1(a,b;c;z),
# then 4/pi = _2F1(a,b;c+1;z)/_2F1(a,b;c;z), and we need:
# The recurrence for _2F1(a,b;c+n;z) with NORMALIZED coefficients
# to match (3n+1) and -n(2n-3).

# From the contiguous relation, after shifting n -> n+c:
# The denominator (c+n-a)(c+n-b)z must divide into the numerator
# to give polynomial coefficients (3n+1) and -n(2n-3).

# If the recurrence has the form:
# (c+n-a)(c+n-b)z * g(n+1) = [poly_1(n)] g(n) + [poly_2(n)] g(n-1)
# and we set P_n = (c+n-a)(c+n-b)z * ... * normalization,
# the effective recurrence for P_n will have rational coefficients.

# Let me try to match directly by solving the system numerically.
# We need: for n = 1,2,3,...
# (3n+1) = (c+n-1)[(2c+2n-a-b-3)z-(c+n-2)] / ((c+n-1-a)(c+n-1-b)z)  [call it alpha(n)]
# -n(2n-3) = -(c+n-1)(c+n-2)(z-1) / ((c+n-1-a)(c+n-1-b)z)   [call it beta(n)]

# From beta(n): n(2n-3) = (c+n-1)(c+n-2)(z-1) / ((c+n-1-a)(c+n-1-b)z)

# RATIO: alpha(n)/beta(n) = (3n+1)/(-n(2n-3))
# alpha/beta = -[(2c+2n-a-b-3)z-(c+n-2)] / ((c+n-2)(z-1))
# = -(3n+1) / (n(2n-3))

# So: [(2c+2n-a-b-3)z-(c+n-2)] / ((c+n-2)(z-1)) = (3n+1)/(n(2n-3))

# Cross multiply: n(2n-3)[(2c+2n-a-b-3)z - (c+n-2)] = (3n+1)(c+n-2)(z-1)

# Expand LHS: n(2n-3)(2c-a-b-3)z + n(2n-3)(2n)z - n(2n-3)(c-2) - n(2n-3)n
#  = n(2n-3)(2c-a-b-3)z + 2n^2(2n-3)z - n(2n-3)(c-2) - n^2(2n-3)
# Hmm this is getting messy. Let me use sympy.

from sympy import Symbol, expand, collect, Poly

n = Symbol('n')
a_s = Symbol('a_s')  # sympy a
b_s = Symbol('b_s')
c_s = Symbol('c_s')
z_s = Symbol('z_s')

lhs = n*(2*n-3)*((2*c_s+2*n-a_s-b_s-3)*z_s - (c_s+n-2))
rhs = (3*n+1)*(c_s+n-2)*(z_s-1)

diff = expand(lhs - rhs)
poly_n = Poly(diff, n)
coeffs = poly_n.all_coeffs()

print("\n  Equation: n(2n-3)[(2c+2n-a-b-3)z-(c+n-2)] = (3n+1)(c+n-2)(z-1)")
print(f"  As polynomial in n: degree {poly_n.degree()}")
print(f"  Coefficients (highest to lowest in n):")
for i, coef in enumerate(coeffs):
    deg = poly_n.degree() - i
    print(f"    n^{deg}: {coef}")

# Must all be zero. This gives 4 equations in (a_s, b_s, c_s, z_s).
# degree 3: 4z - 3z + 3 => z + 3? Let me check more carefully.

print("\n  Setting each coefficient = 0:")
eqs_sympy = []
for i, coef in enumerate(coeffs):
    deg = poly_n.degree() - i
    eq = Eq(coef, 0)
    print(f"    n^{deg}: {coef} = 0")
    eqs_sympy.append(eq)

print("\n  Solving system...")
sols2 = solve(eqs_sympy, [a_s, b_s, c_s, z_s], dict=True)
print(f"  Found {len(sols2)} solution(s):")
for i, s in enumerate(sols2):
    print(f"\n  Solution {i+1}:")
    for var in [a_s, b_s, c_s, z_s]:
        if var in s:
            print(f"    {var} = {s[var]}")
    # Check: free parameters?
    assigned = set(s.keys())
    free = {a_s, b_s, c_s, z_s} - assigned
    if free:
        print(f"    Free parameters: {free}")


# =====================================================================
print("\n" + "=" * 70)
print("STEP 4d: Check if rescaled recurrence matches _2F1 contiguous")
print("=" * 70)

# The issue above is that we're matching the RAW contiguous relation.
# But the CF recurrence P_n = b(n)P_{n-1} + a(n)P_{n-2} may correspond
# to a RESCALED version of the contiguous relation.
# If g(n) = _2F1(a,b;c+n;z) satisfies:
#   (c+n-a)(c+n-b)z g(n+1) = [(c+n)((2c+2n-a-b-1)z-(c+n-1))] g(n) 
#                              - (c+n)(c+n-1)(z-1) g(n-1)
# Then setting P_n = product_{k=1}^{n} (c+k-a)(c+k-b)z * g(n) (normalizing the denominator),
# we'd get a different recurrence for P_n.
#
# Actually, for the CF convergent denominators Q_n, if the CF is related to
# the contiguous ratio, then Q_n = const * prod * _2F1(a,b;c+n;z) for one
# of the solutions.

# Let me try a completely different approach: NUMERICAL parameter fitting.
# Given our t_n (S-fraction coefficients), fit the Gauss formulas.

print("\nNumerical Gauss parameter fitting:")
print("  t_n = n(2n-3)/((3n-2)(3n+1)) for n >= 1")
print("  Gauss: t_{2m-1} = (a+m-1)(c-b+m-1)z/((c+2m-2)(c+2m-1))")
print("         t_{2m}   = (b+m)(c-a+m)z/((c+2m-1)(c+2m))")
print()

# Match t_1 (m=1): a(c-b)z/(c(c+1)) = -1/4
# Match t_2 (m=1): (b+1)(c-a+1)z/((c+1)(c+2)) = 1/14
# Match t_3 (m=2): (a+1)(c-b+1)z/((c+2)(c+3)) = 9/70
# Match t_4 (m=2): (b+2)(c-a+2)z/((c+3)(c+4)) = 2/13
# Match t_5 (m=3): (a+2)(c-b+2)z/((c+4)(c+5)) = 25/238
# Match t_6 (m=3): (b+3)(c-a+3)z/((c+5)(c+6)) = ?

# Let me compute more t values for matching:
print("  Our target t values:")
for n in range(1, 11):
    t = Fraction(n * (2*n - 3), (3*n - 2) * (3*n + 1))
    print(f"    t_{n:2d} = {t}")

# Now solve the 4 Gauss equations using sympy
a, b, c, z = symbols('a b c z')

gauss_eqs = [
    Eq(a*(c-b)*z, Rational(-1,4)*c*(c+1)),              # t_1
    Eq((b+1)*(c-a+1)*z, Rational(1,14)*(c+1)*(c+2)),    # t_2
    Eq((a+1)*(c-b+1)*z, Rational(9,70)*(c+2)*(c+3)),    # t_3
    Eq((b+2)*(c-a+2)*z, Rational(2,13)*(c+3)*(c+4)),    # t_4
]

print("\n  Solving Gauss equations...")
gauss_sols = solve(gauss_eqs, [a, b, c, z], dict=True)
print(f"  Found {len(gauss_sols)} solution(s):")

for i, s in enumerate(gauss_sols):
    print(f"\n  Solution {i+1}:")
    for var in [a, b, c, z]:
        val = s.get(var, '?')
        fval = complex(val).real if val != '?' else None
        print(f"    {var} = {val} = {fval}")
    
    # Check rationality
    all_rat = all(s[v].is_rational for v in [a, b, c, z] if v in s)
    print(f"    All rational? {all_rat}")
    
    # Verify with t_5, t_6
    a_v, b_v, c_v, z_v = [s[v] for v in [a, b, c, z]]
    
    # t_5 (m=3): (a+2)(c-b+2)z/((c+4)(c+5))
    t5_gauss = (a_v + 2)*(c_v - b_v + 2)*z_v / ((c_v + 4)*(c_v + 5))
    t5_ours = Rational(5*(10-3), (3*5-2)*(3*5+1))  # 5*7/(13*16) = 35/208
    print(f"    t_5 check: Gauss = {simplify(t5_gauss)}, ours = {t5_ours}, match? {simplify(t5_gauss - t5_ours) == 0}")
    
    # t_6 (m=3): (b+3)(c-a+3)z/((c+5)(c+6))
    t6_gauss = (b_v + 3)*(c_v - a_v + 3)*z_v / ((c_v + 5)*(c_v + 6))
    t6_ours = Rational(6*9, (3*6-2)*(3*6+1))  # 54/(16*19) = 54/304 = 27/152
    print(f"    t_6 check: Gauss = {simplify(t6_gauss)}, ours = {t6_ours}, match? {simplify(t6_gauss - t6_ours) == 0}")

    # t_7 (m=4): (a+3)(c-b+3)z/((c+6)(c+7))
    t7_gauss = (a_v + 3)*(c_v - b_v + 3)*z_v / ((c_v + 6)*(c_v + 7))
    t7_ours = Fraction(7*11, (3*7-2)*(3*7+1))
    print(f"    t_7 check: Gauss = {float(complex(simplify(t7_gauss)).real):.10f}, ours = {float(t7_ours):.10f}")


# =====================================================================
print("\n" + "=" * 70)
print("STEP 5: Numerical verification - evaluate _2F1 at found params")
print("=" * 70)

if gauss_sols:
    s = gauss_sols[0]
    mp.dps = 60
    a_f = float(complex(s[a]).real)
    b_f = float(complex(s[b]).real)
    c_f = float(complex(s[c]).real)
    z_f = float(complex(s[z]).real)
    
    print(f"\n  Parameters: a={a_f:.10f}, b={b_f:.10f}, c={c_f:.10f}, z={z_f:.10f}")
    
    f_bc = hyp2f1(a_f, b_f, c_f, z_f)
    f_bc1 = hyp2f1(a_f, b_f+1, c_f+1, z_f)
    
    ratio = f_bc1 / f_bc
    target = 4/pi
    
    print(f"  _2F1(a,b;c;z)     = {nstr(f_bc, 30)}")
    print(f"  _2F1(a,b+1;c+1;z) = {nstr(f_bc1, 30)}")
    print(f"  Ratio              = {nstr(ratio, 30)}")
    print(f"  4/pi               = {nstr(target, 30)}")
    print(f"  |ratio - 4/pi|     = {float(abs(ratio - target)):.3e}")
    
    # Also check: does the CF VALUE match?
    # Our CF = b0 + a1/(b1 + ...) with b0=1, and value = 4/pi
    # The Gauss CF gives _2F1(a,b+1;c+1;z)/_2F1(a,b;c;z)
    # After equivalence transform, this should = our CF value = 4/pi? 
    # Actually, the Gauss CF gives the RATIO directly.
    # But we need to check: in which VARIABLE is the shift?
    # Gauss gives ratio with b->b+1, c->c+1.
    # Our CF might correspond to a c-shift instead.
    
    # Try c-shift ratio:
    f_c1 = hyp2f1(a_f, b_f, c_f+1, z_f)
    ratio_c = f_c1 / f_bc
    print(f"\n  _2F1(a,b;c+1;z)/_2F1(a,b;c;z) = {nstr(ratio_c, 30)}")
    print(f"  |ratio_c - 4/pi| = {float(abs(ratio_c - target)):.3e}")
    
    # Try a-shift:
    f_a1 = hyp2f1(a_f+1, b_f, c_f, z_f)
    ratio_a = f_a1 / f_bc
    print(f"  _2F1(a+1,b;c;z)/_2F1(a,b;c;z)  = {nstr(ratio_a, 30)}")
    print(f"  |ratio_a - 4/pi| = {float(abs(ratio_a - target)):.3e}")
    
    # Try 1/_2F1:
    print(f"  1/_2F1(a,b;c;z)                 = {nstr(1/f_bc, 30)}")
    print(f"  |1/f - 4/pi|     = {float(abs(1/f_bc - target)):.3e}")
    
    # Try _2F1 itself:
    print(f"  |f - pi/4|        = {float(abs(f_bc - pi/4)):.3e}")

print("\n" + "=" * 70)
print("FINAL CLASSIFICATION")
print("=" * 70)
