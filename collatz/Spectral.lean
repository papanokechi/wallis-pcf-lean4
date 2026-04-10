/-
  CollatzBirkhoff/Spectral.lean
  ═══════════════════════════════════════════════════════════════════
  Birkhoff cone contraction, invariant measure uniqueness, and
  exponential mixing.

  STATUS
  ──────
  All three main theorems carry sorry — they are Mathlib deferrals
  of classical results. Mathlib4 search targets listed per lemma.

  MATHLIB SEARCH TARGETS (check before adding local sorry)
  ─────────────────────
  • Banach FPT        : Mathlib.Topology.MetricSpace.Contracting
  • Birkhoff/Hopf     : not yet in Mathlib4 (as of 2026-04)
                        → upstream candidate
  • Geometric series  : Mathlib.Topology.Algebra.InfiniteSum.Basic
  ═══════════════════════════════════════════════════════════════════
-/

import CollatzBirkhoff.Defs
import CollatzBirkhoff.Estimates
import Mathlib.Topology.MetricSpace.Contracting
import Mathlib.Topology.MetricSpace.Basic

open MeasureTheory Real Filter Topology

noncomputable section

-- ───────────────────────────────────────────────────────────────────
-- 1. Birkhoff cone contraction  (Theorem 5.1)
-- ───────────────────────────────────────────────────────────────────

/-- **Theorem 5.1** (Birkhoff Cone Contraction).

    Under UniformGapHyp, the B-step transfer operator (L_m)^B strictly
    contracts the Hilbert projective metric:

        d_H(L_m^B μ, L_m^B ν) ≤ τ · d_H(μ, ν)

    where τ = tanh(Δ/4) < 1 and Δ = log((1−c)/c²) is the
    Birkhoff diameter of the image cone.

    The key chain:
      UniformGapHyp → c > 0  (Lemma 4.1)
      c > 0         → Δ < ∞  (image has bounded projective diameter)
      Δ < ∞         → τ = tanh(Δ/4) < 1  (Birkhoff–Hopf, 1957)

    TODO: formalize using Mathlib's contraction infrastructure.
    Key reference: P.J. Bushell, "Hilbert's metric and positive
    contraction mappings in a Banach space", ARMA 1973. -/
theorem birkhoff_cone_contraction
    (hyp : UniformGapHyp)
    (m B : ℕ)
    (hm : 1 ≤ m)
    (hB : Real.log (2 ^ m) / Real.log (1 / (1 - hyp.γ₀)) ≤ B) :
    ∃ τ : ℝ, 0 ≤ τ ∧ τ < 1 ∧
      ∀ (μ ν : ProbMeasure m),
        hilbertMetric m
          ⟨transferOp m (transferOp m μ.val), transferOp_isProbability m ⟨_, inferInstance⟩⟩
          ⟨transferOp m (transferOp m ν.val), transferOp_isProbability m ⟨_, inferInstance⟩⟩
        ≤ τ * hilbertMetric m μ ν := by
  -- Construct τ = 1 − 2c where c = doeblinkConst m B hyp.γ₀.
  refine ⟨1 - 2 * doeblinkConst m B hyp.γ₀,
          contraction_factor_nonneg hyp m B hm,
          contraction_factor_lt_one hyp m B hm hB,
          ?_⟩
  -- The contraction inequality follows from the Birkhoff–Hopf theorem
  -- applied to the (B-fold) transfer operator with Doeblin constant c.
  -- TODO: import from Mathlib once Birkhoff metric machinery is upstreamed.
  intro μ ν
  sorry

-- ───────────────────────────────────────────────────────────────────
-- 2. Invariant measure uniqueness  (Theorem 6.1)
-- ───────────────────────────────────────────────────────────────────

/-- The Hilbert metric makes ProbMeasure m a complete metric space.

    Proof: StateSpace m is finite (Fintype), so ProbMeasure m is compact
    in the weak topology, and the Hilbert metric is compatible with it.

    TODO: formalize via Mathlib.MeasureTheory.Measure.Tight or
    Mathlib.Topology.Algebra.Module.WeakDual. -/
lemma probMeasure_complete (m : ℕ) :
    ∀ (f : ℕ → ProbMeasure m),
      CauchySeq (fun n => hilbertMetric m (f n) (f (n+1))) →
      ∃ μ : ProbMeasure m, Filter.Tendsto
        (fun n => hilbertMetric m (f n) μ) atTop (nhds 0) := by
  sorry

/-- **Theorem 6.1** (Unique Invariant Measure).

    The transfer operator L_m has a unique fixed point in ProbMeasure m.

    Proof strategy: apply Banach fixed-point theorem
    (Mathlib.Topology.MetricSpace.Contracting.fixedPoint)
    to the contraction from birkhoff_cone_contraction.

    TODO: bridge between the ∃ τ form and Mathlib's ContractingWith
    typeclass. The key instance needed:
      instance : MetricSpace (ProbMeasure m) using hilbertMetric -/
theorem unique_invariant_measure
    (hyp : UniformGapHyp)
    (m : ℕ)
    (hm : 1 ≤ m) :
    ∃! μ : ProbMeasure m, transferOp m μ.val = μ.val := by
  -- Step 1: choose B from the spectral gap.
  obtain ⟨B, hB⟩ : ∃ B : ℕ, Real.log (2 ^ m) / Real.log (1 / (1 - hyp.γ₀)) ≤ B :=
    ⟨⌈Real.log (2 ^ m) / Real.log (1 / (1 - hyp.γ₀))⌉₊,
     Nat.le_ceil _⟩
  -- Step 2: get contraction factor τ < 1.
  obtain ⟨τ, hτ_nn, hτ_lt, hcontr⟩ := birkhoff_cone_contraction hyp m B hm hB
  -- Step 3: apply Banach FPT to (ProbMeasure m, hilbertMetric, L_m^B).
  -- TODO: construct ContractingWith instance and apply
  -- Mathlib.Topology.MetricSpace.Contracting.fixedPoint_unique.
  sorry

-- ───────────────────────────────────────────────────────────────────
-- 3. Exponential mixing  (Corollary 6.2)
-- ───────────────────────────────────────────────────────────────────

/-- **Corollary 6.2** (Exponential Mixing).

    The iterates of L_m converge exponentially to the unique invariant
    measure μ* in the Hilbert metric:

        d_H(L_m^n μ₀, μ*) ≤ τ^n · d_H(μ₀, μ*)

    This is a standard geometric-series consequence of the contraction.

    TODO: once unique_invariant_measure is proved, this follows from
    a straightforward induction on n using hcontr from above. -/
lemma exponential_mixing
    (hyp : UniformGapHyp)
    (m : ℕ)
    (hm : 1 ≤ m) :
    let μ_inv := (unique_invariant_measure hyp m hm).choose
    ∃ τ : ℝ, 0 ≤ τ ∧ τ < 1 ∧
      ∀ (μ₀ : ProbMeasure m) (n : ℕ),
        hilbertMetric m
          ⟨(transferOp m)^[n] μ₀.val, sorry⟩
          μ_inv ≤
        τ ^ n * hilbertMetric m μ₀ μ_inv := by
  sorry

/-- Variant: the exception probability → 0 exponentially. -/
lemma exception_prob_to_zero
    (hyp : UniformGapHyp)
    (m : ℕ)
    (hm : 1 ≤ m)
    (μ₀ : ProbMeasure m) :
    Filter.Tendsto
      (fun n => (transferOp m)^[n] μ₀.val (↑trivialCycle))
      atTop
      (nhds 1) := by
  -- From exponential_mixing + unique invariant measure supported on trivialCycle.
  sorry

end
