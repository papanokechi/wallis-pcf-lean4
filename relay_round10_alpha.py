"""
ROUND 10 — PRECISION ALPHA EXTRACTION
Extract A₁^(k) from Meinardus fits and alpha_k from D_m extrapolation.
Also compute to larger N for k=2,3.
"""
import math, sys, time
import numpy as np
from functools import lru_cache
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog

mp.dps = 60
sys.setrecursionlimit(10000)

@lru_cache(maxsize=None)
def p(n):
    if n < 0: return 0
    if n == 0: return 1
    s = 0
    for j in range(1, n + 1):
        g1 = j*(3*j-1)//2; g2 = j*(3*j+1)//2; sign = (-1)**(j+1)
        if g1 > n and g2 > n: break
        if g1 <= n: s += sign * p(n - g1)
        if g2 <= n: s += sign * p(n - g2)
    return s

def compute_pk(N, k):
    pk = [0]*(N+1); pk[0] = 1
    ksig = [0]*(N+1)
    for j in range(1, N+1):
        s, d = 0, 1
        while d*d <= j:
            if j%d == 0:
                s += d
                if d != j//d: s += j//d
            d += 1
        ksig[j] = k*s
    for n in range(1, N+1):
        s = 0
        for j in range(1, n+1): s += ksig[j]*pk[n-j]
        pk[n] = s//n
    return pk

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

def fit_4param(data, c, n0, n1):
    """Fit log f(n) = c√n + α ln n + β + γ/√n + δ/n."""
    ns = list(range(n0, n1+1))
    ys, x1, x2, x3, x4 = [], [], [], [], []
    for n in ns:
        if data[n] <= 0: continue
        y = float(mlog(mpf(data[n])) - mpf(c)*msqrt(mpf(n)))
        ys.append(y); x1.append(math.log(n)); x2.append(1.0)
        x3.append(1.0/math.sqrt(n)); x4.append(1.0/n)
    A = np.column_stack([x1, x2, x3, x4])
    b = np.array(ys)
    params, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    res = float(np.max(np.abs(A@params - b)))
    return {'kappa': params[0], 'beta': params[1], 'A1': params[2],
            'A2_log': params[3], 'max_res': res}

def extract_alpha_richardson(data, c, L, m_pairs):
    """Richardson extrapolation on D_m = (C_m - L)√m.
    Assume D_m = α + B/√m + ..., use pairs to cancel B term.
    """
    def D(m):
        R = mpf(data[m]) / mpf(data[m-1])
        C = mpf(m) * (R - 1 - mpf(c)/(2*msqrt(mpf(m))))
        return float((C - mpf(L)) * msqrt(mpf(m)))
    
    results = []
    for m1, m2 in m_pairs:
        if m1 >= len(data) or m2 >= len(data): continue
        d1, d2 = D(m1), D(m2)
        r = math.sqrt(m2/m1)
        # D(m) = α + B/√m → α = (r·D(m2) - D(m1))/(r-1)
        alpha_rich = (r*d2 - d1)/(r - 1)
        results.append((m1, m2, d1, d2, alpha_rich))
    return results

if __name__ == "__main__":
    t0 = time.time()
    
    families = []
    
    # k=1: standard partitions, N=4000
    print("Computing k=1 (partitions) to N=4000...", end=" ", flush=True)
    N1 = 4000
    pk1 = [p(i) for i in range(N1+1)]
    print(f"done. p({N1}) has {len(str(pk1[N1]))} digits.")
    c1 = float(mpi*msqrt(mpf(2)/3))
    L1 = float(mpi**2/12 - 1)
    alpha1_exact = float((mpi**2-24)*(4*mpi**2-9)/(144*mpi*msqrt(mpf(6))))
    families.append(('k=1', pk1, c1, -(1+3)/4, L1, alpha1_exact, N1))
    
    # k=2: N=1500
    print("Computing k=2 to N=1500...", end=" ", flush=True)
    t2 = time.time()
    pk2 = compute_pk(1500, 2)
    print(f"done in {time.time()-t2:.1f}s.")
    c2 = float(mpi*msqrt(mpf(4)/3))
    L2 = float(2*mpi**2/12 - 5/4)
    families.append(('k=2', pk2, c2, -5/4, L2, None, 1500))
    
    # k=3: N=1500
    print("Computing k=3 to N=1500...", end=" ", flush=True)
    t3 = time.time()
    pk3 = compute_pk(1500, 3)
    print(f"done in {time.time()-t3:.1f}s.")
    c3 = float(mpi*msqrt(mpf(2)))
    L3 = float(3*mpi**2/12 - 6/4)
    families.append(('k=3', pk3, c3, -6/4, L3, None, 1500))
    
    # Overpartitions: N=1000
    print("Computing overpartitions to N=1000...", end=" ", flush=True)
    tov = time.time()
    pbar = compute_overpartitions(1000)
    print(f"done in {time.time()-tov:.1f}s.")
    cov = float(mpi)
    Lov = float(mpi**2/8 - 1)
    families.append(('overpart', pbar, cov, -1.0, Lov, None, 1000))
    
    print(f"\n{'='*80}")
    print(f"PRECISION A₁ EXTRACTION (from Meinardus 4-parameter fit)")
    print(f"{'='*80}")
    
    for label, data, c, kappa, L, alpha_known, N in families:
        fit_start = max(200, N//4)
        fit = fit_4param(data, c, fit_start, N)
        print(f"\n  {label} (fit range [{fit_start}, {N}]):")
        print(f"    κ_fit = {fit['kappa']:.10f}  (pred: {kappa:.6f})")
        print(f"    A₁    = {fit['A1']:.10f}")
        print(f"    A₂_log= {fit['A2_log']:.10f}")
        print(f"    max res = {fit['max_res']:.2e}")
        
        # From A₁, predict alpha
        alpha_from_A1 = c*(c**2+6)/48 + c*kappa/2 - fit['A1']/2
        print(f"    → α from A₁ = {alpha_from_A1:.10f}")
        if alpha_known:
            print(f"    → α exact    = {alpha_known:.10f}")
            print(f"    → diff = {abs(alpha_from_A1 - alpha_known):.2e}")
    
    print(f"\n{'='*80}")
    print(f"PRECISION α EXTRACTION (Richardson extrapolation on D_m)")
    print(f"{'='*80}")
    
    for label, data, c, kappa, L, alpha_known, N in families:
        pairs = []
        for m1 in [50, 100, 150, 200, 300]:
            m2 = 4*m1
            if m2 <= N:
                pairs.append((m1, m2))
        
        results = extract_alpha_richardson(data, c, L, pairs)
        print(f"\n  {label}:")
        for m1, m2, d1, d2, ar in results:
            tag = ""
            if alpha_known:
                tag = f" (gap={abs(ar-alpha_known):.2e})"
            print(f"    D({m1})={d1:.8f}, D({m2})={d2:.8f} → α_Rich = {ar:.8f}{tag}")
        
        if results:
            best = results[-1][4]
            print(f"    Best Richardson α = {best:.10f}")
            if alpha_known:
                print(f"    Exact α            = {alpha_known:.10f}")
    
    # ══════════════════════════════════════════════════════════
    # COMPARE A₁ VALUES
    # ══════════════════════════════════════════════════════════
    print(f"\n{'='*80}")
    print(f"A₁ COMPARISON TABLE")
    print(f"{'='*80}")
    print(f"{'Family':<12} {'A₁(fit)':<14} {'A₁=-c/48+κ/c':<14} {'diff':<12}")
    print("-"*55)
    
    for label, data, c, kappa, L, alpha_known, N in families:
        fit_start = max(200, N//4)
        fit = fit_4param(data, c, fit_start, N)
        A1_simple = -c/48 + kappa/c
        A1_fit = fit['A1']
        diff = abs(A1_fit - A1_simple)
        print(f"{label:<12} {A1_fit:<14.8f} {A1_simple:<14.8f} {diff:<12.4e}")
    
    # Try to identify the pattern in A₁
    print(f"\n{'='*80}")
    print(f"A₁ PATTERN ANALYSIS for k-colored partitions")
    print(f"{'='*80}")
    
    A1_vals = {}
    for label, data, c, kappa, L, alpha_known, N in families:
        if label.startswith('k='):
            k = int(label[2:])
            fit_start = max(200, N//4)
            fit = fit_4param(data, c, fit_start, N)
            A1_fit = fit['A1']
            A1_vals[k] = A1_fit
            
            # Decompose: A₁ = -c/48 + κ/c + extra
            A1_base = -c/48 + kappa/c
            extra = A1_fit - A1_base
            print(f"  k={k}: A₁ = {A1_fit:.8f} = (-c/48 + κ/c = {A1_base:.8f}) + extra = {extra:.8f}")
            # The extra might be related to D(-1)/c or something
            D_neg1 = -k/12  # ζ(-1) = -1/12
            print(f"       D(-1) = kζ(-1) = {D_neg1:.6f}")
            print(f"       D(-1)/c = {D_neg1/c:.8f}")
            print(f"       extra/(k-1) = {extra/(k-1):.8f}" if k > 1 else "")
    
    # Theory: Meinardus full sub-leading correction
    # The actual A₁ for Meinardus involves:
    # A₁ = (D(-1) - D(0)*(D(0)+1)/2 + ...) * something / c_k
    # Let me try a polynomial fit in k
    if len(A1_vals) >= 3:
        ks = sorted(A1_vals.keys())
        A1s = [A1_vals[k] for k in ks]
        # Fit A₁(k) = a + b*k + c*k²
        Xk = np.column_stack([np.ones(len(ks)), ks, np.array(ks)**2])
        params_A1, _, _, _ = np.linalg.lstsq(Xk, A1s, rcond=None)
        print(f"\n  Polynomial fit: A₁(k) ≈ {params_A1[0]:.6f} + {params_A1[1]:.6f}*k + {params_A1[2]:.6f}*k²")
        for k in ks:
            pred = params_A1[0] + params_A1[1]*k + params_A1[2]*k**2
            print(f"    k={k}: fit={pred:.8f}, actual={A1_vals[k]:.8f}, diff={abs(pred-A1_vals[k]):.2e}")
    
    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")
    print("=== DONE ===")
