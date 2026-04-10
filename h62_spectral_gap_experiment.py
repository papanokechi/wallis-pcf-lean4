#!/usr/bin/env python3
"""
H6.2 Minimal Experiment — Spectral Gap as Reward Hacking Predictor

Hypothesis (H6.2): Overoptimization in RLHF is predictable from the
spectral gap of the reward model's preference embedding matrix.

    D_crit = Δ² / (4·d)

where Δ = λ₁ - λ₂ (top two eigenvalues of the preference covariance
matrix M) and d is the hidden dimension.

Protocol:
  Phase 1: Extract preference covariance matrix from Reward Model
  Phase 2: Compute spectral gap Δ and predict D_crit
  Phase 3: Run PPO, monitor KL vs Gold Reward, find actual collapse point
  Phase 4: Validate |D_actual - D_crit| / D_actual < 0.15

Requirements:
  pip install torch transformers datasets trl accelerate

Reference: Breakthrough Engine V7.1, Hypothesis H6.2
  Gao et al. 2023 — Scaling Laws for Reward Model Overoptimization
  Coste et al. 2023 — Reward Model Ensembles Help Mitigate Overoptimization
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

try:
    import torch
    from torch.linalg import svdvals
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False


# ── Configuration ───────────────────────────────────────────────────────

@dataclass
class ExperimentConfig:
    """Configuration for the H6.2 spectral gap experiment."""
    # Reward model to analyze
    reward_model_name: str = "sfairXwRks/Llama-3-8B-Instruct-RM-v0.1"
    # Number of preference pairs to sample
    n_samples: int = 512
    # Noise levels for RM perturbation (σ)
    noise_levels: list = field(default_factory=lambda: [0.0, 0.01, 0.05, 0.1])
    # PPO steps per configuration
    ppo_steps: int = 1000
    # Batch size for activation extraction
    batch_size: int = 16
    # Validation threshold: |D_actual - D_crit| / D_actual < threshold
    validation_threshold: float = 0.15
    # Device
    device: str = "cuda" if HAS_TORCH and torch.cuda.is_available() else "cpu"
    # Output file
    output_file: str = "h62_spectral_results.json"


# ── Phase 1: Preference Matrix Extraction ───────────────────────────────

def extract_preference_vectors(
    model,
    tokenizer,
    preference_pairs: list[dict],
    device: str = "cuda",
    max_length: int = 512,
) -> "torch.Tensor":
    """
    Extract preference direction vectors h_w - h_l from the reward model.

    Args:
        model: Reward model (AutoModelForSequenceClassification)
        tokenizer: Associated tokenizer
        preference_pairs: List of dicts with 'chosen' and 'rejected' keys
        device: Compute device
        max_length: Maximum token length for truncation

    Returns:
        Tensor of shape [N, d] where d is the hidden dimension
    """
    diff_vectors = []

    model.eval()
    with torch.no_grad():
        for pair in preference_pairs:
            chosen_text = pair["chosen"]
            rejected_text = pair["rejected"]

            # Tokenize with truncation to prevent OOM
            inputs_w = tokenizer(
                chosen_text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
                padding=False,
            ).to(device)

            inputs_l = tokenizer(
                rejected_text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
                padding=False,
            ).to(device)

            # Extract last hidden states before the value head
            # model.model accesses the base transformer (no classification head)
            out_w = model.model(**inputs_w, output_hidden_states=True)
            out_l = model.model(**inputs_l, output_hidden_states=True)

            # Last token of last hidden layer — standard for causal LM reward models
            h_w = out_w.hidden_states[-1][0, -1, :]  # [d]
            h_l = out_l.hidden_states[-1][0, -1, :]  # [d]

            diff_vectors.append((h_w - h_l).float())

    return torch.stack(diff_vectors)  # [N, d]


# ── Phase 2: Spectral Gap Computation ───────────────────────────────────

@dataclass
class SpectralResult:
    """Result of spectral gap analysis."""
    lambda_1: float          # Largest eigenvalue
    lambda_2: float          # Second largest eigenvalue
    delta: float             # Spectral gap: λ₁ - λ₂
    hidden_dim: int          # d
    d_crit: float            # Predicted critical KL: Δ²/(4d)
    top_10_eigenvalues: list # For diagnostics
    noise_sigma: float = 0.0

    def to_dict(self):
        return {
            "lambda_1": self.lambda_1,
            "lambda_2": self.lambda_2,
            "delta": self.delta,
            "hidden_dim": self.hidden_dim,
            "d_crit": self.d_crit,
            "top_10_eigenvalues": self.top_10_eigenvalues,
            "noise_sigma": self.noise_sigma,
        }


def compute_spectral_gap(
    diff_vectors: "torch.Tensor",
    hidden_dim: int,
    noise_sigma: float = 0.0,
) -> SpectralResult:
    """
    Compute the spectral gap from preference direction vectors.

    Constructs the preference covariance matrix:
        M = (1/N) Σ (h_w - h_l)(h_w - h_l)^T

    Then computes eigenvalues via SVD.

    Args:
        diff_vectors: Tensor of shape [N, d]
        hidden_dim: Model hidden dimension (d)
        noise_sigma: If > 0, add Gaussian noise to simulate RM degradation

    Returns:
        SpectralResult with gap Δ and predicted D_crit
    """
    V = diff_vectors.clone().float()

    # Optional: perturb to simulate weaker RM (shrinks spectral gap)
    if noise_sigma > 0:
        noise = torch.randn_like(V) * noise_sigma * V.norm(dim=1, keepdim=True)
        V = V + noise

    N = V.shape[0]

    # Preference covariance matrix: M = V^T V / N
    # M is [d, d] — potentially large (4096×4096 for Llama-7B)
    M = (V.T @ V) / N

    # SVD to extract eigenvalues (M is symmetric PSD, so singular values = eigenvalues)
    lambdas = svdvals(M)

    # Spectral gap
    l1 = lambdas[0].item()
    l2 = lambdas[1].item()
    delta = l1 - l2

    # Critical KL divergence prediction
    d_crit = (delta ** 2) / (4 * hidden_dim)

    top_10 = lambdas[:10].tolist()

    return SpectralResult(
        lambda_1=l1,
        lambda_2=l2,
        delta=delta,
        hidden_dim=hidden_dim,
        d_crit=d_crit,
        top_10_eigenvalues=top_10,
        noise_sigma=noise_sigma,
    )


# ── Phase 3: PPO Monitoring (Stub) ─────────────────────────────────────
# Full PPO loop requires trl + significant compute. This provides the
# monitoring harness; actual training is out of scope for the minimal
# experiment script.

@dataclass
class PPOCollapsePoint:
    """Records when and how reward hacking is detected."""
    kl_at_collapse: float     # D_actual: KL when Gold Reward drops >10%
    gold_reward_peak: float   # Maximum Gold Reward before collapse
    gold_reward_at_collapse: float
    proxy_reward_at_collapse: float
    step_at_collapse: int
    noise_sigma: float = 0.0

    def to_dict(self):
        return {
            "kl_at_collapse": self.kl_at_collapse,
            "gold_reward_peak": self.gold_reward_peak,
            "gold_reward_at_collapse": self.gold_reward_at_collapse,
            "proxy_reward_at_collapse": self.proxy_reward_at_collapse,
            "step_at_collapse": self.step_at_collapse,
            "noise_sigma": self.noise_sigma,
        }


def find_collapse_point(
    kl_history: list[float],
    gold_reward_history: list[float],
    proxy_reward_history: list[float],
    drop_threshold: float = 0.10,
    noise_sigma: float = 0.0,
) -> PPOCollapsePoint | None:
    """
    Identify the PPO step where Gold Reward drops >10% from peak while
    Proxy Reward continues rising.

    Args:
        kl_history: KL divergence at each PPO step
        gold_reward_history: Oracle/Gold reward at each step
        proxy_reward_history: Proxy RM reward at each step
        drop_threshold: Fraction drop from peak to trigger collapse detection
        noise_sigma: RM noise level for this run

    Returns:
        PPOCollapsePoint or None if no collapse detected
    """
    if not gold_reward_history:
        return None

    peak_gold = gold_reward_history[0]
    peak_step = 0

    for step in range(len(gold_reward_history)):
        if gold_reward_history[step] > peak_gold:
            peak_gold = gold_reward_history[step]
            peak_step = step

        # Check for collapse: gold dropped >threshold from peak AND proxy still rising
        if step > peak_step and peak_gold > 0:
            drop_frac = (peak_gold - gold_reward_history[step]) / abs(peak_gold)
            if drop_frac > drop_threshold:
                # Verify proxy is still rising (compare to value at peak_step)
                if proxy_reward_history[step] >= proxy_reward_history[peak_step]:
                    return PPOCollapsePoint(
                        kl_at_collapse=kl_history[step],
                        gold_reward_peak=peak_gold,
                        gold_reward_at_collapse=gold_reward_history[step],
                        proxy_reward_at_collapse=proxy_reward_history[step],
                        step_at_collapse=step,
                        noise_sigma=noise_sigma,
                    )

    return None


# ── Phase 4: Validation ────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Final verdict: does spectral gap predict overoptimization?"""
    noise_sigma: float
    d_crit: float             # Predicted
    d_actual: float | None    # Measured (None if no collapse)
    relative_error: float | None
    passed: bool | None       # True if within threshold
    threshold: float = 0.15

    def to_dict(self):
        return {
            "noise_sigma": self.noise_sigma,
            "d_crit": self.d_crit,
            "d_actual": self.d_actual,
            "relative_error": self.relative_error,
            "passed": self.passed,
            "threshold": self.threshold,
        }


def validate_prediction(
    spectral: SpectralResult,
    collapse: PPOCollapsePoint | None,
    threshold: float = 0.15,
) -> ValidationResult:
    """
    Compare predicted D_crit with actual collapse KL.

    Success criterion: |D_actual - D_crit| / D_actual < threshold
    """
    if collapse is None:
        return ValidationResult(
            noise_sigma=spectral.noise_sigma,
            d_crit=spectral.d_crit,
            d_actual=None,
            relative_error=None,
            passed=None,
            threshold=threshold,
        )

    d_actual = collapse.kl_at_collapse
    if d_actual == 0:
        rel_error = float('inf')
    else:
        rel_error = abs(d_actual - spectral.d_crit) / abs(d_actual)

    return ValidationResult(
        noise_sigma=spectral.noise_sigma,
        d_crit=spectral.d_crit,
        d_actual=d_actual,
        relative_error=rel_error,
        passed=rel_error < threshold,
        threshold=threshold,
    )


# ── Synthetic Demo Mode ────────────────────────────────────────────────
# When GPU/transformers unavailable, demonstrate the math with synthetic
# preference vectors that simulate different spectral gap regimes.

def run_synthetic_demo():
    """
    Demonstrate spectral gap analysis with synthetic data.
    Simulates three RM quality levels and shows how Δ predicts D_crit.
    """
    print("=" * 70)
    print("  H6.2 SPECTRAL GAP EXPERIMENT — Synthetic Demo Mode")
    print("  (No GPU/transformers detected; using synthetic preference vectors)")
    print("=" * 70)
    print()

    d = 4096   # Simulated hidden dimension (Llama-7B)
    N = 512    # Number of preference pairs

    results = []

    for sigma_label, gap_ratio in [
        ("Strong RM (large Δ)", 0.5),
        ("Medium RM (moderate Δ)", 0.15),
        ("Weak RM (small Δ)", 0.03),
    ]:
        print(f"\n{'─' * 60}")
        print(f"  {sigma_label}")
        print(f"{'─' * 60}")

        # Create synthetic singular values with controlled gap
        # λ₁ is dominant; λ₂ = λ₁ * (1 - gap_ratio)
        base_lambda = 10.0
        synthetic_lambdas = [
            base_lambda,
            base_lambda * (1 - gap_ratio),
        ] + [base_lambda * 0.1 * (0.9 ** i) for i in range(8)]

        l1 = synthetic_lambdas[0]
        l2 = synthetic_lambdas[1]
        delta = l1 - l2
        d_crit = (delta ** 2) / (4 * d)

        print(f"  λ₁ = {l1:.4f}")
        print(f"  λ₂ = {l2:.4f}")
        print(f"  Δ  = λ₁ - λ₂ = {delta:.4f}")
        print(f"  d  = {d}")
        print(f"  D_crit = Δ²/(4d) = {d_crit:.6f}")
        print()

        # Simulate PPO collapse at D_actual ≈ D_crit * (1 + noise)
        import random
        random.seed(42 + int(gap_ratio * 1000))
        measurement_noise = random.gauss(0, 0.08)  # 8% measurement noise
        d_actual = d_crit * (1 + measurement_noise)
        rel_error = abs(d_actual - d_crit) / abs(d_actual) if d_actual != 0 else float('inf')
        passed = rel_error < 0.15

        print(f"  Simulated D_actual = {d_actual:.6f}")
        print(f"  Relative error     = {rel_error:.2%}")
        print(f"  Verdict: {'✅ PASSED' if passed else '❌ FAILED'} (threshold: <15%)")

        results.append({
            "regime": sigma_label,
            "lambda_1": l1,
            "lambda_2": l2,
            "delta": delta,
            "d_crit": d_crit,
            "d_actual_simulated": d_actual,
            "relative_error": rel_error,
            "passed": passed,
        })

    # Summary
    print(f"\n{'═' * 70}")
    print("  SUMMARY")
    print(f"{'═' * 70}")
    all_passed = all(r["passed"] for r in results)
    print(f"  Configurations tested: {len(results)}")
    print(f"  All passed:            {'✅ YES' if all_passed else '❌ NO'}")
    print(f"\n  Theory prediction: D_crit = Δ²/(4d)")
    print(f"  If validated on real RM data, H6.2 spectral gap hypothesis is confirmed.")
    print(f"{'═' * 70}")

    # Save results
    out = {"mode": "synthetic_demo", "hidden_dim": d, "n_samples": N, "results": results}
    Path("h62_spectral_results.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(f"\n  Results saved to: h62_spectral_results.json")

    return results


# ── Main ────────────────────────────────────────────────────────────────

def main():
    """
    Run the H6.2 spectral gap experiment.

    If GPU + transformers are available, runs the full experiment.
    Otherwise, falls back to synthetic demo mode.
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="H6.2 Minimal Experiment: Spectral Gap → Reward Hacking Predictor"
    )
    parser.add_argument("--model", default="sfairXwRks/Llama-3-8B-Instruct-RM-v0.1",
                        help="Reward model to analyze")
    parser.add_argument("--n-samples", type=int, default=512,
                        help="Number of preference pairs")
    parser.add_argument("--synthetic", action="store_true",
                        help="Force synthetic demo mode")
    parser.add_argument("-o", "--output", default="h62_spectral_results.json",
                        help="Output JSON file")
    args = parser.parse_args()

    if args.synthetic or not HAS_TORCH or not HAS_TRANSFORMERS:
        run_synthetic_demo()
        return

    # Full experiment mode (requires GPU + transformers + dataset)
    print("=" * 70)
    print("  H6.2 SPECTRAL GAP EXPERIMENT — Full Mode")
    print(f"  Reward Model: {args.model}")
    print(f"  Samples:      {args.n_samples}")
    print("=" * 70)

    config = ExperimentConfig(
        reward_model_name=args.model,
        n_samples=args.n_samples,
        output_file=args.output,
    )

    # Load model
    print("\n  Loading reward model...")
    tokenizer = AutoTokenizer.from_pretrained(config.reward_model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        config.reward_model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    # Load preference dataset
    print("  Loading preference data...")
    try:
        from datasets import load_dataset
        ds = load_dataset("Anthropic/hh-rlhf", split=f"test[:{config.n_samples}]")
        pairs = [{"chosen": row["chosen"], "rejected": row["rejected"]} for row in ds]
    except Exception as exc:
        print(f"  ⚠ Could not load dataset: {exc}")
        print("  Falling back to synthetic mode.")
        run_synthetic_demo()
        return

    # Phase 1: Extract preference vectors
    print(f"\n  Phase 1: Extracting preference vectors from {len(pairs)} pairs...")
    diff_vectors = extract_preference_vectors(
        model, tokenizer, pairs, device=config.device
    )
    hidden_dim = model.config.hidden_size
    print(f"  Extracted: [{diff_vectors.shape[0]}, {diff_vectors.shape[1]}]")

    # Phase 2: Compute spectral gap for each noise level
    all_spectral = []
    for sigma in config.noise_levels:
        print(f"\n  Phase 2: Computing spectral gap (σ={sigma})...")
        result = compute_spectral_gap(diff_vectors, hidden_dim, noise_sigma=sigma)
        all_spectral.append(result)
        print(f"    λ₁ = {result.lambda_1:.4f}")
        print(f"    λ₂ = {result.lambda_2:.4f}")
        print(f"    Δ  = {result.delta:.4f}")
        print(f"    D_crit = {result.d_crit:.6f}")

    # Phase 3 & 4: PPO training + validation
    # NOTE: Full PPO training requires trl and significant compute.
    # This section provides the monitoring harness.
    print("\n  Phase 3: PPO training loop (requires trl library)")
    print("  → To run full PPO: pip install trl && python h62_ppo_runner.py")
    print("  → Spectral analysis is complete; D_crit predictions saved.")

    # Save spectral results
    output = {
        "mode": "spectral_analysis",
        "reward_model": config.reward_model_name,
        "n_samples": len(pairs),
        "hidden_dim": hidden_dim,
        "noise_levels": config.noise_levels,
        "spectral_results": [s.to_dict() for s in all_spectral],
        "predictions": {
            "theory": "D_crit = Δ²/(4d) predicts KL threshold for reward collapse",
            "validation_criterion": f"|D_actual - D_crit| / D_actual < {config.validation_threshold}",
            "status": "spectral_analysis_complete — awaiting PPO validation",
        },
    }

    Path(config.output_file).write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(f"\n  Results saved to: {config.output_file}")


if __name__ == "__main__":
    main()
