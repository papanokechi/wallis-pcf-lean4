"""
ramanujan_parallel_launcher.py
──────────────────────────────
Parallel runner for ramanujan_breakthrough_generator.py.

Launches one worker process per (family, k) configuration.
Each worker writes to its own registry shard; a merger thread
combines them into ramanujan_registry.json after all workers finish.

Usage
-----
  python ramanujan_parallel_launcher.py                  # default: Family B k=1..6 + Family A
  python ramanujan_parallel_launcher.py --families A B   # specific families
  python ramanujan_parallel_launcher.py --workers 4      # cap parallel processes
  python ramanujan_parallel_launcher.py --dry-run        # print plan, don't execute
  python ramanujan_parallel_launcher.py --family-b-only  # fastest first-run option

Requirements
------------
  Same as ramanujan_breakthrough_generator.py:
    pip install mpmath anthropic sympy rich colorama

Architecture
------------
  MainProcess
    ├── WorkerPool (ProcessPoolExecutor, max_workers=N)
    │     ├── Worker(family=B, k=1)  → registry_B_k1.json
    │     ├── Worker(family=B, k=2)  → registry_B_k2.json
    │     ├── Worker(family=B, k=4)  → registry_B_k4.json
    │     ├── Worker(family=A)       → registry_A.json
    │     └── ...
    └── RegistryMerger               → ramanujan_registry.json
"""

import argparse
import json
import os
import sys
import time
import copy
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Try importing the generator; fail gracefully ────────────────────────────

try:
    import ramanujan_breakthrough_generator as rbg
    HAS_RBG = True
except ImportError:
    HAS_RBG = False

try:
    from mpmath import mp, mpf, zeta, binomial
    HAS_MPMATH = True
except ImportError:
    HAS_MPMATH = False

# ── Job definitions ──────────────────────────────────────────────────────────

@dataclass
class SearchJob:
    family:      str            # "A", "B", "C", "D"
    k:           Optional[int]  # for family B: k=1..6; others None
    mode:        str            # "mitm" | "dr"
    deg_alpha:   int
    deg_beta:    int
    coeff_range: int
    budget:      int
    precision:   int
    no_ai:       bool = True
    beta_patch:  str  = "n4"   # key into BETA_PATCHES
    alpha_constraints: list = field(default_factory=list)
    label:       str  = ""

    def __post_init__(self):
        if not self.label:
            k_str = f"_k{self.k}" if self.k is not None else ""
            self.label = f"Family{self.family}{k_str}"

    @property
    def registry_path(self) -> str:
        return f"registry_{self.label}.json"


# ── Beta patch implementations ───────────────────────────────────────────────

BETA_PATCHES = {
    "n4":          lambda n: n**4,
    "n6":          lambda n: n**6,
    "n2_nk1":      lambda n: n**2 * (n+1)**2,
    "n2_nk2":      lambda n: n**2 * (n+2)**2,
    "n2_nk3":      lambda n: n**2 * (n+3)**2,
    "n2_nk4":      lambda n: n**2 * (n+4)**2,
    "n2_nk5":      lambda n: n**2 * (n+5)**2,
    "n2_nk6":      lambda n: n**2 * (n+6)**2,
    "binom_sq":    lambda n: (1 if n == 0 else int(binomial(2*n, n))**2) if HAS_MPMATH else n**4,
    "n_binom_sq":  lambda n: n * (1 if n == 0 else int(binomial(2*n, n))**2) if HAS_MPMATH else n**4,
    "n2_binom_sq": lambda n: n**2 * (1 if n == 0 else int(binomial(2*n, n))**2) if HAS_MPMATH else n**4,
}

K_TO_BETA = {1: "n2_nk1", 2: "n2_nk2", 3: "n2_nk3",
             4: "n2_nk4", 5: "n2_nk5", 6: "n2_nk6"}


# ── Default job plans ────────────────────────────────────────────────────────

def build_job_plan(families: list[str], budget_scale: float = 1.0) -> list[SearchJob]:
    """Return ordered list of SearchJobs for the requested families."""
    jobs = []

    if "B" in families:
        # k=1,2 first (closest to Apéry), then k=4, then k=3,5,6
        for k in [1, 2, 4, 3, 5, 6]:
            jobs.append(SearchJob(
                family="B", k=k,
                mode="mitm",
                deg_alpha=3, deg_beta=2,
                coeff_range=20,
                budget=int(1000 * budget_scale),
                precision=100,
                beta_patch=K_TO_BETA[k],
                alpha_constraints=["no_constant"],  # α(0)=0
            ))

    if "A" in families:
        jobs.append(SearchJob(
            family="A", k=None,
            mode="mitm",
            deg_alpha=3, deg_beta=4,
            coeff_range=15,
            budget=int(600 * budget_scale),
            precision=100,
            beta_patch="n4",
        ))

    if "C" in families:
        jobs.append(SearchJob(
            family="C", k=None,
            mode="dr",
            deg_alpha=3, deg_beta=4,
            coeff_range=20,
            budget=int(400 * budget_scale),
            precision=150,
            beta_patch="n4",
            alpha_constraints=["palindrome"],
        ))

    if "D" in families:
        for patch_key, label_suffix in [("binom_sq", "p1"), ("n2_binom_sq", "pn2")]:
            jobs.append(SearchJob(
                family="D", k=None,
                mode="dr",
                deg_alpha=3, deg_beta=3,
                coeff_range=10,
                budget=int(500 * budget_scale),
                precision=120,
                beta_patch=patch_key,
                label=f"FamilyD_{label_suffix}",
            ))

    return jobs


# ── Worker (runs in subprocess) ──────────────────────────────────────────────

def run_worker(job_dict: dict) -> dict:
    """
    Entry point for each worker process.
    Receives job as plain dict (picklable), returns result dict.
    """
    # Pop extra keys not in SearchJob dataclass
    depth_override = job_dict.pop("_depth_override", None)
    worker_timeout = job_dict.pop("_timeout", None)
    job = SearchJob(**job_dict)
    result = {
        "label":      job.label,
        "family":     job.family,
        "k":          job.k,
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "status":     "running",
        "conjectures": [],
        "error":      None,
        "digits_best": 0,
        "hits":       0,
        "log_lines":  [],
    }

    try:
        if not HAS_MPMATH:
            raise ImportError("mpmath not installed — pip install mpmath")
        if not HAS_RBG:
            raise ImportError(
                "ramanujan_breakthrough_generator.py not found in sys.path. "
                "Place it in the same directory as this launcher."
            )

        mp.dps = job.precision + 20

        # ── Build beta function ──────────────────────────────────────────────
        beta_fn = BETA_PATCHES.get(job.beta_patch)
        if beta_fn is None:
            raise ValueError(f"Unknown beta_patch: {job.beta_patch}")

        # ── Instantiate engine ───────────────────────────────────────────────
        engine = rbg.PCFEngine(precision=job.precision)

        # Patch beta into engine (override the polynomial evaluator)
        engine._beta_override = beta_fn

        original_eval = engine.evaluate_pcf

        def patched_eval(alpha_coeffs, beta_coeffs, depth=100):
            """Wrap evaluate_pcf to inject our custom beta.
            Returns (value, error_estimate, convergents) to match PCFEngine API."""
            try:
                mp.dps = max(job.precision + 20, depth * 2 if "binom" in job.beta_patch else job.precision + 20)
                p_prev, p_curr = mpf(1), mpf(alpha_coeffs[0]) if alpha_coeffs else mpf(0)
                q_prev, q_curr = mpf(0), mpf(1)
                convergents = []
                prev_val = None
                for n in range(1, depth + 1):
                    # Evaluate α_n
                    a_n = sum(c * n**i for i, c in enumerate(alpha_coeffs))
                    # Use overridden beta
                    b_n = engine._beta_override(n)
                    p_prev, p_curr = p_curr, a_n * p_curr + b_n * p_prev
                    q_prev, q_curr = q_curr, a_n * q_curr + b_n * q_prev
                    if q_curr == 0:
                        return (None, None, [])
                    if n % 20 == 0:
                        val = p_curr / q_curr
                        convergents.append(val)
                        prev_val = val
                if q_curr == 0:
                    return (None, None, [])
                value = p_curr / q_curr
                # Error estimate: difference between last two sampled convergents
                if len(convergents) >= 2:
                    err = abs(convergents[-1] - convergents[-2])
                else:
                    err = mpf(1)
                return (value, err, convergents)
            except Exception:
                return (None, None, [])

        engine.evaluate_pcf = patched_eval

        # ── Alpha constraint helpers ─────────────────────────────────────────
        def satisfies_constraints(alpha: list) -> bool:
            for constraint in job.alpha_constraints:
                if constraint == "no_constant":
                    # α(0) = 0: constant term (last coeff for poly) must be 0
                    if len(alpha) > 0 and alpha[-1] != 0:
                        return False
                elif constraint == "palindrome":
                    if len(alpha) >= 4:
                        if alpha[0] != alpha[-1]:
                            return False
                        if len(alpha) >= 3 and alpha[1] != alpha[-2]:
                            return False
            return True

        # ── Run search ───────────────────────────────────────────────────────
        target_name = "zeta3"  # pass string, not mpf — _get_constant() needs a name
        conjectures = []
        search_depth = depth_override if depth_override is not None else 80

        import sys
        def _log(msg):
            result["log_lines"].append(msg)

        if job.mode == "mitm":
            searcher = rbg.MITMSearch(engine)
            raw_hits = searcher.run(
                target=target_name,
                deg_alpha=job.deg_alpha,
                deg_beta=job.deg_beta,
                coeff_range=job.coeff_range,
                budget=job.budget,
                depth=search_depth,
                log_fn=_log,
            )
        else:  # "dr"
            searcher = rbg.DescentRepelSearch(engine)
            raw_hits = searcher.run(
                target=target_name,
                deg_alpha=job.deg_alpha,
                deg_beta=job.deg_beta,
                coeff_range=job.coeff_range,
                budget=job.budget,
                depth=search_depth,
                log_fn=_log,
            )

        # ── Filter + package results ─────────────────────────────────────────
        for alpha_coeffs, beta_coeffs, digits in raw_hits:
            if not satisfies_constraints(list(alpha_coeffs)):
                continue
            if digits < 15:
                continue

            conj = {
                "label":          job.label,
                "family":         job.family,
                "k":              job.k,
                "beta_patch":     job.beta_patch,
                "alpha_coeffs":   list(alpha_coeffs),
                "beta_coeffs":    list(beta_coeffs),
                "digits_matched": digits,
                "novel":          True,   # will be cross-checked by merger
                "timestamp":      datetime.now().isoformat(),
            }
            conjectures.append(conj)

        conjectures.sort(key=lambda c: c["digits_matched"], reverse=True)

        # ── Write shard registry ─────────────────────────────────────────────
        shard = {"conjectures": conjectures, "meta": asdict(job)}
        with open(job.registry_path, "w") as f:
            json.dump(shard, f, indent=2)

        result["conjectures"] = conjectures
        result["hits"]        = len(conjectures)
        result["digits_best"] = conjectures[0]["digits_matched"] if conjectures else 0
        result["status"]      = "done"

    except Exception as e:
        result["status"] = "error"
        result["error"]  = traceback.format_exc()

    result["finished_at"] = datetime.now().isoformat()
    return result


# ── Registry merger ──────────────────────────────────────────────────────────

def merge_registries(results: list[dict], output_path: str = "ramanujan_registry.json"):
    """Merge all shard registries into the main registry, deduplicating by alpha_coeffs."""
    all_conjectures = []
    seen_alpha = set()

    for r in results:
        for c in r.get("conjectures", []):
            key = tuple(c["alpha_coeffs"])
            if key not in seen_alpha:
                seen_alpha.add(key)
                all_conjectures.append(c)

    # Sort by digits descending
    all_conjectures.sort(key=lambda c: c["digits_matched"], reverse=True)

    # Mark known Apéry formula
    apery_alpha = [34, 51, 27, 5]
    for c in all_conjectures:
        if c["alpha_coeffs"][:4] == apery_alpha:
            c["novel"] = False

    registry = {
        "generated_at":   datetime.now().isoformat(),
        "total_hits":     len(all_conjectures),
        "conjectures":    all_conjectures,
    }

    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)

    return registry


# ── Progress printer ─────────────────────────────────────────────────────────

def print_plan(jobs: list[SearchJob], max_workers: int):
    print("\n┌─ Parallel Ramanujan Search Plan " + "─" * 44)
    print(f"│  Workers:  {max_workers} parallel processes")
    print(f"│  Jobs:     {len(jobs)} total")
    print(f"│  Waves:    {-(-len(jobs) // max_workers)} (ceil)")
    print("├" + "─" * 77)
    for i, j in enumerate(jobs):
        k_str    = f"  k={j.k}" if j.k is not None else "      "
        mode_str = j.mode.upper().ljust(4)
        print(f"│  [{i+1:2d}] Family {j.family}{k_str}  {mode_str}  "
              f"deg{j.deg_alpha}/{j.deg_beta}  "
              f"coeff±{j.coeff_range}  "
              f"budget={j.budget}  "
              f"β={j.beta_patch}")
    print("└" + "─" * 77 + "\n")


def print_result(r: dict):
    status_sym = "✓" if r["status"] == "done" else "✗"
    hits_str   = f"{r['hits']} hits" if r["hits"] else "no hits"
    best_str   = f"  best={r['digits_best']}d" if r["digits_best"] else ""
    err_str    = f"  ERR: {r['error'].splitlines()[-1]}" if r["error"] else ""
    print(f"  {status_sym} {r['label']:<22}  {hits_str}{best_str}{err_str}")
    for line in r.get("log_lines", []):
        print(f"      {line}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Parallel launcher for ramanujan_breakthrough_generator.py"
    )
    parser.add_argument(
        "--families", nargs="+", default=["B", "A"],
        choices=["A", "B", "C", "D"],
        help="Which families to run (default: B A)"
    )
    parser.add_argument(
        "--family-b-only", action="store_true",
        help="Shortcut: run only Family B k=1..6"
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Max parallel processes (default: min(jobs, cpu_count-1))"
    )
    parser.add_argument(
        "--budget-scale", type=float, default=1.0,
        help="Scale all budgets by this factor (e.g. 0.5 for quick test)"
    )
    parser.add_argument(
        "--coeff", type=str, default=None,
        help="Override coeff_range for all jobs (e.g. 12 or 1..12)"
    )
    parser.add_argument(
        "--max-depth", type=int, default=None,
        help="Override PCF evaluation depth (default: 80)"
    )
    parser.add_argument(
        "--timeout", type=int, default=None,
        help="Per-worker timeout in seconds (default: unlimited)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print plan and exit without running"
    )
    parser.add_argument(
        "--output", default="ramanujan_registry.json",
        help="Merged output registry path"
    )
    args = parser.parse_args()

    families = ["B"] if args.family_b_only else args.families
    jobs     = build_job_plan(families, budget_scale=args.budget_scale)

    # Apply --coeff override
    if args.coeff is not None:
        # Accept "12" or "1..12" (use the upper bound as coeff_range)
        coeff_str = args.coeff.strip()
        if ".." in coeff_str:
            coeff_val = int(coeff_str.split("..")[-1])
        else:
            coeff_val = int(coeff_str)
        for j in jobs:
            j.coeff_range = coeff_val

    # Apply --max-depth override
    if args.max_depth is not None:
        for j in jobs:
            j._depth_override = args.max_depth

    cpu_count   = os.cpu_count() or 4
    max_workers = args.workers or min(len(jobs), max(1, cpu_count - 1))

    print_plan(jobs, max_workers)

    if args.dry_run:
        print("Dry run — exiting.\n")
        return

    if not HAS_RBG:
        print("ERROR: ramanujan_breakthrough_generator.py not found.")
        print("Place it in the same directory as this launcher and retry.\n")
        sys.exit(1)

    if not HAS_MPMATH:
        print("ERROR: mpmath not installed.  pip install mpmath\n")
        sys.exit(1)

    # Serialize jobs as plain dicts for pickling across processes
    job_dicts = []
    for j in jobs:
        jd = asdict(j)
        jd["_depth_override"] = getattr(j, "_depth_override", None)
        jd["_timeout"] = args.timeout
        job_dicts.append(jd)

    t0      = time.time()
    results = []

    print(f"Starting {len(jobs)} workers (max {max_workers} parallel)...\n")

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(run_worker, jd): jd["label"] for jd in job_dicts}
        worker_timeout = args.timeout  # per-worker timeout

        for future in as_completed(futures, timeout=None):
            label = futures[future]
            try:
                r = future.result(timeout=worker_timeout)
            except Exception as exc:
                r = {"label": label, "status": "error",
                     "error": str(exc), "hits": 0,
                     "digits_best": 0, "conjectures": []}
            results.append(r)
            print_result(r)

    elapsed = time.time() - t0

    # Merge registries
    print(f"\nMerging {len(results)} shard registries → {args.output}")
    registry = merge_registries(results, output_path=args.output)

    # Clean up shards — DISABLED to preserve for post-mortem analysis
    # for j in jobs:
    #     p = Path(j.registry_path)
    #     if p.exists():
    #         p.unlink()

    # Summary
    total_hits = registry["total_hits"]
    novel_hits = sum(1 for c in registry["conjectures"] if c.get("novel"))
    best       = registry["conjectures"][0] if registry["conjectures"] else None

    print("\n┌─ Run summary " + "─" * 63)
    print(f"│  Elapsed:      {elapsed:.1f}s")
    print(f"│  Total hits:   {total_hits}")
    print(f"│  Novel hits:   {novel_hits}")
    if best:
        print(f"│  Best result:  {best['label']}  "
              f"α={best['alpha_coeffs']}  "
              f"{best['digits_matched']} digits")
    print(f"│  Registry:     {args.output}")
    print("└" + "─" * 77)

    if novel_hits > 0:
        print("\nTop novel hits (for ramanujan_agent.py escalation):")
        for c in registry["conjectures"][:5]:
            if c.get("novel"):
                print(f"  α={c['alpha_coeffs']}  β_patch={c['beta_patch']}  "
                      f"{c['digits_matched']}d  [{c['label']}]")

    print()


if __name__ == "__main__":
    main()
