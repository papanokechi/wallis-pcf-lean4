#!/usr/bin/env python3
"""
Phase 0c: Higher-m closed form guesser
========================================
Uses the key insight from Phase 0b: R(n,m) = p_n/(2n-1)!! is polynomial
in m of degree floor(n/2) for fixed n.

Strategy:
  1. Compute R(n,m) matrix for many (n,m) pairs
  2. For each fixed n, fit R(n,m) as polynomial in m → get coefficients c_k(n)
  3. Identify c_k(n) as closed forms (Pochhammer, binomial, etc.)
  4. Reconstruct the general formula p_n(m) = (2n-1)!! * sum_k c_k(n) * m^k
  5. Verify symbolically and attempt induction proof for general m
"""
import json, sys, time
from fractions import Fraction
from datetime import datetime
from pathlib import Path

import mpmath
mpmath.mp.dps = 200
from mpmath import mpf, mp

import sympy
from sympy import (symbols, Rational, simplify, expand, factor, Poly,
                   binomial as sp_binom, factorial as sp_fact, floor as sp_floor,
                   cancel, nsimplify, S, together, apart)

n_sym, m_sym, k_sym = symbols('n m k', integer=True, nonneg=True)


def double_factorial_odd(nn):
    if nn <= 0: return 1
    r = 1
    for k in range(1, 2*nn, 2): r *= k
    return r


def compute_convergents(m_val, N=100):
    c = 2*m_val + 1
    bn = [3*k + 1 for k in range(N+1)]
    an = [0] + [-k*(2*k - c) for k in range(1, N+1)]
    p_prev, p_curr = 1, bn[0]
    q_prev, q_curr = 0, 1
    pvals, qvals = [p_curr], [q_curr]
    for k in range(1, N+1):
        p_new = bn[k]*p_curr + an[k]*p_prev
        q_new = bn[k]*q_curr + an[k]*q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
        pvals.append(p_curr)
        qvals.append(q_curr)
    return pvals, qvals


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Build R(n,m) matrix and fit polynomials in m
# ═══════════════════════════════════════════════════════════════════════════════

def build_R_matrix(N_max=20, M_max=12):
    """Build R(n,m) = p_n(m)/(2n-1)!! for n=0..N_max, m=0..M_max."""
    R = {}
    for m_val in range(M_max+1):
        pn, _ = compute_convergents(m_val, N_max)
        for nn in range(N_max+1):
            df = double_factorial_odd(nn)
            R[(nn, m_val)] = Fraction(pn[nn], df)
    return R


def fit_R_in_m(R, N_max=20, M_max=12):
    """For each fixed n, fit R(n,m) as polynomial in m.
    Returns dict: n -> list of rational coefficients [c0, c1, c2, ...]
    """
    results = {}
    
    for nn in range(N_max+1):
        values = [R[(nn, m_val)] for m_val in range(M_max+1)]
        
        # Determine degree: should be floor(n/2)
        expected_deg = nn // 2
        
        # Fit polynomial in m using sympy Lagrange interpolation
        points = [(Rational(m_val), Rational(values[m_val].numerator, values[m_val].denominator)) 
                  for m_val in range(expected_deg + 2)]  # need deg+1 points + 1 extra for verification
        
        # Build interpolating polynomial
        poly = S(0)
        for i, (xi, yi) in enumerate(points[:expected_deg+1]):
            basis = yi
            for j, (xj, yj) in enumerate(points[:expected_deg+1]):
                if i != j:
                    basis *= (m_sym - xj) / (xi - xj)
            poly += basis
        poly = simplify(expand(poly))
        
        # Extract coefficients
        p = Poly(poly, m_sym)
        coeffs = []
        for k in range(expected_deg + 1):
            coeffs.append(p.nth(k))
        
        # Verify against all m values
        ok = True
        for m_val in range(M_max+1):
            predicted = sum(c * m_val**k for k, c in enumerate(coeffs))
            actual = Rational(values[m_val].numerator, values[m_val].denominator)
            if predicted != actual:
                ok = False
                break
        
        results[nn] = {
            'degree': expected_deg,
            'coeffs': coeffs,
            'poly': poly,
            'verified': ok,
        }
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Identify coefficient patterns c_k(n)
# ═══════════════════════════════════════════════════════════════════════════════

def identify_coefficient_patterns(R_polys, N_max=20):
    """For each power of m, extract c_k(n) across n values and try to identify."""
    print("\n" + "=" * 74)
    print("  COEFFICIENT PATTERNS c_k(n) in R(n,m) = Σ c_k(n) · m^k")
    print("=" * 74)
    
    max_deg = max(info['degree'] for info in R_polys.values())
    
    patterns = {}
    for k in range(max_deg + 1):
        print(f"\n  c_{k}(n) — coefficient of m^{k}:")
        values = []
        for nn in range(N_max+1):
            if k <= R_polys[nn]['degree']:
                values.append((nn, R_polys[nn]['coeffs'][k]))
            else:
                values.append((nn, Rational(0)))
        
        # Print values
        for nn, val in values[:15]:
            print(f"    n={nn:2d}: c_{k}({nn}) = {val}")
        
        # Try to identify c_k(n) as a closed form
        # For k=0: c_0(n) should be 2n+1 (from m=0 case)
        # For k=1, k=2, ... need to find pattern
        
        # Finite differences to determine degree in n
        vals = [val for _, val in values]
        deg_n = find_polynomial_degree(vals)
        print(f"    → Polynomial in n of degree: {deg_n}")
        
        if deg_n is not None and deg_n >= 0:
            # Fit polynomial in n
            poly_n = fit_rational_polynomial(vals, deg_n)
            if poly_n is not None:
                print(f"    → c_{k}(n) = {poly_n}")
                # Verify
                ok = all(poly_n.subs(n_sym, nn) == val for nn, val in values[:N_max+1])
                print(f"    → Verified to n={N_max}: {'YES' if ok else 'NO'}")
                patterns[k] = poly_n
            else:
                print(f"    → Could not fit polynomial in n")
                # Try ratio analysis
                print(f"    Successive ratios:")
                for i in range(1, min(10, len(vals))):
                    if vals[i-1] != 0:
                        print(f"      c_{k}({i})/c_{k}({i-1}) = {vals[i]/vals[i-1]}")
        else:
            print(f"    → Not a polynomial in n (or too high degree)")
            # Try to identify as product of rational functions
            if k <= 3:
                for nn in range(2, min(10, len(vals))):
                    if vals[nn] != 0 and vals[nn-1] != 0:
                        ratio = vals[nn] / vals[nn-1]
                        print(f"    ratio c_{k}({nn})/c_{k}({nn-1}) = {ratio} = {float(ratio):.8f}")
    
    return patterns


def find_polynomial_degree(vals, max_deg=10):
    """Find degree of polynomial from values at 0,1,2,..."""
    # Use finite differences
    diffs = list(vals)
    for d in range(max_deg + 1):
        if all(v == 0 for v in diffs):
            return d - 1 if d > 0 else 0
        new_diffs = [diffs[i+1] - diffs[i] for i in range(len(diffs)-1)]
        if len(new_diffs) == 0:
            return None
        diffs = new_diffs
    
    # Check if constant after max_deg differences
    if all(v == diffs[0] for v in diffs):
        return max_deg
    return None


def fit_rational_polynomial(vals, deg):
    """Fit Q[n] polynomial of given degree to values at 0,1,2,..."""
    if deg < 0:
        return Rational(0)
    
    # Use sympy interpolation
    points = [(Rational(i), vals[i]) for i in range(min(deg+2, len(vals)))]
    
    poly = S(0)
    for i, (xi, yi) in enumerate(points[:deg+1]):
        basis = yi
        for j, (xj, yj) in enumerate(points[:deg+1]):
            if i != j:
                basis *= (n_sym - xj) / (xi - xj)
        poly += basis
    
    poly = simplify(expand(poly))
    
    # Verify
    for i in range(min(len(vals), 20)):
        if poly.subs(n_sym, i) != vals[i]:
            return None
    
    return poly


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Reconstruct general formula and attempt proof
# ═══════════════════════════════════════════════════════════════════════════════

def reconstruct_general_formula(patterns):
    """Build R(n,m) = sum_k c_k(n) * m^k from identified patterns."""
    print("\n" + "=" * 74)
    print("  RECONSTRUCTED FORMULA R(n,m)")
    print("=" * 74)
    
    if not patterns:
        print("  No patterns identified.")
        return None
    
    R_formula = S(0)
    for k, c_k in sorted(patterns.items()):
        term = c_k * m_sym**k
        R_formula += term
        print(f"  c_{k}(n) · m^{k} = ({c_k}) · m^{k}")
    
    R_formula = expand(R_formula)
    print(f"\n  R(n,m) = {R_formula}")
    print(f"  p_n(m) = (2n-1)!! · R(n,m)")
    
    return R_formula


def verify_reconstructed(R_formula, M_max=10, N_max=20):
    """Verify the reconstructed formula against computed p_n values."""
    print("\n  Verification against computed values:")
    
    mismatches = 0
    total = 0
    for m_val in range(M_max+1):
        pn, _ = compute_convergents(m_val, N_max)
        for nn in range(N_max+1):
            df = double_factorial_odd(nn)
            expected = pn[nn]
            R_val = R_formula.subs([(n_sym, nn), (m_sym, m_val)])
            predicted = df * R_val
            total += 1
            if predicted != expected:
                mismatches += 1
                if mismatches <= 5:
                    print(f"  MISMATCH n={nn}, m={m_val}: predicted={predicted}, actual={expected}")
    
    print(f"  Verified {total - mismatches}/{total} values "
          f"(n=0..{N_max}, m=0..{M_max}): "
          f"{'ALL MATCH' if mismatches == 0 else f'{mismatches} mismatches'}")
    return mismatches == 0


def attempt_general_proof(R_formula):
    """Attempt to prove the recurrence identity symbolically for general m."""
    print("\n" + "=" * 74)
    print("  GENERAL INDUCTION PROOF ATTEMPT")
    print("=" * 74)
    
    if R_formula is None:
        print("  No formula to prove.")
        return False
    
    c_param = 2*m_sym + 1
    
    # Recurrence: (2n-1)(2n-3) R(n) = (3n+1)(2n-3) R(n-1) - n(2n-c) R(n-2)
    R_n = R_formula
    R_nm1 = R_formula.subs(n_sym, n_sym - 1)
    R_nm2 = R_formula.subs(n_sym, n_sym - 2)
    
    LHS = (2*n_sym - 1) * (2*n_sym - 3) * R_n
    RHS = (3*n_sym + 1) * (2*n_sym - 3) * R_nm1 - n_sym * (2*n_sym - c_param) * R_nm2
    
    print(f"  Checking: (2n-1)(2n-3)·R(n,m) = (3n+1)(2n-3)·R(n-1,m) - n(2n-(2m+1))·R(n-2,m)")
    
    diff = expand(LHS - RHS)
    print(f"  LHS - RHS = {diff}")
    
    if diff == 0:
        print(f"  *** GENERAL IDENTITY VERIFIED! R(n,m) satisfies the recurrence for ALL m. ***")
        return True
    else:
        # Try to simplify
        diff_simplified = simplify(diff)
        print(f"  Simplified: {diff_simplified}")
        if diff_simplified == 0:
            print(f"  *** GENERAL IDENTITY VERIFIED (after simplification)! ***")
            return True
        
        # Try factoring
        try:
            diff_factored = factor(diff)
            print(f"  Factored: {diff_factored}")
        except:
            pass
        
        print(f"  Identity does NOT hold for the reconstructed formula.")
        print(f"  This means R(n,m) is more complex than a simple polynomial in (n,m).")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Alternative approach — bivariate generating function
# ═══════════════════════════════════════════════════════════════════════════════

def bivariate_analysis(N_max=15, M_max=8):
    """Analyze R(n,m) as a bivariate sequence looking for structure."""
    print("\n" + "=" * 74)
    print("  BIVARIATE ANALYSIS: R(n,m) structure")
    print("=" * 74)
    
    R = build_R_matrix(N_max, M_max)
    
    # Look at R(n,m) / (2n+1) — normalize by m=0 case
    print("\n  R(n,m) / R(n,0) = R(n,m)/(2n+1) for m>0:")
    for nn in range(1, min(12, N_max+1)):
        R_n0 = R[(nn, 0)]
        if R_n0 == 0:
            continue
        print(f"  n={nn}:", end="")
        for m_val in range(1, min(6, M_max+1)):
            ratio = R[(nn, m_val)] / R_n0
            print(f"  m={m_val}:{ratio}", end="")
        print()
    
    # Diagonal analysis: R(n,n)
    print("\n  Diagonal R(n,n):")
    for nn in range(min(8, N_max+1, M_max+1)):
        val = R[(nn, nn)]
        print(f"  R({nn},{nn}) = {val} = {float(val):.8f}")
    
    # Look at R(n,m) modulo small primes
    print("\n  Denominator structure of R(n,m):")
    for nn in range(2, min(8, N_max+1)):
        denoms = []
        for m_val in range(M_max+1):
            d = R[(nn, m_val)].denominator
            denoms.append(d)
        print(f"  n={nn}: denoms = {denoms[:8]}")
        import math
        lcm = 1
        for d in denoms:
            lcm = lcm * d // math.gcd(lcm, d)
        print(f"        lcm = {lcm} = {sympy.factorint(lcm)}")
    
    # Check: does lcm = (2n-1)!! / gcd pattern?
    print("\n  LCM compared to products of odd numbers:")
    for nn in range(2, min(10, N_max+1)):
        denoms = [R[(nn, m_val)].denominator for m_val in range(M_max+1)]
        import math
        lcm = 1
        for d in denoms:
            lcm = lcm * d // math.gcd(lcm, d)
        
        # Candidate: is lcm = prod of some odd numbers?
        odd_prod = 1
        remaining = lcm
        factors = []
        for k in range(3, 2*nn, 2):
            if remaining % k == 0:
                factors.append(k)
                remaining //= k
                odd_prod *= k
        if remaining == 1:
            print(f"  n={nn}: lcm = {'·'.join(map(str,factors))} = {lcm}")
        else:
            print(f"  n={nn}: lcm = {lcm}, remaining after odd strip = {remaining}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    
    print("=" * 74)
    print("  PHASE 0c: HIGHER-m CLOSED-FORM GUESSER")
    print("  Using polynomial-in-m insight from Phase 0b")
    print("=" * 74)
    
    N_MAX = 20
    M_MAX = 12
    
    print("\n  Building R(n,m) matrix...")
    R = build_R_matrix(N_MAX, M_MAX)
    
    print("\n  R(n,m) matrix (first entries):")
    print(f"  {'n\\m':>5}", end="")
    for m_val in range(min(7, M_MAX+1)):
        print(f"  {'m='+str(m_val):>12}", end="")
    print()
    for nn in range(min(10, N_MAX+1)):
        print(f"  {nn:5d}", end="")
        for m_val in range(min(7, M_MAX+1)):
            r = R[(nn, m_val)]
            s = str(r) if r.denominator <= 100 else f"{float(r):.6f}"
            print(f"  {s:>12}", end="")
        print()
    
    print("\n  Fitting R(n,m) as polynomial in m for each fixed n...")
    R_polys = fit_R_in_m(R, N_MAX, M_MAX)
    
    print("\n  Polynomial fits:")
    for nn in range(min(15, N_MAX+1)):
        info = R_polys[nn]
        status = "✓" if info['verified'] else "✗"
        print(f"  n={nn:2d}: deg={info['degree']}, R(n,m) = {info['poly']}  {status}")
    
    # Identify coefficient patterns
    patterns = identify_coefficient_patterns(R_polys, N_MAX)
    
    # Reconstruct general formula
    R_formula = reconstruct_general_formula(patterns)
    
    if R_formula is not None:
        # Verify
        ok = verify_reconstructed(R_formula, M_MAX, N_MAX)
        
        if ok:
            # Attempt general proof
            proved = attempt_general_proof(R_formula)
        else:
            print("  Reconstructed formula has mismatches — coefficient patterns incomplete.")
            proved = False
    else:
        proved = False
    
    # Bivariate analysis for deeper structure
    bivariate_analysis(N_MAX, M_MAX)
    
    elapsed = time.time() - t0
    
    # Export
    results = {
        'phase': '0c',
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed, 1),
        'R_poly_fits': {str(nn): {
            'degree': info['degree'],
            'poly_str': str(info['poly']),
            'verified': info['verified'],
        } for nn, info in R_polys.items()},
        'patterns_found': len(patterns),
        'general_formula': str(R_formula) if R_formula else None,
        'proved': proved,
    }
    Path('phase0c_results.json').write_text(json.dumps(results, indent=2))
    
    print("\n" + "=" * 74)
    print("  PHASE 0c SUMMARY")
    print("=" * 74)
    print(f"  Polynomial fits in m: {sum(1 for i in R_polys.values() if i['verified'])}/{len(R_polys)}")
    print(f"  Coefficient patterns c_k(n) identified: {len(patterns)}")
    print(f"  General formula: {'YES' if R_formula else 'NO'}")
    print(f"  General proof: {'PROVED' if proved else 'OPEN'}")
    print(f"  Time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
