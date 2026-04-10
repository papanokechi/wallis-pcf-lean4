#!/usr/bin/env python3
"""Three-basis confluent-Heun/Stokes search for V_quad.

We do not have a native `HeunG`/`HeunC` implementation in the workspace, so this
script uses the verified confluent-Heun reduction of the V_quad ODE and builds
real-valued proxy invariants from the local analytic branches at z=0 and z=1.

Search space
------------
For the transformed equation

    u'' + (alpha + 1/z + 1/(z-1)) u' + (mu/z + nu/(z-1)) u = 0,

we numerically evaluate the regular local branches at the image z0 of x=0 and
combine those values with Stokes / connection invariants and the discriminant-11
CM basis. We then test low-height PSLQ relations of the form

    a*V_quad + b*H + c*S + d*C + e = 0,

where
  - H is a confluent-Heun proxy value,
  - S is a Stokes / connection value,
  - C is a CM / discriminant-11 period candidate.

Outputs
-------
- `vquad_three_basis_confluent_heun_report.json`
- `vquad_three_basis_confluent_heun_report.md`
"""

from __future__ import annotations

import argparse
import json
import math
import time
from fractions import Fraction
from pathlib import Path

import mpmath as mp

from vquad_stokes_0f2_identification import compute_vquad, stokes_connection

REPORT_JSON = Path("vquad_three_basis_confluent_heun_report.json")
REPORT_MD = Path("vquad_three_basis_confluent_heun_report.md")
CONNECTION_JSON = Path("vquad_connection_matrix_report.json")


def small_rationals(max_num: int = 3, max_den: int = 2) -> list[mp.mpf]:
    vals: set[tuple[int, int]] = set()
    for q in range(1, max_den + 1):
        for p in range(-max_num * q, max_num * q + 1):
            frac = Fraction(p, q)
            vals.add((frac.numerator, frac.denominator))
    return [mp.mpf(p) / q for p, q in sorted(vals)]


def relation_status(vec: list[mp.mpf], labels: list[str], maxcoeff: int, tol_digits: int) -> dict:
    try:
        rel = mp.pslq(vec, tol=mp.mpf(10) ** (-tol_digits), maxcoeff=maxcoeff, maxsteps=40000)
    except Exception as exc:
        return {"status": "error", "relation": None, "message": str(exc)}
    if rel is None:
        return {"status": "none", "relation": None}
    nz = [(int(c), lab) for c, lab in zip(rel, labels) if c != 0]
    residual = abs(mp.fsum(mp.mpf(c) * v for c, v in zip(rel, vec)))
    touches_v = any(lab == "V_quad" for _, lab in nz)
    return {
        "status": "relation" if touches_v else "trivial",
        "relation": nz,
        "residual": mp.nstr(residual, 12),
    }


def digits_of_agreement(a, b) -> float:
    err = abs(a - b)
    if err == 0:
        return math.inf
    scale = max(1.0, abs(complex(b)))
    return max(0.0, -math.log10(float(err / scale)))


def heun_params():
    s11 = mp.sqrt(11)
    r_plus = (-1 + 1j * s11) / 6
    r_minus = (-1 - 1j * s11) / 6
    delta = r_minus - r_plus
    z0 = (-r_plus) / delta
    A = (-5 - 1j * s11) / 54
    B = (5 - 1j * s11) / 54
    lam = 1j * s11 / (3 * mp.sqrt(3))
    alpha = 2 * lam
    mu = A + lam
    nu = B + lam
    return z0, alpha, mu, nu


def series_coeffs_zero(alpha, mu, nu, terms: int) -> list[mp.mpc]:
    """Regular local power series at z=0 for

        u'' + (alpha + 1/z + 1/(z-1)) u' + (mu/z + nu/(z-1)) u = 0.

    With u(z)=sum c_n z^n and c_0=1, the recurrence is

        (n+1)^2 c_{n+1}
          = [n(n+1-alpha)-mu] c_n + [alpha(n-1)+mu+nu] c_{n-1}.
    """
    coeffs = [mp.mpc(0) for _ in range(terms + 1)]
    coeffs[0] = mp.mpc(1)
    if terms >= 1:
        coeffs[1] = -mu
    for n in range(1, terms):
        coeffs[n + 1] = (
            (n * (n + 1 - alpha) - mu) * coeffs[n]
            + (alpha * (n - 1) + mu + nu) * coeffs[n - 1]
        ) / (n + 1) ** 2
    return coeffs


def eval_series_and_derivative(coeffs: list[mp.mpc], z: mp.mpc) -> tuple[mp.mpc, mp.mpc]:
    value = mp.fsum(coeffs[n] * z ** n for n in range(len(coeffs)))
    deriv = mp.fsum(n * coeffs[n] * z ** (n - 1) for n in range(1, len(coeffs)))
    return value, deriv


def confluent_heun_basis() -> tuple[list[tuple[str, mp.mpf]], dict]:
    z0, alpha, mu, nu = heun_params()
    w0 = 1 - z0

    # Use a short/long series pair as a stability diagnostic.
    terms_hi = max(180, 2 * mp.mp.dps)
    terms_lo = max(100, terms_hi // 2)

    # z=0 regular branch.
    c_lo = series_coeffs_zero(alpha, mu, nu, terms_lo)
    c_hi = series_coeffs_zero(alpha, mu, nu, terms_hi)
    u0_lo, up0_lo = eval_series_and_derivative(c_lo, z0)
    u0, up0 = eval_series_and_derivative(c_hi, z0)

    # z=1 regular branch via w = 1-z. The transformed equation has
    # alpha -> -alpha, mu -> -nu, nu -> -mu in the same local recurrence form.
    c1_lo = series_coeffs_zero(-alpha, -nu, -mu, terms_lo)
    c1_hi = series_coeffs_zero(-alpha, -nu, -mu, terms_hi)
    v1_lo, vp1_lo = eval_series_and_derivative(c1_lo, w0)
    v1, vp1 = eval_series_and_derivative(c1_hi, w0)
    u1_lo, up1_lo = v1_lo, -vp1_lo
    u1, up1 = v1, -vp1

    rho0_lo = up0_lo / u0_lo
    rho1_lo = up1_lo / u1_lo
    rho0 = up0 / u0
    rho1 = up1 / u1
    ratio = u0 / u1
    wr = u0 * up1 - up0 * u1

    basis = [
        ("|H0(z0)|", abs(u0)),
        ("|H1(z0)|", abs(u1)),
        ("Re(H0'/H0)", mp.re(rho0)),
        ("Im(H0'/H0)", mp.im(rho0)),
        ("Re(H1'/H1)", mp.re(rho1)),
        ("Im(H1'/H1)", mp.im(rho1)),
        ("|H0/H1|", abs(ratio)),
        ("arg(H0/H1)/pi", mp.arg(ratio) / mp.pi),
        ("|Wr(H0,H1)|", abs(wr)),
    ]

    meta = {
        "z0": mp.nstr(z0, 25),
        "alpha": mp.nstr(alpha, 25),
        "mu": mp.nstr(mu, 25),
        "nu": mp.nstr(nu, 25),
        "series_terms_lo": terms_lo,
        "series_terms_hi": terms_hi,
        "branch0_stability_digits": min(
            digits_of_agreement(u0_lo, u0),
            digits_of_agreement(rho0_lo, rho0),
        ),
        "branch1_stability_digits": min(
            digits_of_agreement(u1_lo, u1),
            digits_of_agreement(rho1_lo, rho1),
        ),
        "H0": mp.nstr(u0, 20),
        "H1": mp.nstr(u1, 20),
        "rho0": mp.nstr(rho0, 20),
        "rho1": mp.nstr(rho1, 20),
    }
    return basis, meta


def stokes_basis() -> list[tuple[str, mp.mpf]]:
    y0, y0p, r0 = stokes_connection(X0=mp.mpf("1000"), h=mp.mpf("0.03125"))
    if CONNECTION_JSON.exists():
        payload = json.loads(CONNECTION_JSON.read_text(encoding="utf-8"))
        cm = payload["connection_matrix"]
        m11 = mp.mpf(cm["M11"])
        m12 = mp.mpf(cm["M12"])
        m21 = mp.mpf(cm["M21"])
        m22 = mp.mpf(cm["M22"])
    else:
        m11 = m12 = m21 = m22 = mp.nan
    return [
        ("y0", y0),
        ("y0p", y0p),
        ("r0=y'/y", r0),
        ("1/r0", 1 / r0),
        ("M11", m11),
        ("M21", m21),
        ("M11/M21", m11 / m21),
        ("M12/M22", m12 / m22),
    ]


def cm_basis() -> list[tuple[str, mp.mpf]]:
    s11 = mp.sqrt(11)
    tau_cm = (1 + 1j * s11) / 2
    q = mp.e ** (2 * mp.pi * 1j * tau_cm)
    prod = mp.mpf("1")
    for n in range(1, 200):
        prod *= 1 - q ** n
    eta_tau = q ** (mp.mpf("1") / 24) * prod
    gamma_prod = (
        mp.gamma(mp.mpf(1) / 11)
        * mp.gamma(mp.mpf(2) / 11)
        * mp.gamma(mp.mpf(4) / 11)
        / mp.gamma(mp.mpf(8) / 11)
    )
    return [
        ("pi/sqrt(11)", mp.pi / s11),
        ("pi^2/11", mp.pi ** 2 / 11),
        ("Gamma-prod", gamma_prod),
        ("sqrt(11)", s11),
        ("log|eta|", mp.log(abs(eta_tau))),
    ]


def best_affine_three_basis(target: mp.mpf, x: mp.mpf, y: mp.mpf, z: mp.mpf) -> dict:
    rats = small_rationals(3, 2)
    tf = float(target)
    xf = float(x)
    yf = float(y)
    zf = float(z)
    best = {"digits": -1.0, "a": None, "b": None, "c": None, "d": None, "error": None}
    for a in rats:
        af = float(a)
        for b in rats:
            bf = float(b)
            for c in rats:
                cf = float(c)
                for d in range(-2, 3):
                    err = abs(tf - af * xf - bf * yf - cf * zf - d)
                    if err == 0:
                        digs = math.inf
                    else:
                        digs = -math.log10(err)
                    if digs > best["digits"]:
                        best = {
                            "digits": digs,
                            "a": mp.nstr(a, 12),
                            "b": mp.nstr(b, 12),
                            "c": mp.nstr(c, 12),
                            "d": d,
                            "error": f"{err:.6e}",
                        }
    return best


def write_markdown(summary: dict) -> None:
    lines = [
        "# Three-basis confluent-Heun/Stokes search for V_quad",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Precision: {summary['dps']} dps",
        f"- V_quad: `{summary['vquad']}`",
        f"- Triple count: `{summary['triple_count']}`",
        "",
        "## Confluent-Heun proxy diagnostics",
        "",
        f"- `z0 = {summary['heun_meta']['z0']}`",
        f"- Branch-0 stability: `{summary['heun_meta']['branch0_stability_digits']:.3f}` digits",
        f"- Branch-1 stability: `{summary['heun_meta']['branch1_stability_digits']:.3f}` digits",
        "",
        "## Verified PSLQ hits",
        "",
    ]
    if summary["hits"]:
        for hit in summary["hits"]:
            lines.append(
                f"- `{hit['heun_label']}`, `{hit['stokes_label']}`, `{hit['cm_label']}` -> `{hit['relation']}` (residual `{hit['residual']}`)"
            )
    else:
        lines.append("- No non-trivial PSLQ relation involving `V_quad` was found in the tested three-basis space.")
    lines.append("")
    lines.append("## Strongest low-height near misses")
    lines.append("")
    lines.append("| rank | Heun proxy | Stokes basis | CM basis | digits | affine fit | error |")
    lines.append("|---:|---|---|---|---:|---|---|")
    for idx, row in enumerate(summary["top_near_misses"], start=1):
        fit = f"{row['a']}*H + {row['b']}*S + {row['c']}*C + {row['d']}"
        lines.append(
            f"| {idx} | `{row['heun_label']}` | `{row['stokes_label']}` | `{row['cm_label']}` | {row['digits']:.6f} | `{fit}` | `{row['error']}` |"
        )
    lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Three-basis confluent-Heun/Stokes search for V_quad")
    parser.add_argument("--dps", type=int, default=80)
    parser.add_argument("--depth", type=int, default=9000)
    parser.add_argument("--maxcoeff", type=int, default=2000)
    args = parser.parse_args()

    mp.mp.dps = args.dps
    t0 = time.time()
    V = compute_vquad(args.depth, args.dps)
    heun_basis_vals, heun_meta = confluent_heun_basis()
    stokes_vals = stokes_basis()
    cm_vals = cm_basis()

    print("=" * 78)
    print("Three-basis confluent-Heun/Stokes search for V_quad")
    print("=" * 78)
    print(f"V_quad = {mp.nstr(V, 40)}")
    print(f"Heun proxies = {len(heun_basis_vals)} | Stokes basis = {len(stokes_vals)} | CM basis = {len(cm_vals)}")
    print(f"z0 = {heun_meta['z0']}")
    print(f"Branch stability digits: H0 ~ {heun_meta['branch0_stability_digits']:.3f}, H1 ~ {heun_meta['branch1_stability_digits']:.3f}")
    print()

    for label, val in heun_basis_vals:
        print(f"[Heun]   {label} = {mp.nstr(val, 25)}")
    print()
    for label, val in stokes_vals:
        print(f"[Stokes] {label} = {mp.nstr(val, 25)}")
    print()
    for label, val in cm_vals:
        print(f"[CM]     {label} = {mp.nstr(val, 25)}")
    print()

    hits = []
    near = []
    for h_label, h_val in heun_basis_vals:
        for s_label, s_val in stokes_vals:
            for c_label, c_val in cm_vals:
                labels = ["V_quad", h_label, s_label, c_label, "1"]
                status = relation_status([V, h_val, s_val, c_val, mp.mpf(1)], labels, args.maxcoeff, tol_digits=min(50, args.dps // 2))
                if status["status"] == "relation":
                    hits.append({
                        "heun_label": h_label,
                        "stokes_label": s_label,
                        "cm_label": c_label,
                        "relation": status["relation"],
                        "residual": status.get("residual", "0"),
                    })
                    print(f"HIT: {h_label} + {s_label} + {c_label} -> {status['relation']} residual {status.get('residual', '0')}")
                else:
                    best = best_affine_three_basis(V, h_val, s_val, c_val)
                    near.append({
                        "heun_label": h_label,
                        "stokes_label": s_label,
                        "cm_label": c_label,
                        **best,
                    })

    near.sort(key=lambda row: (-row["digits"], row["heun_label"], row["stokes_label"], row["cm_label"]))
    top = near[:12]

    print("Top near misses:")
    for row in top:
        print(
            f"  {row['digits']:.6f}d :: {row['heun_label']} with {row['stokes_label']} and {row['cm_label']} :: "
            f"V ~= {row['a']}*H + {row['b']}*S + {row['c']}*C + {row['d']} (err {row['error']})"
        )

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dps": args.dps,
        "depth": args.depth,
        "maxcoeff": args.maxcoeff,
        "vquad": mp.nstr(V, 50),
        "triple_count": len(heun_basis_vals) * len(stokes_vals) * len(cm_vals),
        "heun_meta": heun_meta,
        "hits": hits,
        "top_near_misses": top,
        "wall_seconds": round(time.time() - t0, 3),
    }
    REPORT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary)

    print()
    if hits:
        print(f"Found {len(hits)} non-trivial PSLQ relation(s).")
    else:
        print("No non-trivial three-basis PSLQ relation found.")
    print(f"Wall time: {summary['wall_seconds']}s")
    print(f"JSON -> {REPORT_JSON}")
    print(f"MD   -> {REPORT_MD}")


if __name__ == "__main__":
    main()
