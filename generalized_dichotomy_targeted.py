#!/usr/bin/env python3
"""Targeted fractional-rho verification for the generalized dichotomy conjecture.

Implements the corrected mission:
- targeted cubic and quartic cases with fractional beta,
- stability check via depth 300 vs 400,
- PSLQ on the requested rational/Gamma bases at 150 dps,
- non-Gamma counterexample probe for the strongest 1/3-sector case,
- automatic p-extension if any match exceeds 15 digits.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import gcd
from pathlib import Path
from typing import Any

import mpmath as mp

from generalized_dichotomy_scan import eval_cf, digits_of_error, frac_str, rho_data

RESULT_JSON = Path("results") / "dichotomy_fractional_beta_report.json"
RESULT_MD = Path("results") / "dichotomy_fractional_beta_report.md"
LEGACY_RESULT_JSON = Path("results") / "generalized_dichotomy_targeted.json"
LEGACY_RESULT_MD = Path("results") / "generalized_dichotomy_targeted.md"
CONFIRMATION_SUMMARY = Path("results") / "dichotomy_conjecture_confirmed_summary.md"

BETA_MAX_DEN = 12
BETA_MAX_ABS = 3
DEGREE_P_VALUES = {3: [1, 2, -1], 4: [1]}
ALPHA_VALUES = {3: [3, 4, 5, 6], 4: [5, 6]}
TARGET_BUCKETS = {
    3: {"rational", "gamma_1_3", "gamma_2_3"},
    4: {"rational", "gamma_1_4", "gamma_3_4"},
}

P_EXTENSION = [1, 2, 3, 4, -1, -2, -3, -4, 6, 8]


@dataclass
class TargetCase:
    tag: str
    degree: int
    p: int
    alpha: Fraction
    beta: Fraction
    expected_bucket: str
    note: str = ""


@dataclass
class PslqAttempt:
    family: str
    tier: str
    basis_labels: list[str]
    relation: list[int] | None
    relation_text: str
    digits: float


@dataclass
class CaseResult:
    tag: str
    degree: int
    p: int
    alpha: str
    beta: str
    rho: str
    rho_mod_1: str
    bucket: str
    stable_digits: float
    value_20sig: str
    convergent: bool
    pslq_family: str
    pslq_tier: str
    pslq_relation: str
    pslq_vector: list[int] | None
    pslq_digits: float
    confirm: str
    note: str = ""


@dataclass
class ExtensionResult:
    degree: int
    alpha: str
    beta: str
    bucket: str
    p: int
    stable_digits: float
    pslq_family: str
    pslq_relation: str
    pslq_digits: float


@dataclass
class Step4Result:
    target_tag: str
    value: str
    stable_digits: float
    gamma_family: str
    gamma_relation: str
    gamma_digits: float
    non_gamma_family: str
    non_gamma_relation: str
    non_gamma_digits: float
    verdict: str


@dataclass
class BasisBundle:
    family: str
    tiers: list[tuple[str, list[tuple[str, Any]]]]


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


def rational_match(value: Any, max_num: int = 30, max_den: int = 30) -> PslqAttempt:
    best_frac = None
    best_digits = 0.0
    for q in range(1, max_den + 1):
        for p in range(-max_num, max_num + 1):
            cand = mp.mpf(p) / mp.mpf(q)
            digs = digits_of_error(value - cand, floor_exp=180)
            if digs > best_digits:
                best_digits = digs
                best_frac = Fraction(p, q)
    if best_frac is not None and best_digits >= 20:
        rel = [best_frac.denominator, -best_frac.numerator]
        text = f"{best_frac.denominator}*x + ({-best_frac.numerator})*1 = 0  [x = {best_frac}]"
        return PslqAttempt("rational", "small-rational-search", ["x", "1"], rel, text, best_digits)
    rel = mp.pslq([value, mp.mpf(1)], maxcoeff=500, tol=mp.mpf(10) ** (-90), maxsteps=3000)
    if rel and rel[0] != 0:
        rel_list = [int(c) for c in rel]
        residual = abs(rel_list[0] * value + rel_list[1])
        digits = digits_of_error(residual, floor_exp=180)
        return PslqAttempt("rational", "pslq[x,1]", ["x", "1"], rel_list, f"{rel_list[0]}*x + {rel_list[1]} = 0", digits)
    return PslqAttempt("none", "small-rational-search", ["x", "1"], None, "no rational match ≤30/30", 0.0)


def gamma13_bundle() -> BasisBundle:
    g13 = mp.gamma(mp.mpf(1) / 3)
    g23 = mp.gamma(mp.mpf(2) / 3)
    pi = mp.pi
    rt3q = mp.mpf(3) ** (mp.mpf(1) / 4)
    requested = [
        ("1", mp.mpf(1)),
        ("G13", g13),
        ("G23", g23),
        ("G13^2", g13**2),
        ("G13*G23", g13 * g23),
        ("G23^2", g23**2),
        ("G13/pi", g13 / pi),
        ("G23/pi", g23 / pi),
        ("G13^2/pi", g13**2 / pi),
        ("G13*G23/pi", g13 * g23 / pi),
        ("pi/G13", pi / g13),
        ("pi/G23", pi / g23),
        ("pi^2/G13^2", pi**2 / (g13**2)),
        ("3^(1/4)", rt3q),
        ("3^(1/4)*G13", rt3q * g13),
        ("3^(1/4)/G13", rt3q / g13),
    ]
    primary = requested[:6]
    pi_mix = requested[6:13]
    algebraic_mix = [requested[0], requested[13], requested[14], requested[15], requested[1], requested[2]]
    return BasisBundle(
        "gamma_1_3",
        [
            ("primary", primary),
            ("pi-mix", pi_mix),
            ("algebraic-mix", algebraic_mix),
            ("requested-full", requested),
        ],
    )


def gamma14_bundle() -> BasisBundle:
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
        ("G34^2", g34**2),
        ("G14/pi", g14 / pi),
        ("G34/pi", g34 / pi),
        ("G14^2/pi", g14**2 / pi),
        ("G14^2/(pi*sqrt2)", g14**2 / (pi * rt2)),
        ("sqrt2*G14^2/pi", rt2 * g14**2 / pi),
        ("pi/G14", pi / g14),
        ("pi/G34", pi / g34),
        ("2^(1/4)", rt2q),
        ("2^(1/4)*G14", rt2q * g14),
        ("G14/2^(1/4)", g14 / rt2q),
    ]
    primary = requested[:6]
    pi_mix = requested[6:13]
    algebraic_mix = [requested[0], requested[13], requested[14], requested[15], requested[1], requested[2]]
    return BasisBundle(
        "gamma_1_4",
        [
            ("primary", primary),
            ("pi-mix", pi_mix),
            ("algebraic-mix", algebraic_mix),
            ("requested-full", requested),
        ],
    )


def non_gamma_bundle() -> BasisBundle:
    return BasisBundle(
        "non-gamma-common",
        [
            (
                "tier1+2-common",
                [
                    ("1", mp.mpf(1)),
                    ("pi", mp.pi),
                    ("pi^2", mp.pi**2),
                    ("pi^3", mp.pi**3),
                    ("log(2)", mp.log(2)),
                    ("Catalan", mp.catalan),
                    ("zeta(3)", mp.zeta(3)),
                    ("sqrt(2)", mp.sqrt(2)),
                    ("sqrt(3)", mp.sqrt(3)),
                ],
            )
        ],
    )


def try_pslq(value: Any, bundle: BasisBundle, maxcoeff: int = 500) -> PslqAttempt:
    best = PslqAttempt("none", "", ["x"], None, "no relation", 0.0)
    for tier_name, basis in bundle.tiers:
        labels = ["x"] + [name for name, _ in basis]
        vec = [value] + [val for _, val in basis]
        try:
            rel = mp.pslq(vec, maxcoeff=maxcoeff, tol=mp.mpf(10) ** (-90), maxsteps=4000)
        except Exception:
            rel = None
        if not rel:
            continue
        rel_list = [int(c) for c in rel]
        if rel_list[0] == 0:
            continue
        residual = abs(sum(mp.mpf(c) * v for c, v in zip(rel_list, vec)))
        digits = digits_of_error(residual, floor_exp=180)
        text = " + ".join(f"{c}*{name}" for c, name in zip(rel_list, labels) if c) + " = 0"
        if digits > best.digits:
            best = PslqAttempt(bundle.family, tier_name, labels, rel_list, text, digits)
    return best


def fractional_beta_grid(max_den: int = BETA_MAX_DEN, max_abs: int = BETA_MAX_ABS) -> list[Fraction]:
    betas: set[Fraction] = set()
    for q in range(1, max_den + 1):
        for p in range(-max_abs * q, max_abs * q + 1):
            if gcd(abs(p), q) != 1:
                continue
            betas.add(Fraction(p, q))
    return sorted(betas)


def build_cases() -> list[TargetCase]:
    cases: list[TargetCase] = []
    beta_grid = fractional_beta_grid()

    for degree, p_values in DEGREE_P_VALUES.items():
        allowed_buckets = TARGET_BUCKETS[degree]
        for p in p_values:
            for alpha_int in ALPHA_VALUES[degree]:
                alpha = Fraction(alpha_int, 1)
                for beta in beta_grid:
                    rho, rho_mod_1 = rho_data(alpha, beta)
                    bucket = bucket_for(degree, rho_mod_1)
                    if bucket not in allowed_buckets:
                        continue
                    tag = f"d{degree}_p{p}_a{frac_str(alpha)}_b{frac_str(beta)}"
                    tag = tag.replace("-", "m").replace("/", "_")
                    note = (
                        f"dense fractional beta sweep: reduced p/q with q≤{BETA_MAX_DEN}, "
                        f"|β|≤{BETA_MAX_ABS}, target bucket={bucket}, ρ={frac_str(rho)}"
                    )
                    cases.append(TargetCase(tag, degree, p, alpha, beta, bucket, note))

    return cases


def evaluate_case(case: TargetCase) -> CaseResult:
    with mp.workdps(140):
        v300 = eval_cf(case.p, case.degree, case.alpha, case.beta, depth=300, dps=120)
        v400 = eval_cf(case.p, case.degree, case.alpha, case.beta, depth=400, dps=120)
        rho, rho_mod_1 = rho_data(case.alpha, case.beta)
        bucket = bucket_for(case.degree, rho_mod_1)

        if v300 is None or v400 is None or (not mp.isfinite(v300)) or (not mp.isfinite(v400)):
            return CaseResult(
                tag=case.tag,
                degree=case.degree,
                p=case.p,
                alpha=frac_str(case.alpha),
                beta=frac_str(case.beta),
                rho=frac_str(rho),
                rho_mod_1=frac_str(rho_mod_1),
                bucket=bucket,
                stable_digits=0.0,
                value_20sig="nan",
                convergent=False,
                pslq_family="none",
                pslq_tier="",
                pslq_relation="not evaluated (non-finite)",
                pslq_vector=None,
                pslq_digits=0.0,
                confirm="INCONCLUSIVE",
                note=case.note,
            )

        stable_digits = digits_of_error(v400 - v300, floor_exp=180)
        convergent = stable_digits >= 20.0
        value_sig = mp.nstr(v400, 22)

        best = PslqAttempt("none", "", ["x"], None, "not run (<20 stable digits)", 0.0)
        confirm = "INCONCLUSIVE"
        if convergent:
            with mp.workdps(170):
                if case.expected_bucket == "rational":
                    best = rational_match(v400)
                    if best.digits >= 20:
                        confirm = "CONFIRMED"
                    else:
                        # still check that no Gamma(1/3) surprise appears in the rational control
                        gamma_control = try_pslq(v400, gamma13_bundle()) if case.degree == 3 else try_pslq(v400, gamma14_bundle())
                        if gamma_control.digits >= 15:
                            best = gamma_control
                            confirm = "REFUTED"
                        else:
                            confirm = "INCONCLUSIVE"
                elif case.degree == 3:
                    best = try_pslq(v400, gamma13_bundle())
                    if best.digits >= 15:
                        if bucket == "gamma_1_3":
                            confirm = "CONFIRMED"
                        elif bucket == "gamma_2_3":
                            confirm = "CONFIRMED"
                    else:
                        confirm = "INCONCLUSIVE"
                else:
                    best = try_pslq(v400, gamma14_bundle())
                    if best.digits >= 15:
                        if bucket == "gamma_1_4":
                            confirm = "CONFIRMED"
                        elif bucket == "gamma_3_4":
                            confirm = "CONFIRMED"
                    else:
                        confirm = "INCONCLUSIVE"

        return CaseResult(
            tag=case.tag,
            degree=case.degree,
            p=case.p,
            alpha=frac_str(case.alpha),
            beta=frac_str(case.beta),
            rho=frac_str(rho),
            rho_mod_1=frac_str(rho_mod_1),
            bucket=bucket,
            stable_digits=round(stable_digits, 6),
            value_20sig=value_sig,
            convergent=convergent,
            pslq_family=best.family,
            pslq_tier=best.tier,
            pslq_relation=best.relation_text,
            pslq_vector=best.relation,
            pslq_digits=round(best.digits, 6),
            confirm=confirm,
            note=case.note,
        )


def run_step4(results: list[CaseResult]) -> Step4Result:
    b_candidates = [r for r in results if r.degree == 3 and r.bucket == "gamma_1_3" and r.convergent]
    if not b_candidates:
        return Step4Result(
            "none",
            "nan",
            0.0,
            "none",
            "no convergent cubic 1/3-sector case",
            0.0,
            "none",
            "not run",
            0.0,
            "INCONCLUSIVE",
        )
    strongest = max(b_candidates, key=lambda r: (r.pslq_digits, r.stable_digits))
    beta = Fraction(strongest.beta)
    alpha = Fraction(strongest.alpha)
    with mp.workdps(170):
        value = eval_cf(strongest.p, strongest.degree, alpha, beta, depth=400, dps=120)
        gamma_hit = try_pslq(value, gamma13_bundle())
        non_gamma_hit = try_pslq(value, non_gamma_bundle())
    verdict = "INCONCLUSIVE"
    if non_gamma_hit.digits >= 15:
        verdict = "REFUTED"
    elif gamma_hit.digits >= 15 and non_gamma_hit.digits < 15:
        verdict = "CONFIRMED"
    return Step4Result(
        target_tag=strongest.tag,
        value=mp.nstr(value, 30),
        stable_digits=strongest.stable_digits,
        gamma_family=gamma_hit.family,
        gamma_relation=gamma_hit.relation_text,
        gamma_digits=round(gamma_hit.digits, 6),
        non_gamma_family=non_gamma_hit.family,
        non_gamma_relation=non_gamma_hit.relation_text,
        non_gamma_digits=round(non_gamma_hit.digits, 6),
        verdict=verdict,
    )


def run_extension(results: list[CaseResult]) -> list[ExtensionResult]:
    trigger = None
    for r in results:
        if r.pslq_digits > 15:
            trigger = r
            break
    if trigger is None:
        return []

    out: list[ExtensionResult] = []
    degree = trigger.degree
    alpha = Fraction(trigger.alpha)
    beta = Fraction(trigger.beta)
    bundle = gamma13_bundle() if degree == 3 else gamma14_bundle()
    for p in P_EXTENSION:
        with mp.workdps(170):
            v300 = eval_cf(p, degree, alpha, beta, depth=300, dps=120)
            v400 = eval_cf(p, degree, alpha, beta, depth=400, dps=120)
            if v300 is None or v400 is None or (not mp.isfinite(v300)) or (not mp.isfinite(v400)):
                continue
            stable = digits_of_error(v400 - v300, floor_exp=180)
            if stable < 20:
                continue
            hit = try_pslq(v400, bundle)
        out.append(
            ExtensionResult(
                degree=degree,
                alpha=frac_str(alpha),
                beta=frac_str(beta),
                bucket=trigger.bucket,
                p=p,
                stable_digits=round(stable, 6),
                pslq_family=hit.family,
                pslq_relation=hit.relation_text,
                pslq_digits=round(hit.digits, 6),
            )
        )
    return out


def bucket_status(results: list[CaseResult], bucket: str) -> tuple[str, str]:
    subset = [r for r in results if r.bucket == bucket]
    convergent = [r for r in subset if r.convergent]
    strong = [r for r in convergent if r.pslq_digits >= 15]
    if strong:
        return "CONFIRMED", f"{len(strong)} stable case(s) with ≥15-digit PSLQ hit in the expected family."
    if not convergent:
        return "INCONCLUSIVE", "No case in this bucket reached the 20-digit stability threshold at depth 400 vs 300."
    return "INCONCLUSIVE", f"{len(convergent)} stable case(s) tested but no ≥15-digit PSLQ relation was found at coeff bound 500."


def bucket_summary_data(results: list[CaseResult]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for bucket in ["rational", "gamma_1_3", "gamma_2_3", "gamma_1_4", "gamma_3_4"]:
        subset = [r for r in results if r.bucket == bucket]
        if not subset:
            continue
        best = max(subset, key=lambda r: (r.pslq_digits, r.stable_digits))
        out[bucket] = {
            "cases": len(subset),
            "convergent": sum(1 for r in subset if r.convergent),
            "best_case": f"({best.degree}, {best.p}, {best.alpha}, {best.beta})",
            "best_stable_digits": round(best.stable_digits, 6),
            "best_pslq_digits": round(best.pslq_digits, 6),
        }
    return out


def strongest_hit(results: list[CaseResult]) -> CaseResult:
    ranked = sorted(results, key=lambda r: (r.pslq_digits, r.stable_digits), reverse=True)
    return ranked[0]


def render_confirmation_summary(best: CaseResult) -> str:
    return (
        "Conjecture confirmed: the dense fractional-β targeted sweep over reduced fractions "
        f"`p/q` with `1 ≤ q ≤ {BETA_MAX_DEN}` and `|β| ≤ {BETA_MAX_ABS}` produced a stable expected-family PSLQ match for "
        f"`(d, p, α, β) = ({best.degree}, {best.p}, {best.alpha}, {best.beta})`, in bucket `{best.bucket}`. "
        f"The continued fraction stabilized to `{best.stable_digits:.6f}` digits between depths 300 and 400, and the best relation in the predicted basis reached `{best.pslq_digits:.6f}` digits: `{best.pslq_relation}`."
    )


def render_report(results: list[CaseResult], step4: Step4Result, extension: list[ExtensionResult]) -> str:
    stable_rows = [r for r in results if r.convergent]
    ranked = sorted(stable_rows or results, key=lambda r: (r.pslq_digits, r.stable_digits), reverse=True)
    best = strongest_hit(results)
    gamma_rows = [r for r in results if r.bucket in {"gamma_1_3", "gamma_2_3", "gamma_1_4", "gamma_3_4"}]
    best_gamma = max(gamma_rows, key=lambda r: (r.pslq_digits, r.stable_digits)) if gamma_rows else best
    best_quartic = max((r for r in gamma_rows if r.degree == 4), key=lambda r: (r.pslq_digits, r.stable_digits), default=None)
    summary = bucket_summary_data(results)
    confirmed = [r for r in stable_rows if r.confirm == "CONFIRMED" and r.pslq_digits >= 15]

    lines = [
        "# Generalized Dichotomy — Dense Fractional-β Targeted Sweep",
        "",
        "## Scan setup",
        f"- `β` grid: reduced fractions `p/q` with `1 ≤ q ≤ {BETA_MAX_DEN}` and `|β| ≤ {BETA_MAX_ABS}`.",
        f"- Degree 3 parameters kept from the prior targeted run: `p ∈ {DEGREE_P_VALUES[3]}`, `α ∈ {ALPHA_VALUES[3]}`.",
        f"- Degree 4 parameters kept from the prior targeted run: `p ∈ {DEGREE_P_VALUES[4]}`, `α ∈ {ALPHA_VALUES[4]}`.",
        f"- Total evaluated cases: **{len(results)}**; convergent at the ≥20-digit threshold: **{len(stable_rows)}**.",
        "",
        "## Bucket summary",
        "",
        "| bucket | cases | convergent | best case | best stable digits | best PSLQ digits |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for bucket, info in summary.items():
        lines.append(
            f"| `{bucket}` | {info['cases']} | {info['convergent']} | `{info['best_case']}` | {info['best_stable_digits']:.6f} | {info['best_pslq_digits']:.6f} |"
        )

    lines += ["", "## New best ratios / hits", ""]
    lines += [
        f"- Best overall candidate: `({best.degree}, {best.p}, {best.alpha}, {best.beta})` in `{best.bucket}` with **{best.stable_digits:.6f}** stable digits and **{best.pslq_digits:.6f}** PSLQ digits.",
        f"- Best fractional Gamma-sector candidate: `({best_gamma.degree}, {best_gamma.p}, {best_gamma.alpha}, {best_gamma.beta})` in `{best_gamma.bucket}` with value `{best_gamma.value_20sig}`.",
    ]
    if best_quartic is not None:
        lines.append(
            f"- Best quartic candidate: `({best_quartic.degree}, {best_quartic.p}, {best_quartic.alpha}, {best_quartic.beta})` with **{best_quartic.stable_digits:.6f}** stable digits and **{best_quartic.pslq_digits:.6f}** PSLQ digits."
        )

    lines += ["", "| rank | case | bucket | stable digits | PSLQ family | PSLQ digits | verdict |", "|---:|---|---|---:|---|---:|---|"]
    for idx, row in enumerate(ranked[:12], 1):
        lines.append(
            f"| {idx} | `({row.degree}, {row.p}, {row.alpha}, {row.beta})` | `{row.bucket}` | {row.stable_digits:.6f} | `{row.pslq_family or 'none'}` | {row.pslq_digits:.6f} | `{row.confirm}` |"
        )

    lines += ["", "## Conjecture status", ""]
    if confirmed:
        lines.append(f"**Verdict: CONFIRMED.** The dense fractional-β sweep found **{len(confirmed)}** stable expected-family hit(s) at or above 15 PSLQ digits.")
    else:
        lines.append("**Verdict: NOT CONFIRMED.** The denser fractional-β grid did not close the gap or produce an exact expected-family PSLQ match at the current precision and coeff bound.")
    for bucket in ["rational", "gamma_1_3", "gamma_2_3", "gamma_1_4", "gamma_3_4"]:
        status, reason = bucket_status(results, bucket)
        lines.append(f"- `{bucket}`: **{status}** — {reason}")

    lines += ["", "## Step 4 — counterexample search", ""]
    lines += [
        f"- Strongest cubic `1/3`-sector case: `{step4.target_tag}`",
        f"- Value: `{step4.value}`",
        f"- Stable digits: **{step4.stable_digits:.6f}**",
        f"- Gamma-basis result: `{step4.gamma_relation}` ({step4.gamma_digits:.6f} digits)",
        f"- Non-Gamma basis result: `{step4.non_gamma_relation}` ({step4.non_gamma_digits:.6f} digits)",
        f"- Verdict: **{step4.verdict}**",
    ]

    lines += ["", "## Recommended deep rerun", ""]
    lines.append(
        f"- Next best parameter set: `({best_gamma.degree}, {best_gamma.p}, {best_gamma.alpha}, {best_gamma.beta})` because it is the strongest fractional-β candidate under the current sweep (**{best_gamma.stable_digits:.6f}** stable digits)."
    )

    if extension:
        lines += ["", "## Extended p-scan", "", "| p | stable digits | PSLQ family | relation | digits |", "|---:|---:|---|---|---:|"]
        for row in extension:
            rel = row.pslq_relation.replace("|", "\\|")
            lines.append(f"| {row.p} | {row.stable_digits:.6f} | `{row.pslq_family}` | {rel} | {row.pslq_digits:.6f} |")
    else:
        lines += ["", "## Extended p-scan", "", "- Not triggered: no fractional-β case exceeded the 15-digit PSLQ threshold."]
    return "\n".join(lines)


def main() -> None:
    mp.mp.dps = 180
    beta_grid = fractional_beta_grid()
    cases = build_cases()
    results = [evaluate_case(case) for case in cases]
    step4 = run_step4(results)
    extension = run_extension(results)
    summary = bucket_summary_data(results)
    confirmed = [r for r in results if r.confirm == "CONFIRMED" and r.pslq_digits >= 15]

    payload = {
        "scan_metadata": {
            "beta_grid_definition": f"reduced p/q, 1<=q<={BETA_MAX_DEN}, |beta|<={BETA_MAX_ABS}",
            "beta_grid_count": len(beta_grid),
            "beta_values": [frac_str(beta) for beta in beta_grid],
            "degree_p_values": {str(k): v for k, v in DEGREE_P_VALUES.items()},
            "alpha_values": {str(k): v for k, v in ALPHA_VALUES.items()},
            "total_cases": len(results),
            "convergent_cases": sum(1 for r in results if r.convergent),
        },
        "bucket_summary": summary,
        "best_case": asdict(strongest_hit(results)),
        "confirmed_cases": [asdict(r) for r in confirmed],
        "results": [asdict(r) for r in results],
        "step4": asdict(step4),
        "extension": [asdict(r) for r in extension],
    }
    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    md_text = render_report(results, step4, extension)
    json_text = json.dumps(payload, indent=2)

    for path, text in [
        (RESULT_JSON, json_text),
        (LEGACY_RESULT_JSON, json_text),
        (RESULT_MD, md_text),
        (LEGACY_RESULT_MD, md_text),
    ]:
        path.write_text(text, encoding="utf-8")

    if confirmed:
        best_confirmed = max(confirmed, key=lambda r: (r.pslq_digits, r.stable_digits))
        CONFIRMATION_SUMMARY.write_text(render_confirmation_summary(best_confirmed), encoding="utf-8")
        print(f"Wrote {CONFIRMATION_SUMMARY}")
    elif CONFIRMATION_SUMMARY.exists():
        CONFIRMATION_SUMMARY.unlink()

    print(f"Wrote {RESULT_JSON}")
    print(f"Wrote {RESULT_MD}")
    for bucket in ["rational", "gamma_1_3", "gamma_2_3", "gamma_1_4", "gamma_3_4"]:
        status, reason = bucket_status(results, bucket)
        print(f"{bucket}: {status} -- {reason}")
    if any(r.pslq_digits > 20 for r in results):
        print("HIGH PRIORITY: at least one PSLQ match exceeded 20 digits")
    else:
        print("No PSLQ match exceeded 20 digits")


if __name__ == "__main__":
    main()
