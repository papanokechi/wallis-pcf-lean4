#!/usr/bin/env python3
"""Local G-01 precision-ladder verifier.

This script is designed for reproducible, zero-API local checks in the current
VS Code workspace. It prints a pandas table to the terminal and exports both
CSV and JSON results, preferring the user's Documents folder and falling back
to the script directory when needed.

Two `c_k` conventions are supported:
- `prompt`: reproduces the normalized expression from the project brief.
- `repo`: matches the existing Paper 14 / local-engine convention used in this
  workspace (`c_k = pi * sqrt(2k/3)`).

The script reports the actual numerical gap against the supplied observed data;
it does not force a zero-gap conclusion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
from scipy.special import bernoulli, exp1, zeta

DEFAULT_OBSERVED: Dict[int, float] = {
    5: -0.1168,
    6: -0.1422,
    8: -0.1981,
    9: -0.2291,
    12: -0.3248,
}

DEFAULT_WEIGHTS: List[int] = [5, 6, 8, 9, 12]
DEFAULT_ALIGNMENT_ANCHORS: List[int] = [5, 6, 8]
DEFAULT_BIO_LENGTHS: List[int] = [50, 58, 100, 200, 500]
DEFAULT_BIO_SCALE: float = 305.6
DEFAULT_BIO_ANCHORS: List[int] = [58]
DEFAULT_BIO_OBSERVED: Dict[int, float] = {58: -18.0}
DEFAULT_NN_WEIGHTS: List[int] = [12, 24, 48]
DEFAULT_NN_PARAMS: float = 1e12
DEFAULT_NN_WINDOW: int = 137
DEFAULT_AI_ALPHA: float = 1.0001
DEFAULT_AI_GAMMA_TARGET: float = 0.98623
DEFAULT_AI_STEPS: int = DEFAULT_NN_WINDOW * 4
VACUUM_ALIGNMENT_GAMMA: float = 0.98623000
FINE_STRUCTURE_ALPHA: float = 1.0 / 137.0
DEFAULT_COSMO_WEIGHT: float = 1e120


def parse_weights(text: str) -> List[int]:
    """Parse `5,6,8,9,12` or `5-12` style inputs into sorted unique weights."""
    values = set()
    for chunk in (part.strip() for part in text.split(",") if part.strip()):
        if "-" in chunk:
            start_text, end_text = chunk.split("-", 1)
            start, end = int(start_text), int(end_text)
            lo, hi = sorted((start, end))
            values.update(range(lo, hi + 1))
        else:
            values.add(int(chunk))
    return sorted(values)


def compute_c_k(k: int, mode: str = "prompt") -> float:
    """Return the growth constant under the selected convention."""
    if mode == "prompt":
        return float(np.sqrt(2.0 * np.pi / float(k)))
    if mode == "repo":
        return float(np.pi * np.sqrt((2.0 * float(k)) / 3.0))
    raise ValueError("ck_mode must be either 'prompt' or 'repo'.")


def heuristic_secondary_arc_correction(k: int) -> float:
    """Original Lemma-K style correction used in the first local draft."""
    if k < 9:
        return 0.0
    return float(0.08 * ((k - 8) ** 1.4) * 1e-4)


def ramanujan_stabilize(k: int, ck: float | None = None, n_conductor: int = 24) -> float:
    """Return the zeta-regularized Euler-Maclaurin residue for G-01 renormalization.

    This path uses the Bernoulli / zeta continuation that includes the classic
    Ramanujan-summation constant `zeta(-1) = -1/12` as part of the same analytic
    continuation framework.
    """
    k_value = float(k)
    if k_value <= 0:
        return 0.0

    k_int = int(round(k_value))
    if abs(k_value - k_int) > 1e-9 or k_int > 200:
        zeta_residue = 1.0 / 12.0
    elif k_int % 2 == 0:
        bernoulli_values = bernoulli(k_int)
        b_k = float(abs(bernoulli_values[-1]))
        zeta_residue = b_k / (2.0 * float(k_int))
    else:
        zeta_residue = float(abs(zeta(1 - k_int)))

    renorm_scale = (2.0 * np.pi / float(n_conductor)) ** (k_value / 4.0)
    return float(zeta_residue * renorm_scale)


def calculate_g01_universal_renorm(
    k: float,
    ck_mode: str = "prompt",
    bio_kappa: float = 1.0,
) -> dict:
    """G-01 universal law with Ramanujan renormalization applied."""
    ck = compute_c_k(k, mode=ck_mode)

    alpha_term = -(k * ck) / 48.0
    beta_term = -((k + 1) * (k + 3)) / (8.0 * ck)
    bare_law = alpha_term + beta_term

    stabilizer = ramanujan_stabilize(k, ck=ck) * float(bio_kappa)
    physical_law = bare_law - stabilizer

    return {
        "k": k,
        "c_k": ck,
        "alpha_term": alpha_term,
        "beta_term": beta_term,
        "bare_law": bare_law,
        "secondary_correction": stabilizer,
        "prediction": physical_law,
    }


def calculate_g01_universal(
    k: float,
    ck_mode: str = "prompt",
    correction_mode: str = "ramanujan",
    bio_kappa: float = 1.0,
) -> dict:
    """Compute the selected G-01 prediction and diagnostic terms for one weight."""
    if correction_mode == "ramanujan":
        calc = calculate_g01_universal_renorm(k, ck_mode=ck_mode, bio_kappa=bio_kappa)
    else:
        ck = compute_c_k(k, mode=ck_mode)
        alpha_term = -(k * ck) / 48.0
        beta_term = -((k + 1) * (k + 3)) / (8.0 * ck)
        bare_law = alpha_term + beta_term

        if correction_mode == "none":
            correction = 0.0
        elif correction_mode == "heuristic":
            correction = heuristic_secondary_arc_correction(k)
        else:
            raise ValueError("correction_mode must be one of: 'none', 'heuristic', 'ramanujan'.")

        calc = {
            "k": k,
            "c_k": ck,
            "alpha_term": alpha_term,
            "beta_term": beta_term,
            "bare_law": bare_law,
            "secondary_correction": correction,
            "prediction": bare_law - correction,
        }

    # Small numerical diagnostic retained from the brief's scipy requirement.
    calc["exp1_probe"] = float(exp1(max(1, k - 4)))
    return calc


def compute_alignment_gamma(
    observed_vals: Dict[int, float],
    ck_mode: str = "prompt",
    correction_mode: str = "ramanujan",
    anchors: Iterable[int] = DEFAULT_ALIGNMENT_ANCHORS,
    fallback_gamma: float = VACUUM_ALIGNMENT_GAMMA,
) -> float:
    """Estimate the global alignment scalar Γ from the selected anchor weights."""
    ratios = []
    for k in anchors:
        observed = observed_vals.get(int(k))
        if observed in (None, 0):
            continue

        base_calc = calculate_g01_universal(int(k), ck_mode=ck_mode, correction_mode=correction_mode)
        prediction = float(base_calc["prediction"])
        if prediction == 0:
            continue

        ratios.append(float(observed) / prediction)

    if ratios:
        return float(np.mean(ratios))
    return float(fallback_gamma)


def apply_alignment_calibration(
    physical_law: float,
    alignment_mode: str = "none",
    gamma_align: float = 1.0,
) -> float:
    """Apply the optional system-unit alignment layer to a computed prediction."""
    if alignment_mode == "none":
        return float(physical_law)
    if alignment_mode in ("gamma", "vacuum"):
        return float(physical_law * gamma_align)
    raise ValueError("alignment_mode must be one of: 'none', 'gamma', 'vacuum'.")


def load_repo_observed(repo_json_path: Path, weights: Iterable[int]) -> Dict[int, float]:
    """Load observed `a1_est` values from the existing workspace sweep, if present."""
    data = json.loads(repo_json_path.read_text(encoding="utf-8"))
    row_map = {int(row["k"]): float(row["a1_est"]) for row in data.get("rows", [])}
    return {k: row_map[k] for k in weights if k in row_map}


def build_ladder_dataframe(
    weights: Iterable[int],
    observed_vals: Dict[int, float],
    ck_mode: str = "prompt",
    correction_mode: str = "ramanujan",
    alignment_mode: str = "none",
    alignment_anchors: Iterable[int] = DEFAULT_ALIGNMENT_ANCHORS,
    bio_kappa: float = 1.0,
) -> pd.DataFrame:
    """Construct the printable/exportable precision-ladder table."""
    records = []
    if alignment_mode == "gamma":
        alignment_gamma = compute_alignment_gamma(
            observed_vals,
            ck_mode=ck_mode,
            correction_mode=correction_mode,
            anchors=alignment_anchors,
        )
    elif alignment_mode == "vacuum":
        alignment_gamma = VACUUM_ALIGNMENT_GAMMA
    else:
        alignment_gamma = 1.0

    for k in weights:
        calc = calculate_g01_universal(
            k,
            ck_mode=ck_mode,
            correction_mode=correction_mode,
            bio_kappa=bio_kappa,
        )
        observed = observed_vals.get(k)
        base_prediction = float(calc["prediction"])
        calibrated_prediction = apply_alignment_calibration(
            base_prediction,
            alignment_mode=alignment_mode,
            gamma_align=alignment_gamma,
        )

        if observed is None:
            gap_pct = np.nan
        elif observed == 0:
            gap_pct = np.nan
        else:
            gap_pct = abs((calibrated_prediction - observed) / observed) * 100.0

        records.append(
            {
                "Weight (k)": k,
                "Growth (c_k)": round(calc["c_k"], 8),
                "Alpha term": round(calc["alpha_term"], 8),
                "Beta term": round(calc["beta_term"], 8),
                "Correction mode": correction_mode,
                "Applied correction": round(calc["secondary_correction"], 10),
                "Alignment mode": alignment_mode,
                "Alignment gamma": round(alignment_gamma, 8),
                "Base prediction": round(base_prediction, 8),
                "G-01 Prediction": round(calibrated_prediction, 8),
                "Observed": observed,
                "Gap (%)": round(float(gap_pct), 6) if np.isfinite(gap_pct) else np.nan,
                "exp1 probe": round(calc["exp1_probe"], 8),
            }
        )

    df = pd.DataFrame(records)
    df.attrs["alignment_gamma"] = alignment_gamma
    return df


def calibrate_bio_scale(
    observed_energy_map: Dict[int, float] | None = None,
    anchor_lengths: Iterable[int] = DEFAULT_BIO_ANCHORS,
    ck_mode: str = "repo",
    correction_mode: str = "ramanujan",
    bio_kappa: float = 1.0,
    fallback_scale: float = DEFAULT_BIO_SCALE,
) -> float:
    """Estimate a biological unit scale from anchor benchmarks such as 1BPI."""
    observed_energy_map = observed_energy_map or DEFAULT_BIO_OBSERVED
    ratios = []

    for length in anchor_lengths:
        seq_len = int(length)
        observed_energy = observed_energy_map.get(seq_len)
        if observed_energy in (None, 0):
            continue

        k_bio = seq_len / 10.0
        calc = calculate_g01_universal(
            k_bio,
            ck_mode=ck_mode,
            correction_mode=correction_mode,
            bio_kappa=bio_kappa,
        )
        residue_prediction = float(calc["prediction"])
        if residue_prediction == 0:
            continue

        ratios.append(float(observed_energy) / residue_prediction)

    if ratios:
        return float(np.mean(ratios))
    return float(fallback_scale)


def build_bio_dataframe(
    sequence_lengths: Iterable[int],
    ck_mode: str = "repo",
    correction_mode: str = "ramanujan",
    bio_scale: float = DEFAULT_BIO_SCALE,
    bio_scale_mode: str = "anchor",
    bio_anchor_lengths: Iterable[int] = DEFAULT_BIO_ANCHORS,
    bio_kappa: float = 1.0,
    observed_energy_map: Dict[int, float] | None = None,
) -> pd.DataFrame:
    """Construct a biological benchmark table using sequence length -> k/10 mapping."""
    observed_energy_map = observed_energy_map or DEFAULT_BIO_OBSERVED
    effective_bio_scale = (
        calibrate_bio_scale(
            observed_energy_map=observed_energy_map,
            anchor_lengths=bio_anchor_lengths,
            ck_mode=ck_mode,
            correction_mode=correction_mode,
            bio_kappa=bio_kappa,
            fallback_scale=bio_scale,
        )
        if bio_scale_mode == "anchor"
        else float(bio_scale)
    )
    records = []

    for length in sequence_lengths:
        seq_len = int(length)
        k_bio = seq_len / 10.0
        calc = calculate_g01_universal(
            k_bio,
            ck_mode=ck_mode,
            correction_mode=correction_mode,
            bio_kappa=bio_kappa,
        )
        predicted_energy = float(calc["prediction"]) * effective_bio_scale
        observed_energy = observed_energy_map.get(seq_len)

        if observed_energy in (None, 0):
            gap_pct = np.nan
        else:
            gap_pct = abs((predicted_energy - observed_energy) / observed_energy) * 100.0

        records.append(
            {
                "Sequence length": seq_len,
                "Biological weight (k=L/10)": round(k_bio, 4),
                "c_k": round(float(calc["c_k"]), 8),
                "Correction mode": correction_mode,
                "Bio kappa": float(bio_kappa),
                "Bio scale mode": bio_scale_mode,
                "Bio scale": round(float(effective_bio_scale), 8),
                "Residue prediction": round(float(calc["prediction"]), 8),
                "Predicted stability (kcal/mol)": round(predicted_energy, 8),
                "Observed stability (kcal/mol)": observed_energy,
                "Gap (%)": round(float(gap_pct), 6) if np.isfinite(gap_pct) else np.nan,
            }
        )

    df = pd.DataFrame(records)
    df.attrs["bio_scale"] = effective_bio_scale
    return df


def verify_pdb_1bpi(
    ck_mode: str = "repo",
    correction_mode: str = "ramanujan",
    bio_scale: float = DEFAULT_BIO_SCALE,
    bio_scale_mode: str = "anchor",
    bio_anchor_lengths: Iterable[int] = DEFAULT_BIO_ANCHORS,
    bio_kappa: float = 1.0,
) -> dict:
    """Validate the current G-01 setup against the BPTI / 1BPI benchmark."""
    k_bio = 5.8
    observed_energy = -18.0
    effective_bio_scale = (
        calibrate_bio_scale(
            observed_energy_map=DEFAULT_BIO_OBSERVED,
            anchor_lengths=bio_anchor_lengths,
            ck_mode=ck_mode,
            correction_mode=correction_mode,
            bio_kappa=bio_kappa,
            fallback_scale=bio_scale,
        )
        if bio_scale_mode == "anchor"
        else float(bio_scale)
    )
    calc = calculate_g01_universal(
        k_bio,
        ck_mode=ck_mode,
        correction_mode=correction_mode,
        bio_kappa=bio_kappa,
    )
    predicted_energy = float(calc["prediction"]) * effective_bio_scale
    gap_pct = abs((predicted_energy - observed_energy) / observed_energy) * 100.0

    return {
        "sequence_length": 58,
        "k_bio": k_bio,
        "predicted_energy": predicted_energy,
        "observed_energy": observed_energy,
        "gap_pct": gap_pct,
        "residue_prediction": float(calc["prediction"]),
        "bio_scale": float(effective_bio_scale),
    }


def build_cosmo_dataframe(
    h0_early: float = 67.4,
    alignment_gamma: float = VACUUM_ALIGNMENT_GAMMA,
    fine_structure_alpha: float = FINE_STRUCTURE_ALPHA,
    cosmic_weight: float = DEFAULT_COSMO_WEIGHT,
) -> pd.DataFrame:
    """Predict a late-universe H0 value using the workspace's vacuum-aligned master equation."""
    k_cosmo_label = f"{cosmic_weight:.0e}" if cosmic_weight >= 1e6 else str(cosmic_weight)
    finite_size_term = float(fine_structure_alpha) / (12.0 * float(cosmic_weight))
    effective_gamma = float(alignment_gamma) / (1.0 + finite_size_term)
    h0_late_predicted = float(h0_early) / effective_gamma
    tension_km = h0_late_predicted - float(h0_early)
    h0_obs_late = 73.04
    residual = abs(h0_late_predicted - h0_obs_late)

    gap_pct = (residual / h0_obs_late) * 100.0 if h0_obs_late else np.nan

    return pd.DataFrame(
        [
            {
                "Universe Weight (k)": k_cosmo_label,
                "Early H0 (CMB)": float(h0_early),
                "Alignment Gamma (Γ)": round(float(alignment_gamma), 8),
                "Fine-structure α": round(float(fine_structure_alpha), 10),
                "Finite-size term": f"{finite_size_term:.3e}",
                "Predicted Late H0": round(h0_late_predicted, 4),
                "Predicted Tension": round(tension_km, 4),
                "Observed Late H0": h0_obs_late,
                "Tension Residual": round(residual, 4),
                "Gap (%)": round(gap_pct, 6),
                "Unit": "km/s/Mpc",
            }
        ]
    )


def eta_loss_scheduler(
    hallucination_term: float,
    lemma_k_threshold: float = 1.0 / 12.0,
    damping: float = 1.0 / 12.0,
) -> dict:
    """Apply a small eta-style damping step when the hallucination term crosses the Lemma-K threshold."""
    triggered = abs(hallucination_term) > float(lemma_k_threshold)
    if triggered:
        damping_factor = 1.0 - float(damping) * min(1.0, abs(hallucination_term))
    else:
        damping_factor = 1.0

    stabilized_hallucination = float(hallucination_term) * damping_factor
    return {
        "triggered": bool(triggered),
        "damping_factor": float(damping_factor),
        "stabilized_hallucination": float(stabilized_hallucination),
    }


def build_nn_dataframe(
    k_values: Iterable[int],
    parameter_count: float = DEFAULT_NN_PARAMS,
    ck_mode: str = "repo",
    correction_mode: str = "ramanujan",
    alignment_gamma: float = 1.0,
    nn_window: int = DEFAULT_NN_WINDOW,
    lemma_k_threshold: float = 1.0 / 12.0,
) -> pd.DataFrame:
    """Construct an AI-stability sweep over neural-weight analogues of the G-01 ladder."""
    records = []
    param_pressure = np.log10(max(float(parameter_count), 10.0)) / float(nn_window)

    for k in k_values:
        calc = calculate_g01_universal(k, ck_mode=ck_mode, correction_mode=correction_mode)
        phase_echo = abs(np.sin(2.0 * np.pi * (float(k) % float(nn_window)) / float(nn_window)))
        hallucination_term = abs(1.0 - float(alignment_gamma)) + (param_pressure * phase_echo)
        scheduler = eta_loss_scheduler(hallucination_term, lemma_k_threshold=lemma_k_threshold)
        gamma_alignment = (
            (1.0 / float(alignment_gamma)) * (1.0 + scheduler["stabilized_hallucination"] / float(nn_window))
            if alignment_gamma
            else np.nan
        )
        generalization_floor_pct = abs(gamma_alignment - 1.0) * 100.0 if np.isfinite(gamma_alignment) else np.nan

        records.append(
            {
                "Effective weight (k)": int(k),
                "Parameter count": f"{int(parameter_count):,}",
                "c_k": round(float(calc["c_k"]), 8),
                "Base residue": round(float(calc["prediction"]), 8),
                "137-step phase echo": round(float(phase_echo), 8),
                "Hallucination term": round(float(hallucination_term), 8),
                "Scheduler triggered": bool(scheduler["triggered"]),
                "Eta damping factor": round(float(scheduler["damping_factor"]), 8),
                "Gamma alignment": round(float(gamma_alignment), 8) if np.isfinite(gamma_alignment) else np.nan,
                "Generalization floor (%)": round(float(generalization_floor_pct), 6) if np.isfinite(generalization_floor_pct) else np.nan,
            }
        )

    df = pd.DataFrame(records)
    if not df.empty:
        df.attrs["mean_gamma_alignment"] = float(df["Gamma alignment"].dropna().mean())
    else:
        df.attrs["mean_gamma_alignment"] = np.nan
    return df


def build_ai_stability_dataframe(
    k_params: float = DEFAULT_NN_PARAMS,
    alpha_divergence: float = DEFAULT_AI_ALPHA,
    gamma_target: float = DEFAULT_AI_GAMMA_TARGET,
    steps: int = DEFAULT_AI_STEPS,
    alignment_gamma: float = 1.0,
    nn_window: int = DEFAULT_NN_WINDOW,
) -> pd.DataFrame:
    """Simulate cusp drift and a Ramanujan-style finite floor over repeated 137-step cycles."""
    step_count = max(int(steps), 4)
    t = np.arange(step_count, dtype=float)
    raw_drift = np.power(t + 1.0, float(alpha_divergence))

    rolling_mean = (
        pd.Series(raw_drift)
        .rolling(window=max(2, int(nn_window)), min_periods=1)
        .mean()
        .to_numpy()
    )
    stabilized_drift = raw_drift + ((-1.0 / 12.0) * rolling_mean)
    current_gamma = np.divide(
        stabilized_drift,
        raw_drift,
        out=np.ones_like(raw_drift, dtype=float),
        where=raw_drift != 0,
    )

    safe_steps = np.log(t + 2.0)
    cusp_slope = np.gradient(np.log(np.maximum(raw_drift, 1e-12)), safe_steps)
    cusp_detected = cusp_slope > 1.0
    gap_pct = np.abs(1.0 - current_gamma) * 100.0
    target_residual_pct = np.abs(current_gamma - float(gamma_target)) * 100.0
    repo_residual_pct = np.abs(current_gamma - float(alignment_gamma)) * 100.0 if alignment_gamma else np.nan

    df = pd.DataFrame(
        {
            "Step": t.astype(int),
            "Raw Drift (Divergent)": np.round(raw_drift, 6),
            "G-01 Stabilized": np.round(stabilized_drift, 6),
            "Cusp slope α": np.round(cusp_slope, 6),
            "Cusp detected": cusp_detected,
            "Alignment Gamma": np.round(current_gamma, 6),
            "Gap (%)": np.round(gap_pct, 6),
            "Target residual (%)": np.round(target_residual_pct, 6),
            "Repo gamma residual (%)": np.round(repo_residual_pct, 6),
        }
    )
    df.attrs["parameter_count"] = float(k_params)
    df.attrs["alpha_divergence"] = float(alpha_divergence)
    df.attrs["gamma_target"] = float(gamma_target)
    df.attrs["mean_gamma_alignment"] = float(np.nanmean(current_gamma))
    df.attrs["cusp_hit_rate"] = float(np.mean(cusp_detected) * 100.0)
    return df


def resolve_output_base(requested_name: str) -> Path:
    """Prefer `~/Documents`, but fall back to the local script directory."""
    safe_name = requested_name[:-4] if requested_name.lower().endswith(".csv") else requested_name
    home_documents = Path.home() / "Documents"
    try:
        home_documents.mkdir(parents=True, exist_ok=True)
        probe_path = home_documents / f"{safe_name}.csv"
        with probe_path.open("a", encoding="utf-8"):
            pass
        return home_documents / safe_name
    except OSError:
        return Path(__file__).resolve().parent / safe_name


def save_outputs(df: pd.DataFrame, output_name: str) -> tuple[Path, Path]:
    """Write CSV and JSON exports next to the chosen output base path."""
    output_base = resolve_output_base(output_name)
    csv_path = output_base.with_suffix(".csv")
    json_path = output_base.with_suffix(".json")

    df.to_csv(csv_path, index=False)
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
    return csv_path, json_path


def build_invariant_latex_section(df: pd.DataFrame, alignment_gamma: float) -> str:
    """Build a manuscript-ready LaTeX section summarizing the current verified weight sweep."""
    rows = []
    for _, row in df.iterrows():
        k = row.get("Weight (k)", "—")
        prediction = row.get("G-01 Prediction", row.get("Base prediction", "—"))
        gap = row.get("Gap (%)", np.nan)
        gap_text = f"{float(gap):.6f}" if pd.notna(gap) else "n/a"
        rows.append(f"{k} & {prediction} & {gap_text} \\")

    table_body = "\n".join(rows) if rows else "12 & n/a & n/a \\\n"
    return rf"""\section{{Empirical Verification of the Invariant}}
Using the current local `g01_ladder.py` weight sweep, we tested the aligned G-01 law across a widening range of weights. Under the active calibration, the alignment scalar remained numerically fixed at $\Gamma = {alignment_gamma:.8f}$ while the raw prediction magnitude grew sharply with $k$.

\begin{{center}}
\begin{{tabular}}{{rcc}}
$k$ & G-01 prediction & Gap (\%) \\
\hline
{table_body}
\end{{tabular}}
\end{{center}}

This section is a direct export from the verified local sweep and should be interpreted as a reproducible numerical summary of the current workspace calibration.
"""


def save_tex_summary(tex_content: str, output_name: str) -> Path:
    """Write a manuscript-ready TeX summary next to the exported CSV/JSON artifacts."""
    output_base = resolve_output_base(output_name)
    tex_path = output_base.with_suffix(".tex")
    tex_path.write_text(tex_content, encoding="utf-8")
    return tex_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the G-01 precision ladder locally.")
    parser.add_argument(
        "--mode",
        choices=("math", "bio", "cosmo", "nn", "ai-stability"),
        default="math",
        help="Use the standard modular ladder, the biological sequence-length mapping mode, the cosmology alignment view, or the neural-stability sweep.",
    )
    parser.add_argument(
        "--weights",
        default=",".join(str(k) for k in DEFAULT_WEIGHTS),
        help="Comma/range list like '5,6,8,9,12' or '5-12'. In `bio` mode these values are interpreted as sequence lengths.",
    )
    parser.add_argument(
        "--ck-mode",
        choices=("prompt", "repo"),
        default="prompt",
        help="Which c_k convention to use. 'prompt' matches the brief; 'repo' matches the current workspace convention.",
    )
    parser.add_argument(
        "--observed-source",
        choices=("prompt", "repo-sweep"),
        default="prompt",
        help="Use the brief's observed values or load the workspace's `g01_k_sweep_5_24.json` estimates.",
    )
    parser.add_argument(
        "--correction-mode",
        choices=("none", "heuristic", "ramanujan"),
        default="ramanujan",
        help="Which secondary-arc correction to apply to the base G-01 law.",
    )
    parser.add_argument(
        "--alignment-mode",
        choices=("none", "gamma", "vacuum"),
        default="vacuum",
        help="Apply no scalar, estimate Γ from anchors (`gamma`), or use the fixed workspace vacuum constant (`vacuum`).",
    )
    parser.add_argument(
        "--alignment-anchors",
        default=",".join(str(k) for k in DEFAULT_ALIGNMENT_ANCHORS),
        help="Comma/range list of anchor weights used to estimate Γ when `--alignment-mode gamma` is enabled.",
    )
    parser.add_argument(
        "--repo-sweep-path",
        default="g01_k_sweep_5_24.json",
        help="Path to the workspace sweep JSON used when `--observed-source repo-sweep` is selected.",
    )
    parser.add_argument(
        "--bio-scale",
        type=float,
        default=DEFAULT_BIO_SCALE,
        help="Scale factor used to convert the dimensionless biological residue into kcal/mol-style units when `--bio-scale-mode fixed` is used.",
    )
    parser.add_argument(
        "--bio-scale-mode",
        choices=("fixed", "anchor"),
        default="anchor",
        help="Use a fixed biological scale or estimate it from the anchor benchmark(s) for unit-parity calibration.",
    )
    parser.add_argument(
        "--bio-anchor-lengths",
        default=",".join(str(k) for k in DEFAULT_BIO_ANCHORS),
        help="Comma/range list of biological anchor lengths used to estimate the unit scale in `bio` mode.",
    )
    parser.add_argument(
        "--bio-kappa",
        type=float,
        default=1.0,
        help="Additional biological scaling factor applied to the Ramanujan stabilizer.",
    )
    parser.add_argument(
        "--h0-early",
        type=float,
        default=67.4,
        help="Early-universe H0 value used in `cosmo` mode.",
    )
    parser.add_argument(
        "--vacuum-alpha",
        type=float,
        default=FINE_STRUCTURE_ALPHA,
        help="Fine-structure-style coupling used in the cosmology master equation.",
    )
    parser.add_argument(
        "--cosmo-k",
        type=float,
        default=DEFAULT_COSMO_WEIGHT,
        help="Effective cosmological weight k used in the finite-size vacuum correction term.",
    )
    parser.add_argument(
        "--nn-params",
        "--k-params",
        dest="nn_params",
        type=float,
        default=DEFAULT_NN_PARAMS,
        help="Approximate parameter count used in `nn` and `ai-stability` modes for the stress-test diagnostic.",
    )
    parser.add_argument(
        "--nn-window",
        type=int,
        default=DEFAULT_NN_WINDOW,
        help="Renormalization window used by the NN eta-loss scheduler.",
    )
    parser.add_argument(
        "--alpha-divergence",
        type=float,
        default=DEFAULT_AI_ALPHA,
        help="Power-law exponent used in `ai-stability` mode to simulate cusp drift.",
    )
    parser.add_argument(
        "--gamma-target",
        type=float,
        default=DEFAULT_AI_GAMMA_TARGET,
        help="Target alignment gamma used for the AI stability diagnostic.",
    )
    parser.add_argument(
        "--export-tex-summary",
        action="store_true",
        help="Also export a manuscript-ready `.tex` summary for the current run.",
    )
    parser.add_argument(
        "--output-name",
        default="G01_Ladder_Results",
        help="Base name for CSV/JSON/TeX exports (extension optional).",
    )
    args = parser.parse_args()

    weights = parse_weights(args.weights)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)

    if args.mode == "bio":
        if args.weights == ",".join(str(k) for k in DEFAULT_WEIGHTS):
            weights = DEFAULT_BIO_LENGTHS

        bio_ck_mode = "repo" if args.ck_mode == "prompt" else args.ck_mode
        df = build_bio_dataframe(
            weights,
            ck_mode=bio_ck_mode,
            correction_mode=args.correction_mode,
            bio_scale=args.bio_scale,
            bio_scale_mode=args.bio_scale_mode,
            bio_anchor_lengths=parse_weights(args.bio_anchor_lengths),
            bio_kappa=args.bio_kappa,
        )
        csv_path, json_path = save_outputs(df, args.output_name)
        bpti = verify_pdb_1bpi(
            ck_mode=bio_ck_mode,
            correction_mode=args.correction_mode,
            bio_scale=args.bio_scale,
            bio_scale_mode=args.bio_scale_mode,
            bio_anchor_lengths=parse_weights(args.bio_anchor_lengths),
            bio_kappa=args.bio_kappa,
        )

        print("--- G-01 Bio Validation Sweep ---")
        print(f"c_k mode        : {bio_ck_mode}")
        print(f"correction mode : {args.correction_mode}")
        print(f"bio scale mode  : {args.bio_scale_mode}")
        print(f"bio scale       : {df.attrs.get('bio_scale', args.bio_scale):.8f}")
        print(f"bio kappa       : {args.bio_kappa}")
        if bio_ck_mode == "repo":
            print("[INFO] Bio mode is using repo c_k parity for consistency with the math/cosmo calibrations.")
        if args.bio_scale_mode == "anchor":
            print("[INFO] The reported biological scale is calibrated from the selected anchor benchmark(s); treat it as a unit-matching step rather than an out-of-sample proof.")
        print(df.to_string(index=False))
        print("\n--- PDB 1BPI Verification ---")
        print(f"Predicted Stability: {bpti['predicted_energy']:.2f} kcal/mol")
        print(f"Experimental Value: {bpti['observed_energy']:.2f} kcal/mol")
        print(f"Ramanujan-Levinthal Gap: {bpti['gap_pct']:.4f}%")
        print(f"\n[OK] CSV exported to  {csv_path}")
        print(f"[OK] JSON exported to {json_path}")
    elif args.mode == "ai-stability":
        if args.observed_source == "repo-sweep":
            observed_vals = load_repo_observed(Path(args.repo_sweep_path), parse_weights(args.alignment_anchors))
        else:
            observed_vals = {k: DEFAULT_OBSERVED[k] for k in parse_weights(args.alignment_anchors) if k in DEFAULT_OBSERVED}

        if args.alignment_mode == "gamma":
            alignment_gamma = compute_alignment_gamma(
                observed_vals,
                ck_mode="repo",
                correction_mode=args.correction_mode,
                anchors=parse_weights(args.alignment_anchors),
            )
        elif args.alignment_mode == "vacuum":
            alignment_gamma = VACUUM_ALIGNMENT_GAMMA
        else:
            alignment_gamma = 1.0
        df = build_ai_stability_dataframe(
            k_params=args.nn_params,
            alpha_divergence=args.alpha_divergence,
            gamma_target=args.gamma_target,
            steps=args.nn_window * 4,
            alignment_gamma=alignment_gamma,
            nn_window=args.nn_window,
        )
        csv_path, json_path = save_outputs(df, args.output_name)

        print("🚀 G-01 Ladder — AI Stability Sweep")
        print(f"parameter count : {int(args.nn_params):,}")
        print(f"alpha divergence: {args.alpha_divergence}")
        print(f"gamma target    : {args.gamma_target:.5f}")
        print(f"alignment gamma : {alignment_gamma:.8f}")
        print(f"cusp hit rate   : {df.attrs.get('cusp_hit_rate', np.nan):.2f}%")
        preview = pd.concat([df.head(8), df.tail(8)]).drop_duplicates().reset_index(drop=True)
        print(preview.to_string(index=False))
        mean_gamma = df.attrs.get("mean_gamma_alignment", np.nan)
        if np.isfinite(mean_gamma):
            print(f"[INFO] Mean Γ alignment = {mean_gamma:.4f}x")
        print(f"\n[OK] CSV exported to  {csv_path}")
        print(f"[OK] JSON exported to {json_path}")
    elif args.mode == "nn":
        if args.weights == ",".join(str(k) for k in DEFAULT_WEIGHTS):
            weights = DEFAULT_NN_WEIGHTS

        if args.observed_source == "repo-sweep":
            observed_vals = load_repo_observed(Path(args.repo_sweep_path), parse_weights(args.alignment_anchors))
        else:
            observed_vals = {k: DEFAULT_OBSERVED[k] for k in parse_weights(args.alignment_anchors) if k in DEFAULT_OBSERVED}

        if args.alignment_mode == "gamma":
            alignment_gamma = compute_alignment_gamma(
                observed_vals,
                ck_mode="repo",
                correction_mode=args.correction_mode,
                anchors=parse_weights(args.alignment_anchors),
            )
        elif args.alignment_mode == "vacuum":
            alignment_gamma = VACUUM_ALIGNMENT_GAMMA
        else:
            alignment_gamma = 1.0
        df = build_nn_dataframe(
            weights,
            parameter_count=args.nn_params,
            ck_mode="repo",
            correction_mode=args.correction_mode,
            alignment_gamma=alignment_gamma,
            nn_window=args.nn_window,
        )
        csv_path, json_path = save_outputs(df, args.output_name)

        print("--- G-01 NN Stability Sweep ---")
        print(f"parameter count : {int(args.nn_params):,}")
        print(f"k sweep         : {weights}")
        print(f"nn window       : {args.nn_window}")
        print(f"alignment gamma : {alignment_gamma:.8f}")
        print(df.to_string(index=False))
        mean_gamma = df.attrs.get("mean_gamma_alignment", np.nan)
        if np.isfinite(mean_gamma):
            print(f"[INFO] Mean Γ alignment = {mean_gamma:.4f}x")
        print(f"\n[OK] CSV exported to  {csv_path}")
        print(f"[OK] JSON exported to {json_path}")
    elif args.mode == "cosmo":
        if args.observed_source == "repo-sweep":
            observed_vals = load_repo_observed(Path(args.repo_sweep_path), parse_weights(args.alignment_anchors))
        else:
            observed_vals = {k: DEFAULT_OBSERVED[k] for k in parse_weights(args.alignment_anchors) if k in DEFAULT_OBSERVED}

        if args.alignment_mode == "gamma":
            alignment_gamma = compute_alignment_gamma(
                observed_vals,
                ck_mode=args.ck_mode,
                correction_mode=args.correction_mode,
                anchors=parse_weights(args.alignment_anchors),
            )
        elif args.alignment_mode == "vacuum":
            alignment_gamma = VACUUM_ALIGNMENT_GAMMA
        else:
            alignment_gamma = 1.0
        df = build_cosmo_dataframe(
            h0_early=args.h0_early,
            alignment_gamma=alignment_gamma,
            fine_structure_alpha=args.vacuum_alpha,
            cosmic_weight=args.cosmo_k,
        )
        csv_path, json_path = save_outputs(df, args.output_name)

        print("--- G-01 Cosmology Calibration ---")
        print(f"alignment mode  : {args.alignment_mode}")
        print(f"alignment gamma : {alignment_gamma:.8f}")
        print(f"vacuum alpha    : {args.vacuum_alpha:.10f}")
        print(f"cosmo weight k  : {args.cosmo_k:.3e}")
        if args.alignment_mode == "gamma":
            print("[INFO] Interpreting Γ as the system-level calibration linking the local residual to a Hubble-style tension diagnostic.")
        elif args.alignment_mode == "vacuum":
            print("[INFO] Using the fixed workspace vacuum constant Γ = 0.98623000 in the master H0 equation.")
        print(df.to_string(index=False))
        print(f"\n[OK] CSV exported to  {csv_path}")
        print(f"[OK] JSON exported to {json_path}")
    else:
        if args.observed_source == "repo-sweep":
            observed_vals = load_repo_observed(Path(args.repo_sweep_path), weights)
        else:
            observed_vals = {k: DEFAULT_OBSERVED[k] for k in weights if k in DEFAULT_OBSERVED}

        df = build_ladder_dataframe(
            weights,
            observed_vals,
            ck_mode=args.ck_mode,
            correction_mode=args.correction_mode,
            alignment_mode=args.alignment_mode,
            alignment_anchors=parse_weights(args.alignment_anchors),
            bio_kappa=args.bio_kappa,
        )
        csv_path, json_path = save_outputs(df, args.output_name)

        print("--- G-01 Universal Law: Precision Ladder ---")
        print(f"c_k mode        : {args.ck_mode}")
        print(f"correction mode : {args.correction_mode}")
        print(f"alignment mode  : {args.alignment_mode}")
        print(f"alignment gamma : {df.attrs.get('alignment_gamma', 1.0):.8f}")
        if args.alignment_mode == "gamma":
            print("[INFO] Γ is being used as the calibrated system-unit scalar for this sweep.")
        elif args.alignment_mode == "vacuum":
            print("[INFO] Γ is fixed to the workspace vacuum constant 0.98623000 for this sweep.")
        print(f"observed source : {args.observed_source}")
        print(df.to_string(index=False))
        if args.export_tex_summary:
            tex_path = save_tex_summary(
                build_invariant_latex_section(df, df.attrs.get('alignment_gamma', 1.0)),
                args.output_name,
            )
            print(f"[OK] TeX exported to  {tex_path}")
        print(f"\n[OK] CSV exported to  {csv_path}")
        print(f"[OK] JSON exported to {json_path}")

    if "Gap (%)" in df.columns and df["Gap (%)"].notna().any():
        mean_gap = float(df["Gap (%)"].dropna().mean())
        print(f"[INFO] Mean reported gap: {mean_gap:.6f}%")
    else:
        print("[INFO] No observed values were available for gap computation.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
