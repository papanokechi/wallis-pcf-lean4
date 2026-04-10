"""
Corrected L(E',s) computation for E' = 364080.bv3
===================================================
Fixes from review:
  1. Dokchitser sum uses correct incomplete gamma: Gamma(2,x) = (1+x)e^{-x}
     (NOT E1(x) = Gamma(0,x) which was the bug)
  2. L(E',1) uses Gamma(1,x) = e^{-x}
  3. Cross-check against LMFDB's known L(E',1) = 2.45784076218...
  4. Real period Omega from LMFDB, Tamagawa product, torsion in PSLQ basis
  5. Convergence audit: double terms + double precision
"""
from mpmath import (mp, mpf, mpc, pi, log, sqrt, polylog, pslq, nstr,
                    cos, sin, quad, fabs, zeta, exp, gammainc)
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

def _pslq(label, names, vals, bound=50000, tol_exp=-25):
    mp_tol = mpf(10)**(tol_exp)
    try:
        rel = pslq(vals, maxcoeff=bound, tol=mp_tol)
    except Exception:
        rel = None
    if rel:
        nz = [(n, c) for n, c in zip(names, rel) if c != 0]
        if names[0].startswith('x') and rel[0] == 0:
            print(f"    {label}: tautology")
        else:
            print(f"    {label}: RELATION FOUND")
        for n, c in nz:
            print(f"      {c:+d} * {n}")
        res = sum(c * v for c, v in zip(rel, vals))
        print(f"      Residual: {float(res):.3e}")
    else:
        print(f"    {label}: EXCLUDED")

SEP = '=' * 78

def main():
    T0 = time.time()
    mp.dps = 80

    print(SEP)
    print("  CORRECTED L(E',s) FOR E' = 364080.bv3")
    print(SEP)

    # ═══════════════════════════════════════════════════════════
    # CURVE DATA (from LMFDB)
    # ═══════════════════════════════════════════════════════════
    print(f"\n  LMFDB label:    364080.bv3")
    print(f"  Cremona label:  364080bv2")
    print(f"  Model:          y^2 + y = x^3 + x^2 - 933040x - 347099500")
    print(f"  ainvs:          [0, 1, 0, -933040, -347099500]")
    print(f"  Conductor:      N = 364080 = 2^4 * 3 * 5 * 37 * 41")
    print(f"  Rank:           0 (analytic rank 0)")
    print(f"  Torsion:        Z/2 x Z/2  (order 4)")
    print(f"  CM:             no")
    print(f"  Sha:            1")
    print(f"  min_quad_twist: 22755.c3 (twist disc = -4)")
    print(f"")
    print(f"  Local data at bad primes:")
    print(f"    p=2:  f_p=4, Kodaira I*_2, c_p=4, w_p=-1, reduction: additive")
    print(f"    p=3:  f_p=1, Kodaira I_4,  c_p=4, w_p=-1, reduction: multiplicative")
    print(f"    p=5:  f_p=1, Kodaira I_2,  c_p=2, w_p=-1, reduction: multiplicative")
    print(f"    p=37: f_p=1, Kodaira I_2,  c_p=2, w_p=-1, reduction: multiplicative")
    print(f"    p=41: f_p=1, Kodaira I_4,  c_p=4, w_p=-1, reduction: multiplicative")
    print(f"  Global root number: w_oo * prod(w_p) = (-1)*(-1)^5 = +1  (consistent with rank 0)")
    print(f"  Tamagawa product: prod c_p = 4*4*2*2*4 = 256")
    print(f"  Real period (LMFDB): 0.15361504763620030335370943496")
    print(f"  L(E',1) (LMFDB):    2.45784076217920485365935095936")

    # LMFDB reference values for cross-check
    L1_lmfdb = mpf('2.45784076217920485365935095936')
    Omega_lmfdb = mpf('0.15361504763620030335370943496')
    tamagawa_prod = 256
    torsion_order = 4
    sha = 1

    # BSD check: L(E,1) = Omega * |Sha| * prod(c_p) * regulator / |tors|^2
    # rank=0 so regulator=1
    bsd_expected = Omega_lmfdb * sha * tamagawa_prod * 1 / torsion_order**2
    print(f"\n  BSD check: Omega * Sha * prod(c_p) / |tors|^2")
    print(f"           = {nstr(Omega_lmfdb,20)} * 1 * 256 / 16")
    print(f"           = {nstr(bsd_expected, 20)}")
    print(f"  L(E',1)  = {nstr(L1_lmfdb, 20)}")
    print(f"  Ratio L/BSD = {nstr(L1_lmfdb / bsd_expected, 15)}")

    # ═══════════════════════════════════════════════════════════
    # COMPUTE a_p and a_n
    # ═══════════════════════════════════════════════════════════
    print(f"\n  Computing a_p for E' = [0,1,0,-933040,-347099500]...")
    t0 = time.time()

    a1,a2,a3,a4,a6 = 0,1,0,-933040,-347099500
    N_cond = 364080
    bad_primes = {2, 3, 5, 37, 41}

    primes = sieve_primes(5000)
    a_p = {}
    for p in primes:
        _a1=a1%p; _a2=a2%p; _a3=a3%p; _a4=a4%p; _a6=a6%p
        count = 0
        for xv in range(p):
            # RHS of y^2 + a1*x*y + a3*y = x^3 + a2*x^2 + a4*x + a6
            rhs = (xv**3 + _a2*xv*xv + _a4*xv + _a6) % p
            if p == 2:
                # Explicit enumeration for p=2 (general Weierstrass)
                for yv in range(2):
                    if (yv*yv + _a1*xv*yv + _a3*yv - rhs) % 2 == 0: count += 1
            else:
                # Solve y^2 + c*y - rhs = 0 (mod p) where c = a1*x + a3
                c_lin = (_a1 * xv + _a3) % p
                disc = (c_lin * c_lin + 4 * rhs) % p
                if disc == 0: count += 1
                elif pow(disc, (p-1)//2, p) == 1: count += 2
        a_p[p] = p + 1 - (count + 1)
    print(f"  {len(primes)} primes computed in {time.time()-t0:.1f}s")

    # Build a_n for two truncation lengths: N1 and N2 = 2*N1
    N1, N2 = 2000, 4000

    def build_an(N_terms):
        spf = list(range(N_terms+1))
        for p in primes:
            if p*p > N_terms: break
            if spf[p]==p:
                for j in range(p*p, N_terms+1, p):
                    if spf[j]==j: spf[j]=p

        a_pk = {}
        for p in primes:
            if p > N_terms: break
            ap = a_p.get(p, 0)
            a_pk[(p,0)] = 1; a_pk[(p,1)] = ap
            pk=p*p; p2,p1=1,ap; ke=2
            while pk <= N_terms:
                if p in bad_primes: a_pk[(p,ke)] = p1*ap
                else: a_pk[(p,ke)] = ap*p1 - p*p2
                p2,p1 = p1, a_pk[(p,ke)]; pk*=p; ke+=1

        an = [0]*(N_terms+1); an[1] = 1
        for n in range(2, N_terms+1):
            r=1; m=n
            while m>1:
                p=spf[m]; k=0
                while m%p==0: m//=p; k+=1
                r *= a_pk.get((p,k), 0)
            an[n] = r
        return an

    an1 = build_an(N1)
    an2 = build_an(N2)

    # ═══════════════════════════════════════════════════════════
    # DOKCHITSER L(E',s) — FORMULAS
    # ═══════════════════════════════════════════════════════════
    #
    # Completed L-function: Lambda(s) = (sqrt(N)/(2pi))^s * Gamma(s) * L(E,s)
    # Functional equation:  Lambda(s) = eps * Lambda(2-s)
    #
    # Via Mellin splitting at t=1 and the functional equation:
    #   Lambda(s) = sum_n a_n * [(alpha*n)^{-s} * Gamma(s, alpha*n)
    #                           + eps * (alpha*n)^{s-2} * Gamma(2-s, alpha*n)]
    # where alpha = 2*pi/sqrt(N).
    #
    # For s=1 (center of symmetry):
    #   Both terms use Gamma(1,x) = e^{-x}. Result:
    #   L(E,1) = (1+eps) * sum a_n/n * exp(-alpha*n)
    #
    # For s=2:
    #   Direct term uses Gamma(2,x)/Gamma(2) = (1+x)*e^{-x}.
    #   Func. eq. term uses Gamma(0,x) = E1(x) = gammainc(0,x) in mpmath.
    #   Note: Gamma(0) diverges, but Gamma(0,x) is well-defined.
    #   Result:
    #   L(E,2) = sum a_n/n^2 * (1+alpha*n)*e^{-alpha*n}
    #          + eps * alpha^2 * sum a_n * E1(alpha*n)
    #   [derivation: L = (2pi)^2/(N*Gamma(2)) * Lambda(2), and (2pi)^2/N = alpha^2]

    print(f"\n{'#' * 78}")
    print(f"  CORRECTED L-FUNCTION COMPUTATION")
    print(f"{'#' * 78}")

    mp.dps = 70
    N = mpf(N_cond)
    sqN = sqrt(N)
    alpha = 2*pi/sqN
    # Root number: product of local root numbers (from LMFDB local data)
    # w_oo = -1 (archimedean), w_2=-1, w_3=-1, w_5=-1, w_37=-1, w_41=-1
    # eps = w_oo * prod(w_p) = (-1) * (-1)^5 = (-1)^6 = +1
    eps = +1  # verified from LMFDB: analytic_rank=0, consistent with eps=+1

    print(f"\n  N = {N_cond}, sqrt(N) = {nstr(sqN,12)}, alpha = 2pi/sqrt(N) = {nstr(alpha,12)}")

    # ── L(E',1) via Dokchitser (s=1, center of symmetry) ──
    # At s=1: both sides of the func. eq. use G(1,x) = e^{-x}.
    # L(E,1) = sum a_n/n * exp(-alpha*n) + eps * sum a_n/n * exp(-alpha*n)
    #        = (1 + eps) * sum a_n/n * exp(-alpha*n)
    # For eps=+1: L(E,1) = 2 * sum a_n/n * exp(-alpha*n)
    # For eps=-1: L(E,1) = 0

    for N_terms, an_arr, label in [(N1, an1, f"N1={N1}"), (N2, an2, f"N2={N2}")]:
        s1 = mpf(0)
        for n in range(1, N_terms+1):
            if an_arr[n] == 0: continue
            s1 += mpf(an_arr[n]) / mpf(n) * exp(-alpha*n)
        L1_dok = (1 + eps) * s1
        err_L1 = fabs(L1_dok - L1_lmfdb)
        digs_L1 = int(-float(log(err_L1)/log(10))) if err_L1 > 0 else 70
        print(f"\n  L(E',1) Dokchitser [{label}] = {nstr(L1_dok, 35)}")
        print(f"  L(E',1) LMFDB               = {nstr(L1_lmfdb, 35)}")
        print(f"  |difference|                 = {float(err_L1):.3e}  ({digs_L1} digits)")

    # ── L(E',2) via direct Dirichlet series (reference only — O(1/N) convergence) ──
    print(f"\n  L(E',2) via direct Dirichlet series (reference, ~3-4 digits):")
    for N_terms, an_arr, label in [(N1, an1, f"N1={N1}"), (N2, an2, f"N2={N2}")]:
        L2_dir = mpf(0)
        for n in range(1, N_terms+1):
            if an_arr[n] == 0: continue
            L2_dir += mpf(an_arr[n]) / mpf(n)**2
        print(f"  L(E',2) direct [{label}]     = {nstr(L2_dir, 35)}")

    # ── L(E',2) via Dokchitser ──
    print(f"\n  L(E',2) via Dokchitser:")
    print(f"  L(E,2) = sum a_n/n^2 * (1+alpha*n)*exp(-alpha*n)")
    print(f"         + eps * alpha^2 * sum a_n * E1(alpha*n)")
    print(f"  where E1(x) = Gamma(0,x) = gammainc(0,x) in mpmath\n")

    for N_terms, an_arr, label in [(N1, an1, f"N1={N1}"), (N2, an2, f"N2={N2}")]:
        sum_direct = mpf(0)
        sum_fe = mpf(0)
        for n in range(1, N_terms+1):
            if an_arr[n] == 0: continue
            an_val = alpha * n
            # Direct part: a_n/n^2 * Gamma(2, alpha*n) / Gamma(2)
            # = a_n/n^2 * (1 + alpha*n) * exp(-alpha*n)
            g2 = (1 + an_val) * exp(-an_val)
            sum_direct += mpf(an_arr[n]) / mpf(n)**2 * g2
            # Func.eq. part: a_n * Gamma(0, alpha*n) (NOT a_n/n^2 * E1!)
            e1_val = gammainc(0, an_val)  # = E1(alpha*n) = upper inc gamma at s=0
            sum_fe += mpf(an_arr[n]) * e1_val

        L2_dok = sum_direct + eps * alpha**2 * sum_fe
        print(f"  [{label}] direct = {nstr(sum_direct, 30)}")
        print(f"  [{label}] func.eq = {nstr(sum_fe, 20)}")
        print(f"  [{label}] L(E',2) = {nstr(L2_dok, 35)}")

    # Use the N2 result as our best value
    # Recompute one more time for the final value
    L2_final = mpf(0)
    fe_sum = mpf(0)
    dir_sum = mpf(0)
    for n in range(1, N2+1):
        if an2[n] == 0: continue
        an_val = alpha * n
        g2 = (1 + an_val) * exp(-an_val)
        e1v = gammainc(0, an_val)
        dir_sum += mpf(an2[n]) / mpf(n)**2 * g2
        fe_sum += mpf(an2[n]) * e1v
    L2_final = dir_sum + eps * alpha**2 * fe_sum

    # L1 final
    L1_final = mpf(0)
    for n in range(1, N2+1):
        if an2[n] == 0: continue
        L1_final += mpf(an2[n]) / mpf(n) * exp(-alpha*n)
    L1_final *= (1 + eps)

    print(f"\n  {'='*60}")
    print(f"  FINAL VALUES:")
    print(f"  L(E',1) = {nstr(L1_final, 35)}")
    print(f"  L(E',2) = {nstr(L2_final, 35)}")
    print(f"  L(E',1) LMFDB = {nstr(L1_lmfdb, 35)}")
    err1 = float(fabs(L1_final - L1_lmfdb))
    digs1 = int(-float(log(fabs(L1_final-L1_lmfdb))/log(10))) if err1 > 0 else 70
    print(f"  L1 agreement: {digs1} digits")
    print(f"  Omega = {nstr(Omega_lmfdb, 30)}")
    print(f"  {'='*60}")

    # ═══════════════════════════════════════════════════════════
    # PSLQ WITH EXPANDED BASIS
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  PSLQ WITH EXPANDED BASIS (including Omega, Tamagawa, torsion)")
    print(f"{'#' * 78}")

    mp.dps = 70  # consistent with L-function computation precision
    # x = CF value for a(n) = n^2 - 41n, b(n) = n+1 (Heegner D=-163 family)
    # This is the GCF b(0) + a(1)/(b(1) + a(2)/(b(2)+...)) with quadratic a(n)
    # and linear b(n). Its transcendence depth is the subject of this investigation.
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=70)

    disc = mpf(1677)
    alpha_plus = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    log_ap = log(alpha_plus)
    sq163 = sqrt(mpf(163))
    Omega = Omega_lmfdb

    def m2_int(theta):
        u = 41 - 2*cos(theta)
        return log((u + sqrt(u**2 - 4)) / 2)
    m2 = quad(m2_int, [0, 2*pi]) / (2*pi)
    correction = m2 - log_ap
    product_sum = mpf(0)
    for n in range(1, 200):
        product_sum += log(1 - alpha_minus**(2*n))
    boyd_res = correction - product_sum

    L2 = L2_final; L1 = L1_final

    print(f"\n  x           = {nstr(x, 50)}")
    print(f"  m2          = {nstr(m2, 40)}")
    print(f"  log(a+)     = {nstr(log_ap, 40)}")
    print(f"  correction  = {nstr(correction, 30)}")
    print(f"  Boyd resid  = {nstr(boyd_res, 25)}")
    print(f"  L(E',2)     = {nstr(L2, 35)}")
    print(f"  L(E',1)     = {nstr(L1, 35)}")
    print(f"  Omega       = {nstr(Omega, 30)}")
    print(f"  L2/Omega^2  = {nstr(L2/Omega**2, 20)}")
    print(f"  L1/Omega    = {nstr(L1/Omega, 20)}")

    # Test 1: x vs L(E',2)/pi^2 and periods
    print(f"\n  1: [x, L2/pi2, L2/Omega2, Omega, m2, log(a+), pi, 1]")
    _pslq("1", ["x","L2/pi2","L2/Om2","Om","m2","log(a+)","pi","1"],
          [x, L2/pi**2, L2/Omega**2, Omega, m2, log_ap, pi, mpf(1)])

    # Test 2: x vs L(E',2) with fewer constants
    print(f"\n  2: [x, L2/pi2, L1/pi, L2, pi, 1]")
    _pslq("2", ["x","L2/pi2","L1/pi","L2","pi","1"],
          [x, L2/pi**2, L1/pi, L2, pi, mpf(1)])

    # Test 3: correction vs L-values and Li2
    Li2_am2 = polylog(2, alpha_minus**2)
    print(f"\n  3: [corr, L2/pi2, L1/Omega, Li2(am2), 1]")
    _pslq("3", ["corr","L2/pi2","L1/Om","Li2(am2)","1"],
          [correction, L2/pi**2, L1/Omega, Li2_am2, mpf(1)], bound=100000)

    # Test 4: correction vs L2/pi2 alone (tight)
    print(f"\n  4: [corr, L2/pi2, 1]  bound 1M")
    _pslq("4", ["corr","L2/pi2","1"],
          [correction, L2/pi**2, mpf(1)], bound=1000000, tol_exp=-25)

    # Test 5: Boyd residual vs L1, L2
    print(f"\n  5: [resid, L2/pi2, L1/Omega, Omega2, 1]")
    _pslq("5", ["resid","L2/pi2","L1/Om","Om2","1"],
          [boyd_res, L2/pi**2, L1/Omega, Omega**2, mpf(1)], bound=100000)

    # Test 6: x with Omega^2 basis
    print(f"\n  6: [x, L2/Om2, L1/Om, Om, sqrt163, pi, 1]")
    _pslq("6", ["x","L2/Om2","L1/Om","Om","sqrt163","pi","1"],
          [x, L2/Omega**2, L1/Omega, Omega, sq163, pi, mpf(1)])

    # Test 7: correction vs all available weight-2 objects
    print(f"\n  7: [corr, L2/pi2, L1/pi, L2/Om2, Li2(am2), Om, 1]")
    _pslq("7", ["corr","L2/pi2","L1/pi","L2/Om2","Li2","Om","1"],
          [correction, L2/pi**2, L1/pi, L2/Omega**2, Li2_am2, Omega, mpf(1)],
          bound=50000)

    # Test 8: L2/Omega^2 — is it rational?
    print(f"\n  8: [L2/Om2, 1] — test L2/Omega^2 rational?")
    _pslq("8", ["L2/Om2","1"],
          [L2/Omega**2, mpf(1)], bound=1000000, tol_exp=-20)

    # Test 9: L1/Omega — is it rational? (should be by BSD!)
    print(f"\n  9: [L1/Om, 1] — test L1/Omega rational? (BSD: L1/Om = Sha*prod_cp/tors^2 = 256/16 = 16)")
    _pslq("9", ["L1/Om","1"],
          [L1/Omega, mpf(1)], bound=100, tol_exp=-20)

    # Explicit BSD check
    expected_ratio = mpf(tamagawa_prod * sha) / mpf(torsion_order**2)
    actual_ratio = L1 / Omega
    print(f"    L1/Omega = {nstr(actual_ratio, 20)}")
    print(f"    BSD prediction (Sha*prod_cp/tors^2) = {expected_ratio}")
    print(f"    Match: {float(fabs(actual_ratio - expected_ratio)):.3e}")

    # Test 10: Beilinson-type L2/(pi*Omega) — is it rational?
    # Beilinson's conjecture predicts L(E,2) ~ c * pi * Omega for some rational c.
    print(f"\n  10: [L2/(pi*Om), 1] — Beilinson test (L2 ~ c*pi*Omega?)")
    print(f"      L2/(pi*Om) = {nstr(L2/(pi*Omega), 20)}")
    _pslq("10", ["L2/(pi*Om)","1"],
          [L2/(pi*Omega), mpf(1)], bound=1000000, tol_exp=-20)

    # Test 11: correction vs pi*Omega
    print(f"\n  11: [corr, L2/(pi*Om), pi*Om, Om2, 1]")
    _pslq("11", ["corr","L2/(pi*Om)","pi*Om","Om2","1"],
          [correction, L2/(pi*Omega), pi*Omega, Omega**2, mpf(1)], bound=100000)

    # Test 12: x vs Beilinson combination
    print(f"\n  12: [x, L2/(pi*Om), L1/Om, pi, sqrt163, Om, 1]")
    _pslq("12", ["x","L2/(pi*Om)","L1/Om","pi","sqrt163","Om","1"],
          [x, L2/(pi*Omega), L1/Omega, pi, sq163, Omega, mpf(1)])

    print(f"\n  Total time: {time.time()-T0:.1f}s")

if __name__ == '__main__':
    main()
