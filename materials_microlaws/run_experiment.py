#!/usr/bin/env python3
"""
run_experiment.py — Main entry point for the Materials Micro-Laws Discovery Framework.

Usage:
  python run_experiment.py                        # Full demo with synthetic data
  python run_experiment.py --iterations 10        # More refinement iterations
  python run_experiment.py --source matminer      # Use real Materials Project data
  python run_experiment.py --sr pysr              # Use PySR (requires Julia + PySR)
  python run_experiment.py --output results/      # Save results to directory
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from loguru import logger

# Add parent directory to path for package imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from materials_microlaws.data_loader import load_perovskite_dataset
from materials_microlaws.iteration_loop import IterationConfig, run_refinement_loop
from materials_microlaws.theory import (
    NumericalPrediction,
    SearchSpaceReductionTheorem,
    SpuriousLawBound,
)


def main():
    parser = argparse.ArgumentParser(
        description="Materials Micro-Laws Discovery: Symbolic Regression with Physical Constraints"
    )
    parser.add_argument(
        "--source", choices=["synthetic", "matminer"], default="synthetic",
        help="Data source (default: synthetic)",
    )
    parser.add_argument(
        "--iterations", type=int, default=5,
        help="Number of self-improvement iterations (default: 5)",
    )
    parser.add_argument(
        "--sr", choices=["builtin", "pysr"], default="builtin",
        help="Symbolic regression engine (default: builtin)",
    )
    parser.add_argument(
        "--repr", choices=["pca", "autoencoder"], default="pca",
        help="Representation learning method (default: pca)",
    )
    parser.add_argument(
        "--max-complexity", type=int, default=20,
        help="Maximum expression complexity (default: 20)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory for results",
    )
    parser.add_argument(
        "--noise", type=float, default=0.08,
        help="Noise level for synthetic data (default: 0.08 eV)",
    )
    parser.add_argument(
        "--theory-only", action="store_true",
        help="Only print theoretical analysis, skip experiments",
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{message}")

    logger.info("╔══════════════════════════════════════════════════════════════════╗")
    logger.info("║  Materials Micro-Laws Discovery Framework                       ║")
    logger.info("║  Generative AI for Interpretable Materials Micro-Laws           ║")
    logger.info("║  Under Symbolic Physical Constraints                            ║")
    logger.info("╚══════════════════════════════════════════════════════════════════╝")
    logger.info("")

    # Print theoretical framework first
    _print_theoretical_framework(args)

    if args.theory_only:
        return

    # Load dataset
    logger.info("\n" + "=" * 70)
    logger.info("LOADING DATA")
    logger.info("=" * 70)
    dataset = load_perovskite_dataset(source=args.source, noise_std=args.noise)

    # Configure iteration
    config = IterationConfig(
        repr_method=args.repr,
        sr_method=args.sr,
        max_complexity=args.max_complexity,
    )

    # Run the refinement loop
    t_start = time.time()
    results = run_refinement_loop(
        dataset=dataset,
        n_iterations=args.iterations,
        config=config,
        output_dir=args.output,
    )
    t_total = time.time() - t_start

    # Final summary
    logger.info("\n" + "=" * 70)
    logger.info("EXPERIMENT SUMMARY")
    logger.info("=" * 70)
    logger.info(f"  Total runtime:       {t_total:.1f}s")
    logger.info(f"  Iterations:          {args.iterations}")
    logger.info(f"  Data source:         {args.source}")
    logger.info(f"  SR engine:           {args.sr}")
    logger.info(f"  Best formula:        {results.get('best_formula', 'N/A')}")
    logger.info(f"  Best MAE:            {results.get('best_mae', 'N/A')} eV")

    convergence = results.get("convergence", {})
    logger.info(f"  MAE improvement:     {convergence.get('mae_improvement', 0)*100:.1f}%")
    logger.info(f"  Convergence rate:    {convergence.get('convergence_rate_lambda', 0):.4f}")

    theory = results.get("theory", {})
    logger.info(f"  Cumulative reduction: {theory.get('cumulative_reduction', 1):.1f}×")

    pred = results.get("predictions_evaluation")
    if pred:
        overall = pred.get("overall", {})
        status = "ALL PASSED ✓" if overall.get("passed") else "SOME FAILED ✗"
        logger.info(f"  Predictions:         {status}")

    logger.info("\n  Done.")


def _print_theoretical_framework(args):
    """Print the full theoretical framework before running experiments."""
    logger.info("=" * 70)
    logger.info("THEORETICAL FRAMEWORK")
    logger.info("=" * 70)

    logger.info("""
    This framework discovers symbolic "micro-laws" for materials properties
    by combining three components:

    (1) REPRESENTATION LEARNER: Maps crystal structures / descriptor vectors
        to latent features via PCA or autoencoder (GNN when graph data available).

    (2) SYMBOLIC REGRESSION CORE: Proposes candidate formulas over physically
        meaningful descriptors using template enumeration + least-squares,
        or PySR (GP-based) when available.

    (3) CONSTRAINT ENGINE: Prunes expressions violating:
        - Dimensional analysis (e.g., can't add length + energy)
        - Monotonicity rules (e.g., band gap ↑ with anion electronegativity)
        - Physical bounds (e.g., Eg ≥ 0)
        - Complexity limits (Occam's razor)

    The iterative loop refines descriptors, templates, and constraints
    across K iterations, achieving exponential search space reduction.
    """)

    # Theorem 1
    theorem1 = SearchSpaceReductionTheorem(
        D=16, C_max=args.max_complexity,
    )
    theorem1.print_theorem()

    # Theorem 2
    theorem2 = SpuriousLawBound(
        sigma=args.noise,
        delta=0.05,
        log_S_phi=max(
            theorem1.summary()['|S_Φ| (log10)'],
            1.0,
        ),
    )
    theorem2.print_theorem()

    # Predictions
    predictions = NumericalPrediction(K_iterations=args.iterations)
    predictions.print_predictions()


if __name__ == "__main__":
    main()
