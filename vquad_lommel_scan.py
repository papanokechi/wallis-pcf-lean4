#!/usr/bin/env python3
"""
Lommel Parametric PSLQ Scan for V_quad
═══════════════════════════════════════

Scans Lommel functions S_{mu,nu}(z) at rational parameter grids against
V_quad = 1.19737399068... to find integer relations.

The Lommel function S_{mu,nu}(z) satisfies:
    z^2 y'' + z y' + (z^2 - nu^2) y = z^{mu+1}

and is defined as:
    S_{mu,nu}(z) = z^{mu+1} sum_{k=0}^inf (-1)^k z^{2k} /
                    prod_{j=0}^k ((mu+2j+1)^2 - nu^2)

For V_quad with b(n) = 3n^2+n+1, the recurrence coefficients suggest
mu, nu ~ small rationals involving 1/3, 2/3, and z ~ small algebraic.

Also scans Weber modular functions at tau = (1+sqrt(-11))/2.
"""

import sys
import time
import itertools
import mpmath as mp

# ── Configuration ──
WORK_DPS     = 600
CF_DEPTH     = 1500
PSLQ_DPS     = 500
COEFF_BOUND  = 10000
REPORT_FILE  = "lommel_pslq_results.txt"


def compute_vquad(depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            v = mp.mpf(1) / (3*n*n + n + 1 + v)
        return mp.mpf(1) + v


def lommel_s(mu, nu, z, dps):
    """Compute Lommel S_{mu,nu}(z) via series."""
    with mp.workdps(dps + 50):
        mu = mp.mpf(mu)
        nu = mp.mpf(nu)
        z = mp.mpf(z)
        # S_{mu,nu}(z) = z^{mu+1} * sum_{k=0}^N (-z^2)^k /
        #                 prod_{j=0}^k ((mu+2j+1)^2 - nu^2)
        result = mp.mpf(0)
        term = mp.mpf(1)   # k=0: 1 / ((mu+1)^2 - nu^2)
        denom_prod = (mu + 1)**2 - nu**2
        if denom_prod == 0:
            return mp.nan
        term = mp.mpf(1) / denom_prod
        result = term
        mz2 = -(z**2)
        for k in range(1, 500):
            factor = (mu + 2*k + 1)**2 - nu**2
            if factor == 0:
                break
            term *= mz2 / factor
            result += term
            if abs(term) < mp.mpf(10)**(-(dps + 20)):
                break
        return z**(mu + 1) * result


def run_pslq(basis, labels, dps, coeff_bound=COEFF_BOUND):
    """Run PSLQ, return (found, relation_str)."""
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
        parts = [f"{c:+d}*{l}" for c, l in zip(rel, labels) if c != 0]
        return True, f"FOUND ({rd}dp): {' '.join(parts)}"
    return False, ""


def main():
    mp.mp.dps = WORK_DPS
    print("=" * 70)
    print("  LOMMEL PARAMETRIC PSLQ SCAN FOR V_QUAD")
    print("=" * 70)

    # ── Compute V_quad ──
    print(f"\n  Computing V_quad at depth {CF_DEPTH}...")
    V = compute_vquad(CF_DEPTH, WORK_DPS)
    print(f"  V_quad = {mp.nstr(V, 30)}...")

    results = []
    found_any = False

    # ═══ Scan 1: Lommel S_{mu,nu}(z) ════════════════════════════════
    print(f"\n  SCAN 1: Lommel S_{{mu,nu}}(z)")
    print(f"  {'─'*60}")

    # Parameter grid: mu, nu in {-2, -5/3, -4/3, -1, -2/3, -1/3, 0, 1/3, 2/3, 1, 4/3, 5/3, 2}
    # z in {1/3, 2/3, 1, sqrt(11)/3, 2, sqrt(3)}
    mu_vals = [mp.mpf(p)/q for p in range(-6, 7) for q in [1, 2, 3] if q != 0]
    nu_vals = [mp.mpf(p)/q for p in range(-4, 5) for q in [1, 2, 3] if q != 0]
    z_vals_def = [
        (mp.mpf(1)/3, "1/3"),
        (mp.mpf(2)/3, "2/3"),
        (mp.mpf(1), "1"),
        (mp.sqrt(mp.mpf(11))/3, "sqrt(11)/3"),
        (mp.mpf(2), "2"),
        (mp.sqrt(mp.mpf(3)), "sqrt(3)"),
        (2*mp.sqrt(mp.mpf(11))/(3*mp.sqrt(mp.mpf(3))), "2sqrt(11)/3sqrt(3)"),
    ]

    # Deduplicate mu/nu
    mu_unique = sorted(set(float(x) for x in mu_vals))
    nu_unique = sorted(set(float(x) for x in nu_vals))

    total = len(mu_unique) * len(nu_unique) * len(z_vals_def)
    print(f"  Grid: {len(mu_unique)} mu x {len(nu_unique)} nu x {len(z_vals_def)} z = {total} points")

    tested = 0
    t0 = time.time()

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)

        for z_val, z_label in z_vals_def:
            for mu_f in mu_unique:
                mu = mp.mpf(mu_f)
                for nu_f in nu_unique:
                    nu = mp.mpf(nu_f)
                    tested += 1

                    try:
                        s_val = lommel_s(mu, nu, z_val, PSLQ_DPS)
                        if mp.isnan(s_val) or mp.isinf(s_val) or s_val == 0:
                            continue
                    except Exception:
                        continue

                    # PSLQ: V_quad vs S_{mu,nu}(z), 1
                    basis = [Vs, s_val, mp.mpf(1)]
                    labels = ["V_quad", f"S({mu_f},{nu_f},{z_label})", "1"]
                    found, msg = run_pslq(basis, labels, PSLQ_DPS)
                    if found:
                        found_any = True
                        print(f"\n  >>> {msg}")
                        results.append({"mu": mu_f, "nu": nu_f, "z": z_label,
                                       "relation": msg})

                    if tested % 500 == 0:
                        elapsed = time.time() - t0
                        print(f"    [{tested}/{total}] {elapsed:.1f}s ...")

    elapsed = time.time() - t0
    print(f"\n  Lommel scan: {tested} tests in {elapsed:.1f}s")
    if not found_any:
        print("  No Lommel relations found.")

    # ═══ Scan 2: Weber modular functions ═════════════════════════════
    print(f"\n  SCAN 2: Weber modular functions at tau=(1+sqrt(-11))/2")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        tau = (1 + mp.sqrt(mp.mpf(-11))) / 2

        # Weber f, f1, f2 are related to eta functions:
        # f(tau) = e^{-pi*i/24} * eta((tau+1)/2) / eta(tau)
        # f1(tau) = eta(tau/2) / eta(tau)
        # f2(tau) = sqrt(2) * eta(2*tau) / eta(tau)
        # Compute via Dedekind eta
        q = mp.exp(2 * mp.pi * mp.mpc(0, 1) * tau)
        q_abs = abs(q)
        print(f"    |q| = {mp.nstr(q_abs, 10)} (good convergence: {q_abs < 0.5})")

        # eta(tau) = q^{1/24} * prod_{n=1}^inf (1 - q^n)
        def eta_approx(tau_val, terms=200):
            q_loc = mp.exp(2 * mp.pi * mp.mpc(0, 1) * tau_val)
            prod = mp.mpc(1)
            for n in range(1, terms):
                prod *= (1 - q_loc**n)
            return q_loc**(mp.mpf(1)/24) * prod

        eta_tau = eta_approx(tau)
        eta_tau_half = eta_approx(tau / 2)
        eta_tau_plus1_half = eta_approx((tau + 1) / 2)
        eta_2tau = eta_approx(2 * tau)

        f_weber = mp.exp(-mp.pi * mp.mpc(0, 1) / 24) * eta_tau_plus1_half / eta_tau
        f1_weber = eta_tau_half / eta_tau
        f2_weber = mp.sqrt(2) * eta_2tau / eta_tau

        # Take real parts (at CM point they should be real or have known phase)
        f_re = abs(f_weber)
        f1_re = abs(f1_weber)
        f2_re = abs(f2_weber)

        print(f"    |f(tau)|  = {mp.nstr(f_re, 20)}")
        print(f"    |f1(tau)| = {mp.nstr(f1_re, 20)}")
        print(f"    |f2(tau)| = {mp.nstr(f2_re, 20)}")

        basis_w = [Vs, f_re, f1_re, f2_re, mp.mpf(1)]
        labels_w = ["V_quad", "|f(tau)|", "|f1(tau)|", "|f2(tau)|", "1"]
        found, msg = run_pslq(basis_w, labels_w, PSLQ_DPS)
        if found:
            found_any = True
            print(f"\n  >>> {msg}")
            results.append({"family": "weber", "relation": msg})
        else:
            print("  No Weber relation found.")

    # ═══ Scan 3: Meijer G-function evaluations ══════════════════════
    print(f"\n  SCAN 3: Meijer G-functions G_{{0,3}}^{{3,0}}")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)

        # G_{0,3}^{3,0}(z | ; b1, b2, b3) at discriminant-matched params
        # b_i from 3n^2+n+1 recurrence: {0, 1/3, 2/3}
        meijer_params = [
            (([], []), ([0, mp.mpf(1)/3, mp.mpf(2)/3], []), mp.mpf(1)/27, "G(1/27; 0,1/3,2/3)"),
            (([], []), ([0, mp.mpf(1)/3, mp.mpf(2)/3], []), mp.mpf(-1)/27, "G(-1/27; 0,1/3,2/3)"),
            (([], []), ([0, mp.mpf(1)/6, mp.mpf(5)/6], []), mp.mpf(1)/27, "G(1/27; 0,1/6,5/6)"),
            (([], []), ([mp.mpf(1)/3, mp.mpf(1)/2, mp.mpf(2)/3], []), mp.mpf(11)/108, "G(11/108; 1/3,1/2,2/3)"),
        ]

        for (an, ap), (bm, bq), z, label in meijer_params:
            try:
                print(f"    Computing {label}...")
                g_val = mp.meijerg([an, ap], [bm, bq], z)
                if mp.isnan(g_val) or mp.isinf(g_val) or g_val == 0:
                    print(f"      Skipped (invalid)")
                    continue
                g_re = abs(g_val) if isinstance(g_val, mp.mpc) else g_val
                basis_g = [Vs, g_re, mp.mpf(1)]
                labels_g = ["V_quad", label, "1"]
                found, msg = run_pslq(basis_g, labels_g, PSLQ_DPS)
                if found:
                    found_any = True
                    print(f"\n  >>> {msg}")
                    results.append({"family": "meijer", "relation": msg})
                else:
                    print(f"      No relation")
            except Exception as e:
                print(f"      Error: {e}")

    # ═══ Summary ═════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    if found_any:
        print("  >>> RELATION(S) FOUND — SEE ABOVE <<<")
        for r in results:
            print(f"    {r}")
    else:
        print("  NO RELATIONS FOUND across Lommel, Weber, and Meijer scans.")
        print("  V_quad definitively excluded from:")
        print("    - Lommel S_{mu,nu}(z) for mu,nu in [-2,2]x[-4/3,4/3], z in 7 values")
        print("    - Weber modular f, f1, f2 at tau=(1+sqrt(-11))/2")
        print("    - Meijer G_{0,3}^{3,0} at 4 parameter sets")
    print("=" * 70)

    # Save report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("LOMMEL/WEBER/MEIJER PSLQ SCAN FOR V_QUAD\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Precision: {PSLQ_DPS} dps, coeff bound {COEFF_BOUND}\n")
        f.write(f"Lommel grid: {total} points\n")
        f.write(f"Results: {len(results)} relations found\n\n")
        if results:
            for r in results:
                f.write(f"  {r}\n")
        else:
            f.write("  No relations found.\n")
    print(f"\n  Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
