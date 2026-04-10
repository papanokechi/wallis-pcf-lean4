"""
proof_funnel.py — Tightened conjecture funnel + human scaffolding + bootstrapping (v3.4).

Three concerns:
  1. Proof queue management: filter novel CFs down to ≤10 best proof candidates
     using multi-criterion scoring (convergence quality, polynomial structure,
     PSLQ stability, numeric agreement across depths).
  2. Human-in-the-loop scaffolding: produce structured proof sketches formatted
     for a human mathematician to finish.
  3. Success case bootstrapping: record which proof strategies succeed and feed
     them back as templates for future candidates.
"""

from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


# =====================================================================
#  Proof Queue Manager — item 3: tighten the funnel
# =====================================================================

@dataclass
class QueueCandidate:
    """A scored candidate for the proof queue."""
    disc_id: str
    expression: str
    family: str
    score: float
    reasons: list[str]
    discovery: dict

    def to_dict(self) -> dict:
        return {
            "disc_id": self.disc_id,
            "expression": self.expression,
            "family": self.family,
            "score": self.score,
            "reasons": self.reasons,
        }


def build_proof_queue(novel_unproven: list[dict], max_queue: int = 10) -> list[QueueCandidate]:
    """Score and rank novel CFs, return top candidates for proof attempts.

    Scoring criteria (each 0-1, weighted):
      - Convergence quality (3 depths agree)       weight 3
      - Polynomial coefficient structure             weight 2
      - PSLQ stability (consistent across prec)     weight 2
      - Numeric precision (low error)                weight 2
      - CF is linear-b (amenable to Bessel/HG)      weight 1
      - Not flagged by convergence diagnostics       weight 2
    """
    candidates = []

    for d in novel_unproven:
        score = 0.0
        reasons = []
        params = d.get("params", {})
        meta = d.get("metadata", {})

        # 1. Convergence quality: values at depth 500, 300, 150 agree
        conv_err_hi = meta.get("convergence_error_500_300", 1)
        conv_err_lo = meta.get("convergence_error_300_150", 1)
        if conv_err_hi < 1e-50:
            score += 3.0
            reasons.append("Strong convergence (depth 500≈300 to <1e-50)")
        elif conv_err_hi < 1e-20:
            score += 2.0
            reasons.append(f"Good convergence (depth error {conv_err_hi:.1e})")
        elif conv_err_hi < 1e-10:
            score += 1.0
            reasons.append(f"Moderate convergence ({conv_err_hi:.1e})")

        # 2. Polynomial coefficient structure
        an = params.get("an", [])
        bn = params.get("bn", [])
        if an and bn:
            if len(an) == 1 and len(bn) <= 2:
                score += 2.0
                reasons.append("Simple polynomial CF (constant a, linear b)")
            elif len(an) <= 2 and len(bn) <= 2:
                score += 1.5
                reasons.append("Low-degree polynomial CF")
            elif len(an) <= 3 and len(bn) <= 2:
                score += 1.0
                reasons.append("Quadratic-a CF")

        # 3. PSLQ stability
        pslq = meta.get("pslq_recognition", {})
        stab = meta.get("stability_table", [])
        if stab:
            matches = sum(1 for row in stab if row.get("found") and row.get("matches_original") is not False)
            total_stab = len(stab)
            if total_stab > 0:
                ratio = matches / total_stab
                if pslq.get("found") is False:
                    # No PSLQ relation → truly novel, bonus
                    score += 2.0
                    reasons.append(f"PSLQ: no relation found ({ratio:.0%} check)")
                elif ratio > 0.8:
                    score += 1.5
                    reasons.append(f"PSLQ: stable relation ({ratio:.0%})")
                else:
                    score += 0.5
                    reasons.append(f"PSLQ: unstable ({ratio:.0%})")

        # 4. Numeric precision
        error = d.get("error", float("inf"))
        if error == 0:
            score += 2.0
            reasons.append("Zero numeric error")
        elif error < 1e-100:
            score += 2.0
            reasons.append(f"Excellent numeric precision ({error:.1e})")
        elif error < 1e-30:
            score += 1.0
            reasons.append(f"Good precision ({error:.1e})")

        # 5. Linear-b bonus (amenable to Bessel/confluent HG identification)
        # v4.6: Boosted — these are the ONLY CFs that reach L3 (formal proof)
        if len(bn) == 2 and bn[0] != 0:
            score += 3.0
            reasons.append("Linear-b → Bessel/confluent HG provable (boosted)")
            if len(an) == 1:  # constant-a + linear-b: most amenable
                score += 2.0
                reasons.append("Const-a + linear-b → directly Bessel-provable")

        # 6. Convergence diagnostics clean
        conv_check = meta.get("convergence_check", {})
        flags = conv_check.get("flags", [])
        if not flags:
            score += 2.0
            reasons.append("No convergence flags")
        else:
            # Penalty for each flag
            penalty = min(len(flags) * 0.5, 2.0)
            reasons.append(f"Convergence flags: {len(flags)} (−{penalty:.1f})")
            score -= penalty

        candidates.append(QueueCandidate(
            disc_id=d.get("id", "?")[:12],
            expression=d.get("expression", "?"),
            family=d.get("family", "?"),
            score=score,
            reasons=reasons,
            discovery=d,
        ))

    # Sort descending by score
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_queue]


# =====================================================================
#  Human-in-the-loop scaffolding — item 4
# =====================================================================

def format_proof_scaffold(proof_result, discovery: dict) -> str:
    """Create a human-readable proof scaffold from a ProofResult.

    Output format:
    - Clear theorem statement
    - Step-by-step proof plan with citations
    - What the CAS verified vs what remains
    - Suggested next steps for human mathematician
    """
    lines = []
    params = discovery.get("params", {})
    meta = discovery.get("metadata", {})
    an = params.get("an", [])
    bn = params.get("bn", [])
    val_20 = meta.get("value_20_digits", str(discovery.get("value", "?")))

    # ── Theorem statement ──
    lines.append("═" * 60)
    lines.append("CONJECTURE (for human review)")
    lines.append("═" * 60)
    lines.append("")

    # Format CF nicely
    if len(an) == 1 and len(bn) == 2:
        lines.append(f"  Let CF = b(0) + K_{{n≥1}} [ {an[0]} / ({bn[0]}n + {bn[1]}) ]")
    else:
        an_str = "+".join(f"{c}n^{len(an)-1-i}" if i < len(an)-1 else str(c)
                          for i, c in enumerate(an) if c != 0)
        bn_str = "+".join(f"{c}n^{len(bn)-1-i}" if i < len(bn)-1 else str(c)
                          for i, c in enumerate(bn) if c != 0)
        lines.append(f"  Let CF = K_{{n≥1}} [ a(n) / b(n) ]")
        lines.append(f"    where a(n) = {an_str}")
        lines.append(f"    and   b(n) = {bn_str}")

    lines.append(f"  Then CF = {val_20}")
    lines.append("")

    # ── Proof status ──
    status = proof_result.status
    status_map = {
        "formal_proof": "✓ FORMALLY VERIFIED (all steps CAS-checked)",
        "partial_proof": "△ PARTIALLY PROVEN (some gaps remain)",
        "numeric_only": "○ NUMERIC EVIDENCE ONLY (no proof yet)",
    }
    lines.append(f"Status: {status_map.get(status, status)}")
    lines.append(f"Confidence: {proof_result.confidence:.0%}")
    lines.append("")

    # ── Convergence ──
    conv = proof_result.convergence
    lines.append("Step 1: CONVERGENCE")
    if conv.get("proven"):
        lines.append(f"  ✓ Proven via: {conv['theorem_used']}")
        lines.append(f"  {conv.get('proof_detail', '')}")
        lines.append(f"  Reference: See standard CF textbook (Wall 1948, Lorentzen & Waadeland 2008).")
    else:
        lines.append("  ✗ Not proven. Theorems checked:")
        for t in conv.get("theorems_tried", []):
            lines.append(f"    • {t['theorem']}: {t.get('details', 'N/A')[:80]}")
        lines.append("  → Human action: Try Pincherle's theorem, or direct Cauchy analysis.")
    lines.append("")

    # ── Closed form ──
    cf = proof_result.closed_form
    lines.append("Step 2: CLOSED-FORM IDENTIFICATION")
    if cf.get("identified"):
        lines.append(f"  ✓ Identified as: {cf.get('type', '?')}")
        lines.append(f"    Expression: {cf.get('expression', '?')}")
        if cf.get("match_error") is not None:
            lines.append(f"    Numeric match error: {cf['match_error']:.2e}")
        lines.append("  → Human action: Verify the equivalence transform algebraically.")
    else:
        lines.append("  ✗ No closed form found by automated search.")
        lines.append("  Tried: Bessel ratios, confluent ₁F₁ ratios, SymPy nsimplify.")
        lines.append("  → Human action: Try other special functions, or search OEIS/ISC.")
    lines.append("")

    # ── Verification ──
    ver = proof_result.verification
    lines.append("Step 3: SYMBOLIC VERIFICATION")
    if ver.get("verified"):
        lines.append(f"  ✓ CAS verified to {ver.get('match_digits', 0)} digits")
    else:
        lines.append(f"  ✗ Not verified: {ver.get('error', 'no closed form available')}")
    lines.append("")

    # ── Gaps and next steps ──
    if proof_result.gaps:
        lines.append("REMAINING GAPS:")
        for g in proof_result.gaps:
            lines.append(f"  • {g}")
    else:
        lines.append("NO GAPS — all proof components verified.")

    lines.append("")
    lines.append("SUGGESTED NEXT STEPS FOR HUMAN MATHEMATICIAN:")
    if status == "formal_proof":
        lines.append("  1. Write up as formal theorem with full citations.")
        lines.append("  2. Submit to OEIS for value registration.")
    elif status == "partial_proof":
        if not conv.get("proven"):
            lines.append("  1. Prove convergence (try Pincherle or direct analysis).")
        if not cf.get("identified"):
            lines.append("  2. Identify closed form (consult DLMF 18.x, 10.x).")
        if not ver.get("verified"):
            lines.append("  3. Verify equivalence symbolically.")
        lines.append("  4. Once all gaps closed, submit to journal.")
    else:
        lines.append("  1. This is a numeric conjecture only.")
        lines.append("  2. Compute to 500+ digits, search ISC/OEIS.")
        lines.append("  3. Try manual special function matching.")
        lines.append("  4. If novel, submit to Experimental Mathematics.")

    return "\n".join(lines)


# =====================================================================
#  Success case bootstrapping — item 5
# =====================================================================

BOOTSTRAP_PATH = Path("results/proof_bootstrap.json")


def load_bootstrap_cases() -> list[dict]:
    """Load previously successful proof strategies."""
    if BOOTSTRAP_PATH.exists():
        try:
            data = json.loads(BOOTSTRAP_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def save_bootstrap_case(proof_result, discovery: dict) -> None:
    """Record a successful (or partially successful) proof for future reference."""
    if proof_result.status == "numeric_only":
        return  # Don't bootstrap failures

    cases = load_bootstrap_cases()
    params = discovery.get("params", {})
    case = {
        "an": params.get("an", []),
        "bn": params.get("bn", []),
        "status": proof_result.status,
        "theorem_used": proof_result.convergence.get("theorem_used"),
        "sf_type": proof_result.closed_form.get("type"),
        "confidence": proof_result.confidence,
        "expression": discovery.get("expression", "")[:80],
    }
    # Avoid duplicates
    for existing in cases:
        if existing.get("an") == case["an"] and existing.get("bn") == case["bn"]:
            return
    cases.append(case)

    BOOTSTRAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    BOOTSTRAP_PATH.write_text(json.dumps(cases, indent=2), encoding="utf-8")


def get_bootstrap_hints(an_coeffs: list[int], bn_coeffs: list[int]) -> list[str]:
    """Given a new CF's coefficients, find similar past successes for hints."""
    cases = load_bootstrap_cases()
    if not cases:
        return []

    hints = []
    for case in cases:
        if case.get("status") == "numeric_only":
            continue
        past_an = case.get("an", [])
        past_bn = case.get("bn", [])
        # Structural similarity: same degree polynomials
        if len(past_an) == len(an_coeffs) and len(past_bn) == len(bn_coeffs):
            hint = (f"Similar CF (a={past_an}, b={past_bn}) was proven via "
                    f"{case.get('theorem_used', '?')} → {case.get('sf_type', '?')} "
                    f"(status: {case.get('status', '?')})")
            hints.append(hint)

    return hints[:5]
