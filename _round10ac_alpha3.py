"""Round 10AC: Extend alpha=3 Meinardus product to N=10,000."""
import mpmath as mp
import time

mp.mp.dps = 80

print('='*70)
print('  ROUND 10AC: Fourth-root (alpha=3) extended to N=10,000')
print('='*70)
print()

N = 10000

# Step 1: Precompute sigma_3(j) = sum_{d|j} d^3
print('Step 1: Precomputing sigma_3(j) for j=1..%d' % N)
t0 = time.time()
sig3 = [0]*(N+1)
for d in range(1, N+1):
    d3 = d*d*d
    for j in range(d, N+1, d):
        sig3[j] += d3
print('  sigma_3 done in %.1fs' % (time.time()-t0))

# Step 2: Compute f3(n) via recurrence (exact integers)
# For prod(1-q^m)^{-m^2}: n*f3(n) = sum_{j=1}^n sigma_3(j)*f3(n-j)
print('Step 2: Computing f3(n) for n=0..%d (exact integers)' % N)
t0 = time.time()
f3 = [0]*(N+1)
f3[0] = 1
for n in range(1, N+1):
    s = 0
    for j in range(1, n+1):
        s += sig3[j] * f3[n-j]
    f3[n] = s // n
    if n % 2000 == 0:
        ndig = len(str(f3[n]))
        elapsed = time.time() - t0
        print('  n=%d: %d digits, elapsed %.1fs' % (n, ndig, elapsed))

t_compute = time.time() - t0
ndig_final = len(str(f3[N]))
print('  Done in %.1fs' % t_compute)
print('  f3(%d) has %d digits' % (N, ndig_final))
print()

# Verify first values
first = [f3[n] for n in range(8)]
print('First values: %s' % first)
expected = [1, 1, 5, 14, 40, 101, 261, 630]
assert first == expected, 'OEIS mismatch!'
print('OEIS check: PASSED')
print()

# Step 3: Extract L3
print('Step 3: Extracting L3 via ratio analysis')
c3 = mp.mpf(4)/3 * (mp.pi**4/15)**mp.mpf('0.25')
kappa3 = mp.mpf(-5)/8

L3_pred = 27*c3**4/2048 + kappa3
print('c3 = %s' % mp.nstr(c3, 30))
print('kappa3 = %s' % kappa3)
print('L3 predicted = %s' % mp.nstr(L3_pred, 15))
print()

# Compute L_m for each m
Cm_data = []
for m in range(200, N+1):
    if f3[m-1] == 0:
        continue
    Rm = mp.mpf(f3[m]) / mp.mpf(f3[m-1])
    exp_diff = c3 * (mp.power(m, mp.mpf(3)/4) - mp.power(m-1, mp.mpf(3)/4))
    pow_ratio = mp.power(mp.mpf(m)/(m-1), kappa3)
    base = mp.exp(exp_diff) * pow_ratio
    Lm = m * (Rm / base - 1)
    Cm_data.append((m, float(Lm)))

def richardson_4pt(data, m_vals):
    m1, m2, m3, m4 = m_vals
    L1 = next(L for m,L in data if m == m1)
    L2 = next(L for m,L in data if m == m2)
    L3v = next(L for m,L in data if m == m3)
    L4 = next(L for m,L in data if m == m4)
    xs = [m**(-0.25) for m in [m1,m2,m3,m4]]
    ys = [L1, L2, L3v, L4]
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

L3_pred_f = float(L3_pred)
print('%-32s %18s %15s %12s' % ('Config', 'L3 (Richardson)', 'Gap', 'Rel. error'))
print('-'*78)

for cfg in configs:
    try:
        L3_est = richardson_4pt(Cm_data, cfg)
        gap = L3_est - L3_pred_f
        rel = abs(gap / L3_pred_f)
        print('%-32s %18.8f %+15.8f %11.5f%%' % (str(cfg), L3_est, gap, rel*100))
    except Exception as e:
        print('%-32s FAILED: %s' % (str(cfg), e))

# Also report raw L_m at key points
print()
print('Raw L_m convergence:')
for m in [500, 1000, 2000, 3000, 5000, 8000, 10000]:
    Lm = next(L for mm,L in Cm_data if mm == m)
    gap = Lm - L3_pred_f
    print('  m=%5d: L_m = %.8f, gap = %+.8f' % (m, Lm, gap))

print()
print('Computation time: %.1fs' % t_compute)
print('f3(%d) has %d digits' % (N, ndig_final))
