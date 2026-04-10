"""
Blackboard — Shared Knowledge Store
=====================================
Thread-safe shared memory for multi-agent collaboration.
Stores discoveries, hypotheses, counterexamples, patterns,
and proof sketches across all three problem domains.
"""

import threading
import time
import hashlib
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class Discovery:
    """A single discovery or hypothesis on the blackboard."""

    _counter = 0
    _lock = threading.Lock()

    def __init__(self, agent_id: str, domain: str, category: str,
                 content: Dict[str, Any], confidence: float = 0.0,
                 parent_ids: Optional[List[str]] = None):
        with Discovery._lock:
            Discovery._counter += 1
            self.id = f"D{Discovery._counter:06d}"

        self.agent_id = agent_id
        self.domain = domain        # 'collatz', 'erdos_straus', 'hadamard'
        self.category = category    # 'pattern', 'invariant', 'counterexample', 
                                    # 'construction', 'hypothesis', 'proof_sketch',
                                    # 'family', 'transfer'
        self.content = content
        self.confidence = confidence
        self.parent_ids = parent_ids or []
        self.timestamp = time.time()
        self.status = 'proposed'    # proposed -> validated -> refined -> proven / falsified
        self.reviews: List[Dict[str, Any]] = []
        self.priority = self._compute_priority()

    def _compute_priority(self) -> float:
        """Auto-priority based on confidence and category."""
        category_weights = {
            'proof_sketch': 10.0,
            'invariant': 8.0,
            'construction': 7.0,
            'family': 6.0,
            'pattern': 4.0,
            'hypothesis': 3.0,
            'counterexample': 9.0,  # counterexamples are critical
            'transfer': 5.0,
        }
        base = category_weights.get(self.category, 1.0)
        return base * self.confidence

    def add_review(self, reviewer_id: str, verdict: str, notes: str = ''):
        """Add a review from an adversary or validator."""
        self.reviews.append({
            'reviewer': reviewer_id,
            'verdict': verdict,  # 'confirmed', 'weakened', 'falsified', 'refined'
            'notes': notes,
            'timestamp': time.time()
        })
        # Update status based on reviews
        verdicts = [r['verdict'] for r in self.reviews]
        if 'falsified' in verdicts:
            self.status = 'falsified'
        elif verdicts.count('confirmed') >= 2:
            self.status = 'validated'
        elif 'refined' in verdicts:
            self.status = 'refined'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'domain': self.domain,
            'category': self.category,
            'content': self.content,
            'confidence': self.confidence,
            'parent_ids': self.parent_ids,
            'status': self.status,
            'priority': self.priority,
            'reviews': self.reviews,
            'timestamp': self.timestamp,
        }


class Blackboard:
    """Thread-safe shared knowledge store for multi-agent collaboration."""

    def __init__(self):
        self._lock = threading.RLock()
        self._discoveries: Dict[str, Discovery] = {}
        self._by_domain: Dict[str, List[str]] = defaultdict(list)
        self._by_category: Dict[str, List[str]] = defaultdict(list)
        self._by_agent: Dict[str, List[str]] = defaultdict(list)
        self._round_log: List[Dict[str, Any]] = []
        self._global_stats: Dict[str, Any] = {
            'total_proposed': 0,
            'total_validated': 0,
            'total_falsified': 0,
            'breakthroughs': 0,
        }

    def post(self, discovery: Discovery) -> str:
        """Post a new discovery to the blackboard."""
        with self._lock:
            self._discoveries[discovery.id] = discovery
            self._by_domain[discovery.domain].append(discovery.id)
            self._by_category[discovery.category].append(discovery.id)
            self._by_agent[discovery.agent_id].append(discovery.id)
            self._global_stats['total_proposed'] += 1
            if discovery.confidence > 0.95:
                self._global_stats['breakthroughs'] += 1
        return discovery.id

    def get(self, discovery_id: str) -> Optional[Discovery]:
        with self._lock:
            return self._discoveries.get(discovery_id)

    def query(self, domain: Optional[str] = None, category: Optional[str] = None,
              min_confidence: float = 0.0, status: Optional[str] = None,
              limit: int = 50) -> List[Discovery]:
        """Query discoveries with filters."""
        with self._lock:
            candidates = list(self._discoveries.values())

        if domain:
            candidates = [d for d in candidates if d.domain == domain]
        if category:
            candidates = [d for d in candidates if d.category == category]
        if min_confidence > 0:
            candidates = [d for d in candidates if d.confidence >= min_confidence]
        if status:
            candidates = [d for d in candidates if d.status == status]

        candidates.sort(key=lambda d: d.priority, reverse=True)
        return candidates[:limit]

    def get_top_discoveries(self, n: int = 10) -> List[Discovery]:
        """Get the highest-priority discoveries across all domains."""
        with self._lock:
            all_d = sorted(self._discoveries.values(),
                          key=lambda d: d.priority, reverse=True)
            return all_d[:n]

    def get_domain_summary(self, domain: str) -> Dict[str, Any]:
        """Summary statistics for a specific problem domain."""
        with self._lock:
            ids = self._by_domain.get(domain, [])
            discoveries = [self._discoveries[did] for did in ids
                          if did in self._discoveries]

        if not discoveries:
            return {'domain': domain, 'count': 0}

        return {
            'domain': domain,
            'count': len(discoveries),
            'by_category': defaultdict(int,
                {cat: sum(1 for d in discoveries if d.category == cat)
                 for cat in set(d.category for d in discoveries)}),
            'by_status': defaultdict(int,
                {st: sum(1 for d in discoveries if d.status == st)
                 for st in set(d.status for d in discoveries)}),
            'avg_confidence': sum(d.confidence for d in discoveries) / len(discoveries),
            'max_confidence': max(d.confidence for d in discoveries),
            'top_3': [(d.id, d.category, d.confidence) for d in
                      sorted(discoveries, key=lambda d: d.priority, reverse=True)[:3]],
        }

    def get_lineage(self, discovery_id: str) -> List[Discovery]:
        """Trace the full lineage of a discovery (parents, grandparents, etc)."""
        lineage = []
        visited = set()
        queue = [discovery_id]
        while queue:
            did = queue.pop(0)
            if did in visited:
                continue
            visited.add(did)
            d = self.get(did)
            if d:
                lineage.append(d)
                queue.extend(d.parent_ids)
        return lineage

    def log_round(self, round_num: int, summary: Dict[str, Any]):
        """Log the results of an iteration round."""
        with self._lock:
            self._round_log.append({
                'round': round_num,
                'timestamp': time.time(),
                **summary
            })

    def get_stats(self) -> Dict[str, Any]:
        """Global statistics."""
        with self._lock:
            stats = dict(self._global_stats)
            stats['total_discoveries'] = len(self._discoveries)
            stats['by_domain'] = {k: len(v) for k, v in self._by_domain.items()}
            stats['by_category'] = {k: len(v) for k, v in self._by_category.items()}
            stats['rounds_completed'] = len(self._round_log)
            # Count validated
            stats['total_validated'] = sum(
                1 for d in self._discoveries.values() if d.status == 'validated')
            stats['total_falsified'] = sum(
                1 for d in self._discoveries.values() if d.status == 'falsified')
        return stats

    def export(self) -> Dict[str, Any]:
        """Export entire blackboard state for serialization."""
        with self._lock:
            return {
                'discoveries': {did: d.to_dict()
                                for did, d in self._discoveries.items()},
                'stats': self.get_stats(),
                'round_log': self._round_log,
                'domain_summaries': {
                    domain: self.get_domain_summary(domain)
                    for domain in ['collatz', 'erdos_straus', 'hadamard']
                }
            }

    def compute_preregistration_hash(self) -> str:
        """SHA-256 hash of current state for pre-registration."""
        state = json.dumps(self.export(), sort_keys=True, default=str)
        return hashlib.sha256(state.encode()).hexdigest()
