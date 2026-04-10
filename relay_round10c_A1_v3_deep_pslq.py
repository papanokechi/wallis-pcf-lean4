#!/usr/bin/env python3
"""
Deep PSLQ search for A₁^(k) closed forms.
Uses the 12-digit values extracted from v2.
Tries cross-k relations, Bessel-related, Bernoulli, digamma, and more.
"""
from mpmath import mp, mpf, pi, sqrt, log, euler, zeta, gamma as mpgamma
from mpmath import pslq, loggamma, digamma, diff

mp.dps = 50

# Allow mpf in f-string format specs
_orig_fmt = mpf.__format__
def _mpf_fmt(self, spec):
    return format(float(self), spec) if spec else _orig_fmt(self, spec)
mpf.__format__ = _mpf_fmt

# 12-digit extracted values
A1 = {
    1: mpf('-0.443287976870986'),
    2: mpf('-0.668020786470785'),
    3: mpf('-0.952917420748228'),
}

# Exact k=1 for reference
A1_exact_1 = -(pi**2 + 72) / (24 * pi * sqrt(6))

# Meinardus parameters
def c_k(k): return pi * sqrt(mpf(2*k) / 3)
def kappa_k(k): return -(mpf(k) + 3) / 4
def L_k(k): return c_k(k)**2 / 8 + kappa_k(k)

# Base approximation: A₁ ≈ -k c / 48 + κ / c
def base_k(k):
    c, kap = c_k(k), kappa_k(k)
    return -k * c / 48 + kap / c

# Excess beyond base
Delta = {}
for k in [1, 2, 3]:
    Delta[k] = A1[k] - base_k(k)

print("=" * 70)
print("DEEP PSLQ SEARCH FOR A₁ CLOSED FORMS")
print("=" * 70)
print()
for k in [1, 2, 3]:
    c, kap = c_k(k), kappa_k(k)
    print(f"  k={k}: A₁ = {mp.nstr(A1[k], 16)}, c = {mp.nstr(c, 16)}, κ = {kap}")
    print(f"         base = {mp.nstr(base_k(k), 16)}, Δ = {mp.nstr(Delta[k], 16)}")
print()

# =====================================================================
# PART 1: Cross-family PSLQ (relate A₁(2) to A₁(1))
# =====================================================================
print("=" * 70)
print("PART 1: Cross-Family Relations")
print("=" * 70)

cross_bases = [
    ("{A₁(2), A₁(1), 1}", [A1[2], A1[1], 1]),
    ("{A₁(2), A₁(1), c₂, c₁, 1}", [A1[2], A1[1], c_k(2), c_k(1), 1]),
    ("{A₁(2), A₁(1), 1/c₂, 1/c₁, 1}", [A1[2], A1[1], 1/c_k(2), 1/c_k(1), 1]),
    ("{A₁(3), A₁(2), A₁(1), 1}", [A1[3], A1[2], A1[1], 1]),
    ("{A₁(3), A₁(2), c₃, c₂, 1}", [A1[3], A1[2], c_k(3), c_k(2), 1]),
    ("{A₁(3), A₁(1), c₃, c₁, 1}", [A1[3], A1[1], c_k(3), c_k(1), 1]),
    ("{A₁(3), A₁(2), A₁(1), c₃, c₂, c₁, 1}", [A1[3], A1[2], A1[1], c_k(3), c_k(2), c_k(1), 1]),
    ("{Δ₂, Δ₃, c₂, c₃, 1}", [Delta[2], Delta[3], c_k(2), c_k(3), 1]),
    ("{Δ₂, Δ₃, 1}", [Delta[2], Delta[3], 1]),
]

for name, vec in cross_bases:
    try:
        rel = pslq(vec, maxcoeff=1000, maxsteps=5000)
        if rel:
            # Check if A₁ coefficients are non-zero
            non_trivial = any(r != 0 for r in rel[:len(vec)])
            a1_involved = False
            if 'A₁' in name:
                # Check if any A₁ coefficient is nonzero
                a1_count = name.count('A₁')
                a1_involved = any(rel[i] != 0 for i in range(a1_count))
            rr = sum(r * v for r, v in zip(rel, vec))
            print(f"  {name}: FOUND {rel}  (res={abs(rr):.2e})")
            if a1_involved:
                print(f"    ** NON-TRIVIAL: involves A₁ terms! **")
        else:
            print(f"  {name}: no relation")
    except Exception as e:
        print(f"  {name}: error ({e})")

# =====================================================================
# PART 2: A₁(k) × c_k products — look for structure
# =====================================================================
print()
print("=" * 70)
print("PART 2: Products A₁·c and A₁·c² — PSLQ in {π², k, √k, 1}")
print("=" * 70)

for k in [2, 3]:
    c = c_k(k)
    prod_c = A1[k] * c
    prod_c2 = A1[k] * c * c
    print(f"\n  k={k}: A₁·c = {prod_c:.15f}")
    print(f"         A₁·c² = {prod_c2:.15f}")
    
    bases_prod = [
        ("{A₁·c, π², k, 1}", [prod_c, pi**2, mpf(k), 1]),
        ("{A₁·c, π², √k, 1}", [prod_c, pi**2, sqrt(mpf(k)), 1]),
        ("{A₁·c, kπ², k², k, 1}", [prod_c, k * pi**2, mpf(k**2), mpf(k), 1]),
        ("{A₁·c², π², k, 1}", [prod_c2, pi**2, mpf(k), 1]),
        ("{A₁·c², π³, π², k, 1}", [prod_c2, pi**3, pi**2, mpf(k), 1]),
        ("{A₁·c², kπ², k², k, 1}", [prod_c2, k * pi**2, mpf(k**2), mpf(k), 1]),
    ]
    
    for name, vec in bases_prod:
        try:
            rel = pslq(vec, maxcoeff=1000, maxsteps=5000)
            if rel and rel[0] != 0:
                rr = sum(r * v for r, v in zip(rel, vec))
                print(f"    {name}: FOUND {rel}  (res={abs(rr):.2e})")
            elif rel:
                print(f"    {name}: trivial {rel}")
            else:
                print(f"    {name}: no relation")
        except Exception as e:
            print(f"    {name}: error ({e})")

# =====================================================================
# PART 3: Richer single-k bases with Bessel/gamma/Bernoulli terms
# =====================================================================
print()
print("=" * 70)
print("PART 3: Extended Bases for k=2")
print("=" * 70)

c2 = c_k(2)
k2 = mpf(2)

# Some constants that might appear in Rademacher-like formulas
log2pi = log(2 * pi)
log2 = log(2)
log3 = log(3)
euler_const = euler
zeta3 = zeta(3)
zeta5 = zeta(5)
bernoulli_terms = [mpf(1)/6, mpf(1)/30, mpf(1)/42]  # B₂/2, B₄/4, B₆/6
psi_1 = digamma(1)  # = -γ
psi_half = digamma(mpf(1)/2)  # = -γ - 2log2
psi_k2 = digamma(k2)  # ψ(2) = 1 - γ

# Gamma values
gamma_half = mpgamma(mpf(1)/2)  # = √π
gamma_quarter = mpgamma(mpf(1)/4)

# I_{3/2} Bessel asymptotic terms etc.
# For k-colored, the relevant Bessel function is I_{(k+1)/2}
# The asymptotic expansion of I_ν(z) involves terms in 1/z

val = A1[2]

extended_bases = [
    # Logarithmic
    ("{A₁, c, 1/c, log(2), 1}", [val, c2, 1/c2, log2, 1]),
    ("{A₁, c, 1/c, log(3), 1}", [val, c2, 1/c2, log3, 1]),
    ("{A₁, c, 1/c, log(k), 1}", [val, c2, 1/c2, log(k2), 1]),
    
    # Digamma
    ("{A₁, c, 1/c, ψ(k), 1}", [val, c2, 1/c2, psi_k2, 1]),
    ("{A₁, c, 1/c, ψ(1/2), 1}", [val, c2, 1/c2, psi_half, 1]),
    
    # Bernoulli-weighted  
    ("{A₁, c/6, 1/(6c), 1}", [val, c2/6, 1/(6*c2), 1]),
    ("{A₁, c, 1/c, 1/12, 1}", [val, c2, 1/c2, mpf(1)/12, 1]),
    
    # Gamma function values
    ("{A₁, c, 1/c, Γ(1/4), 1}", [val, c2, 1/c2, gamma_quarter, 1]),
    ("{A₁, c, 1/c, log(Γ(k/2)), 1}", [val, c2, 1/c2, loggamma(k2/2), 1]),
    
    # Powers of c  
    ("{A₁, c³, c, 1/c, 1}", [val, c2**3, c2, 1/c2, 1]),
    ("{A₁, c³/6, c, 1/c, 1}", [val, c2**3/6, c2, 1/c2, 1]),
    ("{A₁, c³, c², c, 1/c, 1}", [val, c2**3, c2**2, c2, 1/c2, 1]),
    
    # Mixed with k
    ("{A₁, kc³, c, 1/c, k, 1}", [val, k2*c2**3, c2, 1/c2, k2, 1]),
    ("{A₁, c/(k+1), 1/((k+1)c), 1}", [val, c2/(k2+1), 1/((k2+1)*c2), 1]),
    
    # π-based without c  
    ("{A₁, π², π, 1/π, √2, √3, 1}", [val, pi**2, pi, 1/pi, sqrt(2), sqrt(3), 1]),
    ("{A₁, π²/3, π/√6, √6/π, 1}", [val, pi**2/3, pi/sqrt(6), sqrt(6)/pi, 1]),
    ("{A₁, π²/3, π/√3, √3/π, 1}", [val, pi**2/3, pi/sqrt(3), sqrt(3)/pi, 1]),
    ("{A₁, π²k/3, π√(2k/3), √(3/(2k))/π, 1}", [val, pi**2*k2/3, c2, 1/c2, 1]),
    
    # Zeta-related  
    ("{A₁, ζ(3)/π², c, 1/c, 1}", [val, zeta3/pi**2, c2, 1/c2, 1]),
    ("{A₁, ζ(5), c, 1/c, 1}", [val, zeta5, c2, 1/c2, 1]),
    
    # Exact k=1 value
    ("{A₁(2), A₁_exact(1), c₂, 1/c₂, 1}", [val, A1_exact_1, c2, 1/c2, 1]),
    ("{A₁(2), A₁_exact(1), c₂, c₁, 1/c₂, 1/c₁, 1}", [val, A1_exact_1, c2, c_k(1), 1/c2, 1/c_k(1), 1]),
]

for name, vec in extended_bases:
    try:
        rel = pslq(vec, maxcoeff=2000, maxsteps=10000)
        if rel and rel[0] != 0:
            rr = sum(r * v for r, v in zip(rel, vec))
            print(f"  {name}: FOUND {rel}  (res={abs(rr):.2e})")
        elif rel:
            print(f"  {name}: trivial {rel}")
        else:
            print(f"  {name}: no relation")
    except Exception as e:
        print(f"  {name}: error ({e})")

# =====================================================================
# PART 4: Check A₁(k) = -(π²k + g(k))/(24π√(6k)) pattern
# =====================================================================
print()
print("=" * 70)
print("PART 4: Test A₁(k) = -(π²·a(k) + b(k)) / (24π√(6k))")
print("=" * 70)

for k in [1, 2, 3]:
    denom = 24 * pi * sqrt(6 * mpf(k))
    numerator = -A1[k] * denom
    pi2_part = numerator / pi**2
    # numerator = a·π² + b → pi2_part = a + b/π²
    print(f"\n  k={k}: -A₁·24π√(6k) = {numerator:.15f}")
    print(f"         This / π² = {pi2_part:.15f}")
    print(f"         numerator - π² = {numerator - pi**2:.15f}")
    print(f"         numerator - kπ² = {numerator - k*pi**2:.15f}")
    
    # Try PSLQ: numerator = a·π² + b
    vec = [numerator, pi**2, 1]
    rel = pslq(vec, maxcoeff=1000)
    if rel:
        print(f"         PSLQ {{num, π², 1}}: {rel}")
    else:
        print(f"         PSLQ {{num, π², 1}}: no relation")
    
    # Try: numerator = a·π² + b·k + d
    vec2 = [numerator, pi**2, mpf(k), 1]
    if k > 1:  # for k=1, k is just a constant
        rel2 = pslq(vec2, maxcoeff=1000)
        if rel2 and rel2[0] != 0:
            print(f"         PSLQ {{num, π², k, 1}}: {rel2}")

# =====================================================================
# PART 5: Direct ratio between A₁ values
# =====================================================================
print()
print("=" * 70)
print("PART 5: Ratios and Differences")
print("=" * 70)

r21 = A1[2] / A1[1]
r31 = A1[3] / A1[1]
r32 = A1[3] / A1[2]
d21 = A1[2] - A1[1]
d31 = A1[3] - A1[1]
d32 = A1[3] - A1[2]

print(f"  A₁(2)/A₁(1) = {r21:.15f}")
print(f"  A₁(3)/A₁(1) = {r31:.15f}")
print(f"  A₁(3)/A₁(2) = {r32:.15f}")
print(f"  A₁(2)-A₁(1) = {d21:.15f}")
print(f"  A₁(3)-A₁(1) = {d31:.15f}")
print(f"  A₁(3)-A₁(2) = {d32:.15f}")

# PSLQ on ratios
ratio_bases = [
    ("{r₂₁, √2, √3, 1}", [r21, sqrt(2), sqrt(3), 1]),
    ("{r₃₁, √2, √3, 1}", [r31, sqrt(2), sqrt(3), 1]),
    ("{r₃₂, √2, √3, 1}", [r32, sqrt(2), sqrt(3), 1]),
    ("{r₂₁, c₂/c₁, 1}", [r21, c_k(2)/c_k(1), 1]),
    ("{r₃₁, c₃/c₁, 1}", [r31, c_k(3)/c_k(1), 1]),
    ("{d₂₁, c₂-c₁, 1/c₂-1/c₁, 1}", [d21, c_k(2)-c_k(1), 1/c_k(2)-1/c_k(1), 1]),
]

for name, vec in ratio_bases:
    try:
        rel = pslq(vec, maxcoeff=1000, maxsteps=5000)
        if rel:
            rr = sum(r * v for r, v in zip(rel, vec))
            print(f"  {name}: FOUND {rel}  (res={abs(rr):.2e})")
        else:
            print(f"  {name}: no relation")
    except Exception as e:
        print(f"  {name}: error ({e})")

# =====================================================================
# PART 6: Check Δ_k structure (excess beyond -kc/48 + κ/c)
# =====================================================================
print()
print("=" * 70)
print("PART 6: Structure of Δ_k = A₁(k) - (-kc/48 + κ/c)")
print("=" * 70)

print(f"  Δ₁ = {Delta[1]:+.15e} (should be ~0)")
print(f"  Δ₂ = {Delta[2]:+.15f}")
print(f"  Δ₃ = {Delta[3]:+.15f}")
print(f"  Δ₃/Δ₂ = {Delta[3]/Delta[2]:.15f}")

# Products with c
print(f"\n  Δ₂·c₂ = {Delta[2]*c_k(2):.15f}")
print(f"  Δ₃·c₃ = {Delta[3]*c_k(3):.15f}")
print(f"  Δ₂·c₂² = {Delta[2]*c_k(2)**2:.15f}")
print(f"  Δ₃·c₃² = {Delta[3]*c_k(3)**2:.15f}")

delta_bases = [
    ("{Δ₂·c₂, π², k, 1}", [Delta[2]*c_k(2), pi**2, mpf(2), 1]),
    ("{Δ₂·c₂², π², π, k, 1}", [Delta[2]*c_k(2)**2, pi**2, pi, mpf(2), 1]),
    ("{Δ₂·c₂², kπ², k, 1}", [Delta[2]*c_k(2)**2, 2*pi**2, mpf(4), 1]),
    ("{Δ₃·c₃, π², k, 1}", [Delta[3]*c_k(3), pi**2, mpf(3), 1]),
    ("{Δ₃·c₃², π², π, k, 1}", [Delta[3]*c_k(3)**2, pi**2, pi, mpf(3), 1]),
    # Check if Δ_k c_k = -(k-1)(something)
    ("{Δ₂·c₂/(k-1), π², 1}", [Delta[2]*c_k(2)/1, pi**2, 1]),  # k-1=1
    ("{Δ₃·c₃/(k-1), π², 1}", [Delta[3]*c_k(3)/2, pi**2, 1]),  # k-1=2
    # Δ per unit (k-1)
    ("{Δ₂/(k-1), c₂, 1/c₂, 1}", [Delta[2]/1, c_k(2), 1/c_k(2), 1]),
    ("{Δ₃/(k-1), c₃, 1/c₃, 1}", [Delta[3]/2, c_k(3), 1/c_k(3), 1]),
    # Check Δ₂/(k-1) vs Δ₃/(k-1)
    ("{Δ₂, Δ₃/2, c₂, c₃, 1}", [Delta[2], Delta[3]/2, c_k(2), c_k(3), 1]),
]

for name, vec in delta_bases:
    try:
        rel = pslq(vec, maxcoeff=2000, maxsteps=10000)
        if rel:
            rr = sum(r * v for r, v in zip(rel, vec))
            # Check nontriviality - first element must be nonzero
            if rel[0] != 0:
                print(f"  {name}: FOUND {rel}  (res={abs(rr):.2e})")
            else:
                print(f"  {name}: trivial {rel}")
        else:
            print(f"  {name}: no relation")
    except Exception as e:
        print(f"  {name}: error ({e})")

# =====================================================================
# PART 7: The "nuclear option" — massive basis for A₁(2)
# =====================================================================
print()
print("=" * 70)
print("PART 7: Massive basis for A₁(2)")
print("=" * 70)

c2 = c_k(2)
val = A1[2]

# Build a very large basis including many mathematical constants
nuclear = [
    val,       # 0: A₁(2)
    pi,        # 1
    1/pi,      # 2
    pi**2,     # 3
    1/pi**2,   # 4
    sqrt(2),   # 5
    sqrt(3),   # 6
    sqrt(6),   # 7
    log2,      # 8
    log(3),    # 9
    log2pi,    # 10
    euler,     # 11
    zeta3,     # 12
    1,         # 13
]

try:
    rel = pslq(nuclear, maxcoeff=500, maxsteps=50000)
    if rel and rel[0] != 0:
        labels = ['A₁(2)', 'π', '1/π', 'π²', '1/π²', '√2', '√3', '√6', 
                  'log2', 'log3', 'log2π', 'γ', 'ζ(3)', '1']
        terms = [f"{r}·{l}" for r, l in zip(rel, labels) if r != 0]
        print(f"  FOUND: {' + '.join(terms)} = 0")
        rr = sum(r * v for r, v in zip(rel, nuclear))
        print(f"  residual = {abs(rr):.2e}")
    else:
        print(f"  No relation with maxcoeff=500")
except Exception as e:
    print(f"  Error: {e}")

# Try smaller maxcoeff for speed
try:
    rel = pslq(nuclear, maxcoeff=100, maxsteps=20000)
    if rel and rel[0] != 0:
        labels = ['A₁(2)', 'π', '1/π', 'π²', '1/π²', '√2', '√3', '√6', 
                  'log2', 'log3', 'log2π', 'γ', 'ζ(3)', '1']
        terms = [f"{r}·{l}" for r, l in zip(rel, labels) if r != 0]
        print(f"  maxcoeff=100: FOUND: {' + '.join(terms)} = 0")
        rr = sum(r * v for r, v in zip(rel, nuclear))
        print(f"  residual = {abs(rr):.2e}")
    else:
        print(f"  maxcoeff=100: No relation")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 70)
print("PART 8: Summary — Precision Values for Paper")
print("=" * 70)

for k in [1, 2, 3]:
    c, kap = c_k(k), kappa_k(k)
    lval = L_k(k)
    alpha_struct = c * (c**2 + 6) / 48 + c * kap / 2 - A1[k] / 2
    print(f"\n  k={k} ({k}-colored partitions):")
    print(f"    c   = {c:.18f}")
    print(f"    κ   = {kap}")
    print(f"    L   = {lval:.18f}")
    print(f"    A₁  = {A1[k]:.15f}")
    print(f"    α   = {alpha_struct:.15f}")

print("\n  Quadratic fit: A₁(k) ≈ a + b·k + d·k²")
# Fit with 3 points
# A₁(1) = a + b + d
# A₁(2) = a + 2b + 4d
# A₁(3) = a + 3b + 9d
# Solve:
a1, a2, a3 = A1[1], A1[2], A1[3]
d_coeff = (a3 - 2*a2 + a1) / 2
b_coeff = a2 - a1 - 3*d_coeff
a_coeff = a1 - b_coeff - d_coeff
print(f"    a = {a_coeff:.15f}")
print(f"    b = {b_coeff:.15f}")  
print(f"    d = {d_coeff:.15f}")
print(f"    A₁(k) ≈ {a_coeff:.6f} + ({b_coeff:.6f})k + ({d_coeff:.6f})k²")

# Verify
for k in [1, 2, 3]:
    pred = a_coeff + b_coeff * k + d_coeff * k**2
    gap = A1[k] - pred
    print(f"    k={k}: predicted = {pred:.15f}, gap = {gap:+.2e}")

# Predict k=4,5
for k in [4, 5]:
    pred = a_coeff + b_coeff * k + d_coeff * k**2
    print(f"    k={k}: predicted = {pred:.6f}")

print("\n=== DONE ===")
