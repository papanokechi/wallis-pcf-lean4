#!/usr/bin/env python3
"""
Generalized dichotomy conjecture scan for cubic and quartic PCFs.

Mission goals:
  1. Run the exact integer-grid scan requested by the user.
  2. Note that with integer alpha,beta one always has rho = alpha-beta in Z,
     so rho mod 1 = 0 for every strict-grid case.
  3. Add a small fractional-beta visibility probe so the conjectured Gamma(1/3),
     Gamma(2/3), Gamma(1/4), Gamma(3/4) sectors are actually testable.

The continued fraction convention matches the rest of the workspace:

    b_0 + a_1/(b_1 + a_2/(b_2 + ...))

with
    a_n = p*n^d,
    b_n = alpha*n + beta.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

import mpmath as mp

P_VALUES = [1, 2, 3, 4, 6, 8, -1, -2, -3, -4]
ALPHAS = [1, 2, 3, 4, 5, 6]
BETAS_INT = [0, 1, 2, 3, 4, 5]
RESULT_JSON = Path("results") / "generalized_dichotomy_scan.json"
RESULT_MD = Path("results") / "generalized_dichotomy_scan.md"


@dataclass
class RelationAttempt:
    family: str
    tier: str
    relation: list[int] | None
    relation_text: str
    digits: float


@dataclass
class CaseRecord:
    degree: int
    mode: str
    p: int
    alpha: str
    beta: str
    rho: str
    rho_mod_1: str
    bucket: str
    value_200: str
    stable_digits: float
    convergent: bool
    pslq_family: str
    pslq_result: str
    pslq_vector: list[int] | None
    pslq_digits: float
    confirm: str


def as_mpf(x: int | Fraction | float | str | Any) -> Any:
    if isinstance(x, mp.mpf):
        return x
    if isinstance(x, Fraction):
        return mp.mpf(x.numerator) / mp.mpf(x.denominator)
    return mp.mpf(x)


def as_fraction(x: int | Fraction | str) -> Fraction:
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x, 1)
    return Fraction(x)


def frac_str(x: int | Fraction) -> str:
    f = as_fraction(x)
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def digits_of_error(err: Any, floor_exp: int = 250) -> float:
    err = abs(err)
    floor = mp.mpf(10) ** (-floor_exp)
    if not mp.isfinite(err):
        return 0.0
    return float(max(mp.mpf(0), -mp.log10(err + floor)))


def eval_cf(p: int, degree: int, alpha: int | Fraction, beta: int | Fraction,
            depth: int = 200, dps: int = 120) -> Any | None:
    alpha_m = as_mpf(alpha)
    beta_m = as_mpf(beta)
    with mp.workdps(dps + 30):
        v = mp.mpf("0")
        for n in range(depth, 0, -1):
            n_m = mp.mpf(n)
            a_n = mp.mpf(p) * (n_m ** degree)
            b_n = alpha_m * n_m + beta_m
            denom = b_n + v
            if not mp.isfinite(denom) or abs(denom) < mp.mpf(10) ** (-(dps - 10)):
                return None
            v = a_n / denom
            if not mp.isfinite(v):
                return None
        out = beta_m + v
        if not mp.isfinite(out):
            return None
        return +out


def convergence_profile(p: int, degree: int, alpha: int | Fraction, beta: int | Fraction,
                        dps: int = 120) -> tuple[bool, float, Any | None]:
    depths = [120, 160, 200]
    vals: list[Any] = []
    for depth in depths:
        v = eval_cf(p, degree, alpha, beta, depth=depth, dps=dps)
        if v is None:
            return False, 0.0, None
        vals.append(v)
    v200 = vals[-1]
    stable = min(digits_of_error(v200 - vals[0]), digits_of_error(v200 - vals[1]))
    return stable >= 10.0, stable, v200


def rho_data(alpha: int | Fraction, beta: int | Fraction) -> tuple[Fraction, Fraction]:
    rho = as_fraction(alpha) - as_fraction(beta)
    mod = rho - int(mp.floor(as_mpf(rho)))
    mod_f = Fraction(str(mod)).limit_denominator(12)
    if mod_f == 1:
        mod_f = Fraction(0, 1)
    return rho, mod_f


def bucket_for(degree: int, rho_mod_1: Fraction) -> str:
    if rho_mod_1 == 0:
        return "bucket_0"
    if degree == 3:
        if rho_mod_1 == Fraction(1, 3):
            return "bucket_1_3"
        if rho_mod_1 == Fraction(2, 3):
            return "bucket_2_3"
    if degree == 4:
        if rho_mod_1 == Fraction(1, 4):
            return "bucket_1_4"
        if rho_mod_1 == Fraction(3, 4):
            return "bucket_3_4"
    return "bucket_other"


def predicted_family(bucket: str) -> str:
    return {
        "bucket_0": "rational",
        "bucket_1_3": "gamma_1_3",
        "bucket_2_3": "gamma_2_3",
        "bucket_1_4": "gamma_1_4",
        "bucket_3_4": "gamma_3_4",
    }.get(bucket, "other")


@lru_cache(maxsize=1)
def cubic_tiers() -> dict[str, list[tuple[str, list[tuple[str, Any]]]]]:
    g13 = mp.gamma(mp.mpf(1) / 3)
    g23 = mp.gamma(mp.mpf(2) / 3)
    pi23 = mp.pi ** (mp.mpf(2) / 3)
    return {
        "rational": [
            ("Q(1)", [("1", mp.mpf(1))]),
        ],
        "gamma_1_3": [
            ("Gamma(1/3)-powers", [("1", mp.mpf(1)), ("Gamma(1/3)", g13), ("Gamma(1/3)^2", g13**2), ("Gamma(1/3)^3", g13**3)]),
            ("Gamma(1/3)-pi ratios", [("1", mp.mpf(1)), ("Gamma(1/3)/pi", g13 / mp.pi), ("Gamma(1/3)^2/pi", g13**2 / mp.pi), ("Gamma(1/3)/pi^(2/3)", g13 / pi23)]),
            ("Reflection mix", [("1", mp.mpf(1)), ("3^(1/4)*Gamma(1/3)/pi", (mp.mpf(3) ** (mp.mpf(1) / 4)) * g13 / mp.pi), ("pi/Gamma(1/3)^2", mp.pi / (g13**2)), ("Gamma(1/3)*Gamma(2/3)", g13 * g23)]),
            ("Gamma(2/3)-shell", [("1", mp.mpf(1)), ("Gamma(2/3)", g23), ("Gamma(2/3)^2", g23**2), ("Gamma(1/3)*Gamma(2/3)", g13 * g23)]),
        ],
        "gamma_2_3": [
            ("Gamma(2/3)-powers", [("1", mp.mpf(1)), ("Gamma(2/3)", g23), ("Gamma(2/3)^2", g23**2), ("Gamma(1/3)*Gamma(2/3)", g13 * g23)]),
            ("Gamma(1/3)-reflection", [("1", mp.mpf(1)), ("Gamma(1/3)", g13), ("Gamma(1/3)^2/pi", g13**2 / mp.pi), ("pi/Gamma(1/3)^2", mp.pi / (g13**2))]),
        ],
    }


@lru_cache(maxsize=1)
def quartic_tiers() -> dict[str, list[tuple[str, list[tuple[str, Any]]]]]:
    g14 = mp.gamma(mp.mpf(1) / 4)
    g34 = mp.gamma(mp.mpf(3) / 4)
    rt2 = mp.sqrt(2)
    return {
        "rational": [
            ("Q(1)", [("1", mp.mpf(1))]),
        ],
        "gamma_1_4": [
            ("Gamma(1/4)-powers", [("1", mp.mpf(1)), ("Gamma(1/4)", g14), ("Gamma(1/4)^2", g14**2), ("Gamma(1/4)^3", g14**3), ("Gamma(1/4)^4", g14**4)]),
            ("Gamma(1/4)-pi ratios", [("1", mp.mpf(1)), ("Gamma(1/4)/pi", g14 / mp.pi), ("Gamma(1/4)^2/pi", g14**2 / mp.pi), ("Gamma(1/4)^2/pi^(1/2)", g14**2 / mp.sqrt(mp.pi))]),
            ("Reflection mix", [("1", mp.mpf(1)), ("Gamma(3/4)", g34), ("Gamma(1/4)*Gamma(3/4)", g14 * g34), ("sqrt2*Gamma(1/4)^2/pi", rt2 * g14**2 / mp.pi)]),
        ],
        "gamma_3_4": [
            ("Gamma(3/4)-shell", [("1", mp.mpf(1)), ("Gamma(3/4)", g34), ("Gamma(1/4)*Gamma(3/4)", g14 * g34), ("Gamma(1/4)^2/(pi*sqrt2)", g14**2 / (mp.pi * rt2))]),
            ("Gamma(1/4)-reflection", [("1", mp.mpf(1)), ("Gamma(1/4)", g14), ("Gamma(1/4)^2/pi", g14**2 / mp.pi), ("sqrt2*Gamma(1/4)^2/pi", rt2 * g14**2 / mp.pi)]),
        ],
    }


def relation_text(names: list[str], rel: list[int]) -> str:
    chunks = []
    for coeff, name in zip(rel, names):
        if coeff:
            chunks.append(f"{coeff}*{name}")
    return " + ".join(chunks) + " = 0" if chunks else "0 = 0"


def try_pslq(value: Any, family: str, tier_name: str,
             basis: list[tuple[str, Any]], maxcoeff: int = 500) -> RelationAttempt:
    names = ["x"] + [name for name, _ in basis]
    vec = [value] + [val for _, val in basis]
    try:
        rel = mp.pslq(vec, maxcoeff=maxcoeff, tol=mp.mpf(10) ** (-70), maxsteps=2000)
    except Exception:
        rel = None
    if not rel:
        return RelationAttempt(family=family, tier=tier_name, relation=None, relation_text="no relation", digits=0.0)
    rel_list = [int(c) for c in rel]
    if rel_list[0] == 0:
        return RelationAttempt(family=family, tier=tier_name, relation=None, relation_text="basis-internal relation only", digits=0.0)
    residual = abs(sum(mp.mpf(c) * v for c, v in zip(rel_list, vec)))
    digits = digits_of_error(residual, floor_exp=120)
    return RelationAttempt(
        family=family,
        tier=tier_name,
        relation=rel_list,
        relation_text=relation_text(names, rel_list),
        digits=digits,
    )


def best_relation(value: Any, degree: int) -> RelationAttempt:
    tiers = cubic_tiers() if degree == 3 else quartic_tiers()
    best = RelationAttempt(family="none", tier="", relation=None, relation_text="no relation", digits=0.0)
    for family, family_tiers in tiers.items():
        for tier_name, basis in family_tiers:
            att = try_pslq(value, family, tier_name, basis)
            if att.digits > best.digits:
                best = att
    return best


def verdict(bucket: str, rel_family: str, rel_digits: float, convergent: bool) -> str:
    if not convergent:
        return "unstable"
    expected = predicted_family(bucket)
    if rel_digits < 8:
        return "no-hit"
    if expected == rel_family:
        return "yes"
    if expected.startswith("gamma_") and rel_family.startswith("gamma_"):
        return "reflection-equivalent"
    return "ANOMALY"


def scan_degree(degree: int, include_fractional_probe: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    modes: list[tuple[str, list[int | Fraction]]] = [("strict_integer_grid", BETAS_INT)]
    if include_fractional_probe:
        if degree == 3:
            frac_betas = [Fraction(m, 1) + frac for m in BETAS_INT for frac in (Fraction(1, 3), Fraction(2, 3))]
        else:
            frac_betas = [Fraction(m, 1) + frac for m in BETAS_INT for frac in (Fraction(1, 4), Fraction(3, 4))]
        modes.append(("fractional_visibility_probe", frac_betas))

    rows: list[CaseRecord] = []
    high_priority: list[dict[str, Any]] = []

    for mode_name, betas in modes:
        for p in P_VALUES:
            for alpha in ALPHAS:
                for beta in betas:
                    rho, rho_mod_1 = rho_data(alpha, beta)
                    bucket = bucket_for(degree, rho_mod_1)
                    convergent, stable_digits, value = convergence_profile(p, degree, alpha, beta)
                    rel = RelationAttempt(family="none", tier="", relation=None, relation_text="no relation", digits=0.0)
                    if convergent and value is not None:
                        rel = best_relation(value, degree)
                        if rel.digits >= 20:
                            high_priority.append({
                                "degree": degree,
                                "mode": mode_name,
                                "p": p,
                                "alpha": frac_str(alpha),
                                "beta": frac_str(beta),
                                "rho": frac_str(rho),
                                "bucket": bucket,
                                "digits": round(rel.digits, 3),
                                "relation": rel.relation_text,
                                "family": rel.family,
                            })
                    rows.append(CaseRecord(
                        degree=degree,
                        mode=mode_name,
                        p=p,
                        alpha=frac_str(alpha),
                        beta=frac_str(beta),
                        rho=frac_str(rho),
                        rho_mod_1=frac_str(rho_mod_1),
                        bucket=bucket,
                        value_200=mp.nstr(value, 25) if value is not None else "nan",
                        stable_digits=round(stable_digits, 3),
                        convergent=bool(convergent),
                        pslq_family=rel.family,
                        pslq_result=rel.relation_text,
                        pslq_vector=rel.relation,
                        pslq_digits=round(rel.digits, 3),
                        confirm=verdict(bucket, rel.family, rel.digits, convergent),
                    ))

    by_mode = {}
    for mode_name, _ in modes:
        mode_rows = [r for r in rows if r.mode == mode_name]
        bucket_counts: dict[str, int] = {}
        convergent_rows = [r for r in mode_rows if r.convergent]
        relation_rows = [r for r in convergent_rows if r.pslq_digits >= 8]
        anomalies = [asdict(r) for r in mode_rows if r.confirm == "ANOMALY"][:20]
        for r in mode_rows:
            bucket_counts[r.bucket] = bucket_counts.get(r.bucket, 0) + 1
        by_mode[mode_name] = {
            "count": len(mode_rows),
            "convergent": len(convergent_rows),
            "relation_hits": len(relation_rows),
            "bucket_counts": bucket_counts,
            "top_hits": [asdict(r) for r in sorted(relation_rows, key=lambda z: z.pslq_digits, reverse=True)[:5]],
            "anomalies": anomalies,
        }

    strict_rows = [r for r in rows if r.mode == "strict_integer_grid"]
    strict_conv = [r for r in strict_rows if r.convergent]
    strict_rel = [r for r in strict_conv if r.pslq_digits >= 8]
    if not strict_conv:
        status = "MIXED"
    else:
        rational_hits = sum(1 for r in strict_rel if r.pslq_family == "rational")
        if rational_hits == len(strict_rel) and len(strict_rel) == len(strict_conv):
            status = "STRONGLY SUPPORTED"
        elif rational_hits >= max(1, len(strict_rel) // 2):
            status = "SUPPORTED"
        elif len(strict_rel) == 0:
            status = "REFUTED"
        elif rational_hits == 0 and len(strict_rel) > 0:
            status = "REFUTED"
        else:
            status = "MIXED"

    out["summary"] = by_mode
    out["rows"] = [asdict(r) for r in rows]
    out["high_priority"] = high_priority
    out["status"] = status
    return out


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Generalized Dichotomy Conjecture Scan",
        "",
        "> Note: on the exact integer grid, `rho = alpha - beta` is always an integer, so `rho mod 1 = 0` for every strict-grid case. The nonzero `1/3, 2/3, 1/4, 3/4` buckets only appear in the auxiliary fractional-beta visibility probe.",
        "",
    ]
    for degree_key in ("degree_3", "degree_4"):
        block = payload[degree_key]
        degree = 3 if degree_key.endswith("3") else 4
        lines += [f"## Degree {degree}", ""]
        for mode_name, summary in block["summary"].items():
            lines += [f"### {mode_name}", ""]
            lines += [
                f"- Convergent cases: **{summary['convergent']} / {summary['count']}**",
                f"- PSLQ relation hits (`>=8` digits): **{summary['relation_hits']}**",
                f"- Bucket counts: `{summary['bucket_counts']}`",
                f"- Conjecture status: **{block['status']}**",
                "",
                "| (p, α, β) | ρ | ρ mod 1 | bucket | PSLQ result | digits | confirm? |",
                "|---|---:|---:|---|---|---:|---|",
            ]
            shown = 0
            for row in sorted([r for r in block["rows"] if r["mode"] == mode_name], key=lambda r: (-(1 if r["convergent"] else 0), -r["pslq_digits"], -r["stable_digits"])):
                if shown >= 25:
                    break
                result = row["pslq_result"].replace("|", "\\|")
                if len(result) > 70:
                    result = result[:67] + "..."
                lines.append(
                    f"| `({row['p']}, {row['alpha']}, {row['beta']})` | {row['rho']} | {row['rho_mod_1']} | `{row['bucket']}` | {result} | {row['pslq_digits']:.3f} | `{row['confirm']}` |"
                )
                shown += 1
            lines.append("")
            lines.append("#### Top 5 strongest PSLQ matches")
            lines.append("")
            if summary["top_hits"]:
                for item in summary["top_hits"]:
                    lines.append(
                        f"- `({item['p']}, {item['alpha']}, {item['beta']})` → `{item['pslq_result']}`  (**{item['pslq_digits']} digits**, family `{item['pslq_family']}`)"
                    )
            else:
                lines.append("- No relation hits at the requested coefficient bound.")
            lines.append("")
            lines.append("#### Anomalies")
            lines.append("")
            if summary["anomalies"]:
                for item in summary["anomalies"][:10]:
                    lines.append(
                        f"- `({item['p']}, {item['alpha']}, {item['beta']})`, bucket `{item['bucket']}` → `{item['pslq_family']}` / `{item['pslq_result']}`"
                    )
            else:
                lines.append("- No cross-family anomalies detected among the recorded PSLQ hits.")
            lines.append("")
    if payload.get("high_priority"):
        lines += ["## High-priority hits (>20 digits)", ""]
        for item in payload["high_priority"]:
            lines.append(
                f"- Degree {item['degree']} `{item['mode']}` `({item['p']}, {item['alpha']}, {item['beta']})`: `{item['relation']}` (**{item['digits']} digits**)."
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan the generalized dichotomy conjecture for cubic and quartic PCFs.")
    parser.add_argument("--no-fractional-probe", action="store_true", help="Run only the exact integer grid from the mission brief.")
    args = parser.parse_args()

    mp.mp.dps = 140
    payload = {
        "meta": {
            "p_values": P_VALUES,
            "alphas": ALPHAS,
            "betas_integer": BETAS_INT,
            "pslq_maxcoeff": 500,
            "pslq_dps": 120,
            "cf_depth": 200,
            "note": "Strict integer grid has rho mod 1 = 0 identically; fractional probe added so the Gamma buckets are actually visible.",
        },
        "degree_3": scan_degree(3, include_fractional_probe=not args.no_fractional_probe),
        "degree_4": scan_degree(4, include_fractional_probe=not args.no_fractional_probe),
    }
    payload["high_priority"] = payload["degree_3"].get("high_priority", []) + payload["degree_4"].get("high_priority", [])

    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    RESULT_MD.write_text(render_md(payload), encoding="utf-8")

    print(f"Wrote {RESULT_JSON}")
    print(f"Wrote {RESULT_MD}")
    print(f"Degree 3 status: {payload['degree_3']['status']}")
    print(f"Degree 4 status: {payload['degree_4']['status']}")
    if payload["high_priority"]:
        print("HIGH PRIORITY HITS:")
        for item in payload["high_priority"][:10]:
            print(f"  d={item['degree']} mode={item['mode']} (p,alpha,beta)=({item['p']},{item['alpha']},{item['beta']}) digits={item['digits']} family={item['family']}")
    else:
        print("No >20-digit PSLQ hits detected.")


if __name__ == "__main__":
    main()
