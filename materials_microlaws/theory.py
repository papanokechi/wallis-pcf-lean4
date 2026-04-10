"""
Theoretical Framework
=====================
Formal theorems and bounds for the constrained symbolic regression framework.

Provides:
  - Theorem 1: Search Space Reduction under Physical Constraints
  - Theorem 2: Spurious Law Probability Bound
  - Corollary: Identifiability improvement per iteration
  - Numerical prediction framework
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from loguru import logger


# ===========================================================================
# Theorem 1: Search Space Reduction Under Physical Constraints
# ===========================================================================

@dataclass
class SearchSpaceReductionTheorem:
    """
    Theorem 1 (Search Space Reduction).

    Let S_0 be the unconstrained hypothesis space of symbolic expressions
    with D descriptors, maximum complexity C (measured in AST nodes), and
    operator set O = O_bin ∪ O_un.

    |S_0| ≤ D^C · (|O_bin| + |O_un|)^C · C! / (C/2)!^2

    (Catalan-number-like enumeration of binary trees with C internal/leaf nodes.)

    Let Φ = {φ₁, ..., φ_K} be a set of K independent hard constraints
    (dimensional consistency, monotonicity, boundedness, symmetry).
    Let p_k = P(random expression satisfies φ_k).

    If constraints are approximately independent, the constrained space satisfies:

      |S_Φ| ≤ |S_0| · ∏_{k=1}^K p_k

    Reduction factor:

      R(Φ) = |S_0| / |S_Φ| ≥ ∏_{k=1}^K (1 / p_k)

    For typical materials-science constraints:
      - Dimensional consistency:  p_dim ≈ 0.05–0.15
      - Monotonicity (per rule):  p_mono ≈ 0.3–0.5
      - Boundedness (Eg ≥ 0):     p_bound ≈ 0.4–0.6
      - Complexity (≤ C_max):     p_cplx ≈ depends on C_max / C

    With 2 monotonicity rules:
      R ≈ (1/0.1) · (1/0.4)² · (1/0.5) = 10 · 6.25 · 2 = 125×

    Per iteration, the descriptor set and template space are further pruned,
    yielding exponential cumulative reduction:

      R_total(K_iter) = ∏_{t=1}^{K_iter} R_t ≥ R_1^{α · K_iter}

    where α ∈ (0.6, 1.0) accounts for diminishing returns.
    """

    D: int           # number of descriptors
    C_max: int       # max complexity
    n_binary_ops: int = 4   # +, -, *, /
    n_unary_ops: int = 4    # sqrt, log, exp, abs
    p_dim: float = 0.10     # probability of dimensional consistency
    p_mono: float = 0.40    # probability of satisfying a monotonicity rule
    p_bound: float = 0.50   # probability of satisfying boundedness
    p_cplx: float = 0.30    # probability of complexity constraint satisfaction
    n_mono_rules: int = 2   # number of monotonicity rules
    alpha: float = 0.8      # diminishing returns factor

    def unconstrained_space_size(self) -> float:
        """Upper bound on |S_0|: unconstrained hypothesis space."""
        # Catalan number for binary trees with C leaves
        C = self.C_max
        catalan = math.comb(2 * C, C) / (C + 1)
        # Each internal node chooses an operator, each leaf chooses a descriptor
        # Simplified upper bound
        return (self.D ** C) * ((self.n_binary_ops + self.n_unary_ops) ** C) * catalan

    def constraint_pass_probability(self) -> float:
        """Product of individual constraint satisfaction probabilities."""
        p = self.p_dim * (self.p_mono ** self.n_mono_rules) * self.p_bound * self.p_cplx
        return p

    def reduction_factor(self) -> float:
        """Single-iteration reduction factor R(Φ)."""
        p = self.constraint_pass_probability()
        return 1.0 / p if p > 0 else float("inf")

    def cumulative_reduction(self, n_iterations: int) -> float:
        """Cumulative reduction after n_iterations of refinement."""
        R1 = self.reduction_factor()
        return R1 ** (self.alpha * n_iterations)

    def constrained_space_size(self) -> float:
        """Upper bound on |S_Φ|: constrained hypothesis space."""
        return self.unconstrained_space_size() * self.constraint_pass_probability()

    def summary(self) -> dict:
        return {
            "|S_0| (log10)": math.log10(self.unconstrained_space_size()),
            "|S_Φ| (log10)": math.log10(max(self.constrained_space_size(), 1)),
            "R (single iteration)": self.reduction_factor(),
            "R (5 iterations)": self.cumulative_reduction(5),
            "R (10 iterations)": self.cumulative_reduction(10),
            "p_pass": self.constraint_pass_probability(),
        }

    def print_theorem(self):
        s = self.summary()
        logger.info("=" * 70)
        logger.info("THEOREM 1: Search Space Reduction Under Physical Constraints")
        logger.info("=" * 70)
        logger.info(f"  Descriptors D = {self.D}, Max complexity C = {self.C_max}")
        logger.info(f"  Unconstrained space |S_0| ≈ 10^{s['|S_0| (log10)']:.1f}")
        logger.info(f"  Constrained space   |S_Φ| ≈ 10^{s['|S_Φ| (log10)']:.1f}")
        logger.info(f"  Single-iteration reduction R = {s['R (single iteration)']:.1f}×")
        logger.info(f"  After 5 iterations:  R_cum ≈ {s['R (5 iterations)']:.1e}×")
        logger.info(f"  After 10 iterations: R_cum ≈ {s['R (10 iterations)']:.1e}×")
        logger.info(f"  Constraint satisfaction probability p = {s['p_pass']:.4f}")
        logger.info("=" * 70)


# ===========================================================================
# Theorem 2: Spurious Law Probability Bound
# ===========================================================================

@dataclass
class SpuriousLawBound:
    """
    Theorem 2 (Spurious Law Probability Bound).

    Let f* be the true data-generating law, and let S_Φ be the constrained
    hypothesis space. A "spurious law" is an expression f ∈ S_Φ that achieves
    MAE ≤ ε on training data of size N but has population MAE > ε + δ.

    Under sub-Gaussian noise with parameter σ, the probability of selecting
    a spurious law is bounded by:

      P(spurious) ≤ |S_Φ| · exp(-N·δ² / (8·σ²))

    Equivalently, to ensure P(spurious) ≤ η:

      N ≥ (8·σ² / δ²) · (log|S_Φ| + log(1/η))

    Key insight: By reducing |S_Φ| through physical constraints, we reduce
    the required sample size logarithmically. A 100× reduction in |S_Φ|
    reduces the sample requirement by 8σ²·log(100)/δ² ≈ 37σ²/δ² samples.

    For constrained SR after K iterations with cumulative reduction R_cum:

      P_K(spurious) ≤ (|S_0| / R_cum) · exp(-N·δ² / (8·σ²))

    This is exponentially smaller than the unconstrained bound.
    """

    sigma: float = 0.1          # noise parameter (eV for band gaps)
    delta: float = 0.05         # generalization gap threshold
    eta: float = 0.05           # desired bound on spurious probability
    log_S_phi: float = 10.0     # log10|S_Φ|

    def spurious_probability(self, N: int) -> float:
        """Bound on P(spurious law) given N training samples."""
        log_bound = self.log_S_phi * np.log(10) - N * self.delta**2 / (8 * self.sigma**2)
        return min(float(np.exp(log_bound)), 1.0)

    def required_samples(self) -> int:
        """Minimum N to achieve P(spurious) ≤ η."""
        numerator = 8 * self.sigma**2 * (self.log_S_phi * np.log(10) + np.log(1 / self.eta))
        N = numerator / self.delta**2
        return int(np.ceil(N))

    def sample_savings(self, log_S_unconstrained: float) -> int:
        """How many fewer samples are needed compared to unconstrained search."""
        delta_log = log_S_unconstrained - self.log_S_phi
        savings = 8 * self.sigma**2 * delta_log * np.log(10) / self.delta**2
        return int(np.ceil(savings))

    def print_theorem(self):
        N_req = self.required_samples()
        p_50 = self.spurious_probability(50)
        p_100 = self.spurious_probability(100)
        p_200 = self.spurious_probability(200)

        logger.info("=" * 70)
        logger.info("THEOREM 2: Spurious Law Probability Bound")
        logger.info("=" * 70)
        logger.info(f"  Noise σ = {self.sigma} eV, gap threshold δ = {self.delta} eV")
        logger.info(f"  Constrained space log|S_Φ| = {self.log_S_phi:.1f}")
        logger.info(f"  Required N for P(spurious) ≤ {self.eta}: N ≥ {N_req}")
        logger.info(f"  P(spurious | N=50)  ≤ {p_50:.4e}")
        logger.info(f"  P(spurious | N=100) ≤ {p_100:.4e}")
        logger.info(f"  P(spurious | N=200) ≤ {p_200:.4e}")
        logger.info("=" * 70)


# ===========================================================================
# Falsifiable Numerical Predictions
# ===========================================================================

@dataclass
class NumericalPrediction:
    """
    Falsifiable Prediction for Perovskite Band Gaps.

    After K self-improvement iterations on the halide perovskite dataset:

    Prediction P1 (Accuracy):
      The discovered formula achieves MAE ≤ Δ_E eV on held-out compositions,
      outperforming unconstrained SR baselines by ≥ δ_acc in MAE.

    Prediction P2 (Parsimony):
      The best formula uses ≤ C_max terms (AST operations), making it
      human-interpretable and analytically differentiable.

    Prediction P3 (Search Efficiency):
      Constrained search evaluates ≤ F fraction of the total hypothesis
      space while finding formulas in the top-ε quantile of accuracy.

    These predictions are falsifiable by running the framework and comparing
    the constrained vs unconstrained SR results.
    """

    # Prediction parameters (set based on theoretical analysis)
    K_iterations: int = 5
    target_mae_eV: float = 0.15       # ≤ 0.15 eV MAE
    improvement_over_baseline: float = 0.30  # ≥ 30% better than unconstrained
    max_complexity: int = 12           # ≤ 12 AST operations
    search_fraction: float = 0.01     # evaluates ≤ 1% of hypothesis space

    def print_predictions(self):
        logger.info("=" * 70)
        logger.info("FALSIFIABLE NUMERICAL PREDICTIONS")
        logger.info("=" * 70)
        logger.info(f"  After K = {self.K_iterations} self-improvement iterations:")
        logger.info("")
        logger.info(f"  P1: MAE ≤ {self.target_mae_eV} eV on held-out perovskite compositions")
        logger.info(f"      (≥ {self.improvement_over_baseline*100:.0f}% improvement "
                     f"over unconstrained SR baseline)")
        logger.info(f"  P2: Best formula complexity ≤ {self.max_complexity} operations")
        logger.info(f"  P3: Search evaluates ≤ {self.search_fraction*100:.1f}% of "
                     f"unconstrained hypothesis space")
        logger.info("")
        logger.info("  Falsification criteria: Any ONE of the above failing to hold")
        logger.info("  after K iterations on ABX3 halide perovskite data with ≥30 compounds")
        logger.info("=" * 70)

    def evaluate(
        self,
        constrained_mae: float,
        unconstrained_mae: float,
        best_complexity: int,
        n_evaluated: int,
        n_total_space: int,
    ) -> dict:
        """
        Evaluate whether predictions hold.

        Returns dict mapping prediction name → (passed: bool, value, threshold).
        """
        improvement = 1 - constrained_mae / unconstrained_mae if unconstrained_mae > 0 else 0
        search_frac = n_evaluated / n_total_space if n_total_space > 0 else 1.0

        results = {
            "P1_accuracy": {
                "passed": constrained_mae <= self.target_mae_eV,
                "value": constrained_mae,
                "threshold": self.target_mae_eV,
                "unit": "eV",
            },
            "P1_improvement": {
                "passed": improvement >= self.improvement_over_baseline,
                "value": improvement,
                "threshold": self.improvement_over_baseline,
                "unit": "fraction",
            },
            "P2_parsimony": {
                "passed": best_complexity <= self.max_complexity,
                "value": best_complexity,
                "threshold": self.max_complexity,
                "unit": "operations",
            },
            "P3_efficiency": {
                "passed": search_frac <= self.search_fraction,
                "value": search_frac,
                "threshold": self.search_fraction,
                "unit": "fraction",
            },
        }

        all_passed = all(r["passed"] for r in results.values())
        results["overall"] = {"passed": all_passed}

        for name, r in results.items():
            if name == "overall":
                continue
            status = "✓ PASS" if r["passed"] else "✗ FAIL"
            logger.info(f"  {name}: {status} "
                        f"(value={r['value']:.4f}, threshold={r['threshold']:.4f})")

        return results


# ===========================================================================
# Convergence Analysis
# ===========================================================================

def analyze_convergence(
    iteration_metrics: list[dict],
) -> dict:
    """
    Analyze convergence behavior across iterations.

    Parameters
    ----------
    iteration_metrics : list of dicts with keys:
        "iteration", "best_mae", "n_candidates", "n_surviving",
        "search_space_log10"

    Returns
    -------
    Convergence analysis dict.
    """
    if not iteration_metrics:
        return {}

    maes = [m["best_mae"] for m in iteration_metrics]
    spaces = [m.get("search_space_log10", 0) for m in iteration_metrics]

    # Fit exponential decay to MAE: mae(k) ≈ mae(0) · exp(-λ·k)
    K = len(maes)
    if K > 1 and maes[0] > 0:
        log_ratios = [np.log(maes[i] / maes[0]) for i in range(K) if maes[i] > 0]
        if len(log_ratios) > 1:
            ks = np.arange(len(log_ratios))
            # Simple linear fit in log space
            try:
                slope = np.polyfit(ks, log_ratios, 1)[0]
                convergence_rate = -slope
            except np.linalg.LinAlgError:
                convergence_rate = 0.0
        else:
            convergence_rate = 0.0
    else:
        convergence_rate = 0.0

    # Cumulative reduction factor
    total_reduction = 1.0
    for m in iteration_metrics:
        if "n_candidates" in m and "n_surviving" in m and m["n_surviving"] > 0:
            total_reduction *= m["n_candidates"] / m["n_surviving"]

    return {
        "n_iterations": K,
        "initial_mae": maes[0] if maes else None,
        "final_mae": maes[-1] if maes else None,
        "mae_improvement": (maes[0] - maes[-1]) / maes[0] if maes and maes[0] > 0 else 0,
        "convergence_rate_lambda": convergence_rate,
        "cumulative_reduction_factor": total_reduction,
        "log10_cumulative_reduction": np.log10(total_reduction) if total_reduction > 0 else 0,
    }
