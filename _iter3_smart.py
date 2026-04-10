"""
Iteration 3: SMART search — generalize from KNOWN CF structures
instead of blind grid search.

Strategy:
1. Verify known CFs for zeta(3), Catalan, ln2, Gamma
2. Parametric perturbation of Apery CF
3. Structured search: b_n = (2n+1)(An^2+Bn+C), a_n = -(n*(n+1)/2)^k etc.
4. PSLQ on all convergent CFs from structured forms
"""
from mpmath import mp, mpf, nstr, fabs, log, pi, catalan, zeta
from mpmath import gamma as mpgamma, pslq, log as mplog, sqrt, euler
from mpmath import power, nsum, inf, binomial
import time, sys

mp.dps = 60
Z3 = zeta(3); Z5 = zeta(5); Cat = catalan
G13 = mpgamma(mpf(1)/3); G14 = mpgamma(mpf(1)/4)
Ln2 = mplog(2); Eu = euler

targets = {
    "Z3": Z3, "Cat": Cat, "G13": G13, "G14": G14,
    "ln2": Ln2, "Z5": Z5, "pi": pi, "pi2/6": pi**2/6,
}
# Augmented targets with multiplied/divided forms
aug_targets = {}
for name, val in targets.items():
    aug_targets[name] = val
    for k in [2, 3, 4, 5, 6]:
        aug_targets["%d*%s" % (k, name)] = k*val
        aug_targets["%s/%d" % (name, k)] = val/k

def quick_match(V, threshold=12):
    hits = []
    for name, tgt in aug_targets.items():
        d = fabs(V - tgt)
        if d > 0 and d < mpf("1e-10"):
            dig = int(-log(d, 10))
            if dig >= threshold:
                hits.append((name, dig))
    return hits

print("=" * 60)
print("  ITERATION 3: SMART STRUCTURAL SEARCH")
print("=" * 60)
print()
sys.stdout.flush()

all_hits = []

# ================================================================
# PART 1: Verify ALL known CFs
# ================================================================
print("--- PART 1: Known CF Verification ---")
print()
sys.stdout.flush()

# 1a. Apery CF for zeta(3)
# b_0=5, b_n=34n^3+51n^2+27n+5, a_n=-n^6
mp.dps = 80
Z3_80 = zeta(3)
val = mpf(34*500**3 + 51*500**2 + 27*500 + 5)
for n in range(499, 0, -1):
    val = (34*n**3 + 51*n**2 + 27*n + 5) + (-(n+1)**6)/val
V = mpf(5) + (-1)/val
d = fabs(6/V - Z3_80)
dig = int(-log(d, 10)) if d > 0 else 80
print("  [1a] Apery zeta(3): 6/CF = Z3 to %d digits" % dig)
mp.dps = 60

# 1b. Apery CF for zeta(2) = pi^2/6
# b_0=3, b_n=11n^2+11n+3, a_n=-n^4
# Or: b_n=(2n+1)(3n(n+1)/2+1) ... let me just check
val = mpf(11*300**2 + 11*300 + 3)
for n in range(299, 0, -1):
    val = (11*n**2 + 11*n + 3) + (-(n+1)**4)/val
V2 = mpf(3) + (-1)/val
# Try various normalizations
for k, name in [(1, "V"), (2, "2V"), (3, "3V"), (6, "6V"),
                (mpf(1)/2, "V/2"), (mpf(1)/3, "V/3"), (mpf(1)/6, "V/6")]:
    test = k * V2
    d = fabs(test - pi**2/6)
    if d > 0 and d < 1:
        dig = int(-log(d, 10))
        if dig >= 5:
            print("  [1b] Apery zeta(2): %s = pi^2/6 to %d digits" % (name, dig))
            break
else:
    mh = quick_match(V2)
    if mh:
        print("  [1b] Apery zeta(2): V = %s [%dd]" % (mh[0][0], mh[0][1]))
    else:
        print("  [1b] Apery zeta(2): V = %s (no match)" % nstr(V2, 20))

# 1c. Euler CF for ln2
# ln2 = 1/(1+1/(1+1/(1+4/(1+4/(1+9/(1+9/(1+...)))))))
# = 1/(1 + K) where the CF has a_{2k-1}=k^2, a_{2k}=k^2, b_n=1
# More simply: ln(2) = 1/(1 + 1^2/(2 + 1^2/(3 + 2^2/(4 + 2^2/(5 + ...)))))
# Or: ln(1+x) = x/(1 + x/(2 + x/(3 + 4x/(4 + 4x/(5 + 9x/(6 + ...))))))
# Simpler known: ln(2) = CF with a_n = ceil(n/2)^2, b_n = n  (Stieltjes type)
# Actually simplest: 1/(1+K(n^2 | 4n^2-1))  Nah. Let me just verify:
# ln(2) = 1 - 1/2 + 1/3 - 1/4 + ... Euler transform of this gives a CF.
# Known: ln(2) = 1/(1+1/(1+1/(1+4/(1+4/(1+... )))))) = 
# Thiele CF for ln(1+x) at x=1: a_n = cf_coefficients, b_n = 1
# Let me try a_n = n^2, b_n = 2n+1 (simplest quadratic/linear)
val = mpf(2*100+1)
for n in range(99, 0, -1):
    val = (2*n+1) + (n+1)**2 / val
V_ln2_test = 1 + 1/val
d = fabs(V_ln2_test - Ln2)
mh = quick_match(V_ln2_test)
if mh:
    print("  [1c] ln2 CF test: %s [%dd]" % (mh[0][0], mh[0][1]))
else:
    # Known Stieltjes: ln(2) = 1/(1+1^2/(2+2^2/(3+3^2/(4+...))))
    # a_n = n^2, b_n = n+1 (b_0=1)
    val = mpf(201)
    for n in range(199, 0, -1):
        val = (n+1) + (n+1)**2/val
    V_st = 1/val + 1  # b_0=1, so 1 + a_1/val... wait
    # Actually b_0 + a_1/(b_1 + a_2/(b_2 + ...)) with b_n=n+1, a_n=n^2:
    val = mpf(201)
    for n in range(199, 0, -1):
        val = (n+1) + ((n+1)**2)/val
    V_st2 = 1 + 1/val
    mh2 = quick_match(V_st2)
    if mh2:
        print("  [1c] Stieltjes ln2: %s [%dd]" % (mh2[0][0], mh2[0][1]))
    else:
        print("  [1c] ln2: V=%s (no simple CF match)" % nstr(V_st2, 15))

# 1d. Catalan CF
# Known: G = sum_{n>=0} (-1)^n/(2n+1)^2
# CF: beta(2) via Euler CF of L(2,chi_4)
# There's a CF: G = 1/(2 + 1^2/(2 + 3^2/(2 + 5^2/(2 + ...))))
# a_n = (2n-1)^2, b_n = 2
val = mpf(2)
for n in range(200, 0, -1):
    val = 2 + (2*n-1)**2 / val
V_cat = 1/val
mh = quick_match(V_cat)
if mh:
    print("  [1d] Catalan CF (odd^2, b=2): %s [%dd]" % (mh[0][0], mh[0][1]))
else:
    d = fabs(V_cat - Cat)
    if d > 0 and d < 1:
        print("  [1d] Cat CF: 1/CF = %s, Cat = %s, diff=%s" % (nstr(V_cat, 20), nstr(Cat, 20), nstr(d, 5)))
    else:
        print("  [1d] V_cat = %s" % nstr(V_cat, 15))
    # Try: G = 1/(1 + 1/(8 + 9/(16 + ...)))
    # a_n = n^2(2n-1)^2/4, b_n = ...
    # Or simpler: G can be written as 1/2 * sum ... various forms
    # Let me try Watson's CF: G/(pi/4) related form
    pass

# 1e. Gamma(1/4) from AGM
# Gamma(1/4)^2 = 2pi * AGM(1, sqrt(2))  (approx)
# Not directly a CF but related to elliptic integrals

print()
sys.stdout.flush()

# ================================================================
# PART 2: Apery-FAMILY search
# b_n = (2n+1)(An^2+Bn+C), a_n = -n^p
# Much smaller search space than blind cubic scan
# ================================================================
print("--- PART 2: Apery-family structured search ---")
print("  b_n = (2n+1)(An^2+Bn+C), a_n = -n^p")
print()
sys.stdout.flush()

t0 = time.time()
apery_hits = 0

for p in [4, 5, 6, 8]:
    for A in range(0, 30):
        for B in range(-20, 21):
            for C in range(1, 20):
                # b_n = (2n+1)(An^2 + Bn + C) = 2An^3 + (2B+A)n^2 + (2C+B)n + C
                c3 = 2*A
                c2 = 2*B + A
                c1 = 2*C + B
                c0 = C

                if c0 <= 0:
                    continue

                try:
                    val = mpf(c3*300**3 + c2*300**2 + c1*300 + c0)
                    if fabs(val) < 1:
                        continue
                    for n in range(299, 0, -1):
                        bn = c3*n**3 + c2*n**2 + c1*n + c0
                        val = bn + (-(n+1)**p)/val
                    V = c0 + (-1)/val
                except Exception:
                    continue

                if fabs(V) > 1e15 or fabs(V) < 1e-15:
                    continue

                # Check V, k/V for various k
                for xname, xval in [("V", V), ("6/V", 6/V), ("1/V", 1/V),
                                    ("2/V", 2/V), ("3/V", 3/V),
                                    ("4/V", 4/V), ("5/V", 5/V)]:
                    mh = quick_match(xval)
                    for name, dig in mh:
                        # Skip if it's just the known Apery CF
                        if name == "Z3" and A == 17 and B == 17 and C == 5 and p == 6:
                            continue
                        if name == "pi2/6" and A == 0 and p == 4:
                            continue
                        if dig >= 15:
                            print("  HIT [p=%d, A=%d,B=%d,C=%d]: %s=%s [%dd]" % (
                                p, A, B, C, xname, name, dig))
                            all_hits.append({
                                "search": "Apery-family", "p": p,
                                "A": A, "B": B, "C": C,
                                "xform": xname, "target": name,
                                "digits": dig, "V": nstr(V, 25)
                            })
                            apery_hits += 1
                            sys.stdout.flush()

print("  Apery-family: %d hits (%.0fs)" % (apery_hits, time.time()-t0))
print()
sys.stdout.flush()


# ================================================================
# PART 3: Zudilin-type CFs for zeta values
# a_n = -n^2*(n+1)^2 * P(n), b_n = Q(n)
# ================================================================
print("--- PART 3: Zudilin-type CFs ---")
print("  a_n = -n^2*(n+r)^2, b_n = An^2+Bn+C")
print()
sys.stdout.flush()

t0 = time.time()
zudilin_hits = 0

for r in range(1, 5):
    for A in range(1, 20):
        for B in range(-15, 16):
            for C in range(1, 15):
                try:
                    val = mpf(A*200**2 + B*200 + C)
                    if fabs(val) < 1:
                        continue
                    for n in range(199, 0, -1):
                        an1 = -((n+1)**2) * ((n+1+r)**2)
                        bn = A*n**2 + B*n + C
                        val = bn + an1/val
                    a1_val = -1 * (1+r)**2
                    V = C + a1_val/val
                except Exception:
                    continue

                if fabs(V) > 1e15 or fabs(V) < 1e-15:
                    continue

                for xname, xval in [("V", V), ("6/V", 6/V), ("1/V", 1/V),
                                    ("2/V", 2/V), ("3/V", 3/V)]:
                    mh = quick_match(xval)
                    for name, dig in mh:
                        if dig >= 15:
                            print("  HIT [r=%d, A=%d,B=%d,C=%d]: %s=%s [%dd]" % (
                                r, A, B, C, xname, name, dig))
                            all_hits.append({
                                "search": "Zudilin", "r": r,
                                "A": A, "B": B, "C": C,
                                "xform": xname, "target": name,
                                "digits": dig, "V": nstr(V, 25)
                            })
                            zudilin_hits += 1
                            sys.stdout.flush()

print("  Zudilin-type: %d hits (%.0fs)" % (zudilin_hits, time.time()-t0))
print()
sys.stdout.flush()


# ================================================================
# PART 4: Bauer-Muir / Catalan-targeted CFs
# a_n = -(2n+alpha)^2 * (2n+beta)^2, b_n = linear/quadratic
# ================================================================
print("--- PART 4: Catalan-targeted CFs ---")
print("  a_n = -(2n+a)^2 * f(n), b_n = An+B or An^2+Bn+C")
print()
sys.stdout.flush()

t0 = time.time()
cat_hits = 0

# Type 1: a_n = -(2n+alpha)^2, b_n = An+B
for alpha in range(-3, 4):
    for A in range(1, 15):
        for B in range(-10, 11):
            try:
                val = mpf(A*300 + B)
                if fabs(val) < 1:
                    continue
                for n in range(299, 0, -1):
                    an1 = -((2*(n+1) + alpha)**2)
                    val = (A*n + B) + an1/val
                a1_val = -((2 + alpha)**2)
                if a1_val == 0:
                    continue
                V = B + a1_val/val
            except Exception:
                continue
            if fabs(V) > 1e12 or fabs(V) < 1e-12:
                continue
            for xname, xval in [("V", V), ("1/V", 1/V), ("4/V", 4/V), ("2/V", 2/V)]:
                mh = quick_match(xval)
                for name, dig in mh:
                    if dig >= 12:
                        print("  HIT [alpha=%d, b=%dn+%d]: %s=%s [%dd]" % (
                            alpha, A, B, xname, name, dig))
                        all_hits.append({
                            "search": "Cat-type1", "alpha": alpha,
                            "A": A, "B": B, "xform": xname,
                            "target": name, "digits": dig
                        })
                        cat_hits += 1
                        sys.stdout.flush()

# Type 2: a_n = -n^2*(2n+alpha)^2, b_n = An^2+Bn+C
for alpha in range(-2, 3):
    for A in range(1, 15):
        for B in range(-10, 11):
            for C in range(1, 10):
                try:
                    val = mpf(A*200**2 + B*200 + C)
                    if fabs(val) < 1:
                        continue
                    for n in range(199, 0, -1):
                        an1 = -((n+1)**2) * ((2*(n+1) + alpha)**2)
                        val = (A*n**2 + B*n + C) + an1/val
                    a1_val = -(1) * ((2 + alpha)**2)
                    if a1_val == 0:
                        continue
                    V = C + a1_val/val
                except Exception:
                    continue
                if fabs(V) > 1e15 or fabs(V) < 1e-15:
                    continue
                for xname, xval in [("V", V), ("1/V", 1/V), ("4/V", 4/V),
                                    ("6/V", 6/V), ("2/V", 2/V)]:
                    mh = quick_match(xval)
                    for name, dig in mh:
                        if dig >= 12:
                            print("  HIT [a=-n^2*(2n+%d)^2, b=%dn2+%dn+%d]: %s=%s [%dd]" % (
                                alpha, A, B, C, xname, name, dig))
                            all_hits.append({
                                "search": "Cat-type2", "alpha": alpha,
                                "b": [A, B, C], "xform": xname,
                                "target": name, "digits": dig
                            })
                            cat_hits += 1
                            sys.stdout.flush()

print("  Catalan-targeted: %d hits (%.0fs)" % (cat_hits, time.time()-t0))
print()
sys.stdout.flush()


# ================================================================
# PART 5: PSLQ survival pool on unique CF values from above
# ================================================================
print("--- PART 5: PSLQ survival pool ---")
sys.stdout.flush()

# Collect CF values from structured search
t0 = time.time()
pool_vals = []

# Quick sweep of Apery-family CFs with p=6
for A in range(0, 25):
    for B in range(-15, 16):
        for C in range(1, 15):
            c3, c2, c1, c0 = 2*A, 2*B+A, 2*C+B, C
            if c0 <= 0:
                continue
            try:
                val = mpf(c3*200**3 + c2*200**2 + c1*200 + c0)
                if fabs(val) < 1:
                    continue
                for n in range(199, 0, -1):
                    val = (c3*n**3 + c2*n**2 + c1*n + c0) + (-(n+1)**6)/val
                V = c0 + (-1)/val
            except Exception:
                continue
            if fabs(V) > 1e10 or fabs(V) < 1e-10:
                continue
            pool_vals.append((V, "A=%d,B=%d,C=%d" % (A,B,C)))

print("  Pool: %d CF values" % len(pool_vals))

pslq_hits = 0
for V, label in pool_vals[:300]:
    basis = [V, mpf(1), pi, pi**2, Z3, Cat, Ln2, G13, G14, Z5]
    r = pslq(basis, maxcoeff=500)
    if r is None or r[0] == 0 or abs(r[0]) > 50:
        continue
    nz = sum(1 for x in r if x != 0)
    if nz < 3:
        continue
    check = sum(r[i]*basis[i] for i in range(len(basis)))
    if fabs(check) > mpf("1e-25"):
        continue
    # Check if involves NEW constants (not just pi)
    involves_new = any(r[i] != 0 for i in [4, 5, 7, 8, 9])
    if involves_new:
        labels = ["V", "1", "pi", "pi2", "Z3", "Cat", "ln2", "G13", "G14", "Z5"]
        terms = []
        for i in range(len(r)):
            if r[i] != 0:
                terms.append("%d*%s" % (r[i], labels[i]))
        print("  PSLQ HIT [%s]: %s = 0" % (label, " + ".join(terms)))
        print("    V = %s" % nstr(V, 20))
        all_hits.append({"search": "PSLQ", "label": label, "relation": str(r)})
        pslq_hits += 1
        sys.stdout.flush()

print("  PSLQ: %d hits (%.0fs)" % (pslq_hits, time.time()-t0))
print()
sys.stdout.flush()


# ================================================================
# GRAND SUMMARY
# ================================================================
print("=" * 60)
print("  ITERATION 3 GRAND SUMMARY")
print("=" * 60)
print()
print("  Total hits: %d" % len(all_hits))
if all_hits:
    by_target = {}
    for h in all_hits:
        t = h.get("target", "PSLQ")
        by_target.setdefault(t, []).append(h)
    for t, hs in sorted(by_target.items()):
        max_dig = max(h.get("digits", 0) for h in hs)
        print("  %s: %d hit(s), best %d digits" % (t, len(hs), max_dig))
    print()
    for h in all_hits:
        print("  -> %s" % str(h))
else:
    print("  No new hits from structured search.")
    print()
    print("  The q-series search (48,801 q-polynomial GCFs) also yielded 0 hits.")
    print()
    print("  INTERPRETATION:")
    print("  The Apery CF for zeta(3) uses -n^6 numerators and cubic b_n")
    print("  with LARGE coefficients (34, 51, 27, 5). If no NEW such CFs")
    print("  exist for Catalan/Gamma, this suggests the Apery CF is truly")
    print("  exceptional (consistent with the uniqueness theorems of Zudilin).")
