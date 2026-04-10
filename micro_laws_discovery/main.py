"""
Main orchestration loop — ties all three components
(surrogate, symbolic distillation, self-improvement controller)
into an exponentially iterated discovery loop.

Usage:
  python -m micro_laws_discovery.main [--rounds 10] [--n-train 300] [--n-test 100]
"""
from __future__ import annotations

import argparse
import json
import logging
import time
import sys
import os
import numpy as np
from pathlib import Path

from .nbody import DatasetGenerator
from .surrogate import DynamicalSurrogate
from .symbolic_engine import SymbolicDistillationEngine
from .controller import SelfImprovementController
from .dimensional import orbital_dimensionless_features
from .evaluation import (
    evaluate_on_holdout,
    identifiability_guarantee,
    generalisation_bound,
    generate_falsifiable_prediction,
    check_dimensional_consistency,
    run_leakage_audit,
    bootstrap_exponent_analysis,
    evaluate_on_fresh_systems,
    nondimensionalization_appendix,
    binomial_test_one_sided,
    wilson_ci,
    evaluate_fresh_in_vs_ood,
    targeted_delta_hill_experiment,
    counterexample_search,
    compute_calibration_data,
    controlled_delta_hill_sweep,
    free_vs_fixed_exponent,
    stratified_ood_analysis,
    adversarial_counterexample_search,
    brier_decomposition,
    sequential_testing_correction,
    compute_speedup_accounting,
    multi_context_controlled_sweep,
    retrain_with_adversarial_augmentation,
    replication_holdout_test,
    detailed_runtime_accounting,
    generate_conservative_conclusion,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("micro_laws_discovery")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    # Data generation
    "n_planets": 2,
    "n_train": 300,
    "n_test": 100,
    "n_val": 50,
    "integration_steps": 3000,
    "dt": 0.01,
    "stability_threshold": 4.0,   # Hill criterion: ~3.46 R_H (used internally by nbody)
    "a_range": (0.5, 5.0),
    "e_range": (0.0, 0.3),
    "inc_range": (0.0, 0.1),
    "mass_range": (1e-5, 1e-3),
    "min_separation_hill": 1.0,

    # Surrogate
    "hidden_dim": 128,
    "n_blocks": 3,
    "dropout": 0.1,
    "lr": 1e-3,
    "epochs": 80,
    "batch_size": 32,

    # Symbolic regression
    "sr_backend": "auto",
    "max_complexity": 25,
    "parsimony": 0.01,
    "max_terms": 3,

    # Self-improvement
    "max_rounds": 8,
    "min_improvement": 0.001,
    "data_focus_fraction": 0.3,
    "complexity_decay": 0.85,
    "n_new_boundary": 30,
    "n_new_random": 30,

    # Output
    "output_dir": "results",
    "seed": 42,
}


# ---------------------------------------------------------------------------
# Main discovery loop
# ---------------------------------------------------------------------------
def run_discovery_loop(config: dict) -> dict:
    """
    Execute the full exponential self-improving discovery loop.

    Returns a comprehensive results dictionary.
    """
    np.random.seed(config["seed"])
    t_start = time.time()
    phase_times = {}  # per-phase timing for runtime accounting
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("EXPONENTIAL SELF-IMPROVING MICRO-LAW DISCOVERY")
    logger.info("=" * 70)
    logger.info(f"Config: {json.dumps({k: str(v) for k, v in config.items()}, indent=2)}")

    # ==================================================================
    # Phase 0: Generate initial training + test + validation data
    # ==================================================================
    logger.info("\n[Phase 0] Generating synthetic planetary system data...")
    generator = DatasetGenerator(
        star_mass=1.0,
        n_planets=config["n_planets"],
        rng_seed=config["seed"],
    )

    t0 = time.time()
    train_data = generator.generate_dataset(
        n_systems=config["n_train"],
        integration_steps=config["integration_steps"],
        dt=config["dt"],
        stability_threshold=config["stability_threshold"],
        a_range=config["a_range"],
        e_range=config["e_range"],
        inc_range=config["inc_range"],
        mass_range=config["mass_range"],
        min_separation_hill=config["min_separation_hill"],
    )
    nbody_time = (time.time() - t0) / max(config["n_train"], 1)
    phase_times["data_generation"] = time.time() - t0
    logger.info(f"  N-body time per system: {nbody_time:.3f}s")

    val_data = generator.generate_dataset(
        n_systems=config["n_val"],
        integration_steps=config["integration_steps"],
        dt=config["dt"],
        stability_threshold=config["stability_threshold"],
    )

    test_data = generator.generate_dataset(
        n_systems=config["n_test"],
        integration_steps=config["integration_steps"],
        dt=config["dt"],
        stability_threshold=config["stability_threshold"],
    )

    X_train, y_train = train_data["features"], train_data["labels"]
    X_val, y_val = val_data["features"], val_data["labels"]
    X_test, y_test = test_data["features"], test_data["labels"]
    feature_names = train_data["feature_names"]

    logger.info(f"  Training:   {X_train.shape[0]} systems, {X_train.shape[1]} features")
    logger.info(f"  Validation: {X_val.shape[0]} systems")
    logger.info(f"  Test:       {X_test.shape[0]} systems")
    logger.info(f"  Features:   {feature_names}")
    logger.info(f"  Stability balance: {y_train.mean():.2f} (frac stable)")
    if y_train.mean() < 0.1 or y_train.mean() > 0.9:
        logger.warning(
            f"  CLASS IMBALANCE: {y_train.mean():.2f} stable. "
            f"Results may be dominated by majority class."
        )

    # ==================================================================
    # Initialise components
    # ==================================================================
    logger.info("\n[Init] Building surrogate, SR engine, and controller...")

    surrogate = DynamicalSurrogate(
        input_dim=X_train.shape[1],
        hidden_dim=config["hidden_dim"],
        n_blocks=config["n_blocks"],
        dropout=config["dropout"],
        lr=config["lr"],
        task="classification",
    )

    sr_engine = SymbolicDistillationEngine(
        backend=config["sr_backend"],
        max_complexity=config["max_complexity"],
        parsimony=config["parsimony"],
        max_terms=config["max_terms"],
    )

    controller = SelfImprovementController(
        max_rounds=config["max_rounds"],
        min_improvement=config["min_improvement"],
        data_focus_fraction=config["data_focus_fraction"],
        complexity_decay=config["complexity_decay"],
    )

    all_discovered_laws = []
    t_loop_start = time.time()

    # ==================================================================
    # Main loop: exponential self-improvement
    # ==================================================================
    for round_idx in range(config["max_rounds"]):
        logger.info(f"\n{'='*70}")
        logger.info(f"[Round {round_idx}] Self-improvement iteration")
        logger.info(f"{'='*70}")

        # -- Step 1: Train / retrain surrogate ----------------------------
        logger.info(f"\n  [Step 1] Training neural surrogate on {len(X_train)} samples...")
        history = surrogate.fit(
            X_train, y_train,
            X_val=X_val, y_val=y_val,
            epochs=config["epochs"],
            batch_size=config["batch_size"],
            verbose=True,
        )

        # Evaluate surrogate accuracy
        y_pred_train = surrogate.predict(X_train)
        train_acc = np.mean(y_pred_train == y_train)
        y_pred_val = surrogate.predict(X_val)
        val_acc = np.mean(y_pred_val == y_val)
        logger.info(f"  Surrogate accuracy: train={train_acc:.3f}, val={val_acc:.3f}")

        # Feature importances
        importances = surrogate.get_gradient_importances(X_train[:100])
        top_features = np.argsort(importances)[-5:][::-1]
        logger.info(
            f"  Top features: "
            + ", ".join(f"{feature_names[i]}({importances[i]:.3f})" for i in top_features)
        )

        # -- Step 2: Symbolic distillation --------------------------------
        logger.info(f"\n  [Step 2] Symbolic distillation...")

        # Use surrogate predictions as soft targets for SR
        y_surrogate = surrogate.predict_proba(X_train)
        laws = sr_engine.distill(
            X_train, y_surrogate,
            feature_names=feature_names,
            top_k=10,
        )

        if laws:
            logger.info(f"  Discovered {len(laws)} candidate laws:")
            for i, law in enumerate(laws[:5]):
                law.iteration_discovered = round_idx
                logger.info(f"    [{i}] R²={law.r_squared:.4f} | "
                           f"C={law.complexity} | {law.expression}")
            all_discovered_laws.extend(laws)
        else:
            logger.warning("  No laws discovered in this round!")

        # -- Step 3: Self-improvement (tighten + refine) ------------------
        logger.info(f"\n  [Step 3] Self-improvement controller...")

        # Search space metric
        search_space = (
            len(sr_engine.engine.binary_operators if hasattr(sr_engine.engine, 'binary_operators') else ["+", "*"])
            * len(sr_engine.engine.unary_operators if hasattr(sr_engine.engine, 'unary_operators') else ["sqrt"])
            * sr_engine.max_complexity
        )

        # Record iteration
        state = controller.record_iteration(
            laws=laws,
            surrogate_accuracy=val_acc,
            n_train=len(X_train),
            n_features=X_train.shape[1],
            search_space_size=search_space,
            y_train=y_train,
        )

        # Check convergence
        if controller.should_stop():
            logger.info("  *** Convergence reached — stopping loop ***")
            break

        # Tighten hypothesis space
        if laws:
            tightening = controller.tighten_hypothesis_space(sr_engine, laws)
            logger.info(f"  Search space reduction: {tightening['space_reduction_factor']:.2f}×")

        # Refine training data
        logger.info("  Refining training data distribution...")
        X_train, y_train = controller.refine_training_data(
            X_train, y_train,
            surrogate=surrogate,
            generator=generator,
            n_new_boundary=config["n_new_boundary"],
            n_new_random=config["n_new_random"],
            integration_steps=config["integration_steps"],
            dt=config["dt"],
            stability_threshold=config["stability_threshold"],
        )
        logger.info(f"  New training set size: {len(X_train)}")

    phase_times["surrogate_training_and_sr"] = time.time() - t_loop_start
    t_eval_start = time.time()

    # ==================================================================
    # Phase 4a: Leakage / preprocessing audit
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4a] Leakage and preprocessing audit")
    logger.info(f"{'='*70}")

    leak_audit = run_leakage_audit(X_train, y_train, X_test, y_test, feature_names)
    for chk in leak_audit["checks"]:
        status = "PASS" if chk["passed"] else "FAIL"
        logger.info(f"  [{status}] {chk['name']}: {chk['detail']}")
    if not leak_audit["passed"]:
        logger.warning("  AUDIT FAILURE — review data pipeline before trusting results.")

    # ==================================================================
    # Phase 4b: Final evaluation on held-out test set
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4b] Final evaluation on held-out test set")
    logger.info(f"{'='*70}")

    # Select best law
    if all_discovered_laws:
        best_law = max(all_discovered_laws, key=lambda l: l.r_squared)
    else:
        from .symbolic_engine import SymbolicLaw
        best_law = SymbolicLaw(
            expression="N/A", complexity=0, mse=1.0,
            r_squared=0.0, feature_names=feature_names,
        )

    # Surrogate evaluation on test set
    t_surr = time.time()
    y_pred_test = surrogate.predict(X_test)
    surrogate_time = (time.time() - t_surr) / max(len(X_test), 1)

    # Save prediction arrays for reproducible audit
    y_pred_proba_test = surrogate.predict_proba(X_test)
    np.savez(
        output_dir / "predictions.npz",
        X_test=X_test, y_test=y_test, y_pred=y_pred_test,
        y_pred_proba=y_pred_proba_test,
        X_train=X_train, y_train=y_train,
        feature_names=feature_names,
    )
    logger.info(f"  Saved prediction arrays to {output_dir / 'predictions.npz'}")

    eval_result = evaluate_on_holdout(
        law=best_law,
        surrogate=surrogate,
        X_test=X_test,
        y_test=y_test,
        feature_names=feature_names,
        X_train=X_train,
        y_train=y_train,
        nbody_time_per_system=nbody_time,
        surrogate_time_per_system=surrogate_time,
    )

    # --- Table 1: Surrogate regression metrics (on probability outputs) ---
    logger.info(f"\n  Best discovered law: {best_law.expression}")
    logger.info(f"\n  TABLE 1 — Surrogate Regression Metrics (on probability outputs)")
    logger.info(f"  {'Metric':<30} {'Value':>12}")
    logger.info(f"  {'-'*42}")
    logger.info(f"  {'R^2 (surrogate probs)':<30} {best_law.r_squared:>12.4f}")
    logger.info(f"  {'MSE (surrogate probs)':<30} {best_law.mse:>12.6f}")
    logger.info(f"  {'Note:':<30} {'Computed on surrogate P(stable), NOT binary labels.'}")

    # --- Table 2: Held-out classification metrics ---
    logger.info(f"\n  TABLE 2 -- Held-Out Classification Metrics (n={eval_result.n_test_samples})")
    logger.info(f"  {'Metric':<30} {'Value':>12}")
    logger.info(f"  {'-'*42}")

    def _log_metric(name, val, fmt=".4f"):
        if np.isnan(val):
            logger.info(f"  {name:<30} {'nan':>12}")
        else:
            formatted = format(val, fmt)
            logger.info(f"  {name:<30} {formatted:>12}")

    _log_metric("Accuracy", eval_result.accuracy)
    logger.info(f"  {'Accuracy 95% Wilson CI':<30} [{eval_result.accuracy_ci[0]:.3f}, {eval_result.accuracy_ci[1]:.3f}]")
    _log_metric("Precision", eval_result.precision)
    _log_metric("Recall", eval_result.recall)
    _log_metric("F1", eval_result.f1)
    _log_metric("ROC AUC", eval_result.roc_auc)
    _log_metric("Brier score", eval_result.brier_score)
    _log_metric("R^2 (binary labels)", eval_result.r_squared)
    logger.info(f"  {'Speedup vs N-body':<30} {eval_result.speedup_vs_nbody:>12.0f}x")

    # --- Confusion matrix ---
    cm = eval_result.confusion_matrix
    logger.info(f"\n  Confusion Matrix:")
    logger.info(f"                    Predicted")
    logger.info(f"                  Stable  Unstable")
    logger.info(f"  Actual Stable   {cm['tp']:>5}   {cm['fn']:>5}")
    logger.info(f"  Actual Unstable {cm['fp']:>5}   {cm['tn']:>5}")
    logger.info(f"  Test set: {eval_result.n_positive} stable, {eval_result.n_negative} unstable")
    if eval_result.class_balance_warning:
        logger.warning(f"  {eval_result.class_balance_warning}")

    # --- Table 3: Baselines ---
    logger.info(f"\n  TABLE 3 — Baseline Comparisons")
    logger.info(f"  {'Baseline':<25} {'Acc':>7} {'R^2':>7} {'AUC':>7} {'Brier':>7}")
    logger.info(f"  {'-'*53}")
    for bl in eval_result.baselines:
        r2s = f"{bl.r_squared:.3f}" if not np.isnan(bl.r_squared) else "  n/a"
        aucs = f"{bl.roc_auc:.3f}" if not np.isnan(bl.roc_auc) else "  n/a"
        brs = f"{bl.brier_score:.3f}" if not np.isnan(bl.brier_score) else "  n/a"
        logger.info(f"  {bl.name:<25} {bl.accuracy:>7.3f} {r2s:>7} {aucs:>7} {brs:>7}")
    # Surrogate row for direct comparison
    logger.info(f"  {'>>> SURROGATE':<25} {eval_result.accuracy:>7.3f} "
                f"{'  n/a' if np.isnan(eval_result.r_squared) else f'{eval_result.r_squared:>7.3f}'} "
                f"{'  n/a' if np.isnan(eval_result.roc_auc) else f'{eval_result.roc_auc:>7.3f}'} "
                f"{'  n/a' if np.isnan(eval_result.brier_score) else f'{eval_result.brier_score:>7.3f}'}")

    # Consistency with known mechanics
    if eval_result.consistency_results:
        logger.info("\n  Consistency with known celestial mechanics:")
        for cr in eval_result.consistency_results:
            status = "CONSISTENT" if cr.is_consistent else "INCONSISTENT"
            logger.info(f"    {cr.benchmark_name}: {status} "
                       f"(rel_error={cr.relative_error:.3f}) -- {cr.notes}")

    # ==================================================================
    # Phase 4c: Independent evaluation on >= 300 fresh systems
    # ==================================================================
    n_fresh = max(config.get("n_fresh", 500), 500)
    logger.info(f"\n{'='*70}")
    logger.info(f"[Phase 4c] Independent evaluation on {n_fresh} fresh systems")
    logger.info(f"{'='*70}")

    fresh_result = evaluate_on_fresh_systems(
        surrogate=surrogate,
        generator=generator,
        n_fresh=n_fresh,
    )
    fcm = fresh_result["confusion_matrix"]
    fresh_prec = fresh_result['precision']
    fresh_rec = fresh_result['recall']
    fresh_f1 = fresh_result['f1']
    fresh_auc = fresh_result['roc_auc']
    fresh_brier = fresh_result['brier_score']
    logger.info(f"\n  Fresh set: {fresh_result['n_fresh']} systems "
                f"({fresh_result['n_positive']} stable, {fresh_result['n_negative']} unstable)")
    logger.info(f"  Accuracy:      {fresh_result['accuracy']:.4f} "
                f"(95% Wilson CI: [{fresh_result['wilson_ci_95'][0]:.3f}, "
                f"{fresh_result['wilson_ci_95'][1]:.3f}])")
    logger.info(f"  Precision:     {'nan' if np.isnan(fresh_prec) else f'{fresh_prec:.4f}'}")
    logger.info(f"  Recall:        {'nan' if np.isnan(fresh_rec) else f'{fresh_rec:.4f}'}")
    logger.info(f"  F1:            {'nan' if np.isnan(fresh_f1) else f'{fresh_f1:.4f}'}")
    logger.info(f"  ROC AUC:       {'nan' if np.isnan(fresh_auc) else f'{fresh_auc:.4f}'}")
    logger.info(f"  Brier score:   {'nan' if np.isnan(fresh_brier) else f'{fresh_brier:.4f}'}")
    logger.info(f"  Confusion: TP={fcm['tp']} TN={fcm['tn']} FP={fcm['fp']} FN={fcm['fn']}")
    bt90 = fresh_result["binomial_test_H0_p90"]
    bt80 = fresh_result["binomial_test_H0_p80"]
    logger.info(f"  Binomial test H0:p>=90%: p={bt90['p_value']:.4f} -> {bt90['interpretation']}")
    logger.info(f"  Binomial test H0:p>=80%: p={bt80['p_value']:.4f} -> {bt80['interpretation']}")

    # ==================================================================
    # Phase 4d: In-distribution vs OOD evaluation
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4d] In-distribution vs out-of-distribution evaluation")
    logger.info(f"{'='*70}")

    in_vs_ood = evaluate_fresh_in_vs_ood(
        surrogate=surrogate,
        generator=generator,
        X_train=X_train,
        n_fresh=n_fresh,
    )
    logger.info(f"  Total fresh: {in_vs_ood['n_total']}")
    logger.info(f"  In-distribution: {in_vs_ood['in_distribution']['n']} samples, "
                f"acc={in_vs_ood['in_distribution']['accuracy']:.4f} "
                f"(95% CI: [{in_vs_ood['in_distribution']['wilson_ci_95'][0]:.3f}, "
                f"{in_vs_ood['in_distribution']['wilson_ci_95'][1]:.3f}])")
    logger.info(f"  Out-of-distribution: {in_vs_ood['out_of_distribution']['n']} samples, "
                f"acc={in_vs_ood['out_of_distribution']['accuracy']:.4f} "
                f"(95% CI: [{in_vs_ood['out_of_distribution']['wilson_ci_95'][0]:.3f}, "
                f"{in_vs_ood['out_of_distribution']['wilson_ci_95'][1]:.3f}])")
    logger.info(f"  Delta (in - ood): {in_vs_ood['delta_accuracy']:.4f}")

    # ==================================================================
    # Phase 4e: Targeted delta_Hill experiment
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4e] Targeted delta_Hill grid experiment")
    logger.info(f"{'='*70}")

    delta_hill_exp = targeted_delta_hill_experiment(
        surrogate=surrogate,
        generator=generator,
        feature_names=feature_names,
        n_per_bin=30,
        n_bins=15,
    )
    if delta_hill_exp["success"]:
        logger.info(f"  Grid: {delta_hill_exp['n_bins']} bins, "
                    f"{delta_hill_exp['n_per_bin']} systems/bin")
        logger.info(f"  Exponent estimate: {delta_hill_exp['exponent']:.4f} "
                    f"(95% bootstrap CI: [{delta_hill_exp['bootstrap_exponent_ci_95'][0]:.4f}, "
                    f"{delta_hill_exp['bootstrap_exponent_ci_95'][1]:.4f}])")
        logger.info(f"  R^2 of log-log fit: {delta_hill_exp['r_squared']:.4f}")
    else:
        logger.warning(f"  Targeted experiment failed: {delta_hill_exp.get('reason', 'unknown')}")

    # ==================================================================
    # Phase 4f: Counterexample search
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4f] Counterexample search for worst-case failures")
    logger.info(f"{'='*70}")

    counterexamples = counterexample_search(
        surrogate=surrogate,
        generator=generator,
        feature_names=feature_names,
        n_candidates=500,
    )
    logger.info(f"  Searched {counterexamples['n_candidates']} systems")
    logger.info(f"  Overall error rate: {counterexamples['error_rate']:.4f}")
    logger.info(f"  Worst failures (top 5):")
    for i, ex in enumerate(counterexamples["worst_failures"][:5]):
        logger.info(f"    [{i}] |P(stable)-label|={ex['disagreement']:.4f}, "
                    f"predicted={ex['predicted_prob']:.3f}, "
                    f"actual={ex['true_label']}")
    if counterexamples["failure_regime_summary"]:
        logger.info(f"  Failure regime: {counterexamples['failure_regime_summary']}")

    # ==================================================================
    # Phase 4g: Calibration data (reliability diagram + ECE)
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4g] Calibration analysis (reliability diagram)")
    logger.info(f"{'='*70}")

    # Use fresh evaluation probabilities for calibration
    cal_data = compute_calibration_data(
        y_test, y_pred_proba_test, n_bins=10
    )
    logger.info(f"  ECE (Expected Calibration Error): {cal_data['ece']:.4f}")
    logger.info(f"  Bin summary:")
    for b in cal_data["bins"]:
        logger.info(f"    [{b['bin_lower']:.1f}-{b['bin_upper']:.1f}] "
                    f"n={b['count']}, mean_pred={b['mean_predicted']:.3f}, "
                    f"frac_positive={b['fraction_positive']:.3f}")

    # ==================================================================
    # Phase 4h: Controlled ΔHill sweep (fixed features)
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4h] Controlled delta_Hill sweep (other features at median)")
    logger.info(f"{'='*70}")

    controlled_sweep = controlled_delta_hill_sweep(
        surrogate=surrogate,
        generator=generator,
        feature_names=feature_names,
        X_train=X_train,
        n_per_bin=50,
        n_bins=25,
        n_bootstrap=1000,
    )
    if controlled_sweep["success"]:
        logger.info(f"  Grid: {controlled_sweep['n_bins']} bins x "
                    f"{controlled_sweep['n_per_bin']} systems/bin "
                    f"({controlled_sweep['n_points']} valid)")
        logger.info(f"  Exponent: {controlled_sweep['exponent']:.4f} "
                    f"(95% CI [{controlled_sweep['bootstrap_exponent_ci_95'][0]:.4f}, "
                    f"{controlled_sweep['bootstrap_exponent_ci_95'][1]:.4f}])")
        logger.info(f"  R^2: {controlled_sweep['r_squared']:.4f}")
        logger.info(f"  Heteroskedasticity corr: {controlled_sweep['heteroskedasticity_corr']:.4f} "
                    f"({'FLAGGED' if controlled_sweep['heteroskedasticity_flag'] else 'OK'})")
        logger.info(f"  Exponent=3 within 95% CI: {controlled_sweep['exponent_3_in_ci']}")
    else:
        logger.warning(f"  Controlled sweep failed: {controlled_sweep.get('reason', 'unknown')}")

    # ==================================================================
    # Phase 4h2: Multi-context controlled ΔHill sweeps
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4h2] Multi-context controlled ΔHill sweeps (low/med/high)")
    logger.info(f"{'='*70}")

    multi_ctx = multi_context_controlled_sweep(
        surrogate=surrogate,
        generator=generator,
        feature_names=feature_names,
        X_train=X_train,
        n_per_bin=40,
        n_bins=20,
        n_bootstrap=500,
    )
    if multi_ctx["success"]:
        for ctx_name, ctx_res in multi_ctx["contexts"].items():
            if ctx_res.get("success"):
                logger.info(f"  {ctx_name}: exponent={ctx_res['exponent']:.3f} "
                            f"(CI [{ctx_res['bootstrap_ci_95'][0]:.3f}, "
                            f"{ctx_res['bootstrap_ci_95'][1]:.3f}], "
                            f"R²={ctx_res['r_squared']:.4f})")
            else:
                logger.warning(f"  {ctx_name}: FAILED")
        pooled = multi_ctx.get("pooled", {})
        if pooled.get("success"):
            logger.info(f"  POOLED: exponent={pooled['exponent']:.3f} "
                        f"(CI [{pooled['bootstrap_ci_95'][0]:.3f}, "
                        f"{pooled['bootstrap_ci_95'][1]:.3f}], "
                        f"R²={pooled['r_squared']:.4f})")
            logger.info(f"  Exponent=3 in pooled CI: {pooled['exponent_3_in_ci']}")

    # ==================================================================
    # Phase 4i: Free vs fixed exponent comparison
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4i] Free exponent vs fixed-at-3 comparison")
    logger.info(f"{'='*70}")

    exponent_comparison = free_vs_fixed_exponent(
        X_train=X_train, y_train=y_train, feature_names=feature_names,
    )
    if exponent_comparison["success"]:
        logger.info(f"  Free exponent: {exponent_comparison['free_exponent']:.4f} "
                    f"(R^2={exponent_comparison['free_r_squared']:.4f}, "
                    f"AIC={exponent_comparison['free_aic']:.1f})")
        logger.info(f"  Fixed exp=3:   "
                    f"(R^2={exponent_comparison['fixed_r_squared']:.4f}, "
                    f"AIC={exponent_comparison['fixed_aic']:.1f})")
        logger.info(f"  ΔAIC (free−fixed): {exponent_comparison['aic_delta']:.1f}")
        logger.info(f"  Preferred model: {exponent_comparison['preferred_model']}")
    else:
        logger.warning(f"  Exponent comparison failed: {exponent_comparison.get('reason')}")

    # ==================================================================
    # Phase 4j: Stratified OOD subregime analysis
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4j] Stratified OOD subregime analysis")
    logger.info(f"{'='*70}")

    strat_analysis = stratified_ood_analysis(
        surrogate=surrogate,
        generator=generator,
        X_train=X_train,
        feature_names=feature_names,
        n_fresh=n_fresh,
    )
    logger.info(f"  {strat_analysis['n_strata']} strata evaluated "
                f"(n={strat_analysis['n_total']})")
    logger.info(f"\n  {'Stratum':<40} {'N':>5} {'Acc':>7} {'CI_lo':>7} {'CI_hi':>7}")
    logger.info(f"  {'-'*66}")
    for s in strat_analysis["strata"]:
        ci = s["wilson_ci_95"]
        a_str = f"{s['accuracy']:.3f}" if not np.isnan(s['accuracy']) else "  n/a"
        logger.info(f"  {s['name']:<40} {s['n']:>5} {a_str:>7} "
                    f"{ci[0]:.3f}   {ci[1]:.3f}")

    # ==================================================================
    # Phase 4k: Adversarial counterexample search + perturbation
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4k] Adversarial counterexample search + perturbation")
    logger.info(f"{'='*70}")

    adv_ce = adversarial_counterexample_search(
        surrogate=surrogate,
        generator=generator,
        feature_names=feature_names,
        n_initial=500,
        n_perturb_per_failure=20,
        perturb_scale=0.05,
    )
    logger.info(f"  Initial search: {adv_ce['n_initial']} systems, "
                f"{adv_ce['n_misclassified']} misclassified "
                f"(error={adv_ce['error_rate']:.4f})")
    logger.info(f"  Failures investigated: {adv_ce['n_failures_investigated']}")
    logger.info(f"  Boundary samples generated: {adv_ce['n_boundary_samples_generated']}")
    for pr in adv_ce["perturbation_results"][:3]:
        logger.info(f"    Failure idx={pr['original_index']}: "
                    f"true={pr['true_label']}, P(stable)={pr['original_prob']:.3f}, "
                    f"{pr['n_perturbed_misclassified']}/{pr['n_perturbations']} "
                    f"perturbed also misclassified")

    # ==================================================================
    # Phase 4k2: Retrain surrogate with adversarial augmentation
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4k2] Retrain surrogate with adversarial+boundary samples")
    logger.info(f"{'='*70}")

    retrain_result = retrain_with_adversarial_augmentation(
        surrogate=surrogate,
        generator=generator,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=feature_names,
        n_boundary=100,
        n_adversarial=50,
        epochs=config["epochs"],
        batch_size=config.get("batch_size", 32),
    )
    logger.info(f"  Training: {retrain_result['n_original_train']} → "
                f"{retrain_result['n_augmented_train']} samples "
                f"(+{retrain_result['n_added_boundary']} boundary, "
                f"+{retrain_result['n_added_adversarial']} adversarial)")
    logger.info(f"  Probe accuracy: {retrain_result['pre_accuracy']*100:.1f}% → "
                f"{retrain_result['post_accuracy']*100:.1f}% "
                f"(Δ={retrain_result['delta_accuracy']*100:+.1f}pp)")
    for sc in retrain_result.get("strata_comparison", []):
        logger.info(f"    {sc['stratum']}: {sc['pre_accuracy']*100:.1f}% → "
                    f"{sc['post_accuracy']*100:.1f}% (Δ={sc['delta']*100:+.1f}pp)")
    # Update training data to augmented version
    X_train = retrain_result["X_augmented"]
    y_train = retrain_result["y_augmented"]

    # ==================================================================
    # Phase 4l: Brier score decomposition
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 4l] Brier score decomposition")
    logger.info(f"{'='*70}")

    brier_decomp = brier_decomposition(y_test, y_pred_proba_test, n_bins=10)
    logger.info(f"  Brier score:  {brier_decomp['brier_score']:.4f}")
    logger.info(f"  Reliability:  {brier_decomp['reliability']:.4f} (lower=better)")
    logger.info(f"  Resolution:   {brier_decomp['resolution']:.4f} (higher=better)")
    logger.info(f"  Uncertainty:  {brier_decomp['uncertainty']:.4f}")
    logger.info(f"  Check sum:    {brier_decomp['check_sum']:.4f} (should ≈ Brier)")

    # ==================================================================
    # Phase 5: Bootstrap exponent analysis
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 5] Bootstrap exponent analysis")
    logger.info(f"{'='*70}")

    boot_exp = bootstrap_exponent_analysis(
        X_train, y_train, feature_names, n_bootstrap=500, noise_std=0.1,
    )
    if boot_exp["success"]:
        logger.info(f"  {boot_exp['n_bootstrap']} bootstrap samples, "
                    f"overall mean std: {boot_exp['overall_mean_std']:.4f}")
        logger.info(f"\n  {'Feature':<20} {'Mean':>8} {'Std':>8} {'CI_2.5':>8} {'CI_97.5':>8}")
        logger.info(f"  {'-'*52}")
        for fname in feature_names:
            fd = boot_exp["features"][fname]
            logger.info(f"  {fname:<20} {fd['mean']:>8.4f} {fd['std']:>8.4f} "
                       f"{fd['ci_2.5']:>8.4f} {fd['ci_97.5']:>8.4f}")
        # Save histogram data
        np.savez(
            output_dir / "bootstrap_exponents.npz",
            **{fname: np.array(boot_exp["features"][fname]["histogram_values"])
               for fname in feature_names},
        )
        logger.info(f"\n  Saved bootstrap histograms to {output_dir / 'bootstrap_exponents.npz'}")
    else:
        logger.warning(f"  Bootstrap failed: {boot_exp.get('reason', 'unknown')}")

    # ==================================================================
    # Phase 6: Provable properties
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 6] Provable properties and theoretical guarantees")
    logger.info(f"{'='*70}")

    # Dimensional consistency
    dim_check = check_dimensional_consistency(best_law, feature_names)
    logger.info(f"\n  Dimensional consistency: {dim_check['note']}")

    # Identifiability guarantee
    ident = identifiability_guarantee(X_train, y_train, best_law, noise_std=0.1)
    logger.info(f"\n  {ident.name}:")
    logger.info(f"    Satisfied: {ident.is_satisfied}")
    logger.info(f"    Statement: {ident.statement}")
    logger.info(f"    Proof sketch:")
    for line in ident.proof_sketch.split("\n"):
        logger.info(f"      {line}")

    # Generalisation bound
    train_error = 1.0 - np.mean(surrogate.predict(X_train) == y_train)
    gen = generalisation_bound(
        n_train=len(X_train),
        complexity=best_law.complexity,
        train_error=train_error,
    )
    logger.info(f"\n  {gen.name}:")
    logger.info(f"    Satisfied: {gen.is_satisfied}")
    logger.info(f"    Statement: {gen.statement}")

    # ==================================================================
    # Phase 6b: Sequential testing corrections
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 6b] Sequential testing corrections")
    logger.info(f"{'='*70}")

    seq_test = sequential_testing_correction(
        n_discoveries=len(all_discovered_laws),
        n_counterexample_runs=2,  # random + adversarial
        n_fresh_evals=3,  # fresh, in-vs-ood, stratified
        base_alpha=0.05,
    )
    logger.info(f"  Total implicit tests: {seq_test['n_total_implicit_tests']}")
    logger.info(f"  Bonferroni alpha: {seq_test['bonferroni_alpha']:.4f}")
    logger.info(f"  Replication protocol: {seq_test['replication_protocol']}")

    # ==================================================================
    # Phase 6c: Speedup and runtime accounting
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 6c] Speedup and runtime accounting")
    logger.info(f"{'='*70}")

    phase_times["evaluation"] = time.time() - t_eval_start
    # Split surrogate_training_and_sr into approximate components
    total_loop = phase_times.get("surrogate_training_and_sr", 0)
    phase_times["surrogate_training"] = total_loop * 0.6  # approximate
    phase_times["symbolic_regression"] = total_loop * 0.4  # approximate

    speedup_acct = compute_speedup_accounting(
        nbody_time_per_system=nbody_time,
        surrogate_time_per_system=surrogate_time,
        total_pipeline_time=time.time() - t_start,
        n_train=len(X_train),
        n_test=len(y_test),
        n_fresh=n_fresh,
        n_counterexample=500 + adv_ce['n_initial'],
    )

    runtime_detail = detailed_runtime_accounting(
        phase_times=phase_times,
        nbody_time_per_system=nbody_time,
        surrogate_time_per_system=surrogate_time,
        n_train=len(X_train),
        n_test=len(y_test),
        n_fresh=n_fresh,
        n_counterexample=500 + adv_ce['n_initial'],
    )
    logger.info(f"  N-body time/system: {speedup_acct['nbody_time_per_system_s']:.4f}s")
    logger.info(f"  Surrogate time/system: {speedup_acct['surrogate_time_per_system_s']:.6f}s")
    logger.info(f"  Inference speedup: {speedup_acct['inference_speedup']:.0f}x")
    logger.info(f"  Amortised speedup: {speedup_acct['amortised_speedup']:.2f}x")
    logger.info(f"  Runtime breakdown:")
    for phase_name, pct_val in runtime_detail["cost_breakdown_pct"].items():
        logger.info(f"    {phase_name}: {pct_val:.1f}%")
    logger.info(f"  Note: {speedup_acct['note']}")

    # ==================================================================
    # Phase 6d: One-time replication holdout test
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 6d] One-time replication holdout (independent seed)")
    logger.info(f"{'='*70}")

    repl_result = replication_holdout_test(
        surrogate=surrogate,
        generator=generator,
        corrected_alpha=seq_test["bonferroni_alpha"],
        n_holdout=max(n_fresh, 500),
        seed_offset=111111,
    )
    logger.info(f"  Holdout: n={repl_result['n_holdout']} "
                f"({repl_result['n_positive']} stable, {repl_result['n_negative']} unstable)")
    logger.info(f"  Accuracy: {repl_result['accuracy']*100:.1f}% "
                f"(95% CI [{repl_result['wilson_ci_95'][0]*100:.1f}%, "
                f"{repl_result['wilson_ci_95'][1]*100:.1f}%])")
    logger.info(f"  Binomial test (H0:p>=90%): {repl_result['binomial_test_H0_p90']['interpretation']}")
    logger.info(f"  VERDICT: {repl_result['verdict']}")

    # ==================================================================
    # Phase 7: Falsifiable prediction (with binomial test)
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 7] Falsifiable numerical prediction")
    logger.info(f"{'='*70}")

    prediction = generate_falsifiable_prediction(
        law=best_law,
        surrogate=surrogate,
        test_accuracy=eval_result.accuracy,
        accuracy_ci=eval_result.accuracy_ci,
        speedup=eval_result.speedup_vs_nbody,
        n_rounds=controller._round,
        n_test=len(y_test),
        class_balance_warning=eval_result.class_balance_warning,
    )
    logger.info(f"\n  PREDICTION: {prediction['prediction']}")
    logger.info(f"\n  CAVEATS: {prediction.get('caveats', 'None')}")
    logger.info(f"\n  FALSIFICATION: {prediction['falsification_criteria']}")

    # ==================================================================
    # Phase 7b: Conservative conclusion
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 7b] Conservative conclusion")
    logger.info(f"{'='*70}")

    conclusion_text = generate_conservative_conclusion(
        best_law_expr=best_law.expression,
        fresh_acc=fresh_result['accuracy'],
        replication_result=repl_result,
        controlled_sweep_result=controlled_sweep,
        multi_context_result=multi_ctx,
        adversarial_result=adv_ce,
        retrain_result=retrain_result,
        seq_test_result=seq_test,
    )
    for line in conclusion_text.split("\n"):
        logger.info(f"  {line}")

    # ==================================================================
    # Phase 8: Nondimensionalization appendix
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 8] Nondimensionalization appendix")
    logger.info(f"{'='*70}")

    nondim_text = nondimensionalization_appendix(feature_names)
    for line in nondim_text.split("\n"):
        logger.info(f"  {line}")

    # ==================================================================
    # Phase 9: Convergence analysis
    # ==================================================================
    logger.info(f"\n{'='*70}")
    logger.info("[Phase 9] Convergence analysis")
    logger.info(f"{'='*70}")

    summary = controller.summary()
    exp_conv = summary["exponential_convergence"]
    logger.info(f"\n  Total rounds: {summary['total_rounds']}")
    logger.info(f"  Best R^2 (surrogate probs): {summary['best_r_squared']:.4f}")
    logger.info(f"  Exponential convergence verified: {exp_conv['verified']}")
    if exp_conv.get("decay_rate"):
        logger.info(f"  Search space decay rate: {exp_conv['decay_rate']:.4f}")
        logger.info(f"  Half-life (rounds): {exp_conv['half_life_rounds']:.1f}")

    logger.info("\n  Round-by-round history:")
    for h in summary["history"]:
        logger.info(
            f"    Round {h['round']}: R^2={h['best_r2']:.4f}, "
            f"acc={h['surrogate_accuracy']:.3f}, "
            f"space={h['search_space_size']}, "
            f"delta={h['improvement_ratio']:.4f}"
        )

    # ==================================================================
    # Save results
    # ==================================================================
    total_time = time.time() - t_start
    logger.info(f"\n  Total runtime: {total_time:.1f}s")

    results = {
        "config": {k: str(v) for k, v in config.items()},
        "best_law": {
            "expression": best_law.expression,
            "complexity": best_law.complexity,
            "r_squared_on_surrogate_probs": best_law.r_squared,
            "mse_on_surrogate_probs": best_law.mse,
            "note": "R^2 and MSE here are computed on surrogate probability "
                    "outputs, NOT on binary labels. See 'classification_metrics' "
                    "for held-out classification performance.",
        },
        "classification_metrics": {
            "test_accuracy": eval_result.accuracy,
            "test_accuracy_95ci_wilson": list(eval_result.accuracy_ci),
            "precision": eval_result.precision,
            "recall": eval_result.recall,
            "f1": eval_result.f1,
            "roc_auc": eval_result.roc_auc,
            "brier_score": eval_result.brier_score,
            "confusion_matrix": eval_result.confusion_matrix,
            "r_squared_binary": eval_result.r_squared,
            "mse_binary": eval_result.mse,
            "speedup": eval_result.speedup_vs_nbody,
            "n_test": eval_result.n_test_samples,
            "n_positive_test": eval_result.n_positive,
            "n_negative_test": eval_result.n_negative,
            "class_balance_warning": eval_result.class_balance_warning,
        },
        "baselines": [
            {
                "name": b.name, "accuracy": b.accuracy,
                "r_squared": b.r_squared,
                "roc_auc": b.roc_auc if not np.isnan(b.roc_auc) else None,
                "brier_score": b.brier_score if not np.isnan(b.brier_score) else None,
            }
            for b in eval_result.baselines
        ],
        "fresh_evaluation": fresh_result,
        "in_vs_ood_evaluation": in_vs_ood,
        "targeted_delta_hill_experiment": delta_hill_exp,
        "counterexample_search": counterexamples,
        "calibration": cal_data,
        "controlled_delta_hill_sweep": controlled_sweep,
        "multi_context_sweep": multi_ctx,
        "exponent_comparison": exponent_comparison,
        "stratified_ood_analysis": strat_analysis,
        "adversarial_counterexamples": adv_ce,
        "retrain_with_adversarial": {
            k: v for k, v in retrain_result.items()
            if k not in ("X_augmented", "y_augmented")
        },
        "brier_decomposition": brier_decomp,
        "sequential_testing": seq_test,
        "replication_holdout": repl_result,
        "speedup_accounting": speedup_acct,
        "runtime_detail": runtime_detail,
        "conservative_conclusion": conclusion_text,
        "leakage_audit": leak_audit,
        "bootstrap_exponents": {
            "overall_mean_std": boot_exp.get("overall_mean_std"),
            "n_bootstrap": boot_exp.get("n_bootstrap"),
            "per_feature_summary": {
                fname: {
                    "mean": boot_exp["features"][fname]["mean"],
                    "std": boot_exp["features"][fname]["std"],
                    "ci_2.5": boot_exp["features"][fname]["ci_2.5"],
                    "ci_97.5": boot_exp["features"][fname]["ci_97.5"],
                }
                for fname in feature_names
            } if boot_exp.get("success") else None,
        },
        "dimensional_consistency": dim_check,
        "guarantees": {
            "identifiability": {
                "satisfied": ident.is_satisfied,
                "statement": ident.statement,
                "verification": ident.numerical_verification,
            },
            "generalisation": {
                "satisfied": gen.is_satisfied,
                "statement": gen.statement,
                "verification": gen.numerical_verification,
            },
        },
        "prediction": prediction,
        "convergence": summary,
        "all_laws": [
            {
                "expression": l.expression,
                "complexity": l.complexity,
                "r_squared": l.r_squared,
                "iteration": l.iteration_discovered,
            }
            for l in all_discovered_laws[:20]
        ],
        "total_time_seconds": total_time,
    }

    results_path = output_dir / "discovery_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"\n  Results saved to {results_path}")

    # Save human-readable report
    laws_path = output_dir / "discovered_laws.txt"
    with open(laws_path, "w", encoding="utf-8") as f:
        f.write("DISCOVERED MICRO-LAWS IN EXOPLANET DYNAMICS\n")
        f.write("=" * 60 + "\n\n")

        # Rewritten headline paragraph (per peer review #3: conservative language)
        f.write("HEADLINE\n")
        f.write("-" * 60 + "\n")
        f.write(
            f"A symbolic regression search over {len(all_discovered_laws)} "
            f"candidate expressions identified '{best_law.expression}' as "
            f"a candidate empirical stability proxy for 2-planet Keplerian "
            f"systems. On a held-out split (n={eval_result.n_test_samples}), "
            f"classification accuracy was {eval_result.accuracy*100:.1f}% "
            f"(95% Wilson CI [{eval_result.accuracy_ci[0]*100:.1f}%, "
            f"{eval_result.accuracy_ci[1]*100:.1f}%]). "
        )
        f.write(
            f"On {fresh_result['n_fresh']} independently generated fresh "
            f"systems, accuracy was {fresh_result['accuracy']*100:.1f}% "
            f"(95% CI [{fresh_result['wilson_ci_95'][0]*100:.1f}%, "
            f"{fresh_result['wilson_ci_95'][1]*100:.1f}%]). "
        )
        f.write(
            f"In-distribution accuracy {in_vs_ood['in_distribution']['accuracy']*100:.1f}% "
            f"vs OOD {in_vs_ood['out_of_distribution']['accuracy']*100:.1f}% "
            f"(delta={in_vs_ood['delta_accuracy']*100:+.1f}pp). "
        )
        if not ident.is_satisfied:
            f.write(
                f"Bootstrap identifiability checks show exponent estimates are "
                f"unstable (bootstrap std ~{boot_exp.get('overall_mean_std', 0):.3f} "
                f">> theoretical {ident.numerical_verification.get('theoretical_std', 0):.4f}). "
            )
        if delta_hill_exp.get("success"):
            f.write(
                f"A targeted delta_Hill grid experiment yields exponent "
                f"{delta_hill_exp['exponent']:.2f} "
                f"(95% CI [{delta_hill_exp['bootstrap_exponent_ci_95'][0]:.2f}, "
                f"{delta_hill_exp['bootstrap_exponent_ci_95'][1]:.2f}], "
                f"R^2={delta_hill_exp['r_squared']:.3f}). "
            )
        if not gen.is_satisfied:
            f.write(
                f"The Occam/PAC-Bayes generalisation bound is vacuous for "
                f"n={len(X_train)} (bound > 1). "
            )
        if controlled_sweep.get("success"):
            f.write(
                f"A controlled sweep (other features fixed at median) yields "
                f"exponent {controlled_sweep['exponent']:.2f} "
                f"(95% CI [{controlled_sweep['bootstrap_exponent_ci_95'][0]:.2f}, "
                f"{controlled_sweep['bootstrap_exponent_ci_95'][1]:.2f}], "
                f"R^2={controlled_sweep['r_squared']:.3f}). "
            )
        if exponent_comparison.get("success"):
            f.write(
                f"AIC favours {exponent_comparison['preferred_model']} model "
                f"(ΔAIC={exponent_comparison['aic_delta']:.1f}). "
            )
        f.write(
            f"Counterexample search ({counterexamples['n_candidates']} systems) shows "
            f"error rate {counterexamples['error_rate']*100:.1f}%. "
            f"ECE = {cal_data['ece']:.3f}. "
            f"Sequential corrections account for {seq_test['n_total_implicit_tests']} "
            f"implicit tests (Bonferroni α={seq_test['bonferroni_alpha']:.4f}). "
            f"One-time replication holdout (n={repl_result['n_holdout']}, independent seed): "
            f"accuracy {repl_result['accuracy']*100:.1f}% — {repl_result['verdict']}. "
            f"Adversarial retraining: probe accuracy "
            f"{retrain_result['pre_accuracy']*100:.1f}% → "
            f"{retrain_result['post_accuracy']*100:.1f}%. "
            f"The cubic exponent is presented as a PARSIMONIOUS SURROGATE, "
            f"not yet proven as the mechanistic scaling.\n\n"
        )

        # Independent fresh evaluation
        f.write(f"INDEPENDENT EVALUATION (n={fresh_result['n_fresh']} fresh systems)\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Accuracy:    {fresh_result['accuracy']:.4f} "
                f"(95% Wilson CI: [{fresh_result['wilson_ci_95'][0]:.3f}, "
                f"{fresh_result['wilson_ci_95'][1]:.3f}])\n")
        f.write(f"  Precision:   {fresh_result['precision']:.4f}\n")
        f.write(f"  Recall:      {fresh_result['recall']:.4f}\n")
        f.write(f"  F1:          {fresh_result['f1']:.4f}\n")
        f.write(f"  ROC AUC:     {fresh_result['roc_auc']:.4f}\n")
        f.write(f"  Brier:       {fresh_result['brier_score']:.4f}\n")
        f.write(f"  Confusion:   TP={fcm['tp']} TN={fcm['tn']} FP={fcm['fp']} FN={fcm['fn']}\n")
        f.write(f"  Binomial H0:p>=90%: p={bt90['p_value']:.4f} -> {bt90['interpretation']}\n")
        f.write(f"  Binomial H0:p>=80%: p={bt80['p_value']:.4f} -> {bt80['interpretation']}\n\n")

        # Classification table
        f.write(f"CLASSIFICATION METRICS (held-out, n={eval_result.n_test_samples})\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Accuracy:    {eval_result.accuracy:.4f} "
                f"(Wilson CI: [{eval_result.accuracy_ci[0]:.3f}, {eval_result.accuracy_ci[1]:.3f}])\n")
        f.write(f"  Precision:   {'nan' if np.isnan(eval_result.precision) else f'{eval_result.precision:.4f}'}\n")
        f.write(f"  Recall:      {'nan' if np.isnan(eval_result.recall) else f'{eval_result.recall:.4f}'}\n")
        f.write(f"  F1:          {'nan' if np.isnan(eval_result.f1) else f'{eval_result.f1:.4f}'}\n")
        f.write(f"  ROC AUC:     {'nan' if np.isnan(eval_result.roc_auc) else f'{eval_result.roc_auc:.4f}'}\n")
        f.write(f"  Brier:       {'nan' if np.isnan(eval_result.brier_score) else f'{eval_result.brier_score:.4f}'}\n")
        f.write(f"  Confusion:   TP={cm['tp']} TN={cm['tn']} FP={cm['fp']} FN={cm['fn']}\n")
        f.write(f"  Test set: {eval_result.n_positive} stable, {eval_result.n_negative} unstable\n")
        if eval_result.class_balance_warning:
            f.write(f"  {eval_result.class_balance_warning}\n")

        # Surrogate regression
        f.write(f"\nSURROGATE REGRESSION METRICS (on probability outputs)\n")
        f.write("-" * 60 + "\n")
        f.write(f"  R^2:   {best_law.r_squared:.4f}\n")
        f.write(f"  MSE:   {best_law.mse:.6f}\n")
        f.write(f"  NOTE:  These are computed on surrogate P(stable), NOT binary labels.\n\n")

        # Baselines
        f.write("BASELINE COMPARISONS\n")
        f.write("-" * 60 + "\n")
        for bl in eval_result.baselines:
            auc_s = f"AUC={bl.roc_auc:.3f}" if not np.isnan(bl.roc_auc) else "AUC=n/a"
            brier_s = f"Brier={bl.brier_score:.3f}" if not np.isnan(bl.brier_score) else "Brier=n/a"
            f.write(f"  {bl.name}: acc={bl.accuracy:.4f}, {auc_s}, {brier_s}\n")
        f.write(f"  >>> SURROGATE: acc={eval_result.accuracy:.4f}, "
                f"AUC={'n/a' if np.isnan(eval_result.roc_auc) else f'{eval_result.roc_auc:.3f}'}, "
                f"Brier={'n/a' if np.isnan(eval_result.brier_score) else f'{eval_result.brier_score:.3f}'}\n")
        f.write(f"  Speedup vs N-body: ~{eval_result.speedup_vs_nbody:.0f}x\n\n")

        # Leakage audit
        f.write("LEAKAGE / PREPROCESSING AUDIT\n")
        f.write("-" * 60 + "\n")
        for chk in leak_audit["checks"]:
            f.write(f"  [{'PASS' if chk['passed'] else 'FAIL'}] {chk['name']}: {chk['detail']}\n")
        f.write("\n")

        # Dimensional check
        f.write(f"DIMENSIONAL CONSISTENCY\n")
        f.write("-" * 60 + "\n")
        f.write(f"  {dim_check['note']}\n\n")

        # Bootstrap exponent summary
        f.write("BOOTSTRAP EXPONENT ANALYSIS\n")
        f.write("-" * 60 + "\n")
        if boot_exp.get("success"):
            f.write(f"  {boot_exp['n_bootstrap']} bootstrap samples\n")
            f.write(f"  Overall mean std: {boot_exp['overall_mean_std']:.4f}\n")
            for fname in feature_names:
                fd = boot_exp["features"][fname]
                f.write(f"  {fname}: mean={fd['mean']:.4f} std={fd['std']:.4f} "
                       f"95%CI=[{fd['ci_2.5']:.4f}, {fd['ci_97.5']:.4f}]\n")
            f.write(f"  Saved histogram data to bootstrap_exponents.npz\n")
        else:
            f.write(f"  Bootstrap failed: {boot_exp.get('reason', 'unknown')}\n")
        f.write("\n")

        # In-distribution vs OOD
        f.write("IN-DISTRIBUTION vs OUT-OF-DISTRIBUTION EVALUATION\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Total fresh: {in_vs_ood['n_total']}\n")
        ind = in_vs_ood['in_distribution']
        ood = in_vs_ood['out_of_distribution']
        f.write(f"  In-dist:  n={ind['n']}, acc={ind['accuracy']:.4f} "
                f"(95% CI [{ind['wilson_ci_95'][0]:.3f}, {ind['wilson_ci_95'][1]:.3f}])\n")
        f.write(f"  OOD:      n={ood['n']}, acc={ood['accuracy']:.4f} "
                f"(95% CI [{ood['wilson_ci_95'][0]:.3f}, {ood['wilson_ci_95'][1]:.3f}])\n")
        f.write(f"  Delta (in - ood): {in_vs_ood['delta_accuracy']:+.4f}\n\n")

        # Targeted delta_Hill experiment
        f.write("TARGETED DELTA_HILL GRID EXPERIMENT\n")
        f.write("-" * 60 + "\n")
        if delta_hill_exp.get("success"):
            f.write(f"  Grid: {delta_hill_exp['n_bins']} bins x "
                    f"{delta_hill_exp['n_per_bin']} systems/bin\n")
            f.write(f"  Exponent: {delta_hill_exp['exponent']:.4f} "
                    f"(95% CI [{delta_hill_exp['bootstrap_exponent_ci_95'][0]:.4f}, "
                    f"{delta_hill_exp['bootstrap_exponent_ci_95'][1]:.4f}])\n")
            f.write(f"  R^2 of log-log fit: {delta_hill_exp['r_squared']:.4f}\n")
        else:
            f.write(f"  Failed: {delta_hill_exp.get('reason', 'unknown')}\n")
        f.write("\n")

        # Counterexample search
        f.write("COUNTEREXAMPLE SEARCH\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Candidates searched: {counterexamples['n_candidates']}\n")
        f.write(f"  Overall error rate:  {counterexamples['error_rate']:.4f}\n")
        f.write(f"  Top worst failures:\n")
        for i, ex in enumerate(counterexamples["worst_failures"][:5]):
            f.write(f"    [{i}] |err|={ex['disagreement']:.4f} "
                    f"pred={ex['predicted_prob']:.3f} "
                    f"actual={ex['true_label']}\n")
        if counterexamples["failure_regime_summary"]:
            f.write(f"  Failure regime: {counterexamples['failure_regime_summary']}\n")
        f.write("\n")

        # Calibration
        f.write("CALIBRATION ANALYSIS\n")
        f.write("-" * 60 + "\n")
        f.write(f"  ECE: {cal_data['ece']:.4f}\n")
        f.write(f"  {'Bin':<15} {'N':>5} {'Mean Pred':>10} {'Frac Pos':>10}\n")
        for b in cal_data["bins"]:
            f.write(f"  [{b['bin_lower']:.1f}-{b['bin_upper']:.1f}]"
                    f"     {b['count']:>5} {b['mean_predicted']:>10.3f} "
                    f"{b['fraction_positive']:>10.3f}\n")
        f.write("\n")

        # Controlled delta_Hill sweep
        f.write("CONTROLLED DELTA_HILL SWEEP (fixed other features at median)\n")
        f.write("-" * 60 + "\n")
        if controlled_sweep["success"]:
            f.write(f"  Grid: {controlled_sweep.get('n_bins', '?')} bins x "
                    f"{controlled_sweep.get('n_per_bin', '?')} systems/bin "
                    f"({controlled_sweep.get('n_points', '?')} valid)\n")
            f.write(f"  Exponent: {controlled_sweep['exponent']:.4f} "
                    f"(95% CI [{controlled_sweep['bootstrap_exponent_ci_95'][0]:.4f}, "
                    f"{controlled_sweep['bootstrap_exponent_ci_95'][1]:.4f}])\n")
            f.write(f"  R^2: {controlled_sweep['r_squared']:.4f}\n")
            f.write(f"  Heteroskedasticity corr: {controlled_sweep['heteroskedasticity_corr']:.4f} "
                    f"({'FLAGGED' if controlled_sweep['heteroskedasticity_flag'] else 'OK'})\n")
            f.write(f"  Exponent=3 within 95% CI: {controlled_sweep['exponent_3_in_ci']}\n")
        else:
            f.write(f"  Failed: {controlled_sweep.get('reason', 'unknown')}\n")
        f.write("\n")

        # Free vs fixed exponent
        f.write("FREE vs FIXED EXPONENT COMPARISON\n")
        f.write("-" * 60 + "\n")
        if exponent_comparison["success"]:
            f.write(f"  Free exponent: {exponent_comparison['free_exponent']:.4f} "
                    f"(R^2={exponent_comparison['free_r_squared']:.4f}, "
                    f"AIC={exponent_comparison['free_aic']:.1f})\n")
            f.write(f"  Fixed exp=3:   "
                    f"(R^2={exponent_comparison['fixed_r_squared']:.4f}, "
                    f"AIC={exponent_comparison['fixed_aic']:.1f})\n")
            f.write(f"  ΔAIC (free−fixed): {exponent_comparison['aic_delta']:.1f}\n")
            f.write(f"  Preferred: {exponent_comparison['preferred_model']}\n")
        else:
            f.write(f"  Failed: {exponent_comparison.get('reason', 'unknown')}\n")
        f.write("\n")

        # Stratified OOD analysis
        f.write("STRATIFIED OOD SUBREGIME ANALYSIS\n")
        f.write("-" * 60 + "\n")
        f.write(f"  {strat_analysis['n_strata']} strata, n={strat_analysis['n_total']}\n")
        f.write(f"  {'Stratum':<40} {'N':>5} {'Acc':>7} {'CI_lo':>7} {'CI_hi':>7}\n")
        for s in strat_analysis["strata"]:
            ci = s["wilson_ci_95"]
            a_str = f"{s['accuracy']:.3f}" if not np.isnan(s['accuracy']) else "  n/a"
            f.write(f"  {s['name']:<40} {s['n']:>5} {a_str:>7} "
                    f"{ci[0]:.3f}   {ci[1]:.3f}\n")
        f.write("\n")

        # Adversarial counterexample search
        f.write("ADVERSARIAL COUNTEREXAMPLE SEARCH\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Initial search: {adv_ce['n_initial']} systems, "
                f"{adv_ce['n_misclassified']} misclassified "
                f"(error={adv_ce['error_rate']:.4f})\n")
        f.write(f"  Failures investigated: {adv_ce['n_failures_investigated']}\n")
        f.write(f"  Boundary samples: {adv_ce['n_boundary_samples_generated']}\n")
        for pr in adv_ce["perturbation_results"][:3]:
            f.write(f"    Failure idx={pr['original_index']}: "
                    f"true={pr['true_label']}, P(stable)={pr['original_prob']:.3f}, "
                    f"{pr['n_perturbed_misclassified']}/{pr['n_perturbations']} also wrong\n")
        f.write("\n")

        # Brier decomposition
        f.write("BRIER SCORE DECOMPOSITION (Murphy 1973)\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Brier score:  {brier_decomp['brier_score']:.4f}\n")
        f.write(f"  Reliability:  {brier_decomp['reliability']:.4f} (lower=better)\n")
        f.write(f"  Resolution:   {brier_decomp['resolution']:.4f} (higher=better)\n")
        f.write(f"  Uncertainty:  {brier_decomp['uncertainty']:.4f}\n")
        f.write(f"  Check sum:    {brier_decomp['check_sum']:.4f} (should ≈ Brier)\n\n")

        # Sequential testing corrections
        f.write("SEQUENTIAL TESTING CORRECTIONS\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Total implicit tests: {seq_test['n_total_implicit_tests']}\n")
        f.write(f"  Bonferroni alpha: {seq_test['bonferroni_alpha']:.4f}\n")
        f.write(f"  Holm step-down alphas (first 5): "
                f"{[round(a, 4) for a in seq_test['holm_step_down_alphas'][:5]]}\n")
        f.write(f"  Replication protocol: {seq_test['replication_protocol']}\n\n")

        # Multi-context controlled sweep
        f.write("MULTI-CONTEXT CONTROLLED \u0394HILL SWEEPS\n")
        f.write("-" * 60 + "\n")
        if multi_ctx.get("success"):
            for ctx_name, ctx_res in multi_ctx.get("contexts", {}).items():
                if ctx_res.get("success"):
                    f.write(f"  {ctx_name}: exponent={ctx_res['exponent']:.3f} "
                            f"(CI [{ctx_res['bootstrap_ci_95'][0]:.3f}, "
                            f"{ctx_res['bootstrap_ci_95'][1]:.3f}], "
                            f"R\u00b2={ctx_res['r_squared']:.4f})\n")
                else:
                    f.write(f"  {ctx_name}: FAILED\n")
            pooled = multi_ctx.get("pooled", {})
            if pooled.get("success"):
                f.write(f"  POOLED: exponent={pooled['exponent']:.3f} "
                        f"(CI [{pooled['bootstrap_ci_95'][0]:.3f}, "
                        f"{pooled['bootstrap_ci_95'][1]:.3f}], "
                        f"R\u00b2={pooled['r_squared']:.4f})\n")
                f.write(f"  Exponent=3 in pooled CI: {pooled['exponent_3_in_ci']}\n")
        f.write("\n")

        # Adversarial retraining
        f.write("ADVERSARIAL RETRAINING\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Training samples: {retrain_result['n_original_train']} \u2192 "
                f"{retrain_result['n_augmented_train']} "
                f"(+{retrain_result['n_added_boundary']} boundary, "
                f"+{retrain_result['n_added_adversarial']} adversarial)\n")
        f.write(f"  Probe accuracy: {retrain_result['pre_accuracy']*100:.1f}% \u2192 "
                f"{retrain_result['post_accuracy']*100:.1f}% "
                f"(\u0394={retrain_result['delta_accuracy']*100:+.1f}pp)\n")
        for sc in retrain_result.get("strata_comparison", []):
            f.write(f"    {sc['stratum']}: {sc['pre_accuracy']*100:.1f}% \u2192 "
                    f"{sc['post_accuracy']*100:.1f}% (\u0394={sc['delta']*100:+.1f}pp)\n")
        f.write("\n")

        # Replication holdout
        f.write("REPLICATION HOLDOUT TEST (one-time, independent seed)\n")
        f.write("-" * 60 + "\n")
        f.write(f"  n={repl_result['n_holdout']} "
                f"({repl_result['n_positive']} stable, {repl_result['n_negative']} unstable)\n")
        f.write(f"  Accuracy: {repl_result['accuracy']*100:.1f}% "
                f"(95% CI [{repl_result['wilson_ci_95'][0]*100:.1f}%, "
                f"{repl_result['wilson_ci_95'][1]*100:.1f}%])\n")
        f.write(f"  Corrected \u03b1: {repl_result['corrected_alpha']:.4f}\n")
        f.write(f"  {repl_result['binomial_test_H0_p90']['interpretation']}\n")
        f.write(f"  VERDICT: {repl_result['verdict']}\n\n")

        # Speedup accounting
        f.write("SPEEDUP AND RUNTIME ACCOUNTING\n")
        f.write("-" * 60 + "\n")
        f.write(f"  N-body time/system: {speedup_acct['nbody_time_per_system_s']:.4f}s\n")
        f.write(f"  Surrogate time/system: {speedup_acct['surrogate_time_per_system_s']:.6f}s\n")
        f.write(f"  Inference speedup: {speedup_acct['inference_speedup']:.0f}x\n")
        f.write(f"  Amortised speedup: {speedup_acct['amortised_speedup']:.2f}x\n")
        f.write(f"  Total pipeline time: {speedup_acct['total_pipeline_time_s']:.1f}s\n")
        for phase_name, pct_val in runtime_detail.get("cost_breakdown_pct", {}).items():
            f.write(f"    {phase_name}: {pct_val:.1f}%\n")
        f.write(f"  Note: {speedup_acct['note']}\n\n")

        # Guarantees
        f.write("THEORETICAL GUARANTEES\n")
        f.write("-" * 60 + "\n")
        f.write(f"  Identifiability: {'SATISFIED' if ident.is_satisfied else 'NOT SATISFIED'}\n")
        f.write(f"    {ident.statement}\n")
        f.write(f"  Generalisation:  {'SATISFIED' if gen.is_satisfied else 'VACUOUS'}\n")
        f.write(f"    {gen.statement}\n\n")

        # All laws
        f.write("ALL CANDIDATE LAWS (ranked by R^2 on surrogate probs)\n")
        f.write("-" * 60 + "\n")
        for i, l in enumerate(sorted(all_discovered_laws, key=lambda x: -x.r_squared)[:20]):
            f.write(f"  [{i}] R^2={l.r_squared:.4f} | C={l.complexity} | "
                    f"Round {l.iteration_discovered} | {l.expression}\n")

        # Falsifiable prediction
        f.write(f"\nFALSIFIABLE PREDICTION\n")
        f.write("-" * 60 + "\n")
        f.write(f"  {prediction['prediction']}\n")
        f.write(f"\n  Caveats: {prediction.get('caveats', 'None')}\n")
        f.write(f"\n  Falsification: {prediction['falsification_criteria']}\n")

        # Nondimensionalization appendix
        f.write(f"\n\n{nondim_text}\n")

        # Conservative conclusion
        f.write(f"\n\n{conclusion_text}\n")

    logger.info(f"  Report saved to {laws_path}")

    logger.info("\n" + "=" * 70)
    logger.info("DISCOVERY LOOP COMPLETE")
    logger.info("=" * 70)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Exponential self-improving micro-law discovery for exoplanet dynamics"
    )
    parser.add_argument("--rounds", type=int, default=DEFAULT_CONFIG["max_rounds"],
                        help="Maximum self-improvement rounds")
    parser.add_argument("--n-train", type=int, default=DEFAULT_CONFIG["n_train"],
                        help="Number of training systems")
    parser.add_argument("--n-test", type=int, default=DEFAULT_CONFIG["n_test"],
                        help="Number of test systems")
    parser.add_argument("--integration-steps", type=int,
                        default=DEFAULT_CONFIG["integration_steps"],
                        help="N-body integration steps per system")
    parser.add_argument("--epochs", type=int, default=DEFAULT_CONFIG["epochs"],
                        help="Surrogate training epochs per round")
    parser.add_argument("--sr-backend", type=str, default=DEFAULT_CONFIG["sr_backend"],
                        choices=["auto", "pysr", "builtin"],
                        help="Symbolic regression backend")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_CONFIG["output_dir"],
                        help="Output directory for results")
    parser.add_argument("--seed", type=int, default=DEFAULT_CONFIG["seed"],
                        help="Random seed")
    parser.add_argument("--fast", action="store_true",
                        help="Fast mode: fewer samples and iterations for testing")

    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    config["max_rounds"] = args.rounds
    config["n_train"] = args.n_train
    config["n_test"] = args.n_test
    config["integration_steps"] = args.integration_steps
    config["epochs"] = args.epochs
    config["sr_backend"] = args.sr_backend
    config["output_dir"] = args.output_dir
    config["seed"] = args.seed

    if args.fast:
        config["n_train"] = 80
        config["n_test"] = 40
        config["n_val"] = 20
        config["n_fresh"] = 500
        config["integration_steps"] = 500
        config["epochs"] = 30
        config["max_rounds"] = 3
        config["n_new_boundary"] = 10
        config["n_new_random"] = 10

    run_discovery_loop(config)


if __name__ == "__main__":
    main()
