"""
Round 10D part 2: Targeted β_k / A₂ pattern analysis
=====================================================
Key observation from part 1: 
  Δ³(A₂·c²) ≈ π²/24 → A₂·c² is cubic in k with a₃ = π²/144

Now: extract all 4 cubic coefficients and try to identify them.
"""
from mpmath import mp, mpf, sqrt as msqrt, pi as mpi, pslq as mpslq
import numpy as np
mp.dps = 50

# ─── Extracted values from relay_round10d_beta_extraction.py ───
# β_k values (11-digit precision)
beta_k = {
    1: mpf('+0.02010216758643'),
    2: mpf('-0.05357990661175'),
    3: mpf('-0.13080704340662'),
    4: mpf('-0.21870338853280'),
    5: mpf('-0.31869377113434'),
}

# A₂ values = β_struct - β
A2_k = {
    1: mpf('-0.034324221061'),
    2: mpf('+0.032925209426'),
    3: mpf('+0.111509112273'),
    4: mpf('+0.208551633214'),
    5: mpf('+0.325477601393'),
}

# A₁ closed form 
def ck(k): return mpi * msqrt(mpf(2*k)/3)
def kk(k): return mpf(-(k+3))/4
def A1(k): return -mpf(k)*ck(k)/48 - mpf((k+1)*(k+3))/(8*ck(k))

# ═══════════════════════════════════════════════════════════════
# ANALYSIS 1: A₂·c² as cubic polynomial in k
# ═══════════════════════════════════════════════════════════════
print("="*70)
print("ANALYSIS 1: A₂·c² as cubic polynomial in k")
print("="*70)

A2c2 = {}
for k in range(1,6):
    A2c2[k] = A2_k[k] * ck(k)**2
    print(f"  k={k}: A₂·c² = {float(A2c2[k]):+.14f}")

print(f"\n  Finite differences:")
d1 = [A2c2[k+1] - A2c2[k] for k in range(1,5)]
d2 = [d1[i+1] - d1[i] for i in range(3)]
d3 = [d2[i+1] - d2[i] for i in range(2)]

for i, v in enumerate(d1):
    print(f"  Δf({i+1}) = {float(v):+.14f}")
for i, v in enumerate(d2):
    print(f"  Δ²f({i+1}) = {float(v):+.14f}")
for i, v in enumerate(d3):
    print(f"  Δ³f({i+1}) = {float(v):+.14f}")

pi2_24 = mpi**2/24
print(f"\n  π²/24 = {float(pi2_24):.14f}")
for i, v in enumerate(d3):
    print(f"  Δ³f({i+1}) - π²/24 = {float(v - pi2_24):.2e}")

# ═══════════════════════════════════════════════════════════════
# Fit cubic: A₂·c² = a₃k³ + a₂k² + a₁k + a₀
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("Cubic fit: A₂·c² = a₃k³ + a₂k² + a₁k + a₀")
print("="*70)

# Use forward differences to get exact coefficients from data
a3 = float(d3[0]) / 6
a2 = (float(d2[0]) - 12*a3) / 2
a1 = float(d1[0]) - 7*a3 - 3*a2
a0 = float(A2c2[1]) - a3 - a2 - a1

print(f"  a₃ = {a3:.16f}  (π²/144 = {float(mpi**2/144):.16f})")
print(f"  a₂ = {a2:.16f}")
print(f"  a₁ = {a1:.16f}  (-1/4 = -0.25)")
print(f"  a₀ = {a0:.16f}  (-3/16 = -0.1875)")

# Check predictions
print(f"\n  Verification:")
for k in range(1,6):
    pred = a3*k**3 + a2*k**2 + a1*k + a0
    actual = float(A2c2[k])
    print(f"    k={k}: pred={pred:+.14f}, actual={actual:+.14f}, gap={abs(pred-actual):.2e}")

# ═══════════════════════════════════════════════════════════════
# PSLQ on a₂ coefficient
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("PSLQ on a₂ = {:.16f}".format(a2))
print("="*70)

a2_mp = mpf(a2)

def try_pslq(name, basis, mc=500):
    vec = [a2_mp] + list(basis)
    r = mpslq(vec, maxcoeff=mc, maxsteps=10000)
    if r is not None and r[0] != 0:
        check = sum(r[i]*vec[i] for i in range(len(vec)))
        if abs(float(check)) < 1e-6:
            print(f"  {name}: FOUND {r} (res={float(check):.2e})")
            return r
    if r is not None and r[0] == 0:
        print(f"  {name}: spurious (A₂ coeff=0)")
    else:
        print(f"  {name}: ✗")
    return None

try_pslq("a₂ ~ {1, π²}", [mpf(1), mpi**2])
try_pslq("a₂ ~ {1, π², π⁴}", [mpf(1), mpi**2, mpi**4])
try_pslq("a₂ ~ {1/n for n in [1..10]}", 
         [mpf(1)/n for n in range(1,11)], mc=100)
try_pslq("a₂ ~ {π²/n for n in [12,24,48,96,144,288]}", 
         [mpi**2/n for n in [12,24,48,96,144,288]], mc=200)
try_pslq("a₂ ~ {1, π², 1/π²}", [mpf(1), mpi**2, 1/mpi**2])

# Try: a₂ = (aπ² + b)/c for various small c
print("\n  Systematic search: a₂ = (aπ² + b)/D")
for D in range(1, 1001):
    target = a2 * D
    # Check if target = a·π² + b where a,b are small integers
    a_trial = round(target / float(mpi**2))
    for a in range(a_trial-3, a_trial+4):
        b_trial = target - a * float(mpi**2)
        b_int = round(b_trial)
        if abs(b_trial - b_int) < 0.001 and abs(a) <= 50 and abs(b_int) <= 200:
            pred = (a * float(mpi**2) + b_int) / D
            if abs(pred - a2) < 1e-8:
                print(f"    D={D}: a₂ = ({a}π² + {b_int})/{D} = {pred:.14f} (gap={abs(pred-a2):.2e})")

# ═══════════════════════════════════════════════════════════════
# PSLQ on a₁ residual (is it -1/4?)
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"a₁ residual: a₁ + 1/4 = {a1 + 0.25:.2e}")
print("="*70)

# ═══════════════════════════════════════════════════════════════
# PSLQ on a₀ residual (is it -3/16?)
# ═══════════════════════════════════════════════════════════════
print(f"a₀ residual: a₀ + 3/16 = {a0 + 0.1875:.2e}")
print("="*70)

# ═══════════════════════════════════════════════════════════════
# ALTERNATIVE: PSLQ directly on β values
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("DIRECT PSLQ ON β_k")
print("="*70)

for k in [1,2,3,4,5]:
    c = ck(k)
    kap = kk(k)
    b = beta_k[k]
    a1_val = A1(k)
    
    print(f"\n  k={k}: β = {float(b):+.14f}")
    
    # Try: β = rational function of c, κ, A₁
    # β = p₁c⁴ + p₂c² + p₃κ² + p₄κ + p₅cA₁ + p₆A₁² + p₇ + p₈/c² + p₉κ/c²
    basis_extended = [
        c**4, c**2, kap**2, kap, c*a1_val, a1_val**2, 
        mpf(1), 1/c**2, kap/c**2
    ]
    
    vec = [b] + basis_extended
    r = mpslq(vec, maxcoeff=2000, maxsteps=10000)
    if r is not None and r[0] != 0:
        check = sum(r[i]*vec[i] for i in range(len(vec)))
        if abs(float(check)) < 1e-6:
            labels = ['c⁴','c²','κ²','κ','cA₁','A₁²','1','1/c²','κ/c²']
            parts = []
            for i, (coeff, lab) in enumerate(zip(r[1:], labels)):
                if coeff != 0:
                    parts.append(f"({-coeff}/{r[0]}){lab}")
            print(f"    FOUND: β = {' + '.join(parts)}")
            print(f"    relation: {r}, res={float(check):.2e}")

# ═══════════════════════════════════════════════════════════════
# Try: β·c² as nice polynomial in k and π²
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("β·c² as polynomial in k")
print("="*70)

bc2 = {k: beta_k[k] * ck(k)**2 for k in range(1,6)}
for k in range(1,6):
    print(f"  k={k}: β·c² = {float(bc2[k]):+.14f}")

# Finite differences of β·c²
d1b = [bc2[k+1] - bc2[k] for k in range(1,5)]
d2b = [d1b[i+1] - d1b[i] for i in range(3)]
d3b = [d2b[i+1] - d2b[i] for i in range(2)]

print(f"\n  Third differences of β·c²:")
for i, v in enumerate(d3b):
    print(f"  Δ³(β·c²)({i+1}) = {float(v):+.14f}")

# ═══════════════════════════════════════════════════════════════
# Try: β as a⁴/D₁ + c²/D₂ + A₁/D₃ + constant
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("β decomposition attempt")
print("="*70)

# β = c⁴/384 + c²(1+2κ)/16 + κ(κ+1)/2 - cA₁/4 - A₂
# We know the first 4 terms (β_struct). So β = β_struct - A₂.
# What if A₂ has the form: A₂ = (polynomial in k)/c² where poly is degree 3?

# A₂ = [π²k³/144 + a₂k² + a₁k + a₀] / c²
# Since c² = 2kπ²/3:
# A₂ = 3[π²k³/144 + a₂k² + a₁k + a₀] / (2kπ²)
#     = k²/96 + 3a₂k/(2π²) + 3a₁/(2π²) + 3a₀/(2kπ²)

print(f"\n  If A₂·c² = (π²/144)k³ + a₂k² + a₁k + a₀:")
print(f"  Then A₂ = k²/96 + 3a₂k/(2π²) + 3a₁/(2π²) + 3a₀/(2kπ²)")
print(f"  a₂ = {a2:.16f}")
print(f"  3a₂/(2π²) = {3*a2/(2*float(mpi**2)):.16f}")

# Can we express a₂ in terms of π²?
# Try PSLQ: a₂ ~ a·π² + b (rational)
a2h = mpf(str(a2))  # high precision
r = mpslq([a2h, mpi**2, mpf(1)], maxcoeff=5000, maxsteps=20000)
if r is not None and r[0] != 0:
    print(f"\n  PSLQ: a₂ = ({-r[1]}/{r[0]})π² + ({-r[2]}/{r[0]})")
    pred = (-r[1]*mpi**2 - r[2]) / r[0]
    print(f"  pred = {float(pred):.16f}, gap = {abs(float(pred-a2h)):.2e}")
else:
    print(f"\n  PSLQ on {{a₂, π², 1}}: {'found but coeff=0' if r else 'no relation'}")

# Also try: a₂ ~ a·π⁴ + b·π² + c
r2 = mpslq([a2h, mpi**4, mpi**2, mpf(1)], maxcoeff=5000, maxsteps=20000)
if r2 is not None and r2[0] != 0:
    print(f"\n  PSLQ: a₂ = ({-r2[1]}/{r2[0]})π⁴ + ({-r2[2]}/{r2[0]})π² + ({-r2[3]}/{r2[0]})")
    pred = (-r2[1]*mpi**4 - r2[2]*mpi**2 - r2[3]) / r2[0]
    print(f"  pred = {float(pred):.16f}, gap = {abs(float(pred-a2h)):.2e}")
elif r2 is not None:
    print(f"  PSLQ on {{a₂, π⁴, π², 1}}: found but A₂ coeff=0")
else:
    print(f"  PSLQ on {{a₂, π⁴, π², 1}}: no relation")

# ═══════════════════════════════════════════════════════════════
# ALTERNATIVE: fit A₂·c to a polynomial (since A₁·c was key)
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("A₂·c as polynomial in k")
print("="*70)

A2c = {}
for k in range(1,6):
    A2c[k] = A2_k[k] * ck(k)
    print(f"  k={k}: A₂·c = {float(A2c[k]):+.14f}")

d1ac = [A2c[k+1] - A2c[k] for k in range(1,5)]
d2ac = [d1ac[i+1] - d1ac[i] for i in range(3)]
d3ac = [d2ac[i+1] - d2ac[i] for i in range(2)]

print(f"\n  Differences:")
for i, v in enumerate(d1ac):
    print(f"  Δ(A₂·c)({i+1}) = {float(v):+.14f}")
for i, v in enumerate(d2ac):
    print(f"  Δ²(A₂·c)({i+1}) = {float(v):+.14f}")
for i, v in enumerate(d3ac):
    print(f"  Δ³(A₂·c)({i+1}) = {float(v):+.14f}")

# ═══════════════════════════════════════════════════════════════
# Key comparison: A₁·c pattern was quadratic in k
# A₁·c = -k·c²/48 - (k+1)(k+3)/8
#       = -kπ²·(2k/3)/48 - (k+1)(k+3)/8
# Let's verify A₂·c = a·k³ polynomial / something
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("Recall: A₁·c was quadratic in k")
print("="*70)

for k in range(1,6):
    val = float(A1(k) * ck(k))
    pred = -k * float(ck(k))**2 / 48 - (k+1)*(k+3)/8
    print(f"  k={k}: A₁·c = {val:.14f}, -kc²/48 - (k+1)(k+3)/8 = {pred:.14f}")

# A₁·c = -kc²/48 - (k+1)(k+3)/8 = -k·(2kπ²/3)/48 - (k+1)(k+3)/8
#       = -k²π²/72 - (k²+4k+3)/8

# So A₁·c is degree-2 in k. Natural conjecture: A₂·c is degree-3 in k.
# A₂·c = poly(k) where poly = p₃k³ + p₂k² + p₁k + p₀

# Fit from A₂·c values
A2c_arr = np.array([float(A2c[k]) for k in range(1,6)])
X = np.array([[k**3, k**2, k, 1] for k in range(1,6)], dtype=float)
params, res, _, _ = np.linalg.lstsq(X, A2c_arr, rcond=None)
p3, p2, p1, p0 = params

print(f"\n  Fit: A₂·c = {p3:.16f}k³ + {p2:.16f}k² + {p1:.16f}k + {p0:.16f}")
for k in range(1,6):
    pred = p3*k**3 + p2*k**2 + p1*k + p0
    print(f"    k={k}: pred={pred:+.14f}, actual={float(A2c[k]):+.14f}, gap={abs(pred-float(A2c[k])):.2e}")

# PSLQ on each coefficient
print(f"\n  PSLQ on p₃ = {p3:.16f}")
r = mpslq([mpf(str(p3)), mpi**2, mpf(1)], maxcoeff=10000, maxsteps=20000)
if r and r[0] != 0:
    print(f"    FOUND: p₃ = ({-r[1]}/{r[0]})π² + ({-r[2]}/{r[0]})")

print(f"\n  PSLQ on p₂ = {p2:.16f}")
r = mpslq([mpf(str(p2)), mpi**2, mpf(1)], maxcoeff=10000, maxsteps=20000)
if r and r[0] != 0:
    print(f"    FOUND: p₂ = ({-r[1]}/{r[0]})π² + ({-r[2]}/{r[0]})")

print(f"\n  PSLQ on p₁ = {p1:.16f}")
r = mpslq([mpf(str(p1)), mpi**2, mpf(1)], maxcoeff=10000, maxsteps=20000)
if r and r[0] != 0:
    print(f"    FOUND: p₁ = ({-r[1]}/{r[0]})π² + ({-r[2]}/{r[0]})")

print(f"\n  PSLQ on p₀ = {p0:.16f}")
r = mpslq([mpf(str(p0)), mpi**2, mpf(1)], maxcoeff=10000, maxsteps=20000)
if r and r[0] != 0:
    print(f"    FOUND: p₀ = ({-r[1]}/{r[0]})π² + ({-r[2]}/{r[0]})")

# ═══════════════════════════════════════════════════════════════
# SELECTION RULE analog for A₂
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("SELECTION RULE for A₂")
print("="*70)

# For A₁: Δ₁ = A₁ - (-kc/48), and Δ₁·c = -(k+3)(k-1)/8
# Try: A₂ - (something involving k²c) → compute Δ₂·c and look for polynomial

# Natural base: the first non-trivial piece of A₂ from the derivation
# might scale as k²c²/D.  
# A₂ = k²/96 + something?  Since A₂ = (A₂·c²)/c² and A₂·c²≈π²k³/144,
# A₂ ≈ k²/96 as leading behavior.

for base_name, base_fn in [
    ("k²c/D (D=96)", lambda k: mpf(k**2)*ck(k)/96),
    ("k²c/D (D=288)", lambda k: mpf(k**2)*ck(k)/288),
    ("k²c/D (D=1152)", lambda k: mpf(k**2)*ck(k)/1152),
    ("-k²c/1152", lambda k: -mpf(k**2)*ck(k)/1152),
]:
    print(f"\n  Base: {base_name}")
    for k in range(1,6):
        delta = A2_k[k] - base_fn(k)
        delta_c = delta * ck(k)
        delta_c2 = delta * ck(k)**2
        print(f"    k={k}: Δ₂={float(delta):+.12f}, Δ₂·c={float(delta_c):+.12f}, Δ₂·c²={float(delta_c2):+.12f}")

# ═══════════════════════════════════════════════════════════════
# Compute exact k=1 A₂ from Rademacher
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("k=1 EXACT A₂ from Rademacher expansion")
print("="*70)

# For k=1, the exact β₁ = (π⁶-33π⁴+180π²+648)/(864π²)
beta1_exact = (mpi**6 - 33*mpi**4 + 180*mpi**2 + 648) / (864 * mpi**2)
c1 = ck(1)
k1 = kk(1)
A1_1 = A1(1)

beta_struct_1 = c1**4/384 + c1**2/16 + c1**2*k1/8 - c1*A1_1/4 + k1**2/2 + k1/2
A2_exact_1 = beta_struct_1 - beta1_exact

print(f"  β₁(exact) = {float(beta1_exact):.16f}")
print(f"  β_struct  = {float(beta_struct_1):.16f}")
print(f"  A₂^(1) exact = {float(A2_exact_1):.16f}")
print(f"  A₂^(1) extracted = {float(A2_k[1]):.16f}")
print(f"  Gap: {abs(float(A2_exact_1) - float(A2_k[1])):.2e}")

# Try to simplify A₂^(1) analytically
print(f"\n  Attempting to simplify A₂^(1):")
print(f"  A₂^(1)·c₁² = {float(A2_exact_1 * c1**2):.16f}")
print(f"  A₂^(1)·c₁  = {float(A2_exact_1 * c1):.16f}")
print(f"  A₂^(1)·864π² = {float(A2_exact_1 * 864 * mpi**2):.12f}")

# Since β₁ = (π⁶-33π⁴+180π²+648)/(864π²), let's compute A₂^(1) symbolically
# β_struct = c⁴/384 + c²(1+2κ)/16 + κ(κ+1)/2 - cA₁/4
# With c² = 2π²/3, κ = -1, A₁ = -(π²+72)/(24π√6)
# c⁴ = 4π⁴/9, c = π√(2/3)
# c⁴/384 = 4π⁴/(9·384) = π⁴/864
# c²(1+2κ)/16 = (2π²/3)(1-2)/16 = -2π²/(48) = -π²/24
# κ(κ+1)/2 = (-1)(0)/2 = 0
# -cA₁/4 = -(π√(2/3))·(-(π²+72)/(24π√6))/4
#         = (π²+72)·√(2/3)/(96π√6)
#         = (π²+72)/(96·3)  [since √(2/3)/√6 = 1/3]
#         = (π²+72)/288

# So β_struct = π⁴/864 - π²/24 + (π²+72)/288
#             = π⁴/864 - π²/24 + π²/288 + 1/4
#             = π⁴/864 + π²(-12/288 + 1/288) + 1/4
#             = π⁴/864 - 11π²/288 + 1/4

beta_struct_symbolic = mpi**4/864 - 11*mpi**2/288 + mpf(1)/4
print(f"\n  β_struct symbolic check: {float(beta_struct_symbolic):.16f}")
print(f"  β_struct numerical:      {float(beta_struct_1):.16f}")
print(f"  Gap: {abs(float(beta_struct_symbolic - beta_struct_1)):.2e}")

# A₂^(1) = β_struct - β₁ 
#         = π⁴/864 - 11π²/288 + 1/4 - (π⁶-33π⁴+180π²+648)/(864π²)
# Let's put over common denominator 864π²:
# = π⁶/864 - 11π⁴·3/864 + 864π²/4/864 - (π⁶-33π⁴+180π²+648)/864
# Wait, denominator is 864π²:
# = π⁶/(864) × (π²/π²) ... this is getting messy. Let me compute directly.

# 864π² × A₂ = 864π² × [π⁴/864 - 11π²/288 + 1/4 - (π⁶-33π⁴+180π²+648)/(864π²)]
# = π⁶ - 864·11π⁴/288 + 864π²/4 - (π⁶-33π⁴+180π²+648)
# = π⁶ - 33π⁴ + 216π² - π⁶ + 33π⁴ - 180π² - 648
# = 36π² - 648
# = 36(π² - 18)

A2_1_check = 36*(mpi**2 - 18) / (864*mpi**2)
print(f"\n  A₂^(1) = 36(π²-18)/(864π²) = (π²-18)/(24π²)")
print(f"  = {float(A2_1_check):.16f}")
print(f"  Expected: {float(A2_exact_1):.16f}")
print(f"  Gap: {abs(float(A2_1_check - A2_exact_1)):.2e}")

# Simplify: 36/864 = 1/24
# So A₂^(1) = (π²-18)/(24π²)
A2_1_simple = (mpi**2 - 18) / (24 * mpi**2)
print(f"\n  SIMPLIFIED: A₂^(1) = (π²-18)/(24π²) = {float(A2_1_simple):.16f}")

# Now let's see if there's a general pattern.
# For k=1: A₂·c² = (π²-18)·c²/(24π²) = (π²-18)·(2π²/3)/(24π²) = (π²-18)/(36)
A2c2_1_exact = (mpi**2 - 18) / 36
print(f"  A₂^(1)·c² = (π²-18)/36 = {float(A2c2_1_exact):.16f}")
print(f"  Numerical:                  {float(A2c2[1]):.16f}")

# For the general case, A₂·c² = (π²/144)k³ + a₂k² + a₁k + a₀
# At k=1: (π²-18)/36 = π²/144 + a₂ + a₁ + a₀
# Check: (π²-18)/36 = π²/36 - 1/2
# And π²/144 + a₂ + a₁ + a₀ = π²/144 + 0.14312 + (-0.24999) + (-0.18750)
#                              = 0.06854 + 0.14312 - 0.24999 - 0.18750
#                              = -0.22584

# (π²-18)/36 = (9.8696-18)/36 = -8.1304/36 = -0.22585. ✓

# π²/36 - 1/2 = 0.27416 - 0.5 = -0.22584. So A₂^(1)·c² = π²/36 - 1/2.
print(f"\n  π²/36 - 1/2 = {float(mpi**2/36 - mpf(1)/2):.16f}")

print(f"\n{'='*70}")
print("SUMMARY OF EXTRACTED COEFFICIENTS")
print("="*70)
print(f"  A₂·c² = (π²/144)k³ + a₂k² + a₁k + a₀")
print(f"  a₃ = π²/144 = {float(mpi**2/144):.16f}  [IDENTIFIED]")
print(f"  a₂ = {a2:.16f}  [TRYING TO IDENTIFY]")
print(f"  a₁ = {a1:.16f}  (= -1/4 + {a1+0.25:.6e})")
print(f"  a₀ = {a0:.16f}  (= -3/16 + {a0+3/16:.6e})")

# Check: does the cubic factorize at k=1? 
# A₂^(1)·c₁² = π²/36 - 1/2
# From poly: π²/144 + a₂ + a₁ + a₀ = π²/36 - 1/2
# So: a₂ + a₁ + a₀ = π²/36 - 1/2 - π²/144 = π²(4-1)/144 - 1/2 = 3π²/144 - 1/2 = π²/48 - 1/2
print(f"\n  Check: a₂+a₁+a₀ = {a2+a1+a0:.16f}")
print(f"  π²/48 - 1/2 = {float(mpi**2/48) - 0.5:.16f}")

# For k=2:  8π²/144 + 4a₂ + 2a₁ + a₀ = A₂^(2)·c₂² = 0.43328
# This should equal some nice expression.
# We know from PSLQ that A₂^(2)·c₂² doesn't have a simple {k³,k²,k,1} relation
# (those were spurious), but the cubic polynomial IS determined by 5 data points.

print("\n=== DONE ===")
