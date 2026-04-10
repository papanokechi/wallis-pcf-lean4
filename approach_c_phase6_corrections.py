#!/usr/bin/env python3
"""
Approach C Phase 6 — Address reviewer corrections + falling-factorial ansatz

Fixes:
  1. Classification: Laguerre-type (sqrt(|a_n|) ~ sqrt(2)*n), not "between Wilson"
  2. Stieltjes: sign-change of a_n at n=(2m+1)/2 is the real obstruction
  3. α(m) clarification: Pincherle decomposition coefficient
  4. Falling-factorial ansatz for f_n^(m)
"""
from fractions import Fraction
from mpmath import (mp, mpf, pi, gamma, sqrt, nstr, log, rf, binomial, fac)

mp.dps = 120

# ============================================================================
# HELPERS
# ============================================================================

def val_exact(m):
    return 2 * gamma(m + 1) / (sqrt(pi) * gamma(m + mpf('0.5')))

def pcf_pq(m, N):
    m = mpf(m)
    pp, pc = mpf(1), mpf(1)
    qp, qc = mpf(0), mpf(1)
    ps, qs = [pc], [qc]
    for n in range(1, N + 1):
        an = -mpf(n) * (2*n - (2*m + 1))
        bn = mpf(3*n + 1)
        pn = bn*pc + an*pp; qn = bn*qc + an*qp
        pp, pc = pc, pn; qp, qc = qc, qn
        ps.append(pc); qs.append(qc)
    return ps, qs

def compute_minimal(m, N):
    f = [mpf(0)] * (N + 2)
    f[N] = mpf(1); f[N - 1] = mpf(0)
    for n in range(N, 1, -1):
        an = -mpf(n) * (2*n - (2*m + 1))
        bn = mpf(3*n + 1)
        if an != 0:
            f[n - 2] = (f[n] - bn * f[n - 1]) / an
        else:
            f[n - 2] = mpf(0)
    if f[0] != 0:
        c = f[0]
        for i in range(N + 1):
            f[i] /= c
    return f


# ============================================================================
# PART 1: Corrected classification
# ============================================================================

def part1_classification():
    print("=" * 78)
    print("PART 1: Corrected classification of the PCF family")
    print("=" * 78)
    print("""
CORRECTED CLASSIFICATION:

The PCF has a_n = -n(2n-(2m+1)) ~ -2n² and b_n = 3n+1 ~ 3n.

In Jacobi matrix form J with off-diagonal sqrt(|a_n|) ~ sqrt(2)·n
and diagonal b_n ~ 3n:
  - Off-diagonal growth: O(n)  — Laguerre-type, NOT Nevai class M(0,0)
  - This is comparable to Laguerre polynomials (off-diagonal ~ n/2)
  - NOT comparable to Wilson polynomials (which have O(n²) off-diagonal)

The previous claim "between classical and Wilson" was imprecise.
The correct statement: the Jacobi matrix has Laguerre-type growth
(unbounded off-diagonal entries growing linearly in n), placing it
outside the Nevai class but within the Laguerre universality class.

It is NOT of hypergeometric type in the Nikiforov-Uvarov sense because
the coefficient a_n is quadratic (not linear) in n, while b_n is linear.
Classical OPS have a_n = O(n) and b_n = O(n) (both linear).
""")

    # Verify the growth rates
    print("--- Growth rate verification ---")
    m = 0
    print(f"  {'n':>5}  {'|a_n|':>12}  {'sqrt(|a_n|)':>12}  {'b_n':>8}  {'|a_n|/b_n':>10}")
    for n in [10, 50, 100, 500]:
        an = abs(-n * (2*n - 1))
        bn = 3*n + 1
        print(f"  {n:5d}  {an:12d}  {sqrt(mpf(an)):>12.2f}  {bn:8d}  {mpf(an)/bn:>10.2f}")

    print("""
  sqrt(|a_n|)/n → sqrt(2) ≈ 1.414   (Laguerre-type off-diagonal)
  |a_n|/b_n → 2n/3                   (unbounded: NOT Nevai class)
""")


# ============================================================================
# PART 2: Corrected Stieltjes argument
# ============================================================================

def part2_stieltjes():
    print("=" * 78)
    print("PART 2: Corrected Stieltjes moment obstruction")
    print("=" * 78)
    print("""
CORRECTED ARGUMENT:

For a Stieltjes-type CF (S-fraction), we need ALL a_n > 0 (i.e., the
CF partial numerators are positive; equivalently, the Jacobi matrix has
real off-diagonal entries).

Our a_m(n) = -n(2n-(2m+1)):
  - For n < (2m+1)/2 (i.e. n ≤ m): a_m(n) = -n·(negative) > 0
  - For n > (2m+1)/2 (i.e. n ≥ m+1): a_m(n) = -n·(positive) < 0

Sign change occurs at n = (2m+1)/2:
  m=0: sign change at n=0.5, so a_0(n) < 0 for all n ≥ 1  (sign-definite!)
  m=1: a_1(1) = +1 > 0, a_1(n) < 0 for n ≥ 2  (NOT sign-definite)
  m=2: a_2(1) = +3, a_2(2) = +2 > 0, a_2(n) < 0 for n ≥ 3

The Stieltjes moment interpretation requires ALL a_n to have the same sign.
This holds only for m=0 (where all a_n < 0, giving a proper S-fraction).
For m ≥ 1, the sequence a_n changes sign, so the CF is NOT an S-fraction
and the classical Stieltjes integral representation does not apply.

This is more precise than saying "a_m(1) > 0" — the real obstruction is
that the sign sequence is not constant.
""")

    print("--- Sign pattern of a_m(n) ---")
    for m in range(5):
        signs = []
        for n in range(1, 10):
            a = -n * (2*n - (2*m + 1))
            signs.append('+' if a > 0 else '-' if a < 0 else '0')
        change = (2*m + 1) / 2
        print(f"  m={m}: [{', '.join(signs[:8])}]  sign change at n={(2*m+1)/2}")


# ============================================================================
# PART 3: Clear α(m) statement
# ============================================================================

def part3_alpha_clarification():
    print("\n" + "=" * 78)
    print("PART 3: Precise statement of α(m)")
    print("=" * 78)
    print("""
PRECISE DEFINITION:

The three-term recurrence y_n = (3n+1)·y_{n-1} - n(2n-2m-1)·y_{n-2}
has two linearly independent solution families:
  - p_n^(m): the dominant solution (numerator convergents, p_{-1}=1, p_0=1)
  - f_n^(m): the minimal solution (backward recurrence, normalized f_0=1)

The denominator convergents q_n^(m) (with q_{-1}=0, q_0=1) decompose as:
  q_n^(m) = α(m)·p_n^(m) + β(m)·f_n^(m)

where α(m) and β(m) are constants determined by the initial conditions.

From q_0 = 1: α(m) + β(m) = 1.

Since f_n^(m)/p_n^(m) → 0 as n → ∞ (minimal vs dominant):
  q_n^(m)/p_n^(m) → α(m)

Therefore:  val(m) = lim p_n/q_n = 1/α(m).

The FORMULA:  α(m) = (π/2)·(1/2)_m/m!

This is:
  - The asymptotic ratio q_n/p_n as n → ∞
  - The reciprocal of the CF value: α(m) = 1/val(m)
  - Equal to ∫₀^{π/2} sin^{2m}(x) dx  (the Wallis integral)
  - Equal to (π/2)·₂F₁(-m, 1/2; 1; 1)  (Chu-Vandermonde)
""")

    # Verify all statements
    print("--- Verification ---")
    N = 300
    for m in range(6):
        ps, qs = pcf_pq(m, N)
        alpha_num = qs[-1] / ps[-1]  # q_n/p_n → α(m)
        alpha_formula = (pi/2) * rf(mpf('0.5'), m) / gamma(m + 1)
        err = abs(alpha_num - alpha_formula)
        dp = -int(float(log(err + mpf('1e-200'), 10))) if err > 0 else 120
        print(f"  m={m}: q_N/p_N = {nstr(alpha_num,16)}, "
              f"(π/2)(1/2)_m/m! = {nstr(alpha_formula,16)}, {dp} dp")


# ============================================================================
# PART 4: Falling-factorial ansatz for f_n^(m)
# ============================================================================

def part4_falling_factorial():
    print("\n" + "=" * 78)
    print("PART 4: Falling-factorial ansatz for the minimal solution f_n^(m)")
    print("=" * 78)

    print("""
ANSATZ: f_n^(m) = Σ_{k=0}^{K} c_k(m) · C(n,k)

where C(n,k) = n!/(k!(n-k)!) is the falling-factorial basis.

This is natural because C(n,k) satisfies:
  C(n,k) = C(n-1,k) + C(n-1,k-1)
which often simplifies three-term recurrences.

Strategy: compute f_n^(m) for n=0,...,30 via backward recurrence,
then expand in the falling-factorial basis and look for patterns in c_k(m).
""")

    N_back = 300
    N_use = 25  # use first 25+1 values

    for m in range(5):
        f = compute_minimal(m, N_back)
        f_vals = [f[n] for n in range(N_use + 1)]

        # Expand in falling-factorial (binomial) basis:
        # f_n = Σ c_k * C(n,k). Use forward differences:
        # c_k = Δ^k f_0 / k!  where Δ is the forward difference operator.
        # Actually c_k = Δ^k[f](0) where Δ^k is the k-th forward difference.

        # Compute forward differences
        diffs = list(f_vals)
        coeffs = [diffs[0]]  # c_0 = f_0 = 1
        for k in range(1, N_use + 1):
            diffs = [diffs[i+1] - diffs[i] for i in range(len(diffs) - 1)]
            coeffs.append(diffs[0])  # Δ^k f_0

        # c_k = Δ^k f_0 (coefficient of C(n,k) = n*(n-1)*...*(n-k+1)/k!)
        # Actually f_n = Σ c_k * C(n,k) means c_k = Δ^k f_0.

        if m <= 2:
            print(f"\n  m={m}: Forward difference coefficients c_k = Δ^k f_0:")
            for k in range(min(12, len(coeffs))):
                print(f"    k={k:2d}: c_k = {nstr(coeffs[k], 14)}")

        # Check: do the coefficients decay? Are they eventually zero?
        # If f_n is a polynomial of degree d, then c_k = 0 for k > d.
        significant = sum(1 for c in coeffs if abs(c) > mpf('1e-50'))
        max_k = 0
        for k in range(len(coeffs)-1, -1, -1):
            if abs(coeffs[k]) > mpf('1e-50'):
                max_k = k
                break

        print(f"  m={m}: significant coefficients up to k={max_k} "
              f"(total {significant} nonzero)")

    # The key question: do the c_k have a closed form in both k and m?
    print("""
--- Analysis of c_k structure ---

If all c_k are nonzero (as appears), then f_n^(m) is NOT a polynomial
in the falling-factorial basis either — it's a genuine infinite series
in binomial coefficients. This is consistent with f_n being the
minimal solution of an infinite-order recurrence (when expanded as
a generating function).

Let's check the RATIO c_{k+1}/c_k for each m:
""")

    for m in range(4):
        f = compute_minimal(m, N_back)
        f_vals = [f[n] for n in range(N_use + 1)]
        diffs = list(f_vals)
        coeffs = [diffs[0]]
        for k in range(1, N_use + 1):
            diffs = [diffs[i+1] - diffs[i] for i in range(len(diffs) - 1)]
            coeffs.append(diffs[0])

        print(f"  m={m}: c_(k+1)/c_k ratios:")
        for k in range(min(10, len(coeffs) - 1)):
            if abs(coeffs[k]) > mpf('1e-80'):
                r = coeffs[k+1] / coeffs[k]
                # Check if ratio is a simple rational function of k
                # Try: r = (ak+b)/(ck+d) for small integers
                print(f"    k={k:2d}: c_(k+1)/c_k = {nstr(r, 14)}", end="")

                # Try to identify as rational function of k
                found = False
                for a in range(-5, 6):
                    for b in range(-10, 11):
                        for c in range(-5, 6):
                            for d in range(-10, 11):
                                if c * k + d == 0:
                                    continue
                                trial = mpf(a * k + b) / (c * k + d)
                                if abs(r - trial) < mpf('1e-40'):
                                    print(f"  = ({a}k+{b})/({c}k+{d})", end="")
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
                    if found:
                        break
                print()

    # Alternative: try f_n as a ₂F₁ or ₁F₁ with n-dependent parameters
    print("""
--- Alternative: test if f_n^(m) = ₂F₁(a(n,m), b(n,m); c(n,m); z(m)) ---

For fixed m, the minimal solution might be expressible as a hypergeometric
function evaluated at a specific argument with n-dependent parameters.

A classic case: f_n = ₂F₁(-n, b; c; z) is a terminating series (polynomial in z).
But our f_n is not a polynomial in anything obvious.

Another case: f_n = ₁F₁(a; b+n; z) — confluent hypergeometric with shifted b.
""")

    # Test: f_n^(0) vs various hypergeometric evaluations
    m = 0
    f = compute_minimal(m, N_back)

    print(f"  Testing f_n^(0) against known functions:")
    for n in range(8):
        fn = f[n]
        # Test against Gamma quotients
        # Trial: f_n = Γ(n+α)/Γ(n+β) · Γ(β)/Γ(α) for some α,β
        # Then f_n/f_{n-1} = (n+α-1)/(n+β-1)
        # From Part 1 of phase 4: f_n/f_{n-1} ≈ n + 0.0734*n^{0.5} + ...
        # This doesn't match Γ-quotient behavior (which gives ratio → 1)
        pass

    # Compute the GENERATING FUNCTION F(x) = Σ f_n x^n and check if it
    # satisfies a known ODE
    print("  Generating function coefficients f_n^(0) for n=0..15:")
    f0 = compute_minimal(0, N_back)
    for n in range(16):
        print(f"    f_{n} = {nstr(f0[n], 18)}")

    # Check: F(x) satisfies x²(1-x)²·F'' + x(...)·F' + ... = 0?
    # The recurrence y_n = (3n+1)y_{n-1} - n(2n-1)y_{n-2} translates to:
    # Σ y_n x^n = Σ (3n+1)y_{n-1}x^n - Σ n(2n-1)y_{n-2}x^n
    # F(x) = x·(3xD+1)F(x)/... this is complicated but can be turned into an ODE.

    # Actually, the standard theory: if y_n satisfies
    # c₂(n)y_{n+1} + c₁(n)y_n + c₀(n)y_{n-1} = 0
    # with c_i polynomials, then F(x) = Σ y_n x^n satisfies a LINEAR ODE
    # whose order equals max(deg c_i) + 1.
    # Here: c₂=1, c₁=-(3n+4), c₀=-(n+1)(2n+1-2m)  (shifting index by 1)
    # deg c₂=0, deg c₁=1, deg c₀=2. So the ODE is order max(0,1,2)+1 = 3.
    print("""
  The recurrence has polynomial coefficients of degrees (0, 1, 2),
  so the generating function F(x) = Σ f_n x^n satisfies a 3rd-order
  LINEAR ODE. This is consistent with f being non-hypergeometric
  (₂F₁ satisfies a 2nd-order ODE).
""")


# ============================================================================
# PART 5: Summary of corrections
# ============================================================================

def part5_summary():
    print("\n" + "=" * 78)
    print("SUMMARY OF CORRECTIONS")
    print("=" * 78)
    print("""
1. CLASSIFICATION (corrected):
   Previous: "nonclassical, between classical OPS and Wilson"
   Corrected: Laguerre-type growth (sqrt(|a_n|) ~ sqrt(2)·n),
   outside Nevai class M(0,0), not hypergeometric-type (Nikiforov-Uvarov).
   NOT comparable to Wilson (which has O(n²) off-diagonal).

2. STIELTJES OBSTRUCTION (corrected):
   Previous: "fails for m≥1 since a_m(1)=2m-1>0"
   Corrected: a_m(n) changes sign at n=(2m+1)/2. For m≥1, the sequence
   {a_m(n)}_{n≥1} is NOT sign-definite (positive for n≤m, negative for n≥m+1).
   Only m=0 gives a proper S-fraction with all a_n < 0.

3. α(m) CLARIFICATION:
   α(m) = lim_{n→∞} q_n^(m)/p_n^(m) = 1/val(m) = (π/2)·(1/2)_m/m!
   This is the coefficient of the dominant solution p_n in the decomposition
   q_n = α·p_n + β·f_n. It equals the Wallis integral ∫₀^{π/2} sin^{2m} dx.

4. MINIMAL SOLUTION f_n^(m):
   - Genuinely m-dependent (sympy proof: n!/(2n+1)!! fails for m>0)
   - Not polynomial in the falling-factorial basis (infinite series)
   - Generating function satisfies a 3rd-order linear ODE (not 2nd-order)
   - A closed form remains open; the falling-factorial expansion coefficients
     do not appear to satisfy a simple rational recurrence in k
""")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("*" * 78)
    print("*  APPROACH C PHASE 6: Reviewer corrections + falling-factorial")
    print("*" * 78)

    part1_classification()
    part2_stieltjes()
    part3_alpha_clarification()
    part4_falling_factorial()
    part5_summary()

    print("\n" + "=" * 78)
    print("PHASE 6 COMPLETE")
    print("=" * 78)
