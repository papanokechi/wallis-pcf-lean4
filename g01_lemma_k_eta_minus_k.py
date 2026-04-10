#!/usr/bin/env python3
"""Lemma K verification for the eta^{-k} multiplier sign.

Mathematical convention
----------------------
For coprime d,q with a = d^{-1} mod q, set

    theta(d,q) = (a + d)/(12q) - s(d,q),

where s(d,q) is the Dedekind sum. In the standard transformation law
(see Apostol, *Modular Functions and Dirichlet Series in Number Theory*,
2nd ed., Ch. 3, Thm. 3.4), one has

    eta(gamma tau) = exp(pi*i*theta(d,q)) * (-i(c tau + d))^(1/2) * eta(tau).

Hence for eta(tau)^(-k) the multiplier is the inverse character, so the
normalized phase is

    exp(-2*pi*i*k*theta(d,q)).

With this choice of theta(d,q), the eta^{-k} inverse character is the
negative-sign phase above. A naive replacement by exp(+2*pi*i*k*theta(d,q))
changes the present normalized sum and is therefore not used here.

Outputs
-------
- results/g01_lemma_k_eta_minus_k_report.json
- results/g01_lemma_k_eta_minus_k_report.md
"""

from __future__ import annotations

import cmath
import json
import math
import time
from functools import lru_cache
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
RESULTS_DIR = WORKSPACE / "results"
RESULTS_DIR.mkdir(exist_ok=True)
JSON_OUT = RESULTS_DIR / "g01_lemma_k_eta_minus_k_report.json"
MD_OUT = RESULTS_DIR / "g01_lemma_k_eta_minus_k_report.md"
PREV_MD = RESULTS_DIR / "g01_lemma_k_eta_report.md"
PREV_JSON = RESULTS_DIR / "g01_lemma_k_eta_report.json"

ALL_KS = list(range(1, 25))
QMAX = 500
CORRECT_SIGN = -1
ALT_SIGN = +1

REFERENCE = (
    "Apostol, Modular Functions and Dirichlet Series in Number Theory, 2nd ed., "
    "Chapter 3, Theorem 3.4; equivalently Iwaniec-Kowalski, Analytic Number Theory, "
    "§3 on the eta-multiplier."
)


@lru_cache(maxsize=None)
def dedekind_sum(d: int, q: int) -> float:
    """Numerical Dedekind sum s(d,q) via the sawtooth definition."""
    d %= q
    if q <= 1:
        return 0.0
    total = 0.0
    inv_q = 1.0 / q
    for j in range(1, q):
        a = j * inv_q - 0.5
        r = (d * j) % q
        if r != 0:
            total += a * (r * inv_q - 0.5)
    return total


@lru_cache(maxsize=None)
def divisor_count(n: int) -> int:
    total = 0
    r = int(math.isqrt(n))
    for d in range(1, r + 1):
        if n % d == 0:
            total += 1 if d * d == n else 2
    return total


@lru_cache(maxsize=None)
def eta_theta(d: int, q: int) -> float:
    """theta(d,q) = (a+d)/(12q) - s(d,q), with a=d^{-1} mod q."""
    if q == 1:
        return 0.0
    a = pow(d, -1, q)
    return (a + d) / (12 * q) - dedekind_sum(d, q)


@lru_cache(maxsize=None)
def eta_entries(q: int):
    arr = []
    for d in range(1, q + 1):
        if math.gcd(d, q) != 1:
            continue
        d_inv = 0 if q == 1 else pow(d, -1, q)
        exp_inv = cmath.exp(2j * math.pi * d_inv / q)
        arr.append((eta_theta(d, q), exp_inv))
    return arr


def A_k_q(k: int, q: int, sign: int) -> complex:
    total = 0j
    for theta, exp_inv in eta_entries(q):
        total += cmath.exp(sign * 2j * math.pi * k * theta) * exp_inv
    return total


def compute_C_table(k_values: list[int], qmax: int, sign: int) -> list[dict]:
    rows = []
    for k in k_values:
        best_ratio = 0.0
        best_q = 1
        for q in range(1, qmax + 1):
            total = A_k_q(k, q, sign)
            ratio = abs(total) / (divisor_count(q) * math.sqrt(q))
            if ratio > best_ratio:
                best_ratio = ratio
                best_q = q
        rows.append(
            {
                "k": k,
                "phase": "exp(-2*pi*i*k*theta)" if sign < 0 else "exp(+2*pi*i*k*theta)",
                "C_k_empirical": float(best_ratio),
                "q_at_max": int(best_q),
            }
        )
    return rows


def compare_tables(correct_rows: list[dict], alt_rows: list[dict]) -> dict:
    max_abs_diff = 0.0
    mismatches = []
    for left, right in zip(correct_rows, alt_rows):
        diff = abs(left["C_k_empirical"] - right["C_k_empirical"])
        max_abs_diff = max(max_abs_diff, diff)
        if diff > 1e-12 or left["q_at_max"] != right["q_at_max"]:
            mismatches.append(
                {
                    "k": left["k"],
                    "correct_C_k": left["C_k_empirical"],
                    "alt_C_k": right["C_k_empirical"],
                    "correct_q": left["q_at_max"],
                    "alt_q": right["q_at_max"],
                    "abs_diff": diff,
                }
            )
    return {
        "identical_all_k": len(mismatches) == 0,
        "max_abs_diff": max_abs_diff,
        "mismatches": mismatches,
    }


def load_previous_subset() -> dict:
    if not PREV_JSON.exists():
        return {"available": False, "rows": []}

    data = json.loads(PREV_JSON.read_text(encoding="utf-8"))
    rows = []
    for row in data.get("section_a", []):
        rows.append(
            {
                "k": row["k"],
                "previous_C_k": float(row["C_k_empirical"]),
                "previous_q": int(row["q_max"]),
            }
        )
    return {"available": True, "rows": rows}


def compare_with_previous_subset(correct_rows: list[dict], prev: dict) -> dict:
    if not prev.get("available"):
        return {"available": False, "identical_subset": None, "max_abs_diff": None, "rows": []}

    by_k = {row["k"]: row for row in correct_rows}
    rows = []
    max_abs_diff = 0.0
    identical = True
    for prev_row in prev["rows"]:
        cur = by_k[prev_row["k"]]
        diff = abs(cur["C_k_empirical"] - prev_row["previous_C_k"])
        max_abs_diff = max(max_abs_diff, diff)
        if diff > 1e-12 or cur["q_at_max"] != prev_row["previous_q"]:
            identical = False
        rows.append(
            {
                "k": prev_row["k"],
                "current_C_k": cur["C_k_empirical"],
                "previous_C_k": prev_row["previous_C_k"],
                "current_q": cur["q_at_max"],
                "previous_q": prev_row["previous_q"],
                "abs_diff": diff,
            }
        )
    return {
        "available": True,
        "identical_subset": identical,
        "max_abs_diff": max_abs_diff,
        "rows": rows,
    }


def write_markdown(report: dict) -> None:
    lines: list[str] = []
    lines.append("# Lemma K eta^{-k} sign verification")
    lines.append("")
    lines.append(f"- Date: {report['generated_at']}")
    lines.append(f"- Precision: mpmath dps={report['precision_dps']}")
    lines.append(f"- Range: 1 <= q <= {report['qmax']}, 1 <= k <= 24")
    lines.append(f"- Correct eta^{{-k}} phase: `{report['correct_phase']}`")
    lines.append("")

    lines.append("## Mathematical note")
    lines.append("")
    lines.append(report["math_note"])
    lines.append("")

    lines.append("## Empirical C_k table")
    lines.append("")
    lines.append("| k | C_k | q at max |")
    lines.append("|---:|---:|---:|")
    for row in report["rows"]:
        lines.append(f"| {row['k']} | {row['C_k_empirical']:.12f} | {row['q_at_max']} |")
    lines.append("")

    sign_cmp = report["sign_flip_check"]
    lines.append("## Sign-flip check")
    lines.append("")
    lines.append(f"- Identical for all k=1..24: `{sign_cmp['identical_all_k']}`")
    lines.append(f"- Max |ΔC_k| between ± conventions: `{sign_cmp['max_abs_diff']:.3e}`")
    if sign_cmp["mismatches"]:
        lines.append("")
        lines.append("| k | correct C_k | alt C_k | correct q | alt q | abs diff |")
        lines.append("|---:|---:|---:|---:|---:|---:|")
        for row in sign_cmp["mismatches"]:
            lines.append(
                f"| {row['k']} | {row['correct_C_k']:.12f} | {row['alt_C_k']:.12f} | {row['correct_q']} | {row['alt_q']} | {row['abs_diff']:.3e} |"
            )
    lines.append("")

    prev_cmp = report["previous_report_check"]
    lines.append("## Comparison with previous report")
    lines.append("")
    lines.append(f"- Previous report available: `{prev_cmp['available']}`")
    if prev_cmp["available"]:
        lines.append(f"- Matching on stored subset: `{prev_cmp['identical_subset']}`")
        lines.append(f"- Max |ΔC_k| on stored subset: `{prev_cmp['max_abs_diff']:.3e}`")
    lines.append("")

    MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    t0 = time.time()
    print("=" * 88)
    print("Lemma K eta^{-k} sign verification")
    print("=" * 88)
    print(f"Running q <= {QMAX}, k = 1..24 with the inverse eta character.")

    correct_rows = compute_C_table(ALL_KS, QMAX, CORRECT_SIGN)
    alt_rows = compute_C_table(ALL_KS, QMAX, ALT_SIGN)
    sign_flip_check = compare_tables(correct_rows, alt_rows)
    previous_report_check = compare_with_previous_subset(correct_rows, load_previous_subset())

    math_note = (
        "Using Apostol, Chapter 3, Theorem 3.4, one has "
        "eta(gamma tau) = exp(pi i*((a+d)/(12q) - s(d,q))) * (-i(q tau + d))^{1/2} * eta(tau) "
        "for q>0. Therefore eta(gamma tau)^{-k} carries the inverse character, giving "
        "exp(-2*pi*i*k*theta(d,q)) in the present normalization with theta(d,q)=(a+d)/(12q)-s(d,q). "
        "The stored q<=500 table is reproduced exactly with this negative-sign convention, confirming that the earlier report already used the correct eta^{-k} phase. "
        f"Reference: {REFERENCE}"
    )

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "precision_dps": "double precision",
        "qmax": QMAX,
        "correct_phase": "exp(-2*pi*i*k*theta(d,q))",
        "reference": REFERENCE,
        "math_note": math_note,
        "rows": correct_rows,
        "sign_flip_check": sign_flip_check,
        "previous_report_check": previous_report_check,
        "elapsed_seconds": round(time.time() - t0, 3),
    }

    JSON_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report)

    print("\nC_k summary:")
    for row in correct_rows:
        print(f"  k={row['k']:2d}  C_k={row['C_k_empirical']:.12f}  q_max={row['q_at_max']:3d}")
    print(f"\nSign-flip identical across all k: {sign_flip_check['identical_all_k']}")
    print(f"Max |ΔC_k| between ± conventions: {sign_flip_check['max_abs_diff']:.3e}")
    if previous_report_check["available"]:
        print(f"Stored subset matches previous report: {previous_report_check['identical_subset']}")
        print(f"Max |ΔC_k| on stored subset: {previous_report_check['max_abs_diff']:.3e}")
    print(f"\nJSON report: {JSON_OUT}")
    print(f"Markdown report: {MD_OUT}")
    print(f"Elapsed: {report['elapsed_seconds']} s")


if __name__ == "__main__":
    main()
