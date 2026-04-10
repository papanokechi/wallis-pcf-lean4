#!/usr/bin/env python3
"""
V_quad Hypergeometric Frontier — pFq Parametric Scanner
═══════════════════════════════════════════════════════

Scans generalized hypergeometric functions pFq against V_quad at
parameters motivated by the discriminant -11 and conductor structure.

Families tested:
  A. 2F1 at CM-point arguments (Schwarz map images)
  B. 3F2 at z=1 (Apery-adjacent territory)
  C. q-hypergeometric at roots of unity
  D. 1F2 with disc=-11 matched parameters
  E. Generalized 0F2 with extended parameter ranges

V_quad = 1.19737399068... arises from GCF(1, 3n^2+n+1) with disc=-11.
"""

import sys
import time
import itertools
import mpmath as mp

WORK_DPS     = 600
CF_DEPTH     = 1500
PSLQ_DPS     = 500
COEFF_BOUND  = 10000
REPORT_FILE  = "vquad_hypergeometric_results.txt"


def compute_vquad(depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            v = mp.mpf(1) / (3*n*n + n + 1 + v)
        return mp.mpf(1) + v


def run_pslq(basis, labels, dps, coeff_bound=COEFF_BOUND):
    """Run PSLQ. Returns (found, msg)."""
    with mp.workdps(dps):
        try:
            rel = mp.pslq(basis, maxcoeff=coeff_bound, maxsteps=3000)
        except Exception:
            return False, ""
    if rel is not None:
        with mp.workdps(dps):
            dot = sum(c*b for c, b in zip(rel, basis))
            residual = abs(dot)
            rd = max(0, int(-float(mp.log10(residual + mp.mpf(10)**(-dps))))) if residual > 0 else dps
        nonzero = [(c, l) for c, l in zip(rel, labels) if c != 0]
        if len(nonzero) <= 1:
            return False, ""
        if rd < 50:
            return False, ""
        # Check it's not just "V_quad = 0"
        has_vquad = any(l == "V_quad" for c, l in nonzero)
        has_other = any(l != "V_quad" and l != "1" for c, l in nonzero)
        if has_vquad and has_other:
            parts = [f"{c:+d}*{l}" for c, l in nonzero]
            return True, f"FOUND ({rd}dp): {' '.join(parts)}"
    return False, ""


def main():
    mp.mp.dps = WORK_DPS
    print("=" * 70)
    print("  V_QUAD HYPERGEOMETRIC FRONTIER SCANNER")
    print("=" * 70)

    V = compute_vquad(CF_DEPTH, WORK_DPS)
    print(f"\n  V_quad = {mp.nstr(V, 30)}...")

    results = []
    total_tested = 0
    found_any = False
    t_start = time.time()

    # ═══ SCAN A: 2F1 at CM-point arguments ═══════════════════════════
    print(f"\n  SCAN A: 2F1 at CM-point / Schwarz arguments")
    print(f"  {'─'*60}")

    # CM points for disc=-11: tau = (1+sqrt(-11))/2
    # Schwarz map: z = lambda(tau) where lambda is the elliptic lambda function
    # Key arguments: z = 1/4, 1/2, (3-sqrt(5))/2, 11/16, etc.
    # Parameters (a,b;c) at rational values with small denominators

    param_abc = []
    for p in range(-4, 5):
        for q in [1, 2, 3, 4, 6]:
            param_abc.append(mp.mpf(p) / q)
    param_abc = sorted(set(float(x) for x in param_abc))

    z_values = [
        (mp.mpf(1)/4, "1/4"),
        (mp.mpf(1)/2, "1/2"),
        ((3 - mp.sqrt(5))/2, "(3-sqrt5)/2"),
        (mp.mpf(11)/16, "11/16"),
        (mp.mpf(1)/11, "1/11"),
        (mp.mpf(4)/11, "4/11"),
        (-mp.mpf(1)/27, "-1/27"),
    ]

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_a = 0
        for z_val, z_label in z_values:
            for a_f in param_abc[:15]:  # reduced grid for speed
                for b_f in param_abc[:15]:
                    for c_f in param_abc[:15]:
                        a, b, c = mp.mpf(a_f), mp.mpf(b_f), mp.mpf(c_f)
                        if c == 0 or c == int(c) and int(c) <= 0:
                            continue
                        try:
                            val = mp.hyp2f1(a, b, c, z_val)
                            if mp.isnan(val) or mp.isinf(val) or val == 0:
                                continue
                        except Exception:
                            continue

                        tested_a += 1
                        total_tested += 1
                        basis = [Vs, val, mp.mpf(1)]
                        labels = ["V_quad", f"2F1({a_f},{b_f};{c_f};{z_label})", "1"]
                        found, msg = run_pslq(basis, labels, PSLQ_DPS)
                        if found:
                            found_any = True
                            print(f"\n  >>> {msg}")
                            results.append({"scan": "A_2F1", "params": (a_f, b_f, c_f, z_label),
                                           "relation": msg})

            if tested_a % 2000 == 0 and tested_a > 0:
                elapsed = time.time() - t_start
                print(f"    [A: {tested_a} tested, {elapsed:.0f}s]")

    print(f"    Scan A: {tested_a} tests")

    # ═══ SCAN B: 3F2 at z=1 (Apery territory) ═══════════════════════
    print(f"\n  SCAN B: 3F2 at z=1 (Apery-adjacent)")
    print(f"  {'─'*60}")

    # Parameters motivated by Apery: 3F2(1,1,1; 2,2; 1) = zeta(2)
    # and Zudilin-style: 3F2(a,b,c; d,e; 1) for small rationals
    small_rats = [mp.mpf(p)/q for p in range(-3, 5) for q in [1, 2, 3] if q != 0]
    small_rats = sorted(set(small_rats))

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_b = 0

        for combo in itertools.combinations(small_rats, 5):
            a1, a2, a3, b1, b2 = combo
            # Skip singular cases
            if b1 == 0 or b2 == 0:
                continue
            if b1 == int(b1) and int(b1) <= 0:
                continue
            if b2 == int(b2) and int(b2) <= 0:
                continue

            try:
                val = mp.hyper([a1, a2, a3], [b1, b2], mp.mpf(1))
                if mp.isnan(val) or mp.isinf(val) or val == 0:
                    continue
            except Exception:
                continue

            tested_b += 1
            total_tested += 1
            label = f"3F2({float(a1)},{float(a2)},{float(a3)};{float(b1)},{float(b2)};1)"
            basis = [Vs, val, mp.mpf(1)]
            labels = ["V_quad", label, "1"]
            found, msg = run_pslq(basis, labels, PSLQ_DPS)
            if found:
                found_any = True
                print(f"\n  >>> {msg}")
                results.append({"scan": "B_3F2", "params": [float(x) for x in combo],
                               "relation": msg})

            if tested_b >= 5000:
                break
            if tested_b % 1000 == 0:
                elapsed = time.time() - t_start
                print(f"    [B: {tested_b} tested, {elapsed:.0f}s]")

    print(f"    Scan B: {tested_b} tests")

    # ═══ SCAN C: q-series at roots of unity ══════════════════════════
    print(f"\n  SCAN C: q-hypergeometric at roots of unity")
    print(f"  {'─'*60}")

    # q-Pochhammer and basic hypergeometric at q = e^{2pi*i/N}
    # for conductors N = 11, 24, 44 (related to disc=-11 and level 24)
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_c = 0

        for N in [11, 24, 44]:
            q = mp.exp(mp.mpf(-2) * mp.pi / N)  # real: q = e^{-2pi/N}
            # q-Pochhammer (q;q)_inf = prod_{n=1}^inf (1-q^n)
            qpoch = mp.mpf(1)
            for n in range(1, 500):
                qpoch *= (1 - q**n)
                if abs(q**n) < mp.mpf(10)**(-PSLQ_DPS):
                    break

            # q-exponential: E_q(z) = sum_{n=0}^inf z^n / [n]_q!
            # Try various z values
            for z_mult in [1, 2, 3, mp.mpf(1)/3, mp.mpf(1)/11]:
                z = z_mult * q
                # Simple q-series: sum q^{n^2}/(q;q)_n (Ramanujan theta)
                theta = mp.mpf(0)
                prod_n = mp.mpf(1)
                for n in range(200):
                    theta += q**(n*n) / prod_n if prod_n != 0 else 0
                    prod_n *= (1 - q**(n+1))
                    if abs(q**(n*n)) < mp.mpf(10)**(-PSLQ_DPS):
                        break

                if theta != 0 and not mp.isnan(theta):
                    tested_c += 1
                    total_tested += 1
                    lbl = f"theta(q=e^{{-2pi/{N}}},z={float(z_mult)})"
                    basis = [Vs, theta, qpoch, mp.mpf(1)]
                    labels = ["V_quad", lbl, f"(q;q)_inf[N={N}]", "1"]
                    found, msg = run_pslq(basis, labels, PSLQ_DPS)
                    if found:
                        found_any = True
                        print(f"\n  >>> {msg}")
                        results.append({"scan": "C_qseries", "N": N, "relation": msg})

    print(f"    Scan C: {tested_c} tests")

    # ═══ SCAN D: 1F2 with disc=-11 matched params ═══════════════════
    print(f"\n  SCAN D: 1F2 at discriminant-matched parameters")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_d = 0

        # 1F2(a; b1, b2; z) with a,b from {1/6, 1/3, 1/2, 2/3, 5/6, 1}
        # z from {-1/27, 1/27, -11/108, 11/108, -1/4, 1/4}
        a_vals = [mp.mpf(p)/q for p in range(1, 6) for q in [1, 2, 3, 6]]
        a_vals = sorted(set(a_vals))
        z_1f2 = [mp.mpf(-1)/27, mp.mpf(1)/27, mp.mpf(-11)/108,
                 mp.mpf(11)/108, mp.mpf(-1)/4, mp.mpf(1)/4]

        for z_val in z_1f2:
            for a in a_vals[:10]:
                for b1 in a_vals[:10]:
                    for b2 in a_vals[:10]:
                        if b1 <= 0 or b2 <= 0:
                            continue
                        try:
                            val = mp.hyper([a], [b1, b2], z_val)
                            if mp.isnan(val) or mp.isinf(val) or val == 0:
                                continue
                        except Exception:
                            continue

                        tested_d += 1
                        total_tested += 1
                        basis = [Vs, val, mp.mpf(1)]
                        z_str = mp.nstr(z_val, 5)
                        labels = ["V_quad",
                                 f"1F2({float(a)};{float(b1)},{float(b2)};{z_str})",
                                 "1"]
                        found, msg = run_pslq(basis, labels, PSLQ_DPS)
                        if found:
                            found_any = True
                            print(f"\n  >>> {msg}")
                            results.append({"scan": "D_1F2",
                                          "params": (float(a), float(b1), float(b2), z_str),
                                          "relation": msg})

                        if tested_d >= 8000:
                            break
                    if tested_d >= 8000:
                        break
                if tested_d >= 8000:
                    break
            if tested_d >= 8000:
                break

        if tested_d % 2000 == 0 and tested_d > 0:
            elapsed = time.time() - t_start
            print(f"    [D: {tested_d} tested, {elapsed:.0f}s]")

    print(f"    Scan D: {tested_d} tests")

    # ═══ Summary ═════════════════════════════════════════════════════
    elapsed_total = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  TOTAL: {total_tested} parametric tests in {elapsed_total:.1f}s")
    if found_any:
        print(f"\n  >>> {len(results)} RELATION(S) FOUND <<<")
        for r in results:
            print(f"    [{r['scan']}] {r['relation']}")
    else:
        print(f"\n  NO RELATIONS FOUND.")
        print(f"  V_quad excluded from:")
        print(f"    A: 2F1 at 7 CM-point arguments (reduced rational grid)")
        print(f"    B: 3F2 at z=1 (Apery-adjacent, 5000 parameter sets)")
        print(f"    C: q-series at N=11,24,44 roots of unity")
        print(f"    D: 1F2 at 6 discriminant-matched arguments")
    print(f"{'='*70}")

    # Save report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"V_QUAD HYPERGEOMETRIC FRONTIER SCAN\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Precision: {PSLQ_DPS} dps, coeff bound {COEFF_BOUND}\n")
        f.write(f"Total tests: {total_tested}\n")
        f.write(f"Relations found: {len(results)}\n\n")
        if results:
            for r in results:
                f.write(f"  {r}\n")
        else:
            f.write("  No relations found.\n")
        f.write(f"\nElapsed: {elapsed_total:.1f}s\n")
    print(f"  Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
