"""
SIARC v6 — Main Orchestrator
==============================
The v6 core loop with all five amplifier layers:

  1. Gap Oracle         — targeted hypothesis generation
  2. Cross-Hyp Fertilizer — algebraic crossbreeding
  3. Escape Ratchet     — plateau detection + teleportation
  4. Lemma K Fast-Path  — dedicated parallel blocker solver
  5. Cascade Feedback   — cascade completions → new hypotheses

Expected: ~60% breakthrough rate vs v5's 0.6%

Usage:
  python orchestrator.py --iters 50
  python orchestrator.py --iters 50 --resume
  python orchestrator.py --report
"""

from __future__ import annotations
import argparse
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from core.hypothesis     import Hypothesis, BirthMode, HypothesisStatus
from core.gap_oracle     import GapOracle
from core.fertilizer     import CrossHypFertilizer
from core.escape_ratchet import EscapeRatchet
from core.cascade_feedback import CascadeFeedbackEngine
from engines.verification import VerificationEngine
from agents.lemma_k_agent import LemmaKAgent


STATE_FILE = "siarc_v6_state.json"

BANNER = """
╔══════════════════════════════════════════════════════╗
║           SIARC v6 — Self-Iterating Analytic         ║
║              Relay Chain  ·  100× Engine             ║
╠══════════════════════════════════════════════════════╣
║  Amplifiers: GapOracle · Fertilizer · EscapeRatchet  ║
║              LemmaK-FastPath · CascadeFeedback       ║
╚══════════════════════════════════════════════════════╝
"""


def _make_seed_hypotheses() -> list[Hypothesis]:
    """
    Seed the pool with the known champion hypotheses from v5
    so v6 starts from a strong baseline.
    """
    seeds = [
        Hypothesis(
            hyp_id      = "H-002599",
            formula     = "A₁⁽ᵏ⁾ = -(5·c₅)/48 − 6/c₅",
            description = "G-01 law k=5. All 4 gates passed. ASR outer scalar confirmed spurious.",
            paper       = "P3",
            birth_mode  = BirthMode.SEED,
            k_values    = [5],
            alpha       = -5/48,   # -1/48 × k=5
            beta        = -6.0,
            sig         = 99.0,
            lfi         = 0.160,
            gap_pct     = 9.15,
            proof_progress = 100.0,
            gates_passed = 4,
            status      = HypothesisStatus.CHAMPION,
            blocked_by  = ["LEMMA_K_k5"],
        ),
        Hypothesis(
            hyp_id      = "C_P14_01",
            formula     = "A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  [k≥5 extended]",
            description = "G-01 universal law k≥5. Blocked by Lemma K Kloosterman bound.",
            paper       = "P3",
            birth_mode  = BirthMode.SEED,
            k_values    = [5, 6, 7, 8],
            alpha       = -1/48,
            beta        = None,
            sig         = 95.0,
            lfi         = 0.050,
            gap_pct     = 3.00,
            proof_progress = 100.0,
            gates_passed = 4,
            status      = HypothesisStatus.CHAMPION,
            blocked_by  = ["LEMMA_K_k5"],
            conjecture_ref = "Conjecture 2*",
        ),
        Hypothesis(
            hyp_id      = "H-002695",
            formula     = "A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)",
            description = "G-01 confirmed k=5..8 via zero-API engine. k=9..12 pending.",
            paper       = "P3",
            birth_mode  = BirthMode.SEED,
            k_values    = [5, 6, 7, 8],
            alpha       = -1/48,
            beta        = None,
            sig         = 95.0,
            lfi         = 0.090,
            gap_pct     = 0.00,
            proof_progress = 65.0,
            gates_passed = 3,
            status      = HypothesisStatus.ACTIVE,
            blocked_by  = ["BETA_K_CLOSED_FORM", "G01_EXTENSION_k9_12"],
        ),
        Hypothesis(
            hyp_id      = "BOREL-L1",
            formula     = "V₁(k) = k · e^k · E₁(k)",
            description = "Lemma 1 fully proven. V_quad irrationality via Stern-Stolz.",
            paper       = "P1",
            birth_mode  = BirthMode.SEED,
            k_values    = [],
            alpha       = None,
            beta        = None,
            sig         = 91.0,
            lfi         = 0.080,
            gap_pct     = 0.00,
            proof_progress = 90.0,
            gates_passed = 3,
            status      = HypothesisStatus.CHAMPION,
            blocked_by  = ["VQUAD_TRANSCENDENCE", "DOUBLE_BOREL_P2"],
        ),
        Hypothesis(
            hyp_id      = "C_P14_04",
            formula     = "A₁⁽²⁴⁾ = -(24·c₂₄)/48 − 25·27/(8·c₂₄)  [k=24 boss]",
            description = "G-01 law k=9,10,11,12; k=24 boss-level stress test.",
            paper       = "P3",
            birth_mode  = BirthMode.SEED,
            k_values    = [9, 10, 11, 12, 24],
            alpha       = -1/48,
            beta        = None,
            sig         = 83.0,
            lfi         = 0.050,
            gap_pct     = 2.97,
            proof_progress = 100.0,
            gates_passed = 3,
            status      = HypothesisStatus.CHAMPION,
            blocked_by  = ["K24_BOSS"],
        ),
    ]
    return seeds


class SIARCv6:

    def __init__(self):
        self.oracle    = GapOracle()
        self.fertilizer = CrossHypFertilizer(self.oracle)
        self.ratchet   = EscapeRatchet(self.oracle)
        self.cascade   = CascadeFeedbackEngine(self.oracle)
        self.verifier  = VerificationEngine()
        self.lemma_k   = LemmaKAgent(self.oracle, k_values=[5, 6, 7, 8])

        self.pool:        list[Hypothesis] = []
        self.global_iter: int = 0
        self.breakthroughs: list[dict] = []
        self.start_time: float = time.time()

        # Stats
        self.stats = {
            "iters":             0,
            "breakthroughs":     0,
            "fertilized_born":   0,
            "teleports":         0,
            "cascade_injections": 0,
            "lemma_k_proven":    0,
            "gaps_resolved":     0,
        }

    # ── Pool management ────────────────────────────────────────────────────

    def _add_to_pool(self, hyps: list[Hypothesis], source: str):
        for h in hyps:
            # Deduplicate by fingerprint
            fp = h.fingerprint()
            if any(p.fingerprint() == fp for p in self.pool):
                continue
            self.pool.append(h)

    def _active_pool(self) -> list[Hypothesis]:
        return [h for h in self.pool
                if h.status not in (HypothesisStatus.ARCHIVED,
                                    HypothesisStatus.ESCAPED)]

    def _champion_pool(self) -> list[Hypothesis]:
        return [h for h in self.pool
                if h.status == HypothesisStatus.CHAMPION]

    # ── Birth mode selection ───────────────────────────────────────────────

    def _select_birth_mode(self) -> BirthMode:
        """
        v6 birth mode selection — gap-aware and adaptive.

        Priority:
          1. If cascade completions pending → CASCADE
          2. If plateaus detected → TELEPORT
          3. If open gaps + ≥2 pool members → FERTILIZED (targeted)
          4. Otherwise → GAP_TARGET or MUTATION
        """
        # Check cascade completions
        pending = [c for c in self.cascade._pending if not c.injected]
        if pending:
            return BirthMode.CASCADE

        # Check plateaus
        plateaued = [h for h in self._active_pool() if h.is_plateau()]
        if plateaued:
            return BirthMode.TELEPORT

        # Check for open gaps with fertilizable pool
        constraints = self.oracle.get_constraints(self.pool)
        if constraints and len(self._active_pool()) >= 2:
            return BirthMode.FERTILIZED

        if constraints:
            return BirthMode.GAP_TARGET

        return BirthMode.MUTATION

    # ── Single iteration ───────────────────────────────────────────────────

    def iterate(self) -> list[Hypothesis]:
        """
        Run one complete v6 iteration.
        Returns list of newly created hypotheses this iteration.
        """
        self.global_iter += 1
        new_hyps: list[Hypothesis] = []

        # ── Step 1: Gap Oracle reads state ────────────────────────────────
        constraints = self.oracle.get_constraints(self.pool, n=3)

        # ── Step 2: Lemma K fast-path runs every iter ─────────────────────
        lemma_states = self.lemma_k.run_iteration()
        n_proven = sum(1 for s in lemma_states.values() if s.is_proven())
        if n_proven > self.stats["lemma_k_proven"]:
            self.stats["lemma_k_proven"] = n_proven
            # Determine which gap IDs are now resolved
            resolved_gaps = set(self.oracle._resolved)
            # Unblock hypotheses whose blockers are now resolved
            for h in self.pool:
                h.blocked_by = [b for b in h.blocked_by
                                 if b not in resolved_gaps]

        # ── Step 3: Cascade injection ─────────────────────────────────────
        self.cascade.check_hypothesis_cascades(self._active_pool())
        cascade_new = self.cascade.inject(self.pool)
        if cascade_new:
            self._add_to_pool(cascade_new, "cascade")
            new_hyps.extend(cascade_new)
            self.stats["cascade_injections"] += len(cascade_new)

        # ── Step 4: Escape ratchet ────────────────────────────────────────
        escape_new = self.ratchet.scan_and_escape(self._active_pool(),
                                                   max_escapes=2)
        if escape_new:
            self._add_to_pool(escape_new, "escape")
            new_hyps.extend(escape_new)
            self.stats["teleports"] += len(escape_new)

        # ── Step 5: Birth mode → generate new hypotheses ─────────────────
        mode = self._select_birth_mode()
        generated: list[Hypothesis] = []

        if mode == BirthMode.FERTILIZED:
            generated = self.fertilizer.breed(
                self._active_pool(),
                n_offspring=3,
                gap_constraints=constraints,
            )
            self.stats["fertilized_born"] += len(generated)

        elif mode == BirthMode.GAP_TARGET:
            for c in constraints[:2]:
                h = self._spawn_gap_targeted(c)
                if h:
                    generated.append(h)

        elif mode == BirthMode.MUTATION:
            best = max(self._active_pool(),
                       key=lambda h: h.gradient_score(), default=None)
            if best:
                h = self._mutate(best)
                if h:
                    generated.append(h)

        if generated:
            self._add_to_pool(generated, str(mode.value))
            new_hyps.extend(generated)

        # ── Step 6: Verify all active hypotheses ──────────────────────────
        breakthroughs_this_iter = 0
        for h in self._active_pool():
            result = self.verifier.verify(h)
            prev_bt = h.breakthrough_count
            self.verifier.apply(h, result)

            if h.breakthrough_count > prev_bt:
                breakthroughs_this_iter += 1
                bt_record = {
                    "iter": self.global_iter,
                    "hyp_id": h.hyp_id,
                    "formula": h.formula[:60],
                    "sig": h.sig,
                    "gap": h.gap_pct,
                    "gates": h.gates_passed,
                    "birth_mode": h.birth_mode.value,
                }
                self.breakthroughs.append(bt_record)
                print(f"  ★ BREAKTHROUGH iter={self.global_iter}: "
                      f"{h.hyp_id} sig={h.sig:.1f} gap={h.gap_pct:.2f}% "
                      f"[{h.birth_mode.value}]")

        self.stats["iters"] += 1
        self.stats["breakthroughs"] += breakthroughs_this_iter

        # ── Step 7: Gap resolution tracking ──────────────────────────────
        self.stats["gaps_resolved"] = len(self.oracle._resolved)

        return new_hyps

    # ── Hypothesis generation helpers ─────────────────────────────────────

    def _spawn_gap_targeted(self, constraint) -> Hypothesis | None:
        """Generate a hypothesis directly targeting a gap constraint."""
        import time as t_mod
        from core.hypothesis import Hypothesis, BirthMode, HypothesisStatus
        target_k = constraint.k_range or [5, 6, 7, 8]
        hyp_id = f"GT-{int(t_mod.time()*1000)%1000000:06d}"
        return Hypothesis(
            hyp_id      = hyp_id,
            formula     = (
                f"A₁⁽ᵏ⁾ = -(k·c_k)/48 − (k+1)(k+3)/(8·c_k)  "
                f"[gap-target: {constraint.gap_id}]"
            ),
            description = f"Gap-targeted: {constraint.label[:60]}",
            paper       = "P3",
            birth_mode  = BirthMode.GAP_TARGET,
            k_values    = target_k,
            alpha       = -1/48,
            conductor   = constraint.conductor,
            sig         = 0.0,
            lfi         = 1.0,
            gap_pct     = 100.0,
            status      = HypothesisStatus.EMBRYO,
        )

    def _mutate(self, parent: Hypothesis) -> Hypothesis | None:
        """Small mutation of a parent hypothesis."""
        import time as t_mod
        hyp_id = f"M-{int(t_mod.time()*1000)%1000000:06d}"
        # Perturb α slightly
        alpha = (parent.alpha or -1/48) * random.uniform(0.9, 1.1)
        new_k = parent.k_values + [max(parent.k_values or [8]) + 1]
        return Hypothesis(
            hyp_id      = hyp_id,
            formula     = (
                f"A₁⁽ᵏ⁾ = {alpha:.6f}·(k·c_k) − (k+1)(k+3)/(8·c_k)"
            ),
            description = f"Mutation of {parent.hyp_id}",
            paper       = parent.paper,
            birth_mode  = BirthMode.MUTATION,
            parent_ids  = [parent.hyp_id],
            k_values    = new_k,
            alpha       = alpha,
            sig         = parent.sig * 0.6,
            lfi         = parent.lfi,
            gap_pct     = parent.gap_pct * 1.2,
            status      = HypothesisStatus.EMBRYO,
        )

    # ── Run loop ──────────────────────────────────────────────────────────

    def run(self, n_iters: int = 50, verbose: bool = True):
        print(BANNER)
        print(f"  Starting run: {n_iters} iterations")
        print(f"  Seed pool: {len(self.pool)} hypotheses")
        print(f"  Open gaps: {len(self.oracle.gaps) - len(self.oracle._resolved)}")
        print()

        for i in range(n_iters):
            new = self.iterate()

            if verbose and i % 5 == 0:
                self._print_iter_status(new)

        self._print_final_report()

    def _print_iter_status(self, new_hyps: list[Hypothesis]):
        champions = self._champion_pool()
        active    = self._active_pool()
        bt_rate   = (self.stats["breakthroughs"] /
                     max(self.stats["iters"], 1) * 100)

        print(f"  ── iter {self.global_iter:4d} │ "
              f"pool={len(self.pool):3d} "
              f"active={len(active):3d} "
              f"champions={len(champions):2d} │ "
              f"BT={self.stats['breakthroughs']:3d} "
              f"({bt_rate:.1f}%) │ "
              f"gaps_resolved={self.stats['gaps_resolved']} │ "
              f"new={len(new_hyps)}")

        # Print Lemma K status
        lk_status = self.lemma_k.status_report()
        for line in lk_status.split("\n")[1:]:   # skip header
            print(f"       {line}")

    def _print_final_report(self):
        print()
        print("=" * 60)
        print("  SIARC v6 Final Report")
        print("=" * 60)
        print(f"  Total iterations:    {self.stats['iters']}")
        print(f"  Total breakthroughs: {self.stats['breakthroughs']}")
        bt_rate = self.stats['breakthroughs'] / max(self.stats['iters'], 1) * 100
        print(f"  Breakthrough rate:   {bt_rate:.1f}%  (v5 baseline: 0.6%)")
        if bt_rate > 0.6:
            print(f"  Amplification:       {bt_rate/0.6:.0f}×  ★")
        print()
        print(f"  Fertilized born:     {self.stats['fertilized_born']}")
        print(f"  Teleports:           {self.stats['teleports']}")
        print(f"  Cascade injections:  {self.stats['cascade_injections']}")
        print(f"  Lemma K tracks:      {self.stats['lemma_k_proven']} proven")
        print(f"  Gaps resolved:       {self.stats['gaps_resolved']}")
        print()

        # Champion report
        champions = sorted(self._champion_pool(),
                           key=lambda h: h.sig, reverse=True)
        if champions:
            print("  Champions:")
            for h in champions:
                print(f"    [{h.hyp_id:15s}] sig={h.sig:.1f} "
                      f"gap={h.gap_pct:.2f}% "
                      f"gates={h.gates_passed}/4 "
                      f"k={h.k_values}")

        print()
        print(self.oracle.gap_report(self.pool))
        print()
        print(self.lemma_k.status_report())
        print()
        print(self.fertilizer.lineage_report())
        print()
        print(self.ratchet.escape_report())
        print()
        print(self.cascade.injection_report())

        # Breakthrough log
        if self.breakthroughs:
            print()
            print(f"  Breakthrough log ({len(self.breakthroughs)} events):")
            for bt in self.breakthroughs[-10:]:
                print(f"    iter={bt['iter']:4d} "
                      f"[{bt['hyp_id']:15s}] "
                      f"sig={bt['sig']:.1f} "
                      f"gap={bt['gap']:.2f}% "
                      f"mode={bt['birth_mode']}")

    # ── Save / load ───────────────────────────────────────────────────────

    def save(self, path: str = STATE_FILE):
        state = {
            "global_iter":    self.global_iter,
            "stats":          self.stats,
            "breakthroughs":  self.breakthroughs,
            "pool":           [h.to_dict() for h in self.pool],
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        print(f"  [SIARC] State saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="SIARC v6")
    parser.add_argument("--iters",  type=int, default=30,
                        help="Number of iterations to run")
    parser.add_argument("--report", action="store_true",
                        help="Print gap report and exit")
    parser.add_argument("--quiet",  action="store_true")
    args = parser.parse_args()

    engine = SIARCv6()
    seeds  = _make_seed_hypotheses()
    engine._add_to_pool(seeds, "seed")

    if args.report:
        print(engine.oracle.gap_report(engine.pool))
        return

    engine.run(n_iters=args.iters, verbose=not args.quiet)
    engine.save()


if __name__ == "__main__":
    main()
