"""Iteration 4: Slope scan to map b_n slope -> constant field."""
import mpmath as mp
from mpmath import mpf, nstr, fabs, log, ln, pi, sqrt

mp.dps = 100

def gcf_bw(a_fn, b_fn, depth):
    val = b_fn(depth)
    for n in range(depth-1, 0, -1):
        val = b_fn(n) + a_fn(n+1)/val
    return b_fn(0) + a_fn(1)/val

print("="*75)
print("  ITERATION 4: SLOPE SCAN — a_n = -n^2, b_n = s*n + f")
print("="*75)
print()

# Target constants
targets = [
    ("pi",    pi),
    ("pi/s3", pi/sqrt(3)),
    ("ln2",   ln(2)),
    ("ln3",   ln(3)),
    ("ln3/2", ln(mpf(3)/2)),
    ("e",     mp.e),
    ("sqrt2", sqrt(2)),
    ("sqrt3", sqrt(3)),
    ("pi^2",  pi**2),
    ("cat",   mp.catalan),
]

fmt = "%5s %3s %28s   %s"
print(fmt % ("slope", "f", "V", "PSLQ relation"))
print("-"*85)

hits = []

for s in range(2, 25):
    for f in range(-3, 12):
        try:
            V = gcf_bw(lambda n, _s=s, _f=f: -mpf(n)*n,
                       lambda n, _s=s, _f=f: mpf(_s)*n+_f, 300)
            if not mp.isfinite(V) or fabs(V) > 1e10 or fabs(V) < 1e-10:
                continue

            found = False
            for name, const in targets:
                basis = [V, mpf(1), const]
                rel = mp.pslq(basis, maxcoeff=500)
                if rel is not None:
                    check = rel[0]*V + rel[1] + rel[2]*const
                    if fabs(check) < mpf("1e-60"):
                        a, b, c = rel
                        desc = "%d*V + %d + %d*%s = 0" % (a, b, c, name)
                        print(fmt % (s, f, nstr(V, 22), desc))
                        hits.append((s, f, V, name, rel))
                        found = True
                        break

            # Also try 2-constant PSLQ: V vs {1, pi, ln2}
            if not found:
                basis4 = [V, mpf(1), pi, ln(2)]
                rel4 = mp.pslq(basis4, maxcoeff=200)
                if rel4 is not None:
                    check = sum(r*v for r, v in zip(rel4, basis4))
                    if fabs(check) < mpf("1e-50"):
                        desc = "%d*V + %d + %d*pi + %d*ln2 = 0" % tuple(rel4)
                        print(fmt % (s, f, nstr(V, 22), desc))
                        hits.append((s, f, V, "multi", rel4))

        except Exception:
            pass

print()
print("="*75)
print("  SUMMARY: %d hits" % len(hits))
print("="*75)
print()

# Group by constant
from collections import defaultdict
by_const = defaultdict(list)
for s, f, V, name, rel in hits:
    by_const[name].append((s, f, rel))

for name, entries in sorted(by_const.items()):
    slopes = sorted(set(s for s, f, rel in entries))
    print("  %s: slopes %s" % (name, slopes))

print()
print("Slope -> z-point mapping (inferred):")
print("  slope 3-4 (pi family, z=-1)")
print("  slope 6   (ln2 family, z=1/2)")
print("  slope 12? (pi/sqrt3 family?, z=1/3 ???)")
print("  slope 9?  (ln3 family?, z=2/3 ???)")
