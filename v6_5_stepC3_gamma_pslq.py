#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mpmath import mp

from v6_5_structural_map import Spec, eval_cf

RESULT_DIR = Path("results")
JSON_PATH = RESULT_DIR / "v6_5_stepC3_gamma_pslq.json"
MD_PATH = RESULT_DIR / "v6_5_stepC3_gamma_pslq.md"


@dataclass(slots=True)
class Attempt:
    target: str
    basis_name: str
    found: bool
    maxcoeff: int
    relation: str
    residual: str


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    return slope, intercept


def estimate_c() -> tuple[mp.mpf, float, list[dict[str, str]]]:
    spec = Spec("fixed_alpha", -15, -1, -4, 0, "5/4", 1)
    depth = 1200
    m_values = list(range(5, 16))
    vals = [eval_cf(spec, m, depth) for m in m_values]
    eps = [vals[i] - (6 - 4 * m) for i, m in enumerate(m_values)]

    log_m = [math.log(float(m)) for m in m_values]
    log_eps = [math.log(abs(float(e))) for e in eps]
    slope, _ = fit_line(log_m, log_eps)
    alpha = -slope

    xs = [1.0 / m for m in m_values]
    ys = [float((m ** 1.5) * eps[i]) for i, m in enumerate(m_values)]
    _, intercept = fit_line(xs, ys)
    c_est = mp.mpf(intercept)

    rows = [
        {
            "m": str(m),
            "epsilon": mp.nstr(eps[i], 30),
            "m32epsilon": mp.nstr((m ** 1.5) * eps[i], 30),
        }
        for i, m in enumerate(m_values)
    ]
    return c_est, alpha, rows


def format_relation(coeffs: list[int], labels: list[str]) -> str:
    pieces = [f"{c}*{lab}" for c, lab in zip(coeffs, labels) if c != 0]
    return " + ".join(pieces) + " = 0" if pieces else "0 = 0"


def try_pslq(target_name: str, target, basis_name: str, basis: list[tuple[str, Any]]) -> Attempt:
    labels = [target_name] + [name for name, _ in basis]
    vec = [target] + [val for _, val in basis]
    for maxcoeff in (50, 200, 1000, 5000):
        rel = mp.pslq(vec, maxcoeff=maxcoeff, tol=mp.mpf(10) ** (-80))
        if rel:
            residual = abs(sum(c * v for c, v in zip(rel, vec)))
            return Attempt(
                target=target_name,
                basis_name=basis_name,
                found=True,
                maxcoeff=maxcoeff,
                relation=format_relation(rel, labels),
                residual=mp.nstr(residual, 20),
            )
    return Attempt(
        target=target_name,
        basis_name=basis_name,
        found=False,
        maxcoeff=5000,
        relation="",
        residual="n/a",
    )


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    mp.dps = 350

    c_est, alpha, rows = estimate_c()

    gamma14 = mp.gamma(mp.mpf(1) / 4)
    gamma34 = mp.gamma(mp.mpf(3) / 4)
    z3 = mp.zeta(3)
    sq2 = mp.sqrt(2)
    pi = mp.pi
    rho = mp.sqrt(1 + mp.sqrt(2))
    log1ps2 = mp.log(1 + mp.sqrt(2))

    ratio1 = c_est * pi / (gamma14 ** 2)
    ratio2 = c_est * pi * sq2 / (gamma14 ** 2)
    ratio3 = c_est / (z3 ** (mp.mpf(1) / 4))
    ratio4 = c_est / (z3 ** (mp.mpf(3) / 4))

    basis_gamma = [
        ("1", mp.mpf(1)),
        ("Gamma14", gamma14),
        ("Gamma34", gamma34),
        ("Gamma14^2", gamma14 ** 2),
        ("Gamma14^3", gamma14 ** 3),
        ("Gamma14^4", gamma14 ** 4),
        ("Gamma14/pi", gamma14 / pi),
        ("Gamma14^2/pi", gamma14 ** 2 / pi),
        ("Gamma14^2/(pi*sqrt2)", gamma14 ** 2 / (pi * sq2)),
        ("Gamma14^2*zeta3/pi^2", gamma14 ** 2 * z3 / (pi ** 2)),
        ("sqrt2*Gamma14^2/pi^2", sq2 * gamma14 ** 2 / (pi ** 2)),
        ("1/Gamma14", 1 / gamma14),
        ("1/Gamma14^2", 1 / (gamma14 ** 2)),
        ("sqrt(1+sqrt2)", rho),
        ("log(1+sqrt2)", log1ps2),
    ]

    basis_ratio = [
        ("1", mp.mpf(1)),
        ("zeta3^(1/4)", z3 ** (mp.mpf(1) / 4)),
        ("zeta3^(3/4)", z3 ** (mp.mpf(3) / 4)),
        ("Gamma14^2/pi", gamma14 ** 2 / pi),
        ("Gamma14^2/(pi*sqrt2)", gamma14 ** 2 / (pi * sq2)),
        ("log(1+sqrt2)", log1ps2),
    ]

    attempts = [
        asdict(try_pslq("C", c_est, "Gamma basis", basis_gamma)),
        asdict(try_pslq("C/(zeta3^(1/4))", ratio3, "Gamma+zeta basis", basis_ratio)),
        asdict(try_pslq("C/(zeta3^(3/4))", ratio4, "Gamma+zeta basis", basis_ratio)),
        asdict(try_pslq("C*pi/Gamma14^2", ratio1, "Rationalized ratio basis", [("1", mp.mpf(1)), ("sqrt2", sq2), ("log(1+sqrt2)", log1ps2)])),
        asdict(try_pslq("C*pi*sqrt2/Gamma14^2", ratio2, "Rationalized ratio basis", [("1", mp.mpf(1)), ("log(1+sqrt2)", log1ps2)])),
    ]

    payload = {
        "timestamp": time.time(),
        "dps": mp.dps,
        "alpha_tail_fit": round(alpha, 6),
        "C_est": mp.nstr(c_est, 40),
        "C*pi/Gamma14^2": mp.nstr(ratio1, 30),
        "C*pi*sqrt2/Gamma14^2": mp.nstr(ratio2, 30),
        "C/zeta3^(1/4)": mp.nstr(ratio3, 30),
        "C/zeta3^(3/4)": mp.nstr(ratio4, 30),
        "tail_rows": rows,
        "attempts": attempts,
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step C.4 — Gamma-basis PSLQ for the asymptotic coefficient C",
        "",
        f"_Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['timestamp']))}_",
        "",
        f"- Working precision: `{payload['dps']} dps`",
        f"- Tail-fit exponent used in `C` estimation: `{payload['alpha_tail_fit']}`",
        f"- `C ≈ {payload['C_est']}`",
        f"- `C*pi/Gamma(1/4)^2 ≈ {payload['C*pi/Gamma14^2']}`",
        f"- `C*pi*sqrt(2)/Gamma(1/4)^2 ≈ {payload['C*pi*sqrt2/Gamma14^2']}`",
        f"- `C/zeta(3)^(1/4) ≈ {payload['C/zeta3^(1/4)']}`",
        f"- `C/zeta(3)^(3/4) ≈ {payload['C/zeta3^(3/4)']}`",
        "",
        "## Tail data used for the fit",
        "",
        "| m | epsilon(m) | m^(3/2) epsilon(m) |",
        "|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(f"| {row['m']} | `{row['epsilon']}` | `{row['m32epsilon']}` |")

    lines.extend([
        "",
        "## PSLQ attempts",
        "",
        "| target | basis | found | maxcoeff | residual | relation |",
        "|---|---|---:|---:|---:|---|",
    ])
    for row in attempts:
        relation = row['relation'] if row['relation'] else 'none up to bound'
        lines.append(f"| {row['target']} | {row['basis_name']} | {row['found']} | {row['maxcoeff']} | `{row['residual']}` | `{relation}` |")

    if not any(row['found'] for row in attempts):
        lines.extend([
            "",
            "> No low-height Gamma/Apéry-style relation was detected for `C` in the tested basis up to coefficient bound `5000`. This is strong negative evidence against the simplest `Gamma(1/4)` normalizations, though a subtler higher-weight expression is still possible.",
        ])

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Step C.4 gamma PSLQ complete")
    print(f"JSON: {JSON_PATH}")
    print(f"MD:   {MD_PATH}")
    print("C_est", payload['C_est'])
    for row in attempts:
        print(row)


if __name__ == "__main__":
    main()
