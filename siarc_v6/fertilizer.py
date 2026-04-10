"""
SIARC v6 — Cross-Hypothesis Fertilizer
=======================================
KEY UNLOCK #2: algebraic crossbreeding between high-gradient hypotheses.

v5 flaw:  H-0025, C_P14_01, BOREL-L1 work in silos.
v6 fix:   Algebraic distance sampling ensures genuine novelty;
          fertilized offspring inherit the best structural features
          of both parents while targeting open gaps.

Crossbreeding strategies:
  1. ALPHA_BLEND    — interpolate α coefficients between parents
  2. BETA_SWAP      — take β from one parent, α from another
  3. K_EXTENSION    — extend parent's k-range to open gap k values
  4. CONDUCTOR_LIFT — lift conductor from N₅=24 toward generalised N_k
  5. STRUCTURAL_MIX — combine formula structure from different papers
"""

from __future__ import annotations
import random
import math
import time
from typing import TYPE_CHECKING

from core.hypothesis import Hypothesis, BirthMode, HypothesisStatus

if TYPE_CHECKING:
    from core.gap_oracle import GapOracle, GapConstraint


def _make_id(prefix: str = "F") -> str:
    return f"{prefix}-{int(time.time()*1000) % 1_000_000:06d}"


# ─── Algebraic distance ────────────────────────────────────────────────────

def algebraic_distance(h1: Hypothesis, h2: Hypothesis) -> float:
    """
    Measure how algebraically different two hypotheses are.
    High distance → diverse parents → more novel offspring.
    Low distance → too similar → likely redundant offspring.
    """
    score = 0.0

    # k-range overlap
    k1, k2 = set(h1.k_values), set(h2.k_values)
    if k1 and k2:
        overlap = len(k1 & k2) / max(len(k1 | k2), 1)
        score += (1.0 - overlap) * 30.0   # diverse k-ranges preferred

    # α coefficient distance
    if h1.alpha is not None and h2.alpha is not None:
        score += abs(h1.alpha - h2.alpha) * 50.0

    # β coefficient distance
    if h1.beta is not None and h2.beta is not None:
        score += abs(h1.beta - h2.beta) * 20.0

    # paper diversity bonus
    if h1.paper != h2.paper:
        score += 15.0

    # conductor diversity
    if h1.conductor != h2.conductor:
        score += 10.0

    return score


# ─── Individual crossbreeding strategies ──────────────────────────────────

def _alpha_blend(h1: Hypothesis, h2: Hypothesis,
                 target_k: list[int]) -> dict:
    """Blend α between two parents, target open k values."""
    a1 = h1.alpha or 0.0
    a2 = h2.alpha or 0.0
    lam = random.uniform(0.3, 0.7)
    new_alpha = lam * a1 + (1 - lam) * a2

    b1 = h1.beta or 0.0
    b2 = h2.beta or 0.0
    new_beta = b1 if abs(b1) > abs(b2) else b2   # stronger β dominates

    k_vals = target_k or sorted(set(h1.k_values) | set(h2.k_values))
    # Represent as fraction for readability
    alpha_frac = _float_to_frac(new_alpha)
    formula = f"A₁⁽ᵏ⁾ = {alpha_frac}·(k·c_k) − (k+1)(k+3)/(8·c_k)"
    return {
        "formula": formula,
        "alpha": new_alpha,
        "beta": new_beta,
        "k_values": k_vals,
        "description": f"α-blend of {h1.hyp_id} (λ={lam:.2f}) and {h2.hyp_id}",
        "strategy": "ALPHA_BLEND",
    }


def _beta_swap(h1: Hypothesis, h2: Hypothesis,
               target_k: list[int]) -> dict:
    """Take α from dominant parent, β from the other."""
    # dominant = higher gradient score
    dominant = h1 if h1.gradient_score() >= h2.gradient_score() else h2
    recessive = h2 if dominant is h1 else h1

    alpha = dominant.alpha or (-1/48)
    beta  = recessive.beta  or 0.0
    k_vals = target_k or sorted(set(h1.k_values) | set(h2.k_values))
    alpha_frac = _float_to_frac(alpha)
    formula = f"A₁⁽ᵏ⁾ = {alpha_frac}·(k·c_k) + {beta:.4f}/c_k"
    return {
        "formula": formula,
        "alpha": alpha,
        "beta": beta,
        "k_values": k_vals,
        "description": f"β-swap: α from {dominant.hyp_id}, β from {recessive.hyp_id}",
        "strategy": "BETA_SWAP",
    }


def _k_extension(h1: Hypothesis, h2: Hypothesis,
                 target_k: list[int]) -> dict:
    """Extend the dominant parent's formula to open gap k values."""
    dominant = h1 if h1.gradient_score() >= h2.gradient_score() else h2
    base_k   = sorted(set(dominant.k_values) | set(target_k))
    alpha    = dominant.alpha or (-1/48)
    beta     = dominant.beta  or 0.0
    alpha_frac = _float_to_frac(alpha)
    formula = f"A₁⁽ᵏ⁾ = {alpha_frac}·(k·c_k) − (k+1)(k+3)/(8·c_k)  [k∈{base_k}]"
    return {
        "formula": formula,
        "alpha": alpha,
        "beta": beta,
        "k_values": base_k,
        "description": f"k-extension of {dominant.hyp_id} to k={target_k}",
        "strategy": "K_EXTENSION",
    }


def _conductor_lift(h1: Hypothesis, h2: Hypothesis,
                    target_k: list[int]) -> dict:
    """
    Generalise from specific conductor (N₅=24) to general N_k.
    Key for unlocking Lemma K generalisation.
    """
    # Hypothesise the general conductor formula
    # Known: N₅=24. Pattern from modular forms: N_k = lcm(k, 24) or 24k etc.
    cond_formula = "N_k = 24·k / gcd(k, 24)"  # hypothesis to test
    k_vals = target_k or [5, 6, 7, 8]
    formula = (
        f"A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  "
        f"with Lemma K at conductor {cond_formula}"
    )
    return {
        "formula": formula,
        "alpha": -1/48,
        "beta": 0.0,  # β encoded in (k+1)(k+3)/8 term
        "k_values": k_vals,
        "conductor": None,   # generalised — no fixed conductor
        "description": f"Conductor lift: generalise N₅=24 → {cond_formula}",
        "strategy": "CONDUCTOR_LIFT",
    }


def _structural_mix(h1: Hypothesis, h2: Hypothesis,
                    target_k: list[int]) -> dict:
    """Combine structural elements from different papers."""
    k_vals = target_k or sorted(set(h1.k_values) | set(h2.k_values))
    # Combine G-01 universal law structure with Borel-type growth
    formula = (
        f"A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  "
        f"[structural: {h1.paper}×{h2.paper} mix]"
    )
    return {
        "formula": formula,
        "alpha": -1/48,
        "beta": 0.0,
        "k_values": k_vals,
        "description": (
            f"Structural mix {h1.hyp_id}({h1.paper}) × {h2.hyp_id}({h2.paper})"
        ),
        "strategy": "STRUCTURAL_MIX",
    }


STRATEGIES = [_alpha_blend, _beta_swap, _k_extension,
              _conductor_lift, _structural_mix]


# ─── Fertilizer ───────────────────────────────────────────────────────────

class CrossHypFertilizer:
    """
    Selects diverse parent pairs and applies algebraic crossbreeding.
    Uses breakthrough gradient scores to bias parent selection toward
    high-signal hypotheses while maintaining diversity.
    """

    # Minimum algebraic distance to accept a pair as "diverse enough"
    MIN_DISTANCE = 15.0

    def __init__(self, oracle: "GapOracle"):
        self.oracle = oracle
        self._lineage_log: list[dict] = []

    def _select_parents(
        self,
        pool: list[Hypothesis],
        n_pairs: int = 3,
    ) -> list[tuple[Hypothesis, Hypothesis]]:
        """
        Select diverse parent pairs weighted by gradient score.
        Tournament selection with diversity pressure.
        """
        # Score each hypothesis: gradient × (1 + gate_bonus)
        def parent_weight(h: Hypothesis) -> float:
            base = max(h.gradient_score(), 0.1)
            gate_mult = 1 + h.gates_passed * 0.25
            return base * gate_mult

        weights = [parent_weight(h) for h in pool]
        total_w = sum(weights) or 1.0
        probs   = [w / total_w for w in weights]

        pairs = []
        attempts = 0
        while len(pairs) < n_pairs and attempts < 50:
            attempts += 1
            # Weighted sample without replacement
            idxs = random.choices(range(len(pool)), weights=probs, k=2)
            if idxs[0] == idxs[1]:
                continue
            p1, p2 = pool[idxs[0]], pool[idxs[1]]
            dist = algebraic_distance(p1, p2)
            if dist >= self.MIN_DISTANCE:
                pairs.append((p1, p2))

        return pairs

    def breed(
        self,
        pool: list[Hypothesis],
        n_offspring: int = 5,
        gap_constraints: list["GapConstraint"] | None = None,
    ) -> list[Hypothesis]:
        """
        Generate n_offspring new hypotheses by crossbreeding.
        Gap constraints bias offspring toward open gaps.
        """
        if len(pool) < 2:
            return []

        # Determine target k values from open gaps
        target_k: list[int] = []
        if gap_constraints:
            for c in gap_constraints:
                target_k.extend(c.k_range)
        target_k = sorted(set(target_k))

        # Also pull from oracle directly
        if not target_k:
            target_k = self.oracle.get_open_k_values(pool)

        pairs   = self._select_parents(pool, n_pairs=n_offspring)
        offspring = []

        for i, (p1, p2) in enumerate(pairs):
            strategy_fn = STRATEGIES[i % len(STRATEGIES)]
            spec = strategy_fn(p1, p2, target_k)

            child = Hypothesis(
                hyp_id      = _make_id("F"),
                formula     = spec["formula"],
                description = spec["description"],
                paper       = "P3",
                birth_mode  = BirthMode.FERTILIZED,
                parent_ids  = [p1.hyp_id, p2.hyp_id],
                k_values    = spec.get("k_values", target_k),
                alpha       = spec.get("alpha"),
                beta        = spec.get("beta"),
                conductor   = spec.get("conductor", p1.conductor),
                conjecture_ref = p1.conjecture_ref or p2.conjecture_ref,
                sig         = max(p1.sig, p2.sig) * 0.7,   # inherit partial sig
                lfi         = (p1.lfi + p2.lfi) / 2,
                gap_pct     = min(p1.gap_pct, p2.gap_pct) * 0.9,
                proof_progress = 0.0,
                status      = HypothesisStatus.EMBRYO,
            )

            # Inherit blocked_by from parents (cascade it down)
            child.blocked_by = list(set(p1.blocked_by) | set(p2.blocked_by))

            offspring.append(child)
            self._lineage_log.append({
                "child": child.hyp_id,
                "parents": [p1.hyp_id, p2.hyp_id],
                "strategy": spec["strategy"],
                "dist": round(algebraic_distance(p1, p2), 1),
            })

        return offspring

    def lineage_report(self, last_n: int = 10) -> str:
        lines = ["=== Fertilizer Lineage (last {}) ===".format(last_n)]
        for entry in self._lineage_log[-last_n:]:
            lines.append(
                f"  {entry['child']:15s} ← {entry['parents'][0]} × {entry['parents'][1]}"
                f"  [{entry['strategy']:18s}]  dist={entry['dist']}"
            )
        return "\n".join(lines)


# ─── Utility ──────────────────────────────────────────────────────────────

def _float_to_frac(x: float) -> str:
    """Convert common float coefficients to fraction strings."""
    table = {
        -1/48: "-1/48",
         1/48:  "1/48",
        -1/8:  "-1/8",
         1/8:   "1/8",
        -5/48: "-5/48",
        -1/6:  "-1/6",
        -1/4:  "-1/4",
        -1/12: "-1/12",
    }
    for v, s in table.items():
        if abs(x - v) < 1e-10:
            return s
    return f"{x:.6f}"
