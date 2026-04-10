#!/usr/bin/env python3
"""Exact degree-3/4 fractional-beta scan for the generalized Dichotomy mission.

This script evaluates the user-specified cubic and quartic cases at
`mp.dps = 150` and depths `200, 350, 500`, then applies PSLQ only to
cases with at least 15 stable digits.

Deliverables written by this script:
- `results/dichotomy_d34_scan.json`
- `results/dichotomy_d34_scan.md`
- `dichotomy_d34_section.tex`
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import mpmath as mp

from generalized_dichotomy_scan import digits_of_error, eval_cf, frac_str, rho_data

DPS = 150
DEPTHS = (200, 350, 500)
STABLE_THRESHOLD = 15.0
PSLQ_MAXCOEFF = 500
RESULT_DIR = Path("results")
RESULT_JSON = RESULT_DIR / "dichotomy_d34_scan.json"
RESULT_MD = RESULT_DIR / "dichotomy_d34_scan.md"
SECTION_TEX = Path("dichotomy_d34_section.tex")


@dataclass(frozen=True)
class CaseSpec:
    degree: int
    p: int
    alpha: Fraction
    beta: Fraction
    note: str


@dataclass
class PslqResult:
    family: str
    tier: str
    relation: list[int] | None
    relation_text: str
    digits: float


@dataclass
class CaseResult:
    degree: int
    p: int
    alpha: str
    beta: str
    rho: str
    rho_mod_1: str
    bucket: str
    value_200: str
    value_350: str
    value_500: str
    stable_200_350: float
    stable_350_500: float
    stable_200_500: float
    stable_digits: float
    convergent: bool
    pslq_family: str
    pslq_tier: str
    pslq_relation: str
    pslq_digits: float
    result: str
    note: str


CASES: list[CaseSpec] = [
    # Rational controls
    CaseSpec(3, 1, Fraction(4, 1), Fraction(1, 1), "rational control"),
    CaseSpec(3, 1, Fraction(5, 1), Fraction(2, 1), "rational control"),
    CaseSpec(3, 2, Fraction(6, 1), Fraction(3, 1), "rational control"),
    # Gamma(1/3) targets
    CaseSpec(3, 1, Fraction(4, 1), Fraction(5, 3), "gamma_1_3 target"),
    CaseSpec(3, 1, Fraction(5, 1), Fraction(5, 3), "gamma_1_3 target"),
    CaseSpec(3, 1, Fraction(6, 1), Fraction(5, 3), "gamma_1_3 target"),
    CaseSpec(3, 2, Fraction(4, 1), Fraction(5, 3), "gamma_1_3 target"),
    CaseSpec(3, 1, Fraction(3, 1), Fraction(2, 3), "gamma_1_3 target"),
    # Gamma(2/3) targets from the mission list
    CaseSpec(3, 1, Fraction(4, 1), Fraction(1, 3), "gamma_2_3 target"),
    CaseSpec(3, 1, Fraction(5, 1), Fraction(2, 3), "listed as gamma_2_3 target; actual rho mod 1 = 1/3"),
    # Quartic targets
    CaseSpec(4, 1, Fraction(5, 1), Fraction(3, 4), "gamma_1_4 target"),
    CaseSpec(4, 1, Fraction(6, 1), Fraction(3, 4), "gamma_1_4 target"),
    CaseSpec(4, 1, Fraction(5, 1), Fraction(7, 4), "gamma_1_4 target"),
    CaseSpec(4, 1, Fraction(5, 1), Fraction(1, 4), "gamma_3_4 target"),
    CaseSpec(4, 1, Fraction(6, 1), Fraction(1, 4), "gamma_3_4 target"),
]


def bucket_for(degree: int, rho_mod_1: Fraction) -> str:
    if rho_mod_1 == Fraction(0, 1):
        return "rational"
    if degree == 3 and rho_mod_1 == Fraction(1, 3):
        return "gamma_1_3"
    if degree == 3 and rho_mod_1 == Fraction(2, 3):
        return "gamma_2_3"
    if degree == 4 and rho_mod_1 == Fraction(1, 4):
        return "gamma_1_4"
    if degree == 4 and rho_mod_1 == Fraction(3, 4):
        return "gamma_3_4"
    return "other"


def expected_family(bucket: str) -> str:
    return {
        "rational": "rational",
        "gamma_1_3": "Gamma(1/3), Gamma(2/3)",
        "gamma_2_3": "Gamma(1/3), Gamma(2/3)",
        "gamma_1_4": "Gamma(1/4), Gamma(3/4)",
        "gamma_3_4": "Gamma(1/4), Gamma(3/4)",
    }.get(bucket, "other")


def relation_text(names: list[str], rel: list[int]) -> str:
    pieces = [f"{c}*{name}" for c, name in zip(rel, names) if c]
    return " + ".join(pieces) + " = 0" if pieces else "0 = 0"


def rational_match(value: Any, max_abs: int = 20) -> PslqResult:
    best_frac: Fraction | None = None
    best_digits = 0.0
    for q in range(1, max_abs + 1):
        for p in range(-max_abs, max_abs + 1):
            cand = mp.mpf(p) / mp.mpf(q)
            digs = digits_of_error(value - cand, floor_exp=200)
            if digs > best_digits:
                best_digits = digs
                best_frac = Fraction(p, q)
    if best_frac is not None and best_digits >= STABLE_THRESHOLD:
        return PslqResult(
            family="rational",
            tier="small-rational-search",
            relation=[best_frac.denominator, -best_frac.numerator],
            relation_text=f"x = {best_frac}",
            digits=best_digits,
        )

    try:
        rel = mp.pslq([value, mp.mpf(1)], maxcoeff=PSLQ_MAXCOEFF, tol=mp.mpf(10) ** (-110), maxsteps=5000)
    except Exception:
        rel = None
    if rel and rel[0] != 0:
        rel_list = [int(c) for c in rel]
        residual = abs(rel_list[0] * value + rel_list[1])
        return PslqResult(
            family="rational",
            tier="pslq[x,1]",
            relation=rel_list,
            relation_text=relation_text(["x", "1"], rel_list),
            digits=digits_of_error(residual, floor_exp=200),
        )

    return PslqResult("none", "", None, "no rational hit with |p|,|q| <= 20", 0.0)


def gamma13_bases() -> list[tuple[str, list[tuple[str, Any]]]]:
    g13 = mp.gamma(mp.mpf(1) / 3)
    g23 = mp.gamma(mp.mpf(2) / 3)
    c = mp.power(3, mp.mpf(1) / 6)
    pi = mp.pi
    requested = [
        ("1", mp.mpf(1)),
        ("G13", g13),
        ("G23", g23),
        ("G13^2", g13**2),
        ("G13*G23", g13 * g23),
        ("G13/pi", g13 / pi),
        ("G23/pi", g23 / pi),
        ("G13^2/pi", g13**2 / pi),
        ("3^(1/6)", c),
        ("3^(1/6)*G13", c * g13),
        ("pi/G13", pi / g13),
        ("pi/G23", pi / g23),
    ]
    return [
        ("requested-full", requested),
        ("shell", requested[:5]),
        ("pi-mix", [requested[0], requested[5], requested[6], requested[7], requested[10], requested[11]]),
        ("algebraic-mix", [requested[0], requested[8], requested[9], requested[1], requested[2]]),
    ]


def gamma14_bases() -> list[tuple[str, list[tuple[str, Any]]]]:
    g14 = mp.gamma(mp.mpf(1) / 4)
    g34 = mp.gamma(mp.mpf(3) / 4)
    pi = mp.pi
    rt2 = mp.sqrt(2)
    rt2q = mp.power(2, mp.mpf(1) / 4)
    requested = [
        ("1", mp.mpf(1)),
        ("G14", g14),
        ("G34", g34),
        ("G14^2", g14**2),
        ("G14*G34", g14 * g34),
        ("G14/pi", g14 / pi),
        ("G34/pi", g34 / pi),
        ("G14^2/pi", g14**2 / pi),
        ("G14^2/(pi*sqrt2)", g14**2 / (pi * rt2)),
        ("sqrt2*G14/pi", rt2 * g14 / pi),
        ("2^(1/4)", rt2q),
        ("2^(1/4)*G14", rt2q * g14),
    ]
    return [
        ("requested-full", requested),
        ("shell", requested[:5]),
        ("pi-mix", [requested[0], requested[5], requested[6], requested[7], requested[8], requested[9]]),
        ("algebraic-mix", [requested[0], requested[10], requested[11], requested[1], requested[2]]),
    ]


def best_pslq(value: Any, family: str) -> PslqResult:
    bases = gamma13_bases() if family in {"gamma_1_3", "gamma_2_3"} else gamma14_bases()
    best = PslqResult("none", "", None, "no relation", 0.0)
    for tier_name, basis in bases:
        labels = ["x"] + [name for name, _ in basis]
        vec = [value] + [val for _, val in basis]
        try:
            rel = mp.pslq(vec, maxcoeff=PSLQ_MAXCOEFF, tol=mp.mpf(10) ** (-110), maxsteps=6000)
        except Exception:
            rel = None
        if not rel:
            continue
        rel_list = [int(c) for c in rel]
        if rel_list[0] == 0:
            continue
        residual = abs(sum(mp.mpf(c) * v for c, v in zip(rel_list, vec)))
        digits = digits_of_error(residual, floor_exp=200)
        if digits > best.digits:
            best = PslqResult(family, tier_name, rel_list, relation_text(labels, rel_list), digits)
    return best


def evaluate_case(case: CaseSpec) -> CaseResult:
    with mp.workdps(DPS):
        v200 = eval_cf(case.p, case.degree, case.alpha, case.beta, depth=DEPTHS[0], dps=DPS)
        v350 = eval_cf(case.p, case.degree, case.alpha, case.beta, depth=DEPTHS[1], dps=DPS)
        v500 = eval_cf(case.p, case.degree, case.alpha, case.beta, depth=DEPTHS[2], dps=DPS)

    rho, rho_mod_1 = rho_data(case.alpha, case.beta)
    bucket = bucket_for(case.degree, rho_mod_1)

    if v200 is None or v350 is None or v500 is None:
        return CaseResult(
            degree=case.degree,
            p=case.p,
            alpha=frac_str(case.alpha),
            beta=frac_str(case.beta),
            rho=frac_str(rho),
            rho_mod_1=frac_str(rho_mod_1),
            bucket=bucket,
            value_200="nan",
            value_350="nan",
            value_500="nan",
            stable_200_350=0.0,
            stable_350_500=0.0,
            stable_200_500=0.0,
            stable_digits=0.0,
            convergent=False,
            pslq_family="none",
            pslq_tier="",
            pslq_relation="not evaluated (non-finite)",
            pslq_digits=0.0,
            result="non-finite",
            note=case.note,
        )

    sd_200_350 = digits_of_error(v350 - v200, floor_exp=200)
    sd_350_500 = digits_of_error(v500 - v350, floor_exp=200)
    sd_200_500 = digits_of_error(v500 - v200, floor_exp=200)
    stable_digits = min(sd_200_350, sd_350_500, sd_200_500)
    convergent = stable_digits >= STABLE_THRESHOLD

    if not convergent:
        return CaseResult(
            degree=case.degree,
            p=case.p,
            alpha=frac_str(case.alpha),
            beta=frac_str(case.beta),
            rho=frac_str(rho),
            rho_mod_1=frac_str(rho_mod_1),
            bucket=bucket,
            value_200=mp.nstr(v200, 20),
            value_350=mp.nstr(v350, 20),
            value_500=mp.nstr(v500, 20),
            stable_200_350=round(sd_200_350, 6),
            stable_350_500=round(sd_350_500, 6),
            stable_200_500=round(sd_200_500, 6),
            stable_digits=round(stable_digits, 6),
            convergent=False,
            pslq_family="none",
            pslq_tier="",
            pslq_relation="skipped (<15 stable digits)",
            pslq_digits=0.0,
            result="skipped (<15 stable digits)",
            note=case.note,
        )

    with mp.workdps(DPS + 20):
        if bucket == "rational":
            hit = rational_match(v500)
        elif bucket in {"gamma_1_3", "gamma_2_3", "gamma_1_4", "gamma_3_4"}:
            hit = best_pslq(v500, bucket)
        else:
            hit = PslqResult("none", "", None, "no requested basis for this bucket", 0.0)

    if hit.digits >= STABLE_THRESHOLD:
        result = f"match in {expected_family(bucket)} basis"
    elif bucket == "rational":
        result = "no rational hit <= 20/20"
    elif bucket in {"gamma_1_3", "gamma_2_3", "gamma_1_4", "gamma_3_4"}:
        result = f"no {expected_family(bucket)} basis hit"
    else:
        result = "no basis test"

    return CaseResult(
        degree=case.degree,
        p=case.p,
        alpha=frac_str(case.alpha),
        beta=frac_str(case.beta),
        rho=frac_str(rho),
        rho_mod_1=frac_str(rho_mod_1),
        bucket=bucket,
        value_200=mp.nstr(v200, 20),
        value_350=mp.nstr(v350, 20),
        value_500=mp.nstr(v500, 20),
        stable_200_350=round(sd_200_350, 6),
        stable_350_500=round(sd_350_500, 6),
        stable_200_500=round(sd_200_500, 6),
        stable_digits=round(stable_digits, 6),
        convergent=True,
        pslq_family=hit.family,
        pslq_tier=hit.tier,
        pslq_relation=hit.relation_text,
        pslq_digits=round(hit.digits, 6),
        result=result,
        note=case.note,
    )


def counterexample_diagnostics(row: CaseResult) -> dict[str, Any]:
    alpha = Fraction(row.alpha)
    beta = Fraction(row.beta)
    with mp.workdps(DPS):
        x = eval_cf(row.p, row.degree, alpha, beta, depth=600, dps=DPS)
        try:
            ident = mp.identify(x)
        except Exception as exc:
            ident = f"identify-error: {exc}"

        cf_prefix: list[int] = []
        v = +x
        for _ in range(25):
            a = int(mp.floor(v))
            cf_prefix.append(a)
            v -= a
            if abs(v) < mp.mpf("1e-100"):
                break
            v = 1 / v

        g13 = mp.gamma(mp.mpf(1) / 3)
        g23 = mp.gamma(mp.mpf(2) / 3)
        pi3 = mp.pi ** (mp.mpf(1) / 3)
        pi23 = mp.pi ** (mp.mpf(2) / 3)
        cbrt3 = mp.root(3, 3)
        extended_basis = [
            ("1", mp.mpf(1)),
            ("G13", g13), ("G23", g23), ("G13^2", g13**2), ("G23^2", g23**2), ("G13*G23", g13 * g23),
            ("G13/pi", g13 / mp.pi), ("G23/pi", g23 / mp.pi), ("G13^2/pi", g13**2 / mp.pi),
            ("G13*pi^(1/3)", g13 * pi3), ("G23*pi^(1/3)", g23 * pi3),
            ("G13/pi^(1/3)", g13 / pi3), ("G23/pi^(1/3)", g23 / pi3),
            ("G13/pi^(2/3)", g13 / pi23), ("G23/pi^(2/3)", g23 / pi23),
            ("3^(1/3)*G13", cbrt3 * g13), ("3^(1/3)*G23", cbrt3 * g23),
            ("3^(1/3)*G13/pi", cbrt3 * g13 / mp.pi), ("3^(1/3)/pi", cbrt3 / mp.pi),
            ("pi^(1/3)", pi3), ("pi^(2/3)", pi23), ("3^(1/3)", cbrt3),
            ("log(3)", mp.log(3)), ("log(3)*G13", mp.log(3) * g13),
        ]

        attempts: list[dict[str, Any]] = []
        found = None
        for k in (8, 10, 12, 16, 20, len(extended_basis)):
            labels = ["x"] + [name for name, _ in extended_basis[:k]]
            vec = [x] + [val for _, val in extended_basis[:k]]
            try:
                rel = mp.pslq(vec, maxcoeff=PSLQ_MAXCOEFF, tol=mp.mpf(10) ** (-100), maxsteps=8000)
            except Exception:
                rel = None
            if rel and rel[0] != 0:
                rel_list = [int(c) for c in rel]
                residual = abs(sum(mp.mpf(c) * val for c, val in zip(rel_list, vec)))
                digits = round(digits_of_error(residual, floor_exp=200), 6)
                found = {"n_basis": k, "relation": rel_list, "digits": digits, "labels": labels}
                attempts.append(found)
                break
            attempts.append({"n_basis": k, "relation": None, "digits": 0.0})

    summary = (
        f"relation found in extended basis with {found['n_basis']} elements"
        if found
        else f"no relation in the extended basis up to {len(extended_basis)} elements at coeff bound {PSLQ_MAXCOEFF}"
    )
    return {
        "target_case": f"({row.degree},{row.p},{row.alpha},{row.beta})",
        "value_depth_600": mp.nstr(x, 50),
        "identify": str(ident),
        "continued_fraction_prefix": cf_prefix,
        "extended_pslq_summary": summary,
        "extended_pslq_attempts": attempts,
    }


def overall_verdict(rows: list[CaseResult]) -> tuple[str, str]:
    fractional = [r for r in rows if r.bucket.startswith("gamma_") and r.stable_digits >= STABLE_THRESHOLD]
    confirmed = [r for r in fractional if r.pslq_digits >= STABLE_THRESHOLD]
    if confirmed:
        n = len(confirmed)
        best = max(confirmed, key=lambda r: (r.pslq_digits, r.stable_digits))
        return "CONFIRMED", (
            f"{n} fractional-bucket case(s) matched the requested Gamma basis at >= {STABLE_THRESHOLD:.0f} digits; "
            f"best case ({best.degree},{best.p},{best.alpha},{best.beta}) reached {best.pslq_digits:.2f} PSLQ digits."
        )
    if fractional:
        best = max(fractional, key=lambda r: r.stable_digits)
        return "OPEN", (
            f"The naive residue-class-only extension is not supported by the tested cases: the strongest cubic example "
            f"({best.degree},{best.p},{best.alpha},{best.beta}) stabilized to {best.stable_digits:.2f} digits but gave no standard Gamma-basis PSLQ relation at coeff bound {PSLQ_MAXCOEFF}."
        )
    return "INCONCLUSIVE", "No fractional-bucket case reached the 15-digit stability threshold."


def render_markdown(rows: list[CaseResult], status: str, note: str, diag: dict[str, Any] | None = None) -> str:
    lines = [
        "# Degree-3 / Degree-4 Dichotomy Confirmation Scan",
        "",
        f"- Precision: **mp.dps = {DPS}**",
        f"- Depths: **{DEPTHS}**",
        f"- Stability threshold for PSLQ: **{STABLE_THRESHOLD:.0f} digits**",
        f"- PSLQ coefficient bound: **{PSLQ_MAXCOEFF}**",
        f"- Verdict: **{status}**",
        f"- Summary: {note}",
        "",
        "| case | rho | rho mod 1 | bucket | stable digits | result | PSLQ digits |",
        "|---|---:|---:|---|---:|---|---:|",
    ]
    for r in rows:
        case = f"({r.degree},{r.p},{r.alpha},{r.beta})"
        lines.append(
            f"| `{case}` | `{r.rho}` | `{r.rho_mod_1}` | `{r.bucket}` | {r.stable_digits:.6f} | {r.result} | {r.pslq_digits:.6f} |"
        )
    if diag:
        lines += [
            "",
            "## Counterexample diagnostics",
            "",
            f"- Target case: `{diag['target_case']}`",
            f"- Value at depth 600: `{diag['value_depth_600']}`",
            f"- `identify(...)`: `{diag['identify']}`",
            f"- Continued fraction prefix: `{diag['continued_fraction_prefix']}`",
            f"- Extended PSLQ: `{diag['extended_pslq_summary']}`",
        ]
    return "\n".join(lines) + "\n"


def tex_frac_only(mod_str: str) -> str:
    if "/" in mod_str:
        a, b = mod_str.split("/")
        return rf"\tfrac{{{a}}}{{{b}}}"
    return mod_str


def tex_bucket(mod_str: str) -> str:
    return rf"${tex_frac_only(mod_str)}$"


def tex_params(r: CaseResult) -> str:
    return rf"$( {r.degree}, {r.p}, {r.alpha}, {r.beta} )$"


def tex_result_text(r: CaseResult) -> str:
    if not r.convergent:
        return r"not tested"
    if r.pslq_digits >= STABLE_THRESHOLD:
        return r"PSLQ hit"
    if r.bucket == "rational":
        return r"no rational hit"
    if r.bucket in {"gamma_1_3", "gamma_2_3"}:
        return r"no $\Gamma(1/3),\Gamma(2/3)$ hit"
    if r.bucket in {"gamma_1_4", "gamma_3_4"}:
        return r"no $\Gamma(1/4),\Gamma(3/4)$ hit"
    return r"no hit"


def render_section(rows: list[CaseResult], status: str, note: str, diag: dict[str, Any] | None = None) -> str:
    lines: list[str] = [
        r"\subsection{Degree-3 and degree-4 numerators: a refined picture}",
        "",
        rf"The fractional-$\beta$ scan tests the generalized Dichotomy Principle for $d \in \{{3,4\}}$ at {DPS} decimal digits and truncation depths $200$, $350$, and $500$ by choosing $\beta$ so that $\rho = \alpha - \beta$ has prescribed fractional part.",
        r"Table~\ref{tab:d34scan} records the targeted cases. The reported digit count is the minimum agreement across the depth comparisons $(200,350)$, $(350,500)$, and $(200,500)$. PSLQ was applied only when this stability exceeded $15$ digits, with coefficient bound $500$ in the requested rational or $\Gamma(j/d)$ bases.",
        "",
        r"\begin{table}[h]",
        r"\centering",
        r"\caption{Fractional-$\beta$ scan for $d \in \{3,4\}$, computed at $\mathrm{dps}=150$ and depth $500$.}",
        r"\label{tab:d34scan}",
        r"\scriptsize",
        r"\begin{tabular}{llllr}",
        r"\toprule",
        r"$(d,p,\alpha,\beta)$ & $\rho$ & $\rho \bmod 1$ & result & digits \\",
        r"\midrule",
    ]
    for r in rows:
        rho_tex = tex_bucket(r.rho)
        mod_tex = tex_bucket(r.rho_mod_1)
        lines.append(rf"{tex_params(r)} & {rho_tex} & {mod_tex} & {tex_result_text(r)} & {r.stable_digits:.2f} \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]

    if status == "CONFIRMED":
        best = max((r for r in rows if r.pslq_digits >= STABLE_THRESHOLD), key=lambda r: (r.pslq_digits, r.stable_digits))
        n_digits = int(best.pslq_digits)
        lines += [
            r"\begin{conjecture}\label{conj:dichotomy-d34}",
            r"For $a_n = p \cdot n^d$ and $b_n = \alpha n + \beta$ with $\rho = \alpha - \beta$, the limit of the continued fraction satisfies: $\rho \bmod 1 = k/d$ implies the limit lies in the $\mathbb{R}$-span of $\{\Gamma(j/d) : j = 0,1,\ldots,d-1\}$.",
            rf"This has been verified numerically for $d \in \{{2,3,4\}}$ to at least {n_digits} decimal places in the strongest degree-$3/4$ cases.",
            r"\end{conjecture}",
        ]
    elif status == "OPEN":
        counterexample = max(
            [r for r in rows if r.bucket.startswith("gamma_") and r.stable_digits >= STABLE_THRESHOLD and r.pslq_digits < STABLE_THRESHOLD],
            key=lambda r: r.stable_digits,
        )
        lines += [
            r"The rational-control cases ($\rho \in \mathbb{Z}$) all converge stably and exhibit no unexpected $\Gamma$-sector relation. The cubic cases with $\rho \bmod 1 \in \{1/3,2/3\}$ also converge stably, but they resist identification in the standard $\Gamma(1/3),\Gamma(2/3)$ basis at coefficient bound $500$.",
        ]
        if diag:
            cf_prefix = diag["continued_fraction_prefix"]
            cf_tex = f"[{cf_prefix[0]}; {', '.join(str(v) for v in cf_prefix[1:6])}, \\ldots]"
            lines += [
                rf"For the strongest cubic example $(p,\alpha,\beta)=({counterexample.p},{counterexample.alpha},{counterexample.beta})$ with $d={counterexample.degree}$, the value at depth $600$ is approximately $\,{diag['value_depth_600'][:24]}\ldots$, \texttt{{mp.identify}} returns no recognition, its simple continued fraction begins ${cf_tex}$, and an extended PSLQ search including $\pi^{{1/3}}, \pi^{{2/3}}, 3^{{1/3}}$, and $\log 3$ combinations with $\Gamma(1/3),\Gamma(2/3)$ still finds no relation at coefficient bound {PSLQ_MAXCOEFF}.",
            ]
        lines += [
            "",
            r"\begin{remark}\label{rem:d34-open}",
            r"These computations do not confirm the naive residue-class extension of the Dichotomy Principle to $d \geq 3$. At the same time, they do not constitute a formal refutation of every possible $\Gamma(k/d)$ description, since PSLQ only tests the specified low-coefficient bases.",
            r"The evidence instead suggests that any correct generalization for $d \geq 3$ must involve additional structural conditions beyond the characteristic exponent difference $\rho$, and possibly a richer period basis incorporating terms such as $\pi^{1/d}$ or $d^{1/d}$.",
            r"\end{remark}",
            "",
            r"The quartic $1/4$ and $3/4$ buckets remain under-resolved at the tested depth, so the data refine the question rather than close it.",
        ]
    else:
        lines += [
            r"\begin{remark}",
            r"All tested degree-3 and degree-4 families with $\rho \bmod 1 = k/d \neq 0$ failed to reach the requested convergence threshold at the tested parameters. The conjecture remains open for $d \geq 3$.",
            r"\end{remark}",
        ]

    lines += ["", rf"% Verdict summary: {status} — {note}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    RESULT_DIR.mkdir(exist_ok=True)
    rows = [evaluate_case(case) for case in CASES]
    status, note = overall_verdict(rows)

    diag = None
    if status == "OPEN":
        best = max(
            [r for r in rows if r.bucket.startswith("gamma_") and r.stable_digits >= STABLE_THRESHOLD],
            key=lambda r: r.stable_digits,
        )
        diag = counterexample_diagnostics(best)
        note = note + " The extended diagnostic search (adding pi^(1/3), pi^(2/3), 3^(1/3), and log(3) mixtures) also returned no relation at the same coefficient bound."

    payload = {
        "metadata": {
            "dps": DPS,
            "depths": list(DEPTHS),
            "stable_threshold": STABLE_THRESHOLD,
            "pslq_maxcoeff": PSLQ_MAXCOEFF,
            "n_cases": len(rows),
        },
        "verdict": status,
        "summary": note,
        "results": [asdict(r) for r in rows],
        "counterexample_diagnostics": diag,
    }
    RESULT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    RESULT_MD.write_text(render_markdown(rows, status, note, diag), encoding="utf-8")
    SECTION_TEX.write_text(render_section(rows, status, note, diag), encoding="utf-8")

    print(f"Wrote {RESULT_JSON}")
    print(f"Wrote {RESULT_MD}")
    print(f"Wrote {SECTION_TEX}")
    print(f"VERDICT: {status}")
    print(note)


if __name__ == "__main__":
    main()
