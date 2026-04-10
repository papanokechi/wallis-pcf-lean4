"""
Layer 2 — Conjecture Engine

Leap-first engine inspired by Ramanujan's notebooks: state the result
confidently, let verification be someone else's problem.

Three conjecture generation mechanisms:
  1. Cross-domain resonance scoring — (c, κ) signature matching across domains
  2. Analogy graph traversal — multi-hop chains across domain boundaries
  3. Orphaned-formula matching — re-match lost notebook entries against new data
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Sequence

from .ingestion import DataObject, Domain
from .encoder import (
    RamanujanEncoder, EncodedObject, PartitionSignature, CFDepthScore,
)


@dataclass
class Conjecture:
    """A candidate cross-domain identity or structural relation."""
    id: str
    statement: str
    family: str  # resonance / analogy / orphan_match / selection_rule / ...
    confidence: float  # pre-verification confidence (0-1)
    source_objects: list[str] = field(default_factory=list)  # DataObject IDs
    evidence: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    generation: int = 0
    timestamp: float = 0.0
    cf_depth: int = 0  # Rogers-Ramanujan depth score

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.id:
            raw = f"{self.statement}:{self.source_objects}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════
#  ANALOGY GRAPH
# ═══════════════════════════════════════════════════════════════════

# Known cross-domain analogies (seed knowledge)
KNOWN_ANALOGIES = [
    ("partition", "statistical_mechanics",
     "Partition generating function ↔ canonical partition function Z(β)"),
    ("prime_gaps", "nuclear_energy",
     "Montgomery-Dyson: prime gap distribution ↔ GUE random matrix spacing"),
    ("modular_forms", "error_correcting_codes",
     "Lattice theta series ↔ weight enumerators of self-dual codes"),
    ("mock_theta", "black_hole_entropy",
     "Ramanujan mock theta functions ↔ black hole microstate counting"),
    ("fibonacci", "phyllotaxis",
     "Fibonacci sequence ↔ plant spiral arrangements"),
    ("catalan_numbers", "binary_trees",
     "Catalan numbers ↔ full binary tree count"),
    ("bell_numbers", "set_partitions",
     "Bell numbers ↔ set partition count"),
    ("random_matrix", "finance",
     "Marchenko-Pastur law ↔ empirical correlation matrices"),
    ("partition_asymptotics", "drug_binding",
     "Partition entropy ↔ binding affinity entropy landscapes"),
    ("extreme_value", "finance",
     "GUE Tracy-Widom ↔ extreme loss distribution"),
    ("lattice_partition", "materials",
     "Lattice partition functions ↔ crystal structure prediction"),
]


@dataclass
class AnalogyEdge:
    """An edge in the cross-domain analogy graph."""
    domain_a: str
    domain_b: str
    description: str
    confidence: float = 0.5
    is_verified: bool = False


class AnalogyGraph:
    """Graph of known and conjectured cross-domain analogies."""

    def __init__(self):
        self.edges: list[AnalogyEdge] = []
        self.nodes: set[str] = set()
        self._adjacency: dict[str, list[AnalogyEdge]] = {}
        self._seed()

    def _seed(self):
        for a, b, desc in KNOWN_ANALOGIES:
            self.add_edge(a, b, desc, confidence=0.9, verified=True)

    def add_edge(self, domain_a: str, domain_b: str, description: str,
                 confidence: float = 0.5, verified: bool = False):
        edge = AnalogyEdge(domain_a, domain_b, description, confidence, verified)
        self.edges.append(edge)
        self.nodes.add(domain_a)
        self.nodes.add(domain_b)
        self._adjacency.setdefault(domain_a, []).append(edge)
        self._adjacency.setdefault(domain_b, []).append(edge)

    def neighbors(self, node: str) -> list[tuple[str, AnalogyEdge]]:
        result = []
        for edge in self._adjacency.get(node, []):
            other = edge.domain_b if edge.domain_a == node else edge.domain_a
            result.append((other, edge))
        return result

    def multi_hop(self, start: str, max_hops: int = 3) -> list[list[tuple[str, AnalogyEdge]]]:
        """Find all paths from start up to max_hops deep."""
        paths = []
        self._dfs(start, [], set(), max_hops, paths)
        return paths

    def _dfs(self, node: str, path: list, visited: set, depth: int,
             results: list):
        if depth == 0:
            return
        for neighbor, edge in self.neighbors(node):
            if neighbor not in visited:
                new_path = path + [(neighbor, edge)]
                results.append(new_path)
                self._dfs(neighbor, new_path, visited | {neighbor}, depth - 1, results)

    def open_chain_ends(self) -> list[str]:
        """Find nodes with only one connection — open ends of analogy chains."""
        counts = {}
        for edge in self.edges:
            counts[edge.domain_a] = counts.get(edge.domain_a, 0) + 1
            counts[edge.domain_b] = counts.get(edge.domain_b, 0) + 1
        return [node for node, count in counts.items() if count == 1]


# ═══════════════════════════════════════════════════════════════════
#  CONJECTURE ENGINE
# ═══════════════════════════════════════════════════════════════════

class ConjectureEngine:
    """Layer 2: Generates conjectures via cross-domain resonance,
    analogy traversal, and orphaned-formula matching."""

    def __init__(self, encoder: RamanujanEncoder,
                 analogy_graph: AnalogyGraph | None = None):
        self.encoder = encoder
        self.graph = analogy_graph or AnalogyGraph()
        self.generation = 0
        self.all_conjectures: list[Conjecture] = []

    def generate_all(self, axiom_bank=None, lost_notebook=None) -> list[Conjecture]:
        """Run all conjecture generation strategies."""
        self.generation += 1
        conjectures = []

        conjectures.extend(self._resonance_scan())
        conjectures.extend(self._analogy_traverse())
        conjectures.extend(self._selection_rule_scan())
        conjectures.extend(self._orphan_rematch(lost_notebook))
        conjectures.extend(self._axiom_extension(axiom_bank))

        self.all_conjectures.extend(conjectures)
        return conjectures

    def _resonance_scan(self, threshold: float = 0.15) -> list[Conjecture]:
        """Strategy 1: Cross-domain resonance scoring.

        Find pairs of objects from different domains whose Meinardus signatures
        (c, κ) match within threshold. Each match becomes a conjecture:
        "Object A in domain X is isomorphic to Object B in domain Y."
        """
        matches = self.encoder.find_signature_matches(threshold=threshold)
        conjectures = []

        for obj_a, obj_b, distance in matches:
            sig_a = obj_a.partition_sig
            sig_b = obj_b.partition_sig

            statement = (
                f"Resonance: {obj_a.source.name} ({obj_a.source.domain.value}) "
                f"is structurally isomorphic to {obj_b.source.name} ({obj_b.source.domain.value}). "
                f"Signature match: L_A={sig_a.L:.4f}, L_B={sig_b.L:.4f}, "
                f"|ΔL|={distance:.6f}. "
                f"Meinardus parameters: (c_A={sig_a.c:.4f}, κ_A={sig_a.kappa:.4f}) ↔ "
                f"(c_B={sig_b.c:.4f}, κ_B={sig_b.kappa:.4f})."
            )

            # Confidence based on signature quality and distance
            quality = min(sig_a.fit_quality, sig_b.fit_quality)
            conf = quality * (1.0 - distance / threshold)

            # CF depth score: take the deeper of the two
            depth = 0
            if obj_a.cf_depth:
                depth = max(depth, obj_a.cf_depth.depth)
            if obj_b.cf_depth:
                depth = max(depth, obj_b.cf_depth.depth)

            cj = Conjecture(
                id="",
                statement=statement,
                family="resonance",
                confidence=conf,
                source_objects=[obj_a.source.id, obj_b.source.id],
                evidence={
                    "L_distance": distance,
                    "sig_a": (sig_a.c, sig_a.kappa, sig_a.L),
                    "sig_b": (sig_b.c, sig_b.kappa, sig_b.L),
                    "fit_quality_a": sig_a.fit_quality,
                    "fit_quality_b": sig_b.fit_quality,
                },
                generation=self.generation,
                cf_depth=depth,
            )
            conjectures.append(cj)

        return conjectures

    def _analogy_traverse(self, max_hops: int = 3) -> list[Conjecture]:
        """Strategy 2: Analogy graph traversal.

        Find open chain ends and look for what known structure they resemble.
        Generate conjectures about where chains should connect.
        """
        conjectures = []
        open_ends = self.graph.open_chain_ends()

        for end_node in open_ends:
            # Find multi-hop paths from this end
            paths = self.graph.multi_hop(end_node, max_hops=max_hops)

            for path in paths:
                if len(path) < 2:
                    continue

                # The chain: end_node → ... → terminal
                terminal = path[-1][0]
                chain = " → ".join([end_node] + [p[0] for p in path])
                descriptions = [p[1].description for p in path]

                # Conjecture: the chain suggests a connection between end_node and terminal
                statement = (
                    f"Analogy chain: {chain}. "
                    f"Via: {'; '.join(descriptions)}. "
                    f"Conjecture: There exists a direct structural connection "
                    f"between '{end_node}' and '{terminal}' that bypasses "
                    f"intermediate domains."
                )

                # Confidence decreases with hops
                base_conf = min(e.confidence for _, e in path)
                hop_penalty = 0.8 ** (len(path) - 1)
                conf = base_conf * hop_penalty

                cj = Conjecture(
                    id="",
                    statement=statement,
                    family="analogy",
                    confidence=conf,
                    evidence={
                        "chain": chain,
                        "hops": len(path),
                        "descriptions": descriptions,
                    },
                    generation=self.generation,
                    cf_depth=len(path),  # depth ∝ chain length
                )
                conjectures.append(cj)

        return conjectures

    def _selection_rule_scan(self) -> list[Conjecture]:
        """Strategy 3: Look for universal selection rules.

        Specifically search for the L = c²/8 + κ universality from Paper 14:
        do the encoded objects cluster on discrete L values?
        """
        conjectures = []
        L_values = {}

        for eid, enc in self.encoder.encoded.items():
            if enc.partition_sig and enc.partition_sig.fit_quality > 0.5:
                L = enc.partition_sig.L
                L_values.setdefault(round(L, 2), []).append(enc)

        # Find L values with objects from multiple domains
        for L_round, objects in L_values.items():
            domains = set(o.source.domain for o in objects)
            if len(domains) >= 2 and len(objects) >= 2:
                domain_list = ", ".join(d.value for d in domains)
                names = ", ".join(o.source.name for o in objects[:5])

                statement = (
                    f"Selection rule: Objects [{names}] from domains [{domain_list}] "
                    f"share L ≈ {L_round}, where L = c²/8 + κ is the Meinardus "
                    f"universality parameter. This suggests a deep structural "
                    f"equivalence governed by a shared selection rule."
                )

                cj = Conjecture(
                    id="",
                    statement=statement,
                    family="selection_rule",
                    confidence=0.3 * len(objects) * len(domains),
                    source_objects=[o.source.id for o in objects],
                    evidence={
                        "L_value": L_round,
                        "n_objects": len(objects),
                        "n_domains": len(domains),
                        "domains": [d.value for d in domains],
                    },
                    generation=self.generation,
                    cf_depth=3,  # selection rules are in the sweet spot
                )
                conjectures.append(cj)

        return conjectures

    def _orphan_rematch(self, lost_notebook=None) -> list[Conjecture]:
        """Strategy 4: Re-match orphaned formulas against new data.

        Periodically check if orphans in the encoder or lost notebook now
        have interpretations given the current axiom set.
        """
        conjectures = []
        orphans = self.encoder.get_orphans()

        for orphan in orphans:
            # Check if any non-orphan object has a close signature
            for eid, enc in self.encoder.encoded.items():
                if enc == orphan or not enc.partition_sig or not orphan.partition_sig:
                    continue
                if enc.modular_emb and enc.modular_emb.is_orphan:
                    continue  # don't match orphan-to-orphan

                L_dist = abs(enc.partition_sig.L - orphan.partition_sig.L)
                if L_dist < 0.2:
                    statement = (
                        f"Orphan resolution: '{orphan.source.name}' (orphaned — strong "
                        f"modular projection, no known interpretation) may be the same "
                        f"structure as '{enc.source.name}' ({enc.source.domain.value}). "
                        f"L distance: {L_dist:.6f}."
                    )
                    cj = Conjecture(
                        id="",
                        statement=statement,
                        family="orphan_match",
                        confidence=0.4 * (1.0 - L_dist / 0.2),
                        source_objects=[orphan.source.id, enc.source.id],
                        evidence={"L_distance": L_dist},
                        generation=self.generation,
                    )
                    conjectures.append(cj)

        # Also re-match lost notebook entries if provided
        if lost_notebook:
            for entry in lost_notebook.get_entries():
                for eid, enc in self.encoder.encoded.items():
                    if not enc.partition_sig:
                        continue
                    if hasattr(entry, 'partition_sig') and entry.partition_sig:
                        L_dist = abs(enc.partition_sig.L - entry.partition_sig.L)
                        if L_dist < 0.2:
                            statement = (
                                f"Lost notebook revival: Entry '{entry.id}' "
                                f"(stored gen {entry.generation}, reason: {entry.reason}) "
                                f"now matches '{enc.source.name}'. L distance: {L_dist:.6f}."
                            )
                            cj = Conjecture(
                                id="",
                                statement=statement,
                                family="orphan_match",
                                confidence=0.35,
                                source_objects=[enc.source.id],
                                evidence={
                                    "lost_notebook_id": entry.id,
                                    "L_distance": L_dist,
                                },
                                generation=self.generation,
                            )
                            conjectures.append(cj)

        return conjectures

    def _axiom_extension(self, axiom_bank=None) -> list[Conjecture]:
        """Strategy 5: Extend verified axioms to new predictions.

        High-generativity axioms suggest new conjectures by analogy.
        """
        if not axiom_bank:
            return []

        conjectures = []
        top_axioms = axiom_bank.get_top_generative(limit=5)

        for axiom in top_axioms:
            # For each high-generativity axiom, look for objects that
            # are "close but not matching"
            for eid, enc in self.encoder.encoded.items():
                if enc.source.id in axiom.source_objects:
                    continue  # already part of this axiom
                if not enc.partition_sig:
                    continue

                # Check if the object is within a wider threshold
                for src_id in axiom.source_objects:
                    if src_id in self.encoder.encoded:
                        src_enc = self.encoder.encoded[src_id]
                        if src_enc.partition_sig:
                            L_dist = abs(enc.partition_sig.L - src_enc.partition_sig.L)
                            if 0.1 < L_dist < 0.5:  # close but not matching
                                statement = (
                                    f"Axiom extension: Verified axiom '{axiom.id}' "
                                    f"(generativity={axiom.generativity}) "
                                    f"may extend to '{enc.source.name}' "
                                    f"({enc.source.domain.value}). "
                                    f"L distance from nearest axiom member: {L_dist:.4f}."
                                )
                                cj = Conjecture(
                                    id="",
                                    statement=statement,
                                    family="axiom_extension",
                                    confidence=0.25 * axiom.generativity / max(1, axiom_bank.max_generativity),
                                    source_objects=[enc.source.id],
                                    evidence={
                                        "parent_axiom": axiom.id,
                                        "L_distance": L_dist,
                                    },
                                    generation=self.generation,
                                )
                                conjectures.append(cj)

        return conjectures

    def summary(self) -> dict:
        from collections import Counter
        family_counts = Counter(c.family for c in self.all_conjectures)
        gen_counts = Counter(c.generation for c in self.all_conjectures)
        return {
            "total_conjectures": len(self.all_conjectures),
            "by_family": dict(family_counts),
            "by_generation": dict(gen_counts),
            "current_generation": self.generation,
            "analogy_graph_nodes": len(self.graph.nodes),
            "analogy_graph_edges": len(self.graph.edges),
        }
