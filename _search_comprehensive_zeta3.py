#!/usr/bin/env python3
"""
Comprehensive zeta(3) PCF Search Suite
=======================================
Implements suggestions 1-3 from the analysis:

  Search C: Extended Search B — C up to 20, wider bounds, more k-values
  Search D: Known non-Apery variants (k=1, 8/7, 5/2, 12/7 forms)
  Search E: Higher degrees (6,4) and (8,4) with (2n+1) factor constraint

All searches use:
  Phase 1: numpy float64 vectorised pre-filter (depth 50, threshold 1e-8)
  Phase 2: mpmath verification (depth 500, 50-digit precision)

Usage:
  python _search_comprehensive_zeta3.py C     # Extended Search B
  python _search_comprehensive_zeta3.py D     # Known variants
  python _search_comprehensive_zeta3.py E     # Higher degrees
  python _search_comprehensive_zeta3.py ALL   # Run all three
"""
import numpy as np
import time
import json
import sys
from math import gcd
from functools import reduce

# ══════════════════════════════════════════════════════════════════════════
# SHARED ENGINE
# ══════════════════════════════════════════════════════════════════════════

def gcd_n(*a):
    return reduce(gcd, (abs(x) for x in a if x != 0), 0)


def init_targets_float(extra_k=False):
    """Build float64 target array for pre-filter."""
    import mpmath
    mpmath.mp.dps = 80
    z3 = mpmath.zeta(3)
    pi = mpmath.pi
    pi3 = pi ** 3
    cat = mpmath.catalan
    L3 = (mpmath.zeta(3, mpmath.mpf(1)/3)
          - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27

    base = {
        'z3':          float(z3),
        '1/z3':        float(1/z3),
        'z3/pi3':      float(z3/pi3),
        'pi3/z3':      float(pi3/z3),
        'L(x-3,3)':    float(L3),
        'L(x-3,3)/pi3':float(L3/pi3),
        'Cat':         float(cat),
        'pi':          float(pi),
        'pi2/6':       float(pi**2/6),
    }

    if extra_k:
        k_vals = [1,2,3,4,5,6,7,8,9,10,12,15,16,20,24]
        # Also add rational multiples p/q for small p,q
        k_rats = [(p, q) for p in range(1, 25) for q in range(1, 9)
                  if gcd(p, q) == 1 and p/q <= 25]
    else:
        k_vals = [1,2,3,4,5,6,8,10,12]
        k_rats = [(k, 1) for k in k_vals]

    tgt_vals, tgt_names = [], []
    for name, val in base.items():
        seen_k = set()
        for p, q in k_rats:
            kf = p / q
            if kf in seen_k:
                continue
            seen_k.add(kf)
            tgt_vals.append(kf * val)
            if q == 1:
                lab = f"{p}*{name}" if p > 1 else name
            else:
                lab = f"{p}/{q}*{name}"
            tgt_names.append(lab)

    return np.array(tgt_vals, dtype=np.float64), tgt_names, base


def init_targets_mpmath(dps=50):
    """Build mpmath target dict for verification."""
    import mpmath
    mpmath.mp.dps = dps + 30
    z3 = mpmath.zeta(3)
    pi = mpmath.pi
    pi3 = pi ** 3
    cat = mpmath.catalan
    L3 = (mpmath.zeta(3, mpmath.mpf(1)/3)
          - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27
    return {
        'z3': z3, '1/z3': 1/z3,
        'z3/pi3': z3/pi3, 'pi3/z3': pi3/z3,
        'L(x-3,3)': L3, 'L(x-3,3)/pi3': L3/pi3,
        'Cat': cat, 'pi': pi, 'pi2/6': pi**2/6,
    }


def verify_cf_mpmath(alpha_fn, beta_fn, depth, targets_mp, k_rats, dps=50):
    """
    Evaluate CF at high precision and match against targets.
    alpha_fn(n) -> mpf, beta_fn(n) -> mpf
    Returns (cf_value, best_match_name, best_digits) or (cf_value, None, 0).
    """
    import mpmath
    mpmath.mp.dps = dps + 30

    n = depth
    val = beta_fn(n)
    for n in range(depth - 1, 0, -1):
        val = beta_fn(n) + alpha_fn(n + 1) / val
    cf = beta_fn(0) + alpha_fn(1) / val

    best_name, best_digs = None, 0
    for tn, tv in targets_mp.items():
        for p, q in k_rats:
            kv = mpmath.mpf(p) / q
            d = abs(cf - kv * tv)
            if d == 0:
                dg = dps + 20
            elif d < mpmath.mpf(10)**(-15):
                dg = int(-mpmath.log10(d))
            else:
                continue
            if q == 1:
                lab = f"{p}*{tn}" if p > 1 else tn
            else:
                lab = f"{p}/{q}*{tn}"
            if dg > best_digs:
                best_digs, best_name = dg, lab

    return cf, best_name, best_digs


def eval_cf_numpy_vec(b3, b2, b1_col, b0_row, C, alpha_degree, depth,
                      extra_alpha_coeffs=None):
    """
    Vectorised backward CF evaluation in float64.
    b1_col: shape (N1, 1), b0_row: shape (1, N0)
    alpha_degree: 6 means alpha(n) = -C * n^6
    extra_alpha_coeffs: dict of {power: coeff} for sub-leading terms
    Returns cf array of shape (N1, N0).
    """
    D = depth
    # beta(D) for all (b1, b0)
    val = b3 * D**3 + b2 * D**2 + b1_col * D + b0_row

    for n in range(D - 1, 0, -1):
        bn = b3 * n**3 + b2 * n**2 + b1_col * n + b0_row
        n1 = n + 1
        an1 = -C * n1**alpha_degree
        if extra_alpha_coeffs:
            for pwr, coeff in extra_alpha_coeffs.items():
                an1 += coeff * n1**pwr
        with np.errstate(divide='ignore', invalid='ignore'):
            val = bn + an1 / val

    with np.errstate(divide='ignore', invalid='ignore'):
        a1 = -C * 1**alpha_degree
        if extra_alpha_coeffs:
            for pwr, coeff in extra_alpha_coeffs.items():
                a1 += coeff * 1**pwr
        cf = b0_row + a1 / val
    return cf


def eval_cf_numpy_vec_gen(beta_coeffs_scalar, beta_b1_col, beta_b0_row,
                          alpha_fn_np, depth, beta_deg=3):
    """
    More general vectorised backward CF evaluation.
    beta = beta_coeffs_scalar(n) + beta_b1_col * n + beta_b0_row
    alpha_fn_np(n) -> scalar alpha value
    """
    D = depth
    val = beta_coeffs_scalar(D) + beta_b1_col * D + beta_b0_row

    for n in range(D - 1, 0, -1):
        bn = beta_coeffs_scalar(n) + beta_b1_col * n + beta_b0_row
        an1 = alpha_fn_np(n + 1)
        with np.errstate(divide='ignore', invalid='ignore'):
            val = bn + an1 / val

    with np.errstate(divide='ignore', invalid='ignore'):
        cf = beta_b0_row + alpha_fn_np(1) / val
    return cf


def check_matches(cf, tgt_arr, thresh):
    """Check cf array against target array. Returns mask."""
    with np.errstate(invalid='ignore'):
        diff = np.abs(cf[:, :, np.newaxis]
                      - tgt_arr[np.newaxis, np.newaxis, :])
        return diff < thresh, diff


def print_banner(title):
    print(f'\n{"=" * 78}')
    print(f'  {title}')
    print(f'{"=" * 78}')


# ══════════════════════════════════════════════════════════════════════════
# SEARCH C: EXTENDED SEARCH B
# ══════════════════════════════════════════════════════════════════════════

def search_C():
    """Extended Search B: C up to 20, wider bounds, more k-values."""
    import mpmath

    print_banner('SEARCH C: Extended monomial alpha (C<=20, wider bounds)')

    C_VALUES = list(range(1, 21))
    B3_MIN, B3_MAX = 1, 80
    B2_MIN, B2_MAX = -150, 150
    B1_MIN, B1_MAX = -150, 150
    B0_MIN, B0_MAX = 1, 80
    PRE_DEPTH = 50
    PRE_THRESH = 1e-8
    VER_DEPTH = 500
    VER_DPS = 50

    tgt_arr, tgt_names, base = init_targets_float(extra_k=True)
    k_rats = [(p, q) for p in range(1, 25) for q in range(1, 9)
              if gcd(p, q) == 1 and p/q <= 25]

    b1_arr = np.arange(B1_MIN, B1_MAX + 1, dtype=np.float64)
    b0_arr = np.arange(B0_MIN, B0_MAX + 1, dtype=np.float64)
    b1_col = b1_arr[:, np.newaxis]
    b0_row = b0_arr[np.newaxis, :]

    nb1 = len(b1_arr)
    nb0 = len(b0_arr)
    nb3 = B3_MAX - B3_MIN + 1
    nb2 = B2_MAX - B2_MIN + 1
    total_outer = len(C_VALUES) * nb3 * nb2
    n_cand = total_outer * nb1 * nb0

    print(f'  C in [1, {max(C_VALUES)}],  b3 in [{B3_MIN},{B3_MAX}],  '
          f'b2 in [{B2_MIN},{B2_MAX}]')
    print(f'  b1 in [{B1_MIN},{B1_MAX}],  b0 in [{B0_MIN},{B0_MAX}]')
    print(f'  Candidates:      {n_cand:>15,}')
    print(f'  Outer blocks:    {total_outer:>15,}')
    print(f'  Inner grid:      {nb1} x {nb0} = {nb1*nb0:,}')
    print(f'  Targets:         {len(tgt_arr)}  ({len(base)} bases x '
          f'{len(k_rats)} k-values)')
    print(f'  Pre-filter:      depth {PRE_DEPTH}, thresh {PRE_THRESH}')
    print(f'  Verification:    depth {VER_DEPTH}, {VER_DPS} dps')

    # Sanity check
    print(f'\n  Sanity check (Apery):')
    v = float(34*50**3 + 51*50**2 + 27*50 + 5)
    for n in range(49, 0, -1):
        v = (34*n**3 + 51*n**2 + 27*n + 5) + (-(n+1)**6) / v
    cf_chk = 5.0 + (-1.0) / v
    mpmath.mp.dps = 30
    ref = float(6 / mpmath.zeta(3))
    print(f'    CF={cf_chk:.15f}  ref={ref:.15f}  '
          f'diff={abs(cf_chk-ref):.2e}  {"OK" if abs(cf_chk-ref)<1e-6 else "FAIL"}')

    hits = []
    seen = set()
    count = 0
    t0 = time.time()
    print(f'\n  Phase 1: scanning...')

    for C in C_VALUES:
        for b3 in range(B3_MIN, B3_MAX + 1):
            for b2 in range(B2_MIN, B2_MAX + 1):
                count += 1
                if count % 50000 == 0:
                    el = time.time() - t0
                    r = count / el if el > 0 else 1
                    eta = (total_outer - count) / r
                    print(f'    [{count:>9,}/{total_outer:,}] '
                          f'{100*count/total_outer:5.1f}%  '
                          f't={el:7.0f}s  eta={eta:6.0f}s  '
                          f'hits={len(hits)}', flush=True)

                D = PRE_DEPTH
                base_D = b3 * D**3 + b2 * D**2
                val = base_D + b1_col * D + b0_row

                for n in range(D - 1, 0, -1):
                    base_n = b3 * n**3 + b2 * n**2
                    bn = base_n + b1_col * n + b0_row
                    an1 = -C * (n + 1)**6
                    with np.errstate(divide='ignore', invalid='ignore'):
                        val = bn + an1 / val

                with np.errstate(divide='ignore', invalid='ignore'):
                    cf = b0_row + (-C) / val

                mask, diff = check_matches(cf, tgt_arr, PRE_THRESH)
                if not mask.any():
                    continue

                for i, j, t in zip(*np.where(mask)):
                    b1i = int(b1_arr[i])
                    b0j = int(b0_arr[j])
                    key = (C, b3, b2, b1i, b0j)
                    if key in seen:
                        continue
                    g = gcd_n(b3, b2, b1i, b0j)
                    if g != 1:
                        continue
                    seen.add(key)

                    bh = -b3/8 + b2/4 - b1i/2 + b0j
                    has_factor = abs(bh) < 1e-12

                    hits.append(dict(
                        C=C, b3=b3, b2=b2, b1=b1i, b0=b0j,
                        target=tgt_names[t], cf=float(cf[i,j]),
                        diff=float(diff[i,j,t]), has_2n1=has_factor,
                    ))
                    is_apery = (key == (1, 34, 51, 27, 5))
                    tag = 'APERY' if is_apery else 'NEW? '
                    fstr = '(2n+1)' if has_factor else ''
                    print(f'    [{tag}] C={C} b=({b3},{b2},{b1i},{b0j}) '
                          f'{fstr} -> {tgt_names[t]}  d={float(diff[i,j,t]):.2e}',
                          flush=True)

    t_p1 = time.time() - t0
    print(f'\n  Phase 1 done: {len(hits)} hits in {t_p1:.0f}s')

    # Phase 2 verification
    verified = _verify_hits(hits, VER_DEPTH, VER_DPS, k_rats, alpha_deg=6)
    _save_results('search_c_zeta3_results.json', 'C', n_cand, hits, verified,
                  time.time() - (t0 - (t_p1 - t_p1)))
    return verified


# ══════════════════════════════════════════════════════════════════════════
# SEARCH D: KNOWN NON-APERY VARIANTS
# ══════════════════════════════════════════════════════════════════════════

def search_D():
    """
    Targeted search around known non-Apery ζ(3) PCF variants.

    Known forms from literature:
      D1: k=1 (Euler): beta = n^3 + (n+1)^3 = 2n^3+3n^2+3n+1, alpha = -n^6
          CF -> ??? (slow convergence, may give zeta(3) directly)
      D2: k=8/7 (Batut-Olivier 1980):
          beta = (2n+1)(3n^2+3n+1) = 6n^3+9n^2+5n+1, alpha = -n^6
          CF -> 8/(7*zeta(3)) or similar
      D3: Parametric (Cohen 2023 style):
          beta = (2n+1)(An^2+Bn+C), alpha = -D*n^6 - E*n^5 - F*n^4
          with sub-leading alpha terms
      D4: Perturbed Apery:
          alpha = -(n+a)^3 * (n-a)^3 = -(n^2-a^2)^3 for small integer a
          beta = Zagier form
    """
    import mpmath

    print_banner('SEARCH D: Known non-Apery variants + parametric families')

    VER_DEPTH = 500
    VER_DPS = 50
    k_rats = [(p, q) for p in range(1, 25) for q in range(1, 9)
              if gcd(p, q) == 1 and p/q <= 25]
    tgt_mp = init_targets_mpmath(VER_DPS)

    all_verified = []

    # ── D1: Exact known forms from literature ──
    print(f'\n  D1: Testing exact known/conjectured PCFs')
    print(f'  {"─" * 60}')

    known_forms = [
        # (name, alpha_coeffs [const..leading], beta_coeffs [const..leading])
        ('Apery: a=-n^6, b=(2n+1)(17n^2+17n+5)',
         {6: -1}, [5, 27, 51, 34]),
        ('Euler-type: a=-n^6, b=n^3+(n+1)^3',
         {6: -1}, [1, 3, 3, 2]),
        ('Batut-Olivier: a=-n^6, b=(2n+1)(3n^2+3n+1)',
         {6: -1}, [1, 5, 9, 6]),
        ('Alt Batut: a=-n^6, b=(2n-1)(3n^2-3n+1)',
         {6: -1}, [1, -1, 3, 6]),
        # Zagier sporadic: (A,B,C) from his 2009 paper
        ('Zagier (7,2,-8): a=8n^6, b=(2n+1)(7n^2+7n+2)',
         {6: 8}, [2, 11, 21, 14]),
        ('Zagier (11,3,-1): a=n^6, b=(2n+1)(11n^2+11n+3)',
         {6: 1}, [3, 17, 33, 22]),
        ('Zagier (10,3,9): a=-9n^6, b=(2n+1)(10n^2+10n+3)',
         {6: -9}, [3, 16, 30, 20]),
        ('Zagier (12,4,-8): a=8n^6, b=(2n+1)(12n^2+12n+4)',
         {6: 8}, [4, 20, 36, 24]),
        ('Zagier (9,3,27): a=-27n^6, b=(2n+1)(9n^2+9n+3)',
         {6: -27}, [3, 15, 27, 18]),
        # Cohen-style: alpha with sub-leading terms
        ('Cohen-type: a=-(n^2(n+1))^2, b=(2n+1)(17n^2+17n+5)',
         # -(n^2(n+1))^2 = -(n^4(n^2+2n+1)) = -n^6-2n^5-n^4
         {6: -1, 5: -2, 4: -1}, [5, 27, 51, 34]),
        ('Shifted: a=-(n(n+1))^3, b=(2n+1)(17n^2+17n+5)',
         # -(n(n+1))^3 = -(n^3+3n^2+3n+n)^... actually:
         # (n(n+1))^3 = n^3(n+1)^3 = n^3(n^3+3n^2+3n+1)
         # = n^6+3n^5+3n^4+n^3
         {6: -1, 5: -3, 4: -3, 3: -1}, [5, 27, 51, 34]),
        # More Euler-type
        ('Euler-2: a=-n^6, b=2(2n+1)(n^2+n+1)',
         {6: -1}, [2, 6, 6, 4]),
    ]

    for name, alpha_dict, beta_coeffs in known_forms:
        mpmath.mp.dps = VER_DPS + 30

        def make_alpha(ad):
            def fn(n):
                v = mpmath.mpf(0)
                for pwr, coeff in ad.items():
                    v += coeff * mpmath.mpf(n)**pwr
                return v
            return fn

        def make_beta(bc):
            def fn(n):
                return sum(c * mpmath.mpf(n)**i for i, c in enumerate(bc))
            return fn

        alpha_fn = make_alpha(alpha_dict)
        beta_fn = make_beta(beta_coeffs)

        try:
            cf, match, digs = verify_cf_mpmath(
                alpha_fn, beta_fn, VER_DEPTH, tgt_mp, k_rats, VER_DPS)
            if match and digs >= 15:
                print(f'    MATCH  {name}')
                print(f'           -> {match}  ({digs} digits)')
                print(f'           CF = {mpmath.nstr(cf, 25)}')
                all_verified.append(dict(
                    search='D1', name=name, match=match, digits=digs,
                    cf=str(mpmath.nstr(cf, 30)),
                    alpha=str(alpha_dict), beta=beta_coeffs,
                ))
            else:
                # Also try PSLQ against z3 and 1/z3
                z3v = tgt_mp['z3']
                for base_name, base_val in [('z3', z3v), ('1/z3', 1/z3v)]:
                    for kn in range(1, 25):
                        for kd in range(1, 9):
                            d = abs(cf - mpmath.mpf(kn)/kd * base_val)
                            if d == 0:
                                dg = VER_DPS
                            elif d > 0 and d < mpmath.mpf(10)**(-10):
                                dg = int(-mpmath.log10(d))
                            else:
                                continue
                            if dg >= 10:
                                lab = f'{kn}/{kd}*{base_name}' if kd > 1 else f'{kn}*{base_name}'
                                print(f'    WEAK   {name}')
                                print(f'           -> {lab}  ({dg} digits)')
                                break
                        else:
                            continue
                        break
                else:
                    print(f'    miss   {name}')
                    print(f'           CF = {mpmath.nstr(cf, 20)}')
        except Exception as e:
            print(f'    ERROR  {name}: {e}')

    # ── D2: Parametric search around (2n+1) factor forms ──
    print(f'\n  D2: Parametric around (2n+1)(An^2+Bn+C) with alpha sub-leading')
    print(f'  {"─" * 60}')
    print(f'  alpha(n) = -n^6 + e5*n^5 + e4*n^4 + e3*n^3')
    print(f'  beta(n) = (2n+1)(An^2+Bn+C)')
    print(f'  A in [1,50], B in [-50,50], C in [1,30]')
    print(f'  e5 in [-5,5], e4 in [-5,5], e3 in [-3,3]')

    tgt_arr, tgt_names, _ = init_targets_float(extra_k=True)
    D2_DEPTH = 50
    D2_THRESH = 1e-8

    hits_d2 = []
    seen_d2 = set()
    t0 = time.time()
    count = 0

    e_range5 = range(-5, 6)
    e_range4 = range(-5, 6)
    e_range3 = range(-3, 4)
    A_range = range(1, 51)
    B_range = range(-50, 51)
    C_range = range(1, 31)

    total_d2 = len(e_range5) * len(e_range4) * len(e_range3)
    total_d2 *= len(A_range) * len(B_range)
    # C and B_low are inner
    print(f'  Outer blocks: {len(e_range5)*len(e_range4)*len(e_range3)*len(A_range)*len(B_range):,}')

    # For this search, inner vectorisation is over C only (small)
    c_arr = np.arange(1, 31, dtype=np.float64)

    for e5 in e_range5:
        for e4 in e_range4:
            for e3 in e_range3:
                for A in A_range:
                    for B in B_range:
                        count += 1
                        if count % 100000 == 0:
                            el = time.time() - t0
                            td = len(e_range5)*len(e_range4)*len(e_range3)*len(A_range)*len(B_range)
                            pct = 100*count/td
                            print(f'    [{pct:5.1f}%] t={el:.0f}s '
                                  f'hits={len(hits_d2)}', flush=True)

                        D = D2_DEPTH
                        # beta(n) = (2n+1)(An^2+Bn+C) = 2An^3+(3A+2B)n^2+(A+3B+2C)n+C
                        # but C varies. Split:
                        # beta(n) = 2A*n^3 + (3A+2B)*n^2 + (A+3B)*n + 2*C*n + C
                        #         = [2A*n^3 + (3A+2B)*n^2 + (A+3B)*n] + C*(2n+1)
                        b_fixed_n = lambda n: 2*A*n**3 + (3*A+2*B)*n**2 + (A+3*B)*n
                        # The C part: C*(2n+1)

                        # alpha(n) = -n^6 + e5*n^5 + e4*n^4 + e3*n^3
                        def alpha_n(n):
                            return -n**6 + e5*n**5 + e4*n**4 + e3*n**3

                        # val[c] for each C value
                        n_d = D
                        val = b_fixed_n(n_d) + c_arr * (2*n_d + 1)
                        for n in range(D - 1, 0, -1):
                            bn = b_fixed_n(n) + c_arr * (2*n + 1)
                            an1 = alpha_n(n + 1)
                            with np.errstate(divide='ignore', invalid='ignore'):
                                val = bn + an1 / val

                        # CF = beta(0) + alpha(1)/val = C + alpha(1)/val
                        a1 = alpha_n(1)
                        with np.errstate(divide='ignore', invalid='ignore'):
                            cf = c_arr + a1 / val  # shape (30,)

                        # Check against targets
                        with np.errstate(invalid='ignore'):
                            diff = np.abs(cf[:, np.newaxis]
                                          - tgt_arr[np.newaxis, :])
                            mask = diff < D2_THRESH

                        if not mask.any():
                            continue

                        for ci, ti in zip(*np.where(mask)):
                            Cv = int(c_arr[ci])
                            key = (e5, e4, e3, A, B, Cv)
                            if key in seen_d2:
                                continue
                            seen_d2.add(key)

                            # Expand beta fully
                            b3 = 2*A
                            b2 = 3*A + 2*B
                            b1 = A + 3*B + 2*Cv
                            b0 = Cv
                            is_pure = (e5 == 0 and e4 == 0 and e3 == 0)
                            is_apery = (is_pure and A == 17 and B == 17 and Cv == 5)

                            hits_d2.append(dict(
                                e5=e5, e4=e4, e3=e3, A=A, B=B, Cv=Cv,
                                b3=b3, b2=b2, b1=b1, b0=b0,
                                target=tgt_names[ti],
                                cf=float(cf[ci]),
                                diff=float(diff[ci, ti]),
                                is_pure=is_pure,
                            ))
                            tag = 'APERY' if is_apery else ('pure ' if is_pure else 'mixed')
                            print(f'    [{tag:5s}] e=({e5},{e4},{e3}) '
                                  f'A={A} B={B} C={Cv} -> {tgt_names[ti]}  '
                                  f'd={float(diff[ci,ti]):.2e}', flush=True)

    t_d2 = time.time() - t0
    print(f'\n  D2 Phase 1: {len(hits_d2)} hits in {t_d2:.0f}s')

    # Verify D2 hits
    if hits_d2:
        print(f'\n  D2 Phase 2: verifying {len(hits_d2)} hits...')
        mpmath.mp.dps = VER_DPS + 30

        for h in hits_d2:
            e5, e4, e3 = h['e5'], h['e4'], h['e3']
            b3, b2, b1, b0 = h['b3'], h['b2'], h['b1'], h['b0']

            def af(n, _e5=e5, _e4=e4, _e3=e3):
                nn = mpmath.mpf(n)
                return -nn**6 + _e5*nn**5 + _e4*nn**4 + _e3*nn**3

            def bf(n, _b3=b3, _b2=b2, _b1=b1, _b0=b0):
                nn = mpmath.mpf(n)
                return _b3*nn**3 + _b2*nn**2 + _b1*nn + _b0

            try:
                cf, match, digs = verify_cf_mpmath(
                    af, bf, VER_DEPTH, tgt_mp, k_rats, VER_DPS)
                if match and digs >= 25:
                    is_apery = (e5==0 and e4==0 and e3==0
                                and h['A']==17 and h['B']==17 and h['Cv']==5)
                    tag = 'APERY  ' if is_apery else 'NEW!!!'
                    print(f'    VERIFIED [{tag}] e=({e5},{e4},{e3}) '
                          f'A={h["A"]} B={h["B"]} C={h["Cv"]}')
                    print(f'      -> {match}  ({digs}d)')
                    print(f'      CF = {mpmath.nstr(cf, 25)}')
                    all_verified.append(dict(
                        search='D2', **h, match=match, digits=digs,
                        cf_hp=str(mpmath.nstr(cf, 30)),
                    ))
                else:
                    pass  # silent reject
            except:
                pass

    print(f'\n  Search D total verified: {len(all_verified)}')
    _save_results('search_d_zeta3_results.json', 'D', 0,
                  hits_d2, all_verified, time.time() - t0)
    return all_verified


# ══════════════════════════════════════════════════════════════════════════
# SEARCH E: HIGHER DEGREE PAIRS WITH (2n+1) CONSTRAINT
# ══════════════════════════════════════════════════════════════════════════

def search_E():
    """
    Search at degree pairs (6,4) and (8,4) with (2n+1) factor in beta.

    E1: deg(alpha)=6, deg(beta)=4
        alpha(n) = -C*n^6, beta(n) = (2n+1)(An^3+Bn^2+Cn1*n+D)
        Expanded: beta = 2An^4 + (3A+2B)n^3 + (A+3B+2C1)n^2 + (B+3C1+2D)n + D
    E2: deg(alpha)=8, deg(beta)=4
        alpha(n) = -C*n^8, beta(n) = (2n+1)(An^3+Bn^2+C1*n+D)
    """
    import mpmath

    print_banner('SEARCH E: Higher degrees (6,4) and (8,4) with (2n+1) factor')

    VER_DEPTH = 500
    VER_DPS = 50
    k_rats = [(p, q) for p in range(1, 25) for q in range(1, 9)
              if gcd(p, q) == 1 and p/q <= 25]
    tgt_arr, tgt_names, _ = init_targets_float(extra_k=True)
    tgt_mp = init_targets_mpmath(VER_DPS)

    PRE_DEPTH = 50
    PRE_THRESH = 1e-8

    all_verified = []

    for adeg, label in [(6, 'E1: deg(a)=6, deg(b)=4'),
                         (8, 'E2: deg(a)=8, deg(b)=4')]:
        print(f'\n  {label}')
        print(f'  alpha(n) = -C*n^{adeg}, beta(n) = (2n+1)(An^3+Bn^2+Dn+E)')
        print(f'  {"─" * 60}')

        C_vals = range(1, 6) if adeg == 6 else range(1, 4)
        A_range = range(1, 31)
        B_range = range(-30, 31)
        # D and E are inner (vectorised)
        D_range = np.arange(-30, 31, dtype=np.float64)
        E_range = np.arange(1, 21, dtype=np.float64)

        D_col = D_range[:, np.newaxis]  # (61, 1)
        E_row = E_range[np.newaxis, :]  # (1, 20)

        total = len(C_vals) * len(A_range) * len(B_range)
        print(f'  Outer blocks: {total:,}  (C x A x B)')
        print(f'  Inner grid:   {len(D_range)} x {len(E_range)} = '
              f'{len(D_range)*len(E_range):,}  (D x E)')

        hits = []
        seen = set()
        count = 0
        t0 = time.time()

        for C in C_vals:
            for A in A_range:
                for B in B_range:
                    count += 1
                    if count % 5000 == 0:
                        el = time.time() - t0
                        pct = 100*count/total
                        print(f'    [{pct:5.1f}%] t={el:.0f}s '
                              f'hits={len(hits)}', flush=True)

                    # beta(n) = (2n+1)(An^3+Bn^2+Dn+E)
                    # = 2An^4 + (3A+2B)n^3 + (A+3B)n^2 + Bn
                    #   + (2D)n^2 + (3D+2E)n + E   ... actually:
                    # = 2An^4 + (3A+2B)n^3 + (A+3B+2D)n^2 + (B+3D+2E)n + E
                    # Fixed part (no D,E): 2An^4 + (3A+2B)n^3 + (A+3B)n^2 + Bn
                    # D part: 2D*n^2 + 3D*n = D*(2n^2+3n)
                    # E part: 2E*n + E = E*(2n+1)

                    dep = PRE_DEPTH
                    # Start: val = beta(dep)
                    def beta_fixed(n):
                        return 2*A*n**4 + (3*A+2*B)*n**3 + (A+3*B)*n**2 + B*n

                    val = (beta_fixed(dep)
                           + D_col * (2*dep**2 + 3*dep)
                           + E_row * (2*dep + 1))

                    for n in range(dep - 1, 0, -1):
                        bn = (beta_fixed(n)
                              + D_col * (2*n**2 + 3*n)
                              + E_row * (2*n + 1))
                        an1 = -C * (n + 1)**adeg
                        with np.errstate(divide='ignore', invalid='ignore'):
                            val = bn + an1 / val

                    # CF = beta(0) + alpha(1)/val = E + (-C)/val
                    a1 = -C * 1**adeg
                    with np.errstate(divide='ignore', invalid='ignore'):
                        cf = E_row + a1 / val

                    mask, diff = check_matches(cf, tgt_arr, PRE_THRESH)
                    if not mask.any():
                        continue

                    for i, j, t in zip(*np.where(mask)):
                        Di = int(D_range[i])
                        Ej = int(E_range[j])
                        key = (C, A, B, Di, Ej)
                        if key in seen:
                            continue
                        seen.add(key)

                        # Full beta coefficients
                        b4 = 2*A
                        b3 = 3*A + 2*B
                        b2 = A + 3*B + 2*Di
                        b1 = B + 3*Di + 2*Ej
                        b0 = Ej

                        hits.append(dict(
                            adeg=adeg, C=C, A=A, B=B, D=Di, E=Ej,
                            b4=b4, b3=b3, b2=b2, b1=b1, b0=b0,
                            target=tgt_names[t],
                            cf=float(cf[i, j]),
                            diff=float(diff[i, j, t]),
                        ))
                        print(f'    [HIT] C={C} A={A} B={B} D={Di} E={Ej}'
                              f' -> {tgt_names[t]}  d={float(diff[i,j,t]):.2e}',
                              flush=True)

        t_p1 = time.time() - t0
        print(f'\n  {label} Phase 1: {len(hits)} hits in {t_p1:.0f}s')

        # Phase 2 verification
        if hits:
            print(f'  Verifying {len(hits)} hits...')
            mpmath.mp.dps = VER_DPS + 30

            for h in hits:
                ad = h['adeg']
                Cv = h['C']
                b4,b3,b2,b1,b0 = h['b4'],h['b3'],h['b2'],h['b1'],h['b0']

                def af(n, _C=Cv, _ad=ad):
                    return -_C * mpmath.mpf(n)**_ad

                def bf(n, _b4=b4, _b3=b3, _b2=b2, _b1=b1, _b0=b0):
                    nn = mpmath.mpf(n)
                    return _b4*nn**4 + _b3*nn**3 + _b2*nn**2 + _b1*nn + _b0

                try:
                    cf, match, digs = verify_cf_mpmath(
                        af, bf, VER_DEPTH, tgt_mp, k_rats, VER_DPS)
                    if match and digs >= 25:
                        print(f'    VERIFIED C={Cv} A={h["A"]} B={h["B"]} '
                              f'D={h["D"]} E={h["E"]}')
                        print(f'      -> {match}  ({digs}d)')
                        print(f'      CF = {mpmath.nstr(cf, 25)}')
                        all_verified.append(dict(
                            search=label[:2], **h,
                            match=match, digits=digs,
                            cf_hp=str(mpmath.nstr(cf, 30)),
                        ))
                    else:
                        pass
                except:
                    pass

    print(f'\n  Search E total verified: {len(all_verified)}')
    _save_results('search_e_zeta3_results.json', 'E', 0, [],
                  all_verified, time.time())
    return all_verified


# ══════════════════════════════════════════════════════════════════════════
# SHARED VERIFICATION & IO
# ══════════════════════════════════════════════════════════════════════════

def _verify_hits(hits, ver_depth, ver_dps, k_rats, alpha_deg=6):
    """Verify pre-filter hits from Search C using mpmath."""
    import mpmath
    if not hits:
        return []

    print(f'\n  Phase 2: verifying {len(hits)} hit(s) at '
          f'depth {ver_depth}, {ver_dps} digits...')

    tgt_mp = init_targets_mpmath(ver_dps)
    verified = []

    for h in hits:
        C  = h['C']
        b3, b2, b1, b0 = h['b3'], h['b2'], h['b1'], h['b0']

        def af(n, _C=C):
            return -_C * mpmath.mpf(n)**alpha_deg

        def bf(n, _b3=b3, _b2=b2, _b1=b1, _b0=b0):
            nn = mpmath.mpf(n)
            return _b3*nn**3 + _b2*nn**2 + _b1*nn + _b0

        try:
            cf, match, digs = verify_cf_mpmath(
                af, bf, ver_depth, tgt_mp, k_rats, ver_dps)
        except:
            continue

        is_a = (C == 1 and b3 == 34 and b2 == 51 and b1 == 27 and b0 == 5)
        tag = 'APERY  ' if is_a else 'NEW!!!'

        if match and digs >= 25:
            fac = ' (2n+1)' if h.get('has_2n1') else ''
            print(f'  VERIFIED [{tag}] C={C} b=({b3},{b2},{b1},{b0}){fac}')
            print(f'    -> {match}  ({digs}d)')
            verified.append(dict(**h, match=match, digits=digs,
                                 cf_hp=str(mpmath.nstr(cf, 30))))
        else:
            pass  # silent

    print(f'  Verified: {len(verified)} / {len(hits)}')
    return verified


def _save_results(filename, search_id, n_cand, hits, verified, elapsed):
    out = dict(
        search=search_id,
        n_candidates=n_cand,
        n_prefilter=len(hits),
        n_verified=len(verified),
        verified=verified,
        elapsed_s=elapsed,
    )
    with open(filename, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f'  Results saved -> {filename}')


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print('Usage: python _search_comprehensive_zeta3.py [C|D|E|ALL]')
        sys.exit(1)

    mode = sys.argv[1].upper()
    t0 = time.time()

    all_results = {}

    if mode in ('C', 'ALL'):
        all_results['C'] = search_C()

    if mode in ('D', 'ALL'):
        all_results['D'] = search_D()

    if mode in ('E', 'ALL'):
        all_results['E'] = search_E()

    # Final summary
    print_banner('GRAND SUMMARY')
    total_verified = sum(len(v) for v in all_results.values())
    for sid, vlist in all_results.items():
        n_new = sum(1 for v in vlist
                    if not (v.get('C') == 1 and v.get('b3') == 34
                            and v.get('b2') == 51))
        print(f'  Search {sid}: {len(vlist)} verified  ({n_new} new)')
    print(f'\n  Total verified: {total_verified}')
    print(f'  Total time: {time.time()-t0:.0f}s')

    new_total = sum(
        sum(1 for v in vlist
            if not (v.get('C') == 1 and v.get('b3') == 34
                    and v.get('b2') == 51))
        for vlist in all_results.values()
    )
    if new_total > 0:
        print(f'\n  *** {new_total} NEW zeta(3) PCFs DISCOVERED! ***')
    else:
        print(f'\n  Apery remains the unique known polynomial CF for zeta(3).')


if __name__ == '__main__':
    main()
