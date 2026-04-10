"""
SIARC v6 — Escape Ratchet
==========================
v5 flaw:  Agents iterate near existing hypotheses indefinitely once
          sig plateaus. Local minima trap.
v6 fix:   Detect plateau → force teleportation to orthogonal region
          of the (α, β, k) hypothesis space.

Teleportation strategies:
  1. K_JUMP        — jump to unexplored k band (e.g. k=13..20)
  2. ALPHA_FLIP    — negate or invert the α coefficient
  3. BETA_EXPLORE  — large β perturbation (×5..×20)
  4. CONDUCTOR_NEW — try a different conductor modulus
  5. FORMULA_MORPH — try structurally different formula ansatz
  6. CROSS_PAPER   — borrow structure from a different paper thread
"""

from __future__ import annotations
import random
import math
import time
from typing import TYPE_CHECKING

from core.hypothesis import Hypothesis, BirthMode, HypothesisStatus

if TYPE_CHECKING:
    from core.gap_oracle import GapOracle


PLATEAU_WINDOW   = 20    # iterations without sig improvement
PLATEAU_DELTA    = 0.5   # minimum sig change to NOT be plateau
ESCAPE_COOLDOWN  = 5     # iterations after teleport before next escape allowed

# Alternative conductors to try (beyond N₅=24)
_ALT_CONDUCTORS = [1, 6, 12, 24, 48, 60, 120]

# Alternative α fractions to explore
_ALPHA_CANDIDATES = [
    -1/48, -1/24, -1/12, -1/8, -1/6, -1/4,
    -5/48, -7/48, -11/48, -13/48,
    -1/32, -1/16, -3/16,
]

# Alternative β patterns
_BETA_PATTERNS = [
    lambda k: -(k+1)*(k+3)/8,     # G-01 canonical
    lambda k: -(k+1)*(k+2)/8,     # shifted
    lambda k: -(k+2)*(k+4)/8,     # shifted+
    lambda k: -k*(k+2)/8,         # k-anchored
    lambda k: -(k**2+4*k+3)/8,    # expanded
    lambda k: -(k+1)**2/8,        # perfect square
    lambda k: -(k+1)*(k+3)/6,     # different denominator
    lambda k: -(k+1)*(k+3)/10,    # different denominator
]


def _make_id(prefix: str = "E") -> str:
    return f"{prefix}-{int(time.time()*1000) % 1_000_000:06d}"


class EscapeRatchet:
    """
    Monitors hypothesis pool for plateaus.
    When detected, generates a teleport hypothesis aimed at an
    orthogonal region of formula space.
    """

    def __init__(self, oracle: "GapOracle"):
        self.oracle = oracle
        self._escape_log: list[dict] = []
        self._escaped_regions: list[dict] = []   # memory of tried regions

    def _is_plateaued(self, h: Hypothesis) -> bool:
        """Check if hypothesis is stuck."""
        if h.status in (HypothesisStatus.CHAMPION,
                        HypothesisStatus.ARCHIVED,
                        HypothesisStatus.ESCAPED):
            return False
        if h.iteration < PLATEAU_WINDOW:
            return False
        if h.plateau_count < PLATEAU_WINDOW:
            return False
        return h.is_plateau(PLATEAU_WINDOW)

    def _already_explored(self, alpha: float, k_vals: list[int]) -> bool:
        """Check if this region was already tried and failed."""
        for region in self._escaped_regions:
            if (abs(region.get("alpha", 999) - alpha) < 1e-4
                    and set(region.get("k_vals", [])) == set(k_vals)):
                return True
        return False

    # ── Teleport strategies ─────────────────────────────────────────────

    def _teleport_k_jump(self, h: Hypothesis) -> dict:
        """Jump to a k band not yet explored by any hypothesis."""
        open_k = self.oracle.get_open_k_values([h])
        if open_k:
            # Focus on the first 4 open k values as a band
            target_k = open_k[:4]
        else:
            # Explore higher k territory
            max_known = max(h.k_values) if h.k_values else 8
            start = max_known + 1
            target_k = list(range(start, start + 4))
        return {
            "formula": (
                f"A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  "
                f"[teleport k={target_k}]"
            ),
            "alpha": -1/48,
            "beta_fn": lambda k: -(k+1)*(k+3)/8,
            "k_values": target_k,
            "strategy": "K_JUMP",
            "description": f"k-jump teleport from {h.hyp_id} → k={target_k}",
        }

    def _teleport_alpha_flip(self, h: Hypothesis) -> dict:
        """Try α values not near the current one."""
        current_alpha = h.alpha or -1/48
        # Pick an α that is maximally distant
        candidates = [a for a in _ALPHA_CANDIDATES
                      if abs(a - current_alpha) > 0.01
                      and not self._already_explored(a, h.k_values)]
        if not candidates:
            candidates = _ALPHA_CANDIDATES
        new_alpha = random.choice(candidates)
        k_vals = h.k_values or [5, 6, 7, 8]
        frac = _float_to_frac(new_alpha)
        return {
            "formula": (
                f"A₁⁽ᵏ⁾ = {frac}·(k·c_k) − (k+1)(k+3)/(8·c_k)"
            ),
            "alpha": new_alpha,
            "beta_fn": _BETA_PATTERNS[0],
            "k_values": k_vals,
            "strategy": "ALPHA_FLIP",
            "description": f"α-flip teleport from {h.hyp_id}: α={frac}",
        }

    def _teleport_beta_explore(self, h: Hypothesis) -> dict:
        """Try a structurally different β pattern."""
        beta_fn_idx = random.randint(0, len(_BETA_PATTERNS) - 1)
        beta_fn = _BETA_PATTERNS[beta_fn_idx]
        alpha = h.alpha or -1/48
        k_vals = h.k_values or [5, 6, 7, 8]
        # Show what β evaluates to at k=5 as a hint
        beta_at_5 = beta_fn(5)
        return {
            "formula": (
                f"A₁⁽ᵏ⁾ = {_float_to_frac(alpha)}·(k·c_k) "
                f"+ β_k/c_k  [β pattern {beta_fn_idx}, β(5)={beta_at_5:.4f}]"
            ),
            "alpha": alpha,
            "beta_fn": beta_fn,
            "k_values": k_vals,
            "strategy": "BETA_EXPLORE",
            "description": f"β-explore teleport from {h.hyp_id}, pattern {beta_fn_idx}",
        }

    def _teleport_conductor_new(self, h: Hypothesis) -> dict:
        """Try a different conductor modulus."""
        tried = {h.conductor}
        candidates = [c for c in _ALT_CONDUCTORS if c not in tried]
        new_cond = random.choice(candidates) if candidates else 12
        k_vals = h.k_values or [5]
        return {
            "formula": (
                f"A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  "
                f"[Lemma K at conductor N={new_cond}]"
            ),
            "alpha": -1/48,
            "beta_fn": _BETA_PATTERNS[0],
            "k_values": k_vals,
            "conductor": new_cond,
            "strategy": "CONDUCTOR_NEW",
            "description": f"conductor teleport from {h.hyp_id}: N→{new_cond}",
        }

    def _teleport_formula_morph(self, h: Hypothesis) -> dict:
        """Try a structurally different formula ansatz."""
        # Alternative: log-correction term
        alpha = h.alpha or -1/48
        k_vals = h.k_values or [5, 6, 7, 8]
        frac = _float_to_frac(alpha)
        return {
            "formula": (
                f"A₁⁽ᵏ⁾ = {frac}·(k·c_k) − (k+1)(k+3)/(8·c_k) "
                f"+ O(log(c_k)/c_k²)  [with log-correction]"
            ),
            "alpha": alpha,
            "beta_fn": _BETA_PATTERNS[0],
            "k_values": k_vals,
            "strategy": "FORMULA_MORPH",
            "description": f"formula-morph teleport from {h.hyp_id}: add log-correction",
        }

    _TELEPORT_STRATEGIES = [
        "_teleport_k_jump",
        "_teleport_alpha_flip",
        "_teleport_beta_explore",
        "_teleport_conductor_new",
        "_teleport_formula_morph",
    ]

    def _teleport(self, h: Hypothesis) -> Hypothesis:
        """Generate a teleport hypothesis from a plateaued one."""
        strategy_name = random.choice(self._TELEPORT_STRATEGIES)
        strategy_fn   = getattr(self, strategy_name)
        spec          = strategy_fn(h)

        child = Hypothesis(
            hyp_id      = _make_id("E"),
            formula     = spec["formula"],
            description = spec["description"],
            paper       = h.paper,
            birth_mode  = BirthMode.TELEPORT,
            parent_ids  = [h.hyp_id],
            k_values    = spec.get("k_values", h.k_values),
            alpha       = spec.get("alpha"),
            beta        = None,   # β computed per-k by beta_fn
            conductor   = spec.get("conductor", h.conductor),
            conjecture_ref = h.conjecture_ref,
            sig         = 0.0,    # fresh start
            lfi         = 1.0,
            gap_pct     = 100.0,
            proof_progress = 0.0,
            status      = HypothesisStatus.EMBRYO,
        )

        # Record the region we're jumping to
        self._escaped_regions.append({
            "alpha": child.alpha,
            "k_vals": child.k_values,
        })

        self._escape_log.append({
            "source": h.hyp_id,
            "child": child.hyp_id,
            "strategy": spec["strategy"],
            "source_plateau_count": h.plateau_count,
        })

        # Mark the plateaued hypothesis as escaped
        h.status = HypothesisStatus.ESCAPED

        return child

    # ── Public interface ────────────────────────────────────────────────

    def scan_and_escape(
        self,
        pool: list[Hypothesis],
        max_escapes: int = 2,
    ) -> list[Hypothesis]:
        """
        Scan pool for plateaued hypotheses.
        Generate teleport offspring for up to max_escapes of them.
        Returns list of new teleport hypotheses.
        """
        plateaued = [h for h in pool if self._is_plateaued(h)]
        if not plateaued:
            return []

        # Prioritise hypotheses with highest gate count (most valuable to escape)
        plateaued.sort(key=lambda h: h.gates_passed, reverse=True)

        new_hyps = []
        for h in plateaued[:max_escapes]:
            child = self._teleport(h)
            new_hyps.append(child)
            print(f"  [EscapeRatchet] PLATEAU ESCAPED: {h.hyp_id} "
                  f"(plateau={h.plateau_count}) → {child.hyp_id} "
                  f"[{child.description[:50]}]")

        return new_hyps

    def escape_report(self) -> str:
        lines = [f"=== Escape Ratchet Log ({len(self._escape_log)} escapes) ==="]
        for e in self._escape_log[-10:]:
            lines.append(
                f"  {e['source']:15s} → {e['child']:15s}  "
                f"[{e['strategy']:20s}]  plateau_count={e['source_plateau_count']}"
            )
        return "\n".join(lines)


def _float_to_frac(x: float) -> str:
    table = {
        -1/48: "-1/48",  1/48: "1/48",
        -1/24: "-1/24",  1/24: "1/24",
        -1/12: "-1/12",  1/12: "1/12",
        -1/8:  "-1/8",   1/8:  "1/8",
        -1/6:  "-1/6",   1/6:  "1/6",
        -1/4:  "-1/4",   1/4:  "1/4",
        -5/48: "-5/48",  5/48: "5/48",
        -7/48: "-7/48",  7/48: "7/48",
    }
    for v, s in table.items():
        if abs(x - v) < 1e-10:
            return s
    return f"{x:.6f}"
