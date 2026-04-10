"""
Dimensional analysis utilities — Buckingham Pi theorem and
symmetry-aware feature construction for orbital dynamics.

Provides automatic construction of dimensionless groups from
physical quantities, enforcing the Pi theorem to reduce the
parameter space before symbolic regression.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from itertools import combinations


# ---------------------------------------------------------------------------
# Dimension representation
# ---------------------------------------------------------------------------
# Base dimensions for orbital mechanics: [Mass, Length, Time]
DIM_LABELS = ["M", "L", "T"]
N_BASE_DIMS = 3


@dataclass
class PhysicalQuantity:
    """A named physical quantity with its dimensional exponents [M, L, T]."""
    name: str
    dimensions: np.ndarray   # shape (3,), exponents of [M, L, T]
    value: float = 1.0


# Standard quantities in orbital mechanics (G=1 normalisation)
STANDARD_QUANTITIES = {
    "mass":          np.array([1, 0, 0], dtype=float),
    "length":        np.array([0, 1, 0], dtype=float),
    "time":          np.array([0, 0, 1], dtype=float),
    "velocity":      np.array([0, 1, -1], dtype=float),
    "acceleration":  np.array([0, 1, -2], dtype=float),
    "energy":        np.array([1, 2, -2], dtype=float),
    "ang_momentum":  np.array([1, 2, -1], dtype=float),
    "grav_param":    np.array([0, 3, -2], dtype=float),  # G*M
}


# ---------------------------------------------------------------------------
# Buckingham Pi theorem
# ---------------------------------------------------------------------------
def find_dimensionless_groups(quantities: list[PhysicalQuantity]) -> list[np.ndarray]:
    """
    Apply the Buckingham Pi theorem to find independent dimensionless
    groups from a list of physical quantities.

    Returns list of exponent vectors such that
    prod(q_i^{alpha_i}) is dimensionless.
    """
    n = len(quantities)
    # Build dimension matrix D: (n_base_dims x n_quantities)
    D = np.array([q.dimensions for q in quantities]).T  # (3, n)

    # Find null space of D (the Pi groups)
    rank = np.linalg.matrix_rank(D)
    n_pi = n - rank  # number of independent dimensionless groups

    if n_pi <= 0:
        return []

    # Use SVD to find null space
    _, S, Vt = np.linalg.svd(D, full_matrices=True)
    # Null space = last n_pi rows of Vt
    null_space = Vt[rank:]

    # Clean up near-zero entries
    pi_groups = []
    for row in null_space:
        row[np.abs(row) < 1e-10] = 0.0
        # Normalise so the largest exponent is ±1
        max_abs = np.max(np.abs(row))
        if max_abs > 1e-10:
            row = row / max_abs
        pi_groups.append(row)

    return pi_groups


def construct_pi_values(
    quantities: list[PhysicalQuantity],
    pi_groups: list[np.ndarray],
) -> list[float]:
    """Evaluate each Pi group from the numerical values of quantities."""
    values = np.array([q.value for q in quantities])
    pi_values = []
    for exponents in pi_groups:
        # product of values^exponents
        pv = np.prod(values ** exponents)
        pi_values.append(float(pv))
    return pi_values


# ---------------------------------------------------------------------------
# Orbital-specific dimensionless groups
# ---------------------------------------------------------------------------
def orbital_dimensionless_features(
    m_star: float,
    masses: list[float],
    semi_major_axes: list[float],
    eccentricities: list[float],
    inclinations: list[float],
) -> dict[str, list[float]]:
    """
    Construct the standard dimensionless groups for an N-planet system:
      - mu_i = m_i / m_star                   (mass ratios)
      - alpha_ij = a_i / a_j                  (axis ratios)
      - e_i                                    (already dimensionless)
      - inc_i                                  (already dimensionless)
      - delta_ij = (a_j - a_i) / R_H,mut      (Hill separations)
      - epsilon_i = e_i * (m_star/m_i)^{1/3}  (reduced eccentricity)
      - K_ij = mu_ij^{-2/7} * |alpha - alpha_res|  (resonance overlap)
    """
    n = len(masses)
    result: dict[str, list[float]] = {
        "mu": [],
        "epsilon": [],
        "e": list(eccentricities),
        "inc": list(inclinations),
        "alpha": [],
        "delta_Hill": [],
        "K_overlap": [],
    }

    for i in range(n):
        mu_i = masses[i] / m_star
        result["mu"].append(mu_i)
        eps_i = eccentricities[i] * (m_star / max(masses[i], 1e-30)) ** (1.0 / 3.0)
        result["epsilon"].append(eps_i)

    for i in range(n):
        for j in range(i + 1, n):
            alpha = semi_major_axes[i] / semi_major_axes[j]
            result["alpha"].append(alpha)

            # Mutual Hill radius
            mu_sum = (masses[i] + masses[j]) / m_star
            rH = 0.5 * (semi_major_axes[i] + semi_major_axes[j]) * (mu_sum / 3.0) ** (1.0 / 3.0)
            delta = (semi_major_axes[j] - semi_major_axes[i]) / max(rH, 1e-30)
            result["delta_Hill"].append(delta)

            # Wisdom resonance overlap parameter
            period_ratio = (semi_major_axes[j] / semi_major_axes[i]) ** 1.5
            nearest_res = _nearest_first_order_mmr(period_ratio)
            K = mu_sum ** (-2.0 / 7.0) * nearest_res if mu_sum > 1e-30 else 0.0
            result["K_overlap"].append(K)

    return result


def _nearest_first_order_mmr(period_ratio: float) -> float:
    """Distance to nearest first-order mean-motion resonance p+1:p."""
    min_dist = np.inf
    for p in range(1, 10):
        res = (p + 1) / p
        dist = abs(period_ratio - res)
        if dist < min_dist:
            min_dist = dist
    return min_dist


# ---------------------------------------------------------------------------
# Symmetry constraints
# ---------------------------------------------------------------------------
@dataclass
class SymmetryConstraint:
    """
    Represents a symmetry the micro-law must satisfy.
    transform: function mapping feature dict -> transformed feature dict
    invariant: whether the law's output should be unchanged (True)
               or flip sign (False, for pseudo-scalars)
    """
    name: str
    description: str


# Known symmetries of orbital dynamics
ORBITAL_SYMMETRIES = [
    SymmetryConstraint(
        name="parity_Omega",
        description="Invariance under Ω_i -> Ω_i + const (rotational symmetry about z-axis)",
    ),
    SymmetryConstraint(
        name="time_reversal",
        description="Under t -> -t, velocities flip sign. Stability is time-reversal invariant.",
    ),
    SymmetryConstraint(
        name="scale_invariance",
        description="Under a_i -> λ·a_i, t -> λ^{3/2}·t (Kepler scaling). "
                    "Dimensionless groups are invariant.",
    ),
    SymmetryConstraint(
        name="permutation",
        description="For identical-mass planets, law is symmetric under planet index permutation.",
    ),
]


def enforce_dimensional_consistency(
    exponent_vector: np.ndarray,
    quantity_dimensions: np.ndarray,
) -> bool:
    """
    Check whether a candidate symbolic expression (represented by
    exponents of input quantities) is dimensionally consistent
    (i.e., produces a dimensionless output).

    exponent_vector: shape (n_quantities,)
    quantity_dimensions: shape (n_quantities, 3)
    """
    net_dim = quantity_dimensions.T @ exponent_vector  # shape (3,)
    return bool(np.allclose(net_dim, 0.0, atol=1e-10))


# ---------------------------------------------------------------------------
# Feature augmentation with Pi groups
# ---------------------------------------------------------------------------
def augment_features_with_pi_groups(
    raw_features: np.ndarray,
    feature_dimensions: list[np.ndarray],
    feature_names: list[str],
) -> tuple[np.ndarray, list[str]]:
    """
    Given raw (possibly dimensional) features, compute all independent
    Pi groups and append them as additional features.
    """
    # Build PhysicalQuantity list for one sample
    quantities = [
        PhysicalQuantity(name=feature_names[i], dimensions=feature_dimensions[i])
        for i in range(len(feature_names))
    ]
    pi_groups = find_dimensionless_groups(quantities)

    if not pi_groups:
        return raw_features, feature_names

    n_samples = raw_features.shape[0]
    pi_features = np.zeros((n_samples, len(pi_groups)))
    pi_names = []

    for g_idx, exponents in enumerate(pi_groups):
        pi_name = "Pi_" + "_".join(
            f"{feature_names[i]}^{exponents[i]:.2f}"
            for i in range(len(exponents))
            if abs(exponents[i]) > 1e-10
        )
        pi_names.append(pi_name)
        for s in range(n_samples):
            vals = raw_features[s]
            # Avoid log-domain issues
            safe_vals = np.where(np.abs(vals) < 1e-30, 1e-30, vals)
            pi_features[s, g_idx] = np.prod(np.abs(safe_vals) ** exponents)

    augmented = np.hstack([raw_features, pi_features])
    all_names = feature_names + pi_names
    return augmented, all_names
