"""
Agent Base Classes & Specialized Agent Implementations
======================================================
Each agent is an autonomous scientific discovery unit with:
  - A role (Explorer, Theorist, Validator, Pollinator, Meta-Learner)
  - Access to the shared blackboard
  - Its own symbolic regression + evaluation pipeline
  - Domain-specific or cross-domain capabilities

The key insight: agents don't just run in parallel — they READ
each other's discoveries and build on them, creating compound
breakthroughs.
"""

import time
import random
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .blackboard import (
    Blackboard, Discovery, Analogy, MetaInsight,
    HypothesisStatus, Priority,
)


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    agent_id: str
    role: str
    domain: str
    max_iterations: int = 10
    complexity_budget: int = 20
    exploration_rate: float = 0.3  # fraction of time exploring vs exploiting
    creativity_temperature: float = 1.0  # higher = more novel mutations
    parameters: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all discovery agents."""

    def __init__(self, config: AgentConfig, blackboard: Blackboard):
        self.config = config
        self.blackboard = blackboard
        self.iteration = 0
        self.local_discoveries: list[str] = []  # IDs of own discoveries
        self.log: list[str] = []

    def _log(self, msg: str):
        entry = f"[{self.config.agent_id}:{self.iteration}] {msg}"
        self.log.append(entry)

    @abstractmethod
    def run_iteration(self) -> list[str]:
        """Run one discovery iteration. Returns list of new discovery IDs."""
        ...

    def run(self, max_iterations: int | None = None):
        """Run the agent for N iterations."""
        n = max_iterations or self.config.max_iterations
        for i in range(n):
            self.iteration = i
            self._log(f"Starting iteration {i}")
            new_ids = self.run_iteration()
            self.local_discoveries.extend(new_ids)
            self._log(f"Produced {len(new_ids)} discoveries")
        return self.local_discoveries


# ═══════════════════════════════════════════════════════════
# AGENT TYPE 1: EXPLORER (Breadth-first law discovery)
# ═══════════════════════════════════════════════════════════

class ExplorerAgent(BaseAgent):
    """
    Explores the space of possible symbolic laws broadly.
    Uses randomized operator sets and templates to maximize coverage.
    Posts ALL promising candidates to the blackboard for others to refine.
    """

    # Common operator building blocks
    OPERATOR_POOLS = [
        ["add", "mul", "pow"],           # algebraic
        ["log", "exp", "sqrt"],          # transcendental
        ["sin", "cos", "abs"],           # periodic/nonlinear
        ["div", "sub", "neg"],           # inverse ops
    ]

    def run_iteration(self) -> list[str]:
        new_ids = []

        # Decide: explore novel operators or exploit known good ones?
        if random.random() < self.config.exploration_rate:
            ops = self._random_operator_set()
            self._log(f"EXPLORE mode: trying operators {ops}")
        else:
            ops = self._best_known_operators()
            self._log(f"EXPLOIT mode: using best operators {ops}")

        # Generate candidate laws via symbolic regression
        candidates = self._symbolic_search(ops)

        for expr, accuracy, complexity, r2 in candidates:
            disc_id = self.blackboard.post_discovery(
                agent_id=self.config.agent_id,
                domain=self.config.domain,
                law_expression=expr,
                accuracy=accuracy,
                complexity=complexity,
                r_squared=r2,
                metadata={"operators": ops, "mode": "exploration"},
            )
            new_ids.append(disc_id)

        return new_ids

    def _random_operator_set(self) -> list[str]:
        """Pick a random combination of operator pools."""
        n_pools = random.randint(1, len(self.OPERATOR_POOLS))
        pools = random.sample(self.OPERATOR_POOLS, n_pools)
        return [op for pool in pools for op in pool]

    def _best_known_operators(self) -> list[str]:
        """Extract operators from the best discoveries so far."""
        top = self.blackboard.get_top_discoveries(
            domain=self.config.domain, n=5
        )
        if not top:
            return self.OPERATOR_POOLS[0]
        # Extract operators from metadata
        all_ops = set()
        for d in top:
            all_ops.update(d.metadata.get("operators", []))
        return list(all_ops) or self.OPERATOR_POOLS[0]

    def _symbolic_search(self, operators: list[str]):
        """
        Placeholder for actual symbolic regression call.
        In production, this calls PySR or the brute-force enumerator.
        Returns list of (expression, accuracy, complexity, r_squared).
        """
        # This would call the actual symbolic regression engine
        # For the framework, we show the interface
        return []


# ═══════════════════════════════════════════════════════════
# AGENT TYPE 2: REFINER (Depth-first law improvement)
# ═══════════════════════════════════════════════════════════

class RefinerAgent(BaseAgent):
    """
    Takes existing discoveries from the blackboard and tries to
    improve them through:
      - Constant optimization (fine-tune coefficients)
      - Term addition/removal (add/remove one operator)
      - Symmetry detection (simplify using invariants)
    """

    def run_iteration(self) -> list[str]:
        new_ids = []

        # Get top unrefined discoveries
        candidates = self.blackboard.get_top_discoveries(
            domain=self.config.domain, n=10
        )
        candidates = [d for d in candidates if d.status == HypothesisStatus.PROPOSED]

        for disc in candidates[:3]:  # refine top 3 per iteration
            self._log(f"Refining: {disc.law_expression}")
            refined = self._refine_law(disc)
            if refined:
                expr, accuracy, complexity, r2 = refined
                if accuracy > disc.accuracy or (
                    accuracy >= disc.accuracy * 0.98 and complexity < disc.complexity
                ):
                    new_id = self.blackboard.post_discovery(
                        agent_id=self.config.agent_id,
                        domain=self.config.domain,
                        law_expression=expr,
                        accuracy=accuracy,
                        complexity=complexity,
                        r_squared=r2,
                        metadata={"refined_from": disc.id, "method": "refinement"},
                        parent_id=disc.id,
                    )
                    new_ids.append(new_id)
                    self._log(f"Improved: {accuracy:.4f} (was {disc.accuracy:.4f})")

        return new_ids

    def _refine_law(self, discovery: Discovery):
        """
        Attempt to refine a law. In production, this would:
        1. Parse the expression
        2. Optimize constants via scipy.optimize
        3. Try adding/removing terms
        4. Check for simplification opportunities
        Returns (expression, accuracy, complexity, r_squared) or None.
        """
        return None


# ═══════════════════════════════════════════════════════════
# AGENT TYPE 3: ADVERSARY (Validates & falsifies)
# ═══════════════════════════════════════════════════════════

class AdversaryAgent(BaseAgent):
    """
    The adversarial reviewer. Tries to BREAK every discovery by:
      - Generating adversarial test cases
      - Checking dimensional consistency
      - Testing edge cases / boundary conditions
      - Running counterexample searches
      - Checking for data leakage / overfitting
    """

    def run_iteration(self) -> list[str]:
        # Review unreviewed discoveries
        all_disc = self.blackboard.get_top_discoveries(n=20)
        unreviewed = [
            d for d in all_disc
            if not any(r["reviewer"] == self.config.agent_id for r in d.reviews)
            and d.agent_id != self.config.agent_id  # don't self-review
        ]

        for disc in unreviewed[:5]:
            self._log(f"Reviewing: {disc.law_expression}")
            verdict, score, comments = self._adversarial_review(disc)
            self.blackboard.add_review(
                discovery_id=disc.id,
                reviewer_agent_id=self.config.agent_id,
                verdict=verdict,
                score=score,
                comments=comments,
            )
            self._log(f"Verdict: {verdict} ({score:.2f})")

        return []  # adversary doesn't produce discoveries

    def _adversarial_review(self, discovery: Discovery):
        """
        Adversarial review pipeline:
        1. Dimensional consistency check
        2. Counterexample search (500+ randomly sampled edge cases)
        3. Overfitting detection (train/test gap analysis)
        4. Triviality check (is it just a constant? linear fit?)
        5. Robustness (perturb coefficients ±10%, check accuracy stability)

        Returns (verdict, score, comments).
        """
        # Framework placeholder — in production this calls
        # evaluation.py's counterexample_search, dimensional_check, etc.
        return ("needs_more_data", 0.5, "Framework placeholder")


# ═══════════════════════════════════════════════════════════
# AGENT TYPE 4: CROSS-POLLINATOR (Transfers across domains)
# ═══════════════════════════════════════════════════════════

class CrossPollinatorAgent(BaseAgent):
    """
    THE KEY TO EXPONENTIAL BREAKTHROUGHS.

    This agent doesn't discover laws — it discovers ANALOGIES between
    domains. When a law works in domain A, the pollinator asks:
    "What would the structural equivalent be in domain B?"

    Example: If exoplanet stability ~ Δ_Hill^3, does material stability
    follow a similar cubic relationship with its analogous separation metric?

    Transfer mechanisms:
    1. Structural homomorphism: map variables across domains
    2. Exponent transfer: if power-law ∝ x^α in domain A, try x^α in B
    3. Operator pattern: if log(x/y) works in A, try log-ratios in B
    4. Complexity signature: if 3-op laws dominate A, constrain B to 3-op
    """

    def __init__(self, config: AgentConfig, blackboard: Blackboard,
                 domain_mappings: dict[str, dict[str, str]]):
        super().__init__(config, blackboard)
        # Maps variables between domains
        # e.g., {"exoplanet→materials": {"delta_hill": "tolerance_factor", ...}}
        self.domain_mappings = domain_mappings

    def run_iteration(self) -> list[str]:
        new_ids = []

        # Find validated discoveries in all domains
        for domain in self.blackboard.domain_stats:
            validated = self.blackboard.get_top_discoveries(
                domain=domain, n=5, status=HypothesisStatus.VALIDATED
            )
            for disc in validated:
                analogies = self._find_analogies(disc)
                for analogy in analogies:
                    self.blackboard.post_analogy(analogy)
                    self._log(
                        f"Analogy: {disc.domain}→{analogy.target_domain} "
                        f"sim={analogy.structural_similarity:.2f}"
                    )
                    # If high similarity, immediately try it
                    if analogy.structural_similarity > 0.7:
                        result = self._test_transfer(analogy)
                        if result:
                            expr, acc, comp, r2 = result
                            new_id = self.blackboard.post_discovery(
                                agent_id=self.config.agent_id,
                                domain=analogy.target_domain,
                                law_expression=expr,
                                accuracy=acc,
                                complexity=comp,
                                r_squared=r2,
                                metadata={
                                    "transfer_from": disc.domain,
                                    "source_law": disc.law_expression,
                                    "analogy_similarity": analogy.structural_similarity,
                                },
                                parent_id=disc.id,
                            )
                            new_ids.append(new_id)

        return new_ids

    def _find_analogies(self, discovery: Discovery) -> list[Analogy]:
        """
        Detect structural analogies between a discovery and other domains.
        Uses:
        1. Variable mapping tables
        2. Expression tree structure comparison
        3. Dimensional analysis pattern matching
        """
        analogies = []
        for mapping_key, var_map in self.domain_mappings.items():
            source, target = mapping_key.split("→")
            if discovery.domain != source:
                continue
            # Compute structural similarity
            transferred_expr = self._translate_expression(
                discovery.law_expression, var_map
            )
            if transferred_expr:
                analogies.append(Analogy(
                    source_domain=source,
                    target_domain=target,
                    source_law=discovery.law_expression,
                    proposed_target_law=transferred_expr,
                    structural_similarity=0.8,  # placeholder
                ))
        return analogies

    def _translate_expression(self, expr: str, var_map: dict) -> str | None:
        """Translate an expression from one domain to another using variable mapping."""
        result = expr
        for source_var, target_var in var_map.items():
            result = result.replace(source_var, target_var)
        return result if result != expr else None

    def _test_transfer(self, analogy: Analogy):
        """Test a transferred law in the target domain."""
        return None  # Placeholder


# ═══════════════════════════════════════════════════════════
# AGENT TYPE 5: META-LEARNER (Improves the process itself)
# ═══════════════════════════════════════════════════════════

class MetaLearnerAgent(BaseAgent):
    """
    THE EXPONENTIAL MULTIPLIER.

    This agent doesn't discover scientific laws — it discovers
    LAWS ABOUT DISCOVERING LAWS. It observes all other agents and:

    1. Identifies which operator combinations lead to breakthroughs
    2. Detects when complexity budgets should be tightened or relaxed
    3. Finds optimal exploration/exploitation ratios per domain
    4. Discovers that certain domain orderings accelerate transfer
    5. Identifies the "sweet spot" iteration count before diminishing returns
    6. Learns which adversarial tests are most predictive of true validity

    These meta-insights are posted to the blackboard and consumed by
    all other agents, creating a recursive improvement loop:

        Discovery → Meta-pattern → Better discovery → Better meta-pattern → ...
    """

    def run_iteration(self) -> list[str]:
        self._log("Analyzing agent performance patterns...")

        # Pattern 1: Operator effectiveness
        self._analyze_operator_success()

        # Pattern 2: Complexity sweet spot
        self._analyze_complexity_vs_accuracy()

        # Pattern 3: Cross-domain transfer success rate
        self._analyze_transfer_patterns()

        # Pattern 4: Iteration efficiency
        self._analyze_convergence_speed()

        # Pattern 5: Review predictiveness
        self._analyze_review_quality()

        return []  # meta-learner doesn't produce domain discoveries

    def _analyze_operator_success(self):
        """Which operators appear in the best discoveries?"""
        validated = self.blackboard.get_top_discoveries(
            n=50, status=HypothesisStatus.VALIDATED
        )
        falsified = self.blackboard.get_top_discoveries(
            n=50, status=HypothesisStatus.FALSIFIED
        )

        # Count operator frequencies in validated vs falsified
        valid_ops: dict[str, int] = {}
        false_ops: dict[str, int] = {}

        for d in validated:
            for op in d.metadata.get("operators", []):
                valid_ops[op] = valid_ops.get(op, 0) + 1
        for d in falsified:
            for op in d.metadata.get("operators", []):
                false_ops[op] = false_ops.get(op, 0) + 1

        # Find operators with high validated/falsified ratio
        breakthrough_ops = []
        for op in valid_ops:
            valid_rate = valid_ops.get(op, 0)
            false_rate = false_ops.get(op, 0)
            if valid_rate > false_rate * 2:
                breakthrough_ops.append(op)

        if breakthrough_ops:
            self.blackboard.post_meta_insight(MetaInsight(
                insight_type="operator_pattern",
                description=f"High-success operators: {breakthrough_ops}",
                evidence=[{"validated": valid_ops, "falsified": false_ops}],
            ))

    def _analyze_complexity_vs_accuracy(self):
        """Find the optimal complexity level."""
        all_disc = list(self.blackboard.discoveries.values())
        if len(all_disc) < 10:
            return

        # Group by complexity, find avg accuracy
        by_complexity: dict[int, list[float]] = {}
        for d in all_disc:
            by_complexity.setdefault(d.complexity, []).append(d.accuracy)

        # Find sweet spot: highest avg accuracy at lowest complexity
        best_ratio = 0
        best_complexity = None
        for comp, accs in by_complexity.items():
            if comp == 0:
                continue
            avg_acc = sum(accs) / len(accs)
            ratio = avg_acc / math.log(comp + 1)
            if ratio > best_ratio:
                best_ratio = ratio
                best_complexity = comp

        if best_complexity:
            self.blackboard.post_meta_insight(MetaInsight(
                insight_type="complexity_sweet_spot",
                description=f"Optimal complexity: {best_complexity} (acc/log(c) = {best_ratio:.3f})",
                evidence=[{"by_complexity": {k: sum(v)/len(v) for k, v in by_complexity.items()}}],
            ))

    def _analyze_transfer_patterns(self):
        """Which cross-domain transfers actually work?"""
        tested = [a for a in self.blackboard.analogies if a.tested]
        if len(tested) < 5:
            return

        success = [a for a in tested if a.result_accuracy and a.result_accuracy > 0.8]
        success_rate = len(success) / len(tested)

        # What do successful transfers have in common?
        if success:
            avg_sim = sum(a.structural_similarity for a in success) / len(success)
            self.blackboard.post_meta_insight(MetaInsight(
                insight_type="transfer_pattern",
                description=(
                    f"Transfer success rate: {success_rate:.1%}. "
                    f"Successful transfers have avg similarity {avg_sim:.2f}"
                ),
                evidence=[{
                    "success_rate": success_rate,
                    "avg_similarity": avg_sim,
                    "total_tested": len(tested),
                }],
            ))

    def _analyze_convergence_speed(self):
        """How quickly does each domain converge?"""
        for domain, stats in self.blackboard.domain_stats.items():
            total = stats.get("total_discoveries", 0)
            validated = stats.get("validated", 0)
            if total > 0:
                validation_rate = validated / total
                if validation_rate < 0.1 and total > 20:
                    self.blackboard.post_meta_insight(MetaInsight(
                        insight_type="convergence_warning",
                        description=f"Domain '{domain}' has low validation rate ({validation_rate:.1%}). Consider changing operator set or relaxing constraints.",
                    ))

    def _analyze_review_quality(self):
        """Which adversarial tests best predict actual validity?"""
        # This would correlate review scores with downstream validation
        pass


# ═══════════════════════════════════════════════════════════
# AGENT TYPE 6: THEORIST (Formalizes discoveries into proofs)
# ═══════════════════════════════════════════════════════════

class TheoristAgent(BaseAgent):
    """
    Takes validated empirical laws and attempts to derive them
    from first principles, providing:
    1. Theoretical justification (why does this law hold?)
    2. Domain of validity (under what conditions?)
    3. Error bounds (how far off can it be?)
    4. Connections to known theorems
    """

    def run_iteration(self) -> list[str]:
        # Find validated discoveries lacking theoretical backing
        validated = self.blackboard.get_top_discoveries(
            n=20, status=HypothesisStatus.VALIDATED
        )
        needs_theory = [
            d for d in validated
            if "theoretical_basis" not in d.metadata
        ]

        for disc in needs_theory[:2]:
            self._log(f"Theorizing: {disc.law_expression}")
            theory = self._derive_theory(disc)
            if theory:
                disc.metadata["theoretical_basis"] = theory
                disc.status = HypothesisStatus.PROMOTED

        return []

    def _derive_theory(self, discovery: Discovery) -> dict | None:
        """
        Attempt first-principles derivation. In production:
        1. Dimensional analysis to check plausibility
        2. Taylor expansion around known equilibria
        3. Symmetry-based argument construction
        4. Connection to known scaling laws in the field
        """
        return None


# ═══════════════════════════════════════════════════════════
# FACTORY — Create agent swarms from config
# ═══════════════════════════════════════════════════════════

AGENT_REGISTRY = {
    "explorer": ExplorerAgent,
    "refiner": RefinerAgent,
    "adversary": AdversaryAgent,
    "theorist": TheoristAgent,
    "meta_learner": MetaLearnerAgent,
    # CrossPollinatorAgent requires extra args, handled separately
}


def create_agent(role: str, agent_id: str, domain: str,
                 blackboard: Blackboard, **kwargs) -> BaseAgent:
    """Factory function to create agents by role."""
    if role not in AGENT_REGISTRY:
        raise ValueError(f"Unknown role: {role}. Available: {list(AGENT_REGISTRY.keys())}")
    config = AgentConfig(agent_id=agent_id, role=role, domain=domain, **kwargs)
    return AGENT_REGISTRY[role](config, blackboard)
