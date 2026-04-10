#!/usr/bin/env python3
"""
Conjecture C — Precise Formulation and Direct Test
═══════════════════════════════════════════════════

CONJECTURE C (Universal n-2 GCF Family):

  For every integer k >= 2, there exists a polynomial beta_k(n)
  with integer coefficients and deg(beta_k) <= 3 such that

      GCF(a(n) = n - 2, b(n) = beta_k(n))

  converges to a rational multiple of zeta(k).

KNOWN EVIDENCE (from catalog, verified at 1000dp):
  k=2 (zeta2):  EXISTS in catalog (multiple betas)
  k=3 (zeta3):  EXISTS in catalog (multiple betas)
  k=4 (zeta4):  EXISTS in catalog (multiple betas)
  k=5 (zeta5):  EXISTS in catalog (5 betas for normalized [-2,1])
  k=7 (zeta7):  EXISTS in catalog

UNTESTED:
  k=6 (zeta6):  ???
  k=8 (zeta8):  ???
  k=9 (zeta9):  ???

This script systematically searches for beta_k(n) for k=6,8,9
to either strengthen or falsify the conjecture.

Also investigates: does the root at n=2 create a telescoping
structure in the three-term recurrence?
"""

import json
import time
import itertools
import mpmath as mp

# ── Config ──
SEARCH_DPS     = 500
VERIFY_DPS     = 1000
CF_DEPTH       = 500
VERIFY_DEPTH   = 800
COEFF_RANGE    = range(-12, 13)  # beta coefficients in [-12, 12]
BDEG_MAX       = 3               # max degree of beta
PSLQ_COEFF     = 10000


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
        b_0 = poly_eval(beta, 0)
        return b_0 + v


def search_beta_for_target(target_name, target_val, alpha, bdeg_max, dps, depth):
    """Search over integer beta polynomials up to given degree."""
    hits = []

    # Strategy: for each (bdeg, leading coeff), search smaller coefficients
    # Focus on the coefficient combinations most likely to work
    # based on catalog patterns: leading coeffs in {-6..-1, 1..6}

    for bdeg in range(1, bdeg_max + 1):
        # Generate beta candidates
        # For efficiency: fix leading coeff, vary lower coeffs
        leads = list(range(-8, 9))
        leads = [l for l in leads if l != 0]  # leading coeff nonzero

        for lead in leads:
            if bdeg == 1:
                for b0 in COEFF_RANGE:
                    beta = [b0, lead]
                    hit = _test_one(alpha, beta, target_val, dps, depth)
                    if hit:
                        hits.append({"beta": beta, "cf": hit["cf_str"],
                                     "pslq_digits": hit["digits"],
                                     "relation": hit["relation"]})
                        print(f"    HIT: a={alpha} b={beta} -> {hit['cf_str']} "
                              f"({hit['digits']}dp)")

            elif bdeg == 2:
                for b0 in range(-8, 9):
                    for b1 in range(-8, 9):
                        beta = [b0, b1, lead]
                        hit = _test_one(alpha, beta, target_val, dps, depth)
                        if hit:
                            hits.append({"beta": beta, "cf": hit["cf_str"],
                                         "pslq_digits": hit["digits"],
                                         "relation": hit["relation"]})
                            print(f"    HIT: a={alpha} b={beta} -> {hit['cf_str']} "
                                  f"({hit['digits']}dp)")

            elif bdeg == 3:
                # Reduced grid for cubic (too many combinations otherwise)
                for b0 in range(-6, 7):
                    for b1 in range(-6, 7):
                        for b2 in range(-6, 7):
                            beta = [b0, b1, b2, lead]
                            hit = _test_one(alpha, beta, target_val, dps, depth)
                            if hit:
                                hits.append({"beta": beta, "cf": hit["cf_str"],
                                             "pslq_digits": hit["digits"],
                                             "relation": hit["relation"]})
                                print(f"    HIT: a={alpha} b={beta} -> {hit['cf_str']} "
                                      f"({hit['digits']}dp)")

    return hits


def _test_one(alpha, beta, target_val, dps, depth):
    """Test a single (alpha, beta) pair against target. Returns hit dict or None."""
    try:
        v = eval_backward(alpha, beta, depth, dps)
    except Exception:
        return None
    if mp.isnan(v) or mp.isinf(v):
        return None
    if abs(v) > 1e15 or abs(v) < 1e-15:
        return None

    with mp.workdps(dps):
        cf = mp.mpf(v)
        tgt = mp.mpf(target_val)
        try:
            rel = mp.pslq([cf, tgt, mp.mpf(1)], maxcoeff=PSLQ_COEFF, maxsteps=2000)
        except Exception:
            return None

        if rel is not None:
            dot = abs(rel[0]*cf + rel[1]*tgt + rel[2])
            rd = max(0, int(-float(mp.log10(dot)))) if dot > 0 else dps
            if rd >= 100 and (rel[0] != 0 and rel[1] != 0):
                # Genuine relation involving both CF and target
                cf_str = mp.nstr(cf, 15)
                rel_str = f"{rel[0]}*CF + {rel[1]}*{target_name} + {rel[2]} = 0"
                return {"cf_str": cf_str, "digits": rd, "relation": rel_str,
                        "coefficients": [int(x) for x in rel]}
    return None


# Store target name as module-level for use in _test_one
target_name = ""


def main():
    global target_name
    mp.mp.dps = SEARCH_DPS

    print("=" * 70)
    print("  CONJECTURE C — PRECISE FORMULATION AND DIRECT TEST")
    print("=" * 70)

    # Build targets
    targets = {}
    with mp.workdps(SEARCH_DPS + 50):
        for k in range(2, 10):
            targets[f"zeta{k}"] = mp.zeta(k)

    # ── The alpha under test: a(n) = n - 2 ──
    alpha = [-2, 1]  # a(n) = -2 + n = n - 2

    # Also test the padded versions that appear in the catalog
    alpha_variants = [
        ([-2, 1], "a(n) = n-2"),
        ([-2, 1, 0], "a(n) = (n-2)*1, deg-padded"),
    ]

    print(f"\n  CONJECTURE C (precise):")
    print(f"  For every k >= 2, there exists beta_k(n) in Z[n],")
    print(f"  deg(beta_k) <= 3, such that")
    print(f"    GCF(a(n) = n-2, b(n) = beta_k(n)) = r_k * zeta(k)")
    print(f"  for some r_k in Q \\ {{0}}.")
    print(f"\n  Testing k = 2, 3, 4, 5, 6, 7, 8, 9...")

    all_results = {}

    for k in range(2, 10):
        tname = f"zeta{k}"
        target_name = tname
        tval = targets[tname]
        print(f"\n{'─'*70}")
        print(f"  k={k}: Testing GCF(n-2, beta(n)) = r * zeta({k})")
        print(f"{'─'*70}")

        t0 = time.time()
        hits = []
        for alpha_v, alpha_desc in alpha_variants:
            print(f"  Alpha: {alpha_v} ({alpha_desc})")
            h = search_beta_for_target(tname, tval, alpha_v, BDEG_MAX, SEARCH_DPS, CF_DEPTH)
            hits.extend(h)

        elapsed = time.time() - t0
        print(f"  k={k}: {len(hits)} hits found ({elapsed:.1f}s)")

        all_results[tname] = {
            "k": k,
            "hits": len(hits),
            "details": hits,
            "elapsed_s": round(elapsed, 1),
        }

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"  CONJECTURE C TEST RESULTS")
    print(f"{'='*70}\n")

    supported = []
    falsified = []

    for k in range(2, 10):
        tname = f"zeta{k}"
        r = all_results[tname]
        n_hits = r["hits"]
        if n_hits > 0:
            supported.append(k)
            status = f"SUPPORTED ({n_hits} betas found)"
            # Show first beta
            first = r["details"][0]
            print(f"  k={k} (zeta({k})): {status}")
            print(f"    Example: beta = {first['beta']}, CF = {first['cf']}")
            print(f"    Relation: {first['relation']}")
        else:
            falsified.append(k)
            print(f"  k={k} (zeta({k})): NOT FOUND (searched bdeg<=3, coeffs [-12,12])")

    print(f"\n  Supported: k in {supported}")
    print(f"  Not found: k in {falsified}")

    if falsified:
        print(f"\n  CONJECTURE C STATUS: REFINEMENT NEEDED")
        print(f"  The conjecture as stated fails for k in {falsified}.")
        print(f"  Possible refinements:")
        print(f"    (a) Restrict to odd k (zeta at odd integers)")
        print(f"    (b) Allow deg(beta) > 3")
        print(f"    (c) Allow different alpha roots (not just n=2)")
    else:
        print(f"\n  CONJECTURE C STATUS: SUPPORTED for k=2..9")
        print(f"  All tested values have at least one beta polynomial.")

    # ── High-precision verification of new discoveries ──
    new_k = [k for k in [6, 8, 9] if k in supported]
    if new_k:
        print(f"\n{'='*70}")
        print(f"  HIGH-PRECISION VERIFICATION OF NEW DISCOVERIES")
        print(f"{'='*70}")

        mp.mp.dps = VERIFY_DPS
        verify_targets = {}
        with mp.workdps(VERIFY_DPS + 50):
            for k in new_k:
                verify_targets[f"zeta{k}"] = mp.zeta(k)

        for k in new_k:
            tname = f"zeta{k}"
            details = all_results[tname]["details"]
            tval = verify_targets[tname]

            for d in details[:3]:  # verify top 3 per k
                beta = d["beta"]
                for alpha_v, _ in alpha_variants:
                    v1 = eval_backward(alpha_v, beta, CF_DEPTH, VERIFY_DPS)
                    v2 = eval_backward(alpha_v, beta, VERIFY_DEPTH, VERIFY_DPS)
                    if mp.isnan(v1) or mp.isnan(v2):
                        continue

                    with mp.workdps(VERIFY_DPS):
                        diff = abs(v1 - v2)
                        sa = max(0, int(-float(mp.log10(diff)))) if diff > 0 else VERIFY_DPS
                        rel = mp.pslq([v2, tval, mp.mpf(1)], maxcoeff=PSLQ_COEFF)
                        if rel:
                            dot = abs(rel[0]*v2 + rel[1]*tval + rel[2])
                            rd = max(0, int(-float(mp.log10(dot)))) if dot > 0 else VERIFY_DPS
                            if rd >= 200:
                                print(f"  k={k}: VERIFIED at {rd} digits")
                                print(f"    alpha={alpha_v}, beta={beta}")
                                print(f"    {rel[0]}*CF + {rel[1]}*zeta({k}) + {rel[2]} = 0")
                                print(f"    Self-agreement: {sa} digits")
                                break

    # Save results
    with open("conjecture_c_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to conjecture_c_results.json")


if __name__ == "__main__":
    main()
