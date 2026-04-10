# Mission G-01 report

- Date: 2026-04-09 09:35:27
- Precision: mpmath dps=80
- Partition cutoff: N=10000

## Section A — G-01 law table

| k | c_k (growth) | predicted A1 | actual A1 | rel. error | digits | status |
|---:|---:|---:|---:|---:|---:|:---:|
| 13 | 9.2485983519724638703 | -5.5323145008094008654 | -5.5323145462406939643 | 8.21198663221e-9 | 8.086 | PASS |
| 14 | 9.5977240918616055225 | -6.1204360391020430899 | -6.1204360997478275408 | 9.90873582577e-9 | 8.004 | PASS |
| 15 | 9.9345882657961012344 | -6.7282621045843481584 | -6.7282621832214566382 | 1.16875808847e-8 | 7.932 | PASS |
| 16 | 10.260398641294912764 | -7.3551651741578466952 | -7.3551652737805737203 | 1.35445939441e-8 | 7.868 | PASS |
| 17 | 10.576176839750713892 | -8.0005749454975911251 | -8.0005750693191028944 | 1.54765764581e-8 | 7.810 | PASS |
| 18 | 10.882796185405307104 | -8.6639700127206365754 | -8.6639701641752928651 | 1.7480976206e-8 | 7.757 | PASS |
| 19 | 11.181010199461639395 | -9.3448711682046155774 | -9.3448713509499654606 | 1.95556838634e-8 | 7.709 | PASS |
| 20 | 11.471474419090952884 | -10.042835938323694482 | -10.042836156242847423 | 2.16989652674e-8 | 7.664 | PASS |
| 21 | 11.754763358538997856 | -10.757454071996646728 | -10.757454329200470511 | 2.39093577264e-8 | 7.621 | PASS |
| 22 | 12.03138387230014062 | -11.488343776294150173 | -11.48834407712458372 | 2.61857088826e-8 | 7.582 | PASS |
| 23 | 12.301785811419284834 | -12.235148545710276946 | -12.235148894742014392 | 2.85269709791e-8 | 7.545 | PASS |
| 24 | 12.566370614359172954 | -12.997534468868920955 | -12.99753487091275872 | 3.09323146087e-8 | 7.510 | PASS |

> Diagnostic note: the alternate residue/discriminant quantity `sqrt(24*a_k-(k-1)^2)` was also checked and does not match the extracted partition asymptotics when substituted directly into the G-01 formula.

## Section B — Lemma K table

| k | C_k_empirical | log(C_k)/log(k) | growth classification |
|---:|---:|---:|:---|
| 1 | 1.000000000000 | — | bounded (H3) |
| 2 | 1.000000000000 | 0 | bounded (H3) |
| 3 | 1.000000000000 | 0 | bounded (H3) |
| 5 | 1.000000000000 | 0 | bounded (H3) |
| 7 | 1.000000000000 | 0 | bounded (H3) |
| 10 | 1.000000000000 | 0 | bounded (H3) |
| 12 | 1.000000000000 | 0 | bounded (H3) |
| 13 | 1.000000000000 | 0 | bounded (H3) |
| 16 | 1.000000000000 | 0 | bounded (H3) |
| 20 | 1.000000000000 | 0 | bounded (H3) |
| 24 | 1.000000000000 | 0 | bounded (H3) |

> Max over q<=200: `C_empirical = 1.000000000000` at `q=1`.

## Section C — Proof recommendation

Lemma K appears numerically bounded in the tested window, with a flat empirical constant C_k^emp ≈ 1.000000 (attained at q=1). This supports the elementary proof route: cite the classical Weil bound for Kloosterman sums, then track the eta-multiplier normalization carefully in the Petersson/Rademacher setup. The G-01 law continues to match the extracted A1 values for k=13..24 under the standard growth normalization.

## Section D — Anomaly report

- Using c_k = sqrt(24*a_k - (k-1)^2) literally in the G-01 formula produces large mismatches; this appears to be a notation/normalization mix-up rather than a genuine breakdown of the partition law.
