"""
Evaluation Module
=================
Metrics and evaluation utilities for comparing discovered micro-laws
against baselines and measuring physical plausibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from loguru import logger
from sympy import Expr, Symbol, lambdify


@dataclass
class EvaluationResult:
    """Comprehensive evaluation result for a formula."""
    mae: float
    rmse: float
    r_squared: float
    max_error: float
    median_ae: float
    complexity: int
    n_variables: int
    predictions: np.ndarray | None = None
    residuals: np.ndarray | None = None


def evaluate_formula(
    expr: Expr,
    X: np.ndarray,
    y: np.ndarray,
    variable_names: list[str],
) -> EvaluationResult:
    """
    Evaluate a symbolic formula on data.

    Parameters
    ----------
    expr : sympy expression
    X : (N, D) descriptor matrix
    y : (N,) target values
    variable_names : names of descriptor columns
    """
    syms = [Symbol(n) for n in variable_names]
    used = [s for s in syms if s in expr.free_symbols]

    try:
        f = lambdify(used, expr, modules=["numpy"])
        name_to_idx = {n: i for i, n in enumerate(variable_names)}
        args = [X[:, name_to_idx[str(s)]] for s in used]
        pred = f(*args)

        if isinstance(pred, (int, float)):
            pred = np.full(len(y), pred)

        pred = np.asarray(pred, dtype=float)

        if not np.all(np.isfinite(pred)):
            return EvaluationResult(
                mae=float("inf"), rmse=float("inf"), r_squared=-float("inf"),
                max_error=float("inf"), median_ae=float("inf"),
                complexity=int(expr.count_ops()),
                n_variables=len(used),
            )

        residuals = y - pred
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        max_err = float(np.max(np.abs(residuals)))
        median_ae = float(np.median(np.abs(residuals)))

        return EvaluationResult(
            mae=mae, rmse=rmse, r_squared=r2,
            max_error=max_err, median_ae=median_ae,
            complexity=int(expr.count_ops()),
            n_variables=len(used),
            predictions=pred,
            residuals=residuals,
        )

    except Exception as e:
        logger.debug(f"Evaluation failed for {expr}: {e}")
        return EvaluationResult(
            mae=float("inf"), rmse=float("inf"), r_squared=-float("inf"),
            max_error=float("inf"), median_ae=float("inf"),
            complexity=int(expr.count_ops()),
            n_variables=len(expr.free_symbols),
        )


def compare_methods(
    constrained_results: list[EvaluationResult],
    unconstrained_results: list[EvaluationResult],
) -> dict:
    """
    Compare constrained vs unconstrained SR results.

    Returns summary statistics and improvement metrics.
    """
    def best_by_mae(results):
        valid = [r for r in results if np.isfinite(r.mae)]
        return min(valid, key=lambda r: r.mae) if valid else None

    c_best = best_by_mae(constrained_results)
    u_best = best_by_mae(unconstrained_results)

    comparison = {
        "constrained_best_mae": c_best.mae if c_best else float("inf"),
        "unconstrained_best_mae": u_best.mae if u_best else float("inf"),
        "constrained_best_r2": c_best.r_squared if c_best else 0.0,
        "unconstrained_best_r2": u_best.r_squared if u_best else 0.0,
        "constrained_complexity": c_best.complexity if c_best else 0,
        "unconstrained_complexity": u_best.complexity if u_best else 0,
    }

    if c_best and u_best and u_best.mae > 0:
        comparison["mae_improvement"] = 1 - c_best.mae / u_best.mae
        comparison["r2_improvement"] = c_best.r_squared - u_best.r_squared
        comparison["complexity_reduction"] = 1 - c_best.complexity / u_best.complexity \
            if u_best.complexity > 0 else 0
    else:
        comparison["mae_improvement"] = 0.0
        comparison["r2_improvement"] = 0.0
        comparison["complexity_reduction"] = 0.0

    return comparison


@dataclass
class IterationLog:
    """Track metrics across iterations of the refinement loop."""
    entries: list[dict] = field(default_factory=list)

    def log(self, iteration: int, **kwargs):
        self.entries.append({"iteration": iteration, **kwargs})

    def get_series(self, key: str) -> list:
        return [e.get(key) for e in self.entries if key in e]

    def summary(self) -> str:
        if not self.entries:
            return "No iterations logged."
        lines = []
        lines.append(f"{'Iter':>4} | {'MAE':>8} | {'R²':>8} | "
                      f"{'Cplx':>4} | {'Candidates':>10} | {'Surviving':>9}")
        lines.append("-" * 60)
        for e in self.entries:
            lines.append(
                f"{e.get('iteration', '?'):>4} | "
                f"{e.get('best_mae', float('inf')):>8.4f} | "
                f"{e.get('best_r2', 0):>8.4f} | "
                f"{e.get('best_complexity', '?'):>4} | "
                f"{e.get('n_candidates', '?'):>10} | "
                f"{e.get('n_surviving', '?'):>9}"
            )
        return "\n".join(lines)
