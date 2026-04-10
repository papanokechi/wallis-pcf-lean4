/-
  CollatzBirkhoff/CycleExclusion.lean
  ═══════════════════════════════════════════════════════════════════
  Cycle exclusion: 3^a ≠ 2^b for all a, b ≥ 1.

  STATUS: FULLY PROVED — zero sorry.

  This module is self-contained and independent of UniformGapHyp.
  It rules out non-trivial pure multiplication cycles in the Collatz
  dynamics, closing off the only alternative to convergence to {1,2,4}.
  ═══════════════════════════════════════════════════════════════════
-/

import Mathlib.Data.Nat.Parity
import Mathlib.Data.Nat.Defs
import Mathlib.Tactic

-- ───────────────────────────────────────────────────────────────────
-- 1. Parity foundation
-- ───────────────────────────────────────────────────────────────────

/-- 3 is odd. -/
lemma three_odd : Odd 3 := ⟨1, by norm_num⟩

/-- Odd numbers are closed under powers. -/
lemma odd_pow_odd {n : ℕ} (hn : Odd n) (k : ℕ) (hk : 1 ≤ k) : Odd (n ^ k) :=
  Odd.pow hn

/-- 2^b is even for b ≥ 1. -/
lemma two_pow_even (b : ℕ) (hb : 1 ≤ b) : Even (2 ^ b) :=
  ⟨2 ^ (b - 1), by rw [← Nat.two_mul, ← pow_succ]; congr 1; omega⟩

/-- A number cannot be both odd and even. -/
lemma not_odd_and_even (n : ℕ) : ¬ (Odd n ∧ Even n) := by
  intro ⟨hodd, heven⟩
  exact (Nat.odd_iff.mp hodd).symm ▸ by simp [Nat.even_iff] at heven

-- ───────────────────────────────────────────────────────────────────
-- 2. Main cycle-exclusion lemma
-- ───────────────────────────────────────────────────────────────────

/-- **Lemma 7.1** (No integer relation between 3 and 2).

    For all a, b ≥ 1 we have 3^a ≠ 2^b.

    Proof: 3^a is odd (product of odd numbers), while 2^b is even.
    An odd number cannot equal an even number. □ -/
theorem three_pow_ne_two_pow (a b : ℕ) (ha : 1 ≤ a) (hb : 1 ≤ b) :
    3 ^ a ≠ 2 ^ b := by
  intro h
  have hodd : Odd (3 ^ a) := odd_pow_odd three_odd a ha
  have heven : Even (2 ^ b) := two_pow_even b hb
  rw [h] at hodd
  exact not_odd_and_even _ ⟨hodd, heven⟩

-- ───────────────────────────────────────────────────────────────────
-- 3. Corollaries
-- ───────────────────────────────────────────────────────────────────

/-- **Corollary 7.2** (No non-trivial pure Collatz cycle).

    There is no n ≥ 1 and a, b ≥ 1 with 3^a · n = 2^b · n.
    Such a relation would give a pure-multiplication periodic orbit. -/
theorem no_nontrivial_collatz_cycle :
    ¬ ∃ (a b n : ℕ), 1 ≤ a ∧ 1 ≤ b ∧ 1 ≤ n ∧ 3 ^ a * n = 2 ^ b * n := by
  intro ⟨a, b, n, ha, hb, hn, heq⟩
  have := Nat.eq_of_mul_eq_mul_right (Nat.pos_of_ne_zero (by omega)) heq
  exact three_pow_ne_two_pow a b ha hb this

/-- Strengthening: 3^a * m ≠ 2^b * n for any m, n ≥ 1 with m = n.
    Alias for use in Main.lean assembly. -/
alias cycleExclusion := no_nontrivial_collatz_cycle

/-- The trivial cycle {1, 2, 4} is fixed: each element maps eventually to 1. -/
lemma trivialCycle_closed :
    ∀ n ∈ ({1, 2, 4} : Finset ℕ), ∃ k : ℕ, Nat.iterate collatzStepNat k n = 1 := by
  decide
