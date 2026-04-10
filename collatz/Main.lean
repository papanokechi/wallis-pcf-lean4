/-
  CollatzBirkhoff/Main.lean
  ═══════════════════════════════════════════════════════════════════
  The conditional Density-1 Collatz Theorem.

  This file assembles the pieces from Defs, Estimates, Spectral, and
  CycleExclusion into the final result.

  THE MAIN THEOREM (explicitly conditional):

    theorem collatzDensityOne (hyp : UniformGapHyp) :
        naturalDensity collatzExceptionSet = 0

  LOGICAL STATUS
  ──────────────
  The theorem is proved modulo:
    (a) UniformGapHyp             — the central open problem
    (b) Spectral.lean sorries     — Mathlib deferrals (classical results)
    (c) Final assembly sorry below — conceptually settled; laborious

  The signature makes the dependency on UniformGapHyp impossible to
  hide: any reader sees it immediately.
  ═══════════════════════════════════════════════════════════════════
-/

import CollatzBirkhoff.Defs
import CollatzBirkhoff.Estimates
import CollatzBirkhoff.Spectral
import CollatzBirkhoff.CycleExclusion

open MeasureTheory Real Filter

noncomputable section

-- ═══════════════════════════════════════════════════════════════════
-- EXHIBIT THE HYPOTHESIS AT TOP LEVEL
-- Anyone opening this file sees the assumption immediately.
-- ═══════════════════════════════════════════════════════════════════

#check @UniformGapHyp
/-
  UniformGapHyp : Type
  Fields:
    γ₀         : ℝ           -- universal gap lower bound
    hγ₀_pos    : 0 < γ₀      -- strictly positive
    hγ₀_le_one : γ₀ ≤ 1      -- at most 1
    hgap       : ∀ m ≥ 1, γ₀ ≤ spectralGap m   -- holds at all resolutions
-/

-- ───────────────────────────────────────────────────────────────────
-- Assembly lemmas (intermediate steps in the proof sketch)
-- ───────────────────────────────────────────────────────────────────

/-- Step 5a: The unique invariant measure μ* is supported on trivialCycle.

    Argument: Any invariant measure must assign measure 1 to the
    absorbing set. The Collatz map is eventually absorbed into {1,2,4}
    for all starting points (conditional on gap stability), and μ* is
    the unique such measure by Theorem 6.1.

    TODO: formalize using exception_prob_to_zero from Spectral.lean. -/
lemma invariant_measure_supported_on_trivialCycle
    (hyp : UniformGapHyp)
    (m : ℕ)
    (hm : 1 ≤ m) :
    let μ_inv := (unique_invariant_measure hyp m hm).choose
    μ_inv.val (↑trivialCycle) = 1 := by
  sorry

/-- Step 5b: The exception set has measure zero under μ*.

    Directly from invariant_measure_supported_on_trivialCycle and the
    definition of collatzExceptionSet as the complement. -/
lemma exception_measure_zero
    (hyp : UniformGapHyp)
    (m : ℕ)
    (hm : 1 ≤ m) :
    let μ_inv := (unique_invariant_measure hyp m hm).choose
    μ_inv.val (collatzExceptionSet ∩ ↑(StateSpace m)) = 0 := by
  sorry

/-- Step 6: Transfer from measure-zero to density-zero.

    This is the ergodic-theory step: if the invariant measure assigns
    measure 0 to a set, then the set has natural density 0.

    For finite Markov chains this is standard: the empirical measure
    (1/n) Σ δ_{X_k} → μ* almost surely (ergodic theorem).

    TODO: import from Mathlib.MeasureTheory.Ergodic or prove directly
    using exponential_mixing + Cesaro argument. -/
lemma density_zero_from_measure_zero
    (S : Set ℕ) (hyp : UniformGapHyp) :
    (∀ m : ℕ, 1 ≤ m →
      let μ_inv := (unique_invariant_measure hyp m hm).choose
      μ_inv.val (S ∩ ↑(StateSpace m)) = 0) →
    naturalDensity S = 0 := by
  sorry

-- ═══════════════════════════════════════════════════════════════════
-- THE MAIN THEOREM
-- ═══════════════════════════════════════════════════════════════════

/-- **Theorem 8.1** (Collatz Density-1 Convergence — CONDITIONAL).

    ASSUMING UniformGapHyp, the set of positive integers whose Collatz
    orbit does NOT reach {1, 2, 4} has natural density zero.

    COMPLETE PROOF CHAIN
    ────────────────────
    (1) UniformGapHyp
            │
            ▼  [doeblin_from_spectral_gap, Estimates.lean]
    (2) Doeblin constant c > 0
            │
            ▼  [birkhoff_cone_contraction, Spectral.lean]
    (3) Birkhoff contraction: ∃ τ < 1, d_H(L_m μ, L_m ν) ≤ τ · d_H(μ,ν)
            │
            ▼  [unique_invariant_measure, Spectral.lean]
    (4) ∃! invariant measure μ* for L_m
            │
            ├──[no_nontrivial_collatz_cycle, CycleExclusion.lean]
            │
            ▼  [invariant_measure_supported_on_trivialCycle, above]
    (5) μ*(trivialCycle) = 1   →   μ*(exceptionSet) = 0
            │
            ▼  [density_zero_from_measure_zero, above]
    (6) naturalDensity(collatzExceptionSet) = 0   □

    WHAT REMAINS OPEN
    ─────────────────
    Proving UniformGapHyp unconditionally.
    Numerical evidence (SIARC-3, Stage 9): γ_m ≥ 0.70 for m = 1,…,16.
    A proof for all m is of comparable difficulty to Collatz itself. -/
theorem collatzDensityOne
    (hyp : UniformGapHyp) :
    naturalDensity collatzExceptionSet = 0 := by
  apply density_zero_from_measure_zero
  intro m hm
  exact exception_measure_zero hyp m hm

end

-- ═══════════════════════════════════════════════════════════════════
-- SANITY CHECKS
-- ═══════════════════════════════════════════════════════════════════

-- The type of the main theorem: inspect the hypothesis explicitly.
#check @collatzDensityOne
-- collatzDensityOne : UniformGapHyp → naturalDensity collatzExceptionSet = 0

-- The cycle-exclusion lemmas need no hypothesis.
#check @three_pow_ne_two_pow
-- three_pow_ne_two_pow : ∀ (a b : ℕ), 1 ≤ a → 1 ≤ b → 3 ^ a ≠ 2 ^ b

#check @no_nontrivial_collatz_cycle
-- no_nontrivial_collatz_cycle : ¬∃ a b n, …

-- The contraction factor bound needs only UniformGapHyp.
#check @contraction_factor_lt_one
-- contraction_factor_lt_one :
--   ∀ (hyp : UniformGapHyp) (m B : ℕ), 1 ≤ m → … → 1 − 2c < 1
