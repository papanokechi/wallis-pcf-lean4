"""Quick benchmark to diagnose cycle timing."""
import sys, time, random
sys.path.insert(0, ".")
import ramanujan_breakthrough_generator as rbg
from mpmath import mp

mp.dps = 120
rng = random.Random(42)

# Test eval_pcf timing with high-degree
print("=== eval_pcf timing ===")
for da, db in [(2,1), (3,2), (4,2), (5,3)]:
    t0 = time.time()
    for _ in range(20):
        p = rbg.random_params(a_deg=da, b_deg=db, coeff_range=6, rng=rng)
        rbg.eval_pcf(p.a, p.b, depth=200)
    el = time.time() - t0
    print(f"  deg({da},{db}): 20 evals in {el:.2f}s ({el/20:.3f}s each)")

# Test evolve_population
print("\n=== evolve_population ===")
pop = []
for i in range(80):
    p = rbg.random_params(a_deg=4, b_deg=2, coeff_range=6, rng=rng)
    p.score = rng.random() * 5
    pop.append(p)
pop.sort(key=lambda x: -x.score)

t0 = time.time()
pop2 = rbg.evolve_population(pop, 80, 2.0, rng)
print(f"  evolve 80 -> {len(pop2)} in {time.time()-t0:.3f}s")

# Test is_telescoping timing
print("\n=== is_telescoping timing ===")
t0 = time.time()
for i in range(80):
    p = rbg.random_params(a_deg=4, b_deg=2, coeff_range=6, rng=rng)
    rbg.is_telescoping(p.a, p.b)
print(f"  80 checks: {time.time()-t0:.3f}s")

# Test is_reasonable
print("\n=== is_reasonable timing ===")
t0 = time.time()
for i in range(80):
    rbg.is_reasonable(rng.random() * 100 - 50)
print(f"  80 checks: {time.time()-t0:.3f}s")

# Full cycle simulation
print("\n=== Full cycle sim (1 cycle, pop=80, depth=200) ===")
from mpmath import mpf, log as mplog
consts = {"nu": mpf("0.6299709"), "eta": mpf("0.0362978")}

pop = []
for i in range(80):
    da = rng.choice([3, 4, 5])
    db = rng.choice([1, 2, 3])
    pop.append(rbg.random_params(a_deg=da, b_deg=db, coeff_range=6, rng=rng))

t0 = time.time()
for p in pop:
    val = rbg.eval_pcf(p.a, p.b, depth=200)
    if val is not None and rbg.is_reasonable(val):
        if not rbg.is_telescoping(p.a, p.b):
            best_d = -100
            for cname, cval in consts.items():
                res = abs(val - cval)
                if res > 0:
                    d = float(-mplog(res) / mplog(10))
                    if d > best_d:
                        best_d = d
            p.score = best_d
        else:
            p.score = -999
    else:
        p.score = -999

pop.sort(key=lambda x: -x.score)
pop2 = rbg.evolve_population(pop, 80, 2.0, rng)
print(f"  1 cycle: {time.time()-t0:.2f}s")
print(f"  top scores: {[round(p.score,2) for p in pop[:5]]}")
