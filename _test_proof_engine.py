"""Quick smoke test for proof engine."""
from ramanujan_agent.proof_engine import attempt_proof
import mpmath

mp = mpmath.mp.clone()
mp.dps = 50

# Evaluate CF: b(0) + K_{n>=1}(1/(n+2)) using Lentz
tiny = mp.mpf(10)**(-50)
b0 = mp.mpf(2)  # b(0) = 1*0 + 2 = 2
f = b0
C = b0
D = mp.mpf(0)
for n in range(1, 500):
    an = mp.mpf(1)
    bn = mp.mpf(1*n + 2)
    D = bn + an * D
    if D == 0: D = tiny
    C = bn + an / C
    if C == 0: C = tiny
    D = 1 / D
    delta = C * D
    f *= delta

print(f"CF value = {mp.nstr(f, 20)}")

disc = {
    "id": "test_cf_001",
    "expression": "K(1/(n+2))",
    "params": {"an": [1], "bn": [1, 2]},
    "value": float(f),
    "metadata": {
        "value_hi_prec": str(f),
        "value_20_digits": mp.nstr(f, 20),
    },
    "family": "continued_fraction",
}
r = attempt_proof(disc, prec=50)
print(f"Status: {r.status}")
print(f"Convergence proven: {r.convergence.get('proven')}")
print(f"  Theorem: {r.convergence.get('theorem_used')}")
print(f"Closed form identified: {r.closed_form.get('identified')}")
if r.closed_form.get("type"):
    print(f"  Type: {r.closed_form['type']}")
    expr = r.closed_form.get("expression", "")
    print(f"  Expression: {str(expr)[:80]}")
print(f"Verification: {r.verification.get('verified')}")
print(f"Confidence: {r.confidence}")
print(f"Gaps: {r.gaps}")
print(f"Time: {r.time_seconds:.2f}s")
print()
print("=== Proof text ===")
print(r.proof_text)
