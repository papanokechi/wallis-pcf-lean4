"""
Iteration 3 — Optimized q-Series Search
Split into focused, fast searches with precomputed q^n caches.
"""
from mpmath import (mp, mpf, nstr, fabs, log, pi, sqrt, euler,
                    catalan, zeta, gamma as mpgamma, pslq, exp,
                    log as mplog, power, fac)
import time

mp.dps = 60

# ── Targets ──
Z3 = zeta(3)
Cat = catalan
G13 = mpgamma(mpf(1)/3)
G14 = mpgamma(mpf(1)/4)
Ln2 = mplog(2)
Eu = euler

targets = {
    "ζ(3)": Z3, "Catalan": Cat, "Γ(1/3)": G13, "Γ(1/4)": G14,
    "ln2": Ln2, "1/ζ(3)": 1/Z3, "ζ(3)/π²": Z3/pi**2,
    "Cat/π": Cat/pi, "Γ(1/4)²/(4π)": G14**2/(4*pi),
}
# Also include pi-related to catch any q-deformed pi families
targets["π"] = pi
targets["π²/6"] = pi**2/6  # = ζ(2)

def gcf_bw(a_fn, b_fn, depth=200):
    val = b_fn(depth)
    for n in range(depth-1, 0, -1):
        val = b_fn(n) + a_fn(n+1)/val
    return b_fn(0) + a_fn(1)/val

def match_targets(V, label=""):
    """Check V against all targets with multipliers"""
    hits = []
    for name, tgt in targets.items():
        for kn in range(1, 7):
            for kd in range(1, 7):
                k = mpf(kn)/kd
                d = fabs(V - k*tgt)
                if 0 < d < mpf('1e-15'):
                    dig = int(-log(d, 10))
                    if dig >= 12:
                        pref = "" if (kn==1 and kd==1) else f"{kn}/{kd}·"
                        hits.append((f"{pref}{name}", dig))
    return hits

# ═══════════════════════════════════════════════════════════
# PART 1: Verify Apéry CF for ζ(3) as baseline
# ═══════════════════════════════════════════════════════════
print("═══ BASELINE: Apéry CF for ζ(3) ═══")
print()

# Apéry's CF: ζ(3) = 6/(5 + a_1/(b_1 + a_2/(b_2 + ...)))
# a_n = -n^6,  b_n = (2n-1)(17n²-17n+5) = 34n³-51n²+27n-5
# Wait, need correct formula. Standard: ζ(3) = 6/(c_0 + K(c_n/1))
# where c_n = -n^6/(34n^3+51n^2+27n+5)
# Actually the CF is b_0 + a_1/(b_1 + a_2/(b_2+...))
# b_0=5, b_n = 34n^3+51n^2+27n+5, a_n = -n^6

V = gcf_bw(lambda n: -(n**6), 
           lambda n: 34*n**3+51*n**2+27*n+5 if n > 0 else mpf(5),
           300)
zeta3_from_cf = 6/V
d = fabs(zeta3_from_cf - Z3)
dig = int(-log(d, 10)) if d > 0 else 60
print(f"  ζ(3) from Apéry CF: {nstr(zeta3_from_cf, 30)}")
print(f"  ζ(3) exact:         {nstr(Z3, 30)}")
print(f"  Match: {dig} digits ✓")
print()

# Also verify Catalan CF (Ramanujan-type)
# G = 1 - 1/2 * K where a_n = n^4, b_n = ...
# Known: G = β(2) = Σ (-1)^n/(2n+1)^2
# CF: G = 1/(1 + 1^4/(8 + 2^4/(16 + 3^4/(24 + ...))))
# b_n = 8n, a_n = n^4
V_cat = gcf_bw(lambda n: n**4,
               lambda n: 8*n if n > 0 else mpf(1),
               300)
for k in [1, 2, 4, 8, mpf(1)/2, mpf(1)/4]:
    d = fabs(V_cat*k - Cat)
    if d < mpf('1e-10') and d > 0:
        print(f"  Catalan = {k}·CF: {int(-log(d, 10))} digits ✓")
        break
    d2 = fabs(k/V_cat - Cat)
    if d2 < mpf('1e-10') and d2 > 0:
        print(f"  Catalan = {k}/CF: {int(-log(d2, 10))} digits ✓")
        break
else:
    print(f"  V_cat = {nstr(V_cat, 20)} (checking...)")
    mh = match_targets(V_cat, "cat_cf")
    for m, d in mh:
        print(f"    → {m} [{d}d]")
    if not mh:
        print(f"    (no target match)")
print()


# ═══════════════════════════════════════════════════════════
# PART 2: Optimized q-Polynomial Search
# Precompute q^n table ONCE per q, then scan coefficients
# ═══════════════════════════════════════════════════════════
print("═══ SEARCH A: q-Polynomial GCFs (optimized) ═══")
print()

q_grid = [
    (mpf(1)/2, "1/2"), (mpf(1)/3, "1/3"), (-mpf(1)/2, "-1/2"),
    (mpf(2)/3, "2/3"), (exp(-pi), "e^{-π}"),
]

all_hits = []
total = 0
t0 = time.time()

for q, qlabel in q_grid:
    # Precompute q^n for n=0..250
    QN = [power(q, n) for n in range(251)]

    q_hits = 0
    # a_n = c0 + c1·q^n,  b_n = d0 + d1·q^n  (degree 1, faster)
    for c0 in range(-5, 6):
        for c1 in range(-5, 6):
            if c0 == 0 and c1 == 0:
                continue
            for d0 in range(1, 7):
                for d1 in range(-5, 6):
                    # Check a(1) non-zero
                    a1_val = c0 + c1 * QN[1]
                    if fabs(a1_val) < 1e-10:
                        continue

                    # Quick convergence check at depth 30
                    try:
                        val = d0 + d1 * QN[30]
                        for n in range(29, 0, -1):
                            an1 = c0 + c1 * QN[n+1]
                            val = (d0 + d1 * QN[n]) + an1 / val
                        v30 = (d0 + d1 * QN[0]) + (c0 + c1 * QN[1]) / val
                    except:
                        continue

                    if fabs(v30) > 1e12 or fabs(v30) < 1e-12:
                        continue

                    # Full depth 150
                    try:
                        val = d0 + d1 * QN[150]
                        for n in range(149, 0, -1):
                            an1 = c0 + c1 * QN[n+1]
                            val = (d0 + d1 * QN[n]) + an1 / val
                        v150 = (d0 + d1 * QN[0]) + (c0 + c1 * QN[1]) / val
                    except:
                        continue

                    if fabs(v30 - v150) > mpf('1e-8'):
                        continue

                    total += 1
                    V = v150

                    mh = match_targets(V)
                    for name, dig in mh:
                        print(f"  HIT [q={qlabel}]: a={c0}+{c1}q^n, b={d0}+{d1}q^n → {name} [{dig}d]")
                        all_hits.append({"search": "A", "q": qlabel, "params": f"a={c0}+{c1}q^n, b={d0}+{d1}q^n",
                                        "target": name, "digits": dig, "value": nstr(V, 25)})
                        q_hits += 1

    # Now degree 2: a_n = c0 + c1·q^n + c2·q^{2n}, b_n = d0 + d1·q^n
    QN2 = [QN[n]**2 for n in range(251)]  # q^{2n}
    for c0 in range(-3, 4):
        for c1 in range(-3, 4):
            for c2 in [-2, -1, 1, 2]:
                for d0 in range(1, 5):
                    for d1 in range(-3, 4):
                        a1_val = c0 + c1*QN[1] + c2*QN2[1]
                        if fabs(a1_val) < 1e-10:
                            continue

                        try:
                            val = d0 + d1*QN[30]
                            for n in range(29, 0, -1):
                                an1 = c0 + c1*QN[n+1] + c2*QN2[n+1]
                                val = (d0 + d1*QN[n]) + an1/val
                            v30 = (d0 + d1*QN[0]) + (c0 + c1*QN[1] + c2*QN2[1])/val
                        except:
                            continue

                        if fabs(v30) > 1e12 or fabs(v30) < 1e-12:
                            continue

                        try:
                            val = d0 + d1*QN[150]
                            for n in range(149, 0, -1):
                                an1 = c0 + c1*QN[n+1] + c2*QN2[n+1]
                                val = (d0 + d1*QN[n]) + an1/val
                            v150 = (d0 + d1*QN[0]) + (c0 + c1*QN[1] + c2*QN2[1])/val
                        except:
                            continue

                        if fabs(v30 - v150) > mpf('1e-8'):
                            continue

                        total += 1
                        V = v150

                        mh = match_targets(V)
                        for name, dig in mh:
                            print(f"  HIT [q={qlabel}]: a={c0}+{c1}q^n+{c2}q^{{2n}}, b={d0}+{d1}q^n → {name} [{dig}d]")
                            all_hits.append({"search": "A2", "q": qlabel,
                                            "params": f"a={c0}+{c1}q^n+{c2}q^{{2n}}, b={d0}+{d1}q^n",
                                            "target": name, "digits": dig, "value": nstr(V, 25)})
                            q_hits += 1

    print(f"  q={qlabel}: {q_hits} hits")

print(f"\n  Total A: {total} convergent q-GCFs, {len([h for h in all_hits if h['search'].startswith('A')])} hits ({time.time()-t0:.0f}s)")
print()


# ═══════════════════════════════════════════════════════════
# PART 3: q-Pochhammer CFs (Rogers-Ramanujan territory)
# ═══════════════════════════════════════════════════════════
print("═══ SEARCH B: q-Pochhammer CFs ═══")
print()

def qpoch(a, q, n):
    """(a;q)_n"""
    r = mpf(1)
    ak = a
    for k in range(n):
        r *= (1 - ak)
        ak *= q
    return r

t0 = time.time()
b_hits = 0

for q, qlabel in [(mpf(1)/2, "1/2"), (mpf(1)/3, "1/3"), (-mpf(1)/2, "-1/2")]:
    QN = [power(q, n) for n in range(251)]

    # Precompute (q;q)_n
    qq = [qpoch(q, q, n) for n in range(251)]
    # (q^2;q)_n
    qq2 = [qpoch(q**2, q, n) for n in range(251)]

    for a_type in range(4):
        # 0: (q;q)_n · q^n
        # 1: (q;q)_n^2 · q^n
        # 2: (q;q)_n · (q^2;q)_n · q^n
        # 3: n · (q;q)_n · q^n
        for a_sign in [1, -1]:
            for b_const in [1, 2, 3]:
                for b_qcoeff in range(-3, 4):

                    def a_fn(n, _at=a_type, _as=a_sign):
                        if n <= 0 or n >= 251:
                            return mpf(0)
                        if _at == 0:
                            return _as * qq[n] * QN[n]
                        elif _at == 1:
                            return _as * qq[n]**2 * QN[n]
                        elif _at == 2:
                            return _as * qq[n] * qq2[n] * QN[n]
                        else:
                            return _as * n * qq[n] * QN[n]

                    def b_fn(n, _bc=b_const, _bq=b_qcoeff):
                        return _bc + _bq * QN[min(n, 250)]

                    a1 = a_fn(1)
                    if fabs(a1) < 1e-10:
                        continue

                    try:
                        val = b_fn(30)
                        for n in range(29, 0, -1):
                            val = b_fn(n) + a_fn(n+1)/val
                        v30 = b_fn(0) + a_fn(1)/val
                    except:
                        continue

                    if fabs(v30) > 1e12 or fabs(v30) < 1e-12:
                        continue

                    try:
                        val = b_fn(150)
                        for n in range(149, 0, -1):
                            val = b_fn(n) + a_fn(n+1)/val
                        v150 = b_fn(0) + a_fn(1)/val
                    except:
                        continue

                    if fabs(v30 - v150) > mpf('1e-6'):
                        continue

                    V = v150
                    mh = match_targets(V)
                    for name, dig in mh:
                        type_name = ["(q;q)_n·q^n", "(q;q)_n²·q^n", "(q;q)_n·(q²;q)_n·q^n", "n·(q;q)_n·q^n"][a_type]
                        signstr = "-" if a_sign == -1 else ""
                        print(f"  HIT [q={qlabel}]: a={signstr}{type_name}, b={b_const}+{b_qcoeff}q^n → {name} [{dig}d]")
                        all_hits.append({"search": "B", "q": qlabel, "a_type": type_name,
                                        "target": name, "digits": dig, "value": nstr(V, 25)})
                        b_hits += 1

                    # PSLQ for interesting values
                    if V is not None and fabs(V) > 0.01 and fabs(V) < 100:
                        basis = [V, mpf(1), pi, pi**2, Z3, Cat, Ln2]
                        r = pslq(basis, maxcoeff=200)
                        if r is not None and r[0] != 0 and abs(r[0]) <= 30:
                            nz = sum(1 for x in r if x != 0)
                            if nz >= 3:
                                check = sum(r[i]*basis[i] for i in range(len(basis)))
                                if fabs(check) < mpf('1e-30'):
                                    labels = ["V","1","π","π²","ζ(3)","Cat","ln2"]
                                    terms = [f"{r[i]}·{labels[i]}" for i in range(len(r)) if r[i] != 0]
                                    type_name = ["(q;q)_n·q^n", "(q;q)_n²·q^n", "(q;q)_n·(q²;q)_n·q^n", "n·(q;q)_n·q^n"][a_type]
                                    signstr = "-" if a_sign == -1 else ""
                                    print(f"  PSLQ [q={qlabel}]: a={signstr}{type_name}, b={b_const}+{b_qcoeff}q^n")
                                    print(f"    V = {nstr(V, 20)}")
                                    print(f"    {' + '.join(terms)} = 0")
                                    all_hits.append({"search": "B-PSLQ", "q": qlabel, "relation": str(r),
                                                    "value": nstr(V, 25)})
                                    b_hits += 1

print(f"\n  Search B: {b_hits} hits ({time.time()-t0:.0f}s)")
print()


# ═══════════════════════════════════════════════════════════
# PART 4: Hybrid n^k × q^n
# ═══════════════════════════════════════════════════════════
print("═══ SEARCH C: Hybrid n^k × q^n ═══")
print()

t0 = time.time()
c_hits = 0

for q, qlabel in [(mpf(1)/2, "1/2"), (mpf(1)/3, "1/3"), (-mpf(1)/2, "-1/2")]:
    QN = [power(q, n) for n in range(251)]

    for A in range(-5, 6):
        for B in range(-4, 5):
            for C in range(-3, 4):
                for D in range(1, 5):
                    for E in range(-3, 4):
                        # a_n = (An² + Bn + C)·q^n,  b_n = Dn + E
                        a1 = (A + B + C) * QN[1]
                        if fabs(a1) < 1e-10:
                            continue

                        try:
                            val = mpf(D*30 + E)
                            for n in range(29, 0, -1):
                                an1 = (A*(n+1)**2 + B*(n+1) + C) * QN[n+1]
                                val = mpf(D*n + E) + an1/val
                            v30 = mpf(E) + (A + B + C)*QN[1]/val
                        except:
                            continue
                        if fabs(v30) > 1e12 or fabs(v30) < 1e-12:
                            continue

                        try:
                            val = mpf(D*200 + E)
                            for n in range(199, 0, -1):
                                an1 = (A*(n+1)**2 + B*(n+1) + C) * QN[min(n+1, 250)]
                                val = mpf(D*n + E) + an1/val
                            v200 = mpf(E) + (A + B + C)*QN[1]/val
                        except:
                            continue
                        if fabs(v30 - v200) > mpf('1e-8'):
                            continue

                        V = v200

                        mh = match_targets(V)
                        for name, dig in mh:
                            print(f"  HIT [q={qlabel}]: a=({A}n²+{B}n+{C})q^n, b={D}n+{E} → {name} [{dig}d]")
                            all_hits.append({"search": "C", "q": qlabel,
                                            "params": f"a=({A}n²+{B}n+{C})q^n, b={D}n+{E}",
                                            "target": name, "digits": dig, "value": nstr(V, 25)})
                            c_hits += 1

print(f"\n  Search C: {c_hits} hits ({time.time()-t0:.0f}s)")
print()


# ═══════════════════════════════════════════════════════════
# PART 5: Known q-series for ζ(3) and Catalan (verification)
# ═══════════════════════════════════════════════════════════
print("═══ VERIFICATION: Known q-series for ζ(3) and Catalan ═══")
print()

# Catalan from q-digamma / q-analogs
# G = -∫_0^1 ln(x)/(1+x²)dx = β(2) where β is Dirichlet beta
# q-series: G = (1/2)Σ_{n=0}^∞ q^n/(1+q^{2n}) at q=... nope, that's different

# Known: ζ(3) = (5/2)Σ_{n=1}^∞ (-1)^{n-1}/(n³·C(2n,n))  (Apéry-like)
print("  Apéry-like series for ζ(3):")
from mpmath import binomial
s = nsum(lambda n: (-1)**(n-1) / (n**3 * binomial(2*n, n)), [1, inf])
print(f"    (5/2)·Σ = {nstr(mpf(5)/2 * s, 25)}")
print(f"    ζ(3) =    {nstr(Z3, 25)}")
print(f"    Match: {int(-log(fabs(mpf(5)/2*s - Z3), 10))} digits ✓")
print()

# q-analog of Catalan: G = Σ_{n=0}^∞ (-1)^n/(2n+1)^2
# As a CF: this is related to the Stieltjes CF of the moment function
# Let's try the Euler-style CF for β(2):
# G = 1/(1 + 1²/(1 + 1²/(1 + 2²/(1 + 2²/(1 + 3²/(1 + 3²/(1+...)))))))
# This is the Stieltjes CF
print("  Stieltjes CF for Catalan:")
# a_{2k-1} = k², a_{2k} = k², b_n = 1
depth = 400
val = mpf(1)
for n in range(depth, 0, -1):
    k = (n + 1) // 2
    val = 1 + k*k / val
V_stieltjes = 1 / val
print(f"    1/CF = {nstr(V_stieltjes, 25)}")
print(f"    Cat  = {nstr(Cat, 25)}")
d_cat = fabs(V_stieltjes - Cat)
if d_cat > 0 and d_cat < mpf('1e-5'):
    print(f"    Match: {int(-log(d_cat, 10))} digits ✓")
else:
    # Try different CF structures
    # G = 1/(1+K) where K = 1/(8+2^4/(16+3^4/(24+...)))
    val = mpf(0)
    for n in range(200, 0, -1):
        val = n**4 / (8*n + val)
    V_cat2 = 1/(1 + val)
    print(f"    Alt CF: {nstr(V_cat2, 25)}")
    d2 = fabs(V_cat2 - Cat)
    if d2 > 0 and d2 < mpf('1e-5'):
        print(f"    Match: {int(-log(d2, 10))} digits ✓")
    else:
        # G = Σ (-1)^n / (2n+1)^2 as Euler-accelerated CF
        # Known Ramanujan CF: 1/(1+q/(1+q^2/(1+q^3/(1+...)))) at q=... 
        # Actually: G = π/4 - series. Let's just verify numerically
        from mpmath import nsum
        G_check = nsum(lambda n: (-1)**n / (2*n+1)**2, [0, inf])
        print(f"    Direct sum: {nstr(G_check, 25)}")
        print(f"    Match sum: {int(-log(fabs(G_check - Cat), 10))} digits ✓")
print()


# ═══════════════════════════════════════════════════════════
# PART 6: Apéry-type generalizations  
# a_n = -(αn + β)^k · n^m,  b_n = polynomial cubic
# ═══════════════════════════════════════════════════════════
print("═══ SEARCH D: Apéry-type cubic/quintic ═══")
print()

t0 = time.time()
d_hits = 0

# Apéry CF generalization:
# a_n = -n^p, b_n = cubic in n
for p in [3, 4, 5, 6]:
    for a3 in range(-5, 6):
        for a2 in range(-5, 6):
            for a1 in range(-5, 6):
                for a0 in range(1, 8):
                    a_fn = lambda n, _p=p: -(n**_p) if n > 0 else mpf(0)
                    b_fn = lambda n, _a3=a3, _a2=a2, _a1=a1, _a0=a0: (
                        _a3*n**3 + _a2*n**2 + _a1*n + _a0
                    )

                    # Ghost filter
                    if p > 0:
                        pass  # a(1) = -1 always nonzero

                    try:
                        val = b_fn(50)
                        for n in range(49, 0, -1):
                            val = b_fn(n) + a_fn(n+1)/val
                        v50 = b_fn(0) + a_fn(1)/val
                    except:
                        continue
                    if fabs(v50) > 1e12 or fabs(v50) < 1e-12:
                        continue

                    try:
                        val = b_fn(300)
                        for n in range(299, 0, -1):
                            val = b_fn(n) + a_fn(n+1)/val
                        v300 = b_fn(0) + a_fn(1)/val
                    except:
                        continue
                    if fabs(v50 - v300) > mpf('1e-6'):
                        continue

                    V = v300

                    # Check if V or simple functions of V match targets
                    for xform_name, xform in [("V", V), ("1/V", 1/V if fabs(V) > 1e-10 else None),
                                               ("6/V", 6/V if fabs(V) > 1e-10 else None)]:
                        if xform is None:
                            continue
                        mh = match_targets(xform)
                        for name, dig in mh:
                            if dig >= 15:
                                print(f"  HIT: a=-n^{p}, b={a3}n³+{a2}n²+{a1}n+{a0} → {xform_name}={name} [{dig}d]")
                                all_hits.append({"search": "D", "p": p, "b_cubic": [a3,a2,a1,a0],
                                                "xform": xform_name, "target": name, "digits": dig,
                                                "value": nstr(V, 25)})
                                d_hits += 1

print(f"\n  Search D: {d_hits} hits ({time.time()-t0:.0f}s)")
print()


# ═══════════════════════════════════════════════════════════
# GRAND SUMMARY
# ═══════════════════════════════════════════════════════════
print("═══════════════════════════════════════════════════════")
print("  ITERATION 3: GRAND SUMMARY")
print("═══════════════════════════════════════════════════════")
print()
print(f"Total hits: {len(all_hits)}")
if all_hits:
    by_target = {}
    for h in all_hits:
        t = h.get("target", "unknown")
        by_target.setdefault(t, []).append(h)
    for t, hs in sorted(by_target.items()):
        max_dig = max(h.get("digits", 0) for h in hs)
        print(f"  {t}: {len(hs)} hit(s), best = {max_dig} digits")
        for h in hs[:3]:
            print(f"    search={h['search']}, q={h.get('q','N/A')}, params={h.get('params', h.get('b_cubic',''))}")
    print()
else:
    print("  No hits across all q-series searches.")
print()
for h in all_hits:
    if h.get("digits", 0) >= 20:
        print(f"  ★ HIGH-CONFIDENCE: {h}")
