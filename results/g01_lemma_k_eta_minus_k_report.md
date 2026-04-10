# Lemma K eta^{-k} sign verification

- Date: 2026-04-09 18:29:53
- Precision: mpmath dps=double precision
- Range: 1 <= q <= 500, 1 <= k <= 24
- Correct eta^{-k} phase: `exp(-2*pi*i*k*theta(d,q))`

## Mathematical note

Using Apostol, Chapter 3, Theorem 3.4, one has eta(gamma tau) = exp(pi i*((a+d)/(12q) - s(d,q))) * (-i(q tau + d))^{1/2} * eta(tau) for q>0. Therefore eta(gamma tau)^{-k} carries the inverse character, giving exp(-2*pi*i*k*theta(d,q)) in the present normalization with theta(d,q)=(a+d)/(12q)-s(d,q). The stored q<=500 table is reproduced exactly with this negative-sign convention, confirming that the earlier report already used the correct eta^{-k} phase. Reference: Apostol, Modular Functions and Dirichlet Series in Number Theory, 2nd ed., Chapter 3, Theorem 3.4; equivalently Iwaniec-Kowalski, Analytic Number Theory, §3 on the eta-multiplier.

## Empirical C_k table

| k | C_k | q at max |
|---:|---:|---:|
| 1 | 1.076634708518 | 89 |
| 2 | 1.160742417782 | 443 |
| 3 | 1.304176924365 | 181 |
| 4 | 1.339862458263 | 281 |
| 5 | 1.363291520432 | 431 |
| 6 | 1.272129486365 | 449 |
| 7 | 1.252125077323 | 409 |
| 8 | 1.100491026949 | 337 |
| 9 | 1.210985077823 | 353 |
| 10 | 1.213473861354 | 61 |
| 11 | 1.000000000000 | 1 |
| 12 | 1.000000000000 | 1 |
| 13 | 1.076634708518 | 89 |
| 14 | 1.160742417782 | 443 |
| 15 | 1.304176924365 | 181 |
| 16 | 1.339862458263 | 281 |
| 17 | 1.363291520432 | 431 |
| 18 | 1.272129486365 | 449 |
| 19 | 1.252125077323 | 409 |
| 20 | 1.100491026949 | 337 |
| 21 | 1.210985077823 | 353 |
| 22 | 1.213473861354 | 61 |
| 23 | 1.000000000000 | 1 |
| 24 | 1.000000000000 | 1 |

## Sign-flip check

- Identical for all k=1..24: `False`
- Max |ΔC_k| between ± conventions: `2.394e-01`

| k | correct C_k | alt C_k | correct q | alt q | abs diff |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.076634708518 | 1.000000000000 | 89 | 1 | 7.663e-02 |
| 2 | 1.160742417782 | 1.213473861354 | 443 | 61 | 5.273e-02 |
| 3 | 1.304176924365 | 1.210985077823 | 181 | 353 | 9.319e-02 |
| 4 | 1.339862458263 | 1.100491026949 | 281 | 337 | 2.394e-01 |
| 5 | 1.363291520432 | 1.252125077323 | 431 | 409 | 1.112e-01 |
| 7 | 1.252125077323 | 1.363291520432 | 409 | 431 | 1.112e-01 |
| 8 | 1.100491026949 | 1.339862458263 | 337 | 281 | 2.394e-01 |
| 9 | 1.210985077823 | 1.304176924365 | 353 | 181 | 9.319e-02 |
| 10 | 1.213473861354 | 1.160742417782 | 61 | 443 | 5.273e-02 |
| 11 | 1.000000000000 | 1.076634708518 | 1 | 89 | 7.663e-02 |
| 13 | 1.076634708518 | 1.000000000000 | 89 | 1 | 7.663e-02 |
| 14 | 1.160742417782 | 1.213473861354 | 443 | 61 | 5.273e-02 |
| 15 | 1.304176924365 | 1.210985077823 | 181 | 353 | 9.319e-02 |
| 16 | 1.339862458263 | 1.100491026949 | 281 | 337 | 2.394e-01 |
| 17 | 1.363291520432 | 1.252125077323 | 431 | 409 | 1.112e-01 |
| 19 | 1.252125077323 | 1.363291520432 | 409 | 431 | 1.112e-01 |
| 20 | 1.100491026949 | 1.339862458262 | 337 | 281 | 2.394e-01 |
| 21 | 1.210985077823 | 1.304176924365 | 353 | 181 | 9.319e-02 |
| 22 | 1.213473861354 | 1.160742417782 | 61 | 443 | 5.273e-02 |
| 23 | 1.000000000000 | 1.076634708518 | 1 | 89 | 7.663e-02 |

## Comparison with previous report

- Previous report available: `True`
- Matching on stored subset: `True`
- Max |ΔC_k| on stored subset: `1.035e-13`
