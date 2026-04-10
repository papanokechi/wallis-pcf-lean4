#!/usr/bin/env python3
"""(8,8) Hyper-Deep Pilot with v2 Super-Seeds.

Escalates the 23 v2 super-seeds (already at degree 8-9) to target
degree 8 and runs a focused pilot on ζ(9), ζ(7), and ζ(5).

The v2 seeds already contain 9-coefficient alpha/beta vectors from
the (6,6) mutant harvest, so escalation is minimal — mostly adding
perturbation variants and ensuring structural integrity.

Gated on >1.5% hit rate (lower threshold given higher degree).

Usage:
    python run_zeta_88_pilot.py
    python run_zeta_88_pilot.py --targets zeta7,zeta5 --iters 10 --batch 64
"""
from __future__ import annotations

import argparse
import json
import random
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


PRIORITY_88 = {
    "adeg=8|bdeg=8|mode=ratio|order=8": 9.0,
    "adeg=8|bdeg=7|mode=ratio|order=8": 7.0,
    "adeg=7|bdeg=8|mode=ratio|order=7": 7.0,
    "adeg=8|bdeg=6|mode=ratio|order=6": 5.0,
    "adeg=7|bdeg=7|mode=ratio|order=7": 5.0,
    "adeg=8|bdeg=5|mode=ratio|order=5": 4.0,
    "adeg=6|bdeg=6|mode=ratio|order=6": 3.0,
    "adeg=8|bdeg=3|mode=backward|order=0": 3.0,
}


def _escalate_to_deg8(seeds: list[dict], targets: list[str],
                      variants_per_seed: int = 5) -> list[dict]:
    """Escalate super-seeds to degree 8 (9 coefficients)."""
    escalated = []
    for seed in seeds:
        alpha = list(seed.get("alpha", []))
        beta = list(seed.get("beta", []))

        for target in targets:
            for v in range(variants_per_seed):
                a8 = list(alpha)
                b8 = list(beta)
                # Ensure at least 9 coefficients (degree 8)
                while len(a8) < 9:
                    a8.append(random.choice([-2, -1, 0, 0, 1, 2]))
                while len(b8) < 9:
                    b8.append(random.choice([-3, -2, -1, 0, 0, 1, 2, 3]))

                # Structural integrity
                if a8[-1] == 0:
                    a8[-1] = random.choice([-1, 1])
                if b8[-1] == 0:
                    b8[-1] = random.choice([-1, 1])
                if b8[0] == 0:
                    b8[0] = random.choice([-1, 1])

                # Variant perturbation
                if v > 0:
                    for i in range(len(a8)):
                        a8[i] += random.choice([-1, 0, 0, 0, 0, 0, 1])
                    for i in range(len(b8)):
                        b8[i] += random.choice([-1, 0, 0, 0, 0, 0, 1])

                # Mode: zeta targets → ratio at order 8
                if target.startswith("zeta"):
                    use_mode = "ratio" if random.random() < 0.8 else "backward"
                    use_order = 8 if use_mode == "ratio" else 0
                else:
                    use_mode = "backward"
                    use_order = 0

                escalated.append({
                    "alpha": a8[:9], "beta": b8[:9], "target": target,
                    "n_terms": 800, "mode": use_mode, "order": use_order,
                    "spec_id": f"SS88_{seed.get('spec_id','X')}_{target}_{v:02d}",
                })

    return escalated


def main():
    parser = argparse.ArgumentParser(
        description="(8,8) hyper-deep pilot with v2 super-seeds.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--targets", default="zeta7,zeta5,zeta3")
    parser.add_argument("--iters", type=int, default=8)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--prec", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=88)
    parser.add_argument("--super-seeds", default="super_seeds_v2.json")
    parser.add_argument("--json-out", default="pilot_88_results.json")
    parser.add_argument("--csv-out", default="pilot_88_results.csv")
    parser.add_argument("--hit-rate-threshold", type=float, default=1.5)
    args = parser.parse_args()

    targets = [t.strip() for t in args.targets.split(",")]
    random.seed(args.seed)

    # Load super-seeds
    ss_path = Path(args.super_seeds)
    if ss_path.exists():
        with open(ss_path) as f:
            super_seeds = json.load(f)
        print(f"  Loaded {len(super_seeds)} super-seeds from {ss_path}")
    else:
        print(f"  WARNING: {ss_path} not found")
        super_seeds = []

    # Escalate to degree 8
    escalated = _escalate_to_deg8(super_seeds, targets)
    print(f"  Escalated to {len(escalated)} degree-8 seed variants")

    seed_path = Path("_pilot_88_seeds.json")
    with open(seed_path, "w") as f:
        json.dump(escalated, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  (8,8) Hyper-Deep Pilot")
    print(f"{'='*60}")
    print(f"  Targets:   {', '.join(targets)}")
    print(f"  Precision: {args.prec}dp")
    print(f"  Iters:     {args.iters} x {args.batch}")
    print()

    all_results = []
    total_tested = 0
    total_novel = 0
    total_deep8 = 0
    t0 = time.perf_counter()

    for idx, target in enumerate(targets):
        search_seed = args.seed + idx * 1000
        random.seed(search_seed)
        print(f"── [{idx+1}/{len(targets)}] {target} (8,8 deep) ──")

        spec = RamanujanSearchSpec(
            target=target,
            iters=args.iters,
            batch=args.batch,
            prec=args.prec,
            workers=args.workers,
            executor="process",
            quiet=True,
            seed=search_seed,
            seed_file=str(seed_path),
            deep_mode=True,
            priority_map=PRIORITY_88,
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

        deep8 = 0
        for d in discoveries:
            sd = d.get("spec", {})
            if len(sd.get("alpha", [])) - 1 >= 8 or len(sd.get("beta", [])) - 1 >= 8:
                deep8 += 1
        total_deep8 += deep8

        hit_rate = novel / tested * 100 if tested > 0 else 0.0
        entry = {
            "target": target,
            "tested": tested,
            "novel": novel,
            "deep8_hits": deep8,
            "hit_rate_pct": round(hit_rate, 3),
            "elapsed_seconds": round(elapsed, 3),
        }
        all_results.append(entry)
        print(f"  tested={tested}  novel={novel}  deep8={deep8}  "
              f"rate={hit_rate:.2f}%  elapsed={elapsed:.1f}s")

    wall = round(time.perf_counter() - t0, 3)
    overall_rate = total_novel / total_tested * 100 if total_tested > 0 else 0.0
    green_light = overall_rate >= args.hit_rate_threshold

    output = {
        "pilot": "88_superseed_v2",
        "targets": targets,
        "prec": args.prec,
        "super_seeds_used": len(super_seeds),
        "escalated_seeds": len(escalated),
        "total_tested": total_tested,
        "total_novel": total_novel,
        "total_deep8": total_deep8,
        "overall_hit_rate_pct": round(overall_rate, 3),
        "hit_rate_threshold_pct": args.hit_rate_threshold,
        "green_light_full_88": green_light,
        "per_target": all_results,
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    import csv
    if all_results:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            writer.writeheader()
            writer.writerows(all_results)

    try:
        seed_path.unlink()
    except Exception:
        pass

    print(f"\n{'='*60}")
    print(f"  (8,8) Pilot Results")
    print(f"{'='*60}")
    print(f"  Overall hit rate: {overall_rate:.2f}%")
    print(f"  Deep-8 hits:      {total_deep8}")
    print(f"  Threshold:        {args.hit_rate_threshold}%")
    print(f"  GREEN LIGHT:      {'YES' if green_light else 'NO — defer'}")
    print(f"  Wall time:        {wall}s")
    print(f"  JSON -> {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
