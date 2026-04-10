"""Reproduce the proof pipeline for a specific candidate to debug CAS failure."""
import mpmath
from ramanujan_agent.proof_engine import identify_special_function, cas_verify
from ramanujan_agent.formulas import _evaluate_gcf

mp = mpmath.mp.clone()
mp.dps = 100

# GCF a(n)=-3, b(n)=2n^2+5n+5  — reported as "Closed form found but CAS verification failed"
def a_func(n):
    return -3
def b_func(n):
    return 2*n*n + 5*n + 5

val = _evaluate_gcf(a_func, b_func, depth=500, prec=100)
print(f"Value (100 dps): {mp.nstr(val, 30)}")

# Step 1: identify_special_function
an = [-3]
bn = [2, 5, 5]
sf = identify_special_function(an, bn, str(val), prec=100)
print(f"\nSpecial function identified: {sf['identified']}")
for c in sf.get('candidates', []):
    print(f"  type: {c['type']}")
    print(f"  expression: {c.get('expression', c.get('formula', ''))[:80]}")
    print(f"  match_error: {c.get('match_error', '?')}")

# Step 2: if identified, test cas_verify
if sf.get('identified') and sf.get('best'):
    best = sf['best']
    expr = best.get('expression') or best.get('formula', '')
    print(f"\n--- CAS Verify ---")
    print(f"Expression to verify: {expr}")
    r = cas_verify(expr, str(val), prec=100)
    print(f"Verified: {r['verified']}")
    print(f"Match digits: {r['match_digits']}")
    print(f"Error: {r.get('error', 'none')}")
    print(f"Difference: {r.get('difference', '?')}")
