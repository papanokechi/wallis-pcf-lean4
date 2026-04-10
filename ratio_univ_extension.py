"""
Ratio Universality — Family Extension (Path 3: Beyond-Breakthrough)
===================================================================

Extends the L-formula verification to 3 NEW families beyond the original 6:

  7. k=6 colored partitions  (c = pi*sqrt(4), kappa = -9/4)
  8. Strict partitions Q(n)  (c = pi/sqrt(3), kappa = -1/2)
  9. Plane partitions PL(n)  (c = zeta(3)^{1/3} * ..., different growth class)

The L-formula hypothesis:
  R_m = f(m)/f(m-1) = 1 + c/(2*sqrt(m)) + L/m + O(m^{-3/2})
  where L = c^2/8 + kappa

For Meinardus-class: kappa = (D(0) - (d+1)/2) / 2, d = dim (=1 for 1D products).

Additionally tests the Selection Rule (Theorem 2*):
  A1 = -k*c_k/48 - (k+1)(k+3)/(8*c_k)  for k-colored
  Generalized: A1 = -c/48 + kappa/c       (universal form)

Usage:
    python ratio_univ_extension.py
"""

import math
import sys
from functools import lru_cache
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog, nstr

mp.dps = 60
sys.setrecursionlimit(20000)


# ══════════════════════════════════════════════════════════════
# §1  PARTITION FUNCTIONS
# ══════════════════════════════════════════════════════════════

# --- k-colored partitions: prod (1-q^m)^{-k} ---
def compute_pk(N, k):
    """p_k(n) via n*p_k(n) = sum_{j=1}^{n} k*sigma(j)*p_k(n-j)."""
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
    return pk


# --- Strict (distinct) partitions: prod (1+q^m) = prod (1-q^{2m})/(1-q^m) ---
def compute_strict(N):
    """q(n) = number of partitions into distinct parts.
    Generating function: prod_{m>=1} (1+q^m).
    Recurrence: q(n) = q(n-1) + q(n-2) - q(n-5) - q(n-7) + q(n-12) + ...
    using generalized pentagonal numbers with alternating signs.
    More stable: use the relation to p(n) via Euler's identity:
    q(n) = sum_{k>=0} (-1)^k * p(n - k(3k-1)/2) + similar terms.
    Actually easiest: direct product expansion."""
    # Direct convolution: prod (1+q^m) = sum q(n) q^n
    q = [0] * (N + 1)
    q[0] = 1
    for m in range(1, N + 1):
        # Multiply by (1 + q^m): process in reverse to avoid double-counting
        for n in range(N, m - 1, -1):
            q[n] += q[n - m]
    # Verify against known values (OEIS A000009)
    known = [1, 1, 1, 2, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 22, 27, 32, 38, 46, 54, 64]
    for i, v in enumerate(known):
        if i <= N:
            assert q[i] == v, f"q({i})={q[i]} != {v}"
    return q


# --- Plane partitions: prod_{m>=1} (1-q^m)^{-m} ---
def compute_plane_partitions(N):
    """PL(n) = number of plane partitions.
    Generating function: prod_{m>=1} (1-q^m)^{-m}.
    Recurrence from log derivative:
    n*PL(n) = sum_{j=1}^{n} sigma_2(j) * PL(n-j)
    where sigma_2(j) = sum_{d|j} d^2.  (But we need sum d*m where d*m divides...)
    Actually: if f = prod (1-q^m)^{-a_m}, then n*f(n) = sum_{j=1}^n c(j)*f(n-j)
    where c(j) = sum_{d|j} d * a_d.
    For plane partitions, a_m = m, so c(j) = sum_{d|j} d * (j/d) = sum_{d|j} j = j * tau(j)
    where tau(j) = number of divisors.
    Wait: c(j) = sum_{d|j} d * a_d. Since a_d = d: c(j) = sum_{d|j} d^2 = sigma_2(j)."""
    PL = [0] * (N + 1)
    PL[0] = 1
    sig2 = [0] * (N + 1)
    for j in range(1, N + 1):
        s = 0
        d = 1
        while d * d <= j:
            if j % d == 0:
                s += d * d
                if d != j // d:
                    s += (j // d) ** 2
            d += 1
        sig2[j] = s
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += sig2[j] * PL[n - j]
        PL[n] = s // n
    # Verify (OEIS A000219)
    known = [1, 1, 3, 6, 13, 24, 48, 86, 160, 282, 500, 859, 1479, 2485, 4167, 6879,
             11297, 18334, 29601, 47330, 75278]
    for i, v in enumerate(known):
        if i <= N:
            assert PL[i] == v, f"PL({i})={PL[i]} != {v}"
    return PL


# --- Overpartitions (from Round 10) ---
def compute_overpartitions(N):
    """pbar(n): prod (1+q^m)/(1-q^m) = prod (1-q^m)^{-1} * prod (1+q^m)."""
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
    return pbar


# ══════════════════════════════════════════════════════════════
# §2  THEORY: Meinardus parameters for each family
# ══════════════════════════════════════════════════════════════

def theory_kcolored(k):
    """k-colored partitions: prod (1-q^m)^{-k}.
    D(s) = k*zeta(s), D(0) = -k/2.
    c_k = pi*sqrt(2k/3), kappa = (D(0) - (d+1)/2)/2 = (-k/2 - 1)/2 = -(k+2)/4.
    Wait: Meinardus formula gives f(n) ~ C * n^kappa * exp(c*sqrt(n)).
    kappa = -(k+3)/4 for k-colored (standard result).
    """
    c = float(mpi * msqrt(mpf(2 * k) / 3))
    kappa = -(k + 3) / 4.0
    A1 = -c / 48.0 + kappa / c
    L = c**2 / 8.0 + kappa
    alpha = c * (c**2 + 6) / 48.0 + c * kappa / 2.0 - A1 / 2.0
    return {'c': c, 'kappa': kappa, 'A1': A1, 'L': L, 'alpha': alpha, 'name': f'k={k} colored'}


def theory_overpartitions():
    """Overpartitions: D(s) = zeta(s)*(2-2^{-s}), D(0) = -1/2.
    c = pi, kappa = -1."""
    c = float(mpi)
    kappa = -1.0
    A1 = -c / 48.0 + kappa / c
    L = c**2 / 8.0 + kappa
    alpha = c * (c**2 + 6) / 48.0 + c * kappa / 2.0 - A1 / 2.0
    return {'c': c, 'kappa': kappa, 'A1': A1, 'L': L, 'alpha': alpha, 'name': 'overpartitions'}


def theory_strict():
    """Strict partitions (distinct parts): prod (1+q^m).
    = prod (1-q^{2m}) / prod (1-q^m) = eta(2tau)/eta(tau) type.
    Asymptotic: q(n) ~ (1/(4*(3n^3)^(1/4))) * exp(pi*sqrt(n/3)).
    So c = pi/sqrt(3), kappa = -3/4.
    More precisely: D(s) = (1-2^{-s})*zeta(s), residue at s=1 is 1/2.
    Meinardus: c = pi*sqrt(2*r/d) where r = residue, d = dim of product.
    c = pi*sqrt(2*(1/2)/1) = pi/sqrt(1)... No.
    Standard result: c = pi*sqrt(1/3) = pi/sqrt(3).
    kappa from D(0): D(0) = (1-2^0)*zeta(0) = 0*(-1/2) = 0? No:
    (1 - 2^{-s})*zeta(s) at s=0: L'Hopital or direct: D(0) = -1/2 * (1-1) = 0??? 
    Actually D(0) = (1-1)*(-1/2) = 0.
    So kappa = (D(0) - 1)/2 = (0-1)/2 = -1/2... but known result says -3/4.
    Let me use the known asymptotic directly:
    q(n) ~ (1/4) * (3n^3)^{-1/4} * exp(pi*sqrt(n/3))
    = C * n^{-3/4} * exp(c * sqrt(n)) with c = pi/sqrt(3), kappa = -3/4.
    """
    c = float(mpi / msqrt(3))
    kappa = -3 / 4.0
    A1 = -c / 48.0 + kappa / c
    L = c**2 / 8.0 + kappa
    alpha = c * (c**2 + 6) / 48.0 + c * kappa / 2.0 - A1 / 2.0
    return {'c': c, 'kappa': kappa, 'A1': A1, 'L': L, 'alpha': alpha, 'name': 'strict partitions'}


def theory_plane():
    """Plane partitions: prod (1-q^m)^{-m}.
    D(s) = zeta(s-1) (since a_m = m).
    Asymptotic: PL(n) ~ C * n^{-25/36} * exp(c * n^{2/3})
    where c = (3/2) * zeta(3)^{1/3}.
    NOTE: This is NOT Meinardus class in the standard sense — the growth is
    exp(n^{2/3}), not exp(sqrt(n)). The ratio R_m = PL(m)/PL(m-1) has a
    DIFFERENT expansion structure: R_m ~ 1 + (2c/3) * m^{-1/3} + ...
    So the L-formula L = c^2/8 + kappa does NOT apply directly.
    We test this as a control: if "L" deviates, it confirms the growth-class
    sensitivity of the universality theorem.
    """
    import mpmath
    zeta3 = float(mpmath.zeta(3))
    c_23 = 1.5 * zeta3 ** (1 / 3)  # coefficient of n^{2/3}
    kappa = -25 / 36.0
    return {
        'c': c_23, 'kappa': kappa,
        'A1': None,  # not applicable (different growth class)
        'L': None,   # not applicable
        'alpha': None,
        'name': 'plane partitions (control — non-Meinardus)',
        'growth_exponent': 2/3,   # exp(c * n^{2/3}) instead of exp(c * sqrt(n))
    }


# ══════════════════════════════════════════════════════════════
# §3  EXTRACTION ENGINE
# ══════════════════════════════════════════════════════════════

import numpy as np


def extract_Cm(data, c, m_range):
    """C_m = m * (R_m - 1 - c/(2*sqrt(m)))."""
    m0, m1 = m_range
    results = {}
    for m in range(max(m0, 2), m1 + 1):
        if data[m] == 0 or data[m - 1] == 0:
            continue
        R = mpf(data[m]) / mpf(data[m - 1])
        C = mpf(m) * (R - 1 - mpf(c) / (2 * msqrt(mpf(m))))
        results[m] = float(C)
    return results


def extrapolate_L(cm_dict, m_min):
    """Extrapolate C_m = L + A/sqrt(m) via least squares."""
    ms = np.array(sorted(m for m in cm_dict if m >= m_min), dtype=float)
    cs = np.array([cm_dict[int(m)] for m in ms])
    if len(ms) < 10:
        return None, None
    X = np.column_stack([np.ones_like(ms), 1.0 / np.sqrt(ms)])
    params, _, _, _ = np.linalg.lstsq(X, cs, rcond=None)
    return params[0], params[1]  # L_fit, A1_approx


def extract_Dm(data, c, L, m_range):
    """D_m = (C_m - L)*sqrt(m) → alpha as m→∞."""
    cm = extract_Cm(data, c, m_range)
    return {m: (cv - L) * math.sqrt(m) for m, cv in cm.items()}


# ══════════════════════════════════════════════════════════════
# §4  CAMPAIGN RUNNER
# ══════════════════════════════════════════════════════════════

def run_family(label, data, theory, N_max):
    """Verify the L-formula and A1 formula for one family."""
    c = theory['c']
    kappa = theory['kappa']
    L_pred = theory.get('L')
    A1_pred = theory.get('A1')
    alpha_pred = theory.get('alpha')
    growth_exp = theory.get('growth_exponent', 0.5)

    print(f"\n{'═' * 72}")
    print(f"  FAMILY: {label}  (N_max = {N_max})")
    print(f"  c = {c:.10f},  kappa = {kappa:.6f}")
    if L_pred is not None:
        print(f"  L_pred = {L_pred:.10f}")
    if A1_pred is not None:
        print(f"  A1_pred = {A1_pred:.10f}")
    print(f"{'═' * 72}")

    # For plane partitions (growth ~ n^{2/3}), demonstrate different expansion
    if growth_exp != 0.5:
        print(f"\n  NOTE: growth_exponent = {growth_exp} (not 1/2)")
        print(f"  The standard L-formula does NOT apply. Testing as control.")
        # Just show ratio behavior
        print(f"\n  {'m':>6s}  {'R_m':>16s}  {'R_m - 1':>14s}  {'(R_m-1)*m^(1/3)':>18s}")
        print(f"  {'-'*60}")
        for m in [100, 200, 500, 1000, 2000, min(N_max, 5000)]:
            if m > N_max or data[m] == 0 or data[m - 1] == 0:
                continue
            R = mpf(data[m]) / mpf(data[m - 1])
            diff = float(R - 1)
            scaled = diff * m ** (1 / 3)
            print(f"  {m:6d}  {nstr(R, 14):>16s}  {diff:14.10f}  {scaled:18.10f}")
        print(f"\n  (R_m - 1) * m^(1/3) → 2c/3 = {2*c/3:.10f} for plane partitions")
        return {'family': label, 'L_pred': None, 'L_fit': None, 'gap_pct': None,
                'is_meinardus': False, 'note': 'non-Meinardus growth class'}

    # Standard Meinardus: extract C_m and fit L
    m_range = (max(100, N_max // 10), N_max)
    cm = extract_Cm(data, c, m_range)
    L_fit, A1_approx = extrapolate_L(cm, max(200, N_max // 5))

    if L_pred is not None and L_fit is not None:
        gap = abs(L_fit - L_pred) / abs(L_pred) * 100
        status = "PASS" if gap < 0.2 else "MARGINAL" if gap < 1.0 else "FAIL"
        print(f"\n  L verification:")
        print(f"    L_predicted = {L_pred:.10f}")
        print(f"    L_fitted    = {L_fit:.10f}")
        print(f"    Gap         = {gap:.4f}% — {status}")
    else:
        gap = None

    if A1_pred is not None and A1_approx is not None:
        a1_gap = abs(A1_approx - A1_pred) / abs(A1_pred) * 100 if A1_pred != 0 else None
        print(f"\n  A1 (Selection Rule) verification:")
        print(f"    A1_predicted = {A1_pred:.10f}")
        print(f"    A1_approx    = {A1_approx:.10f}")
        if a1_gap is not None:
            print(f"    Gap          = {a1_gap:.3f}%")

    # Detailed C_m convergence table
    print(f"\n  {'m':>6s}  {'C_m':>14s}  {'C_m - L_pred':>14s}")
    print(f"  {'-'*38}")
    for m in sorted(cm.keys()):
        if m in [100, 200, 500, 1000, 2000, 3000, 4000, min(N_max, 5000)]:
            delta = cm[m] - L_pred if L_pred is not None else 0
            print(f"  {m:6d}  {cm[m]:14.8f}  {delta:14.8f}")

    # Alpha extraction (D_m approach)
    if L_pred is not None and alpha_pred is not None:
        dm = extract_Dm(data, c, L_pred, m_range)
        if dm:
            ms_d = np.array(sorted(m for m in dm if m >= max(500, N_max // 4)), dtype=float)
            ds = np.array([dm[int(m)] for m in ms_d])
            if len(ms_d) > 10:
                X = np.column_stack([np.ones_like(ms_d), 1.0 / np.sqrt(ms_d)])
                params, _, _, _ = np.linalg.lstsq(X, ds, rcond=None)
                alpha_fit = params[0]
                alpha_gap = abs(alpha_fit - alpha_pred) / abs(alpha_pred) * 100 if alpha_pred != 0 else None
                print(f"\n  Alpha verification:")
                print(f"    alpha_predicted = {alpha_pred:.10f}")
                print(f"    alpha_fitted    = {alpha_fit:.10f}")
                if alpha_gap is not None:
                    print(f"    Gap             = {alpha_gap:.3f}%")

    return {
        'family': label,
        'L_pred': L_pred,
        'L_fit': L_fit,
        'gap_pct': gap,
        'is_meinardus': True,
        'is_new_verification': label not in [
            'k=1 colored', 'k=2 colored', 'k=3 colored',
            'k=4 colored', 'k=5 colored', 'overpartitions',
        ],
    }


# ══════════════════════════════════════════════════════════════
# §5  MAIN — 9-FAMILY CAMPAIGN
# ══════════════════════════════════════════════════════════════

def main():
    N_MAX = 6000
    print("=" * 72)
    print("  RATIO UNIVERSALITY — FAMILY EXTENSION CAMPAIGN")
    print(f"  Testing L = c²/8 + κ across 9 families (N_max = {N_MAX})")
    print(f"  NEW families: k=6, k=7, strict partitions, plane partitions (control)")
    print("=" * 72)

    results = []

    # --- Original families (k=1..5 + overpartitions) ---
    @lru_cache(maxsize=None)
    def p(n):
        if n < 0: return 0
        if n == 0: return 1
        s = 0
        for j in range(1, n + 1):
            g1 = j * (3 * j - 1) // 2
            g2 = j * (3 * j + 1) // 2
            sign = (-1) ** (j + 1)
            if g1 > n and g2 > n: break
            if g1 <= n: s += sign * p(n - g1)
            if g2 <= n: s += sign * p(n - g2)
        return s

    print("\nComputing partition functions...")
    import time
    t0 = time.time()

    # k=1 (standard partitions)
    data_k1 = [p(n) for n in range(N_MAX + 1)]
    print(f"  k=1 done ({time.time()-t0:.1f}s)")

    # k=2..7
    for k in range(2, 8):
        t1 = time.time()
        data_k = compute_pk(N_MAX, k)
        print(f"  k={k} done ({time.time()-t1:.1f}s)")
        results.append(run_family(f"k={k} colored", data_k, theory_kcolored(k), N_MAX))

    # k=1 separately (uses pentagonal recurrence)
    results.insert(0, run_family("k=1 colored", data_k1, theory_kcolored(1), N_MAX))

    # Overpartitions
    t1 = time.time()
    data_over = compute_overpartitions(N_MAX)
    print(f"  overpartitions done ({time.time()-t1:.1f}s)")
    results.append(run_family("overpartitions", data_over, theory_overpartitions(), N_MAX))

    # Strict partitions (NEW)
    t1 = time.time()
    data_strict = compute_strict(N_MAX)
    print(f"  strict partitions done ({time.time()-t1:.1f}s)")
    results.append(run_family("strict partitions", data_strict, theory_strict(), N_MAX))

    # Plane partitions (CONTROL — non-Meinardus)
    N_PLANE = min(N_MAX, 5000)  # plane partitions grow fast
    t1 = time.time()
    data_plane = compute_plane_partitions(N_PLANE)
    print(f"  plane partitions done ({time.time()-t1:.1f}s)")
    results.append(run_family("plane partitions (control)", data_plane,
                              theory_plane(), N_PLANE))

    total_time = time.time() - t0

    # ══════════════════════════════════════════════════════════
    # §6  SUMMARY TABLE
    # ══════════════════════════════════════════════════════════
    print(f"\n\n{'═' * 72}")
    print(f"  SUMMARY: L-FORMULA UNIVERSALITY ACROSS {len(results)} FAMILIES")
    print(f"{'═' * 72}")
    print(f"\n  {'Family':<30s}  {'L_pred':>12s}  {'L_fit':>12s}  {'Gap%':>8s}  {'New?':>5s}  {'Status':>8s}")
    print(f"  {'-'*80}")

    pass_count = 0
    new_pass = 0
    for r in results:
        if not r.get('is_meinardus', True):
            print(f"  {r['family']:<30s}  {'N/A':>12s}  {'N/A':>12s}  {'N/A':>8s}  {'—':>5s}  {'CONTROL':>8s}")
            continue
        gap = r.get('gap_pct')
        L_pred = r.get('L_pred')
        L_fit = r.get('L_fit')
        is_new = r.get('is_new_verification', False)
        if gap is not None and gap < 0.2:
            status = "PASS"
            pass_count += 1
            if is_new:
                new_pass += 1
        elif gap is not None and gap < 1.0:
            status = "MARGINAL"
        else:
            status = "FAIL" if gap is not None else "N/A"
        print(f"  {r['family']:<30s}  "
              f"{L_pred:12.6f}" if L_pred else "  {'N/A':>12s}",
              end="")
        print(f"  {L_fit:12.6f}" if L_fit else f"  {'N/A':>12s}", end="")
        print(f"  {gap:8.4f}%" if gap else f"  {'N/A':>8s}", end="")
        print(f"  {'NEW' if is_new else '':>5s}  {status:>8s}")

    meinardus_count = sum(1 for r in results if r.get('is_meinardus', True))
    print(f"\n  Score: {pass_count}/{meinardus_count} Meinardus families PASS (<0.2% gap)")
    print(f"  New families verified: {new_pass}")
    print(f"  Total compute time: {total_time:.1f}s")

    # Selection Rule check — the universal form A1 = -c/48 + kappa/c
    print(f"\n{'═' * 72}")
    print(f"  SELECTION RULE VERIFICATION")
    print(f"  Universal form:  A1 = -c/48 + kappa/c")
    print(f"  k-colored form:  A1 = -k*c_k/48 - (k+1)(k+3)/(8*c_k)")
    print(f"{'═' * 72}")
    print(f"\n  {'Family':<25s}  {'A1_formula':>12s}  {'A1_kform':>12s}  {'Match':>6s}")
    print(f"  {'-'*60}")
    for k in range(1, 8):
        th = theory_kcolored(k)
        # Theorem 2* form: A1 = -k*c_k/48 - (k+1)(k+3)/(8*c_k)
        a1_kform = -k * th['c'] / 48 - (k + 1) * (k + 3) / (8 * th['c'])
        # Universal form: A1 = -c/48 + kappa/c
        a1_univ = -th['c'] / 48 + th['kappa'] / th['c']
        # Note: these are NOT the same formula. The k-colored form includes
        # the k-dependent selection rule while the universal form uses kappa.
        # The k-form is the CORRECT one (Theorem 2*).
        print(f"  k={k} colored{' '*(19-len(str(k)))}  "
              f"{a1_kform:12.8f}  {a1_univ:12.8f}  "
              f"{'=' if abs(a1_kform - a1_univ) < 1e-10 else '≠':>6s}")

    # For non-k-colored families, the universal form A1 = -c/48 + kappa/c applies
    for name, th_func in [("overpartitions", theory_overpartitions),
                          ("strict partitions", theory_strict)]:
        th = th_func()
        a1 = -th['c'] / 48 + th['kappa'] / th['c']
        print(f"  {name:<25s}  {a1:12.8f}  {'—':>12s}  {'univ':>6s}")

    print(f"\n  Note: For k=1, both forms agree (k=1 is the special case).")
    print(f"  For k>1, the k-colored Selection Rule (Theorem 2*) is the")
    print(f"  correct formula. The universal form A1=-c/48+kappa/c is a")
    print(f"  simplification that holds only when the Dirichlet series D(s)")
    print(f"  has a simple structure.")


if __name__ == "__main__":
    main()
