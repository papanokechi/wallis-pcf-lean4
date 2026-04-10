"""
Iteration 3: q-Series & q-Continued Fraction Search Engine
═══════════════════════════════════════════════════════════

Breaks past the π-rational barrier discovered in Iteration 2.
Targets: ζ(3), Catalan G, Γ(1/3), Γ(1/4), and L-function values.

Key insight (Iter 2 boundary): polynomial GCFs → Gauss ₂F₁ → Q(π) only.
q-CFs → Rogers-Ramanujan world → higher transcendentals.
"""

from mpmath import (mp, mpf, mpc, nstr, fabs, log, pi, sqrt, euler,
                    catalan, zeta, gamma as mpgamma, pslq, exp, log as mplog,
                    hyp2f1, polylog, inf, nprod, nsum, power, fac)
import itertools
import time

mp.dps = 60

# ═══════════════════════════════════════════════════════════
# SECTION 0: Core q-arithmetic
# ═══════════════════════════════════════════════════════════

def qpoch(a, q, n):
    """q-Pochhammer symbol (a;q)_n = prod_{k=0}^{n-1} (1 - a*q^k)"""
    if n <= 0:
        return mpf(1)
    result = mpf(1)
    ak = a
    for k in range(n):
        result *= (1 - ak)
        ak *= q
    return result

def qpoch_inf(a, q, terms=300):
    """(a;q)_∞ = prod_{k=0}^{∞} (1 - a*q^k), for |q|<1"""
    result = mpf(1)
    ak = a
    for k in range(terms):
        factor = 1 - ak
        result *= factor
        if fabs(ak) < mpf('1e-80'):
            break
        ak *= q
    return result

def gcf_bw(a_fn, b_fn, depth=200):
    """Standard backward-recurrence GCF evaluation"""
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        an1 = a_fn(n + 1)
        val = b_fn(n) + an1 / val
    return b_fn(0) + a_fn(1) / val

def check_conv(a_fn, b_fn, depth_lo=30, depth_hi=200):
    """Check convergence + non-degeneracy (ghost filter)"""
    if fabs(a_fn(1)) < 1e-10:
        return None
    try:
        v1 = gcf_bw(a_fn, b_fn, depth_lo)
        v2 = gcf_bw(a_fn, b_fn, depth_hi)
        if fabs(v2) > 1e15 or fabs(v2) < 1e-15:
            return None
        if fabs(v1 - v2) < mpf('1e-8'):
            return v2
    except (ZeroDivisionError, ValueError, OverflowError):
        pass
    return None


# ═══════════════════════════════════════════════════════════
# SECTION 1: Target constants
# ═══════════════════════════════════════════════════════════

Z3 = zeta(3)                        # Apéry's constant = 1.20206...
Cat = catalan                        # Catalan's G = 0.91597...
G13 = mpgamma(mpf(1)/3)             # Γ(1/3) = 2.67894...
G14 = mpgamma(mpf(1)/4)             # Γ(1/4) = 3.62561...
Ln2 = mplog(2)
Eu = euler                           # Euler-Mascheroni γ

targets = {
    "ζ(3)":       Z3,
    "Catalan":    Cat,
    "Γ(1/3)":    G13,
    "Γ(1/4)":    G14,
    "ln2":        Ln2,
    "1/ζ(3)":    1/Z3,
    "1/Cat":      1/Cat,
    "ζ(3)/π²":   Z3/pi**2,
    "Cat/π":      Cat/pi,
    "π²/ζ(3)":   pi**2/Z3,
    "Γ(1/4)²/(4π)": G14**2/(4*pi),   # = AGM(1,√2) related
    "ζ(3)/6":     Z3/6,               # appears in Apéry's proof
}

# Extended PSLQ basis
pslq_basis = [mpf(1), pi, pi**2, Z3, Cat, G13, G14, Ln2, Eu,
              sqrt(mpf(2)), sqrt(mpf(3)), mplog(mpf(3))]

print("═══════════════════════════════════════════════════════")
print("  ITERATION 3: q-SERIES PARAMETER SPACE")
print("═══════════════════════════════════════════════════════")
print()

# ═══════════════════════════════════════════════════════════
# SEARCH A: q-Polynomial GCFs
# a_n = c0 + c1*q^n + c2*q^{2n}, b_n = d0 + d1*q^n
# ═══════════════════════════════════════════════════════════

print("═══ SEARCH A: q-Polynomial GCFs ═══")
print()

q_values = [mpf(1)/2, mpf(1)/3, mpf(1)/4, mpf(2)/3,
            -mpf(1)/2, -mpf(1)/3,
            exp(-pi), exp(-2*pi), exp(-pi/2)]

q_labels = ["1/2", "1/3", "1/4", "2/3",
            "-1/2", "-1/3",
            "e^{-π}", "e^{-2π}", "e^{-π/2}"]

hits_a = []
total_searched = 0
t0 = time.time()

for qi, q in enumerate(q_values):
    qlabel = q_labels[qi]
    q_hits = 0

    # Coefficients for a_n = c0 + c1*q^n + c2*q^{2n}
    # and b_n = d0 + d1*q^n
    c_range = range(-5, 6)
    d_range = range(-5, 6)

    for c0 in c_range:
        for c1 in c_range:
            for c2 in [-3, -2, -1, 0, 1, 2, 3]:
                for d0 in range(1, 8):       # b_n should be positive-ish
                    for d1 in range(-5, 6):
                        qn_cache = [power(q, n) for n in range(250)]
                        q2n_cache = [power(q, 2*n) for n in range(250)]

                        a_fn = lambda n, _c0=c0, _c1=c1, _c2=c2: (
                            _c0 + _c1 * qn_cache[n] + _c2 * q2n_cache[n]
                        )
                        b_fn = lambda n, _d0=d0, _d1=d1: (
                            _d0 + _d1 * qn_cache[n]
                        )

                        V = check_conv(a_fn, b_fn)
                        if V is None:
                            continue
                        total_searched += 1

                        # Check against targets
                        for name, tgt in targets.items():
                            for k in [1, 2, 3, 4, mpf(1)/2, mpf(1)/3, mpf(1)/4]:
                                d = fabs(V - k * tgt)
                                if 0 < d < mpf('1e-20'):
                                    dig = int(-log(d, 10))
                                    if dig >= 15:
                                        kstr = "" if k == 1 else f"{k}*"
                                        msg = (f"  HIT [q={qlabel}]: a={c0}+{c1}q^n+{c2}q^{{2n}}, "
                                               f"b={d0}+{d1}q^n → {kstr}{name} [{dig}d]")
                                        print(msg)
                                        hits_a.append({
                                            "q": qlabel, "c0": c0, "c1": c1, "c2": c2,
                                            "d0": d0, "d1": d1, "target": name,
                                            "k": float(k), "digits": dig,
                                            "value": nstr(V, 25)
                                        })
                                        q_hits += 1

                        # PSLQ for unrecognized values
                        if total_searched % 500 == 0:
                            basis = [V] + pslq_basis
                            r = pslq(basis, maxcoeff=500)
                            if r is not None and r[0] != 0 and abs(r[0]) <= 50:
                                nonzero = sum(1 for x in r if x != 0)
                                if nonzero >= 3:
                                    check = sum(r[i]*basis[i] for i in range(len(basis)))
                                    if fabs(check) < mpf('1e-30'):
                                        print(f"  PSLQ [q={qlabel}]: a={c0}+{c1}q^n+{c2}q^{{2n}}, b={d0}+{d1}q^n")
                                        print(f"    V = {nstr(V, 20)}")
                                        terms = []
                                        labels = ["V","1","π","π²","ζ(3)","Cat","Γ(1/3)","Γ(1/4)",
                                                  "ln2","γ","√2","√3","ln3"]
                                        for i, coeff in enumerate(r):
                                            if coeff != 0:
                                                terms.append(f"{coeff}·{labels[i]}")
                                        print(f"    {' + '.join(terms)} = 0")
                                        hits_a.append({
                                            "q": qlabel, "c0": c0, "c1": c1, "c2": c2,
                                            "d0": d0, "d1": d1, "target": "PSLQ",
                                            "relation": str(r), "value": nstr(V, 25)
                                        })

    if q_hits == 0:
        print(f"  q={qlabel}: no hits")

elapsed_a = time.time() - t0
print(f"\n  Search A: {total_searched} convergent q-GCFs in {elapsed_a:.1f}s")
print(f"  Hits: {len(hits_a)}")
print()


# ═══════════════════════════════════════════════════════════
# SEARCH B: q-Pochhammer GCFs (Rogers-Ramanujan type)
# a_n = (1-q^n)·(1-α·q^n), b_n = 1 + β·q^n
# ═══════════════════════════════════════════════════════════

print("═══ SEARCH B: q-Pochhammer GCFs (Rogers-Ramanujan type) ═══")
print()

hits_b = []
total_b = 0
t0 = time.time()

# Focus on q with |q| < 1
for qi, q in enumerate(q_values[:6]):  # skip the exp(-pi) ones for speed
    qlabel = q_labels[qi]

    for alpha_num in range(-4, 5):
        for alpha_den in [1, 2, 3]:
            alpha = mpf(alpha_num) / alpha_den
            for beta_num in range(-4, 5):
                for beta_den in [1, 2, 3]:
                    beta = mpf(beta_num) / beta_den
                    for gamma_num in range(0, 4):
                        for gamma_den in [1, 2]:
                            gam = mpf(gamma_num) / gamma_den

                            qn_cache = [power(q, n) for n in range(250)]

                            # a_n = (1 - q^n)(1 - α·q^n) + γ
                            a_fn = lambda n, _a=alpha, _g=gam: (
                                (1 - qn_cache[n]) * (1 - _a * qn_cache[n]) + _g
                            )
                            # b_n = 1 + β·q^n
                            b_fn = lambda n, _b=beta: 1 + _b * qn_cache[n]

                            V = check_conv(a_fn, b_fn)
                            if V is None:
                                continue
                            total_b += 1

                            for name, tgt in targets.items():
                                for k in [1, 2, 3, mpf(1)/2, mpf(1)/3]:
                                    d = fabs(V - k * tgt)
                                    if 0 < d < mpf('1e-20'):
                                        dig = int(-log(d, 10))
                                        if dig >= 15:
                                            kstr = "" if k == 1 else f"{k}*"
                                            print(f"  HIT [q={qlabel}]: α={alpha_num}/{alpha_den}, "
                                                  f"β={beta_num}/{beta_den}, γ={gamma_num}/{gamma_den} "
                                                  f"→ {kstr}{name} [{dig}d]")
                                            hits_b.append({
                                                "q": qlabel, "alpha": f"{alpha_num}/{alpha_den}",
                                                "beta": f"{beta_num}/{beta_den}",
                                                "gamma": f"{gamma_num}/{gamma_den}",
                                                "target": name, "digits": dig,
                                                "value": nstr(V, 25)
                                            })

elapsed_b = time.time() - t0
print(f"\n  Search B: {total_b} convergent q-Pochhammer GCFs in {elapsed_b:.1f}s")
print(f"  Hits: {len(hits_b)}")
print()


# ═══════════════════════════════════════════════════════════
# SEARCH C: Well-Poised q-series CF (Apéry-style)
# The Apéry proof uses: ζ(3) = 5/2 · Σ (-1)^n (2n+1)! / (n!)^3 · ...
# We target q-analogs of this structure.
# a_n = n^2 * (1-q^n)^2 / (something), etc.
# ═══════════════════════════════════════════════════════════

print("═══ SEARCH C: Apéry-window GCFs ═══")
print()

hits_c = []
total_c = 0
t0 = time.time()

# Known: Apéry's CF for ζ(3): b_0=6, a_n = -n^6, b_n = (2n+1)(17n^2+17n+5)
# = 34n^3 + 51n^2 + 27n + 5
# Let's verify this first and then explore q-deformations

print("  Verifying Apéry CF for ζ(3)...")
a_apery = lambda n: -(n**6)
b_apery = lambda n: 34*n**3 + 51*n**2 + 27*n + 5 if n > 0 else mpf(6)
V_apery = check_conv(a_apery, b_apery, depth_lo=50, depth_hi=300)
if V_apery is not None:
    # Apéry CF converges to 6/ζ(3) ... or some variant
    d = fabs(V_apery - 6/Z3)
    if d < mpf('1e-10'):
        print(f"    6/ζ(3) variant: {int(-log(d, 10))} digits ✓")
    else:
        # Try other forms
        d2 = fabs(1/V_apery - Z3/6)
        print(f"    V = {nstr(V_apery, 25)}")
        print(f"    6/ζ(3) = {nstr(6/Z3, 25)}")
        # Actually Apéry CF: 6 - 1^6/(5*17+...) = ...
        # The CF is: ζ(3) = 6/(5 - 1^6/(117 - ...))
        # So V = 5 - 1^6/(117 - 2^6/(535 - ...)) and ζ(3) = 6/V
        # Let me recompute properly
        def b_ap(n):
            if n == 0: return mpf(5)
            return 34*n**3 + 51*n**2 + 27*n + 5
        a_ap = lambda n: -(n**6) if n >= 1 else mpf(0)
        V2 = gcf_bw(a_ap, b_ap, 300)
        d3 = fabs(6/V2 - Z3)
        if d3 < mpf('1e-10'):
            dig3 = int(-log(d3, 10))
            print(f"    ζ(3) = 6/CF: verified to {dig3} digits ✓")
        else:
            print(f"    V2 = {nstr(V2, 25)}, 6/V2 = {nstr(6/V2, 25)}")
            print(f"    ζ(3) = {nstr(Z3, 25)}")
else:
    print("    Apéry CF did not converge — checking manually...")
    V2 = gcf_bw(lambda n: -(n**6) if n >= 1 else mpf(0),
                lambda n: (34*n**3 + 51*n**2 + 27*n + 5) if n > 0 else mpf(5),
                300)
    d3 = fabs(6/V2 - Z3)
    if d3 > 0 and d3 < mpf('1e-10'):
        print(f"    ζ(3) = 6/CF: verified to {int(-log(d3, 10))} digits ✓")
    else:
        print(f"    V2 = {nstr(V2, 25)}")
        print(f"    6/V2 = {nstr(6/V2, 25)}")
        print(f"    ζ(3) = {nstr(Z3, 25)}")

print()

# Now: q-deform the Apéry CF
# Replace n^k with [n]_q^k where [n]_q = (1-q^n)/(1-q)
print("  q-Deformed Apéry CFs...")
for qi, q in enumerate([mpf(1)/2, mpf(1)/3, exp(-pi)]):
    qlabel = ["1/2", "1/3", "e^{-π}"][qi]
    qm1 = 1 - q
    qn_num = lambda n: (1 - power(q, n)) / qm1  # [n]_q

    for scale_a in [1, 2, 4, 6]:
        for scale_b in [1, 5, 17, 34]:
            a_fn = lambda n, s=scale_a: -s * (qn_num(n))**6 if n >= 1 else mpf(0)
            b_fn = lambda n, s=scale_b: (
                s * (qn_num(n))**3 + 51*(qn_num(n))**2 + 27*qn_num(n) + 5
                if n > 0 else mpf(5)
            )
            V = check_conv(a_fn, b_fn, depth_lo=50, depth_hi=200)
            if V is None:
                continue
            total_c += 1

            for name, tgt in targets.items():
                for k in [1, 6, mpf(1)/6, 5, mpf(1)/5]:
                    kv = k * tgt
                    d = fabs(V - kv)
                    if 0 < d < mpf('1e-15'):
                        dig = int(-log(d, 10))
                        if dig >= 12:
                            print(f"    HIT [q={qlabel}]: scale_a={scale_a}, scale_b={scale_b} → {k}*{name} [{dig}d]")
                            hits_c.append({"q": qlabel, "scale_a": scale_a, "scale_b": scale_b,
                                          "target": name, "digits": dig})

elapsed_c = time.time() - t0
print(f"\n  Search C: {total_c} q-Apéry GCFs in {elapsed_c:.1f}s")
print(f"  Hits: {len(hits_c)}")
print()


# ═══════════════════════════════════════════════════════════
# SEARCH D: Generalized q-CFs with (q;q)_n Pochhammer factors
# a_n = (q;q)_n^2 * q^n, b_n = 1  (Rogers-Ramanujan type)
# ═══════════════════════════════════════════════════════════

print("═══ SEARCH D: Pochhammer-factorial q-CFs ═══")
print()

hits_d = []
total_d = 0
t0 = time.time()

for qi, q in enumerate([mpf(1)/2, mpf(1)/3, mpf(1)/4, -mpf(1)/2, mpf(2)/3]):
    qlabel = ["1/2", "1/3", "1/4", "-1/2", "2/3"][qi]

    # Precompute (q;q)_n and (q^k;q)_n for various k
    max_n = 250
    qq_n = [qpoch(q, q, n) for n in range(max_n + 1)]

    for a_pow in [1, 2, 3]:          # power of (q;q)_n
        for a_qpow in [0, 1, 2]:     # extra q^{a_qpow * n}
            for a_sign in [1, -1]:
                for b_const in [1, 2, 3]:
                    for b_qcoeff in range(-3, 4):

                        qn_cache = [power(q, n) for n in range(max_n + 1)]

                        a_fn = lambda n, _ap=a_pow, _aq=a_qpow, _as=a_sign: (
                            _as * qq_n[n]**_ap * power(q, _aq * n)
                        )
                        b_fn = lambda n, _bc=b_const, _bq=b_qcoeff: (
                            _bc + _bq * qn_cache[n]
                        )

                        V = check_conv(a_fn, b_fn)
                        if V is None:
                            continue
                        total_d += 1

                        for name, tgt in targets.items():
                            for k in [1, 2, 3, 4, 5, 6, mpf(1)/2, mpf(1)/3, mpf(1)/4, mpf(1)/5, mpf(1)/6]:
                                d = fabs(V - k * tgt)
                                if 0 < d < mpf('1e-15'):
                                    dig = int(-log(d, 10))
                                    if dig >= 12:
                                        kstr = "" if k == 1 else f"{k}*"
                                        print(f"  HIT [q={qlabel}]: (q;q)_n^{a_pow}·q^{{{a_qpow}n}}, "
                                              f"sign={a_sign}, b={b_const}+{b_qcoeff}q^n → "
                                              f"{kstr}{name} [{dig}d]")
                                        hits_d.append({
                                            "q": qlabel, "a_pow": a_pow, "a_qpow": a_qpow,
                                            "a_sign": a_sign, "b_const": b_const,
                                            "b_qcoeff": b_qcoeff,
                                            "target": name, "digits": dig,
                                            "value": nstr(V, 25)
                                        })

elapsed_d = time.time() - t0
print(f"\n  Search D: {total_d} Pochhammer-factorial q-CFs in {elapsed_d:.1f}s")
print(f"  Hits: {len(hits_d)}")
print()


# ═══════════════════════════════════════════════════════════
# SEARCH E: Hybrid polynomial × q^n (mixed regime)
# a_n = An^2 · q^n,  b_n = Bn + C
# This interpolates between polynomial (iter 1-2) and pure q (iter 3)
# ═══════════════════════════════════════════════════════════

print("═══ SEARCH E: Hybrid polynomial × q^n GCFs ═══")
print()

hits_e = []
total_e = 0
t0 = time.time()

for qi, q in enumerate([mpf(1)/2, mpf(1)/3, -mpf(1)/2, mpf(2)/3]):
    qlabel = ["1/2", "1/3", "-1/2", "2/3"][qi]

    qn_cache = [power(q, n) for n in range(250)]

    for A in range(-5, 6):
        for B in range(-3, 4):
            for C in range(-3, 4):
                for D in range(1, 6):
                    for E in range(-3, 4):
                        # a_n = (An^2 + Bn + C) * q^n
                        a_fn = lambda n, _A=A, _B=B, _C=C: (
                            (_A * n * n + _B * n + _C) * qn_cache[n]
                        )
                        # b_n = Dn + E
                        b_fn = lambda n, _D=D, _E=E: _D * n + _E

                        V = check_conv(a_fn, b_fn)
                        if V is None:
                            continue
                        total_e += 1

                        for name, tgt in targets.items():
                            for k in [1, 2, 3, 4, mpf(1)/2, mpf(1)/3, mpf(1)/4]:
                                d = fabs(V - k * tgt)
                                if 0 < d < mpf('1e-20'):
                                    dig = int(-log(d, 10))
                                    if dig >= 15:
                                        kstr = "" if k == 1 else f"{k}*"
                                        print(f"  HIT [q={qlabel}]: a=({A}n²+{B}n+{C})q^n, "
                                              f"b={D}n+{E} → {kstr}{name} [{dig}d]")
                                        hits_e.append({
                                            "q": qlabel, "A": A, "B": B, "C": C,
                                            "D": D, "E": E, "target": name,
                                            "k": float(k), "digits": dig,
                                            "value": nstr(V, 25)
                                        })

elapsed_e = time.time() - t0
print(f"\n  Search E: {total_e} hybrid GCFs in {elapsed_e:.1f}s")
print(f"  Hits: {len(hits_e)}")
print()


# ═══════════════════════════════════════════════════════════
# SEARCH F: Padé-Borel transformed divergent CFs
# For divergent a_n = (-1)^n * n! * P(n), apply Borel sum
# ═══════════════════════════════════════════════════════════

print("═══ SEARCH F: Padé-Borel Divergence Transformer ═══")
print()

hits_f = []
t0 = time.time()

def borel_pade_gcf(a_fn, b_fn, N=30):
    """
    Given a divergent GCF, compute partial numerators p_n/q_n,
    then apply [N/N] Padé approximant to the Borel transform.
    """
    # Compute convergents h_n/k_n
    h_prev, h_curr = mpf(1), b_fn(0)
    k_prev, k_curr = mpf(0), mpf(1)
    convergents = [h_curr / k_curr]

    for n in range(1, 2 * N + 5):
        an = a_fn(n)
        bn = b_fn(n)
        h_new = bn * h_curr + an * h_prev
        k_new = bn * k_curr + an * k_prev
        h_prev, h_curr = h_curr, h_new
        k_prev, k_curr = k_curr, k_new
        if fabs(k_curr) > 1e-50:
            convergents.append(h_curr / k_curr)
        else:
            convergents.append(mpf(0))

    if len(convergents) < 4:
        return None

    # Euler transform to accelerate convergence of alternating partial sums
    # Richardson extrapolation using the convergent sequence
    n_terms = min(len(convergents), 2 * N)
    terms = convergents[:n_terms]

    # Aitken Δ² acceleration
    accelerated = []
    for i in range(len(terms) - 2):
        s0, s1, s2 = terms[i], terms[i+1], terms[i+2]
        denom = s2 - 2*s1 + s0
        if fabs(denom) > 1e-50:
            accelerated.append(s0 - (s1 - s0)**2 / denom)

    if not accelerated:
        return None

    # Take the last accelerated value
    return accelerated[-1]

# Test: factorial-divergent GCFs
print("  Testing factorial-divergent GCFs with Padé acceleration...")
for sign in [1, -1]:
    for alpha in [1, 2, 3, 4, 5]:
        for beta in range(-3, 4):
            for b_slope in [1, 2, 3, 4]:
                for b_const in range(-2, 4):
                    a_fn = lambda n, s=sign, a=alpha, b=beta: s * fac(n) * (a*n + b)
                    b_fn = lambda n, m=b_slope, c=b_const: m*n + c

                    V = borel_pade_gcf(a_fn, b_fn, N=20)
                    if V is None or fabs(V) > 1e10 or fabs(V) < 1e-10:
                        continue

                    for name, tgt in targets.items():
                        for k in [1, 2, 3, mpf(1)/2, mpf(1)/3]:
                            d = fabs(V - k * tgt)
                            if 0 < d < mpf('1e-8'):
                                dig = int(-log(d, 10))
                                if dig >= 6:
                                    kstr = "" if k == 1 else f"{k}*"
                                    print(f"  HIT (Padé): sign={sign}, α={alpha}, β={beta}, "
                                          f"b={b_slope}n+{b_const} → {kstr}{name} [{dig}d]")
                                    hits_f.append({
                                        "sign": sign, "alpha": alpha, "beta": beta,
                                        "b_slope": b_slope, "b_const": b_const,
                                        "target": name, "digits": dig,
                                        "value": nstr(V, 20)
                                    })

elapsed_f = time.time() - t0
print(f"\n  Search F: Padé-Borel in {elapsed_f:.1f}s")
print(f"  Hits: {len(hits_f)}")
print()


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════

print("═══════════════════════════════════════════════════════")
print("  ITERATION 3: COMPLETE SUMMARY")
print("═══════════════════════════════════════════════════════")
print()

all_hits = hits_a + hits_b + hits_c + hits_d + hits_e + hits_f
print(f"Total searches: A={total_searched}, B={total_b}, C={total_c}, D={total_d}, E={total_e}")
print(f"Total hits: A={len(hits_a)}, B={len(hits_b)}, C={len(hits_c)}, "
      f"D={len(hits_d)}, E={len(hits_e)}, F={len(hits_f)}")
print(f"Grand total: {len(all_hits)} hits")
print()

if all_hits:
    # Categorize hits by target
    by_target = {}
    for h in all_hits:
        t = h.get("target", "unknown")
        by_target.setdefault(t, []).append(h)
    for t, hs in sorted(by_target.items()):
        max_dig = max(h.get("digits", 0) for h in hs)
        print(f"  {t}: {len(hs)} hit(s), best {max_dig} digits")
        for h in hs[:3]:  # show top 3
            print(f"    {h}")
    print()
else:
    print("  No hits in q-series parameter space.")
    print()
    print("  INTERPRETATION:")
    print("  ζ(3) and Catalan may require:")
    print("  (a) Very-well-poised ₈φ₇ q-series (not reducible to 2-term CFs)")
    print("  (b) Matrix-valued or multi-dimensional CFs")
    print("  (c) Specific modular q-values not in our grid")
    print("  (d) Non-polynomial q-coefficient functions")
