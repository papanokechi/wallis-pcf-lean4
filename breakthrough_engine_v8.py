#!/usr/bin/env python3
"""
Breakthrough Engine V8.5 — Evolutionary Autonomous Discovery System
===================================================================

12-Layer Architecture (V8 + Upgrade Manifesto Phase 2):
  Layer 0:   Serendipity Injection        — random walk on knowledge graph
  Layer 1:   Ingestion / Seed Context     — memory + cross-domain assembly
  Layer 2:   Encoder / Context Compress   — novelty-gradient preserving
  Layer 3:   Conjecture Engine (Producer) — multi-temperature ensemble
  Layer 4:   Adversarial Falsifier        — ARCHITECTURALLY ISOLATED
  Layer 5:   Formal / Computational Verifier
  Layer 5.5: Reality-Sync                 — auto-generates validation scripts
  Layer 6:   Synthesis Chamber            — 3-way cross-domain conceptual blending
  Layer 6.5: Paradigm Shift Detector      — auto-resurrects on new axioms
  Layer 7:   Axiom Graph Updater          — persistent networkx graph
  Layer 8:   Synthesis & Iteration Controller — delta-novelty + stagnation
  Layer 9:   Pattern Evolver              — discovers new structural patterns

Key design principles:
  • Context Isolation: adversarial agent has NO access to producer reasoning
  • Evolution, Not Pipeline: variation + selection + inheritance + mutation
  • Persistent Epistemic State: axiom graph survives across sessions
  • Stagnation Detection: delta-novelty triggers serendipity injection
  • Reality-Sync: hypotheses generate their own validation micro-experiments
  • Dynamic Patterns: pattern library evolves from successful discoveries

Usage:
  python breakthrough_engine_v8.py
  python breakthrough_engine_v8.py --mode "Physics/Math" --target "Scaling Laws" --iters 10
  python breakthrough_engine_v8.py --data v8-run.json   # Agent mode (no API)
  python breakthrough_engine_v8.py --show-graph          # Show axiom graph stats
  python breakthrough_engine_v8.py --archaeology         # Run failure archaeology
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
import random
import html as html_mod
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Optional dependencies ──────────────────────────────────────────────
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

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("WARNING: networkx not installed. Axiom graph will use fallback dict storage.")
    print("  pip install networkx")

import urllib.request
import urllib.error

# ── Constants ──────────────────────────────────────────────────────────
VERSION = "8.5"
PATTERNS_PATH = Path(__file__).parent / "structural_patterns.json"
AXIOM_GRAPH_PATH = Path("axiom_graph.json")
FAILURE_ARCHIVE_PATH = Path("failure_archive.json")
REPORT_PATH = Path("v8_discovery_report.md")
GENEALOGY_PATH = Path("v8_genealogy.json")

# ── Scoring (inherited from V7, evolved) ──────────────────────────────
SCORING_RUBRIC = {
    "N": {
        0.9: "No close prior work; fundamentally new framing",
        0.8: "Closest work differs in mechanism or domain; clear delta",
        0.7: "Extends known work with genuinely new quantitative prediction",
        0.6: "Incremental advance; framing new but mechanism known",
        0.4: "Reframes existing result; novelty mostly presentational",
        0.2: "Directly overlaps published work",
    },
    "F": {
        0.9: "Predicts specific number ± tolerance; wrong value kills theory",
        0.8: "Predicts qualitative structure with clear test",
        0.7: "Directional prediction testable with standard benchmarks",
        0.6: "Testable in principle but requires bespoke setup",
        0.4: "Vague prediction; hard to distinguish from null",
        0.2: "Unfalsifiable or circular",
    },
    "E": {
        0.9: "Experiment runnable with public models + code; < 1 week",
        0.8: "Runnable with public models; standard benchmarks; < 2 weeks",
        0.7: "Requires moderate compute or restricted model access",
        0.6: "Requires significant compute (>$10K) or multiple runs",
        0.5: "Requires new infrastructure or measurement tools",
        0.3: "Purely theoretical; no clear path to test",
    },
    "C": {
        0.9: "Single mechanism explains 5+ unrelated observations",
        0.8: "Explains 3-4 observations or reduces parameters significantly",
        0.7: "Explains 2 observations better than existing theory",
        0.6: "Explains one observation with simpler mechanism",
        0.4: "Single-phenomenon explanation; no compression advantage",
        0.2: "Ad hoc; as many parameters as it explains",
    },
}

KILL_FLOOR = {"N": 0.50, "F": 0.55, "E": 0.35, "C": 0.40}
BT_THRESHOLDS = {"N": 0.70, "F": 0.80, "E": 0.65, "C": 0.60}

# Stagnation detection
STAGNATION_WINDOW = 3          # consecutive low-delta cycles
DELTA_NOVELTY_THRESHOLD = 0.15  # below this = stalling

# Multi-temperature ensemble
TEMPERATURES = {
    "conservative": 0.3,   # rigorous, incremental
    "balanced":     0.8,   # normal creative
    "wild":         1.3,   # lateral, high surprise
}

# Domain rotation
DOMAIN_ROTATION = [
    "physics", "mathematics", "biology", "computer_science",
    "economics", "neuroscience", "chemistry", "engineering",
]


# ══════════════════════════════════════════════════════════════════════════
# ANSI COLORS
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
# AXIOM GRAPH — Persistent Knowledge Graph (Layer 7)
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
    status: str = "alive"          # alive / falsified / dormant / archived
    parent_ids: list = field(default_factory=list)
    falsification_attempts: int = 0
    scores: dict = field(default_factory=dict)  # {"N":, "F":, "E":, "C":}
    tier: str = ""
    counter_hypothesis: str = ""   # generated when falsified
    falsification_evidence: str = ""
    experimental_protocol: dict = field(default_factory=dict)
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def b_score(self):
        s = self.scores
        return s.get("N", 0) * s.get("F", 0) * s.get("E", 0) * s.get("C", 0)


class AxiomGraph:
    """Persistent knowledge graph with confidence decay and cross-domain retrieval."""

    EDGE_TYPES = [
        "derives_from", "contradicts", "strengthens",
        "analogous_to", "recombined_to", "seeded_by", "domain_bridge",
    ]

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
                ok(f"Axiom graph loaded: {len(self.nodes)} nodes, {len(self.edges)} edges")
            except Exception as e:
                warn(f"Failed to load axiom graph: {e}. Starting fresh.")

    def save(self):
        data = {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": self.edges,
            "meta": {
                "version": VERSION,
                "saved_at": datetime.now().isoformat(),
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def add_node(self, node: AxiomNode):
        self.nodes[node.id] = node
        return node.id

    def add_edge(self, src: str, dst: str, edge_type: str, weight: float = 1.0):
        self.edges.append({
            "src": src, "dst": dst, "type": edge_type,
            "weight": weight, "created_at": datetime.now().isoformat(),
        })

    def apply_decay(self, rate: float = 0.005):
        """Confidence fades each session unless reinforced."""
        for node in self.nodes.values():
            if node.status == "alive":
                node.confidence *= (1 - rate)

    def reinforce(self, node_id: str, boost: float = 0.05):
        """Boost confidence when a node is re-verified or referenced."""
        if node_id in self.nodes:
            n = self.nodes[node_id]
            n.confidence = min(1.0, n.confidence + boost)
            n.falsification_attempts += 1

    def get_alive_nodes(self, domain: str = None) -> list[AxiomNode]:
        nodes = [n for n in self.nodes.values() if n.status == "alive"]
        if domain:
            nodes = [n for n in nodes if n.domain == domain
                     or domain in n.domains_touched]
        return nodes

    def get_seed_candidates(self, domain: str = None, k: int = 5) -> list[AxiomNode]:
        """Top-k alive nodes by confidence × novelty."""
        nodes = self.get_alive_nodes(domain)
        nodes.sort(key=lambda n: n.confidence * n.novelty_score, reverse=True)
        return nodes[:k]

    def get_foreign_seeds(self, current_domain: str, k: int = 2) -> list[AxiomNode]:
        """Pull high-novelty nodes from domains OTHER than current."""
        foreign = [n for n in self.nodes.values()
                   if n.status == "alive"
                   and n.domain != current_domain
                   and n.novelty_score > 0.5]
        if len(foreign) <= k:
            return foreign
        return random.sample(foreign, k)

    def get_dormant_nodes(self, k: int = 5) -> list[AxiomNode]:
        """Retrieve falsified/dormant nodes for archaeology."""
        dormant = [n for n in self.nodes.values()
                   if n.status in ("falsified", "dormant")]
        dormant.sort(key=lambda n: n.novelty_score, reverse=True)
        return dormant[:k]

    def get_genealogy(self) -> list[dict]:
        """Return parent-child relationships for tree visualization."""
        tree = []
        for node in self.nodes.values():
            tree.append({
                "id": node.id,
                "text": node.text[:120],
                "domain": node.domain,
                "status": node.status,
                "confidence": node.confidence,
                "novelty": node.novelty_score,
                "generation": node.generation,
                "parents": node.parent_ids,
                "tier": node.tier,
                "b_score": node.b_score(),
            })
        return tree

    def stats(self) -> dict:
        alive = sum(1 for n in self.nodes.values() if n.status == "alive")
        falsified = sum(1 for n in self.nodes.values() if n.status == "falsified")
        dormant = sum(1 for n in self.nodes.values() if n.status == "dormant")
        domains = set(n.domain for n in self.nodes.values())
        return {
            "total": len(self.nodes),
            "alive": alive,
            "falsified": falsified,
            "dormant": dormant,
            "edges": len(self.edges),
            "domains": sorted(domains),
        }


# ══════════════════════════════════════════════════════════════════════════
# STRUCTURAL PATTERN LIBRARY (Layer 0: Serendipity)
# ══════════════════════════════════════════════════════════════════════════

class SerendipityEngine:
    """Manages cross-domain structural pattern injection."""

    def __init__(self, patterns_path=PATTERNS_PATH):
        self.patterns = []
        self.injection_history = []  # track which patterns led to breakthroughs
        self.pattern_scores = {}     # meta-learning: pattern_id -> avg breakthrough score
        self._load_patterns(patterns_path)

    def _load_patterns(self, path):
        if Path(path).exists():
            try:
                self.patterns = json.loads(Path(path).read_text(encoding="utf-8"))
                info(f"Loaded {len(self.patterns)} structural patterns")
            except Exception as e:
                warn(f"Could not load patterns: {e}")

    def inject(self, current_domain: str, stagnant: bool = False) -> dict | None:
        """Select a pattern for injection. Biased toward high-scoring patterns."""
        if not self.patterns:
            return None

        # Filter out patterns already used in last 5 injections
        recent_ids = {h["pattern_id"] for h in self.injection_history[-5:]}
        candidates = [p for p in self.patterns if p["id"] not in recent_ids]
        if not candidates:
            candidates = self.patterns

        # If stagnant, bias toward patterns from domains far from current
        if stagnant:
            candidates = [p for p in candidates
                          if current_domain not in p.get("origin", "").lower()]

        # Meta-learning bias: weight by historical success
        if self.pattern_scores:
            weighted = []
            for p in candidates:
                score = self.pattern_scores.get(p["id"], 0.5)
                weighted.append((p, score))
            # Softmax-ish selection
            total = sum(s for _, s in weighted)
            if total > 0:
                r = random.random() * total
                cumulative = 0
                for p, s in weighted:
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

    def record_outcome(self, pattern_id: str, b_score: float):
        """Meta-learning: update pattern success score."""
        if pattern_id not in self.pattern_scores:
            self.pattern_scores[pattern_id] = b_score
        else:
            # Exponential moving average
            old = self.pattern_scores[pattern_id]
            self.pattern_scores[pattern_id] = 0.7 * old + 0.3 * b_score

    def build_injection_prompt(self, pattern: dict, current_domain: str) -> str:
        return f"""
SERENDIPITY INJECTION:
The following structural pattern has produced breakthroughs in other fields:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern: {pattern['name']}
Core idea: {pattern['core']}
Originally from: {pattern['origin']}
Has appeared in: {', '.join(pattern.get('appeared_in', []))}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONSTRAINT: Your next conjecture MUST explore whether this pattern
applies — in modified form — to the domain of {current_domain}.
Do not force the analogy. If it genuinely fails, say why and what
would need to change about {current_domain} for it to apply.
""".strip()


# ══════════════════════════════════════════════════════════════════════════
# FAILURE ARCHIVE (for Archaeology)
# ══════════════════════════════════════════════════════════════════════════

class FailureArchive:
    """Stores and manages failed hypotheses for periodic re-examination."""

    def __init__(self, path=FAILURE_ARCHIVE_PATH):
        self.path = Path(path)
        self.failures = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.failures = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def save(self):
        self.path.write_text(json.dumps(self.failures, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def add(self, hypothesis_text: str, falsification_evidence: str,
            counter_hypothesis: str, node_id: str, generation: int):
        self.failures.append({
            "id": node_id,
            "text": hypothesis_text,
            "falsification_evidence": falsification_evidence,
            "counter_hypothesis": counter_hypothesis,
            "generation": generation,
            "resurrection_attempts": 0,
            "resurrected": False,
            "timestamp": datetime.now().isoformat(),
        })
        # Cap at 100
        if len(self.failures) > 100:
            self.failures = self.failures[-100:]
        self.save()

    def get_candidates_for_resurrection(self, k: int = 5) -> list[dict]:
        """Get failures most likely to benefit from re-examination."""
        eligible = [f for f in self.failures
                    if not f.get("resurrected", False)
                    and f.get("resurrection_attempts", 0) < 3]
        # Prefer those with interesting counter-hypotheses
        eligible.sort(key=lambda f: len(f.get("counter_hypothesis", "")), reverse=True)
        return eligible[:k]


# ══════════════════════════════════════════════════════════════════════════
# REALITY-SYNC ENGINE (Layer 5.5) — Auto-generate validation micro-scripts
# ══════════════════════════════════════════════════════════════════════════

REALITY_SYNC_PATH = Path("v8_reality_sync")

class RealitySyncEngine:
    """Generates and optionally executes small-scale validation scripts
    to provide immediate first-pass reality checks on hypotheses.

    For each hypothesis with E >= 0.70, generates a Python micro-experiment
    that tests the most accessible aspect of its prediction. Results are
    fed back into the scoring pipeline.
    """

    def __init__(self, output_dir=REALITY_SYNC_PATH):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results: list[dict] = []

    def generate_validation_script(self, hypothesis, gen: int) -> dict | None:
        """Generate a micro-validation script for a hypothesis.
        Returns script metadata dict or None if not applicable."""

        protocol = hypothesis.experimental_protocol
        if not protocol:
            return None

        # Only generate scripts for hypotheses with sufficient E score
        e_score = hypothesis.scores.get("E", 0)
        if e_score < 0.65:
            return None

        ptype = protocol.get("type", "").lower()
        claim_hash = hashlib.md5(hypothesis.claim[:100].encode()).hexdigest()[:8]
        script_name = f"validate_g{gen}_{claim_hash}.py"
        script_path = self.output_dir / script_name

        # Build a sandboxed validation script from the protocol
        description = protocol.get("description", "")
        expected_false = protocol.get("expected_result_if_false", "")
        expected_true = protocol.get("surprising_result_if_true", "")

        script = f'''#!/usr/bin/env python3
"""
Reality-Sync Micro-Validation — Auto-generated by Breakthrough Engine V8.5
Hypothesis: {hypothesis.claim[:200]}
Domain: {hypothesis.domain}
Protocol type: {ptype}
B-Score: {hypothesis.b_score():.4f}
Generated: {datetime.now().isoformat()}
"""
import json
import sys
from datetime import datetime

RESULT = {{
    "hypothesis_id": "{hypothesis.id}",
    "generation": {gen},
    "domain": "{hypothesis.domain}",
    "protocol_type": "{ptype}",
    "b_score": {hypothesis.b_score():.6f},
    "status": "pending",
    "validation_notes": [],
    "score_adjustments": {{}},
}}

def validate():
    """First-pass validation logic."""
    notes = RESULT["validation_notes"]

    # ── Structural checks ──────────────────────────────────────
    claim = """{hypothesis.claim[:500].replace('"', '\\"')}"""
    prediction = """{hypothesis.testable_prediction[:500].replace('"', '\\"')}"""
    protocol_desc = """{description[:500].replace('"', '\\"')}"""

    # Check 1: Does the prediction contain specific numbers?
    import re
    numbers = re.findall(r"[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?", prediction)
    if len(numbers) >= 2:
        notes.append(f"GOOD: Prediction contains {{len(numbers)}} specific numbers — quantitatively testable")
        RESULT["score_adjustments"]["F"] = 0.02  # slight boost
    elif len(numbers) == 1:
        notes.append(f"OK: Prediction contains 1 specific number")
    else:
        notes.append("WEAK: Prediction lacks specific numbers — less falsifiable")
        RESULT["score_adjustments"]["F"] = -0.03

    # Check 2: Does the protocol reference existing datasets/tools?
    known_datasets = ["CIFAR", "ImageNet", "HotpotQA", "MuSiQue", "HCP", "BioGRID",
                      "COSMIC", "gnomAD", "Pythia", "BLS", "FRED", "HMP",
                      "MetaHIT", "WIOD", "LIS", "MaveDB", "PFDB", "OSM"]
    found = [d for d in known_datasets if d.lower() in protocol_desc.lower()]
    if found:
        notes.append(f"GOOD: References known datasets: {{', '.join(found)}}")
        RESULT["score_adjustments"]["E"] = 0.03
    else:
        notes.append("NOTE: No standard datasets referenced — may need custom data collection")

    # Check 3: Internal consistency — does the mechanism support the prediction?
    mechanism = """{hypothesis.mechanism[:500].replace('"', '\\"')}"""
    # Simple keyword overlap check
    mech_words = set(mechanism.lower().split())
    pred_words = set(prediction.lower().split())
    overlap = len(mech_words & pred_words) / max(len(pred_words), 1)
    if overlap > 0.15:
        notes.append(f"GOOD: Mechanism-prediction coherence: {{overlap:.0%}} keyword overlap")
    else:
        notes.append(f"WARN: Low mechanism-prediction coherence: {{overlap:.0%}} — may be disconnected")
        RESULT["score_adjustments"]["C"] = -0.02

    # Check 4: Does the claim explicitly contradict established knowledge?
    contradicts = """{hypothesis.contradicts_axiom[:300].replace('"', '\\"')}"""
    if contradicts and contradicts.lower() != "none":
        notes.append(f"PARADIGM CHALLENGE: Contradicts '{{contradicts[:100]}}'")
        RESULT["score_adjustments"]["N"] = 0.02  # novelty boost for genuine paradigm challenge

    # Check 5: Computational feasibility quick-check
    if any(kw in protocol_desc.lower() for kw in ["python", "simulate", "compute", "download", "api"]):
        notes.append("GOOD: Protocol explicitly describes computational steps")
        RESULT["score_adjustments"]["E"] = RESULT["score_adjustments"].get("E", 0) + 0.02
    if any(kw in protocol_desc.lower() for kw in ["$10k", "$100k", "million", "years"]):
        notes.append("WARN: Protocol references high cost/time — E score may be inflated")
        RESULT["score_adjustments"]["E"] = RESULT["score_adjustments"].get("E", 0) - 0.05

    RESULT["status"] = "validated"
    RESULT["timestamp"] = datetime.now().isoformat()
    return RESULT

if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2))
'''

        script_path.write_text(script, encoding="utf-8")

        result = {
            "hypothesis_id": hypothesis.id,
            "script_path": str(script_path),
            "script_name": script_name,
            "protocol_type": ptype,
            "generated": True,
        }
        return result

    def execute_validation(self, script_path: str, timeout: int = 10) -> dict | None:
        """Execute a validation script in a sandboxed subprocess."""
        import subprocess
        try:
            script_abs = str(Path(script_path).resolve())
            proc = subprocess.run(
                [sys.executable, script_abs],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode == 0:
                return json.loads(proc.stdout)
            else:
                return {"status": "error", "stderr": proc.stderr[:500]}
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def apply_adjustments(self, hypothesis, validation_result: dict):
        """Apply score adjustments from validation back to hypothesis."""
        adjustments = validation_result.get("score_adjustments", {})
        for axis, delta in adjustments.items():
            if axis in hypothesis.scores:
                old = hypothesis.scores[axis]
                hypothesis.scores[axis] = max(0.0, min(1.0, old + delta))

        notes = validation_result.get("validation_notes", [])
        self.results.append({
            "hypothesis_id": hypothesis.id,
            "notes": notes,
            "adjustments": adjustments,
            "status": validation_result.get("status", "unknown"),
        })
        return notes


# ══════════════════════════════════════════════════════════════════════════
# PARADIGM SHIFT DETECTOR (Layer 6.5) — Auto-resurrect on new axioms
# ══════════════════════════════════════════════════════════════════════════

class ParadigmShiftDetector:
    """Monitors for major new axioms and automatically scans the
    FailureArchive for hypotheses that become viable under the new knowledge.

    A 'paradigm shift' is triggered when:
    1. A BREAKTHROUGH_CANDIDATE is added to the graph, OR
    2. A new axiom significantly contradicts an existing one, OR
    3. A new domain is first represented in the graph
    """

    def __init__(self):
        self.known_domains: set = set()
        self.last_bt_count: int = 0
        self.resurrection_log: list[dict] = []

    def check_for_paradigm_shift(self, state, axiom_graph, new_hypotheses) -> list[dict]:
        """Check if any new hypotheses constitute a paradigm shift.
        Returns list of shift events."""

        shifts = []

        # Check 1: New breakthrough candidates
        new_bts = [h for h in new_hypotheses
                   if h.status != "killed"
                   and h.tier in ("BREAKTHROUGH_CANDIDATE", "CONDITIONAL_BREAKTHROUGH")]
        if len(new_bts) > 0:
            for bt in new_bts:
                shifts.append({
                    "type": "breakthrough",
                    "trigger_id": bt.id,
                    "trigger_claim": bt.claim[:200],
                    "domain": bt.domain,
                    "b_score": bt.b_score(),
                })

        # Check 2: New domains appearing for the first time
        current_domains = set(n.domain for n in axiom_graph.nodes.values())
        for h in new_hypotheses:
            if h.domain and h.domain not in self.known_domains:
                shifts.append({
                    "type": "new_domain",
                    "domain": h.domain,
                    "trigger_id": h.id,
                    "trigger_claim": h.claim[:200],
                })
        self.known_domains = current_domains

        # Check 3: Axiom contradiction — new hypothesis explicitly contradicts existing
        for h in new_hypotheses:
            if h.contradicts_axiom and h.contradicts_axiom.lower() != "none":
                if h.status != "killed" and h.b_score() > 0.30:
                    shifts.append({
                        "type": "contradiction",
                        "trigger_id": h.id,
                        "contradicts": h.contradicts_axiom[:200],
                        "domain": h.domain,
                    })

        return shifts

    def scan_archive_for_resurrections(self, shifts, failure_archive,
                                       axiom_graph, gen) -> list[dict]:
        """Given paradigm shift events, scan the failure archive for
        hypotheses that might now be viable."""

        if not shifts or not failure_archive.failures:
            return []

        resurrections = []

        # Build a set of "new knowledge" keywords from shift triggers
        new_knowledge_keywords = set()
        for shift in shifts:
            claim = shift.get("trigger_claim", "")
            # Extract key content words (>5 chars, not stopwords)
            words = set(w.lower().strip(".,;:!?()[]{}\"'")
                        for w in claim.split()
                        if len(w) > 5)
            new_knowledge_keywords |= words

        # Scan each failure for relevance to new knowledge
        for failure in failure_archive.failures:
            if failure.get("resurrected"):
                continue
            if failure.get("resurrection_attempts", 0) >= 3:
                continue

            fail_text = failure.get("text", "")
            fail_evidence = failure.get("falsification_evidence", "")
            fail_words = set(w.lower().strip(".,;:!?()[]{}\"'")
                             for w in (fail_text + " " + fail_evidence).split()
                             if len(w) > 5)

            # Compute relevance: overlap between new knowledge and failure
            overlap = new_knowledge_keywords & fail_words
            relevance = len(overlap) / max(len(new_knowledge_keywords), 1)

            if relevance > 0.08:  # At least 8% keyword overlap
                # Check if any shift's domain matches the failure's domain
                shift_domains = {s.get("domain", "") for s in shifts}
                # Also extract domain from failure text heuristically
                for shift in shifts:
                    resurrection = {
                        "original_id": failure["id"],
                        "original_claim": fail_text[:200],
                        "trigger_shift": shift["type"],
                        "trigger_claim": shift.get("trigger_claim", "")[:200],
                        "relevance_score": relevance,
                        "shared_concepts": list(overlap)[:10],
                        "generation": gen,
                        "reason": (f"Paradigm shift ({shift['type']}) in "
                                   f"{shift.get('domain', '?')} may invalidate "
                                   f"original falsification evidence"),
                    }
                    resurrections.append(resurrection)

                    # Mark in archive
                    failure["resurrection_attempts"] = failure.get("resurrection_attempts", 0) + 1
                    break  # One resurrection per failure per cycle

        # Sort by relevance and cap
        resurrections.sort(key=lambda r: -r["relevance_score"])
        resurrections = resurrections[:3]  # Max 3 resurrections per cycle

        self.resurrection_log.extend(resurrections)
        return resurrections


# ══════════════════════════════════════════════════════════════════════════
# PATTERN EVOLUTION ENGINE (Layer 9) — Discovers new structural patterns
# ══════════════════════════════════════════════════════════════════════════

EVOLVED_PATTERNS_PATH = Path("evolved_patterns.json")

class PatternEvolver:
    """Analyzes successful hypotheses to discover and codify new
    structural patterns that can be injected into future generations.

    Process:
    1. Collect breakthrough-tier hypotheses
    2. Extract common structural motifs across multiple breakthroughs
    3. Codify as new patterns in the SerendipityEngine format
    4. Persist to evolved_patterns.json and merge with library
    """

    def __init__(self, patterns_path=EVOLVED_PATTERNS_PATH):
        self.path = Path(patterns_path)
        self.evolved: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.evolved = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def save(self):
        self.path.write_text(
            json.dumps(self.evolved, ensure_ascii=False, indent=2),
            encoding="utf-8")

    def extract_patterns(self, breakthroughs: list, all_hypotheses: list,
                         axiom_graph) -> list[dict]:
        """Analyze breakthroughs to extract new structural patterns."""
        if len(breakthroughs) < 2:
            return []

        new_patterns = []

        # Strategy 1: Find domain-bridging motifs
        # If the same structural concept appears in breakthroughs from 2+ domains
        domain_claims = {}
        for bt in breakthroughs:
            dom = bt.get("domain", "unknown")
            claim = bt.get("claim", "")
            if dom not in domain_claims:
                domain_claims[dom] = []
            domain_claims[dom].append(claim)

        if len(domain_claims) >= 2:
            # Extract common structural words across domains
            domain_word_sets = {}
            for dom, claims in domain_claims.items():
                words = set()
                for claim in claims:
                    words |= {w.lower().strip(".,;:!?()[]{}\"'")
                              for w in claim.split()
                              if len(w) > 6 and w[0].isalpha()}
                domain_word_sets[dom] = words

            # Find words appearing in 2+ domain sets
            all_domain_words = list(domain_word_sets.values())
            if len(all_domain_words) >= 2:
                shared = all_domain_words[0]
                for ws in all_domain_words[1:]:
                    shared = shared & ws

                structural_keywords = [w for w in shared
                                       if w not in {"hypothesis", "predict",
                                                     "scaling", "model",
                                                     "system", "theory",
                                                     "specific", "between",
                                                     "follows", "suggests"}]

                if structural_keywords:
                    domains_involved = sorted(domain_claims.keys())
                    pattern_id = f"evolved_{hashlib.md5('_'.join(structural_keywords[:3]).encode()).hexdigest()[:8]}"

                    # Check for duplicates
                    existing_ids = {p["id"] for p in self.evolved}
                    if pattern_id not in existing_ids:
                        pattern = {
                            "id": pattern_id,
                            "name": f"Emergent Bridge: {' + '.join(structural_keywords[:3])}",
                            "core": (f"Structural motif '{', '.join(structural_keywords[:5])}' "
                                     f"appears across {', '.join(domains_involved)} "
                                     f"in breakthrough-tier hypotheses, suggesting a "
                                     f"deeper cross-domain invariant"),
                            "origin": f"V8.5 Pattern Evolution (from {len(breakthroughs)} breakthroughs)",
                            "appeared_in": domains_involved,
                            "tags": structural_keywords[:5] + ["evolved", "cross_domain"],
                            "source_breakthroughs": len(breakthroughs),
                            "discovered_at": datetime.now().isoformat(),
                        }
                        new_patterns.append(pattern)

        # Strategy 2: Detect recurring mechanism types
        mechanism_keywords = {}
        for bt in breakthroughs:
            mechanism = bt.get("mechanism", "")
            for keyword in ["scaling", "universality", "phase", "critical",
                            "nucleation", "percolation", "entropy", "information",
                            "network", "feedback", "resonance", "symmetry",
                            "optimization", "self-organized", "emergence",
                            "renormalization", "topology", "spectral",
                            "fractal", "power-law", "exponential"]:
                if keyword in mechanism.lower():
                    mechanism_keywords[keyword] = mechanism_keywords.get(keyword, 0) + 1

        # Keywords appearing in 2+ breakthroughs become evolved patterns
        for keyword, count in mechanism_keywords.items():
            if count >= 2:
                pattern_id = f"evolved_mech_{keyword}"
                existing_ids = {p["id"] for p in self.evolved}
                if pattern_id not in existing_ids:
                    pattern = {
                        "id": pattern_id,
                        "name": f"Mechanism Recurrence: {keyword.title()}",
                        "core": (f"The concept of '{keyword}' recurred in {count} "
                                 f"independent breakthrough hypotheses, suggesting "
                                 f"it is a productive structural lens for discovery"),
                        "origin": f"V8.5 Pattern Evolution (mechanism mining)",
                        "appeared_in": sorted(set(bt.get("domain", "") for bt in breakthroughs)),
                        "tags": [keyword, "evolved", "mechanism_recurrence"],
                        "recurrence_count": count,
                        "discovered_at": datetime.now().isoformat(),
                    }
                    new_patterns.append(pattern)

        # Save and return
        if new_patterns:
            self.evolved.extend(new_patterns)
            self.save()

        return new_patterns

    def merge_into_serendipity(self, serendipity_engine):
        """Merge evolved patterns into the active serendipity engine."""
        existing_ids = {p["id"] for p in serendipity_engine.patterns}
        added = 0
        for p in self.evolved:
            if p["id"] not in existing_ids:
                serendipity_engine.patterns.append(p)
                added += 1
        return added


# ══════════════════════════════════════════════════════════════════════════
# API CALLING (multi-backend, inherited from V6)
# ══════════════════════════════════════════════════════════════════════════

def call_api(system_prompt: str, user_prompt: str, *,
             api_base: str, api_key: str, model: str,
             max_tokens: int = 2048, temperature: float = 0.8) -> str:
    """Call LLM API with configurable temperature. Returns text response."""

    is_anthropic = "anthropic.com" in api_base

    if is_anthropic and HAS_ANTHROPIC:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text

    if not is_anthropic and HAS_OPENAI:
        client = openai.OpenAI(api_key=api_key or "not-needed", base_url=api_base)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content

    return _call_api_raw(system_prompt, user_prompt,
                         api_base=api_base, api_key=api_key,
                         model=model, max_tokens=max_tokens,
                         temperature=temperature)


def _call_api_raw(system_prompt, user_prompt, *, api_base, api_key, model,
                  max_tokens, temperature):
    """Raw HTTP fallback using urllib."""
    is_anthropic = "anthropic.com" in api_base

    if is_anthropic:
        url = api_base.rstrip("/").removesuffix("/v1") + "/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        body = json.dumps({
            "model": model, "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }).encode()
    else:
        url = api_base.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or 'not-needed'}",
        }
        body = json.dumps({
            "model": model, "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())

    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))

    if is_anthropic:
        return data["content"][0]["text"]
    else:
        return data["choices"][0]["message"]["content"]


def parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    # Try to find JSON object in the response
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try extracting first {...} block
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            return json.loads(match.group())
        raise


# ══════════════════════════════════════════════════════════════════════════
# HYPOTHESIS DATA CLASS
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class Hypothesis:
    id: str
    text: str
    claim: str = ""
    mechanism: str = ""
    testable_prediction: str = ""
    domain: str = ""
    domains_touched: list = field(default_factory=list)
    parent_ids: list = field(default_factory=list)
    generation: int = 0
    temperature_tier: str = "balanced"
    serendipity_pattern: str = ""
    contradicts_axiom: str = ""
    plausibility: float = 0.5
    surprise_if_true: float = 0.5
    scores: dict = field(default_factory=dict)
    score_justifications: dict = field(default_factory=dict)
    falsification: dict = field(default_factory=dict)
    experimental_protocol: dict = field(default_factory=dict)
    counter_hypothesis: str = ""
    status: str = "alive"
    created_at: str = ""

    def b_score(self):
        s = self.scores
        if not s:
            return 0
        return s.get("N", 0) * s.get("F", 0) * s.get("E", 0) * s.get("C", 0)

    def fails_kill_floor(self):
        for axis, floor in KILL_FLOOR.items():
            if self.scores.get(axis, 0) < floor:
                return True
        return False

    @property
    def tier(self):
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
    def tier_symbol(self):
        return {"KILLED": "💀", "RESEARCH_DIRECTION": "○",
                "THEORY_PROPOSAL": "◆", "CONDITIONAL_BREAKTHROUGH": "★?",
                "BREAKTHROUGH_CANDIDATE": "★"}.get(self.tier, "?")


# ══════════════════════════════════════════════════════════════════════════
# ENGINE STATE
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class V8State:
    mode: str = "Generic Research"
    target: str = "Autonomous Discovery"
    model: str = "claude-sonnet-4-20250514"
    session_id: str = ""
    generation: int = 0
    max_iterations: int = 10

    # Collections
    all_hypotheses: list = field(default_factory=list)
    survivors: list = field(default_factory=list)
    killed: list = field(default_factory=list)
    breakthroughs: list = field(default_factory=list)

    # Tracking
    log_entries: list = field(default_factory=list)
    interrupts: list = field(default_factory=list)
    b_history: list = field(default_factory=list)
    delta_novelty_history: list = field(default_factory=list)
    kill_rate_history: list = field(default_factory=list)
    serendipity_injections: list = field(default_factory=list)
    recombinations: list = field(default_factory=list)
    resurrections: list = field(default_factory=list)
    reality_sync_results: list = field(default_factory=list)
    paradigm_shifts: list = field(default_factory=list)
    evolved_patterns: list = field(default_factory=list)
    three_way_syntheses: list = field(default_factory=list)
    domain_rotation_idx: int = 0

    # Stagnation detector
    stagnation_count: int = 0

    def add_log(self, phase, agent, msg, msg_type="info"):
        self.log_entries.append({
            "phase": phase, "agent": agent, "msg": msg,
            "type": msg_type, "time": datetime.now().isoformat(),
        })

    def add_interrupt(self, int_type, msg):
        self.interrupts.append({
            "type": int_type, "msg": msg,
            "time": datetime.now().isoformat(),
        })

    def is_stagnant(self) -> bool:
        if len(self.delta_novelty_history) < STAGNATION_WINDOW:
            return False
        recent = self.delta_novelty_history[-STAGNATION_WINDOW:]
        return all(d < DELTA_NOVELTY_THRESHOLD for d in recent)


# ══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS (architecturally separated)
# ══════════════════════════════════════════════════════════════════════════

PRODUCER_SYSTEM = """You are an autonomous conjecture engine in a breakthrough discovery system.
Your role: generate bold, testable hypotheses that push the frontier of knowledge.
You receive context from a persistent axiom graph, cross-domain analogies, and dormant hypotheses.

Output ONLY valid JSON (no markdown fences) matching:
{
  "hypotheses": [
    {
      "claim": "One specific, bold, testable claim (2-3 sentences)",
      "mechanism": "Proposed underlying mechanism or explanation",
      "testable_prediction": "A specific, falsifiable prediction",
      "domain": "primary domain (physics/mathematics/biology/cs/economics/...)",
      "domains_touched": ["list", "of", "all", "domains", "involved"],
      "contradicts_axiom": "Which prior axiom this most challenges (or 'none')",
      "plausibility": 0.0-1.0,
      "surprise_if_true": 0.0-1.0,
      "hypothesis_type": "incremental|lateral|impossible_sounding|resurrection|recombination"
    }
  ]
}

Rules:
- Generate EXACTLY the number of hypotheses requested
- You MUST include the required mix of types as specified
- Rate plausibility AND surprise honestly — highest value is HIGH surprise + MODERATE plausibility
- Each hypothesis must have a concrete, falsifiable prediction
- Do NOT recycle prior axioms without meaningful mutation"""

# ─── ARCHITECTURALLY ISOLATED: the adversarial agent ───────────────────
ADVERSARIAL_SYSTEM = """You are the Falsifier. Your sole purpose is to destroy hypotheses.
You have NO access to how the hypothesis was generated.
You receive ONLY the claim itself.

For each hypothesis, output ONLY valid JSON (no markdown fences):
{
  "verdicts": [
    {
      "hypothesis_index": 0,
      "logical_attack": "The single most damaging logical objection",
      "boundary_case": "Specific case or condition where the claim fails",
      "hidden_assumption": "Key unstated assumption that, if false, kills the claim",
      "experimental_protocol": {
        "type": "mathematical|computational|empirical",
        "description": "Concrete steps to disprove this in <200 words",
        "expected_result_if_false": "What you'd observe if claim is wrong",
        "surprising_result_if_true": "What it would mean if claim survives"
      },
      "survivability_score": 0.0-1.0,
      "resurrectability": 0.0-1.0,
      "scores": {
        "N": 0.0-1.0,
        "F": 0.0-1.0,
        "E": 0.0-1.0,
        "C": 0.0-1.0
      },
      "score_justifications": {
        "N": "Why this novelty score",
        "F": "Why this falsifiability score",
        "E": "Why this empirical score",
        "C": "Why this compression score"
      }
    }
  ]
}

You are not here to be constructive. You are here to find truth by trying to break things.
Be harsh. Be specific. A survivability_score > 0.7 means YOU think the claim will probably survive testing.
Score on the NFEC axes independently and honestly."""

# ─── Counter-hypothesis generator ──────────────────────────────────────
COUNTER_HYPOTHESIS_SYSTEM = """You generate counter-hypotheses from falsification evidence.
When a hypothesis is falsified, you must generate the STRONGEST alternative
suggested by the failure. This is NOT just the negation — it must:
1. Account for the falsification evidence
2. Make a novel positive claim absent from the original
3. Be itself testable (state its own falsification criterion)
4. Score HIGHER on novelty than the original

Output ONLY valid JSON (no markdown fences):
{
  "counter_hypothesis": "The stronger alternative claim (2-3 sentences)",
  "accounts_for": "How it explains the falsification evidence",
  "novel_prediction": "Its own falsifiable prediction",
  "novelty_vs_original": "Why this is more interesting"
}
"""

# ─── Recombination agent ──────────────────────────────────────────────
RECOMBINATION_SYSTEM = """You are the Recombination Chamber in a discovery engine.
You receive 2-3 high-scoring hypotheses from DIFFERENT lineages and domains.
Your job: splice their core insights into chimeric hypotheses that cross lineage boundaries.

Output ONLY valid JSON (no markdown fences):
{
  "recombinations": [
    {
      "claim": "The chimeric hypothesis (2-3 sentences)",
      "parent_sources": ["id1", "id2"],
      "bridge_insight": "What structural analogy connects the parents",
      "testable_prediction": "A specific, falsifiable prediction",
      "domain": "primary domain",
      "surprise_if_true": 0.0-1.0
    }
  ]
}
"""

# ─── Failure archaeology ──────────────────────────────────────────────
ARCHAEOLOGY_SYSTEM = """You are the Failure Archaeologist. You re-examine previously
falsified hypotheses in light of newly discovered axioms.

Output ONLY valid JSON (no markdown fences):
{
  "resurrections": [
    {
      "original_id": "id of the failed hypothesis",
      "modified_claim": "Updated version that accounts for both the falsification AND the new axiom",
      "what_changed": "What new axiom makes this viable now",
      "testable_prediction": "New falsifiable prediction",
      "confidence": 0.0-1.0
    }
  ]
}

Most failures should STAY dead. Only resurrect if new evidence genuinely changes the picture.
If nothing should be resurrected, return {"resurrections": []}.
"""


# ══════════════════════════════════════════════════════════════════════════
# CONTEXT ASSEMBLY (Layer 1 + 2)
# ══════════════════════════════════════════════════════════════════════════

def format_axiom_nodes(nodes: list[AxiomNode], label: str = "") -> str:
    if not nodes:
        return f"[{label}: none available]\n"
    lines = [f"[{label}]"]
    for n in nodes:
        conf = f"{n.confidence:.2f}"
        nov = f"{n.novelty_score:.2f}"
        lines.append(f"  • [{n.domain}] (conf={conf}, nov={nov}) {n.text[:200]}")
    return "\n".join(lines)


def assemble_producer_prompt(
    state: V8State,
    axiom_graph: AxiomGraph,
    serendipity: SerendipityEngine,
    failure_archive: FailureArchive,
    n_hypotheses: int = 5,
) -> tuple[str, dict | None]:
    """Build the producer prompt with structured context. Returns (prompt, injected_pattern)."""

    gen = state.generation
    current_domain = DOMAIN_ROTATION[state.domain_rotation_idx % len(DOMAIN_ROTATION)]
    stagnant = state.is_stagnant()

    # 1. Recent verified axioms (strong prior, same domain)
    recent = axiom_graph.get_seed_candidates(domain=current_domain, k=3)

    # 2. High-novelty archived axioms (distant prior, prevents tunnel vision)
    all_alive = axiom_graph.get_alive_nodes()
    all_alive.sort(key=lambda n: n.novelty_score, reverse=True)
    archive = all_alive[:2] if all_alive else []

    # 3. Serendipity injection (if stagnant or on schedule)
    injected_pattern = None
    serendipity_block = ""
    if stagnant or gen % 5 == 0 or gen == 1:
        pattern = serendipity.inject(current_domain, stagnant=stagnant)
        if pattern:
            injected_pattern = pattern
            serendipity_block = serendipity.build_injection_prompt(pattern, current_domain)

    # 4. Dormant hypotheses for resurrection
    dormant = axiom_graph.get_dormant_nodes(k=2)

    # 5. Foreign domain seeds
    foreign = axiom_graph.get_foreign_seeds(current_domain, k=2)

    # Build type requirements
    type_mix = []
    if recent:
        type_mix.append("2 that extend or combine the verified axioms")
    else:
        type_mix.append("2 incremental hypotheses in the target domain")
    if foreign or injected_pattern:
        type_mix.append("2 that apply a cross-domain analogy structurally")
    else:
        type_mix.append("2 lateral hypotheses from unexpected angles")
    if dormant:
        type_mix.append("1 that resurrects or recombines a dormant hypothesis")
    else:
        type_mix.append("1 'impossible-sounding' hypothesis (high surprise)")

    prompt = f"""Generation {gen} | Domain focus: {current_domain} | Target: {state.target}
{'⚠ STAGNATION DETECTED — be maximally creative, break out of current patterns' if stagnant else ''}

{format_axiom_nodes(recent, "VERIFIED AXIOMS (recent, same domain)")}

{format_axiom_nodes(archive, "HIGH-NOVELTY AXIOMS (distant)")}

{format_axiom_nodes(foreign, "CROSS-DOMAIN SEEDS (foreign domains)")}

{format_axiom_nodes(dormant, "DORMANT HYPOTHESES (previously failed — may now be viable)")}

{serendipity_block}

TASK: Generate {n_hypotheses} hypotheses. You MUST include:
{chr(10).join("- " + t for t in type_mix)}

For each: state the claim, its testable prediction, and which prior axiom it most contradicts.
Rate its own plausibility 0-1 and how surprising it would be if true 0-1.
"""
    return prompt.strip(), injected_pattern


def assemble_adversarial_prompt(hypotheses: list[Hypothesis]) -> str:
    """Build the adversarial prompt. Contains ONLY the claims — no reasoning chains."""
    lines = ["Evaluate each hypothesis independently:\n"]
    for i, h in enumerate(hypotheses):
        lines.append(f"HYPOTHESIS {i}:")
        lines.append(f"  Claim: {h.claim}")
        lines.append(f"  Prediction: {h.testable_prediction}")
        lines.append(f"  Domain: {h.domain}")
        lines.append("")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# LAYER IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════

def layer0_serendipity(state, serendipity, axiom_graph, current_domain):
    """Layer 0: Serendipity Injection (fires on stagnation or schedule)."""
    header("Layer 0 — Serendipity Injection")
    if state.is_stagnant():
        warn(f"STAGNATION detected ({state.stagnation_count} cycles)")
        state.add_interrupt("warn", f"Stagnation detected — injecting serendipity at gen {state.generation}")
    elif state.generation % 5 == 0:
        info("Scheduled injection cycle")
    elif state.generation == 1:
        info("First-iteration injection")
    else:
        info("No injection needed this cycle")


def layer3_produce(state, prompt, injected_pattern, *,
                   api_base, api_key, model, n_hypotheses=5) -> list[Hypothesis]:
    """Layer 3: Multi-temperature ensemble conjecture generation."""
    header("Layer 3 — Conjecture Engine (Multi-Temperature Ensemble)")

    all_hypotheses = []
    session_id = state.session_id

    # Distribute hypotheses across temperatures
    temp_allocation = {
        "conservative": max(1, n_hypotheses // 3),
        "balanced": max(1, n_hypotheses // 3),
        "wild": max(1, n_hypotheses - 2 * (n_hypotheses // 3)),
    }

    for tier_name, count in temp_allocation.items():
        temp = TEMPERATURES[tier_name]
        info(f"  [{tier_name}] T={temp}, generating {count} hypothesis(es)...")

        tier_prompt = prompt + f"\n\nGenerate exactly {count} hypothesis(es)."

        # Forbidden knowledge constraint for wild tier
        if tier_name == "wild" and random.random() < 0.3:
            tier_prompt += ("\n\nFORBIDDEN KNOWLEDGE CONSTRAINT: Generate a hypothesis "
                           "that would be true if everything in the axiom bank were WRONG.")

        try:
            raw = call_api(
                PRODUCER_SYSTEM, tier_prompt,
                api_base=api_base, api_key=api_key, model=model,
                max_tokens=2048, temperature=temp,
            )
            data = parse_json_response(raw)
            hypos = data.get("hypotheses", [])

            for h_data in hypos:
                h = Hypothesis(
                    id=str(uuid.uuid4())[:12],
                    text=h_data.get("claim", ""),
                    claim=h_data.get("claim", ""),
                    mechanism=h_data.get("mechanism", ""),
                    testable_prediction=h_data.get("testable_prediction", ""),
                    domain=h_data.get("domain", ""),
                    domains_touched=h_data.get("domains_touched", []),
                    contradicts_axiom=h_data.get("contradicts_axiom", ""),
                    plausibility=float(h_data.get("plausibility", 0.5)),
                    surprise_if_true=float(h_data.get("surprise_if_true", 0.5)),
                    generation=state.generation,
                    temperature_tier=tier_name,
                    serendipity_pattern=injected_pattern.get("id", "") if injected_pattern else "",
                    created_at=datetime.now().isoformat(),
                )
                all_hypotheses.append(h)
                ok(f"[{tier_name}] {h.claim[:100]}...")

        except Exception as e:
            err(f"[{tier_name}] API error: {e}")
            state.add_log(f"G{state.generation}", "producer",
                          f"Error at T={temp}: {e}", "error")

    state.add_log(f"G{state.generation}", "producer",
                  f"Generated {len(all_hypotheses)} hypotheses across 3 temperatures", "info")
    return all_hypotheses


def layer4_falsify(state, hypotheses, *, api_base, api_key, model) -> list[Hypothesis]:
    """Layer 4: Architecturally ISOLATED adversarial falsification."""
    header("Layer 4 — Adversarial Falsifier (ISOLATED CONTEXT)")

    if not hypotheses:
        warn("No hypotheses to falsify")
        return []

    # Build prompt with ONLY claims — no reasoning chains
    adv_prompt = assemble_adversarial_prompt(hypotheses)

    info(f"Sending {len(hypotheses)} claims to adversarial agent...")
    info(f"(Adversary has NO access to producer reasoning)")

    try:
        raw = call_api(
            ADVERSARIAL_SYSTEM, adv_prompt,
            api_base=api_base, api_key=api_key, model=model,
            max_tokens=3000,
            temperature=TEMPERATURES["conservative"],  # Low T for rigour
        )
        data = parse_json_response(raw)
        verdicts = data.get("verdicts", [])

        for v in verdicts:
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

                # Apply mechanical kill floor
                if h.fails_kill_floor():
                    h.status = "killed"
                    state.add_log(f"G{state.generation}", "falsifier",
                                  f"💀 KILLED: {h.claim[:80]}... (floor violation)", "kill")
                else:
                    surv = v.get("survivability_score", 0)
                    symbol = h.tier_symbol
                    state.add_log(f"G{state.generation}", "falsifier",
                                  f"{symbol} SURVIVED (B={h.b_score():.3f}): {h.claim[:80]}...", "info")

    except Exception as e:
        err(f"Adversarial agent error: {e}")
        state.add_log(f"G{state.generation}", "falsifier",
                      f"Error: {e}", "error")
        # Assign default scores so pipeline can continue
        for h in hypotheses:
            if not h.scores:
                h.scores = {"N": 0.5, "F": 0.5, "E": 0.5, "C": 0.5}

    # Separate survivors from killed
    survivors = [h for h in hypotheses if h.status != "killed"]
    killed = [h for h in hypotheses if h.status == "killed"]

    kill_rate = len(killed) / len(hypotheses) if hypotheses else 0
    state.kill_rate_history.append(kill_rate)

    ok(f"Survivors: {len(survivors)} / {len(hypotheses)}  (kill rate: {kill_rate:.0%})")
    return hypotheses


def layer5_counter_hypotheses(state, killed_hypotheses, *,
                              api_base, api_key, model,
                              failure_archive: FailureArchive) -> list[str]:
    """Layer 5: Generate counter-hypotheses from falsified claims."""
    header("Layer 5 — Counter-Hypothesis Generator")

    counters = []
    for h in killed_hypotheses[:3]:  # Max 3 counter-hypotheses per cycle
        try:
            prompt = f"""FALSIFIED HYPOTHESIS: {h.claim}
FALSIFICATION EVIDENCE: {h.falsification.get('logical_attack', '')}
BOUNDARY CASE: {h.falsification.get('boundary_case', '')}
HIDDEN ASSUMPTION: {h.falsification.get('hidden_assumption', '')}

Generate the strongest counter-hypothesis."""

            raw = call_api(
                COUNTER_HYPOTHESIS_SYSTEM, prompt,
                api_base=api_base, api_key=api_key, model=model,
                max_tokens=800, temperature=0.9,
            )
            data = parse_json_response(raw)
            counter = data.get("counter_hypothesis", "")
            if counter:
                h.counter_hypothesis = counter
                counters.append(counter)
                failure_archive.add(
                    hypothesis_text=h.claim,
                    falsification_evidence=h.falsification.get("logical_attack", ""),
                    counter_hypothesis=counter,
                    node_id=h.id,
                    generation=state.generation,
                )
                info(f"Counter: {counter[:100]}...")
        except Exception as e:
            warn(f"Counter-hypothesis error: {e}")

    ok(f"Generated {len(counters)} counter-hypotheses from failures")
    return counters


def layer6_recombine(state, survivors, axiom_graph, *,
                     api_base, api_key, model) -> list[Hypothesis]:
    """Layer 6: Recombination Chamber — splice survivors across lineages."""
    header("Layer 6 — Recombination Chamber")

    # Need at least 2 survivors + some stored axioms
    stored = axiom_graph.get_alive_nodes()
    if len(survivors) < 1 or len(stored) < 1:
        info("Insufficient material for recombination")
        return []

    # Pick 2-3 candidates from different domains
    candidates = []
    seen_domains = set()

    for h in survivors:
        if h.domain not in seen_domains:
            candidates.append({"id": h.id, "text": h.claim, "domain": h.domain})
            seen_domains.add(h.domain)
        if len(candidates) >= 2:
            break

    # Add a stored axiom from a different domain
    for ax in stored:
        if ax.domain not in seen_domains:
            candidates.append({"id": ax.id, "text": ax.text, "domain": ax.domain})
            break

    if len(candidates) < 2:
        info("Not enough cross-domain material")
        return []

    prompt = f"""Recombine these high-scoring hypotheses from different lineages:

{json.dumps(candidates, indent=2)}

Generate 1-2 chimeric hypotheses that bridge their core insights."""

    recombined = []
    try:
        raw = call_api(
            RECOMBINATION_SYSTEM, prompt,
            api_base=api_base, api_key=api_key, model=model,
            max_tokens=1500, temperature=0.9,
        )
        data = parse_json_response(raw)
        for r in data.get("recombinations", []):
            h = Hypothesis(
                id=str(uuid.uuid4())[:12],
                text=r.get("claim", ""),
                claim=r.get("claim", ""),
                testable_prediction=r.get("testable_prediction", ""),
                domain=r.get("domain", ""),
                parent_ids=r.get("parent_sources", []),
                surprise_if_true=float(r.get("surprise_if_true", 0.6)),
                generation=state.generation,
                temperature_tier="recombination",
                created_at=datetime.now().isoformat(),
            )
            recombined.append(h)
            state.recombinations.append({
                "generation": state.generation,
                "parents": r.get("parent_sources", []),
                "bridge": r.get("bridge_insight", ""),
                "child_id": h.id,
            })
            ok(f"Recombined: {h.claim[:100]}...")
    except Exception as e:
        warn(f"Recombination error: {e}")

    return recombined


def layer7_update_graph(state, hypotheses, axiom_graph, injected_pattern,
                        serendipity):
    """Layer 7: Axiom Graph Updater — persist survivors, track genealogy."""
    header("Layer 7 — Axiom Graph Update")

    survivors = [h for h in hypotheses if h.status != "killed"]
    killed = [h for h in hypotheses if h.status == "killed"]

    for h in survivors:
        node = AxiomNode(
            id=h.id,
            text=h.claim,
            domain=h.domain,
            domains_touched=h.domains_touched,
            confidence=h.b_score(),
            novelty_score=h.surprise_if_true,
            generation=state.generation,
            session_id=state.session_id,
            status="alive",
            parent_ids=h.parent_ids,
            scores=h.scores,
            tier=h.tier,
            experimental_protocol=h.experimental_protocol,
            created_at=h.created_at,
        )
        axiom_graph.add_node(node)

        # Record serendipity origin
        if h.serendipity_pattern:
            axiom_graph.add_edge("pattern:" + h.serendipity_pattern,
                                 h.id, "seeded_by")

        # Record parent edges
        for pid in h.parent_ids:
            axiom_graph.add_edge(pid, h.id, "derives_from")

    for h in killed:
        node = AxiomNode(
            id=h.id, text=h.claim, domain=h.domain,
            confidence=0.0, novelty_score=h.surprise_if_true,
            generation=state.generation, session_id=state.session_id,
            status="falsified",
            falsification_evidence=h.falsification.get("logical_attack", ""),
            counter_hypothesis=h.counter_hypothesis,
            scores=h.scores, created_at=h.created_at,
        )
        axiom_graph.add_node(node)

    # Apply decay to all existing nodes
    axiom_graph.apply_decay(rate=0.005)

    # Meta-learning: record serendipity outcomes
    if injected_pattern:
        avg_b = sum(h.b_score() for h in survivors) / max(len(survivors), 1)
        serendipity.record_outcome(injected_pattern["id"], avg_b)

    axiom_graph.save()
    stats = axiom_graph.stats()
    ok(f"Graph: {stats['alive']} alive, {stats['falsified']} falsified, "
       f"{stats['edges']} edges, domains={stats['domains']}")


def layer8_synthesize(state, hypotheses, axiom_graph):
    """Layer 8: Synthesis & Iteration Controller — delta-novelty + stagnation."""
    header("Layer 8 — Synthesis & Iteration Controller")

    survivors = [h for h in hypotheses if h.status != "killed"]

    if not survivors:
        delta = 0.0
    else:
        # Delta-novelty: average surprise of survivors vs axiom graph baseline
        avg_surprise = sum(h.surprise_if_true for h in survivors) / len(survivors)
        # Compare to graph average
        alive_nodes = axiom_graph.get_alive_nodes()
        if alive_nodes:
            graph_avg = sum(n.novelty_score for n in alive_nodes) / len(alive_nodes)
            delta = abs(avg_surprise - graph_avg)
        else:
            delta = avg_surprise

    state.delta_novelty_history.append(delta)

    # Best B score this generation
    best_b = max((h.b_score() for h in survivors), default=0)
    state.b_history.append(best_b)

    # Track breakthroughs
    bt_candidates = [h for h in survivors if h.tier in ("BREAKTHROUGH_CANDIDATE", "CONDITIONAL_BREAKTHROUGH")]
    for bt in bt_candidates:
        state.breakthroughs.append(asdict(bt))
        state.add_interrupt("info", f"★ BREAKTHROUGH: {bt.claim[:100]}")

    # Stagnation check
    if state.is_stagnant():
        state.stagnation_count += 1
        warn(f"Stagnation cycle {state.stagnation_count}  (delta-novelty: {delta:.3f})")
        state.add_interrupt("warn",
                            f"Stagnation cycle {state.stagnation_count} — "
                            f"serendipity injection scheduled next iteration")
        # Advance domain rotation to force diversity
        state.domain_rotation_idx += 1
    else:
        state.stagnation_count = 0

    ok(f"Delta-novelty: {delta:.3f}  |  Best B: {best_b:.3f}  |  "
       f"Breakthroughs this gen: {len(bt_candidates)}")

    # Update all_hypotheses/survivors/killed lists
    state.all_hypotheses.extend(hypotheses)
    state.survivors.extend(survivors)
    state.killed.extend([h for h in hypotheses if h.status == "killed"])


def run_archaeology(state, axiom_graph, failure_archive, *,
                    api_base, api_key, model) -> list[Hypothesis]:
    """Failure Archaeology: re-examine falsified hypotheses under new axioms."""
    header("FAILURE ARCHAEOLOGY")

    candidates = failure_archive.get_candidates_for_resurrection()
    if not candidates:
        info("No candidates for resurrection")
        return []

    # Recent axioms as new context
    recent_axioms = axiom_graph.get_seed_candidates(k=5)

    prompt = f"""Here are {len(candidates)} previously falsified hypotheses:

{json.dumps(candidates[:5], indent=2)}

Here are the newest verified axioms discovered since those failures:

{format_axiom_nodes(recent_axioms, "NEW AXIOMS")}

Which (if any) of the failed hypotheses should be resurrected in modified form?
Only resurrect if the new axioms genuinely change the picture."""

    resurrected = []
    try:
        raw = call_api(
            ARCHAEOLOGY_SYSTEM, prompt,
            api_base=api_base, api_key=api_key, model=model,
            max_tokens=1500, temperature=0.7,
        )
        data = parse_json_response(raw)
        for r in data.get("resurrections", []):
            h = Hypothesis(
                id=str(uuid.uuid4())[:12],
                text=r.get("modified_claim", ""),
                claim=r.get("modified_claim", ""),
                testable_prediction=r.get("testable_prediction", ""),
                parent_ids=[r.get("original_id", "")],
                generation=state.generation,
                temperature_tier="resurrection",
                created_at=datetime.now().isoformat(),
            )
            resurrected.append(h)
            state.resurrections.append({
                "generation": state.generation,
                "original_id": r.get("original_id", ""),
                "what_changed": r.get("what_changed", ""),
            })
            ok(f"Resurrected: {h.claim[:100]}...")

            # Mark in archive
            for f in failure_archive.failures:
                if f["id"] == r.get("original_id"):
                    f["resurrection_attempts"] += 1
                    f["resurrected"] = True
            failure_archive.save()

    except Exception as e:
        warn(f"Archaeology error: {e}")

    return resurrected


# ══════════════════════════════════════════════════════════════════════════
# MAIN ITERATION LOOP
# ══════════════════════════════════════════════════════════════════════════

def run_iteration(state: V8State, axiom_graph: AxiomGraph,
                  serendipity: SerendipityEngine,
                  failure_archive: FailureArchive, *,
                  api_base: str, api_key: str, model: str) -> list[Hypothesis]:
    """Execute one full 9-layer iteration."""

    state.generation += 1
    gen = state.generation
    current_domain = DOMAIN_ROTATION[state.domain_rotation_idx % len(DOMAIN_ROTATION)]

    print(f"\n{C.BOLD}{C.CYAN}{'═'*70}")
    print(f"  GENERATION {gen}  |  Domain: {current_domain}  |  "
          f"{datetime.now().strftime('%H:%M:%S')}")
    print(f"{'═'*70}{C.RESET}")

    # Layer 0: Serendipity Injection decision
    layer0_serendipity(state, serendipity, axiom_graph, current_domain)

    # Layer 1+2: Assemble producer context
    header("Layer 1+2 — Context Assembly")
    prompt, injected_pattern = assemble_producer_prompt(
        state, axiom_graph, serendipity, failure_archive, n_hypotheses=5)
    if injected_pattern:
        state.serendipity_injections.append({
            "generation": gen, "pattern": injected_pattern["name"],
        })
        ok(f"Injected pattern: {injected_pattern['name']}")
    else:
        info("No serendipity injection this cycle")

    # Layer 3: Multi-temperature ensemble production
    hypotheses = layer3_produce(
        state, prompt, injected_pattern,
        api_base=api_base, api_key=api_key, model=model, n_hypotheses=5)

    if not hypotheses:
        err("No hypotheses generated — skipping remaining layers")
        return []

    # Layer 4: Adversarial falsification (ISOLATED CONTEXT)
    hypotheses = layer4_falsify(
        state, hypotheses,
        api_base=api_base, api_key=api_key, model=model)

    # Layer 5: Counter-hypotheses from killed
    killed = [h for h in hypotheses if h.status == "killed"]
    if killed:
        layer5_counter_hypotheses(
            state, killed,
            api_base=api_base, api_key=api_key, model=model,
            failure_archive=failure_archive)

    survivors = [h for h in hypotheses if h.status != "killed"]

    # Layer 6: Recombination (every 2nd generation, or if survivors exist)
    if gen % 2 == 0 and survivors:
        recombined = layer6_recombine(
            state, survivors, axiom_graph,
            api_base=api_base, api_key=api_key, model=model)
        if recombined:
            # Quick-falsify recombinations
            recombined = layer4_falsify(
                state, recombined,
                api_base=api_base, api_key=api_key, model=model)
            hypotheses.extend(recombined)

    # Failure archaeology (every 10 generations)
    if gen % 10 == 0 and gen > 0:
        resurrected = run_archaeology(
            state, axiom_graph, failure_archive,
            api_base=api_base, api_key=api_key, model=model)
        if resurrected:
            resurrected = layer4_falsify(
                state, resurrected,
                api_base=api_base, api_key=api_key, model=model)
            hypotheses.extend(resurrected)

    # Layer 7: Update axiom graph
    layer7_update_graph(state, hypotheses, axiom_graph, injected_pattern,
                        serendipity)

    # Layer 8: Synthesis & iteration control
    layer8_synthesize(state, hypotheses, axiom_graph)

    # Rotate domain
    state.domain_rotation_idx += 1

    return hypotheses


def run_pipeline(state: V8State, axiom_graph: AxiomGraph,
                 serendipity: SerendipityEngine,
                 failure_archive: FailureArchive, *,
                 api_base: str, api_key: str, model: str):
    """Run the full evolutionary discovery pipeline."""
    t_start = time.time()

    print(f"\n{C.BOLD}{C.PURPLE}{'═'*70}")
    print(f"  BREAKTHROUGH ENGINE V{VERSION} — Evolutionary Discovery System")
    print(f"  Mode: {state.mode}  |  Target: {state.target}")
    print(f"  Model: {model}  |  Iterations: {state.max_iterations}")
    print(f"  Session: {state.session_id}")
    print(f"{'═'*70}{C.RESET}")

    graph_stats = axiom_graph.stats()
    if graph_stats["total"] > 0:
        ok(f"Resuming with {graph_stats['total']} nodes in axiom graph "
           f"({graph_stats['alive']} alive)")
    else:
        info("Fresh axiom graph — first session")

    for i in range(state.max_iterations):
        run_iteration(
            state, axiom_graph, serendipity, failure_archive,
            api_base=api_base, api_key=api_key, model=model)

        # Brief pause between iterations
        if i < state.max_iterations - 1:
            time.sleep(1)

    elapsed = time.time() - t_start

    # Final summary
    print(f"\n{C.BOLD}{C.CYAN}{'═'*70}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'═'*70}{C.RESET}")
    ok(f"Generations: {state.generation}")
    ok(f"Total hypotheses: {len(state.all_hypotheses)}")
    ok(f"Survivors: {len(state.survivors)}")
    ok(f"Killed: {len(state.killed)}")
    ok(f"Breakthroughs: {len(state.breakthroughs)}")
    ok(f"Serendipity injections: {len(state.serendipity_injections)}")
    ok(f"Recombinations: {len(state.recombinations)}")
    ok(f"Resurrections: {len(state.resurrections)}")
    ok(f"Elapsed: {elapsed:.1f}s")

    graph_stats = axiom_graph.stats()
    ok(f"Axiom graph: {graph_stats['total']} nodes, {graph_stats['edges']} edges")
    ok(f"Domains: {', '.join(graph_stats['domains'])}")

    return state


# ══════════════════════════════════════════════════════════════════════════
# AGENT MODE: run from pre-generated JSON (no API calls)
# ══════════════════════════════════════════════════════════════════════════

def run_from_data(state: V8State, axiom_graph: AxiomGraph,
                  serendipity: SerendipityEngine,
                  failure_archive: FailureArchive,
                  iterations_data: list, *,
                  reality_sync: RealitySyncEngine = None,
                  paradigm_detector: ParadigmShiftDetector = None,
                  pattern_evolver: PatternEvolver = None):
    """Process pre-generated iteration data — full 12-layer pipeline, no API calls.

    Executes all layers that don't require API access:
      Layer 0:   Serendipity tracking from data
      Layer 1+2: Context assembly (from data)
      Layer 3:   Hypothesis ingestion + scoring
      Layer 4:   Kill-floor adversarial filter + cross-validation
      Layer 5:   Counter-hypothesis extraction from falsification data
      Layer 5.5: Reality-Sync — auto-generate + execute validation scripts
      Layer 6:   Synthesis Chamber — 3-way cross-domain blending + 2-way recombination
      Layer 6.5: Paradigm Shift Detector — auto-resurrect on breakthroughs
      Layer 7:   Axiom graph update with edges, genealogy, decay
      Layer 8:   Synthesis controller — delta-novelty, stagnation, breakthrough detection
      Layer 9:   Pattern Evolution — discover new structural patterns
    """

    # Default-construct new engines if not provided
    if reality_sync is None:
        reality_sync = RealitySyncEngine()
    if paradigm_detector is None:
        paradigm_detector = ParadigmShiftDetector()
    if pattern_evolver is None:
        pattern_evolver = PatternEvolver()

    # Merge any previously evolved patterns into serendipity library
    merged_count = pattern_evolver.merge_into_serendipity(serendipity)
    if merged_count:
        info(f"Merged {merged_count} evolved patterns into serendipity library")

    t_start = time.time()

    print(f"\n{C.BOLD}{C.PURPLE}{'═'*70}")
    print(f"  BREAKTHROUGH ENGINE V{VERSION} — Data-Driven Pipeline")
    print(f"  Mode: {state.mode}  |  Target: {state.target}")
    print(f"  Generations: {len(iterations_data)}  |  Session: {state.session_id}")
    print(f"{'═'*70}{C.RESET}")

    all_survivors_pool = []  # Cross-generation recombination pool

    for iter_data in iterations_data:
        state.generation += 1
        gen = state.generation

        print(f"\n{C.BOLD}{C.CYAN}{'═'*70}")
        print(f"  GENERATION {gen}  |  "
              f"{iter_data.get('domain_focus', 'cross-domain')}  |  "
              f"{datetime.now().strftime('%H:%M:%S')}")
        print(f"{'═'*70}{C.RESET}")

        # ── Layer 0: Serendipity tracking ──────────────────────────────
        header("Layer 0 — Serendipity Injection")
        serendip_data = iter_data.get("serendipity_injection", {})
        injected_pattern = None
        if serendip_data.get("pattern"):
            pat_name = serendip_data["pattern"]
            # Find the actual pattern in the library
            for p in serendipity.patterns:
                if p.get("name") == pat_name:
                    injected_pattern = p
                    break
            if injected_pattern:
                state.serendipity_injections.append({
                    "generation": gen, "pattern": pat_name,
                })
                ok(f"Injected pattern: {pat_name}")
                state.add_log("serendipity", "system",
                              f"Pattern '{pat_name}' injected at gen {gen}")
            else:
                info(f"Pattern '{pat_name}' referenced but not in library")
        else:
            info("No serendipity injection this cycle")

        # ── Layer 1+2+3: Ingest hypotheses with full metadata ─────────
        header("Layer 1-3 — Hypothesis Ingestion + Scoring")
        hypotheses = []
        for h_data in iter_data.get("hypotheses", []):
            h_type = h_data.get("hypothesis_type", "balanced")
            temp_map = {"conservative": "conservative", "incremental": "conservative",
                        "balanced": "balanced", "lateral": "balanced",
                        "wild": "wild", "impossible_sounding": "wild"}
            temp_tier = temp_map.get(h_type, "balanced")

            h = Hypothesis(
                id=str(uuid.uuid4())[:12],
                text=h_data.get("claim", h_data.get("hypothesis", "")),
                claim=h_data.get("claim", h_data.get("hypothesis", "")),
                mechanism=h_data.get("mechanism", ""),
                testable_prediction=h_data.get("testable_prediction", ""),
                domain=h_data.get("domain", ""),
                domains_touched=h_data.get("domains_touched", []),
                contradicts_axiom=h_data.get("contradicts_axiom", ""),
                plausibility=float(h_data.get("plausibility", 0.5)),
                surprise_if_true=float(h_data.get("surprise_if_true", 0.5)),
                scores=h_data.get("scores", {}),
                score_justifications=h_data.get("score_justifications", {}),
                falsification=h_data.get("falsification", {}),
                experimental_protocol=h_data.get("experimental_protocol", {}),
                temperature_tier=temp_tier,
                serendipity_pattern=serendip_data.get("pattern", ""),
                generation=gen,
                created_at=datetime.now().isoformat(),
            )
            hypotheses.append(h)
            b = h.b_score()
            info(f"  [{temp_tier[0].upper()}] B={b:.4f} ({h.domain}) "
                 f"{h.claim[:80]}...")

        # ── Layer 4: Adversarial filtering (kill floor + cross-validate) ──
        header("Layer 4 — Adversarial Kill Floor")
        for h in hypotheses:
            # Primary kill floor
            if h.fails_kill_floor():
                h.status = "killed"
                warn(f"  KILLED (kill floor): {h.claim[:70]}...")
                state.add_log("falsifier", "kill_floor",
                              f"Killed: {h.claim[:120]}", "warn")
                continue

            # Cross-validate: survivability from adversarial data
            surv = h.falsification.get("survivability", 1.0)
            if surv < 0.20:
                h.status = "killed"
                warn(f"  KILLED (survivability={surv:.2f}): {h.claim[:70]}...")
                state.add_log("falsifier", "adversarial",
                              f"Killed by low survivability ({surv:.2f}): "
                              f"{h.claim[:120]}", "warn")

        survivors = [h for h in hypotheses if h.status != "killed"]
        killed = [h for h in hypotheses if h.status == "killed"]
        ok(f"Survivors: {len(survivors)} / {len(hypotheses)} "
           f"(killed: {len(killed)})")

        # ── Layer 5: Counter-hypothesis extraction ─────────────────────
        if killed:
            header("Layer 5 — Counter-Hypotheses")
            for h in killed:
                falsi = h.falsification
                if falsi.get("logical_attack"):
                    h.counter_hypothesis = (
                        f"Counter: {falsi['logical_attack'][:200]}"
                    )
                    info(f"  Counter for [{h.domain}]: "
                         f"{falsi['logical_attack'][:80]}...")

                # Archive the failure
                failure_archive.add(
                    hypothesis_text=h.claim,
                    falsification_evidence=h.falsification.get("logical_attack", "kill floor"),
                    counter_hypothesis=h.counter_hypothesis,
                    node_id=h.id,
                    generation=gen,
                )
            failure_archive.save()

        # ── Layer 5.5: Reality-Sync — generate validation micro-scripts ──
        header("Layer 5.5 — Reality-Sync Engine")
        sync_count = 0
        for h in survivors:
            result = reality_sync.generate_validation_script(h, gen)
            if result and result.get("generated"):
                # Execute the validation script
                exec_result = reality_sync.execute_validation(result["script_path"])
                if exec_result and exec_result.get("status") == "validated":
                    notes = reality_sync.apply_adjustments(h, exec_result)
                    sync_count += 1
                    for note in notes[:3]:
                        info(f"  [{h.domain}] {note}")
                    # Re-check kill floor after adjustments
                    if h.fails_kill_floor() and h.status == "alive":
                        h.status = "killed"
                        killed.append(h)
                        survivors = [s for s in survivors if s.id != h.id]
                        warn(f"  Post-sync kill: {h.claim[:70]}...")
                elif exec_result:
                    info(f"  [{h.domain}] sync status: {exec_result.get('status', '?')}")
        state.reality_sync_results.extend(reality_sync.results[-sync_count:] if sync_count else [])
        ok(f"Reality-Sync: {sync_count} hypotheses validated")

        # ── Layer 6: Synthesis Chamber (3-way cross-domain blending) ───
        recombined = []
        if gen >= 2 and survivors and all_survivors_pool:
            header("Layer 6 — Synthesis Chamber (3-Way Blending)")

            # Three-way synthesis: pick from 3 different domains
            domain_buckets = {}
            for h in survivors + all_survivors_pool:
                base_dom = h.domain.split("×")[0]  # Handle recombinant domains
                if base_dom not in domain_buckets:
                    domain_buckets[base_dom] = []
                domain_buckets[base_dom].append(h)

            available_domains = sorted(domain_buckets.keys())

            # Generate THREE-WAY syntheses if 3+ domains available
            if len(available_domains) >= 3:
                # Pick the top-scoring hypothesis from each of 3 domains
                for i in range(min(2, len(available_domains) - 2)):
                    trio_domains = available_domains[i:i+3]
                    trio = []
                    for d in trio_domains:
                        best_in_dom = max(domain_buckets[d],
                                          key=lambda h: h.b_score())
                        trio.append(best_in_dom)

                    if len(trio) == 3:
                        h1, h2, h3 = trio
                        r_id = str(uuid.uuid4())[:12]

                        # Three-way synthesis claim
                        r_claim = (
                            f"[3-WAY SYNTHESIS] {h1.domain} × {h2.domain} × "
                            f"{h3.domain}: How does '{h1.claim[:80]}...' inform "
                            f"'{h2.claim[:80]}...' to optimize "
                            f"'{h3.claim[:80]}...'?"
                        )

                        # Geometric mean of all three parents' scores
                        r_scores = {}
                        for axis in ("N", "F", "E", "C"):
                            s1 = h1.scores.get(axis, 0.5)
                            s2 = h2.scores.get(axis, 0.5)
                            s3 = h3.scores.get(axis, 0.5)
                            r_scores[axis] = (s1 * s2 * s3) ** (1/3)
                        # Strong novelty boost for 3-way bridge
                        r_scores["N"] = min(1.0, r_scores["N"] * 1.25)
                        # Compression boost — 3 domains explained
                        r_scores["C"] = min(1.0, r_scores["C"] * 1.15)

                        all_domains = list(set(
                            h1.domains_touched + h2.domains_touched + h3.domains_touched))

                        r = Hypothesis(
                            id=r_id,
                            text=r_claim,
                            claim=r_claim,
                            domain=f"{h1.domain}×{h2.domain}×{h3.domain}",
                            domains_touched=all_domains,
                            parent_ids=[h1.id, h2.id, h3.id],
                            scores=r_scores,
                            temperature_tier="synthesis",
                            generation=gen,
                            created_at=datetime.now().isoformat(),
                        )
                        if not r.fails_kill_floor():
                            recombined.append(r)
                            state.three_way_syntheses.append({
                                "generation": gen,
                                "parents": [h1.id, h2.id, h3.id],
                                "domains": [h1.domain, h2.domain, h3.domain],
                                "child": r_id,
                            })
                            ok(f"  3-Way: {h1.domain} × {h2.domain} × "
                               f"{h3.domain} → B={r.b_score():.4f}")

            # Also do standard 2-way recombinations
            for new_h in survivors:
                for old_h in all_survivors_pool:
                    if (old_h.domain != new_h.domain
                            and old_h.id != new_h.id):
                        shared = set(new_h.domains_touched) & set(old_h.domains_touched)
                        if shared:
                            r_id = str(uuid.uuid4())[:12]
                            r_claim = (
                                f"[RECOMBINATION] Bridging {new_h.domain} × "
                                f"{old_h.domain}: {new_h.claim[:120]} ⊕ "
                                f"{old_h.claim[:120]}"
                            )
                            r_scores = {}
                            for axis in ("N", "F", "E", "C"):
                                s1 = new_h.scores.get(axis, 0.5)
                                s2 = old_h.scores.get(axis, 0.5)
                                r_scores[axis] = (s1 * s2) ** 0.5
                            r_scores["N"] = min(1.0, r_scores["N"] * 1.15)

                            r = Hypothesis(
                                id=r_id,
                                text=r_claim,
                                claim=r_claim,
                                domain=f"{new_h.domain}×{old_h.domain}",
                                domains_touched=list(
                                    set(new_h.domains_touched + old_h.domains_touched)),
                                parent_ids=[new_h.id, old_h.id],
                                scores=r_scores,
                                temperature_tier="recombination",
                                generation=gen,
                                created_at=datetime.now().isoformat(),
                            )
                            if not r.fails_kill_floor():
                                recombined.append(r)
                                state.recombinations.append({
                                    "generation": gen,
                                    "parents": [new_h.id, old_h.id],
                                    "child": r_id,
                                    "domains": r.domain,
                                })
                                ok(f"  Recombinant: {new_h.domain} × "
                                   f"{old_h.domain} → B={r.b_score():.4f}")
                            break

            if recombined:
                hypotheses.extend(recombined)
                survivors.extend(recombined)
                ok(f"Total recombinations + syntheses: {len(recombined)}")
            else:
                info("No viable recombinations this generation")

        # ── Layer 6.5: Paradigm Shift Detector ─────────────────────────
        header("Layer 6.5 — Paradigm Shift Detector")
        shifts = paradigm_detector.check_for_paradigm_shift(
            state, axiom_graph, survivors)
        if shifts:
            for shift in shifts:
                state.paradigm_shifts.append(shift)
                ok(f"  SHIFT [{shift['type']}]: {shift.get('trigger_claim', '')[:80]}...")
                state.add_log("paradigm", "detector",
                              f"Shift: {shift['type']} in {shift.get('domain', '?')}",
                              "info")

            # Scan failure archive for resurrections
            resurrections = paradigm_detector.scan_archive_for_resurrections(
                shifts, failure_archive, axiom_graph, gen)
            if resurrections:
                ok(f"  Paradigm resurrections: {len(resurrections)}")
                for rez in resurrections:
                    state.resurrections.append(rez)
                    info(f"  ↻ [{rez.get('trigger_shift', '?')}] "
                         f"relevance={rez['relevance_score']:.2f}: "
                         f"{rez['original_claim'][:80]}...")
                    state.add_interrupt("info",
                        f"↻ PARADIGM RESURRECTION: {rez['original_claim'][:100]}")
        else:
            info("No paradigm shifts detected this generation")

        # ── Layer 7: Axiom graph update with edges + genealogy ─────────
        header("Layer 7 — Axiom Graph Update")
        for h in survivors:
            node = AxiomNode(
                id=h.id, text=h.claim, domain=h.domain,
                domains_touched=h.domains_touched,
                confidence=h.b_score(),
                novelty_score=h.surprise_if_true,
                generation=gen, session_id=state.session_id,
                status="alive",
                parent_ids=h.parent_ids,
                scores=h.scores, tier=h.tier,
                experimental_protocol=h.experimental_protocol,
                created_at=h.created_at,
            )
            axiom_graph.add_node(node)

            # Record serendipity edges
            if h.serendipity_pattern:
                axiom_graph.add_edge(
                    "pattern:" + h.serendipity_pattern, h.id, "seeded_by")

            # Record parent (recombination) edges
            for pid in h.parent_ids:
                axiom_graph.add_edge(pid, h.id, "derives_from")

            # Cross-domain edges between same-generation survivors
            for h2 in survivors:
                if h2.id != h.id and h2.domain != h.domain:
                    shared = set(h.domains_touched) & set(h2.domains_touched)
                    if shared:
                        axiom_graph.add_edge(h.id, h2.id, "domain_bridge")

        for h in killed:
            node = AxiomNode(
                id=h.id, text=h.claim, domain=h.domain,
                confidence=0.0, novelty_score=h.surprise_if_true,
                generation=gen, session_id=state.session_id,
                status="falsified",
                falsification_evidence=h.falsification.get("logical_attack", ""),
                counter_hypothesis=h.counter_hypothesis,
                scores=h.scores, created_at=h.created_at,
            )
            axiom_graph.add_node(node)

        axiom_graph.apply_decay(rate=0.005)

        # Meta-learning: serendipity outcome
        if injected_pattern and survivors:
            avg_b = sum(h.b_score() for h in survivors) / len(survivors)
            serendipity.record_outcome(injected_pattern["id"], avg_b)

        axiom_graph.save()
        stats = axiom_graph.stats()
        ok(f"Graph: {stats['alive']} alive, {stats['falsified']} falsified, "
           f"{stats['edges']} edges, domains={stats['domains']}")

        # ── Layer 8: Synthesis & iteration control ─────────────────────
        header("Layer 8 — Synthesis Controller")

        # Delta-novelty
        if survivors:
            avg_surprise = sum(h.surprise_if_true for h in survivors) / len(survivors)
            alive_nodes = axiom_graph.get_alive_nodes()
            if alive_nodes:
                graph_avg = sum(n.novelty_score for n in alive_nodes) / len(alive_nodes)
                delta = abs(avg_surprise - graph_avg)
            else:
                delta = avg_surprise
        else:
            delta = 0.0

        state.delta_novelty_history.append(delta)
        best_b = max((h.b_score() for h in survivors), default=0)
        state.b_history.append(best_b)
        kill_rate = len(killed) / max(len(hypotheses), 1)
        state.kill_rate_history.append(kill_rate)

        # Breakthrough detection
        bt_candidates = [h for h in survivors
                         if h.tier in ("BREAKTHROUGH_CANDIDATE",
                                       "CONDITIONAL_BREAKTHROUGH")]
        for bt in bt_candidates:
            state.breakthroughs.append(asdict(bt))
            state.add_interrupt("info", f"★ BREAKTHROUGH: {bt.claim[:100]}")
            ok(f"  ★ {bt.tier}: {bt.claim[:80]}...")

        # Stagnation detection
        if state.is_stagnant():
            state.stagnation_count += 1
            warn(f"Stagnation cycle {state.stagnation_count}  "
                 f"(delta-novelty: {delta:.3f})")
            state.add_interrupt("warn",
                                f"Stagnation cycle {state.stagnation_count} — "
                                f"serendipity injection needed")
        else:
            state.stagnation_count = 0

        ok(f"Delta-novelty: {delta:.3f}  |  Best B: {best_b:.3f}  |  "
           f"Kill rate: {kill_rate:.0%}  |  "
           f"Breakthroughs: {len(bt_candidates)}")

        # Update state collections
        state.all_hypotheses.extend(hypotheses)
        state.survivors.extend(survivors)
        state.killed.extend(killed)

        # Add to recombination pool for next generation
        all_survivors_pool.extend(survivors)

        state.add_log("synthesis", "controller",
                      f"Gen {gen}: {len(survivors)}S/{len(killed)}K, "
                      f"B={best_b:.3f}, Δ={delta:.3f}")

    # ── Layer 9: Pattern Evolution (post-pipeline) ─────────────────
    header("Layer 9 — Pattern Evolution")
    if state.breakthroughs:
        new_patterns = pattern_evolver.extract_patterns(
            state.breakthroughs, state.all_hypotheses, axiom_graph)
        if new_patterns:
            merged = pattern_evolver.merge_into_serendipity(serendipity)
            for p in new_patterns:
                state.evolved_patterns.append(p)
                ok(f"  NEW PATTERN: {p['name']}")
                state.add_log("pattern_evolver", "layer9",
                              f"Evolved: {p['name']}", "info")
            ok(f"Evolved {len(new_patterns)} new patterns, "
               f"merged {merged} into serendipity library "
               f"(total: {len(serendipity.patterns)})")
        else:
            info("No new patterns extracted (need more diverse breakthroughs)")
    else:
        info("No breakthroughs yet — pattern evolution deferred")

    # ── Final summary ──────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(f"\n{C.BOLD}{C.CYAN}{'═'*70}")
    print(f"  PIPELINE COMPLETE — V{VERSION}")
    print(f"{'═'*70}{C.RESET}")
    ok(f"Generations: {state.generation}")
    ok(f"Total hypotheses: {len(state.all_hypotheses)}")
    ok(f"Survivors: {len(state.survivors)}")
    ok(f"Killed: {len(state.killed)}")
    ok(f"Breakthroughs: {len(state.breakthroughs)}")
    ok(f"Serendipity injections: {len(state.serendipity_injections)}")
    ok(f"Recombinations: {len(state.recombinations)}")
    ok(f"3-Way Syntheses: {len(state.three_way_syntheses)}")
    ok(f"Reality-Sync validations: {len(state.reality_sync_results)}")
    ok(f"Paradigm shifts: {len(state.paradigm_shifts)}")
    ok(f"Evolved patterns: {len(state.evolved_patterns)}")
    ok(f"Resurrections: {len(state.resurrections)}")
    ok(f"Elapsed: {elapsed:.1f}s")
    graph_stats = axiom_graph.stats()
    ok(f"Axiom graph: {graph_stats['total']} nodes, "
       f"{graph_stats['edges']} edges")
    ok(f"Domains: {', '.join(graph_stats['domains'])}")


# ══════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD GENERATOR
# ══════════════════════════════════════════════════════════════════════════

def generate_html(state: V8State, axiom_graph: AxiomGraph) -> str:
    """Generate V8 interactive dashboard HTML."""

    # Prepare data for JS
    genealogy = axiom_graph.get_genealogy()
    graph_stats = axiom_graph.stats()

    survivors_html = ""
    for h in state.survivors:
        symbol = h.tier_symbol
        b = h.b_score()
        scores_str = " | ".join(f"{k}={v:.2f}" for k, v in h.scores.items())
        domain_badge = f'<span class="domain-badge">{html_mod.escape(h.domain)}</span>'
        temp_badge = f'<span class="temp-badge temp-{h.temperature_tier}">{h.temperature_tier}</span>'

        protocol = h.experimental_protocol
        protocol_html = ""
        if protocol:
            protocol_html = f"""<div class="protocol">
                <b>Experimental Protocol</b> ({html_mod.escape(protocol.get('type',''))}):<br>
                {html_mod.escape(protocol.get('description','')[:300])}<br>
                <em>If false:</em> {html_mod.escape(protocol.get('expected_result_if_false',''))}<br>
                <em>If true:</em> {html_mod.escape(protocol.get('surprising_result_if_true',''))}
            </div>"""

        survivors_html += f"""<div class="hypo-card tier-{h.tier.lower().replace(' ','_')}">
            <div class="hypo-header">
                <span class="tier-symbol">{symbol}</span>
                <span class="b-score">B={b:.3f}</span>
                {domain_badge} {temp_badge}
                <span class="gen-label">Gen {h.generation}</span>
            </div>
            <div class="hypo-claim">{html_mod.escape(h.claim)}</div>
            <div class="hypo-prediction"><b>Prediction:</b> {html_mod.escape(h.testable_prediction)}</div>
            <div class="hypo-scores">{scores_str}</div>
            {protocol_html}
        </div>\n"""

    killed_html = ""
    for h in state.killed[-20:]:
        falsi = h.falsification
        killed_html += f"""<div class="hypo-card killed">
            <div class="hypo-header">
                <span class="tier-symbol">💀</span>
                <span class="b-score">B={h.b_score():.3f}</span>
                <span class="gen-label">Gen {h.generation}</span>
            </div>
            <div class="hypo-claim">{html_mod.escape(h.claim)}</div>
            <div class="kill-reason"><b>Attack:</b> {html_mod.escape(falsi.get('logical_attack','')[:200])}</div>
            {f'<div class="counter"><b>Counter:</b> {html_mod.escape(h.counter_hypothesis[:200])}</div>' if h.counter_hypothesis else ''}
        </div>\n"""

    log_html = ""
    for entry in state.log_entries[-50:]:
        cls = entry.get("type", "info")
        log_html += f"""<div class="log-entry log-{cls}">
            <span class="log-phase">{html_mod.escape(entry['phase'])}</span>
            <span class="log-agent">{html_mod.escape(entry['agent'])}</span>
            {html_mod.escape(entry['msg'][:200])}
        </div>\n"""

    interrupts_html = ""
    for intr in state.interrupts[-20:]:
        interrupts_html += f"""<div class="interrupt int-{intr['type']}">
            [{intr['type'].upper()}] {html_mod.escape(intr['msg'][:200])}
        </div>\n"""

    # Genealogy data for D3
    genealogy_json = json.dumps(genealogy, ensure_ascii=False)
    b_history_json = json.dumps(state.b_history)
    delta_json = json.dumps(state.delta_novelty_history)
    kill_rate_json = json.dumps(state.kill_rate_history)

    bt_count = len(state.breakthroughs)
    best_b = max(state.b_history) if state.b_history else 0
    avg_kill = sum(state.kill_rate_history) / max(len(state.kill_rate_history), 1)

    # Pre-build sidebar HTML for new layers (avoid backslash-in-fstring issues)
    paradigm_shifts_html = ""
    if state.paradigm_shifts:
        for s in state.paradigm_shifts[-5:]:
            stype = html_mod.escape(s.get("type", "?"))
            sclaim = html_mod.escape(s.get("trigger_claim", "")[:80])
            paradigm_shifts_html += (
                f'<div style="font-size:11px;padding:2px 0;">'
                f'<span style="color:var(--accent6)">[{stype}]</span> '
                f'<span style="color:var(--text2)">{sclaim}</span></div>\n')
    else:
        paradigm_shifts_html = '<div style="color:var(--text3);font-size:11px">None detected</div>'

    evolved_patterns_html = ""
    if state.evolved_patterns:
        for p in state.evolved_patterns[-5:]:
            pname = html_mod.escape(p.get("name", ""))
            evolved_patterns_html += (
                f'<div style="font-size:11px;color:var(--accent1);padding:2px 0;">{pname}</div>\n')
    else:
        evolved_patterns_html = '<div style="color:var(--text3);font-size:11px">None yet</div>'

    reality_sync_summary = f"{len(state.reality_sync_results)} validated"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Breakthrough Engine V{VERSION} — Evolutionary Discovery Dashboard</title>
<style>
:root {{
  --bg: #0a0e14; --surface: #111820; --surface2: #1a2230;
  --border: #2a3545; --border2: #3a4a60;
  --text: #c8d0dc; --text2: #8892a0; --text3: #5c6670;
  --accent1: #00e5a0; --accent2: #00b4d8; --accent3: #ff6b6b;
  --accent4: #ffd93d; --accent5: #c77dff; --accent6: #ff8c42;
  --mono: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  --sans: 'Inter', -apple-system, sans-serif;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background:var(--bg); color:var(--text); font-family:var(--sans);
  font-size:13px; line-height:1.6;
}}
.dashboard {{ display:grid; grid-template-columns:1fr 320px; min-height:100vh; }}
.main {{ padding:20px 24px; overflow-y:auto; }}
.sidebar {{ background:var(--surface); border-left:1px solid var(--border);
  padding:16px; overflow-y:auto; }}

h1 {{ font-size:20px; color:var(--accent1); margin-bottom:4px;
  font-family:var(--mono); letter-spacing:-0.5px; }}
.subtitle {{ color:var(--text2); font-size:12px; margin-bottom:20px; }}
.version {{ color:var(--accent5); font-family:var(--mono); }}

/* Tabs */
.tabs {{ display:flex; gap:2px; margin-bottom:16px; flex-wrap:wrap; }}
.tab {{
  padding:6px 14px; background:var(--surface2); border:1px solid var(--border);
  color:var(--text2); cursor:pointer; font-size:12px; font-family:var(--mono);
  border-radius:4px 4px 0 0; transition:all 0.15s;
}}
.tab:hover {{ color:var(--text); background:var(--surface); }}
.tab.active {{ color:var(--accent1); border-bottom-color:var(--bg);
  background:var(--bg); }}
.tab-panel {{ display:none; }}
.tab-panel.active {{ display:block; }}

/* Stats cards */
.stats-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px;
  margin-bottom:16px; }}
.stat-card {{
  background:var(--surface2); border:1px solid var(--border);
  padding:12px; border-radius:6px; text-align:center;
}}
.stat-value {{ font-size:24px; font-family:var(--mono); font-weight:700; }}
.stat-label {{ font-size:10px; color:var(--text2); text-transform:uppercase;
  letter-spacing:0.5px; }}

/* Hypothesis cards */
.hypo-card {{
  background:var(--surface2); border:1px solid var(--border);
  padding:14px; border-radius:6px; margin-bottom:10px;
}}
.hypo-card.killed {{ border-color:var(--accent3); opacity:0.7; }}
.hypo-card.tier-breakthrough_candidate {{ border-color:var(--accent1);
  box-shadow:0 0 12px rgba(0,229,160,0.15); }}
.hypo-card.tier-conditional_breakthrough {{ border-color:var(--accent4); }}
.hypo-card.tier-theory_proposal {{ border-color:var(--accent2); }}
.hypo-header {{ display:flex; align-items:center; gap:8px; margin-bottom:6px;
  flex-wrap:wrap; }}
.tier-symbol {{ font-size:16px; }}
.b-score {{ font-family:var(--mono); color:var(--accent1); font-size:13px;
  font-weight:700; }}
.gen-label {{ font-size:11px; color:var(--text3); font-family:var(--mono); }}
.domain-badge {{
  font-size:10px; padding:2px 6px; border-radius:3px;
  background:var(--accent5); color:#000; font-weight:600;
}}
.temp-badge {{
  font-size:10px; padding:2px 6px; border-radius:3px; font-weight:600;
}}
.temp-conservative {{ background:var(--accent2); color:#000; }}
.temp-balanced {{ background:var(--accent4); color:#000; }}
.temp-wild {{ background:var(--accent3); color:#000; }}
.temp-recombination {{ background:var(--accent6); color:#000; }}
.temp-synthesis {{ background:linear-gradient(135deg, var(--accent1), var(--accent5)); color:#000; }}
.temp-resurrection {{ background:var(--accent5); color:#000; }}
.hypo-claim {{ margin-bottom:6px; }}
.hypo-prediction {{ font-size:12px; color:var(--text2); margin-bottom:4px; }}
.hypo-scores {{ font-size:11px; color:var(--text3); font-family:var(--mono); }}
.protocol {{
  font-size:11px; color:var(--text2); margin-top:8px; padding:8px;
  background:var(--surface); border-radius:4px;
}}
.kill-reason {{ font-size:12px; color:var(--accent3); margin-top:4px; }}
.counter {{ font-size:12px; color:var(--accent4); margin-top:4px; }}

/* Log */
.log-entry {{
  font-family:var(--mono); font-size:11px; padding:3px 8px;
  border-left:3px solid var(--border);
}}
.log-info {{ border-left-color:var(--accent2); }}
.log-kill {{ border-left-color:var(--accent3); }}
.log-error {{ border-left-color:var(--accent3); background:rgba(255,107,107,0.05); }}
.log-phase {{ color:var(--accent5); margin-right:6px; }}
.log-agent {{ color:var(--accent4); margin-right:6px; }}

/* Interrupts */
.interrupt {{
  padding:6px 10px; margin-bottom:4px; border-radius:4px;
  font-size:11px; font-family:var(--mono);
}}
.int-info {{ background:rgba(0,180,216,0.1); color:var(--accent2); }}
.int-warn {{ background:rgba(255,217,61,0.1); color:var(--accent4); }}
.int-crit {{ background:rgba(255,107,107,0.15); color:var(--accent3); }}

/* Sidebar */
.sidebar h3 {{
  font-size:12px; text-transform:uppercase; letter-spacing:0.5px;
  color:var(--text2); margin:12px 0 6px; padding-bottom:4px;
  border-bottom:1px solid var(--border);
}}
.gauge {{
  background:var(--surface2); border:1px solid var(--border);
  padding:8px; border-radius:4px; margin-bottom:6px; text-align:center;
}}
.gauge-value {{ font-size:20px; font-family:var(--mono); font-weight:700; }}
.gauge-label {{ font-size:10px; color:var(--text2); }}

/* Genealogy tree */
#genealogy-tree {{
  width:100%; min-height:400px; background:var(--surface);
  border:1px solid var(--border); border-radius:6px;
}}
.tree-node {{
  fill:var(--accent2); stroke:var(--border); stroke-width:1;
}}
.tree-node.alive {{ fill:var(--accent1); }}
.tree-node.falsified {{ fill:var(--accent3); }}
.tree-node.dormant {{ fill:var(--accent4); }}

/* Sparkline canvas */
canvas.spark {{ width:100%; height:40px; }}

/* Chart */
#b-chart {{ width:100%; height:120px; }}

@media (max-width:900px) {{
  .dashboard {{ grid-template-columns:1fr; }}
  .sidebar {{ border-left:none; border-top:1px solid var(--border); }}
  .stats-row {{ grid-template-columns:repeat(2,1fr); }}
}}
</style>
</head>
<body>
<div class="dashboard">
<div class="main">
  <h1>Breakthrough Engine <span class="version">V{VERSION}</span></h1>
  <div class="subtitle">
    Evolutionary Autonomous Discovery · {state.mode} · {html_mod.escape(state.target)} ·
    {state.generation} generations · {html_mod.escape(state.model)} ·
    Session {state.session_id[:8]}
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-value" style="color:var(--accent1)">{bt_count}</div>
      <div class="stat-label">Breakthroughs</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:var(--accent2)">{len(state.survivors)}</div>
      <div class="stat-label">Survivors</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:var(--accent3)">{len(state.killed)}</div>
      <div class="stat-label">Killed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:var(--accent4)">{best_b:.3f}</div>
      <div class="stat-label">Best B Score</div>
    </div>
  </div>

  <div class="tabs">
    <div class="tab active" onclick="showTab('survivors')">★ Survivors</div>
    <div class="tab" onclick="showTab('graveyard')">💀 Graveyard</div>
    <div class="tab" onclick="showTab('genealogy')">🌳 Genealogy</div>
    <div class="tab" onclick="showTab('log')">📋 Log</div>
    <div class="tab" onclick="showTab('graph-stats')">🕸 Graph</div>
    <div class="tab" onclick="showTab('visuals')">📊 Visuals</div>
  </div>

  <div id="tab-survivors" class="tab-panel active">
    {survivors_html if survivors_html else '<div style="color:var(--text3);padding:20px">No survivors yet.</div>'}
  </div>

  <div id="tab-graveyard" class="tab-panel">
    {killed_html if killed_html else '<div style="color:var(--text3);padding:20px">No kills yet.</div>'}
  </div>

  <div id="tab-genealogy" class="tab-panel">
    <div id="genealogy-tree"></div>
  </div>

  <div id="tab-log" class="tab-panel">
    {log_html if log_html else '<div style="color:var(--text3);padding:20px">No log entries.</div>'}
  </div>

  <div id="tab-graph-stats" class="tab-panel">
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value" style="color:var(--accent1)">{graph_stats['alive']}</div>
        <div class="stat-label">Alive Nodes</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--accent3)">{graph_stats['falsified']}</div>
        <div class="stat-label">Falsified</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--accent4)">{graph_stats['dormant']}</div>
        <div class="stat-label">Dormant</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--accent2)">{graph_stats['edges']}</div>
        <div class="stat-label">Edges</div>
      </div>
    </div>
    <div style="color:var(--text2); font-size:12px; padding:10px;">
      <b>Domains:</b> {', '.join(graph_stats['domains']) if graph_stats['domains'] else 'none'}<br>
      <b>Serendipity injections:</b> {len(state.serendipity_injections)}<br>
      <b>Recombinations:</b> {len(state.recombinations)}<br>
      <b>3-Way Syntheses:</b> {len(state.three_way_syntheses)}<br>
      <b>Resurrections:</b> {len(state.resurrections)}<br>
      <b>Paradigm shifts:</b> {len(state.paradigm_shifts)}<br>
      <b>Reality-Sync validations:</b> {len(state.reality_sync_results)}<br>
      <b>Evolved patterns:</b> {len(state.evolved_patterns)}<br>
      <b>Stagnation events:</b> {state.stagnation_count}
    </div>
  </div>

  <div id="tab-visuals" class="tab-panel">
    <h3 style="color:var(--accent2); margin-bottom:8px;">B-Score History</h3>
    <canvas id="b-chart"></canvas>
    <h3 style="color:var(--accent4); margin:12px 0 8px;">Delta-Novelty</h3>
    <canvas id="delta-chart" style="width:100%;height:100px;"></canvas>
    <h3 style="color:var(--accent3); margin:12px 0 8px;">Kill Rate</h3>
    <canvas id="kill-chart" style="width:100%;height:100px;"></canvas>
  </div>
</div>

<div class="sidebar">
  <h3>Gauges</h3>
  <div class="gauge">
    <div class="gauge-value" style="color:var(--accent1)">{best_b:.3f}</div>
    <div class="gauge-label">Best B Score</div>
  </div>
  <div class="gauge">
    <div class="gauge-value" style="color:var(--accent3)">{avg_kill:.0%}</div>
    <div class="gauge-label">Avg Kill Rate</div>
  </div>
  <div class="gauge">
    <div class="gauge-value" style="color:var(--accent4)">{bt_count}</div>
    <div class="gauge-label">★ Candidates</div>
  </div>
  <div class="gauge">
    <div class="gauge-value" style="color:var(--accent5)">{graph_stats['total']}</div>
    <div class="gauge-label">Graph Nodes</div>
  </div>

  <h3>Serendipity</h3>
  {''.join(f'<div style="font-size:11px;color:var(--text2);padding:2px 0;">Gen {s["generation"]}: {html_mod.escape(s["pattern"])}</div>' for s in state.serendipity_injections[-8:])}

  <h3>Paradigm Shifts</h3>
  {paradigm_shifts_html}

  <h3>Evolved Patterns</h3>
  {evolved_patterns_html}

  <h3>Interrupts</h3>
  {interrupts_html if interrupts_html else '<div style="color:var(--text3);font-size:11px">None</div>'}

  <h3>Architecture (V{VERSION})</h3>
  <div style="font-size:10px; color:var(--text3); font-family:var(--mono); line-height:1.8;">
    L0 Serendipity Injection<br>
    L1 Ingestion / Seed Context<br>
    L2 Encoder / Context Compress<br>
    L3 Conjecture Engine (3-temp)<br>
    L4 Adversarial Falsifier ⚡<br>
    L5 Counter-Hypothesis Gen<br>
    <span style="color:var(--accent1)">L5.5 Reality-Sync ⚙</span><br>
    <span style="color:var(--accent6)">L6 Synthesis Chamber (3-way)</span><br>
    <span style="color:var(--accent4)">L6.5 Paradigm Shift Detector</span><br>
    L7 Axiom Graph Updater<br>
    L8 Synthesis Controller<br>
    <span style="color:var(--accent5)">L9 Pattern Evolver ✧</span>
  </div>
</div>
</div>

<script>
// ── Tab switching ──────────────────────────────────────────────────────
function showTab(name) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');

  // Re-draw charts when visuals tab shown
  if (name === 'visuals') drawCharts();
  if (name === 'genealogy') drawGenealogy();
}}

// ── Chart drawing ──────────────────────────────────────────────────────
const bHistory = {b_history_json};
const deltaHistory = {delta_json};
const killHistory = {kill_rate_json};

function drawSparkline(canvasId, data, color, maxVal) {{
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data.length) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width = canvas.clientWidth * 2;
  const H = canvas.height = canvas.clientHeight * 2;
  ctx.scale(2, 2);
  const w = W/2, h = H/2;

  ctx.clearRect(0, 0, w, h);
  const mx = maxVal || Math.max(...data, 0.01);
  const step = w / Math.max(data.length - 1, 1);

  // Fill
  ctx.beginPath();
  ctx.moveTo(0, h);
  data.forEach((v, i) => ctx.lineTo(i * step, h - (v / mx) * h * 0.9));
  ctx.lineTo((data.length - 1) * step, h);
  ctx.closePath();
  ctx.fillStyle = color + '15';
  ctx.fill();

  // Line
  ctx.beginPath();
  data.forEach((v, i) => {{
    const x = i * step, y = h - (v / mx) * h * 0.9;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }});
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Dots
  data.forEach((v, i) => {{
    ctx.beginPath();
    ctx.arc(i * step, h - (v / mx) * h * 0.9, 2, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }});
}}

function drawCharts() {{
  drawSparkline('b-chart', bHistory, '#00e5a0', 1);
  drawSparkline('delta-chart', deltaHistory, '#ffd93d', 1);
  drawSparkline('kill-chart', killHistory, '#ff6b6b', 1);
}}

// ── Genealogy tree ─────────────────────────────────────────────────────
const genealogyData = {genealogy_json};

function drawGenealogy() {{
  const container = document.getElementById('genealogy-tree');
  if (!genealogyData.length) {{
    container.innerHTML = '<div style="color:var(--text3);padding:20px">No genealogy data yet.</div>';
    return;
  }}

  // Build a simple hierarchical visualization
  const byGen = {{}};
  genealogyData.forEach(n => {{
    if (!byGen[n.generation]) byGen[n.generation] = [];
    byGen[n.generation].push(n);
  }});

  const gens = Object.keys(byGen).sort((a, b) => a - b);
  let html = '<div style="padding:16px;overflow-x:auto;">';

  gens.forEach(g => {{
    html += `<div style="margin-bottom:12px;">`;
    html += `<div style="color:var(--accent5);font-family:var(--mono);font-size:11px;margin-bottom:4px;">Generation ${{g}}</div>`;
    html += `<div style="display:flex;gap:8px;flex-wrap:wrap;">`;

    byGen[g].forEach(node => {{
      const color = node.status === 'alive' ? 'var(--accent1)' :
                    node.status === 'falsified' ? 'var(--accent3)' : 'var(--accent4)';
      const symbol = node.tier === 'BREAKTHROUGH_CANDIDATE' ? '★' :
                     node.tier === 'CONDITIONAL_BREAKTHROUGH' ? '★?' :
                     node.tier === 'THEORY_PROPOSAL' ? '◆' :
                     node.status === 'falsified' ? '💀' : '○';

      html += `<div style="background:var(--surface2);border:1px solid ${{color}};
        border-radius:4px;padding:6px 8px;max-width:250px;font-size:11px;">
        <span>${{symbol}}</span>
        <span style="color:${{color}};font-family:var(--mono);font-size:10px">
          B=${{node.b_score.toFixed(3)}} c=${{node.confidence.toFixed(2)}}
        </span><br>
        <span style="color:var(--text2)">${{node.text.substring(0, 100)}}${{node.text.length > 100 ? '…' : ''}}</span>
        ${{node.parents.length ? '<br><span style="color:var(--text3);font-size:10px">← ' + node.parents.join(', ') + '</span>' : ''}}
      </div>`;
    }});

    html += `</div></div>`;
  }});

  html += '</div>';
  container.innerHTML = html;
}}

// Initial draw
if (bHistory.length) setTimeout(drawCharts, 100);
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def show_graph_stats():
    """Show axiom graph statistics."""
    graph = AxiomGraph()
    stats = graph.stats()
    print(f"\n{C.BOLD}Axiom Graph Statistics{C.RESET}")
    print(f"  Total nodes:  {stats['total']}")
    print(f"  Alive:        {stats['alive']}")
    print(f"  Falsified:    {stats['falsified']}")
    print(f"  Dormant:      {stats['dormant']}")
    print(f"  Edges:        {stats['edges']}")
    print(f"  Domains:      {', '.join(stats['domains']) if stats['domains'] else 'none'}")
    print()
    # Top nodes
    top = graph.get_seed_candidates(k=10)
    if top:
        print(f"  {C.BOLD}Top nodes by confidence × novelty:{C.RESET}")
        for n in top:
            print(f"    [{n.domain}] conf={n.confidence:.3f} nov={n.novelty_score:.2f} "
                  f"{n.tier}: {n.text[:80]}")


def main():
    parser = argparse.ArgumentParser(
        description=f"Breakthrough Engine V{VERSION} — Evolutionary Autonomous Discovery")
    parser.add_argument("--data", type=str,
                        help="JSON file for agent mode (no API calls)")
    parser.add_argument("--api-base", type=str,
                        default=os.environ.get("API_BASE", "https://api.anthropic.com"),
                        help="API endpoint (default: anthropic)")
    parser.add_argument("--api-key", type=str,
                        default=os.environ.get("ANTHROPIC_API_KEY",
                               os.environ.get("OPENAI_API_KEY", "")),
                        help="API key")
    parser.add_argument("--model", type=str,
                        default=os.environ.get("MODEL", "claude-sonnet-4-20250514"),
                        help="Model name")
    parser.add_argument("--mode", type=str,
                        choices=["AI/ML Meta-analysis", "Physics/Math", "Generic Research"],
                        default="Generic Research")
    parser.add_argument("--target", type=str, default="Autonomous Discovery")
    parser.add_argument("--iters", type=int, default=10,
                        help="Number of generations to run")
    parser.add_argument("-o", "--output", type=str,
                        help="Output HTML file")
    parser.add_argument("--show-graph", action="store_true",
                        help="Show axiom graph stats and exit")
    parser.add_argument("--archaeology", action="store_true",
                        help="Run failure archaeology scan")
    parser.add_argument("--reset", action="store_true",
                        help="Reset axiom graph and start fresh")
    parser.add_argument("--graph-path", type=str, default=str(AXIOM_GRAPH_PATH),
                        help="Path to axiom graph JSON")
    args = parser.parse_args()

    if args.show_graph:
        show_graph_stats()
        return

    if args.reset:
        for p in [AXIOM_GRAPH_PATH, FAILURE_ARCHIVE_PATH, GENEALOGY_PATH,
                  EVOLVED_PATTERNS_PATH]:
            if Path(p).exists():
                Path(p).unlink()
                print(f"{C.YELLOW}  Reset: {p}{C.RESET}")
        # Also clean reality-sync scripts
        if REALITY_SYNC_PATH.exists():
            import shutil
            shutil.rmtree(REALITY_SYNC_PATH, ignore_errors=True)
            print(f"{C.YELLOW}  Reset: {REALITY_SYNC_PATH}/{C.RESET}")
        return

    # Initialize components
    axiom_graph = AxiomGraph(path=args.graph_path)
    serendipity = SerendipityEngine()
    failure_archive = FailureArchive()
    reality_sync = RealitySyncEngine()
    paradigm_detector = ParadigmShiftDetector()
    pattern_evolver = PatternEvolver()

    session_id = str(uuid.uuid4())[:8]
    state = V8State(
        mode=args.mode,
        target=args.target,
        model=args.model,
        session_id=session_id,
        max_iterations=args.iters,
    )

    if args.archaeology:
        if not args.api_key and not args.data:
            err("Archaeology requires API key or --data")
            sys.exit(1)
        run_archaeology(
            state, axiom_graph, failure_archive,
            api_base=args.api_base, api_key=args.api_key, model=args.model)
        axiom_graph.save()
        return

    if args.data:
        # Agent mode: from pre-generated JSON
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        iterations_data = data if isinstance(data, list) else data.get("iterations", [data])
        run_from_data(state, axiom_graph, serendipity, failure_archive,
                      iterations_data,
                      reality_sync=reality_sync,
                      paradigm_detector=paradigm_detector,
                      pattern_evolver=pattern_evolver)
    else:
        # API mode
        if not args.api_key:
            err("API key required. Set ANTHROPIC_API_KEY or use --api-key.")
            sys.exit(1)
        run_pipeline(
            state, axiom_graph, serendipity, failure_archive,
            api_base=args.api_base, api_key=args.api_key, model=args.model)

    # Generate HTML dashboard
    out_path = args.output or f"v8-results-{session_id}.html"
    html = generate_html(state, axiom_graph)
    Path(out_path).write_text(html, encoding="utf-8")
    ok(f"Dashboard: {out_path}")

    # Save genealogy
    genealogy = axiom_graph.get_genealogy()
    GENEALOGY_PATH.write_text(json.dumps(genealogy, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    ok(f"Genealogy: {GENEALOGY_PATH}")

    # Append to discovery report
    if state.breakthroughs:
        with open(REPORT_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*70}\n")
            f.write(f"Session {session_id} — {datetime.now().isoformat()}\n")
            f.write(f"Model: {args.model} | Generations: {state.generation}\n")
            f.write(f"Breakthroughs: {len(state.breakthroughs)}\n\n")
            for bt in state.breakthroughs:
                f.write(f"★ [{bt.get('tier','')}] {bt.get('claim','')}\n")
                f.write(f"  Prediction: {bt.get('testable_prediction','')}\n")
                f.write(f"  B={bt.get('scores',{}).get('N',0)*bt.get('scores',{}).get('F',0)*bt.get('scores',{}).get('E',0)*bt.get('scores',{}).get('C',0):.3f}\n\n")
        ok(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
