"""
_pcf_search_Tc_3d_ising.py  (v2 -- optimized)
=================================================
Targeted PCF search for the 3D Ising critical temperature.

  Tc = 4.51152785060...   Kc = 1/Tc = 0.22165455054...

Phase 1: 1000 evolutionary cycles at 100 dp, depth 200 (fast screen).
Phase 2: Top-5 near-miss guided re-run at 500 dp, depth 600.

Optimizations:
  - depth=200 for Phase 1 (was 600) -- 3x faster per eval
  - No seen_keys gate -- always re-evaluate mutated CFs
  - Entropy monitoring + fresh injection on collapse
  - Both Kc and Tc (+ transforms) in target library
  - 2D Ising Kc cross-reference
"""

from __future__ import annotations
import json, time, sys, random, math
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass

from mpmath import mp, mpf, pi, log, sqrt, zeta, nstr

sys.path.insert(0, ".")
import ramanujan_breakthrough_generator as rbg

# -- Target: 3D simple-cubic Ising critical temperature --------------------
# Ferrenberg-Xu-Landau (2018): Kc = 0.22165455(3)
TC_HP = "4.51152785060191536876679816744526"   # 32 sig digits
KC_HP = "0.22165455054281198362779272823516"


def build_ising_constants(prec: int) -> dict[str, mpf]:
    """Focused constant library: Tc/Kc transforms only."""
    mp.dps = prec + 30
    Tc = mpf(TC_HP)
    Kc = mpf(KC_HP)

    c: dict[str, mpf] = {}

    # Core
    c["Tc"]        = Tc
    c["Kc"]        = Kc

    # Powers / roots
    c["Tc^2"]      = Tc ** 2
    c["sqrt_Tc"]   = sqrt(Tc)
    c["Kc^2"]      = Kc ** 2
    c["sqrt_Kc"]   = sqrt(Kc)

    # Near-integer residuals
    c["Tc-4"]      = Tc - 4
    c["Tc-9/2"]    = Tc - mpf(9) / 2
    c["5-Tc"]      = 5 - Tc

    # With pi
    c["Tc/pi"]     = Tc / pi
    c["Tc*pi"]     = Tc * pi
    c["Kc*pi"]     = Kc * pi

    # With log
    c["log_Tc"]    = log(Tc)
    c["exp_Kc"]    = mp.exp(Kc)

    # With zeta(3)
    c["Tc/zeta3"]  = Tc / zeta(3)

    # 2D Ising connection: Kc_2D = ln(1+sqrt(2))/2
    kc2d = log(1 + sqrt(mpf(2))) / 2
    c["Kc/Kc2d"]   = Kc / kc2d
    c["Tc*Kc2d"]   = Tc * kc2d

    # Small rational multiples
    for p in range(1, 5):
        for q in range(1, 5):
            if p == q or math.gcd(p, q) != 1:
                continue
            c[f"{p}*Tc/{q}"] = mpf(p) * Tc / q
            c[f"{p}*Kc/{q}"] = mpf(p) * Kc / q

    return c


@dataclass
class NearMiss:
    a: list
    b: list
    cf_value: float
    closest: str
    digits: float
    cycle: int


def ratio_scan(val: mpf, constants: dict[str, mpf],
               tol_digits: int) -> tuple[str | None, float]:
    """Compare val (and -val) against every target. Return (name, digits)."""
    best_name: str | None = None
    best_digits = 0.0

    for name, cval in constants.items():
        if cval == 0:
            continue
        for cand, prefix in [(val, ""), (-val, "-")]:
            res = abs(cand - cval)
            if res == 0:
                return f"{prefix}{name}", float("inf")
            d = float(-mp.log10(res / abs(cval)))
            if d > best_digits:
                best_digits = d
                best_name = f"{prefix}{name}" if prefix else name

    return best_name, best_digits


def pop_entropy(population) -> float:
    """Fraction of unique CF keys in the population."""
    keys = {p.key() for p in population}
    return len(keys) / max(len(population), 1)


# =====================================================================
#  PHASE 1
# =====================================================================
def run_phase1(cycles=1000, prec=100, tol=50,
               pop_size=60, depth=200, seed=163):
    print("=" * 70)
    print("  PHASE 1 -- Fast screen")
    print(f"  cycles={cycles}  prec={prec}  depth={depth}  pop={pop_size}  tol={tol}")
    print("=" * 70, flush=True)

    mp.dps = prec + 20
    rng = random.Random(seed)
    consts = build_ising_constants(prec)
    print(f"  {len(consts)} target constants loaded", flush=True)

    # Initial population: 20 seeds + diverse randoms
    pop = list(rbg.seed_population())[:20]
    for da in [1, 2, 3]:
        for db in [1, 2]:
            for _ in range(3):
                pop.append(rbg.random_params(a_deg=da, b_deg=db,
                                             coeff_range=6, rng=rng))
    while len(pop) < pop_size:
        pop.append(rbg.random_fertile_params(rng))

    disc: list[dict] = []
    nms: list[NearMiss] = []
    temp = 2.0
    last_hit = 0
    n_eval = 0
    t0 = time.time()

    for c in range(1, cycles + 1):
        for p in pop:
            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            n_eval += 1
            if val is None or not rbg.is_reasonable(val):
                p.score = -999; continue
            if rbg.is_telescoping(p.a, p.b):
                p.score = -999; continue

            name, digs = ratio_scan(val, consts, tol)
            if name is None:
                p.score = 0.0; continue

            p.score = digs

            if digs >= tol:
                p.hit = name; last_hit = c
                d = {"cycle": c, "a": p.a[:], "b": p.b[:],
                     "match": name, "value": nstr(val, 40),
                     "digits": digs, "cplx": rbg.complexity_score(p.a, p.b)}
                disc.append(d)
                print(f"\n  *** MATCH c={c}: {name} | a={p.a} b={p.b} "
                      f"| {digs:.1f}d ***", flush=True)
            elif digs > 5:
                nms.append(NearMiss(p.a[:], p.b[:], float(val),
                                    name, digs, c))

        # Evolve
        pop.sort(key=lambda x: -x.score)
        temp = rbg.adapt_temperature(
            temp, [p.score for p in pop[:5]], c, last_hit)
        pop = rbg.evolve_population(pop, pop_size, temp, rng)

        # Entropy guard
        ent = pop_entropy(pop)
        if ent < 0.3 and c % 50 == 0:
            n_inj = pop_size // 4
            for i in range(n_inj):
                pop[-(i + 1)] = rbg.random_fertile_params(rng)
            print(f"  [ent={ent:.2f}] injected {n_inj} fresh", flush=True)

        if c % 25 == 0 or c == 1:
            el = time.time() - t0
            bst = max((nm.digits for nm in nms), default=0)
            n8 = sum(1 for nm in nms if nm.digits > 8)
            print(f"  c={c:5d}/{cycles} T={temp:.2f} disc={len(disc)} "
                  f"nm8={n8} best={bst:.1f}d ent={ent:.2f} "
                  f"{el:.0f}s", flush=True)

    el = time.time() - t0

    # Dedup near-misses
    best_nm: dict[tuple, NearMiss] = {}
    for nm in nms:
        k = (tuple(nm.a), tuple(nm.b))
        if k not in best_nm or nm.digits > best_nm[k].digits:
            best_nm[k] = nm
    nms_d = sorted(best_nm.values(), key=lambda x: -x.digits)

    print(f"\n  Phase 1: {el:.0f}s  {n_eval} evals  {len(disc)} disc  "
          f"{len(nms_d)} unique near-misses", flush=True)
    if nms_d:
        print(f"  Top near-miss: {nms_d[0].digits:.1f}d -> {nms_d[0].closest}")

    return {
        "phase": 1, "cycles": cycles, "prec": prec,
        "discoveries": disc,
        "near_misses": [
            {"a": nm.a, "b": nm.b, "cf_value": nm.cf_value,
             "closest": nm.closest, "digits": nm.digits, "cycle": nm.cycle}
            for nm in nms_d[:50]
        ],
        "elapsed": el, "evals": n_eval,
    }


# =====================================================================
#  NEAR-MISS ANALYSIS
# =====================================================================
def analyze_near_misses(res):
    top5 = res["near_misses"][:5]
    print("\n" + "=" * 70)
    print("  NEAR-MISS ANALYSIS")
    print("=" * 70)

    hyps = []
    da_cnt, db_cnt, tgt_cnt = defaultdict(int), defaultdict(int), defaultdict(int)
    mx_coeff = 0

    if not top5:
        print("  (none)")
        return {"hypotheses": [], "rec_da": [2, 3, 4], "rec_db": [1, 2, 3],
                "rec_range": 10, "focus": "Tc"}

    for i, nm in enumerate(top5):
        a, b, closest, digs = nm["a"], nm["b"], nm["closest"], nm["digits"]
        eda = len(a) - 1
        while eda > 0 and a[eda] == 0: eda -= 1
        edb = len(b) - 1
        while edb > 0 and b[edb] == 0: edb -= 1
        da_cnt[eda] += 1; db_cnt[edb] += 1
        mx_coeff = max(mx_coeff, max(abs(c) for c in a + b))
        tgt_cnt[closest] += 1

        print(f"\n  #{i+1}  {digs:.1f}d -> {closest}")
        print(f"        a={a} (deg {eda})   b={b} (deg {edb})")
        print(f"        val={nm['cf_value']}")

        strat = "perturbation" if digs > 15 else "degree_extension"
        hyps.append({"type": strat, "base_a": a, "base_b": b,
                      "target": closest, "digits": digs})

    bda = max(da_cnt, key=da_cnt.get) if da_cnt else 2
    bdb = max(db_cnt, key=db_cnt.get) if db_cnt else 1
    focus = max(tgt_cnt, key=tgt_cnt.get) if tgt_cnt else "Tc"

    print(f"\n  Summary: best da={bda} db={bdb} max_coeff={mx_coeff} focus={focus}")

    return {
        "hypotheses": hyps,
        "rec_da": sorted(set([bda, bda + 1, 2, 3])),
        "rec_db": sorted(set([bdb, bdb + 1, 1, 2])),
        "rec_range": min(mx_coeff + 5, 15),
        "focus": focus, "top5": top5,
    }


# =====================================================================
#  PHASE 2
# =====================================================================
def run_phase2(ana, prec=500, cycles=500, pop_size=80, depth=600, seed=314):
    focus = ana.get("focus", "Tc")
    print("\n" + "=" * 70)
    print(f"  PHASE 2 -- {prec}dp  depth={depth}  focus={focus}")
    print("=" * 70, flush=True)

    mp.dps = prec + 50
    rng = random.Random(seed)
    consts = build_ising_constants(prec)
    tol = prec // 2

    # Seed from hypotheses
    pop = []
    for h in ana.get("hypotheses", []):
        ba, bb = h["base_a"], h["base_b"]
        for _ in range(12):
            na = [c + rng.randint(-2, 2) for c in ba]
            nb = [c + rng.randint(-1, 1) for c in bb]
            nb[0] = max(1, nb[0])
            pop.append(rbg.PCFParams(a=na, b=nb))
        pop.append(rbg.PCFParams(a=ba + [rng.randint(-3, 3)], b=bb))
        pop.append(rbg.PCFParams(a=ba, b=bb + [rng.randint(-2, 2)]))

    rec_da = ana.get("rec_da", [2, 3])
    rec_db = ana.get("rec_db", [1, 2])
    rec_r  = ana.get("rec_range", 8)
    while len(pop) < pop_size:
        pop.append(rbg.random_params(a_deg=rng.choice(rec_da),
                                     b_deg=rng.choice(rec_db),
                                     coeff_range=rec_r, rng=rng))

    disc: list[dict] = []
    nms: list[NearMiss] = []
    temp = 2.5; last_hit = 0; n_eval = 0
    t0 = time.time()

    for c in range(1, cycles + 1):
        for p in pop:
            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            n_eval += 1
            if val is None or not rbg.is_reasonable(val):
                p.score = -999; continue
            if rbg.is_telescoping(p.a, p.b):
                p.score = -999; continue

            name, digs = ratio_scan(val, consts, tol)
            if name is None:
                p.score = 0.0; continue

            p.score = digs
            if digs >= tol:
                p.hit = name; last_hit = c
                disc.append({"cycle": c, "a": p.a[:], "b": p.b[:],
                             "match": name, "value": nstr(val, 80),
                             "digits": digs})
                print(f"\n  *** P2 MATCH c={c}: {name} | {digs:.0f}d ***",
                      flush=True)
            elif digs > 8:
                nms.append(NearMiss(p.a[:], p.b[:], float(val),
                                    name, digs, c))

        pop.sort(key=lambda x: -x.score)
        temp = rbg.adapt_temperature(
            temp, [p.score for p in pop[:5]], c, last_hit)
        pop = rbg.evolve_population(pop, pop_size, temp, rng)

        ent = pop_entropy(pop)
        if ent < 0.3 and c % 30 == 0:
            n_inj = pop_size // 4
            for i in range(n_inj):
                pop[-(i + 1)] = rbg.random_params(
                    a_deg=rng.choice(rec_da), b_deg=rng.choice(rec_db),
                    coeff_range=rec_r, rng=rng)

        if c % 25 == 0 or c == 1:
            el = time.time() - t0
            bst = max((nm.digits for nm in nms), default=0)
            print(f"  c={c:5d}/{cycles} disc={len(disc)} "
                  f"best={bst:.1f}d ent={ent:.2f} {el:.0f}s", flush=True)

    el = time.time() - t0
    best_nm: dict[tuple, NearMiss] = {}
    for nm in nms:
        k = (tuple(nm.a), tuple(nm.b))
        if k not in best_nm or nm.digits > best_nm[k].digits:
            best_nm[k] = nm
    nms_d = sorted(best_nm.values(), key=lambda x: -x.digits)

    print(f"\n  Phase 2: {el:.0f}s  {n_eval} evals  {len(disc)} disc  "
          f"{len(nms_d)} near-misses", flush=True)

    return {
        "phase": 2, "cycles": cycles, "prec": prec,
        "discoveries": disc,
        "near_misses": [
            {"a": nm.a, "b": nm.b, "cf_value": nm.cf_value,
             "closest": nm.closest, "digits": nm.digits, "cycle": nm.cycle}
            for nm in nms_d[:20]
        ],
        "elapsed": el, "evals": n_eval,
    }


# =====================================================================
#  MAIN
# =====================================================================
def main():
    print("\n" + "#" * 70)
    print("#  PCF Search for 3D Ising Tc / Kc")
    print(f"#  Tc = {TC_HP[:25]}...")
    print(f"#  Kc = {KC_HP[:25]}...")
    print("#" * 70, flush=True)

    p1 = run_phase1(cycles=1000, prec=100, tol=50,
                    pop_size=60, depth=200, seed=163)

    out = Path("results/pcf_search_Tc_3d.json")
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        json.dump({"phase1": p1}, f, indent=2, default=str)
    print(f"\n  Saved {out}")

    if p1["discoveries"]:
        print("\n  === Phase 1 SUCCESS ===")
        for d in p1["discoveries"]:
            print(f"    {d['match']}: a={d['a']} b={d['b']} ({d['digits']:.0f}d)")
    else:
        print("\n  No exact match in Phase 1. Analyzing near-misses...")
        ana = analyze_near_misses(p1)
        p2 = run_phase2(ana, prec=500, cycles=500,
                        pop_size=80, depth=600, seed=314)

        with open(out, "w") as f:
            json.dump({"phase1": p1, "analysis": ana, "phase2": p2},
                      f, indent=2, default=str)

        print("\n" + "=" * 70)
        print("  FINAL REPORT")
        print("=" * 70)
        all_d = p1["discoveries"] + p2["discoveries"]
        if all_d:
            for d in all_d:
                print(f"  {d['match']}: a={d['a']} b={d['b']} ({d['digits']:.0f}d)")
        else:
            print("\n  No exact PCF match for Tc = 4.511528...")
            print("  (3D Ising Tc has no known closed-form -- expected.)")
            all_nm = p1["near_misses"] + p2.get("near_misses", [])
            all_nm.sort(key=lambda x: -x["digits"])
            if all_nm:
                print(f"\n  Best near-misses (top 10):")
                for i, nm in enumerate(all_nm[:10]):
                    print(f"    #{i+1}: {nm['digits']:.1f}d -> {nm['closest']}")
                    print(f"         a={nm['a']}  b={nm['b']}")

    print("\n  Done.", flush=True)


if __name__ == "__main__":
    main()
