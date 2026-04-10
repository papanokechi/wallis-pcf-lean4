"""Full attempt_proof test for the formal proof candidate."""
import mpmath
from ramanujan_agent.proof_engine import attempt_proof
from ramanujan_agent.formulas import _evaluate_gcf

mp = mpmath.mp.clone()
mp.dps = 100

def a_func(n): return 2
def b_func(n): return -n*n + 2*n + 8
val = float(_evaluate_gcf(a_func, b_func, depth=500, prec=50))

# Simulate the discovery dict as it would appear
discovery = {
    "id": "test_formal",
    "family": "continued_fraction",
    "expression": "GCF a(n)=2, b(n)=-1n²+2n+8",
    "value": val,
    "params": {
        "an": [2],
        "bn": [-1, 2, 8],
        "strategy": "quadratic_b",
        "label": "cf_qb_a2_b-1_2_8",
    },
    "metadata": {
        "value_20_digits": str(val),
    },
}

pr = attempt_proof(discovery, prec=100)
print(f"Status: {pr.status}")
print(f"Confidence: {pr.confidence}")
print(f"Convergence proven: {pr.convergence.get('proven')}")
print(f"Convergence theorem: {pr.convergence.get('theorem_used')}")
print(f"Closed form identified: {pr.closed_form.get('identified')}")
if pr.closed_form.get('best'):
    print(f"Best: {pr.closed_form['best']}")
print(f"Verified: {pr.verification.get('verified')}")
print(f"Match digits: {pr.verification.get('match_digits')}")
print(f"Gaps: {pr.gaps}")
print()
print("Proof text:")
print(pr.proof_text[:500])
