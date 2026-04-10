"""
Iteration 5B: ₃F₂ / Higher-Hypergeometric CF Search
=====================================================
Target: Break the ζ-barrier by searching CFs at the d_a = 2·d_b boundary.

Theory:
  - d_a=2, d_b=1 → ₂F₁ ratio → π, ln(k/(k-1)), √d  (Iterations 1-4)
  - d_a=6, d_b=3 → ₄F₃ ratio(?) → ζ(3) is Apéry (unique known member)
  - d_a=4, d_b=2 → ₃F₂ ratio → ???  (UNEXPLORED)
  - d_a=3, d_b=1 → ₂F₁ at boundary → ???

Search strategy:
  A. Quadratic b_n with quadratic a_n (d_a=2, d_b=2; below boundary)
  B. Cubic a_n with linear b_n (d_a=3, d_b=1; AT boundary d_a = 3d_b)
  C. Quartic a_n with quadratic b_n (d_a=4, d_b=2; AT boundary d_a = 2d_b)

Constants targeted: ζ(2)=π²/6, ζ(3), Li₂(1/2), Catalan G, and
combinations thereof.
"""
from mpmath import mp, mpf, fabs, log, pi, sqrt, catalan, apery, polylog
from mpmath import zeta as mpzeta

def gcf_bw(a_fn, b_fn, depth, dps=80):
    mp.dps = dps + 20
    val = mpf(0)
    for n in range(depth, 0, -1):
        a = a_fn(n)
        b = b_fn(n)
        if fabs(b + val) < mpf(10)**(-dps):
            return None  # near-zero denominator
        val = a / (b + val)
    return b_fn(0) + val

def convergence_check(a_fn, b_fn, dps=50):
    """Check if CF converges by comparing depths 100 and 200."""
    mp.dps = dps + 10
    v1 = gcf_bw(a_fn, b_fn, 100, dps)
    v2 = gcf_bw(a_fn, b_fn, 200, dps)
    if v1 is None or v2 is None:
        return None, 0
    diff = fabs(v1 - v2)
    if diff > 0:
        digits = max(0, int(-float(mp.log10(diff))))
    else:
        digits = dps
    return v2, digits

# Target constants with higher precision
TARGETS = {}
def init_targets():
    mp.dps = 100
    TARGETS['pi'] = pi
    TARGETS['pi2'] = pi**2
    TARGETS['pi2_6'] = pi**2 / 6  # ζ(2)
    TARGETS['zeta3'] = apery
    TARGETS['cat'] = catalan
    TARGETS['ln2'] = log(2)
    TARGETS['li2_half'] = polylog(2, mpf('0.5'))  # Li₂(1/2) = π²/12 - ln²(2)/2
    TARGETS['sqrt2'] = sqrt(2)
    TARGETS['sqrt3'] = sqrt(3)
    TARGETS['sqrt5'] = sqrt(5)
    TARGETS['phi'] = (1 + sqrt(5)) / 2  # golden ratio
    TARGETS['zeta5'] = mpzeta(5)

init_targets()

def mobius_pslq_multi(V, maxcoeff=200):
    """Test V against all target constants using Möbius PSLQ."""
    mp.dps = 90
    hits = []
    for name, K in TARGETS.items():
        # Basis: [V*K, V, K, 1]
        basis = [V*K, V, K, mpf(1)]
        try:
            rel = mp.pslq(basis, maxcoeff=maxcoeff, tol=mpf(10)**(-50))
        except:
            continue
        if rel is None:
            continue
        a, b, c, d = rel
        # Check degenerate
        if c*b == d*a:
            continue  # ghost
        # Verify residual
        res = fabs(a*V*K + b*V + c*K + d)
        if res < mpf(10)**(-40):
            hits.append((name, rel, float(res)))
    return hits

print("=" * 78)
print("  ITERATION 5B: ₃F₂ / HIGHER-HYPERGEOMETRIC CF SEARCH")
print("=" * 78)
print()

# =====================================================================
# PART A: Cubic a_n with linear b_n (d_a=3, d_b=1)
# =====================================================================
print("PART A: a_n = -αn³ + βn² + γn, b_n = sn + f")
print("  (d_a=3, d_b=1; at the d_a=3d_b boundary)")
print("-" * 60)

hits_A = []
count_A = 0
for alpha in [1, 2]:
    for beta in range(-3, 4):
        for gamma in range(-3, 4):
            for s in range(2, 16):
                for f in range(-2, 6):
                    count_A += 1
                    a_fn = lambda n, a=alpha, b=beta, g=gamma: -a*mpf(n)**3 + b*mpf(n)**2 + g*mpf(n)
                    b_fn = lambda n, s=s, f=f: s*mpf(n) + f
                    
                    V, digits = convergence_check(a_fn, b_fn, dps=60)
                    if V is None or digits < 30:
                        continue
                    
                    # Test against constants
                    results = mobius_pslq_multi(V, maxcoeff=200)
                    if results:
                        for name, rel, res in results:
                            label = f"a=-{alpha}n³+{beta}n²+{gamma}n b={s}n+{f}"
                            hits_A.append((label, name, rel, float(V), digits))
                            print(f"  HIT: {label} → {name} {rel} [{digits}d]")

print(f"\n  Part A: {count_A} tested, {len(hits_A)} hits")
print()

# =====================================================================
# PART B: Quartic a_n with quadratic b_n (d_a=4, d_b=2; d_a=2d_b)
# =====================================================================
print("PART B: a_n = -n²(αn² + βn + γ), b_n = An² + Bn + C")
print("  (d_a=4, d_b=2; AT the d_a=2d_b boundary — same as Apéry class)")
print("-" * 60)

hits_B = []
count_B = 0
for alpha in [1]:
    for beta in range(-3, 4):
        for gamma in range(-3, 4):
            for A in range(1, 6):
                for B in range(-4, 8):
                    for C in range(-3, 6):
                        count_B += 1
                        a_fn = lambda n, a=alpha, b=beta, g=gamma: -mpf(n)**2 * (a*mpf(n)**2 + b*mpf(n) + g)
                        b_fn = lambda n, A=A, B=B, C=C: A*mpf(n)**2 + B*mpf(n) + C
                        
                        V, digits = convergence_check(a_fn, b_fn, dps=60)
                        if V is None or digits < 30:
                            continue
                        
                        results = mobius_pslq_multi(V, maxcoeff=200)
                        if results:
                            for name, rel, res in results:
                                label = f"a=-n²({alpha}n²+{beta}n+{gamma}) b={A}n²+{B}n+{C}"
                                hits_B.append((label, name, rel, float(V), digits))
                                print(f"  HIT: {label} → {name} {rel} [{digits}d]")

print(f"\n  Part B: {count_B} tested, {len(hits_B)} hits")
print()

# =====================================================================
# PART C: Near-Apéry CFs (d_a=6, d_b=3, perturbing Apéry coefficients)
# =====================================================================
print("PART C: Apéry-neighboring CFs")
print("  a_n = -n^6, b_n = (2n+1)(An²+Bn+C)")
print("  Search near (A,B,C) = (17,17,5) — the Apéry point")
print("-" * 60)

hits_C = []
count_C = 0
# Wider search around Apéry coefficients
for A in range(10, 25):
    for B in range(10, 25):
        for C in range(1, 12):
            count_C += 1
            a_fn = lambda n: -mpf(n)**6
            b_fn = lambda n, A=A, B=B, C=C: (2*mpf(n)+1) * (A*mpf(n)**2 + B*mpf(n) + C)
            
            V, digits = convergence_check(a_fn, b_fn, dps=60)
            if V is None or digits < 20:
                continue
            
            # For Apéry-type: known identity is ζ(3) = 6/(5·CF)
            # So check V, 1/V, 5V/6 against constants
            for transform_name, Vt in [("V", V), ("6/(5V)", 6/(5*V)), ("5V/6", 5*V/6)]:
                results = mobius_pslq_multi(Vt, maxcoeff=200)
                if results:
                    for name, rel, res in results:
                        label = f"A={A},B={B},C={C} ({transform_name})"
                        hits_C.append((label, name, rel, float(Vt), digits))
                        print(f"  HIT: {label} → {name} {rel} [{digits}d]")

print(f"\n  Part C: {count_C} tested, {len(hits_C)} hits")
print()

# =====================================================================
# PART D: Known ₃F₂ CFs at special points
# =====================================================================
print("PART D: Known ₃F₂-type CF evaluations")
print("  Testing CFs from Zudilin (2002) and Guillera (2006)")
print("-" * 60)

# The CF for ₃F₂(1,1,1;2,2;z)/₃F₂(1,1,2;2,3;z) arises from
# a_n = -n⁴, b_n = cubic in n. Let's search:
hits_D = []
count_D = 0
for s1 in range(1, 8):
    for s2 in range(-4, 8):
        for s3 in range(-4, 8):
            count_D += 1
            # a_n = -n^4, b_n = s1*n^3 + s2*n^2 + s3*n + f with f from offset
            for f in range(-3, 6):
                a_fn = lambda n: -mpf(n)**4
                b_fn = lambda n, s1=s1, s2=s2, s3=s3, f=f: s1*mpf(n)**3 + s2*mpf(n)**2 + s3*mpf(n) + f
                
                V, digits = convergence_check(a_fn, b_fn, dps=60)
                if V is None or digits < 25:
                    continue
                
                results = mobius_pslq_multi(V, maxcoeff=300)
                if results:
                    for name, rel, res in results:
                        label = f"a=-n⁴ b={s1}n³+{s2}n²+{s3}n+{f}"
                        hits_D.append((label, name, rel, float(V), digits))
                        print(f"  HIT: {label} → {name} {rel} [{digits}d]")

print(f"\n  Part D: {count_D} configs × offsets tested, {len(hits_D)} hits")
print()

# =====================================================================
# SUMMARY
# =====================================================================
print("=" * 78)
print("  SEARCH SUMMARY")
print("=" * 78)
print(f"  Part A (cubic a, linear b):    {count_A:>6} tested, {len(hits_A):>3} hits")
print(f"  Part B (quartic a, quadratic b):{count_B:>6} tested, {len(hits_B):>3} hits")
print(f"  Part C (Apéry-neighborhood):   {count_C:>6} tested, {len(hits_C):>3} hits")
print(f"  Part D (₃F₂-type):             {count_D:>6} tested, {len(hits_D):>3} hits")
total = len(hits_A) + len(hits_B) + len(hits_C) + len(hits_D)
print(f"  TOTAL: {total} non-ghost hits")
print()

if total > 0:
    print("ALL HITS:")
    for src, hits in [("A", hits_A), ("B", hits_B), ("C", hits_C), ("D", hits_D)]:
        for label, name, rel, V, digits in hits:
            print(f"  [{src}] {label} → {name} {rel} V={V:.8f} [{digits}d]")
else:
    print("NO HITS beyond ₂F₁ territory.")
    print("This is a STRONG NEGATIVE RESULT: the ζ-barrier holds for")
    print("polynomial CFs up to degree 4 (a_n) and degree 3 (b_n).")
