#!/usr/bin/env python3
"""
Lightweight benchmark harness for `ramanujan_agent_v2_fast.py`.

It uses `--json-summary` so results are parsed from a stable machine-readable
artifact rather than brittle regexes over console output.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_CASES = [
    {"target": "zeta3", "iters": 3, "batch": 8, "prec": 300},
    {"target": "zeta3", "iters": 10, "batch": 8, "prec": 300},
    {"target": "euler_g", "iters": 20, "batch": 8, "prec": 300},
]


def parse_case(raw: str) -> dict[str, int | str]:
    parts = raw.split(":")
    if len(parts) not in (3, 4):
        raise argparse.ArgumentTypeError(
            "Case must be target:iters:batch[:prec], e.g. zeta3:10:8:300"
        )
    target = parts[0]
    iters = int(parts[1])
    batch = int(parts[2])
    prec = int(parts[3]) if len(parts) == 4 else 300
    return {"target": target, "iters": iters, "batch": batch, "prec": prec}


def case_label(case: dict[str, int | str]) -> str:
    return f"{case['target']} | {case['iters']} iters | batch {case['batch']} | {case['prec']}dp"


def parse_workers_arg(raw: str | int) -> list[int]:
    if isinstance(raw, int):
        return [raw]
    values: list[int] = []
    for part in str(raw).split(","):
        text = part.strip()
        if not text:
            continue
        try:
            values.append(int(text))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid worker count '{text}'. Use integers like 0,1,2,4,8"
            ) from exc
    if not values:
        raise argparse.ArgumentTypeError("At least one worker count must be provided.")
    return values


def run_case(python_exe: str, script_path: Path, case: dict[str, int | str], *, timeout: int, seed: int | None = None, workers: int = 0, executor: str = "process") -> dict:
    with tempfile.TemporaryDirectory(prefix="ramanujan_bench_") as tmpdir:
        tmp = Path(tmpdir)
        summary_path = tmp / "summary.json"
        html_path = tmp / "summary.html"
        cmd = [
            python_exe,
            str(script_path),
            "--target", str(case["target"]),
            "--iters", str(case["iters"]),
            "--batch", str(case["batch"]),
            "--prec", str(case["prec"]),
            "--quiet",
            "--json-summary", str(summary_path),
            "--summary-html", str(html_path),
        ]
        if seed is not None:
            cmd.extend(["--seed", str(seed)])
        if workers is not None:
            cmd.extend(["--workers", str(workers)])
        if executor:
            cmd.extend(["--executor", str(executor)])
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=script_path.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        wall_seconds = time.perf_counter() - t0

        summary = {}
        if summary_path.exists():
            with open(summary_path, encoding="utf-8") as f:
                summary = json.load(f)

        stats = summary.get("stats", {})
        return {
            "case": case,
            "label": case_label(case),
            "returncode": proc.returncode,
            "wall_seconds": round(wall_seconds, 3),
            "elapsed_seconds": stats.get("elapsed_seconds"),
            "gcf_per_sec": stats.get("gcf_per_sec"),
            "novel_finds": stats.get("novel"),
            "discoveries": len(summary.get("discoveries", [])),
            "stdout_tail": "\n".join((proc.stdout or "").strip().splitlines()[-8:]),
            "stderr": (proc.stderr or "").strip(),
        }


def aggregate_trials(label: str, trials: list[dict], *, workers: int, executor: str) -> dict:
    ok = [t for t in trials if t["returncode"] == 0]
    walls = [t["wall_seconds"] for t in ok]
    throughputs = [t["gcf_per_sec"] for t in ok if t["gcf_per_sec"] is not None]
    finds = [t["novel_finds"] for t in ok if t["novel_finds"] is not None]

    return {
        "label": label,
        "workers": workers,
        "executor": executor,
        "trials": len(trials),
        "successful_trials": len(ok),
        "wall_seconds_mean": round(statistics.mean(walls), 3) if walls else None,
        "wall_seconds_std": round(statistics.pstdev(walls), 3) if len(walls) > 1 else 0.0 if walls else None,
        "gcf_per_sec_mean": round(statistics.mean(throughputs), 3) if throughputs else None,
        "novel_finds_mean": round(statistics.mean(finds), 3) if finds else None,
        "speedup_vs_seq": None,
        "efficiency_pct": None,
        "trial_details": trials,
    }


def _annotate_scaling(rows: list[dict]) -> None:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["label"], []).append(row)

    for _label, items in grouped.items():
        baseline = None
        for item in items:
            if item.get("workers") == 1 and item.get("gcf_per_sec_mean"):
                baseline = item["gcf_per_sec_mean"]
                break
        if baseline is None:
            for item in items:
                if item.get("gcf_per_sec_mean"):
                    baseline = item["gcf_per_sec_mean"]
                    break
        if not baseline:
            continue

        for item in items:
            throughput = item.get("gcf_per_sec_mean")
            workers = max(1, int(item.get("workers") or 1))
            if throughput is None:
                continue
            item["speedup_vs_seq"] = round(throughput / baseline, 3)
            item["efficiency_pct"] = round((throughput / baseline) / workers * 100.0, 1)


def print_scaling_summary(rows: list[dict]) -> None:
    if not rows:
        return
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["label"], []).append(row)

    print("\nScaling summary:")
    for label, items in grouped.items():
        print(f"\n  {label}")
        print("  workers  gcf/s    speedup  efficiency  wall(s)")
        print("  -------  -------  -------  ----------  -------")
        for item in sorted(items, key=lambda r: int(r.get("workers", 0))):
            gcf = item.get("gcf_per_sec_mean")
            speedup = item.get("speedup_vs_seq")
            eff = item.get("efficiency_pct")
            wall = item.get("wall_seconds_mean")
            gcf_txt = f"{gcf:.3f}" if isinstance(gcf, (int, float)) else "n/a"
            sp_txt = f"{speedup:.2f}x" if isinstance(speedup, (int, float)) else "n/a"
            eff_txt = f"{eff:.1f}%" if isinstance(eff, (int, float)) else "n/a"
            wall_txt = f"{wall:.3f}" if isinstance(wall, (int, float)) else "n/a"
            print(f"  {int(item.get('workers', 0)):>7}  {gcf_txt:>7}  {sp_txt:>7}  {eff_txt:>10}  {wall_txt:>7}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark ramanujan_agent_v2_fast.py with reproducible JSON summaries.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--script",
        default="ramanujan_agent_v2_fast.py",
        help="Agent script to benchmark.",
    )
    parser.add_argument(
        "--case",
        action="append",
        type=parse_case,
        help="Benchmark case in target:iters:batch[:prec] format. Repeat to add multiple cases.",
    )
    parser.add_argument("--target", default=None, help="Convenience single-case target for scaling sweeps.")
    parser.add_argument("--iters", type=int, default=5, help="Iterations for the convenience single-case sweep.")
    parser.add_argument("--batch", type=int, default=128, help="Batch size for the convenience single-case sweep.")
    parser.add_argument("--prec", type=int, default=300, help="Precision for the convenience single-case sweep.")
    parser.add_argument("--trials", type=int, default=3, help="Number of trials per case.")
    parser.add_argument("--timeout", type=int, default=600, help="Per-trial timeout in seconds.")
    parser.add_argument("--seed", type=int, default=None, help="Optional base RNG seed for reproducible trials.")
    parser.add_argument("--workers", default="0", help="Worker count or comma-separated sweep, e.g. 1,2,4,8.")
    parser.add_argument("--executor", default="process", choices=["process", "thread"], help="Parallel executor backend to benchmark.")
    parser.add_argument("--json-out", "--json", dest="json_out", default="ramanujan_benchmarks.json", help="Path for JSON benchmark results.")
    parser.add_argument("--csv-out", "--csv", dest="csv_out", default="ramanujan_benchmarks.csv", help="Path for CSV benchmark results.")
    args = parser.parse_args()

    script_path = Path(args.script).resolve()
    python_exe = sys.executable
    worker_values = parse_workers_arg(args.workers)
    if args.target:
        cases = [{"target": args.target, "iters": args.iters, "batch": args.batch, "prec": args.prec}]
    else:
        cases = args.case or DEFAULT_CASES

    results = []
    for case in cases:
        label = case_label(case)
        print(f"\n[benchmark] {label}")
        for workers in worker_values:
            trials = []
            print(f"  workers={workers} executor={args.executor}")
            for trial_idx in range(1, args.trials + 1):
                trial_seed = None if args.seed is None else args.seed + trial_idx - 1
                trial = run_case(python_exe, script_path, case, timeout=args.timeout,
                                 seed=trial_seed, workers=workers, executor=args.executor)
                trial["trial"] = trial_idx
                trial["workers"] = workers
                trials.append(trial)
                print(
                    f"    trial {trial_idx}: rc={trial['returncode']} "
                    f"wall={trial['wall_seconds']:.3f}s "
                    f"novel={trial['novel_finds']} gcf/s={trial['gcf_per_sec']}"
                )
            results.append(aggregate_trials(label, trials, workers=workers, executor=args.executor))

    _annotate_scaling(results)
    print_scaling_summary(results)

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "script": str(script_path),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "worker_values": worker_values,
        "results": results,
    }

    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "label",
                "workers",
                "executor",
                "trials",
                "successful_trials",
                "wall_seconds_mean",
                "wall_seconds_std",
                "gcf_per_sec_mean",
                "novel_finds_mean",
                "speedup_vs_seq",
                "efficiency_pct",
            ],
        )
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k) for k in writer.fieldnames})

    print("\nSaved benchmark artifacts:")
    print(f"  JSON -> {args.json_out}")
    print(f"  CSV  -> {args.csv_out}")


if __name__ == "__main__":
    main()
