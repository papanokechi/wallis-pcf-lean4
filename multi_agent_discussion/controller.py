from __future__ import annotations

"""
Multi-agent discussion controller.

Implements a controller-mediated debate loop for:
- OpenAI model as the Strategist (default: gpt-4o)
- Anthropic model as the Critic (default: claude-opus-4-5)
- Optional Judge role

Usage:
    py multi_agent_discussion/controller.py --task "Design a caching strategy" --iterations 3
    py multi_agent_discussion/controller.py --task "Explain zero-trust rollout" --with-judge
    py multi_agent_discussion/controller.py --task "Create an API plan" --dry-run
"""

import argparse
import json
import os
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import anthropic
except Exception:
    anthropic = None

ROOT = Path(__file__).resolve().parents[1]

# Shared default convergence threshold used by both DebateController.run()
# and siarc_adapter.DebateCriticConfig. Keep in one place to avoid drift.
DEFAULT_CONVERGENCE_THRESHOLD = 0.94
RUNS_DIR = ROOT / "multi_agent_discussion" / "runs"


@dataclass
class AgentConfig:
    name: str
    provider: str
    model: str
    temperature: float = 0.2


@dataclass
class IterationRecord:
    round_index: int
    strategist_output: str
    critic_feedback: str
    similarity_to_previous: float
    converged: bool = False
    stop_reason: str = ""


@dataclass
class DebateResult:
    task: str
    iterations_requested: int
    iterations_completed: int
    output_path: str
    final_answer: str
    judge_summary: Optional[str] = None
    history: list[IterationRecord] = field(default_factory=list)


def load_env_file(env_path: Path) -> None:
    """Minimal .env loader without external dependencies."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


class DebateController:
    STRATEGIST_SYSTEM = textwrap.dedent(
        """
        You are the Strategist in a multi-agent reasoning loop.
        Produce the strongest possible answer for the user task.
        When critique is provided, revise the answer to fix gaps, tighten logic,
        and improve edge-case handling without losing clarity.

        Output sections:
        1. Improved answer
        2. Key changes from critique
        3. Remaining uncertainty
        """
    ).strip()

    CRITIC_SYSTEM = textwrap.dedent(
        """
        You are the Critic in a multi-agent reasoning loop.
        Review the strategist answer aggressively but constructively.
        Find factual gaps, weak assumptions, missing edge cases, and unclear wording.

        Output sections:
        1. Strengths
        2. Problems
        3. Edge cases
        4. Revision advice
        5. Verdict
        """
    ).strip()

    JUDGE_SYSTEM = textwrap.dedent(
        """
        You are the Judge in a multi-agent reasoning loop.
        Review the round history and determine whether the final strategist answer
        is strong enough to ship. Summarize what improved across rounds and note
        any remaining risk.
        """
    ).strip()

    def __init__(
        self,
        strategist: AgentConfig,
        critic: AgentConfig,
        judge: Optional[AgentConfig] = None,
        dry_run: bool = False,
        max_tokens: int = 1600,
        strategist_system: Optional[str] = None,
        critic_system: Optional[str] = None,
        judge_system: Optional[str] = None,
    ):
        self.strategist = strategist
        self.critic = critic
        self.judge = judge
        self.dry_run = dry_run
        self.max_tokens = max_tokens
        self.strategist_system = strategist_system or self.STRATEGIST_SYSTEM
        self.critic_system = critic_system or self.CRITIC_SYSTEM
        self.judge_system = judge_system or self.JUDGE_SYSTEM
        self._clients: dict[str, Any] = {}

    def _get_client(self, provider: str) -> Any:
        provider = provider.lower()
        if provider in self._clients:
            return self._clients[provider]

        if provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set.")
            if OpenAI is None:
                raise RuntimeError("The 'openai' package is not installed. Run: py -m pip install openai")
            client = OpenAI(api_key=api_key)
        elif provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set.")
            if anthropic is None:
                raise RuntimeError("The 'anthropic' package is not installed. Run: py -m pip install anthropic")
            client = anthropic.Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self._clients[provider] = client
        return client

    def _call_openai(self, config: AgentConfig, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client("openai")

        try:
            response = client.responses.create(
                model=config.model,
                input=f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}",
            )
            text = getattr(response, "output_text", "") or ""
            if text.strip():
                return text.strip()
        except Exception as _responses_exc:
            # responses.create not available on this SDK version or model;
            # fall through to chat.completions.create
            import warnings
            warnings.warn(f"responses.create failed ({_responses_exc}); using chat.completions")

        completion = client.chat.completions.create(
            model=config.model,
            temperature=config.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        message = completion.choices[0].message.content
        return (message or "").strip()

    def _call_anthropic(self, config: AgentConfig, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client("anthropic")
        message = client.messages.create(
            model=config.model,
            max_tokens=self.max_tokens,
            temperature=config.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        blocks = []
        for block in message.content:
            if getattr(block, "type", "") == "text":
                blocks.append(block.text)
        return "\n".join(blocks).strip()

    def _dry_run_response(self, config: AgentConfig, round_index: int, task: str) -> str:
        task_preview = task.replace("\n", " ")[:120]
        if config.name == "Strategist":
            if round_index == 1:
                return textwrap.dedent(
                    f"""
                    [DRY RUN] Improved answer
                    - Proposed solution for: {task_preview}
                    - Architecture: controller -> GPT Strategist -> Claude Critic -> loop -> final output
                    - Add iteration caps, JSON logs, and env-based secret management.

                    Key changes from critique
                    - Initial draft only, so no changes yet.

                    Remaining uncertainty
                    - Real API behavior depends on installed SDKs and valid keys.
                    """
                ).strip()
            return textwrap.dedent(
                f"""
                [DRY RUN] Improved answer
                - Refined the plan for: {task_preview}
                - Added convergence checks, optional judge role, and clearer output structure.
                - Included safer key handling and persisted per-round logs.

                Key changes from critique
                - Addressed edge cases and clarified controller responsibilities.

                Remaining uncertainty
                - UI streaming is optional and not enabled in this CLI demo.
                """
            ).strip()

        if config.name == "Critic":
            verdict_label = "progress" if round_index > 1 else "inconclusive"
            verdict_text = "Looks close to ready." if round_index > 1 else "Needs one more refinement pass."
            lfi_score = 0.46 if round_index > 1 else 0.82
            return textwrap.dedent(
                f"""
                Strengths
                - The controller-mediated loop is correct.
                - Keys stay on the backend.

                Lethal flaws
                - The current draft still needs an explicit audit trail from critique to revision.
                - Critical verification paths could still be skipped or under-specified.
                - Repeated answers across iterations may hide plateauing rather than true convergence.

                Problems
                - Could better explain stopping conditions and output persistence.

                Edge cases
                - Missing API keys
                - SDK not installed
                - Repeated answers across iterations

                Revision advice
                - Add convergence checks, judge option, explicit log file paths, and a red-team gate before finalization.

                Verdict
                - {verdict_text}

                LFI: {lfi_score:.2f}
                SCORE_JSON: {{"N": 0.55, "F": 0.60, "E": 0.58, "C": 0.52, "LFI": {lfi_score:.2f}, "verdict": "{verdict_label}", "critique_summary": "[DRY RUN] Synthetic scores — no real API call made. Run without --debate-dry-run for live evaluation."}}
                """
            ).strip()

        return textwrap.dedent(
            """
            Judge summary
            - The final draft is stronger than the initial version.
            - The system now covers orchestration, storage, and stopping criteria.
            - Remaining risk is mainly operational setup, not design quality.
            """
        ).strip()

    def _call_model(self, config: AgentConfig, system_prompt: str, user_prompt: str, round_index: int, task: str) -> str:
        if self.dry_run:
            return self._dry_run_response(config, round_index, task)

        provider = config.provider.lower()
        if provider == "openai":
            return self._call_openai(config, system_prompt, user_prompt)
        if provider == "anthropic":
            return self._call_anthropic(config, system_prompt, user_prompt)
        raise ValueError(f"Unsupported provider: {config.provider}")

    def _build_strategist_prompt(
        self,
        task: str,
        previous_answer: str,
        latest_critique: str,
        round_index: int,
    ) -> str:
        prior_context = "No prior critique yet. Produce the first strong answer." if round_index == 1 else textwrap.dedent(
            f"""
            Previous answer:
            {previous_answer}

            Latest critique to address:
            {latest_critique}
            """
        ).strip()

        return textwrap.dedent(
            f"""
            User task:
            {task}

            Debate round: {round_index}

            {prior_context}

            Requirements:
            - Answer the task directly and clearly.
            - Address every important critique point.
            - Improve precision, edge-case coverage, and practical usefulness.
            - Keep the answer ready for a human end user.
            """
        ).strip()

    def _build_critic_prompt(self, task: str, strategist_output: str, round_index: int) -> str:
        return textwrap.dedent(
            f"""
            User task:
            {task}

            Strategist draft for round {round_index}:
            {strategist_output}

            Review instructions:
            - Identify weaknesses, risks, or ambiguity.
            - Suggest concrete fixes.
            - If the answer is already strong, say that explicitly.
            - Focus on correctness, clarity, and edge cases.
            """
        ).strip()

    def _build_judge_prompt(self, task: str, history: list[IterationRecord]) -> str:
        history_blob = []
        for item in history:
            history_blob.append(
                textwrap.dedent(
                    f"""
                    Round {item.round_index} strategist output:
                    {item.strategist_output}

                    Round {item.round_index} critic feedback:
                    {item.critic_feedback}
                    """
                ).strip()
            )
        joined_history = "\n\n".join(history_blob)
        return textwrap.dedent(
            f"""
            Original task:
            {task}

            Debate history:
            {joined_history}

            Decide whether the final strategist answer should be accepted as the final output.
            """
        ).strip()

    @staticmethod
    def _check_convergence(previous_answer: str, current_answer: str, critic_feedback: str, threshold: float) -> tuple[bool, float, str]:
        if not previous_answer.strip():
            return False, 0.0, ""

        similarity = SequenceMatcher(None, previous_answer.strip(), current_answer.strip()).ratio()
        critic_lower = critic_feedback.lower()
        positive_markers = (
            "looks close to ready",
            "ready to ship",
            "no major issues",
            "strong as-is",
            "approved",
        )
        if similarity >= threshold:
            return True, similarity, f"Similarity threshold reached ({similarity:.3f})."
        if any(marker in critic_lower for marker in positive_markers):
            return True, similarity, "Critic indicated the answer is ready."
        return False, similarity, ""

    def _save_run(
        self,
        task: str,
        history: list[IterationRecord],
        final_answer: str,
        judge_summary: Optional[str],
        output_file: Optional[str],
    ) -> str:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        if output_file:
            json_path = Path(output_file).expanduser().resolve()
            json_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            json_path = RUNS_DIR / f"debate_{timestamp}.json"

        md_path = json_path.with_suffix(".md")
        payload = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "strategist": asdict(self.strategist),
            "critic": asdict(self.critic),
            "judge": asdict(self.judge) if self.judge else None,
            "dry_run": self.dry_run,
            "history": [asdict(item) for item in history],
            "judge_summary": judge_summary,
            "final_answer": final_answer,
        }
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        report = [
            "# Multi-Agent Debate Report",
            "",
            "## Task",
            task,
            "",
            "## Final Answer",
            final_answer,
            "",
        ]
        if judge_summary:
            report.extend(["## Judge Summary", judge_summary, ""])

        report.append("## Iteration History")
        for item in history:
            report.extend(
                [
                    "",
                    f"### Round {item.round_index}",
                    f"- Similarity to previous: {item.similarity_to_previous:.3f}",
                    f"- Converged: {item.converged}",
                    f"- Stop reason: {item.stop_reason or 'n/a'}",
                    "",
                    "#### Strategist Output",
                    item.strategist_output,
                    "",
                    "#### Critic Feedback",
                    item.critic_feedback,
                ]
            )

        md_path.write_text("\n".join(report), encoding="utf-8")
        return str(json_path)

    def run(
        self,
        task: str,
        iterations: int = 3,
        convergence_threshold: float = DEFAULT_CONVERGENCE_THRESHOLD,
        with_judge: bool = False,
        output_file: Optional[str] = None,
    ) -> DebateResult:
        history: list[IterationRecord] = []
        previous_answer = ""
        latest_critique = ""

        for round_index in range(1, iterations + 1):
            strategist_prompt = self._build_strategist_prompt(task, previous_answer, latest_critique, round_index)
            strategist_output = self._call_model(
                self.strategist,
                self.strategist_system,
                strategist_prompt,
                round_index,
                task,
            )

            critic_prompt = self._build_critic_prompt(task, strategist_output, round_index)
            critic_feedback = self._call_model(
                self.critic,
                self.critic_system,
                critic_prompt,
                round_index,
                task,
            )

            converged, similarity, reason = self._check_convergence(
                previous_answer,
                strategist_output,
                critic_feedback,
                convergence_threshold,
            )

            history.append(
                IterationRecord(
                    round_index=round_index,
                    strategist_output=strategist_output,
                    critic_feedback=critic_feedback,
                    similarity_to_previous=similarity,
                    converged=converged,
                    stop_reason=reason,
                )
            )

            previous_answer = strategist_output
            latest_critique = critic_feedback

            if converged and round_index >= 2:
                break

        final_answer = history[-1].strategist_output if history else ""
        judge_summary = None

        if with_judge and self.judge is not None:
            judge_prompt = self._build_judge_prompt(task, history)
            judge_summary = self._call_model(
                self.judge,
                self.judge_system,
                judge_prompt,
                0,
                task,
            )

        output_path = self._save_run(task, history, final_answer, judge_summary, output_file)
        return DebateResult(
            task=task,
            iterations_requested=iterations,
            iterations_completed=len(history),
            output_path=output_path,
            final_answer=final_answer,
            judge_summary=judge_summary,
            history=history,
        )


def read_task_from_args(task: Optional[str], task_file: Optional[str]) -> str:
    if task and task.strip():
        return task.strip()
    if task_file:
        return Path(task_file).expanduser().read_text(encoding="utf-8").strip()
    raise ValueError("Provide either --task or --task-file.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controller-mediated GPT ↔ Claude discussion loop")
    parser.add_argument("--task", help="Direct task text")
    parser.add_argument("--task-file", help="Path to a text or markdown file containing the task")
    parser.add_argument(
        "--iterations",
        type=int,
        default=int(os.environ.get("DEBATE_MAX_ITERATIONS", "3")),
        help="Maximum strategist/critic rounds (default: 3)",
    )
    parser.add_argument(
        "--convergence-threshold",
        type=float,
        default=DEFAULT_CONVERGENCE_THRESHOLD,
        help="Stop early when strategist drafts become very similar (default: 0.96)",
    )
    parser.add_argument(
        "--openai-model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        help="OpenAI model name for the Strategist",
    )
    parser.add_argument(
        "--anthropic-model",
        default=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5"),
        help="Anthropic model name for the Critic",
    )
    parser.add_argument("--with-judge", action="store_true", help="Add an optional Judge pass at the end")
    parser.add_argument(
        "--judge-provider",
        choices=["openai", "anthropic"],
        default="anthropic",
        help="Provider for the optional Judge role",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without calling external APIs")
    parser.add_argument("--output-file", help="Optional path for the JSON log output")
    return parser.parse_args()


def main() -> int:
    load_env_file(ROOT / ".env")
    args = parse_args()

    try:
        task = read_task_from_args(args.task, args.task_file)
        strategist = AgentConfig(name="Strategist", provider="openai", model=args.openai_model, temperature=0.3)
        critic = AgentConfig(name="Critic", provider="anthropic", model=args.anthropic_model, temperature=0.2)
        judge = None
        if args.with_judge:
            judge_model = args.openai_model if args.judge_provider == "openai" else args.anthropic_model
            judge = AgentConfig(name="Judge", provider=args.judge_provider, model=judge_model, temperature=0.1)

        controller = DebateController(
            strategist=strategist,
            critic=critic,
            judge=judge,
            dry_run=args.dry_run,
        )
        result = controller.run(
            task=task,
            iterations=max(1, args.iterations),
            convergence_threshold=args.convergence_threshold,
            with_judge=args.with_judge,
            output_file=args.output_file,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("=" * 72)
    print("Multi-Agent Discussion Complete")
    print("=" * 72)
    print(f"Iterations completed : {result.iterations_completed}/{result.iterations_requested}")
    print(f"Run log saved to     : {result.output_path}")
    print()
    print("Final answer")
    print("-" * 72)
    print(result.final_answer)
    if result.judge_summary:
        print()
        print("Judge summary")
        print("-" * 72)
        print(result.judge_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
