#!/usr/bin/env python3
"""
Unified Breakthrough Agent v1.0
================================
Combines breakthrough_engine_v8.py (12-layer evolutionary discovery)
with self_iterating_agent.py (5-phase research cycle + frontier mapping)

New in this prototype:
  ★ Semantic memory   — embedding-based retrieval (ChromaDB or cosine fallback)
  ★ Grounded critic   — SymPy/mpmath verification before LLM scoring
  ★ Dependency graph  — frontier unlocking on discovery success
  ★ Prompt genome     — versioned, heritable prompt DNA
  ★ Population search — 3 parallel hypotheses at T=[0.3, 0.8, 1.3]

Architecture (10-phase cycle):
  Phase 0: Serendipity injection (stagnation / schedule)
  Phase 1: Frontier identification  (knowledge graph + gap analysis)
  Phase 2: Population scoping      (3 hypotheses at varied temperatures)
  Phase 3: Grounded execution      (compute / symbolic / numeric)
  Phase 4: Adversarial evaluation  (isolated critic + tool grounding)
  Phase 5: Dependency propagation  (unlock downstream gaps)
  Phase 6: Synthesis / recombination
  Phase 7: Axiom graph update + genealogy
  Phase 8: Genome evolution        (mutate prompts on breakthrough)
  Phase 9: Summarize + persist

Usage:
  python unified_breakthrough_agent.py                  # 1 cycle
  python unified_breakthrough_agent.py --cycles 5       # N cycles
  python unified_breakthrough_agent.py --status         # show state
  python unified_breakthrough_agent.py --frontier       # frontier map
  python unified_breakthrough_agent.py --history        # iteration log
  python unified_breakthrough_agent.py --mutate         # genome proposals
  python unified_breakthrough_agent.py --rollback N     # revert to iter N
  python unified_breakthrough_agent.py --reset          # wipe state
  python unified_breakthrough_agent.py --show-graph     # axiom graph stats
  python unified_breakthrough_agent.py --archaeology    # resurrect old failures
"""

import abc
import argparse
import hashlib
import json
import math
import os
import re
import random
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ── Windows Unicode fix ────────────────────────────────────────────────────
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Optional heavy imports ─────────────────────────────────────────────────
try:
    import mpmath as mp
    HAS_MPMATH = True
except ImportError:
    HAS_MPMATH = False
    print("  pip install mpmath  (numeric verification disabled)")

try:
    import sympy
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Semantic memory backend — prefer ChromaDB, fall back to numpy cosine
HAS_CHROMA = False
HAS_STTRANSFORMERS = False
try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    pass

try:
    from sentence_transformers import SentenceTransformer
    HAS_STTRANSFORMERS = True
except ImportError:
    pass

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ══════════════════════════════════════════════════════════════════════════
# CONSTANTS & PATHS
# ══════════════════════════════════════════════════════════════════════════

VERSION        = "1.0.0"
WORKSPACE      = Path(__file__).parent
STATE_DIR      = WORKSPACE / "agent_state"
STATE_FILE     = STATE_DIR / "agent_state.json"
MEMORY_FILE    = STATE_DIR / "memory.json"
FAILURE_LOG    = STATE_DIR / "failures.jsonl"
ITERATION_LOG  = STATE_DIR / "iterations.jsonl"
MUTATION_LOG   = STATE_DIR / "mutations.jsonl"
TEMPLATES_DIR  = STATE_DIR / "templates"
GENOMES_DIR    = STATE_DIR / "genomes"
SNAPSHOTS_DIR  = STATE_DIR / "snapshots"
AXIOM_GRAPH_PATH    = WORKSPACE / "axiom_graph.json"
FAILURE_ARCHIVE_PATH = WORKSPACE / "failure_archive.json"
EVOLVED_PATTERNS_PATH = WORKSPACE / "evolved_patterns.json"
REALITY_SYNC_PATH = WORKSPACE / "reality_sync_scripts"
GENEALOGY_PATH = WORKSPACE / "genealogy.json"
KNOWLEDGE_BASE = WORKSPACE / "knowledge_base.json"
PATTERNS_PATH  = WORKSPACE / "structural_patterns.json"
REPORT_PATH    = WORKSPACE / "discovery_report.md"

MAX_CYCLES     = 50
MAX_COMPUTE_SECONDS = 600
HITL_REQUIRED_FOR = {"mutate_templates", "mutate_tools", "architecture_change"}

# Scoring
KILL_FLOOR = {"N": 0.50, "F": 0.55, "E": 0.35, "C": 0.40}
BT_THRESHOLDS = {"N": 0.70, "F": 0.80, "E": 0.65, "C": 0.60}
BREAKTHROUGH_THRESHOLD = 0.25   # N*F*E*C product

# Stagnation
STAGNATION_WINDOW = 3
DELTA_NOVELTY_THRESHOLD = 0.15

# Population search temperatures
TEMPERATURES = {"conservative": 0.3, "balanced": 0.8, "wild": 1.3}

DOMAIN_ROTATION = [
    "physics", "mathematics", "biology", "computer_science",
    "economics", "neuroscience", "chemistry", "engineering",
]


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

def ok(msg):    print(f"{C.GREEN}  ✓ {msg}{C.RESET}")
def warn(msg):  print(f"{C.YELLOW}  [!] {msg}{C.RESET}")
def err(msg):   print(f"{C.RED}  ✗ {msg}{C.RESET}")
def info(msg):  print(f"{C.GRAY}    {msg}{C.RESET}")
def star(msg):  print(f"{C.PURPLE}  ★ {msg}{C.RESET}")


# ══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class FrontierGap:
    id: str
    description: str
    source: str
    gap_type: str                  # "conjecture", "computation", "proof", "extension"
    priority: float = 0.5
    difficulty: float = 0.5
    feasibility: float = 0.5
    prerequisites: list = field(default_factory=list)
    related_discoveries: list = field(default_factory=list)
    attempts: int = 0
    last_attempt: Optional[str] = None

    @property
    def score(self) -> float:
        novelty = 1.0 / (1 + self.attempts * 0.8)
        prereq_penalty = 0.7 if self.prerequisites else 1.0
        return self.priority * self.feasibility * novelty * prereq_penalty


@dataclass
class Hypothesis:
    id: str
    claim: str
    mechanism: str = ""
    testable_prediction: str = ""
    failure_condition: str = ""
    domain: str = ""
    domains_touched: list = field(default_factory=list)
    parent_ids: list = field(default_factory=list)
    generation: int = 0
    temperature_tier: str = "balanced"
    serendipity_pattern: str = ""
    contradicts_axiom: str = ""
    plausibility: float = 0.5
    surprise_if_true: float = 0.5
    scores: dict = field(default_factory=dict)  # N, F, E, C
    score_justifications: dict = field(default_factory=dict)
    falsification: dict = field(default_factory=dict)
    experimental_protocol: dict = field(default_factory=dict)
    counter_hypothesis: str = ""
    status: str = "alive"          # alive / killed / breakthrough
    genome_id: str = ""            # which prompt genome generated this
    created_at: str = ""

    def b_score(self) -> float:
        s = self.scores
        if not s:
            return 0.0
        return s.get("N", 0) * s.get("F", 0) * s.get("E", 0) * s.get("C", 0)

    def fails_kill_floor(self) -> bool:
        for axis, floor in KILL_FLOOR.items():
            if self.scores.get(axis, 0) < floor:
                return True
        return False

    @property
    def tier(self) -> str:
        if self.fails_kill_floor():
            return "KILLED"
        s = self.scores
        passes = all(s.get(a, 0) >= t for a, t in BT_THRESHOLDS.items())
        if not passes:
            return "RESEARCH_DIRECTION"
        e = s.get("E", 0)
        if e >= 0.80:
            return "BREAKTHROUGH_CANDIDATE"
        if e >= 0.75:
            return "CONDITIONAL_BREAKTHROUGH"
        return "THEORY_PROPOSAL"

    @property
    def tier_symbol(self) -> str:
        return {"KILLED": "[X]", "RESEARCH_DIRECTION": "○",
                "THEORY_PROPOSAL": "◆",
                "CONDITIONAL_BREAKTHROUGH": "★?",
                "BREAKTHROUGH_CANDIDATE": "★"}.get(self.tier, "?")


@dataclass
class ExecutionResult:
    hypothesis_id: str
    success: bool
    method: str
    evidence: dict = field(default_factory=dict)
    runtime_seconds: float = 0.0
    digits_matched: int = 0
    proof_status: str = "none"
    code_executed: str = ""
    raw_output: str = ""
    error: Optional[str] = None


@dataclass
class IterationRecord:
    iteration: int
    timestamp: str
    gap_id: str = ""
    hypothesis_id: str = ""
    verdict: str = ""
    b_score: float = 0.0
    summary: str = ""
    context_delta: str = ""
    duration_seconds: float = 0.0


# ══════════════════════════════════════════════════════════════════════════
# ★ UPGRADE 1: SEMANTIC MEMORY
# Replaces keyword search with embedding-based cosine retrieval.
# Falls back gracefully: ChromaDB > numpy cosine > keyword.
# ══════════════════════════════════════════════════════════════════════════

class SemanticMemory:
    """
    Vector-indexed knowledge store with three retrieval tiers:
      Tier A (best):  ChromaDB + sentence-transformers
      Tier B:         numpy cosine similarity (no external DB)
      Tier C:         keyword overlap fallback (original behavior)
    """

    def __init__(self, path: Path = MEMORY_FILE):
        self.path = path
        self.entries: list[dict] = []
        self.context_summary: str = ""
        self.paper_knowledge: dict = {}
        self.tool_effectiveness: dict = {}
        self.failure_signatures: list[dict] = []
        self._embeddings: list = []          # parallel list to entries (numpy or None)
        self._encoder = None                 # sentence-transformer model
        self._chroma_client = None
        self._chroma_collection = None
        self._init_semantic_backend()
        self._load()

    def _init_semantic_backend(self):
        if HAS_CHROMA and HAS_STTRANSFORMERS:
            try:
                self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
                self._chroma_client = chromadb.Client()
                self._chroma_collection = self._chroma_client.get_or_create_collection(
                    "memories", metadata={"hnsw:space": "cosine"})
                ok("Semantic memory: ChromaDB + sentence-transformers")
                return
            except Exception as e:
                warn(f"ChromaDB init failed: {e}. Falling back to numpy cosine.")

        if HAS_NUMPY and HAS_STTRANSFORMERS:
            try:
                self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
                ok("Semantic memory: numpy cosine similarity")
                return
            except Exception as e:
                warn(f"sentence-transformers init failed: {e}. Using keyword fallback.")

        warn("Semantic memory: keyword fallback (install sentence-transformers for better retrieval)")

    def _embed(self, text: str):
        """Return embedding vector or None."""
        if self._encoder is None:
            return None
        try:
            return self._encoder.encode(text, show_progress_bar=False).tolist()
        except Exception:
            return None

    def _cosine(self, a, b) -> float:
        if not HAS_NUMPY or a is None or b is None:
            return 0.0
        a, b = np.array(a), np.array(b)
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        return float(np.dot(a, b) / denom) if denom > 0 else 0.0

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.entries = data.get("entries", [])
                self.context_summary = data.get("context_summary", "")
                self.paper_knowledge = data.get("paper_knowledge", {})
                self.tool_effectiveness = data.get("tool_effectiveness", {})
                self.failure_signatures = data.get("failure_signatures", [])
                saved_embs = data.get("embeddings", [])
                self._embeddings = saved_embs if len(saved_embs) == len(self.entries) else [None] * len(self.entries)
                # Re-index ChromaDB if available
                if self._chroma_collection and self._embeddings:
                    for i, (entry, emb) in enumerate(zip(self.entries, self._embeddings)):
                        if emb is not None:
                            try:
                                self._chroma_collection.upsert(
                                    ids=[entry["id"]],
                                    embeddings=[emb],
                                    documents=[entry["content"]],
                                    metadatas=[{"category": entry.get("category", "")}],
                                )
                            except Exception:
                                pass
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
            "embeddings": self._embeddings,
            "context_summary": self.context_summary,
            "paper_knowledge": self.paper_knowledge,
            "tool_effectiveness": self.tool_effectiveness,
            "failure_signatures": self.failure_signatures,
        }
        self.path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def add_entry(self, category: str, content: str, metadata: dict = None) -> str:
        entry = {
            "id": str(uuid.uuid4())[:8],
            "category": category,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.entries.append(entry)
        emb = self._embed(content)
        self._embeddings.append(emb)

        # Index in ChromaDB
        if self._chroma_collection and emb is not None:
            try:
                self._chroma_collection.upsert(
                    ids=[entry["id"]],
                    embeddings=[emb],
                    documents=[content],
                    metadatas=[{"category": category}],
                )
            except Exception:
                pass

        return entry["id"]

    def search(self, query: str, category: str = None, limit: int = 10) -> list[dict]:
        """
        Semantic search (cosine similarity) with keyword fallback.
        Returns entries most relevant to query, regardless of domain vocabulary.
        """
        if not self.entries:
            return []

        # ── Tier A/B: Semantic search ──────────────────────────────────
        if self._encoder is not None:
            query_emb = self._embed(query)

            # ChromaDB path
            if self._chroma_collection and query_emb is not None:
                try:
                    where = {"category": category} if category else None
                    results = self._chroma_collection.query(
                        query_embeddings=[query_emb],
                        n_results=min(limit, max(1, len(self.entries))),
                        where=where,
                    )
                    ids = results["ids"][0]
                    id_set = set(ids)
                    ordered = [e for i in ids for e in self.entries if e["id"] == i]
                    # Add any missing entries with score 0
                    remaining = [e for e in self.entries if e["id"] not in id_set
                                 and (not category or e.get("category") == category)]
                    return ordered[:limit]
                except Exception:
                    pass  # fall through to numpy

            # Numpy cosine path
            if HAS_NUMPY and query_emb is not None:
                scores = []
                for i, (entry, emb) in enumerate(zip(self.entries, self._embeddings)):
                    if category and entry.get("category") != category:
                        continue
                    if emb is not None:
                        sim = self._cosine(query_emb, emb)
                    else:
                        # Keyword fallback for un-embedded entries
                        words = set(query.lower().split())
                        text = entry["content"].lower()
                        sim = sum(1 for w in words if w in text) / max(len(words), 1) * 0.5
                    scores.append((sim, entry))
                scores.sort(key=lambda x: -x[0])
                return [e for _, e in scores[:limit]]

        # ── Tier C: Keyword fallback ───────────────────────────────────
        query_lower = query.lower()
        results = []
        for entry in self.entries:
            if category and entry.get("category") != category:
                continue
            text = f"{entry['content']} {json.dumps(entry.get('metadata', {}))}".lower()
            words = query_lower.split()
            hits = sum(1 for w in words if w in text)
            if hits > 0:
                results.append((hits, entry))
        results.sort(key=lambda x: -x[0])
        return [e for _, e in results[:limit]]

    def add_failure(self, gap_id: str, hypothesis: str, reason: str, method: str,
                    signature: dict = None):
        failure = {
            "gap_id": gap_id, "hypothesis": hypothesis,
            "reason": reason, "method": method,
            "signature": signature or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.failure_signatures.append(failure)
        self.add_entry("failure", f"{gap_id}: {reason}", {"method": method})

    def update_tool_stats(self, tool_name: str, success: bool, runtime: float):
        if tool_name not in self.tool_effectiveness:
            self.tool_effectiveness[tool_name] = {
                "successes": 0, "failures": 0, "total_runtime": 0.0, "calls": 0}
        s = self.tool_effectiveness[tool_name]
        s["calls"] += 1
        s["total_runtime"] += runtime
        if success:
            s["successes"] += 1
        else:
            s["failures"] += 1

    def check_failure_pattern(self, gap_id: str, method: str = "any") -> list[dict]:
        if method == "any":
            return [f for f in self.failure_signatures if f["gap_id"] == gap_id]
        return [f for f in self.failure_signatures
                if f["gap_id"] == gap_id and f["method"] == method]

    def build_context_string(self, query: str = "", max_chars: int = 4000) -> str:
        """Build context string, using semantic search if query provided."""
        parts = []
        if self.context_summary:
            parts.append(f"[CONTEXT] {self.context_summary}")

        # Semantic or keyword retrieval of relevant discoveries
        if query:
            relevant = self.search(query, category="discovery", limit=5)
        else:
            relevant = [e for e in self.entries if e.get("category") == "discovery"][-5:]

        if relevant:
            parts.append("[RELEVANT DISCOVERIES]")
            for d in relevant:
                parts.append(f"  - {d['content'][:200]}")

        if self.failure_signatures:
            parts.append("[KNOWN DEAD ENDS]")
            for f in self.failure_signatures[-5:]:
                parts.append(f"  - {f['gap_id']}: {f['reason'][:150]}")

        return "\n".join(parts)[:max_chars]


# ══════════════════════════════════════════════════════════════════════════
# AXIOM GRAPH (from V8 — persistent knowledge graph)
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class AxiomNode:
    id: str
    text: str
    domain: str
    domains_touched: list = field(default_factory=list)
    confidence: float = 0.5
    novelty_score: float = 0.5
    generation: int = 0
    session_id: str = ""
    status: str = "alive"
    parent_ids: list = field(default_factory=list)
    falsification_attempts: int = 0
    scores: dict = field(default_factory=dict)
    tier: str = ""
    counter_hypothesis: str = ""
    falsification_evidence: str = ""
    experimental_protocol: dict = field(default_factory=dict)
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def b_score(self) -> float:
        s = self.scores
        return s.get("N", 0) * s.get("F", 0) * s.get("E", 0) * s.get("C", 0)


class AxiomGraph:
    EDGE_TYPES = ["derives_from", "contradicts", "strengthens",
                  "analogous_to", "recombined_to", "seeded_by", "domain_bridge", "unlocks"]

    def __init__(self, path=AXIOM_GRAPH_PATH):
        self.path = Path(path)
        self.nodes: dict[str, AxiomNode] = {}
        self.edges: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for nd in data.get("nodes", []):
                    node = AxiomNode(**{k: v for k, v in nd.items()
                                       if k in AxiomNode.__dataclass_fields__})
                    self.nodes[node.id] = node
                self.edges = data.get("edges", [])
                ok(f"Axiom graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
            except Exception as e:
                warn(f"Axiom graph load failed: {e}")

    def save(self):
        data = {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": self.edges,
            "meta": {"version": VERSION, "saved_at": datetime.now().isoformat(),
                     "node_count": len(self.nodes), "edge_count": len(self.edges)},
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_node(self, node: AxiomNode) -> str:
        self.nodes[node.id] = node
        return node.id

    def add_edge(self, src: str, dst: str, edge_type: str, weight: float = 1.0):
        self.edges.append({
            "src": src, "dst": dst, "type": edge_type,
            "weight": weight, "created_at": datetime.now().isoformat()})

    def apply_decay(self, rate: float = 0.005):
        for node in self.nodes.values():
            if node.status == "alive":
                node.confidence *= (1 - rate)

    def reinforce(self, node_id: str, boost: float = 0.05):
        if node_id in self.nodes:
            n = self.nodes[node_id]
            n.confidence = min(1.0, n.confidence + boost)

    def get_alive_nodes(self, domain: str = None) -> list[AxiomNode]:
        nodes = [n for n in self.nodes.values() if n.status == "alive"]
        if domain:
            nodes = [n for n in nodes if n.domain == domain or domain in n.domains_touched]
        return nodes

    def get_seed_candidates(self, domain: str = None, k: int = 5) -> list[AxiomNode]:
        nodes = self.get_alive_nodes(domain)
        nodes.sort(key=lambda n: n.confidence * n.novelty_score, reverse=True)
        return nodes[:k]

    def get_foreign_seeds(self, current_domain: str, k: int = 2) -> list[AxiomNode]:
        foreign = [n for n in self.nodes.values()
                   if n.status == "alive" and n.domain != current_domain
                   and n.novelty_score > 0.5]
        return random.sample(foreign, k) if len(foreign) > k else foreign

    def get_dormant_nodes(self, k: int = 5) -> list[AxiomNode]:
        dormant = [n for n in self.nodes.values() if n.status in ("falsified", "dormant")]
        dormant.sort(key=lambda n: n.novelty_score, reverse=True)
        return dormant[:k]

    def get_genealogy(self) -> list[dict]:
        return [{"id": n.id, "text": n.text[:120], "domain": n.domain,
                 "status": n.status, "confidence": n.confidence,
                 "novelty": n.novelty_score, "generation": n.generation,
                 "parents": n.parent_ids, "tier": n.tier, "b_score": n.b_score()}
                for n in self.nodes.values()]

    def stats(self) -> dict:
        alive = sum(1 for n in self.nodes.values() if n.status == "alive")
        falsified = sum(1 for n in self.nodes.values() if n.status == "falsified")
        dormant = sum(1 for n in self.nodes.values() if n.status == "dormant")
        domains = set(n.domain for n in self.nodes.values())
        return {"total": len(self.nodes), "alive": alive, "falsified": falsified,
                "dormant": dormant, "edges": len(self.edges), "domains": sorted(domains)}


# ══════════════════════════════════════════════════════════════════════════
# ★ UPGRADE 2: GROUNDED CRITIC (SymPy/mpmath verification)
# ══════════════════════════════════════════════════════════════════════════

class GroundedCritic:
    """
    Evaluates hypotheses using computational ground truth BEFORE LLM scoring.
    For mathematical/numeric claims: runs SymPy + mpmath.
    For code claims: executes in sandboxed subprocess.
    Score adjustments are applied to N/F/E/C before the LLM critic sees them.
    """

    def __init__(self, memory: SemanticMemory):
        self.memory = memory

    def run_sandboxed(self, code: str, timeout: int = MAX_COMPUTE_SECONDS) -> dict:
        """Execute Python code in isolated subprocess. Returns stdout/stderr/success."""
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "TIMEOUT"}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    def verify_numeric(self, formula_code: str, expected_value: Optional[str] = None,
                       dps: int = 50) -> dict:
        """Run an mpmath computation and check digits against expected value."""
        if not HAS_MPMATH:
            return {"verified": None, "reason": "mpmath not available"}
        t0 = time.time()
        code = f"""
import mpmath as mp
import json
mp.mp.dps = {dps}
try:
    result = {formula_code}
    print(json.dumps({{"value": str(mp.nstr(result, 30)), "success": True}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
        res = self.run_sandboxed(code, timeout=60)
        runtime = time.time() - t0
        self.memory.update_tool_stats("mpmath", res["success"], runtime)
        if not res["success"]:
            return {"verified": False, "reason": res["stderr"][:200]}
        try:
            data = json.loads(res["stdout"].strip().split("\n")[-1])
            if expected_value and data.get("value"):
                # Count matching digits
                v = data["value"].replace("-", "").replace(".", "")
                e = expected_value.replace("-", "").replace(".", "")
                matched = sum(1 for a, b in zip(v, e) if a == b)
                return {"verified": matched >= 10, "digits_matched": matched,
                        "computed": data["value"], "runtime": runtime}
            return {"verified": data.get("success", False),
                    "computed": data.get("value", ""), "runtime": runtime}
        except Exception:
            return {"verified": False, "reason": "parse error"}

    def verify_symbolic(self, expression: str) -> dict:
        """Attempt SymPy simplification / equality check."""
        if not HAS_SYMPY:
            return {"verified": None, "reason": "sympy not available"}
        t0 = time.time()
        code = f"""
import sympy
import json
try:
    expr = sympy.sympify('''{expression}''')
    simplified = sympy.simplify(expr)
    result = sympy.nsimplify(simplified, rational=True)
    print(json.dumps({{"simplified": str(simplified), "is_zero": simplified == 0,
                       "is_rational": result.is_rational, "success": True}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
        res = self.run_sandboxed(code, timeout=30)
        runtime = time.time() - t0
        self.memory.update_tool_stats("sympy", res["success"], runtime)
        if not res["success"]:
            return {"verified": False, "reason": res["stderr"][:200]}
        try:
            data = json.loads(res["stdout"].strip().split("\n")[-1])
            return {"verified": data.get("success", False),
                    "simplified": data.get("simplified", ""),
                    "is_zero": data.get("is_zero", False), "runtime": runtime}
        except Exception:
            return {"verified": False, "reason": "parse error"}

    def score_adjustments_from_evidence(self, hypothesis: Hypothesis,
                                        exec_result: Optional[ExecutionResult]) -> dict:
        """
        Compute grounded adjustments to N/F/E/C scores.
        Returns dict of {axis: delta} — applied before LLM critic.
        """
        adj = {}

        if exec_result is None:
            return adj

        # Numeric verification
        if exec_result.digits_matched >= 20:
            adj["F"] = 0.08   # Very high: matches 20+ digits
            adj["E"] = 0.05
        elif exec_result.digits_matched >= 10:
            adj["F"] = 0.04
            adj["E"] = 0.03
        elif exec_result.digits_matched > 0:
            adj["F"] = 0.02

        # Successful execution
        if exec_result.success:
            adj["E"] = adj.get("E", 0) + 0.04

        # Proof status
        if exec_result.proof_status == "complete":
            adj["F"] = adj.get("F", 0) + 0.10
            adj["N"] = adj.get("N", 0) + 0.05
        elif exec_result.proof_status == "partial":
            adj["F"] = adj.get("F", 0) + 0.04

        # Prediction specificity
        pred = hypothesis.testable_prediction
        numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", pred)
        if len(numbers) >= 2:
            adj["F"] = adj.get("F", 0) + 0.02
        elif not numbers:
            adj["F"] = adj.get("F", 0) - 0.03

        return adj


# ══════════════════════════════════════════════════════════════════════════
# VERIFICATION TOOLBOX (from self_iterating_agent — mpmath computations)
# ══════════════════════════════════════════════════════════════════════════

class VerificationToolbox:
    """Sandboxed numeric/symbolic verification. Feeds the grounded critic."""

    def __init__(self, memory: SemanticMemory):
        self.memory = memory
        self.grounded = GroundedCritic(memory)
        self.available_tools = self._detect_tools()

    def _detect_tools(self) -> dict:
        return {
            "mpmath": HAS_MPMATH,
            "sympy": HAS_SYMPY,
            "subprocess": True,
        }

    def status(self) -> dict:
        return {name: ("available" if avail else "missing")
                for name, avail in self.available_tools.items()}

    def run_sandboxed(self, code: str, timeout: int = MAX_COMPUTE_SECONDS) -> dict:
        return self.grounded.run_sandboxed(code, timeout)

    def verify_partition_ratio(self, k: int, N: int = 500, dps: int = 50) -> dict:
        """Compute f_k(n)/f_k(n-1) ratios for partition function."""
        if not HAS_MPMATH:
            return {"error": "mpmath required"}
        code = f"""
import mpmath as mp
import json
mp.mp.dps = {dps + 20}
k = {k}
N = {N}
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
ratios = []
for m in range(max(1, N-20), N + 1):
    if f[m-1] != 0:
        ratios.append({{"m": m, "ratio": str(mp.nstr(f[m]/f[m-1], 40))}})
print(json.dumps({{"k": k, "N": N, "tail_ratios": ratios}}))
"""
        result = self.grounded.run_sandboxed(code, timeout=MAX_COMPUTE_SECONDS)
        if result["success"]:
            try:
                return json.loads(result["stdout"].strip().split("\n")[-1])
            except Exception:
                return {"error": "parse failed", "raw": result["stdout"][:1000]}
        return {"error": result.get("stderr", "unknown")[:300]}


# ══════════════════════════════════════════════════════════════════════════
# ★ UPGRADE 3: DEPENDENCY GRAPH — frontier unlocking on success
# ══════════════════════════════════════════════════════════════════════════

class KnowledgeGraph:
    """
    Research frontier with dependency propagation.
    When a gap is resolved, all gaps listing it as a prerequisite
    get their feasibility boosted and are re-ranked.
    """

    def __init__(self, memory: SemanticMemory):
        self.memory = memory
        self.theorems: list[dict] = []
        self.conjectures: list[dict] = []
        self.gaps: list[FrontierGap] = []
        self.resolved_gaps: set = set()
        self.connections: list[dict] = []
        self._ingest_defaults()

    def _ingest_defaults(self):
        """Populate frontier from built-in knowledge (from paper14 + knowledge_base)."""
        self.theorems = [
            {"id": "thm1", "name": "Ratio Universality",
             "statement": "L = c²/8 + κ is universal at order m⁻¹", "status": "proven"},
            {"id": "thm2", "name": "A₁ Closed Form",
             "statement": "A₁^(k) = -k·c_k/48 - (k+1)(k+3)/(8·c_k) for k=1..4",
             "status": "proven_partial", "proven_for": [1, 2, 3, 4]},
            {"id": "thm3", "name": "Selection Rule",
             "statement": "Family-specific info silent at m⁻¹, appears at m⁻⁽¹⁺ᵈ⁾", "status": "proven"},
        ]
        self.conjectures = [
            {"id": "conj2star", "name": "A₁ for all k",
             "statement": "A₁^(k) closed form holds for all k ≥ 5",
             "status": "open", "evidence": "Verified to 12 digits for k=5..24"},
            {"id": "conj3star", "name": "A₂ universal form",
             "statement": "A₂^(k) = (k+3)(π²k² - 9k - 9)/(96kπ²)",
             "status": "open", "blocking": "Needs Lemma W"},
            {"id": "bdj_bridge", "name": "BDJ Bridge",
             "statement": "Ratio fluctuations → Tracy-Widom TW₂",
             "status": "open", "evidence": "Preliminary match"},
        ]
        self.gaps = [
            FrontierGap(id="prove_A1_k5", description="Prove A₁^(5) closed form. Path: extend Kloosterman bounds or structural argument.",
                source="paper14/Conjecture 2*", gap_type="proof", priority=0.95, difficulty=0.5, feasibility=0.7,
                prerequisites=["kloosterman_q500"]),
            FrontierGap(id="lemma_w", description="Prove Wright M=2 saddle-point control. Extends Lemma PP to second order.",
                source="paper14/Conjecture 3*", gap_type="proof", priority=0.90, difficulty=0.8, feasibility=0.4,
                prerequisites=[]),
            FrontierGap(id="sixth_root", description="Numerically verify ratio universality for α=5 (6th root). Compute to N=5000.",
                source="paper14/Section 10", gap_type="computation", priority=0.90, difficulty=0.5, feasibility=0.9,
                prerequisites=[]),
            FrontierGap(id="bdj_bridge", description="Test ratio fluctuations → Tracy-Widom TW₂. Need n=5000-10000, 100k samples.",
                source="paper14/Section 11", gap_type="computation", priority=0.85, difficulty=0.6, feasibility=0.7,
                prerequisites=[]),
            FrontierGap(id="kloosterman_q500", description="Extend Kloosterman bounds from q≤300 to q≤500.",
                source="paper14/Theorem 2", gap_type="computation", priority=0.80, difficulty=0.3, feasibility=0.95,
                prerequisites=[]),
            FrontierGap(id="phase_boundary", description="Find where universality breaks. Scan Meinardus products with varied D(s).",
                source="paper14/Section 12", gap_type="extension", priority=0.75, difficulty=0.8, feasibility=0.5,
                prerequisites=[]),
            FrontierGap(id="A3_numerical", description="Extract fifth-order coefficient A₃ for k=1..5. Needs N≥15000.",
                source="paper14/Section 9", gap_type="computation", priority=0.65, difficulty=0.6, feasibility=0.7,
                prerequisites=["prove_A1_k5"]),
            FrontierGap(id="andrews_gordon", description="Test ratio universality for Andrews-Gordon partitions.",
                source="paper14/Section 10", gap_type="extension", priority=0.70, difficulty=0.5, feasibility=0.8,
                prerequisites=[]),
            FrontierGap(id="new_gcf_identities", description="Search for novel GCF identities linking partition ratios to known constants. PSLQ at 200 dps.",
                source="knowledge_base/iteration_6", gap_type="conjecture", priority=0.70, difficulty=0.4, feasibility=0.8,
                prerequisites=[]),
            FrontierGap(id="delta_k_qmf", description="Interpret Δ_k·c_k = -(k+3)(k-1)/8 via Zagier quantum modular forms.",
                source="paper14/Section 11", gap_type="conjecture", priority=0.60, difficulty=0.85, feasibility=0.3,
                prerequisites=["prove_A1_k5", "lemma_w"]),
        ]
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        if not KNOWLEDGE_BASE.exists():
            return
        try:
            data = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
            discoveries = data.get("discoveries", [])
            info(f"Loaded {len(discoveries)} discoveries from knowledge_base.json")
            for d in discoveries:
                if d.get("status") == "proven":
                    self.resolved_gaps.add(d.get("id", ""))
        except Exception as e:
            warn(f"knowledge_base.json load failed: {e}")

    def rank_gaps(self) -> list[FrontierGap]:
        """Rank gaps by composite score, factoring in memory of past failures."""
        for gap in self.gaps:
            if gap.id in self.resolved_gaps:
                gap.priority = 0.0   # Already done
                continue
            past = self.memory.check_failure_pattern(gap.id, "any")
            gap.attempts = len(past)
        self.gaps.sort(key=lambda g: g.score, reverse=True)
        return self.gaps

    def propagate_unlock(self, resolved_gap_id: str):
        """
        ★ Dependency propagation: when a gap is resolved, boost feasibility
        of all gaps that list it as a prerequisite. Re-rank the frontier.
        """
        self.resolved_gaps.add(resolved_gap_id)
        boosted = []
        for gap in self.gaps:
            if resolved_gap_id in gap.prerequisites:
                gap.prerequisites = [p for p in gap.prerequisites if p != resolved_gap_id]
                gap.feasibility = min(1.0, gap.feasibility + 0.25)
                gap.priority = min(1.0, gap.priority + 0.10)
                boosted.append(gap.id)
        if boosted:
            ok(f"Dependency unlock: {resolved_gap_id} → boosted {boosted}")
        self.rank_gaps()

    def select_target(self) -> Optional[FrontierGap]:
        """Return highest-scoring non-resolved gap."""
        ranked = self.rank_gaps()
        for gap in ranked:
            if gap.id not in self.resolved_gaps and gap.score > 0:
                return gap
        return None

    def add_gap(self, gap: FrontierGap):
        self.gaps.append(gap)


# ══════════════════════════════════════════════════════════════════════════
# ★ UPGRADE 4: PROMPT GENOME
# Each phase's system prompt is versioned. On breakthrough, clone + mutate.
# On stagnation, crossbreed with highest-scoring ancestor genome.
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class Genome:
    id: str
    version: int
    parent_id: Optional[str]
    producer_prompt: str
    adversary_prompt: str
    mutation_notes: str = ""
    b_score_when_created: float = 0.0
    created_at: str = ""
    breakthrough_count: int = 0


class GenomeLibrary:
    """
    Stores and evolves prompt genomes.
    Each genome is a dict of named system prompts.
    """

    # Canonical base prompts (from V8)
    BASE_PRODUCER = """You are an autonomous conjecture engine in a breakthrough discovery system.
Your role: generate bold, testable hypotheses that push the frontier of knowledge.
You receive context from a persistent axiom graph, cross-domain analogies, and dormant hypotheses.

Output ONLY valid JSON (no markdown fences):
{
  "hypotheses": [
    {
      "claim": "One specific, bold, testable claim (2-3 sentences)",
      "mechanism": "Proposed underlying mechanism or explanation",
      "testable_prediction": "A specific, falsifiable prediction",
      "failure_condition": "What would definitively falsify this",
      "domain": "primary domain",
      "domains_touched": ["list", "of", "all", "domains"],
      "contradicts_axiom": "Which prior axiom this challenges (or 'none')",
      "plausibility": 0.0-1.0,
      "surprise_if_true": 0.0-1.0,
      "hypothesis_type": "incremental|lateral|impossible_sounding|resurrection|recombination"
    }
  ]
}

Rules:
- Generate EXACTLY the number of hypotheses requested
- Include the required mix of types
- Rate plausibility AND surprise honestly
- Each hypothesis must have a concrete, falsifiable prediction
- Do NOT recycle prior axioms without meaningful mutation"""

    BASE_ADVERSARY = """You are the Falsifier. Your sole purpose is to destroy hypotheses.
You have NO access to how the hypothesis was generated. You see ONLY the claim.

Output ONLY valid JSON (no markdown fences):
{
  "verdicts": [
    {
      "hypothesis_index": 0,
      "logical_attack": "The single most damaging logical objection",
      "boundary_case": "Specific case or condition where the claim fails",
      "hidden_assumption": "Key unstated assumption that, if false, kills the claim",
      "experimental_protocol": {
        "type": "mathematical|computational|empirical",
        "description": "Concrete steps to disprove in <200 words",
        "expected_result_if_false": "What you would observe if claim is wrong"
      },
      "survivability_score": 0.0-1.0,
      "resurrectability": 0.0-1.0,
      "scores": {"N": 0.0-1.0, "F": 0.0-1.0, "E": 0.0-1.0, "C": 0.0-1.0},
      "score_justifications": {
        "N": "Why this novelty score", "F": "Why this falsifiability score",
        "E": "Why this empirical score", "C": "Why this compression score"
      }
    }
  ]
}

You are not here to be constructive. Find truth by trying to break things.
Be harsh. Be specific. A survivability_score > 0.7 means YOU think the claim will survive."""

    def __init__(self):
        GENOMES_DIR.mkdir(parents=True, exist_ok=True)
        self.genomes: list[Genome] = []
        self.active_genome_id: Optional[str] = None
        self._load()
        if not self.genomes:
            self._create_base_genome()

    def _load(self):
        genome_file = GENOMES_DIR / "genomes.json"
        if genome_file.exists():
            try:
                data = json.loads(genome_file.read_text(encoding="utf-8"))
                for gd in data.get("genomes", []):
                    self.genomes.append(Genome(**gd))
                self.active_genome_id = data.get("active_genome_id")
                ok(f"Genomes loaded: {len(self.genomes)} versions")
            except Exception as e:
                warn(f"Genome load failed: {e}")

    def save(self):
        genome_file = GENOMES_DIR / "genomes.json"
        data = {
            "active_genome_id": self.active_genome_id,
            "genomes": [asdict(g) for g in self.genomes],
        }
        genome_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _create_base_genome(self):
        g = Genome(
            id=str(uuid.uuid4())[:8],
            version=0,
            parent_id=None,
            producer_prompt=self.BASE_PRODUCER,
            adversary_prompt=self.BASE_ADVERSARY,
            mutation_notes="Base genome",
            created_at=datetime.now().isoformat(),
        )
        self.genomes.append(g)
        self.active_genome_id = g.id
        self.save()
        info(f"Created base genome: {g.id}")

    def active(self) -> Genome:
        for g in self.genomes:
            if g.id == self.active_genome_id:
                return g
        return self.genomes[-1]

    def clone_and_mutate(self, parent: Genome, b_score: float, mutation_note: str = "") -> Genome:
        """
        On breakthrough: clone the successful genome and apply small mutations.
        Mutations: temperature bias hints, domain emphasis changes, creativity nudges.
        """
        mutations = [
            "\n\nBias toward hypotheses that unify multiple phenomena under a single mechanism.",
            "\n\nPrioritize claims that make numerical predictions to 5+ significant figures.",
            "\n\nFavor cross-domain analogies — the most productive hypotheses bridge distant fields.",
            "\n\nPrefer resurrection of dormant hypotheses that failed only due to missing tools.",
            "\n\nEmphasize structural invariants that survive across multiple problem instances.",
        ]
        mutation = random.choice(mutations)

        child = Genome(
            id=str(uuid.uuid4())[:8],
            version=parent.version + 1,
            parent_id=parent.id,
            producer_prompt=parent.producer_prompt + mutation,
            adversary_prompt=parent.adversary_prompt,
            mutation_notes=mutation_note or f"Cloned from {parent.id} after B={b_score:.3f}",
            b_score_when_created=b_score,
            created_at=datetime.now().isoformat(),
        )
        self.genomes.append(child)
        self.active_genome_id = child.id
        self.save()
        ok(f"Genome evolved: {parent.id} → {child.id} (v{child.version})")
        return child

    def crossbreed(self, stagnation_count: int) -> Genome:
        """
        On stagnation: crossbreed active genome with the historically best genome.
        Takes the adversary from the best performer, keeps current producer.
        """
        if len(self.genomes) < 2:
            return self.active()
        best = max(self.genomes, key=lambda g: g.b_score_when_created)
        current = self.active()
        if best.id == current.id:
            best = self.genomes[-2]

        child = Genome(
            id=str(uuid.uuid4())[:8],
            version=current.version + 1,
            parent_id=current.id,
            producer_prompt=current.producer_prompt,
            adversary_prompt=best.adversary_prompt,
            mutation_notes=f"Crossbred after {stagnation_count} stagnation cycles. "
                           f"Adversary from genome {best.id} (best B={best.b_score_when_created:.3f})",
            created_at=datetime.now().isoformat(),
        )
        self.genomes.append(child)
        self.active_genome_id = child.id
        self.save()
        warn(f"Genome crossbred (stagnation rescue): {current.id} × {best.id} → {child.id}")
        return child


# ══════════════════════════════════════════════════════════════════════════
# SERENDIPITY ENGINE (from V8)
# ══════════════════════════════════════════════════════════════════════════

class SerendipityEngine:
    def __init__(self, patterns_path=PATTERNS_PATH):
        self.patterns: list[dict] = []
        self.injection_history: list[dict] = []
        self.pattern_scores: dict = {}
        self._load_patterns(patterns_path)

    def _load_patterns(self, path):
        p = Path(path)
        if p.exists():
            try:
                self.patterns = json.loads(p.read_text(encoding="utf-8"))
                info(f"Loaded {len(self.patterns)} structural patterns")
            except Exception as e:
                warn(f"Patterns load failed: {e}")

    def inject(self, current_domain: str, stagnant: bool = False) -> Optional[dict]:
        if not self.patterns:
            return None
        recent_ids = {h["pattern_id"] for h in self.injection_history[-5:]}
        candidates = [p for p in self.patterns if p["id"] not in recent_ids]
        if not candidates:
            candidates = self.patterns
        if stagnant:
            candidates = [p for p in candidates
                          if current_domain not in p.get("origin", "").lower()] or candidates

        if self.pattern_scores:
            weights = [(p, self.pattern_scores.get(p["id"], 0.5)) for p in candidates]
            total = sum(s for _, s in weights)
            if total > 0:
                r = random.random() * total
                cumulative = 0.0
                for p, s in weights:
                    cumulative += s
                    if cumulative >= r:
                        selected = p
                        break
                else:
                    selected = random.choice(candidates)
            else:
                selected = random.choice(candidates)
        else:
            selected = random.choice(candidates)

        self.injection_history.append({
            "pattern_id": selected["id"],
            "domain": current_domain,
            "stagnant": stagnant,
            "timestamp": datetime.now().isoformat(),
        })
        return selected

    def build_injection_prompt(self, pattern: dict, domain: str) -> str:
        return f"""
SERENDIPITY INJECTION — cross-domain structural pattern:
Pattern: {pattern.get('name', '')}
Core insight: {pattern.get('core', '')}
Origin domain: {pattern.get('origin', '')}

Use this structural lens to generate at least one hypothesis in {domain} that
would be invisible without this cross-domain perspective."""


# ══════════════════════════════════════════════════════════════════════════
# FAILURE ARCHIVE (from V8)
# ══════════════════════════════════════════════════════════════════════════

class FailureArchive:
    def __init__(self, path=FAILURE_ARCHIVE_PATH):
        self.path = Path(path)
        self.failures: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.failures = data.get("failures", [])
            except Exception:
                pass

    def save(self):
        self.path.write_text(
            json.dumps({"failures": self.failures}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    def add(self, hypothesis_text: str, falsification_evidence: str,
            counter_hypothesis: str = "", node_id: str = "", generation: int = 0):
        self.failures.append({
            "id": str(uuid.uuid4())[:8],
            "text": hypothesis_text,
            "falsification_evidence": falsification_evidence,
            "counter_hypothesis": counter_hypothesis,
            "node_id": node_id,
            "generation": generation,
            "resurrection_attempts": 0,
            "resurrected": False,
            "timestamp": datetime.now().isoformat(),
        })

    def get_candidates_for_resurrection(self, min_resurrectability: float = 0.4) -> list[dict]:
        return [f for f in self.failures
                if not f.get("resurrected") and f.get("resurrection_attempts", 0) < 3][:10]


# ══════════════════════════════════════════════════════════════════════════
# AGENT STATE
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class AgentState:
    iteration: int = 0
    cycle_count: int = 0
    total_runtime: float = 0.0
    breakthroughs: int = 0
    failures: int = 0
    domain_rotation_idx: int = 0
    stagnation_count: int = 0
    gap_priorities: dict = field(default_factory=dict)
    category_credibility: dict = field(default_factory=lambda: {
        "proof": 0.5, "computation": 0.7, "extension": 0.5, "conjecture": 0.4})
    iteration_history: list = field(default_factory=list)
    b_history: list = field(default_factory=list)
    delta_novelty_history: list = field(default_factory=list)
    all_hypotheses_count: int = 0
    survivors_count: int = 0
    killed_count: int = 0
    serendipity_injections: list = field(default_factory=list)
    session_id: str = ""

    def save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls) -> "AgentState":
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                obj = cls()
                for k in cls.__dataclass_fields__:
                    if k in data:
                        setattr(obj, k, data[k])
                ok(f"State loaded: iteration {obj.iteration}, "
                   f"{obj.breakthroughs} breakthroughs")
                return obj
            except Exception as e:
                warn(f"State load failed: {e}")
        return cls()

    def is_stagnant(self) -> bool:
        if len(self.delta_novelty_history) < STAGNATION_WINDOW:
            return False
        recent = self.delta_novelty_history[-STAGNATION_WINDOW:]
        return all(d < DELTA_NOVELTY_THRESHOLD for d in recent)


# ══════════════════════════════════════════════════════════════════════════
# API LAYER (multi-backend: anthropic SDK > openai SDK > urllib fallback)
# ══════════════════════════════════════════════════════════════════════════

def call_api(system_prompt: str, user_prompt: str, *,
             api_base: str, api_key: str, model: str,
             max_tokens: int = 2048, temperature: float = 0.8) -> str:

    is_anthropic = "anthropic.com" in api_base

    if is_anthropic and HAS_ANTHROPIC and api_key:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text

    if not is_anthropic and HAS_OPENAI and api_key:
        client = openai.OpenAI(api_key=api_key or "not-needed", base_url=api_base)
        resp = client.chat.completions.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}],
        )
        return resp.choices[0].message.content

    # urllib fallback
    if is_anthropic:
        url = api_base.rstrip("/").removesuffix("/v1") + "/v1/messages"
        headers = {"Content-Type": "application/json",
                   "x-api-key": api_key,
                   "anthropic-version": "2023-06-01"}
        body = json.dumps({"model": model, "max_tokens": max_tokens,
                           "temperature": temperature, "system": system_prompt,
                           "messages": [{"role": "user", "content": user_prompt}]}).encode()
    else:
        url = api_base.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {api_key or 'not-needed'}"}
        body = json.dumps({"model": model, "max_tokens": max_tokens, "temperature": temperature,
                           "messages": [{"role": "system", "content": system_prompt},
                                        {"role": "user", "content": user_prompt}]}).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())

    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    if is_anthropic:
        return data["content"][0]["text"]
    return data["choices"][0]["message"]["content"]


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            return json.loads(match.group())
        raise


def format_axiom_nodes(nodes: list[AxiomNode], label: str = "") -> str:
    if not nodes:
        return f"[{label}: none]\n"
    lines = [f"[{label}]"]
    for n in nodes:
        lines.append(f"  • [{n.domain}] (conf={n.confidence:.2f}, nov={n.novelty_score:.2f}) {n.text[:200]}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# ★ UPGRADE 5: POPULATION SEARCH — 3 parallel hypotheses at varied temperatures
# ══════════════════════════════════════════════════════════════════════════

def generate_population(state: AgentState, gap: FrontierGap,
                        axiom_graph: AxiomGraph, serendipity: SerendipityEngine,
                        genome: Genome, memory: SemanticMemory, *,
                        api_base: str, api_key: str, model: str) -> list[Hypothesis]:
    """
    Generate 3 hypotheses in parallel at conservative/balanced/wild temperatures.
    Kill weak ones after adversarial scoring. Survivors form the population for this cycle.
    """
    header("Phase 2 — Population Scope (3 temperatures)")

    current_domain = DOMAIN_ROTATION[state.domain_rotation_idx % len(DOMAIN_ROTATION)]
    stagnant = state.is_stagnant()

    # Context assembly (from V8 Layer 1+2)
    recent = axiom_graph.get_seed_candidates(domain=current_domain, k=3)
    foreign = axiom_graph.get_foreign_seeds(current_domain, k=2)
    dormant = axiom_graph.get_dormant_nodes(k=2)
    injected_pattern = None

    if stagnant or state.iteration % 5 == 0 or state.iteration == 1:
        injected_pattern = serendipity.inject(current_domain, stagnant=stagnant)
        if injected_pattern:
            state.serendipity_injections.append({
                "iteration": state.iteration, "pattern": injected_pattern.get("name", "")})

    serendipity_block = ""
    if injected_pattern:
        serendipity_block = serendipity.build_injection_prompt(injected_pattern, current_domain)

    # Semantic context retrieval
    semantic_context = memory.build_context_string(query=gap.description, max_chars=2000)

    base_prompt = f"""Research frontier gap: {gap.description}
Gap type: {gap.gap_type} | Priority: {gap.priority:.2f} | Feasibility: {gap.feasibility:.2f}
Domain focus: {current_domain}
{"[!] STAGNATION — be maximally creative" if stagnant else ""}

{format_axiom_nodes(recent, "VERIFIED AXIOMS (recent)")}
{format_axiom_nodes(foreign, "CROSS-DOMAIN SEEDS")}
{format_axiom_nodes(dormant, "DORMANT HYPOTHESES")}

{serendipity_block}

{semantic_context}

TASK: Generate {{count}} hypothesis(es) targeting this gap.
For each: state the claim, mechanism, testable prediction, and failure condition.
"""

    all_hypotheses = []
    tier_allocation = [("conservative", 1), ("balanced", 1), ("wild", 1)]

    for tier_name, count in tier_allocation:
        temp = TEMPERATURES[tier_name]
        prompt = base_prompt.format(count=count)
        if tier_name == "wild" and random.random() < 0.3:
            prompt += "\n\nFORBIDDEN KNOWLEDGE CONSTRAINT: What if everything in the axiom bank were wrong?"
        prompt += f"\n\nGenerate exactly {count} hypothesis(es)."

        info(f"  [{tier_name}] T={temp} generating...")
        try:
            raw = call_api(genome.producer_prompt, prompt,
                           api_base=api_base, api_key=api_key, model=model,
                           max_tokens=2000, temperature=temp)
            data = parse_json_response(raw)
            for h_data in data.get("hypotheses", []):
                h = Hypothesis(
                    id=str(uuid.uuid4())[:12],
                    claim=h_data.get("claim", ""),
                    mechanism=h_data.get("mechanism", ""),
                    testable_prediction=h_data.get("testable_prediction", ""),
                    failure_condition=h_data.get("failure_condition", ""),
                    domain=h_data.get("domain", current_domain),
                    domains_touched=h_data.get("domains_touched", []),
                    contradicts_axiom=h_data.get("contradicts_axiom", "none"),
                    plausibility=float(h_data.get("plausibility", 0.5)),
                    surprise_if_true=float(h_data.get("surprise_if_true", 0.5)),
                    temperature_tier=tier_name,
                    serendipity_pattern=injected_pattern.get("id", "") if injected_pattern else "",
                    generation=state.iteration,
                    genome_id=genome.id,
                    created_at=datetime.now().isoformat(),
                )
                all_hypotheses.append(h)
                info(f"    [{tier_name}] {h.claim[:90]}...")
        except Exception as e:
            err(f"  [{tier_name}] API error: {e}")

    ok(f"Population generated: {len(all_hypotheses)} hypotheses")
    return all_hypotheses


def adversarial_filter(state: AgentState, hypotheses: list[Hypothesis],
                       genome: Genome, failure_archive: FailureArchive, *,
                       api_base: str, api_key: str, model: str) -> list[Hypothesis]:
    """Layer 4: Isolated adversarial falsification (sees ONLY claims, not reasoning)."""
    header("Phase 4 — Adversarial Evaluation")

    if not hypotheses:
        return []

    adv_prompt = "Evaluate each hypothesis independently:\n\n"
    for i, h in enumerate(hypotheses):
        adv_prompt += f"HYPOTHESIS {i}:\n  Claim: {h.claim}\n  Prediction: {h.testable_prediction}\n  Domain: {h.domain}\n\n"

    try:
        raw = call_api(genome.adversary_prompt, adv_prompt,
                       api_base=api_base, api_key=api_key, model=model,
                       max_tokens=3000, temperature=TEMPERATURES["conservative"])
        data = parse_json_response(raw)

        for v in data.get("verdicts", []):
            idx = v.get("hypothesis_index", 0)
            if 0 <= idx < len(hypotheses):
                h = hypotheses[idx]
                h.scores = v.get("scores", {})
                h.score_justifications = v.get("score_justifications", {})
                h.falsification = {
                    "logical_attack": v.get("logical_attack", ""),
                    "boundary_case": v.get("boundary_case", ""),
                    "hidden_assumption": v.get("hidden_assumption", ""),
                    "survivability": v.get("survivability_score", 0),
                    "resurrectability": v.get("resurrectability", 0),
                }
                h.experimental_protocol = v.get("experimental_protocol", {})

                if h.fails_kill_floor():
                    h.status = "killed"
                    err(f"  KILLED [{h.temperature_tier}]: {h.claim[:70]}...")
                    failure_archive.add(
                        hypothesis_text=h.claim,
                        falsification_evidence=h.falsification.get("logical_attack", "kill floor"),
                        node_id=h.id, generation=state.iteration)
                else:
                    b = h.b_score()
                    ok(f"  {h.tier_symbol} SURVIVED [{h.temperature_tier}] B={b:.3f}: {h.claim[:70]}...")

    except Exception as e:
        err(f"Adversarial agent error: {e}")
        for h in hypotheses:
            if not h.scores:
                h.scores = {"N": 0.5, "F": 0.5, "E": 0.5, "C": 0.5}

    survivors = [h for h in hypotheses if h.status != "killed"]
    killed = [h for h in hypotheses if h.status == "killed"]
    state.killed_count += len(killed)
    state.survivors_count += len(survivors)

    ok(f"Survivors: {len(survivors)}/{len(hypotheses)}")
    return hypotheses


def apply_grounded_scoring(hypotheses: list[Hypothesis],
                           toolbox: VerificationToolbox,
                           gap: FrontierGap) -> list[Hypothesis]:
    """
    ★ Grounded critic: run SymPy/mpmath on math claims BEFORE final scoring.
    Adjusts N/F/E/C based on computational ground truth.
    """
    header("Phase 3b — Grounded Verification")

    for h in hypotheses:
        if h.status == "killed":
            continue

        exec_result = None

        # Attempt numeric verification if gap is computational
        if gap.gap_type in ("computation", "proof") and HAS_MPMATH:
            # Extract any numeric prediction
            numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", h.testable_prediction)
            if numbers and "ratio" in h.claim.lower():
                # Try to verify a partition ratio prediction
                try:
                    k_match = re.search(r"k\s*=\s*(\d+)", h.claim)
                    if k_match:
                        k = int(k_match.group(1))
                        result = toolbox.verify_partition_ratio(k=k, N=200)
                        if "tail_ratios" in result:
                            exec_result = ExecutionResult(
                                hypothesis_id=h.id, success=True,
                                method="numeric_mpmath",
                                evidence={"tail_ratios": result.get("tail_ratios", [])[-3:]},
                                digits_matched=len(numbers),
                            )
                            info(f"  [{h.domain}] mpmath verified partition ratios (k={k})")
                except Exception as e:
                    info(f"  [{h.domain}] mpmath check skipped: {e}")

        # Symbolic check if prediction contains equality
        if HAS_SYMPY and "=" in h.testable_prediction:
            lhs_rhs = h.testable_prediction.split("=")
            if len(lhs_rhs) == 2:
                expr = f"({lhs_rhs[0]}) - ({lhs_rhs[1]})"
                sym_result = toolbox.grounded.verify_symbolic(expr)
                if sym_result.get("is_zero"):
                    info(f"  [{h.domain}] SymPy: equality verified symbolically")
                    if exec_result is None:
                        exec_result = ExecutionResult(
                            hypothesis_id=h.id, success=True,
                            method="symbolic_sympy",
                            proof_status="complete",
                            evidence={"sympy": sym_result},
                        )

        # Apply score adjustments
        if exec_result is not None:
            adj = toolbox.grounded.score_adjustments_from_evidence(h, exec_result)
            for axis, delta in adj.items():
                if axis in h.scores:
                    h.scores[axis] = max(0.0, min(1.0, h.scores[axis] + delta))
            if adj:
                info(f"  [{h.domain}] Score adjustments: {adj}")

    return hypotheses


# ══════════════════════════════════════════════════════════════════════════
# MAIN AGENT
# ══════════════════════════════════════════════════════════════════════════

class UnifiedBreakthroughAgent:
    """
    Unified agent combining V8 evolutionary discovery with self_iterating_agent
    research cycle, plus all 5 upgrades.
    """

    def __init__(self, api_base: str = None, api_key: str = None,
                 model: str = "claude-sonnet-4-20250514"):
        self.api_base = api_base or os.environ.get("API_BASE", "https://api.anthropic.com")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY",
                                                   os.environ.get("OPENAI_API_KEY", ""))
        self.model = model

        # Core subsystems
        self.memory = SemanticMemory(MEMORY_FILE)
        self.toolbox = VerificationToolbox(self.memory)
        self.knowledge = KnowledgeGraph(self.memory)
        self.axiom_graph = AxiomGraph(AXIOM_GRAPH_PATH)
        self.serendipity = SerendipityEngine(PATTERNS_PATH)
        self.failure_archive = FailureArchive(FAILURE_ARCHIVE_PATH)
        self.genomes = GenomeLibrary()
        self.state = AgentState.load()

        if not self.state.session_id:
            self.state.session_id = str(uuid.uuid4())[:8]

        STATE_DIR.mkdir(parents=True, exist_ok=True)

    # ── API wrappers ────────────────────────────────────────────────────

    def _call(self, system: str, user: str, max_tokens: int = 2000,
              temperature: float = 0.8) -> str:
        return call_api(system, user, api_base=self.api_base, api_key=self.api_key,
                        model=self.model, max_tokens=max_tokens, temperature=temperature)

    # ── Phase 1: Frontier identification ───────────────────────────────

    def phase_identify_frontier(self) -> Optional[FrontierGap]:
        header("Phase 1 — Frontier Identification")
        ranked = self.knowledge.rank_gaps()
        gap = self.knowledge.select_target()
        if gap is None:
            warn("All frontier gaps resolved or exhausted")
            return None
        ok(f"Target gap: [{gap.gap_type}] {gap.id}")
        info(f"  {gap.description[:120]}")
        info(f"  score={gap.score:.3f}  priority={gap.priority:.2f}  "
             f"feasibility={gap.feasibility:.2f}  attempts={gap.attempts}")
        return gap

    # ── Phases 2-4: Population + verification + evaluation ─────────────

    def phase_execute(self, gap: FrontierGap) -> list[Hypothesis]:
        """Generate population, apply grounded verification, then adversarial filter."""
        genome = self.genomes.active()

        # Phase 2: Generate population
        hypotheses = generate_population(
            self.state, gap, self.axiom_graph, self.serendipity,
            genome, self.memory,
            api_base=self.api_base, api_key=self.api_key, model=self.model)

        if not hypotheses:
            return []

        # Phase 3: Grounded verification (adjusts scores before LLM critic)
        hypotheses = apply_grounded_scoring(hypotheses, self.toolbox, gap)

        # Phase 4: Adversarial evaluation
        hypotheses = adversarial_filter(
            self.state, hypotheses, genome, self.failure_archive,
            api_base=self.api_base, api_key=self.api_key, model=self.model)

        return hypotheses

    # ── Phase 5: Dependency propagation ────────────────────────────────

    def phase_propagate(self, hypotheses: list[Hypothesis], gap: FrontierGap):
        """★ Unlock downstream gaps when a breakthrough is found."""
        header("Phase 5 — Dependency Propagation")
        breakthroughs = [h for h in hypotheses
                         if h.status != "killed"
                         and h.tier in ("BREAKTHROUGH_CANDIDATE", "CONDITIONAL_BREAKTHROUGH")]
        if breakthroughs:
            self.knowledge.propagate_unlock(gap.id)
            for h in breakthroughs:
                self.memory.add_entry(
                    "discovery",
                    f"[{h.tier}] {h.claim}",
                    {"gap_id": gap.id, "b_score": h.b_score(),
                     "domain": h.domain, "genome_id": h.genome_id})
                star(f"BREAKTHROUGH: {h.claim[:100]}...")
            self.state.breakthroughs += len(breakthroughs)
        else:
            info("No breakthroughs this cycle — no dependency unlock")

        # Record all survivors as memory entries
        survivors = [h for h in hypotheses if h.status != "killed"]
        for h in survivors:
            if h.b_score() > 0.1:
                self.memory.add_entry(
                    "insight",
                    f"{h.claim} [B={h.b_score():.3f}]",
                    {"gap_id": gap.id, "domain": h.domain})

    # ── Phase 6: Synthesis / recombination ─────────────────────────────

    def phase_synthesize(self, hypotheses: list[Hypothesis]) -> list[Hypothesis]:
        """Recombine top survivors across domains (from V8 Layer 6)."""
        header("Phase 6 — Synthesis Chamber")
        survivors = [h for h in hypotheses if h.status != "killed"]
        alive = self.axiom_graph.get_alive_nodes()

        if len(survivors) < 2 or not alive:
            info("Insufficient material for recombination")
            return hypotheses

        # Pick top 2 survivors + 1 stored axiom from a different domain
        survivors_sorted = sorted(survivors, key=lambda h: h.b_score(), reverse=True)
        h1 = survivors_sorted[0]
        foreign = [n for n in alive if n.domain != h1.domain]
        if survivors_sorted[1:] and foreign:
            h2 = survivors_sorted[1]
            ax = random.choice(foreign)
            synth_id = str(uuid.uuid4())[:12]
            synth = Hypothesis(
                id=synth_id,
                claim=f"[SYNTHESIS] {h1.domain}×{ax.domain}: {h1.claim[:80]} — "
                      f"applied via {ax.text[:60]}",
                mechanism=f"Bridge: {h1.mechanism[:100]} || {ax.text[:100]}",
                testable_prediction=h1.testable_prediction,
                domain=f"{h1.domain}×{ax.domain}",
                domains_touched=list(set(h1.domains_touched + [ax.domain])),
                scores={"N": min(1.0, h1.scores.get("N", 0.5) + 0.05),
                        "F": h1.scores.get("F", 0.5),
                        "E": max(h1.scores.get("E", 0.5), 0.5),
                        "C": min(1.0, h1.scores.get("C", 0.5) + 0.05)},
                parent_ids=[h1.id, ax.id],
                generation=self.state.iteration,
                temperature_tier="recombination",
                created_at=datetime.now().isoformat(),
            )
            hypotheses.append(synth)
            info(f"  Synthesis: {synth.claim[:100]}...")
        return hypotheses

    # ── Phase 7: Axiom graph update ─────────────────────────────────────

    def phase_update_graph(self, hypotheses: list[Hypothesis],
                           injected_pattern: Optional[dict] = None):
        """Update axiom graph with survivors and edges (from V8 Layer 7)."""
        header("Phase 7 — Axiom Graph Update")
        survivors = [h for h in hypotheses if h.status != "killed"]
        self.axiom_graph.apply_decay()

        for h in survivors:
            node = AxiomNode(
                id=h.id, text=h.claim, domain=h.domain,
                domains_touched=h.domains_touched,
                confidence=h.plausibility,
                novelty_score=h.surprise_if_true,
                generation=h.generation,
                session_id=self.state.session_id,
                status="alive",
                parent_ids=h.parent_ids,
                falsification_attempts=0,
                scores=h.scores,
                tier=h.tier,
                counter_hypothesis=h.counter_hypothesis,
                falsification_evidence=h.falsification.get("logical_attack", ""),
                experimental_protocol=h.experimental_protocol,
                created_at=h.created_at,
            )
            self.axiom_graph.add_node(node)

            # Edges: parent links
            for pid in h.parent_ids:
                if pid in self.axiom_graph.nodes:
                    self.axiom_graph.add_edge(pid, h.id, "derives_from")
                    self.axiom_graph.reinforce(pid)

            # Edge: serendipity
            if h.serendipity_pattern and injected_pattern:
                self.axiom_graph.add_edge(injected_pattern.get("id", ""), h.id, "seeded_by", 0.8)

        # Archive killed
        killed = [h for h in hypotheses if h.status == "killed"]
        for h in killed:
            if h.id in self.axiom_graph.nodes:
                self.axiom_graph.nodes[h.id].status = "falsified"
                self.axiom_graph.nodes[h.id].falsification_evidence = \
                    h.falsification.get("logical_attack", "kill floor")

        self.axiom_graph.save()
        stats = self.axiom_graph.stats()
        ok(f"Graph: {stats['alive']} alive, {stats['falsified']} falsified, "
           f"{stats['edges']} edges")

    # ── Phase 8: Genome evolution ────────────────────────────────────────

    def phase_evolve_genome(self, hypotheses: list[Hypothesis]):
        """★ Prompt genome: mutate on breakthrough, crossbreed on stagnation."""
        header("Phase 8 — Genome Evolution")
        breakthroughs = [h for h in hypotheses
                         if h.tier in ("BREAKTHROUGH_CANDIDATE", "CONDITIONAL_BREAKTHROUGH")]
        if breakthroughs:
            best = max(breakthroughs, key=lambda h: h.b_score())
            new_genome = self.genomes.clone_and_mutate(
                self.genomes.active(), best.b_score(),
                f"Breakthrough in {best.domain} at iter {self.state.iteration}")
            info(f"Genome evolved to v{new_genome.version}: {new_genome.id}")

        elif self.state.is_stagnant():
            new_genome = self.genomes.crossbreed(self.state.stagnation_count)
            info(f"Genome crossbred (stagnation rescue): {new_genome.id}")
        else:
            info(f"Genome unchanged: {self.genomes.active().id} (v{self.genomes.active().version})")

    # ── Phase 9: Summarize + persist ────────────────────────────────────

    def phase_summarize(self, gap: FrontierGap, hypotheses: list[Hypothesis],
                        duration: float) -> IterationRecord:
        """Update state, log iteration, save everything."""
        header("Phase 9 — Summarize & Persist")

        survivors = [h for h in hypotheses if h.status != "killed"]
        best_b = max((h.b_score() for h in survivors), default=0.0)
        self.state.b_history.append(best_b)

        # Delta-novelty for stagnation tracking
        if survivors:
            avg_surprise = sum(h.surprise_if_true for h in survivors) / len(survivors)
            alive = self.axiom_graph.get_alive_nodes()
            graph_avg = (sum(n.novelty_score for n in alive) / len(alive)) if alive else 0.5
            delta = abs(avg_surprise - graph_avg)
        else:
            delta = 0.0
        self.state.delta_novelty_history.append(delta)

        # Stagnation counter
        if self.state.is_stagnant():
            self.state.stagnation_count += 1
            warn(f"Stagnation cycle {self.state.stagnation_count}")
        else:
            self.state.stagnation_count = 0

        # Verdicts
        bt_count = sum(1 for h in survivors
                       if h.tier in ("BREAKTHROUGH_CANDIDATE", "CONDITIONAL_BREAKTHROUGH"))
        if bt_count:
            verdict = "breakthrough"
        elif best_b >= BREAKTHROUGH_THRESHOLD * 0.5:
            verdict = "progress"
        elif survivors:
            verdict = "inconclusive"
        else:
            verdict = "failure"

        self.state.iteration += 1
        self.state.cycle_count += 1
        self.state.total_runtime += duration
        self.state.all_hypotheses_count += len(hypotheses)
        self.state.domain_rotation_idx += 1
        if not survivors:
            self.state.failures += 1

        record = IterationRecord(
            iteration=self.state.iteration,
            timestamp=datetime.now().isoformat(),
            gap_id=gap.id,
            hypothesis_id=survivors[0].id if survivors else "",
            verdict=verdict,
            b_score=best_b,
            summary=f"{gap.id}: {verdict} (B={best_b:.3f}, {len(survivors)} survivors)",
            duration_seconds=duration,
        )

        self.state.iteration_history.append(asdict(record))
        self.state.save()
        self.memory.save()
        self.failure_archive.save()

        # Append to discovery report
        if verdict == "breakthrough":
            REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(REPORT_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Iteration {self.state.iteration} — {record.timestamp}\n")
                f.write(f"Gap: {gap.id} | B={best_b:.4f}\n")
                for h in survivors:
                    if h.tier in ("BREAKTHROUGH_CANDIDATE", "CONDITIONAL_BREAKTHROUGH"):
                        f.write(f"★ [{h.tier}] {h.claim}\n")
                        f.write(f"  Prediction: {h.testable_prediction}\n\n")

        ok(f"Iteration {self.state.iteration} complete: {verdict} | "
           f"B={best_b:.3f} | Δnov={delta:.3f} | runtime={duration:.1f}s")
        return record

    # ── Main cycle ────────────────────────────────────────────────────

    def run_cycle(self) -> Optional[IterationRecord]:
        """Execute one complete 10-phase research cycle."""
        if not self.api_key:
            err("No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")
            return None

        t_start = time.time()
        gen = self.state.iteration + 1

        print(f"\n{C.BOLD}{C.CYAN}{'═'*70}")
        print(f"  UNIFIED BREAKTHROUGH AGENT  |  Cycle {gen}  |  "
              f"{datetime.now().strftime('%H:%M:%S')}")
        print(f"  Model: {self.model}  |  Genome: {self.genomes.active().id} "
              f"v{self.genomes.active().version}")
        print(f"{'═'*70}{C.RESET}")

        # Phase 0: Serendipity check (handled inside generate_population)

        # Phase 1: Frontier identification
        gap = self.phase_identify_frontier()
        if gap is None:
            warn("No frontier gap available — consider adding new gaps or resetting")
            return None

        # Phases 2-4: Population + grounded verification + adversarial filter
        hypotheses = self.phase_execute(gap)
        if not hypotheses:
            err("No hypotheses generated")
            return None

        # Phase 5: Dependency propagation
        self.phase_propagate(hypotheses, gap)

        # Phase 6: Synthesis
        hypotheses = self.phase_synthesize(hypotheses)

        # Phase 7: Axiom graph update
        injected = None
        if self.state.serendipity_injections:
            last_inj = self.state.serendipity_injections[-1]
            if last_inj.get("iteration") == gen - 1:
                for p in self.serendipity.patterns:
                    if p.get("name") == last_inj.get("pattern"):
                        injected = p
                        break
        self.phase_update_graph(hypotheses, injected)

        # Phase 8: Genome evolution
        self.phase_evolve_genome(hypotheses)

        # Phase 9: Summarize
        duration = time.time() - t_start
        record = self.phase_summarize(gap, hypotheses, duration)
        return record

    # ── Failure archaeology ────────────────────────────────────────────

    def run_archaeology(self):
        """Re-examine failures in light of new axioms (from V8)."""
        header("Failure Archaeology")
        ARCHAEOLOGY_SYSTEM = """You are the Failure Archaeologist. Re-examine previously
falsified hypotheses in light of newly discovered axioms.
Output ONLY valid JSON (no markdown fences):
{"resurrections": [{"original_id": "id", "modified_claim": "updated claim",
 "what_changed": "why now viable", "testable_prediction": "new prediction",
 "confidence": 0.0-1.0}]}
If nothing should be resurrected, return {"resurrections": []}.
"""
        candidates = self.failure_archive.get_candidates_for_resurrection()
        if not candidates:
            info("No candidates for resurrection")
            return
        recent_axioms = self.axiom_graph.get_seed_candidates(k=5)
        prompt = (f"Failures: {json.dumps(candidates[:5], indent=2)}\n\n"
                  f"New axioms:\n{format_axiom_nodes(recent_axioms, 'NEW')}")
        try:
            raw = self._call(ARCHAEOLOGY_SYSTEM, prompt, max_tokens=1500, temperature=0.7)
            data = parse_json_response(raw)
            for r in data.get("resurrections", []):
                ok(f"Resurrected: {r.get('modified_claim', '')[:100]}...")
                for f in self.failure_archive.failures:
                    if f["id"] == r.get("original_id"):
                        f["resurrection_attempts"] += 1
                        f["resurrected"] = True
            self.failure_archive.save()
        except Exception as e:
            warn(f"Archaeology error: {e}")

    # ── CLI display methods ─────────────────────────────────────────────

    def show_status(self):
        header("Agent Status")
        print(f"  Version:       {VERSION}")
        print(f"  Iteration:     {self.state.iteration}")
        print(f"  Cycles:        {self.state.cycle_count}")
        print(f"  Breakthroughs: {self.state.breakthroughs}")
        print(f"  Failures:      {self.state.failures}")
        print(f"  Total Runtime: {self.state.total_runtime:.1f}s")
        print(f"  Active Genome: {self.genomes.active().id} "
              f"v{self.genomes.active().version}")
        print(f"  Genome Count:  {len(self.genomes.genomes)}")
        print()
        print("  Category Credibility:")
        for cat, cred in sorted(self.state.category_credibility.items()):
            bar = "#" * int(cred * 20) + "." * (20 - int(cred * 20))
            print(f"    {cat:15s} [{bar}] {cred:.2f}")
        print()
        print("  Semantic Memory Backend:")
        if self.memory._chroma_collection:
            print(f"    ChromaDB + sentence-transformers")
        elif self.memory._encoder:
            print(f"    numpy cosine similarity")
        else:
            print(f"    keyword fallback")
        print(f"  Memory Entries: {len(self.memory.entries)}")
        print(f"  Failure Patterns: {len(self.memory.failure_signatures)}")
        print()
        print("  Tool Status:")
        for name, status in self.toolbox.status().items():
            sym = f"{C.GREEN}✓{C.RESET}" if status == "available" else f"{C.RED}✗{C.RESET}"
            print(f"    {sym} {name}: {status}")

    def show_frontier(self):
        header("Frontier Map")
        gaps = self.knowledge.rank_gaps()
        for gap in gaps:
            resolved = "DONE" if gap.id in self.knowledge.resolved_gaps else ""
            prereq_str = f"← needs {gap.prerequisites}" if gap.prerequisites else ""
            marker = "★" if gap.score > 0.5 else "◆" if gap.score > 0.3 else "○"
            status = resolved or ("ATTEMPT×" + str(gap.attempts) if gap.attempts > 0 else "NEW")
            print(f"  {marker} [{gap.score:.3f}] {gap.id:22s} | {gap.gap_type:12s} | "
                  f"{status:8s} {prereq_str}")
            print(f"         {gap.description[:80]}...")

    def show_history(self):
        header("Iteration History")
        for rec in self.state.iteration_history[-20:]:
            ts = rec.get("timestamp", "?")[:19]
            verdict = rec.get("verdict", "?")
            b = rec.get("b_score", 0)
            summary = rec.get("summary", "")[:80]
            sym = {"breakthrough": "★", "progress": "◆",
                   "failure": "✗", "inconclusive": "?"}.get(verdict, "?")
            print(f"  {sym} [{ts}] B={b:.4f} | {summary}")

    def show_graph_stats(self):
        header("Axiom Graph Statistics")
        stats = self.axiom_graph.stats()
        print(f"  Total nodes:  {stats['total']}")
        print(f"  Alive:        {stats['alive']}")
        print(f"  Falsified:    {stats['falsified']}")
        print(f"  Dormant:      {stats['dormant']}")
        print(f"  Edges:        {stats['edges']}")
        print(f"  Domains:      {', '.join(stats['domains']) if stats['domains'] else 'none'}")
        top = self.axiom_graph.get_seed_candidates(k=5)
        if top:
            print(f"\n  Top nodes (conf × novelty):")
            for n in top:
                print(f"    [{n.domain}] conf={n.confidence:.3f} nov={n.novelty_score:.2f} "
                      f"B={n.b_score():.3f}: {n.text[:80]}")

    def propose_genome_mutation(self):
        header("Genome Mutation Proposals")
        genome = self.genomes.active()
        history = self.state.iteration_history[-20:]
        successes = sum(1 for r in history if r.get("verdict") == "breakthrough")
        failures = sum(1 for r in history if r.get("verdict") == "failure")
        total = len(history)
        print(f"  Active genome: {genome.id} v{genome.version}")
        print(f"  History: {successes} breakthroughs, {failures} failures / {total} cycles")
        print(f"  Mutation note: {genome.mutation_notes}")
        print()
        if self.state.is_stagnant():
            warn("STAGNATION detected — crossbreed recommended")
            print("  Run: python unified_breakthrough_agent.py --cycles 1  (will auto-crossbreed)")
        elif successes / max(total, 1) > 0.3:
            ok("Strong performance — genome mutation on next breakthrough")
        else:
            info("No mutation proposed. Need more iteration data.")
        print(f"\n  Genome lineage:")
        for g in self.genomes.genomes[-5:]:
            sym = "►" if g.id == genome.id else " "
            print(f"  {sym} {g.id} v{g.version}  B={g.b_score_when_created:.3f}  {g.mutation_notes[:60]}")

    def rollback(self, to_iteration: int) -> bool:
        snap_dir = SNAPSHOTS_DIR / f"iter_{to_iteration:04d}"
        if not snap_dir.exists():
            err(f"No snapshot for iteration {to_iteration}")
            return False
        for fname in ["agent_state.json", "memory.json"]:
            src = snap_dir / fname
            if src.exists():
                shutil.copy2(src, STATE_DIR / fname)
        ok(f"Rolled back to iteration {to_iteration}")
        return True

    def take_snapshot(self):
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snap_dir = SNAPSHOTS_DIR / f"iter_{self.state.iteration:04d}"
        snap_dir.mkdir(parents=True, exist_ok=True)
        for src in [STATE_FILE, MEMORY_FILE]:
            if src.exists():
                shutil.copy2(src, snap_dir / src.name)
        ok(f"Snapshot: iter_{self.state.iteration:04d}")


# ══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"Unified Breakthrough Agent v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python unified_breakthrough_agent.py                  # Run 1 cycle
  python unified_breakthrough_agent.py --cycles 5       # Run 5 cycles
  python unified_breakthrough_agent.py --status         # Show state
  python unified_breakthrough_agent.py --frontier       # Frontier map
  python unified_breakthrough_agent.py --history        # Iteration log
  python unified_breakthrough_agent.py --mutate         # Genome proposals
  python unified_breakthrough_agent.py --rollback 3     # Rollback to iter 3
  python unified_breakthrough_agent.py --reset          # Wipe all state
  python unified_breakthrough_agent.py --show-graph     # Axiom graph stats
  python unified_breakthrough_agent.py --archaeology    # Resurrect failures
  python unified_breakthrough_agent.py --mode "Physics/Math" --target "Scaling Laws"
        """)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--frontier", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--mutate", action="store_true")
    parser.add_argument("--rollback", type=int, metavar="N")
    parser.add_argument("--show-graph", action="store_true")
    parser.add_argument("--archaeology", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--mode", type=str, default="Generic Research")
    parser.add_argument("--target", type=str, default="Autonomous Discovery")
    parser.add_argument("--api-base", type=str,
                        default=os.environ.get("API_BASE", "https://api.anthropic.com"))
    parser.add_argument("--api-key", type=str,
                        default=os.environ.get("ANTHROPIC_API_KEY",
                               os.environ.get("OPENAI_API_KEY", "")))
    parser.add_argument("--model", type=str,
                        default=os.environ.get("MODEL", "claude-sonnet-4-20250514"))

    # Normalise en-dash / em-dash typed by some terminals/paste
    import unicodedata
    sys.argv = [
        a.replace("\u2013", "--").replace("\u2014", "--")
        for a in sys.argv
    ]
    args = parser.parse_args()

    if args.reset:
        confirm = input("Reset all agent state? [y/N] ")
        if confirm.lower() == "y":
            for p in [STATE_DIR, AXIOM_GRAPH_PATH, FAILURE_ARCHIVE_PATH,
                      EVOLVED_PATTERNS_PATH, GENEALOGY_PATH]:
                if Path(str(p)).exists():
                    if Path(str(p)).is_dir():
                        shutil.rmtree(p)
                    else:
                        Path(str(p)).unlink()
            ok("State reset.")
        else:
            info("Reset cancelled.")
        return

    agent = UnifiedBreakthroughAgent(
        api_base=args.api_base,
        api_key=args.api_key,
        model=args.model,
    )

    if args.status:
        agent.show_status()
    elif args.frontier:
        agent.show_frontier()
    elif args.history:
        agent.show_history()
    elif args.mutate:
        agent.propose_genome_mutation()
    elif args.rollback is not None:
        agent.rollback(args.rollback)
    elif args.show_graph:
        agent.show_graph_stats()
    elif args.archaeology:
        agent.run_archaeology()
    else:
        n_cycles = min(args.cycles, MAX_CYCLES)
        if n_cycles > 10:
            warn(f"Running {n_cycles} cycles — this may take a while")

        print(f"\n{C.BOLD}{C.PURPLE}{'═'*70}")
        print(f"  UNIFIED BREAKTHROUGH AGENT v{VERSION}")
        print(f"  Mode: {args.mode}  |  Target: {args.target}")
        print(f"  Model: {args.model}  |  Cycles: {n_cycles}")
        print(f"{'═'*70}{C.RESET}")

        for i in range(n_cycles):
            try:
                agent.take_snapshot()
                agent.run_cycle()
                if i < n_cycles - 1:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                warn("Interrupted by user")
                agent.state.save()
                agent.memory.save()
                break
            except Exception as e:
                err(f"Cycle failed: {e}")
                traceback.print_exc()
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

        # Save genealogy
        genealogy = agent.axiom_graph.get_genealogy()
        GENEALOGY_PATH.write_text(
            json.dumps(genealogy, ensure_ascii=False, indent=2), encoding="utf-8")
        ok(f"Genealogy: {GENEALOGY_PATH}")

        agent.show_status()


if __name__ == "__main__":
    main()
