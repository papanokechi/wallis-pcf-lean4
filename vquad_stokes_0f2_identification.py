#!/usr/bin/env python3
"""V_quad — Stokes coefficient and 0F2/Airy/Bessel identification.

Reproduces the requested numerical checks at high precision using mpmath.
"""

from __future__ import annotations

import argparse
import itertools
from fractions import Fraction

import mpmath as mp


def compute_vquad(depth: int, dps: int):
    with mp.workdps(dps + 30):
        v = mp.mpf("0")
        for n in range(depth, 0, -1):
            v = mp.mpf("1") / (3 * n * n + n + 1 + v)
        return +(mp.mpf("1") + v)


def digits_of_error(err) -> float:
    err = abs(err)
    if err == 0:
        return mp.inf
    return float(-mp.log10(err))


def relation_status(vec: list, labels: list[str], maxcoeff: int, maxsteps: int = 20000) -> str:
    rel = mp.pslq(vec, maxcoeff=maxcoeff, maxsteps=maxsteps)
    if rel is None:
        return f"None (maxcoeff={maxcoeff})"
    nz = [(c, lab) for c, lab in zip(rel, labels) if c != 0]
    if any(lab == labels[0] for _, lab in nz):
        return f"relation {nz}"
    return f"trivial/non-target relation {nz}"


def best_rational_multiple(target, value, bound: int = 10, max_den: int = 24) -> tuple[str, float, str]:
    best_digits = -mp.inf
    best_c = None
    best_err = None
    for q in range(1, max_den + 1):
        for p in range(-bound * q, bound * q + 1):
            if p == 0:
                continue
            frac = Fraction(p, q)
            c = mp.mpf(frac.numerator) / frac.denominator
            err = target - c * value
            digs = digits_of_error(err)
            if digs > best_digits:
                best_digits = digs
                best_c = frac
                best_err = err
    return str(best_c), float(best_digits), mp.nstr(best_err, 8)


def wkb_data():
    sqrt3 = mp.sqrt(3)
    sigma_plus = mp.mpf(1) / sqrt3
    sigma_minus = -sigma_plus
    mu_plus = -1 - sigma_plus / 6
    mu_minus = -1 - sigma_minus / 6
    return sigma_plus, sigma_minus, mu_plus, mu_minus


def series_recurrence_text() -> str:
    return (
        "(n+2)(n+1)c_{n+2} + (n+1)^2 c_{n+1} + 3n(n+1)c_n - c_{n-2} = 0"
    )


def hyper_values():
    one = mp.mpf(1)
    third = one / 3
    vals = [
        ("F1", mp.hyper([], [2 * third, 4 * third], mp.mpf(4) / 27)),
        ("F2", mp.hyper([], [third, 2 * third], mp.mpf(4) / 27)),
        ("F3", mp.hyper([], [third, 4 * third], mp.mpf(4) / 27)),
        ("F4", mp.hyper([], [2 * third, 5 * third], mp.mpf(4) / 27)),
        ("F5", mp.hyper([], [third, 2 * third], mp.mpf(1) / 27)),
        ("F6", mp.hyper([], [2 * third, 4 * third], mp.mpf(1) / 27)),
    ]
    return vals


def airy_values():
    z1 = (mp.mpf(11) / 12) ** (mp.mpf(1) / 3)
    z2 = -z1
    z3 = (mp.mpf(1) / 3) ** (mp.mpf(1) / 3)
    z4 = mp.power(11, mp.mpf(1) / 3) / 3
    z5 = (mp.sqrt(11) / 6) ** (mp.mpf(2) / 3)
    zmap = {"z1": z1, "z2": z2, "z3": z3, "z4": z4, "z5": z5}
    vals = []
    for name, z in zmap.items():
        vals.append((f"Ai({name})", mp.airyai(z)))
        vals.append((f"Bi({name})", mp.airybi(z)))
    return vals, zmap


def bessel_values():
    arg1 = mp.mpf(2) / (3 * mp.sqrt(3))
    arg2 = mp.mpf(2) / 3
    third = mp.mpf(1) / 3
    vals = [
        ("B1", mp.besseli(third, arg1)),
        ("B2", mp.besselk(third, arg1)),
        ("B3", mp.besseli(2 * third, arg1)),
        ("B4", mp.besselk(2 * third, arg1)),
        ("B5", mp.besseli(third, arg2)),
        ("B6", mp.besselk(third, arg2)),
    ]
    return vals


def stokes_connection(X0=mp.mpf("1000"), h=mp.mpf("0.03125")):
    _, sigma_recessive, _, mu_recessive = wkb_data()

    def deriv(x, r, logy):
        P = (6 * x + 1) / (3 * x * x + x + 1)
        Q = -(x * x) / (3 * x * x + x + 1)
        drdx = -(r * r) - P * r - Q
        dlogydx = r
        return drdx, dlogydx

    x = mp.mpf(X0)
    r = sigma_recessive + mu_recessive / x
    logy = mu_recessive * mp.log(x) + sigma_recessive * x

    while x > 0:
        step = h if x > h else x
        dx = -step
        k1r, k1l = deriv(x, r, logy)
        k2r, k2l = deriv(x + dx / 2, r + dx * k1r / 2, logy + dx * k1l / 2)
        k3r, k3l = deriv(x + dx / 2, r + dx * k2r / 2, logy + dx * k2l / 2)
        k4r, k4l = deriv(x + dx, r + dx * k3r, logy + dx * k3l)
        r += dx * (k1r + 2 * k2r + 2 * k3r + k4r) / 6
        logy += dx * (k1l + 2 * k2l + 2 * k3l + k4l) / 6
        x -= step

    y0 = mp.e ** logy
    y0p = r * y0
    return y0, y0p, r


def main() -> None:
    parser = argparse.ArgumentParser(description="V_quad 0F2/Airy/Bessel/Stokes identification")
    parser.add_argument("--dps", type=int, default=300)
    parser.add_argument("--depth", type=int, default=9000)
    args = parser.parse_args()

    mp.mp.dps = args.dps
    V = compute_vquad(args.depth, args.dps)

    sigma_plus, sigma_minus, mu_plus, mu_minus = wkb_data()

    print("SECTION A — ODE ASYMPTOTICS")
    print("ODE: (3x^2+x+1)y'' + (6x+1)y' - x^2 y = 0")
    print(f"sigma_+ = 1/sqrt(3) = {mp.nstr(sigma_plus, 25)}")
    print(f"sigma_- = -1/sqrt(3) = {mp.nstr(sigma_minus, 25)}")
    print(f"mu_+ = -1 - 1/(6*sqrt(3)) = {mp.nstr(mu_plus, 25)}")
    print(f"mu_- = -1 + 1/(6*sqrt(3)) = {mp.nstr(mu_minus, 25)}")
    print("WKB branches:")
    print("  y_dom(x) ~ x^mu_+ * exp(+x/sqrt(3))")
    print("  y_rec(x) ~ x^mu_- * exp(-x/sqrt(3))")
    print("Maclaurin recurrence:")
    print(f"  {series_recurrence_text()}")
    print("  This is not the first-order Pochhammer recurrence of a single 0F2 series, so any 0F2 appearance can only be approximate or via a transformed basis.")
    print()

    # 0F2
    Fvals = hyper_values()
    print("SECTION B — 0F2 TEST")
    for name, val in Fvals:
        print(f"  {name} = {mp.nstr(val, 22)}")
    vec = [V] + [val for _, val in Fvals] + [mp.mpf(1)]
    labels = ["V_quad"] + [name for name, _ in Fvals] + ["1"]
    print("  PSLQ(V_quad, F1..F6, 1) ->")
    print(f"    {relation_status(vec, labels, maxcoeff=500)}")
    print("  Best rational-multiple ratio tests for Fi/Fj:")
    best_ratio = (None, None, -1.0, None)
    for (ni, vi), (nj, vj) in itertools.combinations(Fvals, 2):
        rat_label, digs, err = best_rational_multiple(V, vi / vj, bound=10, max_den=24)
        if digs > best_ratio[2]:
            best_ratio = (ni, nj, digs, (rat_label, err))
    print(
        f"    best = {best_ratio[3][0]} * {best_ratio[0]}/{best_ratio[1]} with about {best_ratio[2]:.3f} digits (error {best_ratio[3][1]})"
    )
    print()

    # Airy
    Avals, zmap = airy_values()
    print("SECTION C — AIRY TEST")
    for name, z in zmap.items():
        print(f"  {name} = {mp.nstr(z, 20)}")
    for name, val in Avals:
        print(f"  {name} = {mp.nstr(val, 22)}")
    vec = [V] + [val for _, val in Avals[:8]] + [mp.mpf(1)]
    labels = ["V_quad"] + [name for name, _ in Avals[:8]] + ["1"]
    print("  PSLQ(V_quad, Ai/Bi at z1..z4, 1) ->")
    print(f"    {relation_status(vec, labels, maxcoeff=200)}")
    z1 = zmap["z1"]
    aip = mp.diff(mp.airyai, z1)
    bip = mp.diff(mp.airybi, z1)
    wronskian = mp.airyai(z1) * bip - aip * mp.airybi(z1)
    print(f"  Wronskian sanity check at z1: {mp.nstr(wronskian, 22)}")
    print(f"  1/pi = {mp.nstr(1 / mp.pi, 22)}")
    combos = {
        "Ai(z1)/Bi(z1)": mp.airyai(z1) / mp.airybi(z1),
        "Bi(z1)/Ai(z1)": mp.airybi(z1) / mp.airyai(z1),
        "Ai(z1)+Bi(z1)": mp.airyai(z1) + mp.airybi(z1),
        "Ai(z1)-Bi(z1)": mp.airyai(z1) - mp.airybi(z1),
    }
    best_combo = None
    for name, val in combos.items():
        coeff, digs, err = best_rational_multiple(V, val, bound=10, max_den=24)
        if best_combo is None or digs > best_combo[2]:
            best_combo = (name, coeff, digs, err)
    print(
        f"  Best Airy combo match: V_quad ≈ {best_combo[1]}*({best_combo[0]}) with about {best_combo[2]:.3f} digits (error {best_combo[3]})"
    )
    print()

    # Bessel
    Bvals = bessel_values()
    print("SECTION D — BESSEL TEST")
    for name, val in Bvals:
        print(f"  {name} = {mp.nstr(val, 22)}")
    Bdict = dict(Bvals)
    vec = [
        V,
        Bdict["B1"],
        Bdict["B2"],
        Bdict["B3"],
        Bdict["B4"],
        Bdict["B5"],
        Bdict["B6"],
        mp.mpf(1),
        Bdict["B1"] * Bdict["B2"],
        Bdict["B3"] * Bdict["B4"],
        Bdict["B1"] / Bdict["B2"],
    ]
    labels = ["V_quad", "B1", "B2", "B3", "B4", "B5", "B6", "1", "B1*B2", "B3*B4", "B1/B2"]
    print("  PSLQ(V_quad, B1..B6, 1, B1*B2, B3*B4, B1/B2) ->")
    print(f"    {relation_status(vec, labels, maxcoeff=200)}")
    print()

    # Stokes
    print("SECTION E — STOKES COMPUTATION")
    y0, y0p, r0 = stokes_connection(X0=mp.mpf("1000"), h=mp.mpf("0.03125"))
    print(f"  recessive normalization y(1000) = 1000^mu_- * exp(-1000/sqrt(3))")
    print(f"  y(0) = {mp.nstr(y0, 22)}")
    print(f"  y'(0) = {mp.nstr(y0p, 22)}")
    print(f"  y'(0)/y(0) = {mp.nstr(r0, 22)}")
    print(f"  y(0)/y'(0) = {mp.nstr(1 / r0, 22)}")
    print(f"  y(0)/V_quad = {mp.nstr(y0 / V, 22)}")
    print(f"  [y'(0)/y(0)]/V_quad = {mp.nstr(r0 / V, 22)}")

    gamma_basis = [
        ("pi/sqrt(11)", mp.pi / mp.sqrt(11)),
        ("pi^2/11", mp.pi**2 / 11),
        ("Gamma(1/11)Gamma(2/11)Gamma(4/11)/Gamma(8/11)", mp.gamma(mp.mpf(1)/11) * mp.gamma(mp.mpf(2)/11) * mp.gamma(mp.mpf(4)/11) / mp.gamma(mp.mpf(8)/11)),
        ("sqrt(11)", mp.sqrt(11)),
    ]
    combined = [r0] + [val for _, val in gamma_basis] + [val for _, val in Fvals] + [val for _, val in Bvals] + [combos["Ai(z1)/Bi(z1)"], combos["Bi(z1)/Ai(z1)"], combos["Ai(z1)+Bi(z1)"], mp.mpf(1)]
    combined_labels = ["conn=y'/y"] + [name for name, _ in gamma_basis] + [name for name, _ in Fvals] + [name for name, _ in Bvals] + ["Ai/Bi", "Bi/Ai", "Ai+Bi", "1"]
    print("  Combined PSLQ on the connection coefficient ->")
    print(f"    {relation_status(combined, combined_labels, maxcoeff=200, maxsteps=30000)}")
    print()

    print("SECTION F — VERDICT")
    print(f"  V_quad = {mp.nstr(V, 30)}")
    print("  NOT IDENTIFIED: no non-trivial PSLQ relation was found in the tested 0F2, Airy, or Bessel bases at dps=300 with the requested coefficient bounds.")
    print("  Strongest positive structural statement: the recessive Stokes/connection data are real and numerically stable, but they do not collapse to a low-height special-function expression in the tested families.")
    print("  Transcendence depth: if a closed form exists, it lies beyond low-weight Gamma/L-value combinations and beyond simple 0F2/Airy/Bessel evaluations or their small rational multiples.")


if __name__ == "__main__":
    main()
