"""Round 10AC: alpha=3 at N=10000 with correct extraction."""
import mpmath as mp
import time
import sys

mp.mp.dps = 80
N = 10000

print('Computing alpha=3 product to N=%d...' % N, flush=True)
sig3 = [0]*(N+1)
for d in range(1, N+1):
    d3 = d*d*d
    for j in range(d, N+1, d):
        sig3[j] += d3
print('sigma_3 done', flush=True)

t0 = time.time()
f3 = [0]*(N+1)
f3[0] = 1
for n in range(1, N+1):
    s = 0
    for j in range(1, n+1):
        s += sig3[j] * f3[n-j]
    f3[n] = s // n
    if n % 1000 == 0:
        elapsed = time.time() - t0
        rate = n / elapsed if elapsed > 0 else 0
        eta = (N - n) / rate if rate > 0 else 0
        nd = len(str(f3[n]))
        print('  n=%5d: %4d digits, %.1fs, ETA %.0fs' % (n, nd, elapsed, eta), flush=True)

total = time.time() - t0
nd_final = len(str(f3[N]))
print('DONE: %.1fs, f3(%d) has %d digits' % (total, N, nd_final), flush=True)

# Verify first values
assert [f3[i] for i in range(6)] == [1,1,5,14,40,101], 'OEIS mismatch!'
print('OEIS check passed', flush=True)

# Parameters
c3 = mp.mpf(4)/3 * (mp.pi**4/15)**mp.mpf('0.25')
kappa3 = mp.mpf(-5)/8
L3_pred = 27*c3**4/2048 + kappa3
L3f = float(L3_pred)
a = float(3*c3/4)
C1 = a
C2 = a**2/2
C3 = a**3/6

# Extract L_m for all key points
Lm = {}
key_ms = [500,800,1000,1500,2000,2500,3000,3500,4000,5000,6000,7000,8000,9000,10000]
for m in key_ms:
    Rm = float(mp.mpf(f3[m]) / mp.mpf(f3[m-1]))
    resid = Rm - 1 - C1*m**(-0.25) - C2*m**(-0.5) - C3*m**(-0.75)
    Lm[m] = m * resid

print('\nL3 predicted = %.12f' % L3f, flush=True)
print('\nRaw L_m:', flush=True)
for m in key_ms:
    gap = Lm[m] - L3f
    print('  m=%5d: %.8f gap=%+.10f rel=%.5f%%' % (m, Lm[m], gap, abs(gap/L3f)*100), flush=True)

# 4-pt Richardson
def r4(ms):
    xs = [m**(-0.25) for m in ms]
    ys = [Lm[m] for m in ms]
    r = 0
    for i in range(4):
        b = 1
        for j in range(4):
            if i != j:
                b *= (0 - xs[j])/(xs[i] - xs[j])
        r += ys[i] * b
    return r

configs = [
    (500,1000,2000,3000),
    (1000,2000,3000,5000),
    (2000,3000,5000,8000),
    (2000,4000,7000,10000),
    (3000,5000,7000,10000),
    (2000,5000,8000,10000),
    (3000,5000,8000,10000),
    (3000,6000,8000,10000),
    (4000,6000,8000,10000),
    (5000,7000,9000,10000),
]

print('\nRichardson 4-pt:', flush=True)
best = 1.0
best_cfg = None
for cfg in configs:
    try:
        L = r4(cfg)
        gap = L - L3f
        rel = abs(gap/L3f)
        if rel < best:
            best = rel
            best_cfg = cfg
        print('  %-32s %.10f gap=%+.10f rel=%.6f%%' % (str(cfg), L, gap, rel*100), flush=True)
    except Exception as e:
        print('  %-32s FAILED: %s' % (str(cfg), e), flush=True)

print('\nBEST: %s -> %.6f%%' % (best_cfg, best*100), flush=True)
print('Previous (N=3000): 0.02%%', flush=True)
if best > 0:
    print('Improvement: %.1fx' % (0.0002/best), flush=True)
