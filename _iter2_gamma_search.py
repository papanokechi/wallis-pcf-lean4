"""
Iteration 2: Search for Gamma(1/3), Gamma(1/4), Catalan G, Apery zeta(3)
via GCFs with varied polynomial forms.
"""
from mpmath import mp, mpf, nstr, fabs, log, pi, sqrt, catalan, zeta
from mpmath import gamma as mpgamma, pslq, euler
mp.dps = 60

def gcf_bw(a_fn, b_fn, depth=150):
    val = b_fn(depth)
    for n in range(depth-1, 0, -1):
        val = b_fn(n) + a_fn(n+1) / val
    return b_fn(0) + a_fn(1) / val

def check_conv(a_fn, b_fn, depth_lo=30, depth_hi=150):
    """Check convergence and non-degeneracy"""
    if fabs(a_fn(1)) < 1e-10:
        return None  # ghost
    try:
        v1 = gcf_bw(a_fn, b_fn, depth_lo)
        v2 = gcf_bw(a_fn, b_fn, depth_hi)
        if fabs(v2) > 1e15 or fabs(v2) < 1e-15:
            return None
        if fabs(v1 - v2) < mpf("1e-8"):
            return v2
    except:
        pass
    return None

# Target constants
G1_3 = mpgamma(mpf(1)/3)
G1_4 = mpgamma(mpf(1)/4)
Cat = catalan
Z3 = zeta(3)

targets = {
    "Gamma(1/3)": G1_3,
    "Gamma(1/4)": G1_4,
    "Catalan":    Cat,
    "zeta(3)":    Z3,
    "1/Gamma(1/3)": 1/G1_3,
    "1/Gamma(1/4)": 1/G1_4,
    "Gamma(1/3)^2": G1_3**2,
    "Gamma(1/4)^2": G1_4**2,
    "Gamma(1/3)^3/(2pi*sqrt(3))": G1_3**3 / (2*pi*sqrt(3)),  # known relation
    "Gamma(1/4)^2/(2*sqrt(2*pi))": G1_4**2 / (2*sqrt(2*pi)),
}

print("Target values:")
for name, val in targets.items():
    print(f"  {name} = {nstr(val, 20)}")
print()

hits = []

# ─── SEARCH A: Quadratic a_n, linear b_n (wider than iter 1) ───
print("═══ SEARCH A: Extended quadratic GCFs ═══")
count = 0
for alpha in range(-5, 6):         # coeff of n^2
    for beta in range(-8, 9):       # coeff of n 
        for delta in range(-5, 6):  # constant in a_n
            for p in range(1, 6):   # coeff of n in b_n
                for q in range(-3, 4):  # constant in b_n
                    a_fn = lambda n, a=alpha, b=beta, d=delta: a*n*n + b*n + d
                    b_fn = lambda n, P=p, Q=q: P*n + Q
                    
                    V = check_conv(a_fn, b_fn)
                    if V is None:
                        continue
                    count += 1
                    
                    for name, tgt in targets.items():
                        d = fabs(V - tgt)
                        if 0 < d < mpf("1e-20"):
                            dig = int(-log(d, 10))
                            if dig >= 15:
                                msg = f"  HIT: a={alpha}n^2+{beta}n+{delta}, b={p}n+{q} -> {name} [{dig}d]"
                                print(msg)
                                hits.append((name, alpha, beta, delta, p, q, dig))
                        # Try reciprocal and simple multiples
                        for k in [2, 3, 4, 1/2, 1/3, 1/4]:
                            d2 = fabs(V - k*tgt)
                            if 0 < d2 < mpf("1e-20"):
                                dig2 = int(-log(d2, 10))
                                if dig2 >= 15:
                                    msg = f"  HIT: a={alpha}n^2+{beta}n+{delta}, b={p}n+{q} -> {k}*{name} [{dig2}d]"
                                    print(msg)
                                    hits.append((f"{k}*{name}", alpha, beta, delta, p, q, dig2))
                                    
print(f"  Searched {count} convergent GCFs")
print()

# ─── SEARCH B: PSLQ multi-constant scan on iter 1 unmatched values ───
print("═══ SEARCH B: PSLQ multi-constant on novel values ═══")
# Recompute some GCF values that didn't match pi in iter 1
novel = []
for alpha in [-3, -2, -1, 1, 2, 3]:
    for beta in range(-4, 5):
        for delta in range(-3, 4):
            for p in [2, 3, 4]:
                for q in [-1, 0, 1, 2]:
                    a_fn = lambda n, a=alpha, b=beta, d=delta: a*n*n + b*n + d
                    b_fn = lambda n, P=p, Q=q: P*n + Q
                    V = check_conv(a_fn, b_fn)
                    if V is None:
                        continue
                    # Skip if it's a known pi-family member
                    rpslq = pslq([V, mpf(1), pi])
                    if rpslq is not None:
                        continue  # Already pi-related
                    # Skip rational values
                    rpslq2 = pslq([V, mpf(1)])
                    if rpslq2 is not None:
                        continue
                    novel.append((V, alpha, beta, delta, p, q))

print(f"  Found {len(novel)} non-pi, non-rational GCF values")
# PSLQ against extended basis
for V, alpha, beta, delta, p, q in novel[:100]:  # check first 100
    basis = [V, mpf(1), Cat, Z3, G1_3, G1_4, log(mpf(2))]
    r = pslq(basis, maxcoeff=1000)
    if r is not None and r[0] != 0:
        # Check it's not trivial
        nonzero = sum(1 for x in r if x != 0)
        if nonzero >= 2 and abs(r[0]) <= 100:
            # Verify
            check = sum(r[i]*basis[i] for i in range(len(basis)))
            if fabs(check) < mpf("1e-30"):
                print(f"  PSLQ HIT: a={alpha}n^2+{beta}n+{delta}, b={p}n+{q}")
                print(f"    V = {nstr(V, 20)}")
                print(f"    {r[0]}V + {r[1]} + {r[2]}Cat + {r[3]}Z3 + {r[4]}G(1/3) + {r[5]}G(1/4) + {r[6]}ln2 = 0")
                hits.append(("PSLQ-multi", alpha, beta, delta, p, q, 30))

print()

# ─── SEARCH C: Cubic a_n (non-degenerate, ghost-filtered) ───
print("═══ SEARCH C: Cubic a_n (ghost-filtered) ═══")
cubic_hits = 0
for a3 in [-1, 1]:
    for a2 in range(-3, 4):
        for a1 in range(-3, 4):
            for a0 in range(-3, 4):
                for p in [2, 3, 4]:
                    for q in [-1, 0, 1, 2]:
                        a_fn = lambda n, c3=a3, c2=a2, c1=a1, c0=a0: c3*n**3 + c2*n*n + c1*n + c0
                        b_fn = lambda n, P=p, Q=q: P*n + Q
                        V = check_conv(a_fn, b_fn)
                        if V is None:
                            continue
                        for name, tgt in targets.items():
                            d = fabs(V - tgt)
                            if 0 < d < mpf("1e-20"):
                                dig = int(-log(d, 10))
                                if dig >= 15:
                                    msg = f"  HIT: a={a3}n^3+{a2}n^2+{a1}n+{a0}, b={p}n+{q} -> {name} [{dig}d]"
                                    print(msg)
                                    cubic_hits += 1
                                    hits.append((name, a3, a2, a1, a0, p, q, dig))

print(f"  Cubic hits: {cubic_hits}")
print()

# ─── SUMMARY ───
print("═══ SUMMARY ═══")
if hits:
    print(f"Total hits: {len(hits)}")
    for h in hits:
        print(f"  {h}")
else:
    print("No Gamma/Catalan/Apery hits found from polynomial GCFs.")
    print("This is a NEGATIVE RESULT: polynomial-coefficient GCFs appear")
    print("to be limited to π-related constants (via hypergeometric system).")
    print()
    print("Theoretical explanation: Gauss CFs for ₂F₁(a,b;c;z) with")
    print("half-integer parameters at z=-1 produce only π-rational values.")
    print("Gamma(1/3), Gamma(1/4), Catalan, and ζ(3) require different")
    print("CF families (e.g., q-hypergeometric, modular, or Ramanujan-type).")
