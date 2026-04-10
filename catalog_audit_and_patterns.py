#!/usr/bin/env python3
"""
Catalog Spot Audit + zeta(5) Pattern Analysis
══════════════════════════════════════════════

Two critical analyses before proceeding to (6,6):

Part 1: Spot-audit 30 random discoveries from the full 342 catalog
         at 1000dp to measure the true false-positive rate.

Part 2: Structural pattern analysis of the 117 zeta(5) discoveries
         across 22 polynomial signatures — looking for common recurrence
         structure that could be stated as a conjecture.
"""

import json
import os
import sys
import time
import random
import hashlib
from collections import Counter, defaultdict

import mpmath as mp

# ── Config ──
CATALOG_PATH = "discovery_catalog.json"
AUDIT_DPS = 1000
AUDIT_DEPTH_LOW = 500
AUDIT_DEPTH_HIGH = 800
AUDIT_SAMPLE_SIZE = 30
AUDIT_SEED = 42
REPORT_FILE = "audit_and_pattern_report.txt"


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


def eval_ratio(alpha, beta, order, depth, dps):
    with mp.workdps(dps + 50):
        u2 = mp.mpf(0)
        u1 = mp.mpf(1)
        v2 = mp.mpf(1)
        v1 = poly_eval(beta, 1)
        for n in range(2, depth + 1):
            p = poly_eval(beta, n)
            q = poly_eval(alpha, n)
            nk = mp.mpf(n) ** order
            u_n = (p * u1 - q * u2) / nk
            v_n = (p * v1 - q * v2) / nk
            u2, u1 = u1, u_n
            v2, v1 = v1, v_n
        if v1 == 0:
            return mp.nan
        return u1 / v1


def build_targets(dps):
    mp.mp.dps = dps + 50
    return {
        "zeta2": mp.zeta(2), "zeta3": mp.zeta(3), "zeta4": mp.zeta(4),
        "zeta5": mp.zeta(5), "zeta6": mp.zeta(6), "zeta7": mp.zeta(7),
        "pi": mp.pi, "pi2": mp.pi**2, "pi3": mp.pi**3,
        "e": mp.e, "log2": mp.log(2), "catalan": mp.catalan,
        "euler_g": mp.euler,
    }


def verify_one(d, targets, dps):
    """Verify a single discovery. Returns (status, details)."""
    alpha = d["alpha"]
    beta = d["beta"]
    mode = d.get("mode", "backward")
    order = d.get("order", 0)
    target_name = d.get("target", "unknown")
    closed_form = d.get("closed_form", "")

    try:
        if mode == "ratio" and order > 0:
            v1 = eval_ratio(alpha, beta, order, AUDIT_DEPTH_LOW, dps)
            v2 = eval_ratio(alpha, beta, order, AUDIT_DEPTH_HIGH, dps)
        else:
            v1 = eval_backward(alpha, beta, AUDIT_DEPTH_LOW, dps)
            v2 = eval_backward(alpha, beta, AUDIT_DEPTH_HIGH, dps)
    except Exception as e:
        return "ERROR", {"error": str(e)}

    if mp.isnan(v1) or mp.isnan(v2):
        return "DIVERGENT", {}

    with mp.workdps(dps):
        diff = abs(v1 - v2)
        self_agree = max(0, int(-float(mp.log10(diff)))) if diff > 0 else dps

    if target_name not in targets:
        return "NO_TARGET", {"self_agree": self_agree}

    target_val = targets[target_name]

    # Try PSLQ: [CF, target, 1]
    with mp.workdps(dps):
        cf = mp.mpf(v2)
        tgt = mp.mpf(target_val)
        rel = mp.pslq([cf, tgt, mp.mpf(1)], maxcoeff=10000, maxsteps=3000)
        if rel is not None:
            dot = abs(rel[0]*cf + rel[1]*tgt + rel[2])
            rd = max(0, int(-float(mp.log10(dot)))) if dot > 0 else dps
            if rd >= 100:
                return "VERIFIED", {"self_agree": self_agree, "pslq_digits": rd,
                                     "relation": [int(x) for x in rel]}

        # Try degree-2: [CF^2, CF*target, CF, target, 1]
        rel2 = mp.pslq([cf**2, cf*tgt, cf, tgt, mp.mpf(1)],
                        maxcoeff=10000, maxsteps=3000)
        if rel2 is not None:
            dot2 = abs(sum(c*b for c, b in zip(rel2, [cf**2, cf*tgt, cf, tgt, mp.mpf(1)])))
            rd2 = max(0, int(-float(mp.log10(dot2)))) if dot2 > 0 else dps
            if rd2 >= 100:
                return "VERIFIED_DEG2", {"self_agree": self_agree, "pslq_digits": rd2,
                                          "relation": [int(x) for x in rel2]}

    return "FALSE_POSITIVE", {"self_agree": self_agree, "cf_value": mp.nstr(v2, 20)}


# ═══════════════════════════════════════════════════════════════════
# PART 1: SPOT AUDIT
# ═══════════════════════════════════════════════════════════════════

def run_spot_audit():
    print("=" * 70)
    print("  PART 1: CATALOG SPOT AUDIT (30 random entries at 1000dp)")
    print("=" * 70)

    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    print(f"  Catalog size: {len(catalog)}")

    # Exclude the already-verified top 10 (we know those are fine)
    # Sample from the remaining entries
    rng = random.Random(AUDIT_SEED)
    candidates = [d for d in catalog if not d.get("verified", False)]
    if len(candidates) < AUDIT_SAMPLE_SIZE:
        candidates = catalog  # If most are unverified, sample from all

    sample = rng.sample(candidates, min(AUDIT_SAMPLE_SIZE, len(candidates)))
    print(f"  Sampled {len(sample)} entries for audit\n")

    mp.mp.dps = AUDIT_DPS
    targets = build_targets(AUDIT_DPS)

    results = {"VERIFIED": 0, "VERIFIED_DEG2": 0, "FALSE_POSITIVE": 0,
               "DIVERGENT": 0, "ERROR": 0, "NO_TARGET": 0}
    details = []

    for i, d in enumerate(sample, 1):
        fp = d.get("fingerprint", "?")[:12]
        tgt = d.get("target", "?")
        sig = d.get("signature", "?")
        t0 = time.time()
        status, info = verify_one(d, targets, AUDIT_DPS)
        elapsed = time.time() - t0
        results[status] = results.get(status, 0) + 1
        sa = info.get("self_agree", "?")
        pd = info.get("pslq_digits", "—")
        print(f"  [{i:2d}/{len(sample)}] {status:16s} {tgt:8s} {sig:40s} sa={sa} pslq={pd} ({elapsed:.1f}s)")
        details.append({"fingerprint": fp, "target": tgt, "signature": sig,
                        "status": status, **info})

    # Compute rates
    total = len(sample)
    verified = results["VERIFIED"] + results["VERIFIED_DEG2"]
    fp_count = results["FALSE_POSITIVE"]
    fp_rate = fp_count / total * 100 if total > 0 else 0

    print(f"\n  {'─'*60}")
    print(f"  AUDIT RESULTS ({total} sampled):")
    for status, count in sorted(results.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"    {count:3d}  {status}")
    print(f"\n  Verified:       {verified}/{total} ({verified/total*100:.1f}%)")
    print(f"  False positive: {fp_count}/{total} ({fp_rate:.1f}%)")
    print(f"  {'─'*60}")

    return details, results


# ═══════════════════════════════════════════════════════════════════
# PART 2: ZETA(5) PATTERN ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def run_zeta5_analysis():
    print(f"\n\n{'='*70}")
    print("  PART 2: ZETA(5) STRUCTURAL PATTERN ANALYSIS")
    print("=" * 70)

    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    z5 = [d for d in catalog if d.get("target") == "zeta5"]
    print(f"  Total zeta(5) discoveries: {len(z5)}")

    # ── Signature distribution ──
    sig_counts = Counter(d.get("signature", "?") for d in z5)
    print(f"\n  Signature distribution ({len(sig_counts)} unique):")
    for sig, count in sig_counts.most_common():
        print(f"    {count:4d}  {sig}")

    # ── Degree analysis ──
    print(f"\n  Degree analysis:")
    adegs = Counter(d.get("adeg", 0) for d in z5)
    bdegs = Counter(d.get("bdeg", 0) for d in z5)
    print(f"    adeg distribution: {dict(sorted(adegs.items()))}")
    print(f"    bdeg distribution: {dict(sorted(bdegs.items()))}")

    # ── Mode analysis ──
    modes = Counter(d.get("mode", "?") for d in z5)
    print(f"    mode distribution: {dict(modes)}")

    # ── Closed-form analysis: look for rational structure ──
    print(f"\n  Closed-form rational structure:")
    cf_values = []
    for d in z5:
        cf = d.get("closed_form", "")
        if cf and cf != "None":
            cf_values.append(cf)

    # Parse rationals
    numerators = []
    denominators = []
    for cf in cf_values:
        try:
            if "/" in str(cf):
                parts = str(cf).split("/")
                num, den = int(parts[0].strip()), int(parts[1].strip())
                numerators.append(abs(num))
                denominators.append(abs(den))
            elif str(cf).lstrip("-").replace(".", "").isdigit():
                v = float(cf)
                if v == int(v):
                    numerators.append(abs(int(v)))
                    denominators.append(1)
        except (ValueError, IndexError):
            pass

    if denominators:
        den_counts = Counter(denominators)
        print(f"    Denominator distribution:")
        for d, c in den_counts.most_common(10):
            print(f"      den={d:6d}: {c:3d} occurrences")

    if numerators:
        # Check for divisibility patterns
        print(f"\n    Numerator mod analysis:")
        for m in [2, 3, 5, 7, 11, 24]:
            residues = Counter(n % m for n in numerators)
            nontrivial = sum(1 for r in residues if residues[r] > len(numerators) * 0.3)
            if nontrivial <= 2:
                dominant = residues.most_common(2)
                print(f"      mod {m:2d}: dominant residues = {dominant}")

    # ── Beta polynomial leading coefficient analysis ──
    print(f"\n  Beta polynomial leading coefficient analysis:")
    lead_coeffs = []
    for d in z5:
        beta = d.get("beta", [])
        if beta:
            lead_coeffs.append(beta[-1])
    if lead_coeffs:
        lc_counts = Counter(lead_coeffs)
        print(f"    Leading coefficient distribution (top 10):")
        for lc, c in lc_counts.most_common(10):
            print(f"      lead={lc:6d}: {c:3d} occurrences")

    # ── Alpha polynomial pattern detection ──
    print(f"\n  Alpha polynomial pattern detection:")
    # Check if alpha polynomials share common factors or structures
    alpha_shapes = defaultdict(list)
    for d in z5:
        alpha = tuple(d.get("alpha", []))
        adeg = d.get("adeg", 0)
        # Normalize: divide by GCD of coefficients
        from math import gcd
        from functools import reduce
        nonzero = [abs(c) for c in alpha if c != 0]
        if nonzero:
            g = reduce(gcd, nonzero)
            normalized = tuple(c // g for c in alpha)
            alpha_shapes[normalized].append(d)

    # Find repeated shapes
    repeated = {shape: entries for shape, entries in alpha_shapes.items() if len(entries) >= 2}
    if repeated:
        print(f"    {len(repeated)} repeated alpha shapes found:")
        for shape, entries in sorted(repeated.items(), key=lambda x: -len(x[1]))[:10]:
            betas = [tuple(e.get("beta", [])) for e in entries]
            beta_set = set(betas)
            print(f"      alpha_norm={list(shape)} ({len(entries)}x, {len(beta_set)} distinct betas)")

    # ── Cross-signature structural conjecture ──
    print(f"\n  Cross-signature structural analysis:")
    # Group by bdeg and look for convergence rate patterns
    by_bdeg = defaultdict(list)
    for d in z5:
        by_bdeg[d.get("bdeg", 0)].append(d)

    for bdeg in sorted(by_bdeg.keys()):
        entries = by_bdeg[bdeg]
        rates = [d.get("convergence_rate", 0) for d in entries]
        avg_rate = sum(rates) / len(rates) if rates else 0
        print(f"    bdeg={bdeg}: {len(entries):3d} entries, avg_rate={avg_rate:.3f}")

    # ── Recurrence structure detection ──
    # Check if ratio a(n)/b(n) has common asymptotic behavior
    print(f"\n  Asymptotic ratio a(n)/b(n) behavior:")
    for d in z5[:5]:  # Sample
        alpha = d.get("alpha", [])
        beta = d.get("beta", [])
        adeg = d.get("adeg", 0)
        bdeg = d.get("bdeg", 0)
        if alpha and beta:
            a_lead = alpha[-1]
            b_lead = beta[-1]
            if b_lead != 0:
                ratio = a_lead / b_lead
                print(f"    a={alpha} b={beta} → a_lead/b_lead = {ratio:.4f} (deg {adeg}/{bdeg})")

    return z5


def main():
    report_lines = []

    # Part 1
    audit_details, audit_results = run_spot_audit()

    # Part 2
    z5_entries = run_zeta5_analysis()

    # ── Save report ──
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("  CATALOG SPOT AUDIT + ZETA(5) PATTERN ANALYSIS\n")
        f.write(f"  Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")

        f.write("PART 1: SPOT AUDIT\n")
        f.write(f"  Sample size: {len(audit_details)}\n")
        for status, count in sorted(audit_results.items(), key=lambda x: -x[1]):
            if count > 0:
                f.write(f"  {count:3d}  {status}\n")
        f.write("\n  Individual results:\n")
        for d in audit_details:
            f.write(f"    {d['fingerprint']:12s} {d['target']:8s} {d['signature']:40s} "
                    f"{d['status']}\n")

        f.write(f"\nPART 2: ZETA(5) ANALYSIS\n")
        f.write(f"  Total entries: {len(z5_entries)}\n")
        sig_counts = Counter(d.get("signature", "?") for d in z5_entries)
        f.write(f"  Unique signatures: {len(sig_counts)}\n")
        for sig, count in sig_counts.most_common():
            f.write(f"    {count:4d}  {sig}\n")

    print(f"\n  Report saved to {REPORT_FILE}")

    # ── Decision output ──
    total = len(audit_details)
    verified = audit_results.get("VERIFIED", 0) + audit_results.get("VERIFIED_DEG2", 0)
    fp_count = audit_results.get("FALSE_POSITIVE", 0)

    print(f"\n{'='*70}")
    print(f"  DECISION POINT")
    print(f"{'='*70}")
    if fp_count == 0:
        print(f"  Audit: {verified}/{total} verified, 0 false positives")
        print(f"  -> CATALOG IS CLEAN. Safe to proceed with (6,6) and independence.")
    elif fp_count / total < 0.10:
        print(f"  Audit: {verified}/{total} verified, {fp_count} false positives ({fp_count/total*100:.0f}%)")
        print(f"  -> LOW FP rate. Catalog usable with caveat. Recommend full scan.")
    else:
        print(f"  Audit: {verified}/{total} verified, {fp_count} false positives ({fp_count/total*100:.0f}%)")
        print(f"  -> HIGH FP rate. DO NOT proceed to independence analysis.")
        print(f"  -> Run full catalog verification first.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
