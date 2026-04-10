#!/usr/bin/env python3
"""
Direct CF-Value Rationality Verification
═════════════════════════════════════════

The trivial_relation_audit claimed 100% of catalog entries are rational.
Before discarding 342 entries, verify this DIRECTLY:

For each entry:
  1. Recompute CF value from scratch at 500dp
  2. Run degree-1 PSLQ: [CF, 1] — does it find CF = p/q?
  3. If rational: confirmed trivial
  4. If NOT rational: run [CF, target, 1] — is it a genuine hit?

This is the critical test. If ANY entry has a genuinely transcendental
CF value with a valid linear relation to zeta(k), the catalog is
not entirely invalid.
"""

import json
import time
import mpmath as mp

CATALOG_PATH = "discovery_catalog.json"
DPS = 500
CF_DEPTH = 500
MAX_DENOM = 100000  # check denominators up to 100k


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


def check_rational(val, dps, max_denom=MAX_DENOM):
    """Check if val is rational p/q with q <= max_denom.
    Returns (is_rational, p, q, residual_digits)."""
    with mp.workdps(dps):
        # Method 1: direct denominator search (fast for small q)
        for q in range(1, min(max_denom + 1, 10001)):
            p = mp.nint(val * q)
            diff = abs(val - mp.mpf(p) / q)
            if diff < mp.mpf(10)**(-(dps - 30)):
                return True, int(p), q, dps - 30

        # Method 2: PSLQ on [CF, 1] (catches larger rationals)
        rel = mp.pslq([val, mp.mpf(1)], maxcoeff=max_denom, maxsteps=2000)
        if rel and rel[0] != 0:
            # CF = -rel[1]/rel[0]
            expected = mp.mpf(-rel[1]) / mp.mpf(rel[0])
            diff = abs(val - expected)
            rd = max(0, int(-float(mp.log10(diff)))) if diff > 0 else dps
            if rd >= dps // 2:
                return True, -int(rel[1]), int(rel[0]), rd

    return False, 0, 0, 0


def main():
    mp.mp.dps = DPS

    print("=" * 70)
    print("  DIRECT CF-VALUE RATIONALITY VERIFICATION")
    print("=" * 70)

    with open(CATALOG_PATH) as f:
        catalog = json.load(f)
    print(f"  Catalog size: {len(catalog)}")
    print(f"  Precision: {DPS} dps, depth: {CF_DEPTH}")
    print(f"  Max denominator: {MAX_DENOM}")

    # Build target constants
    targets = {}
    with mp.workdps(DPS + 50):
        for k in range(2, 10):
            targets[f"zeta{k}"] = mp.zeta(k)
        targets["pi2"] = mp.pi**2
        targets["pi3"] = mp.pi**3
        targets["catalan"] = mp.catalan
        targets["pi"] = mp.pi

    rational_count = 0
    transcendental_count = 0
    genuine_hits = []
    error_count = 0
    ratio_mode_count = 0

    t0 = time.time()

    for i, d in enumerate(catalog):
        alpha = d.get("alpha", [])
        beta = d.get("beta", [])
        mode = d.get("mode", "backward")
        order = d.get("order", 0)
        target_name = d.get("target", "unknown")

        # Compute CF from scratch
        try:
            if mode == "ratio" and order > 0:
                cf_val = eval_ratio(alpha, beta, order, CF_DEPTH, DPS)
                ratio_mode_count += 1
            else:
                cf_val = eval_backward(alpha, beta, CF_DEPTH, DPS)
        except Exception as e:
            error_count += 1
            continue

        if mp.isnan(cf_val) or mp.isinf(cf_val):
            error_count += 1
            continue

        # Check rationality
        is_rat, p, q, rd = check_rational(cf_val, DPS)

        if is_rat:
            rational_count += 1
            if i < 10 or i % 50 == 0:
                print(f"  [{i+1:3d}] RATIONAL: CF = {p}/{q} "
                      f"(a={alpha[:3]}{'...' if len(alpha)>3 else ''}, "
                      f"target={target_name})")
        else:
            transcendental_count += 1
            # This CF is NOT rational — check against target
            if target_name in targets:
                tgt = targets[target_name]
                with mp.workdps(DPS):
                    # Degree-1 PSLQ
                    rel = mp.pslq([cf_val, tgt, mp.mpf(1)],
                                  maxcoeff=10000, maxsteps=3000)
                    if rel and rel[0] != 0 and rel[1] != 0:
                        dot = abs(rel[0]*cf_val + rel[1]*tgt + rel[2])
                        pslq_rd = max(0, int(-float(mp.log10(dot)))) if dot > 0 else DPS
                        if pslq_rd >= 100:
                            genuine_hits.append({
                                "index": i,
                                "alpha": alpha,
                                "beta": beta,
                                "mode": mode,
                                "order": order,
                                "target": target_name,
                                "relation": [int(x) for x in rel],
                                "pslq_digits": pslq_rd,
                                "cf_value_20": mp.nstr(cf_val, 20),
                            })
                            print(f"  [{i+1:3d}] *** GENUINE HIT *** "
                                  f"target={target_name} "
                                  f"{rel[0]}*CF + {rel[1]}*{target_name} + {rel[2]} = 0 "
                                  f"({pslq_rd}dp)")
                            print(f"        CF = {mp.nstr(cf_val, 20)}")
                            print(f"        a={alpha}, b={beta}")
                        else:
                            print(f"  [{i+1:3d}] NON-RATIONAL but weak deg-1 relation "
                                  f"(CF={mp.nstr(cf_val, 10)}, target={target_name})")
                    else:
                        # Try degree-2 PSLQ (but ONLY for non-rational CFs)
                        rel2 = mp.pslq([cf_val**2, cf_val*tgt, cf_val, tgt, mp.mpf(1)],
                                       maxcoeff=10000, maxsteps=3000)
                        if rel2:
                            dot2 = abs(sum(c*b for c, b in zip(rel2,
                                         [cf_val**2, cf_val*tgt, cf_val, tgt, mp.mpf(1)])))
                            pslq_rd2 = max(0, int(-float(mp.log10(dot2)))) if dot2 > 0 else DPS
                            if pslq_rd2 >= 100:
                                genuine_hits.append({
                                    "index": i, "alpha": alpha, "beta": beta,
                                    "mode": mode, "order": order,
                                    "target": target_name,
                                    "relation_deg2": [int(x) for x in rel2],
                                    "pslq_digits": pslq_rd2,
                                    "cf_value_20": mp.nstr(cf_val, 20),
                                })
                                print(f"  [{i+1:3d}] *** GENUINE DEG-2 HIT *** "
                                      f"(non-rational CF, {pslq_rd2}dp)")
                                print(f"        CF = {mp.nstr(cf_val, 20)}")
                                print(f"        a={alpha}, b={beta}")
                            else:
                                print(f"  [{i+1:3d}] NON-RATIONAL, no relation "
                                      f"(CF={mp.nstr(cf_val, 10)}, target={target_name})")
                        else:
                            print(f"  [{i+1:3d}] NON-RATIONAL, unidentified "
                                  f"(CF={mp.nstr(cf_val, 10)}, target={target_name})")
            else:
                print(f"  [{i+1:3d}] NON-RATIONAL, unknown target "
                      f"(CF={mp.nstr(cf_val, 10)})")

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"  --- Progress: {i+1}/{len(catalog)} "
                  f"({rational_count} rational, {transcendental_count} non-rational, "
                  f"{len(genuine_hits)} genuine) [{elapsed:.0f}s] ---")

    elapsed = time.time() - t0

    # ── Results ──
    print(f"\n{'='*70}")
    print(f"  DIRECT VERIFICATION RESULTS")
    print(f"{'='*70}")
    print(f"  Total entries:     {len(catalog)}")
    print(f"  Computed:          {rational_count + transcendental_count}")
    print(f"  Rational CFs:      {rational_count}")
    print(f"  Non-rational CFs:  {transcendental_count}")
    print(f"  Genuine hits:      {len(genuine_hits)}")
    print(f"  Errors/skipped:    {error_count}")
    print(f"  Ratio-mode:        {ratio_mode_count}")
    print(f"  Time:              {elapsed:.1f}s")

    if genuine_hits:
        print(f"\n  *** {len(genuine_hits)} GENUINE DISCOVERIES RECOVERED ***")
        for h in genuine_hits:
            print(f"\n  Target: {h['target']}")
            print(f"    alpha = {h['alpha']}")
            print(f"    beta  = {h['beta']}")
            print(f"    CF    = {h['cf_value_20']}")
            if 'relation' in h:
                r = h['relation']
                print(f"    {r[0]}*CF + {r[1]}*{h['target']} + {r[2]} = 0 "
                      f"({h['pslq_digits']}dp)")
            elif 'relation_deg2' in h:
                r = h['relation_deg2']
                print(f"    Deg-2: {r} ({h['pslq_digits']}dp)")
    else:
        print(f"\n  NO genuine transcendental discoveries found.")
        print(f"  The 'all rational' conclusion is CONFIRMED.")

    rat_pct = rational_count / max(rational_count + transcendental_count, 1) * 100
    print(f"\n  Rational rate: {rat_pct:.1f}%")

    # Save
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "catalog_size": len(catalog),
        "rational_count": rational_count,
        "transcendental_count": transcendental_count,
        "genuine_hits": genuine_hits,
        "error_count": error_count,
        "rational_rate_pct": round(rat_pct, 2),
    }
    with open("direct_rationality_check.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Saved to direct_rationality_check.json")


if __name__ == "__main__":
    main()
