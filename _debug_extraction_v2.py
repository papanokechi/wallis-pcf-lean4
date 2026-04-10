"""Debug extraction: verify L and A1 for k=1 and k=5 using paper's pipeline."""
import mpmath as mp
import time

mp.mp.dps = 80

k = 1
c = mp.pi * mp.sqrt(mp.mpf(2)/3)
kappa = -(k+3) / mp.mpf(4)  # = -1
L_pred = c**2/8 + kappa
A1_pred = -k*c/48 - (k+1)*(k+3)/(8*c)

print(f'c_{k} = {mp.nstr(c, 20)}')
print(f'kappa_{k} = {mp.nstr(kappa, 20)}')
print(f'L_{k} = {mp.nstr(L_pred, 20)}')
print(f'A1_{k} = {mp.nstr(A1_pred, 20)}')
print()

# Compute partitions (exact integers)
N = 5000
t0 = time.time()
sig1 = [0]*(N+1)
for dd in range(1, N+1):
    for j in range(dd, N+1, dd):
        sig1[j] += dd

f = [0]*(N+1)
f[0] = 1
for n in range(1, N+1):
    s = 0
    for j in range(1, n+1):
        s += k * sig1[j] * f[n-j]
    f[n] = s // n

dt = time.time() - t0
print(f'Computed {N} partitions in {dt:.1f}s')
print()

# Paper's pipeline: alpha_m = m^{3/2} * [R_m - 1 - c/(2*sqrt(m)) - L/m]
# alpha_m -> A1 with O(1/sqrt(m)) correction
# Richardson with (m, 4m): A1_rich = 2*alpha(4m) - alpha(m)

alpha = {}
for m in range(100, N+1):
    mf = mp.mpf(m)
    R_m = mp.mpf(f[m]) / mp.mpf(f[m-1])
    sm = mp.sqrt(mf)
    alpha[m] = float((R_m - 1 - c / (2*sm) - L_pred / mf) * mf * sm)

print(f'Raw alpha_m (should converge to A1 = {float(A1_pred):.10f}):')
for m in [200, 500, 1000, 2000, 3000, 5000]:
    if m in alpha:
        print(f'  m={m:5d}: alpha_m = {alpha[m]:.10f}  gap = {alpha[m] - float(A1_pred):+.6f}')

# Richardson level 1: pairs (m, 4m)
# alpha_m = A1 + B/sqrt(m) + C/m + ...
# alpha(4m) = A1 + B/(2*sqrt(m)) + C/(4m) + ...
# 2*alpha(4m) - alpha(m) = A1 + C(1/2 - 1)/m + ... = A1 - C/(2m) + ...
print(f'\nRichardson level 1: A1_rich = 2*alpha(4m) - alpha(m)')
rich1 = {}
for m in range(100, N//4 + 1):
    if m in alpha and 4*m in alpha:
        rich1[m] = 2 * alpha[4*m] - alpha[m]

for m in [200, 300, 500, 750, 1000, 1250]:
    if m in rich1:
        gap = rich1[m] - float(A1_pred)
        print(f'  m={m:5d}: A1_rich = {rich1[m]:.10f}  gap = {gap:+.8f}')

# Richardson level 2
print(f'\nRichardson level 2:')
for m in [200, 300]:
    if m in rich1 and 4*m in rich1:
        rich2 = (4*rich1[4*m] - rich1[m]) / 3
        gap = rich2 - float(A1_pred)
        print(f'  m={m:5d}: A1_rich2 = {rich2:.10f}  gap = {gap:+.10f}')

# 4-point Lagrange interpolation at h=1/sqrt(m) -> 0
print(f'\n4-point Lagrange (h=1/sqrt(m) -> 0):')
configs = [
    (200, 500, 1000, 2000),
    (500, 1000, 2000, 4000),
    (250, 500, 1000, 2000),
    (500, 1000, 2500, 5000),
]
for cfg in configs:
    xs = [1/m**0.5 for m in cfg]
    ys = [alpha[m] for m in cfg]
    result = 0
    for i in range(4):
        basis = 1
        for j in range(4):
            if i != j:
                basis *= (0 - xs[j])/(xs[i] - xs[j])
        result += ys[i] * basis
    gap = result - float(A1_pred)
    digits = -mp.log10(abs(gap/float(A1_pred))) if abs(gap) > 0 else 99
    print(f'  {cfg}: A1 = {result:.10f}  gap = {gap:+.10f}  ({float(digits):.1f} digits)')

# === k=5 ===
print(f'\n\n=== k=5 ===')
k = 5
c5 = mp.pi * mp.sqrt(mp.mpf(2*k)/3)
kappa5 = -(k+3) / mp.mpf(4)
L5 = c5**2/8 + kappa5
A1_5 = -k*c5/48 - (k+1)*(k+3)/(8*c5)
print(f'c_5 = {mp.nstr(c5, 15)}')
print(f'L_5 = {mp.nstr(L5, 15)}')
print(f'A1_5 = {mp.nstr(A1_5, 15)}')

N5 = 5000
t0 = time.time()
f5 = [0]*(N5+1)
f5[0] = 1
for n in range(1, N5+1):
    s = 0
    for j in range(1, n+1):
        s += k * sig1[j] * f5[n-j]
    f5[n] = s // n
    if n % 1000 == 0:
        print(f'  n={n}, {len(str(f5[n]))} digits, {time.time()-t0:.1f}s')

alpha5 = {}
for m in range(200, N5+1):
    mf = mp.mpf(m)
    R_m = mp.mpf(f5[m]) / mp.mpf(f5[m-1])
    sm = mp.sqrt(mf)
    alpha5[m] = float((R_m - 1 - c5 / (2*sm) - L5 / mf) * mf * sm)

print(f'\nRaw alpha_m for k=5:')
for m in [500, 1000, 2000, 3000, 5000]:
    if m in alpha5:
        print(f'  m={m}: {alpha5[m]:.10f}')

print(f'\nRichardson (m, 4m) for k=5:')
for m in [200, 300, 500, 750, 1000, 1250]:
    if m in alpha5 and 4*m in alpha5:
        rich = 2 * alpha5[4*m] - alpha5[m]
        gap = rich - float(A1_5)
        digits = -mp.log10(abs(gap/float(A1_5))) if abs(gap) > 0 else 99
        print(f'  m={m}: A1 = {rich:.10f}  gap = {gap:+.8f}  ({float(digits):.1f} digits)')

print(f'\n4-point Lagrange for k=5:')
for cfg in [(200, 500, 1000, 2000), (500, 1000, 2000, 4000), (250, 500, 1000, 2000)]:
    xs = [1/m**0.5 for m in cfg]
    ys = [alpha5[m] for m in cfg if m in alpha5]
    if len(ys) < 4:
        continue
    result = 0
    for i in range(4):
        basis = 1
        for j in range(4):
            if i != j:
                basis *= (0 - xs[j])/(xs[i] - xs[j])
        result += ys[i] * basis
    gap = result - float(A1_5)
    digits = -mp.log10(abs(gap/float(A1_5))) if abs(gap) > 0 else 99
    print(f'  {cfg}: A1 = {result:.10f}  gap = {gap:+.10f}  ({float(digits):.1f} digits)')
