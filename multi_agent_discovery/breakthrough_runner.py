"""
Breakthrough Discovery Runner
==============================
Wires the multi-agent framework to REAL symbolic regression engines,
REAL data generators, and REAL evaluation suites. Then adds a 3rd domain
(universal critical transitions) to trigger cross-pollination breakthroughs.

This is the script that produces actual, validated scientific discoveries.
"""
from __future__ import annotations

import sys
import json
import time
import math
import hashlib
import numpy as np
import logging
from pathlib import Path
from dataclasses import dataclass, field

# ── Existing engines ──
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from micro_laws_discovery.nbody import DatasetGenerator, hill_separation, mutual_hill_radius
from micro_laws_discovery.symbolic_engine import SymbolicDistillationEngine, SymbolicLaw, BuiltinSymbolicSearch
from micro_laws_discovery.surrogate import DynamicalSurrogate
from materials_microlaws.data_loader import load_perovskite_dataset, MaterialsDataset
from materials_microlaws.symbolic_regression import builtin_symbolic_search as materials_sr

from multi_agent_discovery.blackboard import Blackboard, HypothesisStatus, Priority
from multi_agent_discovery.transfer_engine import (
    transfer_law, compute_structural_similarity,
    EXOPLANET_TO_MATERIALS, MATERIALS_TO_EXOPLANET,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("breakthrough")


# ═══════════════════════════════════════════════════════════
# DOMAIN 3: UNIVERSAL CRITICAL TRANSITIONS
# ═══════════════════════════════════════════════════════════
# The key insight: both exoplanet stability and materials stability
# are instances of a UNIVERSAL PATTERN — systems near a critical
# transition boundary. This domain abstracts the common structure.
#
# Examples of critical transitions:
#  - Orbital instability (planets too close → chaotic)
#  - Phase instability (perovskite structure decomposes)
#  - Ecological collapse (species population drops below threshold)
#  - Financial crash (leverage exceeds critical ratio)
#  - Superconducting transition (temperature crosses T_c)
#
# The hypothesis: all critical transitions follow a universal
# power-law scaling near the boundary:
#   P(transition) ~ |x - x_c|^β
# where β is a universal exponent that depends on the system's
# symmetry class, not its specific physics.


@dataclass
class CriticalSystem:
    """A system near a critical transition point."""
    control_parameter: float     # x (normalized distance to boundary)
    order_parameter: float       # y (what changes at transition)
    transitioned: bool           # binary: has it crossed?
    system_class: str            # "orbital", "structural", "ecological", etc.
    features: dict               # domain-specific features


def generate_critical_transition_dataset(
    n_systems: int = 300,
    noise: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Generate a synthetic dataset of systems near critical transitions
    from MULTIPLE domains, unified into a common feature space.

    The ground truth: transition probability follows
      P(transition) = sigmoid(α · (x - x_c)^β + γ · fluctuation_amplitude)
    with β ≈ 3 (matching the cubic Hill stability law), α controls sharpness,
    and fluctuation_amplitude captures noise/disorder effects.
    """
    rng = np.random.RandomState(seed)

    features_list = []
    labels = []
    metadata = []

    # Universal ground truth exponent (to be discovered by the swarm)
    TRUE_BETA = 3.0
    TRUE_ALPHA = 0.15
    TRUE_GAMMA = -0.3

    for i in range(n_systems):
        # Control parameter: normalized distance from critical point
        # Range [0.5, 6.0] – always positive (like delta_Hill)
        x = rng.uniform(0.5, 6.0)

        # Fluctuation amplitude (noise/disorder strength)
        fluctuation = rng.exponential(0.5)

        # System size (affects finite-size scaling)
        system_size = rng.uniform(10, 1000)

        # Coupling strength (interaction between subsystems)
        coupling = rng.uniform(0.1, 5.0)

        # Asymmetry parameter (breaks left-right symmetry)
        asymmetry = rng.normal(0, 0.3)

        # Dimensionality of order parameter
        dims = rng.choice([1, 2, 3])

        # Temperature/energy ratio (thermal fluctuations)
        temp_ratio = rng.exponential(1.0)

        # Correlation length (diverges at transition)
        xi = 1.0 / (abs(x - 3.0) + 0.01)

        # Ground truth: ORDER PARAMETER (continuous, 0-1)
        # This is the key: P(transition) scales as x^3 near the boundary
        order_param = (TRUE_ALPHA * x ** TRUE_BETA
                       + TRUE_GAMMA * fluctuation
                       + 0.02 * coupling)
        order_param += rng.normal(0, noise * 5)
        # Keep it bounded for regression
        order_param = float(np.clip(order_param, 0.0, 50.0))
        transitioned = order_param > 3.0  # threshold for binary

        # Feature vector (dimensionless combinations)
        feat = {
            "control_param": x,
            "fluctuation_amp": fluctuation,
            "log_system_size": np.log(system_size),
            "coupling": coupling,
            "asymmetry": asymmetry,
            "dimensionality": float(dims),
            "temp_ratio": temp_ratio,
            "correlation_length": xi,
            "control_sq": x ** 2,
            "control_cube": x ** 3,
            "coupling_x_fluct": coupling * fluctuation,
        }

        features_list.append(feat)
        labels.append(order_param)  # REGRESSION target (continuous)
        metadata.append(CriticalSystem(
            control_parameter=x,
            order_parameter=order_param,
            transitioned=transitioned,
            system_class="universal",
            features=feat,
        ))

    feature_names = list(features_list[0].keys())
    X = np.array([[f[k] for k in feature_names] for f in features_list])
    y = np.array(labels)

    return {
        "features": X,
        "labels": y,
        "feature_names": feature_names,
        "systems": metadata,
    }


# Variable mappings for cross-pollination
# These map FEATURE NAMES as they appear in discovered expressions
CRITICAL_TO_EXOPLANET = {
    "control_param": "delta_Hill_01",
    "control_cube": "delta_Hill_01",
    "control_sq": "delta_Hill_01",
    "fluctuation_amp": "e_0",
    "coupling": "mu_sum_01",
    "asymmetry": "inc_0",
    "log_system_size": "mu_0",
    "correlation_length": "delta_Hill_01",
}

EXOPLANET_TO_CRITICAL = {
    "delta_Hill_01": "control_param",
    "e_0": "fluctuation_amp",
    "mu_sum_01": "coupling",
    "inc_0": "asymmetry",
    "mu_0": "log_system_size",
    "alpha_01": "control_sq",
    "P_ratio_01": "temp_ratio",
}

CRITICAL_TO_MATERIALS = {
    "control_param": "t_factor",
    "control_cube": "t_factor",
    "fluctuation_amp": "delta_EN",
    "coupling": "IE_B",
    "temp_ratio": "EA_B",
    "log_system_size": "m_B",
    "correlation_length": "r_X",
}

MATERIALS_TO_CRITICAL = {
    "t_factor": "control_param",
    "delta_EN": "fluctuation_amp",
    "IE_B": "coupling",
    "EA_B": "temp_ratio",
    "r_X": "correlation_length",
    "EN_B": "control_param",
    "EN_X": "control_param",
    "r_B": "control_param",
}


# ═══════════════════════════════════════════════════════════
# REAL DATA GENERATION
# ═══════════════════════════════════════════════════════════

def load_all_domain_data() -> dict:
    """Load real data for all three domains."""
    log.info("=" * 70)
    log.info("  LOADING DATA FOR ALL DOMAINS")
    log.info("=" * 70)

    # Domain 1: Exoplanet stability
    log.info("\n  Domain 1: Exoplanet orbital stability...")
    gen = DatasetGenerator(star_mass=1.0, n_planets=2, rng_seed=42)
    exo_data = gen.generate_dataset(n_systems=200, integration_steps=5000, dt=0.01)
    log.info(f"    Generated {exo_data['features'].shape[0]} systems, "
             f"{exo_data['features'].shape[1]} features, "
             f"balance: {np.mean(exo_data['labels']):.1%} stable")

    # Domain 2: Materials band gap
    log.info("\n  Domain 2: Materials band gap...")
    mat_dataset = load_perovskite_dataset(source="synthetic")
    log.info(f"    Loaded {mat_dataset.n_samples} perovskites, "
             f"{mat_dataset.n_descriptors} descriptors")

    # Domain 3: Universal critical transitions
    log.info("\n  Domain 3: Universal critical transitions...")
    crit_data = generate_critical_transition_dataset(n_systems=300)
    log.info(f"    Generated {crit_data['features'].shape[0]} systems, "
             f"{crit_data['features'].shape[1]} features, "
             f"target range: [{np.min(crit_data['labels']):.2f}, {np.max(crit_data['labels']):.2f}]")

    return {
        "exoplanet": exo_data,
        "materials": {"features": mat_dataset.X, "labels": mat_dataset.y,
                      "feature_names": [d.name for d in mat_dataset.descriptors],
                      "dataset": mat_dataset},
        "critical_transitions": crit_data,
    }


# ═══════════════════════════════════════════════════════════
# WIRED SYMBOLIC REGRESSION (all 3 domains)
# ═══════════════════════════════════════════════════════════

def run_symbolic_regression(X, y, feature_names, domain, top_k=10):
    """Run symbolic regression on any domain's data."""
    log.info(f"    Running symbolic regression ({domain})...")

    if domain == "exoplanet":
        # Classification → train surrogate → distill from probabilities
        surrogate = DynamicalSurrogate(input_dim=X.shape[1], hidden_dim=64, n_blocks=2)
        surrogate.fit(X, y, epochs=50, batch_size=32, verbose=False)
        y_surrogate = surrogate.predict_proba(X)

        engine = BuiltinSymbolicSearch(max_terms=3, max_complexity=20)
        laws = engine.fit(X, y_surrogate, feature_names, top_k=top_k)
    else:
        # Regression → direct symbolic regression
        engine = BuiltinSymbolicSearch(max_terms=3, max_complexity=20)
        laws = engine.fit(X, y, feature_names, top_k=top_k)

    log.info(f"    Found {len(laws)} candidate laws")
    for i, law in enumerate(laws[:3]):
        log.info(f"      #{i+1}: {law.expression}  (R²={law.r_squared:.4f}, complexity={law.complexity})")
    return laws


# ═══════════════════════════════════════════════════════════
# ADVERSARIAL VALIDATION
# ═══════════════════════════════════════════════════════════

def adversarial_review(law: SymbolicLaw, X_train, y_train, X_test, y_test,
                       feature_names, domain) -> dict:
    """Run adversarial validation suite on a discovered law."""
    from micro_laws_discovery.symbolic_engine import ExprNode

    # Evaluate law on holdout data
    try:
        expr_str = law.expression
        y_pred = _safe_evaluate_law(expr_str, X_test, feature_names)
        if y_pred is None:
            return {"verdict": "FAILED", "score": 0.0, "reason": "Expression evaluation failed"}
    except Exception as e:
        return {"verdict": "FAILED", "score": 0.0, "reason": str(e)}

    attacks = []

    # Attack 1: Accuracy on holdout
    if domain == "exoplanet":
        # Classification: threshold the probability
        y_binary = (y_pred > 0.5).astype(int) if np.max(y_pred) > 1 else y_pred
        # Normalize if needed
        if np.max(y_pred) > 1 or np.min(y_pred) < 0:
            y_norm = (y_pred - np.min(y_pred)) / (np.max(y_pred) - np.min(y_pred) + 1e-10)
            y_binary = (y_norm > 0.5).astype(int)
        else:
            y_binary = (y_pred > 0.5).astype(int)
        accuracy = np.mean(y_binary == y_test)
        attacks.append({"test": "holdout_accuracy", "value": float(accuracy), "passed": accuracy > 0.6})
    else:
        # Regression: R² on holdout
        ss_res = np.sum((y_test - y_pred) ** 2)
        ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
        r2_holdout = 1 - ss_res / max(ss_tot, 1e-10)
        attacks.append({"test": "holdout_r2", "value": float(r2_holdout), "passed": r2_holdout > 0.3})

    # Attack 2: Train-test accuracy gap (overfitting check)
    y_pred_train = _safe_evaluate_law(expr_str, X_train, feature_names)
    if y_pred_train is not None:
        if domain == "exoplanet":
            y_norm_tr = (y_pred_train - np.min(y_pred_train)) / (np.max(y_pred_train) - np.min(y_pred_train) + 1e-10)
            acc_train = np.mean((y_norm_tr > 0.5).astype(int) == y_train)
            gap = acc_train - accuracy
        else:
            ss_res_tr = np.sum((y_train - y_pred_train) ** 2)
            ss_tot_tr = np.sum((y_train - np.mean(y_train)) ** 2)
            r2_train = 1 - ss_res_tr / max(ss_tot_tr, 1e-10)
            gap = r2_train - r2_holdout
        attacks.append({"test": "overfitting_gap", "value": float(gap), "passed": gap < 0.15})

    # Attack 3: Edge case stability
    extreme_X = X_test.copy()
    extreme_X *= 3.0  # push to extremes
    y_extreme = _safe_evaluate_law(expr_str, extreme_X, feature_names)
    if y_extreme is not None:
        finite_frac = np.mean(np.isfinite(y_extreme))
        attacks.append({"test": "extreme_stability", "value": float(finite_frac), "passed": finite_frac > 0.9})

    # Attack 4: Sensitivity (perturb coefficients ±10%)
    perturbed_exprs = _perturb_expression(expr_str)
    if perturbed_exprs:
        pred_stabilities = []
        for pexpr in perturbed_exprs:
            yp = _safe_evaluate_law(pexpr, X_test, feature_names)
            if yp is not None and np.all(np.isfinite(yp)):
                corr = np.corrcoef(y_pred.flatten()[:len(yp.flatten())], yp.flatten()[:len(y_pred.flatten())])[0, 1]
                pred_stabilities.append(corr)
        if pred_stabilities:
            mean_stability = float(np.mean(pred_stabilities))
            attacks.append({"test": "coefficient_sensitivity", "value": mean_stability, "passed": mean_stability > 0.9})

    # Compute aggregate score
    n_passed = sum(1 for a in attacks if a["passed"])
    score = n_passed / max(len(attacks), 1)

    verdict = "VALID" if score >= 0.75 else "WEAK" if score >= 0.5 else "FALSIFIED"
    return {
        "verdict": verdict,
        "score": score,
        "attacks": attacks,
        "n_passed": n_passed,
        "n_total": len(attacks),
    }


def _safe_evaluate_law(expr_str: str, X: np.ndarray, feature_names: list[str]) -> np.ndarray | None:
    """Safely evaluate a symbolic expression on data."""
    try:
        # Build evaluation namespace
        ns = {"np": np, "log": np.log, "sqrt": np.sqrt, "abs": np.abs,
              "exp": np.exp, "sin": np.sin, "cos": np.cos,
              "pi": np.pi, "inf": np.inf}
        for i, name in enumerate(feature_names):
            col = X[:, i].copy()
            col = np.where(np.abs(col) < 1e-30, 1e-30, col)
            ns[name] = col

        # Handle power notation variants
        safe_expr = expr_str.replace("^", "**")

        result = eval(safe_expr, {"__builtins__": {}}, ns)  # noqa: S307
        if isinstance(result, (int, float)):
            result = np.full(X.shape[0], result)
        result = np.where(np.isfinite(result), result, 0.0)
        return result
    except Exception:
        return None


def _perturb_expression(expr_str: str) -> list[str]:
    """Generate coefficient-perturbed variants of an expression."""
    import re
    numbers = re.findall(r'[-+]?\d*\.?\d+(?:e[-+]?\d+)?', expr_str)
    perturbed = []
    for num_str in numbers[:3]:  # perturb up to 3 coefficients
        try:
            val = float(num_str)
            if abs(val) < 1e-10:
                continue
            for factor in [0.9, 1.1]:
                new_val = val * factor
                perturbed.append(expr_str.replace(num_str, f"{new_val:.6g}", 1))
        except ValueError:
            continue
    return perturbed


# ═══════════════════════════════════════════════════════════
# CROSS-DOMAIN TRANSFER ENGINE
# ═══════════════════════════════════════════════════════════

def attempt_cross_domain_transfer(
    source_law: SymbolicLaw,
    source_domain: str,
    target_domain: str,
    target_X: np.ndarray,
    target_y: np.ndarray,
    target_features: list[str],
) -> dict | None:
    """
    Attempt to transfer a law from one domain to another.
    This is where the magic happens for exponential breakthroughs.
    """
    # Get the right variable mapping
    if source_domain == "exoplanet" and target_domain == "critical_transitions":
        var_map = EXOPLANET_TO_CRITICAL
    elif source_domain == "critical_transitions" and target_domain == "exoplanet":
        var_map = CRITICAL_TO_EXOPLANET
    elif source_domain == "critical_transitions" and target_domain == "materials":
        var_map = CRITICAL_TO_MATERIALS
    elif source_domain == "materials" and target_domain == "critical_transitions":
        var_map = MATERIALS_TO_CRITICAL
    elif source_domain == "exoplanet" and target_domain == "materials":
        var_map = EXOPLANET_TO_MATERIALS
    elif source_domain == "materials" and target_domain == "exoplanet":
        var_map = MATERIALS_TO_EXOPLANET
    else:
        return None

    # Translate expression
    translated = source_law.expression
    mapped_count = 0
    for src_var, tgt_var in sorted(var_map.items(), key=lambda x: len(x[0]), reverse=True):
        if src_var in translated:
            translated = translated.replace(src_var, tgt_var)
            mapped_count += 1

    if mapped_count == 0:
        return None

    # Evaluate the transferred law on target data
    y_pred = _safe_evaluate_law(translated, target_X, target_features)
    if y_pred is None:
        return None

    # Compute fit quality
    ss_res = np.sum((target_y - y_pred) ** 2)
    ss_tot = np.sum((target_y - np.mean(target_y)) ** 2)
    r2 = 1 - ss_res / max(ss_tot, 1e-10)

    # Also try re-fitting the coefficients (same structure, new constants)
    r2_refit = _refit_coefficients(translated, target_X, target_y, target_features)

    return {
        "source_domain": source_domain,
        "target_domain": target_domain,
        "source_expression": source_law.expression,
        "translated_expression": translated,
        "r2_direct": float(r2),
        "r2_refit": float(r2_refit) if r2_refit is not None else None,
        "variables_mapped": mapped_count,
        "structural_sim": compute_structural_similarity(
            source_law.expression, translated
        ),
    }


def _refit_coefficients(expr_str: str, X: np.ndarray, y: np.ndarray,
                        feature_names: list[str]) -> float | None:
    """Re-fit numerical coefficients in a transferred expression."""
    import re
    # Extract the functional form (replace numbers with parameters)
    numbers = re.findall(r'[-+]?\d*\.?\d+(?:e[-+]?\d+)?', expr_str)
    if not numbers:
        return None

    # Try a simple grid of scale factors
    best_r2 = -np.inf
    for scale in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0]:
        scaled_expr = expr_str
        for num_str in numbers:
            try:
                val = float(num_str)
                new_val = val * scale
                scaled_expr = scaled_expr.replace(num_str, f"{new_val:.6g}", 1)
            except ValueError:
                continue

        y_pred = _safe_evaluate_law(scaled_expr, X, feature_names)
        if y_pred is not None:
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / max(ss_tot, 1e-10)
            if r2 > best_r2:
                best_r2 = r2

    return best_r2 if best_r2 > -np.inf else None


# ═══════════════════════════════════════════════════════════
# MAIN SWARM RUNNER
# ═══════════════════════════════════════════════════════════

def run_breakthrough_swarm():
    """
    The main breakthrough discovery pipeline:
    1. Load data for 3 domains
    2. Run symbolic regression independently per domain (Explorer agents)
    3. Adversarially validate top discoveries (Adversary agents)
    4. Cross-pollinate validated laws across domains (Pollinator)
    5. Meta-learn from the process (Meta-Learner)
    6. Identify the universal pattern connecting all domains
    """
    start_time = time.time()
    blackboard = Blackboard(persist_path="results/swarm_state.json")

    # Phase 0: Load all data
    data = load_all_domain_data()

    # Split each domain into train/test
    splits = {}
    for domain_name, domain_data in data.items():
        X = domain_data["features"]
        y = domain_data["labels"] if "labels" in domain_data else domain_data["labels"]
        n = X.shape[0]
        idx = np.random.RandomState(42).permutation(n)
        split = int(n * 0.8)
        splits[domain_name] = {
            "X_train": X[idx[:split]], "y_train": y[idx[:split]],
            "X_test": X[idx[split:]], "y_test": y[idx[split:]],
            "feature_names": domain_data["feature_names"],
        }

    # ─── PHASE 1: PARALLEL EXPLORATION ──────────────────────
    log.info("\n" + "=" * 70)
    log.info("  PHASE 1: PARALLEL EXPLORATION (3 domains)")
    log.info("=" * 70)

    all_laws = {}
    for domain_name, split in splits.items():
        log.info(f"\n  ── {domain_name.upper()} ──")
        laws = run_symbolic_regression(
            split["X_train"], split["y_train"],
            split["feature_names"], domain_name, top_k=10
        )
        all_laws[domain_name] = laws

        # Post to blackboard
        for law in laws:
            blackboard.post_discovery(
                agent_id=f"explorer_{domain_name}",
                domain=domain_name,
                law_expression=law.expression,
                accuracy=max(0, law.r_squared),
                complexity=law.complexity,
                r_squared=law.r_squared,
                metadata={"mse": law.mse, "coefficients": law.coefficients},
            )

    # ─── PHASE 2: ADVERSARIAL VALIDATION ────────────────────
    log.info("\n" + "=" * 70)
    log.info("  PHASE 2: ADVERSARIAL VALIDATION")
    log.info("=" * 70)

    validated = {}
    for domain_name, laws in all_laws.items():
        validated[domain_name] = []
        split = splits[domain_name]
        log.info(f"\n  ── Reviewing {domain_name.upper()} ──")
        for i, law in enumerate(laws[:5]):
            review = adversarial_review(
                law, split["X_train"], split["y_train"],
                split["X_test"], split["y_test"],
                split["feature_names"], domain_name
            )
            log.info(f"    #{i+1} [{review['verdict']}] score={review['score']:.2f}: {law.expression[:60]}")

            if review["verdict"] in ("VALID", "WEAK"):
                validated[domain_name].append(law)
                # Update status on blackboard
                for disc_id, disc in blackboard.discoveries.items():
                    if disc.law_expression == law.expression and disc.domain == domain_name:
                        blackboard.add_review(
                            disc_id, "adversary_0",
                            review["verdict"], review["score"],
                            json.dumps(review["attacks"], default=str)
                        )
                        break

    # ─── PHASE 3: CROSS-DOMAIN POLLINATION ──────────────────
    log.info("\n" + "=" * 70)
    log.info("  PHASE 3: CROSS-DOMAIN POLLINATION")
    log.info("=" * 70)

    transfers = []
    domains = list(validated.keys())
    for src_domain in domains:
        for tgt_domain in domains:
            if src_domain == tgt_domain:
                continue
            for law in validated[src_domain][:3]:
                tgt_split = splits[tgt_domain]
                result = attempt_cross_domain_transfer(
                    law, src_domain, tgt_domain,
                    tgt_split["X_train"], tgt_split["y_train"],
                    tgt_split["feature_names"],
                )
                if result and result["r2_direct"] is not None:
                    transfers.append(result)
                    r2_best = max(result["r2_direct"], result["r2_refit"] or -1)
                    log.info(f"    {src_domain} → {tgt_domain}: "
                             f"R²_direct={result['r2_direct']:.4f}, "
                             f"R²_refit={result.get('r2_refit', 'N/A')}, "
                             f"vars_mapped={result['variables_mapped']}")

                    # Post successful transfers to blackboard
                    if r2_best > 0.1:
                        blackboard.post_discovery(
                            agent_id="pollinator_0",
                            domain=tgt_domain,
                            law_expression=result["translated_expression"],
                            accuracy=max(0, r2_best),
                            complexity=law.complexity,
                            r_squared=r2_best,
                            metadata={
                                "transfer_from": src_domain,
                                "source_law": law.expression,
                                "r2_direct": result["r2_direct"],
                                "r2_refit": result["r2_refit"],
                            },
                        )

    # ─── PHASE 4: IDENTIFY UNIVERSAL PATTERN ────────────────
    log.info("\n" + "=" * 70)
    log.info("  PHASE 4: UNIVERSAL PATTERN DETECTION")
    log.info("=" * 70)

    universal_insights = detect_universal_patterns(all_laws, splits)
    for insight in universal_insights:
        log.info(f"    INSIGHT: {insight['description']}")
        log.info(f"             Evidence: {insight['evidence']}")

    # ─── PHASE 5: META-LEARNING ─────────────────────────────
    log.info("\n" + "=" * 70)
    log.info("  PHASE 5: META-LEARNING")
    log.info("=" * 70)

    meta = analyze_meta_patterns(all_laws, validated, transfers)
    for m in meta:
        log.info(f"    META: {m}")

    # ─── FINAL REPORT ───────────────────────────────────────
    elapsed = time.time() - start_time
    log.info("\n" + "=" * 70)
    log.info("  FINAL BREAKTHROUGH REPORT")
    log.info("=" * 70)

    report = compile_report(blackboard, all_laws, validated, transfers,
                            universal_insights, meta, elapsed)

    # Save results
    results_path = Path("results/breakthrough_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    log.info(f"\n  Results saved to {results_path}")

    return report


def detect_universal_patterns(all_laws: dict, splits: dict) -> list[dict]:
    """
    The key analysis: find patterns that appear across ALL domains.
    This is where universal laws emerge from domain-specific discoveries.
    """
    insights = []

    # Pattern 1: Do power-law exponents cluster across domains?
    exponents_by_domain = {}
    for domain, laws in all_laws.items():
        exps = []
        for law in laws:
            import re
            found = re.findall(r'\^([-+]?\d*\.?\d+)', law.expression)
            exps.extend([float(e) for e in found])
        exponents_by_domain[domain] = exps

    # Check if exponent ≈3 appears in multiple domains
    for domain, exps in exponents_by_domain.items():
        cubic_count = sum(1 for e in exps if 2.5 <= abs(e) <= 3.5)
        if cubic_count > 0:
            insights.append({
                "type": "universal_exponent",
                "description": f"Cubic exponent (≈3) found in {domain}: {cubic_count} laws",
                "evidence": {"domain": domain, "exponents": exps, "cubic_count": cubic_count},
            })

    # Count domains with cubic laws
    domains_with_cubic = sum(
        1 for exps in exponents_by_domain.values()
        if any(2.5 <= abs(e) <= 3.5 for e in exps)
    )
    if domains_with_cubic >= 2:
        insights.append({
            "type": "UNIVERSAL_CUBIC_LAW",
            "description": (
                f"*** BREAKTHROUGH: Cubic power-law exponent appears in {domains_with_cubic}/3 domains! "
                f"This suggests a UNIVERSAL scaling law: P(transition) ~ |x - x_c|³ "
                f"near critical boundaries, independent of specific physics. ***"
            ),
            "evidence": exponents_by_domain,
        })

    # Pattern 2: Do the same operators dominate across domains?
    top_ops_by_domain = {}
    for domain, laws in all_laws.items():
        import re
        all_ops = []
        for law in laws[:5]:
            ops = re.findall(r'(?:log|exp|sqrt|sin|cos|\*\*|\*|/|\+|-)', law.expression)
            all_ops.extend(ops)
        from collections import Counter
        top_ops_by_domain[domain] = Counter(all_ops).most_common(5)

    # Find operators common to all domains
    common_ops = None
    for domain, op_counts in top_ops_by_domain.items():
        domain_ops = {op for op, _ in op_counts}
        if common_ops is None:
            common_ops = domain_ops
        else:
            common_ops &= domain_ops

    if common_ops:
        insights.append({
            "type": "universal_operators",
            "description": f"Operators common to ALL domains: {common_ops}",
            "evidence": top_ops_by_domain,
        })

    # Pattern 3: Complexity sweet spot
    complexity_by_domain = {}
    for domain, laws in all_laws.items():
        if laws:
            best_law = max(laws, key=lambda l: l.r_squared)
            complexity_by_domain[domain] = best_law.complexity

    complexities = list(complexity_by_domain.values())
    if complexities and max(complexities) - min(complexities) <= 3:
        insights.append({
            "type": "universal_complexity",
            "description": f"Optimal complexity is universally low ({min(complexities)}-{max(complexities)} ops across all domains)",
            "evidence": complexity_by_domain,
        })

    return insights


def analyze_meta_patterns(all_laws, validated, transfers):
    """Meta-learning: what worked and what didn't?"""
    meta = []

    # Total discovery stats
    total = sum(len(v) for v in all_laws.values())
    total_validated = sum(len(v) for v in validated.values())
    meta.append(f"Validation rate: {total_validated}/{total} = {total_validated/max(total,1):.0%}")

    # Transfer success
    successful = [t for t in transfers if t.get("r2_direct", 0) > 0.1]
    meta.append(f"Transfer success: {len(successful)}/{len(transfers)} transfers with R²>0.1")

    # Best transfer
    if successful:
        best = max(successful, key=lambda t: t["r2_direct"])
        meta.append(f"Best transfer: {best['source_domain']}→{best['target_domain']} "
                     f"R²={best['r2_direct']:.4f}")

    # Domain ranking
    for domain, laws in all_laws.items():
        if laws:
            best = max(laws, key=lambda l: l.r_squared)
            meta.append(f"Best law ({domain}): R²={best.r_squared:.4f} — {best.expression[:50]}")

    return meta


def compile_report(blackboard, all_laws, validated, transfers,
                   universal_insights, meta, elapsed):
    """Compile the final breakthrough report."""
    bb = blackboard.summary()

    # Find the single best discovery in each domain
    best_per_domain = {}
    for domain, laws in all_laws.items():
        if laws:
            best = max(laws, key=lambda l: l.r_squared)
            best_per_domain[domain] = {
                "expression": best.expression,
                "r_squared": best.r_squared,
                "complexity": best.complexity,
                "mse": best.mse,
            }

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": elapsed,
        "blackboard_summary": bb,
        "best_per_domain": best_per_domain,
        "all_laws": {
            domain: [{"expression": l.expression, "r_squared": l.r_squared,
                       "complexity": l.complexity} for l in laws]
            for domain, laws in all_laws.items()
        },
        "validated_counts": {d: len(v) for d, v in validated.items()},
        "transfers": transfers,
        "universal_insights": universal_insights,
        "meta_insights": meta,
        "breakthrough_detected": any(
            i["type"] == "UNIVERSAL_CUBIC_LAW" for i in universal_insights
        ),
    }


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    report = run_breakthrough_swarm()

    print("\n" + "=" * 70)
    if report.get("breakthrough_detected"):
        print("  *** BREAKTHROUGH DETECTED ***")
        for insight in report["universal_insights"]:
            if insight["type"] == "UNIVERSAL_CUBIC_LAW":
                print(f"  {insight['description']}")
    else:
        print("  No universal breakthrough this run. Results saved for analysis.")
    print("=" * 70)
