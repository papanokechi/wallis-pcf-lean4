"""
Parametric Logarithmic Family Test
===================================
Known:  ln(2)   = 2/GCF[-n², 6n+3]   where b_n = 3(2n+1), k=2
New:    ln(3/2) = 2/GCF[-n², 10n+5]  where b_n = 5(2n+1), k=3

Conjecture: ln(k/(k-1)) = 2/GCF[-n², (2k-1)(2n+1)]  for  k = 2, 3, 4, ...

Equivalently: z = 1/k, slope = 4k-2, offset = 2k-1
"""
from mpmath import mp, mpf, log, fabs

def gcf_bw(a_fn, b_fn, depth, dps=80):
    mp.dps = dps + 20
    val = mpf(0)
    for n in range(depth, 0, -1):
        val = a_fn(n) / (b_fn(n) + val)
    return b_fn(0) + val

print("=" * 78)
print("  PARAMETRIC LOGARITHMIC FAMILY TEST")
print("  Conjecture: ln(k/(k-1)) = 2/GCF[-n², (2k-1)(2n+1)]")
print("=" * 78)
print()
print(f"{'k':>3}  {'slope':>5}  {'offset':>6}  {'constant':>12}  {'V*const':>20}  {'|V*const - 2|':>20}  digits")
print("-" * 100)

for k in range(2, 16):
    s = 4*k - 2       # slope of b_n
    f = 2*k - 1       # offset of b_n (= s/2)
    target = log(mpf(k) / (k - 1))  # ln(k/(k-1))
    
    # Evaluate GCF
    mp.dps = 150
    V = gcf_bw(lambda n: -mpf(n)**2, lambda n: s*mpf(n) + f, 400, dps=150)
    
    product = V * target
    residual = fabs(product - 2)
    
    if residual > 0:
        digits = max(0, int(-float(mp.log10(residual))))
    else:
        digits = 150
    
    const_name = f"ln({k}/{k-1})"
    print(f"{k:>3}  {s:>5}  {f:>6}  {const_name:>12}  {float(product):>20.15f}  {float(residual):>20.2e}  {digits:>3}d")

print()
print("=" * 78)
print("  PRECISION SCALING CHECK (k=4, confirming prediction)")
print("=" * 78)

for test_dps in [40, 80, 120, 200]:
    mp.dps = test_dps + 20
    V = gcf_bw(lambda n: -mpf(n)**2, lambda n: 14*mpf(n) + 7, 400, dps=test_dps+20)
    target = log(mpf(4)/3)
    res = fabs(V * target - 2)
    if res > 0:
        d = max(0, int(-float(mp.log10(res))))
    else:
        d = test_dps
    print(f"  dps={test_dps:>3}: V*ln(4/3) = {float(V*target):.15f}   residual -> {d} digits")

print()
print("=" * 78)
print("  CLOSED FORM: V = 2/ln(k/(k-1))")
print("=" * 78)
print()
for k in [2, 3, 4, 5, 6, 10]:
    mp.dps = 50
    V = mpf(2) / log(mpf(k)/(k-1))
    print(f"  k={k:>2}: GCF[-n², {4*k-2}n+{2*k-1}] = 2/ln({k}/{k-1}) = {float(V):.12f}")
