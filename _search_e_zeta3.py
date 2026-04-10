#!/usr/bin/env python3
"""
Search E: Higher degree pairs with (2n+1) factor constraint.

  E1: deg(alpha)=6, deg(beta)=4: alpha=-C*n^6, beta=(2n+1)(An^3+Bn^2+Dn+E)
  E2: deg(alpha)=8, deg(beta)=4: alpha=-C*n^8, beta=(2n+1)(An^3+Bn^2+Dn+E)

Also re-verifies Batut-Olivier and Apery discovered in Search D.
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
    VER_DEPTH = 500
    VER_DPS = 50
    PRE_DEPTH = 50
    PRE_THRESH = 1e-8

    # Targets
    mpmath.mp.dps = 80
    z3 = mpmath.zeta(3)
    pi = mpmath.pi
    pi3 = pi**3
    cat = mpmath.catalan
    L3 = (mpmath.zeta(3, mpmath.mpf(1)/3)
          - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27

    base = {
        'z3': float(z3), '1/z3': float(1/z3),
        'z3/pi3': float(z3/pi3), 'pi3/z3': float(pi3/z3),
        'L(x-3,3)': float(L3), 'L(x-3,3)/pi3': float(L3/pi3),
        'Cat': float(cat), 'pi': float(pi), 'pi2/6': float(pi**2/6),
    }

    k_rats = [(p, q) for p in range(1, 25) for q in range(1, 9)
              if gcd(p, q) == 1 and p/q <= 25]

    tgt_vals, tgt_names = [], []
    seen_k = {}
    for name, val in base.items():
        sk = set()
        for p, q in k_rats:
            kf = p/q
            if kf in sk:
                continue
            sk.add(kf)
            tgt_vals.append(kf * val)
            lab = f'{p}/{q}*{name}' if q > 1 else (f'{p}*{name}' if p > 1 else name)
            tgt_names.append(lab)
    tgt_arr = np.array(tgt_vals, dtype=np.float64)

    # mpmath targets for verification
    mpmath.mp.dps = VER_DPS + 30
    z3v = mpmath.zeta(3)
    tgt_mp = {
        'z3': z3v, '1/z3': 1/z3v,
        'z3/pi3': z3v/mpmath.pi**3, 'pi3/z3': mpmath.pi**3/z3v,
        'L(x-3,3)': (mpmath.zeta(3, mpmath.mpf(1)/3)
                      - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27,
        'L(x-3,3)/pi3': ((mpmath.zeta(3, mpmath.mpf(1)/3)
                           - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27) / mpmath.pi**3,
        'Cat': mpmath.catalan, 'pi': mpmath.pi, 'pi2/6': mpmath.pi**2/6,
    }

    all_verified = []

    # ══════════════════════════════════════════════════════════════════
    # PART 0: Re-verify Apery and Batut-Olivier from D1 as sanity check
    # ══════════════════════════════════════════════════════════════════
    print('=' * 78)
    print('  SEARCH E: Higher degree pairs + sanity checks')
    print('=' * 78)

    print('\n  Sanity checks (known (6,3) PCFs):')
    known = [
        ('Apery', -1, [5, 27, 51, 34]),
        ('Batut-Olivier', -1, [1, 5, 9, 6]),
    ]
    for name, C, bcoeffs in known:
        mpmath.mp.dps = VER_DPS + 30
        n = VER_DEPTH
        val = sum(c * mpmath.mpf(n)**i for i, c in enumerate(bcoeffs))
        for ni in range(VER_DEPTH - 1, 0, -1):
            bn = sum(c * mpmath.mpf(ni)**i for i, c in enumerate(bcoeffs))
            an1 = C * mpmath.mpf(ni+1)**6
            val = bn + an1 / val
        cf = bcoeffs[0] + C / val

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
                lab = f'{p}/{q}*{tn}' if q > 1 else (f'{p}*{tn}' if p > 1 else tn)
                if dg > best_digs:
                    best_digs, best_name = dg, lab

        print(f'    {name}: CF = {mpmath.nstr(cf, 25)} -> {best_name} ({best_digs}d)')

    # ══════════════════════════════════════════════════════════════════
    # PART 1: (6,4) search
    # alpha(n) = -C*n^6, beta(n) = (2n+1)(An^3 + Bn^2 + Dn + E)
    # Expanded beta:
    #   b4 = 2A, b3 = 3A+2B, b2 = A+3B+2D, b1 = B+3D+2E, b0 = E
    # ══════════════════════════════════════════════════════════════════

    for adeg, part_name in [(6, '(6,4)'), (8, '(8,4)')]:
        print(f'\n  Part {part_name}: alpha(n) = -C*n^{adeg}, '
              f'beta(n) = (2n+1)(An^3+Bn^2+Dn+E)')
        print(f'  {"─" * 60}')

        C_vals = list(range(1, 6)) if adeg == 6 else list(range(1, 4))
        A_range = list(range(1, 31))
        B_range = list(range(-30, 31))
        D_arr = np.arange(-30, 31, dtype=np.float64)
        E_arr = np.arange(1, 21, dtype=np.float64)
        D_col = D_arr[:, np.newaxis]  # (61, 1)
        E_row = E_arr[np.newaxis, :]  # (1, 20)

        total = len(C_vals) * len(A_range) * len(B_range)
        n_cand = total * len(D_arr) * len(E_arr)
        print(f'  C in {C_vals},  A in [1,30],  B in [-30,30]')
        print(f'  D in [-30,30],  E in [1,20]')
        print(f'  Candidates: {n_cand:,}   Outer blocks: {total:,}')

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
                        eta = el * (total - count) / max(count, 1)
                        print(f'    [{pct:5.1f}%] t={el:.0f}s  '
                              f'eta={eta:.0f}s  hits={len(hits)}', flush=True)

                    dep = PRE_DEPTH
                    # beta(n) = (2n+1)(An^3+Bn^2+Dn+E)
                    # = 2An^4 + (3A+2B)n^3 + (A+3B)n^2 + Bn
                    #   + D(2n^2+3n) + E(2n+1)
                    # Fixed(n) = 2An^4 + (3A+2B)n^3 + (A+3B)n^2 + Bn
                    def bfixed(n, _A=A, _B=B):
                        return 2*_A*n**4 + (3*_A+2*_B)*n**3 + (_A+3*_B)*n**2 + _B*n

                    val = (bfixed(dep)
                           + D_col * (2*dep**2 + 3*dep)
                           + E_row * (2*dep + 1))

                    for n in range(dep - 1, 0, -1):
                        bn = (bfixed(n)
                              + D_col * (2*n**2 + 3*n)
                              + E_row * (2*n + 1))
                        an1 = -C * (n+1)**adeg
                        with np.errstate(divide='ignore', invalid='ignore'):
                            val = bn + an1 / val

                    # CF = beta(0) + alpha(1)/val = E + (-C)/val
                    with np.errstate(divide='ignore', invalid='ignore'):
                        cf = E_row + (-C) / val

                    with np.errstate(invalid='ignore'):
                        diff = np.abs(cf[:, :, np.newaxis]
                                      - tgt_arr[np.newaxis, np.newaxis, :])
                        mask = diff < PRE_THRESH

                    if not mask.any():
                        continue

                    for i, j, t in zip(*np.where(mask)):
                        Di = int(D_arr[i])
                        Ej = int(E_arr[j])
                        key = (adeg, C, A, B, Di, Ej)
                        if key in seen:
                            continue
                        seen.add(key)

                        hits.append(dict(
                            adeg=adeg, C=C, A=A, B=B, D=Di, E=Ej,
                            target=tgt_names[t],
                            cf=float(cf[i, j]),
                            diff=float(diff[i, j, t]),
                        ))
                        print(f'    [HIT] C={C} A={A} B={B} D={Di} E={Ej}'
                              f' -> {tgt_names[t]}  d={float(diff[i,j,t]):.2e}',
                              flush=True)

        t_p1 = time.time() - t0
        print(f'\n  {part_name} Phase 1: {len(hits)} hits in {t_p1:.0f}s')

        # Phase 2
        if hits:
            print(f'  Verifying {len(hits)} hits at depth {VER_DEPTH}...')
            mpmath.mp.dps = VER_DPS + 30

            for h in hits:
                ad = h['adeg']
                Cv, Av, Bv, Dv, Ev = h['C'], h['A'], h['B'], h['D'], h['E']
                # Full beta coefficients
                b4 = 2*Av
                b3 = 3*Av + 2*Bv
                b2 = Av + 3*Bv + 2*Dv
                b1 = Bv + 3*Dv + 2*Ev
                b0 = Ev

                n = VER_DEPTH
                val = (b4*mpmath.mpf(n)**4 + b3*mpmath.mpf(n)**3
                       + b2*mpmath.mpf(n)**2 + b1*mpmath.mpf(n) + b0)
                for n in range(VER_DEPTH - 1, 0, -1):
                    bn = (b4*mpmath.mpf(n)**4 + b3*mpmath.mpf(n)**3
                          + b2*mpmath.mpf(n)**2 + b1*mpmath.mpf(n) + b0)
                    an1 = -Cv * mpmath.mpf(n+1)**ad
                    val = bn + an1/val
                cf = mpmath.mpf(b0) + (-Cv)/val

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
                        lab = f'{p}/{q}*{tn}' if q > 1 else (f'{p}*{tn}' if p > 1 else tn)
                        if dg > best_digs:
                            best_digs, best_name = dg, lab

                if best_name and best_digs >= 25:
                    print(f'    VERIFIED  C={Cv} ({Av},{Bv},{Dv},{Ev})')
                    print(f'      beta = {b4}n^4+{b3}n^3+{b2}n^2+{b1}n+{b0}')
                    print(f'      -> {best_name}  ({best_digs}d)')
                    print(f'      CF = {mpmath.nstr(cf, 25)}')
                    all_verified.append(dict(
                        search=part_name, adeg=ad, C=Cv,
                        A=Av, B=Bv, D=Dv, E=Ev,
                        b4=b4, b3=b3, b2=b2, b1=b1, b0=b0,
                        match=best_name, digits=best_digs,
                        cf=str(mpmath.nstr(cf, 30)),
                    ))
                # silent reject otherwise

        print(f'  {part_name} verified: {len([v for v in all_verified if v["search"]==part_name])}')

    # ══════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════════════
    t_total = time.time() - t_global
    print(f'\n{"=" * 78}')
    print(f'  SEARCH E FINAL RESULTS')
    print(f'{"=" * 78}')
    print(f'  Total verified: {len(all_verified)}')
    print(f'  Total time: {t_total:.0f}s')

    for v in all_verified:
        z3_related = 'z3' in v['match'] or '1/z3' in v['match']
        tag = 'ZETA3' if z3_related else 'OTHER'
        print(f'    [{tag}] {v["search"]} C={v["C"]}: '
              f'{v["match"]} ({v["digits"]}d)')

    z3_new = [v for v in all_verified if 'z3' in v['match'] or '1/z3' in v['match']]
    other_new = [v for v in all_verified if 'z3' not in v['match'] and '1/z3' not in v['match']]

    if z3_new:
        print(f'\n  *** {len(z3_new)} zeta(3)-related PCFs at higher degrees! ***')
    else:
        print(f'\n  No zeta(3) PCFs at higher degrees (6,4) or (8,4).')
    if other_new:
        print(f'  Also found {len(other_new)} PCFs for other constants.')

    # Save
    with open('search_e_zeta3_results.json', 'w') as f:
        json.dump(dict(
            verified=all_verified,
            total_time=t_total,
        ), f, indent=2, default=str)
    print(f'  Results saved -> search_e_zeta3_results.json')


if __name__ == '__main__':
    main()
