#!/usr/bin/env python3
"""Meijer G-function Parametric Scanner for V_quad.

V_quad = GCF(1, 3n²+n+1) ≈ 1.197373990688357602...

Strategy:
  1. Derive the ODE satisfied by the GCF from its recurrence relation
  2. Scan Meijer G^{m,n}_{p,q}(z) for parameter tuples that match V_quad
  3. Also scan hypergeometric pFq at rational/algebraic arguments
  4. Test V_quad against Lommel S_{μ,ν}(z) with floating parameters
  5. Any match → V_quad has a closed-form representation

The 3-term recurrence for b₀ + a₁/(b₁ + a₂/(b₂+...)) with a(n)=1, b(n)=3n²+n+1
yields a contiguous relation that can be expressed as a Meijer G-function
evaluated at z=1/27 (the discriminant connection: Δ=-11, 4·3·(-1)=27-like).

Usage:
    python meijer_g_scanner.py
    python meijer_g_scanner.py --prec 1200 --grid-size 5
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from fractions import Fraction
from itertools import product

import mpmath as mp

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# V_quad definition: a(n)=1, b(n)=3n²+n+1
# CF = b(0) + 1/(b(1) + 1/(b(2) + ...)) = 1 + 1/(5 + 1/(15 + ...))
VQUAD_ALPHA = [1]          # a(n) = 1 for all n
VQUAD_BETA = [1, 1, 3]    # b(n) = 3n²+n+1


def compute_vquad(dps: int, n_terms: int = 5000) -> mp.mpf:
    """Compute V_quad to high precision."""
    with mp.workdps(dps + 100):
        val = mp.mpf(0)
        tol = mp.mpf(10) ** -(dps + 80)
        for n in range(n_terms, 0, -1):
            an = mp.mpf(1)  # numerator is always 1
            bn = 3 * mp.mpf(n)**2 + mp.mpf(n) + 1
            denom = bn + val
            if abs(denom) < tol:
                return None
            val = an / denom
        b0 = mp.mpf(1)  # b(0) = 1
        return b0 + val


def _pslq_test(vec, dps, maxcoeff=10000):
    """Run PSLQ and return (relation, precision_digits) or (None, 0)."""
    tol = mp.mpf(10) ** -(dps // 2)
    try:
        with mp.workdps(dps):
            rel = mp.pslq(vec, tol=tol, maxcoeff=maxcoeff)
    except Exception:
        return None, 0
    if rel is None:
        return None, 0
    res = abs(sum(r * v for r, v in zip(rel, vec)))
    if res == 0:
        return rel, dps
    prec = max(0, int(-float(mp.log10(res + mp.mpf(10) ** -(dps - 2)))))
    return rel, prec


def scan_meijer_g(vquad: mp.mpf, dps: int, grid_size: int = 4) -> list[dict]:
    """Scan Meijer G-function special values against V_quad.

    Target G^{m,n}_{p,q}(z | a_1..a_p ; b_1..b_q) at small rational params.
    Focus on (0,3) and (1,3) signatures matching the 3-term recurrence order.
    """
    results = []
    pslq_dps = max(80, dps // 3)

    # Rational parameter grid: k/6 for k in range
    param_pool = [Fraction(k, 6) for k in range(-2 * grid_size, 2 * grid_size + 1)
                  if k != 0]
    # Add discriminant-related fractions
    param_pool += [Fraction(1, 3), Fraction(2, 3), Fraction(1, 11),
                   Fraction(1, 12), Fraction(5, 6), Fraction(7, 6)]
    param_pool = sorted(set(param_pool))

    # Argument values: related to discriminant -11 and conductor structure
    z_values = {
        "1/27": mp.mpf(1) / 27,
        "-1/27": mp.mpf(-1) / 27,
        "4/27": mp.mpf(4) / 27,
        "-4/27": mp.mpf(-4) / 27,
        "11/108": mp.mpf(11) / 108,
        "-11/108": mp.mpf(-11) / 108,
        "1/3": mp.mpf(1) / 3,
        "1/11": mp.mpf(1) / 11,
        "1/12": mp.mpf(1) / 12,
        "1": mp.mpf(1),
    }

    print(f"  Scanning G_{{0,3}}^{{3,0}} with {len(param_pool)} params × {len(z_values)} args...")
    tested = 0

    # G^{3,0}_{0,3}(z | - ; b1, b2, b3) — the natural signature for 3-term recurrences
    for z_label, z_val in z_values.items():
        for b1, b2, b3 in product(param_pool[:grid_size * 2], repeat=3):
            if b1 >= b2 or b2 >= b3:  # Avoid redundant permutations
                continue
            try:
                with mp.workdps(dps + 20):
                    g_val = mp.meijerg([[], []], [[float(b1), float(b2), float(b3)], []], z_val)
                if g_val is None or not mp.isfinite(g_val) or g_val == 0:
                    continue
                # Skip complex results
                if isinstance(g_val, mp.mpc) or (hasattr(g_val, 'imag') and abs(g_val.imag) > 1e-20):
                    continue
                g_val = mp.re(g_val) if hasattr(g_val, 'real') else g_val
            except Exception:
                continue

            tested += 1
            # Test: a·V_quad + b·G + c = 0
            with mp.workdps(pslq_dps):
                vec = [mp.mpf(vquad), mp.mpf(g_val), mp.mpf(1)]
                rel, prec = _pslq_test(vec, pslq_dps)

            if rel and prec >= 15 and rel[1] != 0:
                results.append({
                    "type": "meijer_G_0_3",
                    "params": {"b": [str(b1), str(b2), str(b3)]},
                    "z": z_label,
                    "relation": [int(r) for r in rel],
                    "precision": prec,
                    "g_value": mp.nstr(g_val, 20),
                    "status": "MATCH" if prec >= dps // 4 else "near_miss",
                })

    print(f"    Tested {tested} G-function evaluations")
    return results


def scan_hypergeometric(vquad: mp.mpf, dps: int, grid_size: int = 4) -> list[dict]:
    """Scan hypergeometric pFq at rational arguments against V_quad."""
    results = []
    pslq_dps = max(80, dps // 3)

    # The GCF 1/(3n²+n+1) connects to 0F2 or 1F2 via standard identities
    # Focus: 0F2(; a, b; z) and 1F2(a; b, c; z)

    param_fracs = [Fraction(k, 6) for k in range(1, 4 * grid_size)]
    param_fracs += [Fraction(1, 3), Fraction(2, 3), Fraction(1, 11)]
    param_fracs = sorted(set(f for f in param_fracs if f > 0))

    z_values = {
        "-1/27": mp.mpf(-1) / 27,
        "1/27": mp.mpf(1) / 27,
        "-4/27": mp.mpf(-4) / 27,
        "-11/108": mp.mpf(-11) / 108,
        "11/108": mp.mpf(11) / 108,
    }

    print(f"  Scanning 0F2 with {len(param_fracs)} params × {len(z_values)} args...")
    tested = 0

    for z_label, z_val in z_values.items():
        for a, b in product(param_fracs[:grid_size * 2], repeat=2):
            if a >= b:
                continue
            try:
                with mp.workdps(dps + 20):
                    h_val = mp.hyper([], [float(a), float(b)], z_val)
                if h_val is None or not mp.isfinite(h_val) or h_val == 0:
                    continue
            except Exception:
                continue

            tested += 1
            with mp.workdps(pslq_dps):
                vec = [mp.mpf(vquad), mp.mpf(h_val), mp.mpf(1)]
                rel, prec = _pslq_test(vec, pslq_dps)

            if rel and prec >= 15 and rel[1] != 0:
                results.append({
                    "type": "0F2",
                    "params": {"a": str(a), "b": str(b)},
                    "z": z_label,
                    "relation": [int(r) for r in rel],
                    "precision": prec,
                    "hyp_value": mp.nstr(h_val, 20),
                    "status": "MATCH" if prec >= dps // 4 else "near_miss",
                })

    print(f"    Tested {tested} 0F2 evaluations")

    # Also scan 1F2
    print(f"  Scanning 1F2 with top params...")
    tested = 0
    for z_label, z_val in z_values.items():
        for a1, b1, b2 in product(param_fracs[:grid_size], repeat=3):
            if b1 >= b2:
                continue
            try:
                with mp.workdps(dps + 20):
                    h_val = mp.hyper([float(a1)], [float(b1), float(b2)], z_val)
                if h_val is None or not mp.isfinite(h_val) or h_val == 0:
                    continue
            except Exception:
                continue

            tested += 1
            with mp.workdps(pslq_dps):
                vec = [mp.mpf(vquad), mp.mpf(h_val), mp.mpf(1)]
                rel, prec = _pslq_test(vec, pslq_dps)

            if rel and prec >= 15 and rel[1] != 0:
                results.append({
                    "type": "1F2",
                    "params": {"a1": str(a1), "b1": str(b1), "b2": str(b2)},
                    "z": z_label,
                    "relation": [int(r) for r in rel],
                    "precision": prec,
                    "hyp_value": mp.nstr(h_val, 20),
                    "status": "MATCH" if prec >= dps // 4 else "near_miss",
                })

    print(f"    Tested {tested} 1F2 evaluations")
    return results


def scan_lommel(vquad: mp.mpf, dps: int, grid_size: int = 5) -> list[dict]:
    """Scan Lommel S_{μ,ν}(z) against V_quad with floating parameters."""
    results = []
    pslq_dps = max(80, dps // 3)

    # μ, ν parameter grid: half-integer and third-integer steps
    mu_vals = [Fraction(k, 6) for k in range(-3 * grid_size, 3 * grid_size + 1)]
    nu_vals = [Fraction(k, 6) for k in range(-3 * grid_size, 3 * grid_size + 1)]
    mu_vals = sorted(set(mu_vals))
    nu_vals = sorted(set(nu_vals))

    # z arguments
    z_args = {
        "1": mp.mpf(1),
        "sqrt(11)/3": mp.sqrt(11) / 3,
        "2/3": mp.mpf(2) / 3,
        "1/3": mp.mpf(1) / 3,
        "2*sqrt(11)/(3*sqrt(3))": 2 * mp.sqrt(11) / (3 * mp.sqrt(3)),
        "sqrt(3)": mp.sqrt(3),
    }

    print(f"  Scanning Lommel S_{{μ,ν}}(z) with {len(mu_vals)}×{len(nu_vals)} params × {len(z_args)} args...")
    tested = 0

    for z_label, z_val in z_args.items():
        for mu in mu_vals:
            for nu in nu_vals:
                mu_f = float(mu)
                nu_f = float(nu)
                # Lommel S is defined for (μ-ν) and (μ+ν) not odd negative integers
                if (mu_f - nu_f) % 2 == 0 and (mu_f - nu_f) < 0:
                    continue
                try:
                    with mp.workdps(dps + 20):
                        # Lommel via hypergeometric: S_{μ,ν}(z)
                        # = z^{μ+1} / ((μ+1)²-ν²) · 1F2(1; (μ-ν+3)/2, (μ+ν+3)/2; -z²/4)
                        a_top = (mu_f + 1)**2 - nu_f**2
                        if abs(a_top) < 1e-10:
                            continue
                        p1 = (mu_f - nu_f + 3) / 2
                        p2 = (mu_f + nu_f + 3) / 2
                        if p1 <= 0 or p2 <= 0:
                            continue
                        hyp = mp.hyper([1], [p1, p2], -(z_val**2) / 4)
                        s_val = z_val**(mu_f + 1) / a_top * hyp
                    if s_val is None or not mp.isfinite(s_val) or s_val == 0:
                        continue
                except Exception:
                    continue

                tested += 1
                with mp.workdps(pslq_dps):
                    vec = [mp.mpf(vquad), mp.mpf(s_val), mp.mpf(1)]
                    rel, prec = _pslq_test(vec, pslq_dps)

                if rel and prec >= 15 and rel[1] != 0:
                    results.append({
                        "type": "lommel",
                        "params": {"mu": str(mu), "nu": str(nu)},
                        "z": z_label,
                        "relation": [int(r) for r in rel],
                        "precision": prec,
                        "lommel_value": mp.nstr(s_val, 20),
                        "status": "MATCH" if prec >= dps // 4 else "near_miss",
                    })

    print(f"    Tested {tested} Lommel evaluations")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Meijer G-function parametric scanner for V_quad.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--prec", type=int, default=500,
                        help="Working precision (digits).")
    parser.add_argument("--grid-size", type=int, default=4,
                        help="Parameter grid density (higher = slower).")
    parser.add_argument("--skip-meijer", action="store_true")
    parser.add_argument("--skip-hyper", action="store_true")
    parser.add_argument("--skip-lommel", action="store_true")
    parser.add_argument("--json-out", default="meijer_g_scan.json")
    args = parser.parse_args()

    dps = args.prec
    mp.mp.dps = dps + 100

    print(f"{'='*60}")
    print(f"  Meijer G-function Scanner for V_quad")
    print(f"{'='*60}")
    print(f"  Precision: {dps}dp  Grid: {args.grid_size}")
    t0 = time.perf_counter()

    # Compute V_quad
    print("\n[0] Computing V_quad...")
    vquad = compute_vquad(dps)
    print(f"  V_quad = {mp.nstr(vquad, 40)}")

    all_results = []

    # Meijer G scan
    if not args.skip_meijer:
        print("\n[1] Meijer G-function scan...")
        meijer_results = scan_meijer_g(vquad, dps, args.grid_size)
        all_results.extend(meijer_results)
        matches = sum(1 for r in meijer_results if r["status"] == "MATCH")
        print(f"    Matches: {matches}  Near-misses: {len(meijer_results) - matches}")

    # Hypergeometric scan
    if not args.skip_hyper:
        print("\n[2] Hypergeometric pFq scan...")
        hyper_results = scan_hypergeometric(vquad, dps, args.grid_size)
        all_results.extend(hyper_results)
        matches = sum(1 for r in hyper_results if r["status"] == "MATCH")
        print(f"    Matches: {matches}  Near-misses: {len(hyper_results) - matches}")

    # Lommel scan
    if not args.skip_lommel:
        print("\n[3] Lommel S_{μ,ν}(z) scan...")
        lommel_results = scan_lommel(vquad, dps, args.grid_size)
        all_results.extend(lommel_results)
        matches = sum(1 for r in lommel_results if r["status"] == "MATCH")
        print(f"    Matches: {matches}  Near-misses: {len(lommel_results) - matches}")

    wall = round(time.perf_counter() - t0, 3)

    # Save
    output = {
        "scanner": "meijer_g_vquad",
        "precision": dps,
        "grid_size": args.grid_size,
        "vquad_value": mp.nstr(vquad, 50),
        "total_results": len(all_results),
        "matches": [r for r in all_results if r["status"] == "MATCH"],
        "near_misses": [r for r in all_results if r["status"] == "near_miss"],
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "all_results": all_results,
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  V_quad Parametric Scan Report")
    print(f"{'='*60}")
    print(f"  Total evaluations: across 3 function families")
    print(f"  MATCHES (strong):  {len(output['matches'])}")
    print(f"  Near-misses:       {len(output['near_misses'])}")
    print(f"  Wall time:         {wall}s")

    if output["matches"]:
        print(f"\n  *** MATCHES FOUND — V_quad may have a closed form! ***")
        for m in output["matches"]:
            print(f"    {m['type']}  params={m.get('params',{})}  z={m['z']}")
            print(f"      rel={m['relation']}  prec={m['precision']}dp")
    elif output["near_misses"]:
        print(f"\n  Near-misses (investigate further):")
        for nm in output["near_misses"][:10]:
            print(f"    {nm['type']}  params={nm.get('params',{})}  z={nm['z']}  "
                  f"prec={nm['precision']}dp")
    else:
        print(f"\n  No matches or near-misses found. V_quad remains genuinely wild.")

    print(f"\n  JSON -> {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
