#!/usr/bin/env python3
"""Independent Paper 14 back-check for the G-01 law on k=1..4."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from mpmath import mp, pi, pslq, sqrt

mp.dps = 100


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def c_k(k: int):
    return pi * sqrt((2 * k) / 3)


def g01_value(k: int):
    c = c_k(k)
    return -(k * c) / 48 - ((k + 1) * (k + 3)) / (8 * c)


def paper14_closed_form(k: int):
    c = c_k(k)
    if k == 1:
        return "-c1/48 - 1/c1", -(c / 48) - 1 / c
    if k == 2:
        return "-c2/24 - 15/(8*c2)", -(c / 24) - 15 / (8 * c)
    if k == 3:
        return "-π*sqrt(2)/16 - 3/(π*sqrt(2))", -(pi * sqrt(2)) / 16 - 3 / (pi * sqrt(2))
    if k == 4:
        return "-c4/12 - 35/(8*c4)", -(c / 12) - 35 / (8 * c)
    raise ValueError(f"Unsupported k={k}; this back-check is only for k=1..4.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify that G-01 matches the Paper 14 k=1..4 theorem cases.")
    parser.add_argument("--output", default="g01_paper14_k1_k4.json", help="Path to the JSON report.")
    args = parser.parse_args()

    rows = []
    matched_ks = []

    print("=" * 78)
    print("G-01 vs Paper 14 Theorem 2 back-check (k=1..4)")
    print("=" * 78)
    print(f"{'k':>2}  {'G-01 value':>24}  {'Paper14 value':>24}  {'|Δ|':>12}  {'PSLQ[A1,c,1/c]':>18}")
    print("-" * 78)

    for k in range(1, 5):
        c = c_k(k)
        g01 = g01_value(k)
        label, paper14 = paper14_closed_form(k)
        gap = abs(g01 - paper14)
        relation = pslq([g01, c, 1 / c], maxcoeff=5000)
        exact_match = gap <= mp.mpf("1e-80")
        if exact_match:
            matched_ks.append(k)

        print(f"{k:>2}  {mp.nstr(g01, 16):>24}  {mp.nstr(paper14, 16):>24}  {mp.nstr(gap, 4):>12}  {str(relation):>18}")
        rows.append(
            {
                "k": k,
                "c_k": mp.nstr(c, 40),
                "g01_formula": f"-({k}*c{k})/48 - {(k + 1) * (k + 3)}/(8*c{k})",
                "paper14_formula": label,
                "g01_value": mp.nstr(g01, 50),
                "paper14_value": mp.nstr(paper14, 50),
                "abs_gap": mp.nstr(gap, 10),
                "exact_match": bool(exact_match),
                "pslq_relation_A1_c_inv_c": relation,
            }
        )

    report = {
        "generated_at": iso_now(),
        "theorem": "Paper 14 Theorem 2 (proved k=1,2,3,4)",
        "rows": rows,
        "matched_ks": matched_ks,
        "all_match": len(matched_ks) == 4,
        "summary": (
            "G-01 exactly reproduces the proved Paper 14 Theorem 2 cases for k=1,2,3,4."
            if len(matched_ks) == 4
            else f"Mismatch detected; only k={matched_ks} matched at the configured precision."
        ),
    }

    out_path = Path(args.output)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("-" * 78)
    print(report["summary"])
    print(f"JSON written to {out_path}")


if __name__ == "__main__":
    main()
