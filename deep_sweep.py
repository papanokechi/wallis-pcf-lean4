#!/usr/bin/env python3
"""Deep Sweep: High-order GCF discovery targeting frontier constants.

Implements the "Three Pillars of Transcendence" search:
  Pillar 1: High-order polynomial search (adeg≥4, bdeg≥4, 200+ digits)
  Pillar 2: Multi-constant PSLQ coupling (CF = Σ aᵢ·Kᵢ)
  Pillar 3: Architect-guided structural synthesis

Primary targets: ζ(5), ζ(3) deep, cross-constant relations.

Usage:
    python deep_sweep.py --target zeta5 --iters 20 --batch 32 --prec 500
    python deep_sweep.py --target zeta3 --iters 50 --batch 64 --prec 300 --deep
    python deep_sweep.py --targets zeta5,zeta3,pi --iters 10 --batch 32 --prec 500
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from siarc_ramanujan_adapter import RamanujanSearchSpec, run_ramanujan_search


def _parse_targets(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deep sweep: high-order GCF search for frontier constants.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--target", default=None, type=str,
                        help="Single target constant (e.g. zeta5, zeta3).")
    parser.add_argument("--targets", default=None, type=str,
                        help="Comma-separated targets for multi-target deep sweep.")
    parser.add_argument("--iters", type=int, default=20,
                        help="Search iterations per target.")
    parser.add_argument("--batch", type=int, default=32,
                        help="GCFs per iteration.")
    parser.add_argument("--prec", type=int, default=500,
                        help="Working precision (digits). 500 recommended for deep search.")
    parser.add_argument("--workers", type=int, default=0,
                        help="Parallel workers (0 = auto).")
    parser.add_argument("--executor", default="process",
                        choices=["process", "thread"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--seed-file", default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--deep", action="store_true", default=True,
                        help="Enable deep mode (high-order polynomials). On by default.")
    parser.add_argument("--no-deep", action="store_true",
                        help="Disable deep mode (standard search at high precision).")
    parser.add_argument("--json-out", default="deep_sweep_results.json")
    parser.add_argument("--csv-out", default="deep_sweep_results.csv")
    args = parser.parse_args()

    # Resolve targets
    if args.targets:
        targets = _parse_targets(args.targets)
    elif args.target:
        targets = [args.target]
    else:
        targets = ["zeta5"]

    deep_mode = not args.no_deep

    print("=" * 60)
    print("  Deep Sweep — Frontier GCF Discovery")
    print("=" * 60)
    print(f"  Targets:    {', '.join(targets)}")
    print(f"  Precision:  {args.prec} digits")
    print(f"  Deep mode:  {'ON' if deep_mode else 'OFF'}")
    print(f"  Iterations: {args.iters} × {args.batch} GCFs/iter")
    print()

    all_results: list[dict] = []
    total_discoveries = 0
    total_novel = 0
    t0 = time.perf_counter()

    for idx, target in enumerate(targets):
        search_seed = args.seed + idx if args.seed is not None else None
        print(f"── [{idx+1}/{len(targets)}] {target} (prec={args.prec}, deep={deep_mode}) ──")

        spec = RamanujanSearchSpec(
            target=target,
            iters=args.iters,
            batch=args.batch,
            prec=args.prec,
            workers=args.workers,
            executor=args.executor,
            quiet=args.quiet,
            seed=search_seed,
            seed_file=args.seed_file,
            deep_mode=deep_mode,
        )

        result = run_ramanujan_search(spec)
        discoveries = result.get("discoveries", [])
        summary = result.get("summary", {})
        stats = summary.get("stats", {})
        novel = int(stats.get("novel", 0) or 0)
        elapsed = float(stats.get("elapsed_seconds", 0.0) or 0.0)

        total_discoveries += len(discoveries)
        total_novel += novel

        # Flag high-value discoveries (multi-constant or high-order)
        high_value = []
        for d in discoveries:
            constant = d.get("constant", "")
            prec_dp = d.get("precision_dp", 0)
            spec_data = d.get("spec", {})
            alpha = spec_data.get("alpha", [])
            beta = spec_data.get("beta", [])
            is_deep = len(alpha) > 4 or len(beta) > 4
            is_multi = "+" in constant
            if is_deep or is_multi or prec_dp >= 200:
                high_value.append({
                    "constant": constant,
                    "precision": prec_dp,
                    "alpha": alpha,
                    "beta": beta,
                    "alpha_deg": len(alpha) - 1,
                    "beta_deg": len(beta) - 1,
                    "mode": spec_data.get("mode", "backward"),
                    "order": spec_data.get("order", 0),
                    "n_terms": spec_data.get("n_terms", 200),
                    "spec_id": spec_data.get("spec_id", ""),
                    "relation": d.get("relation", []),
                    "degree": d.get("degree", 0),
                    "formula": d.get("formula", ""),
                    "is_multi_constant": is_multi,
                    "cf_approx": d.get("cf_approx"),
                    "enrichment": d.get("enrichment", {}),
                })

        # Extract near-misses from the summary
        near_misses = summary.get("near_misses", [])

        entry = {
            "target": target,
            "seed": search_seed,
            "prec": args.prec,
            "deep_mode": deep_mode,
            "discovery_count": len(discoveries),
            "novel_count": novel,
            "high_value_count": len(high_value),
            "near_miss_count": len(near_misses),
            "elapsed_seconds": round(elapsed, 3),
            "high_value": high_value,
            "near_misses": near_misses,
        }
        all_results.append(entry)

        print(f"  discoveries={len(discoveries)}  novel={novel}  "
              f"high_value={len(high_value)}  near_misses={len(near_misses)}  "
              f"elapsed={elapsed:.1f}s")
        for hv in high_value[:5]:
            tag = " [MULTI-CONSTANT]" if hv["is_multi_constant"] else ""
            print(f"    ★ {hv['constant']}  deg=({hv['alpha_deg']},{hv['beta_deg']})  "
                  f"{hv['precision']}dp{tag}")
            print(f"      {hv['formula'][:80]}")
        if near_misses:
            top_nm = sorted(near_misses, key=lambda x: x.get("precision", 0),
                            reverse=True)[:5]
            print(f"  Near-misses (top {len(top_nm)}):")
            for nm in top_nm:
                tag = " [MULTI]" if nm.get("basis_type") == "multi" else ""
                print(f"    ~ {nm.get('constant','')}  {nm.get('precision',0)}dp  "
                      f"|  {nm.get('formula','')[:60]}{tag}")
        print()

    wall_seconds = round(time.perf_counter() - t0, 3)

    # Save results
    output = {
        "sweep": "deep_sweep",
        "targets": targets,
        "prec": args.prec,
        "deep_mode": deep_mode,
        "iters": args.iters,
        "batch": args.batch,
        "total_discoveries": total_discoveries,
        "total_novel": total_novel,
        "wall_seconds": wall_seconds,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": all_results,
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    if all_results:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            fields = ["target", "seed", "prec", "deep_mode", "discovery_count",
                      "novel_count", "high_value_count", "near_miss_count",
                      "elapsed_seconds"]
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_results)

    total_nm = sum(r.get("near_miss_count", 0) for r in all_results)
    print("=" * 60)
    print(f"  Total discoveries: {total_discoveries}")
    print(f"  Total novel:       {total_novel}")
    total_hv = sum(r["high_value_count"] for r in all_results)
    print(f"  High-value finds:  {total_hv}")
    print(f"  Near-misses:       {total_nm}")
    print(f"  Wall time:         {wall_seconds}s")
    print(f"  JSON -> {args.json_out}")
    print(f"  CSV  -> {args.csv_out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
