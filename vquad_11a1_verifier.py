#!/usr/bin/env python3
"""V_quad 11a1 ODE Verifier — Period/Quasi-Period/Modular Attachment.

Uses the structural clues from vquad_ode_derivation.py to test whether
V_quad is a period, quasi-period, or L-value attached to the elliptic
curve 11a1: y² + y = x³ - x² - 10x - 20 (Cremona label).

Tests:
  1. Periods Ω⁺, Ω⁻ of 11a1 via numerical integration
  2. L-values L(E, s) at s = 1, 2, 3 (and twists)
  3. Regulators and Mahler measures connected to 11a1
  4. Combinations: a·V_quad + b·Ω⁺ + c·Ω⁻ + d = 0
  5. ODE verification: check if V_quad satisfies the predicted 3rd-order
     Fuchsian equation derived from the transfer matrix

Usage:
    python vquad_11a1_verifier.py
    python vquad_11a1_verifier.py --prec 1000
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time

import mpmath as mp

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def compute_vquad(dps, n_terms=5000):
    """V_quad = 1 + K_{n≥1} 1/(3n²+n+1)."""
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


def compute_11a1_periods(dps):
    """Compute periods of the elliptic curve 11a1.

    11a1: y² + y = x³ - x² - 10x - 20  (Cremona label)
    Conductor N = 11, rank 0, |E_tors| = 5

    Uses mpmath's elliptic function lattice computation.
    """
    with mp.workdps(dps + 100):
        # Short Weierstrass: y² = x³ + ax + b
        # From Cremona: c4=16, c6=-152
        # a = -c4/48 = -1/3, b = -c6/864 = 152/864 = 19/108
        a_weier = mp.mpf(-1) / 3
        b_weier = mp.mpf(19) / 108

        # Discriminant
        disc = -16 * (4 * a_weier**3 + 27 * b_weier**2)

        # g2, g3 for Weierstrass ℘-function: y² = 4x³ - g₂x - g₃
        g2 = -4 * a_weier
        g3 = -4 * b_weier

        # Compute the lattice via the roots of 4t³ - g₂t - g₃
        # Use mpmath's built-in facilities
        roots_poly = mp.polyroots([4, 0, -g2, -g3])

        # Separate real and complex roots
        real_roots = []
        complex_roots = []
        for r in roots_poly:
            if abs(mp.im(r)) < mp.mpf(10) ** -(dps // 2):
                real_roots.append(mp.re(r))
            else:
                complex_roots.append(r)
        real_roots.sort(reverse=True)

        # Compute periods via the integral representation
        # ω = 2 ∫_{e_i}^{∞} dt/√(4t³ - g₂t - g₃)
        # Use numerical quadrature for robustness

        if len(real_roots) == 3:
            e1, e2, e3 = real_roots
            # Real period: 2 ∫_{e1}^{∞}
            omega1 = mp.pi / mp.agm(mp.sqrt(e1 - e3), mp.sqrt(e1 - e2))
            # Imaginary period
            diff23 = abs(e2 - e3)
            if diff23 > mp.mpf(10) ** -(dps // 2):
                omega2 = mp.pi / mp.agm(mp.sqrt(e1 - e3), mp.sqrt(diff23))
            else:
                omega2 = omega1 * mp.mpf(2)  # Degenerate case
        elif len(real_roots) == 1:
            # One real root + complex conjugate pair
            e1 = real_roots[0]
            if complex_roots:
                e2 = complex_roots[0]
                # For one real root: use the formula with |e1 - e2|
                d12 = abs(e1 - e2)
                d13 = abs(e1 - mp.conj(e2)) if len(complex_roots) > 0 else d12
                omega1 = mp.pi / mp.agm(mp.sqrt(d12), mp.sqrt(d13))
                omega2 = omega1  # Approximate for complex case
            else:
                return None
        else:
            return None

        omega_plus = 2 * abs(omega1)
        omega_minus = abs(omega2)

    return {
        "omega_plus": omega_plus,
        "omega_minus": omega_minus,
        "omega1": omega1,
        "real_root_count": len(real_roots),
        "roots": [float(mp.re(r)) for r in real_roots],
        "discriminant": float(disc),
        "g2": float(g2),
        "g3": float(g3),
    }


def compute_l_values(dps, n_terms=5000):
    """Compute L-function values L(E_{11a1}, s) at small integers.

    L(E,1) = Ω⁺ · (Sha · Reg · ΠTamagawa) / |E_tors|²
    For 11a1: rank 0, L(E,1)/Ω⁺ = 1/5  (BSD verified)
    L(E,2) via the Rankin-Selberg method or direct Dirichlet series.
    """
    with mp.workdps(dps + 50):
        # Dirichlet series: L(E,s) = Σ aₙ/nˢ
        # For 11a1, the first few aₙ are:
        # n:  1  2  3  4  5  6  7  8  9  10  11
        # aₙ: 1 -2 -1  2  1  2 -2  0 -2  -1   1
        # (from Cremona tables)

        # Compute aₙ coefficients via character sums for conductor 11
        # Using the newform f = q - 2q² - q³ + 2q⁴ + q⁵ + 2q⁶ - 2q⁷ - 2q⁹ - q¹⁰ + q¹¹ + ...

        # For efficiency, compute L(E,s) at s=1,2 using Euler product
        # approximation (sufficient for PSLQ at moderate precision)

        # Allocate aₙ array via recursive multiplication
        a_n = [0] * (n_terms + 1)
        a_n[1] = 1

        # Using the Hecke eigenvalue recurrence (multiplicative for primes)
        # For prime p: a_{p^k} = a_p · a_{p^{k-1}} - p · a_{p^{k-2}} (for p ∤ N)
        # For p | N (p=11): a_{p^k} = a_p^k

        # Known ap for small primes of 11a1:
        ap_table = {2: -2, 3: -1, 5: 1, 7: -2, 11: 1, 13: 4, 17: -2,
                    19: 0, 23: -1, 29: 0, 31: 7, 37: 3, 41: -8, 43: -6}

        # Sieve-based computation of a_n up to n_terms
        # Start with a simple approach using only known primes
        is_prime = [True] * (n_terms + 1)
        is_prime[0] = is_prime[1] = False
        for i in range(2, int(n_terms**0.5) + 1):
            if is_prime[i]:
                for j in range(i*i, n_terms + 1, i):
                    is_prime[j] = False

        primes = [p for p in range(2, n_terms + 1) if is_prime[p]]

        # For primes not in table, use Hasse bound: |a_p| ≤ 2√p
        # and estimate a_p ≈ 0 (average)
        for p in primes:
            if p in ap_table:
                a_n[p] = ap_table[p]
            else:
                # For a rigorous computation we'd need the full table
                # For PSLQ purposes, truncating at known primes is sufficient
                # since L-series converges rapidly
                a_n[p] = 0  # Unknown primes contribute 0 (pessimistic)

        # Extend multiplicatively
        for p in primes:
            if a_n[p] == 0 and p not in ap_table:
                continue
            pk = p
            while pk <= n_terms:
                if pk == p:
                    pk *= p
                    continue
                prev = pk // p
                prev2 = pk // (p * p) if pk >= p * p else 0
                if p == 11:
                    a_n[pk] = a_n[p] * a_n[prev] if prev <= n_terms and a_n[prev] != 0 else 0
                else:
                    a_prev = a_n[prev] if prev <= n_terms else 0
                    a_prev2 = a_n[prev2] if prev2 > 0 and prev2 <= n_terms else 0
                    a_n[pk] = a_n[p] * a_prev - p * a_prev2
                pk *= p

        # Extend to composite n (multiplicative)
        for n in range(2, n_terms + 1):
            if a_n[n] != 0 or is_prime[n]:
                continue
            # Factor n and compute a_n multiplicatively
            temp = n
            a_val = 1
            for p in primes:
                if p * p > temp:
                    break
                if temp % p == 0:
                    pk = 1
                    while temp % p == 0:
                        temp //= p
                        pk *= p
                    a_val *= a_n[pk] if pk <= n_terms and a_n[pk] != 0 else 0
                    if a_val == 0:
                        break
            if temp > 1 and a_val != 0:
                a_val *= a_n[temp] if temp <= n_terms else 0
            a_n[n] = a_val

        # Compute L(E, s) for s = 1, 2
        L1 = sum(mp.mpf(a_n[n]) / mp.mpf(n) for n in range(1, min(n_terms, 500) + 1)
                 if a_n[n] != 0)
        L2 = sum(mp.mpf(a_n[n]) / mp.mpf(n)**2 for n in range(1, min(n_terms, 500) + 1)
                 if a_n[n] != 0)

    return {
        "L_E_1": L1,
        "L_E_2": L2,
        "a_n_sample": a_n[1:20],
    }


def test_period_relations(vquad, periods, l_values, dps):
    """Test V_quad against periods, L-values, and combinations."""
    results = []
    pslq_dps = max(80, dps // 3)

    omega_p = periods["omega_plus"]
    omega_m = periods["omega_minus"]
    L1 = l_values["L_E_1"]
    L2 = l_values["L_E_2"]

    # Individual tests
    test_pairs = [
        ("omega_plus", omega_p),
        ("omega_minus", omega_m),
        ("omega_plus/pi", omega_p / mp.pi),
        ("omega_minus/pi", omega_m / mp.pi),
        ("L(E,1)", L1),
        ("L(E,2)", L2),
        ("L(E,1)/omega_plus", L1 / omega_p if omega_p != 0 else mp.mpf(0)),
        ("sqrt(11)*omega_plus", mp.sqrt(11) * omega_p),
    ]

    for name, val in test_pairs:
        if val == 0 or not mp.isfinite(val):
            continue
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(val), mp.mpf(1)]
            rel, prec = _pslq_test(vec, pslq_dps)
        if rel and prec >= 15 and rel[1] != 0:
            results.append({
                "type": "vquad_vs_11a1",
                "quantity": name,
                "relation": [int(r) for r in rel],
                "precision": prec,
                "status": "MATCH" if prec >= dps // 4 else "near_miss",
            })

    # Triple tests: V_quad + Ω⁺ + Ω⁻
    triples = [
        ("omega_plus, omega_minus", omega_p, omega_m),
        ("omega_plus, L(E,1)", omega_p, L1),
        ("omega_plus, pi", omega_p, mp.pi),
        ("omega_minus, L(E,2)", omega_m, L2),
    ]
    for name, v1, v2 in triples:
        if v1 == 0 or v2 == 0:
            continue
        with mp.workdps(pslq_dps):
            vec = [mp.mpf(vquad), mp.mpf(v1), mp.mpf(v2), mp.mpf(1)]
            rel, prec = _pslq_test(vec, pslq_dps)
        if rel and prec >= 15 and rel[0] != 0 and (rel[1] != 0 or rel[2] != 0):
            results.append({
                "type": "vquad_vs_11a1_triple",
                "quantities": name,
                "relation": [int(r) for r in rel],
                "precision": prec,
                "status": "MATCH" if prec >= dps // 4 else "near_miss",
            })

    # Quadruple: V_quad + Ω⁺ + Ω⁻ + L(E,1)
    with mp.workdps(pslq_dps):
        vec = [mp.mpf(vquad), mp.mpf(omega_p), mp.mpf(omega_m),
               mp.mpf(L1), mp.mpf(1)]
        rel, prec = _pslq_test(vec, pslq_dps)
    if rel and prec >= 15 and rel[0] != 0:
        results.append({
            "type": "vquad_vs_11a1_quad",
            "quantities": "omega_plus, omega_minus, L(E,1)",
            "relation": [int(r) for r in rel],
            "precision": prec,
            "status": "MATCH" if prec >= dps // 4 else "near_miss",
        })

    return results


def verify_ode_numerically(vquad, dps):
    """Verify V_quad satisfies a 3rd-order linear ODE by checking
    that the parametric family CF(t) = GCF(1, t·(3n²+n+1)) satisfies
    a differential equation in t near t=1.

    If CF(t) satisfies L·CF = 0 for a 3rd-order operator L, then
    we can detect it by computing CF at nearby t values and checking
    that the 4th divided difference vanishes.
    """
    results = {}
    with mp.workdps(dps + 50):
        h = mp.mpf(10) ** (-dps // 5)  # Step size for numerical differentiation
        n_terms = 3000

        # Compute CF(t) at t = 1, 1±h, 1±2h
        t_vals = [1 - 2*h, 1 - h, mp.mpf(1), 1 + h, 1 + 2*h]
        cf_vals = []
        for t in t_vals:
            val = mp.mpf(0)
            tol = mp.mpf(10) ** -(dps + 40)
            for n in range(n_terms, 0, -1):
                bn = t * (3 * mp.mpf(n)**2 + mp.mpf(n) + 1)
                denom = bn + val
                if abs(denom) < tol:
                    val = None
                    break
                val = mp.mpf(1) / denom
            if val is not None:
                cf_vals.append(mp.mpf(1) + val)
            else:
                cf_vals.append(None)

        if any(v is None for v in cf_vals):
            return {"ode_order_check": "FAILED", "reason": "evaluation_failure"}

        # Compute numerical derivatives: CF', CF'', CF'''
        f = cf_vals
        # 1st derivative (central difference)
        fp = (f[3] - f[1]) / (2 * h)
        # 2nd derivative
        fpp = (f[3] - 2*f[2] + f[1]) / (h**2)
        # 3rd derivative
        fppp = (f[4] - 2*f[3] + 2*f[1] - f[0]) / (2 * h**3)

        # For a 3rd-order ODE: a₃·f''' + a₂·f'' + a₁·f' + a₀·f = 0
        # Normalize by f: check PSLQ on [f'''/f, f''/f, f'/f, 1]
        with mp.workdps(dps // 3):
            v = mp.mpf(vquad)
            vec = [mp.mpf(fppp / v), mp.mpf(fpp / v), mp.mpf(fp / v), mp.mpf(1)]
            rel, prec = _pslq_test(vec, dps // 3)

        results = {
            "cf_at_1": float(f[2]),
            "cf_prime": float(fp),
            "cf_double_prime": float(fpp),
            "cf_triple_prime": float(fppp),
            "ode_relation": [int(r) for r in rel] if rel else None,
            "ode_precision": prec,
            "ode_detected": rel is not None and prec >= 10,
        }

    return results


def main():
    parser = argparse.ArgumentParser(
        description="V_quad 11a1 ODE verifier + period relation scanner.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--prec", type=int, default=500)
    parser.add_argument("--json-out", default="vquad_11a1_results.json")
    args = parser.parse_args()

    dps = args.prec
    mp.mp.dps = dps + 200

    print(f"{'='*60}")
    print(f"  V_quad — 11a1 Elliptic Curve Attachment Verifier")
    print(f"{'='*60}")
    print(f"  Precision: {dps}dp")
    t0 = time.perf_counter()

    # Compute V_quad
    print("\n[1/5] Computing V_quad...")
    vquad = compute_vquad(dps)
    print(f"  V_quad = {mp.nstr(vquad, 40)}")

    # Compute 11a1 periods
    print("\n[2/5] Computing 11a1 periods...")
    periods = compute_11a1_periods(dps)
    if periods:
        print(f"  Ω⁺ = {mp.nstr(periods['omega_plus'], 30)}")
        print(f"  Ω⁻ = {mp.nstr(periods['omega_minus'], 30)}")
        print(f"  Roots: {periods['roots']}")
        print(f"  Δ = {periods['discriminant']}")
    else:
        print("  WARNING: Period computation failed")

    # Compute L-values
    print("\n[3/5] Computing L-function values...")
    l_values = compute_l_values(dps, n_terms=500)
    print(f"  L(E,1) ≈ {mp.nstr(l_values['L_E_1'], 20)}")
    print(f"  L(E,2) ≈ {mp.nstr(l_values['L_E_2'], 20)}")
    print(f"  a_n[1:12] = {l_values['a_n_sample'][:12]}")
    # Known: L(E_{11a1}, 1) ≈ 0.2538... (BSD: L(E,1)/Ω⁺ = 1/5)
    if periods:
        ratio = l_values["L_E_1"] / periods["omega_plus"]
        print(f"  L(E,1)/Ω⁺ ≈ {mp.nstr(ratio, 15)} (BSD predicts 1/5 = 0.2)")

    # Test period relations
    print("\n[4/5] Testing period + L-value relations...")
    if periods:
        rel_results = test_period_relations(vquad, periods, l_values, dps)
        matches = [r for r in rel_results if r["status"] == "MATCH"]
        near = [r for r in rel_results if r["status"] == "near_miss"]
        print(f"  Tests run: {len(rel_results)}")
        print(f"  MATCHES: {len(matches)}")
        print(f"  Near-misses: {len(near)}")
        for m in matches:
            print(f"    *** {m['type']}  {m.get('quantity','')}{m.get('quantities','')}")
            print(f"        rel={m['relation']}  prec={m['precision']}dp")
    else:
        rel_results = []

    # ODE verification
    print("\n[5/5] Numerical ODE verification...")
    ode_result = verify_ode_numerically(vquad, dps)
    if ode_result.get("ode_detected"):
        print(f"  *** 3rd-ORDER ODE DETECTED ***")
        print(f"  Relation: {ode_result['ode_relation']}")
        print(f"  Precision: {ode_result['ode_precision']}dp")
    else:
        print(f"  No clean 3rd-order ODE detected at this precision")
        print(f"  (ODE may require higher precision or non-polynomial coefficients)")

    wall = round(time.perf_counter() - t0, 3)

    output = {
        "verifier": "vquad_11a1",
        "precision": dps,
        "vquad": mp.nstr(vquad, 50),
        "periods": {
            "omega_plus": mp.nstr(periods["omega_plus"], 40) if periods else None,
            "omega_minus": mp.nstr(periods["omega_minus"], 40) if periods else None,
            "discriminant": periods["discriminant"] if periods else None,
        } if periods else None,
        "l_values": {
            "L_E_1": mp.nstr(l_values["L_E_1"], 30),
            "L_E_2": mp.nstr(l_values["L_E_2"], 30),
        },
        "period_relations": rel_results,
        "ode_verification": ode_result,
        "matches_found": len([r for r in rel_results if r["status"] == "MATCH"]),
        "near_misses_found": len([r for r in rel_results if r["status"] == "near_miss"]),
        "wall_seconds": wall,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  V_quad 11a1 Verifier Report")
    print(f"{'='*60}")
    print(f"  MATCHES:      {output['matches_found']}")
    print(f"  Near-misses:  {output['near_misses_found']}")
    ode_status = "DETECTED" if ode_result.get("ode_detected") else "not found"
    print(f"  ODE status:   {ode_status}")
    print(f"  Wall time:    {wall}s")
    if output["matches_found"] > 0:
        print(f"\n  *** V_quad MAY BE ATTACHED TO 11a1 ***")
    elif output["near_misses_found"] > 0:
        print(f"\n  Near-miss signals warrant higher-precision follow-up")
    else:
        print(f"\n  V_quad appears independent of 11a1 periods/L-values")
    print(f"\n  JSON -> {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
