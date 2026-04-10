# Generalized Dichotomy — Dense Fractional-β Targeted Sweep

## Scan setup
- `β` grid: reduced fractions `p/q` with `1 ≤ q ≤ 12` and `|β| ≤ 3`.
- Degree 3 parameters kept from the prior targeted run: `p ∈ [1, 2, -1]`, `α ∈ [3, 4, 5, 6]`.
- Degree 4 parameters kept from the prior targeted run: `p ∈ [1]`, `α ∈ [5, 6]`.
- Total evaluated cases: **266**; convergent at the ≥20-digit threshold: **152**.

## Bucket summary

| bucket | cases | convergent | best case | best stable digits | best PSLQ digits |
|---|---:|---:|---|---:|---:|
| `rational` | 98 | 56 | `(3, 1, 6, 3)` | 81.263752 | 0.000000 |
| `gamma_1_3` | 72 | 48 | `(3, 1, 6, 8/3)` | 81.105219 | 0.000000 |
| `gamma_2_3` | 72 | 48 | `(3, 1, 6, 7/3)` | 80.944919 | 0.000000 |
| `gamma_1_4` | 12 | 0 | `(4, 1, 6, 11/4)` | 14.215005 | 0.000000 |
| `gamma_3_4` | 12 | 0 | `(4, 1, 6, 9/4)` | 14.083695 | 0.000000 |

## New best ratios / hits

- Best overall candidate: `(3, 1, 6, 3)` in `rational` with **81.263752** stable digits and **0.000000** PSLQ digits.
- Best fractional Gamma-sector candidate: `(3, 1, 6, 8/3)` in `gamma_1_3` with value `2.775701629741208203442`.
- Best quartic candidate: `(4, 1, 6, 11/4)` with **14.215005** stable digits and **0.000000** PSLQ digits.

| rank | case | bucket | stable digits | PSLQ family | PSLQ digits | verdict |
|---:|---|---|---:|---|---:|---|
| 1 | `(3, 1, 6, 3)` | `rational` | 81.263752 | `none` | 0.000000 | `INCONCLUSIVE` |
| 2 | `(3, 1, 6, 8/3)` | `gamma_1_3` | 81.105219 | `none` | 0.000000 | `INCONCLUSIVE` |
| 3 | `(3, 1, 6, 7/3)` | `gamma_2_3` | 80.944919 | `none` | 0.000000 | `INCONCLUSIVE` |
| 4 | `(3, 1, 6, 2)` | `rational` | 80.782759 | `none` | 0.000000 | `INCONCLUSIVE` |
| 5 | `(3, 1, 6, 5/3)` | `gamma_1_3` | 80.618640 | `none` | 0.000000 | `INCONCLUSIVE` |
| 6 | `(3, 1, 6, 4/3)` | `gamma_2_3` | 80.452450 | `none` | 0.000000 | `INCONCLUSIVE` |
| 7 | `(3, 1, 6, 1)` | `rational` | 80.284067 | `none` | 0.000000 | `INCONCLUSIVE` |
| 8 | `(3, 1, 6, 2/3)` | `gamma_1_3` | 80.113356 | `none` | 0.000000 | `INCONCLUSIVE` |
| 9 | `(3, 1, 6, 1/3)` | `gamma_2_3` | 79.940163 | `none` | 0.000000 | `INCONCLUSIVE` |
| 10 | `(3, 1, 6, 0)` | `rational` | 79.764318 | `none` | 0.000000 | `INCONCLUSIVE` |
| 11 | `(3, 1, 6, -1/3)` | `gamma_1_3` | 79.585629 | `none` | 0.000000 | `INCONCLUSIVE` |
| 12 | `(3, 1, 6, -2/3)` | `gamma_2_3` | 79.403878 | `none` | 0.000000 | `INCONCLUSIVE` |

## Conjecture status

**Verdict: NOT CONFIRMED.** The denser fractional-β grid did not close the gap or produce an exact expected-family PSLQ match at the current precision and coeff bound.
- `rational`: **INCONCLUSIVE** — 56 stable case(s) tested but no ≥15-digit PSLQ relation was found at coeff bound 500.
- `gamma_1_3`: **INCONCLUSIVE** — 48 stable case(s) tested but no ≥15-digit PSLQ relation was found at coeff bound 500.
- `gamma_2_3`: **INCONCLUSIVE** — 48 stable case(s) tested but no ≥15-digit PSLQ relation was found at coeff bound 500.
- `gamma_1_4`: **INCONCLUSIVE** — No case in this bucket reached the 20-digit stability threshold at depth 400 vs 300.
- `gamma_3_4`: **INCONCLUSIVE** — No case in this bucket reached the 20-digit stability threshold at depth 400 vs 300.

## Step 4 — counterexample search

- Strongest cubic `1/3`-sector case: `d3_p1_a6_b8_3`
- Value: `2.77570162974120820344188457135`
- Stable digits: **81.105219**
- Gamma-basis result: `no relation` (0.000000 digits)
- Non-Gamma basis result: `no relation` (0.000000 digits)
- Verdict: **INCONCLUSIVE**

## Recommended deep rerun

- Next best parameter set: `(3, 1, 6, 8/3)` because it is the strongest fractional-β candidate under the current sweep (**81.105219** stable digits).

## Extended p-scan

- Not triggered: no fractional-β case exceeded the 15-digit PSLQ threshold.