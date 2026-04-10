"""
rigor_ladder.py — 4-level rigor tracking with promotion logic (v4).

Reviewer recommendation: "Rigor ladder from numeric → structural → reduction → proof."

Levels:
  Level 0 — Numeric only: computed to N digits, no structural explanation
  Level 1 — Structural: matched to Bessel / HG / algebraic family
  Level 2 — Reduction: reduced to known theorem (Wall, Perron, etc.)
  Level 3 — Full proof: CAS-verified convergence + closed form + identity

Each discovery carries a rigor_level field. The orchestrator attempts to
push each candidate up the ladder after each round.

Strict tagging:
  conjecture         — Level 0 only, numeric agreement
  theorem_conditional — Level 2, proven under stated assumptions
  theorem             — Level 3, fully proven, all assumptions discharged
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# =====================================================================
#  Rigor level definitions
# =====================================================================

RIGOR_LEVELS = {
    0: {"name": "numeric_only",   "label": "Level 0 — Numeric",
        "description": "Computed to N digits; no structural explanation.",
        "tag": "conjecture"},
    1: {"name": "structural",     "label": "Level 1 — Structural",
        "description": "Matched to a known function family (Bessel, HG, algebraic).",
        "tag": "conjecture"},
    2: {"name": "reduction",      "label": "Level 2 — Reduction",
        "description": "Reduced to a named theorem (Wall, Perron, Śl.-Pringsheim).",
        "tag": "theorem_conditional"},
    3: {"name": "full_proof",     "label": "Level 3 — Full Proof",
        "description": "CAS-verified: convergence + closed form + identity match.",
        "tag": "theorem"},
}


@dataclass
class RigorAssessment:
    """Rigor assessment for a single discovery."""
    disc_id: str
    level: int = 0
    tag: str = "conjecture"      # conjecture | theorem_conditional | theorem
    evidence: list[str] = field(default_factory=list)
    convergence_theorem: str = ""
    closed_form: str = ""
    cas_verified: bool = False
    gaps: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return RIGOR_LEVELS.get(self.level, RIGOR_LEVELS[0])["label"]

    def to_dict(self) -> dict:
        return {
            "disc_id": self.disc_id,
            "level": self.level,
            "label": self.label,
            "tag": self.tag,
            "evidence": self.evidence,
            "convergence_theorem": self.convergence_theorem,
            "closed_form": self.closed_form,
            "cas_verified": self.cas_verified,
            "gaps": self.gaps,
        }


# =====================================================================
#  Assess rigor level from discovery metadata
# =====================================================================

def assess_rigor(discovery: dict) -> RigorAssessment:
    """Determine the rigor level of a discovery from its metadata.

    Checks evidence in order: Level 3 → Level 2 → Level 1 → Level 0.
    """
    disc_id = discovery.get("id", "unknown")
    meta = discovery.get("metadata", {})
    params = discovery.get("params", {})
    assessment = RigorAssessment(disc_id=disc_id)

    # ── Check Level 3: full proof ──
    proof_result = meta.get("proof_result", {})
    if proof_result.get("status") == "formal_proof":
        assessment.level = 3
        assessment.tag = "theorem"
        assessment.convergence_theorem = proof_result.get("convergence", {}).get("theorem_used", "")
        assessment.closed_form = str(proof_result.get("closed_form", {}).get("expression", ""))
        assessment.cas_verified = True
        assessment.evidence = [
            f"Convergence: {assessment.convergence_theorem}",
            f"Closed form: {assessment.closed_form}",
            "CAS verification: passed",
        ]
        return assessment

    # ── Check Level 2: reduction to named theorem ──
    convergence = meta.get("convergence_check", {})
    proof_result_partial = proof_result or {}

    convergence_theorem = (
        proof_result_partial.get("convergence", {}).get("theorem_used", "")
        or convergence.get("theorem", "")
    )

    has_convergence_proof = bool(convergence_theorem)
    has_closed_form = bool(
        proof_result_partial.get("closed_form", {}).get("type")
        or meta.get("bessel_identification", {}).get("identified")
        or meta.get("special_function", {}).get("identified")
    )

    if has_convergence_proof and has_closed_form:
        # Almost there — reduction achieved but maybe CAS didn't fully verify
        assessment.level = 2
        assessment.tag = "theorem_conditional"
        assessment.convergence_theorem = convergence_theorem
        cf = (proof_result_partial.get("closed_form", {}).get("expression", "")
              or meta.get("bessel_identification", {}).get("best_identification", {}).get("formula", ""))
        assessment.closed_form = str(cf)
        assessment.evidence = [
            f"Convergence: {convergence_theorem}",
            f"Closed form identified: {assessment.closed_form[:80]}",
        ]
        # Check for gaps
        gaps = proof_result_partial.get("gaps", [])
        if gaps:
            assessment.gaps = gaps
        else:
            assessment.gaps = ["CAS verification incomplete"]
        return assessment

    if has_convergence_proof:
        # Convergence proven but no closed form yet
        assessment.level = 2
        assessment.tag = "theorem_conditional"
        assessment.convergence_theorem = convergence_theorem
        assessment.evidence = [f"Convergence: {convergence_theorem}"]
        assessment.gaps = ["Closed-form identification needed"]
        return assessment

    # ── Check Level 1: structural match ──
    bessel = meta.get("bessel_identification", {})
    special_fn = meta.get("special_function", {})
    algebraic = meta.get("algebraic_analysis", "")
    alg_degree = meta.get("algebraic_degree", {})

    if bessel.get("identified"):
        assessment.level = 1
        assessment.tag = "conjecture"
        best = bessel.get("best_identification", {})
        assessment.closed_form = best.get("formula", "")
        assessment.evidence = [f"Bessel/HG match: {assessment.closed_form[:60]}"]
        assessment.gaps = ["Convergence proof needed", "Identity verification needed"]
        return assessment

    if special_fn.get("identified"):
        assessment.level = 1
        assessment.tag = "conjecture"
        assessment.closed_form = special_fn.get("best", {}).get("expression", "")
        assessment.evidence = [f"Special function: {assessment.closed_form[:60]}"]
        assessment.gaps = ["Convergence proof needed", "Identity verification needed"]
        return assessment

    if alg_degree.get("is_algebraic"):
        assessment.level = 1
        assessment.tag = "conjecture"
        assessment.closed_form = f"algebraic deg ≤ {alg_degree.get('degree_bound', '?')}"
        assessment.evidence = [f"Algebraic: {assessment.closed_form}"]
        assessment.gaps = ["Exact minimal polynomial needed", "Proof of identity needed"]
        return assessment

    if algebraic and "algebraic" in str(algebraic).lower():
        assessment.level = 1
        assessment.tag = "conjecture"
        assessment.evidence = [f"Structural hint: {str(algebraic)[:60]}"]
        assessment.gaps = ["Full identification needed"]
        return assessment

    # ── Level 0: numeric only ──
    precision = discovery.get("precision_digits", 0) or meta.get("precision_achieved", 0)
    assessment.evidence = [f"Numeric: {precision} digits verified"]
    assessment.gaps = [
        "No structural identification",
        "No convergence proof",
        "No closed form",
    ]
    return assessment


# =====================================================================
#  Attempt promotion: try to push a discovery up the ladder
# =====================================================================

def attempt_promotion(discovery: dict, current_level: int) -> RigorAssessment | None:
    """Try to promote a discovery to the next rigor level.

    Returns a new assessment if promotion succeeded, None otherwise.
    This is called by the orchestrator after proof attempts.
    """
    # Re-assess from scratch — the metadata may have been enriched
    new_assessment = assess_rigor(discovery)
    if new_assessment.level > current_level:
        return new_assessment
    return None


# =====================================================================
#  Batch assessment for the report
# =====================================================================

def assess_all(discoveries: list[dict]) -> dict:
    """Assess rigor for all discoveries, return summary statistics.

    Returns:
        {
            "assessments": [RigorAssessment.to_dict(), ...],
            "by_level": {0: count, 1: count, 2: count, 3: count},
            "by_tag": {"conjecture": count, "theorem_conditional": count, "theorem": count},
            "promotable": [disc_ids that have gaps suggesting possible promotion],
        }
    """
    assessments = []
    by_level = {0: 0, 1: 0, 2: 0, 3: 0}
    by_tag = {"conjecture": 0, "theorem_conditional": 0, "theorem": 0}
    promotable = []

    for d in discoveries:
        a = assess_rigor(d)
        assessments.append(a.to_dict())
        by_level[a.level] = by_level.get(a.level, 0) + 1
        by_tag[a.tag] = by_tag.get(a.tag, 0) + 1

        # Check if there's a plausible path up
        if a.level < 3 and len(a.gaps) <= 2:
            promotable.append(a.disc_id)

    return {
        "assessments": assessments,
        "by_level": by_level,
        "by_tag": by_tag,
        "promotable": promotable,
    }


def format_rigor_summary(rigor_data: dict) -> str:
    """Format rigor ladder summary for console output."""
    by_level = rigor_data.get("by_level", {})
    by_tag = rigor_data.get("by_tag", {})
    lines = [
        "Rigor Ladder:",
        f"  Level 3 (Full Proof):     {by_level.get(3, 0)}  [{by_tag.get('theorem', 0)} theorems]",
        f"  Level 2 (Reduction):      {by_level.get(2, 0)}  [{by_tag.get('theorem_conditional', 0)} conditional]",
        f"  Level 1 (Structural):     {by_level.get(1, 0)}",
        f"  Level 0 (Numeric only):   {by_level.get(0, 0)}",
        f"  Promotable candidates:    {len(rigor_data.get('promotable', []))}",
    ]
    return "\n".join(lines)
