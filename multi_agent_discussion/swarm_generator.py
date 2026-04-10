from __future__ import annotations

"""Mutation swarm generator for SIARC debate mode.

Creates a small population of candidate formulas around a base hypothesis so the
controller can evaluate them before sending only the strongest survivors to the
Red-Team critic.

Usage:
    py multi_agent_discussion/swarm_generator.py --claim "A1 = -5*c5/48 - 6/c5" --parent-id H-0024
"""

import argparse
import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

DEFAULT_SWARM_SIZE = 6


def _deterministic_rng(seed_text: str) -> random.Random:
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(seed)


def _extract_formula_from_claim(claim: str) -> str:
    if not claim:
        return "c5 / 48"
    rhs = claim
    if "=" in claim:
        rhs = claim.split("=", 1)[1]
    for marker in (" matches", " with ", " using ", ", compare"):
        if marker in rhs:
            rhs = rhs.split(marker, 1)[0]
    return rhs.strip() or "c5 / 48"


def _normalize_formula_text(formula: str) -> str:
    text = formula.replace("·", "*").replace("−", "-")
    text = text.replace("π", "pi").replace("γ", "gamma")
    text = text.replace("₅", "5").replace("₁", "1")
    return text


def _complexity_score(formula: str) -> float:
    operators = sum(formula.count(op) for op in ["+", "-", "*", "/", "(", ")"])
    unique_tokens = len(set(re.findall(r"[A-Za-z_]+|\d+\.\d+|\d+", formula)))
    return round(min(0.99, 0.15 + operators * 0.04 + unique_tokens * 0.025), 3)


def _perturb_first_number(formula: str, delta: float) -> str:
    def repl(match: re.Match[str]) -> str:
        value = float(match.group(0))
        return f"{value + delta:.3f}".rstrip("0").rstrip(".")

    return re.sub(r"\d+(?:\.\d+)?", repl, formula, count=1)


def _build_safe_candidates(base_formula: str, rng: random.Random) -> list[dict[str, Any]]:
    delta_1 = rng.uniform(-0.8, 0.8)
    delta_2 = rng.uniform(-1.5, 1.5)
    return [
        {
            "mutation_kind": "baseline",
            "formula": base_formula,
            "rationale": "Keep one safe baseline candidate as the control.",
            "tool_strategy": "Sandbox",
        },
        {
            "mutation_kind": "coefficient_perturbation",
            "formula": _perturb_first_number(base_formula, delta_1),
            "rationale": "Perturb the leading coefficient slightly to test local sensitivity.",
            "tool_strategy": "Sandbox",
        },
        {
            "mutation_kind": "denominator_shift",
            "formula": base_formula.replace("48", f"{48 + delta_2:.3f}".rstrip("0").rstrip("."), 1),
            "rationale": "Shift the dominant denominator to probe nearby rational structure.",
            "tool_strategy": "SymbolicVerify",
        },
    ]


def _build_radical_candidates(base_formula: str, rng: random.Random) -> list[dict[str, Any]]:
    normalized = _normalize_formula_text(base_formula)
    radicals = []

    no_inverse = re.sub(r"[+\-]?\s*\d+(?:\.\d+)?\s*\*?\s*\d*(?:\.\d+)?\s*/\s*\(?\s*\d*(?:\.\d+)?\s*\*?\s*c5\s*\)?", "", normalized)
    no_inverse = re.sub(r"\s+", " ", no_inverse).strip(" +-*") or "-(5*c5)/48"
    radicals.append(
        {
            "mutation_kind": "structure_reset",
            "formula": no_inverse,
            "rationale": "Drop the inverse-c5 pole term to test whether the structural mismatch is the real failure mode.",
            "tool_strategy": "SymbolicVerify",
        }
    )

    radicals.append(
        {
            "mutation_kind": "dimension_safe",
            "formula": "-(5*c5)/48 - sqrt(2)/12",
            "rationale": "Keep a simple linear term and replace the pole with a dimensionally safer constant offset.",
            "tool_strategy": "PSLQ",
        }
    )

    radicals.append(
        {
            "mutation_kind": "constant_injection",
            "formula": f"({normalized}) + {rng.choice(['pi/48', 'e/12', 'gamma/12'])}",
            "rationale": "Inject a transcendental correction term to test whether the residual behaves like a known constant.",
            "tool_strategy": "PSLQ",
        }
    )

    radicals.append(
        {
            "mutation_kind": "operator_shift",
            "formula": f"({normalized.replace('/', '*', 1)}) / 12",
            "rationale": "Alter the dominant operator structure to escape local mode collapse.",
            "tool_strategy": "Sandbox",
        }
    )

    return radicals


def generate_mutation_swarm(
    base_hypothesis: dict[str, Any] | str,
    mutation_rate: float = 0.18,
    swarm_size: int = DEFAULT_SWARM_SIZE,
    generation: int | None = None,
    prior_lfi: float | None = None,
) -> dict[str, Any]:
    if isinstance(base_hypothesis, dict):
        claim = str(base_hypothesis.get("claim", "")).strip()
        parent_id = str(base_hypothesis.get("id", "H-parent"))
        gap_id = str(base_hypothesis.get("gap_id", "unknown-gap"))
    else:
        claim = str(base_hypothesis)
        parent_id = "H-parent"
        gap_id = "unknown-gap"

    base_formula = _normalize_formula_text(_extract_formula_from_claim(claim))
    generation = int(generation or 1)
    rng = _deterministic_rng(f"{parent_id}|{generation}|{prior_lfi}|{mutation_rate}|{swarm_size}")

    safe_candidates = _build_safe_candidates(base_formula, rng)
    radical_candidates = _build_radical_candidates(base_formula, rng)

    # If prior LFI is high, force at least half the swarm to be radical.
    if prior_lfi is not None and prior_lfi > 0.5:
        pool = safe_candidates[: max(1, swarm_size // 2)] + radical_candidates
    else:
        pool = safe_candidates + radical_candidates

    candidates = []
    for idx, item in enumerate(pool[:swarm_size], start=1):
        formula = item["formula"].strip()
        candidates.append(
            {
                "id": f"{parent_id}-m{idx}",
                "formula": formula,
                "parent": parent_id,
                "gap_id": gap_id,
                "mutation_kind": item["mutation_kind"],
                "rationale": item["rationale"],
                "tool_strategy": item["tool_strategy"],
                "complexity_score": _complexity_score(formula),
                "diversity_tag": "radical" if item["mutation_kind"] in {"structure_reset", "dimension_safe", "constant_injection", "operator_shift"} else "safe",
            }
        )

    swarm_id = f"S-{parent_id}-G{generation}"
    return {
        "swarm_id": swarm_id,
        "parent_hypothesis_id": parent_id,
        "gap_id": gap_id,
        "generation": generation,
        "mutation_rate": mutation_rate,
        "base_formula": base_formula,
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a mutation swarm for a base hypothesis")
    parser.add_argument("--claim", required=True, help="Base hypothesis claim or formula")
    parser.add_argument("--parent-id", default="H-parent", help="Parent hypothesis id")
    parser.add_argument("--gap-id", default="unknown-gap", help="Gap id for metadata")
    parser.add_argument("--swarm-size", type=int, default=DEFAULT_SWARM_SIZE, help="Number of candidates to generate")
    parser.add_argument("--generation", type=int, default=1, help="Generation index")
    parser.add_argument("--prior-lfi", type=float, default=None, help="Previous LFI score")
    args = parser.parse_args()

    swarm = generate_mutation_swarm(
        {
            "id": args.parent_id,
            "gap_id": args.gap_id,
            "claim": args.claim,
        },
        swarm_size=max(2, args.swarm_size),
        generation=max(1, args.generation),
        prior_lfi=args.prior_lfi,
    )
    print(json.dumps(swarm, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
