#!/usr/bin/env python3
"""Targeted mystery constant sweep for V_quad paper."""
import mpmath
from mpmath import (mpf, mp, nstr, log, pi, sqrt, zeta, catalan, euler,
                    pslq, log10, gamma as mpgamma, tan, binomial as mpbinom)

mp.dps = 300

test_cases = [
    (3, 1, 1, 'V_quad original, disc=-11'),
    (1, 1, 1, 'simplest, disc=-3'),
    (2, -1, 1, 'disc=9'),
    (1, -3, 3, 'disc=-3 variant'),
    (1, 0, 1, 'disc=-4'),
]

depth = 5000
print('TARGETED MYSTERY CONSTANT SWEEP')
print('=' * 74)

# Build extended targets
extended_targets = []
for m_val in range(8):
    v = 2 * mpgamma(m_val + 1) / (sqrt(pi) * mpgamma(m_val + mpf('0.5')))
    extended_targets.append(('val(%d)' % m_val, v))
for m_half in [0.5, 1.5, 2.5, 3.5]:
    v = 2 * mpgamma(m_half + 1) / (sqrt(pi) * mpgamma(m_half + mpf('0.5')))
    extended_targets.append(('val(%.1f)' % m_half, v))

for a in range(1, 7):
    for b in range(1, 7):
        if a != b:
            v = mpgamma(mpf(a) / 2) / mpgamma(mpf(b) / 2)
            extended_targets.append(('G(%d/2)/G(%d/2)' % (a, b), v))

basics = [
    ('pi', pi), ('1/pi', 1 / pi), ('4/pi', 4 / pi),
    ('e', mpmath.e), ('ln2', log(2)), ('G', catalan), ('zeta3', zeta(3)),
    ('sqrt2', sqrt(2)), ('sqrt3', sqrt(3)), ('phi', (1 + sqrt(5)) / 2),
    ('gamma', euler), ('sqrt(pi)', sqrt(pi)), ('2/sqrt(pi)', 2 / sqrt(pi)),
]
for name, val in basics:
    for p in [-3, -2, -1, 1, 2, 3, 4]:
        for q in [1, 2, 3, 4, 5, 6]:
            extended_targets.append(('%d/%d*%s' % (p, q, name), mpf(p) / q * val))

print('  Target pool: %d expressions' % len(extended_targets))

for A, B, C, label in test_cases:
    val = mpf(A * depth ** 2 + B * depth + C)
    for k in range(depth, 0, -1):
        bk = A * (k - 1) ** 2 + B * (k - 1) + C
        val = mpf(bk) + mpf(1) / val
    V = val

    print('\n  %s: b(n) = %dn^2 + %dn + %d' % (label, A, B, C))
    print('  V = %s' % nstr(V, 40))

    best_name, best_d = None, 0
    for tname, tval in extended_targets:
        if abs(tval) < mpf(10) ** (-50):
            continue
        d = abs(V - tval)
        if d > 0:
            digits = -int(float(log10(d)))
            if digits > best_d:
                best_d = digits
                best_name = tname

    if best_d >= 20:
        print('  MATCH: %s (%dd)' % (best_name, best_d))
    else:
        print('  No match (best: %dd %s)' % (best_d, best_name))

    # Log-Gamma PSLQ: is log(V) a rational combination of logGamma(k/6)?
    lgV = mpmath.log(V)
    lgamma_basis = [mpmath.loggamma(mpf(k) / 6) for k in range(1, 13)]
    vec = [lgV] + lgamma_basis + [mpf(1)]
    try:
        rel = pslq(vec, maxcoeff=1000)
        if rel is not None and rel[0] != 0:
            check = sum(r * v for r, v in zip(rel, vec))
            d = -int(float(log10(abs(check)))) if abs(check) > 0 else 300
            if d > 50:
                terms = []
                for i, coeff in enumerate(rel[1:-1], 1):
                    if coeff != 0:
                        terms.append('%d*logG(%d/6)' % (coeff, i))
                cterm = ' + %d' % rel[-1] if rel[-1] != 0 else ''
                print('  LOG-GAMMA: %d*log(V) = %s%s  (%dd)' % (rel[0], ' + '.join(terms), cterm, d))
            else:
                print('  LOG-GAMMA: relation found but low quality (%dd)' % d)
        else:
            print('  LOG-GAMMA: no relation (coeff<=1000)')
    except Exception as e:
        print('  LOG-GAMMA: error: %s' % e)

    # 15-constant PSLQ
    basis15 = [V, pi, pi ** 2, mpmath.e, log(2), log(3), euler, catalan,
               zeta(3), zeta(5), sqrt(2), sqrt(3), sqrt(5),
               (1 + sqrt(5)) / 2, sqrt(pi), mpf(1)]
    try:
        rel2 = pslq(basis15, maxcoeff=10000)
        if rel2 is not None and rel2[0] != 0:
            check2 = sum(r * v for r, v in zip(rel2, basis15))
            d2 = -int(float(log10(abs(check2)))) if abs(check2) > 0 else 300
            if d2 > 100:
                print('  PSLQ-15: %s (%dd)' % (rel2, d2))
            else:
                print('  PSLQ-15: spurious (%dd)' % d2)
        else:
            print('  PSLQ-15: no relation (coeff<=10000)')
    except Exception as e:
        print('  PSLQ-15: error: %s' % e)

    # Non-integer m test: does V = val(m) for some real m?
    # val(m) = 2*Gamma(m+1)/(sqrt(pi)*Gamma(m+1/2))
    # Solve numerically: find m such that val(m) = V
    # val is monotonically increasing for m > -1/2, so bisect
    def val_m(m):
        return 2 * mpgamma(m + 1) / (sqrt(pi) * mpgamma(m + mpf('0.5')))

    if V > val_m(mpf('-0.49')) and V < val_m(mpf('100')):
        lo, hi = mpf('-0.49'), mpf('100')
        for _ in range(200):
            mid = (lo + hi) / 2
            if val_m(mid) < V:
                lo = mid
            else:
                hi = mid
        m_solved = (lo + hi) / 2
        residual = abs(val_m(m_solved) - V)
        print('  GAMMA INVERSION: V = val(m) at m = %s' % nstr(m_solved, 25))

        # Is this m a recognizable constant?
        m_targets = [
            ('integer', None),  # skip
            ('pi', pi), ('e', mpmath.e), ('ln2', log(2)), ('phi', (1 + sqrt(5)) / 2),
            ('sqrt2', sqrt(2)), ('1/pi', 1 / pi), ('gamma', euler),
        ]
        for mn, mv in m_targets:
            if mv is None:
                continue
            for p in range(-4, 5):
                if p == 0:
                    continue
                for q in range(1, 7):
                    d = abs(m_solved - mpf(p) / q * mv)
                    if d < mpf(10) ** (-50):
                        dig = -int(float(log10(d)))
                        print('    m = %d/%d * %s (%dd)' % (p, q, mn, dig))
        # Check simple rationals
        for q in range(1, 200):
            p = round(float(m_solved * q))
            if abs(m_solved - mpf(p) / q) < mpf(10) ** (-50):
                print('    m = %d/%d (%dd)' % (p, q, -int(float(log10(abs(m_solved - mpf(p) / q))))))
                break

print('\n' + '=' * 74)
print('SWEEP COMPLETE')
