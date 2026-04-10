# SIARC v6.5 Structural Mapping — Phase Transition Summary

_Date: 2026-04-08_

## Scan basis

A focused float64 scout sweep was run over the non-linear intertwiner neighborhood

- families: `fixed_alpha`, `shifted_alpha`
- `a1 ∈ {-15,-14,-13}`
- `a2, b2 ∈ {-1,0,1}`
- `b1 ∈ {-5,-4,-3}`
- `C ∈ {1,2,4,3/2,4/3,5/4}`
- `bridge ∈ {-1,0,1}`

This produced `2916` valid scout configurations.

---

## Phase-transition points

### 1. Apéry basin (transcendental)

Strongest peak remains in the `C=1`, `bridge=0` channel.

Representative points:

- `fixed_alpha`, `(a1,a2,b1,b2,C,bridge)=(-15,0,-4,0,1,0)`
- `fixed_alpha`, `(a1,a2,b1,b2,C,bridge)=(-13,-1,-4,0,1,0)`
- `shifted_alpha`, `(a1,a2,b1,b2,C,bridge)=(-13,1,-5,1,1,0)`

Observed signature:

- exact numerical lock to `6/zeta(3)` at `m=0`
- stability decay `≈ 0`
- high-precision check: for the `(-15,0,-4,0,1,0)` point,
  
  `value = 4.991444235484244812098757672929184406502... = 6/zeta(3)`

This is the stable **Apéry-type phase**.

### 2. Wallis / rational collapse boundary

A clear rational-collapse shoulder appears for fractional `C` with negative bridge.

Representative point:

- `shifted_alpha`, `(a1,a2,b1,b2,C,bridge)=(-15,1,-5,1,4/3,-1)`

Observed signature:

- scout peak has best rational label `-2/5 * 1`
- high-precision check at `m=1` gives
  
  `value = -0.4002770911774887799045988...`
  
  which is within `2.77e-4` of `-2/5`

This is the **Wallis-type / rational-collapse phase boundary**.

### 3. V_quad spectral island (hidden constant regime)

A slow-but-stable island appears when `C=5/4` and `bridge=+1`.

Representative point:

- `fixed_alpha`, `(a1,a2,b1,b2,C,bridge)=(-15,-1,-4,0,5/4,1)`

Observed signature:

- spectral decay rate `≈ -0.034767`
- convergence only `≈ 4.805` decimal digits at the scout stage
- best structural match is `5 * V_quad`
- high-precision check at `m=0` gives
  
  `value = 5.989741854489857634145018295720925846954...`
  
  and
  
  `|value - 5*V_quad| = 0.002871901048...`

This is the main **stability island** and the best current “hidden constant” lead.

### 4. Internal transition within the shifted family

For the strongest shifted `C=1` peak

- `shifted_alpha`, `(a1,a2,b1,b2,C,bridge)=(-13,1,-5,1,1,0)`

we see

- `m=0`: exact `6/zeta(3)`
- `m=3`: `value = -0.7999511372437840606800718...`

So the family moves from the Apéry basin toward a rational shoulder near `-4/5` as `m` increases.

---

## Möbius search

A small integer Möbius probe over

`P(m) = (a m + b)/(c m + d)` with `|a|,|b|,|c|,|d| <= 2`

found the best maps to be equivalent fractional-linear reparametrizations such as:

- `P(m) = (2m+2)/(m+2)`
- `P(m) = (m+2)/2`
- `P(m) = (2m+1)/(m+1)`

All top maps gave roughly:

- `zeta` anchor quality at `m=0`: `~1.96` digits
- best `V_quad` overlap for `m=1,2,3`: `~2.36` digits

Interpretation: the master flow is **consistent with a Möbius deformation**, but the currently scanned small-height maps are only heuristic and do **not** yet give an exact Apéry ↔ `V_quad` unifier.

---

## Pincherle / Leiden classification

High-precision forward/backward checks confirm Pincherle compatibility for the principal representatives:

- `(-15,0,-4,0,1,0)` → `119.51` digits agreement
- `(-15,-1,-4,0,5/4,1)` → `120.11` digits agreement
- `(-15,1,-5,1,4/3,-1)` → `119.93` digits agreement

Leiden-style interpretation:

- `C=1, bridge=0` peaks → **Leiden-A transcendental** / Apéry-type
- `C=4/3, bridge=-1` ridge → **Leiden-W rational boundary**
- `C=5/4, bridge=+1` island → **Leiden-S hidden spectral island**

---

## Recommendation for the next 1500dp target

**Primary recommendation**

Run the next full 1500dp validation on:

- `fixed_alpha`
- `(a1,a2,b1,b2,C,bridge)=(-15,-1,-4,0,5/4,+1)`

Reason:

1. it is the clearest non-rational **spectral island**;
2. it has near-zero stability decay without collapsing into the exact `zeta(3)` basin;
3. it lies within `2.87e-3` of `5*V_quad`, making it the strongest bridge toward the `V_quad` frontier.

**Secondary control target**

Use

- `shifted_alpha`, `(-15,1,-5,1,4/3,-1)`

as the **Wallis-boundary control**, since it exhibits the rational-collapse phase toward `-2/5`.
