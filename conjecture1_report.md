# Conjecture 1 Report: Closed Form for p_n(1)

## Statement

The Pi Family at m=1 has convergent numerators
p_n(1) = 1, 5, 33, 285, 3045, 38745, 571725, 9594585, ...

## Result

**Confirmed closed form:**

    p_n(1) = (2n-1)!! * (n^2 + 3n + 1)

Equivalently:

    p_n(1) = 2^n * (1/2)_n * (n^2 + 3n + 1)

where (1/2)_n is the Pochhammer symbol (rising factorial).

## Verification

Verified symbolically for n = 0..20 via the CF recurrence
p_n = (3n+1) p_{n-1} - n(2n-3) p_{n-2}.

## Pochhammer Decomposition Attempt

The quadratic n^2+3n+1 has discriminant 5 and irrational roots at
(-3 +/- sqrt(5))/2.  Systematic search over half-integer Pochhammer
templates with up to 3 upper parameters and 2 lower parameters found
**no** factorisation of p_n(1) as a standard hypergeometric term
(a1)_n (a2)_n ... / ((b1)_n ... n!) with rational parameters.

Over Q(sqrt(5)), we can write:

    p_n(1) = 2^n * (1/2)_n * (n + alpha)(n + beta)

where alpha = (3-sqrt(5))/2 ~ 0.382, beta = (3+sqrt(5))/2 ~ 2.618.

## Ratio Analysis

The ratio p_{n+1}/p_n satisfies:

    p_{n+1}/p_n = (2n+1)(n^2+5n+5) / (n^2+3n+1)

The presence of irreducible quadratics in this ratio confirms the series
is not a standard _pF_q over Q.

## Recommended Next Steps

1. **Generating function**: Seek a contour-integral or beta-integral
   representation that produces the product (2n-1)!!(n^2+3n+1) directly.

2. **Golden ratio connection**: The roots alpha*beta = 1, alpha+beta = 3
   connect to the golden ratio via alpha = 1+psi, beta = 1+phi.  Explore
   whether the recurrence relates to Fibonacci-Chebyshev orthogonal
   polynomials.

3. **Weight function**: Determine whether the recurrence
   (2n-1)u_n = (3n+1)u_{n-1} - n u_{n-2} admits a continuous weight
   function w(x) such that the solutions are moments of w.

4. **General m conjecture**: If p_n(m) = (2n-1)!! * Q_m(n) where Q_m is a
   polynomial of degree 2m in n, characterise Q_m and prove the pattern.
