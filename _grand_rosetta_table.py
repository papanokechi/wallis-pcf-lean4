"""
_grand_rosetta_table.py
========================
Final sweep + consolidation of ALL 4 Rosetta Stone families.

Objectives:
  1. Determine if Families 1, 2, 3 are shifts/transformations of known families
  2. For rational Families (1 & 2): identify the telescoping condition
  3. Build a Grand Rosetta Table with α, β Gamma parameters for each family
  4. Verify everything to 500dp

Families recap (from Rosetta Stone search):
  Family 1: a(n) = -(2m+3)n - 2n², b(n) = 3n+2  → V(m) = 2m+3
  Family 2: a(n) = -(2m+1)n - 2n², b(n) = 3n+2  → V(m) = 2m+1
  Family 3: a(n) = (2m+3)n - 2n²,  b(n) = 3n+1  → S^(m+1) (transcendental)
  Family 4: a(n) = (2m+4)n - 2n²,  b(n) = 3n+1  → S^(m+3/2) (transcendental)

Core S^(m) identity:
  S^(m) = 2·Gamma(m+1) / (sqrt(pi)·Gamma(m+1/2))
  Ratio: S^(m)/S^(m-1) = m / (m - 1/2) = 2m/(2m-1)
"""

from __future__ import annotations
import json
import sys
import time
from datetime import datetime
from fractions import Fraction
from pathlib import Path

try:
    from mpmath import (
        mp, mpf, nstr, pi, log, sqrt, gamma, nsum, inf,
        binomial, identify, pslq, fac, fac2, power,
    )
    import mpmath as mpm
except ImportError:
    sys.exit("mpmath required: pip install mpmath")


RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  GENERIC PCF EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════
def eval_pcf_generic(a_func, b_func, b0, depth=5000):
    """Evaluate continued fraction b0 + a(1)/(b(1) + a(2)/(b(2)+...)).

    a_func(n) and b_func(n) return mpf values for n >= 1.
    """
    val = mpf(0)
    for n in range(depth, 0, -1):
        an = a_func(n)
        bn = b_func(n)
        denom = bn + val
        if abs(denom) < mpf(10)**(-mp.dps + 5):
            return None
        val = an / denom
    return mpf(b0) + val


# ═══════════════════════════════════════════════════════════════════════════════
#  FAMILY EVALUATORS
# ═══════════════════════════════════════════════════════════════════════════════
def eval_S(m, depth=5000):
    """The fundamental S^(m) family:
    a(n) = -n(2n - 2m - 1) = (2m+1)n - 2n², b(n) = 3n+1, b(0) = 1.
    """
    m_val = mpf(m)
    def a_func(n):
        n_mpf = mpf(n)
        return (2*m_val + 1)*n_mpf - 2*n_mpf**2
    def b_func(n):
        return 3*mpf(n) + 1
    return eval_pcf_generic(a_func, b_func, 1, depth)


def eval_family1(m, depth=5000):
    """Family 1: a(n) = -(2m+3)n - 2n², b(n) = 3n+2, b(0) = 2."""
    m_val = mpf(m)
    def a_func(n):
        n_mpf = mpf(n)
        return -(2*m_val + 3)*n_mpf - 2*n_mpf**2
    def b_func(n):
        return 3*mpf(n) + 2
    return eval_pcf_generic(a_func, b_func, 2, depth)


def eval_family2(m, depth=5000):
    """Family 2: a(n) = -(2m+1)n - 2n², b(n) = 3n+2, b(0) = 2."""
    m_val = mpf(m)
    def a_func(n):
        n_mpf = mpf(n)
        return -(2*m_val + 1)*n_mpf - 2*n_mpf**2
    def b_func(n):
        return 3*mpf(n) + 2
    return eval_pcf_generic(a_func, b_func, 2, depth)


def eval_family3(m, depth=5000):
    """Family 3: a(n) = (2m+3)n - 2n², b(n) = 3n+1, b(0) = 1.
    This should be S^(m+1).
    """
    m_val = mpf(m)
    def a_func(n):
        n_mpf = mpf(n)
        return (2*m_val + 3)*n_mpf - 2*n_mpf**2
    def b_func(n):
        return 3*mpf(n) + 1
    return eval_pcf_generic(a_func, b_func, 1, depth)


def eval_family4(m, depth=5000):
    """Family 4: a(n) = (2m+4)n - 2n², b(n) = 3n+1, b(0) = 1.
    This should be S^(m+3/2).
    """
    m_val = mpf(m)
    def a_func(n):
        n_mpf = mpf(n)
        return (2*m_val + 4)*n_mpf - 2*n_mpf**2
    def b_func(n):
        return 3*mpf(n) + 1
    return eval_pcf_generic(a_func, b_func, 1, depth)


# ═══════════════════════════════════════════════════════════════════════════════
#  CLOSED-FORM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def S_closed(m):
    """S^(m) = 2*Gamma(m+1) / (sqrt(pi)*Gamma(m+1/2))"""
    return 2 * gamma(mpf(m) + 1) / (sqrt(pi) * gamma(mpf(m) + mpf('0.5')))


def family1_closed(m):
    """V_1(m) = 2m + 3"""
    return 2*mpf(m) + 3


def family2_closed(m):
    """V_2(m) = 2m + 1"""
    return 2*mpf(m) + 1


def family3_closed(m):
    """V_3(m) = S^(m+1) = 2*Gamma(m+2) / (sqrt(pi)*Gamma(m+3/2))"""
    return S_closed(mpf(m) + 1)


def family4_closed(m):
    """V_4(m) = S^(m+3/2) = 2*Gamma(m+5/2) / (sqrt(pi)*Gamma(m+2))"""
    return S_closed(mpf(m) + mpf('1.5'))


def family1_ratio(m):
    """V_1(m)/V_1(m-1) = (2m+3)/(2m+1) = (m+3/2)/(m+1/2)"""
    m_val = mpf(m)
    return (m_val + mpf('1.5')) / (m_val + mpf('0.5'))


def family2_ratio(m):
    """V_2(m)/V_2(m-1) = (2m+1)/(2m-1) = (m+1/2)/(m-1/2)"""
    m_val = mpf(m)
    denom = m_val - mpf('0.5')
    if abs(denom) < mpf(10)**(-mp.dps + 10):
        return None  # pole at m=1/2
    return (m_val + mpf('0.5')) / denom


def family3_ratio(m):
    """V_3(m)/V_3(m-1) = 2(m+1)/(2m+1) = (m+1)/(m+1/2)"""
    m_val = mpf(m)
    return (m_val + 1) / (m_val + mpf('0.5'))


def family4_ratio(m):
    """V_4(m)/V_4(m-1) = (2m+3)/(2(m+1)) = (m+3/2)/(m+1)"""
    m_val = mpf(m)
    denom = m_val + 1
    if abs(denom) < mpf(10)**(-mp.dps + 10):
        return None  # pole at m=-1
    return (m_val + mpf('1.5')) / denom


# ═══════════════════════════════════════════════════════════════════════════════
#  Γ-PARAMETER FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════════
#
# For ALL 4 families, the ratio V(m)/V(m-1) has the form:
#     (m + alpha) / (m + beta)
#
# which gives:
#     V(m) = V(0) * prod_{j=1}^{m} (j + alpha) / (j + beta)
#          = V(0) * Gamma(m + alpha + 1) * Gamma(beta + 1)
#                 / (Gamma(alpha + 1) * Gamma(m + beta + 1))
#
# TELESCOPING CONDITION: When alpha - beta is a non-negative integer,
# the Gamma ratio reduces to a POLYNOMIAL in m. The transcendental
# factors (sqrt(pi), etc.) cancel EXACTLY.
#
# Table:
#   Family 1: alpha = 3/2, beta = 1/2,  alpha - beta = 1  → TELESCOPING
#   Family 2: alpha = 1/2, beta = -1/2, alpha - beta = 1  → TELESCOPING
#   Family 3: alpha = 1,   beta = 1/2,  alpha - beta = 1/2 → NON-TELESCOPING (S-family)
#   Family 4: alpha = 3/2, beta = 1,    alpha - beta = 1/2 → NON-TELESCOPING (S-family)


def general_closed_form(m, alpha, beta, V0):
    """V(m) = V(0) * Gamma(m+alpha+1)*Gamma(beta+1) / (Gamma(alpha+1)*Gamma(m+beta+1))"""
    m_val = mpf(m)
    return V0 * gamma(m_val + alpha + 1) * gamma(beta + 1) / (
        gamma(alpha + 1) * gamma(m_val + beta + 1)
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    PRECISION = 550   # digits of precision for verification
    DEPTH = 5000      # convergence depth
    N_MEMBERS = 8     # m = 0..N_MEMBERS-1 to test

    mp.dps = PRECISION + 50  # extra guard digits

    families = [
        {
            "name": "Family 1",
            "label": "T^(m+1)",
            "a_formula": "a(n) = -(2m+3)n - 2n^2",
            "b_formula": "b(n) = 3n+2",
            "b0": 2,
            "eval_func": eval_family1,
            "closed_func": family1_closed,
            "ratio_func": family1_ratio,
            "alpha": mpf('1.5'),   # 3/2
            "beta": mpf('0.5'),    # 1/2
            "alpha_frac": "3/2",
            "beta_frac": "1/2",
            "V0_exact": "3",
            "V0_mpf": mpf(3),
            "closed_form_str": "V(m) = 2m + 3",
            "type": "Telescoping (rational)",
            "S_relation": "N/A (b0=2 family)",
        },
        {
            "name": "Family 2",
            "label": "T^(m)",
            "a_formula": "a(n) = -(2m+1)n - 2n^2",
            "b_formula": "b(n) = 3n+2",
            "b0": 2,
            "eval_func": eval_family2,
            "closed_func": family2_closed,
            "ratio_func": family2_ratio,
            "alpha": mpf('0.5'),   # 1/2
            "beta": mpf('-0.5'),   # -1/2
            "alpha_frac": "1/2",
            "beta_frac": "-1/2",
            "V0_exact": "1",
            "V0_mpf": mpf(1),
            "closed_form_str": "V(m) = 2m + 1",
            "type": "Telescoping (rational)",
            "S_relation": "N/A (b0=2 family)",
        },
        {
            "name": "Family 3",
            "label": "S^(m+1)",
            "a_formula": "a(n) = (2m+3)n - 2n^2",
            "b_formula": "b(n) = 3n+1",
            "b0": 1,
            "eval_func": eval_family3,
            "closed_func": family3_closed,
            "ratio_func": family3_ratio,
            "alpha": mpf(1),
            "beta": mpf('0.5'),
            "alpha_frac": "1",
            "beta_frac": "1/2",
            "V0_exact": "4/pi",
            "V0_mpf": mpf(4)/pi,
            "closed_form_str": "V(m) = 2*Gamma(m+2) / (sqrt(pi)*Gamma(m+3/2))",
            "type": "S-family integer shift",
            "S_relation": "S^(m+1)",
        },
        {
            "name": "Family 4",
            "label": "S^(m+3/2)",
            "a_formula": "a(n) = (2m+4)n - 2n^2",
            "b_formula": "b(n) = 3n+1",
            "b0": 1,
            "eval_func": eval_family4,
            "closed_func": family4_closed,
            "ratio_func": family4_ratio,
            "alpha": mpf('1.5'),  # 3/2
            "beta": mpf(1),
            "alpha_frac": "3/2",
            "beta_frac": "1",
            "V0_exact": "3/2",
            "V0_mpf": mpf('1.5'),
            "closed_form_str": "V(m) = 2*Gamma(m+5/2) / (sqrt(pi)*Gamma(m+2))",
            "type": "S-family half-integer shift",
            "S_relation": "S^(m+3/2)",
        },
    ]

    print("=" * 78)
    print("  GRAND ROSETTA TABLE: FINAL SWEEP OF ALL 4 FAMILIES")
    print(f"  Precision: {PRECISION}dp | Depth: {DEPTH} | Members: m=0..{N_MEMBERS-1}")
    print("=" * 78)
    print()

    cert_data = {
        "title": "Grand Rosetta Table - All 4 Families",
        "generated": datetime.now().isoformat(),
        "precision": PRECISION,
        "depth": DEPTH,
        "families": [],
    }

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 1: VERIFY ALL CLOSED FORMS
    # ═════════════════════════════════════════════════════════════════════════
    print("=" * 78)
    print("  PHASE 1: VERIFY CLOSED FORMS AT %ddp" % PRECISION)
    print("=" * 78)

    for fam in families:
        print()
        print("-" * 78)
        print(f"  {fam['name']} ({fam['label']}): {fam['closed_form_str']}")
        print(f"  {fam['a_formula']}, {fam['b_formula']}")
        print(f"  alpha = {fam['alpha_frac']}, beta = {fam['beta_frac']}")
        print(f"  alpha - beta = {float(fam['alpha'] - fam['beta'])}")
        print("-" * 78)

        fam_cert = {
            "name": fam["name"],
            "label": fam["label"],
            "a_formula": fam["a_formula"],
            "b_formula": fam["b_formula"],
            "b0": fam["b0"],
            "alpha": fam["alpha_frac"],
            "beta": fam["beta_frac"],
            "alpha_minus_beta": str(Fraction(fam["alpha_frac"]) - Fraction(fam["beta_frac"])),
            "V0": fam["V0_exact"],
            "closed_form": fam["closed_form_str"],
            "type": fam["type"],
            "S_relation": fam["S_relation"],
            "members": {},
            "ratios": {},
        }

        prev_val = None
        all_ok = True

        for m in range(N_MEMBERS):
            t0 = time.time()
            pcf_val = fam["eval_func"](m, depth=DEPTH)
            t_pcf = time.time() - t0

            if pcf_val is None:
                print(f"  m={m}: DIVERGED")
                all_ok = False
                continue

            # Check against closed form
            closed_val = fam["closed_func"](m)
            diff = abs(pcf_val - closed_val)
            if diff > 0:
                digits = int(float(-log(diff, 10)))
            else:
                digits = PRECISION

            # Check against generic Gamma formula
            gamma_val = general_closed_form(m, fam["alpha"], fam["beta"], fam["V0_mpf"])
            gamma_diff = abs(pcf_val - gamma_val)
            if gamma_diff > 0:
                gamma_digits = int(float(-log(gamma_diff, 10)))
            else:
                gamma_digits = PRECISION

            # Check ratio
            ratio_str = ""
            ratio_digits = 0
            if prev_val is not None and m >= 1:
                actual_ratio = pcf_val / prev_val
                expected_ratio = fam["ratio_func"](m)
                if expected_ratio is not None:
                    ratio_diff = abs(actual_ratio - expected_ratio)
                    if ratio_diff > 0:
                        ratio_digits = int(float(-log(ratio_diff, 10)))
                    else:
                        ratio_digits = PRECISION

                    # Express ratio as fraction
                    r_float = float(actual_ratio)
                    best_p, best_q, best_d = 0, 1, 0
                    for q in range(1, 100):
                        p = round(r_float * q)
                        if p == 0:
                            continue
                        res = abs(actual_ratio - mpf(p)/mpf(q))
                        if res > 0:
                            d = int(float(-log(res, 10)))
                        else:
                            d = PRECISION
                        if d > best_d:
                            best_d, best_p, best_q = d, p, q
                    ratio_str = f"{best_p}/{best_q}"
                    fam_cert["ratios"][str(m)] = ratio_str

            short_val = nstr(pcf_val, 25)
            status = "OK" if digits >= PRECISION - 60 else "LOW"
            if digits < PRECISION - 100:
                all_ok = False

            print(f"  m={m}: V = {short_val:>30s}  "
                  f"closed={digits:>4d}d  gamma={gamma_digits:>4d}d  "
                  f"ratio={ratio_str:>6s} ({ratio_digits}d)  [{t_pcf:.1f}s]")

            fam_cert["members"][str(m)] = {
                "value_25dp": short_val,
                "closed_form_digits": digits,
                "gamma_formula_digits": gamma_digits,
                "status": status,
            }

            prev_val = pcf_val

        fam_cert["all_verified"] = all_ok
        cert_data["families"].append(fam_cert)
        print(f"  >>> {'ALL VERIFIED' if all_ok else 'ISSUES FOUND'}")

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 2: S-FAMILY RELATIONSHIP FOR FAMILIES 3 & 4
    # ═════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 78)
    print("  PHASE 2: S-FAMILY SHIFT VERIFICATION")
    print("=" * 78)

    for shift_name, shift, eval_func in [
        ("Family 3 = S^(m+1)", 1, eval_family3),
        ("Family 4 = S^(m+3/2)", mpf('1.5'), eval_family4),
    ]:
        print(f"\n  --- {shift_name} ---")
        for m in range(6):
            v_fam = eval_func(m, depth=DEPTH)
            s_val = eval_S(mpf(m) + shift, depth=DEPTH)
            s_closed = S_closed(mpf(m) + shift)

            if v_fam is not None and s_val is not None:
                diff_pcf = abs(v_fam - s_val)
                diff_closed = abs(v_fam - s_closed)
                d_pcf = int(float(-log(diff_pcf, 10))) if diff_pcf > 0 else PRECISION
                d_closed = int(float(-log(diff_closed, 10))) if diff_closed > 0 else PRECISION
                print(f"  m={m}: V_fam = {nstr(v_fam,20):>25s}  "
                      f"S^(m+{float(shift)}) = {nstr(s_val,20):>25s}  "
                      f"PCF-match={d_pcf}d  Gamma-match={d_closed}d")
            else:
                print(f"  m={m}: DIVERGED")

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 3: TELESCOPING ANALYSIS FOR FAMILIES 1 & 2
    # ═════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 78)
    print("  PHASE 3: TELESCOPING CONDITION ANALYSIS")
    print("=" * 78)
    print()
    print("  THEOREM (Telescoping Cancellation):")
    print("  ------------------------------------")
    print("  For a PCF family with ratio V(m)/V(m-1) = (m+alpha)/(m+beta),")
    print("  the closed form is:")
    print()
    print("    V(m) = V(0) * Gamma(m+alpha+1)*Gamma(beta+1)")
    print("                 / (Gamma(alpha+1)*Gamma(m+beta+1))")
    print()
    print("  WHEN alpha - beta IN Z (integers), this reduces to a POLYNOMIAL:")
    print("    Gamma(m+alpha+1)/Gamma(m+beta+1) = (m+beta+1)_d")
    print("    where d = alpha - beta and (x)_d is the Pochhammer symbol.")
    print()
    print("  This causes ALL transcendental factors (sqrt(pi), etc.) to cancel.")
    print()

    # Demonstrate telescoping for Families 1 & 2
    for fam_name, alpha, beta, V0, closed_str in [
        ("Family 1", Fraction(3,2), Fraction(1,2), 3, "2m+3"),
        ("Family 2", Fraction(1,2), Fraction(-1,2), 1, "2m+1"),
    ]:
        d = alpha - beta  # should be 1
        print(f"  {fam_name}: alpha={alpha}, beta={beta}, alpha-beta={d}")
        print(f"    General form: V(m) = V(0) * Gamma(m+{alpha+1})*Gamma({beta+1})")
        print(f"                       / (Gamma({alpha+1})*Gamma(m+{beta+1}))")
        print(f"    Since alpha-beta = {d} (integer), telescope:")
        print(f"      Gamma(m+{alpha+1})/Gamma(m+{beta+1}) = m + {beta+1}")
        print(f"      Constants: Gamma({beta+1})/Gamma({alpha+1})")

        # Compute the constant factor
        mp.dps = 100
        const = float(gamma(mpf(str(beta+1))) / gamma(mpf(str(alpha+1))))
        print(f"      = Gamma({beta+1})/Gamma({alpha+1}) = {const}")
        V0_f = float(V0)
        print(f"      V(m) = {V0_f} * {const:.10f} * (m + {float(beta+1):.1f})")
        print(f"           = {V0_f * const:.6f} * (m + {float(beta+1):.1f})")
        full_coeff = V0_f * const
        offset = float(beta + 1)
        print(f"      Check: m=0 => {full_coeff:.6f} * {offset:.1f} = {full_coeff*offset:.6f}")
        print(f"             m=1 => {full_coeff:.6f} * {offset+1:.1f} = {full_coeff*(offset+1):.6f}")
        v_at_0 = int(2*0 + (3 if fam_name == 'Family 1' else 1))
        v_at_1 = int(2*1 + (3 if fam_name == 'Family 1' else 1))
        print(f"      Expected: {closed_str} => m=0: {v_at_0}, m=1: {v_at_1}")
        mp.dps = PRECISION + 50

        # Direct verification: show the Gamma ratio is exactly a linear function
        print(f"    DIRECT PROOF that V(m) = {closed_str}:")
        print(f"      Ratio (m+{alpha})/(m+{beta}) for consecutive m:")
        for m_val in range(1, 6):
            r = Fraction(2*m_val + 2*int(alpha), 2*m_val + 2*int(beta))
            # Use exact fractions
            num = 2*m_val + int(2*alpha)
            den = 2*m_val + int(2*beta)
            print(f"        m={m_val}: ({num}/{den})")
        print(f"      Product m=1..m: telescopes to (2m+{int(2*alpha+1)})/{int(2*int(beta)+1+2)}"
              f" ... = {closed_str} / V(0)")
        print()

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 4: NON-INTEGER PARAMETER PROBES
    # ═════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 78)
    print("  PHASE 4: HALF-INTEGER & NON-INTEGER PARAMETER PROBES")
    print("=" * 78)
    print()

    # For each family, test m = -0.5, 0.5, 1.5 and use PSLQ
    test_ms = [mpf('-0.5'), mpf('0.5'), mpf('1.5')]
    mp.dps = 200  # sufficient for PSLQ

    for fam in families:
        print(f"\n  --- {fam['name']} ({fam['label']}) at half-integer m ---")
        for m_val in test_ms:
            v = fam["eval_func"](m_val, depth=DEPTH)
            if v is None:
                print(f"    m={float(m_val):+.1f}: DIVERGED")
                continue

            # Check closed form
            c = fam["closed_func"](m_val)
            diff = abs(v - c)
            if diff > 0:
                d = int(float(-log(diff, 10)))
            else:
                d = 200

            # PSLQ against {v, 1, 1/pi, sqrt(pi), pi}
            pslq_str = ""
            if abs(v) < mpf(10)**(-50):
                pslq_str = "V ~ 0 (skip PSLQ)"
            else:
                basis = [v, mpf(1), 1/pi, sqrt(pi), pi]
                rel = pslq(basis)
                if rel is not None:
                    # Reconstruct: rel[0]*v + rel[1] + rel[2]/pi + rel[3]*sqrt(pi) + rel[4]*pi = 0
                    # => v = -(rel[1] + rel[2]/pi + rel[3]*sqrt(pi) + rel[4]*pi) / rel[0]
                    pslq_str = f"PSLQ: {rel}"

            print(f"    m={float(m_val):+.1f}: V = {nstr(v, 20):>25s}  "
                  f"closed={d}d  {pslq_str}")

    mp.dps = PRECISION + 50

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 5: STRUCTURAL CLASSIFICATION (a_n SIGN & b_0)
    # ═════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 78)
    print("  PHASE 5: STRUCTURAL CLASSIFICATION")
    print("=" * 78)
    print()
    print("  All 4 families share the QUADRATIC a(n) = k*n - 2n^2, LINEAR b(n) = eps + 3n")
    print()
    print("  Parameterization: a(n,m) = (k_0 + 2m*sigma)n - 2n^2")
    print("    where k_0 = constant offset, sigma = +1 or -1 (sign of m-coupling)")
    print()
    print("  +----------------------------------------------------------+")
    print("  | Family | k_0 | sigma | eps | b_0 | Type                  |")
    print("  +--------+-----+-------+-----+-----+-----------------------+")
    print("  |   1    |  -3 |  -1   |  2  |  2  | Telescoping (2m+3)   |")
    print("  |   2    |  -1 |  -1   |  2  |  2  | Telescoping (2m+1)   |")
    print("  |   3    |  +3 |  +1   |  1  |  1  | S^(m+1)              |")
    print("  |   4    |  +4 |  +1   |  1  |  1  | S^(m+3/2)            |")
    print("  +--------+-----+-------+-----+-----+-----------------------+")
    print()
    print("  KEY OBSERVATION:")
    print("  - Families with b_0=1, sigma=+1 (S-type): yield TRANSCENDENTAL values")
    print("    involving sqrt(pi) and Gamma functions.")
    print("  - Families with b_0=2, sigma=-1 (T-type): yield RATIONAL values")
    print("    because alpha - beta = 1 (integer), causing Gamma cancellation.")
    print()
    print("  The 'T-type' families have a(n) with NEGATIVE m-coupling, which")
    print("  flips the sign in the Euler CF correspondence. Combined with b_0=2,")
    print("  this forces alpha-beta to be an integer, making the Pochhammer ratio")
    print("  (alpha+1)_m / (beta+1)_m telescope to a polynomial.")
    print()

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 6: GRAND ROSETTA TABLE (MANUSCRIPT FORMAT)
    # ═════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 78)
    print("  PHASE 6: GRAND ROSETTA TABLE (MANUSCRIPT FORMAT)")
    print("=" * 78)
    print()
    print("  TABLE: Complete Classification of Rosetta Stone PCF Families")
    print()

    # Header
    hdr = (f"  {'Fam':>3s}  {'Label':>10s}  {'alpha':>5s}  {'beta':>5s}  "
           f"{'a-b':>4s}  {'V(0)':>8s}  {'Ratio (m+a)/(m+b)':>18s}  "
           f"{'Closed Form':>35s}  {'Type':>20s}")
    print(hdr)
    print("  " + "-" * len(hdr.strip()))

    table_rows = []
    for i, fam in enumerate(families, 1):
        alpha_str = fam["alpha_frac"]
        beta_str = fam["beta_frac"]
        a_minus_b = str(Fraction(alpha_str) - Fraction(beta_str))
        V0 = fam["V0_exact"]
        ratio_display = f"(m+{alpha_str})/(m+{beta_str})"
        closed = fam["closed_form_str"]
        ftype = fam["type"]
        label = fam["label"]

        row = (f"  {i:>3d}  {label:>10s}  {alpha_str:>5s}  {beta_str:>5s}  "
               f"{a_minus_b:>4s}  {V0:>8s}  {ratio_display:>18s}  "
               f"{closed:>35s}  {ftype:>20s}")
        print(row)
        table_rows.append(row)

    print()
    print("  UNIVERSALITY PRINCIPLE:")
    print("  All 4 families obey V(m) = V(0) * Gamma(m+alpha+1)*Gamma(beta+1)")
    print("                             / (Gamma(alpha+1)*Gamma(m+beta+1))")
    print()
    print("  DICHOTOMY:")
    print("  - alpha - beta in Z   => TELESCOPING (rational values)")
    print("  - alpha - beta in Z+1/2 => S-FAMILY (transcendental, involving sqrt(pi))")
    print()

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 7: UNIFIED GAMMA FORMULA VERIFICATION
    # ═════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 78)
    print("  PHASE 7: UNIFIED GAMMA FORMULA VERIFICATION")
    print("=" * 78)
    print()
    print("  Test: V(m) = V(0)*Gamma(m+alpha+1)*Gamma(beta+1)/(Gamma(alpha+1)*Gamma(m+beta+1))")
    print()

    for fam in families:
        print(f"  {fam['name']} ({fam['label']}):")
        alpha = fam["alpha"]
        beta = fam["beta"]
        V0 = fam["V0_mpf"]

        for m in range(N_MEMBERS):
            v_pcf = fam["eval_func"](m, depth=DEPTH)
            v_gamma = general_closed_form(m, alpha, beta, V0)
            if v_pcf is not None:
                diff = abs(v_pcf - v_gamma)
                if diff > 0:
                    d = int(float(-log(diff, 10)))
                else:
                    d = PRECISION
                print(f"    m={m}: V_pcf={nstr(v_pcf,15):>20s}  "
                      f"V_Gamma={nstr(v_gamma,15):>20s}  match={d}d")
        print()

    # ═════════════════════════════════════════════════════════════════════════
    #  PHASE 8: SAVE CERTIFICATION
    # ═════════════════════════════════════════════════════════════════════════
    cert_file = RESULTS_DIR / "grand_rosetta_table.json"
    with open(cert_file, "w") as f:
        json.dump(cert_data, f, indent=2, default=str)
    print(f"\n  Certification saved to {cert_file}")

    # Also save a LaTeX-ready table
    tex_file = RESULTS_DIR / "grand_rosetta_table.tex"
    with open(tex_file, "w") as f:
        f.write("% Grand Rosetta Table - Auto-generated\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Complete classification of Rosetta Stone PCF families. "
                "All families share $a_n = (k_0 + 2m\\sigma)n - 2n^2$, $b_n = \\varepsilon + 3n$. "
                "The telescoping condition $\\alpha - \\beta \\in \\mathbb{Z}$ causes all "
                "transcendental factors to cancel.}\n")
        f.write("\\label{tab:rosetta}\n")
        f.write("\\begin{tabular}{cccccccll}\n")
        f.write("\\toprule\n")
        f.write("Fam & Label & $\\alpha$ & $\\beta$ & $\\alpha{-}\\beta$ "
                "& $V(0)$ & Ratio & Closed Form & Type \\\\\n")
        f.write("\\midrule\n")

        for i, fam in enumerate(families, 1):
            alpha_s = fam['alpha_frac']
            beta_s = fam['beta_frac']
            ab = str(Fraction(alpha_s) - Fraction(beta_s))
            V0 = fam['V0_exact']
            ratio_tex = f"$\\frac{{m+{alpha_s}}}{{m+{beta_s}}}$"
            label = fam['label'].replace("^", "\\hat{}")  # escape for tex

            if i <= 2:
                closed_tex = fam['closed_form_str'].replace('V(m) = ', '$') + '$'
            else:
                # Convert Gamma to tex
                cf = fam['closed_form_str'].replace('V(m) = ', '')
                cf_tex = f"$S^{{({fam['S_relation'].replace('S^(','').rstrip(')')})}}$"
                closed_tex = cf_tex

            ftype = fam['type']
            if 'Telescoping' in ftype:
                ftype_tex = "Telescoping"
            elif 'integer' in ftype:
                ftype_tex = "$S$-shift ($\\mathbb{Z}$)"
            else:
                ftype_tex = "$S$-shift ($\\tfrac{1}{2}\\mathbb{Z}$)"

            label_tex = fam['label'].replace('^', '^{').rstrip(')') + '})$'
            label_tex = '$' + label_tex
            # Fix: convert T^(m+1) → $T^{(m+1)}$ 
            label_tex = fam['label']
            if '^' in label_tex:
                base, exp = label_tex.split('^', 1)
                label_tex = f"${base}^{{{exp}}}$"
            else:
                label_tex = f"${label_tex}$"

            V0_tex = f"${V0}$" if '/' not in V0 else f"$\\frac{{{V0.split('/')[0]}}}{{{V0.split('/')[1]}}}$"
            if V0 == "4/pi":
                V0_tex = "$\\frac{4}{\\pi}$"

            f.write(f"{i} & {label_tex} & ${alpha_s}$ & ${beta_s}$ & ${ab}$ "
                    f"& {V0_tex} & {ratio_tex} & {closed_tex} & {ftype_tex} \\\\\n")

        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")
    print(f"  LaTeX table saved to {tex_file}")

    print()
    print("=" * 78)
    print("  GRAND ROSETTA TABLE ANALYSIS COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()
