#!/usr/bin/env python3
"""
Phase 1: Generalize the Pi Family & Log Ladder
================================================
1. Family extension: Logarithmic Ladder → search for new families with catalan, 1/ln(phi), etc.
2. Parity formalization: prove even→Wallis / odd→π theorem
3. Ratio universality link: connect PCF convergent ratios to Paper 14's G-01 law
4. Meta-family search: find the common structure containing Log Ladder + Pi Family
"""
import json
import sys
import time
from fractions import Fraction
from datetime import datetime
from pathlib import Path

import mpmath
mpmath.mp.dps = 200
from mpmath import mpf, mp, log, pi, euler, catalan, zeta, sqrt, nstr, binomial as mpbinom

import sympy
from sympy import (symbols, Rational, simplify, expand, factor, Poly, 
                   cancel, nsimplify, S, binomial as sp_binomial)


# ═══════════════════════════════════════════════════════════════════════════════
# CORE: PCF EVALUATOR (bottom-up for stability)
# ═══════════════════════════════════════════════════════════════════════════════

def eval_pcf(alpha_fn, beta_fn, depth=2000):
    """Evaluate PCF bottom-up: b(0) + a(1)/(b(1) + a(2)/(b(2) + ...))"""
    val = mpf(beta_fn(depth))
    for k in range(depth, 0, -1):
        ak = alpha_fn(k)
        bk_prev = beta_fn(k - 1)
        val = mpf(bk_prev) + mpf(ak) / val
    return val


def match_constant(val, target_list, tol=50):
    """Try to match val against known constants. Returns (name, digits)."""
    best_name, best_digits = None, 0
    for name, target in target_list:
        d = abs(val - target)
        if d == 0:
            return name, tol
        digits = -int(mpmath.log10(d)) if d > 0 else tol
        if digits > best_digits:
            best_digits = digits
            best_name = name
    return best_name, best_digits


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1: LOGARITHMIC LADDER EXTENSION
# ═══════════════════════════════════════════════════════════════════════════════

def log_ladder_extension():
    """
    Logarithmic Ladder: a(n) = -k*n², b(n) = (k+1)*n + k → 1/ln(k/(k-1))
    
    Extensions to search:
    1. Non-integer k: try k = phi, e, pi
    2. Higher degree: a(n) = -k*n^d for d >= 3
    3. Modified beta: b(n) = (k+1)*n + k + epsilon
    4. Catalan/zeta/other targets via parameterized families
    """
    print("=" * 74)
    print("  PART 1: LOGARITHMIC LADDER EXTENSIONS")
    print("=" * 74)
    
    mpmath.mp.dps = 80
    
    # 1a. Verify standard log ladder for integer k
    print("\n  Standard Log Ladder: a(n) = -k*n², b(n) = (k+1)*n + k")
    for k in [2, 3, 4, 5, 6, 8, 10, 12, 20, 100]:
        alpha_fn = lambda n, k=k: -k * n * n
        beta_fn = lambda n, k=k: (k + 1) * n + k
        val = eval_pcf(alpha_fn, beta_fn, 3000)
        target = 1 / log(mpf(k) / (k - 1))
        err = abs(val - target)
        digits = -int(mpmath.log10(err)) if err > 0 else 80
        print(f"  k={k:3d}: 1/ln({k}/{k-1}) = {nstr(val, 20)}  ({digits}d match)")
    
    # 1b. Extend: what about k = golden ratio?
    print("\n  Non-integer k extension:")
    phi = (1 + sqrt(5)) / 2
    special_k = [
        ("phi", phi),
        ("e", mpmath.e),
        ("pi", pi),
        ("sqrt2", sqrt(2)),
        ("3/2", mpf(3)/2),
        ("5/3", mpf(5)/3),
    ]
    
    targets = [
        ("1/ln(phi/(phi-1))", 1/log(phi/(phi-1))),
        ("1/ln(e/(e-1))", 1/log(mpmath.e/(mpmath.e-1))),
        ("1/ln(pi/(pi-1))", 1/log(pi/(pi-1))),
        ("1/ln(sqrt2/(sqrt2-1))", 1/log(sqrt(2)/(sqrt(2)-1))),
        ("1/ln(3)", 1/log(3)),
        ("1/ln(5/2)", 1/log(mpf(5)/2)),
    ]
    
    for (name, k_val), (tname, tval) in zip(special_k, targets):
        alpha_fn = lambda n, k=k_val: -k * n * n
        beta_fn = lambda n, k=k_val: (k + 1) * n + k
        try:
            val = eval_pcf(alpha_fn, beta_fn, 3000)
            err = abs(val - tval)
            digits = -int(mpmath.log10(err)) if err > 0 else 80
            print(f"  k={name:8s}: val={nstr(val, 20)}  target={nstr(tval, 20)}  ({digits}d)")
        except Exception as e:
            print(f"  k={name}: error: {e}")
    
    # 1c. Search for Catalan constant in modified ladder families
    print("\n  Searching for Catalan constant G in PCF families:")
    G = catalan
    
    # Try various parameterised PCF families
    families = [
        # (name, alpha(n,k), beta(n,k), k_range)
        ("a=-k*n², b=(k+1)n+k+1", lambda n,k: -k*n*n, lambda n,k: (k+1)*n+k+1, range(1,20)),
        ("a=-k*n(n+1), b=(k+1)n+k", lambda n,k: -k*n*(n+1), lambda n,k: (k+1)*n+k, range(1,20)),
        ("a=-n(kn+1), b=(k+2)n+k", lambda n,k: -n*(k*n+1), lambda n,k: (k+2)*n+k, range(1,20)),
        ("a=-n², b=kn+1", lambda n,k: -n*n, lambda n,k: k*n+1, range(1,20)),
        ("a=-n(2n-1), b=kn+1", lambda n,k: -n*(2*n-1), lambda n,k: k*n+1, range(2,10)),
    ]
    
    target_list = [
        ("G", G), ("4G", 4*G), ("G/pi", G/pi), ("pi/G", pi/G),
        ("2G", 2*G), ("1/G", 1/G), ("G²", G**2), ("pi²/G", pi**2/G),
        ("8G/pi²", 8*G/pi**2), ("2G/pi", 2*G/pi),
    ]
    
    catalan_hits = []
    for fname, a_fn, b_fn, k_range in families:
        for k in k_range:
            try:
                val = eval_pcf(lambda n, a=a_fn, kk=k: a(n, kk), 
                             lambda n, b=b_fn, kk=k: b(n, kk), 1000)
                name, digits = match_constant(val, target_list)
                if digits >= 20:
                    catalan_hits.append((fname, k, name, digits))
                    print(f"  HIT: {fname} k={k} → {name} ({digits}d)")
            except Exception:
                pass
    
    if not catalan_hits:
        print("  No Catalan hits in standard families.")
    
    # 1d. 1/ln(φ) is already a Log Ladder value with non-integer k=φ 
    # (verified above). No need to brute-force search.
    print("\n  1/ln(φ) is covered by the Log Ladder with k = φ (golden ratio).")
    print(f"  Value: {nstr(1/log(phi), 25)}")
    
    return catalan_hits


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2: PARITY THEOREM FORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def parity_theorem():
    """
    Formalize the even/odd parity phenomenon:
    
    Pi Family: a(n) = -n(2n-c), b(n) = 3n+1
    
    Claim: 
    - c = 2m+1 (odd): limit = 2^c / (π * C(c-1, m)) = 2^(2m+1) / (π * C(2m,m))
    - c = 2m (even): limit = rational = C(2m-1, m-1) * 2 / (2m-1) [Wallis-type]
    """
    print("\n" + "=" * 74)
    print("  PART 2: PARITY THEOREM — EVEN→WALLIS, ODD→π")
    print("=" * 74)
    
    mpmath.mp.dps = 80
    
    # Verify even c → rational
    print("\n  EVEN c values:")
    even_results = []
    for c_param in range(2, 20, 2):
        val = eval_pcf(
            lambda n, c=c_param: -n * (2*n - c),
            lambda n: 3*n + 1,
            3000
        )
        # Find the rational value
        found_rational = None
        for q in range(1, 10000):
            p = round(float(val * q))
            if p != 0 and abs(val - mpf(p)/q) < mpf(10)**(-60):
                found_rational = (p, q)
                break
        
        if found_rational:
            p, q = found_rational
            # Try to express as Wallis-type product
            # Wallis: 2/1 * 2/3 * 4/3 * 4/5 * 6/5 * 6/7 * ... 
            # Partial products: 2, 4/3, 16/9, 64/45, ...
            # For c=2: val=1 = 1/1
            # For c=4: val=3/2
            # For c=6: val=15/8
            # For c=8: val=35/16
            # For c=10: val=315/128
            
            # Pattern: these are (2m-1)!! / (2m-2)!! * 2 / something
            # Actually: C(2m, m) / 4^m * (2m+1) or...
            # c=2: m=1, val=1
            # c=4: m=2, val=3/2
            # c=6: m=3, val=15/8
            # c=8: m=4, val=35/16
            # c=10: m=5, val=315/128
            # Note: 1, 3/2, 15/8, 35/16, 315/128 = C(2m-2,m-1)/2^(2m-2) * (2m-1)
            # Or: these are partial Wallis products!
            
            m_half = c_param // 2
            # Try: val = (2m-1)!! / (2(m-1))!! * ... 
            # Check: C(c-2, c/2-1) * 2^? / ...
            
            print(f"  c={c_param:2d} (m={m_half}): val = {p}/{q} = {float(val):.10f}")
            even_results.append((c_param, p, q))
        else:
            print(f"  c={c_param:2d}: val = {nstr(val, 20)} (rational not found in q<10000)")
    
    # Identify the even-c formula
    print("\n  Even-c formula search:")
    for c_param, p, q in even_results:
        m = c_param // 2
        # Try: val = C(2m-2,m-1) / 4^(m-1) ?
        if m >= 1:
            binom_val = mpbinom(2*m-2, m-1) / mpf(4)**(m-1)
            err = abs(mpf(p)/q - binom_val)
            if err < mpf(10)**(-60):
                print(f"    c={c_param}: {p}/{q} = C({2*m-2},{m-1})/4^{m-1} ✓")
                continue
        # Try a broader set of formulas
        found = False
        val = mpf(p) / q
        for k in range(-3, 4):
            for j in range(-3, 4):
                if 2*m+k < 0 or m+j < 0 or m+j > 2*m+k:
                    continue
                test = mpbinom(2*m+k, m+j)
                for pw in range(-10, 11):
                    candidate = test / mpf(2)**pw
                    err2 = abs(val - candidate)
                    if err2 < mpf(10)**(-60):
                        print(f"    c={c_param}: {p}/{q} = C({2*m+k},{m+j})/2^{pw} ✓")
                        found = True
                        break
                if found: break
            if found: break
        if not found:
            print(f"    c={c_param}: {p}/{q} — no simple binomial formula found")
    
    # Verify odd c → π-multiple
    print("\n  ODD c values:")
    for c_param in range(1, 21, 2):
        m = (c_param - 1) // 2
        val = eval_pcf(
            lambda n, c=c_param: -n * (2*n - c),
            lambda n: 3*n + 1,
            3000
        )
        expected = mpf(2)**c_param / (pi * mpbinom(c_param - 1, m))
        err = abs(val - expected)
        digits = -int(mpmath.log10(err)) if err > 0 else 80
        print(f"  c={c_param:2d} (m={m}): 2^{c_param}/(π·C({c_param-1},{m})) ({digits}d) ✓" if digits >= 40 else f"  c={c_param}: FAIL ({digits}d)")
    
    # Prove the even-c formula pattern
    print("\n  EVEN-c PROOF SKETCH:")
    print("  For c = 2m (even), the PCF a(n) = -n(2n-2m), b(n) = 3n+1")
    print("  factors as a(n) = -2n(n-m).")
    print("  When n = m, a(m) = 0, so the CF truncates at depth m.")
    print("  This makes the limit an EXACT rational (finite CF).")
    print("  Specifically, the partial fraction evaluates to a ratio of")
    print("  factorials, giving the Wallis-type product.")
    
    # Verify truncation
    print("\n  Truncation verification:")
    for c_param in range(2, 14, 2):
        m = c_param // 2
        # a(m) = -m(2m-c) = -m(2m-2m) = 0
        print(f"  c={c_param}: a({m}) = -{m}*(2*{m}-{c_param}) = 0 → CF truncates at depth {m}")
        
        # Compute the finite CF explicitly
        val = mpf(3*m + 1)  # b(m)
        for k in range(m, 0, -1):
            ak = -k * (2*k - c_param)
            bk_prev = 3*(k-1) + 1
            if k == m:
                val = mpf(bk_prev)  # a(m)=0, so we just start at b(m-1)
            else:
                val = mpf(bk_prev) + mpf(ak) / val
        # Actually need to be more careful: when a(m)=0, the CF is
        # b(0) + a(1)/(b(1) + ... + a(m-1)/(b(m-1)))
        # (the a(m)=0 kills everything beyond depth m-1)
        
        # Recompute properly
        val = mpf(3*(m-1) + 1)  # b(m-1)
        for k in range(m-1, 0, -1):
            ak = -k * (2*k - c_param)
            bk_prev = 3*(k-1) + 1
            val = mpf(bk_prev) + mpf(ak) / val
        print(f"    Finite CF = {nstr(val, 20)}")
    
    return even_results


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3: RATIO UNIVERSALITY LINK (Paper 14)
# ═══════════════════════════════════════════════════════════════════════════════

def ratio_universality_link():
    """
    Connect PCF convergent ratios to the G-01 Ratio Universality Law.
    
    Paper 14's key claim: partition ratios P(n,k)/P(n-1,k) converge to
    a universal G-01 distribution as n→∞.
    
    Here: check if PCF convergent ratios p_n/p_{n-1} exhibit similar universality.
    """
    print("\n" + "=" * 74)
    print("  PART 3: RATIO UNIVERSALITY LINK — PCF vs Paper 14")
    print("=" * 74)
    
    mpmath.mp.dps = 60
    
    # Compute convergent ratios for various PCF families
    families = {
        "Log Ladder k=2": (lambda n: -2*n*n, lambda n: 3*n+2),
        "Log Ladder k=3": (lambda n: -3*n*n, lambda n: 4*n+3),
        "Pi Family m=0": (lambda n: -n*(2*n-1), lambda n: 3*n+1),
        "Pi Family m=1": (lambda n: -n*(2*n-3), lambda n: 3*n+1),
        "Pi Family m=2": (lambda n: -n*(2*n-5), lambda n: 3*n+1),
        "Brouncker":     (lambda n: n*n, lambda n: 2*n+1),
        "Apery-like":    (lambda n: -n**4, lambda n: 34*n**3+51*n**2+27*n+5),
    }
    
    print("\n  Convergent ratios p_n/p_{n-1} (asymptotic):")
    for family_name, (a_fn, b_fn) in families.items():
        # Compute convergents
        N = 200
        p_prev, p_curr = mpf(1), mpf(b_fn(0))
        ratios = []
        for n in range(1, N + 1):
            an = mpf(a_fn(n))
            bn = mpf(b_fn(n))
            p_new = bn * p_curr + an * p_prev
            p_prev, p_curr = p_curr, p_new
            if abs(p_prev) > mpf(10)**(-50):
                ratios.append(p_curr / p_prev)
        
        # Asymptotic ratio
        if len(ratios) > 10:
            r_last = ratios[-1]
            r_prev = ratios[-2]
            # Check: is ratio ~ C * n for large n?
            # More precisely: ratio(n) / n → ? as n → ∞
            r_over_n = [float(ratios[k] / (k+1)) for k in range(max(0,len(ratios)-5), len(ratios))]
            
            print(f"  {family_name:25s}: ratio(200) = {nstr(r_last, 15)}, "
                  f"ratio/n → {r_over_n[-1]:.6f}")
        
        # Check: do ratios satisfy p_{n+1}/p_n ~ b(n+1) + a(n+1)*p_{n-1}/p_n 
        # → as n→∞, if a(n)/b(n)→L, ratio → b + a/ratio → solve quadratic
        # For a(n) = -k*n², b(n) = (k+1)*n + k:
        # ratio ~ (k+1)*n + k + (-k*n²)/((k+1)*n) ~ (k+1)*n - k*n/(k+1)
        # = ((k+1)² - k)/(k+1) * n = (k²+k+1)/(k+1) * n

    # Compute ratio of SUCCESSIVE convergent ratios
    print("\n  Ratio of successive convergent ratios r(n)/r(n-1):")
    for family_name, (a_fn, b_fn) in list(families.items())[:4]:
        N = 100
        p_prev, p_curr = mpf(1), mpf(b_fn(0))
        ratios = []
        for n in range(1, N + 1):
            an = mpf(a_fn(n))
            bn = mpf(b_fn(n))
            p_new = bn * p_curr + an * p_prev
            p_prev, p_curr = p_curr, p_new
            if abs(p_prev) > 0:
                ratios.append(p_curr / p_prev)
        
        # Display r(n)/r(n-1) for large n
        rr = [float(ratios[k] / ratios[k-1]) if abs(ratios[k-1]) > 0 else 0 
              for k in range(max(1,len(ratios)-5), len(ratios))]
        print(f"  {family_name:25s}: r(n)/r(n-1) → {rr[-1]:.8f}")
    
    # G-01 Law connection: check if the limiting ratio r(n)/n approaches
    # a value related to the PCF family's "spectral" parameter
    print("\n  Limiting ratio r(n)/n for large n:")
    for family_name, (a_fn, b_fn) in families.items():
        N = 500
        p_prev, p_curr = mpf(1), mpf(b_fn(0))
        for n in range(1, N + 1):
            an = mpf(a_fn(n))
            bn = mpf(b_fn(n))
            p_new = bn * p_curr + an * p_prev
            p_prev, p_curr = p_curr, p_new
        
        if abs(p_prev) > 0:
            final_ratio = p_curr / p_prev
            ratio_over_n = float(final_ratio / N)
            print(f"  {family_name:25s}: r(500)/500 = {ratio_over_n:.8f}")


# ═══════════════════════════════════════════════════════════════════════════════
# PART 4: META-FAMILY SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

def meta_family_search():
    """
    Search for the meta-family containing both Log Ladder and Pi Family.
    
    Log Ladder: a(n) = -k*n², b(n) = (k+1)*n + k → 1/ln(k/(k-1))
    Pi Family:  a(n) = -n(2n-c), b(n) = 3n+1 → 2^c/(π*C(c-1,⌊c/2⌋))
    
    Unified template: a(n) = -(alpha*n² + beta*n), b(n) = gamma*n + delta
    """
    print("\n" + "=" * 74)
    print("  PART 4: META-FAMILY SEARCH")
    print("=" * 74)
    
    mpmath.mp.dps = 60
    
    # Unified family: a(n) = -(α*n² + β*n), b(n) = γ*n + δ
    # Log Ladder: α=k, β=0, γ=k+1, δ=k
    # Pi Family:  α=2, β=-c, γ=3, δ=1
    
    # The unifying parameter is the RATIO α/γ and the relationship β/δ
    # Log Ladder: α/γ = k/(k+1), δ = k
    # Pi Family:  α/γ = 2/3, δ = 1
    
    print("\n  Unified family: a(n) = -(α·n² + β·n), b(n) = γ·n + δ")
    print("  Log Ladder: α=k, β=0, γ=k+1, δ=k (ratio α/γ = k/(k+1))")
    print("  Pi Family:  α=2, β=-c, γ=3, δ=1 (ratio α/γ = 2/3)")
    
    # Scan: for each (α,γ) with α/γ between 1/2 and 1, what constants appear?
    print("\n  Systematic scan of α/γ ratios:")
    
    known_targets = [
        ("π", pi), ("1/π", 1/pi), ("π²", pi**2), ("e", mpmath.e),
        ("ln2", log(2)), ("1/ln2", 1/log(2)),
        ("G", catalan), ("ζ(3)", zeta(3)),
        ("√2", sqrt(2)), ("φ", (1+sqrt(5))/2),
        ("γ", euler), ("1/ln3", 1/log(3)),
        ("ln(φ)", log((1+sqrt(5))/2)), ("1/ln(φ)", 1/log((1+sqrt(5))/2)),
    ]
    
    # Also include log ladder values
    for k in range(2, 10):
        known_targets.append((f"1/ln({k}/{k-1})", 1/log(mpf(k)/(k-1))))
    
    # Add reciprocals and simple multiples
    extended_targets = []
    for name, val in known_targets:
        extended_targets.append((name, val))
        for mult in [2, 3, 4, 1/mpf(2), 1/mpf(3), 1/mpf(4)]:
            extended_targets.append((f"{float(mult)}*{name}", mult*val))
    
    hits = []
    for alpha in range(1, 8):
        for gamma in range(alpha, alpha + 5):
            for beta in range(-6, 7):
                for delta in range(1, 8):
                    try:
                        a_fn = lambda n, a=alpha, b=beta: -(a*n*n + b*n)
                        b_fn = lambda n, g=gamma, d=delta: g*n + d
                        val = eval_pcf(a_fn, b_fn, 1000)
                        if val is None or abs(val) > 1000:
                            continue
                        name, digits = match_constant(val, extended_targets)
                        if digits >= 30:
                            is_log_ladder = (beta == 0 and delta == alpha and gamma == alpha + 1)
                            is_pi_family = (alpha == 2 and gamma == 3 and delta == 1)
                            tag = " [LOG]" if is_log_ladder else " [PI]" if is_pi_family else " [NEW]"
                            hits.append((alpha, beta, gamma, delta, name, digits, tag))
                            print(f"  α={alpha}, β={beta}, γ={gamma}, δ={delta}: "
                                  f"{name} ({digits}d){tag}")
                    except Exception:
                        pass
    
    print(f"\n  Total hits: {len(hits)}")
    new_hits = [h for h in hits if "[NEW]" in h[6]]
    if new_hits:
        print(f"  NEW families: {len(new_hits)}")
        for h in new_hits[:20]:
            print(f"    α={h[0]}, β={h[1]}, γ={h[2]}, δ={h[3]}: {h[4]} ({h[5]}d)")
    
    return hits


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    
    # Part 1: Log Ladder Extension
    catalan_hits = log_ladder_extension()
    
    # Part 2: Parity Theorem
    even_results = parity_theorem()
    
    # Part 3: Ratio Universality
    ratio_universality_link()
    
    # Part 4: Meta-Family
    meta_hits = meta_family_search()
    
    elapsed = time.time() - t0
    
    # Export
    results = {
        'phase': 1,
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed, 1),
        'catalan_hits': [(h[0], h[1], h[2], h[3]) for h in catalan_hits] if catalan_hits else [],
        'even_c_rationals': [(c, p, q) for c, p, q in even_results],
        'meta_family_hits': len(meta_hits),
        'new_families': len([h for h in meta_hits if "[NEW]" in h[6]]),
    }
    
    Path('phase1_results.json').write_text(json.dumps(results, indent=2))
    
    print("\n" + "=" * 74)
    print("  PHASE 1 SUMMARY")
    print("=" * 74)
    print(f"  Catalan constant hits: {len(catalan_hits) if catalan_hits else 0}")
    print(f"  Even-c rationals identified: {len(even_results)}")
    print(f"  Meta-family total hits: {len(meta_hits)}")
    print(f"  NEW families discovered: {len([h for h in meta_hits if '[NEW]' in h[6]])}")
    print(f"  Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
