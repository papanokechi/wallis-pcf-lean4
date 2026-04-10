"""
OEIS A002865 Relay Chain — Round 2 (Falsifier Agent)
Rigorous numerical verification of Conjecture D claims.
"""
import math
from functools import lru_cache

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
        # Generalized pentagonal numbers
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

# ─── a(n) = A002865 ───
def a(n):
    """A002865: partitions of n that have 1 as a part."""
    if n < 2:
        return 0
    return p(n - 1) - 1

# ─── Verify known terms first ───
print("=== Verification of known terms ===")
known = [0, 0, 1, 1, 2, 3, 5, 7, 11, 15, 22, 30, 42, 56, 77, 101, 135, 176, 231, 297,
         385, 490, 627, 792, 1002, 1255, 1575, 1958, 2436, 3010, 3718, 4565, 5604, 6842,
         8349, 10143, 12310]
match = True
for i, val in enumerate(known):
    computed = a(i)
    if computed != val:
        print(f"  MISMATCH at n={i}: computed={computed}, expected={val}")
        match = False
if match:
    print("  All known terms verified ✓")

# ─── Compute R(n) and compare to 1 + pi/sqrt(6n) ───
print("\n=== R(n) = a(n)/a(n-1) vs predicted 1 + π/√(6n) ===")
print(f"{'n':>5} {'a(n)':>12} {'R(n)':>12} {'predicted':>12} {'diff':>12} {'1/n bound?':>12}")

N_MAX = 500
ratios = {}
for n in range(3, N_MAX + 1):
    an = a(n)
    an1 = a(n - 1)
    if an1 == 0:
        continue
    R = an / an1
    pred = 1 + math.pi / math.sqrt(6 * n)
    diff = R - pred
    ratios[n] = (R, pred, diff)
    if n <= 60 or n % 50 == 0 or n >= N_MAX - 5:
        bound_ok = abs(diff) < 1.8 / n  # upper bound from conjecture
        lower_ok = diff > -1.0 / n       # lower bound from conjecture
        in_strip = "YES" if (bound_ok and lower_ok) else "NO"
        print(f"{n:5d} {an:12d} {R:12.6f} {pred:12.6f} {diff:12.6f} {in_strip:>12}")

# ─── Test envelope strip explicitly for n >= 40 ───
print("\n=== Envelope strip test: 1 + π/√(6n) - 1.0/n < R(n) < 1 + π/√(6n) + 1.8/n for n≥40 ===")
violations = []
for n in range(40, N_MAX + 1):
    R, pred, diff = ratios[n]
    lower = pred - 1.0 / n
    upper = pred + 1.8 / n
    if R < lower or R > upper:
        violations.append((n, R, lower, upper))
        
if violations:
    print(f"  VIOLATIONS FOUND: {len(violations)}")
    for v in violations[:20]:
        n, R, lo, hi = v
        print(f"    n={n}: R={R:.8f}, strip=[{lo:.8f}, {hi:.8f}]")
else:
    print("  No violations found in [40, {}] ✓".format(N_MAX))

# ─── Compute discrete log-curvature and T(n) = n^(3/2) * Δ²log a(n) ───
print("\n=== Scaled curvature T(n) = n^(3/2) * Δ²log a(n) ===")
print(f"{'n':>5} {'Δ²log a(n)':>16} {'T(n)':>12}")
T_values = {}
for n in range(4, N_MAX + 1):
    an_m1 = a(n - 1)
    an_0 = a(n)
    an_p1 = a(n + 1)
    if an_m1 <= 0 or an_0 <= 0 or an_p1 <= 0:
        continue
    d2log = math.log(an_p1) - 2 * math.log(an_0) + math.log(an_m1)
    T = (n ** 1.5) * d2log
    T_values[n] = (d2log, T)
    if n <= 60 or n % 50 == 0 or n >= N_MAX - 5:
        print(f"{n:5d} {d2log:16.10f} {T:12.6f}")

# ─── Check if T(n) converges ───
print("\n=== T(n) convergence check (windowed averages) ===")
windows = [(40, 60), (60, 100), (100, 200), (200, 300), (300, 400), (400, 500)]
for w_start, w_end in windows:
    T_vals = [T_values[n][1] for n in range(w_start, min(w_end + 1, N_MAX + 1)) if n in T_values]
    if T_vals:
        avg = sum(T_vals) / len(T_vals)
        mn = min(T_vals)
        mx = max(T_vals)
        print(f"  n ∈ [{w_start}, {w_end}]: mean(T)={avg:.4f}, min={mn:.4f}, max={mx:.4f}")

# ─── Check monotone decrease of R(n) — original C1 conjecture ───
print("\n=== Monotone decrease test of R(n) for n >= 10 ===")
mono_violations = []
for n in range(11, N_MAX + 1):
    R_curr = ratios[n][0]
    R_prev = ratios[n - 1][0]
    if R_curr > R_prev:
        mono_violations.append((n, R_prev, R_curr))

print(f"  Violations of R(n) < R(n-1) in [11, {N_MAX}]: {len(mono_violations)}")
if mono_violations:
    print("  First 20 violations:")
    for v in mono_violations[:20]:
        n, rp, rc = v
        print(f"    n={n}: R({n-1})={rp:.8f} < R({n})={rc:.8f}")

# ─── NEW: Test alternative exponents for curvature scaling ───
print("\n=== Alternative exponent test: n^α * Δ²log a(n) for various α ===")
for alpha in [1.0, 1.25, 1.5, 1.75, 2.0]:
    vals = []
    for n in range(400, N_MAX + 1):
        if n in T_values:
            d2log = T_values[n][0]
            scaled = (n ** alpha) * d2log
            vals.append(scaled)
    if vals:
        avg = sum(vals) / len(vals)
        std = (sum((v - avg)**2 for v in vals) / len(vals)) ** 0.5
        print(f"  α={alpha:.2f}: mean={avg:.6f}, std={std:.6f}, cv={std/abs(avg):.4f}")

# ─── NEW: R(n) vs refined asymptotic with second-order correction ───
print("\n=== Testing R(n) ≈ 1 + π/√(6n) + C/n for best-fit C ===")
# Estimate C from large-n data
C_estimates = []
for n in range(200, N_MAX + 1):
    R = ratios[n][0]
    first_order = math.pi / math.sqrt(6 * n)
    residual = R - 1 - first_order
    C_est = residual * n
    C_estimates.append((n, C_est))

if C_estimates:
    cs = [c for _, c in C_estimates]
    avg_C = sum(cs) / len(cs)
    print(f"  Estimated C (from n ∈ [200, {N_MAX}]): mean={avg_C:.6f}")
    # Check stability
    cs_early = [c for n, c in C_estimates if n < 350]
    cs_late = [c for n, c in C_estimates if n >= 350]
    if cs_early and cs_late:
        print(f"  C (n<350): {sum(cs_early)/len(cs_early):.6f}")
        print(f"  C (n≥350): {sum(cs_late)/len(cs_late):.6f}")

# ─── NEW: Check if R(n) oscillation has a pattern ───
print("\n=== R(n) oscillation analysis (sign of R(n)-R(n-1)) ===")
sign_changes = 0
up_count = 0
down_count = 0
for n in range(11, N_MAX + 1):
    diff = ratios[n][0] - ratios[n-1][0]
    if diff > 0:
        up_count += 1
    else:
        down_count += 1
print(f"  Up (R increases): {up_count}, Down (R decreases): {down_count}")
print(f"  Ratio up/total: {up_count/(up_count+down_count):.4f}")

# Count consecutive ups
max_consec_up = 0
curr_consec_up = 0
for n in range(11, N_MAX + 1):
    diff = ratios[n][0] - ratios[n-1][0]
    if diff > 0:
        curr_consec_up += 1
        max_consec_up = max(max_consec_up, curr_consec_up)
    else:
        curr_consec_up = 0
print(f"  Max consecutive increases of R(n): {max_consec_up}")

print("\n=== Done ===")
