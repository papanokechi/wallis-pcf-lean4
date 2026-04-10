"""
Round 10C v2: PRECISION A₁ EXTRACTION + PSLQ IDENTIFICATION
Larger N, polynomial extrapolation on α_m, systematic PSLQ
"""
import time, math, sys
import numpy as np
sys.setrecursionlimit(10000)
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog
from mpmath import pslq as mpslq, zeta as mzeta
from functools import lru_cache

mp.dps = 120

# ─── Partition computation ───
@lru_cache(maxsize=None)
def p1(n):
    if n < 0: return 0
    if n == 0: return 1
    s = 0
    for j in range(1, n+1):
        g1, g2 = j*(3*j-1)//2, j*(3*j+1)//2
        sign = (-1)**(j+1)
        if g1 > n and g2 > n: break
        if g1 <= n: s += sign * p1(n-g1)
        if g2 <= n: s += sign * p1(n-g2)
    return s

def sigma1(j):
    s, d = 0, 1
    while d*d <= j:
        if j % d == 0:
            s += d
            if d != j//d: s += j//d
        d += 1
    return s

def compute_pk(N, k):
    sig = [0]*(N+1)
    for j in range(1, N+1): sig[j] = k * sigma1(j)
    pk = [0]*(N+1); pk[0] = 1
    for n in range(1, N+1):
        s = 0
        for j in range(1, n+1): s += sig[j]*pk[n-j]
        pk[n] = s // n
    return pk

# ─── A₁ extraction via polynomial extrapolation of α_m ───
def extract_A1_poly(pk, k, N):
    """Extract A₁ via high-order polynomial fit of α_m in 1/√m."""
    ck = mpi * msqrt(mpf(2*k)/3)
    kk = mpf(-(k+3)) / 4
    Lk = ck**2/8 + kk
    universal = ck*(ck**2 + 6)/48 + ck*kk/2  # α = universal - A₁/2

    print(f"  c = {float(ck):.16f}, κ = {float(kk)}, L = {float(Lk):.16f}")

    # Compute α_m for dense set of m values
    m_start = max(200, N//10)
    ms = list(range(m_start, N+1, max(1, (N-m_start)//2000)))
    print(f"  Computing α_m for {len(ms)} values in [{m_start}..{N}]...")

    alpha_vals = []
    for m in ms:
        R = mpf(pk[m]) / mpf(pk[m-1])
        am = mpf(m) * msqrt(mpf(m)) * (R - 1 - ck/(2*msqrt(mpf(m))) - Lk/mpf(m))
        alpha_vals.append(float(am))
    alpha_arr = np.array(alpha_vals)
    ms_arr = np.array(ms, dtype=float)

    # Polynomial fit: α_m = Σ_{j=0}^{P} a_j · m^{-j/2}
    # i.e., α_m = a₀ + a₁/√m + a₂/m + a₃/m^{3/2} + ... + a_P/m^{P/2}
    # where a₀ = α (the target)
    print(f"\n  Polynomial extrapolation of α_m in 1/√m:")
    best_alpha = None
    for P in [4, 5, 6, 7, 8]:
        X = np.column_stack([ms_arr**(-j/2) for j in range(P+1)])
        params, _, _, _ = np.linalg.lstsq(X, alpha_arr, rcond=None)
        alpha_est = params[0]
        res = float(np.max(np.abs(X@params - alpha_arr)))
        A1_est = 2*(float(universal) - alpha_est)
        print(f"    P={P}: α = {alpha_est:.15f}, A₁ = {A1_est:.14f} (res={res:.2e})")
        best_alpha = alpha_est  # highest P is generally best

    best_A1 = 2*(float(universal) - best_alpha)

    # Also do nested Richardson on the polynomial estimates
    # (the P=4..8 values themselves converge)

    # Also: fixed-parameter regression on log f(n)
    print(f"\n  Fixed-(c,κ) regression on log f(n):")
    for n0_frac, nterms in [(0.4, 6), (0.5, 6), (0.6, 6), (0.7, 5)]:
        n0 = int(N * n0_frac)
        ns = list(range(n0, N+1))
        hs = [float(mlog(mpf(pk[n])) - ck*msqrt(mpf(n)) - kk*mlog(mpf(n))) for n in ns]
        X = np.zeros((len(ns), nterms))
        for col in range(nterms):
            X[:, col] = [n**(-col/2) for n in ns]
        params, _, _, _ = np.linalg.lstsq(X, np.array(hs), rcond=None)
        A1_fitval = params[1]  # coefficient of n^{-1/2}
        res = float(np.max(np.abs(X@params - np.array(hs))))
        print(f"    [{n0}..{N}, {nterms}t]: A₁ = {A1_fitval:.14f} (res={res:.2e})")

    # Return the mpf value for PSLQ
    A1_mp = 2*(universal - mpf(best_alpha))
    return A1_mp, ck, kk, best_A1

# ─── PSLQ search ───
def pslq_search(A1_mp, k, ck):
    print(f"\n  PSLQ for A₁^({k}) = {float(A1_mp):.15f}")
    kk = mpf(-(k+3))/4
    sqrt3 = msqrt(3)
    log2pi = mlog(2*mpi)
    zeta3 = mzeta(3)
    zetam1 = mzeta(-1)  # = -1/12
    gamma_em = mpf('0.5772156649015328606065120900824024310421')  # Euler-Mascheroni

    def try_pslq(name, basis, mc=500):
        vec = [A1_mp] + list(basis)
        # Check no zeros
        if any(abs(float(v)) < 1e-100 for v in vec):
            print(f"    {name}: skipped (zero in basis)")
            return None
        r = mpslq(vec, maxcoeff=mc, maxsteps=10000)
        if r is not None:
            check = sum(r[i]*vec[i] for i in range(len(vec)))
            if abs(float(check)) < 1e-15:
                print(f"    {name}: FOUND {r}  (res={float(check):.2e})")
                d = r[0]
                if d != 0:
                    terms = [f"({-r[i+1]}/{d})*{n}" for i, n in enumerate(
                        ['v'+str(j) for j in range(len(basis))]) if r[i+1] != 0]
                    print(f"      A₁ = ", end="")
                    for i, (name_b, coeff) in enumerate(zip(
                            [f"b{j}" for j in range(len(basis))], r[1:])):
                        if coeff != 0:
                            print(f" + ({-coeff}/{d})*basis[{i}]", end="")
                    print()
                return r
            else:
                print(f"    {name}: spurious (res={float(check):.2e})")
        else:
            print(f"    {name}: no relation")
        return None

    # Core bases
    try_pslq("{c, 1/c, 1}", [ck, 1/ck, mpf(1)])
    try_pslq("{c, 1/c, c², 1}", [ck, 1/ck, ck**2, mpf(1)])
    try_pslq("{c, 1/c, c², 1/c², 1}", [ck, 1/ck, ck**2, 1/ck**2, mpf(1)], mc=1000)

    # k-weighted
    if k > 1:
        try_pslq("{kc, k/c, 1}", [mpf(k)*ck, mpf(k)/ck, mpf(1)])
        try_pslq("{kc, 1/c, 1}", [mpf(k)*ck, 1/ck, mpf(1)])
        try_pslq("{kc, 1/c, c², 1}", [mpf(k)*ck, 1/ck, ck**2, mpf(1)])

    # With transcendentals
    try_pslq("{c, 1/c, log(2π), 1}", [ck, 1/ck, log2pi, mpf(1)])
    try_pslq("{c, 1/c, ζ(3), 1}", [ck, 1/ck, zeta3, mpf(1)])
    try_pslq("{c, 1/c, γ, 1}", [ck, 1/ck, gamma_em, mpf(1)])
    try_pslq("{c, 1/c, log(2π), ζ(3), 1}", [ck, 1/ck, log2pi, zeta3, mpf(1)])

    # Raw π and √3
    try_pslq("{π, 1/π, √3, 1}", [mpi, 1/mpi, sqrt3, mpf(1)])
    try_pslq("{π, 1/π, √3, √3/π, 1}", [mpi, 1/mpi, sqrt3, sqrt3/mpi, mpf(1)], mc=1000)
    try_pslq("{π/√3, √3/π, π²/3, 1}", [mpi/sqrt3, sqrt3/mpi, mpi**2/3, mpf(1)])

    # Residual after analytical base: Δ = A₁ - (-kc/48 + κ/c)
    base = -mpf(k)*ck/48 + kk/ck
    Delta = A1_mp - base
    print(f"\n    Δ = A₁ - (-kc/48 + κ/c) = {float(Delta):.15f}")
    if abs(float(Delta)) > 1e-50:
        try_pslq("Δ ~ {c, 1/c, 1}", [ck, 1/ck, mpf(1)])
        try_pslq("Δ ~ {c, 1/c, c², 1}", [ck, 1/ck, ck**2, mpf(1)])
        try_pslq("Δ ~ {c², 1/c², 1}", [ck**2, 1/ck**2, mpf(1)])
        if k > 1:
            try_pslq("Δ ~ {kc, k/c, 1}", [mpf(k)*ck, mpf(k)/ck, mpf(1)])
            km1 = mpf(k-1)
            try_pslq(f"Δ ~ {{(k-1)c, (k-1)/c, 1}}", [km1*ck, km1/ck, mpf(1)])

    # Full A₁ with mixed: {k*c, 1/c, k², k, 1}
    if k > 1:
        try_pslq("{kc, 1/c, k², k, 1}", [mpf(k)*ck, 1/ck, mpf(k**2), mpf(k), mpf(1)], mc=1000)
        try_pslq("{c, 1/c, k*c², k, 1}", [ck, 1/ck, mpf(k)*ck**2, mpf(k), mpf(1)], mc=1000)


if __name__ == "__main__":
    t0 = time.time()

    # ═══ k=1: VALIDATION (N=15000) ═══
    print("="*70)
    print("k=1: Standard Partitions — VALIDATION (N=15000)")
    print("="*70)
    tk = time.time()
    pk1 = [p1(n) for n in range(15001)]
    print(f"Computed in {time.time()-tk:.1f}s. p(15000) has {len(str(pk1[15000]))} digits.")

    A1_1_mp, ck1, kk1, A1_1 = extract_A1_poly(pk1, 1, 15000)
    A1_exact = -(mpi**2 + 72)/(24*mpi*msqrt(6))
    gap = abs(float(A1_1_mp - A1_exact))
    print(f"\n  Exact: A₁ = -(π²+72)/(24π√6) = {float(A1_exact):.15f}")
    print(f"  Extracted:                        {float(A1_1_mp):.15f}")
    print(f"  Gap: {gap:.2e}")
    pslq_search(A1_1_mp, 1, ck1)

    # ═══ k=2 (N=8000) ═══
    print(f"\n\n{'='*70}")
    print("k=2: 2-Colored Partitions (N=8000)")
    print("="*70)
    tk = time.time()
    pk2 = compute_pk(8000, 2)
    print(f"Computed in {time.time()-tk:.1f}s. p_2(8000) has {len(str(pk2[8000]))} digits.")
    A1_2_mp, ck2, kk2, A1_2 = extract_A1_poly(pk2, 2, 8000)
    pslq_search(A1_2_mp, 2, ck2)

    # ═══ k=3 (N=8000) ═══
    print(f"\n\n{'='*70}")
    print("k=3: 3-Colored Partitions (N=8000)")
    print("="*70)
    tk = time.time()
    pk3 = compute_pk(8000, 3)
    print(f"Computed in {time.time()-tk:.1f}s. p_3(8000) has {len(str(pk3[8000]))} digits.")
    A1_3_mp, ck3, kk3, A1_3 = extract_A1_poly(pk3, 3, 8000)
    pslq_search(A1_3_mp, 3, ck3)

    # ═══ Cross-family ═══
    print(f"\n\n{'='*70}")
    print("CROSS-FAMILY SUMMARY")
    print("="*70)
    for k, A1_mp, ck in [(1, A1_1_mp, ck1), (2, A1_2_mp, ck2), (3, A1_3_mp, ck3)]:
        kk = mpf(-(k+3))/4
        base = -mpf(k)*ck/48 + kk/ck
        delta = float(A1_mp - base)
        print(f"  k={k}: A₁ = {float(A1_mp):.14f}, base = {float(base):.14f}, Δ = {delta:+.14f}")

    print(f"\nTotal: {time.time()-t0:.1f}s")
    print("=== DONE ===")
