from __future__ import annotations

"""Batch gauntlet evaluator for SIARC mutation swarms.

Runs a lightweight fitness estimate over a swarm of mutated formulas and keeps
only the strongest survivors for the Red-Team / LFI deep-dive.

This version adds an Active Symbolic Refinement (ASR) layer:
- parse candidate formulas with SymPy
- expose numeric literals / uppercase placeholders as tunable parameters
- attempt local optimization with `scipy.optimize`
- rewrite the best survivor with calibrated coefficients when the fit improves

Usage:
    py multi_agent_discussion/gauntlet.py --swarm swarm.json --execution siarc_outputs/agent_C_out.json
"""

import argparse
import hashlib
import json
import math
import re
import warnings
from pathlib import Path
from typing import Any

try:
    import numpy as np
except Exception:
    np = None

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import parse_expr
    HAS_SYMPY = True
except Exception:
    sp = None
    parse_expr = None
    HAS_SYMPY = False

try:
    from scipy.optimize import curve_fit, least_squares
    HAS_SCIPY = True
except Exception:
    curve_fit = None
    least_squares = None
    HAS_SCIPY = False

DEFAULT_SURVIVAL_THRESHOLD = 15.0
DEFAULT_MAX_SURVIVORS = 2
DEFAULT_ASR_THRESHOLD = 25.0
DEFAULT_PERFECTED_THRESHOLD = 0.001
DEFAULT_TRUSTED_SCALE_EPS = 0.05


def _read_json_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return json.loads(p.read_text(encoding=encoding))
        except (UnicodeError, json.JSONDecodeError):
            continue
    return json.loads(p.read_bytes().decode("utf-8", errors="replace"))


def _normalize_formula_text(formula: str) -> str:
    text = str(formula or "").strip()
    text = text.replace("·", "*").replace("−", "-")
    text = text.replace("π", "pi").replace("γ", "gamma")
    text = text.replace("₅", "5").replace("₁", "1")
    text = text.replace("^", "**")
    return text


def _extract_base_gap_pct(execution: dict[str, Any] | None) -> float:
    if not execution:
        return 100.0
    tool_results = execution.get("tool_results", {})
    for key in ("sandbox_parsed", "sandbox_fallback", "partition_ratios"):
        payload = tool_results.get(key, {}) if isinstance(tool_results, dict) else {}
        if isinstance(payload, dict):
            for gap_key in ("gap_pct", "gap", "gap_percent"):
                if gap_key in payload:
                    try:
                        return float(payload[gap_key])
                    except Exception:
                        pass
    return 100.0


def _extract_numeric_target(execution: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not execution:
        return None, None
    tool_results = execution.get("tool_results", {})
    for key in ("sandbox_parsed", "partition_ratios", "sandbox_fallback"):
        payload = tool_results.get(key, {}) if isinstance(tool_results, dict) else {}
        if isinstance(payload, dict):
            for y_key in ("L_numeric", "L", "numeric", "value"):
                if y_key in payload:
                    try:
                        target = float(payload[y_key])
                        predicted = None
                        for pred_key in ("L_predicted", "L_pred", "predicted", "expected"):
                            if pred_key in payload:
                                try:
                                    predicted = float(payload[pred_key])
                                except Exception:
                                    predicted = None
                        return target, predicted
                    except Exception:
                        pass
            stdout = payload.get("stdout")
            if isinstance(stdout, str) and stdout.strip().startswith("{"):
                try:
                    nested = json.loads(stdout.strip().splitlines()[-1])
                    if "L_numeric" in nested:
                        target = float(nested["L_numeric"])
                        predicted = float(nested.get("L_predicted", nested.get("L_pred", target)))
                        return target, predicted
                except Exception:
                    pass
    return None, None


def _infer_c_value(formula: str, execution: dict[str, Any] | None = None) -> float:
    gap_id = ""
    if execution:
        gap_id = str(execution.get("gap_id") or execution.get("hypothesis", {}).get("gap_id", ""))
    formula_lower = _normalize_formula_text(formula).lower()

    k = None
    match = re.search(r"c(\d+)", formula_lower)
    if match:
        k = int(match.group(1))
    if k is None:
        match = re.search(r"k[_-]?(\d+)", gap_id.lower())
        if match:
            k = int(match.group(1))
    if k is None:
        k = 5 if "c5" in formula_lower else 1
    return float(math.pi * math.sqrt((2.0 * k) / 3.0))


def _hash_jitter(text: str, span: float = 8.0) -> float:
    raw = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    unit = raw / 0xFFFFFFFF
    return (unit - 0.5) * 2.0 * span


def _safe_gap_pct(value: float, target: float) -> float:
    denom = max(abs(target), 1e-12)
    return max(0.00001, round(abs(value - target) / denom * 100.0, 5))


def _parameterize_formula(formula: str) -> tuple[str, str, list[str], list[float]]:
    normalized = _normalize_formula_text(formula)
    param_names: list[str] = []
    initial_values: list[float] = []
    parameterized = normalized

    numeric_tokens = list(dict.fromkeys(re.findall(r"(?<![A-Za-z_])\d+(?:\.\d+)?(?![A-Za-z_])", normalized)))
    for idx, token in enumerate(numeric_tokens):
        name = f"k{idx}"
        parameterized = re.sub(rf"(?<![A-Za-z_]){re.escape(token)}(?![A-Za-z_])", name, parameterized)
        param_names.append(name)
        initial_values.append(float(token))

    uppercase_tokens = [
        token for token in dict.fromkeys(re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", parameterized))
        if token not in {"E"} and token not in param_names
    ]
    for token in uppercase_tokens:
        param_names.append(token)
        initial_values.append(1.0)

    return normalized, parameterized, param_names, initial_values


def _inject_coefficients(parameterized_formula: str, param_names: list[str], values: list[float]) -> str:
    refined = parameterized_formula
    for name, value in sorted(zip(param_names, values), key=lambda item: -len(item[0])):
        refined = re.sub(rf"\b{re.escape(name)}\b", f"({value:.12g})", refined)
    return refined


def _evaluate_formula(formula: str, x_value: float) -> float | None:
    normalized = _normalize_formula_text(formula)
    if HAS_SYMPY and parse_expr is not None and sp is not None:
        c5 = sp.symbols("c5", real=True)
        expr = parse_expr(
            normalized,
            local_dict={
                "c5": c5,
                "pi": sp.pi,
                "e": sp.E,
                "gamma": sp.EulerGamma,
                "sqrt": sp.sqrt,
            },
            evaluate=True,
        )
        value = complex(expr.evalf(subs={c5: x_value}))
        if abs(value.imag) > 1e-8:
            return None
        return float(value.real)

    lowered = normalized.lower().replace("c5", str(x_value))
    safe_globals = {"__builtins__": {}}
    safe_locals = {"pi": math.pi, "e": math.e, "gamma": 0.5772156649015329, "sqrt": math.sqrt}
    try:
        return float(eval(lowered, safe_globals, safe_locals))
    except Exception:
        return None


def execute_sandbox_test(formula: str, base_gap_pct: float) -> dict[str, Any]:
    """Heuristic proxy for the existing gap-script sandbox.

    Until SIARC supports arbitrary formula injection into its mathematical
    sandbox, this function estimates fitness deterministically from the current
    evidence and from the structural properties of the mutated formula.
    """
    lower = _normalize_formula_text(formula).lower()
    gap = float(base_gap_pct)

    if all(token not in lower for token in ("/c5", "1/c5", "1 / c5")):
        gap -= 28.0
    if "sqrt(2)/12" in lower or "sqrt(2) / 12" in lower:
        gap -= 54.0
    if "pi/48" in lower or "gamma/12" in lower or "e/12" in lower:
        gap -= 18.0
    if " / 12" in lower or "/12" in lower:
        gap -= 10.0

    if lower.count("+") + lower.count("-") + lower.count("*") + lower.count("/") > 8:
        gap += 6.0
    if any(token in lower for token in ("gamma", "sqrt", "pi", "log")):
        gap += 2.0

    gap += _hash_jitter(formula, span=6.5)
    gap = max(0.00001, round(gap, 5))

    if gap < 1:
        fitness = "excellent"
    elif gap < 10:
        fitness = "strong"
    elif gap < 25:
        fitness = "promising"
    else:
        fitness = "weak"

    return {
        "gap_pct": gap,
        "fitness": fitness,
        "execution_mode": "heuristic_sandbox_proxy",
    }


def symbolic_refine(
    formula_str: str,
    execution: dict[str, Any] | None,
    initial_gap_pct: float,
) -> dict[str, Any]:
    """Attempt Active Symbolic Refinement (ASR) on a near-miss formula.

    This uses SymPy to parse the formula and `scipy.optimize` when available.
    Because the current SIARC sandbox exposes only a small amount of numeric
    target data, the optimizer uses a regularized local fit around the observed
    `c5` point and falls back to a scalar calibration when necessary.
    """
    target_y, predicted_y = _extract_numeric_target(execution)
    if target_y is None:
        return {
            "enabled": False,
            "status": "skipped",
            "reason": "no_numeric_target",
            "gap_pct": float(initial_gap_pct),
        }

    normalized, parameterized, param_names, initial_values = _parameterize_formula(formula_str)
    x_value = _infer_c_value(normalized, execution=execution)
    current_y = _evaluate_formula(normalized, x_value)
    if current_y is None:
        return {
            "enabled": False,
            "status": "skipped",
            "reason": "formula_not_evaluable",
            "gap_pct": float(initial_gap_pct),
        }

    best_formula = normalized
    best_gap = min(float(initial_gap_pct), _safe_gap_pct(current_y, target_y))
    best_method = "direct_eval"
    best_params: list[float] = []

    if HAS_SYMPY and parse_expr is not None and sp is not None and param_names:
        c5 = sp.symbols("c5", real=True)
        local_dict = {
            "c5": c5,
            "pi": sp.pi,
            "e": sp.E,
            "gamma": sp.EulerGamma,
            "sqrt": sp.sqrt,
        }
        for name in param_names:
            local_dict[name] = sp.symbols(name, real=True)
        try:
            expr = parse_expr(parameterized, local_dict=local_dict, evaluate=True)
            func = sp.lambdify(
                (c5, *[local_dict[name] for name in param_names]),
                expr,
                modules=["numpy", {"sqrt": math.sqrt, "pi": math.pi, "e": math.e, "gamma": float(sp.EulerGamma)}],
            )
            if np is not None:
                x_data = np.array([x_value * 0.999, x_value, x_value * 1.001], dtype=float)
                y_data = np.full_like(x_data, fill_value=float(target_y), dtype=float)
                initial = np.array(initial_values, dtype=float)

                def model_values(x_arr, params):
                    x_arr = np.asarray(x_arr, dtype=float).reshape(-1)
                    vals = np.array([float(func(float(xi), *params)) for xi in x_arr], dtype=float)
                    return vals

                if HAS_SCIPY and curve_fit is not None and len(param_names) <= len(x_data):
                    try:
                        def curve_model(x_arr, *params):
                            return model_values(x_arr, params)
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            popt, _ = curve_fit(curve_model, x_data, y_data, p0=initial, maxfev=20000)
                        refined = _inject_coefficients(parameterized, param_names, list(map(float, popt)))
                        refined_y = _evaluate_formula(refined, x_value)
                        if refined_y is not None:
                            gap = _safe_gap_pct(refined_y, target_y)
                            if gap < best_gap:
                                best_gap = gap
                                best_formula = refined
                                best_method = "curve_fit"
                                best_params = list(map(float, popt))
                    except Exception:
                        pass

                if HAS_SCIPY and least_squares is not None:
                    try:
                        def residual(params):
                            vals = model_values(x_data, params)
                            reg = 1e-3 * (np.asarray(params) - initial)
                            return np.concatenate([vals - y_data, reg])
                        res = least_squares(residual, initial, max_nfev=20000)
                        popt = list(map(float, res.x))
                        refined = _inject_coefficients(parameterized, param_names, popt)
                        refined_y = _evaluate_formula(refined, x_value)
                        if refined_y is not None:
                            gap = _safe_gap_pct(refined_y, target_y)
                            if gap < best_gap:
                                best_gap = gap
                                best_formula = refined
                                best_method = "least_squares"
                                best_params = popt
                    except Exception:
                        pass
        except Exception:
            pass

    # Scalar calibration fallback: if one-point fitting is all we have, scale the
    # entire expression so it hits the observed target exactly at the measured c5.
    if current_y is not None and abs(current_y) > 1e-12:
        scale = float(target_y) / float(current_y)
        scaled_formula = f"({scale:.12g})*({normalized})"
        scaled_y = _evaluate_formula(scaled_formula, x_value)
        if scaled_y is not None:
            scaled_gap = _safe_gap_pct(scaled_y, target_y)
            if scaled_gap < best_gap:
                best_gap = scaled_gap
                best_formula = scaled_formula
                best_method = "scalar_calibration"
                best_params = [scale]

    scale_factor = None
    trusted_refinement = best_method in {"curve_fit", "least_squares"}
    if best_method == "scalar_calibration" and best_params:
        try:
            scale_factor = float(best_params[0])
            trusted_refinement = abs(abs(scale_factor) - 1.0) <= DEFAULT_TRUSTED_SCALE_EPS
        except Exception:
            scale_factor = None
            trusted_refinement = False

    improved = best_gap + 1e-12 < float(initial_gap_pct)
    return {
        "enabled": True,
        "status": "refined" if improved else "no_improvement",
        "method": best_method,
        "refined_formula": best_formula,
        "structural_formula": normalized,
        "gap_pct": round(best_gap, 5),
        "trusted_gap_pct": round(best_gap if trusted_refinement else float(initial_gap_pct), 5),
        "parameter_names": ["scale"] if best_method == "scalar_calibration" else (param_names or ["scale"]),
        "parameter_values": best_params,
        "target_y": float(target_y),
        "predicted_y": predicted_y,
        "scale_factor": scale_factor,
        "trusted_refinement": trusted_refinement,
    }


def run_batch_gauntlet(
    swarm: dict[str, Any],
    execution: dict[str, Any] | None = None,
    max_survivors: int = DEFAULT_MAX_SURVIVORS,
    survival_threshold: float = DEFAULT_SURVIVAL_THRESHOLD,
) -> dict[str, Any]:
    base_gap_pct = _extract_base_gap_pct(execution)
    results = []

    for candidate in swarm.get("candidates", []):
        formula = candidate.get("formula", "")
        raw_stats = execute_sandbox_test(formula, base_gap_pct=base_gap_pct)
        raw_gap_pct = float(raw_stats.get("gap_pct", 100.0))
        status = "SURVIVED" if raw_gap_pct < survival_threshold else "KILLED"

        refined = None
        final_gap_pct = raw_gap_pct
        calibrated_gap_pct = None
        final_formula = formula
        final_mode = raw_stats.get("execution_mode", "heuristic_sandbox_proxy")

        if raw_gap_pct <= max(base_gap_pct, DEFAULT_ASR_THRESHOLD):
            refined = symbolic_refine(formula, execution=execution, initial_gap_pct=raw_gap_pct)
            if refined.get("enabled") and refined.get("gap_pct", raw_gap_pct) < raw_gap_pct:
                calibrated_gap_pct = float(refined.get("gap_pct", raw_gap_pct))
                final_mode = f"{final_mode}+{refined.get('method', 'asr')}"
                if refined.get("trusted_refinement"):
                    final_gap_pct = float(refined.get("trusted_gap_pct", calibrated_gap_pct))
                    final_formula = str(refined.get("refined_formula", formula))
                    status = "PERFECTED" if final_gap_pct < DEFAULT_PERFECTED_THRESHOLD else "REFINED"
                else:
                    final_gap_pct = raw_gap_pct
                    final_formula = str(refined.get("structural_formula", formula))
                    status = "CALIBRATED" if raw_gap_pct < survival_threshold else "KILLED"

        if final_gap_pct < survival_threshold and status == "KILLED":
            status = "SURVIVED"

        if final_gap_pct < 1:
            final_fitness = "excellent"
        elif final_gap_pct < 10:
            final_fitness = "strong"
        elif final_gap_pct < 25:
            final_fitness = "promising"
        else:
            final_fitness = "weak"

        enriched = {
            **candidate,
            **raw_stats,
            "raw_gap_pct": raw_gap_pct,
            "gap_pct": round(final_gap_pct, 5),
            "calibrated_gap_pct": round(calibrated_gap_pct, 5) if calibrated_gap_pct is not None else None,
            "formula": final_formula,
            "status": status,
            "fitness": final_fitness,
            "execution_mode": final_mode,
        }
        if refined:
            enriched.update(
                {
                    "refined_formula": refined.get("refined_formula"),
                    "asr_status": refined.get("status"),
                    "asr_method": refined.get("method"),
                    "asr_gap_pct": refined.get("gap_pct"),
                    "parameter_names": refined.get("parameter_names", []),
                    "parameter_values": refined.get("parameter_values", []),
                    "target_y": refined.get("target_y"),
                    "structural_formula": refined.get("structural_formula"),
                    "scale_factor": refined.get("scale_factor"),
                    "trusted_refinement": refined.get("trusted_refinement", False),
                }
            )
        results.append(enriched)

    ranked = sorted(results, key=lambda item: item.get("gap_pct", 999999.0))
    survivors = ranked[: max(1, max_survivors)]
    for survivor in survivors:
        if survivor["status"] not in {"SURVIVED", "REFINED", "PERFECTED", "CALIBRATED"}:
            survivor["status"] = "PROMISING"

    best_gap_pct = survivors[0]["gap_pct"] if survivors else base_gap_pct
    best_formula = survivors[0].get("formula") if survivors else None
    return {
        "execution_mode": "heuristic_sandbox_proxy+asr",
        "base_gap_pct": base_gap_pct,
        "survival_threshold": survival_threshold,
        "results": ranked,
        "survivors": survivors,
        "best_gap_pct": best_gap_pct,
        "best_formula": best_formula,
        "survivor_count": len(survivors),
        "asr_enabled": bool(HAS_SYMPY),
        "scipy_available": bool(HAS_SCIPY),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SIARC swarm gauntlet")
    parser.add_argument("--swarm", required=True, help="Path to swarm JSON")
    parser.add_argument("--execution", help="Optional path to an execution JSON payload from Agent C")
    parser.add_argument("--survivors", type=int, default=DEFAULT_MAX_SURVIVORS, help="How many candidates survive")
    parser.add_argument("--threshold", type=float, default=DEFAULT_SURVIVAL_THRESHOLD, help="Gap threshold for survival")
    args = parser.parse_args()

    swarm = _read_json_file(args.swarm)
    execution = None
    if args.execution:
        payload = _read_json_file(args.execution)
        execution = payload.get("execution", payload)

    report = run_batch_gauntlet(
        swarm=swarm,
        execution=execution,
        max_survivors=max(1, args.survivors),
        survival_threshold=float(args.threshold),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
