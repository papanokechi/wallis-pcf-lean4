"""
S^(m) Family: DEFINITIVE verification of the closed form.

Proves numerically that:
  val(m) = 2^{2m+1} / (pi * C(2m,m))
  
by computing:
  1. val(m) * pi * C(2m,m) / 2^{2m+1} == 1 to 1000 digits for m=0..20
  2. S^(m)/S^(m-1) = 2m/(2m-1) to 1000 digits
  3. S^(m)*pi/4 = 2^{2m-1}/C(2m,m) (rational verification)
  4. Convergence rate as function of m at 1000dp
"""
from __future__ import annotations
from mpmath import mp, mpf, pi, log, nstr, binomial, fac
import time


PREC = 1000
DEPTH_LO = 2000
DEPTH_HI = 4000
MAX_M = 20


def _eval_pi_family(m, depth=DEPTH_LO):
    """Compute val(m) via backward recurrence."""
    val = mpf(0)
    for n in range(depth, 0, -1):
        an = -mpf(n) * (2 * n - 2 * m - 1)
        bn = mpf(3 * n + 1)
        denom = bn + val
        if abs(denom) < mpf(10) ** (-mp.dps + 5):
            return None
        val = an / denom
    return mpf(1) + val


def main():
    mp.dps = PREC + 50

    sep = "=" * 80
    print(sep)
    print("  DEFINITIVE VERIFICATION: val(m) = 2^(2m+1) / (pi * C(2m,m))")
    print(sep)

    # ── Compute all val(m) ─────────────────────────────────────────────────
    print("\nComputing val(m) at 1000dp, depth 2000...")
    t0 = time.time()
    vals = {}
    for m in range(MAX_M + 1):
        vals[m] = _eval_pi_family(m, depth=DEPTH_LO)
        if m <= 10 or m == MAX_M:
            elapsed = time.time() - t0
            print(f"  m={m:2d}  val={nstr(vals[m], 30)}  [{elapsed:.1f}s]")

    # ── TEST 1: val(m) * pi * C(2m,m) / 2^(2m+1) == 1 ───────────────────
    print(f"\n{'='*80}")
    print("TEST 1: val(m) * pi * C(2m,m) / 2^(2m+1) = 1 ?")
    print(f"{'m':>3s}  {'|ratio - 1|':>20s}  {'Matching digits':>16s}")
    print("-" * 45)
    for m in range(MAX_M + 1):
        binom_val = binomial(2 * m, m)
        ratio = vals[m] * pi * binom_val / mpf(2) ** (2 * m + 1)
        residual = abs(ratio - 1)
        if residual > 0:
            digits = -float(log(residual, 10))
        else:
            digits = PREC
        print(f"{m:3d}  {nstr(residual, 5):>20s}  {digits:>16.1f}")

    # ── TEST 2: val(m)/val(m-1) = 2m/(2m-1) ──────────────────────────────
    print(f"\n{'='*80}")
    print("TEST 2: val(m)/val(m-1) = 2m/(2m-1) ?")
    print(f"{'m':>3s}  {'Ratio':>30s}  {'2m/(2m-1)':>12s}  {'Match digits':>14s}")
    print("-" * 64)
    for m in range(1, MAX_M + 1):
        ratio = vals[m] / vals[m - 1]
        expected = mpf(2 * m) / (2 * m - 1)
        residual = abs(ratio - expected)
        if residual > 0:
            digits = -float(log(residual, 10))
        else:
            digits = PREC
        print(f"{m:3d}  {nstr(ratio, 25):>30s}  {2*m}/{2*m-1:<9d}  {digits:>14.1f}")

    # ── TEST 3: val(m)*pi/4 is rational = 2^(2m-1)/C(2m,m) ──────────────
    print(f"\n{'='*80}")
    print("TEST 3: val(m) * pi / 4 = 2^(2m-1) / C(2m,m)  [rational check]")
    print(f"{'m':>3s}  {'val(m)*pi/4 (30 dig)':>35s}  {'2^(2m-1)/C(2m,m)':>22s}  {'Match':>14s}")
    print("-" * 80)
    for m in range(MAX_M + 1):
        lhs = vals[m] * pi / 4
        rhs = mpf(2) ** (2 * m - 1) / binomial(2 * m, m)
        residual = abs(lhs - rhs)
        if residual > 0:
            digits = -float(log(residual, 10))
        else:
            digits = PREC
        # Print exact rational form
        num = 2 ** (2 * m - 1)
        den = int(binomial(2 * m, m))
        from math import gcd
        g = gcd(int(num), int(den))
        print(f"{m:3d}  {nstr(lhs, 30):>35s}  {num//g}/{den//g:<14d}  {digits:>14.1f}")

    # ── TEST 4: val(m) * pi is rational with denominator prediction ───────
    print(f"\n{'='*80}")
    print("TEST 4: val(m) * pi = 2^(2m+1) / C(2m,m)  [exact rational * pi]")
    for m in range(MAX_M + 1):
        product = vals[m] * pi
        num = 2 ** (2 * m + 1)
        den = int(binomial(2 * m, m))
        from math import gcd
        g = gcd(int(num), int(den))
        expected_rational = mpf(num) / den
        residual = abs(product - expected_rational)
        if residual > 0:
            digits = -float(log(residual, 10))
        else:
            digits = PREC
        print(f"  m={m:2d}: val(m)*pi = {num//g}/{den//g}  ({digits:.0f} digits)")

    # ── TEST 5: Convergence rate R(m) at 1000dp ──────────────────────────
    print(f"\n{'='*80}")
    print("TEST 5: CONVERGENCE RATE (1000dp, depth 2000 vs 4000)")
    print(f"{'m':>3s}  {'Stable digits':>14s}")
    print("-" * 22)
    for m in [0, 1, 2, 5, 8, 10, 15, 20]:
        v_hi = _eval_pi_family(m, depth=DEPTH_HI)
        if v_hi is not None and vals[m] is not None:
            diff = abs(vals[m] - v_hi)
            if diff > 0:
                digits = -float(log(diff, 10))
            else:
                digits = PREC
            print(f"{m:3d}  {digits:>14.1f}")
        else:
            print(f"{m:3d}  {'DIVERGED':>14s}")

    # ── Wallis product connection ─────────────────────────────────────────
    print(f"\n{'='*80}")
    print("WALLIS PRODUCT CONNECTION")
    print("  val(m) = (2/pi) * prod_{i=1}^{m} 2i/(2i-1)")
    print("  This is (2/pi) * 4^m / C(2m,m)  [partial Wallis products]")
    print()
    print("  The S^(m) family is NOT a family of new transcendentals.")
    print("  Every S^(m) is a RATIONAL MULTIPLE of 1/pi.")
    print("  The 'shift operator' m -> m+1 multiplies by 2(m+1)/(2m+1).")
    print()
    print("  Closed form:  val(m) = 2^{2m+1} / (pi * C(2m,m))")
    print(f"\n{sep}")
    print("  ALL TESTS COMPLETE")
    print(sep)


if __name__ == "__main__":
    main()
