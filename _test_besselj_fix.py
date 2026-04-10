"""Quick test: Bessel J ratio identification + CAS verification."""
import mpmath
from ramanujan_agent.proof_engine import identify_special_function, cas_verify

# GCF a(n)=-2, b(n)=-2n+2: A=-2, alpha=-2, beta=2
# c = A/alpha^2 = -2/4 = -0.5 (negative → Bessel J branch)
an = [-2]
bn = [-2, 2]

mp = mpmath.mp.clone()
mp.dps = 120

# Evaluate GCF at high precision using Lentz
tiny = mp.mpf(10) ** (-mp.dps)
f = mp.mpf(bn[0] * 0 + bn[1])  # b(0) = 2
if f == 0: f = tiny
C, D = f, mp.mpf(0)
for n in range(1, 501):
    a_n = mp.mpf(an[0])
    b_n = mp.mpf(bn[0] * n + bn[1])
    D = b_n + a_n * D
    if D == 0: D = tiny
    D = 1 / D
    C = b_n + a_n / C
    if C == 0: C = tiny
    delta = C * D
    f *= delta

print(f"CF value (120 dps): {mp.nstr(f, 30)}")

# Identify
result = identify_special_function(an, bn, f, prec=100)
print(f"\nIdentified: {result['identified']}")
for c in result.get('candidates', []):
    print(f"  Type: {c['type']}")
    print(f"  Formula: {c.get('formula', 'N/A')}")
    print(f"  Expression: {c.get('expression', 'MISSING!')}")
    print(f"  Match error: {c.get('match_error', 'N/A')}")

# CAS verify if expression exists
best = result.get('candidates', [{}])[0] if result['candidates'] else {}
if best.get('expression'):
    print(f"\nRunning CAS verify on: {best['expression']}")
    cas = cas_verify(best['expression'], f, prec=100)
    print(f"  Verified: {cas['verified']}")
    print(f"  Match digits: {cas['match_digits']}")
    if cas.get('error'):
        print(f"  Error: {cas['error']}")
else:
    print("\nNO EXPRESSION — CAS verify skipped (this is the bug)")
