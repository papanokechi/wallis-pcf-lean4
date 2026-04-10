#!/usr/bin/env python3
"""Generate convergence.png: two-panel convergence plot for the 4/pi paper.

Panel (a): log10|S_N - pi/4| vs N for the series partial sums.
Panel (b): log10|p_n/q_n - 4/pi| vs n for the CF convergents.

Usage:  python gen_convergence_plot.py
Output: convergence.png (150 dpi)
"""
import mpmath
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import math


def main():
    mpmath.mp.dps = 80
    pi4 = mpmath.pi / 4
    four_over_pi = 4 / mpmath.pi

    # ── Panel (a): series partial sums ──────────────────────────────
    N_max = 60
    ns_series, errs_series = [], []
    s = mpmath.mpf(1)
    for k in range(1, N_max + 1):
        # (2k-1)!!
        df = mpmath.mpf(1)
        for j in range(1, 2 * k, 2):
            df *= j
        poly_hi = k * k + 3 * k + 1
        poly_lo = k * k + k - 1
        term = mpmath.factorial(k) / (df * poly_hi * poly_lo)
        s -= term
        err = abs(s - pi4)
        if err > 0:
            ns_series.append(k)
            errs_series.append(float(mpmath.log10(err)))

    # Theoretical rate: -k*log10(2) - (7/2)*log10(k) + const
    # Fit constant from the data at k=30
    ref_k = 30
    log2 = math.log10(2)
    c_fit = errs_series[ref_k - 1] + ref_k * log2 + 3.5 * math.log10(ref_k)
    theory_ns = list(range(3, N_max + 1))
    theory_line = [c_fit - n * log2 - 3.5 * math.log10(n) for n in theory_ns]

    # ── Panel (b): CF convergent errors ─────────────────────────────
    n_cf_max = 20
    ns_cf, errs_cf = [], []
    p_prev, p_curr = mpmath.mpf(1), mpmath.mpf(1)
    q_prev, q_curr = mpmath.mpf(0), mpmath.mpf(1)
    err0 = abs(p_curr / q_curr - four_over_pi)
    if err0 > 0:
        ns_cf.append(0)
        errs_cf.append(float(mpmath.log10(err0)))
    for n in range(1, n_cf_max + 1):
        a_n = mpmath.mpf(-n * (2 * n - 3))
        b_n = mpmath.mpf(3 * n + 1)
        p_new = b_n * p_curr + a_n * p_prev
        q_new = b_n * q_curr + a_n * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
        err = abs(p_curr / q_curr - four_over_pi)
        if err > 0:
            ns_cf.append(n)
            errs_cf.append(float(mpmath.log10(err)))

    # ── Plot ────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Panel (a)
    ax1.plot(ns_series, errs_series, "o-", markersize=2.5,
             linewidth=1.0, color="#2060a0", label="Series $S_N$")
    ax1.plot(theory_ns, theory_line, "--", linewidth=0.9,
             color="#b04020",
             label=r"$-N\log_{10}2 - \frac{7}{2}\log_{10}N + C$")
    ax1.set_xlabel("Term index $N$", fontsize=10)
    ax1.set_ylabel(r"$\log_{10}|S_N - \pi/4|$", fontsize=10)
    ax1.set_title("(a) Series convergence", fontsize=11)
    ax1.legend(fontsize=8, loc="upper right")
    ax1.grid(True, alpha=0.25)

    # Panel (b)
    ax2.plot(ns_cf, errs_cf, "s-", markersize=3.5,
             linewidth=1.0, color="#208040")
    ax2.set_xlabel("Convergent index $n$", fontsize=10)
    ax2.set_ylabel(r"$\log_{10}|p_n/q_n - 4/\pi|$", fontsize=10)
    ax2.set_title("(b) CF convergent error", fontsize=11)
    ax2.grid(True, alpha=0.25)

    fig.tight_layout(w_pad=3)
    fig.savefig("convergence.png", dpi=150)
    print(f"Saved convergence.png  (series: {len(ns_series)} pts, "
          f"CF: {len(ns_cf)} pts)")


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
