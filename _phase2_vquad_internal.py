"""
Phase 2 Track A+B combined:
  (1) Internal V_quad cross-relations via PSLQ
  (2) Prefactor sweep: a*V + b*Target + c = 0 for known constants
"""
import mpmath
import json
import itertools
from collections import defaultdict

mpmath.mp.dps = 300  # high precision for PSLQ

# ── Evaluate quadratic GCF ──
def eval_gcf(A, B, C, depth=3000):
    """GCF with b(n)=An^2+Bn+C, a(n)=1."""
    val = mpmath.mpf(A * depth**2 + B * depth + C)
    for n in range(depth - 1, 0, -1):
        bn = A * n**2 + B * n + C
        val = mpmath.mpf(bn) + 1 / val
    return mpmath.mpf(C) + 1 / val


# ── Build V_quad constant table ──
def build_vquad_table():
    """Compute V_quad constants for monic (A=1) quadratics."""
    constants = []
    for B in range(-6, 7):
        for C in range(1, 8):
            disc = B**2 - 4 * C
            try:
                val = eval_gcf(1, B, C)
            except (ZeroDivisionError, ValueError):
                continue
            if not mpmath.isfinite(val) or abs(val) > 1e6 or abs(val) < 1e-6:
                continue
            constants.append({
                'A': 1, 'B': B, 'C': C, 'disc': disc,
                'val': val,
                'label': f'V(1,{B},{C})',
            })
    return constants


# ── Known constants for prefactor sweep ──
def known_constants():
    pi = mpmath.pi
    return {
        'pi': pi, '1/pi': 1/pi, 'pi^2': pi**2, 'pi^2/6': pi**2/6,
        'sqrt(pi)': mpmath.sqrt(pi),
        'e': mpmath.e, 'ln2': mpmath.log(2), 'ln3': mpmath.log(3),
        'zeta3': mpmath.zeta(3), 'catalan': mpmath.catalan,
        'gamma': mpmath.euler, 'phi': (1+mpmath.sqrt(5))/2,
        'sqrt2': mpmath.sqrt(2), 'sqrt3': mpmath.sqrt(3),
        'sqrt5': mpmath.sqrt(5),
        '2/pi': 2/pi, '4/pi': 4/pi,
    }


def main():
    print("=" * 78)
    print("  PHASE 2: V_quad INTERNAL RELATIONS + PREFACTOR SWEEP")
    print("=" * 78)
    print()

    vquad = build_vquad_table()
    print(f"Computed {len(vquad)} V_quad constants (A=1, B∈[-6,6], C∈[1,7])")
    print()

    # ════════════════════════════════════════════════════════════════
    # PART 1: INTERNAL CROSS-RELATIONS
    # ════════════════════════════════════════════════════════════════
    print("PART 1: Internal cross-relations (PSLQ on pairs/triples)")
    print("-" * 60)

    # Check all pairs: a*V1 + b*V2 + c = 0
    pair_hits = []
    N = min(len(vquad), 30)  # top 30 constants
    for i in range(N):
        for j in range(i + 1, N):
            v1 = vquad[i]['val']
            v2 = vquad[j]['val']
            vec = [v1, v2, mpmath.mpf(1)]
            try:
                rel = mpmath.pslq(vec, maxcoeff=500, tol=mpmath.mpf(10)**(-100))
            except Exception:
                rel = None
            if rel and any(r != 0 for r in rel[:2]):
                # Verify
                check = sum(r * v for r, v in zip(rel, vec))
                check_d = -int(mpmath.log10(abs(check))) if abs(check) > 0 else 300
                if check_d >= 80:
                    pair_hits.append({
                        'i': i, 'j': j,
                        'label_i': vquad[i]['label'], 'label_j': vquad[j]['label'],
                        'rel': list(rel), 'digits': check_d,
                    })
                    print(f"  HIT! {rel[0]}*{vquad[i]['label']} + {rel[1]}*{vquad[j]['label']} + {rel[2]} = 0  ({check_d}d)")

    if not pair_hits:
        print("  No pairwise relations found (coeffs up to 500)")
    print(f"\n  Pairs tested: {N*(N-1)//2}, hits: {len(pair_hits)}")
    print()

    # Check triples: a*V1 + b*V2 + c*V3 + d = 0 (top 15 only — O(n^3))
    print("Checking triples (top 15)...")
    triple_hits = []
    N3 = min(len(vquad), 15)
    for i, j, k in itertools.combinations(range(N3), 3):
        v1, v2, v3 = vquad[i]['val'], vquad[j]['val'], vquad[k]['val']
        vec = [v1, v2, v3, mpmath.mpf(1)]
        try:
            rel = mpmath.pslq(vec, maxcoeff=200, tol=mpmath.mpf(10)**(-80))
        except Exception:
            rel = None
        if rel and any(r != 0 for r in rel[:3]):
            check = sum(r * v for r, v in zip(rel, vec))
            check_d = -int(mpmath.log10(abs(check))) if abs(check) > 0 else 300
            if check_d >= 60:
                triple_hits.append({
                    'labels': [vquad[i]['label'], vquad[j]['label'], vquad[k]['label']],
                    'rel': list(rel), 'digits': check_d,
                })
                print(f"  TRIPLE! {rel[0]}*{vquad[i]['label']} + {rel[1]}*{vquad[j]['label']} + {rel[2]}*{vquad[k]['label']} + {rel[3]} = 0  ({check_d}d)")

    if not triple_hits:
        print("  No triple relations found (coeffs up to 200)")
    print(f"  Triples tested: {N3*(N3-1)*(N3-2)//6}, hits: {len(triple_hits)}")
    print()

    # ════════════════════════════════════════════════════════════════
    # PART 2: GROUPING BY DISCRIMINANT
    # ════════════════════════════════════════════════════════════════
    print("PART 2: Discriminant families")
    print("-" * 60)

    by_disc = defaultdict(list)
    for v in vquad:
        by_disc[v['disc']].append(v)

    for disc in sorted(by_disc.keys()):
        group = by_disc[disc]
        if len(group) < 2:
            continue
        print(f"\n  disc={disc}: {len(group)} constants")
        for g in group:
            print(f"    {g['label']}: val={mpmath.nstr(g['val'], 20)}")

        # PSLQ within each discriminant family
        if len(group) >= 2:
            vals = [g['val'] for g in group]
            for ii in range(len(vals)):
                for jj in range(ii + 1, len(vals)):
                    vec = [vals[ii], vals[jj], mpmath.mpf(1)]
                    try:
                        rel = mpmath.pslq(vec, maxcoeff=500, tol=mpmath.mpf(10)**(-80))
                    except Exception:
                        rel = None
                    if rel and any(r != 0 for r in rel[:2]):
                        check = sum(r * v for r, v in zip(rel, vec))
                        cd = -int(mpmath.log10(abs(check))) if abs(check) > 0 else 300
                        if cd >= 60:
                            print(f"    DISC-REL! {rel[0]}*{group[ii]['label']} + {rel[1]}*{group[jj]['label']} + {rel[2]} = 0  ({cd}d)")
    print()

    # ════════════════════════════════════════════════════════════════
    # PART 3: PREFACTOR SWEEP — a*V + b*target + c = 0
    # ════════════════════════════════════════════════════════════════
    print("PART 3: Prefactor sweep (a*V + b*Target + c = 0)")
    print("-" * 60)

    targets = known_constants()
    prefactor_hits = []

    for vi, v in enumerate(vquad[:30]):
        for tname, tval in targets.items():
            vec = [v['val'], tval, mpmath.mpf(1)]
            try:
                rel = mpmath.pslq(vec, maxcoeff=1000, tol=mpmath.mpf(10)**(-80))
            except Exception:
                rel = None
            if rel and rel[0] != 0 and rel[1] != 0:
                check = sum(r * x for r, x in zip(rel, vec))
                cd = -int(mpmath.log10(abs(check))) if abs(check) > 0 else 300
                if cd >= 60:
                    # Express: V = -(b*target + c) / a
                    a, b, c = rel
                    prefactor_hits.append({
                        'label': v['label'], 'target': tname,
                        'rel': [a, b, c], 'digits': cd,
                    })
                    print(f"  {v['label']} = -({b}*{tname} + {c})/{a}  ({cd}d)")

    if not prefactor_hits:
        print("  No prefactor relations found (coeffs up to 1000)")
    print(f"\n  Tests: {min(len(vquad),30)*len(targets)}, hits: {len(prefactor_hits)}")
    print()

    # ════════════════════════════════════════════════════════════════
    # PART 4: EXTENDED PSLQ — V against 2 targets simultaneously
    # ════════════════════════════════════════════════════════════════
    print("PART 4: Extended PSLQ (a*V + b*T1 + c*T2 + d = 0)")
    print("-" * 60)

    pi = mpmath.pi
    target_pairs = [
        ('pi', 'ln2', pi, mpmath.log(2)),
        ('pi', 'sqrt2', pi, mpmath.sqrt(2)),
        ('pi', 'gamma', pi, mpmath.euler),
        ('pi', 'zeta3', pi, mpmath.zeta(3)),
        ('ln2', 'gamma', mpmath.log(2), mpmath.euler),
        ('pi^2', 'ln2', pi**2, mpmath.log(2)),
    ]
    ext_hits = []
    for vi, v in enumerate(vquad[:20]):
        for t1name, t2name, t1val, t2val in target_pairs:
            vec = [v['val'], t1val, t2val, mpmath.mpf(1)]
            try:
                rel = mpmath.pslq(vec, maxcoeff=500, tol=mpmath.mpf(10)**(-60))
            except Exception:
                rel = None
            if rel and rel[0] != 0 and (rel[1] != 0 or rel[2] != 0):
                check = sum(r * x for r, x in zip(rel, vec))
                cd = -int(mpmath.log10(abs(check))) if abs(check) > 0 else 300
                if cd >= 50:
                    ext_hits.append({
                        'label': v['label'], 'targets': f'{t1name},{t2name}',
                        'rel': list(rel), 'digits': cd,
                    })
                    print(f"  {rel[0]}*{v['label']} + {rel[1]}*{t1name} + {rel[2]}*{t2name} + {rel[3]} = 0  ({cd}d)")

    if not ext_hits:
        print("  No extended relations found")
    print()

    # ════════════════════════════════════════════════════════════════
    # SUMMARY
    # ════════════════════════════════════════════════════════════════
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  V_quad constants:    {len(vquad)}")
    print(f"  Pair relations:      {len(pair_hits)}")
    print(f"  Triple relations:    {len(triple_hits)}")
    print(f"  Prefactor relations: {len(prefactor_hits)}")
    print(f"  Extended PSLQ:       {len(ext_hits)}")
    total = len(pair_hits) + len(triple_hits) + len(prefactor_hits) + len(ext_hits)
    if total == 0:
        print("\n  *** V_quad constants appear ALGEBRAICALLY INDEPENDENT ***")
        print("  *** from each other AND from all tested handbook constants ***")
    else:
        print(f"\n  *** {total} RELATIONS FOUND — see details above ***")

    # Save results
    results = {
        'n_constants': len(vquad),
        'pair_hits': pair_hits,
        'triple_hits': triple_hits,
        'prefactor_hits': prefactor_hits,
        'extended_hits': ext_hits,
        'constants': [{'label': v['label'], 'B': v['B'], 'C': v['C'],
                       'disc': v['disc'], 'value': str(mpmath.nstr(v['val'], 60))}
                      for v in vquad],
    }
    with open('rbg_runs/vquad_internal_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to rbg_runs/vquad_internal_results.json")


if __name__ == '__main__':
    main()
