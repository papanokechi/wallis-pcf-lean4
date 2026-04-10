"""
Iteration 3 — Part 2: Apéry-type CF search + known CF verification
Focus: ζ(3), Catalan G via high-degree polynomial CFs (the Apéry CF family).

Key insight: q-polynomial GCFs (48,801 searched) yielded 0 hits.
The correct path to ζ(3) is Apéry-type: a_n = -n^p, b_n = cubic polynomial.
"""
from mpmath import (mp, mpf, nstr, fabs, log, pi, sqrt, euler,
                    catalan, zeta, gamma as mpgamma, pslq, exp,
                    log as mplog, power, fac, binomial, nsum, inf)
import time

mp.dps = 60

Z3 = zeta(3)
Cat = catalan
G13 = mpgamma(mpf(1)/3)
G14 = mpgamma(mpf(1)/4)
Ln2 = mplog(2)

targets = {
    "ζ(3)": Z3, "Catalan": Cat, "Γ(1/3)": G13, "Γ(1/4)": G14,
    "ln2": Ln2, "1/ζ(3)": 1/Z3, "ζ(3)/π²": Z3/pi**2,
    "Cat/π": Cat/pi, "π": pi, "π²/6": pi**2/6,
    "Γ(1/4)²/(4π)": G14**2/(4*pi),
}

def match_targets(V):
    hits = []
    for name, tgt in targets.items():
        for kn in range(1, 8):
            for kd in range(1, 8):
                k = mpf(kn)/kd
                d = fabs(V - k*tgt)
                if 0 < d < mpf('1e-15'):
                    dig = int(-log(d, 10))
                    if dig >= 12:
                        pref = "" if (kn==1 and kd==1) else f"{kn}/{kd}·"
                        hits.append((f"{pref}{name}", dig))
    return hits


# ═══════════════════════════════════════════════════════════
# PART 1: Verify known CFs
# ═══════════════════════════════════════════════════════════
print("═══ KNOWN CF VERIFICATION ═══")
print()

# 1a. Apéry CF for ζ(3) at high depth
print("  [1a] Apéry CF: ζ(3) = 6 / (5 - 1^6/(117 - 2^6/(535 - ...)))")
print("       b_n = 34n³+51n²+27n+5,  a_n = -n^6")
mp.dps = 80
Z3_80 = zeta(3)
depths = [100, 200, 500, 800]
for dep in depths:
    val = mpf(34*dep**3 + 51*dep**2 + 27*dep + 5)
    for n in range(dep-1, 0, -1):
        val = (34*n**3 + 51*n**2 + 27*n + 5) + (-(n+1)**6)/val
    V = mpf(5) + (-1)/val
    z3_est = 6/V
    d = fabs(z3_est - Z3_80)
    dig = int(-log(d, 10)) if d > 0 else 80
    print(f"       depth={dep}: {dig} digits")
mp.dps = 60
print()

# 1b. Apéry CF for ζ(2) = π²/6
print("  [1b] Apéry CF for ζ(2):")
# Correct formula: b_0=3, b_n=11n²+11n+3, a_n=-n^4
# ζ(2) · V_CF = 6  →  π²/6·V=6 nope
# Actually CF computes: sum = Σ 1/n² via b_0+K(a_n/b_n)
val = mpf(11*200**2 + 11*200 + 3)
for n in range(199, 0, -1):
    val = (11*n**2 + 11*n + 3) + (-(n+1)**4)/val
V = mpf(3) + (-1)/val
pi2_6_est = V
d = fabs(pi2_6_est - pi**2/6)
if d > 0 and d < 1:
    dig = int(-log(d, 10))
    print(f"       CF = {nstr(pi2_6_est, 25)}, π²/6 = {nstr(pi**2/6, 25)}")
    print(f"       Match: {dig} digits")
else:
    print(f"       V = {nstr(V, 25)}, trying other forms...")
    for test_name, test_val in [("V", V), ("1/V", 1/V), ("6/V", 6/V), ("3/V", 3/V), ("V/6", V/6)]:
        mh = match_targets(test_val)
        if mh:
            for name, dig in mh[:2]:
                print(f"       {test_name} = {name} [{dig}d]")
print()

# 1c. Catalan's constant from Stieltjes CF
print("  [1c] Catalan G from series:")
G_series = nsum(lambda n: (-1)**n / (2*n + 1)**2, [0, inf])
d = fabs(G_series - Cat)
print(f"       Σ(-1)^n/(2n+1)² = {nstr(G_series, 25)}")
print(f"       Cat = {nstr(Cat, 25)}")
dig_cat = int(-log(d, 10)) if d > 0 else mp.dps
print(f"       Match: {dig_cat} digits ✓")
print()

# 1d. Known Catalan CF: G = 1/(2 - 1^2/(10 - 3^2/(26 - ...)))
# a_n = -(2n-1)^2, b_n = 8n+2
# Or: b_0=2, b_n=8n+2, a_n=-(2n-1)^2
print("  [1d] Bauer-Muir CF for Catalan:")
val = mpf(8*200 + 2)
for n in range(199, 0, -1):
    val = (8*n + 2) + (-(2*n+1)**2)/val
V_bm = mpf(2) + (-1)/val
print(f"       V = {nstr(V_bm, 25)}")
mh = match_targets(V_bm)
for name, dig in mh:
    print(f"       → {name} [{dig}d]")
if not mh:
    for test_name, test_val in [("1/V", 1/V_bm), ("2/V", 2/V_bm), ("4/V", 4/V_bm)]:
        mh2 = match_targets(test_val)
        for name, dig in mh2:
            print(f"       {test_name} = {name} [{dig}d]")
print()


# ═══════════════════════════════════════════════════════════
# PART 2: Apéry-type generalization search
# a_n = -n^p,  b_n = c3·n³ + c2·n² + c1·n + c0
# Check V, 1/V, k/V for small k against all targets
# ═══════════════════════════════════════════════════════════
print("═══ SEARCH A: Apéry-type (a_n = -n^p, cubic b_n) ═══")
print()

all_hits = []
t0 = time.time()

for p in [4, 5, 6]:
    p_hits = 0
    for c3 in range(-8, 9):
        for c2 in range(-8, 9):
            for c1 in range(-8, 9):
                for c0 in range(1, 10):
                    # b(0) = c0 (must be nonzero for CF to start)
                    # b(n) = c3*n³ + c2*n² + c1*n + c0

                    try:
                        val = mpf(c3*50**3 + c2*50**2 + c1*50 + c0)
                        if fabs(val) < 1e-10:
                            continue
                        for n in range(49, 0, -1):
                            bn = c3*n**3 + c2*n**2 + c1*n + c0
                            val = bn + (-(n+1)**p) / val
                        v50 = c0 + (-1) / val
                    except:
                        continue
                    if fabs(v50) > 1e15 or fabs(v50) < 1e-15:
                        continue

                    try:
                        val = mpf(c3*300**3 + c2*300**2 + c1*300 + c0)
                        for n in range(299, 0, -1):
                            bn = c3*n**3 + c2*n**2 + c1*n + c0
                            val = bn + (-(n+1)**p) / val
                        v300 = c0 + (-1) / val
                    except:
                        continue
                    if fabs(v50 - v300) > mpf('1e-6'):
                        continue

                    V = v300

                    # Test V, 1/V, k/V
                    for xname, xval in [("V", V),
                                        ("6/V", 6/V if fabs(V) > 1e-10 else None),
                                        ("1/V", 1/V if fabs(V) > 1e-10 else None),
                                        ("2/V", 2/V if fabs(V) > 1e-10 else None),
                                        ("3/V", 3/V if fabs(V) > 1e-10 else None)]:
                        if xval is None:
                            continue
                        mh = match_targets(xval)
                        for name, dig in mh:
                            if dig >= 15:
                                print(f"  HIT [p={p}]: b={c3}n³+{c2}n²+{c1}n+{c0}, {xname}={name} [{dig}d]")
                                all_hits.append({
                                    "search": "A", "p": p,
                                    "b": [c3, c2, c1, c0],
                                    "xform": xname, "target": name,
                                    "digits": dig, "value": nstr(V, 25)
                                })
                                p_hits += 1

    print(f"  p={p}: {p_hits} hits")

elapsed_a = time.time() - t0
print(f"\n  Search A total: {len(all_hits)} hits ({elapsed_a:.0f}s)")
print()


# ═══════════════════════════════════════════════════════════
# PART 3: Extended Apéry: a_n = -(αn+β)^2 · n^2, cubic b_n
# This covers a broader class that includes the Apéry CF as special case
# ═══════════════════════════════════════════════════════════
print("═══ SEARCH B: Generalized Apéry (a_n = -(αn+β)²·n², cubic b_n) ═══")
print()

t0 = time.time()
b_hits_count = 0

for alpha in range(1, 5):
    for beta in range(-3, 4):
        for c3 in range(-5, 6):
            for c2 in range(-8, 9):
                for c1 in range(-8, 9):
                    for c0 in range(1, 8):
                        try:
                            val = mpf(c3*200**3 + c2*200**2 + c1*200 + c0)
                            if fabs(val) < 1e-10:
                                continue
                            for n in range(199, 0, -1):
                                an1 = -((alpha*(n+1) + beta)**2) * ((n+1)**2)
                                bn = c3*n**3 + c2*n**2 + c1*n + c0
                                val = bn + an1 / val
                            a1 = -((alpha + beta)**2)
                            v200 = c0 + a1 / val
                        except:
                            continue
                        if fabs(v200) > 1e15 or fabs(v200) < 1e-15:
                            continue

                        V = v200

                        for xname, xval in [("V", V), ("6/V", 6/V if fabs(V) > 1e-10 else None),
                                            ("1/V", 1/V if fabs(V) > 1e-10 else None)]:
                            if xval is None:
                                continue
                            mh = match_targets(xval)
                            for name, dig in mh:
                                if dig >= 12:
                                    print(f"  HIT: a=-({alpha}n+{beta})²n², b={c3}n³+{c2}n²+{c1}n+{c0}, {xname}={name} [{dig}d]")
                                    all_hits.append({
                                        "search": "B", "alpha": alpha, "beta": beta,
                                        "b": [c3, c2, c1, c0],
                                        "xform": xname, "target": name,
                                        "digits": dig, "value": nstr(V, 25)
                                    })
                                    b_hits_count += 1

print(f"\n  Search B: {b_hits_count} hits ({time.time()-t0:.0f}s)")
print()


# ═══════════════════════════════════════════════════════════
# PART 4: PSLQ on survival pool — take all non-matching convergent
#         Apéry-type CFs and test against extended basis
# ═══════════════════════════════════════════════════════════
print("═══ SEARCH C: PSLQ survival pool (Apéry-type remainders) ═══")
print()

t0 = time.time()
c_hits = 0
pool = []  # store (V, label) tuples

# Collect some non-matching CFs from Search A
for p in [4, 6]:
    for c3 in [0, 1, 2, 34]:
        for c2 in range(-5, 6):
            for c1 in range(-5, 6):
                for c0 in range(1, 8):
                    try:
                        val = mpf(c3*200**3 + c2*200**2 + c1*200 + c0)
                        if fabs(val) < 1e-10:
                            continue
                        for n in range(199, 0, -1):
                            val = (c3*n**3 + c2*n**2 + c1*n + c0) + (-(n+1)**p)/val
                        V = c0 + (-1)/val
                    except:
                        continue
                    if fabs(V) > 1e10 or fabs(V) < 1e-10:
                        continue
                    pool.append((V, f"p={p},b={c3}n³+{c2}n²+{c1}n+{c0}"))

print(f"  Pool size: {len(pool)}")

# PSLQ against extended basis
pslq_basis_labels = ["V", "1", "π", "π²", "ζ(3)", "Cat", "ln2", "Γ(1/3)", "Γ(1/4)"]

for V, label in pool[:500]:
    basis = [V, mpf(1), pi, pi**2, Z3, Cat, Ln2, G13, G14]
    r = pslq(basis, maxcoeff=500)
    if r is None or r[0] == 0:
        continue
    if abs(r[0]) > 50:
        continue
    nz = sum(1 for x in r if x != 0)
    if nz < 3:
        continue
    # Verify
    check = sum(r[i]*basis[i] for i in range(len(basis)))
    if fabs(check) > mpf('1e-25'):
        continue
    # Check if it involves ζ(3) or Cat (not just π)
    involves_new = any(r[i] != 0 for i in [4, 5, 7, 8])
    if involves_new:
        terms = [f"{r[i]}·{pslq_basis_labels[i]}" for i in range(len(r)) if r[i] != 0]
        print(f"  PSLQ HIT [{label}]:")
        print(f"    V = {nstr(V, 20)}")
        print(f"    {' + '.join(terms)} = 0")
        all_hits.append({"search": "C-PSLQ", "label": label, "relation": str(r),
                        "value": nstr(V, 25)})
        c_hits += 1

print(f"\n  Search C: {c_hits} PSLQ hits ({time.time()-t0:.0f}s)")
print()


# ═══════════════════════════════════════════════════════════
# GRAND SUMMARY
# ═══════════════════════════════════════════════════════════
print("═══════════════════════════════════════════════════════")
print("  ITERATION 3: GRAND SUMMARY")
print("═══════════════════════════════════════════════════════")
print()
print(f"Grand total hits: {len(all_hits)}")
if all_hits:
    by_target = {}
    for h in all_hits:
        t = h.get("target", "PSLQ")
        by_target.setdefault(t, []).append(h)
    for t, hs in sorted(by_target.items()):
        max_dig = max(h.get("digits", 0) for h in hs)
        print(f"  {t}: {len(hs)} hit(s), best = {max_dig} digits")
    print()
    for h in all_hits:
        if h.get("digits", 0) >= 20:
            print(f"  ★ {h}")
else:
    print("  No new hits from Apéry-type search.")
print()

# Analysis of what we learned
print("═══ ANALYSIS ═══")
print()
print("Iteration 3 explored two regimes:")
print("  1. q-series (48,801 GCFs across 5 bases): 0 hits")
print("  2. Apéry-type high-degree (n^p numerators, cubic denominators)")
print()
print("The q-series null result suggests that ζ(3)/Catalan/Γ constants")
print("are NOT accessible from simple q-polynomial GCFs of degree ≤2.")
print("This extends Iteration 2's negative result from polynomial-in-n")
print("to polynomial-in-q^n coefficient functions.")
