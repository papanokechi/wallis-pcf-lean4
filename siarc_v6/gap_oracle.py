"""
SIARC v6 — Gap Oracle
=====================
KEY UNLOCK #1: reads live gap%, pending lemmas, proof progress deltas
and generates TARGETED generation constraints so every new hypothesis
is aimed at a known open gap — not random exploration.

v5 flaw: gap% was tracked but never fed back into generation.
v6 fix:  gap% is the PRIMARY generation constraint.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.hypothesis import Hypothesis


# Known proof gaps in the SIARC knowledge base
# Each entry is a structured description of what's open
KNOWN_GAPS = {
    # H-0025 / G-01 law gaps
    "LEMMA_K_k5": {
        "label": "Lemma K: Kloosterman bound k=5, conductor N₅=24",
        "formula_hint": "η(τ)^{-k} Kloosterman bound",
        "k_range": [5],
        "conductor": 24,
        "priority": 10,   # highest — blocks two champions
        "blocks": ["H-0025", "C_P14_01"],
        "attack_direction": "Weil bound on S(m,n;c) for c | N₅=24, k=5",
    },
    "LEMMA_K_k6_8": {
        "label": "Lemma K generalisation k=6..8",
        "formula_hint": "η(τ)^{-k} Kloosterman, general k≥5",
        "k_range": [6, 7, 8],
        "conductor": None,
        "priority": 8,
        "blocks": ["C_P14_01"],
        "attack_direction": "Uniform Weil bound, show O(k·c^{1/2+ε}) for varying conductor",
    },
    "BETA_K_CLOSED_FORM": {
        "label": "β_k / A₂⁽ᵏ⁾ closed form from higher saddle-point terms",
        "formula_hint": "-((k+1)(k+3))/(8·c_k) — is this exact or asymptotic?",
        "k_range": list(range(5, 13)),
        "conductor": None,
        "priority": 7,
        "blocks": ["H-0026"],
        "attack_direction": "Higher-order Laplace method on the generating integral, compare to known k=1..4",
    },
    "G01_EXTENSION_k9_12": {
        "label": "G-01 law verification k=9..12 precision ladder",
        "formula_hint": "A₁⁽ᵏ⁾ = -(k·c_k)/48 - (k+1)(k+3)/(8·c_k)",
        "k_range": [9, 10, 11, 12],
        "conductor": None,
        "priority": 6,
        "blocks": ["H-0026"],
        "attack_direction": "mpmath precision ladder: verify formula to 50-100 decimal places for each k",
    },
    "K24_BOSS": {
        "label": "k=24 boss-level stress test of G-01 law",
        "formula_hint": "A₁⁽²⁴⁾ = -(24·c₂₄)/48 - 25·27/(8·c₂₄)",
        "k_range": [24],
        "conductor": None,
        "priority": 5,
        "blocks": ["C_P14_04"],
        "attack_direction": "Compute c₂₄ to high precision, verify both terms independently",
    },
    "VQUAD_TRANSCENDENCE": {
        "label": "V_quad transcendence (BOREL-L1 pending)",
        "formula_hint": "V₁(k) = k·e^k·E₁(k) — is V_quad transcendental?",
        "k_range": [],
        "conductor": None,
        "priority": 4,
        "blocks": ["BOREL-L1"],
        "attack_direction": "Mahler/Dirichlet-L approach + parabolic cylinder scan",
    },
    "DOUBLE_BOREL_P2": {
        "label": "Double Borel p=2: a_n = -(n!)² kernel",
        "formula_hint": "Extend Borel–Ramanujan to a_n=-(n!)²",
        "k_range": [],
        "conductor": None,
        "priority": 4,
        "blocks": ["BOREL-L1"],
        "attack_direction": "Find kernel for double-factorial growth rate",
    },
    "SELECTION_RULE_HIGHER_D": {
        "label": "Selection rule mechanism for higher d values",
        "formula_hint": "Extend C_P14_01 selection rule to d > current range",
        "k_range": list(range(5, 25)),
        "conductor": None,
        "priority": 5,
        "blocks": ["C_P14_01"],
        "attack_direction": "Identify d-dependent correction terms in A₁⁽ᵏ⁾ formula",
    },
}


@dataclass
class GapConstraint:
    """A generation constraint derived from an open gap."""
    gap_id:           str
    label:            str
    k_range:          list[int]
    attack_direction: str
    priority:         int
    conductor:        int | None
    blocks:           list[str]
    urgency:          float = 0.0   # computed from how many champions are blocked

    def as_prompt_fragment(self) -> str:
        """Returns a string to inject into hypothesis generation prompts."""
        k_str = f"k ∈ {self.k_range}" if self.k_range else "general k"
        cond_str = f", conductor N={self.conductor}" if self.conductor else ""
        return (
            f"TARGET GAP [{self.gap_id}]: {self.label}\n"
            f"  k-range: {k_str}{cond_str}\n"
            f"  Attack direction: {self.attack_direction}\n"
            f"  Blocks: {', '.join(self.blocks)}\n"
            f"  Priority: {self.priority}/10"
        )


class GapOracle:
    """
    Reads live hypothesis state and produces ordered, targeted
    generation constraints for the next iteration.

    This is what converts random walk → directed search.
    """

    def __init__(self):
        self.gaps = KNOWN_GAPS.copy()
        self._resolved: set[str] = set()
        self._partial_progress: dict[str, float] = {}

    def resolve_gap(self, gap_id: str):
        """Mark a gap as solved (e.g. Lemma K proven)."""
        self._resolved.add(gap_id)
        print(f"  [GapOracle] GAP RESOLVED: {gap_id}")

    def update_progress(self, gap_id: str, progress: float):
        """Track partial progress on a gap (0..1)."""
        self._partial_progress[gap_id] = progress

    def _urgency(self, gap_id: str, gap_info: dict,
                  hypotheses: list["Hypothesis"]) -> float:
        """
        Urgency = priority × (champions_blocked / total_champions)
                  × (1 - partial_progress)
        """
        if gap_id in self._resolved:
            return 0.0

        from core.hypothesis import HypothesisStatus
        n_champions = sum(1 for h in hypotheses
                         if h.status == HypothesisStatus.CHAMPION)
        n_blocked_champions = sum(
            1 for h in hypotheses
            if h.status == HypothesisStatus.CHAMPION
            and any(b in h.blocked_by for b in [gap_id])
        )
        champion_factor = (n_blocked_champions + 1) / (n_champions + 1)
        progress_factor = 1.0 - self._partial_progress.get(gap_id, 0.0)
        return gap_info["priority"] * champion_factor * progress_factor

    def get_constraints(self, hypotheses: list["Hypothesis"],
                        n: int = 3) -> list[GapConstraint]:
        """
        Return the top-n gap constraints for this iteration,
        ordered by urgency.
        """
        scored = []
        for gap_id, info in self.gaps.items():
            if gap_id in self._resolved:
                continue
            urgency = self._urgency(gap_id, info, hypotheses)
            scored.append((urgency, gap_id, info))

        scored.sort(reverse=True)

        result = []
        for urgency, gap_id, info in scored[:n]:
            result.append(GapConstraint(
                gap_id=gap_id,
                label=info["label"],
                k_range=info["k_range"],
                attack_direction=info["attack_direction"],
                priority=info["priority"],
                conductor=info.get("conductor"),
                blocks=info["blocks"],
                urgency=urgency,
            ))
        return result

    def get_open_k_values(self, hypotheses: list["Hypothesis"]) -> list[int]:
        """
        Return k values that appear in open gaps but haven't been
        fully explored by existing hypotheses.
        """
        covered_k: set[int] = set()
        for h in hypotheses:
            if h.gap_pct < 5.0:
                covered_k.update(h.k_values)

        open_k: set[int] = set()
        for gap_id, info in self.gaps.items():
            if gap_id not in self._resolved:
                open_k.update(info.get("k_range", []))

        return sorted(open_k - covered_k)

    def gap_report(self, hypotheses: list["Hypothesis"]) -> str:
        """Human-readable gap status report."""
        constraints = self.get_constraints(hypotheses, n=len(self.gaps))
        lines = ["=== Gap Oracle Report ==="]
        for c in constraints:
            prog = self._partial_progress.get(c.gap_id, 0.0)
            bar = "█" * int(prog * 10) + "░" * (10 - int(prog * 10))
            lines.append(
                f"  [{c.gap_id:30s}] urgency={c.urgency:.2f}  [{bar}] {int(prog*100)}%"
            )
        resolved = [g for g in self.gaps if g in self._resolved]
        if resolved:
            lines.append(f"  Resolved: {', '.join(resolved)}")
        return "\n".join(lines)
