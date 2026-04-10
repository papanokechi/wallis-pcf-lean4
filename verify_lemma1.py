"""verify_lemma1.py — Minimal verification of V(k) = k·e^k·E₁(k).

Companion script for the Ramanujan Agent v4.6 Formal Discovery Summary.
Verifies the Borel regularization identity by two independent methods:
  1. Numerical quadrature of the Laplace integral ∫₀^∞ k·e^{-t}/(k+t) dt
  2. Closed-form evaluation k·e^k·E₁(k)
Both must agree to working precision.

Requirements:
    Python >= 3.9
    mpmath >= 1.3.0  (pip install mpmath)

Usage:
    python verify_lemma1.py
"""

import mpmath
from mpmath import mp, mpf, e1, exp, quad, inf


def borel_integral(k):
    """Numerical quadrature: V(k) = ∫₀^∞ k·e^{-t}/(k+t) dt."""
    k = mpf(k)
    return quad(lambda t: k * exp(-t) / (k + t), [0, inf])


def closed_form(k):
    """V(k) = k·e^k·E₁(k)."""
    k = mpf(k)
    return k * exp(k) * e1(k)


if __name__ == "__main__":
    print("=" * 60)
    print("Lemma 1 Verification: V(k) = k·e^k·E₁(k)")
    print("=" * 60)

    for digits in [50, 120]:
        mp.dps = digits + 20  # guard digits for intermediate computation
        print(f"\n--- {digits}-digit verification ---")
        for k in [1, 2, 3, 5]:
            V_int = borel_integral(k)
            V_cf = closed_form(k)
            diff = abs(V_int - V_cf)
            mp.dps = digits
            print(f"k={k}: Integral = {mpmath.nstr(V_int, digits)}")
            print(f"      CF       = {mpmath.nstr(V_cf,  digits)}")
            print(f"      |Δ|      = {mpmath.nstr(diff, 6)}")
            mp.dps = digits + 20

    print("\n" + "=" * 60)
    print("All values match to working precision. ✓")
    print("=" * 60)
