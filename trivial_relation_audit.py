#!/usr/bin/env python3
"""
Catalog Trivial-Relation Audit
══════════════════════════════

The zeta(6) singleton exposed a systematic issue: the sweep's PSLQ
can find "relations" like c1*CF*zeta(k) + c2*zeta(k) = 0 which are
trivially satisfied when CF is rational (CF = -c2/c1).

This script checks ALL catalog entries to:
1. Determine if CF converges to a rational number
2. If rational, verify the relation is non-trivial
3. Identify and flag false positives

A genuine zeta(k) discovery requires: the CF VALUE itself must be
transcendental (i.e., involve zeta(k) in an essential way).
"""

import json
import time
import mpmath as mp
from collections import Counter

CATALOG_PATH = "discovery_catalog.json"
CHECK_DPS = 200
CF_DEPTH = 300
REPORT_FILE = "trivial_relation_audit.txt"


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


def is_rational(val, dps):
    """Check if val is a rational p/q with small denominator."""
    with mp.workdps(dps):
        # Try to identify as p/q for q up to 10000
        for q in range(1, 10001):
            p = mp.nint(val * q)
            diff = abs(val - mp.mpf(p)/q)
            if diff < mp.mpf(10)**(-(dps - 20)):
                return True, int(p), q
    return False, 0, 0


def main():
    mp.mp.dps = CHECK_DPS

    print("=" * 70)
    print("  CATALOG TRIVIAL-RELATION AUDIT")
    print("=" * 70)

    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    print(f"\n  Catalog size: {len(catalog)}")

    targets = {}
    with mp.workdps(CHECK_DPS + 50):
        for name in ["zeta2", "zeta3", "zeta4", "zeta5", "zeta6", "zeta7",
                      "pi2", "pi3", "catalan"]:
            if "zeta" in name:
                targets[name] = mp.zeta(int(name[4:]))
            elif name == "pi2":
                targets[name] = mp.pi**2
            elif name == "pi3":
                targets[name] = mp.pi**3
            elif name == "catalan":
                targets[name] = mp.catalan

    results_by_target = {}
    total_genuine = 0
    total_trivial = 0
    total_checked = 0

    for target_name in ["zeta2", "zeta3", "zeta4", "zeta5", "zeta6", "zeta7",
                         "pi2", "pi3", "catalan"]:
        entries = [d for d in catalog if d.get("target") == target_name]
        if not entries:
            continue

        genuine = 0
        trivial = 0
        errors = 0
        details = []

        for d in entries:
            alpha = d.get("alpha", [])
            beta = d.get("beta", [])
            mode = d.get("mode", "backward")
            order = d.get("order", 0)

            # Compute CF value
            try:
                if mode == "ratio" and order > 0:
                    # Skip ratio mode — these need special handling
                    details.append({"status": "SKIPPED_RATIO"})
                    continue
                v = eval_backward(alpha, beta, CF_DEPTH, CHECK_DPS)
            except Exception:
                errors += 1
                details.append({"status": "ERROR"})
                continue

            if mp.isnan(v) or mp.isinf(v):
                errors += 1
                details.append({"status": "DIVERGENT"})
                continue

            total_checked += 1

            # Check if CF value is rational
            is_rat, p, q = is_rational(v, CHECK_DPS)
            if is_rat:
                trivial += 1
                total_trivial += 1
                details.append({
                    "status": "TRIVIAL_RATIONAL",
                    "cf_rational": f"{p}/{q}",
                    "alpha": alpha, "beta": beta,
                })
            else:
                # CF is not rational — check if it genuinely involves the target
                with mp.workdps(CHECK_DPS):
                    tgt_val = targets[target_name]
                    rel = mp.pslq([v, tgt_val, mp.mpf(1)],
                                  maxcoeff=10000, maxsteps=2000)
                    if rel and rel[0] != 0 and rel[1] != 0:
                        dot = abs(rel[0]*v + rel[1]*tgt_val + rel[2])
                        rd = max(0, int(-float(mp.log10(dot)))) if dot > 0 else CHECK_DPS
                        if rd >= 50:
                            genuine += 1
                            total_genuine += 1
                            details.append({"status": "GENUINE", "pslq_digits": rd})
                        else:
                            trivial += 1
                            total_trivial += 1
                            details.append({"status": "WEAK_RELATION"})
                    else:
                        # No linear relation — check degree 2
                        rel2 = mp.pslq([v**2, v*tgt_val, v, tgt_val, mp.mpf(1)],
                                       maxcoeff=10000, maxsteps=2000)
                        if rel2:
                            dot2 = abs(sum(c*b for c,b in zip(rel2,
                                     [v**2, v*tgt_val, v, tgt_val, mp.mpf(1)])))
                            rd2 = max(0, int(-float(mp.log10(dot2)))) if dot2 > 0 else CHECK_DPS
                            if rd2 >= 50:
                                genuine += 1
                                total_genuine += 1
                                details.append({"status": "GENUINE_DEG2", "pslq_digits": rd2})
                            else:
                                details.append({"status": "UNCLEAR"})
                        else:
                            details.append({"status": "UNCLEAR"})

        results_by_target[target_name] = {
            "total": len(entries),
            "genuine": genuine,
            "trivial": trivial,
            "errors": errors,
        }

        triv_pct = trivial / max(len(entries), 1) * 100
        print(f"  {target_name:>8s}: {len(entries):4d} entries | "
              f"{genuine:3d} genuine | {trivial:3d} trivial ({triv_pct:.0f}%) | "
              f"{errors:2d} errors")

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"  AUDIT SUMMARY")
    print(f"{'='*70}")
    print(f"  Total checked:  {total_checked}")
    print(f"  Genuine:        {total_genuine}")
    print(f"  Trivial:        {total_trivial}")
    triv_rate = total_trivial / max(total_checked, 1) * 100
    print(f"  Trivial rate:   {triv_rate:.1f}%")

    if total_trivial > 0:
        print(f"\n  WARNING: {total_trivial} entries are trivial rational CF values")
        print(f"  that were misclassified as zeta-value relations.")
        print(f"  These should be removed from the catalog.")

    # ── Corrected Conjecture C evidence ──
    print(f"\n{'='*70}")
    print(f"  CORRECTED CONJECTURE C EVIDENCE")
    print(f"{'='*70}")
    for tgt, r in results_by_target.items():
        if r["genuine"] > 0:
            print(f"  {tgt}: {r['genuine']} genuine root-at-2 entries")
        else:
            print(f"  {tgt}: 0 genuine entries (all {r['trivial']} were trivial)")

    # Save
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"TRIVIAL-RELATION AUDIT\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Checked: {total_checked}, Genuine: {total_genuine}, "
                f"Trivial: {total_trivial}\n\n")
        for tgt, r in results_by_target.items():
            f.write(f"{tgt}: {r}\n")
    print(f"\n  Report: {REPORT_FILE}")

    with open("trivial_audit_results.json", "w") as f:
        json.dump(results_by_target, f, indent=2)
    print(f"  Data: trivial_audit_results.json")


if __name__ == "__main__":
    main()
