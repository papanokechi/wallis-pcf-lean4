"""
ARIA Pilot Demo — Demonstrates the full discovery loop.

Runs ARIA with seed data, then injects custom sequences to show
how cross-domain discovery works.
"""

import sys
import os

# Ensure we can import the aria package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aria.orchestrator import ARIAOrchestrator
from aria.ingestion import Domain


def main():
    print("=" * 72)
    print("  ARIA Pilot Demo")
    print("  Autonomous Reasoning & Intuition Architecture v0.1")
    print("=" * 72)

    # ── Step 1: Create ARIA with pilot config ──
    config = {
        "max_iterations": 3,
        "verifier_max_rounds": 4,
        "resonance_threshold": 0.15,
        "verbose": True,
        "output_dir": "results/aria_demo",
        "axiom_persist_path": "results/aria_demo/axiom_bank.json",
    }

    aria = ARIAOrchestrator(config)

    # ── Step 2: Inject custom sequences to demo cross-domain discovery ──
    print("\n  [Demo] Injecting custom sequences for cross-domain testing...\n")

    # A biological growth curve that secretly has partition-like asymptotics
    import math
    bio_seq = [math.exp(2.5 * math.sqrt(n)) * n ** (-0.75) if n > 0 else 1.0
               for n in range(100)]
    aria.ingest_custom(
        "bacterial_colony_growth_curve",
        bio_seq,
        domain=Domain.BIOLOGY,
        gf_hint="Colony size ~ C·n^κ·exp(c·√n) with c≈2.5, κ≈-0.75",
    )

    # A financial time series with similar growth pattern
    import random
    random.seed(42)
    fin_seq = [math.exp(2.48 * math.sqrt(n)) * n ** (-0.73) * (1 + 0.01 * random.gauss(0, 1))
               if n > 0 else 1.0 for n in range(100)]
    aria.ingest_custom(
        "market_cap_accumulation",
        fin_seq,
        domain=Domain.FINANCE,
        gf_hint="Market cap growth with Meinardus-like accumulation",
    )

    # A mystery sequence (will end up orphaned / lost notebook)
    mystery = [float(n ** 3 * math.sin(n * 0.1) + 100 * math.log(n + 1))
               for n in range(1, 101)]
    aria.ingest_custom(
        "mystery_oscillating_cubic",
        mystery,
        domain=Domain.CUSTOM,
    )

    # ── Step 3: Run the full ARIA loop ──
    print("\n  [Demo] Starting ARIA self-iterating discovery loop...\n")
    result = aria.run()

    # ── Step 4: Show key results ──
    print("\n" + "=" * 72)
    print("  DEMO RESULTS SUMMARY")
    print("=" * 72)

    cumul = result["cumulative"]
    print(f"\n  Iterations:           {cumul['iterations']}")
    print(f"  Total conjectures:    {cumul['total_conjectures_generated']}")
    print(f"  Verified:             {cumul['total_verified']}")
    print(f"  New axioms:           {cumul['total_new_axioms']}")
    print(f"  Syntheses:            {cumul['total_syntheses']}")
    print(f"  Experiments designed: {cumul['total_experiments']}")
    print(f"  Verification rate:    {cumul['verification_rate']:.1%}")

    ab = result["axiom_bank"]
    ln = result["lost_notebook"]
    print(f"\n  Axiom bank:           {ab.get('total', 0)} axioms")
    print(f"  Lost notebook:        {ln.get('total', 0)} quarantined entries")

    enc = result["encoder"]
    print(f"\n  Encoded objects:      {enc['total_encoded']}")
    print(f"  With signatures:      {enc['with_partition_sig']}")
    print(f"  CF sweet-spot:        {enc['cf_sweet_spot']}")
    print(f"  Orphans:              {enc['orphans']}")

    # Show axiom bank details
    if ab.get("total", 0) > 0:
        print(f"\n  Axiom bank breakdown:")
        for status, count in ab.get("by_proof_status", {}).items():
            print(f"    {status}: {count}")

    # Show lost notebook details
    if ln.get("total", 0) > 0:
        print(f"\n  Lost notebook breakdown:")
        for reason, count in ln.get("by_reason", {}).items():
            print(f"    {reason}: {count}")

    # Show synthesizer details
    synth = result.get("synthesizer", {})
    if synth.get("total", 0) > 0:
        print(f"\n  Synthesis breakdown:")
        print(f"    Essential isomorphisms: {synth.get('essential_isomorphisms', 0)}")
        print(f"    Actionable results:     {synth.get('actionable', 0)}")
        print(f"    With experiment specs:  {synth.get('with_experiment_spec', 0)}")

    print(f"\n  Elapsed: {result['elapsed_seconds']:.1f}s")
    print("\n" + "=" * 72)
    print("  Demo complete. Reports saved to results/aria_demo/")
    print("=" * 72)


if __name__ == "__main__":
    main()
