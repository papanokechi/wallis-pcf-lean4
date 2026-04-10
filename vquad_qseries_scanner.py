#!/usr/bin/env python3
"""V_quad q-Series and Modular Form Scanner.

After eliminating D-finite, hypergeometric, elliptic, and Meijer G families,
the next natural function class to test is:
  1. q-series: f(q) = Σ a_n q^n at specific modular points q = e^{2πiτ}
  2. Mock modular forms (Ramanujan's mock theta functions)
  3. Eta products η(τ)^a η(kτ)^b at conductors 11, 24, 44
  4. Eisenstein series E_k(τ) at CM and Heegner points
  5. Atkin-Lehner eigenforms at level 11 and 24

The discriminant Δ=-11 connection suggests looking at:
  - Weight-2 newform f₁₁ on Γ₀(11) (= 11a1's modular parametrization)
  - Weight-3/2 forms on Γ₀(44) (Shimura lifts to level 11)
  - Hecke L-values L(f₁₁, χ, s) with quadratic twists

Usage:
    python vquad_qseries_scanner.py
    python vquad_qseries_scanner.py --prec 500 --conductor-levels 11,24,44
"""
from __future__ import annotations

import argparse
import json
import math
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


def _is_real_finite(val):
    if isinstance(val, mp.mpc):
        if abs(val.imag) > 1e-20:
            return False
        val = mp.re(val)
    return mp.isfinite(val) and val != 0


def _to_real(val):
    if isinstance(val, mp.mpc):
        return mp.re(val)
    return val


def scan_eta_products(vquad, dps, conductor_levels):
    """Scan Dedekind eta products at various conductor levels.

    η(τ) = q^{1/24} Π_{n≥1}(1-q^n), where q = e^{2πiτ}

    Test eta products of the form η(τ)^a · η(kτ)^b for small a,b
    and k | N at CM/Heegner points τ.
    """
    results = []
    pslq_dps = max(80, dps // 3)

    # CM points relevant to discriminant -11
    tau_points = {}
    with mp.workdps(dps + 100):
        # Primary Heegner point for discriminant -11
        tau_points["(1+sqrt(-11))/2"] = (1 + mp.j * mp.sqrt(11)) / 2
        # Other CM points
        tau_points["sqrt(-11)/2"] = mp.j * mp.sqrt(11) / 2
        tau_points["(1+sqrt(-11))/6"] = (1 + mp.j * mp.sqrt(11)) / 6
        # Level-24 related
        tau_points["(1+sqrt(-3))/2"] = (1 + mp.j * mp.sqrt(3)) / 2
        tau_points["sqrt(-6)"] = mp.j * mp.sqrt(6)

    print(f"  Scanning eta products at {len(tau_points)} tau points...")
    tested = 0

    def _compute_eta(tau, n_terms=300):
        """Compute η(τ) numerically."""
        with mp.workdps(dps + 100):
            q = mp.exp(2 * mp.pi * mp.j * tau)
            if abs(q) >= 1:
                return None
            result = q ** (mp.mpf(1) / 24)
            for n in range(1, n_terms + 1):
                term = 1 - q**n
                if abs(term) < mp.mpf(10) ** -(dps + 50):
                    break
                result *= term
            return result

    for tau_label, tau in tau_points.items():
        with mp.workdps(dps + 100):
            q = mp.exp(2 * mp.pi * mp.j * tau)
            if abs(q) >= 1:
                continue

        for N in conductor_levels:
            # Compute η(τ) and η(Nτ)
            eta1 = _compute_eta(tau)
            eta_N = _compute_eta(N * tau)
            if eta1 is None or eta_N is None:
                continue

            # Test various eta products/quotients
            for a in range(-4, 5):
                for b in range(-4, 5):
                    if a == 0 and b == 0:
                        continue
                    try:
                        with mp.workdps(dps + 50):
                            if a >= 0 and b >= 0:
                                val = eta1**a * eta_N**b
                            elif a >= 0:
                                val = eta1**a / eta_N**(-b)
                            elif b >= 0:
                                val = eta_N**b / eta1**(-a)
                            else:
                                val = 1 / (eta1**(-a) * eta_N**(-b))

                        if not _is_real_finite(val):
                            continue
                        val = _to_real(val)
                    except Exception:
                        continue

                    tested += 1
                    with mp.workdps(pslq_dps):
                        vec = [mp.mpf(vquad), mp.mpf(val), mp.mpf(1)]
                        rel, prec = _pslq_test(vec, pslq_dps)

                    if rel and prec >= 15 and rel[1] != 0:
                        results.append({
                            "type": "eta_product",
                            "tau": tau_label,
                            "conductor": N,
                            "exponents": {"a": a, "b": b},
                            "relation": [int(r) for r in rel],
                            "precision": prec,
                            "status": "MATCH" if prec >= dps // 4 else "near_miss",
                        })

    print(f"    Tested {tested} eta product evaluations")
    return results


def scan_eisenstein(vquad, dps, conductor_levels):
    """Scan Eisenstein series E_k(τ) at CM points."""
    results = []
    pslq_dps = max(80, dps // 3)

    tau_points = {}
    with mp.workdps(dps + 100):
        tau_points["(1+sqrt(-11))/2"] = (1 + mp.j * mp.sqrt(11)) / 2
        tau_points["sqrt(-11)/2"] = mp.j * mp.sqrt(11) / 2

    print(f"  Scanning Eisenstein E_k(tau) at CM points...")
    tested = 0

    for tau_label, tau in tau_points.items():
        with mp.workdps(dps + 100):
            q = mp.exp(2 * mp.pi * mp.j * tau)
            if abs(q) >= 1:
                continue

            # E_2(τ) = 1 - 24·Σ σ₁(n)q^n
            # E_4(τ) = 1 + 240·Σ σ₃(n)q^n
            # E_6(τ) = 1 - 504·Σ σ₅(n)q^n
            for k_label, k_mult, sigma_exp in [("E2", -24, 1), ("E4", 240, 3), ("E6", -504, 5)]:
                val = mp.mpf(1)
                for n in range(1, 200):
                    # σ_s(n) = Σ_{d|n} d^s
                    sigma = sum(d**sigma_exp for d in range(1, n + 1) if n % d == 0)
                    val += k_mult * sigma * q**n
                    if abs(q**n) < mp.mpf(10) ** -(dps + 20):
                        break

                if not _is_real_finite(val):
                    continue
                val = _to_real(val)
                tested += 1

                with mp.workdps(pslq_dps):
                    vec = [mp.mpf(vquad), mp.mpf(val), mp.mpf(1)]
                    rel, prec = _pslq_test(vec, pslq_dps)

                if rel and prec >= 15 and rel[1] != 0:
                    results.append({
                        "type": "eisenstein",
                        "series": k_label,
                        "tau": tau_label,
                        "relation": [int(r) for r in rel],
                        "precision": prec,
                        "status": "MATCH" if prec >= dps // 4 else "near_miss",
                    })

    print(f"    Tested {tested} Eisenstein evaluations")
    return results


def scan_mock_theta(vquad, dps):
    """Scan Ramanujan's mock theta functions at conductor-11 q-values.

    Third-order mock theta functions:
      f(q) = Σ_{n≥0} q^{n²} / (1+q)²(1+q²)²...(1+q^n)²
      φ(q) = Σ_{n≥0} q^{n²} / (1+q²)(1+q⁴)...(1+q^{2n})
      ψ(q) = Σ_{n≥1} q^{n²} / (1-q)(1-q³)...(1-q^{2n-1})
    """
    results = []
    pslq_dps = max(80, dps // 3)

    # q-values at CM points
    q_values = {}
    with mp.workdps(dps + 100):
        for tau_label, tau in [
            ("(1+sqrt(-11))/2", (1 + mp.j * mp.sqrt(11)) / 2),
            ("sqrt(-11)/2", mp.j * mp.sqrt(11) / 2),
            ("(1+sqrt(-3))/2", (1 + mp.j * mp.sqrt(3)) / 2),
        ]:
            q = mp.exp(2 * mp.pi * mp.j * tau)
            if abs(q) < 1:
                q_values[tau_label] = q

    print(f"  Scanning mock theta functions at {len(q_values)} q-values...")
    tested = 0

    for q_label, q in q_values.items():
        with mp.workdps(dps + 100):
            # f(q): third-order mock theta
            try:
                f_val = mp.mpf(0)
                for n in range(0, 60):
                    num = q**(n * n)
                    denom = mp.mpf(1)
                    for k in range(1, n + 1):
                        denom *= (1 + q**k)**2
                    if abs(denom) < mp.mpf(10) ** -(dps + 30):
                        break
                    f_val += num / denom

                if _is_real_finite(f_val):
                    f_val = _to_real(f_val)
                    tested += 1
                    with mp.workdps(pslq_dps):
                        vec = [mp.mpf(vquad), mp.mpf(f_val), mp.mpf(1)]
                        rel, prec = _pslq_test(vec, pslq_dps)
                    if rel and prec >= 15 and rel[1] != 0:
                        results.append({
                            "type": "mock_theta_f", "q_point": q_label,
                            "relation": [int(r) for r in rel], "precision": prec,
                            "status": "MATCH" if prec >= dps // 4 else "near_miss",
                        })
            except Exception:
                pass

            # ψ(q): third-order mock theta
            try:
                psi_val = mp.mpf(0)
                for n in range(1, 60):
                    num = q**(n * n)
                    denom = mp.mpf(1)
                    for k in range(1, n + 1):
                        denom *= (1 - q**(2*k - 1))
                    if abs(denom) < mp.mpf(10) ** -(dps + 30):
                        break
                    psi_val += num / denom

                if _is_real_finite(psi_val):
                    psi_val = _to_real(psi_val)
                    tested += 1
                    with mp.workdps(pslq_dps):
                        vec = [mp.mpf(vquad), mp.mpf(psi_val), mp.mpf(1)]
                        rel, prec = _pslq_test(vec, pslq_dps)
                    if rel and prec >= 15 and rel[1] != 0:
                        results.append({
                            "type": "mock_theta_psi", "q_point": q_label,
                            "relation": [int(r) for r in rel], "precision": prec,
                            "status": "MATCH" if prec >= dps // 4 else "near_miss",
                        })
            except Exception:
                pass

    print(f"    Tested {tested} mock theta evaluations")
    return results


def scan_modular_j(vquad, dps):
    """Scan the j-invariant and its roots at Heegner points.

    j((1+√-11)/2) = -32³ = -32768
    But we test j^{1/3}, j^{1/2}, and related singular moduli.
    """
    results = []
    pslq_dps = max(80, dps // 3)

    with mp.workdps(dps + 50):
        # j-invariant at Heegner point for D=-11
        # j(-11) = -32768 exactly (class number 1)
        j_val = mp.mpf(-32768)

        test_values = {
            "j(-11)": j_val,
            "j(-11)^(1/3)": mp.cbrt(abs(j_val)) * (-1),  # -32
            "|j(-11)|^(1/2)": mp.sqrt(abs(j_val)),  # 128√2
            "1/j(-11)": 1 / j_val,
            "j(-11) + 744": j_val + 744,  # j = q^-1 + 744 + ...
        }

    print(f"  Scanning j-invariant values at D=-11...")
    tested = 0
    for label, val in test_values.items():
        if not mp.isfinite(val) or val == 0:
            continue
        tested += 1
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(val), mp.mpf(1)]
            rel, prec = _pslq_test(vec, pslq_dps)
        if rel and prec >= 15 and rel[1] != 0:
            results.append({
                "type": "j_invariant", "quantity": label,
                "relation": [int(r) for r in rel], "precision": prec,
                "status": "MATCH" if prec >= dps // 4 else "near_miss",
            })

    print(f"    Tested {tested} j-invariant evaluations")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="V_quad q-series and modular form scanner.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--prec", type=int, default=500)
    parser.add_argument("--conductor-levels", default="11,24,44")
    parser.add_argument("--json-out", default="vquad_qseries_scan.json")
    args = parser.parse_args()

    dps = args.prec
    mp.mp.dps = dps + 200
    conductors = [int(c) for c in args.conductor_levels.split(",")]

    print(f"{'='*60}")
    print(f"  V_quad q-Series / Modular Form Scanner")
    print(f"{'='*60}")
    print(f"  Precision: {dps}dp")
    print(f"  Conductors: {conductors}")
    t0 = time.perf_counter()

    print("\n[0] Computing V_quad...")
    vquad = compute_vquad(dps)
    print(f"  V_quad = {mp.nstr(vquad, 40)}")

    all_results = []

    print("\n[1] Eta product scan...")
    eta_results = scan_eta_products(vquad, dps, conductors)
    all_results.extend(eta_results)
    m = sum(1 for r in eta_results if r["status"] == "MATCH")
    print(f"    Matches: {m}  Near-misses: {len(eta_results) - m}")

    print("\n[2] Eisenstein series scan...")
    eis_results = scan_eisenstein(vquad, dps, conductors)
    all_results.extend(eis_results)
    m = sum(1 for r in eis_results if r["status"] == "MATCH")
    print(f"    Matches: {m}  Near-misses: {len(eis_results) - m}")

    print("\n[3] Mock theta function scan...")
    mock_results = scan_mock_theta(vquad, dps)
    all_results.extend(mock_results)
    m = sum(1 for r in mock_results if r["status"] == "MATCH")
    print(f"    Matches: {m}  Near-misses: {len(mock_results) - m}")

    print("\n[4] j-invariant scan...")
    j_results = scan_modular_j(vquad, dps)
    all_results.extend(j_results)
    m = sum(1 for r in j_results if r["status"] == "MATCH")
    print(f"    Matches: {m}  Near-misses: {len(j_results) - m}")

    wall = round(time.perf_counter() - t0, 3)

    output = {
        "scanner": "vquad_qseries_modular",
        "precision": dps,
        "conductors": conductors,
        "vquad": mp.nstr(vquad, 50),
        "total_results": len(all_results),
        "matches": [r for r in all_results if r["status"] == "MATCH"],
        "near_misses": [r for r in all_results if r["status"] == "near_miss"],
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    total_matches = len(output["matches"])
    total_nm = len(output["near_misses"])

    print(f"\n{'='*60}")
    print(f"  V_quad q-Series / Modular Scan Report")
    print(f"{'='*60}")
    print(f"  MATCHES:      {total_matches}")
    print(f"  Near-misses:  {total_nm}")
    print(f"  Wall time:    {wall}s")

    if total_matches > 0:
        print(f"\n  *** MODULAR MATCHES FOUND ***")
        for m in output["matches"]:
            print(f"    {m['type']}  {m.get('tau','')}{m.get('q_point','')}"
                  f"{m.get('quantity','')}  rel={m['relation']}  prec={m['precision']}dp")
    elif total_nm > 0:
        print(f"\n  Near-misses (investigate further):")
        for nm in output["near_misses"][:10]:
            print(f"    {nm['type']}  prec={nm['precision']}dp")
    else:
        print(f"\n  V_quad is independent of all tested modular forms.")
        print(f"  Exclusion list now includes: eta products, Eisenstein series,")
        print(f"  mock theta functions, and j-invariant values at D=-11.")

    print(f"\n  JSON -> {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
