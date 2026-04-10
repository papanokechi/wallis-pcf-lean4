"""
Verify ALL remaining untested non-pi hits from v2 search.
Focus on ln(3/2) and sqrt3 entries not covered by _iter4_verify.py
"""
from mpmath import mp, mpf, log, sqrt, fabs, pi, catalan, apery

def gcf_bw(a_fn, b_fn, depth, dps=120):
    mp.dps = dps + 20
    val = mpf(0)
    for n in range(depth, 0, -1):
        val = a_fn(n) / (b_fn(n) + val)
    return b_fn(0) + val

CONSTS = {
    'ln2': lambda: log(2),
    'ln3': lambda: log(3),
    'ln3/2': lambda: log(mpf(3)/2),
    'pi': lambda: pi,
    'pi/s3': lambda: pi/sqrt(3),
    'sqrt3': lambda: sqrt(3),
    'cat': lambda: catalan,
    'zeta3': lambda: apery,
}

def mobius_check(V, name, maxcoeff=500):
    """Check if a*V*K + b*V + c*K + d = 0 for small ints a,b,c,d"""
    mp.dps = 120
    K = CONSTS[name]()
    from mpmath import matrix, mnorm
    # Use PSLQ on [V*K, V, K, 1]
    vec = [V*K, V, K, mpf(1)]
    try:
        rel = mp.pslq(vec, maxcoeff=maxcoeff)
    except:
        return None
    if rel is None:
        return None
    a, b, c, d = rel
    # Check degeneracy: c*b == d*a means K cancels
    if c*b == d*a:
        return {'rel': rel, 'degenerate': True, 'V_rat': -mpf(d)/b if b != 0 else None}
    else:
        return {'rel': rel, 'degenerate': False}

# All entries from the v2 search output for non-pi families
# Format: (alpha, beta, slope, offset, expected_family)
# a_n = -alpha*n^2 + beta*n, b_n = slope*n + offset

ALL_CANDIDATES = [
    # === ln(3/2) family (14 total from v2 search) ===
    # Already tested: (-1,0,10,5), (-1,2,?), (-1,3,?)
    # Let me reconstruct from the search parameters
    # Part 1 had: a=-n^2, b=s*n+f, s in [2..24], f in [-3..8]
    # Part 2 had: a=-alpha*n^2+beta*n, b=s*n+f
    
    # ln(3/2) entries from Part 1 (a_n = -n^2):
    (1, 0, 10, 5, 'ln3/2'),   # already verified genuine
    
    # Let me test ALL slopes 2-30 for a_n = -n^2 against ln(3/2) membership
    # of the parametric family
]

print("=" * 78)
print("  EXTENDED VERIFICATION: Check all untested v2 entries")
print("=" * 78)

# Part A: Check which slopes in Part 2 (with beta != 0) gave genuine ln(3/2) hits
# From the v2 search, ln(3/2) had entries at slopes 4,5,7,10,11,15,20
# Most with beta != 0.

# Let me check ALL entries systematically by re-running Mobius PSLQ on every
# non-pi V from Part 2 that matched ln(3/2)

print("\n--- A: Checking parametric family predictions ---")
print("  Theorem: ln(k/(k-1)) = 2/GCF[-n^2, (2k-1)(2n+1)]")
print("  Equivalently: slope = 4k-2, offset = 2k-1")
print()

# For a_n = -n^2 + beta*n entries, check if they reduce to the parametric family
# after possible GCF equivalence transforms

# First, let me verify ALL Part 2 hits systematically
# Re-scan a subset: alpha in {1,2,3}, beta in {-5..5}, s in {2..20}, f in {-3..8}
# Focus on non-pi constants only

print("--- B: Systematic re-scan of Part 2 hits vs all constants ---")
print()

count_genuine = 0
count_ghost = 0
genuine_list = []

# Only scan the parameter ranges that produced hits
# From the v2 results:
# sqrt3 at slopes 3,4,10,12,14,20
# ln3/2 at slopes 4,5,7,10,11,15,20

test_params = []

# sqrt3 candidates from v2 (alpha, beta, slope, offset)
s3_candidates = [
    (1, -3, 4, 8),
    (1, -1, 4, 4),
    (1, 2, 4, 2),     # not tested
    (1, 2, 10, -1),   # not tested
    (1, 4, 12, -3),   # not tested
    (1, 3, 14, -3),   # not tested
    (2, -3, 20, 8),   # not tested
]

ln32_candidates = [
    (1, 0, 10, 5),    # tested, genuine
    (1, 2, 4, 5),     # not tested
    (1, 0, 4, -3),    # not tested
    (1, 3, 5, 3),     # not tested
    (1, 2, 7, 2),     # not tested
    (1, 5, 11, -3),   # not tested
    (2, -5, 15, 8),   # not tested
    (2, 1, 20, -1),   # not tested
    (2, -3, 11, 5),   # not tested
    (3, -1, 20, 8),   # not tested
]

print(f"{'label':>10}  {'a_n params':>20}  {'b_n':>10}  {'V':>18}  {'const':>6}  deg?  verdict")
print("-" * 95)

for label_prefix, candidates, const_name in [
    ('s3', s3_candidates, 'sqrt3'),
    ('l32', ln32_candidates, 'ln3/2'),
]:
    for i, (alpha, beta, s, f) in enumerate(candidates):
        mp.dps = 130
        a_fn = lambda n, a=alpha, b=beta: -a*mpf(n)**2 + b*mpf(n)
        b_fn = lambda n, s=s, f=f: s*mpf(n) + f
        
        V = gcf_bw(a_fn, b_fn, 400, dps=130)
        
        result = mobius_check(V, const_name)
        label = f"{label_prefix}_{i+1}"
        
        if result is None:
            print(f"{label:>10}  a={-alpha}n²+{beta:+d}n  b={s}n+{f}  {float(V):>18.10f}  {const_name:>6}  ---  NO PSLQ MATCH")
        elif result['degenerate']:
            Vr = result['V_rat']
            count_ghost += 1
            print(f"{label:>10}  a={-alpha}n²+{beta:+d}n  b={s}n+{f}  {float(V):>18.10f}  {const_name:>6}  YES  GHOST (V={float(Vr):.6f})")
        else:
            count_genuine += 1
            rel = result['rel']
            genuine_list.append((label, alpha, beta, s, f, const_name, rel))
            print(f"{label:>10}  a={-alpha}n²+{beta:+d}n  b={s}n+{f}  {float(V):>18.10f}  {const_name:>6}   NO  GENUINE: {rel}")

print()
print(f"Total: {count_genuine} genuine, {count_ghost} ghosts")
print()

if genuine_list:
    print("=" * 78)
    print("  ALL GENUINE NON-PI IDENTITIES (combined with earlier results)")
    print("=" * 78)
    for label, alpha, beta, s, f, const_name, rel in genuine_list:
        a, b, c, d = rel
        print(f"  {label}: GCF[-{alpha}n²+{beta}n, {s}n+{f}]")
        print(f"    Relation: {a}·V·{const_name} + {b}·V + {c}·{const_name} + {d} = 0")
        print(f"    => V = -({c}·{const_name} + {d})/({a}·{const_name} + {b})")
        print()
