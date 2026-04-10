#!/usr/bin/env python3
from __future__ import annotations

"""Prompt architecture for the SIARC Control Center.

This module provides the overseer, field-agent, and judge prompts used by the
browser command center. It is local-first: CTRL-01 can generate complete mission
briefs inside this workspace with no API key required.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
import re
import textwrap
from typing import Any


SUGGESTED_PATHS: dict[str, str] = {
    "controller": "multi_agent_discussion/controller.py",
    "siarc_adapter": "multi_agent_discussion/siarc_adapter.py",
    "gauntlet": "multi_agent_discussion/gauntlet.py",
    "main_runner": "siarc.py",
    "agent_d_output": "siarc_outputs/agent_D_out.json",
    "agent_j_output": "siarc_outputs/agent_J_out.json",
    "self_correction_log": "multi_agent_discussion/self_correction_log.json",
    "formal_report": "breakthroughs/H-0025_Final.md",
    "epoch5_state": "epoch5_state.json",
    "lemma_k_prompt": "lemma_k_relay_prompt.md",
    "agent3_verifier": "agent3_lemma_k_verifier.py",
}


CTRL_SYSTEM_PROMPT = textwrap.dedent(
    """
    You are CTRL-01, the SIARC mission overseer.

    Your job is to receive a research challenge, convert it into a disciplined
    field-agent brief, route the work through the SIARC pipeline, and halt any
    mission that is still relying on dry-run evidence.

    Output requirements:
    1. Produce a concise mission summary.
    2. Specify the domain, success metric, swarm size, ASR threshold, and red-team focus.
    3. Include the exact repository paths the field agent should inspect first.
    4. If any artifact is still synthetic or marked with "[DRY RUN]", explicitly set
       validation_mode = "provisional" and instruct the agent to stop and replace
       the dry-run evidence before claiming success.
    5. Route the mission through: Swarm -> Gauntlet -> ASR -> PSLQ -> Judge -> Report.

    Return structured JSON with keys:
    mission_id, topic, domain, success_metric, validation_mode, red_team_focus,
    suggested_paths, launch_brief.
    """
).strip()


FIELD_AGENT_SEED_TEMPLATE = textwrap.dedent(
    """
    # FIELD AGENT MISSION BRIEF

    Mission ID: {mission_id}
    Topic: {topic}
    Domain: {domain}
    Validation mode: {validation_mode}
    Swarm size: {swarm_size}
    ASR threshold: {asr_threshold}
    Seed formula / starting hypothesis: {seed_formula}

    ## Suggested paths to inspect first
    - `{controller}`
    - `{siarc_adapter}`
    - `{gauntlet}`
    - `{main_runner}`
    - `{agent_d_output}`
    - `{agent_j_output}`
    - `{self_correction_log}`
    - `{formal_report}`
    - `{epoch5_state}`
    - `{lemma_k_prompt}`
    - `{agent3_verifier}`

    ## Mission objective
    {mission_objective}

    ## Required workflow
    1. **Swarm**
       - Generate diverse candidates around the current hypothesis.
       - Keep at least one conservative mutation and one adversarial mutation.
    2. **Gauntlet**
       - Score each candidate by numeric gap, LFI, stability, and cross-seed consistency.
       - Reject any candidate that only improves through an untrusted outer scalar wrapper.
    3. **ASR**
       - Refine only the internal structure of the formula.
       - If the best result depends on a scale far from ±1, report `CALIBRATED`, not `PERFECTED`.
    4. **PSLQ / symbolic recovery**
       - Re-run at higher precision before proposing exact constants.
       - Prefer small, interpretable relations over giant rational noise.
    5. **Judge / report**
       - Send only live-validated survivors to JUDGE-01.
       - If any artifact contains `[DRY RUN]`, stop immediately with verdict `DRY_RUN_DETECTED`.

    ## Red-team requirements
    - Explain the strongest failure mode.
    - Test 10 seed windows or 10 randomized restarts where applicable.
    - Quantify the best gap, median gap, and pass rate.
    - Explain any alpha/beta discrepancy instead of silently absorbing it into calibration.
    - For proof-relay missions, force a 5-step cascade (multiplier system → CRT reduction → Weil/spectral bound → error term → generalisation).
    - After every proof step, report `GAP:` and `SEVERITY: blocks|partial|cosmetic` instead of papering over missing justifications.
    - End any Lemma K proof packet with `BATON TO AGENT 3:` and hand off the numeric check to `agent3_lemma_k_verifier.py`.

    ## Memory loading
    Before proposing a breakthrough, load recent notes from:
    - `multi_agent_discussion/self_correction_log.json`
    - `siarc_outputs/agent_D_out.json`
    - `siarc_outputs/agent_J_out.json`
    - `breakthroughs/H-0025_Final.md`

    ## Termination conditions
    - `REPORT_READY`: live evidence, low LFI, stable across seeds, no dry-run contamination.
    - `REVISE_AND_REPEAT`: promising numeric fit but still unstable or structurally unclear.
    - `DRY_RUN_DETECTED`: any synthetic or mocked judge/debate evidence remains.
    - `RED_TEAM_BLOCK`: a lethal flaw survives critique.
    - `FORMAL_PROOF_PENDING`: numerics hold, but symbolic proof is incomplete.

    ## Deliverable format
    Return:
    1. concise mission log
    2. surviving candidate formulas / hypotheses
    3. evidence table with gap/LFI/seed robustness
    4. exact recommendation for CTRL-01 and JUDGE-01
    """
).strip()


JUDGE_SYSTEM_PROMPT = textwrap.dedent(
    """
    You are JUDGE-01, the publication gate for SIARC.

    Evaluate only the evidence presented. Do not reward aesthetic formulas that
    depend on fragile calibration or dry-run scoring.

    Allowed verdicts:
    - APPROVE_FOR_REPORT
    - REVISE_AND_REPEAT
    - RED_TEAM_BLOCK
    - DRY_RUN_DETECTED
    - FORMAL_PROOF_PENDING

    Mandatory checks:
    1. Was the evidence produced with live execution rather than dry-run simulation?
    2. Is the best-fit formula structurally meaningful without a suspicious outer scale factor?
    3. Are the PSLQ relations small, interpretable, and stable under higher precision?
    4. Does multi-seed robustness support the claimed result?
    5. Is the LFI low enough to justify publication language?

    Return JSON with keys:
    verdict, rationale, required_fixes, publishable_claim, blockers.
    """
).strip()


LEMMA_K_RELAY_PROMPT = textwrap.dedent(
    """
    You are preparing a derivation-grade proof relay packet for the `k >= 5` frontier in Paper 14, starting with `k = 5`.

    Rules:
    - Do NOT claim the theorem is fully proved unless every step closes.
    - After every step, append `GAP: ...` and `SEVERITY: blocks|partial|cosmetic`.
    - If a step is incomplete, stop the proof chain there rather than papering it over.

    Required 5-step cascade:
    1. Multiplier system for `eta(tau)^(-k)` and conductor `N_k = 24/gcd(k,24)`.
    2. CRT / local reduction, isolating the `2`-adic quintic obstruction for `k = 5`.
    3. Weil / Petersson / Goldfeld-Sarnak type Kloosterman control with explicit dependence on `k`.
    4. Error-term insertion into the circle-method / Rademacher tail.
    5. Generalisation from `k = 5` to the full `k >= 5` lane.

    Reference anchors to use explicitly if they justify a step:
    - Petersson
    - Weil
    - Goldfeld-Sarnak

    End with the exact header `BATON TO AGENT 3:` and hand off the conductor formula,
    sample `(m,n,c)` cases, and bound shape for the local zero-API checker.
    """
).strip()


def build_lemma_k_relay_packet() -> dict[str, Any]:
    return {
        "relay_prompt": LEMMA_K_RELAY_PROMPT,
        "relay_prompt_path": SUGGESTED_PATHS["lemma_k_prompt"],
        "agent3_verifier_path": SUGGESTED_PATHS["agent3_verifier"],
        "handoff_contract": "End with `BATON TO AGENT 3:` and report unresolved proof issues via `GAP:` / `SEVERITY:`.",
    }


@dataclass(slots=True)
class MissionSpec:
    topic: str
    domain: str = "general"
    swarm_size: int = 8
    asr_threshold: float = 1.0e-4
    seed_formula: str = "None provided"
    validation_mode: str = "local_workspace"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def make_mission_id(topic: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", (topic or "mission").strip()).strip("-").upper()
    stem = stem[:24] or "MISSION"
    return f"{stem}-{_utc_now()}"


def infer_domain(topic: str, requested_domain: str | None = None) -> str:
    if requested_domain and requested_domain.strip() and requested_domain.lower() != "auto":
        return requested_domain.strip()
    text = (topic or "").lower()
    if "prime" in text or "lucas" in text:
        return "prime-search"
    if "pslq" in text or "constant" in text:
        return "symbolic-recovery"
    if "proof" in text or "identity" in text:
        return "formal-verification"
    if "physics" in text or "bridge" in text:
        return "physics-bridge"
    return "general-research"


def mission_objective(topic: str, domain: str) -> str:
    text = (topic or "").lower()
    if any(key in text for key in ("lemma k", "kloosterman", "proof", "derivation")):
        return (
            f"Investigate the topic '{topic}' in the domain '{domain}' as a proof-relay mission. "
            "Force the 5-step cascade (multiplier system -> CRT reduction -> Weil/spectral bound -> error term -> generalisation), "
            "and mark every unresolved issue with `GAP:` and `SEVERITY:` instead of claiming a finished proof too early."
        )
    return (
        f"Investigate the topic '{topic}' in the domain '{domain}', route it through the full SIARC "
        "pipeline, and return only claims that survive numeric checking, red-team pressure, and judge review."
    )


def render_field_agent_seed(
    topic: str,
    domain: str = "general",
    swarm_size: int = 8,
    asr_threshold: float = 1.0e-4,
    seed_formula: str | None = None,
    validation_mode: str = "provisional",
    mission_id: str | None = None,
    suggested_paths: dict[str, str] | None = None,
) -> str:
    spec = MissionSpec(
        topic=topic.strip() or "Untitled mission",
        domain=infer_domain(topic, domain),
        swarm_size=max(2, int(swarm_size)),
        asr_threshold=float(asr_threshold),
        seed_formula=(seed_formula or "None provided").strip() or "None provided",
        validation_mode=validation_mode,
    )
    mission_id = mission_id or make_mission_id(spec.topic)
    paths = {**SUGGESTED_PATHS, **(suggested_paths or {})}
    return FIELD_AGENT_SEED_TEMPLATE.format(
        mission_id=mission_id,
        topic=spec.topic,
        domain=spec.domain,
        validation_mode=spec.validation_mode,
        swarm_size=spec.swarm_size,
        asr_threshold=f"{spec.asr_threshold:.6g}",
        seed_formula=spec.seed_formula,
        mission_objective=mission_objective(spec.topic, spec.domain),
        **paths,
    )


def build_deployment_packet(
    topic: str,
    domain: str = "auto",
    swarm_size: int = 8,
    asr_threshold: float = 1.0e-4,
    seed_formula: str | None = None,
    validation_mode: str = "local_workspace",
) -> dict[str, Any]:
    resolved_domain = infer_domain(topic, domain)
    mission_id = make_mission_id(topic)
    brief = {
        "mission_id": mission_id,
        "topic": topic,
        "domain": resolved_domain,
        "success_metric": "low gap, low LFI, stable across 10 seeds, no dry-run contamination",
        "validation_mode": validation_mode,
        "red_team_focus": [
            "dry-run detection",
            "outer-scalar audit",
            "multi-seed robustness",
            "small-relation PSLQ only",
        ],
        "suggested_paths": SUGGESTED_PATHS,
    }
    seed_prompt = render_field_agent_seed(
        topic=topic,
        domain=resolved_domain,
        swarm_size=swarm_size,
        asr_threshold=asr_threshold,
        seed_formula=seed_formula,
        validation_mode=validation_mode,
        mission_id=mission_id,
    )
    packet = {
        "brief": brief,
        "seed_prompt": seed_prompt,
        "ctrl_system_prompt": CTRL_SYSTEM_PROMPT,
        "judge_system_prompt": JUDGE_SYSTEM_PROMPT,
    }
    if any(key in (topic or "").lower() for key in ("lemma k", "kloosterman", "proof", "derivation")):
        packet["proof_relay_packet"] = build_lemma_k_relay_packet()
    return packet


PRIME_MISSION_SEED = render_field_agent_seed(
    topic="search for next largest prime number",
    domain="prime-search",
    swarm_size=12,
    asr_threshold=1.0e-6,
    seed_formula="Treat the hypothesis as an exponent-search policy for M_p = 2^p - 1 and validate candidates with Lucas–Lehmer rather than symbolic curve fitting.",
    validation_mode="local_workspace",
    mission_id="PRIME-MISSION-DEMO",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SIARC field-agent prompt packets")
    parser.add_argument("--topic", default="search for next largest prime number", help="Mission topic")
    parser.add_argument("--domain", default="auto", help="Mission domain or 'auto'")
    parser.add_argument("--swarm-size", type=int, default=8, help="Swarm size")
    parser.add_argument("--asr-threshold", type=float, default=1.0e-4, help="ASR threshold")
    parser.add_argument("--seed-formula", default="", help="Optional starting hypothesis")
    parser.add_argument("--json", action="store_true", help="Print full deployment packet as JSON")
    args = parser.parse_args()

    packet = build_deployment_packet(
        topic=args.topic,
        domain=args.domain,
        swarm_size=args.swarm_size,
        asr_threshold=args.asr_threshold,
        seed_formula=args.seed_formula,
    )

    if args.json:
        print(json.dumps(packet, indent=2, ensure_ascii=False))
    else:
        print(packet["seed_prompt"])


if __name__ == "__main__":
    main()
