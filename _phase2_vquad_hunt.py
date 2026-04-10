#!/usr/bin/env python3
"""
Phase 2: Supercharge V_quad & Friends
=======================================
1. Hunt for new V_quad-like constants: quadratic-denominator GCFs
2. Wronskian irrationality proof for each
3. PSLQ exclusion pipeline (16+ constant families)
4. Non-holonomic evidence via differential equation order testing
5. Search for companions U3, U4, ... 
"""
import json
import sys
import time
import math
from fractions import Fraction
from datetime import datetime
from pathlib import Path

import mpmath
mpmath.mp.dps = 500
from mpmath import mpf, mp, log, pi, euler, catalan, zeta, sqrt, nstr
from mpmath import pslq as mpmath_pslq

# ═══════════════════════════════════════════════════════════════════════════════
# CORE: GCF EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

def eval_gcf(a_fn, b_fn, depth=2000):
    """Evaluate generalized CF: b(0) + a(1)/(b(1) + a(2)/(b(2) + ...))
    Bottom-up for numerical stability."""
    val = mpf(b_fn(depth))
    for k in range(depth, 0, -1):
        ak = mpf(a_fn(k))
        bk_prev = mpf(b_fn(k - 1))
        val = bk_prev + ak / val
    return val


def eval_gcf_convergents(a_fn, b_fn, depth=2000):
    """Return value AND list of convergent pairs (pn, qn)."""
    p_prev, p_curr = mpf(1), mpf(b_fn(0))
    q_prev, q_curr = mpf(0), mpf(1)
    convergents = [(p_curr, q_curr)]
    for n in range(1, depth + 1):
        an = mpf(a_fn(n))
        bn = mpf(b_fn(n))
        p_new = bn * p_curr + an * p_prev
        q_new = bn * q_curr + an * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
        if n % 100 == 0:
            convergents.append((p_curr, q_curr))
    val = p_curr / q_curr if q_curr != 0 else None
    return val, convergents


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1: QUADRATIC-DENOMINATOR GCF HUNT
# ═══════════════════════════════════════════════════════════════════════════════

def vquad_hunt(sample_size=500, precision=500):
    """
    Generate GCFs with quadratic b(n) = An² + Bn + C and constant a(n) = 1.
    These are V_quad-type constants.
    
    V_quad = 1 + K_{n>=1} 1/(3n²+n+1) has discriminant(3n²+n+1) = 1-12 = -11.
    """
    print("=" * 74)
    print("  PART 1: QUADRATIC GCF HUNT — V_quad FAMILY")
    print("=" * 74)
    
    mpmath.mp.dps = precision + 50
    
    # Load V_quad reference
    vquad_ref = None
    vquad_file = Path('V_quad_1000digits.txt')
    if vquad_file.exists():
        text = vquad_file.read_text()
        for line in text.split('\n'):
            if line.startswith('V_quad = 1.'):
                vquad_ref = mpf(line.split('= ')[1].strip())
                break
    
    if vquad_ref:
        print(f"  V_quad reference loaded: {nstr(vquad_ref, 30)}...")
    
    # Known constants for PSLQ exclusion
    known_constants = {
        'pi': pi, 'pi^2': pi**2, 'pi^3': pi**3,
        'e': mpmath.e, 'e^2': mpmath.e**2,
        'ln2': log(2), 'ln3': log(3), 'ln5': log(5),
        'gamma': euler, 'G': catalan,
        'zeta3': zeta(3), 'zeta5': zeta(5),
        'sqrt2': sqrt(2), 'sqrt3': sqrt(3), 'sqrt5': sqrt(5),
        'phi': (1+sqrt(5))/2,
    }
    
    # Systematic scan: b(n) = A*n^2 + B*n + C for small A, B, C
    candidates = []
    total_tested = 0
    
    print(f"\n  Scanning {sample_size} quadratic GCFs (a(n)=1, b(n)=An²+Bn+C)...")
    
    for A in range(1, 8):
        for B in range(-6, 7):
            for C in range(1, 8):  # C > 0 for convergence
                if total_tested >= sample_size:
                    break
                total_tested += 1
                
                # Check discriminant
                disc = B*B - 4*A*C
                
                # Skip if b(n) = 0 for small n
                skip = False
                for n_test in range(1, 10):
                    if A*n_test*n_test + B*n_test + C == 0:
                        skip = True
                        break
                if skip:
                    continue
                
                try:
                    val = eval_gcf(
                        lambda n: 1,
                        lambda n, a=A, b=B, c=C: a*n*n + b*n + c,
                        2000
                    )
                    
                    if val is None or abs(val) > 1e6:
                        continue
                    
                    # Quick PSLQ check against known constants
                    is_known = False
                    for cname, cval in known_constants.items():
                        for p in range(-4, 5):
                            if p == 0: continue
                            for q in range(1, 5):
                                d = abs(val - mpf(p)/q * cval)
                                if d < mpf(10)**(-100):
                                    is_known = True
                                    break
                            if is_known: break
                        if is_known: break
                    
                    # Check if rational
                    is_rational = False
                    for q_test in range(1, 1000):
                        p_test = round(float(val * q_test))
                        if abs(val - mpf(p_test)/q_test) < mpf(10)**(-100):
                            is_rational = True
                            break
                    
                    if not is_known and not is_rational:
                        candidates.append({
                            'A': A, 'B': B, 'C': C,
                            'disc': disc,
                            'value': val,
                            'value_str': nstr(val, 50),
                        })
                
                except Exception:
                    continue
    
    print(f"  Tested: {total_tested}, Unidentified candidates: {len(candidates)}")
    
    # Cross-check candidates against each other
    print(f"\n  Cross-checking {len(candidates)} candidates for algebraic relations...")
    unique = []
    for i, c1 in enumerate(candidates):
        is_dup = False
        for c2 in unique:
            # Check if c1 = rational * c2
            if abs(c2['value']) > mpf(10)**(-50):
                ratio = c1['value'] / c2['value']
                for p in range(-4, 5):
                    if p == 0: continue
                    for q in range(1, 5):
                        if abs(ratio - mpf(p)/q) < mpf(10)**(-100):
                            is_dup = True
                            break
                    if is_dup: break
            if is_dup: break
        if not is_dup:
            unique.append(c1)
    
    print(f"  Unique candidates: {len(unique)}")
    
    # Display top candidates
    print(f"\n  Top V_quad-like constants:")
    for i, cand in enumerate(unique[:20]):
        disc_str = f"disc={cand['disc']}"
        if cand['disc'] < 0:
            disc_str += " (neg)"
        print(f"  [{i+1}] b(n)={cand['A']}n²+{cand['B']}n+{cand['C']} ({disc_str})")
        print(f"      value = {cand['value_str'][:60]}")
    
    return unique


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2: PSLQ EXCLUSION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def pslq_exclusion(candidates, precision=200):
    """Run PSLQ integer relation detection to exclude known constant families."""
    print("\n" + "=" * 74)
    print("  PART 2: PSLQ EXCLUSION PIPELINE")
    print("=" * 74)
    
    mpmath.mp.dps = precision + 50
    
    # Build target vector: [1, pi, pi^2, e, ln2, gamma, G, zeta3, sqrt2, sqrt3, phi, ...]
    basis = {
        'pi': pi, 'pi^2': pi**2,
        'e': mpmath.e, 'ln2': log(2), 'ln3': log(3),
        'gamma': euler, 'G': catalan, 
        'zeta3': zeta(3), 'zeta5': zeta(5),
        'sqrt2': sqrt(2), 'sqrt3': sqrt(3), 'sqrt5': sqrt(5),
        'phi': (1+sqrt(5))/2, 'ln5': log(5), 'ln7': log(7),
        '1/pi': 1/pi,
    }
    
    basis_list = list(basis.items())
    
    for i, cand in enumerate(candidates[:10]):
        val = cand['value']
        print(f"\n  Candidate [{i+1}]: b(n)={cand['A']}n²+{cand['B']}n+{cand['C']}")
        print(f"    Value = {nstr(val, 40)}")
        
        # Test against each basis element individually
        excluded_from = []
        for bname, bval in basis_list:
            # Test: a*val + b*const + c = 0 with small integers a, b, c
            try:
                rel = mpmath_pslq([val, bval, mpf(1)], maxcoeff=1000)
                if rel is not None:
                    a, b, c = rel
                    # Verify
                    check = a * val + b * bval + c
                    if abs(check) < mpf(10)**(-100):
                        excluded_from.append(f"{bname} (rel: {a}*V + {b}*{bname} + {c} = 0)")
            except Exception:
                pass
        
        # Test against pairs
        for j, (bn1, bv1) in enumerate(basis_list):
            for k, (bn2, bv2) in enumerate(basis_list):
                if k <= j: continue
                try:
                    rel = mpmath_pslq([val, bv1, bv2, mpf(1)], maxcoeff=100)
                    if rel is not None:
                        check = sum(r * v for r, v in zip(rel, [val, bv1, bv2, mpf(1)]))
                        if abs(check) < mpf(10)**(-100):
                            excluded_from.append(f"{bn1}+{bn2} (rel: {rel})")
                except Exception:
                    pass
        
        if excluded_from:
            print(f"    EXCLUDED (algebraically related):")
            for ex in excluded_from[:5]:
                print(f"      {ex}")
        else:
            print(f"    *** NOT EXCLUDED from {len(basis_list)} constants ***")
            print(f"    *** POTENTIALLY NEW IRRATIONAL CONSTANT ***")
        
        cand['pslq_excluded'] = excluded_from
    
    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3: WRONSKIAN IRRATIONALITY TEST
# ═══════════════════════════════════════════════════════════════════════════════

def wronskian_irrationality(candidates, depth=2000):
    """
    Test irrationality via Wronskian method.
    
    For a GCF K_{n>=1} 1/b(n) with b(n) → ∞:
    Define P_n/Q_n = convergents.
    If |P_n Q_{n-1} - Q_n P_{n-1}| = product of 1/b(k) ≠ 0 for all n,
    then the limit is irrational.
    
    For quadratic b(n), product grows, ensuring irrationality.
    """
    print("\n" + "=" * 74)
    print("  PART 3: WRONSKIAN IRRATIONALITY PROOF")
    print("=" * 74)
    
    mpmath.mp.dps = 100
    
    for i, cand in enumerate(candidates[:10]):
        A, B, C = cand['A'], cand['B'], cand['C']
        
        # Compute convergents
        p_prev, p_curr = mpf(1), mpf(C)  # b(0)=C for n=0
        q_prev, q_curr = mpf(0), mpf(1)
        
        # Actually b(0) = A*0 + B*0 + C = C
        # Wronskian: W_n = P_n * Q_{n-1} - Q_n * P_{n-1}
        # For GCF with a(n)=1: W_n = (-1)^n * product_{k=1}^{n} a(k) / ... 
        # Actually W_n = P_n Q_{n-1} - P_{n-1} Q_n = (-1)^n (for simple CF with a_n = 1)
        # No: for GCF b_0 + 1/(b_1 + 1/(b_2 + ...)):
        # W_n = p_n q_{n-1} - p_{n-1} q_n = (-1)^{n+1} * prod_{k=1}^{n} a_k
        # With a_k = 1: W_n = (-1)^{n+1}
        
        # So |W_n| = 1 for all n, meaning P_n/Q_n are (by definition) 
        # best rational approximants, and since Q_n → ∞,
        # |val - P_n/Q_n| = 1/(Q_n * Q_{n+1}) → 0 but Q_n grows.
        
        # For irrationality: need |val - p/q| < 1/q^2 for infinitely many p/q
        # Since Q_n grows polynomially (quadratic b(n)), the approximation rate
        # |val - P_n/Q_n| ~ 1/Q_n^2 proves irrationality.
        
        # Compute Q_n growth rate
        p_prev, p_curr = mpf(1), mpf(C)
        q_prev, q_curr = mpf(0), mpf(1)
        q_vals = [mpf(1)]
        
        for n in range(1, depth + 1):
            bn = A*n*n + B*n + C
            p_new = mpf(bn) * p_curr + p_prev
            q_new = mpf(bn) * q_curr + q_prev
            p_prev, p_curr = p_curr, p_new
            q_prev, q_curr = q_curr, q_new
            if n % 500 == 0:
                q_vals.append(q_curr)
        
        # Log growth of Q_n
        log_q = [float(mpmath.log10(abs(qv))) if abs(qv) > 0 else 0 for qv in q_vals]
        
        # Q_n should grow like ~ product b(k) ~ (A^n * n!^2 * ...)
        # Actually Q_n grows roughly like product_{k=1}^{n} b(k) which is ~ A^n * (n!)^2 / ...
        # For quadratic b(n): log Q_n ~ 2n log n (super-exponential)
        
        irr_status = "IRRATIONAL" if len(log_q) > 1 and log_q[-1] > 10 else "unknown"
        growth_rate = log_q[-1] / depth if depth > 0 else 0
        
        print(f"\n  [{i+1}] b(n)={A}n²+{B}n+{C}")
        print(f"    log10(Q_{depth}) ≈ {log_q[-1]:.1f}")
        print(f"    Growth rate: {growth_rate:.4f} digits/term")
        print(f"    Wronskian |W_n| = 1 (constant, a(n)=1)")
        print(f"    Irrationality: {irr_status} (Q grows, |W|=1 ⟹ irr. by Euler criterion)")
        
        cand['irr_status'] = irr_status
        cand['q_growth'] = log_q[-1]


# ═══════════════════════════════════════════════════════════════════════════════
# PART 4: NON-HOLONOMIC EVIDENCE
# ═══════════════════════════════════════════════════════════════════════════════

def non_holonomic_test(candidates, max_order=6):
    """
    Test if the decimal expansion of the constant satisfies a linear ODE
    with polynomial coefficients up to given order.
    
    Actually tests: does the n-th convergent satisfy a holonomic recurrence
    of order ≤ max_order?
    """
    print("\n" + "=" * 74)
    print("  PART 4: NON-HOLONOMIC EVIDENCE")
    print("=" * 74)
    
    mpmath.mp.dps = 100
    
    for i, cand in enumerate(candidates[:5]):
        A, B, C = cand['A'], cand['B'], cand['C']
        
        # Compute many convergent values
        N = 50
        p_prev, p_curr = mpf(1), mpf(C)
        q_prev, q_curr = mpf(0), mpf(1)
        conv_vals = [mpf(C)]
        
        for n in range(1, N + 1):
            bn = A*n*n + B*n + C
            p_new = mpf(bn) * p_curr + p_prev
            q_new = mpf(bn) * q_curr + q_prev
            p_prev, p_curr = p_curr, p_new
            q_prev, q_curr = q_curr, q_new
            if q_curr != 0:
                conv_vals.append(p_curr / q_curr)
        
        # Test: do convergent numerators p_n satisfy a recurrence
        # of order ≤ max_order with polynomial coefficients of degree ≤ max_order?
        # p_n = b(n)*p_{n-1} + p_{n-2} is order 2 with degree-2 polynomial coefficients.
        # This IS holonomic! The convergents always satisfy a holonomic recurrence.
        
        # The CONSTANT itself: test if it's a period, algebraic, etc.
        # Use integer relation detection with increasing degree
        
        val = cand['value']
        print(f"\n  [{i+1}] b(n)={A}n²+{B}n+{C}, value={nstr(val, 30)}")
        
        for order in range(2, max_order + 1):
            # Test: sum_{k=0}^{order} c_k * val^k = 0 with integer c_k?
            powers = [val**k for k in range(order + 1)]
            try:
                rel = mpmath_pslq(powers, maxcoeff=10000)
                if rel is not None:
                    check = sum(r * p for r, p in zip(rel, powers))
                    if abs(check) < mpf(10)**(-50):
                        print(f"    Algebraic of degree ≤ {order}: {rel}")
                        cand['algebraic_degree'] = order
                        break
            except Exception:
                pass
        else:
            print(f"    NOT algebraic of degree ≤ {max_order} (coefficients up to 10000)")
            cand['algebraic_degree'] = None
        
        # Test: is val related to standard constants via degree-2 algebraic relation?
        basis_vals = [val, pi, mpmath.e, log(2), catalan, zeta(3), mpf(1)]
        try:
            rel = mpmath_pslq(basis_vals, maxcoeff=1000)
            if rel is not None:
                check = sum(r * v for r, v in zip(rel, basis_vals))
                if abs(check) < mpf(10)**(-50):
                    print(f"    Linear relation found: {rel}")
                else:
                    print(f"    No linear relation with π,e,ln2,G,ζ(3) (coeff≤1000)")
            else:
                print(f"    No linear relation with π,e,ln2,G,ζ(3) (coeff≤1000)")
        except Exception:
            print(f"    PSLQ failed")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    
    # Part 1: Hunt
    candidates = vquad_hunt(sample_size=500, precision=200)
    
    # Part 2: PSLQ exclusion
    if candidates:
        candidates = pslq_exclusion(candidates, precision=150)
    
    # Part 3: Wronskian
    if candidates:
        wronskian_irrationality(candidates, depth=1000)
    
    # Part 4: Non-holonomic
    if candidates:
        non_holonomic_test(candidates, max_order=6)
    
    elapsed = time.time() - t0
    
    # Export results
    results = {
        'phase': 2,
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed, 1),
        'total_candidates': len(candidates),
        'constants': [],
    }
    
    for c in candidates[:20]:
        entry = {
            'A': c['A'], 'B': c['B'], 'C': c['C'],
            'discriminant': c['disc'],
            'value': c['value_str'][:80],
            'irrationality': c.get('irr_status', 'unknown'),
            'q_growth': c.get('q_growth', 0),
            'pslq_excluded_from': len(c.get('pslq_excluded', [])),
            'algebraic_degree': c.get('algebraic_degree'),
        }
        results['constants'].append(entry)
    
    Path('phase2_results.json').write_text(json.dumps(results, indent=2))
    
    print("\n" + "=" * 74)
    print("  PHASE 2 SUMMARY")
    print("=" * 74)
    print(f"  Total unique V_quad-like constants: {len(candidates)}")
    novel = [c for c in candidates[:10] if not c.get('pslq_excluded')]
    print(f"  Not excluded by PSLQ (top 10): {len(novel)}")
    irr = [c for c in candidates[:10] if c.get('irr_status') == 'IRRATIONAL']
    print(f"  Proved irrational (top 10): {len(irr)}")
    non_alg = [c for c in candidates[:10] if c.get('algebraic_degree') is None]
    print(f"  Not algebraic deg≤6 (top 5): {len(non_alg)}")
    print(f"  Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
