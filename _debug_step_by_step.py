"""Debug the full pipeline step by step."""
import mpmath, sympy
from sympy import nsimplify, pi, sqrt

# Step 1: Recompute value at high precision with correct convention
# bn = [2, -3, 1] -> b(n) = 2n^2 - 3n + 1
an = [-1]
bn = [2, -3, 1]

mp = mpmath.mp.clone()
mp.dps = 120

deg_a = len(an) - 1  # 0
deg_b = len(bn) - 1  # 2

def _a(n):
    return an[0]  # -1

def _b(n):
    return bn[0] * n**2 + bn[1] * n + bn[2]  # 2n^2 - 3n + 1

# Verify a few values
print(f"a(1)={_a(1)}, b(0)={_b(0)}, b(1)={_b(1)}, b(2)={_b(2)}, b(3)={_b(3)}")

# Lentz
tiny = mp.mpf(10) ** (-mp.dps)
f = mp.mpf(_b(0))
if f == 0:
    f = tiny
C = f
D = mp.mpf(0)
for n in range(1, 501):
    a_n = mp.mpf(_a(n))
    b_n = mp.mpf(_b(n))
    D = b_n + a_n * D
    if D == 0:
        D = tiny
    D = 1 / D
    C = b_n + a_n / C
    if C == 0:
        C = tiny
    delta = C * D
    f = f * delta

print(f"\nHP value: {mp.nstr(f, 40)}")
print(f"1-sqrt(6)/6: {mp.nstr(1-mp.sqrt(6)/6, 40)}")
print(f"Diff: {float(abs(f - (1-mp.sqrt(6)/6)))}")

# Step 2: nsimplify on the float
val_float = float(f)
print(f"\nFloat: {val_float}")
for constants in [
    [pi, sympy.E, sympy.EulerGamma],
    [pi, sqrt(2), sqrt(3)],
]:
    try:
        exact = nsimplify(val_float, constants=constants, tolerance=1e-15, rational=False)
        expr_str = str(exact)
        if len(expr_str) <= 40:
            try:
                float(expr_str)
                is_num = True
            except ValueError:
                is_num = False
            print(f"  nsimplify: {expr_str} {'[NUMERIC]' if is_num else '[SYMBOLIC]'}")
            if not is_num:
                # Verify at HP
                exact_hp = exact.evalf(120)
                diff = abs(f - mp.mpf(str(exact_hp)))
                print(f"  HP verify diff: {float(diff)}")
    except Exception as e:
        print(f"  nsimplify failed: {e}")
