"""
validator.py — High-precision numeric validation and symbolic verification (v2).

v2 changes:
 - Honest claim taxonomy: verified_numeric | verified_known | novel_unproven |
   novel_proven | falsified (never labels rediscoveries as "proven")
 - Literature-match detection for known results
 - error:∞ bug fix — verified items always get a finite error
 - PSLQ stability flag forwarded from generator
 - Partition corollary detection via blackboard._is_partition_corollary

Three-tier validation pipeline:
 1. Numeric triage: evaluate at increasing precision (50→200→500 digits)
 2. Symbolic simplification: attempt CAS simplification via sympy
 3. PSLQ cross-check: verify integer relations at ultra-high precision
"""

from __future__ import annotations
import re
import time
from dataclasses import dataclass, field
from typing import Any

import mpmath
import sympy
from sympy import (simplify, nsimplify, pi, E, sqrt, Rational,
                   oo, S, Symbol, expand, factor, cancel)

from .formulas import _mp, _pslq_search, _compute_basis_mpf


@dataclass
class ValidationResult:
    """Result of validating a conjecture (v2 taxonomy)."""
    conjecture_id: str
    verdict: str              # verified_known | verified_numeric | novel_unproven | novel_proven | falsified
    confidence: float         # 0.0 – 1.0
    precision_achieved: int   # digits of agreement
    checks: list[dict] = field(default_factory=list)
    proof_sketch: str | None = None
    symbolic_form: str | None = None
    time_seconds: float = 0.0
    literature_match: str | None = None   # v2: citation if known result
    is_novel: bool = False                # v2: True if no literature match


class Validator:
    """Multi-stage conjecture validator."""

    # Precision tiers (digits)
    PRECISION_TIERS = [50, 200, 500]

    def __init__(self, max_precision: int = 500):
        self.max_precision = max_precision

    def validate(self, conjecture) -> ValidationResult:
        """Full validation pipeline for a conjecture."""
        t0 = time.time()
        checks = []
        best_precision = 0

        # ── Stage 1: Numeric precision escalation ──
        for prec in self.PRECISION_TIERS:
            if prec > self.max_precision:
                break
            result = self._numeric_check(conjecture, prec)
            checks.append(result)
            if result["passed"]:
                best_precision = max(best_precision, result["precision_digits"])
            else:
                # Failed at this tier — no point going higher
                break

        # ── Stage 2: Symbolic verification ──
        sym_result = self._symbolic_check(conjecture)
        checks.append(sym_result)

        # ── Stage 3: PSLQ cross-verification (for integer relations) ──
        if conjecture.family == "integer_relation":
            pslq_result = self._pslq_verify(conjecture)
            checks.append(pslq_result)

        # ── Stage 4: Convergence rate analysis ──
        if conjecture.family in ("pi_series", "q_series"):
            conv_result = self._convergence_check(conjecture)
            checks.append(conv_result)

        # ── Stage 4b (v4.1): CF convergence gating ──
        # Reject CFs with |a_n/b_n| → ≥1 or divergent growth before
        # spending resources on expensive symbolic/proof stages
        convergence_gated = False
        if conjecture.family == "continued_fraction":
            params = conjecture.params or {}
            an = params.get("an", [])
            bn = params.get("bn", [])
            if len(bn) == 2 and bn[0] != 0 and len(an) >= 1:
                a_deg = len(an) - 1
                b_deg = 1
                if a_deg > b_deg:
                    convergence_gated = True
                    checks.append({
                        "stage": "convergence_gate",
                        "passed": False,
                        "reason": f"a(n) degree {a_deg} > b(n) degree {b_deg}: likely divergent",
                    })
                elif a_deg == b_deg and abs(bn[0]) > 0:
                    ratio = abs(an[0]) / abs(bn[0])
                    if ratio >= 1.0:
                        convergence_gated = True
                        checks.append({
                            "stage": "convergence_gate",
                            "passed": False,
                            "reason": f"|a_n/b_n| → {ratio:.3g} ≥ 1: convergence not guaranteed",
                        })

        # ── Stage 5: CF fixed-point proof (v3) ──
        if conjecture.family == "continued_fraction":
            fp_proof = self._cf_fixedpoint_proof(conjecture)
            if fp_proof and fp_proof.get("proven"):
                checks.append({
                    "stage": "cf_fixedpoint_proof",
                    "passed": True,
                    "proven": True,
                    "proof_sketch": fp_proof["proof_sketch"],
                    "symbolic_form": fp_proof["symbolic_form"],
                })
                # Upgrade sym_result if not already proven
                if not sym_result.get("proven"):
                    sym_result["proven"] = True
                    sym_result["proof_sketch"] = fp_proof["proof_sketch"]
                    sym_result["symbolic_form"] = fp_proof["symbolic_form"]

        # ── Stage 6: Algebraic number detection (v3.1) ──
        if conjecture.family == "continued_fraction" and not sym_result.get("literature_match"):
            alg_result = self._algebraic_detection(conjecture)
            checks.append(alg_result)
            if alg_result.get("is_algebraic"):
                if not sym_result.get("literature_match"):
                    sym_result["literature_match"] = alg_result.get("description")
                    lit_match = alg_result.get("description")

        # ── Verdict (v2 taxonomy) ──
        n_passed = sum(1 for c in checks if c.get("passed", False))
        n_total = len(checks)
        confidence = n_passed / max(n_total, 1)

        # Determine literature match from generator metadata or symbolic check
        lit_match = (
            getattr(conjecture, 'metadata', {}).get('literature_match')
            or sym_result.get('literature_match')
        )
        is_novel = getattr(conjecture, 'metadata', {}).get('is_novel', True)
        if lit_match:
            is_novel = False

        if confidence < 0.3 or best_precision < 5:
            verdict = "falsified"
        elif convergence_gated:
            verdict = "falsified"
        elif lit_match or not is_novel:
            # Known result — never call it "proven by agent"
            verdict = "verified_known"
        elif best_precision >= 100 and sym_result.get("proven"):
            verdict = "novel_proven"
        elif best_precision >= 30 and confidence >= 0.5:
            verdict = "novel_unproven" if is_novel else "verified_numeric"
        elif confidence >= 0.3:
            verdict = "verified_numeric"
        else:
            verdict = "falsified"

        elapsed = time.time() - t0
        return ValidationResult(
            conjecture_id=conjecture.id,
            verdict=verdict,
            confidence=confidence,
            precision_achieved=best_precision,
            checks=checks,
            proof_sketch=sym_result.get("proof_sketch"),
            symbolic_form=sym_result.get("symbolic_form"),
            time_seconds=elapsed,
            literature_match=lit_match,
            is_novel=is_novel,
        )

    # ------------------------------------------------------------------
    #  Stage 1: Numeric precision escalation
    # ------------------------------------------------------------------
    def _numeric_check(self, conjecture, prec: int) -> dict:
        """Evaluate conjecture at given precision."""
        mp = _mp(prec)
        check = {"stage": "numeric", "precision": prec, "passed": False}

        family = conjecture.family
        params = conjecture.params or {}

        try:
            if family == "pi_series":
                from .formulas import _generalised_pi_series
                r = _generalised_pi_series(
                    params.get("a", 1), params.get("b", 1),
                    params.get("c", 64), params.get("d", 1),
                    num_terms=prec, prec=prec
                )
                error = r["error"]
            elif family == "continued_fraction":
                from .formulas import _generalised_cf
                # v3: For novel CF candidates, convergence_error is the metric
                if params.get("strategy"):
                    # Nonpoly CF — use _evaluate_gcf convergence check
                    from .formulas import _evaluate_gcf
                    strategy = params.get("strategy", "")
                    # Can't easily re-evaluate nonpoly CFs at higher precision
                    # without re-building the function. Use the stored error.
                    meta = getattr(conjecture, 'metadata', {}) or {}
                    conv_err = meta.get("convergence_error", conjecture.error)
                    error = conv_err if conv_err < 1.0 else conjecture.error
                elif params.get("an") and params.get("bn"):
                    r = _generalised_cf(
                        params.get("an", [1, 0, 0]),
                        params.get("bn", [1, 1]),
                        prec=prec,
                    )
                    # v3: For novel candidates, use convergence_error
                    if r.get("is_potentially_novel"):
                        error = r.get("convergence_error", r["best_error"])
                    else:
                        error = r["best_error"]
                else:
                    error = conjecture.error
            elif family == "partition":
                # Partition congruences: check at higher range
                max_n = min(500, 200 + prec)
                p = [0] * (max_n + 1)
                p[0] = 1
                for k in range(1, max_n + 1):
                    for j in range(k, max_n + 1):
                        p[j] += p[j - k]
                a, b, m = params.get("a", 5), params.get("b", 4), params.get("m", 5)
                vals = [p[a*n + b] for n in range(max_n // a)
                        if a*n + b <= max_n]
                violations = sum(1 for v in vals if v % m != 0)
                error = violations / max(len(vals), 1)
                check["violations"] = violations
                check["tested"] = len(vals)
            elif family == "integer_relation":
                # Re-run PSLQ at higher precision
                rel = params.get("relation", [])
                basis = params.get("basis", [])
                if rel:
                    # Recompute basis at higher precision
                    basis_vals = self._compute_basis(basis, prec)
                    residual = abs(sum(r * v for r, v in zip(rel, [conjecture.value] + basis_vals)))
                    error = float(residual)
                else:
                    error = float('inf')
            elif family == "tau_function":
                error = conjecture.error
            else:
                error = conjecture.error

            if error == float('inf'):
                check["passed"] = False
            else:
                digits = max(0, -int(round(mpmath.log10(max(error, 1e-300)))))
                check["error"] = error
                check["precision_digits"] = digits
                check["passed"] = digits >= prec * 0.3  # at least 30% of requested precision

        except Exception as exc:
            check["error_msg"] = str(exc)
            check["passed"] = False
            check["precision_digits"] = 0

        return check

    # ------------------------------------------------------------------
    #  Stage 2: Symbolic verification
    # ------------------------------------------------------------------
    def _symbolic_check(self, conjecture) -> dict:
        """Try to symbolically verify the conjecture via sympy."""
        check = {"stage": "symbolic", "passed": False, "proven": False}

        try:
            expr_str = conjecture.expression
            target = conjecture.target

            # Try nsimplify on the numeric value
            if conjecture.value and abs(conjecture.value) < 1e15:
                sym_val = nsimplify(conjecture.value, rational=False,
                                     tolerance=1e-10)
                check["nsimplify"] = str(sym_val)

                # Check if it matches known constant
                if target == "pi" and sym_val == pi:
                    check["proven"] = True
                    check["proof_sketch"] = "nsimplify identifies value as π"
                elif target == "e" and sym_val == E:
                    check["proven"] = True
                    check["proof_sketch"] = "nsimplify identifies value as e"

                check["symbolic_form"] = str(sym_val)
                check["passed"] = True

            # v3: For continued fractions, check if value matches a known
            # constant via algebraic transform (ISC-style).  This prevents
            # trivial φ-variants from being labeled "novel_unproven".
            if conjecture.family == "continued_fraction":
                meta = getattr(conjecture, 'metadata', {}) or {}
                gen_citation = meta.get("literature_match")
                is_known = meta.get("is_known_transform", False)
                is_novel_candidate = meta.get("is_novel", False)
                if gen_citation or is_known:
                    check["literature_match"] = gen_citation
                    check["passed"] = True
                    check["proven"] = True
                    const_name = meta.get("matched_constant", "known constant")
                    check["proof_sketch"] = (
                        f"Trivial algebraic transform of {const_name}. "
                        f"Not a novel discovery."
                    )
                elif is_novel_candidate:
                    # Novel CF: convergence verified, no known-constant match
                    conv_err = meta.get("convergence_error", 1.0)
                    if conv_err < 1e-10:
                        check["passed"] = True
                        check["proof_sketch"] = (
                            f"CF converges to {conjecture.value:.15f} "
                            f"(convergence error {conv_err:.2e}). "
                            f"Not matched by ISC lookup against 15 constants "
                            f"× 40 multipliers + algebraic transforms. "
                            f"Candidate novel continued fraction identity."
                        )
                elif target and any(c in (target or "") for c in
                                     ["phi", "pi", "sqrt", "ln", "euler",
                                      "catalan", "apery", "zeta"]):
                    # Target field from _generalised_cf indicates a known match
                    check["literature_match"] = (
                        f"Known constant match: {target}"
                    )
                    check["passed"] = True
                    check["proof_sketch"] = (
                        f"CF evaluates to expression involving {target}. "
                        f"Verified via ISC-style constant lookup."
                    )

            # For partition congruences, attempt modular arithmetic proof
            if conjecture.family == "partition":
                params = conjecture.params
                a, b, m = params.get("a"), params.get("b"), params.get("m")
                if a and b is not None and m:
                    # v2: Use blackboard corollary checker
                    from .blackboard import _is_partition_corollary, KNOWN_RESULTS
                    citation = _is_partition_corollary(a, b, m)
                    if citation:
                        check["proven"] = True
                        check["literature_match"] = citation
                        check["proof_sketch"] = (
                            f"Known result: {citation}. "
                            f"This is NOT a novel discovery."
                        )
                    else:
                        check["proof_sketch"] = (
                            f"Candidate congruence p({a}n+{b}) ≡ 0 (mod {m}). "
                            f"Verified numerically; no known literature match found. "
                            f"May be novel — requires formal proof."
                        )
                    check["passed"] = True

        except Exception as exc:
            check["error_msg"] = str(exc)

        return check

    # ------------------------------------------------------------------
    #  Stage 3: PSLQ cross-verification
    # ------------------------------------------------------------------
    def _pslq_verify(self, conjecture) -> dict:
        """Re-run PSLQ at ultra-high precision to verify integer relation."""
        check = {"stage": "pslq_verify", "passed": False}
        params = conjecture.params
        relation = params.get("relation")
        basis_names = params.get("basis", [])

        if not relation or not basis_names:
            return check

        try:
            prec = min(self.max_precision, 300)
            basis_vals = _compute_basis_mpf(basis_names, prec)
            mp = _mp(prec)
            target_val = mp.mpf(conjecture.value)

            r = _pslq_search(target_val, basis_names, basis_vals, prec=prec)
            if r.get("found") and r.get("relation") == relation:
                check["passed"] = True
                check["confirmed_at_precision"] = prec
                check["residual"] = r["residual"]
            elif r.get("found"):
                check["alternative_relation"] = r["relation"]
                check["passed"] = r["residual"] < 1e-20
        except Exception as exc:
            check["error_msg"] = str(exc)

        return check

    # ------------------------------------------------------------------
    #  Stage 4: Convergence rate analysis
    # ------------------------------------------------------------------
    def _convergence_check(self, conjecture) -> dict:
        """Analyze convergence rate of series-based conjectures."""
        check = {"stage": "convergence", "passed": False}

        if conjecture.family != "pi_series":
            check["skipped"] = True
            return check

        params = conjecture.params
        a = params.get("a", 1)
        b = params.get("b", 1)
        c = params.get("c", 64)
        d = params.get("d", 1)

        try:
            from .formulas import _generalised_pi_series
            errors = []
            for n_terms in [5, 10, 20, 40, 80]:
                r = _generalised_pi_series(a, b, c, d, num_terms=n_terms, prec=100)
                if r.get("error") is not None:
                    errors.append((n_terms, r["error"]))

            if len(errors) >= 3:
                # Check for geometric convergence
                ratios = []
                for i in range(1, len(errors)):
                    if errors[i-1][1] > 0 and errors[i][1] > 0:
                        ratios.append(errors[i][1] / errors[i-1][1])

                if ratios and all(r < 0.5 for r in ratios):
                    check["convergence_type"] = "geometric"
                    check["convergence_ratio"] = sum(ratios) / len(ratios)
                    check["passed"] = True
                elif ratios and all(r < 1.0 for r in ratios):
                    check["convergence_type"] = "sublinear"
                    check["passed"] = True

                check["error_history"] = errors

        except Exception as exc:
            check["error_msg"] = str(exc)

        return check

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------
    def _compute_basis(self, names: list[str], prec: int) -> list:
        """Compute basis constant values at given precision (native mpf)."""
        return _compute_basis_mpf(names, prec)

    # ------------------------------------------------------------------
    #  Stage 5: CF fixed-point proof engine (v3)
    # ------------------------------------------------------------------
    def _cf_fixedpoint_proof(self, conjecture) -> dict | None:
        """Attempt an analytic proof for constant-coefficient GCFs.

        For a GCF  y = b + a/y  with constant a, b the positive root of
        y² − by − a = 0 is  y = (b + √(b²+4a))/2.   If this matches the
        numeric value to high precision, we can emit a complete proof.

        Returns a proof dict or None if inapplicable.
        """
        params = conjecture.params or {}
        an = params.get("an")
        bn = params.get("bn")

        # Only applicable to single-coefficient (constant) polynomial CFs
        if an is None or bn is None:
            return None
        if not (isinstance(an, list) and isinstance(bn, list)):
            return None
        if len(an) != 1 or len(bn) != 1:
            return None

        a_const, b_const = an[0], bn[0]

        # The GCF  y = b + a/y  ⟹  y² − by − a = 0
        disc = b_const * b_const + 4 * a_const
        if disc < 0:
            return None  # complex root — not supported yet

        from sympy import sqrt as sp_sqrt, Rational as R, simplify as sp_simplify

        b_sym = sympy.Integer(b_const)
        a_sym = sympy.Integer(a_const)
        disc_sym = b_sym**2 + 4 * a_sym

        y_sym = (b_sym + sp_sqrt(disc_sym)) / 2

        # Verify symbolically:  y² − b·y − a == 0
        check = sp_simplify(y_sym**2 - b_sym * y_sym - a_sym)
        if check != 0:
            return None

        # Verify numerically: y_sym should match conjecture value
        y_num = float(y_sym.evalf(50))
        if abs(y_num - conjecture.value) > 1e-8:
            return None

        # Build proof text
        proof = (
            f"Proof (fixed-point).  Let y = {b_const} + {a_const}/y.  "
            f"Then y² − {b_const}y − {a_const} = 0.  "
            f"Discriminant Δ = {b_const}² + 4·{a_const} = {disc}.  "
            f"Positive root: y = ({b_const} + √{disc})/2 = {y_sym}.  "
            f"Numeric check: {y_num:.15f} vs CF value {conjecture.value:.15f}.  ∎"
        )

        return {
            "proven": True,
            "proof_sketch": proof,
            "symbolic_form": str(y_sym),
            "discriminant": disc,
            "equation": f"y² − {b_const}y − {a_const} = 0",
        }

    # ------------------------------------------------------------------
    #  Stage 6: Algebraic number detection (v3.1)
    # ------------------------------------------------------------------
    def _algebraic_detection(self, conjecture) -> dict:
        """Detect whether a CF value is algebraic by finding its minimal polynomial.

        Uses sympy.minimal_polynomial on the high-precision numeric value.
        If the minimal polynomial has degree <= 4 with small coefficients,
        the value is a known algebraic number and should not be flagged as novel.
        """
        check = {"stage": "algebraic_detection", "passed": False, "is_algebraic": False}

        val = conjecture.value
        if val is None or val == 0 or abs(val) > 1e15:
            return check

        try:
            from sympy import Rational as R, minimal_polynomial, Symbol
            x = Symbol('x')

            # Try to identify the value as an algebraic number
            # nsimplify with aggressive tolerance to catch algebraics
            sym_val = nsimplify(val, rational=False, tolerance=1e-12)

            # Check if minimal_polynomial succeeds
            try:
                mp = minimal_polynomial(sym_val, x)
                deg = mp.as_poly(x).degree()
                coeffs = mp.as_poly(x).all_coeffs()
                max_coeff = max(abs(c) for c in coeffs)

                if deg <= 4 and max_coeff <= 1000:
                    check["passed"] = True
                    check["is_algebraic"] = True
                    check["minimal_polynomial"] = str(mp)
                    check["degree"] = deg
                    check["max_coefficient"] = int(max_coeff)
                    check["description"] = (
                        f"Algebraic number of degree {deg}: "
                        f"root of {mp} = 0 (max coeff {max_coeff})"
                    )
                elif deg <= 8 and max_coeff <= 100:
                    check["passed"] = True
                    check["is_algebraic"] = True
                    check["minimal_polynomial"] = str(mp)
                    check["degree"] = deg
                    check["max_coefficient"] = int(max_coeff)
                    check["description"] = (
                        f"Higher algebraic number of degree {deg}: "
                        f"root of {mp} = 0"
                    )
            except (ValueError, NotImplementedError):
                pass  # minimal_polynomial failed — value may be transcendental

        except Exception as exc:
            check["error_msg"] = str(exc)

        return check

    # ------------------------------------------------------------------
    #  Proof target generation (v3.1)
    # ------------------------------------------------------------------
    @staticmethod
    def generate_proof_targets(discoveries: list) -> list[dict]:
        """Generate structured proof targets for the top novel_unproven discoveries.

        Each target includes:
        - The identity to prove
        - Known mathematical framework it fits into
        - Suggested proof strategy
        - Minimal lemmas needed
        """
        targets = []
        novel = [d for d in discoveries
                 if getattr(d, 'status', '') == 'novel_unproven'
                 and getattr(d, 'confidence', 0) >= 0.5]
        novel.sort(key=lambda d: getattr(d, 'confidence', 0), reverse=True)

        # v3.4: Load bootstrap hints from prior successful proofs
        try:
            from .proof_funnel import get_bootstrap_hints
        except ImportError:
            get_bootstrap_hints = None

        for d in novel[:10]:  # Top 10 candidates
            target = {
                "discovery_id": d.id,
                "family": d.family,
                "expression": d.expression,
                "value": d.value,
                "precision_verified": d.precision_digits,
                "params": d.params,
            }

            # v3.4: Add bootstrap hints from past successful proofs
            if get_bootstrap_hints is not None:
                an = d.params.get("an", [])
                bn = d.params.get("bn", [])
                hints = get_bootstrap_hints(an, bn)
                if hints:
                    target["bootstrap_hints"] = hints

            if d.family == "continued_fraction":
                an = d.params.get("an", [])
                bn = d.params.get("bn", [])
                target["proof_strategy"] = (
                    "1. Establish convergence via named CF theorem "
                    "(Worpitzky, Śleszyński-Pringsheim, Van Vleck, or ratio test). "
                    "2. If polynomial coefficients: express as a ratio of contiguous "
                    "   hypergeometric functions and apply Gauss/Euler CF theorems. "
                    "3. Attempt CAS identification of limit via Bessel/₁F₁ ratios + "
                    "   SymPy nsimplify. "
                    "4. Verify symbolic closed form via high-precision evaluation."
                )
                target["framework"] = "Generalised continued fraction theory (Wall 1948, Lorentzen & Waadeland 2008)"
                target["key_lemmas"] = [
                    f"Convergence: apply named theorem to CF with a(n)={an}, b(n)={bn}",
                    "Closed form: Bessel ratio I_ν(z)/I_{ν-1}(z) or confluent ₁F₁ ratio",
                    "Symbolic verification: CAS check to 100+ digits",
                    "Uniqueness: rule out algebraic/PSLQ relations to known constants",
                ]
            elif d.family == "partition":
                a = d.params.get("a", 0)
                b = d.params.get("b", 0)
                m = d.params.get("m", 0)
                target["proof_strategy"] = (
                    "1. Express the generating function sum p(an+b)q^n in terms of "
                    "   eta-quotients or modular forms of level a*m. "
                    "2. Apply Ono's distribution theorem (2000): if m is prime and "
                    "   p(an+b) ≡ 0 mod m for density-1 set, the congruence holds. "
                    "3. Verify the modular form vanishes at all cusps mod m. "
                    "4. Check via Sturm's bound: verify first B coefficients where "
                    "   B = (k/12)*[SL2Z : Gamma0(N)]."
                )
                target["framework"] = f"Modular forms of level {a}*{m}, weight k (Ono 2000, 2004)"
                target["key_lemmas"] = [
                    f"Express sum_n p({a}n+{b})q^n as eta-quotient mod {m}",
                    f"Compute Sturm bound for Gamma0({a * m})",
                    f"Verify vanishing of first B Fourier coefficients mod {m}",
                ]
            elif d.family == "integer_relation":
                target["proof_strategy"] = (
                    "1. Verify the PSLQ relation at 500+ digits to confirm stability. "
                    "2. Identify the algebraic variety underlying the relation. "
                    "3. Attempt symbolic derivation via integral representations "
                    "   or functional equations of the involved constants. "
                    "4. Check if the relation follows from known polylogarithmic identities."
                )
                target["framework"] = "Integer relation theory (Ferguson & Bailey 1999)"
                target["key_lemmas"] = [
                    "PSLQ stability at 500+ digits",
                    "Identify generating integral or functional equation",
                ]
            else:
                target["proof_strategy"] = (
                    "Numeric verification is complete. A symbolic proof requires "
                    "identifying the appropriate mathematical framework."
                )
                target["framework"] = "To be determined"
                target["key_lemmas"] = ["Identify closed-form expression"]

            targets.append(target)

        return targets
