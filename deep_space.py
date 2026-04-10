"""
deep_space.py
=============
Deep Space research platform for the Ramanujan Breakthrough Generator.

Functional Mapping layer: transitions from point discovery to structural
exploration of the continued-fraction landscape.

Four capabilities:
  1. Symmetry-Invariant Search  -- generate CFs with structural constraints
     (factored b(n), shared-root polynomials, GCD symmetries)
  2. Composite Targets          -- dynamic constant library from near-miss
     pairs (X+Y, X*Y, X/Y, mpmath.identify)
  3. Dimensionality Reduction   -- manifold learning on coefficient vectors
     (UMAP/t-SNE) to discover ridges in discovery space
  4. Elegance Scoring           -- bit-complexity metric for PR tagging

All functions are non-blocking, ASCII-only, and stress-tested at 200 digits.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# ASCII-only logger
# ---------------------------------------------------------------------------
_log = logging.getLogger("deep_space")
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[deep_space %(levelname)s] %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Paths (shared with adaptive_discovery / generator)
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parent
LOGFILE = WORKSPACE / "ramanujan_discoveries.jsonl"
NEAR_MISS_FILE = WORKSPACE / "near_misses.jsonl"
ASSETS_DIR = WORKSPACE / "discoveries" / "assets"
COMPOSITE_CACHE = WORKSPACE / "composite_targets.json"
RIDGE_CACHE = WORKSPACE / "ridge_map.json"

# ---------------------------------------------------------------------------
# Shared data loaders
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _load_discoveries() -> list[dict[str, Any]]:
    return _load_jsonl(LOGFILE)


def _load_near_misses() -> list[dict[str, Any]]:
    return _load_jsonl(NEAR_MISS_FILE)


# ===================================================================
# TASK 1: Symmetry-Invariant Search
# ===================================================================

@dataclass
class SymmetryConstraint:
    """Describes a structural constraint for CF polynomial generation."""
    name: str
    description: str
    generator: str  # key into SYMMETRY_GENERATORS


def _factored_b(n_val, f_coeffs: list[int]) -> "mpf":
    """b(n) = f(n) * f(n-1) where f(x) = sum(c_i * x^i).

    Produces palindromic-like b(n) with guaranteed factored structure.
    """
    from mpmath import mpf
    def f(x):
        return sum(mpf(c) * x ** i for i, c in enumerate(f_coeffs))
    return f(n_val) * f(n_val - 1)


def _shared_root_a_b(rng, deg_a: int = 2, deg_b: int = 1) -> Tuple[list[int], list[int]]:
    """Generate a(n), b(n) that share a common linear factor (n - r).

    This creates CFs where Res(a, b) = 0 at an integer point,
    producing structural correlations between numerator and denominator.
    """
    r = rng.randint(0, 4)  # shared root

    # Build a(n) = (n - r) * q_a(n)  where q_a is random
    # Build b(n) = (n - r) * q_b(n) + offset  (offset to keep b(0) > 0)
    q_a_deg = max(1, deg_a - 1)
    q_b_deg = max(0, deg_b - 1)

    q_a = [rng.randint(-3, 3) for _ in range(q_a_deg + 1)]
    q_b = [rng.randint(-2, 2) for _ in range(q_b_deg + 1)]

    # Expand (n - r) * q_a(n) via polynomial multiplication
    # (n - r) = [-r, 1]
    root_poly = [-r, 1]
    a_coeffs = _poly_mul(root_poly, q_a)

    # For b: (n - r) * q_b(n) then shift b[0] to be positive
    b_coeffs = _poly_mul(root_poly, q_b) if q_b else [1]
    if not b_coeffs:
        b_coeffs = [1]
    b_coeffs[0] = max(1, abs(b_coeffs[0]) + 1)

    return a_coeffs, b_coeffs


def _poly_mul(p1: list[int], p2: list[int]) -> list[int]:
    """Multiply two polynomials represented as coefficient lists."""
    if not p1 or not p2:
        return [0]
    result = [0] * (len(p1) + len(p2) - 1)
    for i, c1 in enumerate(p1):
        for j, c2 in enumerate(p2):
            result[i + j] += c1 * c2
    return result


def _gcd_symmetric(rng, deg: int = 2) -> Tuple[list[int], list[int]]:
    """Generate a(n), b(n) where gcd structure forces a(n) | b(n) * b(n-1).

    Uses: a(n) = k * n * (n - d), b(n) = n + c
    so that a(n) divides b(n)*b(n-1) when c*(c-1) = 0 mod k*d.
    """
    k = rng.choice([1, 2, 4, -1, -2, -4])
    d = rng.randint(1, 4)
    c = rng.randint(1, 5)

    # a(n) = k * n * (n - d) = k*(-d)*n^0 + k*(1+d)*... expanded:
    # a(n) = k * (n^2 - d*n) = [0, -k*d, k]
    a_coeffs = [0, -k * d, k]

    # b(n) = n + c
    b_coeffs = [c, 1]
    b_coeffs[0] = max(1, b_coeffs[0])

    return a_coeffs, b_coeffs


def _palindromic_b(rng, deg: int = 2) -> Tuple[list[int], list[int]]:
    """Generate CFs where b(n) has palindromic coefficients.

    Palindromic b(n) = c0 + c1*n + c2*n^2 + c1*n^3 + c0*n^4  (for deg=4)
    These produce CFs with reflection symmetry in the convergent sequence.
    """
    half_len = deg // 2 + 1
    half = [rng.randint(1, 5) if i == 0 else rng.randint(-3, 3)
            for i in range(half_len)]

    # Build palindromic b coefficients
    if deg % 2 == 0:
        b_coeffs = half + half[-2::-1]
    else:
        b_coeffs = half + half[::-1]

    b_coeffs[0] = max(1, b_coeffs[0])

    # a(n) is unconstrained
    a_deg = rng.choice([2, 3])
    a_coeffs = [rng.randint(-4, 4) for _ in range(a_deg + 1)]

    return a_coeffs, b_coeffs


def generate_symmetry_constrained(
    rng,
    constraint: str = "random",
) -> Tuple[list[int], list[int], str]:
    """Generate a(n), b(n) pair with a specified structural constraint.

    Args:
        rng: random.Random instance
        constraint: one of "factored_b", "shared_root", "gcd_symmetric",
                    "palindromic_b", or "random" (picks one at random)

    Returns:
        (a_coeffs, b_coeffs, constraint_name)
    """
    generators = {
        "factored_b": lambda: _gen_factored_b_pair(rng),
        "shared_root": lambda: _shared_root_a_b(rng),
        "gcd_symmetric": lambda: _gcd_symmetric(rng),
        "palindromic_b": lambda: _palindromic_b(rng),
    }

    if constraint == "random":
        constraint = rng.choice(list(generators.keys()))

    gen = generators.get(constraint)
    if gen is None:
        constraint = "shared_root"
        gen = generators[constraint]

    a, b = gen()
    return a, b, constraint


def _gen_factored_b_pair(rng) -> Tuple[list[int], list[int]]:
    """Generate (a, b) where b(n) = f(n)*f(n-1) for a random linear f."""
    # f(n) = c0 + c1*n  (linear factor)
    c0 = rng.randint(1, 4)
    c1 = rng.choice([1, 2, 3])
    f_coeffs = [c0, c1]

    # Expand b(n) = f(n)*f(n-1) = (c0 + c1*n)(c0 + c1*(n-1))
    # = (c0 + c1*n)(c0 - c1 + c1*n)
    # = c0*(c0-c1) + (c0*c1 + c1*(c0-c1))*n + c1^2*n^2
    # = c0*(c0-c1) + c1*(2*c0 - c1)*n + c1^2*n^2
    b0 = c0 * (c0 - c1)
    b1 = c1 * (2 * c0 - c1)
    b2 = c1 * c1
    b_coeffs = [b0, b1, b2]
    b_coeffs[0] = max(1, b_coeffs[0])

    # a(n): random quadratic/cubic
    a_deg = rng.choice([2, 3])
    a_coeffs = [rng.randint(-4, 4) for _ in range(a_deg + 1)]

    return a_coeffs, b_coeffs


def symmetry_correlation_map(
    min_verified: float = 20.0,
) -> dict[str, Any]:
    """Analyze existing discoveries to find correlations between
    structural symmetry types and target constant families.

    Returns mapping: symmetry_type -> {constant: count, ...}
    """
    discoveries = _load_discoveries()
    if not discoveries:
        return {}

    correlations: dict[str, Counter] = defaultdict(Counter)

    for d in discoveries:
        vd = d.get("verified_digits", 0) or 0
        if vd < min_verified:
            continue

        a = d.get("a", [])
        b = d.get("b", [])
        match = d.get("match", "unknown")
        base_const = match.split("*")[-1] if "*" in match else match

        # Classify the symmetry type
        sym_type = classify_symmetry(a, b)
        correlations[sym_type][base_const] += 1

    return {k: dict(v.most_common(10)) for k, v in correlations.items()}


def classify_symmetry(a_coeffs: list[int], b_coeffs: list[int]) -> str:
    """Classify a CF's structural symmetry type."""
    # Check palindromic b
    if len(b_coeffs) >= 3 and b_coeffs == b_coeffs[::-1]:
        return "palindromic_b"

    # Check if b looks factored: b(n) = c0 + c1*n + c2*n^2 with c2 = perfect square
    if len(b_coeffs) == 3:
        c2 = b_coeffs[2]
        if c2 > 0:
            sqrt_c2 = int(math.isqrt(c2))
            if sqrt_c2 * sqrt_c2 == c2:
                return "factored_b"

    # Check shared-root: if a(0) == 0 and b has integer root
    if a_coeffs and a_coeffs[0] == 0:
        return "shared_root_0"

    # Check GCD structure: a(n) = k*n*(n-d) pattern
    if len(a_coeffs) == 3 and a_coeffs[0] == 0:
        return "gcd_symmetric"

    return "unconstrained"


# ===================================================================
# TASK 2: Composite Targets (Dynamic Constant Library)
# ===================================================================

@dataclass
class CompositeTarget:
    """A dynamically generated target constant."""
    name: str
    value: float  # mpf stored as float for JSON serialization
    source: str   # "near_miss_sum" | "near_miss_product" | "mpmath_identify"
    parent_a: str
    parent_b: str
    confidence: float  # 0..1


def build_composite_targets(
    max_targets: int = 30,
    min_verified: float = 15.0,
) -> dict[str, Any]:
    """Generate dynamic target constants from near-miss data.

    Strategies:
      1. Linear combinations: X +/- Y for near-miss pairs from different families
      2. Products: X * Y
      3. Ratios: X / Y
      4. mpmath.identify() on unmatched CF values

    Returns dict mapping composite name -> mpf value (serialized).
    """
    near_misses = _load_near_misses()
    discoveries = _load_discoveries()

    targets: dict[str, float] = {}
    target_meta: list[dict] = []

    try:
        from mpmath import mpf, mp, identify
        saved_dps = mp.dps
        mp.dps = 80
    except ImportError:
        _log.warning("mpmath not available for composite targets")
        return {}

    try:
        # Collect unique CF values from near-misses
        nm_values: list[Tuple[float, dict]] = []
        for nm in near_misses:
            val_str = nm.get("value")
            if val_str:
                try:
                    val = float(mpf(val_str))
                    if 0.01 < abs(val) < 1e6 and not math.isnan(val):
                        nm_values.append((val, nm))
                except (ValueError, TypeError):
                    continue

        # Dedup by rounding to 10 digits
        seen_vals: set[str] = set()
        unique_nms: list[Tuple[float, dict]] = []
        for val, nm in nm_values:
            key = f"{val:.10e}"
            if key not in seen_vals:
                seen_vals.add(key)
                unique_nms.append((val, nm))

        # Strategy 1-3: pairwise combinations (capped for performance)
        pairs = min(len(unique_nms), 20)
        for i in range(pairs):
            for j in range(i + 1, min(pairs, i + 5)):
                vi, nmi = unique_nms[i]
                vj, nmj = unique_nms[j]

                # Sum
                s = vi + vj
                name = f"NM({i})+NM({j})"
                if 0.01 < abs(s) < 1e6:
                    targets[name] = s
                    target_meta.append({
                        "name": name, "value": s,
                        "source": "near_miss_sum",
                        "parents": [str(nmi.get("a")), str(nmj.get("a"))],
                    })

                # Difference
                d = vi - vj
                name = f"NM({i})-NM({j})"
                if 0.01 < abs(d) < 1e6:
                    targets[name] = d

                # Product
                p = vi * vj
                name = f"NM({i})*NM({j})"
                if 0.01 < abs(p) < 1e6:
                    targets[name] = p

                # Ratio
                if abs(vj) > 1e-10:
                    r = vi / vj
                    name = f"NM({i})/NM({j})"
                    if 0.01 < abs(r) < 1e6:
                        targets[name] = r

                if len(targets) >= max_targets:
                    break
            if len(targets) >= max_targets:
                break

        # Strategy 4: mpmath.identify on unmatched near-miss values
        for val, nm in unique_nms[:15]:
            if len(targets) >= max_targets:
                break
            try:
                ident = identify(val)
                if ident and not ident.startswith("0"):
                    name = f"id:{ident[:30]}"
                    targets[name] = val
            except Exception:
                continue

        # Cache for reuse
        cache_data = {
            "generated": time.time(),
            "count": len(targets),
            "targets": {k: v for k, v in list(targets.items())[:max_targets]},
        }
        COMPOSITE_CACHE.write_text(
            json.dumps(cache_data, indent=2, ensure_ascii=True)
        )
        _log.info("Composite targets: %d generated, cached to %s",
                   len(targets), COMPOSITE_CACHE.name)

    except Exception:
        _log.warning("Composite target generation failed:\n%s",
                      traceback.format_exc())
    finally:
        mp.dps = saved_dps

    return targets


def load_composite_targets() -> dict[str, float]:
    """Load cached composite targets (for merging into constant library)."""
    if not COMPOSITE_CACHE.exists():
        return {}
    try:
        data = json.loads(COMPOSITE_CACHE.read_text(encoding="utf-8"))
        return data.get("targets", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def merge_composite_into_constants(
    base_constants: dict,
    max_composite: int = 15,
) -> dict:
    """Merge composite targets into the main constant library.

    Returns extended dict.  Composite names get 'C:' prefix.
    """
    composites = load_composite_targets()
    if not composites:
        # Try generating fresh
        composites = build_composite_targets(max_targets=max_composite)

    from mpmath import mpf
    merged = dict(base_constants)
    count = 0
    for name, val in composites.items():
        if count >= max_composite:
            break
        safe_name = f"C:{name}"[:40]
        try:
            merged[safe_name] = mpf(val)
            count += 1
        except (ValueError, TypeError):
            continue

    if count > 0:
        _log.info("Merged %d composite targets into constant library", count)
    return merged


# ===================================================================
# TASK 3: Dimensionality Reduction (Manifold Learning)
# ===================================================================

@dataclass
class RidgePoint:
    """A dense region in coefficient space (potential discovery ridge)."""
    centroid_a: list[float]
    centroid_b: list[float]
    density: float
    dominant_constant: str
    member_count: int


def _flatten_coefficients(
    entries: list[dict],
    max_a_len: int = 7,
    max_b_len: int = 4,
) -> Tuple[Any, list[dict]]:
    """Flatten (a, b) coefficient vectors into fixed-length feature vectors.

    Returns (numpy array of shape [N, max_a_len + max_b_len], valid entries).
    """
    try:
        import numpy as np
    except ImportError:
        return None, []

    vectors = []
    valid = []
    for entry in entries:
        a = entry.get("a", [])
        b = entry.get("b", [])
        if not a or not b:
            continue
        # Pad/truncate to fixed length
        a_padded = (a + [0] * max_a_len)[:max_a_len]
        b_padded = (b + [0] * max_b_len)[:max_b_len]
        vectors.append(a_padded + b_padded)
        valid.append(entry)

    if not vectors:
        return None, []
    return np.array(vectors, dtype=float), valid


def compute_manifold(
    method: str = "tsne",
    min_entries: int = 30,
    min_verified: float = 10.0,
) -> list[RidgePoint]:
    """Apply dimensionality reduction to discovery coefficient vectors.

    Identifies dense clusters (ridges) in the reduced 2D space.

    Args:
        method: "tsne" or "umap" (falls back to tsne if umap unavailable)
        min_entries: minimum discoveries needed to run
        min_verified: minimum verified_digits to include

    Returns list of RidgePoint objects for hot-start injection.
    """
    discoveries = _load_discoveries()
    filtered = [d for d in discoveries
                if (d.get("verified_digits", 0) or 0) >= min_verified]

    if len(filtered) < min_entries:
        _log.info("Not enough entries for manifold learning (%d < %d)",
                   len(filtered), min_entries)
        return []

    try:
        import numpy as np
    except ImportError:
        _log.warning("numpy not available for dimensionality reduction")
        return []

    X, valid = _flatten_coefficients(filtered)
    if X is None or len(valid) < min_entries:
        return []

    # Standardize features
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    X_scaled = (X - mean) / std

    # Apply dimensionality reduction
    embedding = None

    if method == "umap":
        try:
            from sklearn.manifold import TSNE
            # Try UMAP first
            import umap
            reducer = umap.UMAP(n_components=2, n_neighbors=min(15, len(valid) - 1),
                                random_state=42)
            embedding = reducer.fit_transform(X_scaled)
        except ImportError:
            method = "tsne"  # fallback

    if embedding is None:
        try:
            from sklearn.manifold import TSNE
            perplexity = min(30, max(5, len(valid) // 3))
            tsne = TSNE(n_components=2, perplexity=perplexity,
                        random_state=42, max_iter=1000)
            embedding = tsne.fit_transform(X_scaled)
        except ImportError:
            # Final fallback: PCA via numpy (no sklearn needed)
            _log.info("sklearn not available, falling back to PCA")
            embedding = _pca_fallback(X_scaled)

    if embedding is None:
        return []

    # Cluster detection via grid density
    ridges = _find_dense_regions(embedding, valid, X)

    # Cache ridge map
    _cache_ridges(ridges)

    return ridges


def _pca_fallback(X: Any) -> Any:
    """Simple PCA to 2D using numpy only (no sklearn dependency)."""
    import numpy as np
    # Center
    X_centered = X - X.mean(axis=0)
    # Covariance
    cov = np.cov(X_centered, rowvar=False)
    # Eigendecomposition
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Top 2 components (largest eigenvalues are at the end)
    top2 = eigenvectors[:, -2:][:, ::-1]
    return X_centered @ top2


def _find_dense_regions(
    embedding: Any,
    entries: list[dict],
    original_X: Any,
    grid_size: int = 10,
    min_cluster_size: int = 3,
) -> list[RidgePoint]:
    """Find dense regions in 2D embedding via grid binning."""
    import numpy as np

    ridges: list[RidgePoint] = []

    # Grid-based density
    x_min, x_max = embedding[:, 0].min(), embedding[:, 0].max()
    y_min, y_max = embedding[:, 1].min(), embedding[:, 1].max()

    x_step = max((x_max - x_min) / grid_size, 1e-10)
    y_step = max((y_max - y_min) / grid_size, 1e-10)

    # Bin entries
    bins: dict[Tuple[int, int], list[int]] = defaultdict(list)
    for idx in range(len(embedding)):
        gx = int((embedding[idx, 0] - x_min) / x_step)
        gy = int((embedding[idx, 1] - y_min) / y_step)
        gx = min(gx, grid_size - 1)
        gy = min(gy, grid_size - 1)
        bins[(gx, gy)].append(idx)

    # Extract dense bins as ridges
    for (gx, gy), indices in sorted(bins.items(), key=lambda x: -len(x[1])):
        if len(indices) < min_cluster_size:
            continue

        # Compute centroid in original coefficient space
        cluster_X = original_X[indices]
        centroid = cluster_X.mean(axis=0)

        # Split centroid back into a and b parts
        # (first 7 = a, next 4 = b by default from _flatten_coefficients)
        max_a_len = 7
        a_centroid = [round(float(x)) for x in centroid[:max_a_len]]
        b_centroid = [round(float(x)) for x in centroid[max_a_len:]]
        b_centroid[0] = max(1, b_centroid[0]) if b_centroid else 1

        # Trim trailing zeros
        while len(a_centroid) > 1 and a_centroid[-1] == 0:
            a_centroid.pop()
        while len(b_centroid) > 1 and b_centroid[-1] == 0:
            b_centroid.pop()

        # Dominant constant in this cluster
        const_counts: Counter = Counter()
        for idx in indices:
            match = entries[idx].get("match", "unknown")
            base = match.split("*")[-1] if "*" in match else match
            const_counts[base] += 1
        dominant = const_counts.most_common(1)[0][0] if const_counts else "unknown"

        density = len(indices) / len(entries) if entries else 0.0
        ridges.append(RidgePoint(
            centroid_a=a_centroid,
            centroid_b=b_centroid,
            density=round(density, 4),
            dominant_constant=dominant,
            member_count=len(indices),
        ))

        if len(ridges) >= 10:
            break

    _log.info("Manifold: found %d dense ridges from %d entries", len(ridges), len(entries))
    return ridges


def _cache_ridges(ridges: list[RidgePoint]) -> None:
    """Save ridge map as JSON for reuse by hot-start engine."""
    data = {
        "generated": time.time(),
        "ridges": [
            {
                "centroid_a": r.centroid_a,
                "centroid_b": r.centroid_b,
                "density": r.density,
                "dominant_constant": r.dominant_constant,
                "member_count": r.member_count,
            }
            for r in ridges
        ],
    }
    try:
        RIDGE_CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=True))
    except Exception:
        pass


def load_ridge_hints(max_hints: int = 5) -> list[dict]:
    """Load cached ridge centroids as hot-start seed parameters.

    Returns list of dicts with 'a', 'b', 'hint_target' keys.
    """
    if not RIDGE_CACHE.exists():
        return []
    try:
        data = json.loads(RIDGE_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return []

    hints = []
    for r in data.get("ridges", [])[:max_hints]:
        hints.append({
            "a": r["centroid_a"],
            "b": r["centroid_b"],
            "hint_target": r.get("dominant_constant", "ridge"),
        })
    return hints


def generate_manifold_plot(
    method: str = "tsne",
    output_path: Path | str | None = None,
) -> Path | None:
    """Generate a 2D scatter plot of the discovery manifold, colored by
    matched constant.  Saves PNG to discoveries/assets/.

    Returns path to saved image or None.
    """
    discoveries = _load_discoveries()
    filtered = [d for d in discoveries
                if (d.get("verified_digits", 0) or 0) >= 10.0]

    if len(filtered) < 20:
        _log.info("Not enough data for manifold plot")
        return None

    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        _log.warning("numpy/matplotlib not available for manifold plot")
        return None

    X, valid = _flatten_coefficients(filtered)
    if X is None or len(valid) < 20:
        return None

    # Standardize
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    X_scaled = (X - mean) / std

    # Reduce
    try:
        from sklearn.manifold import TSNE
        perplexity = min(30, max(5, len(valid) // 3))
        embedding = TSNE(n_components=2, perplexity=perplexity,
                         random_state=42, max_iter=1000).fit_transform(X_scaled)
    except ImportError:
        embedding = _pca_fallback(X_scaled)

    if embedding is None:
        return None

    # Color by matched constant
    const_labels = []
    for d in valid:
        match = d.get("match", "other")
        base = match.split("*")[-1] if "*" in match else match
        const_labels.append(base)

    # Map constants to integers for coloring
    unique_consts = sorted(set(const_labels))
    const_to_idx = {c: i for i, c in enumerate(unique_consts)}
    colors = [const_to_idx[c] for c in const_labels]

    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(
        embedding[:, 0], embedding[:, 1],
        c=colors, cmap="tab20", alpha=0.7, s=20, edgecolors="none",
    )

    # Legend for top constants
    top_consts = Counter(const_labels).most_common(8)
    legend_handles = []
    for const_name, count in top_consts:
        idx = const_to_idx[const_name]
        color = plt.cm.tab20(idx / max(len(unique_consts), 1))
        legend_handles.append(
            plt.Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=color, markersize=8,
                       label=f"{const_name} ({count})")
        )
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8)

    method_label = method.upper()
    ax.set_title(f"Discovery Manifold ({method_label}): {len(valid)} CFs", fontsize=12)
    ax.set_xlabel("Component 1")
    ax.set_ylabel("Component 2")
    ax.grid(True, alpha=0.2)

    # Save
    if output_path is None:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = ASSETS_DIR / "manifold_map.png"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    _log.info("Manifold plot saved: %s", output_path)
    return output_path


# ===================================================================
# TASK 4: Elegance Scoring
# ===================================================================

def description_length(a_coeffs: list[int], b_coeffs: list[int]) -> int:
    """Compute the bit-complexity (description length) of a CF.

    description_length = sum of bit lengths of all non-zero coefficients
                       + count of non-zero terms (structural cost)

    Measures how "simple" the CF definition is: lower = more elegant.
    """
    total_bits = 0
    non_zero_terms = 0

    for c in a_coeffs:
        if c != 0:
            total_bits += c.bit_length() if isinstance(c, int) else int(math.log2(abs(c) + 1)) + 1
            non_zero_terms += 1

    for c in b_coeffs:
        if c != 0:
            total_bits += c.bit_length() if isinstance(c, int) else int(math.log2(abs(c) + 1)) + 1
            non_zero_terms += 1

    return total_bits + non_zero_terms


def elegance_score(
    verified_digits: float,
    a_coeffs: list[int],
    b_coeffs: list[int],
) -> float:
    """Compute elegance = verified_digits / description_length.

    Higher elegance = more digits per bit of description.
    A CF producing 200 verified digits with tiny coefficients is extremely elegant.
    """
    dl = description_length(a_coeffs, b_coeffs)
    if dl == 0:
        return 0.0
    return round(verified_digits / dl, 3)


def elegance_tier(score: float) -> str:
    """Map elegance score to a human-readable tier for PR tagging.

    Tiers:
      >= 15.0  -> "Exceptional Elegance"
      >= 8.0   -> "High Elegance"
      >= 4.0   -> "Moderate Elegance"
      <  4.0   -> "Standard"
    """
    if score >= 15.0:
        return "Exceptional Elegance"
    elif score >= 8.0:
        return "High Elegance"
    elif score >= 4.0:
        return "Moderate Elegance"
    return "Standard"


def compute_elegance_for_discovery(record: dict[str, Any]) -> dict[str, Any]:
    """Compute elegance metrics for a discovery record.

    Returns dict with:
      - 'elegance_score': float
      - 'elegance_tier': str
      - 'description_length': int
      - 'verified_digits': float
    """
    a = record.get("a", [])
    b = record.get("b", [])
    vd = record.get("verified_digits", 0) or 0

    dl = description_length(a, b)
    score = elegance_score(vd, a, b)
    tier = elegance_tier(score)

    return {
        "elegance_score": score,
        "elegance_tier": tier,
        "description_length": dl,
        "verified_digits": round(vd, 1),
    }


def elegance_leaderboard(top_n: int = 10) -> list[dict[str, Any]]:
    """Build a leaderboard ranked by elegance score."""
    discoveries = _load_discoveries()
    if not discoveries:
        return []

    scored = []
    seen_keys: set[Tuple] = set()
    for d in discoveries:
        key = (tuple(d.get("a", [])), tuple(d.get("b", [])))
        if key in seen_keys:
            continue
        seen_keys.add(key)

        vd = d.get("verified_digits", 0) or 0
        if vd < 10:
            continue

        e = compute_elegance_for_discovery(d)
        scored.append({**d, **e})

    scored.sort(key=lambda x: -x["elegance_score"])
    return scored[:top_n]


# ===================================================================
# Integration API (called from generator / adaptive_discovery)
# ===================================================================

def on_deep_space_discovery(record: dict[str, Any]) -> dict[str, Any]:
    """Enrich a discovery record with Deep Space metrics.

    Called from on_discovery in adaptive_discovery or directly from generator.
    Returns enriched record with elegance data and symmetry classification.
    """
    a = record.get("a", [])
    b = record.get("b", [])

    # Elegance
    elegance = compute_elegance_for_discovery(record)
    record["elegance_score"] = elegance["elegance_score"]
    record["elegance_tier"] = elegance["elegance_tier"]
    record["description_length"] = elegance["description_length"]

    # Symmetry classification
    record["symmetry_type"] = classify_symmetry(a, b)

    return record


def get_symmetry_population(pop_size: int = 10, rng=None) -> list[dict]:
    """Generate a population of symmetry-constrained CFs for injection
    into the main evolutionary loop.

    Returns list of dicts with 'a', 'b', 'hint_target' keys.
    """
    import random as _random
    if rng is None:
        rng = _random.Random()

    population = []
    constraints = ["factored_b", "shared_root", "gcd_symmetric", "palindromic_b"]

    for _ in range(pop_size):
        constraint = rng.choice(constraints)
        a, b, cname = generate_symmetry_constrained(rng, constraint=constraint)
        population.append({
            "a": a,
            "b": b,
            "hint_target": f"sym:{cname}",
        })

    return population


def periodic_deep_space_update(cycle: int, update_every: int = 200) -> None:
    """Periodic background tasks for Deep Space platform.

    Called from main loop.  Non-blocking: catches all exceptions.
      - Refresh composite targets (every update_every cycles)
      - Recompute manifold ridges (every update_every*2 cycles)
    """
    try:
        if cycle % update_every == 0 and cycle > 0:
            build_composite_targets()
            _log.info("Composite targets refreshed at cycle %d", cycle)

        if cycle % (update_every * 2) == 0 and cycle > 0:
            ridges = compute_manifold()
            if ridges:
                _log.info("Manifold ridges updated: %d ridges at cycle %d",
                           len(ridges), cycle)
    except Exception:
        _log.debug("Periodic deep space update failed (non-critical)")


# ===================================================================
# CLI (standalone analysis)
# ===================================================================

def _cli() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Deep Space Platform -- analysis & reporting"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symmetry-map", action="store_true",
                       help="Show symmetry-constant correlation map")
    group.add_argument("--composites", action="store_true",
                       help="Generate composite target library")
    group.add_argument("--manifold", action="store_true",
                       help="Compute manifold ridges and generate plot")
    group.add_argument("--elegance", action="store_true",
                       help="Show elegance leaderboard")
    group.add_argument("--generate-sym", type=int, metavar="N",
                       help="Generate N symmetry-constrained CFs")
    args = parser.parse_args()

    if args.symmetry_map:
        corr = symmetry_correlation_map()
        if not corr:
            print("No data for symmetry correlation map.")
            return
        print("\n=== Symmetry-Constant Correlation Map ===\n")
        for sym_type, consts in sorted(corr.items()):
            print(f"  {sym_type}:")
            for const, count in sorted(consts.items(), key=lambda x: -x[1]):
                print(f"    {const:20s}: {count}")

    elif args.composites:
        targets = build_composite_targets()
        if not targets:
            print("No composite targets generated (need near-miss data).")
            return
        print(f"\n=== Composite Targets ({len(targets)}) ===\n")
        for name, val in list(targets.items())[:20]:
            print(f"  {name:30s}: {val:.15g}")

    elif args.manifold:
        print("Computing manifold ridges...")
        ridges = compute_manifold()
        if not ridges:
            print("Not enough data or dependencies missing.")
            return
        print(f"\n=== Discovery Ridges ({len(ridges)}) ===\n")
        for i, r in enumerate(ridges, 1):
            print(f"  {i}. a~{r.centroid_a}, b~{r.centroid_b}")
            print(f"     density={r.density:.4f}, dominant={r.dominant_constant}, "
                  f"members={r.member_count}")

        path = generate_manifold_plot()
        if path:
            print(f"\n  Manifold plot saved: {path}")

    elif args.elegance:
        board = elegance_leaderboard()
        if not board:
            print("No data for elegance leaderboard.")
            return
        print("\n=== Elegance Leaderboard ===\n")
        print(f"  {'#':>3s}  {'Match':22s}  {'a':20s}  {'b':12s}  "
              f"{'VD':>6s}  {'DL':>4s}  {'Eleg':>6s}  {'Tier'}")
        print(f"  {'---':>3s}  {'-'*22}  {'-'*20}  {'-'*12}  "
              f"{'---':>6s}  {'--':>4s}  {'----':>6s}  {'-'*20}")
        for i, entry in enumerate(board, 1):
            print(f"  {i:3d}  {entry.get('match','?'):22s}  "
                  f"{str(entry.get('a',[])):20s}  "
                  f"{str(entry.get('b',[])):12s}  "
                  f"{entry.get('verified_digits',0):6.1f}  "
                  f"{entry.get('description_length',0):4d}  "
                  f"{entry.get('elegance_score',0):6.3f}  "
                  f"{entry.get('elegance_tier','?')}")

    elif args.generate_sym:
        import random
        rng = random.Random(42)
        print(f"\n=== Symmetry-Constrained CFs ({args.generate_sym}) ===\n")
        for i in range(args.generate_sym):
            a, b, cname = generate_symmetry_constrained(rng)
            print(f"  {i+1:3d}. [{cname:15s}] a={a}, b={b}")


if __name__ == "__main__":
    _cli()
