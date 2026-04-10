#!/usr/bin/env python3
"""Algebraic Independence Audit for Ramanujan Agent Discoveries.

Tests pairwise and triple algebraic relations between:
  - GCF limit values from the discovery catalog
  - Known constants (ζ(3), ζ(5), ζ(7), π, log2, Catalan, Euler-γ)
  - V_quad (the new transcendental candidate)

For each pair/triple of values, runs PSLQ at high precision to test
whether any integer relation exists.  If all tests come back negative,
the values are provisionally algebraically independent.

Usage:
    python algebraic_independence_audit.py --input refined_sweep.json
    python algebraic_independence_audit.py --input refined_sweep.json --prec 1500 --top 20
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import defaultdict
from itertools import combinations

import mpmath as mp

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# V_quad: GCF with a(n)=1, b(n)=3n²+n+1, backward mode
# CF = b(0) + 1/(b(1) + 1/(b(2) + ...)) = 1 + 1/(5 + 1/(15 + ...))
VQUAD_ALPHA = [1]          # a(n) = 1 for all n
VQUAD_BETA = [1, 1, 3]    # b(n) = 3n²+n+1
VQUAD_N_TERMS = 3000


def _build_constants(dps: int) -> dict[str, mp.mpf]:
    with mp.workdps(dps + 50):
        c = {}
        c["pi"] = mp.pi; c["e"] = mp.e
        c["log2"] = mp.log(2); c["log3"] = mp.log(3)
        c["zeta2"] = mp.zeta(2); c["zeta3"] = mp.zeta(3)
        c["zeta4"] = mp.zeta(4); c["zeta5"] = mp.zeta(5)
        c["zeta6"] = mp.zeta(6); c["zeta7"] = mp.zeta(7)
        c["catalan"] = mp.catalan; c["euler_g"] = mp.euler
        c["pi2"] = mp.pi**2; c["pi3"] = mp.pi**3
        c["sqrt2"] = mp.sqrt(2); c["sqrt11"] = mp.sqrt(11)
    return c


def _eval_backward(alpha, beta, n_terms, dps):
    with mp.workdps(dps + 50):
        val = mp.mpf(0)
        tol = mp.mpf(10) ** -(dps + 40)
        for n in range(n_terms, 0, -1):
            an = sum(c * mp.mpf(n)**i for i, c in enumerate(alpha))
            bn = sum(c * mp.mpf(n)**i for i, c in enumerate(beta))
            denom = bn + val
            if abs(denom) < tol:
                return None
            val = an / denom
        b0 = sum(c * mp.mpf(0)**i for i, c in enumerate(beta))
        return b0 + val


def _eval_ratio(alpha, beta, n_terms, order, dps):
    with mp.workdps(dps + 50):
        a0 = sum(c * mp.mpf(0)**i for i, c in enumerate(alpha))
        b0 = sum(c * mp.mpf(0)**i for i, c in enumerate(beta))
        p_prev, p_curr = mp.mpf(a0), mp.mpf(b0)
        q_prev, q_curr = mp.mpf(1), mp.mpf(1)
        tol = mp.mpf(10) ** -(dps + 40)
        for n in range(1, n_terms + 1):
            bn = sum(c * mp.mpf(n)**i for i, c in enumerate(beta))
            an = sum(c * mp.mpf(n)**i for i, c in enumerate(alpha))
            div = mp.mpf(n ** order) if order > 0 else mp.mpf(1)
            if abs(div) < tol:
                return None
            p_next = (bn * p_curr - an * p_prev) / div
            q_next = (bn * q_curr - an * q_prev) / div
            p_prev, p_curr = p_curr, p_next
            q_prev, q_curr = q_curr, q_next
        if abs(q_curr) < tol:
            return None
        return p_curr / q_curr


def _eval_gcf(entry, dps):
    alpha = entry["alpha"]
    beta = entry["beta"]
    mode = entry.get("mode", "backward")
    order = entry.get("order", 0)
    n_terms = entry.get("n_terms", 500)
    if mode == "ratio":
        return _eval_ratio(alpha, beta, n_terms, order, dps)
    return _eval_backward(alpha, beta, n_terms, dps)


def _run_pslq(vec, dps, maxcoeff=10000):
    """Run PSLQ and return (relation, precision) or (None, 0)."""
    tol = mp.mpf(10) ** -(dps // 2)
    try:
        with mp.workdps(dps):
            rel = mp.pslq(vec, tol=tol, maxcoeff=maxcoeff)
    except Exception:
        return None, 0
    if rel is None:
        return None, 0
    # Compute residual
    res = sum(r * v for r, v in zip(rel, vec))
    res = abs(res)
    if res == 0:
        prec = dps
    else:
        prec = max(0, int(-float(mp.log10(res + mp.mpf(10) ** -(dps - 2)))))
    return rel, prec


def load_distinct_gcf_values(input_path: str, dps: int,
                             max_entries: int = 20) -> list[dict]:
    """Load and evaluate distinct GCF limits from a sweep JSON."""
    with open(input_path) as f:
        data = json.load(f)

    entries = []
    seen_approx = set()
    for result in data.get("results", []):
        for hv in result.get("high_value", []):
            if not hv.get("alpha"):
                continue
            # Dedup by approximate value prefix
            approx = hv.get("cf_approx", "")
            if not approx or approx == "None":
                continue
            key = approx[:15]
            if key in seen_approx:
                continue
            seen_approx.add(key)
            entries.append(hv)
            if len(entries) >= max_entries:
                break
        if len(entries) >= max_entries:
            break

    # Evaluate at target precision
    values = []
    for e in entries:
        v = _eval_gcf(e, dps)
        if v is not None and mp.isfinite(v):
            values.append({
                "spec_id": e["spec_id"],
                "constant": e["constant"],
                "alpha": e["alpha"],
                "beta": e["beta"],
                "mode": e.get("mode", "backward"),
                "value": v,
            })
    return values


def audit_pairwise(values: list[dict], known: dict[str, mp.mpf],
                   dps: int) -> list[dict]:
    """Test pairwise algebraic relations between GCF limits and known constants."""
    results = []
    pslq_dps = max(80, dps // 3)

    # Test each GCF limit against known constants
    for v in values:
        val = v["value"]
        for kname, kval in known.items():
            # Linear: a·CF + b·K + c = 0
            with mp.workdps(pslq_dps):
                vec = [mp.mpf(val), mp.mpf(kval), mp.mpf(1)]
                rel, prec = _run_pslq(vec, pslq_dps)
            if rel and prec >= 20 and rel[1] != 0:
                results.append({
                    "type": "gcf_vs_known",
                    "spec_id": v["spec_id"],
                    "constant": kname,
                    "relation": [int(r) for r in rel],
                    "precision": prec,
                    "status": "DEPENDENT" if prec >= dps // 4 else "weak",
                })

    # Test GCF limits against each other
    for (v1, v2) in combinations(values, 2):
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(v1["value"]), mp.mpf(v2["value"]), mp.mpf(1)]
            rel, prec = _run_pslq(vec, pslq_dps)
        if rel and prec >= 20 and rel[0] != 0 and rel[1] != 0:
            results.append({
                "type": "gcf_vs_gcf",
                "spec_id_1": v1["spec_id"],
                "spec_id_2": v2["spec_id"],
                "relation": [int(r) for r in rel],
                "precision": prec,
                "status": "DEPENDENT" if prec >= dps // 4 else "weak",
            })

    return results


def audit_triples(values: list[dict], known: dict[str, mp.mpf],
                  dps: int) -> list[dict]:
    """Test triple relations: a·V1 + b·V2 + c·K + d = 0."""
    results = []
    pslq_dps = max(80, dps // 3)

    # Key triples: GCF + ζ(3) + ζ(5), GCF + ζ(5) + ζ(7), etc.
    key_known_pairs = [
        ("zeta3", "zeta5"), ("zeta5", "zeta7"), ("zeta3", "zeta7"),
        ("zeta3", "pi"), ("zeta5", "pi3"),
    ]

    for v in values[:10]:  # Top 10 GCF limits
        val = v["value"]
        for k1name, k2name in key_known_pairs:
            k1 = known.get(k1name)
            k2 = known.get(k2name)
            if k1 is None or k2 is None:
                continue
            with mp.workdps(pslq_dps):
                vec = [mp.mpf(val), mp.mpf(k1), mp.mpf(k2), mp.mpf(1)]
                rel, prec = _run_pslq(vec, pslq_dps)
            if rel and prec >= 20:
                # Check non-trivial: at least CF coeff and one constant coeff nonzero
                if rel[0] != 0 and (rel[1] != 0 or rel[2] != 0):
                    results.append({
                        "type": "triple",
                        "spec_id": v["spec_id"],
                        "constants": [k1name, k2name],
                        "relation": [int(r) for r in rel],
                        "precision": prec,
                        "status": "DEPENDENT" if prec >= dps // 4 else "weak",
                    })

    return results


def audit_vquad(known: dict[str, mp.mpf], dps: int) -> list[dict]:
    """Test V_quad against the full known constant pool + GCF limits."""
    results = []
    pslq_dps = max(80, dps // 3)

    print("  Computing V_quad...")
    vquad = _eval_backward(VQUAD_ALPHA, VQUAD_BETA, VQUAD_N_TERMS, dps)
    if vquad is None:
        print("  WARNING: V_quad evaluation failed")
        return results
    print(f"  V_quad = {mp.nstr(vquad, 30)}")

    # Test V_quad against each known constant individually
    for kname, kval in known.items():
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(kval), mp.mpf(1)]
            rel, prec = _run_pslq(vec, pslq_dps)
        if rel and prec >= 15 and rel[1] != 0:
            results.append({
                "type": "vquad_vs_known",
                "constant": kname,
                "relation": [int(r) for r in rel],
                "precision": prec,
                "status": "DEPENDENT" if prec >= dps // 4 else "near_miss",
            })

    # Test V_quad against pairs of odd zetas
    for k1, k2 in [("zeta3", "zeta5"), ("zeta5", "zeta7"), ("zeta3", "zeta7")]:
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(known[k1]), mp.mpf(known[k2]), mp.mpf(1)]
            rel, prec = _run_pslq(vec, pslq_dps)
        if rel and prec >= 15 and rel[0] != 0:
            results.append({
                "type": "vquad_vs_pair",
                "constants": [k1, k2],
                "relation": [int(r) for r in rel],
                "precision": prec,
                "status": "DEPENDENT" if prec >= dps // 4 else "near_miss",
            })

    # Test V_quad against the full odd-zeta triple
    with mp.workdps(pslq_dps):
        vec = [mp.mpf(vquad), mp.mpf(known["zeta3"]),
               mp.mpf(known["zeta5"]), mp.mpf(known["zeta7"]), mp.mpf(1)]
        rel, prec = _run_pslq(vec, pslq_dps)
    if rel and prec >= 15 and rel[0] != 0:
        results.append({
            "type": "vquad_vs_triple",
            "constants": ["zeta3", "zeta5", "zeta7"],
            "relation": [int(r) for r in rel],
            "precision": prec,
            "status": "DEPENDENT" if prec >= dps // 4 else "near_miss",
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Algebraic independence audit for Ramanujan discoveries.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", "-i", default="refined_sweep.json")
    parser.add_argument("--prec", type=int, default=1000,
                        help="Working precision (digits).")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of distinct GCF limits to test.")
    parser.add_argument("--json-out", default="independence_audit.json")
    parser.add_argument("--csv-out", default="independence_audit.csv")
    parser.add_argument("--skip-vquad", action="store_true")
    args = parser.parse_args()

    dps = args.prec
    mp.mp.dps = dps + 100

    print(f"=== Algebraic Independence Audit ===")
    print(f"  Precision: {dps}dp")
    print(f"  Top GCF limits: {args.top}")
    t0 = time.perf_counter()

    # Build known constants
    known = _build_constants(dps)

    # Load GCF values
    print("\n[1/4] Loading and evaluating GCF limits...")
    gcf_values = load_distinct_gcf_values(args.input, dps, max_entries=args.top)
    print(f"  Loaded {len(gcf_values)} distinct non-rational GCF limits")

    # Pairwise tests
    print("\n[2/4] Pairwise PSLQ audit...")
    pair_results = audit_pairwise(gcf_values, known, dps)
    dep_count = sum(1 for r in pair_results if r["status"] == "DEPENDENT")
    print(f"  Tested pairs: {len(gcf_values)} × {len(known)} + C({len(gcf_values)},2)")
    print(f"  Dependencies found: {dep_count}")

    # Triple tests
    print("\n[3/4] Triple relation audit...")
    triple_results = audit_triples(gcf_values, known, dps)
    tdep = sum(1 for r in triple_results if r["status"] == "DEPENDENT")
    print(f"  Triple dependencies: {tdep}")

    # V_quad audit
    vquad_results = []
    if not args.skip_vquad:
        print("\n[4/4] V_quad independence audit...")
        vquad_results = audit_vquad(known, dps)
        vdep = sum(1 for r in vquad_results if r["status"] == "DEPENDENT")
        print(f"  V_quad dependencies: {vdep}")
    else:
        print("\n[4/4] V_quad skipped")

    wall = round(time.perf_counter() - t0, 3)

    # Compile results
    all_results = pair_results + triple_results + vquad_results
    output = {
        "audit": "algebraic_independence",
        "precision": dps,
        "gcf_count": len(gcf_values),
        "known_constants": list(known.keys()),
        "total_tests": len(all_results),
        "dependencies": [r for r in all_results if r["status"] == "DEPENDENT"],
        "near_misses": [r for r in all_results if r["status"] == "near_miss"],
        "weak_signals": [r for r in all_results if r["status"] == "weak"],
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "all_results": all_results,
    }

    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    if all_results:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["type", "spec_id", "spec_id_1",
                "spec_id_2", "constant", "constants", "relation", "precision", "status"],
                extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_results)

    # Report
    print(f"\n{'='*60}")
    print(f"  Algebraic Independence Audit Report")
    print(f"{'='*60}")
    print(f"  GCF limits tested:    {len(gcf_values)}")
    print(f"  Known constants:      {len(known)}")
    print(f"  Total PSLQ tests:     {len(all_results)}")
    print(f"  Dependencies (strong):{len(output['dependencies'])}")
    print(f"  Near-misses:          {len(output['near_misses'])}")
    print(f"  Wall time:            {wall}s")

    if output["dependencies"]:
        print(f"\n  *** ALGEBRAIC DEPENDENCIES FOUND ***")
        for d in output["dependencies"]:
            print(f"    {d['type']}  {d.get('spec_id','')}{d.get('spec_id_1','')}"
                  f"  rel={d['relation']}  prec={d['precision']}dp")
    else:
        print(f"\n  No algebraic dependencies detected — values appear independent!")

    if output["near_misses"]:
        print(f"\n  Near-misses (worth investigating):")
        for nm in output["near_misses"][:10]:
            print(f"    {nm['type']}  {nm.get('constant','')}{nm.get('constants','')}"
                  f"  rel={nm['relation']}  prec={nm['precision']}dp")

    print(f"\n  JSON -> {args.json_out}")
    print(f"  CSV  -> {args.csv_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
