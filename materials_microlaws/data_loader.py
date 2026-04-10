"""
Data loading and materials database interface.

Supports loading perovskite band gap data, alloy formation energies,
and catalytic activity datasets from Materials Project or local caches.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


# ---------------------------------------------------------------------------
# Physical descriptor definitions with dimensional metadata
# ---------------------------------------------------------------------------

@dataclass
class Descriptor:
    """A physically meaningful descriptor with dimensional information."""
    name: str
    unit: str  # e.g. "eV", "Å", "dimensionless"
    dimensions: dict[str, int] = field(default_factory=dict)
    # dimensions maps base quantities -> exponents: {"energy": 1, "length": -3}
    description: str = ""


# Standard perovskite descriptors (ABX3)
PEROVSKITE_DESCRIPTORS = [
    Descriptor("r_A", "Å", {"length": 1}, "Ionic radius of A-site cation"),
    Descriptor("r_B", "Å", {"length": 1}, "Ionic radius of B-site cation"),
    Descriptor("r_X", "Å", {"length": 1}, "Ionic radius of X-site anion"),
    Descriptor("EN_A", "Pauling", {"dimensionless": 1}, "Electronegativity of A-site"),
    Descriptor("EN_B", "Pauling", {"dimensionless": 1}, "Electronegativity of B-site"),
    Descriptor("EN_X", "Pauling", {"dimensionless": 1}, "Electronegativity of X-site"),
    Descriptor("t_factor", "dimensionless", {"dimensionless": 1},
               "Goldschmidt tolerance factor (r_A + r_X) / (sqrt(2)*(r_B + r_X))"),
    Descriptor("octahedral_factor", "dimensionless", {"dimensionless": 1},
               "Octahedral factor r_B / r_X"),
    Descriptor("delta_EN", "Pauling", {"dimensionless": 1},
               "Electronegativity difference |EN_A - EN_B|"),
    Descriptor("Z_A", "dimensionless", {"dimensionless": 1}, "Atomic number of A-site"),
    Descriptor("Z_B", "dimensionless", {"dimensionless": 1}, "Atomic number of B-site"),
    Descriptor("m_A", "amu", {"mass": 1}, "Atomic mass of A-site"),
    Descriptor("m_B", "amu", {"mass": 1}, "Atomic mass of B-site"),
    Descriptor("IE_A", "eV", {"energy": 1}, "First ionization energy of A-site"),
    Descriptor("IE_B", "eV", {"energy": 1}, "First ionization energy of B-site"),
    Descriptor("EA_B", "eV", {"energy": 1}, "Electron affinity of B-site"),
]


@dataclass
class MaterialsDataset:
    """Container for a materials property dataset."""
    name: str
    X: np.ndarray          # (N, D) descriptor matrix
    y: np.ndarray          # (N,) target property
    descriptors: list[Descriptor]
    compositions: list[str]  # chemical formulas
    target_name: str
    target_unit: str
    metadata: dict = field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        return self.X.shape[0]

    @property
    def n_descriptors(self) -> int:
        return self.X.shape[1]

    def train_test_split(self, test_frac: float = 0.2, seed: int = 42):
        """Split into train/test with deterministic seed."""
        rng = np.random.RandomState(seed)
        n = self.n_samples
        idx = rng.permutation(n)
        split = int(n * (1 - test_frac))
        train_idx, test_idx = idx[:split], idx[split:]
        return (
            MaterialsDataset(
                name=f"{self.name}_train", X=self.X[train_idx], y=self.y[train_idx],
                descriptors=self.descriptors,
                compositions=[self.compositions[i] for i in train_idx],
                target_name=self.target_name, target_unit=self.target_unit,
                metadata={**self.metadata, "split": "train"},
            ),
            MaterialsDataset(
                name=f"{self.name}_test", X=self.X[test_idx], y=self.y[test_idx],
                descriptors=self.descriptors,
                compositions=[self.compositions[i] for i in test_idx],
                target_name=self.target_name, target_unit=self.target_unit,
                metadata={**self.metadata, "split": "test"},
            ),
        )


# ---------------------------------------------------------------------------
# Synthetic perovskite dataset generator (for demo / no-API mode)
# ---------------------------------------------------------------------------

# Elemental data for common perovskite constituents
_ELEMENT_DATA = {
    # element: (radius_Å, EN_pauling, Z, mass_amu, IE_eV, EA_eV)
    "Cs": (1.88, 0.79, 55, 132.91, 3.89, 0.47),
    "Rb": (1.72, 0.82, 37, 85.47, 4.18, 0.49),
    "K":  (1.64, 0.82, 19, 39.10, 4.34, 0.50),
    "Na": (1.39, 0.93, 11, 22.99, 5.14, 0.55),
    "Ba": (1.61, 0.89, 56, 137.33, 5.21, 0.15),
    "Sr": (1.44, 0.95, 38, 87.62, 5.69, 0.05),
    "Ca": (1.34, 1.00, 20, 40.08, 6.11, 0.02),
    "Pb": (1.19, 2.33, 82, 207.2, 7.42, 0.36),
    "Sn": (1.12, 1.96, 50, 118.71, 7.34, 1.11),
    "Ge": (0.73, 2.01, 32, 72.63, 7.90, 1.23),
    "Ti": (0.605, 1.54, 22, 47.87, 6.83, 0.08),
    "Zr": (0.72, 1.33, 40, 91.22, 6.63, 0.43),
    "Hf": (0.71, 1.30, 72, 178.49, 6.83, 0.00),
    "Cl": (1.81, 3.16, 17, 35.45, 12.97, 3.61),
    "Br": (1.96, 2.96, 35, 79.90, 11.81, 3.36),
    "I":  (2.20, 2.66, 53, 126.90, 10.45, 3.06),
    "F":  (1.33, 3.98, 9, 19.00, 17.42, 3.40),
    "O":  (1.40, 3.44, 8, 16.00, 13.62, 1.46),
}

# Common ABX3 compositions
_PEROVSKITE_COMPOSITIONS = [
    ("Cs", "Pb", "I"), ("Cs", "Pb", "Br"), ("Cs", "Pb", "Cl"),
    ("Cs", "Sn", "I"), ("Cs", "Sn", "Br"), ("Cs", "Sn", "Cl"),
    ("Cs", "Ge", "I"), ("Cs", "Ge", "Br"), ("Cs", "Ge", "Cl"),
    ("Rb", "Pb", "I"), ("Rb", "Pb", "Br"), ("Rb", "Pb", "Cl"),
    ("Rb", "Sn", "I"), ("Rb", "Sn", "Br"),
    ("K",  "Pb", "I"), ("K",  "Pb", "Br"),
    ("Na", "Pb", "I"), ("Na", "Pb", "Br"),
    ("Ba", "Ti", "O"), ("Sr", "Ti", "O"), ("Ca", "Ti", "O"),
    ("Ba", "Zr", "O"), ("Sr", "Zr", "O"), ("Ca", "Zr", "O"),
    ("Ba", "Hf", "O"), ("Sr", "Hf", "O"),
    ("Cs", "Sn", "F"), ("Rb", "Ge", "F"),
    ("Rb", "Sn", "Cl"), ("K", "Sn", "I"),
    ("Na", "Sn", "Br"), ("Ba", "Sn", "O"),
    ("Sr", "Sn", "O"), ("Ca", "Sn", "O"),
    ("Ba", "Ge", "O"), ("Sr", "Ge", "O"),
    ("Cs", "Ti", "F"), ("Rb", "Ti", "F"),
    ("K",  "Ti", "F"), ("Ba", "Pb", "O"),
]


def _compute_descriptors(A: str, B: str, X: str) -> dict[str, float]:
    """Compute physically meaningful descriptors for ABX3 perovskite."""
    dA, dB, dX = _ELEMENT_DATA[A], _ELEMENT_DATA[B], _ELEMENT_DATA[X]
    rA, rB, rX = dA[0], dB[0], dX[0]

    t = (rA + rX) / (np.sqrt(2) * (rB + rX))
    mu = rB / rX

    return {
        "r_A": rA, "r_B": rB, "r_X": rX,
        "EN_A": dA[1], "EN_B": dB[1], "EN_X": dX[1],
        "t_factor": t, "octahedral_factor": mu,
        "delta_EN": abs(dA[1] - dB[1]),
        "Z_A": dA[2], "Z_B": dB[2],
        "m_A": dA[3], "m_B": dB[3],
        "IE_A": dA[4], "IE_B": dB[4],
        "EA_B": dB[5],
    }


def _synthetic_band_gap(desc: dict[str, float], noise_std: float = 0.08) -> float:
    """
    Generate a synthetic but physically motivated band gap.

    Uses a formula inspired by known perovskite structure-property relationships:
      Eg ≈ α·(EN_X - EN_B) + β/t + γ·μ + δ·(IE_B - EA_B) + noise

    where t = tolerance factor, μ = octahedral factor.
    """
    EN_diff = desc["EN_X"] - desc["EN_B"]
    t = desc["t_factor"]
    mu = desc["octahedral_factor"]
    IE_B = desc["IE_B"]
    EA_B = desc["EA_B"]

    # Coefficients calibrated to produce realistic 0–5 eV range
    Eg = (
        0.45 * EN_diff
        + 0.8 / (t + 0.1)
        - 0.3 * mu
        + 0.12 * (IE_B - EA_B)
        - 0.5
    )
    # Clamp to physically reasonable range
    Eg = np.clip(Eg, 0.0, 8.0)

    # Use composition-seeded noise for reproducibility
    seed_str = f"{desc['Z_A']}-{desc['Z_B']}-{desc['r_X']}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16) % (2**31)
    rng = np.random.RandomState(seed)
    Eg += rng.normal(0, noise_std)
    return float(np.clip(Eg, 0.0, 8.0))


def load_perovskite_dataset(
    source: str = "synthetic",
    cache_dir: Optional[str] = None,
    noise_std: float = 0.08,
) -> MaterialsDataset:
    """
    Load a perovskite band gap dataset.

    Parameters
    ----------
    source : str
        "synthetic" for reproducible synthetic data,
        "matminer" to fetch from matminer (requires internet).
    cache_dir : str, optional
        Directory to cache downloaded data.
    noise_std : float
        Noise level for synthetic data.
    """
    if source == "synthetic":
        return _load_synthetic_perovskites(noise_std)
    elif source == "matminer":
        return _load_matminer_perovskites(cache_dir)
    else:
        raise ValueError(f"Unknown source: {source}")


def _load_synthetic_perovskites(noise_std: float) -> MaterialsDataset:
    """Generate synthetic perovskite dataset."""
    logger.info("Generating synthetic perovskite band gap dataset...")

    rows = []
    compositions = []
    targets = []

    for A, B, X in _PEROVSKITE_COMPOSITIONS:
        desc = _compute_descriptors(A, B, X)
        Eg = _synthetic_band_gap(desc, noise_std)
        rows.append(desc)
        compositions.append(f"{A}{B}{X}3")
        targets.append(Eg)

    df = pd.DataFrame(rows)
    descriptor_names = [d.name for d in PEROVSKITE_DESCRIPTORS]
    X = df[descriptor_names].values
    y = np.array(targets)

    logger.info(f"  → {len(compositions)} perovskites, {len(descriptor_names)} descriptors")
    logger.info(f"  → Band gap range: [{y.min():.2f}, {y.max():.2f}] eV")

    return MaterialsDataset(
        name="perovskite_band_gap_synthetic",
        X=X, y=y,
        descriptors=PEROVSKITE_DESCRIPTORS,
        compositions=compositions,
        target_name="band_gap",
        target_unit="eV",
        metadata={"source": "synthetic", "noise_std": noise_std},
    )


def _load_matminer_perovskites(cache_dir: Optional[str]) -> MaterialsDataset:
    """Load perovskite data from matminer."""
    try:
        from matminer.datasets import load_dataset
    except ImportError:
        raise ImportError("matminer is required for real data loading. "
                          "Install with: pip install matminer")

    logger.info("Loading perovskite data from matminer...")
    df = load_dataset("castelli_perovskites")

    # Use available columns; compute descriptors from composition
    # This is a simplified loader — full version would parse structures
    compositions = df["formula"].tolist()
    y = df["gap gllbsc"].values  # band gap from GLLB-SC functional

    # Build descriptor matrix from available features
    from matminer.featurizers.composition import ElementProperty
    from pymatgen.core import Composition

    ep = ElementProperty.from_preset("magpie")
    feat_df = pd.DataFrame({"composition": [Composition(c) for c in compositions]})
    feat_df = ep.featurize_dataframe(feat_df, "composition", ignore_errors=True)
    feat_df = feat_df.drop(columns=["composition"]).dropna(axis=1)

    # Use generic descriptors for matminer data
    descriptor_list = [
        Descriptor(name=col, unit="varies", description=f"Matminer feature: {col}")
        for col in feat_df.columns
    ]
    X = feat_df.values

    # Align length
    valid = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
    X, y = X[valid], y[valid]
    compositions = [compositions[i] for i in range(len(compositions)) if valid[i]]

    logger.info(f"  → {len(compositions)} perovskites, {X.shape[1]} descriptors")

    return MaterialsDataset(
        name="perovskite_band_gap_matminer",
        X=X, y=y,
        descriptors=descriptor_list,
        compositions=compositions,
        target_name="band_gap",
        target_unit="eV",
        metadata={"source": "matminer_castelli"},
    )
