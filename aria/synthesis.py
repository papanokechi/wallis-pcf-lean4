"""
Layer 5 — Cross-Domain Synthesis

Where breakthroughs emerge. Given a verified result in domain A and a
structural isomorphism to domain B, the synthesis layer does three things:

1. Unified notation mapping — translate result from domain A's notation
   into domain B's notation (semantically faithful, not just lexical)
2. Isomorphism confidence scoring — is this "accidental" or "essential"?
3. Practical translation — convert abstract results into actionable form:
   partition growth → compression algorithm, modular identity → error code,
   biological asymptotics → drug target scoring, etc.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from .ingestion import Domain
from .conjecture_engine import Conjecture
from .axiom_bank import Axiom, AxiomBank
from .encoder import EncodedObject, PartitionSignature


# ═══════════════════════════════════════════════════════════════════
#  NOTATION TRANSLATION DICTIONARY
# ═══════════════════════════════════════════════════════════════════

# Historical examples of pure math becoming applied
TRANSLATION_DICTIONARY = {
    # (math_concept_type, target_domain) → translation template
    ("partition_growth", "compression"): {
        "abstract": "f(n) ~ C·n^κ·exp(c·√n)",
        "applied": "Entropy rate H ≈ c·√(block_size) bits/symbol",
        "mechanism": "Partition count ↔ alphabet code space: each partition → codeword assignment",
        "example": "Rissanen arithmetic coding bounds via partition asymptotics",
    },
    ("modular_identity", "error_correction"): {
        "abstract": "Modular form f(τ) with transformation law f(-1/τ) = ...",
        "applied": "Self-dual code: weight enumerator = theta series of lattice",
        "mechanism": "Modular invariance ↔ MacWilliams identity on code weights",
        "example": "Golay code from E₈ lattice theta series; Leech lattice → [24,12,8] code",
    },
    ("random_matrix_spacing", "risk_model"): {
        "abstract": "GUE Tracy-Widom distribution: P(λ_max ≤ s) = F₂(s)",
        "applied": "Extreme loss exceedance: P(L > x) ~ 1 - F₂((x-μ)/σ)",
        "mechanism": "Portfolio correlation eigenvalues follow Marchenko-Pastur → Tracy-Widom tails",
        "example": "JPMorgan RiskMetrics using RMT-cleaned correlation matrices",
    },
    ("partition_entropy", "drug_binding"): {
        "abstract": "S(n) = log p(n) ~ c·√n",
        "applied": "Binding entropy ΔS_bind ~ c·√(n_contacts)",
        "mechanism": "Microstates of protein conformational ensemble ↔ partitions of contact energy",
        "example": "Entropy-enthalpy compensation in protein-ligand binding",
    },
    ("lattice_partition_fn", "materials"): {
        "abstract": "Z(β) = Σ_config exp(-β·E(config))",
        "applied": "Crystal structure stability: ΔG = -kT·ln(Z_A/Z_B)",
        "mechanism": "Lattice partition function → thermodynamic phase prediction",
        "example": "Ising model → magnetic material phase diagrams",
    },
    ("continued_fraction", "signal_processing"): {
        "abstract": "R(q) = q^(1/5) / (1 + q/(1 + q²/(1 + ...)))",
        "applied": "Filter design: CF → rational polynomial → transfer function H(z)",
        "mechanism": "Padé approximant via CF ↔ optimal IIR filter coefficients",
        "example": "Lanczos-type CF algorithms for signal extrapolation",
    },
    ("mock_theta", "quantum_gravity"): {
        "abstract": "Mock theta function: modular-like but with shadow correction",
        "applied": "Black hole microstate counting: Ω(N) ~ mock theta evaluated at q = e^(-1/N)",
        "mechanism": "Mock modularity captures wall-crossing phenomena in BPS state counting",
        "example": "OSV conjecture connecting topological string to BH entropy",
    },
    ("prime_gap_statistics", "nuclear_physics"): {
        "abstract": "Pair correlation of primes → GUE",
        "applied": "Nuclear energy level spacing → Wigner surmise P(s) ~ s·exp(-πs²/4)",
        "mechanism": "Montgomery-Dyson: zeta zeros ↔ Hermitian random matrices ↔ nuclear spectra",
        "example": "Neutron resonance peak spacing matching GUE prediction",
    },
    ("partition_entropy", "risk_model"): {
        "abstract": "S(n) = log p(n) ~ c·√n",
        "applied": "Portfolio loss entropy S(L) ~ c·√(n_assets) governs tail risk",
        "mechanism": "Partition microstate count ↔ portfolio configuration count under constraints",
        "example": "Entropy-based portfolio risk bounds via partition asymptotics",
    },
    ("partition_growth", "materials"): {
        "abstract": "p(n) ~ C·n^κ·exp(c·√n)",
        "applied": "Crystal defect configuration count follows partition asymptotics",
        "mechanism": "Lattice defect arrangements ↔ integer partitions under symmetry constraints",
        "example": "2D lattice defect enumeration matching Meinardus prediction",
    },
}


# ═══════════════════════════════════════════════════════════════════
#  ISOMORPHISM TYPES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class IsomorphismScore:
    """Scores whether a cross-domain similarity is superficial or deep."""
    is_accidental: bool  # same asymptotic class but different structure
    is_essential: bool   # same underlying object viewed differently
    confidence: float    # 0-1
    evidence: str
    translation_key: str | None = None  # key into TRANSLATION_DICTIONARY


@dataclass
class SynthesisResult:
    """Output of the cross-domain synthesis layer."""
    axiom_id: str
    source_domain: str
    target_domain: str
    notation_mapping: dict
    isomorphism: IsomorphismScore
    practical_translation: dict | None = None
    experiment_spec: str | None = None
    actionability: float = 0.0  # how directly actionable (0-1)


class CrossDomainSynthesizer:
    """Layer 5: Convert verified cross-domain results into actionable knowledge."""

    def __init__(self, axiom_bank: AxiomBank | None = None):
        self.axiom_bank = axiom_bank
        self.results: list[SynthesisResult] = []

    def synthesize(self, axiom: Axiom) -> list[SynthesisResult]:
        """Given a verified axiom, produce cross-domain synthesis results."""
        results = []

        if axiom.conjecture.family == "resonance":
            results.extend(self._synthesize_resonance(axiom))
        elif axiom.conjecture.family == "selection_rule":
            results.extend(self._synthesize_selection_rule(axiom))
        elif axiom.conjecture.family == "analogy":
            results.extend(self._synthesize_analogy(axiom))

        self.results.extend(results)
        return results

    def synthesize_all(self) -> list[SynthesisResult]:
        """Process all axioms in the bank."""
        if not self.axiom_bank:
            return []
        results = []
        for axiom in self.axiom_bank.axioms.values():
            results.extend(self.synthesize(axiom))
        return results

    def _synthesize_resonance(self, axiom: Axiom) -> list[SynthesisResult]:
        """Synthesize from a resonance (cross-domain signature match) axiom."""
        results = []
        cj = axiom.conjecture

        # Extract domain pair from source objects
        src_domains = self._extract_domains(cj)
        if len(src_domains) < 2:
            return results

        for i, (dom_a, name_a) in enumerate(src_domains):
            for j, (dom_b, name_b) in enumerate(src_domains):
                if i >= j:
                    continue

                # Notation mapping
                notation = self._map_notation(dom_a, dom_b, axiom)

                # Isomorphism scoring
                iso = self._score_isomorphism(axiom, dom_a, dom_b)

                # Practical translation
                practical = self._translate(dom_a, dom_b, axiom)

                # Experiment spec
                experiment = self._design_experiment(dom_a, dom_b, axiom, practical)

                result = SynthesisResult(
                    axiom_id=axiom.id,
                    source_domain=dom_a,
                    target_domain=dom_b,
                    notation_mapping=notation,
                    isomorphism=iso,
                    practical_translation=practical,
                    experiment_spec=experiment,
                    actionability=self._score_actionability(practical, experiment),
                )
                results.append(result)

        return results

    def _synthesize_selection_rule(self, axiom: Axiom) -> list[SynthesisResult]:
        """Synthesize from a selection rule axiom."""
        results = []
        cj = axiom.conjecture
        ev = cj.evidence
        domains = ev.get("domains", [])

        if len(domains) < 2:
            return results

        # Selection rule: L = c²/8 + κ holds across domains
        # This means the same universality class governs all
        for i, dom_a in enumerate(domains):
            for j, dom_b in enumerate(domains):
                if i >= j:
                    continue

                notation = {
                    "universal_parameter": "L = c²/8 + κ",
                    "in_" + dom_a: f"L represents growth class in {dom_a}",
                    "in_" + dom_b: f"L represents growth class in {dom_b}",
                    "implication": (
                        f"Results about L in {dom_a} automatically transfer to {dom_b} "
                        f"by preserving the Meinardus universality parameter."
                    ),
                }

                iso = IsomorphismScore(
                    is_accidental=False,
                    is_essential=True,
                    confidence=axiom.verification.confidence,
                    evidence=f"Selection rule L governs both {dom_a} and {dom_b}",
                )

                result = SynthesisResult(
                    axiom_id=axiom.id,
                    source_domain=dom_a,
                    target_domain=dom_b,
                    notation_mapping=notation,
                    isomorphism=iso,
                    actionability=0.6,
                )
                results.append(result)

        return results

    def _synthesize_analogy(self, axiom: Axiom) -> list[SynthesisResult]:
        """Synthesize from an analogy chain axiom."""
        ev = axiom.conjecture.evidence
        chain = ev.get("chain", "")
        nodes = [n.strip() for n in chain.split("→")]

        results = []
        if len(nodes) >= 2:
            notation = {
                "chain": chain,
                "start": nodes[0],
                "end": nodes[-1],
                "hops": len(nodes) - 1,
            }
            iso = IsomorphismScore(
                is_accidental=len(nodes) > 3,
                is_essential=len(nodes) <= 3,
                confidence=axiom.verification.confidence * (0.8 ** (len(nodes) - 2)),
                evidence=f"Analogy chain: {chain}",
            )
            result = SynthesisResult(
                axiom_id=axiom.id,
                source_domain=nodes[0],
                target_domain=nodes[-1],
                notation_mapping=notation,
                isomorphism=iso,
                actionability=0.3 if iso.is_essential else 0.1,
            )
            results.append(result)

        return results

    def _extract_domains(self, cj: Conjecture) -> list[tuple[str, str]]:
        """Extract domain-name pairs from conjecture statement."""
        # Parse from statement — look for domain tags
        domains = []
        statement = cj.statement
        for domain in Domain:
            if domain.value in statement.lower():
                domains.append((domain.value, domain.value))
        # Also check for known keywords
        keyword_map = {
            "partition": "partition",
            "physics": "physics",
            "finance": "finance",
            "biology": "biology",
            "integer_sequence": "integer_sequence",
            "mock_theta": "mock_theta",
        }
        for kw, dom in keyword_map.items():
            if kw in statement.lower() and (dom, dom) not in domains:
                domains.append((dom, kw))
        return domains[:5]

    def _map_notation(self, dom_a: str, dom_b: str, axiom: Axiom) -> dict:
        """Translate notation from domain A to domain B."""
        mapping = {
            "source_domain": dom_a,
            "target_domain": dom_b,
            "shared_structure": f"Meinardus class (c={axiom.c_signature:.4f}, κ={axiom.kappa_signature:.4f})",
        }

        # Domain-specific translations
        notation_A = self._domain_notation(dom_a)
        notation_B = self._domain_notation(dom_b)
        mapping["notation_A"] = notation_A
        mapping["notation_B"] = notation_B
        mapping["correspondence"] = {
            na: nb for na, nb in zip(notation_A.values(), notation_B.values())
        }

        return mapping

    def _domain_notation(self, domain: str) -> dict:
        """Return standard notation for a domain."""
        notations = {
            "partition": {
                "function": "p(n)",
                "generating_fn": "∏(1-x^k)⁻¹",
                "growth": "~ C·n^κ·exp(c·√n)",
                "parameter": "n (integer)",
            },
            "physics": {
                "function": "Z(β)",
                "generating_fn": "Σ exp(-βE)",
                "growth": "~ C·β^κ·exp(c·√β)",
                "parameter": "β (inverse temperature)",
            },
            "finance": {
                "function": "P(loss > x)",
                "generating_fn": "moment generating function M(t)",
                "growth": "~ C·x^κ·exp(c·√x)",
                "parameter": "x (loss level)",
            },
            "biology": {
                "function": "Ω(n)",
                "generating_fn": "Σ Ω(n)·x^n",
                "growth": "~ C·n^κ·exp(c·√n)",
                "parameter": "n (sequence length / contacts)",
            },
            "integer_sequence": {
                "function": "a(n)",
                "generating_fn": "A(x) = Σ a(n)·x^n",
                "growth": "~ C·n^κ·exp(c·√n)",
                "parameter": "n (index)",
            },
            "mock_theta": {
                "function": "f(q)",
                "generating_fn": "mock modular form",
                "growth": "~ C·n^κ·exp(c·√n) at q = e^(-1/n)",
                "parameter": "q (nome)",
            },
        }
        return notations.get(domain, {
            "function": "f(n)",
            "generating_fn": "F(x)",
            "growth": "~ C·n^κ·exp(c·√n)",
            "parameter": "n",
        })

    def _score_isomorphism(self, axiom: Axiom, dom_a: str, dom_b: str) -> IsomorphismScore:
        """Score whether the isomorphism is accidental or essential."""
        # Essential if: same L value AND generating functions related by known transform
        # Accidental if: same asymptotic class but different fine structure

        ev = axiom.conjecture.evidence
        L_dist = ev.get("L_distance", 1.0)

        # Tight L match → more likely essential
        if L_dist < 0.01:
            return IsomorphismScore(
                is_accidental=False, is_essential=True,
                confidence=0.8,
                evidence=f"Very tight L match: ΔL = {L_dist:.6f}",
                translation_key=self._find_translation_key(dom_a, dom_b),
            )
        elif L_dist < 0.05:
            return IsomorphismScore(
                is_accidental=False, is_essential=True,
                confidence=0.6,
                evidence=f"Good L match: ΔL = {L_dist:.6f}",
                translation_key=self._find_translation_key(dom_a, dom_b),
            )
        else:
            return IsomorphismScore(
                is_accidental=True, is_essential=False,
                confidence=0.3,
                evidence=f"Loose L match: ΔL = {L_dist:.6f}",
            )

    def _find_translation_key(self, dom_a: str, dom_b: str) -> str | None:
        """Find a matching key in the translation dictionary."""
        for (concept, target), _ in TRANSLATION_DICTIONARY.items():
            if dom_a in concept or dom_b in concept:
                if dom_a in target or dom_b in target:
                    return f"{concept}_{target}"
        return None

    # Map ARIA domains to translation dictionary concept/target tags
    _DOMAIN_CONCEPT_MAP = {
        "partition": ["partition_growth", "partition_entropy", "lattice_partition_fn"],
        "biology": ["drug_binding", "partition_entropy"],
        "finance": ["risk_model", "extreme_value"],
        "physics": ["random_matrix_spacing", "lattice_partition_fn", "prime_gap_statistics"],
        "integer_sequence": ["partition_growth", "continued_fraction"],
        "mock_theta": ["mock_theta"],
        "math_constant": ["continued_fraction"],
        "materials": ["materials", "lattice_partition_fn"],
        "signal_processing": ["signal_processing"],
        "quantum_gravity": ["quantum_gravity", "mock_theta"],
        "nuclear_physics": ["nuclear_physics", "prime_gap_statistics"],
        "error_correction": ["error_correction", "modular_identity"],
        "compression": ["compression", "partition_growth"],
    }

    def _translate(self, dom_a: str, dom_b: str, axiom: Axiom) -> dict | None:
        """Find practical translation in the dictionary."""
        # Expand domains to concept tags via the mapping
        concepts_a = self._DOMAIN_CONCEPT_MAP.get(dom_a, [dom_a])
        concepts_b = self._DOMAIN_CONCEPT_MAP.get(dom_b, [dom_b])

        for (concept, target), translation in TRANSLATION_DICTIONARY.items():
            # Forward: A concepts match source, B concepts match target
            if any(c in concept for c in concepts_a) and any(c in target for c in concepts_b):
                return {
                    "type": f"{concept} → {target}",
                    **translation,
                    "axiom_c": axiom.c_signature,
                    "axiom_kappa": axiom.kappa_signature,
                }
            # Reverse: B concepts match source, A concepts match target
            if any(c in concept for c in concepts_b) and any(c in target for c in concepts_a):
                return {
                    "type": f"{concept} → {target} (reversed)",
                    **translation,
                    "axiom_c": axiom.c_signature,
                    "axiom_kappa": axiom.kappa_signature,
                }

        return None

    def _design_experiment(self, dom_a: str, dom_b: str, axiom: Axiom,
                          practical: dict | None) -> str | None:
        """Generate an experiment design spec for the translation."""
        if not practical:
            return None

        c = axiom.c_signature
        kappa = axiom.kappa_signature
        L = axiom.L_value

        return (
            f"EXPERIMENT SPEC: Verify {practical['type']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Prediction: The universal parameter L = {L:.4f} "
            f"(from c={c:.4f}, κ={kappa:.4f}) governs both domains.\n"
            f"Abstract: {practical.get('abstract', 'N/A')}\n"
            f"Applied: {practical.get('applied', 'N/A')}\n"
            f"Mechanism: {practical.get('mechanism', 'N/A')}\n"
            f"Precedent: {practical.get('example', 'N/A')}\n"
            f"\n"
            f"Protocol:\n"
            f"  1. Compute Meinardus signature (c, κ) in domain '{dom_a}' "
            f"for 10+ independent datasets.\n"
            f"  2. Compute the same signature in domain '{dom_b}' "
            f"for 10+ independent datasets.\n"
            f"  3. Test H₀: L_A = L_B (matched to ±0.01) via bootstrap.\n"
            f"  4. If confirmed, the practical translation predicts:\n"
            f"     {practical.get('applied', 'TBD')}\n"
            f"  5. Validate practical prediction against domain '{dom_b}' benchmarks.\n"
        )

    def _score_actionability(self, practical: dict | None, experiment: str | None) -> float:
        """Score how directly actionable a synthesis result is."""
        if not practical:
            return 0.1
        score = 0.3
        if practical.get("example"):
            score += 0.3  # historical precedent exists
        if experiment:
            score += 0.2  # experiment designed
        if practical.get("mechanism"):
            score += 0.2  # mechanism understood
        return min(score, 1.0)

    def summary(self) -> dict:
        if not self.results:
            return {"total": 0}
        essential = sum(1 for r in self.results if r.isomorphism.is_essential)
        actionable = sum(1 for r in self.results if r.actionability > 0.5)
        with_experiment = sum(1 for r in self.results if r.experiment_spec)
        return {
            "total": len(self.results),
            "essential_isomorphisms": essential,
            "actionable": actionable,
            "with_experiment_spec": with_experiment,
        }
