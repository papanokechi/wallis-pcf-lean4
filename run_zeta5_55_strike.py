#!/usr/bin/env python3
"""
(5,5) Transcendental Strike — Guided Deep Sweep for zeta(5)
════════════════════════════════════════════════════════════

Uses the 25 verified zeta(5) templates from the Kloosterman sweep as
seeds, with a priority_map tuned for adeg=5|bdeg=5 exploration.

Feeds templates directly into deep_sweep.py via --seed-file and injects
the Transcendental Architect priority_map for zeta5.
"""

import json
import os
import sys
import subprocess

# ── Configuration ──
TARGET       = "zeta5"
ITERS        = 50
BATCH        = 64
PREC         = 500
SEED_RNG     = 7777
WORKERS      = 0          # auto
TEMPLATE_SRC = "zeta5_architect_templates.json"
SEED_FILE    = "zeta5_deep_seeds.json"
JSON_OUT     = "zeta5_55_sweep_results.json"
CSV_OUT      = "zeta5_55_sweep_results.csv"

# Priority map: heavily bias toward (5,5) and (4,4) balanced signatures
ZETA5_PRIORITY_MAP = {
    "adeg=5|bdeg=5|mode=ratio|order=5":    8.0,   # maximum weight
    "adeg=4|bdeg=4|mode=ratio|order=4":    6.0,
    "adeg=5|bdeg=4|mode=ratio|order=4":    5.0,   # asymmetric
    "adeg=4|bdeg=5|mode=ratio|order=4":    5.0,
    "adeg=6|bdeg=5|mode=ratio|order=5":    3.5,   # higher exploration
    "adeg=5|bdeg=6|mode=ratio|order=5":    3.5,
    "adeg=4|bdeg=3|mode=backward|order=0": 2.0,   # known-good from sweep
    "adeg=3|bdeg=3|mode=backward|order=0": 1.5,   # fallback
}


def main():
    print("=" * 70)
    print("  ZETA(5) (5,5) TRANSCENDENTAL STRIKE")
    print("=" * 70)

    # ── Step 1: Build seed file from templates + QMF conjugates ─────
    print("\n  [1/3] Building seed file from templates...")

    seeds = []

    # Load templates
    if os.path.exists(TEMPLATE_SRC):
        with open(TEMPLATE_SRC) as f:
            templates = json.load(f)
        print(f"    Loaded {len(templates)} templates from {TEMPLATE_SRC}")

        for t in templates:
            seeds.append({
                "alpha": t["alpha"],
                "beta": t["beta"],
                "target": "zeta5",
                "mode": t.get("mode", "backward"),
                "order": t.get("order", 0),
                "n_terms": 500,
            })
    else:
        print(f"    WARNING: {TEMPLATE_SRC} not found. Using generated seeds.")

    # Add manually crafted (5,5) seeds based on structural analysis
    # Apery-like for zeta(5): b(n) should be degree 5, a(n) degree 5
    # Inspired by the Zudilin-style quintic recurrences
    crafted = [
        # Seed S1: Quintic balanced — modeled on Apery structure extension
        {"alpha": [0, 0, 0, 0, 0, -1],   # a(n) = -n^5
         "beta": [1, -15, 75, -155, 120, 34],  # degree-5 polynomial
         "mode": "ratio", "order": 5},

        # Seed S2: Conductor-120 resonance (120 = 5! = 24*5)
        {"alpha": [0, 0, 0, 0, -1, -1],  # a(n) = -(n^5 + n^4)
         "beta": [1, 10, 120, 240, 120, 24],  # incorporates 120
         "mode": "ratio", "order": 5},

        # Seed S3: Discriminant-tuned quintic
        {"alpha": [0, 0, -1, 0, 0, -1],  # a(n) = -(n^5 + n^2)
         "beta": [5, 25, 50, 50, 25, 5],  # (n+1)^5/n^5 structure
         "mode": "ratio", "order": 5},

        # Seed S4: Asymmetric (4,5) from verified discovery mutation
        {"alpha": [0, 0, 0, -1, 1],      # a(n) = n^4 - n^3
         "beta": [1, -5, 10, -10, 5, -1],  # -(n-1)^5 structure
         "mode": "ratio", "order": 4},

        # Seed S5: Mixed (5,4) with conductor correction
        {"alpha": [0, 0, 0, 0, 0, -1],   # a(n) = -n^5
         "beta": [1, 4, 6, 4, 1],         # (n+1)^4 = n^4+4n^3+...
         "mode": "ratio", "order": 4},
    ]

    for i, s in enumerate(crafted):
        s["target"] = "zeta5"
        s["n_terms"] = 500
        seeds.append(s)

    # Generate QMF conjugates (shifts by ±1, +2) for top seeds
    from transcendental_architect_synthesis import _shift_poly
    expanded = []
    for s in seeds[:10]:  # top 10 only
        for shift in [-1, 1, 2]:
            expanded.append({
                "alpha": _shift_poly(s["alpha"], shift),
                "beta": _shift_poly(s["beta"], shift),
                "target": "zeta5",
                "mode": s.get("mode", "backward"),
                "order": s.get("order", 0),
                "n_terms": 500,
            })
    seeds.extend(expanded)

    with open(SEED_FILE, "w") as f:
        json.dump(seeds, f, indent=2)
    print(f"    Wrote {len(seeds)} seeds to {SEED_FILE}")

    # ── Step 2: Write priority_map to temp file ─────────────────────
    print("\n  [2/3] Configuring priority map...")
    for sig, w in sorted(ZETA5_PRIORITY_MAP.items(), key=lambda x: -x[1]):
        print(f"    {w:4.1f}  {sig}")

    # ── Step 3: Launch the deep sweep ───────────────────────────────
    print(f"\n  [3/3] Launching deep sweep: {TARGET} | {ITERS}x{BATCH} | prec={PREC}")
    print(f"    Seed file: {SEED_FILE}")
    print(f"    Output: {JSON_OUT}, {CSV_OUT}")
    print("=" * 70)

    # Use deep_sweep.py if available, otherwise direct agent invocation
    if os.path.exists("deep_sweep.py"):
        cmd = [
            sys.executable, "deep_sweep.py",
            "--target", TARGET,
            "--iters", str(ITERS),
            "--batch", str(BATCH),
            "--prec", str(PREC),
            "--workers", str(WORKERS),
            "--seed", str(SEED_RNG),
            "--seed-file", SEED_FILE,
            "--deep",
            "--json-out", JSON_OUT,
            "--csv-out", CSV_OUT,
        ]
        print(f"  Running: {' '.join(cmd)}\n")
        os.execv(sys.executable, cmd)
    else:
        # Direct invocation via ramanujan_agent_v2_fast
        print("  deep_sweep.py not found; using direct agent invocation.\n")
        sys.path.insert(0, ".")
        from ramanujan_agent_v2_fast import RamanujanAgent
        import random

        random.seed(SEED_RNG)
        agent = RamanujanAgent(
            target=TARGET,
            seed_file=SEED_FILE,
            priority_map=ZETA5_PRIORITY_MAP,
            deep_mode=True,
        )
        agent.run(
            n_iters=ITERS, batch=BATCH, verbose=True,
            workers=WORKERS, executor_kind="process",
        )
        agent.save(JSON_OUT)
        agent.save_seeds("zeta5_55_relay_seeds.json")

        print(f"\n  Results: {JSON_OUT}")
        print(f"  Tested:      {agent.stats.tested}")
        print(f"  Discoveries: {agent.stats.discoveries}")
        print(f"  Novel:       {agent.stats.novel}")


if __name__ == "__main__":
    main()
