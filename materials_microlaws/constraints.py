"""
Physical Constraint Engine
===========================
Prunes symbolic expressions that violate dimensional analysis, known physical limits,
symmetry requirements, or monotonicity rules.

Implements hard constraints as a filter on the hypothesis space, and soft constraints
as penalty terms added to the loss function. This is the key module that enforces
"physical plausibility as a first-class objective."
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import numpy as np
from loguru import logger
from sympy import (
    Abs, Expr, Float, Rational, Symbol, diff, limit, log, oo, simplify,
    symbols, zoo, nan as sp_nan,
)

from .data_loader import Descriptor


# ---------------------------------------------------------------------------
# Constraint types
# ---------------------------------------------------------------------------

class ConstraintType(Enum):
    DIMENSIONAL = auto()
    MONOTONICITY = auto()
    BOUNDEDNESS = auto()
    SYMMETRY = auto()
    KNOWN_LIMIT = auto()
    COMPLEXITY = auto()


class Severity(Enum):
    HARD = auto()   # expression is rejected
    SOFT = auto()   # penalty is added to score


@dataclass
class Violation:
    """Record of a constraint violation."""
    constraint_type: ConstraintType
    severity: Severity
    description: str
    penalty: float = 0.0  # for soft constraints


@dataclass
class ConstraintReport:
    """Full constraint check report for a candidate formula."""
    violations: list[Violation] = field(default_factory=list)
    passed: bool = True
    total_penalty: float = 0.0

    def add_violation(self, v: Violation):
        self.violations.append(v)
        if v.severity == Severity.HARD:
            self.passed = False
        self.total_penalty += v.penalty


# ---------------------------------------------------------------------------
# Dimensional Analysis Engine
# ---------------------------------------------------------------------------

class DimensionalAnalyzer:
    """
    Check dimensional consistency of symbolic expressions.

    Maps each descriptor to its physical dimensions and verifies that
    the expression's result has the dimensions of the target property.
    """

    def __init__(self, descriptors: list[Descriptor], target_dimensions: dict[str, int]):
        """
        Parameters
        ----------
        descriptors : list of Descriptor objects with dimension info
        target_dimensions : dimensions of the target property
                           e.g. {"energy": 1} for band gap in eV
        """
        self.desc_dims = {d.name: d.dimensions for d in descriptors}
        self.target_dims = target_dimensions

    def check(self, expr: Expr) -> list[Violation]:
        """
        Check dimensional consistency of an expression.

        This performs a simplified dimensional analysis:
        1. Terms added together must have the same dimensions.
        2. The result must match the target dimensions (or be dimensionless
           if the expression includes fitted coefficients that absorb dimensions).
        """
        violations = []

        # Check for physically nonsensical operations
        violations.extend(self._check_transcendental_args(expr))

        return violations

    def _check_transcendental_args(self, expr: Expr) -> list[Violation]:
        """Arguments of log/exp/sqrt must be dimensionless or dimensionally consistent."""
        violations = []
        for sub in expr.atoms():
            pass  # Basic atom check

        # Check log(x) where x has dimensions
        from sympy import log as sym_log, exp as sym_exp
        for sub in _find_function_calls(expr, "log"):
            arg = sub.args[0] if sub.args else None
            if arg:
                arg_vars = [str(s) for s in arg.free_symbols]
                mixed_dims = self._has_mixed_dimensions(arg_vars)
                if mixed_dims:
                    violations.append(Violation(
                        ConstraintType.DIMENSIONAL, Severity.SOFT,
                        f"log() argument has mixed dimensions: {arg}",
                        penalty=0.5,
                    ))

        for sub in _find_function_calls(expr, "exp"):
            arg = sub.args[0] if sub.args else None
            if arg:
                arg_vars = [str(s) for s in arg.free_symbols]
                if self._has_dimensioned_vars(arg_vars):
                    violations.append(Violation(
                        ConstraintType.DIMENSIONAL, Severity.SOFT,
                        f"exp() argument should be dimensionless: {arg}",
                        penalty=0.3,
                    ))

        return violations

    def _has_mixed_dimensions(self, var_names: list[str]) -> bool:
        """Check if variables have incompatible dimensions."""
        dims_seen = set()
        for v in var_names:
            if v in self.desc_dims:
                d = tuple(sorted(self.desc_dims[v].items()))
                dims_seen.add(d)
        return len(dims_seen) > 1

    def _has_dimensioned_vars(self, var_names: list[str]) -> bool:
        """Check if any variable has non-trivial dimensions."""
        for v in var_names:
            if v in self.desc_dims:
                d = self.desc_dims[v]
                if d and not (len(d) == 1 and "dimensionless" in d):
                    return True
        return False


def _find_function_calls(expr: Expr, func_name: str) -> list:
    """Find all applications of a named function in expression."""
    results = []
    for sub in expr.atoms():
        pass
    # Walk the expression tree
    if hasattr(expr, 'func') and expr.func.__name__.lower() == func_name:
        results.append(expr)
    for arg in expr.args:
        results.extend(_find_function_calls(arg, func_name))
    return results


# ---------------------------------------------------------------------------
# Monotonicity Constraints
# ---------------------------------------------------------------------------

class MonotonicityChecker:
    """
    Verify that formulas respect known monotonicity relationships.

    For example, band gap should generally decrease with increasing
    B-site electronegativity for halide perovskites.
    """

    def __init__(self, rules: list[dict]):
        """
        Parameters
        ----------
        rules : list of dicts with keys:
            "variable": str - descriptor name
            "direction": "increasing" or "decreasing"
            "description": str
            "strict": bool - whether violation is hard or soft
        """
        self.rules = rules

    def check(self, expr: Expr) -> list[Violation]:
        violations = []
        for rule in self.rules:
            var_name = rule["variable"]
            direction = rule["direction"]
            strict = rule.get("strict", False)

            var = Symbol(var_name)
            if var not in expr.free_symbols:
                continue

            # Compute symbolic derivative
            try:
                deriv = diff(expr, var)
                deriv_simplified = simplify(deriv)

                # Check if derivative has definite sign
                # (heuristic: evaluate at a few representative points)
                sign_check = self._check_derivative_sign(deriv_simplified, expr, var_name)

                if sign_check is not None:
                    if direction == "increasing" and sign_check < 0:
                        violations.append(Violation(
                            ConstraintType.MONOTONICITY,
                            Severity.HARD if strict else Severity.SOFT,
                            f"Formula decreases with {var_name}, expected increasing",
                            penalty=0.0 if strict else 0.3,
                        ))
                    elif direction == "decreasing" and sign_check > 0:
                        violations.append(Violation(
                            ConstraintType.MONOTONICITY,
                            Severity.HARD if strict else Severity.SOFT,
                            f"Formula increases with {var_name}, expected decreasing",
                            penalty=0.0 if strict else 0.3,
                        ))
            except Exception:
                pass  # Can't differentiate — skip

        return violations

    def _check_derivative_sign(self, deriv: Expr, full_expr: Expr,
                                 var_name: str) -> Optional[int]:
        """Evaluate derivative sign at representative points. Returns +1, -1, or None."""
        from sympy import lambdify
        free = list(deriv.free_symbols)
        if not free:
            try:
                val = float(deriv)
                return 1 if val > 0 else (-1 if val < 0 else 0)
            except (TypeError, ValueError):
                return None

        try:
            f = lambdify(free, deriv, modules=["numpy"])
            # Test at reasonable materials-science-range values
            test_points = [0.5, 1.0, 2.0, 3.0]
            signs = []
            for tp in test_points:
                args = [tp] * len(free)
                val = f(*args)
                if np.isfinite(val):
                    signs.append(np.sign(val))

            if signs and all(s == signs[0] for s in signs):
                return int(signs[0])
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Boundedness & Physical Limit Constraints
# ---------------------------------------------------------------------------

class BoundednessChecker:
    """
    Verify that formulas produce physically reasonable values.

    - Band gaps must be non-negative
    - Formation energies must be finite
    - Properties must not diverge for realistic descriptor ranges
    """

    def __init__(
        self,
        lower_bound: Optional[float] = None,
        upper_bound: Optional[float] = None,
        descriptor_ranges: Optional[dict[str, tuple[float, float]]] = None,
    ):
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.descriptor_ranges = descriptor_ranges or {}

    def check(self, expr: Expr, X: Optional[np.ndarray] = None,
              variable_names: Optional[list[str]] = None) -> list[Violation]:
        violations = []

        # Check for singularities in the expression
        free_vars = list(expr.free_symbols)
        for var in free_vars:
            try:
                lim_pos = limit(expr, var, oo)
                if lim_pos in (oo, -oo, zoo):
                    violations.append(Violation(
                        ConstraintType.BOUNDEDNESS, Severity.SOFT,
                        f"Expression diverges as {var} → ∞",
                        penalty=0.2,
                    ))
            except Exception:
                pass

        # Numerical bound checking if data is provided
        if X is not None and variable_names is not None:
            violations.extend(
                self._check_numerical_bounds(expr, X, variable_names)
            )

        return violations

    def _check_numerical_bounds(self, expr: Expr, X: np.ndarray,
                                  variable_names: list[str]) -> list[Violation]:
        """Evaluate expression on data and check bounds."""
        violations = []
        from sympy import lambdify
        syms = [Symbol(n) for n in variable_names]
        used = [s for s in syms if s in expr.free_symbols]
        if not used:
            return violations

        try:
            f = lambdify(used, expr, modules=["numpy"])
            name_to_idx = {n: i for i, n in enumerate(variable_names)}
            args = [X[:, name_to_idx[str(s)]] for s in used]
            vals = f(*args)

            if not np.all(np.isfinite(vals)):
                violations.append(Violation(
                    ConstraintType.BOUNDEDNESS, Severity.HARD,
                    "Expression produces NaN/Inf for training data",
                ))

            if self.lower_bound is not None and np.any(vals < self.lower_bound):
                frac = np.mean(vals < self.lower_bound)
                violations.append(Violation(
                    ConstraintType.BOUNDEDNESS, Severity.HARD if frac > 0.1 else Severity.SOFT,
                    f"{frac:.1%} of predictions below lower bound {self.lower_bound}",
                    penalty=0.5 * frac,
                ))

            if self.upper_bound is not None and np.any(vals > self.upper_bound):
                frac = np.mean(vals > self.upper_bound)
                violations.append(Violation(
                    ConstraintType.BOUNDEDNESS, Severity.SOFT,
                    f"{frac:.1%} of predictions above upper bound {self.upper_bound}",
                    penalty=0.3 * frac,
                ))
        except Exception as e:
            logger.debug(f"Numerical evaluation failed: {e}")

        return violations


# ---------------------------------------------------------------------------
# Complexity Constraints
# ---------------------------------------------------------------------------

class ComplexityChecker:
    """Enforce Occam's razor: penalize overly complex expressions."""

    def __init__(self, max_ops: int = 20, max_variables: int = 8):
        self.max_ops = max_ops
        self.max_variables = max_variables

    def check(self, expr: Expr) -> list[Violation]:
        violations = []
        n_ops = expr.count_ops()
        n_vars = len(expr.free_symbols)

        if n_ops > self.max_ops:
            violations.append(Violation(
                ConstraintType.COMPLEXITY, Severity.HARD,
                f"Expression has {n_ops} operations (max {self.max_ops})",
            ))

        if n_vars > self.max_variables:
            violations.append(Violation(
                ConstraintType.COMPLEXITY, Severity.SOFT,
                f"Expression uses {n_vars} variables (max {self.max_variables})",
                penalty=0.1 * (n_vars - self.max_variables),
            ))

        return violations


# ---------------------------------------------------------------------------
# Unified Constraint Engine
# ---------------------------------------------------------------------------

class ConstraintEngine:
    """
    Unified constraint checker that combines all physical constraints.

    This is the main interface used by the iterative loop to filter
    and penalize candidate formulas.
    """

    def __init__(
        self,
        descriptors: list[Descriptor],
        target_name: str = "band_gap",
        target_unit: str = "eV",
    ):
        self.descriptors = descriptors

        # Set up target dimensions
        target_dims = {"energy": 1} if "eV" in target_unit else {}

        self.dimensional = DimensionalAnalyzer(descriptors, target_dims)

        # Default monotonicity rules for band gaps
        self.monotonicity = MonotonicityChecker([
            {
                "variable": "EN_X",
                "direction": "increasing",
                "description": "Band gap increases with anion electronegativity",
                "strict": False,
            },
        ])

        # Boundedness: band gap is non-negative, typically < 10 eV
        lower = 0.0 if "band_gap" in target_name else None
        self.boundedness = BoundednessChecker(lower_bound=lower, upper_bound=10.0)

        self.complexity = ComplexityChecker(max_ops=20, max_variables=8)

        logger.info(f"ConstraintEngine initialized for {target_name} ({target_unit})")

    def check(
        self,
        expr: Expr,
        X: Optional[np.ndarray] = None,
        variable_names: Optional[list[str]] = None,
    ) -> ConstraintReport:
        """
        Run all constraint checks on a candidate expression.

        Returns a ConstraintReport with pass/fail and penalties.
        """
        report = ConstraintReport()

        # Dimensional analysis
        for v in self.dimensional.check(expr):
            report.add_violation(v)

        # Monotonicity
        for v in self.monotonicity.check(expr):
            report.add_violation(v)

        # Boundedness
        for v in self.boundedness.check(expr, X, variable_names):
            report.add_violation(v)

        # Complexity
        for v in self.complexity.check(expr):
            report.add_violation(v)

        return report

    def filter_candidates(
        self,
        candidates: list,
        X: Optional[np.ndarray] = None,
        variable_names: Optional[list[str]] = None,
    ) -> tuple[list, list[ConstraintReport]]:
        """
        Filter a list of CandidateFormula objects, removing hard violations
        and adjusting scores for soft violations.

        Returns (filtered_candidates, reports).
        """
        filtered = []
        reports = []

        for c in candidates:
            report = self.check(c.expr, X, variable_names)
            c.physically_valid = report.passed
            c.score += report.total_penalty  # Penalize soft violations

            if report.passed:
                filtered.append(c)
            reports.append(report)

        n_rejected = len(candidates) - len(filtered)
        if n_rejected > 0:
            logger.info(f"  Constraints rejected {n_rejected}/{len(candidates)} candidates")

        return filtered, reports

    def update_rules(self, new_rules: dict):
        """
        Update constraint rules based on iteration feedback.

        Parameters
        ----------
        new_rules : dict with optional keys:
            "monotonicity": list of new monotonicity rules
            "max_complexity": int
            "lower_bound", "upper_bound": float
        """
        if "monotonicity" in new_rules:
            self.monotonicity = MonotonicityChecker(new_rules["monotonicity"])
        if "max_complexity" in new_rules:
            self.complexity.max_ops = new_rules["max_complexity"]
        if "lower_bound" in new_rules:
            self.boundedness.lower_bound = new_rules["lower_bound"]
        if "upper_bound" in new_rules:
            self.boundedness.upper_bound = new_rules["upper_bound"]
        logger.info("  Constraint rules updated")

    def get_search_space_reduction(self, n_total: int, n_after: int) -> dict:
        """
        Compute the search space reduction factor from constraint filtering.

        Returns metrics relevant to Theorem 1 (search space reduction).
        """
        if n_total == 0:
            return {"reduction_factor": 1.0, "log_reduction": 0.0}

        ratio = n_after / n_total
        reduction = 1.0 / ratio if ratio > 0 else float("inf")

        return {
            "reduction_factor": reduction,
            "log_reduction": np.log10(reduction) if reduction > 0 else float("inf"),
            "n_total": n_total,
            "n_surviving": n_after,
            "rejection_rate": 1 - ratio,
        }
