"""
Heegner D=-163 CF: Tasks 1-4
=============================
1. Mahler measure m₂ at 100-digit precision vs log(α₊)
2. L(E₄₁, 2) via proper Dirichlet series (50K terms)
3. Weight-4 PSLQ tests
4. Period/recurrence tests for CF family x(k)
"""
from mpmath import (mp, mpf, mpc, pi, log, sqrt, polylog, pslq, nstr,
                    cos, sin, quad, fabs, zeta, exp, loggamma, matrix, chop)
from mpmath.calculus.quadrature import GaussLegendre
import time
import sys

# ─────────────────────── helpers ───────────────────────

def eval_cf(a_coeffs, b_coeffs, depth, dps=None):
    """Evaluate GCF b(0) + a(1)/(b(1) + a(2)/(b(2)+...)) via forward recurrence."""
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
    """Compute the Kronecker symbol (D|n) for fundamental discriminant D."""
    n = int(n)
    if n == 0:
        return 0
    D = int(D)
    # Handle sign
    result = 1
    if n < 0:
        n = -n
        if D < 0:
            result = -result
    # Factor out 2s
    v = 0
    while n % 2 == 0:
        n //= 2
        v += 1
    if v > 0:
        # (D|2)
        Dmod8 = D % 8
        if Dmod8 == 1 or Dmod8 == 7:
            k2 = 1
        elif Dmod8 == 3 or Dmod8 == 5:
            k2 = -1
        else:
            k2 = 0
        if v % 2 == 1:
            result *= k2
        if k2 == 0 and v > 0:
            return 0
    if n == 1:
        return result
    # Now n is odd > 1; compute Jacobi symbol (D|n)
    a = D % n
    if a < 0:
        a += n
    b = n
    # Jacobi symbol (a|b)
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
    if b == 1:
        return result * j
    else:
        return 0


def chi_neg163(n):
    """Kronecker symbol (-163|n)."""
    return kronecker_symbol(-163, n)


def sieve_primes(limit):
    """Simple sieve of Eratosthenes."""
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
        x_coeff = rel[0] if names[0] in ('x', 'x/pi', 'x*pi', 'x*sqrt163') else None
        if x_coeff is not None and x_coeff == 0:
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
# TASK 1: Mahler measure at 100-digit precision
# ═══════════════════════════════════════════════════════════════

def task1():
    print(f"\n{'#' * 78}")
    print(f"  TASK 1: MAHLER MEASURE m₂(x+1/x+y+1/y-41) AT 100-DIGIT PRECISION")
    print(f"{'#' * 78}")
    T0 = time.time()

    mp.dps = 120  # extra guard digits

    disc = mpf(1677)
    alpha_plus  = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    log_alpha_plus = log(alpha_plus)

    print(f"\n  α₊ = (41+√1677)/2 = {nstr(alpha_plus, 50)}")
    print(f"  α₋ = (41-√1677)/2 = {nstr(alpha_minus, 50)}")
    print(f"  log(α₊)            = {nstr(log_alpha_plus, 105)}")

    # ── Jensen's formula derivation ──
    # m₂ = (1/2π)∫₀²π log((41-2cosθ + √((41-2cosθ)²-4))/2) dθ
    # The integrand depends on θ through u = 41 - 2cosθ ∈ [39, 43].
    # log(α₊) = log((41+√1677)/2) corresponds to u=41 (constant term only).
    # Since the integrand is NOT constant in θ, m₂ ≠ log(α₊) in general.

    print(f"\n  Computing m₂ via high-precision 1D quadrature (mpmath quad)...")
    t0 = time.time()

    def m2_integrand(theta):
        u = 41 - 2*cos(theta)
        return log((u + sqrt(u**2 - 4)) / 2)

    # Use mpmath's adaptive quadrature at 120 dps
    m2 = quad(m2_integrand, [0, 2*pi], error=True)
    m2_val = m2[0] / (2*pi)
    m2_err = m2[1] / (2*pi) if m2[1] else mpf(0)
    t1 = time.time()
    print(f"  Time for quad: {t1-t0:.1f}s")
    print(f"\n  m₂ (adaptive quad)  = {nstr(m2_val, 105)}")
    print(f"  Estimated error     = {float(m2_err):.3e}")

    # Also cross-check via Gauss-Legendre with 2000 points (lower count to avoid overflow)
    print(f"\n  Cross-check: 2000-point Gauss-Legendre quadrature...")
    t0 = time.time()
    N_GL = 2000
    # Transform ∫₀²π f(θ)dθ via substitution θ = π(1+t), t ∈ [-1,1]
    # Compute GL nodes/weights at moderate count
    gl = GaussLegendre(mp)
    try:
        nodes_weights = gl.calc_nodes(N_GL, mp.prec)
        m2_gl = mpf(0)
        for node, weight in nodes_weights:
            theta = pi * (1 + node)
            u = 41 - 2*cos(theta)
            m2_gl += weight * log((u + sqrt(u**2 - 4)) / 2)
        m2_gl = m2_gl * pi / (2*pi)
    except Exception as e:
        print(f"    GL failed ({e}), using manual midpoint rule instead...")
        # Fallback: high-precision midpoint rule with 10000 points
        N_mp = 10000
        m2_gl = mpf(0)
        for i in range(N_mp):
            theta = 2 * pi * (mpf(i) + mpf('0.5')) / N_mp
            u = 41 - 2*cos(theta)
            m2_gl += log((u + sqrt(u**2 - 4)) / 2)
        m2_gl /= N_mp

    t1 = time.time()
    print(f"  Time for GL: {t1-t0:.1f}s")
    print(f"  m₂ (GL 10K)         = {nstr(m2_gl, 105)}")
    print(f"  m₂(quad) - m₂(GL)   = {float(m2_val - m2_gl):.3e}")

    # Use the better of the two (adaptive quad is generally more accurate)
    m2_best = m2_val

    diff = m2_best - log_alpha_plus

    print(f"\n  ────── COMPARISON ──────")
    print(f"  m₂                  = {nstr(m2_best, 105)}")
    print(f"  log(α₊)             = {nstr(log_alpha_plus, 105)}")
    print(f"  m₂ - log(α₊)        = {nstr(diff, 40)}")
    print(f"  |difference|         = {float(fabs(diff)):.6e}")

    if fabs(diff) < mpf(10)**(-90):
        print(f"\n  VERDICT: m₂ = log(α₊) to 90+ digits → they appear EQUAL.")
        print(f"  m₂ is weight-1 (algebraic logarithm). The weight-2 claim was wrong.")
    else:
        print(f"\n  VERDICT: m₂ ≠ log(α₊). The difference is genuine.")
        print(f"  m₂ - log(α₊) = {nstr(diff, 30)}")
        # Identify the difference
        # Boyd's formula for k>>4: m₂ - log(α₊) ≈ -∑_{n≥1} Li₂(α₋²ⁿ)/n
        print(f"\n  Identifying the correction term...")
        # Series: ∑_{n≥1} Li₂(α₋²ⁿ)/n
        s_li2 = mpf(0)
        for n in range(1, 30):
            s_li2 += polylog(2, alpha_minus**(2*n)) / n
        print(f"  -∑ Li₂(α₋^{{2n}})/n (n=1..29) = {nstr(-s_li2, 30)}")
        print(f"  diff + ∑                       = {float(diff + s_li2):.6e}")

        # More precise: the exact Rodriguez-Villegas formula
        # m(P_k) = log(α₊) + Re[Li₂(α₋²)]/(1) + higher order
        Li2_am2 = polylog(2, alpha_minus**2)
        print(f"  Li₂(α₋²)   = {nstr(Li2_am2, 30)}")
        print(f"  diff / Li₂(α₋²)  = {float(diff / Li2_am2):.15f}" if Li2_am2 != 0 else "  Li₂(α₋²) = 0")

    print(f"\n  Task 1 time: {time.time()-T0:.1f}s")
    return m2_best, log_alpha_plus


# ═══════════════════════════════════════════════════════════════
# TASK 2: L(E₄₁, 2) via proper Dirichlet series
# ═══════════════════════════════════════════════════════════════

def task2(m2_val, log_alpha_plus):
    print(f"\n{'#' * 78}")
    print(f"  TASK 2: L(E₄₁, 2) VIA DIRICHLET SERIES (50K TERMS)")
    print(f"{'#' * 78}")
    T0 = time.time()

    mp.dps = 60

    # Step 1: Find the Weierstrass model for E₄₁
    # The curve P₄₁: x + 1/x + y + 1/y = 41
    # Multiply through by xy: x²y + xy² + x + y = 41xy
    # x²y + xy² - 41xy + x + y = 0
    #
    # This is a genus-1 curve. We need to convert to Weierstrass form.
    # Standard approach: set y = (v - u²)/(2u - 41) or use Nagell's algorithm.
    #
    # Alternative: use the known parameterization.
    # For P_k: x+1/x+y+1/y=k, with t = k-2:
    #   E_k: Y² + (1-t²)XY - t²Y = X³ - t²X²   (Tate form)
    # With k=41, t=39: t²=1521
    #   Y² + (1-1521)XY - 1521Y = X³ - 1521X²
    #   Y² - 1520XY - 1521Y = X³ - 1521X²
    #
    # Short Weierstrass: y² = x³ + ax + b
    # This requires completing the square and removing the x² term.

    # Instead of hand-computing, let's do point counting directly on the
    # affine model x²y + xy² - 41xy + x + y = 0 for each prime p.
    # Then a_p = p + 1 - #E(F_p) where #E includes projective points.

    print(f"\n  Computing a_p via point counting on x²y+xy²-41xy+x+y=0 mod p...")

    primes = sieve_primes(1000)
    # Bad primes: those dividing the discriminant of E₄₁
    # Related to 1677 = 3 × 13 × 43
    # Also possibly 2 (from the 2-adic part)
    bad_primes = {3, 13, 43}

    a_p = {}
    t0 = time.time()
    for idx, p in enumerate(primes):
        if p in bad_primes:
            # Additive or multiplicative reduction
            # For bad primes, a_p ∈ {-1, 0, 1}
            # We'll compute anyway and handle separately
            pass

        # Count affine solutions to x²y + xy² - 41xy + x + y ≡ 0 mod p
        # For efficiency: for each x, solve for y
        # x²y + xy² - 41xy + x + y = 0
        # y(x² + xy - 41x + 1) + x = 0
        # y(x² + xy - 41x + 1) = -x
        # This is linear in y only if we group carefully:
        # y(x² - 41x + 1) + xy² + x = 0 -- no, xy² term means quadratic in y
        # Actually: xy² + (x² - 41x + 1)y + x = 0
        # Quadratic in y with coefficients a=x, b=(x²-41x+1), c=x
        # Discriminant: (x²-41x+1)² - 4x²
        # = x⁴ - 82x³ + 1683x² - 82x + 1 - 4x²
        # = x⁴ - 82x³ + 1679x² - 82x + 1

        count = 0
        k = 41 % p
        for xx in range(p):
            if xx == 0:
                # y(0 + 0 - 0 + 1) + 0 = 0 → y + 0 = 0... wait
                # x=0: 0 + 0 + 0 + y = 0 → y = 0
                count += 1  # (0, 0) if 0²*0+0*0²-41*0*0+0+0=0 ✓
                continue
            # a_coeff = xx, b_coeff = (xx*xx - 41*xx + 1) mod p, c_coeff = xx
            a_c = xx % p
            b_c = (xx*xx - k*xx + 1) % p
            c_c = xx % p
            disc_y = (b_c * b_c - 4 * a_c * c_c) % p
            if a_c == 0:
                # Linear: b_c * y + c_c = 0
                if b_c != 0:
                    count += 1
                else:
                    if c_c == 0:
                        count += p  # all y work
                    # else no solution
                continue
            # Count solutions of a_c * y² + b_c * y + c_c = 0 (mod p)
            # Discriminant disc_y mod p
            if disc_y == 0:
                # One solution (double root)
                inv_2a = pow(2 * a_c % p, p - 2, p)
                count += 1
            else:
                # Check if disc_y is QR mod p
                leg = pow(disc_y, (p - 1) // 2, p)
                if leg == 1:
                    count += 2
                # elif leg == p-1: no solution
                # else: no solution

        # Add points at infinity on the projective closure
        # Homogenize: X²Y + XY² - 41XYZ + XZ² + YZ² = 0
        # Points at infinity: Z=0 → X²Y + XY² = 0 → XY(X+Y) = 0
        # So: [1:0:0], [0:1:0], [1:-1:0] (if char ≠ 2)
        # But [1:0:0]: plug in: 1·0+1·0-41·1·0·0+1·0+0·0=0 ✓
        # [0:1:0]: 0+0-0+0+1·0=0 ✓
        # [1:-1:0]: 1·(-1)+1·(-1)·1-41·1·(-1)·0+1·0+(-1)·0 = -1-1 =-2
        # Wait let me recheck. Actually for p=2 this needs special care.
        if p == 2:
            # Direct count for p=2
            count = 0
            for xx in range(2):
                for yy in range(2):
                    val = (xx*xx*yy + xx*yy*yy + xx + yy) % 2  # 41 ≡ 1 mod 2
                    # -41xy ≡ xy mod 2
                    val = (xx*xx*yy + xx*yy*yy + xx*yy + xx + yy) % 2
                    if val == 0:
                        count += 1
            # Points at infinity for p=2: Z=0 → X²Y+XY²=XY(X+Y)=0
            # [1:0:0], [0:1:0], [1:1:0] (since -1=1 mod 2)
            # Check [1:1:0]: 1+1-41·0+0+0=2≡0 mod 2 ✓
            n_inf = 3
            Np_total = count + n_inf
            a_p[p] = p + 1 - Np_total
        else:
            # Points at infinity: [1:0:0], [0:1:0], [1:-1:0]
            # Check [1:-1:0]: X²Y+XY²-41XYZ+XZ²+YZ² at Z=0
            # = X²Y+XY² = XY(X+Y). At [1:-1:0]: 1·(-1)·(0)=0 ✓
            n_inf = 3
            Np_total = count + n_inf
            a_p[p] = p + 1 - Np_total

        if idx < 20 or p in bad_primes:
            print(f"    p={p:5d}: #E(F_p)={Np_total:5d}, a_p={a_p[p]:+5d}" + (" [bad]" if p in bad_primes else ""))

    # Quick sanity: |a_p| ≤ 2√p (Hasse bound)
    print(f"\n  Checking Hasse bound |a_p| ≤ 2√p...")
    violations = 0
    for p in primes:
        if p in bad_primes:
            continue
        bound = 2 * p**0.5
        if abs(a_p[p]) > bound + 0.5:
            violations += 1
            if violations <= 5:
                print(f"    VIOLATION: p={p}, a_p={a_p[p]}, bound={bound:.1f}")
    if violations == 0:
        print(f"    All {len(primes) - len(bad_primes)} good primes satisfy Hasse bound.")
    else:
        print(f"    {violations} violations found — point counting may have errors.")
        print(f"    (Projective point counting correction may be off.)")

    t1 = time.time()
    print(f"  Point counting time: {t1-t0:.1f}s")

    # ── Build multiplicative a_n coefficients ──
    print(f"\n  Building a_n Dirichlet coefficients for n ≤ 50000...")
    t0 = time.time()
    N_DIR = 50000
    a_n = [0] * (N_DIR + 1)
    a_n[1] = 1

    # For good primes: a_{p^k} via recurrence
    # a_{p^{k+1}} = a_p * a_{p^k} - p * a_{p^{k-1}} (for good reduction)
    # For bad primes with a_p = c ∈ {-1,0,1}:
    # a_{p^k} = c^k (multiplicative reduction) or 0 for k≥1 (additive)

    # Determine conductor and bad prime behavior
    # For the curve x²y+xy²-41xy+x+y=0, bad primes divide Δ.
    # 1677 = 3·13·43. For now assume multiplicative reduction at bad primes.

    for p in primes:
        if p > N_DIR:
            break
        ap = a_p.get(p, 0)

        # Set a_p first
        pk = p
        if pk <= N_DIR:
            a_n[pk] = ap

        # Higher powers of p
        if p in bad_primes:
            # Multiplicative reduction: a_{p^k} = (a_p)^k
            ppower = p * p
            apk_prev = ap
            while ppower <= N_DIR:
                a_n[ppower] = apk_prev * ap  # NOT correct for additive...
                apk_prev = a_n[ppower]
                ppower *= p
        else:
            # Good reduction: a_{p^{k+1}} = a_p * a_{p^k} - p * a_{p^{k-1}}
            ppower = p * p
            apk_prev_prev = 1  # a_{p^0} = 1
            apk_prev = ap       # a_{p^1} = a_p
            while ppower <= N_DIR:
                apk = ap * apk_prev - p * apk_prev_prev
                a_n[ppower] = apk
                apk_prev_prev = apk_prev
                apk_prev = apk
                ppower *= p

    # Now apply multiplicativity: a_{mn} = a_m * a_n for gcd(m,n)=1
    # Standard approach: iterate over primes and fill in
    # More efficient: use a sieve-like approach
    for p in primes:
        if p > N_DIR:
            break
        # For each prime power p^k that has a_n set, multiply into composites
        pk = p
        while pk <= N_DIR:
            if a_n[pk] == 0 and pk not in [p**j for j in range(1, 20) if p**j <= N_DIR]:
                pk *= p
                continue
            # Multiply a_n[pk] into all n coprime to p
            for m in range(2, N_DIR // pk + 1):
                if m % p == 0:
                    continue
                idx = m * pk
                if idx <= N_DIR:
                    if a_n[m] != 0 or m == 1:
                        val = a_n[pk] * (a_n[m] if m > 1 else 1)
                        if a_n[idx] == 0:
                            a_n[idx] = val
            pk *= p

    # Actually the above is inefficient and buggy. Let me use a cleaner approach.
    # Reset and use standard multiplicative sieve.
    a_n = [0] * (N_DIR + 1)
    a_n[1] = 1

    # First set a_{p^k} for all prime powers
    for p in primes:
        if p > N_DIR:
            break
        ap = a_p.get(p, 0)
        pk = p
        prev2 = 1  # a_{p^0}
        prev1 = ap  # a_{p^1}
        a_n[pk] = ap
        pk = p * p
        while pk <= N_DIR:
            if p in bad_primes:
                a_n[pk] = prev1 * ap  # multiplicative reduction
            else:
                a_n[pk] = ap * prev1 - p * prev2  # good reduction recurrence
            prev2 = prev1
            prev1 = a_n[pk]
            pk *= p

    # Now for composite n: if n = m1 * m2 with gcd = 1,
    # a_n = a_{m1} * a_{m2}. We build this iteratively.
    # Standard approach: factorize each n and compute from prime power values.
    # For speed, we precompute smallest prime factor.
    spf = list(range(N_DIR + 1))  # smallest prime factor
    for p in primes:
        if p * p > N_DIR:
            break
        if spf[p] == p:
            for j in range(p * p, N_DIR + 1, p):
                if spf[j] == j:
                    spf[j] = p

    for n in range(2, N_DIR + 1):
        if a_n[n] != 0:
            continue
        # Factorize n using spf
        p = spf[n]
        # Find p^k dividing n
        pk = 1
        m = n
        while m % p == 0:
            m //= p
            pk *= p
        # n = pk * m with gcd(pk, m) = 1
        if m == 1:
            # n is a prime power; should already be set
            continue
        a_pk = a_n[pk] if pk <= N_DIR else 0
        a_m = a_n[m] if m <= N_DIR else 0
        a_n[n] = a_pk * a_m

    t1 = time.time()
    print(f"  Time for coefficient build: {t1-t0:.1f}s")
    print(f"  a_1..a_10: {a_n[1:11]}")
    print(f"  Non-zero a_n count: {sum(1 for i in range(1, N_DIR+1) if a_n[i] != 0)}")

    # ── Compute L(E₄₁, 2) = Σ a_n/n² ──
    print(f"\n  Computing L(E₄₁, 2) = Σ a_n/n²...")
    mp.dps = 60
    L_E2 = mpf(0)
    for n in range(1, N_DIR + 1):
        if a_n[n] != 0:
            L_E2 += mpf(a_n[n]) / mpf(n)**2
    print(f"  L(E₄₁, 2) [raw, {N_DIR} terms] = {nstr(L_E2, 40)}")

    # Also compute with damping (Dokchitser-like acceleration)
    # L(E,2) ≈ 2·Σ a_n/n² · exp(-2πn/√N)  where N is the conductor
    # For conductor N, estimate from bad primes: N = 3·13·43 = 1677 or 2²·1677 etc
    # Try N = 1677 and N = 4·1677 = 6708
    for N_cond in [1677, 6708]:
        sqN = mpf(N_cond)**mpf('0.5')
        L_damped = mpf(0)
        for n in range(1, N_DIR + 1):
            if a_n[n] != 0:
                L_damped += mpf(a_n[n]) / mpf(n)**2 * exp(-2*pi*n/sqN)
        # The damped sum needs correction via the functional equation
        # For now just report raw
        print(f"  L damped (N={N_cond}): {nstr(L_damped, 30)}")

    # ── Euler product check ──
    print(f"\n  Euler product cross-check (primes ≤ 1000):")
    L_euler = mpf(1)
    for p in primes:
        if p in bad_primes:
            # Bad prime Euler factor: (1 - a_p/p^s)^{-1}
            ap = a_p.get(p, 0)
            if ap != 0:
                factor = 1 - mpf(ap)/p**2
                if factor != 0:
                    L_euler /= factor
            continue
        ap = a_p.get(p, 0)
        # Good prime: (1 - a_p/p^s + 1/p^{2s-1})^{-1} at s=2
        factor = 1 - mpf(ap)/p**2 + mpf(1)/p**3
        if factor != 0:
            L_euler /= factor
    print(f"  L(E₄₁, 2) [Euler, {len(primes)} primes] = {nstr(L_euler, 30)}")

    # ── PSLQ with available values ──
    print(f"\n  Running PSLQ with L(E₄₁,2)...")

    disc = mpf(1677)
    alpha_plus  = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    sq163 = sqrt(mpf(163))
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=60)

    print(f"\n  PSLQ basis: [x, L(E,2)/π², L(E,2)/π, m₂, log(α₊), √163, π, 1]")
    names = ["x", "L(E,2)/pi^2", "L(E,2)/pi", "m2", "log(a+)", "sqrt163", "pi", "1"]
    vals = [x, L_E2/pi**2, L_E2/pi, m2_val, log_alpha_plus, sq163, pi, mpf(1)]
    try:
        rel = pslq(vals, maxcoeff=50000, tol=mpf(10)**(-25))
    except Exception as e:
        rel = None
        print(f"    PSLQ error: {e}")
    _print_pslq("L(E,2) PSLQ", names, vals, rel)

    # Additional PSLQ: L(E,2) vs m2 correction
    if m2_val and log_alpha_plus:
        correction = m2_val - log_alpha_plus
        if fabs(correction) > mpf(10)**(-30):
            print(f"\n  PSLQ: correction term analysis")
            names2 = ["correction", "L(E,2)/pi^2", "L(E,2)/pi", "L(E,2)", "1"]
            vals2 = [correction, L_E2/pi**2, L_E2/pi, L_E2, mpf(1)]
            try:
                rel2 = pslq(vals2, maxcoeff=50000, tol=mpf(10)**(-20))
            except Exception:
                rel2 = None
            _print_pslq("correction PSLQ", names2, vals2, rel2)

    print(f"\n  Task 2 time: {time.time()-T0:.1f}s")
    return L_E2


# ═══════════════════════════════════════════════════════════════
# TASK 3: Weight-4 PSLQ tests
# ═══════════════════════════════════════════════════════════════

def task3(m2_val=None):
    print(f"\n{'#' * 78}")
    print(f"  TASK 3: WEIGHT-4 PSLQ TESTS")
    print(f"{'#' * 78}")
    T0 = time.time()

    mp.dps = 70  # 60 digits + 10 guard

    disc = mpf(1677)
    alpha_plus  = (41 + sqrt(disc)) / 2
    alpha_minus = (41 - sqrt(disc)) / 2
    sq163 = sqrt(mpf(163))
    x = eval_cf([0, -41, 1], [1, 1], depth=5000, dps=70)

    print(f"\n  x = {nstr(x, 60)}")

    # ── Compute weight-4 constants ──
    print(f"\n  Computing weight-4 constants...")
    t0 = time.time()

    Li4_am = polylog(4, alpha_minus)          # Li₄(α⁻)
    Li4_nam = polylog(4, -alpha_minus)        # Li₄(-α⁻)
    Li4_am2 = polylog(4, alpha_minus**2)      # Li₄(α⁻²)

    print(f"  Li₄(α⁻)   = {nstr(Li4_am, 50)}")
    print(f"  Li₄(-α⁻)  = {nstr(Li4_nam, 50)}")
    print(f"  Li₄(α⁻²)  = {nstr(Li4_am2, 50)}")

    # L(χ_{-163}, 4) = Σ χ(n)/n⁴
    print(f"  Computing L(χ_{{-163}}, 4) via 100K terms...")
    L4_chi = mpf(0)
    for n in range(1, 100001):
        c = chi_neg163(n)
        if c != 0:
            L4_chi += mpf(c) / mpf(n)**4
    print(f"  L(χ_{{-163}}, 4) = {nstr(L4_chi, 50)}")

    zeta4 = pi**4 / 90  # ζ(4)
    print(f"  ζ(4) = π⁴/90 = {nstr(zeta4, 50)}")

    # Multiple zeta value ζ(3,1)
    # ζ(3,1) = Σ_{m>n≥1} 1/(m³n) = π⁴/360
    mzv31 = pi**4 / 360
    print(f"  ζ(3,1)  = π⁴/360 = {nstr(mzv31, 50)}")
    print(f"  ζ(3,1) / ζ(4) = {float(mzv31/zeta4):.10f} (should be 1/4)")

    log_am = log(alpha_minus)
    log4 = log_am**4
    log2pi2 = log_am**2 * pi**2
    print(f"  log(α⁻)⁴  = {nstr(log4, 50)}")
    print(f"  log(α⁻)²π² = {nstr(log2pi2, 50)}")

    t1 = time.time()
    print(f"  Computation time: {t1-t0:.1f}s")

    # ── PSLQ Test 1: Full weight-4 basis ──
    print(f"\n  PSLQ Test 1: Full weight-4 basis (10 elements), bound 10000")
    names1 = ["x", "Li4(a-)", "Li4(-a-)", "Li4(a-^2)", "L4_chi/pi^4",
              "zeta4", "log4", "log2pi2", "sqrt163", "1"]
    vals1 = [x, Li4_am, Li4_nam, Li4_am2, L4_chi/pi**4,
             zeta4, log4, log2pi2, sq163, mpf(1)]
    try:
        rel1 = pslq(vals1, maxcoeff=10000, tol=mpf(10)**(-30))
    except Exception as e:
        rel1 = None
        print(f"    Error: {e}")
    _print_pslq("W4 Full", names1, vals1, rel1)

    # ── PSLQ Test 2: Transform x/π ──
    print(f"\n  PSLQ Test 2: [x/π, Li4(a-), L4_chi/π⁴, ζ(4)/π, 1]")
    names2 = ["x/pi", "Li4(a-)", "L4_chi/pi^4", "zeta4/pi", "1"]
    vals2 = [x/pi, Li4_am, L4_chi/pi**4, zeta4/pi, mpf(1)]
    try:
        rel2 = pslq(vals2, maxcoeff=10000, tol=mpf(10)**(-30))
    except Exception:
        rel2 = None
    _print_pslq("W4 x/π", names2, vals2, rel2)

    # ── PSLQ Test 3: Transform x·π ──
    print(f"\n  PSLQ Test 3: [x·π, Li4(a-), L4_chi/π³, π², 1]")
    names3 = ["x*pi", "Li4(a-)", "L4_chi/pi^3", "pi^2", "1"]
    vals3 = [x*pi, Li4_am, L4_chi/pi**3, pi**2, mpf(1)]
    try:
        rel3 = pslq(vals3, maxcoeff=10000, tol=mpf(10)**(-30))
    except Exception:
        rel3 = None
    _print_pslq("W4 x·π", names3, vals3, rel3)

    # ── PSLQ Test 4: √163 transforms ──
    print(f"\n  PSLQ Test 4: [x·√163, Li4(a-)·√163, L4_chi·√163/π⁴, 1]")
    names4 = ["x*sqrt163", "Li4(a-)*sqrt163", "L4_chi*sqrt163/pi^4", "1"]
    vals4 = [x*sq163, Li4_am*sq163, L4_chi*sq163/pi**4, mpf(1)]
    try:
        rel4 = pslq(vals4, maxcoeff=10000, tol=mpf(10)**(-30))
    except Exception:
        rel4 = None
    _print_pslq("W4 √163", names4, vals4, rel4)

    # ── Additional weight-4 tests ──
    print(f"\n  PSLQ Test 5: Extended basis with mzv31")
    names5 = ["x", "Li4(a-)", "Li4(-a-)", "Li4(a-^2)", "L4_chi",
              "zeta4", "mzv31", "log4", "log2pi2", "pi^4", "sqrt163", "1"]
    vals5 = [x, Li4_am, Li4_nam, Li4_am2, L4_chi,
             zeta4, mzv31, log4, log2pi2, pi**4, sq163, mpf(1)]
    try:
        rel5 = pslq(vals5, maxcoeff=5000, tol=mpf(10)**(-25))
    except Exception:
        rel5 = None
    _print_pslq("W4 Extended", names5, vals5, rel5)

    # ── Cross-weight test: mix weight-2 and weight-4 ──
    print(f"\n  PSLQ Test 6: Cross-weight [x, Li4(a-), Li2(a-)², zeta4, log4, log2pi2, 1]")
    Li2_am = polylog(2, alpha_minus)
    Li2_sq = Li2_am**2  # weight-4 composite
    names6 = ["x", "Li4(a-)", "Li2(a-)^2", "zeta4", "log4", "log2pi2", "sqrt163", "1"]
    vals6 = [x, Li4_am, Li2_sq, zeta4, log4, log2pi2, sq163, mpf(1)]
    try:
        rel6 = pslq(vals6, maxcoeff=10000, tol=mpf(10)**(-30))
    except Exception:
        rel6 = None
    _print_pslq("W4 Cross", names6, vals6, rel6)

    print(f"\n  Task 3 time: {time.time()-T0:.1f}s")


# ═══════════════════════════════════════════════════════════════
# TASK 4: Period question — recurrence tests via CF family x(k)
# ═══════════════════════════════════════════════════════════════

def task4():
    print(f"\n{'#' * 78}")
    print(f"  TASK 4: PERIOD QUESTION — CF FAMILY x(k) RECURRENCE")
    print(f"{'#' * 78}")
    T0 = time.time()

    mp.dps = 60

    # ── Compute x(k) for k = 35, 37, 39, 41, 43, 45 ──
    # CF: a(n) = n² - k·n, b(n) = n+1
    k_values = [35, 37, 39, 41, 43, 45]
    x_values = {}

    print(f"\n  Computing x(k) for k ∈ {k_values} at 50-digit precision...")
    for k in k_values:
        t0 = time.time()
        xk = eval_cf([0, -k, 1], [1, 1], depth=5000, dps=60)
        t1 = time.time()
        x_values[k] = xk
        print(f"  x({k}) = {nstr(xk, 50)}  ({t1-t0:.1f}s)")

    # ── Test 1: Polynomial recurrence in k ──
    # Try: Σ_{j=0}^{4} c_j(k) · x(k+2j) = 0 for k = 35, evaluated at specific points
    # With 6 values and a 5-term recurrence (order 4), we have sufficient constraints
    # if the recurrence coefficients are constants.

    print(f"\n  Test 1: Constant-coefficient recurrence Σ c_j x(k+2j) = 0")
    print(f"  Using x(35), x(37), x(39), x(41), x(43), x(45)")

    # 5-term recurrence: c0·x(35) + c1·x(37) + c2·x(39) + c3·x(41) + c4·x(43) + c5·x(45) = 0
    # This is just one PSLQ instance
    names_r1 = [f"x({k})" for k in k_values]
    vals_r1 = [x_values[k] for k in k_values]
    try:
        rel_r1 = pslq(vals_r1, maxcoeff=100000, tol=mpf(10)**(-25))
    except Exception:
        rel_r1 = None
    _print_pslq("Constant recurrence", names_r1, vals_r1, rel_r1)

    # ── Test 2: Linear-in-k recurrence ──
    # Σ (a_j + b_j·k) · x(k+2j) = 0 with shifts 0,2,4
    # At k=35: (a0+35b0)x(35) + (a1+37b1)x(37) + (a2+39b2)x(39) = 0
    # At k=37: (a0+37b0)x(37) + (a1+39b1)x(39) + (a2+41b2)x(41) = 0
    # etc. -> 4 equations in 6 unknowns (a0,b0,a1,b1,a2,b2)
    # Use PSLQ on: [x(k), k·x(k), x(k+2), (k+2)·x(k+2), x(k+4), (k+4)·x(k+4)]

    print(f"\n  Test 2: Linear-in-k recurrence (3-term, 6 unknowns)")
    # Build PSLQ vectors for each starting k
    for k_start in [35, 37, 39]:
        k0, k1, k2 = k_start, k_start+2, k_start+4
        if k2 not in x_values:
            continue
        names_r2 = [f"x({k0})", f"{k0}*x({k0})", f"x({k1})", f"{k1}*x({k1})", f"x({k2})", f"{k2}*x({k2})"]
        vals_r2 = [x_values[k0], k0*x_values[k0], x_values[k1], k1*x_values[k1],
                   x_values[k2], k2*x_values[k2]]
        try:
            rel_r2 = pslq(vals_r2, maxcoeff=10000, tol=mpf(10)**(-20))
        except Exception:
            rel_r2 = None
        _print_pslq(f"Lin recurrence k={k_start}", names_r2, vals_r2, rel_r2)

    # ── Test 3: Does x(k) have a simple closed form pattern? ──
    print(f"\n  Test 3: x(k) vs algebraic functions of k")
    # For each k, test: x(k) =? rational function of k and sqrt(k²-4)?
    for k in k_values:
        disc_k = mpf(k**2 - 4)
        sq_dk = sqrt(disc_k)
        log_ap_k = log((k + sq_dk) / 2)

        names_t3 = [f"x({k})", f"log(a+_{k})", f"sqrt({k}^2-4)", f"k={k}", "1"]
        vals_t3 = [x_values[k], log_ap_k, sq_dk, mpf(k), mpf(1)]
        try:
            rel_t3 = pslq(vals_t3, maxcoeff=100000, tol=mpf(10)**(-25))
        except Exception:
            rel_t3 = None
        if rel_t3:
            _print_pslq(f"x({k}) algebraic", names_t3, vals_t3, rel_t3)
        else:
            print(f"    x({k}): no simple algebraic relation (bound 100K)")

    # ── Test 4: Ratio pattern ──
    print(f"\n  Test 4: Ratio x(k)/x(k+2)")
    for i in range(len(k_values) - 1):
        k0 = k_values[i]
        k1 = k_values[i+1]
        ratio = x_values[k0] / x_values[k1]
        print(f"    x({k0})/x({k1}) = {nstr(ratio, 30)}")

    # ── Test 5: Broader PSLQ including log, sqrt, pi ──
    print(f"\n  Test 5: x(41) vs log/sqrt/pi multiple transforms")
    x41 = x_values[41]
    log_ap41 = log((41 + sqrt(mpf(1677))) / 2)
    sq163 = sqrt(mpf(163))

    for label, vec, nms in [
        ("weight-0", [x41, mpf(41), sqrt(mpf(1677)), mpf(1)],
         ["x(41)", "41", "sqrt1677", "1"]),
        ("weight-1", [x41, log_ap41, pi, sq163, mpf(1)],
         ["x(41)", "log(a+)", "pi", "sqrt163", "1"]),
        ("log transforms", [x41, log_ap41, log_ap41**2, pi**2, mpf(1)],
         ["x(41)", "log(a+)", "log(a+)^2", "pi^2", "1"]),
    ]:
        try:
            rel = pslq(vec, maxcoeff=100000, tol=mpf(10)**(-25))
        except Exception:
            rel = None
        _print_pslq(label, nms, vec, rel)

    # ── Test 6: Dense k scan for pattern ──
    print(f"\n  Test 6: Dense scan k=30..50 (even) for x(k) trend")
    dense_k = list(range(30, 51, 2))
    for k in dense_k:
        if k in x_values:
            xk = x_values[k]
        else:
            xk = eval_cf([0, -k, 1], [1, 1], depth=3000, dps=55)
            x_values[k] = xk
        disc_k = k**2 - 4
        log_ap = log((k + sqrt(mpf(disc_k))) / 2)
        ratio = xk / log_ap if log_ap != 0 else mpf(0)
        print(f"    k={k:3d}: x(k)={nstr(xk, 25):>35s}  x/log(a+)={nstr(ratio, 12)}")

    print(f"\n  Task 4 time: {time.time()-T0:.1f}s")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    T0 = time.time()
    print(SEP)
    print("  HEEGNER D=-163: COMPREHENSIVE ANALYSIS (TASKS 1-4)")
    print(SEP)

    # Task 1: Mahler measure
    m2_val, log_ap = task1()

    # Task 2: L(E₄₁, 2)
    L_E2 = task2(m2_val, log_ap)

    # Task 3: Weight-4 PSLQ
    task3(m2_val)

    # Task 4: Period/recurrence
    task4()

    print(f"\n{'#' * 78}")
    print(f"  ALL TASKS COMPLETE — Total time: {time.time()-T0:.1f}s")
    print(f"{'#' * 78}")


if __name__ == '__main__':
    main()
