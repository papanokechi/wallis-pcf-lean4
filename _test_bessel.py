"""Verify Bessel CF formula with known case."""
import mpmath
mp = mpmath.mp
mp.dps = 50

# The CF c/(a + c/(a+1 + c/(a+2 + ...))) for c=1, a=1
# should equal sqrt(1)*I_1(2)/I_0(2) = I_1(2)/I_0(2)
val_I = mp.besseli(1, 2) / mp.besseli(0, 2)
print(f"I_1(2)/I_0(2) = {mp.nstr(val_I, 20)}")

# Now compute the CF with an=[1], bn=[1,1] => a(n)=1, b(n)=n+1
# CF = b(0) + K_{n>=1} a(n)/b(n) = 1 + 1/(2 + 1/(3 + 1/(4 + ...)))
from ramanujan_agent.analysis import compute_hi_precision_value
hi = compute_hi_precision_value([1], [1, 1], prec=50)
print(f"CF a=[1], b=[1,1]: {mp.nstr(hi['value_mpf'], 20)}")

# The pure tail K_{n=1}^inf 1/(n+1) with Perron formula:
# K_{n=1}^inf 1/(n+1) = f(2, 1) where f(a,c) = sqrt(c)*I_a(2*sqrt(c))/I_{a-1}(2*sqrt(c))
# With c=1, a=2: f = 1*I_2(2)/I_1(2)
f_tail = mp.besseli(2, 2) / mp.besseli(1, 2)
print(f"I_2(2)/I_1(2) = {mp.nstr(f_tail, 20)}")
cf_from_bessel = 1 + f_tail
print(f"1 + I_2(2)/I_1(2) = {mp.nstr(cf_from_bessel, 20)}")
print(f"Match: {abs(hi['value_mpf'] - cf_from_bessel) < 1e-30}")

# Now the full CF = b(0) + tail
# For Bessel matching: the CF has alpha=1, beta=1
# So a0 = 1 + beta/alpha = 2, c = A/alpha = 1
# f_target = S/alpha where S = val - beta = val - 1
# f_bessel = sqrt(c) * I_{a0}(2*sqrt(c)) / I_{a0-1}(2*sqrt(c))
# = 1 * I_2(2) / I_1(2)
# CF = beta + alpha * f_bessel = 1 + 1 * I_2(2)/I_1(2) ✓
print()

# Test with c=4, a=1 (simulated by an=[4], bn=[1,1])
# CF = 1 + 4/(2 + 4/(3 + 4/(4 + ...)))
# Perron: f(2, 4) = sqrt(4)*I_2(2*sqrt(4))/I_1(2*sqrt(4)) = 2*I_2(4)/I_1(4)
hi2 = compute_hi_precision_value([4], [1, 1], prec=50)
f2 = 2 * mp.besseli(2, 4) / mp.besseli(1, 4)
cf2 = 1 + f2
print(f"CF a=[4], b=[1,1]: {mp.nstr(hi2['value_mpf'], 20)}")
print(f"1 + 2*I_2(4)/I_1(4): {mp.nstr(cf2, 20)}")
print(f"Match: {abs(hi2['value_mpf'] - cf2) < 1e-30}")

# Now test identification
from ramanujan_agent.analysis import bessel_identification
print()
print("--- Bessel ID for a=[1], b=[1,1] ---")
res = bessel_identification([1], [1, 1], hi["value_mpf"], prec=50)
print(f"Identified: {res['identified']}")
for c in res.get("candidates", []):
    print(f"  {c['type']}: {c.get('formula', '')[:80]}")

print()
print("--- Bessel ID for a=[4], b=[1,1] ---")
res2 = bessel_identification([4], [1, 1], hi2["value_mpf"], prec=50)
print(f"Identified: {res2['identified']}")
for c in res2.get("candidates", []):
    print(f"  {c['type']}: {c.get('formula', '')[:80]}")
