"""Test E-S coverage at 10k scale."""
from unsolved_solver.problems.erdos_straus import ErdosStrausAnalyzer
import time

a = ErdosStrausAnalyzer()
t0 = time.time()
r = a.analyze_coverage(10000, progress_every=2000)
elapsed = time.time() - t0

print(f"\nCoverage to 10k: {r['covered']}/{r['total']} ({r['coverage_pct']:.4f}%)")
print(f"Unsolved: {r['uncovered']}")
print(f"Methods: {r['method_stats']}")
print(f"Time: {elapsed:.1f}s")
if r['unsolved_examples']:
    print(f"First 20 unsolved: {r['unsolved_examples'][:20]}")
    print(f"Unsolved primes: {r['unsolved_primes'][:20]}")
else:
    print("All solved!")
