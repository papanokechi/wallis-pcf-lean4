"""
ROUND 10 — NUMERICAL BACKBONE (CORRECTED)

Master research script: k-colored partition universality,
overpartition extension, alpha_k derivation, paper-level tables.

IDENTITY CORRECTION (Round 10):
  A002865: a(n) = p(n) - p(n-1)  [OEIS confirmed]
  NOT a(n) = p(n-2) [Round 2 error; corrupted reference array]
  All results on R_m = p(m)/p(m-1) remain valid.
"""

import math
import sys
import time
import numpy as np
from functools import lru_cache
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog, exp as mexp

mp.dps = 60
sys.setrecursionlimit(10000)

# ══════════════════════════════════════════════════════════════
# §0  PARTITION FUNCTION (standard, k=1)
# ══════════════════════════════════════════════════════════════

@lru_cache(maxsize=None)
def p(n):
    """Exact partition function via Euler pentagonal recurrence."""
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
            s += sign * p(n - g1)
        if g2 <= n:
            s += sign * p(n - g2)
    return s

# ══════════════════════════════════════════════════════════════
# §1  IDENTITY CHECKSUM
# ══════════════════════════════════════════════════════════════

def run_checksum():
    """Verify a(n) = p(n) - p(n-1) against OEIS A002865."""
    A002865 = [
        1, 0, 1, 1, 2, 2, 4, 4, 7, 8, 12, 14, 21, 24, 34, 41, 55, 66, 88,
        105, 137, 165, 210, 253, 320, 383, 478, 574, 708, 847, 1039, 1238,
        1507, 1794, 2167, 2573, 3094, 3660, 4378, 5170, 6153, 7245, 8591,
        10087, 11914, 13959, 16424, 19196, 22519, 26252, 30701
    ]
    print("=" * 70)
    print("IDENTITY CHECKSUM: a(n) = p(n) - p(n-1)  [OEIS A002865]")
    print("=" * 70)
    ok = 0
    for n, expected in enumerate(A002865):
        computed = p(n) - p(n - 1) if n >= 1 else 1
        if computed == expected:
            ok += 1
        else:
            print(f"  FAIL n={n}: got {computed}, expected {expected}")
    status = "ALL PASS ✓" if ok == len(A002865) else f"{len(A002865)-ok} FAILURES"
    print(f"  {ok}/{len(A002865)} match — {status}")
    if ok != len(A002865):
        sys.exit(1)

    known_p = [1,1,2,3,5,7,11,15,22,30,42,56,77,101,135,176,231,297,385,490,
               627,792,1002,1255,1575,1958,2436,3010,3718,4565,5604,6842,8349,
               10143,12310,14883,17977]
    p_ok = all(p(i) == known_p[i] for i in range(len(known_p)))
    print(f"  p(n) vs A000041: {len(known_p)}/{len(known_p)} {'✓' if p_ok else '✗'}")
    print()

# ══════════════════════════════════════════════════════════════
# §2  k-COLORED PARTITION COMPUTATION
# ══════════════════════════════════════════════════════════════

def compute_pk(N, k):
    """p_k(n) = coeff of q^n in prod(1-q^m)^{-k}.
    Recurrence: n*p_k(n) = sum_{j=1}^n k*sigma(j)*p_k(n-j)."""
    pk = [0] * (N + 1)
    pk[0] = 1
    ksig = [0] * (N + 1)
    for j in range(1, N + 1):
        s = 0
        d = 1
        while d * d <= j:
            if j % d == 0:
                s += d
                if d != j // d:
                    s += j // d
            d += 1
        ksig[j] = k * s
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += ksig[j] * pk[n - j]
        pk[n] = s // n
    if N >= 2:
        assert pk[1] == k
        assert pk[2] == k * (k + 3) // 2
    return pk

# ══════════════════════════════════════════════════════════════
# §3  OVERPARTITION COMPUTATION
# ══════════════════════════════════════════════════════════════

def compute_overpartitions(N):
    """pbar(n): prod (1+q^m)/(1-q^m).
    n*pbar(n) = sum c(j)*pbar(n-j), c(j)=2*sum_{d|j,(j/d) odd} d."""
    c = [0] * (N + 1)
    for j in range(1, N + 1):
        s = 0
        d = 1
        while d * d <= j:
            if j % d == 0:
                q = j // d
                if q % 2 == 1:
                    s += d
                if d != q and d % 2 == 1:
                    s += q
            d += 1
        c[j] = 2 * s
    pbar = [0] * (N + 1)
    pbar[0] = 1
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += c[j] * pbar[n - j]
        pbar[n] = s // n
    known = [1, 2, 4, 8, 14, 24, 40, 64, 100, 154]
    for i, v in enumerate(known):
        if i <= N:
            assert pbar[i] == v, f"pbar({i})={pbar[i]} != {v}"
    return pbar

# ══════════════════════════════════════════════════════════════
# §4  FITTING ENGINE
# ══════════════════════════════════════════════════════════════

def fit_meinardus(data, c, fit_range):
    """Fit log f(n) = c*sqrt(n) + alpha*ln(n) + beta + gamma/sqrt(n)."""
    n0, n1 = fit_range
    ys, x1, x2, x3 = [], [], [], []
    for n in range(n0, n1 + 1):
        if data[n] <= 0:
            continue
        y = float(mlog(mpf(data[n])) - mpf(c) * msqrt(mpf(n)))
        ys.append(y)
        x1.append(math.log(n))
        x2.append(1.0)
        x3.append(1.0 / math.sqrt(n))
    A = np.column_stack([x1, x2, x3])
    b = np.array(ys)
    params, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    residuals = np.abs(A @ params - b)
    return params[0], params[1], params[2], float(np.max(residuals))

def extract_Cm(data, c, m_range):
    """C_m = m*(R_m - 1 - c/(2*sqrt(m)))."""
    m0, m1 = m_range
    results = {}
    for m in range(max(m0, 2), m1 + 1):
        if data[m] == 0 or data[m - 1] == 0:
            continue
        R = mpf(data[m]) / mpf(data[m - 1])
        C = mpf(m) * (R - 1 - mpf(c) / (2 * msqrt(mpf(m))))
        results[m] = float(C)
    return results

def extract_Dm(data, c, L, m_range):
    """D_m = (C_m - L)*sqrt(m) → alpha as m→∞."""
    cm = extract_Cm(data, c, m_range)
    return {m: (cv - L) * math.sqrt(m) for m, cv in cm.items()}

def extrapolate_L(cm_dict, m_min):
    """Extrapolate C_m = L + A/sqrt(m)."""
    ms = np.array(sorted(m for m in cm_dict if m >= m_min), dtype=float)
    cs = np.array([cm_dict[int(m)] for m in ms])
    if len(ms) < 10:
        return None
    X = np.column_stack([np.ones_like(ms), 1.0 / np.sqrt(ms)])
    params, _, _, _ = np.linalg.lstsq(X, cs, rcond=None)
    return params[0]

# ══════════════════════════════════════════════════════════════
# §5  THEORY
# ══════════════════════════════════════════════════════════════

def theory_kcolored(k):
    """Predict all coefficients for k-colored partitions."""
    c = float(mpi * msqrt(mpf(2 * k) / 3))
    kappa = -(k + 3) / 4.0
    A1 = -c / 48.0 + kappa / c
    L = c**2 / 8.0 + kappa
    alpha = c * (c**2 + 6) / 48.0 + c * kappa / 2.0 - A1 / 2.0
    return {'c': c, 'kappa': kappa, 'A1': A1, 'L': L, 'alpha': alpha}

def theory_overpartitions():
    """Overpartitions: prod (1+q^m)/(1-q^m) = prod (1-q^m)^{-a_m}
    with a_m=2 (m odd), a_m=1 (m even).
    D(s) = zeta(s)*(2 - 2^{-s}), D(0) = -1/2.
    kappa = (D(0) - 3/2)/2 = -1.  c = pi (residue 3/2)."""
    c = float(mpi)
    kappa = -1.0  # D(0) = -1/2 → (D(0)-3/2)/2 = -1
    A1 = -c / 48.0 + kappa / c
    L = c**2 / 8.0 + kappa
    alpha = c * (c**2 + 6) / 48.0 + c * kappa / 2.0 - A1 / 2.0
    return {'c': c, 'kappa': kappa, 'A1': A1, 'L': L, 'alpha': alpha}

# ══════════════════════════════════════════════════════════════
# §6  CAMPAIGN RUNNER
# ══════════════════════════════════════════════════════════════

def run_campaign(label, data, theory, N_max):
    c = theory['c']
    kappa_pr = theory['kappa']
    L_pr = theory['L']
    alpha_pr = theory['alpha']

    print(f"\n{'=' * 70}")
    print(f"CAMPAIGN: {label}  (N = {N_max})")
    print(f"  c = {c:.10f}, kappa = {kappa_pr:.6f}")
    print(f"  L_pred = {L_pr:.10f}, alpha_pred = {alpha_pr:.10f}")
    print(f"{'=' * 70}")

    fit_start = max(100, N_max // 5)
    kf, bf, gf, mr = fit_meinardus(data, c, (fit_start, N_max))
    print(f"\n  Meinardus fit [n in {fit_start}..{N_max}]:")
    print(f"    kappa_fit = {kf:.8f}  (pred: {kappa_pr:.6f}, "
          f"diff: {abs(kf - kappa_pr):.2e})")
    print(f"    max residual = {mr:.2e}")

    cm = extract_Cm(data, c, (50, N_max))
    samples = [m for m in [50,100,200,300,500,700,1000,1500,2000]
               if m <= N_max and m in cm]
    print(f"\n  C_m → L = {L_pr:.10f}:")
    for m in samples:
        print(f"    m={m:5d}: {cm[m]:.10f}  (gap={cm[m]-L_pr:+.6e})")

    L_ext = extrapolate_L(cm, N_max // 3)
    if L_ext is not None:
        gp = abs(L_ext - L_pr) / abs(L_pr) * 100 if L_pr != 0 else float('inf')
        print(f"  L_ext = {L_ext:.10f}  (gap = {abs(L_ext-L_pr):.2e}, {gp:.4f}%)")

    dm = extract_Dm(data, c, L_pr, (100, N_max))
    d_samples = [m for m in [100,200,500,700,1000,1500,2000]
                 if m <= N_max and m in dm]
    if d_samples:
        print(f"\n  D_m → alpha = {alpha_pr:.10f}:")
        for m in d_samples:
            print(f"    m={m:5d}: {dm[m]:.10f}  (gap={dm[m]-alpha_pr:+.6e})")

    dm_best = dm[max(dm.keys())] if dm else None
    return {'kappa_fit': kf, 'L_ext': L_ext, 'dm_best': dm_best, 'max_res': mr}

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    t0 = time.time()
    run_checksum()

    # Theory verification for k=1
    print("=" * 70)
    print("THEORY: alpha_1 cross-check")
    print("=" * 70)
    th1 = theory_kcolored(1)
    alpha1_exact = float((mpi**2-24)*(4*mpi**2-9)/(144*mpi*msqrt(mpf(6))))
    print(f"  alpha_1 (general formula) = {th1['alpha']:.12f}")
    print(f"  alpha_1 (exact Round 7)   = {alpha1_exact:.12f}")
    print(f"  diff = {abs(th1['alpha'] - alpha1_exact):.2e}")
    print()

    # k=1: standard partitions
    print("Computing p(n) n=0..2000...", end=" ", flush=True)
    pk1 = [p(i) for i in range(2001)]
    print(f"done. p(2000) has {len(str(pk1[2000]))} digits.")
    res1 = run_campaign("k=1 (partitions)", pk1, th1, 2000)

    # k=2
    print("\nComputing p_2(n) n=0..800...", end=" ", flush=True)
    t2 = time.time()
    pk2 = compute_pk(800, 2)
    print(f"done in {time.time()-t2:.1f}s.")
    th2 = theory_kcolored(2)
    res2 = run_campaign("k=2", pk2, th2, 800)

    # k=3 (main campaign)
    print("\nComputing p_3(n) n=0..1000...", end=" ", flush=True)
    t3 = time.time()
    pk3 = compute_pk(1000, 3)
    print(f"done in {time.time()-t3:.1f}s. p_3(1000) has {len(str(pk3[1000]))} digits.")
    th3 = theory_kcolored(3)
    res3 = run_campaign("k=3", pk3, th3, 1000)

    # k=4 spot check
    print("\nComputing p_4(n) n=0..500...", end=" ", flush=True)
    t4 = time.time()
    pk4 = compute_pk(500, 4)
    print(f"done in {time.time()-t4:.1f}s.")
    th4 = theory_kcolored(4)
    res4 = run_campaign("k=4", pk4, th4, 500)

    # k=5 spot check
    print("\nComputing p_5(n) n=0..300...", end=" ", flush=True)
    pk5 = compute_pk(300, 5)
    print("done.")
    th5 = theory_kcolored(5)
    res5 = run_campaign("k=5", pk5, th5, 300)

    # Overpartitions
    print("\nComputing overpartitions n=0..500...", end=" ", flush=True)
    pbar = compute_overpartitions(500)
    print(f"done.")
    th_ov = theory_overpartitions()
    res_ov = run_campaign("overpartitions", pbar, th_ov, 500)

    # ══════════════════════════════════════════════════════════
    # MASTER SUMMARY
    # ══════════════════════════════════════════════════════════
    all_res = [
        ('k=1', th1, res1), ('k=2', th2, res2), ('k=3', th3, res3),
        ('k=4', th4, res4), ('k=5', th5, res5), ('over', th_ov, res_ov),
    ]

    print(f"\n\n{'#' * 90}")
    print(f"# TABLE 1: Meinardus Exponent & Second-Order Coefficient L")
    print(f"{'#' * 90}")
    print(f"{'Family':<10} {'c':>10} {'kappa_pr':>10} {'kappa_fit':>10} "
          f"{'L_pred':>14} {'L_ext':>14} {'L_gap%':>8}")
    print("-" * 80)
    for lab, th, res in all_res:
        Le = res['L_ext'] if res['L_ext'] else float('nan')
        gp = abs(Le - th['L'])/abs(th['L'])*100 if th['L'] != 0 and res['L_ext'] else float('nan')
        print(f"{lab:<10} {th['c']:>10.6f} {th['kappa']:>10.4f} {res['kappa_fit']:>10.6f} "
              f"{th['L']:>14.8f} {Le:>14.8f} {gp:>8.4f}")

    print(f"\n{'#' * 90}")
    print(f"# TABLE 2: Third-Order Coefficient alpha")
    print(f"{'#' * 90}")
    print(f"{'Family':<10} {'alpha_pred':>16} {'D_m(best)':>16} {'gap':>12}")
    print("-" * 58)
    for lab, th, res in all_res:
        db = res['dm_best'] if res['dm_best'] else float('nan')
        gap = abs(db - th['alpha']) if res['dm_best'] else float('nan')
        print(f"{lab:<10} {th['alpha']:>16.10f} {db:>16.10f} {gap:>12.2e}")

    print(f"\n{'#' * 90}")
    print(f"# THEOREM TEMPLATE")
    print(f"{'#' * 90}")
    print("""
    THEOREM (Ratio Universality for Meinardus-class sequences):

    Hypotheses:
      Let {f(n)} be a sequence with asymptotics
        f(n) ~ C · n^κ · exp(c·√n) · (1 + A₁/√n + A₂/n + ...)
      where c > 0, κ ∈ R, and A₁ = -c/48 + κ/c [Meinardus form].

    Conclusion:
      The consecutive ratio R_m = f(m)/f(m-1) satisfies, as m → ∞:

        R_m = 1 + c/(2√m) + L/m + α/m^{3/2} + O(m^{-2})

      where:
        L = c²/8 + κ
        α = c(c²+6)/48 + cκ/2 - A₁/2
          = c(c²+6)/48 + cκ/2 + c/96 - κ/(2c)
          = c³/48 + 13c/96 + κ(c² - 1)/(2c)

    Specialization 1 (k-colored partitions):
      f(n) = p_k(n), c_k = π√(2k/3), κ_k = -(k+3)/4
      L_k = kπ²/12 - (k+3)/4
      α_k = c_k³/48 + 13c_k/96 - (k+3)(c_k² - 1)/(8c_k)

    Specialization 2 (overpartitions):
      f(n) = p̄(n), c = π, κ = -1
      L = π²/8 - 1
      α = π³/48 + 13π/96 - (π² - 1)/(2π)
    """)

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")
    print("=== DONE ===")
