#!/usr/bin/env python3
"""
Logged Clean Sweep — 100 Candidates with Full Rationality Filter Trace
═══════════════════════════════════════════════════════════════════════

For each candidate GCF:
  1. Compute CF value at 300dp
  2. Run rationality test: is CF = p/q for q <= 10000?
  3. If rational: log "RATIONAL p/q — FILTERED" and skip
  4. If not rational: run degree-1 PSLQ against target
  5. If degree-1 hits: log "GENUINE" with full relation
  6. If no hit: log "IRRATIONAL — UNIDENTIFIED"

This produces a complete audit trail proving the filter works.
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mpmath as mp

from ramanujan_agent_v2_fast import (
    GCFSpec, GCFGenerator, builtin_seeds, CONSTANTS,
    _merge_priority_maps, DEFAULT_SIGNATURE_PRIORITY_MAP,
)

DPS = 300
DEPTH = 300
N_CANDIDATES = 100
RNG_SEED = 12345
LOG_FILE = "logged_clean_sweep.txt"


def poly_eval(coeffs, n):
    n_mpf = mp.mpf(n)
    result = mp.mpf(coeffs[-1])
    for c in coeffs[-2::-1]:
        result = result * n_mpf + c
    return result


def eval_backward(alpha, beta, depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            a_n = poly_eval(alpha, n)
            b_n = poly_eval(beta, n)
            denom = b_n + v
            if denom == 0:
                return mp.nan
            v = a_n / denom
        return poly_eval(beta, 0) + v


def check_rational(val, dps, max_denom=10000):
    with mp.workdps(dps):
        if abs(val) < mp.mpf(10)**(-(dps // 2)):
            return True, 0, 1  # CF = 0 is rational
        try:
            rel = mp.pslq([val, mp.mpf(1)], maxcoeff=max_denom, maxsteps=500)
        except Exception:
            return False, 0, 0
        if rel and rel[0] != 0:
            expected = mp.mpf(-rel[1]) / mp.mpf(rel[0])
            diff = abs(val - expected)
            if diff < mp.mpf(10)**(-(dps // 2)):
                return True, -int(rel[1]), int(rel[0])
    return False, 0, 0


def main():
    mp.mp.dps = DPS
    random.seed(RNG_SEED)

    targets = {}
    with mp.workdps(DPS + 50):
        targets["zeta3"] = mp.zeta(3)
        targets["zeta5"] = mp.zeta(5)
        targets["pi"] = mp.pi

    target_names = list(targets.keys())

    seeds = builtin_seeds()
    gen = GCFGenerator(seeds, target="zeta3",
                       priority_map=_merge_priority_maps(None, "zeta3"),
                       deep_mode=False)

    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log("=" * 74)
    log("  LOGGED CLEAN SWEEP — 100 CANDIDATES")
    log(f"  Precision: {DPS}dp, Depth: {DEPTH}, RNG seed: {RNG_SEED}")
    log("=" * 74)
    log("")

    rational_count = 0
    irrational_count = 0
    genuine_count = 0
    divergent_count = 0

    batch = gen.next_batch(N_CANDIDATES)

    for i, spec in enumerate(batch):
        alpha = spec.alpha
        beta = spec.beta
        sig = f"adeg={len(alpha)-1}|bdeg={len(beta)-1}"

        try:
            cf = eval_backward(alpha, beta, DEPTH, DPS)
        except Exception:
            log(f"[{i+1:3d}] ERROR     a={alpha} b={beta}")
            divergent_count += 1
            continue

        if mp.isnan(cf) or mp.isinf(cf):
            log(f"[{i+1:3d}] DIVERGENT a={alpha} b={beta}")
            divergent_count += 1
            continue

        is_rat, p, q = check_rational(cf, DPS)

        if is_rat:
            rational_count += 1
            log(f"[{i+1:3d}] RATIONAL  CF={p}/{q:>5d}  {sig:20s}  a={alpha} b={beta}  — FILTERED")
        else:
            irrational_count += 1
            cf_str = mp.nstr(cf, 15)

            # Test against all targets with degree-1 PSLQ
            found = False
            with mp.workdps(DPS):
                for tname, tval in targets.items():
                    rel = mp.pslq([cf, tval, mp.mpf(1)],
                                  maxcoeff=10000, maxsteps=2000)
                    if rel and rel[0] != 0 and rel[1] != 0:
                        dot = abs(rel[0]*cf + rel[1]*tval + rel[2])
                        rd = max(0, int(-float(mp.log10(dot)))) if dot > 0 else DPS
                        if rd >= 50:
                            genuine_count += 1
                            log(f"[{i+1:3d}] GENUINE   CF={cf_str}  {sig:20s}  "
                                f"{rel[0]}*CF + {rel[1]}*{tname} + {rel[2]} = 0 ({rd}dp)")
                            log(f"          a={alpha} b={beta}")
                            found = True
                            break

            if not found:
                log(f"[{i+1:3d}] IRRATIONAL-UNID  CF={cf_str}  {sig:20s}  a={alpha} b={beta}")

    log("")
    log("=" * 74)
    log("  SUMMARY")
    log("=" * 74)
    log(f"  Total candidates:   {N_CANDIDATES}")
    log(f"  Rational (filtered):{rational_count:4d}")
    log(f"  Irrational:         {irrational_count:4d}")
    log(f"  Genuine hits:       {genuine_count:4d}")
    log(f"  Divergent/error:    {divergent_count:4d}")
    log(f"  Filter active:      {'YES' if rational_count > 0 else 'NO'}")
    log("")

    if genuine_count > 0:
        log("  *** GENUINE TRANSCENDENTAL DISCOVERIES FOUND ***")
    elif irrational_count > 0:
        log(f"  {irrational_count} irrational CF values found but none identified")
        log("  with known constants at degree-1 PSLQ.")
    else:
        log("  All CF values were rational. No transcendental GCFs in this batch.")

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"\n  Full log: {LOG_FILE}")


if __name__ == "__main__":
    main()
