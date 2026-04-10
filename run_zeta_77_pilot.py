#!/usr/bin/env python3
"""(7,7) Hyper-Deep Pilot with v2 Super-Seeds.

Escalates the proven (6,6) super-seeds to degree 7 and runs a focused
pilot on ζ(7) and ζ(9) — the next frontier in odd zeta values.

Uses the v2 super-seeds extracted from the 40 deep-6 hits, which encode
the structural DNA of the highest-quality discoveries.

Gated on >2% hit rate to justify full (7,7) production.

Usage:
    python run_zeta_77_pilot.py
    python run_zeta_77_pilot.py --targets zeta7,zeta5 --iters 15 --batch 64
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


PRIORITY_77 = {
    "adeg=7|bdeg=7|mode=ratio|order=7": 9.0,
    "adeg=7|bdeg=6|mode=ratio|order=7": 7.0,
    "adeg=6|bdeg=7|mode=ratio|order=7": 7.0,
    "adeg=7|bdeg=5|mode=ratio|order=5": 5.0,
    "adeg=6|bdeg=6|mode=ratio|order=6": 4.5,
    "adeg=7|bdeg=4|mode=ratio|order=4": 3.5,
    "adeg=7|bdeg=3|mode=backward|order=0": 3.0,
}


def _escalate_to_deg7(seeds: list[dict], targets: list[str],
                      variants_per_seed: int = 6) -> list[dict]:
    """Escalate super-seeds to degree 7."""
    escalated = []
    for seed in seeds:
        alpha = list(seed.get("alpha", []))
        beta = list(seed.get("beta", []))
        mode = seed.get("mode", "backward")

        for target in targets:
            for v in range(variants_per_seed):
                a7 = list(alpha)
                b7 = list(beta)
                # Extend to degree 7 (8 coefficients)
                while len(a7) < 8:
                    a7.append(random.choice([-2, -1, 0, 0, 1, 2]))
                while len(b7) < 8:
                    b7.append(random.choice([-3, -2, -1, 0, 0, 1, 2, 3]))

                # Structural integrity
                if a7[-1] == 0:
                    a7[-1] = random.choice([-1, 1])
                if b7[-1] == 0:
                    b7[-1] = random.choice([-1, 1])
                if b7[0] == 0 and mode == "backward":
                    b7[0] = random.choice([-1, 1])

                # Variant perturbation
                if v > 0:
                    for i in range(len(a7)):
                        a7[i] += random.choice([-1, 0, 0, 0, 0, 1])
                    for i in range(len(b7)):
                        b7[i] += random.choice([-1, 0, 0, 0, 0, 1])

                # Mode selection: zeta targets heavily favour ratio mode
                if target.startswith("zeta"):
                    use_mode = "ratio" if random.random() < 0.75 else "backward"
                    use_order = 7 if use_mode == "ratio" else 0
                else:
                    use_mode = mode
                    use_order = 7 if use_mode == "ratio" else 0

                escalated.append({
                    "alpha": a7[:8], "beta": b7[:8], "target": target,
                    "n_terms": 700, "mode": use_mode, "order": use_order,
                    "spec_id": f"SS77_{seed.get('spec_id','X')}_{target}_{v:02d}",
                })

    return escalated


def main():
    parser = argparse.ArgumentParser(
        description="(7,7) hyper-deep pilot with v2 super-seeds.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--targets", default="zeta7,zeta5")
    parser.add_argument("--iters", type=int, default=12)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--prec", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=77)
    parser.add_argument("--super-seeds", default="super_seeds_v2.json",
                        help="V2 super-seeds (from mutant_harvester_66.py).")
    parser.add_argument("--json-out", default="pilot_77_results.json")
    parser.add_argument("--csv-out", default="pilot_77_results.csv")
    parser.add_argument("--hit-rate-threshold", type=float, default=2.0)
    args = parser.parse_args()

    targets = [t.strip() for t in args.targets.split(",")]
    random.seed(args.seed)

    # Load v2 super-seeds
    ss_path = Path(args.super_seeds)
    if ss_path.exists():
        with open(ss_path) as f:
            super_seeds = json.load(f)
        print(f"  Loaded {len(super_seeds)} v2 super-seeds")
    else:
        # Fallback to v1
        v1_path = Path("super_seeds.json")
        if v1_path.exists():
            with open(v1_path) as f:
                super_seeds = json.load(f)
            print(f"  Loaded {len(super_seeds)} v1 super-seeds (v2 not found)")
        else:
            print("  WARNING: No super-seeds found")
            super_seeds = []

    # Escalate to degree 7
    escalated = _escalate_to_deg7(super_seeds, targets)
    print(f"  Escalated to {len(escalated)} degree-7 seed variants")

    seed_path = Path("_pilot_77_seeds.json")
    with open(seed_path, "w") as f:
        json.dump(escalated, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  (7,7) Hyper-Deep Pilot")
    print(f"{'='*60}")
    print(f"  Targets:   {', '.join(targets)}")
    print(f"  Precision: {args.prec}dp")
    print(f"  Iters:     {args.iters} x {args.batch}")
    print()

    all_results = []
    total_tested = 0
    total_novel = 0
    total_deep7 = 0
    t0 = time.perf_counter()

    for idx, target in enumerate(targets):
        search_seed = args.seed + idx * 1000
        random.seed(search_seed)
        print(f"── [{idx+1}/{len(targets)}] {target} (7,7 deep) ──")

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
            priority_map=PRIORITY_77,
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

        deep7 = 0
        for d in discoveries:
            sd = d.get("spec", {})
            if len(sd.get("alpha", [])) - 1 >= 7 or len(sd.get("beta", [])) - 1 >= 7:
                deep7 += 1
        total_deep7 += deep7

        hit_rate = novel / tested * 100 if tested > 0 else 0.0
        entry = {
            "target": target,
            "tested": tested,
            "novel": novel,
            "deep7_hits": deep7,
            "hit_rate_pct": round(hit_rate, 3),
            "elapsed_seconds": round(elapsed, 3),
        }
        all_results.append(entry)
        print(f"  tested={tested}  novel={novel}  deep7={deep7}  "
              f"rate={hit_rate:.2f}%  elapsed={elapsed:.1f}s")

    wall = round(time.perf_counter() - t0, 3)
    overall_rate = total_novel / total_tested * 100 if total_tested > 0 else 0.0
    green_light = overall_rate >= args.hit_rate_threshold

    output = {
        "pilot": "77_superseed_v2",
        "targets": targets,
        "prec": args.prec,
        "super_seeds_used": len(super_seeds),
        "escalated_seeds": len(escalated),
        "total_tested": total_tested,
        "total_novel": total_novel,
        "total_deep7": total_deep7,
        "overall_hit_rate_pct": round(overall_rate, 3),
        "hit_rate_threshold_pct": args.hit_rate_threshold,
        "green_light_full_77": green_light,
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
    print(f"  (7,7) Pilot Results")
    print(f"{'='*60}")
    print(f"  Overall hit rate: {overall_rate:.2f}%")
    print(f"  Deep-7 hits:      {total_deep7}")
    print(f"  Threshold:        {args.hit_rate_threshold}%")
    print(f"  GREEN LIGHT:      {'YES' if green_light else 'NO — defer'}")
    print(f"  Wall time:        {wall}s")
    print(f"  JSON -> {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
