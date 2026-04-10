"""Automated smoke tests for the PCF Gauss CF identification analysis.

Run with:  pytest tests/test_phase2.py -v
"""
from fractions import Fraction
import math

import pytest


# ---------------------------------------------------------------------------
# Helpers (pure-Python, no external deps beyond stdlib)
# ---------------------------------------------------------------------------

def double_factorial_odd(n: int) -> int:
    """(2n-1)!! = 1*3*5*...*(2n-1)."""
    r = 1
    for k in range(1, 2 * n, 2):
        r *= k
    return r


def cf_unit_coefficients(N: int = 20) -> list:
    """Return c_1 .. c_N, the unit-denominator equivalence-transform coefficients.

    Our CF:  b_0 + a_1/(b_1 + a_2/(b_2 + ...))
    with a(n) = -n(2n-3), b(n) = 3n+1.

    Equivalence transform to  b_0 + c_1/(1 + c_2/(1 + ...)):
        c_1 = a_1/b_1,  c_k = a_k / (b_{k-1} b_k)  for k >= 2.
    """
    an = [0] + [-n * (2 * n - 3) for n in range(1, N + 1)]
    bn = [3 * n + 1 for n in range(N + 1)]
    c = [None]  # 1-indexed
    c.append(Fraction(an[1], bn[1]))
    for k in range(2, N + 1):
        c.append(Fraction(an[k], bn[k - 1] * bn[k]))
    return c


# ---------------------------------------------------------------------------
# Test 1: CF coefficients c_1..c_6 match exact rational values
# ---------------------------------------------------------------------------

EXPECTED_COEFFS = {
    1: Fraction(1, 4),
    2: Fraction(-1, 14),
    3: Fraction(-9, 70),
    4: Fraction(-2, 13),
    5: Fraction(-35, 208),
    6: Fraction(-27, 152),
}


def test_cf_coefficients():
    """Verify the first 6 unit-denominator CF coefficients are exact rationals."""
    c = cf_unit_coefficients(10)
    for k, expected in EXPECTED_COEFFS.items():
        assert c[k] == expected, (
            f"c_{k}: got {c[k]}, expected {expected}"
        )


# ---------------------------------------------------------------------------
# Test 2: Gauss residual is large (CF is NOT a Gauss CF)
# ---------------------------------------------------------------------------

def test_gauss_residual():
    """Solve the 3-equation Gauss system numerically and verify t_4 != c_4.

    The Gauss CF for _2F1(A+1,B;C+1;z)/_2F1(A,B;C;z) has coefficients
    t_k determined by (A,B,C).  Matching t_1=c_1, t_2=c_2, t_3=c_3
    gives (A,B,C).  The CHECK equation is t_4 = c_4.
    """
    from scipy.optimize import fsolve

    c = cf_unit_coefficients(10)

    def equations(vars):
        A, B, C = vars
        eq1 = (A + 1) * (C - B + 1) / (C * (C + 1)) - float(c[1])
        eq2 = (B + 1) * (C - A + 1) / ((C + 1) * (C + 2)) - float(c[2])
        eq3 = (A + 2) * (C - B + 2) / ((C + 2) * (C + 3)) - float(c[3])
        return [eq1, eq2, eq3]

    # Try several starting points; keep solutions with low residual on eqs 1-3
    best_residual = None
    for A0 in [-2, -1, 0, 1]:
        for B0 in [-1, 0, 1]:
            for C0 in [0.5, 2, 4]:
                try:
                    sol, info, ier, _ = fsolve(equations, [A0, B0, C0],
                                               full_output=True)
                    if ier != 1:
                        continue
                    if max(abs(v) for v in equations(sol)) > 1e-8:
                        continue
                    A, B, C = sol
                    t4 = (B + 2) * (C - A + 2) / ((C + 3) * (C + 4))
                    resid = abs(t4 - float(c[4]))
                    if best_residual is None or resid > best_residual:
                        best_residual = resid
                except Exception:
                    pass

    assert best_residual is not None, "No numerical solution found"
    # The residual should be huge (~5.9), proving non-Gauss
    assert best_residual > 1.0, (
        f"Gauss residual {best_residual:.4f} is unexpectedly small; "
        "expected > 1.0 to confirm non-Gauss"
    )


# ---------------------------------------------------------------------------
# Test 3: Series convergence to pi/4
# ---------------------------------------------------------------------------

def test_series_convergence():
    r"""Verify the partial sum of the series

        pi/4 = 1 - sum_{k=1}^{100} k! / ((2k-1)!! (k^2+3k+1)(k^2+k-1))

    matches pi/4 to within 1e-12.
    """
    s = 1.0
    for k in range(1, 101):
        df = double_factorial_odd(k)
        poly_hi = k * k + 3 * k + 1
        poly_lo = k * k + k - 1
        term = math.factorial(k) / (df * poly_hi * poly_lo)
        s -= term

    err = abs(s - math.pi / 4)
    assert err < 1e-12, f"|partial_sum - pi/4| = {err:.2e}, expected < 1e-12"


# ---------------------------------------------------------------------------
# Test 4 (bonus): p_n formula verification via CF recurrence
# ---------------------------------------------------------------------------

def test_pn_formula():
    """Verify p_n = (2n-1)!! * (n^2+3n+1) satisfies the CF recurrence."""
    for n in range(2, 16):
        pn = double_factorial_odd(n) * (n ** 2 + 3 * n + 1)
        pn1 = double_factorial_odd(n - 1) * ((n - 1) ** 2 + 3 * (n - 1) + 1)
        pn2 = double_factorial_odd(n - 2) * ((n - 2) ** 2 + 3 * (n - 2) + 1)
        bn = 3 * n + 1
        an = -n * (2 * n - 3)
        rhs = bn * pn1 + an * pn2
        assert pn == rhs, f"Recurrence failed at n={n}: {pn} != {rhs}"


# ---------------------------------------------------------------------------
# Test 5 (bonus): Series ratio formula
# ---------------------------------------------------------------------------

def test_series_ratio():
    """Verify t_{k+1}/t_k = (k+1)(k^2+k-1) / ((2k+1)(k^2+5k+5))."""
    for k in range(1, 15):
        tk_num = Fraction(math.factorial(k))
        tk_den = Fraction(
            double_factorial_odd(k) * (k ** 2 + 3 * k + 1) * (k ** 2 + k - 1)
        )
        tk1_num = Fraction(math.factorial(k + 1))
        tk1_den = Fraction(
            double_factorial_odd(k + 1)
            * ((k + 1) ** 2 + 3 * (k + 1) + 1)
            * ((k + 1) ** 2 + (k + 1) - 1)
        )
        ratio = (tk1_num * tk_den) / (tk1_den * tk_num)
        expected = Fraction(
            (k + 1) * (k ** 2 + k - 1), (2 * k + 1) * (k ** 2 + 5 * k + 5)
        )
        assert ratio == expected, f"Ratio mismatch at k={k}"
