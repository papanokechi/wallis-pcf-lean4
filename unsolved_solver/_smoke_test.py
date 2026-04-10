"""Quick smoke test for E-S analyzer."""
from unsolved_solver.problems.erdos_straus import ErdosStrausAnalyzer
import time

a = ErdosStrausAnalyzer()
t0 = time.time()
r = a.analyze_coverage(1000, progress_every=0)
elapsed = time.time() - t0

print(f"Coverage to 1000: {r['covered']}/{r['total']} ({r['coverage_pct']:.2f}%)")
print(f"Unsolved: {r['uncovered']}")
print(f"Methods: {r['method_stats']}")
print(f"Time: {elapsed:.1f}s")
if r['unsolved_examples']:
    print(f"Unsolved examples: {r['unsolved_examples'][:20]}")
else:
    print("All n in [2, 1000] solved!")
