"""
Layer 4A — Axiom Bank
Layer 4B — Lost Notebook

Axiom Bank: The system's expanding foundation. Each verified conjecture
is tagged with (c, κ) signature, domain, proof status, and a
"generativity score" measuring how many subsequent conjectures it seeded.

Lost Notebook: The philosophically most important component. Stores results
that failed verification but by a tiny margin, passed verification but have
no known interpretation, or are "too strange" (high weirdness score).
Quarantine reviewed every N iterations as axiom bank grows.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .conjecture_engine import Conjecture
from .verifier import VerificationResult, Verdict


# ═══════════════════════════════════════════════════════════════════
#  AXIOM BANK (Layer 4A)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Axiom:
    """A verified conjecture promoted to axiom status."""
    id: str
    conjecture: Conjecture
    verification: VerificationResult
    added_generation: int
    generativity: float = 0.0  # how many subsequent conjectures this seeded
    source_objects: list[str] = field(default_factory=list)
    domain: str = ""
    proof_status: str = "numeric"  # numeric / symbolic / formal
    c_signature: float = 0.0
    kappa_signature: float = 0.0
    L_value: float = 0.0
    child_ids: list[str] = field(default_factory=list)  # conjectures seeded by this axiom

    def bump_generativity(self, child_id: str):
        """Record a child conjecture seeded by this axiom."""
        self.child_ids.append(child_id)
        self.generativity = len(self.child_ids)


class AxiomBank:
    """Layer 4A: The system's expanding foundation of verified truths."""

    def __init__(self, persist_path: str | None = None):
        self.axioms: dict[str, Axiom] = {}
        self.persist_path = persist_path
        self.max_generativity: float = 0.0
        self._load()

    def add(self, conjecture: Conjecture, verification: VerificationResult,
            generation: int) -> Axiom:
        """Promote a verified conjecture to axiom status."""
        # Extract signature from evidence
        c_sig = 0.0
        kappa_sig = 0.0
        L_val = 0.0
        if conjecture.evidence:
            sig = conjecture.evidence.get("sig_a", (0, 0, 0))
            if len(sig) >= 3:
                c_sig = sig[0]
                kappa_sig = sig[1]
                L_val = sig[2]

        # Determine proof status from verification verdict
        proof_status = "numeric"
        if verification.verdict == Verdict.VERIFIED_FULL:
            proof_status = "domain_verified"
        elif verification.verdict == Verdict.VERIFIED_ADVERSARIAL:
            proof_status = "adversarial_verified"
        elif verification.verdict == Verdict.VERIFIED_SYMBOLIC:
            proof_status = "symbolic"

        axiom = Axiom(
            id=conjecture.id,
            conjecture=conjecture,
            verification=verification,
            added_generation=generation,
            source_objects=conjecture.source_objects,
            domain=conjecture.family,
            proof_status=proof_status,
            c_signature=c_sig,
            kappa_signature=kappa_sig,
            L_value=L_val,
        )
        self.axioms[axiom.id] = axiom
        self._save()
        return axiom

    def get(self, axiom_id: str) -> Axiom | None:
        return self.axioms.get(axiom_id)

    def get_top_generative(self, limit: int = 5) -> list[Axiom]:
        """Return axioms ranked by generativity (most productive first)."""
        ranked = sorted(self.axioms.values(), key=lambda a: a.generativity, reverse=True)
        if ranked:
            self.max_generativity = ranked[0].generativity
        return ranked[:limit]

    def get_by_domain(self, domain: str) -> list[Axiom]:
        return [a for a in self.axioms.values() if a.domain == domain]

    def get_by_L_range(self, L_min: float, L_max: float) -> list[Axiom]:
        return [a for a in self.axioms.values()
                if L_min <= a.L_value <= L_max]

    def bump_generativity(self, axiom_id: str, child_id: str):
        """Record that this axiom seeded a new conjecture."""
        if axiom_id in self.axioms:
            self.axioms[axiom_id].bump_generativity(child_id)
            self.max_generativity = max(
                self.max_generativity, self.axioms[axiom_id].generativity
            )

    def size(self) -> int:
        return len(self.axioms)

    def summary(self) -> dict:
        if not self.axioms:
            return {"total": 0}
        from collections import Counter
        domains = Counter(a.domain for a in self.axioms.values())
        proofs = Counter(a.proof_status for a in self.axioms.values())
        avg_gen = sum(a.generativity for a in self.axioms.values()) / len(self.axioms)
        return {
            "total": len(self.axioms),
            "by_domain": dict(domains),
            "by_proof_status": dict(proofs),
            "avg_generativity": avg_gen,
            "max_generativity": self.max_generativity,
        }

    def _save(self):
        if not self.persist_path:
            return
        p = Path(self.persist_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            aid: {
                "id": a.id,
                "statement": a.conjecture.statement,
                "family": a.conjecture.family,
                "generation": a.added_generation,
                "generativity": a.generativity,
                "proof_status": a.proof_status,
                "c": a.c_signature,
                "kappa": a.kappa_signature,
                "L": a.L_value,
                "confidence": a.verification.confidence,
            }
            for aid, a in self.axioms.items()
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if not self.persist_path:
            return
        p = Path(self.persist_path)
        if not p.exists():
            return
        # Load is best-effort for pilot
        # Full reload would need the original Conjecture/VerificationResult objects


# ═══════════════════════════════════════════════════════════════════
#  LOST NOTEBOOK (Layer 4B)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class LostNotebookEntry:
    """A quarantined result — too strange, too interesting to delete."""
    id: str
    conjecture: Conjecture
    verification: VerificationResult | None
    reason: str  # why quarantined
    generation: int  # when quarantined
    weirdness_score: float = 0.0  # how unusual
    review_count: int = 0  # times re-reviewed
    last_review_gen: int = 0
    partition_sig: object | None = None  # PartitionSignature if available
    notes: list[str] = field(default_factory=list)


class LostNotebook:
    """Layer 4B: Quarantine for results that don't fit the current paradigm.

    History shows Ramanujan's strangest results were often the most
    important ones later. The lost notebook stores:
      - Results that failed verification by a tiny margin
      - Results that passed but have no known interpretation
      - Results that passed all rounds but are "too strange"
    """

    def __init__(self, review_interval: int = 5):
        self.entries: dict[str, LostNotebookEntry] = {}
        self.review_interval = review_interval  # review every N generations

    def quarantine(self, conjecture: Conjecture,
                   verification: VerificationResult | None,
                   reason: str, generation: int,
                   weirdness: float = 0.0,
                   partition_sig=None) -> LostNotebookEntry:
        """Add a result to the lost notebook."""
        entry = LostNotebookEntry(
            id=conjecture.id,
            conjecture=conjecture,
            verification=verification,
            reason=reason,
            generation=generation,
            weirdness_score=weirdness,
            partition_sig=partition_sig,
        )
        self.entries[entry.id] = entry
        return entry

    def get_entries(self) -> list[LostNotebookEntry]:
        return list(self.entries.values())

    def get_due_for_review(self, current_generation: int) -> list[LostNotebookEntry]:
        """Return entries that should be re-reviewed this generation."""
        due = []
        for entry in self.entries.values():
            gens_since_review = current_generation - entry.last_review_gen
            if gens_since_review >= self.review_interval:
                due.append(entry)
        return due

    def mark_reviewed(self, entry_id: str, generation: int, note: str = ""):
        """Mark an entry as reviewed."""
        if entry_id in self.entries:
            self.entries[entry_id].review_count += 1
            self.entries[entry_id].last_review_gen = generation
            if note:
                self.entries[entry_id].notes.append(f"Gen {generation}: {note}")

    def promote(self, entry_id: str) -> Conjecture | None:
        """Promote a lost notebook entry back to active conjecture status."""
        if entry_id not in self.entries:
            return None
        entry = self.entries.pop(entry_id)
        entry.conjecture.metadata["revived_from_lost_notebook"] = True
        entry.conjecture.metadata["quarantine_duration"] = (
            entry.review_count
        )
        return entry.conjecture

    def get_by_weirdness(self, min_score: float = 0.5) -> list[LostNotebookEntry]:
        """Return the weirdest entries — often the most important."""
        result = [e for e in self.entries.values() if e.weirdness_score >= min_score]
        result.sort(key=lambda e: e.weirdness_score, reverse=True)
        return result

    def size(self) -> int:
        return len(self.entries)

    def summary(self) -> dict:
        if not self.entries:
            return {"total": 0}
        from collections import Counter
        reasons = Counter(e.reason for e in self.entries.values())
        avg_weird = sum(e.weirdness_score for e in self.entries.values()) / len(self.entries)
        max_reviews = max(e.review_count for e in self.entries.values())
        return {
            "total": len(self.entries),
            "by_reason": dict(reasons),
            "avg_weirdness": avg_weird,
            "max_review_count": max_reviews,
        }
