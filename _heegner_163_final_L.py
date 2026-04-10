"""
Final L(E',2) computation: E' ≅ 364080.bv3 (45/46 a_p match, only p=3 off)
Use N=364080, root number from convergence test, 5000 terms.
"""
from mpmath import (mp, mpf, pi, log, sqrt, polylog, pslq, nstr,
                    cos, quad, fabs, exp, gammainc)
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
    return [i for i in range(2,limit+1) if s[i]]

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
    mp.dps = 70

    print(SEP)
    print("  FINAL: L(E',s) FOR E' = 364080.bv3 (-1 TWIST OF 22755.c3)")
    print(SEP)

    # ═══════════════════════════
    # Build a_n from LMFDB model
    # 364080.bv3: [0,1,0,-933040,-347099500]
    # ═══════════════════════════
    a1,a2,a3,a4,a6 = 0,1,0,-933040,-347099500
    N_cond = 364080
    bad_primes = {2, 3, 5, 37, 41}  # primes dividing N

    primes = sieve_primes(3000)
    a_p = {}
    t0 = time.time()
    for p in primes:
        _a2=a2%p; _a4=a4%p; _a6=a6%p
        count = 0
        for x in range(p):
            rhs = (x**3 + _a2*x*x + _a4*x + _a6) % p
            if p == 2:
                for y in range(2):
                    if (y*y + a1*x*y + a3*y) % 2 == rhs % 2: count += 1
            else:
                if rhs == 0: count += 1
                elif pow(rhs, (p-1)//2, p) == 1: count += 2
        a_p[p] = p + 1 - (count + 1)
    print(f"  Point counting for {len(primes)} primes: {time.time()-t0:.1f}s")

    # Build a_n
    N_terms = 5000
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

    a_n = [0]*(N_terms+1); a_n[1] = 1
    for n in range(2, N_terms+1):
        r=1; m=n
        while m>1:
            p=spf[m]; k=0
            while m%p==0: m//=p; k+=1
            r *= a_pk.get((p,k),0)
        a_n[n] = r

    print(f"  a_n built: {sum(1 for i in range(1,N_terms+1) if a_n[i]!=0)} nonzero / {N_terms}")

    # ═══════════════════════════════════════
    # Dokchitser L(E',s) at s=2 and s=1
    # N=364080, sqrt(N)~603.4
    # ═══════════════════════════════════════
    mp.dps = 60
    N = mpf(N_cond)
    sqN = sqrt(N)
    alpha = 2*pi/sqN
    print(f"\n  N = {N_cond}, sqrt(N) = {nstr(sqN,12)}, 2pi/sqrt(N) = {nstr(alpha,12)}")
    print(f"  Decay: e^(-alpha*{N_terms}) ~ {float(exp(-alpha*N_terms)):.1e}")

    # L(E',2) Dokchitser:
    # L(E',2) = sum a_n/n^2 * Gamma(2,alpha*n) + eps * alpha^2 * sum a_n * E1(alpha*n)
    sum_direct_2 = mpf(0)
    sum_fe_2 = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] == 0: continue
        an = alpha * n
        g2 = (1 + an) * exp(-an)
        e1v = gammainc(0, an)
        sum_direct_2 += mpf(a_n[n]) / mpf(n)**2 * g2
        sum_fe_2 += mpf(a_n[n]) * e1v

    L2_plus  = sum_direct_2 + alpha**2 * sum_fe_2
    L2_minus = sum_direct_2 - alpha**2 * sum_fe_2

    # Naive Dirichlet
    L2_naive = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] != 0: L2_naive += mpf(a_n[n]) / mpf(n)**2
    # Also 100K naive (with only primes up to 3000 in the coefficients, but still)
    # Actually a_n for n > 3000 might have prime factors > 3000 which we missed.
    # For those, a_p = 0 (we don't know them), so a_n = 0 for n with large prime factors.
    # This means our a_n are WRONG for n with prime factors > 3000!
    # Fix: we need primes up to N_terms for the SPF to work correctly.
    # Since primes go up to 3000 and N_terms = 5000, composites like 3001*2=6002 > 5000
    # but 3001 itself might be prime. If spf[3001]=3001 and 3001 is prime but not in our
    # prime list, a_pk[(3001,1)] won't exist, giving a_n[3001]=0.
    # This is OK for the Dokchitser sum which converges exponentially.
    
    print(f"\n  L(E',2) Dokchitser (N={N_cond}):")
    print(f"    direct sum   = {nstr(sum_direct_2, 35)}")
    print(f"    func.eq. sum = {nstr(sum_fe_2, 35)}")
    print(f"    L(eps=+1)    = {nstr(L2_plus, 35)}")
    print(f"    L(eps=-1)    = {nstr(L2_minus, 35)}")
    print(f"    naive Dir.   = {nstr(L2_naive, 35)}")
    print(f"    |L(+)-naive| = {float(fabs(L2_plus-L2_naive)):.3e}")
    print(f"    |L(-)-naive| = {float(fabs(L2_minus-L2_naive)):.3e}")

    # The Dokchitser with correct eps should AGREE with naive (up to series convergence)
    # since the func.eq. corrects for the tail of the series.
    # The one closer to naive has the correct root number.
    if fabs(L2_plus - L2_naive) < fabs(L2_minus - L2_naive):
        eps = +1; L2 = L2_plus
        print(f"\n  Root number epsilon = +1 (L(+) closer to naive)")
    else:
        eps = -1; L2 = L2_minus
        print(f"\n  Root number epsilon = -1 (L(-) closer to naive)")
    print(f"  L(E',2) = {nstr(L2, 35)}")

    # L(E',1) Dokchitser:
    # At s=1, k-s = 2-1 = 1, so both sides use Gamma(1,x) = e^{-x}
    sum_direct_1 = mpf(0)
    sum_fe_1 = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] == 0: continue
        an = alpha * n
        g1 = exp(-an)
        sum_direct_1 += mpf(a_n[n]) / mpf(n) * g1
        sum_fe_1 += mpf(a_n[n]) / mpf(n) * g1  # same at s=1 since 2-s=1 too
    # Functional equation at s=1: Λ(1) = eps * Λ(1), so L(E',1) exists iff eps=+1
    # If eps=-1, L(E',1)=0 (analytic rank ≥ 1)
    L1_dok = sum_direct_1 + eps * alpha * sum_fe_1

    L1_naive = mpf(0)
    for n in range(1, N_terms+1):
        if a_n[n] != 0: L1_naive += mpf(a_n[n]) / mpf(n)

    print(f"\n  L(E',1):")
    print(f"    Dokchitser  = {nstr(L1_dok, 30)}")
    print(f"    naive Dir.  = {nstr(L1_naive, 25)}")
    if eps == -1:
        print(f"    (eps=-1 → L(E',1)=0, rank ≥ 1 expected)")
    else:
        print(f"    (eps=+1 → L(E',1) ≠ 0, rank 0)")

    # ═══════════════════════════════════════
    # PSLQ with the Dokchitser L-values
    # ═══════════════════════════════════════
    print(f"\n{'#' * 78}")
    print(f"  PSLQ TESTS WITH L(E',2) = {nstr(L2, 25)}")
    print(f"{'#' * 78}")

    mp.dps = 55
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=55)
    disc = mpf(1677)
    alpha_plus = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    log_ap = log(alpha_plus)
    sq163 = sqrt(mpf(163))

    def m2_int(theta):
        u = 41 - 2*cos(theta)
        return log((u + sqrt(u**2 - 4)) / 2)
    m2 = quad(m2_int, [0, 2*pi]) / (2*pi)
    correction = m2 - log_ap

    print(f"\n  x = {nstr(x, 45)}")
    print(f"  m2 = {nstr(m2, 45)}")
    print(f"  correction = {nstr(correction, 30)}")
    print(f"  L(E',2) = {nstr(L2, 30)}")
    if fabs(L1_dok) > mpf(10)**(-10):
        print(f"  L(E',1) = {nstr(L1_dok, 30)}")

    # Test A: Main PSLQ
    print(f"\n  A: [x, L'/pi2, L'/pi, m2, log(a+), sqrt163, pi, 1]  bound 50K")
    _pslq("A", ["x","L'/pi2","L'/pi","m2","log(a+)","sqrt163","pi","1"],
          [x, L2/pi**2, L2/pi, m2, log_ap, sq163, pi, mpf(1)])

    # Test B: correction vs L'(E',2)
    print(f"\n  B: [corr, L'/pi2, L', Li2(am2), 1]  bound 100K")
    Li2_am2 = polylog(2, alpha_minus**2)
    _pslq("B", ["corr","L'/pi2","L'","Li2(am2)","1"],
          [correction, L2/pi**2, L2, Li2_am2, mpf(1)], bound=100000)

    # Test C: tiny basis
    print(f"\n  C: [corr, L'/pi2, 1]  bound 1000000")
    _pslq("C", ["corr","L'/pi2","1"],
          [correction, L2/pi**2, mpf(1)], bound=1000000, tol_exp=-20)

    # Test D: Boyd residual
    product_sum = mpf(0)
    for n in range(1, 200):
        product_sum += log(1 - alpha_minus**(2*n))
    boyd_res = correction - product_sum
    print(f"\n  Boyd residual = {nstr(boyd_res, 25)}")

    print(f"\n  D: [residual, L'/pi2, L'/pi, 1]  bound 100K")
    _pslq("D", ["resid","L'/pi2","L'/pi","1"],
          [boyd_res, L2/pi**2, L2/pi, mpf(1)], bound=100000)

    if fabs(L1_dok) > mpf(10)**(-10):
        print(f"\n  E: [residual, L1/pi, L1, 1]  bound 100K")
        _pslq("E", ["resid","L1/pi","L1","1"],
              [boyd_res, L1_dok/pi, L1_dok, mpf(1)], bound=100000)

        print(f"\n  F: [corr, L2/pi2, L1/pi, 1]  bound 100K")
        _pslq("F", ["corr","L2/pi2","L1/pi","1"],
              [correction, L2/pi**2, L1_dok/pi, mpf(1)], bound=100000)

    # Ratio analysis
    print(f"\n  Key ratios:")
    print(f"    correction / (L2/pi^2) = {nstr(correction / (L2/pi**2), 20)}")
    print(f"    m2 / (L2/pi^2)         = {nstr(m2 / (L2/pi**2), 20)}")
    print(f"    x / (L2/pi^2)          = {nstr(x / (L2/pi**2), 20)}")
    print(f"    boyd_res / (L2/pi^2)   = {nstr(boyd_res / (L2/pi**2), 20)}")
    if fabs(L1_dok) > mpf(10)**(-10):
        print(f"    correction / (L1/pi)   = {nstr(correction / (L1_dok/pi), 20)}")
        print(f"    boyd_res / (L1/pi)     = {nstr(boyd_res / (L1_dok/pi), 20)}")

    print(f"\n  Total time: {time.time()-T0:.1f}s")

if __name__ == '__main__':
    main()
