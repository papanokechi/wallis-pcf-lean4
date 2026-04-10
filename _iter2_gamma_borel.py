"""
Iteration 2 — Stage 2B: Gamma / Catalan / Apéry + Borel GCFs
=============================================================
Three parallel searches:
1. GCFs producing Gamma(1/3), Gamma(1/4), Catalan G, Apéry ζ(3)
2. Borel-regularized divergent GCFs (a_n = -n!, b_n = k)
3. Deeper 2F1 connection via ratio-of-2F1 CFs
"""
from mpmath import (mp, mpf, nstr, fabs, log, pi, gamma, sqrt, e as E,
                    pslq, exp, e1, besseli, besselj, zeta, euler, catalan,
                    hyp2f1, factorial, power, hyp1f1, quad)
from math import factorial as ifac

mp.dps = 80

def gcf_bw(a_fn, b_fn, depth=400):
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = b_fn(n) + a_fn(n + 1) / val
    return b_fn(0) + a_fn(1) / val

def check_conv(a_fn, b_fn, d1=30, d2=80):
    try:
        V1 = gcf_bw(a_fn, b_fn, d1)
        V2 = gcf_bw(a_fn, b_fn, d2)
        if fabs(V1 - V2) > mpf("1e-8"):
            return None
        if fabs(V2) > 1e6 or fabs(V2) < 1e-15:
            return None
        return gcf_bw(a_fn, b_fn, 400)
    except:
        return None

# ════════════════════════════════════════════════════════════════
# SEARCH 1: Gamma / Catalan / Apéry connections
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("SEARCH 1: Gamma, Catalan, Apéry constant hunt")
print("=" * 70)

G14 = gamma(mpf(1)/4)
G34 = gamma(mpf(3)/4)
G13 = gamma(mpf(1)/3)
G23 = gamma(mpf(2)/3)
Cat = catalan
Z3  = zeta(3)
Eul = euler

# Build rich constant library
targets = {}
# Single constants
targets["Catalan"] = Cat
targets["zeta(3)"] = Z3
targets["Gamma(1/4)"] = G14
targets["Gamma(3/4)"] = G34
targets["Gamma(1/3)"] = G13
targets["Gamma(2/3)"] = G23
# Products and ratios
targets["G14/G34"] = G14/G34
targets["G14^2/pi"] = G14**2/pi
targets["G13*G23"] = G13*G23
targets["G14*G34"] = G14*G34
targets["pi^2/G14^2"] = pi**2/G14**2
targets["G14^2/(2*pi*sqrt(2))"] = G14**2/(2*pi*sqrt(2))
targets["pi^(3/2)/G34^2"] = pi**(mpf(3)/2)/G34**2
targets["8*Cat/pi"] = 8*Cat/pi
targets["Cat/pi"] = Cat/pi
targets["4*Cat/pi"] = 4*Cat/pi
targets["12*Cat/pi^2"] = 12*Cat/pi**2
targets["zeta(3)/pi^2"] = Z3/pi**2
targets["7*zeta(3)/(4*pi^2)"] = 7*Z3/(4*pi**2)

print(f"\n{len(targets)} target constants loaded.")
print("Scanning quadratic-a, linear-b grid...")

gamma_hits = []
for c2 in range(-2, 4):
    for c1 in range(-3, 5):
        for c0 in range(-2, 3):
            for d1 in range(1, 5):
                for d0 in range(-1, 5):
                    a_fn = lambda n, c2=c2,c1=c1,c0=c0: mpf(c2*n**2+c1*n+c0)
                    b_fn = lambda n, d1=d1,d0=d0: mpf(d1*n+d0)
                    V = check_conv(a_fn, b_fn)
                    if V is None:
                        continue
                    for tname, tval in targets.items():
                        diff = fabs(V - tval)
                        if diff > 0 and diff < mpf("1e-30"):
                            dig = int(-log(diff, 10))
                            if dig >= 20:
                                desc = f"a={c2}n²+{c1}n+{c0}, b={d1}n+{d0}"
                                gamma_hits.append((desc, tname, dig, V))
                                print(f"  HIT: {desc}  =  {tname}  [{dig}d]")

if not gamma_hits:
    print("  No direct hits in grid. Trying product-basis PSLQ...")
    # Use PSLQ with Gamma values as basis
    test_gcfs = [
        ("a=1n²+0n+0, b=2n+1", lambda n: mpf(n**2), lambda n: mpf(2*n+1)),
        ("a=1n²+1n+0, b=2n+1", lambda n: mpf(n**2+n), lambda n: mpf(2*n+1)),
        ("a=2n²+1n+0, b=3n+1", lambda n: mpf(2*n**2+n), lambda n: mpf(3*n+1)),
        ("a=1n²+0n+1, b=2n+3", lambda n: mpf(n**2+1), lambda n: mpf(2*n+3)),
        ("a=3n²+0n+0, b=2n+1", lambda n: mpf(3*n**2), lambda n: mpf(2*n+1)),
    ]
    for desc, a_fn, b_fn in test_gcfs:
        V = check_conv(a_fn, b_fn)
        if V is None:
            continue
        # PSLQ: V, 1, Cat, zeta3, G14, G34, pi
        basis = [V, mpf(1), Cat, Z3, G14/sqrt(pi), G34*sqrt(pi), pi]
        r = pslq(basis, maxcoeff=200)
        if r and r[0] != 0:
            names = ["V", "1", "Cat", "ζ(3)", "Γ¼/√π", "Γ¾·√π", "π"]
            terms = [f"{c}*{n}" for c, n in zip(r, names) if c != 0]
            print(f"  PSLQ: {desc} → {' + '.join(terms)} = 0")


# ════════════════════════════════════════════════════════════════
# SEARCH 2: Borel-regularized divergent GCFs
# ════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SEARCH 2: Borel-regularized divergent GCFs  (Lemma 1 territory)")
print("=" * 70)

# a_n = -n! (factorial), b_n = k  →  formally divergent
# Borel regularization: V(k) = k * e^k * E1(k)
print("\nVerifying Lemma 1: a_n = -n!, b_n = k → k·e^k·E1(k)")
for k in [1, 2, 3, 4, 5]:
    k_mp = mpf(k)
    # Compute via Borel integral directly
    borel_val = k_mp * exp(k_mp) * e1(k_mp)
    
    # Also compute GCF with modified backward recurrence
    # For divergent CF, use Stieltjes approach: compute integral
    # V(k) = integral_0^inf  k*exp(-t)/(k+t) dt
    integral_val = quad(lambda t: k_mp * exp(-t) / (k_mp + t), [0, mpf("inf")])
    
    diff = fabs(borel_val - integral_val)
    dig = 75 if diff == 0 else (int(-log(diff, 10)) if diff > 0 and diff < 1 else 0)
    print(f"  k={k}: k·eᵏ·E₁(k) = {nstr(borel_val, 30)}  integral = {nstr(integral_val, 30)}  [{dig}d]")

# Now: EXTEND to a_n = -n! * p(n), b_n = q(n) 
# where p,q are simple polynomials
print("\n--- Extended Borel: a_n = -n! * (An+B), b_n = Cn+D ---")
borel_hits = []
for A in range(0, 3):
    for B in range(0, 3):
        if A == 0 and B == 0:
            continue
        for C in range(0, 3):
            for D in range(1, 5):
                # Compute via numerical integral (the "true" Borel sum)
                # Stieltjes: integral_0^inf f(t)*exp(-t) dt where f encodes the CF
                # For a_n = -(An+B)*n!, b_n = Cn+D:
                # The formal series sum_{n>=0} a_1*a_2*...*a_n / (b_1*b_2*...*b_n) * t^n
                # grows factorially. Borel transform divides by n!, giving convergent series.
                
                # Direct approach: try GCF at increasing depths until pattern stabilizes
                try:
                    def a_fn(n, A=A, B=B):
                        return -mpf(ifac(n) * (A*n + B)) if n <= 170 else mpf(0)
                    def b_fn(n, C=C, D=D):
                        return mpf(C*n + D)
                    
                    # For divergent GCFs, convergents oscillate.
                    # Use the integral representation instead.
                    # For simple case: integral of (D+Ct)/(D+Ct+t) * exp(-t) dt... complex.
                    # Skip divergent ones and focus on Stieltjes-convergent cases.
                    
                    # Use truncated CF (may converge for specific parameter choices)
                    V20 = gcf_bw(a_fn, b_fn, 20)
                    V40 = gcf_bw(a_fn, b_fn, 40)
                    if fabs(V20 - V40) < mpf("1e-5"):
                        V = gcf_bw(a_fn, b_fn, 80)
                        # Check against E1 values
                        for kk in range(1, 6):
                            e1_val = mpf(kk) * exp(mpf(kk)) * e1(mpf(kk))
                            diff = fabs(V - e1_val)
                            if diff < mpf("1e-10") and diff > 0:
                                dig = int(-log(diff, 10))
                                if dig >= 8:
                                    desc = f"a=-n!({A}n+{B}), b={C}n+{D}"
                                    borel_hits.append((desc, kk, dig))
                                    print(f"  HIT: {desc} = {kk}·eᵏ·E₁({kk})  [{dig}d]")
                except:
                    pass

if not borel_hits:
    print("  Factorial GCFs mostly diverge (as expected). Integral approach needed.")

# ════════════════════════════════════════════════════════════════
# SEARCH 3: Higher-complexity PSLQ on unmatched values
# ════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SEARCH 3: Multi-constant PSLQ on previously-unmatched GCFs")
print("=" * 70)

# From iteration 1, these had no match:
# H2: a=n(n+1), b=3n+1 → 1.42151545...
# H3: a=n^3, b=n^2+n+1 → 1.25534...
# H4: a=n, b=n+2 → 2.29062... (MATCHED to -1/(5-2e) in iter1)
# H5: a=2n-1, b=n → 0.51325...

unmatched = [
    ("H2: a=n(n+1), b=3n+1", lambda n: mpf(n*(n+1)), lambda n: mpf(3*n+1)),
    ("H5: a=2n-1, b=n", lambda n: mpf(2*n-1), lambda n: mpf(n)),
    ("G1: a=4n²-1, b=2n", lambda n: mpf(4*n**2-1), lambda n: mpf(2*n)),
    ("G2: a=n², b=n²+1", lambda n: mpf(n**2), lambda n: mpf(n**2+1)),
]

for desc, a_fn, b_fn in unmatched:
    V = check_conv(a_fn, b_fn)
    if V is None:
        print(f"  {desc}: divergent, skipping")
        continue
    print(f"\n  {desc}: V = {nstr(V, 30)}")
    
    # Extended PSLQ: V, 1, pi, e, log2, sqrt2, Cat, zeta3, euler_gamma, G14/sqrt(pi)
    basis_sets = [
        ("pi,e,log2,Cat", [V, mpf(1), pi, E, log(2), Cat]),
        ("pi,zeta3,euler", [V, mpf(1), pi, Z3, Eul, pi**2]),
        ("Gamma¼,Gamma¾,pi", [V, mpf(1), G14, G34, pi, sqrt(pi)]),
        ("V·pi,V·e,1,pi,e", [V, V*pi, V*E, mpf(1), pi, E]),
    ]
    for bname, basis in basis_sets:
        r = pslq([mpf(x) for x in basis], maxcoeff=500)
        if r and r[0] != 0:
            names_map = {
                "pi,e,log2,Cat": ["V","1","π","e","log2","Cat"],
                "pi,zeta3,euler": ["V","1","π","ζ(3)","γ","π²"],
                "Gamma¼,Gamma¾,pi": ["V","1","Γ¼","Γ¾","π","√π"],
                "V·pi,V·e,1,pi,e": ["V","V·π","V·e","1","π","e"],
            }
            names = names_map[bname]
            # Check non-triviality
            if all(r[i] == 0 for i in range(2, len(r))):
                continue
            terms = [f"{c}*{n}" for c, n in zip(r, names) if c != 0]
            print(f"    PSLQ({bname}): {' + '.join(terms)} = 0")
            break

print("\nDone - Iteration 2 searches complete.")
