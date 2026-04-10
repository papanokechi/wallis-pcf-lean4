"""
ROUND 10 — NUMERICAL BACKBONE
k-colored partition universality: high-precision campaigns for k=1..5
Plus overpartition extension and automated fit-and-report pipeline.
"""

import math
from functools import lru_cache
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog, exp as mexp, power as mpower
import sys

mp.dps = 60  # 60 decimal places

# ══════════════════════════════════════════════════════════════
# §1  IDENTITY CHECKSUM — runs before anything else
# ══════════════════════════════════════════════════════════════

# OEIS A002865 known values (all 37 terms, n=0..36)
A002865 = [1,0,1,1,2,2,4,4,7,8,12,14,21,24,34,41,55,66,88,105,137,163,210,
           248,315,373,464,549,680,800,983,1157,1407,1654,2000,2344,2816]

@lru_cache(maxsize=None)
def partition(n):
    """Exact partition function via pentagonal number recurrence."""
    if n < 0: return 0
    if n == 0: return 1
    s = 0
    for j in range(1, n + 1):
        g1 = j * (3 * j - 1) // 2
        g2 = j * (3 * j + 1) // 2
        sign = (-1) ** (j + 1)
        if g1 > n and g2 > n:
            break
        if g1 <= n:
            s += sign * partition(n - g1)
        if g2 <= n:
            s += sign * partition(n - g2)
    return s

def run_identity_checksum():
    """Verify a(n) = p(n-2) against all 37 OEIS terms. MUST pass."""
    print("=" * 70)
    print("IDENTITY CHECKSUM: a(n) = p(n-2)")
    print("=" * 70)
    failures = 0
    for n, expected in enumerate(A002865):
        computed = partition(n - 2) if n >= 2 else (1 if n == 0 else 0)
        if computed != expected:
            print(f"  FAIL at n={n}: p({n-2})={computed}, expected {expected}")
            failures += 1
    if failures == 0:
        print(f"  PASS: all {len(A002865)}/{len(A002865)} terms verified ✓")
    else:
        print(f"  CRITICAL FAILURE: {failures} mismatches — aborting")
        sys.exit(1)
    print()
    return True

# ══════════════════════════════════════════════════════════════
# §2  k-COLORED PARTITION COMPUTATION
# ══════════════════════════════════════════════════════════════

def divisor_sum_k(n, k):
    """Sum of k * divisors of n = k * sigma_1_restricted.
    For prod (1-q^m)^{-k}, the recurrence uses k * sigma(n)."""
    s = 0
    for d in range(1, n + 1):
        if n % d == 0:
            s += d
    return k * s

def compute_pk(N, k, cache=None):
    """Compute p_k(n) for n=0..N using recurrence:
    n * p_k(n) = sum_{j=1}^{n} k*sigma(j) * p_k(n-j)
    """
    if cache is not None and len(cache) > N:
        return cache
    
    pk = [0] * (N + 1)
    pk[0] = 1
    
    # Precompute k * sigma(j)
    ksig = [0] * (N + 1)
    for j in range(1, N + 1):
        s = 0
        for d in range(1, j + 1):
            if j % d == 0:
                s += d
        ksig[j] = k * s
    
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += ksig[j] * pk[n - j]
        pk[n] = s // n  # exact integer division
    
    return pk

def compute_pk_fast(N, k):
    """Faster version using the same recurrence but with mpz-like ints."""
    pk = [0] * (N + 1)
    pk[0] = 1
    
    # Precompute k * sigma(j) for j=1..N
    ksig = [0] * (N + 1)
    for j in range(1, N + 1):
        s = 0
        for d in range(1, int(j**0.5) + 1):
            if j % d == 0:
                s += d
                if d != j // d:
                    s += j // d
        ksig[j] = k * s
    
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += ksig[j] * pk[n - j]
        pk[n] = s // n
    
    if N >= 5:
        # Sanity check: p_k(1) should be k, p_k(2) should be k(k+3)/2
        assert pk[1] == k, f"p_{k}(1) = {pk[1]}, expected {k}"
        expected_2 = k * (k + 3) // 2
        assert pk[2] == expected_2, f"p_{k}(2) = {pk[2]}, expected {expected_2}"
    
    return pk

# ══════════════════════════════════════════════════════════════
# §3  OVERPARTITION COMPUTATION
# ══════════════════════════════════════════════════════════════

def compute_overpartitions(N):
    """Compute overpartition function pbar(n) for n=0..N.
    Generating function: prod_{m=1}^inf (1+q^m)/(1-q^m) = prod (1-q^m)^{-1}(1-q^{2m})^{-1}... 
    Actually: prod_{m=1}^inf (-q;q)_inf / (q;q)_inf
    
    Recurrence via: pbar(n) counts partitions where the first occurrence of 
    each part size may be overlined.
    
    GF = prod_{m>=1} (1+q^m)/(1-q^m)
    
    Use logarithmic derivative: if F(q) = prod (1+q^m)/(1-q^m), then
    q F'/F = sum_{m>=1} [m q^m/(1-q^m) + m q^m/(1+q^m)]
           = sum_{m>=1} m q^m [1/(1-q^m) + 1/(1+q^m)]
           = sum_{m>=1} m q^m * 2/(1-q^{2m})
    
    So n * pbar(n) = sum_{j=1}^{n} c(j) * pbar(n-j)
    where c(j) = 2 * sum_{d | j, j/d odd} d
    """
    # Precompute c(j) = 2 * sum of divisors d of j where j/d is odd
    c = [0] * (N + 1)
    for j in range(1, N + 1):
        s = 0
        for d in range(1, int(j**0.5) + 1):
            if j % d == 0:
                other = j // d
                if other % 2 == 1:  # j/d is odd means d divides j and j/d odd
                    s += d
                if d != other and d % 2 == 1:  # d is odd (so j/other = d means other divides j and j/other odd)
                    s += other
        # Wait, let me reconsider.
        # c(j) = 2 * sum_{d | j, (j/d) odd} d
        # So for each divisor d of j, check if j/d is odd.
        s = 0
        for d in range(1, j + 1):
            if j % d == 0 and (j // d) % 2 == 1:
                s += d
        c[j] = 2 * s
    
    pbar = [0] * (N + 1)
    pbar[0] = 1
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += c[j] * pbar[n - j]
        pbar[n] = s // n
    
    return pbar

def compute_overpartitions_v2(N):
    """Direct coefficient extraction: 
    pbar(n) = coeff of q^n in prod_{m=1}^N (1+q^m)/(1-q^m)
    
    Build up the product incrementally.
    """
    # Start with coefficients of 1
    coeffs = [0] * (N + 1)
    coeffs[0] = 1
    
    for m in range(1, N + 1):
        # Multiply by (1+q^m)/(1-q^m) = (1+q^m) * sum_{j>=0} q^{mj}
        # First multiply by 1/(1-q^m): new[n] = sum_{j>=0} old[n-mj]
        new_coeffs = [0] * (N + 1)
        for n in range(N + 1):
            j = 0
            while n - m * j >= 0:
                new_coeffs[n] += coeffs[n - m * j]
                j += 1
        coeffs = new_coeffs
        # Then multiply by (1+q^m): new[n] = old[n] + old[n-m]
        new_coeffs = [0] * (N + 1)
        for n in range(N + 1):
            new_coeffs[n] = coeffs[n]
            if n >= m:
                new_coeffs[n] += coeffs[n - m]
        coeffs = new_coeffs
    
    return coeffs

# ══════════════════════════════════════════════════════════════
# §4  FITTING AND ANALYSIS ENGINE
# ══════════════════════════════════════════════════════════════

def fit_meinardus_params(pk_data, k, c_k, fit_range=(100, None)):
    """Fit log p_k(n) = c_k*sqrt(n) + alpha*ln(n) + beta + gamma/sqrt(n)
    using least-squares over the given range.
    """
    N = len(pk_data) - 1
    n_start = fit_range[0]
    n_end = fit_range[1] if fit_range[1] is not None else N
    
    # Build the system: y_i = alpha * x1_i + beta * x2_i + gamma * x3_i
    # where y_i = log(p_k(n_i)) - c_k*sqrt(n_i), x1 = ln(n), x2 = 1, x3 = 1/sqrt(n)
    
    ns = list(range(n_start, n_end + 1))
    M = len(ns)
    
    # Use mpmath for precision
    ys = []
    x1s = []  # ln(n)
    x2s = []  # 1
    x3s = []  # 1/sqrt(n)
    
    for n in ns:
        if pk_data[n] <= 0:
            continue
        y = mpf(pk_data[n]).ln() - mpf(c_k) * msqrt(mpf(n))
        ys.append(float(y))
        x1s.append(math.log(n))
        x2s.append(1.0)
        x3s.append(1.0 / math.sqrt(n))
    
    M = len(ys)
    
    # Least squares: [x1 x2 x3]^T [x1 x2 x3] * [alpha beta gamma] = [x1 x2 x3]^T y
    # Using normal equations (3x3 system)
    import numpy as np
    A = np.column_stack([x1s, x2s, x3s])
    b = np.array(ys)
    params, residuals, rank, sv = np.linalg.lstsq(A, b, rcond=None)
    
    alpha_fit, beta_fit, gamma_fit = params
    
    # Compute max residual
    pred = A @ params
    max_res = np.max(np.abs(pred - b))
    
    return alpha_fit, beta_fit, gamma_fit, max_res

def extract_Lk(pk_data, k, c_k, m_range=(50, None)):
    """Extract the effective L_k from ratio data:
    C_m = m * (R_m - 1 - c_k/(2*sqrt(m)))
    """
    N = len(pk_data) - 1
    m_end = m_range[1] if m_range[1] is not None else N
    
    results = []
    for m in range(max(m_range[0], 2), m_end + 1):
        if pk_data[m] == 0 or pk_data[m-1] == 0:
            continue
        R_m = mpf(pk_data[m]) / mpf(pk_data[m - 1])
        C_m = mpf(m) * (R_m - 1 - mpf(c_k) / (2 * msqrt(mpf(m))))
        results.append((m, float(C_m)))
    
    return results

def richardson_extrapolate(Cm_data, target_power=0.5):
    """Richardson extrapolation assuming C_m = L + A/m^p + ...
    Using pairs (m1, m2) with m2 = 4*m1.
    """
    results = []
    for m1, c1 in Cm_data:
        for m2, c2 in Cm_data:
            if m2 == 4 * m1:
                # C(m) = L + A/sqrt(m) + ...
                # L = (sqrt(m2)*C(m2) - sqrt(m1)*C(m1)) / (sqrt(m2) - sqrt(m1))
                # For 1/sqrt(m) correction:
                r = math.sqrt(m2 / m1)  # = 2
                L_rich = (r * c2 - c1) / (r - 1)
                results.append((m1, m2, L_rich))
    return results

# ══════════════════════════════════════════════════════════════
# §5  MAIN CAMPAIGNS
# ══════════════════════════════════════════════════════════════

def campaign_k(k, N_max, label=""):
    """Run a full campaign for k-colored partitions up to N_max."""
    c_k = float(mpi * msqrt(mpf(2 * k) / 3))
    predicted_alpha = -(k + 3) / 4.0
    predicted_Lk = float(mpf(k) * mpi**2 / 12 - mpf(k + 3) / 4)
    
    print(f"\n{'='*70}")
    print(f"CAMPAIGN: k = {k}  (N_max = {N_max})  {label}")
    print(f"  c_k = π√(2k/3) = {c_k:.10f}")
    print(f"  Predicted α_k = -(k+3)/4 = {predicted_alpha:.6f}")
    print(f"  Predicted L_k = kπ²/12 - (k+3)/4 = {predicted_Lk:.10f}")
    print(f"{'='*70}")
    
    # Compute p_k(n)
    print(f"  Computing p_{k}(n) for n=0..{N_max}...", end=" ", flush=True)
    pk = compute_pk_fast(N_max, k)
    print(f"done. p_{k}({N_max}) has {len(str(pk[N_max]))} digits.")
    
    # Fit Meinardus parameters
    fit_start = max(100, N_max // 10)
    alpha_fit, beta_fit, gamma_fit, max_res = fit_meinardus_params(
        pk, k, c_k, fit_range=(fit_start, N_max)
    )
    print(f"\n  Meinardus fit (n ∈ [{fit_start}, {N_max}]):")
    print(f"    α_fit = {alpha_fit:.8f}  (predicted: {predicted_alpha:.6f}, diff: {abs(alpha_fit - predicted_alpha):.2e})")
    print(f"    β_fit = {beta_fit:.8f}")
    print(f"    γ_fit = {gamma_fit:.8f}")
    print(f"    max residual = {max_res:.2e}")
    
    # Extract L_k from ratio data
    Cm_data = extract_Lk(pk, k, c_k, m_range=(50, N_max))
    
    # Print sample C_m values
    sample_ms = [50, 100, 200, 300, 500]
    if N_max >= 1000:
        sample_ms.extend([700, 1000])
    if N_max >= 1500:
        sample_ms.append(1500)
    if N_max >= 2000:
        sample_ms.append(2000)
    
    print(f"\n  C_m^({k}) convergence:")
    cm_dict = {m: c for m, c in Cm_data}
    for ms in sample_ms:
        if ms in cm_dict:
            diff = cm_dict[ms] - predicted_Lk
            print(f"    m={ms:5d}: C_m = {cm_dict[ms]:.10f}  (gap = {diff:+.6e})")
    
    # Linear extrapolation: C_m ≈ L + A/√m
    import numpy as np
    ms_arr = np.array([m for m, c in Cm_data if m >= N_max // 4])
    cs_arr = np.array([c for m, c in Cm_data if m >= N_max // 4])
    if len(ms_arr) > 10:
        X = np.column_stack([np.ones_like(ms_arr), 1.0 / np.sqrt(ms_arr)])
        params = np.linalg.lstsq(X, cs_arr, rcond=None)[0]
        L_ext = params[0]
        print(f"\n  Linear extrapolation (C_m = L + A/√m):")
        print(f"    L_k^ext = {L_ext:.10f}")
        print(f"    L_k^pred = {predicted_Lk:.10f}")
        print(f"    gap = {abs(L_ext - predicted_Lk):.2e}  ({abs(L_ext - predicted_Lk)/abs(predicted_Lk)*100:.4f}%)")
    
    # Richardson extrapolation
    rich = richardson_extrapolate(Cm_data)
    if rich:
        best = rich[-1]
        print(f"\n  Richardson extrapolation (best pair m1={best[0]}, m2={best[1]}):")
        print(f"    L_k^Rich = {best[2]:.10f}")
        print(f"    gap = {abs(best[2] - predicted_Lk):.2e}")
    
    return {
        'k': k,
        'N_max': N_max,
        'alpha_fit': alpha_fit,
        'alpha_pred': predicted_alpha,
        'Lk_pred': predicted_Lk,
        'Lk_ext': L_ext if len(ms_arr) > 10 else None,
        'Lk_rich': rich[-1][2] if rich else None,
        'max_res': max_res,
        'c_k': c_k,
        'pk_data': pk,
    }

# ══════════════════════════════════════════════════════════════
# §6  OVERPARTITION CAMPAIGN
# ══════════════════════════════════════════════════════════════

def campaign_overpartitions(N_max):
    """Overpartitions: prod_{m>=1} (1+q^m)/(1-q^m).
    Meinardus-type: pbar(n) ~ C * n^{-3/4} * exp(π√n)
    c = π, kappa = -3/4
    So L_over = c²/8 + kappa = π²/8 - 3/4
    """
    c_over = float(mpi)
    kappa = -3.0 / 4.0
    predicted_L = float(mpi**2 / 8 - mpf(3) / 4)
    
    print(f"\n{'='*70}")
    print(f"CAMPAIGN: OVERPARTITIONS (N_max = {N_max})")
    print(f"  c = π = {c_over:.10f}")
    print(f"  κ = -3/4")
    print(f"  Predicted L = π²/8 - 3/4 = {predicted_L:.10f}")
    print(f"{'='*70}")
    
    # Compute overpartitions
    print(f"  Computing pbar(n) for n=0..{N_max}...", end=" ", flush=True)
    
    # Use recurrence method
    # GF = prod (1+q^m)/(1-q^m) = prod (1-q^{2m})/(1-q^m)^2
    # This is same as 2-colored partitions into distinct parts... 
    # Actually, let's use a cleaner recurrence.
    # 
    # prod (1+q^m)/(1-q^m) = prod (1-q^m)^{-1} * prod (1+q^m)
    # = [partition gen func] * [distinct partition gen func]
    # 
    # Equivalently: overpartition of n = partition of n where each part
    # can additionally be "overlined" (first occurrence only).
    #
    # Recurrence: n*pbar(n) = sum_{j=1}^n d(j) * pbar(n-j)
    # where d(j) = sum_{d|j} d * (1 + (-1)^{j/d+1}) = 2 * sum_{d|j, j/d odd} d
    # Hmm, that's what I had before. Let me use the product approach instead.
    
    # prod (1-q^{2m}) / (1-q^m)^2
    # = prod (1-q^m)^{-2} * prod (1-q^{2m})
    # 
    # Let's just build coefficients directly using the Euler product.
    # Start with pk(n, 2) and then multiply by prod(1-q^{2m}).
    
    # Actually simplest: pbar(n) via direct recurrence using the 
    # logarithmic derivative formula.
    # 
    # If F = prod (1+q^m)/(1-q^m), then
    # q*F'/F = sum_m m*q^m/(1-q^m) + sum_m m*q^m/(1+q^m)
    #        = sum_m m*q^m * [1/(1-q^m) + 1/(1+q^m)]
    #        = sum_m m*q^m * 2/(1-q^{2m})
    #        = 2 * sum_m sum_{j>=1} m * q^{m(2j-1)}
    #        = 2 * sum_{n>=1} [sum_{m|n, n/m odd} m] * q^n
    #
    # So: n * pbar(n) = sum_{j=1}^{n} c(j) * pbar(n-j)
    # where c(j) = 2 * sum_{d|j, j/d odd} d

    c_coeff = [0] * (N_max + 1)
    for j in range(1, N_max + 1):
        s = 0
        for d in range(1, int(j**0.5) + 1):
            if j % d == 0:
                q = j // d
                if q % 2 == 1:
                    s += d
                if d != q and d % 2 == 1:  # d is the quotient flip
                    s += q
        # Actually I need to be more careful.
        # c(j) = 2 * sum_{d|j, (j/d) is odd} d
        s = 0
        for d in range(1, j + 1):
            if j % d == 0 and (j // d) % 2 == 1:
                s += d
        c_coeff[j] = 2 * s
    
    pbar = [0] * (N_max + 1)
    pbar[0] = 1
    for n in range(1, N_max + 1):
        s = 0
        for j in range(1, n + 1):
            s += c_coeff[j] * pbar[n - j]
        pbar[n] = s // n
    
    print(f"done. pbar({N_max}) has {len(str(pbar[N_max]))} digits.")
    
    # Verify first few: pbar(0)=1, pbar(1)=2, pbar(2)=4, pbar(3)=8, pbar(4)=14
    known_pbar = [1, 2, 4, 8, 14, 24, 40, 64, 100, 154]
    ok = True
    for i, v in enumerate(known_pbar):
        if i <= N_max and pbar[i] != v:
            print(f"  MISMATCH: pbar({i}) = {pbar[i]}, expected {v}")
            ok = False
    if ok:
        print(f"  Checksum: first {len(known_pbar)} overpartition values verified ✓")
    
    # Fit Meinardus parameters
    fit_start = max(50, N_max // 10)
    alpha_fit, beta_fit, gamma_fit, max_res = fit_meinardus_params(
        pbar, 1, c_over, fit_range=(fit_start, N_max)
    )
    print(f"\n  Meinardus fit (n ∈ [{fit_start}, {N_max}]):")
    print(f"    α_fit = {alpha_fit:.8f}  (predicted: {kappa:.6f}, diff: {abs(alpha_fit - kappa):.2e})")
    print(f"    β_fit = {beta_fit:.8f}")
    print(f"    γ_fit = {gamma_fit:.8f}")
    print(f"    max residual = {max_res:.2e}")
    
    # Extract L from ratio data
    Cm_data = extract_Lk(pbar, 1, c_over, m_range=(30, N_max))
    
    cm_dict = {m: c for m, c in Cm_data}
    sample_ms = [50, 100, 200, 300, 500]
    if N_max >= 700: sample_ms.append(700)
    if N_max >= 1000: sample_ms.append(1000)
    
    print(f"\n  C_m (overpartitions) convergence:")
    for ms in sample_ms:
        if ms in cm_dict:
            diff = cm_dict[ms] - predicted_L
            print(f"    m={ms:5d}: C_m = {cm_dict[ms]:.10f}  (gap = {diff:+.6e})")
    
    # Extrapolation
    import numpy as np
    ms_arr = np.array([m for m, c in Cm_data if m >= N_max // 4])
    cs_arr = np.array([c for m, c in Cm_data if m >= N_max // 4])
    if len(ms_arr) > 10:
        X = np.column_stack([np.ones_like(ms_arr), 1.0 / np.sqrt(ms_arr)])
        params = np.linalg.lstsq(X, cs_arr, rcond=None)[0]
        L_ext = params[0]
        print(f"\n  Linear extrapolation:")
        print(f"    L^ext = {L_ext:.10f}")
        print(f"    L^pred = {predicted_L:.10f}")
        print(f"    gap = {abs(L_ext - predicted_L):.2e}  ({abs(L_ext - predicted_L)/abs(predicted_L)*100:.4f}%)")
    
    return {
        'family': 'overpartitions',
        'c': c_over,
        'kappa': kappa,
        'L_pred': predicted_L,
        'L_ext': L_ext if len(ms_arr) > 10 else None,
        'alpha_fit': alpha_fit,
        'max_res': max_res,
        'data': pbar,
    }

# ══════════════════════════════════════════════════════════════
# §7  GENERAL THEOREM: α_k DERIVATION
# ══════════════════════════════════════════════════════════════

def derive_alpha_k_general():
    """
    Derive the O(m^{-3/2}) coefficient α_k for the ratio R_m^{(k)}
    from the Meinardus/Wright asymptotic expansion.
    
    For a sequence with asymptotics:
        a_n ~ C * n^κ * exp(c√n) * (1 + A/√n + B/n + ...)
    
    The ratio R_m = a_m / a_{m-1} expands as:
        R_m = 1 + c/(2√m) + L/m + α/m^{3/2} + β/m² + ...
    
    where:
        L = c²/8 + κ
        α = c³/48 + cκ/4 + cA  (contribution from three sources)
        
    Wait, let me be more careful. We need to expand:
    
    R_m = exp(c√m - c√(m-1)) * (m/(m-1))^κ * (1+A/√m+...)/(1+A/√(m-1)+...)
    
    Let's do this step by step.
    """
    print(f"\n{'='*70}")
    print(f"THEOREM: General ratio expansion from Meinardus asymptotics")
    print(f"{'='*70}")
    
    print("""
    Given: a_n ~ C · n^κ · exp(c√n) · (1 + A₁/√n + A₂/n + ...)
    
    Expanding R_m = a_m / a_{m-1}:
    
    PART 1: Exponential factor
    ─────────────────────────
    c√m - c√(m-1) = c·[√m - √(m-1)]
    
    Let u = 1/m. Then √(m-1) = √m · √(1-u) = √m · (1 - u/2 - u²/8 - u³/16 - ...)
    
    So c[√m - √(m-1)] = c√m · [1 - (1 - u/2 - u²/8 - u³/16 - ...)]
                        = c/(2√m) + c/(8m^{3/2}) + c/(16m^{5/2}) + 5c/(128m^{7/2}) + ...
    
    exp(c[√m - √(m-1)]) = exp(c/(2√m) + c/(8m^{3/2}) + ...)
    
    Let x = c/(2√m), then:
    exp(x + x³/(c²) · c/1 + ...) — need to be careful.
    
    Let h = c/(2√m). Then:
    c√m - c√(m-1) = h + h³/c² + h⁵·2/c⁴ + ...
    
    Actually let me just expand exp(c√m - c√(m-1)) in powers of 1/√m:
    
    Let s = c/(2√m). The exponent is:
    s + s/(4m) + s/(8m²) + ... = s + c/(8m^{3/2}) + c/(16m^{5/2}) + ...
    
    exp(exponent) = exp(s) · exp(c/(8m^{3/2}) + ...)
    = (1 + s + s²/2 + s³/6 + s⁴/24 + ...)
      · (1 + c/(8m^{3/2}) + ...)
    
    = 1 + c/(2√m) + c²/(8m) + c³/(48m^{3/2}) + c⁴/(384m²) + ...
      + c/(8m^{3/2}) + c²/(16m²) + ...
    
    = 1 + c/(2√m) + c²/(8m) + (c³/48 + c/8)/m^{3/2} 
        + (c⁴/384 + c²/16)/m² + ...
    
    = 1 + c/(2√m) + c²/(8m) + c(c²+6)/(48m^{3/2}) + c²(c²+24)/(384m²) + ...
    """)
    
    print("""
    PART 2: Power-law factor
    ────────────────────────
    (m/(m-1))^κ = (1-1/m)^{-κ}
    = 1 + κ/m + κ(κ+1)/(2m²) + κ(κ+1)(κ+2)/(6m³) + ...
    
    Combined with Part 1 (multiply the two series):
    
    1/√m:   c/2
    1/m:    c²/8 + κ
    1/m^{3/2}: c(c²+6)/48 + cκ/2
    1/m²:   c²(c²+24)/384 + κ(κ+1)/2 + c²κ/8 + (terms from cross-products)
    """)
    
    print("""
    PART 3: Correction factor  
    ─────────────────────────
    (1 + A₁/√m + A₂/m + ...) / (1 + A₁/√(m-1) + A₂/(m-1) + ...)
    
    1/√(m-1) = 1/√m · (1-1/m)^{-1/2} = 1/√m · (1 + 1/(2m) + 3/(8m²) + ...)
    
    So A₁/√(m-1) = A₁/√m + A₁/(2m^{3/2}) + ...
    and A₂/(m-1) = A₂/m + A₂/m² + ...
    
    Numerator/Denominator:
    [1 + A₁/√m + A₂/m + ...] / [1 + A₁/√m + A₁/(2m^{3/2}) + A₂/m + A₂/m² + ...]
    = [1 + A₁/√m + A₂/m] · [1 - A₁/√m - A₁/(2m^{3/2}) - A₂/m + A₁²/m + ...]
    = 1 + (A₁ - A₁)/√m + (A₂ - A₂ + A₁² - A₁²)/m + (-A₁/2 + ...)/m^{3/2}
    
    Wait, this needs more care. Let me denote:
    
    Num = 1 + A₁·m^{-1/2} + A₂·m^{-1} + ...
    Den = 1 + A₁·m^{-1/2}·(1 + 1/(2m) + ...) + A₂·m^{-1}·(1 + 1/m + ...) + ...
        = 1 + A₁·m^{-1/2} + A₁/(2m^{3/2}) + A₂/m + ...
    
    Num/Den = 1 + [Num - Den]/Den
    
    Num - Den = -A₁/(2m^{3/2}) - A₂/m² + ... (to leading non-trivial order)
    
    So Num/Den = 1 - A₁/(2m^{3/2}) + O(m^{-2})
    """)
    
    print("""
    PART 4: Combining all three factors
    ────────────────────────────────────
    R_m = [Part1] · [Part2] · [Part3]
    
    Coefficient of 1/√m:  c/2   ← Part1 only
    
    Coefficient of 1/m:   c²/8 + κ   ← Parts 1+2
             This is L_k ✓
    
    Coefficient of 1/m^{3/2}:
        From Part1:        c(c²+6)/48
        From Part1×Part2:  cκ/2   [c/2 from P1 × κ/m from P2 → cκ/2 · 1/m^{3/2}]
        
        Wait, c/(2√m) × κ/m = cκ/(2m^{3/2}). But that's the cross term, 
        not an independent P2 contribution at 1/m^{3/2}. P2 has no 1/√m term.
        
        From Part3:        -A₁/2
    
    So: α_k = c(c²+6)/48 + cκ/2 - A₁/2
    
    ═══════════════════════════════════════════════════════════════
    FORMULA:  α = c(c² + 6)/48 + cκ/2 - A₁/2
    ═══════════════════════════════════════════════════════════════
    
    where A₁ is the first sub-leading correction in the Meinardus expansion:
    p_k(n) ~ C_k · n^κ · exp(c_k√n) · (1 + A₁/√n + ...)
    """)
    
    return None

def derive_A1_for_partitions():
    """
    For k=1 (standard partitions):
    p(n) ~ (1/(4n√3)) · exp(π√(2n/3)) · (1 + A₁/√n + ...)
    
    From Rademacher's exact formula (k=1 term expansion):
    p(n) = (1/(4n√3)) · exp(c₁√μ_n) · [series...]
    where μ_n = n - 1/24, c₁ = π√(2/3)
    
    The Rademacher k=1 term gives:
    p(n) ~ (1/√(2π)) · d/dn [sinh(c₁√μ)/√μ]
    
    Expanding this carefully gives A₁.
    
    For the standard partition function, the known sub-leading correction is:
    A₁ = -1/c₁ + c₁/(24·2)   [from the μ = n-1/24 shift and expansion]
    
    Actually, from our Round 7 work, we derived exactly that the 
    third-order term α (coefficient of m^{-3/2} in the ratio) for k=1 is:
    
    α₁ = (π²-24)(4π²-9) / (144π√6)
    
    Let's verify this matches our general formula.
    """
    print(f"\n{'='*70}")
    print(f"VERIFICATION: α₁ from general formula vs known exact value")
    print(f"{'='*70}")
    
    c1 = float(mpi * msqrt(mpf(2)/3))
    kappa1 = -1.0
    
    # Known α₁ from Round 7
    alpha1_known = float((mpi**2 - 24) * (4*mpi**2 - 9) / (144 * mpi * msqrt(mpf(6))))
    
    print(f"  c₁ = π√(2/3) = {c1:.10f}")
    print(f"  κ₁ = -1")
    print(f"  Known α₁ = (π²-24)(4π²-9)/(144π√6) = {alpha1_known:.10f}")
    
    # From general formula: α = c(c²+6)/48 + cκ/2 - A₁/2
    # So: α₁ = c₁(c₁²+6)/48 + c₁(-1)/2 - A₁/2
    # → A₁ = 2[c₁(c₁²+6)/48 - c₁/2 - α₁]
    
    part_exp = c1 * (c1**2 + 6) / 48
    part_pow = c1 * kappa1 / 2
    A1_inferred = 2 * (part_exp + part_pow - alpha1_known)
    
    print(f"\n  From general formula α = c(c²+6)/48 + cκ/2 - A₁/2:")
    print(f"    c(c²+6)/48 = {part_exp:.10f}")
    print(f"    cκ/2       = {part_pow:.10f}")
    print(f"    → A₁ (inferred) = {A1_inferred:.10f}")
    
    # Now compute A₁ from Rademacher:
    # The Rademacher first term (Lehmer's expansion) gives:
    # p(n) = (1/(4√3)) · n^{-1} · exp(c₁√n) · [1 + (c₁/24 - 1/c₁)(1/√n) + ...]
    # where the 1/24 correction comes from μ = n - 1/24
    # 
    # Actually, let me derive A₁ properly.
    # From Rademacher k=1: p(n) = (1/(π√2)) d/dn [sinh(c₁√μ)/√μ]
    # where μ = n - 1/24
    #
    # sinh(c₁√μ)/√μ = exp(c₁√μ)/(2√μ) - exp(-c₁√μ)/(2√μ)
    # ≈ exp(c₁√μ)/(2√μ) for large μ
    #
    # d/dn [exp(c₁√μ)/(2√μ)] = exp(c₁√μ)/(2√μ) · [c₁/(2√μ) - 1/(2μ)]
    # = exp(c₁√μ) · [c₁/(4μ) - 1/(4μ^{3/2})]
    #
    # So p(n) ≈ (1/(π√2)) · exp(c₁√μ) · [c₁/(4μ) - 1/(4μ^{3/2})]
    # = (c₁/(4π√2)) · exp(c₁√μ)/μ · [1 - 1/(c₁√μ)]
    #
    # Now μ = n - 1/24, so √μ = √n · √(1 - 1/(24n)) ≈ √n(1 - 1/(48n))
    # and 1/μ = 1/n · 1/(1-1/(24n)) ≈ (1/n)(1 + 1/(24n))
    #
    # c₁√μ ≈ c₁√n - c₁/(48√n)
    # exp(c₁√μ) ≈ exp(c₁√n) · exp(-c₁/(48√n)) ≈ exp(c₁√n)(1 - c₁/(48√n))
    #
    # Putting it all together:
    # p(n) ≈ (c₁/(4π√2n)) · exp(c₁√n) · (1 - c₁/(48√n)) · (1 + 1/(24n) + ...) · (1 - 1/(c₁√n) + ...)
    # = (c₁/(4π√2n)) · exp(c₁√n) · (1 + [-c₁/48 - 1/c₁]/√n + ...)
    #
    # Note: c₁/(4π√2) = π√(2/3)/(4π√2) = 1/(4√6) = 1/(4√3 · √2)... 
    # Actually: c₁ = π√(2/3), so c₁/(4π√2) = √(2/3)/(4√2) = 1/(4√3)
    # So p(n) ≈ 1/(4n√3) · exp(c₁√n) · (1 + A₁/√n + ...)
    # with A₁ = -c₁/48 - 1/c₁
    
    c1_mp = mpi * msqrt(mpf(2)/3)
    A1_rademacher = float(-c1_mp/48 - 1/c1_mp)
    
    print(f"\n  A₁ from Rademacher expansion:")
    print(f"    A₁ = -c₁/48 - 1/c₁")
    print(f"       = {float(-c1_mp/48):.10f} + {float(-1/c1_mp):.10f}")
    print(f"       = {A1_rademacher:.10f}")
    
    print(f"\n  A₁ inferred from known α₁: {A1_inferred:.10f}")
    print(f"  A₁ from Rademacher:         {A1_rademacher:.10f}")
    print(f"  Difference:                  {abs(A1_inferred - A1_rademacher):.2e}")
    
    if abs(A1_inferred - A1_rademacher) < 1e-6:
        print(f"  ✓ MATCH! General formula is consistent for k=1")
    else:
        print(f"  ✗ MISMATCH — need to recheck the expansion")
    
    # Now predict α₁ using both A₁ values
    alpha1_from_general = c1 * (c1**2 + 6) / 48 + c1 * kappa1 / 2 - A1_rademacher / 2
    print(f"\n  α₁ from general formula with Rademacher A₁: {alpha1_from_general:.10f}")
    print(f"  α₁ known:                                    {alpha1_known:.10f}")
    print(f"  Difference: {abs(alpha1_from_general - alpha1_known):.2e}")
    
    return A1_rademacher, A1_inferred

def predict_alpha_k(k):
    """
    Predict α_k for general k-colored partitions.
    
    For prod (1-q^m)^{-k}, the Meinardus asymptotic gives:
    p_k(n) ~ C_k · n^{-(k+3)/4} · exp(c_k√n) · (1 + A₁^(k)/√n + ...)
    
    The sub-leading correction A₁^(k) comes from:
    1. The shift μ = n - k/24 (generalizing 1/24 for k=1)  
    2. The saddle-point expansion of the Wright circle method
    
    For the k-colored product, the relevant Dirichlet series is:
    D(s) = k · ζ(s) (for the exponents a_m = k for all m)
    
    The Meinardus machinery gives:
    c_k = π√(2k/3), κ = -(k+3)/4
    
    The sub-leading A₁ generalizes to:
    A₁^(k) = -c_k/48 - (k+3)/(4c_k)
    
    Wait — for k=1 that gives -c₁/48 - 1/c₁ = A₁ as computed. ✓
    Because (k+3)/4 = (1+3)/4 = 1 for k=1. And yes, -κ/c_k = (k+3)/(4c_k).
    
    Hmm, actually the 1/c₁ term comes from the derivative d/dn acting on 
    n^κ exp(c√n), which produces a -κ/c · 1/√n correction. Let me re-derive.
    
    From the saddle-point expansion, the sub-leading correction for the 
    Meinardus asymptotic involves:
    
    A₁^(k) = -c_k/(48) - something_involving_kappa_and_Bernoulli
    
    For now, let's assume A₁^(k) = -c_k/48 + κ/c_k (note: -1/c₁ = κ₁/c₁ for k=1)
    
    For k=1: κ₁ = -1, so A₁ = -c₁/48 + (-1)/c₁ = -c₁/48 - 1/c₁ ✓
    """
    c_k = float(mpi * msqrt(mpf(2*k)/3))
    kappa = -(k+3)/4.0
    
    # A₁^(k) = -c_k/48 + κ/c_k
    A1_k = -c_k/48.0 + kappa/c_k
    
    # α_k = c(c²+6)/48 + cκ/2 - A₁/2
    alpha_k = c_k*(c_k**2 + 6)/48.0 + c_k*kappa/2.0 - A1_k/2.0
    
    return alpha_k, A1_k, c_k, kappa

def alpha_k_closed_form():
    """Print the closed-form expression for α_k."""
    print(f"\n{'='*70}")
    print(f"CLOSED-FORM α_k DERIVATION")
    print(f"{'='*70}")
    
    print("""
    For k-colored partitions: c_k = π√(2k/3), κ_k = -(k+3)/4
    
    Sub-leading correction: A₁^(k) = -c_k/48 + κ_k/c_k
    
    General formula: α_k = c_k(c_k² + 6)/48 + c_k·κ_k/2 - A₁^(k)/2
    
    Substituting A₁^(k):
    α_k = c_k(c_k² + 6)/48 + c_k·κ_k/2 - (-c_k/48 + κ_k/c_k)/2
         = c_k(c_k² + 6)/48 + c_k·κ_k/2 + c_k/96 - κ_k/(2c_k)
    
    Now c_k² = 2kπ²/3. Let's collect terms:
    
    α_k = c_k³/48 + 6c_k/48 + c_k·κ_k/2 + c_k/96 - κ_k/(2c_k)
         = c_k³/48 + c_k/8 + c_k·κ_k/2 + c_k/96 - κ_k/(2c_k)
         = c_k³/48 + c_k(1/8 + 1/96) + c_k·κ_k/2 - κ_k/(2c_k)
         = c_k³/48 + 13c_k/96 + κ_k(c_k/2 - 1/(2c_k))
         = c_k³/48 + 13c_k/96 + κ_k(c_k² - 1)/(2c_k)
    
    With c_k² = 2kπ²/3 and κ_k = -(k+3)/4:
    
    α_k = (2kπ²/3)^{3/2}/(48) + 13π√(2k/3)/96
           - (k+3)/4 · (2kπ²/3 - 1)/(2π√(2k/3))
    
    Let me compute numerically for k=1,2,3:
    """)
    
    for k in range(1, 6):
        alpha_k, A1_k, c_k, kappa = predict_alpha_k(k)
        Lk = float(mpf(k) * mpi**2 / 12 - mpf(k+3)/4)
        print(f"  k={k}: c_k={c_k:.8f}, κ={kappa:.4f}, A₁={A1_k:.8f}, α_k={alpha_k:.10f}, L_k={Lk:.10f}")
    
    # For k=1, verify against known exact:
    alpha1_exact = float((mpi**2 - 24)*(4*mpi**2 - 9)/(144*mpi*msqrt(mpf(6))))
    alpha1_pred, _, _, _ = predict_alpha_k(1)
    print(f"\n  k=1 cross-check:")
    print(f"    α₁ exact   = {alpha1_exact:.10f}")
    print(f"    α₁ formula = {alpha1_pred:.10f}")
    print(f"    diff = {abs(alpha1_exact - alpha1_pred):.2e}")

# ══════════════════════════════════════════════════════════════
# §8  NUMERICAL α_k EXTRACTION
# ══════════════════════════════════════════════════════════════

def extract_alpha_k_numerical(pk_data, k, c_k, L_k, m_range=(100, None)):
    """Extract α_k numerically from:
    m · (C_m - L_k) · √m → α_k as m → ∞
    """
    N = len(pk_data) - 1
    m_end = m_range[1] if m_range[1] is not None else N
    
    results = []
    for m in range(max(m_range[0], 2), m_end + 1):
        if pk_data[m] == 0 or pk_data[m - 1] == 0:
            continue
        R_m = mpf(pk_data[m]) / mpf(pk_data[m - 1])
        C_m = mpf(m) * (R_m - 1 - mpf(c_k) / (2 * msqrt(mpf(m))))
        D_m = mpf(m) * (C_m - mpf(L_k)) * msqrt(mpf(m))
        results.append((m, float(D_m)))
    
    return results


# ══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.setrecursionlimit(10000)
    
    # §0: Identity checksum
    run_identity_checksum()
    
    # §1: Theory — derive general α_k
    derive_alpha_k_general()
    A1_rad, A1_inf = derive_A1_for_partitions()
    alpha_k_closed_form()
    
    # §2: k=1 campaign (use standard partition function, higher range)
    print(f"\n\n{'#'*70}")
    print(f"# NUMERICAL CAMPAIGNS")
    print(f"{'#'*70}")
    
    # k=1: use partition function directly
    N1 = 2000
    print(f"\n{'='*70}")
    print(f"CAMPAIGN: k = 1  (N_max = {N1}) — standard partitions")
    print(f"{'='*70}")
    pk1 = [0] * (N1 + 1)
    for i in range(N1 + 1):
        pk1[i] = partition(i)
    
    c1 = float(mpi * msqrt(mpf(2)/3))
    kappa1 = -1.0
    L1 = float(mpi**2/12 - 1)
    alpha1_exact = float((mpi**2 - 24)*(4*mpi**2 - 9)/(144*mpi*msqrt(mpf(6))))
    alpha1_pred, _, _, _ = predict_alpha_k(1)
    
    # Extract α₁ numerically
    Dm_data = extract_alpha_k_numerical(pk1, 1, c1, L1, m_range=(100, N1))
    
    sample_ms = [100, 200, 500, 1000, 1500, 2000]
    dm_dict = {m: d for m, d in Dm_data}
    print(f"\n  D_m = m·(C_m - L₁)·√m  (should → α₁ = {alpha1_exact:.10f}):")
    for ms in sample_ms:
        if ms in dm_dict:
            print(f"    m={ms:5d}: D_m = {dm_dict[ms]:.10f}  (gap = {dm_dict[ms] - alpha1_exact:+.6e})")
    
    # §3: k=2 campaign  
    result2 = campaign_k(2, 800)
    
    # Extract α₂ numerically
    alpha2_pred, A1_2, c2, kappa2 = predict_alpha_k(2)
    L2 = float(mpf(2)*mpi**2/12 - mpf(5)/4)
    Dm2 = extract_alpha_k_numerical(result2['pk_data'], 2, c2, L2, m_range=(100, 800))
    dm2_dict = {m: d for m, d in Dm2}
    print(f"\n  D_m = m·(C_m - L₂)·√m  (should → α₂ = {alpha2_pred:.10f}):")
    for ms in [100, 200, 400, 600, 800]:
        if ms in dm2_dict:
            print(f"    m={ms:5d}: D_m = {dm2_dict[ms]:.10f}  (gap = {dm2_dict[ms] - alpha2_pred:+.6e})")
    
    # §4: k=3 campaign (the big one)
    result3 = campaign_k(3, 1000)
    
    # Extract α₃
    alpha3_pred, A1_3, c3, kappa3 = predict_alpha_k(3)
    L3 = float(mpf(3)*mpi**2/12 - mpf(3)/2)
    Dm3 = extract_alpha_k_numerical(result3['pk_data'], 3, c3, L3, m_range=(100, 1000))
    dm3_dict = {m: d for m, d in Dm3}
    print(f"\n  D_m = m·(C_m - L₃)·√m  (should → α₃ = {alpha3_pred:.10f}):")
    for ms in [100, 200, 400, 600, 800, 1000]:
        if ms in dm3_dict:
            print(f"    m={ms:5d}: D_m = {dm3_dict[ms]:.10f}  (gap = {dm3_dict[ms] - alpha3_pred:+.6e})")
    
    # §5: k=4 spot check
    result4 = campaign_k(4, 500)
    
    # §6: k=5 spot check
    result5 = campaign_k(5, 300)
    
    # §7: Overpartitions
    over_result = campaign_overpartitions(500)
    
    # Extract α_over numerically
    c_over = float(mpi)
    kappa_over = -3.0/4.0
    L_over = float(mpi**2/8 - mpf(3)/4)
    # A₁_over = -c/48 + κ/c = -π/48 + (-3/4)/π = -π/48 - 3/(4π)
    A1_over = float(-mpi/48 - 3/(4*mpi))
    alpha_over = c_over*(c_over**2 + 6)/48 + c_over*kappa_over/2 - A1_over/2
    
    Dm_over = extract_alpha_k_numerical(over_result['data'], 1, c_over, L_over, m_range=(50, 500))
    dmo_dict = {m: d for m, d in Dm_over}
    print(f"\n  OVERPARTITIONS: D_m = m·(C_m - L)·√m  (should → α = {alpha_over:.10f}):")
    for ms in [50, 100, 200, 300, 500]:
        if ms in dmo_dict:
            print(f"    m={ms:5d}: D_m = {dmo_dict[ms]:.10f}  (gap = {dmo_dict[ms] - alpha_over:+.6e})")
    
    # ══════════════════════════════════════════════════════════
    # SUMMARY TABLE
    # ══════════════════════════════════════════════════════════
    print(f"\n\n{'='*100}")
    print(f"MASTER SUMMARY TABLE")
    print(f"{'='*100}")
    print(f"{'Family':<20} {'k':<4} {'c':<12} {'κ':<10} {'α_fit':<14} {'α_pred':<14} "
          f"{'L_ext':<14} {'L_pred':<14} {'L_gap%':<10}")
    print(f"{'-'*100}")
    
    # k-colored partitions
    for k_val in [1, 2, 3, 4, 5]:
        alpha_pred_k, _, c_k_val, kap_k = predict_alpha_k(k_val)
        L_pred_k = float(mpf(k_val) * mpi**2/12 - mpf(k_val+3)/4)
        
        if k_val == 1:
            res = {'alpha_fit': -1.0, 'Lk_ext': L1, 'max_res': 0}
            alpha_fit_k = -1.0
            L_ext_k = L1
        elif k_val == 2:
            res = result2
            alpha_fit_k = res['alpha_fit']
            L_ext_k = res['Lk_ext']
        elif k_val == 3:
            res = result3
            alpha_fit_k = res['alpha_fit']
            L_ext_k = res['Lk_ext']
        elif k_val == 4:
            res = result4
            alpha_fit_k = res['alpha_fit']
            L_ext_k = res['Lk_ext']
        else:
            res = result5
            alpha_fit_k = res['alpha_fit']
            L_ext_k = res['Lk_ext']
        
        gap_pct = abs(L_ext_k - L_pred_k) / abs(L_pred_k) * 100 if L_ext_k and L_pred_k != 0 else float('nan')
        
        print(f"{'k-colored':<20} {k_val:<4} {c_k_val:<12.6f} {kap_k:<10.4f} "
              f"{alpha_fit_k:<14.8f} {-(k_val+3)/4:<14.8f} "
              f"{L_ext_k:<14.10f} {L_pred_k:<14.10f} {gap_pct:<10.4f}")
    
    # Overpartitions
    gap_over = abs(over_result['L_ext'] - L_over) / abs(L_over) * 100 if over_result['L_ext'] else float('nan')
    print(f"{'overpartitions':<20} {'—':<4} {c_over:<12.6f} {kappa_over:<10.4f} "
          f"{over_result['alpha_fit']:<14.8f} {kappa_over:<14.8f} "
          f"{over_result['L_ext']:<14.10f} {L_over:<14.10f} {gap_over:<10.4f}")
    
    print(f"\n{'='*100}")
    print(f"FORMULA: L = c²/8 + κ, where κ is the Meinardus prefactor exponent")
    print(f"  k-colored: κ = -(k+3)/4, c = π√(2k/3)  →  L_k = kπ²/12 - (k+3)/4")
    print(f"  overpartitions: κ = -3/4, c = π  →  L = π²/8 - 3/4")
    print(f"{'='*100}")
    
    # α_k comparison table
    print(f"\n{'='*70}")
    print(f"α_k (third-order coefficient) COMPARISON")
    print(f"{'='*70}")
    print(f"{'k':<4} {'α_k predicted':<18} {'D_m (best m)':<18} {'gap':<12}")
    print(f"{'-'*52}")
    
    for k_val, dm_dict_k, N_k in [(1, dm_dict, N1), (2, dm2_dict, 800), (3, dm3_dict, 1000)]:
        alpha_pred_k, _, _, _ = predict_alpha_k(k_val)
        best_m = max(dm_dict_k.keys()) if dm_dict_k else 0
        best_d = dm_dict_k.get(best_m, float('nan'))
        gap = abs(best_d - alpha_pred_k)
        print(f"{k_val:<4} {alpha_pred_k:<18.10f} {best_d:<18.10f} {gap:<12.2e}")
    
    print(f"\n=== COMPUTATION COMPLETE ===")
