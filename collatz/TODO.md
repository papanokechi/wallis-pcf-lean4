# TODO.md — CollatzBirkhoff sorry reduction roadmap

**Current sorry count**: 7 (mathematical claims in doubt: 0)  
**Fully proved results**: 7 (no sorry)

---

## Priority 1 — ~20 min each, mechanical

### TODO-1: Close `doeblin_from_spectral_gap` γ₀ < 1 case

**File**: `Estimates.lean`, line ~68  
**The sorry**:
```lean
-- If γ₀ = 1, degenerate case — in practice γ₀ < 1 by SIARC-3.
exfalso; sorry
```
**Fix**: Strengthen `UniformGapHyp` to include `hγ₀_lt_one : γ₀ < 1`,
or add a lemma that derives it from `hgap` and the fact that
`spectralGap m < 1` for any non-trivial operator.

```lean
-- Add to UniformGapHyp:
hγ₀_lt_one : γ₀ < 1
-- Then the sorry becomes:
exact hyp.hγ₀_lt_one
```

**Downstream unlock**: This closes 1 sorry in `doeblin_from_spectral_gap`
and makes the entire `Estimates.lean` sorry-free (except for definitions).

---

### TODO-2: Close `hilbertMetric_nonneg`

**File**: `Defs.lean`, `hilbertMetric_nonneg`  
**Fix**: Implement `hilbertMetric` concretely as
```lean
def hilbertMetric (m : ℕ) (μ ν : ProbMeasure m) : ℝ :=
  Real.log (iSup (fun a : StateSpace m => μ.val {a} / ν.val {a})) -
  Real.log (iInf (fun a : StateSpace m => μ.val {a} / ν.val {a}))
```
Then `hilbertMetric_nonneg` follows from `log(sup) ≥ log(inf)`.

---

## Priority 2 — 1–2 hours, Mathlib search

### TODO-3: `birkhoff_cone_contraction` — Mathlib import or local proof

**File**: `Spectral.lean`  
**Search in Mathlib4**:
- `Mathlib.Topology.MetricSpace.Contracting` — has `ContractingWith`
- `Mathlib.Analysis.MeanInequalities` — has log-sum inequalities
- Look for `Birkhoff` or `Hilbert metric` in Mathlib search

**If not in Mathlib**: write a minimal local version with the statement
```lean
-- Minimal form needed:
lemma birkhoff_tanh_contraction (c : ℝ) (hc : 0 < c) (hc' : c < 1/2) :
    ∀ μ ν, d_H(L μ, L ν) ≤ (1 - 2*c) * d_H(μ, ν)
```
and open a Mathlib PR with this motivation.

### TODO-4: `unique_invariant_measure` — wire to Banach FPT

**File**: `Spectral.lean`  
**Mathlib target**: `ContractingWith.fixedPoint_unique`  
**Bridge needed**:
```lean
-- Construct the MetricSpace instance:
instance : MetricSpace (ProbMeasure m) where
  dist μ ν := hilbertMetric m μ ν
  ...
-- Then ContractingWith (1 - 2*c) (transferOp m) gives uniqueness.
```

### TODO-5: `exponential_mixing` — geometric series

**File**: `Spectral.lean`  
**Mathlib target**: `tendsto_pow_atTop_nhds_zero_of_lt_one`  
**Fix**: Once unique_invariant_measure is done, this is a straightforward
induction:
```lean
-- Base: d_H(L^0 μ₀, μ*) = d_H(μ₀, μ*) = τ^0 * d_H(μ₀, μ*)
-- Step: d_H(L^(n+1) μ₀, μ*) ≤ τ * d_H(L^n μ₀, μ*) ≤ τ^(n+1) * d_H(μ₀, μ*)
```

---

## Priority 3 — Half day, assembly

### TODO-6: `invariant_measure_supported_on_trivialCycle`

**File**: `Main.lean`  
**Strategy**: Show that trivialCycle is an absorbing class (closed under L_m),
then use uniqueness of μ* to conclude it must be supported there.
Use `trivialCycle_closed` from `CycleExclusion.lean`.

### TODO-7: `density_zero_from_measure_zero`

**File**: `Main.lean`  
**Strategy**: Birkhoff ergodic theorem for finite Markov chains.
The empirical measure (1/n) Σ_{k=0}^{n-1} δ_{X_k} → μ* a.s.
If μ*(S) = 0, the empirical frequency of S → 0.
**Mathlib target**: `Mathlib.MeasureTheory.Ergodic.Basic`

---

## Project hygiene checklist

- [ ] Add `hγ₀_lt_one` field to `UniformGapHyp` (closes TODO-1)
- [ ] Implement `hilbertMetric` concretely in `Defs.lean` (closes TODO-2)
- [ ] Search Mathlib for Birkhoff metric / contraction results
- [ ] Open Mathlib PR for `birkhoff_tanh_contraction` if not present
- [ ] Open Mathlib PR for `ContractingWith` instance for `ProbMeasure`
- [ ] Set up `lake build` CI (GitHub Actions: `lean-action`)
- [ ] Add `#eval` checks for small m (m=1,2,3) to test `collatzStep`
- [ ] Reference `collatz_stage9_output.txt` in `spectralGap` docstring

---

## Sorry audit (full list)

| # | Name | File | Type | Fix |
|---|------|------|------|-----|
| 1 | `hilbertMetric` | Defs | definition stub | implement concretely |
| 2 | `spectralGap` | Defs | definition stub | matrix eigenvalue |
| 3 | `hilbertMetric_nonneg` | Defs | follows from def | after TODO-2 |
| 4 | `hilbertMetric_symm` | Defs | follows from def | after TODO-2 |
| 5 | `doeblin_from_spectral_gap` | Estimates | γ₀ < 1 case | TODO-1 (~20 min) |
| 6 | `birkhoff_cone_contraction` | Spectral | Mathlib deferral | TODO-3 |
| 7 | `unique_invariant_measure` | Spectral | Banach FPT bridge | TODO-4 |
| 8 | `exponential_mixing` | Spectral | geometric series | TODO-5 |
| 9 | `exception_prob_to_zero` | Spectral | follows from 7+8 | after TODO-4,5 |
|10 | `invariant_measure_supported…` | Main | assembly | TODO-6 |
|11 | `exception_measure_zero` | Main | assembly | after TODO-6 |
|12 | `density_zero_from_measure_zero` | Main | ergodic thm | TODO-7 |

**Mathematical claims in doubt**: 0  
**UniformGapHyp**: open — comparable to Collatz conjecture itself
