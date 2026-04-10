#!/usr/bin/env python3
"""
Address review gaps: Zagier PSLQ sweep, convergence rate comparison,
Search E false-positive diagnosis.
"""
import mpmath
from mpmath import mp, mpf, zeta, pi, log, log10, sqrt, gamma, catalan, euler
from mpmath import nstr, fabs, pslq

mp.dps = 80

z3 = zeta(3)
z2 = zeta(2)  # pi^2/6
z5 = zeta(5)
pi_v = pi
pi2 = pi**2
pi3 = pi**3
pi4 = pi**4
cat = catalan
ln2 = log(2)
ln3 = log(3)
G14 = gamma(mpf(1)/4)
G13 = gamma(mpf(1)/3)

# Dirichlet L-values
L_chi4_2 = catalan  # L(chi_{-4}, 2) = Catalan
# L(chi_{-3}, 2) = pi^2/(6*sqrt(3))
L_chi3_2 = pi2 / (6 * sqrt(3))
# L(chi_{-3}, 3)
L_chi3_3 = (zeta(3, mpf(1)/3) - zeta(3, mpf(2)/3)) / 27
# L(chi_{-4}, 3) = pi^3/32
L_chi4_3 = pi3 / 32

targets = {
    'z3':       z3,
    '1/z3':     1/z3,
    'z2':       z2,
    'z5':       z5,
    'pi':       pi_v,
    'pi2':      pi2,
    'pi3':      pi3,
    'pi4':      pi4,
    'Cat':      cat,
    'ln2':      ln2,
    'ln3':      ln3,
    'G(1/4)':   G14,
    'G(1/3)':   G13,
    'L(x-3,2)': L_chi3_2,
    'L(x-3,3)': L_chi3_3,
    'L(x-4,3)': L_chi4_3,
    'z3/pi2':   z3/pi2,
    'z3/pi3':   z3/pi3,
    'pi2/z3':   pi2/z3,
    'pi3/z3':   pi3/z3,
    'z2*z3':    z2*z3,
    'z5/pi4':   z5/pi4,
}


def eval_cf(alpha_fn, beta_fn, depth=500):
    """Backward CF evaluation."""
    mp.dps = 80
    val = beta_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = beta_fn(n) + alpha_fn(n + 1) / val
    return beta_fn(0) + alpha_fn(1) / val


def pslq_identify(V, label=""):
    """Run PSLQ against rich target set. Returns list of (desc, residual)."""
    mp.dps = 70
    results = []

    # 1. Simple rational multiples p/q * target
    for tname, tval in targets.items():
        for p in range(1, 25):
            for q in range(1, 13):
                if __import__('math').gcd(p, q) != 1:
                    continue
                d = fabs(V - mpf(p)/q * tval)
                if d == 0:
                    results.append((f"{p}/{q}*{tname}" if q > 1 else
                                    (f"{p}*{tname}" if p > 1 else tname),
                                    0, 80))
                elif d < mpf(10)**(-20):
                    digs = int(-log10(d))
                    results.append((f"{p}/{q}*{tname}" if q > 1 else
                                    (f"{p}*{tname}" if p > 1 else tname),
                                    float(d), digs))

    # 2. Mobius PSLQ: a*V*K + b*V + c*K + d = 0 for each target K
    for tname, tval in targets.items():
        try:
            basis = [V * tval, V, tval, mpf(1)]
            rel = pslq(basis, maxcoeff=200, tol=mpf(10)**(-50))
            if rel is not None:
                a, b, c, d = rel
                if a*d != b*c:  # non-degenerate
                    res = fabs(a*V*tval + b*V + c*tval + d)
                    if res < mpf(10)**(-30):
                        digs = int(-log10(res)) if res > 0 else 70
                        # V = -(c*K + d) / (a*K + b)
                        desc = f"V = -({c}*{tname}+{d})/({a}*{tname}+{b})"
                        results.append((desc, float(res), digs))
        except:
            pass

    # 3. Two-target PSLQ: a*V + b*T1 + c*T2 + d = 0
    key_targets = ['z3', '1/z3', 'z2', 'pi', 'pi2', 'Cat', 'ln2', 'L(x-3,3)']
    for i, t1 in enumerate(key_targets):
        for t2 in key_targets[i+1:]:
            try:
                basis = [V, targets[t1], targets[t2], mpf(1)]
                rel = pslq(basis, maxcoeff=100, tol=mpf(10)**(-40))
                if rel is not None:
                    a, b, c, d = rel
                    if a != 0:
                        res = fabs(a*V + b*targets[t1] + c*targets[t2] + d)
                        if res < mpf(10)**(-30):
                            digs = int(-log10(res)) if res > 0 else 70
                            desc = f"{a}*V + {b}*{t1} + {c}*{t2} + {d} = 0"
                            results.append((desc, float(res), digs))
            except:
                pass

    results.sort(key=lambda x: -x[2])
    return results


# ══════════════════════════════════════════════════════════════════
# PART 1: ZAGIER FAMILY PSLQ SWEEP
# ══════════════════════════════════════════════════════════════════

print('=' * 78)
print('  PART 1: ZAGIER FAMILY — DEEP PSLQ IDENTIFICATION')
print('=' * 78)

zagier_forms = [
    ('Apery (17,5,1)',      -1,  [5, 27, 51, 34]),
    ('Batut-Olivier (3,1,1)', -1, [1, 5, 9, 6]),
    ('Zagier (7,2,-8)',      8,  [2, 11, 21, 14]),
    ('Zagier (11,3,-1)',     1,  [3, 17, 33, 22]),
    ('Zagier (10,3,9)',     -9,  [3, 16, 30, 20]),
    ('Zagier (12,4,-8)',     8,  [4, 20, 36, 24]),
    ('Zagier (9,3,27)',    -27,  [3, 15, 27, 18]),
]

# Also compute convergence rates
print('\n  Computing CF values, convergence rates, and PSLQ identifications...\n')

for name, C, bcoeffs in zagier_forms:
    alpha_fn = lambda n, _C=C: _C * mpf(n)**6
    beta_fn = lambda n, _b=bcoeffs: sum(c * mpf(n)**i for i, c in enumerate(_b))

    # Value at depth 500
    cf500 = eval_cf(alpha_fn, beta_fn, 500)

    # Convergence rate: compare depth 498 vs 500
    cf498 = eval_cf(alpha_fn, beta_fn, 498)
    cf496 = eval_cf(alpha_fn, beta_fn, 496)
    if cf500 != cf498 and cf498 != cf496:
        err500 = fabs(cf500 - cf498)
        err498 = fabs(cf498 - cf496)
        if err498 > 0 and err500 > 0:
            rate = float(err500 / err498)
        else:
            rate = 0.0
    else:
        rate = 0.0

    # Also get characteristic equation rate
    # Leading beta coeff b3, alpha leading -|C|
    b3 = bcoeffs[-1]
    # Characteristic: x^2 - b3*x + |C| = 0 if C < 0
    #                 x^2 - b3*x - C = 0    if C > 0
    # Actually for recurrence p_n = b3*n^3*p_{n-1} + C*n^6*p_{n-2}
    # Divide by n^3: leading behavior x^2 - b3*x + C = 0... no.
    # Actually: p_n ~ r^n, ratio of consecutive ~ b3 + sqrt(b3^2+4|C|))/2
    # The CF convergence rate is the smaller/larger root ratio
    import cmath
    disc = b3**2 + 4*C  # C is already signed; for alpha=C*n^6
    # Actually characteristic eq: x^2 - b3*x - C = 0 when we absorb n^3
    # Wait: p_n = beta(n)*p_{n-1} + alpha(n)*p_{n-2}
    # Leading: b3*n^3 * p_{n-1} + C*n^6 * p_{n-2}
    # Set p_n = r^n * n^{3n}: r^2 - b3*r - C = 0
    # Hmm, sign depends on convention. Let me just solve both and pick.
    for eq_name, a_coeff, b_coeff, c_coeff in [
            ('x^2-b3*x-C=0', 1, -b3, -C),
            ('x^2-b3*x+C=0', 1, -b3, C)]:
        disc = b_coeff**2 - 4*a_coeff*c_coeff
        if disc > 0:
            r1 = (-b_coeff + disc**0.5) / 2
            r2 = (-b_coeff - disc**0.5) / 2
            if abs(r1) > 0 and abs(r2) > 0:
                conv = min(abs(r2/r1), abs(r1/r2))
                if 0 < conv < 1:
                    char_rate = conv
                    char_eq = eq_name
                    break
    else:
        char_rate = None
        char_eq = "complex roots"

    print(f'  {name}')
    print(f'    CF value  = {nstr(cf500, 25)}')
    print(f'    alpha(n)  = {C}*n^6,  beta coeffs = {bcoeffs}')
    if rate > 0:
        print(f'    Empirical convergence rate ~ {rate:.6f}')
    if char_rate is not None:
        print(f'    Characteristic rate (r2/r1)^2 ~ {char_rate**2:.8f}  [{char_eq}]')

    # PSLQ identification
    results = pslq_identify(cf500, name)
    if results:
        print(f'    PSLQ identifications:')
        for desc, res, digs in results[:5]:
            marker = ' <-- MATCH' if digs >= 40 else ''
            print(f'      {desc}  ({digs}d){marker}')
    else:
        print(f'    PSLQ: no identification found')
    print()


# ══════════════════════════════════════════════════════════════════
# PART 2: CONVERGENCE RATE COMPARISON
# ══════════════════════════════════════════════════════════════════

print('=' * 78)
print('  PART 2: CONVERGENCE RATE COMPARISON')
print('=' * 78)

print("""
  For a PCF p_n = beta(n)*p_{n-1} + alpha(n)*p_{n-2} with
    alpha(n) = C*n^6,  beta(n) ~ b3*n^3
  the characteristic equation (dividing by the dominant n^3 growth) is:
    r^2 - b3*r - C = 0
  The CF convergence rate per step is |r_small/r_large|.
  The convergence rate per TWO steps (which is what matters for
  the even/odd convergent subsequences) is |r_small/r_large|^2.
""")

print(f'  {"Name":<25s}  {"b3":>4}  {"C":>4}  {"r1":>12}  {"r2":>12}  '
      f'{"rate":>12}  {"rate^2":>12}  {"digits/step":>12}')
print(f'  {"─"*25}  {"─"*4}  {"─"*4}  {"─"*12}  {"─"*12}  '
      f'{"─"*12}  {"─"*12}  {"─"*12}')

for name, C, bcoeffs in zagier_forms:
    b3 = bcoeffs[-1]
    # r^2 - b3*r - C = 0
    disc = b3**2 + 4*C
    if disc > 0:
        r1 = (b3 + disc**0.5) / 2
        r2 = (b3 - disc**0.5) / 2
        rate = abs(r2/r1)
        rate2 = rate**2
        import math
        dps = -math.log10(rate2) if rate2 > 0 else float('inf')
        print(f'  {name:<25s}  {b3:4d}  {C:4d}  {r1:12.4f}  {r2:12.6f}  '
              f'{rate:12.8f}  {rate2:12.10f}  {dps:12.4f}')
    else:
        r1c = (b3 + (-disc)**0.5 * 1j) / 2
        print(f'  {name:<25s}  {b3:4d}  {C:4d}  complex: {r1c}')

# Explicit Apery and B-O comparison
print(f'\n  Apery:')
print(f'    r^2 - 34r + 1 = 0  =>  r1 = 17+12*sqrt(2) = (1+sqrt(2))^4')
print(f'    rate^2 = ((sqrt(2)-1)/(sqrt(2)+1))^4 = (sqrt(2)-1)^8')
r_apery = (sqrt(2) - 1)**8
print(f'    = {float(r_apery):.10f}')
print(f'    digits per 2 steps: {float(-log10(r_apery)):.4f}')

print(f'\n  Batut-Olivier:')
print(f'    r^2 - 6r + 1 = 0  =>  r1 = 3+2*sqrt(2), r2 = 3-2*sqrt(2)')
r_bo = ((3 - 2*sqrt(2)) / (3 + 2*sqrt(2)))**2
print(f'    rate^2 = ((3-2sqrt2)/(3+2sqrt2))^2 = {float(r_bo):.10f}')
print(f'    digits per 2 steps: {float(-log10(r_bo)):.4f}')
print(f'    Apery is {float(-log10(r_apery) / -log10(r_bo)):.2f}x faster')


# ══════════════════════════════════════════════════════════════════
# PART 3: SEARCH E FALSE-POSITIVE DIAGNOSIS
# ══════════════════════════════════════════════════════════════════

print(f'\n{"=" * 78}')
print(f'  PART 3: SEARCH E FALSE-POSITIVE DIAGNOSIS')
print(f'{"=" * 78}')

import json
e_data = json.load(open('search_e_zeta3_results.json'))

# The E data only has verified (0). Let's reconstruct the pre-filter hits
# and diagnose them. We know the hits from the terminal output.

e_hits_64 = [
    # (6,4) hits from terminal output
    (6, 1, 8, 30, -7, 11, '7/2*pi'),
    (6, 1, 10, 23, -1, 11, '7/2*pi'),
    (6, 1, 11, -19, 30, 5, '6*1/z3'),
    (6, 1, 13, 15, 5, 11, '7/2*pi'),
    (6, 1, 15, 8, 11, 11, '7/2*pi'),
    (6, 1, 17, 1, 17, 11, '7/2*pi'),
    (6, 1, 19, -6, 23, 11, '7/2*pi'),
    (6, 1, 21, -13, 29, 11, '7/2*pi'),
    (6, 1, 24, -21, -10, 15, '19/4*pi'),
    (6, 3, 16, -5, 11, 3, '13/4*Cat'),
    (6, 4, 1, -7, -22, 1, '5/8*pi2/6'),
    (6, 4, 10, -4, 27, 4, '9/2*L(x-3,3)'),
    (6, 4, 11, -2, 30, 10, '12*1/z3'),
    (6, 5, 24, 26, -13, 14, '17/2*pi2/6'),
    # (8,4) hits
    (8, 1, 1, -7, -4, 2, '16/7*L(x-3,3)'),
    (8, 2, 16, -18, -11, 1, '6/7*z3'),
    (8, 2, 21, 26, -21, 2, '9/4*L(x-3,3)'),
    (8, 2, 25, 15, -7, 11, '12*Cat'),
    (8, 3, 10, -30, 10, 1, '8/7*Cat'),
    (8, 3, 19, 27, 12, 5, '6*1/z3'),
]

print(f'\n  Diagnosing {len(e_hits_64)} pre-filter hits that failed verification...\n')

mp.dps = 80

for adeg, Cv, A, B, D, E, prefilter_target in e_hits_64:
    b4 = 2*A
    b3 = 3*A + 2*B
    b2 = A + 3*B + 2*D
    b1 = B + 3*D + 2*E
    b0 = E

    alpha_fn = lambda n, _C=Cv, _ad=adeg: -_C * mpf(n)**_ad
    beta_fn = lambda n, _b4=b4, _b3=b3, _b2=b2, _b1=b1, _b0=b0: (
        _b4*mpf(n)**4 + _b3*mpf(n)**3 + _b2*mpf(n)**2 + _b1*mpf(n) + _b0)

    # Evaluate at multiple depths to see convergence behavior
    vals = {}
    for dep in [50, 100, 200, 500]:
        try:
            v = eval_cf(alpha_fn, beta_fn, dep)
            vals[dep] = v
        except:
            vals[dep] = None

    v50 = vals.get(50)
    v500 = vals.get(500)

    if v50 is not None and v500 is not None:
        drift = fabs(v50 - v500)
        if drift > 0:
            drift_digs = int(-log10(drift))
        else:
            drift_digs = 80
    else:
        drift_digs = -1

    # Classify
    if drift_digs >= 20:
        category = "CONVERGED (but not to target)"
    elif drift_digs >= 5:
        category = f"SLOW CONVERGENCE ({drift_digs}d at depth 500)"
    elif 0 <= drift_digs < 5:
        category = "DIVERGENT / noise"
    else:
        category = "ERROR"

    # If converged, try PSLQ on the depth-500 value
    identifications = ""
    if v500 is not None and drift_digs >= 15:
        results = pslq_identify(v500)
        if results and results[0][2] >= 25:
            identifications = f" -> actually {results[0][0]} ({results[0][2]}d)"

    print(f'  ({adeg},{4}) C={Cv} A={A} B={B} D={D} E={E}')
    print(f'    Pre-filter match: {prefilter_target}')
    print(f'    depth50 = {nstr(v50, 15) if v50 else "None"}')
    print(f'    depth500= {nstr(v500, 15) if v500 else "None"}')
    print(f'    drift   = {drift_digs}d   [{category}]{identifications}')
    print()
