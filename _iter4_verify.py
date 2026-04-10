"""Iteration 4: Verify all non-pi hits from _iter4_z_search_v2.py.

Ghost detection: A Mobius relation V = (cK+d)/(aK+b) is a GHOST if:
  c/a = d/b  (the constant K cancels and V = c/a = d/b is just rational)

For genuine hits, verify:
  1. The check value is < 10^{-60}
  2. Digits scale with precision (genuine identity)
  3. The relation is non-degenerate (K does NOT cancel)
"""
import mpmath as mp
from mpmath import mpf, nstr, fabs, log, ln, pi, sqrt
import time

mp.dps = 120  # higher than search to verify scaling

def gcf_bw(a_fn, b_fn, depth):
    val = b_fn(depth)
    for n in range(depth-1, 0, -1):
        val = b_fn(n) + a_fn(n+1)/val
    return b_fn(0) + a_fn(1)/val

def is_degenerate(rel_4):
    """Check if Mobius relation a*V*K + b*V + c*K + d = 0 is degenerate.
    Degenerate means c/a = d/b (K cancels, V is rational)."""
    a, b, c, d = rel_4
    if a == 0 and c == 0:
        return True  # V = -d/b, K absent
    if b == 0 and d == 0:
        return True  # V*K = 0 or V = 0
    if a != 0 and c != 0 and b != 0 and d != 0:
        # Check c/a == d/b  (i.e. c*b == d*a)
        if c * b == d * a:
            return True
    return False


print("="*75)
print("  ITERATION 4: VERIFICATION OF NON-PI HITS")
print("="*75)
print()

# All non-pi hits from the search
candidates = [
    # (name, alpha, beta, slope, f, K_name)
    # Catalan hits
    ("cat1", 1, 4, 6, -3, "cat"),
    ("cat2", 2, -5, 3, 3, "cat"),
    ("cat3", 2, -1, 3, -1, "cat"),
    ("cat4", 2, 4, 18, 1, "cat"),
    ("cat5", 3, -5, 4, 0, "cat"),
    # zeta3 hits
    ("z3_1", 1, 4, 3, -1, "zeta3"),
    ("z3_2", 1, 5, 3, 0, "zeta3"),
    ("z3_3", 2, -5, 3, 4, "zeta3"),
    ("z3_4", 2, 1, 3, -2, "zeta3"),
    # ln3 hits
    ("ln3_1", 1, 3, 6, 0, "ln3"),
    ("ln3_2", 1, 4, 2, 0, "ln3"),
    ("ln3_3", 1, 5, 2, 0, "ln3"),
    ("ln3_4", 3, -5, 4, 2, "ln3"),
    ("ln3_5", 3, -4, 4, 1, "ln3"),
    # ln(3/2) hits
    ("ln32_1", 1, 0, 10, 5, "ln3/2"),  # claimed V*ln(3/2) = 2
    ("ln32_2", 1, 2, 11, 2, "ln3/2"),
    ("ln32_3", 1, 3, 5, -1, "ln3/2"),
    # pi/sqrt3 hit
    ("pis3_1", 1, 2, 17, 5, "pi/s3"),
    # sqrt3 hits
    ("s3_1", 1, -3, 4, 8, "sqrt3"),
    ("s3_2", 1, -1, 4, 4, "sqrt3"),
    ("s3_3", 1, 2, 3, 4, "sqrt3"),
    ("s3_4", 1, 2, 12, 2, "sqrt3"),
    # ln2 (non-known)
    ("ln2_ext1", 1, 2, 13, 2, "ln2"),
    ("ln2_ext2", 1, 3, 8, 1, "ln2"),
]

# Constant values
consts = {
    "cat": mp.catalan,
    "zeta3": mp.zeta(3),
    "ln3": ln(3),
    "ln3/2": ln(mpf(3)/2),
    "pi/s3": pi/sqrt(3),
    "sqrt3": sqrt(3),
    "ln2": ln(2),
}

print("%-8s  %6s  %20s  %8s  %8s  %s" % ("Label", "a_n", "V", "check", "degenerate?", "verdict"))
print("-" * 95)

genuine_hits = []

for label, alpha, beta, s, f, kname in candidates:
    K = consts[kname]

    # Compute GCF at dps=120
    V = gcf_bw(
        lambda n, _a=alpha, _b=beta: -mpf(_a)*n*n + mpf(_b)*n,
        lambda n, _s=s, _f=f: mpf(_s)*n + _f,
        400)

    if not mp.isfinite(V):
        print("%-8s  -%d*n^2+%dn  DIVERGENT" % (label, alpha, beta))
        continue

    # Run PSLQ Mobius: {V*K, V, K, 1}
    basis = [V*K, V, K, mpf(1)]
    rel = mp.pslq(basis, maxcoeff=1000)

    if rel is None:
        # Also try simple: V*K = rational?
        rel2 = mp.pslq([V*K, mpf(1)], maxcoeff=1000)
        if rel2 is not None:
            check = rel2[0]*V*K + rel2[1]
            dig = int(-log(fabs(check), 10)) if fabs(check) > 0 else 120
            # V*K = -rel2[1]/rel2[0], this is NOT degenerate (involves K)
            a_str = "-%d*n^2+%d*n" % (alpha, beta)
            print("%-8s  %6s  %20s  %4dd  %8s  V*%s = %d/%d" % (
                label, a_str, nstr(V, 15), dig, "NO", kname, -rel2[1], rel2[0]))
            genuine_hits.append((label, alpha, beta, s, f, kname, "V*K=rat", dig))
        else:
            print("%-8s  PSLQ failed" % label)
        continue

    check = sum(r*v for r, v in zip(rel, basis))
    dig = int(-log(fabs(check), 10)) if fabs(check) > 0 else 120

    degen = is_degenerate(rel)
    a_str = "-%d*n^2+%d*n" % (alpha, beta)

    if degen:
        # V is rational
        a, b, c, d = rel
        if b != 0:
            Vrat = mpf(-d) / b
        elif a != 0:
            Vrat = mpf(-c) / a
        else:
            Vrat = mpf(0)
        verdict = "GHOST (V=%s)" % nstr(Vrat, 8)
    else:
        a, b, c, d = rel
        verdict = "GENUINE: %d*V*%s + %d*V + %d*%s + %d = 0" % (a, kname, b, c, kname, d)
        genuine_hits.append((label, alpha, beta, s, f, kname, rel, dig))

    print("%-8s  %6s  %20s  %4dd  %8s  %s" % (
        label, a_str, nstr(V, 15), dig, "YES" if degen else "NO", verdict))

print()
print("="*75)
print("  GENUINE (non-degenerate) hits: %d" % len(genuine_hits))
print("="*75)
print()

for label, alpha, beta, s, f, kname, rel_or_type, dig in genuine_hits:
    print("  %s: a=-%d*n^2+%d*n, b=%d*n+%d -> %s (%s) [%dd]" % (
        label, alpha, beta, s, f, kname, rel_or_type, dig))

# For each genuine hit, verify precision scaling
print()
print("--- PRECISION SCALING CHECK (genuine hits) ---")
print()

for label, alpha, beta, s, f, kname, rel_or_type, dig in genuine_hits:
    K = consts[kname]
    print("  %s:" % label)
    for dps in [40, 80, 120]:
        mp.dps = dps + 20
        K_local = consts[kname]  # recompute at higher dps
        # Recompute constants at current precision
        if kname == "cat": K_local = mp.catalan
        elif kname == "zeta3": K_local = mp.zeta(3)
        elif kname == "ln3": K_local = ln(3)
        elif kname == "ln3/2": K_local = ln(mpf(3)/2)
        elif kname == "pi/s3": K_local = pi/sqrt(3)
        elif kname == "sqrt3": K_local = sqrt(3)
        elif kname == "ln2": K_local = ln(2)

        V_local = gcf_bw(
            lambda n, _a=alpha, _b=beta: -mpf(_a)*n*n + mpf(_b)*n,
            lambda n, _s=s, _f=f: mpf(_s)*n + _f,
            max(200, dps*2))

        if isinstance(rel_or_type, str) and "V*K" in rel_or_type:
            # V*K = rational check
            prod = V_local * K_local
            # Find nearest rational
            rel_check = mp.pslq([prod, mpf(1)], maxcoeff=1000)
            if rel_check:
                resid = fabs(rel_check[0]*prod + rel_check[1])
                d_dig = int(-log(resid, 10)) if resid > 0 else dps
                print("    dps=%3d: V*%s residual -> %d digits" % (dps, kname, d_dig))
            else:
                print("    dps=%3d: PSLQ failed" % dps)
        else:
            # Mobius check
            rel = rel_or_type
            basis = [V_local*K_local, V_local, K_local, mpf(1)]
            resid = fabs(sum(r*v for r, v in zip(rel, basis)))
            d_dig = int(-log(resid, 10)) if resid > 0 else dps
            print("    dps=%3d: Mobius residual -> %d digits" % (dps, d_dig))
    mp.dps = 120  # reset
    print()
