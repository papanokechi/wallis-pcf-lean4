"""
Iteration 2 — Stage 2A: Hypergeometric Derivation of the π Family
=================================================================
Goal: Identify the specific 2F1(a,b;c;z) parameters that produce
the negative-quadratic π family from Iteration 1.

The Gauss CF for 2F1 ratios:
  2F1(a,b;c;z)/2F1(a,b+1;c+1;z) has a CF with:
    d_{2m+1} = -(a+m)(c-b+m) / ((c+2m)(c+2m+1))
    d_{2m}   = -(b+m)(c-a+m) / ((c+2m-1)(c+2m))
  at z=1.

We check: can we map a_n = -2n^2+cn+d, b_n = 3n+f to such a Gauss CF?
"""
from mpmath import (mp, mpf, nstr, fabs, log, pi, gamma, sqrt, e as E,
                    pslq, hyp2f1, hyp1f1, rf, beta)

mp.dps = 80

def gcf_bw(a_fn, b_fn, depth=500):
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = b_fn(n) + a_fn(n + 1) / val
    return b_fn(0) + a_fn(1) / val


# ════════════════════════════════════════════════════════════════
# PART A: Direct 2F1 ratio check
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("PART A: Can a_n=-2n^2+n, b_n=3n+2 arise from Gauss CF at z=1?")
print("=" * 70)

# Our best example: a_n = -2n^2+n, b_n = 3n+2 → V = 2/(pi-2)
V_target = 2 / (pi - 2)
print(f"\nTarget: V = 2/(pi-2) = {nstr(V_target, 40)}")

# The Gauss CF for 2F1(a,b;c;1) = Gamma(c)Gamma(c-a-b)/(Gamma(c-a)Gamma(c-b))
# when c-a-b > 0 (convergence condition).
# Scan: which (a,b,c) produce 2/(pi-2)?

print("\nScanning 2F1(a,b;c;1) for a,b,c in {k/6 : k=-6..12}...")

hits_2f1 = []
# Use half-integer and third-integer parameters (typical for pi-producing 2F1)
fracs = [mpf(k)/6 for k in range(-6, 13) if k != 0]
fracs += [mpf(k)/4 for k in range(-4, 9) if k != 0]  
fracs_unique = sorted(set(fracs))

for a in fracs_unique:
    for b in fracs_unique:
        for c in fracs_unique:
            # convergence requires c-a-b > 0
            if c - a - b <= 0:
                continue
            # avoid poles
            if c <= 0 and c == int(c):
                continue
            try:
                val = hyp2f1(a, b, c, 1)
                diff = fabs(val - V_target)
                if diff < mpf("1e-40"):
                    dig = int(-log(diff, 10)) if diff > 0 else 75
                    hits_2f1.append((float(a), float(b), float(c), dig))
                    print(f"  HIT: 2F1({nstr(a,4)}, {nstr(b,4)}; {nstr(c,4)}; 1) = {nstr(val, 25)} [{dig} dig]")

                # Also check 1/V, V-1, V+1, 2V, pi*V/4
                for label, transform in [("1/V", 1/V_target), ("V-1", V_target-1), 
                                          ("pi*V/4", pi*V_target/4)]:
                    diff2 = fabs(val - transform)
                    if diff2 < mpf("1e-40") and diff2 > 0:
                        dig2 = int(-log(diff2, 10))
                        if dig2 >= 30:
                            print(f"  HIT: 2F1({nstr(a,4)}, {nstr(b,4)}; {nstr(c,4)}; 1) = {label} [{dig2} dig]")
            except:
                pass

# ════════════════════════════════════════════════════════════════
# PART B: Check all pi-family members against 2F1 ratios
# ════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PART B: pi-family members vs Gamma-ratio formulas")
print("=" * 70)

# 2F1(a,b;c;1) = Gamma(c)*Gamma(c-a-b) / (Gamma(c-a)*Gamma(c-b))
# So if V ∈ Q(pi), we need a Gamma formula that equals a/b+c*pi/d.
# pi arises from Gamma(1/2) = sqrt(pi).
# So look for half-integer parameters.

pi_family = [
    ("a=-2n²+n, b=3n+2", 2/(pi-2)),
    ("a=-2n²+3n, b=3n+2", 12/(3*pi-4)),
    ("a=(n+1)², b=2n+3", pi/(4-pi)),
    ("a=n²+2n, b=2n+3", 4/(pi-2)),
    ("a=-2n²-n, b=3n+3", 2/(pi-4)),  # note: pi-4 < 0
    ("a=-2n²+n, b=3n+3", 4/(3*pi-8)),
    ("a=-2n²+5n, b=3n+2", 80/(15*pi-16)),
]

# For each, try 2F1(a,b;c;1) with half-integer params
print("\nChecking Gamma(c)Gamma(c-a-b)/(Gamma(c-a)Gamma(c-b)) formulas...")
for label, target in pi_family:
    print(f"\n  {label}: V = {nstr(target, 25)}")
    found = False
    # Try half-integer a,b,c
    for a2 in range(-4, 8):
        aa = mpf(a2) / 2
        for b2 in range(-4, 8):
            bb = mpf(b2) / 2
            for c2 in range(1, 12):
                cc = mpf(c2) / 2
                if cc - aa - bb <= 0:
                    continue
                if cc <= 0:
                    continue
                try:
                    gval = gamma(cc) * gamma(cc - aa - bb) / (gamma(cc - aa) * gamma(cc - bb))
                    diff = fabs(gval - target)
                    if diff < mpf("1e-50"):
                        dig = 75 if diff == 0 else int(-log(diff, 10))
                        if dig >= 40:
                            print(f"    = Γ({nstr(cc,3)})Γ({nstr(cc-aa-bb,3)})/(Γ({nstr(cc-aa,3)})Γ({nstr(cc-bb,3)}))")
                            print(f"      i.e. 2F1({nstr(aa,3)},{nstr(bb,3)};{nstr(cc,3)};1) [{dig}d]")
                            found = True
                except:
                    pass
    if not found:
        # Try ratio of two Gamma products
        for n1 in range(1, 6):
            for d1 in range(1, 6):
                for n2 in range(1, 6):
                    for d2 in range(1, 6):
                        try:
                            g = gamma(mpf(n1)/d1) / gamma(mpf(n2)/d2)
                            # Check g, g/sqrt(pi), g*sqrt(pi), g/pi, g*2/pi
                            for lbl, mult in [("Γ/Γ", 1), ("Γ/(Γ√π)", 1/sqrt(pi)), 
                                               ("Γ√π/Γ", sqrt(pi)), ("2Γ/(πΓ)", 2/pi)]:
                                diff = fabs(g * mult - target)
                                if diff < mpf("1e-50") and diff >= 0:
                                    dig = 75 if diff == 0 else int(-log(diff, 10))
                                    if dig >= 40:
                                        print(f"    = {lbl} * Γ({n1}/{d1})/Γ({n2}/{d2}) [{dig}d]")
                                        found = True
                        except:
                            pass
    if not found:
        print(f"    (no simple Gamma/2F1 match found)")

# ════════════════════════════════════════════════════════════════
# PART C: Euler CF transform analysis
# ════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PART C: Euler equivalence transform identification")
print("=" * 70)

# Check if a_n=-2n²+n, b_n=3n+2 can be equivalence-transformed 
# into a standard Gauss CF form.
# An equivalence transform: multiply numerator & denominator of nth fraction
# by c_n, giving a'_n = c_n*c_{n-1}*a_n, b'_n = c_n*b_n.

# For Gauss CF: b_n=1 and a_n = d_n*z where d_n are the Gauss coefficients.
# We want: c_n*(3n+2) = 1 for all n => c_n = 1/(3n+2).
# Then a'_n = a_n * c_n * c_{n-1} = (-2n²+n)/(3n+2)/(3(n-1)+2)
#           = (-2n²+n)/((3n+2)(3n-1))
#           = n(-2n+1)/((3n+2)(3n-1))

# For n=1: a'_1 = 1*(-1)/(5*2) = -1/10
# For n=2: a'_2 = 2*(-3)/(8*5) = -6/40 = -3/20
# For n=3: a'_3 = 3*(-5)/(11*8) = -15/88

# Compare to Gauss: d_{2m+1}*z = -(a+m)(c-b+m)/((c+2m)(c+2m+1))
#                    d_{2m}*z   = -(b+m)(c-a+m)/((c+2m-1)(c+2m))

# At z=1: d_1 = -a(c-b)/(c(c+1)), d_2 = -(b+0)(c-a)/(c+1)(c+2)) wait, 
# d_1 = -a(c-b)/(c(c+1)), but our a'_1 = -1/10.
# So a(c-b)/(c(c+1)) = 1/10.

# Let's solve numerically for a,b,c.
print("\nEquivalence-transform coefficients a'_n for a=-2n²+n, b=3n+2:")
for n in range(1, 8):
    a_prime = mpf(n*(-2*n + 1)) / ((3*n+2) * (3*(n-1)+2))
    if n == 1:
        a_prime_1 = mpf(-2+1) / ((3+2) * (3*0+2))  # = -1/10
        a_prime = a_prime_1
    print(f"  n={n}: a'_n = {nstr(a_prime, 10)}")

print("\n  Gauss d_n pattern: d_1 = a(c-b)/(c(c+1)), d_2 = (b)(c-a)/((c+1)(c+2))")
print("  Need: d_1 = 1/10 where the sign is absorbed. Solving...")
# a*(c-b)/(c*(c+1)) = 1/10
# (b)*(c-a)/((c+1)*(c+2)) = 3/20
# (a+1)*(c-b+1)/((c+2)*(c+3)) = 15/88

# System of 3 equations in 3 unknowns (a,b,c)
# Solve numerically with mpmath
from mpmath import findroot

def gauss_system(a, b, c):
    # d_1 (m=0, odd): -(a+0)(c-b+0)/((c+0)(c+1)) = d_1
    d1 = a*(c-b)/(c*(c+1))
    # d_2 (m=1, even): -(b+0)(c-a+0)/((c+1)(c+2)) = d_2  wait, indexing...
    # Actually for standard Gauss CF: the n-th coefficient (n starting from 1) is:
    # For odd n=2m+1: -(a+m)(c-b+m)/((c+2m)(c+2m+1)) * z
    # For even n=2m:  -(b+m-1)(c-a+m-1)/((c+2m-2)(c+2m-1)) * z  
    # Hmm, conventions vary. Let me use the standard form:
    # CF = b0 + K(a_n/1) where a_n are the Gauss coefficients.
    # a_1 = ab/(c(c+1)) at z=-1... this gets complicated.
    # Let me just use brute force: compute 2F1 ratio CFs and compare.
    eq1 = d1 - mpf(1)/10
    d2 = (b)*(c-a)/((c+1)*(c+2))
    eq2 = d2 - mpf(3)/20
    d3 = (a+1)*(c-b+1)/((c+2)*(c+3))
    eq3 = d3 - mpf(15)/88
    return eq1, eq2, eq3

try:
    sol = findroot(gauss_system, (mpf("0.5"), mpf("0.5"), mpf("1.5")))
    print(f"  Solution: a={nstr(sol[0],10)}, b={nstr(sol[1],10)}, c={nstr(sol[2],10)}")
    a_sol, b_sol, c_sol = sol
    # Check: 2F1(a,b;c;1)
    if c_sol - a_sol - b_sol > 0:
        val_2f1 = hyp2f1(a_sol, b_sol, c_sol, 1)
        print(f"  2F1({nstr(a_sol,6)}, {nstr(b_sol,6)}; {nstr(c_sol,6)}; 1) = {nstr(val_2f1, 25)}")
        print(f"  Target 2/(pi-2) = {nstr(2/(pi-2), 25)}")
except Exception as e:
    print(f"  findroot failed: {e}")

print("\nDone Part C.")
