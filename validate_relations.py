#!/usr/bin/env python3
"""Validate and triage Ramanujan agent discoveries at multiple precisions.

For each discovery from a sweep, this script:
  1. Recomputes the GCF value at the original and higher precisions
  2. Re-evaluates the PSLQ relation residual at each precision level
  3. Checks coefficient stability (same relation found at higher prec?)
  4. Verifies asymptotic convergence rate for deep discoveries
  5. Compares discovered specs against seed templates ("mutant harvest")

Output: ranked CSV + JSON with stability grades and diagnostics.

Usage:
    python validate_relations.py --input ultima_sweep_results.json
    python validate_relations.py --input ultima_sweep_results.json --seeds kloosterman_seeds.json
    python validate_relations.py --input deep_sweep_zeta5_full.json --prec-levels 1200,1500
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import mpmath as mp

# Ensure Unicode output on Windows
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _build_constants(dps: int = 1500) -> dict[str, mp.mpf]:
    """Build constants at given precision."""
    with mp.workdps(dps):
        c = {}
        c["pi"] = mp.pi; c["e"] = mp.e
        c["phi"] = (1 + mp.sqrt(5)) / 2
        c["sqrt2"] = mp.sqrt(2); c["sqrt3"] = mp.sqrt(3)
        c["log2"] = mp.log(2); c["log3"] = mp.log(3)
        c["zeta2"] = mp.zeta(2); c["zeta3"] = mp.zeta(3)
        c["zeta4"] = mp.zeta(4); c["zeta5"] = mp.zeta(5)
        c["zeta6"] = mp.zeta(6); c["zeta7"] = mp.zeta(7)
        c["catalan"] = mp.catalan; c["euler_g"] = mp.euler
        c["ln_pi"] = mp.log(mp.pi)
        c["pi2"] = mp.pi**2; c["pi3"] = mp.pi**3
        c["pi5"] = mp.pi**5; c["pi7"] = mp.pi**7
        c["e2"] = mp.e**2
    return c


def _eval_backward(alpha: list[int], beta: list[int], n_terms: int,
                   dps: int) -> mp.mpf | None:
    """Evaluate backward CF at given precision."""
    with mp.workdps(dps):
        val = mp.mpf(0)
        tol = mp.mpf(10) ** -(dps - 10)
        for n in range(n_terms, 0, -1):
            an = sum(c * mp.mpf(n)**i for i, c in enumerate(alpha))
            bn = sum(c * mp.mpf(n)**i for i, c in enumerate(beta))
            denom = bn + val
            if abs(denom) < tol:
                return None
            val = an / denom
        b0 = sum(c * mp.mpf(0)**i for i, c in enumerate(beta))
        return b0 + val


def _eval_ratio(alpha: list[int], beta: list[int], n_terms: int,
                order: int, dps: int) -> mp.mpf | None:
    """Evaluate ratio-mode CF at given precision."""
    with mp.workdps(dps):
        a0 = sum(c * mp.mpf(0)**i for i, c in enumerate(alpha))
        b0 = sum(c * mp.mpf(0)**i for i, c in enumerate(beta))
        p_prev, p_curr = mp.mpf(a0), mp.mpf(b0)
        q_prev, q_curr = mp.mpf(1), mp.mpf(1)
        tol = mp.mpf(10) ** -(dps - 10)
        for n in range(1, n_terms + 1):
            bn = sum(c * mp.mpf(n)**i for i, c in enumerate(beta))
            an = sum(c * mp.mpf(n)**i for i, c in enumerate(alpha))
            div = mp.mpf(n ** order) if order > 0 else mp.mpf(1)
            if abs(div) < tol:
                return None
            p_next = (bn * p_curr - an * p_prev) / div
            q_next = (bn * q_curr - an * q_prev) / div
            p_prev, p_curr = p_curr, p_next
            q_prev, q_curr = q_curr, q_next
        if abs(q_curr) < tol:
            return None
        return p_curr / q_curr


def _eval_gcf(entry: dict, n_terms: int, dps: int) -> mp.mpf | None:
    """Evaluate a GCF from its spec dict."""
    alpha = entry.get("alpha", [])
    beta = entry.get("beta", [])
    mode = entry.get("mode", "backward")
    order = entry.get("order", 0)
    if not alpha or not beta:
        return None
    if mode == "ratio":
        return _eval_ratio(alpha, beta, n_terms, order, dps)
    return _eval_backward(alpha, beta, n_terms, dps)


def _compute_residual(cf_value: mp.mpf, constant_name: str, relation: list[int],
                      degree: int, constants: dict[str, mp.mpf]) -> float:
    """Compute |residual| for a relation at given precision."""
    if "+" in constant_name:
        # Multi-constant: rel = [a_cf, a_K1, a_K2, ..., a_const]
        names = constant_name.split("+")
        res = relation[0] * cf_value
        for i, name in enumerate(names):
            K = constants.get(name, mp.mpf(0))
            res += relation[i + 1] * K
        res += relation[-1]
    elif degree == 1 and len(relation) == 3:
        K = constants.get(constant_name, mp.mpf(0))
        res = relation[0] * cf_value + relation[1] * K + relation[2]
    elif degree == 2 and len(relation) == 6:
        K = constants.get(constant_name, mp.mpf(0))
        res = (relation[0] * cf_value**2 + relation[1] * cf_value * K
               + relation[2] * K**2 + relation[3] * cf_value
               + relation[4] * K + relation[5])
    else:
        return float("inf")
    return float(abs(res))


def _residual_to_digits(res: float, dps: int) -> int:
    """Convert residual to digit count."""
    if res == 0:
        return dps
    return max(0, int(-math.log10(res + 10**(-(dps - 2)))))


def _convergence_check(entry: dict, n_values: list[int],
                       dps: int) -> list[dict]:
    """Check asymptotic convergence at multiple n_terms values."""
    results = []
    base_val = _eval_gcf(entry, entry.get("n_terms", 500), dps)
    if base_val is None:
        return results
    for n in n_values:
        val = _eval_gcf(entry, n, dps)
        if val is None:
            results.append({"n_terms": n, "converged": False})
            continue
        diff = float(abs(val - base_val))
        digits = _residual_to_digits(diff, dps) if diff > 0 else dps
        results.append({"n_terms": n, "converged": True, "diff_digits": digits})
    return results


def _seed_distance(entry: dict, seeds: list[dict]) -> dict:
    """Find the closest Kloosterman seed and compute coefficient drift."""
    alpha = entry.get("alpha", [])
    beta = entry.get("beta", [])
    mode = entry.get("mode", "backward")

    best_dist = float("inf")
    best_seed = None
    for seed in seeds:
        sa = seed.get("alpha", [])
        sb = seed.get("beta", [])
        # Allow cross-mode and cross-degree comparison with penalty
        mode_penalty = 0.0 if seed.get("mode") == mode else 0.5
        deg_penalty = (abs(len(sa) - len(alpha)) + abs(len(sb) - len(beta))) * 0.3

        # Pad shorter to match longer
        max_a = max(len(alpha), len(sa))
        max_b = max(len(beta), len(sb))
        pa = list(alpha) + [0] * (max_a - len(alpha))
        psa = list(sa) + [0] * (max_a - len(sa))
        pb = list(beta) + [0] * (max_b - len(beta))
        psb = list(sb) + [0] * (max_b - len(sb))

        a_dist = sum(abs(a - s) for a, s in zip(pa, psa))
        b_dist = sum(abs(b - s) for b, s in zip(pb, psb))
        a_norm = max(1, sum(abs(s) for s in psa))
        b_norm = max(1, sum(abs(s) for s in psb))
        dist = (a_dist / a_norm + b_dist / b_norm) / 2 + mode_penalty + deg_penalty
        if dist < best_dist:
            best_dist = dist
            best_seed = seed

    return {
        "nearest_seed_id": best_seed.get("spec_id", "") if best_seed else "",
        "coefficient_drift": round(best_dist, 4),
        "is_mutant": best_dist > 0.5,  # >50% drift
    }


def validate_discoveries(input_path: str, seeds_path: str | None = None,
                         prec_levels: list[int] | None = None,
                         max_entries: int = 100) -> dict:
    """Main validation pipeline."""
    prec_levels = prec_levels or [1200, 1500]
    max_prec = max(prec_levels) + 100
    constants = _build_constants(max_prec)

    # Load seeds for mutant harvest
    seeds: list[dict] = []
    if seeds_path and Path(seeds_path).exists():
        with open(seeds_path) as f:
            seeds = json.load(f)

    # Load discoveries
    with open(input_path) as f:
        data = json.load(f)

    entries: list[dict] = []
    for result in data.get("results", []):
        for hv in result.get("high_value", []):
            if hv.get("alpha"):  # Has full spec data
                hv["_target"] = result.get("target", "")
                entries.append(hv)

    if not entries:
        print("No entries with full spec data found. Re-run deep_sweep to populate.")
        return {"validated": [], "summary": {"total": 0}}

    entries = entries[:max_entries]
    original_prec = data.get("prec", 1000)

    print(f"Validating {len(entries)} discoveries at prec={prec_levels}")
    validated: list[dict] = []

    for idx, entry in enumerate(entries):
        constant = entry.get("constant", "")
        relation = entry.get("relation", [])
        degree = entry.get("degree", 0)
        orig_prec_dp = entry.get("precision", 0)
        n_terms = entry.get("n_terms", 500)

        record = {
            "index": idx,
            "spec_id": entry.get("spec_id", ""),
            "constant": constant,
            "formula": entry.get("formula", ""),
            "degree": degree,
            "alpha_deg": entry.get("alpha_deg", 0),
            "beta_deg": entry.get("beta_deg", 0),
            "original_precision": orig_prec_dp,
            "max_coeff": max(abs(c) for c in relation) if relation else 0,
            "is_deep": entry.get("alpha_deg", 0) >= 4 or entry.get("beta_deg", 0) >= 4,
            "is_multi": entry.get("is_multi_constant", False),
        }

        # Multi-precision residual check
        residuals = {}
        cf_values = {}
        for prec in [original_prec] + prec_levels:
            cf_val = _eval_gcf(entry, n_terms, prec)
            if cf_val is None:
                residuals[prec] = float("inf")
                continue
            cf_values[prec] = cf_val
            with mp.workdps(prec):
                res = _compute_residual(cf_val, constant, relation, degree, constants)
            residuals[prec] = res

        record["residuals"] = {str(p): _residual_to_digits(r, p)
                               for p, r in residuals.items()}

        # Stability grade
        stable_at = [p for p, r in residuals.items()
                     if _residual_to_digits(r, p) >= orig_prec_dp * 0.8]
        if len(stable_at) == len(residuals):
            record["grade"] = "A"  # Stable at all precisions
        elif len(stable_at) >= 2:
            record["grade"] = "B"  # Mostly stable
        elif len(stable_at) >= 1:
            record["grade"] = "C"  # Marginal
        else:
            record["grade"] = "F"  # Failed validation

        # Asymptotic check for deep discoveries
        if record["is_deep"] and cf_values:
            asym = _convergence_check(entry, [1000, 2000, 3000], original_prec)
            record["asymptotic"] = asym

        # Mutant harvest
        if seeds:
            seed_info = _seed_distance(entry, seeds)
            record.update(seed_info)

        validated.append(record)

        if (idx + 1) % 20 == 0:
            print(f"  ... validated {idx + 1}/{len(entries)}")

    # Summary statistics
    grades = defaultdict(int)
    for v in validated:
        grades[v["grade"]] += 1
    mutant_count = sum(1 for v in validated if v.get("is_mutant", False))
    deep_count = sum(1 for v in validated if v["is_deep"])

    summary = {
        "total": len(validated),
        "grades": dict(grades),
        "deep_count": deep_count,
        "mutant_count": mutant_count,
        "prec_levels_tested": [original_prec] + prec_levels,
    }

    return {"validated": validated, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and triage Ramanujan discoveries at multiple precisions.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", "-i", default="ultima_sweep_results.json",
                        help="Input JSON from deep_sweep.py.")
    parser.add_argument("--seeds", "-s", default="kloosterman_seeds.json",
                        help="Kloosterman seed pool for mutant harvest.")
    parser.add_argument("--prec-levels", default="1200,1500",
                        help="Comma-separated higher precision levels to test.")
    parser.add_argument("--max-entries", type=int, default=100,
                        help="Maximum discoveries to validate.")
    parser.add_argument("--json-out", default="validation_results.json")
    parser.add_argument("--csv-out", default="validation_results.csv")
    args = parser.parse_args()

    prec_levels = [int(p.strip()) for p in args.prec_levels.split(",")]
    seeds_path = args.seeds if Path(args.seeds).exists() else None

    t0 = time.perf_counter()
    result = validate_discoveries(
        input_path=args.input,
        seeds_path=seeds_path,
        prec_levels=prec_levels,
        max_entries=args.max_entries,
    )
    wall = round(time.perf_counter() - t0, 3)

    validated = result["validated"]
    summary = result["summary"]

    # Save JSON
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Save CSV
    if validated:
        csv_fields = ["index", "spec_id", "constant", "formula", "degree",
                      "alpha_deg", "beta_deg", "original_precision", "max_coeff",
                      "is_deep", "is_multi", "grade", "nearest_seed_id",
                      "coefficient_drift", "is_mutant"]
        # Add residual columns
        for p in [summary["prec_levels_tested"][0]] + prec_levels:
            csv_fields.append(f"residual_{p}dp")

        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            for v in validated:
                row = dict(v)
                for p_str, digits in v.get("residuals", {}).items():
                    row[f"residual_{p_str}dp"] = digits
                writer.writerow(row)

    # Print report
    print(f"\n{'='*60}")
    print(f"  Validation Report")
    print(f"{'='*60}")
    print(f"  Total validated:   {summary['total']}")
    print(f"  Grades:            {summary['grades']}")
    print(f"  Deep discoveries:  {summary['deep_count']}")
    print(f"  Mutants (>50%):    {summary['mutant_count']}")
    print(f"  Wall time:         {wall}s")
    print(f"  JSON -> {args.json_out}")
    print(f"  CSV  -> {args.csv_out}")

    # Top discoveries by grade
    a_grade = [v for v in validated if v["grade"] == "A"]
    if a_grade:
        print(f"\n  Grade A discoveries ({len(a_grade)}):")
        for v in a_grade[:10]:
            mut = " [MUTANT]" if v.get("is_mutant") else ""
            deep = " [DEEP]" if v["is_deep"] else ""
            print(f"    {v['constant']}  {v['original_precision']}dp  "
                  f"coeff={v['max_coeff']}{deep}{mut}")
            print(f"      {v['formula'][:70]}")

    # Mutant harvest
    mutants = [v for v in validated if v.get("is_mutant")]
    if mutants:
        print(f"\n  Mutant Harvest ({len(mutants)} evolutionary leaps):")
        for v in mutants[:10]:
            print(f"    {v['spec_id']}  drift={v['coefficient_drift']:.2f}  "
                  f"from {v['nearest_seed_id']}")

    print(f"{'='*60}")


if __name__ == "__main__":
    main()
