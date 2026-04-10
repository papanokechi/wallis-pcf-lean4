"""Test GCF a=-1, b=2n^2-3n+1 which should identify as 1-sqrt(6)/6."""
import mpmath
from ramanujan_agent.proof_engine import attempt_proof

discovery = {
    "id": "test_sqrt6",
    "family": "continued_fraction",
    "expression": "GCF a(n)=-1, b(n)=2n^2-3n+1",
    "value": 0.59175170953613697,
    "params": {
        "an": [-1],
        "bn": [2, -3, 1],
        "strategy": "quadratic_b",
        "label": "cf_qb_a-1_b2_-3_1",
    },
    "metadata": {},
}

pr = attempt_proof(discovery, prec=100)
print(f"Status: {pr.status}")
print(f"Confidence: {pr.confidence}")
print(f"Convergence: {pr.convergence.get('theorem_used')}")
print(f"Closed form: {pr.closed_form.get('identified')}")
if pr.closed_form.get('best'):
    print(f"  Best: {pr.closed_form['best']}")
print(f"CAS verified: {pr.verification.get('verified')}")
print(f"Match digits: {pr.verification.get('match_digits')}")
print(f"Gaps: {pr.gaps}")
