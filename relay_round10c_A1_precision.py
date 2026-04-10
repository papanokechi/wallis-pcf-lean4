"""
Round 10C: PRECISION A₁ EXTRACTION + PSLQ CLOSED-FORM IDENTIFICATION
Goal: Extract A₁^(k) to 12+ digits for k=1,2,3 and identify via PSLQ
"""
import time, math, sys
import numpy as np
sys.setrecursionlimit(10000)

from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog, power as mpow
from mpmath import pslq as mpslq, zeta as mzeta
from functools import lru_cache

mp.dps = 120

# ═══════════════════════════════════════════════════════════
# PARTITION COMPUTATIONS (exact integers)
# ═══════════════════════════════════════════════════════════

@lru_cache(maxsize=None)
def p1(n):
    if n < 0: return 0
    if n == 0: return 1
    s = 0
    for j in range(1, n+1):
        g1, g2 = j*(3*j-1)//2, j*(3*j+1)//2
        sign = (-1)**(j+1)
        if g1 > n and g2 > n: break
        if g1 <= n: s += sign * p1(n - g1)
        if g2 <= n: s += sign * p1(n - g2)
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

# ═══════════════════════════════════════════════════════════
# A₁ EXTRACTION ENGINE
# ═══════════════════════════════════════════════════════════

def extract_A1(pk, k, N):
    """Extract A₁ to maximum precision via dual methods."""
    ck = mpi * msqrt(mpf(2*k) / 3)
    kk = mpf(-(k+3)) / 4
    Lk = ck**2 / 8 + kk

    print(f"\n  c_{k} = {float(ck):.16f}")
    print(f"  κ_{k} = {float(kk)}")
    print(f"  L_{k} = {float(Lk):.16f}")

    # ─── Method 1: Fixed-(c,κ) regression ───
    # h(n) = log f(n) - c√n - κ log n
    # h(n) = β₀ + A₁/√n + A₂/n + A₃/n^{3/2} + A₄/n²
    print(f"\n  Method 1: Fixed-parameter regression (5 terms)")
    fit_A1_vals = []
    for n0_frac in [0.3, 0.4, 0.5, 0.6]:
        n0 = int(N * n0_frac)
        ns = list(range(n0, N+1))
        hs = [float(mlog(mpf(pk[n])) - ck*msqrt(mpf(n)) - kk*mlog(mpf(n))) for n in ns]
        X = np.column_stack([
            np.ones(len(ns)),
            [1/math.sqrt(n) for n in ns],
            [1.0/n for n in ns],
            [1/(n*math.sqrt(n)) for n in ns],
            [1.0/(n*n) for n in ns]
        ])
        params, _, _, _ = np.linalg.lstsq(X, np.array(hs), rcond=None)
        A1 = params[1]
        res = float(np.max(np.abs(X @ params - np.array(hs))))
        fit_A1_vals.append(A1)
        print(f"    [{n0:4d}..{N}]: A₁ = {A1:.14f}  (res={res:.2e})")

    # ─── Method 2: Quadruple Richardson on α_m ───
    # α_m = m^{3/2}·(R_m - 1 - c/(2√m) - L/m)
    # α_m = α + B₁/√m + B₂/m + B₃/m^{3/2} + B₄/m² + ...
    def alpha_m(m):
        R = mpf(pk[m]) / mpf(pk[m-1])
        return mpf(m) * msqrt(mpf(m)) * (R - 1 - ck/(2*msqrt(mpf(m))) - Lk/mpf(m))

    r = mpf(2)
    sqr = msqrt(r)

    print(f"\n  Method 2: Quadruple Richardson (r=2)")
    rich_results = []
    for m0 in range(100, N//8 + 1, 25):
        m1, m2, m3, m4 = m0, 2*m0, 4*m0, 8*m0
        if m4 > N: break
        a1, a2, a3, a4 = alpha_m(m1), alpha_m(m2), alpha_m(m3), alpha_m(m4)

        # Level 1: eliminate B₁/√m  (weight √r)
        b1 = (sqr*a2 - a1)/(sqr - 1)
        b2 = (sqr*a3 - a2)/(sqr - 1)
        b3 = (sqr*a4 - a3)/(sqr - 1)

        # Level 2: eliminate B₂/m  (weight r)
        c1 = (r*b2 - b1)/(r - 1)
        c2 = (r*b3 - b2)/(r - 1)

        # Level 3: eliminate B₃/m^{3/2}  (weight r^{3/2})
        r32 = r * sqr
        d1 = (r32*c2 - c1)/(r32 - 1)

        rich_results.append((m0, d1))

    for m0, alpha in rich_results[-8:]:
        print(f"    m₀={m0:5d}: α_ext = {float(alpha):.15f}")

    # Best: take the highest-m₀ result (in mpf)
    best_m0, best_alpha_mp = rich_results[-1]
    best_alpha = float(best_alpha_mp)

    # Stability check: spread of last 5
    if len(rich_results) >= 5:
        recent = [float(a) for _, a in rich_results[-5:]]
        spread = max(recent) - min(recent)
        print(f"  Best α = {best_alpha:.15f} (spread {spread:.2e})")

    # A₁ = 2·[c(c²+6)/48 + cκ/2 - α]
    universal = ck*(ck**2 + 6)/48 + ck*kk/2
    A1_rich_mp = 2*(universal - best_alpha_mp)
    A1_rich = float(A1_rich_mp)
    print(f"  A₁ from Richardson: {A1_rich:.15f}")

    # ─── Method 3: Direct regression on α_m ───
    # α_m = α + β/√m + γ/m  →  3-parameter regression
    print(f"\n  Method 3: Direct regression on α_m sequence")
    m_start = max(500, N//5)
    ms = list(range(m_start, N+1))
    alphas = [float(alpha_m(m)) for m in ms]
    X3 = np.column_stack([
        np.ones(len(ms)),
        [1/math.sqrt(m) for m in ms],
        [1.0/m for m in ms],
        [1/(m*math.sqrt(m)) for m in ms]
    ])
    p3, _, _, _ = np.linalg.lstsq(X3, np.array(alphas), rcond=None)
    A1_reg3 = 2*(float(universal) - p3[0])
    print(f"  α (regression) = {p3[0]:.15f}")
    print(f"  A₁ from regression: {A1_reg3:.15f}")

    # ─── Consensus ───
    all_A1 = fit_A1_vals + [A1_rich, A1_reg3]
    best_A1 = np.median(all_A1)
    A1_range = max(all_A1) - min(all_A1)
    print(f"\n  ══ CONSENSUS A₁^({k}) = {best_A1:.15f} (range {A1_range:.2e}) ══")

    # For PSLQ, use the mpf Richardson value (highest precision)
    return A1_rich_mp, ck, kk, Lk

# ═══════════════════════════════════════════════════════════
# PSLQ IDENTIFICATION ENGINE
# ═══════════════════════════════════════════════════════════

def pslq_search(A1_mp, k, ck):
    """Systematic PSLQ search for closed-form A₁."""
    print(f"\n  ╔══════════════════════════════════════════╗")
    print(f"  ║  PSLQ SEARCH: A₁^({k}) = {float(A1_mp):.15f}  ║")
    print(f"  ╚══════════════════════════════════════════╝")

    kk = mpf(-(k+3))/4
    sqrt3 = msqrt(3)

    def try_basis(name, vec, max_coeff=500):
        """Try PSLQ on [A₁] + basis_values."""
        full = [A1_mp] + list(vec)
        result = mpslq(full, maxcoeff=max_coeff, maxsteps=10000)
        if result is not None:
            check = sum(result[i]*full[i] for i in range(len(full)))
            if abs(float(check)) < 1e-20:
                # Parse: result[0]*A₁ + result[1]*v₁ + ... = 0
                # A₁ = -sum(result[i]*v_i)/result[0]
                print(f"    {name}: FOUND! {result}")
                print(f"      residual = {float(check):.2e}")
                denom = result[0]
                terms = []
                for i, (coeff, val) in enumerate(zip(result[1:], vec)):
                    if coeff != 0:
                        terms.append(f"({-coeff}/{denom})*v{i}")
                return result
            else:
                print(f"    {name}: spurious (residual={float(check):.2e})")
                return None
        else:
            print(f"    {name}: no relation")
            return None

    # Basis A: {c_k, 1/c_k, 1}
    # k=1: A₁ = -c₁/48 - 1/c₁, so PSLQ should find [48, 1, 48, 0]
    rA = try_basis("{c, 1/c, 1}", [ck, 1/ck, mpf(1)])
    if rA:
        d = rA[0]
        print(f"      → A₁ = ({-rA[1]}/{d})·c + ({-rA[2]}/{d})/c + ({-rA[3]}/{d})")

    # Basis B: {k·c_k, 1/c_k, 1}
    rB = try_basis("{kc, 1/c, 1}", [mpf(k)*ck, 1/ck, mpf(1)])
    if rB:
        d = rB[0]
        print(f"      → A₁ = ({-rB[1]}/{d})·{k}c + ({-rB[2]}/{d})/c + ({-rB[3]}/{d})")

    # Basis C: {c_k, 1/c_k, c_k², 1}
    rC = try_basis("{c, 1/c, c², 1}", [ck, 1/ck, ck**2, mpf(1)])
    if rC:
        d = rC[0]
        print(f"      → A₁ = ({-rC[1]}/{d})c + ({-rC[2]}/{d})/c + ({-rC[3]}/{d})c² + ({-rC[4]}/{d})")

    # Basis D: {k·c_k, k/c_k, k², 1}
    rD = try_basis("{kc, k/c, k², 1}", [mpf(k)*ck, mpf(k)/ck, mpf(k*k), mpf(1)])
    if rD:
        d = rD[0]
        print(f"      → A₁ = ({-rD[1]}/{d})·kc + ({-rD[2]}/{d})·k/c + ({-rD[3]}/{d})·k² + ({-rD[4]}/{d})")

    # Basis E: {c_k, 1/c_k, c_k², 1/c_k², 1}
    rE = try_basis("{c, 1/c, c², 1/c², 1}", [ck, 1/ck, ck**2, 1/ck**2, mpf(1)], max_coeff=1000)

    # Basis F: {c_k, 1/c_k, log(2π), 1}
    log2pi = mlog(2*mpi)
    rF = try_basis("{c, 1/c, log(2π), 1}", [ck, 1/ck, log2pi, mpf(1)])

    # Basis G: {c_k, 1/c_k, ζ(3), 1}
    zeta3 = mzeta(3)
    rG = try_basis("{c, 1/c, ζ(3), 1}", [ck, 1/ck, zeta3, mpf(1)])

    # Basis H: {c_k, 1/c_k, log(2π), ζ(3), 1}
    rH = try_basis("{c, 1/c, log(2π), ζ(3), 1}", [ck, 1/ck, log2pi, zeta3, mpf(1)])

    # Basis I: raw {π, 1/π, √3, √3/π, 1}  (avoid c_k parametrization)
    rI = try_basis("{π, 1/π, √3, √3/π, 1}", [mpi, 1/mpi, sqrt3, sqrt3/mpi, mpf(1)], max_coeff=1000)

    # Basis J: {π/√3, √3/π, π²/3, 3/π², 1}
    rJ = try_basis("{π/√3, √3/π, π²/3, 3/π², 1}",
                   [mpi/sqrt3, sqrt3/mpi, mpi**2/3, 3/mpi**2, mpf(1)], max_coeff=1000)

    # Basis K: {c_k, 1/c_k, c_k·log(2π), log(2π)/c_k, 1}
    rK = try_basis("{c, 1/c, c·log(2π), log(2π)/c, 1}",
                   [ck, 1/ck, ck*log2pi, log2pi/ck, mpf(1)], max_coeff=1000)

    # Basis L: Also try the RESIDUAL after removing analytical base
    base = -mpf(k)*ck/48 + kk/ck
    Delta = A1_mp - base
    print(f"\n    Δ = A₁ - (-kc/48+κ/c) = {float(Delta):.15f}")
    rL = try_basis("Δ ~ {c, 1/c, c², 1}", [ck, 1/ck, ck**2, mpf(1)], max_coeff=1000)
    if rL:
        d = rL[0]
        print(f"      → Δ = ({-rL[1]}/{d})c + ({-rL[2]}/{d})/c + ({-rL[3]}/{d})c² + ({-rL[4]}/{d})")

    # Basis M: Δ ~ {(k-1)·c, (k-1)/c, (k-1)², 1}
    km1 = mpf(k-1)
    rM = try_basis(f"Δ ~ {{(k-1)c, (k-1)/c, (k-1)², 1}}",
                   [km1*ck, km1/ck, km1**2, mpf(1)], max_coeff=1000)

    return rA or rB or rC or rD or rE or rF or rG or rH or rI or rJ or rK


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    t0 = time.time()

    for k, N in [(1, 6000), (2, 5000), (3, 5000)]:
        print(f"\n{'='*70}")
        print(f"k = {k}: {'Standard' if k==1 else f'{k}-Colored'} Partitions (N={N})")
        print(f"{'='*70}")

        tk = time.time()
        if k == 1:
            pk = [p1(n) for n in range(N+1)]
        else:
            pk = compute_pk(N, k)
        elapsed = time.time() - tk
        print(f"Computed in {elapsed:.1f}s. f({N}) has {len(str(pk[N]))} digits.")

        A1_mp, ck, kk, Lk = extract_A1(pk, k, N)

        # Validation for k=1
        if k == 1:
            A1_exact = -(mpi**2 + 72) / (24 * mpi * msqrt(6))
            gap = abs(float(A1_mp - A1_exact))
            print(f"\n  Exact: A₁ = -(π²+72)/(24π√6) = {float(A1_exact):.15f}")
            print(f"  Gap from exact: {gap:.2e}")

        pslq_search(A1_mp, k, ck)

    # ─── Cross-family summary ───
    print(f"\n\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Total time: {time.time()-t0:.1f}s")
    print("=== DONE ===")
