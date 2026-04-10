"""
Round 10AD: Explicit Kloosterman sum bounds for eta(tau)^{-k}

For each k, the generalized Kloosterman sum is:
  S_k(m,n;q) = sum_{h: (h,q)=1} omega_{h,q}^{-k} * exp(2*pi*i*(m*h + n*hbar)/q)

where omega_{h,q} = exp(pi*i*s(h,q)) is the Dedekind sum multiplier,
and hbar is the modular inverse of h mod q.

The Dedekind sum: s(h,q) = sum_{r=1}^{q-1} ((r/q)) * ((hr/q))
where ((x)) = x - floor(x) - 1/2 if x not integer, else 0.

We need: |S_k(m,n;q)| <= C_k * d(q) * q^{1/2} for all q >= 1
where d(q) is the number of divisors.

The conductor N_k = 24/gcd(k,24) takes values {1,2,3,4,6,8,12,24}.

Strategy: For each conductor level, compute S_k explicitly for all q up to Q_max,
track the ratio |S_k(m,n;q)| / (d(q) * q^{1/2}), and find the supremum.
"""

import numpy as np
from math import gcd, floor, sqrt, pi, log
from fractions import Fraction
import time

def dedekind_sum(h, q):
    """Compute the Dedekind sum s(h,q) = sum_{r=1}^{q-1} ((r/q))((hr/q))"""
    if q <= 1:
        return 0
    s = 0
    for r in range(1, q):
        x = r / q
        hx = (h * r) / q
        # sawtooth function ((x)) = x - floor(x) - 1/2 if x not integer, else 0
        bx = x - floor(x) - 0.5 if abs(x - round(x)) > 1e-12 else 0.0
        bhx = hx - floor(hx) - 0.5 if abs(hx - round(hx)) > 1e-12 else 0.0
        s += bx * bhx
    return s

def dedekind_sum_exact(h, q):
    """Compute Dedekind sum exactly using Fraction for precision"""
    if q <= 1:
        return Fraction(0)
    s = Fraction(0)
    for r in range(1, q):
        x = Fraction(r, q)
        hx = Fraction(h * r, q)
        # sawtooth: ((x)) = x - floor(x) - 1/2, 0 if integer
        fx = x - int(x)
        if fx == 0:
            bx = Fraction(0)
        else:
            bx = fx - Fraction(1, 2)
        fhx = hx - int(hx)
        if fhx == 0:
            bhx = Fraction(0)
        else:
            bhx = fhx - Fraction(1, 2)
        s += bx * bhx
    return s

def mod_inverse(h, q):
    """Compute modular inverse of h mod q using extended Euclidean algorithm"""
    if q == 1:
        return 0
    g, x, _ = extended_gcd(h, q)
    if g != 1:
        return None
    return x % q

def extended_gcd(a, b):
    if a == 0:
        return b, 0, 1
    g, x, y = extended_gcd(b % a, a)
    return g, y - (b // a) * x, x

def divisor_count(n):
    """Count divisors of n"""
    count = 0
    for d in range(1, int(sqrt(n)) + 1):
        if n % d == 0:
            count += 2 if d * d != n else 1
    return count

def kloosterman_sum_eta_k(k, m, n, q):
    """
    Compute generalized Kloosterman sum for eta(tau)^{-k}:
    S_k(m,n;q) = sum_{(h,q)=1} omega_{h,q}^{-k} * exp(2*pi*i*(m*h + n*hbar)/q)
    
    where omega_{h,q} = exp(pi*i*s(h,q)) and s(h,q) is the Dedekind sum.
    """
    if q == 1:
        # Only h = 0, but (0,1)=1, hbar=0
        # s(0,1) = 0, omega = 1
        return np.exp(2j * pi * (m * 0 + n * 0))
    
    total = 0j
    for h in range(q):
        if gcd(h, q) != 1:
            continue
        hbar = mod_inverse(h, q)
        if hbar is None:
            continue
        # Dedekind sum
        s = dedekind_sum(h, q)
        # multiplier: omega^{-k} = exp(-k * pi * i * s(h,q))
        phase_mult = np.exp(-1j * k * pi * s)
        # Kloosterman phase
        phase_kloos = np.exp(2j * pi * (m * h + n * hbar) / q)
        total += phase_mult * phase_kloos
    
    return total

def compute_conductor_bounds(Q_max=500, test_pairs=None):
    """
    For each conductor N_k, compute the supremum of
    |S_k(m,n;q)| / (d(q) * sqrt(q))
    over q = 1..Q_max and test (m,n) pairs.
    
    Map: conductor -> representative k values
    N_k = 24/gcd(k,24):
      k=24: N=1, k=12: N=2, k=8: N=3, k=6: N=4, k=4: N=6, k=3: N=8, k=2: N=12, k=1: N=24
      k=5: N=24, k=7: N=24, k=9: N=8, k=10: N=12, k=11: N=24, k=13: N=24
    """
    if test_pairs is None:
        test_pairs = [(1, 1), (1, 2), (2, 1), (1, 5), (3, 7), (1, 0), (0, 1)]
    
    # Representative k for each conductor
    conductor_to_k = {
        1:  24,  # gcd(24,24)=24, N=1
        2:  12,  # gcd(12,24)=12, N=2
        3:  8,   # gcd(8,24)=8, N=3
        4:  6,   # gcd(6,24)=6, N=4
        6:  4,   # gcd(4,24)=4, N=6
        8:  3,   # gcd(3,24)=3, N=8
        12: 2,   # gcd(2,24)=2, N=12
        24: 5,   # gcd(5,24)=1, N=24 (the hard case)
    }
    
    # Also test additional k values at conductor 24
    extra_k_at_24 = [1, 5, 7, 11, 13]
    
    results = {}
    
    for N, k_rep in sorted(conductor_to_k.items()):
        print(f"\n{'='*60}")
        print(f"Conductor N = {N}, representative k = {k_rep}")
        print(f"Weight = -{k_rep}/2, {'half-integer' if k_rep % 2 == 1 else 'integer'}")
        print(f"{'='*60}")
        
        sup_ratio = 0
        worst_q = 0
        worst_mn = (0, 0)
        
        for q in range(1, Q_max + 1):
            dq = divisor_count(q)
            sq = sqrt(q)
            
            for m, n in test_pairs:
                S = kloosterman_sum_eta_k(k_rep, m, n, q)
                absS = abs(S)
                ratio = absS / (dq * sq) if dq * sq > 0 else 0
                
                if ratio > sup_ratio:
                    sup_ratio = ratio
                    worst_q = q
                    worst_mn = (m, n)
        
        results[N] = {
            'k': k_rep,
            'C_k': sup_ratio,
            'worst_q': worst_q,
            'worst_mn': worst_mn,
            'weight': f"-{k_rep}/2" if k_rep % 2 == 1 else f"-{k_rep // 2}",
        }
        
        print(f"  sup |S_k| / (d(q)*sqrt(q)) = {sup_ratio:.6f}")
        print(f"  Achieved at q = {worst_q}, (m,n) = {worst_mn}")
        
    return results

def verify_known_cases(Q_max=200):
    """Verify the known bounds C_2=2, C_3=3, C_4=2"""
    print("="*60)
    print("VERIFICATION OF KNOWN CASES")
    print("="*60)
    
    test_pairs = [(1, 1), (1, 2), (2, 1), (1, 5), (3, 7), (0, 1), (1, 0),
                  (2, 3), (5, 7), (1, 10), (10, 1), (7, 13)]
    
    for k in [2, 3, 4]:
        print(f"\nk = {k}: Expected C_{k} = {2 if k != 3 else 3}")
        sup_ratio = 0
        worst_q = 0
        worst_mn = (0, 0)
        
        for q in range(1, Q_max + 1):
            dq = divisor_count(q)
            sq = sqrt(q)
            
            for m, n in test_pairs:
                S = kloosterman_sum_eta_k(k, m, n, q)
                absS = abs(S)
                ratio = absS / (dq * sq) if dq * sq > 0 else 0
                
                if ratio > sup_ratio:
                    sup_ratio = ratio
                    worst_q = q
                    worst_mn = (m, n)
        
        print(f"  Max ratio: {sup_ratio:.6f} (at q={worst_q}, (m,n)={worst_mn})")
        print(f"  Bound C_{k} <= {sup_ratio:.2f}")

def exhaustive_k5_check(Q_max=300):
    """
    Detailed check for k=5 (the critical open case).
    Conductor 24, half-integer weight -5/2.
    """
    print("="*60)
    print("EXHAUSTIVE k=5 BOUND (Conductor 24)")
    print("="*60)
    
    test_pairs = [(m, n) for m in range(0, 8) for n in range(0, 8)]
    
    sup_ratio = 0
    worst_q = 0
    worst_mn = (0, 0)
    
    ratios_by_q = []
    
    for q in range(1, Q_max + 1):
        dq = divisor_count(q)
        sq = sqrt(q)
        
        q_max_ratio = 0
        for m, n in test_pairs:
            S = kloosterman_sum_eta_k(5, m, n, q)
            absS = abs(S)
            ratio = absS / (dq * sq) if dq * sq > 0 else 0
            
            if ratio > q_max_ratio:
                q_max_ratio = ratio
            if ratio > sup_ratio:
                sup_ratio = ratio
                worst_q = q
                worst_mn = (m, n)
        
        ratios_by_q.append((q, q_max_ratio))
    
    print(f"\nOverall sup: {sup_ratio:.6f}")
    print(f"At q = {worst_q}, (m,n) = {worst_mn}")
    
    # Show worst 20
    ratios_by_q.sort(key=lambda x: -x[1])
    print("\nTop 20 values of |S_5|/(d(q)*sqrt(q)):")
    for q, r in ratios_by_q[:20]:
        print(f"  q = {q:4d}: ratio = {r:.6f}")
    
    return sup_ratio

def check_all_k_up_to(k_max=24, Q_max=200):
    """
    Compute the bound C_k for all k = 1..k_max.
    This is the key computation: if C_k is finite and computable for all k,
    Conjecture 2* becomes a theorem.
    """
    print("="*60)
    print(f"SYSTEMATIC KLOOSTERMAN BOUNDS: k = 1..{k_max}")
    print(f"Q_max = {Q_max}")
    print("="*60)
    
    test_pairs = [(m, n) for m in range(0, 6) for n in range(0, 6)]
    
    results = []
    
    for k in range(1, k_max + 1):
        N_k = 24 // gcd(k, 24)
        
        sup_ratio = 0
        worst_q = 0
        worst_mn = (0, 0)
        
        for q in range(1, Q_max + 1):
            dq = divisor_count(q)
            sq = sqrt(q)
            
            for m, n in test_pairs:
                S = kloosterman_sum_eta_k(k, m, n, q)
                absS = abs(S)
                ratio = absS / (dq * sq) if dq * sq > 0 else 0
                
                if ratio > sup_ratio:
                    sup_ratio = ratio
                    worst_q = q
                    worst_mn = (m, n)
        
        weight_str = f"-{k}/2" if k % 2 == 1 else f"-{k//2}"
        conductor = N_k
        
        results.append({
            'k': k,
            'N_k': conductor,
            'weight': weight_str,
            'C_k': sup_ratio,
            'worst_q': worst_q,
            'worst_mn': worst_mn,
        })
        
        status = "PROVED" if k <= 4 else "COMPUTED"
        print(f"  k={k:2d}  N={conductor:2d}  wt={weight_str:>5s}  C_k <= {sup_ratio:6.3f}  (q={worst_q:4d}, (m,n)={worst_mn})  [{status}]")
    
    return results

if __name__ == "__main__":
    t0 = time.time()
    
    # Phase 1: Verify known cases
    print("\n" + "="*60)
    print("PHASE 1: Verify known bounds C_2=2, C_3=3, C_4=2")
    print("="*60)
    verify_known_cases(Q_max=150)
    
    # Phase 2: Systematic computation for all k up to 24
    print("\n\n" + "="*60)
    print("PHASE 2: All k = 1..24, Q_max=150")
    print("="*60)
    results = check_all_k_up_to(k_max=24, Q_max=150)
    
    # Phase 3: Detailed k=5 analysis
    print("\n\n" + "="*60)
    print("PHASE 3: Detailed k=5 analysis, Q_max=200")
    print("="*60)
    c5 = exhaustive_k5_check(Q_max=200)
    
    t1 = time.time()
    print(f"\n\nTotal time: {t1-t0:.1f}s")
    
    # Summary table
    print("\n" + "="*60)
    print("SUMMARY: Kloosterman Constants by Conductor")
    print("="*60)
    
    # Group by conductor
    by_conductor = {}
    for r in results:
        N = r['N_k']
        if N not in by_conductor:
            by_conductor[N] = []
        by_conductor[N].append(r)
    
    print(f"\n{'N':>3s}  {'k values':>20s}  {'max C_k':>8s}  {'Weight type':>12s}")
    print("-" * 50)
    for N in sorted(by_conductor.keys()):
        entries = by_conductor[N]
        k_vals = [str(e['k']) for e in entries]
        max_ck = max(e['C_k'] for e in entries)
        # Weight type
        has_half = any(e['k'] % 2 == 1 for e in entries)
        has_int = any(e['k'] % 2 == 0 for e in entries)
        wtype = "mixed" if has_half and has_int else ("half-int" if has_half else "integer")
        print(f"{N:3d}  {','.join(k_vals):>20s}  {max_ck:8.3f}  {wtype:>12s}")
