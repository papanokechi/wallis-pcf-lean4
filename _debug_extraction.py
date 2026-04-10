"""Debug extraction: verify L and A1 for k=1 (ordinary partitions)."""
import mpmath as mp
import time

mp.mp.dps = 80

k = 1
c = mp.pi * mp.sqrt(mp.mpf(2)/3)
kappa = -(k+3) / mp.mpf(4)  # = -1
d = mp.mpf(1)/2
L_pred = c**2/8 + kappa
A1_pred = -k*c/48 - (k+1)*(k+3)/(8*c)

print(f'c_{k} = {mp.nstr(c, 20)}')
print(f'kappa_{k} = {mp.nstr(kappa, 20)}')
print(f'L_{k} = {mp.nstr(L_pred, 20)}')
print(f'A1_{k} = {mp.nstr(A1_pred, 20)}')
print()

# Compute partitions (exact integers)
N = 3000
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
print(f'f(0..10) = {[f[i] for i in range(11)]}')
print(f'Expected:   [1, 1, 2, 3, 5, 7, 11, 15, 22, 30, 42]')
print()

# Method 1: Naive subtraction R_m ~ 1 + c/(2*sqrt(m)) + L/m + A1/m^{3/2}
print(f'=== Method 1: Naive subtraction ===')
print(f'R_m = 1 + c/(2*sqrt(m)) + L/m + A1/m^{3/2} + ...')
print(f'L predicted = {float(L_pred):.10f}')
print(f'A1 predicted = {float(A1_pred):.10f}')
print()
print(f'{"m":>6s}  {"L_m":>16s}  {"A1_m":>16s}')
print('-' * 44)

for m in [200, 500, 1000, 1500, 2000, 2500, 3000]:
    mf = mp.mpf(m)
    R_m = mp.mpf(f[m]) / mp.mpf(f[m-1])
    sm = mp.sqrt(mf)
    
    L_m = (R_m - 1 - c / (2*sm)) * mf
    A1_m = (R_m - 1 - c / (2*sm) - L_pred / mf) * mf * sm
    
    print(f'{m:6d}  {float(L_m):16.10f}  {float(A1_m):16.10f}')

# Method 2: Exponential/power-law division (paper's 3-factor)
# R_m = E_m * P_m * S_m
# E_m = exp(c*(m^d - (m-1)^d)), P_m = (m/(m-1))^kappa
# After dividing: R_m/(E_m * P_m) - 1 ~ something
print()
print(f'=== Method 2: Divide by E_m * P_m (standard approach) ===')
print(f'{"m":>6s}  {"Q_m*m":>16s}')
print('-' * 26)

for m in [200, 500, 1000, 1500, 2000, 2500, 3000]:
    mf = mp.mpf(m)
    R_m = mp.mpf(f[m]) / mp.mpf(f[m-1])
    
    exp_diff = c * (mp.sqrt(mf) - mp.sqrt(mf - 1))
    pow_ratio = mp.power(mf / (mf - 1), kappa)
    leading = mp.exp(exp_diff) * pow_ratio
    
    Q_m = R_m / leading - 1
    print(f'{m:6d}  {float(Q_m * mf):16.10f}')

# Method 3: The _round10ac approach for alpha=3 (L_m = m*(R_m/base - 1))
print()
print(f'=== Method 3: _round10ac approach adapted ===')
print(f'{"m":>6s}  {"L_m":>16s}')
print('-' * 26)

for m in [200, 500, 1000, 1500, 2000, 2500, 3000]:
    mf = mp.mpf(m)
    R_m = mp.mpf(f[m]) / mp.mpf(f[m-1])
    
    # For d=1/2: exp(c * (m^{1/2} - (m-1)^{1/2}))
    exp_diff = c * (mp.power(mf, d) - mp.power(mf-1, d))
    pow_ratio = mp.power(mf/(mf-1), kappa)
    base = mp.exp(exp_diff) * pow_ratio
    Lm = float(mf * (R_m / base - 1))
    print(f'{m:6d}  {Lm:16.10f}')

# Method 4: Richardson extrapolation on naive L_m
print()
print(f'=== Method 4: Richardson on naive L_m ===')
L_data = {}
for m in range(100, N+1):
    mf = mp.mpf(m)
    R_m = mp.mpf(f[m]) / mp.mpf(f[m-1])
    sm = mp.sqrt(mf)
    L_data[m] = float((R_m - 1 - c / (2*sm)) * mf)

# Richardson: L_rich = (4*L_{2m} - L_m) / 3
print(f'{"(m,2m)":>12s}  {"L_rich":>16s}  {"gap":>16s}')
print('-' * 48)
for m in [250, 500, 750, 1000, 1250, 1500]:
    if m in L_data and 2*m in L_data:
        L_rich = (4*L_data[2*m] - L_data[m]) / 3
        gap = L_rich - float(L_pred)
        print(f'({m},{2*m}){"":<4s}  {L_rich:16.10f}  {gap:+16.10f}')

