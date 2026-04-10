#!/usr/bin/env python3
"""Phase 2 re-verification with d==0 bug fix."""
import mpmath, json

VER_DEPTH = 500
VER_DPS = 50
K_VALUES = [1, 2, 3, 4, 5, 6, 8, 10, 12]

mpmath.mp.dps = VER_DPS + 30
z3  = mpmath.zeta(3)
pi  = mpmath.pi
pi3 = pi**3
L3  = (mpmath.zeta(3, mpmath.mpf(1)/3) - mpmath.zeta(3, mpmath.mpf(2)/3)) / 27

vtgts = {
    'zeta3': z3, '1/zeta3': 1/z3,
    'zeta3/pi3': z3/pi3, 'pi3/zeta3': pi3/z3,
    'L(chi-3,3)': L3, 'L(chi-3,3)/pi3': L3/pi3,
}

# Load pre-filter hits
with open('search_b_zeta3_results.json') as f:
    data = json.load(f)
hits = data['prefilter_hits']

print(f'Verifying {len(hits)} pre-filter hits at depth {VER_DEPTH}, {VER_DPS} dps')
print('=' * 78)

# First, verify Apery explicitly
print('\n  Apery direct check:')
C, b3, b2, b1, b0 = 1, 34, 51, 27, 5
n = VER_DEPTH
val = mpmath.mpf(b3*n**3 + b2*n**2 + b1*n + b0)
for n in range(VER_DEPTH - 1, 0, -1):
    bn = b3*n**3 + b2*n**2 + b1*n + b0
    an1 = -C * (n+1)**6
    val = mpmath.mpf(bn) + mpmath.mpf(an1)/val
cf_apery = mpmath.mpf(b0) + mpmath.mpf(-C)/val
ref = 6/z3
diff_apery = abs(cf_apery - ref)
print(f'    CF     = {mpmath.nstr(cf_apery, 40)}')
print(f'    6/z(3) = {mpmath.nstr(ref, 40)}')
print(f'    diff   = {mpmath.nstr(diff_apery, 10)}')
print(f'    diff == 0? {diff_apery == 0}')
print()

verified = []
for h in hits:
    C = h['C']
    b3, b2, b1, b0 = h['b3'], h['b2'], h['b1'], h['b0']
    
    n = VER_DEPTH
    val = mpmath.mpf(b3*n**3 + b2*n**2 + b1*n + b0)
    for n in range(VER_DEPTH - 1, 0, -1):
        bn = b3*n**3 + b2*n**2 + b1*n + b0
        an1 = -C * (n+1)**6
        val = mpmath.mpf(bn) + mpmath.mpf(an1)/val
    cf_hp = mpmath.mpf(b0) + mpmath.mpf(-C)/val
    
    best_name, best_digs = None, 0
    for tn, tv in vtgts.items():
        for k in K_VALUES:
            d = abs(cf_hp - k*tv)
            if d == 0:
                dg = VER_DPS + 20
                lab = f'{k}*{tn}' if k > 1 else tn
                if dg > best_digs:
                    best_digs, best_name = dg, lab
            elif d < mpmath.mpf(10)**(-15):
                dg = int(-mpmath.log10(d))
                lab = f'{k}*{tn}' if k > 1 else tn
                if dg > best_digs:
                    best_digs, best_name = dg, lab
    
    is_a = (C == 1 and b3 == 34 and b2 == 51 and b1 == 27 and b0 == 5)
    tag = 'APERY  ' if is_a else 'NEW!!!'
    fac = ' (2n+1)' if h.get('has_2n1') else ''
    
    if best_name and best_digs >= 25:
        verified.append(h)
        print(f'  VERIFIED [{tag}] C={C} beta=({b3},{b2},{b1},{b0}){fac}')
        print(f'    -> {best_name}  ({best_digs} digits)')
        print(f'    CF = {mpmath.nstr(cf_hp, 25)}')
    else:
        status = f'{best_digs}d {best_name}' if best_name else 'no match'
        if is_a:
            print(f'  *** APERY REJECTED *** ({status})')
            print(f'      CF = {mpmath.nstr(cf_hp, 30)}')
            print(f'      target 6/z3 = {mpmath.nstr(6/z3, 30)}')
            print(f'      diff = {mpmath.nstr(abs(cf_hp - 6/z3), 10)}')
        else:
            print(f'  rejected  C={C} beta=({b3},{b2},{b1},{b0})  ({status})')

print()
print('=' * 78)
print(f'Verified: {len(verified)} / {len(hits)} pre-filter hits')
if len(verified) == 1 and any(v['C'] == 1 and v['b3'] == 34 for v in verified):
    print('Apery is the UNIQUE zeta(3) PCF in this search space.')
elif len(verified) == 0:
    print('ERROR: Apery should have been found')
else:
    new = [v for v in verified if not (v['C'] == 1 and v['b3'] == 34 and v['b2'] == 51)]
    if new:
        print(f'{len(new)} NEW zeta(3) PCFs DISCOVERED!')
    else:
        print('Apery is the UNIQUE zeta(3) PCF in this search space.')
