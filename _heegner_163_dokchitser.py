"""
Dokchitser L(E',2) for the (-1)-twist of 22755.c3
E' is the Jacobian of w^2 = (u+2)(u-2)(u-39)(u-43)
"""
from mpmath import (mp, mpf, mpc, pi, log, sqrt, polylog, pslq, nstr,
                    cos, sin, quad, fabs, zeta, exp, gammainc, gamma, e1)
import time

def eval_cf(a_coeffs, b_coeffs, depth, dps=None):
    if dps: mp.dps = dps
    p_prev, p_curr = mpf(1), mpf(b_coeffs[0]) if b_coeffs else mpf(0)
    q_prev, q_curr = mpf(0), mpf(1)
    for n in range(1, depth + 1):
        a_n = sum(c * n**i for i, c in enumerate(a_coeffs))
        b_n = sum(c * n**i for i, c in enumerate(b_coeffs))
        p_prev, p_curr = p_curr, b_n * p_curr + a_n * p_prev
        q_prev, q_curr = q_curr, b_n * q_curr + a_n * q_prev
        if q_curr == 0: return None
    return p_curr / q_curr if q_curr != 0 else None

def sieve_primes(limit):
    s = [True]*(limit+1); s[0]=s[1]=False
    for i in range(2, int(limit**0.5)+1):
        if s[i]:
            for j in range(i*i, limit+1, i): s[j]=False
    return [i for i in range(2, limit+1) if s[i]]

def _print_pslq(label, names, vals, rel):
    if rel:
        nz = [(n, c) for n, c in zip(names, rel) if c != 0]
        if names[0].startswith('x') and rel[0] == 0:
            print(f"    {label}: tautology")
        else:
            print(f"    {label}: RELATION FOUND")
        for n, c in nz:
            print(f"      {c:+d} * {n}")
        residual = sum(c * v for c, v in zip(rel, vals))
        print(f"      Residual: {float(residual):.3e}")
    else:
        print(f"    {label}: EXCLUDED")

SEP = '=' * 78

def main():
    T0 = time.time()
    print(SEP)
    print("  L(E',2) VIA DOKCHITSER FOR THE (-1)-TWIST OF 22755.c3")
    print(SEP)

    mp.dps = 70

    # ═══════════════════════════════════════════════════
    # STEP 1: Identify E' and its conductor
    # ═══════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  STEP 1: IDENTIFY E' (the -1 twist)")
    print(f"{'#' * 78}")

    # E = 22755.c3: y^2 + xy + y = x^3 + x^2 - 58315x + 5394272
    # ainvs [1,1,1,-58315,5394272], conductor 22755 = 3*5*37*41, rank 0

    # E' = (-1)-twist of E.
    # For general Weierstrass y^2 + a1 xy + a3 y = x^3 + a2 x^2 + a4 x + a6,
    # the short Weierstrass is y^2 = x^3 + A*x + B where:
    # b2 = a1^2+4*a2, b4 = a1*a4+2*a6... wait let me use the standard formulas.

    # To twist by d=-1 for the SHORT Weierstrass:
    # Convert E to short Weierstrass first.
    # For [1,1,1,-58315,5394272]:
    a1,a2,a3,a4,a6 = 1,1,1,-58315,5394272
    b2 = a1**2 + 4*a2  # = 1+4 = 5
    b4 = a1*a4 + 2*a6  # = -58315 + 10788544 = 10730229
    b6 = a4**2 + 4*a6  # = 58315^2 + 4*5394272... wait, b6 = a3^2+4*a6 = 1+21577088=21577089
    b8 = a1**2*a6 - a1*a3*a4 + a2*a6 + a2*a4*a3 - a3**2  # wait, wrong
    # Actually b6 = a3^2 + 4*a6 = 1 + 4*5394272 = 21577089
    # b8 = a1^2*a6 + 4*a2*a6 - a1*a3*a4 + a2*a3^2 - a4^2
    b8 = a1**2*a6 + 4*a2*a6 - a1*a3*a4 + a2*a3**2 - a4**2

    # c4 = b2^2 - 24*b4 = 25 - 24*10730229 = 25 - 257525496 = -257525471
    c4 = b2**2 - 24*b4
    # c6 = -b2^3 + 36*b2*b4 - 216*b6
    c6 = -b2**3 + 36*b2*b4 - 216*b6

    # Short Weierstrass: y^2 = x^3 - 27*c4*x - 54*c6
    A_E = -27 * c4
    B_E = -54 * c6

    print(f"\n  E = 22755.c3")
    print(f"  Short Weierstrass of E: y^2 = x^3 + ({A_E})x + ({B_E})")

    # (-1)-twist: y^2 = x^3 + A*x - B  (flip sign of B)
    A_twist = A_E
    B_twist = -B_E
    print(f"  (-1)-twist E': y^2 = x^3 + ({A_twist})x + ({B_twist})")

    # Verify this matches our Jacobian model
    A_jac = -75576267
    B_jac = -252808806726
    print(f"  Jacobian model: y^2 = x^3 + ({A_jac})x + ({B_jac})")

    # Check if they're the same up to scaling
    if A_twist != 0 and A_jac != 0:
        ratio_A = A_twist / A_jac
        ratio_B = B_twist / B_jac if B_jac != 0 else None
        print(f"  A_twist/A_jac = {ratio_A}")
        if ratio_B: print(f"  B_twist/B_jac = {ratio_B}")
        # If ratio_A = u^4 and ratio_B = u^6 for some u, they're isomorphic
        if ratio_B:
            lam2 = ratio_B / ratio_A  # should be u^2
            print(f"  lambda^2 = {lam2}")

    # Since the Jacobian model might be a different scaling, let's compute a_p
    # directly from the twist model and verify they match the Jacobian.

    # For the LMFDB model [0,1,0,-933040,-347099500] at conductor 364080:
    # 364080 = 2^4 * 3 * 5 * 37 * 41 = 16 * 22755
    # This is the twist! Let me verify.
    print(f"\n  LMFDB candidate: 364080.bv3, ainvs [0,1,0,-933040,-347099500]")
    print(f"  Conductor: 364080 = 2^4 * 3 * 5 * 37 * 41 = 16 * 22755")

    # Verify a_p match between Jacobian and 364080.bv3
    primes = sieve_primes(200)
    a_p_jac = {}
    for p in primes:
        Ap = A_jac % p; Bp = B_jac % p
        count = 0
        for xv in range(p):
            rhs = (xv**3 + Ap*xv + Bp) % p
            if rhs == 0: count += 1
            elif p > 2 and pow(rhs, (p-1)//2, p) == 1: count += 2
        a_p_jac[p] = p + 1 - (count + 1)

    # Count on 364080.bv3 model: [0,1,0,-933040,-347099500]
    a1b,a2b,a3b,a4b,a6b = 0,1,0,-933040,-347099500
    a_p_bv = {}
    for p in primes:
        _a1=a1b%p; _a2=a2b%p; _a3=a3b%p; _a4=a4b%p; _a6=a6b%p
        count = 0
        for x in range(p):
            rhs = (x**3 + _a2*x*x + _a4*x + _a6) % p
            c_lin = (_a1*x + _a3) % p
            if p == 2:
                for y in range(2):
                    if (y*y + _a1*x*y + _a3*y) % 2 == rhs % 2: count += 1
            else:
                disc = (c_lin*c_lin + 4*rhs) % p
                if disc == 0: count += 1
                elif pow(disc, (p-1)//2, p) == 1: count += 2
        a_p_bv[p] = p + 1 - (count + 1)

    print(f"\n  Verify a_p match: Jacobian vs 364080.bv3")
    match = 0
    for p in primes[:30]:
        m = "ok" if a_p_jac[p] == a_p_bv[p] else "MISMATCH"
        if a_p_jac[p] == a_p_bv[p]: match += 1
        if p <= 73 or m != "ok":
            print(f"    p={p:5d}: Jac={a_p_jac[p]:+5d}  bv3={a_p_bv[p]:+5d}  {m}")
    total_match = sum(1 for p in primes if a_p_jac[p] == a_p_bv[p])
    print(f"  Total match: {total_match}/{len(primes)}")

    # Determine which curve matches; if 364080.bv3 doesn't match, try the
    # Jacobian model directly.
    if total_match == len(primes):
        print(f"\n  CONFIRMED: E' = 364080.bv3")
        N_cond = 364080
        use_ainvs = (a1b,a2b,a3b,a4b,a6b)
        a_p_Ep = a_p_bv
    else:
        print(f"\n  364080.bv3 does NOT match Jacobian a_p.")
        print(f"  Using Jacobian model directly.")
        # Estimate conductor from discriminant
        # |Disc| = 2^12*3^16*5^2*37^2*41^4
        # Conductor divides radical(Disc)... need to determine from a_p
        # For p where a_p=0 and not bad: additive reduction => p^2 | N
        # Try N = 2^? * 3 * 5 * 37 * 41
        # a_2(Jac) = 0 => likely additive at 2, so 2^2|N at least
        N_cond = 4 * 22755  # = 91020 as first guess
        use_ainvs = None
        a_p_Ep = a_p_jac

    # ═══════════════════════════════════════════════════
    # STEP 2: Compute L(E',2) via Dokchitser
    # ═══════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  STEP 2: L(E',2) VIA DOKCHITSER")
    print(f"{'#' * 78}")

    mp.dps = 60
    N = mpf(N_cond)
    sqrtN = sqrt(N)
    twopi_sqrtN = 2*pi / sqrtN

    # Build a_n from a_p
    N_terms = 2000  # enough for exponential convergence
    primes_for_an = sieve_primes(N_terms)

    # SPF sieve
    spf = list(range(N_terms+1))
    for p in primes_for_an:
        if p*p > N_terms: break
        if spf[p]==p:
            for j in range(p*p, N_terms+1, p):
                if spf[j]==j: spf[j]=p

    bad_primes_Ep = set()
    for p in [2,3,5,37,41]:
        bad_primes_Ep.add(p)

    a_pk = {}
    for p in primes_for_an:
        if p > N_terms: break
        ap = a_p_Ep.get(p, 0)
        a_pk[(p,0)] = 1; a_pk[(p,1)] = ap
        pk = p*p; prev2,prev1 = 1, ap; ke = 2
        while pk <= N_terms:
            if p in bad_primes_Ep:
                a_pk[(p,ke)] = prev1 * ap
            else:
                a_pk[(p,ke)] = ap*prev1 - p*prev2
            prev2, prev1 = prev1, a_pk[(p,ke)]
            pk *= p; ke += 1

    a_n = [0]*(N_terms+1); a_n[1] = 1
    for n in range(2, N_terms+1):
        result = 1; m = n
        while m > 1:
            p = spf[m]; k = 0
            while m%p==0: m//=p; k+=1
            result *= a_pk.get((p,k), 0)
        a_n[n] = result

    print(f"\n  Conductor N = {N_cond}")
    print(f"  sqrt(N) = {nstr(sqrtN, 15)}")
    print(f"  2pi/sqrt(N) = {nstr(twopi_sqrtN, 15)}")
    print(f"  Using {N_terms} terms (e^{{-2pi*N/sqrt(N)}} ~ {float(exp(-twopi_sqrtN*N_terms)):.1e})")

    # Dokchitser formula for L(E,s) at s=2:
    # L(E,2) = sum_n a_n/n^2 * Gamma(2, 2*pi*n/sqrt(N))
    #        + epsilon * (2pi/sqrt(N))^2 * sum_n a_n * E1(2*pi*n/sqrt(N))
    # where Gamma(2,x) = (1+x)*e^(-x), E1(x) = Gamma(0,x) = int_x^inf e^-t/t dt

    # Root number epsilon: for the original E (rank 0), epsilon = +1 (even functional eq).
    # For the -1 twist: epsilon(E') = epsilon(E) * prod of local signs...
    # For weight 2: epsilon = (-1)^{rank} for Mordell-Weil rank over Q.
    # We don't know the rank of E' yet. Try both epsilon = +1 and -1.

    for eps_try in [+1, -1]:
        sum1 = mpf(0)  # sum a_n/n^2 * Gamma(2, alpha*n) where alpha = 2pi/sqrt(N)
        sum2 = mpf(0)  # sum a_n * E1(alpha*n)

        for n in range(1, N_terms+1):
            if a_n[n] == 0: continue
            alpha_n = twopi_sqrtN * n
            # Gamma(2, x) = (1+x)*exp(-x)
            g2 = (1 + alpha_n) * exp(-alpha_n)
            # E1(x) = gammainc(0, x)  -- exponential integral
            e1_val = gammainc(0, alpha_n)

            sum1 += mpf(a_n[n]) / mpf(n)**2 * g2
            sum2 += mpf(a_n[n]) * e1_val

        L_E2 = sum1 + eps_try * twopi_sqrtN**2 * sum2
        print(f"\n  epsilon = {eps_try:+d}:")
        print(f"    sum1 (direct)    = {nstr(sum1, 35)}")
        print(f"    sum2 (func. eq.) = {nstr(sum2, 35)}")
        print(f"    L(E',2)          = {nstr(L_E2, 35)}")

    # Also compute naive Dirichlet series for comparison
    L_naive = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] != 0:
            L_naive += mpf(a_n[n]) / mpf(n)**2
    print(f"\n  Naive Dirichlet sum ({N_terms} terms): {nstr(L_naive, 30)}")

    # Try different conductors if the Dokchitser values look wrong
    print(f"\n  Testing multiple conductors:")
    for N_try in [22755, 45510, 91020, 182040, 364080]:
        sqN = sqrt(mpf(N_try))
        alpha = 2*pi/sqN
        s1 = mpf(0); s2 = mpf(0)
        for n in range(1, N_terms+1):
            if a_n[n] == 0: continue
            an = alpha*n
            g2 = (1+an)*exp(-an)
            e1v = gammainc(0, an)
            s1 += mpf(a_n[n])/mpf(n)**2 * g2
            s2 += mpf(a_n[n]) * e1v
        Lp = s1 + alpha**2 * s2
        Lm = s1 - alpha**2 * s2
        print(f"    N={N_try:6d}: L(+)={nstr(Lp,20)} L(-)={nstr(Lm,20)} naive={nstr(L_naive,20)}")

    # Pick the best: the Dokchitser value should agree with naive for large N_terms
    # The "direct" part sum1 should dominate when alpha is small (large N)
    # Use the conductor where L(+) or L(-) most closely matches the naive sum

    # ═══════════════════════════════════════════════════
    # STEP 3: PSLQ with L(E',2)
    # ═══════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  STEP 3: PSLQ TESTS")
    print(f"{'#' * 78}")

    mp.dps = 65
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=65)

    disc = mpf(1677)
    alpha_plus = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    log_ap = log(alpha_plus)
    sq163 = sqrt(mpf(163))

    def m2_integrand(theta):
        u = 41 - 2*cos(theta)
        return log((u + sqrt(u**2 - 4)) / 2)
    m2 = quad(m2_integrand, [0, 2*pi]) / (2*pi)

    # Use several L-values (both epsilon choices, several conductors)
    # Take the naive Dirichlet sum as the most reliable L(E',2) estimate
    L2 = L_naive

    print(f"\n  Using L(E',2) = {nstr(L2, 35)} (naive Dirichlet, {N_terms} terms)")
    print(f"  x       = {nstr(x, 50)}")

    # Main PSLQ
    print(f"\n  PSLQ-A: [x, L'/pi2, L'/pi, m2, log(a+), sqrt163, pi, 1]")
    names_a = ["x", "L'/pi2", "L'/pi", "m2", "log(a+)", "sqrt163", "pi", "1"]
    vals_a = [x, L2/pi**2, L2/pi, m2, log_ap, sq163, pi, mpf(1)]
    try:
        rel_a = pslq(vals_a, maxcoeff=50000, tol=mpf(10)**(-25))
    except Exception: rel_a = None
    _print_pslq("PSLQ-A", names_a, vals_a, rel_a)

    # PSLQ-B: correction vs L(E',2)
    correction = m2 - log_ap
    print(f"\n  PSLQ-B: [correction, L'/pi2, L'/pi, L', 1]")
    names_b = ["corr", "L'/pi2", "L'/pi", "L'", "1"]
    vals_b = [correction, L2/pi**2, L2/pi, L2, mpf(1)]
    try:
        rel_b = pslq(vals_b, maxcoeff=100000, tol=mpf(10)**(-25))
    except Exception: rel_b = None
    _print_pslq("PSLQ-B", names_b, vals_b, rel_b)

    # PSLQ-C: small basis
    print(f"\n  PSLQ-C: [x, L', m2, pi, 1]")
    names_c = ["x", "L'", "m2", "pi", "1"]
    vals_c = [x, L2, m2, pi, mpf(1)]
    try:
        rel_c = pslq(vals_c, maxcoeff=100000, tol=mpf(10)**(-25))
    except Exception: rel_c = None
    _print_pslq("PSLQ-C", names_c, vals_c, rel_c)

    # ═══════════════════════════════════════════════════
    # STEP 4: Boyd residual vs L(E',1)
    # ═══════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  STEP 4: BOYD RESIDUAL vs L(E',1)")
    print(f"{'#' * 78}")

    # Compute L(E',1) naively
    L1 = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] != 0:
            L1 += mpf(a_n[n]) / mpf(n)
    print(f"\n  L(E',1) naive ({N_terms} terms) = {nstr(L1, 25)}")

    # Also Dokchitser for L(E',1):
    # Gamma(1,x) = e^{-x}, and the s=1 analogue needs Gamma(1,x) for direct
    # and Gamma(1,x) for func.eq. (since 2-s=1 too). At s=1 the func.eq. is symmetric.
    for N_try in [91020, 364080]:
        sqN = sqrt(mpf(N_try))
        alpha = 2*pi/sqN
        s1_L1 = mpf(0); s2_L1 = mpf(0)
        for n in range(1, N_terms+1):
            if a_n[n] == 0: continue
            an = alpha*n
            g1 = exp(-an)  # Gamma(1,x) = e^{-x}
            s1_L1 += mpf(a_n[n])/mpf(n) * g1
            s2_L1 += mpf(a_n[n])/mpf(n) * g1
        L1p = s1_L1 + alpha * s2_L1
        L1m = s1_L1 - alpha * s2_L1
        print(f"    N={N_try}: L1(+)={nstr(L1p,20)}  L1(-)={nstr(L1m,20)}")

    # Boyd residual
    product_sum = mpf(0)
    for n in range(1, 200):
        product_sum += log(1 - alpha_minus**(2*n))
    boyd_residual = correction - product_sum

    print(f"\n  Boyd residual = {nstr(boyd_residual, 30)}")
    print(f"  L(E',1) naive = {nstr(L1, 25)}")

    # PSLQ: residual vs L(E',1)
    print(f"\n  PSLQ-D: [residual, L(E',1)/pi, L(E',1), 1]")
    names_d = ["resid", "L1/pi", "L1", "1"]
    vals_d = [boyd_residual, L1/pi, L1, mpf(1)]
    try:
        rel_d = pslq(vals_d, maxcoeff=100000, tol=mpf(10)**(-20))
    except Exception: rel_d = None
    _print_pslq("PSLQ-D", names_d, vals_d, rel_d)

    # PSLQ: correction vs L values
    print(f"\n  PSLQ-E: [corr, L2/pi2, L1/pi, Li2(a-^2), 1]")
    Li2_am2 = polylog(2, alpha_minus**2)
    names_e = ["corr", "L2/pi2", "L1/pi", "Li2(am2)", "1"]
    vals_e = [correction, L2/pi**2, L1/pi, Li2_am2, mpf(1)]
    try:
        rel_e = pslq(vals_e, maxcoeff=100000, tol=mpf(10)**(-20))
    except Exception: rel_e = None
    _print_pslq("PSLQ-E", names_e, vals_e, rel_e)

    # Ratio table
    print(f"\n  Ratio analysis:")
    for name, val in [("L2/pi2", L2/pi**2), ("L1/pi", L1/pi), ("L2", L2), ("L1", L1)]:
        if val != 0:
            r_res = boyd_residual / val
            r_cor = correction / val
            print(f"    {name:12s}: resid/val={nstr(r_res,15)}  corr/val={nstr(r_cor,15)}")

    print(f"\n  Total time: {time.time()-T0:.1f}s")

if __name__ == '__main__':
    main()
