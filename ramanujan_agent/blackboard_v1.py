"""
blackboard.py — Thread-safe discovery store for the Ramanujan agent.

Stores conjectures, validation results, and cross-references.
Follows the blackboard architecture pattern from multi_agent_discovery.
"""

from __future__ import annotations
import threading
import time
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any
from pathlib import Path


@dataclass
class Discovery:
    """A validated conjecture posted to the blackboard."""
    id: str
    agent_id: str
    family: str                # pi_series | continued_fraction | q_series | ...
    category: str              # conjecture | validated | proven | pattern | congruence
    expression: str
    value: float
    target: str | None = None
    error: float = float('inf')
    confidence: float = 0.0
    params: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    status: str = "proposed"   # proposed → validated → proven | falsified
    reviews: list = field(default_factory=list)
    parent_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    generation: int = 0

    @property
    def priority(self) -> float:
        category_weights = {
            "proven": 10.0,
            "validated": 7.0,
            "congruence": 8.0,
            "integer_relation": 6.0,
            "conjecture": 3.0,
            "pattern": 4.0,
        }
        return category_weights.get(self.category, 1.0) * self.confidence

    def add_review(self, reviewer_id: str, verdict: str, notes: str = ""):
        self.reviews.append({
            "reviewer": reviewer_id,
            "verdict": verdict,
            "notes": notes,
            "timestamp": time.time(),
        })
        verdicts = [r["verdict"] for r in self.reviews]
        if "falsified" in verdicts:
            self.status = "falsified"
        elif verdicts.count("confirmed") >= 2:
            self.status = "validated"
        elif "proven" in verdicts:
            self.status = "proven"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["priority"] = self.priority
        return d


class Blackboard:
    """Thread-safe central knowledge store."""

    def __init__(self, persist_path: str | None = None):
        self._lock = threading.RLock()
        self._discoveries: dict[str, Discovery] = {}
        self._by_family: dict[str, list[str]] = defaultdict(list)
        self._by_category: dict[str, list[str]] = defaultdict(list)
        self._round_log: list[dict] = []
        self._persist_path = persist_path

    def post(self, discovery: Discovery) -> str:
        with self._lock:
            if discovery.id in self._discoveries:
                # Deduplicate: keep higher-confidence version
                existing = self._discoveries[discovery.id]
                if discovery.confidence > existing.confidence:
                    self._discoveries[discovery.id] = discovery
                return discovery.id
            self._discoveries[discovery.id] = discovery
            self._by_family[discovery.family].append(discovery.id)
            self._by_category[discovery.category].append(discovery.id)
        return discovery.id

    def get(self, disc_id: str) -> Discovery | None:
        with self._lock:
            return self._discoveries.get(disc_id)

    def add_review(self, disc_id: str, reviewer: str, verdict: str, notes: str = ""):
        with self._lock:
            d = self._discoveries.get(disc_id)
            if d:
                d.add_review(reviewer, verdict, notes)

    def query(self, family: str | None = None, category: str | None = None,
              status: str | None = None, min_confidence: float = 0.0,
              limit: int = 50) -> list[Discovery]:
        with self._lock:
            results = list(self._discoveries.values())
        if family:
            results = [d for d in results if d.family == family]
        if category:
            results = [d for d in results if d.category == category]
        if status:
            results = [d for d in results if d.status == status]
        if min_confidence > 0:
            results = [d for d in results if d.confidence >= min_confidence]
        results.sort(key=lambda d: (-d.priority, -d.confidence))
        return results[:limit]

    def get_top(self, n: int = 20) -> list[Discovery]:
        with self._lock:
            results = list(self._discoveries.values())
        results.sort(key=lambda d: (-d.priority, -d.confidence))
        return results[:n]

    def get_stats(self) -> dict:
        with self._lock:
            all_d = list(self._discoveries.values())
        return {
            "total": len(all_d),
            "by_family": dict(defaultdict(int, {
                f: sum(1 for d in all_d if d.family == f)
                for f in {d.family for d in all_d}
            })),
            "by_status": dict(defaultdict(int, {
                s: sum(1 for d in all_d if d.status == s)
                for s in {d.status for d in all_d}
            })),
            "by_category": dict(defaultdict(int, {
                c: sum(1 for d in all_d if d.category == c)
                for c in {d.category for d in all_d}
            })),
            "max_confidence": max((d.confidence for d in all_d), default=0),
            "proven_count": sum(1 for d in all_d if d.status == "proven"),
            "validated_count": sum(1 for d in all_d if d.status == "validated"),
        }

    def log_round(self, round_num: int, summary: dict):
        with self._lock:
            self._round_log.append({"round": round_num, **summary})

    def get_round_log(self) -> list[dict]:
        with self._lock:
            return list(self._round_log)

    def persist(self):
        """Save state to disk."""
        if not self._persist_path:
            return
        with self._lock:
            data = {
                "discoveries": [d.to_dict() for d in self._discoveries.values()],
                "round_log": self._round_log,
                "stats": self.get_stats(),
            }
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
