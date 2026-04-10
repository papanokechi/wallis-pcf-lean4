#!/usr/bin/env python3
"""
orchestrator.py — Supervisor for Ramanujan PCF discovery agents.

Manages up to 5 concurrent Python search agents on a single Windows PC,
handling resource contention, health monitoring, discovery aggregation,
and a live terminal dashboard.

Dependencies: stdlib + psutil
Target: Python 3.10+, Windows 11 (primary), Linux-compatible.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    print("psutil required: pip install psutil", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "CRITICAL": {"cpu": 95, "ram": 95},
    "HIGH":     {"cpu": 85, "ram": 88},
    "NORMAL":   {"cpu": 70, "ram": 80},
    "HEADROOM": {"cpu": 60, "ram": 75},
}

COOLDOWN_SECONDS = 120
POLL_INTERVAL_DEFAULT = 10
CRITICAL_CONSECUTIVE_LIMIT = 3  # after N consecutive CRITICAL ticks, escalate

LOG = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# 1. AgentSpec
# ---------------------------------------------------------------------------

@dataclass
class AgentSpec:
    name: str
    command: list[str]
    log_file: str
    tier: int
    status_file: str
    max_stale_seconds: int
    min_hit_rate: float
    process: subprocess.Popen | None = field(default=None, repr=False)
    state: str = "WAIT"          # RUN | SUSP | WAIT | STALL | BROKEN | CRASH
    suspended: bool = False
    restart_count: int = 0
    restart_timestamps: list[float] = field(default_factory=list)
    last_check: float = 0.0
    last_discoveries: int = 0
    prev_discoveries: int = 0    # for delta display
    last_known_cycle: int = -1   # track cycle advancement for stall detection
    pending_restart_at: float = 0.0  # deferred restart time (0 = none)


AGENTS = [
    AgentSpec(
        "generator",
        ["python", "-B", "ramanujan_breakthrough_generator.py", "--resume"],
        "ramanujan_discoveries.jsonl",
        tier=1,
        status_file="status_generator.json",
        max_stale_seconds=300,
        min_hit_rate=0.0,
    ),
    AgentSpec(
        "parallel",
        ["python", "-B", "parallel_engine.py"],
        "ramanujan_discoveries.jsonl",
        tier=2,
        status_file="status_parallel.json",
        max_stale_seconds=180,
        min_hit_rate=0.0,
    ),
    AgentSpec(
        "ising",
        ["python", "-B", "_pcf_search_Tc_3d_ising.py"],
        "pcf_tc_results.jsonl",
        tier=2,
        status_file="status_ising.json",
        max_stale_seconds=600,
        min_hit_rate=0.0,
    ),
    AgentSpec(
        "deep_space",
        ["python", "-B", "_deep_space_sweep.py"],
        "deep_space_discoveries.jsonl",
        tier=3,
        status_file="status_deep_space.json",
        max_stale_seconds=120,
        min_hit_rate=0.1,
    ),
    AgentSpec(
        "even_k_sweep",
        ["python", "-B", "_even_k_sweep.py"],
        "even_k_discoveries.jsonl",
        tier=3,
        status_file="status_even_k.json",
        max_stale_seconds=120,
        min_hit_rate=0.0,
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: str | Path) -> dict | None:
    """Read a JSON file, returning None on any failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSONL file, skipping bad lines."""
    entries: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    except Exception as exc:
        LOG.warning("Error reading %s: %s", path, exc)
    return entries


def _write_json(path: str | Path, data: dict) -> None:
    try:
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, str(path))
    except Exception as exc:
        LOG.warning("Failed to write %s: %s", path, exc)


def _file_mtime(path: str | Path) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 2. ResourceMonitor
# ---------------------------------------------------------------------------

class ResourceMonitor:
    """Polls system resource usage via psutil."""

    def __init__(self) -> None:
        self.cpu_pct: float = 0.0
        self.ram_pct: float = 0.0
        self.per_proc_cpu: dict[int, float] = {}
        self.thermal_ok: bool = True

    def poll(self) -> "ResourceMonitor":
        try:
            self.cpu_pct = psutil.cpu_percent(interval=2)
        except Exception:
            self.cpu_pct = 50.0

        try:
            self.ram_pct = psutil.virtual_memory().percent
        except Exception:
            self.ram_pct = 50.0

        self._poll_per_proc()
        self._poll_thermal()
        return self

    def _poll_per_proc(self) -> None:
        self.per_proc_cpu = {}
        try:
            for proc in psutil.process_iter(["pid", "cpu_percent"]):
                info = proc.info
                if info and info.get("cpu_percent") is not None:
                    self.per_proc_cpu[info["pid"]] = info["cpu_percent"]
        except Exception:
            pass

    def _poll_thermal(self) -> None:
        self.thermal_ok = True
        if not hasattr(psutil, "sensors_temperatures"):
            return
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return
            for _name, entries in temps.items():
                for entry in entries:
                    if entry.current and entry.current > 85:
                        self.thermal_ok = False
                        return
        except Exception:
            pass

    def level(self) -> str:
        """Return the current resource pressure level."""
        t = THRESHOLDS
        if self.cpu_pct >= t["CRITICAL"]["cpu"] or self.ram_pct >= t["CRITICAL"]["ram"]:
            return "CRITICAL"
        if self.cpu_pct >= t["HIGH"]["cpu"] or self.ram_pct >= t["HIGH"]["ram"]:
            return "HIGH"
        if self.cpu_pct < t["HEADROOM"]["cpu"] and self.ram_pct < t["HEADROOM"]["ram"]:
            return "HEADROOM"
        return "NORMAL"


# ---------------------------------------------------------------------------
# 3. AgentRegistry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Manages lifecycle of all agent processes."""

    def __init__(self, agents: list[AgentSpec], *, dry_run: bool = False) -> None:
        self.agents = {a.name: a for a in agents}
        self.dry_run = dry_run

    def get(self, name: str) -> AgentSpec | None:
        return self.agents.get(name)

    def all(self) -> list[AgentSpec]:
        return list(self.agents.values())

    def by_tier(self, tier: int) -> list[AgentSpec]:
        return [a for a in self.agents.values() if a.tier == tier]

    def running(self) -> list[AgentSpec]:
        return [a for a in self.agents.values() if a.process and a.process.poll() is None]

    # -- lifecycle -----------------------------------------------------------

    def start(self, name: str, extra_args: list[str] | None = None) -> bool:
        agent = self.agents.get(name)
        if agent is None:
            LOG.error("Unknown agent: %s", name)
            return False
        if agent.process and agent.process.poll() is None:
            LOG.debug("Agent %s already running (pid %d)", name, agent.process.pid)
            return True

        cmd = list(agent.command)
        if extra_args:
            cmd.extend(extra_args)

        # Check that the script file exists
        script = cmd[2] if len(cmd) > 2 else None
        if script and not Path(script).exists():
            LOG.warning("Script %s not found — skipping %s", script, name)
            agent.state = "WAIT"
            return False

        if self.dry_run:
            LOG.info("[DRY-RUN] Would start %s: %s", name, " ".join(cmd))
            agent.state = "RUN"
            return True

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            agent.process = proc
            agent.state = "RUN"
            agent.suspended = False
            LOG.info("Started %s (pid %d): %s", name, proc.pid, " ".join(cmd))
            return True
        except Exception as exc:
            LOG.error("Failed to start %s: %s", name, exc)
            agent.state = "CRASH"
            return False

    def suspend(self, name: str, reason: str = "") -> None:
        agent = self.agents.get(name)
        if not agent or not agent.process or agent.process.poll() is not None:
            return
        if agent.suspended:
            return
        if self.dry_run:
            LOG.info("[DRY-RUN] Would suspend %s (%s)", name, reason)
            agent.state = "SUSP"
            agent.suspended = True
            return
        try:
            p = psutil.Process(agent.process.pid)
            p.suspend()
            agent.suspended = True
            agent.state = "SUSP"
            LOG.info("Suspended %s (pid %d): %s", name, agent.process.pid, reason)
        except Exception as exc:
            LOG.warning("Could not suspend %s: %s", name, exc)

    def resume(self, name: str) -> None:
        agent = self.agents.get(name)
        if not agent or not agent.process or not agent.suspended:
            return
        if self.dry_run:
            LOG.info("[DRY-RUN] Would resume %s", name)
            agent.state = "RUN"
            agent.suspended = False
            return
        try:
            p = psutil.Process(agent.process.pid)
            p.resume()
            agent.suspended = False
            agent.state = "RUN"
            LOG.info("Resumed %s (pid %d)", name, agent.process.pid)
        except Exception as exc:
            LOG.warning("Could not resume %s: %s", name, exc)

    def kill(self, name: str) -> None:
        agent = self.agents.get(name)
        if not agent or not agent.process:
            return
        if self.dry_run:
            LOG.info("[DRY-RUN] Would kill %s", name)
            agent.process = None
            return
        try:
            if agent.suspended:
                try:
                    psutil.Process(agent.process.pid).resume()
                except Exception:
                    pass
            agent.process.terminate()
            try:
                agent.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent.process.kill()
            LOG.info("Killed %s", name)
        except Exception as exc:
            LOG.warning("Error killing %s: %s", name, exc)
        finally:
            agent.process = None
            agent.suspended = False

    def resume_all_suspended(self) -> None:
        """Resume every suspended agent (used during graceful shutdown)."""
        for agent in self.agents.values():
            if agent.suspended:
                self.resume(agent.name)


# ---------------------------------------------------------------------------
# 4. SchedulerPolicy
# ---------------------------------------------------------------------------

class SchedulerPolicy:
    """Resource-aware scheduling: suspend / resume agents by tier."""

    def __init__(self, registry: AgentRegistry, monitor: ResourceMonitor) -> None:
        self.registry = registry
        self.monitor = monitor
        self.cooldown_until: float = 0.0
        self.last_action: str = ""
        self.consecutive_critical: int = 0

    def step(self, state: ResourceMonitor) -> None:
        now = time.time()
        level = state.level()

        if level == "CRITICAL":
            self.consecutive_critical += 1
            self._handle_critical(now)
        else:
            self.consecutive_critical = 0

        if level == "HIGH":
            self._handle_high()
        elif level == "NORMAL":
            self._handle_normal(now)
        elif level == "HEADROOM":
            self._handle_headroom(now)

        self._persist_state(level)

    # -- handlers ------------------------------------------------------------

    def _handle_critical(self, now: float) -> None:
        LOG.warning("CRITICAL resources — suspending tier-2 and tier-3 (streak=%d)",
                    self.consecutive_critical)
        for a in self.registry.by_tier(3):
            self.registry.suspend(a.name, "CRITICAL resource pressure")
        for a in self.registry.by_tier(2):
            self.registry.suspend(a.name, "CRITICAL resource pressure (throttle)")

        # Escalation: if CRITICAL persists for N+ ticks, also suspend T1 generator
        if self.consecutive_critical >= CRITICAL_CONSECUTIVE_LIMIT:
            ram = self.monitor.ram_pct
            if ram >= 92:
                LOG.warning("ESCALATION: suspending tier-1 generator (RAM=%.0f%%, streak=%d)",
                            ram, self.consecutive_critical)
                for a in self.registry.by_tier(1):
                    self.registry.suspend(a.name, "CRITICAL escalation — RAM %.0f%%" % ram)

        self.cooldown_until = now + COOLDOWN_SECONDS
        self.last_action = "critical_suspend"

    def _handle_high(self) -> None:
        for a in self.registry.by_tier(3):
            self.registry.suspend(a.name, "HIGH resource pressure")
        self.last_action = "high_suspend_t3"

    def _handle_normal(self, now: float) -> None:
        if now < self.cooldown_until:
            return
        # Resume tier-1 agents that were escalation-suspended
        for a in self.registry.by_tier(1):
            if a.suspended:
                LOG.info("Resuming escalation-suspended tier-1 agent %s", a.name)
                self.registry.resume(a.name)
        # Resume tier-2 agents that were suspended
        for a in self.registry.by_tier(2):
            if a.suspended:
                self.registry.resume(a.name)
        # Resume tier-3 agents that were suspended
        for a in self.registry.by_tier(3):
            if a.suspended:
                self.registry.resume(a.name)
        self.last_action = "normal_resume"

    def _handle_headroom(self, now: float) -> None:
        if now < self.cooldown_until:
            return
        # Resume any suspended agents
        for a in self.registry.all():
            if a.suspended:
                self.registry.resume(a.name)

        # If all agents healthy, try launching even_k_sweep
        even_k = self.registry.get("even_k_sweep")
        if even_k and even_k.state == "WAIT" and even_k.process is None:
            if Path("_even_k_sweep.py").exists():
                self.registry.start("even_k_sweep")
        self.last_action = "headroom_expand"

    # -- persistence ---------------------------------------------------------

    def _persist_state(self, level: str) -> None:
        data = {
            "timestamp": _now_iso(),
            "resource_level": level,
            "last_action": self.last_action,
            "agents": {},
        }
        for a in self.registry.all():
            data["agents"][a.name] = {
                "state": a.state,
                "tier": a.tier,
                "suspended": a.suspended,
                "pid": a.process.pid if a.process and a.process.poll() is None else None,
            }
        _write_json("orchestrator_state.json", data)


# ---------------------------------------------------------------------------
# 5. HealthChecker
# ---------------------------------------------------------------------------

class HealthChecker:
    """Detects stalled, broken, and crashed agents; auto-restarts by tier."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self.sdi_last_check: float = 0.0

    def check_all(self) -> None:
        now = time.time()

        # Process deferred restarts first (non-blocking)
        for agent in self.registry.all():
            if agent.pending_restart_at and now >= agent.pending_restart_at:
                agent.pending_restart_at = 0.0
                LOG.info("Executing deferred restart of %s", agent.name)
                agent.restart_timestamps.append(now)
                agent.restart_count += 1
                self.registry.start(agent.name)

        for agent in self.registry.all():
            if agent.state == "WAIT":
                continue
            self._check_crash(agent, now)
            self._check_stall(agent, now)
            self._check_broken(agent)

        # SDI guard for generator
        if now - self.sdi_last_check >= 60:
            self._sdi_guard()
            self.sdi_last_check = now

    # -- crash ---------------------------------------------------------------

    def _check_crash(self, agent: AgentSpec, now: float) -> None:
        if agent.process is None:
            return
        exit_code = agent.process.poll()
        if exit_code is None:
            return
        # Process has exited
        LOG.error("Agent %s CRASHED with exit code %d", agent.name, exit_code)
        agent.state = "CRASH"
        agent.process = None
        agent.suspended = False

        if agent.tier == 1:
            self._schedule_restart(agent, delay=10, now=now)
        elif agent.tier == 2:
            self._schedule_restart(agent, delay=30, now=now, max_per_hour=3)
        else:
            LOG.info("Tier-3 agent %s crashed — awaiting manual intervention or headroom", agent.name)

    def _schedule_restart(
        self, agent: AgentSpec, delay: float, now: float, max_per_hour: int = 0
    ) -> None:
        # Prune old restart timestamps (older than 1 hour)
        one_hour_ago = now - 3600
        agent.restart_timestamps = [t for t in agent.restart_timestamps if t > one_hour_ago]

        if max_per_hour and len(agent.restart_timestamps) >= max_per_hour:
            LOG.warning(
                "Agent %s hit restart limit (%d/hr) — not restarting",
                agent.name,
                max_per_hour,
            )
            return

        LOG.info("Scheduling deferred restart of %s in %ds", agent.name, int(delay))
        agent.pending_restart_at = now + delay

    # -- stall ---------------------------------------------------------------

    def _check_stall(self, agent: AgentSpec, now: float) -> None:
        if agent.state in ("CRASH", "WAIT", "SUSP"):
            return

        # Generator: check cycle advancement OR state file mtime
        if agent.name == "generator":
            state_data = _read_json("ramanujan_state.json")
            if state_data:
                # Primary: check if cycle counter is advancing
                current_cycle = state_data.get("cycle", -1)
                if agent.last_known_cycle >= 0 and current_cycle > agent.last_known_cycle:
                    # Cycle advanced since last check — definitely alive
                    agent.last_known_cycle = current_cycle
                    if agent.state == "STALL":
                        LOG.info("Agent %s recovered from STALL (cycle %d)", agent.name, current_cycle)
                        agent.state = "RUN"
                    return
                agent.last_known_cycle = current_cycle

                # Fallback: check state file mtime (works even if cycle field unchanged)
                mtime = _file_mtime("ramanujan_state.json")
                if mtime is not None:
                    age = now - mtime
                    if age <= agent.max_stale_seconds:
                        if agent.state == "STALL":
                            agent.state = "RUN"
                        return

                # Only mark stall if state file exists but is old AND cycle not advancing
                try:
                    ts = datetime.fromisoformat(state_data["timestamp"])
                    age = (datetime.now() - ts).total_seconds()
                    if age > agent.max_stale_seconds:
                        LOG.warning("Agent %s STALLED (state %ds old, cycle stuck at %d)",
                                    agent.name, int(age), current_cycle)
                        agent.state = "STALL"
                except (ValueError, TypeError, KeyError):
                    pass
            return

        mtime = _file_mtime(agent.log_file)
        if mtime is None:
            # No log file yet — only stall if process has been running long enough
            if agent.process and agent.process.poll() is None:
                try:
                    create_time = psutil.Process(agent.process.pid).create_time()
                    if now - create_time > agent.max_stale_seconds:
                        LOG.warning("Agent %s STALLED (no log file after %ds)", agent.name,
                                    int(now - create_time))
                        agent.state = "STALL"
                except Exception:
                    pass
            return

        age = now - mtime
        if age > agent.max_stale_seconds:
            LOG.warning("Agent %s STALLED (log %ds stale)", agent.name, int(age))
            agent.state = "STALL"

    # -- broken --------------------------------------------------------------

    def _check_broken(self, agent: AgentSpec) -> None:
        if agent.min_hit_rate <= 0:
            return
        status = _read_json(agent.status_file)
        if not status:
            return
        evals = status.get("evals", 0)
        hits = status.get("hits", 0)
        if evals > 50_000 and hits == 0:
            LOG.error("Agent %s BROKEN (0 hits after %d evals)", agent.name, evals)
            agent.state = "BROKEN"
            if agent.name == "deep_space":
                LOG.info("Relaunching deep_space with --template-seeded")
                self.registry.kill("deep_space")
                self.registry.start("deep_space", extra_args=["--template-seeded"])

    # -- SDI guard -----------------------------------------------------------

    def _sdi_guard(self) -> None:
        state_data = _read_json("ramanujan_state.json")
        if not state_data:
            return
        sdi = state_data.get("structural_diversity_index")
        if sdi is not None and sdi < 3:
            LOG.warning("SDI rescue: injecting T=1.2 reheat (SDI=%d)", sdi)
            state_data["temperature"] = 1.2
            _write_json("ramanujan_state.json", state_data)


# ---------------------------------------------------------------------------
# 6. DiscoveryAggregator
# ---------------------------------------------------------------------------

class DiscoveryAggregator:
    """Merges all agent discovery logs into master_discoveries.jsonl."""

    MASTER_FILE = "master_discoveries.jsonl"

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self.prev_count: int = 0
        self.unique_count: int = 0
        self.best_digits: float = 0.0
        self.best_match: str = ""

    def run(self) -> None:
        # Collect all log files
        log_files: set[str] = set()
        for a in self.registry.all():
            log_files.add(a.log_file)

        # Read all entries
        all_entries: list[dict] = []
        for lf in log_files:
            all_entries.extend(_read_jsonl(lf))

        # Deduplicate by (tuple(a), tuple(b)), keep highest verified_digits
        best: dict[str, dict] = {}
        for entry in all_entries:
            a_val = entry.get("a")
            b_val = entry.get("b")
            if a_val is None or b_val is None:
                continue
            try:
                key = json.dumps([list(a_val), list(b_val)], sort_keys=True)
            except (TypeError, ValueError):
                continue
            vd = entry.get("verified_digits", 0) or 0
            existing = best.get(key)
            if existing is None or vd > (existing.get("verified_digits", 0) or 0):
                best[key] = entry

        self.prev_count = self.unique_count
        self.unique_count = len(best)
        new_since_last = self.unique_count - self.prev_count

        # Find best
        self.best_digits = 0.0
        self.best_match = ""
        for entry in best.values():
            vd = entry.get("verified_digits", 0) or 0
            if vd > self.best_digits:
                self.best_digits = vd
                self.best_match = entry.get("match", "?")

        # Write master file
        try:
            with open(self.MASTER_FILE, "w", encoding="utf-8") as f:
                for entry in sorted(best.values(),
                                    key=lambda e: -(e.get("verified_digits", 0) or 0)):
                    f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            LOG.warning("Failed to write %s: %s", self.MASTER_FILE, exc)

        LOG.info(
            "Aggregator: %d unique discoveries (+%d new), best: %s @ %.0f digits",
            self.unique_count, max(new_since_last, 0), self.best_match, self.best_digits,
        )

    def agent_discovery_count(self, agent: AgentSpec) -> int:
        """Count discoveries in an agent's log file."""
        entries = _read_jsonl(agent.log_file)
        return len(entries)


# ---------------------------------------------------------------------------
# 7. StatusDashboard
# ---------------------------------------------------------------------------

class StatusDashboard:
    """Terminal dashboard for orchestrator state."""

    def __init__(
        self,
        registry: AgentRegistry,
        monitor: ResourceMonitor,
        aggregator: DiscoveryAggregator,
        *,
        enabled: bool = True,
    ) -> None:
        self.registry = registry
        self.monitor = monitor
        self.aggregator = aggregator
        self.enabled = enabled
        self._use_rich = False
        if enabled:
            try:
                from rich.console import Console
                from rich.table import Table
                self._use_rich = True
                self._console = Console()
            except ImportError:
                pass

    def render(self) -> None:
        if not self.enabled:
            return
        if self._use_rich:
            self._render_rich()
        else:
            self._render_plain()

    # -- rich ----------------------------------------------------------------

    def _render_rich(self) -> None:
        from rich.console import Console
        from rich.table import Table

        console = self._console
        now_str = _now_iso()
        thermal = "OK" if self.monitor.thermal_ok else "HOT!"
        level = self.monitor.level()

        console.print()
        console.rule(f"[bold cyan]ORCHESTRATOR[/]  —  {now_str}  [{level}]")
        console.print(
            f"  CPU: [{'red' if self.monitor.cpu_pct > 85 else 'green'}]"
            f"{self.monitor.cpu_pct:.0f}%[/]  "
            f"RAM: [{'red' if self.monitor.ram_pct > 88 else 'green'}]"
            f"{self.monitor.ram_pct:.0f}%[/]  "
            f"Thermal: {thermal}"
        )

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Agent", style="cyan", width=14)
        table.add_column("Tier", justify="center", width=6)
        table.add_column("Status", justify="center", width=8)
        table.add_column("Cycle/Eval", justify="right", width=11)
        table.add_column("Discoveries", justify="right", width=13)

        for agent in self.registry.all():
            tier_str = f"T{agent.tier}"
            status_str = self._status_markup_rich(agent)
            cycle_str = self._cycle_str(agent)
            disc_str = self._disc_str(agent)
            table.add_row(agent.name, tier_str, status_str, cycle_str, disc_str)

        console.print(table)
        console.print(
            f"  Master discoveries: {self.aggregator.unique_count} unique  |  "
            f"Best: {self.aggregator.best_match} @ {self.aggregator.best_digits:.0f}d"
        )
        console.print()

    def _status_markup_rich(self, agent: AgentSpec) -> str:
        s = agent.state
        if s == "RUN":
            return "[green]RUN[/]"
        if s == "SUSP":
            return "[yellow]SUSP[/]"
        if s == "STALL":
            return "[yellow]STALL[/]"
        if s == "BROKEN":
            return "[red]BROKEN[/]"
        if s == "CRASH":
            return "[red]CRASH[/]"
        return "[dim]WAIT[/]"

    # -- plain ---------------------------------------------------------------

    def _render_plain(self) -> None:
        now_str = _now_iso()
        thermal = "OK" if self.monitor.thermal_ok else "HOT!"
        level = self.monitor.level()

        W = 60
        print()
        print("+" + "=" * W + "+")
        print(f"|  ORCHESTRATOR  —  {now_str:<{W - 20}}|")
        print("+" + "=" * W + "+")
        print(f"|  CPU: {self.monitor.cpu_pct:4.0f}%  RAM: {self.monitor.ram_pct:4.0f}%  "
              f"Thermal: {thermal:<4}  Level: {level:<10}|")
        print("+" + "-" * W + "+")
        hdr = f"| {'Agent':<14} {'Tier':>4}  {'Status':>6}  {'Cycle/Eval':>10}  {'Discoveries':>12} |"
        print(hdr)
        print("+" + "-" * W + "+")

        for agent in self.registry.all():
            tier_str = f"T{agent.tier}"
            status = agent.state
            cycle = self._cycle_str(agent)
            disc = self._disc_str(agent)
            line = f"| {agent.name:<14} {tier_str:>4}  {status:>6}  {cycle:>10}  {disc:>12} |"
            print(line)

        print("+" + "-" * W + "+")
        print(f"|  Master discoveries: {self.aggregator.unique_count} unique  |  "
              f"Best: {self.aggregator.best_match} @ {self.aggregator.best_digits:.0f}d")
        print("+" + "=" * W + "+")
        print()

    # -- helpers -------------------------------------------------------------

    def _cycle_str(self, agent: AgentSpec) -> str:
        """Read cycle or eval count from status file."""
        status = _read_json(agent.status_file)
        if status:
            cycle = status.get("cycle")
            evals = status.get("evals")
            if evals and evals > 1000:
                return f"{evals // 1000}K"
            if cycle is not None:
                return f"c={cycle}"

        # For generator, try ramanujan_state.json
        if agent.name == "generator":
            state = _read_json("ramanujan_state.json")
            if state and "cycle" in state:
                return f"c={state['cycle']}"

        return "—"

    def _disc_str(self, agent: AgentSpec) -> str:
        count = self.aggregator.agent_discovery_count(agent)
        agent.last_discoveries = count
        delta = count - agent.prev_discoveries
        agent.prev_discoveries = count
        if count == 0 and agent.state == "WAIT":
            return "—"
        suffix = ""
        if agent.state == "BROKEN":
            suffix = " \u2717BROKEN"
        if delta > 0:
            return f"{count} (\u2191{delta}){suffix}"
        return f"{count}{suffix}"


# ---------------------------------------------------------------------------
# 8. Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_file: str, level: int = logging.INFO) -> None:
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)


# ---------------------------------------------------------------------------
# 9. Main loop
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ramanujan PCF agent orchestrator")
    p.add_argument("--dry-run", action="store_true",
                   help="Print decisions but do not suspend/kill/restart anything")
    p.add_argument("--no-dashboard", action="store_true",
                   help="Suppress terminal dashboard (log-only mode)")
    p.add_argument("--interval", type=int, default=POLL_INTERVAL_DEFAULT,
                   help="Poll interval in seconds (default: 10)")
    p.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING"], default="INFO",
                   help="Logging verbosity (default: INFO)")
    p.add_argument("--config", type=str, default=None,
                   help="Path to external config file (reserved for future use)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    log_level = getattr(logging, args.log_level, logging.INFO)
    setup_logging("orchestrator.log", level=log_level)
    LOG.info("Orchestrator starting (interval=%ds, dry_run=%s)", args.interval, args.dry_run)

    if args.config:
        LOG.info("--config flag noted (%s) but not yet implemented", args.config)

    registry = AgentRegistry(AGENTS, dry_run=args.dry_run)
    monitor = ResourceMonitor()
    scheduler = SchedulerPolicy(registry, monitor)
    health = HealthChecker(registry)
    aggregator = DiscoveryAggregator(registry)
    dashboard = StatusDashboard(registry, monitor, aggregator, enabled=not args.no_dashboard)

    try:
        # Start tier-1 agent immediately
        registry.start("generator")

        # Start tier-2 agents after 10s delay
        time.sleep(10)
        registry.start("parallel")
        registry.start("ising")

        # Tier-3 agents start only if headroom available
        # (scheduler handles this in its first HEADROOM check)

        tick = 0
        while True:
            state = monitor.poll()
            scheduler.step(state)

            if tick % 3 == 0:  # every 30s  (tick * interval)
                health.check_all()
                dashboard.render()

            if tick % 6 == 0:  # every 60s
                aggregator.run()

            tick += 1
            time.sleep(args.interval)

    except KeyboardInterrupt:
        LOG.info("Shutting down — resuming all suspended agents")
        registry.resume_all_suspended()
        LOG.info("Orchestrator stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
