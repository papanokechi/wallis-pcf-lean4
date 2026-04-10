"""
zeta3_fast.py — Fast ζ(3) hunt with tighter budgets
"""
import sys, time, json, random, math
import mpmath
from mpmath import mp, mpf, log, nstr, pslq

mp.dps = 120
random.seed(42)

ZETA3 = mpmath.zeta(3)
CONSTANTS = {
    "zeta3": ZETA3, "1/zeta3": 1/ZETA3,
    "6*zeta3": 6*ZETA3, "zeta3/6": ZETA3/6,
    "2*zeta3": 2*ZETA3, "zeta3/2": ZETA3/2,
    "pi^2/6": mpmath.pi**2/6, "pi^4/72": mpmath.pi**4/72,
    "catalan": mpmath.catalan, "ln2": log(2),
}

def pcf_eval(alpha_fn, beta_fn, depth):
    p_prev, p_curr = mpf(1), beta_fn(0)
    q_prev, q_curr = mpf(0), mpf(1)
    for n in range(1, depth + 1):
        a_n, b_n = alpha_fn(n), beta_fn(n)
        p_new = b_n * p_curr + a_n * p_prev
        q_new = b_n * q_curr + a_n * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
    return p_curr / q_curr if q_curr != 0 else None

def match(val, min_dp=8):
    if val is None or abs(val) > 1000 or abs(val) < 1e-8:
        return None, 0
    best = (None, 0)
    for name, cval in CONSTANTS.items():
        for p in range(-6, 7):
            if p == 0: continue
            for q in range(1, 7):
                diff = abs(val - mpf(p)/q * cval)
                if diff > 0:
                    dp = -int(mpmath.log10(diff))
                    if dp > best[1]:
                        best = (f"{p}/{q}*{name}" if (p != 1 or q != 1) else name, dp)
    return best

results = []
seen = set()
t0 = time.time()

def hit(family, adesc, bdesc, val, name, dp):
    key = (name, adesc, bdesc)
    if key in seen: return
    seen.add(key)
    results.append({"family": family, "alpha": adesc, "beta": bdesc,
                     "match": name, "digits": dp, "value": nstr(val, 25)})
    with open("zeta3_hunt_results.json", "w", encoding="utf-8") as f:
        json.dump({"count": len(results), "results": results}, f, indent=2)

# ═══════════════════════════════════════════════════════════════════════
# FAMILY B: β(n) = n²(n+k)², α(n) cubic, α(0)=0  [HIGHEST PRIORITY]
# ═══════════════════════════════════════════════════════════════════════
print("=" * 72, flush=True)
print("  FAMILY B: β(n) = n²(n+k)²  (k=1..6)", flush=True)
print("=" * 72, flush=True)

for k in [1, 2, 4, 3, 5, 6]:
    t1 = time.time()
    kh = 0
    for a3 in range(-15, 16):
        if a3 == 0: continue
        for a2 in range(-10, 11):
            for a1 in range(-10, 11):
                try:
                    af = lambda n, a=a3, b=a2, c=a1: a*n**3+b*n**2+c*n
                    bf = lambda n, k=k: n*n*(n+k)**2
                    with mpmath.workdps(20):
                        v = pcf_eval(af, bf, 50)
                    if v is None or abs(v) > 100 or abs(v) < 0.01: continue
                    name, dp = match(v, 8)
                    if name and dp >= 8:
                        with mpmath.workdps(100):
                            v2 = pcf_eval(af, bf, 200)
                        name2, dp2 = match(v2, 12)
                        if name2 and dp2 >= 12:
                            desc = f"{a3}n³+{a2}n²+{a1}n"
                            hit("B", desc, f"n²(n+{k})²", v2, name2, dp2)
                            kh += 1
                            print(f"  + B k={k}: {name2:20s} {dp2:3d}dp  α={desc}", flush=True)
                except: continue
    print(f"  k={k}: {kh} hits ({time.time()-t1:.0f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# FAMILY C: CUBIC α + LINEAR β  (extend proven technique to ζ(3))
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  FAMILY C: CUBIC α + LINEAR β  (b=dn+e, d=2..8)", flush=True)
print("=" * 72, flush=True)

t1 = time.time()
ch = 0
for d in range(2, 9):
    for e in range(1, 7):
        for a3 in [-5, -3, -2, -1, 1, 2, 3, 5]:
            for a2 in range(-8, 9):
                for a1 in range(-8, 9):
                    try:
                        af = lambda n, a=a3, b=a2, c=a1: a*n**3+b*n**2+c*n
                        bf = lambda n, d=d, e=e: d*n+e
                        with mpmath.workdps(20):
                            v = pcf_eval(af, bf, 60)
                        if v is None or abs(v) > 50 or abs(v) < 0.01: continue
                        name, dp = match(v, 8)
                        if name and dp >= 8:
                            with mpmath.workdps(100):
                                v2 = pcf_eval(af, bf, 200)
                            name2, dp2 = match(v2, 12)
                            if name2 and dp2 >= 12:
                                desc = f"{a3}n³+{a2}n²+{a1}n"
                                hit("C", desc, f"{d}n+{e}", v2, name2, dp2)
                                ch += 1
                                print(f"  + C: {name2:20s} {dp2:3d}dp  α={desc}  β={d}n+{e}", flush=True)
                    except: continue
print(f"\n  Family C: {ch} hits ({time.time()-t1:.0f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════
# FAMILY A-FAST: RANDOM SAMPLING near Apéry (budget 5000)
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 72, flush=True)
print("  FAMILY A: APÉRY RANDOM NEIGHBOURHOOD (5000 samples)", flush=True)
print("=" * 72, flush=True)

t1 = time.time()
ah = 0
for _ in range(5000):
    a = random.randint(25, 45)
    b = random.randint(35, 65)
    c = random.randint(-20, 50)
    d = random.randint(-20, 20)
    if a == 34 and b == 51 and c == 27 and d == 5: continue
    try:
        af = lambda n, a=a, b=b, c=c, d=d: a*n**3+b*n**2+c*n+d
        bf = lambda n: n**4
        with mpmath.workdps(20):
            v = pcf_eval(af, bf, 50)
        if v is None or abs(v) > 100 or abs(v) < 0.001: continue
        name, dp = match(v, 8)
        if name and dp >= 8:
            with mpmath.workdps(100):
                v2 = pcf_eval(af, bf, 200)
            name2, dp2 = match(v2, 12)
            if name2 and dp2 >= 12:
                desc = f"{a}n³+{b}n²+{c}n+{d}"
                hit("A", desc, "n⁴", v2, name2, dp2)
                ah += 1
                print(f"  + A: {name2:20s} {dp2:3d}dp  α={desc}", flush=True)
    except: continue
print(f"  Family A: {ah} hits ({time.time()-t1:.0f}s)", flush=True)

# ═══════════════════════════════════════════════════════════════════════
total = time.time() - t0
print("\n" + "=" * 72, flush=True)
print(f"  ζ(3) HUNT: {len(results)} hits in {total:.0f}s", flush=True)
print("=" * 72, flush=True)
for r in sorted(results, key=lambda x: -x["digits"]):
    print(f"  [{r['family']}] {r['match']:25s} {r['digits']:3d}dp  α={r['alpha']}  β={r['beta']}", flush=True)
if not results:
    print("  No hits. ζ(3) PCFs require higher-degree or larger coefficients.", flush=True)
print(f"\n  Saved → zeta3_hunt_results.json", flush=True)
