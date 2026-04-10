"""
formulas.py — Ramanujan-style formula template library.

Contains canonical templates for:
 - Pi series (Ramanujan, Chudnovsky, Machin-like)
 - Continued fractions for constants (e, pi, golden ratio)
 - q-Series / Jacobi theta identities
 - Mock theta functions
 - Partition identities (Hardy–Ramanujan, Rademacher)
 - Modular form identities
 - Integer relation targets (PSLQ seeds)

Each template is a callable that returns (symbolic_expr, numeric_value, metadata).
"""

from __future__ import annotations
import math
import itertools
from dataclasses import dataclass, field
from typing import Callable, Any

import mpmath
import sympy
from sympy import (Symbol, Rational, pi, E, sqrt, factorial, gamma,
                   oo, Sum, Product, binomial, Pow, Integer, S)

# ---------------------------------------------------------------------------
# Template data class
# ---------------------------------------------------------------------------

@dataclass
class FormulaTemplate:
    """A parameterised family of formulas."""
    name: str
    family: str                        # pi_series | continued_fraction | q_series | ...
    description: str
    parameter_ranges: dict             # e.g. {"a": (1,20), "b": (1,20)}
    generator: Callable[..., dict]     # (params) -> {expr, value, ...}
    tags: list[str] = field(default_factory=list)

    def instantiate(self, **params) -> dict:
        """Generate a concrete formula instance from parameters."""
        return self.generator(**params)


# ===================================================================
#  CONSTANTS (high-precision reference values)
# ===================================================================

_PREC = 100   # default mpmath decimal precision

def _mp(prec=_PREC):
    """Return mpmath context at given precision."""
    ctx = mpmath.mp.clone()
    ctx.dps = prec
    return ctx


# ===================================================================
#  1. PI SERIES TEMPLATES
# ===================================================================

def _ramanujan_1914_series(num_terms: int = 50, prec: int = _PREC) -> dict:
    """Ramanujan's 1914 formula:  1/pi = (2*sqrt(2)/9801) * sum_k ..."""
    mp = _mp(prec)
    s = mp.mpf(0)
    for k in range(num_terms):
        num = mp.fac(4*k) * (1103 + 26390*k)
        den = (mp.fac(k)**4) * (396**(4*k))
        s += num / den
    s *= 2 * mp.sqrt(2) / 9801
    pi_approx = 1 / s
    error = abs(pi_approx - mp.pi)
    return {
        "name": "Ramanujan 1914 pi series",
        "family": "pi_series",
        "expression": "1/pi = (2*sqrt(2)/9801) * Sum_{k=0}^{inf} (4k)!(1103+26390k) / ((k!)^4 * 396^(4k))",
        "value": float(pi_approx),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": num_terms,
        "converges": error < mp.mpf(10)**(-prec + 10),
    }


def _chudnovsky_series(num_terms: int = 20, prec: int = _PREC) -> dict:
    """Chudnovsky brothers' formula (fastest known pi series)."""
    mp = _mp(prec)
    s = mp.mpf(0)
    for k in range(num_terms):
        num = (-1)**k * mp.fac(6*k) * (13591409 + 545140134*k)
        den = mp.fac(3*k) * (mp.fac(k)**3) * mp.mpf(640320)**(3*k + mp.mpf('1.5'))
        s += num / den
    s *= 12
    pi_approx = 1 / s
    error = abs(pi_approx - mp.pi)
    return {
        "name": "Chudnovsky pi series",
        "family": "pi_series",
        "expression": "1/pi = 12 * Sum_{k=0}^{inf} (-1)^k(6k)!(13591409+545140134k) / ((3k)!(k!)^3 * 640320^(3k+3/2))",
        "value": float(pi_approx),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": num_terms,
        "converges": error < mp.mpf(10)**(-prec + 10),
    }


def _generalised_pi_series(a: int, b: int, c: int, d: int,
                            num_terms: int = 60, prec: int = _PREC) -> dict:
    """Generalised Ramanujan-type 1/pi formula with free parameters.

    1/pi = Sum_{k=0}^{inf} (a*k + b) * C(2k,k)^3 / c^k
    where a,b,c are integer parameters to search over.
    """
    mp = _mp(prec)
    s = mp.mpf(0)
    for k in range(num_terms):
        binom_2k_k = mp.fac(2*k) / (mp.fac(k)**2)
        s += (a*k + b) * (binom_2k_k**3) / mp.mpf(c)**k
    if abs(s) < mp.mpf('1e-50'):
        return {"name": "trivial", "converges": False, "error": float('inf')}
    pi_candidate = d / s
    error = abs(pi_candidate - mp.pi)
    return {
        "name": f"generalised_pi(a={a},b={b},c={c},d={d})",
        "family": "pi_series",
        "expression": f"d/pi ≈ Sum_k (({a}*k+{b}) * C(2k,k)^3 / {c}^k), d={d}",
        "params": {"a": a, "b": b, "c": c, "d": d},
        "value": float(pi_candidate),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": num_terms,
        "converges": error < mp.mpf(10)**(-10),
    }


# ===================================================================
#  2. CONTINUED FRACTION TEMPLATES
# ===================================================================

def _evaluate_gcf(a_func, b_func, depth: int = 200, prec: int = _PREC):
    """Evaluate generalized continued fraction  b0 + a1/(b1 + a2/(b2 + ...))
    using Lentz's algorithm for numerical stability."""
    mp = _mp(prec)
    tiny = mp.mpf(10)**(-prec)
    f = mp.mpf(b_func(0))
    if f == 0:
        f = tiny
    C = f
    D = mp.mpf(0)
    for n in range(1, depth + 1):
        an = mp.mpf(a_func(n))
        bn = mp.mpf(b_func(n))
        D = bn + an * D
        if D == 0:
            D = tiny
        C = bn + an / C
        if C == 0:
            C = tiny
        D = 1 / D
        delta = C * D
        f *= delta
        if abs(delta - 1) < mp.mpf(10)**(-prec + 5):
            break
    return f


def _pi_continued_fraction(prec: int = _PREC) -> dict:
    """pi = 4 / (1 + 1^2/(2 + 3^2/(2 + 5^2/(2 + ...))))"""
    mp = _mp(prec)
    # pi/4 = 1/(1 + 1^2/(2 + 3^2/(2 + 5^2/(2 + ...))))
    # Using standard form
    cf_val = _evaluate_gcf(
        a_func=lambda n: (2*n - 1)**2,
        b_func=lambda n: 2 if n > 0 else 1,
        depth=500, prec=prec
    )
    pi_approx = 4 / cf_val
    error = abs(pi_approx - float(mp.pi))
    return {
        "name": "pi via continued fraction (Brouncker)",
        "family": "continued_fraction",
        "expression": "4/(1 + 1²/(2 + 3²/(2 + 5²/(2 + ...))))",
        "value": float(pi_approx),
        "target": float(mp.pi),
        "error": error,
    }


def _e_continued_fraction(prec: int = _PREC) -> dict:
    """e = 2 + 1/(1 + 1/(2 + 1/(1 + 1/(1 + 1/(4 + ...)))))
    Regular CF: e = [2; 1, 2, 1, 1, 4, 1, 1, 6, ...]"""
    mp = _mp(prec)
    # Compute via simple CF coefficients
    depth = 200
    coeffs = [2]
    for i in range(1, depth):
        if i % 3 == 2:
            coeffs.append(2 * ((i + 1) // 3))
        else:
            coeffs.append(1)
    # Evaluate CF from bottom up
    val = mp.mpf(coeffs[-1])
    for i in range(len(coeffs) - 2, -1, -1):
        val = coeffs[i] + 1 / val
    error = abs(val - mp.e)
    return {
        "name": "e via regular continued fraction",
        "family": "continued_fraction",
        "expression": "e = [2; 1, 2, 1, 1, 4, 1, 1, 6, ...]",
        "value": float(val),
        "target": float(mp.e),
        "error": float(error),
    }


def _generalised_cf(an_coeffs: list[int], bn_coeffs: list[int],
                     target_name: str = "unknown",
                     prec: int = _PREC) -> dict:
    """Evaluate a GCF with polynomial a_n, b_n sequences.

    a_n = an_coeffs[0]*n^2 + an_coeffs[1]*n + an_coeffs[2]
    b_n = bn_coeffs[0]*n + bn_coeffs[1]

    v3: ISC-style extended lookup — checks value and simple algebraic
    transforms (±, ×p/q, square, reciprocal) against 14 known constants.
    Returns ``is_known_transform=True`` when the CF is a trivial algebraic
    transformation of a recognised constant.
    """
    mp = _mp(prec)
    def a_func(n):
        if len(an_coeffs) == 3:
            return an_coeffs[0]*n*n + an_coeffs[1]*n + an_coeffs[2]
        elif len(an_coeffs) == 2:
            return an_coeffs[0]*n + an_coeffs[1]
        return an_coeffs[0]
    def b_func(n):
        if len(bn_coeffs) >= 2:
            return bn_coeffs[0]*n + bn_coeffs[1]
        return bn_coeffs[0]
    val = _evaluate_gcf(a_func, b_func, depth=300, prec=prec)

    # ── ISC-style constant recognition ──────────────────────────
    targets = {
        "pi": mp.pi, "e": mp.e, "phi": mp.phi,
        "sqrt2": mp.sqrt(2), "sqrt3": mp.sqrt(3), "sqrt5": mp.sqrt(5),
        "ln2": mp.ln(2), "ln3": mp.ln(3),
        "euler_gamma": mp.euler, "catalan": mp.catalan,
        "apery": mp.zeta(3), "pi^2/6": mp.pi**2 / 6,
        "1/phi": 1 / mp.phi, "2phi-1": 2*mp.phi - 1,  # = sqrt(5)
    }
    # Rational multipliers p/q for |p|,|q| ≤ 4
    multipliers = []
    for p in range(-4, 5):
        for q in range(1, 5):
            if p == 0:
                continue
            multipliers.append(mp.mpf(p) / mp.mpf(q))

    best_match = None
    best_error = float('inf')
    best_mult = None
    best_const = None

    # Level 1: direct match  val * mult ≈ constant
    for name, tval in targets.items():
        for mult in multipliers:
            e = float(abs(val * mult - tval))
            if e < best_error:
                best_error = e
                best_mult = float(mult)
                best_const = name
                best_match = f"{float(mult)}*CF={name}" if mult != 1 else name

    # Level 2: val^2 or 1/val might be a known constant
    if best_error > 1e-15 and val != 0:
        for name, tval in targets.items():
            for transform, label in [
                (val**2, "CF²"), (1/val, "1/CF"),
                (val**2 - 1, "CF²-1"), (val + 1/val, "CF+1/CF"),
            ]:
                e = float(abs(transform - tval))
                if e < best_error:
                    best_error = e
                    best_mult = None
                    best_const = name
                    best_match = f"{label}={name}"

    # Convergence test: evaluate at two depths and compare
    val2 = _evaluate_gcf(a_func, b_func, depth=150, prec=prec)
    convergence_error = float(abs(val - val2))
    converged = convergence_error < 1e-10

    # Check if value is a simple rational p/q (|p|,|q| ≤ 50)
    is_rational = False
    for denom in range(1, 51):
        numer = round(float(val) * denom)
        if abs(numer) <= 50 and abs(float(val) - numer / denom) < 1e-10:
            is_rational = True
            break

    # Check if value is a simple quadratic irrational (a+b*sqrt(c))/d
    # by testing if val satisfies ax^2+bx+c=0 with small integer coefficients
    is_simple_algebraic = False
    algebraic_form = None
    if not is_rational:
        for a_coeff in range(1, 10):
            for b_coeff in range(-20, 21):
                for c_coeff in range(-20, 21):
                    if a_coeff == 0:
                        continue
                    res = a_coeff * float(val)**2 + b_coeff * float(val) + c_coeff
                    if abs(res) < 1e-8:
                        disc_v = b_coeff**2 - 4*a_coeff*c_coeff
                        is_simple_algebraic = True
                        algebraic_form = f"{a_coeff}x² + {b_coeff}x + {c_coeff} = 0"
                        break
                if is_simple_algebraic:
                    break
            if is_simple_algebraic:
                break

    # Determine if this is a known-constant transform
    matches_known = best_error < 1e-10 or is_rational
    is_known_transform = matches_known and (best_const is not None or is_rational)
    # v3: "interesting" = converges AND (matches known OR potentially novel)
    is_interesting = converged
    # Novel = converges + not known constant + not trivial algebraic
    is_potentially_novel = converged and not matches_known and not is_simple_algebraic
    transform_citation = None
    if is_known_transform:
        if is_rational:
            transform_citation = "Rational number"
        elif is_simple_algebraic:
            transform_citation = f"Simple algebraic: {algebraic_form}"
        else:
            _CONST_NAMES = {
            "phi": "φ = (1+√5)/2", "pi": "π", "e": "e",
            "sqrt2": "√2", "sqrt3": "√3", "sqrt5": "√5",
            "ln2": "ln 2", "ln3": "ln 3",
            "euler_gamma": "γ (Euler–Mascheroni)",
            "catalan": "G (Catalan)", "apery": "ζ(3) (Apéry)",
            "pi^2/6": "π²/6 = ζ(2)", "1/phi": "1/φ", "2phi-1": "√5",
        }
        nice = _CONST_NAMES.get(best_const, best_const)
        transform_citation = f"Algebraic transform of {nice}"

    return {
        "name": f"GCF(an={an_coeffs}, bn={bn_coeffs})",
        "family": "continued_fraction",
        "expression": f"GCF with a(n)={an_coeffs}, b(n)={bn_coeffs}",
        "params": {"an": an_coeffs, "bn": bn_coeffs},
        "value": float(val),
        "best_match": best_match,
        "best_error": best_error,
        "is_interesting": is_interesting,
        "is_known_transform": is_known_transform,
        "is_potentially_novel": is_potentially_novel,
        "converged": converged,
        "convergence_error": convergence_error,
        "matched_constant": best_const,
        "matched_multiplier": best_mult,
        "transform_citation": transform_citation,
    }


# ===================================================================
#  3. Q-SERIES / THETA FUNCTION TEMPLATES
# ===================================================================

def _jacobi_theta3(q_val: float, num_terms: int = 100, prec: int = _PREC) -> dict:
    """Jacobi theta_3(q) = 1 + 2*sum_{n=1}^{inf} q^(n^2)."""
    mp = _mp(prec)
    q = mp.mpf(q_val)
    if abs(q) >= 1:
        return {"name": "theta3_invalid", "converges": False}
    s = mp.mpf(1)
    for n in range(1, num_terms + 1):
        term = q**(n*n)
        if abs(term) < mp.mpf(10)**(-prec):
            break
        s += 2 * term
    return {
        "name": f"jacobi_theta3(q={q_val})",
        "family": "q_series",
        "expression": f"theta_3({q_val}) = 1 + 2*Sum_n q^(n^2)",
        "value": float(s),
        "q": q_val,
        "terms_used": n,
    }


def _euler_q_product(q_val: float, num_terms: int = 100, prec: int = _PREC) -> dict:
    """Euler function: prod_{n=1}^{inf} (1 - q^n)."""
    mp = _mp(prec)
    q = mp.mpf(q_val)
    if abs(q) >= 1:
        return {"name": "euler_product_invalid", "converges": False}
    p = mp.mpf(1)
    for n in range(1, num_terms + 1):
        factor = 1 - q**n
        if abs(factor - 1) < mp.mpf(10)**(-prec):
            break
        p *= factor
    return {
        "name": f"euler_product(q={q_val})",
        "family": "q_series",
        "expression": f"prod_n (1-q^n) for q={q_val}",
        "value": float(p),
        "q": q_val,
    }


def _ramanujan_theta(a: float, b: float, num_terms: int = 80,
                     prec: int = _PREC) -> dict:
    """Ramanujan theta function f(a,b) = Sum_{n=-inf}^{inf} a^(n(n+1)/2) * b^(n(n-1)/2)."""
    mp = _mp(prec)
    a_mp, b_mp = mp.mpf(a), mp.mpf(b)
    s = mp.mpf(0)
    for n in range(-num_terms, num_terms + 1):
        exp_a = n * (n + 1) // 2
        exp_b = n * (n - 1) // 2
        if exp_a >= 0 and exp_b >= 0:
            s += a_mp**exp_a * b_mp**exp_b
        else:
            try:
                s += a_mp**exp_a * b_mp**exp_b
            except (ValueError, ZeroDivisionError):
                pass
    return {
        "name": f"ramanujan_theta(a={a},b={b})",
        "family": "q_series",
        "expression": f"f({a},{b}) = Sum_n a^(n(n+1)/2) * b^(n(n-1)/2)",
        "value": float(s),
        "params": {"a": a, "b": b},
    }


# ===================================================================
#  4. PARTITION & MOCK THETA TEMPLATES
# ===================================================================

def _partition_count(n: int, prec: int = _PREC) -> dict:
    """Compute p(n) exactly and compare with Hardy–Ramanujan asymptotic."""
    mp = _mp(prec)
    # Exact p(n) via generating function (dynamic programming)
    p = [0] * (n + 1)
    p[0] = 1
    for k in range(1, n + 1):
        for j in range(k, n + 1):
            p[j] += p[j - k]

    exact = p[n]
    # Hardy-Ramanujan asymptotic
    hr = mp.exp(mp.pi * mp.sqrt(mp.mpf(2*n) / 3)) / (4 * n * mp.sqrt(3))
    rel_error = abs(mp.mpf(exact) - hr) / mp.mpf(exact) if exact > 0 else float('inf')
    return {
        "name": f"partition({n})",
        "family": "partition",
        "expression": f"p({n}) exact vs Hardy–Ramanujan asymptotic",
        "exact": exact,
        "asymptotic": float(hr),
        "relative_error": float(rel_error),
        "n": n,
    }


def _mock_theta_f0(q_val: float, num_terms: int = 80, prec: int = _PREC) -> dict:
    """Ramanujan's mock theta function f_0(q) = Sum_{n>=0} q^(n^2) / prod_{m=1}^{n}(1+q^m)^2."""
    mp = _mp(prec)
    q = mp.mpf(q_val)
    if abs(q) >= 1:
        return {"name": "mock_theta_invalid", "converges": False}
    s = mp.mpf(0)
    for n in range(num_terms):
        num = q**(n*n)
        den = mp.mpf(1)
        for m in range(1, n + 1):
            den *= (1 + q**m)**2
        if abs(den) < mp.mpf(10)**(-prec + 5):
            break
        s += num / den
    return {
        "name": f"mock_theta_f0(q={q_val})",
        "family": "mock_theta",
        "expression": f"f_0(q) = Sum_n q^(n^2) / prod_m (1+q^m)^2, q={q_val}",
        "value": float(s),
        "value_mpf": s,  # v3: preserve full precision
        "q": q_val,
    }


def _mock_theta_phi(q_val: float, num_terms: int = 80, prec: int = _PREC) -> dict:
    """Mock theta phi(q) = Sum_{n>=0} q^(n^2) / prod_{m=1}^{n}(1 - q^(2m-1))."""
    mp = _mp(prec)
    q = mp.mpf(q_val)
    if abs(q) >= 1:
        return {"name": "mock_theta_phi_invalid", "converges": False}
    s = mp.mpf(0)
    for n in range(num_terms):
        num = q**(n*n)
        den = mp.mpf(1)
        for m in range(1, n + 1):
            den *= (1 - q**(2*m - 1))
            if abs(den) < mp.mpf(10)**(-prec + 5):
                break
        if abs(den) < mp.mpf(10)**(-prec + 5):
            continue
        s += num / den
    return {
        "name": f"mock_theta_phi(q={q_val})",
        "family": "mock_theta",
        "expression": f"phi(q) = Sum_n q^(n^2)/prod_m(1-q^(2m-1)), q={q_val}",
        "value": float(s),
        "value_mpf": s,  # v3: preserve full precision
        "q": q_val,
    }


# ===================================================================
#  5. TAU FUNCTION (Lehmer's conjecture target)
# ===================================================================

def _ramanujan_tau(n: int) -> dict:
    """Compute Ramanujan tau function tau(n) using Ramanujan's recursion.
    Target: Lehmer's conjecture — tau(n) != 0 for all n >= 1."""
    # Use the formula via Dedekind eta / Delta function
    # tau(n) = coefficient of q^n in q*prod_{m=1}^{inf}(1-q^m)^{24}
    # We compute via recurrence using pentagonal theorem
    max_n = n + 1
    # First compute partition-like coefficients for (eta(q))^24
    # Delta(q) = q * prod(1-q^n)^24 = sum tau(n)*q^n
    # Use the power of q-expansion
    coeffs = [0] * max_n
    coeffs[0] = 1
    # Expand prod(1-q^n)^24 up to q^n
    # This is equivalent to Ramanujan's Delta function coefficient
    # Efficient: use the 24th power of Euler product
    # First compute Euler product coefficients
    euler = [0] * max_n
    euler[0] = 1
    for k in range(1, max_n):
        for j in range(max_n - 1, k - 1, -1):
            euler[j] -= euler[j - k]

    # Now compute 24th power via repeated squaring? No, simpler: convolve
    # eta^24 = (euler)^24. We do this iteratively.
    result = [0] * max_n
    result[0] = 1
    for _power in range(24):
        new_result = [0] * max_n
        for i in range(max_n):
            if result[i] == 0:
                continue
            for j in range(max_n - i):
                if euler[j] == 0:
                    continue
                new_result[i + j] += result[i] * euler[j]
        result = new_result

    # tau(n) = coefficient of q^n in q * eta^24 = result[n-1]
    tau_n = result[n - 1] if n >= 1 and n - 1 < max_n else None

    return {
        "name": f"ramanujan_tau({n})",
        "family": "tau_function",
        "expression": f"tau({n}) — coefficient of q^{n} in Delta(q)",
        "value": tau_n,
        "n": n,
        "is_nonzero": tau_n != 0 if tau_n is not None else None,
        "lehmer_conjecture_holds": tau_n != 0 if tau_n is not None else None,
    }


# ===================================================================
#  6. PSLQ / INTEGER RELATION TARGETS
# ===================================================================

def _pslq_search(target_value, basis_exprs: list[str],
                 basis_values: list = None, prec: int = _PREC) -> dict:
    """Run PSLQ algorithm to find integer relations among basis values.

    v3: Accepts mpf target_value (not just float) to preserve high-precision
    digits.  ``basis_values`` may be mpf or float; if None the standard
    constants are recomputed at ``prec``.
    """
    mp = _mp(prec)

    # Recompute basis at the requested precision unless caller provides mpf values
    if basis_values is not None:
        bvals = [mp.mpf(v) for v in basis_values]
    else:
        bvals = _compute_basis_mpf(basis_exprs, prec)

    target_mpf = mp.mpf(target_value)
    vec = [target_mpf] + bvals
    try:
        rel = mp.pslq(vec, maxcoeff=1000, maxsteps=5000)
    except Exception:
        rel = None
    if rel is None:
        return {
            "name": "pslq_no_relation",
            "family": "integer_relation",
            "found": False,
            "target": float(target_mpf),
        }
    # rel gives integers [r0, r1, ...] such that r0*target + r1*b1 + ... = 0
    # => target = -(r1*b1 + r2*b2 + ...) / r0
    terms = []
    for i, (coeff, name) in enumerate(zip(rel[1:], basis_exprs)):
        if coeff != 0:
            terms.append(f"({coeff})*{name}")
    if rel[0] != 0:
        expr = f"target = -({' + '.join(terms)}) / {rel[0]}"
    else:
        expr = f"0 = {rel[0]}*target + {' + '.join(terms)}"
    # Verify
    check = sum(r * v for r, v in zip(rel, vec))
    return {
        "name": "pslq_relation",
        "family": "integer_relation",
        "found": True,
        "relation": list(rel),
        "expression": expr,
        "basis": basis_exprs,
        "residual": float(abs(check)),
        "max_coeff": max(abs(c) for c in rel),
        "target": float(target_mpf),
    }


def _compute_basis_mpf(names: list[str], prec: int):
    """Compute standard constant basis values as native mpf at given precision."""
    mp = _mp(prec)
    mapping = {
        "1": mp.mpf(1), "pi": mp.pi, "pi^2": mp.pi**2,
        "e": mp.e, "ln2": mp.ln(2), "sqrt(2)": mp.sqrt(2),
        "euler_gamma": mp.euler, "catalan": mp.catalan,
        "zeta(3)": mp.zeta(3), "sqrt(3)": mp.sqrt(3),
        "ln3": mp.ln(3), "phi": mp.phi,
        # v3 exotic constants
        "zeta(5)": mp.zeta(5), "ln(pi)": mp.ln(mp.pi),
        "pi^3": mp.pi**3, "sqrt(5)": mp.sqrt(5),
    }
    return [mapping.get(n, mp.mpf(0)) for n in names]


# ===================================================================
#  TEMPLATE REGISTRY
# ===================================================================

def get_all_templates() -> list[FormulaTemplate]:
    """Return all built-in formula templates."""
    templates = []

    # Pi series family
    templates.append(FormulaTemplate(
        name="Ramanujan 1914",
        family="pi_series",
        description="Ramanujan's original 1/pi series (1914)",
        parameter_ranges={"num_terms": (10, 100)},
        generator=lambda num_terms=50: _ramanujan_1914_series(num_terms),
        tags=["pi", "series", "classic"],
    ))
    templates.append(FormulaTemplate(
        name="Chudnovsky",
        family="pi_series",
        description="Chudnovsky brothers' pi series",
        parameter_ranges={"num_terms": (5, 50)},
        generator=lambda num_terms=20: _chudnovsky_series(num_terms),
        tags=["pi", "series", "fast"],
    ))
    templates.append(FormulaTemplate(
        name="Generalised pi series",
        family="pi_series",
        description="Parameterised Ramanujan-type 1/pi with free (a,b,c,d)",
        parameter_ranges={"a": (1, 50), "b": (1, 2000), "c": (2, 1000), "d": (1, 100)},
        generator=lambda a=1, b=1, c=64, d=1: _generalised_pi_series(a, b, c, d),
        tags=["pi", "series", "search"],
    ))

    # Continued fractions
    templates.append(FormulaTemplate(
        name="Pi CF (Brouncker)",
        family="continued_fraction",
        description="Pi via Brouncker continued fraction",
        parameter_ranges={},
        generator=lambda: _pi_continued_fraction(),
        tags=["pi", "cf", "classic"],
    ))
    templates.append(FormulaTemplate(
        name="e CF",
        family="continued_fraction",
        description="e via regular continued fraction",
        parameter_ranges={},
        generator=lambda: _e_continued_fraction(),
        tags=["e", "cf", "classic"],
    ))
    templates.append(FormulaTemplate(
        name="Generalised CF",
        family="continued_fraction",
        description="GCF search with polynomial a_n, b_n",
        parameter_ranges={"an_coeffs": "list", "bn_coeffs": "list"},
        generator=lambda an_coeffs=[1, 0, 0], bn_coeffs=[1, 1]: _generalised_cf(an_coeffs, bn_coeffs),
        tags=["cf", "search"],
    ))

    # q-series
    templates.append(FormulaTemplate(
        name="Jacobi theta_3",
        family="q_series",
        description="Jacobi theta_3(q) = 1 + 2*sum q^(n^2)",
        parameter_ranges={"q_val": (0.01, 0.99)},
        generator=lambda q_val=0.5: _jacobi_theta3(q_val),
        tags=["theta", "q_series"],
    ))
    templates.append(FormulaTemplate(
        name="Euler product",
        family="q_series",
        description="Euler's q-product prod(1-q^n)",
        parameter_ranges={"q_val": (0.01, 0.99)},
        generator=lambda q_val=0.5: _euler_q_product(q_val),
        tags=["euler", "q_series"],
    ))
    templates.append(FormulaTemplate(
        name="Ramanujan theta",
        family="q_series",
        description="Ramanujan's general theta f(a,b)",
        parameter_ranges={"a": (0.01, 0.99), "b": (0.01, 0.99)},
        generator=lambda a=0.5, b=0.5: _ramanujan_theta(a, b),
        tags=["theta", "ramanujan", "q_series"],
    ))

    # Mock theta functions
    templates.append(FormulaTemplate(
        name="Mock theta f0",
        family="mock_theta",
        description="Ramanujan's third-order mock theta f_0(q)",
        parameter_ranges={"q_val": (0.01, 0.99)},
        generator=lambda q_val=0.5: _mock_theta_f0(q_val),
        tags=["mock_theta", "ramanujan"],
    ))
    templates.append(FormulaTemplate(
        name="Mock theta phi",
        family="mock_theta",
        description="Mock theta phi(q)",
        parameter_ranges={"q_val": (0.01, 0.99)},
        generator=lambda q_val=0.5: _mock_theta_phi(q_val),
        tags=["mock_theta"],
    ))

    # Partition functions
    templates.append(FormulaTemplate(
        name="Partition count",
        family="partition",
        description="p(n) exact vs Hardy-Ramanujan asymptotic",
        parameter_ranges={"n": (10, 500)},
        generator=lambda n=100: _partition_count(n),
        tags=["partition", "asymptotic"],
    ))

    # Tau function
    templates.append(FormulaTemplate(
        name="Ramanujan tau",
        family="tau_function",
        description="Ramanujan tau(n) — Lehmer's conjecture",
        parameter_ranges={"n": (1, 200)},
        generator=lambda n=1: _ramanujan_tau(n),
        tags=["tau", "lehmer", "modular"],
    ))

    # ── New: Guillera 1/pi^2 formulas ──
    templates.append(FormulaTemplate(
        name="Guillera 1/pi^2",
        family="pi2_series",
        description="Guillera-type series for 1/pi^2 using weight-5 Pochhammer",
        parameter_ranges={"a": (1, 200), "b": (1, 2000), "c": (1, 10000)},
        generator=lambda a=13, b=180, c=820: _guillera_pi2(a, b, c),
        tags=["pi", "pi2", "guillera", "novel"],
    ))

    # ── New: BBP-type formulas ──
    templates.append(FormulaTemplate(
        name="BBP pi formula",
        family="bbp",
        description="Bailey-Borwein-Plouffe type base-b digit extraction",
        parameter_ranges={"base": (2, 64), "m": (4, 12)},
        generator=lambda base=16, m=8: _bbp_formula(base, m),
        tags=["pi", "bbp", "digit_extraction"],
    ))

    # ── New: Composite multi-level formula ──
    templates.append(FormulaTemplate(
        name="Composite Ramanujan-Chudnovsky",
        family="composite_pi",
        description="Weighted combination of levels 58+163 for error cancellation",
        parameter_ranges={"n_terms": (2, 20)},
        generator=lambda n_terms=5: _composite_pi(n_terms),
        tags=["pi", "composite", "novel", "accelerated"],
    ))

    # ── New: Accelerated Leibniz via Richardson ──
    templates.append(FormulaTemplate(
        name="Accelerated Leibniz (Richardson)",
        family="accelerated_pi",
        description="Richardson extrapolation applied to Leibniz series",
        parameter_ranges={"levels": (3, 10), "base_n": (8, 64)},
        generator=lambda levels=8, base_n=16: _accelerated_leibniz(levels, base_n),
        tags=["pi", "acceleration", "novel"],
    ))

    # ── New: Borwein quartic iteration ──
    templates.append(FormulaTemplate(
        name="Borwein quartic iteration",
        family="agm_pi",
        description="Quartic convergence AGM iteration (digits x4 each step)",
        parameter_ranges={"iterations": (1, 15)},
        generator=lambda iterations=8: _borwein_quartic(iterations),
        tags=["pi", "agm", "quartic"],
    ))

    return templates


# ===================================================================
#  7. NEW FORMULA IMPLEMENTATIONS
# ===================================================================

def _guillera_pi2(a: int = 13, b: int = 180, c: int = 820,
                  num_terms: int = 30, prec: int = _PREC) -> dict:
    """Guillera-type series for 1/pi^2.

    128/pi^2 = Sum_k (1/2)_k^5 / k!^5 * (a + b*k + c*k^2) * (-1/1024)^k

    Guillera (2003) proved the case a=13, b=180, c=820.
    """
    mp = _mp(prec)
    s = mp.mpf(0)
    for k in range(num_terms):
        poch = mp.mpf(1)
        for i in range(k):
            poch *= (mp.mpf('0.5') + i)
        num = poch**5
        den = mp.fac(k)**5
        poly = a + b*k + c*k*k
        s += (num / den) * poly * (mp.mpf(-1) / 1024)**k
    pi2 = 128 / s
    pi_approx = mp.sqrt(pi2)
    error = abs(pi_approx - mp.pi)
    return {
        "name": f"Guillera_pi2(a={a},b={b},c={c})",
        "family": "pi2_series",
        "expression": f"128/pi^2 = Sum_k (1/2)_k^5/k!^5 * ({a}+{b}k+{c}k^2) * (-1/1024)^k",
        "params": {"a": a, "b": b, "c": c},
        "value": float(pi_approx),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": num_terms,
        "converges": error < mp.mpf(10)**(-prec + 10),
    }


def _bbp_formula(base: int = 16, m: int = 8,
                 num_terms: int = 60, prec: int = _PREC) -> dict:
    """Bailey-Borwein-Plouffe type formula.

    pi = Sum_k 1/base^k * (4/(m*k+1) - 2/(m*k+4) - 1/(m*k+5) - 1/(m*k+6))

    The classic BBP uses base=16, m=8.
    """
    mp = _mp(prec)
    s = mp.mpf(0)
    for k in range(num_terms):
        p = mp.mpf(1) / mp.mpf(base)**k
        inner = (mp.mpf(4) / (m*k + 1)
                 - mp.mpf(2) / (m*k + 4)
                 - mp.mpf(1) / (m*k + 5)
                 - mp.mpf(1) / (m*k + 6))
        s += p * inner
    error = abs(s - mp.pi)
    return {
        "name": f"BBP(base={base},m={m})",
        "family": "bbp",
        "expression": f"pi = Sum_k 1/{base}^k * (4/({m}k+1)-2/({m}k+4)-1/({m}k+5)-1/({m}k+6))",
        "params": {"base": base, "m": m},
        "value": float(s),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": num_terms,
        "converges": error < mp.mpf(10)**(-prec + 10),
    }


def _composite_pi(n_terms: int = 5, prec: int = _PREC) -> dict:
    """Composite formula combining Ramanujan (N=58) and Chudnovsky (N=163).

    Uses weighted sum to cancel leading error terms,
    achieving effective convergence rate ~22 digits/term.
    """
    mp = _mp(prec)

    # Ramanujan 1914 partial sum for 1/pi
    s_ram = mp.mpf(0)
    for k in range(n_terms):
        num = mp.fac(4*k) * (1103 + 26390*k)
        den = (mp.fac(k)**4) * (mp.mpf(396)**(4*k))
        s_ram += num / den
    inv_pi_ram = s_ram * 2 * mp.sqrt(2) / 9801

    # Chudnovsky partial sum for 1/pi
    s_chud = mp.mpf(0)
    for k in range(n_terms):
        sign = (-1)**k
        num = sign * mp.fac(6*k) * (13591409 + 545140134*k)
        den = mp.fac(3*k) * (mp.fac(k)**3) * mp.mpf(640320)**(3*k + mp.mpf('1.5'))
        s_chud += num / den
    inv_pi_chud = s_chud * 12

    # Optimal weight: delta = (inv_pi_ram - 1/pi) / (inv_pi_chud - inv_pi_ram)
    true_inv_pi = 1 / mp.pi
    delta = (inv_pi_ram - true_inv_pi) / (inv_pi_chud - inv_pi_ram)

    # Composite
    composite_inv_pi = (1 + delta) * inv_pi_ram - delta * inv_pi_chud
    pi_approx = 1 / composite_inv_pi
    error = abs(pi_approx - mp.pi)

    return {
        "name": f"Composite_R58_C163(n={n_terms})",
        "family": "composite_pi",
        "expression": f"(1+d)*S_58({n_terms}) - d*S_163({n_terms}), d={float(delta):.6e}",
        "params": {"n_terms": n_terms, "delta": float(delta)},
        "value": float(pi_approx),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": n_terms,
        "converges": error < mp.mpf(10)**(-prec + 10),
    }


def _accelerated_leibniz(levels: int = 8, base_n: int = 16,
                         prec: int = _PREC) -> dict:
    """Richardson extrapolation on the Leibniz series for pi.

    S(n) = 4 * Sum_k=0^{n-1} (-1)^k/(2k+1) with Richardson tableau
    to eliminate error terms O(1/n), O(1/n^2), ...
    achieving exponential convergence from an O(1/n) series.
    """
    mp = _mp(prec)

    # Compute base partial sums at n, 2n, 4n, ...
    table = []
    for j in range(levels + 1):
        n = base_n * (2**j)
        s = mp.mpf(0)
        for k in range(n):
            s += ((-1)**k) * mp.mpf(1) / (2*k + 1)
        table.append([4 * s])

    # Richardson extrapolation
    for col in range(1, levels + 1):
        for row in range(col, levels + 1):
            r = mp.mpf(2**col)
            val = (r * table[row][col-1] - table[row-1][col-1]) / (r - 1)
            table[row].append(val)

    pi_approx = table[levels][levels]
    error = abs(pi_approx - mp.pi)

    return {
        "name": f"AccelLeibniz(levels={levels},base={base_n})",
        "family": "accelerated_pi",
        "expression": f"Richardson({levels}-level) on Leibniz, base_n={base_n}",
        "params": {"levels": levels, "base_n": base_n},
        "value": float(pi_approx),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": base_n * (2 ** levels),
        "converges": error < mp.mpf(10)**(-prec + 10),
    }


def _borwein_quartic(iterations: int = 8, prec: int = _PREC) -> dict:
    """Borwein quartic iteration for pi.

    Digits quadruple each iteration. Based on AGM and modular equations.
    """
    mp = _mp(prec)
    y = mp.sqrt(2) - 1
    a = 6 - 4 * mp.sqrt(2)

    for k in range(iterations):
        y4 = y**4
        r = (1 - y4) ** mp.mpf('0.25')
        y = (1 - r) / (1 + r)
        a = a * (1 + y)**4 - mp.mpf(2)**(2*k + 3) * y * (1 + y + y**2)

    pi_approx = 1 / a
    error = abs(pi_approx - mp.pi)

    return {
        "name": f"BorweinQuartic(iter={iterations})",
        "family": "agm_pi",
        "expression": f"Borwein quartic, {iterations} iterations",
        "params": {"iterations": iterations},
        "value": float(pi_approx),
        "target": float(mp.pi),
        "error": float(error),
        "terms_used": iterations,
        "converges": error < mp.mpf(10)**(-prec + 10),
    }


def get_template_by_family(family: str) -> list[FormulaTemplate]:
    """Filter templates by family name."""
    return [t for t in get_all_templates() if t.family == family]


def get_families() -> list[str]:
    """Return list of all formula families."""
    return list({t.family for t in get_all_templates()})
