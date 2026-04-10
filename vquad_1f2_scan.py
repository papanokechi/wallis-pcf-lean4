#!/usr/bin/env python3
"""
V_quad 1F2 Scan — Multiprocessing-Based Hard Timeout
════════════════════════════════════════════════════

Uses multiprocessing (not threading) to hard-kill stuck mpmath
evaluations. This is important because mpmath's C-level compute
can't be interrupted by Python threading.

Targets 1F2(a; b1, b2; z) which is the natural hypergeometric
family for V_quad's GCF structure:
  b(n) = 3n^2 + n + 1 → degree 2 → kernel family includes 1F2

Parameters motivated by discriminant -11 of 3n^2+n+1.
"""

import sys
import time
import multiprocessing as mp_mod
import mpmath as mp

WORK_DPS    = 600
CF_DEPTH    = 1500
PSLQ_DPS    = 500
COEFF_BOUND = 10000
EVAL_TIMEOUT = 20  # seconds per evaluation (hard kill)
REPORT_FILE = "vquad_1f2_results.txt"


def compute_vquad(depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            v = mp.mpf(1) / (3*n*n + n + 1 + v)
        return mp.mpf(1) + v


def _eval_worker(args):
    """Worker function for multiprocessing evaluation."""
    func_name, params, dps = args
    mp.mp.dps = dps + 50
    try:
        if func_name == "hyper_1f2":
            a, b1, b2, z = params
            val = mp.hyper([mp.mpf(a)], [mp.mpf(b1), mp.mpf(b2)], mp.mpf(z))
            return float(mp.re(val)), float(mp.im(val)) if isinstance(val, mp.mpc) else 0.0
        elif func_name == "hyper_3f2":
            a1, a2, a3, b1, b2, z = params
            val = mp.hyper([mp.mpf(a1), mp.mpf(a2), mp.mpf(a3)],
                          [mp.mpf(b1), mp.mpf(b2)], mp.mpf(z))
            return float(mp.re(val)), float(mp.im(val)) if isinstance(val, mp.mpc) else 0.0
    except Exception:
        return None, None
    return None, None


def safe_eval_mp(func_name, params, dps, timeout=EVAL_TIMEOUT):
    """Evaluate with hard timeout via multiprocessing."""
    ctx = mp_mod.get_context("spawn")
    pool = ctx.Pool(1)
    try:
        result = pool.apply_async(_eval_worker, [(func_name, params, dps)])
        re_val, im_val = result.get(timeout=timeout)
        pool.terminate()
        if re_val is None:
            return None
        mp.mp.dps = dps
        return mp.mpf(re_val)  # take real part
    except mp_mod.TimeoutError:
        pool.terminate()
        return None
    except Exception:
        pool.terminate()
        return None
    finally:
        pool.join()


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
    print("  V_QUAD 1F2 SCAN (MULTIPROCESSING HARD TIMEOUT)")
    print("=" * 70)

    V = compute_vquad(CF_DEPTH, WORK_DPS)
    print(f"\n  V_quad = {mp.nstr(V, 30)}...")
    print(f"  Eval timeout: {EVAL_TIMEOUT}s (hard kill via multiprocessing)")

    results = []
    total_tested = 0
    total_skipped = 0
    found_any = False
    t_start = time.time()

    # ═══ 1F2(a; b1, b2; z) scan ═════════════════════════════════════
    print(f"\n  1F2(a; b1, b2; z) SCAN")
    print(f"  {'─'*60}")

    # Parameters from the recurrence 3n^2+n+1:
    # Leading coeff 3: suggests a ~ 1/3, 2/3
    # Linear coeff 1: suggests shifts by 1/3
    # Constant 1: trivial
    # Discriminant -11: suggests z ~ ±11/108 or ±1/27 or ±1/4
    a_vals = [1/6, 1/4, 1/3, 1/2, 2/3, 3/4, 5/6, 1,
              4/3, 3/2, 5/3, 2, 5/2, 3, 1/11, 2/11, 3/11]
    b_vals = [1/6, 1/4, 1/3, 1/2, 2/3, 3/4, 5/6, 1,
              4/3, 3/2, 5/3, 2, 7/3, 5/2, 3, 7/2, 4]
    z_vals = [
        (-1/27, "-1/27"),
        (1/27, "1/27"),
        (-11/108, "-11/108"),
        (11/108, "11/108"),
        (-1/4, "-1/4"),
        (1/4, "1/4"),
        (-4/27, "-4/27"),
        (4/27, "4/27"),
        (-1/3, "-1/3"),
        (1/3, "1/3"),
    ]

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)

        for z_val, z_label in z_vals:
            z_tested = 0
            z_skipped = 0

            for a in a_vals:
                for b1 in b_vals:
                    for b2 in b_vals:
                        if b1 <= 0 or b2 <= 0:
                            continue

                        val = safe_eval_mp("hyper_1f2", (a, b1, b2, z_val), PSLQ_DPS)
                        if val is None:
                            z_skipped += 1
                            total_skipped += 1
                            continue
                        if mp.isnan(val) or mp.isinf(val) or val == 0:
                            continue

                        z_tested += 1
                        total_tested += 1
                        label = f"1F2({a:.3g};{b1:.3g},{b2:.3g};{z_label})"
                        basis = [Vs, val, mp.mpf(1)]
                        labels = ["V_quad", label, "1"]
                        found, msg = run_pslq(basis, labels, PSLQ_DPS)
                        if found:
                            found_any = True
                            print(f"\n  >>> {msg}")
                            results.append({"family": "1F2",
                                           "params": (a, b1, b2, z_val),
                                           "relation": msg})

            elapsed = time.time() - t_start
            print(f"    z={z_label}: {z_tested} tested, {z_skipped} timed out ({elapsed:.0f}s)")

    # ═══ Also run remaining 3F2 at z=1 with hard timeout ════════════
    print(f"\n  3F2 at z=1 (hard timeout)")
    print(f"  {'─'*60}")

    small_rats = sorted(set([p/q for p in range(-2, 4) for q in [1, 2, 3] if q != 0]))

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tested_3f2 = 0
        skipped_3f2 = 0

        import itertools
        for combo in itertools.combinations(small_rats, 5):
            a1, a2, a3, b1, b2 = combo
            if b1 <= 0 or b2 <= 0:
                continue

            val = safe_eval_mp("hyper_3f2", (a1, a2, a3, b1, b2, 1.0), PSLQ_DPS)
            if val is None:
                skipped_3f2 += 1
                total_skipped += 1
                continue
            if mp.isnan(val) or mp.isinf(val) or val == 0:
                continue

            tested_3f2 += 1
            total_tested += 1
            label = f"3F2({a1:.2g},{a2:.2g},{a3:.2g};{b1:.2g},{b2:.2g};1)"
            basis = [Vs, val, mp.mpf(1)]
            labels = ["V_quad", label, "1"]
            found, msg = run_pslq(basis, labels, PSLQ_DPS)
            if found:
                found_any = True
                print(f"\n  >>> {msg}")
                results.append({"family": "3F2", "relation": msg})

            if tested_3f2 >= 3000:
                break
            if tested_3f2 % 500 == 0 and tested_3f2 > 0:
                elapsed = time.time() - t_start
                print(f"    [3F2: {tested_3f2} tested, {skipped_3f2} timed out, {elapsed:.0f}s]")

        print(f"    3F2: {tested_3f2} tested, {skipped_3f2} timed out")

    # ═══ Summary ═════════════════════════════════════════════════════
    elapsed_total = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  TOTAL: {total_tested} tests ({total_skipped} timed out) in {elapsed_total:.1f}s")
    if found_any:
        print(f"\n  >>> {len(results)} RELATION(S) FOUND <<<")
        for r in results:
            print(f"    {r['relation']}")
    else:
        print(f"  NO RELATIONS FOUND.")
        print(f"  V_quad excluded from 1F2 and 3F2 at tested parameters.")
    print(f"{'='*70}")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"V_QUAD 1F2 + 3F2 SCAN (MULTIPROCESSING)\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total: {total_tested} tests, {total_skipped} timed out\n")
        f.write(f"Relations: {len(results)}\n\n")
        for r in results:
            f.write(f"  {r}\n")
    print(f"  Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
