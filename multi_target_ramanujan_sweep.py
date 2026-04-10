#!/usr/bin/env python3
"""Phase 3 multi-target discovery sweep for the SIARC Ramanujan kernel.

Runs the optimized search kernel across a list of constants and aggregates
structural pattern signatures so shared GCF families are easy to spot.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from siarc_ramanujan_adapter import MultiTargetSweepSpec, run_multi_target_sweep


def _parse_targets(raw: str) -> list[str]:
    targets = [part.strip() for part in raw.split(",") if part.strip()]
    if not targets:
        raise argparse.ArgumentTypeError("Provide at least one target, e.g. zeta3,pi,e,log2")
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a multi-target Ramanujan discovery sweep and save aggregate artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--targets", default="zeta3,pi,e,log2", type=str,
                        help="Comma-separated target constants to sweep.")
    parser.add_argument("--iters", type=int, default=2,
                        help="Iterations per target run.")
    parser.add_argument("--batch", type=int, default=16,
                        help="Batch size per target run.")
    parser.add_argument("--prec", type=int, default=300,
                        help="Precision for each target run.")
    parser.add_argument("--workers", type=int, default=0,
                        help="Workers per target run (0 = auto heuristic).")
    parser.add_argument("--executor", default="process", choices=["process", "thread"],
                        help="Executor backend for each target run.")
    parser.add_argument("--seed", type=int, default=123,
                        help="Base seed; each target uses an offset from this value.")
    parser.add_argument("--seed-file", default=None,
                        help="Optional seed pool JSON to continue from a previous run.")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-target agent output.")
    parser.add_argument("--no-cross-pollinate", action="store_true",
                        help="Disable learned signature boosting between targets during the sweep.")
    parser.add_argument("--json-out", "--json", dest="json_out", default="multi_target_sweep.json",
                        help="Path for the JSON sweep artifact.")
    parser.add_argument("--csv-out", "--csv", dest="csv_out", default="multi_target_sweep.csv",
                        help="Path for the CSV summary artifact.")
    args = parser.parse_args()

    targets = _parse_targets(args.targets)
    spec = MultiTargetSweepSpec(
        targets=targets,
        iters=args.iters,
        batch=args.batch,
        prec=args.prec,
        workers=args.workers,
        executor=args.executor,
        quiet=args.quiet,
        seed=args.seed,
        seed_file=args.seed_file,
        cross_pollinate=not args.no_cross_pollinate,
    )

    t0 = time.perf_counter()
    result = run_multi_target_sweep(spec)
    wall_seconds = round(time.perf_counter() - t0, 3)
    result["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    result["wall_seconds"] = wall_seconds

    json_path = Path(args.json_out)
    csv_path = Path(args.csv_out)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "target",
                "seed",
                "discovery_count",
                "novel_count",
                "elapsed_seconds",
                "resolved_workers",
                "effective_batch",
                "persistent_promotions",
            ],
        )
        writer.writeheader()
        for entry in result.get("targets", []):
            summary = entry.get("summary", {})
            run_config = summary.get("run_config", {})
            writer.writerow({
                "target": entry.get("target"),
                "seed": entry.get("seed"),
                "discovery_count": entry.get("discovery_count"),
                "novel_count": entry.get("novel_count"),
                "elapsed_seconds": entry.get("elapsed_seconds"),
                "resolved_workers": run_config.get("resolved_workers"),
                "effective_batch": run_config.get("effective_batch"),
                "persistent_promotions": (summary.get("stats", {}) or {}).get("persistent_promotions"),
            })

    aggregate = result.get("aggregate", {})
    print("Multi-target sweep complete")
    print(f"  targets:          {', '.join(targets)}")
    print(f"  total discoveries:{aggregate.get('total_discoveries', 0)}")
    print(f"  total novel:      {aggregate.get('total_novel', 0)}")
    print(f"  shared patterns:  {aggregate.get('shared_pattern_count', 0)}")
    print(f"  wall time:        {wall_seconds}s")
    print(f"  JSON -> {json_path}")
    print(f"  CSV  -> {csv_path}")

    learned = (aggregate.get("learned_priority_map") or {})
    if learned:
        top_learned = sorted(learned.items(), key=lambda item: item[1], reverse=True)[:5]
        print("\nLearned priority map (top, merged):")
        for signature, weight in top_learned:
            print(f"  {signature}  ->  {weight:.2f}")

    learned_per_target = aggregate.get("learned_per_target") or {}
    for t, tmap in learned_per_target.items():
        if tmap:
            top = sorted(tmap.items(), key=lambda item: item[1], reverse=True)[:3]
            print(f"\n  [{t}] top learned:")
            for sig, w in top:
                print(f"    {sig}  ->  {w:.2f}")

    if result.get("shared_patterns"):
        print("\nShared structural patterns:")
        for row in result["shared_patterns"][:8]:
            example = row.get("example", {})
            print(
                f"  {row['signature']}  ::  {', '.join(row['targets'])}"
                f"  [example={example.get('spec_id')}]"
            )


if __name__ == "__main__":
    main()
