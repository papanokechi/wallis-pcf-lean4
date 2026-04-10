"""
Iteration 2 — Stage 2D: Proper cubic search (exclude a(1)=0 ghosts)
+ Extended Borel family + 2F1 ratio CF for pi derivation
"""
from mpmath import (mp, mpf, nstr, fabs, log, pi, gamma, sqrt, e as E,
                    pslq, exp, e1, besseli, besselj, zeta, euler, catalan,
                    hyp2f1, quad, hyp1f1)

mp.dps = 60

def gcf_bw(a_fn, b_fn, depth=400):
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = b_fn(n) + a_fn(n + 1) / val
    return b_fn(0) + a_fn(1) / val

def check_conv(a_fn, b_fn):
    try:
        # GHOST CHECK: if a(1) is zero or near-zero, skip
        a1_val = a_fn(1)
        if fabs(a1_val) < mpf("1e-10"):
            return None
        V1 = gcf_bw(a_fn, b_fn, 30)
        V2 = gcf_bw(a_fn, b_fn, 80)
        if fabs(V1 - V2) > mpf("1e-8"):
            return None
        if fabs(V2) > 1e6 or fabs(V2) < 1e-15:
            return None
        return gcf_bw(a_fn, b_fn, 400)
    except:
        return None

G14 = gamma(mpf(1)/4)
G34 = gamma(mpf(3)/4)
G13 = gamma(mpf(1)/3)
G23 = gamma(mpf(2)/3)
Cat = catalan
Z3 = zeta(3)
Eul = euler

# Rich target list (excluding trivial = 1 cases)
targets = {
    "Cat": Cat,
    "ζ(3)": Z3,
    "γ": Eul,
    "Γ(1/4)": G14,
    "Γ(3/4)": G34,
    "Γ(1/3)": G13,
    "Γ(2/3)": G23,
    "Γ¼/Γ¾": G14/G34,
    "Γ¼²/(2π)": G14**2/(2*pi),
    "Γ¼²/(4√2π)": G14**2/(4*sqrt(2)*pi),
    "π^{3/2}/Γ¾²": pi**(mpf(3)/2)/G34**2,
    "4Cat/π": 4*Cat/pi,
    "8Cat/π": 8*Cat/pi, 
    "12Cat/π²": 12*Cat/pi**2,
    "ζ(3)/π²": Z3/pi**2,
    "Li₂(1/2)": (pi**2 - 6*log(2)**2)/12,  # = ζ(2)/2 - log(2)^2/2
    "3√3·Γ(1/3)³/(4π²)": 3*sqrt(3)*G13**3/(4*pi**2),
    "Γ(1/4)⁴/(4π³)": G14**4/(4*pi**3),
}

# ════════════════════════════════════════════════════════════════
# SEARCH A: Proper cubic GCFs (a(1) ≠ 0)
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("SEARCH A: Cubic GCFs with a(1) ≠ 0 → Gamma/Catalan/Apéry")
print("=" * 70)

hits = []
for A in [-2, -1, 1, 2]:
    for B in range(-2, 4):
        for C in range(-2, 4):
            for d1 in range(1, 5):
                for d0 in range(0, 4):
                    a_fn = lambda n, A=A,B=B,C=C: mpf(A*n**3 + B*n**2 + C*n)
                    b_fn = lambda n, d1=d1,d0=d0: mpf(d1*n + d0)
                    V = check_conv(a_fn, b_fn)
                    if V is None:
                        continue
                    for tname, tval in targets.items():
                        d = fabs(V - tval)
                        if 0 < d < mpf("1e-30"):
                            dig = int(-log(d, 10))
                            if dig >= 15:
                                desc = f"a={A}n³+{B}n²+{C}n, b={d1}n+{d0}"
                                hits.append((desc, tname, dig, V))
                                print(f"  HIT: {desc}  =  {tname}  [{dig}d]")
                    
                    # PSLQ with extended basis
                    for bname, basis, names in [
                        ("Cat,ζ3,π", [V, mpf(1), Cat, Z3, pi], ["V","1","Cat","ζ3","π"]),
                        ("Γ¼,π", [V, mpf(1), G14, G34, pi], ["V","1","Γ¼","Γ¾","π"]),
                    ]:
                        r = pslq(basis, maxcoeff=200)
                        if r and r[0] != 0 and any(r[i] != 0 for i in [2,3]):
                            terms = [f"{c}*{n}" for c, n in zip(r, names) if c != 0]
                            desc = f"a={A}n³+{B}n²+{C}n, b={d1}n+{d0}"
                            rel = " + ".join(terms)
                            # Verify non-triviality
                            if fabs(V - 1) < mpf("1e-10"):
                                continue  # another ghost
                            hits.append((desc, f"PSLQ({bname})", 0, V))
                            print(f"  PSLQ: {desc} → {rel} = 0")
                            break

if not hits:
    print("  No Gamma/Catalan hits from non-degenerate cubic GCFs")

# ════════════════════════════════════════════════════════════════
# SEARCH B: Borel E1 parametric family
# ════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SEARCH B: Borel E1 parametric family — Euler CF variations")
print("=" * 70)

# Verified: 1/CF = e^z E1(z) for a_n = -n^2, b_n = z + 2n + 1
# This is the Euler CF representation.
# Perturbed: shifting z in b_n moves between E1 values.
# Now: what about a_n = -(n^2 + αn + β)?

print("\nParametric: a_n = -(n² + αn + β), b_n = z + 2n + 1")
for z_val in [1, 2, 3]:
    z = mpf(z_val)
    print(f"\n  z = {z_val}:")
    for alpha in range(-2, 4):
        for beta in range(-2, 3):
            try:
                a_fn = lambda n, a=alpha, b=beta: -(mpf(n)**2 + a*mpf(n) + b)
                b_fn = lambda n, z=z: z + 2*mpf(n) + 1
                V1 = gcf_bw(a_fn, b_fn, 50)
                V2 = gcf_bw(a_fn, b_fn, 200)
                if fabs(V1 - V2) > mpf("1e-10"):
                    continue
                V = gcf_bw(a_fn, b_fn, 400)
                if fabs(V) < 1e-15 or fabs(V) > 1e6:
                    continue
                
                # Check both V and 1/V against E1 basis
                for val, vname in [(V, "CF"), (1/V if V != 0 else mpf(0), "1/CF")]:
                    basis = [val, mpf(1), exp(z)*e1(z), E, pi, exp(z)]
                    r = pslq(basis, maxcoeff=100)
                    if r and r[0] != 0 and any(r[i] != 0 for i in [2,5]):
                        names = [vname, "1", "e^z·E₁(z)", "e", "π", "e^z"]
                        terms = [f"{c}*{n}" for c,n in zip(r, names) if c != 0]
                        print(f"    α={alpha:+d},β={beta:+d}: {' + '.join(terms)} = 0")
                        break
            except:
                pass

# ════════════════════════════════════════════════════════════════
# SEARCH C: 2F1 ratio approach for the π family
# ════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SEARCH C: Derive π family via Gauss CF composition")
print("=" * 70)

# The Gauss CF for f(z) = 2F1(a,b;c;z)/2F1(a,b+1;c+1;z):
# f(z) = 1/(1 + d1*z/(1 + d2*z/(1 + ...)))
# where d_{2n-1} = (a+n-1)(c-b+n-1)/((c+2n-3)(c+2n-2))
#        d_{2n}   = (b+n)(c-a+n-1)/((c+2n-2)(c+2n-1))  [Cuyt et al.]
#
# At z=1 with specific (a,b,c), this might map to our polynomial form.

# Instead, let's check: 2F1(1/2,1;3/2;-1) = pi/4 (known).
# The Gauss CF for this at z=-1 has coefficients...
# Actually, let me just try to match the GCF values directly to 2F1 *ratios*
# (not single 2F1 values).

V_target = 2/(pi-2)
print(f"\nTarget: V = 2/(π-2) = {nstr(V_target, 30)}")
print("Trying 2F1 ratios and products:")

for a1 in range(1, 5):
    for b1 in range(1, 5):
        for c1 in range(1, 7):
            for a2 in range(1, 5):
                for b2 in range(1, 5):
                    for c2 in range(1, 7):
                        aa1, bb1, cc1 = mpf(a1)/2, mpf(b1)/2, mpf(c1)/2
                        aa2, bb2, cc2 = mpf(a2)/2, mpf(b2)/2, mpf(c2)/2
                        if cc1 <= 0 or cc2 <= 0:
                            continue
                        try:
                            h1 = hyp2f1(aa1, bb1, cc1, -1)
                            h2 = hyp2f1(aa2, bb2, cc2, -1)
                            if fabs(h2) < 1e-10:
                                continue
                            ratio = h1/h2
                            d = fabs(ratio - V_target)
                            if 0 < d < mpf("1e-40"):
                                dig = int(-log(d, 10))
                                if dig >= 30:
                                    print(f"  RATIO: 2F1({nstr(aa1,3)},{nstr(bb1,3)};{nstr(cc1,3)};-1)")
                                    print(f"       / 2F1({nstr(aa2,3)},{nstr(bb2,3)};{nstr(cc2,3)};-1)")
                                    print(f"       = {nstr(ratio,25)} [{dig}d]")
                        except:
                            pass

# Also check 1F1 (confluent hypergeometric / Kummer)
print("\nTrying 1F1 connections (Kummer functions):")
for a_num in range(1, 6):
    for c_num in range(1, 8):
        for z_frac in [-1, mpf(1)/2, 1, 2]:
            a = mpf(a_num)/2
            c = mpf(c_num)/2
            if c <= 0:
                continue
            try:
                val = hyp1f1(a, c, z_frac)
                d = fabs(val - V_target)
                if 0 < d < mpf("1e-40"):
                    dig = int(-log(d, 10))
                    if dig >= 30:
                        print(f"  1F1({nstr(a,3)};{nstr(c,3)};{z_frac}) = {nstr(val,25)} [{dig}d]")
            except:
                pass

print("\nDone - Iteration 2D.")
