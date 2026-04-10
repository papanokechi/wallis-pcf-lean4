#!/usr/bin/env python3
"""Expanded two-basis Meijer/Stokes search for V_quad.

This script searches low-height relations of the form

    a*V_quad + b*M + c*S + d = 0,

where M is a Meijer-G value (or a simple ratio of the requested Meijer-G
special values) and S is a Stokes/connection datum extracted from the cubic
ODE attached to

    V_quad = 1 + K_{n>=1} 1/(3n^2+n+1).

Outputs
-------
- `vquad_two_basis_meijer_stokes_report.json`
- `vquad_two_basis_meijer_stokes_report.md`
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from fractions import Fraction
from pathlib import Path

import mpmath as mp

from vquad_stokes_0f2_identification import compute_vquad, stokes_connection

REPORT_JSON = Path("vquad_two_basis_meijer_stokes_report.json")
REPORT_MD = Path("vquad_two_basis_meijer_stokes_report.md")
CONNECTION_JSON = Path("vquad_connection_matrix_report.json")


def relation_status(vec: list[mp.mpf], labels: list[str], maxcoeff: int, tol_digits: int) -> dict:
    """Attempt PSLQ and return a structured status dict."""
    try:
        rel = mp.pslq(vec, tol=mp.mpf(10) ** (-tol_digits), maxcoeff=maxcoeff, maxsteps=40000)
    except Exception as exc:
        return {"status": "error", "message": str(exc), "relation": None}
    if rel is None:
        return {"status": "none", "relation": None}
    nz = [(int(c), lab) for c, lab in zip(rel, labels) if c != 0]
    touches_v = any(lab == labels[0] for _, lab in nz)
    residual = abs(mp.fsum(mp.mpf(c) * v for c, v in zip(rel, vec)))
    return {
        "status": "relation" if touches_v else "trivial",
        "relation": nz,
        "residual": mp.nstr(residual, 12),
    }


def digits_of_error(err: mp.mpf) -> float:
    err = abs(err)
    if err == 0:
        return math.inf
    return float(-mp.log10(err))


def small_rationals(max_num: int = 4, max_den: int = 3) -> list[mp.mpf]:
    vals: set[tuple[int, int]] = set()
    for q in range(1, max_den + 1):
        for p in range(-max_num * q, max_num * q + 1):
            vals.add((Fraction(p, q).numerator, Fraction(p, q).denominator))
    return [mp.mpf(p) / q for p, q in sorted(vals)]


def best_affine_two_basis(target: mp.mpf, x: mp.mpf, y: mp.mpf) -> dict:
    """Best low-height approximation target ≈ a*x + b*y + c.

    This is only a heuristic ranking step, so it intentionally uses fast
    double-precision arithmetic rather than full high-precision mpmath.
    """
    rats = small_rationals(4, 3)
    tf = float(target)
    xf = float(x)
    yf = float(y)
    best = {
        "digits": -1.0,
        "a": None,
        "b": None,
        "c": None,
        "error": None,
    }
    for a in rats:
        af = float(a)
        for b in rats:
            bf = float(b)
            for c in range(-3, 4):
                err = abs(tf - af * xf - bf * yf - c)
                if err == 0:
                    digs = math.inf
                else:
                    digs = -math.log10(err)
                if digs > best["digits"]:
                    best = {
                        "digits": digs,
                        "a": mp.nstr(a, 12),
                        "b": mp.nstr(b, 12),
                        "c": c,
                        "error": f"{err:.6e}",
                    }
    return best


def meijer_basis() -> list[tuple[str, mp.mpf]]:
    one = mp.mpf(1)
    base = []
    values = {}
    specs = {
        "G(1/27)": one / 27,
        "G(4/27)": 4 * one / 27,
        "G(1/3)": one / 3,
    }
    for label, z in specs.items():
        values[label] = mp.meijerg([[], []], [[0, one / 3], [2 * one / 3]], z)
        base.append((label, values[label]))
    base.extend([
        ("G(4/27)/G(1/27)", values["G(4/27)"] / values["G(1/27)"]),
        ("G(1/3)/G(1/27)", values["G(1/3)"] / values["G(1/27)"]),
        ("G(1/3)/G(4/27)", values["G(1/3)"] / values["G(4/27)"]),
    ])
    return base


def stokes_basis() -> list[tuple[str, mp.mpf]]:
    y0, y0p, r0 = stokes_connection(X0=mp.mpf("1000"), h=mp.mpf("0.03125"))
    if CONNECTION_JSON.exists():
        payload = json.loads(CONNECTION_JSON.read_text(encoding="utf-8"))
        cm = payload["connection_matrix"]
        m11 = mp.mpf(cm["M11"])
        m12 = mp.mpf(cm["M12"])
        m21 = mp.mpf(cm["M21"])
        m22 = mp.mpf(cm["M22"])
    else:
        m11 = m12 = m21 = m22 = mp.nan
    return [
        ("y0", y0),
        ("y0p", y0p),
        ("r0=y'/y", r0),
        ("1/r0", 1 / r0),
        ("M11", m11),
        ("M21", m21),
        ("M11/M21", m11 / m21),
        ("M12/M22", m12 / m22),
        ("M11+M21", m11 + m21),
        ("-M21/3", -m21 / 3),
    ]


def write_markdown(summary: dict) -> None:
    lines = [
        "# Expanded two-basis Meijer/Stokes search for V_quad",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Precision: {summary['dps']} dps",
        f"- V_quad: `{summary['vquad']}`",
        f"- Pair count: `{summary['pair_count']}`",
        "",
        "## Verified PSLQ hits",
        "",
    ]
    if summary["hits"]:
        for hit in summary["hits"]:
            lines.append(f"- `{hit['meijer_label']}` with `{hit['stokes_label']}` -> `{hit['relation']}` (residual `{hit['residual']}`)")
    else:
        lines.append("- No non-trivial PSLQ relation involving `V_quad` was found in the tested two-basis space.")
    lines.append("")
    lines.append("## Strongest low-height near misses")
    lines.append("")
    lines.append("| rank | Meijer basis | Stokes basis | digits | affine fit | error |")
    lines.append("|---:|---|---|---:|---|---|")
    for idx, row in enumerate(summary["top_near_misses"], start=1):
        fit = f"{row['a']}*M + {row['b']}*S + {row['c']}"
        lines.append(
            f"| {idx} | `{row['meijer_label']}` | `{row['stokes_label']}` | {row['digits']:.6f} | `{fit}` | `{row['error']}` |"
        )
    lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Expanded two-basis Meijer/Stokes search for V_quad")
    parser.add_argument("--dps", type=int, default=120)
    parser.add_argument("--depth", type=int, default=9000)
    parser.add_argument("--maxcoeff", type=int, default=5000)
    args = parser.parse_args()

    mp.mp.dps = args.dps
    t0 = time.time()

    V = compute_vquad(args.depth, args.dps)
    m_basis = meijer_basis()
    s_basis = stokes_basis()

    print("=" * 76)
    print("Expanded two-basis Meijer/Stokes search for V_quad")
    print("=" * 76)
    print(f"V_quad = {mp.nstr(V, 40)}")
    print(f"Meijer basis size = {len(m_basis)} | Stokes basis size = {len(s_basis)}")
    print()

    hits = []
    near_misses = []

    for m_label, m_val in m_basis:
        print(f"[Meijer] {m_label} = {mp.nstr(m_val, 25)}")
    print()
    for s_label, s_val in s_basis:
        print(f"[Stokes] {s_label} = {mp.nstr(s_val, 25)}")
    print()

    for m_label, m_val in m_basis:
        for s_label, s_val in s_basis:
            labels = ["V_quad", m_label, s_label, "1"]
            status = relation_status([V, m_val, s_val, mp.mpf(1)], labels, args.maxcoeff, tol_digits=min(70, args.dps // 2))
            if status["status"] == "relation":
                hits.append({
                    "meijer_label": m_label,
                    "stokes_label": s_label,
                    "relation": status["relation"],
                    "residual": status.get("residual", "0"),
                })
                print(f"HIT: {m_label} + {s_label} -> {status['relation']} residual {status.get('residual', '0')}")
            else:
                approx = best_affine_two_basis(V, m_val, s_val)
                near_misses.append({
                    "meijer_label": m_label,
                    "stokes_label": s_label,
                    **approx,
                })

    near_misses.sort(key=lambda row: (-row["digits"], row["meijer_label"], row["stokes_label"]))
    top = near_misses[:10]

    print("Top near misses:")
    for row in top:
        print(
            f"  {row['digits']:.6f}d :: {row['meijer_label']} with {row['stokes_label']} :: "
            f"V ~= {row['a']}*M + {row['b']}*S + {row['c']} (err {row['error']})"
        )

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dps": args.dps,
        "depth": args.depth,
        "maxcoeff": args.maxcoeff,
        "vquad": mp.nstr(V, 50),
        "pair_count": len(m_basis) * len(s_basis),
        "hits": hits,
        "top_near_misses": top,
        "wall_seconds": round(time.time() - t0, 3),
    }
    REPORT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary)

    print()
    if hits:
        print(f"Found {len(hits)} non-trivial PSLQ relation(s).")
    else:
        print("No non-trivial two-basis PSLQ relation found.")
    print(f"Wall time: {summary['wall_seconds']}s")
    print(f"JSON -> {REPORT_JSON}")
    print(f"MD   -> {REPORT_MD}")


if __name__ == "__main__":
    main()
