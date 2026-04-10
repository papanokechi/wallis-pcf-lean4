#!/usr/bin/env python3
"""
v6_5_structural_map.py
======================

Structural mapping layer for the SIARC v6.5 PCF landscape.

What it does
------------
1. Scans the quadratic-intertwiner neighborhood around the verified lead
      A(m) = 17 - 14 m,
      B(m) =  5 -  4 m,
   including C-relaxation and fractional-C probes.
2. Treats the v6.5 stability-decay rate as a spectral observable and extracts
   "stability islands" where decay is near zero but convergence is slower than
   the main Apéry channel.
3. Searches for a Möbius law
      P(m) = (a m + b) / (c m + d)
   governing the coefficient flow from the Apéry anchor toward the V_quad zone.
4. Produces a Leiden-style theoretical profile for candidates with strong
   Bayesian evidence ratio.
5. Writes JSON / CSV / Markdown summaries under `results/`.

Usage
-----
python v6_5_structural_map.py --workers 1 --radius 1 --top-k 12
python v6_5_structural_map.py --workers 4 --radius 2 --top-k 20
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Optional

import mpmath as mpm
from mpmath import mp

try:
    import sympy as sp
    HAVE_SYMPY = True
except ImportError:  # pragma: no cover
    sp = None
    HAVE_SYMPY = False


RESULT_DIR = Path("results")
JSON_PATH = RESULT_DIR / "v6_5_structural_map.json"
CSV_PATH = RESULT_DIR / "v6_5_structural_map.csv"
MD_PATH = RESULT_DIR / "v6_5_structural_map_summary.md"


@dataclass(frozen=True, slots=True)
class Spec:
    family: str
    a1: int
    a2: int
    b1: int
    b2: int
    c_value: str
    bridge: int


@dataclass(slots=True)
class Candidate:
    family: str
    a1: int
    a2: int
    b1: int
    b2: int
    c_value: str
    bridge: int
    best_zeta_label: str
    best_zeta_digits: float
    best_vquad_label: str
    best_vquad_digits: float
    best_pi_label: str
    best_pi_digits: float
    stability_low: float
    stability_high: float
    convergence_digits: float
    stability_decay_rate: float
    bayes_log10_evidence: float
    evidence_ratio: float
    intersection_score: float
    pincherle_ok: bool
    forward_backward_digits: float
    leiden_class: str
    theoretical_profile: str
    note: str


@dataclass(slots=True)
class MobiusRecord:
    a: int
    b: int
    c: int
    d: int
    map_formula: str
    zeta_digits_m0: float
    best_vquad_digits: float
    best_vquad_m: int
    stability_decay_rate: float
    score: float


def parse_c_value(text: str) -> mpm.mpf:
    if "/" in text:
        frac = Fraction(text)
        return mp.mpf(frac.numerator) / mp.mpf(frac.denominator)
    return mp.mpf(text)


def load_vquad_reference(dps: int = 120) -> mpm.mpf:
    ref_path = Path("V_quad_1000digits.txt")
    if ref_path.exists():
        for line in ref_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "V_quad" in line and "=" in line:
                raw = line.split("=", 1)[1].strip().rstrip(".")
                try:
                    with mp.workdps(dps):
                        return mp.mpf(raw)
                except Exception:
                    pass
    with mp.workdps(dps):
        tail = mp.zero
        for n in range(4000, 0, -1):
            tail = mp.one / (3 * n * n + n + 1 + tail)
        return 1 + tail


def A_of_m(spec: Spec, m: int) -> mpm.mpf:
    return mp.mpf(17 + spec.a1 * m + spec.a2 * m * m)


def B_of_m(spec: Spec, m: int) -> mpm.mpf:
    return mp.mpf(5 + spec.b1 * m + spec.b2 * m * m)


def alpha_value(spec: Spec, n: int, m: int) -> mpm.mpf:
    c_val = parse_c_value(spec.c_value)
    n_mp = mp.mpf(n)
    m_mp = mp.mpf(m)
    if spec.family == "fixed_alpha":
        return -c_val * (n_mp ** 6)
    return -c_val * (n_mp ** 4) * ((n_mp + m_mp) ** 2)


def beta_value(spec: Spec, n: int, m: int) -> mpm.mpf:
    n_mp = mp.mpf(n)
    A = A_of_m(spec, m)
    B = B_of_m(spec, m)
    apery_core = (2 * n_mp + 1) * (A * n_mp * n_mp + A * n_mp + B)
    vquad_core = mp.mpf(spec.bridge) * (3 * n_mp * n_mp + n_mp + 1)
    return apery_core + vquad_core


def eval_cf(spec: Spec, m: int, depth: int) -> mpm.mpf:
    tail = mp.zero
    for n in range(depth, 0, -1):
        a_n = alpha_value(spec, n, m)
        b_n = beta_value(spec, n, m)
        denom = b_n + tail
        if denom == 0:
            raise ZeroDivisionError(f"zero denominator for {spec} at n={n}, m={m}")
        tail = a_n / denom
    return beta_value(spec, 0, m) + tail


def eval_cf_mobius(m: int, depth: int, a: int, b: int, c: int, d: int, family: str = "fixed_alpha") -> mpm.mpf:
    denom = c * m + d
    if denom == 0:
        raise ZeroDivisionError("Möbius pole encountered")
    t = mp.mpf(a * m + b) / mp.mpf(denom)
    tail = mp.zero
    for n in range(depth, 0, -1):
        n_mp = mp.mpf(n)
        if family == "fixed_alpha":
            a_n = -(n_mp ** 6)
        else:
            a_n = -(n_mp ** 4) * ((n_mp + mp.mpf(m)) ** 2)
        A = 17 - 14 * t
        B = 5 - 4 * t
        b_n = (2 * n_mp + 1) * (A * n_mp * n_mp + A * n_mp + B)
        denom2 = b_n + tail
        if denom2 == 0:
            raise ZeroDivisionError("zero denominator in Möbius scan")
        tail = a_n / denom2
    b0 = (mp.mpf(1)) * B  # n=0 => (2*0+1)*(A*0+A*0+B) = B
    return b0 + tail


def forward_eval(spec: Spec, m: int, depth: int = 120) -> Optional[mpm.mpf]:
    try:
        p_prev, p_curr = mp.mpf(1), beta_value(spec, 0, m)
        q_prev, q_curr = mp.mpf(0), mp.mpf(1)
        for n in range(1, depth + 1):
            a_n = alpha_value(spec, n, m)
            b_n = beta_value(spec, n, m)
            p_new = b_n * p_curr + a_n * p_prev
            q_new = b_n * q_curr + a_n * q_prev
            p_prev, p_curr = p_curr, p_new
            q_prev, q_curr = q_curr, q_new
        if q_curr == 0:
            return None
        return p_curr / q_curr
    except Exception:
        return None


def safe_digits(err: float | mpm.mpf, floor: float = 1e-300) -> float:
    val = abs(float(err))
    if not math.isfinite(val):
        return 0.0
    return max(0.0, -math.log10(max(val, floor)))


def best_match(value: mpm.mpf, pool: dict[str, mpm.mpf], max_num: int = 8, max_den: int = 8) -> tuple[str, float]:
    best_label = "(none)"
    best_digits = 0.0
    for name, target in pool.items():
        for p in range(-max_num, max_num + 1):
            if p == 0:
                continue
            for q in range(1, max_den + 1):
                rat = mp.mpf(p) / q
                diff = abs(value - rat * target)
                digits = 999.0 if diff == 0 else float(-mp.log10(diff))
                if digits > best_digits:
                    frac = f"{p}/{q}" if q != 1 else str(p)
                    best_label = f"{frac}*{name}"
                    best_digits = digits
    if value != 0:
        inv = 1 / value
        for name, target in pool.items():
            diff = abs(inv - target)
            digits = 999.0 if diff == 0 else float(-mp.log10(diff))
            if digits > best_digits:
                best_label = f"1/value≈{name}"
                best_digits = digits
    return best_label, best_digits


def bayes_log10_evidence(stability_low: float, stability_high: float) -> float:
    eps = 1e-300
    raw_obs = math.log10((stability_high + eps) / (stability_low + eps))
    # Saturate the observable so "super-stable" candidates are treated as strong
    # evidence for the stable model instead of being over-penalized for lying far
    # into the left tail of both priors.
    obs = min(max(raw_obs, -2.0), 2.0)

    def logpdf(x: float, mu: float, sigma: float) -> float:
        z = (x - mu) / sigma
        return -0.5 * z * z - math.log(sigma * math.sqrt(2 * math.pi))

    log_stable = logpdf(obs, mu=-0.85, sigma=0.55)
    log_collapse = logpdf(obs, mu=0.55, sigma=0.45)
    return (log_stable - log_collapse) / math.log(10.0)


def evidence_ratio(log10_evidence: float) -> float:
    return 10.0 ** log10_evidence


def classify_candidate(
    spec: Spec,
    best_zeta_label: str,
    best_zeta_digits: float,
    best_vquad_label: str,
    best_vquad_digits: float,
    best_pi_label: str,
    best_pi_digits: float,
    log10_ev: float,
    conv_digits: float,
    pincherle_ok: bool,
) -> tuple[str, str]:
    if best_pi_digits > max(best_zeta_digits, best_vquad_digits) + 5:
        family_type = "Wallis-Type"
    elif best_zeta_digits >= 12 or best_vquad_digits >= 6:
        family_type = "Apery-Type"
    else:
        family_type = "Bridge-Type"

    if abs(log10_ev) < 0.05 and 4.0 <= conv_digits <= 18.0:
        leiden = "Leiden-S island"
    elif evidence_ratio(log10_ev) > 15 and family_type == "Apery-Type":
        leiden = "Leiden-A transcendental"
    elif family_type == "Wallis-Type":
        leiden = "Leiden-W rational"
    else:
        leiden = "Leiden-B bridge"

    pincherle_text = "Pincherle-compatible" if pincherle_ok else "Pincherle-fragile"
    profile = (
        f"{pincherle_text}; {family_type}; "
        f"zeta-fit={best_zeta_label} ({best_zeta_digits:.2f}d), "
        f"V_quad-fit={best_vquad_label} ({best_vquad_digits:.2f}d), "
        f"pi-fit={best_pi_label} ({best_pi_digits:.2f}d)"
    )
    return leiden, profile


def pincherle_check(spec: Spec, m: int = 0, depth: int = 120) -> tuple[bool, float]:
    try:
        with mp.workdps(120):
            back = eval_cf(spec, m, depth)
            forward = forward_eval(spec, m, depth)
        if forward is None:
            return False, 0.0
        diff = abs(back - forward)
        digits = 999.0 if diff == 0 else float(-mp.log10(diff))
        return digits >= 8.0, digits
    except Exception:
        return False, 0.0


def evaluate_spec(spec: Spec, zeta3: mpm.mpf, vquad: mpm.mpf, depths: tuple[int, int, int] = (30, 90, 150)) -> Optional[Candidate]:
    zeta_pool = {
        "zeta3": zeta3,
        "1/zeta3": 1 / zeta3,
        "pi^2/zeta3": (mp.pi ** 2) / zeta3,
        "pi^2": mp.pi ** 2,
        "1": mp.mpf(1),
    }
    vquad_pool = {
        "V_quad": vquad,
        "1/V_quad": 1 / vquad,
        "V_quad/zeta3": vquad / zeta3,
        "zeta3*V_quad": zeta3 * vquad,
        "1": mp.mpf(1),
    }
    pi_pool = {
        "pi": mp.pi,
        "1/pi": 1 / mp.pi,
        "pi^2": mp.pi ** 2,
        "4/pi": 4 / mp.pi,
        "1": mp.mpf(1),
    }

    best_z_label, best_v_label, best_pi_label = "(none)", "(none)", "(none)"
    best_z_digits = best_v_digits = best_pi_digits = 0.0
    low_errors = []
    high_errors = []

    try:
        with mp.workdps(60):
            for m in (0, 1, 2, 3):
                v30 = eval_cf(spec, m, depths[0])
                v90 = eval_cf(spec, m, depths[1])
                v150 = eval_cf(spec, m, depths[2])
                low_errors.append(abs(v90 - v30))
                high_errors.append(abs(v150 - v90))

                zlab, zdig = best_match(v150, zeta_pool)
                vlab, vdig = best_match(v150, vquad_pool)
                plab, pdig = best_match(v150, pi_pool)
                if zdig > best_z_digits:
                    best_z_label, best_z_digits = zlab, zdig
                if vdig > best_v_digits:
                    best_v_label, best_v_digits = vlab, vdig
                if pdig > best_pi_digits:
                    best_pi_label, best_pi_digits = plab, pdig
    except Exception:
        return None

    if not low_errors or not high_errors:
        return None

    low = max(low_errors)
    high = max(high_errors)
    conv_digits = safe_digits(high)
    log10_ev = bayes_log10_evidence(float(low), float(high))
    ratio = evidence_ratio(log10_ev)
    decay = math.log10((float(high) + 1e-300) / (float(low) + 1e-300))
    intersection = (
        0.60 * min(best_z_digits, max(best_v_digits, best_pi_digits))
        + 0.25 * max(best_z_digits, best_v_digits)
        + 0.15 * conv_digits
        + 0.50 * max(0.0, log10_ev)
    )

    ok, fb_digits = False, 0.0
    leiden, profile = classify_candidate(
        spec,
        best_z_label, best_z_digits,
        best_v_label, best_v_digits,
        best_pi_label, best_pi_digits,
        log10_ev, conv_digits, ok,
    )

    note = "fractional-C" if "/" in spec.c_value else "integer-C"
    return Candidate(
        family=spec.family,
        a1=spec.a1,
        a2=spec.a2,
        b1=spec.b1,
        b2=spec.b2,
        c_value=spec.c_value,
        bridge=spec.bridge,
        best_zeta_label=best_z_label,
        best_zeta_digits=round(best_z_digits, 3),
        best_vquad_label=best_v_label,
        best_vquad_digits=round(best_v_digits, 3),
        best_pi_label=best_pi_label,
        best_pi_digits=round(best_pi_digits, 3),
        stability_low=float(low),
        stability_high=float(high),
        convergence_digits=round(conv_digits, 3),
        stability_decay_rate=round(decay, 6),
        bayes_log10_evidence=round(log10_ev, 6),
        evidence_ratio=round(ratio, 6),
        intersection_score=round(intersection, 6),
        pincherle_ok=ok,
        forward_backward_digits=round(fb_digits, 3),
        leiden_class=leiden,
        theoretical_profile=profile,
        note=note,
    )


def mobius_search(zeta3: mpm.mpf, vquad: mpm.mpf, bound: int = 4) -> list[MobiusRecord]:
    rows: list[MobiusRecord] = []
    for a in range(-bound, bound + 1):
        for b in range(-bound, bound + 1):
            for c in range(-bound, bound + 1):
                for d in range(-bound, bound + 1):
                    if a == 0 and b == 0:
                        continue
                    if d == 0:
                        continue
                    det = a * d - b * c
                    if det == 0:
                        continue
                    if math.gcd(math.gcd(abs(a), abs(b)), math.gcd(abs(c), abs(d))) != 1:
                        continue
                    try:
                        with mp.workdps(80):
                            v0_30 = eval_cf_mobius(0, 30, a, b, c, d)
                            v0_90 = eval_cf_mobius(0, 90, a, b, c, d)
                            v0_150 = eval_cf_mobius(0, 150, a, b, c, d)
                            zlab, zdig = best_match(v0_150, {"zeta3": zeta3, "1/zeta3": 1 / zeta3, "1": mp.mpf(1)})
                            del zlab
                            low = abs(v0_90 - v0_30)
                            high = abs(v0_150 - v0_90)
                            best_v = 0.0
                            best_m = -1
                            for m in (1, 2, 3):
                                vm = eval_cf_mobius(m, 150, a, b, c, d)
                                _, vdig = best_match(vm, {"V_quad": vquad, "1/V_quad": 1 / vquad, "1": mp.mpf(1)})
                                if vdig > best_v:
                                    best_v = vdig
                                    best_m = m
                    except Exception:
                        continue
                    decay = math.log10((float(high) + 1e-300) / (float(low) + 1e-300))
                    score = min(zdig, 30.0) + 1.5 * best_v - abs(decay)
                    rows.append(MobiusRecord(
                        a=a,
                        b=b,
                        c=c,
                        d=d,
                        map_formula=f"({a}m{b:+d})/({c}m{d:+d})",
                        zeta_digits_m0=round(zdig, 3),
                        best_vquad_digits=round(best_v, 3),
                        best_vquad_m=best_m,
                        stability_decay_rate=round(decay, 6),
                        score=round(score, 6),
                    ))
    rows.sort(key=lambda row: (-row.score, -row.best_vquad_digits, -row.zeta_digits_m0))
    return rows[:10]


def build_specs(radius: int, a1_centers: list[int], b1_centers: list[int]) -> list[Spec]:
    c_values = ["1", "2", "4", "8", "16", "3/2", "4/3", "5/4"]
    specs: list[Spec] = []
    for family in ("fixed_alpha", "shifted_alpha"):
        for a1_center in a1_centers:
            for b1_center in b1_centers:
                for a1 in range(a1_center - radius, a1_center + radius + 1):
                    for a2 in range(-radius, radius + 1):
                        for b1 in range(b1_center - radius, b1_center + radius + 1):
                            for b2 in range(-radius, radius + 1):
                                for c_value in c_values:
                                    for bridge in (-2, -1, 0, 1, 2):
                                        specs.append(Spec(family, a1, a2, b1, b2, c_value, bridge))
    deduped = list(dict.fromkeys(specs))
    return deduped


def identify_stability_islands(candidates: list[Candidate]) -> list[Candidate]:
    islands = [
        c for c in candidates
        if abs(c.stability_decay_rate) <= 0.05 and 2.0 <= c.convergence_digits <= 18.0
    ]
    islands.sort(key=lambda row: (-row.evidence_ratio, -row.intersection_score, row.convergence_digits))
    return islands[:8]


def high_evidence_profiles(candidates: list[Candidate], threshold: float = 15.0) -> list[Candidate]:
    rows = [c for c in candidates if c.evidence_ratio > threshold]
    rows.sort(key=lambda row: (-row.evidence_ratio, -row.intersection_score))
    return rows


def next_target_recommendation(candidates: list[Candidate], islands: list[Candidate]) -> tuple[str, Optional[Candidate]]:
    pool = islands if islands else candidates
    if not pool:
        return "No viable spectral peaks found.", None

    ranked = sorted(
        pool,
        key=lambda c: (
            -c.evidence_ratio,
            -c.intersection_score,
            abs(c.stability_decay_rate),
            -c.best_vquad_digits,
            -c.best_zeta_digits,
        ),
    )
    best = ranked[0]
    message = (
        f"Next 1500dp target: {best.family} with (a1,a2,b1,b2,C,bridge)="
        f"({best.a1},{best.a2},{best.b1},{best.b2},{best.c_value},{best.bridge}); "
        f"Leiden={best.leiden_class}; evidence_ratio={best.evidence_ratio:.2f}; "
        f"decay={best.stability_decay_rate:.3f}."
    )
    return message, best


def write_outputs(candidates: list[Candidate], islands: list[Candidate], mobius_rows: list[MobiusRecord], recommendation: str) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp": time.time(),
        "candidates": [asdict(c) for c in candidates],
        "stability_islands": [asdict(c) for c in islands],
        "mobius_top": [asdict(m) for m in mobius_rows],
        "recommendation": recommendation,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        fields = list(asdict(candidates[0]).keys()) if candidates else [
            "family", "a1", "a2", "b1", "b2", "c_value", "bridge", "best_zeta_label",
            "best_zeta_digits", "best_vquad_label", "best_vquad_digits", "best_pi_label",
            "best_pi_digits", "stability_low", "stability_high", "convergence_digits",
            "stability_decay_rate", "bayes_log10_evidence", "evidence_ratio", "intersection_score",
            "pincherle_ok", "forward_backward_digits", "leiden_class", "theoretical_profile", "note",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in candidates:
            writer.writerow(asdict(row))

    lines = [
        "# v6.5 Structural Mapping Summary",
        "",
        "## Recommendation",
        "",
        f"- {recommendation}",
        "",
        "## Stability Islands",
        "",
    ]
    if islands:
        for c in islands[:5]:
            lines.append(
                f"- `{c.family}` `(a1,a2,b1,b2,C,bridge)=({c.a1},{c.a2},{c.b1},{c.b2},{c.c_value},{c.bridge})` "
                f"→ decay={c.stability_decay_rate:.3f}, evidence={c.evidence_ratio:.2f}, "
                f"type={c.leiden_class}, profile={c.theoretical_profile}"
            )
    else:
        lines.append("- No near-zero-decay islands were found in the scanned box.")

    lines.extend(["", "## Möbius Top Maps", ""])
    for row in mobius_rows[:5]:
        lines.append(
            f"- `{row.map_formula}` → zeta(m=0)={row.zeta_digits_m0:.2f} d, "
            f"best V_quad={row.best_vquad_digits:.2f} d at m={row.best_vquad_m}, score={row.score:.3f}"
        )

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Structural mapping for the SIARC v6.5 PCF landscape")
    parser.add_argument("--radius", type=int, default=1, help="search radius around each supplied linear lead")
    parser.add_argument("--a1-centers", nargs="*", type=int, default=[-15, -14, -13], help="a1 slices to probe")
    parser.add_argument("--b1-centers", nargs="*", type=int, default=[-5, -4, -3], help="b1 slices to probe")
    parser.add_argument("--top-k", type=int, default=12, help="number of top candidates to keep")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1), help="accepted for compatibility; scan is sequential")
    args = parser.parse_args()

    del args.workers  # compatibility only; this stage is intentionally deterministic

    with mp.workdps(120):
        zeta3 = mp.zeta(3)
        vquad = load_vquad_reference(120)

    specs = build_specs(args.radius, args.a1_centers, args.b1_centers)
    candidates: list[Candidate] = []
    for spec in specs:
        cand = evaluate_spec(spec, zeta3, vquad)
        if cand is None:
            continue
        candidates.append(cand)

    candidates.sort(key=lambda row: (-row.intersection_score, -row.evidence_ratio, -row.best_vquad_digits, -row.best_zeta_digits))
    candidates = candidates[: args.top_k]

    for cand in candidates:
        spec = Spec(cand.family, cand.a1, cand.a2, cand.b1, cand.b2, cand.c_value, cand.bridge)
        ok, fb_digits = pincherle_check(spec, m=0)
        cand.pincherle_ok = ok
        cand.forward_backward_digits = round(fb_digits, 3)
        cand.leiden_class, cand.theoretical_profile = classify_candidate(
            spec,
            cand.best_zeta_label,
            cand.best_zeta_digits,
            cand.best_vquad_label,
            cand.best_vquad_digits,
            cand.best_pi_label,
            cand.best_pi_digits,
            cand.bayes_log10_evidence,
            cand.convergence_digits,
            ok,
        )

    islands = identify_stability_islands(candidates)
    mobius_rows = mobius_search(zeta3, vquad, bound=2)
    recommendation, best = next_target_recommendation(candidates, islands)
    del best
    write_outputs(candidates, islands, mobius_rows, recommendation)

    high_ev = high_evidence_profiles(candidates)

    print("\nPhase-transition structural map")
    print("-------------------------------")
    print(f"Candidates retained:     {len(candidates)}")
    print(f"Stability islands:      {len(islands)}")
    print(f"High-evidence (>15):    {len(high_ev)}")
    print(f"JSON:                   {JSON_PATH}")
    print(f"CSV:                    {CSV_PATH}")
    print(f"Summary MD:             {MD_PATH}")
    print(f"Recommendation:         {recommendation}")

    if candidates:
        print("\nTop spectral peaks:")
        for i, c in enumerate(candidates[:5], 1):
            print(
                f"  {i}. {c.family:12s} a1={c.a1:>3d} a2={c.a2:>2d} b1={c.b1:>3d} b2={c.b2:>2d} "
                f"C={c.c_value:>3s} br={c.bridge:+d}  score={c.intersection_score:7.3f} "
                f"ev={c.evidence_ratio:6.2f} decay={c.stability_decay_rate:7.3f}  {c.leiden_class}"
            )

    if mobius_rows:
        best_map = mobius_rows[0]
        print(
            f"\nBest Möbius map: {best_map.map_formula}  | "
            f"zeta(m=0)={best_map.zeta_digits_m0:.2f}d, "
            f"V_quad peak={best_map.best_vquad_digits:.2f}d at m={best_map.best_vquad_m}"
        )


if __name__ == "__main__":
    main()
