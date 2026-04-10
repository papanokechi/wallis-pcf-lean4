"""
meta_critic.py — Value scoring + deprioritization filter (v4).

Reviewer recommendation: "Meta-critic to kill low-value conjectures."

Scoring philosophy (Reviewer 2):
  +10  proven theorem (Level 3, CAS-verified)
  +5   conditional theorem (Level 2, convergence proven + closed form)
  +3   structural match (Level 1, Bessel/HG/algebraic identified)
  +1   numeric-only with structure hints (promising Level 0)
  +0.1 isolated numeric observation (Level 0, no hints)

Deprioritization criteria:
  - Isolated constant with no structural pattern → suppress
  - Known result (verified_known) → no theorem credit
  - Trivial algebraic (deg ≤ 2 with integer coeffs) → no credit
  - Duplicate value (another CF gives same constant) → reduce

Boost criteria:
  - Recurring across runs → stability bonus
  - Fits a theorem template → template bonus
  - Connects to known theory → literature bonus
  - Admits partial proof → proof-path bonus
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


# =====================================================================
#  Scoring weights
# =====================================================================

SCORE_WEIGHTS = {
    "proven_theorem":       10.0,   # Level 3
    "conditional_theorem":   5.0,   # Level 2
    "structural_match":      3.0,   # Level 1
    "promising_numeric":     1.0,   # Level 0 with hints
    "isolated_numeric":      0.1,   # Level 0 no hints
    "template_member":       2.0,   # belongs to a theorem template
    "literature_connected":  1.5,   # connects to known theory
    "proof_path_exists":     1.0,   # has identifiable next step
    "cross_run_stable":      0.5,   # seen in multiple runs
}

PENALTY_WEIGHTS = {
    "known_result":         -8.0,   # verified_known → nearly no value
    "trivial_algebraic":    -5.0,   # quadratic surd, fully known
    "duplicate_value":      -2.0,   # same constant from another CF
    "low_precision":        -1.0,   # < 20 digits verified
    "unstable_convergence": -3.0,   # convergence flags
}


# =====================================================================
#  Data structures
# =====================================================================

@dataclass
class CriticScore:
    """Score assigned by the meta-critic to a single discovery."""
    disc_id: str
    raw_score: float = 0.0
    bonuses: list[tuple[str, float]] = None
    penalties: list[tuple[str, float]] = None
    verdict: str = "keep"          # keep | deprioritize | suppress
    reason: str = ""

    def __post_init__(self):
        if self.bonuses is None:
            self.bonuses = []
        if self.penalties is None:
            self.penalties = []

    @property
    def final_score(self) -> float:
        bonus_sum = sum(v for _, v in self.bonuses)
        penalty_sum = sum(v for _, v in self.penalties)
        return max(0.0, self.raw_score + bonus_sum + penalty_sum)

    def to_dict(self) -> dict:
        return {
            "disc_id": self.disc_id,
            "raw_score": self.raw_score,
            "final_score": self.final_score,
            "bonuses": self.bonuses,
            "penalties": self.penalties,
            "verdict": self.verdict,
            "reason": self.reason,
        }


# =====================================================================
#  Scoring logic
# =====================================================================

def score_discovery(discovery: dict,
                    rigor_level: int = 0,
                    template_ids: list[str] | None = None,
                    known_values: set[str] | None = None) -> CriticScore:
    """Score a single discovery for theorem value.

    Args:
        discovery: discovery dict
        rigor_level: from rigor_ladder assessment
        template_ids: template IDs this discovery belongs to
        known_values: set of value strings already seen (for duplicate detection)
    """
    disc_id = discovery.get("id", "unknown")
    meta = discovery.get("metadata", {})
    status = discovery.get("status", "candidate")
    score = CriticScore(disc_id=disc_id)

    # ── Base score from rigor level ──
    if rigor_level >= 3:
        score.raw_score = SCORE_WEIGHTS["proven_theorem"]
    elif rigor_level == 2:
        score.raw_score = SCORE_WEIGHTS["conditional_theorem"]
    elif rigor_level == 1:
        score.raw_score = SCORE_WEIGHTS["structural_match"]
    else:
        # Level 0: check if there are structural hints
        has_hints = bool(
            meta.get("pslq_recognition", {}).get("found")
            or meta.get("bessel_identification", {}).get("identified")
            or meta.get("convergence_check", {}).get("theorem")
        )
        score.raw_score = (SCORE_WEIGHTS["promising_numeric"] if has_hints
                           else SCORE_WEIGHTS["isolated_numeric"])

    # ── Bonuses ──
    if template_ids:
        score.bonuses.append(("template_member", SCORE_WEIGHTS["template_member"]))

    if meta.get("literature_match"):
        # Known result → penalty, not bonus
        pass
    elif meta.get("bessel_identification", {}).get("identified"):
        score.bonuses.append(("literature_connected", SCORE_WEIGHTS["literature_connected"]))

    # Proof path exists (gaps are small)
    proof_result = meta.get("proof_result", {})
    gaps = proof_result.get("gaps", [])
    if proof_result and len(gaps) <= 2:
        score.bonuses.append(("proof_path_exists", SCORE_WEIGHTS["proof_path_exists"]))

    # ── Penalties ──
    if status == "verified_known":
        score.penalties.append(("known_result", PENALTY_WEIGHTS["known_result"]))

    # Trivial algebraic
    alg = meta.get("algebraic_degree", {})
    if alg.get("is_algebraic") and alg.get("degree_bound", 99) <= 2:
        score.penalties.append(("trivial_algebraic", PENALTY_WEIGHTS["trivial_algebraic"]))

    # Duplicate value
    if known_values is not None:
        val_str = meta.get("value_20_digits") or str(discovery.get("value", ""))
        # Truncate to 15 digits for duplicate detection
        val_key = val_str[:17] if val_str else ""
        if val_key in known_values:
            score.penalties.append(("duplicate_value", PENALTY_WEIGHTS["duplicate_value"]))

    # Low precision
    prec = discovery.get("precision_digits", 0) or meta.get("precision_achieved", 0)
    if prec < 20:
        score.penalties.append(("low_precision", PENALTY_WEIGHTS["low_precision"]))

    # Unstable convergence
    conv = meta.get("convergence_check", {})
    if conv.get("flags"):
        score.penalties.append(("unstable_convergence", PENALTY_WEIGHTS["unstable_convergence"]))

    # ── Verdict ──
    fs = score.final_score
    if fs >= 3.0:
        score.verdict = "keep"
        score.reason = "High theorem value"
    elif fs >= 1.0:
        score.verdict = "keep"
        score.reason = "Moderate value — worth pursuing"
    elif fs >= 0.1:
        score.verdict = "deprioritize"
        score.reason = "Low value — deprioritize for proof attempts"
    else:
        score.verdict = "suppress"
        score.reason = "No theorem value — suppress from report"

    return score


# =====================================================================
#  Batch scoring
# =====================================================================

def score_batch(discoveries: list[dict],
                rigor_assessments: dict | None = None,
                templates: list | None = None) -> dict:
    """Score all discoveries and return ranked results.

    Args:
        discoveries: list of discovery dicts
        rigor_assessments: output of rigor_ladder.assess_all()
        templates: list of TheoremTemplate objects

    Returns:
        {
            "scores": [CriticScore.to_dict(), ...],
            "ranked": [disc_ids in descending score order],
            "suppressed": [disc_ids with verdict='suppress'],
            "deprioritized": [disc_ids with verdict='deprioritize'],
            "kept": [disc_ids with verdict='keep'],
            "total_theorem_value": sum of final scores,
        }
    """
    # Build rigor level lookup
    rigor_lookup = {}
    if rigor_assessments:
        for a in rigor_assessments.get("assessments", []):
            rigor_lookup[a["disc_id"]] = a["level"]

    # Build template membership lookup
    template_lookup: dict[str, list[str]] = {}
    if templates:
        for t in templates:
            t_dict = t if isinstance(t, dict) else t.to_dict()
            for inst_id in t_dict.get("instances", []):
                template_lookup.setdefault(inst_id, []).append(t_dict.get("template_id", ""))

    # Track seen values for duplicate detection
    known_values: set[str] = set()
    scores = []

    for d in discoveries:
        disc_id = d.get("id", "unknown")
        rl = rigor_lookup.get(disc_id, 0)
        tmpl_ids = template_lookup.get(disc_id)

        cs = score_discovery(d, rigor_level=rl, template_ids=tmpl_ids,
                             known_values=known_values)
        scores.append(cs)

        # Track value for duplicate detection
        val_str = d.get("metadata", {}).get("value_20_digits") or str(d.get("value", ""))
        val_key = val_str[:17] if val_str else ""
        if val_key:
            known_values.add(val_key)

    # Sort by final score descending
    scores.sort(key=lambda s: -s.final_score)

    kept = [s.disc_id for s in scores if s.verdict == "keep"]
    deprioritized = [s.disc_id for s in scores if s.verdict == "deprioritize"]
    suppressed = [s.disc_id for s in scores if s.verdict == "suppress"]
    total_value = sum(s.final_score for s in scores)

    return {
        "scores": [s.to_dict() for s in scores],
        "ranked": [s.disc_id for s in scores],
        "kept": kept,
        "deprioritized": deprioritized,
        "suppressed": suppressed,
        "total_theorem_value": total_value,
    }


def format_critic_summary(critic_data: dict) -> str:
    """Format meta-critic summary for console output."""
    lines = [
        "Meta-Critic:",
        f"  Kept (high value):      {len(critic_data.get('kept', []))}",
        f"  Deprioritized:          {len(critic_data.get('deprioritized', []))}",
        f"  Suppressed:             {len(critic_data.get('suppressed', []))}",
        f"  Total theorem value:    {critic_data.get('total_theorem_value', 0):.1f}",
    ]
    return "\n".join(lines)
