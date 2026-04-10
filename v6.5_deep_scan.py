#!/usr/bin/env python3
"""
v6.5_deep_scan.py
=================

Deep Forge / SIARC v6.5 scan for the Apéry-template ↔ V_quad frontier.

This script pushes beyond linear A/B shifts and explores:

1. Quadratic intertwiners
   A(m) = 17 + a1*m + a2*m^2
   B(m) =  5 + b1*m + b2*m^2

2. C-relaxed Apéry numerators
   alpha_m(n) = -C*n^6                 (fixed_alpha)
   alpha_m(n) = -C*n^4*(n+m)^2         (shifted_alpha)

3. V_quad bridge perturbations on the denominator
   beta_m(n) = (2n+1)(A(m)n^2 + A(m)n + B(m)) + bridge*(3n^2 + n + 1)

4. Stability-as-signal scoring
   - depth-30 / depth-90 / depth-150 scout
   - stability decay rate
   - Bayesian evidence ratio for "stable" vs "collapsing"
   - near-miss shift suggestions

5. High-precision validation
   - `mpmath` reruns at 1500 dps
   - PSLQ against {zeta(3), V_quad, pi^2, 1}
   - SymPy Riccati / nullspace probe across m, m+1, m+2

Usage examples
--------------
python v6.5_deep_scan.py --workers 8 --top-k 20
python v6.5_deep_scan.py --a1-radius 1 --b1-radius 1 --a2-min -1 --a2-max 1 --b2-min -1 --b2-max 1 --workers 1
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Sequence

import mpmath as mpm
from mpmath import mp

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise SystemExit("numpy is required: pip install numpy") from exc

try:
    import sympy as sp
    HAVE_SYMPY = True
except ImportError:  # pragma: no cover
    sp = None
    HAVE_SYMPY = False

try:
    from numba import njit
    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*args, **kwargs):
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


RESULT_DIR = Path("results")
JSON_PATH = RESULT_DIR / "v6_5_deep_scan.json"
CSV_PATH = RESULT_DIR / "v6_5_deep_scan.csv"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeepSpec:
    family: str
    a1: int
    a2: int
    b1: int
    b2: int
    c_scale: int
    bridge: int


@dataclass(frozen=True, slots=True)
class DeepConfig:
    scout_depths: tuple[int, int, int] = (30, 90, 150)
    validator_depths: tuple[int, int] = (250, 600)
    validator_dps: int = 1500
    workers: int = min(8, os.cpu_count() or 1)
    chunk_size: int = 48
    top_k: int = 20
    keep_per_chunk: int = 10
    m_values: tuple[int, int, int, int] = (0, 1, 2, 3)
    thermal_every: int = 2048
    cpu_threshold: float = 92.0
    micro_sleep: float = 0.004
    scout_min_score: float = 2.0
    scout_min_digits: float = 2.5


@dataclass(slots=True)
class ScoutRecord:
    family: str
    a1: int
    a2: int
    b1: int
    b2: int
    c_scale: int
    bridge: int
    best_zeta_label: str
    best_zeta_digits: float
    best_vquad_label: str
    best_vquad_digits: float
    best_m_for_zeta: int
    best_m_for_vquad: int
    stability_low: float
    stability_high: float
    stability_decay_rate: float
    bayes_log10_evidence: float
    intersection_score: float
    near_miss_shift: str
    scout_summary: dict[str, dict[str, float]]


@dataclass(slots=True)
class ValidationRecord:
    family: str
    a1: int
    a2: int
    b1: int
    b2: int
    c_scale: int
    bridge: int
    best_zeta_label: str
    best_zeta_digits: float
    best_vquad_label: str
    best_vquad_digits: float
    stability_decay_rate: float
    bayes_log10_evidence: float
    intersection_score: float
    near_miss_shift: str
    validated_values: dict[str, str]
    validator_deltas: dict[str, str]
    pslq_relation: str
    riccati_nullity: int
    riccati_relation: str
    riccati_residual: str
    casoratian_signature: str
    status: str = "validated"


# ---------------------------------------------------------------------------
# Thermal guard
# ---------------------------------------------------------------------------


class ThermalGuard:
    def __init__(self, every: int = 2048, cpu_threshold: float = 92.0, micro_sleep: float = 0.004):
        self.every = max(1, every)
        self.cpu_threshold = cpu_threshold
        self.micro_sleep = max(0.0, micro_sleep)
        self.counter = 0

    def pulse(self, step: int = 1) -> None:
        self.counter += step
        if self.counter % self.every != 0:
            return
        if not HAVE_PSUTIL:
            return
        try:
            cpu = psutil.cpu_percent(interval=0.0)
        except Exception:
            return
        if cpu >= self.cpu_threshold:
            time.sleep(self.micro_sleep)


# ---------------------------------------------------------------------------
# Reference constants
# ---------------------------------------------------------------------------


def load_vquad_reference(dps: int = 120) -> mpm.mpf:
    ref_path = Path("V_quad_1000digits.txt")
    if ref_path.exists():
        text = ref_path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if "V_quad" in line and "=" in line:
                try:
                    raw = line.split("=", 1)[1].strip().rstrip(".")
                    with mp.workdps(dps):
                        return mp.mpf(raw)
                except Exception:
                    continue
    with mp.workdps(dps):
        tail = mp.zero
        for n in range(2500, 0, -1):
            denom = 3 * n * n + n + 1 + tail
            tail = mp.one / denom
        return 1 + tail


# ---------------------------------------------------------------------------
# Family definition
# ---------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def _A_of_m(a1: int, a2: int, m: int) -> float:
    return 17.0 + a1 * m + a2 * m * m


@njit(cache=True, fastmath=True)
def _B_of_m(b1: int, b2: int, m: int) -> float:
    return 5.0 + b1 * m + b2 * m * m


@njit(cache=True, fastmath=True)
def _alpha_float(family_id: int, c_scale: int, n: int, m: int) -> float:
    nf = float(n)
    mf = float(m)
    if family_id == 0:  # fixed_alpha
        return -float(c_scale) * (nf ** 6)
    return -float(c_scale) * (nf ** 4) * ((nf + mf) ** 2)


@njit(cache=True, fastmath=True)
def _beta_float(a1: int, a2: int, b1: int, b2: int, bridge: int, n: int, m: int) -> float:
    nf = float(n)
    A = _A_of_m(a1, a2, m)
    B = _B_of_m(b1, b2, m)
    apery_core = (2.0 * nf + 1.0) * (A * nf * nf + A * nf + B)
    vquad_core = float(bridge) * (3.0 * nf * nf + nf + 1.0)
    return apery_core + vquad_core


@njit(cache=True, fastmath=True)
def eval_cf_scout_core(
    family_id: int,
    a1: int,
    a2: int,
    b1: int,
    b2: int,
    c_scale: int,
    bridge: int,
    m: int,
    depth: int,
) -> float:
    tail = 0.0
    for n in range(depth, 0, -1):
        a_n = _alpha_float(family_id, c_scale, n, m)
        b_n = _beta_float(a1, a2, b1, b2, bridge, n, m)
        denom = b_n + tail
        if denom == 0.0 or not math.isfinite(denom):
            return np.nan
        tail = a_n / denom
        if not math.isfinite(tail):
            return np.nan
    b0 = _beta_float(a1, a2, b1, b2, bridge, 0, m)
    out = b0 + tail
    return out if math.isfinite(out) else np.nan


def family_id(name: str) -> int:
    return 0 if name == "fixed_alpha" else 1


def alpha_mp(spec: DeepSpec, n: int, m: int) -> mpm.mpf:
    n_mp = mp.mpf(n)
    m_mp = mp.mpf(m)
    if spec.family == "fixed_alpha":
        return -mp.mpf(spec.c_scale) * (n_mp ** 6)
    return -mp.mpf(spec.c_scale) * (n_mp ** 4) * ((n_mp + m_mp) ** 2)


def beta_mp(spec: DeepSpec, n: int, m: int) -> mpm.mpf:
    n_mp = mp.mpf(n)
    A = mp.mpf(17 + spec.a1 * m + spec.a2 * m * m)
    B = mp.mpf(5 + spec.b1 * m + spec.b2 * m * m)
    apery_core = (2 * n_mp + 1) * (A * n_mp * n_mp + A * n_mp + B)
    vquad_core = mp.mpf(spec.bridge) * (3 * n_mp * n_mp + n_mp + 1)
    return apery_core + vquad_core


def eval_cf_mp(spec: DeepSpec, m: int, depth: int) -> mpm.mpf:
    tail = mp.zero
    for n in range(depth, 0, -1):
        a_n = alpha_mp(spec, n, m)
        b_n = beta_mp(spec, n, m)
        denom = b_n + tail
        if denom == 0:
            raise ZeroDivisionError(f"zero denominator at n={n} for {spec}")
        tail = a_n / denom
    return beta_mp(spec, 0, m) + tail


# ---------------------------------------------------------------------------
# Metrics and scoring
# ---------------------------------------------------------------------------


def safe_digits(err: float, floor: float = 1e-300) -> float:
    err = abs(float(err))
    if not math.isfinite(err):
        return 0.0
    return max(0.0, -math.log10(max(err, floor)))


def _normal_logpdf(x: float, mu: float, sigma: float) -> float:
    z = (x - mu) / sigma
    return -0.5 * z * z - math.log(sigma * math.sqrt(2.0 * math.pi))


def bayes_log10_evidence(stability_low: float, stability_high: float) -> float:
    eps = 1e-300
    obs = math.log10((stability_high + eps) / (stability_low + eps))
    log_stable = _normal_logpdf(obs, mu=-0.40, sigma=0.35)
    log_collapse = _normal_logpdf(obs, mu=0.55, sigma=0.40)
    return (log_stable - log_collapse) / math.log(10.0)


def stability_decay_rate(stability_low: float, stability_high: float) -> float:
    eps = 1e-300
    return math.log10((stability_high + eps) / (stability_low + eps))


def target_pools(zeta3_val: float, vquad_val: float) -> tuple[dict[str, float], dict[str, float]]:
    zeta_pool = {
        "zeta3": zeta3_val,
        "1/zeta3": 1.0 / zeta3_val,
        "zeta3/vquad": zeta3_val / vquad_val,
        "zeta3*vquad": zeta3_val * vquad_val,
    }
    vquad_pool = {
        "vquad": vquad_val,
        "1/vquad": 1.0 / vquad_val,
        "vquad/zeta3": vquad_val / zeta3_val,
        "zeta3*vquad": zeta3_val * vquad_val,
    }
    return zeta_pool, vquad_pool


def best_target_match(value: float, pool: dict[str, float], max_num: int = 8, max_den: int = 8) -> tuple[str, float]:
    best_label = "(none)"
    best_digits = 0.0
    for name, target in pool.items():
        for p in range(-max_num, max_num + 1):
            if p == 0:
                continue
            for q in range(1, max_den + 1):
                rat = p / q
                diff = value - rat * target
                digits = safe_digits(diff)
                if digits > best_digits:
                    frac = f"{p}/{q}" if q != 1 else str(p)
                    best_label = f"{frac}*{name}"
                    best_digits = digits
    if math.isfinite(value) and abs(value) > 1e-40:
        inv = 1.0 / value
        for name, target in pool.items():
            diff = inv - target
            digits = safe_digits(diff)
            if digits > best_digits:
                best_label = f"1/value≈{name}"
                best_digits = digits
    return best_label, best_digits


def casoratian_signature(spec: DeepSpec, m: int, depth: int = 12) -> str:
    sign = 1
    log_mag = 0.0
    tail = []
    start = max(1, depth - 5)
    for n in range(1, depth + 1):
        a_n = float(alpha_mp(spec, n, m))
        if a_n == 0 or not math.isfinite(a_n):
            return "degenerate"
        sign *= -1 if a_n > 0 else 1
        log_mag += math.log10(abs(a_n))
        if n >= start:
            tail.append("+" if sign > 0 else "-")
    return f"{''.join(tail)}|log10|W|≈{log_mag:.3f}"


def score_spec(spec: DeepSpec, config: DeepConfig, zeta3_val: float, vquad_val: float) -> Optional[dict[str, Any]]:
    depths = config.scout_depths
    zeta_pool, vquad_pool = target_pools(zeta3_val, vquad_val)
    summary: dict[str, dict[str, float]] = {}

    best_z_label = "(none)"
    best_v_label = "(none)"
    best_z_digits = 0.0
    best_v_digits = 0.0
    best_z_m = -1
    best_v_m = -1
    low_errors = []
    high_errors = []

    for m in config.m_values:
        v30 = eval_cf_scout_core(family_id(spec.family), spec.a1, spec.a2, spec.b1, spec.b2, spec.c_scale, spec.bridge, m, depths[0])
        v90 = eval_cf_scout_core(family_id(spec.family), spec.a1, spec.a2, spec.b1, spec.b2, spec.c_scale, spec.bridge, m, depths[1])
        v150 = eval_cf_scout_core(family_id(spec.family), spec.a1, spec.a2, spec.b1, spec.b2, spec.c_scale, spec.bridge, m, depths[2])
        if not (np.isfinite(v30) and np.isfinite(v90) and np.isfinite(v150)):
            return None
        if abs(v150) > 1e9 or abs(v150) < 1e-18:
            return None

        lo = abs(v90 - v30)
        hi = abs(v150 - v90)
        low_errors.append(lo)
        high_errors.append(hi)

        zlab, zdig = best_target_match(v150, zeta_pool)
        vlab, vdig = best_target_match(v150, vquad_pool)
        summary[str(m)] = {
            "v30": float(v30),
            "v90": float(v90),
            "v150": float(v150),
            "zeta_digits": float(zdig),
            "vquad_digits": float(vdig),
        }
        if zdig > best_z_digits:
            best_z_label, best_z_digits, best_z_m = zlab, zdig, m
        if vdig > best_v_digits:
            best_v_label, best_v_digits, best_v_m = vlab, vdig, m

    stability_lo = max(low_errors) if low_errors else math.inf
    stability_hi = max(high_errors) if high_errors else math.inf
    decay = stability_decay_rate(stability_lo, stability_hi)
    logb10 = bayes_log10_evidence(stability_lo, stability_hi)

    intersection = (
        0.55 * min(best_z_digits, best_v_digits)
        + 0.30 * max(best_z_digits, best_v_digits)
        + 1.50 * max(0.0, logb10)
        - 1.20 * max(0.0, decay)
    )

    return {
        "family": spec.family,
        "a1": spec.a1,
        "a2": spec.a2,
        "b1": spec.b1,
        "b2": spec.b2,
        "c_scale": spec.c_scale,
        "bridge": spec.bridge,
        "best_zeta_label": best_z_label,
        "best_zeta_digits": round(best_z_digits, 3),
        "best_vquad_label": best_v_label,
        "best_vquad_digits": round(best_v_digits, 3),
        "best_m_for_zeta": best_z_m,
        "best_m_for_vquad": best_v_m,
        "stability_low": stability_lo,
        "stability_high": stability_hi,
        "stability_decay_rate": round(decay, 6),
        "bayes_log10_evidence": round(logb10, 6),
        "intersection_score": round(intersection, 6),
        "scout_summary": summary,
    }


def local_perturbations(spec: DeepSpec) -> Iterator[tuple[str, DeepSpec]]:
    deltas = [
        ("a1", 1), ("a1", -1), ("a2", 1), ("a2", -1),
        ("b1", 1), ("b1", -1), ("b2", 1), ("b2", -1),
        ("bridge", 1), ("bridge", -1),
    ]
    for key, delta in deltas:
        payload = asdict(spec)
        payload[key] += delta
        if key == "c_scale" and payload[key] <= 0:
            continue
        yield f"shift {key} by {delta:+d}", DeepSpec(**payload)


def suggest_near_miss_shift(spec: DeepSpec, config: DeepConfig, zeta3_val: float, vquad_val: float, base_score: float) -> str:
    best_note = "hold"
    best_gain = 0.0
    best_decay = None
    for note, neighbor in local_perturbations(spec):
        scored = score_spec(neighbor, config, zeta3_val, vquad_val)
        if not scored:
            continue
        gain = float(scored["intersection_score"]) - base_score
        if gain > best_gain:
            best_gain = gain
            best_note = note
            best_decay = float(scored["stability_decay_rate"])
    if best_gain <= 0.05:
        return "no local recovery shift found"
    if best_decay is None:
        return f"{best_note}"
    return f"{best_note} (predicted Δscore≈{best_gain:.3f}, decay→{best_decay:.3f})"


# ---------------------------------------------------------------------------
# Scout workers
# ---------------------------------------------------------------------------


def chunked(items: Sequence[DeepSpec], chunk_size: int) -> Iterator[list[DeepSpec]]:
    for i in range(0, len(items), chunk_size):
        yield list(items[i:i + chunk_size])


def _worker_chunk(specs: list[DeepSpec], config_dict: dict[str, Any], zeta3_val: float, vquad_val: float) -> list[dict[str, Any]]:
    config = DeepConfig(**config_dict)
    guard = ThermalGuard(config.thermal_every, config.cpu_threshold, config.micro_sleep)
    kept: list[dict[str, Any]] = []
    for spec in specs:
        guard.pulse()
        scored = score_spec(spec, config, zeta3_val, vquad_val)
        if not scored:
            continue
        if max(float(scored["best_zeta_digits"]), float(scored["best_vquad_digits"])) < config.scout_min_digits:
            continue
        if float(scored["intersection_score"]) < config.scout_min_score:
            continue
        shift = suggest_near_miss_shift(spec, config, zeta3_val, vquad_val, float(scored["intersection_score"]))
        scored["near_miss_shift"] = shift
        kept.append(scored)
    kept.sort(key=lambda row: (-float(row["intersection_score"]), -float(row["best_zeta_digits"]), -float(row["best_vquad_digits"])))
    return kept[: config.keep_per_chunk]


# ---------------------------------------------------------------------------
# SymPy Riccati / nullspace probe
# ---------------------------------------------------------------------------


def _basis_monomials(n_value: int, m_value: int) -> list[int]:
    return [1, n_value, m_value, n_value * n_value, n_value * m_value, m_value * m_value]


def _format_poly(coeffs: Sequence[Any], basis_names: Sequence[str]) -> str:
    pieces = []
    for c, name in zip(coeffs, basis_names):
        if c == 0:
            continue
        if name == "1":
            pieces.append(f"({sp.simplify(c)})")
        else:
            pieces.append(f"({sp.simplify(c)})*{name}")
    return " + ".join(pieces) if pieces else "0"


def riccati_nullspace_probe(spec: DeepSpec, sample_depths: Sequence[int] = (18, 24, 30, 36), sample_m: Sequence[int] = (0, 1, 2)) -> tuple[int, str, str]:
    if not HAVE_SYMPY:
        return 0, "sympy-unavailable", "n/a"

    rows = []
    for m_idx in sample_m:
        for depth in sample_depths:
            with mp.workdps(80):
                s0 = eval_cf_mp(spec, m_idx, depth)
                s1 = eval_cf_mp(spec, m_idx + 1, depth)
                s2 = eval_cf_mp(spec, m_idx + 2, depth)
            if s0 == 0 or s1 == 0:
                continue
            r_m = s1 / s0
            r_next = s2 / s1
            mon = _basis_monomials(depth, m_idx)
            row = []
            for phi in mon:
                row.append(sp.nsimplify(float(phi * r_m * r_next), rational=True))
            for phi in mon:
                row.append(sp.nsimplify(float(phi * r_m), rational=True))
            for phi in mon:
                row.append(sp.nsimplify(float(phi * r_next), rational=True))
            for phi in mon:
                row.append(sp.Integer(phi))
            rows.append(row)

    if not rows:
        return 0, "no-rows", "n/a"

    M = sp.Matrix(rows)
    nullspace = M.nullspace()
    if not nullspace:
        return 0, "", "n/a"

    vec = nullspace[0]
    basis_names = ["1", "n", "m", "n^2", "n*m", "m^2"]
    width = len(basis_names)
    rr = vec[0:width]
    r = vec[width:2 * width]
    rp = vec[2 * width:3 * width]
    c0 = vec[3 * width:4 * width]

    relation = (
        f"[{_format_poly(rr, basis_names)}] r_m r_(m+1) + "
        f"[{_format_poly(r, basis_names)}] r_m + "
        f"[{_format_poly(rp, basis_names)}] r_(m+1) + "
        f"[{_format_poly(c0, basis_names)}] = 0"
    )

    max_residual = mp.zero
    for m_idx in (0, 1):
        for depth in (42, 48):
            with mp.workdps(80):
                s0 = eval_cf_mp(spec, m_idx, depth)
                s1 = eval_cf_mp(spec, m_idx + 1, depth)
                s2 = eval_cf_mp(spec, m_idx + 2, depth)
            if s0 == 0 or s1 == 0:
                continue
            r_m = s1 / s0
            r_next = s2 / s1
            mon = _basis_monomials(depth, m_idx)
            rr_val = sum(float(c) * phi for c, phi in zip(rr, mon))
            r_val = sum(float(c) * phi for c, phi in zip(r, mon))
            rp_val = sum(float(c) * phi for c, phi in zip(rp, mon))
            c0_val = sum(float(c) * phi for c, phi in zip(c0, mon))
            resid = abs(rr_val * float(r_m) * float(r_next) + r_val * float(r_m) + rp_val * float(r_next) + c0_val)
            max_residual = max(max_residual, resid)

    return len(nullspace), relation, mp.nstr(max_residual, 8)


# ---------------------------------------------------------------------------
# High-precision validator
# ---------------------------------------------------------------------------


def mp_best_target_match(value: mpm.mpf, pools: dict[str, mpm.mpf]) -> tuple[str, float]:
    best_label = "(none)"
    best_digits = 0.0
    for name, target in pools.items():
        for p in range(-8, 9):
            if p == 0:
                continue
            for q in range(1, 9):
                rat = mp.mpf(p) / q
                diff = abs(value - rat * target)
                digits = 999.0 if diff == 0 else float(-mp.log10(diff))
                if digits > best_digits:
                    frac = f"{p}/{q}" if q != 1 else str(p)
                    best_label = f"{frac}*{name}"
                    best_digits = digits
    if value != 0:
        inv = 1 / value
        for name, target in pools.items():
            diff = abs(inv - target)
            digits = 999.0 if diff == 0 else float(-mp.log10(diff))
            if digits > best_digits:
                best_label = f"1/value≈{name}"
                best_digits = digits
    return best_label, best_digits


def pslq_bridge(value: mpm.mpf, zeta3_ref: mpm.mpf, vquad_ref: mpm.mpf) -> str:
    try:
        identified = mpm.identify(value)
        if identified:
            return str(identified)
    except Exception:
        pass

    vec = [value, zeta3_ref, vquad_ref, mp.pi ** 2, mp.mpf(1)]
    try:
        rel = mp.pslq(vec, maxcoeff=5000, tol=mp.mpf(10) ** (-120))
    except Exception as exc:
        return f"pslq-error: {exc}"
    if not rel:
        return ""
    labels = ["x", "zeta3", "V_quad", "pi^2", "1"]
    pieces = [f"{coef}*{label}" for coef, label in zip(rel, labels) if coef]
    return " + ".join(pieces) + " = 0"


def validate_record(row: dict[str, Any], config: DeepConfig, zeta3_ref: mpm.mpf, vquad_ref: mpm.mpf) -> ValidationRecord:
    spec = DeepSpec(
        family=row["family"],
        a1=int(row["a1"]),
        a2=int(row["a2"]),
        b1=int(row["b1"]),
        b2=int(row["b2"]),
        c_scale=int(row["c_scale"]),
        bridge=int(row["bridge"]),
    )

    zeta_pool = {
        "zeta3": zeta3_ref,
        "1/zeta3": 1 / zeta3_ref,
        "zeta3/vquad": zeta3_ref / vquad_ref,
        "zeta3*vquad": zeta3_ref * vquad_ref,
    }
    vquad_pool = {
        "vquad": vquad_ref,
        "1/vquad": 1 / vquad_ref,
        "vquad/zeta3": vquad_ref / zeta3_ref,
        "zeta3*vquad": zeta3_ref * vquad_ref,
    }

    values: dict[str, str] = {}
    deltas: dict[str, str] = {}
    best_for_pslq = None
    best_pslq_score = -1.0
    hp_best_z_label = row["best_zeta_label"]
    hp_best_z_digits = float(row["best_zeta_digits"])
    hp_best_v_label = row["best_vquad_label"]
    hp_best_v_digits = float(row["best_vquad_digits"])

    with mp.workdps(config.validator_dps):
        for m_idx in config.m_values:
            v_lo = eval_cf_mp(spec, m_idx, config.validator_depths[0])
            v_hi = eval_cf_mp(spec, m_idx, config.validator_depths[1])
            values[str(m_idx)] = mp.nstr(v_hi, 50)
            deltas[str(m_idx)] = mp.nstr(abs(v_hi - v_lo), 12)

            zlab, zdig = mp_best_target_match(v_hi, zeta_pool)
            vlab, vdig = mp_best_target_match(v_hi, vquad_pool)
            if zdig > hp_best_z_digits:
                hp_best_z_label, hp_best_z_digits = zlab, zdig
            if vdig > hp_best_v_digits:
                hp_best_v_label, hp_best_v_digits = vlab, vdig
            if max(zdig, vdig) > best_pslq_score:
                best_pslq_score = max(zdig, vdig)
                best_for_pslq = v_hi

        relation = pslq_bridge(best_for_pslq, zeta3_ref, vquad_ref) if best_for_pslq is not None else ""
        nullity, riccati_relation, riccati_resid = riccati_nullspace_probe(spec)
        cas_sig = casoratian_signature(spec, 0)

    return ValidationRecord(
        family=spec.family,
        a1=spec.a1,
        a2=spec.a2,
        b1=spec.b1,
        b2=spec.b2,
        c_scale=spec.c_scale,
        bridge=spec.bridge,
        best_zeta_label=hp_best_z_label,
        best_zeta_digits=round(hp_best_z_digits, 3),
        best_vquad_label=hp_best_v_label,
        best_vquad_digits=round(hp_best_v_digits, 3),
        stability_decay_rate=float(row["stability_decay_rate"]),
        bayes_log10_evidence=float(row["bayes_log10_evidence"]),
        intersection_score=float(row["intersection_score"]),
        near_miss_shift=str(row.get("near_miss_shift", "")),
        validated_values=values,
        validator_deltas=deltas,
        pslq_relation=relation,
        riccati_nullity=int(nullity),
        riccati_relation=riccati_relation,
        riccati_residual=str(riccati_resid),
        casoratian_signature=cas_sig,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def persist_results(config: DeepConfig, scout_rows: Sequence[dict[str, Any]], validated_rows: Sequence[ValidationRecord]) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "config": asdict(config),
        "numba_enabled": HAVE_NUMBA,
        "sympy_enabled": HAVE_SYMPY,
        "scout_top": list(scout_rows),
        "validated": [asdict(v) for v in validated_rows],
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        fields = [
            "family", "a1", "a2", "b1", "b2", "c_scale", "bridge",
            "best_zeta_label", "best_zeta_digits", "best_vquad_label", "best_vquad_digits",
            "stability_decay_rate", "bayes_log10_evidence", "intersection_score", "near_miss_shift",
            "pslq_relation", "riccati_nullity", "riccati_residual", "casoratian_signature",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in validated_rows:
            rec = asdict(row)
            writer.writerow({key: rec.get(key, "") for key in fields})


# ---------------------------------------------------------------------------
# Search space and orchestration
# ---------------------------------------------------------------------------


def build_specs(args: argparse.Namespace) -> list[DeepSpec]:
    families = ["fixed_alpha", "shifted_alpha"] if args.family == "both" else [args.family]
    a1_values = range(args.a1_center - args.a1_radius, args.a1_center + args.a1_radius + 1)
    b1_values = range(args.b1_center - args.b1_radius, args.b1_center + args.b1_radius + 1)
    a2_values = range(args.a2_min, args.a2_max + 1)
    b2_values = range(args.b2_min, args.b2_max + 1)

    c_values = list(dict.fromkeys(args.c_values + [k * k for k in range(1, args.square_max + 1)]))
    bridge_values = list(dict.fromkeys(args.bridge_values))

    specs = []
    for fam in families:
        for a1 in a1_values:
            for a2 in a2_values:
                for b1 in b1_values:
                    for b2 in b2_values:
                        for c_scale in c_values:
                            for bridge in bridge_values:
                                specs.append(DeepSpec(fam, a1, a2, b1, b2, int(c_scale), int(bridge)))
    return specs


def run_scan(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[ValidationRecord], DeepConfig]:
    config = DeepConfig(workers=min(args.workers, os.cpu_count() or 1), top_k=args.top_k)
    specs = build_specs(args)

    with mp.workdps(120):
        zeta3_ref = mp.zeta(3)
        vquad_ref = load_vquad_reference(dps=120)
    zeta3_float = float(zeta3_ref)
    vquad_float = float(vquad_ref)

    scout_hits: list[dict[str, Any]] = []
    config_dict = asdict(config)

    with ProcessPoolExecutor(max_workers=config.workers) as pool:
        futures = [
            pool.submit(_worker_chunk, chunk, config_dict, zeta3_float, vquad_float)
            for chunk in chunked(specs, config.chunk_size)
        ]
        for future in as_completed(futures):
            scout_hits.extend(future.result())

    scout_hits.sort(key=lambda row: (-float(row["intersection_score"]), -float(row["best_zeta_digits"]), -float(row["best_vquad_digits"])))
    scout_hits = scout_hits[: config.top_k]

    validated = [validate_record(row, config, zeta3_ref, vquad_ref) for row in scout_hits]
    persist_results(config, scout_hits, validated)
    return scout_hits, validated, config


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SIARC v6.5 Deep Forge scan for non-linear intertwiners")
    parser.add_argument("--family", choices=["fixed_alpha", "shifted_alpha", "both"], default="both")
    parser.add_argument("--a1-center", type=int, default=-14, help="Center for the known stability lead A(m)=17-14m")
    parser.add_argument("--a1-radius", type=int, default=2)
    parser.add_argument("--b1-center", type=int, default=-4, help="Center for the known stability lead B(m)=5-4m")
    parser.add_argument("--b1-radius", type=int, default=2)
    parser.add_argument("--a2-min", type=int, default=-2)
    parser.add_argument("--a2-max", type=int, default=2)
    parser.add_argument("--b2-min", type=int, default=-2)
    parser.add_argument("--b2-max", type=int, default=2)
    parser.add_argument("--c-values", nargs="*", type=int, default=[1, 2, 4, 8, 16])
    parser.add_argument("--square-max", type=int, default=5, help="Also add k^2 for 1<=k<=square-max")
    parser.add_argument("--bridge-values", nargs="*", type=int, default=[-2, -1, 0, 1, 2], help="V_quad bridge perturbations")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--top-k", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.time()
    scout_hits, validated, config = run_scan(args)
    elapsed = time.time() - t0

    print("\nSIARC v6.5 Deep Forge summary")
    print("-----------------------------")
    print(f"Specs validated:      {len(validated)}")
    print(f"Workers:              {config.workers}")
    print(f"Numba enabled:        {'yes' if HAVE_NUMBA else 'no'}")
    print(f"SymPy enabled:        {'yes' if HAVE_SYMPY else 'no'}")
    print(f"Elapsed seconds:      {elapsed:.2f}")
    print(f"JSON artifact:        {JSON_PATH}")
    print(f"CSV artifact:         {CSV_PATH}")

    if validated:
        best = max(validated, key=lambda row: row.intersection_score)
        print("\nTop candidate")
        print(f"  family/spec:        {best.family} | a1={best.a1}, a2={best.a2}, b1={best.b1}, b2={best.b2}, C={best.c_scale}, bridge={best.bridge}")
        print(f"  intersection score: {best.intersection_score:.3f}")
        print(f"  zeta match:         {best.best_zeta_label} ({best.best_zeta_digits:.2f} digits)")
        print(f"  V_quad match:       {best.best_vquad_label} ({best.best_vquad_digits:.2f} digits)")
        print(f"  decay / evidence:   {best.stability_decay_rate:.3f} / {best.bayes_log10_evidence:.3f}")
        print(f"  near-miss shift:    {best.near_miss_shift}")
        if best.pslq_relation:
            print(f"  PSLQ:               {best.pslq_relation}")
        if best.riccati_relation:
            print(f"  Riccati/nullspace:  nullity={best.riccati_nullity}, residual={best.riccati_residual}")


if __name__ == "__main__":
    main()
