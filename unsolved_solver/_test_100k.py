"""Test E-S coverage at 100k scale with sieve optimization."""
from unsolved_solver.problems.erdos_straus import ErdosStrausAnalyzer
import time

t0 = time.time()
a = ErdosStrausAnalyzer(max_n=100000)
print(f"Sieve built in {time.time()-t0:.1f}s")

t1 = time.time()
r = a.analyze_coverage(100000, progress_every=20000)
elapsed = time.time() - t1

print(f"\nCoverage to 100k: {r['covered']}/{r['total']} ({r['coverage_pct']:.4f}%)")
print(f"Unsolved: {r['uncovered']}")
print(f"Methods: {r['method_stats']}")
print(f"Time (coverage only): {elapsed:.1f}s")
print(f"Total time: {time.time()-t0:.1f}s")
if r['unsolved_examples']:
    print(f"First 20 unsolved: {r['unsolved_examples'][:20]}")
else:
    print("All solved!")
