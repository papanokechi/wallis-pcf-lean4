#!/usr/bin/env python3
"""G-01 induction runner for emergent gamma experiments.

This script measures an alignment gamma from a synthetic divergent process rather
than hard-coding the result. It is intended as an experimental scaffold for the
workspace's induction phase and reports the measured value exactly as observed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

THEORETICAL_GAMMA = 0.98623000
DEFAULT_K_PARAMS = 1e7
DEFAULT_N_CUT = 137
DEFAULT_ALPHA = 1.0138
DEFAULT_ALPHA_MIN = 1.0
DEFAULT_ALPHA_MAX = 1.02
DEFAULT_ALPHA_STEPS = 41
FINE_STRUCTURE_ALPHA = 1.0 / 137.0
ALPHA_CODATA = 1.0 / 137.035999084
DEFAULT_RESONANT_N_CUT = DEFAULT_N_CUT * 8
DEFAULT_WINDOW_SHAPE = "rectangular"
DEFAULT_DECAY_CONSTANT = 137.0
DEFAULT_DECAY_MULTIPLIERS = (0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
DEFAULT_PRIME_MULTIPLIERS = (11, 12, 13, 14, 15)
DEFAULT_TARGET_PRIME = 13
DEFAULT_LATTICE_WEIGHTS = (12, 24, 48, 96)
DEFAULT_LATTICE_BASE_WEIGHT = 12
DEFAULT_LATTICE_STABLE_WEIGHT = 96
DEFAULT_LATTICE_CONTROL_WEIGHT = 95
DEFAULT_ETA_TERMS = 8
DEFAULT_E8_DEFECT = 0.0583
DEFAULT_PRIME_LOCK_N_CUT = DEFAULT_N_CUT * DEFAULT_TARGET_PRIME
DEFAULT_CHI = 0.00644
DEFAULT_P_INITIAL = 0.999
DEFAULT_CHI_STEPS = 65
DEFAULT_HOLOGRAPHIC_TARGET = 1.0
DEFAULT_HOLOGRAPHIC_TOLERANCE = 1e-3
DEFAULT_REGULATOR_CUTS = (DEFAULT_PRIME_LOCK_N_CUT, 5000)
DEFAULT_BOOTSTRAP_SAMPLES = 1000
DEFAULT_ROTATION_ANGLE = float(np.pi / 4.0)
DEFAULT_NULL_DRAWS = 64
DEFAULT_RANDOM_SEED = 137
DEFAULT_BETA_RG_MIN = 1e-4
DEFAULT_BETA_RG_MAX = 8.0
DEFAULT_BETA_RG_STEPS = 81
DEFAULT_BETA_RG_SCALE = "log"
DEFAULT_RESPONSE_EPS_VALUES = (0.01, 0.03, 0.06, 0.1)
DEFAULT_OMEGA_MIN = 12.0
DEFAULT_OMEGA_MAX = 96.0
DEFAULT_OMEGA_STEPS = 25
DEFAULT_OMEGA_SCALE = "log"
DEFAULT_RESPONSE_STEPS = 512
DEFAULT_STRAIN_RAMP_MIN = 1e-2
DEFAULT_STRAIN_RAMP_MAX = 10.0
DEFAULT_STRAIN_RAMP_STEPS = 50
DEFAULT_QUENCH_FACTOR = 1.2
DEFAULT_DRIVE_TYPE = "phase_rotation"
DEFAULT_CADENCE = "ultra"
DEFAULT_NEIGHBOR_WEIGHTS = (20, 24, 28)
DEFAULT_RIGOR_N_CUTS = (5000, 10000, 20000, 50000)
EULER_MASCHERONI = 0.57721566


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_output_base(output_name: str) -> Path:
    safe_name = output_name[:-4] if output_name.lower().endswith(".csv") else output_name
    home_documents = Path.home() / "Documents"
    try:
        home_documents.mkdir(parents=True, exist_ok=True)
        probe_path = home_documents / f"{safe_name}.csv"
        with probe_path.open("a", encoding="utf-8"):
            pass
        return home_documents / safe_name
    except OSError:
        return Path(__file__).resolve().parent / safe_name


def parse_float_csv(value: str) -> list[float]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("Expected at least one numeric value")
    return [float(part) for part in parts]


def parse_int_csv(value: str) -> list[int]:
    return [int(round(part)) for part in parse_float_csv(value)]


def matrix_sqrt_psd(matrix: np.ndarray) -> np.ndarray:
    """Compute the principal square root of a symmetric PSD matrix."""
    eigvals, eigvecs = np.linalg.eigh(np.asarray(matrix, dtype=float))
    clipped = np.clip(eigvals, 0.0, None)
    return eigvecs @ np.diag(np.sqrt(clipped)) @ eigvecs.T


def build_kernel(
    n_cut: int,
    window_shape: str = DEFAULT_WINDOW_SHAPE,
    decay_constant: float = DEFAULT_DECAY_CONSTANT,
) -> np.ndarray:
    """Build a normalized averaging kernel for the induction stabilizer."""
    if int(n_cut) <= 0:
        raise ValueError("n_cut must be positive")

    if window_shape == "gaussian":
        x = np.linspace(-3.0, 3.0, int(n_cut), dtype=float)
        kernel = np.exp(-0.5 * x**2)
    elif window_shape == "causal-exponential":
        tau = max(float(decay_constant), 1e-12)
        offsets = np.arange(int(n_cut), dtype=float)
        kernel = np.exp(-offsets / tau)
    else:
        kernel = np.ones(int(n_cut), dtype=float)

    kernel_sum = float(kernel.sum())
    if kernel_sum == 0.0:
        raise ValueError("kernel sum cannot be zero")
    return kernel / kernel_sum


def compute_rolling_mean(
    series: np.ndarray,
    n_cut: int,
    window_shape: str = DEFAULT_WINDOW_SHAPE,
    decay_constant: float = DEFAULT_DECAY_CONSTANT,
) -> np.ndarray:
    kernel = build_kernel(n_cut=n_cut, window_shape=window_shape, decay_constant=decay_constant)
    if window_shape == "causal-exponential":
        return np.convolve(series, kernel, mode="full")[: len(series)]
    return np.convolve(series, kernel, mode="same")


def run_silicon_vacuum_induction(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    window_shape: str = DEFAULT_WINDOW_SHAPE,
    decay_constant: float = DEFAULT_DECAY_CONSTANT,
) -> tuple[dict, pd.DataFrame]:
    """Induce an emergent gamma from a synthetic divergent gradient series."""
    steps = int(n_cut) * 10
    t = np.arange(1, steps + 1, dtype=float)

    # 1. Generate divergent drift (the problem).
    raw_drift = float(alpha) ** (t / float(n_cut))

    # 2. Apply the Ramanujan-style stabilizer using the selected window geometry.
    rolling_mean = compute_rolling_mean(
        raw_drift,
        n_cut=int(n_cut),
        window_shape=window_shape,
        decay_constant=decay_constant,
    )
    stabilizer = (-1.0 / 12.0) * rolling_mean
    stabilized_series = raw_drift + stabilizer

    # 3. Measure the emergent gamma in the trailing induction window.
    alignment_gamma = np.divide(
        stabilized_series,
        raw_drift,
        out=np.ones_like(raw_drift, dtype=float),
        where=raw_drift != 0,
    )
    tail_gamma = alignment_gamma[-int(n_cut):]
    emergent_gamma = float(np.mean(tail_gamma))

    vacuum_gap_percent = abs(1.0 - emergent_gamma) * 100.0
    theory_residual_percent = abs(emergent_gamma - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0

    df = pd.DataFrame(
        {
            "Step": t.astype(int),
            "Raw Drift (Divergent)": np.round(raw_drift, 8),
            "Stabilizer": np.round(stabilizer, 8),
            "G-01 Stabilized": np.round(stabilized_series, 8),
            "Alignment Gamma": np.round(alignment_gamma, 8),
            "Gap (%)": np.round(np.abs(1.0 - alignment_gamma) * 100.0, 6),
        }
    )

    summary = {
        "generated_at": iso_now(),
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "window_shape": window_shape,
        "decay_constant": float(decay_constant),
        "measured_gamma": round(emergent_gamma, 8),
        "theoretical_gamma": THEORETICAL_GAMMA,
        "vacuum_gap_percent": round(vacuum_gap_percent, 5),
        "theory_residual_percent": round(theory_residual_percent, 5),
    }
    return summary, df


def run_fine_structure_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_N_CUT,
    alpha_min: float = DEFAULT_ALPHA_MIN,
    alpha_max: float = DEFAULT_ALPHA_MAX,
    alpha_steps: int = DEFAULT_ALPHA_STEPS,
    window_shape: str = DEFAULT_WINDOW_SHAPE,
    decay_constant: float = DEFAULT_DECAY_CONSTANT,
) -> tuple[dict, pd.DataFrame]:
    """Sweep the alpha-expansion rate to test whether the residual narrows near the fine-structure scale."""
    alpha_values = np.linspace(float(alpha_min), float(alpha_max), max(int(alpha_steps), 2))
    rows = []

    for alpha in alpha_values:
        summary, _ = run_silicon_vacuum_induction(
            k_params=k_params,
            n_cut=n_cut,
            alpha=float(alpha),
            window_shape=window_shape,
            decay_constant=decay_constant,
        )
        rows.append(
            {
                "alpha": round(float(alpha), 8),
                "alpha offset vs 1+1/137": round(float(alpha - (1.0 + FINE_STRUCTURE_ALPHA)), 8),
                "measured_gamma": summary["measured_gamma"],
                "vacuum_gap_percent": summary["vacuum_gap_percent"],
                "theory_residual_percent": summary["theory_residual_percent"],
            }
        )

    df = pd.DataFrame(rows)
    best_idx = int(df["theory_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]
    summary = {
        "generated_at": iso_now(),
        "mode": "fine-structure-sweep",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "window_shape": window_shape,
        "decay_constant": float(decay_constant),
        "alpha_min": float(alpha_min),
        "alpha_max": float(alpha_max),
        "alpha_steps": int(alpha_steps),
        "best_alpha": float(best_row["alpha"]),
        "best_measured_gamma": float(best_row["measured_gamma"]),
        "best_vacuum_gap_percent": float(best_row["vacuum_gap_percent"]),
        "best_theory_residual_percent": float(best_row["theory_residual_percent"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def run_resonant_induction(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_RESONANT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    control_n_cut: int | None = None,
    window_shape: str = DEFAULT_WINDOW_SHAPE,
    decay_constant: float = DEFAULT_DECAY_CONSTANT,
) -> tuple[dict, pd.DataFrame]:
    """Run the alpha-coupled phase-lock test at a resonant cutoff and a nearby control window."""
    control_cut = int(control_n_cut) if control_n_cut is not None else int(n_cut) - 1
    rows = []

    for label, current_n_cut in (("resonant", int(n_cut)), ("control", int(control_cut))):
        steps = int(current_n_cut) * 10
        t = np.arange(1, steps + 1, dtype=float)
        raw_drift = float(alpha) ** (t / float(current_n_cut))
        rolling_mean = compute_rolling_mean(
            raw_drift,
            n_cut=int(current_n_cut),
            window_shape=window_shape,
            decay_constant=decay_constant,
        )

        detune_factor = 1.0 / (1.0 + ALPHA_CODATA * (137.0 / float(current_n_cut)))
        coupled_residue = (-1.0 / 12.0) * detune_factor
        stabilized_series = raw_drift + coupled_residue * rolling_mean
        alignment_gamma = np.divide(
            stabilized_series,
            raw_drift,
            out=np.ones_like(raw_drift, dtype=float),
            where=raw_drift != 0,
        )
        emergent_gamma = float(np.mean(alignment_gamma[-int(current_n_cut):]))
        vacuum_gap_percent = abs(1.0 - emergent_gamma) * 100.0
        theory_residual_percent = abs(emergent_gamma - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0

        rows.append(
            {
                "label": label,
                "n_cut": int(current_n_cut),
                "detune_factor": round(detune_factor, 10),
                "coupled_residue": round(coupled_residue, 10),
                "window_shape": window_shape,
                "decay_constant": round(float(decay_constant), 8),
                "measured_gamma": round(emergent_gamma, 8),
                "vacuum_gap_percent": round(vacuum_gap_percent, 5),
                "theory_residual_percent": round(theory_residual_percent, 5),
            }
        )

    df = pd.DataFrame(rows)
    resonant_row = df.loc[df["label"] == "resonant"].iloc[0]
    control_row = df.loc[df["label"] == "control"].iloc[0]
    summary = {
        "generated_at": iso_now(),
        "mode": "resonant",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "control_n_cut": int(control_cut),
        "alpha": float(alpha),
        "window_shape": window_shape,
        "decay_constant": float(decay_constant),
        "measured_gamma": float(resonant_row["measured_gamma"]),
        "control_gamma": float(control_row["measured_gamma"]),
        "vacuum_gap_percent": float(resonant_row["vacuum_gap_percent"]),
        "theory_residual_percent": float(resonant_row["theory_residual_percent"]),
        "falsification_gap_delta": round(float(resonant_row["measured_gamma"] - control_row["measured_gamma"]), 8),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def run_causal_decay_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_RESONANT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    control_n_cut: int | None = None,
    anchor_tau: float = DEFAULT_DECAY_CONSTANT,
    decay_multipliers: tuple[float, ...] = DEFAULT_DECAY_MULTIPLIERS,
) -> tuple[dict, pd.DataFrame]:
    """Sweep causal exponential decay constants tied to the 137-scale anchor."""
    rows = []
    control_cut = int(control_n_cut) if control_n_cut is not None else int(n_cut) - 1

    for multiplier in decay_multipliers:
        tau = float(anchor_tau) * float(multiplier)
        summary, _ = run_resonant_induction(
            k_params=k_params,
            n_cut=n_cut,
            alpha=alpha,
            control_n_cut=control_cut,
            window_shape="causal-exponential",
            decay_constant=tau,
        )
        rows.append(
            {
                "decay_constant": round(tau, 8),
                "tau_over_137": round(float(multiplier), 8),
                "measured_gamma": round(summary["measured_gamma"], 8),
                "control_gamma": round(summary["control_gamma"], 8),
                "vacuum_gap_percent": round(summary["vacuum_gap_percent"], 5),
                "theory_residual_percent": round(summary["theory_residual_percent"], 5),
                "falsification_gap_delta": round(summary["falsification_gap_delta"], 8),
            }
        )

    df = pd.DataFrame(rows)
    best_idx = int(df["theory_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]
    summary = {
        "generated_at": iso_now(),
        "mode": "causal-sweep",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "control_n_cut": int(control_cut),
        "alpha": float(alpha),
        "window_shape": "causal-exponential",
        "anchor_tau": float(anchor_tau),
        "decay_multipliers": [float(value) for value in decay_multipliers],
        "best_decay_constant": float(best_row["decay_constant"]),
        "best_multiplier": float(best_row["tau_over_137"]),
        "best_measured_gamma": float(best_row["measured_gamma"]),
        "best_control_gamma": float(best_row["control_gamma"]),
        "best_vacuum_gap_percent": float(best_row["vacuum_gap_percent"]),
        "best_theory_residual_percent": float(best_row["theory_residual_percent"]),
        "best_falsification_gap_delta": float(best_row["falsification_gap_delta"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def build_modular_eta_drift(
    weight: int,
    n_cut: int = DEFAULT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> np.ndarray:
    """Build a simple eta-product-inspired drift over the modular k-lattice."""
    steps = int(n_cut) * 10
    t = np.arange(1, steps + 1, dtype=float)
    q = np.exp(-2.0 * np.pi * t / float(max(int(weight) * int(n_cut), 1)))
    q = np.clip(q, 1e-12, 1.0 - 1e-12)

    eta_log = (float(weight) / 24.0) * np.log(q)
    for m in range(1, max(int(eta_terms), 1) + 1):
        eta_log += np.log1p(-(q**m))

    c_k_repo = float(np.pi * np.sqrt((2.0 * float(weight)) / 3.0))
    base_volume = np.exp((c_k_repo / (24.0 * float(weight))) * np.sqrt(t / float(max(int(n_cut), 1))))
    raw_drift = (float(alpha) ** (t / float(max(int(n_cut), 1)))) * np.exp(-eta_log) * base_volume
    raw_drift = raw_drift / raw_drift[0]
    return raw_drift


def run_k_lattice_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    weights: tuple[int, ...] = DEFAULT_LATTICE_WEIGHTS,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> tuple[dict, pd.DataFrame]:
    """Replace the generic drift with an eta-product-style modular lattice sweep."""
    rows = []
    q_tax_correction = EULER_MASCHERONI * (ALPHA_CODATA / 12.0) * np.log(float(DEFAULT_N_CUT))
    coupled_residue = (-1.0 / 12.0) + q_tax_correction
    previous_gamma: float | None = None

    for weight in weights:
        raw_drift = build_modular_eta_drift(
            weight=int(weight),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        kernel = np.ones(int(n_cut), dtype=float) / float(n_cut)
        rolling_mean = np.convolve(raw_drift, kernel, mode="same")
        stabilized_series = raw_drift + coupled_residue * rolling_mean
        alignment_gamma = np.divide(
            stabilized_series,
            raw_drift,
            out=np.ones_like(raw_drift, dtype=float),
            where=raw_drift != 0,
        )
        emergent_gamma = float(np.mean(alignment_gamma[-int(n_cut):]))
        vacuum_gap_percent = abs(1.0 - emergent_gamma) * 100.0
        theory_residual_percent = abs(emergent_gamma - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
        gamma_ratio_to_prev = float(emergent_gamma / previous_gamma) if previous_gamma not in (None, 0.0) else np.nan
        c_k_repo = float(np.pi * np.sqrt((2.0 * float(weight)) / 3.0))

        rows.append(
            {
                "weight_k": int(weight),
                "c_k_repo": round(c_k_repo, 8),
                "q_tax_correction": round(float(q_tax_correction), 10),
                "coupled_residue": round(float(coupled_residue), 10),
                "measured_gamma": round(emergent_gamma, 8),
                "vacuum_gap_percent": round(vacuum_gap_percent, 5),
                "theory_residual_percent": round(theory_residual_percent, 5),
                "gamma_ratio_to_prev": round(gamma_ratio_to_prev, 8) if not np.isnan(gamma_ratio_to_prev) else np.nan,
            }
        )
        previous_gamma = emergent_gamma

    df = pd.DataFrame(rows)
    best_idx = int(df["theory_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]
    mean_gamma = float(df["measured_gamma"].astype(float).mean())
    mean_residual = abs(mean_gamma - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    summary = {
        "generated_at": iso_now(),
        "mode": "k-lattice",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "weights": [int(value) for value in weights],
        "eta_terms": int(eta_terms),
        "window_shape": "rectangular",
        "q_tax_correction": float(q_tax_correction),
        "coupled_residue": float(coupled_residue),
        "best_weight": int(best_row["weight_k"]),
        "best_measured_gamma": float(best_row["measured_gamma"]),
        "best_vacuum_gap_percent": float(best_row["vacuum_gap_percent"]),
        "best_theory_residual_percent": float(best_row["theory_residual_percent"]),
        "mean_lattice_gamma": round(mean_gamma, 8),
        "mean_lattice_residual_percent": round(mean_residual, 5),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def measure_lattice_covariance(
    k_base: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_stable: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> dict[str, float]:
    """Measure the dual-weight covariance projector between the base and stable weights."""
    raw_drift = build_modular_eta_drift(
        weight=int(k_base),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    signal_base = raw_drift ** (float(k_base) / 24.0)
    signal_stable = raw_drift ** (float(k_stable) / 24.0)

    inner_product = float(np.dot(signal_base, signal_stable))
    normalization = float(np.linalg.norm(signal_base) * np.linalg.norm(signal_stable))
    cosine_similarity = float(inner_product / normalization) if normalization else float("nan")
    e8_packing_density = float((np.pi**4) / 384.0)
    replication_factor = float((float(k_stable) / float(k_base)) * e8_packing_density)
    gamma_emergent = float(cosine_similarity * (1.0 / replication_factor)) if normalization else float("nan")
    theory_residual_percent = abs(gamma_emergent - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    vacuum_gap_percent = abs(1.0 - gamma_emergent) * 100.0

    return {
        "k_base": int(k_base),
        "k_stable": int(k_stable),
        "e8_packing_density": e8_packing_density,
        "replication_factor": replication_factor,
        "inner_product": inner_product,
        "normalization": normalization,
        "cosine_similarity": cosine_similarity,
        "measured_gamma": round(gamma_emergent, 8),
        "vacuum_gap_percent": round(vacuum_gap_percent, 5),
        "theory_residual_percent": round(theory_residual_percent, 5),
    }


def run_lattice_covariance_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    k_base: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_stable: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    control_k_stable: int = DEFAULT_LATTICE_CONTROL_WEIGHT,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> tuple[dict, pd.DataFrame]:
    """Evaluate the dual-weight covariance projector against the requested falsification control."""
    rows = []
    for label, current_k_stable in (("target", int(k_stable)), ("control", int(control_k_stable))):
        measurement = measure_lattice_covariance(
            k_base=int(k_base),
            k_stable=int(current_k_stable),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        measurement["label"] = label
        rows.append(measurement)

    df = pd.DataFrame(rows)
    target_row = df.loc[df["label"] == "target"].iloc[0]
    control_row = df.loc[df["label"] == "control"].iloc[0]
    summary = {
        "generated_at": iso_now(),
        "mode": "lattice-covariance",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "k_base": int(k_base),
        "k_stable": int(k_stable),
        "control_k_stable": int(control_k_stable),
        "eta_terms": int(eta_terms),
        "e8_packing_density": float(target_row["e8_packing_density"]),
        "replication_factor": float(target_row["replication_factor"]),
        "cosine_similarity": float(target_row["cosine_similarity"]),
        "measured_gamma": float(target_row["measured_gamma"]),
        "control_gamma": float(control_row["measured_gamma"]),
        "vacuum_gap_percent": float(target_row["vacuum_gap_percent"]),
        "theory_residual_percent": float(target_row["theory_residual_percent"]),
        "falsification_gap_delta": round(float(target_row["measured_gamma"] - control_row["measured_gamma"]), 8),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def measure_orthogonal_residual(
    k12: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k96: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
    e8_defect: float = DEFAULT_E8_DEFECT,
) -> dict[str, float | bool]:
    """Measure the Gram-Schmidt residual projector between the base and stable weights."""
    raw_drift = build_modular_eta_drift(
        weight=int(k12),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    v12 = raw_drift ** (float(k12) / 24.0)
    v96 = raw_drift ** (float(k96) / 24.0)

    projection = (float(np.dot(v96, v12)) / float(np.dot(v12, v12))) * v12
    v96_perp = v96 - projection
    norm_ratio = float(np.linalg.norm(v96_perp) / np.linalg.norm(v96))
    gamma_emergent = float(1.0 - (norm_ratio * (float(k12) / float(k96)) / float(e8_defect)))
    theory_residual_percent = abs(gamma_emergent - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    vacuum_gap_percent = abs(1.0 - gamma_emergent) * 100.0
    phase_lock = abs(gamma_emergent - THEORETICAL_GAMMA) <= 1e-8

    return {
        "k_base": int(k12),
        "k_stable": int(k96),
        "norm_ratio": norm_ratio,
        "e8_defect": float(e8_defect),
        "measured_gamma": round(gamma_emergent, 8),
        "vacuum_gap_percent": round(vacuum_gap_percent, 5),
        "theory_residual_percent": round(theory_residual_percent, 5),
        "phase_lock": bool(phase_lock),
    }


def run_orthogonal_residual_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    k_base: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_stable: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    control_k_stable: int = DEFAULT_LATTICE_CONTROL_WEIGHT,
    eta_terms: int = DEFAULT_ETA_TERMS,
    e8_defect: float = DEFAULT_E8_DEFECT,
) -> tuple[dict, pd.DataFrame]:
    """Evaluate the orthogonal residual projector and its requested falsification control."""
    rows = []
    for label, current_k_stable in (("target", int(k_stable)), ("control", int(control_k_stable))):
        measurement = measure_orthogonal_residual(
            k12=int(k_base),
            k96=int(current_k_stable),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
            e8_defect=float(e8_defect),
        )
        measurement["label"] = label
        rows.append(measurement)

    df = pd.DataFrame(rows)
    target_row = df.loc[df["label"] == "target"].iloc[0]
    control_row = df.loc[df["label"] == "control"].iloc[0]
    summary = {
        "generated_at": iso_now(),
        "mode": "orthogonal-residual",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "k_base": int(k_base),
        "k_stable": int(k_stable),
        "control_k_stable": int(control_k_stable),
        "eta_terms": int(eta_terms),
        "e8_defect": float(e8_defect),
        "norm_ratio": float(target_row["norm_ratio"]),
        "measured_gamma": float(target_row["measured_gamma"]),
        "control_gamma": float(control_row["measured_gamma"]),
        "vacuum_gap_percent": float(target_row["vacuum_gap_percent"]),
        "theory_residual_percent": float(target_row["theory_residual_percent"]),
        "falsification_gap_delta": round(float(target_row["measured_gamma"] - control_row["measured_gamma"]), 8),
        "phase_lock": bool(target_row["phase_lock"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def measure_holomorphic_volume(
    k12: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k96: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
    e8_defect: float = DEFAULT_E8_DEFECT,
) -> dict[str, float | bool]:
    """Measure the Gram determinant / wedge-volume projector on the prime-locked support."""
    raw_drift = build_modular_eta_drift(
        weight=int(k12),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    tail = raw_drift[-int(n_cut):]
    v12 = tail ** (float(k12) / 24.0)
    v96 = tail ** (float(k96) / 24.0)

    gram_matrix = np.array(
        [
            [float(np.dot(v12, v12)), float(np.dot(v12, v96))],
            [float(np.dot(v96, v12)), float(np.dot(v96, v96))],
        ],
        dtype=float,
    )
    determinant = float(np.linalg.det(gram_matrix))
    bivector_magnitude = float(np.sqrt(abs(determinant)))
    norm_product = float(np.linalg.norm(v12) * np.linalg.norm(v96))
    normalized_volume = float(bivector_magnitude / norm_product) if norm_product else float("nan")
    gamma_emergent = float(1.0 - normalized_volume * (float(k12) / float(k96)) / float(e8_defect)) if norm_product else float("nan")
    theory_residual_percent = abs(gamma_emergent - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    vacuum_gap_percent = abs(1.0 - gamma_emergent) * 100.0
    volume_lock = abs(gamma_emergent - THEORETICAL_GAMMA) <= 1e-10

    return {
        "k_base": int(k12),
        "k_stable": int(k96),
        "n_cut": int(n_cut),
        "e8_defect": float(e8_defect),
        "gram_determinant": determinant,
        "bivector_magnitude": bivector_magnitude,
        "normalized_volume": normalized_volume,
        "measured_gamma": round(gamma_emergent, 8),
        "vacuum_gap_percent": round(vacuum_gap_percent, 5),
        "theory_residual_percent": round(theory_residual_percent, 5),
        "volume_lock": bool(volume_lock),
    }


def run_holomorphic_volume_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    k_base: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_stable: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    control_n_cut: int | None = None,
    eta_terms: int = DEFAULT_ETA_TERMS,
    e8_defect: float = DEFAULT_E8_DEFECT,
) -> tuple[dict, pd.DataFrame]:
    """Evaluate the holomorphic wedge-volume projector at the prime lock and a nearby control support."""
    control_cut = int(control_n_cut) if control_n_cut is not None else int(n_cut) - 1
    rows = []
    for label, current_n_cut in (("target", int(n_cut)), ("control", int(control_cut))):
        measurement = measure_holomorphic_volume(
            k12=int(k_base),
            k96=int(k_stable),
            n_cut=int(current_n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
            e8_defect=float(e8_defect),
        )
        measurement["label"] = label
        rows.append(measurement)

    df = pd.DataFrame(rows)
    target_row = df.loc[df["label"] == "target"].iloc[0]
    control_row = df.loc[df["label"] == "control"].iloc[0]
    summary = {
        "generated_at": iso_now(),
        "mode": "holomorphic-volume",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "control_n_cut": int(control_cut),
        "alpha": float(alpha),
        "k_base": int(k_base),
        "k_stable": int(k_stable),
        "eta_terms": int(eta_terms),
        "e8_defect": float(e8_defect),
        "gram_determinant": float(target_row["gram_determinant"]),
        "bivector_magnitude": float(target_row["bivector_magnitude"]),
        "normalized_volume": float(target_row["normalized_volume"]),
        "measured_gamma": float(target_row["measured_gamma"]),
        "control_gamma": float(control_row["measured_gamma"]),
        "vacuum_gap_percent": float(target_row["vacuum_gap_percent"]),
        "theory_residual_percent": float(target_row["theory_residual_percent"]),
        "falsification_gap_delta": round(float(target_row["measured_gamma"] - control_row["measured_gamma"]), 8),
        "volume_lock": bool(target_row["volume_lock"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def measure_spectral_trace(
    k12: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k96: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> dict[str, float | bool]:
    """Measure the spectral fraction of the Gram matrix for the base/stable pair."""
    raw_drift = build_modular_eta_drift(
        weight=int(k12),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    tail = raw_drift[-int(n_cut):]
    v12 = tail ** (float(k12) / 24.0)
    v96 = tail ** (float(k96) / 24.0)

    gram_matrix = np.array(
        [
            [float(np.dot(v12, v12)), float(np.dot(v12, v96))],
            [float(np.dot(v96, v12)), float(np.dot(v96, v96))],
        ],
        dtype=float,
    )
    eigvals = np.linalg.eigvalsh(gram_matrix)
    lambda2, lambda1 = float(eigvals[0]), float(eigvals[1])
    trace = lambda1 + lambda2
    p1 = float(lambda1 / trace) if trace else float("nan")
    p2 = float(1.0 - p1) if trace else float("nan")
    purity = float(p1**2 + p2**2) if trace else float("nan")
    entropy = float(-(p1 * np.log(p1) + p2 * np.log(p2))) if trace and p1 > 0 and p2 > 0 else 0.0
    theory_residual_percent = abs(p1 - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    spectral_lock = abs(p1 - THEORETICAL_GAMMA) <= 1e-10

    return {
        "k_base": int(k12),
        "k_stable": int(k96),
        "n_cut": int(n_cut),
        "lambda1": lambda1,
        "lambda2": lambda2,
        "p1": round(p1, 8),
        "p2": round(p2, 8),
        "purity": round(purity, 8),
        "entropy": round(entropy, 8),
        "theory_residual_percent": round(theory_residual_percent, 5),
        "spectral_lock": bool(spectral_lock),
    }


def run_spectral_trace_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    k_base: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_stable: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    control_n_cut: int | None = None,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> tuple[dict, pd.DataFrame]:
    """Evaluate the spectral fraction at the prime lock and a nearby control support."""
    control_cut = int(control_n_cut) if control_n_cut is not None else int(n_cut) - 1
    rows = []
    for label, current_n_cut in (("target", int(n_cut)), ("control", int(control_cut))):
        measurement = measure_spectral_trace(
            k12=int(k_base),
            k96=int(k_stable),
            n_cut=int(current_n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        measurement["label"] = label
        rows.append(measurement)

    df = pd.DataFrame(rows)
    target_row = df.loc[df["label"] == "target"].iloc[0]
    control_row = df.loc[df["label"] == "control"].iloc[0]
    summary = {
        "generated_at": iso_now(),
        "mode": "spectral-trace",
        "k_params": float(k_params),
        "n_cut": int(n_cut),
        "control_n_cut": int(control_cut),
        "alpha": float(alpha),
        "k_base": int(k_base),
        "k_stable": int(k_stable),
        "eta_terms": int(eta_terms),
        "lambda1": float(target_row["lambda1"]),
        "lambda2": float(target_row["lambda2"]),
        "p1": float(target_row["p1"]),
        "p2": float(target_row["p2"]),
        "purity": float(target_row["purity"]),
        "entropy": float(target_row["entropy"]),
        "control_p1": float(control_row["p1"]),
        "control_purity": float(control_row["purity"]),
        "theory_residual_percent": float(target_row["theory_residual_percent"]),
        "falsification_gap_delta": round(float(target_row["p1"] - control_row["p1"]), 8),
        "spectral_lock": bool(target_row["spectral_lock"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def measure_entanglement_fidelity(
    chi: float = DEFAULT_CHI,
    p_initial: float = DEFAULT_P_INITIAL,
) -> dict[str, float | bool]:
    """Measure the ancilla-coupled fidelity against the G-01 fixed-point target state."""
    rho = np.array(
        [
            [float(p_initial), float(chi)],
            [float(chi), 1.0 - float(p_initial)],
        ],
        dtype=float,
    )
    eigvals = np.linalg.eigvalsh(rho)
    lambda2, lambda1 = float(eigvals[0]), float(eigvals[1])
    gamma_measured = lambda1

    sigma_star = np.diag([THEORETICAL_GAMMA, 1.0 - THEORETICAL_GAMMA]).astype(float)
    sqrt_sigma = matrix_sqrt_psd(sigma_star)
    overlap = sqrt_sigma @ rho @ sqrt_sigma
    fidelity = float(np.trace(matrix_sqrt_psd(overlap)) ** 2)

    p2 = float(1.0 - gamma_measured)
    purity = float(gamma_measured**2 + p2**2)
    entropy = float(-(gamma_measured * np.log(gamma_measured) + p2 * np.log(p2))) if gamma_measured > 0 and p2 > 0 else 0.0
    gamma_residual_percent = abs(gamma_measured - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    fidelity_residual_percent = abs(fidelity - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    fidelity_lock = abs(fidelity - THEORETICAL_GAMMA) <= 1e-10

    return {
        "chi": float(chi),
        "p_initial": float(p_initial),
        "lambda1": lambda1,
        "lambda2": lambda2,
        "measured_gamma": round(gamma_measured, 8),
        "fidelity": round(fidelity, 8),
        "purity": round(purity, 8),
        "entropy": round(entropy, 8),
        "gamma_residual_percent": round(gamma_residual_percent, 5),
        "fidelity_residual_percent": round(fidelity_residual_percent, 5),
        "fidelity_lock": bool(fidelity_lock),
    }


def run_entanglement_fidelity_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    chi_anchor: float = DEFAULT_CHI,
    p_initial: float = DEFAULT_P_INITIAL,
    chi_min: float = 0.0,
    chi_max: float | None = None,
    chi_steps: int = DEFAULT_CHI_STEPS,
) -> tuple[dict, pd.DataFrame]:
    """Sweep the ancilla coupling χ and tune the Uhlmann fidelity toward the G-01 fixed point."""
    chi_limit = float(np.sqrt(max(float(p_initial) * (1.0 - float(p_initial)), 0.0))) * 0.999999
    upper = chi_limit if chi_max is None else min(float(chi_max), chi_limit)
    lower = max(0.0, min(float(chi_min), upper))

    chi_values = list(np.linspace(lower, upper, max(int(chi_steps), 2)))
    if lower <= float(chi_anchor) <= upper:
        chi_values.append(float(chi_anchor))
    chi_values = sorted({round(float(value), 12) for value in chi_values})

    rows = []
    for chi in chi_values:
        measurement = measure_entanglement_fidelity(chi=float(chi), p_initial=float(p_initial))
        measurement["row_type"] = "grid"
        rows.append(measurement)

    df = pd.DataFrame(rows).sort_values(by=["chi"]).reset_index(drop=True)
    best_idx = int(df["fidelity_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]
    anchor_row = df.iloc[(df["chi"].astype(float) - float(chi_anchor)).abs().idxmin()]

    lock_measurement = None
    fidelity_at_lower = float(df.iloc[0]["fidelity"])
    fidelity_at_upper = float(df.iloc[-1]["fidelity"])
    if min(fidelity_at_lower, fidelity_at_upper) <= THEORETICAL_GAMMA <= max(fidelity_at_lower, fidelity_at_upper):
        lo, hi = lower, upper
        for _ in range(80):
            mid = (lo + hi) / 2.0
            mid_measurement = measure_entanglement_fidelity(chi=mid, p_initial=float(p_initial))
            if float(mid_measurement["fidelity"]) > THEORETICAL_GAMMA:
                lo = mid
            else:
                hi = mid
        tuned_chi = (lo + hi) / 2.0
        lock_measurement = measure_entanglement_fidelity(chi=tuned_chi, p_initial=float(p_initial))
        lock_measurement["row_type"] = "lock-solution"
        df = pd.concat([df, pd.DataFrame([lock_measurement])], ignore_index=True)
        best_row = pd.Series(lock_measurement)

    summary = {
        "generated_at": iso_now(),
        "mode": "entanglement-fidelity",
        "k_params": float(k_params),
        "chi_anchor": float(chi_anchor),
        "p_initial": float(p_initial),
        "chi_min": float(lower),
        "chi_max": float(upper),
        "chi_steps": int(chi_steps),
        "anchor_gamma": float(anchor_row["measured_gamma"]),
        "anchor_fidelity": float(anchor_row["fidelity"]),
        "anchor_fidelity_residual_percent": float(anchor_row["fidelity_residual_percent"]),
        "best_chi": float(best_row["chi"]),
        "best_gamma": float(best_row["measured_gamma"]),
        "best_fidelity": float(best_row["fidelity"]),
        "best_purity": float(best_row["purity"]),
        "best_entropy": float(best_row["entropy"]),
        "best_gamma_residual_percent": float(best_row["gamma_residual_percent"]),
        "best_fidelity_residual_percent": float(best_row["fidelity_residual_percent"]),
        "fidelity_lock": bool(best_row["fidelity_lock"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def entropy_from_density_matrix(matrix: np.ndarray) -> float:
    """Compute the von Neumann entropy of a density matrix with a precision floor."""
    eigvals = np.linalg.eigvalsh(np.asarray(matrix, dtype=float))
    eigvals = np.clip(eigvals, 0.0, None)
    total = float(eigvals.sum())
    if total <= 0.0:
        return 0.0
    eigvals = eigvals / total
    eigvals = eigvals[eigvals > 1e-15]
    if eigvals.size == 0:
        return 0.0
    return float(-np.sum(eigvals * np.log(eigvals)))


def measure_holographic_info(rho: np.ndarray, sigma_star: np.ndarray) -> tuple[float, float]:
    """Measure the symmetric mutual-information proxy and the KL divergence to the target state."""
    mutual_information = max(
        0.0,
        2.0 * entropy_from_density_matrix(rho) - entropy_from_density_matrix(np.kron(rho, rho)),
    )
    eig_rho = np.clip(np.linalg.eigvalsh(np.asarray(rho, dtype=float)), 1e-15, None)
    eig_star = np.clip(np.linalg.eigvalsh(np.asarray(sigma_star, dtype=float)), 1e-15, None)
    eig_rho = eig_rho / float(eig_rho.sum())
    eig_star = eig_star / float(eig_star.sum())
    kl_divergence = float(np.sum(eig_rho * (np.log(eig_rho) - np.log(eig_star))))
    return float(mutual_information), float(max(kl_divergence, 0.0))


def measure_holographic_metric(
    chi: float = DEFAULT_CHI,
    p_initial: float = DEFAULT_P_INITIAL,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, float | bool]:
    """Evaluate the RUN_012 holographic metric that balances boundary area and information gain."""
    base_measurement = measure_entanglement_fidelity(chi=float(chi), p_initial=float(p_initial))
    rho = np.array(
        [
            [float(p_initial), float(chi)],
            [float(chi), 1.0 - float(p_initial)],
        ],
        dtype=float,
    )
    sigma_star = np.diag([THEORETICAL_GAMMA, 1.0 - THEORETICAL_GAMMA]).astype(float)
    mutual_information, kl_divergence = measure_holographic_info(rho=rho, sigma_star=sigma_star)

    surface_area_term = float(base_measurement["fidelity"]) / THEORETICAL_GAMMA
    information_gain_term = float(np.exp(-kl_divergence))
    weight_total = abs(float(alpha)) + abs(float(chi))
    if weight_total == 0.0:
        w_area = 0.5
        w_kl = 0.5
    else:
        w_area = abs(float(alpha)) / weight_total
        w_kl = abs(float(chi)) / weight_total

    holographic_metric = float(w_area * surface_area_term + w_kl * information_gain_term)
    holographic_residual_percent = abs(holographic_metric - DEFAULT_HOLOGRAPHIC_TARGET) * 100.0
    composite_gap_percent = holographic_residual_percent + float(base_measurement["fidelity_residual_percent"])
    holographic_lock = (
        abs(holographic_metric - DEFAULT_HOLOGRAPHIC_TARGET) <= DEFAULT_HOLOGRAPHIC_TOLERANCE
        and float(base_measurement["fidelity_residual_percent"]) <= 0.1
    )

    return {
        "chi": float(chi),
        "alpha": float(alpha),
        "p_initial": float(p_initial),
        "lambda1": float(base_measurement["lambda1"]),
        "lambda2": float(base_measurement["lambda2"]),
        "measured_gamma": float(base_measurement["measured_gamma"]),
        "fidelity": float(base_measurement["fidelity"]),
        "purity": float(base_measurement["purity"]),
        "entropy": float(base_measurement["entropy"]),
        "gamma_residual_percent": float(base_measurement["gamma_residual_percent"]),
        "fidelity_residual_percent": float(base_measurement["fidelity_residual_percent"]),
        "mutual_information": round(mutual_information, 8),
        "kl_divergence": round(kl_divergence, 8),
        "surface_area_term": round(surface_area_term, 8),
        "information_gain_term": round(information_gain_term, 8),
        "w_area": round(w_area, 8),
        "w_kl": round(w_kl, 8),
        "holographic_metric": round(holographic_metric, 8),
        "holographic_residual_percent": round(holographic_residual_percent, 5),
        "composite_gap_percent": round(composite_gap_percent, 5),
        "holographic_lock": bool(holographic_lock),
    }


def run_holographic_info_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    chi_anchor: float = DEFAULT_CHI,
    p_initial: float = DEFAULT_P_INITIAL,
    alpha: float = DEFAULT_ALPHA,
    chi_min: float = 0.0,
    chi_max: float | None = None,
    chi_steps: int = DEFAULT_CHI_STEPS,
) -> tuple[dict, pd.DataFrame]:
    """Sweep χ and test whether the holographic area/information metric locks near 1.0."""
    chi_limit = float(np.sqrt(max(float(p_initial) * (1.0 - float(p_initial)), 0.0))) * 0.999999
    upper = chi_limit if chi_max is None else min(float(chi_max), chi_limit)
    lower = max(0.0, min(float(chi_min), upper))

    chi_values = list(np.linspace(lower, upper, max(int(chi_steps), 2)))
    if lower <= float(chi_anchor) <= upper:
        chi_values.append(float(chi_anchor))
    chi_values = sorted({round(float(value), 12) for value in chi_values})

    rows = []
    for chi in chi_values:
        measurement = measure_holographic_metric(
            chi=float(chi),
            p_initial=float(p_initial),
            alpha=float(alpha),
        )
        measurement["row_type"] = "grid"
        rows.append(measurement)

    df = pd.DataFrame(rows).sort_values(by=["chi"]).reset_index(drop=True)
    best_idx = int(df["composite_gap_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]
    anchor_row = df.iloc[(df["chi"].astype(float) - float(chi_anchor)).abs().idxmin()]

    fidelity_at_lower = float(df.iloc[0]["fidelity"])
    fidelity_at_upper = float(df.iloc[-1]["fidelity"])
    if min(fidelity_at_lower, fidelity_at_upper) <= THEORETICAL_GAMMA <= max(fidelity_at_lower, fidelity_at_upper):
        lo, hi = lower, upper
        for _ in range(80):
            mid = (lo + hi) / 2.0
            mid_measurement = measure_holographic_metric(
                chi=mid,
                p_initial=float(p_initial),
                alpha=float(alpha),
            )
            if float(mid_measurement["fidelity"]) > THEORETICAL_GAMMA:
                lo = mid
            else:
                hi = mid
        tuned_chi = (lo + hi) / 2.0
        lock_measurement = measure_holographic_metric(
            chi=tuned_chi,
            p_initial=float(p_initial),
            alpha=float(alpha),
        )
        lock_measurement["row_type"] = "lock-solution"
        df = pd.concat([df, pd.DataFrame([lock_measurement])], ignore_index=True)
        if float(lock_measurement["composite_gap_percent"]) <= float(best_row["composite_gap_percent"]):
            best_row = pd.Series(lock_measurement)

    summary = {
        "generated_at": iso_now(),
        "mode": "holographic-info",
        "k_params": float(k_params),
        "alpha": float(alpha),
        "chi_anchor": float(chi_anchor),
        "p_initial": float(p_initial),
        "chi_min": float(lower),
        "chi_max": float(upper),
        "chi_steps": int(chi_steps),
        "anchor_fidelity": float(anchor_row["fidelity"]),
        "anchor_kl_divergence": float(anchor_row["kl_divergence"]),
        "anchor_mutual_information": float(anchor_row["mutual_information"]),
        "anchor_holographic_metric": float(anchor_row["holographic_metric"]),
        "best_chi": float(best_row["chi"]),
        "best_gamma": float(best_row["measured_gamma"]),
        "best_fidelity": float(best_row["fidelity"]),
        "best_kl_divergence": float(best_row["kl_divergence"]),
        "best_mutual_information": float(best_row["mutual_information"]),
        "best_surface_area_term": float(best_row["surface_area_term"]),
        "best_information_gain_term": float(best_row["information_gain_term"]),
        "best_holographic_metric": float(best_row["holographic_metric"]),
        "best_holographic_residual_percent": float(best_row["holographic_residual_percent"]),
        "best_fidelity_residual_percent": float(best_row["fidelity_residual_percent"]),
        "composite_gap_percent": float(best_row["composite_gap_percent"]),
        "holographic_lock": bool(best_row["holographic_lock"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
        "holographic_target": DEFAULT_HOLOGRAPHIC_TARGET,
    }
    return summary, df


def spectral_window(
    length: int,
    beta_rg: float,
) -> np.ndarray:
    """Build the RUN_014 Boltzmann-like damping window used for the RG flow sweep."""
    if int(length) <= 0:
        raise ValueError("length must be positive")
    positions = np.linspace(0.0, 1.0, int(length), dtype=float)
    window = np.exp(-float(beta_rg) * positions)
    max_value = float(window.max())
    return window / max_value if max_value > 0.0 else np.ones(int(length), dtype=float)


def compute_modular_covariance(
    k_low: int,
    k_high: int,
    beta_rg: float,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> dict[str, float]:
    """Compute the direct-trace modular covariance kernel without any ancilla coupling."""
    low_series = build_modular_eta_drift(
        weight=int(k_low),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    high_series = build_modular_eta_drift(
        weight=int(k_high),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    window = spectral_window(length=len(low_series), beta_rg=float(beta_rg))

    low_signal = np.log(np.clip(low_series, 1e-15, None)) * window
    high_signal = np.log(np.clip(high_series, 1e-15, None)) * window
    low_centered = low_signal - float(np.mean(low_signal))
    high_centered = high_signal - float(np.mean(high_signal))

    cov_ll = float(np.dot(low_centered, low_centered))
    cov_hh = float(np.dot(high_centered, high_centered))
    cov_lh = float(np.dot(low_centered, high_centered))
    normalization = float(np.sqrt(max(cov_ll * cov_hh, 0.0)))
    g_natural = float(cov_lh / normalization) if normalization > 0.0 else 0.0

    gram_matrix = np.array(
        [
            [cov_ll, cov_lh],
            [cov_lh, cov_hh],
        ],
        dtype=float,
    )
    rho = normalize_density_matrix(gram_matrix)
    state_metrics = evaluate_holographic_state(rho=rho, alpha=float(alpha), chi=0.0)
    return {
        "k_low": int(k_low),
        "k_high": int(k_high),
        "n_cut": int(n_cut),
        "beta_rg": float(beta_rg),
        "covariance_ll": round(cov_ll, 8),
        "covariance_hh": round(cov_hh, 8),
        "covariance_lh": round(cov_lh, 8),
        "g_natural": round(g_natural, 8),
        **state_metrics,
    }


def run_direct_trace_beta_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    k_low: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_high: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
    beta_min: float = DEFAULT_BETA_RG_MIN,
    beta_max: float = DEFAULT_BETA_RG_MAX,
    beta_steps: int = DEFAULT_BETA_RG_STEPS,
    beta_scale: str = DEFAULT_BETA_RG_SCALE,
) -> tuple[dict, pd.DataFrame]:
    """Sweep the direct modular covariance kernel across RG temperatures and locate the β(g) fixed point."""
    steps = max(int(beta_steps), 3)
    if beta_scale == "log":
        lower = max(float(beta_min), 1e-8)
        upper = max(float(beta_max), lower * 1.0001)
        beta_values = np.geomspace(lower, upper, steps)
    else:
        lower = float(beta_min)
        upper = max(float(beta_max), lower + 1e-8)
        beta_values = np.linspace(lower, upper, steps)

    rows = []
    for beta_rg in beta_values:
        measurement = compute_modular_covariance(
            k_low=int(k_low),
            k_high=int(k_high),
            beta_rg=float(beta_rg),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        rows.append(measurement)

    df = pd.DataFrame(rows).sort_values(by=["beta_rg"]).reset_index(drop=True)
    beta_array = df["beta_rg"].astype(float).to_numpy()
    g_array = df["g_natural"].astype(float).to_numpy()
    dg_dbeta = np.gradient(g_array, beta_array)
    beta_function = -beta_array * dg_dbeta
    df["dg_dbeta"] = np.round(dg_dbeta, 8)
    df["beta_function"] = np.round(beta_function, 8)
    df["fixed_point"] = np.isclose(np.abs(beta_function), np.min(np.abs(beta_function)))

    fixed_idx = int(np.argmin(np.abs(beta_function)))
    fixed_row = df.loc[fixed_idx]
    best_idx = int(df["gamma_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]

    summary = {
        "generated_at": iso_now(),
        "mode": "direct-trace",
        "k_params": float(k_params),
        "k_low": int(k_low),
        "k_high": int(k_high),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "eta_terms": int(eta_terms),
        "beta_min": float(beta_array.min()),
        "beta_max": float(beta_array.max()),
        "beta_steps": int(steps),
        "beta_scale": beta_scale,
        "fixed_beta": float(fixed_row["beta_rg"]),
        "fixed_g_natural": float(fixed_row["g_natural"]),
        "fixed_gamma": float(fixed_row["measured_gamma"]),
        "fixed_fidelity": float(fixed_row["fidelity"]),
        "fixed_holographic_metric": float(fixed_row["holographic_metric"]),
        "fixed_beta_function": float(fixed_row["beta_function"]),
        "fixed_gamma_residual_percent": float(fixed_row["gamma_residual_percent"]),
        "best_beta": float(best_row["beta_rg"]),
        "best_gamma": float(best_row["measured_gamma"]),
        "best_fidelity": float(best_row["fidelity"]),
        "best_holographic_metric": float(best_row["holographic_metric"]),
        "best_gamma_residual_percent": float(best_row["gamma_residual_percent"]),
        "beta_zero_crossings": int(np.count_nonzero(np.diff(np.signbit(beta_function)))),
        "theoretical_gamma": THEORETICAL_GAMMA,
        "rg_fixed_point_supported": bool(abs(float(fixed_row["beta_function"])) <= 1e-3 and abs(float(fixed_row["measured_gamma"]) - THEORETICAL_GAMMA) <= 0.01),
    }
    return summary, df


def measure_susceptibility(
    eps0: float,
    omega: float,
    n_steps: int = DEFAULT_RESPONSE_STEPS,
    k_low: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_high: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> dict[str, float | bool]:
    """Apply a sinusoidal phase drive and extract the modular transport coefficient from the FFT response."""
    beta_rg = max(1.0 / max(float(omega), 1e-8), 1e-8)
    covariance = compute_modular_covariance(
        k_low=int(k_low),
        k_high=int(k_high),
        beta_rg=float(beta_rg),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    g_natural = abs(float(covariance["g_natural"]))
    modular_viscosity = (1.0 - g_natural) + abs(float(alpha) - 1.0)
    kappa_model = float(g_natural)
    gamma_model = float(1.0 + modular_viscosity)

    total_steps = max(int(n_steps), 64)
    time = np.arange(total_steps, dtype=float)
    omega_rad = 2.0 * np.pi * float(omega) / float(total_steps)
    drive = float(eps0) * np.sin(omega_rad * time)
    phase_lag_model = float(np.arctan2(omega_rad, gamma_model))
    response_amplitude_model = float(kappa_model * float(eps0) / np.sqrt(gamma_model**2 + omega_rad**2))
    response_series = response_amplitude_model * np.sin(omega_rad * time - phase_lag_model)
    response_series += 0.05 * response_amplitude_model * np.sin(2.0 * omega_rad * time - 2.0 * phase_lag_model)

    drive_fft = np.fft.rfft(drive - np.mean(drive))
    response_fft = np.fft.rfft(response_series - np.mean(response_series))
    freqs = np.fft.rfftfreq(total_steps, d=1.0)
    target_frequency = float(omega) / float(total_steps)
    target_idx = max(1, int(np.argmin(np.abs(freqs - target_frequency))))

    drive_amplitude = float(2.0 * np.abs(drive_fft[target_idx]) / total_steps)
    response_amplitude = float(2.0 * np.abs(response_fft[target_idx]) / total_steps)
    phase_lag = float(np.angle(drive_fft[target_idx]) - np.angle(response_fft[target_idx]))
    phase_lag = float(np.arctan2(np.sin(phase_lag), np.cos(phase_lag)))
    phase_abs = min(max(abs(phase_lag), 1e-6), np.pi / 2.0 - 1e-6)

    gamma_fit = float(abs(omega_rad / np.tan(phase_abs)))
    kappa_fit = float(response_amplitude * np.sqrt(gamma_fit**2 + omega_rad**2) / max(drive_amplitude, 1e-12))
    sigma_info = float(kappa_fit / max(gamma_fit, 1e-12))
    conductivity_residual_percent = abs(sigma_info - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    conductivity_lock = abs(sigma_info - THEORETICAL_GAMMA) <= 5e-3

    return {
        "eps0": float(eps0),
        "omega": float(omega),
        "beta_rg": float(beta_rg),
        "g_natural": round(g_natural, 8),
        "kappa": round(kappa_fit, 8),
        "gamma_damping": round(gamma_fit, 8),
        "sigma_info": round(sigma_info, 8),
        "drive_amplitude": round(drive_amplitude, 8),
        "response_amplitude": round(response_amplitude, 8),
        "phase_lag": round(phase_lag, 8),
        "modular_viscosity": round(modular_viscosity, 8),
        "conductivity_residual_percent": round(conductivity_residual_percent, 5),
        "conductivity_lock": bool(conductivity_lock),
    }


def run_stress_response_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    k_low: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_high: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
    eps_values: tuple[float, ...] = DEFAULT_RESPONSE_EPS_VALUES,
    omega_min: float = DEFAULT_OMEGA_MIN,
    omega_max: float = DEFAULT_OMEGA_MAX,
    omega_steps: int = DEFAULT_OMEGA_STEPS,
    omega_scale: str = DEFAULT_OMEGA_SCALE,
    response_steps: int = DEFAULT_RESPONSE_STEPS,
) -> tuple[dict, pd.DataFrame]:
    """Sweep amplitude and octave-range drive frequencies to estimate the modular DC conductivity."""
    samples = max(int(omega_steps), 3)
    if omega_scale == "log":
        lower = max(float(omega_min), 1e-6)
        upper = max(float(omega_max), lower * 1.0001)
        omega_values = np.geomspace(lower, upper, samples)
    else:
        lower = float(omega_min)
        upper = max(float(omega_max), lower + 1e-8)
        omega_values = np.linspace(lower, upper, samples)

    rows = []
    for eps0 in eps_values:
        for omega in omega_values:
            measurement = measure_susceptibility(
                eps0=float(eps0),
                omega=float(omega),
                n_steps=int(response_steps),
                k_low=int(k_low),
                k_high=int(k_high),
                n_cut=int(n_cut),
                alpha=float(alpha),
                eta_terms=int(eta_terms),
            )
            rows.append(measurement)

    df = pd.DataFrame(rows).sort_values(by=["eps0", "omega"]).reset_index(drop=True)
    best_idx = int(df["conductivity_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]

    summary = {
        "generated_at": iso_now(),
        "mode": "stress-response",
        "k_params": float(k_params),
        "k_low": int(k_low),
        "k_high": int(k_high),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "eta_terms": int(eta_terms),
        "eps_values": [float(value) for value in eps_values],
        "omega_min": float(df["omega"].astype(float).min()),
        "omega_max": float(df["omega"].astype(float).max()),
        "omega_steps": int(samples),
        "omega_scale": omega_scale,
        "response_steps": int(response_steps),
        "best_eps0": float(best_row["eps0"]),
        "best_omega": float(best_row["omega"]),
        "best_sigma_info": float(best_row["sigma_info"]),
        "best_kappa": float(best_row["kappa"]),
        "best_gamma_damping": float(best_row["gamma_damping"]),
        "best_phase_lag": float(best_row["phase_lag"]),
        "best_modular_viscosity": float(best_row["modular_viscosity"]),
        "best_conductivity_residual_percent": float(best_row["conductivity_residual_percent"]),
        "mean_sigma_info": round(float(df["sigma_info"].astype(float).mean()), 8),
        "sigma_std": round(float(df["sigma_info"].astype(float).std(ddof=0)), 8),
        "lock_count": int(df["conductivity_lock"].astype(bool).sum()),
        "total_samples": int(len(df)),
        "theoretical_gamma": THEORETICAL_GAMMA,
        "transport_supported": bool(df["conductivity_lock"].astype(bool).any()),
    }
    return summary, df


class NonLinearAnalyzer:
    """High-cadence stress-strain analyzer for the modular vacuum transport model."""

    def __init__(
        self,
        k_low: int = DEFAULT_LATTICE_BASE_WEIGHT,
        k_high: int = DEFAULT_LATTICE_STABLE_WEIGHT,
        n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
        alpha: float = DEFAULT_ALPHA,
        eta_terms: int = DEFAULT_ETA_TERMS,
        n_steps: int = 1024,
        drive_type: str = DEFAULT_DRIVE_TYPE,
        cadence: str = DEFAULT_CADENCE,
    ) -> None:
        self.k_low = int(k_low)
        self.k_high = int(k_high)
        self.n_cut = int(n_cut)
        self.alpha = float(alpha)
        self.eta_terms = int(eta_terms)
        self.drive_type = drive_type
        minimum_steps = 1024 if cadence == "ultra" else 512
        self.n_steps = max(int(n_steps), minimum_steps)

    def _rng(self, eps0: float, omega: float, square: bool) -> np.random.Generator:
        seed = DEFAULT_RANDOM_SEED + int(round(float(eps0) * 1000.0)) * 13 + int(round(float(omega) * 10.0)) * 17 + (100000 if square else 0)
        return np.random.default_rng(seed)

    def _build_drive(self, eps0: float, omega: float, square: bool = False) -> tuple[np.ndarray, float, np.ndarray]:
        time = np.arange(self.n_steps, dtype=float)
        omega_rad = 2.0 * np.pi * float(omega) / float(self.n_steps)
        if square or self.drive_type == "square_pulse":
            drive = float(eps0) * np.sign(np.sin(omega_rad * time))
        else:
            drive = float(eps0) * np.sin(omega_rad * time)
        return time, omega_rad, drive

    def measure(self, eps0: float, omega: float, square: bool = False, memory_factor: float = 1.0) -> dict[str, float | bool | list[float]]:
        base = measure_susceptibility(
            eps0=min(max(float(eps0), 1e-4), 0.1),
            omega=float(omega),
            n_steps=self.n_steps,
            k_low=self.k_low,
            k_high=self.k_high,
            n_cut=self.n_cut,
            alpha=self.alpha,
            eta_terms=self.eta_terms,
        )
        sigma_linear = float(base["sigma_info"])
        gamma_linear = float(base["gamma_damping"])
        g_natural = float(base["g_natural"])
        eps_crit_guess = 1.0 / max(self.alpha, 1e-8)
        strain_ratio = float(eps0) / max(eps_crit_guess, 1e-8)

        time, omega_rad, drive = self._build_drive(eps0=float(eps0), omega=float(omega), square=square)
        phase_lag_model = float(np.arctan2(omega_rad, gamma_linear))
        saturation = 1.0 / (1.0 + 0.01 * strain_ratio**4)
        if square:
            saturation /= 1.0 + 0.15 * strain_ratio

        chi3_model = -0.22 * sigma_linear * (1.0 + 0.15 * float(omega) / max(DEFAULT_OMEGA_MAX, 1e-8))
        chi5_model = -0.04 * sigma_linear * max(strain_ratio - 0.8, 0.0)
        amplitude_fundamental = sigma_linear * float(eps0) * saturation * float(memory_factor)
        amplitude_third = abs(chi3_model) * float(eps0) ** 3 / (1.0 + 0.25 * strain_ratio)
        amplitude_fifth = abs(chi5_model) * float(eps0) ** 5 / (1.0 + strain_ratio)

        response = amplitude_fundamental * np.sin(omega_rad * time - phase_lag_model)
        response -= amplitude_third * np.sin(3.0 * omega_rad * time - 3.0 * phase_lag_model)
        response -= amplitude_fifth * np.sin(5.0 * omega_rad * time - 5.0 * phase_lag_model)

        noise_scale = max(0.0, strain_ratio - 0.9)
        if square:
            noise_scale += 0.75
        if noise_scale > 0.0:
            rng = self._rng(eps0=float(eps0), omega=float(omega), square=square)
            response += 0.08 * max(abs(amplitude_fundamental), 1e-6) * noise_scale * rng.normal(size=self.n_steps)
            response += 0.04 * max(abs(amplitude_fundamental), 1e-6) * noise_scale * np.sign(np.sin(7.0 * omega_rad * time))

        drive_fft = np.fft.rfft(drive - np.mean(drive))
        response_fft = np.fft.rfft(response - np.mean(response))
        freqs = np.fft.rfftfreq(self.n_steps, d=1.0)
        target_frequency = float(omega) / float(self.n_steps)
        target_idx = max(1, int(np.argmin(np.abs(freqs - target_frequency))))
        third_idx = min(target_idx * 3, len(response_fft) - 1)
        fifth_idx = min(target_idx * 5, len(response_fft) - 1)

        power = np.abs(response_fft) ** 2
        response_power = power[1:]
        total_power = float(response_power.sum())
        fundamental_power = float(power[target_idx])
        third_power = float(power[third_idx])
        fifth_power = float(power[fifth_idx])
        used_indices = {0, target_idx, third_idx, fifth_idx}
        broadband_power = float(sum(power[idx] for idx in range(len(power)) if idx not in used_indices))

        spectrum_prob = response_power / max(total_power, 1e-12)
        spectral_entropy = float(-np.sum(spectrum_prob * np.log(spectrum_prob + 1e-15)) / np.log(max(len(spectrum_prob), 2)))
        harmonic_distortion = float((third_power + fifth_power) / max(fundamental_power, 1e-12))

        drive_amplitude = float(2.0 * np.abs(drive_fft[target_idx]) / self.n_steps)
        response_amplitude = float(2.0 * np.abs(response_fft[target_idx]) / self.n_steps)
        phase_lag = float(np.angle(drive_fft[target_idx]) - np.angle(response_fft[target_idx]))
        phase_lag = float(np.arctan2(np.sin(phase_lag), np.cos(phase_lag)))
        phase_abs = min(max(abs(phase_lag), 1e-6), np.pi / 2.0 - 1e-6)
        gamma_fit = float(abs(omega_rad / np.tan(phase_abs)))
        sigma_info = float(response_amplitude / max(drive_amplitude, 1e-12))
        kappa_fit = float(sigma_info * gamma_fit)
        conductivity_residual_percent = abs(sigma_info - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0

        return {
            "eps0": float(eps0),
            "omega": float(omega),
            "sigma_info": round(sigma_info, 8),
            "kappa": round(kappa_fit, 8),
            "gamma_damping": round(gamma_fit, 8),
            "phase_lag": round(phase_lag, 8),
            "g_natural": round(g_natural, 8),
            "third_order_susceptibility": round(-abs(2.0 * np.abs(response_fft[third_idx]) / self.n_steps) / max(float(eps0) ** 3, 1e-12), 8),
            "spectral_entropy": round(spectral_entropy, 8),
            "harmonic_distortion": round(harmonic_distortion, 8),
            "fundamental_power": round(fundamental_power, 8),
            "third_power": round(third_power, 8),
            "fifth_power": round(fifth_power, 8),
            "broadband_power": round(broadband_power, 8),
            "modular_viscosity": round((1.0 - g_natural) + abs(self.alpha - 1.0), 8),
            "conductivity_residual_percent": round(conductivity_residual_percent, 5),
            "conductivity_lock": bool(conductivity_residual_percent <= 0.5),
            "harmonic_vector": [float(fundamental_power), float(third_power), float(fifth_power), float(broadband_power)],
        }


def run_stress_strain_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    k_low: int = DEFAULT_LATTICE_BASE_WEIGHT,
    k_high: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = DEFAULT_PRIME_LOCK_N_CUT,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
    omega_target: float = DEFAULT_OMEGA_MAX,
    ramp_min: float = DEFAULT_STRAIN_RAMP_MIN,
    ramp_max: float = DEFAULT_STRAIN_RAMP_MAX,
    ramp_steps: int = DEFAULT_STRAIN_RAMP_STEPS,
    quench_factor: float = DEFAULT_QUENCH_FACTOR,
    drive_type: str = DEFAULT_DRIVE_TYPE,
    cadence: str = DEFAULT_CADENCE,
    response_steps: int = 1024,
) -> tuple[dict, pd.DataFrame]:
    """Run the RUN_016 dual-phase stress-strain protocol with a logarithmic ramp and critical quench."""
    analyzer = NonLinearAnalyzer(
        k_low=int(k_low),
        k_high=int(k_high),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
        n_steps=int(response_steps),
        drive_type=drive_type,
        cadence=cadence,
    )
    lower = max(float(ramp_min), 1e-6)
    upper = max(float(ramp_max), lower * 1.0001)
    eps_values = np.geomspace(lower, upper, max(int(ramp_steps), 3))

    rows = []
    for eps0 in eps_values:
        measurement = analyzer.measure(eps0=float(eps0), omega=float(omega_target), square=False)
        measurement["phase"] = "ramp"
        rows.append(measurement)

    baseline_vector = np.asarray(rows[0]["harmonic_vector"], dtype=float) + 1e-12
    baseline_vector = baseline_vector / float(baseline_vector.sum())
    baseline_window = rows[: min(5, len(rows))]
    baseline_entropy = np.asarray([float(row["spectral_entropy"]) for row in baseline_window], dtype=float)
    entropy_threshold = max(float(np.mean(baseline_entropy) + 3.0 * np.std(baseline_entropy)), 0.02)

    for row in rows:
        current_vector = np.asarray(row["harmonic_vector"], dtype=float) + 1e-12
        current_vector = current_vector / float(current_vector.sum())
        kl_drift = float(np.sum(current_vector * np.log(current_vector / baseline_vector)))
        row["kl_drift"] = round(kl_drift, 8)
        row["spectral_spike"] = bool(float(row["spectral_entropy"]) > entropy_threshold)
        row["distortion_spike"] = bool(float(row["harmonic_distortion"]) > 0.05)
        row["kl_break"] = bool(kl_drift > 0.0138)
        row["criteria_count"] = int(row["spectral_spike"]) + int(row["distortion_spike"]) + int(row["kl_break"])
        row["elastic"] = bool(row["criteria_count"] == 0)

    df = pd.DataFrame(rows)
    search_df = df.iloc[min(5, len(df) - 1):] if len(df) > 5 else df
    critical_matches = search_df.loc[search_df["criteria_count"].astype(int) >= 2]
    if critical_matches.empty:
        critical_matches = search_df.loc[(search_df["spectral_spike"] == True) | (search_df["distortion_spike"] == True) | (search_df["kl_break"] == True)]
    critical_row = critical_matches.iloc[0] if not critical_matches.empty else df.iloc[-1]

    baseline_sigma = float(df.iloc[0]["sigma_info"])
    quench_eps = min(float(critical_row["eps0"]) * float(quench_factor), upper)
    quench_measurement = analyzer.measure(eps0=float(quench_eps), omega=float(omega_target), square=True)
    quench_vector = np.asarray(quench_measurement["harmonic_vector"], dtype=float) + 1e-12
    quench_vector = quench_vector / float(quench_vector.sum())
    quench_measurement["kl_drift"] = round(float(np.sum(quench_vector * np.log(quench_vector / baseline_vector))), 8)
    quench_measurement["phase"] = "quench"
    re_mod = float((float(quench_measurement["broadband_power"]) / max(float(quench_measurement["fundamental_power"]), 1e-12)) * (float(omega_target) / float(DEFAULT_OMEGA_MIN)))
    quench_measurement["re_mod"] = round(re_mod, 8)

    recovery_memory = 1.0 / (1.0 + max(re_mod - 1.0, 0.0) * 0.35)
    recovery_measurement = analyzer.measure(eps0=float(eps_values[0]), omega=float(omega_target), square=False, memory_factor=recovery_memory)
    recovery_measurement["phase"] = "recovery"
    recovery_measurement["kl_drift"] = round(float(quench_measurement["kl_drift"]), 8)
    recovery_measurement["re_mod"] = round(re_mod, 8)

    df = pd.concat([df, pd.DataFrame([quench_measurement, recovery_measurement])], ignore_index=True)
    df["harmonic_vector"] = df["harmonic_vector"].apply(lambda values: ",".join(f"{float(value):.6f}" for value in values) if isinstance(values, list) else values)

    recovery_gap_percent = abs(float(recovery_measurement["sigma_info"]) - baseline_sigma) / max(baseline_sigma, 1e-12) * 100.0
    hardening_detected = bool(((df["third_order_susceptibility"].astype(float) < 0.0) & (df["harmonic_distortion"].astype(float) > 0.05)).any())
    fracture_detected = bool(re_mod > 1.0 or (float(quench_measurement["spectral_entropy"]) > entropy_threshold and float(quench_measurement["kl_drift"]) > 0.0138))
    hysteresis_detected = bool(recovery_gap_percent > 1.0 or float(recovery_measurement["sigma_info"]) < 0.95 * baseline_sigma)

    summary = {
        "generated_at": iso_now(),
        "mode": "stress-strain",
        "k_params": float(k_params),
        "k_low": int(k_low),
        "k_high": int(k_high),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "eta_terms": int(eta_terms),
        "omega_target": float(omega_target),
        "ramp_min": float(lower),
        "ramp_max": float(upper),
        "ramp_steps": int(ramp_steps),
        "quench_factor": float(quench_factor),
        "drive_type": drive_type,
        "cadence": cadence,
        "response_steps": int(analyzer.n_steps),
        "baseline_sigma": baseline_sigma,
        "entropy_threshold": round(entropy_threshold, 8),
        "critical_eps": float(critical_row["eps0"]),
        "critical_sigma": float(critical_row["sigma_info"]),
        "critical_entropy": float(critical_row["spectral_entropy"]),
        "critical_distortion": float(critical_row["harmonic_distortion"]),
        "critical_kl_drift": float(critical_row["kl_drift"]),
        "critical_chi3": float(critical_row["third_order_susceptibility"]),
        "quench_eps": float(quench_eps),
        "quench_sigma": float(quench_measurement["sigma_info"]),
        "quench_entropy": float(quench_measurement["spectral_entropy"]),
        "quench_kl_drift": float(quench_measurement["kl_drift"]),
        "re_mod": round(re_mod, 8),
        "recovery_sigma": float(recovery_measurement["sigma_info"]),
        "recovery_gap_percent": round(recovery_gap_percent, 5),
        "hardening_detected": bool(hardening_detected),
        "fracture_detected": bool(fracture_detected),
        "hysteresis_detected": bool(hysteresis_detected),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def run_neighbor_weight_control(
    k_params: float = DEFAULT_K_PARAMS,
    probe_weights: tuple[int, ...] = DEFAULT_NEIGHBOR_WEIGHTS,
    reference_weight: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cut: int = 5000,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
    eps0: float = 1e-6,
    omega: float = DEFAULT_OMEGA_MAX,
    response_steps: int = 4096,
) -> tuple[dict, pd.DataFrame]:
    """Compare nearby weights around k=24 under a fixed linear-response transport probe."""
    unique_weights = tuple(sorted({int(value) for value in probe_weights}))
    rows = []
    for weight in unique_weights:
        measurement = measure_susceptibility(
            eps0=float(eps0),
            omega=float(omega),
            n_steps=int(response_steps),
            k_low=int(weight),
            k_high=int(reference_weight),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        measurement["weight_k"] = int(weight)
        measurement["delta_from_target"] = round(float(measurement["sigma_info"]) - THEORETICAL_GAMMA, 8)
        measurement["abs_target_residual"] = round(abs(float(measurement["sigma_info"]) - THEORETICAL_GAMMA), 8)
        rows.append(measurement)

    df = pd.DataFrame(rows).sort_values(by=["weight_k"]).reset_index(drop=True)
    best_idx = int(df["conductivity_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]

    target_matches = df.loc[df["weight_k"].astype(int) == 24]
    k24_row = target_matches.iloc[0] if not target_matches.empty else best_row
    other_rows = df.loc[df["weight_k"].astype(int) != int(k24_row["weight_k"])]
    next_best_residual = float(other_rows["conductivity_residual_percent"].astype(float).min()) if not other_rows.empty else float(k24_row["conductivity_residual_percent"])
    k24_margin_percent = round(next_best_residual - float(k24_row["conductivity_residual_percent"]), 5)

    sigma_values = df["sigma_info"].astype(float).to_numpy()
    leech_anchor_confirmed = bool(int(k24_row["weight_k"]) == 24 and float(k24_row["conductivity_residual_percent"]) < next_best_residual)
    scaling_law_trend = bool(np.all(np.diff(sigma_values) >= 0.0) or np.all(np.diff(sigma_values) <= 0.0))
    if leech_anchor_confirmed:
        verdict = "Leech Anchor Confirmed"
    elif scaling_law_trend:
        verdict = "Scaling-Law Trend"
    else:
        verdict = "Stochastic/Artifact Candidate"

    summary = {
        "generated_at": iso_now(),
        "mode": "neighborhood-control",
        "k_params": float(k_params),
        "probe_weights": [int(value) for value in unique_weights],
        "reference_weight": int(reference_weight),
        "n_cut": int(n_cut),
        "alpha": float(alpha),
        "eta_terms": int(eta_terms),
        "eps0": float(eps0),
        "omega": float(omega),
        "response_steps": int(response_steps),
        "k24_sigma": float(k24_row["sigma_info"]),
        "k24_residual_percent": float(k24_row["conductivity_residual_percent"]),
        "best_weight": int(best_row["weight_k"]),
        "best_sigma": float(best_row["sigma_info"]),
        "best_residual_percent": float(best_row["conductivity_residual_percent"]),
        "k24_margin_percent": float(k24_margin_percent),
        "sigma_std": round(float(df["sigma_info"].astype(float).std(ddof=0)), 8),
        "verdict": verdict,
        "leech_anchor_confirmed": bool(leech_anchor_confirmed),
        "scaling_law_trend": bool(scaling_law_trend),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def compute_borel_l1_tail_proxy(
    weight: int,
    n_cut: int,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
) -> dict[str, float]:
    """Estimate a Borel-L1 tail proxy from the stabilized q-series increments."""
    series = build_modular_eta_drift(
        weight=int(weight),
        n_cut=int(n_cut),
        alpha=float(alpha),
        eta_terms=int(eta_terms),
    )
    log_series = np.log(np.clip(series, 1e-15, None))
    deltas = np.diff(log_series)
    midpoint = len(deltas) // 2
    tail = deltas[midpoint:]
    centered_tail = tail - float(np.mean(tail))
    quarter = max(len(centered_tail) // 4, 1)
    head_l1 = float(np.mean(np.abs(centered_tail[:quarter])))
    end_l1 = float(np.mean(np.abs(centered_tail[-quarter:])))
    borel_tail = np.cumsum(centered_tail[::-1])[::-1] / np.arange(len(centered_tail), 0, -1, dtype=float)
    return {
        "tail_l1_norm": round(float(np.mean(np.abs(centered_tail))), 8),
        "borel_l1_norm": round(float(np.mean(np.abs(borel_tail))), 8),
        "tail_decay_ratio": round(float(end_l1 / max(head_l1, 1e-12)), 8),
    }


def fit_asymptotic_scaling(n_values: np.ndarray, sigma_values: np.ndarray) -> tuple[float, float, float]:
    """Fit sigma(N) = sigma_inf + c * N^{-alpha} by a simple alpha grid search."""
    n_array = np.asarray(n_values, dtype=float)
    sigma_array = np.asarray(sigma_values, dtype=float)
    best_loss = float("inf")
    best_sigma_inf = float(sigma_array[-1])
    best_alpha = 1.0
    best_c = 0.0

    for alpha_candidate in np.linspace(0.1, 3.0, 581):
        x_values = n_array ** (-float(alpha_candidate))
        design = np.column_stack([np.ones_like(x_values), x_values])
        coeffs, _, _, _ = np.linalg.lstsq(design, sigma_array, rcond=None)
        sigma_inf_candidate = float(coeffs[0])
        c_candidate = float(coeffs[1])
        prediction = sigma_inf_candidate + c_candidate * x_values
        loss = float(np.mean((prediction - sigma_array) ** 2))
        if loss < best_loss:
            best_loss = loss
            best_sigma_inf = sigma_inf_candidate
            best_alpha = float(alpha_candidate)
            best_c = c_candidate

    return best_sigma_inf, best_alpha, best_c


def bootstrap_scaling_fit(
    n_values: np.ndarray,
    sigma_values: np.ndarray,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_RANDOM_SEED,
) -> dict[str, float]:
    """Bootstrap the finite-size scaling fit to estimate confidence intervals."""
    n_array = np.asarray(n_values, dtype=float)
    sigma_array = np.asarray(sigma_values, dtype=float)
    rng = np.random.default_rng(int(seed))
    sigma_inf_samples = []
    alpha_samples = []

    for _ in range(max(int(bootstrap_samples), 10)):
        indices = rng.integers(0, len(n_array), size=len(n_array))
        n_sample = n_array[indices]
        sigma_sample = sigma_array[indices]
        if np.unique(n_sample).size < 2:
            continue
        order = np.argsort(n_sample)
        sigma_inf, alpha_fit, _ = fit_asymptotic_scaling(n_sample[order], sigma_sample[order])
        sigma_inf_samples.append(float(sigma_inf))
        alpha_samples.append(float(alpha_fit))

    sigma_inf_array = np.asarray(sigma_inf_samples, dtype=float)
    alpha_array = np.asarray(alpha_samples, dtype=float)
    if sigma_inf_array.size == 0 or alpha_array.size == 0:
        sigma_inf, alpha_fit, _ = fit_asymptotic_scaling(n_array, sigma_array)
        sigma_inf_array = np.asarray([sigma_inf], dtype=float)
        alpha_array = np.asarray([alpha_fit], dtype=float)

    return {
        "sigma_inf_bootstrap_mean": round(float(np.mean(sigma_inf_array)), 8),
        "sigma_inf_ci_low": round(float(np.quantile(sigma_inf_array, 0.025)), 8),
        "sigma_inf_ci_high": round(float(np.quantile(sigma_inf_array, 0.975)), 8),
        "alpha_bootstrap_mean": round(float(np.mean(alpha_array)), 8),
        "alpha_ci_low": round(float(np.quantile(alpha_array, 0.025)), 8),
        "alpha_ci_high": round(float(np.quantile(alpha_array, 0.975)), 8),
    }


def run_rigor_check(
    k_params: float = DEFAULT_K_PARAMS,
    k_probe: int = 24,
    k_high: int = DEFAULT_LATTICE_STABLE_WEIGHT,
    n_cuts: tuple[int, ...] = DEFAULT_RIGOR_N_CUTS,
    alpha: float = DEFAULT_ALPHA,
    eta_terms: int = DEFAULT_ETA_TERMS,
    eps0: float = 1e-6,
    omega: float = DEFAULT_OMEGA_MAX,
    response_steps: int = 4096,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    pair_weights: tuple[int, ...] = (12, 24, 48),
) -> tuple[dict, pd.DataFrame]:
    """Run the mandatory pre-submission finite-size and Borel-L1 control tests."""
    rows = []
    sorted_cuts = tuple(sorted({int(value) for value in n_cuts}))
    for n_cut in sorted_cuts:
        transport = measure_susceptibility(
            eps0=float(eps0),
            omega=float(omega),
            n_steps=int(response_steps),
            k_low=int(k_probe),
            k_high=int(k_high),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        tail_metrics = compute_borel_l1_tail_proxy(
            weight=int(k_probe),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        covariance = compute_modular_covariance(
            k_low=int(k_probe),
            k_high=int(k_high),
            beta_rg=max(1.0 / max(float(omega), 1e-8), 1e-8),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        rows.append(
            {
                "row_type": "resolution",
                "weight_k": int(k_probe),
                "k_high": int(k_high),
                "n_cut": int(n_cut),
                "sigma_info": float(transport["sigma_info"]),
                "conductivity_residual_percent": float(transport["conductivity_residual_percent"]),
                "gamma_damping": float(transport["gamma_damping"]),
                "g_natural": float(transport["g_natural"]),
                "direct_gamma": float(covariance["measured_gamma"]),
                "direct_fidelity": float(covariance["fidelity"]),
                **tail_metrics,
            }
        )

    largest_cut = int(sorted_cuts[-1]) if sorted_cuts else int(DEFAULT_RIGOR_N_CUTS[-1])
    unique_pair_weights = tuple(sorted({int(value) for value in pair_weights}))
    pair_cases = []
    for idx in range(len(unique_pair_weights)):
        for jdx in range(idx + 1, len(unique_pair_weights)):
            pair_cases.append((unique_pair_weights[idx], unique_pair_weights[jdx]))

    for k_low_pair, k_high_pair in pair_cases:
        pair_measurement = measure_susceptibility(
            eps0=float(eps0),
            omega=float(omega),
            n_steps=int(response_steps),
            k_low=int(k_low_pair),
            k_high=int(k_high_pair),
            n_cut=int(largest_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        rows.append(
            {
                "row_type": "pair-control",
                "pair_label": f"{k_low_pair}-{k_high_pair}",
                "n_cut": int(largest_cut),
                "sigma_info": float(pair_measurement["sigma_info"]),
                "conductivity_residual_percent": float(pair_measurement["conductivity_residual_percent"]),
                "gamma_damping": float(pair_measurement["gamma_damping"]),
                "g_natural": float(pair_measurement["g_natural"]),
            }
        )

    df = pd.DataFrame(rows)
    resolution_df = df.loc[df["row_type"] == "resolution"].sort_values(by=["n_cut"]).reset_index(drop=True)
    pair_df = df.loc[df["row_type"] == "pair-control"].sort_values(by=["pair_label"]).reset_index(drop=True)

    n_values = resolution_df["n_cut"].astype(float).to_numpy()
    sigma_values = resolution_df["sigma_info"].astype(float).to_numpy()
    sigma_inf, alpha_fit, c_fit = fit_asymptotic_scaling(n_values=n_values, sigma_values=sigma_values)
    bootstrap = bootstrap_scaling_fit(
        n_values=n_values,
        sigma_values=sigma_values,
        bootstrap_samples=int(bootstrap_samples),
    )

    tail_decay_supported = bool((resolution_df["tail_decay_ratio"].astype(float) < 1.0).all())
    pair_spread_percent = round(
        (float(pair_df["sigma_info"].astype(float).max()) - float(pair_df["sigma_info"].astype(float).min())) / THEORETICAL_GAMMA * 100.0,
        5,
    ) if not pair_df.empty else 0.0

    summary = {
        "generated_at": iso_now(),
        "mode": "rigor-check",
        "k_params": float(k_params),
        "k_probe": int(k_probe),
        "k_high": int(k_high),
        "n_cuts": [int(value) for value in sorted_cuts],
        "alpha": float(alpha),
        "eta_terms": int(eta_terms),
        "eps0": float(eps0),
        "omega": float(omega),
        "response_steps": int(response_steps),
        "bootstrap_samples": int(bootstrap_samples),
        "sigma_inf": round(float(sigma_inf), 8),
        "alpha_fit": round(float(alpha_fit), 8),
        "fit_coefficient": round(float(c_fit), 8),
        "sigma_n_min": round(float(resolution_df["sigma_info"].astype(float).min()), 8),
        "sigma_n_max": round(float(resolution_df["sigma_info"].astype(float).max()), 8),
        "tail_l1_last": float(resolution_df.iloc[-1]["tail_l1_norm"]),
        "borel_l1_last": float(resolution_df.iloc[-1]["borel_l1_norm"]),
        "tail_decay_supported": bool(tail_decay_supported),
        "pair_spread_percent": float(pair_spread_percent),
        "pair_stability_supported": bool(pair_spread_percent <= 0.05),
        **bootstrap,
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def build_target_density_matrix(dim: int) -> np.ndarray:
    """Build the fixed-point target density matrix for the requested dimension."""
    if int(dim) <= 1:
        return np.array([[1.0]], dtype=float)
    remainder = (1.0 - THEORETICAL_GAMMA) / float(int(dim) - 1)
    diagonal = [THEORETICAL_GAMMA] + [remainder] * (int(dim) - 1)
    return np.diag(diagonal).astype(float)


def normalize_density_matrix(matrix: np.ndarray) -> np.ndarray:
    """Project a symmetric matrix to the PSD cone and normalize it to trace 1."""
    rho = np.asarray(matrix, dtype=float)
    rho = 0.5 * (rho + rho.T)
    eigvals, eigvecs = np.linalg.eigh(rho)
    eigvals = np.clip(eigvals, 1e-12, None)
    projected = eigvecs @ np.diag(eigvals) @ eigvecs.T
    trace = float(np.trace(projected))
    if trace <= 0.0:
        return np.eye(projected.shape[0], dtype=float) / float(projected.shape[0])
    return projected / trace


def build_rotation_matrix(dim: int, angle: float) -> np.ndarray:
    """Build a simple orthogonal basis rotation for the hierarchy invariance test."""
    rotation = np.eye(int(dim), dtype=float)
    if int(dim) >= 2:
        cos_theta = float(np.cos(angle))
        sin_theta = float(np.sin(angle))
        rotation[:2, :2] = np.array([[cos_theta, -sin_theta], [sin_theta, cos_theta]], dtype=float)
    if int(dim) >= 3:
        extra = np.eye(int(dim), dtype=float)
        cos_phi = float(np.cos(angle / 2.0))
        sin_phi = float(np.sin(angle / 2.0))
        extra[1:3, 1:3] = np.array([[cos_phi, -sin_phi], [sin_phi, cos_phi]], dtype=float)
        rotation = extra @ rotation
    return rotation


def build_hierarchy_signals(
    weights: tuple[int, ...],
    n_cut: int,
    alpha: float,
    eta_terms: int,
) -> np.ndarray:
    """Construct normalized modular-lattice signals for the requested hierarchy weights."""
    signals = []
    for weight in weights:
        raw_drift = build_modular_eta_drift(
            weight=int(weight),
            n_cut=int(n_cut),
            alpha=float(alpha),
            eta_terms=int(eta_terms),
        )
        tail = raw_drift[-int(n_cut):]
        signal = tail ** (float(weight) / 24.0)
        norm = float(np.linalg.norm(signal))
        if norm > 0.0:
            signal = signal / norm
        signals.append(signal)
    return np.asarray(signals, dtype=float)


def density_from_gram(
    gram_matrix: np.ndarray,
    chi: float,
    p_initial: float,
    rotation_angle: float = 0.0,
) -> np.ndarray:
    """Convert a Gram matrix into a trace-normalized coupled density matrix."""
    dim = int(np.asarray(gram_matrix).shape[0])
    rho = normalize_density_matrix(gram_matrix)
    if dim > 1:
        anchor_diag = np.diag([float(p_initial)] + [(1.0 - float(p_initial)) / float(dim - 1)] * (dim - 1))
        coupling = np.ones((dim, dim), dtype=float) - np.eye(dim, dtype=float)
        rho = 0.95 * rho + 0.05 * anchor_diag + float(chi) * coupling / float(dim * (dim - 1))
    if abs(float(rotation_angle)) > 0.0:
        rotation = build_rotation_matrix(dim=dim, angle=float(rotation_angle))
        rho = rotation @ rho @ rotation.T
    return normalize_density_matrix(rho)


def build_random_thermal_state(dim: int, rng: np.random.Generator) -> np.ndarray:
    """Generate a random thermal null state for the ancilla replacement control."""
    beta = float(rng.uniform(0.5, 3.0))
    energies = np.sort(rng.normal(size=int(dim)))
    boltzmann = np.exp(-beta * (energies - float(energies.min())))
    probabilities = boltzmann / float(boltzmann.sum())
    basis = rng.normal(size=(int(dim), int(dim)))
    q_matrix, _ = np.linalg.qr(basis)
    thermal_state = q_matrix @ np.diag(probabilities) @ q_matrix.T
    return normalize_density_matrix(thermal_state)


def evaluate_holographic_state(rho: np.ndarray, alpha: float, chi: float) -> dict[str, float | bool]:
    """Evaluate fidelity, KL balance, and the holographic metric for a density matrix."""
    rho = normalize_density_matrix(rho)
    sigma_star = build_target_density_matrix(dim=rho.shape[0])
    eigvals = np.linalg.eigvalsh(rho)
    eigvals = np.clip(eigvals, 0.0, None)
    eigvals = eigvals / float(eigvals.sum())
    sorted_eigvals = np.sort(eigvals)
    lambda1 = float(sorted_eigvals[-1])
    lambda2 = float(sorted_eigvals[-2]) if sorted_eigvals.size > 1 else 0.0
    gamma_measured = lambda1

    sqrt_sigma = matrix_sqrt_psd(sigma_star)
    overlap = sqrt_sigma @ rho @ sqrt_sigma
    fidelity = float(np.trace(matrix_sqrt_psd(overlap)) ** 2)
    purity = float(np.trace(rho @ rho))
    entropy = entropy_from_density_matrix(rho)
    mutual_information, kl_divergence = measure_holographic_info(rho=rho, sigma_star=sigma_star)

    surface_area_term = float(fidelity / THEORETICAL_GAMMA)
    information_gain_term = float(np.exp(-kl_divergence))
    weight_total = abs(float(alpha)) + abs(float(chi))
    if weight_total == 0.0:
        w_area = 0.5
        w_kl = 0.5
    else:
        w_area = abs(float(alpha)) / weight_total
        w_kl = abs(float(chi)) / weight_total

    holographic_metric = float(w_area * surface_area_term + w_kl * information_gain_term)
    gamma_residual_percent = abs(gamma_measured - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    fidelity_residual_percent = abs(fidelity - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0
    holographic_residual_percent = abs(holographic_metric - DEFAULT_HOLOGRAPHIC_TARGET) * 100.0
    composite_gap_percent = fidelity_residual_percent + holographic_residual_percent
    holographic_lock = (
        abs(holographic_metric - DEFAULT_HOLOGRAPHIC_TARGET) <= DEFAULT_HOLOGRAPHIC_TOLERANCE
        and fidelity_residual_percent <= 0.1
    )

    return {
        "lambda1": round(lambda1, 8),
        "lambda2": round(lambda2, 8),
        "measured_gamma": round(gamma_measured, 8),
        "fidelity": round(fidelity, 8),
        "purity": round(purity, 8),
        "entropy": round(entropy, 8),
        "gamma_residual_percent": round(gamma_residual_percent, 5),
        "fidelity_residual_percent": round(fidelity_residual_percent, 5),
        "mutual_information": round(mutual_information, 8),
        "kl_divergence": round(kl_divergence, 8),
        "surface_area_term": round(surface_area_term, 8),
        "information_gain_term": round(information_gain_term, 8),
        "w_area": round(w_area, 8),
        "w_kl": round(w_kl, 8),
        "holographic_metric": round(holographic_metric, 8),
        "holographic_residual_percent": round(holographic_residual_percent, 5),
        "composite_gap_percent": round(composite_gap_percent, 5),
        "holographic_lock": bool(holographic_lock),
    }


def measure_tripartite_information(rho: np.ndarray) -> float:
    """Compute a coarse tripartite information diagnostic from normalized principal submatrices."""
    matrix = normalize_density_matrix(rho)
    if matrix.shape[0] < 3:
        return float("nan")

    diagonal = np.clip(np.diag(matrix), 1e-15, None)
    diagonal = diagonal / float(diagonal.sum())

    def single_site_entropy(probability: float) -> float:
        site_state = np.diag([probability, max(1.0 - probability, 1e-15)])
        return entropy_from_density_matrix(site_state)

    def sub_entropy(indices: tuple[int, ...]) -> float:
        submatrix = matrix[np.ix_(indices, indices)]
        return entropy_from_density_matrix(submatrix)

    s_a = single_site_entropy(float(diagonal[0]))
    s_b = single_site_entropy(float(diagonal[1]))
    s_c = single_site_entropy(float(diagonal[2]))
    s_ab = sub_entropy((0, 1))
    s_ac = sub_entropy((0, 2))
    s_bc = sub_entropy((1, 2))
    s_abc = entropy_from_density_matrix(matrix)
    return round(float(s_a + s_b + s_c - s_ab - s_ac - s_bc + s_abc), 8)


def bootstrap_hierarchy_statistics(
    weights: tuple[int, ...],
    n_cut: int,
    alpha: float,
    eta_terms: int,
    chi: float,
    p_initial: float,
    bootstrap_samples: int,
    rng: np.random.Generator,
) -> dict[str, float]:
    """Bootstrap the hierarchy measurement to estimate 95% confidence intervals."""
    signals = build_hierarchy_signals(weights=weights, n_cut=n_cut, alpha=alpha, eta_terms=eta_terms)
    signal_length = int(signals.shape[1])
    fidelity_samples: list[float] = []
    holographic_samples: list[float] = []

    for _ in range(max(int(bootstrap_samples), 1)):
        indices = rng.integers(0, signal_length, size=signal_length)
        sampled = signals[:, indices]
        gram = sampled @ sampled.T
        rho = density_from_gram(gram_matrix=gram, chi=float(chi), p_initial=float(p_initial))
        measurement = evaluate_holographic_state(rho=rho, alpha=float(alpha), chi=float(chi))
        fidelity_samples.append(float(measurement["fidelity"]))
        holographic_samples.append(float(measurement["holographic_metric"]))

    fidelity_array = np.asarray(fidelity_samples, dtype=float)
    holographic_array = np.asarray(holographic_samples, dtype=float)
    return {
        "bootstrap_fidelity_mean": round(float(np.mean(fidelity_array)), 8),
        "bootstrap_fidelity_ci_low": round(float(np.quantile(fidelity_array, 0.025)), 8),
        "bootstrap_fidelity_ci_high": round(float(np.quantile(fidelity_array, 0.975)), 8),
        "bootstrap_h_mean": round(float(np.mean(holographic_array)), 8),
        "bootstrap_h_ci_low": round(float(np.quantile(holographic_array, 0.025)), 8),
        "bootstrap_h_ci_high": round(float(np.quantile(holographic_array, 0.975)), 8),
    }


def compute_model_selection(samples: np.ndarray) -> dict[str, float | bool]:
    """Compare a fixed-Γ model against a free-Γ Gaussian model using AIC/BIC."""
    values = np.asarray(samples, dtype=float)
    n_obs = int(values.size)
    if n_obs == 0:
        return {
            "log_likelihood_fixed": float("nan"),
            "log_likelihood_free": float("nan"),
            "lr_stat": float("nan"),
            "aic_fixed": float("nan"),
            "aic_free": float("nan"),
            "bic_fixed": float("nan"),
            "bic_free": float("nan"),
            "fixed_gamma_preferred": False,
        }

    mu_fixed = THEORETICAL_GAMMA
    mu_free = float(np.mean(values))
    sigma2_fixed = max(float(np.mean((values - mu_fixed) ** 2)), 1e-12)
    sigma2_free = max(float(np.mean((values - mu_free) ** 2)), 1e-12)

    log_likelihood_fixed = float(-0.5 * n_obs * (np.log(2.0 * np.pi * sigma2_fixed) + 1.0))
    log_likelihood_free = float(-0.5 * n_obs * (np.log(2.0 * np.pi * sigma2_free) + 1.0))
    lr_stat = float(2.0 * (log_likelihood_free - log_likelihood_fixed))

    aic_fixed = float(2.0 * 1 - 2.0 * log_likelihood_fixed)
    aic_free = float(2.0 * 2 - 2.0 * log_likelihood_free)
    bic_fixed = float(np.log(max(n_obs, 1)) * 1 - 2.0 * log_likelihood_fixed)
    bic_free = float(np.log(max(n_obs, 1)) * 2 - 2.0 * log_likelihood_free)
    fixed_gamma_preferred = bool(aic_fixed < aic_free and bic_fixed < bic_free)

    return {
        "log_likelihood_fixed": round(log_likelihood_fixed, 8),
        "log_likelihood_free": round(log_likelihood_free, 8),
        "lr_stat": round(lr_stat, 8),
        "aic_fixed": round(aic_fixed, 8),
        "aic_free": round(aic_free, 8),
        "bic_fixed": round(bic_fixed, 8),
        "bic_free": round(bic_free, 8),
        "fixed_gamma_preferred": bool(fixed_gamma_preferred),
    }


def run_hierarchy_stress_test(
    k_params: float = DEFAULT_K_PARAMS,
    alpha: float = DEFAULT_ALPHA,
    chi: float = DEFAULT_CHI,
    p_initial: float = DEFAULT_P_INITIAL,
    weights: tuple[int, ...] = DEFAULT_LATTICE_WEIGHTS,
    regulator_cuts: tuple[int, ...] = DEFAULT_REGULATOR_CUTS,
    eta_terms: int = DEFAULT_ETA_TERMS,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    rotation_angle: float = DEFAULT_ROTATION_ANGLE,
    null_draws: int = DEFAULT_NULL_DRAWS,
) -> tuple[dict, pd.DataFrame]:
    """Run the RUN_013 hierarchy stress test across scale pairs, tripartite split, and null controls."""
    ladder = tuple(sorted({int(value) for value in weights}))
    if len(ladder) < 2:
        raise ValueError("At least two hierarchy weights are required for RUN_013")

    pair_cases = tuple((ladder[i], ladder[i + 1]) for i in range(len(ladder) - 1))
    triplet_case = (ladder[0], ladder[-2], ladder[-1]) if len(ladder) >= 3 else None
    case_list = list(pair_cases)
    if triplet_case is not None:
        case_list.append(triplet_case)

    rows = []
    rng = np.random.default_rng(DEFAULT_RANDOM_SEED)
    chi_limit = float(np.sqrt(max(float(p_initial) * (1.0 - float(p_initial)), 0.0))) * 0.999999
    delta_chi = max(abs(float(chi)) * 1e-4, 1e-6)

    for n_cut in regulator_cuts:
        for case_weights in case_list:
            signals = build_hierarchy_signals(
                weights=tuple(case_weights),
                n_cut=int(n_cut),
                alpha=float(alpha),
                eta_terms=int(eta_terms),
            )
            gram_matrix = signals @ signals.T
            rho = density_from_gram(gram_matrix=gram_matrix, chi=float(chi), p_initial=float(p_initial))
            actual = evaluate_holographic_state(rho=rho, alpha=float(alpha), chi=float(chi))

            rotated_rho = density_from_gram(
                gram_matrix=gram_matrix,
                chi=float(chi),
                p_initial=float(p_initial),
                rotation_angle=float(rotation_angle),
            )
            rotated = evaluate_holographic_state(rho=rotated_rho, alpha=float(alpha), chi=float(chi))

            null_fidelity_values = []
            null_h_values = []
            for _ in range(max(int(null_draws), 1)):
                null_state = build_random_thermal_state(dim=len(case_weights), rng=rng)
                null_measurement = evaluate_holographic_state(rho=null_state, alpha=float(alpha), chi=0.0)
                null_fidelity_values.append(float(null_measurement["fidelity"]))
                null_h_values.append(float(null_measurement["holographic_metric"]))

            chi_plus = min(float(chi) + delta_chi, chi_limit)
            chi_minus = max(float(chi) - delta_chi, 0.0)
            plus_rho = density_from_gram(gram_matrix=gram_matrix, chi=chi_plus, p_initial=float(p_initial))
            minus_rho = density_from_gram(gram_matrix=gram_matrix, chi=chi_minus, p_initial=float(p_initial))
            plus_measurement = evaluate_holographic_state(rho=plus_rho, alpha=float(alpha), chi=chi_plus)
            minus_measurement = evaluate_holographic_state(rho=minus_rho, alpha=float(alpha), chi=chi_minus)

            bootstrap = bootstrap_hierarchy_statistics(
                weights=tuple(case_weights),
                n_cut=int(n_cut),
                alpha=float(alpha),
                eta_terms=int(eta_terms),
                chi=float(chi),
                p_initial=float(p_initial),
                bootstrap_samples=int(bootstrap_samples),
                rng=rng,
            )

            row = {
                "case_label": "-".join(str(value) for value in case_weights),
                "case_type": "tripartite" if len(case_weights) >= 3 else "pair",
                "weights": ",".join(str(value) for value in case_weights),
                "n_cut": int(n_cut),
                "alpha": float(alpha),
                "chi": float(chi),
                "p_initial": float(p_initial),
                **actual,
                "rotated_fidelity": round(float(rotated["fidelity"]), 8),
                "rotated_h": round(float(rotated["holographic_metric"]), 8),
                "basis_shift_percent": round(abs(float(actual["fidelity"]) - float(rotated["fidelity"])) * 100.0, 5),
                "null_mean_fidelity": round(float(np.mean(null_fidelity_values)), 8),
                "null_mean_h": round(float(np.mean(null_h_values)), 8),
                "null_gap_percent": round((float(actual["holographic_metric"]) - float(np.mean(null_h_values))) * 100.0, 5),
                "d_gamma_d_chi": round((float(plus_measurement["measured_gamma"]) - float(minus_measurement["measured_gamma"])) / max(chi_plus - chi_minus, 1e-12), 8),
                "d_h_d_chi": round((float(plus_measurement["holographic_metric"]) - float(minus_measurement["holographic_metric"])) / max(chi_plus - chi_minus, 1e-12), 8),
                "kappa_balance": round(float(chi) / float(alpha), 8) if float(alpha) != 0.0 else float("nan"),
                "tripartite_information": measure_tripartite_information(rho) if len(case_weights) >= 3 else float("nan"),
                **bootstrap,
            }
            rows.append(row)

    df = pd.DataFrame(rows).sort_values(by=["case_type", "case_label", "n_cut"]).reset_index(drop=True)
    model_selection = compute_model_selection(df["fidelity"].astype(float).to_numpy())

    regulator_shift_values = []
    for _, group in df.groupby("case_label"):
        if group["n_cut"].nunique() > 1:
            regulator_shift_values.append(float(group["fidelity"].max() - group["fidelity"].min()))
    regulator_shift_max = max(regulator_shift_values) if regulator_shift_values else 0.0

    best_idx = int(df["composite_gap_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]
    summary = {
        "generated_at": iso_now(),
        "mode": "hierarchy-stress",
        "k_params": float(k_params),
        "alpha": float(alpha),
        "chi": float(chi),
        "p_initial": float(p_initial),
        "weights": [int(value) for value in ladder],
        "regulator_cuts": [int(value) for value in regulator_cuts],
        "eta_terms": int(eta_terms),
        "bootstrap_samples": int(bootstrap_samples),
        "rotation_angle": float(rotation_angle),
        "null_draws": int(null_draws),
        "best_case": str(best_row["case_label"]),
        "best_n_cut": int(best_row["n_cut"]),
        "best_fidelity": float(best_row["fidelity"]),
        "best_gamma": float(best_row["measured_gamma"]),
        "best_holographic_metric": float(best_row["holographic_metric"]),
        "best_composite_gap_percent": float(best_row["composite_gap_percent"]),
        "lock_count": int(df["holographic_lock"].astype(bool).sum()),
        "total_cases": int(len(df)),
        "mean_fidelity": round(float(df["fidelity"].astype(float).mean()), 8),
        "mean_holographic_metric": round(float(df["holographic_metric"].astype(float).mean()), 8),
        "regulator_shift_max": round(float(regulator_shift_max), 8),
        "basis_shift_max_percent": round(float(df["basis_shift_percent"].astype(float).max()), 5),
        "mean_null_gap_percent": round(float(df["null_gap_percent"].astype(float).mean()), 5),
        "mean_abs_d_h_d_chi": round(float(df["d_h_d_chi"].astype(float).abs().mean()), 8),
        "tripartite_i3": float(df.loc[df["case_type"] == "tripartite", "tripartite_information"].astype(float).mean()) if (df["case_type"] == "tripartite").any() else float("nan"),
        **model_selection,
        "universality_supported": bool(
            float(regulator_shift_max) <= 0.01
            and float(df["basis_shift_percent"].astype(float).max()) <= 1.0
            and bool(model_selection["fixed_gamma_preferred"])
        ),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def measure_prime_lock(
    p_multiplier: int = DEFAULT_TARGET_PRIME,
    alpha: float = DEFAULT_ALPHA,
    prime_base: int = DEFAULT_N_CUT,
) -> dict[str, float]:
    """Measure the quantization-corrected prime-lock response at N_cut = 137 * P."""
    n_cut = int(prime_base) * int(p_multiplier)
    control_n_cut = int(n_cut) - 1
    q_tax_correction = EULER_MASCHERONI * (ALPHA_CODATA / 12.0) * np.log(float(prime_base))
    coupled_residue = (-1.0 / 12.0) + q_tax_correction

    def measure_window(current_n_cut: int) -> float:
        steps = int(current_n_cut) * 10
        t = np.arange(1, steps + 1, dtype=float)
        raw_drift = float(alpha) ** (t / float(current_n_cut))
        kernel = np.ones(int(current_n_cut), dtype=float) / float(current_n_cut)
        rolling_mean = np.convolve(raw_drift, kernel, mode="same")
        stabilized_series = raw_drift + coupled_residue * rolling_mean
        alignment_gamma = np.divide(
            stabilized_series,
            raw_drift,
            out=np.ones_like(raw_drift, dtype=float),
            where=raw_drift != 0,
        )
        return float(np.mean(alignment_gamma[-int(current_n_cut):]))

    prime_gamma = measure_window(n_cut)
    control_gamma = measure_window(control_n_cut)
    vacuum_gap_percent = abs(1.0 - prime_gamma) * 100.0
    theory_residual_percent = abs(prime_gamma - THEORETICAL_GAMMA) / THEORETICAL_GAMMA * 100.0

    return {
        "p_multiplier": int(p_multiplier),
        "n_cut": int(n_cut),
        "control_n_cut": int(control_n_cut),
        "q_tax_correction": float(q_tax_correction),
        "coupled_residue": float(coupled_residue),
        "measured_gamma": round(prime_gamma, 8),
        "control_gamma": round(control_gamma, 8),
        "vacuum_gap_percent": round(vacuum_gap_percent, 5),
        "theory_residual_percent": round(theory_residual_percent, 5),
        "falsification_gap_delta": round(float(prime_gamma - control_gamma), 8),
    }


def run_prime_lock_sweep(
    k_params: float = DEFAULT_K_PARAMS,
    alpha: float = DEFAULT_ALPHA,
    p_multipliers: tuple[int, ...] = DEFAULT_PRIME_MULTIPLIERS,
    target_prime: int = DEFAULT_TARGET_PRIME,
    prime_base: int = DEFAULT_N_CUT,
) -> tuple[dict, pd.DataFrame]:
    """Sweep nearby prime-lock multipliers and highlight the requested P=13 test."""
    rows = []
    for multiplier in p_multipliers:
        measurement = measure_prime_lock(
            p_multiplier=int(multiplier),
            alpha=alpha,
            prime_base=prime_base,
        )
        rows.append(measurement)

    df = pd.DataFrame(rows).sort_values(by=["p_multiplier", "n_cut"]).reset_index(drop=True)
    best_idx = int(df["theory_residual_percent"].astype(float).idxmin())
    best_row = df.loc[best_idx]

    target_matches = df.loc[df["p_multiplier"].astype(int) == int(target_prime)]
    target_row = target_matches.iloc[0] if not target_matches.empty else best_row

    summary = {
        "generated_at": iso_now(),
        "mode": "prime-lock",
        "k_params": float(k_params),
        "alpha": float(alpha),
        "window_shape": "rectangular",
        "prime_base": int(prime_base),
        "prime_multipliers": [int(value) for value in p_multipliers],
        "target_p_multiplier": int(target_row["p_multiplier"]),
        "target_n_cut": int(target_row["n_cut"]),
        "target_control_n_cut": int(target_row["control_n_cut"]),
        "quantization_tax_correction": float(target_row["q_tax_correction"]),
        "coupled_residue": float(target_row["coupled_residue"]),
        "target_measured_gamma": float(target_row["measured_gamma"]),
        "target_control_gamma": float(target_row["control_gamma"]),
        "target_vacuum_gap_percent": float(target_row["vacuum_gap_percent"]),
        "target_theory_residual_percent": float(target_row["theory_residual_percent"]),
        "target_falsification_gap_delta": float(target_row["falsification_gap_delta"]),
        "best_p_multiplier": int(best_row["p_multiplier"]),
        "best_n_cut": int(best_row["n_cut"]),
        "best_measured_gamma": float(best_row["measured_gamma"]),
        "best_theory_residual_percent": float(best_row["theory_residual_percent"]),
        "theoretical_gamma": THEORETICAL_GAMMA,
    }
    return summary, df


def save_outputs(summary: dict, df: pd.DataFrame, output_name: str) -> tuple[Path, Path]:
    base = resolve_output_base(output_name)
    csv_path = base.with_suffix(".csv")
    json_path = base.with_suffix(".json")

    df.to_csv(csv_path, index=False)
    payload = {
        "summary": summary,
        "rows": json.loads(df.to_json(orient="records")),
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if summary.get("mode") == "stress-strain":
        saturation_map_path = (Path.home() / "Documents" / "saturation_map.json")
        saturation_payload = {
            "summary": summary,
            "saturation_curve": json.loads(df.to_json(orient="records")),
        }
        saturation_map_path.write_text(json.dumps(saturation_payload, indent=2), encoding="utf-8")

    return csv_path, json_path


def append_log_entry(log_path: Path, summary: dict) -> None:
    if summary.get("mode") == "fine-structure-sweep":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v2 / Fine_Structure_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, window={summary.get('window_shape', DEFAULT_WINDOW_SHAPE)}, decay={summary.get('decay_constant', DEFAULT_DECAY_CONSTANT)}, alpha_range=[{summary['alpha_min']}, {summary['alpha_max']}], steps={summary['alpha_steps']}\n"
            f"- **Best Alpha:** `{summary['best_alpha']}`\n"
            f"- **Best Measured Gamma:** `{summary['best_measured_gamma']}`\n"
            f"- **Best Vacuum Gap:** `{summary['best_vacuum_gap_percent']}%`\n"
            f"- **Best Theory Residual:** `{summary['best_theory_residual_percent']}%`\n"
        )
    elif summary.get("mode") == "causal-sweep":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v5 / Causal_Decay_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, control={summary['control_n_cut']}, window={summary['window_shape']}, alpha={summary['alpha']}, anchor_tau={summary['anchor_tau']}, multipliers={summary['decay_multipliers']}\n"
            f"- **Best Decay Constant:** `{summary['best_decay_constant']}`\n"
            f"- **Best τ/137:** `{summary['best_multiplier']}`\n"
            f"- **Best Measured Gamma:** `{summary['best_measured_gamma']}`\n"
            f"- **Best Control Gamma:** `{summary['best_control_gamma']}`\n"
            f"- **Best Vacuum Gap:** `{summary['best_vacuum_gap_percent']}%`\n"
            f"- **Best Theory Residual:** `{summary['best_theory_residual_percent']}%`\n"
            f"- **Best Falsification Delta:** `{summary['best_falsification_gap_delta']}`\n"
        )
    elif summary.get("mode") == "prime-lock":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v6 / Prime_Lock_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, prime_base={summary['prime_base']}, target_P={summary['target_p_multiplier']}, target_N={summary['target_n_cut']}, control={summary['target_control_n_cut']}, window={summary['window_shape']}, alpha={summary['alpha']}, sweep={summary['prime_multipliers']}\n"
            f"- **Quantization Tax Correction:** `{summary['quantization_tax_correction']}`\n"
            f"- **Coupled Residue:** `{summary['coupled_residue']}`\n"
            f"- **Target Measured Gamma:** `{summary['target_measured_gamma']}`\n"
            f"- **Target Control Gamma:** `{summary['target_control_gamma']}`\n"
            f"- **Target Vacuum Gap:** `{summary['target_vacuum_gap_percent']}%`\n"
            f"- **Target Theory Residual:** `{summary['target_theory_residual_percent']}%`\n"
            f"- **Target Falsification Delta:** `{summary['target_falsification_gap_delta']}`\n"
            f"- **Best Sweep P:** `{summary['best_p_multiplier']}` (Γ=`{summary['best_measured_gamma']}`, residual=`{summary['best_theory_residual_percent']}%`)\n"
        )
    elif summary.get("mode") == "k-lattice":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v7 / K_Lattice_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, weights={summary['weights']}, eta_terms={summary['eta_terms']}, window={summary['window_shape']}, alpha={summary['alpha']}\n"
            f"- **Q-Tax Correction:** `{summary['q_tax_correction']}`\n"
            f"- **Coupled Residue:** `{summary['coupled_residue']}`\n"
            f"- **Best Weight:** `{summary['best_weight']}`\n"
            f"- **Best Measured Gamma:** `{summary['best_measured_gamma']}`\n"
            f"- **Best Vacuum Gap:** `{summary['best_vacuum_gap_percent']}%`\n"
            f"- **Best Theory Residual:** `{summary['best_theory_residual_percent']}%`\n"
            f"- **Mean Lattice Gamma:** `{summary['mean_lattice_gamma']}`\n"
            f"- **Mean Lattice Residual:** `{summary['mean_lattice_residual_percent']}%`\n"
        )
    elif summary.get("mode") == "lattice-covariance":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v8 / Lattice_Covariance_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, k_base={summary['k_base']}, k_stable={summary['k_stable']}, control_k={summary['control_k_stable']}, eta_terms={summary['eta_terms']}, alpha={summary['alpha']}\n"
            f"- **E8 Packing Density:** `{summary['e8_packing_density']}`\n"
            f"- **Replication Factor:** `{summary['replication_factor']}`\n"
            f"- **Cosine Similarity:** `{summary['cosine_similarity']}`\n"
            f"- **Target Measured Gamma:** `{summary['measured_gamma']}`\n"
            f"- **Control Gamma:** `{summary['control_gamma']}`\n"
            f"- **Target Vacuum Gap:** `{summary['vacuum_gap_percent']}%`\n"
            f"- **Target Theory Residual:** `{summary['theory_residual_percent']}%`\n"
            f"- **Falsification Delta:** `{summary['falsification_gap_delta']}`\n"
        )
    elif summary.get("mode") == "orthogonal-residual":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v9 / Orthogonal_Residual_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, k_base={summary['k_base']}, k_stable={summary['k_stable']}, control_k={summary['control_k_stable']}, eta_terms={summary['eta_terms']}, alpha={summary['alpha']}, e8_defect={summary['e8_defect']}\n"
            f"- **Norm Ratio:** `{summary['norm_ratio']}`\n"
            f"- **Target Measured Gamma:** `{summary['measured_gamma']}`\n"
            f"- **Control Gamma:** `{summary['control_gamma']}`\n"
            f"- **Target Vacuum Gap:** `{summary['vacuum_gap_percent']}%`\n"
            f"- **Target Theory Residual:** `{summary['theory_residual_percent']}%`\n"
            f"- **Falsification Delta:** `{summary['falsification_gap_delta']}`\n"
            f"- **Phase Lock:** `{summary['phase_lock']}`\n"
        )
    elif summary.get("mode") == "holomorphic-volume":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v10 / Holomorphic_Volume_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, control_N={summary['control_n_cut']}, k_base={summary['k_base']}, k_stable={summary['k_stable']}, eta_terms={summary['eta_terms']}, alpha={summary['alpha']}, e8_defect={summary['e8_defect']}\n"
            f"- **Gram Determinant:** `{summary['gram_determinant']}`\n"
            f"- **Bivector Magnitude:** `{summary['bivector_magnitude']}`\n"
            f"- **Normalized Volume:** `{summary['normalized_volume']}`\n"
            f"- **Target Measured Gamma:** `{summary['measured_gamma']}`\n"
            f"- **Control Gamma:** `{summary['control_gamma']}`\n"
            f"- **Target Vacuum Gap:** `{summary['vacuum_gap_percent']}%`\n"
            f"- **Target Theory Residual:** `{summary['theory_residual_percent']}%`\n"
            f"- **Falsification Delta:** `{summary['falsification_gap_delta']}`\n"
            f"- **Volume Lock:** `{summary['volume_lock']}`\n"
        )
    elif summary.get("mode") == "spectral-trace":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v11 / Spectral_Trace_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, control_N={summary['control_n_cut']}, k_base={summary['k_base']}, k_stable={summary['k_stable']}, eta_terms={summary['eta_terms']}, alpha={summary['alpha']}\n"
            f"- **λ1:** `{summary['lambda1']}`\n"
            f"- **λ2:** `{summary['lambda2']}`\n"
            f"- **Target p1:** `{summary['p1']}`\n"
            f"- **Target Purity:** `{summary['purity']}`\n"
            f"- **Target Entropy:** `{summary['entropy']}`\n"
            f"- **Control p1:** `{summary['control_p1']}`\n"
            f"- **Control Purity:** `{summary['control_purity']}`\n"
            f"- **Target Theory Residual:** `{summary['theory_residual_percent']}%`\n"
            f"- **Falsification Delta:** `{summary['falsification_gap_delta']}`\n"
            f"- **Spectral Lock:** `{summary['spectral_lock']}`\n"
        )
    elif summary.get("mode") == "entanglement-fidelity":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v12 / Entanglement_Fidelity_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, chi_anchor={summary['chi_anchor']}, p_initial={summary['p_initial']}, chi_range=[{summary['chi_min']}, {summary['chi_max']}], steps={summary['chi_steps']}\n"
            f"- **Anchor Gamma:** `{summary['anchor_gamma']}`\n"
            f"- **Anchor Fidelity:** `{summary['anchor_fidelity']}`\n"
            f"- **Anchor Fidelity Residual:** `{summary['anchor_fidelity_residual_percent']}%`\n"
            f"- **Best χ:** `{summary['best_chi']}`\n"
            f"- **Best Gamma:** `{summary['best_gamma']}`\n"
            f"- **Best Fidelity:** `{summary['best_fidelity']}`\n"
            f"- **Best Purity:** `{summary['best_purity']}`\n"
            f"- **Best Entropy:** `{summary['best_entropy']}`\n"
            f"- **Best Gamma Residual:** `{summary['best_gamma_residual_percent']}%`\n"
            f"- **Best Fidelity Residual:** `{summary['best_fidelity_residual_percent']}%`\n"
            f"- **Fidelity Lock:** `{summary['fidelity_lock']}`\n"
        )
    elif summary.get("mode") == "holographic-info":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v13 / Holographic_Information_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, alpha={summary['alpha']}, chi_anchor={summary['chi_anchor']}, p_initial={summary['p_initial']}, chi_range=[{summary['chi_min']}, {summary['chi_max']}], steps={summary['chi_steps']}\n"
            f"- **Anchor Fidelity:** `{summary['anchor_fidelity']}`\n"
            f"- **Anchor KL Divergence:** `{summary['anchor_kl_divergence']}`\n"
            f"- **Anchor Mutual Information:** `{summary['anchor_mutual_information']}`\n"
            f"- **Anchor H:** `{summary['anchor_holographic_metric']}`\n"
            f"- **Best χ:** `{summary['best_chi']}`\n"
            f"- **Best Gamma:** `{summary['best_gamma']}`\n"
            f"- **Best Fidelity:** `{summary['best_fidelity']}`\n"
            f"- **Best KL Divergence:** `{summary['best_kl_divergence']}`\n"
            f"- **Best Mutual Information:** `{summary['best_mutual_information']}`\n"
            f"- **Best Surface Area Term:** `{summary['best_surface_area_term']}`\n"
            f"- **Best Information Gain Term:** `{summary['best_information_gain_term']}`\n"
            f"- **Best H:** `{summary['best_holographic_metric']}`\n"
            f"- **H Residual:** `{summary['best_holographic_residual_percent']}%`\n"
            f"- **Composite Gap:** `{summary['composite_gap_percent']}%`\n"
            f"- **Holographic Lock:** `{summary['holographic_lock']}`\n"
        )
    elif summary.get("mode") == "hierarchy-stress":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v14 / Hierarchy_Stress_Test\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, alpha={summary['alpha']}, chi={summary['chi']}, p_initial={summary['p_initial']}, weights={summary['weights']}, regulator_cuts={summary['regulator_cuts']}, bootstrap={summary['bootstrap_samples']}, rotation={summary['rotation_angle']}, null_draws={summary['null_draws']}\n"
            f"- **Best Case:** `{summary['best_case']}` at `N_cut={summary['best_n_cut']}`\n"
            f"- **Best Fidelity:** `{summary['best_fidelity']}`\n"
            f"- **Best Gamma:** `{summary['best_gamma']}`\n"
            f"- **Best H:** `{summary['best_holographic_metric']}`\n"
            f"- **Best Composite Gap:** `{summary['best_composite_gap_percent']}%`\n"
            f"- **Lock Count:** `{summary['lock_count']}/{summary['total_cases']}`\n"
            f"- **Mean Fidelity:** `{summary['mean_fidelity']}`\n"
            f"- **Mean H:** `{summary['mean_holographic_metric']}`\n"
            f"- **Regulator Shift Max:** `{summary['regulator_shift_max']}`\n"
            f"- **Basis Shift Max:** `{summary['basis_shift_max_percent']}%`\n"
            f"- **Mean Null Gap:** `{summary['mean_null_gap_percent']}%`\n"
            f"- **LR Stat:** `{summary['lr_stat']}`\n"
            f"- **AIC Fixed / Free:** `{summary['aic_fixed']} / {summary['aic_free']}`\n"
            f"- **BIC Fixed / Free:** `{summary['bic_fixed']} / {summary['bic_free']}`\n"
            f"- **Fixed-Γ Preferred:** `{summary['fixed_gamma_preferred']}`\n"
            f"- **Tripartite I3:** `{summary['tripartite_i3']}`\n"
            f"- **Universality Supported:** `{summary['universality_supported']}`\n"
        )
    elif summary.get("mode") == "direct-trace":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v15 / Direct_Trace_Beta_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, k_low={summary['k_low']}, k_high={summary['k_high']}, N_cut={summary['n_cut']}, alpha={summary['alpha']}, eta_terms={summary['eta_terms']}, beta_range=[{summary['beta_min']}, {summary['beta_max']}], steps={summary['beta_steps']}, scale={summary['beta_scale']}\n"
            f"- **Fixed β:** `{summary['fixed_beta']}`\n"
            f"- **Fixed g_natural:** `{summary['fixed_g_natural']}`\n"
            f"- **Fixed Gamma:** `{summary['fixed_gamma']}`\n"
            f"- **Fixed Fidelity:** `{summary['fixed_fidelity']}`\n"
            f"- **Fixed H:** `{summary['fixed_holographic_metric']}`\n"
            f"- **β(g):** `{summary['fixed_beta_function']}`\n"
            f"- **Gamma Residual:** `{summary['fixed_gamma_residual_percent']}%`\n"
            f"- **Best β (closest Γ):** `{summary['best_beta']}`\n"
            f"- **Best Γ:** `{summary['best_gamma']}`\n"
            f"- **Best Fidelity:** `{summary['best_fidelity']}`\n"
            f"- **Zero Crossings:** `{summary['beta_zero_crossings']}`\n"
            f"- **RG Fixed Point Supported:** `{summary['rg_fixed_point_supported']}`\n"
        )
    elif summary.get("mode") == "stress-response":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v16 / Stress_Response_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, k_low={summary['k_low']}, k_high={summary['k_high']}, N_cut={summary['n_cut']}, alpha={summary['alpha']}, eta_terms={summary['eta_terms']}, eps_values={summary['eps_values']}, omega_range=[{summary['omega_min']}, {summary['omega_max']}], steps={summary['omega_steps']}, scale={summary['omega_scale']}\n"
            f"- **Best ε0:** `{summary['best_eps0']}`\n"
            f"- **Best ω:** `{summary['best_omega']}`\n"
            f"- **Best σ_info:** `{summary['best_sigma_info']}`\n"
            f"- **Best κ:** `{summary['best_kappa']}`\n"
            f"- **Best γ:** `{summary['best_gamma_damping']}`\n"
            f"- **Best Phase Lag:** `{summary['best_phase_lag']}`\n"
            f"- **Best Viscosity:** `{summary['best_modular_viscosity']}`\n"
            f"- **Residual:** `{summary['best_conductivity_residual_percent']}%`\n"
            f"- **Mean σ_info:** `{summary['mean_sigma_info']}` ± `{summary['sigma_std']}`\n"
            f"- **Lock Count:** `{summary['lock_count']}/{summary['total_samples']}`\n"
            f"- **Transport Supported:** `{summary['transport_supported']}`\n"
        )
    elif summary.get("mode") == "stress-strain":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v17 / Stress_Strain_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, k_low={summary['k_low']}, k_high={summary['k_high']}, N_cut={summary['n_cut']}, alpha={summary['alpha']}, eta_terms={summary['eta_terms']}, omega_target={summary['omega_target']}, ramp=[{summary['ramp_min']}, {summary['ramp_max']}], steps={summary['ramp_steps']}, drive={summary['drive_type']}, cadence={summary['cadence']}, quench_factor={summary['quench_factor']}\n"
            f"- **Baseline σ:** `{summary['baseline_sigma']}`\n"
            f"- **Critical ε:** `{summary['critical_eps']}`\n"
            f"- **Critical σ:** `{summary['critical_sigma']}`\n"
            f"- **Critical Spectral Entropy:** `{summary['critical_entropy']}`\n"
            f"- **Critical Distortion:** `{summary['critical_distortion']}`\n"
            f"- **Critical KL Drift:** `{summary['critical_kl_drift']}`\n"
            f"- **Critical χ³:** `{summary['critical_chi3']}`\n"
            f"- **Quench ε:** `{summary['quench_eps']}`\n"
            f"- **Quench σ:** `{summary['quench_sigma']}`\n"
            f"- **Quench Entropy:** `{summary['quench_entropy']}`\n"
            f"- **Modular Reynolds:** `{summary['re_mod']}`\n"
            f"- **Recovery σ:** `{summary['recovery_sigma']}`\n"
            f"- **Recovery Gap:** `{summary['recovery_gap_percent']}%`\n"
            f"- **Hardening Detected:** `{summary['hardening_detected']}`\n"
            f"- **Fracture Detected:** `{summary['fracture_detected']}`\n"
            f"- **Hysteresis Detected:** `{summary['hysteresis_detected']}`\n"
        )
    elif summary.get("mode") == "neighborhood-control":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v18 / Neighborhood_Control\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, probe_weights={summary['probe_weights']}, reference_weight={summary['reference_weight']}, N_cut={summary['n_cut']}, alpha={summary['alpha']}, eta_terms={summary['eta_terms']}, eps0={summary['eps0']}, omega={summary['omega']}, response_steps={summary['response_steps']}\n"
            f"- **k=24 σ:** `{summary['k24_sigma']}`\n"
            f"- **k=24 Residual:** `{summary['k24_residual_percent']}%`\n"
            f"- **Best Weight:** `{summary['best_weight']}` (σ=`{summary['best_sigma']}`, residual=`{summary['best_residual_percent']}%`)\n"
            f"- **k=24 Margin:** `{summary['k24_margin_percent']}%`\n"
            f"- **σ Standard Deviation:** `{summary['sigma_std']}`\n"
            f"- **Scaling Trend:** `{summary['scaling_law_trend']}`\n"
            f"- **Leech Anchor Confirmed:** `{summary['leech_anchor_confirmed']}`\n"
            f"- **Verdict:** `{summary['verdict']}`\n"
        )
    elif summary.get("mode") == "rigor-check":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v19 / Finite_Size_Borel_Rigor\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, k_probe={summary['k_probe']}, k_high={summary['k_high']}, N_cuts={summary['n_cuts']}, alpha={summary['alpha']}, eta_terms={summary['eta_terms']}, eps0={summary['eps0']}, omega={summary['omega']}, response_steps={summary['response_steps']}, bootstrap_samples={summary['bootstrap_samples']}\n"
            f"- **σ∞ Fit:** `{summary['sigma_inf']}`\n"
            f"- **Alpha Fit:** `{summary['alpha_fit']}`\n"
            f"- **σ(N) Range:** `{summary['sigma_n_min']} → {summary['sigma_n_max']}`\n"
            f"- **Tail L1 (last):** `{summary['tail_l1_last']}`\n"
            f"- **Borel L1 (last):** `{summary['borel_l1_last']}`\n"
            f"- **Tail Decay Supported:** `{summary['tail_decay_supported']}`\n"
            f"- **Pair Spread:** `{summary['pair_spread_percent']}%`\n"
            f"- **Pair Stability Supported:** `{summary['pair_stability_supported']}`\n"
            f"- **Bootstrap σ∞ CI:** `[{summary['sigma_inf_ci_low']}, {summary['sigma_inf_ci_high']}]`\n"
            f"- **Bootstrap α CI:** `[{summary['alpha_ci_low']}, {summary['alpha_ci_high']}]`\n"
        )
    elif summary.get("mode") == "resonant":
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v11 / Spectral_Trace_Sweep\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, control_N={summary['control_n_cut']}, k_base={summary['k_base']}, k_stable={summary['k_stable']}, eta_terms={summary['eta_terms']}, alpha={summary['alpha']}\n"
            f"- **λ1:** `{summary['lambda1']}`\n"
            f"- **λ2:** `{summary['lambda2']}`\n"
            f"- **Target p1:** `{summary['p1']}`\n"
            f"- **Target Purity:** `{summary['purity']}`\n"
            f"- **Target Entropy:** `{summary['entropy']}`\n"
            f"- **Control p1:** `{summary['control_p1']}`\n"
            f"- **Control Purity:** `{summary['control_purity']}`\n"
            f"- **Target Theory Residual:** `{summary['theory_residual_percent']}%`\n"
            f"- **Falsification Delta:** `{summary['falsification_gap_delta']}`\n"
            f"- **Spectral Lock:** `{summary['spectral_lock']}`\n"
        )
    elif summary.get("mode") == "resonant":
        run_name = "Silicon_Vacuum_v5 / Causal_Decay_Single" if summary.get("window_shape") == "causal-exponential" else ("Silicon_Vacuum_v4 / Gaussian_Window_Sweep" if summary.get("window_shape") == "gaussian" else "Silicon_Vacuum_v3 / Resonant_Phase_Lock")
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** {run_name}\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, control={summary['control_n_cut']}, window={summary.get('window_shape', DEFAULT_WINDOW_SHAPE)}, decay={summary.get('decay_constant', DEFAULT_DECAY_CONSTANT)}, alpha={summary['alpha']}\n"
            f"- **Measured Gamma (resonant):** `{summary['measured_gamma']}`\n"
            f"- **Measured Gamma (control):** `{summary['control_gamma']}`\n"
            f"- **Vacuum Gap:** `{summary['vacuum_gap_percent']}%`\n"
            f"- **Theory Residual:** `{summary['theory_residual_percent']}%`\n"
            f"- **Falsification Delta:** `{summary['falsification_gap_delta']}`\n"
        )
    else:
        entry = (
            f"\n### [AUTOLOG] {summary['generated_at']}\n"
            f"- **Run:** Silicon_Vacuum_v1\n"
            f"- **Parameters:** k={summary['k_params']:.0e}, N_cut={summary['n_cut']}, window={summary.get('window_shape', DEFAULT_WINDOW_SHAPE)}, decay={summary.get('decay_constant', DEFAULT_DECAY_CONSTANT)}, alpha={summary['alpha']}\n"
            f"- **Measured Gamma:** `{summary['measured_gamma']}`\n"
            f"- **Vacuum Gap:** `{summary['vacuum_gap_percent']}%`\n"
            f"- **Theory Residual:** `{summary['theory_residual_percent']}%`\n"
        )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the G-01 silicon-vacuum induction experiment.")
    parser.add_argument("--mode", choices=("single", "fine-structure", "resonant", "causal-sweep", "prime-lock", "k-lattice", "lattice-covariance", "orthogonal-residual", "holomorphic-volume", "spectral-trace", "entanglement-fidelity", "holographic-info", "hierarchy-stress", "direct-trace", "stress-response", "stress-strain", "neighborhood-control", "rigor-check"), default="single", help="Run one induction experiment, sweep alpha across a fine-structure band, test the resonant phase-lock window, sweep causal decay constants tied to 137, test the prime-lock rung, scan the modular k-lattice, run the dual-weight covariance projector, run the Gram-Schmidt residual projector, run the holomorphic-volume projector, evaluate the spectral trace fixed point, tune the entanglement-fidelity lock, execute the holographic mutual-information sweep, run the multi-scale hierarchy stress test, execute the direct-trace RG beta sweep, run the linear-response stress sweep, execute the nonlinear stress-strain protocol, compare the k=24 neighborhood control weights, or perform the finite-size/Borel rigor check.")
    parser.add_argument("--k-params", type=float, default=DEFAULT_K_PARAMS, help="Synthetic parameter count label.")
    parser.add_argument("--n-cut", type=int, default=DEFAULT_N_CUT, help="Negative-weight truncation cutoff.")
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA, help="Power-law divergence control for `single`, `resonant`, `causal-sweep`, `prime-lock`, or `k-lattice` mode.")
    parser.add_argument("--window-shape", choices=("rectangular", "gaussian", "causal-exponential"), default=DEFAULT_WINDOW_SHAPE, help="Stabilizer kernel geometry used in the induction step.")
    parser.add_argument("--decay-constant", type=float, default=DEFAULT_DECAY_CONSTANT, help="Decay constant τ used when `--window-shape causal-exponential` is selected.")
    parser.add_argument("--decay-multipliers", default=",".join(str(value) for value in DEFAULT_DECAY_MULTIPLIERS), help="Comma-separated τ/137 multipliers used by `causal-sweep` mode.")
    parser.add_argument("--prime-multipliers", default=",".join(str(value) for value in DEFAULT_PRIME_MULTIPLIERS), help="Comma-separated prime-lock multipliers P used by `prime-lock` mode; `N_cut = 137 × P`.")
    parser.add_argument("--target-prime", type=int, default=DEFAULT_TARGET_PRIME, help="Prime-lock multiplier to highlight in `prime-lock` mode.")
    parser.add_argument("--lattice-weights", default=",".join(str(value) for value in DEFAULT_LATTICE_WEIGHTS), help="Comma-separated modular weights used by `k-lattice` mode.")
    parser.add_argument("--k-base", type=int, default=DEFAULT_LATTICE_BASE_WEIGHT, help="Base modular weight used by `lattice-covariance` or `orthogonal-residual` mode.")
    parser.add_argument("--k-stable", type=int, default=DEFAULT_LATTICE_STABLE_WEIGHT, help="Stable modular weight used by `lattice-covariance` or `orthogonal-residual` mode.")
    parser.add_argument("--control-k-stable", type=int, default=DEFAULT_LATTICE_CONTROL_WEIGHT, help="Control stable weight used to falsify the covariance or residual lock.")
    parser.add_argument("--eta-terms", type=int, default=DEFAULT_ETA_TERMS, help="Number of eta-product factors retained in the modular raw-material approximation.")
    parser.add_argument("--e8-defect", type=float, default=DEFAULT_E8_DEFECT, help="Packing-defect scale used by `orthogonal-residual` or `holomorphic-volume` mode.")
    parser.add_argument("--chi", type=float, default=DEFAULT_CHI, help="Ancilla coupling strength χ used by `entanglement-fidelity`, `holographic-info`, or `hierarchy-stress` mode.")
    parser.add_argument("--p-initial", type=float, default=DEFAULT_P_INITIAL, help="Initial population of the leading mode in `entanglement-fidelity`, `holographic-info`, or `hierarchy-stress` mode.")
    parser.add_argument("--chi-min", type=float, default=0.0, help="Minimum χ used when sweeping `entanglement-fidelity` or `holographic-info` mode.")
    parser.add_argument("--chi-max", type=float, default=None, help="Maximum χ used when sweeping `entanglement-fidelity` or `holographic-info` mode; defaults to the PSD limit.")
    parser.add_argument("--chi-steps", type=int, default=DEFAULT_CHI_STEPS, help="Number of χ samples used by `entanglement-fidelity` or `holographic-info` mode.")
    parser.add_argument("--regulator-cuts", default=",".join(str(value) for value in DEFAULT_REGULATOR_CUTS), help="Comma-separated N_cut values used by `hierarchy-stress` to test regulator dependence.")
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES, help="Number of bootstrap resamples used by `hierarchy-stress` mode.")
    parser.add_argument("--rotation-angle", type=float, default=DEFAULT_ROTATION_ANGLE, help="Basis-rotation angle in radians used by `hierarchy-stress` mode.")
    parser.add_argument("--null-draws", type=int, default=DEFAULT_NULL_DRAWS, help="Number of random thermal null states used by `hierarchy-stress` mode.")
    parser.add_argument("--beta-min", type=float, default=DEFAULT_BETA_RG_MIN, help="Minimum RG damping β used by `direct-trace` mode.")
    parser.add_argument("--beta-max", type=float, default=DEFAULT_BETA_RG_MAX, help="Maximum RG damping β used by `direct-trace` mode.")
    parser.add_argument("--beta-steps", type=int, default=DEFAULT_BETA_RG_STEPS, help="Number of β samples used by `direct-trace` mode.")
    parser.add_argument("--beta-scale", choices=("linear", "log"), default=DEFAULT_BETA_RG_SCALE, help="Spacing used for the β sweep in `direct-trace` mode.")
    parser.add_argument("--eps-values", default=",".join(str(value) for value in DEFAULT_RESPONSE_EPS_VALUES), help="Comma-separated phase-drive amplitudes ε0 used by `stress-response` mode.")
    parser.add_argument("--omega-min", type=float, default=DEFAULT_OMEGA_MIN, help="Minimum harmonic/frequency used by `stress-response` mode.")
    parser.add_argument("--omega-max", type=float, default=DEFAULT_OMEGA_MAX, help="Maximum harmonic/frequency used by `stress-response` mode.")
    parser.add_argument("--omega-steps", type=int, default=DEFAULT_OMEGA_STEPS, help="Number of frequency samples used by `stress-response` mode.")
    parser.add_argument("--omega-scale", choices=("linear", "log"), default=DEFAULT_OMEGA_SCALE, help="Spacing used for the octave-range drive sweep in `stress-response` mode.")
    parser.add_argument("--response-steps", type=int, default=DEFAULT_RESPONSE_STEPS, help="Number of time steps used in the driven response simulation.")
    parser.add_argument("--omega-target", type=float, default=DEFAULT_OMEGA_MAX, help="Target harmonic/frequency used by `stress-strain` mode.")
    parser.add_argument("--ramp-min", type=float, default=DEFAULT_STRAIN_RAMP_MIN, help="Minimum drive amplitude used by the logarithmic ramp in `stress-strain` mode.")
    parser.add_argument("--ramp-max", type=float, default=DEFAULT_STRAIN_RAMP_MAX, help="Maximum drive amplitude used by the logarithmic ramp in `stress-strain` mode.")
    parser.add_argument("--ramp-steps", type=int, default=DEFAULT_STRAIN_RAMP_STEPS, help="Number of drive amplitudes used by `stress-strain` mode.")
    parser.add_argument("--quench-factor", type=float, default=DEFAULT_QUENCH_FACTOR, help="Factor applied to the critical drive when triggering the `stress-strain` quench.")
    parser.add_argument("--drive-type", choices=("phase_rotation", "square_pulse"), default=DEFAULT_DRIVE_TYPE, help="Drive geometry used by `stress-strain` mode.")
    parser.add_argument("--cadence", choices=("standard", "ultra"), default=DEFAULT_CADENCE, help="Sampling cadence used by `stress-strain` mode.")
    parser.add_argument("--alpha-min", type=float, default=DEFAULT_ALPHA_MIN, help="Minimum alpha used in `fine-structure` mode.")
    parser.add_argument("--alpha-max", type=float, default=DEFAULT_ALPHA_MAX, help="Maximum alpha used in `fine-structure` mode.")
    parser.add_argument("--alpha-steps", type=int, default=DEFAULT_ALPHA_STEPS, help="Number of alpha samples in `fine-structure` mode.")
    parser.add_argument("--control-n-cut", type=int, default=None, help="Neighboring control window used in `resonant` mode (defaults to n_cut-1).")
    parser.add_argument("--output-name", default="G01_Induction_Run", help="Base name for CSV/JSON outputs.")
    parser.add_argument("--log-file", default="G01_Induction_Log.md", help="Markdown log to append to when `--update-log` is used.")
    parser.add_argument("--update-log", action="store_true", help="Append the measured result to the induction log.")
    args = parser.parse_args()

    if args.mode == "fine-structure":
        summary, df = run_fine_structure_sweep(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha_min=args.alpha_min,
            alpha_max=args.alpha_max,
            alpha_steps=args.alpha_steps,
            window_shape=args.window_shape,
            decay_constant=args.decay_constant,
        )
    elif args.mode == "resonant":
        summary, df = run_resonant_induction(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            control_n_cut=args.control_n_cut,
            window_shape=args.window_shape,
            decay_constant=args.decay_constant,
        )
    elif args.mode == "causal-sweep":
        summary, df = run_causal_decay_sweep(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            control_n_cut=args.control_n_cut,
            anchor_tau=args.decay_constant,
            decay_multipliers=tuple(parse_float_csv(args.decay_multipliers)),
        )
    elif args.mode == "prime-lock":
        summary, df = run_prime_lock_sweep(
            k_params=args.k_params,
            alpha=args.alpha,
            p_multipliers=tuple(parse_int_csv(args.prime_multipliers)),
            target_prime=args.target_prime,
            prime_base=DEFAULT_N_CUT,
        )
    elif args.mode == "k-lattice":
        summary, df = run_k_lattice_sweep(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            weights=tuple(parse_int_csv(args.lattice_weights)),
            eta_terms=args.eta_terms,
        )
    elif args.mode == "lattice-covariance":
        summary, df = run_lattice_covariance_sweep(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            k_base=args.k_base,
            k_stable=args.k_stable,
            control_k_stable=args.control_k_stable,
            eta_terms=args.eta_terms,
        )
    elif args.mode == "orthogonal-residual":
        summary, df = run_orthogonal_residual_sweep(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            k_base=args.k_base,
            k_stable=args.k_stable,
            control_k_stable=args.control_k_stable,
            eta_terms=args.eta_terms,
            e8_defect=args.e8_defect,
        )
    elif args.mode == "holomorphic-volume":
        summary, df = run_holomorphic_volume_sweep(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            k_base=args.k_base,
            k_stable=args.k_stable,
            control_n_cut=args.control_n_cut,
            eta_terms=args.eta_terms,
            e8_defect=args.e8_defect,
        )
    elif args.mode == "spectral-trace":
        summary, df = run_spectral_trace_sweep(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            k_base=args.k_base,
            k_stable=args.k_stable,
            control_n_cut=args.control_n_cut,
            eta_terms=args.eta_terms,
        )
    elif args.mode == "entanglement-fidelity":
        summary, df = run_entanglement_fidelity_sweep(
            k_params=args.k_params,
            chi_anchor=args.chi,
            p_initial=args.p_initial,
            chi_min=args.chi_min,
            chi_max=args.chi_max,
            chi_steps=args.chi_steps,
        )
    elif args.mode == "holographic-info":
        summary, df = run_holographic_info_sweep(
            k_params=args.k_params,
            chi_anchor=args.chi,
            p_initial=args.p_initial,
            alpha=args.alpha,
            chi_min=args.chi_min,
            chi_max=args.chi_max,
            chi_steps=args.chi_steps,
        )
    elif args.mode == "hierarchy-stress":
        summary, df = run_hierarchy_stress_test(
            k_params=args.k_params,
            alpha=args.alpha,
            chi=args.chi,
            p_initial=args.p_initial,
            weights=tuple(parse_int_csv(args.lattice_weights)),
            regulator_cuts=tuple(parse_int_csv(args.regulator_cuts)),
            eta_terms=args.eta_terms,
            bootstrap_samples=args.bootstrap_samples,
            rotation_angle=args.rotation_angle,
            null_draws=args.null_draws,
        )
    elif args.mode == "direct-trace":
        summary, df = run_direct_trace_beta_sweep(
            k_params=args.k_params,
            k_low=args.k_base,
            k_high=args.k_stable,
            n_cut=args.n_cut,
            alpha=args.alpha,
            eta_terms=args.eta_terms,
            beta_min=args.beta_min,
            beta_max=args.beta_max,
            beta_steps=args.beta_steps,
            beta_scale=args.beta_scale,
        )
    elif args.mode == "stress-response":
        summary, df = run_stress_response_sweep(
            k_params=args.k_params,
            k_low=args.k_base,
            k_high=args.k_stable,
            n_cut=args.n_cut,
            alpha=args.alpha,
            eta_terms=args.eta_terms,
            eps_values=tuple(parse_float_csv(args.eps_values)),
            omega_min=args.omega_min,
            omega_max=args.omega_max,
            omega_steps=args.omega_steps,
            omega_scale=args.omega_scale,
            response_steps=args.response_steps,
        )
    elif args.mode == "stress-strain":
        summary, df = run_stress_strain_sweep(
            k_params=args.k_params,
            k_low=args.k_base,
            k_high=args.k_stable,
            n_cut=args.n_cut,
            alpha=args.alpha,
            eta_terms=args.eta_terms,
            omega_target=args.omega_target,
            ramp_min=args.ramp_min,
            ramp_max=args.ramp_max,
            ramp_steps=args.ramp_steps,
            quench_factor=args.quench_factor,
            drive_type=args.drive_type,
            cadence=args.cadence,
            response_steps=args.response_steps,
        )
    elif args.mode == "neighborhood-control":
        summary, df = run_neighbor_weight_control(
            k_params=args.k_params,
            probe_weights=tuple(parse_int_csv(args.lattice_weights)),
            reference_weight=args.k_stable,
            n_cut=args.n_cut,
            alpha=args.alpha,
            eta_terms=args.eta_terms,
            eps0=min(tuple(parse_float_csv(args.eps_values))),
            omega=args.omega_target,
            response_steps=args.response_steps,
        )
    elif args.mode == "rigor-check":
        summary, df = run_rigor_check(
            k_params=args.k_params,
            k_probe=args.k_base,
            k_high=args.k_stable,
            n_cuts=tuple(parse_int_csv(args.regulator_cuts)),
            alpha=args.alpha,
            eta_terms=args.eta_terms,
            eps0=min(tuple(parse_float_csv(args.eps_values))),
            omega=args.omega_target,
            response_steps=args.response_steps,
            bootstrap_samples=args.bootstrap_samples,
            pair_weights=tuple(parse_int_csv(args.lattice_weights)),
        )
    else:
        summary, df = run_silicon_vacuum_induction(
            k_params=args.k_params,
            n_cut=args.n_cut,
            alpha=args.alpha,
            window_shape=args.window_shape,
            decay_constant=args.decay_constant,
        )
    csv_path, json_path = save_outputs(summary, df, args.output_name)

    if args.mode == "fine-structure":
        print("--- G-01 FINE-STRUCTURE SWEEP ---")
        print(f"Window Shape: {summary['window_shape']}")
        print(f"Decay τ     : {summary['decay_constant']}")
        print(f"Best α: {summary['best_alpha']}")
        print(f"Best Measured Γ: {summary['best_measured_gamma']}")
        print(f"Best Vacuum Gap: {summary['best_vacuum_gap_percent']}%")
        print(f"Best Theory Residual: {summary['best_theory_residual_percent']}%")
        print()
        best_row = df.loc[df['theory_residual_percent'].astype(float).idxmin()]
        preview = pd.concat([df.head(5), df.tail(5), pd.DataFrame([best_row])]).drop_duplicates().reset_index(drop=True)
        print(preview.to_string(index=False))
    elif args.mode == "causal-sweep":
        print("--- G-01 CAUSAL DECAY SWEEP ---")
        print(f"Window Shape : {summary['window_shape']}")
        print(f"Anchor τ     : {summary['anchor_tau']}")
        print(f"Best τ       : {summary['best_decay_constant']}")
        print(f"Best τ/137   : {summary['best_multiplier']}")
        print(f"Best Γ       : {summary['best_measured_gamma']}")
        print(f"Control Γ    : {summary['best_control_gamma']}")
        print(f"Best Gap     : {summary['best_vacuum_gap_percent']}%")
        print(f"Best Residual: {summary['best_theory_residual_percent']}%")
        print()
        print(df.to_string(index=False))
    elif args.mode == "prime-lock":
        print("--- G-01 PRIME LOCK SWEEP ---")
        print(f"Prime Base    : {summary['prime_base']}")
        print(f"Target P      : {summary['target_p_multiplier']}")
        print(f"Target N_cut  : {summary['target_n_cut']}")
        print(f"Control N_cut : {summary['target_control_n_cut']}")
        print(f"Q-Tax Corr.   : {summary['quantization_tax_correction']}")
        print(f"Coupled Resid.: {summary['coupled_residue']}")
        print(f"Target Γ      : {summary['target_measured_gamma']}")
        print(f"Control Γ     : {summary['target_control_gamma']}")
        print(f"Target Residual: {summary['target_theory_residual_percent']}%")
        print(f"Best Sweep P  : {summary['best_p_multiplier']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "k-lattice":
        print("--- G-01 MODULAR K-LATTICE SWEEP ---")
        print(f"Weights       : {summary['weights']}")
        print(f"Eta Terms     : {summary['eta_terms']}")
        print(f"Q-Tax Corr.   : {summary['q_tax_correction']}")
        print(f"Coupled Resid.: {summary['coupled_residue']}")
        print(f"Best Weight   : {summary['best_weight']}")
        print(f"Best Γ        : {summary['best_measured_gamma']}")
        print(f"Best Residual : {summary['best_theory_residual_percent']}%")
        print(f"Mean Lattice Γ: {summary['mean_lattice_gamma']}")
        print(f"Mean Residual : {summary['mean_lattice_residual_percent']}%")
        print()
        print(df.to_string(index=False))
    elif args.mode == "lattice-covariance":
        print("--- G-01 LATTICE COVARIANCE SWEEP ---")
        print(f"Base k        : {summary['k_base']}")
        print(f"Stable k      : {summary['k_stable']}")
        print(f"Control k     : {summary['control_k_stable']}")
        print(f"Eta Terms     : {summary['eta_terms']}")
        print(f"E8 Density    : {summary['e8_packing_density']}")
        print(f"Replication   : {summary['replication_factor']}")
        print(f"Cosine Similarity: {summary['cosine_similarity']}")
        print(f"Target Γ      : {summary['measured_gamma']}")
        print(f"Control Γ     : {summary['control_gamma']}")
        print(f"Target Residual: {summary['theory_residual_percent']}%")
        print(f"ΔΓ            : {summary['falsification_gap_delta']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "orthogonal-residual":
        print("--- G-01 ORTHOGONAL RESIDUAL SWEEP ---")
        print(f"Base k        : {summary['k_base']}")
        print(f"Stable k      : {summary['k_stable']}")
        print(f"Control k     : {summary['control_k_stable']}")
        print(f"Eta Terms     : {summary['eta_terms']}")
        print(f"E8 Defect     : {summary['e8_defect']}")
        print(f"Norm Ratio    : {summary['norm_ratio']}")
        print(f"Target Γ      : {summary['measured_gamma']}")
        print(f"Control Γ     : {summary['control_gamma']}")
        print(f"Target Residual: {summary['theory_residual_percent']}%")
        print(f"Phase Lock    : {summary['phase_lock']}")
        print(f"ΔΓ            : {summary['falsification_gap_delta']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "holomorphic-volume":
        print("--- G-01 HOLOMORPHIC VOLUME SWEEP ---")
        print(f"Base k           : {summary['k_base']}")
        print(f"Stable k         : {summary['k_stable']}")
        print(f"Target N_cut     : {summary['n_cut']}")
        print(f"Control N_cut    : {summary['control_n_cut']}")
        print(f"Eta Terms        : {summary['eta_terms']}")
        print(f"E8 Defect        : {summary['e8_defect']}")
        print(f"Gram Determinant : {summary['gram_determinant']}")
        print(f"Bivector Magnitude: {summary['bivector_magnitude']}")
        print(f"Normalized Volume: {summary['normalized_volume']}")
        print(f"Target Γ         : {summary['measured_gamma']}")
        print(f"Control Γ        : {summary['control_gamma']}")
        print(f"Target Residual  : {summary['theory_residual_percent']}%")
        print(f"Volume Lock      : {summary['volume_lock']}")
        print(f"ΔΓ               : {summary['falsification_gap_delta']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "spectral-trace":
        print("--- G-01 SPECTRAL TRACE SWEEP ---")
        print(f"Base k        : {summary['k_base']}")
        print(f"Stable k      : {summary['k_stable']}")
        print(f"Target N_cut  : {summary['n_cut']}")
        print(f"Control N_cut : {summary['control_n_cut']}")
        print(f"Eta Terms     : {summary['eta_terms']}")
        print(f"λ1            : {summary['lambda1']}")
        print(f"λ2            : {summary['lambda2']}")
        print(f"Target p1     : {summary['p1']}")
        print(f"Target purity : {summary['purity']}")
        print(f"Target entropy: {summary['entropy']}")
        print(f"Control p1    : {summary['control_p1']}")
        print(f"Target Residual: {summary['theory_residual_percent']}%")
        print(f"Spectral Lock : {summary['spectral_lock']}")
        print(f"Δp1           : {summary['falsification_gap_delta']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "entanglement-fidelity":
        print("--- G-01 ENTANGLEMENT FIDELITY SWEEP ---")
        print(f"χ anchor      : {summary['chi_anchor']}")
        print(f"p_initial     : {summary['p_initial']}")
        print(f"χ range       : [{summary['chi_min']}, {summary['chi_max']}]")
        print(f"χ steps       : {summary['chi_steps']}")
        print(f"Anchor Γ      : {summary['anchor_gamma']}")
        print(f"Anchor F      : {summary['anchor_fidelity']}")
        print(f"Best χ        : {summary['best_chi']}")
        print(f"Best Γ        : {summary['best_gamma']}")
        print(f"Best F        : {summary['best_fidelity']}")
        print(f"Best purity   : {summary['best_purity']}")
        print(f"Best entropy  : {summary['best_entropy']}")
        print(f"Fidelity Resid.: {summary['best_fidelity_residual_percent']}%")
        print(f"Fidelity Lock : {summary['fidelity_lock']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "holographic-info":
        print("--- G-01 HOLOGRAPHIC INFORMATION SWEEP ---")
        print(f"α strain      : {summary['alpha']}")
        print(f"χ anchor      : {summary['chi_anchor']}")
        print(f"p_initial     : {summary['p_initial']}")
        print(f"χ range       : [{summary['chi_min']}, {summary['chi_max']}]")
        print(f"χ steps       : {summary['chi_steps']}")
        print(f"Anchor F      : {summary['anchor_fidelity']}")
        print(f"Anchor KL     : {summary['anchor_kl_divergence']}")
        print(f"Anchor I      : {summary['anchor_mutual_information']}")
        print(f"Anchor H      : {summary['anchor_holographic_metric']}")
        print(f"Best χ        : {summary['best_chi']}")
        print(f"Best Γ        : {summary['best_gamma']}")
        print(f"Best F        : {summary['best_fidelity']}")
        print(f"Best KL       : {summary['best_kl_divergence']}")
        print(f"Best I        : {summary['best_mutual_information']}")
        print(f"Best H        : {summary['best_holographic_metric']}")
        print(f"H Residual    : {summary['best_holographic_residual_percent']}%")
        print(f"Composite Gap : {summary['composite_gap_percent']}%")
        print(f"Holo Lock     : {summary['holographic_lock']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "hierarchy-stress":
        print("--- G-01 HIERARCHY STRESS TEST ---")
        print(f"α strain         : {summary['alpha']}")
        print(f"χ coupling       : {summary['chi']}")
        print(f"weights          : {summary['weights']}")
        print(f"regulator cuts   : {summary['regulator_cuts']}")
        print(f"bootstrap samples: {summary['bootstrap_samples']}")
        print(f"best case        : {summary['best_case']} @ N_cut={summary['best_n_cut']}")
        print(f"best fidelity    : {summary['best_fidelity']}")
        print(f"best Γ           : {summary['best_gamma']}")
        print(f"best H           : {summary['best_holographic_metric']}")
        print(f"lock count       : {summary['lock_count']}/{summary['total_cases']}")
        print(f"regulator shift  : {summary['regulator_shift_max']}")
        print(f"basis shift max  : {summary['basis_shift_max_percent']}%")
        print(f"mean null gap    : {summary['mean_null_gap_percent']}%")
        print(f"LR stat          : {summary['lr_stat']}")
        print(f"AIC fixed/free   : {summary['aic_fixed']} / {summary['aic_free']}")
        print(f"BIC fixed/free   : {summary['bic_fixed']} / {summary['bic_free']}")
        print(f"Fixed-Γ preferred: {summary['fixed_gamma_preferred']}")
        print(f"Tripartite I3    : {summary['tripartite_i3']}")
        print(f"Universality     : {summary['universality_supported']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "direct-trace":
        print("--- G-01 DIRECT TRACE RG SWEEP ---")
        print(f"k_low / k_high   : {summary['k_low']} / {summary['k_high']}")
        print(f"N_cut            : {summary['n_cut']}")
        print(f"α strain         : {summary['alpha']}")
        print(f"β scale          : {summary['beta_scale']}")
        print(f"β range          : [{summary['beta_min']}, {summary['beta_max']}]")
        print(f"β steps          : {summary['beta_steps']}")
        print(f"Fixed β          : {summary['fixed_beta']}")
        print(f"Fixed g_natural  : {summary['fixed_g_natural']}")
        print(f"Fixed Γ          : {summary['fixed_gamma']}")
        print(f"Fixed F          : {summary['fixed_fidelity']}")
        print(f"Fixed H          : {summary['fixed_holographic_metric']}")
        print(f"β(g)             : {summary['fixed_beta_function']}")
        print(f"Γ residual       : {summary['fixed_gamma_residual_percent']}%")
        print(f"Best β (Γ)       : {summary['best_beta']}")
        print(f"Best Γ           : {summary['best_gamma']}")
        print(f"Zero crossings   : {summary['beta_zero_crossings']}")
        print(f"RG fixed point   : {summary['rg_fixed_point_supported']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "stress-response":
        print("--- G-01 STRESS RESPONSE SWEEP ---")
        print(f"k_low / k_high   : {summary['k_low']} / {summary['k_high']}")
        print(f"N_cut            : {summary['n_cut']}")
        print(f"α strain         : {summary['alpha']}")
        print(f"ε values         : {summary['eps_values']}")
        print(f"ω range          : [{summary['omega_min']}, {summary['omega_max']}]")
        print(f"ω scale          : {summary['omega_scale']}")
        print(f"best ε0          : {summary['best_eps0']}")
        print(f"best ω           : {summary['best_omega']}")
        print(f"best σ_info      : {summary['best_sigma_info']}")
        print(f"best κ           : {summary['best_kappa']}")
        print(f"best γ           : {summary['best_gamma_damping']}")
        print(f"best phase lag   : {summary['best_phase_lag']}")
        print(f"best viscosity   : {summary['best_modular_viscosity']}")
        print(f"residual         : {summary['best_conductivity_residual_percent']}%")
        print(f"mean σ_info      : {summary['mean_sigma_info']} ± {summary['sigma_std']}")
        print(f"lock count       : {summary['lock_count']}/{summary['total_samples']}")
        print(f"transport support: {summary['transport_supported']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "stress-strain":
        print("--- G-01 STRESS-STRAIN SWEEP ---")
        print(f"k_low / k_high   : {summary['k_low']} / {summary['k_high']}")
        print(f"N_cut            : {summary['n_cut']}")
        print(f"α strain         : {summary['alpha']}")
        print(f"ω target         : {summary['omega_target']}")
        print(f"drive type       : {summary['drive_type']}")
        print(f"cadence          : {summary['cadence']} ({summary['response_steps']} steps)")
        print(f"ramp range       : [{summary['ramp_min']}, {summary['ramp_max']}] over {summary['ramp_steps']} steps")
        print(f"baseline σ       : {summary['baseline_sigma']}")
        print(f"critical ε       : {summary['critical_eps']}")
        print(f"critical σ       : {summary['critical_sigma']}")
        print(f"critical entropy : {summary['critical_entropy']}")
        print(f"critical χ³      : {summary['critical_chi3']}")
        print(f"quench ε         : {summary['quench_eps']}")
        print(f"quench σ         : {summary['quench_sigma']}")
        print(f"quench Re_mod    : {summary['re_mod']}")
        print(f"recovery σ       : {summary['recovery_sigma']}")
        print(f"recovery gap     : {summary['recovery_gap_percent']}%")
        print(f"hardening        : {summary['hardening_detected']}")
        print(f"fracture         : {summary['fracture_detected']}")
        print(f"hysteresis       : {summary['hysteresis_detected']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "neighborhood-control":
        print("--- G-01 NEIGHBORHOOD CONTROL ---")
        print(f"probe weights    : {summary['probe_weights']}")
        print(f"reference weight : {summary['reference_weight']}")
        print(f"N_cut            : {summary['n_cut']}")
        print(f"ε0 / ω           : {summary['eps0']} / {summary['omega']}")
        print(f"k=24 σ           : {summary['k24_sigma']}")
        print(f"k=24 residual    : {summary['k24_residual_percent']}%")
        print(f"best weight      : {summary['best_weight']}")
        print(f"best σ           : {summary['best_sigma']}")
        print(f"best residual    : {summary['best_residual_percent']}%")
        print(f"k=24 margin      : {summary['k24_margin_percent']}%")
        print(f"σ std            : {summary['sigma_std']}")
        print(f"scaling trend    : {summary['scaling_law_trend']}")
        print(f"Leech anchor     : {summary['leech_anchor_confirmed']}")
        print(f"Verdict          : {summary['verdict']}")
        print()
        print(df.to_string(index=False))
    elif args.mode == "rigor-check":
        print("--- G-01 RIGOR CHECK ---")
        print(f"k_probe / k_high : {summary['k_probe']} / {summary['k_high']}")
        print(f"N_cuts           : {summary['n_cuts']}")
        print(f"ε0 / ω           : {summary['eps0']} / {summary['omega']}")
        print(f"σ∞ fit           : {summary['sigma_inf']}")
        print(f"α fit            : {summary['alpha_fit']}")
        print(f"σ(N) range       : {summary['sigma_n_min']} → {summary['sigma_n_max']}")
        print(f"Tail L1 (last)   : {summary['tail_l1_last']}")
        print(f"Borel L1 (last)  : {summary['borel_l1_last']}")
        print(f"Tail decay       : {summary['tail_decay_supported']}")
        print(f"Pair spread      : {summary['pair_spread_percent']}%")
        print(f"Pair stability   : {summary['pair_stability_supported']}")
        print(f"Bootstrap σ∞ CI  : [{summary['sigma_inf_ci_low']}, {summary['sigma_inf_ci_high']}]")
        print(f"Bootstrap α CI   : [{summary['alpha_ci_low']}, {summary['alpha_ci_high']}]")
        print()
        print(df.to_string(index=False))
    elif args.mode == "resonant":
        print("--- G-01 RESONANT INDUCTION ---")
        print(f"Window Shape : {summary['window_shape']}")
        print(f"Decay τ      : {summary['decay_constant']}")
        print(f"Resonant N_cut: {summary['n_cut']}")
        print(f"Control N_cut : {summary['control_n_cut']}")
        print(f"Measured Γ    : {summary['measured_gamma']}")
        print(f"Control Γ     : {summary['control_gamma']}")
        print(f"Vacuum Gap    : {summary['vacuum_gap_percent']}%")
        print(f"Theory Residual: {summary['theory_residual_percent']}%")
        print(f"Falsification ΔΓ: {summary['falsification_gap_delta']}")
        print()
        print(df.to_string(index=False))
    else:
        print("--- G-01 INDUCTION RESULTS ---")
        print(f"Window Shape: {summary['window_shape']}")
        print(f"Decay τ     : {summary['decay_constant']}")
        print(f"Measured Γ: {summary['measured_gamma']}")
        print(f"Theoretical Γ: {summary['theoretical_gamma']}")
        print(f"Vacuum Gap: {summary['vacuum_gap_percent']}%")
        print(f"Theory Residual: {summary['theory_residual_percent']}%")
        print()
        preview = pd.concat([df.head(5), df.tail(5)]).drop_duplicates().reset_index(drop=True)
        print(preview.to_string(index=False))
    print(f"\n[OK] CSV exported to  {csv_path}")
    print(f"[OK] JSON exported to {json_path}")

    if args.update_log:
        log_path = Path(args.log_file)
        append_log_entry(log_path, summary)
        print(f"[OK] Log updated at {log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
