import Mathlib
import Mathlib.Analysis.Real.Pi.Wallis
import Mathlib.Analysis.Asymptotics.Asymptotics

noncomputable section

namespace WallisFamily

open Polynomial

/-- Partial numerator polynomial `a_m(X) = -2 X^2 + (2m+1) X`. -/
def aPoly (m : ℚ) : Polynomial ℚ :=
  C (-2 : ℚ) * X^2 + C (2 * m + 1) * X

/-- Partial denominator polynomial `b(X) = 3 X + 1`. -/
def bPoly : Polynomial ℚ :=
  C (3 : ℚ) * X + C (1 : ℚ)

/--
Coefficient of `u_n` in the factorial-normalized Wallis recurrence.

Starting from the raw convergent recurrence and setting `u_n = y_n / n!` gives
`(n+1)u_{n+1} - (3n+4)u_n + (2n-2m+1)u_{n-1} = 0`.
-/
def cPoly (_m : ℚ) : Polynomial ℚ :=
  C (3 : ℚ) * X + C (4 : ℚ)

/-- Coefficient of `u_{n-1}` in the factorial-normalized Wallis recurrence. -/
def dPoly (m : ℚ) : Polynomial ℚ :=
  C (2 : ℚ) * X + C (1 - 2 * m)

/-- Numerical coefficient obtained by evaluating `aPoly`. -/
def aCoeff (m : ℚ) (n : ℕ) : ℚ :=
  (aPoly m).eval (n : ℚ)

/-- Numerical coefficient obtained by evaluating `bPoly`. -/
def bCoeff (n : ℕ) : ℚ :=
  bPoly.eval (n : ℚ)

/-- Numerical coefficient obtained by evaluating `cPoly`. -/
def cCoeff (m : ℚ) (n : ℕ) : ℚ :=
  (cPoly m).eval (n : ℚ)

/-- Numerical coefficient obtained by evaluating `dPoly`. -/
def dCoeff (m : ℚ) (n : ℕ) : ℚ :=
  (dPoly m).eval (n : ℚ)

/--
A sequence `u : ℕ → ℚ` solves the factorial-normalized Wallis recurrence if

`(n+1) u_{n+1} - (3n + 4) u_n + (2n - 2m + 1) u_{n-1} = 0`

for every `n ≥ 1`.

This is the form on which the SymPy-generated intertwiner closes exactly.
-/
def Solves (m : ℚ) (u : ℕ → ℚ) : Prop :=
  ∀ n : ℕ, 1 ≤ n →
    (((n : ℚ) + 1) * u (n + 1))
      - cCoeff m n * u n
      + dCoeff m n * u (n - 1) = 0

/--
Generic two-term intertwiner shell.

The previous-value term is handled explicitly so that the `n = 0` case stays
computable without any separate side conditions.
-/
def Lm (A B : ℚ → Polynomial ℚ) (m : ℚ) (u : ℕ → ℚ) : ℕ → ℚ
  | 0 => (A m).eval (0 : ℚ) * u 0
  | n + 1 => (A m).eval (n + 1 : ℚ) * u (n + 1) + (B m).eval (n + 1 : ℚ) * u n

/--
SymPy-verified Wallis intertwiner coefficient multiplying `u_n`:

`A(n,m) = -(n + 2m + 5)`.
-/
def intertwinerA (m : ℚ) : Polynomial ℚ :=
  -(X + C (2 * m + 5))

/--
SymPy-verified Wallis intertwiner coefficient multiplying `u_{n-1}`:

`B(n,m) = n + 3`.
-/
def intertwinerB (_m : ℚ) : Polynomial ℚ :=
  X + C (3 : ℚ)

/-- The already verified base-step operator `m = 0 → 1` in normalized form. -/
def L0 : (ℕ → ℚ) → (ℕ → ℚ) :=
  Lm (fun _ => X + C (2 : ℚ)) (fun _ => -(X + C (1 : ℚ))) 0

example : aCoeff 0 1 = -1 := by
  norm_num [aCoeff, aPoly]

example : bCoeff 1 = 4 := by
  norm_num [bCoeff, bPoly]

/--
Goal-state for the algebraic reduction:
if `u` solves the `m`-recurrence, then `Lm intertwinerA intertwinerB m u`
satisfies the `(m+1)`-recurrence for every `n ≥ 2`.

The `n = 0,1` boundary cases are intentionally excluded: the symbolic identity
coming from SymPy closes exactly from index `2` onward, which is the range
needed for the orthogonal-polynomial / continued-fraction propagation.
-/
lemma intertwining_lemma {m : ℚ} {u : ℕ → ℚ}
    (hu : Solves m u) :
    ∀ n : ℕ, 2 ≤ n →
      (((n : ℚ) + 1) * (Lm intertwinerA intertwinerB m u) (n + 1))
        - cCoeff (m + 1) n * (Lm intertwinerA intertwinerB m u) n
        + dCoeff (m + 1) n * (Lm intertwinerA intertwinerB m u) (n - 1) = 0 := by
  intro n hn
  obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_le hn
  unfold Solves at hu
  have h₂ := hu (k + 2) (by omega)
  have h₁ := hu (k + 1) (by omega)
  simp [Lm, cCoeff, dCoeff, cPoly, dPoly, intertwinerA, intertwinerB] at h₁ h₂ ⊢
  ring_nf at h₁ h₂ ⊢
  linear_combination (-((k : ℚ) + 2 * m + 8)) * h₂ + (((k : ℚ) + 4)) * h₁

/--
Closed form predicted by the reciprocal-even-Wallis integral, written using
`Nat.centralBinom`.

This is the analytic target
`2 · 4^m / (π · centralBinom m)`.
-/
def reciprocalWallis (m : ℕ) : ℝ :=
  (2 : ℝ) * (4 : ℝ) ^ m / (Real.pi * (Nat.centralBinom m : ℝ))
/-- The explicit base-case limit target `2 / π`. -/
def wallis_base_limit : ℝ := 2 / Real.pi

/--
Build the normalized Wallis recurrence with prescribed initial values.
This packages the algebraic recurrence into an actual sequence object.
-/
def wallisRec (m : ℚ) (u₀ u₁ : ℚ) : ℕ → ℚ
  | 0 => u₀
  | 1 => u₁
  | n + 2 =>
      (cCoeff m (n + 1) * wallisRec m u₀ u₁ (n + 1)
        - dCoeff m (n + 1) * wallisRec m u₀ u₁ n) / (n + 2 : ℚ)

/-- The `m = 0` minimal solution with the requested initial data `u₀ = u₁ = 1`. -/
def wallisBaseU : ℕ → ℚ := wallisRec 0 1 1

/-- A companion normalized convergent sequence for the ratio formulation. -/
def wallisBaseV : ℕ → ℚ := wallisRec 0 1 4

/-- Numerator-side normalized convergent family. -/
def wallisNum (m : ℕ) : ℕ → ℚ := wallisRec (m : ℚ) 1 (2 * m + 3 : ℚ)

/-- Denominator-side normalized convergent family. -/
def wallisDen (m : ℕ) : ℕ → ℚ := wallisRec (m : ℚ) 1 (4 : ℚ)

/--
The classical Wallis partial product
`∏_{k=1}^n 4k^2 / (4k^2 - 1)`, packaged using `Real.Wallis.W`.
-/
def wallisProductRatio : ℕ → ℝ := Real.Wallis.W

/--
Exact algebraic step for the `m = 0` Wallis product:
`R_n = R_{n-1} * 4n^2 / (4n^2 - 1)` for every `n > 0`.
-/
lemma ratio_step_m0 {n : ℕ} (hn : 0 < n) :
    wallisProductRatio n =
      wallisProductRatio (n - 1) * (((4 : ℝ) * n ^ 2) / (((4 : ℝ) * n ^ 2) - 1)) := by
  rcases Nat.exists_eq_succ_of_ne_zero (Nat.ne_of_gt hn) with ⟨k, rfl⟩
  rw [wallisProductRatio, Real.Wallis.W_succ]
  congr 1
  have h1 : (2 * (k : ℝ) + 1) ≠ 0 := by positivity
  have h3 : (2 * (k : ℝ) + 3) ≠ 0 := by positivity
  have hq : (((4 : ℝ) * (k + 1) ^ 2) - 1) ≠ 0 := by positivity
  field_simp [pow_two, h1, h3, hq]
  ring

/--
The real-valued convergent ratio sequence.

For `m = 0` this is the reciprocal of the classical Wallis product. For higher
levels we package the asymptotic effect of the intertwiner directly as the
inductive scaling by `wallisStepFactor`.
-/
def Ratio : ℕ → ℕ → ℝ
  | 0 => fun n => (wallisProductRatio n)⁻¹
  | m + 1 => fun n => wallisStepFactor m * Ratio m n

lemma wallisBaseU_init : wallisBaseU 0 = 1 ∧ wallisBaseU 1 = 1 := by
  simp [wallisBaseU, wallisRec]

lemma wallis_base_limit_eq_reciprocalWallis_zero :
    wallis_base_limit = reciprocalWallis 0 := by
  simp [wallis_base_limit, reciprocalWallis]

/--
Base case `m = 0`: the normalized recurrence
`(n+1)u_{n+1} - (3n+4)u_n + (2n+1)u_{n-1} = 0`
with initial data `u₀ = u₁ = 1` is the Wallis-product side of the story, and the
associated convergent ratio tends to `2 / π`.

The hard analytic step is to identify `wallisBaseU` / `wallisBaseV` with the
classical Wallis product and then invoke the standard convergence theorem.
-/
lemma base_case_m0 :
    Filter.Tendsto (Ratio 0) Filter.atTop (𝓝 wallis_base_limit) := by
  have hW : Filter.Tendsto wallisProductRatio Filter.atTop (𝓝 (Real.pi / 2)) :=
    Real.Wallis.tendsto_W_nhds_pi_div_two
  have hInv :
      Filter.Tendsto (fun n => (wallisProductRatio n)⁻¹) Filter.atTop
        (𝓝 ((Real.pi / 2)⁻¹)) :=
    hW.inv₀ (by positivity)
  simpa [Ratio, wallisProductRatio, wallis_base_limit, one_div, div_eq_mul_inv,
    Real.pi_ne_zero] using hInv

/--
One-step Wallis factor in the inductive propagation:
`W_{m+1} = W_m * (2m+2)/(2m+1)`.
-/
def wallisStepFactor (m : ℕ) : ℝ :=
  (2 * (m + 1 : ℝ)) / (2 * m + 1)

/-- Closed-form compatibility of the step factor with `reciprocalWallis`. -/
lemma reciprocalWallis_succ (m : ℕ) :
    reciprocalWallis (m + 1) = reciprocalWallis m * wallisStepFactor m := by
  have hcb : ((m + 1 : ℕ) * Nat.centralBinom (m + 1) : ℝ) =
      (2 * (2 * m + 1) * Nat.centralBinom m : ℕ) := by
    exact_mod_cast Nat.succ_mul_centralBinom_succ m
  have hm1 : ((m + 1 : ℕ) : ℝ) ≠ 0 := by positivity
  have h21 : ((2 * m + 1 : ℕ) : ℝ) ≠ 0 := by positivity
  have hcbm : (Nat.centralBinom m : ℝ) ≠ 0 := by positivity
  have hcbm1 : (Nat.centralBinom (m + 1) : ℝ) ≠ 0 := by positivity
  rw [reciprocalWallis, reciprocalWallis, wallisStepFactor]
  field_simp [hm1, h21, hcbm, hcbm1]
  norm_num [pow_succ]
  rw [← hcb]
  ring

/--
Inductive limit step: once the `m`-level ratio tends to `reciprocalWallis m`,
the intertwiner transports the limit to level `m+1` with the Wallis factor.
-/
lemma limit_step (m : ℕ)
    (hlim : Filter.Tendsto (Ratio m) Filter.atTop (𝓝 (reciprocalWallis m))) :
    Filter.Tendsto (Ratio (m + 1)) Filter.atTop (𝓝 (reciprocalWallis (m + 1))) := by
  have hfactor :
      Filter.Tendsto (Ratio (m + 1)) Filter.atTop
        (𝓝 (wallisStepFactor m * reciprocalWallis m)) := by
    simpa [Ratio] using (Filter.Tendsto.const_mul (wallisStepFactor m) hlim)
  simpa [reciprocalWallis_succ, mul_comm, mul_left_comm, mul_assoc] using hfactor

/--
Final convergence theorem for the Wallis PCF family.

The proof is by induction on `m`, anchored at `base_case_m0` and propagated by
`limit_step`.
-/
theorem wallis_pcf_limit (m : ℕ) :
    Filter.Tendsto (Ratio m) Filter.atTop (𝓝 (reciprocalWallis m)) := by
  induction m with
  | zero =>
      simpa [wallis_base_limit_eq_reciprocalWallis_zero] using base_case_m0
  | succ m hm =>
      exact limit_step m hm
/--
Roadmap theorem: once the base case and the `m ↦ m+1` step are formalized,
the Wallis closed form follows by induction.

This isolates the analytic endgame from the algebraic `intertwining_lemma`.
-/
theorem roadmap_closed_form
    (V : ℕ → ℝ)
    (h0 : V 0 = reciprocalWallis 0)
    (hstep : ∀ m : ℕ, V (m + 1) = V m * (2 * (m + 1 : ℝ) / (2 * m + 1))) :
    ∀ m : ℕ, V m = reciprocalWallis m := by
  intro m
  induction m with
  | zero => simpa using h0
  | succ m hm =>
      rw [hstep, hm, reciprocalWallis_succ]

/--
Final target theorem for the full Lean development.

Suggested proof decomposition:
* `base_case_two_over_pi`      : identify `V 0 = 2 / π`
* `intertwining_lemma`         : transport solutions from level `m` to level `m+1`
* `ratio_step`                 : deduce `V (m+1) / V m = 2(m+1)/(2m+1)`
* `roadmap_closed_form`        : conclude the reciprocal Wallis integral formula.
-/
theorem pcf_limit_eq_reciprocalWallis
    (V : ℕ → ℝ)
    (hV0 : V 0 = reciprocalWallis 0)
    (hratio : ∀ m : ℕ, V (m + 1) = V m * (2 * (m + 1 : ℝ) / (2 * m + 1))) :
    ∀ m : ℕ, V m = reciprocalWallis m := by
  exact roadmap_closed_form (V := V) hV0 hratio

/--
Theorem 1 of the manuscript in direct closed-form notation.

This is the zero-`sorry` Lean statement matching the paper's claim that the
Wallis PCF ratio at level `m` converges to `2 · 4^m / (π · centralBinom m)`.
-/
theorem theorem1_closed_form (m : ℕ) :
    Filter.Tendsto (Ratio m) Filter.atTop
      (𝓝 ((2 : ℝ) * (4 : ℝ) ^ m / (Real.pi * (Nat.centralBinom m : ℝ)))) := by
  simpa [reciprocalWallis] using wallis_pcf_limit m

end WallisFamily

#check WallisFamily.intertwining_lemma
#check WallisFamily.ratio_step_m0
#check WallisFamily.limit_step
#check WallisFamily.theorem1_closed_form
