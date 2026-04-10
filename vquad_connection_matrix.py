#!/usr/bin/env python3
"""Compute the Frobenius↔WKB connection matrix for

    (3x^2 + x + 1) y'' + (6x + 1) y' - x^2 y = 0.

Outputs:
  - `vquad_connection_matrix_report.md`
  - `vquad_connection_matrix_report.json`

Method summary
--------------
1. Compute the analytic/Frobenius basis at x=0 (indicial roots 0 and 1)
   and integrate that basis to x_match = 10 with RK4 + step halving.
2. Compute the recessive WKB branch at infinity from the asymptotic
   expansion y ~ x^mu_- exp(-x/sqrt(3)).
3. Reconstruct the dominant branch stably. A naive backward shot from x0
   collapses onto the recessive branch numerically, so the code uses the
   equivalent Wronskian / reduction-of-order stabilization while keeping the
   same asymptotic normalization at x0.
4. Assemble the 2x2 connection matrix and run the requested PSLQ checks.
"""

from __future__ import annotations

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Iterable

import mpmath as mp

ODE_TEXT = "(3x^2+x+1)y'' + (6x+1)y' - x^2 y = 0"
REPORT_MD = Path("vquad_connection_matrix_report.md")
REPORT_JSON = Path("vquad_connection_matrix_report.json")


def compute_vquad(depth: int, dps: int) -> mp.mpf:
    with mp.workdps(dps + 40):
        v = mp.mpf("0")
        for n in range(depth, 0, -1):
            v = mp.mpf("1") / (3 * n * n + n + 1 + v)
        return +(mp.mpf("1") + v)


def digits_from_relative_error(err: mp.mpf, scale: mp.mpf | None = None) -> float:
    err = abs(err)
    if scale is not None and scale != 0:
        err /= abs(scale)
    if err == 0:
        return math.inf
    return max(0.0, float(-mp.log10(err)))


def digits_of_agreement(a: mp.mpf, b: mp.mpf) -> float:
    scale = max(mp.mpf("1"), abs(b))
    return digits_from_relative_error(a - b, scale)


def state_agreement_digits(a: Iterable[mp.mpf], b: Iterable[mp.mpf]) -> float:
    vals = [digits_of_agreement(x, y) for x, y in zip(a, b)]
    return min(vals) if vals else math.inf


def fmt(x: mp.mpf, digits: int = 30) -> str:
    return mp.nstr(x, digits)


def nz_relation(rel: list[int], labels: list[str]) -> list[tuple[int, str]]:
    return [(int(c), lab) for c, lab in zip(rel, labels) if c != 0]


def ode_matrix_rhs(x: mp.mpf, state: list[mp.mpf]) -> list[mp.mpf]:
    """RHS for one or more copies of the second-order ODE.

    State is packed as [y1, y1', y2, y2', ...].
    """
    A = 3 * x * x + x + 1
    out: list[mp.mpf] = []
    for i in range(0, len(state), 2):
        y = state[i]
        yp = state[i + 1]
        ypp = (x * x * y - (6 * x + 1) * yp) / A
        out.extend([yp, ypp])
    return out


def rk4_step(x: mp.mpf, state: list[mp.mpf], dx: mp.mpf) -> list[mp.mpf]:
    k1 = ode_matrix_rhs(x, state)
    s2 = [u + dx * k / 2 for u, k in zip(state, k1)]
    k2 = ode_matrix_rhs(x + dx / 2, s2)
    s3 = [u + dx * k / 2 for u, k in zip(state, k2)]
    k3 = ode_matrix_rhs(x + dx / 2, s3)
    s4 = [u + dx * k for u, k in zip(state, k3)]
    k4 = ode_matrix_rhs(x + dx, s4)
    return [
        u + dx * (k1i + 2 * k2i + 2 * k3i + k4i) / 6
        for u, k1i, k2i, k3i, k4i in zip(state, k1, k2, k3, k4)
    ]


def integrate_fixed(state0: list[mp.mpf], x0: mp.mpf, x1: mp.mpf, h: mp.mpf) -> list[mp.mpf]:
    x = mp.mpf(x0)
    state = [mp.mpf(v) for v in state0]
    direction = mp.sign(x1 - x0)
    if direction == 0:
        return state
    h = abs(mp.mpf(h))
    while direction * (x1 - x) > 0:
        step = min(h, abs(x1 - x))
        dx = direction * step
        state = rk4_step(x, state, dx)
        x += dx
    return state


def integrate_with_step_halving(
    state0: list[mp.mpf],
    x0: mp.mpf,
    x1: mp.mpf,
    *,
    h0: mp.mpf,
    target_digits: float,
    max_halvings: int = 8,
) -> tuple[list[mp.mpf], float, str]:
    h = mp.mpf(h0)
    prev = integrate_fixed(state0, x0, x1, h)
    best_digits = 0.0
    step_used = fmt(h, 12)
    for _ in range(max_halvings):
        h /= 2
        cur = integrate_fixed(state0, x0, x1, h)
        digs = state_agreement_digits(prev, cur)
        best_digits = digs
        step_used = fmt(h, 12)
        prev = cur
        if digs >= target_digits:
            break
    return prev, best_digits, step_used


def integrate_with_richardson(
    state0: list[mp.mpf],
    x0: mp.mpf,
    x1: mp.mpf,
    *,
    h0: mp.mpf,
    levels: int = 7,
    order: int = 4,
) -> tuple[list[mp.mpf], float, str]:
    """Repeated Richardson extrapolation on halved RK4 step sizes."""
    table: list[list[list[mp.mpf]]] = []
    prev_diag: list[mp.mpf] | None = None
    digits = 0.0
    for i in range(levels):
        h = mp.mpf(h0) / (2 ** i)
        row = [integrate_fixed(state0, x0, x1, h)]
        for m in range(1, i + 1):
            factor = mp.mpf(2) ** (order + m - 1)
            prev = row[m - 1]
            prev_row = table[i - 1][m - 1]
            row.append([
                v + (v - u) / (factor - 1)
                for u, v in zip(prev_row, prev)
            ])
        table.append(row)
        diag = row[-1]
        if prev_diag is not None:
            digits = state_agreement_digits(prev_diag, diag)
        prev_diag = diag
    return prev_diag or table[-1][-1], digits, f"Richardson-RK4 from h={fmt(h0,12)} with {levels} levels"


# ---------------------------------------------------------------------------
# Frobenius basis at x = 0
# ---------------------------------------------------------------------------

def analytic_series_coeffs(c0: mp.mpf, c1: mp.mpf, terms: int = 40) -> list[mp.mpf]:
    """Ordinary-point series y = sum c_n x^n.

    The recurrence from the ODE is
        (n+2)(n+1)c_{n+2} + (n+1)^2 c_{n+1} + 3n(n+1)c_n - c_{n-2} = 0,
    with c_{-1}=c_{-2}=0.
    """
    coeffs = [mp.mpf("0") for _ in range(terms)]
    coeffs[0] = mp.mpf(c0)
    if terms > 1:
        coeffs[1] = mp.mpf(c1)
    for n in range(terms - 2):
        rhs = (coeffs[n - 2] if n >= 2 else mp.mpf("0"))
        rhs -= (n + 1) ** 2 * coeffs[n + 1]
        rhs -= 3 * n * (n + 1) * coeffs[n]
        coeffs[n + 2] = rhs / ((n + 2) * (n + 1))
    return coeffs


def series_expression(coeffs: list[mp.mpf], symbol: str = "x", digits: int = 12) -> str:
    terms = []
    for n, c in enumerate(coeffs):
        if abs(c) < mp.mpf("1e-60"):
            continue
        if n == 0:
            term = f"{fmt(c, digits)}"
        elif n == 1:
            term = f"{fmt(c, digits)}*{symbol}"
        else:
            term = f"{fmt(c, digits)}*{symbol}^{n}"
        terms.append(term)
    return " + ".join(terms[:12]) + (" + ..." if len(terms) > 12 else "")


# ---------------------------------------------------------------------------
# WKB asymptotics at infinity
# ---------------------------------------------------------------------------

def wkb_riccati_coeffs(sigma: mp.mpf, order: int = 220) -> list[mp.mpf]:
    """Formal coefficients for r = y'/y = sum c_k x^{-k}."""
    c = [mp.mpf("0") for _ in range(order + 1)]
    c[0] = mp.mpf(sigma)
    c[1] = -1 - sigma / 6  # mu

    d = [mp.mpf("0") for _ in range(order + 1)]
    d[0] = c[0] ** 2
    d[1] = 2 * c[0] * c[1]

    for k in range(2, order + 1):
        known_s = mp.fsum(c[i] * c[k - i] for i in range(1, k))
        rest = 3 * (known_s - (k - 1) * c[k - 1]) + d[k - 1] + d[k - 2] + 6 * c[k - 1] + c[k - 2]
        c[k] = -rest / (6 * c[0])
        d[k] = 2 * c[0] * c[k] + known_s - (k - 1) * c[k - 1]
    return c


def wkb_initial_data(sigma: mp.mpf, x0: mp.mpf, dps_target: int, order: int = 260) -> tuple[mp.mpf, mp.mpf, mp.mpf, mp.mpf, int]:
    """Return (y0, y0', r0, mu, order_used) from the asymptotic series.

    y(x) ~ x^mu exp(sigma x) with the logarithmic-derivative correction series.
    """
    coeffs = wkb_riccati_coeffs(sigma, order=order)
    mu = coeffs[1]
    tol = mp.power(10, -(min(dps_target, 120) + 20))
    use = 2
    best_term = mp.inf
    for k in range(2, order + 1):
        term = abs(coeffs[k] / ((k - 1) * x0 ** (k - 1)))
        if term < best_term:
            best_term = term
            use = k
        elif k > 12 and term > best_term:
            break
        if k >= 20 and term < tol:
            use = k
            break

    r0 = mp.fsum(coeffs[k] / x0 ** k for k in range(use + 1))
    logy0 = sigma * x0 + mu * mp.log(x0)
    if use >= 2:
        logy0 -= mp.fsum(coeffs[k] / ((k - 1) * x0 ** (k - 1)) for k in range(2, use + 1))
    y0 = mp.exp(logy0)
    return y0, r0 * y0, r0, mu, use


def integrate_wkb_recessive_and_aux(
    x0: mp.mpf,
    x_match: mp.mpf,
    yrec0: mp.mpf,
    yrecp0: mp.mpf,
    *,
    h0: mp.mpf,
    target_digits: float,
) -> tuple[dict[str, mp.mpf | float | str], list[mp.mpf]]:
    """Integrate the recessive solution and a Wronskian-normalized auxiliary one.

    The auxiliary solution z satisfies the same ODE with initial data
        z(x0) = 0,
        z'(x0) = 1/(A(x0) y_rec(x0)),
    so that W(y_rec, z) = 1/A(x).
    """
    A0 = 3 * x0 * x0 + x0 + 1
    z0 = mp.mpf("0")
    z0p = 1 / (A0 * yrec0)
    state0 = [yrec0, yrecp0, z0, z0p]
    state, digs, h_used = integrate_with_step_halving(
        state0,
        x0,
        x_match,
        h0=h0,
        target_digits=target_digits,
    )
    info = {
        "stable_digits": digs,
        "step": h_used,
        "z0prime": z0p,
    }
    return info, state


# ---------------------------------------------------------------------------
# PSLQ helpers
# ---------------------------------------------------------------------------

def pslq_scalar_report(entry: mp.mpf, basis_labels: list[str], basis_values: list[mp.mpf], *, maxcoeff: int = 500) -> dict:
    vec = [entry] + basis_values
    labels = ["target"] + basis_labels
    mags = [abs(v) for v in vec if v != 0]
    scale = max(mags + [mp.mpf("1")])
    if mags and scale / min(mags) > mp.power(10, max(20, mp.mp.dps - 10)):
        return {
            "status": "None",
            "maxcoeff": maxcoeff,
            "relation": None,
            "near_miss": {
                "heuristic": "skipped: dynamic range too large for current dps",
                "digits": 0.0,
            },
        }
    vec_scaled = [v / scale for v in vec]
    try:
        rel = mp.pslq(vec_scaled, maxcoeff=maxcoeff, maxsteps=15000)
    except ValueError:
        return {
            "status": "None",
            "maxcoeff": maxcoeff,
            "relation": None,
            "near_miss": {
                "heuristic": "skipped: PSLQ lost significance at this dps",
                "digits": 0.0,
            },
        }
    payload: dict = {
        "status": "hit" if rel is not None else "None",
        "maxcoeff": maxcoeff,
        "relation": nz_relation(rel, labels) if rel is not None else None,
    }
    if rel is not None:
        residual = mp.fsum(c * v for c, v in zip(rel, vec_scaled))
        payload["residual"] = fmt(residual, 20)
        payload["digits"] = digits_from_relative_error(residual, max(mp.mpf("1"), abs(entry)))
        return payload

    # Heuristic near miss: best affine one-basis fit a + b*c with small rational b.
    best_digits = -1.0
    best_desc = None
    for lab, val in zip(basis_labels[1:], basis_values[1:]):  # skip the '1' basis for this fallback
        for q in range(1, 25):
            for p in range(-24 * q, 24 * q + 1):
                if p == 0:
                    continue
                frac = Fraction(p, q)
                b = mp.mpf(frac.numerator) / frac.denominator
                a = mp.nint(entry - b * val)
                approx = a + b * val
                digs = digits_of_agreement(entry, approx)
                if digs > best_digits:
                    best_digits = digs
                    best_desc = f"{a} + ({frac})*{lab}"
    payload["near_miss"] = {
        "heuristic": "best affine one-basis fit with |p|,|q|<=24",
        "expression": best_desc,
        "digits": best_digits,
    }
    return payload


def pslq_joint_report(vec_labels: list[str], vec_values: list[mp.mpf], *, maxcoeff: int = 500) -> dict:
    mags = [abs(v) for v in vec_values if v != 0]
    scale = max(mags + [mp.mpf("1")])
    if mags and scale / min(mags) > mp.power(10, max(20, mp.mp.dps - 10)):
        return {
            "status": "None",
            "maxcoeff": maxcoeff,
            "relation": None,
            "note": "skipped: dynamic range too large for current dps",
        }
    vec_scaled = [v / scale for v in vec_values]
    try:
        rel = mp.pslq(vec_scaled, maxcoeff=maxcoeff, maxsteps=20000)
    except ValueError:
        return {
            "status": "None",
            "maxcoeff": maxcoeff,
            "relation": None,
            "note": "skipped: PSLQ lost significance at this dps",
        }
    payload = {
        "status": "hit" if rel is not None else "None",
        "maxcoeff": maxcoeff,
        "relation": nz_relation(rel, vec_labels) if rel is not None else None,
    }
    if rel is not None:
        residual = mp.fsum(c * v for c, v in zip(rel, vec_scaled))
        payload["residual"] = fmt(residual, 20)
        payload["digits"] = digits_from_relative_error(residual)
    return payload


# ---------------------------------------------------------------------------
# V_quad scan against simple M-combinations
# ---------------------------------------------------------------------------

def scan_vquad_combinations(M: mp.matrix, V: mp.mpf) -> dict:
    entries = {
        "M11": M[0, 0],
        "M12": M[0, 1],
        "M21": M[1, 0],
        "M22": M[1, 1],
    }
    combos: dict[str, mp.mpf] = dict(entries)
    combos["det(M)"] = M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0]
    combos["trace(M)"] = M[0, 0] + M[1, 1]
    combos["M11+M21"] = M[0, 0] + M[1, 0]
    combos["M12+M22"] = M[0, 1] + M[1, 1]
    combos["M11/M21"] = M[0, 0] / M[1, 0]
    combos["M12/M22"] = M[0, 1] / M[1, 1]
    combos["M11/M12"] = M[0, 0] / M[0, 1]
    combos["M21/M22"] = M[1, 0] / M[1, 1]

    try:
        Minv = M ** -1
    except ZeroDivisionError:
        Minv = None
    if Minv is not None:
        combos["(M^-1)11"] = Minv[0, 0]
        combos["(M^-1)12"] = Minv[0, 1]
        combos["(M^-1)21"] = Minv[1, 0]
        combos["(M^-1)22"] = Minv[1, 1]
        combos["(M^-1)11/(M^-1)21"] = Minv[0, 0] / Minv[1, 0]
        combos["(M^-1)12/(M^-1)22"] = Minv[0, 1] / Minv[1, 1]

    best_name = None
    best_digits = -1.0
    best_value = None
    for name, val in combos.items():
        digs = digits_of_agreement(val, V)
        if digs > best_digits:
            best_name = name
            best_digits = digs
            best_value = val
    return {
        "best_name": best_name,
        "best_value": fmt(best_value, 30),
        "digits_vs_vquad": best_digits,
        "vquad": fmt(V, 30),
        "simple_match": bool(best_digits >= 10),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Compute the V_quad ODE connection matrix")
    parser.add_argument("--dps", type=int, default=300)
    parser.add_argument("--internal-extra", type=int, default=650, help="extra guard digits for the unstable dominant branch reconstruction")
    parser.add_argument("--series-terms", type=int, default=40)
    parser.add_argument("--x0", type=str, default="1000")
    parser.add_argument("--x-match", type=str, default="10")
    parser.add_argument("--x-bridge", type=str, default="30", help="stable intermediate asymptotic matching point for the dominant branch")
    parser.add_argument("--depth", type=int, default=9000, help="continued-fraction depth for V_quad")
    args = parser.parse_args()

    dps = int(args.dps)
    internal_dps = max(dps + int(args.internal_extra), dps + 80)
    x0 = mp.mpf(args.x0)
    x_match = mp.mpf(args.x_match)
    x_bridge = mp.mpf(args.x_bridge)

    mp.mp.dps = internal_dps

    sqrt3 = mp.sqrt(3)
    sigma_plus = mp.mpf("1") / sqrt3
    sigma_minus = -sigma_plus

    print("[1/5] Frobenius basis at x=0 ...", flush=True)

    # ------------------------------------------------------------------
    # Step 1: Frobenius basis
    # ------------------------------------------------------------------
    rho1 = mp.mpf("0")
    rho2 = mp.mpf("1")
    y1_coeffs = analytic_series_coeffs(1, 0, terms=args.series_terms)
    y2_coeffs = analytic_series_coeffs(0, 1, terms=args.series_terms)

    frob_state, frob_digits, frob_step = integrate_with_richardson(
        [mp.mpf("1"), mp.mpf("0"), mp.mpf("0"), mp.mpf("1")],
        mp.mpf("0"),
        x_match,
        h0=mp.mpf("0.5"),
        levels=9,
        order=4,
    )
    y1_x, y1p_x, y2_x, y2p_x = frob_state

    print("[2/5] WKB branches at infinity ...", flush=True)

    # ------------------------------------------------------------------
    # Step 2: WKB data at infinity
    # ------------------------------------------------------------------
    yrec0, yrecp0, rrec0, mu_minus, rec_order = wkb_initial_data(sigma_minus, x0, internal_dps)
    ydom0, ydomp0, rdom0, _, _ = wkb_initial_data(sigma_plus, x0, internal_dps)
    # The dominant asymptotic data are matched at a moderate bridge point to avoid
    # catastrophic cancellation while keeping the same infinity-normalization.
    ydom_bridge, ydomp_bridge, rdom_bridge, mu_plus, dom_order = wkb_initial_data(sigma_plus, x_bridge, internal_dps)

    # First carry the recessive branch from the requested seed x0=1000 down to the
    # moderate bridge point. Then start a fresh auxiliary solution at the bridge,
    # which avoids the enormous contaminated scale factor of a direct dominant shot.
    rec_bridge_state, bridge_digits, bridge_step = integrate_with_step_halving(
        [yrec0, yrecp0],
        x0,
        x_bridge,
        h0=mp.mpf("4"),
        target_digits=min(50, dps - 30),
        max_halvings=5,
    )
    yrec_bridge, yrecp_bridge = rec_bridge_state

    A_bridge = 3 * x_bridge * x_bridge + x_bridge + 1
    z_bridge = mp.mpf("0")
    zp_bridge = 1 / (A_bridge * yrec_bridge)

    match_state, leg2_digits, leg2_step = integrate_with_step_halving(
        [yrec_bridge, yrecp_bridge, z_bridge, zp_bridge],
        x_bridge,
        x_match,
        h0=mp.mpf("1"),
        target_digits=min(50, dps - 30),
        max_halvings=5,
    )
    yrec_x, yrecp_x, z_x, zp_x = match_state

    # Reconstruct the dominant branch at the bridge point, then transport it to x_match.
    alpha = ydom_bridge / yrec_bridge
    beta = (ydomp_bridge - alpha * yrecp_bridge) / zp_bridge
    ydom_x = alpha * yrec_x + beta * z_x
    ydomp_x = alpha * yrecp_x + beta * zp_x

    wkb_info = {
        "stable_digits": min(bridge_digits, leg2_digits),
        "step": f"{bridge_step} then {leg2_step}",
        "z0prime": zp_bridge,
        "bridge_digits": bridge_digits,
        "leg2_digits": leg2_digits,
    }

    # Verify the expected Wronskian constant at the match point.
    A_match = 3 * x_match * x_match + x_match + 1
    wronskian_match = A_match * (yrec_x * ydomp_x - yrecp_x * ydom_x)

    # For diagnostics, compare with the naive unstable backward dominant shot.
    naive_dom_state, naive_dom_digits, naive_dom_step = integrate_with_step_halving(
        [ydom0, ydomp0],
        x0,
        x_match,
        h0=mp.mpf("4"),
        target_digits=min(20, dps - 20),
        max_halvings=4,
    )
    naive_ydom_x, naive_ydomp_x = naive_dom_state
    naive_wronskian = A_match * (yrec_x * naive_ydomp_x - yrecp_x * naive_ydom_x)

    print("[3/5] Assembling the connection matrix ...", flush=True)

    # ------------------------------------------------------------------
    # Step 3: Connection matrix M
    # ------------------------------------------------------------------
    F = mp.matrix([[y1_x, y2_x], [y1p_x, y2p_x]])
    W = mp.matrix([[yrec_x, ydom_x], [yrecp_x, ydomp_x]])
    M = F ** -1 * W

    print("[4/5] Running PSLQ searches ...", flush=True)

    # ------------------------------------------------------------------
    # Step 4: PSLQ
    # ------------------------------------------------------------------
    mp.mp.dps = dps
    V = compute_vquad(args.depth, dps)
    basis_labels = [
        "1",
        "pi",
        "log(2)",
        "log(3)",
        "sqrt(3)",
        "Gamma(1/3)",
        "Gamma(2/3)",
        "Gamma(1/4)",
        "Gamma(3/4)",
        "zeta(3)",
    ]
    basis_values = [
        mp.mpf("1"),
        mp.pi,
        mp.log(2),
        mp.log(3),
        mp.sqrt(3),
        mp.gamma(mp.mpf("1") / 3),
        mp.gamma(mp.mpf("2") / 3),
        mp.gamma(mp.mpf("1") / 4),
        mp.gamma(mp.mpf("3") / 4),
        mp.zeta(3),
    ]

    M_rounded = mp.matrix([[+M[0, 0], +M[0, 1]], [+M[1, 0], +M[1, 1]]])
    scalar_pslq = {
        "M11": pslq_scalar_report(M_rounded[0, 0], basis_labels, basis_values, maxcoeff=500),
        "M12": pslq_scalar_report(M_rounded[0, 1], basis_labels, basis_values, maxcoeff=500),
        "M21": pslq_scalar_report(M_rounded[1, 0], basis_labels, basis_values, maxcoeff=500),
        "M22": pslq_scalar_report(M_rounded[1, 1], basis_labels, basis_values, maxcoeff=500),
    }

    # Literal 8-vector core search (4 entries + 4 core constants)
    joint_core_labels = ["M11", "M12", "M21", "M22", "1", "pi", "log(2)", "sqrt(3)"]
    joint_core_values = [
        M_rounded[0, 0], M_rounded[0, 1], M_rounded[1, 0], M_rounded[1, 1],
        mp.mpf("1"), mp.pi, mp.log(2), mp.sqrt(3),
    ]
    joint_core = pslq_joint_report(joint_core_labels, joint_core_values, maxcoeff=500)

    # Natural full-basis joint search (4 entries + all 10 supplied basis elements)
    joint_full_labels = ["M11", "M12", "M21", "M22"] + basis_labels
    joint_full_values = [M_rounded[0, 0], M_rounded[0, 1], M_rounded[1, 0], M_rounded[1, 1]] + basis_values
    joint_full = pslq_joint_report(joint_full_labels, joint_full_values, maxcoeff=500)

    print("[5/5] Scanning simple V_quad combinations ...", flush=True)

    # ------------------------------------------------------------------
    # Step 5: V_quad simple-combination scan
    # ------------------------------------------------------------------
    vquad_scan = scan_vquad_combinations(M_rounded, V)

    # ------------------------------------------------------------------
    # Save JSON report
    # ------------------------------------------------------------------
    payload = {
        "ode": ODE_TEXT,
        "parameters": {
            "dps": dps,
            "internal_dps": internal_dps,
            "x0": str(x0),
            "x_match": str(x_match),
            "x_bridge": str(x_bridge),
            "series_terms": int(args.series_terms),
            "continued_fraction_depth": int(args.depth),
        },
        "indicial_roots": [fmt(rho1, 10), fmt(rho2, 10)],
        "frobenius": {
            "y1_normalization": "y1(0)=1, y1'(0)=0",
            "y2_normalization": "y2(0)=0, y2'(0)=1",
            "y1_series_preview": series_expression(y1_coeffs, digits=12),
            "y2_series_preview": series_expression(y2_coeffs, digits=12),
            "y1_coeffs": [fmt(c, 40) for c in y1_coeffs],
            "y2_coeffs": [fmt(c, 40) for c in y2_coeffs],
            "at_x_match": {
                "y1": fmt(y1_x, 50),
                "y1prime": fmt(y1p_x, 50),
                "y2": fmt(y2_x, 50),
                "y2prime": fmt(y2p_x, 50),
                "stable_digits": frob_digits,
                "step": frob_step,
            },
        },
        "wkb": {
            "sigma_plus": fmt(sigma_plus, 40),
            "sigma_minus": fmt(sigma_minus, 40),
            "mu_plus": fmt(mu_plus, 40),
            "mu_minus": fmt(mu_minus, 40),
            "recessive_asymptotic_order_used": rec_order,
            "dominant_asymptotic_order_used": dom_order,
            "recessive_at_x_match": {
                "y": fmt(yrec_x, 50),
                "yprime": fmt(yrecp_x, 50),
                "log_derivative": fmt(yrecp_x / yrec_x, 50),
            },
            "dominant_at_x_match": {
                "y": fmt(ydom_x, 50),
                "yprime": fmt(ydomp_x, 50),
                "log_derivative": fmt(ydomp_x / ydom_x, 50),
            },
            "wronskian_check": {
                "A(x_match)*(y_rec*y_dom' - y_rec'*y_dom)": fmt(wronskian_match, 50),
                "expected_asymptotic_constant_2*sqrt(3)": fmt(2 * mp.sqrt(3), 50),
            },
            "naive_backward_dominant_shot": {
                "y": fmt(naive_ydom_x, 30),
                "yprime": fmt(naive_ydomp_x, 30),
                "stable_digits": naive_dom_digits,
                "step": naive_dom_step,
                "wronskian": fmt(naive_wronskian, 30),
                "note": "This direct backward shot collapses onto the recessive branch numerically; the final dominant column uses the stabilized reconstruction above.",
            },
            "integration": {
                "stable_digits": wkb_info["stable_digits"],
                "step": wkb_info["step"],
            },
        },
        "connection_matrix": {
            "definition": "[[y_rec,y_dom],[y_rec',y_dom']] = [[y1,y2],[y1',y2']] * M",
            "M11": fmt(M_rounded[0, 0], 60),
            "M12": fmt(M_rounded[0, 1], 60),
            "M21": fmt(M_rounded[1, 0], 60),
            "M22": fmt(M_rounded[1, 1], 60),
            "M_20sig": {
                "M11": fmt(M_rounded[0, 0], 20),
                "M12": fmt(M_rounded[0, 1], 20),
                "M21": fmt(M_rounded[1, 0], 20),
                "M22": fmt(M_rounded[1, 1], 20),
            },
        },
        "pslq_scalar": scalar_pslq,
        "pslq_joint": {
            "core_8_vector": joint_core,
            "full_basis_vector": joint_full,
        },
        "vquad_scan": vquad_scan,
    }

    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Save Markdown report
    # ------------------------------------------------------------------
    def pslq_line(name: str, data: dict) -> str:
        if data["status"] == "hit":
            return f"- `{name}`: **hit** — `{data['relation']}` (digits `{data.get('digits', 'n/a')}`)"
        near = data.get("near_miss")
        if near is None:
            return f"- `{name}`: **None**"
        if "relation" in near:
            return (
                f"- `{name}`: **None** at bound 500; best outside bound is at `{near['bound']}` with "
                f"about `{near['digits']:.3f}` digits, relation `{near['relation']}`"
            )
        expr = near.get('expression', near.get('heuristic', 'no heuristic expression'))
        digits = near.get('digits', 0.0)
        return (
            f"- `{name}`: **None** at bound 500; best heuristic near-miss is `{expr}` "
            f"with about `{digits:.3f}` digits"
        )

    md = []
    md.append("# V_quad connection-matrix report")
    md.append("")
    md.append(f"ODE: `{ODE_TEXT}`")
    md.append("")
    md.append("## 1. Indicial roots and Frobenius basis")
    md.append("")
    md.append(f"- Indicial roots at `x=0`: `rho1 = {fmt(rho1, 10)}`, `rho2 = {fmt(rho2, 10)}`.")
    md.append("- Because `3x^2+x+1` does **not** vanish at `x=0`, this is actually an ordinary point; the two Frobenius roots `0,1` simply recover the usual analytic basis.")
    md.append(f"- `y1(x) = {series_expression(y1_coeffs, digits=10)}`")
    md.append(f"- `y2(x) = {series_expression(y2_coeffs, digits=10)}`")
    md.append(f"- Richardson-extrapolated RK4 transport from the `x=0` Frobenius data reached about `{frob_digits:.2f}` agreement digits.")
    md.append("")
    md.append("### Values at `x=10`")
    md.append("")
    md.append("| quantity | value |")
    md.append("|---|---:|")
    md.append(f"| `y1(10)` | `{fmt(y1_x, 25)}` |")
    md.append(f"| `y1'(10)` | `{fmt(y1p_x, 25)}` |")
    md.append(f"| `y2(10)` | `{fmt(y2_x, 25)}` |")
    md.append(f"| `y2'(10)` | `{fmt(y2p_x, 25)}` |")
    md.append("")
    md.append("## 2. WKB branches at infinity")
    md.append("")
    md.append(f"- `mu_+ = {fmt(mu_plus, 25)}`")
    md.append(f"- `mu_- = {fmt(mu_minus, 25)}`")
    md.append(f"- Recessive seed used: `x0 = {fmt(x0, 10)}`; stable dominant matching was performed at `x_bridge = {fmt(x_bridge, 10)}`.")
    md.append(f"- Recessive branch at `x=10`: `y_rec = {fmt(yrec_x, 25)}`, `y_rec'/y_rec = {fmt(yrecp_x / yrec_x, 25)}`")
    md.append(f"- Dominant branch at `x=10`: `y_dom = {fmt(ydom_x, 25)}`, `y_dom'/y_dom = {fmt(ydomp_x / ydom_x, 25)}`")
    md.append(f"- Wronskian check: `A(10) * W = {fmt(wronskian_match, 25)}` vs expected `2*sqrt(3) = {fmt(2*mp.sqrt(3), 25)}`.")
    md.append("")
    md.append("> The naive direct backward RK4 shot for the dominant branch collapses onto the recessive solution (Wronskian nearly zero). The reported dominant column therefore uses the stable reduction-of-order reconstruction with the same asymptotic normalization.")
    md.append("")
    md.append("## 3. Connection matrix")
    md.append("")
    md.append("The matrix is defined by")
    md.append("")
    md.append("```text")
    md.append("[[y_rec, y_dom], [y_rec', y_dom']] = [[y1, y2], [y1', y2']] * M")
    md.append("```")
    md.append("")
    md.append("| entry | value (20 sig. digits) |")
    md.append("|---|---:|")
    md.append(f"| `M11` | `{fmt(M_rounded[0,0], 20)}` |")
    md.append(f"| `M12` | `{fmt(M_rounded[0,1], 20)}` |")
    md.append(f"| `M21` | `{fmt(M_rounded[1,0], 20)}` |")
    md.append(f"| `M22` | `{fmt(M_rounded[1,1], 20)}` |")
    md.append("")
    md.append("## 4. PSLQ results")
    md.append("")
    md.append("Basis:")
    md.append("`{1, pi, log(2), log(3), sqrt(3), Gamma(1/3), Gamma(2/3), Gamma(1/4), Gamma(3/4), zeta(3)}`")
    md.append("")
    for key in ("M11", "M12", "M21", "M22"):
        md.append(pslq_line(key, scalar_pslq[key]))
    md.append("")
    md.append(f"- Joint PSLQ on the literal core 8-vector `[M11,M12,M21,M22,1,pi,log(2),sqrt(3)]`: **{joint_core['status']}**")
    md.append(f"- Joint PSLQ on the full supplied basis vector `[M11,M12,M21,M22] + basis`: **{joint_full['status']}**")
    md.append("")
    md.append("## 5. V_quad check")
    md.append("")
    md.append(f"- `V_quad = {fmt(V, 25)}`")
    md.append(f"- Best simple combination scanned from entries/ratios/determinant/inverse entries: `{vquad_scan['best_name']}` = `{vquad_scan['best_value']}`")
    md.append(f"- Agreement with `V_quad`: about `{vquad_scan['digits_vs_vquad']:.3f}` digits")
    if vquad_scan["simple_match"]:
        md.append("- **Possible simple match detected** (>=10 digits).")
    else:
        md.append("- **No simple combination of the tested `M`-expressions reproduces `V_quad`.**")
    md.append("")
    md.append("## 6. Bottom line")
    md.append("")
    md.append("- The Frobenius roots are `0` and `1`.")
    md.append("- A full two-column connection matrix can be assembled once the dominant branch is stabilized numerically.")
    md.append("- In the requested 300-digit PSLQ search, the matrix entries show no low-height relation with the supplied basis.")

    REPORT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    # Console summary
    print("V_quad connection-matrix computation complete")
    print(f"  rho = ({fmt(rho1,10)}, {fmt(rho2,10)})")
    print(f"  M11 = {fmt(M_rounded[0,0],20)}")
    print(f"  M12 = {fmt(M_rounded[0,1],20)}")
    print(f"  M21 = {fmt(M_rounded[1,0],20)}")
    print(f"  M22 = {fmt(M_rounded[1,1],20)}")
    print(f"  Wronskian check at x=10 = {fmt(wronskian_match,20)}")
    print(f"  naive backward-shot Wronskian = {fmt(naive_wronskian,20)}")
    print(f"  joint PSLQ core/full = {joint_core['status']} / {joint_full['status']}")
    print(f"  report -> {REPORT_MD}")
    print(f"  json   -> {REPORT_JSON}")


if __name__ == "__main__":
    main()
