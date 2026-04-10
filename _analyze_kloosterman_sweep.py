#!/usr/bin/env python3
"""
Analyze Kloosterman Sweep Results
══════════════════════════════════

Parse kloosterman_sweep_results.json and extract:
  - Discovery count by target constant
  - Signature distribution (adeg/bdeg)
  - High-convergence discoveries (super-exponential)
  - K2 cusp-width descendants (conductor-24 resonance)
  - Novel high-order GCFs
"""

import json
import sys
from collections import Counter

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "kloosterman_sweep_results.json"
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {path}")
        print("The sweep may still be running. Check with:")
        print("  Get-Process python | Select-Object Id, CPU, WorkingSet")
        return

    stats = data.get("stats", {})
    discoveries = data.get("discoveries", [])

    print("=" * 70)
    print("  KLOOSTERMAN SWEEP ANALYSIS")
    print("=" * 70)
    print(f"\n  Iterations: {stats.get('iters', '?')}")
    print(f"  Tested:     {stats.get('tested', '?')}")
    print(f"  Novel:      {stats.get('novel', '?')}")
    print(f"  Total discoveries: {len(discoveries)}")

    if not discoveries:
        print("\n  No discoveries to analyze.")
        return

    # ── By target ──
    target_counts = Counter()
    for d in discoveries:
        target = d.get("target", d.get("closed_form", "?"))
        # Extract target from the closed_form or relation
        cf = d.get("closed_form", "")
        rel = d.get("relation", "")
        for t in ["zeta3", "zeta5", "zeta2", "zeta4", "catalan", "pi", "pi2",
                   "e", "log2", "euler_g", "phi"]:
            if t in str(cf) or t in str(rel):
                target_counts[t] += 1
                break

    print(f"\n  Discoveries by target:")
    for t, c in target_counts.most_common():
        print(f"    {t:12s}: {c}")

    # ── By signature ──
    sig_counts = Counter()
    for d in discoveries:
        spec = d.get("spec", {})
        alpha = spec.get("alpha", [])
        beta = spec.get("beta", [])
        mode = spec.get("mode", "backward")
        order = spec.get("order", 0)
        adeg = len(alpha) - 1 if alpha else 0
        bdeg = len(beta) - 1 if beta else 0
        sig = f"adeg={adeg}|bdeg={bdeg}|mode={mode}|order={order}"
        sig_counts[sig] += 1

    print(f"\n  Discoveries by signature:")
    for sig, c in sig_counts.most_common(15):
        print(f"    {c:3d}  {sig}")

    # ── High convergence rate (>3 dp/term) ──
    print(f"\n  HIGH CONVERGENCE DISCOVERIES (>3 dp/term or cubic+ β):")
    print(f"  {'─'*62}")
    for d in discoveries:
        spec = d.get("spec", {})
        beta = spec.get("beta", [])
        alpha = spec.get("alpha", [])
        bdeg = len(beta) - 1 if beta else 0
        digits = d.get("digits", 0)
        n_terms = spec.get("n_terms", 120)
        rate = digits / max(n_terms, 1)

        if rate >= 3.0 or bdeg >= 3:
            cf = d.get("closed_form", "?")
            rel = d.get("relation", "?")
            mode = spec.get("mode", "?")
            print(f"\n    a(n) = {alpha}")
            print(f"    b(n) = {beta}")
            print(f"    CF = {cf}")
            print(f"    Relation: {rel}")
            print(f"    Mode: {mode}, Digits: {digits}, Rate: ~{rate:.2f} dp/term")

    # ── Conductor-24 descendants ──
    print(f"\n  K2 CUSP-WIDTH DESCENDANTS (β has coeff 48 or 24):")
    print(f"  {'─'*62}")
    for d in discoveries:
        spec = d.get("spec", {})
        beta = spec.get("beta", [])
        if any(abs(c) in (24, 48, 72) for c in beta):
            alpha = spec.get("alpha", [])
            cf = d.get("closed_form", "?")
            digits = d.get("digits", 0)
            print(f"    a={alpha}, b={beta} → {cf} ({digits}dp)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
