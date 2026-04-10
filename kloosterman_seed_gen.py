#!/usr/bin/env python3
"""Kloosterman Spectral Seed Generator.

Generates GCF seeds tuned to specific arithmetic conductors (N=8, 24, 48)
whose Kloosterman sum spectra are conjectured to govern the appearance of
integer relations between odd zeta values and powers of π.

The key insight: Apéry's proof of irr(ζ(3)) uses a recurrence whose
characteristic polynomial factors over the N=6 cyclotomic field.
By analogy, relations for ζ(5) and ζ(7) should arise from recurrences
governed by conductors N=24, 48, where the Kloosterman spectrum is richer.

Output: kloosterman_seeds.json — a pool of GCFSpec dicts ready for
        --seed-file consumption by the Ramanujan agent.

Usage:
    python kloosterman_seed_gen.py
    python kloosterman_seed_gen.py --conductors 8,24,48 --targets zeta3,zeta5,zeta7
    python kloosterman_seed_gen.py --output kloosterman_seeds.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from itertools import product


# ── Conductor-specific coefficient templates ─────────────────────
# These encode the structure of recurrence operators whose characteristic
# roots lie on Kloosterman sum spectra for the given conductor N.
#
# For conductor N, the key denominators in Apéry-like recurrences are
# multiples of N, and the leading polynomial coefficients encode
# binomial/Pochhammer products modular to N.

CONDUCTOR_TEMPLATES: dict[int, list[dict]] = {
    # N=6: Classical Apéry conductor (ζ(3) proven irrational)
    6: [
        {"alpha_base": [0, 0, 0, 1],  # n³
         "beta_scales": [(-5, 27, -51, 34)],  # Apéry's actual coefficients
         "mode": "ratio", "order": 3,
         "target_affinity": ["zeta3"]},
    ],
    # N=8: First extension — cusp forms of level 8
    8: [
        {"alpha_base": [0, 0, 0, 1],
         "beta_scales": [(-7, 40, -80, 56), (-3, 20, -45, 32)],
         "mode": "ratio", "order": 3,
         "target_affinity": ["zeta3", "zeta5"]},
        {"alpha_base": [0, 0, 0, 0, 1],
         "beta_scales": [(-8, 56, -128, 128, -48)],
         "mode": "ratio", "order": 4,
         "target_affinity": ["zeta5"]},
    ],
    # N=24: Prime conductor for ζ(5) — Kloosterman spectral peak
    24: [
        # Quintic recurrence: n⁵ operator, β coefficients encode
        # binomial(2n,n)² structure modular to 24
        {"alpha_base": [0, 0, 0, 0, 0, 1],
         "beta_scales": [
             (-11, 120, -540, 1320, -1760, 1024),
             (-7,  85, -400, 1000, -1344, 768),
             (-13, 156, -780, 2080, -2880, 1536),
         ],
         "mode": "ratio", "order": 5,
         "target_affinity": ["zeta5"]},
        # Cubic sub-recurrence at conductor 24 (cross-talk with ζ(3))
        {"alpha_base": [0, 0, 0, 1],
         "beta_scales": [
             (-5, 33, -75, 58),
             (-7, 48, -114, 90),
             (-3, 24, -60, 48),
         ],
         "mode": "ratio", "order": 3,
         "target_affinity": ["zeta3", "zeta5"]},
        # Mixed backward mode for coupling search
        {"alpha_base": [0, 0, 0, 0, 1],
         "beta_scales": [
             (0, -24, 120, -192, 96),
             (0, -12, 72, -144, 96),
         ],
         "mode": "backward", "order": 0,
         "target_affinity": ["zeta5", "zeta3"]},
    ],
    # N=48: Extended conductor for ζ(7)
    48: [
        # Septic recurrence: n⁷ operator
        {"alpha_base": [0, 0, 0, 0, 0, 0, 0, 1],
         "beta_scales": [
             (-15, 252, -1890, 8400, -23520, 42336, -45360, 21504),
             (-13, 210, -1512, 6300, -16380, 27216, -26880, 11520),
         ],
         "mode": "ratio", "order": 7,
         "target_affinity": ["zeta7"]},
        # Quintic sub-recurrence (ζ(7)↔ζ(5) coupling)
        {"alpha_base": [0, 0, 0, 0, 0, 1],
         "beta_scales": [
             (-9, 108, -540, 1440, -2016, 1152),
             (-11, 144, -780, 2240, -3360, 2048),
         ],
         "mode": "ratio", "order": 5,
         "target_affinity": ["zeta7", "zeta5"]},
    ],
}

# Perturbation strategies for generating variants from templates
PERTURBATION_STRATEGIES = [
    "identity",          # Use template as-is
    "sign_flip",         # Flip signs of alternating β coefficients
    "scale_2",           # Multiply all β by 2
    "shift_conductor",   # Add ±N to each β coefficient
    "pochhammer_twist",  # Multiply β[k] by binomial structure
]


def _binomial(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)


def _perturb_beta(beta: tuple[int, ...], strategy: str,
                  conductor: int) -> list[int]:
    """Apply a perturbation strategy to a beta coefficient vector."""
    b = list(beta)
    if strategy == "identity":
        return b
    elif strategy == "sign_flip":
        return [(-1)**i * c for i, c in enumerate(b)]
    elif strategy == "scale_2":
        return [2 * c for c in b]
    elif strategy == "shift_conductor":
        sign = random.choice([-1, 1])
        return [c + sign * conductor for c in b]
    elif strategy == "pochhammer_twist":
        deg = len(b) - 1
        return [c + _binomial(deg, i) * random.choice([-1, 0, 1])
                for i, c in enumerate(b)]
    return b


def _small_perturbation(coeffs: list[int], magnitude: int = 3) -> list[int]:
    """Add small random noise to coefficients."""
    return [c + random.randint(-magnitude, magnitude) for c in coeffs]


def generate_kloosterman_seeds(
    conductors: list[int] | None = None,
    targets: list[str] | None = None,
    variants_per_template: int = 8,
    seed: int | None = None,
) -> list[dict]:
    """Generate a pool of GCF specs tuned to Kloosterman conductors.

    Args:
        conductors: Which conductor levels to use (default: [8, 24, 48])
        targets: Filter to only these targets (default: all)
        variants_per_template: How many perturbations per base template
        seed: RNG seed for reproducibility

    Returns:
        List of GCFSpec dicts ready for JSON serialization
    """
    if seed is not None:
        random.seed(seed)

    conductors = conductors or [8, 24, 48]
    specs: list[dict] = []
    seen_fingerprints: set[str] = set()

    for N in conductors:
        templates = CONDUCTOR_TEMPLATES.get(N, [])
        for tmpl in templates:
            alpha_base = tmpl["alpha_base"]
            mode = tmpl["mode"]
            order = tmpl["order"]
            affinity = tmpl["target_affinity"]

            # Filter by target if specified
            if targets:
                matching = [t for t in affinity if t in targets]
                if not matching:
                    continue
                use_targets = matching
            else:
                use_targets = affinity

            for beta_tuple in tmpl["beta_scales"]:
                for strategy in PERTURBATION_STRATEGIES:
                    for variant_idx in range(max(1, variants_per_template // len(PERTURBATION_STRATEGIES))):
                        beta = _perturb_beta(beta_tuple, strategy, N)

                        # Small additional noise for variant diversity
                        if variant_idx > 0:
                            beta = _small_perturbation(beta, magnitude=2)
                            alpha = _small_perturbation(list(alpha_base), magnitude=1)
                        else:
                            alpha = list(alpha_base)

                        # Ensure structural integrity
                        if all(c == 0 for c in alpha[1:]):
                            continue
                        if all(c == 0 for c in beta[1:]):
                            continue
                        if beta[0] == 0 and mode == "backward":
                            beta[0] = random.choice([-1, 1])

                        # Ensure leading coefficients are nonzero
                        if alpha[-1] == 0:
                            alpha[-1] = random.choice([-1, 1])
                        if beta[-1] == 0:
                            beta[-1] = random.choice([-1, 1])

                        # Deduplicate
                        fp = f"{alpha}|{beta}|{mode}|{order}"
                        if fp in seen_fingerprints:
                            continue
                        seen_fingerprints.add(fp)

                        # n_terms scaled to precision needs
                        deg = max(len(alpha), len(beta))
                        n_terms = 500 if deg >= 6 else 400 if deg >= 4 else 300

                        for target in use_targets:
                            spec = {
                                "alpha": alpha,
                                "beta": beta,
                                "target": target,
                                "n_terms": n_terms,
                                "mode": mode,
                                "order": order,
                                "spec_id": f"KLOOST_N{N}_{target}_{len(specs):04d}",
                                "_conductor": N,
                                "_strategy": strategy,
                            }
                            specs.append(spec)

    return specs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Kloosterman spectral GCF seeds.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--conductors", default="8,24,48",
                        help="Comma-separated conductor levels.")
    parser.add_argument("--targets", default=None,
                        help="Comma-separated targets (default: all from templates).")
    parser.add_argument("--variants", type=int, default=8,
                        help="Variants per template.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", "-o", default="kloosterman_seeds.json")
    args = parser.parse_args()

    conductors = [int(c.strip()) for c in args.conductors.split(",")]
    targets = [t.strip() for t in args.targets.split(",")] if args.targets else None

    seeds = generate_kloosterman_seeds(
        conductors=conductors,
        targets=targets,
        variants_per_template=args.variants,
        seed=args.seed,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(seeds, f, indent=2)

    # Summary
    from collections import Counter
    target_dist = Counter(s["target"] for s in seeds)
    conductor_dist = Counter(s["_conductor"] for s in seeds)

    print(f"Kloosterman Spectral Seed Pool Generated")
    print(f"  Total seeds: {len(seeds)}")
    print(f"  Output:      {args.output}")
    print(f"  Conductors:  {dict(conductor_dist)}")
    print(f"  Targets:     {dict(target_dist)}")
    print(f"  Seed:        {args.seed}")

    # Show a few examples
    for s in seeds[:3]:
        print(f"\n  [{s['spec_id']}]  target={s['target']}  mode={s['mode']}  order={s['order']}")
        print(f"    alpha={s['alpha']}")
        print(f"    beta={s['beta']}")


if __name__ == "__main__":
    main()
