# Corrected Lemma K diagnosis

- Date: 2026-04-09 16:40:22
- Precision: mpmath dps=80
- Main q-range: 1..300
- Extended q-range: 1..500

## Section A — Corrected Kloosterman table

| k | C_k_empirical | q_max | log(C_k)/log(k) | growth class |
|---:|---:|---:|---:|:---|
| 1 | 1.076634708518 | 89 | — | bounded (H4) |
| 2 | 1.160742417782 | 443 | 0.215048 | bounded (H4) |
| 3 | 1.304176924365 | 181 | 0.241734 | bounded (H4) |
| 4 | 1.339862458263 | 281 | 0.211042 | bounded (H4) |
| 5 | 1.363291520432 | 431 | 0.192553 | bounded (H4) |
| 6 | 1.272129486365 | 449 | 0.134333 | bounded (H4) |
| 7 | 1.252125077323 | 409 | 0.115546 | bounded (H4) |
| 8 | 1.100491026949 | 337 | 0.046049 | bounded (H4) |
| 10 | 1.213473861354 | 61 | 0.084030 | bounded (H4) |
| 12 | 1.000000000000 | 1 | 0.000000 | bounded (H4) |
| 13 | 1.076634708518 | 89 | 0.028788 | bounded (H4) |
| 16 | 1.339862458263 | 281 | 0.105521 | bounded (H4) |
| 20 | 1.100491026949 | 337 | 0.031964 | bounded (H4) |
| 24 | 1.000000000000 | 1 | 0.000000 | bounded (H4) |

## Section B — Growth fit

- **Best-fit hypothesis:** H4 bounded
- **Bounded window:** 1.000000 to 1.363292
- **Periodicity detected:** `True`
- **Power-law alpha:** -0.015779
- **Exponential alpha:** -0.003324
- **Confidence:** very high

## Section C — Proof recommendation

The corrected eta-multiplier computation supports H4: the empirical constants remain bounded in a narrow window (1.000 to 1.363) and are exactly 12-periodic in k, as expected from a 24th-root multiplier entering as nu_eta^{-2k}. This points to the low-difficulty route: invoke the classical Weil bound for Kloosterman sums together with the unit-modulus eta multiplier, then cite Weil (1948) or Iwaniec–Kowalski §4 for the q^{1/2} divisor-bound control.

## Section D — G-01 cross-check

- Source: `g01_lemma_k_report.json`
- All relative errors below `1e-6`: `True`
- Max relative error: `3.093e-08`
- Note: The recurrence-based A1 extraction is independent of the Kloosterman normalization. Using the corrected eta multiplier does not change the already-verified k=13..24 G-01 errors.

| k | predicted A1 | actual A1 | rel. error | status |
|---:|---:|---:|---:|:---:|
| 13 | -5.5323145008094008654 | -5.5323145462406939643 | 8.21198663221e-9 | PASS |
| 14 | -6.1204360391020430899 | -6.1204360997478275408 | 9.90873582577e-9 | PASS |
| 15 | -6.7282621045843481584 | -6.7282621832214566382 | 1.16875808847e-8 | PASS |
| 16 | -7.3551651741578466952 | -7.3551652737805737203 | 1.35445939441e-8 | PASS |
| 17 | -8.0005749454975911251 | -8.0005750693191028944 | 1.54765764581e-8 | PASS |
| 18 | -8.6639700127206365754 | -8.6639701641752928651 | 1.7480976206e-8 | PASS |
| 19 | -9.3448711682046155774 | -9.3448713509499654606 | 1.95556838634e-8 | PASS |
| 20 | -10.042835938323694482 | -10.042836156242847423 | 2.16989652674e-8 | PASS |
| 21 | -10.757454071996646728 | -10.757454329200470511 | 2.39093577264e-8 | PASS |
| 22 | -11.488343776294150173 | -11.48834407712458372 | 2.61857088826e-8 | PASS |
| 23 | -12.235148545710276946 | -12.235148894742014392 | 2.85269709791e-8 | PASS |
| 24 | -12.997534468868920955 | -12.99753487091275872 | 3.09323146087e-8 | PASS |

## Section E — Action item for Paper 14

Lemma K follows from the standard Weil bound for Kloosterman sums together with the unit-modulus Dedekind eta multiplier; empirically, for 1<=k<=24 and q<=500 one finds max |A_k(1,q)|/(d(q)q^{1/2}) <= 1.3633, with no growth in k beyond the expected mod-12 periodicity.

## Section F — Sign convention for $\eta(\tau)^{-k}$

Using Apostol, *Modular Functions and Dirichlet Series in Number Theory* (2nd ed., Ch. 3, Thm. 3.4), equivalently Iwaniec–Kowalski on the eta-multiplier, one has
\[
\eta(\gamma\tau)=\exp\!\left(\pi i\left(\frac{a+d}{12q}-s(d,q)\right)\right)(-i(q\tau+d))^{1/2}\eta(\tau).
\]
Therefore $\eta(\tau)^{-k}$ carries the **inverse** multiplier, so with $\theta(d,q)=\frac{a+d}{12q}-s(d,q)$ the correct phase in the present normalization is
\[
\exp\!\bigl(-2\pi i k\,\theta(d,q)\bigr).
\]
This is the sign used in the verified computation; a raw replacement by $\exp(+2\pi i k\,\theta(d,q))$ would correspond to a different normalization and is not the paper convention adopted here.

## Sign convention

By Apostol, Ch.~3, Thm.~3.4 (see also Iwaniec--Kowalski, \S2.8), the correct phase for the $\eta(\tau)^{-k}$ multiplier is $\exp(-2\pi i k\,\theta(d,q))$ with $\theta(d,q)=(a+d)/(12q)-s(d,q)$. 
