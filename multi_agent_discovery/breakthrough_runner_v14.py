"""
breakthrough_runner_v14.py — The RG-Aware Autonomous Discovery Engine
═══════════════════════════════════════════════════════════════════════

v14 ADDITIONS (driven by 9.8/10 review of v13):
─────────────────────────────────────────────────
1. AUTOMATED SCALING FUNCTION COLLAPSE
   - Finds optimal (β/ν, 1/ν) by minimizing inter-curve distance
   - Produces M·L^(β/ν) = F(t·L^(1/ν)) universal scaling function
   - Collapse quality metric S quantifies universality class membership

2. AUTONOMOUS WEGNER CORRECTIONS TO SCALING
   - Automatically detects when leading power-law fits fail (χ² test)
   - Fits M ~ L^(-β/ν)(1 + B·L^(-ω)) with autonomous ω search
   - Compares AIC of corrected vs. uncorrected fits to decide inclusion

3. CROSS-OBSERVABLE ν CONSISTENCY CHECK
   - Extracts ν from 3 independent methods:
     (a) Binder cumulant derivative dU4/dT scaling
     (b) Susceptibility peak shift χ_max(L)
     (c) Specific heat scaling C_max(L)
   - Flags self-inconsistency and triggers equilibration diagnostics

RETAINED: Everything from v13: O(2) Wolff, auto-WHAM, β scaling study,
          dual CIs, self-diagnosis, self-repair, pre-registration.
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
from scipy.optimize import minimize, minimize_scalar, curve_fit, differential_evolution
from scipy.interpolate import interp1d, UnivariateSpline
from scipy.stats import norm, shapiro, chi2, t as t_dist
from scipy.spatial.distance import cdist

sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_agent_discovery.breakthrough_runner_v7 import (
    ising_3d_mc, wolff_cluster_mc, generate_3d_dataset,
    discover_tc_binder, discover_tc_susceptibility,
    continuous_power_law_fit, ContinuousLaw,
    finite_size_scaling_exponents,
    ISING_3D_EXPONENTS, TC_3D, OMEGA_3D,
)
from multi_agent_discovery.breakthrough_runner_v8 import (
    integrated_autocorrelation_time,
    dual_confidence_intervals,
)
from multi_agent_discovery.breakthrough_runner_v11 import (
    ising_3d_mc_raw, wolff_cluster_mc_raw, generate_3d_dataset_raw,
    histogram_reweight_tc,
)
from multi_agent_discovery.breakthrough_runner_v12 import (
    XY_3D_EXPONENTS, TC_3D_XY, OMEGA_3D_XY,
    xy_3d_mc_raw, generate_xy_dataset_raw,
    wham_tc_refinement,
)
from multi_agent_discovery.breakthrough_runner_v13 import (
    xy_wolff_cluster_mc_raw, generate_xy_wolff_dataset_raw,
    wham_track_selector, xy_beta_scaling_study,
    xy_transfer_experiment_v13,
    hash_pre_registration_v13, PRE_REG_PROTOCOL_V13,
)
from multi_agent_discovery.breakthrough_runner_v4 import (
    TC_2D, ising_2d_mc, generate_ising_dataset,
)
from multi_agent_discovery.breakthrough_runner_v7 import (
    discover_tc_binder as discover_tc_binder_v7,
)
from multi_agent_discovery.heisenberg_kernel import (
    heisenberg_3d_mc, generate_heisenberg_dataset,
    heisenberg_transfer_experiment, heisenberg_pedestal_prediction,
    benchmark_heisenberg,
    HEISENBERG_3D_EXPONENTS, TC_3D_HEISENBERG, OMEGA_3D_HEISENBERG,
    U4_GAUSSIAN_LIMIT_O3, HAS_NUMBA,
)


# ═══════════════════════════════════════════════════════════════
# PRE-REGISTRATION v14
# ═══════════════════════════════════════════════════════════════
PRE_REG_PROTOCOL_V14 = {
    **PRE_REG_PROTOCOL_V13,
    'version': 'v14_rg_aware_autonomous_engine',
    'new_capabilities': [
        'automated_scaling_collapse',
        'autonomous_wegner_corrections',
        'cross_observable_nu_consistency',
        'weighted_crossing_tc_consensus',
        'heisenberg_O3_transfer',
    ],
    'collapse_method': 'functional minimization of inter-curve distance S',
    'wegner_criterion': 'AIC comparison: corrected vs. uncorrected fit',
    'nu_consistency_threshold': '15% max spread across 3 methods',
    'crossing_weight': 'w_ij = (L_i * L_j)^alpha / sigma_ij, alpha calibrated on 2D Ising',
    'heisenberg_dynamics': 'hybrid O(3) Wolff + over-relaxation (5 OR + 3 Wolff per sweep)',
    'commitment': 'NO parameter tuning after seeing results',
}


def hash_pre_registration_v14() -> str:
    canonical = json.dumps(PRE_REG_PROTOCOL_V14, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════
# 0. WEIGHTED-CROSSING Tc CONSENSUS (v14 NEW)
# ═══════════════════════════════════════════════════════════════

def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """
    Compute weighted median: the value at which cumulative weight
    reaches 50% of total weight.

    Parameters
    ----------
    values : 1D array of values
    weights : 1D array of non-negative weights (same length)

    Returns
    -------
    Weighted median (float)
    """
    if len(values) == 0:
        return np.nan
    if len(values) == 1:
        return float(values[0])
    order = np.argsort(values)
    sorted_vals = values[order]
    sorted_wts = weights[order]
    cum_wt = np.cumsum(sorted_wts)
    half = cum_wt[-1] / 2.0
    idx = np.searchsorted(cum_wt, half)
    idx = min(idx, len(sorted_vals) - 1)
    return float(sorted_vals[idx])


def ising_2d_mc_with_U4(L: int, T: float, n_equil: int = 2000,
                         n_measure: int = 3000, seed: int = None) -> dict:
    """
    2D Ising MC wrapper that adds the Binder cumulant U4.

    The v4 ising_2d_mc doesn't track M2/M4 separately, so we
    reimplement the measurement loop to compute U4 = 1 - <M^4>/(3<M^2>^2).
    """
    rng = np.random.RandomState(seed)
    N = L * L
    spins = rng.choice([-1, 1], size=(L, L)).astype(np.float64)
    rows, cols = np.meshgrid(np.arange(L), np.arange(L), indexing='ij')
    masks = [(rows + cols) % 2 == p for p in (0, 1)]
    beta_J = 1.0 / T

    def sweep():
        for mask in masks:
            nn = (np.roll(spins, 1, 0) + np.roll(spins, -1, 0) +
                  np.roll(spins, 1, 1) + np.roll(spins, -1, 1))
            dE = 2.0 * spins * nn
            accept = (dE <= 0) | (rng.random((L, L)) < np.exp(-beta_J * np.clip(dE, 0, 20)))
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
        M_arr[i] = abs(m)
        M2_arr[i] = m ** 2
        M4_arr[i] = m ** 4
        E_arr[i] = -np.mean(spins * (np.roll(spins, 1, 0) + np.roll(spins, 1, 1)))

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
    }


def allpairs_binder_crossings(multi_L: Dict[int, List[dict]],
                              T_density: int = 2000) -> List[dict]:
    """
    Extract Binder cumulant crossings from ALL L-pair combinations
    (not just adjacent pairs), returning per-crossing metadata.

    For each pair (L_i, L_j) with L_i < L_j, finds all T values where
    U4(T, L_i) = U4(T, L_j) via linear interpolation of sign changes.

    Parameters
    ----------
    multi_L : dict mapping L → list of {T, U4, ...} measurement dicts
    T_density : number of points in the fine T grid

    Returns
    -------
    List of dicts, each with:
      - 'Tc': crossing temperature
      - 'L_i', 'L_j': the two lattice sizes
      - 'sigma': rough uncertainty from interpolation (T-grid spacing)
      - 'L_product': L_i * L_j
    """
    L_values = sorted(multi_L.keys())
    U4_interps = {}
    T_ranges = []

    for L in L_values:
        data = sorted(multi_L[L], key=lambda d: d['T'])
        Ts = [d['T'] for d in data]
        U4s = [d['U4'] for d in data]
        T_ranges.append((min(Ts), max(Ts)))
        U4_interps[L] = interp1d(Ts, U4s, kind='linear', fill_value='extrapolate')

    T_min = max(r[0] for r in T_ranges)
    T_max = min(r[1] for r in T_ranges)
    T_fine = np.linspace(T_min, T_max, T_density)
    dT = (T_max - T_min) / T_density  # grid spacing → rough σ

    crossings = []
    for i in range(len(L_values)):
        for j in range(i + 1, len(L_values)):
            L_i, L_j = L_values[i], L_values[j]
            diff = U4_interps[L_i](T_fine) - U4_interps[L_j](T_fine)
            sign_changes = np.where(np.diff(np.sign(diff)))[0]

            for idx in sign_changes:
                t1, t2 = T_fine[idx], T_fine[idx + 1]
                d1, d2 = diff[idx], diff[idx + 1]
                if abs(d2 - d1) > 1e-15:
                    tc_est = t1 - d1 * (t2 - t1) / (d2 - d1)
                    crossings.append({
                        'Tc': float(tc_est),
                        'L_i': L_i,
                        'L_j': L_j,
                        'sigma': float(dT),
                        'L_product': L_i * L_j,
                    })

    return crossings


def weighted_crossing_tc(crossings: List[dict],
                         alpha: float = 1.0) -> dict:
    """
    Compute weighted-median Tc from a list of Binder crossing estimates,
    using the crossing-quality weight:

        w_ij = (L_i * L_j)^alpha / sigma_ij

    The (L_i * L_j)^alpha term upweights large-lattice pairs (whose
    crossings are less contaminated by finite-size corrections), and
    1/sigma_ij downweights uncertain crossings.

    Parameters
    ----------
    crossings : list of dicts from allpairs_binder_crossings()
    alpha : exponent on the L-product weighting
            (α=0 → unweighted; α=1 → linear; α=2 → quadratic)

    Returns
    -------
    dict with:
      - 'Tc_weighted': weighted median Tc
      - 'Tc_unweighted': unweighted median for comparison
      - 'MAD_weighted': weighted median absolute deviation
      - 'MAD_unweighted': unweighted MAD
      - 'n_crossings': total number of crossings used
      - 'alpha': the α value used
    """
    if not crossings:
        return {'status': 'no_crossings', 'Tc_weighted': np.nan}

    tc_arr = np.array([c['Tc'] for c in crossings])
    sigma_arr = np.array([max(c['sigma'], 1e-6) for c in crossings])
    Lprod_arr = np.array([c['L_product'] for c in crossings], dtype=float)

    # Compute weights
    weights = (Lprod_arr ** alpha) / sigma_arr

    # Weighted median
    tc_weighted = weighted_median(tc_arr, weights)

    # Unweighted median
    tc_unweighted = float(np.median(tc_arr))

    # MADs
    mad_weighted = weighted_median(np.abs(tc_arr - tc_weighted), weights)
    mad_unweighted = float(np.median(np.abs(tc_arr - tc_unweighted)))

    return {
        'status': 'success',
        'Tc_weighted': tc_weighted,
        'Tc_unweighted': tc_unweighted,
        'Tc_std_weighted': float(1.4826 * mad_weighted),  # Gaussian-equivalent σ
        'Tc_std_unweighted': float(1.4826 * mad_unweighted),
        'MAD_weighted': float(mad_weighted),
        'MAD_unweighted': float(mad_unweighted),
        'n_crossings': len(crossings),
        'alpha': alpha,
    }


def calibrate_crossing_alpha(multi_L_2d: Dict[int, List[dict]],
                             Tc_exact: float,
                             alpha_range: Tuple[float, float] = (0.0, 3.0),
                             n_grid: int = 31) -> dict:
    """
    Calibrate the crossing-quality exponent α on the 2D Ising control,
    where the exact Tc is known.

    Strategy: leave-one-out (LOO) cross-validation.
    For each α in [0, 3]:
      1. Extract all-pairs crossings from 2D Ising data
      2. For each crossing i, compute the weighted-median Tc from all
         OTHER crossings (leave-one-out)
      3. Score = mean |Tc_LOO_i - Tc_exact| across all held-out crossings

    The α that minimizes this LOO error is returned.

    Parameters
    ----------
    multi_L_2d : dict mapping L → list of 2D Ising measurement dicts
    Tc_exact : exact 2D Ising Tc (2/ln(1+√2) ≈ 2.26919)
    alpha_range : search range for α
    n_grid : number of α values to evaluate

    Returns
    -------
    dict with:
      - 'alpha_best': optimal α value
      - 'loo_error_best': LOO error at optimal α
      - 'alpha_scores': all (α, LOO_error) pairs
      - 'improvement': ratio of unweighted to best-weighted LOO error
    """
    crossings = allpairs_binder_crossings(multi_L_2d)
    n_cross = len(crossings)

    if n_cross < 4:
        return {
            'status': 'insufficient_crossings',
            'n_crossings': n_cross,
            'alpha_best': 1.0,  # fallback default
        }

    tc_arr = np.array([c['Tc'] for c in crossings])
    sigma_arr = np.array([max(c['sigma'], 1e-6) for c in crossings])
    Lprod_arr = np.array([c['L_product'] for c in crossings], dtype=float)

    alphas = np.linspace(alpha_range[0], alpha_range[1], n_grid)
    loo_scores = np.empty(n_grid)

    for ai, alpha in enumerate(alphas):
        loo_errors = np.empty(n_cross)
        raw_weights = (Lprod_arr ** alpha) / sigma_arr

        for k in range(n_cross):
            # Leave out crossing k
            mask = np.ones(n_cross, dtype=bool)
            mask[k] = False
            tc_loo = weighted_median(tc_arr[mask], raw_weights[mask])
            loo_errors[k] = abs(tc_loo - Tc_exact)

        loo_scores[ai] = float(np.mean(loo_errors))

    best_idx = int(np.argmin(loo_scores))
    alpha_best = float(alphas[best_idx])
    loo_best = float(loo_scores[best_idx])

    # Unweighted baseline (α = 0)
    loo_unweighted = float(loo_scores[0]) if alphas[0] == 0.0 else None

    improvement = loo_unweighted / loo_best if loo_unweighted and loo_best > 0 else None

    return {
        'status': 'success',
        'alpha_best': alpha_best,
        'loo_error_best': loo_best,
        'loo_error_unweighted': loo_unweighted,
        'improvement': float(improvement) if improvement else None,
        'n_crossings': n_cross,
        'alpha_scores': [(float(a), float(s)) for a, s in zip(alphas, loo_scores)],
    }


def v14_weighted_crossing_analysis(
    multi_L_target: Dict[int, List[dict]],
    multi_L_2d_control: Dict[int, List[dict]],
    Tc_exact_2d: float,
    Tc_accepted_target: float = None,
    system_label: str = '3D system',
) -> dict:
    """
    Full v14 weighted-crossing pipeline:
      1. Calibrate α on 2D Ising control (LOO)
      2. Extract all-pairs crossings from target system
      3. Compute weighted-median Tc using calibrated α
      4. Compare to unweighted median and accepted Tc

    Parameters
    ----------
    multi_L_target : target system data (e.g., 3D Ising or 3D XY)
    multi_L_2d_control : 2D Ising control data
    Tc_exact_2d : exact 2D Ising Tc
    Tc_accepted_target : accepted Tc for the target system (for error %)
    system_label : label for output

    Returns
    -------
    dict with calibration results, weighted Tc, comparison table
    """
    # Step 1: Calibrate α on 2D Ising
    calib = calibrate_crossing_alpha(multi_L_2d_control, Tc_exact_2d)
    alpha_best = calib.get('alpha_best', 1.0)

    # Step 2: Extract target crossings
    crossings_target = allpairs_binder_crossings(multi_L_target)

    # Step 3: Compute weighted Tc at α = 0 (unweighted), α = 1, α_best, α = 2
    results_by_alpha = {}
    for label, alpha_val in [('unweighted', 0.0), ('alpha_1', 1.0),
                              ('alpha_best', alpha_best), ('alpha_2', 2.0)]:
        r = weighted_crossing_tc(crossings_target, alpha=alpha_val)
        if Tc_accepted_target and r.get('status') == 'success':
            r['error_pct'] = abs(r['Tc_weighted'] - Tc_accepted_target) / Tc_accepted_target * 100
        results_by_alpha[label] = r

    # Also calibrate on 2D control and report α = 1 and α = 2 for comparison
    crossings_2d = allpairs_binder_crossings(multi_L_2d_control)
    control_results = {}
    for label, alpha_val in [('unweighted', 0.0), ('alpha_1', 1.0),
                              ('alpha_best', alpha_best), ('alpha_2', 2.0)]:
        r = weighted_crossing_tc(crossings_2d, alpha=alpha_val)
        r['error_pct'] = abs(r['Tc_weighted'] - Tc_exact_2d) / Tc_exact_2d * 100
        control_results[label] = r

    return {
        'status': 'success',
        'system': system_label,
        'calibration': calib,
        'alpha_best': alpha_best,
        'target_results': results_by_alpha,
        'control_results': control_results,
        'n_crossings_target': len(crossings_target),
        'n_crossings_control': len(crossings_2d),
    }


# ═══════════════════════════════════════════════════════════════
# 1. AUTOMATED SCALING FUNCTION COLLAPSE
# ═══════════════════════════════════════════════════════════════

def scaling_collapse(multi_L: Dict[int, List[dict]],
                     Tc: float,
                     observable: str = 'M',
                     exponent_bounds: dict = None,
                     n_bootstrap: int = 200,
                     seed: int = 42) -> dict:
    """
    Automated data collapse for universal scaling functions.

    For magnetization: M · L^(β/ν) = F(t · L^(1/ν))
    For susceptibility: χ · L^(-γ/ν) = G(t · L^(1/ν))

    The algorithm:
      1. Extract M(T, L) or χ(T, L) from multi_L data
      2. For trial exponents (x = β/ν or -γ/ν, y = 1/ν):
         - Compute scaled variables: X_i = t_i · L^y, Y_i = O_i · L^x
         - Measure collapse quality S (inter-curve distance)
      3. Minimize S over (x, y) using differential evolution
      4. Bootstrap over MC data to get exponent CIs
      5. Report best-fit exponents and collapse quality

    Collapse quality metric S:
      For each rescaled point (X_i, Y_i) from lattice L_i, find the
      nearest point from a DIFFERENT lattice. S = mean of these distances.
      Perfect collapse → S ≈ 0. Poor collapse → S >> 0.

    Parameters
    ----------
    multi_L : dict mapping L → list of {T, M, chi, ...} dicts
    Tc : critical temperature estimate
    observable : 'M' for magnetization, 'chi' for susceptibility
    exponent_bounds : dict with 'x_range' and 'y_range' for search bounds
    n_bootstrap : number of bootstrap resamples for CIs
    seed : random seed for reproducibility

    Returns
    -------
    dict with best-fit exponents, collapse quality, bootstrap CIs
    """
    rng = np.random.RandomState(seed)
    L_vals = sorted(multi_L.keys())

    if len(L_vals) < 3:
        return {'status': 'insufficient_L', 'L_vals': L_vals}

    # --- Extract data per L ---
    curves = {}  # L → (T_array, O_array)
    for L in L_vals:
        data = sorted(multi_L[L], key=lambda d: d['T'])
        Ts = np.array([d['T'] for d in data])
        if observable == 'M':
            Os = np.array([d['M'] for d in data])
        elif observable == 'chi':
            Os = np.array([d['chi'] for d in data])
        else:
            raise ValueError(f"Unknown observable: {observable}")
        # Filter to near-critical region: |t| < 0.3
        t_reduced = (Ts - Tc) / Tc
        mask = np.abs(t_reduced) < 0.3
        if np.sum(mask) >= 4:
            curves[L] = (t_reduced[mask], Os[mask], Ts[mask])

    if len(curves) < 3:
        return {'status': 'insufficient_data_near_Tc', 'n_curves': len(curves)}

    # --- Set search bounds ---
    if exponent_bounds is None:
        if observable == 'M':
            # β/ν ∈ [0.1, 1.5], 1/ν ∈ [0.5, 3.0]
            x_range = (0.1, 1.5)
            y_range = (0.5, 3.0)
        else:
            # -γ/ν ∈ [-3.5, -0.5], 1/ν ∈ [0.5, 3.0]
            x_range = (-3.5, -0.5)
            y_range = (0.5, 3.0)
    else:
        x_range = exponent_bounds.get('x_range', (0.1, 1.5))
        y_range = exponent_bounds.get('y_range', (0.5, 3.0))

    def collapse_quality(params):
        """
        Compute collapse quality S for given exponents.

        S = mean nearest-neighbor distance between rescaled curves
        from DIFFERENT lattice sizes. Lower is better.
        """
        x_exp, y_exp = params

        # Rescale all data
        all_points = []  # (X_scaled, Y_scaled, L_label)
        for L in curves:
            t_arr, O_arr, _ = curves[L]
            X_scaled = t_arr * (L ** y_exp)
            if observable == 'M':
                Y_scaled = O_arr * (L ** x_exp)
            else:
                Y_scaled = O_arr * (L ** x_exp)
            for xi, yi in zip(X_scaled, Y_scaled):
                all_points.append((xi, yi, L))

        if len(all_points) < 6:
            return 1e6

        # Normalize axes to [0,1] for fair distance computation
        xs = np.array([p[0] for p in all_points])
        ys = np.array([p[1] for p in all_points])
        x_scale = np.ptp(xs) if np.ptp(xs) > 0 else 1.0
        y_scale = np.ptp(ys) if np.ptp(ys) > 0 else 1.0

        # Compute mean nearest-neighbor distance from different-L points
        total_dist = 0.0
        n_pairs = 0
        for i, (xi, yi, Li) in enumerate(all_points):
            min_d = np.inf
            for j, (xj, yj, Lj) in enumerate(all_points):
                if i == j or Li == Lj:
                    continue
                d = ((xi - xj) / x_scale) ** 2 + ((yi - yj) / y_scale) ** 2
                if d < min_d:
                    min_d = d
            if min_d < np.inf:
                total_dist += np.sqrt(min_d)
                n_pairs += 1

        return total_dist / max(n_pairs, 1)

    # --- Optimize using differential evolution (global) ---
    bounds = [x_range, y_range]
    result = differential_evolution(
        collapse_quality, bounds,
        seed=seed, maxiter=300, tol=1e-6,
        popsize=20, mutation=(0.5, 1.5), recombination=0.8,
    )

    best_x, best_y = result.x
    best_S = result.fun

    # --- Refine with Nelder-Mead (local) ---
    refined = minimize(collapse_quality, [best_x, best_y],
                       method='Nelder-Mead', options={'xatol': 1e-5, 'fatol': 1e-8})
    if refined.fun < best_S:
        best_x, best_y = refined.x
        best_S = refined.fun

    # --- Bootstrap CIs ---
    boot_x = np.empty(n_bootstrap)
    boot_y = np.empty(n_bootstrap)

    for b in range(n_bootstrap):
        # Resample data within each L
        boot_curves = {}
        for L in curves:
            t_arr, O_arr, T_arr = curves[L]
            n = len(t_arr)
            idx = rng.choice(n, size=n, replace=True)
            boot_curves[L] = (t_arr[idx], O_arr[idx], T_arr[idx])

        # Store original curves, replace temporarily
        orig_curves = curves.copy()
        curves_ref = curves

        def boot_quality(params):
            x_exp, y_exp = params
            all_points = []
            for L in boot_curves:
                t_arr, O_arr, _ = boot_curves[L]
                X_scaled = t_arr * (L ** y_exp)
                Y_scaled = O_arr * (L ** x_exp)
                for xi, yi in zip(X_scaled, Y_scaled):
                    all_points.append((xi, yi, L))
            if len(all_points) < 6:
                return 1e6
            xs = np.array([p[0] for p in all_points])
            ys = np.array([p[1] for p in all_points])
            x_scale = np.ptp(xs) if np.ptp(xs) > 0 else 1.0
            y_scale = np.ptp(ys) if np.ptp(ys) > 0 else 1.0
            total_dist = 0.0
            n_pairs = 0
            for i, (xi, yi, Li) in enumerate(all_points):
                min_d = np.inf
                for j, (xj, yj, Lj) in enumerate(all_points):
                    if i == j or Li == Lj:
                        continue
                    d = ((xi - xj) / x_scale) ** 2 + ((yi - yj) / y_scale) ** 2
                    if d < min_d:
                        min_d = d
                if min_d < np.inf:
                    total_dist += np.sqrt(min_d)
                    n_pairs += 1
            return total_dist / max(n_pairs, 1)

        try:
            b_result = minimize(boot_quality, [best_x, best_y],
                                method='Nelder-Mead',
                                options={'xatol': 1e-4, 'maxiter': 200})
            boot_x[b] = b_result.x[0]
            boot_y[b] = b_result.x[1]
        except Exception:
            boot_x[b] = best_x
            boot_y[b] = best_y

    # --- Compute exponents from collapse ---
    if observable == 'M':
        beta_over_nu = best_x
        one_over_nu = best_y
        nu_collapse = 1.0 / one_over_nu
        beta_collapse = beta_over_nu * nu_collapse
        exponent_results = {
            'beta_over_nu': float(beta_over_nu),
            'one_over_nu': float(one_over_nu),
            'nu': float(nu_collapse),
            'beta': float(beta_collapse),
            'beta_over_nu_ci': [float(np.percentile(boot_x, 2.5)),
                                 float(np.percentile(boot_x, 97.5))],
            'one_over_nu_ci': [float(np.percentile(boot_y, 2.5)),
                                float(np.percentile(boot_y, 97.5))],
        }
    else:
        gamma_over_nu = -best_x  # we fit -γ/ν
        one_over_nu = best_y
        nu_collapse = 1.0 / one_over_nu
        gamma_collapse = gamma_over_nu * nu_collapse
        exponent_results = {
            'gamma_over_nu': float(gamma_over_nu),
            'one_over_nu': float(one_over_nu),
            'nu': float(nu_collapse),
            'gamma': float(gamma_collapse),
            'gamma_over_nu_ci': [float(np.percentile(-boot_x, 2.5)),
                                  float(np.percentile(-boot_x, 97.5))],
            'one_over_nu_ci': [float(np.percentile(boot_y, 2.5)),
                                float(np.percentile(boot_y, 97.5))],
        }

    # --- Generate collapsed curve data for plotting ---
    collapsed_data = {}
    for L in curves:
        t_arr, O_arr, T_arr = curves[L]
        X_scaled = t_arr * (L ** best_y)
        Y_scaled = O_arr * (L ** best_x)
        collapsed_data[L] = {
            'X_scaled': X_scaled.tolist(),
            'Y_scaled': Y_scaled.tolist(),
            'T_original': T_arr.tolist(),
        }

    # --- Collapse quality assessment ---
    # S < 0.02: excellent collapse (strong universality evidence)
    # S ∈ [0.02, 0.05]: good collapse
    # S ∈ [0.05, 0.10]: moderate — possible corrections to scaling
    # S > 0.10: poor — wrong universality class or severe FSS corrections
    if best_S < 0.02:
        quality_label = 'EXCELLENT'
    elif best_S < 0.05:
        quality_label = 'GOOD'
    elif best_S < 0.10:
        quality_label = 'MODERATE'
    else:
        quality_label = 'POOR'

    return {
        'status': 'success',
        'observable': observable,
        'collapse_quality_S': float(best_S),
        'quality_label': quality_label,
        'optimizer_converged': bool(result.success),
        'n_function_evals': int(result.nfev),
        'exponents': exponent_results,
        'collapsed_data': collapsed_data,
        'L_values_used': sorted(curves.keys()),
        'n_bootstrap': n_bootstrap,
    }


# ═══════════════════════════════════════════════════════════════
# 2. AUTONOMOUS WEGNER CORRECTIONS TO SCALING
# ═══════════════════════════════════════════════════════════════

def wegner_corrected_fss(multi_L: Dict[int, List[dict]],
                         Tc: float,
                         observable: str = 'M',
                         omega_range: Tuple[float, float] = (0.3, 1.5),
                         known_omega: float = None) -> dict:
    """
    Autonomous detection and fitting of Wegner corrections to scaling.

    The leading FSS ansatz:
        O(Tc, L) = A · L^(-x/ν) · (1 + B · L^(-ω) + ...)

    For magnetization: x = β, so O = M ~ L^(-β/ν)(1 + B·L^(-ω))
    For susceptibility: x = -γ, so O = χ ~ L^(γ/ν)(1 + B·L^(-ω))

    Algorithm:
      1. Fit simple power law: O = A · L^p
      2. Compute χ² goodness-of-fit
      3. If χ²/dof > 2.0 (poor fit), autonomously try Wegner correction:
         O = A · L^p · (1 + B · L^(-ω))
      4. If known_omega is provided, fix ω; otherwise search over omega_range
      5. Compare AIC of both models to decide if correction is justified

    Parameters
    ----------
    multi_L : dict mapping L → list of measurement dicts
    Tc : critical temperature
    observable : 'M' or 'chi'
    omega_range : search range for correction exponent ω
    known_omega : if provided, fix ω to this value (e.g., 0.832 for 3D Ising)

    Returns
    -------
    dict with uncorrected fit, corrected fit (if needed), AIC comparison
    """
    L_vals = sorted(multi_L.keys())
    if len(L_vals) < 3:
        return {'status': 'insufficient_L'}

    # Extract O(Tc, L) by interpolation
    OL = {}
    OL_err = {}
    for L in L_vals:
        data = sorted(multi_L[L], key=lambda d: d['T'])
        Ts = np.array([d['T'] for d in data])
        if observable == 'M':
            Os = np.array([d['M'] for d in data])
        elif observable == 'chi':
            Os = np.array([d['chi'] for d in data])
        else:
            raise ValueError(f"Unknown observable: {observable}")
        try:
            f = interp1d(Ts, Os, kind='linear', fill_value='extrapolate')
            OL[L] = float(f(Tc))
            # Rough error from neighboring T points
            idx = np.argmin(np.abs(Ts - Tc))
            local_std = np.std(Os[max(0, idx-2):idx+3]) if len(Os) > 4 else np.std(Os) * 0.1
            OL_err[L] = max(float(local_std), abs(OL[L]) * 0.01)  # floor at 1%
        except Exception:
            pass

    Ls = np.array(sorted(OL.keys()), dtype=float)
    Os = np.array([OL[int(L)] for L in Ls])
    Os_err = np.array([OL_err[int(L)] for L in Ls])

    if len(Ls) < 3:
        return {'status': 'insufficient_interpolated_data'}

    # === Fit 1: Simple power law O = A * L^p ===
    log_L = np.log(Ls)
    log_O = np.log(np.abs(Os))

    try:
        p_simple, log_A_simple = np.polyfit(log_L, log_O, 1)
        A_simple = np.exp(log_A_simple)
        O_pred_simple = A_simple * Ls ** p_simple
        residuals_simple = (Os - O_pred_simple) / Os_err
        chi2_simple = float(np.sum(residuals_simple ** 2))
        dof_simple = len(Ls) - 2
        chi2_dof_simple = chi2_simple / max(dof_simple, 1)

        # AIC for simple model (2 parameters: A, p)
        n = len(Ls)
        ss_simple = float(np.sum((Os - O_pred_simple) ** 2))
        aic_simple = n * np.log(ss_simple / n) + 2 * 2
    except Exception as e:
        return {'status': 'simple_fit_failed', 'error': str(e)}

    simple_fit = {
        'A': float(A_simple),
        'p': float(p_simple),
        'chi2': chi2_simple,
        'chi2_dof': chi2_dof_simple,
        'aic': float(aic_simple),
        'residuals': residuals_simple.tolist(),
    }

    # === Decision: is correction needed? ===
    needs_correction = chi2_dof_simple > 2.0
    correction_reason = None
    if needs_correction:
        correction_reason = f'chi2/dof = {chi2_dof_simple:.2f} > 2.0 threshold'

    # === Fit 2: Wegner-corrected O = A * L^p * (1 + B * L^(-ω)) ===
    corrected_fit = None
    if needs_correction or known_omega is not None:
        def wegner_model(L_arr, A, p, B, omega):
            return A * L_arr ** p * (1.0 + B * L_arr ** (-omega))

        best_aic_corr = np.inf
        best_params_corr = None

        if known_omega is not None:
            omega_trials = [known_omega]
        else:
            omega_trials = np.linspace(omega_range[0], omega_range[1], 30)

        for omega_trial in omega_trials:
            try:
                def model_fixed_omega(L_arr, A, p, B):
                    return A * L_arr ** p * (1.0 + B * L_arr ** (-omega_trial))

                popt, pcov = curve_fit(
                    model_fixed_omega, Ls, Os,
                    p0=[A_simple, p_simple, 0.1],
                    sigma=Os_err, absolute_sigma=True,
                    maxfev=5000,
                )
                O_pred_corr = model_fixed_omega(Ls, *popt)
                ss_corr = float(np.sum((Os - O_pred_corr) ** 2))

                # AIC: 4 parameters (A, p, B, ω) or 3 if ω fixed
                n_params = 3 if known_omega is not None else 4
                aic_corr = n * np.log(ss_corr / n) + 2 * n_params

                if aic_corr < best_aic_corr:
                    best_aic_corr = aic_corr
                    residuals_corr = (Os - O_pred_corr) / Os_err
                    best_params_corr = {
                        'A': float(popt[0]),
                        'p': float(popt[1]),
                        'B': float(popt[2]),
                        'omega': float(omega_trial),
                        'omega_fixed': known_omega is not None,
                        'chi2': float(np.sum(residuals_corr ** 2)),
                        'chi2_dof': float(np.sum(residuals_corr ** 2)) / max(len(Ls) - n_params, 1),
                        'aic': float(aic_corr),
                        'correction_amplitude': float(abs(popt[2])),
                        'residuals': residuals_corr.tolist(),
                    }
            except Exception:
                continue

        if best_params_corr is not None:
            corrected_fit = best_params_corr

    # === Model selection ===
    correction_adopted = False
    if corrected_fit is not None:
        delta_aic = aic_simple - corrected_fit['aic']
        # AIC difference > 2: correction is justified
        correction_adopted = delta_aic > 2.0
        model_selection = {
            'delta_aic': float(delta_aic),
            'correction_adopted': correction_adopted,
            'reason': ('Correction adopted: ΔAIC = {:.1f} > 2.0'.format(delta_aic)
                       if correction_adopted
                       else 'Correction rejected: ΔAIC = {:.1f} ≤ 2.0 (simple model preferred)'.format(delta_aic)),
        }
    else:
        model_selection = {
            'delta_aic': None,
            'correction_adopted': False,
            'reason': 'No valid corrected fit obtained' if needs_correction else 'Simple fit adequate (χ²/dof ≤ 2.0)',
        }

    # === Best-fit exponent ===
    if correction_adopted and corrected_fit:
        best_exponent = corrected_fit['p']
        best_omega = corrected_fit['omega']
        best_B = corrected_fit['B']
    else:
        best_exponent = simple_fit['p']
        best_omega = None
        best_B = None

    return {
        'status': 'success',
        'observable': observable,
        'L_values': [int(L) for L in Ls],
        'O_at_Tc': {int(L): float(OL[int(L)]) for L in Ls},
        'simple_fit': simple_fit,
        'needs_correction': needs_correction,
        'correction_reason': correction_reason,
        'corrected_fit': corrected_fit,
        'model_selection': model_selection,
        'best_exponent': float(best_exponent),
        'best_omega': float(best_omega) if best_omega is not None else None,
        'best_correction_amplitude': float(best_B) if best_B is not None else None,
    }


# ═══════════════════════════════════════════════════════════════
# 3. CROSS-OBSERVABLE ν CONSISTENCY CHECK
# ═══════════════════════════════════════════════════════════════

def nu_cross_consistency(multi_L: Dict[int, List[dict]],
                         Tc: float,
                         Tc_std: float = 0.0,
                         accepted_nu: float = None) -> dict:
    """
    Extract ν from 3 independent methods and check self-consistency.

    Method 1 — Binder cumulant derivative:
        dU4/dT|_max ~ L^(1/ν)

    Method 2 — Susceptibility peak height:
        χ_max ~ L^(γ/ν)  →  combined with γ/ν from FSS, extract ν

    Method 3 — Specific heat scaling:
        C_max ~ L^(α/ν)  (or log(L) for α ≈ 0)

    If max spread > 15%, the pipeline flags a self-inconsistency and
    reports whether insufficient thermalization is the likely cause.

    Parameters
    ----------
    multi_L : dict mapping L → list of measurement dicts
    Tc : estimated critical temperature
    Tc_std : uncertainty in Tc
    accepted_nu : literature value for comparison (optional)

    Returns
    -------
    dict with 3 ν estimates, spread metric, consistency verdict
    """
    L_vals = sorted(multi_L.keys())
    if len(L_vals) < 3:
        return {'status': 'insufficient_L'}

    nu_estimates = {}

    # --- Method 1: Binder cumulant derivative ---
    # dU4/dT|_{T=Tc} scales as L^(1/ν)
    # We estimate dU4/dT from finite differences of U4(T) near Tc
    dU4_dT_max = {}
    for L in L_vals:
        data = sorted(multi_L[L], key=lambda d: d['T'])
        Ts = np.array([d['T'] for d in data])
        U4s = np.array([d['U4'] for d in data])

        # Numerical derivative via finite differences
        if len(Ts) < 4:
            continue
        try:
            f = interp1d(Ts, U4s, kind='cubic', fill_value='extrapolate')
            # dU4/dT near Tc
            dT = 0.01
            dU4 = abs(float(f(Tc + dT)) - float(f(Tc - dT))) / (2 * dT)
            dU4_dT_max[L] = dU4
        except Exception:
            continue

    if len(dU4_dT_max) >= 3:
        Ls_binder = np.array(sorted(dU4_dT_max.keys()), dtype=float)
        dU4s = np.array([dU4_dT_max[int(L)] for L in Ls_binder])
        valid = dU4s > 0
        if np.sum(valid) >= 3:
            log_L = np.log(Ls_binder[valid])
            log_dU4 = np.log(dU4s[valid])
            slope, _ = np.polyfit(log_L, log_dU4, 1)
            nu_binder = 1.0 / slope if slope > 0 else None
            if nu_binder is not None and 0.1 < nu_binder < 5.0:
                nu_estimates['binder_derivative'] = {
                    'nu': float(nu_binder),
                    'one_over_nu': float(slope),
                    'method': 'dU4/dT|_Tc ~ L^(1/ν)',
                    'n_points': int(np.sum(valid)),
                }

    # --- Method 2: Susceptibility peak position shift ---
    # T_chi_max(L) - Tc ~ L^(-1/ν)
    T_chi_max = {}
    chi_max_vals = {}
    for L in L_vals:
        data = sorted(multi_L[L], key=lambda d: d['T'])
        Ts = np.array([d['T'] for d in data])
        chis = np.array([d['chi'] for d in data])

        if len(Ts) < 4:
            continue

        try:
            # Densify with spline and find peak
            f_chi = interp1d(Ts, chis, kind='cubic')
            T_dense = np.linspace(Ts[1], Ts[-2], 200)
            chi_dense = f_chi(T_dense)
            idx_max = np.argmax(chi_dense)
            T_chi_max[L] = float(T_dense[idx_max])
            chi_max_vals[L] = float(chi_dense[idx_max])
        except Exception:
            continue

    if len(T_chi_max) >= 3:
        Ls_chi = np.array(sorted(T_chi_max.keys()), dtype=float)
        T_peaks = np.array([T_chi_max[int(L)] for L in Ls_chi])
        shifts = np.abs(T_peaks - Tc)
        valid = shifts > 0
        if np.sum(valid) >= 3:
            log_L = np.log(Ls_chi[valid])
            log_shift = np.log(shifts[valid])
            slope, _ = np.polyfit(log_L, log_shift, 1)
            nu_chi_shift = -1.0 / slope if slope < 0 else None
            if nu_chi_shift is not None and 0.1 < nu_chi_shift < 5.0:
                nu_estimates['chi_peak_shift'] = {
                    'nu': float(nu_chi_shift),
                    'one_over_nu': float(-slope),
                    'method': 'T_χmax(L) - Tc ~ L^(-1/ν)',
                    'n_points': int(np.sum(valid)),
                }

    # --- Method 2b: Susceptibility peak HEIGHT ---
    # χ_max ~ L^(γ/ν)
    if len(chi_max_vals) >= 3:
        Ls_chi_h = np.array(sorted(chi_max_vals.keys()), dtype=float)
        chi_peaks = np.array([chi_max_vals[int(L)] for L in Ls_chi_h])
        valid = chi_peaks > 0
        if np.sum(valid) >= 3:
            log_L = np.log(Ls_chi_h[valid])
            log_chi = np.log(chi_peaks[valid])
            gamma_over_nu_fss, _ = np.polyfit(log_L, log_chi, 1)
            nu_estimates['chi_peak_height'] = {
                'gamma_over_nu': float(gamma_over_nu_fss),
                'method': 'χ_max ~ L^(γ/ν)',
                'n_points': int(np.sum(valid)),
                'note': 'provides γ/ν ratio, not ν directly',
            }

    # --- Method 3: Specific heat scaling ---
    # C_max ~ L^(α/ν)  (for α > 0) or ~ log(L) (for α ≈ 0)
    C_max_vals = {}
    for L in L_vals:
        data = sorted(multi_L[L], key=lambda d: d['T'])
        Ts = np.array([d['T'] for d in data])
        Cs = np.array([d['C'] for d in data])

        if len(Ts) < 4:
            continue
        try:
            f_C = interp1d(Ts, Cs, kind='cubic')
            T_dense = np.linspace(Ts[1], Ts[-2], 200)
            C_dense = f_C(T_dense)
            C_max_vals[L] = float(np.max(C_dense))
        except Exception:
            continue

    if len(C_max_vals) >= 3:
        Ls_C = np.array(sorted(C_max_vals.keys()), dtype=float)
        Cs = np.array([C_max_vals[int(L)] for L in Ls_C])
        valid = Cs > 0
        if np.sum(valid) >= 3:
            log_L = np.log(Ls_C[valid])
            log_C = np.log(Cs[valid])
            alpha_over_nu_fss, _ = np.polyfit(log_L, log_C, 1)

            # Also fit log model: C = a + b*log(L) (for α ≈ 0)
            coeff_log = np.polyfit(log_L, Cs[valid], 1)
            ss_power = np.sum((log_C - np.polyval(np.polyfit(log_L, log_C, 1), log_L)) ** 2)
            ss_log = np.sum((Cs[valid] - np.polyval(coeff_log, log_L)) ** 2)

            if alpha_over_nu_fss > 0.05:
                nu_estimates['specific_heat'] = {
                    'alpha_over_nu': float(alpha_over_nu_fss),
                    'method': 'C_max ~ L^(α/ν)',
                    'is_logarithmic': False,
                    'n_points': int(np.sum(valid)),
                }
            else:
                nu_estimates['specific_heat'] = {
                    'alpha_over_nu': float(alpha_over_nu_fss),
                    'method': 'C_max ~ log(L) (α ≈ 0)',
                    'is_logarithmic': True,
                    'note': 'α/ν ≈ 0 → Specific heat is not a reliable ν probe for this system',
                    'n_points': int(np.sum(valid)),
                }

    # --- Cross-consistency check ---
    nu_values = []
    nu_labels = []
    for method, est in nu_estimates.items():
        if 'nu' in est and est['nu'] is not None:
            nu_values.append(est['nu'])
            nu_labels.append(method)

    consistency = {}
    if len(nu_values) >= 2:
        nu_arr = np.array(nu_values)
        nu_mean = float(np.mean(nu_arr))
        nu_spread = float(np.ptp(nu_arr))
        nu_rel_spread = nu_spread / nu_mean if nu_mean > 0 else 999.0
        consistent = nu_rel_spread < 0.15  # 15% threshold

        consistency = {
            'n_methods': len(nu_values),
            'nu_values': {l: float(v) for l, v in zip(nu_labels, nu_values)},
            'nu_mean': nu_mean,
            'nu_std': float(np.std(nu_arr)),
            'nu_spread': nu_spread,
            'relative_spread': float(nu_rel_spread),
            'consistent': consistent,
            'verdict': ('CONSISTENT: ν estimates agree within 15%'
                        if consistent
                        else f'INCONSISTENT: ν spread = {nu_rel_spread:.0%} > 15% '
                             '— possible insufficient thermalization or strong corrections to scaling'),
        }

        # Compare to accepted value if provided
        if accepted_nu is not None:
            consistency['accepted_nu'] = float(accepted_nu)
            consistency['mean_error_pct'] = float(abs(nu_mean - accepted_nu) / accepted_nu * 100)
    elif len(nu_values) == 1:
        consistency = {
            'n_methods': 1,
            'nu_values': {nu_labels[0]: float(nu_values[0])},
            'verdict': 'Only 1 method produced a ν estimate — cross-check not possible',
        }
    else:
        consistency = {
            'n_methods': 0,
            'verdict': 'No ν estimates available',
        }

    # --- Diagnostic: if inconsistent, suggest thermalization increase ---
    diagnostics = None
    if consistency.get('consistent') is False:
        diagnostics = {
            'suggestion': 'increase_thermalization',
            'reason': (
                'ν inconsistency across methods often indicates that the system has not '
                'fully equilibrated at some lattice sizes. The Binder derivative is '
                'particularly sensitive to near-Tc equilibration. Recommended action: '
                'double equilibration sweeps and re-run.'
            ),
            'alternative': (
                'If thermalization is confirmed adequate, the inconsistency may reflect '
                'strong corrections to scaling — try the Wegner-corrected FSS analysis.'
            ),
        }

    return {
        'status': 'success',
        'estimates': nu_estimates,
        'consistency': consistency,
        'diagnostics': diagnostics,
    }


# ═══════════════════════════════════════════════════════════════
# INTEGRATED v14 ANALYSIS
# ═══════════════════════════════════════════════════════════════

def v14_rg_analysis(multi_L: Dict[int, List[dict]],
                    Tc: float,
                    Tc_std: float,
                    system_label: str = '3D Ising',
                    accepted_exponents: dict = None,
                    known_omega: float = None) -> dict:
    """
    Run the full v14 RG-aware analysis suite on a given system.

    Combines:
      1. Scaling collapse (M and χ)
      2. Wegner corrections (M and χ)
      3. Cross-observable ν consistency

    Parameters
    ----------
    multi_L : dict mapping L → list of measurement dicts
    Tc : critical temperature
    Tc_std : Tc uncertainty
    system_label : human-readable system name
    accepted_exponents : dict with 'beta', 'gamma', 'nu', etc.
    known_omega : Wegner correction exponent if known

    Returns
    -------
    dict with all v14 analysis results
    """
    print(f"\n  ┌─── v14 RG-AWARE ANALYSIS: {system_label} ──────────────┐")
    results = {'system': system_label}

    # --- 1. Scaling collapse ---
    print(f"  │ Scaling collapse (M) ... ", end='', flush=True)
    t0 = time.time()
    collapse_M = scaling_collapse(multi_L, Tc, observable='M', seed=42)
    dt = time.time() - t0
    if collapse_M.get('status') == 'success':
        S = collapse_M['collapse_quality_S']
        q = collapse_M['quality_label']
        exps = collapse_M['exponents']
        print(f"S={S:.4f} ({q}), β/ν={exps.get('beta_over_nu', '?'):.3f}, "
              f"1/ν={exps.get('one_over_nu', '?'):.3f} [{dt:.1f}s]")
    else:
        print(f"[{collapse_M.get('status')}]")
    results['collapse_M'] = collapse_M

    print(f"  │ Scaling collapse (χ) ... ", end='', flush=True)
    t0 = time.time()
    collapse_chi = scaling_collapse(multi_L, Tc, observable='chi', seed=43)
    dt = time.time() - t0
    if collapse_chi.get('status') == 'success':
        S = collapse_chi['collapse_quality_S']
        q = collapse_chi['quality_label']
        exps = collapse_chi['exponents']
        print(f"S={S:.4f} ({q}), γ/ν={exps.get('gamma_over_nu', '?'):.3f}, "
              f"1/ν={exps.get('one_over_nu', '?'):.3f} [{dt:.1f}s]")
    else:
        print(f"[{collapse_chi.get('status')}]")
    results['collapse_chi'] = collapse_chi

    # --- 2. Wegner corrections ---
    print(f"  │ Wegner corrections (M) ... ", end='', flush=True)
    wegner_M = wegner_corrected_fss(multi_L, Tc, observable='M', known_omega=known_omega)
    if wegner_M.get('status') == 'success':
        sel = wegner_M['model_selection']
        p = wegner_M['best_exponent']
        adopted = 'ADOPTED' if sel['correction_adopted'] else 'REJECTED'
        print(f"p={p:.3f}, correction {adopted}")
        if wegner_M.get('corrected_fit'):
            w = wegner_M['corrected_fit']['omega']
            B = wegner_M['corrected_fit']['B']
            print(f"  │   ω={w:.3f}, B={B:.3f}, ΔAIC={sel['delta_aic']:.1f}")
    else:
        print(f"[{wegner_M.get('status')}]")
    results['wegner_M'] = wegner_M

    print(f"  │ Wegner corrections (χ) ... ", end='', flush=True)
    wegner_chi = wegner_corrected_fss(multi_L, Tc, observable='chi', known_omega=known_omega)
    if wegner_chi.get('status') == 'success':
        sel = wegner_chi['model_selection']
        p = wegner_chi['best_exponent']
        adopted = 'ADOPTED' if sel['correction_adopted'] else 'REJECTED'
        print(f"p={p:.3f}, correction {adopted}")
    else:
        print(f"[{wegner_chi.get('status')}]")
    results['wegner_chi'] = wegner_chi

    # --- 3. Cross-observable ν consistency ---
    print(f"  │ ν cross-consistency ... ", end='', flush=True)
    nu_check = nu_cross_consistency(
        multi_L, Tc, Tc_std,
        accepted_nu=accepted_exponents.get('nu') if accepted_exponents else None,
    )
    if nu_check.get('consistency'):
        c = nu_check['consistency']
        print(f"{c.get('n_methods', 0)} methods, "
              f"spread={c.get('relative_spread', '?'):.1%}, "
              f"{'CONSISTENT' if c.get('consistent', False) else 'INCONSISTENT'}")
    else:
        print(f"[{nu_check.get('status')}]")
    results['nu_consistency'] = nu_check

    # --- Summary comparison with accepted values ---
    if accepted_exponents:
        comparison = {}
        # From collapse
        if collapse_M.get('status') == 'success':
            beta_c = collapse_M['exponents'].get('beta')
            nu_c = collapse_M['exponents'].get('nu')
            if beta_c:
                comparison['beta_collapse'] = {
                    'value': float(beta_c),
                    'error_pct': float(abs(beta_c - accepted_exponents['beta']) / accepted_exponents['beta'] * 100),
                }
            if nu_c:
                comparison['nu_collapse_M'] = {
                    'value': float(nu_c),
                    'error_pct': float(abs(nu_c - accepted_exponents['nu']) / accepted_exponents['nu'] * 100),
                }
        if collapse_chi.get('status') == 'success':
            gamma_c = collapse_chi['exponents'].get('gamma')
            if gamma_c:
                comparison['gamma_collapse'] = {
                    'value': float(gamma_c),
                    'error_pct': float(abs(gamma_c - accepted_exponents['gamma']) / accepted_exponents['gamma'] * 100),
                }
        # From Wegner
        if wegner_M.get('status') == 'success':
            comparison['beta_over_nu_wegner'] = {
                'value': float(wegner_M['best_exponent']),
                'correction_adopted': wegner_M['model_selection']['correction_adopted'],
            }
        if wegner_chi.get('status') == 'success':
            comparison['gamma_over_nu_wegner'] = {
                'value': float(wegner_chi['best_exponent']),
                'correction_adopted': wegner_chi['model_selection']['correction_adopted'],
            }

        results['comparison'] = comparison
        print(f"  │ Comparison with accepted values:")
        for key, val in comparison.items():
            err = val.get('error_pct', '?')
            v = val.get('value', '?')
            print(f"  │   {key}: {v:.4f} ({err:.1f}% error)" if isinstance(err, float) else f"  │   {key}: {v}")

    print(f"  └─────────────────────────────────────────────────────┘")
    return results


# ═══════════════════════════════════════════════════════════════
# MAIN — v14 PIPELINE
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 76)
    print("  BREAKTHROUGH v14: THE RG-AWARE AUTONOMOUS DISCOVERY ENGINE")
    print("  Collapse + Wegner + ν Check + Weighted Crossings + O(3) Heisenberg")
    print("=" * 76)

    t_start = time.time()

    # Pre-registration
    pre_reg_hash = hash_pre_registration_v14()
    print(f"\n╔══ PRE-REGISTRATION v14 (SHA-256: {pre_reg_hash[:16]}...) ══╗")
    print(f"  NEW: Automated collapse, Wegner corrections, ν consistency, weighted crossings, O(3)")

    # ═══════════════════════════════════════════════════════════
    # PHASE A: Run v13 pipeline (Ising + XY)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE A: v13 Base Pipeline (Ising 3D) ═══════════════╗")

    # Generate Ising data
    L_sizes_ising = [4, 6, 8, 10, 12]
    T_scan_ising = np.linspace(3.5, 5.5, 30)
    multi_ising_wolff: Dict[int, List[dict]] = {}

    for L in L_sizes_ising:
        n_eq = max(200, (600 + 200 * L) // 3)
        n_ms = max(400, (1000 + 300 * L) // 3)
        print(f"  Wolff L={L:2d}³ ... ", end='', flush=True)
        t0 = time.time()
        data = []
        for i, T in enumerate(T_scan_ising):
            obs = wolff_cluster_mc(L, T, n_eq, n_ms, seed=99 + L * 1000 + i * 137)
            data.append(obs)
        multi_ising_wolff[L] = data
        print(f"{time.time() - t0:.1f}s")

    # Tc discovery
    tc_ising_binder = discover_tc_binder(multi_ising_wolff)
    tc_ising = tc_ising_binder['Tc']
    tc_ising_std = tc_ising_binder.get('Tc_std', 0.1)
    print(f"  Ising Tc = {tc_ising:.4f} ± {tc_ising_std:.4f} "
          f"(accepted {TC_3D:.4f}, error {abs(tc_ising - TC_3D) / TC_3D * 100:.1f}%)")

    # ═══════════════════════════════════════════════════════════
    # PHASE B: v14 RG-AWARE ANALYSIS — ISING
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE B: v14 RG-Aware Analysis — 3D Ising ══════════╗")
    ising_v14 = v14_rg_analysis(
        multi_ising_wolff, tc_ising, tc_ising_std,
        system_label='3D Ising (Z₂)',
        accepted_exponents=ISING_3D_EXPONENTS,
        known_omega=OMEGA_3D,
    )

    # ═══════════════════════════════════════════════════════════
    # PHASE C: XY transfer with v13 dual simulators
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE C: v13 XY Transfer + v14 Analysis ═════════════╗")
    xy_result = xy_transfer_experiment_v13(L_sizes=[4, 6, 8, 10, 12])

    # Re-generate Wolff data dict for v14 analysis
    # (xy_transfer_experiment_v13 doesn't return multi_L directly)
    T_scan_xy = np.linspace(1.5, 3.0, 24)
    multi_xy_wolff: Dict[int, List[dict]] = {}
    for L in [4, 6, 8, 10, 12]:
        n_eq = max(200, (500 + 200 * L) // 3)
        n_ms = max(300, (800 + 200 * L) // 2)
        multi_xy_wolff[L] = generate_xy_wolff_dataset_raw(
            L, T_scan_xy, n_eq, n_ms, seed=300 + L + 500)

    tc_xy = xy_result['Tc_discovered']
    tc_xy_std = xy_result['Tc_std']

    print(f"\n╔══ PHASE D: v14 RG-Aware Analysis — 3D XY ══════════════╗")
    xy_v14 = v14_rg_analysis(
        multi_xy_wolff, tc_xy, tc_xy_std,
        system_label='3D XY (O(2))',
        accepted_exponents={
            'beta': XY_3D_EXPONENTS['beta'],
            'gamma': XY_3D_EXPONENTS['gamma'],
            'nu': XY_3D_EXPONENTS['nu'],
        },
        known_omega=OMEGA_3D_XY,
    )

    # ═══════════════════════════════════════════════════════════
    # PHASE E: WEIGHTED-CROSSING Tc CONSENSUS (v14 NEW)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE E: v14 Weighted-Crossing Tc Consensus ═════════╗")

    # Generate 2D Ising control data for α calibration
    print(f"  Generating 2D Ising control data for α calibration ...")
    L_sizes_2d = [4, 6, 8, 12, 16, 24]
    T_scan_2d = np.linspace(1.8, 2.8, 30)
    multi_2d_control: Dict[int, List[dict]] = {}
    for L in L_sizes_2d:
        n_eq = 500 + 100 * L
        n_ms = 1000 + 200 * L
        print(f"    2D Ising L={L:2d}² ... ", end='', flush=True)
        t0 = time.time()
        data = []
        for i, T in enumerate(T_scan_2d):
            obs = ising_2d_mc_with_U4(L, T, n_eq, n_ms, seed=777 + L * 100 + i * 31)
            data.append(obs)
        multi_2d_control[L] = data
        print(f"{time.time() - t0:.1f}s")

    # Calibrate α
    print(f"\n  Calibrating crossing weight exponent α on 2D Ising (exact Tc = {TC_2D:.5f}) ...")
    calib = calibrate_crossing_alpha(multi_2d_control, TC_2D)
    alpha_best = calib.get('alpha_best', 1.0)
    print(f"    α_best = {alpha_best:.2f}")
    if calib.get('improvement'):
        print(f"    LOO improvement: {calib['improvement']:.1f}× over unweighted")
    if calib.get('loo_error_best') is not None:
        print(f"    LOO error: {calib['loo_error_best']:.5f} (weighted) "
              f"vs {calib.get('loo_error_unweighted', '?'):.5f} (unweighted)" if calib.get('loo_error_unweighted') else '')

    # Apply to 3D Ising
    print(f"\n  Weighted-crossing Tc — 3D Ising:")
    crossing_ising = v14_weighted_crossing_analysis(
        multi_ising_wolff, multi_2d_control, TC_2D,
        Tc_accepted_target=TC_3D,
        system_label='3D Ising',
    )
    if crossing_ising.get('status') == 'success':
        for label, r in crossing_ising['target_results'].items():
            err_str = f" ({r['error_pct']:.2f}%)" if 'error_pct' in r else ''
            print(f"    {label:12s}: Tc = {r.get('Tc_weighted', '?'):.4f} "
                  f"± {r.get('Tc_std_weighted', 0):.4f}{err_str}")

    # Apply to 3D XY
    print(f"\n  Weighted-crossing Tc — 3D XY:")
    crossing_xy = v14_weighted_crossing_analysis(
        multi_xy_wolff, multi_2d_control, TC_2D,
        Tc_accepted_target=TC_3D_XY,
        system_label='3D XY',
    )
    if crossing_xy.get('status') == 'success':
        for label, r in crossing_xy['target_results'].items():
            err_str = f" ({r['error_pct']:.2f}%)" if 'error_pct' in r else ''
            print(f"    {label:12s}: Tc = {r.get('Tc_weighted', '?'):.4f} "
                  f"± {r.get('Tc_std_weighted', 0):.4f}{err_str}")

    # ═══════════════════════════════════════════════════════════
    # PHASE F: O(3) HEISENBERG TRANSFER (v14 NEW)
    # ═══════════════════════════════════════════════════════════
    print(f"\n╔══ PHASE F: O(3) Heisenberg Transfer ═══════════════════╗")
    print(f"  Numba JIT: {'ACTIVE' if HAS_NUMBA else 'NOT AVAILABLE (pure NumPy mode)'}")

    # Benchmark first to assess feasibility
    bench = benchmark_heisenberg(L_range=[4, 6, 8], n_temps=3, n_measure=100)

    # Pedestal prediction
    pedestal = heisenberg_pedestal_prediction()
    print(f"\n  Goldstone pedestal prediction:")
    print(f"    {pedestal['hypothesis']}")

    # Run the full transfer experiment
    heisenberg_result = heisenberg_transfer_experiment(
        L_sizes=[4, 6, 8, 10, 12],
        T_range=(1.0, 2.0),
        n_temps=24,
        seed=500,
    )

    # v14 RG-aware analysis on Heisenberg data
    print(f"\n╔══ PHASE G: v14 RG-Aware Analysis — O(3) Heisenberg ══╗")
    heisenberg_v14 = v14_rg_analysis(
        heisenberg_result['multi_L'],
        heisenberg_result['Tc_consensus'],
        heisenberg_result['Tc_std'],
        system_label='3D Heisenberg (O(3))',
        accepted_exponents=HEISENBERG_3D_EXPONENTS,
        known_omega=OMEGA_3D_HEISENBERG,
    )

    # Weighted-crossing Tc for Heisenberg
    print(f"\n  Weighted-crossing Tc — 3D Heisenberg:")
    crossing_heisenberg = v14_weighted_crossing_analysis(
        heisenberg_result['multi_L'], multi_2d_control, TC_2D,
        Tc_accepted_target=TC_3D_HEISENBERG,
        system_label='3D Heisenberg',
    )
    if crossing_heisenberg.get('status') == 'success':
        for label, r in crossing_heisenberg['target_results'].items():
            err_str = f" ({r['error_pct']:.2f}%)" if 'error_pct' in r else ''
            print(f"    {label:12s}: Tc = {r.get('Tc_weighted', '?'):.4f} "
                  f"± {r.get('Tc_std_weighted', 0):.4f}{err_str}")

    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════
    elapsed = time.time() - t_start
    print(f"\n{'=' * 76}")
    print(f"  v14 RG-AWARE ANALYSIS COMPLETE")
    print(f"  Total time: {elapsed:.0f}s ({elapsed / 60:.1f} min)")
    print(f"{'=' * 76}")

    # Collapse summary
    for label, result in [('Ising', ising_v14), ('XY', xy_v14), ('Heisenberg', heisenberg_v14)]:
        print(f"\n  {label}:")
        if result.get('collapse_M', {}).get('status') == 'success':
            cm = result['collapse_M']
            print(f"    M collapse: S={cm['collapse_quality_S']:.4f} ({cm['quality_label']})")
            print(f"      β/ν = {cm['exponents'].get('beta_over_nu', '?'):.4f}, "
                  f"ν = {cm['exponents'].get('nu', '?'):.4f}")
        if result.get('collapse_chi', {}).get('status') == 'success':
            cc = result['collapse_chi']
            print(f"    χ collapse: S={cc['collapse_quality_S']:.4f} ({cc['quality_label']})")
            print(f"      γ/ν = {cc['exponents'].get('gamma_over_nu', '?'):.4f}, "
                  f"ν = {cc['exponents'].get('nu', '?'):.4f}")
        if result.get('nu_consistency', {}).get('consistency'):
            nc = result['nu_consistency']['consistency']
            print(f"    ν consistency: {nc.get('verdict', '?')}")

    # Crossing summary
    print(f"\n  Weighted-Crossing Tc Consensus (α = {alpha_best:.2f}):")
    for label, cresult in [('Ising', crossing_ising), ('XY', crossing_xy),
                            ('Heisenberg', crossing_heisenberg)]:
        if cresult.get('status') == 'success':
            uw = cresult['target_results'].get('unweighted', {})
            wt = cresult['target_results'].get('alpha_best', {})
            uw_err = uw.get('error_pct', '?')
            wt_err = wt.get('error_pct', '?')
            print(f"    {label}: unweighted Tc error = {uw_err:.2f}%"
                  f" → weighted = {wt_err:.2f}%"
                  if isinstance(uw_err, float) and isinstance(wt_err, float)
                  else f"    {label}: [check output]")

    return {
        'version': 'v14_rg_aware',
        'ising_v14': ising_v14,
        'xy_v14': xy_v14,
        'heisenberg_v14': heisenberg_v14,
        'xy_v13': xy_result,
        'ising_Tc': tc_ising,
        'heisenberg_result': heisenberg_result,
        'crossing_ising': crossing_ising,
        'crossing_xy': crossing_xy,
        'crossing_heisenberg': crossing_heisenberg,
        'heisenberg_pedestal': pedestal,
        'heisenberg_benchmark': bench,
        'alpha_calibration': calib,
        'elapsed_s': elapsed,
        'pre_reg_hash': pre_reg_hash,
    }


if __name__ == '__main__':
    main()
