"""
Targeted zeta(3) search using CMF exhaustive sweep.
Searches for Apéry-like continued fractions with cubic a(n) and quadratic b(n).
Writes discoveries to zeta3_discoveries.jsonl.
"""
import sys, json, time, itertools, re
from pathlib import Path
from datetime import datetime

from mpmath import mp, mpf, nstr, zeta, pi, log, sqrt, euler, gamma
import mpmath as mpm

# ── constants focused on zeta(3) neighborhood ─────────────────────────────────
def build_zeta_targets(prec):
    mp.dps = prec + 20
    z3 = zeta(3)
    z5 = zeta(5)
    pi_val = pi
    return {
        'zeta3':       z3,
        '6/zeta3':     mpf(6) / z3,
        '1/zeta3':     1 / z3,
        '2*zeta3':     2 * z3,
        'zeta3/pi^2':  z3 / pi_val**2,
        'pi^2/zeta3':  pi_val**2 / z3,
        'zeta5':       z5,
        'pi^2/6':      pi_val**2 / 6,
        'pi^4/90':     pi_val**4 / 90,
        'catalan':     mpm.catalan,
        'log2':        log(2),
        'pi':          pi_val,
        '4/pi':        mpf(4) / pi_val,
    }


def eval_pcf(a_coeffs, b_coeffs, depth=500):
    try:
        def a(n): return sum(mpf(c) * n**i for i, c in enumerate(a_coeffs))
        def b(n): return sum(mpf(c) * n**i for i, c in enumerate(b_coeffs))
        val = mpf(0)
        for n in range(depth, 0, -1):
            bn = b(n)
            an = a(n)
            denom = bn + val
            if abs(denom) < mpf(10)**(-mp.dps + 5):
                return None
            val = an / denom
        return b(0) + val
    except Exception:
        return None


def is_reasonable(val):
    if val is None:
        return False
    try:
        f = float(val)
        return abs(f) > 1e-6 and abs(f) < 1e8 and f == f  # not nan
    except:
        return False


LOGFILE = Path("zeta3_discoveries.jsonl")


def log_discovery(record):
    with LOGFILE.open('a') as f:
        f.write(json.dumps(record) + '\n')
    print("  FOUND: a=%s b=%s -> %s (res=%.1f)" % (
        record['a'], record['b'], record['match'], record['residual']))


def main():
    prec = 80
    depth = 400
    tol = 18
    mp.dps = prec + 20

    targets = build_zeta_targets(prec)
    print(f"Zeta(3) Targeted Search")
    print(f"  Targets: {list(targets.keys())}")
    print(f"  Precision: {prec} dps | Depth: {depth} | Tol: {tol} digits")

    seen = set()
    discoveries = []
    evaluated = 0
    t_start = time.time()
    last_report = t_start

    # Strategy 1: Cubic a(n), quadratic b(n) — Apéry neighborhood
    print("\n--- Phase 1: Cubic a(n), quadratic b(n), coeffs [-5,5] ---")
    cr = 5
    a_range = range(-cr, cr + 1)
    b_range = range(-cr, cr + 1)

    for a0, a1, a2, a3 in itertools.product(a_range, a_range, a_range, a_range):
        if a3 == 0:  # require cubic
            continue
        for b0 in range(1, cr + 1):
            for b1, b2 in itertools.product(b_range, b_range):
                a_coeffs = [a0, a1, a2, a3]
                b_coeffs = [b0, b1, b2]

                val = eval_pcf(a_coeffs, b_coeffs, depth=depth)
                evaluated += 1

                if not is_reasonable(val):
                    continue

                for name, cval in targets.items():
                    for numer in [1, 2, 3, 4, 6]:
                        for denom in [1, 2, 3, 4, 6, 8]:
                            ratio = mpf(numer) / denom * cval
                            res = abs(val - ratio)
                            if res < mpf(10)**(-tol):
                                key = (tuple(a_coeffs), tuple(b_coeffs), name, numer, denom)
                                if key not in seen:
                                    seen.add(key)
                                    label = f"{numer}/{denom}*{name}" if (numer != 1 or denom != 1) else name
                                    record = {
                                        'type': 'zeta3_cmf',
                                        'a': a_coeffs, 'b': b_coeffs,
                                        'value': nstr(val, 20),
                                        'match': label,
                                        'residual': float(mpm.log10(max(res, mpf(10)**(-mp.dps+5)))),
                                        'timestamp': datetime.now().isoformat(),
                                    }
                                    discoveries.append(record)
                                    log_discovery(record)

                # Progress
                now = time.time()
                if now - last_report > 15:
                    elapsed = now - t_start
                    rate = evaluated / elapsed
                    print(f"  [{evaluated:,} eval | {len(discoveries)} hits | "
                          f"{rate:.0f}/s | {elapsed:.0f}s]", flush=True)
                    last_report = now

    elapsed = time.time() - t_start
    print(f"\nPhase 1 done: {evaluated:,} evaluated, {len(discoveries)} discoveries, {elapsed:.1f}s")

    # Strategy 2: Sextic a(n) near Apéry, cubic b(n) — small perturbations
    print("\n--- Phase 2: Apéry perturbations: a(n)~-n^6, b(n)~34n^3-51n^2+27n-5 ---")
    pert = 2
    for da6 in range(-pert, pert+1):
        for da5 in range(-pert, pert+1):
            for da4 in range(-pert, pert+1):
                a_coeffs = [0, 0, 0, 0, da4, da5, -1 + da6]
                if a_coeffs[-1] == 0:
                    continue
                for db0, db1, db2, db3 in itertools.product(
                    range(-5-pert, -5+pert+1),
                    range(27-pert, 27+pert+1),
                    range(-51-pert, -51+pert+1),
                    range(34-pert, 34+pert+1),
                ):
                    b_coeffs = [db0, db1, db2, db3]
                    if b_coeffs[0] == 0:
                        continue

                    val = eval_pcf(a_coeffs, b_coeffs, depth=depth)
                    evaluated += 1

                    if not is_reasonable(val):
                        continue

                    for name, cval in targets.items():
                        for numer in [1, 2, 3, 4, 6]:
                            for denom in [1, 2, 3, 4, 6]:
                                ratio = mpf(numer) / denom * cval
                                res = abs(val - ratio)
                                if res < mpf(10)**(-tol):
                                    key = (tuple(a_coeffs), tuple(b_coeffs), name, numer, denom)
                                    if key not in seen:
                                        seen.add(key)
                                        label = f"{numer}/{denom}*{name}" if (numer != 1 or denom != 1) else name
                                        record = {
                                            'type': 'zeta3_apery',
                                            'a': a_coeffs, 'b': b_coeffs,
                                            'value': nstr(val, 20),
                                            'match': label,
                                            'residual': float(mpm.log10(max(res, mpf(10)**(-mp.dps+5)))),
                                            'timestamp': datetime.now().isoformat(),
                                        }
                                        discoveries.append(record)
                                        log_discovery(record)

                    now = time.time()
                    if now - last_report > 15:
                        elapsed = now - t_start
                        rate = evaluated / elapsed
                        print(f"  [{evaluated:,} eval | {len(discoveries)} hits | "
                              f"{rate:.0f}/s | {elapsed:.0f}s]", flush=True)
                        last_report = now

    elapsed = time.time() - t_start
    print(f"\nTotal: {evaluated:,} evaluated, {len(discoveries)} discoveries, {elapsed:.1f}s")
    print(f"Results in {LOGFILE}")


if __name__ == '__main__':
    main()
