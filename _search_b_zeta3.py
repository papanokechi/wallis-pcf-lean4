#!/usr/bin/env python3
"""
Search B: zeta(3) PCFs at minimum degrees (6,3) -- monomial-alpha exhaustive.

  alpha(n) = -C * n^6        C in {1, 2, 3, 4, 5}
  beta(n)  = b3*n^3 + b2*n^2 + b1*n + b0
    b3 in [1,50], b2 in [-100,100], b1 in [-100,100], b0 in [1,50]
    gcd(b3, b2, b1, b0) = 1  (primitive)

Phase 1: numpy float64 backward eval at depth 50, threshold 1e-8
Phase 2: mpmath verify at depth 500, 50-digit precision

Targets: k * {zeta(3), 1/zeta(3), zeta(3)/pi^3, pi^3/zeta(3),
               L(chi_{-3},3), L(chi_{-3},3)/pi^3}
         for k in {1,2,3,4,5,6,8,10,12}
"""
import numpy as np
import time
import json
from math import gcd
from functools import reduce

# === Configuration ===
C_VALUES       = [1, 2, 3, 4, 5]
B3_MIN, B3_MAX = 1, 50
B2_MIN, B2_MAX = -100, 100
B1_MIN, B1_MAX = -100, 100
B0_MIN, B0_MAX = 1, 50
K_VALUES       = [1, 2, 3, 4, 5, 6, 8, 10, 12]
PRE_DEPTH      = 50
PRE_THRESH     = 1e-8
VER_DEPTH      = 500
VER_DPS        = 50


def gcd_n(*a):
    return reduce(gcd, (abs(x) for x in a))


def main():
    import mpmath

    t_global = time.time()

    # ── Compute target constants at high precision ──
    mpmath.mp.dps = 80
    z3  = mpmath.zeta(3)
    pi  = mpmath.pi
    pi3 = pi ** 3
    # L(chi_{-3}, 3) via Hurwitz zeta:
    #   L(chi_{-3}, s) = [zeta(s,1/3) - zeta(s,2/3)] / 3^s
    L3 = (mpmath.zeta(3, mpmath.mpf(1)/3)
          - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27

    base_targets = {
        'zeta3':          float(z3),
        '1/zeta3':        float(1/z3),
        'zeta3/pi3':      float(z3/pi3),
        'pi3/zeta3':      float(pi3/z3),
        'L(chi-3,3)':     float(L3),
        'L(chi-3,3)/pi3': float(L3/pi3),
    }

    # Flatten: every k * base_target
    tgt_vals, tgt_names = [], []
    for name, val in base_targets.items():
        for k in K_VALUES:
            tgt_vals.append(k * val)
            tgt_names.append(f"{k}*{name}" if k > 1 else name)
    tgt_arr = np.array(tgt_vals, dtype=np.float64)
    N_tgt = len(tgt_arr)

    # ── Print header ──
    nb1 = B1_MAX - B1_MIN + 1   # 201
    nb0 = B0_MAX - B0_MIN + 1   # 50
    nb3 = B3_MAX - B3_MIN + 1   # 50
    nb2 = B2_MAX - B2_MIN + 1   # 201
    n_cand = len(C_VALUES) * nb3 * nb2 * nb1 * nb0
    total_outer = len(C_VALUES) * nb3 * nb2

    print('=' * 78)
    print('  SEARCH B: zeta(3) PCFs at MINIMUM DEGREES (6,3)')
    print('  alpha(n) = -C*n^6,  beta(n) = b3*n^3 + b2*n^2 + b1*n + b0')
    print('=' * 78)
    print(f'\n  Raw candidates:   {n_cand:>15,}')
    print(f'  Outer iterations: {total_outer:>15,}  (C x b3 x b2)')
    print(f'  Inner grid:       {nb1} x {nb0} = {nb1*nb0:,}  (b1 x b0)')
    print(f'  Target values:    {N_tgt:>15}  '
          f'({len(base_targets)} bases x {len(K_VALUES)} multipliers)')
    print(f'  Pre-filter:       depth {PRE_DEPTH}, threshold {PRE_THRESH}')
    print(f'  Verification:     depth {VER_DEPTH}, {VER_DPS}-digit precision')
    print(f'\n  Target constants:')
    for name, val in base_targets.items():
        print(f'    {name:>20s} = {val:.15f}')

    # ── Sanity check: Apery at float64 ──
    print(f'\n  Sanity check (Apery CF, float64, depth {PRE_DEPTH}):')
    C_a, b3_a, b2_a, b1_a, b0_a = 1, 34, 51, 27, 5
    v = float(b3_a * PRE_DEPTH**3 + b2_a * PRE_DEPTH**2
              + b1_a * PRE_DEPTH + b0_a)
    for n in range(PRE_DEPTH - 1, 0, -1):
        bn = b3_a*n**3 + b2_a*n**2 + b1_a*n + b0_a
        v = bn + (-C_a * (n+1)**6) / v
    cf_check = b0_a + (-C_a) / v
    ref = 6.0 / float(z3)
    print(f'    CF value    = {cf_check:.15f}')
    print(f'    6/zeta(3)   = {ref:.15f}')
    print(f'    |diff|      = {abs(cf_check - ref):.2e}  (expect < 1e-14)')
    if abs(cf_check - ref) > 1e-6:
        print('    *** SANITY CHECK FAILED — aborting ***')
        return
    print(f'    OK')

    # ── Phase 1: Vectorised pre-filter ──
    b1_arr = np.arange(B1_MIN, B1_MAX + 1, dtype=np.float64)   # (201,)
    b0_arr = np.arange(B0_MIN, B0_MAX + 1, dtype=np.float64)   # (50,)

    # Pre-shape for broadcasting
    b1_col = b1_arr[:, np.newaxis]   # (201, 1)
    b0_row = b0_arr[np.newaxis, :]   # (1, 50)

    hits = []
    seen = set()
    count = 0
    t0 = time.time()

    print(f'\n  Phase 1: scanning {total_outer:,} outer blocks '
          f'({nb1}x{nb0} = {nb1*nb0:,} each)...')
    print(f'  {"=" * 70}')

    for C in C_VALUES:
        for b3 in range(B3_MIN, B3_MAX + 1):
            for b2 in range(B2_MIN, B2_MAX + 1):
                count += 1
                if count % 10000 == 0:
                    el = time.time() - t0
                    r = count / el if el > 0 else 1
                    eta = (total_outer - count) / r
                    print(f'    [{count:>7,}/{total_outer:,}] '
                          f'{100*count/total_outer:5.1f}%  '
                          f't={el:7.1f}s  eta={eta:6.0f}s  '
                          f'hits={len(hits)}', flush=True)

                # Initialize val = beta(D) for all (b1, b0)
                D = PRE_DEPTH
                base_D = b3 * D**3 + b2 * D**2      # scalar
                val = base_D + b1_col * D + b0_row   # (201, 50)

                # Backward D-1 -> 1
                for n in range(D - 1, 0, -1):
                    base_n = b3 * n**3 + b2 * n**2
                    bn = base_n + b1_col * n + b0_row
                    an1 = -C * (n + 1)**6
                    with np.errstate(divide='ignore', invalid='ignore'):
                        val = bn + an1 / val

                # CF = beta(0) + alpha(1)/val = b0 + (-C)/val
                with np.errstate(divide='ignore', invalid='ignore'):
                    cf = b0_row + (-C) / val   # (201, 50)

                # Check |cf - target| < threshold for every target
                with np.errstate(invalid='ignore'):
                    diff = np.abs(cf[:, :, np.newaxis]
                                  - tgt_arr[np.newaxis, np.newaxis, :])
                    mask = diff < PRE_THRESH

                if not mask.any():
                    continue

                # Extract hit indices
                for i, j, t in zip(*np.where(mask)):
                    b1i = int(b1_arr[i])
                    b0j = int(b0_arr[j])
                    key = (C, b3, b2, b1i, b0j)

                    if key in seen:
                        continue
                    if gcd_n(b3, b2, b1i, b0j) != 1:
                        continue
                    seen.add(key)

                    cfv = float(cf[i, j])
                    dv  = float(diff[i, j, t])
                    is_apery = (key == (1, 34, 51, 27, 5))
                    tag = 'APERY' if is_apery else 'NEW? '

                    # Check (2n+1) factor: beta(-1/2) = 0?
                    bh = -b3 / 8 + b2 / 4 - b1i / 2 + b0j
                    has_factor = abs(bh) < 1e-12

                    hits.append(dict(
                        C=C, b3=b3, b2=b2, b1=b1i, b0=b0j,
                        target=tgt_names[t], cf=cfv, diff=dv,
                        has_2n1=has_factor,
                    ))
                    fstr = '(2n+1)' if has_factor else '      '
                    print(f'    [{tag}] C={C} beta=({b3},{b2},{b1i},{b0j}) '
                          f'{fstr} -> {tgt_names[t]}  diff={dv:.2e}',
                          flush=True)

    t_phase1 = time.time() - t0
    print(f'\n  Phase 1 complete: {len(hits)} hit(s) in {t_phase1:.1f}s')

    # ── Phase 2: mpmath verification ──
    if not hits:
        print('\n  No pre-filter hits. Apery should have appeared — check code.')
        verified = []
    else:
        print(f'\n  {"=" * 70}')
        print(f'  Phase 2: verifying {len(hits)} hit(s) at '
              f'depth {VER_DEPTH}, {VER_DPS} digits...')
        print(f'  {"=" * 70}')

        mpmath.mp.dps = VER_DPS + 30
        z3v  = mpmath.zeta(3)
        piv  = mpmath.pi
        pi3v = piv ** 3
        L3v  = (mpmath.zeta(3, mpmath.mpf(1)/3)
                - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27

        vtgts = {
            'zeta3':          z3v,
            '1/zeta3':        1 / z3v,
            'zeta3/pi3':      z3v / pi3v,
            'pi3/zeta3':      pi3v / z3v,
            'L(chi-3,3)':     L3v,
            'L(chi-3,3)/pi3': L3v / pi3v,
        }

        verified = []
        for h in hits:
            C  = h['C']
            b3, b2, b1, b0 = h['b3'], h['b2'], h['b1'], h['b0']

            # Backward evaluation at high depth + precision
            n = VER_DEPTH
            val = mpmath.mpf(b3*n**3 + b2*n**2 + b1*n + b0)
            for n in range(VER_DEPTH - 1, 0, -1):
                bn  = b3*n**3 + b2*n**2 + b1*n + b0
                an1 = -C * (n + 1)**6
                val = mpmath.mpf(bn) + mpmath.mpf(an1) / val
            cf_hp = mpmath.mpf(b0) + mpmath.mpf(-C) / val

            # Match against all targets
            best_name, best_digs = None, 0
            for tn, tv in vtgts.items():
                for k in K_VALUES:
                    d = abs(cf_hp - k * tv)
                    if d == 0:
                        # Exact match to working precision
                        dg = VER_DPS + 20
                        lab = f'{k}*{tn}' if k > 1 else tn
                        if dg > best_digs:
                            best_digs, best_name = dg, lab
                    elif d < mpmath.mpf(10)**(-15):
                        dg = int(-mpmath.log10(d))
                        lab = f'{k}*{tn}' if k > 1 else tn
                        if dg > best_digs:
                            best_digs, best_name = dg, lab

            is_a = (C == 1 and b3 == 34 and b2 == 51
                    and b1 == 27 and b0 == 5)
            tag = 'APERY  ' if is_a else 'NEW!!!'

            if best_name and best_digs >= 25:
                verified.append(dict(
                    **h,
                    match=best_name, digits=best_digs,
                    cf_hp=str(mpmath.nstr(cf_hp, 30)),
                ))
                fstr = '(2n+1)' if h.get('has_2n1') else ''
                print(f'\n  VERIFIED [{tag}] C={C}  '
                      f'beta=({b3},{b2},{b1},{b0})  {fstr}')
                print(f'    -> {best_name}  ({best_digs} digits)')
                print(f'    CF = {mpmath.nstr(cf_hp, 25)}')
            else:
                print(f'  REJECTED  C={C} beta=({b3},{b2},{b1},{b0})'
                      f'  (best: {best_digs}d, {best_name})')

        print(f'\n  Phase 2 done: {len(verified)} verified out of '
              f'{len(hits)} pre-filter hits')

    # ── Summary ──
    t_total = time.time() - t_global
    print(f'\n{"=" * 78}')
    print(f'  FINAL RESULTS')
    print(f'{"=" * 78}')
    print(f'  Search space:      {n_cand:>15,}  candidates')
    print(f'  Pre-filter hits:   {len(hits):>15}')
    print(f'  Verified hits:     {len(verified):>15}')
    print(f'  Total time:        {t_total:>12.1f} s')

    if verified:
        print(f'\n  Verified zeta(3)-related PCFs:')
        print(f'  {"=" * 70}')
        for v in verified:
            is_a = (v['C'] == 1 and v['b3'] == 34 and v['b2'] == 51
                    and v['b1'] == 27 and v['b0'] == 5)
            tag = 'KNOWN (Apery 1979)' if is_a else '*** NEW DISCOVERY ***'
            fac = '  [beta has (2n+1) factor]' if v.get('has_2n1') else ''
            print(f'    {tag}{fac}')
            print(f'      alpha(n) = -{v["C"]}*n^6')
            b3, b2, b1, b0 = v['b3'], v['b2'], v['b1'], v['b0']
            sign_b2 = f'+{b2}' if b2 >= 0 else str(b2)
            sign_b1 = f'+{b1}' if b1 >= 0 else str(b1)
            print(f'      beta(n)  = {b3}n^3 {sign_b2}n^2 {sign_b1}n +{b0}')
            print(f'      CF -> {v["match"]}  ({v["digits"]} digits)')
            print(f'      CF value = {v.get("cf_hp", "?")}')

        new_hits = [v for v in verified
                    if not (v['C'] == 1 and v['b3'] == 34 and v['b2'] == 51
                            and v['b1'] == 27 and v['b0'] == 5)]
        if new_hits:
            print(f'\n  *** {len(new_hits)} NEW zeta(3) PCF(s) DISCOVERED! ***')
        else:
            print(f'\n  Apery is the UNIQUE zeta(3) PCF in this search space.')
    else:
        print('\n  No verified hits.')

    # ── Save ──
    out = dict(
        params=dict(
            C=C_VALUES,
            b3=[B3_MIN, B3_MAX], b2=[B2_MIN, B2_MAX],
            b1=[B1_MIN, B1_MAX], b0=[B0_MIN, B0_MAX],
            pre_depth=PRE_DEPTH, pre_thresh=PRE_THRESH,
            ver_depth=VER_DEPTH, ver_dps=VER_DPS,
            k_values=K_VALUES,
        ),
        targets={n: v for n, v in base_targets.items()},
        n_candidates=n_cand,
        n_prefilter_hits=len(hits),
        prefilter_hits=[{k: v for k, v in h.items()} for h in hits],
        n_verified=len(verified),
        verified=[{k: v for k, v in h.items()} for h in verified],
        total_seconds=t_total,
    )
    with open('search_b_zeta3_results.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f'\n  Results saved -> search_b_zeta3_results.json')


if __name__ == '__main__':
    main()
