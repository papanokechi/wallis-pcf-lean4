"""agents.py -- Specialised agents for the Ramanujan discovery system (v4).

v4 architecture (reviewers' redesign):
 Six dedicated agent roles forming a theorem-proving pipeline:

  ExplorerAgent        - Generates conjectures via formula templates
  ValidatorAgent       - High-precision numeric verification + stability labels
  PatternMatcherAgent  - Structural identification (Bessel/HG/algebraic/PSLQ)
  ProofPlannerAgent    - Creates proof plans with lemma lists + theorem templates
  ProofExecutorAgent   - Executes proof plans via CAS (wraps proof_engine)
  RefereeAgent         - Final review: checks lemmas, strict accept/reject

  Supporting agents (periodic):
  RefinerAgent         - Improves promising conjectures (parameter tuning)
  CrossPollinatorAgent - Transfers patterns across formula families
  MetaLearnerAgent     - Analyses discovery history, adjusts strategies

  Pipeline: Explorer → Validator → PatternMatcher → ProofPlanner → ProofExecutor → Referee
"""

from __future__ import annotations
import time
import math
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .blackboard import Blackboard, Discovery
from .generator import ConjectureGenerator, Conjecture
from .validator import Validator, ValidationResult
from .formulas import (
    _generalised_pi_series, _generalised_cf, _pslq_search,
    _compute_basis_mpf, get_all_templates, _mp,
)


@dataclass
class AgentConfig:
    agent_id: str
    agent_type: str
    exploration_rate: float = 0.6
    budget: int = 20


class BaseAgent(ABC):
    """Base class for all Ramanujan agents."""

    def __init__(self, config: AgentConfig, blackboard: Blackboard):
        self.config = config
        self.bb = blackboard
        self.iteration = 0
        self.stats = {"discoveries_posted": 0, "time_spent": 0.0, "rounds": 0}

    @abstractmethod
    def run(self, round_num: int) -> list[str]:
        """Execute one round. Returns list of discovery IDs posted."""

    def _post(self, family: str, category: str, conjecture: Conjecture,
              confidence: float, **extra) -> str:
        d = Discovery(
            id=conjecture.id,
            agent_id=self.config.agent_id,
            family=family,
            category=category,
            expression=conjecture.expression,
            value=conjecture.value,
            target=conjecture.target,
            error=conjecture.error if conjecture.error != float('inf') else None,
            confidence=confidence,
            params=conjecture.params,
            metadata={**conjecture.metadata, **extra},
            generation=conjecture.generation,
            provenance=getattr(conjecture, 'provenance', {}),
        )
        self.bb.post(d)
        self.stats["discoveries_posted"] += 1
        return d.id


# ===================================================================
#  Explorer Agent
# ===================================================================

class ExplorerAgent(BaseAgent):
    """Generates new conjectures via all formula strategies."""

    def __init__(self, config: AgentConfig, blackboard: Blackboard,
                 seed: int | None = None):
        super().__init__(config, blackboard)
        self.generator = ConjectureGenerator(prec=60, seed=seed)

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        self.generator.set_generation(round_num)
        ids = []

        # Feed back good parameters from previous rounds
        top = self.bb.query(min_confidence=0.5, limit=20)
        good_params = []
        for d in top:
            p = dict(d.params)
            p["_family"] = d.family
            good_params.append(p)

        relay_params = self.generator.load_relay_seed_pool(
            limit=max(6, self.config.budget)
        )
        if relay_params:
            good_params.extend(relay_params)

        self.generator.feedback(good_params)

        # Generate
        conjectures = self.generator.generate_all(
            budget_per_strategy=self.config.budget
        )

        for cj in conjectures:
            if cj.error == float('inf') or cj.quality <= 0:
                continue
            confidence = min(1.0, cj.quality / 50.0)
            cat = "conjecture"
            if cj.family == "partition" and cj.error == 0:
                cat = "congruence"
            elif cj.family == "integer_relation":
                cat = "integer_relation"
            did = self._post(cj.family, cat, cj, confidence,
                             source=cj.source)
            ids.append(did)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids


# ===================================================================
#  Validator Agent
# ===================================================================

class ValidatorAgent(BaseAgent):
    """Validates conjectures with high-precision numerics + symbolic."""

    def __init__(self, config: AgentConfig, blackboard: Blackboard):
        super().__init__(config, blackboard)
        self.validator = Validator(max_precision=500)

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []

        # v2: query candidates that haven't been through v2 validation yet
        candidates = self.bb.query(status="candidate", limit=self.config.budget)
        candidates = [d for d in candidates if d.category != "proof_sketch"
                      and d.status not in ("verified_known", "novel_proven",
                                           "novel_unproven", "falsified")]

        for disc in candidates:
            # Reconstruct a Conjecture object for the validator
            cj = Conjecture(
                id=disc.id,
                family=disc.family,
                expression=disc.expression,
                value=disc.value,
                target=disc.target,
                target_value=None,
                error=disc.error if disc.error is not None else float('inf'),
                params=disc.params,
                source="blackboard",
                generation=disc.generation,
                metadata=disc.metadata,
            )
            result = self.validator.validate(cj)

            # Post review
            self.bb.add_review(
                disc.id,
                self.config.agent_id,
                result.verdict,
                f"precision={result.precision_achieved}, "
                f"confidence={result.confidence:.3f}, "
                f"checks={len(result.checks)}"
            )

            # v2: Use honest taxonomy — never label known results as "proven"
            disc.confidence = max(disc.confidence, result.confidence)

            if result.verdict == "verified_known":
                disc.status = "verified_known"
                disc.category = "verified_known"
                disc.metadata["literature_match"] = result.literature_match
                disc.metadata["is_novel"] = False
            elif result.verdict == "novel_proven":
                disc.status = "novel_proven"
                disc.category = "novel_proven"
                disc.metadata["is_novel"] = True
            elif result.verdict == "novel_unproven":
                disc.status = "novel_unproven"
                disc.category = "novel_unproven"
                disc.metadata["is_novel"] = True
            elif result.verdict == "verified_numeric":
                disc.status = "validated"
                disc.category = "validated"
            elif result.verdict == "falsified":
                disc.status = "falsified"
                disc.category = "falsified"

            # v2: fix error:inf bug — give verified items their actual error
            if disc.error is None or disc.error == float('inf'):
                if result.precision_achieved > 0:
                    disc.error = 10 ** (-result.precision_achieved)

            # Post proof sketch if available (stable ID to avoid duplicates)
            if result.proof_sketch and result.verdict != "falsified":
                stable_seed = f"proof_{disc.family}_{disc.canonical_key}"
                proof_disc = Discovery(
                    id=hashlib.sha256(
                        stable_seed.encode()
                    ).hexdigest()[:12],
                    agent_id=self.config.agent_id,
                    family=disc.family,
                    category="proof_sketch",
                    expression=disc.expression,
                    value=disc.value,
                    target=disc.target,
                    confidence=result.confidence,
                    params=disc.params,
                    metadata={
                        "proof_sketch": result.proof_sketch,
                        "symbolic_form": result.symbolic_form,
                        "precision_achieved": result.precision_achieved,
                        "literature_match": result.literature_match,
                        "is_novel": result.is_novel,
                    },
                    parent_id=disc.id,
                    generation=round_num,
                )
                proof_disc.status = disc.status
                self.bb.post(proof_disc)
                ids.append(proof_disc.id)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids


# ===================================================================
#  Adversary Agent
# ===================================================================

class AdversaryAgent(BaseAgent):
    """Tests conjectures adversarially to catch false positives."""

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()

        candidates = self.bb.query(
            status="validated", limit=self.config.budget
        ) + self.bb.query(
            status="novel_unproven", limit=self.config.budget
        ) + self.bb.query(
            status="candidate", min_confidence=0.3, limit=self.config.budget
        )

        for disc in candidates:
            attacks = self._adversarial_suite(disc)
            n_passed = sum(1 for a in attacks if a["passed"])
            score = n_passed / max(len(attacks), 1)

            if score < 0.3:
                verdict = "falsified"
            elif score < 0.6:
                verdict = "weakened"
            else:
                verdict = "confirmed"

            self.bb.add_review(
                disc.id,
                self.config.agent_id,
                verdict,
                f"attacks={len(attacks)}, passed={n_passed}, score={score:.2f}"
            )

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return []  # Adversaries don't post discoveries

    def _adversarial_suite(self, disc: Discovery) -> list[dict]:
        attacks = []

        # Attack 1: Parameter sensitivity
        attacks.append(self._param_sensitivity(disc))

        # Attack 2: Numerical stability at extreme precision
        attacks.append(self._extreme_precision(disc))

        # Attack 3: Edge-case evaluation
        attacks.append(self._edge_cases(disc))

        # Attack 4: Triviality check
        attacks.append(self._triviality_check(disc))

        # v2 Attack 5: PSLQ stability (for integer_relation family)
        if disc.family == "integer_relation":
            attacks.append(self._pslq_stability_check(disc))

        return attacks

    def _param_sensitivity(self, disc: Discovery) -> dict:
        """Perturb parameters ±10% and check stability."""
        attack = {"test": "param_sensitivity", "passed": False}
        if not disc.params:
            attack["passed"] = True
            attack["note"] = "no params to perturb"
            return attack

        stable_count = 0
        total = 0
        for key, val in disc.params.items():
            if not isinstance(val, (int, float)):
                continue
            if val == 0:
                continue
            for delta in [-0.1, 0.1]:
                perturbed = {**disc.params, key: val * (1 + delta)}
                try:
                    if disc.family == "pi_series":
                        r = _generalised_pi_series(
                            int(perturbed.get("a", 1)),
                            int(perturbed.get("b", 1)),
                            int(perturbed.get("c", 64)),
                            int(perturbed.get("d", 1)),
                            num_terms=30, prec=50
                        )
                        if r.get("error", float('inf')) < 1.0:
                            stable_count += 1
                    elif disc.family == "continued_fraction":
                        r = _generalised_cf(
                            perturbed.get("an", [1, 0, 0]),
                            perturbed.get("bn", [1, 1]), prec=50
                        )
                        if r.get("best_error", float('inf')) < 1.0:
                            stable_count += 1
                    else:
                        stable_count += 1  # can't test
                except Exception:
                    pass
                total += 1

        attack["passed"] = total == 0 or stable_count / max(total, 1) < 0.8
        attack["note"] = f"{stable_count}/{total} perturbed variants also match"
        return attack

    def _extreme_precision(self, disc: Discovery) -> dict:
        """Check if result holds at 200-digit precision."""
        attack = {"test": "extreme_precision", "passed": False}
        try:
            if disc.family == "pi_series" and disc.params:
                r = _generalised_pi_series(
                    disc.params.get("a", 1), disc.params.get("b", 1),
                    disc.params.get("c", 64), disc.params.get("d", 1),
                    num_terms=200, prec=200
                )
                attack["passed"] = r.get("error", float('inf')) < 1e-50
                attack["error_at_200"] = r.get("error")
            elif disc.family == "continued_fraction" and disc.params.get("an"):
                # Polynomial CFs: re-evaluate at 200 dps
                r = _generalised_cf(
                    disc.params.get("an", [1, 0, 0]),
                    disc.params.get("bn", [1, 1]), prec=200
                )
                if r.get("is_potentially_novel"):
                    attack["passed"] = r.get("convergence_error", 1.0) < 1e-30
                    attack["convergence_at_200"] = r.get("convergence_error")
                else:
                    attack["passed"] = r.get("best_error", float('inf')) < 1e-50
            elif disc.family == "continued_fraction":
                # Nonpoly CFs: use stored convergence error
                conv = disc.metadata.get("convergence_error", disc.error)
                attack["passed"] = conv < 1e-8
                attack["note"] = f"convergence_error={conv:.2e}"
            elif disc.family == "partition":
                # Partition congruences: extend range
                attack["passed"] = disc.error == 0
            else:
                attack["passed"] = disc.error is not None and disc.error < 1e-10
        except Exception as exc:
            attack["note"] = str(exc)
        return attack

    def _edge_cases(self, disc: Discovery) -> dict:
        """Test at boundary parameter values."""
        attack = {"test": "edge_cases", "passed": True}
        # For partition congruences: test larger n
        if disc.family == "partition":
            params = disc.params
            a, b, m = params.get("a"), params.get("b"), params.get("m")
            if a and b is not None and m:
                max_n = 500
                p = [0] * (max_n + 1)
                p[0] = 1
                for k in range(1, max_n + 1):
                    for j in range(k, max_n + 1):
                        p[j] += p[j - k]
                vals = [p[a*n + b] for n in range(max_n // a) if a*n + b <= max_n]
                violations = sum(1 for v in vals if v % m != 0)
                attack["passed"] = violations == 0
                attack["violations"] = violations
                attack["tested_up_to"] = max_n
        return attack

    def _triviality_check(self, disc: Discovery) -> dict:
        """Check if the conjecture is trivially true or meaningless."""
        attack = {"test": "triviality", "passed": True}
        # Trivial if error is exactly 0 and expression is very simple
        if disc.error == 0 and len(disc.expression) < 20:
            attack["note"] = "very simple expression with zero error — likely known"
            attack["passed"] = True  # still passes, just flagged
        if disc.value == 0 and disc.family not in ("partition", "tau_function"):
            attack["passed"] = False
            attack["note"] = "zero value — likely degenerate"
        # Flag density-based tau patterns as statistical, not congruences
        if disc.family == "tau_function" and disc.params.get("density") is not None:
            density = disc.params["density"]
            if density < 1.0:
                attack["note"] = f"density {density:.1%} — statistical pattern, not exact congruence"
                attack["passed"] = True  # passes, but downgraded
                disc.category = "statistical_pattern"
                disc.confidence = min(disc.confidence, density * 0.5)
        return attack

    def _pslq_stability_check(self, disc: Discovery) -> dict:
        """v3: Check PSLQ relation stability at multiple precisions.
        
        Records a full stability table: coefficients at each tier.
        """
        attack = {"test": "pslq_stability", "passed": False}
        # If generator already has a stability table, use it
        gen_table = disc.metadata.get("stability_table")
        if gen_table and disc.metadata.get("pslq_stable") is True:
            attack["passed"] = True
            attack["stability_table"] = gen_table
            attack["note"] = (
                f"generator confirmed stability across "
                f"{len(gen_table)} precision tiers"
            )
            return attack
        if disc.metadata.get("pslq_stable") is False:
            attack["passed"] = False
            attack["stability_table"] = gen_table or []
            attack["note"] = "generator flagged as UNSTABLE at double precision"
            return attack
        # Otherwise run our own check at ascending precisions
        relation = disc.params.get("relation")
        basis = disc.params.get("basis", [])
        if not relation or not basis:
            attack["passed"] = True
            attack["note"] = "no relation to check"
            return attack
        try:
            stability_table = []
            all_match = True
            for prec in [60, 120, 240]:
                mp = _mp(prec)
                basis_vals = _compute_basis_mpf(basis, prec)
                target_mpf = mp.mpf(disc.value)
                r = _pslq_search(target_mpf, basis, basis_vals, prec=prec)
                row = {
                    "precision": prec,
                    "relation": r.get("relation"),
                    "residual": r.get("residual"),
                    "max_coeff": r.get("max_coeff"),
                    "found": r.get("found", False),
                    "matches_original": (
                        r.get("found") and r["relation"] == relation
                    ),
                }
                stability_table.append(row)
                if not row["matches_original"]:
                    all_match = False
            attack["stability_table"] = stability_table
            attack["passed"] = all_match
            if all_match:
                attack["note"] = (
                    f"confirmed at {len(stability_table)} precision tiers "
                    f"({', '.join(str(t['precision']) for t in stability_table)} dps)"
                )
            else:
                attack["note"] = "relation NOT stable across precision tiers"
        except Exception as exc:
            attack["note"] = f"stability check error: {exc}"
        return attack


# ===================================================================
#  Refiner Agent
# ===================================================================
#  Pattern Matcher Agent (v4 — Reviewer role: "Structure Finder")
# ===================================================================

class PatternMatcherAgent(BaseAgent):
    """Structural identification: tries Bessel/HG/algebraic/PSLQ matching.

    For each candidate, outputs a 'best structural guess' — the most
    specific identification possible. This feeds the ProofPlanner.
    """

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []

        # Target: validated + novel_unproven CFs without structural ID
        candidates = self.bb.query(status="novel_unproven", limit=self.config.budget)
        candidates += self.bb.query(status="validated", limit=self.config.budget // 2)

        for disc in candidates:
            if disc.family != "continued_fraction":
                continue
            # Skip if already structurally identified
            if disc.metadata.get("structural_match"):
                continue

            match = self._identify_structure(disc)
            if match:
                disc.metadata["structural_match"] = match
                disc.metadata["pattern_agent_round"] = round_num
                self.bb.add_review(
                    disc.id, self.config.agent_id,
                    "structural_match",
                    f"type={match.get('type', '?')}, match_error={match.get('match_error', '?')}"
                )
                ids.append(disc.id)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids

    def _identify_structure(self, disc: Discovery) -> dict | None:
        """Try to identify structural form of a CF value."""
        from .proof_engine import identify_special_function
        params = disc.params
        an = params.get("an", [])
        bn = params.get("bn", [])
        if not an or not bn:
            return None

        # Get high-precision value
        val_str = disc.metadata.get("value_hi_prec") or str(disc.value)
        try:
            import mpmath
            mp = mpmath.mp.clone()
            mp.dps = 100
            val = mp.mpf(val_str)
        except Exception:
            return None

        result = identify_special_function(an, bn, val, prec=100)
        if result.get("identified") and result.get("best"):
            best = result["best"]
            return {
                "type": best.get("type", "unknown"),
                "expression": best.get("expression", ""),
                "formula": best.get("formula", best.get("expression", "")),
                "match_error": best.get("match_error", float("inf")),
                "candidates": result.get("candidates", []),
            }
        return None


# ===================================================================
#  Proof Planner Agent (v4 — Reviewer role: "Theorem Architect")
# ===================================================================

class ProofPlannerAgent(BaseAgent):
    """Creates proof plans: theorem template + lemma list + strategy.

    Takes a candidate with structural match and produces a detailed
    proof plan that the ProofExecutor can follow.
    """

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []

        # Target: candidates with structural matches but no proof yet
        candidates = self.bb.query(status="novel_unproven", limit=self.config.budget)

        for disc in candidates:
            if disc.family != "continued_fraction":
                continue
            # Need structural match to plan proof
            match = disc.metadata.get("structural_match")
            if not match and not disc.metadata.get("bessel_identification", {}).get("identified"):
                continue
            # Skip if already has proof plan
            if disc.metadata.get("proof_plan"):
                continue

            plan = self._create_proof_plan(disc, match)
            if plan:
                disc.metadata["proof_plan"] = plan
                # Post proof plan as a discovery for tracking
                plan_disc = Discovery(
                    id=hashlib.sha256(
                        f"plan_{disc.id}_{round_num}".encode()
                    ).hexdigest()[:12],
                    agent_id=self.config.agent_id,
                    family=disc.family,
                    category="proof_sketch",
                    expression=f"Proof plan for {disc.expression[:60]}",
                    value=disc.value,
                    confidence=plan.get("confidence", 0.3),
                    params=disc.params,
                    metadata={"proof_plan": plan, "target_id": disc.id},
                    parent_id=disc.id,
                    generation=round_num,
                )
                self.bb.post(plan_disc)
                ids.append(plan_disc.id)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids

    def _create_proof_plan(self, disc: Discovery, match: dict | None) -> dict | None:
        """Create a structured proof plan with lemma list."""
        params = disc.params
        an = params.get("an", [])
        bn = params.get("bn", [])

        # Determine proof strategy based on structure
        match_type = (match or {}).get("type", "")
        if not match_type:
            bessel = disc.metadata.get("bessel_identification", {})
            if bessel.get("identified"):
                match_type = "bessel_ratio"

        if match_type in ("bessel_ratio", "bessel_j_ratio"):
            return self._bessel_proof_plan(disc, an, bn, match)
        elif match_type in ("confluent_1F1", "sympy_nsimplify"):
            return self._hypergeometric_proof_plan(disc, an, bn, match)
        elif len(an) == 1 and len(bn) == 1:
            return self._algebraic_proof_plan(disc, an, bn)
        elif len(bn) >= 2 and bn[0] != 0:
            return self._linear_b_proof_plan(disc, an, bn, match)

        return None

    def _bessel_proof_plan(self, disc, an, bn, match) -> dict:
        A = an[0] if an else 0
        alpha = bn[0] if len(bn) >= 2 else 0
        beta = bn[1] if len(bn) >= 2 else 0
        return {
            "strategy": "bessel_ratio",
            "theorem_statement": (
                f"The CF K({{n≥1}} {A}/({alpha}n+{beta})) converges to "
                f"β + α·√(A/α²)·I_{{1+β/α}}(2√(A/α²))/I_{{β/α}}(2√(A/α²))"
            ),
            "lemmas": [
                {"id": "L1", "statement": f"Show a(n)={A}, b(n)={alpha}n+{beta} satisfies Śleszyński-Pringsheim or Van Vleck",
                 "status": "unproven", "method": "convergence_theorem"},
                {"id": "L2", "statement": "Rewrite CF as ratio of contiguous ₁F₁ via Euler's equivalence",
                 "status": "unproven", "method": "euler_equivalence"},
                {"id": "L3", "statement": "Apply ₁F₁ → Bessel connection (DLMF 10.25.2)",
                 "status": "unproven", "method": "special_function_identity"},
                {"id": "L4", "statement": "CAS-verify closed form matches numeric value to 50+ digits",
                 "status": "unproven", "method": "cas_verification"},
            ],
            "literature": ["Wall (1948) Thm 92.1", "Perron (1954) Ch. 8", "DLMF §10.25"],
            "confidence": 0.7,
            "match_info": match,
        }

    def _hypergeometric_proof_plan(self, disc, an, bn, match) -> dict:
        return {
            "strategy": "hypergeometric",
            "theorem_statement": f"The CF converges to a ratio of hypergeometric functions",
            "lemmas": [
                {"id": "L1", "statement": "Prove convergence via named theorem",
                 "status": "unproven", "method": "convergence_theorem"},
                {"id": "L2", "statement": "Express as ₂F₁ or ₁F₁ ratio using Gauss CF formula",
                 "status": "unproven", "method": "gauss_cf"},
                {"id": "L3", "statement": "Simplify hypergeometric ratio to closed form",
                 "status": "unproven", "method": "hg_simplification"},
                {"id": "L4", "statement": "CAS-verify against numeric value",
                 "status": "unproven", "method": "cas_verification"},
            ],
            "literature": ["Gauss CF theorem; Wall (1948) §89"],
            "confidence": 0.5,
            "match_info": match,
        }

    def _algebraic_proof_plan(self, disc, an, bn) -> dict:
        A, B = an[0], bn[0]
        return {
            "strategy": "algebraic_fixed_point",
            "theorem_statement": f"The CF B + K(A/B) = (B + √(B²+4A))/2",
            "lemmas": [
                {"id": "L1", "statement": f"The CF satisfies y = {B} + {A}/y, giving y² - {B}y - {A} = 0",
                 "status": "unproven", "method": "fixed_point_equation"},
                {"id": "L2", "statement": f"Discriminant = {B}² + 4·{A} = {B*B + 4*A}",
                 "status": "unproven", "method": "quadratic_formula"},
                {"id": "L3", "statement": "Select positive root; verify convergence",
                 "status": "unproven", "method": "root_selection"},
            ],
            "literature": ["Elementary; Wall (1948) §1"],
            "confidence": 0.95,
        }

    def _linear_b_proof_plan(self, disc, an, bn, match) -> dict:
        return {
            "strategy": "linear_b_general",
            "theorem_statement": "Linear-b CF converges by ratio test; value identified via special functions",
            "lemmas": [
                {"id": "L1", "statement": "|a(n)/b(n)| → 0 as n → ∞; ratio test guarantees convergence",
                 "status": "unproven", "method": "ratio_test"},
                {"id": "L2", "statement": "Apply Euler equivalence transform to standard form",
                 "status": "unproven", "method": "euler_equivalence"},
                {"id": "L3", "statement": "Identify value via special function or nsimplify",
                 "status": "unproven", "method": "identification"},
                {"id": "L4", "statement": "CAS-verify identified form",
                 "status": "unproven", "method": "cas_verification"},
            ],
            "literature": ["Lorentzen & Waadeland (2008) Ch. 3"],
            "confidence": 0.4,
            "match_info": match,
        }


# ===================================================================
#  Proof Executor Agent (v4 — wraps proof_engine.py)
# ===================================================================

class ProofExecutorAgent(BaseAgent):
    """Executes proof plans via CAS, records every step.

    Takes candidates with proof_plans and runs proof_engine.attempt_proof().
    Records results back into the discovery metadata.
    """

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []
        from .proof_engine import attempt_proof

        # Target: discoveries with proof plans
        candidates = self.bb.query(status="novel_unproven", limit=self.config.budget)

        for disc in candidates:
            if disc.family != "continued_fraction":
                continue
            # Run proof engine
            d_dict = disc.to_dict()
            try:
                pr = attempt_proof(d_dict, prec=100)
                disc.metadata["proof_result"] = pr.to_dict()

                if pr.status == "formal_proof":
                    disc.status = "novel_proven"
                    disc.category = "novel_proven"
                    disc.confidence = max(disc.confidence, pr.confidence)
                elif pr.status == "partial_proof":
                    # Update proof plan lemma statuses
                    plan = disc.metadata.get("proof_plan", {})
                    if plan:
                        for lemma in plan.get("lemmas", []):
                            if lemma["method"] == "convergence_theorem" and pr.convergence.get("proven"):
                                lemma["status"] = "proven"
                            if lemma["method"] == "cas_verification" and pr.verification.get("verified"):
                                lemma["status"] = "proven"
                            if lemma["method"] in ("special_function_identity", "identification"):
                                if pr.closed_form.get("type"):
                                    lemma["status"] = "proven"

                self.bb.add_review(
                    disc.id, self.config.agent_id,
                    pr.status,
                    f"confidence={pr.confidence:.2f}, gaps={len(pr.gaps)}"
                )
                ids.append(disc.id)
            except Exception as exc:
                disc.metadata["proof_error"] = str(exc)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids


# ===================================================================
#  Referee Agent (v4 — Reviewer role: "Falsifier/Formalist")
# ===================================================================

class RefereeAgent(BaseAgent):
    """Final review: checks each lemma, re-runs numerics, outputs verdict.

    Strict tagging:
      - "accepted"  → all lemmas proven, CAS verified
      - "gap_in_lemma_X" → specific gap identified
      - "refuted" → counterexample or inconsistency found
    """

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []

        # Review candidates that have been through the proof pipeline
        candidates = self.bb.query(status="novel_proven", limit=self.config.budget)
        candidates += self.bb.query(status="novel_unproven", limit=self.config.budget)

        for disc in candidates:
            verdict, notes = self._review(disc)
            self.bb.add_review(disc.id, self.config.agent_id, verdict, notes)

            # Update epistemic tag
            if verdict == "accepted":
                disc.metadata["epistemic_tag"] = "theorem"
                disc.metadata["referee_verdict"] = "accepted"
            elif verdict.startswith("gap_in"):
                disc.metadata["epistemic_tag"] = "theorem_conditional"
                disc.metadata["referee_verdict"] = verdict
            elif verdict == "refuted":
                disc.status = "falsified"
                disc.metadata["epistemic_tag"] = "refuted"
                disc.metadata["referee_verdict"] = "refuted"
            else:
                disc.metadata["epistemic_tag"] = "conjecture"
                disc.metadata["referee_verdict"] = verdict
            ids.append(disc.id)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids

    def _review(self, disc: Discovery) -> tuple[str, str]:
        """Full review of a discovery's proof chain."""
        proof_result = disc.metadata.get("proof_result", {})
        proof_plan = disc.metadata.get("proof_plan", {})

        # No proof attempted → just re-run adversarial checks
        if not proof_result:
            attacks = self._basic_checks(disc)
            n_passed = sum(1 for a in attacks if a.get("passed"))
            if n_passed == len(attacks):
                return "confirmed", f"passes {n_passed}/{len(attacks)} checks (no proof attempted)"
            else:
                failed = [a["test"] for a in attacks if not a.get("passed")]
                return "weakened", f"fails: {', '.join(failed)}"

        # Check proof completeness
        status = proof_result.get("status", "")
        gaps = proof_result.get("gaps", [])
        convergence = proof_result.get("convergence", {})
        closed_form = proof_result.get("closed_form", {})
        verification = proof_result.get("verification", {})

        if status == "formal_proof" and not gaps:
            # Verify the formal proof claim
            if verification.get("verified") and convergence.get("proven"):
                return "accepted", (
                    f"Convergence: {convergence.get('theorem_used', '?')}; "
                    f"Closed form: {closed_form.get('type', '?')}; "
                    f"CAS match: {verification.get('match_digits', 0)} digits"
                )
            # Claimed formal but verification incomplete
            return "gap_in_verification", "Formal proof claimed but CAS verification incomplete"

        # Partial proof — identify specific gaps
        if gaps:
            first_gap = gaps[0]
            return f"gap_in_{first_gap[:20].replace(' ', '_')}", f"Gaps: {'; '.join(gaps[:3])}"

        # Check individual lemmas if proof plan exists
        if proof_plan:
            lemmas = proof_plan.get("lemmas", [])
            unproven = [l for l in lemmas if l.get("status") != "proven"]
            if not unproven:
                return "accepted", "All lemmas proven"
            first_unproven = unproven[0]
            return (f"gap_in_lemma_{first_unproven['id']}",
                    f"Unproven: {first_unproven['statement'][:60]}")

        return "unreviewed", "Insufficient proof data for review"

    def _basic_checks(self, disc: Discovery) -> list[dict]:
        """Quick numeric checks without full adversarial suite."""
        checks = []

        # Precision check
        prec = disc.metadata.get("precision_achieved", 0) or disc.precision_digits
        checks.append({
            "test": "precision",
            "passed": prec >= 20,
            "note": f"{prec} digits verified",
        })

        # Convergence check for CFs
        if disc.family == "continued_fraction":
            conv_err = disc.metadata.get("convergence_error_500_300", 1)
            checks.append({
                "test": "convergence",
                "passed": conv_err < 1e-10,
                "note": f"depth error = {conv_err:.2e}",
            })

        # Non-trivial check
        checks.append({
            "test": "nontrivial",
            "passed": disc.value != 0 and abs(disc.value) > 1e-10,
            "note": f"value = {disc.value}",
        })

        return checks


# ===================================================================
#  Refiner Agent
# ===================================================================

class RefinerAgent(BaseAgent):
    """Improves promising conjectures by tuning parameters."""

    def __init__(self, config: AgentConfig, blackboard: Blackboard):
        super().__init__(config, blackboard)
        self.generator = ConjectureGenerator(prec=80)

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []

        # Get not-yet-proven discoveries for refinement
        candidates = self.bb.query(status="validated", limit=self.config.budget)
        candidates += self.bb.query(status="novel_unproven", limit=self.config.budget)

        for disc in candidates:
            refined = self._refine(disc, round_num)
            for cj in refined:
                if cj.quality > disc.confidence * 40:
                    did = self._post(
                        cj.family, "conjecture", cj,
                        min(1.0, cj.quality / 50.0),
                        parent_id=disc.id, source="refinement"
                    )
                    ids.append(did)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids

    def _refine(self, disc: Discovery, round_num: int) -> list[Conjecture]:
        """Try nearby parameter variations."""
        results = []
        params = disc.params
        if not params:
            return results

        if disc.family == "pi_series":
            a, b, c, d = (params.get("a", 1), params.get("b", 1),
                          params.get("c", 64), params.get("d", 1))
            # Fine grid search around known good params
            for da in range(-3, 4):
                for db in range(-10, 11, 5):
                    na, nb = a + da, b + db
                    if na <= 0 or nb <= 0 or c <= 0:
                        continue
                    try:
                        r = _generalised_pi_series(na, nb, c, d,
                                                    num_terms=80, prec=80)
                    except Exception:
                        continue
                    if not r.get("converges"):
                        continue
                    if r["error"] < disc.error:
                        cj = Conjecture(
                            id=hashlib.sha256(
                                f"refine_pi_{na}_{nb}_{c}_{d}_{round_num}".encode()
                            ).hexdigest()[:12],
                            family="pi_series",
                            expression=r["expression"],
                            value=r["value"],
                            target="pi",
                            target_value=r["target"],
                            error=r["error"],
                            params={"a": na, "b": nb, "c": c, "d": d},
                            source="refinement",
                            generation=round_num,
                        )
                        results.append(cj)

        elif disc.family == "continued_fraction":
            an = params.get("an", [1, 0, 0])
            bn = params.get("bn", [1, 1])
            for i in range(len(an)):
                for delta in [-1, 1]:
                    new_an = list(an)
                    new_an[i] += delta
                    try:
                        r = _generalised_cf(new_an, bn, prec=80)
                    except Exception:
                        continue
                    if r.get("is_interesting") and r["best_error"] < disc.error:
                        cj = Conjecture(
                            id=hashlib.sha256(
                                f"refine_cf_{new_an}_{bn}_{round_num}".encode()
                            ).hexdigest()[:12],
                            family="continued_fraction",
                            expression=r["expression"],
                            value=r["value"],
                            target=r.get("best_match"),
                            error=r["best_error"],
                            params={"an": new_an, "bn": bn},
                            source="refinement",
                            generation=round_num,
                        )
                        results.append(cj)

        return results


# ===================================================================
#  Cross-Pollinator Agent
# ===================================================================

class CrossPollinatorAgent(BaseAgent):
    """Finds structural analogies across formula families."""

    # Mapping: what patterns transfer between families
    FAMILY_BRIDGES = {
        ("pi_series", "continued_fraction"): "Euler-type transform",
        ("q_series", "partition"): "generating function duality",
        ("mock_theta", "q_series"): "modular completion",
        ("tau_function", "partition"): "modular form connection",
    }

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []

        top = self.bb.get_top(30)
        families_seen = {d.family for d in top}

        for (src_fam, tgt_fam), bridge_type in self.FAMILY_BRIDGES.items():
            if src_fam not in families_seen:
                continue
            src_discs = [d for d in top if d.family == src_fam]
            tgt_discs = [d for d in top if d.family == tgt_fam]

            for sd in src_discs[:3]:
                # Check if same structural pattern appears
                for td in tgt_discs[:3]:
                    sim = self._structural_similarity(sd, td)
                    if sim > 0.3:
                        transfer = Discovery(
                            id=hashlib.sha256(
                                f"xpoll_{sd.id}_{td.id}_{round_num}".encode()
                            ).hexdigest()[:12],
                            agent_id=self.config.agent_id,
                            family="cross_pollination",
                            category="transfer",
                            expression=f"Bridge({sd.family}→{td.family}): {bridge_type}",
                            value=sim,
                            confidence=sim * 0.8,
                            params={
                                "source_id": sd.id, "target_id": td.id,
                                "source_family": sd.family,
                                "target_family": td.family,
                                "bridge": bridge_type,
                            },
                            metadata={
                                "source_expr": sd.expression[:100],
                                "target_expr": td.expression[:100],
                            },
                            generation=round_num,
                        )
                        self.bb.post(transfer)
                        ids.append(transfer.id)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids

    def _structural_similarity(self, d1: Discovery, d2: Discovery) -> float:
        """Compute structural similarity between two discoveries."""
        score = 0.0
        # Same target constant?
        if d1.target and d2.target and d1.target == d2.target:
            score += 0.3
        # Similar error magnitude?
        if d1.error > 0 and d2.error > 0:
            ratio = max(d1.error, d2.error) / min(d1.error, d2.error)
            if ratio < 10:
                score += 0.2
        # Both high confidence?
        if d1.confidence > 0.5 and d2.confidence > 0.5:
            score += 0.2
        # Expression length similarity
        len1, len2 = len(d1.expression), len(d2.expression)
        if max(len1, len2) > 0:
            score += 0.1 * min(len1, len2) / max(len1, len2)
        # Common keywords in expression
        words1 = set(d1.expression.lower().split())
        words2 = set(d2.expression.lower().split())
        if words1 & words2:
            score += 0.1 * len(words1 & words2) / max(len(words1 | words2), 1)
        return min(score, 1.0)


# ===================================================================
#  Meta-Learner Agent
# ===================================================================

class MetaLearnerAgent(BaseAgent):
    """Analyses discovery history to improve strategy."""

    def run(self, round_num: int) -> list[str]:
        t0 = time.time()
        ids = []

        stats = self.bb.get_stats()
        round_log = self.bb.get_round_log()
        top = self.bb.get_top(50)

        insights = []

        # Insight 1: Which families are producing the most discoveries?
        by_family = stats.get("by_family", {})
        best_family = max(by_family, key=by_family.get) if by_family else None
        if best_family:
            insights.append(f"Most productive family: {best_family} ({by_family[best_family]} discoveries)")

        # Insight 2: What parameter regions are most successful?
        successful = [d for d in top if d.confidence > 0.6]
        if successful:
            families = {}
            for d in successful:
                families.setdefault(d.family, []).append(d.params)
            for fam, param_list in families.items():
                insights.append(f"Successful {fam} params: {len(param_list)} examples")

        # Insight 3: Discovery rate trend
        if len(round_log) >= 3:
            recent = round_log[-3:]
            counts = [r.get("new_discoveries", 0) for r in recent]
            trend = "increasing" if counts[-1] > counts[0] else "decreasing"
            insights.append(f"Discovery trend: {trend} (recent: {counts})")

        # Insight 4: Validation rate (v2 taxonomy)
        total = stats.get("total", 1)
        verified_known = stats.get("by_novelty", {}).get("verified_known", 0)
        novel_count = stats.get("by_novelty", {}).get("novel_unproven", 0) + stats.get("by_novelty", {}).get("novel_proven", 0)
        validated = stats.get("validated_count", 0)
        val_rate = (validated + verified_known + novel_count) / max(total, 1)
        insights.append(f"Validation rate: {val_rate:.1%} ({verified_known} known, {novel_count} novel, {validated} numeric)")

        # Post meta-insight
        if insights:
            meta_disc = Discovery(
                id=hashlib.sha256(
                    f"meta_{round_num}_{time.time()}".encode()
                ).hexdigest()[:12],
                agent_id=self.config.agent_id,
                family="meta",
                category="pattern",
                expression="; ".join(insights),
                value=val_rate,
                confidence=0.5,
                metadata={"insights": insights, "stats": stats},
                generation=round_num,
            )
            self.bb.post(meta_disc)
            ids.append(meta_disc.id)

        self.stats["time_spent"] += time.time() - t0
        self.stats["rounds"] += 1
        return ids


# ===================================================================
#  Agent factory
# ===================================================================

def create_agents(blackboard: Blackboard, config: dict | None = None
                  ) -> list[BaseAgent]:
    """Create the v4 agent ensemble with theorem-proving pipeline."""
    config = config or {}
    budget = config.get("budget_per_agent", 15)

    agents = [
        # Phase 1: Exploration (2 explorers with different seeds)
        ExplorerAgent(
            AgentConfig("explorer_0", "explorer", budget=budget),
            blackboard, seed=42
        ),
        ExplorerAgent(
            AgentConfig("explorer_1", "explorer",
                        exploration_rate=0.9, budget=budget),
            blackboard, seed=137
        ),
        # Phase 2: Numeric verification
        ValidatorAgent(
            AgentConfig("validator_0", "validator", budget=budget * 2),
            blackboard,
        ),
        # Phase 3: Adversarial testing
        AdversaryAgent(
            AgentConfig("adversary_0", "adversary", budget=budget),
            blackboard,
        ),
        # Phase 4: Pattern matching (v4 new)
        PatternMatcherAgent(
            AgentConfig("matcher_0", "pattern_matcher", budget=budget),
            blackboard,
        ),
        # Phase 5: Proof planning (v4 new)
        ProofPlannerAgent(
            AgentConfig("planner_0", "proof_planner", budget=budget),
            blackboard,
        ),
        # Phase 6: Proof execution (v4 new)
        ProofExecutorAgent(
            AgentConfig("executor_0", "proof_executor", budget=budget),
            blackboard,
        ),
        # Phase 7: Referee (v4 new)
        RefereeAgent(
            AgentConfig("referee_0", "referee", budget=budget),
            blackboard,
        ),
        # Supporting agents (periodic)
        RefinerAgent(
            AgentConfig("refiner_0", "refiner", budget=budget),
            blackboard,
        ),
        CrossPollinatorAgent(
            AgentConfig("pollinator_0", "pollinator", budget=budget),
            blackboard,
        ),
        MetaLearnerAgent(
            AgentConfig("meta_0", "meta_learner", budget=budget),
            blackboard,
        ),
    ]
    return agents
