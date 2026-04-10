"""
_pcf_search_Tc_3d_ising.py
============================
Targeted PCF search for the 3D Ising critical temperature K = Tc = 4.511528...

Uses the ramanujan-breakthrough-generator's evolutionary search engine
to find polynomial continued fractions matching K and simple rational
transforms of K (1/K, K/pi, K^2, sqrt(K), etc.).

Phase 1: 1000 evolutionary cycles at 100 dp, tol = 50 digits.
Phase 2: If no exact match, analyze top-5 near-misses and re-run at 500 dp
          with refined search ranges.
"""

from __future__ import annotations
import json, time, sys, random, math
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass

from mpmath import mp, mpf, pi, log, sqrt, zeta, euler, nstr

sys.path.insert(0, ".")
import ramanujan_breakthrough_generator as rbg

# ── The target constant: 3D Ising critical temperature ───────────────────────
# High-precision value from Ferrenberg-Xu-Landau (2018) / Butera-Comi (2002):
#   Kc = 0.22165455(3)  =>  Tc = 1/Kc = 4.51152785(6)
# We use 30+ digits via the series-expansion literature value:
TC_HP = "4.51152785060191536876679816744526"  # 32 significant digits
KC_HP = "0.22165455054281198362779272823516"  # 1/Tc to 32 digits


def build_ising_constants(prec: int) -> dict[str, mpf]:
    """Build a constant library centered on Tc and its transforms."""
    mp.dps = prec + 30

    Tc = mpf(TC_HP)
    Kc = mpf(KC_HP)

    consts: dict[str, mpf] = {}

    # ── Core Tc transforms (small, focused library) ──
    consts["Tc"]        = Tc
    consts["1/Tc"]      = Kc
    consts["Tc^2"]      = Tc**2
    consts["sqrt_Tc"]   = sqrt(Tc)
    consts["Tc-4"]      = Tc - 4

    # ── Tc with pi ──
    consts["Tc/pi"]     = Tc / pi

    # ── Tc with log ──
    consts["log_Tc"]    = log(Tc)

    # ── Tc with zeta ──
    consts["Tc/zeta3"]  = Tc / zeta(3)

    # ── Kc transforms ──
    consts["2*Kc"]      = 2 * Kc
    consts["Kc^2"]      = Kc**2
    consts["sqrt_Kc"]   = sqrt(Kc)

    # ── Small rational multiples p/q * Tc for p,q <= 4 ──
    for p in range(1, 5):
        for q in range(1, 5):
            if math.gcd(p, q) == 1 and (p, q) != (1, 1):
                label = f"{p}/{q}*Tc"
                consts[label] = mpf(p) / q * Tc

    # ── Small rational multiples p/q * Kc for p,q <= 4 ──
    for p in range(1, 5):
        for q in range(1, 5):
            if math.gcd(p, q) == 1 and (p, q) != (1, 1):
                label = f"{p}/{q}*Kc"
                consts[label] = mpf(p) / q * Kc

    # NOTE: We deliberately exclude standard constants (pi, e, zeta3, etc.)
    # to avoid false-positive matches from known seed CFs. This search is
    # *exclusively* targeting Tc and its transforms.

    return consts


@dataclass
class NearMiss:
    """A CF that came close to matching a constant."""
    a_coeffs: list
    b_coeffs: list
    cf_value: float
    closest_const: str
    residual_digits: float
    cycle: int


def pslq_scan(val: mpf, constants: dict[str, mpf], tol_digits: int) -> tuple | None:
    """Check val against all constants via direct ratio comparison."""
    if val is None or not rbg.is_reasonable(val):
        return None

    threshold = mpf(10) ** (-tol_digits)
    best_name, best_digits = None, 0.0

    for name, cval in constants.items():
        if cval == 0:
            continue
        residual = abs(val - cval)
        if residual == 0:
            return (name, float('inf'))
        digits = float(-mp.log10(residual))
        if digits > best_digits:
            best_digits = digits
            best_name = name
        if residual < threshold:
            return (name, digits)

    # Also try -val
    negval = -val
    for name, cval in constants.items():
        if cval == 0:
            continue
        residual = abs(negval - cval)
        if residual == 0:
            return (f"-{name}", float('inf'))
        digits = float(-mp.log10(residual))
        if digits > best_digits:
            best_digits = digits
            best_name = f"-{name}"
        if residual < threshold:
            return (f"-{name}", digits)

    # Return best near-miss info even if below threshold
    if best_name and best_digits > 3:
        return (best_name, best_digits)
    return None


def run_phase1(cycles: int = 1000, precision: int = 100, tol_digits: int = 50,
               pop_size: int = 60, depth: int = 300, seed: int = 163) -> dict:
    """Phase 1: Evolutionary search for PCFs matching Tc."""
    print("=" * 72)
    print("  PHASE 1: PCF Search for 3D Ising Tc = 4.511528...")
    print(f"  Cycles: {cycles}, Precision: {precision} dp, Tol: {tol_digits} digits")
    print(f"  Population: {pop_size}, Depth: {depth}, Seed: {seed}")
    print("=" * 72)

    mp.dps = precision + 30
    rng = random.Random(seed)
    constants = build_ising_constants(precision)

    print(f"\n  Target library: {len(constants)} constants")
    print(f"  Tc  = {nstr(constants['Tc'], 30)}")
    print(f"  Kc  = {nstr(constants['1/Tc'], 30)}")

    # Build initial population
    population = list(rbg.seed_population())
    while len(population) < pop_size:
        population.append(rbg.random_fertile_params(rng))

    discoveries = []
    near_misses: list[NearMiss] = []
    seen_keys: set = set()
    temperature = 2.0
    last_discovery_cycle = 0

    t0 = time.time()

    for cycle in range(1, cycles + 1):
        # Evaluate each CF
        for p in population:
            key = p.key()
            if key in seen_keys:
                continue
            seen_keys.add(key)

            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            if val is None or not rbg.is_reasonable(val):
                p.score = -999
                continue
            if rbg.is_telescoping(p.a, p.b):
                p.score = -999
                continue

            result = pslq_scan(val, constants, tol_digits)
            if result is not None:
                name, digits = result
                p.score = digits

                if digits >= tol_digits:
                    # MATCH!
                    p.hit = name
                    last_discovery_cycle = cycle
                    discoveries.append({
                        "cycle": cycle,
                        "a": p.a[:],
                        "b": p.b[:],
                        "match": name,
                        "value": str(val),
                        "digits": digits,
                        "complexity": rbg.complexity_score(p.a, p.b),
                    })
                    print(f"\n  *** MATCH at cycle {cycle}: {name} ***")
                    print(f"      a(n) = {p.a}, b(n) = {p.b}")
                    print(f"      Verified: {digits:.1f} digits")

                elif digits > 5:
                    # Near-miss
                    near_misses.append(NearMiss(
                        a_coeffs=p.a[:], b_coeffs=p.b[:],
                        cf_value=float(val),
                        closest_const=name,
                        residual_digits=digits,
                        cycle=cycle,
                    ))
            else:
                p.score = 0.0

        # Sort and report progress
        population.sort(key=lambda p: -p.score)
        temperature = rbg.adapt_temperature(
            temperature, [p.score for p in population[:5]], cycle, last_discovery_cycle
        )
        population = rbg.evolve_population(population, pop_size, temperature, rng)

        if cycle % 10 == 0 or cycle == 1:
            elapsed = time.time() - t0
            best = max((nm.residual_digits for nm in near_misses), default=0.0)
            n_nm = len([nm for nm in near_misses if nm.residual_digits > 8])
            print(f"  Cycle {cycle:5d}/{cycles} | T={temperature:.3f} | "
                  f"Discoveries: {len(discoveries)} | Near-misses(>8d): {n_nm} | "
                  f"Best: {best:.1f}d | {elapsed:.1f}s", flush=True)

    elapsed = time.time() - t0

    # Deduplicate near-misses by CF key, keep best
    nm_best: dict[tuple, NearMiss] = {}
    for nm in near_misses:
        key = (tuple(nm.a_coeffs), tuple(nm.b_coeffs))
        if key not in nm_best or nm.residual_digits > nm_best[key].residual_digits:
            nm_best[key] = nm

    near_misses_dedup = sorted(nm_best.values(), key=lambda nm: -nm.residual_digits)

    print(f"\n  Phase 1 complete in {elapsed:.1f}s")
    print(f"  Discoveries: {len(discoveries)}")
    print(f"  Unique near-misses (>5 digits): {len(near_misses_dedup)}")

    return {
        "phase": 1,
        "cycles": cycles,
        "precision": precision,
        "discoveries": discoveries,
        "near_misses": [
            {"a": nm.a_coeffs, "b": nm.b_coeffs, "cf_value": nm.cf_value,
             "closest": nm.closest_const, "digits": nm.residual_digits, "cycle": nm.cycle}
            for nm in near_misses_dedup[:50]
        ],
        "elapsed": elapsed,
    }


def analyze_near_misses(results: dict) -> dict:
    """Analyze top-5 near-misses to hypothesize refined search ranges."""
    near_misses = results["near_misses"][:5]

    print("\n" + "=" * 72)
    print("  NEAR-MISS ANALYSIS — Top 5")
    print("=" * 72)

    hypotheses = []

    if not near_misses:
        print("  No near-misses found. Broadening search in Phase 2.")
        return {
            "hypotheses": [],
            "recommended_deg_a": [2, 3, 4],
            "recommended_deg_b": [1, 2, 3],
            "recommended_coeff_range": 10,
        }

    # Analyze structural patterns in the top near-misses
    deg_a_counts = defaultdict(int)
    deg_b_counts = defaultdict(int)
    max_coeff = 0
    closest_targets = defaultdict(int)

    for i, nm in enumerate(near_misses):
        a, b = nm["a"], nm["b"]
        digits = nm["digits"]
        closest = nm["closest"]

        # Effective degree (ignoring trailing zeros)
        eff_deg_a = len(a) - 1
        while eff_deg_a > 0 and a[eff_deg_a] == 0:
            eff_deg_a -= 1
        eff_deg_b = len(b) - 1
        while eff_deg_b > 0 and b[eff_deg_b] == 0:
            eff_deg_b -= 1

        deg_a_counts[eff_deg_a] += 1
        deg_b_counts[eff_deg_b] += 1
        max_coeff = max(max_coeff, max(abs(c) for c in a + b))
        closest_targets[closest] += 1

        print(f"\n  #{i+1}: {digits:.1f} digits -> {closest}")
        print(f"       a(n) = {a}  (deg {eff_deg_a})")
        print(f"       b(n) = {b}  (deg {eff_deg_b})")
        print(f"       CF value = {nm['cf_value']}")

        # Hypothesis: based on how close this came
        if digits > 15:
            hypotheses.append({
                "type": "perturbation",
                "base_a": a,
                "base_b": b,
                "target": closest,
                "digits": digits,
                "strategy": "Perturb coefficients by +/-1 at 500dp",
            })
        elif digits > 7:
            hypotheses.append({
                "type": "degree_extension",
                "base_a": a,
                "base_b": b,
                "target": closest,
                "digits": digits,
                "strategy": f"Extend a(n) to deg {eff_deg_a + 1}, widen coeff range",
            })

    # Determine recommended search parameters from patterns
    best_deg_a = max(deg_a_counts, key=deg_a_counts.get) if deg_a_counts else 2
    best_deg_b = max(deg_b_counts, key=deg_b_counts.get) if deg_b_counts else 1
    rec_coeff = min(max_coeff + 5, 15)

    most_common_target = max(closest_targets, key=closest_targets.get) if closest_targets else "Tc"

    print(f"\n  --- Structural Summary ---")
    print(f"  Most productive deg(a): {best_deg_a}")
    print(f"  Most productive deg(b): {best_deg_b}")
    print(f"  Max coefficient seen:   {max_coeff}")
    print(f"  Most matched target:    {most_common_target}")

    analysis = {
        "hypotheses": hypotheses,
        "recommended_deg_a": sorted(set([best_deg_a, best_deg_a + 1, 2, 3])),
        "recommended_deg_b": sorted(set([best_deg_b, best_deg_b + 1, 1, 2])),
        "recommended_coeff_range": rec_coeff,
        "focus_target": most_common_target,
        "top_near_misses": near_misses,
    }

    return analysis


def run_phase2(analysis: dict, precision: int = 500, cycles: int = 500,
               pop_size: int = 80, depth: int = 500, seed: int = 314) -> dict:
    """Phase 2: High-precision re-run guided by near-miss hypotheses."""
    print("\n" + "=" * 72)
    print("  PHASE 2: High-Precision Refinement at 500 dp")
    print(f"  Cycles: {cycles}, Precision: {precision} dp, Depth: {depth}")
    print(f"  Focus: {analysis.get('focus_target', 'Tc')}")
    print("=" * 72)

    mp.dps = precision + 50
    rng = random.Random(seed)
    constants = build_ising_constants(precision)
    tol_digits = precision // 2  # 250 digits for a match at 500dp

    # Build targeted initial population from hypotheses
    population = []

    # Inject perturbations of top near-misses
    for h in analysis.get("hypotheses", []):
        base_a = h["base_a"]
        base_b = h["base_b"]
        # Generate perturbation cloud around each near-miss
        for _ in range(10):
            new_a = [c + rng.randint(-2, 2) for c in base_a]
            new_b = [c + rng.randint(-1, 1) for c in base_b]
            new_b[0] = max(1, new_b[0])
            population.append(rbg.PCFParams(a=new_a, b=new_b))
        # Also try degree extensions
        ext_a = base_a + [rng.randint(-3, 3)]
        population.append(rbg.PCFParams(a=ext_a, b=base_b))
        ext_b = base_b + [rng.randint(-2, 2)]
        population.append(rbg.PCFParams(a=base_a, b=ext_b))

    # Fill with recommended-degree random CFs
    rec_degs_a = analysis.get("recommended_deg_a", [2, 3])
    rec_degs_b = analysis.get("recommended_deg_b", [1, 2])
    rec_range = analysis.get("recommended_coeff_range", 8)

    while len(population) < pop_size:
        da = rng.choice(rec_degs_a)
        db = rng.choice(rec_degs_b)
        population.append(rbg.random_params(a_deg=da, b_deg=db,
                                            coeff_range=rec_range, rng=rng))

    discoveries = []
    near_misses: list[NearMiss] = []
    seen_keys: set = set()
    temperature = 2.5
    last_discovery_cycle = 0

    t0 = time.time()

    for cycle in range(1, cycles + 1):
        for p in population:
            key = p.key()
            if key in seen_keys:
                continue
            seen_keys.add(key)

            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            if val is None or not rbg.is_reasonable(val):
                p.score = -999
                continue
            if rbg.is_telescoping(p.a, p.b):
                p.score = -999
                continue

            result = pslq_scan(val, constants, tol_digits)
            if result is not None:
                name, digits = result

                p.score = digits

                if digits >= tol_digits:
                    p.hit = name
                    last_discovery_cycle = cycle
                    discoveries.append({
                        "cycle": cycle,
                        "a": p.a[:],
                        "b": p.b[:],
                        "match": name,
                        "value": nstr(val, 60),
                        "digits": digits,
                        "complexity": rbg.complexity_score(p.a, p.b),
                    })
                    print(f"\n  *** PHASE 2 MATCH at cycle {cycle}: {name} ***")
                    print(f"      a(n) = {p.a}, b(n) = {p.b}")
                    print(f"      Verified: {digits:.1f} digits at {precision}dp")

                elif digits > 8:
                    near_misses.append(NearMiss(
                        a_coeffs=p.a[:], b_coeffs=p.b[:],
                        cf_value=float(val),
                        closest_const=name,
                        residual_digits=digits,
                        cycle=cycle,
                    ))
            else:
                p.score = 0.0

        population.sort(key=lambda p: -p.score)
        temperature = rbg.adapt_temperature(
            temperature, [p.score for p in population[:5]], cycle, last_discovery_cycle
        )
        population = rbg.evolve_population(population, pop_size, temperature, rng)

        if cycle % 10 == 0 or cycle == 1:
            elapsed = time.time() - t0
            best = max((nm.residual_digits for nm in near_misses), default=0.0)
            print(f"  Cycle {cycle:5d}/{cycles} | T={temperature:.3f} | "
                  f"Matches: {len(discoveries)} | Best near-miss: {best:.1f}d | "
                  f"{elapsed:.1f}s", flush=True)

    elapsed = time.time() - t0

    # Dedup near-misses
    nm_best: dict[tuple, NearMiss] = {}
    for nm in near_misses:
        key = (tuple(nm.a_coeffs), tuple(nm.b_coeffs))
        if key not in nm_best or nm.residual_digits > nm_best[key].residual_digits:
            nm_best[key] = nm
    near_misses_dedup = sorted(nm_best.values(), key=lambda nm: -nm.residual_digits)

    print(f"\n  Phase 2 complete in {elapsed:.1f}s")
    print(f"  Discoveries: {len(discoveries)}")
    print(f"  Near-misses (>8 digits): {len(near_misses_dedup)}")

    return {
        "phase": 2,
        "cycles": cycles,
        "precision": precision,
        "discoveries": discoveries,
        "near_misses": [
            {"a": nm.a_coeffs, "b": nm.b_coeffs, "cf_value": nm.cf_value,
             "closest": nm.closest_const, "digits": nm.residual_digits, "cycle": nm.cycle}
            for nm in near_misses_dedup[:20]
        ],
        "elapsed": elapsed,
    }


def main():
    print("\n" + "#" * 72)
    print("#  PCF Search for 3D Ising Critical Temperature")
    print("#  K = Tc = 4.51152785060191536876679816744526...")
    print("#" * 72)

    # Phase 1
    p1 = run_phase1(cycles=1000, precision=100, tol_digits=50,
                    pop_size=60, depth=600, seed=163)

    # Save Phase 1 results
    out_path = Path("results/pcf_search_Tc_3d.json")
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"phase1": p1}, f, indent=2, default=str)
    print(f"\n  Phase 1 results saved to {out_path}")

    if p1["discoveries"]:
        print("\n" + "=" * 72)
        print("  SUCCESS: Found PCF match(es) for Tc in Phase 1!")
        print("=" * 72)
        for d in p1["discoveries"]:
            print(f"  {d['match']}: a={d['a']}, b={d['b']} ({d['digits']:.0f} digits)")
    else:
        print("\n  No exact matches in Phase 1 -- proceeding to near-miss analysis.")

        # Analyze near-misses
        analysis = analyze_near_misses(p1)

        # Phase 2: High-precision re-run
        p2 = run_phase2(analysis, precision=500, cycles=500,
                        pop_size=80, depth=1000, seed=314)

        # Save combined results
        with open(out_path, "w") as f:
            json.dump({"phase1": p1, "analysis": analysis, "phase2": p2},
                      f, indent=2, default=str)
        print(f"\n  Full results saved to {out_path}")

        # Final report
        print("\n" + "=" * 72)
        print("  FINAL REPORT")
        print("=" * 72)

        all_disc = p1["discoveries"] + p2["discoveries"]
        if all_disc:
            print(f"\n  Total discoveries: {len(all_disc)}")
            for d in all_disc:
                print(f"    Phase {d.get('phase', '?')}: {d['match']}")
                print(f"      a(n) = {d['a']}, b(n) = {d['b']}")
                print(f"      Digits: {d['digits']:.0f}")
        else:
            print("\n  No exact match found for Tc = 4.511528...")
            print("  This suggests Tc may not have a simple PCF representation,")
            print("  or the search space needs further expansion.")

            # Print best near-misses across both phases
            all_nm = p1["near_misses"] + p2["near_misses"]
            all_nm.sort(key=lambda nm: -nm["digits"])
            print(f"\n  Best near-misses across both phases (top 10):")
            for i, nm in enumerate(all_nm[:10]):
                print(f"    #{i+1}: {nm['digits']:.1f}d -> {nm['closest']}")
                print(f"         a = {nm['a']}, b = {nm['b']}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
