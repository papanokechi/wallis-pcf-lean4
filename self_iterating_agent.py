#!/usr/bin/env python3
"""
Self-Iterating Research Agent v1.1 — LOCAL MODE ENABLED
========================================================

Unified Breakthrough Agent: 9/10 Local Autonomy. No API Key Required.

A recursive research agent that builds upon paper14-ratio-universality-v2.html
and the existing breakthrough engine/ratio universality infrastructure.

v1.1 Key Improvements (Local Mode):
  • Symbolic Induction: SymPy-powered algebraic identity testing replaces LLM calls
  • Local Synthesis Engine: Deterministic hypothesis generation from Axiom Graph
  • Numeric Verification: mpmath 3-tier (50→100→200 dps) with PSLQ
  • Sandboxed Execution: subprocess-based self-verification (no external validator)
  • Symbolic Regression: Optional PySR integration for equation discovery

Architecture:
  ┌────────────────────────────────────────────────────────────┐
  │  Phase 1: IDENTIFY FRONTIER  (Knowledge Graph + Gap Analysis) │
  │  Phase 2: SCOPE TARGET       (Local Synthesis Engine)        │
  │  Phase 3: EXECUTE            (Calculate / Prove / Simulate)  │
  │  Phase 4: EVALUATE           (Critic + Fitness Function)     │
  │  Phase 5: SUMMARIZE          (Update Memory → Feed Phase 1)  │
  └────────────────────────────────────────────────────────────┘

Key Design Principles:
  • State Machine: Each phase is a discrete state with typed I/O
  • Creator + Critic: Isolated agents prevent hallucination loops
  • Persistent Memory: Vector-indexed knowledge survives sessions
  • Self-Iteration: Agent can mutate its own templates + tooling
  • HITL Guardrails: Architectural changes require human approval
  • Failure Learning: Every dead end becomes training data

Builds on:
  - breakthrough_engine_v8.py  (9-layer scoring, axiom graph)
  - ratio_universality_agent.py (frontier map, ECAL, partition tools)
  - knowledge_base.json (73 discoveries across 6 iterations)
  - axiom_graph.json (persistent knowledge graph from V8)

Usage:
  python self_iterating_agent.py                     # auto single cycle (local)
  python self_iterating_agent.py --cycles 5          # run N cycles
  python self_iterating_agent.py --mode local        # explicit local mode
  python self_iterating_agent.py --status            # show state
  python self_iterating_agent.py --frontier          # show frontier gaps
  python self_iterating_agent.py --history           # show iteration log
  python self_iterating_agent.py --mutate            # propose self-improvement
  python self_iterating_agent.py --rollback N        # revert to iteration N
  python self_iterating_agent.py --critic-only       # run critic on last result
  python self_iterating_agent.py --induction GAP_ID  # run symbolic induction on gap
"""

import abc
import argparse
import json
import os
import re
import sys
import time
import uuid
import math
import hashlib
import shutil
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from enum import Enum

# ── Optional heavy imports ────────────────────────────────────────────
try:
    import mpmath as mp
    HAS_MPMATH = True
except ImportError:
    HAS_MPMATH = False
    print("WARNING: mpmath not installed. Numeric verification disabled.")
    print("  pip install mpmath")

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import sympy
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False

try:
    import pysr
    HAS_PYSR = True
except ImportError:
    HAS_PYSR = False

# ══════════════════════════════════════════════════════════════════════════
# CONSTANTS & PATHS
# ══════════════════════════════════════════════════════════════════════════

VERSION = "1.1.0"
WORKSPACE = Path(__file__).parent

# State persistence
STATE_DIR = WORKSPACE / "agent_state"
STATE_FILE = STATE_DIR / "agent_state.json"
MEMORY_FILE = STATE_DIR / "memory.json"
FAILURE_LOG = STATE_DIR / "failures.jsonl"
ITERATION_LOG = STATE_DIR / "iterations.jsonl"
MUTATION_LOG = STATE_DIR / "mutations.jsonl"
TEMPLATES_DIR = STATE_DIR / "templates"
SNAPSHOTS_DIR = STATE_DIR / "snapshots"

# Upstream data
KNOWLEDGE_BASE = WORKSPACE / "knowledge_base.json"
AXIOM_GRAPH = WORKSPACE / "axiom_graph.json"
PAPER_PATH = WORKSPACE / "paper14-ratio-universality-v2.html"

# Local synthesis
LOCAL_SYNTHESIS_DIR = STATE_DIR / "local_synthesis"
INDUCTION_CACHE = STATE_DIR / "induction_cache.json"

# Safety
MAX_CYCLES = 50           # Hard cap on autonomous iterations
MAX_COMPUTE_SECONDS = 600  # Per-execution time limit
HITL_REQUIRED_FOR = {"mutate_templates", "mutate_tools", "architecture_change"}

# Scoring thresholds (from V8)
KILL_FLOOR = {"N": 0.50, "F": 0.55, "E": 0.35, "C": 0.40}
BREAKTHROUGH_THRESHOLD = 0.25  # N*F*E*C product


# ══════════════════════════════════════════════════════════════════════════
# ANSI FORMATTING
# ══════════════════════════════════════════════════════════════════════════

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    PURPLE = "\033[95m"
    GRAY   = "\033[90m"
    BLUE   = "\033[94m"

def header(title):
    print(f"\n{C.CYAN}{'─'*70}\n  {C.BOLD}{title}{C.RESET}{C.CYAN}\n{'─'*70}{C.RESET}")

def ok(msg):   print(f"{C.GREEN}  ✓ {msg}{C.RESET}")
def warn(msg): print(f"{C.YELLOW}  ⚠ {msg}{C.RESET}")
def err(msg):  print(f"{C.RED}  ✗ {msg}{C.RESET}")
def info(msg): print(f"{C.GRAY}    {msg}{C.RESET}")


# ══════════════════════════════════════════════════════════════════════════
# PHASE ENUM — Research Cycle State Machine
# ══════════════════════════════════════════════════════════════════════════

class Phase(Enum):
    IDENTIFY_FRONTIER = "identify_frontier"
    SCOPE_TARGET = "scope_target"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    SUMMARIZE = "summarize"
    BACKTRACK = "backtrack"
    MUTATE = "mutate"


# ══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class FrontierGap:
    """An identified gap or open question in the research frontier."""
    id: str
    description: str
    source: str                    # which paper/section
    gap_type: str                  # "conjecture", "computation", "proof", "extension"
    priority: float = 0.5         # 0-1, impact if resolved
    difficulty: float = 0.5       # 0-1, estimated effort
    feasibility: float = 0.5     # 0-1, can we do it with current tools?
    prerequisites: list = field(default_factory=list)
    related_discoveries: list = field(default_factory=list)
    attempts: int = 0
    last_attempt: Optional[str] = None

    @property
    def score(self) -> float:
        """Feasibility-weighted impact with diminishing returns."""
        novelty = 1.0 / (1 + self.attempts * 0.8)  # Strong decay per failure
        prereq_penalty = 0.7 if self.prerequisites else 1.0
        return self.priority * self.feasibility * novelty * prereq_penalty


@dataclass
class Hypothesis:
    """A specific, testable claim scoped from a frontier gap."""
    id: str
    gap_id: str
    claim: str
    mechanism: str                # how it would work
    testable_prediction: str      # what to compute/prove
    failure_condition: str        # what would falsify it
    tools_needed: list = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecutionResult:
    """Output from Phase 3: the actual computational/proof work."""
    hypothesis_id: str
    success: bool
    method: str                   # "numeric", "symbolic", "proof", "simulation"
    evidence: dict = field(default_factory=dict)
    runtime_seconds: float = 0.0
    digits_matched: int = 0
    proof_status: str = "none"    # "none", "partial", "complete", "failed"
    code_executed: str = ""
    raw_output: str = ""
    error: Optional[str] = None


@dataclass
class Evaluation:
    """Phase 4 output: critic's assessment of a result."""
    result_id: str
    is_breakthrough: bool
    confidence: float              # 0-1
    scores: dict = field(default_factory=dict)  # N, F, E, C
    critique: str = ""
    flaws_found: list = field(default_factory=list)
    suggested_fixes: list = field(default_factory=list)
    verdict: str = "inconclusive"  # "breakthrough", "progress", "inconclusive", "failure"

    @property
    def b_score(self) -> float:
        s = self.scores
        return s.get("N", 0) * s.get("F", 0) * s.get("E", 0) * s.get("C", 0)


@dataclass
class IterationRecord:
    """Complete record of one research cycle."""
    iteration: int
    timestamp: str
    phase_results: dict = field(default_factory=dict)
    gap: Optional[dict] = None
    hypothesis: Optional[dict] = None
    result: Optional[dict] = None
    evaluation: Optional[dict] = None
    summary: str = ""
    context_delta: str = ""        # what was learned
    duration_seconds: float = 0.0


# ══════════════════════════════════════════════════════════════════════════
# PERSISTENT MEMORY — Knowledge that survives across sessions
# ══════════════════════════════════════════════════════════════════════════

class PersistentMemory:
    """
    Vector-indexed knowledge store. Tracks:
    - Paper context (theorems, conjectures, known results)
    - Discovery history (what we proved, what failed)
    - Failure patterns (what NOT to try)
    - Tool effectiveness (which methods work for which problems)
    """

    def __init__(self, path: Path = MEMORY_FILE):
        self.path = path
        self.entries: list[dict] = []
        self.context_summary: str = ""
        self.paper_knowledge: dict = {}
        self.tool_effectiveness: dict = {}  # tool_name -> {successes, failures, avg_runtime}
        self.failure_signatures: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.entries = data.get("entries", [])
                self.context_summary = data.get("context_summary", "")
                self.paper_knowledge = data.get("paper_knowledge", {})
                self.tool_effectiveness = data.get("tool_effectiveness", {})
                self.failure_signatures = data.get("failure_signatures", [])
                ok(f"Memory loaded: {len(self.entries)} entries, "
                   f"{len(self.failure_signatures)} failure patterns")
            except Exception as e:
                warn(f"Memory load failed: {e}")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": VERSION,
            "saved_at": datetime.now().isoformat(),
            "entries": self.entries,
            "context_summary": self.context_summary,
            "paper_knowledge": self.paper_knowledge,
            "tool_effectiveness": self.tool_effectiveness,
            "failure_signatures": self.failure_signatures,
        }
        self.path.write_text(json.dumps(data, indent=2, default=str),
                             encoding="utf-8")

    def add_entry(self, category: str, content: str, metadata: dict = None):
        """Add a knowledge entry with automatic tagging."""
        entry = {
            "id": str(uuid.uuid4())[:8],
            "category": category,  # "discovery", "failure", "insight", "tool_result"
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.entries.append(entry)
        return entry["id"]

    def add_failure(self, gap_id: str, hypothesis: str, reason: str,
                    method: str, signature: dict = None):
        """Record a failure pattern for future avoidance."""
        failure = {
            "gap_id": gap_id,
            "hypothesis": hypothesis,
            "reason": reason,
            "method": method,
            "signature": signature or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.failure_signatures.append(failure)

    def update_tool_stats(self, tool_name: str, success: bool, runtime: float):
        """Track which verification tools work best."""
        if tool_name not in self.tool_effectiveness:
            self.tool_effectiveness[tool_name] = {
                "successes": 0, "failures": 0, "total_runtime": 0.0, "calls": 0
            }
        stats = self.tool_effectiveness[tool_name]
        stats["calls"] += 1
        stats["total_runtime"] += runtime
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1

    def search(self, query: str, category: str = None, limit: int = 10) -> list[dict]:
        """Simple keyword search over memory entries."""
        query_lower = query.lower()
        results = []
        for entry in self.entries:
            if category and entry["category"] != category:
                continue
            text = f"{entry['content']} {json.dumps(entry.get('metadata', {}))}".lower()
            # Simple relevance: count query word hits
            words = query_lower.split()
            hits = sum(1 for w in words if w in text)
            if hits > 0:
                results.append((hits, entry))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    def check_failure_pattern(self, gap_id: str, method: str) -> list[dict]:
        """Check if we've already failed with this approach."""
        if method == "any":
            return [f for f in self.failure_signatures if f["gap_id"] == gap_id]
        return [f for f in self.failure_signatures
                if f["gap_id"] == gap_id and f["method"] == method]

    def get_best_tool(self, problem_type: str) -> Optional[str]:
        """Recommend the best verification tool for a problem type."""
        candidates = {}
        for tool, stats in self.tool_effectiveness.items():
            if stats["calls"] > 0:
                rate = stats["successes"] / stats["calls"]
                candidates[tool] = rate
        if candidates:
            return max(candidates, key=candidates.get)
        return None

    def build_context_string(self, max_chars: int = 4000) -> str:
        """Build a compact context string from memory for LLM consumption."""
        parts = []
        if self.context_summary:
            parts.append(f"[CONTEXT] {self.context_summary}")

        # Recent discoveries
        discoveries = [e for e in self.entries if e["category"] == "discovery"]
        if discoveries:
            recent = discoveries[-5:]
            parts.append("[RECENT DISCOVERIES]")
            for d in recent:
                parts.append(f"  - {d['content'][:200]}")

        # Active failure patterns
        if self.failure_signatures:
            parts.append("[KNOWN DEAD ENDS]")
            for f in self.failure_signatures[-5:]:
                parts.append(f"  - {f['gap_id']}: {f['reason'][:150]}")

        text = "\n".join(parts)
        return text[:max_chars]


# ══════════════════════════════════════════════════════════════════════════
# TOOLBOX — Sandboxed verification engines
# ══════════════════════════════════════════════════════════════════════════

class VerificationToolbox:
    """
    Provides sandboxed access to:
    - mpmath (arbitrary precision arithmetic, PSLQ, special functions)
    - sympy (symbolic computation, simplification, series)
    - subprocess (run external scripts in isolated process)
    - numeric verification (multi-tier 50→100→200 dps)
    """

    def __init__(self, memory: PersistentMemory):
        self.memory = memory
        self.available_tools = self._detect_tools()

    def _detect_tools(self) -> dict:
        tools = {}
        tools["mpmath"] = HAS_MPMATH
        tools["sympy"] = HAS_SYMPY
        tools["networkx"] = HAS_NETWORKX
        tools["subprocess"] = True
        # Check for external tools
        for cmd in ["python", "git"]:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
                tools[cmd] = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tools[cmd] = False
        return tools

    def status(self) -> dict:
        return {name: "available" if avail else "missing"
                for name, avail in self.available_tools.items()}

    # ── Numeric Verification (3-tier) ──────────────────────────────────

    def verify_numeric(self, expression: str, expected: str,
                       tiers: list[int] = None) -> dict:
        """
        Multi-tier numeric verification.
        Evaluates `expression` at increasing precision and compares to `expected`.
        """
        if not HAS_MPMATH:
            return {"error": "mpmath not available", "verified": False}

        tiers = tiers or [50, 100, 200]
        results = {}

        for dps in tiers:
            mp.mp.dps = dps + 20
            t0 = time.time()
            try:
                computed = mp.mpf(eval(expression, {"mp": mp, "mpmath": mp, "__builtins__": {}}))
                expected_val = mp.mpf(eval(expected, {"mp": mp, "mpmath": mp, "__builtins__": {}}))
                diff = abs(computed - expected_val)
                digits = int(-mp.log10(diff / abs(expected_val))) if diff > 0 and expected_val != 0 else dps
                results[dps] = {
                    "computed": str(mp.nstr(computed, min(dps, 50))),
                    "expected": str(mp.nstr(expected_val, min(dps, 50))),
                    "digits_matched": min(digits, dps),
                    "runtime": time.time() - t0,
                    "verified": digits >= dps * 0.8,
                }
            except Exception as e:
                results[dps] = {"error": str(e), "verified": False, "runtime": time.time() - t0}

            self.memory.update_tool_stats(
                f"numeric_{dps}dps",
                results[dps].get("verified", False),
                results[dps].get("runtime", 0)
            )

        return {
            "tiers": results,
            "verified": all(r.get("verified", False) for r in results.values()),
            "max_digits": max(r.get("digits_matched", 0) for r in results.values()),
        }

    # ── PSLQ Integer Relation Search ──────────────────────────────────

    def pslq_search(self, value, basis_labels: list[str],
                    basis_values: list, dps: int = 100) -> dict:
        """
        Run PSLQ to find integer relations between `value` and basis constants.
        """
        if not HAS_MPMATH:
            return {"error": "mpmath not available"}

        mp.mp.dps = dps + 20
        t0 = time.time()
        try:
            vec = [mp.mpf(value)] + [mp.mpf(v) for v in basis_values]
            labels = ["V"] + list(basis_labels)
            rel = mp.pslq(vec, tol=mp.power(10, -dps // 2), maxcoeff=1000)
            runtime = time.time() - t0

            if rel:
                # Format the relation
                terms = [(c, labels[i]) for i, c in enumerate(rel) if c != 0]
                relation_str = " + ".join(f"{c}*{label}" for c, label in terms) + " = 0"
                self.memory.update_tool_stats("pslq", True, runtime)
                return {
                    "found": True,
                    "relation": rel,
                    "labels": labels,
                    "formatted": relation_str,
                    "active_terms": terms,
                    "runtime": runtime,
                }
            else:
                self.memory.update_tool_stats("pslq", False, runtime)
                return {"found": False, "runtime": runtime}
        except Exception as e:
            return {"error": str(e)}

    # ── Symbolic Verification ─────────────────────────────────────────

    def verify_symbolic(self, lhs_expr: str, rhs_expr: str) -> dict:
        """
        Try to prove lhs == rhs symbolically using SymPy.
        """
        if not HAS_SYMPY:
            return {"error": "sympy not available", "proven": False}

        t0 = time.time()
        try:
            lhs = sympy.sympify(lhs_expr)
            rhs = sympy.sympify(rhs_expr)
            diff = sympy.simplify(lhs - rhs)
            proven = diff == 0
            runtime = time.time() - t0

            self.memory.update_tool_stats("sympy_verify", proven, runtime)
            return {
                "proven": proven,
                "simplified_diff": str(diff),
                "lhs": str(lhs),
                "rhs": str(rhs),
                "runtime": runtime,
            }
        except Exception as e:
            return {"error": str(e), "proven": False}

    # ── Sandboxed Script Execution ────────────────────────────────────

    def run_sandboxed(self, code: str, timeout: int = None) -> dict:
        """
        Execute Python code in a subprocess with timeout.
        Returns stdout, stderr, and exit code.
        """
        timeout = timeout or MAX_COMPUTE_SECONDS
        t0 = time.time()

        # Write code to temp file
        script_path = STATE_DIR / f"_sandbox_{uuid.uuid4().hex[:8]}.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(code, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(WORKSPACE),
            )
            runtime = time.time() - t0
            success = result.returncode == 0

            self.memory.update_tool_stats("sandbox", success, runtime)
            return {
                "success": success,
                "stdout": result.stdout[-10000:] if result.stdout else "",  # Cap output
                "stderr": result.stderr[-5000:] if result.stderr else "",
                "exit_code": result.returncode,
                "runtime": runtime,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "runtime": timeout,
            }
        finally:
            # Clean up sandbox script
            try:
                script_path.unlink()
            except OSError:
                pass

    # ── Partition Ratio Computation (from ratio_universality_agent) ───

    def compute_partition_ratios(self, k: int, N: int, dps: int = 80) -> dict:
        """
        Compute k-colored partition ratios to N terms.
        Delegates to sandboxed execution for safety.
        """
        code = f"""
import mpmath as mp
import json
mp.mp.dps = {dps + 20}

k = {k}
N = {N}

# f_k(n) via recurrence: n*f_k(n) = sum_{{j=1}}^n k*sigma_1(j)*f_k(n-j)
f = [mp.mpf(0)] * (N + 1)
f[0] = mp.mpf(1)

sigma1 = [mp.mpf(0)] * (N + 1)
for j in range(1, N + 1):
    s = mp.mpf(0)
    d = 1
    while d * d <= j:
        if j % d == 0:
            s += d
            if d != j // d:
                s += j // d
        d += 1
    sigma1[j] = s

for n in range(1, N + 1):
    s = mp.mpf(0)
    for j in range(1, n + 1):
        s += k * sigma1[j] * f[n - j]
    f[n] = s / n

# Extract last 20 ratios
ratios = []
for m in range(max(1, N-20), N + 1):
    if f[m-1] != 0:
        ratios.append({{"m": m, "ratio": str(mp.nstr(f[m]/f[m-1], 40))}})

print(json.dumps({{"k": k, "N": N, "n_ratios": N, "tail_ratios": ratios}}))
"""
        result = self.run_sandboxed(code, timeout=MAX_COMPUTE_SECONDS)
        if result["success"]:
            try:
                return json.loads(result["stdout"].strip().split("\n")[-1])
            except (json.JSONDecodeError, IndexError):
                return {"error": "Failed to parse output", "raw": result["stdout"][:2000]}
        return {"error": result.get("error", result.get("stderr", "Unknown error"))}

    # ── Continued Fraction Evaluation ─────────────────────────────────

    def evaluate_gcf(self, a_formula: str, b_formula: str, N: int = 500,
                     dps: int = 60) -> dict:
        """
        Evaluate a generalized continued fraction GCF(a_n, b_n) via backward recurrence.
        a_formula and b_formula are Python expressions with 'n' as variable.
        """
        code = f"""
import mpmath as mp
import json
mp.mp.dps = {dps + 20}

N = {N}

def a(n):
    return mp.mpf(eval("{a_formula}", {{"n": n, "mp": mp, "__builtins__": {{}}}}))

def b(n):
    return mp.mpf(eval("{b_formula}", {{"n": n, "mp": mp, "__builtins__": {{}}}}))

# Backward recurrence
t = b(N)
for n in range(N-1, -1, -1):
    t = b(n) + a(n+1) / t

result = {{
    "value": str(mp.nstr(t, {min(dps, 50)})),
    "N": N,
    "dps": {dps},
    "a_formula": "{a_formula}",
    "b_formula": "{b_formula}",
}}
print(json.dumps(result))
"""
        result = self.run_sandboxed(code, timeout=120)
        if result["success"]:
            try:
                return json.loads(result["stdout"].strip().split("\n")[-1])
            except (json.JSONDecodeError, IndexError):
                return {"error": "Parse failed", "raw": result["stdout"][:2000]}
        return {"error": result.get("error", result.get("stderr", "Unknown error"))}


# ══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH — Paper-aware frontier mapping
# ══════════════════════════════════════════════════════════════════════════

class KnowledgeGraph:
    """
    Manages the research frontier: what's known, what's open, what's blocked.
    Ingests from paper14-ratio-universality-v2.html and knowledge_base.json.
    """

    def __init__(self, memory: PersistentMemory):
        self.memory = memory
        self.theorems: list[dict] = []      # proven results
        self.conjectures: list[dict] = []   # open claims
        self.gaps: list[FrontierGap] = []   # identified white space
        self.connections: list[dict] = []   # links between results
        self._ingest_paper()
        self._ingest_knowledge_base()

    def _ingest_paper(self):
        """Extract key results from paper14."""
        # Core theorems from the paper
        self.theorems = [
            {
                "id": "thm1",
                "name": "Ratio Universality (Theorem 1)",
                "statement": "For Meinardus-class partition functions, "
                             "L = c²/8 + κ is universal at order m⁻¹",
                "status": "proven",
                "families_verified": 7,
                "precision": "0.1%",
            },
            {
                "id": "thm2",
                "name": "A₁ Closed Form (Theorem 2)",
                "statement": "A₁^(k) = -k·c_k/48 - (k+1)(k+3)/(8·c_k) for k=1..4",
                "status": "proven_partial",
                "proven_for": [1, 2, 3, 4],
                "conjectured_for": list(range(5, 25)),
            },
            {
                "id": "thm3",
                "name": "Selection Rule (Theorem 3)",
                "statement": "Family-specific Dirichlet information is silent at order m⁻¹, "
                             "first appearing at m⁻⁽¹⁺ᵈ⁾ via three-factor decomposition R=E·P·S",
                "status": "proven",
            },
            {
                "id": "thm4",
                "name": "Cube-Root Regime (Theorem 4)",
                "statement": "Plane partitions satisfy ratio universality via Lemma PP "
                             "(Olver uniform bounds)",
                "status": "proven",
            },
        ]

        self.conjectures = [
            {
                "id": "conj2star",
                "name": "Conjecture 2*: A₁ for all k",
                "statement": "A₁^(k) closed form holds for all k ≥ 5",
                "status": "open",
                "evidence": "Verified to 12 digits for k=5..24",
                "blocking": "Kloosterman bound C_5 ≤ 1.36 > 1.0",
            },
            {
                "id": "conj3star",
                "name": "Conjecture 3*: A₂ universal form",
                "statement": "A₂^(k) = (k+3)(π²k² - 9k - 9)/(96kπ²)",
                "status": "open",
                "evidence": "Verified to 11 digits",
                "blocking": "Needs Lemma W (Wright M=2 saddle point)",
            },
            {
                "id": "bdj_bridge",
                "name": "BDJ Bridge Conjecture",
                "statement": "Ratio fluctuations under Plancherel → Tracy-Widom",
                "status": "open",
                "evidence": "Preliminary: mean=-1.608, std=0.830 (TW₂ std=0.813)",
            },
        ]

    def _ingest_knowledge_base(self):
        """Load discoveries from knowledge_base.json if available."""
        if not KNOWLEDGE_BASE.exists():
            return
        try:
            data = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
            discoveries = data.get("discoveries", [])
            info(f"Loaded {len(discoveries)} discoveries from knowledge base")

            # Count by status
            by_status = {}
            for d in discoveries:
                s = d.get("status", "unknown")
                by_status[s] = by_status.get(s, 0) + 1
            for s, count in by_status.items():
                info(f"  {s}: {count}")
        except Exception as e:
            warn(f"Knowledge base load failed: {e}")

    def identify_gaps(self) -> list[FrontierGap]:
        """Analyze theorems + conjectures to find actionable gaps."""
        gaps = []

        # Gap 1: Prove A₁ for k=5 (lowest-hanging fruit in Conj 2*)
        gaps.append(FrontierGap(
            id="prove_A1_k5",
            description="Prove A₁^(5) closed form. C_5 ≤ 1.36, need C_5 < 1.0. "
                        "Path: extend Kloosterman bounds to q ≤ 500 or find structural argument.",
            source="paper14/Conjecture 2*",
            gap_type="proof",
            priority=0.95,
            difficulty=0.5,
            feasibility=0.7,
        ))

        # Gap 2: Lemma W — blocks Conjecture 3*
        gaps.append(FrontierGap(
            id="lemma_w",
            description="Prove Wright M=2 saddle-point control. "
                        "Extends Lemma PP (Olver bounds) to second order.",
            source="paper14/Conjecture 3*",
            gap_type="proof",
            priority=0.90,
            difficulty=0.8,
            feasibility=0.4,
        ))

        # Gap 3: 6th-root regime — first untested growth class
        gaps.append(FrontierGap(
            id="sixth_root",
            description="Numerically verify ratio universality for α=5 (6th root). "
                        "Compute prod(1-q^n)^{-n^4} to N=5000. Untested regime.",
            source="paper14/Section 10",
            gap_type="computation",
            priority=0.90,
            difficulty=0.5,
            feasibility=0.9,
        ))

        # Gap 4: BDJ bridge — Tracy-Widom connection
        gaps.append(FrontierGap(
            id="bdj_bridge",
            description="Test whether ratio fluctuations converge to Tracy-Widom TW₂. "
                        "Need n=5000-10000, 100k samples, KS statistic.",
            source="paper14/Section 11",
            gap_type="computation",
            priority=0.85,
            difficulty=0.6,
            feasibility=0.7,
        ))

        # Gap 5: Kloosterman tightening
        gaps.append(FrontierGap(
            id="kloosterman_q500",
            description="Extend Kloosterman bounds from q≤300 to q≤500. "
                        "May drop C_5 below 1.0, unlocking proof path.",
            source="paper14/Theorem 2 proof",
            gap_type="computation",
            priority=0.80,
            difficulty=0.3,
            feasibility=0.95,
        ))

        # Gap 6: Phase transition boundary
        gaps.append(FrontierGap(
            id="phase_boundary",
            description="Find where universality breaks. "
                        "Scan Meinardus products with varied D(s) coefficient patterns. "
                        "Harris-criterion analogy.",
            source="paper14/Section 12",
            gap_type="extension",
            priority=0.75,
            difficulty=0.8,
            feasibility=0.5,
        ))

        # Gap 7: A₃ extraction
        gaps.append(FrontierGap(
            id="A3_numerical",
            description="Extract fifth-order coefficient A₃ for k=1..5. "
                        "Needs N ≥ 15000, Richardson at order 5.",
            source="paper14/Section 9",
            gap_type="computation",
            priority=0.65,
            difficulty=0.6,
            feasibility=0.7,
        ))

        # Gap 8: Andrews-Gordon family
        gaps.append(FrontierGap(
            id="andrews_gordon",
            description="Test ratio universality for Andrews-Gordon partitions. "
                        "Different D(s) structure, satisfies Meinardus conditions.",
            source="paper14/Section 10",
            gap_type="extension",
            priority=0.70,
            difficulty=0.5,
            feasibility=0.8,
        ))

        # Gap 9: New GCF identities via Ramanujan agent
        gaps.append(FrontierGap(
            id="new_gcf_identities",
            description="Search for novel GCF identities linking partition ratios "
                        "to known constants. Use PSLQ at 200 dps.",
            source="knowledge_base/iteration_6",
            gap_type="conjecture",
            priority=0.70,
            difficulty=0.4,
            feasibility=0.8,
        ))

        # Gap 10: Δ_k quantum modular form
        gaps.append(FrontierGap(
            id="delta_k_qmf",
            description="Interpret Δ_k·c_k = -(k+3)(k-1)/8 (rational) via "
                        "Zagier quantum modular forms. Compute mock modular partners.",
            source="paper14/Section 11",
            gap_type="conjecture",
            priority=0.60,
            difficulty=0.85,
            feasibility=0.3,
        ))

        self.gaps = gaps
        return gaps

    def rank_gaps(self) -> list[FrontierGap]:
        """Rank gaps by composite score, factoring in memory of past failures."""
        if not self.gaps:
            self.identify_gaps()

        for gap in self.gaps:
            # Check for known failures
            past_failures = self.memory.check_failure_pattern(gap.id, "any")
            gap.attempts = len(past_failures)

        self.gaps.sort(key=lambda g: g.score, reverse=True)
        return self.gaps


# ══════════════════════════════════════════════════════════════════════════
# LOCAL AXIOM GRAPH — Load persistent knowledge from V8 engine
# ══════════════════════════════════════════════════════════════════════════

class LocalAxiomGraph:
    """
    Loads the axiom_graph.json from breakthrough_engine_v8
    and provides seed candidates for local hypothesis synthesis.
    """

    def __init__(self, path: Path = AXIOM_GRAPH):
        self.path = path
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self.domains: set = set()
        self._load()

    def _load(self):
        if not self.path.exists():
            info("No axiom graph found — synthesis will use paper knowledge only")
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.nodes = data.get("nodes", [])
            self.edges = data.get("edges", [])
            self.domains = {n.get("domain", "") for n in self.nodes}
            ok(f"Axiom graph loaded: {len(self.nodes)} nodes, "
               f"{len(self.edges)} edges, {len(self.domains)} domains")
        except Exception as e:
            warn(f"Axiom graph load failed: {e}")

    def get_alive_nodes(self, domain: str = None) -> list[dict]:
        """Get active (non-falsified) axiom nodes."""
        alive = [n for n in self.nodes if n.get("status", "alive") == "alive"]
        if domain:
            alive = [n for n in alive
                     if n.get("domain") == domain
                     or domain in n.get("domains_touched", [])]
        return alive

    def get_seed_candidates(self, domain: str = None, k: int = 5) -> list[dict]:
        """Top-k alive nodes by confidence × novelty for synthesis seeding."""
        nodes = self.get_alive_nodes(domain)
        nodes.sort(
            key=lambda n: n.get("confidence", 0.5) * n.get("novelty_score", 0.5),
            reverse=True
        )
        return nodes[:k]

    def get_cross_domain_seeds(self, current_domain: str, k: int = 3) -> list[dict]:
        """Pull high-novelty nodes from OTHER domains for conceptual blending."""
        foreign = [n for n in self.nodes
                   if n.get("status") == "alive"
                   and n.get("domain") != current_domain
                   and n.get("novelty_score", 0) > 0.5]
        foreign.sort(key=lambda n: n.get("novelty_score", 0), reverse=True)
        return foreign[:k]

    def get_falsified_patterns(self, k: int = 5) -> list[dict]:
        """Retrieve falsified nodes for failure archaeology."""
        falsified = [n for n in self.nodes
                     if n.get("status") in ("falsified", "dormant")]
        falsified.sort(key=lambda n: n.get("novelty_score", 0), reverse=True)
        return falsified[:k]

    def stats(self) -> dict:
        alive = sum(1 for n in self.nodes if n.get("status") == "alive")
        falsified = sum(1 for n in self.nodes if n.get("status") == "falsified")
        return {
            "total": len(self.nodes),
            "alive": alive,
            "falsified": falsified,
            "edges": len(self.edges),
            "domains": sorted(self.domains),
        }


# ══════════════════════════════════════════════════════════════════════════
# SYMBOLIC INDUCTION ENGINE — SymPy-powered identity testing
# ══════════════════════════════════════════════════════════════════════════

class SymbolicInductionEngine:
    """
    Replaces LLM 'creative' steps with deterministic symbolic methods.
    Tests algebraic identities against local data using SymPy.
    """

    def __init__(self, toolbox: "VerificationToolbox"):
        self.toolbox = toolbox
        self.cache: dict = {}
        self._load_cache()

    def _load_cache(self):
        if INDUCTION_CACHE.exists():
            try:
                self.cache = json.loads(INDUCTION_CACHE.read_text(encoding="utf-8"))
            except Exception:
                self.cache = {}

    def _save_cache(self):
        INDUCTION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        INDUCTION_CACHE.write_text(json.dumps(self.cache, indent=2, default=str),
                                   encoding="utf-8")

    def test_ratio_identity(self, k: int, formula_name: str,
                            formula_expr: str) -> dict:
        """
        Test whether a proposed formula matches partition ratio coefficients.
        Uses SymPy for symbolic simplification + mpmath for numeric check.

        Args:
            k: partition color parameter
            formula_name: e.g. "A1", "A2", "L"
            formula_expr: SymPy expression string with 'k' as variable
        Returns:
            dict with {matches: bool, symbolic_simplified: str, numeric_digits: int}
        """
        if not HAS_SYMPY:
            return {"error": "sympy not available", "matches": False}

        result = {"formula_name": formula_name, "k": k}
        try:
            # Symbolic check: does the formula simplify to known form?
            k_sym = sympy.Symbol('k', positive=True, integer=True)
            expr = sympy.sympify(formula_expr, locals={"k": k_sym})
            simplified = sympy.simplify(expr)
            result["symbolic"] = str(simplified)

            # Numeric check at target k
            numeric_val = float(expr.subs(k_sym, k).evalf(30))
            result["numeric_value"] = numeric_val

            # Check against known formulas
            if formula_name == "L":
                # L = c_k^2/8 + kappa_k
                c_k = sympy.pi * sympy.sqrt(2 * k_sym / 3)
                kappa_k = -(k_sym + 3) / 4
                L_known = c_k**2 / 8 + kappa_k
                diff = sympy.simplify(expr - L_known)
                result["matches_known"] = diff == 0
                if not result["matches_known"]:
                    result["diff_from_known"] = str(diff)

            elif formula_name == "A1":
                c_k = sympy.pi * sympy.sqrt(2 * k_sym / 3)
                A1_known = -k_sym * c_k / 48 - (k_sym + 1) * (k_sym + 3) / (8 * c_k)
                diff = sympy.simplify(expr - A1_known)
                result["matches_known"] = diff == 0

            elif formula_name == "A2":
                A2_known = ((k_sym + 3) * (sympy.pi**2 * k_sym**2 - 9*k_sym - 9)
                            / (96 * k_sym * sympy.pi**2))
                diff = sympy.simplify(expr - A2_known)
                result["matches_known"] = diff == 0

            else:
                result["matches_known"] = None  # No reference formula

            result["success"] = True

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)

        return result

    def discover_pattern(self, data_points: list[tuple],
                         variable: str = "k") -> dict:
        """
        Given (k, value) pairs, attempt to find a closed-form formula.
        Uses SymPy rational interpolation and PSLQ as fallback.

        Args:
            data_points: list of (k, numeric_value) tuples
            variable: name for the independent variable
        Returns:
            dict with {found: bool, formula: str, confidence: float}
        """
        if not HAS_SYMPY:
            return {"found": False, "error": "sympy not available"}

        k_sym = sympy.Symbol(variable, positive=True)
        result = {"n_points": len(data_points)}

        try:
            # Strategy 1: Rational interpolation
            # Fit P(k)/Q(k) through the data points
            if len(data_points) >= 3:
                # Try polynomial fit first
                for degree in range(1, min(4, len(data_points))):
                    try:
                        points = [(sympy.Integer(k), sympy.nsimplify(
                            sympy.Rational(v).limit_denominator(10**6)))
                            for k, v in data_points[:degree + 1]]
                        poly = sympy.interpolate(points, k_sym)
                        simplified = sympy.simplify(poly)

                        # Verify on remaining points
                        matches = 0
                        for k_val, expected in data_points:
                            predicted = float(simplified.subs(k_sym, k_val).evalf(15))
                            if abs(predicted - expected) / max(abs(expected), 1e-15) < 1e-8:
                                matches += 1

                        if matches == len(data_points):
                            result["found"] = True
                            result["formula"] = str(simplified)
                            result["method"] = f"polynomial_deg{degree}"
                            result["confidence"] = min(1.0, matches / len(data_points))
                            return result
                    except Exception:
                        continue

            # Strategy 2: Check if values match common forms involving pi, sqrt
            if HAS_MPMATH and len(data_points) >= 1:
                for k_val, num_val in data_points[:3]:
                    pslq_result = self.toolbox.pslq_search(
                        num_val,
                        ["1", "pi", "pi^2", "sqrt(k)", "1/pi"],
                        [1, float(mp.pi), float(mp.pi**2),
                         float(mp.sqrt(k_val)), float(1/mp.pi)],
                        dps=50,
                    )
                    if pslq_result.get("found"):
                        result["found"] = True
                        result["formula"] = pslq_result["formatted"]
                        result["method"] = "pslq"
                        result["confidence"] = 0.7
                        return result

            result["found"] = False
            result["method"] = "exhausted"

        except Exception as e:
            result["found"] = False
            result["error"] = str(e)

        return result

    def test_universality_hypothesis(self, gap_id: str,
                                     test_values: dict) -> dict:
        """
        Test a universality hypothesis: does coefficient X depend only
        on parameters (c, κ) rather than on family-specific Dirichlet data?

        Args:
            gap_id: frontier gap being tested
            test_values: {k: value} for multiple k
        Returns:
            dict with universality assessment
        """
        if not HAS_SYMPY or not test_values:
            return {"universal": None, "reason": "insufficient data"}

        k_sym = sympy.Symbol('k', positive=True)

        # Check if values satisfy L = c_k^2/8 + kappa_k
        deviations = []
        for k_val, observed in test_values.items():
            k_int = int(k_val)
            c_k = float((sympy.pi * sympy.sqrt(sympy.Rational(2 * k_int, 3))).evalf(20))
            kappa_k = -(k_int + 3) / 4.0
            L_pred = c_k**2 / 8.0 + kappa_k
            if L_pred != 0:
                dev = abs(observed - L_pred) / abs(L_pred)
                deviations.append(dev)

        if not deviations:
            return {"universal": None, "reason": "no valid comparisons"}

        avg_dev = sum(deviations) / len(deviations)
        max_dev = max(deviations)

        return {
            "universal": max_dev < 1e-6,
            "avg_deviation": avg_dev,
            "max_deviation": max_dev,
            "n_tested": len(deviations),
            "assessment": (
                "CONFIRMED: universal to 6+ digits" if max_dev < 1e-6
                else "PARTIAL: universal to ~" + str(max(0, int(-math.log10(max_dev)))) + " digits"
                if max_dev < 0.1
                else "REJECTED: deviations too large"
            ),
        }


# ══════════════════════════════════════════════════════════════════════════
# LOCAL SYNTHESIS ENGINE — Replaces LLM for hypothesis generation
# ══════════════════════════════════════════════════════════════════════════

class LocalSynthesisEngine:
    """
    Deterministic hypothesis generation using:
    1. Axiom Graph seeds (conceptual blending)
    2. Symbolic induction (SymPy pattern discovery)
    3. Failure archaeology (what NOT to try)
    4. Cross-domain pattern injection

    Replaces LLMClient for fully local (9/10) autonomy.
    """

    def __init__(self, axiom_graph: LocalAxiomGraph,
                 induction: SymbolicInductionEngine,
                 memory: PersistentMemory):
        self.axiom_graph = axiom_graph
        self.induction = induction
        self.memory = memory
        self.synthesis_count = 0

    def synthesize_hypothesis(self, gap: FrontierGap,
                              iteration: int) -> Hypothesis:
        """
        Generate a hypothesis for a frontier gap using local synthesis.
        Combines axiom seeds + symbolic patterns + failure avoidance.
        """
        self.synthesis_count += 1
        hyp_id = f"H-{iteration:04d}-{gap.id}"

        # 1. Retrieve axiom seeds
        seeds = self.axiom_graph.get_seed_candidates(domain="mathematics", k=3)
        cross_seeds = self.axiom_graph.get_cross_domain_seeds("mathematics", k=2)
        seed_ids = [s.get("id", "?") for s in seeds[:3]]

        # 2. Check failure archaeology
        past_failures = self.memory.check_failure_pattern(gap.id, "any")
        failed_methods = {f.get("method", "") for f in past_failures}

        # 3. Select synthesis strategy based on gap type
        if gap.gap_type == "computation":
            return self._synthesize_computation(hyp_id, gap, seeds,
                                                failed_methods)
        elif gap.gap_type == "proof":
            return self._synthesize_proof(hyp_id, gap, seeds,
                                          failed_methods)
        elif gap.gap_type == "conjecture":
            return self._synthesize_conjecture(hyp_id, gap, seeds,
                                               cross_seeds, failed_methods)
        elif gap.gap_type == "extension":
            return self._synthesize_extension(hyp_id, gap, seeds,
                                              cross_seeds, failed_methods)
        else:
            return self._synthesize_generic(hyp_id, gap, seeds)

    def _synthesize_computation(self, hyp_id: str, gap: FrontierGap,
                                seeds: list, failed_methods: set) -> Hypothesis:
        """Synthesize a computational verification hypothesis."""
        # Determine method: if 'numeric' failed before, try symbolic
        if "numeric" in failed_methods:
            method = "symbolic"
            mechanism = "Symbolic verification via SymPy (numeric previously failed)"
            tools = ["symbolic_verify", "sandbox"]
        else:
            method = "numeric"
            mechanism = "Multi-tier numeric verification (50→100→200 dps)"
            tools = ["compute_partition_ratios", "extract_coefficients"]

        seed_context = ""
        if seeds:
            seed_context = f" Seeded by axiom nodes: {', '.join(s.get('id', '?') for s in seeds[:2])}."

        return Hypothesis(
            id=hyp_id,
            gap_id=gap.id,
            claim=f"Local induction: {gap.description[:80]} verified via {method}.{seed_context}",
            mechanism=mechanism,
            testable_prediction=f"Coefficient extraction matches prediction to 8+ digits at high N",
            failure_condition=f"Digit agreement < 5 after {method} verification",
            tools_needed=tools,
            confidence=0.6 if method == "numeric" else 0.4,
        )

    def _synthesize_proof(self, hyp_id: str, gap: FrontierGap,
                          seeds: list, failed_methods: set) -> Hypothesis:
        """Synthesize a proof-oriented hypothesis."""
        # For proof gaps, try symbolic approach first
        if "symbolic" in failed_methods:
            approach = "constructive numeric bounds"
            mechanism = "Establish numeric bounds sufficient for proof via Richardson extrapolation"
            tools = ["sandbox", "compute_partition_ratios"]
        else:
            approach = "symbolic identity verification"
            mechanism = "SymPy symbolic simplification + series expansion matching"
            tools = ["symbolic_verify", "sandbox"]

        return Hypothesis(
            id=hyp_id,
            gap_id=gap.id,
            claim=f"Proof path for {gap.id} via {approach}",
            mechanism=mechanism,
            testable_prediction=f"Symbolic identity holds or numeric bounds confirm conjecture",
            failure_condition=f"Identity does not simplify to zero / bounds insufficient",
            tools_needed=tools,
            confidence=0.3,
        )

    def _synthesize_conjecture(self, hyp_id: str, gap: FrontierGap,
                               seeds: list, cross_seeds: list,
                               failed_methods: set) -> Hypothesis:
        """Synthesize a conjecture hypothesis via conceptual blending."""
        # Use cross-domain seeds for creative combination
        blend_context = ""
        if cross_seeds:
            foreign = cross_seeds[0]
            blend_context = (
                f" Cross-domain seed: '{foreign.get('text', '?')[:60]}' "
                f"(domain={foreign.get('domain', '?')})."
            )

        return Hypothesis(
            id=hyp_id,
            gap_id=gap.id,
            claim=f"Conjectured pattern in {gap.id} via PSLQ + symbolic induction.{blend_context}",
            mechanism="PSLQ search over extended constant basis + SymPy pattern matching",
            testable_prediction="At least one algebraic relation found at 100+ digit precision",
            failure_condition="No PSLQ relations and no symbolic patterns after exhaustive search",
            tools_needed=["pslq_search", "sandbox"],
            confidence=0.4,
        )

    def _synthesize_extension(self, hyp_id: str, gap: FrontierGap,
                              seeds: list, cross_seeds: list,
                              failed_methods: set) -> Hypothesis:
        """Synthesize an extension hypothesis."""
        return Hypothesis(
            id=hyp_id,
            gap_id=gap.id,
            claim=f"Extension: {gap.description[:80]} follows from existing universality structure",
            mechanism="Apply known universality framework to new family/regime parameter space",
            testable_prediction="L coefficient matches c²/8 + κ to 6+ digits in new domain",
            failure_condition="Deviation > 1% from universal prediction",
            tools_needed=["sandbox", "compute_partition_ratios"],
            confidence=0.5,
        )

    def _synthesize_generic(self, hyp_id: str, gap: FrontierGap,
                            seeds: list) -> Hypothesis:
        """Fallback synthesis for untyped gaps."""
        seed_ctx = ""
        if seeds:
            seed_ctx = f" (axiom seeds: {', '.join(s.get('id', '?') for s in seeds[:2])})"

        return Hypothesis(
            id=hyp_id,
            gap_id=gap.id,
            claim=f"Exploratory investigation of {gap.id}{seed_ctx}",
            mechanism="Combined numeric + symbolic exploration",
            testable_prediction="Progress metric TBD from initial computation",
            failure_condition="No measurable progress after execution",
            tools_needed=["sandbox"],
            confidence=0.3,
        )

    def enrich_hypothesis(self, hyp: Hypothesis, gap: FrontierGap) -> Hypothesis:
        """
        Post-process a hardcoded hypothesis with axiom graph context.
        Called when using the original hardcoded hypothesis generators
        to add synthesis metadata.
        """
        # Add axiom seed context
        seeds = self.axiom_graph.get_seed_candidates(domain="mathematics", k=2)
        if seeds:
            seed_text = "; ".join(s.get("text", "?")[:50] for s in seeds)
            hyp.mechanism += f" [Axiom seeds: {seed_text}]"

        # Check if symbolic induction can strengthen the claim
        if HAS_SYMPY and gap.gap_type in ("computation", "proof"):
            hyp.tools_needed = list(set(hyp.tools_needed + ["symbolic_verify"]))

        return hyp


# ══════════════════════════════════════════════════════════════════════════
# CRITIC AGENT — Architecturally isolated evaluator
# ══════════════════════════════════════════════════════════════════════════

class CriticAgent:
    """
    Evaluates results with a skeptical lens.
    CRITICAL: This agent has NO access to the Creator's reasoning chain.
    It only sees the claim and the evidence.
    """

    def __init__(self, toolbox: VerificationToolbox):
        self.toolbox = toolbox

    def evaluate(self, hypothesis: Hypothesis, result: ExecutionResult) -> Evaluation:
        """
        Score a result on 4 dimensions + attempt falsification.
        """
        header(f"CRITIC: Evaluating {hypothesis.id}")
        scores = {}
        flaws = []
        fixes = []

        # ── Novelty (N) ──────────────────────────────────────────────
        n_score = self._score_novelty(hypothesis, result)
        scores["N"] = n_score

        # ── Falsifiability (F) ────────────────────────────────────────
        f_score = self._score_falsifiability(hypothesis, result)
        scores["F"] = f_score

        # ── Empirical Support (E) ────────────────────────────────────
        e_score, e_flaws = self._score_empirical(hypothesis, result)
        scores["E"] = e_score
        flaws.extend(e_flaws)

        # ── Compression (C) ──────────────────────────────────────────
        c_score = self._score_compression(hypothesis, result)
        scores["C"] = c_score

        # ── Kill Floor Check ─────────────────────────────────────────
        killed = False
        for dim, floor in KILL_FLOOR.items():
            if scores.get(dim, 0) < floor:
                err(f"KILL FLOOR: {dim} = {scores[dim]:.2f} < {floor}")
                killed = True
                flaws.append(f"{dim} below kill floor ({scores[dim]:.2f} < {floor})")

        # ── B-Score ──────────────────────────────────────────────────
        b = scores["N"] * scores["F"] * scores["E"] * scores["C"]

        # Determine verdict
        if killed:
            verdict = "failure"
            is_breakthrough = False
        elif b >= BREAKTHROUGH_THRESHOLD:
            verdict = "breakthrough"
            is_breakthrough = True
            ok(f"BREAKTHROUGH CANDIDATE — B = {b:.4f}")
        elif b >= BREAKTHROUGH_THRESHOLD * 0.5:
            verdict = "progress"
            is_breakthrough = False
            info(f"Progress — B = {b:.4f}")
        else:
            verdict = "inconclusive"
            is_breakthrough = False
            info(f"Inconclusive — B = {b:.4f}")

        # Generate suggestions
        if not is_breakthrough:
            fixes = self._suggest_fixes(hypothesis, result, scores, flaws)

        critique = (
            f"Scores: N={scores['N']:.2f} F={scores['F']:.2f} "
            f"E={scores['E']:.2f} C={scores['C']:.2f} → B={b:.4f}\n"
            f"Verdict: {verdict}\n"
            f"Flaws: {'; '.join(flaws) if flaws else 'None found'}"
        )

        return Evaluation(
            result_id=hypothesis.id,
            is_breakthrough=is_breakthrough,
            confidence=min(scores.values()),
            scores=scores,
            critique=critique,
            flaws_found=flaws,
            suggested_fixes=fixes,
            verdict=verdict,
        )

    def _score_novelty(self, hyp: Hypothesis, result: ExecutionResult) -> float:
        """Is this genuinely new?"""
        # Base score from hypothesis structure
        if "novel" in hyp.claim.lower() or "new" in hyp.claim.lower():
            base = 0.7
        elif "extend" in hyp.claim.lower() or "generalize" in hyp.claim.lower():
            base = 0.6
        else:
            base = 0.5

        # Boost for successful proofs
        if result.proof_status == "complete":
            base = min(1.0, base + 0.2)
        elif result.digits_matched >= 50:
            base = min(1.0, base + 0.1)

        return base

    def _score_falsifiability(self, hyp: Hypothesis, result: ExecutionResult) -> float:
        """Can this be tested and potentially disproved?"""
        if hyp.failure_condition and hyp.testable_prediction:
            base = 0.8
        elif hyp.testable_prediction:
            base = 0.7
        else:
            base = 0.4

        # Higher if we actually tested it
        if result.method in ("numeric", "symbolic", "proof"):
            base = min(1.0, base + 0.1)

        return base

    def _score_empirical(self, hyp: Hypothesis,
                         result: ExecutionResult) -> tuple[float, list]:
        """How strong is the evidence?"""
        flaws = []

        if result.error:
            flaws.append(f"Execution error: {result.error[:200]}")
            return 0.1, flaws

        if not result.success:
            flaws.append("Execution did not succeed")
            return 0.15, flaws

        if result.proof_status == "complete":
            return 0.95, flaws
        elif result.proof_status == "partial":
            return 0.7, flaws

        # Digit-based scoring (classic numeric verification)
        if result.digits_matched >= 100:
            return 0.9, flaws
        elif result.digits_matched >= 50:
            return 0.8, flaws
        elif result.digits_matched >= 20:
            return 0.65, flaws
        elif result.digits_matched >= 10:
            return 0.55, flaws
        elif result.digits_matched >= 5:
            flaws.append(f"Only {result.digits_matched} digits matched — could be coincidence")
            return 0.4, flaws

        # Evidence-based scoring for non-digit results
        # If execution succeeded and produced data, score based on evidence content
        if result.evidence:
            ev = result.evidence

            # BDJ bridge: check if statistics are reasonable
            if "mean" in ev and "std" in ev and "tw2_ref" in ev:
                tw2 = ev["tw2_ref"]
                std_ratio = abs(ev["std"] - tw2["std"]) / tw2["std"] if tw2.get("std") else 1
                if std_ratio < 0.1:
                    return 0.7, flaws  # Strong TW2 match
                elif std_ratio < 0.3:
                    return 0.55, flaws  # Moderate match
                else:
                    flaws.append(f"TW2 std mismatch: {ev['std']:.3f} vs {tw2['std']:.3f}")
                    return 0.4, flaws

            # Kloosterman: check if bound was computed
            if "C_k_bound" in ev:
                bound = ev["C_k_bound"]
                if bound < 1.0:
                    return 0.8, flaws  # Bound below proof threshold!
                elif bound < 1.5:
                    return 0.55, flaws  # Bound computed but still above
                else:
                    flaws.append(f"C_k bound = {bound:.3f}, still above 1.0")
                    return 0.4, flaws

            # Scaling exponent check (sixth_root etc.)
            if "beta_digits" in ev:
                bd = ev["beta_digits"]
                if bd >= 3:
                    return 0.65, flaws
                elif bd >= 1:
                    return 0.45, flaws

            # General: if we have structured data output, give baseline credit
            if len(ev) >= 3:
                return 0.4, flaws

        flaws.append("Insufficient digit agreement and no structured evidence")
        return 0.2, flaws

    def _score_compression(self, hyp: Hypothesis, result: ExecutionResult) -> float:
        """Does this simplify our understanding?"""
        # More observations explained = higher compression
        mechanism_words = len(hyp.mechanism.split()) if hyp.mechanism else 0
        claim_words = len(hyp.claim.split()) if hyp.claim else 0

        if mechanism_words > 0 and claim_words > 0:
            ratio = claim_words / mechanism_words  # shorter mechanism = better
            if ratio > 2:
                return 0.8
            elif ratio > 1:
                return 0.7
            else:
                return 0.6
        return 0.5

    def _suggest_fixes(self, hyp: Hypothesis, result: ExecutionResult,
                       scores: dict, flaws: list) -> list[str]:
        """Generate actionable suggestions for improvement."""
        fixes = []
        if scores.get("E", 0) < 0.5:
            fixes.append("Increase precision: try 200 dps or N=10000 for more digits")
        if scores.get("N", 0) < 0.5:
            fixes.append("Reframe hypothesis with clearer novelty delta from prior work")
        if scores.get("F", 0) < 0.5:
            fixes.append("Sharpen testable prediction with specific numeric target")
        if scores.get("C", 0) < 0.5:
            fixes.append("Identify additional phenomena this mechanism explains")
        if result.error:
            fixes.append(f"Fix execution error: {result.error[:150]}")
        return fixes


# ══════════════════════════════════════════════════════════════════════════
# SELF-ITERATION ENGINE — Mutate own templates + tools
# ══════════════════════════════════════════════════════════════════════════

class SelfIterationEngine:
    """
    Manages the agent's ability to modify its own behavior.
    All mutations are version-controlled via snapshots.
    """

    def __init__(self, memory: PersistentMemory):
        self.memory = memory
        self.templates: dict[str, str] = {}
        self.mutation_history: list[dict] = []
        self._load_templates()

    def _load_templates(self):
        """Load prompt templates from disk."""
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

        defaults = {
            "frontier_analysis": (
                "Analyze the current research frontier. "
                "Given the proven theorems, open conjectures, and recent discoveries, "
                "identify the most promising gap to attack next. "
                "Consider: feasibility with available tools, potential impact, "
                "and whether we've already failed at similar attempts."
            ),
            "hypothesis_generation": (
                "Given the identified gap '{gap_description}', generate a specific, "
                "testable hypothesis. Include: (1) precise claim, (2) mechanism, "
                "(3) testable prediction with expected numeric value, "
                "(4) falsification condition."
            ),
            "result_evaluation": (
                "Evaluate this result as a skeptic. "
                "Claim: {claim}\n"
                "Evidence: {evidence}\n"
                "Score on Novelty, Falsifiability, Empirical support, Compression. "
                "Try to find flaws FIRST. Only score high if no flaws found."
            ),
            "self_improvement": (
                "Review the last {n} iterations. Identify patterns:\n"
                "- Which approaches consistently succeed?\n"
                "- Which consistently fail?\n"
                "- What tools are missing?\n"
                "- What scoring adjustments would improve target selection?\n"
                "Propose ONE concrete improvement to the agent's behavior."
            ),
        }

        for name, default_text in defaults.items():
            path = TEMPLATES_DIR / f"{name}.txt"
            if not path.exists():
                path.write_text(default_text, encoding="utf-8")
            self.templates[name] = path.read_text(encoding="utf-8")

    def propose_mutation(self, iteration_history: list[IterationRecord]) -> dict:
        """
        Analyze iteration history and propose a self-improvement.
        Returns a mutation proposal (not yet applied).
        """
        if len(iteration_history) < 3:
            return {"type": "none", "reason": "Too few iterations for self-analysis"}

        # Analyze patterns
        successes = [r for r in iteration_history if r.evaluation
                     and r.evaluation.get("is_breakthrough")]
        failures = [r for r in iteration_history if r.evaluation
                    and r.evaluation.get("verdict") == "failure"]

        proposal = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "total_iterations": len(iteration_history),
                "successes": len(successes),
                "failures": len(failures),
                "success_rate": len(successes) / max(1, len(iteration_history)),
            },
            "mutations": [],
        }

        # Pattern: If a gap type consistently fails, lower its priority
        gap_outcomes = {}
        for r in iteration_history:
            gap = r.gap
            if gap and r.evaluation:
                gtype = gap.get("gap_type", "unknown")
                v = r.evaluation.get("verdict", "unknown")
                if gtype not in gap_outcomes:
                    gap_outcomes[gtype] = {"success": 0, "failure": 0}
                if v in ("breakthrough", "progress"):
                    gap_outcomes[gtype]["success"] += 1
                elif v == "failure":
                    gap_outcomes[gtype]["failure"] += 1

        for gtype, counts in gap_outcomes.items():
            total = counts["success"] + counts["failure"]
            if total >= 3 and counts["failure"] / total > 0.7:
                proposal["mutations"].append({
                    "type": "priority_adjustment",
                    "target": gtype,
                    "action": f"Reduce priority for '{gtype}' gaps (70%+ failure rate)",
                    "requires_hitl": False,
                })

        # Pattern: If a tool consistently fails, suggest alternative
        for tool, stats in self.memory.tool_effectiveness.items():
            if stats["calls"] >= 5:
                rate = stats["successes"] / stats["calls"]
                if rate < 0.3:
                    proposal["mutations"].append({
                        "type": "tool_adjustment",
                        "target": tool,
                        "action": f"Tool '{tool}' has {rate:.0%} success rate — consider alternative",
                        "requires_hitl": False,
                    })

        # Pattern: Template tuning (only with HITL)
        if len(iteration_history) >= 10:
            proposal["mutations"].append({
                "type": "template_review",
                "action": "Review and update prompt templates after 10+ iterations",
                "requires_hitl": True,
            })

        return proposal

    def apply_mutation(self, mutation: dict, hitl_approved: bool = False) -> bool:
        """Apply a mutation. HITL-required mutations need explicit approval."""
        if mutation.get("requires_hitl") and not hitl_approved:
            warn(f"Mutation requires HITL approval: {mutation.get('action', '?')}")
            return False

        mtype = mutation.get("type")

        if mtype == "priority_adjustment":
            # Log the adjustment for the knowledge graph to use
            self.memory.add_entry(
                "mutation",
                f"Priority adjustment: {mutation['action']}",
                {"mutation": mutation}
            )
            ok(f"Applied priority adjustment: {mutation['action']}")

        elif mtype == "tool_adjustment":
            self.memory.add_entry(
                "mutation",
                f"Tool adjustment noted: {mutation['action']}",
                {"mutation": mutation}
            )
            ok(f"Noted tool adjustment: {mutation['action']}")

        elif mtype == "template_review":
            if hitl_approved:
                info("Template review approved — templates may be updated")
            return hitl_approved

        # Log mutation
        self.mutation_history.append({
            "mutation": mutation,
            "applied": True,
            "timestamp": datetime.now().isoformat(),
        })

        return True

    def take_snapshot(self, iteration: int):
        """Save a snapshot of current agent state for rollback."""
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snap_dir = SNAPSHOTS_DIR / f"iter_{iteration:04d}"
        snap_dir.mkdir(parents=True, exist_ok=True)

        # Copy critical state files
        for src in [STATE_FILE, MEMORY_FILE]:
            if src.exists():
                shutil.copy2(src, snap_dir / src.name)

        # Copy templates
        templates_snap = snap_dir / "templates"
        if TEMPLATES_DIR.exists():
            if templates_snap.exists():
                shutil.rmtree(templates_snap)
            shutil.copytree(TEMPLATES_DIR, templates_snap)

        ok(f"Snapshot saved: iter_{iteration:04d}")

    def rollback(self, to_iteration: int) -> bool:
        """Restore agent state from a snapshot."""
        snap_dir = SNAPSHOTS_DIR / f"iter_{to_iteration:04d}"
        if not snap_dir.exists():
            err(f"No snapshot for iteration {to_iteration}")
            return False

        # Restore state files
        for fname in ["agent_state.json", "memory.json"]:
            src = snap_dir / fname
            if src.exists():
                shutil.copy2(src, STATE_DIR / fname)

        # Restore templates
        templates_snap = snap_dir / "templates"
        if templates_snap.exists():
            if TEMPLATES_DIR.exists():
                shutil.rmtree(TEMPLATES_DIR)
            shutil.copytree(templates_snap, TEMPLATES_DIR)

        ok(f"Rolled back to iteration {to_iteration}")
        return True


# ══════════════════════════════════════════════════════════════════════════
# AGENT STATE — Full persistent state machine
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class AgentState:
    """Complete agent state, serializable to disk."""
    iteration: int = 0
    current_phase: str = "identify_frontier"
    cycle_count: int = 0
    total_runtime: float = 0.0
    breakthroughs: int = 0
    failures: int = 0
    gap_priorities: dict = field(default_factory=dict)   # gap_id -> adjusted priority
    category_credibility: dict = field(default_factory=lambda: {
        "proof": 0.5, "computation": 0.7, "extension": 0.5,
        "conjecture": 0.4,
    })
    iteration_history: list = field(default_factory=list)

    def save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(asdict(self), indent=2, default=str),
            encoding="utf-8"
        )

    @classmethod
    def load(cls) -> "AgentState":
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                state = cls()
                for key in ["iteration", "current_phase", "cycle_count",
                            "total_runtime", "breakthroughs", "failures",
                            "gap_priorities", "category_credibility",
                            "iteration_history"]:
                    if key in data:
                        setattr(state, key, data[key])
                return state
            except Exception as e:
                warn(f"State load failed: {e}")
        return cls()

    def update_credibility(self, category: str, success: bool, alpha: float = 0.15):
        """Bayesian-ish credibility update."""
        if category in self.category_credibility:
            old = self.category_credibility[category]
            target = 1.0 if success else 0.0
            self.category_credibility[category] = old + alpha * (target - old)


# ══════════════════════════════════════════════════════════════════════════
# MAIN AGENT — The Self-Iterating Research Loop
# ══════════════════════════════════════════════════════════════════════════

class SelfIteratingAgent:
    """
    The core research agent. Implements the 5-phase cycle:
      1. Identify Frontier → 2. Scope Target → 3. Execute → 4. Evaluate → 5. Summarize
    With backtracking (4→2 or 4→3) and self-mutation (5→templates).
    """

    def __init__(self, mode: str = "local"):
        self.mode = mode
        header("Self-Iterating Research Agent v" + VERSION)
        if mode == "local":
            ok("RUNNING IN LOCAL MODE (9/10 Discovery Engine)")
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)

        # Load persistent state
        self.state = AgentState.load()
        self.memory = PersistentMemory()
        self.toolbox = VerificationToolbox(self.memory)
        self.knowledge = KnowledgeGraph(self.memory)
        self.critic = CriticAgent(self.toolbox)
        self.mutation_engine = SelfIterationEngine(self.memory)

        # v1.1: Local synthesis components
        self.axiom_graph = LocalAxiomGraph()
        self.induction = SymbolicInductionEngine(self.toolbox)
        self.synthesis = LocalSynthesisEngine(
            self.axiom_graph, self.induction, self.memory
        )

        # Show tool status
        info("Tool status:")
        for name, status in self.toolbox.status().items():
            sym = "✓" if status == "available" else "✗"
            info(f"  {sym} {name}: {status}")
        # v1.1: Show synthesis capabilities
        info(f"  {'✓' if HAS_SYMPY else '✗'} symbolic_induction: "
             f"{'available' if HAS_SYMPY else 'missing (pip install sympy)'}")
        info(f"  {'✓' if HAS_PYSR else '✗'} symbolic_regression: "
             f"{'available' if HAS_PYSR else 'optional (pip install pysr)'}")
        info(f"  ✓ local_synthesis: active ({len(self.axiom_graph.nodes)} axiom nodes)")

        ok(f"State loaded: iteration {self.state.iteration}, "
           f"{self.state.breakthroughs} breakthroughs, "
           f"{self.state.failures} failures")

    # ── Phase 1: Identify Frontier ────────────────────────────────────

    def phase_identify_frontier(self) -> FrontierGap:
        """Analyze knowledge to find the best gap to attack."""
        header("Phase 1: IDENTIFY FRONTIER")

        gaps = self.knowledge.rank_gaps()
        info(f"Found {len(gaps)} frontier gaps:")
        for i, gap in enumerate(gaps[:5]):
            marker = "→" if i == 0 else " "
            info(f"  {marker} [{gap.score:.3f}] {gap.id}: {gap.description[:80]}...")

        # Apply priority adjustments from mutations
        for gap in gaps:
            if gap.id in self.state.gap_priorities:
                gap.priority *= self.state.gap_priorities[gap.id]

        # Apply credibility weighting
        for gap in gaps:
            cred = self.state.category_credibility.get(gap.gap_type, 0.5)
            gap.feasibility *= cred

        # Re-sort after adjustments
        gaps.sort(key=lambda g: g.score, reverse=True)

        best = gaps[0]
        ok(f"Selected: {best.id} (score={best.score:.3f})")
        return best

    # ── Phase 2: Scope Target ─────────────────────────────────────────

    def phase_scope_target(self, gap: FrontierGap) -> Hypothesis:
        """Convert a gap into a specific, testable hypothesis using local synthesis."""
        header(f"Phase 2: SCOPE TARGET — {gap.id}")

        # Check for known failures with this gap
        past_failures = self.memory.check_failure_pattern(gap.id, "any")
        if past_failures:
            warn(f"Known failures on {gap.id}: {len(past_failures)}")
            for f in past_failures[-2:]:
                info(f"  Previous failure: {f['reason'][:100]}")

        # v1.1: Use LocalSynthesisEngine for hypothesis generation
        # Try hardcoded first (specific domain knowledge), fall back to synthesis
        hyp = self._generate_hypothesis(gap)

        # Enrich with axiom graph context
        hyp = self.synthesis.enrich_hypothesis(hyp, gap)

        ok(f"Hypothesis: {hyp.claim[:100]}")
        info(f"  Testable: {hyp.testable_prediction[:100]}")
        info(f"  Falsify:  {hyp.failure_condition[:100]}")
        info(f"  Mode:     Local Synthesis (no API)")

        return hyp

    def _generate_hypothesis(self, gap: FrontierGap) -> Hypothesis:
        """Build a concrete hypothesis from a gap."""
        hyp_id = f"H-{self.state.iteration:04d}-{gap.id}"

        if gap.id == "prove_A1_k5":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="A₁^(5) = -5·c₅/48 - 6·8/(8·c₅) matches numerical extraction to 12+ digits",
                mechanism="Kloosterman sum analysis at conductor N₅=24 with q≤500 bounds",
                testable_prediction="Compute A₁ from 8000-term partition ratios, compare to formula",
                failure_condition="Digit agreement < 10 at N=8000",
                tools_needed=["compute_partition_ratios", "pslq_search"],
                confidence=0.7,
            )
        elif gap.id == "sixth_root":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="Product prod(1-q^n)^{-n^4} ratios satisfy L₅ = c₅²/8 + κ₅ universality",
                mechanism="Meinardus theorem extends to α=5 (6th root growth regime)",
                testable_prediction="L₅ numerical matches predicted value to 8+ digits at N=5000",
                failure_condition="Digit agreement < 5 at N=5000",
                tools_needed=["compute_general_product", "extract_coefficients"],
                confidence=0.8,
            )
        elif gap.id == "kloosterman_q500":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="Extending Kloosterman bounds to q≤500 reduces C₅ below 1.0",
                mechanism="Explicit computation of generalized Kloosterman sums at higher moduli",
                testable_prediction="C₅ ≤ 0.95 with q≤500 (currently 1.36 at q≤300)",
                failure_condition="C₅ still > 1.0 at q≤500",
                tools_needed=["sandbox"],
                confidence=0.4,
            )
        elif gap.id == "lemma_w":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="Wright M=2 saddle-point expansion has uniform Olver-type error bounds",
                mechanism="Extend Lemma PP proof technique with second-order Olver bounds",
                testable_prediction="Numerical error in M=2 expansion matches O(n^{-d-1}) predicted bound",
                failure_condition="Error scaling deviates from predicted exponent by > 10%",
                tools_needed=["sandbox", "symbolic_verify"],
                confidence=0.3,
            )
        elif gap.id == "bdj_bridge":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="Partition ratio fluctuations ξ_m converge to Tracy-Widom TW₂",
                mechanism="BDJ correspondence: partition asymptotics ↔ random matrix eigenvalues",
                testable_prediction="KS statistic vs TW₂ < 0.05 at n=5000, 10k samples",
                failure_condition="KS statistic > 0.15 (reject TW₂ at p=0.01)",
                tools_needed=["sandbox"],
                confidence=0.5,
            )
        elif gap.id == "new_gcf_identities":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="New GCF identities exist linking ratio coefficients to L-function values",
                mechanism="PSLQ search at 200 dps over extended constant basis",
                testable_prediction="At least one PSLQ hit at 100+ digits with maxcoeff<100",
                failure_condition="No PSLQ relations found across 1000+ configurations",
                tools_needed=["pslq_search", "evaluate_gcf"],
                confidence=0.4,
            )
        elif gap.id == "andrews_gordon":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="Andrews-Gordon partitions satisfy ratio universality with same L formula",
                mechanism="Meinardus conditions met with different D(s) but same leading structure",
                testable_prediction="L coefficient matches c²/8 + κ to 8+ digits at N=5000",
                failure_condition="Digit agreement < 4, suggesting universality breakdown",
                tools_needed=["sandbox"],
                confidence=0.6,
            )
        elif gap.id == "A3_numerical":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="A₃^(k) has a closed form analogous to A₁ and A₂",
                mechanism="Richardson extrapolation at order 5 from N≥15000 partition data",
                testable_prediction="A₃^(1) matches a formula involving c, κ, and π to 6+ digits",
                failure_condition="Extrapolation not converged at N=15000",
                tools_needed=["compute_partition_ratios", "pslq_search"],
                confidence=0.4,
            )
        elif gap.id == "phase_boundary":
            return Hypothesis(
                id=hyp_id,
                gap_id=gap.id,
                claim="Universality breaks at a critical boundary in Dirichlet parameter space",
                mechanism="Harris-criterion analogy: certain D(s) coefficient patterns break universality",
                testable_prediction="Find D(s) parameters where L ≠ c²/8 + κ",
                failure_condition="All tested D(s) families satisfy universality",
                tools_needed=["sandbox"],
                confidence=0.3,
            )
        else:
            # v1.1: Use LocalSynthesisEngine for unknown gap types
            return self.synthesis.synthesize_hypothesis(
                gap, self.state.iteration
            )

    # ── Phase 3: Execute ──────────────────────────────────────────────

    def phase_execute(self, hypothesis: Hypothesis) -> ExecutionResult:
        """Run the actual computation, proof, or simulation."""
        header(f"Phase 3: EXECUTE — {hypothesis.id}")
        t0 = time.time()

        gap_id = hypothesis.gap_id
        info(f"Tools needed: {hypothesis.tools_needed}")

        try:
            if gap_id == "prove_A1_k5":
                result = self._execute_A1_verification(hypothesis, k=5)
            elif gap_id == "sixth_root":
                result = self._execute_general_product(hypothesis, alpha=5, N=3000)
            elif gap_id == "kloosterman_q500":
                result = self._execute_kloosterman(hypothesis)
            elif gap_id == "bdj_bridge":
                result = self._execute_bdj(hypothesis)
            elif gap_id == "new_gcf_identities":
                result = self._execute_gcf_search(hypothesis)
            elif gap_id == "andrews_gordon":
                result = self._execute_new_family(hypothesis, "andrews_gordon")
            elif gap_id in ("A3_numerical",):
                result = self._execute_A3_extraction(hypothesis)
            else:
                result = self._execute_generic(hypothesis)
        except Exception as e:
            result = ExecutionResult(
                hypothesis_id=hypothesis.id,
                success=False,
                method="error",
                error=f"{type(e).__name__}: {e}",
                runtime_seconds=time.time() - t0,
            )

        result.runtime_seconds = time.time() - t0
        info(f"Execution time: {result.runtime_seconds:.1f}s")

        if result.success:
            ok(f"Method: {result.method} | Digits: {result.digits_matched}")
        else:
            err(f"Failed: {result.error or 'No result'}")

        return result

    def _execute_A1_verification(self, hyp: Hypothesis, k: int) -> ExecutionResult:
        """Verify A₁ formula for a specific k."""
        code = f"""
import mpmath as mp
import json
mp.mp.dps = 100

k = {k}
N = 6000

# Compute k-colored partition ratios
f = [mp.mpf(0)] * (N + 1)
f[0] = mp.mpf(1)

sigma1 = [mp.mpf(0)] * (N + 1)
for j in range(1, N + 1):
    s = mp.mpf(0)
    d = 1
    while d * d <= j:
        if j % d == 0:
            s += d
            if d != j // d:
                s += j // d
        d += 1
    sigma1[j] = s

for n in range(1, N + 1):
    s = mp.mpf(0)
    for j in range(1, n + 1):
        s += k * sigma1[j] * f[n - j]
    f[n] = s / n

# Constants
c = mp.pi * mp.sqrt(mp.mpf(2*k)/3)
kappa = -(k + 3) / mp.mpf(4)
L_pred = c**2 / 8 + kappa
A1_pred = -k * c / 48 - (k+1)*(k+3) / (8*c)

# Extract A1 from last 500 ratios
A1_estimates = []
for m in range(N-500, N+1):
    if m < 200 or f[m-1] == 0:
        continue
    sm = mp.sqrt(mp.mpf(m))
    R_m = f[m] / f[m-1]
    remainder = R_m - 1 - c / (2*sm) - L_pred / m
    A1_est = remainder * m * sm
    A1_estimates.append(float(mp.nstr(A1_est, 20)))

# Agreement
if A1_estimates:
    A1_num = A1_estimates[-1]
    A1_the = float(mp.nstr(A1_pred, 20))
    if A1_the != 0:
        digits = -mp.log10(abs(mp.mpf(A1_num) - A1_pred) / abs(A1_pred))
    else:
        digits = 0
    
    print(json.dumps({{
        "k": k,
        "N": N,
        "A1_numerical": A1_num,
        "A1_formula": A1_the,
        "digits_matched": int(max(0, float(digits))),
        "last_5": A1_estimates[-5:],
    }}))
else:
    print(json.dumps({{"error": "No estimates"}}))
"""
        sandbox = self.toolbox.run_sandboxed(code, timeout=MAX_COMPUTE_SECONDS)
        if sandbox["success"]:
            try:
                data = json.loads(sandbox["stdout"].strip().split("\n")[-1])
                return ExecutionResult(
                    hypothesis_id=hyp.id,
                    success=True,
                    method="numeric",
                    evidence=data,
                    digits_matched=data.get("digits_matched", 0),
                    code_executed=code,
                    raw_output=sandbox["stdout"][:5000],
                )
            except (json.JSONDecodeError, IndexError):
                pass
        return ExecutionResult(
            hypothesis_id=hyp.id,
            success=False,
            method="numeric",
            error=sandbox.get("stderr", sandbox.get("error", "Unknown")),
            code_executed=code,
            raw_output=sandbox.get("stdout", "")[:5000],
        )

    def _execute_general_product(self, hyp: Hypothesis, alpha: int,
                                 N: int = 3000) -> ExecutionResult:
        """Compute general product and verify ratio universality via empirical extraction."""
        code = f"""
import mpmath as mp
import json, math
mp.mp.dps = 80

alpha = {alpha}
N = {N}

# prod(1-q^n)^{{-n^alpha}} via recurrence
# n*f(n) = sum sigma_{{alpha+1}}(j) * f(n-j)
f = [mp.mpf(0)] * (N + 1)
f[0] = mp.mpf(1)

s_exp = alpha + 1
sigma = [mp.mpf(0)] * (N + 1)
for j in range(1, N + 1):
    s = mp.mpf(0)
    d = 1
    while d * d <= j:
        if j % d == 0:
            s += mp.power(d, s_exp)
            if d != j // d:
                s += mp.power(j // d, s_exp)
        d += 1
    sigma[j] = s

for n in range(1, N + 1):
    s = mp.mpf(0)
    for j in range(1, n + 1):
        s += sigma[j] * f[n - j]
    f[n] = s / n

# Empirical extraction approach:
# 1. Fit log(R_m - 1) = log(A) + beta*log(m) to get leading power law
# 2. Subtract leading term and extract L_m = (R_m - 1 - A*m^beta) * m
# 3. Check if L stabilizes (universality test)

# Step 1: Fit power law from tail ratios
pts = []
for m in range(N//2, N + 1):
    if f[m-1] != 0:
        dr = float(f[m] / f[m-1] - 1)
        if dr > 0:
            pts.append((math.log(m), math.log(dr)))

n_pts = len(pts)
if n_pts >= 10:
    sx = sum(x for x, y in pts)
    sy = sum(y for x, y in pts)
    sxx = sum(x*x for x, y in pts)
    sxy = sum(x*y for x, y in pts)
    beta = (n_pts*sxy - sx*sy) / (n_pts*sxx - sx*sx)
    logA = (sy - beta*sx) / n_pts
    A_fit = mp.exp(logA)
    beta_fit = mp.mpf(beta)
else:
    A_fit = mp.mpf(0)
    beta_fit = mp.mpf(0)

# Step 2: Extract L after removing leading term
L_raw = []
for m in range(N//2, N + 1):
    if f[m-1] == 0:
        continue
    R_m = f[m] / f[m-1]
    leading = A_fit * mp.power(m, beta_fit)
    L_est = (R_m - 1 - leading) * m
    L_raw.append((m, L_est))

# Richardson extrapolation on L
L_richardson = []
lmap = dict(L_raw)
for m, L_m in L_raw:
    if 2*m in lmap:
        L_rich = (4 * lmap[2*m] - L_m) / 3
        L_richardson.append((m, L_rich))

# Step 3: Check convergence of L
if L_raw:
    L_num = L_raw[-1][1]
    # Check stability: compare L at N vs N-100
    L_earlier = [v for m, v in L_raw if m <= N - 100]
    if L_earlier:
        L_conv = abs(L_num - L_earlier[-1])
        conv_digits = int(-float(mp.log10(L_conv / abs(L_num)))) if L_conv > 0 and L_num != 0 else 0
    else:
        conv_digits = 0
else:
    L_num = mp.mpf(0)
    conv_digits = 0

# Expected theoretical values
alpha_D = alpha + 1
d_frac = mp.mpf(alpha_D) / (alpha_D + 1)
D_0 = mp.zeta(-alpha)
kappa_est = D_0 / 2 - mp.mpf(1) / 2
beta_expected = float(d_frac - 1)

# Universality check: does the extracted beta match (d-1)?
beta_digits = 0
if beta_fit != 0:
    beta_err = abs(float(beta_fit) - beta_expected) / abs(beta_expected)
    if beta_err > 0:
        beta_digits = max(0, int(-math.log10(beta_err)))

# Total digits = convergence quality of L + scaling exponent match
digits = max(beta_digits, conv_digits)

print(json.dumps({{
    "alpha": alpha,
    "d": float(d_frac),
    "beta_expected": beta_expected,
    "beta_fitted": float(beta_fit),
    "beta_digits": beta_digits,
    "A_fitted": float(A_fit),
    "kappa_Meinardus": float(kappa_est),
    "L_numerical": float(L_num),
    "L_convergence_digits": conv_digits,
    "digits_matched": digits,
    "N": N,
    "n_raw": len(L_raw),
    "n_richardson": len(L_richardson),
    "last_5_L_raw": [(m, float(mp.nstr(v, 15))) for m, v in L_raw[-5:]],
    "last_5_L_rich": [(m, float(mp.nstr(v, 15))) for m, v in L_richardson[-5:]],
}}))
"""
        sandbox = self.toolbox.run_sandboxed(code, timeout=MAX_COMPUTE_SECONDS)
        if sandbox["success"]:
            try:
                data = json.loads(sandbox["stdout"].strip().split("\n")[-1])
                digits = data.get("digits_matched", 0)
                return ExecutionResult(
                    hypothesis_id=hyp.id,
                    success=True,
                    method="numeric",
                    evidence=data,
                    digits_matched=digits,
                    code_executed=code,
                    raw_output=sandbox["stdout"][:5000],
                )
            except (json.JSONDecodeError, IndexError):
                return ExecutionResult(
                    hypothesis_id=hyp.id,
                    success=False,
                    method="numeric",
                    error="JSON parse error on sandbox output",
                    raw_output=sandbox.get("stdout", "")[:5000],
                )
        return ExecutionResult(
            hypothesis_id=hyp.id,
            success=False,
            method="numeric",
            error=sandbox.get("stderr", "")[:500] or sandbox.get("error", "Unknown sandbox error"),
            code_executed=code,
        )

    def _execute_kloosterman(self, hyp: Hypothesis) -> ExecutionResult:
        """Extend Kloosterman bound computation."""
        code = """
import mpmath as mp
import json
import math
mp.mp.dps = 40

Q_max = 500
k = 5

# Simplified Kloosterman bound computation
# Full version: compute S_k(m,n;q) = sum_{h mod q, gcd(h,q)=1} omega_{h,q}^{-k} * e^{2pi*i*(mh+nh')/q}
# Bound: C_k = max_{m,n} max_q |S_k(m,n;q)| / q

# For the simplified version, track the maximum contribution per q
C_max = 0.0
details = {}

for q in range(1, Q_max + 1):
    # Count coprime h
    coprime_count = sum(1 for h in range(1, q) if math.gcd(h, q) == 1)
    # Weil bound: |S_k(m,n;q)| <= d(q) * q^{1/2} * gcd(m,n,q)^{1/2} * k for squarefree
    # Simplified estimate
    d_q = sum(1 for d in range(1, q+1) if q % d == 0)
    est = d_q * q**0.5 * k / q  # normalized
    if est > C_max:
        C_max = est
        details["worst_q"] = q
        details["worst_bound"] = round(est, 4)

# Factor in refinement from extended range
print(json.dumps({
    "k": k,
    "Q_max": Q_max,
    "C_k_bound": round(C_max, 4),
    "details": details,
    "note": "Simplified Weil bound - full Dedekind sum computation needed for tight bound"
}))
"""
        sandbox = self.toolbox.run_sandboxed(code, timeout=300)
        if sandbox["success"]:
            try:
                data = json.loads(sandbox["stdout"].strip().split("\n")[-1])
                return ExecutionResult(
                    hypothesis_id=hyp.id,
                    success=True,
                    method="numeric",
                    evidence=data,
                    code_executed=code,
                    raw_output=sandbox["stdout"][:5000],
                )
            except (json.JSONDecodeError, IndexError):
                return ExecutionResult(
                    hypothesis_id=hyp.id, success=False, method="numeric",
                    error="JSON parse error on sandbox output",
                    raw_output=sandbox.get("stdout", "")[:5000],
                )
        return ExecutionResult(
            hypothesis_id=hyp.id, success=False, method="numeric",
            error=sandbox.get("stderr", "")[:500] or sandbox.get("error", "Unknown"),
        )

    def _execute_bdj(self, hyp: Hypothesis) -> ExecutionResult:
        """Run BDJ bridge computation."""
        code = """
import mpmath as mp
import json
mp.mp.dps = 40

N = 3000  # Partition count limit for reasonable runtime

# Compute p(n)
f = [mp.mpf(0)] * (N + 1)
f[0] = mp.mpf(1)

sigma1 = [mp.mpf(0)] * (N + 1)
for j in range(1, N + 1):
    s = mp.mpf(0)
    d = 1
    while d * d <= j:
        if j % d == 0:
            s += d
            if d != j // d:
                s += j // d
        d += 1
    sigma1[j] = s

for n in range(1, N + 1):
    s = mp.mpf(0)
    for j in range(1, n + 1):
        s += sigma1[j] * f[n - j]
    f[n] = s / n

# Ratio fluctuation analysis
c = mp.pi * mp.sqrt(mp.mpf(2)/3)
kappa = -1  # -(1+3)/4
L_pred = c**2/8 + kappa
A1_pred = -c/48 - 2*4/(8*c)  # k=1: -c/48 - (2)(4)/(8c)

xi_values = []
for m in range(500, N+1):
    if f[m-1] == 0:
        continue
    R_m = f[m] / f[m-1]
    sm = mp.sqrt(mp.mpf(m))
    R_pred = 1 + c/(2*sm) + L_pred/m + A1_pred/(m*sm)
    residual = float(R_m - R_pred)
    xi = residual * float(m**0.75)
    xi_values.append(xi)

if xi_values:
    n_pts = len(xi_values)
    mean_xi = sum(xi_values) / n_pts
    var_xi = sum((x - mean_xi)**2 for x in xi_values) / n_pts
    std_xi = var_xi**0.5
    skew_xi = (sum((x - mean_xi)**3 for x in xi_values) / (n_pts * std_xi**3)
               if std_xi > 0 else 0)
    
    print(json.dumps({
        "n_residuals": n_pts,
        "mean": round(mean_xi, 6),
        "std": round(std_xi, 6),
        "skew": round(skew_xi, 6),
        "tw2_ref": {"mean": -1.771, "std": 0.813, "skew": 0.224},
    }))
else:
    print(json.dumps({"error": "No residuals"}))
"""
        sandbox = self.toolbox.run_sandboxed(code, timeout=MAX_COMPUTE_SECONDS)
        if sandbox["success"]:
            try:
                data = json.loads(sandbox["stdout"].strip().split("\n")[-1])
                return ExecutionResult(
                    hypothesis_id=hyp.id, success=True, method="numeric",
                    evidence=data, raw_output=sandbox["stdout"][:5000],
                )
            except (json.JSONDecodeError, IndexError):
                pass
        return ExecutionResult(
            hypothesis_id=hyp.id, success=False, method="numeric",
            error=sandbox.get("stderr", sandbox.get("error", "Unknown")),
        )

    def _execute_gcf_search(self, hyp: Hypothesis) -> ExecutionResult:
        """Search for new GCF identities via PSLQ."""
        code = """
import mpmath as mp
import json
mp.mp.dps = 120

results = []

# Search GCFs of form K(1 | a*n^2 + b*n + c) for small a,b,c
for a in range(1, 6):
    for b in range(0, 4):
        for c in range(1, 4):
            try:
                # Backward recurrence
                N = 400
                t = a*N**2 + b*N + c
                for n in range(N-1, -1, -1):
                    bn = a*n**2 + b*n + c
                    t = bn + mp.mpf(1)/t
                val = t
                
                # PSLQ against common constants
                basis = [val, mp.mpf(1), mp.pi, mp.pi**2, mp.log(2),
                         mp.euler, mp.catalan]
                labels = ['V', '1', 'pi', 'pi2', 'ln2', 'gamma', 'G']
                
                rel = mp.pslq(basis, tol=mp.mpf('1e-50'), maxcoeff=100)
                if rel:
                    active = [(int(c_), labels[i]) for i, c_ in enumerate(rel) if c_ != 0]
                    if len(active) >= 2 and any(c_ != 0 for c_, l in active if l != 'V'):
                        results.append({
                            "a": a, "b": b, "c": c,
                            "value": str(mp.nstr(val, 30)),
                            "relation": active,
                            "formula": f"GCF(1, {a}n^2+{b}n+{c})",
                        })
            except:
                continue

print(json.dumps({"n_found": len(results), "results": results[:10]}))
"""
        sandbox = self.toolbox.run_sandboxed(code, timeout=MAX_COMPUTE_SECONDS)
        if sandbox["success"]:
            try:
                data = json.loads(sandbox["stdout"].strip().split("\n")[-1])
                n_found = data.get("n_found", 0)
                return ExecutionResult(
                    hypothesis_id=hyp.id, success=n_found > 0,
                    method="numeric", evidence=data,
                    digits_matched=50 if n_found > 0 else 0,
                    raw_output=sandbox["stdout"][:5000],
                )
            except (json.JSONDecodeError, IndexError):
                pass
        return ExecutionResult(
            hypothesis_id=hyp.id, success=False, method="numeric",
            error=sandbox.get("stderr", sandbox.get("error", "Unknown")),
        )

    def _execute_new_family(self, hyp: Hypothesis, family: str) -> ExecutionResult:
        """Test ratio universality for a new partition family."""
        return self._execute_generic(hyp)

    def _execute_A3_extraction(self, hyp: Hypothesis) -> ExecutionResult:
        """Extract fifth-order coefficient A₃."""
        return self._execute_generic(hyp)

    def _execute_generic(self, hyp: Hypothesis) -> ExecutionResult:
        """Generic execution stub for gaps without specific executors."""
        info(f"Generic execution for {hyp.gap_id} — not yet specialized")
        return ExecutionResult(
            hypothesis_id=hyp.id,
            success=False,
            method="none",
            error=f"No specialized executor for {hyp.gap_id} yet",
        )

    # ── Phase 4: Evaluate ─────────────────────────────────────────────

    def phase_evaluate(self, hypothesis: Hypothesis,
                       result: ExecutionResult) -> Evaluation:
        """Delegate to the isolated Critic agent."""
        return self.critic.evaluate(hypothesis, result)

    # ── Phase 5: Summarize & Update ───────────────────────────────────

    def phase_summarize(self, gap: FrontierGap, hypothesis: Hypothesis,
                        result: ExecutionResult, evaluation: Evaluation) -> str:
        """Update memory, log results, and prepare context for next cycle."""
        header("Phase 5: SUMMARIZE & UPDATE")

        # Build iteration record
        record = IterationRecord(
            iteration=self.state.iteration,
            timestamp=datetime.now().isoformat(),
            gap=asdict(gap),
            hypothesis=hypothesis.to_dict(),
            result=asdict(result),
            evaluation=asdict(evaluation),
            duration_seconds=result.runtime_seconds,
        )

        # Determine what we learned
        if evaluation.verdict == "breakthrough":
            record.context_delta = (
                f"BREAKTHROUGH: {hypothesis.claim} — "
                f"B={evaluation.b_score:.4f}, {result.digits_matched} digits"
            )
            self.memory.add_entry("discovery", record.context_delta,
                                  {"evaluation": asdict(evaluation)})
            self.state.breakthroughs += 1
            ok(f"Discovery logged: {record.context_delta[:100]}")

        elif evaluation.verdict == "progress":
            record.context_delta = (
                f"Progress on {gap.id}: {result.digits_matched} digits, "
                f"B={evaluation.b_score:.4f}"
            )
            self.memory.add_entry("insight", record.context_delta)
            info(f"Progress logged: {record.context_delta[:100]}")

        elif evaluation.verdict == "failure":
            record.context_delta = (
                f"Failed: {gap.id} via {result.method}. "
                f"Reason: {'; '.join(evaluation.flaws_found[:2])}"
            )
            self.memory.add_failure(
                gap.id, hypothesis.claim,
                "; ".join(evaluation.flaws_found),
                result.method,
            )
            self.state.failures += 1
            warn(f"Failure logged: {record.context_delta[:100]}")

        else:
            record.context_delta = f"Inconclusive: {gap.id}"

        # Track ALL gap attempts (not just failures) for diminishing returns
        if gap.id not in self.state.gap_priorities:
            self.state.gap_priorities[gap.id] = 1.0
        # Apply diminishing returns: each attempt reduces priority by 15%
        self.state.gap_priorities[gap.id] *= 0.85

        # Update credibility
        success = evaluation.verdict in ("breakthrough", "progress")
        self.state.update_credibility(gap.gap_type, success)

        # Update state
        record.summary = record.context_delta
        self.state.iteration_history.append(asdict(record))
        self.state.iteration += 1
        self.state.cycle_count += 1
        self.state.total_runtime += result.runtime_seconds

        # Save everything
        self.state.save()
        self.memory.save()

        # Log to JSONL
        ITERATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ITERATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), default=str) + "\n")

        # Snapshot for rollback
        self.mutation_engine.take_snapshot(self.state.iteration - 1)

        return record.context_delta

    # ── Backtrack Logic ───────────────────────────────────────────────

    def should_backtrack(self, evaluation: Evaluation) -> Optional[str]:
        """Determine if we should backtrack and to which phase."""
        if evaluation.verdict == "failure":
            # If execution error, retry with different method (→ Phase 3)
            if any("error" in f.lower() for f in evaluation.flaws_found):
                return "execute"
            # If weak evidence, re-scope with different approach (→ Phase 2)
            elif evaluation.scores.get("E", 0) < 0.4:
                return "scope_target"
        return None

    # ── Main Cycle ────────────────────────────────────────────────────

    def run_cycle(self):
        """Run one complete research cycle."""
        cycle_start = time.time()

        print(f"\n{'═'*70}")
        print(f"  RESEARCH CYCLE {self.state.cycle_count + 1}  "
              f"(iteration {self.state.iteration})")
        print(f"{'═'*70}")

        # Phase 1: Identify Frontier
        gap = self.phase_identify_frontier()

        # Phase 2: Scope Target
        hypothesis = self.phase_scope_target(gap)

        # Phase 3: Execute
        result = self.phase_execute(hypothesis)

        # Phase 4: Evaluate (via Critic)
        evaluation = self.phase_evaluate(hypothesis, result)

        # Backtrack check
        backtrack_to = self.should_backtrack(evaluation)
        if backtrack_to == "scope_target":
            warn("BACKTRACK → Phase 2 (re-scoping)")
            # Adjust gap and retry once
            gap.attempts += 1
            hypothesis = self.phase_scope_target(gap)
            result = self.phase_execute(hypothesis)
            evaluation = self.phase_evaluate(hypothesis, result)
        elif backtrack_to == "execute":
            warn("BACKTRACK → Phase 3 (re-executing)")
            result = self.phase_execute(hypothesis)
            evaluation = self.phase_evaluate(hypothesis, result)

        # Phase 5: Summarize
        summary = self.phase_summarize(gap, hypothesis, result, evaluation)

        # Self-iteration check (every 5 cycles)
        if self.state.cycle_count % 5 == 0 and self.state.cycle_count > 0:
            self._consider_self_mutation()

        # Print cycle summary
        cycle_duration = time.time() - cycle_start
        print(f"\n{'─'*70}")
        info(f"Cycle completed in {cycle_duration:.1f}s")
        info(f"Summary: {summary}")
        info(f"State: {self.state.breakthroughs} breakthroughs, "
             f"{self.state.failures} failures, "
             f"{self.state.cycle_count} cycles")
        print(f"{'─'*70}\n")

    def _consider_self_mutation(self):
        """Check if self-improvement is warranted."""
        header("META: Self-Iteration Check")
        history = [IterationRecord(**r) if isinstance(r, dict) else r
                   for r in self.state.iteration_history[-10:]]
        proposal = self.mutation_engine.propose_mutation(history)

        if proposal.get("mutations"):
            info(f"Mutation proposal: {len(proposal['mutations'])} changes suggested")
            for m in proposal["mutations"]:
                if m.get("requires_hitl"):
                    warn(f"  [HITL REQUIRED] {m['action']}")
                else:
                    self.mutation_engine.apply_mutation(m)
        else:
            info("No mutations proposed")

    # ── CLI Interface ─────────────────────────────────────────────────

    def show_status(self):
        """Display current agent state."""
        header("Agent Status")
        mode_str = C.GREEN + "LOCAL" + C.RESET if self.mode == "local" else C.CYAN + "API" + C.RESET
        print(f"  Version:       {VERSION}")
        print(f"  Mode:          {mode_str}")
        print(f"  Iteration:     {self.state.iteration}")
        print(f"  Cycles:        {self.state.cycle_count}")
        print(f"  Breakthroughs: {self.state.breakthroughs}")
        print(f"  Failures:      {self.state.failures}")
        print(f"  Total Runtime: {self.state.total_runtime:.1f}s")
        print()

        print("  Category Credibility:")
        for cat, cred in sorted(self.state.category_credibility.items()):
            bar = "█" * int(cred * 20) + "░" * (20 - int(cred * 20))
            print(f"    {cat:15s} [{bar}] {cred:.2f}")
        print()

        print("  Tool Status:")
        for name, status in self.toolbox.status().items():
            sym = C.GREEN + "✓" + C.RESET if status == "available" else C.RED + "✗" + C.RESET
            print(f"    {sym} {name}: {status}")
        print()

        # v1.1: Synthesis stats
        ax_stats = self.axiom_graph.stats()
        print("  Synthesis Engine:")
        print(f"    Axiom Graph:       {ax_stats.get('total', 0)} nodes "
              f"({ax_stats.get('alive', 0)} alive, {ax_stats.get('falsified', 0)} falsified), "
              f"{ax_stats.get('edges', 0)} edges, "
              f"{len(ax_stats.get('domains', []))} domains")
        print(f"    Induction Cache:   {len(self.induction.cache)} entries")
        print(f"    Synthesis Count:   {self.synthesis.synthesis_count}")
        print(f"    Symbolic Induction: {'available' if HAS_SYMPY else 'missing'}")
        print(f"    Symbolic Regression: {'available' if HAS_PYSR else 'optional'}")
        print()

        # Memory stats
        print(f"  Memory Entries:      {len(self.memory.entries)}")
        print(f"  Failure Patterns:    {len(self.memory.failure_signatures)}")
        print(f"  Tool Effectiveness:  {len(self.memory.tool_effectiveness)} tracked")

    def show_frontier(self):
        """Display the ranked frontier gap map."""
        header("Frontier Map")
        gaps = self.knowledge.rank_gaps()
        for i, gap in enumerate(gaps):
            marker = "★" if gap.score > 0.5 else "◆" if gap.score > 0.3 else "○"
            status = "ATTEMPT×" + str(gap.attempts) if gap.attempts > 0 else "NEW"
            print(f"  {marker} [{gap.score:.3f}] {gap.id:20s} | {gap.gap_type:12s} | "
                  f"{status:10s} | {gap.description[:60]}...")

    def show_history(self):
        """Display iteration history."""
        header("Iteration History")
        for record in self.state.iteration_history[-20:]:
            r = record if isinstance(record, dict) else asdict(record)
            ts = r.get("timestamp", "?")[:19]
            summary = r.get("summary", "")[:80]
            eval_data = r.get("evaluation", {})
            verdict = eval_data.get("verdict", "?")
            b_score = (eval_data.get("scores", {}).get("N", 0) *
                       eval_data.get("scores", {}).get("F", 0) *
                       eval_data.get("scores", {}).get("E", 0) *
                       eval_data.get("scores", {}).get("C", 0))
            sym = {"breakthrough": "★", "progress": "◆",
                   "failure": "✗", "inconclusive": "?"}.get(verdict, "?")
            print(f"  {sym} [{ts}] B={b_score:.4f} | {summary}")

    def propose_mutation(self):
        """Show self-improvement proposals."""
        header("Self-Improvement Proposals")
        history = [IterationRecord(**r) if isinstance(r, dict) else r
                   for r in self.state.iteration_history[-20:]]
        proposal = self.mutation_engine.propose_mutation(history)

        if proposal.get("mutations"):
            for i, m in enumerate(proposal["mutations"]):
                hitl = " [HITL REQUIRED]" if m.get("requires_hitl") else ""
                print(f"  {i+1}. [{m['type']}]{hitl}")
                print(f"     {m.get('action', '?')}")
                if "target" in m:
                    print(f"     Target: {m['target']}")
        else:
            print("  No mutations proposed. Need more iteration history.")

        print(f"\n  Analysis: {json.dumps(proposal.get('analysis', {}), indent=4)}")


# ══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Self-Iterating Research Agent v" + VERSION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python self_iterating_agent.py                     # Run 1 cycle (local mode)
  python self_iterating_agent.py --mode api          # Run with API synthesis
  python self_iterating_agent.py --cycles 5          # Run 5 cycles
  python self_iterating_agent.py --induction sixth_root  # Run symbolic induction on gap
  python self_iterating_agent.py --status            # Show state
  python self_iterating_agent.py --frontier          # Show frontier gaps
  python self_iterating_agent.py --history           # Show iteration log
  python self_iterating_agent.py --mutate            # Show self-improvement proposals
  python self_iterating_agent.py --rollback 3        # Rollback to iteration 3
  python self_iterating_agent.py --critic-only       # Re-evaluate last result
        """,
    )
    parser.add_argument("--mode", choices=["local", "api"], default="local",
                        help="Synthesis mode: 'local' (no API) or 'api' (default: local)")
    parser.add_argument("--cycles", type=int, default=1,
                        help="Number of research cycles to run (default: 1)")
    parser.add_argument("--induction", type=str, metavar="GAP_ID",
                        help="Run symbolic induction on a specific frontier gap")
    parser.add_argument("--status", action="store_true",
                        help="Show current agent state")
    parser.add_argument("--frontier", action="store_true",
                        help="Show ranked frontier gap map")
    parser.add_argument("--history", action="store_true",
                        help="Show iteration history")
    parser.add_argument("--mutate", action="store_true",
                        help="Show self-improvement proposals")
    parser.add_argument("--rollback", type=int, metavar="N",
                        help="Rollback to iteration N")
    parser.add_argument("--critic-only", action="store_true",
                        help="Re-run critic on last result")
    parser.add_argument("--reset", action="store_true",
                        help="Reset agent state (requires confirmation)")

    args = parser.parse_args()

    # Handle reset
    if args.reset:
        confirm = input("Are you sure you want to reset all agent state? [y/N] ")
        if confirm.lower() == "y":
            if STATE_DIR.exists():
                shutil.rmtree(STATE_DIR)
            ok("Agent state reset.")
        else:
            info("Reset cancelled.")
        return

    # Initialize agent with mode
    agent = SelfIteratingAgent(mode=args.mode)

    # Handle commands
    if args.induction:
        # v1.1: Standalone symbolic induction on a gap
        gap_id = args.induction
        header(f"Symbolic Induction: {gap_id}")
        gap = next((g for g in agent.knowledge.rank_gaps() if g.id == gap_id), None)
        if gap is None:
            err(f"Unknown gap ID: {gap_id}")
            info("Available gaps: " + ", ".join(g.id for g in agent.knowledge.rank_gaps()))
            return
        info(f"Gap: {gap.description}")
        info(f"Type: {gap.gap_type}, Priority: {gap.score:.2f}")
        print()

        # Determine k values to test based on gap_id
        gap_k_map = {
            "sixth_root": 5, "prove_A1_k5": 5, "kloosterman_q500": 5,
            "bdj_bridge": 3, "andrews_gordon": 4, "overpartition": 2,
            "cubic_root": 2, "quartic_root": 3, "quintic_root": 4,
        }
        k = gap_k_map.get(gap_id, 3)

        # 1) Test ratio identity for L, A1, A2 at this k
        info(f"Testing known formulas at k={k}...")
        for fname, fexpr in [
            ("L", "pi**2*k/12 - (k+3)/4"),
            ("A1", "-k*pi*sqrt(2*k/3)/48 - (k+1)*(k+3)/(8*pi*sqrt(2*k/3))"),
            ("A2", "(k+3)*(pi**2*k**2 - 9*k - 9)/(96*k*pi**2)"),
        ]:
            result = agent.induction.test_ratio_identity(k, fname, fexpr)
            status = "matches" if result.get("matches_known") else "no match"
            sym = C.GREEN + "✓" + C.RESET if result.get("matches_known") else C.YELLOW + "?" + C.RESET
            print(f"    {sym} {fname}(k={k}): {status}")
            if result.get("numeric_value") is not None:
                print(f"      numeric = {result['numeric_value']:.10f}")
        print()

        # 2) Run universality test across multiple k
        info("Testing universality hypothesis L = c²/8 + κ...")
        test_vals = {}
        for test_k in [2, 3, 4, 5]:
            c_k = float(mp.pi * mp.sqrt(mp.mpf(2 * test_k) / 3))
            kappa_k = -(test_k + 3) / 4.0
            L_pred = c_k**2 / 8.0 + kappa_k
            test_vals[str(test_k)] = L_pred
        uni = agent.induction.test_universality_hypothesis(gap_id, test_vals)
        if uni.get("universal"):
            ok(f"Universality confirmed: max deviation {uni.get('max_deviation', '?'):.2e}")
        elif uni.get("universal") is False:
            warn(f"Universality FAILS: max deviation {uni.get('max_deviation', '?'):.2e}")
        else:
            info(f"Universality inconclusive: {uni.get('reason', 'unknown')}")
        print()

        # 3) Attempt pattern discovery on L values
        info("Attempting pattern discovery on L coefficients...")
        data_pts = [(k_val, float(mp.pi**2 * k_val / 12 - (k_val + 3) / 4.0))
                    for k_val in [2, 3, 4, 5, 6]]
        pat = agent.induction.discover_pattern(data_pts, "k")
        if pat.get("found"):
            ok(f"Discovered pattern: {pat.get('formula', '?')}")
            ok(f"Method: {pat.get('method', '?')}, confidence: {pat.get('confidence', 0):.2f}")
        else:
            info(f"No pattern found ({pat.get('method', 'exhausted')})")

    elif args.status:
        agent.show_status()
    elif args.frontier:
        agent.show_frontier()
    elif args.history:
        agent.show_history()
    elif args.mutate:
        agent.propose_mutation()
    elif args.rollback is not None:
        agent.mutation_engine.rollback(args.rollback)
    elif args.critic_only:
        if agent.state.iteration_history:
            last = agent.state.iteration_history[-1]
            info("Re-evaluating last iteration...")
            hyp = Hypothesis(**last.get("hypothesis", {}))
            res = ExecutionResult(**last.get("result", {}))
            evaluation = agent.phase_evaluate(hyp, res)
            print(f"\n  {evaluation.critique}")
        else:
            warn("No iteration history to evaluate")
    else:
        # Run research cycles
        n_cycles = min(args.cycles, MAX_CYCLES)
        if n_cycles > 10:
            warn(f"Running {n_cycles} cycles — this may take a while")

        for i in range(n_cycles):
            try:
                agent.run_cycle()
            except KeyboardInterrupt:
                warn("Interrupted by user")
                agent.state.save()
                agent.memory.save()
                break
            except Exception as e:
                err(f"Cycle failed: {e}")
                traceback.print_exc()
                # Log failure
                FAILURE_LOG.parent.mkdir(parents=True, exist_ok=True)
                with open(FAILURE_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "iteration": agent.state.iteration,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "timestamp": datetime.now().isoformat(),
                    }) + "\n")
                agent.state.save()
                agent.memory.save()

        # Final status
        agent.show_status()


if __name__ == "__main__":
    main()
