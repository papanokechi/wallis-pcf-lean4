"""
Phase 2 Track B: V_quad Systematic Classification
Cluster the 400+ unidentified quadratic GCF constants against known families.
"""
import mpmath
import json
from collections import defaultdict

mpmath.mp.dps = 250

# ── Known constants to test against ──
pi = mpmath.pi
e = mpmath.e
ln2 = mpmath.log(2)
ln3 = mpmath.log(3)
z2 = mpmath.pi**2 / 6  # zeta(2)
z3 = mpmath.zeta(3)
cat = mpmath.catalan
gamma = mpmath.euler
phi = (1 + mpmath.sqrt(5)) / 2
sqrt2 = mpmath.sqrt(2)
sqrt3 = mpmath.sqrt(3)
sqrt5 = mpmath.sqrt(5)

CONSTANTS = {
    'pi': pi, '1/pi': 1/pi, 'pi^2': pi**2, 'pi^2/6': z2,
    'sqrt(pi)': mpmath.sqrt(pi),
    'e': e, '1/e': 1/e, 'e^2': e**2,
    'ln2': ln2, 'ln3': ln3, 'ln(3/2)': mpmath.log(mpmath.mpf(3)/2),
    'zeta(3)': z3, 'zeta(3)/pi^2': z3/pi**2,
    'catalan': cat, 'catalan/pi': cat/pi,
    'gamma': gamma,
    'phi': phi, 'sqrt(2)': sqrt2, 'sqrt(3)': sqrt3, 'sqrt(5)': sqrt5,
    '2/pi': 2/pi, '4/pi': 4/pi, 'pi/4': pi/4, 'pi/2': pi/2,
    'pi/3': pi/3, 'pi/6': pi/6,
    'pi*sqrt(2)': pi*sqrt2, 'pi*sqrt(3)': pi*sqrt3,
    'ln(2)/pi': ln2/pi, 'pi*ln2': pi*ln2,
    'e*pi': e*pi, 'e/pi': e/pi,
    'sqrt(2)*pi': sqrt2*pi, 'sqrt(3)/2': sqrt3/2,
    'ln(phi)': mpmath.log(phi), 'phi^2': phi**2,
}

# ── Integer multipliers to try ──
MULTS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 16, 20, 24, 30, 32]


def evaluate_gcf(A, B, C, depth=2000):
    """Evaluate GCF with b(n) = An^2 + Bn + C, a(n) = 1."""
    val = mpmath.mpf(A * depth**2 + B * depth + C)
    for n in range(depth - 1, 0, -1):
        bn = A * n**2 + B * n + C
        val = mpmath.mpf(bn) + 1 / val
    b0 = C
    return mpmath.mpf(b0) + 1 / val


def identify_constant(val, threshold=30):
    """Try to match val against known constants with integer multipliers."""
    best = None
    for name, const in CONSTANTS.items():
        if const == 0:
            continue
        for k in MULTS:
            for sign in [1, -1]:
                target = sign * k * const
                if abs(target) < 1e-10:
                    continue
                # Direct match
                diff = abs(val - target)
                if diff > 0 and diff < mpmath.mpf(10)**(-threshold):
                    digits = -int(mpmath.log10(diff))
                    label = f"{'-' if sign < 0 else ''}{k}*{name}" if k > 1 else f"{'-' if sign < 0 else ''}{name}"
                    if best is None or digits > best[1]:
                        best = (label, digits)
                # Ratio match: val/const
                ratio = val / target
                rdiff = abs(ratio - 1)
                if rdiff > 0 and rdiff < mpmath.mpf(10)**(-threshold):
                    digits = -int(mpmath.log10(rdiff))
                    label = f"{'-' if sign < 0 else ''}{k}*{name}" if k > 1 else f"{'-' if sign < 0 else ''}{name}"
                    if best is None or digits > best[1]:
                        best = (label, digits)
    return best


def main():
    print("PHASE 2 TRACK B: V_quad Systematic Classification")
    print("=" * 70)
    print()

    # Sweep quadratic GCFs: b(n) = An^2 + Bn + C, a(n) = 1
    # Focus on A=1 (monic) with various B, C
    results = []
    identified = 0
    unidentified = 0

    A_range = range(1, 4)
    B_range = range(-8, 9)
    C_range = range(1, 10)

    total = sum(1 for _ in A_range for _ in B_range for _ in C_range)
    count = 0

    for A in range(1, 4):
        for B in range(-8, 9):
            for C in range(1, 10):
                count += 1
                # Check discriminant for convergence
                disc = B**2 - 4*A*C
                try:
                    val = evaluate_gcf(A, B, C, depth=2000)
                except (ZeroDivisionError, mpmath.mp.NoConvergence):
                    continue

                if not mpmath.isfinite(val) or abs(val) > 1e6 or abs(val) < 1e-6:
                    continue

                match = identify_constant(val, threshold=25)
                entry = {
                    'A': A, 'B': B, 'C': C,
                    'disc': disc,
                    'value': str(mpmath.nstr(val, 50)),
                    'match': match[0] if match else None,
                    'digits': match[1] if match else 0,
                }
                results.append(entry)

                if match and match[1] >= 25:
                    identified += 1
                else:
                    unidentified += 1

    # Summary
    print(f"Total evaluated: {len(results)}")
    print(f"Identified:      {identified}")
    print(f"Unidentified:    {unidentified}")
    print()

    # Group identified by constant
    by_const = defaultdict(list)
    for r in results:
        if r['match']:
            by_const[r['match']].append(r)

    print("IDENTIFIED CONSTANTS:")
    print("-" * 50)
    for name in sorted(by_const.keys()):
        entries = by_const[name]
        print(f"  {name}: {len(entries)} GCFs")
        for e in entries[:3]:
            print(f"    A={e['A']}, B={e['B']}, C={e['C']} ({e['digits']}d)")
    print()

    # Cluster unidentified by value proximity
    unid = [r for r in results if not r['match']]
    unid.sort(key=lambda x: float(mpmath.mpf(x['value'])))

    # Find clusters (values within 1e-20 of each other)
    clusters = []
    if unid:
        current_cluster = [unid[0]]
        for i in range(1, len(unid)):
            v1 = mpmath.mpf(unid[i-1]['value'])
            v2 = mpmath.mpf(unid[i]['value'])
            if abs(v1 - v2) < mpmath.mpf('1e-20'):
                current_cluster.append(unid[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [unid[i]]
        clusters.append(current_cluster)

    multi_clusters = [c for c in clusters if len(c) > 1]
    print(f"UNIDENTIFIED VALUE CLUSTERS (same value, different params): {len(multi_clusters)}")
    print("-" * 50)
    for cl in multi_clusters[:15]:
        val = cl[0]['value'][:30]
        params = [(e['A'], e['B'], e['C']) for e in cl]
        print(f"  val={val}...  params={params}")
    print()

    # PSLQ attempt on top unidentified
    print("PSLQ ANALYSIS on top 20 unidentified constants:")
    print("-" * 50)
    basis_names = ['1', 'pi', 'pi^2', 'ln2', 'zeta3', 'catalan', 'gamma', 'sqrt2', 'phi', 'e']

    euler_e = mpmath.e  # avoid shadowing
    pslq_hits = 0
    for r in unid[:20]:
        val = mpmath.mpf(r['value'])
        vec = [val, mpmath.mpf(1), pi, pi**2, ln2, z3, cat, gamma, sqrt2, phi, euler_e]
        try:
            rel = mpmath.pslq(vec, maxcoeff=1000, tol=mpmath.mpf(10)**(-50))
        except Exception:
            rel = None

        if rel:
            if rel[0] != 0:
                terms = []
                for coeff, name in zip(rel[1:], basis_names):
                    if coeff != 0:
                        terms.append(f"({coeff})*{name}")
                formula = " + ".join(terms)
                check = sum(c * b for c, b in zip(rel, vec))
                check_d = -int(mpmath.log10(abs(check))) if abs(check) > 0 else 200
                if check_d >= 40:
                    pslq_hits += 1
                    print(f"  A={r['A']},B={r['B']},C={r['C']}: val = -({formula})/{rel[0]}")
                    print(f"    verification: {check_d}d")

    if pslq_hits == 0:
        print("  No PSLQ relations found (coeffs up to 1000)")

    # Save results
    output = {
        'total': len(results),
        'identified': identified,
        'unidentified': unidentified,
        'clusters': len(multi_clusters),
        'pslq_hits': pslq_hits,
        'results': [{k: v for k, v in r.items()} for r in results[:100]],
    }
    with open('rbg_runs/vquad_cluster_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to rbg_runs/vquad_cluster_results.json")


if __name__ == '__main__':
    main()
