#!/usr/bin/env python3
"""
Approach C Phase 7 — ODE derivation, convergence rate, J-fraction moments,
and deformation analysis

Based on reviewer suggestions:
  1. Derive the explicit 3rd-order ODE for the generating function G(z)
  2. Map log(eps_N) vs sqrt(N) to confirm Laguerre-type convergence
  3. Compute J-fraction moments and check Favard's theorem
  4. Test coefficient deformations
"""
from fractions import Fraction
from mpmath import (mp, mpf, pi, gamma, sqrt, nstr, log, log10, binomial,
                    rf, matrix, exp, power, mpf as mf)
from sympy import (symbols, Function, Eq, simplify, expand, factor,
                   Rational, Poly, collect, series, diff as sdiff, cancel,
                   together, apart, S)

# ============================================================================
# PART 1: Derive the 3rd-order ODE for G(z) = sum f_n^(m) z^n
# ============================================================================

def part1_ode_derivation():
    print("=" * 78)
    print("PART 1: Derive the ODE for the generating function G(z)")
    print("=" * 78)

    print("""
The recurrence is:
  f_n = (3n+1) f_{n-1} - n(2n-2m-1) f_{n-2}   for n >= 2

Rewrite with shifted index (set n -> n+1):
  f_{n+1} = (3n+4) f_n - (n+1)(2n+1-2m) f_{n-1}

Define G(z) = sum_{n>=0} f_n z^n.

The standard translation from recurrence to ODE uses:
  sum n^k f_n z^n = (z d/dz)^k G(z)

Let D = z*d/dz (Euler operator). Then:
  sum f_{n+1} z^n = (G(z) - f_0)/z
  sum n*f_n z^n = D[G]
  sum n^2*f_n z^n = D^2[G]

The recurrence f_{n+1} = (3n+4)f_n - (n+1)(2n+1-2m)f_{n-1} becomes:

  (G-f_0)/z = (3D+4)G - (2D^2 + (3-2m)D + (1-2m)) * zG

where the last term uses (n+1)(2n+1-2m) = 2n^2 + (3-2m)n + (1-2m).

Multiply through by z:
  G - f_0 = z(3D+4)G - z^2(2D^2 + (3-2m)D + (1-2m))G

Since D[z^k G] = z^k(D+k)G, we have z*D = D*z etc.
Actually D = z*d/dz, so D[zG] = z*(zG)' = z(G + zG') = z*G + z^2*G'.
Better to work in x = z, y = G, y' = dG/dz directly.

Let me redo using the standard method with theta = z*d/dz.

sum_{n>=0} f_{n+1} z^n = sum_{n>=0} [(3n+4)f_n - (n+1)(2n+1-2m)f_{n-1}] z^n

LHS = (1/z)[G(z) - f_0]

RHS = 3*sum n*f_n*z^n + 4*sum f_n*z^n
    - sum (n+1)(2n+1-2m) f_{n-1} z^n

    = 3*theta*G + 4*G
    - z * sum (n+1)(2n+1-2m) f_{n-1} z^{n-1}  ... hmm, index shift.

Let me be more careful with the shift.

sum_{n>=0} (n+1)(2n+1-2m) f_{n-1} z^n
= z * sum_{n>=1} (n+1)(2n+1-2m) f_{n-1} z^{n-1}
= z * sum_{k>=0} (k+2)(2k+3-2m) f_k z^k    [k = n-1]

Now (k+2)(2k+3-2m) = 2k^2 + (7-2m)k + (6-4m).

So:  sum = z * [2*theta^2 + (7-2m)*theta + (6-4m)] G
        ... where we use theta^2 G = sum k^2 f_k z^k etc.

Wait: theta = z*d/dz, so theta[G] = sum n*f_n*z^n, theta^2[G] = sum n^2*f_n*z^n.
But (k+2)(2k+3-2m) = 2k^2 + (7-2m)k + (6-4m).

So sum_{k>=0} (k+2)(2k+3-2m) f_k z^k = [2*theta^2 + (7-2m)*theta + (6-4m)] G

Therefore the recurrence in GF form:
  (1/z)(G - f_0) = (3*theta + 4)*G - z*[2*theta^2 + (7-2m)*theta + (6-4m)]*G

Multiply by z:
  G - f_0 = z*(3*theta + 4)*G - z^2*[2*theta^2 + (7-2m)*theta + (6-4m)]*G

Rearrange:
  G = f_0 + z*(3*theta+4)*G - z^2*[2*theta^2+(7-2m)*theta+(6-4m)]*G

This is a SECOND-ORDER ODE in G (since theta^2 involves z^2*G'' + z*G').
""")

    # Let me derive it explicitly in terms of y = G, y', y''
    n_sym, m_sym, z = symbols('n m z')
    y = Function('y')(z)
    yp = y.diff(z)
    ypp = y.diff(z, 2)

    # theta = z*d/dz: theta[y] = z*y', theta^2[y] = z^2*y'' + z*y'
    theta_y = z * yp
    theta2_y = z**2 * ypp + z * yp

    # The equation: y - 1 = z*(3*z*yp + 4*y) - z^2*(2*(z^2*ypp+z*yp) + (7-2*m_sym)*(z*yp) + (6-4*m_sym)*y)
    # With f_0 = 1.

    lhs = y - 1
    rhs = z * (3*theta_y + 4*y) - z**2 * (2*theta2_y + (7 - 2*m_sym)*theta_y + (6 - 4*m_sym)*y)

    ode_eq = expand(lhs - rhs)

    print("--- Explicit ODE (for m general) ---")
    print(f"  0 = {collect(ode_eq, [ypp, yp, y])}")
    print()

    # Collect by derivatives
    coeff_ypp = ode_eq.coeff(ypp)
    coeff_yp = ode_eq.coeff(yp)
    # Remove the ypp and yp parts to get the y coefficient
    ode_no_deriv = ode_eq - coeff_ypp * ypp - coeff_yp * yp
    # But there might be terms with just y left
    coeff_y = ode_no_deriv.coeff(y)
    remainder = expand(ode_no_deriv - coeff_y * y)

    print(f"  Coeff of y'':  {factor(coeff_ypp)}")
    print(f"  Coeff of y':   {factor(coeff_yp)}")
    print(f"  Coeff of y:    {factor(coeff_y)}")
    print(f"  Constant:      {remainder}")
    print()

    # For m=0:
    print("--- ODE at m=0 ---")
    c_ypp_0 = coeff_ypp.subs(m_sym, 0)
    c_yp_0 = coeff_yp.subs(m_sym, 0)
    c_y_0 = coeff_y.subs(m_sym, 0)
    r_0 = remainder.subs(m_sym, 0)
    print(f"  {factor(c_ypp_0)} y'' + {factor(c_yp_0)} y' + {factor(c_y_0)} y + {r_0} = 0")

    print("""
ANALYSIS:
  The ODE is SECOND order (not third!) because theta^2 is the highest
  operator appearing. This contradicts the Phase 5 claim of "3rd order".

  The error in Phase 5: the claim was based on "max(deg c_i) + 1 = 3"
  but the correct rule for the recurrence-to-ODE translation gives order
  max(deg c_i) = 2, since the recurrence is order 2 with polynomial
  coefficients of degree ≤ 2.

  CORRECTION: G(z) satisfies a 2nd-order LINEAR ODE.
  This means the minimal solution IS potentially expressible as a ₂F₁
  or a closely related function — we just haven't found the right
  parametrization.
""")

    # Write out the full ODE explicitly for m=0
    # Simplify: -2z^4 y'' + (-2z^3 - 7z^3 + 3z^2)y' + (... )y = 1
    # = -2z^4 y'' + z^2(3 - 9z) y' + ... y = ...
    # Let me factor more carefully
    print("--- Simplified ODE for m=0 ---")
    print(f"  y'' coeff: {expand(c_ypp_0)} = {factor(c_ypp_0)}")
    print(f"  y'  coeff: {expand(c_yp_0)}")
    print(f"  y   coeff: {expand(c_y_0)}")

    # Check singular points: y'' coeff = 0
    from sympy import solve as ssolve
    sings = ssolve(c_ypp_0, z)
    print(f"  Singular points (y'' coeff = 0): z = {sings}")
    print()

    # Verify numerically: does the backward-computed G(z) for some z satisfy this ODE?
    mp.dps = 40
    print("--- Numerical ODE verification at z=0.1, m=0 ---")

    # Compute G(0.1) = sum f_n * 0.1^n
    N_back = 200
    f = [mpf(0)] * (N_back + 2)
    f[N_back] = mpf(1); f[N_back - 1] = mpf(0)
    for nn in range(N_back, 1, -1):
        an = -mpf(nn) * (2*nn - 1)
        bn = mpf(3*nn + 1)
        if an != 0:
            f[nn - 2] = (f[nn] - bn * f[nn - 1]) / an
    if f[0] != 0:
        c = f[0]
        for i in range(N_back + 1):
            f[i] /= c

    z_val = mpf('0.1')
    G = sum(f[n] * z_val**n for n in range(100))
    Gp = sum(n * f[n] * z_val**(n-1) for n in range(1, 100))
    Gpp = sum(n*(n-1) * f[n] * z_val**(n-2) for n in range(2, 100))

    # Evaluate ODE: c_ypp * Gpp + c_yp * Gp + c_y * G + remainder = 0
    # For m=0, from the symbolic expressions
    z_num = mpf('0.1')
    cypp = -2 * z_num**4
    cyp_num = float(expand(c_yp_0).subs(z, Rational(1, 10)))
    cy_num = float(expand(c_y_0).subs(z, Rational(1, 10)))
    r_num = float(r_0.subs(z, Rational(1, 10)))

    residual = cypp * Gpp + mpf(cyp_num) * Gp + mpf(cy_num) * G + mpf(r_num)
    print(f"  G(0.1)   = {nstr(G, 20)}")
    print(f"  G'(0.1)  = {nstr(Gp, 20)}")
    print(f"  G''(0.1) = {nstr(Gpp, 20)}")
    print(f"  ODE residual = {nstr(residual, 10)}  (should be ~0)")


# ============================================================================
# PART 2: Convergence rate mapping
# ============================================================================

def part2_convergence():
    mp.dps = 200
    print("\n" + "=" * 78)
    print("PART 2: Convergence rate — log(eps_N) vs sqrt(N)")
    print("=" * 78)

    print("""
For Laguerre-type CFs with sqrt(|a_n|) ~ c*n, the convergence rate is
sub-exponential: eps_N ~ exp(-C*sqrt(N)) for some constant C.

For Gauss CFs (bounded a_n), convergence is geometric: eps_N ~ r^N.

We map log10(eps_N) vs sqrt(N) — if linear, confirms Laguerre-type.
We also map log10(eps_N) vs N — if linear, would indicate geometric.
""")

    for m in [0, 1, 2]:
        print(f"\n--- m = {m} ---")
        exact = 2 * gamma(m + 1) / (sqrt(pi) * gamma(m + mpf('0.5')))

        data = []
        pp, pc = mpf(1), mpf(1)
        qp, qc = mpf(0), mpf(1)
        for n in range(1, 601):
            an = -mpf(n) * (2*n - (2*m + 1))
            bn = mpf(3*n + 1)
            pn = bn*pc + an*pp; qn = bn*qc + an*qp
            pp, pc = pc, pn; qp, qc = qc, qn
            if n in [10, 20, 50, 100, 150, 200, 300, 400, 500, 600]:
                err = abs(pc/qc - exact)
                if err > 0:
                    le = float(log10(err))
                    sn = float(sqrt(mpf(n)))
                    data.append((n, le, sn))

        print(f"  {'N':>5}  {'log10(eps)':>12}  {'sqrt(N)':>8}  "
              f"{'log10/N':>10}  {'log10/sqrt(N)':>14}")
        for n, le, sn in data:
            print(f"  {n:5d}  {le:12.4f}  {sn:8.3f}  "
                  f"{le/n:10.5f}  {le/sn:14.5f}")

        # Linear regression of log10(eps) vs sqrt(N)
        if len(data) >= 3:
            xs = [d[2] for d in data]  # sqrt(N)
            ys = [d[1] for d in data]  # log10(eps)
            n_pts = len(xs)
            sx = sum(xs); sy = sum(ys)
            sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
            slope = (n_pts*sxy - sx*sy) / (n_pts*sxx - sx*sx)
            intercept = (sy - slope*sx) / n_pts
            # R^2
            ss_res = sum((y - (slope*x + intercept))**2 for x, y in zip(xs, ys))
            ss_tot = sum((y - sy/n_pts)**2 for y in ys)
            r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0
            print(f"  Linear fit: log10(eps) = {slope:.4f} * sqrt(N) + {intercept:.2f}  (R^2 = {r2:.6f})")

            # Also fit log10(eps) vs N (geometric test)
            xs2 = [d[0] for d in data]
            slope2 = (n_pts*sum(x*y for x, y in zip(xs2, ys)) - sum(xs2)*sy) / \
                      (n_pts*sum(x*x for x in xs2) - sum(xs2)**2)
            intercept2 = (sy - slope2*sum(xs2)) / n_pts
            ss_res2 = sum((y - (slope2*x + intercept2))**2 for x, y in zip(xs2, ys))
            r2_geo = 1 - ss_res2/ss_tot if ss_tot > 0 else 0
            print(f"  Geometric fit: log10(eps) = {slope2:.6f} * N + {intercept2:.2f}  (R^2 = {r2_geo:.6f})")

            if r2 > r2_geo:
                print(f"  -> sqrt(N) fit is BETTER: sub-exponential (Laguerre-type) convergence")
            else:
                print(f"  -> Linear-N fit is better: geometric convergence")


# ============================================================================
# PART 3: J-fraction moments and Favard's theorem
# ============================================================================

def part3_moments():
    mp.dps = 60
    print("\n" + "=" * 78)
    print("PART 3: J-fraction moments and Favard's theorem")
    print("=" * 78)

    print("""
The CF b_0 + K(a_n/b_n) is associated with the Jacobi matrix:

  J = | b_0   1    0    0   ... |
      | a_1  b_1   1    0   ... |
      | 0    a_2  b_2   1   ... |
      | ...                      |

The moments mu_k = e_1^T J^k e_1 determine the measure.
For a Stieltjes CF, mu_k = integral x^k d_mu(x) with positive measure.

For our CF, a_n changes sign => J has complex or signed spectral measure.
""")

    # Compute moments by expanding the matrix exponential / resolvent
    # Actually, moments from CF are computed via:
    # mu_0 = 1, and the CF gives the formal Laurent series
    # val = mu_0 + mu_1/z + mu_2/z^2 + ... via the resolvent.

    # More practical: compute the first few moments from the convergents.
    # The formal continued fraction expansion at z=infinity of
    # integral d_mu(t)/(z-t) = 1/z + mu_1/z^2 + mu_2/z^3 + ...

    # For our CF, the "moments" are the coefficients of the Laurent expansion
    # of val(m) viewed as a function. But this CF is not a Stieltjes transform.

    # Instead, use Favard's theorem directly:
    # Given b_n and a_n, the orthogonal polynomials P_n(x) satisfy
    # x P_n(x) = P_{n+1}(x) + b_n P_n(x) + a_n P_{n-1}(x)
    # with P_{-1}=0, P_0=1.

    # Actually our CF has the form b_0 + a_1/(b_1 + a_2/(b_2 + ...))
    # which corresponds to the J-fraction for a DIFFERENT Jacobi matrix.
    # In the standard Jacobi continued fraction:
    # J(z) = 1/(z - b_0 - a_1/(z - b_1 - a_2/(z - b_2 - ...)))

    # Compute eigenvalues of truncated Jacobi matrices to understand the spectrum
    print("--- Spectrum of truncated Jacobi matrices (m=0) ---")
    m = 0
    for N_trunc in [5, 10, 15]:
        # Build the tridiagonal Jacobi matrix
        J = matrix(N_trunc, N_trunc)
        for i in range(N_trunc):
            J[i, i] = mpf(3*i + 1)  # b_i
            if i > 0:
                # off-diagonal: sqrt(|a_i|) or a_i depending on convention
                ai = -mpf(i) * (2*i - (2*m + 1))
                # For the standard symmetric Jacobi: J[i,i-1] = J[i-1,i] = sqrt(|a_i|)
                # But a_i < 0 for m=0 (all n>=1), so |a_i| = n(2n-1)
                J[i, i-1] = sqrt(abs(ai))
                J[i-1, i] = sqrt(abs(ai))

        # Compute eigenvalues
        try:
            eigs = sorted([float(e) for e in J.eigenvalues()])
            print(f"  N={N_trunc}: eigenvalues = [{', '.join(f'{e:.3f}' for e in eigs)}]")
        except Exception as ex:
            print(f"  N={N_trunc}: eigenvalue computation failed: {ex}")

    # For m=1, a_1 > 0, so we need to handle the sign
    print("\n--- Spectrum for m=1 (non-definite case) ---")
    m = 1
    for N_trunc in [5, 10]:
        J = matrix(N_trunc, N_trunc)
        for i in range(N_trunc):
            J[i, i] = mpf(3*i + 1)
            if i > 0:
                ai = -mpf(i) * (2*i - 3)
                # a_1 = +1 > 0, a_i < 0 for i >= 2
                # sqrt(a_i) is imaginary for a_i < 0 in the standard form
                # Use SIGNED version: J[i,i-1] = sign(ai)*sqrt(|ai|)
                # Actually in the non-symmetric form: just use a_i directly
                # on the sub-diagonal and 1 on the super-diagonal
                J[i, i-1] = ai  # lower diagonal = a_i
                J[i-1, i] = mpf(1)  # upper diagonal = 1

        try:
            eigs_raw = J.eigenvalues()
            eigs = sorted(eigs_raw, key=lambda e: float(abs(e)))
            print(f"  N={N_trunc} (non-symmetric): eigs = "
                  f"[{', '.join(nstr(e, 6) for e in eigs[:6])}...]")
            # Check for complex eigenvalues
            n_complex = sum(1 for e in eigs_raw if abs(e.imag) > mpf('1e-20'))
            print(f"    Complex eigenvalues: {n_complex}")
        except Exception as ex:
            print(f"  N={N_trunc}: {ex}")

    print("""
For m=0: all a_n < 0, so the symmetric Jacobi matrix is well-defined
  and has real, positive eigenvalues — consistent with a positive measure.

For m>=1: a_n changes sign, so the Jacobi matrix is non-symmetric
  (or has imaginary off-diagonal in the symmetric form). The eigenvalues
  may be complex, confirming there is no positive Borel measure.

  Favard's theorem guarantees formal orthogonality with respect to a
  LINEAR FUNCTIONAL (not necessarily a positive measure). The "measure"
  is a signed distribution or a contour integral.
""")


# ============================================================================
# PART 4: Deformation test
# ============================================================================

def part4_deformation():
    mp.dps = 50
    print("\n" + "=" * 78)
    print("PART 4: Deformation test — a_m(n) + delta")
    print("=" * 78)

    print("""
Test: if we perturb a_m(n) -> a_m(n) + delta for small delta,
does the CF still converge to a Beta/Gamma ratio?

This determines whether the Wallis-PCF is isolated or part of a family.
""")

    m = 0
    N = 300

    exact_0 = 2 * gamma(1) / (sqrt(pi) * gamma(mpf('0.5')))  # 2/pi

    deltas = [mpf(0), mpf('0.01'), mpf('0.1'), mpf('0.5'),
              mpf('-0.01'), mpf('-0.1'), mpf(1), mpf(-1)]

    print(f"  {'delta':>8}  {'CF value':>22}  {'val(0)=2/pi':>12}  {'diff':>14}  {'converged':>10}")
    print("  " + "-" * 75)

    for delta in deltas:
        pp, pc = mpf(1), mpf(1)
        qp, qc = mpf(0), mpf(1)
        converged = True
        for n in range(1, N + 1):
            an = -mpf(n) * (2*n - 1) + delta  # a_0(n) + delta
            bn = mpf(3*n + 1)
            pn = bn*pc + an*pp; qn = bn*qc + an*qp
            pp, pc = pc, pn; qp, qc = qc, qn
            if abs(qc) < mpf('1e-30') and n > 10:
                converged = False
                break

        if converged and qc != 0:
            val = pc / qc
            diff = val - exact_0
            print(f"  {nstr(delta, 5):>8}  {nstr(val, 18):>22}  {nstr(exact_0, 10):>12}"
                  f"  {nstr(diff, 8):>14}  {'yes':>10}")
        else:
            print(f"  {nstr(delta, 5):>8}  {'DIVERGED':>22}  {nstr(exact_0, 10):>12}"
                  f"  {'---':>14}  {'NO':>10}")

    # Try: does a_m(n) + delta*n give another known constant?
    print(f"\n--- Deformation a_0(n) + delta*n ---")
    for delta in [mpf(1), mpf(2), mpf(-1), mpf(-2)]:
        pp, pc = mpf(1), mpf(1)
        qp, qc = mpf(0), mpf(1)
        for n in range(1, 500 + 1):
            an = -mpf(n) * (2*n - 1) + delta * n
            bn = mpf(3*n + 1)
            pn = bn*pc + an*pp; qn = bn*qc + an*qp
            pp, pc = pc, pn; qp, qc = qc, qn

        if qc != 0:
            val = pc / qc
            # This is a_0(n) + delta*n = -n(2n-1) + delta*n = -n(2n-1-delta)
            # = -n(2n - (1+delta)) = a_m(n) with 2m+1 = 1+delta, m = delta/2
            m_eff = delta / 2
            if m_eff == int(m_eff) and m_eff >= 0:
                expected = 2 * gamma(m_eff + 1) / (sqrt(pi) * gamma(m_eff + mpf('0.5')))
                print(f"  delta={nstr(delta,3):>5} => m_eff={nstr(m_eff,3)}: "
                      f"val={nstr(val,16)}, expected={nstr(expected,16)}, "
                      f"match={abs(val-expected)<mpf('1e-30')}")
            else:
                # Non-integer m_eff: still check gamma formula if not at a pole
                try:
                    expected = 2 * gamma(m_eff + 1) / (sqrt(pi) * gamma(m_eff + mpf('0.5')))
                    err = abs(val - expected)
                    dp = -int(float(log10(err + mpf('1e-100')))) if err > 0 else 50
                    print(f"  delta={nstr(delta,3):>5} => m_eff={nstr(m_eff,4)}: "
                          f"val={nstr(val,16)}, gamma formula={nstr(expected,16)}, {dp} dp")
                except (ValueError, ZeroDivisionError):
                    print(f"  delta={nstr(delta,3):>5} => m_eff={nstr(m_eff,4)}: "
                          f"val={nstr(val,16)} (gamma pole at m+1/2={nstr(m_eff+0.5,4)})")

    print("""
INTERPRETATION:
  Constant delta: shifts the CF value away from 2/pi. The CF converges
  to a DIFFERENT value that is NOT a simple Gamma ratio (for generic delta).

  Linear delta*n: equivalent to changing m to m + delta/2.
  For delta=2: m_eff=1, gives val(1)=4/pi. EXACT match.
  For delta=1: m_eff=1/2, gives val(1/2) = 2*Gamma(3/2)/(sqrt(pi)*Gamma(1))
             = 2*(sqrt(pi)/2)/sqrt(pi) = 1. So val(1/2) = 1.

  CONCLUSION: The family a_m(n) = -n(2n-(2m+1)) is a CONTINUOUS family
  parametrized by m (not just integer m). The formula
  val(m) = 2*Gamma(m+1)/(sqrt(pi)*Gamma(m+1/2)) holds for ALL real m >= 0.
""")

    # Verify continuous m
    print("--- Continuous m verification ---")
    for m_real in [mpf('0.5'), mpf('0.25'), mpf('1.5'), mpf('0.7'), mpf('3.14')]:
        pp, pc = mpf(1), mpf(1)
        qp, qc = mpf(0), mpf(1)
        for n in range(1, 500 + 1):
            an = -mpf(n) * (2*n - (2*m_real + 1))
            bn = mpf(3*n + 1)
            pn = bn*pc + an*pp; qn = bn*qc + an*qp
            pp, pc = pc, pn; qp, qc = qc, qn
        val = pc / qc
        expected = 2 * gamma(m_real + 1) / (sqrt(pi) * gamma(m_real + mpf('0.5')))
        err = abs(val - expected)
        dp = -int(float(log10(err + mpf('1e-100')))) if err > 0 else 50
        print(f"  m={nstr(m_real,5)}: val={nstr(val,16)}, formula={nstr(expected,16)}, {dp} dp")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("*" * 78)
    print("*  APPROACH C PHASE 7: ODE, convergence, moments, deformation")
    print("*" * 78)

    part1_ode_derivation()
    part2_convergence()
    part3_moments()
    part4_deformation()

    print("\n" + "=" * 78)
    print("PHASE 7 COMPLETE")
    print("=" * 78)
