"""
Heegner D=-163 CF: Targeted Tasks (Boyd series, Weierstrass model, non-period test)
====================================================================================
Task 1: Complete Boyd series expansion for m₂
Task 2: Correct Weierstrass model for E₄₁ and L(E,2)
Task 3: Non-period test via differential equations and Wronskians
"""
from mpmath import (mp, mpf, mpc, pi, log, sqrt, polylog, pslq, nstr,
                    cos, sin, quad, fabs, zeta, exp, matrix, chop, lu_solve,
                    det as mpdet, power, acosh, inf, nsum)
import time

# ─────────────────────── helpers ───────────────────────

def eval_cf(a_coeffs, b_coeffs, depth, dps=None):
    """Evaluate GCF b(0)+a(1)/(b(1)+a(2)/(b(2)+...)) via forward recurrence."""
    if dps:
        mp.dps = dps
    p_prev, p_curr = mpf(1), mpf(b_coeffs[0]) if b_coeffs else mpf(0)
    q_prev, q_curr = mpf(0), mpf(1)
    for n in range(1, depth + 1):
        a_n = sum(c * n**i for i, c in enumerate(a_coeffs))
        b_n = sum(c * n**i for i, c in enumerate(b_coeffs))
        p_prev, p_curr = p_curr, b_n * p_curr + a_n * p_prev
        q_prev, q_curr = q_curr, b_n * q_curr + a_n * q_prev
        if q_curr == 0:
            return None
    return p_curr / q_curr if q_curr != 0 else None


def kronecker_symbol(D, n):
    """Kronecker symbol (D|n) for fundamental discriminant D."""
    n = int(n)
    if n == 0:
        return 0
    D = int(D)
    result = 1
    if n < 0:
        n = -n
        if D < 0:
            result = -result
    v = 0
    while n % 2 == 0:
        n //= 2
        v += 1
    if v > 0:
        Dmod8 = D % 8
        if Dmod8 in (1, 7):
            k2 = 1
        elif Dmod8 in (3, 5):
            k2 = -1
        else:
            k2 = 0
        if v % 2 == 1:
            result *= k2
        if k2 == 0 and v > 0:
            return 0
    if n == 1:
        return result
    a = D % n
    if a < 0:
        a += n
    b = n
    j = 1
    while a != 0:
        while a % 2 == 0:
            a //= 2
            if b % 8 in (3, 5):
                j = -j
        a, b = b, a
        if a % 4 == 3 and b % 4 == 3:
            j = -j
        a = a % b
    return result * j if b == 1 else 0


def sieve_primes(limit):
    sieve = [True] * (limit + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            for j in range(i*i, limit + 1, i):
                sieve[j] = False
    return [i for i in range(2, limit + 1) if sieve[i]]


def _print_pslq(label, names, vals, rel):
    if rel:
        nz = [(n, c) for n, c in zip(names, rel) if c != 0]
        first_name = names[0] if names else ""
        if first_name.startswith('x') or first_name.startswith('c') or first_name.startswith('corr'):
            if rel[0] == 0:
                print(f"    {label}: tautology (target not involved)")
                for n, c in nz:
                    print(f"      {c:+d} * {n}")
                residual = sum(c * v for c, v in zip(rel, vals))
                print(f"      Residual: {float(residual):.3e}")
                return
        print(f"    {label}: RELATION FOUND")
        for n, c in nz:
            print(f"      {c:+d} * {n}")
        residual = sum(c * v for c, v in zip(rel, vals))
        print(f"      Residual: {float(residual):.3e}")
    else:
        print(f"    {label}: EXCLUDED (no relation found)")


SEP = '=' * 78

# ═══════════════════════════════════════════════════════════════════════
# TASK 1: Complete the Boyd series expansion
# ═══════════════════════════════════════════════════════════════════════

def task1():
    print(f"\n{'#' * 78}")
    print(f"  TASK 1: COMPLETE THE BOYD SERIES EXPANSION")
    print(f"{'#' * 78}")
    T0 = time.time()

    mp.dps = 120  # extra guard digits for 100-digit target

    disc = mpf(1677)
    alpha_plus  = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    log_ap = log(alpha_plus)

    print(f"\n  alpha+ = {nstr(alpha_plus, 50)}")
    print(f"  alpha- = {nstr(alpha_minus, 50)}")
    print(f"  alpha-^2 = {nstr(alpha_minus**2, 20)}")
    print(f"  alpha-^4 = {nstr(alpha_minus**4, 20)}")
    print(f"  alpha-^6 = {nstr(alpha_minus**6, 20)}")

    # Compute m₂ at 100+ digits
    print(f"\n  Computing m2 via adaptive quadrature (120 dps)...")
    t0 = time.time()
    def m2_integrand(theta):
        u = 41 - 2*cos(theta)
        return log((u + sqrt(u**2 - 4)) / 2)
    m2_result = quad(m2_integrand, [0, 2*pi], error=True)
    m2 = m2_result[0] / (2*pi)
    print(f"  m2 = {nstr(m2, 105)}")
    print(f"  log(alpha+) = {nstr(log_ap, 105)}")
    correction = m2 - log_ap
    print(f"  correction = m2 - log(alpha+) = {nstr(correction, 80)}")
    print(f"  Time: {time.time()-t0:.1f}s")

    # ── Step 1: Boyd series convergence ──
    print(f"\n  {'─'*60}")
    print(f"  Step 1: Boyd series S_N = log(alpha+) - sum_{{n=1}}^N Li2(alpha-^{{2n}})/n")
    print(f"  {'─'*60}")

    print(f"\n  {'N':>4s}  {'S_N':>50s}  {'S_N - m2':>20s}  {'|error|':>12s}")
    print(f"  {'─'*4}  {'─'*50}  {'─'*20}  {'─'*12}")

    S_prev = log_ap
    li2_terms = []
    for N in range(1, 31):
        z = alpha_minus**(2*N)
        li2_val = polylog(2, z)
        li2_terms.append(li2_val)
        S_N = log_ap - sum(li2_terms[n] / (n+1) for n in range(N))
        err = S_N - m2
        if N <= 15 or N % 5 == 0:
            print(f"  {N:4d}  {nstr(S_N, 50):>50s}  {float(err):>+20.6e}  {float(fabs(err)):>12.3e}")

    # ── Step 2: Series structural analysis ──
    print(f"\n  {'─'*60}")
    print(f"  Step 2: Series structure and convergence rate")
    print(f"  {'─'*60}")

    # The Boyd series: m2 = log(alpha+) - sum_{n>=1} Li2(alpha_-^{2n})/n
    # But actually... the standard formula is different. Let me verify.
    # 
    # For P_k = x+1/x+y+1/y-k with alpha+ > 1, alpha- < 1 roots of t^2-kt+1=0:
    # m(P_k) = log(alpha+) - sum_{m=1}^inf sum_{n=1}^inf (alpha_-^{2mn})/(m*n)
    #         ... that's a double sum which simplifies.
    #
    # Actually the correct Boyd formula involves the Bloch-Wigner:
    # m(P_k) = log(alpha+) + D(alpha_-^2)/(pi) + ... (Deninger's formula)
    #
    # Or more directly for |k|>4:
    # m(x+1/x+y+1/y-k) = log |alpha+| + sum_{n=1}^inf log(1 - alpha_-^{2n})
    # This is the product formula:
    # m = log(alpha+ * prod_{n>=1}(1 - alpha_-^{2n}))

    print(f"\n  Testing PRODUCT formula: m2 =? log(alpha+ * prod(1 - alpha-^{{2n}}))")
    prod = mpf(1)
    for n in range(1, 200):
        prod *= (1 - alpha_minus**(2*n))
    m2_product = log(alpha_plus * prod)
    print(f"  log(alpha+ * prod(1-a-^2n, n=1..200)) = {nstr(m2_product, 80)}")
    print(f"  m2                                      = {nstr(m2, 80)}")
    err_prod = m2 - m2_product
    print(f"  difference = {nstr(err_prod, 20)}")

    # The product formula: m2 = log(alpha+) + sum log(1 - alpha-^{2n})
    # = log(alpha+) - sum_{n>=1} sum_{m>=1} alpha_-^{2nm}/m
    # = log(alpha+) - sum_{m>=1} (1/m) sum_{n>=1} alpha_-^{2nm}
    # = log(alpha+) - sum_{m>=1} (1/m) * alpha_-^{2m}/(1-alpha_-^{2m})
    # This is the CORRECT Boyd series.

    print(f"\n  Testing CORRECT Boyd form: m2 = log(a+) - sum_{{m>=1}} a-^{{2m}} / (m*(1-a-^{{2m}}))")
    S_correct = log_ap
    for m in range(1, 200):
        z = alpha_minus**(2*m)
        S_correct -= z / (m * (1 - z))
    print(f"  Boyd correct (200 terms) = {nstr(S_correct, 80)}")
    print(f"  m2                       = {nstr(m2, 80)}")
    err_correct = m2 - S_correct
    print(f"  difference = {nstr(err_correct, 20)}")

    # Compare: which expansion works?
    print(f"\n  Convergence comparison (product vs Li2 vs correct):")
    for N in [1, 2, 3, 5, 10, 20, 50, 100]:
        # Product formula
        prod_N = mpf(1)
        for n in range(1, N+1):
            prod_N *= (1 - alpha_minus**(2*n))
        s_prod = log(alpha_plus * prod_N)

        # "Li2" form: -sum Li2(a^{2n})/n
        s_li2 = log_ap
        for n in range(1, N+1):
            s_li2 -= polylog(2, alpha_minus**(2*n)) / n

        # Correct form: -sum a^{2m}/(m(1-a^{2m}))
        s_corr = log_ap
        for m in range(1, N+1):
            z = alpha_minus**(2*m)
            s_corr -= z / (m * (1 - z))

        e1 = float(fabs(s_prod - m2))
        e2 = float(fabs(s_li2 - m2))
        e3 = float(fabs(s_corr - m2))
        print(f"    N={N:3d}: |prod-m2|={e1:.3e}  |Li2-m2|={e2:.3e}  |corr-m2|={e3:.3e}")

    # ── Step 3: PSLQ on the correction ──
    print(f"\n  {'─'*60}")
    print(f"  Step 3: PSLQ on correction = m2 - log(alpha+)")
    print(f"  {'─'*60}")

    mp.dps = 90
    # Recompute at 90 dps for PSLQ
    m2_90 = quad(m2_integrand, [0, 2*pi]) / (2*pi)
    correction = m2_90 - log(alpha_plus)
    
    Li2_am2 = polylog(2, alpha_minus**2)
    Li2_am4 = polylog(2, alpha_minus**4)
    Li2_am6 = polylog(2, alpha_minus**6)
    log_am = log(alpha_minus)
    log_am_sq = log_am**2

    print(f"  correction = {nstr(correction, 70)}")
    print(f"  Li2(a-^2)  = {nstr(Li2_am2, 40)}")
    print(f"  Li2(a-^4)  = {nstr(Li2_am4, 40)}")
    print(f"  Li2(a-^6)  = {nstr(Li2_am6, 40)}")
    print(f"  log(a-)^2  = {nstr(log_am_sq, 40)}")

    # PSLQ Test A: correction vs Li2 terms
    print(f"\n  PSLQ-A: [corr, Li2(a-^2), Li2(a-^4), Li2(a-^6), log(a-)^2, pi^2, 1]")
    names_a = ["corr", "Li2(a2)", "Li2(a4)", "Li2(a6)", "log(a-)^2", "pi^2", "1"]
    vals_a = [correction, Li2_am2, Li2_am4, Li2_am6, log_am_sq, pi**2, mpf(1)]
    try:
        rel_a = pslq(vals_a, maxcoeff=100000, tol=mpf(10)**(-40))
    except Exception as e:
        rel_a = None
        print(f"    Error: {e}")
    _print_pslq("PSLQ-A", names_a, vals_a, rel_a)

    # PSLQ Test B: correction vs just Li2(a-^2) and Li2(a-^4)
    # The Boyd series says corr = -Li2(a^2) - Li2(a^4)/2 - Li2(a^6)/3 - ...
    # So: corr + Li2(a^2) + Li2(a^4)/2 should be very small
    residual_2 = correction + Li2_am2
    residual_3 = residual_2 + Li2_am4/2
    residual_4 = residual_3 + Li2_am6/3
    print(f"\n  Boyd series partial sum test:")
    print(f"    corr + Li2(a^2)                         = {float(residual_2):.15e}")
    print(f"    corr + Li2(a^2) + Li2(a^4)/2            = {float(residual_3):.15e}")
    print(f"    corr + Li2(a^2) + Li2(a^4)/2 + Li2(a^6)/3 = {float(residual_4):.15e}")

    # Actually now test the PRODUCT form: corr = sum log(1-a^{2n})
    print(f"\n  Product form residuals:")
    s = mpf(0)
    for n in range(1, 11):
        s += log(1 - alpha_minus**(2*n))
        res = correction - s
        print(f"    sum_{{n=1}}^{n:2d} log(1-a^{{2n}}) residual: {float(res):.15e}")

    # PSLQ Test C: Boyd series remainder
    # After subtracting the leading Boyd terms, test what's left
    # corr_remainder = corr + sum_{n=1}^{10} Li2(a^{2n})/n
    corr_remainder = correction
    for n in range(1, 11):
        corr_remainder += polylog(2, alpha_minus**(2*n)) / n
    print(f"\n  Li2-series remainder (after 10 terms) = {nstr(corr_remainder, 30)}")
    print("  (should be sum_{n>10} Li2(a^{2n})/n, exponentially small)")

    # Check: is the Li2 series the same as the product formula?
    # sum Li2(z^n)/n = - sum_{n>=1} sum_{m>=1} z^{nm}/(n*m)
    # sum log(1-z^n) = - sum_{n>=1} sum_{m>=1} z^{nm}/m
    # These are DIFFERENT! The Li2 series has 1/(nm), the log-product has 1/m.
    # So which one matches m2?
    # 
    # Let's be precise. The inner integral gives:
    # (1/2pi) int log|u - 2cos(t)| dt = log((|u|+sqrt(u^2-4))/2) for |u|>2
    # Let R(u) = (|u|+sqrt(u^2-4))/2, which is the larger root of z^2-|u|z+1=0.
    # So m2 = (1/2pi) int_0^{2pi} log(R(41-2cos(s))) ds
    # 
    # For u = 41-2cos(s), R(u) = (u+sqrt(u^2-4))/2 since u>0.
    # log R(u) = acosh(u/2)
    # So m2 = (1/2pi) int_0^{2pi} acosh((41-2cos(s))/2) ds
    
    # Alternative: write R(u) in terms of alpha+ and the perturbation.
    # u = 41-2cos(s) = (alpha+ + alpha-) - 2cos(s)
    # R(u) = (u+sqrt(u^2-4))/2
    # Note: alpha+ + alpha- = 41, alpha+*alpha- = 1
    # (u+sqrt(u^2-4))/2 where u = alpha+ + alpha- - 2cos(s)

    print(f"\n  Task 1 time: {time.time()-T0:.1f}s")
    return m2, correction


# ═══════════════════════════════════════════════════════════════════════
# TASK 2: Correct Weierstrass model for E₄₁
# ═══════════════════════════════════════════════════════════════════════

def task2(m2_val, correction):
    print(f"\n{'#' * 78}")
    print(f"  TASK 2: CORRECT WEIERSTRASS MODEL FOR E_41")
    print(f"{'#' * 78}")
    T0 = time.time()

    mp.dps = 80

    # ── Step 1: Birational parametrization ──
    print(f"\n  {'─'*60}")
    print(f"  Step 1: Birational model w^2 = (u^2-4)((41-u)^2-4)")
    print(f"  {'─'*60}")

    # V: x+1/x+y+1/y = 41
    # Set u=x+1/x, v=y+1/y, so u+v=41
    # s=x-1/x => s^2=u^2-4, t=y-1/y => t^2=v^2-4=(41-u)^2-4
    # w = st => w^2 = (u^2-4)((41-u)^2-4)
    # Expand: (u^2-4)((41-u)^2-4) = (u^2-4)(u^2-82u+1681-4)
    #       = (u^2-4)(u^2-82u+1677)
    # Let's expand fully:
    # u^4 - 82u^3 + 1677u^2 - 4u^2 + 328u - 6708
    # = u^4 - 82u^3 + 1673u^2 + 328u - 6708

    print(f"  Quartic: w^2 = u^4 - 82u^3 + 1673u^2 + 328u - 6708")
    print(f"  = (u^2-4)(u^2-82u+1677)")

    # Factor analysis:
    # u^2-4 = (u-2)(u+2)
    # u^2-82u+1677: disc = 6724-6708 = 16, so u = (82+-4)/2 = 43 or 39
    # u^2-82u+1677 = (u-39)(u-43)
    print(f"  = (u-2)(u+2)(u-39)(u-43)")
    print(f"  Roots of the quartic: u = -2, 2, 39, 43")

    # ── Step 2: Transform to Weierstrass form ──
    print(f"\n  {'─'*60}")
    print(f"  Step 2: Transform quartic to Weierstrass form")
    print(f"  {'─'*60}")

    # Standard method: for w^2 = (u-r1)(u-r2)(u-r3)(u-r4) with roots r1<r2<r3<r4
    # r1=-2, r2=2, r3=39, r4=43
    # Use the substitution u = (r2*(r1-r3)*v - r1*(r2-r3)) / ((r1-r3)*v - (r2-r3))
    # with appropriate Mobius transform, or simpler:
    #
    # Shift: let U = u - r1 = u + 2. Then roots become 0, 4, 41, 45.
    # w^2 = U(U-4)(U-41)(U-45)
    # 
    # For y^2 = x(x-a)(x-b)(x-c) type, standard approach:
    # Let U = 4/X (to move one root to infinity) or use the Jacobi quartic form.
    #
    # Better: use the standard algorithm.
    # w^2 = (u+2)(u-2)(u-39)(u-43)
    # Group: [(u+2)(u-43)] * [(u-2)(u-39)] = [u^2-41u-86] * [u^2-41u-78+82]
    # Hmm, that's not clean. Try:
    # [(u+2)(u-39)] * [(u-2)(u-43)] 
    # = [u^2-37u-78] * [u^2-45u+86]
    # Still not clean. Use the classical substitution.

    # For C: y^2 = (x-e1)(x-e2)(x-e3)(x-e4), Cassels' method:
    # Pick a root, say e1 = -2. Set x = -2 + 1/t. Then:
    # y^2/t^4 = (1/t)(1/t - 4)(1/t - 41)(1/t - 45)
    # = (1/t^4)(1)(1-4t)(1-41t)(1-45t)
    # y^2 = (1-4t)(1-41t)(1-45t)/1
    # Hmm, need y = w * t^2 to absorb.
    # Let t = 1/(u+2), so u+2 = 1/t, u-2 = 1/t - 4 = (1-4t)/t, 
    # u-39 = 1/t - 41 = (1-41t)/t, u-43 = 1/t - 45 = (1-45t)/t.
    # w^2 = (1/t) * (1-4t)/t * (1-41t)/t * (1-45t)/t = (1-4t)(1-41t)(1-45t)/t^4
    # Set W = w * t^2: W^2 = (1-4t)(1-41t)(1-45t)
    # Expand: (1-4t)(1-41t) = 1-45t+164t^2
    # (1-45t+164t^2)(1-45t) = 1-45t-45t+45^2*t^2+164t^2-164*45t^3
    # = 1 - 90t + (2025+164)t^2 - 7380t^3
    # = 1 - 90t + 2189t^2 - 7380t^3
    # W^2 = -7380t^3 + 2189t^2 - 90t + 1

    # Reverse: W^2 = -7380t^3 + 2189t^2 - 90t + 1
    # Multiply by -7380^2 and set X = -7380t + 2189/3..., or standard Nagell:
    # W^2 = c3*t^3 + c2*t^2 + c1*t + c0
    # with c3=-7380, c2=2189, c1=-90, c0=1

    c3, c2, c1, c0 = -7380, 2189, -90, 1

    # Standard: multiply both sides by c3^2:
    # (c3*W)^2 = c3^3*t^3 + c3^2*c2*t^2 + c3^2*c1*t + c3^2*c0
    # Set X = c3*t + c2/3:
    # c3^3*t^3 = (X-c2/3)^3/1 ... this gets messy with fractions.
    #
    # Cleaner: use the substitution that sends the cubic to Weierstrass form.
    # W^2 = c3*t^3 + c2*t^2 + c1*t + c0
    # Let t = (X - c2*c3/3)/c3^2 ... actually:
    # Standard: T = c3*t, W' = c3*W
    # Then W'^2 = c3 * (T/c3)^3*c3^2 + ... 
    # Let me just do it numerically and symbolically.

    # For W^2 = at^3 + bt^2 + ct + d with a=-7380, b=2189, c=-90, d=1
    # Depress the cubic: substitute t = (T - b/(3a))
    # where T = new variable, to eliminate T^2 term.
    a_, b_, c_, d_ = c3, c2, c1, c0
    # t = (T - b_/(3*a_)) → cubic in T: a_*T^3 + (c_ - b_^2/(3*a_))*T + (d_ - b_*c_/(3*a_) + 2*b_^3/(27*a_^2))
    # Coefficient of T: p = c_ - b_^2/(3*a_)
    # Constant: q = d_ - b_*c_/(3*a_) + 2*b_^3/(27*a_^2)
    
    # For Weierstrass: multiply through by a_^2:
    # (a_*W)^2 = a_^3*t^3 + a_^2*b_*t^2 + a_^2*c_*t + a_^2*d_
    # Set U = a_*t + b_/3:  a_*t = U - b_/3, t = (U-b_/3)/a_
    # a_^3*t^3 = (U-b_/3)^3 = U^3 - b_*U^2 + b_^2*U/3 - b_^3/27
    # a_^2*b_*t^2 = b_*(U-b_/3)^2 = b_*U^2 - 2*b_^2*U/3 + b_^3/9
    # a_^2*c_*t = c_*a_*(U-b_/3) = c_*a_*U - c_*a_*b_/3
    # Gathering:
    # U^3 + (-b_+b_)*U^2 + (b_^2/3 - 2*b_^2/3 + c_*a_)*U + (-b_^3/27 + b_^3/9 - c_*a_*b_/3 + a_^2*d_)
    # = U^3 + (c_*a_ - b_^2/3)*U + (-b_^3/27 + b_^3/9 - c_*a_*b_/3 + a_^2*d_)
    # = U^3 + (c_*a_ - b_^2/3)*U + (2*b_^3/27 - c_*a_*b_/3 + a_^2*d_)

    # So: (a_*W)^2 = U^3 + A*U + B where:
    A_coeff = c_ * a_ - b_**2 // 3
    # Wait, need exact fractions. Let me use rational arithmetic.
    # A = c_*a_ - b_^2/3 = -90*(-7380) - 2189^2/3 = 664200 - 4791721/3
    # = (3*664200 - 4791721)/3 = (1992600 - 4791721)/3 = -2799121/3
    
    A_num = 3 * c_ * a_ - b_**2  # = 3*(-90)*(-7380) - 2189^2
    print(f"\n  Cubic coefficients:")
    print(f"    3*c*a = {3*c_*a_}")
    print(f"    b^2 = {b_**2}")
    A_num_val = 3 * c_ * a_ - b_**2
    print(f"    A_num (3*c*a - b^2) = {A_num_val}")
    # A = A_num/3

    B_num = 2 * b_**3 - 9 * c_ * a_ * b_ + 27 * a_**2 * d_
    print(f"    B_num (2b^3 - 9cab + 27a^2d) = {B_num}")
    # B = B_num/27

    # So (a_*W)^2 = U^3 + (A_num/3)*U + (B_num/27)
    # Multiply by 27: (a_*W*3*sqrt(3))^2/27 ... better:
    # 27*(a_*W)^2 = 27*U^3 + 9*A_num*U + B_num
    # Set Y = a_*W * 3*sqrt(3), X = 3*U: ... getting complicated.
    
    # Simpler: standard short Weierstrass.
    # Y^2 = X^3 + A4*X + A6 where:
    # X = 12*a_*t + 4*b_ (scale to clear denominators)
    # Actually let's use the well-known formula.
    # For y^2 = f(x) = a*x^3+b*x^2+c*x+d, the Weierstrass form is:
    # Y^2 = X^3 - 27*I*X - 27*J  where
    # I = 12*a*d - 3*b*c + ... (invariants of the cubic)

    # Invariants of cubic f(t) = a_*t^3 + b_*t^2 + c_*t + d_:
    # g2 = a_*d_ - b_*c_/3  ... no, the standard invariants for binary cubics...
    # Let me just use the standard a-invariants.
    
    # Alternative direct approach using the LMFDB / Cremona approach:
    # The curve x+1/x+y+1/y=k is well-studied. For k=41, the associated curve
    # in the LMFDB is identified by the conductor.
    
    # From our computation: w^2 = (u+2)(u-2)(u-39)(u-43)
    # This is a standard form. Let me use a Mobius transformation to 
    # get a cubic model.
    
    # Take the substitution X = u - 39/2 - 2/2 = u - 41/2 + ... hmm.
    # Let me use a cleaner approach: send one root to infinity.
    # Dehomogenize differently.
    
    # From w^2 = (u+2)(u-2)(u-39)(u-43), rewrite as:
    # w^2 = [(u-2)(u-39)] * [(u+2)(u-43)]
    # = [u^2 - 41u + 78] * [u^2 - 41u - 86]
    # Let v = u^2 - 41u. Then:
    # w^2 = (v+78)(v-86) = v^2 - 8v - 6708
    # So: w^2 = (u^2-41u)^2 - 8(u^2-41u) - 6708
    # w^2 - v^2 + 8v + 6708 = 0 where v = u^2-41u
    # This doesn't simplify nicely to Weierstrass.

    # Let me just use the cubic model from t-substitution.
    # W^2 = -7380t^3 + 2189t^2 - 90t + 1
    # To get Y^2 = X^3 + aX + b, use:
    # X = (12*(-7380)*t + 4*2189) / 12 = -7380t + 2189/3
    # Actually, the standard transformation for y^2 = a3*x^3 + a2*x^2 + a1*x + a0:
    # Set X = (a2^2 - 3*a3*a1) and compute from invariants.
    
    # Let me compute numerically. The j-invariant determines the curve.
    # From Rodriguez-Villegas: j = (t^2+12)^3/(t^2-4) where t=k-2=39.
    t_rv = 39
    j_num = (t_rv**2 + 12)**3
    j_den = t_rv**2 - 4
    j_val = mpf(j_num) / mpf(j_den)
    print(f"\n  Rodriguez-Villegas j-invariant:")
    print(f"    j = (39^2+12)^3 / (39^2-4) = {j_num} / {j_den}")
    print(f"    j = {nstr(j_val, 20)}")
    print(f"    j = {j_num/j_den:.6f}")

    # j = 1533^3 / 1517 = 3604288137/1517
    print(f"    1533 = 3*7*73, 1517 = 37*41")
    print(f"    j = 3604288137/1517 = {3604288137/1517:.6f}")

    # For Weierstrass form from j:
    # A standard curve with j-invariant j is:
    # y^2 = x^3 - 27j/(j-1728) * x - 54j/(j-1728)
    # (this is the "generic" model, might need twist)
    j_mp = mpf(j_num)/mpf(j_den)
    j_minus_1728 = j_mp - 1728
    c4 = 27 * j_mp / j_minus_1728
    c6 = 54 * j_mp / j_minus_1728
    print(f"\n  Generic Weierstrass from j:")
    print(f"    j - 1728 = {nstr(j_minus_1728, 20)}")
    print(f"    A = -27j/(j-1728) = {nstr(-c4, 20)}")
    print(f"    B = -54j/(j-1728) = {nstr(-c6, 20)}")

    # Compute discriminant of generic model to find conductor
    A_gen = -c4
    B_gen = -c6
    disc_gen = -16*(4*A_gen**3 + 27*B_gen**2)
    print(f"    Disc = -16(4A^3+27B^2) = {nstr(disc_gen, 20)}")

    # ── The actual curve: use exact rational arithmetic ──
    # j = 3604288137/1517, j-1728 = (3604288137 - 1728*1517)/1517 = (3604288137-2621376)/1517
    j_exact_num = 3604288137
    j_exact_den = 1517
    j1728_num = j_exact_num - 1728 * j_exact_den  # = 3604288137 - 2621376 = 3601666761
    j1728_den = j_exact_den  # = 1517
    print(f"\n  Exact j-1728 = {j1728_num}/{j1728_den}")
    # Factor 3601666761: check small primes
    n = j1728_num
    factors = []
    for p in [3,7,11,13,17,19,23,29,31,37,41,43,73,79,83,89,97]:
        while n % p == 0:
            factors.append(p)
            n //= p
    if n > 1:
        factors.append(n)
    print(f"    {j1728_num} = {'*'.join(str(f) for f in factors)}")

    # For the ACTUAL model, we need to find the minimal Weierstrass form.
    # The curve from the quartic w^2 = (u+2)(u-2)(u-39)(u-43) can be computed.
    # 
    # Standard result: for w^2 = prod(u-ei), the Weierstrass invariants are:
    # The cubic resolvent approach.
    # For roots e1=-2, e2=2, e3=39, e4=43:
    # sigma1 = sum = -2+2+39+43 = 82
    # sigma2 = sum pairs = (-2)(2)+(-2)(39)+(-2)(43)+(2)(39)+(2)(43)+39*43
    #        = -4 -78 -86 +78 +86 +1677 = 1673
    # sigma3 = sum triples = ... 
    # sigma4 = prod = (-2)(2)(39)(43) = -2*2*39*43 = -6708

    # For a genus-1 quartic C: y^2 = f(x) = (x-e1)(x-e2)(x-e3)(x-e4),
    # the Jacobian has the Weierstrass model:
    # Y^2 = 4X^3 - g2*X - g3
    # where g2 and g3 are computed from the invariants of f.
    # 
    # I = (e1e2+e3e4)(e1e3+e2e4)(e1e4+e2e3) relative ordering...
    # Actually the standard invariants of a degree-4 binary form:
    # I = 12*a0*a4 - 3*a1*a3 + a2^2 (for a0*x^4+a1*x^3+...)
    # J = 72*a0*a2*a4 + 9*a1*a2*a3 - 27*a0*a3^2 - 27*a1^2*a4 - 2*a2^3
    
    # Our quartic: u^4 - 82u^3 + 1673u^2 + 328u - 6708
    # a0=1, a1=-82, a2=1673, a3=328, a4=-6708
    a0, a1, a2, a3, a4 = 1, -82, 1673, 328, -6708

    I = 12*a0*a4 - 3*a1*a3 + a2**2
    J = 72*a0*a2*a4 + 9*a1*a2*a3 - 27*a0*a3**2 - 27*a1**2*a4 - 2*a2**3

    print(f"\n  Quartic invariants (Cassels-Flynn):")
    print(f"    f(u) = u^4 - 82u^3 + 1673u^2 + 328u - 6708")
    print(f"    I = 12*a0*a4 - 3*a1*a3 + a2^2 = {I}")
    print(f"    J = 72*a0*a2*a4 + 9*a1*a2*a3 - 27*a0*a3^2 - 27*a1^2*a4 - 2*a2^3 = {J}")

    # The Jacobian Weierstrass model is:
    # Y^2 = X^3 - 27*I*X - 27*J
    # (This is the standard result; see Cassels "Lectures on Elliptic Curves" §8)
    A_weier = -27 * I
    B_weier = -27 * J
    disc_weier = -16 * (4 * A_weier**3 + 27 * B_weier**2)

    print(f"\n  Jacobian Weierstrass model:")
    print(f"    Y^2 = X^3 + ({A_weier})*X + ({B_weier})")
    print(f"    A = -27I = {A_weier}")
    print(f"    B = -27J = {B_weier}")
    print(f"    Disc = -16(4A^3+27B^2) = {disc_weier}")

    # Factor discriminant
    d = abs(disc_weier)
    facs = []
    for p in sieve_primes(1000):
        while d % p == 0:
            facs.append(p)
            d //= p
    if d > 1:
        facs.append(d)
    fac_str = '*'.join(str(f) for f in facs) if facs else str(abs(disc_weier))
    print(f"    |Disc| = {'*'.join(str(f) for f in facs)}")

    # j-invariant check: j = -1728*(4A)^3 / Disc
    j_check = -1728 * (4*A_weier)**3 / disc_weier
    print(f"    j-check = {nstr(j_check, 20)} (should be {nstr(j_val, 20)})")

    # Minimal model: divide out by u^4 for u^12 | Disc, etc.
    # For minimal_model, need to find c4, c6 and reduce.
    # c4 = -48*A_weier, c6 = -864*B_weier
    c4_val = -48 * A_weier
    c6_val = -864 * B_weier
    print(f"\n  c4 = {c4_val}")
    print(f"  c6 = {c6_val}")

    # The minimal model has a = -c4/48 and b = -c6/864 after dividing by u^4, u^6.
    # Check if c4, c6 are divisible by large powers of primes:
    import math
    g = math.gcd(c4_val, c6_val)
    print(f"  gcd(c4, c6) = {g}")
    # Factor g
    g_temp = g
    g_facs = []
    for p in sieve_primes(200):
        while g_temp % p == 0:
            g_facs.append(p)
            g_temp //= p
    if g_temp > 1:
        g_facs.append(g_temp)
    print(f"  gcd factors: {'*'.join(str(f) for f in g_facs)}")

    # For minimal model, we need u such that u^4 | c4 and u^6 | c6
    # Test u = 2, 3, 4, 6, 12, ...
    for u_test in [2, 3, 4, 6, 8, 9, 12, 16, 18, 24, 27, 36, 48, 54, 72, 108, 216]:
        if c4_val % (u_test**4) == 0 and c6_val % (u_test**6) == 0:
            a_min = c4_val // (u_test**4) // (-48) if c4_val % (u_test**4 * 48) == 0 else None
            b_min = c6_val // (u_test**6) // (-864) if c6_val % (u_test**6 * 864) == 0 else None
            if a_min is not None and b_min is not None:
                print(f"  u={u_test}: A_min={a_min}, B_min={b_min}")
                disc_min = -16*(4*a_min**3 + 27*b_min**2)
                print(f"    Disc_min = {disc_min}")

    # ── Step 3: Point-counting with the correct model ──
    print(f"\n  {'─'*60}")
    print(f"  Step 3: Point counting on the correct model")
    print(f"  {'─'*60}")

    # Use the quartic: w^2 = (u+2)(u-2)(u-39)(u-43) directly for point counting.
    # #E(F_p) for primes p:
    primes = sieve_primes(500)
    bad_primes_quartic = set()  # primes dividing disc
    # disc factors include 2, 39-factor, 43-factor...
    # The disciminant of w^2 = prod(u-ei) involves differences of roots:
    # (e1-e2)(e1-e3)...(e3-e4) = (4)(41)(45)(37)(41)(4) up to sign
    # So bad primes divide 2*37*41
    # Also 39-43=-4, 2-39=-37, 2-43=-41, -2-39=-41, -2-43=-45
    # Differences: 4, 41, 45, 37, 41, 4 → primes: 2, 3, 5, 37, 41
    bad_primes_quartic = {2, 3, 5, 37, 41}

    a_p_quartic = {}
    print(f"  Counting on w^2 = (u+2)(u-2)(u-39)(u-43) mod p...")
    t0 = time.time()
    for p in primes:
        count = 0
        k39 = 39 % p
        k43 = 43 % p
        for u in range(p):
            rhs = ((u+2) * (u-2) * (u - k39) * (u - k43)) % p
            if rhs == 0:
                count += 1  # one w=0 point
            else:
                # Legendre symbol
                leg = pow(rhs, (p-1)//2, p) if p > 2 else 1
                if leg == 1:
                    count += 2

        # Include point(s) at infinity. For a quartic with leading coeff 1 (monic),
        # there are 2 points at infinity (the "top" and "bottom").
        # Actually for w^2 = u^4 + ... (degree 4, leading coeff positive QR),
        # there are 2 points at infinity.
        count += 2  # for p > 2
        if p == 2:
            # Direct check for p=2
            count = 0
            for u in range(2):
                for w in range(2):
                    rhs = ((u+2)*(u-2)*(u-39)*(u-43)) % 2
                    if (w*w - rhs) % 2 == 0:
                        count += 1
            count += 2  # proj pts

        a_p_quartic[p] = p + 1 - count

    # Hasse check
    for p in primes[:30]:
        ap = a_p_quartic[p]
        bound = 2*p**0.5
        flag = " [bad]" if p in bad_primes_quartic else ""
        viol = " HASSE!" if abs(ap) > bound + 0.5 and p not in bad_primes_quartic else ""
        if p <= 73 or viol:
            print(f"    p={p:5d}: a_p={ap:+5d}{flag}{viol}")

    violations = [p for p in primes if p not in bad_primes_quartic and abs(a_p_quartic[p]) > 2*p**0.5+0.5]
    print(f"  Hasse violations: {len(violations)}" + (f" at {violations[:5]}" if violations else " (none)"))
    print(f"  Time: {time.time()-t0:.1f}s")

    # ── Step 4: L(E,2) via Dirichlet series ──
    print(f"\n  {'─'*60}")
    print(f"  Step 4: L(E,2) from quartic model")
    print(f"  {'─'*60}")

    N_DIR = 50000
    # Build a_n
    spf = list(range(N_DIR + 1))
    for p in primes:
        if p * p > N_DIR:
            break
        if spf[p] == p:
            for j in range(p * p, N_DIR + 1, p):
                if spf[j] == j:
                    spf[j] = p

    # Prime power values
    a_pk = {}
    for p in primes:
        if p > N_DIR:
            break
        ap = a_p_quartic.get(p, 0)
        a_pk[(p, 0)] = 1
        a_pk[(p, 1)] = ap
        pk = p*p
        prev2, prev1 = 1, ap
        k_exp = 2
        while pk <= N_DIR:
            if p in bad_primes_quartic:
                a_pk[(p, k_exp)] = prev1 * ap
            else:
                a_pk[(p, k_exp)] = ap * prev1 - p * prev2
            prev2, prev1 = prev1, a_pk[(p, k_exp)]
            pk *= p
            k_exp += 1

    # Build a_n by factorization
    a_n = [0] * (N_DIR+1)
    a_n[1] = 1
    for n in range(2, N_DIR+1):
        result = 1
        m = n
        while m > 1:
            p = spf[m]
            k = 0
            while m % p == 0:
                m //= p
                k += 1
            result *= a_pk.get((p, k), 0)
        a_n[n] = result

    mp.dps = 60
    L_E2 = mpf(0)
    for n in range(1, N_DIR+1):
        if a_n[n] != 0:
            L_E2 += mpf(a_n[n]) / mpf(n)**2

    # Convergence
    print(f"  L(E,2) partial sums:")
    for cut in [100, 500, 1000, 5000, 10000, 25000, 50000]:
        Lp = mpf(0)
        for nn in range(1, min(cut, N_DIR)+1):
            if a_n[nn] != 0:
                Lp += mpf(a_n[nn]) / mpf(nn)**2
        print(f"    N={cut:6d}: {nstr(Lp, 30)}")

    # Euler product
    L_euler = mpf(1)
    for p in primes:
        ap_ = a_p_quartic.get(p, 0)
        if p in bad_primes_quartic:
            fac = 1 - mpf(ap_)/p**2
        else:
            fac = 1 - mpf(ap_)/p**2 + mpf(1)/p**3
        if fac != 0:
            L_euler /= fac
    print(f"  L(E,2) Euler ({len(primes)} primes): {nstr(L_euler, 25)}")

    # ── PSLQ with L(E,2) ──
    print(f"\n  PSLQ with correct L(E,2):")
    disc_val = mpf(1677)
    alpha_plus = (41 + sqrt(disc_val)) / 2
    alpha_minus = (41 - sqrt(disc_val)) / 2
    sq1677 = sqrt(disc_val)
    sq163 = sqrt(mpf(163))
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=60)
    log_ap = log(alpha_plus)

    for lab, nms, vs in [
        ("8-basis",
         ["x", "L/pi2", "L/pi", "m2", "log(a+)", "sqrt163", "pi", "1"],
         [x, L_E2/pi**2, L_E2/pi, m2_val, log_ap, sq163, pi, mpf(1)]),
        ("corr vs L",
         ["corr", "L/pi2", "L", "Li2(a-2)", "pi2", "1"],
         [correction, L_E2/pi**2, L_E2, polylog(2, alpha_minus**2), pi**2, mpf(1)]),
    ]:
        try:
            rel = pslq(vs, maxcoeff=50000, tol=mpf(10)**(-20))
        except Exception:
            rel = None
        _print_pslq(lab, nms, vs, rel)

    print(f"\n  Task 2 time: {time.time()-T0:.1f}s")
    return L_E2, a_p_quartic


# ═══════════════════════════════════════════════════════════════════════
# TASK 3: Non-period test via ODE/Wronskian
# ═══════════════════════════════════════════════════════════════════════

def task3():
    print(f"\n{'#' * 78}")
    print(f"  TASK 3: NON-PERIOD TEST VIA ODE AND WRONSKIANS")
    print(f"{'#' * 78}")
    T0 = time.time()

    mp.dps = 70

    # ── Step 1: Compute x(k) for k=1..20 ──
    print(f"\n  {'─'*60}")
    print(f"  Step 1: x(k) for k=1..20 (a(n)=n^2-kn, b(n)=n+1)")
    print(f"  {'─'*60}")

    x_vals = {}
    print(f"  {'k':>4s}  {'x(k)':>55s}  {'time':>6s}")
    for k in range(1, 21):
        t0 = time.time()
        xk = eval_cf([0, -k, 1], [1, 1], depth=4000, dps=70)
        x_vals[k] = xk
        t1 = time.time()
        print(f"  {k:4d}  {nstr(xk, 50):>55s}  {t1-t0:.1f}s")

    # ── Step 2: ODE test — does x(k) satisfy a linear ODE? ──
    print(f"\n  {'─'*60}")
    print(f"  Step 2: Linear ODE test (finite-difference approximation)")
    print(f"  {'─'*60}")

    # x(k) sampled at k=1..20 with spacing h=1.
    # Use central differences to approximate derivatives:
    # x'(k) ≈ (x(k+1)-x(k-1))/(2h)
    # x''(k) ≈ (x(k+1)-2x(k)+x(k-1))/h^2
    # x'''(k) ≈ (x(k+2)-2x(k+1)+2x(k-1)-x(k-2))/(2h^3)
    # x''''(k) ≈ (x(k+2)-4x(k+1)+6x(k)-4x(k-1)+x(k-2))/h^4

    # For order-r ODE with degree-d polynomial coefficients:
    # sum_{j=0}^r sum_{i=0}^d c_{j,i} * k^i * x^{(j)}(k) = 0
    # Number of unknowns: (r+1)*(d+1)
    # Number of equations: 20 - (stencil width needed for derivatives)

    # Test with integer-step differences (treat as a difference equation):
    # Instead of ODE, test a RECURRENCE:
    # sum_{j=0}^r P_j(k) * x(k+j) = 0 where P_j are polynomials of degree d
    # This is more natural for integer-spaced data.

    def test_recurrence(r, d, x_data, k_start=1):
        """Test if x(k) satisfies a recurrence of order r with poly-degree d coefficients."""
        n_unknowns = (r + 1) * (d + 1)
        n_equations = len(x_data) - r
        if n_equations < n_unknowns:
            return None, None

        # Build matrix: each row is one equation
        # For k = k_start, k_start+1, ..., we need x(k), x(k+1), ..., x(k+r)
        keys = sorted(x_data.keys())
        rows = []
        for idx in range(n_equations):
            k = keys[idx]
            if k + r not in x_data:
                continue
            row = []
            for j in range(r + 1):
                xkj = x_data[k + j]
                for i in range(d + 1):
                    row.append(mpf(k)**i * xkj)
            rows.append(row)

        if len(rows) < n_unknowns:
            return None, None

        # Use more equations than unknowns → overdetermined system
        # Check if the matrix has a nontrivial null vector
        m_rows = min(len(rows), n_unknowns + 5)
        M = matrix(rows[:m_rows])

        # Try PSLQ on the first n_unknowns rows (square system)
        if m_rows >= n_unknowns:
            # Build n_unknowns-dimensional vectors and check for linear dependence
            # Actually, use SVD-like approach: try to find null vector via PSLQ
            # on each column combination... too expensive.
            # Instead: check if rank < n_unknowns by trying to solve M*c=0.
            pass

        return rows, n_unknowns

    # Test specific small orders
    # Filter out None values from x_vals
    x_valid = {k: v for k, v in x_vals.items() if v is not None}
    valid_keys = sorted(x_valid.keys())
    print(f"  Valid x(k) values: {len(x_valid)}/20 (missing: {[k for k in range(1,21) if k not in x_valid]})")

    for r in range(2, 6):
        for d in range(0, 4):
            n_unk = (r+1)*(d+1)

            # Build system: for consecutive k values where x(k)..x(k+r) all exist
            rows = []
            for k in valid_keys:
                # Check that x(k), x(k+1), ..., x(k+r) all exist
                if all((k+j) in x_valid for j in range(r+1)):
                    row = []
                    for j in range(r+1):
                        xkj = x_valid[k+j]
                        for i in range(d+1):
                            row.append(mpf(k)**i * xkj)
                    rows.append(row)

            if len(rows) < n_unk:
                continue

            # Take exactly n_unk rows, solve M*c = 0 by extending to PSLQ
            # Take first n_unk rows as a square matrix, check det
            A = matrix(rows[:n_unk])
            try:
                d_val = mpdet(A)
            except Exception:
                d_val = None
            if d_val is not None:
                log_det = float(log(fabs(d_val))) if fabs(d_val) > 0 else -999
            else:
                log_det = -999

            # Also check with extra rows (overdetermined residual)
            if len(rows) > n_unk:
                # Use all rows to build overdetermined system and check residual
                A_full = matrix(rows)
                # Compute the residual of the least-squares solution
                # by checking if the square sub-matrix has near-zero det
                pass

            tiny = fabs(d_val) < mpf(10)**(-30) if d_val is not None else False
            marker = " *** POSSIBLE ODE ***" if tiny else ""
            print(f"    order={r}, deg={d}: {n_unk} unknowns, {len(rows)} eqs, "
                  f"|det|={float(fabs(d_val)) if d_val else 0:.3e}, "
                  f"log|det|={log_det:.1f}{marker}")

    # ── Step 3: Wronskian test ──
    print(f"\n  {'─'*60}")
    print(f"  Step 3: Wronskian test — W_r(k) = det([x(k+i+j)]_{{i,j=0..r-1}})")
    print(f"  {'─'*60}")
    print(f"  If x(k) satisfies a linear recurrence of order r, then W_r(k) = 0 for all k.\n")

    for r in range(3, 7):
        print(f"  Wronskian order {r}:")
        for k_start in range(1, min(12, 21-r)):
            # Check all indices exist and are not None
            indices = [k_start + i + j for i in range(r) for j in range(r)]
            max_idx = max(indices)
            if max_idx > 20:
                continue
            if any(idx not in x_valid for idx in indices):
                print(f"    k={k_start:3d}: skipped (missing values)")
                continue
            W = matrix(r, r)
            for i in range(r):
                for j in range(r):
                    W[i, j] = x_valid[k_start + i + j]
            try:
                det_val = mpdet(W)
                print(f"    k={k_start:3d}: |W_{r}| = {float(fabs(det_val)):.6e}")
            except Exception as e:
                print(f"    k={k_start:3d}: error: {e}")

    # Summary
    print(f"\n  Interpretation:")
    print(f"  If |W_r| stays large for all r and k, then x(k) is NOT D-finite")
    print(f"  (does not satisfy any linear recurrence with polynomial coefficients).")
    print(f"  This is a strong obstruction to being a period of a motivic family.")

    # ── Step 4: Gamma-function test ──
    print(f"\n  {'─'*60}")
    print(f"  Step 4: Ratio test x(k+1)/x(k)")
    print(f"  {'─'*60}")
    print(f"  For 'Gamma-type' periods, x(k+1)/x(k) -> rational function of k as k->inf.\n")

    print(f"  {'k':>4s}  {'x(k+1)/x(k)':>30s}  {'(k+1)/k':>12s}  {'ratio/((k+1)/k)':>20s}")
    for k in range(1, 19):
        if k in x_valid and k+1 in x_valid and x_valid[k] != 0:
            ratio = x_valid[k+1] / x_valid[k]
            simple = mpf(k+1)/k
            adj = ratio / simple if simple != 0 else mpf(0)
            print(f"  {k:4d}  {nstr(ratio, 25):>30s}  {float(simple):>12.6f}  {nstr(adj, 15):>20s}")

    # Test: is x(k+1)/x(k) a rational function of k?
    # Fit: ratio(k) ≈ (a*k+b)/(c*k+d) for large k
    # Use the last 10 ratios (k=9..18) to build a PSLQ test
    print(f"\n  PSLQ on ratios: is x(k+1)/x(k) rational in k?")
    for k in range(10, 18):
        if k in x_valid and k+1 in x_valid and x_valid[k] != 0:
            r = x_valid[k+1] / x_valid[k]
            # Test: r = (a0 + a1*k) / (b0 + b1*k) → r*(b0+b1*k) = a0+a1*k
            # → r*b0 + r*b1*k - a0 - a1*k = 0
            # PSLQ on [r, r*k, 1, k] should find relation
            vals = [r, r*mpf(k), mpf(1), mpf(k)]
            try:
                rel = pslq(vals, maxcoeff=10000, tol=mpf(10)**(-25))
            except Exception:
                rel = None
            if rel:
                b0, b1, a0_neg, a1_neg = rel
                print(f"    k={k}: {b0}*r + {b1}*r*k + {a0_neg} + {a1_neg}*k = 0  → r = ({-a0_neg}+{-a1_neg}*k)/({b0}+{b1}*k)")
            else:
                print(f"    k={k}: no rational relation (bound 10K)")

    # Check if ratios stabilize for large k
    print(f"\n  Ratio trend for large k (k=15..19):")
    for k in range(15, 20):
        if k in x_valid and k+1 in x_valid and x_valid[k] != 0:
            r = x_valid[k+1] / x_valid[k]
            print(f"    x({k+1})/x({k}) = {nstr(r, 30)}")

    # ── Step 5: Sign pattern and growth ──
    print(f"\n  {'─'*60}")
    print(f"  Step 5: Growth and sign pattern")
    print(f"  {'─'*60}")

    print(f"\n  {'k':>4s}  {'|x(k)|':>25s}  {'sign':>6s}  {'log|x(k)|':>15s}")
    for k in range(1, 21):
        if k not in x_valid:
            print(f"  {k:4d}  {'N/A':>25s}  {'N/A':>6s}  {'N/A':>15s}")
            continue
        xk = x_valid[k]
        sgn = "+" if xk > 0 else "-"
        abs_xk = fabs(xk)
        if abs_xk > 0:
            print(f"  {k:4d}  {float(abs_xk):>25.15e}  {sgn:>6s}  {float(log(abs_xk)):>15.6f}")
        else:
            print(f"  {k:4d}  {float(abs_xk):>25.15e}  {sgn:>6s}  {'   -inf':>15s}")

    print(f"\n  Task 3 time: {time.time()-T0:.1f}s")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    T0 = time.time()
    print(SEP)
    print("  HEEGNER D=-163: TARGETED ANALYSIS (Boyd, Weierstrass, Non-Period)")
    print(SEP)

    m2, correction = task1()
    L_E2, a_p = task2(m2, correction)
    task3()

    print(f"\n{'#' * 78}")
    print(f"  ALL TASKS COMPLETE — Total: {time.time()-T0:.1f}s")
    print(f"{'#' * 78}")

if __name__ == '__main__':
    main()
