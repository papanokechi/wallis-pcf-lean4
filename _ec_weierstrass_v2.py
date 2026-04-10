"""
Definitive EC computation for w^2 = (u+2)(u-2)(u-39)(u-43).
Multiple methods + point counting to verify.
"""
from mpmath import mp, mpf, nstr, fabs, pi, sqrt, log
from fractions import Fraction
import math

mp.dps = 50

e1, e2, e3, e4 = -2, 2, 39, 43
print("=" * 70)
print("QUARTIC: w^2 = (u+2)(u-2)(u-39)(u-43)")
print("=" * 70)

# ================================================================
# METHOD 1: Resolvent cubic (Cassels)
# For y^2 = prod(x-ei), the Jacobian has cubic Y^2 = prod(X-ri)
# with r1=e1e2+e3e4, r2=e1e3+e2e4, r3=e1e4+e2e3
# ================================================================
r1 = e1*e2 + e3*e4
r2 = e1*e3 + e2*e4
r3 = e1*e4 + e2*e3
print(f"\nResolvent cubic: r1={r1}, r2={r2}, r3={r3}")
print(f"Y^2 = (X-{r1})(X-{r2})(X+{-r3})")

# Short Weierstrass
s1 = r1 + r2 + r3
A1 = Fraction(-s1**2, 3) + (r1*r2 + r1*r3 + r2*r3)
S = Fraction(s1, 3)
B1 = S**3 - s1*S**2 + (r1*r2+r1*r3+r2*r3)*S - r1*r2*r3
print(f"\nMethod 1 Weierstrass: y^2 = x^3 + ({A1})x + ({B1})")

# ================================================================
# METHOD 2: Binary quartic invariants I, J
# f(u) = u^4 - 82u^3 + 1673u^2 + 328u - 6708
# I = 12*a0*a4 - 3*a1*a3 + a2^2 (for f = a0*u^4 + a1*u^3 + a2*u^2 + a3*u + a4)
# J = 72*a0*a2*a4 + 9*a1*a2*a3 - 27*a0*a3^2 - 27*a1^2*a4 - 2*a2^3
# Jacobian: Y^2 = X^3 - 27I*X - 27J
# ================================================================
a0, a1, a2, a3, a4 = 1, -82, 1673, 328, -6708
I = 12*a0*a4 - 3*a1*a3 + a2**2
J = 72*a0*a2*a4 + 9*a1*a2*a3 - 27*a0*a3**2 - 27*a1**2*a4 - 2*a2**3
print(f"\nMethod 2 invariants: I={I}, J={J}")
print(f"Jacobian: Y^2 = X^3 + ({-27*I})X + ({-27*J})")

# Cross-check: methods should give same A, B
A2 = Fraction(-27*I, 1)
B2 = Fraction(-27*J, 1)
# Method 1 gives A/B in fractions; need to scale
# Method 1: y^2 = x^3 + (A1)x + (B1) -- fractional
# Method 2: Y^2 = X^3 + (-27I)X + (-27J) -- integer
# They should be related by a scaling x -> lambda^2 X, y -> lambda^3 Y
print(f"\nMethod 1: A1 = {A1}, B1 = {B1}")
print(f"Method 2: A2 = {A2}, B2 = {B2}")

# Check: A2/A1 should be lambda^4, B2/B1 should be lambda^6
if A1 != 0 and B1 != 0:
    ratio_A = A2 / A1
    ratio_B = B2 / B1
    print(f"A2/A1 = {ratio_A} = {float(ratio_A):.6f}")
    print(f"B2/B1 = {ratio_B} = {float(ratio_B):.6f}")
    # lambda^4 should equal ratio_A, lambda^6 = ratio_B
    # So ratio_B / ratio_A = lambda^2
    lam_sq = ratio_B / ratio_A
    print(f"lambda^2 = B_ratio/A_ratio = {lam_sq} = {float(lam_sq):.6f}")
    # Both should give same j-invariant

# j-invariant from Method 2 (integer model)
A_int = -27 * I
B_int = -27 * J
j_num_raw = -1728 * (4 * A_int)**3
j_den_raw = 4 * A_int**3 + 27 * B_int**2
g = math.gcd(abs(j_num_raw), abs(j_den_raw))
j_n, j_d = j_num_raw // g, j_den_raw // g
print(f"\nj (Method 2) = {j_n}/{j_d} = {j_n/j_d:.15f}")

# j-invariant from Method 1 (rational model -- should be same)
A1_f, B1_f = float(A1), float(B1)
j_m1 = -1728 * (4*A1_f)**3 / (4*A1_f**3 + 27*B1_f**2)
print(f"j (Method 1) = {j_m1:.15f}")
print(f"Match: {abs(j_n/j_d - j_m1) < 0.001}")

# ================================================================
# CORRECT THE SIGN OF B: note that in Method 1 we used s3 = r1*r2*r3
# The standard shift gives B = 2s1^3/27 - s1 s2/3 + s3
# Let me verify by direct expansion
# ================================================================
print("\n" + "=" * 70)
print("VERIFICATION: direct expansion of (X-1673)(X-8)(X+8)")
print("=" * 70)
# = X^3 - 1673 X^2 + (-64) X - (-107072)
# = X^3 - 1673 X^2 - 64 X + 107072
# Shift X = x + 1673/3:
# A = -64 - 1673^2/3
# B = -107072 + ... let me compute directly with exact fractions.
S_frac = Fraction(1673, 3)
# y^2 = (x+S)^3 - 1673(x+S)^2 - 64(x+S) + 107072
# Expand (x+S)^3 = x^3 + 3S x^2 + 3S^2 x + S^3
# -1673(x+S)^2 = -1673 x^2 - 2*1673*S x - 1673 S^2
# -64(x+S) = -64 x - 64 S
# Combine:
# x^3 term: 1
# x^2 term: 3S - 1673 = 0  (since 3S = 1673)
# x term: 3S^2 - 2*1673*S - 64
# const: S^3 - 1673*S^2 - 64*S + 107072

A_direct = 3*S_frac**2 - 2*1673*S_frac - 64
B_direct = S_frac**3 - 1673*S_frac**2 - 64*S_frac + 107072

print(f"A (direct) = {A_direct} = {float(A_direct):.6f}")
print(f"B (direct) = {B_direct} = {float(B_direct):.6f}")

# Compare with Method 1
print(f"A (method 1) = {A1} = {float(A1):.6f}")
print(f"B (method 1) = {B1} = {float(B1):.6f}")
print(f"A match: {A_direct == A1}")
print(f"B match: {B_direct == B1}")

# So B_direct should be correct. Let me check the sign.
# B_direct = 1673^3/27 - 1673*1673^2/9 - 64*1673/3 + 107072
# = 1673^3/27 - 1673^3/9 - 64*1673/3 + 107072
# = 1673^3(1/27 - 1/9) - 64*1673/3 + 107072
# = 1673^3(-2/27) - 64*1673/3 + 107072

val = Fraction(1673**3 * (-2), 27) - Fraction(64*1673, 3) + 107072
print(f"\nB check: {val} = {float(val):.6f}")
print(f"B_direct: {B_direct} = {float(B_direct):.6f}")
print(f"Match: {val == B_direct}")

# ================================================================
# FINAL: Scale B_direct to integer model
# A = -2799121/3, B = ?
# ================================================================
print(f"\nA_frac = {A_direct}")
print(f"B_frac = {B_direct}")

# Scale: (x,y) -> (9x, 27y) i.e. u=3
A_scaled = int(A_direct * 81)  # 3^4 = 81
B_scaled = int(B_direct * 729)  # 3^6 = 729
print(f"\nInteger model (u=3): y^2 = x^3 + ({A_scaled})x + ({B_scaled})")

# Check if further reducible
for p in [2, 3, 5, 7, 11, 13, 37, 41]:
    while A_scaled % p**4 == 0 and B_scaled % p**6 == 0:
        A_scaled //= p**4
        B_scaled //= p**6
        print(f"  Reduced by {p}")

print(f"Minimal: y^2 = x^3 + ({A_scaled})x + ({B_scaled})")

# Discriminant
disc = -16*(4*A_scaled**3 + 27*B_scaled**2)
print(f"Disc = {disc}")
d = abs(disc)
facs = {}
for p in range(2, 300):
    while d % p == 0:
        facs[p] = facs.get(p, 0) + 1
        d //= p
if d > 1: facs[d] = 1
print(f"|Disc| = {' * '.join(f'{p}^{e}' if e>1 else str(p) for p,e in sorted(facs.items()))}")

# j-invariant
j_num = -1728 * (4*A_scaled)**3
j_den = 4*A_scaled**3 + 27*B_scaled**2
g = math.gcd(abs(j_num), abs(j_den))
j_n, j_d = j_num//g, j_den//g
print(f"j = {j_n}/{j_d}")
if abs(j_d) == 1:
    print(f"j is INTEGER: {j_n * (1 if j_d > 0 else -1)}")
print(f"j = {j_n/j_d:.15f}")

# ================================================================
# NOW: Check different cross-ratio orderings
# The cross-ratio lambda depends on which root maps where.
# There are 3 distinct cross-ratios from the 6 pairings:
# ================================================================
print("\n" + "=" * 70)
print("ALL CROSS-RATIO ORDERINGS")
print("=" * 70)

from itertools import permutations
roots = [e1, e2, e3, e4]
seen_j = set()
for perm in permutations(roots):
    a, b, c, d = perm
    if (d - b) == 0 or (c - b) == 0 or (d - a) == 0:
        continue
    lam = Fraction((c - a) * (d - b), (c - b) * (d - a))
    # j from Legendre: j = 256*(lam^2-lam+1)^3 / (lam^2*(lam-1)^2)
    num_j = 256 * (lam**2 - lam + 1)**3
    den_j = lam**2 * (lam - 1)**2
    if den_j == 0:
        continue
    j_leg = num_j / den_j
    j_float = float(j_leg)
    if abs(j_float) < 1e15:
        key = round(j_float, 6)
        if key not in seen_j:
            seen_j.add(key)
            print(f"  lambda={float(lam):.10f}  j={j_float:.6f}")

print(f"\n  Distinct j-values from cross-ratios: {len(seen_j)}")
print(f"  (The Legendre j should be the same for all orderings of a given curve)")

# ================================================================
# POINT COUNTING on the resolvent cubic model
# to match against known a_p sequences
# ================================================================
print("\n" + "=" * 70)
print(f"POINT COUNTING on y^2 = x^3 + ({A_scaled})x + ({B_scaled})")
print("=" * 70)

def sieve_primes(limit):
    s = [True]*(limit+1); s[0]=s[1]=False
    for i in range(2, int(limit**0.5)+1):
        if s[i]:
            for j in range(i*i, limit+1, i): s[j]=False
    return [i for i in range(2,limit+1) if s[i]]

primes = sieve_primes(100)
print(f"\n{'p':>5s}  {'#E':>5s}  {'a_p':>5s}  {'|a_p|<=2sqrt(p)?':>18s}")
for p in primes:
    Ap = A_scaled % p
    Bp = B_scaled % p
    count = 0
    for x in range(p):
        rhs = (x**3 + Ap*x + Bp) % p
        if rhs == 0:
            count += 1
        else:
            if p == 2:
                if rhs % 2 == 0: count += 2
            else:
                leg = pow(rhs, (p-1)//2, p)
                if leg == 1: count += 2
    Np = count + 1  # point at infinity
    ap = p + 1 - Np
    bound = 2*p**0.5
    ok = "ok" if abs(ap) <= bound + 0.5 else "HASSE VIOLATION"
    print(f"{p:5d}  {Np:5d}  {ap:+5d}  {ok:>18s}")

# ================================================================
# SEARCH Cremona tables by a_p values
# The sequence a_2, a_3, a_5, a_7, a_11, a_13, ... identifies the curve
# ================================================================
print("\n" + "=" * 70)
print("a_p SIGNATURE for database lookup")
print("=" * 70)
sig = []
for p in primes[:15]:
    Ap = A_scaled % p
    Bp = B_scaled % p
    count = 0
    for x in range(p):
        rhs = (x**3 + Ap*x + Bp) % p
        if rhs == 0: count += 1
        elif p > 2 and pow(rhs, (p-1)//2, p) == 1: count += 2
    ap = p + 1 - (count + 1)
    sig.append((p, ap))
    
print(f"a_p values: {[ap for _, ap in sig]}")
print(f"Search LMFDB by: a2={sig[0][1]}, a3={sig[1][1]}, a5={sig[2][1]}, a7={sig[3][1]}")
