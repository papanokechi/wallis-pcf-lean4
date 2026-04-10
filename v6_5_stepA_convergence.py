#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from mpmath import mp, fabs, log10

from v6_5_structural_map import Spec, eval_cf, load_vquad_reference

RESULT_DIR = Path("results")
JSON_PATH = RESULT_DIR / "v6_5_stepA_convergence.json"
MD_PATH = RESULT_DIR / "v6_5_stepA_convergence.md"


def digits(err: mp.mpf) -> float:
    if err == 0:
        return 999.0
    return float(-log10(err + mp.mpf("1e-590")))


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    mp.dps = 600
    spec = Spec("fixed_alpha", -15, -1, -4, 0, "5/4", 1)
    depths = [100, 200, 500, 1000, 1500, 2000]
    ref_depth = 3000

    ref = eval_cf(spec, 0, ref_depth)
    vquad = load_vquad_reference(200)
    gap = fabs(ref - 5 * vquad)

    rows = []
    for depth in depths:
        value = eval_cf(spec, 0, depth)
        err = fabs(value - ref)
        rows.append(
            {
                "depth": depth,
                "digits_vs_ref": round(digits(err), 6),
                "err_vs_ref": mp.nstr(err, 20),
                "value": mp.nstr(value, 50),
            }
        )

    verdict = (
        "stable-limit-offset"
        if min(r["digits_vs_ref"] for r in rows) >= 50
        else "needs-more-structure-check"
    )

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
        "ref_depth": ref_depth,
        "reference_value": mp.nstr(ref, 80),
        "gap_vs_5Vquad": mp.nstr(gap, 20),
        "rows": rows,
        "verdict": verdict,
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Step A — V_quad island convergence check",
        "",
        f"_Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['timestamp']))}_",
        "",
        f"- Spec: `{payload['spec']}`",
        f"- Reference depth: `{ref_depth}`",
        f"- `|x_ref - 5*V_quad| = {payload['gap_vs_5Vquad']}`",
        f"- Verdict: `{verdict}`",
        "",
        "| depth | digits vs ref | `|x_n - x_ref|` |",
        "|---:|---:|---:|",
    ]
    for row in rows:
        md_lines.append(f"| {row['depth']} | {row['digits_vs_ref']} | `{row['err_vs_ref']}` |")

    if verdict == "stable-limit-offset":
        md_lines.extend([
            "",
            "> The agreement with the depth-3000 reference is already very high at shallow depth, so the `0.002871901...` separation from `5*V_quad` is a real limiting gap, not a slow transient.",
        ])

    MD_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("Step A convergence complete")
    print(f"JSON: {JSON_PATH}")
    print(f"MD:   {MD_PATH}")
    for row in rows:
        print(row["depth"], row["digits_vs_ref"], row["err_vs_ref"])
    print("gap_vs_5Vquad", payload["gap_vs_5Vquad"])
    print("verdict", verdict)


if __name__ == "__main__":
    main()
