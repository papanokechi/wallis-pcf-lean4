"""Iteration 4 v2: Fixed PSLQ methodology.

KEY INSIGHT: V = 2/ln(2) means V*ln(2) = 2 (integer relation).
But PSLQ with basis {V, 1, ln2} looks for aV + b + c*ln2 = 0,
which CANNOT find V = 2/ln(2) since that's a Mobius relation, not linear.

Fix: For each constant K, also check:
  - V*K against rationals  (catches V = p/q * 1/K)
  - 1/V against {1, K}     (catches V = 1/(a + b*K))
  - Full Mobius: {V*K, V, K, 1}  (catches V = (a + bK)/(c + dK))
"""
import mpmath as mp
from mpmath import mpf, nstr, fabs, log, ln, pi, sqrt
import time

mp.dps = 80

def gcf_bw(a_fn, b_fn, depth):
    val = b_fn(depth)
    for n in range(depth-1, 0, -1):
        val = b_fn(n) + a_fn(n+1)/val
    return b_fn(0) + a_fn(1)/val

def check_mobius(V, name, K, min_digits=40):
    """Check if V is a Mobius transform of K: V = (a+bK)/(c+dK) for small int a,b,c,d.
    This is equivalent to finding an integer relation among {V*K, V, K, 1}."""
    hits = []

    # Method 1: V*K = rational?
    VK = V * K
    rel = mp.pslq([VK, mpf(1)], maxcoeff=1000)
    if rel is not None:
        check = rel[0]*VK + rel[1]
        if fabs(check) < mpf("1e-40"):
            dig = int(-log(fabs(check), 10)) if fabs(check) > 0 else 80
            if dig >= min_digits:
                # V*K = -rel[1]/rel[0], so V = -rel[1]/(rel[0]*K)
                hits.append(("V*%s=%d/%d" % (name, -rel[1], rel[0]), dig))

    # Method 2: Full Mobius basis {V*K, V, K, 1}
    basis = [V*K, V, K, mpf(1)]
    rel = mp.pslq(basis, maxcoeff=500)
    if rel is not None:
        check = sum(r*v for r, v in zip(rel, basis))
        if fabs(check) < mpf("1e-40"):
            dig = int(-log(fabs(check), 10)) if fabs(check) > 0 else 80
            if dig >= min_digits:
                a, b, c, d = rel
                # a*V*K + b*V + c*K + d = 0 => V = -(c*K + d)/(a*K + b)
                hits.append(("V=(-%d*%s+%d)/(%d*%s+%d)" % (c, name, -d, a, name, b), dig))

    # Method 3: Linear: V = a + b*K?
    rel = mp.pslq([V, mpf(1), K], maxcoeff=1000)
    if rel is not None:
        check = rel[0]*V + rel[1] + rel[2]*K
        if fabs(check) < mpf("1e-40"):
            dig = int(-log(fabs(check), 10)) if fabs(check) > 0 else 80
            if dig >= min_digits:
                hits.append(("%d*V+%d+%d*%s=0" % (rel[0], rel[1], rel[2], name), dig))

    return hits


print("="*75)
print("  ITERATION 4 v2: FIXED z-POINT SEARCH (Mobius PSLQ)")
print("="*75)
print()

# Target constants
target_consts = [
    ("pi",    pi),
    ("pi/s3", pi/sqrt(3)),
    ("ln2",   ln(2)),
    ("ln3",   ln(3)),
    ("ln3/2", ln(mpf(3)/2)),
    ("sqrt3", sqrt(3)),
    ("cat",   mp.catalan),
    ("zeta3", mp.zeta(3)),
]

all_hits = []
t0 = time.time()

# ==== PART 1: a_n = -n^2, b_n = s*n + f ====
print("--- PART 1: a_n = -n^2, b_n = s*n+f, slopes 2-24 ---")
print()

for s in range(2, 25):
    for f in range(-5, 15):
        try:
            V = gcf_bw(lambda n, _s=s, _f=f: -mpf(n)*n,
                       lambda n, _s=s, _f=f: mpf(_s)*n + _f, 300)
            if not mp.isfinite(V) or fabs(V) > 1e8 or fabs(V) < 1e-8:
                continue

            for name, K in target_consts:
                mobius_hits = check_mobius(V, name, K)
                for desc, dig in mobius_hits:
                    label = "  s=%2d f=%2d: %s [%dd]" % (s, f, desc, dig)
                    print(label)
                    all_hits.append(("P1", s, f, 0, 0, name, desc, dig))
                    break  # one match per (s,f) is enough
                if mobius_hits:
                    break
        except:
            pass

p1_time = time.time() - t0
print()
print("  Part 1: %d hits in %.0fs" % (sum(1 for h in all_hits if h[0]=="P1"), p1_time))
print()

# ==== PART 2: a_n = -alpha*n^2 + beta*n, slopes 2-20 ====
print("--- PART 2: a_n = -alpha*n^2 + beta*n, b_n = s*n+f ---")
print("    alpha={1,2,3}, beta={-5..5}, s={2..20}, f={-3..8}")
print()

t1 = time.time()
p2_count = 0

for alpha in [1, 2, 3]:
    for beta in range(-5, 6):
        for s in range(2, 21):
            for f in range(-3, 9):
                try:
                    V = gcf_bw(
                        lambda n, _a=alpha, _b=beta: -mpf(_a)*n*n + mpf(_b)*n,
                        lambda n, _s=s, _f=f: mpf(_s)*n + _f,
                        200)
                    if not mp.isfinite(V) or fabs(V) > 1e8 or fabs(V) < 1e-8:
                        continue

                    for name, K in target_consts:
                        mobius_hits = check_mobius(V, name, K)
                        for desc, dig in mobius_hits:
                            # Skip known families
                            if name == "pi" and alpha == 2 and s == 3:
                                continue
                            if name == "ln2" and alpha == 1 and beta == 0 and s == 6:
                                continue
                            label = "  a=-%d*n^2+%d*n b=%d*n+%d: %s (%s) [%dd]" % (
                                alpha, beta, s, f, desc, name, dig)
                            print(label)
                            all_hits.append(("P2", s, f, alpha, beta, name, desc, dig))
                            p2_count += 1
                            break
                        if mobius_hits:
                            break
                except:
                    pass

print()
print("  Part 2: %d NEW hits in %.0fs" % (p2_count, time.time()-t1))
print()

# ==== PART 3: Wider slope scan with multi-constant Mobius ====
print("--- PART 3: Extended slopes 15-30 with a_n=-n^2 ---")
print()

t2 = time.time()
p3_count = 0

for s in range(15, 31):
    for f in range(-3, 15):
        try:
            V = gcf_bw(lambda n, _s=s, _f=f: -mpf(n)*n,
                       lambda n, _s=s, _f=f: mpf(_s)*n + _f, 300)
            if not mp.isfinite(V) or fabs(V) > 1e8 or fabs(V) < 1e-8:
                continue

            for name, K in target_consts:
                mobius_hits = check_mobius(V, name, K, min_digits=30)
                for desc, dig in mobius_hits:
                    label = "  s=%2d f=%2d: %s (%s) [%dd]" % (s, f, desc, name, dig)
                    print(label)
                    all_hits.append(("P3", s, f, 0, 0, name, desc, dig))
                    p3_count += 1
                    break
                if mobius_hits:
                    break
        except:
            pass

print()
print("  Part 3: %d hits in %.0fs" % (p3_count, time.time()-t2))
print()

# ==== VERIFICATION: Can we see our known ln(2) identity? ====
print("--- SANITY CHECK: known ln(2) identity ---")
V_ln2 = gcf_bw(lambda n: -mpf(n)*n, lambda n: mpf(6)*n+3, 300)
print("  V(s=6,f=3) = %s" % nstr(V_ln2, 30))
ln2_hits = check_mobius(V_ln2, "ln2", ln(2))
for desc, dig in ln2_hits:
    print("  MATCH: %s [%dd]" % (desc, dig))
print()

# ==== GRAND SUMMARY ====
total = time.time() - t0
print("="*75)
print("  TOTAL: %d hits in %.0fs" % (len(all_hits), total))
print("="*75)
print()

from collections import defaultdict
by_const = defaultdict(list)
for part, s, f, alpha, beta, name, desc, dig in all_hits:
    by_const[name].append((part, s, f, alpha, beta, desc, dig))

if by_const:
    for name, entries in sorted(by_const.items()):
        slopes = sorted(set(s for _, s, f, a, b, d, dg in entries))
        print("  %s: %d entries, slopes %s" % (name, len(entries), slopes))
        for part, s, f, alpha, beta, desc, dig in entries[:5]:
            if alpha == 0:
                print("    %s s=%d f=%d: %s [%dd]" % (part, s, f, desc, dig))
            else:
                print("    %s a=-%dn^2+%dn b=%dn+%d: %s [%dd]" % (part, alpha, beta, s, f, desc, dig))
else:
    print("  No new constant families found beyond known pi and ln(2).")
    print()
    print("  This is a SIGNIFICANT NEGATIVE RESULT:")
    print("  The z-point stratification does NOT extend to z=1/3 or z=2/3")
    print("  via simple polynomial coefficient GCFs.")
