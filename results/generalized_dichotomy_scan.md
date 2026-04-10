# Generalized Dichotomy Conjecture Scan

> Note: on the exact integer grid, `rho = alpha - beta` is always an integer, so `rho mod 1 = 0` for every strict-grid case. The nonzero `1/3, 2/3, 1/4, 3/4` buckets only appear in the auxiliary fractional-beta visibility probe.

## Degree 3

### strict_integer_grid

- Convergent cases: **156 / 360**
- PSLQ relation hits (`>=8` digits): **0**
- Bucket counts: `{'bucket_0': 360}`
- Conjecture status: **REFUTED**

| (p, α, β) | ρ | ρ mod 1 | bucket | PSLQ result | digits | confirm? |
|---|---:|---:|---|---|---:|---|
| `(1, 6, 5)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 4)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 3)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 2)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 1)` | 5 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 0)` | 6 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 5)` | 0 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 4)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 3)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 2)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 1)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 0)` | 5 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(2, 6, 5)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(2, 6, 4)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(2, 6, 3)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 4, 5)` | -1 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(2, 6, 2)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 4, 4)` | 0 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(2, 6, 1)` | 5 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(2, 6, 0)` | 6 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 4, 3)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 4, 2)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 4, 1)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 4, 0)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(2, 5, 5)` | 0 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |

#### Top 5 strongest PSLQ matches

- No relation hits at the requested coefficient bound.

#### Anomalies

- No cross-family anomalies detected among the recorded PSLQ hits.

### fractional_visibility_probe

- Convergent cases: **319 / 720**
- PSLQ relation hits (`>=8` digits): **0**
- Bucket counts: `{'bucket_2_3': 360, 'bucket_1_3': 360}`
- Conjecture status: **REFUTED**

| (p, α, β) | ρ | ρ mod 1 | bucket | PSLQ result | digits | confirm? |
|---|---:|---:|---|---|---:|---|
| `(1, 6, 17/3)` | 1/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 16/3)` | 2/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 14/3)` | 4/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 13/3)` | 5/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 11/3)` | 7/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 10/3)` | 8/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 8/3)` | 10/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 7/3)` | 11/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 5/3)` | 13/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 4/3)` | 14/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 2/3)` | 16/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 6, 1/3)` | 17/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 17/3)` | -2/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 16/3)` | -1/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 14/3)` | 1/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 13/3)` | 2/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 11/3)` | 4/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 10/3)` | 5/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 8/3)` | 7/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 7/3)` | 8/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 5/3)` | 10/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 4/3)` | 11/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 2/3)` | 13/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |
| `(1, 5, 1/3)` | 14/3 | 2/3 | `bucket_2_3` | no relation | 0.000 | `no-hit` |
| `(2, 6, 17/3)` | 1/3 | 1/3 | `bucket_1_3` | no relation | 0.000 | `no-hit` |

#### Top 5 strongest PSLQ matches

- No relation hits at the requested coefficient bound.

#### Anomalies

- No cross-family anomalies detected among the recorded PSLQ hits.

## Degree 4

### strict_integer_grid

- Convergent cases: **9 / 360**
- PSLQ relation hits (`>=8` digits): **0**
- Bucket counts: `{'bucket_0': 360}`
- Conjecture status: **REFUTED**

| (p, α, β) | ρ | ρ mod 1 | bucket | PSLQ result | digits | confirm? |
|---|---:|---:|---|---|---:|---|
| `(1, 6, 5)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 4)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 3)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 2)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 1)` | 5 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 6, 0)` | 6 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 5)` | 0 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 4)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 3)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `no-hit` |
| `(1, 5, 2)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 5, 1)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 5, 0)` | 5 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 4, 5)` | -1 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(2, 6, 5)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 4, 4)` | 0 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(2, 6, 4)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 4, 3)` | 1 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(2, 6, 3)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(2, 6, 2)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 4, 2)` | 2 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(2, 6, 1)` | 5 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 4, 1)` | 3 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(2, 6, 0)` | 6 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(2, 5, 5)` | 0 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |
| `(1, 4, 0)` | 4 | 0 | `bucket_0` | no relation | 0.000 | `unstable` |

#### Top 5 strongest PSLQ matches

- No relation hits at the requested coefficient bound.

#### Anomalies

- No cross-family anomalies detected among the recorded PSLQ hits.

### fractional_visibility_probe

- Convergent cases: **20 / 720**
- PSLQ relation hits (`>=8` digits): **0**
- Bucket counts: `{'bucket_3_4': 360, 'bucket_1_4': 360}`
- Conjecture status: **REFUTED**

| (p, α, β) | ρ | ρ mod 1 | bucket | PSLQ result | digits | confirm? |
|---|---:|---:|---|---|---:|---|
| `(1, 6, 23/4)` | 1/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 21/4)` | 3/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 19/4)` | 5/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 17/4)` | 7/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 15/4)` | 9/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 13/4)` | 11/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 11/4)` | 13/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 9/4)` | 15/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 7/4)` | 17/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 5/4)` | 19/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 3/4)` | 21/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 6, 1/4)` | 23/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 23/4)` | -3/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 21/4)` | -1/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 19/4)` | 1/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 17/4)` | 3/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 15/4)` | 5/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 13/4)` | 7/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 11/4)` | 9/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 9/4)` | 11/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `no-hit` |
| `(1, 5, 7/4)` | 13/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `unstable` |
| `(1, 5, 5/4)` | 15/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `unstable` |
| `(1, 5, 3/4)` | 17/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `unstable` |
| `(1, 5, 1/4)` | 19/4 | 3/4 | `bucket_3_4` | no relation | 0.000 | `unstable` |
| `(1, 4, 23/4)` | -7/4 | 1/4 | `bucket_1_4` | no relation | 0.000 | `unstable` |

#### Top 5 strongest PSLQ matches

- No relation hits at the requested coefficient bound.

#### Anomalies

- No cross-family anomalies detected among the recorded PSLQ hits.
