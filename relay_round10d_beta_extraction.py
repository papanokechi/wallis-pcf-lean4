"""
Round 10D: β_k EXTRACTION — 4th-order coefficient of ratio universality
=========================================================================
Goals:
  1. Push k=4,5 A₁ extraction to N=5000 (from N≈800-1000)
  2. Extract β_k for all k=1,...,5 via polynomial extrapolation
  3. PSLQ identification of β_k and A₂^(k)

The ratio expansion is:
  R_m = p_k(m)/p_k(m-1) = 1 + c/(2√m) + L/m + α/m^{3/2} + β/m² + O(m^{-5/2})

where α = c(c²+6)/48 + cκ/2 - A₁/2  (involves A₁, now known in closed form)
and   β = structural(c, κ, A₁) - A₂   (involves A₂, the next frontier)

The structural piece is derived from exp(log R_m) expansion:
  β_struct = c⁴/384 + c²(1+2κ)/16 + κ(κ+1)/2 - cA₁/4
  β = β_struct - A₂

So: A₂ = β_struct - β
"""
import time, sys
import numpy as np
sys.setrecursionlimit(10000)
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, log as mlog, power as mpow
from mpmath import pslq as mpslq, zeta as mzeta
from functools import lru_cache

mp.dps = 80

# ─── Partition computation ───
@lru_cache(maxsize=None)
def p1(n):
    """Standard partitions via pentagonal number theorem."""
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
    """k-colored partitions: n·p_k(n) = Σ_{j=1}^n k·σ(j)·p_k(n-j)."""
    sig = [0]*(N+1)
    for j in range(1, N+1): sig[j] = k * sigma1(j)
    pk = [0]*(N+1); pk[0] = 1
    for n in range(1, N+1):
        s = 0
        for j in range(1, n+1): s += sig[j]*pk[n-j]
        pk[n] = s // n
    return pk

# ─── Meinardus parameters ───
def meinardus_params(k):
    ck = mpi * msqrt(mpf(2*k)/3)
    kk = mpf(-(k+3)) / 4
    Lk = ck**2/8 + kk
    return ck, kk, Lk

def A1_closed(k, ck, kk):
    """Closed form: A₁^(k) = -kc_k/48 - (k+1)(k+3)/(8c_k)."""
    return -mpf(k)*ck/48 - mpf((k+1)*(k+3))/(8*ck)

def alpha_from_A1(ck, kk, A1):
    """α = c(c²+6)/48 + cκ/2 - A₁/2."""
    return ck*(ck**2 + 6)/48 + ck*kk/2 - A1/2

def beta_structural(ck, kk, A1):
    """
    Structural part of β from exp(log R_m) expansion.
    
    log R_m = u₁/√m + u₂/m + u₃/m^{3/2} + u₄/m² + ...
    where u₁=c/2, u₂=κ, u₃=c/8−A₁/2, u₄=κ/2−A₂
    
    β = u₄ + u₁u₃ + u₂²/2 + u₁²u₂/2 + u₁⁴/24
      = (κ/2 − A₂) + (c/2)(c/8 − A₁/2) + κ²/2 + c²κ/8 + c⁴/384
    
    So β_struct (A₂-independent part) = c⁴/384 + c²/16 + c²κ/8 − cA₁/4 + κ²/2 + κ/2
    And β = β_struct − A₂
    """
    c, k_ = ck, kk
    return c**4/384 + c**2/16 + c**2*k_/8 - c*A1/4 + k_**2/2 + k_/2


# ═══════════════════════════════════════════════════════════════
# EXTRACTION
# ═══════════════════════════════════════════════════════════════

def extract_all(pk, k, N, label=""):
    """Extract A₁ and β for k-colored partitions from data pk[0..N]."""
    ck, kk, Lk = meinardus_params(k)
    A1_formula = A1_closed(k, ck, kk)
    alpha_k = alpha_from_A1(ck, kk, A1_formula)
    
    print(f"\n{'='*70}")
    print(f"k={k}: {label} (N={N})")
    print(f"{'='*70}")
    print(f"  c_k   = {float(ck):.16f}")
    print(f"  κ_k   = {float(kk)}")
    print(f"  L_k   = {float(Lk):.16f}")
    print(f"  A₁(formula) = {float(A1_formula):.16f}")
    print(f"  α(formula)  = {float(alpha_k):.16f}")
    
    # ─── Step 1: Extract A₁ via polynomial extrapolation of α_m ───
    m_start = max(200, N//8)
    step = max(1, (N - m_start) // 2000)
    ms = list(range(m_start, N+1, step))
    
    alpha_vals = []
    for m in ms:
        R = mpf(pk[m]) / mpf(pk[m-1])
        am = mpf(m) * msqrt(mpf(m)) * (R - 1 - ck/(2*msqrt(mpf(m))) - Lk/mpf(m))
        alpha_vals.append(float(am))
    
    alpha_arr = np.array(alpha_vals)
    ms_arr = np.array(ms, dtype=float)
    
    print(f"\n  A₁ extraction (polynomial extrapolation of α_m):")
    best_A1 = None
    for P in [5, 6, 7, 8]:
        X = np.column_stack([ms_arr**(-j/2) for j in range(P+1)])
        params, _, _, _ = np.linalg.lstsq(X, alpha_arr, rcond=None)
        alpha_est = params[0]
        res = float(np.max(np.abs(X@params - alpha_arr)))
        A1_est = 2*(float(alpha_k) - alpha_est + float(A1_formula)/2)
        # Actually: α_extracted = universal - A₁_true/2
        # So A₁_true = 2*(universal - α_extracted)
        # where universal = c(c²+6)/48 + cκ/2
        universal = float(ck*(ck**2 + 6)/48 + ck*kk/2)
        A1_est = 2*(universal - alpha_est)
        print(f"    P={P}: α_∞ = {alpha_est:.14f}, A₁ = {A1_est:.14f} (res={res:.2e})")
        best_A1 = A1_est
    
    gap_A1 = abs(best_A1 - float(A1_formula))
    print(f"  A₁(extracted) = {best_A1:.14f}")
    print(f"  A₁(formula)   = {float(A1_formula):.14f}")
    print(f"  Gap: {gap_A1:.2e}")
    
    # ─── Step 2: Extract β via polynomial extrapolation of β_m ───
    # β_m = m² · [R_m - 1 - c/(2√m) - L/m - α/m^{3/2}]
    print(f"\n  β extraction (polynomial extrapolation of β_m):")
    
    beta_vals = []
    for m in ms:
        R = mpf(pk[m]) / mpf(pk[m-1])
        sqm = msqrt(mpf(m))
        bm = mpf(m)**2 * (R - 1 - ck/(2*sqm) - Lk/mpf(m) - alpha_k/mpf(m)/sqm)
        beta_vals.append(float(bm))
    
    beta_arr = np.array(beta_vals)
    
    best_beta = None
    for P in [4, 5, 6, 7, 8]:
        X = np.column_stack([ms_arr**(-j/2) for j in range(P+1)])
        params, _, _, _ = np.linalg.lstsq(X, beta_arr, rcond=None)
        beta_est = params[0]
        res = float(np.max(np.abs(X@params - beta_arr)))
        print(f"    P={P}: β = {beta_est:+.14f} (res={res:.2e})")
        best_beta = beta_est
    
    # Compute structural β and extract A₂
    bs = float(beta_structural(ck, kk, A1_formula))
    A2_extracted = bs - best_beta
    print(f"\n  β(extracted)    = {best_beta:+.14f}")
    print(f"  β_struct        = {bs:+.14f}")
    print(f"  A₂ = β_struct−β = {A2_extracted:+.14f}")
    
    return best_A1, best_beta, float(A1_formula), float(alpha_k), A2_extracted, float(ck), float(kk)


# ═══════════════════════════════════════════════════════════════
# PSLQ SEARCH FOR A₂
# ═══════════════════════════════════════════════════════════════

def pslq_A2(A2_val, k, ck_f, kk_f):
    """Try PSLQ identification of A₂^(k)."""
    print(f"\n  PSLQ search for A₂^({k}) = {A2_val:+.14f}")
    
    A2 = mpf(A2_val)
    ck = mpi * msqrt(mpf(2*k)/3)
    kk = mpf(-(k+3))/4
    
    def try_pslq(name, basis, mc=500):
        vec = [A2] + list(basis)
        if any(abs(float(v)) < 1e-100 for v in vec):
            return None
        r = mpslq(vec, maxcoeff=mc, maxsteps=10000)
        if r is not None:
            check = sum(r[i]*vec[i] for i in range(len(vec)))
            if abs(float(check)) < 1e-8:
                print(f"    {name}: FOUND {r}  (res={float(check):.2e})")
                if r[0] != 0:
                    formula_parts = []
                    names = name.split('{')[1].split('}')[0].split(', ') if '{' in name else [f"b{j}" for j in range(len(basis))]
                    for i, coeff in enumerate(r[1:]):
                        if coeff != 0 and i < len(names):
                            formula_parts.append(f"({-coeff}/{r[0]})*{names[i]}")
                    print(f"      A₂ = {' + '.join(formula_parts)}")
                return r
        else:
            print(f"    {name}: ✗")
        return None
    
    # Basic polynomial in c, 1/c
    try_pslq("{c, 1/c, 1}", [ck, 1/ck, mpf(1)])
    try_pslq("{c², 1/c², c, 1/c, 1}", [ck**2, 1/ck**2, ck, 1/ck, mpf(1)], mc=1000)
    
    # k-weighted
    try_pslq("{kc, k/c, 1}", [mpf(k)*ck, mpf(k)/ck, mpf(1)])
    try_pslq("{kc, 1/c, k, 1}", [mpf(k)*ck, 1/ck, mpf(k), mpf(1)])
    try_pslq("{k²c, (k+1)(k+3)/c, 1}", [mpf(k**2)*ck, mpf((k+1)*(k+3))/ck, mpf(1)])
    
    # Quadratic in k with c
    try_pslq("{k²c, kc, c, k²/c, k/c, 1/c, 1}", 
             [mpf(k**2)*ck, mpf(k)*ck, ck, mpf(k**2)/ck, mpf(k)/ck, 1/ck, mpf(1)], mc=2000)
    
    # With transcendentals
    try_pslq("{c, 1/c, c³, 1/c³, 1}", [ck, 1/ck, ck**3, 1/ck**3, mpf(1)], mc=1000)
    
    # Analogy with A₁ pattern: A₁ = -kc/48 - (k+1)(k+3)/(8c)
    # Try: A₂ = a·k²c/D + b·(k+?)(k+?)/c² + ...
    try_pslq("{k²c, (k²-1)/c, 1}", [mpf(k**2)*ck, mpf(k**2-1)/ck, mpf(1)])
    try_pslq("{k²c², k(k+3)/c², 1}", [mpf(k**2)*ck**2, mpf(k*(k+3))/ck**2, mpf(1)])
    
    # Residual approach: subtract possible leading structure
    for a_num, a_den in [(-1, 48), (-1, 96), (-1, 192), (-1, 384), (-1, 576), (-1, 864), (-1, 1152)]:
        base = mpf(a_num) * mpf(k**2) * ck / mpf(a_den)
        delta = A2 - base
        if abs(float(delta)) > 1e-50:
            r = try_pslq(f"A₂-({a_num}k²c/{a_den}) ~ {{1/c, c, 1}}", [1/ck, ck, mpf(1)])
            if r: break
    
    # Try factored forms like with A₁
    # A₁·c = -(k+1)(k+3)/8 - k·c²/48
    # Try: A₂·c² = polynomial in k + polynomial × c²
    A2c2 = A2 * ck**2
    print(f"\n    A₂·c² = {float(A2c2):+.14f}")
    try_pslq("A₂·c² ~ {k³, k², k, 1}", [mpf(k**3), mpf(k**2), mpf(k), mpf(1)], mc=2000)
    try_pslq("A₂·c² ~ {k³, k², k, 1, c²}", [mpf(k**3), mpf(k**2), mpf(k), mpf(1), ck**2], mc=2000)
    
    # Try A₂·c  
    A2c = A2 * ck
    print(f"    A₂·c  = {float(A2c):+.14f}")
    try_pslq("A₂·c ~ {k³, k², k, 1}", [mpf(k**3), mpf(k**2), mpf(k), mpf(1)], mc=2000)
    try_pslq("A₂·c ~ {k², k, 1, c², kc²}", [mpf(k**2), mpf(k), mpf(1), ck**2, mpf(k)*ck**2], mc=2000)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    t0 = time.time()
    results = {}
    
    # ═══ k=1: Standard partitions (N=10000) ═══
    print("Computing k=1 (N=10000)...")
    tk = time.time()
    pk1 = [p1(n) for n in range(10001)]
    print(f"  Done in {time.time()-tk:.1f}s. p(10000) has {len(str(pk1[10000]))} digits.")
    r1 = extract_all(pk1, 1, 10000, "Standard Partitions")
    results[1] = r1
    
    # Check k=1 exact β
    beta1_exact = float((mpi**6 - 33*mpi**4 + 180*mpi**2 + 648) / (864*mpi**2))
    print(f"\n  β₁(exact)     = {beta1_exact:+.14f}")
    print(f"  β₁(extracted) = {r1[1]:+.14f}")
    print(f"  Gap: {abs(r1[1]-beta1_exact):.2e}")
    
    # ═══ k=2: 2-colored (N=5000) ═══
    print("\n\nComputing k=2 (N=5000)...")
    tk = time.time()
    pk2 = compute_pk(5000, 2)
    print(f"  Done in {time.time()-tk:.1f}s. p_2(5000) has {len(str(pk2[5000]))} digits.")
    r2 = extract_all(pk2, 2, 5000, "2-Colored Partitions")
    results[2] = r2
    
    # ═══ k=3: 3-colored (N=5000) ═══
    print("\n\nComputing k=3 (N=5000)...")
    tk = time.time()
    pk3 = compute_pk(5000, 3)
    print(f"  Done in {time.time()-tk:.1f}s. p_3(5000) has {len(str(pk3[5000]))} digits.")
    r3 = extract_all(pk3, 3, 5000, "3-Colored Partitions")
    results[3] = r3
    
    # ═══ k=4: 4-colored (N=5000) — UPGRADE from N≈800 ═══
    print("\n\nComputing k=4 (N=5000)...")
    tk = time.time()
    pk4 = compute_pk(5000, 4)
    print(f"  Done in {time.time()-tk:.1f}s. p_4(5000) has {len(str(pk4[5000]))} digits.")
    r4 = extract_all(pk4, 4, 5000, "4-Colored Partitions [UPGRADED]")
    results[4] = r4
    
    # ═══ k=5: 5-colored (N=5000) — UPGRADE from N≈1000 ═══
    print("\n\nComputing k=5 (N=5000)...")
    tk = time.time()
    pk5 = compute_pk(5000, 5)
    print(f"  Done in {time.time()-tk:.1f}s. p_5(5000) has {len(str(pk5[5000]))} digits.")
    r5 = extract_all(pk5, 5, 5000, "5-Colored Partitions [UPGRADED]")
    results[5] = r5
    
    # ═══════════════════════════════════════════════════════════
    # CROSS-FAMILY SUMMARY
    # ═══════════════════════════════════════════════════════════
    print(f"\n\n{'='*70}")
    print("CROSS-FAMILY A₁ SUMMARY")
    print(f"{'='*70}")
    print(f"{'k':>3} | {'A₁(extracted)':>20} | {'A₁(formula)':>20} | {'Gap':>12}")
    print("-"*70)
    for k in [1,2,3,4,5]:
        r = results[k]
        print(f"{k:>3} | {r[0]:>20.12f} | {r[2]:>20.12f} | {abs(r[0]-r[2]):>12.2e}")
    
    print(f"\n\n{'='*70}")
    print("CROSS-FAMILY β SUMMARY")
    print(f"{'='*70}")
    print(f"{'k':>3} | {'β(extracted)':>20} | {'A₂(extracted)':>20}")
    print("-"*70)
    for k in [1,2,3,4,5]:
        r = results[k]
        print(f"{k:>3} | {r[1]:>+20.12f} | {r[4]:>+20.12f}")
    
    # ═══ PSLQ on A₂ ═══
    print(f"\n\n{'='*70}")
    print("PSLQ IDENTIFICATION OF A₂")
    print(f"{'='*70}")
    for k in [1,2,3,4,5]:
        r = results[k]
        pslq_A2(r[4], k, r[5], r[6])
    
    # ═══ Pattern search on A₂ products ═══
    print(f"\n\n{'='*70}")
    print("PATTERN SEARCH: A₂ · c_k^n PRODUCTS")
    print(f"{'='*70}")
    for n_pow in [0, 1, 2, 3]:
        print(f"\n  A₂ · c^{n_pow}:")
        for k in [1,2,3,4,5]:
            r = results[k]
            ck = float(mpi * msqrt(mpf(2*k)/3))
            val = r[4] * ck**n_pow
            print(f"    k={k}: {val:+.14f}")
    
    # Also check Δ₂ pattern analogous to Δ₁
    print(f"\n\n  SELECTION RULE SEARCH for A₂:")
    print(f"  Analogous to Δ₁·c = -(k+3)(k-1)/8 for A₁")
    
    # For A₁: base = -kc/48, extra Δ₁ = A₁ - base, Δ₁·c = -(k+3)(k-1)/8
    # For A₂: try base = -k²c/D, extra Δ₂ = A₂ - base, check Δ₂·c^n
    for D in [48, 96, 192, 384, 576, 864, 1152, 1728, 2304, 3456, 6912]:
        deltas = []
        for k in [1,2,3,4,5]:
            r = results[k]
            ck = float(mpi * msqrt(mpf(2*k)/3))
            base = -k**2 * ck / D
            delta = r[4] - base
            deltas.append(delta)
        # Check delta * ck
        products = []
        for k, d in zip([1,2,3,4,5], deltas):
            ck = float(mpi * msqrt(mpf(2*k)/3))
            products.append(d * ck)
        # Check if products are rational or simple
        ratios = [products[i] / (1 if abs(products[0]) < 1e-10 else products[0]) for i in range(5)]
        # Check if products[i] = polynomial in k
        if all(abs(p) < 100 for p in products):
            diffs = [products[i+1] - products[i] for i in range(4)]
            if max(abs(d) for d in diffs) < 0.5 and min(abs(d) for d in diffs) > 0.001:
                print(f"  base=-k²c/{D}: Δ₂·c = {[f'{p:.6f}' for p in products]}")
    
    # Direct polynomial fit: A₂ = a·k²·c + b·poly(k)/c + d
    print(f"\n\n  Direct fit: A₂ = a·k²c + b·(k+p)(k+q)/c + d")
    print(f"  (Analogous to A₁ = -kc/48 - (k+1)(k+3)/(8c))")
    
    # Try to fit: A₂ = a·k²·ck + b·f(k)/ck
    # For 5 data points and 2 unknowns, we can do least squares
    ck_vals = [float(mpi * msqrt(mpf(2*k)/3)) for k in range(1,6)]
    A2_vals = [results[k][4] for k in range(1,6)]
    
    # Fit: A₂ = a·k²c + b/c  (simplest 2-param)
    X2 = np.array([[k**2 * ck_vals[k-1], 1/ck_vals[k-1]] for k in range(1,6)])
    params2, res2, _, _ = np.linalg.lstsq(X2, np.array(A2_vals), rcond=None)
    print(f"  Fit A₂ = a·k²c + b/c:  a={params2[0]:.10f}, b={params2[1]:.10f}")
    for k in range(1,6):
        pred = params2[0]*k**2*ck_vals[k-1] + params2[1]/ck_vals[k-1]
        print(f"    k={k}: pred={pred:+.10f}, actual={A2_vals[k-1]:+.10f}, gap={abs(pred-A2_vals[k-1]):.2e}")
    
    # Fit: A₂ = a·k²c + b·(k+1)(k+3)/(8c) + d  (3-param, A₁-inspired)
    X3 = np.array([[k**2 * ck_vals[k-1], (k+1)*(k+3)/(8*ck_vals[k-1]), 1] for k in range(1,6)])
    params3, _, _, _ = np.linalg.lstsq(X3, np.array(A2_vals), rcond=None)
    print(f"\n  Fit A₂ = a·k²c + b·(k+1)(k+3)/(8c) + d:")
    print(f"    a={params3[0]:.10f}, b={params3[1]:.10f}, d={params3[2]:.10f}")
    for k in range(1,6):
        pred = params3[0]*k**2*ck_vals[k-1] + params3[1]*(k+1)*(k+3)/(8*ck_vals[k-1]) + params3[2]
        print(f"    k={k}: pred={pred:+.10f}, actual={A2_vals[k-1]:+.10f}, gap={abs(pred-A2_vals[k-1]):.2e}")
    
    # Richer fit with more polynomial structure
    # A₂ = a·k²c + b·k³/c + d·k²/c + e·k/c + f/c + g
    X6 = np.array([
        [k**2*ck_vals[k-1], k**3/ck_vals[k-1], k**2/ck_vals[k-1], 
         k/ck_vals[k-1], 1/ck_vals[k-1], 1] for k in range(1,6)
    ])
    params6, _, _, _ = np.linalg.lstsq(X6, np.array(A2_vals), rcond=None)
    print(f"\n  Fit A₂ = a·k²c + (b·k³+d·k²+e·k+f)/c + g:")
    print(f"    a={params6[0]:.8f}, poly/c = ({params6[1]:.4f}k³ + {params6[2]:.4f}k² + {params6[3]:.4f}k + {params6[4]:.4f})/c + {params6[5]:.8f}")
    for k in range(1,6):
        pred = sum(params6[j]*X6[k-1,j] for j in range(6))
        print(f"    k={k}: pred={pred:+.10f}, actual={A2_vals[k-1]:+.10f}, gap={abs(pred-A2_vals[k-1]):.2e}")
    
    print(f"\nTotal runtime: {time.time()-t0:.1f}s")
    print("=== DONE ===")
