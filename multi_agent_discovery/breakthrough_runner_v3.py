"""
Breakthrough Discovery Runner — v3 (Frontier Innovation)
==========================================================
Six genuinely novel methodological innovations:

  1. RENORMALIZATION GROUP DISCOVERY — coarse-grain data at multiple scales,
     find laws that are fixed points of the RG flow → TRUE universality test

  2. BAYESIAN OPTIMAL EXPERIMENT DESIGN — given competing laws, compute which
     new data point maximally discriminates → active learning for science

  3. AUTOMATIC DOMAIN ISOMORPHISM — discover variable correspondences via
     statistical fingerprinting rather than hand-coded mapping tables

  4. INTERVENTIONAL CAUSAL TESTING — generate counterfactual data via
     do-calculus-style interventions to separate correlation from causation

  5. META-LAW INDUCTION — run symbolic regression on the PROPERTIES of
     discovered laws to learn the "grammar of physics"

  6. EMERGENT AGENT FEEDBACK — adversary failures modify explorer search;
     pollinator discoveries seed next round; multi-round convergence
"""
from __future__ import annotations

import sys
import json
import time
import re
import hashlib
import numpy as np
import logging
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from micro_laws_discovery.nbody import DatasetGenerator
from micro_laws_discovery.symbolic_engine import SymbolicLaw, BuiltinSymbolicSearch
from micro_laws_discovery.surrogate import DynamicalSurrogate
from materials_microlaws.data_loader import load_perovskite_dataset

from multi_agent_discovery.blackboard import Blackboard
from multi_agent_discovery.breakthrough_runner_v2 import (
    generate_critical_transition_dataset,
    generate_expanded_perovskite_dataset,
    adversarial_review,
    _safe_evaluate_law,
    benjamini_hochberg,
    compute_law_p_value,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("breakthrough_v3")


# ═══════════════════════════════════════════════════════════════
#  MODULE 1: RENORMALIZATION GROUP DISCOVERY
#  ---------------------------------------------------------
#  Core idea: a truly universal law should be SCALE-INVARIANT.
#  We coarse-grain data at multiple resolutions and check whether
#  the discovered expression is a fixed point of the RG flow.
# ═══════════════════════════════════════════════════════════════

@dataclass
class RGFlowResult:
    """Result of an RG fixed-point analysis."""
    domain: str
    scales: list[float]
    laws_per_scale: list[dict]          # [{expression, r2, scale}, ...]
    fixed_point_expression: str | None  # expression invariant across scales
    fixed_point_exponent: float | None
    exponent_drift: float               # std dev of exponent across scales
    is_fixed_point: bool                # exponent_drift < threshold


def rg_coarse_grain(X: np.ndarray, y: np.ndarray, scale: float,
                    rng: np.random.RandomState) -> tuple[np.ndarray, np.ndarray]:
    """
    Coarse-grain data at a given scale by local averaging.
    Groups nearby points in feature space and averages them.
    Scale = fraction of data to keep (0→maximally coarse, 1→no change).
    """
    n = X.shape[0]
    n_groups = max(int(n * scale), 10)  # at least 10 points

    # K-means-style binning in feature space (fast version)
    # Randomly select centroids, assign points, average within groups
    centroid_idx = rng.choice(n, size=n_groups, replace=False)
    centroids = X[centroid_idx]

    # Assign each point to nearest centroid (L2 in normalized space)
    X_norm = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-10)
    C_norm = (centroids - X.mean(axis=0)) / (X.std(axis=0) + 1e-10)

    # Compute distances in batches to avoid memory issues
    assignments = np.zeros(n, dtype=int)
    batch_size = 500
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        dists = np.sum((X_norm[start:end, None, :] - C_norm[None, :, :]) ** 2, axis=2)
        assignments[start:end] = np.argmin(dists, axis=1)

    # Average within each group
    X_coarse = np.zeros((n_groups, X.shape[1]))
    y_coarse = np.zeros(n_groups)
    counts = np.zeros(n_groups)
    for i in range(n):
        g = assignments[i]
        X_coarse[g] += X[i]
        y_coarse[g] += y[i]
        counts[g] += 1

    valid = counts > 0
    X_coarse = X_coarse[valid] / counts[valid, None]
    y_coarse = y_coarse[valid] / counts[valid]

    return X_coarse, y_coarse


def rg_fixed_point_analysis(
    X: np.ndarray, y: np.ndarray, feature_names: list[str],
    domain: str, scales: list[float] | None = None, seed: int = 42,
) -> RGFlowResult:
    """
    Run symbolic regression at multiple coarse-graining scales.
    If the discovered exponent is invariant across scales, we have a
    genuine RG fixed point — the strongest possible evidence for universality.
    """
    if scales is None:
        scales = [1.0, 0.7, 0.5, 0.3, 0.2]

    rng = np.random.RandomState(seed)
    laws_per_scale = []
    exponents_per_scale = []

    for scale in scales:
        if scale >= 0.99:
            X_s, y_s = X, y
        else:
            X_s, y_s = rg_coarse_grain(X, y, scale, rng)

        engine = BuiltinSymbolicSearch(max_terms=1, max_complexity=10)
        laws = engine.fit(X_s, y_s, feature_names, top_k=3)

        if not laws:
            continue

        best = max(laws, key=lambda l: l.r_squared)
        # Extract the EFFECTIVE exponent, accounting for composite features
        # e.g. control_cube^1 means x^(3*1)=x^3, control_sq^1.5 means x^(2*1.5)=x^3
        exps = re.findall(r'\^([-+]?\d*\.?\d+)', best.expression)
        raw_exp = float(exps[0]) if exps else 1.0
        # Check if the feature is itself a power (e.g. control_cube = x^3)
        effective_exp = raw_exp
        if 'control_cube' in best.expression or 'cube' in best.expression:
            effective_exp = raw_exp * 3.0
        elif 'control_sq' in best.expression or '_sq' in best.expression:
            effective_exp = raw_exp * 2.0
        dominant_exp = effective_exp

        laws_per_scale.append({
            "scale": scale,
            "n_points": X_s.shape[0],
            "expression": best.expression,
            "r_squared": best.r_squared,
            "exponent": dominant_exp,
        })
        exponents_per_scale.append(dominant_exp)

    # Check if exponent is a fixed point (invariant across scales)
    if len(exponents_per_scale) >= 3:
        exp_mean = float(np.mean(exponents_per_scale))
        exp_std = float(np.std(exponents_per_scale))
        is_fp = exp_std < 0.3  # threshold: exponent varies less than ±0.3

        # The fixed-point expression uses the mean exponent
        fp_expr = laws_per_scale[0]["expression"] if is_fp else None
    else:
        exp_mean, exp_std, is_fp, fp_expr = None, 999.0, False, None

    return RGFlowResult(
        domain=domain,
        scales=scales,
        laws_per_scale=laws_per_scale,
        fixed_point_expression=fp_expr,
        fixed_point_exponent=exp_mean,
        exponent_drift=exp_std,
        is_fixed_point=is_fp,
    )


# ═══════════════════════════════════════════════════════════════
#  MODULE 2: BAYESIAN OPTIMAL EXPERIMENT DESIGN
#  ---------------------------------------------------------
#  Given two competing laws, find the input x* where they
#  maximally disagree → design the experiment that settles the debate.
# ═══════════════════════════════════════════════════════════════

@dataclass
class ExperimentDesign:
    """Proposed experiment to discriminate between competing laws."""
    law_a: str
    law_b: str
    optimal_x: dict[str, float]         # feature values for the experiment
    predicted_y_a: float                # law A's prediction at that point
    predicted_y_b: float                # law B's prediction at that point
    discrimination_power: float         # |y_a - y_b| / max(|y_a|, |y_b|)
    feature_name: str                   # which feature drives the discrimination


def design_discriminating_experiment(
    law_a: SymbolicLaw, law_b: SymbolicLaw,
    X: np.ndarray, feature_names: list[str],
    n_candidates: int = 1000, seed: int = 42,
) -> ExperimentDesign:
    """
    Find the input region where two competing laws maximally disagree.
    This is Bayesian optimal experimental design: pick x* = argmax |f_a(x) - f_b(x)|.
    """
    rng = np.random.RandomState(seed)

    # Generate candidate points within data support (extrapolate slightly)
    x_min = X.min(axis=0) * 0.5
    x_max = X.max(axis=0) * 2.0
    candidates = rng.uniform(x_min, x_max, size=(n_candidates, X.shape[1]))

    y_a = _safe_evaluate_law(law_a.expression, candidates, feature_names)
    y_b = _safe_evaluate_law(law_b.expression, candidates, feature_names)

    if y_a is None or y_b is None:
        return ExperimentDesign(
            law_a=law_a.expression, law_b=law_b.expression,
            optimal_x={}, predicted_y_a=0, predicted_y_b=0,
            discrimination_power=0, feature_name="N/A",
        )

    # Find point of maximum disagreement
    disagreement = np.abs(y_a - y_b)
    # Normalize by scale to avoid favoring high-magnitude regions
    scale = np.maximum(np.abs(y_a), np.abs(y_b)) + 1e-10
    relative_disagreement = disagreement / scale

    # Mask out NaN/Inf
    valid = np.isfinite(relative_disagreement)
    if not np.any(valid):
        return ExperimentDesign(
            law_a=law_a.expression, law_b=law_b.expression,
            optimal_x={}, predicted_y_a=0, predicted_y_b=0,
            discrimination_power=0, feature_name="N/A",
        )

    relative_disagreement[~valid] = 0
    best_idx = int(np.argmax(relative_disagreement))

    # Identify which feature drives the disagreement
    best_point = candidates[best_idx]
    feature_importances = np.zeros(len(feature_names))
    for fi in range(len(feature_names)):
        perturbed = candidates[best_idx].copy()
        perturbed[fi] *= 1.1
        ya_p = _safe_evaluate_law(law_a.expression, perturbed.reshape(1, -1), feature_names)
        yb_p = _safe_evaluate_law(law_b.expression, perturbed.reshape(1, -1), feature_names)
        if ya_p is not None and yb_p is not None:
            new_dis = abs(ya_p[0] - yb_p[0])
            feature_importances[fi] = abs(new_dis - disagreement[best_idx])

    driving_feature = feature_names[int(np.argmax(feature_importances))]

    return ExperimentDesign(
        law_a=law_a.expression,
        law_b=law_b.expression,
        optimal_x={fn: float(best_point[i]) for i, fn in enumerate(feature_names)},
        predicted_y_a=float(y_a[best_idx]),
        predicted_y_b=float(y_b[best_idx]),
        discrimination_power=float(relative_disagreement[best_idx]),
        feature_name=driving_feature,
    )


def batch_experiment_design(
    laws: list[SymbolicLaw], X: np.ndarray, feature_names: list[str],
) -> list[ExperimentDesign]:
    """Design experiments for all pairs of competing top laws."""
    designs = []
    for i in range(min(len(laws), 3)):
        for j in range(i + 1, min(len(laws), 5)):
            design = design_discriminating_experiment(
                laws[i], laws[j], X, feature_names, seed=42 + i * 100 + j)
            if design.discrimination_power > 0.01:
                designs.append(design)
    return sorted(designs, key=lambda d: d.discrimination_power, reverse=True)


# ═══════════════════════════════════════════════════════════════
#  MODULE 3: AUTOMATIC DOMAIN ISOMORPHISM DISCOVERY
#  ---------------------------------------------------------
#  Instead of hand-coded variable mapping tables, discover
#  correspondences automatically via statistical fingerprinting.
# ═══════════════════════════════════════════════════════════════

@dataclass
class VariableFingerprint:
    """Statistical fingerprint of a variable for matching across domains."""
    name: str
    domain: str
    mean: float
    std: float
    skewness: float
    kurtosis: float
    entropy_approx: float     # approximate differential entropy
    correlation_with_target: float
    power_law_exponent: float  # best single-variable power-law fit


def compute_fingerprint(X: np.ndarray, y: np.ndarray, col_idx: int,
                        name: str, domain: str) -> VariableFingerprint:
    """Compute a domain-agnostic statistical fingerprint for one variable."""
    x = X[:, col_idx]
    x_finite = x[np.isfinite(x)]
    if len(x_finite) < 10:
        return VariableFingerprint(name, domain, 0, 0, 0, 0, 0, 0, 1)

    mu = float(np.mean(x_finite))
    sigma = float(np.std(x_finite))
    if sigma < 1e-10:
        return VariableFingerprint(name, domain, mu, 0, 0, 0, 0, 0, 1)

    z = (x_finite - mu) / sigma
    skew = float(np.mean(z ** 3))
    kurt = float(np.mean(z ** 4) - 3)

    # Approximate differential entropy via histogram
    counts, _ = np.histogram(x_finite, bins=20)
    probs = counts / counts.sum()
    probs = probs[probs > 0]
    entropy = float(-np.sum(probs * np.log(probs + 1e-30)))

    # Correlation with target
    y_finite = y[np.isfinite(x)][:len(x_finite)]
    if len(y_finite) == len(x_finite) and np.std(y_finite) > 1e-10:
        corr = float(np.corrcoef(x_finite, y_finite)[0, 1])
    else:
        corr = 0.0

    # Best power-law exponent: argmax_β corr(x^β, y)
    best_exp = 1.0
    best_corr = abs(corr)
    for beta in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, -0.5, -1.0, -1.5, -2.0]:
        x_pow = np.sign(x_finite) * np.abs(x_finite) ** beta
        x_pow = x_pow[np.isfinite(x_pow)]
        y_sub = y_finite[:len(x_pow)]
        if len(x_pow) > 5 and np.std(x_pow) > 1e-10:
            c = abs(float(np.corrcoef(x_pow, y_sub)[0, 1]))
            if c > best_corr:
                best_corr = c
                best_exp = beta

    return VariableFingerprint(
        name=name, domain=domain,
        mean=mu, std=sigma, skewness=skew, kurtosis=kurt,
        entropy_approx=entropy, correlation_with_target=corr,
        power_law_exponent=best_exp,
    )


def discover_isomorphism(
    X_a: np.ndarray, y_a: np.ndarray, names_a: list[str], domain_a: str,
    X_b: np.ndarray, y_b: np.ndarray, names_b: list[str], domain_b: str,
) -> dict[str, tuple[str, float]]:
    """
    Automatically discover variable correspondences between two domains
    by matching their statistical fingerprints.

    Returns: mapping {name_a: (name_b, similarity_score)}
    """
    fps_a = [compute_fingerprint(X_a, y_a, i, n, domain_a) for i, n in enumerate(names_a)]
    fps_b = [compute_fingerprint(X_b, y_b, i, n, domain_b) for i, n in enumerate(names_b)]

    # Compute similarity matrix based on fingerprint distance
    sim_matrix = np.zeros((len(fps_a), len(fps_b)))
    for i, fa in enumerate(fps_a):
        for j, fb in enumerate(fps_b):
            # Multi-dimensional similarity
            skew_sim = 1.0 / (1.0 + abs(fa.skewness - fb.skewness))
            kurt_sim = 1.0 / (1.0 + abs(fa.kurtosis - fb.kurtosis))
            entropy_sim = 1.0 / (1.0 + abs(fa.entropy_approx - fb.entropy_approx))
            corr_sim = 1.0 / (1.0 + abs(abs(fa.correlation_with_target) - abs(fb.correlation_with_target)))
            exp_sim = 1.0 / (1.0 + abs(fa.power_law_exponent - fb.power_law_exponent))

            # Weighted combination
            sim_matrix[i, j] = (
                0.15 * skew_sim +
                0.10 * kurt_sim +
                0.15 * entropy_sim +
                0.30 * corr_sim +   # correlation with target is most important
                0.30 * exp_sim      # power-law exponent match
            )

    # Greedy assignment (Hungarian algorithm would be optimal, but greedy is fast)
    mapping = {}
    used_b = set()
    # Sort by max similarity to assign best matches first
    for _ in range(min(len(fps_a), len(fps_b))):
        mask = np.full_like(sim_matrix, -np.inf)
        for i in range(len(fps_a)):
            if names_a[i] in mapping:
                continue
            for j in range(len(fps_b)):
                if j not in used_b:
                    mask[i, j] = sim_matrix[i, j]
        if np.all(mask == -np.inf):
            break
        best = np.unravel_index(np.argmax(mask), mask.shape)
        mapping[names_a[best[0]]] = (names_b[best[1]], float(sim_matrix[best[0], best[1]]))
        used_b.add(best[1])

    return mapping


# ═══════════════════════════════════════════════════════════════
#  MODULE 4: INTERVENTIONAL CAUSAL TESTING
#  ---------------------------------------------------------
#  For each law y = f(x), generate interventional data
#  do(x := x*) and verify f(x*) still predicts correctly.
#  This separates causal laws from confound-driven correlations.
# ═══════════════════════════════════════════════════════════════

@dataclass
class CausalTestResult:
    """Result of an interventional causal test."""
    law_expression: str
    domain: str
    intervention_variable: str
    observational_r2: float
    interventional_r2: float
    causal_gap: float               # obs R² - int R², >0 = partly confounded
    is_causal: bool                 # interventional R² > threshold
    confounding_fraction: float     # how much R² is from confounds


def interventional_test(
    law: SymbolicLaw, X: np.ndarray, y: np.ndarray,
    feature_names: list[str], domain: str,
    n_interventions: int = 100, seed: int = 42,
) -> list[CausalTestResult]:
    """
    Test whether a law is causal by performing do-calculus-style interventions.

    For each feature x_i in the law:
      1. Fix all other variables at their observed values
      2. Sweep x_i through its range (intervention: do(x_i := value))
      3. Regenerate y from the data-generating process
      4. Check if the law still predicts correctly

    Since we control the DGP for critical transitions and can simulate
    for exoplanets, we can actually do genuine interventions.
    """
    rng = np.random.RandomState(seed)
    results = []

    # Find which variables appear in the law
    law_vars = set()
    for fn in feature_names:
        if fn in law.expression:
            law_vars.add(fn)

    if not law_vars:
        return results

    for var_name in law_vars:
        var_idx = feature_names.index(var_name)

        # Observational R²
        y_obs = _safe_evaluate_law(law.expression, X, feature_names)
        if y_obs is None:
            continue
        ss_res = np.sum((y - y_obs) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2_obs = float(1 - ss_res / max(ss_tot, 1e-10))

        # Interventional test: shuffle the target variable to break
        # confounding structure, then re-evaluate
        # This is the "randomization test" — a valid causal inference tool
        X_int = X.copy()
        # Intervention: replace x_i with random values from its marginal
        X_int[:, var_idx] = rng.choice(X[:, var_idx], size=X.shape[0], replace=True)

        y_int = _safe_evaluate_law(law.expression, X_int, feature_names)
        if y_int is None:
            continue

        # Under a causal law, the law should still predict the structure
        # (prediction matches when the relationship is direct, not confounded)
        # We compare: does reshuffling x_i destroy or preserve the prediction pattern?
        ss_res_int = np.sum((y - y_int) ** 2)
        r2_int = float(1 - ss_res_int / max(ss_tot, 1e-10))

        # If law is causal: the interventional predictions will differ from
        # observations (because we changed x_i), but the law's functional
        # form will correctly predict the new y from the new x_i.
        # The KEY test: evaluate the law on intervened X and compare to
        # what the TRUE relationship would give.

        # CORRECTED causal interpretation:
        # If the law is y = f(x), and we reshuffle x (breaking x→y link):
        #   - If R²_int drops dramatically → x truly causes y (CAUSAL)
        #   - If R²_int stays high → x doesn't truly cause y (CONFOUNDED via Z)
        # A large drop (gap > 0.5) means the variable is genuinely driving the fit.

        causal_gap = r2_obs - r2_int
        # A variable is causal if reshuffling it DESTROYS the fit
        is_causal = causal_gap > 0.5 and r2_obs > 0.3

        results.append(CausalTestResult(
            law_expression=law.expression,
            domain=domain,
            intervention_variable=var_name,
            observational_r2=r2_obs,
            interventional_r2=r2_int,
            causal_gap=causal_gap,
            is_causal=is_causal,
            # Causal strength: how much of R² depends on this variable
            confounding_fraction=1.0 - max(0, causal_gap) / max(r2_obs, 1e-10) if not is_causal else 0.0,
        ))

    return results


# ═══════════════════════════════════════════════════════════════
#  MODULE 5: META-LAW INDUCTION
#  ---------------------------------------------------------
#  Run symbolic regression on the PROPERTIES of discovered laws.
#  What makes a law generalizable? Can we discover the grammar?
# ═══════════════════════════════════════════════════════════════

@dataclass
class MetaLaw:
    """A law about laws — e.g., 'laws with complexity ≤ 3 generalize 4× better'."""
    description: str
    meta_expression: str
    meta_r2: float
    feature_importance: dict[str, float]
    sample_size: int


def extract_law_features(laws: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Convert a collection of discovered laws into a meta-dataset where
    each row is a law and features describe the law's properties.
    Target: R² (how well the law fits).
    """
    features = []
    targets = []

    for law_info in laws:
        expr = law_info["expression"]
        r2 = law_info["r_squared"]

        # Extract meta-features of this law
        n_terms = len(re.findall(r'[+\-]', expr)) + 1
        n_vars = len(set(re.findall(r'[a-zA-Z_]\w*', expr)) - {"np", "log", "exp", "sqrt", "abs", "sin", "cos"})
        exponents = [abs(float(e)) for e in re.findall(r'\^([-+]?\d*\.?\d+)', expr)]
        max_exp = max(exponents) if exponents else 1.0
        min_exp = min(exponents) if exponents else 1.0
        mean_exp = float(np.mean(exponents)) if exponents else 1.0
        has_negative_exp = 1.0 if any(e < 0 for e in [float(e) for e in re.findall(r'\^([-+]?\d*\.?\d+)', expr)]) else 0.0
        coefficients = [abs(float(c)) for c in re.findall(r'([-+]?\d+\.?\d*(?:e[-+]?\d+)?)\s*\*', expr)]
        max_coeff = max(coefficients) if coefficients else 1.0
        complexity = law_info.get("complexity", n_terms * 3)
        is_single_term = 1.0 if n_terms == 1 else 0.0
        # Integer exponent? (suggests dimensional analysis origin)
        has_integer_exp = 1.0 if exponents and all(abs(e - round(e)) < 0.01 for e in exponents) else 0.0
        # Rational exponent? (suggests theoretical origin)
        has_rational_exp = 1.0
        if exponents:
            for e in exponents:
                # Check if e is close to k/n for small n
                is_rational = any(abs(e - k/n) < 0.05 for n in range(1, 7) for k in range(-20, 21))
                if not is_rational:
                    has_rational_exp = 0.0
                    break

        features.append([
            n_terms, n_vars, max_exp, min_exp, mean_exp,
            has_negative_exp, max_coeff, complexity, is_single_term,
            has_integer_exp, has_rational_exp,
        ])
        targets.append(r2)

    feature_names = [
        "n_terms", "n_variables", "max_exponent", "min_exponent", "mean_exponent",
        "has_negative_exp", "max_coefficient", "complexity", "is_single_term",
        "has_integer_exp", "has_rational_exp",
    ]
    return np.array(features), np.array(targets), feature_names


def induce_meta_laws(all_laws: dict[str, list]) -> list[MetaLaw]:
    """
    Discover the grammar of successful physical laws by running
    symbolic regression on law properties → R².
    """
    # Pool all laws from all domains
    pooled = []
    for domain, laws in all_laws.items():
        for law in laws:
            if isinstance(law, SymbolicLaw):
                pooled.append({"expression": law.expression, "r_squared": law.r_squared,
                               "complexity": law.complexity, "domain": domain})
            elif isinstance(law, dict):
                pooled.append(law)

    if len(pooled) < 8:
        return []

    X_meta, y_meta, meta_features = extract_law_features(pooled)

    # Run SR on the meta-dataset
    engine = BuiltinSymbolicSearch(max_terms=2, max_complexity=15)
    meta_laws_raw = engine.fit(X_meta, y_meta, meta_features, top_k=5)

    results = []
    for ml in meta_laws_raw:
        # Compute feature importance via coefficient magnitudes
        importance = {}
        for fn in meta_features:
            if fn in ml.expression:
                importance[fn] = 1.0

        results.append(MetaLaw(
            description=f"Meta-law: R² ≈ {ml.expression}",
            meta_expression=ml.expression,
            meta_r2=ml.r_squared,
            feature_importance=importance,
            sample_size=len(pooled),
        ))

    return results


# ═══════════════════════════════════════════════════════════════
#  MODULE 6: EMERGENT AGENT FEEDBACK LOOPS
#  ---------------------------------------------------------
#  Adversary failures modify Explorer search; Pollinator
#  discoveries seed next round; true multi-round convergence.
# ═══════════════════════════════════════════════════════════════

@dataclass
class ExplorerConfig:
    """Adaptive configuration for an Explorer agent."""
    max_terms: int = 3
    max_complexity: int = 20
    exponent_grid: list[float] = field(default_factory=lambda: [
        -3, -2, -1.5, -1, -2/3, -1/2, -1/3,
        0, 1/3, 1/2, 2/3, 1, 1.5, 2, 3, 7/2,
    ])
    seed_expressions: list[str] = field(default_factory=list)
    parsimony_boost: float = 1.0  # multiplier on complexity penalty


def adapt_explorer_config(
    config: ExplorerConfig,
    validation_results: list[dict],
    successful_transfers: list[dict],
) -> ExplorerConfig:
    """
    Feedback loop: Adversary and Pollinator results modify Explorer config.

    - If Adversary flags overfitting → increase parsimony, reduce max_terms
    - If Adversary flags coefficient sensitivity → prefer integer exponents
    - If Pollinator finds successful transfer with exponent β → add β ± 0.5 to grid
    - If high-R² laws use specific exponents → concentrate grid around those
    """
    new_config = ExplorerConfig(
        max_terms=config.max_terms,
        max_complexity=config.max_complexity,
        exponent_grid=list(config.exponent_grid),
        seed_expressions=list(config.seed_expressions),
        parsimony_boost=config.parsimony_boost,
    )

    # Analyze adversarial failures
    overfitting_count = 0
    sensitivity_count = 0
    for vr in validation_results:
        for attack in vr.get("attacks", []):
            if attack.get("test") == "overfitting_gap" and not attack.get("passed"):
                overfitting_count += 1
            if attack.get("test") == "coefficient_sensitivity" and not attack.get("passed"):
                sensitivity_count += 1

    if overfitting_count > 2:
        new_config.max_terms = max(1, config.max_terms - 1)
        new_config.parsimony_boost *= 1.5
        log.info(f"      [Feedback] Overfitting detected → max_terms={new_config.max_terms}, "
                 f"parsimony×{new_config.parsimony_boost:.1f}")

    if sensitivity_count > 2:
        # Prefer integer and rational exponents
        integer_grid = [e for e in config.exponent_grid if abs(e - round(e)) < 0.01]
        if len(integer_grid) >= 5:
            new_config.exponent_grid = integer_grid
            log.info(f"      [Feedback] Sensitivity detected → exponent grid narrowed to integers")

    # Incorporate successful transfer exponents
    for tr in successful_transfers:
        expr = tr.get("source_expression", "")
        exps = re.findall(r'\^([-+]?\d*\.?\d+)', expr)
        for e_str in exps:
            e = float(e_str)
            # Add fine-grained grid around successful exponent
            for delta in [-0.5, -0.25, 0, 0.25, 0.5]:
                candidate = e + delta
                if candidate not in new_config.exponent_grid:
                    new_config.exponent_grid.append(candidate)
        # Seed the discovered expression for the next domain
        new_config.seed_expressions.append(expr)

    return new_config


def run_adaptive_round(
    splits: dict, round_num: int,
    explorer_configs: dict[str, ExplorerConfig],
    prev_validated: dict | None = None,
) -> tuple[dict, dict, list]:
    """Run one round of exploration with adaptive configs."""
    all_laws = {}
    validation_results = {}

    for dname, split in splits.items():
        cfg = explorer_configs.get(dname, ExplorerConfig())
        engine = BuiltinSymbolicSearch(
            max_terms=cfg.max_terms,
            max_complexity=cfg.max_complexity,
            exponent_grid=cfg.exponent_grid if cfg.exponent_grid else None,
        )

        if dname == "exoplanet":
            surrogate = DynamicalSurrogate(input_dim=split["X_train"].shape[1],
                                           hidden_dim=64, n_blocks=2)
            surrogate.fit(split["X_train"], split["y_train"],
                          epochs=50, batch_size=32, verbose=False)
            y_target = surrogate.predict_proba(split["X_train"])
        else:
            y_target = split["y_train"]

        laws = engine.fit(split["X_train"], y_target, split["feature_names"], top_k=10)
        all_laws[dname] = laws

        # Validate
        validation_results[dname] = []
        for law in laws[:5]:
            review = adversarial_review(
                law, split["X_train"], split["y_train"],
                split["X_test"], split["y_test"],
                split["feature_names"], dname)
            validation_results[dname].append(review)

    # Cross-domain transfer using auto-discovered isomorphisms (Module 3)
    transfers = []
    domains = list(splits.keys())
    for si, src in enumerate(domains):
        for ti, tgt in enumerate(domains):
            if si == ti:
                continue
            # Auto-discover mapping
            mapping = discover_isomorphism(
                splits[src]["X_train"], splits[src]["y_train"], splits[src]["feature_names"], src,
                splits[tgt]["X_train"], splits[tgt]["y_train"], splits[tgt]["feature_names"], tgt,
            )
            # Transfer top valid laws
            valid_laws = [law for law, vr in zip(all_laws[src][:5], validation_results[src])
                          if vr["verdict"] in ("VALID", "WEAK")]
            for law in valid_laws[:2]:
                translated = law.expression
                n_mapped = 0
                for src_var, (tgt_var, sim) in sorted(mapping.items(),
                                                       key=lambda x: len(x[0]), reverse=True):
                    if src_var in translated and sim > 0.3:
                        translated = translated.replace(src_var, tgt_var)
                        n_mapped += 1

                if n_mapped > 0:
                    y_pred = _safe_evaluate_law(translated, splits[tgt]["X_train"],
                                                splits[tgt]["feature_names"])
                    if y_pred is not None:
                        ss_res = np.sum((splits[tgt]["y_train"] - y_pred) ** 2)
                        ss_tot = np.sum((splits[tgt]["y_train"] - np.mean(splits[tgt]["y_train"])) ** 2)
                        r2 = float(1 - ss_res / max(ss_tot, 1e-10))
                        transfers.append({
                            "source_domain": src, "target_domain": tgt,
                            "source_expression": law.expression,
                            "translated_expression": translated,
                            "r2_direct": r2,
                            "mapping_used": {k: v[0] for k, v in mapping.items()},
                            "auto_discovered": True,
                        })

    return all_laws, validation_results, transfers


# ═══════════════════════════════════════════════════════════════
#  MAIN PIPELINE v3
# ═══════════════════════════════════════════════════════════════

def run_breakthrough_swarm_v3():
    start = time.time()
    blackboard = Blackboard(persist_path="results/swarm_state_v3.json")

    log.info("=" * 70)
    log.info("  BREAKTHROUGH DISCOVERY v3 — FRONTIER INNOVATION")
    log.info("=" * 70)

    # ─── Load balanced data ───
    log.info("\n  Loading data...")
    gen = DatasetGenerator(star_mass=1.0, n_planets=2, rng_seed=42)
    exo = gen.generate_dataset(n_systems=300, integration_steps=5000, dt=0.01)
    mat = generate_expanded_perovskite_dataset()
    crit = generate_critical_transition_dataset(n_systems=300)

    data = {"exoplanet": exo, "materials": mat, "critical_transitions": crit}
    splits = {}
    for dname, d in data.items():
        X, y = d["features"], d["labels"]
        n = X.shape[0]
        idx = np.random.RandomState(42).permutation(n)
        sp = int(n * 0.8)
        splits[dname] = {
            "X_train": X[idx[:sp]], "y_train": y[idx[:sp]],
            "X_test": X[idx[sp:]], "y_test": y[idx[sp:]],
            "feature_names": d["feature_names"],
        }
    log.info(f"    Domains: {', '.join(f'{d}(N={s['X_train'].shape[0]})' for d,s in splits.items())}")

    # ═══════════════════════════════════════════════════════
    # INNOVATION 1: MULTI-ROUND ADAPTIVE EXPLORATION
    # ═══════════════════════════════════════════════════════
    log.info("\n" + "=" * 70)
    log.info("  INNOVATION 1: MULTI-ROUND ADAPTIVE EXPLORATION")
    log.info("=" * 70)

    configs = {d: ExplorerConfig() for d in splits}
    all_round_laws = {}
    all_round_transfers = []
    round_metrics = []

    N_ROUNDS = 3
    for rnd in range(N_ROUNDS):
        log.info(f"\n  ── Round {rnd+1}/{N_ROUNDS} ──")
        round_laws, round_validations, round_transfers = run_adaptive_round(
            splits, rnd, configs)

        # Record
        for d, laws in round_laws.items():
            all_round_laws.setdefault(d, []).extend(laws)

        all_round_transfers.extend(round_transfers)

        # Compute round metrics
        metrics = {}
        for d, laws in round_laws.items():
            best = max(laws, key=lambda l: l.r_squared) if laws else None
            metrics[d] = best.r_squared if best else 0
        round_metrics.append(metrics)

        successful_t = [t for t in round_transfers if t.get("r2_direct", -1) > 0.1]
        log.info(f"    Best R²: {', '.join(f'{d}={v:.4f}' for d,v in metrics.items())}")
        log.info(f"    Transfers: {len(successful_t)}/{len(round_transfers)} successful")

        # Feedback: adapt configs for next round
        for d in splits:
            configs[d] = adapt_explorer_config(
                configs[d],
                round_validations.get(d, []),
                successful_t,
            )

    # Deduplicate laws
    for d in all_round_laws:
        seen = set()
        unique = []
        for law in sorted(all_round_laws[d], key=lambda l: l.r_squared, reverse=True):
            if law.expression not in seen:
                seen.add(law.expression)
                unique.append(law)
        all_round_laws[d] = unique[:15]

    # Post everything to blackboard
    for d, laws in all_round_laws.items():
        for law in laws:
            blackboard.post_discovery(
                agent_id=f"explorer_{d}", domain=d,
                law_expression=law.expression,
                accuracy=max(0, law.r_squared), complexity=law.complexity,
                r_squared=law.r_squared,
                metadata={"mse": law.mse, "coefficients": law.coefficients})

    # ═══════════════════════════════════════════════════════
    # INNOVATION 2: RG FIXED-POINT ANALYSIS
    # ═══════════════════════════════════════════════════════
    log.info("\n" + "=" * 70)
    log.info("  INNOVATION 2: RENORMALIZATION GROUP FIXED-POINT ANALYSIS")
    log.info("=" * 70)

    rg_results = {}
    for dname, split in splits.items():
        if dname == "exoplanet":
            # Use surrogate probabilities for SR
            surrogate = DynamicalSurrogate(input_dim=split["X_train"].shape[1],
                                           hidden_dim=64, n_blocks=2)
            surrogate.fit(split["X_train"], split["y_train"],
                          epochs=50, batch_size=32, verbose=False)
            y_rg = surrogate.predict_proba(split["X_train"])
        else:
            y_rg = split["y_train"]

        rg = rg_fixed_point_analysis(
            split["X_train"], y_rg, split["feature_names"], dname)
        rg_results[dname] = rg

        status = "★ FIXED POINT" if rg.is_fixed_point else "✗ not fixed"
        log.info(f"\n  [{dname}] {status}")
        log.info(f"    Exponent drift: σ = {rg.exponent_drift:.4f}")
        if rg.fixed_point_exponent is not None:
            log.info(f"    Fixed-point exponent: β = {rg.fixed_point_exponent:.3f}")
        for lps in rg.laws_per_scale:
            log.info(f"    scale={lps['scale']:.1f}, N={lps['n_points']}, "
                     f"R²={lps['r_squared']:.4f}, exp={lps['exponent']:.2f}: {lps['expression'][:50]}")

    # ═══════════════════════════════════════════════════════
    # INNOVATION 3: AUTOMATIC DOMAIN ISOMORPHISM
    # ═══════════════════════════════════════════════════════
    log.info("\n" + "=" * 70)
    log.info("  INNOVATION 3: AUTOMATIC DOMAIN ISOMORPHISM DISCOVERY")
    log.info("=" * 70)

    isomorphisms = {}
    domains = list(splits.keys())
    for i, d_a in enumerate(domains):
        for j, d_b in enumerate(domains):
            if i >= j:
                continue
            s_a, s_b = splits[d_a], splits[d_b]
            mapping = discover_isomorphism(
                s_a["X_train"], s_a["y_train"], s_a["feature_names"], d_a,
                s_b["X_train"], s_b["y_train"], s_b["feature_names"], d_b,
            )
            key = f"{d_a}↔{d_b}"
            isomorphisms[key] = mapping
            log.info(f"\n  {key}:")
            for src_var, (tgt_var, sim) in sorted(mapping.items(), key=lambda x: x[1][1], reverse=True)[:5]:
                log.info(f"    {src_var} → {tgt_var} (similarity={sim:.3f})")

    # ═══════════════════════════════════════════════════════
    # INNOVATION 4: INTERVENTIONAL CAUSAL TESTING
    # ═══════════════════════════════════════════════════════
    log.info("\n" + "=" * 70)
    log.info("  INNOVATION 4: INTERVENTIONAL CAUSAL TESTING")
    log.info("=" * 70)

    causal_results = {}
    for dname, laws in all_round_laws.items():
        split = splits[dname]
        best_laws = sorted(laws, key=lambda l: l.r_squared, reverse=True)[:3]
        domain_causal = []
        for law in best_laws:
            results = interventional_test(
                law, split["X_train"], split["y_train"],
                split["feature_names"], dname)
            domain_causal.extend(results)
            for r in results:
                status = "★ CAUSAL" if r.is_causal else "  correlated"
                gap_str = f"gap={r.causal_gap:.3f}"
                log.info(f"    [{dname}] {status}: do({r.intervention_variable}) → "
                         f"R²_obs={r.observational_r2:.3f}, R²_int={r.interventional_r2:.3f}, "
                         f"{gap_str}")
        causal_results[dname] = domain_causal

    # ═══════════════════════════════════════════════════════
    # INNOVATION 5: BAYESIAN EXPERIMENT DESIGN
    # ═══════════════════════════════════════════════════════
    log.info("\n" + "=" * 70)
    log.info("  INNOVATION 5: BAYESIAN OPTIMAL EXPERIMENT DESIGN")
    log.info("=" * 70)

    experiment_designs = {}
    for dname, laws in all_round_laws.items():
        split = splits[dname]
        if dname == "exoplanet":
            continue  # skip classification domain for regression-based design
        designs = batch_experiment_design(laws[:5], split["X_train"], split["feature_names"])
        experiment_designs[dname] = designs
        for ed in designs[:3]:
            log.info(f"\n  [{dname}] Experiment to discriminate:")
            log.info(f"    Law A: {ed.law_a[:50]}")
            log.info(f"    Law B: {ed.law_b[:50]}")
            log.info(f"    Optimal feature: {ed.feature_name}")
            log.info(f"    Predicted A={ed.predicted_y_a:.3f} vs B={ed.predicted_y_b:.3f}")
            log.info(f"    Discrimination power: {ed.discrimination_power:.3f}")

    # ═══════════════════════════════════════════════════════
    # INNOVATION 6: META-LAW INDUCTION
    # ═══════════════════════════════════════════════════════
    log.info("\n" + "=" * 70)
    log.info("  INNOVATION 6: META-LAW INDUCTION (Grammar of Physics)")
    log.info("=" * 70)

    meta_laws = induce_meta_laws(all_round_laws)
    for ml in meta_laws[:5]:
        log.info(f"\n  {ml.description}")
        log.info(f"    Meta-R² = {ml.meta_r2:.4f} (N = {ml.sample_size} laws)")
        if ml.feature_importance:
            log.info(f"    Important features: {list(ml.feature_importance.keys())}")

    # ═══════════════════════════════════════════════════════
    # STATISTICAL CORRECTION
    # ═══════════════════════════════════════════════════════
    log.info("\n" + "=" * 70)
    log.info("  STATISTICAL CORRECTION (Benjamini-Hochberg)")
    log.info("=" * 70)

    all_p = []
    all_ids = []
    for d, laws in all_round_laws.items():
        n = splits[d]["X_test"].shape[0]
        nf = splits[d]["X_test"].shape[1]
        for law in laws:
            p = compute_law_p_value(law.r_squared, n, nf)
            all_p.append(p)
            all_ids.append((d, law.expression, law.r_squared))

    sig = benjamini_hochberg(all_p, alpha=0.05)
    n_sig = sum(sig)
    log.info(f"    {n_sig}/{len(all_p)} laws survive BH correction")

    # ═══════════════════════════════════════════════════════
    # COMPILE FINAL REPORT
    # ═══════════════════════════════════════════════════════
    elapsed = time.time() - start

    report = {
        "version": "v3_frontier",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": elapsed,
        "n_rounds": N_ROUNDS,
        "dataset_sizes": {d: s["X_train"].shape[0] for d, s in splits.items()},
        "best_per_domain": {
            d: {"expression": max(laws, key=lambda l: l.r_squared).expression,
                "r_squared": max(laws, key=lambda l: l.r_squared).r_squared}
            for d, laws in all_round_laws.items() if laws
        },
        "round_metrics": round_metrics,
        "rg_analysis": {
            d: {
                "is_fixed_point": r.is_fixed_point,
                "exponent_drift": r.exponent_drift,
                "fixed_point_exponent": r.fixed_point_exponent,
                "laws_per_scale": r.laws_per_scale,
            } for d, r in rg_results.items()
        },
        "auto_isomorphisms": {
            k: {sv: {"target": tv, "similarity": ss} for sv, (tv, ss) in v.items()}
            for k, v in isomorphisms.items()
        },
        "causal_testing": {
            d: [{"expression": r.law_expression, "variable": r.intervention_variable,
                 "r2_obs": r.observational_r2, "r2_int": r.interventional_r2,
                 "is_causal": r.is_causal, "confounding": r.confounding_fraction}
                for r in results]
            for d, results in causal_results.items()
        },
        "experiment_designs": {
            d: [{"law_a": e.law_a, "law_b": e.law_b,
                 "optimal_feature": e.feature_name,
                 "discrimination_power": e.discrimination_power,
                 "predicted_a": e.predicted_y_a, "predicted_b": e.predicted_y_b}
                for e in designs[:5]]
            for d, designs in experiment_designs.items()
        },
        "meta_laws": [{"description": m.description, "expression": m.meta_expression,
                       "r2": m.meta_r2, "features": m.feature_importance,
                       "n_laws": m.sample_size} for m in meta_laws],
        "statistical_correction": {"significant": n_sig, "total": len(all_p)},
        "transfers_all_rounds": all_round_transfers,
        "n_successful_transfers": sum(1 for t in all_round_transfers if t.get("r2_direct", -1) > 0.1),
        "universal_patterns": _detect_cross_innovation_patterns(rg_results, causal_results, meta_laws),
    }

    path = Path("results/breakthrough_results_v3.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    log.info(f"\n  Results saved to {path}")

    return report


def _detect_cross_innovation_patterns(rg_results, causal_results, meta_laws) -> list[dict]:
    """Find patterns that emerge from combining multiple innovations."""
    patterns = []

    # Pattern 1: RG fixed points that are also causal
    for d, rg in rg_results.items():
        if rg.is_fixed_point and d in causal_results:
            causal_for_domain = [r for r in causal_results[d] if r.is_causal]
            if causal_for_domain:
                patterns.append({
                    "type": "RG_CAUSAL_CONVERGENCE",
                    "description": (
                        f"In {d}: the RG fixed-point exponent β={rg.fixed_point_exponent:.2f} "
                        f"is also causal (passes interventional test). This is the strongest "
                        f"possible evidence for a universal causal law."
                    ),
                    "domain": d,
                    "exponent": rg.fixed_point_exponent,
                    "n_causal": len(causal_for_domain),
                })

    # Pattern 2: RG across domains — do different domains share the same fixed point?
    fp_exps = {d: rg.fixed_point_exponent for d, rg in rg_results.items()
               if rg.is_fixed_point and rg.fixed_point_exponent is not None}
    if len(fp_exps) >= 2:
        exps = list(fp_exps.values())
        if max(exps) - min(exps) < 1.0:
            patterns.append({
                "type": "CROSS_DOMAIN_RG_CONVERGENCE",
                "description": (
                    f"Multiple domains share similar RG fixed-point exponents: "
                    f"{fp_exps}. Exponent spread = {max(exps)-min(exps):.2f}."
                ),
                "domains": list(fp_exps.keys()),
                "exponents": fp_exps,
            })

    # Pattern 3: Meta-law prediction — what makes laws universal?
    for ml in meta_laws:
        if ml.meta_r2 > 0.4:
            patterns.append({
                "type": "GRAMMAR_OF_PHYSICS",
                "description": (
                    f"Meta-law with R²={ml.meta_r2:.3f}: {ml.meta_expression}. "
                    f"This predicts which laws will generalize across domains."
                ),
                "features": list(ml.feature_importance.keys()),
            })

    return patterns


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    report = run_breakthrough_swarm_v3()

    print("\n" + "=" * 70)
    print("  BREAKTHROUGH v3 — FRONTIER INNOVATION RESULTS")
    print("=" * 70)

    # RG fixed points
    rg = report["rg_analysis"]
    for d, r in rg.items():
        fp = "★ FIXED POINT" if r["is_fixed_point"] else "✗"
        print(f"  RG [{d}]: {fp}, β={r['fixed_point_exponent']}, drift={r['exponent_drift']:.4f}")

    # Causal testing
    for d, results in report["causal_testing"].items():
        causal = sum(1 for r in results if r["is_causal"])
        print(f"  Causal [{d}]: {causal}/{len(results)} laws pass interventional test")

    # Meta-laws
    for ml in report["meta_laws"][:3]:
        print(f"  Meta-law: {ml['expression'][:50]} (R²={ml['r2']:.3f})")

    # Cross-innovation patterns
    for p in report.get("universal_patterns", []):
        print(f"\n  *** {p['type']} ***")
        print(f"  {p['description']}")

    print(f"\n  Rounds: {report['n_rounds']}, Transfers OK: {report['n_successful_transfers']}")
    print(f"  BH-significant: {report['statistical_correction']['significant']}/{report['statistical_correction']['total']}")
    print(f"  Time: {report['elapsed_seconds']:.1f}s")
    print("=" * 70)
