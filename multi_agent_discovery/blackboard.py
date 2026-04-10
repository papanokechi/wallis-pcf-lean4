"""
Shared Blackboard — The Central Knowledge Store
================================================
All agents read/write to this blackboard. It stores:
  - Discovered laws (from any domain)
  - Hypotheses (proposed, under-review, validated, falsified)
  - Cross-domain analogies detected
  - Meta-insights about the discovery process itself
  - Breakthrough candidates awaiting adversarial review

The blackboard enables emergent collaboration: Agent A's discovery
in domain X can trigger Agent B's breakthrough in domain Y.
"""

import json
import threading
import time
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
from pathlib import Path


class HypothesisStatus(Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    VALIDATED = "validated"
    FALSIFIED = "falsified"
    PROMOTED = "promoted"  # cross-domain transfer candidate


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    BREAKTHROUGH = 4


@dataclass
class Discovery:
    """A single discovery posted to the blackboard."""
    id: str
    agent_id: str
    domain: str
    timestamp: float
    law_expression: str
    accuracy: float
    complexity: int
    r_squared: float
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    priority: Priority = Priority.MEDIUM
    metadata: dict = field(default_factory=dict)
    reviews: list = field(default_factory=list)
    cross_domain_transfers: list = field(default_factory=list)
    parent_discovery_id: str | None = None  # lineage tracking

    def to_dict(self):
        d = asdict(self)
        d["status"] = self.status.value
        d["priority"] = self.priority.value
        return d


@dataclass
class Analogy:
    """A cross-domain structural analogy detected by the pollinator."""
    source_domain: str
    target_domain: str
    source_law: str
    proposed_target_law: str
    structural_similarity: float  # 0-1
    tested: bool = False
    result_accuracy: float | None = None


@dataclass
class MetaInsight:
    """An insight about the discovery process itself."""
    insight_type: str  # "operator_pattern", "complexity_trend", "domain_bridge", etc.
    description: str
    evidence: list = field(default_factory=list)
    actionable: bool = True
    applied: bool = False


class Blackboard:
    """Thread-safe shared knowledge store for all agents."""

    def __init__(self, persist_path: str | None = None):
        self._lock = threading.RLock()
        self.discoveries: dict[str, Discovery] = {}
        self.analogies: list[Analogy] = []
        self.meta_insights: list[MetaInsight] = []
        self.iteration_count = 0
        self.domain_stats: dict[str, dict] = {}
        self._subscribers: list = []
        self._persist_path = persist_path

    def _generate_id(self, agent_id: str, expression: str) -> str:
        raw = f"{agent_id}:{expression}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def post_discovery(self, agent_id: str, domain: str,
                       law_expression: str, accuracy: float,
                       complexity: int, r_squared: float,
                       metadata: dict | None = None,
                       parent_id: str | None = None) -> str:
        """Post a new discovery. Returns the discovery ID."""
        with self._lock:
            disc_id = self._generate_id(agent_id, law_expression)
            discovery = Discovery(
                id=disc_id,
                agent_id=agent_id,
                domain=domain,
                timestamp=time.time(),
                law_expression=law_expression,
                accuracy=accuracy,
                complexity=complexity,
                r_squared=r_squared,
                metadata=metadata or {},
                parent_discovery_id=parent_id,
            )

            # Auto-prioritize breakthroughs
            if accuracy > 0.95 and complexity <= 5:
                discovery.priority = Priority.BREAKTHROUGH
            elif accuracy > 0.90:
                discovery.priority = Priority.HIGH

            self.discoveries[disc_id] = discovery
            self._update_domain_stats(domain)
            self._notify_subscribers("new_discovery", discovery)

            if self._persist_path:
                self._save()

            return disc_id

    def get_top_discoveries(self, domain: str | None = None,
                            n: int = 10,
                            status: HypothesisStatus | None = None) -> list[Discovery]:
        """Get top N discoveries, optionally filtered by domain and status."""
        with self._lock:
            candidates = list(self.discoveries.values())
            if domain:
                candidates = [d for d in candidates if d.domain == domain]
            if status:
                candidates = [d for d in candidates if d.status == status]
            # Sort by priority (desc), then accuracy (desc), then complexity (asc)
            candidates.sort(
                key=lambda d: (d.priority.value, d.accuracy, -d.complexity),
                reverse=True,
            )
            return candidates[:n]

    def add_review(self, discovery_id: str, reviewer_agent_id: str,
                   verdict: str, score: float, comments: str):
        """Add a review to a discovery."""
        with self._lock:
            if discovery_id not in self.discoveries:
                raise KeyError(f"Discovery {discovery_id} not found")
            disc = self.discoveries[discovery_id]
            disc.reviews.append({
                "reviewer": reviewer_agent_id,
                "verdict": verdict,
                "score": score,
                "comments": comments,
                "timestamp": time.time(),
            })
            # Auto-promote or falsify based on reviews
            if len(disc.reviews) >= 3:
                avg_score = sum(r["score"] for r in disc.reviews) / len(disc.reviews)
                if avg_score >= 0.8:
                    disc.status = HypothesisStatus.VALIDATED
                elif avg_score < 0.4:
                    disc.status = HypothesisStatus.FALSIFIED

    def post_analogy(self, analogy: Analogy):
        """Post a cross-domain analogy."""
        with self._lock:
            self.analogies.append(analogy)
            self._notify_subscribers("new_analogy", analogy)

    def post_meta_insight(self, insight: MetaInsight):
        """Post a meta-insight about the discovery process."""
        with self._lock:
            self.meta_insights.append(insight)
            self._notify_subscribers("new_meta_insight", insight)

    def get_untested_analogies(self) -> list[Analogy]:
        """Get all analogies that haven't been tested yet."""
        with self._lock:
            return [a for a in self.analogies if not a.tested]

    def get_actionable_insights(self) -> list[MetaInsight]:
        """Get meta-insights that haven't been applied yet."""
        with self._lock:
            return [m for m in self.meta_insights if m.actionable and not m.applied]

    def subscribe(self, callback):
        """Subscribe to blackboard events."""
        self._subscribers.append(callback)

    def _notify_subscribers(self, event_type: str, data: Any):
        for cb in self._subscribers:
            try:
                cb(event_type, data)
            except Exception:
                pass

    def _update_domain_stats(self, domain: str):
        domain_discs = [d for d in self.discoveries.values() if d.domain == domain]
        self.domain_stats[domain] = {
            "total_discoveries": len(domain_discs),
            "validated": sum(1 for d in domain_discs if d.status == HypothesisStatus.VALIDATED),
            "best_accuracy": max((d.accuracy for d in domain_discs), default=0),
            "min_complexity": min((d.complexity for d in domain_discs), default=999),
            "breakthrough_count": sum(1 for d in domain_discs if d.priority == Priority.BREAKTHROUGH),
        }

    def get_lineage(self, discovery_id: str) -> list[Discovery]:
        """Trace the ancestry of a discovery back to its root."""
        with self._lock:
            lineage = []
            current_id = discovery_id
            while current_id and current_id in self.discoveries:
                disc = self.discoveries[current_id]
                lineage.append(disc)
                current_id = disc.parent_discovery_id
            return list(reversed(lineage))

    def summary(self) -> dict:
        """Full blackboard summary."""
        with self._lock:
            return {
                "total_discoveries": len(self.discoveries),
                "by_status": {
                    s.value: sum(1 for d in self.discoveries.values() if d.status == s)
                    for s in HypothesisStatus
                },
                "by_domain": self.domain_stats,
                "total_analogies": len(self.analogies),
                "untested_analogies": len(self.get_untested_analogies()),
                "meta_insights": len(self.meta_insights),
                "iteration": self.iteration_count,
            }

    def _save(self):
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "discoveries": {k: v.to_dict() for k, v in self.discoveries.items()},
            "analogies": [asdict(a) for a in self.analogies],
            "meta_insights": [asdict(m) for m in self.meta_insights],
            "domain_stats": self.domain_stats,
            "iteration_count": self.iteration_count,
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
