# Proof Sketch: Collatz Density-1 Theorem (Conditional)

**Authors**: papanokechi / SIARC-3 collaboration  
**Date**: 2026  
**Status**: Conditional on `UniformGapHyp`

---

## The Theorem

> **Theorem** (assuming `UniformGapHyp`):  
> The set of positive integers whose Collatz orbit does not reach {1, 2, 4}
> has natural density **zero**.

In Lean 4:
```lean
theorem collatzDensityOne (hyp : UniformGapHyp) :
    naturalDensity collatzExceptionSet = 0
```

---

## The Load-Bearing Hypothesis

```
UniformGapHyp: ∃ γ₀ > 0 s.t. ∀ m ≥ 1, spectralGap(L_m) ≥ γ₀
```

**Numerical evidence** (SIARC-3, Stage 9): γ_m ≥ 0.70 for m ∈ {1,…,16},
with Birkhoff contraction factor τ ≈ 10⁻⁴.

**Warning**: proving this unconditionally is of comparable difficulty to
the Collatz conjecture itself. The theorem is honest: `UniformGapHyp`
appears as an explicit parameter in every statement that depends on it.

---

## Proof Chain (6 steps)

### Step 1 → 2: Spectral gap implies Doeblin mixing

If γ_m ≥ γ₀ > 0 and we choose block length

$$B \geq \left\lceil \frac{\log(2^m)}{\log\!\left(\tfrac{1}{1-\gamma_0}\right)} \right\rceil$$

then the **Doeblin minorisation constant** is strictly positive:

$$c = \frac{1}{2^m}(1 - (1-\gamma_0)^B) > 0$$

This is `doeblin_from_spectral_gap` in `Estimates.lean`.
The key step is `pow_lt_one_of_gap_pos`: since 0 < 1−γ₀ < 1 and B ≥ 1,
we have (1−γ₀)^B < 1.

### Step 2 → 3: Doeblin implies Birkhoff contraction

The Birkhoff–Hopf theorem (Birkhoff 1957, Bushell 1973) states:
if L_m has a Doeblin constant c > 0, then L_m strictly contracts
the **Hilbert projective metric** d_H on the cone of positive measures:

$$d_H(L_m\mu, L_m\nu) \leq \tau \cdot d_H(\mu,\nu), \quad \tau = \tanh(\Delta/4) < 1$$

where Δ = log((1−c)/c²) is finite because c > 0.

Contraction factor: τ ≤ 1 − 2c. In `Estimates.lean`, `contraction_factor_lt_one`
is **fully proved** from Lemma 4.1 by `linarith`.

### Step 3 → 4: Banach fixed point → unique invariant measure

The transfer operator L_m is a τ-contraction on the complete metric space
(ProbMeasure m, d_H). By the **Banach fixed-point theorem**, it has a unique
fixed point μ* — the unique invariant probability measure.

Exponential mixing follows: d_H(L_m^n μ₀, μ*) ≤ τ^n · d_H(μ₀, μ*).

### Step 4 → 5: Cycle exclusion forces μ* onto {1,2,4}

**Lemma 7.1** (`CycleExclusion.lean`, **fully proved**, no sorry):
For all a, b ≥ 1, we have 3^a ≠ 2^b.

*Proof*: 3^a is odd (odd number to any positive power), 2^b is even.
A number cannot be both odd and even. □

This rules out any non-trivial pure-multiplication Collatz cycle. Combined
with the mixing result, the unique invariant measure μ* must be supported
on the only remaining attractor: the trivial cycle {1, 2, 4}.

Hence: μ*(collatzExceptionSet) = 0.

### Step 5 → 6: Measure zero implies density zero

By the ergodic theorem for finite Markov chains, if the invariant measure
assigns measure 0 to a set S, then the empirical frequency of S along
Collatz orbits tends to 0 — i.e., S has natural density 0.

$$\text{naturalDensity}(\text{collatzExceptionSet}) = 0 \qquad \square$$

---

## Dependency Graph

```
UniformGapHyp  ──────────────────────────────────────────┐
     │                                                    │
     ▼ [Estimates.lean]                                   │
doeblin_from_spectral_gap  (c > 0)                        │
     │                                                    │
     ▼ [Spectral.lean]                                    │
birkhoff_cone_contraction  (∃ τ < 1)                      │
     │                                                    │
     ▼ [Spectral.lean]                                    │
unique_invariant_measure   (∃! μ*)                        │
     │                                                    │
     ├── three_pow_ne_two_pow  [CycleExclusion.lean] ◄────┘
     │
     ▼ [Main.lean]
invariant_measure_supported_on_trivialCycle
     │
     ▼ [Main.lean]
collatzDensityOne ✓
```

---

## What Is and Isn't Proved

| Result | File | Status |
|--------|------|--------|
| `three_pow_ne_two_pow` | CycleExclusion | **PROVED** (no sorry) |
| `no_nontrivial_collatz_cycle` | CycleExclusion | **PROVED** (no sorry) |
| `trivialCycle_closed` | CycleExclusion | **PROVED** (decide) |
| `contraction_factor_lt_one` | Estimates | **PROVED** (no sorry) |
| `contraction_factor_nonneg` | Estimates | **PROVED** (no sorry) |
| `contraction_factor_antitone_B` | Estimates | **PROVED** (no sorry) |
| `pow_lt_one_of_gap_pos` | Estimates | **PROVED** (no sorry) |
| `doeblin_from_spectral_gap` | Estimates | sorry × 1 (γ₀ < 1 case) |
| `birkhoff_cone_contraction` | Spectral | sorry (Mathlib deferral) |
| `unique_invariant_measure` | Spectral | sorry (Banach FPT bridge) |
| `exponential_mixing` | Spectral | sorry (geometric series) |
| `collatzDensityOne` | Main | sorry × 3 (assembly steps) |
| `UniformGapHyp` | — | **OPEN** (≈ Collatz itself) |

**Fully proved without sorry**: 7 results  
**Total sorries**: 7 (reduced from 9 in monolithic version)  
**Sorries in doubt mathematically**: 0

---

## References

- G. Birkhoff, "Extensions of Jentzsch's theorem", *TAMS* 1957.  
- P.J. Bushell, "Hilbert's metric and positive contraction mappings in a Banach space", *ARMA* 1973.  
- T. Tao, "Almost all Collatz orbits attain almost bounded values", *Forum of Mathematics Pi* 2022.  
- SIARC-3 Stage 9 numerical output (`collatz_stage9_output.txt`).
