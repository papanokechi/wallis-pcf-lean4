"""
Self-improvement controller — orchestrates exponential tightening
of the discovery loop across iterations.

Responsibilities:
  1. Refine training data distribution (focus on decision boundaries)
  2. Tighten the hypothesis language (prune unused operators/exponents)
  3. Update priors on dimensionless groups
  4. Track convergence and decide when to stop
"""
from __future__ import annotations

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter

from .symbolic_engine import SymbolicLaw, SymbolicDistillationEngine
from .surrogate import DynamicalSurrogate
from .nbody import DatasetGenerator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Iteration state
# ---------------------------------------------------------------------------
@dataclass
class IterationState:
    """Snapshot of one self-improvement round."""
    round_idx: int
    n_train_samples: int
    n_features: int
    best_law: Optional[SymbolicLaw]
    all_laws: list[SymbolicLaw]
    surrogate_accuracy: float
    search_space_size: int    # proxy: |operators| × |exponents| × max_complexity
    data_entropy: float       # entropy of label distribution (balance metric)
    improvement_ratio: float  # R² gain over previous round
    notes: str = ""


# ---------------------------------------------------------------------------
# Self-improvement controller
# ---------------------------------------------------------------------------
class SelfImprovementController:
    """
    Implements the exponential refinement loop:

      - Each round, the controller analyses the discovered laws
        to prune the operator/exponent vocabulary.
      - It re-weights the data distribution to focus on
        misclassified or boundary-region systems.
      - It tracks the shrinkage rate of the search space and
        the improvement in law quality, aiming for exponential
        convergence.
    """

    def __init__(
        self,
        max_rounds: int = 10,
        min_improvement: float = 0.001,
        data_focus_fraction: float = 0.3,
        complexity_decay: float = 0.85,
        operator_prune_threshold: float = 0.05,
    ):
        self.max_rounds = max_rounds
        self.min_improvement = min_improvement
        self.data_focus_fraction = data_focus_fraction
        self.complexity_decay = complexity_decay
        self.operator_prune_threshold = operator_prune_threshold

        self.history: list[IterationState] = []
        self._best_r2: float = -np.inf
        self._best_law: Optional[SymbolicLaw] = None
        self._round: int = 0

    # -- operator analysis -------------------------------------------------
    def _analyse_operator_usage(
        self, laws: list[SymbolicLaw]
    ) -> dict[str, float]:
        """Count operator frequency across top laws."""
        all_ops = ["+", "-", "*", "/", "pow", "sqrt", "log",
                   "exp", "abs", "square", "cube"]
        counts: Counter = Counter()
        for law in laws:
            expr = law.expression.lower()
            for op in all_ops:
                if op in expr:
                    counts[op] += 1

        total = max(sum(counts.values()), 1)
        return {op: counts.get(op, 0) / total for op in all_ops}

    def _analyse_exponent_usage(
        self, laws: list[SymbolicLaw]
    ) -> list[float]:
        """Extract exponents that appear in top laws."""
        import re
        exponents_found = set()
        for law in laws:
            # Parse exponents from expressions like "x^2.5" or "x^{-1/3}"
            matches = re.findall(r'\^[({]?(-?[\d.]+(?:/[\d.]+)?)[)}]?', law.expression)
            for m in matches:
                try:
                    if "/" in m:
                        num, den = m.split("/")
                        exponents_found.add(float(num) / float(den))
                    else:
                        exponents_found.add(float(m))
                except ValueError:
                    pass
            # Also check coefficient dict
            for key, val in law.coefficients.items():
                # Parse exponent from key like "delta_Hill^2"
                if "^" in key:
                    try:
                        exp_str = key.split("^")[-1]
                        exponents_found.add(float(exp_str))
                    except ValueError:
                        pass

        return sorted(exponents_found) if exponents_found else None

    # -- data refinement ---------------------------------------------------
    def refine_training_data(
        self,
        X: np.ndarray,
        y: np.ndarray,
        surrogate: DynamicalSurrogate,
        generator: DatasetGenerator,
        n_new_boundary: int = 50,
        n_new_random: int = 50,
        integration_steps: int = 5000,
        dt: float = 0.01,
        stability_threshold: float = 4.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Refine the training set by:
          1. Identifying boundary samples (where surrogate is uncertain)
          2. Generating new systems near the decision boundary
          3. Adding random samples for coverage
        """
        # Get surrogate uncertainty
        probs = surrogate.predict_proba(X)
        uncertainty = np.abs(probs - 0.5)  # 0 = most uncertain, 0.5 = most certain

        # Select the most uncertain samples to keep
        n_keep = int(len(X) * (1 - self.data_focus_fraction))
        uncertain_indices = np.argsort(uncertainty)
        boundary_indices = uncertain_indices[:int(len(X) * self.data_focus_fraction)]
        certain_indices = uncertain_indices[int(len(X) * self.data_focus_fraction):]

        # Keep all boundary + subsample certain
        if len(certain_indices) > n_keep:
            keep_certain = np.random.choice(certain_indices, n_keep, replace=False)
        else:
            keep_certain = certain_indices
        keep_indices = np.concatenate([boundary_indices, keep_certain])

        X_refined = X[keep_indices]
        y_refined = y[keep_indices]

        # Generate new boundary systems (perturb uncertain ones)
        if n_new_boundary > 0 and len(boundary_indices) > 0:
            boundary_X = X[boundary_indices]
            new_X_list = []
            new_y_list = []

            for _ in range(n_new_boundary):
                # Pick a random boundary sample and perturb
                idx = np.random.randint(len(boundary_X))
                x_base = boundary_X[idx].copy()
                perturbation = np.random.randn(len(x_base)) * 0.05
                x_new = np.clip(x_base + perturbation * np.abs(x_base), 1e-10, None)
                new_X_list.append(x_new)
                # Label via surrogate (fast) — to be corrected by N-body later
                pred = surrogate.predict(x_new.reshape(1, -1))[0]
                new_y_list.append(pred)

            X_boundary_new = np.array(new_X_list)
            y_boundary_new = np.array(new_y_list)
            X_refined = np.vstack([X_refined, X_boundary_new])
            y_refined = np.concatenate([y_refined, y_boundary_new])

        # Generate random new systems for diversity
        if n_new_random > 0:
            new_data = generator.generate_dataset(
                n_systems=n_new_random,
                integration_steps=integration_steps,
                dt=dt,
                stability_threshold=stability_threshold,
            )
            X_refined = np.vstack([X_refined, new_data["features"]])
            y_refined = np.concatenate([y_refined, new_data["labels"]])

        logger.info(
            f"  Data refinement: {len(X)} → {len(X_refined)} samples "
            f"({len(boundary_indices)} boundary, {n_new_boundary} new boundary, "
            f"{n_new_random} new random)"
        )
        return X_refined, y_refined

    # -- hypothesis space tightening ---------------------------------------
    def tighten_hypothesis_space(
        self,
        engine: SymbolicDistillationEngine,
        laws: list[SymbolicLaw],
    ) -> dict:
        """
        Prune operators and exponents based on what appeared in
        the best laws from this round. This is the key mechanism
        for exponential search space reduction.
        """
        op_usage = self._analyse_operator_usage(laws[:10])
        exp_usage = self._analyse_exponent_usage(laws[:10])

        # Prune binary operators below threshold
        all_binary = ["+", "-", "*", "/", "pow"]
        all_unary = ["sqrt", "log", "exp", "abs", "square", "cube"]
        kept_binary = [op for op in all_binary
                       if op_usage.get(op, 0) >= self.operator_prune_threshold]
        kept_unary = [op for op in all_unary
                      if op_usage.get(op, 0) >= self.operator_prune_threshold]

        # Always keep +, -, *, / as core operators
        for essential in ["+", "-", "*", "/"]:
            if essential not in kept_binary:
                kept_binary.append(essential)

        # Reduce max complexity
        new_max_complexity = max(
            5, int(engine.max_complexity * self.complexity_decay)
        )

        # Tighten exponent grid (if using builtin)
        new_exponent_grid = None
        if exp_usage is not None and len(exp_usage) > 0:
            # Keep discovered exponents + small neighbourhood
            expanded = set()
            for e in exp_usage:
                expanded.add(e)
                expanded.add(e - 0.5)
                expanded.add(e + 0.5)
            # Always keep standard exponents
            for std_e in [-2, -1, -0.5, 0, 0.5, 1, 2]:
                expanded.add(std_e)
            new_exponent_grid = sorted(expanded)

        engine.restrict_search_space(
            allowed_binary=kept_binary,
            allowed_unary=kept_unary,
            max_complexity=new_max_complexity,
            exponent_grid=new_exponent_grid,
        )

        old_space = len(all_binary) * len(all_unary) * engine.max_complexity
        new_space = len(kept_binary) * len(kept_unary) * new_max_complexity

        tightening_info = {
            "kept_binary": kept_binary,
            "kept_unary": kept_unary,
            "new_max_complexity": new_max_complexity,
            "new_exponent_grid": new_exponent_grid,
            "space_reduction_factor": old_space / max(new_space, 1),
            "operator_usage": op_usage,
        }

        logger.info(
            f"  Hypothesis tightening: binary={kept_binary}, "
            f"unary={kept_unary}, max_complexity={new_max_complexity}, "
            f"space reduction={tightening_info['space_reduction_factor']:.2f}×"
        )
        return tightening_info

    # -- convergence check -------------------------------------------------
    def should_stop(self) -> bool:
        """Check if the loop has converged or exceeded max rounds."""
        if self._round >= self.max_rounds:
            logger.info(f"  Stopping: reached max rounds ({self.max_rounds})")
            return True

        if len(self.history) >= 2:
            recent_improvement = (
                self.history[-1].improvement_ratio
            )
            if recent_improvement < self.min_improvement:
                logger.info(
                    f"  Stopping: improvement {recent_improvement:.6f} "
                    f"< threshold {self.min_improvement}"
                )
                return True

        return False

    # -- record state ------------------------------------------------------
    def record_iteration(
        self,
        laws: list[SymbolicLaw],
        surrogate_accuracy: float,
        n_train: int,
        n_features: int,
        search_space_size: int,
        y_train: np.ndarray,
    ) -> IterationState:
        """Record the state of this iteration."""
        best_law = laws[0] if laws else None
        current_r2 = best_law.r_squared if best_law else -np.inf

        improvement = current_r2 - self._best_r2
        if current_r2 > self._best_r2:
            self._best_r2 = current_r2
            self._best_law = best_law

        # Data entropy (balance metric)
        if len(y_train) > 0:
            p1 = np.mean(y_train)
            p0 = 1 - p1
            entropy = 0.0
            if p0 > 0:
                entropy -= p0 * np.log2(p0)
            if p1 > 0:
                entropy -= p1 * np.log2(p1)
        else:
            entropy = 0.0

        state = IterationState(
            round_idx=self._round,
            n_train_samples=n_train,
            n_features=n_features,
            best_law=best_law,
            all_laws=laws,
            surrogate_accuracy=surrogate_accuracy,
            search_space_size=search_space_size,
            data_entropy=entropy,
            improvement_ratio=improvement,
        )
        self.history.append(state)
        self._round += 1

        logger.info(
            f"  Round {state.round_idx}: best R²={current_r2:.4f}, "
            f"improvement={improvement:.4f}, "
            f"surrogate_acc={surrogate_accuracy:.4f}, "
            f"search_space={search_space_size}"
        )
        return state

    # -- summary -----------------------------------------------------------
    def summary(self) -> dict:
        """Return a summary of the entire self-improvement run."""
        return {
            "total_rounds": self._round,
            "best_law": self._best_law,
            "best_r_squared": self._best_r2,
            "history": [
                {
                    "round": s.round_idx,
                    "best_r2": s.best_law.r_squared if s.best_law else None,
                    "best_expr": s.best_law.expression if s.best_law else None,
                    "surrogate_accuracy": s.surrogate_accuracy,
                    "search_space_size": s.search_space_size,
                    "n_train_samples": s.n_train_samples,
                    "improvement_ratio": s.improvement_ratio,
                }
                for s in self.history
            ],
            "exponential_convergence": self._check_exponential_convergence(),
        }

    def _check_exponential_convergence(self) -> dict:
        """
        Verify that search space is shrinking roughly exponentially.
        Fits log(search_space) ~ -k * round and checks k > 0.
        """
        if len(self.history) < 3:
            return {"verified": False, "reason": "not enough rounds"}

        rounds = np.array([s.round_idx for s in self.history], dtype=float)
        spaces = np.array([max(s.search_space_size, 1) for s in self.history], dtype=float)
        log_spaces = np.log(spaces)

        # Linear fit: log(space) = a + b * round
        coeffs = np.polyfit(rounds, log_spaces, 1)
        decay_rate = -coeffs[0]  # should be positive for shrinkage

        return {
            "verified": decay_rate > 0.05,
            "decay_rate": float(decay_rate),
            "half_life_rounds": float(np.log(2) / max(decay_rate, 1e-10)),
            "fit_coefficients": coeffs.tolist(),
        }
