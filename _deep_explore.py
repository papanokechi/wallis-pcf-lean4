"""
Deep exploration round 2: Extend the negative-quadratic pi family 
and search for Bessel/Gamma/E1 connections.
"""
from mpmath import (mp, mpf, nstr, fabs, log, pi, gamma, sqrt, e as E, 
                    pslq, exp, e1, besseli, besselj, zeta, euler, catalan)

mp.dps = 60

def gcf_bw(a_fn, b_fn, depth=400):
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = b_fn(n) + a_fn(n + 1) / val
    return b_fn(0) + a_fn(1) / val

def check_convergence(a_fn, b_fn):
    try:
        V1 = gcf_bw(a_fn, b_fn, 30)
        V2 = gcf_bw(a_fn, b_fn, 80)
        if fabs(V1 - V2) > mpf("1e-8"):
            return None
        if fabs(V2) > 1e6 or fabs(V2) < 1e-15:
            return None
        return gcf_bw(a_fn, b_fn, 400)
    except:
        return None

# ============================================================
# PART 1: Extend the negative-quadratic pi family
# a_n = A*n^2 + B*n + C, b_n = D*n + F
# Focus: A < 0, D = 3 (known to produce pi)
# ============================================================
print("=" * 70)
print("PART 1: Negative-quadratic pi family — extended scan")
print("=" * 70)

pi_hits = []
for A in [-3, -2, -1]:
    for B in range(-3, 6):
        for C in range(-2, 3):
            for D in range(2, 5):
                for F in range(-1, 5):
                    a_fn = lambda n, A=A,B=B,C=C: mpf(A*n**2 + B*n + C)
                    b_fn = lambda n, D=D,F=F: mpf(D*n + F)
                    V = check_convergence(a_fn, b_fn)
                    if V is None:
                        continue
                    # PSLQ: V = (a + b*pi)/(c + d*pi)
                    basis = [V, V*pi, mpf(1), pi]
                    r = pslq(basis, maxcoeff=200)
                    if r and r[0] != 0 and (r[1] != 0 or r[3] != 0):
                        # Involves pi
                        denom = r[0] + r[1]*pi
                        numer = -(r[2] + r[3]*pi)
                        if fabs(denom) > 1e-10:
                            V_check = numer / denom
                            if fabs(V - V_check) < mpf("1e-40"):
                                desc = f"a={A}n2+{B}n+{C}, b={D}n+{F}"
                                cf = f"({-r[2]}+{-r[3]}*pi)/({r[0]}+{r[1]}*pi)"
                                pi_hits.append((desc, V, cf))

print(f"Found {len(pi_hits)} pi-connected GCFs:")
for desc, V, cf in sorted(pi_hits, key=lambda x: float(fabs(x[1]))):
    print(f"  {desc:30s}  V = {nstr(V, 20):>25s}  = {cf}")

# ============================================================
# PART 2: Search for Bessel and E1 connections
# a_n = A*n^2 + B*n, b_n = D*n + F with larger range
# ============================================================
print()
print("=" * 70)
print("PART 2: Bessel and Exponential Integral search")
print("=" * 70)

bessel_targets = {
    "I0(1)/I1(1)": besseli(0,1)/besseli(1,1),
    "I0(2)/I1(2)": besseli(0,2)/besseli(1,2),
    "J0(1)/J1(1)": besselj(0,1)/besselj(1,1),
    "2e^2*E1(2)": 2*E**2*e1(2),
    "e*E1(1)": E*e1(1),
    "3e^3*E1(3)": 3*E**3*e1(3),
    "Gamma(1/4)/Gamma(3/4)": gamma(mpf(1)/4)/gamma(mpf(3)/4),
    "Gamma(1/3)/Gamma(2/3)": gamma(mpf(1)/3)/gamma(mpf(2)/3),
}

bessel_hits = []
for A in range(-1, 3):
    for B in range(-2, 4):
        for C in range(-1, 2):
            for D in range(1, 5):
                for F in range(0, 5):
                    a_fn = lambda n, A=A,B=B,C=C: mpf(A*n**2 + B*n + C)
                    b_fn = lambda n, D=D,F=F: mpf(D*n + F)
                    V = check_convergence(a_fn, b_fn)
                    if V is None:
                        continue
                    for tname, tval in bessel_targets.items():
                        diff = fabs(V - tval)
                        if diff > 0 and diff < mpf("1e-30"):
                            dig = int(-log(diff, 10))
                            desc = f"a={A}n2+{B}n+{C}, b={D}n+{F}"
                            bessel_hits.append((desc, tname, dig))
                            print(f"  MATCH: {desc}  =  {tname}  [{dig} digits]")

if not bessel_hits:
    print("  No direct Bessel/E1 matches in linear-denominator scan.")
    print("  Trying quadratic denominators...")
    
    for A in range(0, 3):
        for B in range(-1, 3):
            for D2 in range(0, 2):
                for D1 in range(1, 4):
                    for D0 in range(0, 4):
                        a_fn = lambda n, A=A,B=B: mpf(A*n**2 + B*n)
                        b_fn = lambda n, D2=D2,D1=D1,D0=D0: mpf(D2*n**2 + D1*n + D0)
                        V = check_convergence(a_fn, b_fn)
                        if V is None:
                            continue
                        for tname, tval in bessel_targets.items():
                            diff = fabs(V - tval)
                            if diff > 0 and diff < mpf("1e-20"):
                                dig = int(-log(diff, 10))
                                if dig >= 15:
                                    desc = f"a={A}n2+{B}n, b={D2}n2+{D1}n+{D0}"
                                    print(f"  MATCH: {desc}  =  {tname}  [{dig} digits]")

# ============================================================
# PART 3: Coefficient -3 exploration
# ============================================================
print()
print("=" * 70)
print("PART 3: a_n = -3n^2 + Bn family (extending beyond -2)")
print("=" * 70)

for B in range(-2, 8):
    for D in range(2, 6):
        for F in range(0, 5):
            a_fn = lambda n, B=B: mpf(-3*n**2 + B*n)
            b_fn = lambda n, D=D, F=F: mpf(D*n + F)
            V = check_convergence(a_fn, b_fn)
            if V is None:
                continue
            # Check pi and e
            basis = [V, V*pi, mpf(1), pi]
            r = pslq(basis, maxcoeff=200)
            if r and r[0] != 0 and (r[1] != 0 or r[3] != 0):
                denom = r[0] + r[1]*pi
                numer = -(r[2] + r[3]*pi)
                if fabs(denom) > 1e-10:
                    V_check = numer / denom
                    if fabs(V - V_check) < mpf("1e-40"):
                        desc = f"a=-3n2+{B}n, b={D}n+{F}"
                        print(f"  PI-HIT: {desc}  V={nstr(V,20)}  = ({-r[2]}+{-r[3]}*pi)/({r[0]}+{r[1]}*pi)")

            basis2 = [V, V*E, mpf(1), E]
            r2 = pslq(basis2, maxcoeff=200)
            if r2 and r2[0] != 0 and (r2[1] != 0 or r2[3] != 0):
                denom = r2[0] + r2[1]*E
                numer = -(r2[2] + r2[3]*E)
                if fabs(denom) > 1e-10:
                    V_check = numer / denom
                    if fabs(V - V_check) < mpf("1e-40"):
                        desc = f"a=-3n2+{B}n, b={D}n+{F}"
                        print(f"  E-HIT:  {desc}  V={nstr(V,20)}  = ({-r2[2]}+{-r2[3]}*e)/({r2[0]}+{r2[1]}*e)")

print("\nDone.")
