# Degree-3 / Degree-4 Dichotomy Confirmation Scan

- Precision: **mp.dps = 150**
- Depths: **(200, 350, 500)**
- Stability threshold for PSLQ: **15 digits**
- PSLQ coefficient bound: **500**
- Verdict: **OPEN**
- Summary: The naive residue-class-only extension is not supported by the tested cases: the strongest cubic example (3,1,6,5/3) stabilized to 64.22 digits but gave no standard Gamma-basis PSLQ relation at coeff bound 500. The extended diagnostic search (adding pi^(1/3), pi^(2/3), 3^(1/3), and log(3) mixtures) also returned no relation at the same coefficient bound.

| case | rho | rho mod 1 | bucket | stable digits | result | PSLQ digits |
|---|---:|---:|---|---:|---|---:|
| `(3,1,4,1)` | `3` | `0` | `rational` | 43.906568 | no rational hit <= 20/20 | 0.000000 |
| `(3,1,5,2)` | `3` | `0` | `rational` | 54.574259 | no rational hit <= 20/20 | 0.000000 |
| `(3,2,6,3)` | `3` | `0` | `rational` | 46.874139 | no rational hit <= 20/20 | 0.000000 |
| `(3,1,4,5/3)` | `7/3` | `1/3` | `gamma_1_3` | 44.294466 | no Gamma(1/3), Gamma(2/3) basis hit | 0.000000 |
| `(3,1,5,5/3)` | `10/3` | `1/3` | `gamma_1_3` | 54.400367 | no Gamma(1/3), Gamma(2/3) basis hit | 0.000000 |
| `(3,1,6,5/3)` | `13/3` | `1/3` | `gamma_1_3` | 64.218489 | no Gamma(1/3), Gamma(2/3) basis hit | 0.000000 |
| `(3,2,4,5/3)` | `7/3` | `1/3` | `gamma_1_3` | 31.638542 | no Gamma(1/3), Gamma(2/3) basis hit | 0.000000 |
| `(3,1,3,2/3)` | `7/3` | `1/3` | `gamma_1_3` | 33.267687 | no Gamma(1/3), Gamma(2/3) basis hit | 0.000000 |
| `(3,1,4,1/3)` | `11/3` | `2/3` | `gamma_2_3` | 43.504292 | no Gamma(1/3), Gamma(2/3) basis hit | 0.000000 |
| `(3,1,5,2/3)` | `13/3` | `1/3` | `gamma_1_3` | 53.862873 | no Gamma(1/3), Gamma(2/3) basis hit | 0.000000 |
| `(4,1,5,3/4)` | `17/4` | `1/4` | `gamma_1_4` | 10.626293 | skipped (<15 stable digits) | 0.000000 |
| `(4,1,6,3/4)` | `21/4` | `1/4` | `gamma_1_4` | 12.537646 | skipped (<15 stable digits) | 0.000000 |
| `(4,1,5,7/4)` | `13/4` | `1/4` | `gamma_1_4` | 10.924657 | skipped (<15 stable digits) | 0.000000 |
| `(4,1,5,1/4)` | `19/4` | `3/4` | `gamma_3_4` | 10.470131 | skipped (<15 stable digits) | 0.000000 |
| `(4,1,6,1/4)` | `23/4` | `3/4` | `gamma_3_4` | 12.392615 | skipped (<15 stable digits) | 0.000000 |

## Counterexample diagnostics

- Target case: `(3,1,6,5/3)`
- Value at depth 600: `1.7885654281636925083376668614200083376530911373171`
- `identify(...)`: `None`
- Continued fraction prefix: `[1, 1, 3, 1, 2, 1, 2, 3, 5, 6, 1, 10, 2, 3, 2, 3, 15, 1, 1, 1, 1, 1, 3, 5, 1]`
- Extended PSLQ: `no relation in the extended basis up to 24 elements at coeff bound 500`
