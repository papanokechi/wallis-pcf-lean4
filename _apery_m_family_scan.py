#!/usr/bin/env python3
"""
_apery_m_family_scan.py
=======================

Targeted search for one-parameter Apéry-template PCF families for zeta(3).

We scan two natural ansätze anchored at m=0 by the classical Apéry CF:

  (A) fixed_alpha
      alpha_m(n) = -n^6
      beta_m(n)  = (2n+1)(A(m)n^2 + A(m)n + B(m))

  (B) shifted_alpha
      alpha_m(n) = -n^4 (n+m)^2
      beta_m(n)  = (2n+1)(A(m)n^2 + A(m)n + B(m))

with
      A(m) = 17 + a1*m + a2*m^2,
      B(m) = 5  + b1*m + b2*m^2,

where the m=0 member is exactly Apéry's PCF.

For each candidate family, the script:
  1. evaluates S^(m) for m = 0,1,2,3,
  2. checks simple closed-form matches involving zeta(3) / pi^2,
  3. ranks candidates by the strength of those matches,
  4. fits a low-degree numeric intertwiner shell
         v_n = A(n,m) u_n + B(n,m) u_{n-1} + C(n,m) u_{n-2}
     and reports the validation residual.

The scan uses 8 workers by default and writes a report to
`results/apery_m_family_scan.json`.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import mpmath as mp
import numpy as np
import sympy as sp

RESULT_PATH = Path("results") / "apery_m_family_scan.json"


@dataclass
class Candidate:
    family: str
    a1: int
    a2: int
    b1: int
    b2: int
    score: float
    relations: list[dict[str, Any]]
    intertwiner_max_residual: float | None = None
    intertwiner_med_residual: float | None = None
    intertwiner_coefficients: dict[str, list[str]] | None = None


def alpha_value(kind: str, n: int, m: int) -> mp.mpf:
    n = mp.mpf(n)
    m = mp.mpf(m)
    if kind == "fixed_alpha":
        return -(n ** 6)
    if kind == "shifted_alpha":
        return -(n ** 4) * ((n + m) ** 2)
    raise ValueError(kind)


def A_of_m(a1: int, a2: int, m: int) -> int:
    return 17 + a1 * m + a2 * m * m


def B_of_m(b1: int, b2: int, m: int) -> int:
    return 5 + b1 * m + b2 * m * m


def beta_value(a1: int, a2: int, b1: int, b2: int, n: int, m: int) -> mp.mpf:
    A = mp.mpf(A_of_m(a1, a2, m))
    B = mp.mpf(B_of_m(b1, b2, m))
    n = mp.mpf(n)
    return (2 * n + 1) * (A * n * n + A * n + B)


def eval_pcf(kind: str, a1: int, a2: int, b1: int, b2: int,
             m: int, depth: int = 1400, dps: int = 110) -> mp.mpf | None:
    with mp.workdps(dps + 40):
        val = mp.mpf(0)
        for n in range(depth, 0, -1):
            an = alpha_value(kind, n, m)
            bn = beta_value(a1, a2, b1, b2, n, m)
            den = bn + val
            if abs(den) < mp.mpf(10) ** (-(dps - 10)):
                return None
            val = an / den
        b0 = mp.mpf(B_of_m(b1, b2, m))
        return b0 + val


def _best_rational_multiple(val: mp.mpf, target: mp.mpf,
                            max_num: int = 30, max_den: int = 30) -> tuple[str, float]:
    best_name = "(no match)"
    best_digits = 0.0
    for p in range(-max_num, max_num + 1):
        if p == 0:
            continue
        for q in range(1, max_den + 1):
            rat = mp.mpf(p) / q
            diff = abs(val - rat * target)
            if diff == 0:
                digits = 999.0
            else:
                digits = float(-mp.log10(diff)) if diff > 0 else 999.0
            if digits > best_digits:
                frac = f"{p}/{q}" if q > 1 else str(p)
                best_name = f"{frac}*target"
                best_digits = digits
    return best_name, best_digits


def describe_relation(val: mp.mpf, dps: int = 110) -> dict[str, Any]:
    with mp.workdps(dps + 20):
        z3 = mp.zeta(3)
        pi2 = mp.pi ** 2
        targets = {
            "1/zeta3": 1 / z3,
            "zeta3": z3,
            "pi^2": pi2,
            "pi^2/zeta3": pi2 / z3,
            "zeta3/pi^2": z3 / pi2,
            "1": mp.mpf(1),
        }

        best = {"mode": "value", "formula": "(no match)", "digits": 0.0}
        for name, tgt in targets.items():
            form, digs = _best_rational_multiple(val, tgt)
            if digs > best["digits"]:
                best = {
                    "mode": "value",
                    "formula": form.replace("target", name),
                    "digits": round(digs, 3),
                }

        if val is not None and abs(val) > mp.mpf("1e-40"):
            inv = 1 / val
            for name, tgt in {"zeta3": z3, "pi^2": pi2, "1": mp.mpf(1)}.items():
                form, digs = _best_rational_multiple(inv, tgt)
                if digs > best["digits"]:
                    best = {
                        "mode": "inverse",
                        "formula": f"1/value = {form.replace('target', name)}",
                        "digits": round(digs, 3),
                    }

        # one PSLQ attempt for the inverse shell: c0*(1/v) + c1*zeta3 + c2*pi^2 + c3 = 0
        if val is not None and abs(val) > mp.mpf("1e-40"):
            inv = 1 / val
            rel = mp.pslq([inv, z3, pi2, mp.mpf(1)], maxcoeff=250)
            if rel is not None and rel[0] != 0:
                lhs = rel[1] * z3 + rel[2] * pi2 + rel[3]
                est = -lhs / rel[0]
                diff = abs(inv - est)
                digs = 999.0 if diff == 0 else float(-mp.log10(diff))
                if digs > best["digits"]:
                    parts = []
                    labels = ["1/value", "zeta3", "pi^2", "1"]
                    for c, lab in zip(rel, labels):
                        if c:
                            parts.append(f"{int(c)}*{lab}")
                    best = {
                        "mode": "pslq-inverse",
                        "formula": " + ".join(parts) + " = 0",
                        "digits": round(digs, 3),
                    }

        return best


def recurrence_coeffs(kind: str, a1: int, a2: int, b1: int, b2: int,
                      n: int, m: int) -> tuple[float, float, float]:
    n_f = float(n)
    m_f = float(m)
    if kind == "fixed_alpha":
        P = (n_f + 1.0) ** 3
        R = n_f ** 3
    else:
        P = (n_f + 1.0) ** 2 * (n_f + m_f + 1.0)
        R = (n_f ** 2) * (n_f + m_f)

    A = 17 + a1 * m_f + a2 * m_f * m_f
    B = 5 + b1 * m_f + b2 * m_f * m_f
    Q = -(2 * n_f + 1.0) * (A * n_f * n_f + A * n_f + B)
    return P, Q, R


def fit_intertwiner(kind: str, a1: int, a2: int, b1: int, b2: int) -> tuple[float, float, dict[str, list[str]]]:
    """Fit a low-degree numeric intertwiner shell by SVD and validate it."""
    # A(n,m), B(n,m), C(n,m) each use the same 5-term basis.
    def feats(nn: int, mm: int) -> list[float]:
        return [1.0, float(nn), float(mm), float(nn * mm), float(nn * nn)]

    rows: list[list[float]] = []
    for mm in range(0, 3):
        for nn in range(3, 12):
            Pn, Qn, Rn = recurrence_coeffs(kind, a1, a2, b1, b2, nn, mm)
            Pp, Qp, Rp = recurrence_coeffs(kind, a1, a2, b1, b2, nn, mm + 1)
            Pm2, Qm2, Rm2 = recurrence_coeffs(kind, a1, a2, b1, b2, nn - 2, mm)
            if abs(Pn) < 1e-14 or abs(Rm2) < 1e-14:
                continue

            # v_{n+1}
            coeff_un = -Qn / Pn
            coeff_um1 = -Rn / Pn
            fA_np1 = feats(nn + 1, mm)
            fB_np1 = feats(nn + 1, mm)
            fC_np1 = feats(nn + 1, mm)
            fA_n = feats(nn, mm)
            fB_n = feats(nn, mm)
            fC_n = feats(nn, mm)
            fA_nm1 = feats(nn - 1, mm)
            fB_nm1 = feats(nn - 1, mm)
            fC_nm1 = feats(nn - 1, mm)

            # u_{n-3} = -(P_{n-2}/R_{n-2}) u_{n-1} - (Q_{n-2}/R_{n-2}) u_{n-2}
            c_um1 = -Pm2 / Rm2
            c_um2 = -Qm2 / Rm2

            # coefficient of u_n
            row_un = [0.0] * 15
            for i, v in enumerate(fA_np1):
                row_un[i] += Pp * coeff_un * v
            for i, v in enumerate(fB_np1):
                row_un[5 + i] += Pp * v
            for i, v in enumerate(fA_n):
                row_un[i] += Qp * v
            rows.append(row_un)

            # coefficient of u_{n-1}
            row_um1 = [0.0] * 15
            for i, v in enumerate(fA_np1):
                row_um1[i] += Pp * coeff_um1 * v
            for i, v in enumerate(fC_np1):
                row_um1[10 + i] += Pp * v
            for i, v in enumerate(fB_n):
                row_um1[5 + i] += Qp * v
            for i, v in enumerate(fA_nm1):
                row_um1[i] += Rp * v
            for i, v in enumerate(fC_nm1):
                row_um1[10 + i] += Rp * c_um1 * v
            rows.append(row_um1)

            # coefficient of u_{n-2}
            row_um2 = [0.0] * 15
            for i, v in enumerate(fC_n):
                row_um2[10 + i] += Qp * v
            for i, v in enumerate(fB_nm1):
                row_um2[5 + i] += Rp * v
            for i, v in enumerate(fC_nm1):
                row_um2[10 + i] += Rp * c_um2 * v
            rows.append(row_um2)

    M = np.array(rows, dtype=float)
    _, _, vh = np.linalg.svd(M)
    coeff = vh[-1, :]
    coeff /= np.max(np.abs(coeff))

    def eval_shell(nn: int, mm: int) -> tuple[float, float, float]:
        f = np.array(feats(nn, mm), dtype=float)
        A = float(np.dot(coeff[0:5], f))
        B = float(np.dot(coeff[5:10], f))
        C = float(np.dot(coeff[10:15], f))
        return A, B, C

    residuals: list[float] = []
    for mm in range(0, 3):
        for nn in range(12, 20):
            Pn, Qn, Rn = recurrence_coeffs(kind, a1, a2, b1, b2, nn, mm)
            Pp, Qp, Rp = recurrence_coeffs(kind, a1, a2, b1, b2, nn, mm + 1)
            Pm2, Qm2, Rm2 = recurrence_coeffs(kind, a1, a2, b1, b2, nn - 2, mm)
            if abs(Pn) < 1e-14 or abs(Rm2) < 1e-14:
                continue
            A_np1, B_np1, C_np1 = eval_shell(nn + 1, mm)
            A_n, B_n, C_n = eval_shell(nn, mm)
            A_nm1, B_nm1, C_nm1 = eval_shell(nn - 1, mm)
            c_um1 = -Pm2 / Rm2
            c_um2 = -Qm2 / Rm2

            # residuals for basis coefficients u_n, u_{n-1}, u_{n-2}
            r1 = Pp * ((-Qn / Pn) * A_np1 + B_np1) + Qp * A_n
            r2 = Pp * ((-Rn / Pn) * A_np1 + C_np1) + Qp * B_n + Rp * (A_nm1 + c_um1 * C_nm1)
            r3 = Qp * C_n + Rp * (B_nm1 + c_um2 * C_nm1)

            scale = max(1.0, abs(Pp), abs(Qp), abs(Rp))
            residuals.extend([abs(r1) / scale, abs(r2) / scale, abs(r3) / scale])

    # rationalize the coefficients for display only
    syms = [sp.nsimplify(float(x), rational=True) for x in coeff]
    shell = {
        "A": [str(s) for s in syms[0:5]],
        "B": [str(s) for s in syms[5:10]],
        "C": [str(s) for s in syms[10:15]],
        "basis": ["1", "n", "m", "n*m", "n^2"],
    }
    return float(max(residuals)), float(np.median(residuals)), shell


def scan_one(kind: str, a1: int, a2: int, b1: int, b2: int,
             depth: int, dps: int) -> Candidate | None:
    relations = []
    digits = []
    for m in range(4):
        val = eval_pcf(kind, a1, a2, b1, b2, m, depth=depth, dps=dps)
        if val is None or not mp.isfinite(val):
            return None
        rel = describe_relation(val, dps=dps)
        rel["m"] = m
        rel["value"] = mp.nstr(val, 35)
        relations.append(rel)
        digits.append(float(rel["digits"]))

    # Prefer families that keep m=0 exact and stay identifiable for m=1..3.
    score = 2.0 * digits[0] + digits[1] + digits[2] + digits[3]
    return Candidate(kind, a1, a2, b1, b2, round(score, 3), relations)


def run_scan(kind: str, jobs: list[tuple[int, int, int, int]],
             depth: int, dps: int, workers: int) -> list[Candidate]:
    out: list[Candidate] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(scan_one, kind, a1, a2, b1, b2, depth, dps): (a1, a2, b1, b2)
            for (a1, a2, b1, b2) in jobs
        }
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            cand = fut.result()
            if cand is not None:
                # keep only families with at least a visible relation at m=1..3
                if sum(1 for r in cand.relations if r["digits"] >= 8.0) >= 2:
                    out.append(cand)
            if done % 250 == 0 or done == total:
                print(f"[{kind}] {done}/{total} scanned, kept={len(out)}", flush=True)
    out.sort(key=lambda c: (-c.score, c.family, c.a1, c.a2, c.b1, c.b2))
    return out


def build_jobs_linear() -> list[tuple[int, int, int, int]]:
    return [(a1, 0, b1, 0) for a1 in range(-20, 21) for b1 in range(-10, 11)]


def build_jobs_quadratic(seed_pairs: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    jobs = set()
    for a1, b1 in seed_pairs:
        for a2 in range(-3, 4):
            for b2 in range(-3, 4):
                jobs.add((a1, a2, b1, b2))
    return sorted(jobs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Search Apéry-template m-families for zeta(3)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--depth", type=int, default=1000)
    ap.add_argument("--dps", type=int, default=90)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--family", choices=["both", "fixed_alpha", "shifted_alpha"],
                    default="both")
    ap.add_argument("--linear-only", action="store_true",
                    help="Stop after the linear scan and intertwiner ranking")
    args = ap.parse_args()

    t0 = time.time()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("  Apéry-template one-parameter family scan")
    print("=" * 78)
    print(f"workers={args.workers} depth={args.depth} dps={args.dps}")

    families = ["fixed_alpha", "shifted_alpha"] if args.family == "both" else [args.family]

    linear_jobs = build_jobs_linear()
    linear_results: list[Candidate] = []
    for kind in families:
        print(f"\n--- Linear scan: {kind} ---")
        linear_results.extend(run_scan(kind, linear_jobs, args.depth, args.dps, args.workers))

    linear_results.sort(key=lambda c: -c.score)
    top_linear = linear_results[: max(12, args.top)]

    print("\nTop linear families:")
    for c in top_linear[:args.top]:
        print(f"  {c.family:13s} a1={c.a1:>3d} b1={c.b1:>3d}  score={c.score:8.2f}")
        for rel in c.relations:
            print(f"      m={rel['m']}: {rel['formula']}  [{rel['digits']} d]")

    quad_results: list[Candidate] = []
    if not args.linear_only:
        seed_pairs = sorted({(c.a1, c.b1) for c in top_linear})
        quad_jobs = build_jobs_quadratic(seed_pairs)
        for kind in families:
            print(f"\n--- Quadratic refinement: {kind} ({len(quad_jobs)} jobs) ---")
            quad_results.extend(run_scan(kind, quad_jobs, args.depth, args.dps, args.workers))

    all_results = linear_results + quad_results
    # Deduplicate by full parameter tuple, keep best score.
    best_map: dict[tuple[str, int, int, int, int], Candidate] = {}
    for c in all_results:
        key = (c.family, c.a1, c.a2, c.b1, c.b2)
        if key not in best_map or c.score > best_map[key].score:
            best_map[key] = c
    ranked = sorted(best_map.values(), key=lambda c: -c.score)

    # Intertwiner fit on the strongest few candidates.
    for c in ranked[:args.top]:
        try:
            mx, med, shell = fit_intertwiner(c.family, c.a1, c.a2, c.b1, c.b2)
            c.intertwiner_max_residual = mx
            c.intertwiner_med_residual = med
            c.intertwiner_coefficients = shell
        except Exception as exc:
            c.intertwiner_max_residual = math.inf
            c.intertwiner_med_residual = math.inf
            c.intertwiner_coefficients = {"error": [str(exc)]}

    ranked.sort(key=lambda c: (c.intertwiner_max_residual or math.inf, -c.score))

    print("\nBest candidates after intertwiner scoring:")
    for i, c in enumerate(ranked[:args.top], 1):
        print(f"\n[{i}] {c.family}  a1={c.a1} a2={c.a2} b1={c.b1} b2={c.b2}")
        print(f"    score={c.score}  intertwiner max residual={c.intertwiner_max_residual:.3e}")
        for rel in c.relations:
            print(f"    m={rel['m']}  value={rel['value']}")
            print(f"         {rel['formula']}  [{rel['digits']} d]")

    payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "workers": args.workers,
        "depth": args.depth,
        "dps": args.dps,
        "elapsed_s": round(time.time() - t0, 3),
        "ranked": [asdict(c) for c in ranked[:args.top]],
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nSaved report to {RESULT_PATH}")


if __name__ == "__main__":
    main()
