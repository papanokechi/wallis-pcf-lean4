"""
adaptive_discovery.py
=====================
Adaptive Discovery System for the Ramanujan Breakthrough Generator.

Implements four capabilities:
  1. Heuristic Feedback Loop  -- analyze near-misses, hot-start parameter narrowing
  2. Convergence Map generator -- matplotlib visualizations per discovery
  3. Conjecture Verification  -- SymPy closed-form simplification + PR flagging
  4. Autonomous Search Scaling -- self-adjust scan_every / precision by density

All functions are designed to be called non-blockingly from the main loop
or from github_research_sync.py.  ASCII-only output.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# ASCII-only logger
# ---------------------------------------------------------------------------
_log = logging.getLogger("adaptive")
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[adaptive %(levelname)s] %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parent
LOGFILE = WORKSPACE / "ramanujan_discoveries.jsonl"
STATEFILE = WORKSPACE / "ramanujan_state.json"
NEAR_MISS_FILE = WORKSPACE / "near_misses.jsonl"
ASSETS_DIR = WORKSPACE / "discoveries" / "assets"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_discoveries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not LOGFILE.exists():
        return entries
    for line in LOGFILE.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _load_near_misses() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not NEAR_MISS_FILE.exists():
        return entries
    for line in NEAR_MISS_FILE.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ===================================================================
# TASK 1: Heuristic Feedback Loop
# ===================================================================

@dataclass
class HotStartHint:
    """Narrowed search parameters derived from near-miss analysis."""
    a_center: list[int]       # center coefficients for a(n)
    b_center: list[int]       # center coefficients for b(n)
    radius: int               # search +/- this many around center
    target_constant: str      # which constant was nearly matched
    confidence: float         # 0..1 how promising this region is
    source: str               # "near_miss" | "pattern"


def log_near_miss(record: dict[str, Any]) -> None:
    """Append a near-miss record (high residual but below breakthrough threshold)."""
    with NEAR_MISS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def analyze_coefficient_patterns(
    min_verified: float = 50.0,
) -> dict[str, Any]:
    """Analyze ramanujan_discoveries.jsonl to identify coefficient patterns.

    Returns a dict with:
      - 'b_family_counts': Counter of b-polynomial signatures
      - 'a_coeff_stats': per-position mean/std of a-coefficients for top hits
      - 'fertile_degrees': (deg_a, deg_b) pairs ranked by discovery density
      - 'constant_hotspots': which constants have the most near-misses
    """
    discoveries = _load_discoveries()
    if not discoveries:
        return {}

    b_families: Counter = Counter()
    a_by_position: defaultdict[int, list[int]] = defaultdict(list)
    degree_pairs: Counter = Counter()
    constant_counts: Counter = Counter()

    for d in discoveries:
        a = d.get("a", [])
        b = d.get("b", [])
        vd = d.get("verified_digits", 0) or 0
        match = d.get("match", "")

        if vd < min_verified:
            continue

        # b-polynomial signature (tuple of coefficients)
        b_families[tuple(b)] += 1

        # a-coefficient distribution per position
        for i, c in enumerate(a):
            a_by_position[i].append(c)

        # degree pairs
        deg_a = len(a) - 1 if a else 0
        deg_b = len(b) - 1 if b else 0
        degree_pairs[(deg_a, deg_b)] += 1

        # constant targets
        # Strip rational prefixes like "3/8*"
        base = match.split("*")[-1] if "*" in match else match
        constant_counts[base] += 1

    # Compute per-position stats for a-coefficients
    a_stats = {}
    for pos, vals in sorted(a_by_position.items()):
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / max(len(vals) - 1, 1)
        std = math.sqrt(variance)
        a_stats[pos] = {"mean": round(mean, 2), "std": round(std, 2), "n": len(vals)}

    return {
        "b_family_counts": b_families.most_common(20),
        "a_coeff_stats": a_stats,
        "fertile_degrees": degree_pairs.most_common(10),
        "constant_hotspots": constant_counts.most_common(15),
    }


def _weighted_centroid(
    members: list[dict[str, Any]],
    key: str = "a",
    recency_half_life: int = 50,
) -> tuple[list[int], list[float]]:
    """Compute a verified-digit-weighted centroid of coefficient vectors.

    Each member is weighted by:
      w = verified_digits * recency_decay
    where recency_decay = 0.5^(age_in_entries / half_life).

    Returns (centroid, per-position weighted_std).
    """
    max_len = max(len(m.get(key, [])) for m in members)
    n = len(members)

    # Compute weights: vd * recency
    weights = []
    for idx, m in enumerate(members):
        vd = max(m.get("verified_digits", 1) or 1, 1.0)
        age = n - 1 - idx  # older entries have larger age
        decay = 0.5 ** (age / max(recency_half_life, 1))
        weights.append(vd * decay)

    total_w = sum(weights) or 1.0

    centroid = []
    stds = []
    for pos in range(max_len):
        vals = []
        ws = []
        for m, w in zip(members, weights):
            coeffs = m.get(key, [])
            if pos < len(coeffs):
                vals.append(coeffs[pos])
                ws.append(w)
        if not vals:
            centroid.append(0)
            stds.append(1.0)
            continue
        w_total = sum(ws) or 1.0
        wmean = sum(v * w for v, w in zip(vals, ws)) / w_total
        wvar = sum(w * (v - wmean) ** 2 for v, w in zip(vals, ws)) / w_total
        centroid.append(round(wmean))
        stds.append(math.sqrt(max(wvar, 0)))

    return centroid, stds


def generate_hot_start_hints(
    max_hints: int = 5,
    near_miss_threshold: float = 10.0,
) -> list[HotStartHint]:
    """Generate hot-start hints from near-misses and successful discovery patterns.

    Uses verified-digit-weighted centroids and recency bias to focus on the
    most promising algebraic neighborhoods.  Clusters are scored by:
      score = cluster_size * mean_vd * recency_factor
    """
    hints: list[HotStartHint] = []

    # --- From near-miss log ---
    near_misses = _load_near_misses()
    if near_misses:
        # Group by (b-signature, target constant base)
        groups: defaultdict[tuple, list] = defaultdict(list)
        for nm in near_misses:
            b_key = tuple(nm.get("b", []))
            target = nm.get("match", "unknown")
            base = target.split("*")[-1] if "*" in target else target
            groups[(b_key, base)].append(nm)

        # Rank clusters by composite score: size * avg_vd
        def _cluster_score(members: list) -> float:
            n = len(members)
            vd_vals = [m.get("verified_digits", 0) or 0 for m in members]
            avg_vd = sum(vd_vals) / max(n, 1)
            # Recency bonus: fraction of entries from last 50% of log
            total_nm = len(near_misses)
            recent_count = sum(
                1 for m in members
                if near_misses.index(m) > total_nm * 0.5
            ) if total_nm > 0 else 0
            recency = 1.0 + 0.5 * (recent_count / max(n, 1))
            return n * avg_vd * recency

        ranked = sorted(groups.items(), key=lambda x: -_cluster_score(x[1]))

        for (b_key, target), members in ranked:
            if len(hints) >= max_hints:
                break
            if len(members) < 2:
                continue  # skip singletons

            # Weighted centroid + per-position std
            a_center, a_stds = _weighted_centroid(members, key="a")

            # Radius: clamp weighted std, favouring tighter search for
            # high-confidence clusters
            vd_avg = sum((m.get("verified_digits", 0) or 0) for m in members) / len(members)
            base_radius = max(1, round(max(a_stds) + 0.5)) if a_stds else 2
            if vd_avg > 40:
                radius = max(1, base_radius - 1)  # tighter
            else:
                radius = min(base_radius + 1, 6)

            confidence = min(1.0, _cluster_score(members) / 500.0)
            confidence = round(max(0.1, confidence), 2)

            hints.append(HotStartHint(
                a_center=a_center,
                b_center=list(b_key),
                radius=radius,
                target_constant=target,
                confidence=confidence,
                source="near_miss",
            ))

    # --- From pattern analysis of successful discoveries ---
    patterns = analyze_coefficient_patterns(min_verified=100.0)
    if patterns and patterns.get("b_family_counts"):
        discoveries = _load_discoveries()
        for b_tuple, count in patterns["b_family_counts"][:3]:
            if len(hints) >= max_hints:
                break

            # Gather members matching this b-family at high vd
            family_members = [
                d for d in discoveries
                if tuple(d.get("b", [])) == b_tuple
                and (d.get("verified_digits", 0) or 0) >= 100
            ]
            if not family_members:
                # Fallback to simple stats
                a_stats = patterns.get("a_coeff_stats", {})
                a_center = [round(a_stats[p]["mean"]) for p in sorted(a_stats)]
                stds = [a_stats[p]["std"] for p in sorted(a_stats)]
            else:
                a_center, stds = _weighted_centroid(family_members, key="a")

            if not a_center:
                continue
            max_std = max(stds) if stds else 2.0
            radius = max(1, min(int(math.ceil(max_std)), 4))

            hints.append(HotStartHint(
                a_center=a_center,
                b_center=list(b_tuple),
                radius=radius,
                target_constant="(pattern-derived)",
                confidence=round(min(1.0, count / 20.0), 2),
                source="pattern",
            ))

    return hints


def hot_start_population(hints: list[HotStartHint], pop_size: int = 20,
                         rng=None) -> list:
    """Generate a population biased around hot-start hints.

    Returns list of dicts with 'a' and 'b' keys (compatible with PCFParams
    constructor in the generator).
    """
    import random as _random
    if rng is None:
        rng = _random

    population = []
    if not hints:
        return population

    per_hint = max(1, pop_size // len(hints))

    for hint in hints:
        for _ in range(per_hint):
            a = [
                c + rng.randint(-hint.radius, hint.radius)
                for c in hint.a_center
            ]
            b = list(hint.b_center)
            # Small perturbation on b too
            b = [c + rng.randint(-1, 1) for c in b]
            if b:
                b[0] = max(1, b[0])
            population.append({"a": a, "b": b, "hint_target": hint.target_constant})
            if len(population) >= pop_size:
                break

    return population[:pop_size]


# ===================================================================
# TASK 2: Convergence Map (matplotlib)
# ===================================================================

def generate_convergence_map(
    a_coeffs: list[int],
    b_coeffs: list[int],
    match_label: str,
    target_value: float | None = None,
    max_depth: int = 200,
    output_path: Path | str | None = None,
) -> Path | None:
    """Generate a convergence-rate plot showing how the CF approaches
    the matched constant vs. partial sums of 1/n^2 (baseline).

    Saves a PNG to discoveries/assets/ and returns the path.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend
        import matplotlib.pyplot as plt
        from mpmath import mp, mpf, nstr
        import mpmath as mpm
    except ImportError:
        _log.warning("matplotlib or mpmath not available -- skipping convergence map")
        return None

    saved_dps = mp.dps
    mp.dps = 80

    try:
        # Evaluate CF at increasing depths
        depths = list(range(5, max_depth + 1, 5))
        cf_values = []
        for d in depths:
            val = _eval_pcf_local(a_coeffs, b_coeffs, depth=d)
            cf_values.append(float(val) if val is not None else float("nan"))

        # Target value
        if target_value is None:
            # Use the deepest evaluation as target
            deep_val = _eval_pcf_local(a_coeffs, b_coeffs, depth=max_depth * 2)
            if deep_val is not None:
                target_value = float(deep_val)
            else:
                mp.dps = saved_dps
                return None

        # Compute convergence errors (log10 |CF_n - target|)
        cf_errors = []
        for v in cf_values:
            if math.isnan(v):
                cf_errors.append(0.0)
            else:
                err = abs(v - target_value)
                cf_errors.append(math.log10(max(err, 1e-80)) if err > 0 else -80.0)

        # Baseline: partial sums of pi^2/6 = sum(1/n^2) convergence
        baseline_errors = []
        pi2_6 = math.pi ** 2 / 6.0
        partial = 0.0
        depth_idx = 0
        for n in range(1, max_depth + 1):
            partial += 1.0 / (n * n)
            if n == depths[depth_idx]:
                err = abs(partial - pi2_6)
                baseline_errors.append(
                    math.log10(max(err, 1e-80)) if err > 0 else -80.0
                )
                depth_idx += 1
                if depth_idx >= len(depths):
                    break

        # Plot
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(depths[:len(cf_errors)], cf_errors, "b-o", markersize=3,
                linewidth=1.5, label=f"CF -> {match_label}")
        if baseline_errors:
            ax.plot(depths[:len(baseline_errors)], baseline_errors, "r--",
                    linewidth=1, alpha=0.6, label=r"$\sum 1/n^2 \to \pi^2/6$ (baseline)")
        ax.set_xlabel("Depth (number of convergents)")
        ax.set_ylabel("$\\log_{10}|\\mathrm{error}|$")
        ax.set_title(
            f"Convergence Map: $a(n)={a_coeffs}$, $b(n)={b_coeffs}$\n"
            f"$\\to$ {match_label}",
            fontsize=11,
        )
        ax.legend(loc="upper right", fontsize=9)
        ax.grid(True, alpha=0.3)

        # Save
        if output_path is None:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            safe_label = "".join(
                c if c.isalnum() or c in "_-" else "_" for c in match_label
            )[:40]
            a_id = "_".join(str(c) for c in a_coeffs)
            b_id = "_".join(str(c) for c in b_coeffs)
            fname = f"convergence_a{a_id}_b{b_id}_{safe_label}.png"
            output_path = ASSETS_DIR / fname
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
        plt.close(fig)
        _log.info("Convergence map saved: %s", output_path)
        return output_path

    except Exception:
        _log.warning("Convergence map failed:\n%s", traceback.format_exc())
        return None
    finally:
        mp.dps = saved_dps


def _eval_pcf_local(a_coeffs, b_coeffs, depth=500):
    """Minimal local CF evaluator (avoids circular import)."""
    from mpmath import mpf, mp
    try:
        def a(n):
            return sum(mpf(c) * n ** i for i, c in enumerate(a_coeffs))
        def b(n):
            return sum(mpf(c) * n ** i for i, c in enumerate(b_coeffs))
        val = mpf(0)
        for n in range(depth, 0, -1):
            bn = b(n)
            an = a(n)
            denom = bn + val
            if abs(denom) < mpf(10) ** (-mp.dps + 5):
                return None
            val = an / denom
        return b(0) + val
    except Exception:
        return None


# ===================================================================
# TASK 3: Conjecture Verification (SymPy)
# ===================================================================

def attempt_closed_form(
    a_coeffs: list[int],
    b_coeffs: list[int],
    match_label: str,
    numerical_value: float | None = None,
    precision_digits: int = 50,
) -> dict[str, Any]:
    """Attempt to simplify a CF match into a known closed form with SymPy.

    Returns a dict:
      - 'simplified': bool -- whether SymPy found a simpler expression
      - 'closed_form': str | None -- LaTeX of closed form if found
      - 'is_novel': bool -- True if no simplification found (potential new identity)
      - 'sympy_result': str | None -- raw SymPy output
      - 'pr_flag': str -- label for GitHub PR ("Known Identity" | "Potential New Identity")
    """
    result: dict[str, Any] = {
        "simplified": False,
        "closed_form": None,
        "is_novel": False,
        "sympy_result": None,
        "pr_flag": "Unverified",
    }

    try:
        import sympy
        from sympy import (
            nsimplify, Rational, pi as sym_pi, E as sym_E, log as sym_log,
            sqrt as sym_sqrt, zeta as sym_zeta, GoldenRatio, EulerGamma,
            latex, S, oo,
        )
    except ImportError:
        _log.warning("SymPy not installed -- skipping conjecture verification")
        return result

    try:
        from mpmath import mp, mpf
        saved_dps = mp.dps
        mp.dps = precision_digits + 30

        # Get numerical value if not provided
        if numerical_value is None:
            val = _eval_pcf_local(a_coeffs, b_coeffs, depth=1000)
            if val is not None:
                numerical_value = float(val)
            else:
                return result

        # Attempt nsimplify with an expanded library of constants
        constants_pool = [
            sym_pi, sym_E, sym_log(2), sym_log(3),
            sym_sqrt(2), sym_sqrt(3), sym_sqrt(5),
            GoldenRatio, EulerGamma,
            sym_zeta(3), sym_zeta(5), sym_zeta(7),
            sympy.catalan,
            sympy.gamma(Rational(1, 4)), sympy.gamma(Rational(3, 4)),
            sympy.gamma(Rational(1, 3)), sympy.gamma(Rational(2, 3)),
        ]

        # Try with increasing tolerance
        closed = None
        for tol in [1e-30, 1e-20, 1e-15]:
            try:
                closed = nsimplify(
                    numerical_value,
                    constants=constants_pool,
                    tolerance=tol,
                    rational=False,
                )
                # Verify the simplification is actually simpler than the raw float
                if closed is not None and closed != S(numerical_value):
                    # Check it actually matches
                    diff = abs(float(closed.evalf(50)) - numerical_value)
                    if diff < 10 ** (-precision_digits * 0.5):
                        break
                closed = None
            except Exception:
                continue

        if closed is not None:
            latex_str = latex(closed)
            result["simplified"] = True
            result["closed_form"] = f"${latex_str}$"
            result["sympy_result"] = str(closed)
            result["pr_flag"] = "Known Identity"
            _log.info("Closed form found: %s -> $%s$", match_label, latex_str)
        else:
            # No simplification -- flag as potentially novel
            result["is_novel"] = True
            result["pr_flag"] = "Potential New Mathematical Identity"
            _log.info("No closed form for %s -- flagged as potential new identity", match_label)

        mp.dps = saved_dps

    except Exception:
        _log.warning("Conjecture verification failed:\n%s", traceback.format_exc())

    return result


# ===================================================================
# TASK 4: Autonomous Search Scaling
# ===================================================================

@dataclass
class ScalingDecision:
    """Output of the autonomous scaling logic."""
    scan_every: int
    precision: int
    depth: int
    reason: str


# Track timing across calls
_cycle_times: list[float] = []
_discovery_timestamps: list[float] = []


def record_cycle_timing(elapsed: float) -> None:
    """Record how long the last cycle took."""
    _cycle_times.append(elapsed)
    # Keep last 100 entries
    if len(_cycle_times) > 100:
        _cycle_times.pop(0)


def record_discovery_event() -> None:
    """Record timestamp of a discovery for density calculation."""
    _discovery_timestamps.append(time.time())
    if len(_discovery_timestamps) > 200:
        _discovery_timestamps.pop(0)


def compute_scaling(
    current_scan_every: int,
    current_precision: int,
    current_depth: int,
    cycle: int,
    last_discovery_cycle: int,
    max_cycle_time: float = 30.0,
) -> ScalingDecision:
    """Self-adjust scan_every, precision, and depth based on:
      - cycle time (thermal/CPU proxy)
      - discovery density (hits per cycle window)
      - staleness (cycles since last discovery)

    Rules:
      1. If avg cycle time > max_cycle_time: reduce precision/depth, increase scan_every
      2. If discovery density is high (>1 per 20 cycles): increase precision for quality
      3. If stale > 150 cycles: widen scan (lower scan_every), lower precision for speed
      4. Never reduce precision below 40 or depth below 100
    """
    new_scan = current_scan_every
    new_prec = current_precision
    new_depth = current_depth
    reasons = []

    # --- Cycle time analysis ---
    if len(_cycle_times) >= 5:
        avg_time = sum(_cycle_times[-10:]) / len(_cycle_times[-10:])

        if avg_time > max_cycle_time * 1.5:
            # CPU is overloaded -- reduce workload
            new_prec = max(40, current_precision - 10)
            new_depth = max(100, current_depth - 50)
            new_scan = min(30, current_scan_every + 5)
            reasons.append(
                f"cycle time {avg_time:.1f}s > {max_cycle_time*1.5:.0f}s -> reduce load"
            )
        elif avg_time < max_cycle_time * 0.3 and current_precision < 100:
            # CPU has headroom -- increase quality
            new_prec = min(120, current_precision + 5)
            new_depth = min(800, current_depth + 50)
            reasons.append(
                f"cycle time {avg_time:.1f}s << {max_cycle_time:.0f}s -> increase quality"
            )

    # --- Discovery density ---
    stale = cycle - last_discovery_cycle
    if _discovery_timestamps and len(_discovery_timestamps) >= 2:
        window = _discovery_timestamps[-1] - _discovery_timestamps[0]
        if window > 0:
            density = len(_discovery_timestamps) / (window / 3600.0)  # hits/hour
            if density > 5.0 and new_prec < 100:
                # High discovery rate -- invest in precision
                new_prec = min(120, new_prec + 10)
                reasons.append(f"high density {density:.1f}/hr -> boost precision")
            elif density < 0.5 and stale > 100:
                # Low density + stale -- widen search
                new_scan = max(5, new_scan - 2)
                reasons.append(f"low density {density:.1f}/hr -> widen scan")

    # --- Staleness override ---
    if stale > 150:
        new_scan = max(5, min(new_scan, 8))
        new_prec = max(40, min(new_prec, 60))
        new_depth = max(150, min(new_depth, 300))
        reasons.append(f"stale {stale} cycles -> speed mode")
    elif stale > 80 and new_scan > 10:
        new_scan = max(8, new_scan - 2)
        reasons.append(f"stale {stale} -> scan more often")

    reason = "; ".join(reasons) if reasons else "no adjustment needed"

    return ScalingDecision(
        scan_every=new_scan,
        precision=new_prec,
        depth=new_depth,
        reason=reason,
    )


# ===================================================================
# Integration API (called from generator main loop)
# ===================================================================

def on_near_miss(record: dict[str, Any]) -> None:
    """Called when evaluate_population finds a near-miss (10-50 digit match)."""
    log_near_miss(record)


def on_discovery(record: dict[str, Any]) -> dict[str, Any] | None:
    """Called after a verified discovery.  Returns conjecture verification
    result (or None on failure).  Non-blocking: call in background thread."""
    try:
        record_discovery_event()

        # Deep Space: enrich with elegance + symmetry classification
        try:
            from deep_space import on_deep_space_discovery
            on_deep_space_discovery(record)
        except Exception:
            pass

        # Attempt symbolic simplification
        verification = attempt_closed_form(
            a_coeffs=record.get("a", []),
            b_coeffs=record.get("b", []),
            match_label=record.get("match", "?"),
            numerical_value=float(record["value"]) if "value" in record else None,
        )

        # Generate convergence map
        generate_convergence_map(
            a_coeffs=record.get("a", []),
            b_coeffs=record.get("b", []),
            match_label=record.get("match", "?"),
        )

        return verification

    except Exception:
        _log.warning("on_discovery failed:\n%s", traceback.format_exc())
        return None


def get_hot_start_population(pop_size: int = 20, rng=None) -> list[dict]:
    """Generate hot-start params from accumulated heuristic data.

    Merges near-miss hints with Deep Space ridge hints and
    symmetry-constrained CFs for maximally diverse injection.
    """
    hints = generate_hot_start_hints(max_hints=5)
    base_pop = hot_start_population(hints, pop_size=max(1, pop_size - 5), rng=rng) if hints else []

    # Deep Space: add ridge-based hints
    try:
        from deep_space import load_ridge_hints
        ridge_seeds = load_ridge_hints(max_hints=3)
        base_pop.extend(ridge_seeds)
    except Exception:
        pass

    # Deep Space: add symmetry-constrained CFs
    try:
        from deep_space import get_symmetry_population
        sym_pop = get_symmetry_population(pop_size=max(1, pop_size // 4), rng=rng)
        base_pop.extend(sym_pop)
    except Exception:
        pass

    return base_pop[:pop_size]


# ===================================================================
# CLI (standalone analysis)
# ===================================================================

def _cli() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Adaptive Discovery System -- analysis & reporting"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--analyze", action="store_true",
                       help="Analyze discovery patterns")
    group.add_argument("--hints", action="store_true",
                       help="Generate hot-start hints")
    group.add_argument("--convergence", nargs=2, metavar=("A_COEFFS", "B_COEFFS"),
                       help="Generate convergence map (JSON arrays)")
    group.add_argument("--verify", nargs=2, metavar=("A_COEFFS", "B_COEFFS"),
                       help="Attempt closed-form verification")
    args = parser.parse_args()

    if args.analyze:
        patterns = analyze_coefficient_patterns()
        if not patterns:
            print("No discoveries to analyze.")
            return
        print("\n=== Coefficient Pattern Analysis ===\n")
        print("Top b(n) families:")
        for b_tuple, count in patterns["b_family_counts"]:
            print(f"  b={list(b_tuple):20s}  count={count}")
        print("\na(n) coefficient stats:")
        for pos, stats in sorted(patterns["a_coeff_stats"].items()):
            print(f"  position {pos}: mean={stats['mean']:6.2f}  "
                  f"std={stats['std']:5.2f}  n={stats['n']}")
        print("\nFertile degree pairs (deg_a, deg_b):")
        for pair, count in patterns["fertile_degrees"]:
            print(f"  {pair}: {count}")
        print("\nConstant hotspots:")
        for name, count in patterns["constant_hotspots"]:
            print(f"  {name:20s}: {count}")

    elif args.hints:
        hints = generate_hot_start_hints()
        if not hints:
            print("No hot-start hints available (need near-miss data or discoveries).")
            return
        print("\n=== Hot-Start Hints ===\n")
        for i, h in enumerate(hints, 1):
            print(f"  {i}. target={h.target_constant}")
            print(f"     a_center={h.a_center}, b_center={h.b_center}")
            print(f"     radius={h.radius}, confidence={h.confidence}, source={h.source}")

    elif args.convergence:
        a = json.loads(args.convergence[0])
        b = json.loads(args.convergence[1])
        path = generate_convergence_map(a, b, match_label="manual")
        if path:
            print(f"Saved: {path}")
        else:
            print("Failed to generate convergence map.")

    elif args.verify:
        a = json.loads(args.verify[0])
        b = json.loads(args.verify[1])
        result = attempt_closed_form(a, b, match_label="manual")
        print(f"\nResult: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    _cli()
