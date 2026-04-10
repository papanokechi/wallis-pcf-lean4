"""
Symbolic Regression Core
========================
Proposes candidate symbolic formulas over physically meaningful descriptors.

Supports:
  - PySR integration (production-grade GP-based symbolic regression)
  - Built-in lightweight symbolic search (no external dependencies)
  - Template-based symbolic expansion with pruning hooks
"""

from __future__ import annotations

import itertools
import operator
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
from loguru import logger
from sympy import (
    Abs, Expr, Float, Rational, Symbol, exp, latex, log, simplify, sqrt,
    symbols, sympify, oo, zoo, nan as sp_nan, N as sp_N,
)

try:
    from pysr import PySRRegressor
    HAS_PYSR = True
except ImportError:
    HAS_PYSR = False


# ---------------------------------------------------------------------------
# Symbolic expression data structures
# ---------------------------------------------------------------------------

@dataclass
class CandidateFormula:
    """A candidate symbolic micro-law."""
    expr: Expr                       # sympy expression
    score: float = float("inf")      # loss (lower is better)
    complexity: int = 0              # number of operations / terms
    mae: float = float("inf")
    r_squared: float = 0.0
    variables: list[str] = field(default_factory=list)
    physically_valid: bool = True
    iteration_found: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def latex_str(self) -> str:
        return latex(self.expr)

    def __repr__(self):
        return (f"CandidateFormula(expr={self.expr}, "
                f"MAE={self.mae:.4f}, R²={self.r_squared:.4f}, "
                f"complexity={self.complexity}, valid={self.physically_valid})")


# ---------------------------------------------------------------------------
# PySR wrapper
# ---------------------------------------------------------------------------

def run_pysr(
    X: np.ndarray,
    y: np.ndarray,
    variable_names: list[str],
    binary_operators: list[str] | None = None,
    unary_operators: list[str] | None = None,
    max_complexity: int = 25,
    niterations: int = 40,
    populations: int = 30,
    constraints: dict | None = None,
    **kwargs,
) -> list[CandidateFormula]:
    """
    Run PySR symbolic regression and return candidate formulas.

    Parameters
    ----------
    X : (N, D) feature matrix
    y : (N,) target array
    variable_names : names for each column of X
    binary_operators : allowed binary ops e.g. ["+", "-", "*", "/"]
    unary_operators : allowed unary ops e.g. ["sqrt", "exp", "log"]
    max_complexity : max expression tree size
    niterations : SR iterations
    populations : number of evolutionary populations
    constraints : PySR constraints dict for nesting rules
    """
    if not HAS_PYSR:
        logger.warning("PySR not installed; falling back to built-in symbolic search")
        return builtin_symbolic_search(X, y, variable_names, max_complexity=max_complexity)

    if binary_operators is None:
        binary_operators = ["+", "-", "*", "/"]
    if unary_operators is None:
        unary_operators = ["sqrt", "exp", "log", "abs"]

    logger.info(f"Running PySR: {niterations} iterations, max_complexity={max_complexity}")

    model = PySRRegressor(
        binary_operators=binary_operators,
        unary_operators=unary_operators,
        niterations=niterations,
        populations=populations,
        maxsize=max_complexity,
        variable_names=variable_names,
        constraints=constraints or {},
        deterministic=True,
        procs=0,  # single-threaded for reproducibility
        random_state=42,
        verbosity=0,
        **kwargs,
    )
    model.fit(X, y)

    candidates = []
    for idx in range(len(model.equations_)):
        eq = model.equations_.iloc[idx]
        try:
            expr = sympify(eq["sympy_format"])
            pred = model.predict(X, index=idx)
            mae = float(np.mean(np.abs(pred - y)))
            ss_res = np.sum((y - pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

            candidates.append(CandidateFormula(
                expr=expr,
                score=eq["loss"],
                complexity=int(eq["complexity"]),
                mae=mae,
                r_squared=r2,
                variables=[str(s) for s in expr.free_symbols],
            ))
        except Exception as e:
            logger.debug(f"Skipping equation {idx}: {e}")

    candidates.sort(key=lambda c: c.score)
    logger.info(f"PySR returned {len(candidates)} candidate formulas")
    return candidates


# ---------------------------------------------------------------------------
# Built-in lightweight symbolic search (no PySR dependency)
# ---------------------------------------------------------------------------

# Grammar for expression templates
_BINARY_OPS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": lambda a, b: a / b if abs(b) > 1e-12 else 1e12 * np.sign(a),
}

_UNARY_OPS = {
    "sqrt": lambda x: np.sqrt(np.abs(x)),
    "inv": lambda x: 1.0 / x if abs(x) > 1e-12 else 1e12,
    "sq": lambda x: x**2,
    "log": lambda x: np.log(np.abs(x) + 1e-12),
    "exp_clip": lambda x: np.exp(np.clip(x, -20, 20)),
}

_UNARY_SYMPY = {
    "sqrt": lambda s: sqrt(Abs(s)),
    "inv": lambda s: 1 / s,
    "sq": lambda s: s**2,
    "log": lambda s: log(Abs(s)),
    "exp_clip": lambda s: exp(s),
}


def _evaluate_expr_safe(func: Callable, X: np.ndarray) -> Optional[np.ndarray]:
    """Evaluate a numpy expression safely, returning None if it produces NaN/Inf."""
    try:
        result = func(X)
        if isinstance(result, (int, float)):
            result = np.full(X.shape[0], result)
        if np.any(~np.isfinite(result)):
            return None
        return result
    except (ZeroDivisionError, FloatingPointError, ValueError, OverflowError):
        return None


def _fit_linear(features: np.ndarray, y: np.ndarray):
    """Least-squares fit: y = a·features + b."""
    A = np.column_stack([features, np.ones(len(y))])
    try:
        coeffs, residuals, _, _ = np.linalg.lstsq(A, y, rcond=None)
        pred = A @ coeffs
        mae = np.mean(np.abs(pred - y))
        ss_res = np.sum((y - pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        return coeffs, mae, r2, pred
    except np.linalg.LinAlgError:
        return None, float("inf"), 0.0, None


def builtin_symbolic_search(
    X: np.ndarray,
    y: np.ndarray,
    variable_names: list[str],
    max_complexity: int = 20,
    max_terms: int = 4,
    allowed_unary: list[str] | None = None,
    top_k: int = 50,
) -> list[CandidateFormula]:
    """
    Lightweight symbolic regression via exhaustive template enumeration.

    Enumerates expressions of the form:
      y ≈ c₀ + c₁·f₁(x_i) + c₂·f₂(x_j) + ... + cₙ·fₙ(x_i ⊕ x_j)

    where f_k ∈ {id, sqrt, inv, sq, log} and ⊕ ∈ {+, -, *, /}.
    """
    if allowed_unary is None:
        allowed_unary = ["id", "sqrt", "inv", "sq", "log"]

    logger.info(f"Built-in symbolic search: {X.shape[1]} vars, max_terms={max_terms}")
    t0 = time.time()

    syms = [Symbol(n) for n in variable_names]
    D = X.shape[1]

    # Phase 1: Build basis of single-variable features
    basis_features: list[tuple[np.ndarray, Expr, str]] = []
    for i in range(D):
        xi = X[:, i]
        si = syms[i]
        # identity
        basis_features.append((xi, si, f"{variable_names[i]}"))
        # unary transforms
        for uname in allowed_unary:
            if uname == "id":
                continue
            uf = _UNARY_OPS.get(uname)
            us = _UNARY_SYMPY.get(uname)
            if uf and us:
                vals = _evaluate_expr_safe(lambda X, _i=i, _uf=uf: _uf(X[:, _i]), X)
                if vals is not None:
                    basis_features.append((vals, us(si), f"{uname}({variable_names[i]})"))

    # Phase 2: Two-variable interaction features
    interaction_features: list[tuple[np.ndarray, Expr, str]] = []
    for i, j in itertools.combinations(range(D), 2):
        xi, xj = X[:, i], X[:, j]
        si, sj = syms[i], syms[j]
        for op_name, op_func in [("*", operator.mul), ("/", _BINARY_OPS["/"])]:
            vals = _evaluate_expr_safe(
                lambda X, _i=i, _j=j, _op=op_func: _op(X[:, _i], X[:, _j]), X
            )
            sym_expr = operator.mul(si, sj) if op_name == "*" else si / sj
            if vals is not None:
                interaction_features.append((vals, sym_expr,
                                             f"{variable_names[i]}{op_name}{variable_names[j]}"))

    all_features = basis_features + interaction_features
    logger.info(f"  Built {len(all_features)} candidate features "
                f"({len(basis_features)} basis + {len(interaction_features)} interactions)")

    # Phase 3: Enumerate multi-term combinations and fit
    candidates: list[CandidateFormula] = []

    # Single-term formulas
    for vals, sym_expr, desc in all_features:
        coeffs, mae, r2, pred = _fit_linear(vals, y)
        if coeffs is not None and mae < 1e6:
            full_expr = Float(round(coeffs[0], 4)) * sym_expr + Float(round(coeffs[1], 4))
            full_expr = simplify(full_expr)
            candidates.append(CandidateFormula(
                expr=full_expr, score=mae, complexity=_count_ops(full_expr),
                mae=mae, r_squared=r2,
                variables=[str(s) for s in full_expr.free_symbols],
            ))

    # Multi-term formulas (2 and 3 terms)
    for n_terms in range(2, min(max_terms + 1, 4)):
        for combo in itertools.combinations(range(len(all_features)), n_terms):
            feat_matrix = np.column_stack([all_features[k][0] for k in combo])
            coeffs, mae, r2, pred = _fit_linear(feat_matrix.sum(axis=1), y)
            if coeffs is None or mae > candidates[0].mae * 5 if candidates else True:
                # Try proper multi-variate fit
                A = np.column_stack([all_features[k][0] for k in combo] + [np.ones(len(y))])
                try:
                    coeffs_mv, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
                    pred_mv = A @ coeffs_mv
                    mae_mv = float(np.mean(np.abs(pred_mv - y)))
                    ss_res = np.sum((y - pred_mv) ** 2)
                    ss_tot = np.sum((y - y.mean()) ** 2)
                    r2_mv = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

                    # Build symbolic expression
                    terms = []
                    for idx_c, k in enumerate(combo):
                        c = round(float(coeffs_mv[idx_c]), 4)
                        if abs(c) > 1e-6:
                            terms.append(Float(c) * all_features[k][1])
                    intercept = round(float(coeffs_mv[-1]), 4)
                    if terms:
                        full_expr = sum(terms) + Float(intercept)
                        full_expr = simplify(full_expr)
                        cplx = _count_ops(full_expr)
                        if cplx <= max_complexity:
                            candidates.append(CandidateFormula(
                                expr=full_expr, score=mae_mv, complexity=cplx,
                                mae=mae_mv, r_squared=r2_mv,
                                variables=[str(s) for s in full_expr.free_symbols],
                            ))
                except np.linalg.LinAlgError:
                    continue

    candidates.sort(key=lambda c: c.mae)
    candidates = candidates[:top_k]

    elapsed = time.time() - t0
    logger.info(f"  Symbolic search complete: {len(candidates)} candidates in {elapsed:.1f}s")
    if candidates:
        logger.info(f"  Best MAE: {candidates[0].mae:.4f}, R²: {candidates[0].r_squared:.4f}")
        logger.info(f"  Best formula: {candidates[0].expr}")

    return candidates


def _count_ops(expr: Expr) -> int:
    """Count number of operations in a sympy expression as complexity measure."""
    return expr.count_ops()


# ---------------------------------------------------------------------------
# Template-based symbolic expansion
# ---------------------------------------------------------------------------

# Physical formula templates common in materials science
PEROVSKITE_TEMPLATES = [
    "a * (EN_X - EN_B) + b",
    "a * (EN_X - EN_B) + b / t_factor + c",
    "a * (EN_X - EN_B) + b * octahedral_factor + c",
    "a * (EN_X - EN_B) + b / t_factor + c * octahedral_factor + d",
    "a * delta_EN + b * t_factor**(-1) + c",
    "a * (IE_B - EA_B) + b * t_factor + c",
    "a * (EN_X - EN_B) + b / t_factor + c * (IE_B - EA_B) + d",
    "a * sqrt(delta_EN) + b / t_factor + c",
    "a * EN_X / EN_B + b * t_factor + c",
    "a * r_A / r_B + b * (EN_X - EN_B) + c",
    "a * (r_A + r_X) / (r_B + r_X) + b * EN_B + c",
    "a * delta_EN**2 + b * t_factor + c * octahedral_factor + d",
]


def fit_template(
    template_str: str,
    X: np.ndarray,
    y: np.ndarray,
    variable_names: list[str],
) -> Optional[CandidateFormula]:
    """
    Fit a symbolic template by optimizing its free coefficients via least squares.

    Parameters
    ----------
    template_str : e.g. "a * (EN_X - EN_B) + b / t_factor + c"
    X : descriptor matrix
    y : target
    variable_names : descriptor names matching X columns

    Returns
    -------
    CandidateFormula or None if template can't be evaluated.
    """
    var_map = {name: X[:, i] for i, name in enumerate(variable_names)}

    # Parse template to identify feature columns
    # We use sympy to symbolically parse, then evaluate numerically
    all_syms = {name: Symbol(name) for name in variable_names}
    coeff_names = [chr(ord('a') + i) for i in range(10)]
    coeff_syms = {n: Symbol(n) for n in coeff_names}

    try:
        expr = sympify(template_str, locals={**all_syms, **coeff_syms})
    except Exception:
        return None

    # Identify coefficient symbols used
    used_coeffs = [s for s in expr.free_symbols if str(s) in coeff_names]
    used_vars = [s for s in expr.free_symbols if str(s) in variable_names]

    if not used_coeffs or not used_vars:
        return None

    # Build design matrix: template should be linear in coefficients
    # Express as y = Σ c_k * phi_k(x)
    # Collect terms by coefficient
    from sympy import collect, Add
    design_cols = []
    for c in sorted(used_coeffs, key=str):
        # Coefficient of c in the expression
        term = expr.coeff(c)
        if term == 0:
            continue
        # Evaluate term numerically
        try:
            term_func = _sympy_to_numpy(term, variable_names, var_map)
            if term_func is not None:
                design_cols.append(term_func)
        except Exception:
            return None

    if not design_cols:
        return None

    A = np.column_stack(design_cols)
    try:
        coeffs, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    except np.linalg.LinAlgError:
        return None

    pred = A @ coeffs
    if not np.all(np.isfinite(pred)):
        return None

    mae = float(np.mean(np.abs(pred - y)))
    ss_res = np.sum((y - pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Substitute numerical coefficients back into symbolic expression
    final_expr = expr
    for i, c in enumerate(sorted(used_coeffs, key=str)):
        if i < len(coeffs):
            final_expr = final_expr.subs(c, Float(round(float(coeffs[i]), 4)))
    final_expr = simplify(final_expr)

    return CandidateFormula(
        expr=final_expr, score=mae, complexity=_count_ops(final_expr),
        mae=mae, r_squared=r2,
        variables=[str(s) for s in final_expr.free_symbols if str(s) in variable_names],
    )


def _sympy_to_numpy(
    expr: Expr,
    variable_names: list[str],
    var_map: dict[str, np.ndarray],
) -> Optional[np.ndarray]:
    """Evaluate a sympy expression with numpy arrays."""
    from sympy import lambdify
    syms = [Symbol(n) for n in variable_names]
    used = [s for s in syms if s in expr.free_symbols]
    if not used:
        # Constant expression
        try:
            val = float(expr)
            return np.full(len(next(iter(var_map.values()))), val)
        except (TypeError, ValueError):
            return None
    try:
        f = lambdify(used, expr, modules=["numpy"])
        args = [var_map[str(s)] for s in used]
        result = f(*args)
        if isinstance(result, (int, float)):
            result = np.full(len(next(iter(var_map.values()))), result)
        if np.all(np.isfinite(result)):
            return result
    except Exception:
        pass
    return None


def fit_all_templates(
    X: np.ndarray,
    y: np.ndarray,
    variable_names: list[str],
    templates: list[str] | None = None,
) -> list[CandidateFormula]:
    """Fit all physical templates and return ranked candidates."""
    if templates is None:
        templates = PEROVSKITE_TEMPLATES

    logger.info(f"Fitting {len(templates)} physical templates...")
    candidates = []
    for t in templates:
        c = fit_template(t, X, y, variable_names)
        if c is not None:
            candidates.append(c)

    candidates.sort(key=lambda c: c.mae)
    if candidates:
        logger.info(f"  Best template MAE: {candidates[0].mae:.4f}")
    return candidates
