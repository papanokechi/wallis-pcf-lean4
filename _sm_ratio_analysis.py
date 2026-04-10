"""
S^(m) Family: Inter-Family Ratio Analysis & Structural Characterization.

Computes S^(m) for m=0..15 at high precision, then analyzes:
  1. Value table (50 digits)
  2. Inter-family ratios S^(m)/S^(m-1)
  3. Rational approximation of ratios
  4. Second-order ratio structure
  5. Approach to unity & asymptotic form
  6. Convergence rate R(m) as function of m
  7. mpmath identify() on ratios and differences
"""
from __future__ import annotations
from mpmath import mp, mpf, pi, log, nstr, identify, sqrt, gamma, zeta
import mpmath as mpm

PREC = 200
DEPTH = 3000
MAX_M = 15


def _eval_pi_family(m, depth=DEPTH):
    """Compute S^(m) = CF value with a(n)=-n(2n-2m-1), b(n)=3n+1."""
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
    mp.dps = PREC + 20

    sep = "=" * 76
    print(sep)
    print("  S^(m) FAMILY: INTER-FAMILY RATIOS & STRUCTURE")
    print(sep)

    # ── Compute S^(m) for m=0..MAX_M ──────────────────────────────────────
    sm = {}
    for m in range(MAX_M + 1):
        sm[m] = _eval_pi_family(m, depth=DEPTH)
        if sm[m] is None:
            print(f"  WARNING: S^({m}) diverged at depth {DEPTH}")

    # ── TABLE 1: Values ───────────────────────────────────────────────────
    print()
    print("TABLE 1: S^(m) values (50 digits)")
    hdr = f"{'m':>3s}  {'k=2m+1':>6s}  {'S^(m)':>55s}"
    print(hdr)
    print("-" * len(hdr))
    for m in range(min(MAX_M + 1, 12)):
        print(f"{m:3d}  {2*m+1:6d}  {nstr(sm[m], 50):>55s}")

    # ── Verify S^(0) = 4/pi ──────────────────────────────────────────────
    print()
    print("VERIFICATION: S^(0) vs 4/pi")
    diff0 = abs(sm[0] - mpf(4) / pi)
    d0 = -float(log(diff0 + mpf(10) ** (-PREC), 10))
    print(f"  |S^(0) - 4/pi| = {nstr(diff0, 5)}  ({d0:.1f} stable digits)")

    # ── TABLE 2: Inter-family ratios ─────────────────────────────────────
    print()
    print("TABLE 2: INTER-FAMILY RATIOS  S^(m) / S^(m-1)")
    hdr2 = f"{'m':>3s}  {'Ratio (50 digits)':>55s}  {'~float':>14s}"
    print(hdr2)
    print("-" * len(hdr2))
    ratios = []
    for m in range(1, MAX_M + 1):
        r = sm[m] / sm[m - 1]
        ratios.append(r)
        print(f"{m:3d}  {nstr(r, 50):>55s}  {float(r):>14.12f}")

    # ── TABLE 3: Rational approximation ──────────────────────────────────
    print()
    print("TABLE 3: RATIONAL APPROXIMATION OF RATIOS (best p/q, |q| <= 200)")
    hdr3 = f"{'m':>3s}  {'p/q':>12s}  {'Residual':>18s}  {'Match digits':>12s}"
    print(hdr3)
    print("-" * len(hdr3))
    for i, r in enumerate(ratios):
        m = i + 1
        best_p, best_q, best_d = 0, 1, 0
        for q in range(1, 201):
            p_approx = r * q
            p_round = int(round(float(p_approx)))
            if p_round == 0:
                continue
            residual = abs(p_approx - p_round)
            if residual > 0:
                d = float(-log(residual / abs(p_round), 10))
                if d > best_d:
                    best_d = d
                    best_p, best_q = p_round, q
        frac_str = f"{best_p}/{best_q}"
        res = abs(r - mpf(best_p) / best_q)
        print(f"{m:3d}  {frac_str:>12s}  {nstr(res, 8):>18s}  {best_d:>12.1f}")

    # ── TABLE 4: Differences from 1 & asymptotic form ────────────────────
    print()
    print("TABLE 4: S^(m)/S^(m-1) - 1  (approach to unity)")
    hdr4 = f"{'m':>3s}  {'ratio - 1':>20s}  {'(ratio-1)*m':>20s}  {'(ratio-1)*m^2':>20s}"
    print(hdr4)
    print("-" * len(hdr4))
    for i, r in enumerate(ratios):
        m = i + 1
        d = r - 1
        print(f"{m:3d}  {float(d):>+20.15f}  {float(d * m):>+20.15f}  {float(d * m * m):>+20.15f}")

    # ── TABLE 5: Second-order ratio r(m)/r(m-1) ─────────────────────────
    print()
    print("TABLE 5: SECOND-ORDER RATIOS  r(m)/r(m-1)")
    for i in range(1, len(ratios)):
        r2 = ratios[i] / ratios[i - 1]
        print(f"  r({i+1})/r({i}) = {float(r2):.15f}")

    # ── TABLE 6: Convergence rate R(m) ───────────────────────────────────
    print()
    print("TABLE 6: CONVERGENCE RATE  (digits gained per 1000 depth)")
    hdr6 = f"{'m':>3s}  {'Digits @2000':>14s}  {'Digits @3000':>14s}  {'Rate/1000':>12s}"
    print(hdr6)
    print("-" * len(hdr6))
    for m in range(min(MAX_M + 1, 12)):
        v1 = _eval_pi_family(m, depth=2000)
        v2 = _eval_pi_family(m, depth=3000)
        if v1 is not None and v2 is not None:
            diff = abs(v1 - v2)
            if diff > 0:
                digits = -float(log(diff, 10))
            else:
                digits = PREC
            # Also check 1000 vs 2000
            v0 = _eval_pi_family(m, depth=1000)
            if v0 is not None:
                diff01 = abs(v0 - v1)
                d01 = -float(log(diff01, 10)) if diff01 > 0 else PREC
            else:
                d01 = 0
            rate = digits - d01  # digits gained going from 1k->2k vs 2k->3k
            print(f"{m:3d}  {d01:>14.1f}  {digits:>14.1f}  {rate:>12.1f}")

    # ── TABLE 7: mpmath identify() on ratios and S^(m) ──────────────────
    print()
    print("TABLE 7: mpmath identify() attempts")
    old_dps = mp.dps
    mp.dps = 30
    for i, r in enumerate(ratios[:8]):
        m = i + 1
        ident_r = identify(r)
        ident_s = identify(float(sm[m]))
        print(f"  S^({m})/S^({m-1}) = {ident_r if ident_r else '(no closed form)'}")
        print(f"  S^({m})           = {ident_s if ident_s else '(no closed form)'}")
    mp.dps = old_dps

    # ── TABLE 8: Check for polynomial/hypergeometric pattern ─────────────
    print()
    print("TABLE 8: S^(m) * pi / 4  (check if S^(m) = rational * 4/pi)")
    for m in range(12):
        v = sm[m] * pi / 4
        print(f"  S^({m:2d}) * pi/4 = {nstr(v, 50)}")

    print()
    print(sep)
    print("  ANALYSIS COMPLETE")
    print(sep)


if __name__ == "__main__":
    main()
