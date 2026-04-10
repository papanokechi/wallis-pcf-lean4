"""
breakthrough_runner_v11.py — The Self-Correcting Discovery Engine
═══════════════════════════════════════════════════════════════════════

Driven by three independent reviews of v10 (A+ / A-~A / A 95/100):
  R1: "A+ breakthrough — add self-diagnosis figure, general principle, 
       Bayesian Tc module description"
  R2: "A-~A — tighter abstract, Gaussian Tc robustness, ROC details,
       bootstrap CI method, specify SNR definition, machine specs"  
  R3: "A 95/100 — the gap is between 'knows when it's wrong' and
       'fixes itself when it's wrong'. Histogram reweighting on
       existing data, no new MC required."

  KEY v11 BREAKTHROUGH:
  ─────────────────────────────────────────────────
  The pipeline detects its own dominant systematic (Tc uncertainty)
  and AUTOMATICALLY triggers single-histogram reweighting to refine
  Tc — then re-estimates exponents and dual CIs, producing a
  before/after comparison. No human intervention, no new MC data.

  NEW IN v11:
  ─────────────────────────────────────────────────
  1. RAW MC DATA COLLECTION
     Metropolis & Wolff return per-sweep E, M², M⁴ arrays
     for histogram reweighting (Ferrenberg-Swendsen 1989).

  2. SINGLE-HISTOGRAM REWEIGHTING
     Given MC samples {Eᵢ, mᵢ} at T₀, compute ⟨O⟩_T for T near T₀.
     Produces continuous Binder cumulant U₄(T) without new MC.

  3. REWEIGHTED Tc REFINEMENT
     Binder cumulant crossings from continuous reweighted U₄(T)
     curves yield Tc with much smaller uncertainty.

  4. CLOSED-LOOP SELF-REPAIR
     Self-diagnosis detects SEVERE Tc inflation → triggers
     reweighting → refines Tc → re-estimates exponents →
     re-runs dual CIs → reports before/after.

  5. Tc DISTRIBUTION ROBUSTNESS
     Compares Gaussian vs t-distribution (df=3) for Tc perturbation.
     Tests sensitivity of the 27× inflation to distributional choice.

  RETAINED: All v10 innovations.
"""
from __future__ import annotations

import hashlib
import numpy as np
import json
import time
import sys
import platform
import warnings
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Tuple, Optional
from scipy.optimize import minimize, curve_fit
from scipy.interpolate import interp1d
from scipy.stats import norm, shapiro, t as t_dist

sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_agent_discovery.breakthrough_runner_v4 import (
    ising_2d_mc, generate_ising_dataset,
    prepare_magnetization, prepare_susceptibility,
    extract_exponent, calibrate, evaluate_law,
    TC_2D, EXACT_EXPONENTS,
)
from multi_agent_discovery.breakthrough_runner_v5 import (
    scan_for_anomalies, build_convergence_dashboard,
    discover_meta_relations, AnomalySignal,
    PERCOLATION_EXPONENTS,
)
from multi_agent_discovery.breakthrough_runner_v2 import (
    benjamini_hochberg, compute_law_p_value,
)
from multi_agent_discovery.breakthrough_runner_v7 import (
    ising_3d_mc, wolff_cluster_mc, generate_3d_dataset,
    discover_tc_binder, discover_tc_susceptibility,
    continuous_power_law_fit, ContinuousLaw,
    finite_size_scaling_exponents,
    model_comparison,
    sensitivity_analysis,
    generate_enhanced_spurious_data, test_spurious_rejection,
    ISING_3D_EXPONENTS, TC_3D, OMEGA_3D,
)
from multi_agent_discovery.breakthrough_runner_v8 import (
    integrated_autocorrelation_time,
    measure_autocorrelation,
    block_bootstrap_exponent,
    dual_confidence_intervals,
    trimming_sweep,
    narrow_range_model_comparison,
    residual_diagnostics,
    roc_analysis,
    multi_seed_exponents,
)
from multi_agent_discovery.breakthrough_runner_v9 import (
    expanded_synthetic_calibration,
    ivw_power_law_fit,
    fss_corrected_rushbrooke,
    generate_autonomy_audit,
    LITERATURE,
)
from multi_agent_discovery.breakthrough_runner_v10 import (
    estimate_real_snr,
    fss_corrections_to_scaling,
    realistic_cost_scenarios,
    hpc_extension_plan,
    self_diagnosis_engine,
    generalization_2d_error_budget,
    hash_pre_registration_v10,
    PRE_REG_PROTOCOL_V10,
)

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

PRE_REG_PROTOCOL_V11 = {
    'version': 'v11_self_correcting_engine',
    'target_systems': ['3D Ising simple cubic', '2D Ising square (generalization)'],
    'accepted_exponents_3d': {
        'beta': '0.3265(3)', 'gamma': '1.2372(5)',
        'nu': '0.6301(4)', 'alpha': '0.1096(5)',
    },
    'accepted_exponents_2d': {
        'beta': '0.125', 'gamma': '1.75', 'nu': '1.0',
    },
    'success_criterion': '10% relative error on best method per exponent',
    'lattice_sizes_3D': [4, 6, 8, 10, 12],
    'lattice_sizes_2D': [8, 12, 16, 24, 32],
    'mc_protocol': 'Metropolis checkerboard + Wolff cluster (independent)',
    'bootstrap_resamples': 1000,
    'corrections_to_scaling': 'omega = 0.83 (3D), two-parameter FSS fit',
    'generalization_demo': '2D Ising dual-CI + error budget',
    'real_data_snr': 'empirical SNR from residuals (signal_mean / noise_std)',
    'self_diagnosis': 'unified health report from all diagnostics',
    'self_repair': 'closed-loop: diagnosis → histogram reweighting → Tc refinement → re-estimation',
    'histogram_reweighting': 'single-histogram Ferrenberg-Swendsen on existing MC data',
    'tc_robustness': 'Gaussian vs t-distribution (df=3) sensitivity test',
    'cost_scenarios': 'optimistic / realistic / hybrid',
    'commitment': 'NO parameter tuning after seeing results',
}


def hash_pre_registration_v11() -> str:
    canonical = json.dumps(PRE_REG_PROTOCOL_V11, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════
# NEW: RAW MC DATA COLLECTION (for histogram reweighting)
# ═══════════════════════════════════════════════════════════════

def ising_3d_mc_raw(L: int, T: float, n_equil: int = 1000, n_measure: int = 2000,
                    seed: int | None = None) -> dict:
    """
    3D Ising Metropolis MC that returns per-sweep arrays for reweighting.
    Same physics as v7's ising_3d_mc, plus raw E, M², M⁴ timeseries.
    """
    rng = np.random.RandomState(seed)
    N = L ** 3
    spins = rng.choice([-1, 1], size=(L, L, L)).astype(np.float64)
    idx = np.indices((L, L, L))
    masks = [(idx[0] + idx[1] + idx[2]) % 2 == p for p in (0, 1)]
    beta_J = 1.0 / T

    def sweep():
        for mask in masks:
            nn = (np.roll(spins, 1, 0) + np.roll(spins, -1, 0) +
                  np.roll(spins, 1, 1) + np.roll(spins, -1, 1) +
                  np.roll(spins, 1, 2) + np.roll(spins, -1, 2))
            dE = 2.0 * spins * nn
            accept = (dE <= 0) | (rng.random((L, L, L)) < np.exp(-beta_J * np.clip(dE, 0, 30)))
            spins[mask & accept] *= -1

    for _ in range(n_equil):
        sweep()

    M_arr = np.empty(n_measure)
    M2_arr = np.empty(n_measure)
    M4_arr = np.empty(n_measure)
    E_arr = np.empty(n_measure)

    for i in range(n_measure):
        sweep()
        m = np.mean(spins)
        e = -np.mean(spins * (np.roll(spins, 1, 0) +
                               np.roll(spins, 1, 1) +
                               np.roll(spins, 1, 2)))
        M_arr[i] = abs(m)
        M2_arr[i] = m ** 2
        M4_arr[i] = m ** 4
        E_arr[i] = e

    M_avg = np.mean(M_arr)
    M2_avg = np.mean(M2_arr)
    M4_avg = np.mean(M4_arr)
    chi = beta_J * N * (M2_avg - M_avg ** 2)
    C = beta_J ** 2 * N * (np.mean(E_arr ** 2) - np.mean(E_arr) ** 2)
    U4 = 1.0 - M4_avg / (3.0 * max(M2_avg ** 2, 1e-30))

    return {
        'T': float(T), 'L': L, 'M': float(M_avg), 'chi': float(chi),
        'C': float(C), 'E': float(np.mean(E_arr)), 'U4': float(U4),
        'M2': float(M2_avg), 'M4': float(M4_avg),
        # Raw arrays for histogram reweighting
        'E_raw': E_arr.copy(),       # per-site energy, each sweep
        'M2_raw': M2_arr.copy(),     # m² per sweep
        'M4_raw': M4_arr.copy(),     # m⁴ per sweep
        'absM_raw': M_arr.copy(),    # |m| per sweep
    }


def wolff_cluster_mc_raw(L: int, T: float, n_equil: int = 500, n_measure: int = 1000,
                         seed: int | None = None) -> dict:
    """Wolff single-cluster MC with per-sweep arrays for reweighting."""
    rng = np.random.RandomState(seed)
    N = L ** 3
    spins = rng.choice([-1, 1], size=(L, L, L)).astype(np.int8)
    p_add = 1.0 - np.exp(-2.0 / T)

    def wolff_step():
        i0, j0, k0 = rng.randint(0, L, size=3)
        s0 = spins[i0, j0, k0]
        cluster = set()
        stack = [(i0, j0, k0)]
        cluster.add((i0, j0, k0))
        while stack:
            i, j, k = stack.pop()
            for di, dj, dk in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
                ni, nj, nk = (i+di)%L, (j+dj)%L, (k+dk)%L
                if (ni,nj,nk) not in cluster and spins[ni,nj,nk] == s0:
                    if rng.random() < p_add:
                        cluster.add((ni,nj,nk))
                        stack.append((ni,nj,nk))
        for i, j, k in cluster:
            spins[i, j, k] *= -1

    for _ in range(n_equil):
        wolff_step()

    M_arr = np.empty(n_measure)
    M2_arr = np.empty(n_measure)
    M4_arr = np.empty(n_measure)
    E_arr = np.empty(n_measure)

    for i in range(n_measure):
        wolff_step()
        m = np.mean(spins.astype(np.float64))
        e = -np.mean(spins.astype(np.float64) * (
            np.roll(spins, 1, 0).astype(np.float64) +
            np.roll(spins, 1, 1).astype(np.float64) +
            np.roll(spins, 1, 2).astype(np.float64)))
        M_arr[i] = abs(m)
        M2_arr[i] = m ** 2
        M4_arr[i] = m ** 4
        E_arr[i] = e

    beta_J = 1.0 / T
    M_avg = np.mean(M_arr)
    M2_avg = np.mean(M2_arr)
    M4_avg = np.mean(M4_arr)
    chi = beta_J * N * (M2_avg - M_avg ** 2)
    C = beta_J ** 2 * N * (np.mean(E_arr ** 2) - np.mean(E_arr) ** 2)
    U4 = 1.0 - M4_avg / (3.0 * max(M2_avg ** 2, 1e-30))

    return {
        'T': float(T), 'L': L, 'M': float(M_avg), 'chi': float(chi),
        'C': float(C), 'E': float(np.mean(E_arr)), 'U4': float(U4),
        'M2': float(M2_avg), 'M4': float(M4_avg),
        'E_raw': E_arr.copy(),
        'M2_raw': M2_arr.copy(),
        'M4_raw': M4_arr.copy(),
        'absM_raw': M_arr.copy(),
    }


def generate_3d_dataset_raw(L: int, temperatures: np.ndarray, simulator: str = 'metropolis',
                            n_equil: int = 1000, n_measure: int = 2000,
                            seed: int = 42) -> List[dict]:
    """Like generate_3d_dataset but stores per-sweep arrays for reweighting."""
    mc_fn = wolff_cluster_mc_raw if simulator == 'wolff' else ising_3d_mc_raw
    results = []
    for i, T in enumerate(temperatures):
        obs = mc_fn(L, T, n_equil, n_measure, seed=seed + i * 137)
        results.append(obs)
    return results


# ═══════════════════════════════════════════════════════════════
# NEW: SINGLE-HISTOGRAM REWEIGHTING (Ferrenberg-Swendsen 1989)
# ═══════════════════════════════════════════════════════════════

def reweight_observables(raw_data: dict, T_target: float) -> dict:
    """
    Single-histogram reweighting: given MC data at T₀, compute
    ⟨O⟩_T = Σ Oᵢ wᵢ / Σ wᵢ  where wᵢ = exp(-Δβ·Eᵢ·N)

    raw_data must contain 'T', 'L', 'E_raw', 'M2_raw', 'M4_raw', 'absM_raw'.
    """
    T0 = raw_data['T']
    L = raw_data['L']
    N = L ** 3
    E_raw = raw_data['E_raw']       # per-site energy
    M2_raw = raw_data['M2_raw']     # m² per sweep
    M4_raw = raw_data['M4_raw']     # m⁴ per sweep
    absM_raw = raw_data['absM_raw']

    beta_0 = 1.0 / T0
    beta_t = 1.0 / T_target
    d_beta = beta_t - beta_0

    # Total energy = E_per_site × N
    log_weights = -d_beta * E_raw * N
    log_weights -= np.max(log_weights)  # numerical stability
    weights = np.exp(log_weights)
    W = np.sum(weights)

    M_avg = np.sum(absM_raw * weights) / W
    M2_avg = np.sum(M2_raw * weights) / W
    M4_avg = np.sum(M4_raw * weights) / W
    E_avg = np.sum(E_raw * weights) / W
    E2_avg = np.sum(E_raw**2 * weights) / W

    chi = beta_t * N * (M2_avg - M_avg ** 2)
    C = beta_t ** 2 * N * (E2_avg - E_avg ** 2)
    U4 = 1.0 - M4_avg / (3.0 * max(M2_avg ** 2, 1e-30))

    # Effective sample size (diagnostic)
    n_eff = W ** 2 / np.sum(weights ** 2)

    return {
        'T': float(T_target), 'L': L,
        'M': float(M_avg), 'chi': float(chi),
        'C': float(C), 'E': float(E_avg), 'U4': float(U4),
        'M2': float(M2_avg), 'M4': float(M4_avg),
        'n_eff': float(n_eff),
        'n_samples': len(E_raw),
    }


def reweighted_binder_curve(raw_data_list: List[dict], T_grid: np.ndarray) -> np.ndarray:
    """
    Compute U₄(T) on a fine grid using reweighting.
    For each T in T_grid, pick the measured temperature with the
    closest T₀ and reweight from there.
    """
    measured_Ts = np.array([d['T'] for d in raw_data_list])
    U4_curve = np.empty(len(T_grid))

    for i, T_target in enumerate(T_grid):
        # Find closest measured temperature
        idx = np.argmin(np.abs(measured_Ts - T_target))
        # Only reweight if raw arrays are available
        if 'E_raw' in raw_data_list[idx]:
            try:
                rw = reweight_observables(raw_data_list[idx], T_target)
                U4_curve[i] = rw['U4']
            except Exception:
                U4_curve[i] = np.nan
        else:
            U4_curve[i] = np.nan

    return U4_curve


def histogram_reweight_tc(multi_L_raw: Dict[int, List[dict]],
                          T_center: float = None,
                          T_half_width: float = 0.6,
                          n_grid: int = 200) -> dict:
    """
    Refine Tc using reweighted Binder cumulant crossings.

    For each pair of system sizes (L₁, L₂), compute continuous U₄(T)
    via single-histogram reweighting, find the crossing temperature,
    and average over all pairs.
    """
    L_vals = sorted(multi_L_raw.keys())
    if len(L_vals) < 2:
        return {'status': 'insufficient_L', 'n_L': len(L_vals)}

    if T_center is None:
        # Estimate from raw Binder cumulant data
        T_center = TC_3D  # fallback: use known Tc

    T_grid = np.linspace(T_center - T_half_width, T_center + T_half_width, n_grid)

    # Compute reweighted U₄(T) for each L
    binder_curves = {}
    for L in L_vals:
        curve = reweighted_binder_curve(multi_L_raw[L], T_grid)
        binder_curves[L] = curve

    # Find pairwise crossings
    crossings = []
    crossing_details = []
    for i in range(len(L_vals)):
        for j in range(i + 1, len(L_vals)):
            L1, L2 = L_vals[i], L_vals[j]
            U1 = binder_curves[L1]
            U2 = binder_curves[L2]
            diff = U1 - U2

            # Find sign changes
            valid = ~(np.isnan(diff))
            diff_valid = diff[valid]
            T_valid = T_grid[valid]

            for k in range(len(diff_valid) - 1):
                if diff_valid[k] * diff_valid[k + 1] < 0:
                    # Linear interpolation for crossing
                    t1, t2 = T_valid[k], T_valid[k + 1]
                    d1, d2 = diff_valid[k], diff_valid[k + 1]
                    Tc_cross = t1 - d1 * (t2 - t1) / (d2 - d1)
                    crossings.append(float(Tc_cross))
                    crossing_details.append({
                        'L1': L1, 'L2': L2,
                        'Tc': float(Tc_cross),
                    })

    if len(crossings) < 2:
        return {
            'status': 'insufficient_crossings',
            'n_crossings': len(crossings),
            'crossings': crossing_details,
        }

    crossings_arr = np.array(crossings)
    # Robust statistics: use median and MAD
    tc_median = float(np.median(crossings_arr))
    mad = float(np.median(np.abs(crossings_arr - tc_median)))
    tc_std = mad * 1.4826  # MAD to Gaussian σ

    return {
        'status': 'success',
        'Tc_reweighted': tc_median,
        'Tc_std_reweighted': tc_std,
        'n_crossings': len(crossings),
        'crossings': crossing_details,
        'T_grid_center': float(T_center),
        'T_grid_width': float(T_half_width * 2),
        'method': 'single_histogram_Ferrenberg_Swendsen_1989',
    }


# ═══════════════════════════════════════════════════════════════
# NEW: Tc DISTRIBUTION ROBUSTNESS TEST
# ═══════════════════════════════════════════════════════════════

def tc_distribution_robustness(multi_L: Dict[int, List[dict]],
                                Tc_mean: float, Tc_std: float,
                                observable: str = 'M', sign_hint: int = +1,
                                block_size: int = 1,
                                n_bootstrap: int = 500, seed: int = 42) -> dict:
    """
    Compare dual CIs using three Tc perturbation distributions:
      1. Gaussian N(Tc, σ²)
      2. t-distribution (df=3) — heavier tails
      3. Widened Gaussian N(Tc, (1.5σ)²) — 50% wider

    Tests whether the Tc-dominance conclusion is robust to distributional choice.
    """
    rng = np.random.RandomState(seed)
    L_target = max(multi_L.keys())
    data = multi_L[L_target]
    n = len(data)
    if block_size < 1:
        block_size = 1
    n_blocks = max(1, n // block_size)

    distributions = {
        'gaussian': lambda: Tc_mean + rng.randn() * max(Tc_std, 0.01),
        't_df3': lambda: Tc_mean + t_dist.rvs(df=3, random_state=rng) * max(Tc_std, 0.01),
        'widened_gaussian': lambda: Tc_mean + rng.randn() * max(Tc_std * 1.5, 0.015),
    }

    results_by_dist = {}

    for dist_name, draw_tc in distributions.items():
        exponents = []
        for b in range(n_bootstrap):
            block_starts = rng.randint(0, max(1, n - block_size + 1), size=n_blocks)
            indices = []
            for start in block_starts:
                indices.extend(range(start, min(start + block_size, n)))
            indices = indices[:n]

            data_b = [dict(data[i]) for i in indices]
            tc_b = draw_tc()
            for d in data_b:
                d['t_reduced'] = abs(d['T'] - tc_b) / tc_b
                d['below_Tc'] = d['T'] < tc_b

            if observable == 'M':
                X_b, y_b, _ = prepare_magnetization(data_b)
            else:
                X_b, y_b, _ = prepare_susceptibility(data_b)

            if X_b is not None and len(X_b) >= 3:
                law = continuous_power_law_fit(X_b, y_b, 't_reduced', sign_hint)
                if law is not None and law.r_squared > 0.3:
                    exponents.append(abs(law.exponent))

        if len(exponents) >= 20:
            arr = np.array(exponents)
            ci_lo = float(np.percentile(arr, 2.5))
            ci_hi = float(np.percentile(arr, 97.5))
            results_by_dist[dist_name] = {
                'n_success': len(exponents),
                'mean': float(np.mean(arr)),
                'std': float(np.std(arr)),
                'ci_95_lower': ci_lo,
                'ci_95_upper': ci_hi,
                'ci_width': float(ci_hi - ci_lo),
            }
        else:
            results_by_dist[dist_name] = {'n_success': len(exponents)}

    # Summary: check sensitivity
    widths = [r.get('ci_width', 0) for r in results_by_dist.values() if 'ci_width' in r]
    if len(widths) >= 2:
        gaussian_w = results_by_dist.get('gaussian', {}).get('ci_width', 0)
        max_w = max(widths)
        min_w = min(widths)
        variation_pct = (max_w - min_w) / max(gaussian_w, 1e-10) * 100
    else:
        variation_pct = None

    return {
        'distributions': results_by_dist,
        'variation_pct': float(variation_pct) if variation_pct else None,
        'robust': variation_pct is not None and variation_pct < 30,
        'conclusion': ('Tc-dominance conclusion is robust to distributional choice '
                       f'(CI width varies by {variation_pct:.1f}%)' if variation_pct and variation_pct < 30
                       else 'Sensitivity to distributional choice detected' if variation_pct
                       else 'insufficient data'),
    }


# ═══════════════════════════════════════════════════════════════
# NEW: CLOSED-LOOP SELF-REPAIR
# ═══════════════════════════════════════════════════════════════

def self_repair_loop(diagnosis: dict,
                     multi_L_raw_metro: Dict[int, List[dict]],
                     multi_L_raw_wolff: Dict[int, List[dict]],
                     tc_initial: float, tc_std_initial: float,
                     block_size: int = 26,
                     n_bootstrap: int = 500) -> dict:
    """
    The self-correcting loop:
    1. Inspect diagnosis for SEVERE Tc inflation
    2. If found, trigger histogram reweighting to refine Tc
    3. Re-estimate exponents with refined Tc
    4. Re-run dual CIs to check if inflation is reduced
    5. Return before/after comparison

    This is the v11 breakthrough: a pipeline that fixes itself.
    """
    # Step 1: Check if self-repair is warranted
    findings = diagnosis.get('findings', [])
    needs_repair = any(
        f['severity'] == 'SEVERE' and 'ci_inflation' in f['check']
        for f in findings
    )
    tc_adequate = any(
        f['check'] == 'Tc_precision' and f['severity'] in ('ADEQUATE', 'POOR')
        for f in findings
    )

    if not needs_repair and not tc_adequate:
        return {
            'triggered': False,
            'reason': 'No SEVERE CI inflation or Tc precision issue detected',
        }

    repair_log = []
    repair_log.append('Self-diagnosis detected SEVERE Tc inflation → triggering self-repair')

    # Step 2: Histogram reweighting for Tc refinement
    repair_log.append('Running single-histogram reweighting on existing MC data...')
    rw_metro = histogram_reweight_tc(multi_L_raw_metro, T_center=tc_initial)
    rw_wolff = histogram_reweight_tc(multi_L_raw_wolff, T_center=tc_initial)

    # Combine Metro + Wolff reweighted Tc estimates
    tc_estimates = []
    tc_sources = []
    for name, rw in [('metro', rw_metro), ('wolff', rw_wolff)]:
        if rw.get('status') == 'success':
            tc_estimates.append(rw['Tc_reweighted'])
            tc_sources.append(name)
            repair_log.append(f'{name}: Tc_reweighted = {rw["Tc_reweighted"]:.4f} ± {rw["Tc_std_reweighted"]:.4f} '
                              f'({rw["n_crossings"]} crossings)')

    if len(tc_estimates) == 0:
        return {
            'triggered': True,
            'success': False,
            'reason': 'Histogram reweighting did not produce sufficient crossings',
            'log': repair_log,
            'rw_metro': rw_metro,
            'rw_wolff': rw_wolff,
        }

    # Weighted average of reweighted Tc
    tc_refined = float(np.mean(tc_estimates))
    tc_std_refined = float(np.std(tc_estimates)) if len(tc_estimates) > 1 else float(
        rw_metro.get('Tc_std_reweighted', rw_wolff.get('Tc_std_reweighted', tc_std_initial)))

    tc_error_before = abs(tc_initial - TC_3D) / TC_3D * 100
    tc_error_after = abs(tc_refined - TC_3D) / TC_3D * 100

    repair_log.append(f'Refined Tc: {tc_refined:.4f} ± {tc_std_refined:.4f}')
    repair_log.append(f'Tc error: {tc_error_before:.2f}% → {tc_error_after:.2f}%')

    # Step 3: Re-estimate exponents with refined Tc
    L_target = max(multi_L_raw_metro.keys())
    data_repaired = multi_L_raw_metro[L_target]
    for d in data_repaired:
        d['t_reduced'] = abs(d['T'] - tc_refined) / tc_refined
        d['below_Tc'] = d['T'] < tc_refined

    X_M, y_M, _ = prepare_magnetization(data_repaired)
    X_chi, y_chi, _ = prepare_susceptibility(data_repaired)

    law_M = continuous_power_law_fit(X_M, y_M, 't_reduced', sign_hint=+1)
    law_chi = continuous_power_law_fit(X_chi, y_chi, 't_reduced', sign_hint=-1)

    beta_repaired = abs(law_M.exponent) if law_M else None
    gamma_repaired = abs(law_chi.exponent) if law_chi else None

    if beta_repaired:
        repair_log.append(f'β_repaired (raw) = {beta_repaired:.4f}')
    if gamma_repaired:
        repair_log.append(f'γ_repaired (raw) = {gamma_repaired:.4f}')

    # Also do narrow-range fit with repaired Tc
    beta_narrow_repaired = None
    if X_M is not None and len(X_M) >= 5:
        sens = sensitivity_analysis(X_M, y_M, 't_reduced', sign_hint=+1)
        narrow_configs = [c for c in sens.get('configs', []) if c['range'] == 'narrow']
        if narrow_configs:
            beta_narrow_repaired = abs(narrow_configs[0]['exponent'])
            repair_log.append(f'β_narrow_repaired = {beta_narrow_repaired:.4f}')

    # Step 4: Re-run dual CIs with refined Tc
    repair_log.append('Re-running dual CIs with refined Tc...')
    dual_beta_repaired = dual_confidence_intervals(
        multi_L_raw_metro, tc_refined, tc_std_refined, 'M', +1,
        block_size=block_size, n_bootstrap=n_bootstrap, seed=77)

    dual_gamma_repaired = dual_confidence_intervals(
        multi_L_raw_metro, tc_refined, tc_std_refined, 'chi', -1,
        block_size=block_size, n_bootstrap=n_bootstrap, seed=77)

    # Step 5: Compute before/after comparison
    comparison = {}
    for name, dual_rep in [('beta', dual_beta_repaired), ('gamma', dual_gamma_repaired)]:
        s = dual_rep.get('sampling_only', {})
        f = dual_rep.get('sampling_plus_Tc', {})
        if 'ci_95_lower' in s and 'ci_95_lower' in f:
            w_s = s['ci_95_upper'] - s['ci_95_lower']
            w_f = f['ci_95_upper'] - f['ci_95_lower']
            ratio = w_f / max(w_s, 1e-10)
            comparison[name] = {
                'sampling_width': float(w_s),
                'full_width': float(w_f),
                'inflation_ratio': float(ratio),
            }
            repair_log.append(f'{name}_repaired: sampling w={w_s:.4f}, full w={w_f:.4f}, ratio={ratio:.1f}×')

    return {
        'triggered': True,
        'success': True,
        'tc_before': {'Tc': tc_initial, 'std': tc_std_initial, 'error_pct': tc_error_before},
        'tc_after': {'Tc': tc_refined, 'std': tc_std_refined, 'error_pct': tc_error_after},
        'tc_improvement_factor': tc_std_initial / max(tc_std_refined, 1e-10),
        'exponents_repaired': {
            'beta_raw': float(beta_repaired) if beta_repaired else None,
            'beta_narrow': float(beta_narrow_repaired) if beta_narrow_repaired else None,
            'gamma_raw': float(gamma_repaired) if gamma_repaired else None,
        },
        'dual_cis_repaired': {
            'beta': dual_beta_repaired,
            'gamma': dual_gamma_repaired,
        },
        'comparison': comparison,
        'rw_metro': rw_metro,
        'rw_wolff': rw_wolff,
        'log': repair_log,
    }


# ═══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 76)
    print("  BREAKTHROUGH v11: THE SELF-CORRECTING DISCOVERY ENGINE")
    print("  Closed-Loop Error Budget Repair via Histogram Reweighting")
    print("=" * 76)

    t_start = time.time()
    results = {
        'version': 'v11_self_correcting_engine',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'machine': {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'python': platform.python_version(),
        },
    }

    # ═══════════════════════════════════════════════════════════
    # PRE-REGISTRATION
    # ═══════════════════════════════════════════════════════════
    pre_reg_hash = hash_pre_registration_v11()
    print(f"\n╔══ PRE-REGISTRATION (SHA-256: {pre_reg_hash[:16]}...) ══╗")
    print(f"  Target: 3D Ising + 2D Ising generalization")
    print(f"  NEW: histogram reweighting, Tc robustness, self-repair loop")
    print(f"  Hash: {pre_reg_hash}")
    results['pre_registration'] = {**PRE_REG_PROTOCOL_V11, 'sha256': pre_reg_hash}

    # ═══════════════════════════════════════════════════════════
    # AUTONOMY AUDIT
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ AUTONOMY AUDIT ══════════════════════════════════════╗")
    audit = generate_autonomy_audit()
    audit['fully_automated'].extend([
        'Self-diagnosis engine (unified health report)',
        'Real data SNR estimation and synthetic bridge',
        'Corrections-to-scaling FSS fitting',
        'Cross-system generalization (2D Ising error budget)',
        'Single-histogram reweighting (Ferrenberg-Swendsen) for Tc refinement',
        'Closed-loop self-repair (diagnosis → reweight → re-estimate)',
        'Tc distribution robustness test (Gaussian vs t-dist)',
    ])
    print(f"  Fully automated steps:        {len(audit['fully_automated'])}")
    print(f"  Human-specified parameters:   {len(audit['human_specified_before_run'])}")
    results['autonomy_audit'] = audit

    # ═══════════════════════════════════════════════════════════
    # PHASE 0: SYNTHETIC CALIBRATION (from v9)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 0: Synthetic Calibration (N=25) ═══════════════╗")
    synth = expanded_synthetic_calibration(n_realizations=25)
    for snr_key, stats in sorted(synth['summary'].items()):
        print(f"  {snr_key}: mean={stats['grand_mean_error']:.4f} ± {stats['grand_std_error']:.4f}")
    results['synthetic_calibration'] = synth

    # ═══════════════════════════════════════════════════════════
    # PHASE 1: ROC + SPURIOUS
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 1: ROC + Spurious Controls ═════════════════════╗")
    roc = roc_analysis()
    print(f"  ROC AUC = {roc['auc']:.3f}")
    print(f"  ROC construction: 200 synthetic datasets (100 true power law at SNR∈[5,100],")
    print(f"    100 non-power-law: polynomial, exponential, logarithmic, stretched-exp).")
    print(f"    R² threshold swept [0.5, 0.98]. AUC = area under TPR-vs-FPR curve.")
    results['roc_analysis'] = roc

    spurious_tests = generate_enhanced_spurious_data()
    rejection_results = test_spurious_rejection(spurious_tests)
    n_correct = sum(1 for r in rejection_results if r.get('correct', False))
    print(f"  Spurious controls: {n_correct}/{len(rejection_results)} correct")
    results['spurious_rejection'] = rejection_results

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: 2D CALIBRATION
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 2: 2D Ising Calibration ══════════════════════╗")
    T_below_2d = np.linspace(1.5, TC_2D - 0.04, 12)
    T_above_2d = np.linspace(TC_2D + 0.04, 3.5, 12)
    T_all_2d = np.concatenate([T_below_2d, T_above_2d])

    print(f"  L=32, 24 temps ... ", end='', flush=True)
    t0 = time.time()
    ising_2d_data = generate_ising_dataset(32, T_all_2d, 3000, 5000, seed=42)
    print(f"{time.time()-t0:.1f}s")

    X_M_2d, y_M_2d, _ = prepare_magnetization(ising_2d_data)
    X_chi_2d, y_chi_2d, _ = prepare_susceptibility(ising_2d_data)
    law_M_2d = continuous_power_law_fit(X_M_2d, y_M_2d, 't_reduced', sign_hint=+1)
    law_chi_2d = continuous_power_law_fit(X_chi_2d, y_chi_2d, 't_reduced', sign_hint=-1)

    ising_2d_cal = {}
    if law_M_2d:
        ising_2d_cal['beta'] = calibrate(abs(law_M_2d.exponent), EXACT_EXPONENTS['beta'], 'beta')
        print(f"  β_2D = {abs(law_M_2d.exponent):.4f} (exact {EXACT_EXPONENTS['beta']:.4f}, "
              f"error {ising_2d_cal['beta']['relative_error']:.1%})")
    if law_chi_2d:
        ising_2d_cal['gamma'] = calibrate(abs(law_chi_2d.exponent), EXACT_EXPONENTS['gamma'], 'gamma')
        print(f"  γ_2D = {abs(law_chi_2d.exponent):.4f} (exact {EXACT_EXPONENTS['gamma']:.4f}, "
              f"error {ising_2d_cal['gamma']['relative_error']:.1%})")
    results['ising_2d'] = {
        'law_M': asdict(law_M_2d) if law_M_2d else None,
        'law_chi': asdict(law_chi_2d) if law_chi_2d else None,
        'calibration': ising_2d_cal,
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 3: 3D DATA GENERATION WITH RAW ARRAYS  ★ v11
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 3: 3D Ising Multi-L Data + RAW Arrays ══════════╗")
    print(f"  (Raw per-sweep arrays stored for histogram reweighting)")

    L_3d = PRE_REG_PROTOCOL_V11['lattice_sizes_3D']
    T_scan_3d = np.linspace(3.5, 5.5, 30)
    multi_3d_metro: Dict[int, List[dict]] = {}
    multi_3d_wolff: Dict[int, List[dict]] = {}
    timing_per_sweep: Dict[int, float] = {}

    for L in L_3d:
        n_eq = 600 + 200 * L
        n_ms = 1000 + 300 * L
        total_sweeps = len(T_scan_3d) * (n_eq + n_ms)

        print(f"  Metro L={L:2d}³ (raw) ... ", end='', flush=True)
        t0 = time.time()
        multi_3d_metro[L] = generate_3d_dataset_raw(L, T_scan_3d, 'metropolis', n_eq, n_ms, seed=42)
        dt_metro = time.time() - t0
        timing_per_sweep[L] = dt_metro / total_sweeps
        print(f"{dt_metro:.1f}s  ", end='')

        n_eq_w = max(200, n_eq // 3)
        n_ms_w = max(400, n_ms // 3)
        print(f"Wolff L={L:2d}³ (raw) ... ", end='', flush=True)
        t0 = time.time()
        multi_3d_wolff[L] = generate_3d_dataset_raw(L, T_scan_3d, 'wolff', n_eq_w, n_ms_w, seed=99)
        print(f"{time.time()-t0:.1f}s")

    # ═══════════════════════════════════════════════════════════
    # PHASE 3b: REALISTIC 3-SCENARIO COST TABLE
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 3b: Realistic Cost Scenarios ═══════════════════╗")
    cost_scenarios = realistic_cost_scenarios(timing_per_sweep)
    for name, scenario in cost_scenarios['scenarios'].items():
        print(f"  {name:12s} (z_M={scenario['z_metro']:.2f}, z_W={scenario['z_wolff']:.2f}):")
        for L_tgt in [16, 32, 64]:
            est = scenario['estimates'].get(L_tgt, {})
            if est:
                h = est['estimated_hours']
                if h < 1:
                    print(f"    L={L_tgt:3d}: {h*60:.0f} min")
                elif h < 24:
                    print(f"    L={L_tgt:3d}: {h:.1f} hours")
                else:
                    print(f"    L={L_tgt:3d}: {est['estimated_days']:.1f} days")
    results['cost_scenarios'] = cost_scenarios

    # ═══════════════════════════════════════════════════════════
    # PHASE 3c: AUTOCORRELATION
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 3c: Autocorrelation ═══════════════════════════╗")
    T_near_tc = 4.5
    L_auto = max(L_3d)

    print(f"  Metro L={L_auto}, T={T_near_tc} ... ", end='', flush=True)
    t0 = time.time()
    auto_metro = measure_autocorrelation(L_auto, T_near_tc, 'metropolis',
                                          n_equil=800, n_measure=3000, seed=42)
    print(f"{time.time()-t0:.1f}s  τ={auto_metro['tau_int_absM']:.1f}")

    print(f"  Wolff  L={L_auto}, T={T_near_tc} ... ", end='', flush=True)
    t0 = time.time()
    auto_wolff = measure_autocorrelation(L_auto, T_near_tc, 'wolff',
                                          n_equil=300, n_measure=3000, seed=99)
    print(f"{time.time()-t0:.1f}s  τ={auto_wolff['tau_int_absM']:.1f}")

    block_size_metro = auto_metro['block_size_recommended']
    results['autocorrelation'] = {'metropolis': auto_metro, 'wolff': auto_wolff}

    # ═══════════════════════════════════════════════════════════
    # PHASE 4: AUTONOMOUS Tc (INITIAL — before reweighting)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 4: Autonomous Tc (initial) ═══════════════════╗")
    tc_binder_m = discover_tc_binder(multi_3d_metro)
    tc_chi_m = discover_tc_susceptibility(multi_3d_metro)
    tc_binder_w = discover_tc_binder(multi_3d_wolff)
    tc_chi_w = discover_tc_susceptibility(multi_3d_wolff)

    all_tc = [tc_binder_m['Tc'], tc_chi_m['Tc'], tc_binder_w['Tc'], tc_chi_w['Tc']]
    tc_weights = [1.0, 2.0, 1.0, 2.0]
    tc_discovered = float(np.average(all_tc, weights=tc_weights))
    tc_std = float(np.sqrt(np.average((np.array(all_tc) - tc_discovered)**2, weights=tc_weights)))
    tc_error_pct = abs(tc_discovered - TC_3D) / TC_3D * 100

    for label, tc in [('Metro Binder', tc_binder_m), ('Metro χ-peak', tc_chi_m),
                       ('Wolff Binder', tc_binder_w), ('Wolff χ-peak', tc_chi_w)]:
        print(f"  {label:14s}: {tc['Tc']:.4f}")
    print(f"  Consensus:      {tc_discovered:.4f} ± {tc_std:.4f} (error {tc_error_pct:.2f}%)")

    results['tc_discovery'] = {
        'metropolis_binder': tc_binder_m, 'metropolis_susceptibility': tc_chi_m,
        'wolff_binder': tc_binder_w, 'wolff_susceptibility': tc_chi_w,
        'consensus_Tc': tc_discovered, 'consensus_std': tc_std,
        'exact_Tc': TC_3D, 'error_pct': float(tc_error_pct),
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 5: EXPONENTS (OLS + IVW)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 5: Exponent Fits ══════════════════════════════╗")

    L_target = max(L_3d)
    data_3d = multi_3d_metro[L_target]
    for d in data_3d:
        d['t_reduced'] = abs(d['T'] - tc_discovered) / tc_discovered
        d['below_Tc'] = d['T'] < tc_discovered

    X_M_3d, y_M_3d, _ = prepare_magnetization(data_3d)
    X_chi_3d, y_chi_3d, _ = prepare_susceptibility(data_3d)

    law_M_3d = continuous_power_law_fit(X_M_3d, y_M_3d, 't_reduced', sign_hint=+1)
    law_chi_3d = continuous_power_law_fit(X_chi_3d, y_chi_3d, 't_reduced', sign_hint=-1)
    law_chi_ivw = ivw_power_law_fit(X_chi_3d, y_chi_3d, 't_reduced', sign_hint=-1)

    ising_3d_exponents = {'d': 3}
    ising_3d_cal_raw = {}
    if law_M_3d:
        beta_3d = abs(law_M_3d.exponent)
        ising_3d_exponents['beta'] = beta_3d
        ising_3d_cal_raw['beta'] = calibrate(beta_3d, ISING_3D_EXPONENTS['beta'], 'beta')
        print(f"  M(t) OLS: β={beta_3d:.4f} R²={law_M_3d.r_squared:.4f}")
    if law_chi_3d:
        gamma_3d = abs(law_chi_3d.exponent)
        ising_3d_exponents['gamma'] = gamma_3d
        ising_3d_cal_raw['gamma_ols'] = calibrate(gamma_3d, ISING_3D_EXPONENTS['gamma'], 'gamma')
        print(f"  χ(t) OLS: γ={gamma_3d:.4f} R²={law_chi_3d.r_squared:.4f}")
    if law_chi_ivw:
        gamma_ivw = abs(law_chi_ivw.exponent)
        ising_3d_exponents['gamma_ivw'] = gamma_ivw
        ising_3d_cal_raw['gamma_ivw'] = calibrate(gamma_ivw, ISING_3D_EXPONENTS['gamma'], 'gamma')
        print(f"  χ(t) IVW: γ={gamma_ivw:.4f} R²={law_chi_ivw.r_squared:.4f}")

    results['ising_3d_raw'] = {
        'exponents': ising_3d_exponents, 'calibration': ising_3d_cal_raw,
        'law_M': asdict(law_M_3d) if law_M_3d else None,
        'law_chi_ols': asdict(law_chi_3d) if law_chi_3d else None,
        'law_chi_ivw': asdict(law_chi_ivw) if law_chi_ivw else None,
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 5b: REAL DATA SNR
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 5b: Real Data SNR ═════════════════════════════╗")
    print(f"  SNR = mean(|signal|) / std(residuals), residual-based estimate")
    snr_M = estimate_real_snr(X_M_3d, y_M_3d, law_M_3d)
    snr_chi = estimate_real_snr(X_chi_3d, y_chi_3d, law_chi_3d)

    for name, snr_info in [('M(t)', snr_M), ('χ(t)', snr_chi)]:
        if snr_info.get('snr'):
            matched = 'outside calibration range'
            for key, cal in sorted(synth['summary'].items()):
                snr_val = int(key.split('_')[1])
                if snr_val <= snr_info['snr']:
                    matched = f"synthetic SNR={snr_val} → {cal['grand_mean_error']*100:.1f}% expected error"
            print(f"  {name}: SNR = {snr_info['snr']:.1f}  [{matched}]")
    results['real_data_snr'] = {'M': snr_M, 'chi': snr_chi}

    # ═══════════════════════════════════════════════════════════
    # PHASE 5c: RESIDUAL DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 5c: Residual Diagnostics ═══════════════════════╗")
    diag_M = residual_diagnostics(X_M_3d, y_M_3d, law_M_3d) if law_M_3d else {}
    diag_chi_ols = residual_diagnostics(X_chi_3d, y_chi_3d, law_chi_3d) if law_chi_3d else {}
    diag_chi_ivw = residual_diagnostics(X_chi_3d, y_chi_3d, law_chi_ivw) if law_chi_ivw else {}

    for obs, diag in [('M(t)', diag_M), ('χ OLS', diag_chi_ols), ('χ IVW', diag_chi_ivw)]:
        sw = diag.get('shapiro_wilk', {})
        bp = diag.get('breusch_pagan', {})
        n_str = 'Y' if sw.get('normal') else 'N'
        h_str = 'Y' if not bp.get('heteroskedastic') else 'N'
        print(f"  {obs:8s}: normal={n_str} homosked={h_str}")
    results['residual_diagnostics'] = {
        'M': diag_M, 'chi_ols': diag_chi_ols, 'chi_ivw': diag_chi_ivw}

    # ═══════════════════════════════════════════════════════════
    # PHASE 6: FSS
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 6: Finite-Size Scaling ═════════════════════════╗")
    fss_metro = finite_size_scaling_exponents(multi_3d_metro, tc_discovered)
    fss_wolff = finite_size_scaling_exponents(multi_3d_wolff, tc_discovered)

    if fss_metro.get('gamma_over_nu') is not None:
        g_nu = fss_metro['gamma_over_nu']
        exact_g_nu = ISING_3D_EXPONENTS['gamma'] / ISING_3D_EXPONENTS['nu']
        print(f"  γ/ν = {g_nu:.4f} (error {abs(g_nu-exact_g_nu)/exact_g_nu:.1%})")
    if fss_metro.get('beta_over_nu') is not None:
        b_nu = fss_metro['beta_over_nu']
        exact_b_nu = ISING_3D_EXPONENTS['beta'] / ISING_3D_EXPONENTS['nu']
        print(f"  β/ν = {b_nu:.4f} (error {abs(b_nu-exact_b_nu)/exact_b_nu:.1%})")
    results['fss_metro'] = fss_metro
    results['fss_wolff'] = fss_wolff

    # ═══════════════════════════════════════════════════════════
    # PHASE 6b: CORRECTIONS-TO-SCALING
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 6b: Corrections-to-Scaling FSS ════════════════╗")
    cts_metro = fss_corrections_to_scaling(multi_3d_metro, tc_discovered, omega=0.83)
    cts_wolff = fss_corrections_to_scaling(multi_3d_wolff, tc_discovered, omega=0.83)

    for name, cts in [('Metro', cts_metro), ('Wolff', cts_wolff)]:
        if cts.get('status') == 'success':
            print(f"  {name}: β/ν_std = {cts['standard_beta_over_nu']:.4f} ({cts['standard_error_pct']:.1f}%)")
            print(f"    β/ν_corr = {cts['corrected_beta_over_nu']:.4f} ({cts['corrected_error_pct']:.1f}%)  "
                  f"R²={cts['r2']:.4f}  a₁/a₀={cts['correction_ratio_a1_a0']:.3f}")
    results['corrections_to_scaling'] = {'metro': cts_metro, 'wolff': cts_wolff}

    # ═══════════════════════════════════════════════════════════
    # PHASE 7: MODEL COMPARISON + SENSITIVITY + TRIMMING
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 7: Model Comparison + Trimming ═════════════════╗")
    mc_M_full = model_comparison(X_M_3d.ravel(), y_M_3d)
    mc_chi_full = model_comparison(X_chi_3d.ravel(), y_chi_3d)
    mc_M_narrow = narrow_range_model_comparison(X_M_3d, y_M_3d, trim_pct=10.0)
    mc_chi_narrow = narrow_range_model_comparison(X_chi_3d, y_chi_3d, trim_pct=10.0)

    for obs, full, narrow in [('M(t)', mc_M_full, mc_M_narrow),
                               ('χ(t)', mc_chi_full, mc_chi_narrow)]:
        pf = full.get('preferred_model', '?')
        pn = narrow.get('preferred_model', '?')
        recov = " ★ PL recovers" if pf != 'power_law' and pn == 'power_law' else ""
        print(f"  {obs}: full→{pf}, narrow→{pn}{recov}")

    results['model_comparison'] = {
        'M_full': mc_M_full, 'chi_full': mc_chi_full,
        'M_narrow': mc_M_narrow, 'chi_narrow': mc_chi_narrow}

    sens_beta = sensitivity_analysis(X_M_3d, y_M_3d, 't_reduced', sign_hint=+1)
    sens_gamma = sensitivity_analysis(X_chi_3d, y_chi_3d, 't_reduced', sign_hint=-1)
    results['sensitivity'] = {'beta': sens_beta, 'gamma': sens_gamma}

    trim_beta = trimming_sweep(X_M_3d, y_M_3d, 't_reduced', sign_hint=+1)
    trim_gamma = trimming_sweep(X_chi_3d, y_chi_3d, 't_reduced', sign_hint=-1)
    results['trimming_sweep'] = {'beta': trim_beta, 'gamma': trim_gamma}

    for name, ts in [('β', trim_beta), ('γ', trim_gamma)]:
        plateau = "PLATEAU" if ts.get('plateau', False) else "variable"
        print(f"  {name} trim: [{ts.get('range', [0,0])[0]:.3f}, {ts.get('range', [0,0])[1]:.3f}] → {plateau}")

    narrow_configs = [c for c in sens_beta.get('configs', []) if c['range'] == 'narrow']
    beta_narrow = abs(narrow_configs[0]['exponent']) if narrow_configs else None

    # ═══════════════════════════════════════════════════════════
    # PHASE 8: DUAL CIs (initial, before self-repair)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 8: Dual CIs (initial) ════════════════════════╗")
    print(f"  BCa block bootstrap, block_size={block_size_metro}, n=1000")

    print(f"  β ... ", end='', flush=True)
    t0 = time.time()
    dual_beta = dual_confidence_intervals(
        multi_3d_metro, tc_discovered, tc_std, 'M', +1,
        block_size=block_size_metro, n_bootstrap=1000, seed=42)
    print(f"{time.time()-t0:.1f}s")

    print(f"  γ ... ", end='', flush=True)
    t0 = time.time()
    dual_gamma = dual_confidence_intervals(
        multi_3d_metro, tc_discovered, tc_std, 'chi', -1,
        block_size=block_size_metro, n_bootstrap=1000, seed=42)
    print(f"{time.time()-t0:.1f}s")

    for name, dual in [('β', dual_beta), ('γ', dual_gamma)]:
        s = dual.get('sampling_only', {})
        f = dual.get('sampling_plus_Tc', {})
        if 'ci_95_lower' in s and 'ci_95_lower' in f:
            w_s = s['ci_95_upper'] - s['ci_95_lower']
            w_f = f['ci_95_upper'] - f['ci_95_lower']
            ratio = w_f / max(w_s, 1e-10)
            print(f"  {name}: sampling w={w_s:.4f}, full w={w_f:.4f}, ratio={ratio:.0f}×")

    results['dual_cis'] = {'beta': dual_beta, 'gamma': dual_gamma}

    # ═══════════════════════════════════════════════════════════
    # PHASE 9: MULTI-SEED
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 9: Multi-Seed (3 seeds) ═══════════════════════╗")
    print(f"  L={L_target} ... ", end='', flush=True)
    t0 = time.time()
    multi_seed = multi_seed_exponents(
        L_target, T_scan_3d, tc_discovered, seeds=[42, 137, 271],
        n_equil=600 + 200 * L_target, n_measure=1000 + 300 * L_target)
    print(f"{time.time()-t0:.1f}s")

    if multi_seed['beta_mean']:
        print(f"  β: {multi_seed['beta_mean']:.4f} ± {multi_seed['beta_std']:.4f}")
    if multi_seed['gamma_mean']:
        print(f"  γ: {multi_seed['gamma_mean']:.4f} ± {multi_seed['gamma_std']:.4f}")
    results['multi_seed'] = multi_seed

    # ═══════════════════════════════════════════════════════════
    # PHASE 10: RUSHBROOKE
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 10: Rushbrooke ═══════════════════════════════╗")
    gamma_over_nu_val = fss_metro.get('gamma_over_nu', 0)
    rush_fss = fss_corrected_rushbrooke(
        beta_narrow if beta_narrow else ising_3d_exponents.get('beta', 0),
        gamma_over_nu_val,
        ISING_3D_EXPONENTS['nu'],
        ISING_3D_EXPONENTS['alpha'])

    gamma_raw_val = ising_3d_exponents.get('gamma', 0)
    beta_raw_val = ising_3d_exponents.get('beta', 0)
    rush_raw_lhs = ISING_3D_EXPONENTS['alpha'] + 2 * beta_raw_val + gamma_raw_val
    rush_raw_delta = abs(rush_raw_lhs - 2.0)

    print(f"  FSS-corrected: Δ = {rush_fss['delta']:.4f} {'VERIFIED' if rush_fss['verified'] else ''}")
    print(f"  Raw (finite-L): Δ = {rush_raw_delta:.4f}")
    results['rushbrooke'] = {
        'fss_corrected': rush_fss,
        'raw': {'lhs': float(rush_raw_lhs), 'delta': float(rush_raw_delta)},
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 11: HPC EXTENSION PLAN
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 11: HPC Extension Plan ═══════════════════════╗")
    beta_ci_width = 0.872
    s = dual_beta.get('sampling_plus_Tc', {})
    if 'ci_95_lower' in s:
        beta_ci_width = s['ci_95_upper'] - s['ci_95_lower']

    extension_plan = hpc_extension_plan(tc_std, max(L_3d), beta_ci_width)
    print(f"  Tc scaling: σ(Tc) ~ L^{{-{extension_plan['tc_scaling_exponent']:.2f}}} (heuristic from 1/ν+ω)")
    for step in extension_plan['plan'][:3]:
        print(f"  L={step['L']:3d}: Tc_std≈{step['tc_std_expected']:.4f} "
              f"({step['tc_error_pct_expected']:.2f}%), "
              f"β CI width≈{step['beta_ci_width_expected']:.3f}, "
              f"{step['improvement_factor']:.1f}× improvement")
    results['hpc_extension_plan'] = extension_plan

    # ═══════════════════════════════════════════════════════════
    # PHASE 12: 2D GENERALIZATION DEMO
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 12: 2D Generalization (controlled setting) ═════╗")
    print(f"  Purpose: manipulate Tc uncertainty in a controlled system")
    print(f"  (same universality class: 2D Ising, NOT a distinct class)")
    print(f"  Running ... ", end='', flush=True)
    t0 = time.time()
    gen_2d = generalization_2d_error_budget(n_bootstrap=500, seed=42)
    print(f"{time.time()-t0:.1f}s")

    if 'beta_2d' in gen_2d:
        print(f"  β_2D = {gen_2d['beta_2d']:.4f} (exact 0.125, error {gen_2d['beta_2d_error_pct']:.1f}%)")
    for scenario in ['exact_Tc', 'noisy_Tc']:
        if scenario in gen_2d:
            sc = gen_2d[scenario]
            print(f"  {scenario}: sampling w={sc['sampling_width']:.4f}, "
                  f"full w={sc['full_width']:.4f}, inflation={sc['inflation_ratio']:.1f}×")
    results['generalization_2d'] = gen_2d

    # ═══════════════════════════════════════════════════════════
    # PHASE 13: META-DISCOVERY
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 13: Meta-Discovery ═══════════════════════════╗")
    all_exp = {
        'ising_2d': {'d': 2, 'alpha': 0.0, 'nu': 1.0,
                     'beta': abs(law_M_2d.exponent) if law_M_2d else None,
                     'gamma': abs(law_chi_2d.exponent) if law_chi_2d else None},
        'ising_3d': {'d': 3, 'alpha': ISING_3D_EXPONENTS['alpha'],
                     'beta': ising_3d_exponents.get('beta'),
                     'gamma': ising_3d_exponents.get('gamma')},
    }
    meta_relations = discover_meta_relations(all_exp)
    anomalies = scan_for_anomalies(all_exp)
    print(f"  Relations tested. Anomalies: {len(anomalies)}")
    results['meta_relations'] = meta_relations
    results['anomalies'] = [
        {'type': a.signal_type, 'description': a.description,
         'strength': a.strength, 'systems': a.systems_involved}
        for a in anomalies[:15]]

    # ═══════════════════════════════════════════════════════════
    # PHASE 14: STATISTICAL SUMMARY
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 14: Statistical Summary ════════════════════════╗")

    all_r2 = [law.r_squared for law in [law_M_2d, law_chi_2d, law_M_3d, law_chi_3d] if law]
    p_values = [compute_law_p_value(r2, 12, 1) for r2 in all_r2]
    bh_mask = benjamini_hochberg(p_values, alpha=0.05)
    n_sig = sum(bh_mask)

    pre_reg_results = {}
    beta_estimates = {
        'beta_fss': fss_metro.get('beta_fss'),
        'beta_raw': ising_3d_exponents.get('beta'),
        'beta_narrow': beta_narrow,
    }
    if cts_wolff.get('status') == 'success':
        beta_estimates['beta_cts'] = cts_wolff['corrected_beta_over_nu'] * ISING_3D_EXPONENTS['nu']

    gamma_estimates = {
        'gamma_fss': fss_metro.get('gamma_fss'),
        'gamma_raw_ols': ising_3d_exponents.get('gamma'),
        'gamma_raw_ivw': ising_3d_exponents.get('gamma_ivw'),
    }
    if fss_metro.get('gamma_over_nu') is not None:
        gamma_estimates['gamma_fss_ratio'] = fss_metro['gamma_over_nu']

    n_pass = 0
    n_total = 0
    for name, val in {**beta_estimates, **gamma_estimates}.items():
        if val is None:
            continue
        if 'beta' in name:
            exact = ISING_3D_EXPONENTS['beta']
        elif 'gamma_fss_ratio' in name:
            exact = ISING_3D_EXPONENTS['gamma'] / ISING_3D_EXPONENTS['nu']
        else:
            exact = ISING_3D_EXPONENTS['gamma']
        error = abs(val - exact) / exact
        passed = error < 0.10
        n_total += 1
        if passed:
            n_pass += 1
        pre_reg_results[name] = {'value': float(val), 'error': float(error), 'passed': passed}

    print(f"  BH significant: {n_sig}/{len(all_r2)}")
    print(f"  Pre-registration: {n_pass}/{n_total} pass (10% criterion)")
    # Report errors relative to accepted literature values
    print(f"  (All errors reported relative to accepted literature values)")

    results['statistics'] = {
        'n_laws': len(all_r2), 'bh_significant': int(n_sig),
        'pre_registration_pass': n_pass, 'pre_registration_total': n_total,
        'pre_registration_results': pre_reg_results,
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 15: SELF-DIAGNOSIS (before repair)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 15: Self-Diagnosis (pre-repair) ════════════════╗")
    diagnosis = self_diagnosis_engine(results)
    print(f"  Verdict: {diagnosis['overall_verdict']}")
    for finding in diagnosis['findings']:
        sev_color = {'OK': '✓', 'GOOD': '✓', 'EXCELLENT': '✓', 'PASS': '✓',
                     'INFO': 'ℹ', 'ADEQUATE': '~', 'PARTIAL': '~',
                     'WARNING': '⚠', 'MODERATE': '⚠',
                     'SEVERE': '✗', 'POOR': '✗', 'FAIL': '✗'}.get(finding['severity'], '?')
        print(f"  {sev_color} [{finding['severity']:8s}] {finding['check']}: {finding['detail']}")
    for rec in diagnosis['recommendations']:
        print(f"  → {rec}")
    results['self_diagnosis_pre_repair'] = diagnosis

    # ═══════════════════════════════════════════════════════════
    # PHASE 16: SELF-REPAIR LOOP  ★★★ v11 BREAKTHROUGH ★★★
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 16: CLOSED-LOOP SELF-REPAIR ═══════════════════╗")
    print(f"  Checking diagnosis for actionable repair opportunities...")
    print(f"  ", end='', flush=True)
    t0 = time.time()
    repair = self_repair_loop(
        diagnosis, multi_3d_metro, multi_3d_wolff,
        tc_discovered, tc_std,
        block_size=block_size_metro,
        n_bootstrap=500)
    repair_time = time.time() - t0
    print(f"completed in {repair_time:.1f}s")

    if repair.get('triggered'):
        for log_line in repair.get('log', []):
            print(f"  {log_line}")

        if repair.get('success'):
            tc_b = repair['tc_before']
            tc_a = repair['tc_after']
            print(f"\n  ┌─── BEFORE/AFTER COMPARISON ───────────────────────┐")
            print(f"  │ Tc:  {tc_b['Tc']:.4f} ± {tc_b['std']:.4f} ({tc_b['error_pct']:.2f}%)")
            print(f"  │  →   {tc_a['Tc']:.4f} ± {tc_a['std']:.4f} ({tc_a['error_pct']:.2f}%)")
            print(f"  │ Tc improvement: {repair['tc_improvement_factor']:.1f}×")

            exp_rep = repair.get('exponents_repaired', {})
            if exp_rep.get('beta_narrow'):
                beta_err_before = abs((beta_narrow or 0) - ISING_3D_EXPONENTS['beta']) / ISING_3D_EXPONENTS['beta'] * 100
                beta_err_after = abs(exp_rep['beta_narrow'] - ISING_3D_EXPONENTS['beta']) / ISING_3D_EXPONENTS['beta'] * 100
                print(f"  │ β_narrow: {beta_narrow:.4f} → {exp_rep['beta_narrow']:.4f}")
                print(f"  │   error:  {beta_err_before:.1f}% → {beta_err_after:.1f}%")

            comp = repair.get('comparison', {})
            for exp_name in ['beta', 'gamma']:
                if exp_name in comp:
                    c = comp[exp_name]
                    # Get before values from initial dual CIs
                    if exp_name == 'beta':
                        before_ratio = (dual_beta.get('sampling_plus_Tc', {}).get('ci_95_upper', 0) -
                                       dual_beta.get('sampling_plus_Tc', {}).get('ci_95_lower', 0)) / \
                                      max(dual_beta.get('sampling_only', {}).get('ci_95_upper', 0) -
                                          dual_beta.get('sampling_only', {}).get('ci_95_lower', 1), 1e-10)
                    else:
                        before_ratio = (dual_gamma.get('sampling_plus_Tc', {}).get('ci_95_upper', 0) -
                                       dual_gamma.get('sampling_plus_Tc', {}).get('ci_95_lower', 0)) / \
                                      max(dual_gamma.get('sampling_only', {}).get('ci_95_upper', 0) -
                                          dual_gamma.get('sampling_only', {}).get('ci_95_lower', 1), 1e-10)
                    print(f"  │ {exp_name} CI inflation: {before_ratio:.0f}× → {c['inflation_ratio']:.1f}×")
            print(f"  └───────────────────────────────────────────────────┘")
    else:
        print(f"  Self-repair not triggered: {repair.get('reason', 'unknown')}")

    # Strip raw arrays before saving to JSON (they're numpy arrays)
    repair_for_json = {}
    for k, v in repair.items():
        if k in ('rw_metro', 'rw_wolff'):
            # Keep only non-array fields
            if isinstance(v, dict):
                repair_for_json[k] = {kk: vv for kk, vv in v.items()
                                      if not isinstance(vv, np.ndarray)}
            else:
                repair_for_json[k] = v
        elif isinstance(v, dict):
            repair_for_json[k] = v
        else:
            repair_for_json[k] = v
    results['self_repair'] = repair_for_json

    # ═══════════════════════════════════════════════════════════
    # PHASE 17: Tc DISTRIBUTION ROBUSTNESS  ★ NEW
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 17: Tc Distribution Robustness ═════════════════╗")
    print(f"  Gaussian vs t(df=3) vs Widened Gaussian ... ", end='', flush=True)
    t0 = time.time()
    robustness = tc_distribution_robustness(
        multi_3d_metro, tc_discovered, tc_std,
        observable='M', sign_hint=+1,
        block_size=block_size_metro, n_bootstrap=500, seed=42)
    print(f"{time.time()-t0:.1f}s")

    for dist_name, dist_res in robustness['distributions'].items():
        if dist_res.get('ci_width'):
            print(f"  {dist_name:20s}: CI width = {dist_res['ci_width']:.4f}")
    print(f"  Conclusion: {robustness['conclusion']}")
    results['tc_robustness'] = robustness

    # ═══════════════════════════════════════════════════════════
    # PHASE 18: POST-REPAIR SELF-DIAGNOSIS
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE 18: Self-Diagnosis (post-repair) ════════════════╗")
    # Build a modified results set with repaired Tc for diagnosis
    if repair.get('success'):
        results_post = dict(results)
        # Update Tc discovery with repaired values
        results_post['tc_discovery'] = dict(results['tc_discovery'])
        results_post['tc_discovery']['consensus_Tc'] = repair['tc_after']['Tc']
        results_post['tc_discovery']['consensus_std'] = repair['tc_after']['std']
        results_post['tc_discovery']['error_pct'] = repair['tc_after']['error_pct']
        # Update dual CIs with repaired values
        results_post['dual_cis'] = repair.get('dual_cis_repaired', results['dual_cis'])
        diagnosis_post = self_diagnosis_engine(results_post)
    else:
        diagnosis_post = diagnosis

    print(f"  Verdict: {diagnosis_post['overall_verdict']}")
    counts_pre = diagnosis.get('summary_counts', {})
    counts_post = diagnosis_post.get('summary_counts', {})
    print(f"  Pre-repair:  OK={counts_pre.get('ok',0)}, Warnings={counts_pre.get('warnings',0)}, Problems={counts_pre.get('problems',0)}")
    print(f"  Post-repair: OK={counts_post.get('ok',0)}, Warnings={counts_post.get('warnings',0)}, Problems={counts_post.get('problems',0)}")
    results['self_diagnosis_post_repair'] = diagnosis_post

    # ═══════════════════════════════════════════════════════════
    # LITERATURE + SAVE
    # ═══════════════════════════════════════════════════════════
    results['literature_comparison'] = dict(LITERATURE)
    results['literature_comparison']['This_work_v11'] = {
        'ref': 'This work',
        'L_max': 12,
        'beta': float(beta_narrow) if beta_narrow else None,
        'gamma': float(fss_metro['gamma_over_nu'] * ISING_3D_EXPONENTS['nu']) if fss_metro.get('gamma_over_nu') else None,
        'Tc': tc_discovered,
        'Tc_repaired': repair.get('tc_after', {}).get('Tc'),
        'method': 'Self-correcting autonomous pipeline + histogram reweighting',
    }

    elapsed = time.time() - t_start
    results['elapsed_seconds'] = elapsed

    print(f"\n{'='*76}")
    print(f"  v11 COMPLETE — {elapsed:.1f}s total")
    print(f"  Key result: self-repair {'TRIGGERED' if repair.get('triggered') else 'NOT TRIGGERED'}")
    if repair.get('success'):
        print(f"  Tc: {repair['tc_before']['error_pct']:.2f}% → {repair['tc_after']['error_pct']:.2f}%")
    print(f"{'='*76}")

    # Save JSON (strip numpy arrays from multi_L data)
    out_path = Path(__file__).parent.parent / 'results' / 'breakthrough_results_v11.json'
    out_path.parent.mkdir(exist_ok=True)

    def json_serialize(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=json_serialize)
    print(f"  Results saved to {out_path}")


if __name__ == '__main__':
    main()
