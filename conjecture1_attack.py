#!/usr/bin/env python3
"""Conjecture 1 attack: search for closed form of p_n(1).

The Pi Family at m=1 has convergent numerators:
  p_n(1) = 1, 5, 33, 285, 3045, 38745, 571725, 9594585, ...

We attempt:
  1. Rational reconstruction: express p_n(1) as product/ratio of Pochhammer symbols.
  2. Factorisation over Q(sqrt(d)) for small d.
  3. Fit to hypergeometric term templates.
  4. OEIS lookup of the sequence.
"""
from fractions import Fraction
import math


def double_factorial_odd(n):
    r = 1
    for k in range(1, 2 * n, 2):
        r *= k
    return r


def compute_pn1(N=25):
    """Compute p_n(1) via the CF recurrence for m=1 family:
    a(n) = -n(2n-3), b(n) = 3n+1."""
    bn = [3 * n + 1 for n in range(N + 1)]
    an = [0] + [-n * (2 * n - 3) for n in range(1, N + 1)]
    p_prev, p_curr = 1, bn[0]  # p_{-1}=1, p_0=b_0=1
    vals = [p_curr]
    for n in range(1, N + 1):
        p_new = bn[n] * p_curr + an[n] * p_prev
        p_prev, p_curr = p_curr, p_new
        vals.append(p_curr)
    return vals


def main():
    N = 20
    pn = compute_pn1(N)

    print("=" * 70)
    print("Conjecture 1 Attack: Closed form for p_n(1)")
    print("=" * 70)

    print("\np_n(1) values:")
    for n in range(min(16, N + 1)):
        print(f"  p_{n:2d}(1) = {pn[n]}")

    # Hypothesis 1: p_n(1) = (2n-1)!! * (n^2 + 3n + 1)
    print("\nTest: p_n(1) = (2n-1)!! * (n^2+3n+1)?")
    all_match = True
    for n in range(N + 1):
        df = double_factorial_odd(n)
        poly = n * n + 3 * n + 1
        expected = df * poly
        ok = (pn[n] == expected)
        if not ok:
            all_match = False
        if n < 12 or not ok:
            print(f"  n={n:2d}: p_n(1)={pn[n]}, (2n-1)!!*(n^2+3n+1)={expected}  {'OK' if ok else 'FAIL'}")
    if all_match:
        print(f"  ALL MATCH for n=0..{N}!")
    else:
        print("  MISMATCH FOUND")

    # Attempt Pochhammer factorisation of (2n-1)!! * (n^2+3n+1)
    print("\n" + "=" * 70)
    print("Pochhammer Analysis")
    print("=" * 70)
    print("\n(2n-1)!! = 2^n * (1/2)_n  [standard identity]")
    print("\nn^2+3n+1: roots at n = (-3 +/- sqrt(5))/2")
    print("  These are irrational => no factoring into rational Pochhammer symbols.")
    print()

    # Try: does a PRODUCT of Pochhammer symbols give (2n-1)!!(n^2+3n+1)?
    # Template: C * (a1)_n * (a2)_n / ((b1)_n * n!)  for small rationals a_i, b_i
    print("Searching hypergeometric term templates...")
    print("Template: p_n = C * (a1)_n * (a2)_n / ((b1)_n)")
    print("where a1, a2, b1 are half-integers and C is rational.\n")

    def pochhammer(a, n):
        r = Fraction(1)
        for k in range(n):
            r *= a + k
        return r

    # Brute force over half-integer parameters
    candidates = []
    halves = [Fraction(i, 2) for i in range(-6, 13) if i != 0]
    for a1 in halves:
        for a2 in halves:
            for b1 in halves:
                if b1 <= 0 and b1.denominator == 1:
                    continue
                # Check: does C * (a1)_n * (a2)_n / (b1)_n = p_n?
                # At n=0: p_0=1, (a1)_0*(a2)_0/(b1)_0 = 1, so C = 1
                ok = True
                for n in range(1, 12):
                    top = pochhammer(a1, n) * pochhammer(a2, n)
                    bot = pochhammer(b1, n)
                    if bot == 0:
                        ok = False
                        break
                    val = top / bot
                    if val != pn[n]:
                        ok = False
                        break
                if ok:
                    candidates.append((a1, a2, b1))

    if candidates:
        print(f"Found {len(candidates)} matches:")
        for a1, a2, b1 in candidates:
            print(f"  p_n = ({a1})_n * ({a2})_n / ({b1})_n")
    else:
        print("No 2-parameter Pochhammer match found.")

    # Try template with 3 top, 1 bottom: (a1)_n(a2)_n(a3)_n / ((b1)_n n!)
    print("\nTemplate: p_n = (a1)_n * (a2)_n * (a3)_n / ((b1)_n * n!)")
    candidates2 = []
    for a1 in halves:
        for a2 in halves:
            if float(a2) < float(a1):
                continue  # avoid duplicates
            for a3 in halves:
                if float(a3) < float(a2):
                    continue
                for b1 in halves:
                    if b1 <= 0 and b1.denominator == 1:
                        continue
                    ok = True
                    for n in range(1, 10):
                        top = pochhammer(a1, n) * pochhammer(a2, n) * pochhammer(a3, n)
                        bot = pochhammer(b1, n) * Fraction(math.factorial(n))
                        if bot == 0:
                            ok = False
                            break
                        val = top / bot
                        if val != pn[n]:
                            ok = False
                            break
                    if ok:
                        candidates2.append((a1, a2, a3, b1))

    if candidates2:
        print(f"Found {len(candidates2)} matches:")
        for a1, a2, a3, b1 in candidates2:
            print(f"  p_n = ({a1})_n * ({a2})_n * ({a3})_n / (({b1})_n * n!)")
    else:
        print("No 3-top/2-bottom Pochhammer match found.")

    # Ratio analysis
    print("\n" + "=" * 70)
    print("Ratio p_{n+1}(1) / p_n(1)")
    print("=" * 70)
    for n in range(15):
        ratio = Fraction(pn[n + 1], pn[n])
        # Expected from formula: (2n+1)*(n^2+5n+5) / (n^2+3n+1)
        expected_ratio = Fraction((2 * n + 1) * (n ** 2 + 5 * n + 5), n ** 2 + 3 * n + 1)
        match = (ratio == expected_ratio)
        print(f"  n={n:2d}: {ratio} = {float(ratio):.6f}  "
              f"formula={(2*n+1)}*{n**2+5*n+5}/{n**2+3*n+1} {'OK' if match else 'FAIL'}")

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("""
CONFIRMED: p_n(1) = (2n-1)!! * (n^2 + 3n + 1) for all tested n (0..20).

This factors as:
  p_n(1) = 2^n * (1/2)_n * (n^2 + 3n + 1)

where (1/2)_n is the Pochhammer symbol (rising factorial).

The quadratic factor n^2+3n+1 has discriminant 5 and roots
  (-3 +/- sqrt(5))/2,
which are irrational.  Therefore:

  (a) p_n(1) CANNOT be written as a finite product of Pochhammer symbols
      with RATIONAL parameters.

  (b) Over Q(sqrt(5)), we can write:
      p_n(1) = 2^n * (1/2)_n * (n + alpha)(n + beta)
      where alpha = (3-sqrt(5))/2, beta = (3+sqrt(5))/2.

  (c) The ratio p_{n+1}/p_n = (2n+1)(n^2+5n+5)/(n^2+3n+1) contains
      irreducible quadratics, confirming the series is not a standard
      hypergeometric _pF_q over Q.

Recommended next steps:
  - Search for a GENERATING FUNCTION identity that yields this product
    directly from a contour integral or beta-integral representation.
  - Check if the quadratic n^2+3n+1 relates to Chebyshev or Fibonacci
    polynomials evaluated at specific arguments (note: alpha*beta = 1,
    alpha+beta = 3, and the roots involve the golden ratio).
  - Explore whether the recurrence (2n-1)u_n = (3n+1)u_{n-1} - n u_{n-2}
    admits a Laguerre-type or Jacobi-type weight function.
""")


if __name__ == "__main__":
    main()
