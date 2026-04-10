#!/usr/bin/env python3
"""(6,6) Hyper-Deep Pilot with Mutant Super-Seeds.

Runs a focused ζ(7)/ζ(9) strike using the 5 super-seeds extracted from
the mutant drift cluster analysis. These seeds encode the discrete
symmetry group of the GCF solution space and should outperform random
initialization at degree 6.

Gated on a >3% hit rate threshold to justify full (6,6) runs.

Usage:
    python run_zeta_66_pilot.py
    python run_zeta_66_pilot.py --targets zeta7,zeta5 --iters 20 --batch 64
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from siarc_ramanujan_adapter import RamanujanSearchSpec, run_ramanujan_search


def _escalate_seeds_to_degree6(super_seeds: list[dict],
                               targets: list[str]) -> list[dict]:
    """Escalate super-seeds to degree-6 by extending coefficient vectors.

    For each super-seed, generate degree-6 variants:
      - Pad alpha/beta to length 7 with small perturbations
      - Set mode to ratio with order=6 for zeta-like targets
      - Keep the structural DNA (core coefficients) from the super-seed
    """
    import random
    escalated = []
    for seed in super_seeds:
        alpha = list(seed.get("alpha", []))
        beta = list(seed.get("beta", []))
        mode = seed.get("mode", "backward")

        for target in targets:
            for variant in range(5):  # 5 variants per seed per target
                # Extend to degree 6
                a6 = list(alpha)
                b6 = list(beta)
                while len(a6) < 7:
                    a6.append(random.choice([-2, -1, 0, 0, 1, 2]))
                while len(b6) < 7:
                    b6.append(random.choice([-3, -2, -1, 0, 0, 1, 2, 3]))

                # Ensure leading coefficients are nonzero
                if a6[-1] == 0:
                    a6[-1] = random.choice([-1, 1])
                if b6[-1] == 0:
                    b6[-1] = random.choice([-1, 1])
                if b6[0] == 0 and mode == "backward":
                    b6[0] = random.choice([-1, 1])

                # For zeta targets, use ratio mode at order 6
                if target in ("zeta7", "zeta5", "zeta3", "zeta9"):
                    use_mode = "ratio" if random.random() < 0.7 else "backward"
                    use_order = 6 if use_mode == "ratio" else 0
                else:
                    use_mode = mode
                    use_order = seed.get("order", 0)

                # Small perturbation on core coefficients (variant noise)
                if variant > 0:
                    for i in range(min(len(alpha), len(a6))):
                        a6[i] += random.choice([-1, 0, 0, 0, 1])
                    for i in range(min(len(beta), len(b6))):
                        b6[i] += random.choice([-1, 0, 0, 0, 1])

                escalated.append({
                    "alpha": a6,
                    "beta": b6,
                    "target": target,
                    "n_terms": 600,
                    "mode": use_mode,
                    "order": use_order,
                    "spec_id": f"SS66_{seed.get('spec_id', 'X')}_{target}_{variant:02d}",
                    "_source_superseed": seed.get("spec_id", ""),
                })

    return escalated


def main():
    parser = argparse.ArgumentParser(
        description="(6,6) hyper-deep pilot with mutant super-seeds.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--targets", default="zeta7,zeta5",
                        help="Comma-separated targets.")
    parser.add_argument("--iters", type=int, default=15)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--prec", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--super-seeds", default="super_seeds.json")
    parser.add_argument("--json-out", default="pilot_66_results.json")
    parser.add_argument("--csv-out", default="pilot_66_results.csv")
    parser.add_argument("--hit-rate-threshold", type=float, default=3.0,
                        help="Minimum hit rate (%%) to green-light full (6,6).")
    args = parser.parse_args()

    targets = [t.strip() for t in args.targets.split(",")]

    # Load super-seeds
    ss_path = Path(args.super_seeds)
    if ss_path.exists():
        with open(ss_path) as f:
            super_seeds = json.load(f)
        print(f"  Loaded {len(super_seeds)} super-seeds from {ss_path}")
    else:
        print(f"  WARNING: {ss_path} not found, using empty seed set")
        super_seeds = []

    # Escalate seeds to degree 6
    escalated = _escalate_seeds_to_degree6(super_seeds, targets)
    print(f"  Escalated to {len(escalated)} degree-6 seed variants")

    # Save escalated seeds for the agent
    escalated_path = Path("_pilot_66_seeds.json")
    with open(escalated_path, "w") as f:
        json.dump(escalated, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  (6,6) Hyper-Deep Pilot — Super-Seed Strike")
    print(f"{'='*60}")
    print(f"  Targets:   {', '.join(targets)}")
    print(f"  Precision: {args.prec}dp")
    print(f"  Deep mode: ON")
    print(f"  Iters:     {args.iters} × {args.batch}")
    print()

    all_results = []
    total_tested = 0
    total_novel = 0
    t0 = time.perf_counter()

    for idx, target in enumerate(targets):
        search_seed = args.seed + idx if args.seed is not None else None
        print(f"── [{idx+1}/{len(targets)}] {target} (6,6 deep) ──")

        spec = RamanujanSearchSpec(
            target=target,
            iters=args.iters,
            batch=args.batch,
            prec=args.prec,
            workers=args.workers,
            executor="process",
            quiet=True,
            seed=search_seed,
            seed_file=str(escalated_path),
            deep_mode=True,
        )

        result = run_ramanujan_search(spec)
        summary = result.get("summary", {})
        stats = summary.get("stats", {})
        discoveries = result.get("discoveries", [])
        tested = int(stats.get("tested", 0) or 0)
        novel = int(stats.get("novel", 0) or 0)
        elapsed = float(stats.get("elapsed_seconds", 0) or 0)

        total_tested += tested
        total_novel += novel

        # Count deep hits (alpha or beta degree >= 6)
        deep_hits = 0
        for d in discoveries:
            spec_data = d.get("spec", {})
            adeg = len(spec_data.get("alpha", [])) - 1
            bdeg = len(spec_data.get("beta", [])) - 1
            if adeg >= 6 or bdeg >= 6:
                deep_hits += 1

        hit_rate = novel / tested * 100 if tested > 0 else 0.0

        entry = {
            "target": target,
            "tested": tested,
            "novel": novel,
            "deep_hits": deep_hits,
            "hit_rate_pct": round(hit_rate, 3),
            "elapsed_seconds": round(elapsed, 3),
        }
        all_results.append(entry)
        print(f"  tested={tested}  novel={novel}  deep(6,6)={deep_hits}  "
              f"rate={hit_rate:.2f}%  elapsed={elapsed:.1f}s")

    wall = round(time.perf_counter() - t0, 3)
    overall_rate = total_novel / total_tested * 100 if total_tested > 0 else 0.0

    # Green-light decision
    green_light = overall_rate >= args.hit_rate_threshold

    output = {
        "pilot": "66_superseed",
        "targets": targets,
        "prec": args.prec,
        "super_seeds_used": len(super_seeds),
        "escalated_seeds": len(escalated),
        "total_tested": total_tested,
        "total_novel": total_novel,
        "overall_hit_rate_pct": round(overall_rate, 3),
        "hit_rate_threshold_pct": args.hit_rate_threshold,
        "green_light_full_66": green_light,
        "per_target": all_results,
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    import csv as csvmod
    if all_results:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            writer = csvmod.DictWriter(f, fieldnames=list(all_results[0].keys()))
            writer.writeheader()
            writer.writerows(all_results)

    print(f"\n{'='*60}")
    print(f"  (6,6) Pilot Results")
    print(f"{'='*60}")
    print(f"  Overall hit rate: {overall_rate:.2f}%")
    print(f"  Threshold:        {args.hit_rate_threshold}%")
    print(f"  GREEN LIGHT:      {'YES — launch full (6,6)!' if green_light else 'NO — defer'}")
    print(f"  Wall time:        {wall}s")
    print(f"  JSON -> {args.json_out}")
    print(f"{'='*60}")

    # Cleanup tmp seed file
    try:
        escalated_path.unlink()
    except Exception:
        pass


if __name__ == "__main__":
    main()
