#!/usr/bin/env python3
"""Mutant Harvester for (6,6) Results — Super-Seed v2 Generation.

Extracts the 40 deep-6 discoveries from zeta66_full_results.json,
clusters their coefficient structures, and produces upgraded super-seeds
that encode degree-6 structural DNA for the next generation of sweeps.

Usage:
    python mutant_harvester_66.py
    python mutant_harvester_66.py --input zeta66_full_results.json --min-deg 5
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _pad(vec, length, pad=0):
    v = list(vec)
    while len(v) < length:
        v.append(pad)
    return v[:length]


def _l2(v):
    return math.sqrt(sum(x**2 for x in v))


def _cosine_sim(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = _l2(v1)
    n2 = _l2(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _cluster_greedy(vectors, labels, threshold=0.75):
    clusters = []
    assigned = set()
    for i in range(len(vectors)):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, len(vectors)):
            if j in assigned:
                continue
            if _cosine_sim(vectors[i], vectors[j]) >= threshold:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)
    return clusters


def extract_deep_discoveries(input_path: str, min_deg: int = 5) -> list[dict]:
    """Extract discoveries where alpha_deg or beta_deg >= min_deg."""
    with open(input_path) as f:
        data = json.load(f)

    deep = []
    for result in data.get("results", []):
        target = result.get("target", "")
        for hv in result.get("high_value", []):
            adeg = hv.get("alpha_deg", 0)
            bdeg = hv.get("beta_deg", 0)
            if adeg >= min_deg or bdeg >= min_deg:
                hv["_target"] = target
                deep.append(hv)
    return deep


def build_super_seeds_v2(deep_entries: list[dict],
                         cluster_threshold: float = 0.70) -> tuple[list[dict], list[dict]]:
    """Cluster deep discoveries and produce super-seeds from centroids."""
    if not deep_entries:
        return [], []

    # Build feature vectors: alpha + beta coefficients
    max_a = max(len(e.get("alpha", [])) for e in deep_entries)
    max_b = max(len(e.get("beta", [])) for e in deep_entries)
    vectors = []
    labels = []
    for e in deep_entries:
        v = _pad(e.get("alpha", []), max_a) + _pad(e.get("beta", []), max_b)
        vectors.append(v)
        labels.append(e.get("spec_id", ""))

    # Cluster
    clusters = _cluster_greedy(vectors, labels, cluster_threshold)

    cluster_records = []
    super_seeds = []

    for ci, indices in enumerate(clusters):
        members = [labels[i] for i in indices]
        member_entries = [deep_entries[i] for i in indices]

        # Compute centroid
        dim = len(vectors[0])
        centroid = [0.0] * dim
        for idx in indices:
            for j in range(dim):
                centroid[j] += vectors[idx][j]
        centroid = [c / len(indices) for c in centroid]

        # Internal similarity
        sims = []
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                sims.append(_cosine_sim(vectors[indices[i]], vectors[indices[j]]))
        mean_sim = sum(sims) / max(1, len(sims)) if sims else 1.0

        # Most common target and mode
        target_dist = Counter(e.get("_target", "") for e in member_entries)
        mode_dist = Counter(e.get("mode", "backward") for e in member_entries)
        best_target = target_dist.most_common(1)[0][0] if target_dist else "zeta5"
        best_mode = mode_dist.most_common(1)[0][0] if mode_dist else "ratio"

        # Average order
        avg_order = sum(e.get("order", 0) for e in member_entries) / max(1, len(member_entries))

        cluster_records.append({
            "cluster_id": ci,
            "size": len(indices),
            "members": members,
            "mean_sim": round(mean_sim, 4),
            "target": best_target,
            "mode": best_mode,
        })

        # Generate super-seed from centroid
        if len(indices) >= 1:
            alpha_seed = [round(c) for c in centroid[:max_a]]
            beta_seed = [round(c) for c in centroid[max_a:max_a + max_b]]
            # Ensure structural integrity
            if alpha_seed and alpha_seed[-1] == 0:
                alpha_seed[-1] = 1
            if beta_seed and beta_seed[-1] == 0:
                beta_seed[-1] = 1
            if beta_seed and beta_seed[0] == 0 and best_mode == "backward":
                beta_seed[0] = 1

            super_seeds.append({
                "alpha": alpha_seed,
                "beta": beta_seed,
                "target": best_target,
                "mode": best_mode,
                "order": round(avg_order),
                "n_terms": 700,
                "spec_id": f"SS2_C{ci:02d}_{best_target}",
                "source_cluster_size": len(indices),
                "source_members": members[:5],
                "generation": 2,
            })

    return cluster_records, super_seeds


def main():
    parser = argparse.ArgumentParser(
        description="Harvest deep-6 discoveries into v2 super-seeds.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default="zeta66_full_results.json")
    parser.add_argument("--min-deg", type=int, default=5,
                        help="Minimum alpha or beta degree to qualify as deep.")
    parser.add_argument("--cluster-threshold", type=float, default=0.70)
    parser.add_argument("--json-out", default="mutant_harvest_66.json")
    parser.add_argument("--seeds-out", default="super_seeds_v2.json")
    args = parser.parse_args()

    t0 = time.perf_counter()

    # Extract deep discoveries
    deep = extract_deep_discoveries(args.input, args.min_deg)
    print(f"Extracted {len(deep)} deep discoveries (deg>={args.min_deg})")

    # By-target breakdown
    by_target = Counter(e.get("_target", "") for e in deep)
    print(f"  By target: {dict(by_target)}")

    # Build clusters and seeds
    clusters, seeds = build_super_seeds_v2(deep, args.cluster_threshold)
    print(f"  Clusters: {len(clusters)}")
    print(f"  Super-seeds v2: {len(seeds)}")

    # Also merge with existing v1 super-seeds (escalated to match v2 format)
    from pathlib import Path
    v1_path = Path("super_seeds.json")
    v1_seeds = []
    if v1_path.exists():
        with open(v1_path) as f:
            v1_seeds = json.load(f)
        print(f"  Loaded {len(v1_seeds)} v1 super-seeds for merge")

    # Combined pool: v2 first (higher quality), then v1
    combined = list(seeds)
    seen_fps = {str(s["alpha"]) + str(s["beta"]) for s in combined}
    for s in v1_seeds:
        fp = str(s.get("alpha", [])) + str(s.get("beta", []))
        if fp not in seen_fps:
            s["generation"] = 1
            combined.append(s)
            seen_fps.add(fp)

    wall = round(time.perf_counter() - t0, 3)

    # Save
    output = {
        "harvest": "66_deep",
        "deep_count": len(deep),
        "by_target": dict(by_target),
        "clusters": clusters,
        "super_seeds_v2_count": len(seeds),
        "combined_pool_size": len(combined),
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    with open(args.seeds_out, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Mutant Harvest (6,6) Report")
    print(f"{'='*60}")
    print(f"  Deep discoveries:  {len(deep)}")
    print(f"  Clusters:          {len(clusters)}")
    print(f"  New super-seeds:   {len(seeds)}")
    print(f"  Combined pool:     {len(combined)} (v1+v2)")
    for cl in clusters:
        print(f"    C{cl['cluster_id']}: {cl['size']} members, "
              f"sim={cl['mean_sim']:.3f}, target={cl['target']}")
    print(f"  Wall time:         {wall}s")
    print(f"  JSON -> {args.json_out}")
    print(f"  Seeds -> {args.seeds_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
