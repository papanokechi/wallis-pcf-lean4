#!/usr/bin/env python3
"""Symmetry Group Analysis for GCF Drift Clusters.

Analyzes the discrete transformations mapping Kloosterman seeds to their
mutant descendants.  For each drift cluster, computes:
  1. Explicit affine transformations (seed → discovery) in coefficient space
  2. Whether these transformations form a group (closure, inverses)
  3. Connection to Atkin-Lehner involutions at level N=24
  4. The natural coordinate system of the GCF identity space

Usage:
    python symmetry_group_analysis.py
    python symmetry_group_analysis.py --mutant-analysis mutant_analysis.json --sweep refined_sweep.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from itertools import combinations

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _pad(vec, length, pad=0):
    v = list(vec)
    while len(v) < length:
        v.append(pad)
    return v[:length]


def _cosine_sim(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a**2 for a in v1))
    n2 = math.sqrt(sum(b**2 for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _l2(v):
    return math.sqrt(sum(x**2 for x in v))


def _vec_sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _vec_add(a, b):
    return [x + y for x, y in zip(a, b)]


def _vec_scale(v, s):
    return [x * s for x in v]


def _vec_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def compute_transformation_matrices(cluster_records, seeds):
    """For each cluster, compute the affine map from nearest seed to each member.

    Returns list of {seed_coeffs, member_coeffs, translation, scale_ratios}.
    """
    transforms = []
    for rec in cluster_records:
        alpha = rec["alpha"]
        beta = rec["beta"]
        nearest_id = rec.get("nearest_seed", "")
        # Find the seed
        seed = None
        for s in seeds:
            if s.get("spec_id") == nearest_id:
                seed = s
                break
        if seed is None:
            continue

        sa = seed.get("alpha", [])
        sb = seed.get("beta", [])
        max_a = max(len(alpha), len(sa))
        max_b = max(len(beta), len(sb))

        pa = _pad(alpha, max_a)
        psa = _pad(sa, max_a)
        pb = _pad(beta, max_b)
        psb = _pad(sb, max_b)

        # Translation vector (additive difference)
        trans_a = _vec_sub(pa, psa)
        trans_b = _vec_sub(pb, psb)

        # Scale ratios where seed coefficient is nonzero
        scale_a = []
        for i in range(max_a):
            if psa[i] != 0:
                scale_a.append(pa[i] / psa[i])
            else:
                scale_a.append(None)
        scale_b = []
        for i in range(max_b):
            if psb[i] != 0:
                scale_b.append(pb[i] / psb[i])
            else:
                scale_b.append(None)

        transforms.append({
            "spec_id": rec["spec_id"],
            "seed_id": nearest_id,
            "discovery_alpha": pa,
            "discovery_beta": pb,
            "seed_alpha": psa,
            "seed_beta": psb,
            "translation_alpha": trans_a,
            "translation_beta": trans_b,
            "scale_ratios_alpha": scale_a,
            "scale_ratios_beta": scale_b,
            "full_translation": trans_a + trans_b,
        })
    return transforms


def check_group_closure(transforms, tol=0.15):
    """Check if the transformation vectors form a closed group under composition.

    Tests: for each pair (T_i, T_j), does T_i + T_j ≈ some T_k in the set?
    (Additive group structure on the translation vectors.)
    """
    if len(transforms) < 2:
        return {"is_group": False, "reason": "too_few_transforms"}

    trans_vecs = [t["full_translation"] for t in transforms]
    max_dim = max(len(v) for v in trans_vecs)
    padded = [_pad(v, max_dim) for v in trans_vecs]

    # Check additive closure: T_i + T_j ≈ T_k?
    closure_hits = 0
    closure_tests = 0
    closure_details = []

    for i, j in combinations(range(len(padded)), 2):
        composed = _vec_add(padded[i], padded[j])
        # Find closest existing transform
        best_dist = float("inf")
        best_k = -1
        for k in range(len(padded)):
            dist = _l2(_vec_sub(composed, padded[k]))
            norm = max(_l2(composed), 1.0)
            if dist / norm < best_dist:
                best_dist = dist / norm
                best_k = k
        closure_tests += 1
        if best_dist < tol:
            closure_hits += 1
            closure_details.append({
                "i": transforms[i]["spec_id"],
                "j": transforms[j]["spec_id"],
                "k": transforms[best_k]["spec_id"],
                "relative_error": round(best_dist, 4),
            })

    # Check if zero vector is approximately present (identity element)
    zero = [0] * max_dim
    min_zero_dist = min(_l2(v) for v in padded)
    has_identity = min_zero_dist < 1.0  # Loose: identity should be small

    # Check inverses: for each T, does -T ≈ some other T?
    inverse_hits = 0
    for i in range(len(padded)):
        neg = _vec_scale(padded[i], -1)
        for j in range(len(padded)):
            if i == j:
                continue
            dist = _l2(_vec_sub(neg, padded[j]))
            norm = max(_l2(neg), 1.0)
            if dist / norm < tol:
                inverse_hits += 1
                break

    closure_rate = closure_hits / max(closure_tests, 1)

    return {
        "is_group": closure_rate > 0.5 and has_identity,
        "closure_rate": round(closure_rate, 4),
        "closure_hits": closure_hits,
        "closure_tests": closure_tests,
        "has_identity_approx": has_identity,
        "min_identity_norm": round(min_zero_dist, 4),
        "inverse_count": inverse_hits,
        "total_transforms": len(transforms),
        "closure_examples": closure_details[:10],
    }


def analyze_atkin_lehner(transforms, conductor=24):
    """Check if transformations resemble Atkin-Lehner involutions at level N.

    Atkin-Lehner involutions W_q for q | N act on modular forms by
    specific sign changes and permutations of Fourier coefficients.
    For N=24, the involutions are W_3, W_8, W_24.
    """
    results = []

    # Extract just the beta translations (these encode the recurrence structure)
    beta_trans = [t["translation_beta"] for t in transforms]
    if not beta_trans:
        return results

    max_len = max(len(b) for b in beta_trans)
    padded = [_pad(b, max_len) for b in beta_trans]

    # W_q signature: look for transformations that are approximately
    # sign patterns modulo the conductor divisors
    divisors = []
    for q in [2, 3, 4, 6, 8, 12, 24]:
        if conductor % q == 0:
            divisors.append(q)

    for q in divisors:
        # W_q acts by negating coefficients at positions divisible by q
        # and permuting others. Check if any transform matches this pattern.
        for idx, trans in enumerate(padded):
            # Build the "W_q signature": sign pattern at positions mod q
            sign_pattern = []
            for i, c in enumerate(trans):
                if c == 0:
                    sign_pattern.append(0)
                elif (i % q == 0) and c < 0:
                    sign_pattern.append(-1)
                elif (i % q == 0) and c > 0:
                    sign_pattern.append(+1)
                else:
                    sign_pattern.append(0)

            # Check if the sign pattern is consistent with W_q
            nonzero_signs = [s for s in sign_pattern if s != 0]
            if len(nonzero_signs) >= 2:
                # All nonzero signs should be the same for W_q
                if len(set(nonzero_signs)) == 1:
                    results.append({
                        "transform_idx": idx,
                        "spec_id": transforms[idx]["spec_id"],
                        "candidate_involution": f"W_{q}",
                        "conductor": conductor,
                        "sign_pattern": sign_pattern,
                        "confidence": "suggestive",
                    })

    return results


def principal_directions(transforms):
    """Compute principal directions of the drift vectors (PCA without numpy)."""
    trans_vecs = [t["full_translation"] for t in transforms]
    if len(trans_vecs) < 2:
        return {"directions": [], "explained_variance": []}

    max_dim = max(len(v) for v in trans_vecs)
    padded = [_pad(v, max_dim) for v in trans_vecs]
    n = len(padded)

    # Center the data
    mean = [sum(padded[i][j] for i in range(n)) / n for j in range(max_dim)]
    centered = [[padded[i][j] - mean[j] for j in range(max_dim)] for i in range(n)]

    # Power iteration for top 3 principal directions
    directions = []
    explained = []
    residuals = [list(c) for c in centered]

    for _ in range(min(3, max_dim)):
        # Random initial direction
        import random
        v = [random.gauss(0, 1) for _ in range(max_dim)]
        norm = _l2(v)
        if norm == 0:
            break
        v = _vec_scale(v, 1.0 / norm)

        # Power iteration (20 steps)
        for _ in range(20):
            # Multiply by covariance matrix: v' = X^T X v
            xv = [_vec_dot(r, v) for r in residuals]
            new_v = [sum(xv[i] * residuals[i][j] for i in range(n))
                     for j in range(max_dim)]
            norm = _l2(new_v)
            if norm < 1e-10:
                break
            v = _vec_scale(new_v, 1.0 / norm)

        # Eigenvalue (variance along this direction)
        projections = [_vec_dot(r, v) for r in residuals]
        eigenval = sum(p**2 for p in projections) / max(n - 1, 1)
        directions.append([round(x, 4) for x in v])
        explained.append(round(eigenval, 4))

        # Deflate: remove this component from residuals
        for i in range(n):
            proj = _vec_dot(residuals[i], v)
            residuals[i] = [residuals[i][j] - proj * v[j] for j in range(max_dim)]

    total_var = sum(explained)
    pct = [round(e / total_var * 100, 1) if total_var > 0 else 0 for e in explained]

    return {
        "directions": directions,
        "eigenvalues": explained,
        "explained_variance_pct": pct,
        "effective_dimension": sum(1 for p in pct if p > 5),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Symmetry group analysis for GCF drift clusters.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mutant-analysis", default="mutant_analysis.json")
    parser.add_argument("--seeds", default="kloosterman_seeds.json")
    parser.add_argument("--sweep", default="refined_sweep.json")
    parser.add_argument("--json-out", default="symmetry_analysis.json")
    args = parser.parse_args()

    t0 = time.perf_counter()

    with open(args.mutant_analysis) as f:
        mutant_data = json.load(f)
    with open(args.seeds) as f:
        seeds = json.load(f)

    clusters = mutant_data["clusters"]
    records = mutant_data["mutant_records"]

    print(f"{'='*60}")
    print(f"  Symmetry Group Analysis")
    print(f"{'='*60}")
    print(f"  Clusters: {len(clusters)}")
    print(f"  Records:  {len(records)}")

    all_cluster_results = []

    for cl in clusters:
        if cl["size"] < 2:
            continue

        print(f"\n  ── Cluster {cl['cluster_id']} ({cl['size']} members, sim={cl['mean_internal_sim']:.3f}) ──")

        # Get records for this cluster
        cl_records = [r for r in records if r["spec_id"] in cl["members"]]

        # Compute transformations
        transforms = compute_transformation_matrices(cl_records, seeds)
        print(f"    Transforms computed: {len(transforms)}")

        # Check group closure
        group = check_group_closure(transforms)
        print(f"    Group closure: rate={group['closure_rate']:.3f}, "
              f"identity={group['has_identity_approx']}, "
              f"inverses={group['inverse_count']}/{group['total_transforms']}")
        if group["is_group"]:
            print(f"    *** APPROXIMATE GROUP STRUCTURE DETECTED ***")

        # Check Atkin-Lehner signatures
        al_results = analyze_atkin_lehner(transforms, conductor=24)
        if al_results:
            print(f"    Atkin-Lehner candidates: {len(al_results)}")
            for r in al_results[:3]:
                print(f"      {r['spec_id']} ~ {r['candidate_involution']} "
                      f"(conductor {r['conductor']})")

        # Principal directions
        pca = principal_directions(transforms)
        if pca["directions"]:
            print(f"    Principal directions: {pca['effective_dimension']}D effective")
            print(f"    Variance explained: {pca['explained_variance_pct']}")

        all_cluster_results.append({
            "cluster_id": cl["cluster_id"],
            "size": cl["size"],
            "internal_sim": cl["mean_internal_sim"],
            "members": cl["members"],
            "group_structure": group,
            "atkin_lehner_candidates": al_results,
            "principal_component_analysis": pca,
            "transforms": transforms,
        })

    # Cross-cluster analysis: check if cluster centroids form a higher-order structure
    print(f"\n  ── Cross-Cluster Analysis ──")
    centroids = [cl["centroid"] for cl in clusters if cl["size"] >= 2]
    if len(centroids) >= 2:
        max_dim = max(len(c) for c in centroids)
        padded_centroids = [_pad(c, max_dim) for c in centroids]
        for i, j in combinations(range(len(padded_centroids)), 2):
            sim = _cosine_sim(padded_centroids[i], padded_centroids[j])
            if abs(sim) > 0.7:
                print(f"    Centroids {i},{j}: cosine_sim={sim:.3f} "
                      f"(parallel or anti-parallel)")

    wall = round(time.perf_counter() - t0, 3)

    output = {
        "analysis": "symmetry_group",
        "total_clusters_analyzed": len(all_cluster_results),
        "groups_detected": sum(1 for r in all_cluster_results
                               if r["group_structure"]["is_group"]),
        "atkin_lehner_candidates": sum(len(r["atkin_lehner_candidates"])
                                       for r in all_cluster_results),
        "cluster_results": all_cluster_results,
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  Groups detected:         {output['groups_detected']}")
    print(f"  Atkin-Lehner candidates:  {output['atkin_lehner_candidates']}")
    print(f"  Wall time:               {wall}s")
    print(f"  JSON -> {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
