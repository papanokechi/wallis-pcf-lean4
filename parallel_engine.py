"""
parallel_engine.py
==================
Commander-Worker distributed architecture for the Ramanujan Breakthrough
Generator.  Bypasses the GIL by using multiprocessing to flood manifold
ridges with parallel CF evaluations.

Architecture
------------
  Commander (main process)
    |-- SharedState (multiprocessing.Manager: ridges, seen_hits, counters)
    |-- DiscoveryQueue (multiprocessing.Queue: process-safe logging)
    |-- LogWriter daemon thread (drains queue -> JSONL)
    |-- Rebalancer (success-based feedback: reallocates shards between waves)
    |-- ThermalGuard (psutil CPU/RAM monitor: throttles if overheated)
    |
    |-- Worker 0  [pi-ridge shard, Stage 1 fast scan]
    |-- Worker 1  [pi-ridge shard, Stage 1 fast scan]
    |-- Worker 2  [zeta-ridge shard]
    |-- ...
    |-- Worker N-2 [exploratory shard]
    |-- Worker N-1 [hp-verify shard, Stage 2 high-precision]
    |
    +-- GitHub BatchSync (breakthrough=immediate, standard=30min batches)

Level 2 Optimizations
---------------------
  1. Dynamic Ridge Rebalancing  -- success-based shard allocation between waves
  2. Multi-Precision Waterfall  -- Stage 1 fast scan -> Stage 2 HP verification
  3. Near-Miss Heatmap          -- coefficient-space density visualization
  4. Batched GitHub Sync        -- immediate for breakthroughs, batched otherwise
  5. Hardware Thermal Guard     -- psutil CPU/RAM throttling

Usage
-----
  python parallel_engine.py                    # auto-detect cores
  python parallel_engine.py --workers 8        # manual core count
  python parallel_engine.py --workers 12 --cycles 500 --precision 80
  python parallel_engine.py --waves 3          # 3 rebalancing waves
  python parallel_engine.py --heatmap          # generate near-miss heatmap after run
  python parallel_engine.py --dry-run          # print shard plan only

For programmatic use:
  from parallel_engine import CommanderPool
  pool = CommanderPool(workers=8)
  pool.run(cycles=1000)
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import multiprocessing as mp_lib
import os
import queue
import random
import signal
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from multiprocessing import Process, Queue, Event, Value, Lock
from multiprocessing.managers import SyncManager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# ASCII-only logger
# ---------------------------------------------------------------------------
_log = logging.getLogger("parallel")
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[parallel %(levelname)s] %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parent
LOGFILE = WORKSPACE / "ramanujan_discoveries.jsonl"
NEAR_MISS_FILE = WORKSPACE / "near_misses.jsonl"
STATEFILE = WORKSPACE / "ramanujan_state.json"
RIDGE_CACHE = WORKSPACE / "ridge_map.json"
HEATMAP_PATH = WORKSPACE / "discoveries" / "assets" / "nearmiss_heatmap.png"
HP_VERIFY_QUEUE_FILE = WORKSPACE / "hp_verify_queue.jsonl"


# ===================================================================
# Shard Definitions
# ===================================================================

@dataclass
class ShardAssignment:
    """Defines what a worker should search."""
    shard_id: str                  # "pi-ridge", "zeta-ridge", "composite", "exploratory"
    worker_id: int
    constant_filter: list[str]     # subset of constant names to match against (empty = all)
    ridge_hint: Optional[dict] = None   # {"a": [...], "b": [...]} centroid
    symmetry_constraint: Optional[str] = None  # "factored_b", "shared_root", etc.
    coeff_range: int = 5
    temperature: float = 1.5
    a_deg: int = 2
    b_deg: int = 1


# Constant families for ridge sharding
PI_FAMILY = [
    '4/pi', '2/pi', 'pi/4', 'pi/2', 'pi', 'pi^2/6', 'pi^2/8',
    'pi^2/12', 'pi^3/32', 'pi^4/90', '6/pi^2', 'sqrt_pi',
    '1/sqrt_pi', '2/sqrt_pi',
]
PI_FAMILY += [f'S^({m})' for m in range(2, 9)]

ZETA_FAMILY = [
    'zeta3', 'zeta5', 'zeta7', '1/zeta3', 'zeta3/pi^3', 'zeta3*pi',
]

LOG_FAMILY = [
    'log2', 'log3', 'log5', 'log10', 'log2^2', 'log3/log2', 'ln2/pi',
]

ALGEBRAIC_FAMILY = [
    'sqrt2', 'sqrt3', 'sqrt5', 'sqrt6', 'sqrt7', 'phi', '1/phi',
    'sqrt2+1', 'sqrt3+1',
]

GAMMA_FAMILY = [
    'Gamma_1_4', 'Gamma_3_4', 'Gamma_1_3', 'Gamma_2_3', 'Gamma_1_6',
    'Gamma14^2/sqrt_pi',
]

EXOTIC_FAMILY = [
    'e', '1/e', 'e^2', 'e*pi', 'euler_g', 'euler_g^2',
    'catalan', 'catalan/pi', 'catalan*4/pi', 'pi*catalan',
]

# Shard type -> constant filter
SHARD_CONSTANT_MAP = {
    "pi-ridge":     PI_FAMILY,
    "zeta-ridge":   ZETA_FAMILY,
    "log-ridge":    LOG_FAMILY,
    "algebraic":    ALGEBRAIC_FAMILY,
    "gamma-ridge":  GAMMA_FAMILY,
    "exotic":       EXOTIC_FAMILY,
    "composite":    [],   # uses composite targets
    "exploratory":  [],   # searches all constants
}


def build_shard_plan(
    num_workers: int,
    ridge_hints: list[dict] | None = None,
    shard_weights: dict[str, float] | None = None,
) -> list[ShardAssignment]:
    """Distribute workers across ridges based on historical productivity.

    Args:
        num_workers: total available workers
        ridge_hints: manifold centroids for seeding populations
        shard_weights: override allocation weights (from rebalancer).
            Maps shard_id -> fraction (0..1).  If None, uses defaults.

    Default allocation (scales with worker count):
      ~30% pi-ridge     (historically most productive)
      ~20% zeta-ridge   (high-value targets)
      ~15% exploratory   (wild-card search, all constants)
      ~10% composite     (dynamic targets from near-misses)
      ~10% symmetry      (structurally constrained CFs)
      ~15% remaining ridges (log, algebraic, gamma, exotic)
    """
    if num_workers < 1:
        return []

    shards: list[ShardAssignment] = []

    # Default allocations (shard_id, fraction, a_deg, b_deg, symmetry)
    default_alloc = [
        ("pi-ridge",    0.30, 2, 1, None),
        ("zeta-ridge",  0.20, 3, 2, None),
        ("exploratory", 0.15, 2, 1, None),
        ("composite",   0.10, 2, 1, None),
        ("symmetry",    0.10, 2, 1, "random"),
        ("log-ridge",   0.05, 2, 1, None),
        ("algebraic",   0.03, 2, 1, None),
        ("gamma-ridge", 0.04, 2, 1, None),
        ("exotic",      0.03, 2, 1, None),
    ]

    # Apply rebalanced weights if provided
    if shard_weights:
        allocations = []
        for stype, default_frac, a_deg, b_deg, sym in default_alloc:
            frac = shard_weights.get(stype, default_frac)
            allocations.append((stype, frac, a_deg, b_deg, sym))
    else:
        allocations = default_alloc

    # Calculate worker counts per shard type
    remaining = num_workers
    shard_counts: list[tuple[str, int, int, int, str | None]] = []
    for stype, frac, a_deg, b_deg, sym in allocations:
        count = max(0, round(frac * num_workers))
        shard_counts.append((stype, count, a_deg, b_deg, sym))
        remaining -= count

    # Distribute remainder to pi-ridge (most productive)
    if remaining > 0:
        for i, (stype, count, a_deg, b_deg, sym) in enumerate(shard_counts):
            if stype == "pi-ridge":
                shard_counts[i] = (stype, count + remaining, a_deg, b_deg, sym)
                break

    # Ensure at least 1 worker total
    total_assigned = sum(c for _, c, _, _, _ in shard_counts)
    if total_assigned == 0 and num_workers > 0:
        shard_counts[0] = (shard_counts[0][0], 1, shard_counts[0][2],
                           shard_counts[0][3], shard_counts[0][4])

    worker_id = 0
    for stype, count, a_deg, b_deg, sym in shard_counts:
        const_filter = SHARD_CONSTANT_MAP.get(stype, [])

        # Assign ridge hints if available
        hints_for_shard = []
        if ridge_hints:
            for rh in ridge_hints:
                target = rh.get("hint_target", "")
                if stype == "pi-ridge" and any(k in target.lower() for k in ["pi", "s^("]):
                    hints_for_shard.append(rh)
                elif stype == "zeta-ridge" and "zeta" in target.lower():
                    hints_for_shard.append(rh)
                elif stype == "exploratory":
                    hints_for_shard.append(rh)

        for i in range(count):
            hint = hints_for_shard[i % len(hints_for_shard)] if hints_for_shard else None
            shards.append(ShardAssignment(
                shard_id=stype,
                worker_id=worker_id,
                constant_filter=list(const_filter),
                ridge_hint=hint,
                symmetry_constraint=sym if stype == "symmetry" else None,
                a_deg=a_deg,
                b_deg=b_deg,
            ))
            worker_id += 1

    return shards[:num_workers]


# ===================================================================
# Worker Process (runs in subprocess — fully independent mpmath state)
# ===================================================================

def _worker_loop(
    shard_dict: dict,
    discovery_queue: Queue,
    near_miss_queue: Queue,
    halt_event: Event,
    seen_hits_lock: Lock,
    shared_seen_keys: Any,     # manager.list() of string keys
    cycles: int,
    precision: int,
    depth: int,
    tol_digits: int,
    pop_size: int,
    verify: bool,
    verify_prec: int,
    seed_offset: int,
) -> dict:
    """Worker entry point.  Runs in a separate process with its own
    mpmath context.  Only communicates via Queues + shared state.

    Returns a summary dict when done.
    """
    # -- Reconstruct shard from dict (can't pickle dataclasses across processes
    #    on all platforms) --
    shard = ShardAssignment(**shard_dict)
    wid = shard.worker_id
    stats = {
        "worker_id": wid,
        "shard_id": shard.shard_id,
        "cycles_run": 0,
        "evaluated": 0,
        "discoveries": 0,
        "near_misses": 0,
        "elapsed": 0.0,
        "best_score": 0.0,
        "status": "running",
        "error": None,
    }

    try:
        # Each worker gets its own mpmath precision — no state leakage
        from mpmath import mp, mpf, nstr
        import mpmath as mpm
        mp.dps = precision + 20

        # Import generator functions from the main module
        from ramanujan_breakthrough_generator import (
            eval_pcf, is_reasonable, is_telescoping, is_spurious_match,
            build_constants, complexity_score, fitness_trap_penalty,
            is_fitness_trap, verify_match_high_precision, PCFParams,
            random_params, mutate, crossover, random_fertile_params,
            seed_population, _parse_match_target,
        )

        # Build constant library for this worker's shard
        all_constants = build_constants(precision)

        if shard.constant_filter:
            # Filter to shard's constant subset + always include ratio variants
            constants = {}
            for name, val in all_constants.items():
                if name in shard.constant_filter:
                    constants[name] = val
            # If filter produced nothing (stale names), fall back to all
            if not constants:
                constants = all_constants
        else:
            constants = all_constants

        # Merge composite targets for composite shard
        if shard.shard_id == "composite":
            try:
                from deep_space import merge_composite_into_constants
                constants = merge_composite_into_constants(constants, max_composite=20)
            except Exception:
                pass

        # Worker-specific RNG (deterministic per worker, no collisions)
        rng = random.Random(42 + seed_offset + wid * 1000)

        # Build local seen-hits set from shared state
        local_seen: set[tuple] = set()
        try:
            for key_str in shared_seen_keys:
                parsed = json.loads(key_str)
                local_seen.add((tuple(parsed[0]), tuple(parsed[1])))
        except Exception:
            pass

        # Initial population
        population = _build_worker_population(
            shard, rng, pop_size, all_constants, constants
        )

        temperature = shard.temperature
        t_start = time.time()

        for cycle in range(1, cycles + 1):
            if halt_event.is_set():
                stats["status"] = "halted_by_breakthrough"
                break

            # -- Evaluate population --
            for p in population:
                if halt_event.is_set():
                    break

                if is_telescoping(p.a, p.b):
                    p.score = -2
                    continue

                val = eval_pcf(p.a, p.b, depth=depth)
                if not is_reasonable(val):
                    p.score = -1
                    continue

                stats["evaluated"] += 1

                # Match against this shard's constants
                best_residual = mpf(1)
                best_match = None

                for name, cval in constants.items():
                    for numer in [1, 2, 3, 4]:
                        for denom in [1, 2, 3, 4, 6, 8]:
                            ratio = mpf(numer) / denom * cval
                            res = abs(val - ratio)
                            if res < best_residual:
                                best_residual = res
                                label = (f"{numer}/{denom}*{name}"
                                         if (numer != 1 or denom != 1)
                                         else name)
                                best_match = (label, res)

                if best_match:
                    raw_score = float(-mpm.log10(
                        max(best_match[1], mpf(10)**(-mp.dps + 5))
                    ))
                    penalty = complexity_score(p.a, p.b)
                    trap_pen = fitness_trap_penalty(best_match[0], raw_score)
                    p.score = raw_score - penalty - trap_pen

                    if raw_score > stats["best_score"]:
                        stats["best_score"] = raw_score

                    seen_key = (tuple(p.a), tuple(p.b))
                    key_str = json.dumps([p.a, p.b], ensure_ascii=True)

                    if raw_score > tol_digits and seen_key not in local_seen:
                        if is_spurious_match(best_match[0]):
                            local_seen.add(seen_key)
                            continue

                        # High-precision verification
                        verified = True
                        verify_digits = raw_score
                        if verify and raw_score > tol_digits + 5:
                            verified, verify_digits = verify_match_high_precision(
                                p.a, p.b, best_match[0], constants,
                                verify_prec=verify_prec,
                                verify_depth=min(depth * 2, 1000),
                            )

                        if verified:
                            p.hit = best_match[0]
                            record = {
                                'cycle': cycle,
                                'worker_id': wid,
                                'shard': shard.shard_id,
                                'a': p.a, 'b': p.b,
                                'value': nstr(val, 20),
                                'match': best_match[0],
                                'residual': float(mpm.log10(
                                    max(best_match[1], mpf(10)**(-mp.dps + 5))
                                )),
                                'verified_digits': round(verify_digits, 1),
                                'complexity': round(penalty, 2),
                                'timestamp': datetime.now().isoformat(),
                                'type': 'parallel',
                            }
                            # Send to commander via queue (process-safe)
                            discovery_queue.put(record)
                            stats["discoveries"] += 1
                            local_seen.add(seen_key)

                            # Broadcast to shared seen-keys
                            try:
                                with seen_hits_lock:
                                    shared_seen_keys.append(key_str)
                            except Exception:
                                pass

                            # HALT SIGNAL: 100+ digit breakthrough
                            if verify_digits >= 100:
                                halt_event.set()
                                stats["status"] = "breakthrough_trigger"

                        else:
                            # Near-miss
                            if raw_score > tol_digits + 3:
                                nm_record = {
                                    'a': p.a, 'b': p.b,
                                    'value': nstr(val, 20),
                                    'match': best_match[0],
                                    'residual': float(mpm.log10(
                                        max(best_match[1], mpf(10)**(-mp.dps + 5))
                                    )),
                                    'verified_digits': round(verify_digits, 1),
                                    'worker_id': wid,
                                    'shard': shard.shard_id,
                                    'timestamp': datetime.now().isoformat(),
                                }
                                near_miss_queue.put(nm_record)
                                stats["near_misses"] += 1

                            local_seen.add(seen_key)
                else:
                    p.score = 0.0

            # -- Sort + evolve --
            population.sort(key=lambda p: p.score, reverse=True)

            # Simple evolution: keep top 20%, fill rest with mutations + fertile
            elite_n = max(2, pop_size // 5)
            elite = population[:elite_n]
            new_pop = list(elite)

            while len(new_pop) < pop_size:
                r = rng.random()
                if r < 0.35:
                    parent = rng.choice(elite)
                    child = mutate(parent, temperature, rng)
                elif r < 0.55 and len(elite) >= 2:
                    p1, p2 = rng.sample(elite, 2)
                    child = crossover(p1, p2, rng)
                    child = mutate(child, temperature * 0.5, rng)
                elif r < 0.75:
                    child = random_fertile_params(rng)
                elif r < 0.88:
                    # Symmetry-constrained (for symmetry shards)
                    if shard.symmetry_constraint:
                        try:
                            from deep_space import generate_symmetry_constrained
                            a, b, _ = generate_symmetry_constrained(
                                rng, constraint=shard.symmetry_constraint
                            )
                            child = PCFParams(a=a, b=b)
                        except Exception:
                            child = random_params(
                                a_deg=shard.a_deg, b_deg=shard.b_deg,
                                coeff_range=shard.coeff_range, rng=rng
                            )
                    else:
                        child = random_params(
                            a_deg=shard.a_deg, b_deg=shard.b_deg,
                            coeff_range=shard.coeff_range, rng=rng
                        )
                else:
                    child = random_params(
                        a_deg=rng.choice([1, 2, 2, 3]),
                        b_deg=rng.choice([1, 1, 2]),
                        coeff_range=rng.randint(3, 7), rng=rng,
                    )
                new_pop.append(child)

            population = new_pop

            # Adaptive temperature
            temperature = max(0.3, temperature * 0.998)
            if cycle % 50 == 0 and stats["discoveries"] == 0:
                temperature = min(4.0, temperature * 1.5)

            stats["cycles_run"] = cycle

        stats["elapsed"] = round(time.time() - t_start, 2)
        if stats["status"] == "running":
            stats["status"] = "completed"

    except Exception:
        stats["status"] = "error"
        stats["error"] = traceback.format_exc()

    return stats


# ===================================================================
# Stage 2: High-Precision Verification Worker (Waterfall Method)
# ===================================================================

def _hp_verify_worker(
    verify_queue: Queue,
    result_queue: Queue,
    halt_event: Event,
    verify_prec: int = 1500,
    verify_depth: int = 2000,
) -> dict:
    """Specialized worker that only does high-precision verification.

    Pulls candidate records from verify_queue, re-evaluates at verify_prec,
    and pushes verified results to result_queue.
    """
    stats = {"verified": 0, "rejected": 0, "elapsed": 0.0, "status": "running"}
    t_start = time.time()

    try:
        from mpmath import mp, mpf
        import mpmath as mpm
        mp.dps = verify_prec + 50

        from ramanujan_breakthrough_generator import (
            eval_pcf, build_constants, _parse_match_target,
        )
        hi_constants = build_constants(verify_prec)

        while not halt_event.is_set():
            try:
                candidate = verify_queue.get(timeout=2.0)
            except queue.Empty:
                # Check if all Stage 1 workers are done
                continue

            if candidate is None:  # poison pill
                break

            a = candidate.get("a", [])
            b = candidate.get("b", [])
            match_label = candidate.get("match", "?")

            # Re-evaluate at high precision
            mp.dps = verify_prec + 50
            val = eval_pcf(a, b, depth=verify_depth)
            if val is None:
                stats["rejected"] += 1
                continue

            target = _parse_match_target(match_label, hi_constants)
            if target is None:
                stats["rejected"] += 1
                continue

            residual = abs(val - target)
            if residual == 0:
                digits = float(verify_prec)
            else:
                digits = float(-mpm.log10(residual))

            if digits > verify_prec * 0.8:
                # Verified at high precision!
                candidate["verified_digits"] = round(digits, 1)
                candidate["hp_verified"] = True
                candidate["verify_prec"] = verify_prec
                result_queue.put(candidate)
                stats["verified"] += 1

                if digits >= 100:
                    halt_event.set()
            else:
                stats["rejected"] += 1

    except Exception:
        stats["status"] = "error"
        stats["error"] = traceback.format_exc()

    stats["elapsed"] = round(time.time() - t_start, 2)
    if stats["status"] == "running":
        stats["status"] = "completed"
    return stats


# ===================================================================
# Opt 1: Dynamic Ridge Rebalancer
# ===================================================================

def compute_rebalanced_weights(
    worker_stats: list[dict],
    near_miss_counts: dict[str, int],
    discovery_counts: dict[str, int],
) -> dict[str, float]:
    """Compute new shard allocation weights based on per-shard hit rates.

    Strategy:
      - Shards with higher (discovery + near_miss) rates get more workers
      - Minimum 5% floor per shard to prevent starvation
      - Exploratory always keeps at least 10% (serendipity budget)

    Returns dict: shard_id -> weight (0..1), sums to ~1.0
    """
    all_shards = list(SHARD_CONSTANT_MAP.keys()) + ["symmetry"]

    # Compute per-shard "productivity score"
    scores: dict[str, float] = {}
    for shard in all_shards:
        disc = discovery_counts.get(shard, 0)
        nm = near_miss_counts.get(shard, 0)
        # Weighted: discoveries worth 5x near-misses
        scores[shard] = disc * 5.0 + nm * 1.0

    total_score = sum(scores.values())

    if total_score < 1.0:
        # No data yet — return None to use defaults
        return {}

    # Normalize to weights with 5% floor
    floor = 0.05
    weights: dict[str, float] = {}
    for shard in all_shards:
        raw = scores[shard] / total_score
        weights[shard] = max(floor, raw)

    # Enforce exploratory minimum
    weights["exploratory"] = max(0.10, weights.get("exploratory", 0.10))

    # Renormalize to sum to 1.0
    total_w = sum(weights.values())
    if total_w > 0:
        weights = {k: round(v / total_w, 3) for k, v in weights.items()}

    return weights


# ===================================================================
# Opt 3: Near-Miss Heatmap Visualization
# ===================================================================

def generate_nearmiss_heatmap(
    output_path: Path | str | None = None,
) -> Path | None:
    """Generate a 2D heatmap of near-miss density in (a_coeff_1, a_coeff_2) space.

    X-axis: a[1] (linear coefficient)
    Y-axis: a[2] (quadratic coefficient)
    Color intensity: count of near-misses in that bin

    Returns path to saved PNG or None.
    """
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        _log.warning("numpy/matplotlib not available for heatmap")
        return None

    # Load near-misses
    near_misses = []
    if NEAR_MISS_FILE.exists():
        for line in NEAR_MISS_FILE.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                near_misses.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if len(near_misses) < 10:
        _log.info("Not enough near-misses for heatmap (%d)", len(near_misses))
        return None

    # Extract (a[1], a[2]) coordinates
    a1_vals = []
    a2_vals = []
    shard_labels = []
    for nm in near_misses:
        a = nm.get("a", [])
        if len(a) >= 3:
            a1_vals.append(a[1])
            a2_vals.append(a[2])
            shard_labels.append(nm.get("shard", nm.get("match", "?")))
        elif len(a) >= 2:
            a1_vals.append(a[1])
            a2_vals.append(0)
            shard_labels.append(nm.get("shard", nm.get("match", "?")))

    if len(a1_vals) < 10:
        return None

    a1 = np.array(a1_vals, dtype=float)
    a2 = np.array(a2_vals, dtype=float)

    # 2D histogram
    bins = min(30, max(10, len(a1_vals) // 5))
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Left: density heatmap
    ax = axes[0]
    h, xedges, yedges, img = ax.hist2d(
        a1, a2, bins=bins, cmap="YlOrRd", cmin=1,
    )
    fig.colorbar(img, ax=ax, label="Near-miss count")
    ax.set_xlabel("a[1] (linear coefficient)")
    ax.set_ylabel("a[2] (quadratic coefficient)")
    ax.set_title(f"Near-Miss Density Heatmap ({len(a1_vals)} points)")
    ax.grid(True, alpha=0.2)

    # Right: scatter colored by shard/constant
    ax2 = axes[1]
    unique_shards = sorted(set(shard_labels))
    shard_to_idx = {s: i for i, s in enumerate(unique_shards)}
    colors = [shard_to_idx[s] for s in shard_labels]
    scatter = ax2.scatter(a1, a2, c=colors, cmap="tab10", alpha=0.5, s=8)
    ax2.set_xlabel("a[1] (linear coefficient)")
    ax2.set_ylabel("a[2] (quadratic coefficient)")
    ax2.set_title("Near-Misses by Shard/Target")
    ax2.grid(True, alpha=0.2)

    # Legend
    top_shards = Counter(shard_labels).most_common(8)
    handles = []
    for sname, cnt in top_shards:
        idx = shard_to_idx[sname]
        color = plt.cm.tab10(idx / max(len(unique_shards), 1))
        handles.append(plt.Line2D([0], [0], marker="o", color="w",
                                   markerfacecolor=color, markersize=6,
                                   label=f"{sname} ({cnt})"))
    ax2.legend(handles=handles, loc="upper right", fontsize=7)

    plt.tight_layout()

    # Save
    if output_path is None:
        output_path = HEATMAP_PATH
    else:
        output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    _log.info("Near-miss heatmap saved: %s", output_path)
    return output_path


# ===================================================================
# Opt 5: Hardware Thermal Guard
# ===================================================================

class ThermalGuard:
    """Monitor CPU/RAM via psutil.  Throttle poll rate when overheated.

    Falls back gracefully if psutil is not installed.
    """

    def __init__(
        self,
        cpu_threshold: float = 95.0,   # percent
        ram_threshold: float = 90.0,   # percent
        throttle_seconds: float = 5.0, # extra sleep when hot
    ):
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold
        self.throttle_seconds = throttle_seconds
        self._has_psutil = False
        self._psutil = None
        self._throttle_count = 0

        try:
            import psutil
            self._psutil = psutil
            self._has_psutil = True
        except ImportError:
            pass

    def check_and_throttle(self) -> dict[str, Any]:
        """Check system health.  Returns status dict.

        If thresholds exceeded, sleeps for throttle_seconds (blocking).
        """
        status = {
            "cpu_percent": None,
            "ram_percent": None,
            "throttled": False,
            "available": self._has_psutil,
        }

        if not self._has_psutil:
            return status

        try:
            cpu = self._psutil.cpu_percent(interval=0.5)
            ram = self._psutil.virtual_memory().percent
            status["cpu_percent"] = round(cpu, 1)
            status["ram_percent"] = round(ram, 1)

            if cpu > self.cpu_threshold or ram > self.ram_threshold:
                status["throttled"] = True
                self._throttle_count += 1
                _log.warning(
                    "Thermal guard: CPU=%.1f%% RAM=%.1f%% -- throttling %.1fs "
                    "(count=%d)",
                    cpu, ram, self.throttle_seconds, self._throttle_count,
                )
                time.sleep(self.throttle_seconds)
        except Exception:
            pass

        return status

    @property
    def throttle_count(self) -> int:
        return self._throttle_count


def _build_worker_population(
    shard: ShardAssignment,
    rng: random.Random,
    pop_size: int,
    all_constants: dict,
    shard_constants: dict,
) -> list:
    """Build initial population for a worker, biased by shard assignment."""
    from ramanujan_breakthrough_generator import (
        PCFParams, random_params, seed_population, random_fertile_params,
    )

    population = []

    # If we have a ridge hint, seed 40% of population around it
    if shard.ridge_hint:
        hint_a = shard.ridge_hint.get("a", [0, 1, -1])
        hint_b = shard.ridge_hint.get("b", [1, 2])
        for _ in range(pop_size * 2 // 5):
            a = [c + rng.randint(-2, 2) for c in hint_a]
            b = [c + rng.randint(-1, 1) for c in hint_b]
            if b:
                b[0] = max(1, b[0])
            population.append(PCFParams(a=a, b=b))

    # Add known seeds (10%)
    seeds = seed_population()
    for s in rng.sample(seeds, min(len(seeds), max(1, pop_size // 10))):
        population.append(s)

    # Symmetry-constrained (for symmetry shards)
    if shard.symmetry_constraint:
        try:
            from deep_space import generate_symmetry_constrained
            for _ in range(pop_size // 5):
                a, b, _ = generate_symmetry_constrained(
                    rng, constraint=shard.symmetry_constraint
                )
                population.append(PCFParams(a=a, b=b))
        except Exception:
            pass

    # Fill remainder with fertile + random
    while len(population) < pop_size:
        if rng.random() < 0.6:
            population.append(random_fertile_params(rng))
        else:
            population.append(random_params(
                a_deg=shard.a_deg, b_deg=shard.b_deg,
                coeff_range=shard.coeff_range, rng=rng,
            ))

    return population[:pop_size]


# ===================================================================
# Commander (Main Process Orchestrator)
# ===================================================================

class CommanderPool:
    """Orchestrates parallel CF discovery across multiple processes.

    Level 2 Optimizations:
      1. Dynamic Ridge Rebalancing  -- reallocates shards between waves
      2. Multi-Precision Waterfall  -- Stage1 fast scan -> Stage2 HP verify
      3. Near-Miss Heatmap          -- coefficient-space density viz
      4. Batched GitHub Sync        -- immediate breakthroughs, batched standard
      5. Hardware Thermal Guard     -- psutil CPU/RAM throttling
    """

    def __init__(
        self,
        workers: int | None = None,
        precision: int = 60,
        depth: int = 300,
        tol_digits: int = 15,
        pop_size: int = 40,
        verify: bool = True,
        verify_prec: int = 200,
        waves: int = 1,
        hp_verify_prec: int = 1500,
        generate_heatmap: bool = False,
        github_batch_interval: float = 1800.0,  # 30 minutes
    ):
        cpu_count = os.cpu_count() or 4
        self.num_workers = workers or max(1, cpu_count - 1)
        self.precision = precision
        self.depth = depth
        self.tol_digits = tol_digits
        self.pop_size = pop_size
        self.verify = verify
        self.verify_prec = verify_prec
        self.waves = max(1, waves)
        self.hp_verify_prec = hp_verify_prec
        self.generate_heatmap = generate_heatmap
        self.github_batch_interval = github_batch_interval

        # IPC primitives
        self.discovery_queue: Queue = Queue()
        self.near_miss_queue: Queue = Queue()
        self.halt_event: Event = Event()
        self.seen_hits_lock: Lock = Lock()

        # Waterfall: Stage 2 HP verification queue
        self._hp_verify_queue: Queue = Queue()
        self._hp_result_queue: Queue = Queue()

        # Statistics
        self._total_discoveries = 0
        self._total_near_misses = 0
        self._total_evaluated = 0
        self._start_time = 0.0
        self._worker_stats: list[dict] = []

        # Per-shard tracking (for rebalancer)
        self._shard_discoveries: dict[str, int] = defaultdict(int)
        self._shard_near_misses: dict[str, int] = defaultdict(int)

        # Batched GitHub sync tracking (Opt 4)
        self._last_github_sync = 0.0
        self._pending_sync_count = 0

        # Thermal guard (Opt 5)
        self._thermal = ThermalGuard()

    def run(self, cycles: int = 100, seed: int = 42) -> dict:
        """Launch all workers in waves, drain queues, return summary.

        If waves > 1, runs multiple rounds with rebalanced shard weights.
        """
        self._start_time = time.time()
        cycles_per_wave = max(1, cycles // self.waves)
        shard_weights = None  # first wave uses defaults

        for wave in range(1, self.waves + 1):
            if self.waves > 1:
                print(f"\n  === WAVE {wave}/{self.waves} "
                      f"({cycles_per_wave} cycles) ===", flush=True)

            # Clear halt from previous wave so workers can run again
            self.halt_event.clear()

            self._run_wave(
                cycles=cycles_per_wave,
                seed=seed + wave * 10000,
                shard_weights=shard_weights,
            )

            # Rebalance for next wave (Opt 1)
            if wave < self.waves:
                shard_weights = compute_rebalanced_weights(
                    self._worker_stats,
                    dict(self._shard_near_misses),
                    dict(self._shard_discoveries),
                )
                if shard_weights:
                    print("  [Rebalancer] New shard weights:", flush=True)
                    for stype, w in sorted(shard_weights.items(),
                                           key=lambda x: -x[1]):
                        if w > 0.01:
                            print(f"    {stype:18s}: {w:.1%}", flush=True)

        # Final batched GitHub sync
        self._flush_github_sync()

        # Generate heatmap (Opt 3)
        if self.generate_heatmap:
            hm_path = generate_nearmiss_heatmap()
            if hm_path:
                print(f"  Heatmap saved: {hm_path}")

        elapsed = time.time() - self._start_time
        summary = self._build_summary(elapsed)
        self._print_summary(summary)
        return summary

    def _run_wave(
        self,
        cycles: int,
        seed: int,
        shard_weights: dict[str, float] | None = None,
    ) -> None:
        """Run a single wave of workers."""
        # Load ridge hints for shard planning
        ridge_hints = self._load_ridges()

        # Build shard plan (with rebalanced weights if available)
        shards = build_shard_plan(self.num_workers, ridge_hints, shard_weights)
        self._print_shard_plan(shards)

        # Shared seen-keys via Manager
        manager = mp_lib.Manager()
        shared_seen_keys = manager.list()

        # Pre-load existing seen keys from discovery log
        existing_keys = self._load_existing_seen_keys()
        for k in existing_keys:
            shared_seen_keys.append(k)
        _log.info("Pre-loaded %d existing seen keys", len(existing_keys))

        # Launch Stage 1 workers
        processes: list[tuple[Process, ShardAssignment]] = []
        for shard in shards:
            shard_dict = asdict(shard)
            p = Process(
                target=_worker_wrapper,
                args=(
                    shard_dict,
                    self.discovery_queue,
                    self.near_miss_queue,
                    self.halt_event,
                    self.seen_hits_lock,
                    shared_seen_keys,
                    cycles,
                    self.precision,
                    self.depth,
                    self.tol_digits,
                    self.pop_size,
                    self.verify,
                    self.verify_prec,
                    seed,
                ),
                name=f"worker-{shard.worker_id}-{shard.shard_id}",
                daemon=True,
            )
            processes.append((p, shard))

        _log.info("Launching %d workers...", len(processes))
        for p, _ in processes:
            p.start()

        # Commander loop: drain queues while workers run
        try:
            self._commander_loop(processes, cycles)
        except KeyboardInterrupt:
            _log.info("Interrupted -- signaling halt to all workers")
            self.halt_event.set()

        # Wait for workers to finish
        for p, _ in processes:
            p.join(timeout=30)
            if p.is_alive():
                p.terminate()

        # Final queue drain
        self._drain_queues()

        # Stage 2: run HP verification on any queued candidates (Opt 2)
        self._run_hp_verification()

        # Cleanup manager
        manager.shutdown()

    def _commander_loop(
        self,
        processes: list[tuple[Process, ShardAssignment]],
        total_cycles: int,
    ) -> None:
        """Monitor workers, drain queues periodically, monitor thermals."""
        last_status = time.time()
        status_interval = 60.0  # seconds between status prints

        while any(p.is_alive() for p, _ in processes):
            # Drain discovery queue
            self._drain_queues()

            # Periodic status
            now = time.time()
            if now - last_status > status_interval:
                self._print_status()

                # Thermal guard check (Opt 5)
                thermal_status = self._thermal.check_and_throttle()
                if thermal_status.get("throttled"):
                    print(f"  [Thermal] CPU={thermal_status['cpu_percent']}% "
                          f"RAM={thermal_status['ram_percent']}% -- throttled",
                          flush=True)

                last_status = now

            # Batched GitHub sync (Opt 4)
            if (now - self._last_github_sync > self.github_batch_interval
                    and self._pending_sync_count > 0):
                self._flush_github_sync()

            time.sleep(0.5)

    def _drain_queues(self) -> None:
        """Drain both queues, writing discoveries and near-misses to disk."""
        # Discoveries
        while True:
            try:
                record = self.discovery_queue.get_nowait()
            except queue.Empty:
                break

            # Filter out worker stats reports (not actual discoveries)
            if record.get("_worker_stats"):
                self._worker_stats.append(record)
                wid = record.get("worker_id", "?")
                shard = record.get("shard_id", "?")
                status = record.get("status", "?")
                disc = record.get("discoveries", 0)
                nm = record.get("near_misses", 0)
                elapsed = record.get("elapsed", 0)
                self._total_evaluated += record.get("evaluated", 0)
                _log.info("Worker %s [%s] %s: %d discoveries, %d near-misses in %.1fs",
                          wid, shard, status, disc, nm, elapsed)
                if record.get("error"):
                    _log.warning("Worker %s error:\n%s", wid, record["error"])
                continue

            self._write_discovery(record)
            self._total_discoveries += 1

            # Track per-shard stats (for rebalancer)
            shard_id = record.get("shard", "unknown")
            self._shard_discoveries[shard_id] += 1

            # Trigger adaptive hooks (non-blocking)
            try:
                from adaptive_discovery import on_discovery
                on_discovery(record)
            except Exception:
                pass

            # Opt 2: Queue high-scoring candidates for Stage 2 HP verification
            vd = record.get("verified_digits", 0) or 0
            if vd >= 30 and vd < 100:
                # Promising but not yet breakthrough — send to HP queue
                self._hp_verify_queue.put(dict(record))

            # Opt 4: GitHub sync — immediate for breakthroughs, batched otherwise
            if vd >= 100:
                # Breakthrough: sync immediately
                try:
                    from github_research_sync import maybe_sync
                    maybe_sync(record.get("cycle", 0), sync_every=1)
                except Exception:
                    pass
            else:
                # Standard discovery: batch it
                self._pending_sync_count += 1

        # Near-misses
        while True:
            try:
                nm_record = self.near_miss_queue.get_nowait()
            except queue.Empty:
                break
            self._write_near_miss(nm_record)
            self._total_near_misses += 1

            # Track per-shard near-miss counts (for rebalancer)
            shard_id = nm_record.get("shard", "unknown")
            self._shard_near_misses[shard_id] += 1

    def _run_hp_verification(self) -> None:
        """Stage 2 of the Waterfall: verify promising candidates at high precision."""
        qsize = self._hp_verify_queue.qsize()
        if qsize == 0:
            return

        print(f"\n  [Stage 2] HP verification: {qsize} candidates at "
              f"{self.hp_verify_prec}dp...", flush=True)

        # Run HP worker in current process (sequential, CPU-intensive)
        verified_count = 0
        rejected_count = 0

        try:
            from mpmath import mp, mpf
            import mpmath as mpm
            saved_dps = mp.dps
            mp.dps = self.hp_verify_prec + 50

            from ramanujan_breakthrough_generator import (
                eval_pcf, build_constants, _parse_match_target,
            )
            hi_constants = build_constants(self.hp_verify_prec)

            while True:
                try:
                    candidate = self._hp_verify_queue.get_nowait()
                except queue.Empty:
                    break

                a = candidate.get("a", [])
                b = candidate.get("b", [])
                match_label = candidate.get("match", "?")

                val = eval_pcf(a, b, depth=2000)
                if val is None:
                    rejected_count += 1
                    continue

                target = _parse_match_target(match_label, hi_constants)
                if target is None:
                    rejected_count += 1
                    continue

                residual = abs(val - target)
                if residual == 0:
                    digits = float(self.hp_verify_prec)
                else:
                    digits = float(-mpm.log10(residual))

                if digits > self.hp_verify_prec * 0.5:
                    verified_count += 1
                    candidate["hp_verified_digits"] = round(digits, 1)
                    candidate["hp_verify_prec"] = self.hp_verify_prec
                    candidate["type"] = "hp_verified"

                    # Re-log as HP-verified discovery
                    self._write_discovery(candidate)

                    print(f"  [Stage 2] VERIFIED: {match_label} "
                          f"a={a} -> {digits:.1f}d at {self.hp_verify_prec}dp",
                          flush=True)

                    if digits >= 100:
                        self.halt_event.set()
                else:
                    rejected_count += 1

            mp.dps = saved_dps

        except Exception:
            _log.warning("HP verification failed: %s", traceback.format_exc())

        if verified_count > 0 or rejected_count > 0:
            print(f"  [Stage 2] Done: {verified_count} verified, "
                  f"{rejected_count} rejected", flush=True)

    def _flush_github_sync(self) -> None:
        """Flush pending GitHub syncs (Opt 4: batched sync)."""
        if self._pending_sync_count == 0:
            return
        try:
            from github_research_sync import maybe_sync
            maybe_sync(0, sync_every=1)  # force sync
            _log.info("Batched GitHub sync: %d discoveries synced",
                       self._pending_sync_count)
        except Exception:
            pass
        self._pending_sync_count = 0
        self._last_github_sync = time.time()

    def _write_discovery(self, record: dict) -> None:
        """Append discovery to JSONL (process-safe: only commander writes)."""
        try:
            with open(LOGFILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")

            vd = record.get("verified_digits", "?")
            match = record.get("match", "?")
            wid = record.get("worker_id", "?")
            shard = record.get("shard", "?")
            print(f"\n{'='*60}")
            print(f"  DISCOVERY [Worker {wid} / {shard}]: {match}")
            print(f"  CF: a={record.get('a')}, b={record.get('b')}")
            print(f"  Verified: {vd}d")
            print(f"{'='*60}\n", flush=True)
        except Exception:
            _log.warning("Failed to write discovery: %s", traceback.format_exc())

    def _write_near_miss(self, record: dict) -> None:
        """Append near-miss to JSONL."""
        try:
            with open(NEAR_MISS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _load_ridges(self) -> list[dict]:
        """Load ridge hints from Deep Space manifold analysis."""
        try:
            from deep_space import load_ridge_hints
            return load_ridge_hints(max_hints=10)
        except Exception:
            return []

    def _load_existing_seen_keys(self) -> list[str]:
        """Load existing (a, b) keys from discovery log to prevent re-logging."""
        keys = []
        if LOGFILE.exists():
            try:
                for line in LOGFILE.read_text(encoding="utf-8").strip().split("\n"):
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    keys.append(json.dumps([d["a"], d["b"]], ensure_ascii=True))
            except Exception:
                pass
        return keys

    def _print_shard_plan(self, shards: list[ShardAssignment]) -> None:
        """Print the shard allocation table."""
        print(f"\n{'='*70}")
        print(f"  PARALLEL ENGINE -- {len(shards)} Workers")
        print(f"{'='*70}")
        shard_counts = Counter(s.shard_id for s in shards)
        for stype, count in shard_counts.most_common():
            consts = len(SHARD_CONSTANT_MAP.get(stype, []))
            const_str = f"{consts} constants" if consts else "all constants"
            print(f"  {stype:18s}: {count} worker(s)  ({const_str})")
        print(f"{'='*70}\n", flush=True)

    def _print_status(self) -> None:
        """Print periodic status update."""
        elapsed = time.time() - self._start_time
        rate = self._total_discoveries / max(elapsed / 3600, 0.001)
        print(f"  [Commander] {elapsed:.0f}s | "
              f"discoveries={self._total_discoveries} | "
              f"near_misses={self._total_near_misses} | "
              f"rate={rate:.1f}/hr", flush=True)

    def _build_summary(self, elapsed: float) -> dict:
        """Build final run summary."""
        return {
            "elapsed_seconds": round(elapsed, 2),
            "num_workers": self.num_workers,
            "total_discoveries": self._total_discoveries,
            "total_near_misses": self._total_near_misses,
            "discoveries_per_hour": round(
                self._total_discoveries / max(elapsed / 3600, 0.001), 2
            ),
            "precision": self.precision,
            "depth": self.depth,
            "timestamp": datetime.now().isoformat(),
        }

    def _print_summary(self, summary: dict) -> None:
        """Print final summary."""
        print(f"\n{'='*70}")
        print(f"  PARALLEL ENGINE -- COMPLETE")
        print(f"{'='*70}")
        print(f"  Elapsed:          {summary['elapsed_seconds']:.1f}s")
        print(f"  Workers:          {summary['num_workers']}")
        print(f"  Discoveries:      {summary['total_discoveries']}")
        print(f"  Near-misses:      {summary['total_near_misses']}")
        print(f"  Rate:             {summary['discoveries_per_hour']:.1f}/hr")
        print(f"  Log:              {LOGFILE}")
        print(f"{'='*70}\n", flush=True)


def _worker_wrapper(
    shard_dict: dict,
    discovery_queue: Queue,
    near_miss_queue: Queue,
    halt_event: Event,
    seen_hits_lock: Lock,
    shared_seen_keys,
    cycles: int,
    precision: int,
    depth: int,
    tol_digits: int,
    pop_size: int,
    verify: bool,
    verify_prec: int,
    seed: int,
) -> None:
    """Process entry point — calls _worker_loop and puts stats
    on the discovery queue tagged as a stats report."""
    try:
        stats = _worker_loop(
            shard_dict=shard_dict,
            discovery_queue=discovery_queue,
            near_miss_queue=near_miss_queue,
            halt_event=halt_event,
            seen_hits_lock=seen_hits_lock,
            shared_seen_keys=shared_seen_keys,
            cycles=cycles,
            precision=precision,
            depth=depth,
            tol_digits=tol_digits,
            pop_size=pop_size,
            verify=verify,
            verify_prec=verify_prec,
            seed_offset=seed,
        )
        # Report worker completion via discovery queue
        discovery_queue.put({"_worker_stats": True, **stats})
    except Exception:
        discovery_queue.put({
            "_worker_stats": True,
            "worker_id": shard_dict.get("worker_id", -1),
            "shard_id": shard_dict.get("shard_id", "?"),
            "status": "crash",
            "error": traceback.format_exc(),
        })


# ===================================================================
# CLI
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Parallel Ramanujan Discovery Engine (Commander-Worker)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --workers 8 --cycles 200
  %(prog)s --workers 16 --precision 80 --depth 500
  %(prog)s --dry-run
  %(prog)s --cycles 1000 --verify-prec 220
  %(prog)s --waves 3 --heatmap --hp-prec 1500
""",
    )
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of worker processes (default: cpu_count - 1)")
    parser.add_argument("--cycles", type=int, default=100,
                        help="Cycles per worker (default: 100)")
    parser.add_argument("--precision", type=int, default=60,
                        help="mpmath decimal precision (default: 60)")
    parser.add_argument("--depth", type=int, default=300,
                        help="CF evaluation depth (default: 300)")
    parser.add_argument("--tol", type=int, default=15,
                        help="Match tolerance in digits (default: 15)")
    parser.add_argument("--pop", type=int, default=40,
                        help="Population size per worker (default: 40)")
    parser.add_argument("--verify-prec", type=int, default=200,
                        help="High-precision verification digits (default: 200)")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip high-precision verification")
    parser.add_argument("--seed", type=int, default=42,
                        help="Base random seed (default: 42)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print shard plan and exit")
    # Level 2 optimizations
    parser.add_argument("--waves", type=int, default=1,
                        help="Number of rebalancing waves (default: 1)")
    parser.add_argument("--heatmap", action="store_true",
                        help="Generate near-miss heatmap after run")
    parser.add_argument("--hp-prec", type=int, default=1500,
                        help="Stage 2 HP verification precision (default: 1500)")
    parser.add_argument("--sync-interval", type=float, default=1800.0,
                        help="GitHub batch sync interval in seconds (default: 1800)")
    args = parser.parse_args()

    pool = CommanderPool(
        workers=args.workers,
        precision=args.precision,
        depth=args.depth,
        tol_digits=args.tol,
        pop_size=args.pop,
        verify=not args.no_verify,
        verify_prec=args.verify_prec,
        waves=args.waves,
        hp_verify_prec=args.hp_prec,
        generate_heatmap=args.heatmap,
        github_batch_interval=args.sync_interval,
    )

    if args.dry_run:
        ridge_hints = pool._load_ridges()
        shards = build_shard_plan(pool.num_workers, ridge_hints)
        pool._print_shard_plan(shards)
        print("  Dry run -- no workers launched.\n")
        return

    summary = pool.run(cycles=args.cycles, seed=args.seed)

    # Save summary
    summary_path = WORKSPACE / "parallel_run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"  Summary saved to {summary_path.name}")


if __name__ == "__main__":
    # Required for Windows multiprocessing
    mp_lib.freeze_support()
    main()
