#!/usr/bin/env python3
"""Mutant Analyzer: Extract structural DNA from evolutionary GCF discoveries.

For each Grade-A "mutant" discovery (>50% coefficient drift from Kloosterman seed):
  1. Compute the drift vector in coefficient space (seed → final form)
  2. Build convergence fingerprints (partial denominator sequences)
  3. Cluster drift vectors to discover symmetry groups
  4. Output new "super-seed" templates derived from cluster centroids

Usage:
    python mutant_analyzer.py --validation validation_results.json --sweep refined_sweep.json
    python mutant_analyzer.py --seeds kloosterman_seeds.json --top 30
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import Counter, defaultdict

import mpmath as mp

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _eval_backward_partial_denoms(alpha, beta, n_max, dps=50):
    """Extract the sequence of partial denominators q_n for fingerprinting."""
    denoms = []
    with mp.workdps(dps):
        for n in range(1, min(n_max + 1, 51)):
            an = sum(c * mp.mpf(n)**i for i, c in enumerate(alpha))
            bn = sum(c * mp.mpf(n)**i for i, c in enumerate(beta))
            denoms.append(float(bn))
    return denoms


def _pad_to_length(vec, length, pad=0):
    """Pad a coefficient vector to a target length."""
    v = list(vec)
    while len(v) < length:
        v.append(pad)
    return v[:length]


def _drift_vector(discovery_alpha, discovery_beta, seed_alpha, seed_beta):
    """Compute the normalized drift vector from seed to discovery."""
    max_len_a = max(len(discovery_alpha), len(seed_alpha))
    max_len_b = max(len(discovery_beta), len(seed_beta))

    da = _pad_to_length(discovery_alpha, max_len_a)
    sa = _pad_to_length(seed_alpha, max_len_a)
    db = _pad_to_length(discovery_beta, max_len_b)
    sb = _pad_to_length(seed_beta, max_len_b)

    drift_a = [d - s for d, s in zip(da, sa)]
    drift_b = [d - s for d, s in zip(db, sb)]
    return drift_a + drift_b


def _cosine_similarity(v1, v2):
    """Cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a**2 for a in v1))
    n2 = math.sqrt(sum(b**2 for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _l2_norm(v):
    return math.sqrt(sum(x**2 for x in v))


def _simple_cluster(vectors, labels, threshold=0.8):
    """Simple greedy clustering by cosine similarity."""
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
            sim = _cosine_similarity(vectors[i], vectors[j])
            if sim >= threshold:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)
    return clusters


def find_nearest_seed(entry, seeds):
    """Find nearest Kloosterman seed for a discovery entry."""
    alpha = entry.get("alpha", [])
    beta = entry.get("beta", [])
    mode = entry.get("mode", "backward")

    best_dist = float("inf")
    best_seed = None
    for seed in seeds:
        sa = seed.get("alpha", [])
        sb = seed.get("beta", [])
        mode_penalty = 0.0 if seed.get("mode") == mode else 0.5
        max_a = max(len(alpha), len(sa))
        max_b = max(len(beta), len(sb))
        pa = _pad_to_length(alpha, max_a)
        psa = _pad_to_length(sa, max_a)
        pb = _pad_to_length(beta, max_b)
        psb = _pad_to_length(sb, max_b)
        a_dist = sum(abs(a - s) for a, s in zip(pa, psa))
        b_dist = sum(abs(b - s) for b, s in zip(pb, psb))
        a_norm = max(1, sum(abs(s) for s in psa))
        b_norm = max(1, sum(abs(s) for s in psb))
        dist = (a_dist / a_norm + b_dist / b_norm) / 2 + mode_penalty
        if dist < best_dist:
            best_dist = dist
            best_seed = seed
    return best_seed, best_dist


def analyze_mutants(sweep_path: str, seeds_path: str,
                    validation_path: str | None = None,
                    top_n: int = 30) -> dict:
    """Main mutant analysis pipeline."""
    # Load data
    with open(sweep_path) as f:
        sweep = json.load(f)
    with open(seeds_path) as f:
        seeds = json.load(f)

    # Get all discoveries with full specs
    entries = []
    for r in sweep.get("results", []):
        for hv in r.get("high_value", []):
            if hv.get("alpha"):
                hv["_target"] = r["target"]
                entries.append(hv)

    # Load validation grades if available
    grades = {}
    if validation_path:
        try:
            with open(validation_path) as f:
                val = json.load(f)
            for v in val.get("validated", []):
                grades[v["spec_id"]] = v.get("grade", "?")
        except Exception:
            pass

    # Analyze each entry
    mutant_records = []
    all_drifts = []
    all_labels = []

    for entry in entries[:top_n]:
        seed, dist = find_nearest_seed(entry, seeds)
        is_mutant = dist > 0.5
        grade = grades.get(entry.get("spec_id", ""), "?")

        if seed:
            drift = _drift_vector(
                entry["alpha"], entry["beta"],
                seed["alpha"], seed["beta"]
            )
        else:
            drift = list(entry["alpha"]) + list(entry["beta"])

        # Convergence fingerprint
        fingerprint = _eval_backward_partial_denoms(
            entry["alpha"], entry["beta"], 50
        ) if entry.get("mode", "backward") == "backward" else []

        record = {
            "spec_id": entry.get("spec_id", ""),
            "target": entry.get("_target", ""),
            "constant": entry.get("constant", ""),
            "alpha": entry["alpha"],
            "beta": entry["beta"],
            "mode": entry.get("mode", "backward"),
            "precision": entry.get("precision", 0),
            "grade": grade,
            "nearest_seed": seed.get("spec_id", "") if seed else "",
            "seed_conductor": seed.get("_conductor", 0) if seed else 0,
            "drift_distance": round(dist, 4),
            "is_mutant": is_mutant,
            "drift_vector": drift,
            "drift_magnitude": round(_l2_norm(drift), 4),
            "fingerprint": fingerprint[:20],
        }
        mutant_records.append(record)

        if is_mutant and drift:
            all_drifts.append(drift)
            all_labels.append(entry.get("spec_id", ""))

    # Cluster drift vectors
    cluster_results = []
    if len(all_drifts) >= 2:
        # Normalize drift vectors to same dimension
        max_dim = max(len(d) for d in all_drifts)
        norm_drifts = [_pad_to_length(d, max_dim) for d in all_drifts]

        # Cluster by cosine similarity
        clusters = _simple_cluster(norm_drifts, all_labels, threshold=0.7)

        for ci, indices in enumerate(clusters):
            members = [all_labels[i] for i in indices]
            # Compute centroid
            centroid = [0.0] * max_dim
            for idx in indices:
                for j, v in enumerate(norm_drifts[idx]):
                    centroid[j] += v
            centroid = [c / len(indices) for c in centroid]

            # Pairwise similarity within cluster
            sims = []
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    sims.append(_cosine_similarity(norm_drifts[indices[i]],
                                                    norm_drifts[indices[j]]))

            cluster_results.append({
                "cluster_id": ci,
                "size": len(indices),
                "members": members,
                "centroid": [round(c, 3) for c in centroid],
                "mean_internal_sim": round(sum(sims) / max(1, len(sims)), 4) if sims else 1.0,
            })

    # Generate super-seeds from cluster centroids
    super_seeds = []
    for cl in cluster_results:
        if cl["size"] >= 2:
            centroid = cl["centroid"]
            # Split centroid back into alpha/beta parts
            # Find the most common alpha/beta lengths from members
            member_records = [r for r in mutant_records if r["spec_id"] in cl["members"]]
            if not member_records:
                continue
            # Use the first member's structure
            ref = member_records[0]
            alen = len(ref["alpha"])
            blen = len(ref["beta"])
            # Round centroid to nearest integers
            alpha_seed = [round(c) for c in centroid[:alen]]
            beta_seed = [round(c) for c in centroid[alen:alen + blen]]
            # Ensure nonzero leading coefficients
            if alpha_seed and alpha_seed[-1] == 0:
                alpha_seed[-1] = 1
            if beta_seed and beta_seed[-1] == 0:
                beta_seed[-1] = 1

            super_seeds.append({
                "alpha": alpha_seed,
                "beta": beta_seed,
                "target": ref["target"],
                "mode": ref["mode"],
                "order": ref.get("order", 0) if "order" in ref else 0,
                "n_terms": 500,
                "spec_id": f"SUPER_CLUSTER{cl['cluster_id']:02d}",
                "source_cluster_size": cl["size"],
                "source_members": cl["members"][:5],
            })

    return {
        "mutant_records": mutant_records,
        "clusters": cluster_results,
        "super_seeds": super_seeds,
        "summary": {
            "total_analyzed": len(mutant_records),
            "mutants": sum(1 for r in mutant_records if r["is_mutant"]),
            "clusters": len(cluster_results),
            "super_seeds": len(super_seeds),
            "parallel_drift_detected": any(
                cl["mean_internal_sim"] > 0.85 and cl["size"] >= 3
                for cl in cluster_results
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze mutant GCF discoveries for structural patterns.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sweep", default="refined_sweep.json")
    parser.add_argument("--seeds", default="kloosterman_seeds.json")
    parser.add_argument("--validation", default="validation_results.json")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--json-out", default="mutant_analysis.json")
    parser.add_argument("--super-seeds-out", default="super_seeds.json")
    args = parser.parse_args()

    from pathlib import Path
    val_path = args.validation if Path(args.validation).exists() else None

    t0 = time.perf_counter()
    result = analyze_mutants(
        sweep_path=args.sweep,
        seeds_path=args.seeds,
        validation_path=val_path,
        top_n=args.top,
    )
    wall = round(time.perf_counter() - t0, 3)

    summary = result["summary"]
    clusters = result["clusters"]
    super_seeds = result["super_seeds"]

    # Save results
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    if super_seeds:
        with open(args.super_seeds_out, "w", encoding="utf-8") as f:
            json.dump(super_seeds, f, indent=2)

    # Report
    print(f"{'='*60}")
    print(f"  Mutant Analysis Report")
    print(f"{'='*60}")
    print(f"  Analyzed:     {summary['total_analyzed']}")
    print(f"  Mutants:      {summary['mutants']}")
    print(f"  Clusters:     {summary['clusters']}")
    print(f"  Super-seeds:  {summary['super_seeds']}")
    print(f"  Parallel drift: {'YES' if summary['parallel_drift_detected'] else 'no'}")
    print(f"  Wall time:    {wall}s")

    if clusters:
        print(f"\n  Drift vector clusters:")
        for cl in clusters:
            print(f"    Cluster {cl['cluster_id']}: {cl['size']} members, "
                  f"internal_sim={cl['mean_internal_sim']:.3f}")
            for m in cl["members"][:5]:
                print(f"      - {m}")

    if super_seeds:
        print(f"\n  Generated super-seeds ({len(super_seeds)}):")
        for ss in super_seeds:
            print(f"    [{ss['spec_id']}]  target={ss['target']}  "
                  f"alpha={ss['alpha']}  beta={ss['beta']}")

    print(f"\n  JSON -> {args.json_out}")
    if super_seeds:
        print(f"  Super-seeds -> {args.super_seeds_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
