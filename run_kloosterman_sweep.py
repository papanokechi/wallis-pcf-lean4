#!/usr/bin/env python3
"""
N=24 Cusp Sweep — Kloosterman-Tuned ζ(3) Search
══════════════════════════════════════════════════

Runs the Ramanujan agent with:
  • 12 Kloosterman-tuned seeds (3 base + 9 QMF conjugates)
  • Transcendental Architect priority_map (boosted quartic signatures)
  • Deep mode enabled for high-order polynomial exploration

This targets the 1.36% Eisenstein gap at Γ₀(24).
"""

import json
import sys
import os

# Ensure we can import from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ramanujan_agent_v2_fast import RamanujanAgent
from transcendental_architect_synthesis import (
    get_priority_map_for_target,
    export_kloosterman_seeds,
)


def main():
    # ── Configuration ──
    TARGET    = "zeta3"
    ITERS     = 100
    BATCH     = 128
    WORKERS   = 0       # auto
    SEED_FILE = "kloosterman_seeds.json"
    DEEP      = True
    PREC      = 300
    SEED_RNG  = 2024    # reproducible

    # ── Priority map from synthesis ──
    priority_map = get_priority_map_for_target(TARGET)
    print(f"Priority map for {TARGET}:")
    for sig, w in sorted(priority_map.items(), key=lambda x: -x[1]):
        print(f"  {w:5.1f}  {sig}")

    # ── Verify seed file exists ──
    if not os.path.exists(SEED_FILE):
        print(f"\nERROR: {SEED_FILE} not found. Generate it first:")
        print("  python -c \"from transcendental_architect_synthesis import *; "
              "import json; seeds = export_kloosterman_seeds(); "
              "json.dump(seeds, open('kloosterman_seeds.json','w'), indent=2)\"")
        sys.exit(1)

    with open(SEED_FILE) as f:
        seeds = json.load(f)
    print(f"\nLoaded {len(seeds)} seeds from {SEED_FILE}")

    # ── Run agent ──
    print(f"\n{'='*74}")
    print(f"  N=24 CUSP SWEEP: {TARGET} | {ITERS} iters × {BATCH} batch | deep={DEEP}")
    print(f"{'='*74}\n")

    import random
    random.seed(SEED_RNG)

    agent = RamanujanAgent(
        target=TARGET,
        seed_file=SEED_FILE,
        priority_map=priority_map,
        deep_mode=DEEP,
    )
    agent.run(
        n_iters=ITERS,
        batch=BATCH,
        verbose=True,
        workers=WORKERS,
        executor_kind="process",
        print_report=True,
    )

    # ── Save results ──
    out_json = "kloosterman_sweep_results.json"
    out_html = "kloosterman-sweep-summary.html"

    agent.save(out_json)
    print(f"\nResults saved to {out_json}")

    # Export seed pool for relay chaining
    agent.save_seeds("kloosterman_relay_seeds.json")
    print(f"Seed pool saved to kloosterman_relay_seeds.json")

    # ── Summary ──
    print(f"\n{'='*74}")
    print(f"  SWEEP COMPLETE")
    print(f"  Tested:      {agent.stats.tested}")
    print(f"  Discoveries: {agent.stats.discoveries}")
    print(f"  Novel:       {agent.stats.novel}")
    if agent.stats.tested > 0:
        rate = agent.stats.novel / agent.stats.tested * 100
        print(f"  Novel rate:  {rate:.3f}%")
    print(f"  Persistent promotions: {agent.stats.persistent_promotions}")
    print(f"{'='*74}")

    # Report any discoveries with their signatures
    if agent.discoveries:
        print(f"\n  DISCOVERIES:")
        for i, d in enumerate(agent.discoveries, 1):
            spec = d.spec
            sig = f"adeg={len(spec.alpha)-1}|bdeg={len(spec.beta)-1}|mode={spec.mode}|order={spec.order}"
            print(f"  [{i}] {d.closed_form}")
            print(f"      a(n) = {spec.alpha}")
            print(f"      b(n) = {spec.beta}")
            print(f"      Signature: {sig}")
            print(f"      Digits: {d.digits}")


if __name__ == "__main__":
    main()
