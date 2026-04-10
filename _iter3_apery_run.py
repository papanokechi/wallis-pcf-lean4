"""Iteration 3: Apery-type CF search + PSLQ survival pool"""
from mpmath import mp, mpf, nstr, fabs, log, pi, catalan, zeta
from mpmath import gamma as mpgamma, pslq, log as mplog
import time, sys

mp.dps = 60
Z3 = zeta(3); Cat = catalan; G13 = mpgamma(mpf(1)/3); G14 = mpgamma(mpf(1)/4)
Ln2 = mplog(2)

targets = {
    "Z3": Z3, "Cat": Cat, "G13": G13, "G14": G14, "ln2": Ln2,
    "1/Z3": 1/Z3, "Z3/pi2": Z3/pi**2, "Cat/pi": Cat/pi,
    "pi": pi, "pi2/6": pi**2/6, "G14sq/(4pi)": G14**2/(4*pi),
}

def match_tgt(V):
    hits = []
    for name, tgt in targets.items():
        for kn in range(1, 8):
            for kd in range(1, 8):
                k = mpf(kn)/kd
                d = fabs(V - k*tgt)
                if d > 0 and d < mpf("1e-15"):
                    dig = int(-log(d, 10))
                    if dig >= 12:
                        pref = "" if (kn == 1 and kd == 1) else str(kn) + "/" + str(kd) + "*"
                        hits.append((pref + name, dig))
    return hits

all_hits = []
t0 = time.time()

# ================================================================
# SEARCH A: a_n = -n^p, b_n = c3*n^3 + c2*n^2 + c1*n + c0
# ================================================================
print("=== SEARCH A: Apery-type (a_n=-n^p, cubic b_n) ===")
sys.stdout.flush()

for p in [4, 5, 6]:
    p_hits = 0
    count = 0
    for c3 in range(-6, 7):
        for c2 in range(-6, 7):
            for c1 in range(-6, 7):
                for c0 in range(1, 8):
                    count += 1
                    try:
                        val = mpf(c3*50**3 + c2*50**2 + c1*50 + c0)
                        if fabs(val) < 1e-5:
                            continue
                        for n in range(49, 0, -1):
                            bn = c3*n**3 + c2*n**2 + c1*n + c0
                            val = bn + (-(n+1)**p) / val
                        v50 = c0 + (-1) / val
                    except Exception:
                        continue
                    if fabs(v50) > 1e15 or fabs(v50) < 1e-15:
                        continue

                    try:
                        val = mpf(c3*300**3 + c2*300**2 + c1*300 + c0)
                        if fabs(val) < 1e-5:
                            continue
                        for n in range(299, 0, -1):
                            bn = c3*n**3 + c2*n**2 + c1*n + c0
                            val = bn + (-(n+1)**p) / val
                        v300 = c0 + (-1) / val
                    except Exception:
                        continue
                    if fabs(v50 - v300) > mpf("1e-6"):
                        continue

                    V = v300
                    for xname, xval in [("V", V), ("6/V", 6/V), ("1/V", 1/V),
                                        ("2/V", 2/V), ("3/V", 3/V)]:
                        mh = match_tgt(xval)
                        for name, dig in mh:
                            if dig >= 12:
                                label = "  HIT [p=%d]: b=%dn3+%dn2+%dn+%d, %s=%s [%dd]" % (
                                    p, c3, c2, c1, c0, xname, name, dig)
                                print(label)
                                all_hits.append({
                                    "search": "A", "p": p,
                                    "b": [c3, c2, c1, c0],
                                    "xform": xname, "target": name,
                                    "digits": dig, "V": nstr(V, 25)
                                })
                                p_hits += 1
                                sys.stdout.flush()

    print("  p=%d: %d tested, %d hits" % (p, count, p_hits))
    sys.stdout.flush()

# ================================================================
# SEARCH B: a_n = -(alpha*n+beta)^2 * n^2, cubic b_n
# ================================================================
print()
print("=== SEARCH B: Generalized Apery (a_n=-(an+b)^2*n^2, cubic b_n) ===")
sys.stdout.flush()
b_hits = 0
for alpha in range(1, 4):
    for beta in range(-2, 3):
        for c3 in range(-4, 5):
            for c2 in range(-6, 7):
                for c1 in range(-6, 7):
                    for c0 in range(1, 6):
                        try:
                            val = mpf(c3*200**3 + c2*200**2 + c1*200 + c0)
                            if fabs(val) < 1e-5:
                                continue
                            for n in range(199, 0, -1):
                                an1 = -((alpha*(n+1) + beta)**2) * ((n+1)**2)
                                val = (c3*n**3 + c2*n**2 + c1*n + c0) + an1/val
                            a1 = -((alpha + beta)**2)
                            if fabs(a1) < 1e-10:
                                continue
                            v200 = c0 + a1/val
                        except Exception:
                            continue
                        if fabs(v200) > 1e15 or fabs(v200) < 1e-15:
                            continue

                        V = v200
                        for xname, xval in [("V", V), ("6/V", 6/V), ("1/V", 1/V)]:
                            mh = match_tgt(xval)
                            for name, dig in mh:
                                if dig >= 12:
                                    label = "  HIT: a=-(%dn+%d)^2*n^2, b=%dn3+%dn2+%dn+%d, %s=%s [%dd]" % (
                                        alpha, beta, c3, c2, c1, c0, xname, name, dig)
                                    print(label)
                                    all_hits.append({
                                        "search": "B", "alpha": alpha, "beta": beta,
                                        "b": [c3, c2, c1, c0],
                                        "xform": xname, "target": name,
                                        "digits": dig
                                    })
                                    b_hits += 1
                                    sys.stdout.flush()

print("  B total hits: %d" % b_hits)
sys.stdout.flush()

# ================================================================
# SEARCH C: PSLQ on non-matching Apery-type CFs
# ================================================================
print()
print("=== SEARCH C: PSLQ on Apery-type CFs ===")
sys.stdout.flush()
c_hits = 0
tested = 0
for p in [4, 6]:
    for c3 in [0, 1, 2, 17, 34]:
        for c2 in range(-5, 6):
            for c1 in range(-5, 6):
                for c0 in range(1, 6):
                    try:
                        val = mpf(c3*200**3 + c2*200**2 + c1*200 + c0)
                        if fabs(val) < 1e-5:
                            continue
                        for n in range(199, 0, -1):
                            val = (c3*n**3 + c2*n**2 + c1*n + c0) + (-(n+1)**p)/val
                        V = c0 + (-1)/val
                    except Exception:
                        continue
                    if fabs(V) > 1e10 or fabs(V) < 1e-10:
                        continue
                    tested += 1
                    basis = [V, mpf(1), pi, pi**2, Z3, Cat, Ln2, G13, G14]
                    r = pslq(basis, maxcoeff=500)
                    if r is None or r[0] == 0 or abs(r[0]) > 50:
                        continue
                    nz = sum(1 for x in r if x != 0)
                    if nz < 3:
                        continue
                    check = sum(r[i]*basis[i] for i in range(len(basis)))
                    if fabs(check) > mpf("1e-25"):
                        continue
                    new_const = any(r[i] != 0 for i in [4, 5, 7, 8])
                    if new_const:
                        labels = ["V", "1", "pi", "pi2", "Z3", "Cat", "ln2", "G13", "G14"]
                        terms = []
                        for i in range(len(r)):
                            if r[i] != 0:
                                terms.append("%d*%s" % (r[i], labels[i]))
                        print("  PSLQ HIT [p=%d,b=%dn3+%dn2+%dn+%d]:" % (p, c3, c2, c1, c0))
                        print("    V = %s" % nstr(V, 20))
                        print("    %s = 0" % " + ".join(terms))
                        all_hits.append({"search": "C", "p": p, "relation": str(r)})
                        c_hits += 1
                        sys.stdout.flush()

print("  C: %d tested, %d PSLQ hits" % (tested, c_hits))

elapsed = time.time() - t0
print()
print("=== GRAND TOTAL: %d hits in %.0fs ===" % (len(all_hits), elapsed))
for h in all_hits:
    print("  %s" % str(h))
