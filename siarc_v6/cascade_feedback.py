"""
SIARC v6 — Cascade Feedback Engine
=====================================
v5 flaw:  Completed cascade lanes sit "pending integration".
          Their proofs never re-enter the generation pool.
v6 fix:   Cascade completions immediately generate 3 child
          hypotheses using the proven result as a structural seed.

Example:
  H-0025→G01-PACKET (100% proof progress, 0% gap) completes.
  → Child 1: Extend G-01 proof package to k=9..12
  → Child 2: Apply G-01 structure to β_k closed form
  → Child 3: Use G-01 as lemma to attack Theorem 2* directly
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.hypothesis import Hypothesis, BirthMode, HypothesisStatus

if TYPE_CHECKING:
    from core.gap_oracle import GapOracle


def _make_id(prefix: str = "C") -> str:
    return f"{prefix}-{int(time.time()*1000) % 1_000_000:06d}"


@dataclass
class CascadeCompletion:
    """Records a completed cascade lane ready for injection."""
    source_id:     str
    cascade_lane:  str
    proof_result:  str    # what was proven
    formula:       str
    k_values:      list[int]
    alpha:         float | None
    paper:         str
    completed_at:  float = field(default_factory=time.time)
    injected:      bool  = False


# Templates for generating cascade offspring
# Each template describes how to extend a completed cascade result

CASCADE_EXTENSION_TEMPLATES = [
    {
        "name": "k_extension",
        "description_template": "Extend {proof_result} to k={next_k}",
        "formula_modifier": lambda f, k: f.replace(
            "[k≥5 extended]", f"[k={k} extension]"
        ) if "[k≥5" in f else f + f"  [extended to k={k}]",
        "k_shift": +4,   # extend to next k band
        "sig_inherit": 0.85,
        "gap_inherit": 0.05,
    },
    {
        "name": "beta_application",
        "description_template": "Apply {proof_result} to β_k closed form",
        "formula_modifier": lambda f, k: (
            f"β_k / A₂⁽ᵏ⁾ = -(k+1)(k+3)/(8·c_k)  [from {f[:40]}...]"
        ),
        "k_shift": 0,
        "sig_inherit": 0.75,
        "gap_inherit": 0.15,
    },
    {
        "name": "theorem_attack",
        "description_template": "Use {proof_result} as lemma → Theorem 2* direct attack",
        "formula_modifier": lambda f, k: (
            f"Theorem 2* (k≥5): A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  "
            f"[via cascade lemma]"
        ),
        "k_shift": 0,
        "sig_inherit": 0.90,   # theorem attack inherits high sig
        "gap_inherit": 0.03,
    },
]


class CascadeFeedbackEngine:
    """
    Monitors cascade lane completions and injects offspring
    back into the hypothesis pool every iteration.
    """

    def __init__(self, oracle: "GapOracle"):
        self.oracle = oracle
        self._pending: list[CascadeCompletion] = []
        self._injection_log: list[dict] = []

        # Pre-load known completed cascades from v5
        self._pre_load_v5_completions()

    def _pre_load_v5_completions(self):
        """
        Pre-load v5's completed cascade results so they immediately
        feed back into v6 on first run.
        """
        self._pending.append(CascadeCompletion(
            source_id    = "H-0025",
            cascade_lane = "H-0025→G01-PACKET-BT69979",
            proof_result = "G-01 derivation package — full symbolic proof Lemma K→Theorem 2*",
            formula      = "A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  [k≥5]",
            k_values     = [5, 6, 7, 8],
            alpha        = -1/48,
            paper        = "P3",
        ))
        # Mark oracle progress for the associated gap
        self.oracle.update_progress("LEMMA_K_k5", 0.7)

    def register_completion(self, completion: CascadeCompletion):
        """Register a newly completed cascade lane."""
        self._pending.append(completion)
        print(f"  [CascadeFeedback] Registered completion: {completion.cascade_lane}")

    def check_hypothesis_cascades(self, hypotheses: list[Hypothesis]):
        """Scan hypothesis list for newly completed cascade lanes."""
        for h in hypotheses:
            for lane_id, result in h.cascade_results.items():
                if result.get("proof_progress", 0) >= 1.0:
                    # Check if already registered
                    known = {c.cascade_lane for c in self._pending}
                    if lane_id not in known:
                        completion = CascadeCompletion(
                            source_id    = h.hyp_id,
                            cascade_lane = lane_id,
                            proof_result = result.get("description", "proven"),
                            formula      = h.formula,
                            k_values     = h.k_values,
                            alpha        = h.alpha,
                            paper        = h.paper,
                        )
                        self.register_completion(completion)

    def inject(self, pool: list[Hypothesis]) -> list[Hypothesis]:
        """
        For each pending (uninjected) completion, generate 3 offspring
        and add them to the pool.
        """
        new_hyps = []

        for completion in self._pending:
            if completion.injected:
                continue

            print(f"  [CascadeFeedback] INJECTING from: {completion.cascade_lane}")

            for tmpl in CASCADE_EXTENSION_TEMPLATES:
                max_k = max(completion.k_values) if completion.k_values else 8
                target_k_max = max_k + tmpl["k_shift"]

                if tmpl["k_shift"] > 0:
                    new_k = list(range(max_k + 1, target_k_max + 1))
                else:
                    new_k = completion.k_values

                new_formula = tmpl["formula_modifier"](
                    completion.formula, target_k_max
                )
                new_desc = tmpl["description_template"].format(
                    proof_result=completion.proof_result[:50],
                    next_k=new_k,
                )

                child = Hypothesis(
                    hyp_id      = _make_id("C"),
                    formula     = new_formula,
                    description = new_desc,
                    paper       = completion.paper,
                    birth_mode  = BirthMode.CASCADE,
                    parent_ids  = [completion.source_id],
                    k_values    = new_k or completion.k_values,
                    alpha       = completion.alpha,
                    sig         = 85.0 * tmpl["sig_inherit"],
                    lfi         = 0.05,
                    gap_pct     = 5.0 * (1 - tmpl["gap_inherit"]) + 0.5,
                    proof_progress = 0.0,
                    status      = HypothesisStatus.EMBRYO,
                )
                new_hyps.append(child)
                self._injection_log.append({
                    "source": completion.cascade_lane,
                    "child": child.hyp_id,
                    "template": tmpl["name"],
                })

            completion.injected = True

        return new_hyps

    def injection_report(self) -> str:
        lines = [f"=== Cascade Feedback ({len(self._injection_log)} injections) ==="]
        for entry in self._injection_log[-10:]:
            lines.append(
                f"  {entry['source'][:40]:40s} → {entry['child']}  [{entry['template']}]"
            )
        return "\n".join(lines)
