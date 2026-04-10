#!/usr/bin/env python3
"""
forge_core.py — The Forge core skeleton
======================================

Hybrid-precision discovery engine for polynomial continued fractions (PCFs).

Design goals
------------
1. Use a Numba-accelerated float64 scout to sweep large parameter regions fast.
2. Promote only genuinely "hot" candidates into high-precision `mpmath`.
3. Keep the search thermal-aware on an 8-core i7 by pacing dense loops.
4. Persist candidates with convergence metrics and Casoratian signatures.

The default family is intentionally simple and swappable:

    a_n = n * (n + alpha) + beta
    b_n = 2n + gamma

Replace `_a_term_float`, `_b_term_float`, `_a_term_mp`, and `_b_term_mp`
with the PCF family you want to explore.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Sequence

import mpmath as mpm
from mpmath import mp

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise SystemExit("numpy is required for forge_core.py") from exc

try:
    from numba import njit
    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*args, **kwargs):
        """Fallback no-op decorator when numba is unavailable."""
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

try:
    import psutil
    HAVE_PSUTIL = True
except ImportError:  # pragma: no cover
    psutil = None
    HAVE_PSUTIL = False


# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------


def _target_library() -> dict[str, Any]:
    return {
        "zeta3": lambda: mp.zeta(3),
        "catalan": lambda: mp.catalan,
        "pi": lambda: mp.pi,
        "4/pi": lambda: 4 / mp.pi,
        "pi^2": lambda: mp.pi**2,
        "ln2": lambda: mp.log(2),
        "euler_gamma": lambda: mp.euler,
    }


@dataclass(frozen=True, slots=True)
class ForgeConfig:
    target_name: str = "zeta3"
    scout_depths: tuple[int, int, int] = (64, 128, 256)
    validator_depths: tuple[int, int] = (600, 1200)
    validator_dps: int = 1200
    scout_tol: float = 1e-12
    scout_stability_tol: float = 1e-10
    min_log_slope: float = 0.20
    max_workers: int = min(8, os.cpu_count() or 1)
    chunk_size: int = 2048
    pslq_maxcoeff: int = 2000
    pslq_tol_digits: int = 80
    output_dir: str = "discoveries/forge"
    run_label: str = "forge_run"
    density_check_every: int = 4096
    cpu_threshold: float = 92.0
    micro_sleep: float = 0.004


@dataclass(frozen=True, slots=True)
class ParameterPoint:
    alpha: float
    beta: float
    gamma: float


@dataclass(slots=True)
class ScoutHit:
    alpha: float
    beta: float
    gamma: float
    scout_value: float
    scout_residual: float
    convergence_delta: float
    log_slope: float
    casoratian_signature: str
    gate_reason: str = ""


@dataclass(slots=True)
class CandidateIdentity:
    alpha: float
    beta: float
    gamma: float
    target_name: str
    scout_value: float
    scout_residual: float
    validator_value: str
    validator_residual: str
    validator_delta: str
    log_slope: float
    convergence_rate: str
    casoratian_signature: str
    pslq_relation: str
    validator_dps: int
    scout_depths: tuple[int, int, int]
    validator_depths: tuple[int, int]
    status: str = "validated"


# ---------------------------------------------------------------------------
# Thermal guard
# ---------------------------------------------------------------------------


class ThermalGuard:
    """Micro-throttle dense loops to reduce thermal collapse on laptop CPUs.

    This can be used as a decorator around an inner sweep function. The wrapper
    itself is kept local to each worker process, so Windows process spawning
    stays safe.
    """

    def __init__(
        self,
        density_check_every: int = 4096,
        cpu_threshold: float = 92.0,
        micro_sleep: float = 0.004,
    ):
        self.density_check_every = max(1, density_check_every)
        self.cpu_threshold = cpu_threshold
        self.micro_sleep = max(0.0, micro_sleep)
        self._counter = 0

    def pulse(self, step: int = 1) -> None:
        self._counter += step
        if self._counter % self.density_check_every != 0:
            return
        if not HAVE_PSUTIL:
            return
        try:
            cpu = psutil.cpu_percent(interval=0.0)
        except Exception:
            return
        if cpu >= self.cpu_threshold:
            time.sleep(self.micro_sleep)

    def decorate(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            kwargs.setdefault("thermal_guard", self)
            return func(*args, **kwargs)

        return wrapper


# ---------------------------------------------------------------------------
# PCF family hooks — replace these for new families
# ---------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def _a_term_float(n: int, alpha: float, beta: float, gamma: float) -> float:
    del gamma
    return n * (n + alpha) + beta


@njit(cache=True, fastmath=True)
def _b_term_float(n: int, alpha: float, beta: float, gamma: float) -> float:
    del alpha, beta
    return 2.0 * n + gamma


def _a_term_mp(n: int, alpha: float, beta: float, gamma: float) -> mpm.mpf:
    del gamma
    n_mp = mp.mpf(n)
    return n_mp * (n_mp + mp.mpf(alpha)) + mp.mpf(beta)


def _b_term_mp(n: int, alpha: float, beta: float, gamma: float) -> mpm.mpf:
    del alpha, beta
    return 2 * mp.mpf(n) + mp.mpf(gamma)


# ---------------------------------------------------------------------------
# Float64 scout (Numba-friendly)
# ---------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def _evaluate_pcf_float(alpha: float, beta: float, gamma: float, depth: int) -> float:
    """Backward CF evaluation at float64 precision for high-speed scouting."""
    tail = 0.0
    for n in range(depth, 0, -1):
        b_n = _b_term_float(n, alpha, beta, gamma)
        denom = b_n + tail
        if denom == 0.0 or not math.isfinite(denom):
            return np.nan
        a_n = _a_term_float(n, alpha, beta, gamma)
        tail = a_n / denom
        if not math.isfinite(tail):
            return np.nan
    b0 = gamma
    return b0 + tail


@njit(cache=True, fastmath=True)
def _casoratian_signature_float(alpha: float, beta: float, gamma: float, depth: int) -> tuple[float, float, float]:
    """Compressed Casoratian signature based on sign/growth of W_n.

    Uses the stable recurrence W_n = -a_n * W_{n-1}. To avoid overflow, we keep
    only sign and log10 magnitude summaries.
    """
    sign = 1.0
    log_mag = 0.0
    signed_total = 0.0
    window = 6
    start = max(1, depth - window + 1)
    count = 0
    first_log = 0.0

    for n in range(1, depth + 1):
        a_n = _a_term_float(n, alpha, beta, gamma)
        if a_n == 0.0 or not math.isfinite(a_n):
            return 0.0, 0.0, -np.inf
        sign *= -1.0 if a_n > 0.0 else 1.0
        log_mag += math.log10(abs(a_n))
        if n == start:
            first_log = log_mag
        if n >= start:
            signed_total += sign
            count += 1

    mean_sign = signed_total / count if count else 0.0
    growth = (log_mag - first_log) / max(count - 1, 1)
    return mean_sign, growth, log_mag


@njit(cache=True, fastmath=True)
def _scout_metrics(
    alpha: float,
    beta: float,
    gamma: float,
    target_value: float,
    d1: int,
    d2: int,
    d3: int,
) -> tuple[float, float, float, float, float, float, float]:
    v1 = _evaluate_pcf_float(alpha, beta, gamma, d1)
    v2 = _evaluate_pcf_float(alpha, beta, gamma, d2)
    v3 = _evaluate_pcf_float(alpha, beta, gamma, d3)

    if not math.isfinite(v1) or not math.isfinite(v2) or not math.isfinite(v3):
        return np.nan, np.inf, np.inf, -np.inf, 0.0, 0.0, -np.inf

    delta12 = abs(v2 - v1)
    delta23 = abs(v3 - v2)
    residual = abs(v3 - target_value)

    eps = 1e-300
    if delta12 <= 0.0 or delta23 <= 0.0:
        slope = 0.0
    else:
        slope = math.log10((delta12 + eps) / (delta23 + eps))

    sig_a, sig_b, sig_c = _casoratian_signature_float(alpha, beta, gamma, d3)
    return v3, residual, delta23, slope, sig_a, sig_b, sig_c


# ---------------------------------------------------------------------------
# High-precision validation (`mpmath`)
# ---------------------------------------------------------------------------


def evaluate_pcf_mp(point: ParameterPoint, depth: int) -> mpm.mpf:
    """High-precision evaluation used only after scout promotion."""
    tail = mp.zero
    for n in range(depth, 0, -1):
        a_n = _a_term_mp(n, point.alpha, point.beta, point.gamma)
        b_n = _b_term_mp(n, point.alpha, point.beta, point.gamma)
        denom = b_n + tail
        if denom == 0:
            raise ZeroDivisionError(f"Zero denominator at n={n} for {point}")
        tail = a_n / denom
    return mp.mpf(point.gamma) + tail


def high_precision_casoratian(point: ParameterPoint, depth: int = 64) -> str:
    sign = mp.mpf(1)
    log_mag = mp.zero
    tail: list[str] = []
    start = max(1, depth - 5)
    for n in range(1, depth + 1):
        a_n = _a_term_mp(n, point.alpha, point.beta, point.gamma)
        if a_n == 0:
            return "zero-casoratian"
        if a_n > 0:
            sign *= -1
        log_mag += mp.log10(abs(a_n))
        if n >= start:
            tail.append("+" if sign > 0 else "-")
    return f"{''.join(tail)}|log10|W_n|≈{mp.nstr(log_mag, 8)}"


def pslq_probe(value: mpm.mpf, target_name: str, maxcoeff: int = 2000, tol_digits: int = 80) -> str:
    """Try to express the validated value in a small basis of known constants."""
    library = _target_library()
    basis_names = [target_name, "pi", "ln2", "catalan", "euler_gamma", "1"]
    basis_values = []
    effective_names = []

    for name in basis_names:
        if name == "1":
            basis_values.append(mp.mpf(1))
            effective_names.append(name)
        elif name in library:
            basis_values.append(library[name]())
            effective_names.append(name)

    try:
        identified = mpm.identify(value)
        if identified:
            return str(identified)
    except Exception:
        pass

    vec = [value] + basis_values
    try:
        rel = mp.pslq(vec, maxcoeff=maxcoeff, tol=mp.mpf(10) ** (-tol_digits))
    except Exception as exc:
        return f"pslq-error: {exc}"

    if not rel:
        return ""

    labels = ["x"] + effective_names
    terms = [f"{coef}*{label}" for coef, label in zip(rel, labels) if coef]
    if not terms:
        return ""
    return " + ".join(terms) + " = 0"


def validate_hit(hit: ScoutHit, config: ForgeConfig) -> Optional[CandidateIdentity]:
    """Escalate a hot scout hit into 1000–1500 dp only when warranted."""
    point = ParameterPoint(hit.alpha, hit.beta, hit.gamma)
    target_value = _target_library()[config.target_name]()

    with mp.workdps(config.validator_dps):
        v_lo = evaluate_pcf_mp(point, config.validator_depths[0])
        v_hi = evaluate_pcf_mp(point, config.validator_depths[1])
        residual = abs(v_hi - target_value)
        delta = abs(v_hi - v_lo)
        slope_metric = max(hit.log_slope, 0.0)
        convergence_rate = f"log-slope≈{slope_metric:.3f}, Δ_hp≈{mp.nstr(delta, 8)}"
        casoratian = high_precision_casoratian(point)
        relation = pslq_probe(
            v_hi,
            config.target_name,
            maxcoeff=config.pslq_maxcoeff,
            tol_digits=config.pslq_tol_digits,
        )

    return CandidateIdentity(
        alpha=hit.alpha,
        beta=hit.beta,
        gamma=hit.gamma,
        target_name=config.target_name,
        scout_value=hit.scout_value,
        scout_residual=hit.scout_residual,
        validator_value=mp.nstr(v_hi, 50),
        validator_residual=mp.nstr(residual, 12),
        validator_delta=mp.nstr(delta, 12),
        log_slope=hit.log_slope,
        convergence_rate=convergence_rate,
        casoratian_signature=casoratian,
        pslq_relation=relation,
        validator_dps=config.validator_dps,
        scout_depths=config.scout_depths,
        validator_depths=config.validator_depths,
    )


# ---------------------------------------------------------------------------
# Handoff gate — the key scout → validator logic
# ---------------------------------------------------------------------------


def should_promote(hit: ScoutHit, config: ForgeConfig) -> tuple[bool, str]:
    """Only allow truly promising candidates into expensive multi-precision.

    This is the key budget-protection rule for The Forge.
    """
    if not math.isfinite(hit.scout_value):
        return False, "non-finite scout value"
    if hit.scout_residual >= config.scout_tol:
        return False, "residual above scout threshold"
    if hit.convergence_delta >= config.scout_stability_tol:
        return False, "unstable across scout depths"
    if hit.log_slope < config.min_log_slope:
        return False, "cold convergence slope"
    return True, "promote-to-mpmath"


def dedupe_hot_hits(hits: Iterable[ScoutHit]) -> Iterator[ScoutHit]:
    seen: set[tuple[int, int, int, int]] = set()
    for hit in hits:
        key = (
            round(hit.alpha * 10_000),
            round(hit.beta * 10_000),
            round(hit.gamma * 10_000),
            round(hit.scout_value * 1_000_000_000_000),
        )
        if key in seen:
            continue
        seen.add(key)
        yield hit


# ---------------------------------------------------------------------------
# Parallel scout engine
# ---------------------------------------------------------------------------


def chunked(iterable: Iterable[ParameterPoint], size: int) -> Iterator[list[ParameterPoint]]:
    bucket: list[ParameterPoint] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def _sweep_chunk(points: Sequence[ParameterPoint], config: ForgeConfig, target_float: float) -> list[dict[str, Any]]:
    """Worker-side scout sweep.

    Returns only hot hits as plain dictionaries to keep cross-process payloads
    simple and cheap.
    """
    guard = ThermalGuard(
        density_check_every=config.density_check_every,
        cpu_threshold=config.cpu_threshold,
        micro_sleep=config.micro_sleep,
    )

    @guard.decorate
    def guarded_sweep(points: Sequence[ParameterPoint], thermal_guard: Optional[ThermalGuard] = None) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        d1, d2, d3 = config.scout_depths
        for point in points:
            if thermal_guard is not None:
                thermal_guard.pulse()
            v, residual, delta, slope, sig_a, sig_b, sig_c = _scout_metrics(
                point.alpha,
                point.beta,
                point.gamma,
                target_float,
                d1,
                d2,
                d3,
            )
            hit = ScoutHit(
                alpha=point.alpha,
                beta=point.beta,
                gamma=point.gamma,
                scout_value=float(v),
                scout_residual=float(residual),
                convergence_delta=float(delta),
                log_slope=float(slope),
                casoratian_signature=f"{sig_a:+.2f}|{sig_b:.3f}|{sig_c:.3f}",
            )
            promote, reason = should_promote(hit, config)
            if promote:
                hit.gate_reason = reason
                collected.append(asdict(hit))
        return collected

    return guarded_sweep(points)


def run_parallel_scout(config: ForgeConfig, grid: Iterable[ParameterPoint]) -> list[ScoutHit]:
    target_mp = _target_library()[config.target_name]()
    target_float = float(target_mp)
    all_hits: list[ScoutHit] = []

    with futures.ProcessPoolExecutor(max_workers=config.max_workers) as pool:
        submitted = [
            pool.submit(_sweep_chunk, chunk, config, target_float)
            for chunk in chunked(grid, config.chunk_size)
        ]
        for future in futures.as_completed(submitted):
            payload = future.result()
            for item in payload:
                all_hits.append(ScoutHit(**item))

    return list(dedupe_hot_hits(all_hits))


# ---------------------------------------------------------------------------
# Persistence and reporting
# ---------------------------------------------------------------------------


def persist_candidates(candidates: Sequence[CandidateIdentity], config: ForgeConfig) -> tuple[Path, Path]:
    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{config.run_label}_candidates.jsonl"
    csv_path = out_dir / f"{config.run_label}_candidates.csv"

    with json_path.open("a", encoding="utf-8") as jf:
        for cand in candidates:
            jf.write(json.dumps(asdict(cand), ensure_ascii=False) + "\n")

    fieldnames = list(asdict(candidates[0]).keys()) if candidates else [
        "alpha", "beta", "gamma", "target_name", "scout_value", "scout_residual",
        "validator_value", "validator_residual", "validator_delta", "log_slope",
        "convergence_rate", "casoratian_signature", "pslq_relation",
        "validator_dps", "scout_depths", "validator_depths", "status",
    ]

    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", encoding="utf-8", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for cand in candidates:
            writer.writerow(asdict(cand))

    return json_path, csv_path


# ---------------------------------------------------------------------------
# Grid helpers and orchestration
# ---------------------------------------------------------------------------


def build_axis(start: float, stop: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("step must be positive")
    count = int(round((stop - start) / step)) + 1
    return [start + i * step for i in range(max(count, 0))]


def parameter_grid(
    alpha_values: Sequence[float],
    beta_values: Sequence[float],
    gamma_values: Sequence[float],
) -> Iterator[ParameterPoint]:
    for alpha in alpha_values:
        for beta in beta_values:
            for gamma in gamma_values:
                yield ParameterPoint(alpha=float(alpha), beta=float(beta), gamma=float(gamma))


def run_forge(config: ForgeConfig, grid: Iterable[ParameterPoint]) -> list[CandidateIdentity]:
    hot_hits = run_parallel_scout(config, grid)
    validated: list[CandidateIdentity] = []

    for hit in hot_hits:
        candidate = validate_hit(hit, config)
        if candidate is not None:
            validated.append(candidate)

    if validated:
        persist_candidates(validated, config)
    return validated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="The Forge — hybrid-precision PCF search skeleton")
    parser.add_argument("--target", default="zeta3", choices=sorted(_target_library().keys()))
    parser.add_argument("--alpha", nargs=3, type=float, metavar=("START", "STOP", "STEP"), default=(-4.0, 4.0, 0.5))
    parser.add_argument("--beta", nargs=3, type=float, metavar=("START", "STOP", "STEP"), default=(-4.0, 4.0, 0.5))
    parser.add_argument("--gamma", nargs=3, type=float, metavar=("START", "STOP", "STEP"), default=(1.0, 8.0, 0.5))
    parser.add_argument("--scout-tol", type=float, default=1e-12)
    parser.add_argument("--validator-dps", type=int, default=1200)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--run-label", default="forge_run")
    parser.add_argument("--output-dir", default="discoveries/forge")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ForgeConfig(
        target_name=args.target,
        scout_tol=args.scout_tol,
        validator_dps=args.validator_dps,
        max_workers=min(args.workers, os.cpu_count() or 1),
        run_label=args.run_label,
        output_dir=args.output_dir,
    )

    alpha_values = build_axis(*args.alpha)
    beta_values = build_axis(*args.beta)
    gamma_values = build_axis(*args.gamma)
    grid = parameter_grid(alpha_values, beta_values, gamma_values)

    t0 = time.time()
    validated = run_forge(config, grid)
    elapsed = time.time() - t0

    print("\nThe Forge summary")
    print("-----------------")
    print(f"Target:              {config.target_name}")
    print(f"Scout workers:       {config.max_workers}")
    print(f"Numba enabled:       {'yes' if HAVE_NUMBA else 'no'}")
    print(f"Validated hits:      {len(validated)}")
    print(f"Elapsed seconds:     {elapsed:.2f}")
    if validated:
        best = min(validated, key=lambda c: mp.mpf(c.validator_residual))
        print(f"Best residual:       {best.validator_residual}")
        print(f"Best point:          (α,β,γ)=({best.alpha}, {best.beta}, {best.gamma})")
        if best.pslq_relation:
            print(f"PSLQ:                {best.pslq_relation}")


if __name__ == "__main__":
    main()
