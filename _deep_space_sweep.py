"""Deep space sweep targeting transcendental gap constants.

Strategy: systematic grid scan of coefficient space around known-productive
templates, using RBG's full constant library plus transcendental gap targets.

Phase 1: Low-precision screening (50dps, depth 200) — fast rejection
Phase 2: Verify hits at 120dps/depth 800, then 220dps HP verification
"""
from __future__ import annotations
import json, time, sys, random, itertools
from pathlib import Path
from mpmath import mp, mpf, nstr, pi, log, sqrt, euler, catalan, log10

import ramanujan_breakthrough_generator as rbg
from deep_space import generate_symmetry_constrained

# ── Configuration ──────────────────────────────────────────────────
SCREEN_DPS = 50
SCREEN_DEPTH = 200
VERIFY_DPS = 120
VERIFY_DEPTH = 800
HP_DPS = 220
TOLERANCE = 15       # digits to count as a hit at screening
LOGFILE = Path("deep_space_discoveries.jsonl")


def build_full_library():
    """RBG's 59 constants + additional gap targets."""
    lib = rbg.build_constants(VERIFY_DPS)
    # Add extra gap targets not in RBG
    mp.dps = VERIFY_DPS + 20
    extras = {
        "ln(pi)":          log(pi),
        "pi/ln2":          pi / log(2),
        "pi*ln2":          pi * log(2),
        "sqrt(pi)":        sqrt(pi),
        "1/Catalan":       1 / catalan,
        "2*Catalan":       2 * catalan,
        "gamma+ln2":       euler + log(2),
        "exp(gamma)":      mp.exp(euler),
        "gamma^2":         euler**2,
        "pi/e":            pi / mp.e,
        "e/pi":            mp.e / pi,
        "Catalan+ln2":     catalan + log(2),
        "pi^2*ln2":        pi**2 * log(2),
        "gamma/ln2":       euler / log(2),
        "sqrt2*ln2":       sqrt(2) * log(2),
        "sqrt3*Catalan":   sqrt(3) * catalan,
    }
    for k, v in extras.items():
        if k not in lib:
            lib[k] = v
    return lib


def match_against(val, lib):
    """Match a PCF value against the constant library. Returns (name, digits)."""
    if val is None:
        return None, 0
    best_match = None
    best_digits = 0
    for name, const_val in lib.items():
        try:
            for label, test_val in [(name, val), (f"1/{name}", 1/val)]:
                diff = abs(test_val - const_val)
                if diff == 0:
                    return label, mp.dps
                if const_val != 0:
                    digits = float(-log10(abs(diff / const_val)))
                else:
                    digits = float(-log10(abs(diff)))
                if digits > best_digits:
                    best_digits = digits
                    best_match = label
        except Exception:
            continue
    return best_match, best_digits


def eval_cf(a, b, dps, depth):
    """Evaluate CF at given precision."""
    mp.dps = dps
    try:
        val = rbg.eval_pcf(list(a), list(b), depth=depth)
        if val is None or not rbg.is_reasonable(val):
            return None
        if rbg.is_telescoping(list(a), list(b)):
            return None
        return val
    except Exception:
        return None


def log_discovery(record):
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def grid_scan_configs():
    """Generate systematic coefficient grids around known-productive templates."""
    configs = []

    # Grid 1: S-family extensions — a(n) = c0 + c1*n + c2*n^2, b(n) = b0 + b1*n
    # The known S-family uses a=[0, 2m+1, -2], b=[1, 3]
    # Scan neighboring b values and non-standard c2
    for c2 in [-4, -3, -2, -1, 1, 2, 3, 4]:
        for c1 in range(-12, 16):
            for c0 in range(-4, 5):
                for b0 in [1, 2, 3, 4, 5]:
                    for b1 in [1, 2, 3, 4, 5, 6]:
                        configs.append(([c0, c1, c2], [b0, b1]))

    # Grid 2: Cubic a, linear b — a(n) = c0 + c1*n + c2*n^2 + c3*n^3
    for c3 in [-3, -2, -1, 1, 2, 3]:
        for c2 in range(-4, 5):
            for c1 in range(-6, 7):
                for b0 in [1, 2, 3]:
                    for b1 in [1, 2, 3, 4, 5]:
                        configs.append(([0, c1, c2, c3], [b0, b1]))

    # Grid 3: Linear a, quadratic b — a(n) = c0 + c1*n, b(n) = b0 + b1*n + b2*n^2
    for c0 in range(-5, 6):
        for c1 in range(-5, 6):
            for b0 in [1, 2, 3]:
                for b1 in range(-3, 4):
                    for b2 in range(-3, 4):
                        if b2 != 0:
                            configs.append(([c0, c1], [b0, b1, b2]))

    # Grid 4: Quadratic a, quadratic b (both deg 2)
    for c0 in range(-3, 4):
        for c1 in range(-4, 5):
            for c2 in [-3, -2, -1, 1, 2, 3]:
                for b0 in [1, 2, 3]:
                    for b1 in range(-3, 4):
                        for b2 in [-2, -1, 1, 2]:
                            configs.append(([c0, c1, c2], [b0, b1, b2]))

    random.shuffle(configs)
    return configs


def main():
    mp.dps = VERIFY_DPS + 20
    lib = build_full_library()

    print(f"Deep Space Systematic Sweep v2")
    print(f"  Constants: {len(lib)} targets (RBG + gap)")
    print(f"  Screen: {SCREEN_DPS}dps/depth {SCREEN_DEPTH}")
    print(f"  Verify: {VERIFY_DPS}dps/depth {VERIFY_DEPTH} -> {HP_DPS}dps HP")
    print(f"  Tolerance: {TOLERANCE}d")
    print(f"  Log: {LOGFILE}")

    configs = grid_scan_configs()
    total = len(configs)
    print(f"  Grid configs: {total:,}")
    print()

    seen = set()
    discoveries = 0
    near_misses = 0
    evaluated = 0
    converged = 0
    best_ever = ("", 0)
    t_start = time.time()

    batch_size = 1000

    for i, (a, b) in enumerate(configs):
        key = (tuple(a), tuple(b))
        if key in seen:
            continue
        seen.add(key)

        # Phase 1: fast screen
        val = eval_cf(a, b, SCREEN_DPS, SCREEN_DEPTH)
        evaluated += 1
        if val is None:
            continue
        converged += 1

        match, digits = match_against(val, lib)
        if digits < 8:
            continue

        # Phase 2: verify at full precision
        mp.dps = VERIFY_DPS + 20
        val_hp = eval_cf(a, b, VERIFY_DPS, VERIFY_DEPTH)
        if val_hp is None:
            continue

        match_hp, digits_hp = match_against(val_hp, lib)
        if digits_hp < TOLERANCE:
            if digits_hp >= 8:
                near_misses += 1
            continue

        # Phase 3: HP verification
        verified_digits = digits_hp
        mp.dps = HP_DPS + 20
        val_uhp = eval_cf(a, b, HP_DPS, VERIFY_DEPTH)
        if val_uhp is not None:
            _, vd = match_against(val_uhp, lib)
            verified_digits = vd

        discoveries += 1
        record = {
            "match": match_hp,
            "a": list(a),
            "b": list(b),
            "digits": round(digits_hp, 1),
            "verified_digits": round(verified_digits, 1),
            "cycle": i,
            "source": "deep_space_grid",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        log_discovery(record)
        print(f"  *** DISCOVERY: {match_hp} = CF(a={a}, b={b}) "
              f"@ {verified_digits:.0f}d verified")

        if verified_digits > best_ever[1]:
            best_ever = (match_hp, verified_digits)

        # Report progress
        if (i + 1) % batch_size == 0 or discoveries > 0:
            elapsed = time.time() - t_start
            rate = evaluated / elapsed if elapsed > 0 else 0
            pct = 100 * (i + 1) / total
            print(f"  [{pct:5.1f}%] eval={evaluated:,} conv={converged:,} "
                  f"disc={discoveries} nm={near_misses} "
                  f"best={best_ever[0]}@{best_ever[1]:.0f}d "
                  f"[{rate:.0f}/s, {elapsed:.0f}s]")

        if (i + 1) % batch_size == 0 and discoveries == 0:
            elapsed = time.time() - t_start
            rate = evaluated / elapsed if elapsed > 0 else 0
            pct = 100 * (i + 1) / total
            print(f"  [{pct:5.1f}%] eval={evaluated:,} conv={converged:,} "
                  f"disc={discoveries} nm={near_misses} "
                  f"[{rate:.0f}/s, {elapsed:.0f}s]")

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"Sweep complete in {elapsed:.0f}s")
    print(f"  Evaluated: {evaluated:,} | Converged: {converged:,}")
    print(f"  Discoveries: {discoveries} | Near-misses: {near_misses}")
    print(f"  Best: {best_ever[0]} @ {best_ever[1]:.0f}d")


if __name__ == "__main__":
    main()
