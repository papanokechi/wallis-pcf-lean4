"""Compute Weierstrass form of w^2 = (u+2)(u-2)(u-39)(u-43) via resolvent cubic."""
from mpmath import mp, mpf, nstr
from fractions import Fraction
import math

mp.dps = 50

e1, e2, e3, e4 = -2, 2, 39, 43

# Resolvent cubic roots
r1 = e1*e2 + e3*e4  # (-2)(2)+(39)(43) = -4+1677 = 1673
r2 = e1*e3 + e2*e4  # (-2)(39)+(2)(43) = -78+86 = 8
r3 = e1*e4 + e2*e3  # (-2)(43)+(2)(39) = -86+78 = -8
print(f"Resolvent cubic roots: r1={r1}, r2={r2}, r3={r3}")
print(f"Jacobian: Y^2 = (X-{r1})(X-{r2})(X-{r3})")
print(f"        = (X-1673)(X-8)(X+8) = (X-1673)(X^2-64)")

s1 = r1 + r2 + r3
s2 = r1*r2 + r1*r3 + r2*r3
s3 = r1*r2*r3
print(f"\nsigma1={s1}, sigma2={s2}, sigma3={s3}")

# Short Weierstrass via shift X -> x + s1/3
A_frac = Fraction(-s1**2, 3) + s2
B_frac = Fraction(s1, 3)**3 - s1 * Fraction(s1, 3)**2 + s2 * Fraction(s1, 3) - s3
print(f"\nA = {A_frac} = {float(A_frac):.6f}")
print(f"B = {B_frac} = {float(B_frac):.6f}")

# Scale by u=3 to get integer model
A_sc = int(A_frac * 3**4)
B_sc = int(B_frac * 3**6)
print(f"\nScaled (u=3): y^2 = x^3 + ({A_sc})x + ({B_sc})")

# Reduce to minimal
A_i, B_i = A_sc, B_sc
for p in [2, 3, 5, 7, 11, 13]:
    while A_i % p**4 == 0 and B_i % p**6 == 0:
        A_i //= p**4
        B_i //= p**6
        print(f"  Reduced by {p}: A={A_i}, B={B_i}")

print(f"\nMinimal model: y^2 = x^3 + ({A_i})x + ({B_i})")

disc = -16 * (4 * A_i**3 + 27 * B_i**2)
print(f"Disc = {disc}")

d = abs(disc)
factors = {}
for p in range(2, 200):
    while d % p == 0:
        factors[p] = factors.get(p, 0) + 1
        d //= p
if d > 1:
    factors[d] = 1
fstr = ' * '.join(f'{p}^{e}' if e > 1 else str(p) for p, e in sorted(factors.items()))
print(f"|Disc| = {fstr}")

# j-invariant as exact fraction
j_num = -1728 * (4 * A_i)**3
j_den = 4 * A_i**3 + 27 * B_i**2
g = math.gcd(abs(j_num), abs(j_den))
j_n, j_d = j_num // g, j_den // g
print(f"\nj = {j_n}/{j_d}")
print(f"j (decimal) = {j_n / j_d:.15f}")

# Check: is j an integer?
if j_d == 1:
    print(f"j is an INTEGER: {j_n}")
elif j_d == -1:
    print(f"j is an INTEGER: {-j_n}")

# Rodriguez-Villegas prediction
t = 39
j_rv_num = (t**2 + 12)**3
j_rv_den = t**2 - 4
j_rv_g = math.gcd(j_rv_num, j_rv_den)
print(f"\nRodriguez-Villegas: j = {j_rv_num//j_rv_g}/{j_rv_den//j_rv_g} = {j_rv_num/j_rv_den:.15f}")
print(f"Our j = {j_n}/{j_d} = {j_n/j_d:.15f}")
print(f"Match: {j_n * j_rv_den == j_d * j_rv_num}")

# LMFDB lookup URL
if j_d == 1 or j_d == -1:
    j_val = j_n * (1 if j_d == 1 else -1)
    print(f"\nLMFDB URL: https://www.lmfdb.org/EllipticCurve/Q/?jinv={j_val}")
else:
    from urllib.parse import quote
    jstr = f"{j_n}/{j_d}"
    print(f"\nLMFDB URL: https://www.lmfdb.org/EllipticCurve/Q/?jinv={quote(jstr)}")
