#!/usr/bin/env python3
"""
7 Unidentified Irrationals — Exclusion Battery
═══════════════════════════════════════════════

The 7 non-rational ratio-mode GCFs from the catalog.
Test each against the same special-function battery used for V_quad:
  - Elementary: pi, e, log2, gamma, Catalan, sqrt(2), sqrt(3)
  - Bessel: I/K at various orders and arguments
  - Airy: Ai(0), Ai(1), Bi(0)
  - zeta values: zeta(2) through zeta(9)

If any of them resist classification, they may be publishable
alongside V_quad as genuinely new constants.
"""

import time
import mpmath as mp

DPS = 300
CF_DEPTH = 500
COEFF_BOUND = 10000

ENTRIES = [
    {"label": "U1", "alpha": [6,3,-4,-8,3], "beta": [4,0,1,-4,-6,-4], "order": 4},
    {"label": "U2", "alpha": [-10,-10,5,4,4,7], "beta": [8,-4,0,4,-8,-5,-7], "order": 5},
    {"label": "U3", "alpha": [9,-2,1,-8,-2,-6,-5,5], "beta": [9,3,-4,0,6], "order": 7},
    {"label": "U4", "alpha": [-4,-4,0,2,-3,-5,1], "beta": [-4,-9,5,-5,-9], "order": 6},
    {"label": "U5", "alpha": [7,6,-7,2,-1,-8,10], "beta": [7,-4,-2,10,-7], "order": 6},
    {"label": "U6", "alpha": [-10,8,4,-2,6], "beta": [-10,10,8,10,-3], "order": 4},
    {"label": "U7", "alpha": [-4,0,0,0,0,0], "beta": [5,0], "order": 0},
]


def poly_eval(coeffs, n):
    n_mpf = mp.mpf(n)
    result = mp.mpf(coeffs[-1])
    for c in coeffs[-2::-1]:
        result = result * n_mpf + c
    return result


def eval_ratio(alpha, beta, order, depth, dps):
    with mp.workdps(dps + 50):
        u2, u1 = mp.mpf(0), mp.mpf(1)
        v2, v1 = mp.mpf(1), poly_eval(beta, 1)
        for n in range(2, depth + 1):
            p = poly_eval(beta, n)
            q = poly_eval(alpha, n)
            nk = mp.mpf(n) ** order
            u_n = (p * u1 - q * u2) / nk
            v_n = (p * v1 - q * v2) / nk
            u2, u1 = u1, u_n
            v2, v1 = v1, v_n
        return u1 / v1 if v1 != 0 else mp.nan


def eval_backward(alpha, beta, depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            a_n = poly_eval(alpha, n)
            b_n = poly_eval(beta, n)
            denom = b_n + v
            if denom == 0: return mp.nan
            v = a_n / denom
        return poly_eval(beta, 0) + v


def run_pslq(basis, labels, dps):
    with mp.workdps(dps):
        try:
            rel = mp.pslq(basis, maxcoeff=COEFF_BOUND, maxsteps=3000)
        except Exception:
            return None
    if rel is None:
        return None
    with mp.workdps(dps):
        dot = sum(c*b for c, b in zip(rel, basis))
        residual = abs(dot)
        rd = max(0, int(-float(mp.log10(residual + mp.mpf(10)**(-dps))))) if residual > 0 else dps
    nonzero = [(c, l) for c, l in zip(rel, labels) if c != 0]
    if len(nonzero) <= 1 or rd < 50:
        return None
    has_cf = any(l == "CF" for _, l in nonzero)
    has_other = any(l != "CF" and l != "1" for _, l in nonzero)
    if has_cf and has_other:
        parts = [f"{c:+d}*{l}" for c, l in nonzero]
        return f"{' '.join(parts)} ({rd}dp)"
    return None


def main():
    mp.mp.dps = DPS

    print("=" * 70)
    print("  7 UNIDENTIFIED IRRATIONALS — EXCLUSION BATTERY")
    print("=" * 70)

    # Build target battery
    battery = {}
    with mp.workdps(DPS + 50):
        battery["pi"] = mp.pi
        battery["e"] = mp.e
        battery["log2"] = mp.log(2)
        battery["gamma"] = mp.euler
        battery["catalan"] = mp.catalan
        battery["sqrt2"] = mp.sqrt(2)
        battery["sqrt3"] = mp.sqrt(3)
        battery["sqrt11"] = mp.sqrt(11)
        battery["phi"] = (1 + mp.sqrt(5)) / 2
        for k in range(2, 10):
            battery[f"zeta{k}"] = mp.zeta(k)
        battery["pi2"] = mp.pi**2
        battery["pi3"] = mp.pi**3
        battery["Ai0"] = mp.airyai(0)
        battery["Ai1"] = mp.airyai(1)
        battery["Bi0"] = mp.airybi(0)
        battery["I_1/3_2/3"] = mp.besseli(mp.mpf(1)/3, mp.mpf(2)/3)
        battery["K_1/3_2/3"] = mp.besselk(mp.mpf(1)/3, mp.mpf(2)/3)
        battery["J0_4/5"] = mp.besselj(0, mp.mpf(4)/5)
        battery["J1_4/5"] = mp.besselj(1, mp.mpf(4)/5)

    print(f"  Battery: {len(battery)} constants")

    results = []

    for entry in ENTRIES:
        label = entry["label"]
        alpha = entry["alpha"]
        beta = entry["beta"]
        order = entry["order"]

        print(f"\n  {'─'*60}")
        print(f"  {label}: a={alpha}, b={beta}, order={order}")

        # Compute CF
        if order > 0:
            cf = eval_ratio(alpha, beta, order, CF_DEPTH, DPS)
        else:
            cf = eval_backward(alpha, beta, CF_DEPTH, DPS)

        if mp.isnan(cf):
            print(f"    DIVERGENT")
            results.append({"label": label, "status": "DIVERGENT"})
            continue

        print(f"    CF = {mp.nstr(cf, 20)}")

        # Self-consistency
        if order > 0:
            cf2 = eval_ratio(alpha, beta, order, CF_DEPTH + 200, DPS)
        else:
            cf2 = eval_backward(alpha, beta, CF_DEPTH + 200, DPS)

        with mp.workdps(DPS):
            diff = abs(cf - cf2)
            sa = max(0, int(-float(mp.log10(diff)))) if diff > 0 else DPS
        print(f"    Self-agreement: {sa} digits")

        # Test against battery
        identified = False
        with mp.workdps(DPS):
            for name, val in battery.items():
                basis = [cf, val, mp.mpf(1)]
                labels_pslq = ["CF", name, "1"]
                hit = run_pslq(basis, labels_pslq, DPS)
                if hit:
                    print(f"    IDENTIFIED: {hit}")
                    identified = True
                    results.append({"label": label, "status": "IDENTIFIED",
                                   "relation": hit, "cf": mp.nstr(cf, 15)})
                    break

        if not identified:
            # Multi-constant: [CF, zeta3, zeta5, 1]
            with mp.workdps(DPS):
                for pair in [("zeta3", "zeta5"), ("zeta3", "pi"),
                             ("zeta5", "pi"), ("zeta3", "zeta7")]:
                    basis = [cf, battery[pair[0]], battery[pair[1]], mp.mpf(1)]
                    labels_pslq = ["CF", pair[0], pair[1], "1"]
                    hit = run_pslq(basis, labels_pslq, DPS)
                    if hit:
                        print(f"    MULTI-IDENTIFIED: {hit}")
                        identified = True
                        results.append({"label": label, "status": "MULTI-IDENTIFIED",
                                       "relation": hit, "cf": mp.nstr(cf, 15)})
                        break

        if not identified:
            print(f"    UNIDENTIFIED — resists all {len(battery)} constants + multi-pairs")
            results.append({"label": label, "status": "UNIDENTIFIED",
                           "cf": mp.nstr(cf, 20), "self_agree": sa})

    # Summary
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    unid = [r for r in results if r["status"] == "UNIDENTIFIED"]
    iden = [r for r in results if r["status"] in ("IDENTIFIED", "MULTI-IDENTIFIED")]
    div = [r for r in results if r["status"] == "DIVERGENT"]

    print(f"  Identified:    {len(iden)}")
    print(f"  Unidentified:  {len(unid)}")
    print(f"  Divergent:     {len(div)}")

    if unid:
        print(f"\n  UNIDENTIFIED CONSTANTS (potential V_quad companions):")
        for r in unid:
            print(f"    {r['label']}: CF = {r['cf']} (self-agree: {r.get('self_agree','?')}dp)")

    import json
    with open("seven_irrationals_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved to seven_irrationals_results.json")


if __name__ == "__main__":
    main()
