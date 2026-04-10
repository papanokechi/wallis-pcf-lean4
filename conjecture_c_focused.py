#!/usr/bin/env python3
"""
Conjecture C — Focused Test (Fast Version)
═══════════════════════════════════════════

Instead of brute-forcing all beta coefficients, this script:
1. Confirms which k values already have n-2 alpha in the catalog
2. Uses the KNOWN beta patterns from the catalog to predict betas
   for untested k values (zeta6, zeta8)
3. Runs a focused small search for the gap cases

The key insight from the alpha-shape analysis:
  - slope=-1 family (a(n) = c + (-1)*n) has 8 instances for zeta5
  - For k(n-2), the known betas are {[-2,4], [-5,0], [5,0], [-8,6], ...}
  - These are ALL linear or have small coefficients
  => Restrict search to |coeff| <= 8 for bdeg<=2
"""

import json
import time
import mpmath as mp

SEARCH_DPS = 300
CF_DEPTH = 300
VERIFY_DPS = 1000
VERIFY_DEPTH = 800
PSLQ_COEFF = 10000


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


def test_pslq(cf_val, target_val, dps):
    """Test PSLQ relation. Returns (found, relation, digits) or (False, None, 0)."""
    with mp.workdps(dps):
        cf = mp.mpf(cf_val)
        tgt = mp.mpf(target_val)
        rel = mp.pslq([cf, tgt, mp.mpf(1)], maxcoeff=PSLQ_COEFF, maxsteps=2000)
        if rel and rel[0] != 0 and rel[1] != 0:
            dot = abs(rel[0]*cf + rel[1]*tgt + rel[2])
            rd = max(0, int(-float(mp.log10(dot)))) if dot > 0 else dps
            if rd >= 50:
                return True, [int(x) for x in rel], rd
    return False, None, 0


def main():
    print("=" * 70)
    print("  CONJECTURE C — FOCUSED TEST")
    print("=" * 70)

    # ── Step 1: Check catalog for existing n-2 alpha entries ────────
    print("\n  [1/3] Scanning catalog for alpha ~ k(n-2) entries...")

    with open("discovery_catalog.json") as f:
        catalog = json.load(f)

    # Find entries where alpha has a root at n=2
    n2_entries = {}
    for d in catalog:
        alpha = d.get("alpha", [])
        # Check if a(2) = 0
        a_at_2 = sum(c * (2**i) for i, c in enumerate(alpha))
        if a_at_2 == 0 and len(alpha) >= 2:
            target = d.get("target", "?")
            if target not in n2_entries:
                n2_entries[target] = []
            n2_entries[target].append({
                "alpha": alpha, "beta": d.get("beta", []),
                "closed_form": d.get("closed_form", ""),
            })

    print(f"  Found alpha with root at n=2 in catalog:")
    for tgt, entries in sorted(n2_entries.items()):
        print(f"    {tgt}: {len(entries)} entries")
        for e in entries[:3]:
            print(f"      a={e['alpha']}, b={e['beta']} -> CF={e['closed_form']}")

    confirmed_k = set()
    for tgt in n2_entries:
        # Map target name to k
        if tgt.startswith("zeta"):
            try:
                k = int(tgt[4:])
                confirmed_k.add(k)
            except ValueError:
                pass
        elif tgt == "pi2":
            confirmed_k.add(-2)  # pi^2 = 6*zeta(2), so related

    print(f"\n  k values with root-at-2 alpha: {sorted(confirmed_k)}")
    missing_k = [k for k in range(2, 10) if k not in confirmed_k]
    print(f"  Missing k values: {missing_k}")

    # ── Step 2: Focused search for missing k ────────────────────────
    print(f"\n  [2/3] Focused search for missing k values...")

    mp.mp.dps = SEARCH_DPS
    targets = {}
    with mp.workdps(SEARCH_DPS + 50):
        for k in range(2, 10):
            targets[k] = mp.zeta(k)

    # Alpha variants
    alphas = [
        [-2, 1],        # a(n) = n-2
        [-2, 1, 0],     # a(n) = (n-2), padded
        [-4, 2],        # a(n) = 2(n-2)
        [-6, 3],        # a(n) = 3(n-2)
        [-8, 4],        # a(n) = 4(n-2)
        [8, -2, -1],    # a(n) = -(n-2)(n+4) = 8-2n-n^2
        [2, -1, 2, -1], # a(n) = -(n-2)(n^2-1) [has root at 2]
    ]

    # Beta grid: focused on small coefficients
    beta_candidates = []
    for b0 in range(-8, 9):
        for b1 in range(-8, 9):
            beta_candidates.append([b0, b1])   # bdeg=1
    for b0 in range(-6, 7):
        for b1 in range(-6, 7):
            for b2 in range(-4, 5):
                if b2 == 0:
                    continue
                beta_candidates.append([b0, b1, b2])  # bdeg=2

    new_hits = {}

    for k in missing_k + sorted(confirmed_k):  # test missing first, then confirm
        tval = targets[k]
        tname = f"zeta({k})"
        hits = []

        t0 = time.time()
        tested = 0
        for alpha in alphas:
            for beta in beta_candidates:
                tested += 1
                try:
                    v = eval_backward(alpha, beta, CF_DEPTH, SEARCH_DPS)
                except Exception:
                    continue
                if mp.isnan(v) or mp.isinf(v) or abs(v) > 1e12 or abs(v) < 1e-12:
                    continue
                found, rel, rd = test_pslq(v, tval, SEARCH_DPS)
                if found:
                    hits.append({
                        "alpha": alpha, "beta": beta,
                        "relation": rel, "digits": rd,
                        "cf_approx": mp.nstr(v, 15),
                    })
                    if k in missing_k:  # Print immediately for missing k
                        print(f"    k={k} HIT: a={alpha} b={beta} -> CF={mp.nstr(v,10)} ({rd}dp)")

        elapsed = time.time() - t0
        new_hits[k] = hits
        status = "FOUND" if hits else "NOT FOUND"
        print(f"  k={k}: {status} ({len(hits)} hits, {tested} tested, {elapsed:.1f}s)")

    # ── Step 3: High-precision verification of new discoveries ──────
    print(f"\n  [3/3] High-precision verification of new discoveries...")

    mp.mp.dps = VERIFY_DPS
    verify_targets = {}
    with mp.workdps(VERIFY_DPS + 50):
        for k in range(2, 10):
            verify_targets[k] = mp.zeta(k)

    verified = {}
    for k, hits in new_hits.items():
        if not hits:
            continue
        for h in hits[:2]:  # verify top 2 per k
            alpha = h["alpha"]
            beta = h["beta"]
            v1 = eval_backward(alpha, beta, CF_DEPTH, VERIFY_DPS)
            v2 = eval_backward(alpha, beta, VERIFY_DEPTH, VERIFY_DPS)
            if mp.isnan(v1) or mp.isnan(v2):
                continue
            with mp.workdps(VERIFY_DPS):
                diff = abs(v1 - v2)
                sa = max(0, int(-float(mp.log10(diff)))) if diff > 0 else VERIFY_DPS
                found, rel, rd = test_pslq(v2, verify_targets[k], VERIFY_DPS)
                if found and rd >= 200:
                    verified[k] = {"alpha": alpha, "beta": beta,
                                   "relation": rel, "digits": rd,
                                   "self_agree": sa}
                    print(f"  k={k}: VERIFIED at {rd} digits (sa={sa})")
                    print(f"    a={alpha}, b={beta}")
                    print(f"    {rel[0]}*CF + {rel[1]}*zeta({k}) + {rel[2]} = 0")
                    break

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"  CONJECTURE C TEST RESULTS")
    print(f"{'='*70}")

    all_k = sorted(set(list(confirmed_k) + list(new_hits.keys())))
    for k in range(2, 10):
        in_catalog = k in confirmed_k
        in_search = k in new_hits and len(new_hits[k]) > 0
        in_verified = k in verified
        if in_verified:
            status = "VERIFIED (1000dp)"
        elif in_search:
            status = "FOUND (300dp)"
        elif in_catalog:
            status = "IN CATALOG (root-at-2 alpha)"
        else:
            status = "NOT FOUND"
        print(f"  k={k} (zeta({k})): {status}")

    supported = [k for k in range(2, 10) if k in confirmed_k or (k in new_hits and new_hits[k])]
    not_found = [k for k in range(2, 10) if k not in supported]

    print(f"\n  Supported: k in {supported}")
    if not_found:
        print(f"  Not found: k in {not_found}")
        print(f"\n  CONJECTURE STATUS: PARTIALLY SUPPORTED")
        print(f"  May need deg(beta) > 2 for k in {not_found}")
    else:
        print(f"\n  CONJECTURE STATUS: FULLY SUPPORTED for k=2..9")

    # Save
    results = {
        "confirmed_from_catalog": sorted(confirmed_k),
        "search_results": {str(k): {"hits": len(h), "details": h}
                           for k, h in new_hits.items()},
        "verified": {str(k): v for k, v in verified.items()},
    }
    with open("conjecture_c_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved to conjecture_c_results.json")


if __name__ == "__main__":
    main()
