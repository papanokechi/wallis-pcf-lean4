"""
Heegner D=-163: Extended PSLQ tests
====================================
Adds to the corrected L-function computation:
  1. Dirichlet L-series L(chi_{-163}, 1) and L(chi_{-163}, 2)
  2. Bloch-Wigner dilogarithm D(z) at z = (1+sqrt(-163))/2
  3. Broadened regulator basis with log terms
  4. Kitchen-sink PSLQ
"""
from mpmath import (mp, mpf, mpc, pi, log, sqrt, polylog, pslq, nstr,
                    cos, sin, quad, fabs, zeta, exp, gammainc, im, re, arg,
                    loggamma)
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

def kronecker_symbol(D, n):
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

def bloch_wigner(z):
    """Bloch-Wigner dilogarithm D(z) = Im(Li_2(z)) + arg(1-z) * log|z|."""
    li2 = polylog(2, z)
    return im(li2) + arg(1 - z) * log(abs(z))

def _pslq(label, names, vals, bound=50000, tol_exp=-25):
    mp_tol = mpf(10)**(tol_exp)
    try:
        rel = pslq(vals, maxcoeff=bound, tol=mp_tol)
    except Exception:
        rel = None
    if rel:
        nz = [(n, c) for n, c in zip(names, rel) if c != 0]
        if len(names) > 0 and names[0].startswith('x') and rel[0] == 0:
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
    mp.dps = 70

    print(SEP)
    print("  EXTENDED PSLQ: Dirichlet L, Bloch-Wigner, Regulator basis")
    print(SEP)

    # ═══════════════════════════════════════════════════════════
    # KNOWN VALUES (from previous corrected computation)
    # ═══════════════════════════════════════════════════════════
    L1_lmfdb = mpf('2.45784076217920485365935095936')
    Omega = mpf('0.15361504763620030335370943496')

    # Reuse Dokchitser L(E',2) from previous run
    # L(E',2) = 1.1233078742712014688 (13 digits stable from Dokchitser)
    # We'll recompute it here for self-containment.
    print(f"\n  Recomputing L(E',2) via Dokchitser...")

    a1,a2,a3,a4,a6 = 0,1,0,-933040,-347099500
    N_cond = 364080
    bad_primes_E = {2, 3, 5, 37, 41}

    primes = sieve_primes(5000)
    a_p = {}
    t0 = time.time()
    for p in primes:
        _a1=a1%p; _a2=a2%p; _a3=a3%p; _a4=a4%p; _a6=a6%p
        count = 0
        for xv in range(p):
            rhs = (xv**3 + _a2*xv*xv + _a4*xv + _a6) % p
            if p == 2:
                for yv in range(2):
                    if (yv*yv + _a1*xv*yv + _a3*yv - rhs) % 2 == 0: count += 1
            else:
                c_lin = (_a1*xv + _a3) % p
                disc = (c_lin*c_lin + 4*rhs) % p
                if disc == 0: count += 1
                elif pow(disc, (p-1)//2, p) == 1: count += 2
        a_p[p] = p + 1 - (count + 1)
    print(f"  a_p for {len(primes)} primes: {time.time()-t0:.1f}s")

    N_terms = 4000
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
            if p in bad_primes_E: a_pk[(p,ke)] = p1*ap
            else: a_pk[(p,ke)] = ap*p1 - p*p2
            p2,p1 = p1, a_pk[(p,ke)]; pk*=p; ke+=1
    a_n = [0]*(N_terms+1); a_n[1] = 1
    for n in range(2, N_terms+1):
        r=1; m=n
        while m>1:
            p=spf[m]; k=0
            while m%p==0: m//=p; k+=1
            r *= a_pk.get((p,k), 0)
        a_n[n] = r

    N = mpf(N_cond); sqN = sqrt(N); alpha = 2*pi/sqN
    eps = +1

    # L(E',2) Dokchitser
    dir_sum = mpf(0); fe_sum = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] == 0: continue
        an_val = alpha * n
        dir_sum += mpf(a_n[n]) / mpf(n)**2 * (1 + an_val) * exp(-an_val)
        fe_sum += mpf(a_n[n]) * gammainc(0, an_val)
    L2 = dir_sum + eps * alpha**2 * fe_sum

    # L(E',1) Dokchitser
    s1 = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] == 0: continue
        s1 += mpf(a_n[n]) / mpf(n) * exp(-alpha*n)
    L1 = (1 + eps) * s1

    print(f"  L(E',2) = {nstr(L2, 30)}")
    print(f"  L(E',1) = {nstr(L1, 30)}")
    print(f"  L(E',1) LMFDB = {nstr(L1_lmfdb, 30)}")
    err = float(fabs(L1 - L1_lmfdb))
    print(f"  L1 agreement: {int(-float(log(fabs(L1-L1_lmfdb))/log(10))) if err > 0 else 70} digits")

    # ═══════════════════════════════════════════════════════════
    # 1. DIRICHLET L-SERIES L(chi_{-163}, s) at s=1 and s=2
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  1. DIRICHLET L(chi_{{-163}}, s)")
    print(f"{'#' * 78}")

    # L(chi_{-163}, 1) = pi / sqrt(163)  [exact, class number formula: h(-163)=1]
    L_chi_1_exact = pi / sqrt(mpf(163))
    print(f"\n  L(chi_{{-163}}, 1) = pi/sqrt(163) = {nstr(L_chi_1_exact, 30)}")

    # L(chi_{-163}, 2) via direct summation (50K terms)
    print(f"  Computing L(chi_{{-163}}, 2) via 50000 terms...")
    t0 = time.time()
    L_chi_2 = mpf(0)
    for n in range(1, 50001):
        chi = kronecker_symbol(-163, n)
        if chi != 0:
            L_chi_2 += mpf(chi) / mpf(n)**2
    print(f"  L(chi_{{-163}}, 2) = {nstr(L_chi_2, 30)}  ({time.time()-t0:.1f}s)")

    # The exact value: L(chi_{-163}, 2) = pi^2 * h / (6 * sqrt(163) * ...)
    # For D=-163 (class number 1), L(chi_D, 2) has a known closed form
    # involving Clausen functions, but let's just use the numerical value.
    print(f"  L_chi_2 / pi^2 = {nstr(L_chi_2/pi**2, 20)}")
    print(f"  L_chi_2 * sqrt(163) / pi^2 = {nstr(L_chi_2*sqrt(mpf(163))/pi**2, 20)}")

    # ═══════════════════════════════════════════════════════════
    # 2. BLOCH-WIGNER DILOGARITHM at Heegner point
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  2. BLOCH-WIGNER DILOGARITHM D(z)")
    print(f"{'#' * 78}")

    # Heegner point: z = (1 + sqrt(-163))/2 (generator of ring of integers of Q(sqrt(-163)))
    z_heeg = (1 + sqrt(mpc(0, 1)) * sqrt(mpf(163))) / 2
    print(f"\n  z = (1 + sqrt(-163))/2 = {nstr(z_heeg, 20)}")

    D_z = bloch_wigner(z_heeg)
    print(f"  D(z) = Im(Li_2(z)) + arg(1-z)*log|z|")
    print(f"  D(z) = {nstr(D_z, 30)}")

    # Also compute D at related points
    # z_bar = (1 - sqrt(-163))/2
    z_bar = (1 - sqrt(mpc(0, 1)) * sqrt(mpf(163))) / 2
    D_zbar = bloch_wigner(z_bar)
    print(f"  D(z_bar) = {nstr(D_zbar, 30)}")
    print(f"  D(z) + D(z_bar) = {nstr(D_z + D_zbar, 15)}  (should be 0 by symmetry)")

    # Also alpha_minus = (41-sqrt(1677))/2 as a real argument
    alpha_minus = (41 - sqrt(mpf(1677))) / 2
    D_am = bloch_wigner(alpha_minus)  # real argument: D(x) = Im(Li_2(x)) = 0 for real x in (0,1)
    print(f"\n  alpha- = {nstr(alpha_minus, 20)}")
    print(f"  D(alpha-) = {nstr(D_am, 20)}  (0 for real arguments)")

    # The Clausen function Cl_2(theta) is related: Cl_2(theta) = -int_0^theta log|2sin(t/2)| dt
    # = Im(Li_2(e^{i*theta}))
    # For the Heegner discriminant, the relevant value is:
    # D(e^{2*pi*i/163}) or similar
    theta_163 = 2*pi / 163
    z_unit = exp(mpc(0, 1) * theta_163)
    D_unit = bloch_wigner(z_unit)
    Cl2_163 = im(polylog(2, z_unit))  # = Cl_2(2*pi/163)
    print(f"\n  Cl_2(2*pi/163) = Im(Li_2(e^{{2*pi*i/163}})) = {nstr(Cl2_163, 30)}")
    print(f"  D(e^{{2pi*i/163}}) = {nstr(D_unit, 30)}")

    # ═══════════════════════════════════════════════════════════
    # 3. COMPUTE x, m2, correction, Boyd residual
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  3. CF VALUE AND MAHLER MEASURE")
    print(f"{'#' * 78}")

    # x = CF value for a(n) = n^2 - 41n, b(n) = n+1 (Heegner D=-163 family)
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=70)

    disc = mpf(1677)
    alpha_plus = (41 + sqrt(disc)) / 2
    log_ap = log(alpha_plus)
    sq163 = sqrt(mpf(163))

    def m2_int(theta):
        u = 41 - 2*cos(theta)
        return log((u + sqrt(u**2 - 4)) / 2)
    m2 = quad(m2_int, [0, 2*pi]) / (2*pi)
    correction = m2 - log_ap

    product_sum = mpf(0)
    for n in range(1, 200):
        product_sum += log(1 - alpha_minus**(2*n))
    boyd_res = correction - product_sum

    Li2_am2 = polylog(2, alpha_minus**2)

    print(f"\n  x           = {nstr(x, 50)}")
    print(f"  m2          = {nstr(m2, 35)}")
    print(f"  log(a+)     = {nstr(log_ap, 35)}")
    print(f"  correction  = {nstr(correction, 25)}")
    print(f"  Boyd resid  = {nstr(boyd_res, 20)}")
    print(f"  Li2(am^2)   = {nstr(Li2_am2, 25)}")

    # ═══════════════════════════════════════════════════════════
    # 4. PSLQ — DIRICHLET L-SERIES TESTS
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  4. PSLQ WITH DIRICHLET L-VALUES")
    print(f"{'#' * 78}")

    # Test 13: x vs Dirichlet L-values
    print(f"\n  13: [x, L_chi2/pi2, L_chi1, L2/pi2, pi, sqrt163, 1]")
    _pslq("13", ["x","Lchi2/pi2","Lchi1","L2/pi2","pi","sqrt163","1"],
          [x, L_chi_2/pi**2, L_chi_1_exact, L2/pi**2, pi, sq163, mpf(1)])

    # Test 14: correction vs Dirichlet L(chi,-163, 2)
    print(f"\n  14: [corr, L_chi2/pi2, L2/pi2, Li2(am2), 1]")
    _pslq("14", ["corr","Lchi2/pi2","L2/pi2","Li2(am2)","1"],
          [correction, L_chi_2/pi**2, L2/pi**2, Li2_am2, mpf(1)], bound=100000)

    # Test 15: Boyd residual vs Dirichlet
    print(f"\n  15: [resid, L_chi2/pi2, L_chi1/pi, L2/pi2, 1]")
    _pslq("15", ["resid","Lchi2/pi2","Lchi1/pi","L2/pi2","1"],
          [boyd_res, L_chi_2/pi**2, L_chi_1_exact/pi, L2/pi**2, mpf(1)], bound=100000)

    # Test 16: L(E',2) vs L(chi, 2) and Omega
    print(f"\n  16: [L2, L_chi2, pi*Om, pi2, Om2, 1]")
    _pslq("16", ["L2","Lchi2","pi*Om","pi2","Om2","1"],
          [L2, L_chi_2, pi*Omega, pi**2, Omega**2, mpf(1)])

    # Test 17: L(E',2)/(pi^2) vs L(chi_{-163}, 2)/(pi^2) — are they Q-linearly related?
    print(f"\n  17: [L2/pi2, Lchi2/pi2, 1]  bound 1M")
    _pslq("17", ["L2/pi2","Lchi2/pi2","1"],
          [L2/pi**2, L_chi_2/pi**2, mpf(1)], bound=1000000, tol_exp=-20)

    # ═══════════════════════════════════════════════════════════
    # 5. PSLQ — BLOCH-WIGNER TESTS
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  5. PSLQ WITH BLOCH-WIGNER DILOGARITHM")
    print(f"{'#' * 78}")

    # Test 18: L(E',2) vs D(z_heeg) (Deninger-type)
    # m(P_k) should relate to D(z)/pi for some algebraic z
    print(f"\n  D(z_heeg) = {nstr(D_z, 25)}")
    print(f"  Cl2(2pi/163) = {nstr(Cl2_163, 25)}")

    print(f"\n  18: [L2, D(z), pi*Om, pi2, 1]")
    _pslq("18", ["L2","D(z)","pi*Om","pi2","1"],
          [L2, D_z, pi*Omega, pi**2, mpf(1)])

    # Test 19: correction vs D(z)/pi
    print(f"\n  19: [corr, D(z)/pi, Cl2/pi, Li2(am2), 1]")
    _pslq("19", ["corr","D(z)/pi","Cl2/pi","Li2(am2)","1"],
          [correction, D_z/pi, Cl2_163/pi, Li2_am2, mpf(1)], bound=100000)

    # Test 20: m2 vs D(z)/pi (the RV formula: m(P_k) = r * D(z)/pi for some r in Q)
    print(f"\n  20: [m2, D(z)/pi, log(a+), 1]  bound 100K")
    _pslq("20", ["m2","D(z)/pi","log(a+)","1"],
          [m2, D_z/pi, log_ap, mpf(1)], bound=100000)

    # Test 21: D(z) vs L(chi_{-163}, 2) — Zagier's formula
    # The Dedekind zeta at s=2 involves D(z). For Q(sqrt{-163}):
    # zeta_K(2) = (pi^2/6) * L(chi_{-163}, 2) and also involves D(z)
    print(f"\n  21: [D(z), Lchi2, pi2, sqrt163, 1]")
    _pslq("21", ["D(z)","Lchi2","pi2","sqrt163","1"],
          [D_z, L_chi_2, pi**2, sq163, mpf(1)])

    # ═══════════════════════════════════════════════════════════
    # 6. BROADENED REGULATOR BASIS (kitchen-sink)
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  6. KITCHEN-SINK PSLQ")
    print(f"{'#' * 78}")

    log163 = log(mpf(163))

    # Test 22: x vs everything
    print(f"\n  22: [x, L2/pi2, L_chi2/pi2, D(z)/pi, m2, log(a+), pi, Om, sqrt163, 1]")
    _pslq("22", ["x","L2/pi2","Lchi2/pi2","D(z)/pi","m2","log(a+)","pi","Om","sqrt163","1"],
          [x, L2/pi**2, L_chi_2/pi**2, D_z/pi, m2, log_ap, pi, Omega, sq163, mpf(1)],
          bound=10000)

    # Test 23: correction vs everything
    print(f"\n  23: [corr, L2/pi2, L_chi2/pi2, D(z)/pi, Li2(am2), Om, pi*log163, 1]")
    _pslq("23", ["corr","L2/pi2","Lchi2/pi2","D(z)/pi","Li2","Om","pi*log163","1"],
          [correction, L2/pi**2, L_chi_2/pi**2, D_z/pi, Li2_am2, Omega,
           pi*log163, mpf(1)], bound=50000)

    # Test 24: Boyd residual vs everything
    print(f"\n  24: [resid, L2/pi2, Lchi2/pi2, D(z)/pi, L1/Om, Om2, 1]")
    _pslq("24", ["resid","L2/pi2","Lchi2/pi2","D(z)/pi","L1/Om","Om2","1"],
          [boyd_res, L2/pi**2, L_chi_2/pi**2, D_z/pi, L1/Omega, Omega**2, mpf(1)],
          bound=100000)

    # Test 25: L(E',2) vs L(chi, 2) and D(z) — the Zagier/Beilinson structure
    print(f"\n  25: [L2/(pi*Om), Lchi2*sqrt163/pi2, D(z)/(pi*Om), 1]  bound 1M")
    _pslq("25", ["L2/(pi*Om)","Lchi2*s163/pi2","D(z)/(pi*Om)","1"],
          [L2/(pi*Omega), L_chi_2*sq163/pi**2, D_z/(pi*Omega), mpf(1)],
          bound=1000000, tol_exp=-20)

    # Test 26: x as linear combination of ALL available constants
    print(f"\n  26: [x, L2/(pi*Om), Lchi2*s163/pi2, D(z)/pi, m2, log(a+), pi, 1]")
    _pslq("26", ["x","L2/(pi*Om)","Lchi2*s163/pi2","D(z)/pi","m2","log(a+)","pi","1"],
          [x, L2/(pi*Omega), L_chi_2*sq163/pi**2, D_z/pi, m2, log_ap, pi, mpf(1)],
          bound=50000)

    # ═══════════════════════════════════════════════════════════
    # SUMMARY OF KEY RATIOS
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  KEY RATIOS")
    print(f"{'#' * 78}")
    print(f"\n  L(E',2)/pi^2        = {nstr(L2/pi**2, 20)}")
    print(f"  L(E',2)/(pi*Om)    = {nstr(L2/(pi*Omega), 20)}")
    print(f"  L(E',2)/Omega^2    = {nstr(L2/Omega**2, 20)}")
    print(f"  L(chi,-163,2)/pi^2 = {nstr(L_chi_2/pi**2, 20)}")
    print(f"  L(E',2)/L(chi,2)   = {nstr(L2/L_chi_2, 20)}")
    print(f"  D(z_heeg)          = {nstr(D_z, 20)}")
    print(f"  D(z_heeg)/pi       = {nstr(D_z/pi, 20)}")
    print(f"  Cl2(2pi/163)/pi    = {nstr(Cl2_163/pi, 20)}")
    print(f"  correction/D(z)    = {nstr(correction/D_z if fabs(D_z) > 1e-30 else mpf(0), 20)}")
    print(f"  x / D(z_heeg)      = {nstr(x/D_z if fabs(D_z) > 1e-30 else mpf(0), 20)}")

    print(f"\n  Total time: {time.time()-T0:.1f}s")

if __name__ == '__main__':
    main()
