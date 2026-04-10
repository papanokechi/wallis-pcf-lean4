"""
MetaOrchestrator — Unified AI-Researcher over AI-Researchers
============================================================

A thin dispatch layer that treats each discovery engine as a tool:
  1. Ising/XY/O(3) Monte Carlo pipeline  (breakthrough_runner)
  2. Ramanujan GCF agent                  (ramanujan_agent)
  3. Ratio universality engine            (relay_round10)
  4. GCF discovery loop                   (discovery_loop)
  5. Micro-laws / materials               (materials_microlaws)

The MetaOrchestrator:
  - Maintains a priority queue of DiscoveryTasks
  - Dispatches each task to the appropriate engine
  - Evaluates results against pre-registered success criteria
  - Logs a structured decision trace (JSON audit trail)
  - Produces a unified session report

Usage:
    python meta_orchestrator.py                    # run default task queue
    python meta_orchestrator.py --tasks tasks.json # custom task file
    python meta_orchestrator.py --demo             # quick 3-domain demo
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ══════════════════════════════════════════════════════════════════════════
# §1  SCHEMA
# ══════════════════════════════════════════════════════════════════════════

class Domain(str, Enum):
    ISING_MC    = "ising_mc"
    RAMANUJAN   = "ramanujan_gcf"
    RATIO_UNIV  = "ratio_universality"
    GCF_LOOP    = "gcf_discovery_loop"
    MICRO_LAWS  = "micro_laws"


class TaskStatus(str, Enum):
    QUEUED      = "queued"
    RUNNING     = "running"
    PASSED      = "passed"
    FAILED      = "failed"
    SKIPPED     = "skipped"


@dataclass
class SuccessCriterion:
    """Pre-registered success threshold for a task."""
    metric: str                    # e.g. "relative_error", "novel_proven_count", "L_gap_pct"
    threshold: float               # e.g. 0.05 (5% error)
    direction: str = "below"       # "below" = metric < threshold is success


@dataclass
class DiscoveryTask:
    """Universal task schema dispatched to any engine."""
    task_id: str
    domain: Domain
    description: str
    hypothesis_space: dict         # domain-specific config
    success_criterion: SuccessCriterion
    compute_budget_seconds: float = 600.0
    priority: int = 5              # 1=highest, 10=lowest
    pre_registration_hash: str = ""

    def __post_init__(self):
        if not self.pre_registration_hash:
            blob = json.dumps({
                "task_id": self.task_id,
                "domain": self.domain,
                "hypothesis_space": self.hypothesis_space,
                "criterion": asdict(self.success_criterion),
            }, sort_keys=True)
            self.pre_registration_hash = hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class TaskResult:
    """Standardized result from any engine."""
    task_id: str
    domain: Domain
    status: TaskStatus
    metric_value: Optional[float] = None
    summary: str = ""
    artifacts: dict = field(default_factory=dict)  # paths to outputs
    wall_time_seconds: float = 0.0
    raw_output: str = ""
    novelty_check: Optional[dict] = None


@dataclass
class DecisionRecord:
    """One entry in the audit trail."""
    timestamp: str
    task_id: str
    decision_type: str             # "dispatch", "evaluate", "skip", "novelty_gate"
    rationale: str
    details: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════
# §2  NOVELTY GATE
# ══════════════════════════════════════════════════════════════════════════

class NoveltyGate:
    """Check whether a result is genuinely new before accepting it."""

    KNOWN_EXPONENTS = {
        "ising_3d_beta": 0.3265, "ising_3d_gamma": 1.2372, "ising_3d_nu": 0.6300,
        "xy_3d_beta": 0.3486, "xy_3d_gamma": 1.3178, "xy_3d_nu": 0.6717,
        "ising_2d_beta": 0.125, "ising_2d_gamma": 1.75,
    }

    KNOWN_CONSTANTS = {
        "pi", "e", "ln2", "gamma_euler", "catalan", "zeta3",
        "sqrt2", "sqrt3", "sqrt5", "golden_ratio",
    }

    def check(self, result: TaskResult) -> dict:
        """Return {is_novel: bool, reason: str, checks: [...]}."""
        checks = []

        # 1. Exponent match
        if result.domain == Domain.ISING_MC:
            for key, known in self.KNOWN_EXPONENTS.items():
                measured = result.artifacts.get(key)
                if measured is not None:
                    rel_err = abs(measured - known) / known
                    is_known = rel_err < 0.001  # within 0.1% of literature
                    checks.append({
                        "check": f"exponent_{key}",
                        "measured": measured,
                        "known": known,
                        "rel_error": rel_err,
                        "is_known_value": is_known,
                    })

        # 2. Closed-form match (Ramanujan / GCF)
        if result.domain in (Domain.RAMANUJAN, Domain.GCF_LOOP):
            novel_count = result.artifacts.get("novel_proven_count", 0)
            total = result.artifacts.get("total_discoveries", 0)
            checks.append({
                "check": "novel_proven_ratio",
                "novel_proven": novel_count,
                "total": total,
                "is_novel": novel_count > 0,
            })

        # 3. Ratio universality: check if L formula gap is new
        if result.domain == Domain.RATIO_UNIV:
            families_tested = result.artifacts.get("families", [])
            new_families = [f for f in families_tested
                           if f.get("is_new_verification", False)]
            checks.append({
                "check": "new_family_verifications",
                "count": len(new_families),
                "families": [f["name"] for f in new_families],
                "is_novel": len(new_families) > 0,
            })

        is_novel = any(c.get("is_novel", False) for c in checks)
        reason = "novel result detected" if is_novel else "all results match known values"
        return {"is_novel": is_novel, "reason": reason, "checks": checks}


# ══════════════════════════════════════════════════════════════════════════
# §3  ENGINE ADAPTERS
# ══════════════════════════════════════════════════════════════════════════

WORKSPACE = Path(__file__).parent


class EngineAdapter:
    """Base class for engine adapters."""
    def run(self, task: DiscoveryTask) -> TaskResult:
        raise NotImplementedError


class IsingMCAdapter(EngineAdapter):
    """Adapter for breakthrough_runner_v14.py (Ising/XY/O(3) MC pipeline)."""

    def run(self, task: DiscoveryTask) -> TaskResult:
        script = WORKSPACE / "multi_agent_discovery" / "breakthrough_runner_v14.py"
        if not script.exists():
            # Fallback: look for any breakthrough_runner
            candidates = sorted(WORKSPACE.glob("**/breakthrough_runner_v*.py"))
            script = candidates[-1] if candidates else None

        if not script:
            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.FAILED, summary="No breakthrough_runner found",
            )

        t0 = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True,
                timeout=task.compute_budget_seconds,
                cwd=str(WORKSPACE),
            )
            wall = time.time() - t0
            output = proc.stdout[-5000:] if len(proc.stdout) > 5000 else proc.stdout

            # Parse key results from stdout
            artifacts = self._parse_output(output)
            metric = artifacts.get(task.success_criterion.metric)
            passed = (metric is not None and
                      (metric < task.success_criterion.threshold
                       if task.success_criterion.direction == "below"
                       else metric > task.success_criterion.threshold))

            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.PASSED if passed else TaskStatus.FAILED,
                metric_value=metric,
                summary=f"MC pipeline completed in {wall:.0f}s",
                artifacts=artifacts, wall_time_seconds=wall,
                raw_output=output,
            )
        except subprocess.TimeoutExpired:
            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.FAILED,
                summary=f"Timeout after {task.compute_budget_seconds}s",
                wall_time_seconds=task.compute_budget_seconds,
            )

    def _parse_output(self, output: str) -> dict:
        """Extract key metrics from breakthrough_runner stdout."""
        import re
        artifacts = {}
        # Look for patterns like "β = 0.329 (0.9% error)"
        for line in output.split("\n"):
            m = re.search(r"[βbeta]+.*?=\s*([\d.]+).*?([\d.]+)%\s*error", line, re.I)
            if m:
                artifacts["ising_3d_beta"] = float(m.group(1))
                artifacts["relative_error"] = float(m.group(2)) / 100
            m = re.search(r"[γgamma]+.*?=\s*([\d.]+).*?([\d.]+)%\s*error", line, re.I)
            if m:
                artifacts["ising_3d_gamma"] = float(m.group(1))
        return artifacts


class RamanujanAdapter(EngineAdapter):
    """Adapter for ramanujan_agent (python -m ramanujan_agent)."""

    def run(self, task: DiscoveryTask) -> TaskResult:
        hs = task.hypothesis_space
        rounds = hs.get("rounds", 2)
        budget = hs.get("budget", 15)

        t0 = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "ramanujan_agent",
                 "--rounds", str(rounds), "--budget", str(budget), "--fast"],
                capture_output=True, text=True,
                timeout=task.compute_budget_seconds,
                cwd=str(WORKSPACE),
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            wall = time.time() - t0
            output = proc.stdout[-5000:] if len(proc.stdout) > 5000 else proc.stdout

            artifacts = self._parse_output(output)
            metric = artifacts.get(task.success_criterion.metric)
            passed = (metric is not None and
                      (metric < task.success_criterion.threshold
                       if task.success_criterion.direction == "below"
                       else metric > task.success_criterion.threshold))

            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.PASSED if passed else TaskStatus.FAILED,
                metric_value=metric,
                summary=f"Ramanujan agent: {artifacts.get('novel_proven_count', 0)} novel proven",
                artifacts=artifacts, wall_time_seconds=wall,
                raw_output=output,
            )
        except subprocess.TimeoutExpired:
            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.FAILED,
                summary=f"Timeout after {task.compute_budget_seconds}s",
                wall_time_seconds=task.compute_budget_seconds,
            )

    def _parse_output(self, output: str) -> dict:
        import re
        artifacts = {}
        m = re.search(r"novel.proven.*?(\d+)", output, re.I)
        if m:
            artifacts["novel_proven_count"] = int(m.group(1))
        m = re.search(r"total.*?(\d+)\s*discover", output, re.I)
        if m:
            artifacts["total_discoveries"] = int(m.group(1))
        # Also try loading results JSON
        results_path = WORKSPACE / "results" / "ramanujan_results.json"
        if results_path.exists():
            try:
                data = json.loads(results_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    artifacts["novel_proven_count"] = sum(
                        1 for d in data.get("discoveries", [])
                        if d.get("status") == "novel_proven"
                    )
                    artifacts["total_discoveries"] = len(data.get("discoveries", []))
            except Exception:
                pass
        return artifacts


class RatioUniversalityAdapter(EngineAdapter):
    """Adapter for ratio universality verification (relay_round10_master.py)."""

    def run(self, task: DiscoveryTask) -> TaskResult:
        script = WORKSPACE / "relay_round10_master.py"
        if not script.exists():
            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.FAILED, summary="relay_round10_master.py not found",
            )

        t0 = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True,
                timeout=task.compute_budget_seconds,
                cwd=str(WORKSPACE),
            )
            wall = time.time() - t0
            output = proc.stdout[-8000:] if len(proc.stdout) > 8000 else proc.stdout
            artifacts = self._parse_output(output)
            metric = artifacts.get(task.success_criterion.metric)
            passed = (metric is not None and
                      (metric < task.success_criterion.threshold
                       if task.success_criterion.direction == "below"
                       else metric > task.success_criterion.threshold))

            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.PASSED if passed else TaskStatus.FAILED,
                metric_value=metric,
                summary=f"Ratio universality: {len(artifacts.get('families', []))} families verified",
                artifacts=artifacts, wall_time_seconds=wall,
                raw_output=output,
            )
        except subprocess.TimeoutExpired:
            return TaskResult(
                task_id=task.task_id, domain=task.domain,
                status=TaskStatus.FAILED,
                summary=f"Timeout after {task.compute_budget_seconds}s",
                wall_time_seconds=task.compute_budget_seconds,
            )

    def _parse_output(self, output: str) -> dict:
        import re
        artifacts = {"families": []}
        # Parse "k=X: L_pred=Y, L_fit=Z, gap=W%"
        for m in re.finditer(
            r"k\s*=\s*(\d+).*?gap.*?([\d.]+)%", output, re.I
        ):
            k = int(m.group(1))
            gap = float(m.group(2))
            artifacts["families"].append({
                "name": f"k={k}_colored",
                "L_gap_pct": gap,
                "is_new_verification": k > 5,
            })
        if artifacts["families"]:
            artifacts["max_L_gap_pct"] = max(f["L_gap_pct"] for f in artifacts["families"])
            artifacts["L_gap_pct"] = artifacts["max_L_gap_pct"]
        return artifacts


# ══════════════════════════════════════════════════════════════════════════
# §4  META-ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════

class MetaOrchestrator:
    """
    AI-Researcher over AI-Researchers.

    Maintains a priority queue of DiscoveryTasks, dispatches each to
    the appropriate engine, evaluates results, and produces a unified
    session report with full audit trail.
    """

    ADAPTERS = {
        Domain.ISING_MC:   IsingMCAdapter,
        Domain.RAMANUJAN:  RamanujanAdapter,
        Domain.RATIO_UNIV: RatioUniversalityAdapter,
    }

    def __init__(self, tasks: list[DiscoveryTask] | None = None):
        self.tasks: list[DiscoveryTask] = sorted(tasks or [], key=lambda t: t.priority)
        self.results: list[TaskResult] = []
        self.audit_trail: list[DecisionRecord] = []
        self.novelty_gate = NoveltyGate()
        self.session_id = f"meta_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    def _log(self, task_id: str, decision_type: str, rationale: str, **details):
        self.audit_trail.append(DecisionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task_id,
            decision_type=decision_type,
            rationale=rationale,
            details=details,
        ))

    def run(self) -> dict:
        """Execute all tasks in priority order."""
        print("=" * 72)
        print(f"  META-ORCHESTRATOR  |  Session: {self.session_id}")
        print(f"  Tasks: {len(self.tasks)}  |  Domains: "
              f"{', '.join(sorted(set(t.domain.value for t in self.tasks)))}")
        print("=" * 72)

        self._log("session", "start",
                  f"Beginning session with {len(self.tasks)} tasks",
                  task_count=len(self.tasks))

        total_t0 = time.time()

        for i, task in enumerate(self.tasks, 1):
            print(f"\n{'─'*72}")
            print(f"  [{i}/{len(self.tasks)}] {task.task_id}")
            print(f"  Domain: {task.domain.value}  |  Priority: {task.priority}")
            print(f"  Criterion: {task.success_criterion.metric} "
                  f"{task.success_criterion.direction} {task.success_criterion.threshold}")
            print(f"  Pre-reg: {task.pre_registration_hash}")
            print(f"{'─'*72}")

            # Dispatch decision
            adapter_cls = self.ADAPTERS.get(task.domain)
            if adapter_cls is None:
                self._log(task.task_id, "skip",
                          f"No adapter for domain {task.domain.value}")
                print(f"  SKIPPED: no adapter for {task.domain.value}")
                self.results.append(TaskResult(
                    task_id=task.task_id, domain=task.domain,
                    status=TaskStatus.SKIPPED,
                    summary=f"No adapter for {task.domain.value}",
                ))
                continue

            self._log(task.task_id, "dispatch",
                      f"Dispatching to {adapter_cls.__name__}",
                      budget=task.compute_budget_seconds)

            # Execute
            adapter = adapter_cls()
            result = adapter.run(task)

            # Novelty gate
            novelty = self.novelty_gate.check(result)
            result.novelty_check = novelty
            self._log(task.task_id, "novelty_gate",
                      novelty["reason"],
                      is_novel=novelty["is_novel"],
                      checks=novelty["checks"])

            # Evaluate
            self._log(task.task_id, "evaluate",
                      f"Status={result.status.value}, metric={result.metric_value}",
                      metric_value=result.metric_value,
                      wall_time=result.wall_time_seconds)

            self.results.append(result)

            status_icon = {"passed": "✓", "failed": "✗", "skipped": "○"}.get(
                result.status.value, "?")
            print(f"\n  Result: {status_icon} {result.status.value.upper()}")
            print(f"  Metric: {result.metric_value}")
            print(f"  Novel: {novelty['is_novel']} — {novelty['reason']}")
            print(f"  Wall time: {result.wall_time_seconds:.1f}s")
            print(f"  Summary: {result.summary}")

        total_wall = time.time() - total_t0

        self._log("session", "end",
                  f"Session complete: {sum(1 for r in self.results if r.status == TaskStatus.PASSED)}"
                  f"/{len(self.results)} passed",
                  total_wall_time=total_wall)

        # Save audit trail
        report = self._build_report(total_wall)
        self._save_report(report)

        return report

    def _build_report(self, total_wall: float) -> dict:
        passed = sum(1 for r in self.results if r.status == TaskStatus.PASSED)
        novel = sum(1 for r in self.results
                    if r.novelty_check and r.novelty_check.get("is_novel"))
        return {
            "session_id": self.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tasks": len(self.tasks),
            "passed": passed,
            "failed": len(self.results) - passed,
            "novel_results": novel,
            "total_wall_time_seconds": total_wall,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "domain": t.domain.value,
                    "description": t.description,
                    "pre_reg_hash": t.pre_registration_hash,
                    "criterion": asdict(t.success_criterion),
                }
                for t in self.tasks
            ],
            "results": [
                {
                    "task_id": r.task_id,
                    "domain": r.domain.value,
                    "status": r.status.value,
                    "metric_value": r.metric_value,
                    "summary": r.summary,
                    "wall_time_seconds": r.wall_time_seconds,
                    "novelty_check": r.novelty_check,
                    "artifacts": {k: v for k, v in r.artifacts.items()
                                  if k != "raw_output"},
                }
                for r in self.results
            ],
            "audit_trail": [asdict(d) for d in self.audit_trail],
            "autonomy_profile": self._autonomy_profile(),
        }

    def _autonomy_profile(self) -> dict:
        """Rate each domain on the 5-level autonomy scale."""
        return {
            "ising_mc": {
                "hypothesis": {"level": 3, "note": "Human picks universality class"},
                "design": {"level": 4, "note": "Auto selects L, T grid, simulator"},
                "execution": {"level": 5, "note": "Full auto 22-phase pipeline"},
                "synthesis": {"level": 4, "note": "Auto diagnosis + repair + audit"},
            },
            "ramanujan_gcf": {
                "hypothesis": {"level": 4, "note": "Auto-generates GCF families"},
                "design": {"level": 4, "note": "Auto parameter sweep + strategy selection"},
                "execution": {"level": 5, "note": "Full auto 10-phase pipeline"},
                "synthesis": {"level": 4, "note": "Auto proof funnel + CAS verify"},
            },
            "ratio_universality": {
                "hypothesis": {"level": 3, "note": "Human picks Meinardus class"},
                "design": {"level": 3, "note": "Human sets N range, semi-auto extraction"},
                "execution": {"level": 4, "note": "Auto L/alpha/beta extraction"},
                "synthesis": {"level": 2, "note": "Human derives closed forms, PSLQ-assisted"},
            },
            "gcf_discovery_loop": {
                "hypothesis": {"level": 4, "note": "Auto hypothesis via Claude API"},
                "design": {"level": 4, "note": "Auto parameter search strategy"},
                "execution": {"level": 5, "note": "Full auto iteration + verify"},
                "synthesis": {"level": 3, "note": "Semi-auto: Claude proposes, human validates"},
            },
        }

    def _save_report(self, report: dict):
        out_path = WORKSPACE / f"meta_session_{self.session_id}.json"
        out_path.write_text(json.dumps(report, indent=2, default=str),
                            encoding="utf-8")
        print(f"\n  Session report: {out_path.name}")

        # Also generate HTML summary
        html_path = WORKSPACE / f"meta_session_{self.session_id}.html"
        html_path.write_text(self._render_html(report), encoding="utf-8")
        print(f"  HTML report:    {html_path.name}")

    def _render_html(self, report: dict) -> str:
        """Generate a self-contained HTML session report."""
        rows = ""
        for r in report["results"]:
            icon = {"passed": "✓", "failed": "✗", "skipped": "○"}.get(r["status"], "?")
            color = {"passed": "#2d5", "failed": "#e44", "skipped": "#888"}.get(r["status"], "#ccc")
            novel = r.get("novelty_check", {})
            novel_tag = ('<span style="color:#f90;font-weight:bold">★ NOVEL</span>'
                         if novel.get("is_novel") else '<span style="color:#888">known</span>')
            rows += f"""<tr>
              <td>{r['task_id']}</td>
              <td><code>{r['domain']}</code></td>
              <td style="color:{color};font-weight:bold">{icon} {r['status']}</td>
              <td class="num">{r['metric_value'] if r['metric_value'] is not None else '—'}</td>
              <td>{novel_tag}</td>
              <td class="num">{r['wall_time_seconds']:.1f}s</td>
              <td>{r['summary']}</td>
            </tr>\n"""

        auto_rows = ""
        for domain, stages in report.get("autonomy_profile", {}).items():
            for stage, info in stages.items():
                lvl = info["level"]
                bar = "█" * lvl + "░" * (5 - lvl)
                auto_rows += f"""<tr>
                  <td><code>{domain}</code></td>
                  <td>{stage}</td>
                  <td class="num"><span style="font-family:monospace">{bar}</span> L{lvl}</td>
                  <td>{info['note']}</td>
                </tr>\n"""

        audit_rows = ""
        for d in report.get("audit_trail", [])[:50]:
            audit_rows += f"""<tr>
              <td style="font-size:0.8em">{d['timestamp'][11:19]}</td>
              <td>{d['task_id']}</td>
              <td>{d['decision_type']}</td>
              <td>{d['rationale']}</td>
            </tr>\n"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MetaOrchestrator Session — {report['session_id']}</title>
<style>
  :root {{ --bg: #0d1117; --fg: #c9d1d9; --accent: #58a6ff; --card: #161b22; --border: #30363d; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: var(--bg); color: var(--fg); max-width: 1100px; margin: 0 auto; padding: 2em; }}
  h1 {{ color: var(--accent); border-bottom: 2px solid var(--border); padding-bottom: 0.3em; }}
  h2 {{ color: #7ee787; margin-top: 2em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid var(--border); padding: 6px 10px; text-align: left; font-size: 0.9em; }}
  th {{ background: var(--card); color: var(--accent); }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  code {{ background: var(--card); padding: 2px 5px; border-radius: 3px; font-size: 0.88em; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1em; margin: 1em 0; }}
  .stat {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px;
           padding: 1em; text-align: center; }}
  .stat .val {{ font-size: 2em; font-weight: bold; color: var(--accent); }}
  .stat .label {{ font-size: 0.85em; color: #8b949e; margin-top: 0.3em; }}
</style>
</head>
<body>
<h1>MetaOrchestrator Session Report</h1>
<p>Session: <code>{report['session_id']}</code> | {report['timestamp'][:19]}Z</p>

<div class="stat-grid">
  <div class="stat"><div class="val">{report['total_tasks']}</div><div class="label">Tasks</div></div>
  <div class="stat"><div class="val" style="color:#2d5">{report['passed']}</div><div class="label">Passed</div></div>
  <div class="stat"><div class="val" style="color:#f90">{report['novel_results']}</div><div class="label">Novel</div></div>
  <div class="stat"><div class="val">{report['total_wall_time_seconds']:.0f}s</div><div class="label">Wall Time</div></div>
</div>

<h2>Results</h2>
<table>
  <tr><th>Task</th><th>Domain</th><th>Status</th><th>Metric</th><th>Novelty</th><th>Time</th><th>Summary</th></tr>
  {rows}
</table>

<h2>Autonomy Profile</h2>
<table>
  <tr><th>Domain</th><th>Stage</th><th>Level</th><th>Note</th></tr>
  {auto_rows}
</table>

<h2>Audit Trail (first 50)</h2>
<table>
  <tr><th>Time</th><th>Task</th><th>Type</th><th>Rationale</th></tr>
  {audit_rows}
</table>

<hr>
<p style="color:#8b949e;font-size:0.8em">Generated by MetaOrchestrator v1.0 — Unified AI-Researcher over AI-Researchers</p>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════
# §5  DEFAULT TASK LIBRARY
# ══════════════════════════════════════════════════════════════════════════

def demo_tasks() -> list[DiscoveryTask]:
    """Three-domain demo: Ising, Ramanujan, Ratio Universality."""
    return [
        DiscoveryTask(
            task_id="ising_3d_exponents",
            domain=Domain.ISING_MC,
            description="Discover 3D Ising critical exponents (beta, gamma) autonomously",
            hypothesis_space={
                "universality_class": "ising_3d",
                "lattice_sizes": [4, 6, 8, 10, 12],
                "T_range": [3.0, 5.0],
                "simulators": ["metropolis", "wolff"],
            },
            success_criterion=SuccessCriterion(
                metric="relative_error", threshold=0.10, direction="below"
            ),
            compute_budget_seconds=1800,
            priority=2,
        ),
        DiscoveryTask(
            task_id="ramanujan_gcf_discovery",
            domain=Domain.RAMANUJAN,
            description="Discover novel GCF identities with formal proofs",
            hypothesis_space={
                "rounds": 2,
                "budget": 15,
                "strategies": ["linear_b", "quadratic_b", "factorial", "alternating"],
            },
            success_criterion=SuccessCriterion(
                metric="novel_proven_count", threshold=1, direction="above"
            ),
            compute_budget_seconds=600,
            priority=1,
        ),
        DiscoveryTask(
            task_id="ratio_univ_k1to5",
            domain=Domain.RATIO_UNIV,
            description="Verify L-formula universality for k=1..5 colored partitions + overpartitions",
            hypothesis_space={
                "families": ["k=1", "k=2", "k=3", "k=4", "k=5", "overpartitions"],
                "N_max": 5000,
                "precision_dps": 60,
            },
            success_criterion=SuccessCriterion(
                metric="L_gap_pct", threshold=0.1, direction="below"
            ),
            compute_budget_seconds=300,
            priority=3,
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════
# §6  CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MetaOrchestrator — Unified AI-Researcher over AI-Researchers"
    )
    parser.add_argument("--tasks", type=str, default="",
                        help="Path to JSON task file")
    parser.add_argument("--demo", action="store_true",
                        help="Run 3-domain demo (Ising + Ramanujan + Ratio)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print task queue without executing")
    args = parser.parse_args()

    if args.tasks:
        with open(args.tasks, encoding="utf-8") as f:
            raw = json.load(f)
        tasks = [
            DiscoveryTask(
                task_id=t["task_id"],
                domain=Domain(t["domain"]),
                description=t.get("description", ""),
                hypothesis_space=t.get("hypothesis_space", {}),
                success_criterion=SuccessCriterion(**t["success_criterion"]),
                compute_budget_seconds=t.get("compute_budget_seconds", 600),
                priority=t.get("priority", 5),
            )
            for t in raw
        ]
    elif args.demo:
        tasks = demo_tasks()
    else:
        tasks = demo_tasks()  # default to demo

    orchestrator = MetaOrchestrator(tasks)

    if args.dry_run:
        print("\nDRY RUN — Task Queue:")
        for i, t in enumerate(orchestrator.tasks, 1):
            print(f"  {i}. [{t.priority}] {t.task_id} ({t.domain.value}) — {t.description}")
            print(f"     Criterion: {t.success_criterion.metric} "
                  f"{t.success_criterion.direction} {t.success_criterion.threshold}")
            print(f"     Budget: {t.compute_budget_seconds}s | Hash: {t.pre_registration_hash}")
        return

    report = orchestrator.run()

    # Final summary
    print("\n" + "=" * 72)
    print(f"  SESSION COMPLETE: {report['passed']}/{report['total_tasks']} passed, "
          f"{report['novel_results']} novel")
    print(f"  Total wall time: {report['total_wall_time_seconds']:.1f}s")
    print("=" * 72)


if __name__ == "__main__":
    main()
