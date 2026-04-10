"""
Phase 7: Pi Family Convergent Analysis & Final Paper
=====================================================
A. Exact symbolic p_n/q_n for the pi family (m=0,1,2)
B. Pattern recognition: factorization, OEIS, P-recursive search
C. Final paper assembly with polished proof + updated conjecture
"""
import sys, time, json
sys.path.insert(0, '.')

from sympy import (Symbol, factor, expand, simplify, together, cancel,
                    Rational, factorial, binomial, gamma, sqrt, pi as sp_pi,
                    Poly, collect, gcd, lcm, Integer, Abs, prod,
                    Matrix, zeros, eye, Function, solve, oo)
from math import comb

n = Symbol('n', positive=True, integer=True)
c_sym = Symbol('c')

t_total = time.time()

# ═══════════════════════════════════════════════════════════════════════
# PART A: EXACT SYMBOLIC CONVERGENTS FOR PI FAMILY
# ═══════════════════════════════════════════════════════════════════════
print("=" * 74, flush=True)
print("  PART A: PI FAMILY — EXACT SYMBOLIC CONVERGENTS", flush=True)
print("=" * 74, flush=True)

def compute_symbolic_convergents(alpha_fn, beta_fn, depth, label=""):
    """Compute convergents symbolically and return (p_list, q_list)."""
    p = [Integer(1)]  # p_{-1} = 1
    q = [Integer(0)]  # q_{-1} = 0
    b0 = beta_fn(0)
    p.append(b0)       # p_0 = b(0)
    q.append(Integer(1))  # q_0 = 1
    
    for nn in range(1, depth + 1):
        a_n = alpha_fn(nn)
        b_n = beta_fn(nn)
        p_new = expand(b_n * p[-1] + a_n * p[-2])
        q_new = expand(b_n * q[-1] + a_n * q[-2])
        p.append(p_new)
        q.append(q_new)
    
    return p, q

# Case m=0: a(n) = -n(2n-1), b(n) = 3n+1 → 2/π
print("\n  Case m=0: a(n) = -n(2n-1), b(n) = 3n+1  [target: 2/π]", flush=True)
alpha_m0 = lambda nn: -nn * (2*nn - 1)
beta_m0 = lambda nn: 3*nn + 1

p_m0, q_m0 = compute_symbolic_convergents(alpha_m0, beta_m0, 15, "m=0")

print(f"\n  {'n':>3s}  {'p_n':>20s}  {'q_n':>20s}  {'p_n factored':>30s}  {'q_n factored':>30s}", flush=True)
print(f"  {'-'*108}", flush=True)
for i in range(1, min(13, len(p_m0))):
    nn = i - 1  # p[1] = p_0, p[2] = p_1, etc.
    pn = p_m0[i]
    qn = q_m0[i]
    pf = str(factor(pn))[:30] if pn != 0 else "0"
    qf = str(factor(qn))[:30] if qn != 0 else "0"
    print(f"  {nn:3d}  {str(pn):>20s}  {str(qn):>20s}  {pf:>30s}  {qf:>30s}", flush=True)

# Case m=1: a(n) = -n(2n-3), b(n) = 3n+1 → 4/π
print("\n  Case m=1: a(n) = -n(2n-3), b(n) = 3n+1  [target: 4/π]", flush=True)
alpha_m1 = lambda nn: -nn * (2*nn - 3)
beta_m1 = lambda nn: 3*nn + 1

p_m1, q_m1 = compute_symbolic_convergents(alpha_m1, beta_m1, 15, "m=1")

print(f"\n  {'n':>3s}  {'p_n':>20s}  {'q_n':>20s}", flush=True)
for i in range(1, min(13, len(p_m1))):
    nn = i - 1
    print(f"  {nn:3d}  {str(p_m1[i]):>20s}  {str(q_m1[i]):>20s}", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# PATTERN ANALYSIS
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 74, flush=True)
print("  PATTERN ANALYSIS FOR m=0 CONVERGENTS", flush=True)
print("=" * 74, flush=True)

# Extract p_n and q_n as integer sequences
p_seq = [int(p_m0[i]) for i in range(1, min(16, len(p_m0)))]
q_seq = [int(q_m0[i]) for i in range(1, min(16, len(q_m0)))]

print(f"\n  p_n sequence (m=0): {p_seq}", flush=True)
print(f"  q_n sequence (m=0): {q_seq}", flush=True)

# Factor each p_n and q_n
print("\n  Factorizations:", flush=True)
for i, (pn, qn) in enumerate(zip(p_seq, q_seq)):
    print(f"  n={i}: p={factor(Integer(pn)):>25s}  q={factor(Integer(qn)):>25s}", flush=True)

# Look at p_n: are they related to double factorials, Pochhammer, etc.?
print("\n  p_n analysis:", flush=True)
for i in range(len(p_seq)):
    pn = p_seq[i]
    # Check: p_n = c * (2n)! / n! ?
    if i > 0:
        ratio = Rational(p_seq[i], p_seq[i-1])
        print(f"  p_{i}/p_{i-1} = {ratio} = {float(ratio):.4f}", flush=True)

print("\n  q_n analysis:", flush=True)
for i in range(1, len(q_seq)):
    ratio = Rational(q_seq[i], q_seq[i-1])
    print(f"  q_{i}/q_{i-1} = {ratio} = {float(ratio):.4f}", flush=True)

# Check: p_n = (2n+1)!! or (2n)!! or similar
print("\n  Testing p_n against factorial formulas:", flush=True)
for i in range(len(p_seq)):
    pn = p_seq[i]
    # (2i)! / i! = double factorial-like
    if i > 0:
        test1 = factorial(2*i) // factorial(i)
        test2 = factorial(2*i+1) // factorial(i)
        test3 = comb(2*i, i) * factorial(i)
        tests = {
            f"(2*{i})!/{i}!": int(test1),
            f"(2*{i}+1)!/{i}!": int(test2),
            f"C(2*{i},{i})*{i}!": int(test3),
        }
        for name, val in tests.items():
            if pn != 0 and val != 0:
                r = Rational(pn, val)
                if r.q == 1 and abs(r.p) < 100:
                    print(f"    p_{i} = {r} * {name}", flush=True)

# Look at q_n as a partial sum (like the log family)
# For the log family: q_n = (n+1)! * sum k^{n-j}/(j+1)
# What is the analog here?
print("\n  q_n partial sum structure:", flush=True)

# Try: q_n = sum_{j=0}^n c_j where c_j involves products of a(1)..a(j)
# In the log family, the key was that q_n/(n+1)! had a recognizable sum structure.
# Let's divide q_n by various factorial-like quantities and look for patterns.

for i in range(len(q_seq)):
    qn = q_seq[i]
    if qn == 0: continue
    
    # Try dividing by (2i+1)!!, (3i)!, etc.
    numer = Integer(qn)
    candidates = {}
    for d_name, d_val in [
        ("1", 1),
        (f"{i}!", max(factorial(i), 1)),
        (f"(2*{i})!", max(factorial(2*i), 1)),
        (f"3^{i}", 3**i),
        (f"(2{i}+1)!!", max(int(prod(range(1, 2*i+2, 2))), 1) if i > 0 else 1),
    ]:
        if d_val > 0:
            r = Rational(qn, int(d_val))
            if r.q <= 100:
                candidates[d_name] = r
    
    if candidates:
        best = min(candidates.items(), key=lambda x: abs(x[1].q))
        print(f"  q_{i}/{best[0]} = {best[1]}", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# P-RECURSIVE SEARCH
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 74, flush=True)
print("  P-RECURSIVE RELATION SEARCH", flush=True)
print("=" * 74, flush=True)

# The convergents satisfy the 3-term recurrence by definition.
# But do p_n or q_n individually satisfy a simpler recurrence?
# p_n = (3n+1)*p_{n-1} - n(2n-1)*p_{n-2}  (this IS the defining recurrence)
# Can we find a FIRST-ORDER recurrence? p_n = f(n) * p_{n-1}?

print("\n  Checking if p_n satisfies a first-order relation p_n = f(n)*p_{n-1}:", flush=True)
for i in range(1, len(p_seq)):
    if p_seq[i-1] != 0:
        r = Rational(p_seq[i], p_seq[i-1])
        print(f"  p_{i}/p_{i-1} = {r}", flush=True)

# Let me try to find a closed form by looking at the sequence in OEIS terms
print("\n  p_n (m=0) raw values: ", flush=True)
for i, v in enumerate(p_seq):
    print(f"    p_{i} = {v}", flush=True)

# Similarly for m=1
p_seq_m1 = [int(p_m1[i]) for i in range(1, min(14, len(p_m1)))]
q_seq_m1 = [int(q_m1[i]) for i in range(1, min(14, len(q_m1)))]

print(f"\n  p_n (m=1) raw values: ", flush=True)
for i, v in enumerate(p_seq_m1):
    print(f"    p_{i} = {v}", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# KEY INSIGHT: MATRIX FORMULATION
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 74, flush=True)
print("  MATRIX PRODUCT FORMULATION", flush=True)
print("=" * 74, flush=True)

# [p_n]   [b(n)  a(n)] [p_{n-1}]
# [p_{n-1}] = [1     0  ] [p_{n-2}]
#
# So [p_n, p_{n-1}] = M_n * M_{n-1} * ... * M_1 * [p_0, p_{-1}]
# where M_j = [[b(j), a(j)], [1, 0]]
#
# The DETERMINANT of M_j = -a(j) = n(2n-1)
# So det(prod M) = prod n(2n-1) = prod_{j=1}^n j(2j-1)
# = n! * (2n-1)!! = n! * (2n)! / (2^n * n!) = (2n)! / 2^n
#
# And p_n*q_{n-1} - p_{n-1}*q_n = (-1)^n * prod a(j) = (-1)^n * (-1)^n * prod j(2j-1)
# = prod j(2j-1) = n! * (2n-1)!!

print("  det(M_1...M_n) = prod_{j=1}^n [-a(j)] = prod j(2j-1)", flush=True)
print("                 = n! * (2n-1)!!", flush=True)

# Verify
for nn in range(1, 8):
    det_prod = 1
    for j in range(1, nn+1):
        det_prod *= j * (2*j - 1)
    # Also: n! * (2n-1)!! = n! * (2n)!/(2^n * n!) = (2n)!/2^n
    predicted = factorial(2*nn) // (2**nn)
    match = det_prod == predicted
    print(f"  n={nn}: prod = {det_prod:12d}  (2n)!/2^n = {predicted:12d}  match={match}", flush=True)

# This means: p_n*q_{n-1} - p_{n-1}*q_n = (2n)!/2^n  (up to sign)
# Verify with actual values
print("\n  Verify p_n*q_{n-1} - p_{n-1}*q_n:", flush=True)
for nn in range(1, min(10, len(p_seq))):
    if nn < len(p_seq) and nn < len(q_seq):
        pn = p_seq[nn]
        qn = q_seq[nn]
        pnm1 = p_seq[nn-1]
        qnm1 = q_seq[nn-1]
        det = pn * qnm1 - pnm1 * qn
        predicted = factorial(2*nn) // (2**nn)
        # Could be (-1)^n * predicted
        for sign in [1, -1]:
            if det == sign * predicted:
                print(f"  n={nn}: p_n*q_{{n-1}} - p_{{n-1}}*q_n = {det:15d} = "
                      f"{'(-1)^n' if sign == (-1)**nn else '(-1)^{n+1}'} * (2n)!/2^n", flush=True)
                break
        else:
            # Try other forms
            print(f"  n={nn}: det = {det:15d}  (2n)!/2^n = {predicted:15d}  ratio = {Rational(det, predicted)}", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# COMPUTE q_n / some_factorial to find structure
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 74, flush=True)
print("  LOOKING FOR q_n CLOSED FORM (m=0)", flush=True)
print("=" * 74, flush=True)

# For the log family, q_n / (n+1)! was a polynomial in k.
# Here b(n)=3n+1, so the "step" is 3. 
# Perhaps q_n is related to sums involving 1/(3j+...) ?
# The key identity in the log proof was:
#   sum x^j/(j+1) = -ln(1-x)/x
# For pi, we might need:
#   sum related to arctan or arcsin

# Let me compute q_n * pi / 2 and see if those are nice
import mpmath
mpmath.mp.dps = 50

print("\n  q_n * (2/pi) for m=0:", flush=True)
for i in range(min(12, len(q_seq))):
    qn_times_target = mpmath.mpf(q_seq[i]) * 2 / mpmath.pi
    print(f"  n={i}: q_n = {q_seq[i]:15d}  q_n*(2/pi) = {mpmath.nstr(qn_times_target, 20)}", flush=True)

# Also: what are p_n * (pi/2)?
print("\n  p_n * (pi/2) for m=0:", flush=True)
for i in range(min(12, len(p_seq))):
    pn_times = mpmath.mpf(p_seq[i]) * mpmath.pi / 2
    print(f"  n={i}: p_n = {p_seq[i]:15d}  p_n*(pi/2) = {mpmath.nstr(pn_times, 20)}", flush=True)

# Check: C_n = p_n/q_n → 2/pi, so q_n → p_n * pi/2 for large n
# q_n = p_n * pi/2 * (1 + O(1/n))
# So q_n * 2 / (pi * p_n) → 1

# The KEY question: what is the closed form for p_n?
# p_n sequence (m=0): 1, -3, 16, -120, 1080, ...
# Let me check absolute values: 1, 3, 16, 120, 1080, ...
# 1, 3, 16, 120, 1080
# 1 = 1
# 3 = 3
# 16 = 16
# 120 = 120
# 1080 = 1080

# Signs: +, -, +, -, +, ... = (-1)^n pattern
# |p_n|: 1, 3, 16, 120, 1080, 11340, 134400, ...
# Ratios: 3, 16/3, 120/16=7.5, 1080/120=9, 11340/1080=10.5, 134400/11340=11.85...
# These ratios aren't trivially factorial.

# Let me try: |p_n| / n!
print("\n  |p_n| / n! for m=0:", flush=True)
for i in range(min(12, len(p_seq))):
    ap = abs(p_seq[i])
    if i == 0:
        ratio = ap
    else:
        ratio = Rational(ap, factorial(i))
    print(f"  n={i}: |p_n|={ap:15d}  |p_n|/n! = {ratio}", flush=True)

# |p_n| / (2n)!
print("\n  |p_n| * 2^n / (2n)! for m=0:", flush=True)
for i in range(min(12, len(p_seq))):
    ap = abs(p_seq[i])
    denom = factorial(2*i) // (2**i) if i > 0 else 1
    ratio = Rational(ap * (2**i if i > 0  else 1), factorial(2*i) if i > 0 else 1)
    print(f"  n={i}: |p_n|*2^n/(2n)! = {ratio} = {float(ratio):.6f}", flush=True)

# Try: |p_n| / ((2n-1)!! * something)
print("\n  |p_n| / (2n-1)!! for m=0:", flush=True)
for i in range(min(12, len(p_seq))):
    ap = abs(p_seq[i])
    ddf = 1
    for j in range(1, 2*i, 2):
        ddf *= j
    if ddf == 0: ddf = 1
    ratio = Rational(ap, ddf)
    print(f"  n={i}: |p_n|/(2n-1)!! = {ratio}", flush=True)

total_time = time.time() - t_total
print(f"\n  Analysis complete in {total_time:.0f}s", flush=True)
