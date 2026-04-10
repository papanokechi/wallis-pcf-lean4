"""
Ramanujan Agent Search Script v4.7 — The Hypergeometric Pivot
=============================================================
Multi-basis PSLQ scan to identify the quadratic GCF limit V = 1.19737399069...
from GCF(1, 3n^2 + n + 1).

Bases:
  A. Airy-Type:    {Ai(z), Bi(z), Ai'(z), Bi'(z)} at z = 3^{-1/3}
  B. Gamma-Const:  {Gamma(1/3), Gamma(2/3), pi, sqrt(3)}
  C. Lommel:       {s_{mu,nu}(z)} for mu,nu in {1/3, 2/3}
  D. Hypergeometric: 1F2 candidates with parameters from roots of 3n^2+n+1=0

Usage:
    python ramanujan_search_v47.py
"""

import mpmath
from mpmath import (
    mp, mpf, pslq, pi, sqrt, gamma, exp,
    airyai, airybi, besseli, besselk, hyper
)

# High precision for PSLQ scan
mp.dps = 120


# ── GCF Computation (backward recurrence) ──────────────────────────────────

def get_gcf_limit(a_func, b_func, depth=500):
    """Computes the GCF using backward recurrence for stability.
    
    GCF = b(0) + a(1)/(b(1) + a(2)/(b(2) + ...))
    
    Superlinear convergence for quadratic b_n means depth=500
    achieves 120-digit stability (error ~ exp(-n log n)).
    """
    v = mpf(0)
    for n in range(depth, 0, -1):
        v = a_func(n) / (b_func(n) + v)
    return b_func(0) + v


# ── Target value ────────────────────────────────────────────────────────────

a_n = lambda n: mpf(1)
b_n = lambda n: 3 * n**2 + n + 1

target = get_gcf_limit(a_n, b_n)
print(f"Target GCF Limit (120 digits):")
print(f"  V = {mpmath.nstr(target, 50)}")
print()


# ── Basis A: Airy-Type ─────────────────────────────────────────────────────

def scan_airy_basis():
    """Airy functions at z = 3^{-1/3}."""
    z = mpf(3) ** (mpf(-1) / 3)
    
    basis = [
        target,
        mpf(1),
        airyai(z),
        airybi(z),
        airyai(z, derivative=1),
        airybi(z, derivative=1),
    ]
    
    print("Basis A: Airy-Type at z = 3^{-1/3}")
    print(f"  Ai(z)  = {mpmath.nstr(basis[2], 30)}")
    print(f"  Bi(z)  = {mpmath.nstr(basis[3], 30)}")
    print(f"  Ai'(z) = {mpmath.nstr(basis[4], 30)}")
    print(f"  Bi'(z) = {mpmath.nstr(basis[5], 30)}")
    
    rel = pslq(basis, tol=mpf(10) ** (-100))
    if rel:
        print(f"  RELATION FOUND: {rel}")
    else:
        print("  No relation found.")
    print()
    return rel


# ── Basis B: Gamma-Constant ────────────────────────────────────────────────

def scan_gamma_basis():
    """Standard transcendentals of order 1/3."""
    basis = [
        target,
        mpf(1),
        pi,
        gamma(mpf(1) / 3),
        gamma(mpf(2) / 3),
        sqrt(mpf(3)),
        pi ** 2,
        gamma(mpf(1) / 3) ** 2,
    ]
    
    print("Basis B: Gamma-Constant")
    print(f"  Gamma(1/3) = {mpmath.nstr(basis[3], 30)}")
    print(f"  Gamma(2/3) = {mpmath.nstr(basis[4], 30)}")
    
    rel = pslq(basis, tol=mpf(10) ** (-100))
    if rel:
        print(f"  RELATION FOUND: {rel}")
    else:
        print("  No relation found.")
    print()
    return rel


# ── Basis C: Bessel + Lommel-adjacent ──────────────────────────────────────

def scan_bessel_lommel_basis():
    """Bessel ratios and Lommel-adjacent functions."""
    z = mpf(2) / 3
    
    basis = [
        target,
        mpf(1),
        # Standard Bessel ratios at z=2/3
        besseli(mpf(1) / 3, z) / besseli(mpf(4) / 3, z),
        besseli(mpf(4) / 3, z) / besseli(mpf(1) / 3, z),
        besselk(mpf(1) / 3, z) / besselk(mpf(2) / 3, z),
        # Hypergeometric 1F2 candidates
        hyper([1], [mpf(4) / 3, mpf(5) / 3], mpf(1) / 9),
        hyper([1], [mpf(1) / 3, mpf(2) / 3], mpf(1) / 9),
    ]
    
    print("Basis C: Bessel/Lommel-adjacent")
    print(f"  I_{{1/3}}/I_{{4/3}}(2/3) = {mpmath.nstr(basis[2], 30)}")
    print(f"  I_{{4/3}}/I_{{1/3}}(2/3) = {mpmath.nstr(basis[3], 30)}")
    print(f"  K_{{1/3}}/K_{{2/3}}(2/3) = {mpmath.nstr(basis[4], 30)}")
    print(f"  1F2(1; 4/3, 5/3; 1/9)   = {mpmath.nstr(basis[5], 30)}")
    print(f"  1F2(1; 1/3, 2/3; 1/9)   = {mpmath.nstr(basis[6], 30)}")
    
    rel = pslq(basis, tol=mpf(10) ** (-100))
    if rel:
        print(f"  RELATION FOUND: {rel}")
    else:
        print("  No relation found.")
    print()
    return rel


# ── Basis D: Extended Hypergeometric ───────────────────────────────────────

def scan_hypergeometric_basis():
    """Extended Hypergeometric 1F2 / 2F2 scan with varied arguments."""
    basis = [
        target,
        mpf(1),
        pi,
        # 1F2 at z = 1/27 (related to 3^3)
        hyper([1], [mpf(4) / 3, mpf(5) / 3], mpf(1) / 27),
        hyper([mpf(1) / 2], [mpf(4) / 3, mpf(5) / 3], mpf(1) / 27),
        # 1F2 at z = 1/3
        hyper([1], [mpf(4) / 3, mpf(5) / 3], mpf(1) / 3),
        # 2F2 candidates
        hyper([1, 1], [mpf(4) / 3, mpf(5) / 3], mpf(1) / 9),
    ]
    
    print("Basis D: Extended Hypergeometric (1F2, 2F2)")
    for i, v in enumerate(basis):
        print(f"  basis[{i}] = {mpmath.nstr(v, 30)}")
    
    rel = pslq(basis, tol=mpf(10) ** (-100))
    if rel:
        print(f"  RELATION FOUND: {rel}")
    else:
        print("  No relation found.")
    print()
    return rel


# ── Main execution ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("Ramanujan Agent Search v4.7 — The Hypergeometric Pivot")
    print("=" * 70)
    print()
    
    results = {}
    results["A_airy"] = scan_airy_basis()
    results["B_gamma"] = scan_gamma_basis()
    results["C_bessel_lommel"] = scan_bessel_lommel_basis()
    results["D_hypergeometric"] = scan_hypergeometric_basis()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    found_any = False
    for name, rel in results.items():
        if rel:
            print(f"  {name}: RELATION = {rel}")
            found_any = True
        else:
            print(f"  {name}: no relation")
    
    if not found_any:
        print()
        print("  No linear relation found in any basis.")
        print("  Possible conclusions:")
        print("    (a) V is a RATIO of special functions (requires multiplicative PSLQ)")
        print("    (b) V involves higher-order functions not in the current basis")
        print("    (c) V may be a genuinely new transcendental constant")
        print()
        print("  Next step: Submit 120-digit value to ISC with tag 'quadratic GCF limit'")
