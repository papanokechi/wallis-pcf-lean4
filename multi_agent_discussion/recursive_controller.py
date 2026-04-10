from __future__ import annotations

"""Recursive controller utilities for SIARC debate transcripts.

This reads a debate transcript JSON, extracts the latest Lethal Flaw Index (LFI),
and returns the next controller action:
- TRIGGER_REFACTOR
- TRIGGER_PERTURBATION
- PROCEED_TO_JUDGE

Usage:
    py multi_agent_discussion/recursive_controller.py --transcript multi_agent_discussion/runs/debate_20260331_055629.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _read_json_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return json.loads(p.read_text(encoding=encoding))
        except (UnicodeError, json.JSONDecodeError):
            continue
    return json.loads(p.read_bytes().decode("utf-8", errors="replace"))


def _extract_score_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    patterns = [
        r"SCORE_JSON\s*:\s*(\{.*?\})",
        r"(\{\s*\"N\"\s*:\s*.*?\})",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        for blob in reversed(matches):
            try:
                return json.loads(blob)
            except Exception:
                continue
    return {}


def generate_meta_directive(lfi_score: float, gap_pct: float | None = None) -> str:
    if lfi_score > 0.8:
        return "SYSTEM_PROMPT_INJECTION: Strategist must abandon current pole-structure and re-derive from first principles."
    if lfi_score > 0.7:
        return "SYSTEM_PROMPT_INJECTION: Strategist must rewrite the claim with explicit falsification tests and a cleaner evidence chain."
    if lfi_score > 0.3:
        if gap_pct is not None and gap_pct > 10:
            return "TRIGGER symbolic_regression / coefficient perturbation and keep only variants with gap_pct <= 10%."
        return "TRIGGER one more perturbation / verification pass before judge review."
    return "PROCEED_TO_JUDGE"


def autonomous_loop_controller(transcript_path: str) -> dict[str, Any]:
    path = Path(transcript_path)
    data = _read_json_file(path)

    rounds = data.get("rounds") or data.get("history") or []
    latest_round = rounds[-1] if rounds else {}
    latest_feedback = ""

    if isinstance(latest_round, dict):
        red_team_output = latest_round.get("red_team_output")
        if isinstance(red_team_output, dict):
            lfi_score = float(red_team_output.get("LFI", 1.0))
        else:
            latest_feedback = latest_round.get("critic_feedback", "") or str(red_team_output or "")
            parsed = _extract_score_json(latest_feedback)
            lfi_score = float(parsed.get("LFI", 1.0)) if parsed else 1.0
    else:
        lfi_score = 1.0

    gap_pct = None
    task_blob = data.get("task", "")
    best_gap_match = re.search(r"best_swarm_gap_pct:\s*([0-9.]+)", task_blob, flags=re.IGNORECASE)
    gap_match = re.search(r"gap_pct:\s*([0-9.]+)", task_blob, flags=re.IGNORECASE)
    if best_gap_match:
        gap_pct = float(best_gap_match.group(1))
    elif gap_match:
        gap_pct = float(gap_match.group(1))

    if lfi_score > 0.7:
        action = "TRIGGER_REFACTOR"
    elif 0.3 < lfi_score <= 0.7:
        action = "TRIGGER_PERTURBATION"
    else:
        action = "PROCEED_TO_JUDGE"

    meta_directive = generate_meta_directive(lfi_score, gap_pct=gap_pct)
    result = {
        "transcript_path": str(path.resolve()),
        "latest_lfi": lfi_score,
        "gap_pct": gap_pct,
        "action": action,
        "meta_directive": meta_directive,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Recursive controller for SIARC debate transcripts")
    parser.add_argument("--transcript", required=True, help="Path to debate transcript JSON")
    args = parser.parse_args()

    result = autonomous_loop_controller(args.transcript)
    print("--- Current Meta-Iteration Status ---")
    print(f"Transcript: {result['transcript_path']}")
    print(f"Latest LFI: {result['latest_lfi']:.3f}")
    if result["gap_pct"] is not None:
        print(f"Gap pct:    {result['gap_pct']:.3f}")
    print(f"Action:     {result['action']}")
    print(f"Directive:  {result['meta_directive']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
