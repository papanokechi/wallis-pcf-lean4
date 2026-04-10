#!/usr/bin/env python3
"""
_third_order_wallis_scan.py
===========================

Third-order Wallis-style recurrence scan for dimension-3 linear recurrences

    y_n + b_n y_{n-1} + a_n y_{n-2} + d_n y_{n-3} = 0.

This script scans the integer box (alpha, beta, gamma, delta) in [-R, R]^4 for
natural 4-parameter Wallis analogues and applies a multivariate Wallis check:

1. Build the 3 fundamental solutions from basis seeds at n=0,1,2.
2. Isolate the two subdominant modes by a tail Gram/SVD analysis.
3. Form the ratio f1_n / f2_n of the two least-growing modes.
4. Measure stabilization and compare it to a dominant-involving ratio to detect
   accelerated convergence.
5. Match against targets built from zeta(3), Catalan's constant, and selected
   elliptic period ratios.

Two natural families are scanned:

  falling:
      b_n = alpha*n + beta
      a_n = gamma*n*(n-1)
      d_n = delta*n*(n-1)*(n-2)

  power:
      b_n = alpha*n + beta
      a_n = gamma*n^2
      d_n = delta*n^3

Usage examples:
    python _third_order_wallis_scan.py --workers 8 --range 10
    python _third_order_wallis_scan.py --workers 8 --range 10 --families falling
    python _third_order_wallis_scan.py --workers 4 --range 3 --depth 90 --verify-top 10
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import islice
from pathlib import Path
from typing import Iterable, Sequence

import mpmath as mp
import numpy as np

try:
    from numba import njit
    HAS_NUMBA = True
except Exception:
    HAS_NUMBA = False

    def njit(*args, **kwargs):
        def _decorator(func):
            return func
        return _decorator


RESULTS_PATH = Path("results") / "third_order_wallis_scan.json"


class ThermalGuard:
    """Lightweight CPU/RAM guard mirroring the workspace parallel engine."""

    def __init__(self, cpu_threshold: float = 95.0, ram_threshold: float = 90.0,
                 throttle_seconds: float = 2.0):
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold
        self.throttle_seconds = throttle_seconds
        self._has_psutil = False
        self._psutil = None
        try:
            import psutil  # type: ignore
            self._psutil = psutil
            self._has_psutil = True
        except Exception:
            pass

    def check_and_throttle(self) -> dict:
        status = {
            "available": self._has_psutil,
            "cpu_percent": None,
            "ram_percent": None,
            "throttled": False,
        }
        if not self._has_psutil:
            return status
        try:
            cpu = float(self._psutil.cpu_percent(interval=0.1))
            ram = float(self._psutil.virtual_memory().percent)
            status["cpu_percent"] = round(cpu, 1)
            status["ram_percent"] = round(ram, 1)
            if cpu > self.cpu_threshold or ram > self.ram_threshold:
                status["throttled"] = True
                time.sleep(self.throttle_seconds)
        except Exception:
            pass
        return status


@dataclass
class Candidate:
    family: str
    alpha: int
    beta: int
    gamma: int
    delta: int
    ratio_estimate: float
    best_match: str
    match_digits: float
    stability_digits: float
    dominant_digits: float
    acceleration_gain: float
    score: float
    verify_depths: list[int] | None = None
    verified_digits: float | None = None
    verified_match: str | None = None
    ratio_depth_values: list[str] | None = None


def _safe_digits(err: float, floor: float = 1e-30) -> float:
    err = abs(float(err))
    if not math.isfinite(err):
        return 0.0
    return max(0.0, -math.log10(max(err, floor)))


def _family_coeffs(n: int, alpha: int, beta: int, gamma: int, delta: int,
                   family: str) -> tuple[float, float, float]:
    nf = float(n)
    if family == "falling":
        b_n = alpha * nf + beta
        a_n = gamma * nf * (nf - 1.0)
        d_n = delta * nf * (nf - 1.0) * (nf - 2.0)
    elif family == "power":
        b_n = alpha * nf + beta
        a_n = gamma * (nf ** 2)
        d_n = delta * (nf ** 3)
    else:
        raise ValueError(f"Unknown family: {family}")
    return b_n, a_n, d_n


@njit(cache=True)
def _build_basis_kernel(alpha: int, beta: int, gamma: int, delta: int,
                        family_code: int, depth: int):
    basis = np.zeros((3, depth + 1), dtype=np.float64)
    basis[0, 0] = 1.0
    basis[1, 1] = 1.0
    basis[2, 2] = 1.0

    for n in range(3, depth + 1):
        nf = float(n)
        b_n = alpha * nf + beta
        if family_code == 0:
            a_n = gamma * nf * (nf - 1.0)
            d_n = delta * nf * (nf - 1.0) * (nf - 2.0)
        else:
            a_n = gamma * (nf * nf)
            d_n = delta * (nf * nf * nf)

        for row in range(3):
            basis[row, n] = -(
                b_n * basis[row, n - 1]
                + a_n * basis[row, n - 2]
                + d_n * basis[row, n - 3]
            )

        mx = abs(basis[0, n])
        cand = abs(basis[1, n])
        if cand > mx:
            mx = cand
        cand = abs(basis[2, n])
        if cand > mx:
            mx = cand

        if not np.isfinite(mx):
            return basis, False
        if mx > 1e120:
            basis /= mx

    return basis, True


def _build_basis(alpha: int, beta: int, gamma: int, delta: int,
                 family: str, depth: int) -> np.ndarray | None:
    """Build the three fundamental real solutions in float64."""
    if HAS_NUMBA:
        if family == "falling":
            family_code = 0
        elif family == "power":
            family_code = 1
        else:
            raise ValueError(f"Unknown family: {family}")
        basis, ok = _build_basis_kernel(alpha, beta, gamma, delta, family_code, depth)
        if not ok:
            return None
        return basis

    basis = np.zeros((3, depth + 1), dtype=np.float64)
    basis[0, 0] = 1.0
    basis[1, 1] = 1.0
    basis[2, 2] = 1.0

    for n in range(3, depth + 1):
        b_n, a_n, d_n = _family_coeffs(n, alpha, beta, gamma, delta, family)
        basis[:, n] = -(b_n * basis[:, n - 1] + a_n * basis[:, n - 2] + d_n * basis[:, n - 3])

        mx = float(np.max(np.abs(basis[:, n])))
        if not math.isfinite(mx):
            return None
        if mx > 1e120:
            basis /= mx

    if not np.all(np.isfinite(basis)):
        return None
    return basis


def _extract_ratio_metrics(basis: np.ndarray, depth: int, tail_window: int) -> tuple[float, float, float] | None:
    """Return (ratio_estimate, stability_digits, dominant_digits).

    The multivariate Wallis-check uses the tail Gram matrix of the three basis
    solutions to isolate the two least-growing directions.
    """
    rows = []
    for n in range(depth - tail_window + 1, depth + 1):
        col = basis[:, n]
        scale = float(np.max(np.abs(col)))
        if (not math.isfinite(scale)) or scale < 1e-30:
            return None
        rows.append(col / scale)
    T = np.array(rows, dtype=np.float64)

    try:
        gram = T.T @ T
        evals, evecs = np.linalg.eigh(gram)
    except np.linalg.LinAlgError:
        return None

    order = np.argsort(evals)
    c_min = evecs[:, order[0]]
    c_sub = evecs[:, order[1]]
    c_dom = evecs[:, order[2]]

    f_min = c_min @ basis
    f_sub = c_sub @ basis
    f_dom = c_dom @ basis

    rs: list[float] = []
    ds: list[float] = []
    start = max(8, depth - 12)
    for n in range(start, depth + 1):
        if abs(f_sub[n]) > 1e-14:
            r = float(f_min[n] / f_sub[n])
            if math.isfinite(r):
                rs.append(r)
        if abs(f_dom[n]) > 1e-14:
            d = float(f_sub[n] / f_dom[n])
            if math.isfinite(d):
                ds.append(d)

    if len(rs) < 6 or len(ds) < 6:
        return None

    ratio = rs[-1]
    stability = max(abs(ratio - rs[-3]), abs(ratio - rs[-6]), abs(ratio - rs[0]))
    dom_ratio = ds[-1]
    dom_stability = max(abs(dom_ratio - ds[-3]), abs(dom_ratio - ds[-6]), abs(dom_ratio - ds[0]))

    return ratio, _safe_digits(stability), _safe_digits(dom_stability)


def _make_target_grid(dps: int = 80, max_num: int = 12, max_den: int = 12) -> list[tuple[str, float]]:
    mp.mp.dps = dps

    targets = {
        "zeta(3)": mp.zeta(3),
        "G": mp.catalan,
        "K(1/2)/pi": mp.ellipk(mp.mpf(1) / 2) / mp.pi,
        "E(1/2)/pi": mp.ellipe(mp.mpf(1) / 2) / mp.pi,
        "K(1/11)/pi": mp.ellipk(mp.mpf(1) / 11) / mp.pi,
        "K((3-sqrt(5))/8)/pi": mp.ellipk((3 - mp.sqrt(5)) / 8) / mp.pi,
        "K(sin(pi/11)^2)/pi": mp.ellipk(mp.sin(mp.pi / 11) ** 2) / mp.pi,
        "K(1/11)/K(10/11)": mp.ellipk(mp.mpf(1) / 11) / mp.ellipk(mp.mpf(10) / 11),
    }

    grid: list[tuple[str, float]] = []
    seen = set()
    for name, val in targets.items():
        for p in range(-max_num, max_num + 1):
            if p == 0:
                continue
            for q in range(1, max_den + 1):
                frac = Fraction(p, q)
                label = name if frac == 1 else f"({frac.numerator}/{frac.denominator})*{name}"
                key = (label, round(float(frac * val), 18))
                if key in seen:
                    continue
                seen.add(key)
                grid.append((label, float(frac * val)))
    return grid


def _match_ratio(ratio: float, target_grid: Sequence[tuple[str, float]]) -> tuple[str, float]:
    best_name = "(no target match)"
    best_digits = 0.0
    for label, target in target_grid:
        diff = abs(ratio - target)
        digits = _safe_digits(diff)
        if digits > best_digits:
            best_name = label
            best_digits = digits
    return best_name, best_digits


def _score_candidate(stability_digits: float, match_digits: float, dominant_digits: float) -> float:
    acceleration_gain = max(0.0, stability_digits - dominant_digits)
    effective = min(stability_digits, match_digits)
    return 2.0 * effective + 0.25 * acceleration_gain


def _evaluate_tuple(params: tuple[int, int, int, int], family: str, depth: int,
                    tail_window: int, target_grid: Sequence[tuple[str, float]],
                    min_stability: float, min_match: float) -> Candidate | None:
    alpha, beta, gamma, delta = params
    if delta == 0:
        return None

    basis = _build_basis(alpha, beta, gamma, delta, family, depth)
    if basis is None:
        return None

    metrics = _extract_ratio_metrics(basis, depth, tail_window)
    if metrics is None:
        return None
    ratio, stability_digits, dominant_digits = metrics

    if (not math.isfinite(ratio)) or abs(ratio) > 1e6 or abs(ratio) < 1e-10:
        return None

    best_match, match_digits = _match_ratio(ratio, target_grid)
    acceleration_gain = stability_digits - dominant_digits
    score = _score_candidate(stability_digits, match_digits, dominant_digits)

    if stability_digits < min_stability or match_digits < min_match:
        return None

    return Candidate(
        family=family,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        delta=delta,
        ratio_estimate=ratio,
        best_match=best_match,
        match_digits=match_digits,
        stability_digits=stability_digits,
        dominant_digits=dominant_digits,
        acceleration_gain=acceleration_gain,
        score=score,
    )


def _scan_chunk(chunk: Sequence[tuple[int, int, int, int]], family: str, depth: int,
                tail_window: int, target_grid: Sequence[tuple[str, float]],
                min_stability: float, min_match: float, keep_per_chunk: int) -> list[dict]:
    found: list[Candidate] = []
    for params in chunk:
        rec = _evaluate_tuple(params, family, depth, tail_window, target_grid,
                              min_stability, min_match)
        if rec is not None:
            found.append(rec)
    found.sort(key=lambda c: c.score, reverse=True)
    return [asdict(c) for c in found[:keep_per_chunk]]


def _chunked_product(values: Sequence[int], chunk_size: int) -> Iterable[list[tuple[int, int, int, int]]]:
    prod = itertools.product(values, repeat=4)
    while True:
        chunk = list(islice(prod, chunk_size))
        if not chunk:
            break
        yield chunk


def _candidate_key(item: Candidate) -> tuple:
    return (item.family, item.alpha, item.beta, item.gamma, item.delta)


def _verify_candidate(item: Candidate, verify_depths: Sequence[int], tail_window: int,
                      target_grid: Sequence[tuple[str, float]], dps: int = 100) -> Candidate:
    """Higher-precision verification for a top candidate."""
    mp.mp.dps = dps
    ratios = []
    matches = []
    stabilities = []

    for depth in verify_depths:
        basis = _build_basis(item.alpha, item.beta, item.gamma, item.delta, item.family, depth)
        if basis is None:
            continue
        metrics = _extract_ratio_metrics(basis, depth, min(tail_window, max(8, depth // 4)))
        if metrics is None:
            continue
        ratio, stability_digits, dominant_digits = metrics
        label, match_digits = _match_ratio(ratio, target_grid)
        ratios.append(ratio)
        stabilities.append((stability_digits, dominant_digits))
        matches.append((label, match_digits))

    if ratios:
        cross_depth_digits = 99.0
        if len(ratios) >= 2:
            diffs = [abs(ratios[i] - ratios[i - 1]) for i in range(1, len(ratios))]
            cross_depth_digits = min(_safe_digits(d) for d in diffs)
        best_idx = max(range(len(matches)), key=lambda i: matches[i][1])
        item.verify_depths = list(verify_depths)
        item.verified_match = matches[best_idx][0]
        item.ratio_depth_values = [f"{r:.16g}" for r in ratios]
        item.verified_digits = min(matches[best_idx][1], cross_depth_digits)

    return item


def run_scan(args: argparse.Namespace) -> dict:
    values = list(range(-args.range, args.range + 1))
    total_tuples = len(values) ** 4
    families = [f.strip() for f in args.families.split(",") if f.strip()]
    target_grid = _make_target_grid(dps=90)
    guard = ThermalGuard()

    print("=" * 78, flush=True)
    print("THIRD-ORDER WALLIS SCAN", flush=True)
    print("=" * 78, flush=True)
    print(f"Families: {families}", flush=True)
    print(f"Coefficient box: [-{args.range}, {args.range}]^4 = {total_tuples} tuples/family", flush=True)
    print(f"Workers: {args.workers}  |  Depth: {args.depth}  |  Tail window: {args.tail_window}", flush=True)
    print(f"Acceleration: {'Numba @njit' if HAS_NUMBA else 'NumPy fallback'}", flush=True)
    print(f"Target grid size: {len(target_grid)} rational multiples", flush=True)
    print(flush=True)

    all_found: dict[tuple, Candidate] = {}
    family_reports = []

    for family in families:
        t0 = time.time()
        chunks = list(_chunked_product(values, args.chunk_size))
        print(f"[scan] family={family}  chunks={len(chunks)}", flush=True)

        submitted = 0
        completed = 0
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futures = [
                ex.submit(
                    _scan_chunk,
                    chunk,
                    family,
                    args.depth,
                    args.tail_window,
                    target_grid,
                    args.min_stability,
                    args.min_match,
                    args.keep_per_chunk,
                )
                for chunk in chunks
            ]
            submitted = len(futures)

            for fut in as_completed(futures):
                completed += 1
                if completed % max(1, args.guard_every) == 0:
                    status = guard.check_and_throttle()
                    if status.get("available"):
                        print(
                            f"  progress {completed}/{submitted} | CPU={status['cpu_percent']}% RAM={status['ram_percent']}%",
                            flush=True,
                        )
                for raw in fut.result():
                    cand = Candidate(**raw)
                    key = _candidate_key(cand)
                    prev = all_found.get(key)
                    if prev is None or cand.score > prev.score:
                        all_found[key] = cand

        elapsed = time.time() - t0
        fam_cands = [c for c in all_found.values() if c.family == family]
        fam_cands.sort(key=lambda c: c.score, reverse=True)
        top = fam_cands[: args.top_k]
        family_reports.append({
            "family": family,
            "elapsed_seconds": elapsed,
            "candidate_count": len(fam_cands),
            "top_candidates": [asdict(c) for c in top],
        })
        print(f"[done] family={family}  elapsed={elapsed:.1f}s  candidates={len(fam_cands)}", flush=True)
        if top:
            best = top[0]
            print(
                f"       best=({best.alpha},{best.beta},{best.gamma},{best.delta})  "
                f"match={best.best_match}  score={best.score:.2f}  "
                f"stab={best.stability_digits:.2f}  digits={best.match_digits:.2f}",
                flush=True,
            )
        print(flush=True)

    ranked = sorted(all_found.values(), key=lambda c: c.score, reverse=True)
    verify_list = ranked[: args.verify_top]
    verified = [
        _verify_candidate(c, args.verify_depths, args.tail_window, target_grid, dps=args.verify_dps)
        for c in verify_list
    ]
    verified.sort(key=lambda c: (c.verified_digits or 0.0, c.score), reverse=True)

    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "protocol": {
            "families": families,
            "coefficient_box": [-args.range, args.range],
            "depth": args.depth,
            "tail_window": args.tail_window,
            "workers": args.workers,
            "acceleration": "numba-njit" if HAS_NUMBA else "numpy-fallback",
            "multivariate_wallis_check": (
                "Tail Gram/SVD isolation of the two least-growing modes; "
                "ratio f1_n/f2_n checked for stabilization and acceleration."
            ),
        },
        "family_reports": family_reports,
        "verified_top_candidates": [asdict(c) for c in verified],
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("=" * 78, flush=True)
    print("VERIFIED TOP CANDIDATES", flush=True)
    print("=" * 78, flush=True)
    if not verified:
        print("No candidates survived the stability/match thresholds.", flush=True)
    else:
        for i, c in enumerate(verified[:10], 1):
            vdig = 0.0 if c.verified_digits is None else c.verified_digits
            print(
                f"[{i}] {c.family:7s} ({c.alpha:>3d},{c.beta:>3d},{c.gamma:>3d},{c.delta:>3d})  "
                f"{c.verified_match or c.best_match}  "
                f"verified≈{vdig:.2f}d  raw={c.ratio_estimate:.12g}",
                flush=True,
            )

    print(f"\nSaved JSON report to: {RESULTS_PATH}", flush=True)
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Third-order Wallis-style recurrence scan.")
    p.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 8))
    p.add_argument("--range", type=int, default=10, help="Scan integer box [-range, range].")
    p.add_argument("--depth", type=int, default=110)
    p.add_argument("--tail-window", type=int, default=18)
    p.add_argument("--families", type=str, default="falling,power")
    p.add_argument("--chunk-size", type=int, default=1200)
    p.add_argument("--keep-per-chunk", type=int, default=8)
    p.add_argument("--top-k", type=int, default=25)
    p.add_argument("--verify-top", type=int, default=20)
    p.add_argument("--verify-dps", type=int, default=100)
    p.add_argument("--verify-depths", type=int, nargs="+", default=[110, 140, 180])
    p.add_argument("--min-stability", type=float, default=1.75)
    p.add_argument("--min-match", type=float, default=3.0)
    p.add_argument("--guard-every", type=int, default=12)
    return p.parse_args()


if __name__ == "__main__":
    import multiprocessing as _mp
    _mp.freeze_support()
    args = parse_args()
    run_scan(args)
