"""Round 10AC: Extend alpha=3 Meinardus product to N=10,000."""
import sys
import time

try:
    import mpmath as mp
except ImportError:
    print("mpmath not found, installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mpmath"])
    import mpmath as mp

mp.mp.dps = 80

print('='*70)
print('  ROUND 10AC: Fourth-root (alpha=3) extended to N=10,000')
print('='*70)
print(flush=True)

N = 10000

# Step 1: Precompute sigma_3(j) = sum_{d|j} d^3
print('Step 1: Precomputing sigma_3(j)...', flush=True)
t0 = time.time()
sig3 = [0]*(N+1)
for d in range(1, N+1):
    d3 = d*d*d
    for j in range(d, N+1, d):
        sig3[j] += d3
print('  Done in %.1fs' % (time.time()-t0), flush=True)

# Step 2: Compute f3(n) via recurrence (exact integers)
print('Step 2: Computing f3(n) for n=0..%d...' % N, flush=True)
t0 = time.time()
f3 = [0]*(N+1)
f3[0] = 1

try:
    for n in range(1, N+1):
        s = 0
        for j in range(1, n+1):
            s += sig3[j] * f3[n-j]
        assert s % n == 0, "n=%d: s not divisible by n!" % n
        f3[n] = s // n
        if n % 1000 == 0:
            ndig = len(str(f3[n]))
            elapsed = time.time() - t0
            rate = n / elapsed if elapsed > 0 else 0
            eta = (N - n) / rate if rate > 0 else 0
            print('  n=%5d: %4d digits, %.1fs elapsed, ETA %.0fs' % (n, ndig, elapsed, eta), flush=True)
except Exception as e:
    print('ERROR at n=%d: %s' % (n, e), flush=True)
    sys.exit(1)

t_compute = time.time() - t0
ndig_final = len(str(f3[N]))
print('  Complete: %.1fs, f3(%d) has %d digits' % (t_compute, N, ndig_final), flush=True)
print(flush=True)

# Verify first values
first = [f3[n] for n in range(8)]
print('First values: %s' % first)
expected = [1, 1, 5, 14, 40, 101, 261, 630]
if first != expected:
    print('OEIS MISMATCH! Expected: %s' % expected)
    sys.exit(1)
print('OEIS check: PASSED', flush=True)
print(flush=True)

# Step 3: Extract L3
print('Step 3: Ratio analysis...', flush=True)
c3 = mp.mpf(4)/3 * (mp.pi**4/15)**mp.mpf('0.25')
kappa3 = mp.mpf(-5)/8

L3_pred = 27*c3**4/2048 + kappa3
L3_pred_f = float(L3_pred)
print('c3 = %s' % mp.nstr(c3, 25))
print('kappa3 = -5/8 = %s' % kappa3)
print('L3 predicted = %s' % mp.nstr(L3_pred, 15))
print(flush=True)

# Compute L_m
Cm_data = {}
for m in range(200, N+1):
    Rm = mp.mpf(f3[m]) / mp.mpf(f3[m-1])
    exp_diff = c3 * (mp.power(m, mp.mpf(3)/4) - mp.power(m-1, mp.mpf(3)/4))
    pow_ratio = mp.power(mp.mpf(m)/(m-1), kappa3)
    base = mp.exp(exp_diff) * pow_ratio
    Lm = float(m * (Rm / base - 1))
    Cm_data[m] = Lm

# Raw convergence
print('Raw L_m convergence:')
for m in [500, 1000, 2000, 3000, 5000, 8000, 10000]:
    Lm = Cm_data[m]
    gap = Lm - L3_pred_f
    rel = abs(gap / L3_pred_f)
    print('  m=%5d: L_m = %.8f, gap = %+.8f, rel = %.4f%%' % (m, Lm, gap, rel*100))
print(flush=True)

# 4-point Richardson extrapolation via Lagrange at x=0 in m^{-1/4}
def richardson_4pt(m_vals):
    xs = [m**(-0.25) for m in m_vals]
    ys = [Cm_data[m] for m in m_vals]
    result = 0
    for i in range(4):
        basis = 1
        for j in range(4):
            if i != j:
                basis *= (0 - xs[j])/(xs[i] - xs[j])
        result += ys[i] * basis
    return result

configs = [
    (500, 1000, 2000, 3000),
    (1000, 2000, 3000, 5000),
    (1000, 3000, 5000, 8000),
    (2000, 4000, 6000, 10000),
    (1000, 3000, 7000, 10000),
    (2000, 5000, 8000, 10000),
    (3000, 5000, 7000, 10000),
]

print('Richardson extrapolation (4-point, Lagrange in m^{-1/4}):')
print('%-32s %18s %15s %12s' % ('Config', 'L3 (estimate)', 'Gap', 'Rel. error'))
print('-'*78)

best_rel = 1.0
for cfg in configs:
    try:
        L3_est = richardson_4pt(cfg)
        gap = L3_est - L3_pred_f
        rel = abs(gap / L3_pred_f)
        if rel < best_rel:
            best_rel = rel
        print('%-32s %18.8f %+15.8f %11.5f%%' % (str(cfg), L3_est, gap, rel*100))
    except Exception as e:
        print('%-32s FAILED: %s' % (str(cfg), e))

print()
print('BEST relative agreement: %.5f%%' % (best_rel*100))
print('Previous (v26, N=3000): 0.02%%')
print('Improvement factor: %.0fx' % (0.0002/best_rel) if best_rel > 0 else 'infinite')
print()
print('Computation time: %.1fs' % t_compute)
