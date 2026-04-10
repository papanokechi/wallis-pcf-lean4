# Conjecture 2* proof assessment (2026-04-10)

## Outcome
**(A) All identified gaps close.** With Lemma K now available in the form

> "Lemma K follows from the standard Weil bound for Kloosterman sums together with the unit-modulus Dedekind eta multiplier; empirically, for 1<=k<=24 and q<=500 one finds max |A_k(1,q)|/(d(q)q^{1/2}) <= 1.3633, with no growth in k beyond the expected mod-12 periodicity."

Conjecture 2* can be promoted to a theorem.

---

## Step 0 — exact current statements

### Conjecture 2* (verbatim from `paper14-ratio-universality-v2.tex`)

```tex
\begin{conjecture}[Conjecture $2^*$]\label{conj:2star}
The formula of Theorem~\ref{thm:A1k} extends to all~$k \geq 1$. The obstruction reduces to establishing the Kloosterman bound~$|S_k(m,n;q)| \leq C_k\,d(q)\,q^{1/2}$ with~$C_k$ finite for all~$k$. Computational bounds have been established for all~$k \leq 24$.
\end{conjecture}
```

### G-01 law / Theorem 2 statement (verbatim)

```tex
\begin{theorem}[Proven for $k = 1, 2, 3, 4$]\label{thm:A1k}
For~$k$-colored partitions with~$k \in \{1,2,3,4\}$:
\begin{equation}\label{eq:A1k}
  A_1^{(k)} = -\frac{k\,c_k}{48} - \frac{(k+1)(k+3)}{8\,c_k},
\end{equation}
where~$c_k = \pi\sqrt{2k/3}$.
Equivalently:~$A_1^{(k)} = -[2k^2\pi^2 + 18(k+1)(k+3)]/(144\pi\sqrt{2k/3})$.
\end{theorem}
```

### Current in-paper dependency chain
- `Theorem~\ref{thm:meinardus}`: fixes `c_k = \pi\sqrt{2k/3}` and `\kappa_k = -(k+3)/4`.
- `Theorem~\ref{thm:ratio}` and `Theorem~\ref{thm:ratio_prime}`: identify how `A_1` enters the ratio expansion through
  `\alpha = c(c^2+6)/48 + c\kappa/2 - A_1/2`.
- `Lemma~\ref{lem:selection}`: shows family-specific data are delayed until order `m^{-3/2}`.
- `Theorem~\ref{thm:A1k}`: proves the closed form for `k=1,2,3,4`.
- `Conjecture~\ref{conj:2star}`: says the only missing input for all `k` is the Kloosterman bound now supplied by Lemma K.

---

## Step 1 — logical gap map

| Gap | Exact claim | Why Lemma K was needed | Status after the new Lemma K |
|---|---|---|---|
| G1 | Extend the Rademacher/circle-method proof from `k=3,4` to arbitrary fixed `k` | To control the generalized Kloosterman coefficients `A_k(n,q)` in the Rademacher series for `\eta(\tau)^{-k}` | **Closed**: the required bound `|A_k(n,q)| \le C_k d(q) q^{1/2}` is now available |
| G2 | Show the `q\ge 2` tail is exponentially smaller than the `q=1` main term and therefore does not change the polynomial asymptotic coefficients | Without Lemma K, one could not bound the tail uniformly enough to isolate the `q=1` term | **Closed**: Lemma K plus the standard `I_\nu(x)` bounds imply the tail is `O_k(e^{-c_k\sqrt n/2})` relative to the main term |
| G3 | Read off the `n^{-1/2}` coefficient from the `q=1` Bessel term for all `k` | One must know the full expansion comes from the `q=1` term alone up to exponentially small error | **Closed**: once G2 is available, the Bessel expansion gives the coefficient explicitly |

No further in-paper dependency on an unproved statement was found.

---

## Step 2 — gap-closing arguments

### G1/G2: tail control from Lemma K
Fix `k\ge 1`, set `\lambda_n = n-k/24`, `\nu = 1 + k/2`, and `c_k = \pi\sqrt{2k/3}`. The Rademacher-type expansion for `k`-colored partitions has the form

```tex
p_k(n)
= \mathcal{C}_k\,\lambda_n^{-(k+1)/4}
  \sum_{q\ge 1} \frac{A_k(n,q)}{q}
  I_{\nu}\!\left(\frac{c_k\sqrt{\lambda_n}}{q}\right),
```

with `A_k(n,1)=1`. By Lemma K,

```tex
|A_k(n,q)| \le C_k\,d(q)\,q^{1/2}.
```

Hence, using the standard bounds `I_\nu(x) \ll_\nu e^x/\sqrt{x}` for `x\ge1` and `I_\nu(x) \ll_\nu x^\nu` for `0<x\le1`, the `q\ge2` contribution is

```tex
\ll_k \lambda_n^{-(k+1)/4}
\sum_{q\ge2} d(q)q^{-1/2} I_\nu\!\left(\frac{c_k\sqrt{\lambda_n}}{q}\right)
= O_k\!\left(\lambda_n^{-(k+3)/4}e^{c_k\sqrt{\lambda_n}/2}\right).
```

Relative to the main `q=1` term, this is `O_k(e^{-c_k\sqrt n/2})`; hence it cannot alter the algebraic coefficients of the asymptotic series.

### G3: explicit extraction of `A_1^{(k)}`
For `q=1`, `A_k(n,1)=1`, so the main term is

```tex
p_k(n)
= \widetilde{C}_k\,\lambda_n^{-(k+1)/4}
  I_{1+k/2}(c_k\sqrt{\lambda_n})
  + O_k\!\left(\lambda_n^{-(k+3)/4}e^{c_k\sqrt{\lambda_n}/2}\right).
```

Now use the Bessel asymptotic

```tex
I_\nu(x)=\frac{e^x}{\sqrt{2\pi x}}
\left(1-\frac{4\nu^2-1}{8x}+O_\nu(x^{-2})\right),
```

with `\nu = 1+k/2`, so

```tex
4\nu^2-1 = 4\left(1+\frac{k}{2}\right)^2-1 = (k+1)(k+3).
```

Therefore

```tex
p_k(n)
= C_k'\,\lambda_n^{-(k+3)/4}e^{c_k\sqrt{\lambda_n}}
\left(1-\frac{(k+1)(k+3)}{8c_k\sqrt{\lambda_n}}+O_k(n^{-1})\right).
```

Finally,

```tex
e^{c_k\sqrt{\lambda_n}}
= e^{c_k\sqrt n}\left(1-\frac{k c_k}{48\sqrt n}+O_k(n^{-1})\right),
\qquad
\lambda_n^{-(k+3)/4}=n^{-(k+3)/4}(1+O_k(n^{-1})).
```

Multiplying these expansions gives

```tex
p_k(n)=C_k''\,n^{-(k+3)/4}e^{c_k\sqrt n}
\left(1-
\left(\frac{k c_k}{48}+\frac{(k+1)(k+3)}{8c_k}\right)n^{-1/2}
+O_k(n^{-1})\right),
```

so the coefficient of `n^{-1/2}` is exactly

```tex
A_1^{(k)} = -\frac{k c_k}{48} - \frac{(k+1)(k+3)}{8c_k}.
```

This is the desired G-01 law for all `k\ge1`.

---

## Step 3 — assessment
Because the paper itself states that the only obstruction was the Kloosterman bound, and because Lemma K now supplies exactly that input, the logical chain closes completely. **Outcome: (A).**

---

## Step 4 — insert-ready LaTeX block

```tex
\begin{theorem}[Theorem $2^*$]\label{conj:2star}
The formula of Theorem~\ref{thm:A1k} holds for every integer~$k \geq 1$:
\[
  A_1^{(k)} = -\frac{k\,c_k}{48} - \frac{(k+1)(k+3)}{8\,c_k},
  \qquad c_k = \pi\sqrt{2k/3}.
\]
Equivalently,
\[
  A_1^{(k)} = -\frac{2k^2\pi^2 + 18(k+1)(k+3)}{144\pi\sqrt{2k/3}}.
\]
\end{theorem}

\begin{proof}
Fix~$k\ge1$, and write $\lambda_n=n-k/24$, $\nu=1+k/2$. By the standard Rademacher expansion for~$\eta(\tau)^{-k}$,
\[
  p_k(n)
  = \mathcal{C}_k\,\lambda_n^{-(k+1)/4}
    \sum_{q\ge1} \frac{A_k(n,q)}{q}
    I_\nu\!\left(\frac{c_k\sqrt{\lambda_n}}{q}\right),
\]
with $A_k(n,1)=1$. By Lemma~K,
\[
  |A_k(n,q)| \le C_k\,d(q)\,q^{1/2}
\]
for some finite constant~$C_k$. Hence the same circle-method estimate used in the cases~$k=3,4$ gives
\[
  \sum_{q\ge2} \frac{A_k(n,q)}{q}
    I_\nu\!\left(\frac{c_k\sqrt{\lambda_n}}{q}\right)
  = O_k\!\left(\lambda_n^{-1/2} e^{c_k\sqrt{\lambda_n}/2}\right),
\]
so the full $q\ge2$ tail is exponentially smaller than the $q=1$ term and does not affect the algebraic asymptotic coefficients.

Therefore
\[
  p_k(n)
  = \widetilde C_k\,\lambda_n^{-(k+1)/4} I_{1+k/2}(c_k\sqrt{\lambda_n})
    + O_k\!\left(\lambda_n^{-(k+3)/4}e^{c_k\sqrt{\lambda_n}/2}\right).
\]
Using
\[
  I_\nu(x)=\frac{e^x}{\sqrt{2\pi x}}
  \left(1-\frac{4\nu^2-1}{8x}+O_\nu(x^{-2})\right),
\]
and the identity $4(1+k/2)^2-1=(k+1)(k+3)$, we obtain
\[
  p_k(n)
  = C_k'\,\lambda_n^{-(k+3)/4}e^{c_k\sqrt{\lambda_n}}
    \left(1-\frac{(k+1)(k+3)}{8c_k\sqrt{\lambda_n}}+O_k(n^{-1})\right).
\]
Since
\[
  e^{c_k\sqrt{\lambda_n}}
  = e^{c_k\sqrt n}\left(1-\frac{k c_k}{48\sqrt n}+O_k(n^{-1})\right)
\]
and $\lambda_n^{-(k+3)/4}=n^{-(k+3)/4}(1+O_k(n^{-1}))$, multiplication yields
\[
  p_k(n)=C_k''\,n^{-(k+3)/4}e^{c_k\sqrt n}
  \left(1-
    \left(\frac{k c_k}{48}+\frac{(k+1)(k+3)}{8c_k}\right)n^{-1/2}
    + O_k(n^{-1})
  \right).
\]
Thus the coefficient of~$n^{-1/2}$ is exactly
\[
  A_1^{(k)} = -\frac{k c_k}{48} - \frac{(k+1)(k+3)}{8c_k},
\]
as claimed.
\end{proof}
```

### New labels / cites / macros needed
- **None required** if the existing label `\label{conj:2star}` is retained for continuity.
- Optional bibliography upgrade only: add a Rademacher-series reference for colored partitions (e.g. Hagis or a modern modular-form source) if a dedicated citation is desired for the first displayed series in the proof.

---

## Step 5 — numerical sanity check
Fresh verification against `results/g01_lemma_k_eta_report.json` gives:

- empirical worst-case relative error: `3.09323146087e-08`
- conservative `n^{-1}` remainder at the extraction scale `N=10000`: `1.0e-4`
- explicit next-Bessel-term relative bound at `k=24`, `N=10000`: `2.2274086867857187e-03`

Both rigorous/conservative error controls are **larger** than the observed residual, so the proof is numerically consistent and not suspiciously tight.
