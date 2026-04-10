#!/usr/bin/env python3
"""
WEAK Candidate Diagnostic — Resolve the 2 ratio-mode verification gaps
═══════════════════════════════════════════════════════════════════════

The 2 WEAK candidates both:
  - Have 1050+ digit self-agreement (they converge fine)
  - Are high-order ratio-mode GCFs (order 4 and 5)
  - Failed closed-form parsing (non-trivial algebraic roots)

This script runs proper PSLQ against the target constant at high
precision to determine whether they are genuine identities.
"""

import json
import time
import mpmath as mp

VERIFY_DPS = 1500
CF_DEPTH_LOW = 1000
CF_DEPTH_HIGH = 1500

WEAK_CANDIDATES = [
    {
        "index": 3,
        "target": "zeta5",
        "alpha": [6, 3, -4, -8, 3],
        "beta": [4, 0, 1, -4, -6, -4],
        "mode": "ratio",
        "order": 4,
        "formula": "1*CF^2 + -2*CF*zeta5 + -2*CF + 8*zeta5 + -8 = 0",
    },
    {
        "index": 8,
        "target": "zeta3",
        "alpha": [-10, -10, 5, 4, 4, 7],
        "beta": [8, -4, 0, 4, -8, -5, -7],
        "mode": "ratio",
        "order": 5,
        "formula": "?",
    },
]


def poly_eval(coeffs, n):
    n_mpf = mp.mpf(n)
    result = mp.mpf(coeffs[-1])
    for c in coeffs[-2::-1]:
        result = result * n_mpf + c
    return result


def eval_backward(alpha, beta, depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            a_n = poly_eval(alpha, n)
            b_n = poly_eval(beta, n)
            denom = b_n + v
            if denom == 0:
                return mp.nan
            v = a_n / denom
        b_0 = poly_eval(beta, 0)
        return b_0 + v


def eval_ratio(alpha, beta, order, depth, dps):
    with mp.workdps(dps + 50):
        u_prev2 = mp.mpf(0)
        u_prev1 = mp.mpf(1)
        v_prev2 = mp.mpf(1)
        v_prev1 = poly_eval(beta, 1)

        for n in range(2, depth + 1):
            p_n = poly_eval(beta, n)
            q_n = poly_eval(alpha, n)
            n_ord = mp.mpf(n) ** order
            u_n = (p_n * u_prev1 - q_n * u_prev2) / n_ord
            v_n = (p_n * v_prev1 - q_n * v_prev2) / n_ord
            u_prev2, u_prev1 = u_prev1, u_n
            v_prev2, v_prev1 = v_prev1, v_n

        if v_prev1 == 0:
            return mp.nan
        return u_prev1 / v_prev1


def main():
    mp.mp.dps = VERIFY_DPS

    targets = {
        "zeta3": mp.zeta(3),
        "zeta5": mp.zeta(5),
    }

    print("=" * 70)
    print("  WEAK CANDIDATE DIAGNOSTIC")
    print("=" * 70)

    results = []

    for cand in WEAK_CANDIDATES:
        alpha = cand["alpha"]
        beta = cand["beta"]
        mode = cand["mode"]
        order = cand["order"]
        tgt_name = cand["target"]
        tgt_val = targets[tgt_name]

        print(f"\n  Candidate [{cand['index']}]: {tgt_name} | mode={mode} order={order}")
        print(f"    a(n) = {alpha}")
        print(f"    b(n) = {beta}")
        print(f"    Formula: {cand['formula']}")

        # Compute at two depths
        t0 = time.time()
        if mode == "ratio":
            v1 = eval_ratio(alpha, beta, order, CF_DEPTH_LOW, VERIFY_DPS)
            v2 = eval_ratio(alpha, beta, order, CF_DEPTH_HIGH, VERIFY_DPS)
        else:
            v1 = eval_backward(alpha, beta, CF_DEPTH_LOW, VERIFY_DPS)
            v2 = eval_backward(alpha, beta, CF_DEPTH_HIGH, VERIFY_DPS)
        elapsed = time.time() - t0

        if mp.isnan(v1) or mp.isnan(v2):
            print(f"    RESULT: DIVERGENT ({elapsed:.1f}s)")
            results.append({"index": cand["index"], "status": "DIVERGENT"})
            continue

        # Self-agreement
        with mp.workdps(VERIFY_DPS):
            diff = abs(v1 - v2)
            self_agree = max(0, int(-float(mp.log10(diff)))) if diff > 0 else VERIFY_DPS

        print(f"    CF value (30 digits): {mp.nstr(v2, 30)}")
        print(f"    Self-agreement: {self_agree} digits ({elapsed:.1f}s)")

        # PSLQ: try [CF^2, CF*target, CF, target, 1]
        with mp.workdps(VERIFY_DPS):
            cf = mp.mpf(v2)
            tgt = mp.mpf(tgt_val)
            basis = [cf**2, cf * tgt, cf, tgt, mp.mpf(1)]
            labels = ["CF^2", f"CF*{tgt_name}", "CF", tgt_name, "1"]

            print(f"    Running degree-2 PSLQ (5 elements)...")
            t0 = time.time()
            rel = mp.pslq(basis, maxcoeff=10000, maxsteps=5000)
            pslq_time = time.time() - t0

            if rel is not None:
                dot = sum(c * b for c, b in zip(rel, basis))
                residual = abs(dot)
                rd = max(0, int(-float(mp.log10(residual)))) if residual > 0 else VERIFY_DPS

                nonzero = [(c, l) for c, l in zip(rel, labels) if c != 0]
                relation_str = " + ".join(f"{c}*{l}" for c, l in nonzero) + " = 0"

                print(f"    PSLQ RESULT ({pslq_time:.1f}s):")
                print(f"      {relation_str}")
                print(f"      Residual: {rd} digits")

                # Solve for CF
                # c0*CF^2 + c1*CF*T + c2*CF + c3*T + c4 = 0
                # CF*(c0*CF + c1*T + c2) = -(c3*T + c4)
                c = rel
                if c[0] != 0 or c[1] != 0:  # quadratic in CF
                    # a*CF^2 + b*CF + c = 0 where b = c1*T+c2, c_const = c3*T+c4
                    a_coeff = mp.mpf(c[0])
                    b_coeff = mp.mpf(c[1]) * tgt + mp.mpf(c[2])
                    c_coeff = mp.mpf(c[3]) * tgt + mp.mpf(c[4])
                    disc = b_coeff**2 - 4 * a_coeff * c_coeff
                    if disc >= 0:
                        root1 = (-b_coeff + mp.sqrt(disc)) / (2 * a_coeff) if a_coeff != 0 else -c_coeff / b_coeff
                        root2 = (-b_coeff - mp.sqrt(disc)) / (2 * a_coeff) if a_coeff != 0 else root1
                        # Pick the root closest to CF
                        best = root1 if abs(root1 - cf) < abs(root2 - cf) else root2
                        check = abs(best - cf)
                        check_dig = max(0, int(-float(mp.log10(check)))) if check > 0 else VERIFY_DPS
                        print(f"      Solved CF = {mp.nstr(best, 20)}")
                        print(f"      Agreement: {check_dig} digits")

                        if rd >= 200:
                            status = "VERIFIED_ALGEBRAIC"
                        elif rd >= 50:
                            status = "LIKELY_VALID"
                        else:
                            status = "SUSPICIOUS"
                        print(f"    STATUS: {status}")
                else:
                    # Linear: c2*CF + c3*T + c4 = 0 => CF = -(c3*T+c4)/c2
                    if c[2] != 0:
                        solved = -(mp.mpf(c[3]) * tgt + mp.mpf(c[4])) / mp.mpf(c[2])
                        check = abs(solved - cf)
                        check_dig = max(0, int(-float(mp.log10(check)))) if check > 0 else VERIFY_DPS
                        print(f"      Linear: CF = {mp.nstr(solved, 20)}")
                        print(f"      Agreement: {check_dig} digits")
                        status = "VERIFIED_RATIONAL" if rd >= 200 else "WEAK"
                        print(f"    STATUS: {status}")
                    else:
                        status = "PSLQ_ODD_FORM"
                        print(f"    STATUS: {status}")

                results.append({
                    "index": cand["index"], "status": status,
                    "relation": relation_str, "residual_digits": rd,
                    "self_agree": self_agree,
                })
            else:
                print(f"    PSLQ: No relation found ({pslq_time:.1f}s)")

                # Try degree-1 PSLQ as fallback
                basis_lin = [cf, tgt, mp.mpf(1)]
                labels_lin = ["CF", tgt_name, "1"]
                rel_lin = mp.pslq(basis_lin, maxcoeff=10000)
                if rel_lin is not None:
                    dot = sum(c * b for c, b in zip(rel_lin, basis_lin))
                    rd = max(0, int(-float(mp.log10(abs(dot))))) if abs(dot) > 0 else VERIFY_DPS
                    ns = [(c, l) for c, l in zip(rel_lin, labels_lin) if c != 0]
                    rstr = " + ".join(f"{c}*{l}" for c, l in ns) + " = 0"
                    print(f"    Linear fallback: {rstr} ({rd} digits)")
                    results.append({"index": cand["index"], "status": "VERIFIED_LINEAR",
                                   "relation": rstr, "residual_digits": rd})
                else:
                    print(f"    No relation found at degree 1 or 2.")
                    results.append({"index": cand["index"], "status": "NO_RELATION",
                                   "self_agree": self_agree})

    # Summary
    print("\n" + "=" * 70)
    print("  DIAGNOSTIC SUMMARY")
    print("=" * 70)
    for r in results:
        idx = r["index"]
        st = r["status"]
        rel = r.get("relation", "—")
        rd = r.get("residual_digits", "—")
        print(f"  [{idx}] {st:25s} | residual={rd} digits | {rel}")

    with open("weak_diagnostic_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved to weak_diagnostic_results.json")


if __name__ == "__main__":
    main()
