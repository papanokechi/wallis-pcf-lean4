#!/usr/bin/env python3
"""
Targeted Catalan's constant (G) search using approaches that bypass
the polynomial-GCF barrier proven in _iter6_catalan_barrier.py.

Strategy:
  1. Non-polynomial sequences: factorial, Pochhammer, binomial-weighted a(n)/b(n)
  2. ₃F₂ hypergeometric families (Zudilin-type)
  3. Known Catalan integral/series representations as CF seeds
  4. Wider PSLQ with mixed basis {G, π, ln2, π², γ, 1}
  5. Alternating-sign cubic/quartic templates

Key identity: G = β(2) = L(2, χ₋₄) = Σ (-1)^n/(2n+1)²
             G = Im[Li₂(i)] = (1/2)∫₀¹ K(k)dk  (elliptic integral avg)
"""

import itertools, json, time, sys
from pathlib import Path
from datetime import datetime
from fractions import Fraction

import mpmath
from mpmath import mp, mpf, nstr, pi, log, sqrt, zeta, euler, catalan, gamma, pslq, e as E

SCAN_DPS = 40       # low precision for fast scanning
VERIFY_DPS = 120    # high precision for verification
mp.dps = SCAN_DPS
G = catalan  # 0.9159655941772190...

LOGFILE = Path("catalan_discoveries.jsonl")

def log_discovery(record):
    with LOGFILE.open('a') as f:
        f.write(json.dumps(record) + '\n')
    print(f"\n{'='*65}")
    print(f"  HIT: {record['description']}")
    print(f"  Value: {record['value'][:50]}")
    print(f"  Digits: {record.get('digits', '?')}")
    print(f"{'='*65}\n")


# ═══════════════════════════════════════════════════════════════════
# PSLQ matching against a rich basis
# ═══════════════════════════════════════════════════════════════════
def pslq_match(val, tol_digits=25):
    """Try PSLQ with multiple bases to identify val in terms of known constants."""
    bases = [
        ("basic", [val, G, mpf(1)]),
        ("pi",    [val, G, pi, mpf(1)]),
        ("log2",  [val, G, log(2), mpf(1)]),
        ("full",  [val, G, pi, log(2), pi**2, euler, mpf(1)]),
        ("ratG",  [val, G, G**2, mpf(1)]),
        ("piG",   [val, G, pi*G, pi, mpf(1)]),
    ]
    results = []
    for name, basis in bases:
        try:
            mp.dps = tol_digits + 30
            rel = pslq(basis, maxcoeff=1000, tol=mpf(10)**(-tol_digits))
            if rel and rel[0] != 0:
                residual = abs(sum(r*b for r, b in zip(rel, basis)))
                if residual < mpf(10)**(-tol_digits + 2):
                    results.append((name, rel, residual, basis))
        except Exception:
            pass
    mp.dps = SCAN_DPS
    return results


def describe_relation(name, rel, basis_names):
    """Format a PSLQ relation as human-readable string."""
    terms = []
    for coeff, bname in zip(rel, basis_names):
        if coeff == 0:
            continue
        if coeff == 1:
            terms.append(bname)
        elif coeff == -1:
            terms.append(f"-{bname}")
        else:
            terms.append(f"{coeff}*{bname}")
    return " + ".join(terms) + " = 0"


# ═══════════════════════════════════════════════════════════════════
# CF evaluation (standard polynomial)
# ═══════════════════════════════════════════════════════════════════
def eval_cf(a_func, b_func, depth=300):
    """Evaluate b(0) + a(1)/(b(1) + a(2)/(b(2) + ...)) bottom-up."""
    val = mpf(0)
    for n in range(depth, 0, -1):
        bn = b_func(n)
        an = a_func(n)
        denom = bn + val
        if abs(denom) < mpf(10)**(-mp.dps + 10):
            return None
        val = an / denom
    return b_func(0) + val


def is_interesting(val):
    """Filter NaN, inf, near-zero, huge."""
    if val is None:
        return False
    try:
        f = float(val)
        return abs(f) > 1e-8 and abs(f) < 1e6 and not (f != f)
    except:
        return False


def check_catalan(val, tol_digits=15):
    """Check if val is a simple rational multiple of G."""
    if not is_interesting(val):
        return None
    for p in range(1, 13):
        for q in range(1, 13):
            for sign in [1, -1]:
                target = sign * mpf(p) / q * G
                if abs(val - target) < mpf(10)**(-tol_digits):
                    label = f"{sign*p}/{q}*G" if (p != 1 or q != 1) else ("G" if sign == 1 else "-G")
                    digits = -int(mpmath.log10(max(abs(val - target), mpf(10)**(-mp.dps+5))))
                    return label, digits
            # Also try G/pi, G*pi, G+pi/4, etc.
            for const_name, const_val in [("pi", pi), ("ln2", log(2)), ("pi2", pi**2)]:
                target = sign * mpf(p) / q * G * const_val
                if abs(val - target) < mpf(10)**(-tol_digits):
                    label = f"{sign*p}/{q}*G*{const_name}"
                    digits = -int(mpmath.log10(max(abs(val - target), mpf(10)**(-mp.dps+5))))
                    return label, digits
                target = sign * mpf(p) / q * G / const_val
                if abs(val - target) < mpf(10)**(-tol_digits):
                    label = f"{sign*p}/{q}*G/{const_name}"
                    digits = -int(mpmath.log10(max(abs(val - target), mpf(10)**(-mp.dps+5))))
                    return label, digits
    return None


total_hits = 0
total_evaluated = 0

# ═══════════════════════════════════════════════════════════════════
# FAMILY 1: Zudilin-type ₃F₂ continued fractions
#   Known: ₃F₂(1,1,1; 3/2,3/2; z) is related to Catalan via z=1/4
#   Explore CFs that arise from contiguous relations of ₃F₂
# ═══════════════════════════════════════════════════════════════════
print("="*65)
print("FAMILY 1: ₃F₂ contiguous CFs near Catalan")
print("="*65)

# The ₃F₂ contiguous CFs have a(n) that are CUBIC or QUARTIC in n
# and b(n) that are QUADRATIC.  This bypasses the deg-2 barrier.

t0 = time.time()
fam1_hits = 0

# Template: a(n) = c3*n³ + c2*n² + c1*n + c0
#           b(n) = d2*n² + d1*n + d0
# Inspired by Apéry's CF for ζ(3): a(n) = -n⁶, b(n) = (2n+1)(17n²+17n+5)
# For Catalan, try cubic a(n) with quadratic b(n)

cubic_configs = [
    # (description, a_func, b_func)
    # Zudilin-inspired: alternating cubic
    ("n³ alt", lambda n: (-1)**n * n**3, lambda n: mpf(2*n+1)),
    ("-n³, 2n+1", lambda n: -n**3, lambda n: mpf(2*n+1)),
    ("-n³, 2n²+2n+1", lambda n: -n**3, lambda n: mpf(2*n**2+2*n+1)),
    # Apéry-style with different b(n)
    ("-n³, (2n-1)(n²+1)", lambda n: -n**3, lambda n: mpf((2*n-1)*(n**2+1)) if n > 0 else mpf(1)),
    # Catalan-tuned: odd denominators
    ("-n²(2n+1), (2n+1)²", lambda n: -n**2*(2*n+1), lambda n: mpf((2*n+1)**2)),
    ("-n²(2n-1), (2n+1)²", lambda n: -n**2*(2*n-1), lambda n: mpf((2*n+1)**2)),
    ("-n(2n+1)², (2n+1)(2n+3)", lambda n: -n*(2*n+1)**2, lambda n: mpf((2*n+1)*(2*n+3)) if n > 0 else mpf(1)),
    # Quartic / Apéry for L-values
    ("-n⁴, (2n+1)³", lambda n: -n**4, lambda n: mpf((2*n+1)**3)),
    ("-n⁴, n(2n+1)(2n-1)", lambda n: -n**4, lambda n: mpf(n*(2*n+1)*(2*n-1)) if n > 0 else mpf(1)),
    ("-n²(n+1)², (2n+1)³", lambda n: -n**2*(n+1)**2, lambda n: mpf((2*n+1)**3)),
    # Catalan from chi_-4 character: alternating with (2n+1) structure
    ("(-1)^n n², (2n+1)", lambda n: (-1)**n * n**2, lambda n: mpf(2*n+1)),
    ("(-1)^n n³, (2n+1)²", lambda n: (-1)**n * n**3, lambda n: mpf((2*n+1)**2)),
    ("(-1)^n n(n+1), (2n+1)²", lambda n: (-1)**n * n*(n+1), lambda n: mpf((2*n+1)**2)),
    ("(-1)^n(2n+1), 4n²+1", lambda n: (-1)**n * (2*n+1) if n > 0 else mpf(0), lambda n: mpf(4*n**2+1)),
]

for desc, a_func, b_func in cubic_configs:
    val = eval_cf(a_func, b_func, depth=500)
    total_evaluated += 1
    if not is_interesting(val):
        continue
    hit = check_catalan(val)
    if hit:
        label, digits = hit
        fam1_hits += 1
        total_hits += 1
        print(f"  ✓ {desc}: CF = {label} ({digits}d)")
        log_discovery({
            'family': '3F2_contiguous', 'description': f"{desc} -> {label}",
            'value': nstr(val, 40), 'digits': digits,
            'timestamp': datetime.now().isoformat()
        })
    else:
        # Try PSLQ
        matches = pslq_match(val, tol_digits=25)
        for mname, rel, res, basis in matches:
            if any(r != 0 for r in rel[1:]):  # non-trivial relation involving G
                if rel[1] != 0:  # G appears
                    fam1_hits += 1
                    total_hits += 1
                    basis_names = {
                        "basic": ["x", "G", "1"],
                        "pi": ["x", "G", "π", "1"],
                        "log2": ["x", "G", "ln2", "1"],
                        "full": ["x", "G", "π", "ln2", "π²", "γ", "1"],
                        "ratG": ["x", "G", "G²", "1"],
                        "piG": ["x", "G", "πG", "π", "1"],
                    }
                    rdesc = describe_relation(mname, rel, basis_names[mname])
                    print(f"  ✓ {desc} -> PSLQ[{mname}]: {rdesc}")
                    log_discovery({
                        'family': '3F2_contiguous', 'description': f"{desc} -> PSLQ: {rdesc}",
                        'value': nstr(val, 40), 'relation': list(rel),
                        'digits': -int(mpmath.log10(max(res, mpf(10)**(-100)))),
                        'timestamp': datetime.now().isoformat()
                    })
                    break

print(f"  Family 1: {fam1_hits} hits from {len(cubic_configs)} configs ({time.time()-t0:.1f}s)")


# ═══════════════════════════════════════════════════════════════════
# FAMILY 2: Parametric sweeps with Catalan-friendly structures
#   a(n) = α·n³ + β·n² + γ·n,  b(n) = (2n+1)·(δ·n² + ε·n + ζ)
#   Small integer coefficients, targeting (2n+1) denominators
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("FAMILY 2: Parametric cubic sweep with (2n+1) structure")
print("="*65)

t0 = time.time()
fam2_hits = 0
fam2_evaluated = 0

# Sweep: a(n) = c3*n^3 + c2*n^2 + c1*n (force a(0)=0 for regularity)
# b(n) = d2*n^2 + d1*n + d0 with d0 >= 1
R_a = 3   # coefficient range for a
R_b = 4   # coefficient range for b

for c3 in range(-R_a, R_a+1):
    for c2 in range(-R_a, R_a+1):
        for c1 in range(-R_a, R_a+1):
            if c3 == 0 and c2 == 0 and c1 == 0:
                continue
            a_func = lambda n, _c3=c3, _c2=c2, _c1=c1: mpf(_c3*n**3 + _c2*n**2 + _c1*n)
            for d2 in range(0, R_b+1):
                for d1 in range(0, R_b+1):
                    if d2 == 0 and d1 == 0:
                        continue  # skip constant b(n)
                    for d0 in range(1, R_b+1):
                        b_func = lambda n, _d2=d2, _d1=d1, _d0=d0: mpf(_d2*n**2 + _d1*n + _d0)
                        
                        val = eval_cf(a_func, b_func, depth=200)
                        fam2_evaluated += 1
                        total_evaluated += 1
                        
                        if not is_interesting(val):
                            continue
                        
                        hit = check_catalan(val, tol_digits=18)
                        if hit:
                            label, digits = hit
                            fam2_hits += 1
                            total_hits += 1
                            print(f"  ✓ a=[0,{c1},{c2},{c3}] b=[{d0},{d1},{d2}]: CF = {label} ({digits}d)")
                            log_discovery({
                                'family': 'cubic_sweep',
                                'a_coeffs': [0, c1, c2, c3],
                                'b_coeffs': [d0, d1, d2],
                                'description': f"a=[0,{c1},{c2},{c3}] b=[{d0},{d1},{d2}] -> {label}",
                                'value': nstr(val, 40), 'digits': digits,
                                'timestamp': datetime.now().isoformat()
                            })
                        
                        if fam2_evaluated % 5000 == 0:
                            elapsed = time.time() - t0
                            rate = fam2_evaluated / elapsed if elapsed > 0 else 0
                            print(f"  [{fam2_evaluated:,} evaluated | {fam2_hits} hits | {rate:.0f}/s]", flush=True)

print(f"  Family 2: {fam2_hits} hits from {fam2_evaluated:,} configs ({time.time()-t0:.1f}s)")


# ═══════════════════════════════════════════════════════════════════
# FAMILY 3: Non-polynomial sequences (factorial / Pochhammer / binomial)
#   These bypass the polynomial barrier entirely
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("FAMILY 3: Non-polynomial (factorial/binomial) CFs")
print("="*65)

t0 = time.time()
fam3_hits = 0

# Known CF-like representations involving Catalan:
# G = 1 - 1/2 * 1/(1 + 1/2 * 1²/(1 + 1/2 * 2²/(1 + ...)))  (not quite)
# 
# From Euler's CF for arctan:
# arctan(x) = x/(1 + (x)²/(3 + (2x)²/(5 + (3x)²/(7 + ...))))
# So G = Σ (-1)^n/(2n+1)² = ∫₀¹ arctan(t)/t dt
# is an integral of a CF, but we want a direct CF.
#
# Stieltjes-type CFs for L-functions:
# L(2, χ₋₄) as a CF with factorial-like numerators

# Template A: a(n) involves (2n-1)!!/(2n)!! type ratios
# Template B: a(n) = -n² * f(n) for various f
# Template C: Binomial coefficients C(2n,n) / 4^n weights

non_poly_configs = []

# Type 1: Pochhammer-weighted
# a(n) = -n² * (1/2)_n / (3/2)_n = -n²/(2n+1)
for k in range(1, 8):
    for j in range(1, 6):
        desc = f"-n²/(2n+{2*k-1}), j={j}"
        def a_f(n, _k=k): return -mpf(n)**2 / (2*n + 2*_k - 1) if n > 0 else mpf(0)
        def b_f(n, _j=j): return mpf(2*n + _j)
        non_poly_configs.append((desc, a_f, b_f))

# Type 2: Alternating with odd-denominator structure
for k in range(1, 6):
    for m in range(1, 5):
        desc = f"(-1)^n n^{m}/(2n+1)^{k}"
        def a_f(n, _m=m, _k=k): return (-1)**n * mpf(n)**_m / mpf(2*n+1)**_k if n > 0 else mpf(0)
        def b_f(n): return mpf(1)
        non_poly_configs.append((desc, a_f, b_f))

# Type 3: Binomial coefficient CFs
# C(2n,n)/4^n → 1/√(πn) asymptotically — slow convergence
for c in [1, 2, 3, 4]:
    for d in [1, 2, 3]:
        desc = f"-C(2n,n)/4^n * n^{c}, b=n+{d}"
        def a_f(n, _c=c): 
            if n <= 0: return mpf(0)
            return -mpmath.binomial(2*n, n) / mpf(4)**n * mpf(n)**_c
        def b_f(n, _d=d): return mpf(n + _d)
        non_poly_configs.append((desc, a_f, b_f))

# Type 4: Known convergent integrals as CFs
# G = π/2 · ln(2+√3)/2  ... no, that's not right
# G = Σ_{k=0}^∞ 1/((4k+1)² - 1/((4k+3)²)  — alternating with (2n+1)² terms
# As CF:  a(n) relates to 1/(2n+1)²

for alpha in [1, 2, 3, 4]:
    for beta in [1, 2, 3]:
        desc = f"-{alpha}/(2n+1)^2, b={beta}"
        def a_f(n, _a=alpha): return -mpf(_a) / (2*n+1)**2 if n > 0 else mpf(0)
        def b_f(n, _b=beta): return mpf(_b)
        non_poly_configs.append((desc, a_f, b_f))

# Type 5: Euler-type CFs for Dirichlet beta
# β(s) has CF expansions involving chi_{-4} character values
for r in range(1, 5):
    desc = f"chi4-CF r={r}: a=(-1)^n n^2, b=(2n+1)^{r}"
    def a_f(n, _r=r): return (-1)**n * mpf(n)**2 if n > 0 else mpf(0)
    def b_f(n, _r=r): return mpf(2*n+1)**_r
    non_poly_configs.append((desc, a_f, b_f))

for desc, a_func, b_func in non_poly_configs:
    val = eval_cf(a_func, b_func, depth=400)
    total_evaluated += 1
    if not is_interesting(val):
        continue
    
    hit = check_catalan(val)
    if hit:
        label, digits = hit
        fam3_hits += 1
        total_hits += 1
        print(f"  ✓ {desc}: CF = {label} ({digits}d)")
        log_discovery({
            'family': 'non_polynomial', 'description': f"{desc} -> {label}",
            'value': nstr(val, 40), 'digits': digits,
            'timestamp': datetime.now().isoformat()
        })
    else:
        # Quick PSLQ check (basic basis only for speed)
        try:
            rel = pslq([val, G, mpf(1)], maxcoeff=100, tol=mpf(10)**(-15))
            if rel and rel[0] != 0 and rel[1] != 0:
                residual = abs(rel[0]*val + rel[1]*G + rel[2])
                if residual < mpf(10)**(-13):
                    fam3_hits += 1
                    total_hits += 1
                    rdesc = f"{rel[0]}*x + {rel[1]}*G + {rel[2]} = 0"
                    print(f"  ✓ {desc} -> PSLQ: {rdesc}")
                    log_discovery({
                        'family': 'non_polynomial',
                        'description': f"{desc} -> {rdesc}",
                        'value': nstr(val, 40), 'relation': list(rel),
                        'timestamp': datetime.now().isoformat()
                    })
        except:
            pass

print(f"  Family 3: {fam3_hits} hits from {len(non_poly_configs)} configs ({time.time()-t0:.1f}s)")


# ═══════════════════════════════════════════════════════════════════
# FAMILY 4: Known Catalan CF representations (verification + variants)
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("FAMILY 4: Known Catalan representations & perturbations")
print("="*65)

t0 = time.time()
fam4_hits = 0

# (A) Ramanujan-type series: G = π/8 ln(2+√3) + 3/8 Σ ... 
# (B) Euler's representation: G = 1/(1+ 1²/(1+ 2²/(1+ 3²/(1+ ...))))
#     Actually: 4G/π = 1 + 1·2/(3 + 3·4/(5 + 5·6/(7 + ...)))
#     i.e., a(n) = n(n+1), b(n) = 2n+1, shifted
# (C) From Brouncker-Stieltjes theory:
#     G = 1/(2·(1 + 1²·2²/(4·5 + 3²·4²/(8·9 + ...))))

# Known: 4G/π from Brouncker-type
# a(n) = n(n+1), b(n) = 2n+1
def a_brouncker(n): return mpf(n) * (n+1) if n > 0 else mpf(0) 
def b_brouncker(n): return mpf(2*n + 1)
val = eval_cf(a_brouncker, b_brouncker, depth=500)
if is_interesting(val):
    hit = check_catalan(val)
    if hit:
        fam4_hits += 1; total_hits += 1
        print(f"  ✓ Brouncker a=n(n+1), b=2n+1: {hit[0]} ({hit[1]}d)")
    else:
        ratio = val / G if abs(G) > 0 else None
        print(f"  Brouncker CF = {nstr(val, 30)}")
        if ratio: print(f"    ratio to G = {nstr(ratio, 20)}")
        # Check 4G/π
        target = 4*G/pi
        if abs(val - target) < mpf(10)**(-15):
            fam4_hits += 1; total_hits += 1
            digits = -int(mpmath.log10(abs(val - target)))
            print(f"  ✓ Matches 4G/π! ({digits}d)")
            log_discovery({
                'family': 'known_reps', 'description': f"a=n(n+1), b=2n+1 -> 4G/π",
                'value': nstr(val, 40), 'digits': digits,
                'timestamp': datetime.now().isoformat()
            })

total_evaluated += 1

# Generalized: a(n) = n(n+k), b(n) = 2n+m for various k, m
for k in range(1, 8):
    for m in range(1, 8):
        a_f = lambda n, _k=k: mpf(n)*(n+_k) if n > 0 else mpf(0)
        b_f = lambda n, _m=m: mpf(2*n + _m)
        val = eval_cf(a_f, b_f, depth=400)
        total_evaluated += 1
        if not is_interesting(val):
            continue
        hit = check_catalan(val)
        if hit:
            label, digits = hit
            fam4_hits += 1; total_hits += 1
            print(f"  ✓ a=n(n+{k}), b=2n+{m}: {label} ({digits}d)")
            log_discovery({
                'family': 'known_reps',
                'description': f"a=n(n+{k}), b=2n+{m} -> {label}",
                'value': nstr(val, 40), 'digits': digits,
                'timestamp': datetime.now().isoformat()
            })

# (D) Perturbed known CFs: a(n) = n(n+1) + small correction
for eps_a in range(-3, 4):
    for eps_b in range(-2, 3):
        if eps_a == 0 and eps_b == 0:
            continue
        a_f = lambda n, _e=eps_a: mpf(n)*(n+1) + _e*n if n > 0 else mpf(0)
        b_f = lambda n, _e=eps_b: mpf(2*n + 1 + _e)
        val = eval_cf(a_f, b_f, depth=400)
        total_evaluated += 1
        if not is_interesting(val):
            continue
        hit = check_catalan(val)
        if hit:
            label, digits = hit
            fam4_hits += 1; total_hits += 1
            print(f"  ✓ a=n(n+1)+{eps_a}n, b=2n+{1+eps_b}: {label} ({digits}d)")
            log_discovery({
                'family': 'perturbed_known',
                'description': f"a=n(n+1)+{eps_a}n, b=2n+{1+eps_b} -> {label}",
                'value': nstr(val, 40), 'digits': digits,
                'timestamp': datetime.now().isoformat()
            })

print(f"  Family 4: {fam4_hits} hits from known reps + perturbations ({time.time()-t0:.1f}s)")


# ═══════════════════════════════════════════════════════════════════
# FAMILY 5: Quartic-quintic a(n) with specific Catalan structure
#   Zudilin showed that for ζ(3), a(n) = -n⁶ works.
#   For L(2, χ₋₄), try a(n) with character twist:
#   a(n) = (-1)^n · P(n) for polynomial P
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("FAMILY 5: Character-twisted polynomial CFs")
print("="*65)

t0 = time.time()
fam5_hits = 0
fam5_eval = 0

# a(n) = (-1)^n * (c2*n² + c1*n)  (forced a(0)=0)
# b(n) = d2*n² + d1*n + d0
R5 = 5
for c2 in range(-R5, R5+1):
    for c1 in range(-R5, R5+1):
        if c2 == 0 and c1 == 0:
            continue
        for d2 in range(0, 4):
            for d1 in range(0, 7):
                for d0 in range(1, 5):
                    if d2 == 0 and d1 == 0:
                        continue
                    a_f = lambda n, _c2=c2, _c1=c1: (-1)**n * mpf(_c2*n**2 + _c1*n) if n > 0 else mpf(0)
                    b_f = lambda n, _d2=d2, _d1=d1, _d0=d0: mpf(_d2*n**2 + _d1*n + _d0)
                    
                    val = eval_cf(a_f, b_f, depth=200)
                    fam5_eval += 1
                    total_evaluated += 1
                    
                    if not is_interesting(val):
                        continue
                    
                    hit = check_catalan(val, tol_digits=15)
                    if hit:
                        label, digits = hit
                        fam5_hits += 1; total_hits += 1
                        print(f"  ✓ a=(-1)^n({c2}n²+{c1}n), b={d2}n²+{d1}n+{d0}: {label} ({digits}d)")
                        log_discovery({
                            'family': 'character_twisted',
                            'a_twist': [0, c1, c2], 'b_coeffs': [d0, d1, d2],
                            'description': f"(-1)^n({c2}n²+{c1}n), b={d2}n²+{d1}n+{d0} -> {label}",
                            'value': nstr(val, 40), 'digits': digits,
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    if fam5_eval % 5000 == 0:
                        elapsed = time.time() - t0
                        rate = fam5_eval / elapsed if elapsed > 0 else 0
                        print(f"  [{fam5_eval:,} evaluated | {fam5_hits} hits | {rate:.0f}/s]", flush=True)

print(f"  Family 5: {fam5_hits} hits from {fam5_eval:,} configs ({time.time()-t0:.1f}s)")


# ═══════════════════════════════════════════════════════════════════
# FAMILY 6: Direct ₃F₂ and ₄F₃ evaluation → CF seed generation
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("FAMILY 6: Direct hypergeometric evaluations near Catalan")
print("="*65)

t0 = time.time()
fam6_hits = 0

# Known: G can be expressed via generalized hypergeometric functions
# G ≈ ₃F₂(1/2, 1/2, 1/2; 3/2, 3/2; 1) * something?
# Let's just evaluate many ₃F₂ at various rational z and check

from fractions import Fraction

hyp_configs = []
params_pool = [Fraction(1,4), Fraction(1,3), Fraction(1,2), Fraction(2,3), 
               Fraction(3,4), Fraction(1,1), Fraction(3,2), Fraction(2,1)]
z_pool = [Fraction(-1,1), Fraction(-1,2), Fraction(-1,4), Fraction(1,4), 
          Fraction(1,2), Fraction(3,4), Fraction(1,1)]

# Quick check of specific known ₃F₂ that might relate to G
specific_3f2 = [
    # (a1,a2,a3, b1,b2, z, description)
    (0.5, 0.5, 0.5, 1.5, 1.5, 1.0, "₃F₂(1/2,1/2,1/2;3/2,3/2;1)"),
    (0.5, 0.5, 1.0, 1.5, 1.5, 1.0, "₃F₂(1/2,1/2,1;3/2,3/2;1)"),
    (1.0, 1.0, 1.0, 1.5, 1.5, 0.25, "₃F₂(1,1,1;3/2,3/2;1/4)"),
    (1.0, 1.0, 0.5, 1.5, 2.0, 1.0, "₃F₂(1,1,1/2;3/2,2;1)"),
    (0.5, 0.5, 1.0, 1.5, 2.0, -1.0, "₃F₂(1/2,1/2,1;3/2,2;-1)"),
    (1.0, 1.0, 1.0, 2.0, 2.0, -1.0, "₃F₂(1,1,1;2,2;-1)"),
    (0.5, 1.0, 1.0, 1.5, 1.5, -1.0, "₃F₂(1/2,1,1;3/2,3/2;-1)"),
    (1.0, 1.0, 1.0, 1.5, 2.0, -1.0, "₃F₂(1,1,1;3/2,2;-1)"),
]

for a1, a2, a3, b1, b2, z, desc in specific_3f2:
    try:
        val = mpmath.hyper([a1, a2, a3], [b1, b2], z)
        total_evaluated += 1
        if is_interesting(val):
            hit = check_catalan(val)
            ratio_to_G = val / G
            print(f"  {desc} = {nstr(val, 25)}")
            print(f"    ratio to G = {nstr(ratio_to_G, 15)}")
            if hit:
                label, digits = hit
                fam6_hits += 1; total_hits += 1
                print(f"    ✓ MATCH: {label} ({digits}d)")
                log_discovery({
                    'family': 'hypergeometric', 'description': f"{desc} -> {label}",
                    'value': nstr(val, 40), 'digits': digits,
                    'timestamp': datetime.now().isoformat()
                })
    except Exception as ex:
        print(f"  {desc}: error ({ex})")

print(f"  Family 6: {fam6_hits} hits ({time.time()-t0:.1f}s)")


# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print(f"SUMMARY")
print(f"{'='*65}")
print(f"  Total evaluated: {total_evaluated:,}")
print(f"  Total Catalan hits: {total_hits}")
print(f"  Log file: {LOGFILE}")
print(f"  Reference: G = {nstr(G, 40)}")
