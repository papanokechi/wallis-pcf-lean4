#!/usr/bin/env python3
"""
Phase 21: Wild Target Scan — Lommel & Meijer G Constants
=========================================================
Searches for V_quad = 1.19737399... in the function-space basis:
  1. 1F2 ratios at motivated z-values
  2. Lommel function ratios s_{mu,nu}(z)
  3. 0F2 ratios (from quadratic recurrences)
  4. Stokes Constant Hunter for the divergent Lemma 1 GCF

Uses parameter motivation from disc(3n^2+n+1) = -11:
  roots = (-1 ± i√11)/6 → order params near 1/6, 1/3, 11/6
"""
import mpmath as mp
import time

mp.mp.dps = 120

# ─── Target computation ────────────────────────────────────────────
def eval_quad_gcf(depth=300):
    """Backward recurrence for GCF(1, 3n^2+n+1)."""
    v = mp.mpf(0)
    for n in range(depth, 0, -1):
        v = 1 / (3*n**2 + n + 1 + v)
    return 1 + v

TARGET = eval_quad_gcf(300)
print("="*72)
print("  PHASE 21: WILD TARGET SCAN")
print("="*72)
print(f"\nV_quad = {mp.nstr(TARGET, 80)}\n")

# ─── SCAN 1: Focused 1F2 ratios ───────────────────────────────────
print("─── SCAN 1: 1F2 ratio search (motivated params) ───")
t0 = time.time()

# Motivated params: sixths (from disc=-11), thirds, halves, integers
sixths = [mp.mpf(j)/6 for j in range(1, 25)]
thirds = [mp.mpf(j)/3 for j in range(1, 13)]
halves = [mp.mpf(j)/2 for j in range(1, 9)]
ints_  = [mp.mpf(j) for j in range(1, 6)]
params = sorted(set(sixths + thirds + halves + ints_))

# z-values motivated by the recurrence structure
z_vals = {
    '1/3': mp.mpf(1)/3,
    '1/6': mp.mpf(1)/6,
    '2/3': mp.mpf(2)/3,
    '1':   mp.mpf(1),
    '1/9': mp.mpf(1)/9,
    '1/12': mp.mpf(1)/12,
    '11/36': mp.mpf(11)/36,  # disc/6^2
    '-1/3': mp.mpf(-1)/3,
    '-1': mp.mpf(-1),
}

hits_1f2 = []
tested = 0

for z_name, z in z_vals.items():
    # Precompute 1F2 cache for this z
    cache = {}
    for a in params:
        for b1 in params:
            for b2 in params:
                if b1 <= 0 or b2 <= 0:
                    continue
                if b1 > 4 or b2 > 4 or a > 4:
                    continue  # keep parameter space manageable
                key = (float(a), float(b1), float(b2))
                if key in cache:
                    continue
                try:
                    val = mp.hyper([a], [b1, b2], z)
                    if abs(val) > 1e-12 and mp.isfinite(val):
                        cache[key] = val
                except:
                    pass

    keys = list(cache.keys())
    vals = list(cache.values())
    n = len(keys)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            tested += 1
            ratio = vals[i] / vals[j]
            # Check k*ratio + offset for small integers
            for kn in range(1, 4):
                for kd in range(1, 4):
                    scaled = ratio * mp.mpf(kn) / mp.mpf(kd)
                    for offset in [0, 1, -1]:
                        candidate = scaled + offset
                        diff = abs(candidate - TARGET)
                        if 0 < diff < mp.mpf('1e-30'):
                            dig = int(-mp.log10(diff))
                            if dig >= 30:
                                a1, b1_, b2_ = keys[i]
                                a2, b3_, b4_ = keys[j]
                                pref = "" if (kn == 1 and kd == 1) else f"{kn}/{kd}*"
                                off = "" if offset == 0 else f" + {offset}"
                                expr = f"{pref}1F2({a1};{b1_},{b2_};{z_name}) / 1F2({a2};{b3_},{b4_};{z_name}){off}"
                                hits_1f2.append((dig, expr))
                                print(f"  HIT [{dig}d] z={z_name}: {expr}")

elapsed = time.time() - t0
print(f"  Tested {tested:,} pairs in {elapsed:.1f}s")
if not hits_1f2:
    print("  No 1F2 ratio hits — target may require pFq with p≥2 or non-rational z.")
print()


# ─── SCAN 2: Lommel function ratios ───────────────────────────────
print("─── SCAN 2: Lommel function s_{μ,ν}(z) ratios ───")
t0 = time.time()

def lommel_s(mu, nu, z, terms=80):
    """Lommel function s_{mu,nu}(z) via series representation."""
    # s_{mu,nu}(z) = z^{mu+1} sum_{k=0}^inf (-1)^k z^{2k} / prod_{j=0}^k ((mu+2j+1)^2 - nu^2)
    total = mp.mpf(0)
    z2 = z**2
    term = mp.mpf(1)
    for k in range(terms):
        denom = (mu + 2*k + 1)**2 - nu**2
        if abs(denom) < 1e-50:
            break
        if k == 0:
            term = 1 / denom
        else:
            term *= -z2 / denom
        total += term
    return z**(mu + 1) * total

# Motivated μ,ν from roots of 3n^2+n+1: n = (-1±i√11)/6
# Real part = -1/6, |imaginary| = √11/6
mu_vals = [mp.mpf(j)/6 for j in range(-3, 19)]  # -1/2 to 3
nu_vals = [mp.mpf(j)/6 for j in range(1, 19)]    # 1/6 to 3
z_lommel = [mp.mpf(1)/3, mp.mpf(2)/3, mp.mpf(1), mp.mpf(2), mp.mpf(1)/6]

hits_lommel = []
tested = 0

for z in z_lommel:
    z_name = mp.nstr(z, 4)
    cache_l = {}
    for mu in mu_vals:
        for nu in nu_vals:
            key = (float(mu), float(nu))
            try:
                val = lommel_s(mu, nu, z)
                if abs(val) > 1e-15 and mp.isfinite(val):
                    cache_l[key] = val
            except:
                pass

    keys_l = list(cache_l.keys())
    vals_l = list(cache_l.values())
    n = len(keys_l)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            tested += 1
            ratio = vals_l[i] / vals_l[j]
            for kn in range(1, 4):
                for kd in range(1, 4):
                    scaled = ratio * mp.mpf(kn) / mp.mpf(kd)
                    for offset in [0, 1, -1]:
                        candidate = scaled + offset
                        diff = abs(candidate - TARGET)
                        if 0 < diff < mp.mpf('1e-30'):
                            dig = int(-mp.log10(diff))
                            if dig >= 30:
                                m1, n1 = keys_l[i]
                                m2, n2 = keys_l[j]
                                pref = "" if kn == 1 and kd == 1 else f"{kn}/{kd}*"
                                off = "" if offset == 0 else f" + {offset}"
                                expr = f"{pref}s({m1},{n1};{z_name}) / s({m2},{n2};{z_name}){off}"
                                hits_lommel.append((dig, expr))
                                print(f"  HIT [{dig}d]: {expr}")

elapsed = time.time() - t0
print(f"  Tested {tested:,} Lommel pairs in {elapsed:.1f}s")
if not hits_lommel:
    print("  No Lommel hits — target may require Meijer G or different function family.")
print()


# ─── SCAN 3: 0F2 ratios ──────────────────────────────────────────
print("─── SCAN 3: 0F2(; b1, b2; z) ratios ───")
t0 = time.time()

hits_0f2 = []
tested = 0

for z_name, z in z_vals.items():
    cache_02 = {}
    for b1 in params:
        for b2 in params:
            if b1 <= 0 or b2 <= 0 or b1 > 4 or b2 > 4:
                continue
            key = (float(b1), float(b2))
            if key in cache_02:
                continue
            try:
                val = mp.hyper([], [b1, b2], z)
                if abs(val) > 1e-12 and mp.isfinite(val):
                    cache_02[key] = val
            except:
                pass

    keys_02 = list(cache_02.keys())
    vals_02 = list(cache_02.values())
    n = len(keys_02)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            tested += 1
            ratio = vals_02[i] / vals_02[j]
            for kn in range(1, 4):
                for kd in range(1, 4):
                    scaled = ratio * mp.mpf(kn) / mp.mpf(kd)
                    for offset in [0, 1, -1]:
                        candidate = scaled + offset
                        diff = abs(candidate - TARGET)
                        if 0 < diff < mp.mpf('1e-30'):
                            dig = int(-mp.log10(diff))
                            if dig >= 30:
                                b1_, b2_ = keys_02[i]
                                b3_, b4_ = keys_02[j]
                                pref = "" if kn == 1 and kd == 1 else f"{kn}/{kd}*"
                                off = "" if offset == 0 else f" + {offset}"
                                expr = f"{pref}0F2(;{b1_},{b2_};{z_name}) / 0F2(;{b3_},{b4_};{z_name}){off}"
                                hits_0f2.append((dig, expr))
                                print(f"  HIT [{dig}d] z={z_name}: {expr}")

elapsed = time.time() - t0
print(f"  Tested {tested:,} 0F2 pairs in {elapsed:.1f}s")
if not hits_0f2:
    print("  No 0F2 ratio hits.")
print()


# ─── SCAN 4: Multi-basis PSLQ ────────────────────────────────────
print("─── SCAN 4: Multi-basis PSLQ (extended transcendental basis) ───")

# Build basis vector with special function values
V = TARGET
basis_labels = []
basis_vals = []

# Standard transcendentals
for label, val in [
    ("1", mp.mpf(1)),
    ("V", V),
    ("pi", mp.pi),
    ("pi^2", mp.pi**2),
    ("e", mp.e),
    ("ln(2)", mp.log(2)),
    ("ln(3)", mp.log(3)),
    ("gamma", mp.euler),
    ("G", mp.catalan),  # Catalan's constant
    ("sqrt(3)", mp.sqrt(3)),
    ("sqrt(11)", mp.sqrt(11)),
    ("Gamma(1/3)", mp.gamma(mp.mpf(1)/3)),
    ("Gamma(1/6)", mp.gamma(mp.mpf(1)/6)),
    ("Gamma(2/3)", mp.gamma(mp.mpf(2)/3)),
    ("zeta(3)", mp.zeta(3)),
]:
    basis_labels.append(label)
    basis_vals.append(val)

# Try PSLQ with subsets
mp.mp.dps = 100

print(f"  Basis: {basis_labels}")
try:
    result = mp.pslq(basis_vals, maxcoeff=1000, maxsteps=5000)
    if result:
        terms = []
        for i, c in enumerate(result):
            if c != 0:
                terms.append(f"{c}*{basis_labels[i]}")
        print(f"  PSLQ HIT: {' + '.join(terms)} = 0")
    else:
        print("  No PSLQ relation found (maxcoeff=1000)")
except Exception as e:
    print(f"  PSLQ error: {e}")
print()

# Also try V^2 and V^3 in basis
print("  Extended PSLQ (with V^2, V^3, V*pi, V*e):")
ext_labels = ["1", "V", "V^2", "V^3", "pi", "V*pi", "e", "V*e", "sqrt(11)", "V*sqrt(11)"]
ext_vals = [mp.mpf(1), V, V**2, V**3, mp.pi, V*mp.pi, mp.e, V*mp.e, mp.sqrt(11), V*mp.sqrt(11)]
try:
    result = mp.pslq(ext_vals, maxcoeff=10000, maxsteps=5000)
    if result:
        terms = []
        for i, c in enumerate(result):
            if c != 0:
                terms.append(f"{c}*{ext_labels[i]}")
        print(f"  PSLQ HIT: {' + '.join(terms)} = 0")
    else:
        print("  No algebraic/transcendental relation found (maxcoeff=10000)")
except Exception as e:
    print(f"  PSLQ error: {e}")

mp.mp.dps = 120
print()


# ─── SUMMARY ─────────────────────────────────────────────────────
print("="*72)
print("  SCAN SUMMARY")
print("="*72)
all_hits = hits_1f2 + hits_lommel + hits_0f2
if all_hits:
    print(f"\n  Total hits: {len(all_hits)}")
    for dig, expr in sorted(all_hits, reverse=True):
        print(f"    [{dig}d] {expr}")
else:
    print(f"\n  V_quad = {mp.nstr(TARGET, 60)}")
    print("  Status: NO CLOSED FORM FOUND in scanned function space")
    print("  Classification: POTENTIALLY NEW TRANSCENDENTAL")
    print("  Next steps:")
    print("    - Expand to 2F3, 3F2 families")
    print("    - Try Meijer G-function G^{m,n}_{p,q} at algebraic z")
    print("    - Query LMFDB for L-function values matching V")
    print("    - Submit 120-digit value to ISC (Inverse Symbolic Calculator)")
print()
