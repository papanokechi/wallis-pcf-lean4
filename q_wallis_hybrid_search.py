from __future__ import annotations

"""
Hybrid q-Wallis search:
- 1500 candidate families
- q in {0.8, 0.9, 0.95}
- q-Wallis ratio check against (1-q^(2m+2))/(1-q^(2m+1))
- if passed to 20 d.p., attempt simple q-intertwiner solve
"""

import json
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from mpmath import mp

mp.dps = 80

Q_VALUES = [mp.mpf("0.8"), mp.mpf("0.9"), mp.mpf("0.95")]
M_VALUES = [0, 1, 2, 3, 4]
SEARCH_ITERATIONS = 1500
DEPTH_LO = 120
DEPTH_HI = 260
PASS_TOL = mp.mpf("1e-20")
STABILITY_TOL = mp.mpf("1e-12")
SEED = 20260408


def qnum_int(n: int, q):
    return (1 - q**n) / (1 - q)


def target_ratio(q, m: int):
    return (1 - q ** (2 * m + 2)) / (1 - q ** (2 * m + 1))


def build_cache(q, depth: int = DEPTH_HI + 5, max_m: int = max(M_VALUES) + 3):
    qn = [mp.mpf(1)] * (depth + 1)
    for n in range(1, depth + 1):
        qn[n] = qn[n - 1] * q
    hn = [(1 - qn[n]) / (1 - q) for n in range(depth + 1)]
    hm = [(1 - q**m) / (1 - q) for m in range(max_m + 1)]
    qm = [q**m for m in range(max_m + 1)]
    q3n1 = [(1 - q ** (3 * n + 1)) / (1 - q) for n in range(depth + 1)]
    return {
        "q": q,
        "qn": qn,
        "hn": hn,
        "hm": hm,
        "qm": qm,
        "q3n1": q3n1,
    }


def gap_qnum(n: int, m: int, q):
    expn = 2 * n - 2 * m - 1
    return (1 - q ** expn) / (1 - q)


def coeffs(spec: Dict[str, int], n: int, m: int, cache):
    q = cache["q"]
    x = cache["qn"][n]
    y = cache["qm"][m]
    hn = cache["hn"][n]
    hm = cache["hm"][m]
    qgap = gap_qnum(n, m, q)

    inner = (
        spec["a_gap"] * qgap
        + spec["a_lin_n"] * hn
        + spec["a_lin_m"] * hm
        + spec["a_const"]
        + spec["a_qn"] * x
        + spec["a_qm"] * y
    )
    a = -hn * inner

    b = (
        spec["b_lin_n"] * hn
        + spec["b_const"]
        + spec["b_qn"] * x
        + spec["b_qm"] * y
        + spec["b_q3"] * cache["q3n1"][n]
    )
    return a, b


def eval_cf(spec: Dict[str, int], cache, m: int, depth: int):
    val = mp.mpf("0")
    try:
        for n in range(depth, 0, -1):
            a, b = coeffs(spec, n, m, cache)
            denom = b + val
            if abs(denom) < mp.mpf("1e-40"):
                return None
            val = a / denom
        return mp.mpf("1") + val
    except (ZeroDivisionError, OverflowError, ValueError):
        return None


CACHE_BY_Q = {str(q): build_cache(q, depth=DEPTH_HI + 5) for q in Q_VALUES}


def build_cache_float(q: float, depth: int = DEPTH_HI + 5, max_m: int = max(M_VALUES) + 3):
    qn = [1.0] * (depth + 1)
    for n in range(1, depth + 1):
        qn[n] = qn[n - 1] * q
    hn = [(1.0 - qn[n]) / (1.0 - q) for n in range(depth + 1)]
    hm = [(1.0 - q**m) / (1.0 - q) for m in range(max_m + 1)]
    qm = [q**m for m in range(max_m + 1)]
    q3n1 = [(1.0 - q ** (3 * n + 1)) / (1.0 - q) for n in range(depth + 1)]
    return {"q": q, "qn": qn, "hn": hn, "hm": hm, "qm": qm, "q3n1": q3n1}


CACHE_BY_Q_FLOAT = {str(q): build_cache_float(float(q), depth=DEPTH_HI + 5) for q in Q_VALUES}


def coeffs_fast(spec: Dict[str, int], n: int, m: int, cache):
    q = cache["q"]
    x = cache["qn"][n]
    y = cache["qm"][m]
    hn = cache["hn"][n]
    hm = cache["hm"][m]
    qgap = (1.0 - q ** (2 * n - 2 * m - 1)) / (1.0 - q)
    inner = (
        spec["a_gap"] * qgap
        + spec["a_lin_n"] * hn
        + spec["a_lin_m"] * hm
        + spec["a_const"]
        + spec["a_qn"] * x
        + spec["a_qm"] * y
    )
    a = -hn * inner
    b = (
        spec["b_lin_n"] * hn
        + spec["b_const"]
        + spec["b_qn"] * x
        + spec["b_qm"] * y
        + spec["b_q3"] * cache["q3n1"][n]
    )
    return a, b


def eval_cf_fast(spec: Dict[str, int], cache, m: int, depth: int):
    val = 0.0
    try:
        for n in range(depth, 0, -1):
            a, b = coeffs_fast(spec, n, m, cache)
            denom = b + val
            if abs(denom) < 1e-30:
                return None
            val = a / denom
        return 1.0 + val
    except Exception:
        return None


def assess_candidate_fast(spec: Dict[str, int]) -> Optional[Dict[str, object]]:
    ratio_errors = []
    stab_errors = []
    for q in Q_VALUES:
        cache = CACHE_BY_Q_FLOAT[str(q)]
        vals_lo, vals_hi = [], []
        for m in M_VALUES:
            v_lo = eval_cf_fast(spec, cache, m, DEPTH_LO)
            v_hi = eval_cf_fast(spec, cache, m, DEPTH_HI)
            if v_lo is None or v_hi is None:
                return None
            if not np.isfinite(v_lo) or not np.isfinite(v_hi):
                return None
            if abs(v_hi) > 1e8 or abs(v_hi) < 1e-20:
                return None
            vals_lo.append(v_lo)
            vals_hi.append(v_hi)
            stab_errors.append(abs(v_hi - v_lo))
        if max(stab_errors[-len(M_VALUES):]) > float(STABILITY_TOL):
            return None
        ratios = [vals_hi[i + 1] / vals_hi[i] for i in range(len(M_VALUES) - 1)]
        errs = [abs(ratios[i] - float(target_ratio(q, i))) for i in range(len(ratios))]
        ratio_errors.extend(errs)
    return {
        "spec": spec,
        "max_ratio_error": max(ratio_errors),
        "max_stability_error": max(stab_errors),
        "passes_q_wallis": False,
    }


def assess_candidate_precise(spec: Dict[str, int]) -> Optional[Dict[str, object]]:
    all_vals = {}
    ratio_errors: List[mp.mpf] = []
    stab_errors: List[mp.mpf] = []

    for q in Q_VALUES:
        cache = CACHE_BY_Q[str(q)]
        vals_lo, vals_hi = [], []
        for m in M_VALUES:
            v_lo = eval_cf(spec, cache, m, DEPTH_LO)
            v_hi = eval_cf(spec, cache, m, DEPTH_HI)
            if v_lo is None or v_hi is None:
                return None
            if not (mp.isfinite(v_lo) and mp.isfinite(v_hi)):
                return None
            if abs(v_hi) > mp.mpf("1e8") or abs(v_hi) < mp.mpf("1e-20"):
                return None
            vals_lo.append(v_lo)
            vals_hi.append(v_hi)
            stab_errors.append(abs(v_hi - v_lo))
        if max(stab_errors[-len(M_VALUES):]) > STABILITY_TOL:
            return None

        ratios = [vals_hi[i + 1] / vals_hi[i] for i in range(len(M_VALUES) - 1)]
        errs = [abs(ratios[i] - target_ratio(q, i)) for i in range(len(ratios))]
        ratio_errors.extend(errs)
        all_vals[str(q)] = {
            "vals": [str(v) for v in vals_hi],
            "ratios": [str(r) for r in ratios],
            "target": [str(target_ratio(q, i)) for i in range(len(ratios))],
            "max_ratio_error": str(max(errs)),
        }

    return {
        "spec": spec,
        "max_ratio_error": max(ratio_errors),
        "max_stability_error": max(stab_errors),
        "values": all_vals,
        "passes_q_wallis": max(ratio_errors) < PASS_TOL,
    }


def curated_specs() -> List[Dict[str, int]]:
    return [
        # direct q-lift from the classical Wallis family
        dict(a_gap=0, a_lin_n=2, a_lin_m=-2, a_const=-1, a_qn=0, a_qm=0,
             b_lin_n=3, b_const=1, b_qn=0, b_qm=0, b_q3=0),
        # q-gap based lifts
        dict(a_gap=1, a_lin_n=0, a_lin_m=0, a_const=0, a_qn=0, a_qm=0,
             b_lin_n=3, b_const=1, b_qn=0, b_qm=0, b_q3=0),
        dict(a_gap=1, a_lin_n=0, a_lin_m=0, a_const=0, a_qn=0, a_qm=1,
             b_lin_n=3, b_const=1, b_qn=0, b_qm=0, b_q3=0),
        dict(a_gap=1, a_lin_n=0, a_lin_m=0, a_const=0, a_qn=0, a_qm=0,
             b_lin_n=2, b_const=1, b_qn=0, b_qm=0, b_q3=1),
        dict(a_gap=0, a_lin_n=2, a_lin_m=-2, a_const=-1, a_qn=0, a_qm=1,
             b_lin_n=3, b_const=1, b_qn=0, b_qm=0, b_q3=0),
        dict(a_gap=0, a_lin_n=2, a_lin_m=-1, a_const=-1, a_qn=0, a_qm=0,
             b_lin_n=3, b_const=1, b_qn=0, b_qm=0, b_q3=0),
    ]


def random_spec(rng: random.Random) -> Dict[str, int]:
    a_gap = rng.choice([0, 1])
    return {
        "a_gap": a_gap,
        "a_lin_n": rng.choice([0, 1, 2, 3] if a_gap else [1, 2, 3]),
        "a_lin_m": rng.choice([-3, -2, -1, 0]),
        "a_const": rng.choice([-2, -1, 0, 1]),
        "a_qn": rng.choice([-1, 0, 1]),
        "a_qm": rng.choice([-1, 0, 1]),
        "b_lin_n": rng.choice([2, 3, 4]),
        "b_const": rng.choice([0, 1, 2]),
        "b_qn": rng.choice([-1, 0, 1]),
        "b_qm": rng.choice([-1, 0, 1]),
        "b_q3": rng.choice([0, 1]),
    }


def spec_key(spec: Dict[str, int]) -> Tuple[int, ...]:
    return tuple(spec[k] for k in [
        "a_gap", "a_lin_n", "a_lin_m", "a_const", "a_qn", "a_qm",
        "b_lin_n", "b_const", "b_qn", "b_qm", "b_q3"
    ])


# ---------- q-intertwiner attempt ----------

def basis_A(n: int, m: int, cache):
    hn = cache["hn"][n]
    hm = cache["hm"][m]
    x = cache["qn"][n]
    y = cache["qm"][m]
    return [1.0, float(hn), float(hm), float(x), float(y)]


def basis_B(n: int, m: int, cache):
    hn = cache["hn"][n]
    x = cache["qn"][n]
    y = cache["qm"][m]
    return [1.0, float(hn), float(hn * hn), float(x), float(x * x), float(y), float(hn * x)]


def fit_intertwiner_numeric(spec: Dict[str, int], q: mp.mpf):
    cache = build_cache(q, depth=30, max_m=10)
    rows = []
    rhs = []

    for m in range(0, 4):
        for n in range(3, 12):
            a_n, b_n = coeffs(spec, n, m, cache)
            a_nm1, b_nm1 = coeffs(spec, n - 1, m, cache)
            a_p, b_p = coeffs(spec, n, m + 1, cache)

            row1 = []
            # E1 = A_n*b_n + B_n - (b'_n A_{n-1} + a'_n B_{n-2}/a_{n-1})
            for v in basis_A(n, m, cache):
                row1.append(float(b_n) * v)
            for v in basis_A(n - 1, m, cache):
                row1.append(-float(b_p) * v)
            # We combine A-basis unknowns by subtraction: same coeffs for A_n and A_{n-1}
            # convert to 5 unknowns total
            row1 = [float(b_n) * v - float(b_p) * w for v, w in zip(basis_A(n, m, cache), basis_A(n - 1, m, cache))]
            row1 += [v - float(a_p / a_nm1) * w for v, w in zip(basis_B(n, m, cache), basis_B(n - 2, m, cache))]
            rows.append(row1)
            rhs.append(0.0)

            # E2 = A_n*a_n - a'_n A_{n-2} - b'_n B_{n-1} + a'_n*b_{n-1}B_{n-2}/a_{n-1}
            row2 = [float(a_n) * v - float(a_p) * w for v, w in zip(basis_A(n, m, cache), basis_A(n - 2, m, cache))]
            row2 += [-(float(b_p) * v) + float(a_p * b_nm1 / a_nm1) * w
                     for v, w in zip(basis_B(n - 1, m, cache), basis_B(n - 2, m, cache))]
            rows.append(row2)
            rhs.append(0.0)

    M = np.array(rows, dtype=float)
    y = np.array(rhs, dtype=float)
    try:
        _, _, vh = np.linalg.svd(M)
        coeff = vh[-1, :]
        if abs(coeff[0]) > 1e-12:
            coeff = coeff / coeff[0]
    except np.linalg.LinAlgError:
        return None

    # Validate on out-of-sample points
    residuals = []
    for m in range(0, 4):
        for n in range(12, 18):
            a_n, b_n = coeffs(spec, n, m, cache)
            a_nm1, b_nm1 = coeffs(spec, n - 1, m, cache)
            a_p, b_p = coeffs(spec, n, m + 1, cache)
            Acoef = coeff[:5]
            Bcoef = coeff[5:]
            A_n = sum(c * v for c, v in zip(Acoef, basis_A(n, m, cache)))
            A_n1 = sum(c * v for c, v in zip(Acoef, basis_A(n - 1, m, cache)))
            A_n2 = sum(c * v for c, v in zip(Acoef, basis_A(n - 2, m, cache)))
            B_n = sum(c * v for c, v in zip(Bcoef, basis_B(n, m, cache)))
            B_n1 = sum(c * v for c, v in zip(Bcoef, basis_B(n - 1, m, cache)))
            B_n2 = sum(c * v for c, v in zip(Bcoef, basis_B(n - 2, m, cache)))
            e1 = A_n * float(b_n) + B_n - (float(b_p) * A_n1 + float(a_p / a_nm1) * B_n2)
            e2 = A_n * float(a_n) - float(a_p) * A_n2 - float(b_p) * B_n1 + float(a_p * b_nm1 / a_nm1) * B_n2
            residuals.extend([abs(e1), abs(e2)])

    return {
        "coefficients": coeff.tolist(),
        "max_residual": float(max(residuals)) if residuals else None,
    }


def main():
    rng = random.Random(SEED)
    t0 = time.time()
    seen = set()
    candidates: List[Dict[str, int]] = []

    for spec in curated_specs():
        k = spec_key(spec)
        if k not in seen:
            seen.add(k)
            candidates.append(spec)

    while len(candidates) < SEARCH_ITERATIONS:
        spec = random_spec(rng)
        k = spec_key(spec)
        if k in seen:
            continue
        seen.add(k)
        candidates.append(spec)

    print("=" * 78)
    print("  q-WALLIS HYBRID SEARCH")
    print("=" * 78)
    print(f"Iterations: {len(candidates)}")
    print(f"q-grid: {[str(q) for q in Q_VALUES]}")
    print(f"Ratio target: (1-q^(2m+2))/(1-q^(2m+1))")
    print()

    top: List[Dict[str, object]] = []
    breakthroughs: List[Dict[str, object]] = []
    tested = 0
    stable = 0

    for idx, spec in enumerate(candidates, 1):
        tested += 1
        result = assess_candidate_fast(spec)
        if result is None:
            continue
        stable += 1
        top.append(result)
        top.sort(key=lambda r: (r["max_ratio_error"], r["max_stability_error"]))
        top = top[:10]

        # Only expensive-check serious contenders.
        if result["max_ratio_error"] < 1e-10:
            precise = assess_candidate_precise(spec)
            if precise is not None and precise["passes_q_wallis"]:
                print(f"PASS @ candidate {idx}: spec={spec}")
                print(f"  max ratio error = {mp.nstr(precise['max_ratio_error'], 8)}")
                intertwiners = {}
                ok = True
                for q in Q_VALUES:
                    fit = fit_intertwiner_numeric(spec, q)
                    intertwiners[str(q)] = fit
                    if fit is None or fit["max_residual"] is None or fit["max_residual"] > 1e-10:
                        ok = False
                precise["intertwiner_fit"] = intertwiners
                precise["quantum_breakthrough"] = ok
                breakthroughs.append(precise)
                if ok:
                    print("  >>> QUANTUM BREAKTHROUGH <<<")

        if idx % 250 == 0:
            best_err = top[0]["max_ratio_error"] if top else None
            print(f"  scanned {idx:4d} / {len(candidates)}   stable={stable:4d}   best_err={best_err:.6e} " if best_err is not None else f"  scanned {idx:4d} / {len(candidates)}   stable={stable:4d}   best_err=n/a")

    elapsed = time.time() - t0

    confirmed_top = []
    for item in top[:5]:
        precise = assess_candidate_precise(item["spec"])
        confirmed_top.append(precise if precise is not None else item)

    print()
    print("Top candidates by q-Wallis error:")
    for rank, item in enumerate(confirmed_top[:5], 1):
        print(f"  #{rank}: err={mp.nstr(item['max_ratio_error'], 12)}  stab={mp.nstr(item['max_stability_error'], 8)}  spec={item['spec']}")

    if not breakthroughs:
        print()
        print("Result: no candidate reached the 20-decimal q-Wallis threshold; no Quantum Breakthrough flagged.")
        if confirmed_top:
            print(f"Best near-miss error: {mp.nstr(confirmed_top[0]['max_ratio_error'], 12)}")
            best_fit = {}
            for q in Q_VALUES:
                fit = fit_intertwiner_numeric(confirmed_top[0]["spec"], q)
                best_fit[str(q)] = fit
            confirmed_top[0]["intertwiner_fit"] = best_fit
            print("Best near-miss intertwiner residuals:")
            for q, fit in best_fit.items():
                if fit is None:
                    print(f"  q={q}: no simple fit")
                else:
                    print(f"  q={q}: max residual {fit['max_residual']:.3e}")

    out = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "iterations": len(candidates),
        "tested": tested,
        "stable": stable,
        "pass_tolerance": str(PASS_TOL),
        "breakthrough_count": len([b for b in breakthroughs if b.get('quantum_breakthrough')]),
        "passes_count": len(breakthroughs),
        "top_candidates": confirmed_top[:5],
        "breakthroughs": breakthroughs,
        "elapsed_seconds": elapsed,
    }

    Path("results").mkdir(exist_ok=True)
    out_path = Path("results/q_wallis_hybrid_search.json")
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print()
    print(f"Saved detailed results to {out_path}")
    print(f"Elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
