#!/usr/bin/env python3
"""V_quad Elliptic Integral Scanner.

Tests V_quad against complete elliptic integrals K(m) and E(m) at
CM and modular parameters, plus q-series related to conductor 11.

V_quad = 1.197373990688357602... (discriminant -11 GCF)

Target function families:
  1. Complete elliptic K(m) at CM points (m = algebraic, class field)
  2. Complete elliptic E(m) at CM points
  3. Arithmetic-geometric mean M(a,b) at algebraic arguments
  4. Modular lambda function λ(τ) at τ = (1+√-11)/2
  5. Theta function ratios θ₃/θ₂ at conductor-11 q-values
  6. Dedekind eta quotients η(τ)/η(11τ)

Usage:
    python vquad_elliptic_scanner.py
    python vquad_elliptic_scanner.py --prec 500 --grid-size 4
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from fractions import Fraction

import mpmath as mp

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def compute_vquad(dps, n_terms=5000):
    with mp.workdps(dps + 100):
        val = mp.mpf(0)
        tol = mp.mpf(10) ** -(dps + 80)
        for n in range(n_terms, 0, -1):
            bn = 3 * mp.mpf(n)**2 + mp.mpf(n) + 1
            denom = bn + val
            if abs(denom) < tol:
                return None
            val = mp.mpf(1) / denom
        return mp.mpf(1) + val


def _pslq_test(vec, dps, maxcoeff=10000):
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


def _is_real(val):
    """Check if a value is real (not complex)."""
    if isinstance(val, mp.mpc):
        return abs(val.imag) < 1e-20
    return True


def _to_real(val):
    if isinstance(val, mp.mpc):
        return mp.re(val)
    return val


def scan_elliptic_K(vquad, dps, grid_size=4):
    """Scan complete elliptic integral K(m) at CM moduli."""
    results = []
    pslq_dps = max(80, dps // 3)

    # CM moduli: m values with complex multiplication
    # Key: m related to discriminant -11 class field
    cm_moduli = {}
    with mp.workdps(dps + 20):
        # Standard CM points
        cm_moduli["1/2"] = mp.mpf(1) / 2
        cm_moduli["(3-sqrt(5))/8"] = (3 - mp.sqrt(5)) / 8
        cm_moduli["(3+sqrt(5))/8"] = (3 + mp.sqrt(5)) / 8
        # Conductor-11 related
        cm_moduli["1/11"] = mp.mpf(1) / 11
        cm_moduli["11/12"] = mp.mpf(11) / 12
        cm_moduli["(11-3*sqrt(11))/22"] = (11 - 3 * mp.sqrt(11)) / 22
        # Singular moduli for discriminant -11
        # j(-11) = -32³ = -32768, related modulus via j → m
        # Using Ramanujan-type singular modulus approximations
        cm_moduli["sin(pi/11)^2"] = mp.sin(mp.pi / 11)**2
        cm_moduli["sin(pi/3)^2"] = mp.sin(mp.pi / 3)**2
        # Rational grid for completeness
        for k in range(1, grid_size + 1):
            for d in range(2, 2 * grid_size + 1):
                if 0 < k < d:
                    label = f"{k}/{d}"
                    cm_moduli[label] = mp.mpf(k) / d

    print(f"  Scanning K(m) at {len(cm_moduli)} moduli...")
    tested = 0
    for label, m in cm_moduli.items():
        try:
            with mp.workdps(dps + 20):
                k_val = mp.ellipk(m)
            if k_val is None or not _is_real(k_val) or not mp.isfinite(_to_real(k_val)):
                continue
            k_val = _to_real(k_val)
        except Exception:
            continue

        tested += 1
        # Test: a·V_quad + b·K(m) + c = 0
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(k_val), mp.mpf(1)]
            rel, prec = _pslq_test(vec, pslq_dps)
        if rel and prec >= 15 and rel[1] != 0:
            results.append({
                "type": "elliptic_K", "modulus": label,
                "relation": [int(r) for r in rel], "precision": prec,
                "k_value": mp.nstr(k_val, 20),
                "status": "MATCH" if prec >= dps // 4 else "near_miss",
            })

        # Also test: a·V_quad + b·K(m)/π + c = 0 (common normalization)
        with mp.workdps(pslq_dps):
            k_norm = mp.mpf(k_val) / mp.pi
            vec2 = [mp.mpf(vquad), mp.mpf(k_norm), mp.mpf(1)]
            rel2, prec2 = _pslq_test(vec2, pslq_dps)
        if rel2 and prec2 >= 15 and rel2[1] != 0:
            results.append({
                "type": "elliptic_K/pi", "modulus": label,
                "relation": [int(r) for r in rel2], "precision": prec2,
                "status": "MATCH" if prec2 >= dps // 4 else "near_miss",
            })

    print(f"    Tested {tested} K(m) evaluations")
    return results


def scan_elliptic_E(vquad, dps, grid_size=4):
    """Scan complete elliptic integral E(m) at select moduli."""
    results = []
    pslq_dps = max(80, dps // 3)

    moduli = {}
    with mp.workdps(dps + 20):
        moduli["1/2"] = mp.mpf(1) / 2
        moduli["1/11"] = mp.mpf(1) / 11
        moduli["sin(pi/11)^2"] = mp.sin(mp.pi / 11)**2
        for k in range(1, grid_size + 1):
            for d in range(2, 2 * grid_size + 1):
                if 0 < k < d:
                    moduli[f"{k}/{d}"] = mp.mpf(k) / d

    print(f"  Scanning E(m) at {len(moduli)} moduli...")
    tested = 0
    for label, m in moduli.items():
        try:
            with mp.workdps(dps + 20):
                e_val = mp.ellipe(m)
            if e_val is None or not _is_real(e_val) or not mp.isfinite(_to_real(e_val)):
                continue
            e_val = _to_real(e_val)
        except Exception:
            continue

        tested += 1
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(e_val), mp.mpf(1)]
            rel, prec = _pslq_test(vec, pslq_dps)
        if rel and prec >= 15 and rel[1] != 0:
            results.append({
                "type": "elliptic_E", "modulus": label,
                "relation": [int(r) for r in rel], "precision": prec,
                "e_value": mp.nstr(e_val, 20),
                "status": "MATCH" if prec >= dps // 4 else "near_miss",
            })

    print(f"    Tested {tested} E(m) evaluations")
    return results


def scan_agm(vquad, dps, grid_size=3):
    """Scan arithmetic-geometric mean M(a,b) at algebraic arguments."""
    results = []
    pslq_dps = max(80, dps // 3)

    pairs = []
    with mp.workdps(dps + 20):
        # Standard AGM pairs related to elliptic functions
        pairs.append(("1,sqrt(2)", mp.mpf(1), mp.sqrt(2)))
        pairs.append(("1,sqrt(11)", mp.mpf(1), mp.sqrt(11)))
        pairs.append(("1,sqrt(11)/3", mp.mpf(1), mp.sqrt(11) / 3))
        pairs.append(("sqrt(2),sqrt(3)", mp.sqrt(2), mp.sqrt(3)))
        pairs.append(("1,2", mp.mpf(1), mp.mpf(2)))
        pairs.append(("1,3", mp.mpf(1), mp.mpf(3)))
        for d in range(2, 3 * grid_size):
            pairs.append((f"1,sqrt({d})", mp.mpf(1), mp.sqrt(d)))

    print(f"  Scanning AGM at {len(pairs)} pairs...")
    tested = 0
    for label, a, b in pairs:
        try:
            with mp.workdps(dps + 20):
                agm_val = mp.agm(a, b)
            if agm_val is None or not mp.isfinite(agm_val):
                continue
        except Exception:
            continue

        tested += 1
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(agm_val), mp.mpf(1)]
            rel, prec = _pslq_test(vec, pslq_dps)
        if rel and prec >= 15 and rel[1] != 0:
            results.append({
                "type": "agm", "pair": label,
                "relation": [int(r) for r in rel], "precision": prec,
                "agm_value": mp.nstr(agm_val, 20),
                "status": "MATCH" if prec >= dps // 4 else "near_miss",
            })

    print(f"    Tested {tested} AGM evaluations")
    return results


def scan_theta_eta(vquad, dps):
    """Scan theta functions and Dedekind eta quotients at conductor-11 τ values."""
    results = []
    pslq_dps = max(80, dps // 3)

    tau_values = {}
    with mp.workdps(dps + 50):
        # Key τ values for conductor 11
        tau_values["(1+sqrt(-11))/2"] = (1 + mp.sqrt(-11)) / 2
        tau_values["sqrt(-11)"] = mp.sqrt(-11)
        tau_values["(1+sqrt(-11))/6"] = (1 + mp.sqrt(-11)) / 6
        tau_values["sqrt(-11)/2"] = mp.sqrt(-11) / 2

    print(f"  Scanning theta/eta at {len(tau_values)} τ values...")
    tested = 0

    for label, tau in tau_values.items():
        try:
            with mp.workdps(dps + 50):
                q = mp.exp(2 * mp.pi * mp.j * tau)
                if abs(q) >= 1:
                    continue

                # Jacobi theta functions
                th2 = mp.jtheta(2, 0, q)
                th3 = mp.jtheta(3, 0, q)
                th4 = mp.jtheta(4, 0, q)

                for th_name, th_val in [("theta3", th3), ("theta2", th2), ("theta4", th4)]:
                    if th_val is None or not _is_real(th_val) or abs(th_val) < 1e-30:
                        continue
                    th_real = _to_real(th_val)
                    if not mp.isfinite(th_real):
                        continue
                    tested += 1
                    with mp.workdps(pslq_dps):
                        vec = [mp.mpf(vquad), mp.mpf(th_real), mp.mpf(1)]
                        rel, prec = _pslq_test(vec, pslq_dps)
                    if rel and prec >= 15 and rel[1] != 0:
                        results.append({
                            "type": f"{th_name}", "tau": label,
                            "relation": [int(r) for r in rel], "precision": prec,
                            "status": "MATCH" if prec >= dps // 4 else "near_miss",
                        })

                # Theta ratios
                if abs(th2) > 1e-30 and _is_real(th3) and _is_real(th2):
                    ratio = _to_real(th3) / _to_real(th2)
                    if mp.isfinite(ratio):
                        tested += 1
                        with mp.workdps(pslq_dps):
                            vec = [mp.mpf(vquad), mp.mpf(ratio), mp.mpf(1)]
                            rel, prec = _pslq_test(vec, pslq_dps)
                        if rel and prec >= 15 and rel[1] != 0:
                            results.append({
                                "type": "theta3/theta2", "tau": label,
                                "relation": [int(r) for r in rel], "precision": prec,
                                "status": "MATCH" if prec >= dps // 4 else "near_miss",
                            })

                # Dedekind eta: η(τ) via q^{1/24} product
                # η(τ) = q^{1/24} Π_{n≥1} (1-q^n)
                eta_val = mp.exp(2 * mp.pi * mp.j * tau / 24)
                for nn in range(1, 200):
                    eta_val *= (1 - q**nn)
                eta11 = mp.exp(2 * mp.pi * mp.j * (11 * tau) / 24)
                q11 = q**11
                for nn in range(1, 50):
                    eta11 *= (1 - q11**nn)

                if abs(eta11) > 1e-30 and _is_real(eta_val / eta11):
                    eta_ratio = _to_real(eta_val / eta11)
                    if mp.isfinite(eta_ratio):
                        tested += 1
                        with mp.workdps(pslq_dps):
                            vec = [mp.mpf(vquad), mp.mpf(eta_ratio), mp.mpf(1)]
                            rel, prec = _pslq_test(vec, pslq_dps)
                        if rel and prec >= 15 and rel[1] != 0:
                            results.append({
                                "type": "eta(tau)/eta(11*tau)", "tau": label,
                                "relation": [int(r) for r in rel], "precision": prec,
                                "status": "MATCH" if prec >= dps // 4 else "near_miss",
                            })

        except Exception:
            continue

    print(f"    Tested {tested} theta/eta evaluations")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="V_quad elliptic integral / modular function scanner.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--prec", type=int, default=500)
    parser.add_argument("--grid-size", type=int, default=4)
    parser.add_argument("--json-out", default="vquad_elliptic_scan.json")
    args = parser.parse_args()

    dps = args.prec
    mp.mp.dps = dps + 100

    print(f"{'='*60}")
    print(f"  V_quad Elliptic / Modular Scanner")
    print(f"{'='*60}")
    print(f"  Precision: {dps}dp  Grid: {args.grid_size}")
    t0 = time.perf_counter()

    print("\n[0] Computing V_quad...")
    vquad = compute_vquad(dps)
    print(f"  V_quad = {mp.nstr(vquad, 40)}")

    all_results = []

    print("\n[1] Elliptic K(m) scan...")
    k_results = scan_elliptic_K(vquad, dps, args.grid_size)
    all_results.extend(k_results)
    matches = sum(1 for r in k_results if r["status"] == "MATCH")
    print(f"    Matches: {matches}  Near-misses: {len(k_results) - matches}")

    print("\n[2] Elliptic E(m) scan...")
    e_results = scan_elliptic_E(vquad, dps, args.grid_size)
    all_results.extend(e_results)
    matches = sum(1 for r in e_results if r["status"] == "MATCH")
    print(f"    Matches: {matches}  Near-misses: {len(e_results) - matches}")

    print("\n[3] Arithmetic-Geometric Mean scan...")
    agm_results = scan_agm(vquad, dps, args.grid_size)
    all_results.extend(agm_results)
    matches = sum(1 for r in agm_results if r["status"] == "MATCH")
    print(f"    Matches: {matches}  Near-misses: {len(agm_results) - matches}")

    print("\n[4] Theta / Dedekind eta scan (conductor 11)...")
    theta_results = scan_theta_eta(vquad, dps)
    all_results.extend(theta_results)
    matches = sum(1 for r in theta_results if r["status"] == "MATCH")
    print(f"    Matches: {matches}  Near-misses: {len(theta_results) - matches}")

    wall = round(time.perf_counter() - t0, 3)

    output = {
        "scanner": "vquad_elliptic",
        "precision": dps,
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
    print(f"  V_quad Elliptic Scan Report")
    print(f"{'='*60}")
    print(f"  MATCHES:      {len(output['matches'])}")
    print(f"  Near-misses:  {len(output['near_misses'])}")
    print(f"  Wall time:    {wall}s")

    if output["matches"]:
        print(f"\n  *** MATCHES — V_quad may be an elliptic/modular value! ***")
        for m in output["matches"]:
            print(f"    {m['type']}  param={m.get('modulus','')}{m.get('pair','')}"
                  f"{m.get('tau','')}  rel={m['relation']}  prec={m['precision']}dp")
    else:
        print(f"\n  No elliptic/modular matches. V_quad isolation strengthened further.")

    print(f"\n  JSON -> {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
