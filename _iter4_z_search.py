"""Iteration 4: Comprehensive z-point search engine.

Strategy: For each slope s and offset f, test GCFs with:
  a_n = -alpha*n^2 + beta*n + gamma (quadratic)
  b_n = s*n + f (linear)
against an extended constant basis via PSLQ.

The known families have:
  pi-family:  a_n = -2n^2 + cn, b_n = 3n + f  (slope 3)
  ln2-family: a_n = -n^2,       b_n = 6n + 3   (slope 6)
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

print("="*75)
print("  ITERATION 4: z-POINT SEARCH ENGINE")
print("="*75)
print()

# Extended constant basis for PSLQ
PI = pi
LN2 = ln(2)
LN3 = ln(3)
PI_S3 = pi / sqrt(3)   # = pi*sqrt(3)/3
SQRT2 = sqrt(2)
SQRT3 = sqrt(3)
CAT = mp.catalan
ZETA3 = mp.zeta(3)
E = mp.e
LN_PHI = ln((1 + sqrt(5))/2)  # ln(golden ratio)

# PSLQ basis: check V against each constant individually, then pairs
single_targets = [
    ("pi",    PI),
    ("pi/s3", PI_S3),
    ("ln2",   LN2),
    ("ln3",   LN3),
    ("sqrt2", SQRT2),
    ("sqrt3", SQRT3),
    ("cat",   CAT),
    ("zeta3", ZETA3),
]

hits = []
t0 = time.time()

# ==== PART 1: a_n = -n^2, b_n = s*n + f  (pure square) ====
print("--- PART 1: a_n = -n^2, b_n = s*n+f ---")
print()

for s in range(2, 25):
    for f in range(-5, 15):
        try:
            V = gcf_bw(lambda n, _s=s, _f=f: -mpf(n)*n,
                       lambda n, _s=s, _f=f: mpf(_s)*n + _f, 300)
            if not mp.isfinite(V) or fabs(V) > 1e8 or fabs(V) < 1e-8:
                continue

            for name, const in single_targets:
                # Check aV + b + c*const = 0 (i.e. V = rational + rational*const)
                basis = [V, mpf(1), const]
                rel = mp.pslq(basis, maxcoeff=1000)
                if rel is not None:
                    check = sum(r*v for r, v in zip(rel, basis))
                    if fabs(check) < mpf("1e-50"):
                        dig = int(-log(fabs(check), 10)) if fabs(check) > 0 else 80
                        desc = "%d*V + %d + %d*%s = 0 [%dd]" % (rel[0], rel[1], rel[2], name, dig)
                        print("  s=%2d f=%2d: %s" % (s, f, desc))
                        hits.append(("P1", s, f, 0, 0, name, rel, dig))
                        break
        except:
            pass

print()
print("  Part 1 done in %.0fs, %d hits" % (time.time()-t0, len(hits)))
print()

# ==== PART 2: a_n = -alpha*n^2 + beta*n, b_n = s*n + f ====
print("--- PART 2: a_n = -alpha*n^2 + beta*n, b_n = s*n+f ---")
print("    (alpha in {1,2,3}, beta in {-5..5}, slope in {2..15}, f in {-3..8})")
print()

t1 = time.time()
p2_hits = 0

for alpha in [1, 2, 3]:
    for beta in range(-5, 6):
        if alpha == 2 and 3 <= beta <= 5:
            continue  # skip known pi-family (already discovered)
        for s in range(2, 16):
            for f in range(-3, 9):
                try:
                    V = gcf_bw(
                        lambda n, _a=alpha, _b=beta: -mpf(_a)*n*n + mpf(_b)*n,
                        lambda n, _s=s, _f=f: mpf(_s)*n + _f,
                        200)
                    if not mp.isfinite(V) or fabs(V) > 1e8 or fabs(V) < 1e-8:
                        continue

                    for name, const in single_targets:
                        basis = [V, mpf(1), const]
                        rel = mp.pslq(basis, maxcoeff=1000)
                        if rel is not None:
                            check = sum(r*v for r, v in zip(rel, basis))
                            if fabs(check) < mpf("1e-40"):
                                dig = int(-log(fabs(check), 10))
                                desc = "a=%d*n^2+%d*n, b=%d*n+%d -> %d*V+%d+%d*%s=0 [%dd]" % (
                                    -alpha, beta, s, f, rel[0], rel[1], rel[2], name, dig)
                                # Skip known pi-family (alpha=2, s=3)
                                if name == "pi" and alpha == 2 and s == 3:
                                    continue
                                # Skip known ln2 (alpha=1, beta=0, s=6, f=3)
                                if name == "ln2" and alpha == 1 and beta == 0 and s == 6 and f == 3:
                                    continue
                                print("  [HIT] %s" % desc)
                                hits.append(("P2", s, f, alpha, beta, name, rel, dig))
                                p2_hits += 1
                                break
                except:
                    pass

print()
print("  Part 2 done in %.0fs, %d new hits" % (time.time()-t1, p2_hits))
print()

# ==== PART 3: Higher-slope a_n = -n^2, b_n = s*n + f with MULTI-constant PSLQ ====
print("--- PART 3: Multi-constant PSLQ (slopes 8-20) ---")
print("    Basis: {V, 1, pi, ln2, ln3, pi/sqrt3, sqrt3}")
print()

t2 = time.time()
p3_hits = 0

for s in range(8, 21):
    for f in range(-3, 12):
        try:
            V = gcf_bw(lambda n, _s=s, _f=f: -mpf(n)*n,
                       lambda n, _s=s, _f=f: mpf(_s)*n + _f, 300)
            if not mp.isfinite(V) or fabs(V) > 1e8 or fabs(V) < 1e-8:
                continue

            # Multi-constant PSLQ
            basis = [V, mpf(1), PI, LN2, LN3, PI_S3, SQRT3]
            rel = mp.pslq(basis, maxcoeff=500)
            if rel is not None:
                check = sum(r*v for r, v in zip(rel, basis))
                if fabs(check) < mpf("1e-40"):
                    dig = int(-log(fabs(check), 10))
                    names = ["V", "1", "pi", "ln2", "ln3", "pi/s3", "s3"]
                    terms = []
                    for r, nm in zip(rel, names):
                        if r != 0:
                            terms.append("%d*%s" % (r, nm))
                    desc = " + ".join(terms) + " = 0 [%dd]" % dig
                    # Filter trivial (only V and 1)
                    if any(rel[i] != 0 for i in range(2, len(rel))):
                        print("  s=%2d f=%2d: %s" % (s, f, desc))
                        hits.append(("P3", s, f, 0, 0, "multi", rel, dig))
                        p3_hits += 1
        except:
            pass

print()
print("  Part 3 done in %.0fs, %d new hits" % (time.time()-t2, p3_hits))
print()

# ==== SUMMARY ====
print("="*75)
total_time = time.time() - t0
print("  TOTAL: %d hits in %.0fs" % (len(hits), total_time))
print("="*75)
print()

# Organize by constant
from collections import defaultdict
by_const = defaultdict(list)
for part, s, f, alpha, beta, name, rel, dig in hits:
    by_const[name].append((part, s, f, alpha, beta, rel, dig))

for name, entries in sorted(by_const.items()):
    print("  %s (%d entries):" % (name, len(entries)))
    for part, s, f, alpha, beta, rel, dig in entries:
        if alpha == 0:
            print("    %s: a=-n^2, b=%dn+%d, rel=%s [%dd]" % (part, s, f, rel, dig))
        else:
            print("    %s: a=-%dn^2+%dn, b=%dn+%d, rel=%s [%dd]" % (part, alpha, beta, s, f, rel, dig))
