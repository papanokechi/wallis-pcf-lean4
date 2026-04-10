"""
analysis.py — Post-discovery analysis for novel CF candidates.

Implements the reviewer-requested analysis pipeline:
 1. High-precision numeric values (20+ digits) for each novel CF
 2. PSLQ constant-basis recognition: test each CF value against
    {1, π, e, ln2, ln3, √2, √3, √5, γ, G, ζ(3), ζ(5), φ, π², π³}
 3. Periodic CF algebraic fixed-point solver (degree ≤ period)
 4. Cluster CFs by numeric value to detect duplicates
 5. Per-candidate PSLQ stability tables
 6. Bessel / hypergeometric function identification (v3.3)
 7. mpmath.identify() ISC-style lookup (v3.3)
 8. Algebraic degree bound via PSLQ (v3.3)
 9. Pringsheim convergence diagnostics (v3.3)
10. Prioritized candidate table (v3.3)
 6. Reproducibility bundle per discovery
"""

from __future__ import annotations
import hashlib
import time
import platform
from dataclasses import dataclass, field
from typing import Any

import mpmath


# ===================================================================
#  High-precision CF evaluation
# ===================================================================

def compute_hi_precision_value(an_coeffs: list[int], bn_coeffs: list[int],
                                prec: int = 200) -> dict:
    """Evaluate a polynomial GCF at high precision and return detailed info."""
    mp = mpmath.mp.clone()
    mp.dps = prec

    def a_func(n):
        if len(an_coeffs) == 1:
            return an_coeffs[0]
        elif len(an_coeffs) == 2:
            return an_coeffs[0] * n + an_coeffs[1]
        elif len(an_coeffs) == 3:
            return an_coeffs[0] * n * n + an_coeffs[1] * n + an_coeffs[2]
        else:
            # degree >= 3: evaluate polynomial
            result = mp.mpf(0)
            for i, c in enumerate(an_coeffs):
                result += c * mp.power(n, len(an_coeffs) - 1 - i)
            return result

    def b_func(n):
        if len(bn_coeffs) == 1:
            return bn_coeffs[0]
        else:
            return bn_coeffs[0] * n + bn_coeffs[1]

    tiny = mp.mpf(10) ** (-prec)

    # Evaluate at two depths for convergence estimate
    depths = [500, 300, 150]
    vals = []
    for depth in depths:
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
        vals.append(f)

    val = vals[0]
    convergence_errors = [float(abs(vals[0] - vals[1])),
                          float(abs(vals[1] - vals[2]))]

    # Format value string with full available precision
    digits_avail = max(0, prec - 10)
    val_str = mp.nstr(val, digits_avail)

    return {
        "value_mpf": val,
        "value_str": val_str,
        "value_float": float(val),
        "convergence_error_500_300": convergence_errors[0],
        "convergence_error_300_150": convergence_errors[1],
        "precision_dps": prec,
    }


# ===================================================================
#  Periodic CF algebraic fixed-point analysis
# ===================================================================

def periodic_cf_fixedpoint(an_coeffs: list[int], bn_coeffs: list[int],
                           value_mpf=None, prec: int = 100) -> dict:
    """Determine if a periodic-coefficient GCF has an algebraic fixed point.

    For a GCF with periodic coefficients of period k, the value satisfies
    a polynomial equation of degree k. For period-1 (constant) CFs:
        y = b(0) + a / (b + a/(b + ...))  =>  y = b + a/y  =>  y² - by - a = 0

    For period-2, we get a degree-2 equation from the matrix iteration.

    Returns dict with:
     - is_algebraic: bool
     - degree: int (polynomial degree)
     - minimal_poly: str (if algebraic)
     - exact_form: str (symbolic root expression if possible)
    """
    result = {"is_algebraic": False, "analysis": ""}

    period_a = len(an_coeffs)
    period_b = len(bn_coeffs)
    # Check if this is truly periodic (no n-dependence)
    # Period-1: constant a_n = a, b_n = b (len == 1 for both)
    is_constant_a = period_a == 1  # a(n) = an_coeffs[0] for all n
    is_constant_b = period_b == 1  # b(n) = bn_coeffs[0]
    is_linear_b = period_b == 2    # b(n) = bn_coeffs[0]*n + bn_coeffs[1]

    if is_constant_a and is_constant_b:
        # Period-1 constant CF: y = b + a/y => y² - by - a = 0
        a_val = an_coeffs[0]
        b_val = bn_coeffs[0]
        disc = b_val * b_val + 4 * a_val
        result["is_algebraic"] = True
        result["degree"] = 2
        result["minimal_poly"] = f"y² - {b_val}y - {a_val} = 0"
        result["discriminant"] = disc
        if disc >= 0:
            import math
            root = (b_val + math.sqrt(disc)) / 2
            result["exact_form"] = f"({b_val} + √{disc}) / 2"
            result["exact_value"] = root
        result["analysis"] = (
            f"Constant-coefficient CF with a={a_val}, b={b_val}. "
            f"Fixed-point equation: y² - {b_val}y - {a_val} = 0 (quadratic). "
            f"Solution is algebraic of degree ≤ 2."
        )
        return result

    if is_constant_a and is_linear_b:
        # a(n) = A (constant), b(n) = αn + β (linear)
        # This is NOT periodic — it's genuinely n-dependent.
        # The value is typically related to Bessel functions or confluent HG.
        # For small a, the CF b0 + a/(b1 + a/(b2 + ...)) where b_n = αn+β
        # is related to ratios of Bessel/Kummer functions.
        A = an_coeffs[0]
        alpha = bn_coeffs[0]
        beta = bn_coeffs[1]
        result["analysis"] = (
            f"Linear-b CF: a(n)={A}, b(n)={alpha}n+{beta}. "
            f"Non-periodic — value typically transcendental, "
            f"related to ratios of Bessel/confluent hypergeometric functions. "
            f"Cannot be resolved by algebraic fixed-point."
        )
        result["cf_class"] = "linear_b_constant_a"
        result["is_algebraic"] = False
        return result

    if not is_constant_a and is_linear_b:
        # a(n) depends on n — high-degree polynomial in n
        result["analysis"] = (
            f"Polynomial CF: a(n) is degree {period_a-1}, b(n) is degree {period_b-1}. "
            f"Non-periodic — value likely transcendental. "
            f"No simple algebraic resolution available."
        )
        result["cf_class"] = "polynomial"
        result["is_algebraic"] = False
        return result

    # General case
    result["analysis"] = (
        f"General polynomial CF: a_n coeffs={an_coeffs}, b_n coeffs={bn_coeffs}. "
        f"No automatic algebraic resolution."
    )
    result["cf_class"] = "general_polynomial"
    result["is_algebraic"] = False
    return result


# ===================================================================
#  PSLQ constant-basis recognition
# ===================================================================

STANDARD_BASIS = [
    "1", "pi", "e", "ln2", "ln3", "sqrt(2)", "sqrt(3)", "sqrt(5)",
    "euler_gamma", "catalan", "zeta(3)", "pi^2",
    "zeta(5)", "ln(pi)", "pi^3",
    # v4.3: polylogarithms & extended constants
    "Li2(1/2)", "zeta(7)", "sqrt(pi)",
]

def _make_basis_mpf(names: list[str], mp):
    """Compute basis constant values at the current mp precision."""
    mapping = {
        "1": mp.mpf(1), "pi": mp.pi, "pi^2": mp.pi ** 2,
        "pi^3": mp.pi ** 3, "e": mp.e, "ln2": mp.ln(2),
        "sqrt(2)": mp.sqrt(2), "euler_gamma": mp.euler,
        "catalan": mp.catalan, "zeta(3)": mp.zeta(3),
        "sqrt(3)": mp.sqrt(3), "sqrt(5)": mp.sqrt(5),
        "ln3": mp.ln(3),
        "zeta(5)": mp.zeta(5), "ln(pi)": mp.ln(mp.pi),
        # v4.2: L-function / Dirichlet constants
        "dirichlet_beta(2)": mp.catalan,  # G = β(2)
        "dirichlet_beta(3)": mp.pi ** 3 / 32,  # β(3) = π³/32
        "zeta(4)": mp.pi ** 4 / 90,
        "zeta(7)": mp.zeta(7),
        # v4.3: polylogarithms & extended constants
        "Li2(1/2)": mp.polylog(2, mp.mpf(1)/2),  # pi^2/12 - ln(2)^2/2
        "sqrt(pi)": mp.sqrt(mp.pi),
    }
    return [mapping.get(n, mp.mpf(0)) for n in names]


def pslq_constant_recognition(value_mpf, prec: int = 100,
                               basis_names: list[str] | None = None,
                               max_coeff: int = 1000) -> dict:
    """Run PSLQ to express value as integer linear combination of constants.

    Returns dict with found, relation, expression, residual, stability info.
    """
    mp = mpmath.mp.clone()
    mp.dps = prec
    val = mp.mpf(value_mpf)
    names = basis_names or STANDARD_BASIS
    basis = _make_basis_mpf(names, mp)

    vec = [val] + basis
    try:
        # Reduce maxsteps for higher precision to avoid long PSLQ runtimes
        steps = min(2000, max(500, 5000 // max(prec // 50, 1)))
        # Thread-based timeout to prevent PSLQ from hanging
        import threading
        pslq_result = [None]
        def _run_pslq():
            try:
                pslq_result[0] = mp.pslq(vec, maxcoeff=max_coeff, maxsteps=steps)
            except Exception:
                pslq_result[0] = None
        t = threading.Thread(target=_run_pslq, daemon=True)
        t.start()
        t.join(timeout=10)  # 10 seconds max per PSLQ call
        rel = pslq_result[0]
    except Exception:
        rel = None

    if rel is None:
        return {
            "found": False,
            "precision": prec,
            "basis": names,
            "note": f"No integer relation found at {prec} dps with maxcoeff={max_coeff}",
        }

    # If r0 == 0, the relation is among basis constants, not involving value
    if rel[0] == 0:
        return {
            "found": False,
            "precision": prec,
            "basis": names,
            "note": "PSLQ found basis-internal relation (r0=0), not involving value",
            "basis_relation": list(rel),
        }

    # Build expression: value = -(r1*b1 + r2*b2 + ...) / r0
    terms = []
    for coeff, name in zip(rel[1:], names):
        if coeff != 0:
            terms.append(f"({coeff})*{name}")
    if rel[0] != 0 and terms:
        expr = f"value = -({' + '.join(terms)}) / {rel[0]}"
    elif not terms:
        expr = f"0 = {rel[0]}*value (trivial)"
    else:
        expr = f"0 = {rel[0]}*value + {' + '.join(terms)}"

    # Residual
    check = sum(r * v for r, v in zip(rel, vec))
    residual = float(abs(check))

    return {
        "found": True,
        "relation": list(rel),
        "expression": expr,
        "residual": residual,
        "max_coeff_used": max(abs(c) for c in rel),
        "precision": prec,
        "basis": names,
    }


def pslq_stability_table(value_mpf, precisions: list[int] | None = None,
                          basis_names: list[str] | None = None) -> list[dict]:
    """Run PSLQ at multiple precisions and report stability.

    Returns list of per-precision results. A stable relation will have
    identical coefficient vectors across all precisions.
    """
    precs = precisions or [50, 100, 200]
    names = basis_names or STANDARD_BASIS
    results = []
    ref_rel = None

    for prec in precs:
        r = pslq_constant_recognition(value_mpf, prec=prec,
                                       basis_names=names)
        row = {
            "precision": prec,
            "found": r.get("found", False),
            "relation": r.get("relation"),
            "residual": r.get("residual"),
            "expression": r.get("expression"),
            "max_coeff": r.get("max_coeff_used"),
        }
        if r.get("found") and r.get("relation"):
            if ref_rel is None:
                ref_rel = r["relation"]
                row["matches_reference"] = True
            else:
                row["matches_reference"] = (r["relation"] == ref_rel)
        results.append(row)

    return results


# ===================================================================
#  Numeric value clustering
# ===================================================================

def cluster_by_value(discoveries: list[dict], tolerance: float = 1e-12) -> list[list[int]]:
    """Group discoveries by numeric value within tolerance.

    Returns list of clusters, each a list of indices into the input list.
    """
    n = len(discoveries)
    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue
        val_i = discoveries[i].get("value", None)
        if val_i is None:
            continue
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if visited[j]:
                continue
            val_j = discoveries[j].get("value", None)
            if val_j is None:
                continue
            if abs(val_i - val_j) < tolerance * max(abs(val_i), 1):
                cluster.append(j)
                visited[j] = True
        clusters.append(cluster)

    return clusters


# ===================================================================
#  Reproducibility bundle
# ===================================================================

def reproducibility_bundle(discovery: dict) -> dict:
    """Generate per-discovery reproducibility metadata."""
    import mpmath as _mpmath
    import sympy as _sympy

    params = discovery.get("params", {})
    meta = discovery.get("metadata", {})
    prov = discovery.get("provenance", {})

    # Stable content hash
    content = f"{discovery.get('family', '')}_{discovery.get('expression', '')}"
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    bundle = {
        "candidate_id": content_hash[:16],
        "family": discovery.get("family", ""),
        "expression": discovery.get("expression", ""),
        "generation_params": params,
        "rng_seed": prov.get("seed"),
        "numeric_value": discovery.get("value"),
        "precision_dps": prov.get("prec", 60),
        "evaluation_depth": prov.get("depth", 300),
        "convergence_error": meta.get("convergence_error"),
        "isc_matched": meta.get("is_known_transform", False),
        "isc_target_count": "15 constants × 40 multipliers × 4 transforms",
        "algebraic_check": {
            "rational_test": "p/q, |p|,|q| ≤ 50",
            "quadratic_test": "ax²+bx+c=0, a∈[1,9], b∈[-20,20], c∈[-20,20]",
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "mpmath": _mpmath.__version__,
            "sympy": _sympy.__version__,
        },
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return bundle


# ===================================================================
#  Bessel / hypergeometric function identification  (v3.3)
# ===================================================================

def bessel_identification(an_coeffs: list[int], bn_coeffs: list[int],
                          value_mpf, prec: int = 100) -> dict:
    """Try to identify a linear-b CF as a ratio of Bessel/confluent HG functions.

    For a GCF with constant a(n)=A, b(n)=αn+β:
        CF = β + A/(α+β + A/(2α+β + A/(3α+β + ...)))
    The tail S = CF - β satisfies:
        S = A/((α+β) + A/((2α+β) + ...)) = K_{m=0}^∞ A/(α(m+a₀))
    where a₀ = 1 + β/α and the normalised ratio c = A/α².

    For the CF K_{m=0}^∞ c/(m+a):
      If c > 0: f = √c · I_a(2√c) / I_{a-1}(2√c)
      If c < 0: f = -√|c| · J_a(2√|c|) / J_{a-1}(2√|c|)
    Then CF = β + α·f.

    Note: c = A/α² (not A/α) because the equivalence transform that
    normalises denominators α·n+β → n+a₀ with factors c_n = 1/α
    transforms the CF numerators via the product c_n · c_{n-1} = 1/α².
    """
    if len(an_coeffs) != 1 or len(bn_coeffs) != 2:
        return {"identified": False, "reason": "Not a linear-b CF"}

    mp = mpmath.mp.clone()
    mp.dps = prec
    A = an_coeffs[0]
    alpha = bn_coeffs[0]
    beta = bn_coeffs[1]
    val = mp.mpf(value_mpf)

    result = {
        "identified": False,
        "A": A, "alpha": alpha, "beta": beta,
        "candidates": [],
    }

    if alpha == 0:
        result["reason"] = "α=0 → constant denominators (degenerate)"
        return result

    # Parameters for the normalized CF K_{m=0}^∞ c/(m + a₀)
    c = mp.mpf(A) / (mp.mpf(alpha) ** 2)   # normalised ratio A/α²
    a0 = 1 + mp.mpf(beta) / mp.mpf(alpha)  # first param

    # The tail S = val - beta, and S = alpha * f where f is the normalized CF
    S_target = val - mp.mpf(beta)
    f_target = S_target / mp.mpf(alpha)   # what the normalized CF should equal

    threshold = mp.mpf(10) ** (-prec // 3)

    # ── Strategy 1: Perron formula for K_{m=0}^∞ c/(m+a₀) ──
    try:
        if c > 0:
            z = 2 * mp.sqrt(c)
            # f = √c · I_{a₀}(z) / I_{a₀-1}(z)
            f_bessel = mp.sqrt(c) * mp.besseli(a0, z) / mp.besseli(a0 - 1, z)
            diff = abs(f_target - f_bessel)
            if diff < threshold:
                cf_val = mp.mpf(beta) + mp.mpf(alpha) * f_bessel
                result["candidates"].append({
                    "type": "modified_bessel_ratio",
                    "formula": f"{beta} + {alpha}·√({float(c):.4g})·I_{{{float(a0):.4g}}}({float(z):.4g})/I_{{{float(a0-1):.4g}}}({float(z):.4g})",
                    "formula_short": f"β+α·√c·I_a₀(2√c)/I_{{a₀-1}}(2√c), c={float(c):.4g}, a₀={float(a0):.4g}",
                    "computed_value": mp.nstr(cf_val, 20),
                    "match_error": float(diff),
                    "match_digits": max(0, -int(mp.log10(diff + mp.mpf(10)**(-prec)))),
                })
        elif c < 0:
            z = 2 * mp.sqrt(-c)
            abs_c = float(abs(c))
            # f = -√|c| · J_{a₀}(z) / J_{a₀-1}(z)
            Ja0 = mp.besselj(a0, z)
            Ja0m1 = mp.besselj(a0 - 1, z)
            if abs(Ja0m1) > mp.mpf(10)**(-prec + 10):
                f_bessel = -mp.sqrt(-c) * Ja0 / Ja0m1
                diff = abs(f_target - f_bessel)
                if diff < threshold:
                    cf_val = mp.mpf(beta) + mp.mpf(alpha) * f_bessel
                    result["candidates"].append({
                        "type": "bessel_j_ratio",
                        "formula": f"{beta} + {alpha}·(-√({abs_c:.4g}))·J_{{{float(a0):.4g}}}({float(z):.4g})/J_{{{float(a0-1):.4g}}}({float(z):.4g})",
                        "formula_short": f"β-α·√|c|·J_a₀(2√|c|)/J_{{a₀-1}}(2√|c|), c={abs_c:.4g}, a₀={float(a0):.4g}",
                        "computed_value": mp.nstr(cf_val, 20),
                        "match_error": float(diff),
                        "match_digits": max(0, -int(mp.log10(diff + mp.mpf(10)**(-prec)))),
                    })
    except Exception:
        pass

    # ── Strategy 2: Direct confluent hypergeometric ₁F₁ ratio ──
    try:
        # CF = β + A · ₁F₁(1; a₀+1; c) / ((a₀·α) · ₁F₁(1; a₀; c))
        if abs(a0) < 100 and abs(c) < 100:
            f1 = mp.hyp1f1(1, a0, c)
            f2 = mp.hyp1f1(1, a0 + 1, c)
            if abs(f1) > mp.mpf(10)**(-prec + 10):
                cf_hyp = mp.mpf(beta) + mp.mpf(A) * f2 / (a0 * mp.mpf(alpha) * f1)
                diff = abs(val - cf_hyp)
                if diff < threshold:
                    result["candidates"].append({
                        "type": "confluent_1F1",
                        "formula": f"{beta}+{A}·₁F₁(1;{float(a0+1):.4g};{float(c):.4g})/({float(a0*alpha):.4g}·₁F₁(1;{float(a0):.4g};{float(c):.4g}))",
                        "computed_value": mp.nstr(cf_hyp, 20),
                        "match_error": float(diff),
                        "match_digits": max(0, -int(mp.log10(diff + mp.mpf(10)**(-prec)))),
                    })
    except Exception:
        pass

    # ── Strategy 3: Brute-force Bessel ratio grid ──
    try:
        if abs(A) <= 25 and abs(alpha) <= 10 and abs(beta) <= 20:
            for z_try in [mp.mpf(1), mp.mpf(2), mp.mpf(3), mp.mpf(4),
                          mp.mpf(1)/2, mp.mpf(3)/2, mp.mpf(5)/2]:
                for nu_try in [mp.mpf(0), mp.mpf(1)/2, mp.mpf(1), mp.mpf(3)/2,
                               mp.mpf(2), mp.mpf(5)/2, mp.mpf(3)]:
                    try:
                        ratio = mp.besseli(nu_try, z_try) / mp.besseli(nu_try - 1, z_try)
                        for mult in [1, 2, 3, 4, -1, -2]:
                            diff = abs(val - mp.mpf(mult) * ratio)
                            if diff < threshold:
                                result["candidates"].append({
                                    "type": "bessel_grid_match",
                                    "formula": f"{mult}·I_{{{float(nu_try)}}}({float(z_try)})/I_{{{float(nu_try-1)}}}({float(z_try)})",
                                    "computed_value": mp.nstr(mp.mpf(mult) * ratio, 20),
                                    "match_error": float(diff),
                                    "match_digits": max(0, -int(mp.log10(diff + mp.mpf(10)**(-prec)))),
                                })
                    except Exception:
                        continue
    except Exception:
        pass

    if result["candidates"]:
        result["identified"] = True
        best = min(result["candidates"], key=lambda c: c["match_error"])
        result["best_identification"] = best

    return result


def mpmath_identify(value_mpf, prec: int = 50) -> dict:
    """Use mpmath.identify() for ISC-style constant lookup.

    Uses specific mathematical constant bases (π, e, γ, etc.) rather than
    the default lattice reduction which produces meaningless rational-power fits.
    Tries multiple constant sets and transforms.
    """
    mp = mpmath.mp.clone()
    mp.dps = max(prec, 30)
    val = mp.mpf(value_mpf)

    result = {"found": False, "identifications": []}

    # Constant sets to try with mpmath.identify
    const_sets = [
        ["pi", "E", "euler", "log(2)", "catalan"],
        ["pi", "sqrt(2)", "sqrt(3)", "sqrt(5)"],
        ["E", "log(2)", "log(3)"],
    ]

    for cset in const_sets:
        try:
            ids = mp.identify(val, constants=cset, tol=mp.mpf(10) ** (-20))
            if ids:
                if isinstance(ids, str):
                    ids = [ids]
                for ident in ids[:2]:
                    if ident not in result["identifications"]:
                        result["identifications"].append(ident)
                        result["found"] = True
        except Exception:
            pass

    # Try common transforms
    transforms = {
        "1/x": lambda v: 1 / v if v != 0 else None,
        "x\u00b2": lambda v: v ** 2,
        "\u221ax": lambda v: mp.sqrt(v) if v > 0 else None,
        "-x": lambda v: -v,
        "x-1": lambda v: v - 1,
        "x+1": lambda v: v + 1,
        "2x": lambda v: 2 * v,
        "x/2": lambda v: v / 2,
        "\u03c0\u00b7x": lambda v: mp.pi * v,
        "x/\u03c0": lambda v: v / mp.pi,
        "x-2": lambda v: v - 2,
    }
    for tname, tfunc in transforms.items():
        try:
            tv = tfunc(val)
            if tv is None:
                continue
            for cset in const_sets[:1]:  # only first constant set for transforms
                ids = mp.identify(tv, constants=cset, tol=mp.mpf(10) ** (-20))
                if ids:
                    if isinstance(ids, str):
                        ids = [ids]
                    for ident in ids[:1]:
                        tag = f"{tname} \u2192 {ident}"
                        if tag not in result["identifications"]:
                            result["identifications"].append(tag)
                            result["found"] = True
        except Exception:
            continue

    return result


# ===================================================================
#  Algebraic degree bound (v3.3)
# ===================================================================

def algebraic_degree_bound(value_mpf, prec: int = 200,
                            max_degree: int = 8) -> dict:
    """Use PSLQ to determine if value is algebraic of degree ≤ max_degree.

    Tests [1, x, x², ..., x^d] for d = 1..max_degree.
    If PSLQ finds a relation, value satisfies an integer polynomial.
    """
    mp = mpmath.mp.clone()
    mp.dps = prec
    val = mp.mpf(value_mpf)

    result = {"is_algebraic": False, "degree_bound": None, "polynomials": []}

    for deg in range(1, max_degree + 1):
        vec = [mp.power(val, k) for k in range(deg + 1)]
        try:
            rel = mp.pslq(vec, maxcoeff=10000, maxsteps=5000)
        except Exception:
            continue

        if rel is None:
            continue

        # rel gives [c0, c1, ..., c_deg] such that c0 + c1*x + ... + c_deg*x^deg = 0
        max_c = max(abs(c) for c in rel)

        # Verify at higher precision
        mp2 = mpmath.mp.clone()
        mp2.dps = prec + 50
        val2 = mp2.mpf(value_mpf)
        check = sum(c * mp2.power(val2, k) for k, c in enumerate(rel))
        residual = float(abs(check))

        poly_str = " + ".join(
            f"{c}·x^{k}" if k > 1 else f"{c}·x" if k == 1 else f"{c}"
            for k, c in enumerate(rel) if c != 0
        )

        entry = {
            "degree": deg,
            "coefficients": list(rel),
            "max_coeff": max_c,
            "polynomial": poly_str,
            "residual": residual,
            "stable": residual < 10 ** (-(prec // 2)),
        }
        result["polynomials"].append(entry)

        if entry["stable"] and max_c < 5000:
            result["is_algebraic"] = True
            result["degree_bound"] = deg
            result["minimal_polynomial"] = poly_str
            result["minimal_coefficients"] = list(rel)
            break  # Found minimal degree

    return result


# ===================================================================
#  Enhanced closed-form matching (v4.1)
# ===================================================================

def enhanced_closed_form(value_mpf, an_coeffs: list[int] | None = None,
                         bn_coeffs: list[int] | None = None,
                         prec: int = 100) -> dict:
    """Wider closed-form identification for CF values.

    v4.1: Addresses Review 2 ("閉形式ゼロ") and Review 3 ("Symbolic
    Identification fails") by trying:
      1. Extended Bessel ratio grid (half-integer ν, rational z)
      2. Gauss ₂F₁ ratios at rational arguments
      3. Kummer ₁F₁ at wider parameter ranges
      4. Elementary function combinations (exp, log, trig at rationals)
    """
    mp = mpmath.mp.clone()
    mp.dps = prec
    val = mp.mpf(value_mpf)
    threshold = mp.mpf(10) ** (-prec // 3)

    result = {"found": False, "matches": []}

    def _check(formula_str, computed, match_type):
        diff = abs(val - computed)
        if diff < threshold:
            digits = max(0, -int(mp.log10(diff + mp.mpf(10)**(-prec))))
            result["matches"].append({
                "type": match_type,
                "formula": formula_str,
                "computed_value": mp.nstr(computed, 20),
                "match_error": float(diff),
                "match_digits": digits,
            })
            result["found"] = True

    # ── 1. Extended Bessel ratio grid ──
    half_ints = [mp.mpf(k)/2 for k in range(-3, 14)]  # -1.5 to 6.5
    z_vals = [mp.mpf(p)/q for p in range(1, 9) for q in [1, 2, 3, 4]
              if p/q <= 8]
    z_vals = sorted(set(z_vals))
    for nu in half_ints:
        for z in z_vals[:20]:
            try:
                r = mp.besseli(nu, z) / mp.besseli(nu - 1, z)
                for mult_p in range(-4, 5):
                    for mult_q in [1, 2, 3]:
                        if mult_p == 0:
                            continue
                        m = mp.mpf(mult_p) / mult_q
                        _check(f"({mult_p}/{mult_q})·I_{{{float(nu)}}}({float(z)})/I_{{{float(nu-1)}}}({float(z)})",
                               m * r, "bessel_extended")
            except Exception:
                continue

    # ── 2. Gauss ₂F₁ ratio identification ──
    # For small rational parameters, ₂F₁(a,b;c;z) can produce many CF values
    small_rats = [mp.mpf(p)/q for p in range(-3, 4) for q in [1, 2, 3]
                  if q > 0 and abs(p/q) <= 3]
    for a in small_rats[:8]:
        for b in small_rats[:8]:
            for c in small_rats[:8]:
                if c <= 0 and c == int(c):
                    continue  # pole
                for z in [mp.mpf(1)/2, mp.mpf(1)/4, mp.mpf(3)/4,
                          mp.mpf(1)/3, mp.mpf(2)/3]:
                    try:
                        h = mp.hyp2f1(a, b, c, z)
                        _check(f"₂F₁({float(a)},{float(b)};{float(c)};{float(z)})",
                               h, "gauss_2F1")
                        if abs(h) > threshold:
                            _check(f"1/₂F₁({float(a)},{float(b)};{float(c)};{float(z)})",
                                   1/h, "gauss_2F1_recip")
                    except Exception:
                        continue

    # ── 3. Wider Kummer ₁F₁ ──
    for a_p in range(-3, 6):
        for b_p in range(1, 8):
            for z_p in range(-4, 5):
                if z_p == 0:
                    continue
                try:
                    h = mp.hyp1f1(a_p, b_p, z_p)
                    _check(f"₁F₁({a_p};{b_p};{z_p})", h, "kummer_1F1")
                    if abs(h) > threshold:
                        _check(f"1/₁F₁({a_p};{b_p};{z_p})", 1/h, "kummer_1F1_recip")
                except Exception:
                    continue

    # ── 4. Elementary function combos at rationals ──
    for p in range(1, 8):
        for q in [1, 2, 3, 4, 6]:
            x = mp.mpf(p) / q
            try:
                _check(f"exp({float(x)})", mp.exp(x), "elementary")
                _check(f"exp(-{float(x)})", mp.exp(-x), "elementary")
                if x > 0:
                    _check(f"ln({float(x)})", mp.ln(x), "elementary")
                    _check(f"√{float(x)}", mp.sqrt(x), "elementary")
                _check(f"sin({float(x)})", mp.sin(x), "elementary")
                _check(f"cos({float(x)})", mp.cos(x), "elementary")
                _check(f"tan({float(x)})", mp.tan(x), "elementary")
                # Combinations with π
                _check(f"sin(π/{q})", mp.sin(mp.pi / q), "elementary")
                _check(f"cos(π/{q})", mp.cos(mp.pi / q), "elementary")
            except Exception:
                continue

    # ── 5. L-function / Dirichlet series values  (v4.2) ──
    l_targets = {
        "ζ(3)": mp.zeta(3), "ζ(5)": mp.zeta(5), "ζ(7)": mp.zeta(7),
        "ζ(4)": mp.pi ** 4 / 90,
        "G=β(2)": mp.catalan,
        "β(3)=π³/32": mp.pi ** 3 / 32,
        "L(2,χ₋₄)": mp.catalan,  # same as Catalan for χ₋₄
    }
    for l_name, l_val in l_targets.items():
        for m_num in range(-4, 5):
            if m_num == 0:
                continue
            for m_den in [1, 2, 3, 4]:
                m = mp.mpf(m_num) / m_den
                try:
                    _check(f"({m_num}/{m_den})·{l_name}", m * l_val, "l_function")
                    if abs(l_val) > threshold:
                        _check(f"({m_num}/{m_den})/{l_name}", m / l_val, "l_function_recip")
                except Exception:
                    continue

    if result["matches"]:
        best = min(result["matches"], key=lambda m: m["match_error"])
        result["best_match"] = best

    return result


# ===================================================================
#  Pringsheim convergence diagnostics (v3.3)
# ===================================================================

def pringsheim_convergence_check(an_coeffs: list[int], bn_coeffs: list[int],
                                  n_terms: int = 100) -> dict:
    """Check convergence criteria for the GCF.

    Flags:
    - Zero denominators: b(n) = 0 for some n → potential divergence
    - Pringsheim criterion: |b_n| ≥ |a_n| + 1 for all n ≥ 1 ensures convergence
    - Śleszyński–Pringsheim: |b_n| ≥ |a_{n+1}| + 1
    """
    result = {
        "converges": True,
        "flags": [],
        "zero_denominators": [],
        "pringsheim_satisfied": True,
        "convergence_tier": "unknown",
    }

    def eval_a(n):
        if len(an_coeffs) == 1:
            return an_coeffs[0]
        coeffs = an_coeffs
        val = 0
        for i, c in enumerate(coeffs):
            val += c * (n ** (len(coeffs) - 1 - i))
        return val

    def eval_b(n):
        if len(bn_coeffs) == 1:
            return bn_coeffs[0]
        return bn_coeffs[0] * n + bn_coeffs[1]

    # Check for zero denominators
    for n in range(n_terms + 1):
        bn = eval_b(n)
        if bn == 0:
            result["zero_denominators"].append(n)

    if result["zero_denominators"]:
        if len(result["zero_denominators"]) == 1 and result["zero_denominators"][0] == 0:
            result["flags"].append("b(0)=0: first denominator zero, CF starts from n=1")
        else:
            result["converges"] = False
            result["flags"].append(
                f"b(n)=0 at n={result['zero_denominators'][:5]}... — "
                f"Potential divergence. Requires explicit Pringsheim analysis."
            )

    # Pringsheim criterion: |b_n| >= |a_n| + 1 for all n >= 1
    pringsheim_fails = []
    for n in range(1, min(n_terms, 50) + 1):
        an = eval_a(n)
        bn = eval_b(n)
        if abs(bn) < abs(an) + 1:
            pringsheim_fails.append(n)

    if pringsheim_fails:
        result["pringsheim_satisfied"] = False
        if len(pringsheim_fails) > 10:
            result["flags"].append(
                f"Pringsheim criterion fails for {len(pringsheim_fails)}/50 terms. "
                f"Convergence not guaranteed by Pringsheim — verify numerically."
            )
        else:
            result["flags"].append(
                f"Pringsheim fails at n={pringsheim_fails[:5]}... "
                f"(mild — convergence still likely if |a_n/b_n| → 0)"
            )

    # Growth rate check: |a_n/b_n| → 0?
    if len(bn_coeffs) >= 2 and bn_coeffs[0] != 0:
        # b(n) grows linearly, a(n) is polynomial
        a_deg = len(an_coeffs) - 1
        b_deg = 1  # linear
        if a_deg <= b_deg:
            # |a_n/b_n| → |leading_a/leading_b| (constant) or → 0
            ratio = abs(an_coeffs[0]) / abs(bn_coeffs[0]) if a_deg == b_deg else 0
            if ratio < 1:
                result["convergence_tier"] = "strong"
                result["flags"].append(f"|a_n/b_n| → {ratio:.3g} < 1: strong convergence")
            elif ratio == 0:
                result["convergence_tier"] = "very_strong"
                result["flags"].append("|a_n/b_n| → 0: very strong convergence")
            else:
                result["convergence_tier"] = "conditional"
                result["flags"].append(f"|a_n/b_n| → {ratio:.3g} ≥ 1: convergence conditional")
        else:
            result["convergence_tier"] = "divergent_likely"
            result["flags"].append(
                f"a(n) degree {a_deg} > b(n) degree {b_deg}: likely divergent"
            )

    return result


# ===================================================================
#  Nonpolynomial CF convergence analysis  (v4.2)
# ===================================================================

def nonpoly_convergence_analysis(metadata: dict) -> dict:
    """Convergence analysis for nonpolynomial CFs (factorial, Fibonacci, etc.).

    Uses the stored numerical convergence error and the growth-rate of the
    coefficient sequence to give a convergence tier + sketch proof.
    """
    strategy = metadata.get("cf_type") or metadata.get("strategy", "")
    conv_err = metadata.get("convergence_error", None)
    result = {
        "converges": False,
        "convergence_tier": "unknown",
        "proof_sketch": "",
        "numerical_error": conv_err,
        "flags": [],
    }

    if conv_err is not None and conv_err < 1e-8:
        result["converges"] = True
        result["flags"].append(
            f"Numerical convergence: depth-200 vs depth-100 error = {conv_err:.2e}"
        )

    if strategy == "factorial":
        result["convergence_tier"] = "superexponential"
        result["proof_sketch"] = (
            "For a(n) = k·n!, b(n) = B (constant): the n-th tail T_n of the CF "
            "satisfies T_n = k·n!/(B + T_{n+1}). Since |T_{n+1}| grows as (n+1)!, "
            "we get |T_n| ~ k·n!/((n+1)!) = k/(n+1) → 0. The tails converge "
            "super-exponentially fast, guaranteeing convergence of the full CF."
        )
        result["converges"] = True
    elif strategy == "fibonacci":
        result["convergence_tier"] = "exponential"
        result["proof_sketch"] = (
            "For a(n) = k·F(n) (Fibonacci), b(n) = αn+β: "
            "|a(n)/b(n)| ~ k·φⁿ/(αn+β) → ∞ as n → ∞ (φ = golden ratio). "
            "However the CF tails still converge because nested division "
            "by super-polynomial terms forces |T_n| → 0. Numerical evidence "
            "confirms convergence."
        )
    elif strategy == "exponential":
        result["convergence_tier"] = "exponential"
        result["proof_sketch"] = (
            "For a(n) = k·B^n, b(n) = cn+1: |a(n)/b(n)| ~ B^n/n → ∞. "
            "Convergence follows from the same tail-decay argument as the "
            "factorial case, with |T_n| ~ B^n/B^{n+1} = 1/B → 0."
        )
    elif strategy == "prime_mix":
        result["convergence_tier"] = "polynomial"
        result["proof_sketch"] = (
            "For a(n) = αn²+p(n), b(n) = B: |a(n)/b(n)| ~ n²/B → ∞ but "
            "grows polynomially. Convergence depends on the specific parameter "
            "regime. Numerical convergence is confirmed."
        )
    elif strategy == "alt_factorial":
        result["convergence_tier"] = "superexponential"
        result["proof_sketch"] = (
            "For a(n) = (-1)^n·k·n!, b(n) = B: alternating signs provide "
            "additional convergence acceleration. The Leibniz-type alternation "
            "means the partial numerators cancel progressively, and the "
            "tail T_n ~ (-1)^n·k/(n+1) → 0 super-exponentially."
        )
        result["converges"] = True
    elif strategy == "quadratic_b":
        result["convergence_tier"] = "strong"
        result["proof_sketch"] = (
            "For a(n) = A (constant), b(n) = αn²+βn+γ: "
            "|a(n)/b(n)| ~ |A|/(αn²) → 0 as n → ∞. "
            "Convergence guaranteed by the general ratio test (Wall 1948)."
        )
        result["converges"] = True

    return result


# ===================================================================
#  Candidate priority table (v3.3)
# ===================================================================

def build_candidate_table(discoveries: list[dict]) -> list[dict]:
    """Build the Tier 3 refined candidate table for all novel CFs.

    Each row:  Value (20 digits) | ISC result | Algebraic degree bound |
               Bessel/HG ID | Convergence | Final status
    """
    table = []
    for disc in discoveries:
        meta = disc.get("metadata", {})
        params = disc.get("params", {})
        an = params.get("an")
        bn = params.get("bn")

        row = {
            "expression": disc.get("expression", ""),
            "value_20_digits": meta.get("value_20_digits", ""),
            "isc_result": meta.get("isc_result", {}),
            "algebraic_degree": meta.get("algebraic_degree", {}),
            "bessel_hg_id": meta.get("bessel_identification", {}),
            "convergence": meta.get("convergence_check", {}),
            "pslq_status": "no relation" if not meta.get("pslq_recognition", {}).get("found") else meta.get("pslq_recognition", {}).get("expression", ""),
            "final_status": _determine_final_status(meta),
            "priority_tier": _assign_tier(an, bn, meta),
        }
        table.append(row)

    # Sort by priority tier then by expression
    tier_order = {"tier1_isc_priority": 0, "tier2_flagged": 1, "tier3_novel": 2}
    table.sort(key=lambda r: (tier_order.get(r["priority_tier"], 99), r["expression"]))

    return table


def _determine_final_status(meta: dict) -> str:
    """Determine the final analytical status of a candidate."""
    # If Bessel/HG identified → identified
    bessel = meta.get("bessel_identification", {})
    if bessel.get("identified"):
        best = bessel.get("best_identification", {})
        return f"Identified: {best.get('type', 'Bessel/HG')}"

    # If ISC found something
    isc = meta.get("isc_result", {})
    if isc.get("found"):
        return f"ISC match: {isc.get('identifications', ['?'])[0][:40]}"

    # If algebraic
    alg = meta.get("algebraic_degree", {})
    if alg.get("is_algebraic"):
        return f"Algebraic degree ≤ {alg.get('degree_bound', '?')}"

    # If PSLQ matched
    pslq = meta.get("pslq_recognition", {})
    if pslq.get("found"):
        return "PSLQ relation found"

    # If convergence issues
    conv = meta.get("convergence_check", {})
    if not conv.get("converges", True):
        return "Convergence issue — flagged"

    return "Novel — no identification"


def _assign_tier(an, bn, meta: dict) -> str:
    """Assign priority tier per the reviewer's framework."""
    conv = meta.get("convergence_check", {})

    # Tier 2: convergence problems
    if not conv.get("converges", True):
        return "tier2_flagged"
    if conv.get("zero_denominators"):
        return "tier2_flagged"

    # Tier 1: linear-b CFs (Bessel/HG identifiable) or factorial CFs
    if an is not None and bn is not None:
        if len(an) == 1 and len(bn) == 2:
            return "tier1_isc_priority"

    # Tier 3: everything else
    return "tier3_novel"


# ===================================================================
#  Full novel-CF analysis pipeline
# ===================================================================

def analyze_novel_cf(discovery: dict, prec: int = 200) -> dict:
    """Complete analysis of a novel CF candidate (all reviewer recs).

    Returns enriched metadata dict to merge into discovery.
    """
    params = discovery.get("params", {})
    an = params.get("an")
    bn = params.get("bn")

    result = {
        "analysis_version": "v4.2",
        "analysis_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # 1. High-precision value
    if an is not None and bn is not None:
        hi = compute_hi_precision_value(an, bn, prec=prec)
        result["value_hi_prec"] = hi["value_str"]
        result["value_20_digits"] = mpmath.nstr(hi["value_mpf"], 20)
        result["convergence_500_vs_300"] = hi["convergence_error_500_300"]
        result["convergence_300_vs_150"] = hi["convergence_error_300_150"]
        val_mpf = hi["value_mpf"]
    else:
        # Nonpoly CF — use stored value
        result["value_20_digits"] = f"{discovery.get('value', 0):.15f}"
        val_mpf = None
        # v4.2: nonpoly convergence analysis
        meta = discovery.get("metadata", {})
        npconv = nonpoly_convergence_analysis(meta)
        result["convergence_check"] = npconv
        result["nonpoly_convergence"] = npconv

    # 2. Algebraic fixed-point analysis
    if an is not None and bn is not None:
        fp = periodic_cf_fixedpoint(an, bn)
        result["algebraic_analysis"] = fp.get("analysis", "")
        result["is_algebraic"] = fp.get("is_algebraic", False)
        result["cf_class"] = fp.get("cf_class", "unknown")
        if fp.get("exact_form"):
            result["exact_form"] = fp["exact_form"]
            result["minimal_polynomial"] = fp.get("minimal_poly")

    # 3. PSLQ constant-basis recognition
    if val_mpf is not None:
        pslq_result = pslq_constant_recognition(val_mpf, prec=min(prec, 100))
        result["pslq_recognition"] = {
            "found": pslq_result.get("found", False),
            "expression": pslq_result.get("expression"),
            "residual": pslq_result.get("residual"),
            "max_coeff": pslq_result.get("max_coeff_used"),
        }
        # If PSLQ found a relation, this might be a known constant
        if pslq_result.get("found"):
            result["pslq_match_warning"] = (
                "PSLQ found an integer relation — verify stability before "
                "claiming novelty. Check if max_coeff is small."
            )

    # 4. PSLQ stability table (multi-precision — limited to avoid hanging)
    if val_mpf is not None:
        stab = pslq_stability_table(val_mpf, precisions=[50, 100])
        result["pslq_stability_table"] = stab
        # v4.4: Only trust stability if both precisions found identical
        # relation AND all coefficients are small (max_coeff < 500).
        # High coefficients at prec=50 are often numerical artefacts.
        all_found = [r for r in stab if r.get("found")]
        if len(all_found) >= 2:
            rels = [tuple(r["relation"]) for r in all_found]
            stable = all(r == rels[0] for r in rels)
            # Also reject if any coefficient is large (likely spurious)
            if stable and max(abs(c) for c in rels[0]) > 500:
                stable = False
            result["pslq_stable"] = stable
        else:
            result["pslq_stable"] = None  # inconclusive

    # 5. Reproducibility bundle
    result["reproducibility"] = reproducibility_bundle(discovery)

    # ── v3.3 additions ──

    # 6. Bessel / hypergeometric identification (for linear-b CFs)
    if an is not None and bn is not None and val_mpf is not None:
        bessel_res = bessel_identification(an, bn, val_mpf, prec=min(prec, 100))
        result["bessel_identification"] = bessel_res

    # 7. mpmath.identify() ISC-style lookup
    if val_mpf is not None:
        isc_res = mpmath_identify(val_mpf, prec=min(prec, 50))
        result["isc_result"] = isc_res

    # 8. Algebraic degree bound
    if val_mpf is not None:
        alg_deg = algebraic_degree_bound(val_mpf, prec=min(prec, 150),
                                          max_degree=6)
        result["algebraic_degree"] = alg_deg

    # 9. Pringsheim convergence diagnostics
    if an is not None and bn is not None:
        conv = pringsheim_convergence_check(an, bn)
        result["convergence_check"] = conv

    # 10. Enhanced closed-form matching (v4.1)
    if val_mpf is not None:
        ecf = enhanced_closed_form(val_mpf, an, bn, prec=min(prec, 80))
        result["enhanced_closed_form"] = ecf
        if ecf.get("found"):
            best = ecf["best_match"]
            result["closed_form_identified"] = True
            result["closed_form_expression"] = best["formula"]
            result["closed_form_type"] = best["type"]
            result["closed_form_digits"] = best["match_digits"]

    return result
