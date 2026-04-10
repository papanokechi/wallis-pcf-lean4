"""
Iteration 3 — Fast focused searches (Parts 3-4 only)
Zudilin-type + Catalan-targeted
"""
from mpmath import mp, mpf, nstr, fabs, log, pi, catalan, zeta
from mpmath import gamma as mpgamma, pslq, log as mplog
import time, sys

mp.dps = 60
Z3 = zeta(3); Cat = catalan; G13 = mpgamma(mpf(1)/3); G14 = mpgamma(mpf(1)/4)
Ln2 = mplog(2)

targets_aug = {}
for name, val in [("Z3", Z3), ("Cat", Cat), ("G13", G13), ("G14", G14),
                  ("ln2", Ln2), ("pi", pi), ("pi2/6", pi**2/6)]:
    targets_aug[name] = val
    for k in [2,3,4,5,6]:
        targets_aug["%d*%s" % (k,name)] = k*val
        targets_aug["%s/%d" % (name,k)] = val/k

def quick_match(V, threshold=12):
    hits = []
    for name, tgt in targets_aug.items():
        d = fabs(V - tgt)
        if d > 0 and d < mpf("1e-10"):
            dig = int(-log(d, 10))
            if dig >= threshold:
                hits.append((name, dig))
    return hits

all_hits = []

# ================================================================
# PART A: Zudilin-type: a_n = -n^2*(n+r)^2, b_n = An^2+Bn+C
# ================================================================
print("--- Zudilin-type: a=-n^2*(n+r)^2, b=An^2+Bn+C ---")
sys.stdout.flush()
t0 = time.time()
zh = 0
for r in range(1, 5):
    for A in range(1, 20):
        for B in range(-15, 16):
            for C in range(1, 15):
                try:
                    val = mpf(A*200**2 + B*200 + C)
                    if fabs(val) < 1: continue
                    for n in range(199, 0, -1):
                        an1 = -((n+1)**2) * ((n+1+r)**2)
                        val = (A*n**2 + B*n + C) + an1/val
                    a1_val = -(1) * ((1+r)**2)
                    V = C + a1_val/val
                except: continue
                if fabs(V) > 1e15 or fabs(V) < 1e-15: continue
                for xn, xv in [("V", V), ("6/V", 6/V), ("1/V", 1/V),
                                ("2/V", 2/V), ("3/V", 3/V)]:
                    mh = quick_match(xv)
                    for name, dig in mh:
                        if dig >= 15:
                            print("  HIT [r=%d, A=%d,B=%d,C=%d]: %s=%s [%dd]" % (
                                r, A, B, C, xn, name, dig))
                            all_hits.append({"search": "Zudilin", "r": r,
                                "b": [A,B,C], "xform": xn, "target": name, "digits": dig})
                            zh += 1; sys.stdout.flush()
print("  Zudilin: %d hits (%.0fs)" % (zh, time.time()-t0))
print(); sys.stdout.flush()

# ================================================================
# PART B: Catalan-targeted type 1: a=-(2n+alpha)^2, b=An+B
# ================================================================
print("--- Catalan type 1: a=-(2n+alpha)^2, b=An+B ---")
sys.stdout.flush()
t0 = time.time()
ch1 = 0
for alpha in range(-3, 4):
    for A in range(1, 15):
        for B in range(-10, 11):
            try:
                val = mpf(A*300 + B)
                if fabs(val) < 1: continue
                for n in range(299, 0, -1):
                    an1 = -((2*(n+1) + alpha)**2)
                    val = (A*n + B) + an1/val
                a1_val = -((2 + alpha)**2)
                if a1_val == 0: continue
                V = B + a1_val/val
            except: continue
            if fabs(V) > 1e12 or fabs(V) < 1e-12: continue
            for xn, xv in [("V", V), ("1/V", 1/V), ("4/V", 4/V), ("2/V", 2/V)]:
                mh = quick_match(xv)
                for name, dig in mh:
                    if dig >= 12:
                        print("  HIT [alpha=%d, b=%dn+%d]: %s=%s [%dd]" % (
                            alpha, A, B, xn, name, dig))
                        all_hits.append({"search": "Cat1", "alpha": alpha,
                            "A": A, "B": B, "xform": xn, "target": name, "digits": dig})
                        ch1 += 1; sys.stdout.flush()
print("  Cat type 1: %d hits (%.0fs)" % (ch1, time.time()-t0))
print(); sys.stdout.flush()

# ================================================================
# PART C: Catalan type 2: a=-n^2*(2n+alpha)^2, b=An^2+Bn+C
# ================================================================
print("--- Catalan type 2: a=-n^2*(2n+alpha)^2, b=An^2+Bn+C ---")
sys.stdout.flush()
t0 = time.time()
ch2 = 0
for alpha in range(-2, 3):
    for A in range(1, 15):
        for B in range(-10, 11):
            for C in range(1, 10):
                try:
                    val = mpf(A*200**2 + B*200 + C)
                    if fabs(val) < 1: continue
                    for n in range(199, 0, -1):
                        an1 = -((n+1)**2) * ((2*(n+1)+alpha)**2)
                        val = (A*n**2 + B*n + C) + an1/val
                    a1_val = -(1) * ((2+alpha)**2)
                    if a1_val == 0: continue
                    V = C + a1_val/val
                except: continue
                if fabs(V) > 1e15 or fabs(V) < 1e-15: continue
                for xn, xv in [("V", V), ("1/V", 1/V), ("4/V", 4/V),
                                ("6/V", 6/V), ("2/V", 2/V)]:
                    mh = quick_match(xv)
                    for name, dig in mh:
                        if dig >= 12:
                            print("  HIT [a=-n^2*(2n+%d)^2, b=%dn2+%dn+%d]: %s=%s [%dd]" % (
                                alpha, A, B, C, xn, name, dig))
                            all_hits.append({"search": "Cat2", "alpha": alpha,
                                "b": [A,B,C], "xform": xn, "target": name, "digits": dig})
                            ch2 += 1; sys.stdout.flush()
print("  Cat type 2: %d hits (%.0fs)" % (ch2, time.time()-t0))
print(); sys.stdout.flush()

# ================================================================
# PART D: Broader -n^p search but with b_n = QUADRATIC (faster than cubic)
# a_n = -n^p (p=2,3,4), b_n = An^2+Bn+C
# ================================================================
print("--- Broad quadratic b_n with -n^p numerators ---")
sys.stdout.flush()
t0 = time.time()
dh = 0
for p in [2, 3, 4]:
    for A in range(0, 20):
        for B in range(-15, 16):
            for C in range(1, 15):
                try:
                    val = mpf(A*200**2 + B*200 + C)
                    if fabs(val) < 1: continue
                    for n in range(199, 0, -1):
                        val = (A*n**2 + B*n + C) + (-(n+1)**p)/val
                    V = C + (-1)/val
                except: continue
                if fabs(V) > 1e15 or fabs(V) < 1e-15: continue
                for xn, xv in [("V", V), ("6/V", 6/V), ("1/V", 1/V),
                                ("2/V", 2/V), ("3/V", 3/V), ("4/V", 4/V)]:
                    mh = quick_match(xv)
                    for name, dig in mh:
                        if dig >= 15:
                            print("  HIT [p=%d, b=%dn2+%dn+%d]: %s=%s [%dd]" % (
                                p, A, B, C, xn, name, dig))
                            all_hits.append({"search": "Broad", "p": p,
                                "b": [A,B,C], "xform": xn, "target": name, "digits": dig})
                            dh += 1; sys.stdout.flush()
print("  Broad search: %d hits (%.0fs)" % (dh, time.time()-t0))
print(); sys.stdout.flush()

# ================================================================
# PART E: PSLQ survival pool on Zudilin-type CFs
# ================================================================
print("--- PSLQ survival pool ---")
sys.stdout.flush()
t0 = time.time()
pool = []
for r in [1, 2]:
    for A in range(1, 15):
        for B in range(-10, 11):
            for C in range(1, 10):
                try:
                    val = mpf(A*200**2 + B*200 + C)
                    if fabs(val) < 1: continue
                    for n in range(199, 0, -1):
                        val = (A*n**2 + B*n + C) + (-((n+1)**2)*((n+1+r)**2))/val
                    V = C + (-(1+r)**2)/val
                except: continue
                if fabs(V) > 1e10 or fabs(V) < 1e-10: continue
                pool.append((V, "r=%d,A=%d,B=%d,C=%d" % (r,A,B,C)))

print("  Pool: %d values" % len(pool))
ph = 0
for V, label in pool[:200]:
    basis = [V, mpf(1), pi, pi**2, Z3, Cat, Ln2, G13, G14]
    r = pslq(basis, maxcoeff=500)
    if r is None or r[0] == 0 or abs(r[0]) > 50: continue
    nz = sum(1 for x in r if x != 0)
    if nz < 3: continue
    check = sum(r[i]*basis[i] for i in range(len(basis)))
    if fabs(check) > mpf("1e-25"): continue
    new = any(r[i] != 0 for i in [4, 5, 7, 8])
    if new:
        labels = ["V","1","pi","pi2","Z3","Cat","ln2","G13","G14"]
        terms = ["%d*%s" % (r[i], labels[i]) for i in range(len(r)) if r[i] != 0]
        joiner = " + ".join(terms)
        print("  PSLQ [%s]: %s = 0" % (label, joiner))
        all_hits.append({"search": "PSLQ", "label": label, "relation": str(r)})
        ph += 1; sys.stdout.flush()
print("  PSLQ: %d hits (%.0fs)" % (ph, time.time()-t0))
print()

# SUMMARY
print("=" * 60)
print("GRAND TOTAL: %d hits" % len(all_hits))
for h in all_hits:
    print("  %s" % str(h))
if not all_hits:
    print("  No hits. Negative result confirmed across all search regimes.")
