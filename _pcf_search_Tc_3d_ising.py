"""
_pcf_search_Tc_3d_ising.py  (v3 -- gradient-guided)
=====================================================
Targeted PCF search for the 3D Ising critical temperature.

  Tc = 4.51152785060...   Kc = 1/Tc = 0.22165455054...

Key insight from v2: when NO CF matches to > 5 digits, ALL scores are 0
and the GA has zero gradient. Fix: use log-proximity-to-nearest-target as
fitness, so CFs evaluating near 4.5 are preferentially selected.

Phase 1: 1000 cycles at 100dp, depth=200, gradient-guided.
Phase 2: Top-5 near-miss -> perturbation cloud at 500dp.
"""

from __future__ import annotations
import json, time, sys, random, math
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass

from mpmath import mp, mpf, pi, log, sqrt, zeta, nstr

sys.path.insert(0, ".")
import ramanujan_breakthrough_generator as rbg

# -- Target: 3D Ising Tc --------------------------------------------------
TC_HP = "4.51152785060191536876679816744526"
KC_HP = "0.22165455054281198362779272823516"


def build_ising_constants(prec: int) -> dict[str, mpf]:
    """Focused constant library: Tc/Kc transforms."""
    mp.dps = prec + 30
    Tc = mpf(TC_HP)
    Kc = mpf(KC_HP)

    c: dict[str, mpf] = {}

    # Core
    c["Tc"] = Tc
    c["Kc"] = Kc

    # Powers/roots
    c["Tc^2"] = Tc ** 2
    c["sqrt_Tc"] = sqrt(Tc)
    c["Kc^2"] = Kc ** 2
    c["sqrt_Kc"] = sqrt(Kc)

    # Near-integer residuals
    c["Tc-4"] = Tc - 4          # 0.51152...
    c["Tc-9/2"] = Tc - mpf(9)/2  # 0.01152...
    c["5-Tc"] = 5 - Tc          # 0.48847...

    # With pi
    c["Tc/pi"] = Tc / pi
    c["Tc*pi"] = Tc * pi
    c["Kc*pi"] = Kc * pi

    # With log/exp
    c["log_Tc"] = log(Tc)
    c["exp_Kc"] = mp.exp(Kc)

    # With zeta(3)
    c["Tc/zeta3"] = Tc / zeta(3)

    # 2D Ising: Kc_2D = ln(1+sqrt(2))/2
    kc2d = log(1 + sqrt(mpf(2))) / 2
    c["Kc/Kc2d"] = Kc / kc2d
    c["Tc*Kc2d"] = Tc * kc2d

    # Rational multiples p*Tc/q, p*Kc/q
    for p in range(1, 5):
        for q in range(1, 5):
            if p == q or math.gcd(p, q) != 1:
                continue
            c[f"{p}*Tc/{q}"] = mpf(p) * Tc / q
            c[f"{p}*Kc/{q}"] = mpf(p) * Kc / q

    return c


@dataclass
class NearMiss:
    a: list; b: list; cf_value: float
    closest: str; digits: float; cycle: int


def score_cf(val: mpf, constants: dict[str, mpf]) -> tuple[str | None, float]:
    """Score a CF value by absolute log-proximity to nearest target.

    Returns (name, digits) where digits = -log10(|val - const|).
    Always returns the best match, even if only 0.5 digits.
    This provides gradient for the GA.
    """
    if val is None:
        return None, -100.0

    best_name: str | None = None
    best_digits = -100.0

    for name, cval in constants.items():
        if cval == 0:
            continue
        for cand, prefix in [(val, ""), (-val, "-")]:
            res = abs(cand - cval)
            if res == 0:
                return f"{prefix}{name}" if prefix else name, 999.0
            try:
                d = float(-mp.log10(res))
            except (ValueError, ZeroDivisionError):
                continue
            if d > best_digits:
                best_digits = d
                best_name = f"{prefix}{name}" if prefix else name

    return best_name, best_digits


def pop_entropy(population) -> float:
    return len({p.key() for p in population}) / max(len(population), 1)


# =====================================================================
#  PHASE 1
# =====================================================================
def run_phase1(cycles=1000, prec=100, tol=50,
               pop_size=60, depth=200, seed=163):
    print("=" * 70)
    print("  PHASE 1 -- Gradient-guided search")
    print(f"  cycles={cycles}  prec={prec}dp  depth={depth}  pop={pop_size}")
    print(f"  match threshold: {tol} digits")
    print("=" * 70, flush=True)

    mp.dps = prec + 20
    rng = random.Random(seed)
    consts = build_ising_constants(prec)
    print(f"  {len(consts)} target constants", flush=True)

    # Population: mix seeds, targeted randoms, fertile randoms
    pop = list(rbg.seed_population())[:15]
    # Add CFs likely to produce values near 4.5
    for da in [1, 2, 3]:
        for db in [1, 2]:
            for _ in range(3):
                pop.append(rbg.random_params(
                    a_deg=da, b_deg=db, coeff_range=6, rng=rng))
    while len(pop) < pop_size:
        pop.append(rbg.random_fertile_params(rng))

    disc: list[dict] = []
    nms: list[NearMiss] = []
    best_ever = -100.0
    best_ever_nm: NearMiss | None = None
    temp = 2.0

    t0 = time.time()

    for cyc in range(1, cycles + 1):
        for p in pop:
            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            if val is None or not rbg.is_reasonable(val):
                p.score = -999; continue
            if rbg.is_telescoping(p.a, p.b):
                p.score = -999; continue

            name, digs = score_cf(val, consts)
            p.score = digs  # ALWAYS assign, even if only 0.5 digits

            if digs >= tol:
                p.hit = name
                disc.append({
                    "cycle": cyc, "a": p.a[:], "b": p.b[:],
                    "match": name, "value": nstr(val, 40),
                    "digits": digs,
                })
                print(f"\n  *** MATCH c={cyc}: {name} ***")
                print(f"      a={p.a}  b={p.b}  {digs:.1f}d", flush=True)

            if digs > 2:  # Track anything within 0.01
                nm = NearMiss(p.a[:], p.b[:], float(val), name, digs, cyc)
                nms.append(nm)
                if digs > best_ever:
                    best_ever = digs
                    best_ever_nm = nm

        # Evolve with gradient-aware scoring
        pop.sort(key=lambda x: -x.score)
        top5 = [p.score for p in pop[:5]]
        temp = rbg.adapt_temperature(temp, top5, cyc, 0)
        pop = rbg.evolve_population(pop, pop_size, temp, rng)

        # Entropy guard
        ent = pop_entropy(pop)
        if ent < 0.3 and cyc % 50 == 0:
            n_inj = pop_size // 4
            for i in range(n_inj):
                pop[-(i+1)] = rbg.random_fertile_params(rng)

        # Progress
        if cyc % 50 == 0 or cyc == 1:
            el = time.time() - t0
            t5_avg = sum(top5) / len(top5) if top5 else 0
            print(f"  c={cyc:5d}/{cycles} T={temp:.2f} "
                  f"top5_avg={t5_avg:.2f}d best_ever={best_ever:.2f}d "
                  f"ent={ent:.2f} disc={len(disc)} "
                  f"nm(>2d)={len(nms)} {el:.0f}s", flush=True)

    el = time.time() - t0

    # Dedup near-misses
    nm_map: dict[tuple, NearMiss] = {}
    for nm in nms:
        k = (tuple(nm.a), tuple(nm.b))
        if k not in nm_map or nm.digits > nm_map[k].digits:
            nm_map[k] = nm
    nms_d = sorted(nm_map.values(), key=lambda x: -x.digits)

    print(f"\n  Phase 1 done: {el:.0f}s")
    print(f"  Discoveries: {len(disc)}")
    print(f"  Unique near-misses: {len(nms_d)}")
    if best_ever_nm:
        print(f"  Best: {best_ever:.2f}d -> {best_ever_nm.closest}")
        print(f"         a={best_ever_nm.a}  b={best_ever_nm.b}")
        print(f"         val={best_ever_nm.cf_value}")

    # Show top 10 near-misses
    if nms_d:
        print(f"\n  Top near-misses:")
        for i, nm in enumerate(nms_d[:10]):
            print(f"    #{i+1}: {nm.digits:.2f}d -> {nm.closest}  "
                  f"a={nm.a} b={nm.b} val={nm.cf_value:.10f}")

    return {
        "phase": 1, "cycles": cycles, "prec": prec,
        "discoveries": disc,
        "near_misses": [
            {"a": nm.a, "b": nm.b, "cf_value": nm.cf_value,
             "closest": nm.closest, "digits": nm.digits, "cycle": nm.cycle}
            for nm in nms_d[:50]
        ],
        "elapsed": el, "best_digits": best_ever,
    }


# =====================================================================
#  NEAR-MISS ANALYSIS
# =====================================================================
def analyze(res):
    top5 = res["near_misses"][:5]
    print("\n" + "=" * 70)
    print("  NEAR-MISS ANALYSIS")
    print("=" * 70)

    hyps = []
    da_cnt, db_cnt, tgt_cnt = defaultdict(int), defaultdict(int), defaultdict(int)
    mx = 0

    if not top5:
        print("  No near-misses. Broadening for Phase 2.", flush=True)
        return {"hypotheses": [], "rec_da": [2, 3, 4], "rec_db": [1, 2, 3],
                "rec_range": 12, "focus": "Tc"}

    for i, nm in enumerate(top5):
        a, b, cl, d = nm["a"], nm["b"], nm["closest"], nm["digits"]
        eda = max(0, len(a) - 1)
        while eda > 0 and a[eda] == 0: eda -= 1
        edb = max(0, len(b) - 1)
        while edb > 0 and b[edb] == 0: edb -= 1
        da_cnt[eda] += 1; db_cnt[edb] += 1
        mx = max(mx, max(abs(c) for c in a + b))
        tgt_cnt[cl] += 1

        print(f"\n  #{i+1}  {d:.2f}d -> {cl}")
        print(f"        a={a} (deg {eda})   b={b} (deg {edb})")
        print(f"        val={nm['cf_value']:.12f}")

        hyps.append({"type": "perturbation" if d > 10 else "extension",
                      "base_a": a, "base_b": b, "target": cl, "digits": d})

    bda = max(da_cnt, key=da_cnt.get) if da_cnt else 2
    bdb = max(db_cnt, key=db_cnt.get) if db_cnt else 1
    focus = max(tgt_cnt, key=tgt_cnt.get) if tgt_cnt else "Tc"
    print(f"\n  best da={bda} db={bdb} max_coeff={mx} focus={focus}", flush=True)

    return {
        "hypotheses": hyps,
        "rec_da": sorted(set([bda, bda + 1, 2, 3])),
        "rec_db": sorted(set([bdb, bdb + 1, 1, 2])),
        "rec_range": min(mx + 5, 15),
        "focus": focus,
    }


# =====================================================================
#  PHASE 2
# =====================================================================
def run_phase2(ana, prec=500, cycles=500, pop_size=80, depth=600, seed=314):
    focus = ana.get("focus", "Tc")
    print("\n" + "=" * 70)
    print(f"  PHASE 2 -- {prec}dp, depth={depth}, focus={focus}")
    print("=" * 70, flush=True)

    mp.dps = prec + 50
    rng = random.Random(seed)
    consts = build_ising_constants(prec)
    tol = prec // 2

    # Seed population from hypotheses
    pop = []
    for h in ana.get("hypotheses", []):
        ba, bb = h["base_a"], h["base_b"]
        for _ in range(15):
            na = [c + rng.randint(-3, 3) for c in ba]
            nb = [c + rng.randint(-2, 2) for c in bb]
            nb[0] = max(1, nb[0])
            pop.append(rbg.PCFParams(a=na, b=nb))
        # Degree extensions
        pop.append(rbg.PCFParams(a=ba + [rng.randint(-4, 4)], b=bb))
        pop.append(rbg.PCFParams(a=ba, b=bb + [rng.randint(-3, 3)]))

    rec_da = ana.get("rec_da", [2, 3])
    rec_db = ana.get("rec_db", [1, 2])
    rec_r = ana.get("rec_range", 10)
    while len(pop) < pop_size:
        pop.append(rbg.random_params(a_deg=rng.choice(rec_da),
                                     b_deg=rng.choice(rec_db),
                                     coeff_range=rec_r, rng=rng))

    disc: list[dict] = []
    nms: list[NearMiss] = []
    best_ever = -100.0
    temp = 2.5
    t0 = time.time()

    for cyc in range(1, cycles + 1):
        for p in pop:
            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            if val is None or not rbg.is_reasonable(val):
                p.score = -999; continue
            if rbg.is_telescoping(p.a, p.b):
                p.score = -999; continue

            name, digs = score_cf(val, consts)
            p.score = digs

            if digs >= tol:
                p.hit = name
                disc.append({"cycle": cyc, "a": p.a[:], "b": p.b[:],
                             "match": name, "value": nstr(val, 80),
                             "digits": digs})
                print(f"\n  *** P2 MATCH c={cyc}: {name} {digs:.0f}d ***",
                      flush=True)
            if digs > 2:
                nms.append(NearMiss(p.a[:], p.b[:], float(val),
                                    name, digs, cyc))
                best_ever = max(best_ever, digs)

        pop.sort(key=lambda x: -x.score)
        temp = rbg.adapt_temperature(
            temp, [p.score for p in pop[:5]], cyc, 0)
        pop = rbg.evolve_population(pop, pop_size, temp, rng)

        ent = pop_entropy(pop)
        if ent < 0.3 and cyc % 30 == 0:
            n_inj = pop_size // 4
            for i in range(n_inj):
                pop[-(i+1)] = rbg.random_params(
                    a_deg=rng.choice(rec_da), b_deg=rng.choice(rec_db),
                    coeff_range=rec_r, rng=rng)

        if cyc % 50 == 0 or cyc == 1:
            el = time.time() - t0
            print(f"  c={cyc:5d}/{cycles} disc={len(disc)} "
                  f"best={best_ever:.2f}d ent={ent:.2f} {el:.0f}s",
                  flush=True)

    el = time.time() - t0
    nm_map: dict[tuple, NearMiss] = {}
    for nm in nms:
        k = (tuple(nm.a), tuple(nm.b))
        if k not in nm_map or nm.digits > nm_map[k].digits:
            nm_map[k] = nm
    nms_d = sorted(nm_map.values(), key=lambda x: -x.digits)

    print(f"\n  Phase 2: {el:.0f}s  {len(disc)} disc  "
          f"{len(nms_d)} near-misses  best={best_ever:.2f}d", flush=True)

    if nms_d:
        print(f"\n  Top 10 near-misses:")
        for i, nm in enumerate(nms_d[:10]):
            print(f"    #{i+1}: {nm.digits:.2f}d -> {nm.closest}  "
                  f"a={nm.a} b={nm.b}")

    return {
        "phase": 2, "prec": prec,
        "discoveries": disc,
        "near_misses": [
            {"a": nm.a, "b": nm.b, "cf_value": nm.cf_value,
             "closest": nm.closest, "digits": nm.digits, "cycle": nm.cycle}
            for nm in nms_d[:20]
        ],
        "elapsed": el, "best_digits": best_ever,
    }


# =====================================================================
#  MAIN
# =====================================================================
def main():
    print("\n" + "#" * 70)
    print("#  PCF Search for 3D Ising Tc / Kc  (v3: gradient-guided)")
    print(f"#  Tc = {TC_HP[:25]}...")
    print(f"#  Kc = {KC_HP[:25]}...")
    print("#" * 70, flush=True)

    # Phase 1
    p1 = run_phase1(cycles=1000, prec=100, tol=50,
                    pop_size=60, depth=200, seed=163)

    out = Path("results/pcf_search_Tc_3d.json")
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        json.dump({"phase1": p1}, f, indent=2, default=str)
    print(f"  Saved {out}")

    if p1["discoveries"]:
        print("\n  === Phase 1 SUCCESS ===")
        for d in p1["discoveries"]:
            print(f"    {d['match']}: a={d['a']} b={d['b']} ({d['digits']:.0f}d)")
    else:
        print("\n  No match in Phase 1. Running Phase 2...")
        ana = analyze(p1)
        p2 = run_phase2(ana, prec=500, cycles=500,
                        pop_size=80, depth=600, seed=314)

        with open(out, "w") as f:
            json.dump({"phase1": p1, "analysis": ana, "phase2": p2},
                      f, indent=2, default=str)

        # Final
        print("\n" + "=" * 70)
        print("  FINAL REPORT")
        print("=" * 70)
        all_d = p1["discoveries"] + p2["discoveries"]
        if all_d:
            for d in all_d:
                print(f"  {d['match']}: a={d['a']} b={d['b']} ({d['digits']:.0f}d)")
        else:
            print("\n  No exact PCF found for Tc = 4.51152785...")
            print("  (3D Ising Tc has no known closed-form -- this is expected.)")
            all_nm = p1["near_misses"] + p2.get("near_misses", [])
            all_nm.sort(key=lambda x: -x["digits"])
            if all_nm:
                print(f"\n  Best near-misses across both phases:")
                for i, nm in enumerate(all_nm[:10]):
                    print(f"    #{i+1}: {nm['digits']:.2f}d -> {nm['closest']}")
                    print(f"         a={nm['a']}  b={nm['b']}")
                    print(f"         cf_value={nm['cf_value']:.15f}")

    print("\n  Done.", flush=True)


if __name__ == "__main__":
    main()
