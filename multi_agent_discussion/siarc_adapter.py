from __future__ import annotations

"""SIARC integration helpers for the multi-agent debate controller.

This module adds an optional red-team / debate-driven critic for `siarc.py`
Agent D. It reuses the generic `DebateController`, records a lightweight
self-correction memory log, and maps the result back into the evaluation
schema SIARC already expects.
"""

import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from multi_agent_discussion.controller import AgentConfig, DebateController, DEFAULT_CONVERGENCE_THRESHOLD
from multi_agent_discussion.gauntlet import run_batch_gauntlet
from multi_agent_discussion.swarm_generator import DEFAULT_SWARM_SIZE, generate_mutation_swarm

ROOT = Path(__file__).resolve().parents[1]
SELF_CORRECTION_LOG_PATH = ROOT / "multi_agent_discussion" / "self_correction_log.json"


@dataclass
class DebateCriticConfig:
    """Configuration for SIARC's debate-based Agent D critic."""

    dry_run: bool = True
    with_judge: bool = False
    max_iter: int = 3
    convergence_threshold: float = DEFAULT_CONVERGENCE_THRESHOLD
    strategist_provider: str = "openai"
    critic_provider: str = "anthropic"
    strategist_model: str = "gpt-4o"
    critic_model: str = "claude-opus-4-5"
    judge_provider: str = "anthropic"
    lfi_refactor_threshold: float = 0.70
    lfi_judge_threshold: float = 0.20
    swarm_mode: bool = True
    swarm_size: int = DEFAULT_SWARM_SIZE
    swarm_survivors: int = 2

    @classmethod
    def from_env(cls) -> "DebateCriticConfig":
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        strategist_provider = os.environ.get("SIARC_STRATEGIST_PROVIDER", "").strip().lower()
        critic_provider = os.environ.get("SIARC_CRITIC_PROVIDER", "").strip().lower()
        if not strategist_provider:
            strategist_provider = "openai" if openai_key else ("anthropic" if anthropic_key else "openai")
        if not critic_provider:
            critic_provider = "anthropic" if anthropic_key else ("openai" if openai_key else "anthropic")
        judge_provider = os.environ.get("SIARC_JUDGE_PROVIDER", critic_provider).strip().lower() or critic_provider
        return cls(
            dry_run=os.environ.get("SIARC_DEBATE_DRY_RUN", "1") != "0",
            with_judge=os.environ.get("SIARC_DEBATE_JUDGE", "0") == "1",
            max_iter=int(os.environ.get("SIARC_DEBATE_ITERATIONS", "3")),
            convergence_threshold=float(os.environ.get("SIARC_DEBATE_CONVERGENCE", str(DEFAULT_CONVERGENCE_THRESHOLD))),
            strategist_provider=strategist_provider,
            critic_provider=critic_provider,
            strategist_model=os.environ.get("SIARC_OPENAI_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o")),
            critic_model=os.environ.get("SIARC_ANTHROPIC_MODEL", os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5")),
            judge_provider=judge_provider,
            lfi_refactor_threshold=float(os.environ.get("SIARC_LFI_REFACTOR_THRESHOLD", "0.70")),
            lfi_judge_threshold=float(os.environ.get("SIARC_LFI_JUDGE_THRESHOLD", "0.20")),
            swarm_mode=os.environ.get("SIARC_SWARM_MODE", "1") != "0",
            swarm_size=int(os.environ.get("SIARC_SWARM_SIZE", str(DEFAULT_SWARM_SIZE))),
            swarm_survivors=int(os.environ.get("SIARC_SWARM_SURVIVORS", "2")),
        )


class AgentDDebate:
    """Red-team / debate-driven evaluator for SIARC Agent D.

    The Strategist defends or narrows the mathematical hypothesis using the
    execution evidence, while the Critic acts as "The Skeptic" and attempts
    to falsify it. The output includes standard N/F/E/C scores plus a
    Lethal Flaw Index (LFI) and a controller action for the next iteration.
    """

    def __init__(self, config: Optional[DebateCriticConfig] = None):
        self.config = config or DebateCriticConfig.from_env()

    @staticmethod
    def _clamp(value: float, lo: float = 0.05, hi: float = 0.99) -> float:
        return max(lo, min(hi, round(float(value), 3)))

    @staticmethod
    def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
        try:
            return float(value)
        except Exception:
            return default

    def _strategist_system(self) -> str:
        return textwrap.dedent(
            """
            Role: You are a Lead Research Architect specialized in Recursive Evolutionary Discovery.

            Core objective:
            - Do not cling to a single formula.
            - Use the prior self-correction memory and any swarm-survivor data to identify
              the best surviving structure and explain how it should evolve next.
            - If the prior LFI is above 0.5, prefer structural rewrites over cosmetic edits.

            Output sections:
            1. Revised claim or best survivor
            2. Why the evidence does or does not support it
            3. What would falsify it next
            """
        ).strip()

    def _critic_system(self) -> str:
        return textwrap.dedent(
            """
            Role: You are "The Skeptic" - a senior formal verifier and adversarial mathematician.
            Your sole objective is to falsify the hypothesis provided by the Strategist.
            Do not be polite. Identify lethal flaws, hidden assumptions, structural mismatches,
            and numerical inconsistencies.

            Attack directives:
            1. Check dimensional / structural consistency and whether the formula contains suspect pole terms.
            2. Audit the actual execution evidence; skipped tools weaken the claim.
            3. Challenge precision claims if the reported numeric gap is still large.
            4. Prefer simpler explanations over curve-fit complexity.

            Output requirements:
            1. Strengths
            2. Lethal flaws (3 bullets if possible)
            3. Formal or numeric weaknesses
            4. What stronger evidence is required
            5. A final single-line JSON object beginning with SCORE_JSON:
               {"N": 0.0, "F": 0.0, "E": 0.0, "C": 0.0, "LFI": 0.0,
                "verdict": "failure|inconclusive|progress|breakthrough",
                "critique_summary": "..."}

            LFI = Lethal Flaw Index, from 0.0 (bulletproof) to 1.0 (complete hallucination).
            Keep all scores between 0 and 1.
            """
        ).strip()

    def _judge_system(self) -> str:
        return textwrap.dedent(
            """
            You are the final SIARC judge.
            Review the debate history and decide whether the hypothesis deserves
            a failure, inconclusive, progress, or breakthrough verdict.
            Prefer caution over hype.
            """
        ).strip()

    def _load_self_correction_memory(self, hypothesis: dict) -> list[dict[str, Any]]:
        if not SELF_CORRECTION_LOG_PATH.exists():
            return []
        try:
            data = json.loads(SELF_CORRECTION_LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, list):
            return []

        gap_id = hypothesis.get("gap_id", "")
        relevant = [
            item for item in data
            if item.get("gap_id") == gap_id or item.get("verdict") in {"progress", "breakthrough"}
        ]
        return relevant[-5:]

    def _format_self_correction_memory(self, memory_entries: list[dict[str, Any]]) -> str:
        if not memory_entries:
            return "- No prior self-correction memory yet."

        lines = []
        for item in memory_entries[-3:]:
            lfi = item.get("lfi")
            lfi_text = f"{float(lfi):.2f}" if lfi is not None else "n/a"
            lines.append(
                f"- {item.get('timestamp_utc', '?')}: verdict={item.get('verdict', '?')}, "
                f"LFI={lfi_text}, directive={item.get('controller_action', 'n/a')}, "
                f"note={item.get('critique_summary', '')[:140]}"
            )
        return "\n".join(lines)

    def _run_swarm_gauntlet(
        self,
        hypothesis: dict,
        execution: dict,
        memory_entries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.config.swarm_mode:
            return {}

        prior_lfi = None
        for item in reversed(memory_entries):
            if item.get("lfi") is not None:
                prior_lfi = float(item["lfi"])
                break

        generation = 1
        if memory_entries:
            generation = max(1, len([m for m in memory_entries if m.get("gap_id") == hypothesis.get("gap_id")]) + 1)

        swarm = generate_mutation_swarm(
            base_hypothesis=hypothesis,
            swarm_size=max(2, int(self.config.swarm_size)),
            generation=generation,
            prior_lfi=prior_lfi,
        )
        gauntlet = run_batch_gauntlet(
            swarm=swarm,
            execution=execution,
            max_survivors=max(1, int(self.config.swarm_survivors)),
        )
        return {
            **swarm,
            **gauntlet,
        }

    @staticmethod
    def _format_swarm_report(swarm_report: dict[str, Any]) -> str:
        if not swarm_report:
            return "- Swarm mode disabled."

        survivors = swarm_report.get("survivors", [])
        lines = [
            f"- swarm_id: {swarm_report.get('swarm_id', '?')}",
            f"- generation: {swarm_report.get('generation', '?')}",
            f"- base_gap_pct: {swarm_report.get('base_gap_pct', 'n/a')}",
            f"- best_swarm_gap_pct: {swarm_report.get('best_gap_pct', 'n/a')}",
            f"- survivor_count: {len(survivors)} / {len(swarm_report.get('results', []))}",
        ]
        if swarm_report.get("best_formula"):
            lines.append(f"- best_formula: {swarm_report.get('best_formula')}")
        for item in survivors[:2]:
            formula = item.get("refined_formula") or item.get("formula")
            lines.append(
                f"  * {item.get('id')}: gap_pct={item.get('gap_pct')}, status={item.get('status')}, "
                f"kind={item.get('mutation_kind')}, tool={item.get('tool_strategy')}, formula={formula}"
            )
            if item.get("asr_method"):
                lines.append(
                    f"    ASR: method={item.get('asr_method')}, raw_gap={item.get('raw_gap_pct')}, "
                    f"refined_gap={item.get('gap_pct')}"
                )
        return "\n".join(lines)

    @staticmethod
    def _extract_gap_pct(execution: dict) -> Optional[float]:
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
        return None

    def _build_task_prompt(
        self,
        hypothesis: dict,
        execution: dict,
        memory_entries: Optional[list[dict[str, Any]]] = None,
        swarm_report: Optional[dict[str, Any]] = None,
    ) -> str:
        tool_results = execution.get("tool_results", {})
        tool_result_text = json.dumps(tool_results, indent=2, ensure_ascii=False, default=str)
        gap_pct = self._extract_gap_pct(execution)
        gap_line = f"- gap_pct: {gap_pct:.6f}" if gap_pct is not None else "- gap_pct: unavailable"
        memory_text = self._format_self_correction_memory(memory_entries or [])
        swarm_text = self._format_swarm_report(swarm_report or {})
        return textwrap.dedent(
            f"""
            Evaluate this SIARC mathematical hypothesis.

            Hypothesis ID: {hypothesis.get('id', 'unknown')}
            Gap ID: {hypothesis.get('gap_id', 'unknown')}
            Claim: {hypothesis.get('claim', '')}
            Mechanism: {hypothesis.get('mechanism', '')}
            Testable prediction: {hypothesis.get('testable_prediction', '')}
            Failure condition: {hypothesis.get('failure_condition', '')}
            Tools used: {', '.join(hypothesis.get('tools_needed', []))}
            Confidence: {hypothesis.get('confidence', 0)}

            Execution summary:
            - success: {execution.get('success', False)}
            - digits_matched: {execution.get('digits_matched', 0)}
            - proof_status: {execution.get('proof_status', 'none')}
            - wall_time_seconds: {execution.get('wall_time_seconds', 0)}
            {gap_line}

            Prior self-correction memory:
            {memory_text}

            Swarm search results:
            {swarm_text}

            Tool evidence:
            {tool_result_text}

            Requirements:
            - Attempt to falsify the claim if possible.
            - If the claim is too broad, narrow it precisely.
            - Focus on mathematical rigor, verification quality, and missing edge cases.
            - If the numeric gap remains large or a proof tool was skipped, say so explicitly.
            - Use the swarm summary to identify the strongest surviving branches.
            - Produce an honest SIARC-ready evaluation.
            """
        ).strip()

    def _extract_score_json(self, text: str) -> dict[str, Any]:
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
                    data = json.loads(blob)
                    if all(key in data for key in ("N", "F", "E", "C")):
                        return data
                except Exception:
                    continue
        return {}

    def _derive_scores(self, parsed: dict[str, Any], hypothesis: dict, execution: dict, critique_text: str) -> dict[str, float]:
        success = bool(execution.get("success", False))
        digits = max(0, int(execution.get("digits_matched", 0) or 0))
        claim = (hypothesis.get("claim", "") or "").lower()
        mechanism = (hypothesis.get("mechanism", "") or "").lower()
        failure_condition = (hypothesis.get("failure_condition", "") or "").lower()
        critique = (critique_text or "").lower()

        scores = {
            "N": self._safe_float(parsed.get("N"), 0.50 if success else 0.35),
            "F": self._safe_float(parsed.get("F"), 0.68 if failure_condition else 0.45),
            "E": self._safe_float(parsed.get("E"), min(0.92, 0.30 + (0.30 if success else 0.0) + min(0.25, digits * 0.02))),
            "C": self._safe_float(parsed.get("C"), 0.55 if mechanism else 0.42),
        }

        if "known" in critique or "not novel" in critique:
            scores["N"] -= 0.12
        if any(token in claim for token in ("new", "novel", "unknown", "universality")):
            scores["N"] += 0.05

        if "not falsifiable" in critique or "unfalsifiable" in critique:
            scores["F"] -= 0.20
        if failure_condition:
            scores["F"] += 0.06

        if any(token in critique for token in ("weak evidence", "insufficient evidence", "does not verify", "verification gap", "hallucinated convergence")):
            scores["E"] -= 0.16
        if any(token in critique for token in ("well-supported", "strong evidence", "numeric support")):
            scores["E"] += 0.08

        if any(token in critique for token in ("inconsistent", "contradiction", "imprecise", "underspecified", "vague", "dimensional violation")):
            scores["C"] -= 0.15
        if any(token in critique for token in ("precise", "coherent", "consistent")):
            scores["C"] += 0.07

        return {key: self._clamp(value) for key, value in scores.items()}

    def _derive_lfi(
        self,
        parsed: dict[str, Any],
        hypothesis: dict,
        execution: dict,
        critique_text: str,
        swarm_report: Optional[dict[str, Any]] = None,
    ) -> float:
        parsed_lfi = self._safe_float(parsed.get("LFI"), None)
        if parsed_lfi is not None:
            if swarm_report and swarm_report.get("best_gap_pct") is not None:
                try:
                    best_swarm_gap = float(swarm_report.get("best_gap_pct"))
                    if best_swarm_gap < 0.001:
                        parsed_lfi -= 0.30
                    elif best_swarm_gap < 1:
                        parsed_lfi -= 0.16
                except Exception:
                    pass
            return self._clamp(parsed_lfi, 0.0, 1.0)

        success = bool(execution.get("success", False))
        digits = max(0, int(execution.get("digits_matched", 0) or 0))
        critique = (critique_text or "").lower()
        claim = (hypothesis.get("claim", "") or "").lower()
        gap_pct = self._extract_gap_pct(execution)
        tool_results = execution.get("tool_results", {})
        best_swarm_gap = None
        if swarm_report and swarm_report.get("best_gap_pct") is not None:
            try:
                best_swarm_gap = float(swarm_report.get("best_gap_pct"))
            except Exception:
                best_swarm_gap = None
        if best_swarm_gap is not None:
            gap_pct = min(float(gap_pct if gap_pct is not None else 1e9), best_swarm_gap)

        lfi = 0.72 if not success else 0.54
        lfi -= min(0.18, digits * 0.01)

        if gap_pct is not None:
            if gap_pct > 90:
                lfi += 0.24
            elif gap_pct > 10:
                lfi += 0.14
            elif gap_pct > 1:
                lfi += 0.05
            else:
                lfi -= 0.12

        if isinstance(tool_results.get("pslq_search"), dict) and tool_results["pslq_search"].get("skipped"):
            lfi += 0.08
        if isinstance(tool_results.get("symbolic_verify"), dict) and tool_results["symbolic_verify"].get("skipped"):
            lfi += 0.08

        if any(token in critique for token in ("hallucinated convergence", "structurally invalid", "dimensional violation", "contradiction")):
            lfi += 0.12
        if any(token in critique for token in ("well-supported", "strong evidence", "precise", "consistent")):
            lfi -= 0.10

        if any(token in claim for token in ("/c₅", "/c5", "1/c", "1 / c")):
            lfi += 0.06

        if best_swarm_gap is not None:
            if best_swarm_gap < 0.001:
                lfi -= 0.22
            elif best_swarm_gap < 1:
                lfi -= 0.14
            elif best_swarm_gap < 10:
                lfi -= 0.06

        return self._clamp(lfi, 0.0, 1.0)

    def _collect_lethal_flaws(
        self,
        hypothesis: dict,
        execution: dict,
        critique_text: str,
        swarm_report: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        flaws: list[str] = []
        tool_results = execution.get("tool_results", {})
        gap_pct = self._extract_gap_pct(execution)
        claim = hypothesis.get("claim", "") or ""
        best_swarm_gap = None
        if swarm_report and swarm_report.get("best_gap_pct") is not None:
            try:
                best_swarm_gap = float(swarm_report.get("best_gap_pct"))
            except Exception:
                best_swarm_gap = None

        if best_swarm_gap is not None and best_swarm_gap < 10:
            flaws.append(f"Swarm survivor improved local fit to gap_pct={best_swarm_gap:.5f}; independent verification is still required.")
        elif gap_pct is not None and gap_pct > 10:
            flaws.append(f"Numeric mismatch remains large: gap_pct={gap_pct:.2f}%.")

        if isinstance(tool_results.get("pslq_search"), dict) and tool_results["pslq_search"].get("skipped"):
            flaws.append("`pslq_search` was skipped, so the claimed relation remains unanchored to a symbolic constant search.")

        if isinstance(tool_results.get("symbolic_verify"), dict) and tool_results["symbolic_verify"].get("skipped"):
            flaws.append("`symbolic_verify` was skipped, so no formal proof layer validated the claim.")

        if any(token in claim.lower() for token in ("/c₅", "/c5", "1/c", "1 / c")):
            flaws.append("The formula includes an inverse-`c` term, which may signal a pole / structural mismatch that needs first-principles justification.")

        if isinstance(tool_results.get("partition_ratios"), dict) and tool_results["partition_ratios"].get("skipped"):
            flaws.append("The partition-ratio pathway did not execute cleanly for this gap, weakening the evidence chain.")

        critique = (critique_text or "").lower()
        if "hallucinated convergence" in critique:
            flaws.append("Red-team flagged possible hallucinated convergence between the textual claim and the measured evidence.")
        if "dimensional violation" in critique:
            flaws.append("Red-team flagged a potential dimensional / scaling inconsistency in the proposed structure.")

        deduped: list[str] = []
        seen = set()
        for flaw in flaws:
            if flaw not in seen:
                deduped.append(flaw)
                seen.add(flaw)
        return deduped[:4]

    def _build_controller_action(
        self,
        lfi: float,
        hypothesis: dict,
        execution: dict,
        flaws: list[str],
        swarm_report: Optional[dict[str, Any]] = None,
    ) -> tuple[str, str]:
        gap_pct = self._extract_gap_pct(execution)
        claim = (hypothesis.get("claim", "") or "").lower()
        best_swarm_gap = None
        best_swarm_formula = None
        if swarm_report and swarm_report.get("best_gap_pct") is not None:
            try:
                best_swarm_gap = float(swarm_report.get("best_gap_pct"))
            except Exception:
                best_swarm_gap = None
            best_swarm_formula = swarm_report.get("best_formula")

        if best_swarm_gap is not None and best_swarm_gap < 0.001 and lfi <= max(self.config.lfi_judge_threshold + 0.10, 0.30):
            return (
                "PROCEED_TO_JUDGE_WITH_ASR_SURVIVOR",
                f"Active symbolic refinement produced a near-zero local gap ({best_swarm_gap}); escalate the best survivor to judge and independent verification: {best_swarm_formula or hypothesis.get('candidate_formula', '')}",
            )

        if lfi > self.config.lfi_refactor_threshold:
            if any(token in claim for token in ("/c₅", "/c5", "1/c", "1 / c")) or any("pole" in flaw.lower() for flaw in flaws):
                return (
                    "TRIGGER_REFACTOR",
                    "SYSTEM_PROMPT_INJECTION: Strategist must abandon the current pole-structure and re-derive the claim from first principles before another debate round.",
                )
            return (
                "TRIGGER_REFACTOR",
                "SYSTEM_PROMPT_INJECTION: Strategist must rewrite the claim with narrower assumptions, explicit falsification tests, and a cleaner evidence chain.",
            )

        if lfi > self.config.lfi_judge_threshold:
            if best_swarm_gap is not None and best_swarm_gap <= 10:
                return (
                    "TRIGGER_PERTURBATION_ON_BEST_SURVIVOR",
                    f"Run one more verification pass on the ASR-refined survivor before judge escalation: best_gap_pct={best_swarm_gap}, formula={best_swarm_formula or hypothesis.get('candidate_formula', '')}",
                )
            if gap_pct is not None and gap_pct > 10:
                return (
                    "TRIGGER_PERTURBATION",
                    "Run a symbolic-regression / coefficient-perturbation sweep and keep only variants with gap_pct <= 10% before the next round.",
                )
            return (
                "TRIGGER_PERTURBATION",
                "Run one more targeted verification and parameter-perturbation pass before escalating to the judge.",
            )

        if best_swarm_gap is not None and (gap_pct is None or best_swarm_gap < gap_pct):
            return (
                "PROCEED_TO_JUDGE_WITH_SWARM_SURVIVOR",
                f"The swarm materially improved the local fit (best_gap_pct={best_swarm_gap}); continue with the best survivor: {best_swarm_formula or hypothesis.get('candidate_formula', '')}",
            )

        return (
            "PROCEED_TO_JUDGE",
            "Hypothesis survived the current red-team gate; proceed to judge or stronger formal verification.",
        )

    def _append_self_correction_log(
        self,
        hypothesis: dict,
        execution: dict,
        verdict: str,
        scores: dict[str, float],
        lfi: float,
        controller_action: str,
        meta_directive: str,
        critique_summary: str,
        lethal_flaws: list[str],
        swarm_report: Optional[dict[str, Any]] = None,
    ) -> None:
        SELF_CORRECTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing = json.loads(SELF_CORRECTION_LOG_PATH.read_text(encoding="utf-8")) if SELF_CORRECTION_LOG_PATH.exists() else []
        except Exception:
            existing = []
        if not isinstance(existing, list):
            existing = []

        existing.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "hypothesis_id": hypothesis.get("id", "unknown"),
                "gap_id": hypothesis.get("gap_id", "unknown"),
                "verdict": verdict,
                "scores": scores,
                "lfi": lfi,
                "controller_action": controller_action,
                "meta_directive": meta_directive,
                "critique_summary": critique_summary[:300],
                "lethal_flaws": lethal_flaws,
                "gap_pct": self._extract_gap_pct(execution),
                "swarm_id": (swarm_report or {}).get("swarm_id"),
                "generation": (swarm_report or {}).get("generation"),
                "best_gap_pct": (swarm_report or {}).get("best_gap_pct"),
                "survivor_ids": [item.get("id") for item in (swarm_report or {}).get("survivors", [])],
            }
        )
        SELF_CORRECTION_LOG_PATH.write_text(json.dumps(existing[-200:], indent=2, ensure_ascii=False), encoding="utf-8")

    def _derive_verdict(self, parsed: dict[str, Any], scores: dict[str, float], execution: dict, critique_text: str) -> str:
        parsed_verdict = str(parsed.get("verdict", "")).strip().lower()
        if parsed_verdict in {"failure", "inconclusive", "progress", "breakthrough"}:
            return parsed_verdict

        critique = (critique_text or "").lower()
        success = bool(execution.get("success", False))
        b_score = scores["N"] * scores["F"] * scores["E"] * scores["C"]

        if any(token in critique for token in ("falsified", "invalid", "unsupported", "contradiction")):
            return "failure"
        if success and b_score >= 0.35 and min(scores.values()) >= 0.62:
            if scores["N"] >= 0.80 and scores["E"] >= 0.82 and scores["C"] >= 0.80:
                return "breakthrough"
            return "progress"
        if success or b_score >= 0.10:
            return "progress"
        return "inconclusive"

    def evaluate(self, hypothesis: dict, execution: dict) -> dict[str, Any]:
        judge = None
        if self.config.with_judge:
            judge_model = self.config.strategist_model if self.config.judge_provider == "openai" else self.config.critic_model
            judge = AgentConfig(
                name="Judge",
                provider=self.config.judge_provider,
                model=judge_model,
                temperature=0.1,
            )

        controller = DebateController(
            strategist=AgentConfig(name="Strategist", provider=self.config.strategist_provider, model=self.config.strategist_model, temperature=0.25),
            critic=AgentConfig(name="Critic", provider=self.config.critic_provider, model=self.config.critic_model, temperature=0.40),
            judge=judge,
            dry_run=self.config.dry_run,
            strategist_system=self._strategist_system(),
            critic_system=self._critic_system(),
            judge_system=self._judge_system(),
        )

        memory_entries = self._load_self_correction_memory(hypothesis)
        swarm_report = self._run_swarm_gauntlet(hypothesis, execution, memory_entries)
        result = controller.run(
            task=self._build_task_prompt(hypothesis, execution, memory_entries, swarm_report),
            iterations=max(1, self.config.max_iter),
            convergence_threshold=self.config.convergence_threshold,
            with_judge=self.config.with_judge,
        )

        critique_parts = [item.critic_feedback for item in result.history if item.critic_feedback]
        if result.judge_summary:
            critique_parts.append(result.judge_summary)
        critique_text = "\n\n".join(critique_parts)

        parsed = self._extract_score_json(critique_text)
        scores = self._derive_scores(parsed, hypothesis, execution, critique_text)
        b_score = round(scores["N"] * scores["F"] * scores["E"] * scores["C"], 6)
        verdict = self._derive_verdict(parsed, scores, execution, critique_text)
        lfi = self._derive_lfi(parsed, hypothesis, execution, critique_text, swarm_report=swarm_report)
        lethal_flaws = self._collect_lethal_flaws(hypothesis, execution, critique_text, swarm_report=swarm_report)
        controller_action, meta_directive = self._build_controller_action(lfi, hypothesis, execution, lethal_flaws, swarm_report=swarm_report)

        summary = parsed.get("critique_summary") if isinstance(parsed, dict) else None
        if not summary:
            summary = critique_text[:1200]

        self._append_self_correction_log(
            hypothesis=hypothesis,
            execution=execution,
            verdict=verdict,
            scores=scores,
            lfi=lfi,
            controller_action=controller_action,
            meta_directive=meta_directive,
            critique_summary=summary,
            lethal_flaws=lethal_flaws,
            swarm_report=swarm_report,
        )

        return {
            "scores": scores,
            "b_score": b_score,
            "verdict": verdict,
            "critique": summary,
            "judge_summary": result.judge_summary,
            "debate_output_path": result.output_path,
            "iterations_completed": result.iterations_completed,
            "dry_run": self.config.dry_run,
            "lfi": lfi,
            "controller_action": controller_action,
            "meta_directive": meta_directive,
            "self_correction_log_path": str(SELF_CORRECTION_LOG_PATH),
            "red_team_output": {
                "LFI": lfi,
                "lethal_flaws": lethal_flaws,
                "controller_action": controller_action,
                "meta_directive": meta_directive,
            },
            "swarm": swarm_report,
            "best_swarm_gap_pct": (swarm_report or {}).get("best_gap_pct"),
            "best_swarm_formula": (swarm_report or {}).get("best_formula"),
            "memory_hits": len(memory_entries),
            "history": [
                {
                    "round_index": item.round_index,
                    "strategist_output": item.strategist_output,
                    "critic_feedback": item.critic_feedback,
                    "similarity_to_previous": item.similarity_to_previous,
                    "converged": item.converged,
                    "stop_reason": item.stop_reason,
                }
                for item in result.history
            ],
        }
