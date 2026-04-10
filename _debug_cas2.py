"""Debug CAS failure for GCF a(n)=-5, b(n)=2n^2+2n+2."""
import mpmath
from ramanujan_agent.proof_engine import identify_special_function, cas_verify
from ramanujan_agent.formulas import _evaluate_gcf

mp = mpmath.mp.clone()
mp.dps = 100

# GCF a(n)=-5, b(n)=2n^2+2n+2
def a_func(n): return -5
def b_func(n): return 2*n*n + 2*n + 2

val = _evaluate_gcf(a_func, b_func, depth=500, prec=100)
print(f"Value: {mp.nstr(val, 30)}")

an = [-5]
bn = [2, 2, 2]
sf = identify_special_function(an, bn, str(val), prec=100)
print(f"Identified: {sf['identified']}")
for c in sf.get('candidates', []):
    print(f"  type={c['type']}, expr={c.get('expression', c.get('formula', ''))[:60]}")
    print(f"  match_error={c.get('match_error', '?')}")

if sf.get('best'):
    expr = sf['best'].get('expression') or sf['best'].get('formula', '')
    print(f"\nCAS verify: {expr}")
    r = cas_verify(expr, str(val), prec=100)
    print(f"  verified={r['verified']}  digits={r['match_digits']}  error={r.get('error','none')}")
    print(f"  diff={r.get('difference','?')}")

# Also try: GCF a(n)=2, b(n)=-n^2+2n+8 (the one that DID get formal)
print("\n--- GCF a(n)=2, b(n)=-n^2+2n+8 (formal proof candidate) ---")
def a2(n): return 2
def b2(n): return -n*n + 2*n + 8
val2 = _evaluate_gcf(a2, b2, depth=500, prec=100)
print(f"Value: {mp.nstr(val2, 30)}")
sf2 = identify_special_function([2], [-1, 2, 8], str(val2), prec=100)
print(f"Identified: {sf2['identified']}")
for c in sf2.get('candidates', []):
    print(f"  type={c['type']}, expr={c.get('expression', c.get('formula', ''))[:60]}")
if sf2.get('best'):
    expr2 = sf2['best'].get('expression') or sf2['best'].get('formula', '')
    print(f"CAS verify: {expr2}")
    r2 = cas_verify(expr2, str(val2), prec=100)
    print(f"  verified={r2['verified']}  digits={r2['match_digits']}  diff={r2.get('difference','?')}")
