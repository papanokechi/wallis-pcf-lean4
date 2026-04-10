#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from mpmath import mp

from v6_5_structural_map import Spec, eval_cf, load_vquad_reference

RESULT_DIR = Path("results")
JSON_PATH = RESULT_DIR / "v6_5_stepB_pslq.json"
MD_PATH = RESULT_DIR / "v6_5_stepB_pslq.md"


@dataclass(slots=True)
class PslqAttempt:
    target: str
    tier: str
    maxcoeff_tested: int
    relation: str
    residual: str
    found: bool


def cf_terms(x, count: int = 20) -> list[int]:
    x = mp.mpf(x)
    terms: list[int] = []
    for _ in range(count):
        a = int(mp.floor(x))
        terms.append(a)
        frac = x - a
        if frac == 0:
            break
        x = 1 / frac
    return terms


def format_relation(coeffs: list[int], labels: list[str]) -> str:
    pieces: list[str] = []
    for c, label in zip(coeffs, labels):
        if c == 0:
            continue
        pieces.append(f"{c}*{label}")
    return " + ".join(pieces) + " = 0" if pieces else "0 = 0"


def try_pslq(target_name: str, target, tier_name: str, basis: list[tuple[str, mp.mpf]]) -> PslqAttempt:
    labels = [target_name] + [name for name, _ in basis]
    vector = [target] + [value for _, value in basis]
    last_maxcoeff = 0
    for maxcoeff in (50, 200, 1000):
        last_maxcoeff = maxcoeff
        rel = mp.pslq(vector, maxcoeff=maxcoeff, tol=mp.mpf(10) ** (-100))
        if rel:
            residual = abs(sum(c * v for c, v in zip(rel, vector)))
            return PslqAttempt(
                target=target_name,
                tier=tier_name,
                maxcoeff_tested=maxcoeff,
                relation=format_relation(rel, labels),
                residual=mp.nstr(residual, 20),
                found=True,
            )
    return PslqAttempt(
        target=target_name,
        tier=tier_name,
        maxcoeff_tested=last_maxcoeff,
        relation="",
        residual="n/a",
        found=False,
    )


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    mp.dps = 250
    spec = Spec("fixed_alpha", -15, -1, -4, 0, "5/4", 1)
    value = eval_cf(spec, 0, 3000)
    vquad = load_vquad_reference(250)
    zeta3 = mp.zeta(3)
    gap = value - 5 * vquad

    phi = (1 + mp.sqrt(5)) / 2
    tier1 = [
        ("1", mp.mpf(1)),
        ("Vquad", vquad),
        ("zeta3", zeta3),
        ("Vquad^2", vquad**2),
        ("Vquad*zeta3", vquad * zeta3),
        ("zeta3^2", zeta3**2),
        ("1/Vquad", 1 / vquad),
        ("1/zeta3", 1 / zeta3),
    ]
    tier2 = [
        ("pi", mp.pi),
        ("pi^2", mp.pi**2),
        ("log(2)", mp.log(2)),
        ("pi*Vquad", mp.pi * vquad),
        ("pi*zeta3", mp.pi * zeta3),
        ("pi^2/zeta3", (mp.pi**2) / zeta3),
        ("Catalan", mp.catalan),
        ("zeta5", mp.zeta(5)),
    ]
    tier3 = [
        ("sqrt(5)*Vquad", mp.sqrt(5) * vquad),
        ("phi*Vquad", phi * vquad),
        ("sqrt(zeta3)", mp.sqrt(zeta3)),
        ("Vquad^(1/3)", vquad ** (mp.mpf(1) / 3)),
    ]

    attempts = []
    for target_name, target in (("x", value), ("gap", gap)):
        attempts.append(asdict(try_pslq(target_name, target, "Tier 1", tier1)))
        attempts.append(asdict(try_pslq(target_name, target, "Tier 2", tier2)))
        attempts.append(asdict(try_pslq(target_name, target, "Tier 3", tier3)))

    payload = {
        "timestamp": time.time(),
        "spec": asdict(spec),
        "dps": mp.dps,
        "depth": 3000,
        "value": mp.nstr(value, 80),
        "gap": mp.nstr(gap, 30),
        "identify_value": str(mp.identify(value)),
        "identify_gap": str(mp.identify(gap)),
        "continued_fraction_value": cf_terms(value, 20),
        "continued_fraction_gap": cf_terms(abs(gap), 20),
        "attempts": attempts,
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step B — PSLQ identification of the V_quad island",
        "",
        f"_Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['timestamp']))}_",
        "",
        f"- Spec: `{payload['spec']}`",
        f"- Working precision: `{payload['dps']} dps`",
        f"- Depth: `{payload['depth']}`",
        f"- Island value `x`: `{payload['value']}`",
        f"- Gap `x - 5*V_quad`: `{payload['gap']}`",
        f"- `mp.identify(x)`: `{payload['identify_value']}`",
        f"- `mp.identify(gap)`: `{payload['identify_gap']}`",
        f"- CF terms for `x`: `{payload['continued_fraction_value']}`",
        f"- CF terms for `|gap|`: `{payload['continued_fraction_gap']}`",
        "",
        "## PSLQ attempts",
        "",
        "| target | tier | found | maxcoeff tested | residual | relation |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in attempts:
        relation = row['relation'] if row['relation'] else 'none up to bound'
        lines.append(
            f"| {row['target']} | {row['tier']} | {row['found']} | {row['maxcoeff_tested']} | `{row['residual']}` | `{relation}` |"
        )

    if not any(row["found"] for row in attempts):
        lines.extend([
            "",
            "> No small-coefficient PSLQ relation was found for the island value or the gap in the tested bases. This is strong negative evidence against a simple low-weight expression in `V_quad`, `ζ(3)`, `π`, `log(2)`, `Catalan`, or the tested algebraic variants.",
        ])

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Step B PSLQ complete")
    print(f"JSON: {JSON_PATH}")
    print(f"MD:   {MD_PATH}")
    for row in attempts:
        print(row)


if __name__ == "__main__":
    main()
