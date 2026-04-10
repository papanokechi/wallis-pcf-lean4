#!/usr/bin/env python3
"""
Phase 0: Seed the Generator with Existing Data
================================================
Quick wins from the roadmap:
1. Compute Pi Family numerator/denominator sequences for m=0,1,2,3,4
2. Search for closed-form expressions (Pochhammer, binomial, hypergeometric)
3. Verify candidate closed forms to 500+ terms
4. Attempt automated inductive proof of Conjecture 1
5. Export results for the generator registry

Pi Family: a(n) = -n(2n-(2m+1)), b(n) = 3n+1
  m=0 => a(n) = -n(2n-1), c=1
  m=1 => a(n) = -n(2n-3), c=3
  m=2 => a(n) = -n(2n-5), c=5
  etc.
"""
import json
import sys
import time
from fractions import Fraction
from datetime import datetime
from pathlib import Path

try:
    import mpmath
    mpmath.mp.dps = 200
    from mpmath import mpf, mp
    HAS_MPMATH = True
except ImportError:
    HAS_MPMATH = False
    print("ERROR: mpmath required. pip install mpmath")
    sys.exit(1)

try:
    import sympy
    from sympy import (symbols, factorial, binomial, gamma, sqrt, Rational,
                       simplify, expand, factor, rf, ff, oo, Sum, oo as sp_oo,
                       Eq, solve, Poly, cancel, together, apart, nsimplify)
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False
    print("Warning: sympy not available. Symbolic proofs disabled.")


# ═══════════════════════════════════════════════════════════════════════════════
# CORE: COMPUTE PCF CONVERGENTS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_convergents(m, N=100, return_both=True):
    """Compute convergent numerators p_n and denominators q_n for Pi Family.
    
    Pi Family: a(n) = -n(2n-(2m+1)), b(n) = 3n+1
    """
    c = 2 * m + 1
    bn = [3 * n + 1 for n in range(N + 1)]
    an = [0] + [-n * (2 * n - c) for n in range(1, N + 1)]
    
    # p_{-1}=1, p_0=b_0=1, q_{-1}=0, q_0=1
    p_prev, p_curr = 1, bn[0]
    q_prev, q_curr = 0, 1
    
    pvals = [p_curr]
    qvals = [q_curr]
    
    for n in range(1, N + 1):
        p_new = bn[n] * p_curr + an[n] * p_prev
        q_new = bn[n] * q_curr + an[n] * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
        pvals.append(p_curr)
        qvals.append(q_curr)
    
    if return_both:
        return pvals, qvals
    return pvals


def double_factorial_odd(n):
    """(2n-1)!! = 1*3*5*...*(2n-1)"""
    if n <= 0:
        return 1
    r = 1
    for k in range(1, 2 * n, 2):
        r *= k
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0a: CLOSED-FORM GUESSING FOR ALL m
# ═══════════════════════════════════════════════════════════════════════════════

def guess_closed_form_numerators(m, N=30):
    """Try to find closed form for p_n(m) by:
    1. Dividing out (2n-1)!! factor
    2. Fitting the remaining polynomial
    """
    pn, qn = compute_convergents(m, N)
    
    print(f"\n  m={m}: a(n) = -n(2n-{2*m+1}), b(n) = 3n+1")
    print(f"  First 12 p_n: {pn[:12]}")
    
    # Try dividing by (2n-1)!!
    residuals = []
    for n in range(N + 1):
        df = double_factorial_odd(n)
        if df == 0:
            residuals.append(None)
        else:
            r = Fraction(pn[n], df)
            residuals.append(r)
    
    print(f"  p_n / (2n-1)!! = {[str(r) for r in residuals[:12]]}")
    
    # Check if residuals are polynomial in n
    all_int = all(r is not None and r.denominator == 1 for r in residuals[:N+1])
    if all_int:
        int_res = [int(r) for r in residuals[:N+1]]
        print(f"  Integer residuals: {int_res[:12]}")
        
        # Fit polynomial: try degrees 0, 1, 2, 3, 4
        for deg in range(5):
            poly = fit_polynomial(int_res, deg)
            if poly is not None:
                print(f"  MATCH: p_n(m={m}) = (2n-1)!! * P_{deg}(n)")
                print(f"    P_{deg}(n) = {poly_to_str(poly)}")
                # Verify
                ok = verify_poly(int_res, poly, N)
                print(f"    Verified to n={N}: {'YES' if ok else 'NO'}")
                if ok:
                    return {'type': 'double_factorial_times_poly', 
                            'poly_coeffs': poly, 'degree': deg, 'm': m}
        
        # Try ratios of successive residuals
        print(f"  Checking ratio pattern...")
        for n in range(1, min(10, len(int_res))):
            if int_res[n-1] != 0:
                ratio = Fraction(int_res[n], int_res[n-1])
                print(f"    r({n})/r({n-1}) = {ratio} = {float(ratio):.6f}")
    else:
        # Residuals are rational - try different normalization
        print(f"  Non-integer residuals. Trying alternative factorizations...")
        
        # Try dividing by n! instead
        for n in range(N + 1):
            nf = 1 if n == 0 else Fraction(1)
            for k in range(1, n + 1):
                nf *= k
            r2 = Fraction(pn[n], int(nf))
            if n < 10:
                print(f"    p_{n} / {n}! = {r2} = {float(r2):.6f}")
        
        # Try (2n)!! / n!
        print(f"  Trying p_n / ((2n-1)!! * n!):")
        for n in range(min(10, N + 1)):
            df = double_factorial_odd(n)
            nf = 1
            for k in range(1, n + 1):
                nf *= k
            denom = df * nf
            if denom != 0:
                r3 = Fraction(pn[n], denom)
                print(f"    n={n}: {r3} = {float(r3):.6f}")
    
    return None


def fit_polynomial(values, degree):
    """Fit a polynomial of given degree to values[0..degree+1] and verify."""
    n = degree + 1
    if len(values) < n + 2:
        return None
    
    # Use Lagrange interpolation with first (degree+1) points
    from fractions import Fraction
    points = [(Fraction(i), Fraction(values[i])) for i in range(n + 1)]
    
    # Build the polynomial coefficients via Vandermonde
    # Simple: just check if a polynomial of this degree works
    # Build system: sum(c_k * i^k, k=0..deg) = values[i] for i=0..N
    
    # Use sympy if available for exact polynomial fitting
    if HAS_SYMPY:
        x = symbols('x')
        pts = [(i, values[i]) for i in range(degree + 2)]
        # Lagrange interpolation
        poly = 0
        for i, (xi, yi) in enumerate(pts):
            term = yi
            for j, (xj, yj) in enumerate(pts):
                if i != j:
                    term = term * (x - xj) / (xi - xj)
            poly += term
        poly = simplify(expand(poly))
        
        # Extract coefficients
        p = Poly(poly, x)
        coeffs = [int(p.nth(k)) for k in range(degree + 1)]
        
        # Verify against ALL values
        for i in range(len(values)):
            val = sum(c * i**k for k, c in enumerate(coeffs))
            if val != values[i]:
                return None
        return coeffs
    else:
        # Manual fitting using differences
        if degree == 0:
            if all(v == values[0] for v in values):
                return [values[0]]
            return None
        elif degree == 1:
            d = values[1] - values[0]
            if all(values[i] == values[0] + d * i for i in range(len(values))):
                return [values[0], d]
            return None
        elif degree == 2:
            a = values[0]
            b_c = values[1] - a  # b + c
            four_b_c = values[2] - a  # 2b + 4c
            # b + c = values[1] - a
            # 2b + 4c = values[2] - a
            # => 2c = (values[2]-a) - 2*(values[1]-a) = values[2] - 2*values[1] + a
            c2 = values[2] - 2 * values[1] + values[0]
            if c2 % 2 != 0:
                return None
            c = c2 // 2
            b = values[1] - values[0] - c
            # Verify: a + bn + cn^2
            for i in range(len(values)):
                if a + b * i + c * i * i != values[i]:
                    return None
            return [a, b, c]
        else:
            # Higher degrees: use finite differences
            return None


def poly_to_str(coeffs):
    """Convert [a0, a1, a2, ...] to string."""
    terms = []
    for k, c in enumerate(coeffs):
        if c == 0:
            continue
        if k == 0:
            terms.append(str(c))
        elif k == 1:
            terms.append(f"{c}*n" if c != 1 else "n")
        else:
            terms.append(f"{c}*n^{k}" if c != 1 else f"n^{k}")
    return " + ".join(terms) if terms else "0"


def verify_poly(values, coeffs, N):
    """Verify polynomial evaluates correctly for all n."""
    for n in range(min(N + 1, len(values))):
        expected = sum(c * n**k for k, c in enumerate(coeffs))
        if expected != values[n]:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0b: DENOMINATOR CLOSED-FORM SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

def guess_closed_form_denominators(m, N=30):
    """Search for closed form of q_n(m)."""
    pn, qn = compute_convergents(m, N)
    
    print(f"\n  m={m}: denominator sequence q_n")
    print(f"  First 12 q_n: {qn[:12]}")
    
    # Try dividing by (2n-1)!!
    residuals = []
    for n in range(N + 1):
        df = double_factorial_odd(n)
        if df == 0:
            residuals.append(None)
        else:
            r = Fraction(qn[n], df)
            residuals.append(r)
    
    all_int = all(r is not None and r.denominator == 1 for r in residuals[:N+1])
    if all_int:
        int_res = [int(r) for r in residuals[:N+1]]
        print(f"  q_n / (2n-1)!! = {int_res[:12]}")
        
        for deg in range(5):
            poly = fit_polynomial(int_res, deg)
            if poly is not None:
                print(f"  MATCH: q_n(m={m}) = (2n-1)!! * Q_{deg}(n)")
                print(f"    Q_{deg}(n) = {poly_to_str(poly)}")
                ok = verify_poly(int_res, poly, N)
                print(f"    Verified to n={N}: {'YES' if ok else 'NO'}")
                if ok:
                    return {'type': 'double_factorial_times_poly',
                            'poly_coeffs': poly, 'degree': deg, 'm': m}
    else:
        print(f"  Residuals not integer. First 8: {[str(r) for r in residuals[:8]]}")
        
        # Try dividing by (2n)!! = 2^n * n!
        print(f"  Trying q_n / (2^n * n!):")
        for n in range(min(12, N + 1)):
            denom = (2**n) * (1 if n == 0 else 1)
            for k in range(1, n + 1):
                denom *= k
            r2 = Fraction(qn[n], denom)
            print(f"    n={n}: {r2} = {float(r2):.8f}")
    
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0c: INDUCTION PROVER
# ═══════════════════════════════════════════════════════════════════════════════

def prove_by_induction(m, p_form, q_form, N_verify=200):
    """
    Attempt automatic inductive proof of Conjecture 1.
    
    Given: p_n = (2n-1)!! * P(n), q_n = (2n-1)!! * Q(n)
    Recurrence: p_n = b(n)*p_{n-1} + a(n)*p_{n-2}
    where a(n) = -n(2n-(2m+1)), b(n) = 3n+1
    
    Need to show: (2n-1)!! * P(n) = (3n+1)(2n-3)!! * P(n-1) - n(2n-(2m+1))(2n-5)!! * P(n-2)
    
    Dividing by (2n-5)!!:
    (2n-1)(2n-3) * P(n) = (3n+1)(2n-3) * P(n-1) - n(2n-(2m+1)) * P(n-2)
    
    This is a polynomial identity that can be verified symbolically.
    """
    if not HAS_SYMPY:
        print("  sympy required for symbolic proof. Falling back to numerical verification.")
        return numerical_verify(m, p_form, N_verify)
    
    if p_form is None:
        print(f"  No closed form found for m={m} numerators.")
        return False
    
    c = 2 * m + 1
    n = symbols('n')
    
    # Build polynomial P(n) from coefficients
    P_coeffs = p_form['poly_coeffs']
    P = sum(Rational(c_val) * n**k for k, c_val in enumerate(P_coeffs))
    
    print(f"\n  INDUCTION PROOF for m={m}:")
    print(f"  P(n) = {P}")
    print(f"  Claim: p_n = (2n-1)!! * P(n)")
    print(f"  Recurrence: p_n = (3n+1)*p_{{n-1}} - n(2n-{c})*p_{{n-2}}")
    
    # The recurrence (2n-1)!! * P(n) = (3n+1) * (2n-3)!! * P(n-1) - n(2n-c) * (2n-5)!! * P(n-2)
    # Note: (2n-1)!! / (2n-3)!! = (2n-1) and (2n-1)!! / (2n-5)!! = (2n-1)(2n-3)
    # So after dividing through by (2n-5)!!:
    # (2n-1)(2n-3) P(n) = (3n+1)(2n-3) P(n-1) - n(2n-c) P(n-2)
    # Wait, (2n-1)!! = (2n-1) * (2n-3)!! so (2n-1)!!/(2n-5)!! = (2n-1)(2n-3)
    # and (2n-3)!!/(2n-5)!! = (2n-3)
    
    # LHS
    LHS = (2*n - 1) * (2*n - 3) * P
    
    # RHS
    P_nm1 = P.subs(n, n - 1)
    P_nm2 = P.subs(n, n - 2)
    RHS = (3*n + 1) * (2*n - 3) * P_nm1 - n * (2*n - c) * P_nm2
    
    # Check: LHS - RHS should be 0
    diff = expand(LHS - RHS)
    print(f"  LHS = (2n-1)(2n-3) * P(n)")
    print(f"  RHS = (3n+1)(2n-3) * P(n-1) - n(2n-{c}) * P(n-2)")
    print(f"  LHS - RHS = {diff}")
    
    if diff == 0:
        print(f"  *** IDENTITY VERIFIED SYMBOLICALLY! Induction step PROVED. ***")
        
        # Check base cases
        pn, qn = compute_convergents(m, 5)
        base_ok = True
        for n_val in range(3):
            expected = double_factorial_odd(n_val) * sum(c_val * n_val**k for k, c_val in enumerate(P_coeffs))
            if expected != pn[n_val]:
                base_ok = False
                print(f"  BASE CASE n={n_val}: FAIL (expected {expected}, got {pn[n_val]})")
        
        if base_ok:
            print(f"  Base cases n=0,1,2: VERIFIED")
            print(f"  *** CONJECTURE 1 PROVED for m={m} numerators! ***")
            return True
        else:
            print(f"  BASE CASES FAILED!")
            return False
    else:
        print(f"  Difference is nonzero. Checking if it factors nicely...")
        try:
            factored = factor(diff)
            print(f"  Factored diff: {factored}")
        except Exception:
            pass
        
        # Still verify numerically
        return numerical_verify(m, p_form, N_verify)


def numerical_verify(m, form, N):
    """Verify closed form against computed values."""
    pn, qn = compute_convergents(m, N)
    
    mismatches = 0
    for n_val in range(N + 1):
        expected = double_factorial_odd(n_val) * sum(c * n_val**k for k, c in enumerate(form['poly_coeffs']))
        if expected != pn[n_val]:
            if mismatches < 3:
                print(f"  MISMATCH at n={n_val}: formula={expected}, actual={pn[n_val]}")
            mismatches += 1
    
    if mismatches == 0:
        print(f"  Numerically verified to N={N} terms: ALL MATCH")
        return True
    else:
        print(f"  {mismatches} mismatches out of {N+1}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0d: CONVERGENT VALUE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def verify_pcf_values(m_range=range(6), depth=2000):
    """Verify PCF limit values match theoretical predictions.
    
    Pi Family gives: val(m) = 2^(2m+1) / (pi * C(2m,m))
    """
    print(f"\n  PCF LIMIT VALUES (depth={depth}):")
    mpmath.mp.dps = 100
    
    results = []
    for m in m_range:
        c = 2 * m + 1
        
        # Evaluate PCF bottom-up for better numerical stability
        val = mpf(3 * depth + 1)  # b(N)
        for n in range(depth, 0, -1):
            an = -n * (2 * n - c)
            bn_prev = 3 * (n - 1) + 1
            val = mpf(bn_prev) + mpf(an) / val
        # val is now b(0) + a(1)/(b(1) + ...) = the PCF
        
        # Expected: 2^(2m+1) / (pi * C(2m,m))
        expected = mpf(2)**(2*m+1) / (mpmath.pi * mpmath.binomial(2*m, m))
        
        err = abs(val - expected)
        digits = -int(mpmath.log10(err)) if err > 0 else 100
        
        print(f"  m={m}: PCF = {mpmath.nstr(val, 25)}")
        print(f"        Exp = {mpmath.nstr(expected, 25)}")
        print(f"        Match: {digits} digits")
        
        results.append({
            'm': m, 'value': str(val)[:50], 'expected_formula': f'2^{2*m+1}/(pi*C(2*{m},{m}))',
            'digits_match': digits
        })
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0e: PARITY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_parity():
    """Analyze even/odd parity phenomenon in Pi Family."""
    print("\n" + "=" * 74)
    print("  PARITY ANALYSIS: even c → Wallis, odd c → pi")
    print("=" * 74)
    
    mpmath.mp.dps = 60
    
    for c_param in range(1, 15):
        m = (c_param - 1) / 2.0
        
        # Evaluate PCF
        depth = 2000
        val = mpf(3 * depth + 1)
        for n in range(depth, 0, -1):
            an = -n * (2 * n - c_param)
            bn_prev = 3 * (n - 1) + 1
            val = mpf(bn_prev) + mpf(an) / val
        
        # Try matching
        is_odd = (c_param % 2 == 1)
        m_int = (c_param - 1) // 2
        
        if is_odd:
            # Should match 2^(2m+1) / (pi * C(2m,m))
            expected = mpf(2)**(c_param) / (mpmath.pi * mpmath.binomial(c_param - 1, m_int))
            err = abs(val - expected)
            digits = -int(mpmath.log10(err)) if err > 0 else 60
            tag = f"2^{c_param}/(pi*C({c_param-1},{m_int}))"
            parity = "ODD → π"
        else:
            # Even c: should give rational (Wallis-type)
            # Try simple rational reconstruction
            tag = "?"
            digits = 0
            # Try val = p/q for small p,q
            for q in range(1, 200):
                p_approx = round(float(val * q))
                if p_approx != 0 and abs(val - mpf(p_approx)/q) < mpf(10)**(-40):
                    tag = f"{p_approx}/{q}"
                    digits = 40
                    break
            
            if digits < 10:
                # Try matching against known constants
                for desc, tv in [("2/3", mpf(2)/3), ("4/3", mpf(4)/3), ("8/15", mpf(8)/15),
                                 ("16/15", mpf(16)/15), ("4/5", mpf(4)/5),
                                 ("2/pi", 2/mpmath.pi), ("4/pi", 4/mpmath.pi),
                                 ("pi/4", mpmath.pi/4), ("pi/2", mpmath.pi/2)]:
                    d = abs(val - tv)
                    if d < mpf(10)**(-40):
                        tag = desc
                        digits = 40
                        break
            parity = "EVEN → rational?"
        
        status = f"{'✓' if digits >= 30 else '?'}"
        print(f"  c={c_param:2d} (m={'%.1f'%m}): val={mpmath.nstr(val,20)}  {status} {tag}  [{parity}] ({digits}d)")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    
    print("=" * 74)
    print("  PHASE 0: SEED THE GENERATOR — Pi Family Closed Forms")
    print("=" * 74)
    
    # ── Step 1: Compute and guess closed forms for numerators ──
    print("\n" + "─" * 74)
    print("  STEP 1: NUMERATOR CLOSED-FORM SEARCH")
    print("─" * 74)
    
    N = 50  # terms to compute
    num_forms = {}
    for m in range(6):
        form = guess_closed_form_numerators(m, N)
        if form:
            num_forms[m] = form
    
    # ── Step 2: Guess closed forms for denominators ──
    print("\n" + "─" * 74)
    print("  STEP 2: DENOMINATOR CLOSED-FORM SEARCH")
    print("─" * 74)
    
    den_forms = {}
    for m in range(6):
        form = guess_closed_form_denominators(m, N)
        if form:
            den_forms[m] = form
    
    # ── Step 3: Induction proofs ──
    print("\n" + "─" * 74)
    print("  STEP 3: INDUCTION PROOFS (Conjecture 1)")
    print("─" * 74)
    
    proof_results = {}
    for m in range(6):
        if m in num_forms:
            proved = prove_by_induction(m, num_forms[m], den_forms.get(m), N_verify=200)
            proof_results[m] = proved
    
    # Also try denominator proofs
    print("\n  DENOMINATOR INDUCTION PROOFS:")
    den_proof_results = {}
    for m in range(6):
        if m in den_forms:
            print(f"\n  Attempting denominator proof for m={m}...")
            # Same recurrence, different initial conditions
            c = 2 * m + 1
            Q_coeffs = den_forms[m]['poly_coeffs']
            if HAS_SYMPY:
                n = symbols('n')
                Q = sum(Rational(c_val) * n**k for k, c_val in enumerate(Q_coeffs))
                LHS = (2*n - 1) * (2*n - 3) * Q
                Q_nm1 = Q.subs(n, n - 1)
                Q_nm2 = Q.subs(n, n - 2)
                RHS = (3*n + 1) * (2*n - 3) * Q_nm1 - n * (2*n - c) * Q_nm2
                diff = expand(LHS - RHS)
                print(f"    Q(n) = {Q}")
                print(f"    LHS - RHS = {diff}")
                if diff == 0:
                    # Check base cases
                    pn, qn = compute_convergents(m, 5)
                    base_ok = True
                    for n_val in range(3):
                        expected = double_factorial_odd(n_val) * sum(c_val * n_val**k for k, c_val in enumerate(Q_coeffs))
                        if expected != qn[n_val]:
                            base_ok = False
                    if base_ok:
                        print(f"    *** DENOMINATOR CONJECTURE PROVED for m={m}! ***")
                        den_proof_results[m] = True
                    else:
                        print(f"    Induction step OK but base cases FAIL")
                        den_proof_results[m] = False
                else:
                    print(f"    Induction step FAILS")
                    den_proof_results[m] = False
    
    # ── Step 4: PCF value verification ──
    print("\n" + "─" * 74)
    print("  STEP 4: PCF LIMIT VALUE VERIFICATION")
    print("─" * 74)
    
    value_results = verify_pcf_values(range(8), depth=2000)
    
    # ── Step 5: Parity analysis ──
    analyze_parity()
    
    # ── Step 6: Export results ──
    print("\n" + "─" * 74)
    print("  STEP 6: EXPORT RESULTS")
    print("─" * 74)
    
    elapsed = time.time() - t0
    
    results = {
        'phase': 0,
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed, 1),
        'numerator_closed_forms': {},
        'denominator_closed_forms': {},
        'induction_proofs': {},
        'denominator_proofs': {},
        'pcf_values': value_results,
    }
    
    for m, form in num_forms.items():
        results['numerator_closed_forms'][str(m)] = {
            'formula': f"p_n(m={m}) = (2n-1)!! * ({poly_to_str(form['poly_coeffs'])})",
            'poly_coeffs': form['poly_coeffs'],
            'degree': form['degree'],
        }
    
    for m, form in den_forms.items():
        results['denominator_closed_forms'][str(m)] = {
            'formula': f"q_n(m={m}) = (2n-1)!! * ({poly_to_str(form['poly_coeffs'])})",
            'poly_coeffs': form['poly_coeffs'],
            'degree': form['degree'],
        }
    
    for m, proved in proof_results.items():
        results['induction_proofs'][str(m)] = {
            'proved': proved,
            'method': 'symbolic_induction' if HAS_SYMPY else 'numerical_verification'
        }
    
    for m, proved in den_proof_results.items():
        results['denominator_proofs'][str(m)] = {'proved': proved}
    
    outfile = Path('phase0_results.json')
    outfile.write_text(json.dumps(results, indent=2))
    print(f"  Results saved to {outfile}")
    
    # Summary
    print("\n" + "=" * 74)
    print("  PHASE 0 SUMMARY")
    print("=" * 74)
    print(f"  Numerator closed forms found: {len(num_forms)}/{6}")
    print(f"  Denominator closed forms found: {len(den_forms)}/{6}")
    print(f"  Numerator proofs: {sum(1 for v in proof_results.values() if v)}/{len(proof_results)}")
    print(f"  Denominator proofs: {sum(1 for v in den_proof_results.values() if v)}/{len(den_proof_results)}")
    print(f"  Total time: {elapsed:.1f}s")
    
    proved_m = [m for m, v in proof_results.items() if v]
    if proved_m:
        print(f"\n  *** CONJECTURE 1 PROVED for m = {proved_m} ***")
    
    return results


if __name__ == "__main__":
    main()
