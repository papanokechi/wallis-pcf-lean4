"""
Iteration 2 — Stage 2C: Deep Borel exploration + Cubic GCFs + 2F1 ratio CF
===========================================================================
"""
from mpmath import (mp, mpf, nstr, fabs, log, pi, gamma, sqrt, e as E,
                    pslq, exp, e1, besseli, besselj, zeta, euler, catalan,
                    hyp2f1, quad, inf, airyai, airybi, polylog)

mp.dps = 80

def gcf_bw(a_fn, b_fn, depth=400):
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = b_fn(n) + a_fn(n + 1) / val
    return b_fn(0) + a_fn(1) / val

def check_conv(a_fn, b_fn):
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

# ═══════════════════════════════════════════════════════════
# PART 1: Borel-regularized GCFs with polynomial b_n
# ═══════════════════════════════════════════════════════════
print("=" * 70)
print("PART 1: Borel-regularized GCFs — Stieltjes integral approach")
print("=" * 70)

# The Stieltjes integral for GCF with a_n = -n!, b_n = f(n):
# For b_n = k (constant): V(k) = k·eᵏ·E₁(k)
# For b_n = k + n: different formula (confluent hypergeometric)
# For b_n = αn + β: V = integral_0^∞ (β + αt)/(β + (α-1)t + t²) · e^{-t} dt ??
# Actually it's non-trivial. Let me compute via direct integral representation.

# Known: the Stieltjes-type integral for the formal series
# S = sum_{n=0}^∞ (-1)^n n! / k^{n+1} which diverges
# has Borel sum = integral_0^∞ e^{-t}/(k+t) dt = e^k E_1(k)
# The CF coefficients are a_n = -n (not -n!), b_0 = k, b_n = k+n... 
# Wait, let me re-derive properly.

# For the Euler CF of e^z E_1(z):  
# e^z E_1(z) = cfrac{1}{z+1-cfrac{1^2}{z+3-cfrac{2^2}{z+5-cfrac{3^2}{z+7-...}}}}
# So a_n = -n^2, b_0 = z+1, b_n = z+2n+1

print("\n--- Euler CF for e^z · E1(z) ---")
for z_val in [1, 2, 3, 5, 10]:
    z = mpf(z_val)
    # a_n = -n^2, b_n = z + 2n + 1
    V = gcf_bw(lambda n, z=z: -mpf(n**2), lambda n, z=z: z + 2*n + 1, 400)
    exact = exp(z) * e1(z)
    # But V is 1/(z+1 - 1/(z+3 - ...)) so it's 1/CF, let me check
    V_inv = 1 / V if V != 0 else mpf(0)
    diff_v = fabs(V - exact)
    diff_i = fabs(V_inv - exact)
    if diff_v < diff_i:
        d = fabs(V - exact)
        dig = 75 if d == 0 else (int(-log(d, 10)) if 0 < d < 1 else 0)
        print(f"  z={z_val}: CF = {nstr(V, 25)}  e^z·E1(z) = {nstr(exact, 25)}  [{dig}d, direct]")
    else:
        d = fabs(V_inv - exact)
        dig = 75 if d == 0 else (int(-log(d, 10)) if 0 < d < 1 else 0)
        print(f"  z={z_val}: 1/CF = {nstr(V_inv, 25)}  e^z·E1(z) = {nstr(exact, 25)}  [{dig}d, reciprocal]")

# Now: PERTURB the Euler E1 CF
print("\n--- Perturbed E1 CFs: a_n = -(n^2 + αn), b_n = z + 2n + 1 + β ---")
z = mpf(2)
base = exp(z) * e1(z)
for alpha in range(-2, 4):
    for beta in range(-2, 4):
        if alpha == 0 and beta == 0:
            continue
        try:
            V = gcf_bw(lambda n, a=alpha: -mpf(n**2 + a*n), 
                       lambda n, b=beta, z=z: z + 2*n + 1 + b, 400)
            V_check = gcf_bw(lambda n, a=alpha: -mpf(n**2 + a*n),
                            lambda n, b=beta, z=z: z + 2*n + 1 + b, 200)
            if fabs(V - V_check) > mpf("1e-15"):
                continue
                
            # Try matching to e^z E1(z) variants and integrals
            targs = {
                "e²E1(2)": exp(2)*e1(2),
                "e³E1(3)": exp(3)*e1(3),
                "eE1(1)": exp(1)*e1(1),
                "2e²E1(2)": 2*exp(2)*e1(2),
                "1/(2e²E1(2))": 1/(2*exp(2)*e1(2)),
            }
            for tn, tv in targs.items():
                d = fabs(V - tv)
                if 0 < d < mpf("1e-30"):
                    dig = int(-log(d, 10))
                    if dig >= 20:
                        print(f"  α={alpha:+d}, β={beta:+d}: V = {tn}  [{dig}d]")
                # Also try 1/V
                d2 = fabs(1/V - tv) if V != 0 else mpf(999)
                if 0 < d2 < mpf("1e-30"):
                    dig2 = int(-log(d2, 10))
                    if dig2 >= 20:
                        print(f"  α={alpha:+d}, β={beta:+d}: 1/V = {tn}  [{dig2}d]")
            
            # PSLQ against e1 basis
            basis = [V, mpf(1), exp(2)*e1(2), E, pi]
            r = pslq(basis, maxcoeff=100)
            if r and r[0] != 0 and any(r[i] != 0 for i in [2, 4]):
                names = ["V", "1", "e²E₁(2)", "e", "π"]
                terms = [f"{c}*{n}" for c, n in zip(r, names) if c != 0]
                print(f"  α={alpha:+d}, β={beta:+d}: PSLQ → {' + '.join(terms)} = 0")
        except:
            pass

# ═══════════════════════════════════════════════════════════
# PART 2: GCFs with cubic numerators → Gamma / Airy / Catalan
# ═══════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PART 2: Cubic-numerator GCFs — hunting Gamma and Catalan")
print("=" * 70)

G14 = gamma(mpf(1)/4)
G34 = gamma(mpf(3)/4)
G13 = gamma(mpf(1)/3)
G23 = gamma(mpf(2)/3)
Cat = catalan
Z3 = zeta(3)

# Build target list including Airy values (which go through Gamma(1/3))
targets_ext = {
    "Cat": Cat,
    "ζ(3)": Z3,
    "Γ¼/Γ¾": G14/G34,
    "Γ14²/(2π)": G14**2/(2*pi),
    "Γ13·Γ23/(2π/√3)": G13*G23/(2*pi/sqrt(3)),
    "π³/²/Γ34²": pi**(mpf(3)/2)/G34**2,
    "Ai(0)": airyai(0),   # = 1/(3^{2/3} Gamma(2/3))
    "Ai'(0)": -airyai(0, derivative=1) if hasattr(airyai, '__call__') else mpf(0),
    "3^{1/3}Γ(1/3)/(2π)": mpf(3)**(mpf(1)/3)*G13/(2*pi),
    "12Cat/π²": 12*Cat/pi**2,
    "2Cat/π": 2*Cat/pi,
    "B(1/4,1/4)/4": gamma(mpf(1)/4)**2 / (4*gamma(mpf(1)/2)),
}

print(f"\n{len(targets_ext)} targets. Scanning cubic a_n = An³+Bn²+Cn, linear b_n...")

cubic_hits = []
for A in [1, -1, 2, -2]:
    for B in range(-2, 3):
        for C_coef in range(-2, 3):
            for d1 in range(1, 5):
                for d0 in range(0, 4):
                    a_fn = lambda n, A=A, B=B, C=C_coef: mpf(A*n**3 + B*n**2 + C*n)
                    b_fn = lambda n, d1=d1, d0=d0: mpf(d1*n + d0)
                    V = check_conv(a_fn, b_fn)
                    if V is None:
                        continue
                    for tname, tval in targets_ext.items():
                        d = fabs(V - tval)
                        if 0 < d < mpf("1e-30"):
                            dig = int(-log(d, 10))
                            if dig >= 20:
                                desc = f"a={A}n³+{B}n²+{C_coef}n, b={d1}n+{d0}"
                                cubic_hits.append((desc, tname, dig))
                                print(f"  HIT: {desc}  =  {tname}  [{dig}d]")
                    
                    # Also PSLQ for multi-constant relations
                    basis = [V, V*pi, mpf(1), pi, Cat, Z3]
                    r = pslq(basis, maxcoeff=100)
                    if r and r[0] != 0 and any(r[i] != 0 for i in [4,5]):
                        names = ["V", "V·π", "1", "π", "Cat", "ζ(3)"]
                        terms = [f"{c}*{n}" for c, n in zip(r, names) if c != 0]
                        desc = f"a={A}n³+{B}n²+{C_coef}n, b={d1}n+{d0}"
                        print(f"  CATALAN/ZETA PSLQ: {desc} → {' + '.join(terms)} = 0")

if not cubic_hits:
    print("  No direct Gamma/Catalan hits from cubic GCFs.")

# ═══════════════════════════════════════════════════════════
# PART 3: 2F1 ratio GCF → derive π-family analytically
# ═══════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PART 3: Gauss CF for 2F1 ratios at z=-1 → π connection")
print("=" * 70)

# Key insight: many pi-formulas come from 2F1 at z=-1 or z=1/2.
# Gauss CF for 2F1(a,b;c;-1)/2F1(a,b;c;-1) with specific params.
# Also: 4/pi = 2F1(1/2, 1/2; 1; 1) = sum of Wallis-type terms.

# The CF for arctan(1) = pi/4 comes from:
# 4/pi = 1 + 1^2/(2 + 3^2/(2 + 5^2/(2 + ...)))
# i.e. b_n = 2, a_n = (2n-1)^2 for n>=1

# Our family a_n = -2n²+cn, b_n = 3n+f has the form:
# a_n / b_n ≈ -2n/3 for large n → this is a "divergent tendency" modified by
# the alternating sign from negative a_n.

# Check: Gauss CF for 2F1(1/2, α; 3/2; -1) which gives arctan variants
print("\n2F1(1/2, α; 3/2; -1) for various α:")
for alpha_num in range(1, 8):
    for alpha_den in [2, 3, 4, 6]:
        alpha = mpf(alpha_num) / alpha_den
        if alpha >= mpf(3)/2:
            continue
        try:
            val = hyp2f1(mpf(1)/2, alpha, mpf(3)/2, -1)
            # Check pi-rationality
            r = pslq([val, mpf(1), pi, pi**2], maxcoeff=200)
            if r and any(r[i] != 0 for i in [2,3]):
                terms = [f"{c}*{n}" for c, n in zip(r, ["V","1","π","π²"]) if c != 0]
                print(f"  α={alpha_num}/{alpha_den}: 2F1(1/2,{nstr(alpha,4)};3/2;-1) = {nstr(val,20)}  PSLQ: {' + '.join(terms)} = 0")
        except:
            pass

# Also try 2F1(a,b;c;z) at z=-1 with various (a,b,c) 
print("\n2F1(a,b;c;-1) π-producers:")
pi_producers = []
for a2 in range(1, 5):
    for b2 in range(1, 5):
        for c2 in range(1, 7):
            a = mpf(a2)/2
            b = mpf(b2)/2
            c = mpf(c2)/2
            try:
                val = hyp2f1(a, b, c, -1)
                if fabs(val) > 100 or fabs(val) < 1e-10:
                    continue
                r = pslq([val, mpf(1), pi, sqrt(2), sqrt(2)*pi], maxcoeff=200)
                if r and any(r[i] != 0 for i in [2,4]):
                    terms = [f"{c_}*{n}" for c_, n in zip(r, ["V","1","π","√2","√2·π"]) if c_ != 0]
                    print(f"  2F1({nstr(a,3)},{nstr(b,3)};{nstr(c,3)};-1) = {nstr(val,20)}  {' + '.join(terms)} = 0")
                    pi_producers.append((a, b, c, val, r))
            except:
                pass

# ═══════════════════════════════════════════════════════════
# PART 4: Can we form the π-family GCF from these 2F1?
# ═══════════════════════════════════════════════════════════
print()
print("=" * 70)
print("PART 4: Match π family GCF values to 2F1 combinations")
print("=" * 70)

# V = 2/(π-2) ≈ 1.7519...
# Try 2F1(a,b;c;z) for z in {-1, 1/2, 1/4, 1} with half-integer params
V_pi = 2/(pi-2)
print(f"\nTarget: 2/(π-2) = {nstr(V_pi, 25)}")

for z_val in [-1, mpf(1)/2, mpf(1)/4]:
    for a2 in range(-2, 6):
        for b2 in range(-2, 6):
            for c2 in range(1, 8):
                a, b, c = mpf(a2)/2, mpf(b2)/2, mpf(c2)/2
                if c <= 0:
                    continue
                try:
                    val = hyp2f1(a, b, c, z_val)
                    if fabs(val) > 100 or fabs(val) < 1e-10:
                        continue
                    diff = fabs(val - V_pi)
                    if 0 < diff < mpf("1e-40"):
                        dig = int(-log(diff, 10))
                        if dig >= 30:
                            print(f"  MATCH: 2F1({nstr(a,3)},{nstr(b,3)};{nstr(c,3)};{nstr(z_val,4)}) = 2/(π-2) [{dig}d]")
                except:
                    pass

print("\nDone - Iteration 2C complete.")
