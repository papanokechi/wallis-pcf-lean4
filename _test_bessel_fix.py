"""Verify that the corrected bessel_identification (c=A/alpha^2) works."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ramanujan_agent.analysis import bessel_identification
import mpmath

mp = mpmath.mp.clone()
mp.dps = 100

# Compute CF values at high precision
def eval_cf(A, alpha, beta, n_terms=2000):
    val = mp.mpf(0)
    for n in range(n_terms, 0, -1):
        bn = alpha * n + beta
        val = mp.mpf(A) / (mp.mpf(bn) + val)
    return mp.mpf(beta) + val   # add b(0)

test_cases = [
    ([-6], [8, 7]),
    ([-9], [-7, 8]),
    ([3], [1, 5]),     # alpha=1 case (should still work)
]

for an, bn in test_cases:
    A = an[0]
    alpha, beta = bn[0], bn[1]
    val = eval_cf(A, alpha, beta)
    print(f"\na={an}, b={bn}, val={mp.nstr(val, 25)}")
    
    result = bessel_identification(an, bn, val, prec=100)
    print(f"  identified: {result['identified']}")
    if result['identified']:
        best = result['best_identification']
        print(f"  type: {best['type']}")
        print(f"  formula: {best['formula']}")
        print(f"  match_digits: {best['match_digits']}")
        print(f"  match_error: {best['match_error']:.2e}")
    else:
        print(f"  reason: {result.get('reason', 'no candidates')}")
        print(f"  candidates: {len(result['candidates'])}")
