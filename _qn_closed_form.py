"""
Q_n closed form search for the m=1 Pi family PCF.

PCF: a(n) = -n(2n-3), b(n) = 3n+1
Value = 4/pi

We know P_n = (2n-1)!! * (n^2 + 3n + 1) for n >= 1, P_0 = 1.
Now find Q_n (denominator convergent).

Recurrence: P_n = b(n)*P_{n-1} + a(n)*P_{n-2}
            Q_n = b(n)*Q_{n-1} + a(n)*Q_{n-2}
with P_{-1}=1, P_0=b_0=1, Q_{-1}=0, Q_0=1.

Wait -- standard CF convention:
  CF = b_0 + a_1/(b_1 + a_2/(b_2 + ...))
  P_{-1}=1, P_0=b_0, Q_{-1}=0, Q_0=1
  P_n = b_n*P_{n-1} + a_n*P_{n-2}
  Q_n = b_n*Q_{n-1} + a_n*Q_{n-2}

For our PCF: b_0 = b(0) = 1, a_n = -n(2n-3) for n>=1, b_n = 3n+1 for n>=0.
"""

from mpmath import mp, mpf, pi, factorial, gamma, sqrt, log10, fabs

mp.dps = 80

def double_fact(n):
    """(2n-1)!! = 1*3*5*...*(2n-1)"""
    if n <= 0:
        return mpf(1)
    r = mpf(1)
    for k in range(1, n+1):
        r *= (2*k - 1)
    return r

def compute_convergents(N):
    """Compute P_n and Q_n for n = -1, 0, 1, ..., N"""
    def a(n):
        return -n * (2*n - 3)
    def b(n):
        return 3*n + 1
    
    Pm1 = mpf(1)   # P_{-1}
    P0 = mpf(b(0)) # P_0 = b_0 = 1
    Qm1 = mpf(0)   # Q_{-1}
    Q0 = mpf(1)     # Q_0 = 1
    
    Ps = [P0]
    Qs = [Q0]
    
    Pprev2, Pprev1 = Pm1, P0
    Qprev2, Qprev1 = Qm1, Q0
    
    for n in range(1, N+1):
        an = mpf(a(n))
        bn = mpf(b(n))
        Pn = bn * Pprev1 + an * Pprev2
        Qn = bn * Qprev1 + an * Qprev2
        Ps.append(Pn)
        Qs.append(Qn)
        Pprev2, Pprev1 = Pprev1, Pn
        Qprev2, Qprev1 = Qprev1, Qn
    
    return Ps, Qs

N = 25
Ps, Qs = compute_convergents(N)

print("=== P_n values ===")
for n in range(min(N+1, 16)):
    print(f"  P_{n} = {Ps[n]}")

print("\n=== Q_n values ===")
for n in range(min(N+1, 16)):
    print(f"  Q_{n} = {Qs[n]}")

print("\n=== P_n / (2n-1)!! ===")
for n in range(min(N+1, 16)):
    df = double_fact(n)
    if df != 0:
        ratio = Ps[n] / df
        print(f"  P_{n} / (2n-1)!! = {ratio}")

print("\n=== Q_n / (2n-1)!! ===")
for n in range(1, min(N+1, 16)):
    df = double_fact(n)
    if df != 0:
        ratio = Qs[n] / df
        print(f"  Q_{n} / (2n-1)!! = {ratio}")

print("\n=== Q_n / (2n)!! ===")
for n in range(1, min(N+1, 16)):
    ef = mpf(1)
    for k in range(1, n+1):
        ef *= 2*k  # (2n)!! = 2*4*6*...*2n
    ratio = Qs[n] / ef
    print(f"  Q_{n} / (2n)!! = {ratio}")

print("\n=== Q_n rational form ===")
# Try Q_n / n!
for n in range(min(N+1, 16)):
    nf = factorial(n)
    ratio = Qs[n] / nf
    print(f"  Q_{n} / n! = {ratio}")

print("\n=== Q_n / (2n-1)!! check against polynomial ===")
# If Q_n = (2n-1)!! * poly(n), find poly
for n in range(1, min(N+1, 16)):
    df = double_fact(n)
    ratio = Qs[n] / df
    # Check if ratio is an integer or simple fraction
    nearest_int = round(float(ratio))
    if abs(float(ratio) - nearest_int) < 0.001:
        print(f"  n={n}: Q_{n}/(2n-1)!! = {nearest_int} (integer)")
    else:
        # Try rational with small denominators
        found = False
        for d in range(1, 200):
            num = ratio * d
            nearest = round(float(num))
            if abs(float(num) - nearest) < 0.0001:
                print(f"  n={n}: Q_{n}/(2n-1)!! = {nearest}/{d}")
                found = True
                break
        if not found:
            print(f"  n={n}: Q_{n}/(2n-1)!! = {float(ratio):.10f} (no simple rational)")

# Now look at Q_n * pi / 4 to see if there's a pattern
print("\n=== Q_n * pi/4 ===")
for n in range(min(N+1, 16)):
    val = Qs[n] * pi / 4
    print(f"  Q_{n} * pi/4 = {val}")

# Check P_n/Q_n vs 4/pi
print("\n=== P_n/Q_n convergence to 4/pi ===")
target = 4 / pi
for n in range(min(N+1, 16)):
    if Qs[n] != 0:
        approx = Ps[n] / Qs[n]
        err = fabs(approx - target)
        if err > 0:
            digits = -log10(err)
        else:
            digits = mp.dps
        print(f"  P_{n}/Q_{n} = {float(approx):.15f}, digits = {float(digits):.1f}")

# Look for Q_n pattern via differences and ratios
print("\n=== Q_n consecutive ratios ===")
for n in range(1, min(N+1, 16)):
    if Qs[n-1] != 0:
        ratio = Qs[n] / Qs[n-1]
        print(f"  Q_{n}/Q_{n-1} = {float(ratio):.10f}")

# Determinant P_n*Q_{n-1} - P_{n-1}*Q_n = prod a_k
print("\n=== Determinant check: P_n*Q_{n-1} - P_{n-1}*Q_n ===")
for n in range(1, min(N+1, 16)):
    det = Ps[n]*Qs[n-1] - Ps[n-1]*Qs[n]
    # Expected: (-1)^n * prod_{k=1}^{n} a_k
    prod_a = mpf(1)
    for k in range(1, n+1):
        prod_a *= (-k * (2*k - 3))
    print(f"  n={n}: det = {det}, expected = {prod_a}, match = {abs(float(det - prod_a)) < 1e-10}")

# Try to express Q_n as sum involving P_k
# From partial fraction: Q_n/P_n = sum_{k=0}^{n} prod_{j=1}^{k} a_j / (P_{k-1} P_k)
# So Q_n = P_n * sum_{k=0}^{n} (-1)^k * |prod a_j| / (P_{k-1}*P_k)
print("\n=== Partial fraction decomposition Q_n/P_n ===")
target_val = 4/pi
Pm1_val = mpf(1)
terms = []
running_sum = mpf(0)
for k in range(N+1):
    if k == 0:
        prod_a = mpf(1)  # empty product
        Pkm1 = Pm1_val   # P_{-1} = 1
    else:
        prod_a = mpf(1)
        for j in range(1, k+1):
            prod_a *= (-j * (2*j - 3))
        Pkm1 = Ps[k-1]
    
    term = prod_a / (Pkm1 * Ps[k])
    running_sum += term
    terms.append(term)

# Q_n = P_n * running_sum_n?? No, that's not quite right.
# Actually: P_n/Q_n = b_0 + sum ... but let's use the standard:
# 1/(P_n/Q_n) = Q_n/P_n
# Euler-Minding: P_n*Q_{n-1} - P_{n-1}*Q_n = (-1)^{n-1} * prod_{k=1}^n a_k
# So Q_n/P_n = Q_0/P_0 + sum_{k=1}^{n} (Q_k*P_{k-1} - Q_{k-1}*P_k)/(P_k*P_{k-1})
#            = 1 + sum_{k=1}^n (-1)^k * prod_{j=1}^k a_j / (P_k*P_{k-1})

print("\n=== Decomposition terms ===")
s = mpf(1)  # Q_0/P_0 = 1/1 = 1
for k in range(1, min(N+1, 16)):
    prod_a = mpf(1)
    for j in range(1, k+1):
        prod_a *= (-j * (2*j - 3))
    term = (-1)**k * prod_a / (Ps[k] * Ps[k-1])
    # Simplify: prod_{j=1}^k [-j(2j-3)] = (-1)^k * prod j * prod (2j-3)
    # prod j = k!, prod (2j-3) for j=1..k: -1, 1, 3, 5, ..., 2k-3
    # = (-1) * 1 * 3 * 5 * ... * (2k-3) = (-1)*(2k-3)!! for k>=2, and just -1 for k=1
    s += term
    err = fabs(s - pi/4)
    if err > 0:
        dgts = -log10(err)
    else:
        dgts = mp.dps
    print(f"  k={k}: term = {float(term):.15e}, running Q/P -> pi/4 digits = {float(dgts):.1f}")

print(f"\n  pi/4 = {float(pi/4):.15f}")
print(f"  Final sum = {float(s):.15f}")
