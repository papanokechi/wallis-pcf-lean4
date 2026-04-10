"""
Erdős–Straus Extension to n ≤ 1,000,000
=========================================
Dedicated runner for the #1 priority from peer review:
  "Run the existing pipeline to n ≤ 10⁶ and plot which primes
   (if any) evade all 12 family constructions."

This produces genuinely new empirical data.
"""

import json
import math
import os
import time
from collections import defaultdict, Counter

from unsolved_solver.problems.erdos_straus import ErdosStrausAnalyzer


def run_extension(max_n: int = 1_000_000) -> dict:
    """Run Erdős–Straus coverage analysis up to max_n."""
    print(f"\n{'='*62}")
    print(f"  Erdős–Straus Extension: n <= {max_n:,}")
    print(f"{'='*62}\n")

    t0 = time.time()
    analyzer = ErdosStrausAnalyzer(max_n=max_n)
    sieve_time = time.time() - t0
    print(f"  Sieve built in {sieve_time:.1f}s")

    # Phase 1: Parametric families + divisor-based decomposition
    prog = max(max_n // 10, 1000)
    print(f"Phase 1: Parametric families + divisor decomposition (progress every {prog:,})...")
    coverage = analyzer.analyze_coverage(max_n, progress_every=prog)

    phase1_time = time.time() - t0
    print(f"\n  Phase 1 complete: {phase1_time:.1f}s")
    print(f"  Coverage: {coverage['covered']:,}/{coverage['total']:,} "
          f"({coverage['coverage_pct']:.4f}%)")
    print(f"  Unsolved: {coverage['uncovered']:,}")

    # Phase 2: If any unsolved, try extended a-range in divisor method
    t1 = time.time()
    rescued = {}
    rescued_by_method = defaultdict(int)

    still_unsolved = sorted(analyzer.unsolved_n)
    if still_unsolved:
        print(f"\nPhase 2: Deep divisor search on {len(still_unsolved)} unsolved values...")
        for i, n in enumerate(still_unsolved):
            if i % 200 == 0 and i > 0:
                print(f"    Deep search: {i}/{len(still_unsolved)} "
                      f"(rescued {len(rescued)} so far)")
            for a_off in range(n):
                a = math.ceil(n / 4) + a_off
                if a > 2 * n:
                    break
                dec = analyzer._divisor_decompose(n, a, 'deep_divisor')
                if dec:
                    rescued[n] = str(dec)
                    rescued_by_method['deep_divisor'] += 1
                    analyzer.decompositions[n] = [dec]
                    analyzer.unsolved_n.discard(n)
                    break
        still_unsolved = sorted(analyzer.unsolved_n)
    else:
        print("\nPhase 2: Skipped (all values solved by families + divisor method)")

    phase2_time = time.time() - t1

    # Phase 3: Family re-discovery
    print("\nPhase 3: Family re-discovery on extended range...")
    t2 = time.time()
    families = analyzer.discover_new_families()
    phase3_time = time.time() - t2
    print(f"  Discovered {len(families)} parametric families")

    # Phase 4: Analysis
    print("\nPhase 4: Statistical analysis...")
    t3 = time.time()

    final_unsolved = sorted(analyzer.unsolved_n)
    final_unsolved_primes = [n for n in final_unsolved if analyzer._is_prime(n)]

    prime_mod_analysis = {}
    if final_unsolved_primes:
        for m in [4, 6, 8, 12, 24, 60, 120]:
            counts = Counter(p % m for p in final_unsolved_primes)
            prime_mod_analysis[m] = dict(counts)

    method_coverage = dict(coverage['method_stats'])
    for m, c in rescued_by_method.items():
        method_coverage[m] = method_coverage.get(m, 0) + c

    total_covered = coverage['total'] - len(final_unsolved)
    num_methods = len([v for v in method_coverage.values() if v > 0])
    compression_ratio = total_covered / max(1, num_methods)

    phase4_time = time.time() - t3
    total_time = time.time() - t0

    results = {
        'max_n': max_n,
        'total_time_seconds': round(total_time, 2),
        'phase_times': {
            'coverage': round(phase1_time, 2),
            'deep_search': round(phase2_time, 2),
            'family_discovery': round(phase3_time, 2),
            'analysis': round(phase4_time, 2),
        },
        'coverage': {
            'total': coverage['total'],
            'covered_after_phase1': coverage['covered'],
            'rescued_in_phase2': len(rescued),
            'final_covered': total_covered,
            'final_unsolved': len(final_unsolved),
            'coverage_pct': total_covered / coverage['total'] * 100,
        },
        'method_stats': method_coverage,
        'rescued_by_method': dict(rescued_by_method),
        'unsolved': {
            'count': len(final_unsolved),
            'primes': final_unsolved_primes[:500],
            'all_values': final_unsolved[:1000],
            'prime_count': len(final_unsolved_primes),
        },
        'prime_mod_analysis': prime_mod_analysis,
        'families': families,
        'family_count': len(families),
        'active_methods': num_methods,
        'compression_ratio': round(compression_ratio, 1),
    }

    # Print summary
    print(f"\n{'='*62}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*62}")
    print(f"  Range: n in [2, {max_n:,}]")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Final coverage: {total_covered:,}/{coverage['total']:,} "
          f"({results['coverage']['coverage_pct']:.6f}%)")
    print(f"  Unsolved: {len(final_unsolved):,} values "
          f"({len(final_unsolved_primes)} primes)")
    print(f"  Methods: {num_methods} active, compression {compression_ratio:.1f}x")

    print(f"\n  Method breakdown:")
    for m, c in sorted(method_coverage.items(), key=lambda x: -x[1]):
        pct = c / coverage['total'] * 100
        print(f"    {m:30s}: {c:>8,} ({pct:.2f}%)")

    if final_unsolved_primes:
        print(f"\n  First 20 unsolved primes:")
        for p in final_unsolved_primes[:20]:
            print(f"    p = {p:,} (p mod 4 = {p%4}, p mod 24 = {p%24})")

    print(f"{'='*62}")
    return results


def main():
    """Entry point for the E-S extension."""
    # Run at multiple scales for comparison
    results = {}

    for target in [10_000, 100_000, 1_000_000]:
        print(f"\n\n{'#'*62}")
        print(f"# TARGET: n ≤ {target:,}")
        print(f"{'#'*62}")

        result = run_extension(target)
        results[target] = result

    # Save all results
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
    os.makedirs(results_dir, exist_ok=True)

    json_path = os.path.join(results_dir, 'erdos_straus_extension.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved: {json_path}")

    # Cross-scale comparison
    print(f"\n{'='*62}")
    print(f"  CROSS-SCALE COMPARISON")
    print(f"{'='*62}")
    print(f"  {'Range':>12s}  {'Covered':>10s}  {'Unsolved':>10s}  {'%':>10s}  {'Time':>8s}")
    for target, r in results.items():
        c = r['coverage']
        print(f"  n≤{target:>9,}  {c['final_covered']:>10,}  "
              f"{c['final_unsolved']:>10,}  "
              f"{c['coverage_pct']:>9.4f}%  "
              f"{r['total_time_seconds']:>7.1f}s")

    return results


if __name__ == '__main__':
    main()
