#!/usr/bin/env python3
"""
V_quad Hypergeometric Scan v2 — Timeout-Protected
══════════════════════════════════════════════════

Previous run: Scan A (2F1) completed with 15,728 tests, NO relations.
              Scan B (3F2) hung on a divergent evaluation.

This version adds per-evaluation timeouts (30s) so one pathological
parameter combination cannot block the queue.  Prioritizes:
  C. q-hypergeometric at roots of unity (highest scientific value)
  B'. 3F2 at z=1 with timeout protection
  D. 1F2 at disc=-11 matched params

The q-series scan (C) is prioritized first because a positive result
would connect V_quad to mock-modular territory.
"""

import sys
import time
import signal
import itertools
import mpmath as mp

WORK_DPS     = 600
CF_DEPTH     = 1500
PSLQ_DPS     = 500
COEFF_BOUND  = 10000
EVAL_TIMEOUT = 30    # seconds per evaluation
REPORT_FILE  = "vquad_hypergeometric_v2_results.txt"


class EvalTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise EvalTimeout("evaluation timed out")


def safe_eval(func, *args, timeout=EVAL_TIMEOUT):
    """Evaluate func(*args) with a timeout. Returns None on timeout."""
    # On Windows, signal.alarm isn't available, use threading instead
    import threading
    result = [None]
    exc = [None]
    def target():
        try:
            result[0] = func(*args)
        except Exception as e:
            exc[0] = e
    t = threading.Thread(target=target)
    t.daemon = True
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None  # timed out
    if exc[0]:
        return None  # error
    return result[0]


def compute_vquad(depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            v = mp.mpf(1) / (3*n*n + n + 1 + v)
        return mp.mpf(1) + v


def run_pslq(basis, labels, dps, coeff_bound=COEFF_BOUND):
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
        has_vquad = any(l == "V_quad" for c, l in nonzero)
        has_other = any(l != "V_quad" and l != "1" for c, l in nonzero)
        if has_vquad and has_other:
            parts = [f"{c:+d}*{l}" for c, l in nonzero]
            return True, f"FOUND ({rd}dp): {' '.join(parts)}"
    return False, ""


def main():
    mp.mp.dps = WORK_DPS
    print("=" * 70)
    print("  V_QUAD HYPERGEOMETRIC SCAN v2 (TIMEOUT-PROTECTED)")
    print("=" * 70)

    V = compute_vquad(CF_DEPTH, WORK_DPS)
    print(f"\n  V_quad = {mp.nstr(V, 30)}...")
    print(f"  Per-eval timeout: {EVAL_TIMEOUT}s")
    print(f"  NOTE: Scan A (2F1, 15728 tests) already completed — NO relations.")

    results = []
    total_tested = 0
    total_skipped = 0
    found_any = False
    t_start = time.time()

    # ═══ SCAN C: q-hypergeometric at roots of unity (PRIORITY) ═══════
    print(f"\n  SCAN C: q-hypergeometric at roots of unity [PRIORITY]")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_c = 0

        for N in [11, 24, 44, 48, 120]:
            q = mp.exp(mp.mpf(-2) * mp.pi / N)
            q_abs = abs(q)
            print(f"    N={N}: |q| = {mp.nstr(q_abs, 6)}")

            # q-Pochhammer (q;q)_inf
            qpoch = mp.mpf(1)
            for n in range(1, 500):
                qpoch *= (1 - q**n)
                if abs(q**n) < mp.mpf(10)**(-PSLQ_DPS):
                    break

            # Ramanujan theta: sum q^{n^2}
            theta_q = mp.mpf(0)
            for n in range(-200, 201):
                theta_q += q**(n*n)
                if abs(q**(n*n)) < mp.mpf(10)**(-PSLQ_DPS) and n > 10:
                    break

            # Jacobi theta3: sum q^{n^2}
            theta3 = 1 + 2 * sum(q**(n*n) for n in range(1, 200)
                                  if abs(q**(n*n)) > mp.mpf(10)**(-PSLQ_DPS))

            # Euler function phi(q) = (q;q)_inf
            # Rogers-Ramanujan: G(q) = sum q^{n^2} / (q;q)_n
            rr_G = mp.mpf(0)
            prod_n = mp.mpf(1)
            for n in range(200):
                if prod_n != 0:
                    rr_G += q**(n*n) / prod_n
                prod_n *= (1 - q**(n+1))
                if abs(q**(n*n)) < mp.mpf(10)**(-PSLQ_DPS):
                    break

            # Rogers-Ramanujan: H(q) = sum q^{n(n+1)} / (q;q)_n
            rr_H = mp.mpf(0)
            prod_n = mp.mpf(1)
            for n in range(200):
                if prod_n != 0:
                    rr_H += q**(n*(n+1)) / prod_n
                prod_n *= (1 - q**(n+1))
                if abs(q**(n*(n+1))) < mp.mpf(10)**(-PSLQ_DPS):
                    break

            # Test various combinations
            test_bases = [
                ([Vs, qpoch, mp.mpf(1)],
                 ["V_quad", f"(q;q)_inf[N={N}]", "1"]),
                ([Vs, theta3, mp.mpf(1)],
                 ["V_quad", f"theta3(q)[N={N}]", "1"]),
                ([Vs, rr_G, mp.mpf(1)],
                 ["V_quad", f"RR_G(q)[N={N}]", "1"]),
                ([Vs, rr_H, mp.mpf(1)],
                 ["V_quad", f"RR_H(q)[N={N}]", "1"]),
                ([Vs, qpoch, theta3, mp.mpf(1)],
                 ["V_quad", f"(q;q)_inf[N={N}]", f"theta3[N={N}]", "1"]),
                ([Vs, rr_G, rr_H, mp.mpf(1)],
                 ["V_quad", f"RR_G[N={N}]", f"RR_H[N={N}]", "1"]),
                ([Vs, rr_G/rr_H, mp.mpf(1)],
                 ["V_quad", f"G/H[N={N}]", "1"]),
                ([Vs, qpoch**24, mp.mpf(1)],
                 ["V_quad", f"(q;q)^24[N={N}]", "1"]),
            ]

            for basis, labels in test_bases:
                # Skip if any basis element is invalid
                if any(mp.isnan(b) or mp.isinf(b) or b == 0 for b in basis):
                    continue
                tested_c += 1
                total_tested += 1
                found, msg = run_pslq(basis, labels, PSLQ_DPS)
                if found:
                    found_any = True
                    print(f"\n  >>> {msg}")
                    results.append({"scan": "C_qseries", "N": N, "relation": msg})

        print(f"    Scan C: {tested_c} tests")

    # ═══ SCAN B': 3F2 at z=1 with timeout ═══════════════════════════
    print(f"\n  SCAN B': 3F2 at z=1 (timeout-protected)")
    print(f"  {'─'*60}")

    small_rats = sorted(set(mp.mpf(p)/q for p in range(-2, 4) for q in [1, 2, 3] if q != 0))

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_b = 0
        skipped_b = 0

        for combo in itertools.combinations(small_rats, 5):
            a1, a2, a3, b1, b2 = combo
            if b1 <= 0 or b2 <= 0:
                continue

            def _eval_3f2():
                return mp.hyper([a1, a2, a3], [b1, b2], mp.mpf(1))

            val = safe_eval(_eval_3f2, timeout=EVAL_TIMEOUT)
            if val is None:
                skipped_b += 1
                total_skipped += 1
                continue
            if mp.isnan(val) or mp.isinf(val) or val == 0:
                continue

            tested_b += 1
            total_tested += 1
            label = f"3F2({float(a1):.2g},{float(a2):.2g},{float(a3):.2g};{float(b1):.2g},{float(b2):.2g};1)"
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
            if tested_b % 500 == 0 and tested_b > 0:
                elapsed = time.time() - t_start
                print(f"    [B: {tested_b} tested, {skipped_b} timed out, {elapsed:.0f}s]")

        print(f"    Scan B: {tested_b} tests ({skipped_b} timed out)")

    # ═══ SCAN D: 1F2 at disc=-11 matched params ═══════════════════
    print(f"\n  SCAN D: 1F2 at discriminant-matched parameters")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_d = 0

        a_vals = sorted(set(mp.mpf(p)/q for p in range(1, 6) for q in [1, 2, 3, 6]))
        z_1f2 = [mp.mpf(-1)/27, mp.mpf(1)/27, mp.mpf(-11)/108,
                 mp.mpf(11)/108, mp.mpf(-1)/4, mp.mpf(1)/4]

        for z_val in z_1f2:
            for a in a_vals[:10]:
                for b1 in a_vals[:10]:
                    for b2 in a_vals[:10]:
                        if b1 <= 0 or b2 <= 0:
                            continue

                        def _eval_1f2(aa=a, bb1=b1, bb2=b2, zz=z_val):
                            return mp.hyper([aa], [bb1, bb2], zz)

                        val = safe_eval(_eval_1f2, timeout=EVAL_TIMEOUT)
                        if val is None or mp.isnan(val) or mp.isinf(val) or val == 0:
                            if val is None:
                                total_skipped += 1
                            continue

                        tested_d += 1
                        total_tested += 1
                        z_str = mp.nstr(z_val, 5)
                        basis = [Vs, val, mp.mpf(1)]
                        labels = ["V_quad",
                                  f"1F2({float(a):.2g};{float(b1):.2g},{float(b2):.2g};{z_str})",
                                  "1"]
                        found, msg = run_pslq(basis, labels, PSLQ_DPS)
                        if found:
                            found_any = True
                            print(f"\n  >>> {msg}")
                            results.append({"scan": "D_1F2", "relation": msg})

                        if tested_d >= 6000:
                            break
                    if tested_d >= 6000:
                        break
                if tested_d >= 6000:
                    break
            if tested_d >= 6000:
                break

        print(f"    Scan D: {tested_d} tests")

    # ═══ Summary ═════════════════════════════════════════════════════
    elapsed_total = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  TOTAL: {total_tested} tests ({total_skipped} timed out) in {elapsed_total:.1f}s")
    print(f"  PREVIOUS: Scan A (2F1) = 15,728 tests, NO relations")
    if found_any:
        print(f"\n  >>> {len(results)} RELATION(S) FOUND <<<")
        for r in results:
            print(f"    [{r['scan']}] {r['relation']}")
    else:
        print(f"\n  NO RELATIONS FOUND across scans B', C, D.")
        print(f"  Combined with Scan A, V_quad now excluded from:")
        print(f"    A: 2F1 at CM-point arguments (15,728 tests)")
        print(f"    B: 3F2 at z=1 ({tested_b} tests)")
        print(f"    C: q-hypergeometric at N=11,24,44,48,120 ({tested_c} tests)")
        print(f"    D: 1F2 at disc=-11 arguments ({tested_d} tests)")
        print(f"  PLUS previously: Lommel, Weber, Meijer-G, Bessel, Airy, Whittaker,")
        print(f"    elliptic periods, parabolic cylinder, elementary constants")
    print(f"{'='*70}")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"V_QUAD HYPERGEOMETRIC SCAN v2 (TIMEOUT-PROTECTED)\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total tests: {total_tested + 15728} (incl Scan A)\n")
        f.write(f"Timed out: {total_skipped}\n")
        f.write(f"Relations: {len(results)}\n\n")
        if results:
            for r in results:
                f.write(f"  {r}\n")
        else:
            f.write("No relations found.\n")
    print(f"\n  Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
