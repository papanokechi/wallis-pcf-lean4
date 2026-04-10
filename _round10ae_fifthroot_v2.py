"""
Round 10AE: Fifth-root (alpha=4) numerical verification
Product: prod_{n>=1} (1-q^n)^{-n^3}, D(s) = zeta(s-3), pole at alpha=4
Growth: f(n) ~ C * n^kappa * exp(c * n^{4/5})
d = 4/5, p = 5
Recurrence: n*f(n) = sum_{j=1}^{n} sigma_4(j) * f(n-j)
"""
import time
import numpy as np

def compute_sigma4_table(N):
    """sigma_4(m) = sum_{d|m} d^4 for m=1..N."""
    sigma = [0] * (N + 1)
    for d in range(1, N + 1):
        d4 = d ** 4
        for m in range(d, N + 1, d):
            sigma[m] += d4
    return sigma

def compute_partitions(N):
    """Exact integer coefficients of prod(1-q^n)^{-n^3} up to q^N."""
    print(f"Computing sigma_4 table up to N={N}...")
    sigma = compute_sigma4_table(N)
    
    f = [0] * (N + 1)
    f[0] = 1
    
    print(f"Computing partition coefficients (alpha=4)...")
    t0 = time.time()
    ck = max(1, N // 10)
    
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += sigma[j] * f[n - j]
        assert s % n == 0, f"n={n}: not divisible"
        f[n] = s // n
        
        if n % ck == 0:
            el = time.time() - t0
            dig = len(str(abs(f[n])))
            eta = (N - n) / (n / el) if el > 0 else 0
            print(f"  n={n}/{N}: {dig} digits, {el:.0f}s elapsed, ~{eta:.0f}s remaining")
    
    dig = len(str(abs(f[N])))
    print(f"  Done: f({N}) has {dig} digits in {time.time()-t0:.1f}s")
    return f

def extract_L(f, c, kappa, d, points):
    """Extract L by subtracting known fractional-power terms from R_m.
    
    For d=4/5, p=5: R_m = 1 + a*m^{-1/5} + a^2/2*m^{-2/5} + a^3/6*m^{-3/5} 
                         + a^4/24*m^{-4/5} + L*m^{-1} + ...
    where a = cd = 4c/5 and L = a^5/120 + kappa.
    Subtract the first 4 terms, multiply by m to get L_est -> L.
    """
    import mpmath as mp
    mp.mp.dps = 50
    
    a = mp.mpf(c) * mp.mpf(d)  # cd = 4c/5
    
    results = []
    for m in points:
        R = mp.mpf(f[m]) / mp.mpf(f[m - 1])
        m_mp = mp.mpf(m)
        
        # Subtract the 4 fractional-power terms from E_m
        inv_fifth = m_mp ** (mp.mpf(-1)/5)  # m^{-1/5}
        sub = (a * inv_fifth 
               + a**2/2 * inv_fifth**2 
               + a**3/6 * inv_fifth**3 
               + a**4/24 * inv_fifth**4)
        
        L_est = float(m_mp * (R - 1 - sub))
        results.append((m, float(R), L_est))
    return results

def richardson_4pt(pts, delta=0.2):
    """4-point Richardson extrapolation assuming error ~ m^{-delta}."""
    ms = np.array([p[0] for p in pts], dtype=float)
    Ls = np.array([p[1] for p in pts], dtype=float)
    A = np.zeros((4, 4))
    for i in range(4):
        A[i, 0] = 1.0
        for j in range(1, 4):
            A[i, j] = ms[i] ** (-j * delta)
    try:
        return np.linalg.solve(A, Ls)[0]
    except:
        return None

def main():
    from math import gamma as Gamma, pi
    
    print("=" * 70)
    print("  ROUND 10AE: Fifth-Root (alpha=4) Numerical Verification")
    print("  Product: prod(1-q^n)^{-n^3}, D(s) = zeta(s-3)")
    print("  Growth: d = 4/5, p = 5")
    print("=" * 70)
    
    alpha = 4
    zeta5 = 1.0369277551433699
    zeta_neg3 = 1.0 / 120.0  # zeta(-3) = 1/120
    d = alpha / (alpha + 1)  # 4/5
    c = (1 + 1/alpha) * (Gamma(alpha + 1) * zeta5) ** (1/(alpha+1))
    kappa = (zeta_neg3 - 1 - alpha/2) / (1 + alpha)
    p = 5
    L_pred = (c * d) ** p / Gamma(p + 1) + kappa
    
    print(f"\nParameters:")
    print(f"  alpha = {alpha}, d = {d}, c = {c:.10f}, kappa = {kappa:.10f}")
    print(f"  p = {p}")
    print(f"\nPredictions:")
    print(f"  (cd)^5/5! = {(c*d)**5/120:.10f}")
    print(f"  L_4 = {L_pred:.10f}")
    print(f"  Reviewer: 256*c^5/93750 = {256*c**5/93750 + kappa:.10f} (match: {abs(L_pred - 256*c**5/93750 - kappa) < 1e-12})")
    print()
    
    N = 10000
    t0 = time.time()
    f = compute_partitions(N)
    print(f"Total computation: {time.time()-t0:.1f}s\n")
    
    test_points = [200, 500, 1000, 2000, 3000, 4000, 5000, 7000, 10000]
    test_points = [m for m in test_points if m <= N]
    
    print("Ratio extraction (R_m / (E_m * P_m) - 1) * m -> L:")
    print(f"  {'m':>6}  {'L_est':>14}  {'gap':>12}  {'rel_err':>10}")
    print("  " + "-" * 50)
    
    results = extract_L(f, c, kappa, d, test_points)
    for m, R, L_est in results:
        gap = L_est - L_pred
        rel = abs(gap / L_pred) * 100
        print(f"  {m:>6}  {L_est:>14.8f}  {gap:>+12.8f}  {rel:>8.4f}%")
    
    print("\n4-point Richardson (error ~ m^{-1/5}):")
    rico_sets = [
        [500, 1000, 2000, 3000],
        [1000, 2000, 3000, 5000],
        [2000, 3000, 5000, 7000],
        [3000, 5000, 7000, 10000],
        [2000, 4000, 7000, 10000],
        [5000, 7000, 9000, 10000],
    ]
    for pts in rico_sets:
        pts_f = [p for p in pts if p <= N]
        if len(pts_f) < 4:
            continue
        data = [(m, L) for m, R, L in results if m in pts_f]
        if len(data) == 4:
            L_r = richardson_4pt(data, delta=1/5)
            if L_r is not None:
                gap = L_r - L_pred
                rel = abs(gap / L_pred) * 100
                print(f"  ({', '.join(str(p) for p in pts_f)}) -> L = {L_r:.8f}, gap = {gap:+.8f}, err = {rel:.4f}%")
    
    print(f"\nPredicted L_4 = {L_pred:.10f}")

if __name__ == "__main__":
    main()
