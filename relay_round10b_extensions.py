"""
ROUND 10B — PLANE PARTITIONS + EXTENDED A₁ EXTRACTION
Tests ratio universality for cube-root growth (plane partitions)
and extracts A₁^(k) for k=1..5 with high precision.
"""
import math, sys, time
import numpy as np
from functools import lru_cache
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog, exp as mexp, power as mpow, cbrt

mp.dps = 80
sys.setrecursionlimit(10000)

# ══════════════════════════════════════════════════════════════
# §1  PLANE PARTITIONS
# ══════════════════════════════════════════════════════════════

def compute_plane_partitions(N):
    """MacMahon: prod_{m>=1} (1-q^m)^{-m}.
    Recurrence: n*f(n) = sum_{j=1}^n sigma_2(j)*f(n-j)
    where sigma_2(j) = sum_{d|j} d^2.
    """
    sig2 = [0]*(N+1)
    for j in range(1, N+1):
        s, d = 0, 1
        while d*d <= j:
            if j % d == 0:
                s += d*d
                if d != j//d: s += (j//d)**2
            d += 1
        sig2[j] = s

    f = [0]*(N+1); f[0] = 1
    for n in range(1, N+1):
        s = 0
        for j in range(1, n+1):
            s += sig2[j]*f[n-j]
        f[n] = s//n
    
    # Verify: MacMahon numbers 1, 1, 3, 6, 13, 24, 48, 86, 160, 282, ...
    known = [1, 1, 3, 6, 13, 24, 48, 86, 160, 282, 500, 859, 1479]
    for i, v in enumerate(known):
        if i <= N: assert f[i] == v, f"PL({i})={f[i]} != {v}"
    return f

def analyze_plane_partitions(f, N):
    """Plane partition asymptotics:
    f(n) ~ C * n^{-25/36} * exp(c_pp * n^{2/3})
    where c_pp = 3*(zeta(3)/4)^{1/3} * (what?)
    
    Exact: c_pp = (2*pi)^{2/3} * (zeta(3))^{1/3} ... no.
    
    Actually: log f(n) ~ c*n^{2/3} + kappa*log(n) + const + A1*n^{-1/3} + ...
    
    From Wright: c_pp = alpha * zeta(3)^{1/3}
    where alpha = 3/(2^{2/3}) = 3/2^{2/3}
    
    Wait, the standard result is:
    PL(n) ~ C * n^{-25/36} * exp(3*(zeta(3)/4)^{1/3} * n^{2/3} + ...)
    where c_pp = 3*(zeta(3)/4)^{1/3} ≈ 3*(1.20206/4)^{1/3} ≈ 3*0.67105 ≈ 2.01315
    
    Actually wait, let me look this up precisely.
    
    Wright (1934): for prod(1-q^m)^{-m}, the asymptotics are
    PL(n) ~ C * exp(c * n^{2/3}) * n^{-25/36}
    where c = {3/[2*zeta(3)]}^{1/3} * zeta(3) ... no.
    
    The correct formula is: c = (3*zeta(3)/2)^{1/3} * something.
    
    Let me just compute it numerically from the data.
    """
    print("="*70)
    print("PLANE PARTITIONS: Ratio Analysis")
    print("="*70)
    
    # First: extract c_pp from log f(n) / n^{2/3}
    # For large n: log f(n) ≈ c*n^{2/3} + κ*log(n) + const
    print(f"\n  Extracting c_pp from data (N={N}):")
    
    # Rough extraction: c ≈ [log f(n) - log f(n/2)] / [n^{2/3} - (n/2)^{2/3}]
    for n_test in [200, 500, 1000, 2000]:
        if n_test > N: break
        n2 = n_test // 2
        if f[n_test] > 0 and f[n2] > 0:
            logf1 = float(mlog(mpf(f[n_test])))
            logf2 = float(mlog(mpf(f[n2])))
            c_est = (logf1 - logf2) / (n_test**(2/3) - n2**(2/3))
            print(f"    n={n_test}: c_est = {c_est:.8f}")
    
    # Better: 4-parameter fit log f(n) = c*n^{2/3} + κ*log(n) + β + γ*n^{-1/3}
    fit_start = max(100, N//5)
    ns = list(range(fit_start, N+1))
    ys = [float(mlog(mpf(f[n]))) for n in ns]
    x1 = [n**(2/3) for n in ns]  # c coefficient
    x2 = [math.log(n) for n in ns]  # κ coefficient
    x3 = [1.0 for n in ns]  # constant
    x4 = [n**(-1/3) for n in ns]  # γ coefficient
    
    A = np.column_stack([x1, x2, x3, x4])
    b = np.array(ys)
    params, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    c_pp, kappa_pp, beta_pp, gamma_pp = params
    max_res = float(np.max(np.abs(A@params - b)))
    
    print(f"\n  4-parameter fit [n in {fit_start}..{N}]:")
    print(f"    c_pp  = {c_pp:.10f}")
    print(f"    κ_pp  = {kappa_pp:.8f}  (expected: -25/36 = {-25/36:.8f})")
    print(f"    β     = {beta_pp:.8f}")
    print(f"    γ     = {gamma_pp:.8f}")
    print(f"    max residual = {max_res:.2e}")
    
    # Theoretical c_pp
    from mpmath import zeta as mzeta
    zeta3 = float(mzeta(3))
    # Wright: c = 3 * (zeta(3)/4)^{1/3}
    c_wright = 3 * (zeta3/4)**(1/3)
    print(f"\n  Theoretical: c = 3*(ζ(3)/4)^{{1/3}} = {c_wright:.10f}")
    print(f"  Fitted:      c = {c_pp:.10f}")
    print(f"  Diff: {abs(c_pp - c_wright):.4e}")
    
    # Now test ratio universality
    # For cube-root growth: f(n) ~ C*n^κ*exp(c*n^{2/3})
    # R_m = f(m)/f(m-1) = exp(c[m^{2/3}-(m-1)^{2/3}]) * (m/(m-1))^κ * correction
    # 
    # m^{2/3} - (m-1)^{2/3} = m^{2/3}[1 - (1-1/m)^{2/3}]
    #  = m^{2/3}[(2/3)/m + (1/9)/m^2 + (4/81)/m^3 + ...]
    #  = (2/3)m^{-1/3} + (1/9)m^{-4/3} + ...
    #
    # So R_m ≈ 1 + 2c/(3m^{1/3}) + L_pp/m^{2/3} + ...
    # where L_pp = (2c)^2/18 + κ = 2c^2/9 + κ  (by analogy with sqrt case)
    #
    # More carefully: exp(2c/(3m^{1/3}) + c/(9m^{4/3}) + ...)
    # = 1 + 2c/(3m^{1/3}) + [2c^2/9]/(m^{2/3}) + ...
    # Plus power law: 1 + κ/m + ... (only integer powers)
    # So L_pp = 2c^2/9 + ... hmm, κ enters at 1/m not 1/m^{2/3}
    
    # Let me be precise. For f(n) ~ C*n^κ*exp(c*n^{2/3}):
    # R_m = exp(c*(m^{2/3}-(m-1)^{2/3})) * (m/(m-1))^κ * sub-leading
    #
    # Expand m^{2/3}-(m-1)^{2/3}:
    # = m^{2/3}*(1-(1-1/m)^{2/3})
    # = m^{2/3}*((2/3)/m + (1/9)/m^2 + (4/81)/m^3 + ...)
    # = (2/3)*m^{-1/3} + (1/9)*m^{-4/3} + (4/81)*m^{-7/3} + ...
    #
    # exp of this: exp((2c/3)*m^{-1/3} + (c/9)*m^{-4/3} + ...)
    # Let u = (2c/3)*m^{-1/3}
    # = 1 + u + u^2/2 + u^3/6 + ...
    #   + (c/9)*m^{-4/3} + cross terms
    # = 1 + (2c/3)*m^{-1/3} + (2c^2/9)*m^{-2/3} + (4c^3/81)*m^{-1}
    #   + (c/9)*m^{-4/3} + ...
    #
    # Power law: (1-1/m)^{-κ} = 1 + κ/m + κ(κ+1)/(2m^2) + ...
    #
    # Combined:
    # m^{-1/3}: 2c/3
    # m^{-2/3}: 2c^2/9
    # m^{-1}:   4c^3/81 + κ   ← THIS is L_pp!
    # m^{-4/3}: correction involving c^4 + c/9 + cκ/3       
    
    L_pp_pred = 4*c_pp**3/81 + kappa_pp
    print(f"\n  Ratio universality for cube-root growth:")
    print(f"  R_m = 1 + (2c/3)/m^{{1/3}} + (2c²/9)/m^{{2/3}} + L_pp/m + ...")
    print(f"  L_pp = 4c³/81 + κ = {4*c_pp**3/81:.8f} + {kappa_pp:.8f} = {L_pp_pred:.8f}")
    
    # Extract empirically
    print(f"\n  Empirical C_m extraction:")
    print(f"  C_m = m*(R_m - 1 - (2c/3)/m^{{1/3}} - (2c²/9)/m^{{2/3}})")
    
    cm_data = {}
    for m in range(50, N+1):
        if f[m] == 0 or f[m-1] == 0: continue
        R = mpf(f[m]) / mpf(f[m-1])
        # Subtract known terms
        correction = mpf(2*c_pp/3) / mpow(mpf(m), mpf(1)/3) + mpf(2*c_pp**2/9) / mpow(mpf(m), mpf(2)/3)
        Cm = mpf(m) * (R - 1 - correction)
        cm_data[m] = float(Cm)
    
    samples = [m for m in [50, 100, 200, 500, 1000, 2000] if m <= N and m in cm_data]
    for m in samples:
        gap = cm_data[m] - L_pp_pred
        print(f"    m={m:5d}: C_m = {cm_data[m]:.8f}  (gap from L_pp = {gap:+.4e})")
    
    # Extrapolate
    ms = np.array(sorted(m for m in cm_data if m >= N//3), dtype=float)
    cs = np.array([cm_data[int(m)] for m in ms])
    if len(ms) > 10:
        # C_m = L + A*m^{-1/3}
        X = np.column_stack([np.ones_like(ms), ms**(-1/3)])
        prm, _, _, _ = np.linalg.lstsq(X, cs, rcond=None)
        L_ext = prm[0]
        print(f"\n  Extrapolation (C_m = L + A/m^{{1/3}}):")
        print(f"    L_ext = {L_ext:.10f}")
        print(f"    L_pred = {L_pp_pred:.10f}")
        gap_pct = abs(L_ext - L_pp_pred)/abs(L_pp_pred)*100 if L_pp_pred != 0 else float('inf')
        print(f"    gap = {abs(L_ext - L_pp_pred):.4e} ({gap_pct:.4f}%)")
    
    return c_pp, kappa_pp, L_pp_pred, cm_data

# ══════════════════════════════════════════════════════════════
# §2  EXTENDED A₁ FOR k=4,5
# ══════════════════════════════════════════════════════════════

def compute_pk(N, k):
    pk = [0]*(N+1); pk[0] = 1
    ksig = [0]*(N+1)
    for j in range(1, N+1):
        s, d = 0, 1
        while d*d <= j:
            if j%d == 0: s += d; s += j//d if d != j//d else 0
            d += 1
        ksig[j] = k*s
    for n in range(1, N+1):
        s = 0
        for j in range(1, n+1): s += ksig[j]*pk[n-j]
        pk[n] = s//n
    return pk

def fit_4param(data, c, n0, n1):
    ys, x1, x2, x3, x4 = [], [], [], [], []
    for n in range(n0, n1+1):
        if data[n] <= 0: continue
        y = float(mlog(mpf(data[n])) - mpf(c)*msqrt(mpf(n)))
        ys.append(y); x1.append(math.log(n)); x2.append(1.0)
        x3.append(1.0/math.sqrt(n)); x4.append(1.0/n)
    A = np.column_stack([x1, x2, x3, x4])
    b = np.array(ys)
    params, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    res = float(np.max(np.abs(A@params - b)))
    return params[0], params[1], params[2], params[3], res

@lru_cache(maxsize=None)
def p(n):
    if n < 0: return 0
    if n == 0: return 1
    s = 0
    for j in range(1, n+1):
        g1 = j*(3*j-1)//2; g2 = j*(3*j+1)//2; sign = (-1)**(j+1)
        if g1>n and g2>n: break
        if g1<=n: s += sign*p(n-g1)
        if g2<=n: s += sign*p(n-g2)
    return s

def compute_overpartitions(N):
    c = [0]*(N+1)
    for j in range(1, N+1):
        s, d = 0, 1
        while d*d <= j:
            if j%d == 0:
                q = j//d
                if q%2 == 1: s += d
                if d != q and d%2 == 1: s += q
            d += 1
        c[j] = 2*s
    pbar = [0]*(N+1); pbar[0] = 1
    for n in range(1, N+1):
        s = 0
        for j in range(1, n+1): s += c[j]*pbar[n-j]
        pbar[n] = s//n
    return pbar

if __name__ == "__main__":
    t0 = time.time()
    
    # §1: Plane partitions
    print("Computing plane partitions to N=2000...", end=" ", flush=True)
    tp = time.time()
    pl = compute_plane_partitions(2000)
    print(f"done in {time.time()-tp:.1f}s. PL(2000) has {len(str(pl[2000]))} digits.")
    
    c_pp, kappa_pp, L_pp, cm_pp = analyze_plane_partitions(pl, 2000)
    
    # §2: Extended A₁ extraction
    print(f"\n\n{'='*70}")
    print(f"EXTENDED A₁ EXTRACTION (k=1..5 + overpartitions)")
    print(f"{'='*70}")
    
    families = []
    
    # k=1: N=4000
    print("\nComputing k=1 to N=4000...", end=" ", flush=True)
    pk1 = [p(i) for i in range(4001)]
    print(f"done.")
    c1 = float(mpi*msqrt(mpf(2)/3))
    families.append((1, pk1, c1, 4000))
    
    # k=2: N=2000
    print("Computing k=2 to N=2000...", end=" ", flush=True)
    t2 = time.time()
    pk2 = compute_pk(2000, 2)
    print(f"done in {time.time()-t2:.1f}s.")
    c2 = float(mpi*msqrt(mpf(4)/3))
    families.append((2, pk2, c2, 2000))
    
    # k=3: N=2000
    print("Computing k=3 to N=2000...", end=" ", flush=True)
    t3 = time.time()
    pk3 = compute_pk(2000, 3)
    print(f"done in {time.time()-t3:.1f}s.")
    c3 = float(mpi*msqrt(mpf(2)))
    families.append((3, pk3, c3, 2000))
    
    # k=4: N=1000
    print("Computing k=4 to N=1000...", end=" ", flush=True)
    t4 = time.time()
    pk4 = compute_pk(1000, 4)
    print(f"done in {time.time()-t4:.1f}s.")
    c4 = float(mpi*msqrt(mpf(8)/3))
    families.append((4, pk4, c4, 1000))
    
    # k=5: N=800
    print("Computing k=5 to N=800...", end=" ", flush=True)
    pk5 = compute_pk(800, 5)
    print(f"done.")
    c5 = float(mpi*msqrt(mpf(10)/3))
    families.append((5, pk5, c5, 800))
    
    # Overpartitions: N=1500
    print("Computing overpartitions to N=1500...", end=" ", flush=True)
    tov = time.time()
    pbar = compute_overpartitions(1500)
    print(f"done in {time.time()-tov:.1f}s.")
    cov = float(mpi)
    
    print(f"\n{'='*70}")
    print(f"PRECISION A₁ TABLE")
    print(f"{'='*70}")
    print(f"{'k':>3} {'N':>6} {'κ_fit':>12} {'A₁':>14} {'A₂':>14} {'max_res':>10}")
    print("-"*62)
    
    A1_vals = {}
    for k, data, ck, N in families:
        fit_start = max(200, N//4)
        kf, bf, a1f, a2f, mr = fit_4param(data, ck, fit_start, N)
        A1_vals[k] = a1f
        kap_pred = -(k+3)/4
        print(f"{k:>3} {N:>6} {kf:>12.8f} {a1f:>14.8f} {a2f:>14.8f} {mr:>10.2e}")
    
    # Overpartitions
    fit_os = max(200, 1500//4)
    kf_ov, bf_ov, a1_ov, a2_ov, mr_ov = fit_4param(pbar, cov, fit_os, 1500)
    print(f"{'ov':>3} {1500:>6} {kf_ov:>12.8f} {a1_ov:>14.8f} {a2_ov:>14.8f} {mr_ov:>10.2e}")
    
    # A₁ pattern analysis
    print(f"\n{'='*70}")
    print(f"A₁ PATTERN ANALYSIS")
    print(f"{'='*70}")
    
    ks = sorted(A1_vals.keys())
    A1s = np.array([A1_vals[k] for k in ks])
    
    # Polynomial fit: A₁(k) = a + b*k + c*k²
    Xk = np.column_stack([np.ones(len(ks)), ks, np.array(ks)**2])
    pfit, _, _, _ = np.linalg.lstsq(Xk, A1s, rcond=None)
    print(f"\n  Quadratic fit: A₁(k) = {pfit[0]:.8f} + {pfit[1]:.8f}*k + {pfit[2]:.8f}*k²")
    
    print(f"\n  k  {'A₁(fit)':>14}  {'A₁(quad)':>14}  {'diff':>10}")
    for k in ks:
        pred = pfit[0] + pfit[1]*k + pfit[2]*k**2
        print(f"  {k}  {A1_vals[k]:>14.8f}  {pred:>14.8f}  {abs(pred-A1_vals[k]):>10.2e}")
    
    # Alternative: try A₁(k) = a + b*c_k + d/c_k
    cks = [float(mpi*msqrt(mpf(2*k)/3)) for k in ks]
    Xb = np.column_stack([np.ones(len(ks)), cks, [1/c for c in cks]])
    pfitb, _, _, _ = np.linalg.lstsq(Xb, A1s, rcond=None)
    print(f"\n  Basis {{1, c_k, 1/c_k}}:")
    print(f"    A₁(k) = {pfitb[0]:.8f} + {pfitb[1]:.8f}*c_k + {pfitb[2]:.8f}/c_k")
    for i, k in enumerate(ks):
        pred = pfitb[0] + pfitb[1]*cks[i] + pfitb[2]/cks[i]
        print(f"    k={k}: fit={A1_vals[k]:.8f}, pred={pred:.8f}, diff={abs(pred-A1_vals[k]):.2e}")
    
    # Try to identify constants
    # For k=1: A₁ = -c/48 - 1/c (known from Rademacher)
    # Let me try: A₁(k) = -c_k/48 + κ_k/c_k + δ_k where δ_k is Dirichlet-dependent
    print(f"\n  Decomposition: A₁ = -c_k/48 + κ_k/c_k + δ_k")
    deltas = {}
    for k in ks:
        ck = float(mpi*msqrt(mpf(2*k)/3))
        kap = -(k+3)/4
        base = -ck/48 + kap/ck
        delta = A1_vals[k] - base
        deltas[k] = delta
        print(f"    k={k}: δ = {delta:+.8f}")
    
    # δ_k pattern
    print(f"\n  δ_k analysis:")
    print(f"    δ_1 = {deltas[1]:+.8f}  (should be ~0 for Rademacher)")
    if len(deltas) >= 3:
        # Fit δ(k) = a*(k-1) + b*(k-1)^2
        dk = np.array([deltas[k] for k in ks])
        km1 = np.array([k-1 for k in ks])
        Xd = np.column_stack([km1, km1**2])
        pd, _, _, _ = np.linalg.lstsq(Xd, dk, rcond=None)
        print(f"    δ(k) ≈ {pd[0]:.8f}*(k-1) + {pd[1]:.8f}*(k-1)²")
        for k in ks:
            pred = pd[0]*(k-1) + pd[1]*(k-1)**2
            print(f"      k={k}: δ_pred={pred:+.8f}, δ_act={deltas[k]:+.8f}, diff={abs(pred-deltas[k]):.2e}")
    
    # ══════════════════════════════════════════════════════════
    # Richardson α extraction for all families
    # ══════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"RICHARDSON α EXTRACTION")
    print(f"{'='*70}")
    
    def rich_alpha(data, c, L, N):
        """Richardson extrapolation on D_m = sqrt(m)*(C_m - L)."""
        def D(m):
            R = mpf(data[m])/mpf(data[m-1])
            C = mpf(m)*(R - 1 - mpf(c)/(2*msqrt(mpf(m))))
            return float((C - mpf(L))*msqrt(mpf(m)))
        pairs = [(m1, 4*m1) for m1 in [50,100,150,200,300,400,500] if 4*m1 <= N]
        results = []
        for m1, m2 in pairs:
            d1, d2 = D(m1), D(m2)
            alpha_r = (2*d2 - d1)  # r=2, (r*D2-D1)/(r-1)
            results.append((m1, alpha_r))
        return results
    
    print(f"\n{'k':>3} {'best α_Rich':>16} {'α from formula':>16} {'gap':>12}")
    print("-"*50)
    
    alpha_rich_vals = {}
    for k, data, ck, N in families:
        kap = -(k+3)/4
        L = ck**2/8 + kap
        results = rich_alpha(data, ck, L, N)
        if results:
            best = results[-1][1]
            alpha_rich_vals[k] = best
            # Formula prediction using fitted A₁
            alpha_formula = ck*(ck**2+6)/48 + ck*kap/2 - A1_vals[k]/2
            print(f"{k:>3} {best:>16.10f} {alpha_formula:>16.10f} {abs(best-alpha_formula):>12.2e}")
    
    # Overpartitions
    L_ov = cov**2/8 - 1
    rov = rich_alpha(pbar, cov, L_ov, 1500)
    if rov:
        best_ov = rov[-1][1]
        alpha_ov_formula = cov*(cov**2+6)/48 + cov*(-1)/2 - a1_ov/2
        print(f"{'ov':>3} {best_ov:>16.10f} {alpha_ov_formula:>16.10f} {abs(best_ov-alpha_ov_formula):>12.2e}")
    
    # ══════════════════════════════════════════════════════════
    # CONVERGENCE DATA for visualization (output as JSON-ish)
    # ══════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"CONVERGENCE DATA FOR VISUALIZATION")
    print(f"{'='*70}")
    
    for k, data, ck, N in families:
        kap = -(k+3)/4
        L = ck**2/8 + kap
        print(f"\nk={k}: L={L:.10f}")
        ms_out = [m for m in range(20, N+1, max(1, N//200))]
        for m in ms_out:
            if m >= len(data) or data[m] == 0 or data[m-1] == 0: continue
            R = mpf(data[m])/mpf(data[m-1])
            # Normalized: [R_m - 1 - c/(2sqrt(m))] * m / L = should → 1
            Cm = float(mpf(m)*(R - 1 - mpf(ck)/(2*msqrt(mpf(m)))))
            if m in [50, 200, 500, 1000, 2000]:
                ratio_to_L = Cm/L if L != 0 else float('inf')
                print(f"  m={m:5d}: C_m/L = {ratio_to_L:.6f}")
    
    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")
    print("=== DONE ===")
