"""Even-k sweep: explore the rational branch of the a=[0, k, -2], b=[1, 3] family.

The "parity phenomenon": odd k -> transcendental (pi-multiples),
even k -> rational (central binomial convergents C(c-1,(c-2)/2)/2^(c/2-1)).

This script:
  Phase 1: Verify the known rational pattern for even k=2,4,...,60
  Phase 2: Extend with perturbed a-vectors around even k templates
  Phase 3: Sweep alternative b-vectors with even k a-polynomials
  Phase 4: Search for NEW rational families beyond a=[0,k,-2]

Outputs discoveries to even_k_discoveries.jsonl and status to status_even_k.json.
"""
from __future__ import annotations
import json, sys, time, random, itertools
from fractions import Fraction
from math import comb, factorial
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from mpmath import mp, mpf, nstr, pi, log, sqrt, log10

import ramanujan_breakthrough_generator as rbg

# ── Configuration ──────────────────────────────────────────────────
SCREEN_DPS = 60
SCREEN_DEPTH = 300
VERIFY_DPS = 150
VERIFY_DEPTH = 2000
HP_DPS = 250
TOLERANCE = 18       # digits required for a hit
LOGFILE = Path("even_k_discoveries.jsonl")
STATUS_FILE = Path("status_even_k.json")
SEED = 4242


def write_status(evals, hits, near_misses, best, phase, elapsed):
    """Write status JSON for the orchestrator to monitor."""
    data = {
        "evals": evals,
        "hits": hits,
        "near_misses": near_misses,
        "best_match": best[0],
        "best_digits": round(best[1], 1),
        "phase": phase,
        "elapsed": round(elapsed, 1),
        "timestamp": datetime.now().isoformat(),
    }
    STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def log_discovery(record):
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def eval_cf(a, b, dps, depth):
    """Evaluate CF at given precision, returning None on failure."""
    mp.dps = dps + 10
    try:
        val = rbg.eval_pcf(list(a), list(b), depth=depth)
        if val is None or not rbg.is_reasonable(val):
            return None
        return val
    except Exception:
        return None


def convergence_check(a, b, dps, d1, d2):
    """Return (value, agreement_digits) using two depths."""
    v1 = eval_cf(a, b, dps, d1)
    if v1 is None:
        return None, 0
    v2 = eval_cf(a, b, dps, d2)
    if v2 is None:
        return None, 0
    diff = abs(v1 - v2)
    if diff == 0:
        return v1, dps
    return v1, max(0, float(-log10(diff)))


def rational_identify(val, max_denom=10000):
    """Try to identify val as a simple rational p/q."""
    if val is None:
        return None
    fval = float(val)
    # Use continued fraction algorithm
    best = None
    best_err = 1.0
    for q in range(1, min(max_denom + 1, 2000)):
        p = round(fval * q)
        if p == 0:
            continue
        err = abs(fval - p / q)
        if err < best_err:
            best_err = err
            best = (p, q)
        if err < 1e-30:
            break
    if best is None:
        return None
    p, q = best
    # Verify at high precision
    mp.dps = VERIFY_DPS + 10
    residual = abs(val - mpf(p) / q)
    if residual == 0:
        digits = VERIFY_DPS
    elif residual > 0:
        digits = float(-log10(residual))
    else:
        return None
    if digits > TOLERANCE:
        return (p, q, digits)
    return None


def central_binomial_prediction(c):
    """For even c, a(n) = n(c-2n) has a(c/2)=0 so the CF truncates.
    
    Compute the exact finite CF value using rational arithmetic:
      CF = b(0) + a(1)/(b(1) + a(2)/(b(2) + ... + a(c/2-1)/b(c/2-1)))
    where a(n) = n(c-2n), b(n) = 3n+1.
    """
    if c % 2 != 0 or c < 2:
        return None
    # The CF truncates at n = c/2 (since a(c/2)=0)
    # Build from bottom up
    N = c // 2  # truncation point
    val = Fraction(0)
    for n in range(N - 1, 0, -1):
        an = n * (c - 2 * n)
        bn = 3 * n + 1
        val = Fraction(an, bn + val)
    # Add b(0) = 1
    return Fraction(1) + val


def build_rational_library(max_k=100):
    """Pre-compute expected rational values for even k from the closed form."""
    lib = {}
    for k in range(2, max_k + 1, 2):
        frac = central_binomial_prediction(k)
        if frac is not None:
            lib[k] = frac
    return lib


def match_against_constants(val, lib):
    """Match against the RBG constant library. Returns (name, digits)."""
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


# ── Phase 1: Verify known rational pattern ─────────────────────────
def phase1_verify_rationals():
    """Verify C(k-1,(k-2)/2)/2^((k-2)/2) for even k=2..60."""
    print("=" * 70)
    print("  PHASE 1: Verify known rational branch (even k, a=[0,k,-2], b=[1,3])")
    print("=" * 70)

    rat_lib = build_rational_library(80)
    results = []
    verified = 0
    extended = 0

    for k in range(2, 62, 2):
        a = [0, k, -2]
        b = [1, 3]
        val, conv = convergence_check(a, b, VERIFY_DPS, SCREEN_DEPTH, VERIFY_DEPTH)
        if val is None:
            print(f"  k={k:3d}  DIVERGES")
            continue

        # Check against predicted rational
        expected = rat_lib.get(k)
        if expected is not None:
            mp.dps = VERIFY_DPS + 10
            exp_mpf = mpf(expected.numerator) / mpf(expected.denominator)
            residual = abs(val - exp_mpf)
            if residual == 0:
                match_digits = VERIFY_DPS
            else:
                match_digits = float(-log10(residual))

            if match_digits > 30:
                verified += 1
                tag = "VERIFIED"
            else:
                tag = f"MISMATCH ({match_digits:.1f}d)"

            print(f"  k={k:3d}  = {expected.numerator}/{expected.denominator}"
                  f"  {tag}  (conv={conv:.0f}d)")

            record = {
                "a": a, "b": b,
                "match": f"{expected.numerator}/{expected.denominator}",
                "verified_digits": round(match_digits, 1),
                "convergence_digits": round(conv, 1),
                "type": "even_k_rational",
                "k": k,
                "shard": "even-k-verify",
                "timestamp": datetime.now().isoformat(),
            }
            results.append(record)
            if match_digits > 30:
                log_discovery(record)
        else:
            # For higher k, try rational identification
            rid = rational_identify(val)
            if rid:
                p, q, digits = rid
                print(f"  k={k:3d}  = {p}/{q}  ({digits:.1f}d, conv={conv:.0f}d) NEW")
                extended += 1
                record = {
                    "a": a, "b": b,
                    "match": f"{p}/{q}",
                    "verified_digits": round(digits, 1),
                    "convergence_digits": round(conv, 1),
                    "type": "even_k_rational_new",
                    "k": k,
                    "shard": "even-k-extend",
                    "timestamp": datetime.now().isoformat(),
                }
                results.append(record)
                log_discovery(record)
            else:
                print(f"  k={k:3d}  = {nstr(val, 25)}  NO RATIONAL ID (conv={conv:.0f}d)")

    print(f"\n  Phase 1 summary: {verified} verified, {extended} new extensions")
    return results


# ── Phase 2: Perturbed a-vectors around even k ─────────────────────
def phase2_perturbations():
    """Explore a-vectors near [0, k, -2] for even k."""
    print("\n" + "=" * 70)
    print("  PHASE 2: Perturbations around a=[0, k, -2] (even k)")
    print("=" * 70)

    hits = []
    evals = 0
    # Build RBG constant library for transcendental matching
    mp.dps = VERIFY_DPS + 20
    const_lib = rbg.build_constants(VERIFY_DPS)

    for k in range(2, 22, 2):
        print(f"\n  --- k={k} ---")
        # Try a0 != 0, a2 != -2, higher degree terms
        for a0 in range(-3, 4):
            for a2 in [-4, -3, -2, -1, 1, 2]:
                for a3 in [0, -1, 1]:
                    a = [a0, k, a2] if a3 == 0 else [a0, k, a2, a3]
                    if a == [0, k, -2]:
                        continue  # skip base case

                    val = eval_cf(a, [1, 3], SCREEN_DPS, SCREEN_DEPTH)
                    evals += 1
                    if val is None:
                        continue

                    # Try rational identification first
                    rid = rational_identify(val)
                    if rid:
                        p, q, digits = rid
                        if digits > TOLERANCE:
                            print(f"    a={a} b=[1,3]  = {p}/{q}  ({digits:.1f}d) RATIONAL")
                            record = {
                                "a": a, "b": [1, 3],
                                "match": f"{p}/{q}",
                                "verified_digits": round(digits, 1),
                                "type": "even_k_perturbed_rational",
                                "k": k,
                                "shard": "even-k-perturb",
                                "timestamp": datetime.now().isoformat(),
                            }
                            hits.append(record)
                            log_discovery(record)
                            continue

                    # Try transcendental match
                    match, digits = match_against_constants(val, const_lib)
                    if digits > TOLERANCE:
                        # Verify at higher precision
                        val_hp = eval_cf(a, [1, 3], VERIFY_DPS, VERIFY_DEPTH)
                        if val_hp is not None:
                            match_hp, digits_hp = match_against_constants(val_hp, const_lib)
                            if digits_hp > TOLERANCE:
                                print(f"    a={a} b=[1,3]  ≈ {match_hp}  ({digits_hp:.1f}d)")
                                record = {
                                    "a": a, "b": [1, 3],
                                    "match": match_hp,
                                    "verified_digits": round(digits_hp, 1),
                                    "type": "even_k_perturbed_transcendental",
                                    "k": k,
                                    "shard": "even-k-perturb",
                                    "timestamp": datetime.now().isoformat(),
                                }
                                hits.append(record)
                                log_discovery(record)

    print(f"\n  Phase 2 summary: {len(hits)} hits from {evals} evaluations")
    return hits, evals


# ── Phase 3: Alternative b-vectors with even k ────────────────────
def phase3_alt_b_vectors():
    """Try different b-vectors with a=[0, k, -2] for even k."""
    print("\n" + "=" * 70)
    print("  PHASE 3: Alternative b-vectors with even k")
    print("=" * 70)

    mp.dps = VERIFY_DPS + 20
    const_lib = rbg.build_constants(VERIFY_DPS)

    hits = []
    evals = 0

    b_candidates = [
        [1, 2], [1, 4], [1, 5], [1, 6], [1, 7],
        [2, 3], [2, 5], [3, 1], [3, 5],
        [1, 1, 1], [1, 2, 1], [1, 3, 1],
        [0, 1, 1],  # b(n) = n(n+1)
        [1, 0, 1],  # b(n) = n^2 + 1
    ]

    for b in b_candidates:
        print(f"\n  --- b={b} ---")
        for k in range(2, 26, 2):
            a = [0, k, -2]
            val = eval_cf(a, b, SCREEN_DPS, SCREEN_DEPTH)
            evals += 1
            if val is None:
                continue

            # Check rational
            rid = rational_identify(val)
            if rid:
                p, q, digits = rid
                if digits > TOLERANCE:
                    print(f"    a={a} b={b}  = {p}/{q}  ({digits:.1f}d)")
                    record = {
                        "a": a, "b": b,
                        "match": f"{p}/{q}",
                        "verified_digits": round(digits, 1),
                        "type": "even_k_alt_b_rational",
                        "k": k,
                        "shard": "even-k-alt-b",
                        "timestamp": datetime.now().isoformat(),
                    }
                    hits.append(record)
                    log_discovery(record)
                    continue

            # Check transcendental
            match, digits = match_against_constants(val, const_lib)
            if digits > TOLERANCE:
                val_hp = eval_cf(a, b, VERIFY_DPS, VERIFY_DEPTH)
                if val_hp is not None:
                    match_hp, digits_hp = match_against_constants(val_hp, const_lib)
                    if digits_hp > TOLERANCE:
                        print(f"    a={a} b={b}  ≈ {match_hp}  ({digits_hp:.1f}d)")
                        record = {
                            "a": a, "b": b,
                            "match": match_hp,
                            "verified_digits": round(digits_hp, 1),
                            "type": "even_k_alt_b_transcendental",
                            "k": k,
                            "shard": "even-k-alt-b",
                            "timestamp": datetime.now().isoformat(),
                        }
                        hits.append(record)
                        log_discovery(record)

    print(f"\n  Phase 3 summary: {len(hits)} hits from {evals} evaluations")
    return hits, evals


# ── Phase 4: Search new rational families ──────────────────────────
def phase4_new_rational_families():
    """Broader search for CFs converging to rationals outside the known family."""
    print("\n" + "=" * 70)
    print("  PHASE 4: Search for new rational PCF families")
    print("=" * 70)

    rng = random.Random(SEED)
    hits = []
    evals = 0

    # Systematic grid: quadratic a, linear b
    a_ranges = {
        "a0": range(-4, 5),
        "a1": range(-8, 12),  # focus on even values
        "a2": [-4, -3, -2, -1, 1, 2, 3, 4],
    }
    b_ranges = {
        "b0": [1, 2, 3, 4, 5],
        "b1": [1, 2, 3, 4, 5, 6, 7],
    }

    configs = []
    for a0 in a_ranges["a0"]:
        for a1 in a_ranges["a1"]:
            if a1 % 2 != 0:
                continue  # focus on even k (a1)
            for a2 in a_ranges["a2"]:
                for b0 in b_ranges["b0"]:
                    for b1 in b_ranges["b1"]:
                        configs.append(([a0, a1, a2], [b0, b1]))

    rng.shuffle(configs)
    total = len(configs)
    print(f"  Grid: {total:,} configs (even a1 only)")

    batch_size = 2000
    for i, (a, b) in enumerate(configs):
        # Skip the base family (already covered)
        if a[0] == 0 and a[2] == -2 and b == [1, 3]:
            continue

        val = eval_cf(a, b, SCREEN_DPS, SCREEN_DEPTH)
        evals += 1
        if val is None:
            continue

        # Rational identification
        rid = rational_identify(val, max_denom=5000)
        if rid:
            p, q, digits = rid
            if digits > TOLERANCE and q > 1:
                # Not trivially integer — verify
                val_hp = eval_cf(a, b, VERIFY_DPS, VERIFY_DEPTH)
                if val_hp is not None:
                    rid2 = rational_identify(val_hp, max_denom=5000)
                    if rid2 and rid2[2] > TOLERANCE:
                        # Skip telescoping
                        if rbg.is_telescoping(list(a), list(b)):
                            continue
                        p2, q2, d2 = rid2
                        print(f"  *** NEW RATIONAL: a={a} b={b}  = {p2}/{q2}  ({d2:.1f}d)")
                        record = {
                            "a": a, "b": b,
                            "match": f"{p2}/{q2}",
                            "verified_digits": round(d2, 1),
                            "type": "new_rational_family",
                            "shard": "even-k-new",
                            "timestamp": datetime.now().isoformat(),
                        }
                        hits.append(record)
                        log_discovery(record)

        # Progress
        if (i + 1) % batch_size == 0:
            elapsed = time.time() - t_global
            rate = evals / elapsed if elapsed > 0 else 0
            pct = 100 * (i + 1) / total
            print(f"  [{pct:5.1f}%] eval={evals:,} hits={len(hits)} [{rate:.0f}/s]")
            write_status(evals, len(hits), 0, ("", 0) if not hits else
                         (hits[-1]["match"], hits[-1]["verified_digits"]),
                         "phase4", elapsed)

    print(f"\n  Phase 4 summary: {len(hits)} new rational families from {evals} evals")
    return hits, evals


# ── Main ───────────────────────────────────────────────────────────
t_global = 0

def main():
    global t_global
    t_global = time.time()

    print("Even-k Sweep: Exploring the Rational Branch")
    print(f"  Screen: {SCREEN_DPS}dps / depth {SCREEN_DEPTH}")
    print(f"  Verify: {VERIFY_DPS}dps / depth {VERIFY_DEPTH}")
    print(f"  HP: {HP_DPS}dps")
    print(f"  Tolerance: {TOLERANCE}d")
    print(f"  Log: {LOGFILE}")
    print()

    total_evals = 0
    total_hits = 0

    # Phase 1
    t1 = time.time()
    p1_results = phase1_verify_rationals()
    total_hits += len(p1_results)
    write_status(len(p1_results), total_hits, 0,
                 (p1_results[-1]["match"], p1_results[-1]["verified_digits"])
                 if p1_results else ("", 0),
                 "phase1", time.time() - t_global)

    # Phase 2
    t2 = time.time()
    p2_hits, p2_evals = phase2_perturbations()
    total_evals += p2_evals
    total_hits += len(p2_hits)
    write_status(total_evals, total_hits, 0,
                 (p2_hits[-1]["match"], p2_hits[-1]["verified_digits"])
                 if p2_hits else ("", 0),
                 "phase2", time.time() - t_global)

    # Phase 3
    t3 = time.time()
    p3_hits, p3_evals = phase3_alt_b_vectors()
    total_evals += p3_evals
    total_hits += len(p3_hits)
    write_status(total_evals, total_hits, 0,
                 (p3_hits[-1]["match"], p3_hits[-1]["verified_digits"])
                 if p3_hits else ("", 0),
                 "phase3", time.time() - t_global)

    # Phase 4
    t4 = time.time()
    p4_hits, p4_evals = phase4_new_rational_families()
    total_evals += p4_evals
    total_hits += len(p4_hits)

    elapsed = time.time() - t_global
    write_status(total_evals, total_hits, 0,
                 ("done", 0), "complete", elapsed)

    print("\n" + "=" * 70)
    print(f"  EVEN-K SWEEP COMPLETE  ({elapsed:.0f}s)")
    print(f"  Total evaluations: {total_evals:,}")
    print(f"  Total discoveries: {total_hits}")
    print(f"    Phase 1 (verify):      {len(p1_results)}")
    print(f"    Phase 2 (perturb):     {len(p2_hits)}")
    print(f"    Phase 3 (alt b):       {len(p3_hits)}")
    print(f"    Phase 4 (new family):  {len(p4_hits)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
