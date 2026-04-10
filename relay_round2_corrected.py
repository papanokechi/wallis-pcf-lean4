"""
OEIS A002865 Relay Chain — Round 2 (Falsifier Agent) CORRECTED
First: determine the CORRECT identity for a(n).
Then: test all conjectures rigorously.
"""
import math
from functools import lru_cache
from decimal import Decimal, getcontext
getcontext().prec = 50

# ─── Partition function via recurrence (exact integer arithmetic) ───
@lru_cache(maxsize=None)
def p(n):
    """Number of partitions of n (A000041), exact."""
    if n < 0:
        return 0
    if n == 0:
        return 1
    total = 0
    k = 1
    while True:
        g1 = k * (3 * k - 1) // 2
        g2 = k * (3 * k + 1) // 2
        if g1 > n:
            break
        sign = (-1) ** (k + 1)
        total += sign * p(n - g1)
        if g2 <= n:
            total += sign * p(n - g2)
        k += 1
    return total

# ─── Determine the correct identity ───
known = [0, 0, 1, 1, 2, 3, 5, 7, 11, 15, 22, 30, 42, 56, 77, 101, 135, 176, 231, 297,
         385, 490, 627, 792, 1002, 1255, 1575, 1958, 2436, 3010, 3718, 4565, 5604, 6842,
         8349, 10143, 12310]

print("=== Testing candidate identities ===")
# Test a(n) = p(n-2)
all_match = True
for i, val in enumerate(known):
    if p(i - 2) != val:
        all_match = False
        break
print(f"  a(n) = p(n-2): {'MATCHES ALL' if all_match else 'FAILS'}")

# Test a(n) = p(n-1) - 1
all_match2 = True
for i, val in enumerate(known):
    if i < 2:
        continue
    if p(i - 1) - 1 != val:
        all_match2 = False
        print(f"    FAILS at n={i}: p({i-1})-1 = {p(i-1)-1}, expected {val}")
        if i > 8:
            break
print(f"  a(n) = p(n-1) - 1: {'MATCHES' if all_match2 else 'FAILS'}")

# ─── Use the CORRECT identity ───
def a(n):
    """A002865 as given in the prompt: a(n) = p(n-2)."""
    return p(n - 2)

# Verify
print("\n=== Verification with a(n) = p(n-2) ===")
for i, val in enumerate(known):
    comp = a(i)
    if comp != val:
        print(f"  MISMATCH n={i}: {comp} vs {val}")
print("  All verified ✓" if all(a(i) == known[i] for i in range(len(known))) else "  ERRORS FOUND")

# ─── Core computation: R(n), envelope, curvature up to N_MAX ───
N_MAX = 600
print(f"\n=== Computing a(n) for n up to {N_MAX+2} ===")

# Precompute
for n in range(N_MAX + 3):
    p(n)  # fill cache

# R(n) = a(n)/a(n-1) = p(n-2)/p(n-3)
print("\n=== R(n) = a(n)/a(n-1) = p(n-2)/p(n-3) ===")
print(f"{'n':>5} {'a(n)':>16} {'R(n)':>12} {'pred(n)':>12} {'pred(n-2)':>12} {'diff_n':>12} {'diff_n2':>12}")

ratios = {}
for n in range(4, N_MAX + 1):
    an = a(n)
    an1 = a(n - 1)
    if an1 == 0:
        continue
    R = an / an1  # = p(n-2)/p(n-3)
    pred_n = 1 + math.pi / math.sqrt(6 * n)
    # The ratio is really p(m)/p(m-1) where m = n-2
    m = n - 2
    pred_m = 1 + math.pi / math.sqrt(6 * m)
    diff_n = R - pred_n
    diff_m = R - pred_m
    ratios[n] = {'R': R, 'pred_n': pred_n, 'pred_m': pred_m, 'diff_n': diff_n, 'diff_m': diff_m, 'm': m}
    if n <= 25 or n in [30, 40, 50, 100, 200, 300, 400, 500, 600]:
        print(f"{n:5d} {an:16d} {R:12.6f} {pred_n:12.6f} {pred_m:12.6f} {diff_n:12.6f} {diff_m:12.6f}")

# ─── CRITICAL TEST: Which asymptotic variable is correct? n or n-2? ───
print("\n=== Which variable gives better fit: R(n)≈1+π/√(6n) or R(n)≈1+π/√(6(n-2))? ===")
# Mean squared error for n >= 100
mse_n = 0
mse_m = 0
count = 0
for n in range(100, N_MAX + 1):
    if n in ratios:
        mse_n += ratios[n]['diff_n'] ** 2
        mse_m += ratios[n]['diff_m'] ** 2
        count += 1
if count > 0:
    print(f"  MSE(pred_n) for n>=100: {mse_n/count:.12f}")
    print(f"  MSE(pred_m) for n>=100: {mse_m/count:.12f}")
    print(f"  Ratio MSE_n/MSE_m: {mse_n/mse_m:.4f}")
    print(f"  {'→ n-2 is BETTER' if mse_m < mse_n else '→ n is BETTER'}")

# ─── Envelope strip test with both variables ───
print("\n=== Envelope strip test (Agent 2's strip): R(n) in 1+π/√(6n) ± [1.0/n, 1.8/n] for n≥40 ===")
violations_n = []
for n in range(40, N_MAX + 1):
    if n not in ratios:
        continue
    R = ratios[n]['R']
    pred = ratios[n]['pred_n']
    lower = pred - 1.0 / n
    upper = pred + 1.8 / n
    if R < lower or R > upper:
        violations_n.append((n, R, lower, upper))
        
if violations_n:
    print(f"  VIOLATIONS with variable n: {len(violations_n)}")
    for v in violations_n[:10]:
        nn, R, lo, hi = v
        print(f"    n={nn}: R={R:.8f}, strip=[{lo:.8f}, {hi:.8f}]")
else:
    print(f"  No violations with variable n in [40, {N_MAX}]")

print(f"\n=== Envelope strip test with CORRECT variable m=n-2 ===")
violations_m = []
for n in range(40, N_MAX + 1):
    if n not in ratios:
        continue
    R = ratios[n]['R']
    m = n - 2
    pred = 1 + math.pi / math.sqrt(6 * m)
    lower = pred - 1.0 / m
    upper = pred + 1.8 / m
    if R < lower or R > upper:
        violations_m.append((n, R, lower, upper, m))

if violations_m:
    print(f"  VIOLATIONS with variable m=n-2: {len(violations_m)}")
    for v in violations_m[:10]:
        nn, R, lo, hi, mm = v
        print(f"    n={nn} (m={mm}): R={R:.8f}, strip=[{lo:.8f}, {hi:.8f}]")
else:
    print(f"  No violations with m=n-2 in [40, {N_MAX}]")

# ─── Discrete log-curvature ───
print(f"\n=== Scaled curvature T(n) = n^(3/2) * Δ²log a(n) ===")
print(f"{'n':>5} {'Δ²log a(n)':>18} {'T(n)':>12} {'T_m(m^1.5)':>12}")

T_values = {}
for n in range(4, N_MAX + 1):
    an_m1 = a(n - 1)
    an_0 = a(n)
    an_p1 = a(n + 1)
    if an_m1 <= 0 or an_0 <= 0 or an_p1 <= 0:
        continue
    d2log = math.log(an_p1) - 2 * math.log(an_0) + math.log(an_m1)
    T = (n ** 1.5) * d2log
    m = n - 2
    T_m = (m ** 1.5) * d2log if m > 0 else float('nan')
    T_values[n] = {'d2log': d2log, 'T_n': T, 'T_m': T_m, 'm': m}
    if n <= 20 or n in [30, 40, 50, 60, 80, 100, 150, 200, 300, 400, 500, 600] or n >= N_MAX - 2:
        print(f"{n:5d} {d2log:18.12f} {T:12.6f} {T_m:12.6f}")

# ─── T(n) convergence analysis ───
print("\n=== T(n) convergence (windowed) ===")
for label, key in [("T_n (scale by n)", 'T_n'), ("T_m (scale by m=n-2)", 'T_m')]:
    print(f"  --- {label} ---")
    windows = [(40, 60), (60, 100), (100, 200), (200, 300), (300, 400), (400, 500), (500, 600)]
    for w_start, w_end in windows:
        vals = [T_values[n][key] for n in range(w_start, min(w_end + 1, N_MAX + 1))
                if n in T_values and not math.isnan(T_values[n][key])]
        if vals:
            avg = sum(vals) / len(vals)
            mn = min(vals)
            mx = max(vals)
            print(f"    n∈[{w_start},{w_end}]: mean={avg:.6f}, range=[{mn:.6f}, {mx:.6f}]")

# ─── Alternative exponents ───
print("\n=== Best exponent α: find α s.t. n^α * Δ²log a(n) → const ===")
print("  Testing with m = n-2 as the scaling variable:")
for alpha in [1.0, 1.25, 1.5, 1.75, 2.0]:
    vals_early = []
    vals_late = []
    for n in range(200, N_MAX + 1):
        if n not in T_values:
            continue
        m = n - 2
        d2log = T_values[n]['d2log']
        scaled = (m ** alpha) * d2log
        if n < 400:
            vals_early.append(scaled)
        else:
            vals_late.append(scaled)
    if vals_early and vals_late:
        avg_e = sum(vals_early) / len(vals_early)
        avg_l = sum(vals_late) / len(vals_late)
        drift = abs(avg_l - avg_e) / abs(avg_e) if avg_e != 0 else float('inf')
        print(f"  α={alpha:.2f}: early_mean={avg_e:.6f}, late_mean={avg_l:.6f}, drift={drift:.4f}")

# ─── Monotone decrease violations ───
print(f"\n=== Monotone decrease of R(n) for n >= 10 ===")
mono_viol = []
for n in range(11, N_MAX + 1):
    if n in ratios and n - 1 in ratios:
        if ratios[n]['R'] > ratios[n-1]['R']:
            mono_viol.append((n, ratios[n-1]['R'], ratios[n]['R']))

print(f"  Violations in [11,{N_MAX}]: {len(mono_viol)}")
for v in mono_viol[:15]:
    n, rp, rc = v
    print(f"    n={n}: R({n-1})={rp:.8f} → R({n})={rc:.8f}")
if len(mono_viol) > 15:
    # Check if violations stop
    last_viol = mono_viol[-1][0]
    print(f"  ... last violation at n={last_viol}")

# ─── Oscillation pattern ───
print(f"\n=== Oscillation of R(n) ===")
up = 0
down = 0
for n in range(5, N_MAX + 1):
    if n in ratios and n - 1 in ratios:
        if ratios[n]['R'] > ratios[n-1]['R']:
            up += 1
        else:
            down += 1
print(f"  Up: {up}, Down: {down}, Fraction up: {up/(up+down):.4f}")

# Check if fraction of ups converges
for start, end in [(5, 50), (50, 100), (100, 200), (200, 400), (400, 600)]:
    u = d = 0
    for n in range(start, min(end + 1, N_MAX + 1)):
        if n in ratios and n - 1 in ratios:
            if ratios[n]['R'] > ratios[n-1]['R']:
                u += 1
            else:
                d += 1
    if u + d > 0:
        print(f"    n∈[{start},{end}]: up={u}, down={d}, frac_up={u/(u+d):.4f}")

# ─── NEW OBJECT: Second-order correction coefficient ───
print(f"\n=== Fitting R(n) = 1 + π/√(6m) + C/m where m=n-2 ===")
C_estimates = []
for n in range(100, N_MAX + 1):
    if n not in ratios:
        continue
    m = n - 2
    R = ratios[n]['R']
    first = math.pi / math.sqrt(6 * m)
    resid = R - 1 - first
    C = resid * m
    C_estimates.append((n, m, C))

windows_C = [(100, 200), (200, 300), (300, 400), (400, 500), (500, 600)]
for ws, we in windows_C:
    cs = [c for n, m, c in C_estimates if ws <= n <= we]
    if cs:
        avg = sum(cs) / len(cs)
        print(f"  n∈[{ws},{we}]: mean(C)={avg:.6f}")

# ─── Fitting: R(n) = 1 + π/√(6m) + C₁/m + C₂/m^(3/2) ───
print(f"\n=== Three-term fit: R = 1 + π/√(6m) + C₁/m + C₂/m^(3/2) ===")
# Use least squares with two unknowns C1, C2 from large-m data
import numpy as np
ms = []
ys = []
for n in range(200, N_MAX + 1):
    if n not in ratios:
        continue
    m = n - 2
    R = ratios[n]['R']
    y = R - 1 - math.pi / math.sqrt(6 * m)
    ms.append(m)
    ys.append(y)

ms = np.array(ms, dtype=float)
ys = np.array(ys, dtype=float)
# y = C1/m + C2/m^(3/2)
A = np.column_stack([1.0 / ms, 1.0 / ms**1.5])
result = np.linalg.lstsq(A, ys, rcond=None)
C1, C2 = result[0]
print(f"  Fitted C₁ = {C1:.6f}")
print(f"  Fitted C₂ = {C2:.6f}")

# Check residuals
residuals = ys - A @ result[0]
print(f"  Max residual: {max(abs(residuals)):.2e}")
print(f"  Mean abs residual: {np.mean(np.abs(residuals)):.2e}")

# ─── Verify the conjectured kappa from curvature ───
print(f"\n=== What is κ in Δ²log a(n) ~ -κ·n^(-3/2)? ===")
kappa_estimates = []
for n in range(200, N_MAX + 1):
    if n not in T_values:
        continue
    m = n - 2
    kappa = -T_values[n]['T_m']  # Using m = n-2
    kappa_estimates.append((n, kappa))

for ws, we in [(200, 300), (300, 400), (400, 500), (500, 600)]:
    ks = [k for n, k in kappa_estimates if ws <= n <= we]
    if ks:
        print(f"  n∈[{ws},{we}]: mean(κ)={sum(ks)/len(ks):.6f}")

# Theoretical prediction: from p(n) ~ (1/4n√3)exp(π√(2n/3))
# log p(n) ~ π√(2n/3) - log(4n√3) = π√(2/3)·√n - (1/2)log(n) - log(4√3)
# Δ²log p(n) ~ π√(2/3)·Δ²(√n) + ...
# √(n+1) - 2√n + √(n-1) ~ -1/(4n^(3/2)) for large n
# So Δ²log p(n) ~ -π√(2/3)/(4n^(3/2)) = -π/(4√(3/2)·n^(3/2)) = -π/(2√6·n^(3/2))
kappa_theory = math.pi / (2 * math.sqrt(6))
print(f"\n  Theoretical κ = π/(2√6) = {kappa_theory:.6f}")

print("\n=== DONE ===")
