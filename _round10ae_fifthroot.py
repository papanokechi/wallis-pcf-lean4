"""
Round 10AE: Fifth-root (alpha=4) numerical verification
Product: prod_{n>=1} (1-q^n)^{-n^3}, D(s) = zeta(s-3), pole at alpha=4
Growth: f(n) ~ C * n^kappa * exp(c * n^{4/5})
d = 4/5, p = 5

Meinardus parameters:
  c = (5/4) * (Gamma(4)*zeta(5))^{1/5} = (5/4) * (6*zeta(5))^{1/5}
  kappa = (D(0) - 1 - alpha/2) / (1 + alpha) = (zeta(-3) - 3) / 5 = (1/120 - 3)/5
  L_4 = (c*d)^5 / 5! + kappa = (4c/5)^5 / 120 + kappa

Recurrence: n*f(n) = sum_{j=1}^{n} sigma_4(j) * f(n-j)
where sigma_4(m) = sum_{d|m} d^4 * 1 = sum_{d|m} a_d * d
Wait: a_n = n^3, so the coefficient of q^m in q*d/dq log F is sum_{n|m} n*a_n = sum_{d|m} d*d^3 = sum_{d|m} d^4 = sigma_4(m).
"""
import time
import sys
from math import log, sqrt, pi
from functools import lru_cache

def compute_sigma4_table(N):
    """Compute sigma_4(m) = sum_{d|m} d^4 for m=1..N."""
    sigma = [0] * (N + 1)
    for d in range(1, N + 1):
        d4 = d * d * d * d
        for m in range(d, N + 1, d):
            sigma[m] += d4
    return sigma

def compute_fifth_root_partitions(N):
    """Compute coefficients of prod(1-q^n)^{-n^3} up to q^N using exact integers."""
    print(f"Computing sigma_4 table up to N={N}...")
    t0 = time.time()
    sigma = compute_sigma4_table(N)
    print(f"  sigma_4 done in {time.time()-t0:.1f}s")
    
    f = [0] * (N + 1)
    f[0] = 1
    
    print(f"Computing partition coefficients (alpha=4)...")
    t1 = time.time()
    checkpoint = max(1, N // 20)
    
    for n in range(1, N + 1):
        s = 0
        for j in range(1, n + 1):
            s += sigma[j] * f[n - j]
        f[n] = s // n  # must be exact integer
        if s % n != 0:
            print(f"  WARNING: n={n}, sum not divisible! remainder={s % n}")
            f[n] = s / n  # fallback (shouldn't happen)
        
        if n % checkpoint == 0:
            elapsed = time.time() - t1
            digits = len(str(abs(f[n]))) if f[n] != 0 else 0
            rate = n / elapsed if elapsed > 0 else 0
            eta = (N - n) / rate if rate > 0 else 0
            print(f"  n={n}/{N}: {digits} digits, {elapsed:.0f}s elapsed, ~{eta:.0f}s remaining")
    
    elapsed = time.time() - t1
    digits = len(str(abs(f[N]))) if f[N] != 0 else 0
    print(f"  Done: f({N}) has {digits} digits, total {elapsed:.0f}s")
    
    return f

def extract_L(f, c, kappa, d, points):
    """Extract L from ratio residuals using Richardson extrapolation."""
    # R_m = f(m)/f(m-1)
    # R_m ~ 1 + c*d/m^{1/p} + ... + L/m + ...  where 1/p = 1-d
    # Residual: res_m = m * (R_m - 1 - cd*m^{-(1-d)})  
    # But this is too crude for p=5 - need to subtract more terms from E_m expansion
    
    p = 1.0 / (1.0 - d)  # p = 5
    cd = c * d
    
    # For E_m = exp(c[m^d - (m-1)^d]), expand more terms
    # m^d - (m-1)^d = d/m^{1-d} + d(1-d)/(2m^{2-d}) + d(1-d)(2-d)/(6m^{3-d}) + ...
    # We need to subtract the E_m and P_m contributions up to m^{-1-epsilon}
    # to isolate L at m^{-1}
    
    # Better approach: just compute R_m - 1 directly, 
    # then Richardson-extrapolate the sequence m*(R_m - 1 - sum_of_lower_terms) -> L
    
    # For p=5, the E_m expansion contributes at m^{-1/5}, m^{-2/5}, m^{-3/5}, m^{-4/5}
    # before hitting m^{-1}. So we need:
    # e1 = cd = c*4/5
    # e2 = cd(1-d)/2 = c*4/5 * 1/5 / 2 = 2c/25
    # e3 = cd(1-d)(2-d)/6 = c*4/5 * 1/5 * 6/5 / 6 = 4c/125
    # e4 = cd(1-d)(2-d)(3-d)/24 = c*4/5 * 1/5 * 6/5 * 11/5 / 24
    #    = c * 4*1*6*11 / (5^4 * 24) = c * 264 / 15000 = 11c/625
    # Wait, that doesn't look right. Let me redo.
    
    # (m-1)^d = m^d (1 - 1/m)^d
    # (1-x)^d = 1 - dx + d(d-1)/2 x^2 - d(d-1)(d-2)/6 x^3 + d(d-1)(d-2)(d-3)/24 x^4 - ...
    # m^d - (m-1)^d = m^d [1 - (1-1/m)^d]
    #   = m^d [d/m - d(d-1)/(2m^2) + d(d-1)(d-2)/(6m^3) - d(d-1)(d-2)(d-3)/(24m^4) + ...]
    #   = d*m^{d-1} - d(d-1)/(2)*m^{d-2} + d(d-1)(d-2)/(6)*m^{d-3} - d(d-1)(d-2)(d-3)/(24)*m^{d-4} + ...
    
    # With d=4/5:
    # a1 = d = 4/5 (power: d-1 = -1/5)
    # a2 = -d(d-1)/2 = -(4/5)(-1/5)/2 = 4/50 = 2/25 (power: d-2 = -6/5, wait d-2 = -1.2? No, d-2 = 4/5-2 = -6/5)
    # Hmm, these are at m^{-1/5}, m^{-6/5}, m^{-11/5}, ... that doesn't make sense for reaching m^{-1}.
    
    # Actually, I need to think about this differently. E_m = exp(c * [m^d - (m-1)^d]).
    # Let u = c*[m^d - (m-1)^d]. Then:
    # u = c*d*m^{d-1} - c*d*(d-1)/(2)*m^{d-2} + ...
    # For d=4/5, d-1 = -1/5, d-2 = -6/5, d-3 = -11/5, ...
    # u = 4c/(5 m^{1/5}) + 2c/(25 m^{6/5}) + ... 
    # So u ~ 4c/(5 m^{1/5}) to leading order.
    
    # E_m = exp(u) = 1 + u + u^2/2 + u^3/6 + u^4/24 + u^5/120 + ...
    # u^1 ~ m^{-1/5}
    # u^2 ~ m^{-2/5}
    # u^3 ~ m^{-3/5}
    # u^4 ~ m^{-4/5}
    # u^5 ~ m^{-1}   <-- this is the "5-fold resonance"
    
    # So R_m ~ E_m * P_m * S_m ~ exp(u) * (1 + kappa/m + ...) * (1 + O(m^{-6/5}))
    # The m^{-1} term in R_m comes from:
    #   - u^5/120 (the 5-fold resonance from E_m)
    #   - cross terms from u * u^4/24, etc.
    #   - kappa/m from P_m
    # But actually u^5/120 gives (cd)^5 m^{-1} / 120 only from the leading part of u.
    # There are also contributions from the sub-leading parts of u at intermediate orders.
    
    # Richardson approach: define res(m) such that res(m) -> L as m -> infinity.
    # The simplest: compute R_m exactly (as float), then define
    # res(m) = m * [R_m - 1 - a1*m^{-1/5} - a2*m^{-2/5} - a3*m^{-3/5} - a4*m^{-4/5}]
    # where a1,...,a4 are the known E_m expansion coefficients.
    
    # For this, I need the exact expansion of E_m*P_m at orders m^{-1/5} through m^{-4/5}.
    
    # Simpler approach for now: 4-point Richardson on raw L estimates.
    # L_raw(m) = m * (R_m / E_m / P_m - 1) is hard because we need E_m precisely.
    # 
    # Alternative: just do Richardson on the sequence
    # xi(m) = m * (R_m - 1 - cd*m^{-(1-d)}) - but this still has garbage from m^{-2/5} etc.
    # 
    # Best: use the FULL asymptotic expansion to subtract all terms below m^{-1},
    # then read off L directly.
    
    # Actually, the cleanest approach (same as used for 4th-root) is:
    # Compute log(R_m) instead, since log(E_m * P_m * S_m) = log(E_m) + log(P_m) + log(S_m)
    # log(E_m) = c[m^d - (m-1)^d] = known expansion
    # log(P_m) = kappa * log(m/(m-1)) = kappa * [1/m + 1/(2m^2) + ...]
    # log(S_m) = O(m^{-(1+d)}) = O(m^{-9/5})
    # So log(R_m) = c[m^d - (m-1)^d] + kappa/m + O(m^{-9/5})
    # 
    # Wait, but L is in R_m, not log(R_m). Let me reconsider.
    # R_m = exp(log(E_m) + log(P_m) + log(S_m))
    # log(R_m) = c[m^d-(m-1)^d] + kappa*log(m/(m-1)) + log(S_m)
    # 
    # Expanding c[m^d-(m-1)^d]:
    # = c*d/m^{1/p} - c*d*(d-1)/(2*m^{1+1/p}) + ...
    # For d=4/5, 1/p=1/5: = 4c/5 * m^{-1/5} + 2c/25 * m^{-6/5} + ...
    # These are at m^{-1/5} and m^{-6/5}. So the ONLY sub-leading integer power is from:
    # exp(u) at m^{-1} through the 5-fold resonance of the m^{-1/5} term.
    # All other terms in the exponent are at m^{-6/5}, m^{-11/5}, etc.
    # Plus kappa/m.
    
    # So: log(R_m) = 4c/(5m^{1/5}) + 2c/(25m^{6/5}) + ... + kappa/m + kappa/(2m^2) + ... + O(m^{-9/5})
    # R_m = exp(log(R_m))
    # At m^{-1}: coefficient is kappa + (4c/5)^5 / (5! * ... ) 
    # Wait, I need to be more careful. Let u = sum of all the exponent terms.
    # Then R_m = e^u = 1 + u + u^2/2 + ...
    # u = a*m^{-1/5} + b*m^{-6/5} + kappa/m + ...
    # where a = 4c/5, b = 2c/25
    
    # u^5/5! at m^{-1}: only (a*m^{-1/5})^5 / 120 = a^5/(120*m) = (4c/5)^5/(120m)
    # u^4/4! * (kappa/m): this is O(m^{-4/5-1}) = O(m^{-9/5}), below m^{-1}
    # So the m^{-1} coefficient is: (4c/5)^5/120 + kappa 
    # Plus cross terms from u^5: 5*(a*m^{-1/5})^4 * (b*m^{-6/5}) / 120 = 5*a^4*b/(120*m^{10/5}) 
    # = a^4*b/(24*m^2) which is at m^{-2}, not m^{-1}.
    # Hmm wait, 4*(-1/5) + (-6/5) = -4/5 - 6/5 = -10/5 = -2. Right.
    
    # So at m^{-1}, the only contributions are:
    # From u^5/5!: a^5/120 where a = 4c/5  -> (4c/5)^5/120 = 1024c^5/(3125*120) = 1024c^5/375000
    # From u: kappa (the kappa/m term directly)
    # That's it! 
    # L = (4c/5)^5/120 + kappa = (cd)^5/120 + kappa

    # Richardson extrapolation: subtract the known lower-order terms.
    # Define residual(m) = R_m - [exp(a*m^{-1/5})*(m/(m-1))^kappa]
    #                     ~ L/m + O(m^{-6/5})
    # Then m*residual(m) -> L with error O(m^{-1/5})
    # 4-point Richardson with power -1/5 error should converge nicely.
    
    results = []
    for m in points:
        R = float(f[m]) / float(f[m-1])
        
        # Subtract the full exponential factor
        m_d = m ** d
        m1_d = (m - 1) ** d
        E = __import__('math').exp(c * (m_d - m1_d))
        P = (m / (m - 1)) ** kappa
        
        residual = R / (E * P) - 1.0
        L_est = m * residual
        results.append((m, R, L_est))
    
    return results

def richardson_4pt(pts, delta=0.2):
    """4-point Richardson extrapolation assuming error ~ m^{-delta}."""
    # pts = [(m1, L1), (m2, L2), (m3, L3), (m4, L4)]
    # L_i = L + A * m_i^{-delta} + ...
    # Use 4-point extrapolation to eliminate the leading error term
    
    import numpy as np
    ms = np.array([p[0] for p in pts], dtype=float)
    Ls = np.array([p[1] for p in pts], dtype=float)
    
    # Solve L + A*m^{-d1} + B*m^{-d2} + C*m^{-d3} = L_i for each i
    # With d1=delta, d2=2*delta, d3=3*delta
    n = len(pts)
    A = np.zeros((n, n))
    for i in range(n):
        A[i, 0] = 1.0  # L
        for j in range(1, n):
            A[i, j] = ms[i] ** (-j * delta)
    
    try:
        coeffs = np.linalg.solve(A, Ls)
        return coeffs[0]
    except:
        return None

def main():
    print("=" * 70)
    print("  ROUND 10AE: Fifth-Root (alpha=4) Numerical Verification")
    print("  Product: prod(1-q^n)^{-n^3}, D(s) = zeta(s-3)")
    print("  Growth: d = 4/5, p = 5")
    print("=" * 70)
    print()
    
    # Meinardus parameters
    from math import gamma as Gamma
    
    zeta5 = 1.0369277551433699  # zeta(5)
    zeta_neg3 = 1.0 / 120.0    # zeta(-3) = B_4/4 = -1/120... wait
    # B_4 = -1/30, zeta(-3) = -B_4/4 = 1/120
    # Actually: zeta(-n) = (-1)^n * B_{n+1}/(n+1) for n >= 1
    # zeta(-3) = (-1)^3 * B_4/4 = -(-1/30)/4 = 1/120
    zeta_neg3 = 1.0 / 120.0
    
    alpha = 4
    A_res = 1  # residue of D(s) = zeta(s-3) at s=4
    d = alpha / (alpha + 1)  # 4/5
    
    c = (1 + 1/alpha) * (A_res * Gamma(alpha) * zeta5) ** (1/(alpha+1))
    # = (5/4) * (6 * zeta(5))^{1/5}
    
    kappa = (zeta_neg3 - 1 - alpha/2) / (1 + alpha)
    # = (1/120 - 3) / 5
    
    p = 5
    L_pred = (c * d) ** p / Gamma(p + 1) + kappa
    # Note: Gamma(6) = 120 = 5!
    
    print(f"Parameters:")
    print(f"  alpha = {alpha}")
    print(f"  d     = {d} = 4/5")
    print(f"  c     = {c:.10f}")
    print(f"  kappa = {kappa:.10f}")
    print(f"  zeta(-3) = {zeta_neg3}")
    print(f"  p     = {p}")
    print()
    print(f"Predictions:")
    print(f"  (cd)^5 / 5! = {(c*d)**5 / 120:.10f}")
    print(f"  L_4 = (cd)^5/5! + kappa = {L_pred:.10f}")
    print()
    
    # Reviewer's formula: 256*c^5/93750 + kappa
    L_reviewer = 256 * c**5 / 93750 + kappa
    print(f"  Reviewer formula: 256*c^5/93750 + kappa = {L_reviewer:.10f}")
    print(f"  Match: {abs(L_pred - L_reviewer) < 1e-12}")
    print()
    
    # Compute partition function
    N = 3000
    t0 = time.time()
    f = compute_fifth_root_partitions(N)
    total_time = time.time() - t0
    print(f"\nTotal computation time: {total_time:.1f}s")
    print()
    
    # Extract L at various points
    test_points = [200, 300, 500, 700, 1000, 1500, 2000, 2500, 3000]
    test_points = [m for m in test_points if m <= N]
    
    print("Ratio extraction:")
    print(f"  {'m':>6}  {'R_m':>16}  {'L_est':>14}  {'gap':>12}  {'rel_err':>10}")
    print("  " + "-" * 72)
    
    results = extract_L(f, c, kappa, d, test_points)
    for m, R, L_est in results:
        gap = L_est - L_pred
        rel = abs(gap / L_pred) * 100 if L_pred != 0 else 0
        print(f"  {m:>6}  {R:>16.12f}  {L_est:>14.8f}  {gap:>+12.8f}  {rel:>8.4f}%")
    
    # Richardson extrapolation
    print("\n4-point Richardson extrapolation (error ~ m^{-1/5}):")
    
    rico_sets = [
        [200, 500, 1000, 2000],
        [300, 700, 1500, 3000],
        [500, 1000, 2000, 3000],
        [1000, 1500, 2000, 3000],
    ]
    
    for pts in rico_sets:
        pts_filtered = [p for p in pts if p <= N]
        if len(pts_filtered) < 4:
            continue
        L_data = []
        for m in pts_filtered:
            for mm, R, L_est in results:
                if mm == m:
                    L_data.append((m, L_est))
                    break
        if len(L_data) == 4:
            L_rich = richardson_4pt(L_data, delta=1/5)
            if L_rich is not None:
                gap = L_rich - L_pred
                rel = abs(gap / L_pred) * 100
                print(f"  ({', '.join(str(p) for p in pts_filtered)}) -> L = {L_rich:.8f}, gap = {gap:+.8f}, error = {rel:.4f}%")
    
    print(f"\nPredicted L_4 = {L_pred:.10f}")
    print("Done.")

if __name__ == "__main__":
    main()
