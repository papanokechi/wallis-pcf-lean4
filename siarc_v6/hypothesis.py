"""
SIARC v6 — Core Hypothesis Data Structures
Breakthrough Gradient scoring: continuous signal, not binary.
"""

from __future__ import annotations
import time
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class HypothesisStatus(Enum):
    EMBRYO      = "embryo"       # just born, unverified
    ACTIVE      = "active"       # under iteration
    CHAMPION    = "champion"     # sig >= 90, gap == 0
    PLATEAU     = "plateau"      # sig stagnant > PLATEAU_WINDOW iters
    ESCAPED     = "escaped"      # was plateau, teleported to new region
    BLOCKED     = "blocked"      # waiting on a lemma
    CASCADE     = "cascade"      # spawned as cascade child
    ARCHIVED    = "archived"     # retired


class BirthMode(Enum):
    SEED        = "seed"         # initial seed hypothesis
    MUTATION    = "mutation"     # small perturbation of parent
    FERTILIZED  = "fertilized"   # algebraic crossbreed of 2+ parents
    GAP_TARGET  = "gap_target"   # oracle-targeted at open gap
    TELEPORT    = "teleport"     # escape-ratchet jump
    CASCADE     = "cascade"      # spawned from completed cascade lane


@dataclass
class BreakthroughGradient:
    """Continuous gradient signal — not just 0/1 breakthrough count."""
    sig_delta:      float = 0.0   # Δsig from last iter
    lfi_delta:      float = 0.0   # ΔLFI (negative = improving)
    gap_delta:      float = 0.0   # Δgap% (negative = improving)
    proof_delta:    float = 0.0   # Δproof progress
    gate_bonus:     int   = 0     # +1 per gate passed this iter
    raw_score:      float = 0.0   # composite gradient magnitude

    def compute(self) -> float:
        """Composite gradient — weights tuned for analytic NT discovery."""
        s = (
            self.sig_delta    * 2.0    +   # sig improvement is primary signal
            (-self.lfi_delta) * 15.0   +   # LFI drop is very informative
            (-self.gap_delta) * 5.0    +   # gap closure
            self.proof_delta  * 3.0    +   # proof progress
            self.gate_bonus   * 10.0       # discrete gate passing
        )
        self.raw_score = s
        return s


@dataclass
class Hypothesis:
    """A single SIARC hypothesis with full lineage and gradient tracking."""

    # Identity
    hyp_id:         str
    formula:        str
    description:    str
    paper:          str             = "P3"
    birth_mode:     BirthMode       = BirthMode.SEED
    parent_ids:     list[str]       = field(default_factory=list)

    # Mathematical content
    k_values:       list[int]       = field(default_factory=list)   # e.g. [5,6,7,8]
    alpha:          Optional[float] = None    # α coefficient
    beta:           Optional[float] = None    # β coefficient
    conductor:      Optional[int]   = None    # e.g. N₅=24
    conjecture_ref: Optional[str]   = None    # e.g. "Conjecture 2*"

    # SIARC metrics
    sig:            float = 0.0
    lfi:            float = 1.0
    gap_pct:        float = 100.0
    proof_progress: float = 0.0
    gates_passed:   int   = 0
    gates_total:    int   = 4

    # Status tracking
    status:         HypothesisStatus = HypothesisStatus.EMBRYO
    iteration:      int   = 0
    plateau_count:  int   = 0
    created_at:     float = field(default_factory=time.time)
    last_updated:   float = field(default_factory=time.time)

    # Gradient history (last N iterations)
    gradient_history: list[float] = field(default_factory=list)
    sig_history:      list[float] = field(default_factory=list)

    # Lemma dependencies
    blocked_by:     list[str] = field(default_factory=list)   # e.g. ["LEMMA_K_k5"]

    # Cascade
    cascade_lanes:  list[str] = field(default_factory=list)
    cascade_results: dict     = field(default_factory=dict)

    # Breakthrough record
    breakthrough_count: int   = 0
    breakthrough_iters: list[int] = field(default_factory=list)

    def fingerprint(self) -> str:
        """Algebraic fingerprint for deduplication."""
        key = f"{self.formula}|{sorted(self.k_values)}|{self.alpha}|{self.beta}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def gradient_score(self) -> float:
        """Rolling average of recent gradient — used by fertilizer."""
        if not self.gradient_history:
            return 0.0
        window = self.gradient_history[-10:]
        return sum(window) / len(window)

    def is_plateau(self, window: int = 20) -> bool:
        """True if sig hasn't improved meaningfully in `window` iterations."""
        if len(self.sig_history) < window:
            return False
        recent = self.sig_history[-window:]
        return (max(recent) - min(recent)) < 0.5

    def is_champion(self) -> bool:
        return self.sig >= 90 and self.gap_pct == 0.0 and self.gates_passed >= 4

    def is_breakthrough(self) -> bool:
        return self.sig >= 85 and self.gap_pct < 5.0

    def update_gradient(self, prev_sig: float, prev_lfi: float,
                         prev_gap: float, prev_proof: float,
                         gates_this_iter: int) -> float:
        g = BreakthroughGradient(
            sig_delta   = self.sig - prev_sig,
            lfi_delta   = self.lfi - prev_lfi,
            gap_delta   = self.gap_pct - prev_gap,
            proof_delta = self.proof_progress - prev_proof,
            gate_bonus  = gates_this_iter,
        )
        score = g.compute()
        self.gradient_history.append(score)
        self.sig_history.append(self.sig)
        self.last_updated = time.time()
        return score

    def to_dict(self) -> dict:
        d = {
            "id": self.hyp_id,
            "formula": self.formula,
            "description": self.description,
            "birth_mode": self.birth_mode.value,
            "parent_ids": self.parent_ids,
            "sig": round(self.sig, 2),
            "lfi": round(self.lfi, 3),
            "gap_pct": round(self.gap_pct, 2),
            "proof_progress": round(self.proof_progress, 1),
            "gates_passed": self.gates_passed,
            "status": self.status.value,
            "iteration": self.iteration,
            "gradient_score": round(self.gradient_score(), 3),
            "breakthrough_count": self.breakthrough_count,
            "blocked_by": self.blocked_by,
        }
        return d
