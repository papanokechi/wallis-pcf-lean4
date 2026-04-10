#!/usr/bin/env python3
"""
Conductor-Stratified (6,6) Pilot
═════════════════════════════════

Three separate pilot sweeps, one per conductor cluster, to measure
which conductor family produces the highest hit rate at (6,6) degrees.

Based on the harvest analysis:
  Cluster A: N=24 (Kloosterman heritage, 3 confirmed entries)
  Cluster B: N=6  (53 entries, strong zeta5/zeta3 signal)
  Cluster C: N=generic (286 entries, baseline)

Each pilot runs a short sweep (20 iters x 64 batch) with conductor-
specific seeds and priority maps.

The ζ(5) pattern analysis shows:
  - bdeg=3 has 2.7x convergence rate vs bdeg=1
  - Alpha shapes [-2,1,0], [2,-1,0], [8,-2,-1,0] recur frequently
  - Leading beta coefficients {4, 6, -1, -3} dominate

These insights are built into the seed generation.
"""

import json
import os
import sys
import random
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── Conductor-specific priority maps ──

PRIORITY_N24 = {
    "adeg=6|bdeg=6|mode=ratio|order=6":    8.0,
    "adeg=5|bdeg=5|mode=ratio|order=5":    6.0,
    "adeg=6|bdeg=5|mode=ratio|order=5":    5.0,
    "adeg=5|bdeg=6|mode=ratio|order=5":    5.0,
    "adeg=6|bdeg=3|mode=ratio|order=3":    4.0,  # bdeg=3 super-convergence
    "adeg=5|bdeg=3|mode=backward|order=0": 3.0,
    "adeg=4|bdeg=4|mode=ratio|order=4":    2.5,
}

PRIORITY_N6 = {
    "adeg=6|bdeg=6|mode=ratio|order=6":    8.0,
    "adeg=5|bdeg=5|mode=ratio|order=5":    6.0,
    "adeg=6|bdeg=3|mode=backward|order=0": 5.0,  # exploit bdeg=3 signal
    "adeg=5|bdeg=3|mode=backward|order=0": 4.5,
    "adeg=6|bdeg=4|mode=ratio|order=4":    4.0,
    "adeg=4|bdeg=3|mode=backward|order=0": 3.0,
}

PRIORITY_GENERIC = {
    "adeg=6|bdeg=6|mode=ratio|order=6":    7.0,
    "adeg=5|bdeg=5|mode=ratio|order=5":    5.0,
    "adeg=6|bdeg=5|mode=ratio|order=5":    4.0,
    "adeg=5|bdeg=4|mode=ratio|order=4":    3.5,
    "adeg=4|bdeg=4|mode=ratio|order=4":    3.0,
    "adeg=6|bdeg=3|mode=backward|order=0": 3.0,
}


def build_conductor_seeds(cluster_name, harvest_path="harvest/conductor_clusters.json",
                          pilot_path="harvest/66_pilot_seeds.json"):
    """Build seeds for a specific conductor family."""
    seeds = []

    # Load pilot seeds
    if os.path.exists(pilot_path):
        with open(pilot_path) as f:
            all_seeds = json.load(f)
        # Filter by approximate conductor match (check beta coefficients)
        for s in all_seeds:
            beta = s.get("beta", [])
            if cluster_name == "N24":
                if any(abs(c) in (24, 48, 72) for c in beta):
                    seeds.append(s)
            elif cluster_name == "N6":
                if beta and abs(beta[-1]) in (6, 12, 18, 3):
                    seeds.append(s)
            else:
                seeds.append(s)

    # Add degree-raised seeds from ζ(5) patterns
    # The recurring alpha shapes at degree 2-4, extended to degree 6
    z5_alpha_shapes = [
        [-2, 1, 0, 0, 0, 0, 1],           # [-2,1,0] extended to deg 6
        [2, -1, 0, 0, 0, 0, -1],           # [2,-1,0] negated + extended
        [8, -2, -1, 0, 0, 0, 1],           # [8,-2,-1,0] extended
        [0, 0, 0, 0, 0, 0, -1],            # -n^6 (pure power)
        [0, 0, -1, 0, 0, 0, -1],           # -(n^6 + n^2)
    ]

    z5_beta_shapes = [
        [1, 4, 6, 4, 1, 0, 1],             # (n+1)^4 + n^6 structure
        [-1, -3, 0, 1, 4, 6, 4],           # conductor-4 with leading 4
        [1, 6, 15, 20, 15, 6, 1],          # (n+1)^6 structure
    ]

    if cluster_name == "N24":
        z5_beta_shapes.append([1, 24, 72, 24, 0, 0, 1])  # conductor-24
        z5_beta_shapes.append([1, 1, 8, 48, 0, 0, 1])    # K2 cusp extended
    elif cluster_name == "N6":
        z5_beta_shapes.append([1, 6, 6, 6, 6, 6, 1])     # conductor-6 symmetric
        z5_beta_shapes.append([0, 1, 3, 6, 3, 1, 6])     # conductor-6 leading

    for alpha in z5_alpha_shapes:
        for beta in z5_beta_shapes:
            seeds.append({
                "alpha": alpha, "beta": beta,
                "target": "zeta5", "mode": "ratio",
                "order": 6, "n_terms": 500,
                "_source": f"crafted_{cluster_name}",
            })

    return seeds


def run_pilot(cluster_name, priority_map, seeds, seed_file, iters=20, batch=64,
              prec=500, rng_seed=None):
    """Run a single pilot sweep."""
    # Write seeds
    with open(seed_file, "w") as f:
        json.dump(seeds, f, indent=2)

    print(f"\n  Cluster {cluster_name}: {len(seeds)} seeds, {iters}x{batch}")
    for sig, w in sorted(priority_map.items(), key=lambda x: -x[1])[:5]:
        print(f"    {w:4.1f}  {sig}")

    from ramanujan_agent_v2_fast import RamanujanAgent
    if rng_seed is not None:
        random.seed(rng_seed)

    agent = RamanujanAgent(
        target="zeta5",
        seed_file=seed_file,
        priority_map=priority_map,
        deep_mode=True,
    )
    t0 = time.time()
    agent.run(
        n_iters=iters, batch=batch, verbose=False,
        workers=0, executor_kind="process",
    )
    elapsed = time.time() - t0

    tested = agent.stats.tested
    novel = agent.stats.novel
    discoveries = agent.stats.discoveries
    rate = novel / tested * 100 if tested > 0 else 0

    result = {
        "cluster": cluster_name,
        "seeds": len(seeds),
        "iters": iters,
        "batch": batch,
        "tested": tested,
        "discoveries": discoveries,
        "novel": novel,
        "rate_pct": round(rate, 3),
        "elapsed_s": round(elapsed, 1),
        "discovery_details": [d.to_dict() if hasattr(d, 'to_dict') else str(d)
                              for d in agent.discoveries],
    }

    print(f"    Result: {tested} tested, {discoveries} discoveries, "
          f"{novel} novel ({rate:.2f}%), {elapsed:.0f}s")

    return result


def main():
    print("=" * 70)
    print("  CONDUCTOR-STRATIFIED (6,6) PILOT")
    print("=" * 70)

    results = []

    # ── Cluster A: N=24 ──
    seeds_a = build_conductor_seeds("N24")
    result_a = run_pilot(
        "N24", PRIORITY_N24, seeds_a,
        "pilot_seeds_N24.json", iters=20, batch=64, rng_seed=1111,
    )
    results.append(result_a)

    # ── Cluster B: N=6 ──
    seeds_b = build_conductor_seeds("N6")
    result_b = run_pilot(
        "N6", PRIORITY_N6, seeds_b,
        "pilot_seeds_N6.json", iters=20, batch=64, rng_seed=2222,
    )
    results.append(result_b)

    # ── Cluster C: Generic ──
    seeds_c = build_conductor_seeds("generic")
    result_c = run_pilot(
        "generic", PRIORITY_GENERIC, seeds_c,
        "pilot_seeds_generic.json", iters=20, batch=64, rng_seed=3333,
    )
    results.append(result_c)

    # ── Comparison ──
    print(f"\n{'='*70}")
    print("  PILOT COMPARISON")
    print(f"{'='*70}")
    print(f"  {'Cluster':<12s} {'Seeds':>6s} {'Tested':>8s} {'Disc':>6s} {'Novel':>6s} {'Rate%':>8s} {'Time':>8s}")
    print(f"  {'─'*60}")

    best = None
    for r in results:
        print(f"  {r['cluster']:<12s} {r['seeds']:>6d} {r['tested']:>8d} "
              f"{r['discoveries']:>6d} {r['novel']:>6d} {r['rate_pct']:>7.2f}% {r['elapsed_s']:>7.1f}s")
        if best is None or r['rate_pct'] > best['rate_pct']:
            best = r

    print(f"\n  WINNER: {best['cluster']} with {best['rate_pct']:.2f}% novel rate")
    print(f"  Recommendation: Scale {best['cluster']} to full (6,6) sweep")

    # Save results
    out_path = "66_pilot_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")

    # Decision
    print(f"\n{'='*70}")
    print("  DECISION")
    print(f"{'='*70}")
    if best['rate_pct'] > 3.0:
        print(f"  Hit rate {best['rate_pct']:.1f}% > 3% threshold")
        print(f"  -> GREEN LIGHT: Full (6,6) sweep on {best['cluster']} cluster")
        print(f"  -> Command: python deep_sweep.py --target zeta5 \\")
        print(f"              --seed-file pilot_seeds_{best['cluster']}.json \\")
        print(f"              --iters 100 --batch 128 --prec 500 --deep")
    else:
        print(f"  Hit rate {best['rate_pct']:.1f}% <= 3% threshold")
        print(f"  -> HOLD: Recycle cycles into V_quad parametric frontier")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
