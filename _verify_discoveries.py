"""High-precision verification of discovered GCF identities."""
from mpmath import mp, mpf, nstr, fabs, log, pi, gamma, sqrt, e as E

mp.dps = 100

def gcf_bw(a_fn, b_fn, depth=500):
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = b_fn(n) + a_fn(n + 1) / val
    return b_fn(0) + a_fn(1) / val

discoveries = [
    ("D1: a_n=(n+1)^2, b_n=2n+3",
     lambda n: mpf((n+1)**2), lambda n: mpf(2*n+3),
     "pi/(4-pi)", pi/(4-pi)),
    
    ("D2: a_n=n^2+2n, b_n=2n+3",
     lambda n: mpf(n**2+2*n), lambda n: mpf(2*n+3),
     "4/(pi-2)", 4/(pi-2)),
    
    ("D3: a_n=1, b_n=4n+2",
     lambda n: mpf(1), lambda n: mpf(4*n+2),
     "(1+e)/(e-1)", (1+E)/(E-1)),
    
    ("D4: a_n=-2n^2-n, b_n=3n+3",
     lambda n: mpf(-2*n**2-n), lambda n: mpf(3*n+3),
     "2/(pi-4)", 2/(pi-4)),
    
    ("D5: a_n=-2n^2+n, b_n=3n+2",
     lambda n: mpf(-2*n**2+n), lambda n: mpf(3*n+2),
     "2/(pi-2)", 2/(pi-2)),

    ("D6: a_n=-2n^2+3n, b_n=3n+2",
     lambda n: mpf(-2*n**2+3*n), lambda n: mpf(3*n+2),
     "-12/(4-3*pi)", -12/(4-3*pi)),

    ("D7: a_n=n, b_n=n",
     lambda n: mpf(n), lambda n: mpf(n),
     "1/(e-1)", 1/(E-1)),

    ("D8: a_n=n+1, b_n=n+1",
     lambda n: mpf(n+1), lambda n: mpf(n+1),
     "e-1", E-1),

    ("D9: a_n=-n, b_n=n+3",
     lambda n: mpf(-n), lambda n: mpf(n+3),
     "e", E),
    
    ("D10: a_n=n, b_n=n+2",
     lambda n: mpf(n), lambda n: mpf(n+2),
     "-1/(5-2e)", -1/(5-2*E)),

    ("D11: a_n=n+2, b_n=n+2",
     lambda n: mpf(n+2), lambda n: mpf(n+2),
     "2/(e-1)", 2/(E-1)),

    ("D12: a_n=n+1, b_n=n+2",
     lambda n: mpf(n+1), lambda n: mpf(n+2),
     "-1/(3-e)", -1/(3-E)),

    # Sqrt family
    ("D13: a_n=k*n(n+1), b_n=2(n+1), k=5",
     lambda n: 5*mpf(n*(n+1)), lambda n: 2*mpf(n+1),
     "1+sqrt(6)", 1+sqrt(6)),

    ("D14: a_n=k*n(n+1), b_n=2(n+1), k=10",
     lambda n: 10*mpf(n*(n+1)), lambda n: 2*mpf(n+1),
     "1+sqrt(11)", 1+sqrt(11)),
]

for label, a_fn, b_fn, closed_str, expected in discoveries:
    V = gcf_bw(a_fn, b_fn, 500)
    diff = fabs(V - expected)
    if diff == 0:
        digits = 95
    elif diff > 0 and diff < 1:
        digits = int(-log(diff, 10))
    else:
        digits = 0
    status = "VERIFIED" if digits >= 50 else ("PARTIAL" if digits >= 10 else "FAILED")
    print(f"{label}")
    print(f"  V = {nstr(V, 60)}")
    print(f"  = {closed_str} = {nstr(expected, 60)}")
    print(f"  [{status}: {digits} digits]")
    print()
