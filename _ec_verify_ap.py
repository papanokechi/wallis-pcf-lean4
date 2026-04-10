"""Verify a_p match: our quartic Jacobian vs LMFDB 22755.c3"""

def ap_short(A, B, p):
    count = 0
    Ap, Bp = A % p, B % p
    for x in range(p):
        rhs = (x**3 + Ap*x + Bp) % p
        if rhs == 0: count += 1
        elif p > 2 and pow(rhs, (p-1)//2, p) == 1: count += 2
    return p + 1 - (count + 1)

def ap_general(a1, a2, a3, a4, a6, p):
    count = 0
    for x in range(p):
        for y in range(p):
            lhs = (y**2 + a1*x*y + a3*y) % p
            rhs = (x**3 + a2*x**2 + a4*x + a6) % p
            if lhs == rhs:
                count += 1
    return p + 1 - count

primes = [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73]

print("Comparison: our quartic Jacobian vs LMFDB 22755.c3")
print(f"{'p':>5s}  {'ours':>5s}  {'LMFDB':>6s}  match?")

A_ours = -75576267
B_ours = -252808806726
a1,a2,a3,a4,a6 = 1,1,1,-58315,5394272

matches = 0
for p in primes:
    ap_us = ap_short(A_ours, B_ours, p)
    ap_lm = ap_general(a1,a2,a3,a4,a6, p)
    m = "YES" if ap_us == ap_lm else f"NO"
    if ap_us == ap_lm: matches += 1
    print(f"{p:5d}  {ap_us:+5d}  {ap_lm:+6d}  {m}")

print(f"\nMatches: {matches}/{len(primes)}")
if matches < len(primes):
    # Check if they differ by a twist: ap_ours = chi(p)*ap_lmfdb for some character chi
    print("\nChecking quadratic twist: ap_ours = (D/p) * ap_lmfdb ?")
    for D in [-1, -3, -4, 5, -5, 37, -37, 41, -41, 3, -15, 15, -185, 185]:
        twist_ok = True
        for p in primes:
            if p in [3,5,37,41]: continue  # skip bad primes
            ap_us = ap_short(A_ours, B_ours, p)
            ap_lm = ap_general(a1,a2,a3,a4,a6, p)
            # Kronecker symbol (D/p)
            if p == 2:
                Dmod8 = D % 8
                chi = 1 if Dmod8 in [1,7] else (-1 if Dmod8 in [3,5] else 0)
            else:
                chi = pow(D % p, (p-1)//2, p)
                if chi > 1: chi = chi - p
            if ap_us != chi * ap_lm:
                twist_ok = False
                break
        if twist_ok:
            print(f"  D={D}: TWIST MATCH!")
        
    # Also try all curves in the isogeny class
    print("\nChecking other curves in 22755.c isogeny class:")
    curves = {
        "22755.c1": [1,1,1,-481845,-126290430],
        "22755.c2": [1,1,1,-66720,3726720],
        "22755.c3": [1,1,1,-58315,5394272],
        "22755.c4": [1,1,1,-58310,5395250],
        "22755.c5": [1,1,1,-49990,6999332],
        "22755.c6": [1,1,1,213925,27188642],
    }
    for label, ainv in curves.items():
        a1,a2,a3,a4,a6 = ainv
        m = 0
        for p in primes:
            ap_us = ap_short(A_ours, B_ours, p)
            ap_lm = ap_general(a1,a2,a3,a4,a6, p)
            if ap_us == ap_lm: m += 1
        print(f"  {label}: {m}/{len(primes)} matches")
