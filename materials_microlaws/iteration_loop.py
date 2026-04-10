"""
Iterative Refinement Loop
==========================
The main generative loop that refines both the descriptor set and symbolic
templates using feedback from fit quality, OOD generalization, and constraint
violation reports.

This is the "exponentially iterated generative framework" described in the
problem statement. Each iteration:
  1. Representation learning → extract/refine descriptors
  2. Symbolic regression → propose candidate formulas
  3. Constraint filtering → prune physically invalid candidates
  4. Evaluation → measure fit quality and OOD generalization
  5. Feedback → update descriptor set, templates, and constraints
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from .constraints import ConstraintEngine
from .data_loader import MaterialsDataset
from .evaluation import (
    EvaluationResult,
    IterationLog,
    compare_methods,
    evaluate_formula,
)
from .representation import LearnedFeatures, learn_representations
from .symbolic_regression import (
    CandidateFormula,
    builtin_symbolic_search,
    fit_all_templates,
    run_pysr,
)
from .theory import (
    NumericalPrediction,
    SearchSpaceReductionTheorem,
    SpuriousLawBound,
    analyze_convergence,
)


@dataclass
class IterationConfig:
    """Configuration for a single iteration of the refinement loop."""
    # Representation learning
    repr_method: str = "pca"        # "autoencoder" or "pca"
    latent_dim: int = 8
    repr_epochs: int = 200

    # Symbolic regression
    sr_method: str = "builtin"      # "pysr" or "builtin"
    max_complexity: int = 20
    max_terms: int = 3
    sr_iterations: int = 40
    top_k: int = 50

    # Feature selection
    importance_threshold: float = 0.03   # drop descriptors below this
    max_descriptors: int = 12

    # Templates
    use_templates: bool = True
    evolve_templates: bool = True


@dataclass
class RefinementState:
    """Mutable state tracked across iterations."""
    active_descriptors: list[str] = field(default_factory=list)
    active_indices: list[int] = field(default_factory=list)
    best_formulas: list[CandidateFormula] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    iteration_metrics: list[dict] = field(default_factory=list)
    descriptor_history: list[list[str]] = field(default_factory=list)
    cumulative_reduction: float = 1.0


def run_refinement_loop(
    dataset: MaterialsDataset,
    n_iterations: int = 5,
    config: Optional[IterationConfig] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Execute the full iterative refinement loop.

    Parameters
    ----------
    dataset : MaterialsDataset with descriptors and targets
    n_iterations : number of self-improvement iterations
    config : iteration configuration
    output_dir : directory to save results

    Returns
    -------
    dict with keys: "best_formula", "all_formulas", "iteration_log",
                    "convergence", "predictions_evaluation", "theory_results"
    """
    if config is None:
        config = IterationConfig()

    logger.info("=" * 70)
    logger.info("STARTING ITERATIVE REFINEMENT LOOP")
    logger.info(f"  Dataset: {dataset.name} ({dataset.n_samples} samples, "
                f"{dataset.n_descriptors} descriptors)")
    logger.info(f"  Target: {dataset.target_name} ({dataset.target_unit})")
    logger.info(f"  Iterations: {n_iterations}")
    logger.info("=" * 70)

    # Split data
    train_data, test_data = dataset.train_test_split(test_frac=0.2)
    logger.info(f"  Train: {train_data.n_samples}, Test: {test_data.n_samples}")

    # Initialize state
    state = RefinementState(
        active_descriptors=[d.name for d in dataset.descriptors],
        active_indices=list(range(dataset.n_descriptors)),
    )

    # Initialize constraint engine
    constraint_engine = ConstraintEngine(
        dataset.descriptors, dataset.target_name, dataset.target_unit
    )

    # Initialize iteration log
    iter_log = IterationLog()

    # Run unconstrained baseline first
    logger.info("\n--- BASELINE: Unconstrained Symbolic Regression ---")
    baseline_candidates = _run_symbolic_regression(
        train_data.X, train_data.y, state.active_descriptors, config
    )
    baseline_eval = None
    if baseline_candidates:
        baseline_eval = evaluate_formula(
            baseline_candidates[0].expr, test_data.X, test_data.y,
            state.active_descriptors
        )
        logger.info(f"  Baseline MAE (test): {baseline_eval.mae:.4f} {dataset.target_unit}")
        logger.info(f"  Baseline R² (test):  {baseline_eval.r_squared:.4f}")
        logger.info(f"  Baseline formula:    {baseline_candidates[0].expr}")

    # -----------------------------------------------------------------------
    # Main iteration loop
    # -----------------------------------------------------------------------
    for iteration in range(1, n_iterations + 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"ITERATION {iteration}/{n_iterations}")
        logger.info(f"{'='*70}")
        t_start = time.time()

        # Step 1: Representation Learning
        logger.info(f"\n  [Step 1] Representation Learning ({config.repr_method})")
        X_active = train_data.X[:, state.active_indices]
        features = learn_representations(
            X_active, state.active_descriptors,
            method=config.repr_method,
            latent_dim=min(config.latent_dim, len(state.active_descriptors)),
            epochs=config.repr_epochs,
        )

        # Step 2: Feature Selection / Descriptor Refinement
        logger.info("\n  [Step 2] Descriptor Refinement")
        state = _refine_descriptors(state, features, config, iteration)

        # Recompute active X after descriptor pruning
        X_train_active = train_data.X[:, state.active_indices]
        X_test_active = test_data.X[:, state.active_indices]

        # Step 3: Symbolic Regression
        logger.info(f"\n  [Step 3] Symbolic Regression ({config.sr_method})")
        candidates = _run_symbolic_regression(
            X_train_active, train_data.y, state.active_descriptors, config
        )

        # Also fit templates
        if config.use_templates and state.templates:
            template_candidates = fit_all_templates(
                X_train_active, train_data.y, state.active_descriptors,
                templates=state.templates,
            )
            candidates.extend(template_candidates)

        n_before_filter = len(candidates)

        # Step 4: Constraint Filtering
        logger.info(f"\n  [Step 4] Constraint Filtering ({n_before_filter} candidates)")
        candidates, reports = constraint_engine.filter_candidates(
            candidates, X_train_active, state.active_descriptors
        )
        n_after_filter = len(candidates)

        reduction_info = constraint_engine.get_search_space_reduction(
            n_before_filter, n_after_filter
        )
        state.cumulative_reduction *= reduction_info["reduction_factor"]

        # Step 5: Evaluation on test set
        logger.info(f"\n  [Step 5] Evaluation ({n_after_filter} surviving candidates)")
        test_results = []
        for c in candidates:
            result = evaluate_formula(
                c.expr, X_test_active, test_data.y, state.active_descriptors
            )
            test_results.append((c, result))

        test_results.sort(key=lambda x: x[1].mae)

        # Update best formulas
        if test_results:
            best_c, best_r = test_results[0]
            best_c.iteration_found = iteration
            state.best_formulas.append(best_c)

            logger.info(f"  Best formula (iter {iteration}):")
            logger.info(f"    Expression: {best_c.expr}")
            logger.info(f"    MAE (test): {best_r.mae:.4f} {dataset.target_unit}")
            logger.info(f"    R² (test):  {best_r.r_squared:.4f}")
            logger.info(f"    Complexity: {best_r.complexity}")

            # Log metrics
            iter_log.log(
                iteration=iteration,
                best_mae=best_r.mae,
                best_r2=best_r.r_squared,
                best_complexity=best_r.complexity,
                n_candidates=n_before_filter,
                n_surviving=n_after_filter,
                reduction_factor=reduction_info["reduction_factor"],
                n_descriptors=len(state.active_descriptors),
                elapsed_s=time.time() - t_start,
            )
            state.iteration_metrics.append({
                "iteration": iteration,
                "best_mae": best_r.mae,
                "n_candidates": n_before_filter,
                "n_surviving": n_after_filter,
                "search_space_log10": np.log10(max(n_before_filter, 1)),
            })
        else:
            logger.warning(f"  No valid candidates survived iteration {iteration}")
            iter_log.log(
                iteration=iteration,
                best_mae=float("inf"),
                best_r2=0.0,
                best_complexity=0,
                n_candidates=n_before_filter,
                n_surviving=0,
            )

        # Step 6: Feedback → evolve templates and constraint rules
        logger.info(f"\n  [Step 6] Feedback & Template Evolution")
        if config.evolve_templates and test_results:
            state.templates = _evolve_templates(
                state, test_results, state.active_descriptors
            )

        # Tighten complexity constraint over iterations
        new_max = max(config.max_complexity - iteration * 2, 8)
        constraint_engine.update_rules({"max_complexity": new_max})

        elapsed = time.time() - t_start
        logger.info(f"\n  Iteration {iteration} complete ({elapsed:.1f}s)")

    # -----------------------------------------------------------------------
    # Final Analysis
    # -----------------------------------------------------------------------
    logger.info("\n" + "=" * 70)
    logger.info("REFINEMENT LOOP COMPLETE")
    logger.info("=" * 70)

    # Print iteration summary
    logger.info("\n" + iter_log.summary())

    # Find overall best formula
    all_best = state.best_formulas
    if all_best:
        all_best.sort(key=lambda c: c.mae)
        overall_best = all_best[0]
        logger.info(f"\n  OVERALL BEST FORMULA:")
        logger.info(f"    {overall_best.expr}")
        logger.info(f"    MAE: {overall_best.mae:.4f} {dataset.target_unit}")
        logger.info(f"    Found in iteration: {overall_best.iteration_found}")
    else:
        overall_best = None

    # Convergence analysis
    convergence = analyze_convergence(state.iteration_metrics)
    logger.info(f"\n  Convergence rate λ: {convergence.get('convergence_rate_lambda', 0):.4f}")
    logger.info(f"  MAE improvement: {convergence.get('mae_improvement', 0)*100:.1f}%")
    logger.info(f"  Cumulative reduction: {state.cumulative_reduction:.1f}×")

    # Theory results
    theorem1 = SearchSpaceReductionTheorem(
        D=dataset.n_descriptors, C_max=config.max_complexity
    )
    theorem1.print_theorem()

    theorem2 = SpuriousLawBound(
        sigma=dataset.metadata.get("noise_std", 0.1),
        log_S_phi=np.log10(max(theorem1.constrained_space_size(), 1)),
    )
    theorem2.print_theorem()

    # Numerical predictions evaluation
    predictions = NumericalPrediction(K_iterations=n_iterations)
    predictions.print_predictions()

    pred_eval = None
    if overall_best and baseline_eval:
        best_test_eval = evaluate_formula(
            overall_best.expr,
            test_data.X[:, state.active_indices] if state.active_indices else test_data.X,
            test_data.y,
            state.active_descriptors,
        )
        n_total_space = int(theorem1.unconstrained_space_size())
        n_evaluated = sum(m.get("n_candidates", 0) for m in state.iteration_metrics)

        logger.info("\n  PREDICTION EVALUATION:")
        pred_eval = predictions.evaluate(
            constrained_mae=best_test_eval.mae,
            unconstrained_mae=baseline_eval.mae,
            best_complexity=best_test_eval.complexity,
            n_evaluated=n_evaluated,
            n_total_space=n_total_space,
        )

    # Save results
    results = {
        "best_formula": str(overall_best.expr) if overall_best else None,
        "best_mae": overall_best.mae if overall_best else None,
        "all_formulas": [(str(c.expr), c.mae, c.r_squared) for c in all_best],
        "iteration_log": iter_log.entries,
        "convergence": convergence,
        "predictions_evaluation": pred_eval,
        "theory": {
            "theorem1": theorem1.summary(),
            "cumulative_reduction": state.cumulative_reduction,
        },
        "descriptor_history": state.descriptor_history,
    }

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        # Convert numpy types to native Python for JSON serialization
        with open(out_path / "results.json", "w") as f:
            json.dump(_make_serializable(results), f, indent=2)
        logger.info(f"\n  Results saved to {out_path / 'results.json'}")

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_symbolic_regression(
    X: np.ndarray,
    y: np.ndarray,
    variable_names: list[str],
    config: IterationConfig,
) -> list[CandidateFormula]:
    """Run symbolic regression with given config."""
    if config.sr_method == "pysr":
        return run_pysr(
            X, y, variable_names,
            max_complexity=config.max_complexity,
            niterations=config.sr_iterations,
            populations=30,
        )
    else:
        return builtin_symbolic_search(
            X, y, variable_names,
            max_complexity=config.max_complexity,
            max_terms=config.max_terms,
            top_k=config.top_k,
        )


def _refine_descriptors(
    state: RefinementState,
    features: LearnedFeatures,
    config: IterationConfig,
    iteration: int,
) -> RefinementState:
    """Refine the active descriptor set based on importance scores."""
    if features.importance_scores is None:
        return state

    importance = features.importance_scores
    names = features.descriptor_names

    # Rank by importance
    ranked = sorted(zip(names, importance), key=lambda x: -x[1])
    logger.info(f"    Descriptor importance ranking:")
    for name, imp in ranked[:8]:
        logger.info(f"      {name}: {imp:.4f}")

    # Prune low-importance descriptors (but keep at least 4)
    threshold = config.importance_threshold
    # Increase threshold over iterations
    adaptive_threshold = threshold * (1 + 0.2 * (iteration - 1))

    new_descriptors = []
    new_indices = []

    for name, imp in ranked:
        if imp >= adaptive_threshold or len(new_descriptors) < 4:
            if name in state.active_descriptors:
                idx_in_active = state.active_descriptors.index(name)
                original_idx = state.active_indices[idx_in_active]
                new_descriptors.append(name)
                new_indices.append(original_idx)

    # Limit to max_descriptors
    new_descriptors = new_descriptors[:config.max_descriptors]
    new_indices = new_indices[:config.max_descriptors]

    n_dropped = len(state.active_descriptors) - len(new_descriptors)
    if n_dropped > 0:
        logger.info(f"    Dropped {n_dropped} descriptors "
                    f"(threshold={adaptive_threshold:.4f})")
        logger.info(f"    Active descriptors: {new_descriptors}")

    state.active_descriptors = new_descriptors
    state.active_indices = new_indices
    state.descriptor_history.append(new_descriptors.copy())

    return state


def _evolve_templates(
    state: RefinementState,
    test_results: list[tuple[CandidateFormula, EvaluationResult]],
    active_descriptors: list[str],
) -> list[str]:
    """
    Evolve symbolic templates based on best-performing formulas.

    Strategy: Extract structural patterns from top formulas and
    create new templates by combining / mutating successful patterns.
    """
    from sympy import symbols as sym_symbols

    new_templates = list(state.templates) if state.templates else []

    # Extract patterns from top-3 formulas
    top_formulas = test_results[:3]
    for c, r in top_formulas:
        expr = c.expr
        # Create a generalized template by replacing constants with parameters
        template = _generalize_expression(expr, active_descriptors)
        if template and template not in new_templates:
            new_templates.append(template)

    # Generate cross-term templates from pairs of good descriptors
    if len(active_descriptors) >= 2:
        for i in range(min(3, len(active_descriptors))):
            for j in range(i + 1, min(4, len(active_descriptors))):
                d1, d2 = active_descriptors[i], active_descriptors[j]
                t = f"a * {d1} + b * {d2} + c"
                if t not in new_templates:
                    new_templates.append(t)
                t2 = f"a * {d1} / {d2} + b"
                if t2 not in new_templates:
                    new_templates.append(t2)

    logger.info(f"    Evolved templates: {len(new_templates)} total")
    return new_templates[:30]  # Cap at 30 templates


def _generalize_expression(expr, descriptor_names: list[str]) -> Optional[str]:
    """Convert a fitted expression into a template with free coefficients."""
    from sympy import Float, Rational, Number
    s = str(expr)
    # Replace floating point numbers with coefficient placeholders
    import re
    coeff_counter = [0]
    coeff_chars = "abcdefghij"

    def replacer(match):
        idx = coeff_counter[0] % len(coeff_chars)
        coeff_counter[0] += 1
        return coeff_chars[idx]

    template = re.sub(r'-?\d+\.\d+', replacer, s)

    # Verify template still contains descriptor variables
    has_var = any(d in template for d in descriptor_names)
    return template if has_var else None


def _make_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, tuple):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return str(obj)
    return obj
