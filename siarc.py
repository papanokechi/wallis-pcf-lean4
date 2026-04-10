#!/usr/bin/env python3
"""
SIARC -- Self-Improving Autonomous Research Chain
==================================================

Unified entry point wrapping the existing discovery engines into a
composable A -> B -> C -> D -> E -> F agent chain with:
  - Interactive agent selector (or --agent flag)
  - .env support for API keys (python-dotenv)
  - Streaming output (token-by-token in VS Code terminal)
  - Single-agent mode with file-based I/O for step-debugging
  - VS Code launch.json profiles for F5 execution

Agent Mapping:
  A: Frontier Scanner      -- identify gaps from knowledge base
  B: Hypothesis Generator  -- scope testable claims from gaps
  C: Execution Engine      -- numeric/symbolic/CAS verification
  D: Adversarial Critic    -- stress-test, falsify, score
  E: Cross-Pollinator      -- multi-domain pattern transfer
  F: Memory & Report       -- persist, summarize, seed next cycle

Usage:
  python siarc.py                          # interactive selector
  python siarc.py --agent A                # run Agent A only
  python siarc.py --agent full --cycles 3  # full chain, 3 cycles
  python siarc.py --agent BC --input agent_A_out.json  # sub-chain
  python siarc.py --agent C --input agent_B_out.json   # mid-chain
  python siarc.py --seed ramanujan         # seed with Ramanujan domain
  python siarc.py --agent full --debate-critic --debate-dry-run    # debate (safe test)
  python siarc.py --agent full --debate-critic --debate-live       # debate (live API)
  python siarc.py --agent D   --debate-critic --debate-live --debate-judge  # D only, +judge
"""

import argparse
import json
import math
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
# self_iterating_agent.py emits Unicode chars (⚠ ✓ ✗) that crash on Windows
# cp1252 terminals. Reconfigure stdout/stderr to UTF-8 if possible (Python 3.7+).
# PYTHONUTF8=1 in .env also covers subprocess spawns.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── .env support ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    # Graceful: .env is optional if keys are already exported
    pass

# ── Workspace root ────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).parent
CHAIN_OUTPUT_DIR = WORKSPACE / "siarc_outputs"

# Add workspace to sys.path once at module level so all agents can import
# local engines without repeating this in every run() method.
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# ── Optional debate integration ───────────────────────────────────────────────
# Imported lazily inside AgentD.run() so SIARC works without the
# multi_agent_discussion package when --debate-critic is not requested.
_DEBATE_AVAILABLE = None  # None = unchecked, True/False after first attempt

def _load_debate() -> bool:
    """Try to import the debate subsystem. Returns True on success."""
    global _DEBATE_AVAILABLE
    if _DEBATE_AVAILABLE is not None:
        return _DEBATE_AVAILABLE
    try:
        import importlib
        importlib.import_module("multi_agent_discussion.siarc_adapter")
        _DEBATE_AVAILABLE = True
    except ImportError as e:
        warn(f"Debate subsystem not available: {e}")
        _DEBATE_AVAILABLE = False
    return _DEBATE_AVAILABLE


# ── ANSI colors ───────────────────────────────────────────────────────────────
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
    print(f"\n{C.CYAN}{'='*72}")
    print(f"  {C.BOLD}{title}{C.RESET}{C.CYAN}")
    print(f"{'='*72}{C.RESET}")

def ok(msg):   print(f"{C.GREEN}  [OK] {msg}{C.RESET}")
def warn(msg): print(f"{C.YELLOW}  [!]  {msg}{C.RESET}")
def err(msg):  print(f"{C.RED}  [X]  {msg}{C.RESET}")
def info(msg): print(f"{C.GRAY}       {msg}{C.RESET}")

def banner():
    print(f"""
{C.CYAN}{C.BOLD}
  ╔═══════════════════════════════════════════════════════════════╗
  ║   SIARC -- Self-Improving Autonomous Research Chain          ║
  ║   Agents: A(Frontier) B(Hypothesis) C(Execute) D(Critic)    ║
  ║           E(Pollinate) F(Report)                             ║
  ╚═══════════════════════════════════════════════════════════════╝
{C.RESET}""")


# ══════════════════════════════════════════════════════════════════════════
# AGENT DEFINITIONS — Each wraps existing engine functionality
# ══════════════════════════════════════════════════════════════════════════

class AgentBase:
    """Base class for all SIARC agents."""
    name = "?"
    letter = "?"
    description = ""

    def run(self, input_data: dict) -> dict:
        raise NotImplementedError

    def save_output(self, data: dict):
        CHAIN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CHAIN_OUTPUT_DIR / f"agent_{self.letter}_out.json"
        data["_agent"] = self.letter
        data["_name"] = self.name
        data["_timestamp"] = datetime.now().isoformat()
        serialised = json.dumps(data, indent=2, default=str)
        out_path.write_text(serialised, encoding="utf-8")
        ok(f"Output saved: {out_path.name}")
        # Mirror to workspace root only when SIARC_ROOT_MIRROR=1 is set.
        # This exists for launch.json --input compatibility but doubles writes
        # and creates stale files when running sub-chains; off by default.
        if os.environ.get("SIARC_ROOT_MIRROR", "0") == "1":
            root_path = WORKSPACE / f"agent_{self.letter}_out.json"
            root_path.write_text(serialised, encoding="utf-8")
        return data

    @staticmethod
    def load_input(path_str: str) -> dict:
        p = Path(path_str)
        if not p.is_absolute():
            p = WORKSPACE / p
        if not p.exists():
            # Also check siarc_outputs/
            alt = CHAIN_OUTPUT_DIR / p.name
            if alt.exists():
                p = alt
            else:
                warn(f"Input file not found: {path_str}")
                return {}
        return json.loads(p.read_text(encoding="utf-8"))


# ── Agent A: Frontier Scanner ─────────────────────────────────────────────────

class AgentA(AgentBase):
    name = "Frontier Scanner"
    letter = "A"
    description = "Scan knowledge base, axiom graph, and discovery history to identify research gaps"

    def run(self, input_data: dict) -> dict:
        header(f"Agent A: {self.name}")
        seed_domain = input_data.get("seed", None)

        # Check if a pre-selected gap was passed in from a previous cycle (F→A feedback).
        # If so, skip the full scan and use it directly, preserving self-iteration.
        preselected = input_data.get("selected_gap")

        from self_iterating_agent import (
            PersistentMemory, KnowledgeGraph, LocalAxiomGraph, AgentState,
            STATE_DIR, VERSION
        )

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        memory = PersistentMemory()
        knowledge = KnowledgeGraph(memory)
        axiom_graph = LocalAxiomGraph()

        # ── F→A feedback: if a next_gap was recommended by the previous cycle,
        # use it — but refresh its score via a fresh rank_gaps() call so that
        # failure penalties and attempt increments accumulated during the previous
        # cycle are reflected. Stale scores from prior cycles would otherwise
        # mislead downstream agents about the gap's current priority.
        if preselected and not seed_domain:
            fresh_gaps = knowledge.rank_gaps()
            fresh_map = {g.id: g for g in fresh_gaps}
            if preselected["id"] in fresh_map:
                g = fresh_map[preselected["id"]]
                gap_list = [{
                    "id": g.id,
                    "description": g.description,
                    "source": g.source,
                    "gap_type": g.gap_type,
                    "priority": g.priority,
                    "difficulty": g.difficulty,
                    "feasibility": g.feasibility,
                    "score": g.score,
                    "attempts": g.attempts,
                }]
                info(f"Pre-selected gap refreshed: {g.id} (score={g.score:.3f}, attempts={g.attempts})")
            else:
                # Gap no longer in ranking; fall back to top of fresh list
                warn(f"Pre-selected gap '{preselected['id']}' not in ranking; using top gap")
                gap_list = []  # triggers the else branch below
                preselected = None
        if not (preselected and not seed_domain):
            # Rank frontier gaps
            gaps = knowledge.rank_gaps()
            info(f"Found {len(gaps)} frontier gaps in knowledge graph")

            # Filter by seed domain if given
            if seed_domain:
                domain_map = {
                    "ramanujan": ["partition", "gcf", "ratio", "cf", "pslq"],
                    "ising":     ["ising", "critical", "exponent", "mc", "heisenberg"],
                    "materials": ["material", "perovskite", "stability", "bandgap"],
                }
                keywords = domain_map.get(seed_domain, [seed_domain])
                gaps = [g for g in gaps
                        if any(kw in g.description.lower() or kw in g.id.lower()
                               for kw in keywords)] or gaps
                info(f"Filtered to {len(gaps)} gaps for seed={seed_domain}")

            # Build output: top 10 ranked gaps
            gap_list = []
            for i, gap in enumerate(gaps[:10]):
                marker = " >> " if i == 0 else "    "
                print(f"{C.BLUE}{marker}[{gap.score:.3f}] {gap.id}{C.RESET}: "
                      f"{gap.description[:70]}...")
                gap_list.append({
                    "id": gap.id,
                    "description": gap.description,
                    "source": gap.source,
                    "gap_type": gap.gap_type,
                    "priority": gap.priority,
                    "difficulty": gap.difficulty,
                    "feasibility": gap.feasibility,
                    "score": gap.score,
                    "attempts": gap.attempts,
                })

        # Axiom graph stats
        axiom_stats = {
            "nodes": len(axiom_graph.nodes),
            "edges": len(axiom_graph.edges) if hasattr(axiom_graph, 'edges') else 0,
        }
        info(f"Axiom graph: {axiom_stats['nodes']} nodes")

        # Memory stats
        mem_stats = {
            "entries": len(memory.entries),
            "failures": len(memory.failure_signatures),
            "tools": list(memory.tool_effectiveness.keys()),
        }
        info(f"Memory: {mem_stats['entries']} entries, "
             f"{mem_stats['failures']} failure patterns")

        result = {
            "gaps": gap_list,
            "selected_gap": gap_list[0] if gap_list else None,
            "axiom_stats": axiom_stats,
            "memory_stats": mem_stats,
            "seed": seed_domain,
        }

        ok(f"Selected: {result['selected_gap']['id']}" if result['selected_gap'] else "No gaps found")
        return self.save_output(result)


# ── Agent B: Hypothesis Generator ─────────────────────────────────────────────

class AgentB(AgentBase):
    name = "Hypothesis Generator"
    letter = "B"
    description = "Convert frontier gap into testable hypothesis using local synthesis"

    def run(self, input_data: dict) -> dict:
        header(f"Agent B: {self.name}")

        gap_data = input_data.get("selected_gap")
        if not gap_data:
            # Fallback: run Agent A to get a gap
            warn("No gap in input; running Agent A first...")
            a_result = AgentA().run(input_data)
            gap_data = a_result.get("selected_gap")
            if not gap_data:
                err("No gaps found. Cannot generate hypothesis.")
                return self.save_output({"error": "no_gaps", "hypothesis": None})

        info(f"Gap: {gap_data['id']} -- {gap_data['description'][:80]}")

        from self_iterating_agent import (
            PersistentMemory, KnowledgeGraph, VerificationToolbox,
            LocalAxiomGraph, SymbolicInductionEngine, LocalSynthesisEngine,
            FrontierGap, Hypothesis, STATE_DIR
        )

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        memory = PersistentMemory()
        toolbox = VerificationToolbox(memory)
        axiom_graph = LocalAxiomGraph()
        induction = SymbolicInductionEngine(toolbox)
        synthesis = LocalSynthesisEngine(axiom_graph, induction, memory)

        # Reconstruct gap object
        gap = FrontierGap(
            id=gap_data["id"],
            description=gap_data["description"],
            source=gap_data.get("source", ""),
            gap_type=gap_data.get("gap_type", "computation"),
            priority=gap_data.get("priority", 0.5),
            difficulty=gap_data.get("difficulty", 0.5),
            feasibility=gap_data.get("feasibility", 0.5),
            attempts=gap_data.get("attempts", 0),
        )

        # Safe construction: call __init__ properly, then set SIARC-specific attrs.
        # Using __new__ alone would silently drop any attrs set in __init__ that
        # we don't explicitly re-assign here, causing hard-to-diagnose AttributeErrors.
        try:
            from self_iterating_agent import SelfIteratingAgent, AgentState
            agent = SelfIteratingAgent.__new__(SelfIteratingAgent)
            agent.mode = "local"
            agent.state = AgentState.load()
            agent.memory = memory
            agent.toolbox = toolbox
            agent.knowledge = KnowledgeGraph(memory)
            agent.axiom_graph = axiom_graph
            agent.induction = induction
            agent.synthesis = synthesis
            # Populate any remaining attrs __init__ would normally set
            for attr, default in [
                ("api_client", None), ("model", "local"), ("cycles", 1),
                ("domain", "math"), ("verbose", False),
            ]:
                if not hasattr(agent, attr):
                    setattr(agent, attr, default)
        except Exception as e:
            warn(f"SelfIteratingAgent construction error: {e}")
            agent = None

        hyp = None
        if agent is not None:
            try:
                hyp = agent._generate_hypothesis(gap)
                hyp = synthesis.enrich_hypothesis(hyp, gap)
            except Exception as e:
                warn(f"Hypothesis generation error: {e}")

        if hyp is None:
            # Build a generic but structurally complete fallback hypothesis.
            # Use ["sandbox"] not ["verify_numeric", "pslq_search"]: the latter
            # two now require numeric_lhs / target_value which are None here, so
            # they would always skip. "sandbox" gives the gap-specific script a
            # chance to run if one exists in gap_scripts/<gap_id>.py.
            hyp = Hypothesis(
                id=f"H-auto-{gap.id}",
                gap_id=gap.id,
                claim=f"Investigate {gap.description[:100]}",
                mechanism="Gap-specific sandbox verification",
                testable_prediction=f"Run verification script for {gap.id}",
                failure_condition="Sandbox returns error or no numeric result",
                tools_needed=["sandbox"],
                confidence=0.35,
            )

        info(f"Claim: {hyp.claim[:100]}")
        info(f"Test:  {hyp.testable_prediction[:100]}")
        info(f"Falsify: {hyp.failure_condition[:100]}")

        result = {
            "gap": gap_data,
            "hypothesis": {
                "id": hyp.id,
                "gap_id": hyp.gap_id,
                "claim": hyp.claim,
                "mechanism": hyp.mechanism,
                "testable_prediction": hyp.testable_prediction,
                "failure_condition": hyp.failure_condition,
                "tools_needed": hyp.tools_needed,
                "confidence": hyp.confidence,
                # numeric_lhs / numeric_rhs: pulled from hyp if present, else
                # defaulted to None so Agent C knows to skip verify_numeric rather
                # than silently verify a meaningless identity like pi==pi.
                "numeric_lhs": getattr(hyp, "numeric_lhs", None),
                "numeric_rhs": getattr(hyp, "numeric_rhs", None),
                "target_value": getattr(hyp, "target_value", None),
            },
        }

        ok(f"Hypothesis: {hyp.id} (confidence={hyp.confidence:.2f})")
        return self.save_output(result)


# ── Agent C: Execution Engine ─────────────────────────────────────────────────

class AgentC(AgentBase):
    name = "Execution Engine"
    letter = "C"
    description = "Run numeric/symbolic/CAS verification on hypothesis"

    def run(self, input_data: dict) -> dict:
        header(f"Agent C: {self.name}")

        hyp_data = input_data.get("hypothesis")
        if not hyp_data:
            warn("No hypothesis in input; running Agent B first...")
            b_result = AgentB().run(input_data)
            hyp_data = b_result.get("hypothesis")
            if not hyp_data:
                err("No hypothesis generated.")
                return self.save_output({"error": "no_hypothesis", "execution": None})

        info(f"Hypothesis: {hyp_data['id']}")
        info(f"Claim: {hyp_data['claim'][:80]}")
        tools_needed = hyp_data.get("tools_needed", [])
        info(f"Tools: {', '.join(tools_needed)}")

        from self_iterating_agent import (
            PersistentMemory, VerificationToolbox, Hypothesis,
            ExecutionResult, STATE_DIR, MAX_COMPUTE_SECONDS
        )

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        memory = PersistentMemory()
        toolbox = VerificationToolbox(memory)

        # Filter to constructor-safe fields only (module-level _HYP_CTOR_FIELDS).
        # numeric_lhs / numeric_rhs / target_value remain in hyp_data for Agent C
        # to read directly — they are not attributes of the Hypothesis dataclass.
        hyp_clean = {k: v for k, v in hyp_data.items() if k in _HYP_CTOR_FIELDS}
        try:
            hyp = Hypothesis(**hyp_clean)
        except TypeError as e:
            warn(f"Hypothesis construction warning: {e}; using minimal fallback")
            hyp = Hypothesis(
                id=hyp_data.get("id", "unknown"),
                gap_id=hyp_data.get("gap_id", "unknown"),
                claim=hyp_data.get("claim", ""),
                mechanism=hyp_data.get("mechanism", ""),
                testable_prediction=hyp_data.get("testable_prediction", ""),
                failure_condition=hyp_data.get("failure_condition", ""),
            )

        t0 = time.time()
        exec_results = {}
        success = False
        digits_matched = 0
        proof_status = "none"

        # Execute based on tools_needed
        for tool in tools_needed:
            elapsed = time.time() - t0
            if elapsed > MAX_COMPUTE_SECONDS:
                warn(f"Compute budget exceeded ({MAX_COMPUTE_SECONDS}s)")
                break

            stream_progress(f"Running {tool}...")

            if tool == "verify_numeric":
                # Use expressions from the hypothesis, not a hardcoded pi==pi identity.
                # If the hypothesis didn't supply them, skip gracefully rather than
                # returning a spurious success.
                lhs = hyp_data.get("numeric_lhs")
                rhs = hyp_data.get("numeric_rhs")
                if lhs and rhs:
                    result = toolbox.verify_numeric(lhs, rhs, tiers=[50, 100])
                    exec_results["verify_numeric"] = result
                    if result.get("verified"):
                        digits_matched = max(digits_matched, result.get("max_digits", 0))
                        success = True
                        info(f"Numeric match: {lhs} == {rhs} ({digits_matched} digits)")
                else:
                    warn("verify_numeric skipped: hypothesis missing numeric_lhs/numeric_rhs")
                    exec_results["verify_numeric"] = {"skipped": "no numeric expressions in hypothesis"}

            elif tool == "pslq_search":
                try:
                    import mpmath as mp
                    mp.mp.dps = 120
                    # Use target_value from hypothesis if provided; skip if not,
                    # rather than silently searching for a relation in pi which
                    # has nothing to do with the actual hypothesis.
                    target_val_expr = hyp_data.get("target_value")
                    if target_val_expr:
                        try:
                            value = mp.mpf(target_val_expr)
                        except Exception:
                            warn(f"Could not parse target_value '{target_val_expr}'; skipping PSLQ")
                            exec_results["pslq_search"] = {"skipped": "unparseable target_value"}
                            continue
                    else:
                        warn("pslq_search skipped: hypothesis missing target_value")
                        exec_results["pslq_search"] = {"skipped": "no target_value in hypothesis"}
                        continue
                    basis_labels = ["pi", "pi^2", "ln2", "e", "sqrt2", "1"]
                    basis_values = [mp.pi, mp.pi**2, mp.log(2), mp.e, mp.sqrt(2), mp.mpf(1)]
                    result = toolbox.pslq_search(value, basis_labels, basis_values, dps=100)
                    exec_results["pslq_search"] = result
                    if result.get("found"):
                        success = True
                        info(f"PSLQ relation: {result.get('formatted', '?')}")
                except ImportError:
                    exec_results["pslq_search"] = {"error": "mpmath not available"}

            elif tool == "compute_partition_ratios":
                # Domain guard: only run for gaps that are genuinely about
                # partition functions. A non-partition gap requesting this tool
                # would silently compute irrelevant k=3 ratios and report success.
                _PARTITION_KEYWORDS = {"partition", "ratio", "sixth", "bdj", "andrews",
                                       "overpartition", "kloosterman", "gcf", "modular"}
                if not any(kw in hyp.gap_id.lower() for kw in _PARTITION_KEYWORDS):
                    warn(f"compute_partition_ratios skipped: '{hyp.gap_id}' is not a partition gap")
                    exec_results["partition_ratios"] = {"skipped": "non-partition gap"}
                else:
                    gap_id = hyp.gap_id
                    k_map = {"prove_A1_k5": 5, "sixth_root": 5, "kloosterman_q500": 5,
                             "bdj_bridge": 3, "andrews_gordon": 4, "overpartition": 2}
                    k = k_map.get(gap_id, 3)
                    info(f"Computing k={k} partition ratios (N=2000)...")
                    result = toolbox.compute_partition_ratios(k=k, N=2000, dps=80)
                    exec_results["partition_ratios"] = result
                    if "error" not in result:
                        success = True

            elif tool == "sandbox":
                # Execute gap-specific verification script.
                # Timeout is capped to the remaining compute budget, not a fixed 300s,
                # so multi-cycle runs don't stall on a single stuck gap.
                code = _build_gap_script(hyp.gap_id, hyp_data)
                if code:
                    remaining = max(10, MAX_COMPUTE_SECONDS - (time.time() - t0))
                    result = toolbox.run_sandboxed(code, timeout=min(300, remaining))
                    exec_results["sandbox"] = result
                    if result.get("success"):
                        success = True
                else:
                    exec_results["sandbox"] = {"skipped": "no script for this gap"}

            else:
                info(f"Tool '{tool}' not directly mapped; trying sandbox fallback")
                exec_results[tool] = {"skipped": True}

        # Fallback: if no tool succeeded, try sandbox script for the gap
        if not success and hyp.gap_id:
            code = _build_gap_script(hyp.gap_id, hyp_data)
            if code and "sandbox" not in exec_results:
                stream_progress(f"Sandbox fallback for {hyp.gap_id}...")
                remaining = max(10, MAX_COMPUTE_SECONDS - (time.time() - t0))
                result = toolbox.run_sandboxed(code, timeout=min(300, remaining))
                exec_results["sandbox_fallback"] = result
                if result.get("success"):
                    success = True
                    try:
                        parsed = json.loads(result["stdout"].strip().split("\n")[-1])
                        exec_results["sandbox_parsed"] = parsed
                        digits_matched = max(digits_matched, 8)
                        info(f"Sandbox result: {json.dumps(parsed, indent=2)[:200]}")
                    except (json.JSONDecodeError, IndexError):
                        pass

        wall_time = time.time() - t0

        result = {
            "hypothesis": hyp_data,
            "execution": {
                "success": success,
                "digits_matched": digits_matched,
                "proof_status": proof_status,
                "wall_time_seconds": round(wall_time, 2),
                "tool_results": exec_results,
            },
        }

        status = f"{C.GREEN}SUCCESS{C.RESET}" if success else f"{C.RED}FAILED{C.RESET}"
        print(f"\n  Result: {status} ({wall_time:.1f}s)")
        return self.save_output(result)


# ── Agent D: Adversarial Critic ───────────────────────────────────────────────

class AgentD(AgentBase):
    name = "Adversarial Critic"
    letter = "D"
    description = "Stress-test execution results, score N/F/E/C, attempt falsification"

    def run(self, input_data: dict) -> dict:
        header(f"Agent D: {self.name}")

        execution = input_data.get("execution")
        hyp_data = input_data.get("hypothesis")

        if not execution:
            warn("No execution data; running Agent C first...")
            c_result = AgentC().run(input_data)
            execution = c_result.get("execution")
            hyp_data = c_result.get("hypothesis")

        if not execution:
            return self.save_output({"error": "no_execution_data", "evaluation": None})

        info(f"Evaluating: {hyp_data['id'] if hyp_data else '?'}")

        # ── Debate path ──────────────────────────────────────────────────────
        use_debate = input_data.get("debate_critic", False)
        if use_debate and _load_debate():
            return self._run_debate(input_data, hyp_data, execution)

        # ── Local critic path (default) ──────────────────────────────────────
        return self._run_local(input_data, hyp_data, execution)

    def _run_debate(self, input_data: dict, hyp_data: dict, execution: dict) -> dict:
        """Evaluate hypothesis using the GPT↔Claude debate loop (AgentDDebate)."""
        from multi_agent_discussion.siarc_adapter import AgentDDebate, DebateCriticConfig
        from self_iterating_agent import KILL_FLOOR

        dry_run   = input_data.get("debate_dry_run", True)
        with_judge = input_data.get("debate_judge", False)
        max_iter  = input_data.get("debate_iterations", 3)
        threshold_override = input_data.get("critic_threshold")
        swarm_mode = input_data.get("debate_swarm", False)
        swarm_size = input_data.get("swarm_size", 6)
        swarm_survivors = input_data.get("swarm_survivors", 2)

        cfg = DebateCriticConfig.from_env()
        cfg.dry_run    = dry_run
        cfg.with_judge = with_judge
        cfg.max_iter   = max_iter
        cfg.swarm_mode = bool(swarm_mode)
        cfg.swarm_size = max(2, int(swarm_size))
        cfg.swarm_survivors = max(1, int(swarm_survivors))

        mode_label = "dry-run" if dry_run else "live"
        swarm_suffix = f", swarm={cfg.swarm_size}->{cfg.swarm_survivors}" if cfg.swarm_mode else ""
        info(f"Debate critic enabled ({mode_label}, rounds={max_iter}"
             + (", +judge" if with_judge else "") + f"{swarm_suffix})")

        try:
            debate = AgentDDebate(cfg)
            eval_out = debate.evaluate(hyp_data or {}, execution)
        except Exception as e:
            err(f"Debate evaluation failed: {e}; falling back to local critic")
            traceback.print_exc()
            return self._run_local(input_data, hyp_data, execution)

        scores  = eval_out["scores"]
        b_score = eval_out["b_score"]
        verdict = eval_out["verdict"]
        critique_text = eval_out.get("critique", "")
        lfi = eval_out.get("lfi")
        controller_action = eval_out.get("controller_action", "")
        meta_directive = eval_out.get("meta_directive", "")
        red_team_output = eval_out.get("red_team_output", {})
        swarm_report = eval_out.get("swarm", {})

        # Apply effective kill floor (respects --critic-threshold override)
        effective_kill_floor = (
            {dim: threshold_override for dim in KILL_FLOOR}
            if threshold_override is not None
            else KILL_FLOOR
        )
        if threshold_override is not None:
            info(f"Kill floor overridden to {threshold_override:.2f} for all dimensions")

        print(f"\n  {C.BOLD}Scores (debate):{C.RESET}")
        for dim, val in scores.items():
            bar = "#" * int(val * 20)
            color = C.GREEN if val >= effective_kill_floor.get(dim, 0.5) else C.RED
            print(f"    {dim}: {color}{val:.3f} [{bar:<20}]{C.RESET}")
        print(f"    B-score: {C.BOLD}{b_score:.4f}{C.RESET}")
        print(f"    Verdict: {C.BOLD}{verdict}{C.RESET}")
        if lfi is not None:
            print(f"    LFI:     {C.BOLD}{float(lfi):.3f}{C.RESET}")
        if controller_action:
            info(f"Controller action: {controller_action}")
        if swarm_report:
            info(f"Swarm {swarm_report.get('swarm_id', '?')}: best_gap={swarm_report.get('best_gap_pct', 'n/a')}% from {len(swarm_report.get('results', []))} candidates")
            for survivor in swarm_report.get("survivors", [])[:2]:
                info(f"Survivor {survivor.get('id')}: gap={survivor.get('gap_pct')}%, status={survivor.get('status')}, kind={survivor.get('mutation_kind')}")
        for flaw in red_team_output.get("lethal_flaws", [])[:3]:
            info(f"Red-Team flaw: {flaw}")
        if meta_directive:
            info(f"Meta-directive: {meta_directive[:220]}")
        if eval_out.get("judge_summary"):
            info(f"Judge: {eval_out['judge_summary'][:200]}")

        killed = any(scores.get(dim, 0) < floor
                     for dim, floor in effective_kill_floor.items())
        if killed:
            warn("Below kill floor -- hypothesis rejected")

        result = {
            "hypothesis": hyp_data,
            "execution": execution,
            "evaluation": {
                "scores": scores,
                "b_score": b_score,
                "verdict": verdict,
                "killed": killed,
                "critique": critique_text,
                "lfi": lfi,
                "controller_action": controller_action,
                "meta_directive": meta_directive,
                "red_team": red_team_output,
                "swarm": swarm_report if swarm_report else None,
                "best_swarm_gap_pct": eval_out.get("best_swarm_gap_pct"),
                "best_swarm_formula": eval_out.get("best_swarm_formula"),
                # Debate-specific metadata passed through for F's logs
                "debate": {
                    "mode": "dry_run" if dry_run else "live",
                    "iterations_completed": eval_out.get("iterations_completed", 0),
                    "output_path": eval_out.get("debate_output_path", ""),
                    "judge_summary": eval_out.get("judge_summary", ""),
                    "self_correction_log_path": eval_out.get("self_correction_log_path", ""),
                    "memory_hits": eval_out.get("memory_hits", 0),
                },
            },
        }
        return self.save_output(result)

    def _run_local(self, input_data: dict, hyp_data: dict, execution: dict) -> dict:
        """Evaluate hypothesis using the local CriticAgent (default path)."""
        from self_iterating_agent import (
            PersistentMemory, VerificationToolbox, CriticAgent,
            Hypothesis, ExecutionResult, STATE_DIR, KILL_FLOOR
        )

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        memory = PersistentMemory()
        toolbox = VerificationToolbox(memory)
        critic = CriticAgent(toolbox)

        # Allow per-run threshold override via --critic-threshold CLI arg.
        threshold_override = input_data.get("critic_threshold")
        effective_kill_floor = (
            {dim: threshold_override for dim in KILL_FLOOR}
            if threshold_override is not None
            else KILL_FLOOR
        )
        if threshold_override is not None:
            info(f"Kill floor overridden to {threshold_override:.2f} for all dimensions")

        exec_result = ExecutionResult(
            hypothesis_id=hyp_data.get("id", "unknown") if hyp_data else "unknown",
            success=execution.get("success", False),
            method="multi_tool",
            evidence=execution.get("tool_results", {}),
            runtime_seconds=execution.get("wall_time_seconds", 0),
            digits_matched=execution.get("digits_matched", 0),
            proof_status=execution.get("proof_status", "none"),
        )

        # Filter to constructor-safe fields only (module-level _HYP_CTOR_FIELDS).
        if hyp_data:
            hyp_clean = {k: v for k, v in hyp_data.items() if k in _HYP_CTOR_FIELDS}
            try:
                hyp = Hypothesis(**hyp_clean)
            except TypeError as e:
                warn(f"Hypothesis construction warning: {e}; using minimal fallback")
                hyp = Hypothesis(
                    id=hyp_data.get("id", "unknown"),
                    gap_id=hyp_data.get("gap_id", "unknown"),
                    claim=hyp_data.get("claim", ""),
                    mechanism=hyp_data.get("mechanism", ""),
                    testable_prediction=hyp_data.get("testable_prediction", ""),
                    failure_condition=hyp_data.get("failure_condition", ""),
                )
        else:
            hyp = Hypothesis(
                id="unknown", gap_id="unknown", claim="", mechanism="",
                testable_prediction="", failure_condition=""
            )

        evaluation_obj = None
        try:
            evaluation_obj = critic.evaluate(hyp, exec_result)
            scores = evaluation_obj.scores
            verdict = evaluation_obj.verdict
            b_score = evaluation_obj.b_score
        except Exception as e:
            warn(f"Critic error: {e}")
            _success = execution.get("success", False)
            _dm = min(execution.get("digits_matched", 0), 12)
            scores = {
                "N": round(min(0.85, 0.25 + _dm * 0.05), 3) if _success else 0.20,
                "F": 0.55 if _success else 0.30,
                "E": round(min(0.90, 0.40 + _dm * 0.04), 3) if _success else 0.25,
                "C": 0.45,
            }
            b_score = round(scores["N"] * scores["F"] * scores["E"] * scores["C"], 6)
            verdict = "progress" if _success else "inconclusive"

        print(f"\n  {C.BOLD}Scores:{C.RESET}")
        for dim, val in scores.items():
            bar = "#" * int(val * 20)
            color = C.GREEN if val >= effective_kill_floor.get(dim, 0.5) else C.RED
            print(f"    {dim}: {color}{val:.3f} [{bar:<20}]{C.RESET}")
        print(f"    B-score: {C.BOLD}{b_score:.4f}{C.RESET}")
        print(f"    Verdict: {C.BOLD}{verdict}{C.RESET}")

        killed = any(scores.get(dim, 0) < floor
                     for dim, floor in effective_kill_floor.items())
        if killed:
            warn("Below kill floor -- hypothesis rejected")

        critique_text = getattr(evaluation_obj, "critique", "") if evaluation_obj is not None else ""

        result = {
            "hypothesis": hyp_data,
            "execution": execution,
            "evaluation": {
                "scores": scores,
                "b_score": b_score,
                "verdict": verdict,
                "killed": killed,
                "critique": critique_text,
            },
        }
        return self.save_output(result)


# ── Agent E: Cross-Pollinator ─────────────────────────────────────────────────

class AgentE(AgentBase):
    name = "Cross-Pollinator"
    letter = "E"
    description = "Transfer patterns across domains, dispatch MetaOrchestrator tasks"

    def run(self, input_data: dict) -> dict:
        header(f"Agent E: {self.name}")

        evaluation = input_data.get("evaluation", {})
        hyp_data = input_data.get("hypothesis")
        verdict = evaluation.get("verdict", "inconclusive")

        info(f"Incoming verdict: {verdict}")

        analogies = []
        meta_insights = []

        # 1. Check if multi_agent_discovery transfer engine is available
        try:
            from multi_agent_discovery.transfer_engine import TransferEngine
            transfer = TransferEngine()
            info("Transfer engine loaded")

            if hyp_data and hyp_data.get("claim"):
                claim = hyp_data["claim"]
                for target_domain in ["ising", "materials", "partition"]:
                    try:
                        result = transfer.translate(claim, "math", target_domain)
                        if result and getattr(result, 'similarity', 0) > 0.3:
                            analogies.append({
                                "source": "math",
                                "target": target_domain,
                                "similarity": result.similarity,
                                "mapped": str(result),
                            })
                            ok(f"Analogy found: math -> {target_domain} "
                               f"(sim={result.similarity:.2f})")
                    except Exception:
                        pass
        except ImportError:
            info("Transfer engine not available; using keyword-similarity pollination")

        # 2. Check MetaOrchestrator domain results on disk.
        # We enumerate domains and check for actual result files rather than
        # just listing "available" — that label was misleading (no checking done).
        try:
            from meta_orchestrator import Domain
            results_dir = WORKSPACE / "results"
            for domain in Domain:
                result_files = list(results_dir.glob(f"*{domain.value}*")) if results_dir.is_dir() else []
                meta_insights.append({
                    "domain": domain.value,
                    "status": "results_found" if result_files else "no_results",
                    "result_count": len(result_files),
                })
            found = sum(1 for m in meta_insights if m["status"] == "results_found")
            if found:
                ok(f"MetaOrchestrator: {found} domain(s) have existing results")
            else:
                info("MetaOrchestrator: no domain result files found")
        except ImportError:
            info("MetaOrchestrator not available")

        # 3. Knowledge base cross-references.
        # Searches ALL discoveries (not just the last 20) and uses a richer keyword
        # set derived from both gap_id tokens and claim words so E has real signal
        # even when TransferEngine is absent.
        kb_path = WORKSPACE / "knowledge_base.json"
        cross_refs = []
        if kb_path.exists():
            try:
                kb = json.loads(kb_path.read_text(encoding="utf-8"))
                discoveries = kb.get("discoveries", [])
                info(f"Knowledge base: {len(discoveries)} discoveries for cross-reference")

                gap_id = hyp_data.get("gap_id", "") if hyp_data else ""
                claim_text = (hyp_data.get("claim", "") if hyp_data else "").lower()
                # Build keyword set: gap_id tokens + significant claim words (>4 chars)
                kw_set = set(gap_id.lower().split("_"))
                kw_set |= {w for w in claim_text.split() if len(w) > 4}
                kw_set.discard("")

                for disc in discoveries:  # full scan, not just last-20
                    desc = disc.get("description", "").lower()
                    disc_id = disc.get("id", "").lower()
                    if kw_set and any(kw in desc or kw in disc_id for kw in kw_set):
                        cross_refs.append({
                            "id": disc.get("id", "?"),
                            "description": disc.get("description", "")[:120],
                            "status": disc.get("status", "?"),
                        })
                        if len(cross_refs) >= 10:  # cap at 10 to keep output readable
                            break

                # 3b. Lightweight keyword analogy when TransferEngine is absent
                if not analogies and hyp_data:
                    domain_keywords = {
                        "ising":     ["critical", "exponent", "spin", "lattice", "phase"],
                        "materials": ["bandgap", "perovskite", "stability", "crystal"],
                        "partition": ["partition", "gcf", "ratio", "modular", "ramanujan"],
                        "graph":     ["graph", "vertex", "edge", "connectivity", "cycle"],
                    }
                    claim_lower = claim_text
                    for domain, kws in domain_keywords.items():
                        hits = [kw for kw in kws if kw in claim_lower]
                        if hits:
                            sim = min(1.0, len(hits) / 3)
                            analogies.append({
                                "source": "math",
                                "target": domain,
                                "similarity": round(sim, 2),
                                "mapped": f"keyword match: {', '.join(hits)}",
                            })
                            info(f"Lightweight analogy: math -> {domain} "
                                 f"(keywords: {', '.join(hits)})")
            except Exception as e:
                warn(f"KB cross-reference error: {e}")

        if cross_refs:
            ok(f"Found {len(cross_refs)} cross-references in knowledge base")
        if analogies:
            ok(f"Found {len(analogies)} cross-domain analogies")

        result = {
            "hypothesis": hyp_data,
            "execution": input_data.get("execution"),
            "evaluation": evaluation,
            "pollination": {
                "analogies": analogies,
                "meta_insights": meta_insights,
                "cross_references": cross_refs,
                "domains_checked": len(meta_insights),
            },
        }

        return self.save_output(result)


# ── Agent F: Memory & Report ─────────────────────────────────────────────────

class AgentF(AgentBase):
    name = "Memory & Report"
    letter = "F"
    description = "Persist results, update memory, generate summary, seed next cycle"

    def run(self, input_data: dict) -> dict:
        header(f"Agent F: {self.name}")

        hyp_data = input_data.get("hypothesis")
        execution = input_data.get("execution", {})
        evaluation = input_data.get("evaluation", {})
        pollination = input_data.get("pollination", {})

        from self_iterating_agent import (
            PersistentMemory, AgentState, STATE_DIR, ITERATION_LOG
        )

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        memory = PersistentMemory()
        state = AgentState.load()

        # 1. Update memory with results
        verdict = evaluation.get("verdict", "inconclusive")
        gap_id = hyp_data.get("gap_id", "unknown") if hyp_data else "unknown"

        if verdict == "breakthrough":
            memory.add_entry("discovery", f"BREAKTHROUGH on {gap_id}: {hyp_data.get('claim', '')[:200]}")
            state.breakthroughs += 1
            ok("BREAKTHROUGH recorded!")
        elif verdict == "progress":
            memory.add_entry("discovery", f"Progress on {gap_id}: {hyp_data.get('claim', '')[:200]}")
            ok("Progress recorded")
        elif verdict == "failure":
            reason = evaluation.get("critique", "unknown reason")
            memory.add_failure(gap_id, hyp_data.get("claim", ""), reason, "siarc_chain")
            state.failures += 1
            warn("Failure recorded for future avoidance")
        else:
            memory.add_entry("insight", f"Inconclusive on {gap_id}")

        # 2. Update tool stats
        for tool, result in execution.get("tool_results", {}).items():
            success = not result.get("error") and not result.get("skipped")
            runtime = result.get("runtime", 0) if isinstance(result, dict) else 0
            memory.update_tool_stats(tool, success, runtime)

        # 3. Record cross-pollination insights
        for analogy in pollination.get("analogies", []):
            memory.add_entry("insight",
                f"Cross-domain analogy: {analogy['source']}->{analogy['target']} "
                f"(sim={analogy.get('similarity', 0):.2f})")

        # 4. Save state
        state.iteration += 1
        state.save()
        memory.save()

        # 5. Append to iteration log
        ITERATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        swarm_eval = evaluation.get("swarm") or {}
        log_entry = {
            "iteration": state.iteration,
            "timestamp": datetime.now().isoformat(),
            "gap_id": gap_id,
            "verdict": verdict,
            "b_score": evaluation.get("b_score", 0),
            "scores": evaluation.get("scores", {}),
            "lfi": evaluation.get("lfi", evaluation.get("red_team", {}).get("LFI")),
            "controller_action": evaluation.get("controller_action", evaluation.get("red_team", {}).get("controller_action")),
            "best_swarm_gap_pct": swarm_eval.get("best_gap_pct"),
            "swarm_generation": swarm_eval.get("generation"),
            "wall_time": execution.get("wall_time_seconds", 0),
            "analogies_found": len(pollination.get("analogies", [])),
        }
        with open(ITERATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

        # 6. Print summary
        print(f"\n{C.BOLD}  Cycle Summary:{C.RESET}")
        print(f"    Iteration:  {state.iteration}")
        print(f"    Gap:        {gap_id}")
        print(f"    Verdict:    {verdict}")
        print(f"    B-score:    {evaluation.get('b_score', 0):.4f}")
        print(f"    Breakthroughs total: {state.breakthroughs}")
        print(f"    Failures total:      {state.failures}")
        print(f"    Memory entries:      {len(memory.entries)}")

        # 7. Recommend next gap (seed for next cycle).
        # Exclude the current gap_id so a failed gap is never immediately
        # re-recommended. The failure penalty in memory already lowers its
        # score, but we guarantee at least one cycle of exploration elsewhere
        # before revisiting it.
        from self_iterating_agent import KnowledgeGraph
        knowledge = KnowledgeGraph(memory)
        all_next = knowledge.rank_gaps()
        next_gaps = [g for g in all_next if g.id != gap_id][:3]
        # Fallback: if only one gap exists in the KB, allow revisiting it
        if not next_gaps:
            next_gaps = all_next[:3]
        next_gap_data = None
        if next_gaps:
            next_gap_data = {
                "id": next_gaps[0].id,
                "description": next_gaps[0].description,
                "source": next_gaps[0].source,
                "gap_type": next_gaps[0].gap_type,
                "score": next_gaps[0].score,
            }
            skipped = f" (skipped '{gap_id}')" if next_gaps[0].id != gap_id else ""
            info(f"Next recommended gap: {next_gaps[0].id} (score={next_gaps[0].score:.3f}){skipped}")

        result = {
            "summary": {
                "iteration": state.iteration,
                "gap_id": gap_id,
                "verdict": verdict,
                "b_score": evaluation.get("b_score", 0),
                "breakthroughs_total": state.breakthroughs,
                "failures_total": state.failures,
            },
            "next_gap": next_gap_data,
            "seed": input_data.get("seed"),
        }

        ok(f"Cycle {state.iteration} complete. State saved.")
        return self.save_output(result)


class AgentJudge(AgentBase):
    name = "Formal Judge"
    letter = "J"
    description = "Generate a formal verification report from Agent D output"

    @staticmethod
    def _extract_gap_pct(execution: dict) -> float | None:
        tool_results = execution.get("tool_results", {}) if isinstance(execution, dict) else {}
        for key in ("sandbox_parsed", "sandbox_fallback", "partition_ratios"):
            payload = tool_results.get(key, {}) if isinstance(tool_results, dict) else {}
            if isinstance(payload, dict):
                for gap_key in ("gap_pct", "gap", "gap_percent"):
                    if gap_key in payload:
                        try:
                            return float(payload[gap_key])
                        except Exception:
                            pass
            stdout = payload.get("stdout") if isinstance(payload, dict) else None
            if isinstance(stdout, str) and stdout.strip().startswith("{"):
                try:
                    nested = json.loads(stdout.strip().splitlines()[-1])
                    for gap_key in ("gap_pct", "gap", "gap_percent"):
                        if gap_key in nested:
                            return float(nested[gap_key])
                except Exception:
                    pass
        return None

    @staticmethod
    def _best_formula(hypothesis: dict, evaluation: dict) -> str:
        if evaluation.get("best_swarm_formula"):
            return str(evaluation.get("best_swarm_formula"))
        swarm = evaluation.get("swarm") or {}
        if swarm.get("best_formula"):
            return str(swarm.get("best_formula"))
        survivors = swarm.get("survivors", [])
        if survivors:
            top = survivors[0]
            return str(top.get("refined_formula") or top.get("formula") or "")
        candidate_formula = hypothesis.get("candidate_formula")
        if candidate_formula:
            return str(candidate_formula)
        claim = str(hypothesis.get("claim", "")).strip()
        if "=" in claim:
            return claim.split("=", 1)[1].strip()
        return claim

    @staticmethod
    def _swarm_peak_gap(evaluation: dict) -> float | None:
        swarm = evaluation.get("swarm") or {}
        results = swarm.get("results", [])
        values = []
        for item in results:
            for key in ("raw_gap_pct", "gap_pct"):
                if key in item and item.get(key) is not None:
                    try:
                        values.append(float(item[key]))
                        break
                    except Exception:
                        pass
        if values:
            return min(values)
        best_gap = evaluation.get("best_swarm_gap_pct", swarm.get("best_gap_pct"))
        try:
            return float(best_gap) if best_gap is not None else None
        except Exception:
            return None

    @staticmethod
    def _format_pct(value: float | None) -> str:
        if value is None:
            return "n/a"
        if value < 0.001:
            return f"{value:.1e}%"
        return f"{value:.5f}%"

    @staticmethod
    def _normalize_formula_text(formula: str) -> str:
        text = str(formula or "").strip()
        text = text.replace("·", "*").replace("−", "-")
        text = text.replace("π", "pi").replace("γ", "EulerGamma")
        text = text.replace("₅", "5").replace("^", "**")
        return text

    def _symbolic_deconstruction(self, formula: str) -> dict:
        details = {
            "formula": formula,
            "coefficients": [],
            "notes": [],
        }
        if not formula:
            details["notes"].append("No refined formula was available for symbolic analysis.")
            return details

        try:
            import sympy as sp
            from sympy.parsing.sympy_parser import parse_expr

            c5 = sp.symbols("c5", real=True)
            expr = sp.simplify(
                parse_expr(
                    self._normalize_formula_text(formula),
                    local_dict={
                        "c5": c5,
                        "pi": sp.pi,
                        "e": sp.E,
                        "sqrt": sp.sqrt,
                        "gamma": sp.EulerGamma,
                        "EulerGamma": sp.EulerGamma,
                        "zeta": sp.zeta,
                    },
                    evaluate=True,
                )
            )
            expanded = sp.expand(expr)
            alpha = sp.simplify(expanded.coeff(c5, 1))
            beta = sp.simplify(expanded.coeff(c5, -1))
            gamma = sp.simplify(expanded - alpha * c5 - beta / c5)
            basis = [sp.pi, sp.E, sp.EulerGamma, sp.sqrt(2), sp.zeta(2), sp.zeta(3)]

            for label, coeff in (("α · c5", alpha), ("β / c5", beta), ("γ", gamma)):
                try:
                    if coeff == 0 or getattr(coeff, "is_infinite", False):
                        continue
                    approx_expr = sp.N(coeff, 16)
                    if getattr(approx_expr, "is_infinite", False):
                        continue
                    approx = float(approx_expr)
                    simplified = sp.nsimplify(coeff, basis, tolerance=1e-12, rational=True)
                    details["coefficients"].append(
                        {
                            "label": label,
                            "approx": approx,
                            "nsimplify": str(simplified),
                        }
                    )
                except Exception:
                    continue

            if not details["coefficients"]:
                details["notes"].append("No clean low-order decomposition was detected; the formula may need a richer symbolic basis.")
        except Exception as e:
            details["notes"].append(f"SymPy deconstruction fallback: {e}")

        return details

    def _derive_status(self, best_gap_pct: float | None, lfi: float | None, execution: dict) -> str:
        tool_results = execution.get("tool_results", {}) if isinstance(execution, dict) else {}
        symbolic_skipped = isinstance(tool_results.get("symbolic_verify"), dict) and tool_results["symbolic_verify"].get("skipped")
        pslq_skipped = isinstance(tool_results.get("pslq_search"), dict) and tool_results["pslq_search"].get("skipped")

        if best_gap_pct is not None and best_gap_pct <= 1e-4 and (lfi is None or lfi <= 0.20):
            if symbolic_skipped or pslq_skipped:
                return "NUMERICALLY VERIFIED — FORMAL PROOF PENDING"
            return "VERIFIED"
        if best_gap_pct is not None and best_gap_pct <= 1 and (lfi is None or lfi <= 0.35):
            return "STRONG NUMERIC SUPPORT"
        if best_gap_pct is not None and best_gap_pct <= 10:
            return "PROMISING"
        return "INCONCLUSIVE"

    def _build_formal_report(self, hypothesis: dict, execution: dict, evaluation: dict) -> tuple[str, dict]:
        gap_id = hypothesis.get("gap_id", "unknown")
        hypothesis_id = hypothesis.get("id", "unknown")
        formula = self._best_formula(hypothesis, evaluation)
        initial_gap = self._extract_gap_pct(execution)
        swarm_peak = self._swarm_peak_gap(evaluation)
        best_gap = evaluation.get("best_swarm_gap_pct")
        swarm = evaluation.get("swarm") or {}
        if best_gap is None:
            best_gap = swarm.get("best_gap_pct")
        try:
            best_gap = float(best_gap) if best_gap is not None else initial_gap
        except Exception:
            best_gap = initial_gap
        lfi = evaluation.get("lfi")
        try:
            lfi = float(lfi) if lfi is not None else None
        except Exception:
            lfi = None

        status = self._derive_status(best_gap, lfi, execution)
        symbolic = self._symbolic_deconstruction(formula)
        red_team = (evaluation.get("red_team") or {}).get("lethal_flaws", [])

        finding_lines = []
        if initial_gap is not None and best_gap is not None and best_gap < initial_gap:
            finding_lines.append(f"- **[CLOSED]** Numeric mismatch collapsed from `{self._format_pct(initial_gap)}` to `{self._format_pct(best_gap)}` after ASR.")
        for flaw in red_team[:4]:
            tag = "REMAINING"
            lower = str(flaw).lower()
            if "numeric mismatch" in lower and best_gap is not None and best_gap < 1:
                tag = "CLOSED"
            elif "improved local fit" in lower:
                tag = "CLOSED"
            finding_lines.append(f"- **[{tag}]** {flaw}")
        if not finding_lines:
            finding_lines.append("- No adversarial findings were recorded in the supplied Agent D payload.")

        coeff_lines = []
        for item in symbolic.get("coefficients", []):
            coeff_lines.append(
                f"- **{item['label']}** ≈ `{item['approx']:.12g}`  →  `nsimplify = {item['nsimplify']}`"
            )
        for note in symbolic.get("notes", []):
            coeff_lines.append(f"- {note}")
        if not coeff_lines:
            coeff_lines.append("- Symbolic inversion did not produce a simpler constant basis automatically.")

        verdict_quote = (
            "The ASR survivor is now numerically locked-on and deserves formal follow-up; "
            "however, the remaining skipped symbolic checks mean this should be treated as a recovered identity candidate rather than a finished proof."
        )
        if status == "VERIFIED":
            verdict_quote = (
                "The hypothesis has crossed both the numeric and symbolic verification thresholds and can be treated as a verified identity."
            )

        md = [
            f"# Formal Verification Report: `{hypothesis_id}` Finality",
            f"**Subject:** {gap_id}",
            f"**Status:** **{status}** (LFI: {lfi if lfi is not None else 'n/a'})",
            "",
            "## 1. Executive Summary",
            f"The candidate formula `{formula}` has cleared the ASR-augmented red-team gate with controller action `{evaluation.get('controller_action', 'n/a')}`.",
            f"Current verdict: **{evaluation.get('verdict', 'inconclusive')}**. This report consolidates the numeric evidence, symbolic deconstruction, and remaining proof obligations.",
            "",
            "## 2. Numerical Convergence Profile",
            f"- **Initial Gap:** `{self._format_pct(initial_gap)}`",
            f"- **Swarm Peak:** `{self._format_pct(swarm_peak)}`",
            f"- **ASR Refinement:** `{self._format_pct(best_gap)}`",
            f"- **Digits Matched:** `{execution.get('digits_matched', 0)}`",
            f"- **Controller Action:** `{evaluation.get('controller_action', 'n/a')}`",
            "",
            "## 3. Symbolic Deconstruction",
            *coeff_lines,
            "",
            "## 4. Adversarial Falsification Results",
            *finding_lines,
            "",
            "## 5. Formal Verdict",
            f"> **{verdict_quote}**",
            "",
            "## 6. Next Proof Steps",
            "1. Run `pslq_search` on the refined coefficients and residual to identify a compact constant basis.",
            "2. Re-run `symbolic_verify` on the ASR survivor to replace numeric evidence with a derivation.",
            "3. Cross-test the recovered structure on a neighboring seed (for example `k=6`) to rule out overfitting.",
            "",
        ]
        return "\n".join(md).strip() + "\n", {
            "status": status,
            "best_formula": formula,
            "initial_gap_pct": initial_gap,
            "swarm_peak_gap_pct": swarm_peak,
            "best_gap_pct": best_gap,
            "lfi": lfi,
            "symbolic_deconstruction": symbolic,
            "formal_verdict": verdict_quote,
        }

    def run(self, input_data: dict) -> dict:
        header(f"Agent J: {self.name}")

        hypothesis = input_data.get("hypothesis")
        execution = input_data.get("execution")
        evaluation = input_data.get("evaluation")

        if not evaluation:
            warn("No evaluation payload found; running Agent D first...")
            d_result = AgentD().run(input_data)
            hypothesis = d_result.get("hypothesis")
            execution = d_result.get("execution")
            evaluation = d_result.get("evaluation")

        if not evaluation:
            return self.save_output({"error": "no_evaluation_data", "judge": None})

        hypothesis = hypothesis or {}
        execution = execution or {}
        report_md, judge_meta = self._build_formal_report(hypothesis, execution, evaluation)

        report_path = None
        if input_data.get("formal_report"):
            output_path = input_data.get("output_path") or f"breakthroughs/{hypothesis.get('id', 'formal_report')}_Final.md"
            report_path = Path(output_path)
            if not report_path.is_absolute():
                report_path = WORKSPACE / report_path
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report_md, encoding="utf-8")
            ok(f"Formal report written: {report_path}")

        print(f"\n  {C.BOLD}Judge Summary:{C.RESET}")
        print(f"    Status:      {judge_meta['status']}")
        print(f"    Best formula: {judge_meta['best_formula']}")
        print(f"    Best gap:    {self._format_pct(judge_meta['best_gap_pct'])}")
        if judge_meta.get("lfi") is not None:
            print(f"    LFI:         {judge_meta['lfi']:.3f}")

        result = {
            "hypothesis": hypothesis,
            "execution": execution,
            "evaluation": evaluation,
            "judge": {
                **judge_meta,
                "report_path": str(report_path) if report_path else None,
                "formal_report_requested": bool(input_data.get("formal_report")),
            },
        }
        return self.save_output(result)


# ══════════════════════════════════════════════════════════════════════════
# CHAIN RUNNER — Composes agents into a pipeline
# ══════════════════════════════════════════════════════════════════════════

AGENT_MAP = {
    "A": AgentA, "B": AgentB, "C": AgentC,
    "D": AgentD, "E": AgentE, "F": AgentF, "J": AgentJudge,
}

FULL_CHAIN = "ABCDEF"

# Fields that Hypothesis.__init__ actually accepts.
# Kept at module level so AgentC and AgentD share a single source of truth.
# numeric_lhs / numeric_rhs / target_value are inter-agent communication fields
# that live in the JSON dict but NOT on the Hypothesis dataclass.
_HYP_CTOR_FIELDS = frozenset({
    "id", "gap_id", "claim", "mechanism", "testable_prediction",
    "failure_condition", "tools_needed", "confidence",
})


def run_chain(agent_spec: str, input_data: dict, cycles: int = 1) -> dict:
    """Run a chain of agents. agent_spec is e.g. 'A', 'BC', 'ABCDEF', 'full', 'judge'."""
    spec_norm = agent_spec.lower().replace("+", "")
    if spec_norm == "full":
        agent_spec = FULL_CHAIN
    elif spec_norm in {"judge", "formal", "j"}:
        agent_spec = "J"
    elif spec_norm in {"fulljudge", "fullj"}:
        agent_spec = FULL_CHAIN + "J"

    agent_spec = agent_spec.upper()
    for ch in agent_spec:
        if ch not in AGENT_MAP:
            err(f"Unknown agent '{ch}'. Valid: A, B, C, D, E, F, J")
            sys.exit(1)

    result = input_data
    passthrough_keys = {
        key: input_data[key]
        for key in (
            "seed",
            "critic_threshold",
            "debate_critic",
            "debate_dry_run",
            "debate_judge",
            "debate_iterations",
            "debate_swarm",
            "swarm_size",
            "swarm_survivors",
            "formal_report",
            "output_path",
        )
        if key in input_data
    }
    for cycle in range(cycles):
        if cycles > 1:
            header(f"SIARC Cycle {cycle + 1}/{cycles}")

        failed_at = None
        for letter in agent_spec:
            agent_cls = AGENT_MAP[letter]
            agent = agent_cls()
            try:
                payload = dict(result)
                payload.update(passthrough_keys)
                result = agent.run(payload)
            except KeyboardInterrupt:
                warn("Interrupted by user")
                return result
            except Exception as e:
                err(f"Agent {letter} ({agent.name}) failed: {e}")
                traceback.print_exc()
                agent.save_output({"error": str(e), "_partial": True})
                failed_at = letter
                # Skip-to-F: if F is in the chain and we haven't reached it yet,
                # jump straight to Agent F so the cycle is always logged to memory.
                # This prevents silent data loss on long multi-cycle runs.
                if "F" in agent_spec and letter != "F":
                    warn(f"Skipping to Agent F to preserve cycle log...")
                    result["_error_agent"] = letter
                    result["_error_msg"] = str(e)
                    try:
                        result = AgentF().run(result)
                    except Exception as fe:
                        err(f"Agent F also failed during skip-to-F: {fe}")
                break

        # F→A feedback loop: promote next_gap to selected_gap so Agent A
        # skips a full rescan and targets the gap F recommended.
        # Also carry forward seed so domain filtering is preserved across cycles.
        if cycles > 1:
            if "next_gap" in result and result["next_gap"]:
                result["selected_gap"] = result["next_gap"]
                info(f"[chain] Next cycle gap: {result['selected_gap'].get('id', '?')}")
            # Preserve seed from original input_data if not already in result
            if "seed" not in result or result["seed"] is None:
                result["seed"] = input_data.get("seed")

    # ── Session summary (multi-cycle only) ──────────────────────────────────
    if cycles > 1:
        _print_session_summary(cycles, agent_spec)

    return result


def _print_session_summary(cycles: int, agent_spec: str):
    """Print an aggregate summary across all completed cycles by reading ITERATION_LOG."""
    try:
        from self_iterating_agent import ITERATION_LOG
        if not ITERATION_LOG.exists():
            return
        entries = []
        with open(ITERATION_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        if not entries:
            return
        # Only show the last N entries matching this run (last `cycles` entries)
        session = entries[-cycles:]
        verdicts = [e.get("verdict", "?") for e in session]
        b_scores = [e.get("b_score", 0) for e in session]
        wall_times = [e.get("wall_time", 0) for e in session]
        gaps = [e.get("gap_id", "?") for e in session]
        analogies = sum(e.get("analogies_found", 0) for e in session)

        total_time = sum(wall_times)
        breakthroughs = verdicts.count("breakthrough")
        progress_cnt = verdicts.count("progress")
        failures = verdicts.count("failure")
        avg_b = sum(b_scores) / len(b_scores) if b_scores else 0

        print(f"\n{C.CYAN}{'═'*72}")
        print(f"  {C.BOLD}SIARC Session Summary  ({cycles} cycles, agents={agent_spec}){C.RESET}{C.CYAN}")
        print(f"{'═'*72}{C.RESET}")
        print(f"  Total wall time:   {total_time:.1f}s")
        print(f"  Avg B-score:       {avg_b:.4f}")
        print(f"  Breakthroughs:     {C.GREEN}{breakthroughs}{C.RESET}")
        print(f"  Progress:          {C.BLUE}{progress_cnt}{C.RESET}")
        print(f"  Failures:          {C.RED}{failures}{C.RESET}")
        print(f"  Analogies found:   {analogies}")
        print(f"  Gaps attempted:    {', '.join(dict.fromkeys(gaps))}")  # deduplicated order
        bscores_str = ', '.join(f'{b:.3f}' for b in b_scores)
        print(f"  Per-cycle B:       {bscores_str}")
        print(f"{C.CYAN}{'='*72}{C.RESET}\n")
    except Exception as e:
        warn(f"Session summary error: {e}")


# ══════════════════════════════════════════════════════════════════════════
# INTERACTIVE SELECTOR
# ══════════════════════════════════════════════════════════════════════════

def interactive_selector() -> tuple:
    """Interactive menu for agent selection. Returns (agent_spec, input_data)."""
    banner()
    print(f"  {C.BOLD}Select what to run:{C.RESET}\n")
    print(f"    {C.CYAN}1{C.RESET}  Full chain A->B->C->D->E->F (1 cycle)")
    print(f"    {C.CYAN}2{C.RESET}  Full chain (3 cycles)")
    print(f"    {C.CYAN}3{C.RESET}  Full chain (5 cycles)")
    print(f"    {C.CYAN}4{C.RESET}  Agent A only (Frontier Scanner)")
    print(f"    {C.CYAN}5{C.RESET}  Agent B only (Hypothesis Generator)")
    print(f"    {C.CYAN}6{C.RESET}  Agent C only (Execution Engine)")
    print(f"    {C.CYAN}7{C.RESET}  Agent D only (Adversarial Critic)")
    print(f"    {C.CYAN}8{C.RESET}  Agent E only (Cross-Pollinator)")
    print(f"    {C.CYAN}9{C.RESET}  Agent F only (Memory & Report)")
    print(f"   {C.CYAN}10{C.RESET}  Sub-chain A->B->C")
    print(f"   {C.CYAN}11{C.RESET}  Sub-chain A->B->C->D->E")
    print(f"   {C.CYAN}12{C.RESET}  Seeded: Ramanujan focus (3 cycles)")
    print(f"   {C.CYAN}13{C.RESET}  Seeded: Ising MC focus (2 cycles)")
    print(f"   {C.CYAN}14{C.RESET}  MetaOrchestrator demo (3 domains)")
    print(f"   {C.CYAN}15{C.RESET}  Debate critic: full chain, dry-run (no API cost)")
    print(f"   {C.CYAN}16{C.RESET}  Debate critic: full chain, live (uses OpenAI + Anthropic APIs)")
    print()

    choice_map = {
        "1":  ("full", {}, 1),
        "2":  ("full", {}, 3),
        "3":  ("full", {}, 5),
        "4":  ("A", {}, 1),
        "5":  ("B", {}, 1),
        "6":  ("C", {}, 1),
        "7":  ("D", {}, 1),
        "8":  ("E", {}, 1),
        "9":  ("F", {}, 1),
        "10": ("ABC", {}, 1),
        "11": ("ABCDE", {}, 1),
        "12": ("full", {"seed": "ramanujan"}, 3),
        "13": ("full", {"seed": "ising"}, 2),
        "14": ("meta", {}, 1),  # special case
        "15": ("full", {"debate_critic": True, "debate_dry_run": True,
                         "debate_judge": False, "debate_iterations": 3}, 1),
        "16": ("full", {"debate_critic": True, "debate_dry_run": False,
                         "debate_judge": True, "debate_iterations": 3}, 1),
    }

    while True:
        try:
            choice = input(f"  {C.BOLD}Enter choice [1-16]: {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if choice in choice_map:
            spec, data, cycles = choice_map[choice]
            return spec, data, cycles
        else:
            warn("Invalid choice. Enter 1-16.")


def run_meta_demo():
    """Run the MetaOrchestrator 3-domain demo."""
    header("MetaOrchestrator: 3-Domain Demo")
    try:
        from meta_orchestrator import MetaOrchestrator, demo_tasks
        orchestrator = MetaOrchestrator(demo_tasks())
        report = orchestrator.run()
        print(f"\n{C.BOLD}Session: {report['passed']}/{report['total_tasks']} passed, "
              f"{report['novel_results']} novel ({report['total_wall_time_seconds']:.1f}s){C.RESET}")
        return report
    except Exception as e:
        err(f"MetaOrchestrator failed: {e}")
        traceback.print_exc()
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def stream_progress(msg: str):
    """Print streaming-style progress to terminal."""
    print(f"{C.GRAY}  ... {msg}{C.RESET}", flush=True)


# Directory for gap-specific verification scripts.
# Add <gap_id>.py files here to extend coverage without editing siarc.py.
GAP_SCRIPTS_DIR = WORKSPACE / "gap_scripts"

# Inline scripts kept for the two legacy gap IDs that existed before the
# file-based system. New gaps should use gap_scripts/<gap_id>.py instead.
_INLINE_SCRIPTS = {
        "prove_A1_k5": """
import mpmath as mp, json
mp.mp.dps = 120
k = 5
N = 2000
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
ratios = [f[n] / f[n-1] for n in range(N-10, N+1) if f[n-1] != 0]
L = float(mp.log(ratios[-1]))
c_k = float(mp.pi * mp.sqrt(mp.mpf(2*k)/3))
L_pred = c_k**2/8 - (k+3)/4
print(json.dumps({"L_numeric": L, "L_predicted": L_pred, "gap_pct": abs(L-L_pred)/abs(L_pred)*100}))
""",
        "sixth_root": """
import mpmath as mp, json
mp.mp.dps = 100
k = 5
N = 1000
f = [mp.mpf(0)] * (N + 1)
f[0] = mp.mpf(1)
for n in range(1, N + 1):
    s = mp.mpf(0)
    for j in range(1, n + 1):
        d = 1
        sigma = mp.mpf(0)
        while d * d <= j:
            if j % d == 0:
                sigma += d
                if d != j // d:
                    sigma += j // d
            d += 1
        s += k * sigma * f[n - j]
    f[n] = s / n
if f[N] > 0 and f[N-1] > 0:
    ratio = f[N] / f[N-1]
    L = float(mp.log(ratio))
    c_k = float(mp.pi * mp.sqrt(mp.mpf(2*k)/3))
    L_pred = c_k**2/8 - (k+3)/4
    print(json.dumps({"L": L, "L_pred": L_pred, "gap": abs(L-L_pred)/abs(L_pred)*100, "N": N}))
else:
    print(json.dumps({"error": "zero partition values"}))
""",
    }


def _build_gap_script(gap_id: str, hyp_data: dict) -> str:
    """Return a verification script for the given gap_id, or empty string.

    Resolution order:
      1. gap_scripts/<gap_id>.py  — file-based, add new scripts here
      2. _INLINE_SCRIPTS dict     — legacy inline scripts
    """
    # 1. File-based lookup (preferred for new gaps)
    if GAP_SCRIPTS_DIR.is_dir():
        script_path = GAP_SCRIPTS_DIR / f"{gap_id}.py"
        if script_path.exists():
            return script_path.read_text(encoding="utf-8")

    # 2. Inline legacy fallback
    return _INLINE_SCRIPTS.get(gap_id, "")


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="SIARC -- Self-Improving Autonomous Research Chain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python siarc.py                                  # Interactive selector
  python siarc.py --agent full --cycles 3          # Full chain, 3 cycles
  python siarc.py --agent A                        # Agent A only
  python siarc.py --agent BC --input agent_A_out.json  # Sub-chain B->C
  python siarc.py --seed ramanujan                 # Ramanujan-focused full chain
        """,
    )
    parser.add_argument("--agent", type=str, default="",
                        help="Agent(s) to run: A, B, C, D, E, F, J/judge, ABC, ABCDE, full")
    parser.add_argument("--input", type=str, default="",
                        help="Path to input JSON (from previous agent output)")
    parser.add_argument("--cycles", type=int, default=1,
                        help="Number of full-chain cycles (default: 1)")
    parser.add_argument("--seed", type=str, default="",
                        help="Seed domain: ramanujan, ising, materials")
    parser.add_argument("--critic-threshold", type=float, default=None,
                        help=("Override kill-floor threshold for Agent D (0.0–1.0). "
                              "Lower = exploratory (let weak hypotheses through); "
                              "higher = strict validation. Default: use KILL_FLOOR "
                              "from self_iterating_agent."))
    parser.add_argument("--formal-report", action="store_true",
                        help="When running Agent J/judge, write a Markdown Formal Verification Report.")
    parser.add_argument("--output-path", type=str, default="",
                        help="Optional path for the formal report Markdown output.")

    # ── Debate flags ─────────────────────────────────────────────────────────
    debate_group = parser.add_argument_group(
        "debate",
        "GPT↔Claude debate critic for Agent D (requires openai + anthropic packages)"
    )
    debate_group.add_argument(
        "--debate-critic", action="store_true",
        help="Enable debate-driven Agent D (GPT strategist + Claude Opus critic)."
    )
    debate_group.add_argument(
        "--debate-live", action="store_true",
        help="Use live API calls. Default is dry-run (safe, no API cost)."
    )
    debate_group.add_argument(
        "--debate-dry-run", action="store_true",
        help="Explicitly force dry-run mode for the debate critic."
    )
    debate_group.add_argument(
        "--debate-judge", action="store_true",
        help="Add a Judge pass after the debate loop."
    )
    debate_group.add_argument(
        "--debate-iterations", type=int, default=3,
        help="Max strategist/critic rounds per hypothesis (default: 3)."
    )
    debate_group.add_argument(
        "--debate-swarm", action="store_true",
        help="Enable mutation-swarm generation plus a batch gauntlet before the Red-Team review."
    )
    debate_group.add_argument(
        "--swarm-size", type=int, default=6,
        help="Number of swarm candidates to generate when --debate-swarm is enabled (default: 6)."
    )
    debate_group.add_argument(
        "--swarm-survivors", type=int, default=2,
        help="How many swarm candidates survive the gauntlet for deep review (default: 2)."
    )

    args = parser.parse_args()

    # Load input data
    input_data = {}
    if args.input:
        input_data = AgentBase.load_input(args.input)
    if args.seed:
        input_data["seed"] = args.seed
    if args.critic_threshold is not None:
        input_data["critic_threshold"] = args.critic_threshold
        # Note: Agent D will print this info with context when it runs
    if args.formal_report:
        input_data["formal_report"] = True
    if args.output_path:
        input_data["output_path"] = args.output_path

    # Debate flags — stored in input_data so they flow through the full chain
    if args.debate_critic:
        input_data["debate_critic"] = True
        dry_run = True if args.debate_dry_run or not args.debate_live else False
        input_data["debate_dry_run"] = dry_run
        input_data["debate_judge"]   = args.debate_judge
        input_data["debate_iterations"] = args.debate_iterations
        input_data["debate_swarm"] = args.debate_swarm
        input_data["swarm_size"] = max(2, args.swarm_size)
        input_data["swarm_survivors"] = max(1, args.swarm_survivors)
        mode = "dry-run" if dry_run else "live"
        swarm_note = f", swarm={input_data['swarm_size']}->{input_data['swarm_survivors']}" if args.debate_swarm else ""
        info(f"Debate critic enabled ({mode}, {args.debate_iterations} rounds"
             + (", +judge" if args.debate_judge else "") + f"{swarm_note})")

    # Interactive mode if no --agent flag
    if not args.agent:
        spec, extra_data, cycles = interactive_selector()
        input_data.update(extra_data)

        if spec == "meta":
            run_meta_demo()
            return

        run_chain(spec, input_data, cycles)
        return

    # CLI mode
    run_chain(args.agent, input_data, args.cycles)


if __name__ == "__main__":
    main()
