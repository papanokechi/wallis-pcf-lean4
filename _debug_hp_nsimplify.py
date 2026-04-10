"""Debug nsimplify matching at high precision."""
import mpmath, sympy
from sympy import nsimplify, pi, E, EulerGamma, sqrt

mp = mpmath.mp.clone()
mp.dps = 120

# Recompute the GCF a=-1, b=2n^2-3n+1 at 120 dps
an = [-1]
bn = [2, -3, 1]
tiny = mp.mpf(10) ** (-mp.dps)
f = mp.mpf(bn[2])  # b(0) = 0*0 + (-3)*0 + 1 = 1... wait
# b(n) = 2n^2 - 3n + 1 -> b(0) = 1

def b_poly(n):
    return 2*n*n - 3*n + 1

f = mp.mpf(b_poly(0))
if f == 0:
    f = tiny
C = f
D = mp.mpf(0)
for n in range(1, 501):
    a_n = mp.mpf(-1)
    b_n = mp.mpf(b_poly(n))
    D = b_n + a_n * D
    if D == 0:
        D = tiny
    D = 1 / D
    C = b_n + a_n / C
    if C == 0:
        C = tiny
    delta = C * D
    f = f * delta
    if abs(delta - 1) < mp.mpf(10) ** (-(mp.dps - 5)):
        break

print(f"CF value at 120 dps: {mp.nstr(f, 40)}")

# Check if it's 1 - sqrt(6)/6
target = 1 - mp.sqrt(6)/6
print(f"1 - sqrt(6)/6:      {mp.nstr(target, 40)}")
print(f"Difference:          {float(abs(f - target))}")

# nsimplify test
val_float = float(f)
print(f"\nFloat value: {val_float}")
for constants in [[pi, sqrt(2), sqrt(3)]]:
    exact = nsimplify(val_float, constants=constants, tolerance=1e-15, rational=False)
    print(f"nsimplify result: {exact} (type: {type(exact).__name__})")
    # Verify at high precision
    exact_hp = exact.evalf(120)
    diff = abs(f - mp.mpf(str(exact_hp)))
    print(f"HP diff: {float(diff)}")
    print(f"Threshold (prec//2 = 50): {float(mp.mpf(10) ** -50)}")
    print(f"Passes: {diff < mp.mpf(10) ** -50}")
