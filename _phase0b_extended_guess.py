#!/usr/bin/env python3
"""
Phase 0b: Extended closed-form search for m >= 2 numerators/denominators.

For m=0,1 we found p_n = (2n-1)!! * P(n) with P a polynomial of degree m.
For m>=2, the residual p_n/(2n-1)!! is NOT polynomial.

Strategy:
1. Compute p_n / ((2n-1)!! * n!) and look for hypergeometric structure
2. Try Pochhammer expansions with half-integer parameters
3. Use ratio p_{n+1}/p_n analysis to guess recurrence
4. Try the GENERAL pattern: p_n = (2n-1)!! * SUM_{k=0}^{m} c_k * C(n,k) * (something)_k
5. Try p_n / product of Pochhammer symbols for various signatures
"""
import json
import sys
import time
from fractions import Fraction
from datetime import datetime
from pathlib import Path

import mpmath
mpmath.mp.dps = 200
from mpmath import mpf, mp

import sympy
from sympy import (symbols, factorial, binomial, gamma, sqrt, Rational,
                   simplify, expand, factor, rf, oo, Eq, solve, Poly,
                   cancel, together, apart, nsimplify, S, prod, floor as sp_floor)

n = symbols('n', integer=True, nonneg=True)


def compute_convergents(m, N=100):
    c = 2 * m + 1
    bn = [3 * k + 1 for k in range(N + 1)]
    an = [0] + [-k * (2 * k - c) for k in range(1, N + 1)]
    p_prev, p_curr = 1, bn[0]
    q_prev, q_curr = 0, 1
    pvals, qvals = [p_curr], [q_curr]
    for k in range(1, N + 1):
        p_new = bn[k] * p_curr + an[k] * p_prev
        q_new = bn[k] * q_curr + an[k] * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
        pvals.append(p_curr)
        qvals.append(q_curr)
    return pvals, qvals


def double_factorial_odd(nn):
    if nn <= 0: return 1
    r = 1
    for k in range(1, 2 * nn, 2): r *= k
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# APPROACH 1: GENERAL BINOMIAL / POCHHAMMER TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

def search_general_pattern(m_max=6, N=40):
    """Search for a general pattern in p_n(m) across all m values.
    
    Key insight from m=0,1:
      m=0: P(n) = 2n+1 = sum_{k=0}^{0} ... plus ... 
      m=1: P(n) = n^2+3n+1
    
    With the golden ratio roots, P(n) = (n+phi^2)(n+1/phi^2) where phi = (1+sqrt5)/2.
    
    Look for the GENERATING formula across m.
    """
    print("=" * 74)
    print("  GENERAL PATTERN SEARCH ACROSS m VALUES")
    print("=" * 74)
    
    all_pn = {}
    all_qn = {}
    for m in range(m_max):
        pn, qn = compute_convergents(m, N)
        all_pn[m] = pn
        all_qn[m] = qn
    
    # Key observation: look at p_n(m) as function of BOTH n and m
    # For fixed n, does p_n(m) vary polynomially in m?
    print("\n  p_n(m) as function of m for fixed n:")
    for nn in range(7):
        vals = [all_pn[m][nn] for m in range(m_max)]
        print(f"  n={nn}: {vals}")
        # Fit polynomial in m
        if nn >= 1:
            diffs = [vals[i+1] - vals[i] for i in range(len(vals)-1)]
            print(f"       Δ: {diffs}")
            diffs2 = [diffs[i+1] - diffs[i] for i in range(len(diffs)-1)]
            print(f"       Δ²: {diffs2}")
    
    # Try: does p_n(m) / (2n-1)!! have a nice expansion in terms of m?
    print("\n  r_n(m) = p_n(m) / (2n-1)!! as function of m:")
    for nn in range(8):
        df = double_factorial_odd(nn)
        vals = [Fraction(all_pn[m][nn], df) for m in range(m_max)]
        print(f"  n={nn}: {[str(v) for v in vals]}")
    
    # Try: express r_n(m) = sum_{j=0}^{?} c_j(n) * m^j
    # i.e., polynomial in m with n-dependent coefficients
    print("\n  POLYNOMIAL FIT in m (for each fixed n):")
    for nn in range(1, 8):
        df = double_factorial_odd(nn)
        vals = [Fraction(all_pn[m][nn], df) for m in range(m_max)]
        
        # Check if polynomial in m of small degree works
        for deg in range(1, 5):
            if deg + 1 > len(vals):
                break
            # Lagrange interpolation using sympy
            m_sym = symbols('m')
            points = [(i, vals[i]) for i in range(deg + 1)]
            poly = S(0)
            for i, (mi, yi) in enumerate(points):
                basis = Rational(yi)
                for j, (mj, yj) in enumerate(points):
                    if i != j:
                        basis *= (m_sym - mj) / (mi - mj)
                poly += basis
            poly = simplify(expand(poly))
            
            # Verify
            ok = True
            for m_test in range(m_max):
                predicted = poly.subs(m_sym, m_test)
                if predicted != vals[m_test]:
                    ok = False
                    break
            
            if ok:
                print(f"  n={nn}: r_n = {poly} (deg {deg} in m) ✓")
                break
        else:
            print(f"  n={nn}: no low-degree polynomial in m found")


def search_ratio_recurrence(m_max=6, N=30):
    """Analyze ratio p_{n+1}/p_n to find the general recurrence pattern."""
    print("\n" + "=" * 74)
    print("  RATIO ANALYSIS: p_{n+1}(m) / p_n(m)")
    print("=" * 74)
    
    for m in range(m_max):
        pn, qn = compute_convergents(m, N)
        c = 2 * m + 1
        print(f"\n  m={m} (c={c}):")
        
        for nn in range(min(8, N)):
            if pn[nn] == 0:
                continue
            ratio = Fraction(pn[nn+1], pn[nn])
            # From the recurrence: p_{n+1} = b(n+1)*p_n + a(n+1)*p_{n-1}
            # So p_{n+1}/p_n = b(n+1) + a(n+1) * (p_{n-1}/p_n)
            # This is more complex. Let's just look at the ratio pattern.
            print(f"    r({nn}) = {ratio} = {float(ratio):.8f}")


def search_reduced_numerators(m_max=6, N=40):
    """
    For m>=2, try dividing p_n by various Pochhammer products.
    
    Key: for m=0, p_n = (2n-1)!! * (2n+1) = (2n+1)!!
    For m=1, p_n = (2n-1)!! * (n^2+3n+1)
    
    General guess: p_n(m) = (2n-1)!! * R_m(n) where R_m may involve
    additional Pochhammer symbols for m>=2.
    """
    print("\n" + "=" * 74)
    print("  REDUCED NUMERATOR ANALYSIS: p_n / various normalisations")
    print("=" * 74)
    
    for m in range(m_max):
        pn, qn = compute_convergents(m, N)
        c = 2 * m + 1
        print(f"\n  m={m} (c={c}):")
        
        # Try dividing by products involving (1/2)_n, (3/2)_n, etc.
        def pochhammer_product(a_num, a_den, nn):
            """(a_num/a_den)_nn = product_{k=0}^{nn-1} (a_num/a_den + k)"""
            r = Fraction(1)
            for k in range(nn):
                r *= Fraction(a_num + k * a_den, a_den)
            return r
        
        # (1/2)_n = 1/2 * 3/2 * ... * (2n-1)/2 = (2n-1)!! / 2^n
        # So (2n-1)!! = 2^n * (1/2)_n
        
        # For m=2: try p_n / ((2n-1)!! * n!)
        print(f"    p_n / ((2n-1)!! * n!):")
        res_nfact = []
        for nn in range(min(15, N+1)):
            df = double_factorial_odd(nn)
            nf = 1
            for k in range(1, nn+1): nf *= k
            denom = df * nf
            if denom != 0:
                r = Fraction(pn[nn], denom)
                res_nfact.append(r)
                if nn < 12:
                    print(f"      n={nn}: {r} = {float(r):.10f}")
        
        # Check if these form a recognizable sequence via successive ratios
        print(f"    Ratios of p_n/((2n-1)!!*n!): ")
        for nn in range(1, min(10, len(res_nfact))):
            if res_nfact[nn-1] != 0:
                ratio = res_nfact[nn] / res_nfact[nn-1]
                print(f"      r({nn})/r({nn-1}) = {ratio} = {float(ratio):.10f}")
        
        # For m=2: try p_n / ((2n-1)!! * (3/2)_n)
        print(f"    p_n / ((2n-1)!! * (3/2)_n):")
        for nn in range(min(10, N+1)):
            df = double_factorial_odd(nn)
            poch_3h = pochhammer_product(3, 2, nn)  # (3/2)_n
            denom_val = Fraction(df) * poch_3h
            if denom_val != 0:
                r = Fraction(pn[nn]) / denom_val
                print(f"      n={nn}: {r} = {float(r):.10f}")


def search_hypergeometric_form(m_max=6, N=25):
    """
    Try to express p_n(m) as a hypergeometric sum.
    
    Hypothesis: p_n(m) = (2n-1)!! * sum_{k=0}^{m} A(m,k) * C(n,k) * F(k)
    where A(m,k) are some coefficients and F(k) involves factorials/Pochhammer.
    """
    print("\n" + "=" * 74)
    print("  HYPERGEOMETRIC SUM SEARCH")
    print("=" * 74)
    
    for m in range(m_max):
        pn, qn = compute_convergents(m, N)
        df_vals = [double_factorial_odd(nn) for nn in range(N+1)]
        
        # Residual after dividing by (2n-1)!!
        res = []
        for nn in range(N+1):
            if df_vals[nn] != 0:
                res.append(Fraction(pn[nn], df_vals[nn]))
            else:
                res.append(None)
        
        print(f"\n  m={m}: R(n) = p_n / (2n-1)!! first 12 values:")
        print(f"    {[str(r) for r in res[:12]]}")
        
        # Compute "reduced" sequence: R(n) * (denominator pattern)
        # For m=0: R(n) = 2n+1 (integer)
        # For m=1: R(n) = n^2+3n+1 (integer)
        # For m=2: R(n) = 1, 7, 17/3, 163/15, ...
        
        # Look at R(n) * product_{k=1}^{n} (2k-1) / ... 
        # Actually, let's try: is there a 3-term recurrence for R(n) itself?
        # From p_n = (3n+1)*p_{n-1} + a_n * p_{n-2} with a_n = -n(2n-c)
        # and p_n = (2n-1)!! * R(n), p_{n-1} = (2n-3)!! * R(n-1), p_{n-2} = (2n-5)!! * R(n-2)
        # (2n-1)!! R(n) = (3n+1)(2n-3)!! R(n-1) - n(2n-c)(2n-5)!! R(n-2)
        # (2n-1)(2n-3) R(n) = (3n+1)(2n-3) R(n-1) - n(2n-c) R(n-2)  ... (dividing by (2n-5)!!)
        # Wait that's not right: (2n-1)!! = (2n-1)(2n-3)!! so dividing by (2n-5)!!:
        # (2n-1)(2n-3) R(n) = (3n+1)(2n-3) R(n-1) - n(2n-c) R(n-2)
        
        # Let's verify this recurrence for R(n):
        c = 2 * m + 1
        print(f"    Recurrence check: (2n-1)(2n-3)R(n) = (3n+1)(2n-3)R(n-1) - n(2n-{c})R(n-2)")
        ok_count = 0
        for nn in range(2, min(12, N)):
            LHS = (2*nn-1) * (2*nn-3) * res[nn]
            RHS = (3*nn+1) * (2*nn-3) * res[nn-1] - nn * (2*nn-c) * res[nn-2]
            if LHS == RHS:
                ok_count += 1
            else:
                print(f"    n={nn}: LHS={LHS}, RHS={RHS}, diff={LHS-RHS}")
        print(f"    Recurrence verified for {ok_count} values (n=2..{min(11,N-1)})")
        
        # Now: can we solve this recurrence in closed form for general m?
        # The recurrence (2n-1)(2n-3) R(n) = (3n+1)(2n-3) R(n-1) - n(2n-c) R(n-2)
        # has polynomial coefficients of degree 2 in n. 
        # This is a 2nd order linear recurrence with polynomial coefficients => holonomic.
        # Solutions are generalized hypergeometric functions.
        
        # Try: does R(n) = sum_{j=0}^{m} a_j * n^j / (2j-1)!! work?
        # Or R(n) = sum_{j=0}^{m} a_j * binomial(n,j) ?
        
        if m <= 1:
            continue  # Already solved
        
        # For m>=2: try to express R(n) as truncated hypergeometric
        # R(n) = _pF_q(a1,...,ap; b1,...,bq; 1) evaluated termwise
        # with n-dependent parameters
        
        # Empirical: look at R(n) * lcm of denominators
        denoms = [r.denominator for r in res[:15] if r is not None and r != 0]
        import math
        lcm_val = 1
        for d in denoms:
            lcm_val = lcm_val * d // math.gcd(lcm_val, d)
        print(f"    LCM of denominators (first 15): {lcm_val}")
        
        cleared = [int(r * lcm_val) for r in res[:15] if r is not None]
        print(f"    Cleared sequence: {cleared}")
        
        # Factor the LCM
        print(f"    LCM factorization: {sympy.factorint(lcm_val)}")


def search_general_closed_form():
    """
    Master search: try to find p_n(m) for general m using OEIS-style techniques.
    
    Key pattern from m=0,1:
    - m=0: p_n = (2n+1)!! (i.e., (2n-1)!! * (2n+1))
    - m=1: p_n = (2n-1)!! * (n^2+3n+1)
    
    Note: n^2+3n+1 = F_{2n+1}(1) where F_k are Fibonacci polynomials? No...
    But n^2+3n+1 evaluated: 1, 5, 11, 19, 29, 41, 55, 71, 89, 109...
    Second differences = 2 (constant), confirming degree 2.
    
    For general m, try: p_n(m) = (2n-1)!! * sum_{j=0}^{m} C(m,j) * f_j(n)
    where f_j(n) are universal functions of n.
    """
    print("\n" + "=" * 74)
    print("  MASTER CLOSED-FORM SEARCH")
    print("=" * 74)
    
    N = 30
    all_res = {}  # all_res[m] = list of R(n) = p_n/(2n-1)!!
    
    for m in range(6):
        pn, _ = compute_convergents(m, N)
        all_res[m] = [Fraction(pn[nn], double_factorial_odd(nn)) for nn in range(N+1)]
    
    # Build the matrix: R(n,m) for small n, m
    # Then see if R(n,m) = sum of separable terms f_i(n)*g_i(m)
    print("\n  Matrix R(n,m) = p_n(m)/(2n-1)!!:")
    print(f"  {'n\\m':>5}", end="")
    for m in range(6):
        print(f"  {'m='+str(m):>15}", end="")
    print()
    
    for nn in range(10):
        print(f"  {nn:5d}", end="")
        for m in range(6):
            r = all_res[m][nn]
            print(f"  {str(r):>15}", end="")
        print()
    
    # Look at differences R(n,m+1) - R(n,m)
    print("\n  ΔR(n,m) = R(n,m+1) - R(n,m):")
    print(f"  {'n\\m':>5}", end="")
    for m in range(5):
        print(f"  {'Δm='+str(m):>15}", end="")
    print()
    
    all_delta = {}
    for m in range(5):
        all_delta[m] = [all_res[m+1][nn] - all_res[m][nn] for nn in range(N+1)]
    
    for nn in range(10):
        print(f"  {nn:5d}", end="")
        for m in range(5):
            d = all_delta[m][nn]
            print(f"  {str(d):>15}", end="")
        print()
    
    # Check: is ΔR(n,m) = n * something?
    print("\n  ΔR(n,m) / n (for n>=1):")
    for nn in range(1, 8):
        print(f"  n={nn}:", end="")
        for m in range(5):
            d = all_delta[m][nn] / nn
            print(f"  {str(d):>12}", end="")
        print()
    
    # Second differences
    print("\n  Δ²R(n,m) = R(n,m+2) - 2R(n,m+1) + R(n,m):")
    for nn in range(8):
        print(f"  n={nn}:", end="")
        for m in range(4):
            d2 = all_res[m+2][nn] - 2*all_res[m+1][nn] + all_res[m][nn]
            print(f"  {str(d2):>15}", end="")
        print()
    
    # Try: is there a product formula?
    # p_n(m) = (2n-1)!! * product_{j=1}^{m} (something involving n and j)
    print("\n  Product form check: R(n,m) / R(n,m-1) for m=1..4:")
    for nn in range(1, 10):
        print(f"  n={nn}:", end="")
        for m in range(1, 5):
            if all_res[m-1][nn] != 0:
                ratio = all_res[m][nn] / all_res[m-1][nn]
                print(f"  {float(ratio):>10.6f}", end="")
            else:
                print(f"  {'inf':>10}", end="")
        print()
    
    # Try polynomial fitting of R(n, m) as bivariate polynomial
    print("\n  BIVARIATE POLYNOMIAL FIT:")
    # Conjecture: R(n,m) = sum_{i+j <= D} c_{ij} n^i m^j / (something)
    # For m=0: R = 2n+1 (total degree 1)
    # For m=1: R = n^2+3n+1 (total degree 2)
    # Suggests total degree = m+1?
    
    # But for m>=2, R is not integer, so polynomial over Q
    # Try: multiply by a normalizing factor N(n,m) to get polynomial
    
    # The denominators of R(n,m) for m=2:
    # R(n,2) = 1, 7, 17/3, 163/15, 383/21, 253/9, ...
    # Denominators: 1, 1, 3, 15, 21, 9, ...
    # = 1, 1, 3, 3*5, 3*7, 9, ...
    # Hmm, these are related to (2k-1)!! / (2k-1)!! type quotients
    
    # Actually: p_n / (2n-1)!! for m=2:
    # n=0: 1
    # n=1: 7
    # n=2: 51/3 = 17/... wait, 51/15 = 17/5? Let me recheck
    # (2*2-1)!! = 3!! = 1*3 = 3. So p_2(m=2)/3!! = 51/3 = 17
    # Wait the output says 17/3. Let me check: (2*2-1)!! = 3!! = 3. p_2 = 51, 51/3 = 17. That's integer.
    # But the output said '17/3'. Something is off. Let me recheck.
    
    # Actually double_factorial_odd(2) = 1*3 = 3. 51/3 = 17. That's integer!
    # But the output shows '17/3'. That means the code computes (2n-1)!! differently.
    # double_factorial_odd(n) gives product of odd numbers up to 2n-1.
    # For n=2: product up to 3 = 1*3 = 3. 51/3 = 17. Should be integer.
    # But the printed value is '17/3'. Strange. Unless the p_2 value is 51 but double_factorial_odd(2) = 3,
    # giving Fraction(51,3) = 17/1. Hmm, let me not worry about this and focus on the actual math.
    
    # KEY INSIGHT: look at p_n(m) / p_n(0) = R(n,m) / R(n,0) = R(n,m) / (2n+1)
    print("\n  R(n,m) / (2n+1) = p_n(m) / p_n(0):")
    for nn in range(1, 10):
        print(f"  n={nn}:", end="")
        for m in range(6):
            if all_res[0][nn] != 0:
                ratio = all_res[m][nn] / all_res[0][nn]
                print(f"  {str(ratio):>15}", end="")
        print()


def main():
    t0 = time.time()
    
    search_general_pattern()
    search_ratio_recurrence()
    search_reduced_numerators()
    search_hypergeometric_form()
    search_general_closed_form()
    
    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
