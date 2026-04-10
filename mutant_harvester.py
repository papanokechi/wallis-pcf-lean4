#!/usr/bin/env python3
"""
Mutant Harvester — Phase 5A
════════════════════════════

Extracts convergence fingerprints, conductor-clustered seed families,
and improved templates from the merged discovery catalog.

Inputs:
  - kloosterman_sweep_results.json  (209 discoveries)
  - zeta5_55_sweep_results.json     (158 discoveries)
  - ramanujan_persistent_seeds.json (promoted seeds)

Outputs:
  - harvest/mutant_harvest.json     (full harvest data)
  - harvest/conductor_clusters.json (seed families by conductor)
  - harvest/66_pilot_seeds.json     (ready-to-use (6,6) seeds)
  - harvest/independence_candidates.json (for algebraic independence checks)
"""

import json
import os
import hashlib
import time
from collections import Counter, defaultdict
from pathlib import Path
from dataclasses import dataclass, asdict

HARVEST_DIR = Path("harvest")
HARVEST_DIR.mkdir(exist_ok=True)


@dataclass
class MutantFingerprint:
    source: str                 # "kloosterman" or "zeta5_55"
    target: str                 # "zeta3", "zeta5", etc.
    alpha: list
    beta: list
    adeg: int
    bdeg: int
    mode: str
    order: int
    closed_form: str
    conv_digits: int
    formula: str
    signature: str
    fingerprint: str
    convergence_rate: float     # digits per term
    conductor_resonance: str    # "N=24", "N=120", etc.


def load_kloosterman():
    """Load discoveries from Kloosterman sweep."""
    path = "kloosterman_sweep_results.json"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    results = []
    for d in data.get("discoveries", []):
        spec = d.get("spec", {})
        alpha = spec.get("alpha", [])
        beta = spec.get("beta", [])
        results.append(_make_fingerprint(
            source="kloosterman",
            target=d.get("constant", "unknown"),
            alpha=alpha, beta=beta,
            mode=spec.get("mode", "backward"),
            order=spec.get("order", 0),
            closed_form=d.get("enrichment", {}).get("closed_form", d.get("cf_approx", "")),
            conv_digits=d.get("conv_digits", d.get("precision_dp", 300)),
            formula=d.get("formula", ""),
            n_terms=spec.get("n_terms", 120),
        ))
    return results


def load_zeta5_55():
    """Load discoveries from (5,5) strike."""
    path = "zeta5_55_sweep_results.json"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    results = []
    for r in data.get("results", []):
        for d in r.get("high_value", []):
            alpha = d.get("alpha", [])
            beta = d.get("beta", [])
            results.append(_make_fingerprint(
                source="zeta5_55",
                target=d.get("constant", "unknown"),
                alpha=alpha, beta=beta,
                mode=d.get("mode", "backward"),
                order=d.get("order", 0),
                closed_form=d.get("enrichment", {}).get("closed_form", d.get("cf_approx", "")),
                conv_digits=d.get("precision", 500),
                formula=d.get("formula", ""),
                n_terms=d.get("n_terms", 300),
            ))
    return results


def _make_fingerprint(source, target, alpha, beta, mode, order,
                       closed_form, conv_digits, formula, n_terms):
    adeg = max(0, len(alpha) - 1)
    bdeg = max(0, len(beta) - 1)
    sig = f"adeg={adeg}|bdeg={bdeg}|mode={mode}|order={order}"
    fp = hashlib.md5((str(alpha) + str(beta) + mode).encode()).hexdigest()[:12]
    rate = conv_digits / max(n_terms, 1)
    cond = _detect_conductor(beta)

    return MutantFingerprint(
        source=source, target=target,
        alpha=alpha, beta=beta,
        adeg=adeg, bdeg=bdeg,
        mode=mode, order=order,
        closed_form=str(closed_form),
        conv_digits=conv_digits,
        formula=formula,
        signature=sig, fingerprint=fp,
        convergence_rate=round(rate, 3),
        conductor_resonance=cond,
    )


def _detect_conductor(beta):
    """Detect conductor resonance from beta polynomial coefficients."""
    if not beta:
        return "N=?"
    # Check for conductor-24 family (Kloosterman)
    for c in beta:
        if abs(c) in (24, 48, 72):
            return f"N=24 (coeff {c})"
    # Check for conductor-120 (5! = zeta5 territory)
    for c in beta:
        if abs(c) in (120, 60, 240):
            return f"N=120 (coeff {c})"
    # Leading coefficient analysis
    lead = abs(beta[-1]) if beta else 0
    if lead > 0:
        # Check if lead is a product of small primes
        for n in [24, 120, 720, 48, 12, 6]:
            if lead % n == 0:
                return f"N={n} (lead={lead})"
    return "N=generic"


def cluster_by_conductor(fingerprints):
    """Group fingerprints by conductor family."""
    clusters = defaultdict(list)
    for fp in fingerprints:
        clusters[fp.conductor_resonance].append(fp)
    return dict(clusters)


def extract_66_seeds(fingerprints):
    """Extract seeds for the (6,6) pilot from highest-degree mutations."""
    # Strategy: take the highest-degree successful specs and extend them
    high_deg = [fp for fp in fingerprints if fp.adeg >= 4 or fp.bdeg >= 4]
    high_deg.sort(key=lambda fp: fp.adeg + fp.bdeg + fp.convergence_rate, reverse=True)

    seeds = []
    seen = set()
    for fp in high_deg[:30]:
        key = fp.fingerprint
        if key in seen:
            continue
        seen.add(key)

        # Direct seed
        seeds.append({
            "alpha": fp.alpha, "beta": fp.beta,
            "target": fp.target, "mode": fp.mode,
            "order": fp.order, "n_terms": 500,
            "_source": f"harvest_{fp.source}",
            "_signature": fp.signature,
        })

        # Degree extension: add one more term to alpha and beta
        alpha_ext = fp.alpha + [1]
        beta_ext = fp.beta + [1]
        seeds.append({
            "alpha": alpha_ext, "beta": beta_ext,
            "target": fp.target,
            "mode": "ratio" if len(alpha_ext) > 4 else fp.mode,
            "order": max(fp.order, len(alpha_ext) - 1),
            "n_terms": 500,
            "_source": "harvest_degree_extension",
        })

    return seeds


def extract_independence_candidates(fingerprints):
    """Extract candidates for algebraic independence checks.

    We want GCFs that converge to the SAME target constant via
    different polynomial families.  If two independent GCFs both
    converge to zeta(5), that's evidence the relation is structural
    (not accidental).
    """
    by_target = defaultdict(list)
    for fp in fingerprints:
        by_target[fp.target].append(fp)

    candidates = {}
    for target, fps in by_target.items():
        if len(fps) < 3:
            continue
        # Group by signature
        by_sig = defaultdict(list)
        for fp in fps:
            by_sig[fp.signature].append(fp)

        # Want at least 2 different signatures
        if len(by_sig) >= 2:
            representatives = []
            for sig, group in sorted(by_sig.items(), key=lambda x: -len(x[1])):
                best = max(group, key=lambda fp: fp.convergence_rate)
                representatives.append({
                    "signature": sig,
                    "count": len(group),
                    "best_alpha": best.alpha,
                    "best_beta": best.beta,
                    "best_rate": best.convergence_rate,
                    "best_closed_form": best.closed_form,
                })
            candidates[target] = {
                "total_discoveries": len(fps),
                "unique_signatures": len(by_sig),
                "representatives": representatives[:8],
            }
    return candidates


def main():
    print("=" * 70)
    print("  MUTANT HARVESTER — PHASE 5A")
    print("=" * 70)

    # ── Load all discovery sources ──
    print("\n  [1/5] Loading discovery sources...")
    kloos = load_kloosterman()
    print(f"    Kloosterman sweep: {len(kloos)} discoveries")
    z5 = load_zeta5_55()
    print(f"    Zeta5 (5,5) strike: {len(z5)} discoveries")

    all_fps = kloos + z5
    print(f"    TOTAL: {len(all_fps)} fingerprints")

    if not all_fps:
        print("  ERROR: No discoveries to harvest.")
        return

    # ── Summary statistics ──
    print("\n  [2/5] Summary statistics...")
    target_counts = Counter(fp.target for fp in all_fps)
    print("    By target:")
    for t, c in target_counts.most_common():
        print(f"      {c:4d}  {t}")

    sig_counts = Counter(fp.signature for fp in all_fps)
    print("    By signature (top 15):")
    for sig, c in sig_counts.most_common(15):
        print(f"      {c:4d}  {sig}")

    source_counts = Counter(fp.source for fp in all_fps)
    print("    By source:")
    for s, c in source_counts.most_common():
        print(f"      {c:4d}  {s}")

    # Rate statistics
    rates = [fp.convergence_rate for fp in all_fps if fp.convergence_rate > 0]
    if rates:
        import statistics
        print(f"    Convergence rate: mean={statistics.mean(rates):.3f}, "
              f"max={max(rates):.3f}, median={statistics.median(rates):.3f}")

    # ── Conductor clustering ──
    print("\n  [3/5] Conductor clustering...")
    clusters = cluster_by_conductor(all_fps)
    for cond, fps in sorted(clusters.items(), key=lambda x: -len(x[1])):
        targets = Counter(fp.target for fp in fps)
        tgt_str = ", ".join(f"{t}:{c}" for t, c in targets.most_common(3))
        print(f"    {len(fps):4d}  {cond:30s}  [{tgt_str}]")

    # ── Extract (6,6) pilot seeds ──
    print("\n  [4/5] Extracting (6,6) pilot seeds...")
    seeds_66 = extract_66_seeds(all_fps)
    print(f"    Generated {len(seeds_66)} seeds for (6,6) pilot")
    if seeds_66:
        # Show top 5
        for i, s in enumerate(seeds_66[:5], 1):
            adeg = len(s["alpha"]) - 1
            bdeg = len(s["beta"]) - 1
            print(f"      [{i}] adeg={adeg} bdeg={bdeg} target={s['target']} "
                  f"mode={s['mode']} src={s.get('_source','?')}")

    # ── Algebraic independence candidates ──
    print("\n  [5/5] Extracting algebraic independence candidates...")
    indep = extract_independence_candidates(all_fps)
    for target, info in indep.items():
        n_disc = info["total_discoveries"]
        n_sig = info["unique_signatures"]
        print(f"    {target}: {n_disc} discoveries across {n_sig} signatures")
        for rep in info["representatives"][:3]:
            print(f"      {rep['count']:3d}x {rep['signature']:40s} rate={rep['best_rate']:.3f}")

    # ── Save outputs ──
    print(f"\n  Saving harvest outputs to {HARVEST_DIR}/...")

    harvest_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_fingerprints": len(all_fps),
        "sources": dict(source_counts),
        "targets": dict(target_counts),
        "signatures": dict(sig_counts.most_common(20)),
        "conductor_clusters": {
            cond: len(fps) for cond, fps in clusters.items()
        },
        "fingerprints": [asdict(fp) for fp in all_fps],
    }
    with open(HARVEST_DIR / "mutant_harvest.json", "w") as f:
        json.dump(harvest_data, f, indent=2, default=str)

    with open(HARVEST_DIR / "conductor_clusters.json", "w") as f:
        cluster_data = {
            cond: [asdict(fp) for fp in fps]
            for cond, fps in clusters.items()
        }
        json.dump(cluster_data, f, indent=2, default=str)

    with open(HARVEST_DIR / "66_pilot_seeds.json", "w") as f:
        json.dump(seeds_66, f, indent=2)

    with open(HARVEST_DIR / "independence_candidates.json", "w") as f:
        json.dump(indep, f, indent=2, default=str)

    print(f"    mutant_harvest.json:         {len(all_fps)} fingerprints")
    print(f"    conductor_clusters.json:     {len(clusters)} clusters")
    print(f"    66_pilot_seeds.json:         {len(seeds_66)} seeds")
    print(f"    independence_candidates.json: {len(indep)} targets")

    print("\n" + "=" * 70)
    print("  HARVEST COMPLETE")
    print("=" * 70)
    print(f"""
  Next steps:
    1. Run (6,6) pilot:
         python deep_sweep.py --target zeta5 --seed-file harvest/66_pilot_seeds.json \\
                              --iters 20 --batch 64 --prec 500 --deep
    2. Algebraic independence check:
         python algebraic_independence.py --input harvest/independence_candidates.json
    3. V_quad frontier:
         python vquad_hypergeometric_scan.py
""")


if __name__ == "__main__":
    main()
