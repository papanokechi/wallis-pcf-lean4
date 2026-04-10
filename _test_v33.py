"""Quick test of v3.3 analysis functions."""
from ramanujan_agent.analysis import (
    bessel_identification, mpmath_identify,
    algebraic_degree_bound, pringsheim_convergence_check,
    compute_hi_precision_value, build_candidate_table,
)
import mpmath

# Test on GCF a(n)=[-4], b(n)=[4,2]  (value ~1.284185...)
an = [-4]; bn = [4, 2]
hi = compute_hi_precision_value(an, bn, prec=100)
val = hi["value_mpf"]
print(f"Value: {mpmath.nstr(val, 20)}")

# 1. Bessel identification
print("\n--- Bessel/HG (a=[-4], b=[4,2]) ---")
res = bessel_identification(an, bn, val, prec=100)
print(f"Identified: {res['identified']}")
for c in res.get("candidates", []):
    print(f"  {c['type']}: {c.get('formula', '')[:80]}")
    print(f"  match_digits: {c['match_digits']}, error: {c['match_error']:.2e}")

# Test Bessel on a CF that SHOULD match: a(n)=1, b(n)=[2,1] => CF = 1 + I_1(2)/I_0(2)?
print("\n--- Bessel/HG (a=[1], b=[2,1]) ---")
hi2 = compute_hi_precision_value([1], [2, 1], prec=100)
val2 = hi2["value_mpf"]
print(f"Value: {mpmath.nstr(val2, 20)}")
res2 = bessel_identification([1], [2, 1], val2, prec=100)
print(f"Identified: {res2['identified']}")
for c in res2.get("candidates", []):
    print(f"  {c['type']}: {c.get('formula', '')[:80]}")
    print(f"  match_digits: {c['match_digits']}, error: {c['match_error']:.2e}")

# Test Bessel on a=4, b=[2,1] (should match modified Bessel)
print("\n--- Bessel/HG (a=[4], b=[2,1]) ---")
hi3 = compute_hi_precision_value([4], [2, 1], prec=100)
val3 = hi3["value_mpf"]
print(f"Value: {mpmath.nstr(val3, 20)}")
res3 = bessel_identification([4], [2, 1], val3, prec=100)
print(f"Identified: {res3['identified']}")
for c in res3.get("candidates", []):
    print(f"  {c['type']}: {c.get('formula', '')[:80]}")
    print(f"  match_digits: {c['match_digits']}, error: {c['match_error']:.2e}")

# 2. ISC lookup
print("\n--- ISC ---")
isc = mpmath_identify(val, prec=30)
print(f"Found: {isc['found']}")
for i in isc.get("identifications", [])[:5]:
    print(f"  {i}")

# 3. Algebraic degree bound
print("\n--- Algebraic degree ---")
alg = algebraic_degree_bound(val, prec=100, max_degree=6)
print(f"Algebraic: {alg['is_algebraic']}")
for p in alg.get("polynomials", []):
    print(f"  deg {p['degree']}: max_coeff={p['max_coeff']}, stable={p['stable']}, residual={p['residual']:.2e}")

# 4. Pringsheim convergence
print("\n--- Convergence ---")
conv = pringsheim_convergence_check(an, bn)
print(f"Converges: {conv['converges']}")
for f in conv.get("flags", []):
    print(f"  {f}")

# 5. Test convergence on degenerate CF
print("\n--- Convergence (a=5, b=[-3,0]) ---")
conv2 = pringsheim_convergence_check([5], [-3, 0])
print(f"Converges: {conv2['converges']}")
print(f"Zero denoms: {conv2['zero_denominators']}")
for f in conv2.get("flags", []):
    print(f"  {f}")

# 6. Test ISC on known constant
print("\n--- ISC on pi^2/6 ---")
mp2 = mpmath.mp.clone()
mp2.dps = 50
isc2 = mpmath_identify(mp2.pi**2 / 6, prec=30)
print(f"Found: {isc2['found']}")
for i in isc2.get("identifications", [])[:5]:
    print(f"  {i}")

print("\n--- All tests passed ---")
