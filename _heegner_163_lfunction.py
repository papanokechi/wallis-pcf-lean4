"""
L(E,2) computation using LMFDB curve 22755.c3 (Cremona 22755e2)
Model: y^2 + xy + y = x^3 + x^2 - 58315x + 5394272
Conductor N = 22755 = 3*5*37*41
"""
from mpmath import (mp, mpf, mpc, pi, log, sqrt, polylog, pslq, nstr,
                    cos, sin, quad, fabs, zeta, exp, matrix)
import time, math

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

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
    s = [True] * (limit + 1); s[0] = s[1] = False
    for i in range(2, int(limit**0.5) + 1):
        if s[i]:
            for j in range(i*i, limit+1, i): s[j] = False
    return [i for i in range(2, limit+1) if s[i]]

def _print_pslq(label, names, vals, rel):
    if rel:
        nz = [(n, c) for n, c in zip(names, rel) if c != 0]
        if names[0].startswith('x') and rel[0] == 0:
            print(f"    {label}: tautology (x not involved)")
        else:
            print(f"    {label}: RELATION FOUND")
        for n, c in nz:
            print(f"      {c:+d} * {n}")
        residual = sum(c * v for c, v in zip(rel, vals))
        print(f"      Residual: {float(residual):.3e}")
    else:
        print(f"    {label}: EXCLUDED (no relation found)")

SEP = '=' * 78

# ═══════════════════════════════════════════════════════════════
# STEP 1: Compute a_p from the LMFDB model
# y^2 + xy + y = x^3 + x^2 - 58315x + 5394272
# a1=1, a2=1, a3=1, a4=-58315, a6=5394272
# ═══════════════════════════════════════════════════════════════

def step1():
    print(f"\n{'#' * 78}")
    print(f"  STEP 1: COMPUTE a_p FROM LMFDB MODEL 22755.c3")
    print(f"{'#' * 78}")
    T0 = time.time()

    a1, a2, a3, a4, a6 = 1, 1, 1, -58315, 5394272
    N_cond = 22755
    bad_primes = {3, 5, 37, 41}

    print(f"\n  Model: y^2 + xy + y = x^3 + x^2 - 58315x + 5394272")
    print(f"  Conductor: {N_cond} = 3*5*37*41")

    # Point counting for primes up to 1000
    # For larger primes, use the short Weierstrass reduction:
    # Complete the square: y^2 + (a1*x+a3)y = ... => (2y+a1*x+a3)^2/4 = RHS + (a1*x+a3)^2/4
    # b2=a1^2+4*a2=1+4=5, b4=a1*a4+2*a6=1*(-58315)+2*5394272=-58315+10788544=10730229
    # b6=a4^2+4*a6=(-58315)^2+4*5394272=... wait, b6 = a3^2+4*a6 = 1+4*5394272=21577089
    # b8=a1^2*a6-a1*a3*a4+a2*a6+a2*a4*a3-a3^2*... complicated.
    # Actually for point counting mod p, just count directly for p <= some limit.

    primes = sieve_primes(1000)
    a_p = {}
    t0 = time.time()

    for p in primes:
        _a1 = a1 % p; _a2 = a2 % p; _a3 = a3 % p
        _a4 = a4 % p; _a6 = a6 % p
        count = 0
        for x in range(p):
            # LHS = y^2 + a1*x*y + a3*y
            # RHS = x^3 + a2*x^2 + a4*x + a6
            rhs = (x*x*x + _a2*x*x + _a4*x + _a6) % p
            # Count solutions to y^2 + (a1*x + a3)*y - rhs = 0 mod p
            c_lin = (_a1 * x + _a3) % p  # coefficient of y
            # y^2 + c_lin*y = rhs  =>  (2y+c_lin)^2 = 4*rhs + c_lin^2
            if p == 2:
                for y in range(2):
                    lhs = (y*y + _a1*x*y + _a3*y) % 2
                    if lhs == rhs % 2:
                        count += 1
            else:
                disc = (c_lin * c_lin + 4 * rhs) % p
                if disc == 0:
                    count += 1
                else:
                    leg = pow(disc, (p - 1) // 2, p)
                    if leg == 1:
                        count += 2
        Np = count + 1  # point at infinity
        a_p[p] = p + 1 - Np

    t1 = time.time()
    print(f"  Computed a_p for {len(primes)} primes in {t1-t0:.1f}s")

    # Report first 25 primes
    print(f"\n  {'p':>5s}  {'a_p':>5s}  {'bad?':>5s}")
    for p in primes[:25]:
        bad = "yes" if p in bad_primes else ""
        print(f"  {p:5d}  {a_p[p]:+5d}  {bad:>5s}")

    # Hasse check
    violations = [p for p in primes if p not in bad_primes and abs(a_p[p]) > 2*p**0.5+0.5]
    print(f"\n  Hasse violations: {len(violations)}")

    print(f"  Step 1 time: {time.time()-T0:.1f}s")
    return a_p, primes, bad_primes


# ═══════════════════════════════════════════════════════════════
# STEP 2: Build Dirichlet series and compute L(E,2)
# ═══════════════════════════════════════════════════════════════

def step2(a_p, primes, bad_primes):
    print(f"\n{'#' * 78}")
    print(f"  STEP 2: L(E,2) VIA DIRICHLET SERIES (100K TERMS)")
    print(f"{'#' * 78}")
    T0 = time.time()

    N_DIR = 100000
    mp.dps = 60

    # Build smallest prime factor sieve
    spf = list(range(N_DIR + 1))
    for p in primes:
        if p * p > N_DIR: break
        if spf[p] == p:
            for j in range(p*p, N_DIR+1, p):
                if spf[j] == j: spf[j] = p

    # Prime power table: a_{p^k}
    a_pk = {}
    for p in primes:
        if p > N_DIR: break
        ap = a_p.get(p, 0)
        a_pk[(p, 0)] = 1
        a_pk[(p, 1)] = ap
        pk = p * p
        prev2, prev1 = 1, ap
        k_exp = 2
        while pk <= N_DIR:
            if p in bad_primes:
                # Multiplicative reduction: a_{p^k} = a_p^k
                a_pk[(p, k_exp)] = prev1 * ap
            else:
                # Good reduction: a_{p^{k+1}} = a_p * a_{p^k} - p * a_{p^{k-1}}
                a_pk[(p, k_exp)] = ap * prev1 - p * prev2
            prev2, prev1 = prev1, a_pk[(p, k_exp)]
            pk *= p
            k_exp += 1

    # Build a_n by factorization
    t0 = time.time()
    a_n = [0] * (N_DIR + 1)
    a_n[1] = 1
    for n in range(2, N_DIR + 1):
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
    t1 = time.time()
    print(f"\n  Built {N_DIR} coefficients in {t1-t0:.1f}s")
    print(f"  a_1..a_20: {a_n[1:21]}")
    nz = sum(1 for i in range(1, N_DIR+1) if a_n[i] != 0)
    print(f"  Non-zero: {nz}/{N_DIR}")

    # Compute L(E,2) = sum a_n / n^2
    mp.dps = 60
    L_E2 = mpf(0)
    for n in range(1, N_DIR + 1):
        if a_n[n] != 0:
            L_E2 += mpf(a_n[n]) / mpf(n)**2

    print(f"\n  L(E,2) [{N_DIR} terms] = {nstr(L_E2, 40)}")

    # Convergence check
    print(f"\n  Partial sums:")
    for cut in [1000, 5000, 10000, 25000, 50000, 100000]:
        Lp = mpf(0)
        for n in range(1, min(cut, N_DIR) + 1):
            if a_n[n] != 0:
                Lp += mpf(a_n[n]) / mpf(n)**2
        print(f"    N={cut:7d}: {nstr(Lp, 35)}")

    # Euler product comparison
    L_euler = mpf(1)
    for p in primes:
        ap_ = a_p.get(p, 0)
        if p in bad_primes:
            fac = 1 - mpf(ap_) / p**2
        else:
            fac = 1 - mpf(ap_) / p**2 + mpf(1) / p**3
        if fac != 0:
            L_euler /= fac
    print(f"  L(E,2) Euler ({len(primes)} primes): {nstr(L_euler, 30)}")

    # Also compute L(E,1) since rank=0 so L(E,1) != 0
    # L(E,1) = sum a_n / n
    L_E1 = mpf(0)
    for n in range(1, N_DIR + 1):
        if a_n[n] != 0:
            L_E1 += mpf(a_n[n]) / mpf(n)
    print(f"\n  L(E,1) [{N_DIR} terms] = {nstr(L_E1, 30)}")
    # (convergence is slower for s=1)
    for cut in [10000, 50000, 100000]:
        Lp = mpf(0)
        for n in range(1, min(cut, N_DIR) + 1):
            if a_n[n] != 0:
                Lp += mpf(a_n[n]) / mpf(n)
        print(f"    N={cut:7d}: {nstr(Lp, 20)}")

    print(f"\n  Step 2 time: {time.time()-T0:.1f}s")
    return L_E2, L_E1, a_n, a_p


# ═══════════════════════════════════════════════════════════════
# STEP 3: PSLQ tests
# ═══════════════════════════════════════════════════════════════

def step3(L_E2, L_E1):
    print(f"\n{'#' * 78}")
    print(f"  STEP 3: PSLQ TESTS WITH L(E,2)")
    print(f"{'#' * 78}")

    mp.dps = 65
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=65)

    disc = mpf(1677)
    alpha_plus = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    log_ap = log(alpha_plus)
    sq163 = sqrt(mpf(163))

    # Compute m2
    def m2_integrand(theta):
        u = 41 - 2*cos(theta)
        return log((u + sqrt(u**2 - 4)) / 2)
    m2 = quad(m2_integrand, [0, 2*pi]) / (2*pi)

    print(f"\n  x       = {nstr(x, 50)}")
    print(f"  m2      = {nstr(m2, 50)}")
    print(f"  log(a+) = {nstr(log_ap, 50)}")
    print(f"  L(E,2)  = {nstr(L_E2, 40)}")
    print(f"  L(E,1)  = {nstr(L_E1, 30)}")

    # Main PSLQ: [x, L(E,2)/pi^2, L(E,2)/pi, m2, log(a+), sqrt163, pi, 1]
    print(f"\n  PSLQ-A: [x, L/pi2, L/pi, m2, log(a+), sqrt163, pi, 1]  bound 50K")
    names_a = ["x", "L/pi2", "L/pi", "m2", "log(a+)", "sqrt163", "pi", "1"]
    vals_a = [x, L_E2/pi**2, L_E2/pi, m2, log_ap, sq163, pi, mpf(1)]
    try:
        rel_a = pslq(vals_a, maxcoeff=50000, tol=mpf(10)**(-25))
    except Exception as e:
        rel_a = None
        print(f"    Error: {e}")
    _print_pslq("PSLQ-A", names_a, vals_a, rel_a)

    # PSLQ-B: x vs L(E,2) with fewer constants
    print(f"\n  PSLQ-B: [x, L/pi2, L, pi, sqrt163, 1]  bound 50K")
    names_b = ["x", "L/pi2", "L", "pi", "sqrt163", "1"]
    vals_b = [x, L_E2/pi**2, L_E2, pi, sq163, mpf(1)]
    try:
        rel_b = pslq(vals_b, maxcoeff=50000, tol=mpf(10)**(-25))
    except Exception:
        rel_b = None
    _print_pslq("PSLQ-B", names_b, vals_b, rel_b)

    # PSLQ-C: x vs m2 and L(E,2) together
    print(f"\n  PSLQ-C: [x, m2, L/pi2, log(a+), 1]  bound 100K")
    names_c = ["x", "m2", "L/pi2", "log(a+)", "1"]
    vals_c = [x, m2, L_E2/pi**2, log_ap, mpf(1)]
    try:
        rel_c = pslq(vals_c, maxcoeff=100000, tol=mpf(10)**(-25))
    except Exception:
        rel_c = None
    _print_pslq("PSLQ-C", names_c, vals_c, rel_c)

    return x, m2, log_ap


# ═══════════════════════════════════════════════════════════════
# STEP 4: Boyd residual vs L(E,1)
# ═══════════════════════════════════════════════════════════════

def step4(m2, log_ap, L_E1, L_E2):
    print(f"\n{'#' * 78}")
    print(f"  STEP 4: BOYD RESIDUAL vs L(E,1)")
    print(f"{'#' * 78}")

    mp.dps = 65
    disc = mpf(1677)
    alpha_minus = (41 - sqrt(disc)) / 2

    correction = m2 - log_ap
    # Product formula residual: m2 - log(a+) - sum log(1 - a-^{2n})
    product_sum = mpf(0)
    for n in range(1, 200):
        product_sum += log(1 - alpha_minus**(2*n))
    boyd_residual = correction - product_sum

    print(f"\n  correction = m2 - log(a+) = {nstr(correction, 40)}")
    print(f"  product sum (200 terms)   = {nstr(product_sum, 40)}")
    print(f"  Boyd residual             = {nstr(boyd_residual, 40)}")
    print(f"  |residual|                = {float(fabs(boyd_residual)):.15e}")

    print(f"\n  L(E,1) = {nstr(L_E1, 30)}")
    print(f"  L(E,2) = {nstr(L_E2, 30)}")

    # PSLQ: residual vs L(E,1)/pi
    print(f"\n  PSLQ: [residual, L(E,1)/pi, L(E,1), 1]")
    names_d1 = ["residual", "L(E,1)/pi", "L(E,1)", "1"]
    vals_d1 = [boyd_residual, L_E1/pi, L_E1, mpf(1)]
    try:
        rel_d1 = pslq(vals_d1, maxcoeff=100000, tol=mpf(10)**(-20))
    except Exception:
        rel_d1 = None
    _print_pslq("resid vs L1", names_d1, vals_d1, rel_d1)

    # PSLQ: residual vs L(E,2)/pi^2
    print(f"\n  PSLQ: [residual, L(E,2)/pi2, L(E,2)/pi, L(E,2), 1]")
    names_d2 = ["residual", "L/pi2", "L/pi", "L", "1"]
    vals_d2 = [boyd_residual, L_E2/pi**2, L_E2/pi, L_E2, mpf(1)]
    try:
        rel_d2 = pslq(vals_d2, maxcoeff=100000, tol=mpf(10)**(-20))
    except Exception:
        rel_d2 = None
    _print_pslq("resid vs L2", names_d2, vals_d2, rel_d2)

    # PSLQ: correction (not residual) vs L values
    print(f"\n  PSLQ: [correction, L(E,2)/pi2, L(E,1)/pi, Li2(a-^2), 1]")
    Li2_am2 = polylog(2, alpha_minus**2)
    names_d3 = ["corr", "L2/pi2", "L1/pi", "Li2(a-2)", "1"]
    vals_d3 = [correction, L_E2/pi**2, L_E1/pi, Li2_am2, mpf(1)]
    try:
        rel_d3 = pslq(vals_d3, maxcoeff=100000, tol=mpf(10)**(-20))
    except Exception:
        rel_d3 = None
    _print_pslq("corr vs L1+L2", names_d3, vals_d3, rel_d3)

    # Simple ratio checks
    print(f"\n  Ratio checks:")
    for name, val in [("L(E,1)", L_E1), ("L(E,1)/pi", L_E1/pi),
                      ("L(E,2)", L_E2), ("L(E,2)/pi2", L_E2/pi**2),
                      ("L(E,2)/(4pi2)", L_E2/(4*pi**2))]:
        if val != 0:
            r = boyd_residual / val
            print(f"    residual / {name:15s} = {nstr(r, 20)}")

    for name, val in [("L(E,2)/pi2", L_E2/pi**2), ("L(E,2)/(4pi2)", L_E2/(4*pi**2)),
                      ("L(E,1)/(2pi)", L_E1/(2*pi))]:
        if val != 0:
            r = correction / val
            print(f"    correction / {name:15s} = {nstr(r, 20)}")


# ═══════════════════════════════════════════════════════════════
# STEP 5: Identify quadratic twist
# ═══════════════════════════════════════════════════════════════

def step5(a_p_lmfdb, primes, bad_primes):
    print(f"\n{'#' * 78}")
    print(f"  STEP 5: IDENTIFY QUADRATIC TWIST")
    print(f"{'#' * 78}")

    # Compute a_p for our quartic Jacobian (resolvent cubic model)
    # y^2 = x^3 + (-75576267)x + (-252808806726)
    A_jac = -75576267
    B_jac = -252808806726

    a_p_jac = {}
    for p in primes:
        Ap = A_jac % p
        Bp = B_jac % p
        count = 0
        for xv in range(p):
            rhs = (xv**3 + Ap*xv + Bp) % p
            if rhs == 0:
                count += 1
            elif p > 2 and pow(rhs, (p-1)//2, p) == 1:
                count += 2
        a_p_jac[p] = p + 1 - (count + 1)

    # Print comparison
    print(f"\n  {'p':>5s}  {'a(Jac)':>7s}  {'a(LMFDB)':>9s}  {'ratio':>10s}")
    for p in primes[:30]:
        if p in bad_primes: continue
        aj = a_p_jac[p]
        al = a_p_lmfdb[p]
        if al != 0:
            r = aj / al
            print(f"  {p:5d}  {aj:+7d}  {al:+9d}  {r:+10.4f}")
        else:
            print(f"  {p:5d}  {aj:+7d}  {al:+9d}  {'undef':>10s}")

    # Test each candidate twist discriminant
    print(f"\n  Testing quadratic twist characters chi_d(p):")
    candidates = [-1, -3, -4, -5, 5, -7, -8, 8, -11, -15, 15,
                  -37, 37, -41, 41, -185, 185, -111, 111, -205, 205,
                  -1517, 1517, -1665, 1665, -1681, 1681, -1677, 1677]

    def kronecker(D, n):
        n = int(n)
        if n == 0: return 0
        D = int(D)
        result = 1
        if n < 0: n = -n; result = -result if D < 0 else result
        v = 0
        while n % 2 == 0: n //= 2; v += 1
        if v > 0:
            Dm8 = D % 8
            k2 = 1 if Dm8 in (1,7) else (-1 if Dm8 in (3,5) else 0)
            if v % 2 == 1: result *= k2
            if k2 == 0 and v > 0: return 0
        if n == 1: return result
        a = D % n
        if a < 0: a += n
        b = n; j = 1
        while a != 0:
            while a % 2 == 0:
                a //= 2
                if b % 8 in (3,5): j = -j
            a, b = b, a
            if a % 4 == 3 and b % 4 == 3: j = -j
            a = a % b
        return result * j if b == 1 else 0

    good_primes = [p for p in primes if p not in bad_primes and p > 2]

    for d in candidates:
        match_count = 0
        total = 0
        for p in good_primes[:50]:
            chi = kronecker(d, p)
            aj = a_p_jac[p]
            al = a_p_lmfdb[p]
            if chi != 0:
                total += 1
                if aj == chi * al:
                    match_count += 1
        if total > 0 and match_count == total:
            # Verify with more primes
            full_match = True
            for p in good_primes:
                chi = kronecker(d, p)
                if chi == 0: continue
                if a_p_jac[p] != chi * a_p_lmfdb[p]:
                    full_match = False
                    break
            if full_match:
                print(f"  *** d={d}: FULL MATCH (all {len(good_primes)} good primes) ***")
                print(f"      a_p(Jacobian) = chi_{d}(p) * a_p(22755.c3)")
            else:
                print(f"  d={d}: partial match {match_count}/{total} (failed full check)")
        elif total > 0 and match_count >= total - 2:
            print(f"  d={d}: near-match {match_count}/{total}")

    # Also check: maybe the Jacobian IS 22755.c3 without twist (just different model)
    direct_match = sum(1 for p in good_primes[:50] if a_p_jac[p] == a_p_lmfdb[p])
    print(f"\n  Direct match (no twist): {direct_match}/{min(50, len(good_primes))}")

    # Check negation: a_p(Jac) = -a_p(LMFDB)?
    neg_match = sum(1 for p in good_primes[:50] if a_p_jac[p] == -a_p_lmfdb[p])
    print(f"  Negation match: {neg_match}/{min(50, len(good_primes))}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    T0 = time.time()
    print(SEP)
    print("  L(E,2) COMPUTATION USING LMFDB CURVE 22755.c3")
    print(SEP)

    a_p, primes, bad_primes = step1()
    L_E2, L_E1, a_n, a_p_full = step2(a_p, primes, bad_primes)
    x, m2, log_ap = step3(L_E2, L_E1)
    step4(m2, log_ap, L_E1, L_E2)
    step5(a_p, primes, bad_primes)

    print(f"\n{'#' * 78}")
    print(f"  ALL STEPS COMPLETE — Total: {time.time()-T0:.1f}s")
    print(f"{'#' * 78}")

if __name__ == '__main__':
    main()
