#!/usr/bin/env python3
"""Full (6,6) Production Sweep — Super-Seeds + Atkin-Lehner Conductors.

Scales the green-lit (6,6) pilot to a full production run across
ζ(5), ζ(7), and ζ(3) using three seed channels:
  1. Mutant super-seeds (5 cluster centroids, escalated to degree 6)
  2. Atkin-Lehner conductor templates (W₂ and W₃ at N=24)
  3. Best (6,6) discoveries from the pilot as relay seeds

Outputs a pipeline-ready JSON with full discovery specs for
validate_relations.py and catalog integration.

Usage:
    python run_zeta_66_full.py
    python run_zeta_66_full.py --targets zeta5,zeta7 --iters 30 --batch 128 --prec 1000
"""
from __future__ import annotations

import argparse
import csv
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


def _load_json(path: str) -> list | dict:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return []


def _build_seed_pool(super_seeds_path: str, symmetry_path: str,
                     pilot_path: str, targets: list[str]) -> list[dict]:
    """Merge super-seeds, Atkin-Lehner candidates, and pilot discoveries."""
    pool: list[dict] = []
    seen: set[str] = set()

    def _add(spec: dict):
        fp = str(spec.get("alpha", [])) + str(spec.get("beta", []))
        if fp in seen:
            return
        seen.add(fp)
        pool.append(spec)

    # Channel 1: Super-seeds escalated to degree 6
    super_seeds = _load_json(super_seeds_path)
    if isinstance(super_seeds, list):
        for seed in super_seeds:
            for target in targets:
                for variant in range(8):
                    alpha = list(seed.get("alpha", []))
                    beta = list(seed.get("beta", []))
                    # Extend to degree 6+
                    while len(alpha) < 7:
                        alpha.append(random.choice([-2, -1, 0, 0, 1, 2]))
                    while len(beta) < 7:
                        beta.append(random.choice([-3, -2, -1, 0, 0, 1, 2, 3]))
                    if alpha[-1] == 0:
                        alpha[-1] = random.choice([-1, 1])
                    if beta[-1] == 0:
                        beta[-1] = random.choice([-1, 1])
                    if variant > 0:
                        for i in range(len(alpha)):
                            alpha[i] += random.choice([-1, 0, 0, 0, 1])
                        for i in range(len(beta)):
                            beta[i] += random.choice([-1, 0, 0, 0, 1])

                    use_mode = "ratio" if target.startswith("zeta") and random.random() < 0.7 else "backward"
                    _add({
                        "alpha": alpha, "beta": beta, "target": target,
                        "n_terms": 600, "mode": use_mode,
                        "order": 6 if use_mode == "ratio" else 0,
                        "spec_id": f"SS66_{seed.get('spec_id', 'X')}_{target}_{variant:02d}",
                    })

    # Channel 2: Atkin-Lehner conductor templates from symmetry analysis
    sym = _load_json(symmetry_path)
    if isinstance(sym, dict):
        for cl_result in sym.get("cluster_results", []):
            al_candidates = cl_result.get("atkin_lehner_candidates", [])
            transforms = cl_result.get("transforms", [])
            for transform in transforms[:5]:  # Top 5 per cluster
                for target in targets:
                    alpha = list(transform.get("discovery_alpha", []))
                    beta = list(transform.get("discovery_beta", []))
                    while len(alpha) < 7:
                        alpha.append(random.choice([-1, 0, 0, 1]))
                    while len(beta) < 7:
                        beta.append(random.choice([-2, -1, 0, 0, 1, 2]))
                    if alpha[-1] == 0:
                        alpha[-1] = random.choice([-1, 1])
                    if beta[-1] == 0:
                        beta[-1] = random.choice([-1, 1])

                    use_mode = "ratio" if target.startswith("zeta") and random.random() < 0.6 else "backward"
                    _add({
                        "alpha": alpha[:7], "beta": beta[:7], "target": target,
                        "n_terms": 600, "mode": use_mode,
                        "order": 6 if use_mode == "ratio" else 0,
                        "spec_id": f"AL_{transform.get('spec_id', 'X')}_{target}",
                    })

    # Channel 3: Relay from pilot discoveries
    pilot = _load_json(pilot_path)
    if isinstance(pilot, dict):
        for per_target in pilot.get("per_target", []):
            for d in (per_target.get("discoveries") or [])[:5]:
                spec = d.get("spec", {})
                if spec.get("alpha"):
                    for target in targets:
                        _add({
                            "alpha": spec["alpha"], "beta": spec["beta"],
                            "target": target,
                            "n_terms": spec.get("n_terms", 600),
                            "mode": spec.get("mode", "backward"),
                            "order": spec.get("order", 0),
                            "spec_id": f"RELAY_{spec.get('spec_id', 'X')}_{target}",
                        })
    elif isinstance(pilot, list):
        # Handle list-format pilot results
        for entry in pilot:
            for d in (entry.get("discovery_details") or [])[:5]:
                spec = d.get("spec", {})
                if spec.get("alpha"):
                    for target in targets:
                        _add({
                            "alpha": spec["alpha"], "beta": spec["beta"],
                            "target": target,
                            "n_terms": spec.get("n_terms", 600),
                            "mode": spec.get("mode", "backward"),
                            "order": spec.get("order", 0),
                            "spec_id": f"RELAY_{spec.get('spec_id', 'X')}_{target}",
                        })

    return pool


# Priority map tuned for (6,6) deep search
PRIORITY_66 = {
    "adeg=6|bdeg=6|mode=ratio|order=6": 8.0,
    "adeg=5|bdeg=5|mode=ratio|order=5": 6.0,
    "adeg=6|bdeg=5|mode=ratio|order=5": 5.0,
    "adeg=6|bdeg=3|mode=ratio|order=3": 4.5,
    "adeg=5|bdeg=3|mode=backward|order=0": 3.5,
    "adeg=4|bdeg=4|mode=ratio|order=4": 3.0,
    "adeg=6|bdeg=4|mode=ratio|order=4": 3.0,
}


def main():
    parser = argparse.ArgumentParser(
        description="Full (6,6) production sweep with super-seeds + Atkin-Lehner.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--targets", default="zeta5,zeta7,zeta3")
    parser.add_argument("--iters", type=int, default=25)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--prec", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--super-seeds", default="super_seeds.json")
    parser.add_argument("--symmetry", default="symmetry_analysis.json")
    parser.add_argument("--pilot", default="pilot_66_results.json")
    parser.add_argument("--json-out", default="zeta66_full_results.json")
    parser.add_argument("--csv-out", default="zeta66_full_results.csv")
    args = parser.parse_args()

    targets = [t.strip() for t in args.targets.split(",")]
    random.seed(args.seed)

    # Build merged seed pool
    print("Building merged seed pool...")
    seed_pool = _build_seed_pool(args.super_seeds, args.symmetry,
                                  args.pilot, targets)
    seed_path = Path("_zeta66_full_seeds.json")
    with open(seed_path, "w") as f:
        json.dump(seed_pool, f, indent=2)
    print(f"  Pool: {len(seed_pool)} seeds")

    print(f"\n{'='*60}")
    print(f"  Full (6,6) Production Sweep")
    print(f"{'='*60}")
    print(f"  Targets:   {', '.join(targets)}")
    print(f"  Precision: {args.prec}dp")
    print(f"  Iters:     {args.iters} x {args.batch}")
    print(f"  Seeds:     {len(seed_pool)}")
    print()

    all_results = []
    total_tested = 0
    total_novel = 0
    total_deep6 = 0
    all_discoveries = []
    t0 = time.perf_counter()

    for idx, target in enumerate(targets):
        search_seed = args.seed + idx * 1000
        random.seed(search_seed)
        print(f"── [{idx+1}/{len(targets)}] {target} ──")

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
            priority_map=PRIORITY_66,
        )

        result = run_ramanujan_search(spec)
        summary = result.get("summary", {})
        stats = summary.get("stats", {})
        discoveries = result.get("discoveries", [])
        near_misses = summary.get("near_misses", [])
        tested = int(stats.get("tested", 0) or 0)
        novel = int(stats.get("novel", 0) or 0)
        elapsed = float(stats.get("elapsed_seconds", 0) or 0)

        total_tested += tested
        total_novel += novel

        # Count deep-6 hits
        deep6 = 0
        high_value = []
        for d in discoveries:
            sd = d.get("spec", {})
            adeg = len(sd.get("alpha", [])) - 1
            bdeg = len(sd.get("beta", [])) - 1
            if adeg >= 6 or bdeg >= 6:
                deep6 += 1
            # Store full spec for pipeline
            high_value.append({
                "constant": d.get("constant", ""),
                "precision": d.get("precision_dp", 0),
                "alpha": sd.get("alpha", []),
                "beta": sd.get("beta", []),
                "alpha_deg": adeg,
                "beta_deg": bdeg,
                "mode": sd.get("mode", "backward"),
                "order": sd.get("order", 0),
                "n_terms": sd.get("n_terms", 600),
                "spec_id": sd.get("spec_id", ""),
                "relation": d.get("relation", []),
                "degree": d.get("degree", 0),
                "formula": d.get("formula", ""),
                "is_multi_constant": "+" in d.get("constant", ""),
                "cf_approx": d.get("cf_approx"),
                "enrichment": d.get("enrichment", {}),
            })

        total_deep6 += deep6
        all_discoveries.extend(high_value)
        hit_rate = novel / tested * 100 if tested > 0 else 0.0

        entry = {
            "target": target,
            "tested": tested,
            "novel": novel,
            "deep6_hits": deep6,
            "hit_rate_pct": round(hit_rate, 3),
            "near_miss_count": len(near_misses),
            "elapsed_seconds": round(elapsed, 3),
            "high_value": high_value,
            "near_misses": near_misses,
        }
        all_results.append(entry)
        print(f"  tested={tested}  novel={novel}  deep6={deep6}  "
              f"rate={hit_rate:.2f}%  nm={len(near_misses)}  elapsed={elapsed:.1f}s")

    wall = round(time.perf_counter() - t0, 3)
    overall_rate = total_novel / total_tested * 100 if total_tested > 0 else 0.0

    output = {
        "sweep": "zeta66_full",
        "targets": targets,
        "prec": args.prec,
        "iters": args.iters,
        "batch": args.batch,
        "seed_pool_size": len(seed_pool),
        "total_tested": total_tested,
        "total_novel": total_novel,
        "total_deep6": total_deep6,
        "overall_hit_rate_pct": round(overall_rate, 3),
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": all_results,
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    if all_results:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            fields = ["target", "tested", "novel", "deep6_hits",
                      "hit_rate_pct", "near_miss_count", "elapsed_seconds"]
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_results)

    # Cleanup
    try:
        seed_path.unlink()
    except Exception:
        pass

    print(f"\n{'='*60}")
    print(f"  Full (6,6) Sweep Results")
    print(f"{'='*60}")
    print(f"  Targets:        {', '.join(targets)}")
    print(f"  Total tested:   {total_tested}")
    print(f"  Total novel:    {total_novel}")
    print(f"  Deep-6 hits:    {total_deep6}")
    print(f"  Hit rate:       {overall_rate:.2f}%")
    print(f"  Wall time:      {wall}s")
    print(f"  JSON -> {args.json_out}")
    print(f"  CSV  -> {args.csv_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
