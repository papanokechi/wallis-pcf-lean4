#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from mpmath import mp

from v6_5_structural_map import Spec, eval_cf, load_vquad_reference

RESULT_DIR = Path("results")
JSON_PATH = RESULT_DIR / "v6_5_stepC_mfamily.json"
MD_PATH = RESULT_DIR / "v6_5_stepC_mfamily.md"


def mp_digits(x) -> float:
    x = abs(x)
    if x == 0:
        return 999.0
    return float(-mp.log10(x))


def try_pslq(name: str, target, basis: list[tuple[str, Any]]):
    labels = [name] + [lab for lab, _ in basis]
    vector = [target] + [val for _, val in basis]
    for maxcoeff in (50, 200, 500):
        with mp.workdps(120):
            rel = mp.pslq(vector, maxcoeff=maxcoeff, tol=mp.mpf(10) ** (-60))
        if rel:
            residual = abs(sum(c * v for c, v in zip(rel, vector)))
            pieces = [f"{c}*{lab}" for c, lab in zip(rel, labels) if c != 0]
            return {
                "found": True,
                "maxcoeff": maxcoeff,
                "relation": " + ".join(pieces) + " = 0",
                "residual": mp.nstr(residual, 20),
            }
    return {"found": False, "maxcoeff": 500, "relation": "", "residual": "n/a"}


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    mp.dps = 400
    spec = Spec("fixed_alpha", -15, -1, -4, 0, "5/4", 1)
    depth = 500
    m_values = list(range(6))

    vals = [eval_cf(spec, m, depth) for m in m_values]
    diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    ratios = [vals[i] / vals[i - 1] for i in range(1, len(vals))]
    diff_ratios = [diffs[i] / diffs[i - 1] for i in range(1, len(diffs)) if diffs[i - 1] != 0]
    affine_residuals = [vals[m] - (6 - 4 * m) for m in m_values]

    vquad = load_vquad_reference(200)
    zeta3 = mp.zeta(3)
    tier1_basis = [
        ("1", mp.mpf(1)),
        ("Vquad", vquad),
        ("zeta3", zeta3),
        ("Vquad^2", vquad**2),
        ("Vquad*zeta3", vquad * zeta3),
        ("zeta3^2", zeta3**2),
        ("1/Vquad", 1 / vquad),
        ("1/zeta3", 1 / zeta3),
    ]
    tier2_basis = [
        ("pi", mp.pi),
        ("pi^2", mp.pi**2),
        ("log(2)", mp.log(2)),
        ("Catalan", mp.catalan),
    ]

    pslq_rows = {}
    for m in (0, 1, 2):
        pslq_rows[f"x({m}) / Tier 1"] = try_pslq(f"x{m}", vals[m], tier1_basis)
        pslq_rows[f"x({m}) / Tier 2"] = try_pslq(f"x{m}", vals[m], tier2_basis)

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
        "values": [{"m": m, "x": mp.nstr(v, 50)} for m, v in zip(m_values, vals)],
        "differences": [{"pair": f"{i}->{i+1}", "delta": mp.nstr(d, 30)} for i, d in enumerate(diffs)],
        "ratios": [{"pair": f"{i}/{i-1}", "ratio": mp.nstr(r, 30)} for i, r in enumerate(ratios, start=1)],
        "difference_ratios": [{"pair": f"d{i+1}/d{i}", "ratio": mp.nstr(r, 30)} for i, r in enumerate(diff_ratios, start=1)],
        "affine_residuals_vs_6_minus_4m": [{"m": m, "residual": mp.nstr(r, 30)} for m, r in zip(m_values, affine_residuals)],
        "pslq": pslq_rows,
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step C — m-family diagnostic for the V_quad island",
        "",
        f"_Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['timestamp']))}_",
        "",
        f"- Spec: `{payload['spec']}`",
        f"- Working precision: `{payload['dps']} dps`",
        f"- Depth: `{depth}`",
        "",
        "## Values `x(m)`",
        "",
        "| m | x(m) |",
        "|---:|---|",
    ]
    for row in payload["values"]:
        lines.append(f"| {row['m']} | `{row['x']}` |")

    lines.extend([
        "",
        "## First differences `x(m+1)-x(m)`",
        "",
        "| pair | delta |",
        "|---|---|",
    ])
    for row in payload["differences"]:
        lines.append(f"| {row['pair']} | `{row['delta']}` |")

    lines.extend([
        "",
        "## Ratios `x(m)/x(m-1)`",
        "",
        "| pair | ratio |",
        "|---|---|",
    ])
    for row in payload["ratios"]:
        lines.append(f"| {row['pair']} | `{row['ratio']}` |")

    lines.extend([
        "",
        "## Difference ratios `d(m)/d(m-1)`",
        "",
        "| pair | ratio |",
        "|---|---|",
    ])
    for row in payload["difference_ratios"]:
        lines.append(f"| {row['pair']} | `{row['ratio']}` |")

    lines.extend([
        "",
        "## Residuals against `6-4m`",
        "",
        "| m | `x(m) - (6-4m)` |",
        "|---:|---|",
    ])
    for row in payload["affine_residuals_vs_6_minus_4m"]:
        lines.append(f"| {row['m']} | `{row['residual']}` |")

    lines.extend([
        "",
        "## PSLQ checks on `x(0), x(1), x(2)`",
        "",
        "| target | found | maxcoeff | residual | relation |",
        "|---|---:|---:|---:|---|",
    ])
    for key, row in pslq_rows.items():
        relation = row['relation'] if row['relation'] else 'none up to bound'
        lines.append(f"| {key} | {row['found']} | {row['maxcoeff']} | `{row['residual']}` | `{relation}` |")

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Step C m-family complete")
    print(f"JSON: {JSON_PATH}")
    print(f"MD:   {MD_PATH}")
    for row in payload['values']:
        print(row)
    for row in payload['differences']:
        print(row)
    for row in payload['ratios']:
        print(row)
    for row in payload['difference_ratios']:
        print(row)
    for key, row in pslq_rows.items():
        print(key, row)


if __name__ == "__main__":
    main()
