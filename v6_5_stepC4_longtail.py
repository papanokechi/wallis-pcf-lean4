#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from mpmath import mp

from v6_5_structural_map import Spec, eval_cf

RESULT_DIR = Path("results")
JSON_PATH = RESULT_DIR / "v6_5_stepC4_longtail.json"
MD_PATH = RESULT_DIR / "v6_5_stepC4_longtail.md"

CANDIDATE_EXPONENTS = [1.0, 1.25, 1.5, 2.0]


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    return slope, intercept


def second_difference_score(values: list[float]) -> float:
    if len(values) < 3:
        return float("inf")
    sds = [values[i + 2] - 2 * values[i + 1] + values[i] for i in range(len(values) - 2)]
    return sum(abs(x) for x in sds) / len(sds)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    mp.dps = 400

    spec = Spec("fixed_alpha", -15, -1, -4, 0, "5/4", 1)
    depth = 1200
    m_values = list(range(2, 51))

    xs = [eval_cf(spec, m, depth) for m in m_values]
    eps = [x - (6 - 4 * m) for m, x in zip(m_values, xs)]

    probe_points = [10, 15, 20, 30, 40, 50]
    local_alpha = []
    for m in range(10, 50):
        e0 = abs(float(eps[m_values.index(m)]))
        e1 = abs(float(eps[m_values.index(m + 1)]))
        num = math.log(e1 / e0)
        den = math.log((m + 1) / m)
        local_alpha.append({"m": m, "alpha_local": round(-num / den, 6)})

    log_m = [math.log(float(m)) for m in m_values]
    log_eps = [math.log(abs(float(e))) for e in eps]
    slope_full, intercept_full = fit_line(log_m, log_eps)

    tail_m = list(range(20, 51))
    tail_log_m = [math.log(float(m)) for m in tail_m]
    tail_log_eps = [math.log(abs(float(eps[m_values.index(m)]))) for m in tail_m]
    slope_tail, intercept_tail = fit_line(tail_log_m, tail_log_eps)

    scaling_scores = []
    scaling_samples = {}
    for alpha in CANDIDATE_EXPONENTS:
        seq = [float((m ** alpha) * eps[m_values.index(m)]) for m in tail_m]
        score = second_difference_score(seq)
        scaling_scores.append({"alpha": alpha, "second_difference_score": score})
        scaling_samples[str(alpha)] = [
            {"m": m, "value": mp.nstr((m ** alpha) * eps[m_values.index(m)], 20)}
            for m in probe_points
        ]

    scaling_scores.sort(key=lambda row: row["second_difference_score"])
    best_alpha = scaling_scores[0]["alpha"]

    payload = {
        "timestamp": time.time(),
        "spec": {
            "family": spec.family,
            "a1": spec.a1,
            "a2": spec.a2,
            "b1": spec.b1,
            "b2": spec.b2,
            "c_value": spec.c_value,
            "bridge": spec.bridge,
        },
        "depth": depth,
        "dps": mp.dps,
        "global_alpha_fit_m2_to_m50": round(-slope_full, 6),
        "tail_alpha_fit_m20_to_m50": round(-slope_tail, 6),
        "global_log_intercept": round(intercept_full, 6),
        "tail_log_intercept": round(intercept_tail, 6),
        "local_alpha_samples": [row for row in local_alpha if row["m"] in probe_points[:-1]],
        "candidate_scaling_scores": scaling_scores,
        "candidate_scaling_samples": scaling_samples,
        "best_candidate_alpha": best_alpha,
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step C.5 — long-tail exponent stabilization check",
        "",
        f"_Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['timestamp']))}_",
        "",
        f"- Spec: `{payload['spec']}`",
        f"- Working precision: `{payload['dps']} dps`",
        f"- Depth: `{payload['depth']}`",
        f"- Global exponent fit over `m=2..50`: `{payload['global_alpha_fit_m2_to_m50']}`",
        f"- Tail exponent fit over `m=20..50`: `{payload['tail_alpha_fit_m20_to_m50']}`",
        f"- Best candidate among `1, 5/4, 3/2, 2`: `{payload['best_candidate_alpha']}`",
        "",
        "## Local exponent samples",
        "",
        "| m | alpha_local from epsilon(m+1)/epsilon(m) |",
        "|---:|---:|",
    ]
    for row in payload["local_alpha_samples"]:
        lines.append(f"| {row['m']} | `{row['alpha_local']}` |")

    lines.extend([
        "",
        "## Candidate scaling scores (smaller is better)",
        "",
        "| alpha | mean abs second difference on `m^alpha epsilon(m)` over m=20..50 |",
        "|---:|---:|",
    ])
    for row in scaling_scores:
        lines.append(f"| {row['alpha']} | `{row['second_difference_score']:.12e}` |")

    for alpha in CANDIDATE_EXPONENTS:
        lines.extend([
            "",
            f"### Samples for alpha = {alpha}",
            "",
            "| m | value |",
            "|---:|---:|",
        ])
        for row in scaling_samples[str(alpha)]:
            lines.append(f"| {row['m']} | `{row['value']}` |")

    lines.extend([
        "",
        "> This test determines whether the exponent is actually stabilizing and which simple power gives the flattest renormalized sequence at large `m`.",
    ])

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Step C.5 long-tail check complete")
    print(f"JSON: {JSON_PATH}")
    print(f"MD:   {MD_PATH}")
    print("global_alpha_fit_m2_to_m50", payload['global_alpha_fit_m2_to_m50'])
    print("tail_alpha_fit_m20_to_m50", payload['tail_alpha_fit_m20_to_m50'])
    print("best_candidate_alpha", payload['best_candidate_alpha'])
    for row in payload['local_alpha_samples']:
        print(row)
    for row in scaling_scores:
        print(row)


if __name__ == "__main__":
    main()
