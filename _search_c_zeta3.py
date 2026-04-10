#!/usr/bin/env python3
"""
Search C: Extended monomial search with rational k-targets.

Fixes the gap from Search B: includes rational k=p/q for p<=24, q<=8
so that Batut-Olivier (CF -> 8/(7*z3)) is caught.

Parameters:
  alpha(n) = -C*n^6,  C in {1,...,10}
  beta(n)  = b3*n^3 + b2*n^2 + b1*n + b0
    b3 in [1,80], b2 in [-150,150], b1 in [-150,150], b0 in [1,80]
    gcd(b3,b2,b1,b0) = 1

Pre-filter:  depth 50, float64, threshold 1e-8
Verify:      depth 500, 50-digit mpmath
"""
import numpy as np
import time
import json
from math import gcd
from functools import reduce

def gcd_n(*a):
    return reduce(gcd, (abs(x) for x in a if x != 0), 0)

def main():
    import mpmath

    t_global = time.time()

    # Config
    C_VALUES = list(range(1, 11))
    B3_MIN, B3_MAX = 1, 80
    B2_MIN, B2_MAX = -150, 150
    B1_MIN, B1_MAX = -150, 150
    B0_MIN, B0_MAX = 1, 80
    PRE_DEPTH = 50
    PRE_THRESH = 1e-8
    VER_DEPTH = 500
    VER_DPS = 50

    # Rational k-values
    k_rats = sorted(set(
        (p, q) for p in range(1, 25) for q in range(1, 9)
        if gcd(p, q) == 1 and 0 < p/q <= 25
    ), key=lambda x: x[0]/x[1])

    # Targets: LEAN pre-filter (only z3 and 1/z3 with rational k)
    # Other constants checked only in Phase 2
    mpmath.mp.dps = 80
    z3 = mpmath.zeta(3)
    pi = mpmath.pi
    cat = mpmath.catalan
    L3 = (mpmath.zeta(3, mpmath.mpf(1)/3)
          - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27

    # Pre-filter targets: only z3 and 1/z3 with rational k
    prefilter_base = {
        'z3': float(z3), '1/z3': float(1/z3),
    }
    tgt_vals, tgt_names = [], []
    for name, val in prefilter_base.items():
        seen_k = set()
        for p, q in k_rats:
            kf = p/q
            if kf in seen_k:
                continue
            seen_k.add(kf)
            tgt_vals.append(kf * val)
            tgt_names.append(f"{p}/{q}*{name}" if q > 1 else
                             (f"{p}*{name}" if p > 1 else name))
    tgt_arr = np.array(tgt_vals, dtype=np.float64)

    # Arrays
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

    print('=' * 78)
    print('  SEARCH C: Extended monomial alpha with rational k-targets')
    print('=' * 78)
    print(f'  C in [1, {max(C_VALUES)}],  b3 in [{B3_MIN},{B3_MAX}],  '
          f'b2 in [{B2_MIN},{B2_MAX}]')
    print(f'  b1 in [{B1_MIN},{B1_MAX}],  b0 in [{B0_MIN},{B0_MAX}]')
    print(f'  Total candidates: {n_cand:>15,}')
    print(f'  Outer blocks:     {total_outer:>15,}')
    print(f'  Targets:          {len(tgt_arr)} (z3 and 1/z3 with '
          f'{len(set(p/q for p,q in k_rats))} rational k-values)')
    print(f'  Post-verify:      also checks pi, Cat, L-values, pi^2/6')
    print(f'  Pre-filter:       depth {PRE_DEPTH}, thresh {PRE_THRESH}')
    print(f'  Verify:           depth {VER_DEPTH}, {VER_DPS} digits')

    # Sanity checks
    print(f'\n  Sanity checks (float64, depth {PRE_DEPTH}):')
    for name, C, b3, b2, b1, b0, expected in [
            ('Apery', 1, 34, 51, 27, 5, 6.0/float(z3)),
            ('Batut-Olivier', 1, 6, 9, 5, 1, 8.0/(7*float(z3)))]:
        v = float(b3*50**3 + b2*50**2 + b1*50 + b0)
        for n in range(49, 0, -1):
            v = (b3*n**3 + b2*n**2 + b1*n + b0) + (-(n+1)**6 * C) / v
        cf = b0 + (-C) / v
        diff = abs(cf - expected)
        print(f'    {name}: CF={cf:.15f} ref={expected:.15f} '
              f'diff={diff:.2e} {"OK" if diff < 1e-6 else "FAIL"}')

    # Phase 1
    hits = []
    seen = set()
    count = 0
    t0 = time.time()
    print(f'\n  Phase 1: scanning {total_outer:,} blocks...')

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

                with np.errstate(invalid='ignore'):
                    diff = np.abs(cf[:, :, np.newaxis]
                                  - tgt_arr[np.newaxis, np.newaxis, :])
                    mask = diff < PRE_THRESH

                if not mask.any():
                    continue

                for i, j, t in zip(*np.where(mask)):
                    b1i = int(b1_arr[i])
                    b0j = int(b0_arr[j])
                    key = (C, b3, b2, b1i, b0j)
                    if key in seen:
                        continue
                    if gcd_n(b3, b2, b1i, b0j) != 1:
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
                    is_bo = (key == (1, 6, 9, 5, 1))
                    tag = 'APERY' if is_apery else ('B-O  ' if is_bo else 'NEW? ')
                    fstr = '(2n+1)' if has_factor else ''
                    print(f'    [{tag}] C={C} b=({b3},{b2},{b1i},{b0j}) '
                          f'{fstr} -> {tgt_names[t]}  d={float(diff[i,j,t]):.2e}',
                          flush=True)

    t_p1 = time.time() - t0
    print(f'\n  Phase 1: {len(hits)} hits in {t_p1:.0f}s')

    # Phase 2
    if not hits:
        print('  ERROR: no pre-filter hits found')
        return

    print(f'\n  Phase 2: verifying {len(hits)} hits at depth {VER_DEPTH}...')
    mpmath.mp.dps = VER_DPS + 30

    # mpmath targets — FULL set for verification
    z3v = mpmath.zeta(3)
    tgt_mp = {
        'z3': z3v, '1/z3': 1/z3v,
        'z3/pi3': z3v/mpmath.pi**3, 'pi3/z3': mpmath.pi**3/z3v,
        'L(x-3,3)': (mpmath.zeta(3, mpmath.mpf(1)/3) - mpmath.zeta(3, mpmath.mpf(2)/3))/27,
        'Cat': mpmath.catalan, 'pi': mpmath.pi, 'pi2/6': mpmath.pi**2/6,
        'ln2': mpmath.log(2),
    }

    verified = []
    for h in hits:
        C = h['C']
        b3, b2, b1, b0 = h['b3'], h['b2'], h['b1'], h['b0']

        n = VER_DEPTH
        val = mpmath.mpf(b3*n**3 + b2*n**2 + b1*n + b0)
        for n in range(VER_DEPTH - 1, 0, -1):
            bn = b3*n**3 + b2*n**2 + b1*n + b0
            an1 = -C * (n+1)**6
            val = mpmath.mpf(bn) + mpmath.mpf(an1)/val
        cf = mpmath.mpf(b0) + mpmath.mpf(-C)/val

        best_name, best_digs = None, 0
        for tn, tv in tgt_mp.items():
            for p, q in k_rats:
                kv = mpmath.mpf(p)/q
                d = abs(cf - kv * tv)
                if d == 0:
                    dg = VER_DPS + 20
                elif d < mpmath.mpf(10)**(-15):
                    dg = int(-mpmath.log10(d))
                else:
                    continue
                lab = f"{p}/{q}*{tn}" if q > 1 else (f"{p}*{tn}" if p > 1 else tn)
                if dg > best_digs:
                    best_digs, best_name = dg, lab

        if best_name and best_digs >= 25:
            is_a = (C==1 and b3==34 and b2==51 and b1==27 and b0==5)
            is_bo = (C==1 and b3==6 and b2==9 and b1==5 and b0==1)
            tag = 'APERY' if is_a else ('B-O  ' if is_bo else 'NEW!!')
            fac = ' (2n+1)' if h.get('has_2n1') else ''
            print(f'    VERIFIED [{tag}] C={C} b=({b3},{b2},{b1},{b0}){fac}')
            print(f'      -> {best_name}  ({best_digs}d)')
            verified.append(dict(**h, match=best_name, digits=best_digs,
                                 cf_hp=str(mpmath.nstr(cf, 30))))

    t_total = time.time() - t_global
    print(f'\n  Phase 2: {len(verified)} verified / {len(hits)} pre-filter')

    # Summary
    print(f'\n{"=" * 78}')
    print(f'  SEARCH C RESULTS')
    print(f'{"=" * 78}')
    print(f'  Candidates:    {n_cand:>15,}')
    print(f'  Pre-filter:    {len(hits):>15}')
    print(f'  Verified:      {len(verified):>15}')
    print(f'  Total time:    {t_total:>12.0f}s')

    known = 0
    for v in verified:
        is_a = (v['C']==1 and v['b3']==34 and v['b2']==51)
        is_bo = (v['C']==1 and v['b3']==6 and v['b2']==9)
        tag = 'KNOWN (Apery)' if is_a else ('KNOWN (B-O)' if is_bo else '*** NEW ***')
        if is_a or is_bo:
            known += 1
        fac = '  [(2n+1) factor]' if v.get('has_2n1') else ''
        print(f'    {tag}{fac}')
        print(f'      a(n)=-{v["C"]}n^6  b(n)={v["b3"]}n^3+{v["b2"]}n^2+{v["b1"]}n+{v["b0"]}')
        print(f'      -> {v["match"]}  ({v["digits"]}d)')

    new = len(verified) - known
    if new > 0:
        print(f'\n  *** {new} NEW zeta(3) PCFs! ***')
    else:
        print(f'\n  Both known PCFs (Apery + Batut-Olivier) found.')
        print(f'  No new zeta(3) formulas in this search space.')

    with open('search_c_zeta3_results.json', 'w') as f:
        json.dump(dict(
            candidates=n_cand, prefilter=len(hits),
            verified=[{k:v for k,v in v.items()} for v in verified],
            total_s=t_total,
        ), f, indent=2, default=str)
    print(f'  Saved -> search_c_zeta3_results.json')


if __name__ == '__main__':
    main()
