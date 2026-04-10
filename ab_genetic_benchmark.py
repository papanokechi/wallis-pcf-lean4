#!/usr/bin/env python3
"""A/B benchmark: genetic priority map vs control (no priority bias).

Runs the Ramanujan agent twice with the same seed — once with the corrected
per-target genetic priority map and once with an empty map — then compares
discovery rates.  Exit code 1 if genetic is worse than control.

Usage:
    python ab_genetic_benchmark.py --target zeta3 --iters 30 --batch 64 --seed 42
    python ab_genetic_benchmark.py --targets zeta3,pi,e,log2 --iters 5 --batch 64 --trials 3 --csv-out lift.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time

from ramanujan_agent_v2_fast import (
    CONSTANTS,
    DEFAULT_SIGNATURE_PRIORITY_MAP,
    RamanujanAgent,
    _auto_worker_count,
    _effective_batch_size,
)


def _run_arm(label: str, target: str, iters: int, batch: int,
             seed: int, workers: int, executor: str,
             priority_map: dict[str, float] | None) -> dict:
    random.seed(seed)
    agent = RamanujanAgent(target=target, priority_map=priority_map)
    agent.run(n_iters=iters, batch=batch, verbose=False,
              workers=workers, executor_kind=executor)
    tested = agent.stats.tested
    novel = agent.stats.novel
    rate = novel / tested if tested else 0.0
    elapsed = agent.stats.elapsed_seconds()
    return {
        "label": label,
        "target": target,
        "iters": iters,
        "batch": batch,
        "seed": seed,
        "tested": tested,
        "discoveries": agent.stats.discoveries,
        "novel": novel,
        "rate_percent": round(rate * 100, 3),
        "elapsed_seconds": round(elapsed, 3),
        "persistent_promotions": agent.stats.persistent_promotions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A/B benchmark: genetic priority map vs no-priority control.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--target", default=None, choices=list(CONSTANTS),
                        help="Single target (use --targets for multi-target).")
    parser.add_argument("--targets", default=None, type=str,
                        help="Comma-separated targets, e.g. zeta3,pi,e,log2.")
    parser.add_argument("--iters", type=int, default=30)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trials", type=int, default=1,
                        help="Number of independent trials per target (seed offset per trial).")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--executor", default="process", choices=["process", "thread"])
    parser.add_argument("--json-out", default="ab_genetic_results.json")
    parser.add_argument("--csv-out", default=None,
                        help="Optional CSV output with per-target/trial rows.")
    parser.add_argument("--fail-on-regression", action="store_true",
                        help="Exit 1 if genetic arm has lower rate than control.")
    args = parser.parse_args()

    # Resolve target list
    if args.targets:
        targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    elif args.target:
        targets = [args.target]
    else:
        targets = ["zeta3"]

    trials = max(1, args.trials)

    print(f"=== A/B Genetic Benchmark ===")
    print(f"  targets={','.join(targets)}  trials={trials}")
    print(f"  iters={args.iters}  batch={args.batch}  seed={args.seed}  workers={args.workers}")
    print()

    all_rows: list[dict] = []
    target_summaries: list[dict] = []
    any_fail = False

    for target in targets:
        genetic_priors = DEFAULT_SIGNATURE_PRIORITY_MAP.get(target, {})
        control_rates: list[float] = []
        genetic_rates: list[float] = []

        print(f"── {target} ({len(genetic_priors)} prior sigs, {trials} trial(s)) ──")

        for trial in range(trials):
            trial_seed = args.seed + trial * 1000
            # Control arm
            t0 = time.perf_counter()
            control = _run_arm("control", target, args.iters, args.batch,
                               trial_seed, args.workers, args.executor,
                               priority_map={})
            control["wall_seconds"] = round(time.perf_counter() - t0, 3)
            control_rates.append(control["rate_percent"])

            # Genetic arm
            t1 = time.perf_counter()
            genetic = _run_arm("genetic", target, args.iters, args.batch,
                               trial_seed, args.workers, args.executor,
                               priority_map=genetic_priors)
            genetic["wall_seconds"] = round(time.perf_counter() - t1, 3)
            genetic_rates.append(genetic["rate_percent"])

            delta = genetic["rate_percent"] - control["rate_percent"]
            print(f"  trial {trial+1}/{trials}  seed={trial_seed}  "
                  f"ctrl={control['rate_percent']:.2f}%  gen={genetic['rate_percent']:.2f}%  "
                  f"Δ={delta:+.2f}pp")

            all_rows.append({
                "target": target,
                "trial": trial + 1,
                "seed": trial_seed,
                "control_tested": control["tested"],
                "control_novel": control["novel"],
                "control_rate": control["rate_percent"],
                "control_wall_s": control["wall_seconds"],
                "genetic_tested": genetic["tested"],
                "genetic_novel": genetic["novel"],
                "genetic_rate": genetic["rate_percent"],
                "genetic_wall_s": genetic["wall_seconds"],
                "delta_pp": round(delta, 3),
            })

        # Aggregate per target
        mean_ctrl = statistics.mean(control_rates) if control_rates else 0.0
        mean_gen = statistics.mean(genetic_rates) if genetic_rates else 0.0
        delta_mean = mean_gen - mean_ctrl
        ratio = mean_gen / mean_ctrl if mean_ctrl > 0 else float("inf")
        verdict = "PASS" if delta_mean >= 0 else "FAIL"
        if verdict == "FAIL":
            any_fail = True

        target_summaries.append({
            "target": target,
            "trials": trials,
            "mean_control_rate": round(mean_ctrl, 3),
            "mean_genetic_rate": round(mean_gen, 3),
            "delta_pp": round(delta_mean, 3),
            "ratio": round(ratio, 3),
            "verdict": verdict,
        })
        print(f"  ➜ {target}: ctrl_avg={mean_ctrl:.2f}%  gen_avg={mean_gen:.2f}%  "
              f"Δ={delta_mean:+.2f}pp  ratio={ratio:.2f}x  [{verdict}]")
        print()

    # ── Summary table ──
    print("=" * 72)
    print(f"{'Target':>10}  {'Ctrl%':>7}  {'Gen%':>7}  {'Δpp':>7}  {'Ratio':>6}  {'Verdict':>7}")
    print("-" * 72)
    for s in target_summaries:
        print(f"{s['target']:>10}  {s['mean_control_rate']:>7.2f}  {s['mean_genetic_rate']:>7.2f}  "
              f"{s['delta_pp']:>+7.2f}  {s['ratio']:>6.2f}  {s['verdict']:>7}")
    print("=" * 72)

    overall_verdict = "FAIL" if any_fail else "PASS"
    print(f"Overall verdict: {overall_verdict}")

    result = {
        "benchmark": "ab_genetic",
        "targets": targets,
        "trials": trials,
        "iters": args.iters,
        "batch": args.batch,
        "base_seed": args.seed,
        "target_summaries": target_summaries,
        "all_rows": all_rows,
        "overall_verdict": overall_verdict,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\n  JSON -> {args.json_out}")

    if args.csv_out:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()) if all_rows else [])
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"  CSV  -> {args.csv_out}")

    if args.fail_on_regression and overall_verdict == "FAIL":
        print("\n  *** REGRESSION: genetic arm is worse than control on 1+ targets ***")
        sys.exit(1)


if __name__ == "__main__":
    main()
