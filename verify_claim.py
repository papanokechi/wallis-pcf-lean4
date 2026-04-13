#!/usr/bin/env python3
"""Lightweight runtime verifier for numerical research claims.

The verifier validates a claim JSON payload, re-executes the provided
`reproduce` command in a subprocess, compares the reproduced output against the
claimed raw output, and reports one of:

- VERIFIED
- MISMATCH
- EXECUTION_FAILED
- SCHEMA_INVALID

It is intentionally strict about provenance and evidence class because prompts
alone do not provide meaningful guarantees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

try:
    from mpmath import mp
except Exception as exc:  # pragma: no cover
    sys.exit(f"SCHEMA_INVALID\nmpmath is required to verify numeric claims: {exc}")

mp.dps = 200

VALID_EVIDENCE_CLASSES = {
    "near_miss",
    "numerical_identity",
    "independently_verified",
    "formalized",
}

TEXT_FIELDS = ("narrative", "summary", "claim_text", "report_text", "message")

BANNED_BY_EVIDENCE = {
    "near_miss": [
        "breakthrough",
        "closed form found",
        "closed-form found",
        "proved",
        "proven",
        "theorem",
        "established",
        "exact identity",
    ],
    "numerical_identity": [
        "proved",
        "proven",
        "theorem",
        "formal proof",
        "fully established",
    ],
    "independently_verified": [
        "formalized",
        "machine proved",
        "theorem proved",
    ],
    "formalized": [],
}

SAFE_GLOBALS = {"__builtins__": {}}
SAFE_LOCALS = {"mp": mp}


def _status_exit_code(status: str) -> int:
    return {
        "VERIFIED": 0,
        "MISMATCH": 1,
        "EXECUTION_FAILED": 2,
        "SCHEMA_INVALID": 3,
    }[status]


def _print_result(status: str, details: list[str]) -> None:
    print(status)
    for line in details:
        print(f"- {line}")


def _load_claim(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _coerce_mpf(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        try:
            return mp.mpf(s)
        except Exception:
            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s):
                return mp.mpf(s)
            return None

    try:
        return mp.mpf(value)
    except Exception:
        return None


def _relative_digits(a: Any, b: Any) -> float:
    aa = _coerce_mpf(a)
    bb = _coerce_mpf(b)
    if aa is None or bb is None:
        return -1.0
    err = abs(aa - bb)
    if err == 0:
        return 999999.0
    scale = max(mp.mpf(1), abs(aa), abs(bb))
    return max(0.0, float(-mp.log10(err / scale)))


def _evaluate_target_expr(expr: str) -> Any:
    return eval(expr, SAFE_GLOBALS, SAFE_LOCALS)


def _validate_schema(claim: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(claim, dict):
        return ["Top-level claim object must be a JSON object."]

    required_top = [
        "inputs",
        "raw_output",
        "comparison",
        "reproduce",
        "evidence_class",
        "environment",
        "provenance",
    ]
    for key in required_top:
        if key not in claim:
            issues.append(f"Missing required top-level field: {key}")

    if issues:
        return issues

    inputs = claim["inputs"]
    if not isinstance(inputs, dict):
        issues.append("inputs must be an object")
    else:
        for key in ("function", "args", "precision", "depth"):
            if key not in inputs:
                issues.append(f"inputs.{key} is required")
        if not isinstance(inputs.get("function", ""), str) or not inputs.get("function", "").strip():
            issues.append("inputs.function must be a non-empty string")
        if not isinstance(inputs.get("args", {}), dict):
            issues.append("inputs.args must be an object")

    if not isinstance(claim["reproduce"], str) or not claim["reproduce"].strip():
        issues.append("reproduce must be a non-empty shell command")

    comparison = claim["comparison"]
    if not isinstance(comparison, dict):
        issues.append("comparison must be an object")
    else:
        for key in ("target", "residual", "digits", "threshold", "threshold_met"):
            if key not in comparison:
                issues.append(f"comparison.{key} is required")
        digits = comparison.get("digits")
        threshold = comparison.get("threshold")
        threshold_met = comparison.get("threshold_met")
        if not isinstance(digits, (int, float)):
            issues.append("comparison.digits must be numeric")
        if not isinstance(threshold, (int, float)):
            issues.append("comparison.threshold must be numeric")
        if not isinstance(threshold_met, bool):
            issues.append("comparison.threshold_met must be boolean")
        if isinstance(digits, (int, float)) and isinstance(threshold, (int, float)) and isinstance(threshold_met, bool):
            expected = digits >= threshold
            if expected != threshold_met:
                issues.append(
                    f"comparison.threshold_met={threshold_met} is inconsistent with digits={digits} and threshold={threshold}"
                )

    evidence_class = claim.get("evidence_class")
    if evidence_class not in VALID_EVIDENCE_CLASSES:
        issues.append(
            "evidence_class must be one of: " + ", ".join(sorted(VALID_EVIDENCE_CLASSES))
        )

    env = claim["environment"]
    if not isinstance(env, dict):
        issues.append("environment must be an object")
    else:
        for key in ("python", "git_commit"):
            if key not in env:
                issues.append(f"environment.{key} is required")

    prov = claim["provenance"]
    if not isinstance(prov, dict):
        issues.append("provenance must be an object")
    else:
        for key in ("code_path", "implementation_hash", "timestamp"):
            if key not in prov:
                issues.append(f"provenance.{key} is required")
        code_path_value = str(prov.get("code_path", "")).strip()
        if code_path_value and Path(code_path_value).name == Path(__file__).name:
            issues.append(
                "provenance.code_path must point to the research script under audit, not verify_claim.py"
            )

    narrative_bits = []
    for field in TEXT_FIELDS:
        value = claim.get(field)
        if isinstance(value, str) and value.strip():
            narrative_bits.append(_normalize_text(value))
    joined = " | ".join(narrative_bits)
    if joined and evidence_class in BANNED_BY_EVIDENCE:
        for phrase in BANNED_BY_EVIDENCE[evidence_class]:
            if phrase in joined:
                issues.append(
                    f"Narrative contains banned phrase for evidence_class={evidence_class!r}: {phrase!r}"
                )

    return issues


def _verify_environment(claim: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    env = claim["environment"]

    declared_py = str(env.get("python", "")).strip()
    current_py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if declared_py and not current_py.startswith(declared_py):
        issues.append(f"Python version mismatch: claim={declared_py}, runtime={current_py}")

    declared_mpmath = str(env.get("mpmath", "")).strip()
    if declared_mpmath:
        try:
            installed = version("mpmath")
            if installed != declared_mpmath:
                issues.append(f"mpmath version mismatch: claim={declared_mpmath}, runtime={installed}")
        except PackageNotFoundError:
            issues.append("mpmath is not installed in the current environment")

    git_commit = str(env.get("git_commit", "")).strip()
    if git_commit:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{git_commit}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            issues.append(f"git_commit not found in repository history: {git_commit}")

    return issues


def _verify_provenance(claim: dict[str, Any], claim_path: Path) -> list[str]:
    issues: list[str] = []
    prov = claim["provenance"]
    code_path = Path(prov.get("code_path", ""))
    if not code_path.is_absolute():
        base = claim_path.parent if claim_path.name else Path.cwd()
        code_path = (base / code_path).resolve()

    if not code_path.exists():
        issues.append(f"provenance.code_path does not exist: {code_path}")
        return issues

    declared_hash = str(prov.get("implementation_hash", "")).strip().lower()
    actual_hash = _sha256_file(code_path).lower()
    if declared_hash and not actual_hash.startswith(declared_hash):
        issues.append(
            f"implementation_hash mismatch for {code_path.name}: claim={declared_hash}, actual={actual_hash}"
        )

    ts = str(prov.get("timestamp", "")).strip()
    if ts:
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            issues.append(f"Invalid ISO timestamp in provenance.timestamp: {ts}")

    return issues


def _run_reproduce(command: str, timeout: int) -> tuple[int, str, str]:
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=os.getcwd(),
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _verify_outputs(claim: dict[str, Any], reproduced_stdout: str) -> list[str]:
    issues: list[str] = []
    raw_output = claim["raw_output"]
    raw_text = raw_output if isinstance(raw_output, str) else json.dumps(raw_output, sort_keys=True)
    got_text = reproduced_stdout.strip()

    if _normalize_text(raw_text) != _normalize_text(got_text):
        digits = _relative_digits(raw_text, got_text)
        threshold = float(claim["comparison"]["threshold"])
        if digits < threshold:
            issues.append(
                f"Reproduced stdout does not match raw_output closely enough (matched {digits:.2f} digits, need {threshold:.2f})"
            )

    target_value = claim["comparison"].get("target_value")
    if target_value is not None:
        try:
            target = _evaluate_target_expr(str(target_value))
        except Exception as exc:
            issues.append(f"comparison.target_value is not machine-evaluable: {exc}")
            return issues

        actual_digits = _relative_digits(reproduced_stdout, target)
        claimed_digits = float(claim["comparison"]["digits"])
        threshold = float(claim["comparison"]["threshold"])
        claimed_met = bool(claim["comparison"]["threshold_met"])
        actual_met = actual_digits >= threshold

        if actual_met != claimed_met:
            issues.append(
                f"threshold_met mismatch after replay: claim={claimed_met}, actual={actual_met}, digits={actual_digits:.2f}, threshold={threshold:.2f}"
            )
        if actual_digits + 1e-9 < claimed_digits - 0.5:
            issues.append(
                f"Claimed digits ({claimed_digits:.2f}) exceed replayed digits ({actual_digits:.2f})"
            )

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and replay a numerical claim JSON payload.")
    parser.add_argument("claim", help="Path to the claim JSON file, or '-' to read from stdin")
    parser.add_argument("--timeout", type=int, default=60, help="Subprocess timeout in seconds (default: 60)")
    args = parser.parse_args()

    claim_path = Path(args.claim).resolve() if args.claim != "-" else Path.cwd()

    try:
        claim = _load_claim(args.claim)
    except Exception as exc:
        _print_result("SCHEMA_INVALID", [f"Could not load JSON claim: {exc}"])
        raise SystemExit(_status_exit_code("SCHEMA_INVALID"))

    schema_issues = _validate_schema(claim)
    if schema_issues:
        _print_result("SCHEMA_INVALID", schema_issues)
        raise SystemExit(_status_exit_code("SCHEMA_INVALID"))

    env_issues = _verify_environment(claim)
    prov_issues = _verify_provenance(claim, claim_path)
    if env_issues or prov_issues:
        _print_result("MISMATCH", env_issues + prov_issues)
        raise SystemExit(_status_exit_code("MISMATCH"))

    try:
        returncode, stdout, stderr = _run_reproduce(claim["reproduce"], timeout=args.timeout)
    except subprocess.TimeoutExpired:
        _print_result("EXECUTION_FAILED", [f"Reproduce command exceeded {args.timeout} seconds"])
        raise SystemExit(_status_exit_code("EXECUTION_FAILED"))
    except Exception as exc:
        _print_result("EXECUTION_FAILED", [f"Could not execute reproduce command: {exc}"])
        raise SystemExit(_status_exit_code("EXECUTION_FAILED"))

    if returncode != 0:
        details = [f"Reproduce command exited with code {returncode}"]
        if stderr:
            details.append(f"stderr: {stderr}")
        _print_result("EXECUTION_FAILED", details)
        raise SystemExit(_status_exit_code("EXECUTION_FAILED"))

    output_issues = _verify_outputs(claim, stdout)
    if output_issues:
        _print_result("MISMATCH", output_issues)
        raise SystemExit(_status_exit_code("MISMATCH"))

    _print_result(
        "VERIFIED",
        [
            f"evidence_class={claim['evidence_class']}",
            f"git_commit={claim['environment'].get('git_commit', '')}",
            f"code_path={claim['provenance'].get('code_path', '')}",
        ],
    )
    raise SystemExit(_status_exit_code("VERIFIED"))


if __name__ == "__main__":
    main()
