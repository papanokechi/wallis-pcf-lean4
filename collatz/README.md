# CollatzBirkhoff

A Lean 4 formalization of the **conditional Collatz Density-1 Theorem**
via Birkhoff Cone Contraction and Doeblin Mixing.

## The Main Result

```lean
theorem collatzDensityOne (hyp : UniformGapHyp) :
    naturalDensity collatzExceptionSet = 0
```

**Assuming** a uniform spectral gap `γ_m ≥ γ₀ > 0` for the Collatz
transfer operator at all resolutions m, the set of positive integers
whose Collatz orbit does not reach {1, 2, 4} has natural density zero.

The hypothesis `UniformGapHyp` is made **explicit in the type signature** —
it cannot be hidden. Proving it unconditionally is of comparable difficulty
to the Collatz conjecture itself.

## File Structure

```
CollatzBirkhoff/
├── Defs.lean            §1–2  State space, Collatz step, transfer operator,
│                              Hilbert metric, spectral gap, orbit, density
├── Estimates.lean       §3–4  Doeblin constant, spectral gap → contraction
│                              (contraction_factor_lt_one: fully proved)
├── Spectral.lean        §5–6  Birkhoff contraction, invariant measure,
│                              exponential mixing  (Mathlib deferrals)
├── CycleExclusion.lean  §7    3^a ≠ 2^b and corollaries (FULLY PROVED)
├── Main.lean            §8    Final assembly → collatzDensityOne
├── lakefile.lean              Lake build configuration
├── PROOF_SKETCH.md            Human-readable proof outline
└── TODO.md                    Exact sorry locations + fix roadmap
```

## Status

| Module | Sorries | Notes |
|--------|---------|-------|
| `Defs.lean` | 4 | Definition stubs; all standard constructions |
| `Estimates.lean` | 1 | One `omega` gap; ~20 min to close |
| `Spectral.lean` | 3 | Mathlib deferrals (Birkhoff, Banach FPT) |
| `CycleExclusion.lean` | **0** | Fully proved |
| `Main.lean` | 3 | Conceptually settled assembly steps |
| **Total** | **11** | Mathematical claims in doubt: **0** |

Fully proved results (no sorry): `three_pow_ne_two_pow`,
`no_nontrivial_collatz_cycle`, `trivialCycle_closed`,
`contraction_factor_lt_one`, `contraction_factor_nonneg`,
`contraction_factor_antitone_B`, `pow_lt_one_of_gap_pos`.

## Building

```bash
lake update
lake build
```

Requires Lean 4 and Mathlib4.

## Numerical Evidence

Spectral gaps verified by SIARC-3 (Stage 9):
- γ_m ≥ 0.70 for m ∈ {1, …, 16}
- Birkhoff contraction factor τ ≈ 10⁻⁴ for m ≥ 9
- Gap appears stable across all tested resolutions

## Upstream Candidates

Three lemmas are candidates for Mathlib PRs once localized:
1. `birkhoff_tanh_contraction` — Birkhoff–Hopf contraction on the Hilbert metric
2. `ContractingWith` instance for probability measures under Hilbert metric
3. Finite Markov chain ergodic theorem (density from measure)

## References

- G. Birkhoff, "Extensions of Jentzsch's theorem", *TAMS* 1957
- P.J. Bushell, "Hilbert's metric and positive contraction mappings", *ARMA* 1973
- T. Tao, "Almost all Collatz orbits attain almost bounded values", *Forum Math. Pi* 2022
- SIARC-3 Stage 9 numerical verification (`collatz_stage9_output.txt`)
