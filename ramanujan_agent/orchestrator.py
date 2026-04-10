"""
orchestrator.py — Self-iterating discovery controller (v4 — theorem machine).

v4 pipeline (depth-over-breadth, theorem-first):
  Round structure:
    Phase 1: Exploration    (ExplorerAgents generate conjectures)
    Phase 2: Validation     (ValidatorAgent numeric verification + stability labels)
    Phase 3: Adversarial    (AdversaryAgent stress-tests)
    Phase 4: Pattern Match  (PatternMatcherAgent: Bessel/HG/algebraic ID)
    Phase 5: Proof Planning (ProofPlannerAgent: theorem templates + lemma lists)
    Phase 6: Proof Execution (ProofExecutorAgent: CAS-based proof attempts)
    Phase 7: Referee        (RefereeAgent: accept/reject/gap analysis)
    Phase 8: Refinement     (RefinerAgent tunes promising results)     [periodic]
    Phase 9: Pollination    (CrossPollinatorAgent finds analogies)     [periodic]
    Phase 10: Meta-learning (MetaLearnerAgent adjusts strategy)        [periodic]

  Post-round: Rigor ladder assessment, meta-critic scoring, template induction

Self-iteration: each round feeds discoveries back as seeds for the next.
Scoring: proven theorems >> conditional theorems >> structural matches >> raw conjectures.
"""

from __future__ import annotations
import time
import json
from pathlib import Path

from .analysis import analyze_novel_cf, cluster_by_value, build_candidate_table
from .proof_engine import attempt_proof
from .proof_funnel import build_proof_queue, format_proof_scaffold, save_bootstrap_case
from .theorem_templates import induce_templates, format_template_card
from .rigor_ladder import assess_all, format_rigor_summary
from .meta_critic import score_batch, format_critic_summary
from .relay_chain import execute_relay_chain

from .blackboard import Blackboard
from .agents import (
    BaseAgent, ExplorerAgent, ValidatorAgent, AdversaryAgent,
    PatternMatcherAgent, ProofPlannerAgent, ProofExecutorAgent, RefereeAgent,
    RefinerAgent, CrossPollinatorAgent, MetaLearnerAgent,
    create_agents,
)


class Orchestrator:
    """Self-iterating multi-agent Ramanujan discovery system (v4)."""

    DEFAULT_CONFIG = {
        "max_rounds": 5,
        "budget_per_agent": 15,
        "pollinate_every": 2,
        "meta_learn_every": 2,
        "persist_path": "results/ramanujan_state.json",
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.bb = Blackboard(persist_path=self.config["persist_path"])
        self.agents = create_agents(self.bb, self.config)
        self.results_log: list[dict] = []
        self.relay_snapshots: list[dict] = []

    def run(self) -> dict:
        """Execute the v4 theorem-proving discovery loop."""
        t_start = time.time()
        max_rounds = self.config["max_rounds"]

        print("=" * 70)
        print("  RAMANUJAN AGENT v4 — Theorem Machine")
        print("  (depth-over-breadth · proof pipeline · rigor ladder)")
        print("=" * 70)
        print(f"  Configuration: {max_rounds} rounds, "
              f"{len(self.agents)} agents")
        print(f"  Pipeline: Explore → Validate → Adversarial → "
              f"Pattern Match → Proof Plan → Proof Execute → Referee")
        print("=" * 70)
        print()

        for rnd in range(1, max_rounds + 1):
            round_start = time.time()
            round_ids = []

            print(f"╔══ Round {rnd}/{max_rounds} {'═' * 50}")

            # Phase 1: Exploration
            print(f"║  Phase 1: Exploration...")
            explorers = [a for a in self.agents if isinstance(a, ExplorerAgent)]
            for agent in explorers:
                ids = agent.run(rnd)
                round_ids.extend(ids)
            print(f"║    → {len(round_ids)} conjectures generated")

            # Phase 2: Numeric Verification
            print(f"║  Phase 2: Numeric Verification...")
            validators = [a for a in self.agents if isinstance(a, ValidatorAgent)]
            val_ids = []
            for agent in validators:
                ids = agent.run(rnd)
                val_ids.extend(ids)
            print(f"║    → {len(val_ids)} validation results")

            # Phase 3: Adversarial Testing
            print(f"║  Phase 3: Adversarial Testing...")
            adversaries = [a for a in self.agents if isinstance(a, AdversaryAgent)]
            for agent in adversaries:
                agent.run(rnd)
            stats = self.bb.get_stats()
            print(f"║    → {stats.get('by_status', {}).get('falsified', 0)} falsified")

            # Phase 4: Pattern Matching (v4 new)
            print(f"║  Phase 4: Pattern Matching...")
            matchers = [a for a in self.agents if isinstance(a, PatternMatcherAgent)]
            match_ids = []
            for agent in matchers:
                ids = agent.run(rnd)
                match_ids.extend(ids)
            print(f"║    → {len(match_ids)} structural matches found")

            # Phase 4b: Generative relay chain (new)
            print(f"║  Phase 4b: Relay Chain...")
            try:
                relay_input = [
                    d.to_dict()
                    for d in self.bb.query(family="continued_fraction", limit=250)
                ]
                relay_summary = execute_relay_chain(
                    relay_input,
                    output_dir="results",
                    max_seeds=max(8, self.config["budget_per_agent"]),
                )
            except Exception as exc:
                relay_summary = {
                    "recognized_count": 0,
                    "template_count": 0,
                    "seed_count": 0,
                    "error": str(exc),
                }
            self.relay_snapshots.append({"round": rnd, **relay_summary})
            print(f"║    → {relay_summary.get('recognized_count', 0)} CF patterns | "
                  f"{relay_summary.get('template_count', 0)} templates | "
                  f"{relay_summary.get('seed_count', 0)} seeds")

            # Phase 5: Proof Planning (v4 new)
            print(f"║  Phase 5: Proof Planning...")
            planners = [a for a in self.agents if isinstance(a, ProofPlannerAgent)]
            plan_ids = []
            for agent in planners:
                ids = agent.run(rnd)
                plan_ids.extend(ids)
            print(f"║    → {len(plan_ids)} proof plans created")

            # Phase 6: Proof Execution (v4 new)
            print(f"║  Phase 6: Proof Execution...")
            executors = [a for a in self.agents if isinstance(a, ProofExecutorAgent)]
            exec_ids = []
            for agent in executors:
                ids = agent.run(rnd)
                exec_ids.extend(ids)
            n_proven = len(self.bb.query(status="novel_proven", limit=200))
            print(f"║    → {len(exec_ids)} proof attempts, {n_proven} proven total")

            # Phase 7: Referee (v4 new)
            print(f"║  Phase 7: Referee Review...")
            referees = [a for a in self.agents if isinstance(a, RefereeAgent)]
            ref_ids = []
            for agent in referees:
                ids = agent.run(rnd)
                ref_ids.extend(ids)
            print(f"║    → {len(ref_ids)} candidates reviewed")

            # Phase 8: Refinement
            print(f"║  Phase 8: Refinement...")
            refiners = [a for a in self.agents if isinstance(a, RefinerAgent)]
            ref_ids2 = []
            for agent in refiners:
                ids = agent.run(rnd)
                ref_ids2.extend(ids)
            round_ids.extend(ref_ids2)
            print(f"║    → {len(ref_ids2)} refined conjectures")

            # Phase 9: Cross-pollination (periodic)
            if rnd % self.config["pollinate_every"] == 0:
                print(f"║  Phase 9: Cross-pollination...")
                pollinators = [a for a in self.agents
                               if isinstance(a, CrossPollinatorAgent)]
                poll_ids = []
                for agent in pollinators:
                    ids = agent.run(rnd)
                    poll_ids.extend(ids)
                print(f"║    → {len(poll_ids)} cross-family bridges")

            # Phase 10: Meta-learning (periodic)
            if rnd % self.config["meta_learn_every"] == 0:
                print(f"║  Phase 10: Meta-learning...")
                metas = [a for a in self.agents
                         if isinstance(a, MetaLearnerAgent)]
                for agent in metas:
                    agent.run(rnd)

            # Round summary
            round_time = time.time() - round_start
            stats = self.bb.get_stats()
            by_nov = stats.get("by_novelty", {})
            summary = {
                "round": rnd,
                "new_discoveries": len(round_ids),
                "total_discoveries": stats["total"],
                "verified_known": by_nov.get("verified_known", 0),
                "novel_unproven": by_nov.get("novel_unproven", 0),
                "novel_proven": by_nov.get("novel_proven", 0),
                "validated": stats.get("validated_count", 0),
                "falsified": stats.get("by_status", {}).get("falsified", 0),
                "relay_seed_count": relay_summary.get("seed_count", 0),
                "max_confidence": stats.get("max_confidence", 0),
                "time": round_time,
            }
            self.bb.log_round(rnd, summary)
            self.results_log.append(summary)

            print(f"║")
            print(f"║  Summary: {stats['total']} total | "
                  f"{summary['verified_known']} known | "
                  f"{summary['novel_unproven']} novel-unproven | "
                  f"{summary['novel_proven']} novel-proven | "
                  f"{summary['falsified']} falsified")
            print(f"║  Max confidence: {summary['max_confidence']:.4f} | "
                  f"Time: {round_time:.1f}s")
            print(f"╚{'═' * 62}")
            print()

            # Persist after each round
            self.bb.persist()

        total_time = time.time() - t_start

        # Compile final report
        report = self._compile_report(total_time)
        return report

    def _compile_report(self, total_time: float) -> dict:
        """Compile the v4 final discovery report with theorem-first metrics."""
        stats = self.bb.get_stats()
        top = self.bb.get_top(30)

        # Categorize top discoveries (deduplicated by expression)
        seen_exprs = set()
        breakthroughs = []
        for d in top:
            if d.confidence > 0.7 and d.expression not in seen_exprs:
                breakthroughs.append(d)
                seen_exprs.add(d.expression)

        # Gather each category directly
        novel_proven = self.bb.query(status="novel_proven", limit=100)
        verified_known = self.bb.query(status="verified_known", limit=100)
        novel_unproven = self.bb.query(status="novel_unproven", limit=100)
        validated = self.bb.query(status="validated", limit=100)
        falsified = self.bb.query(status="falsified", limit=100)

        # ── Post-discovery analysis for novel CFs ──
        print("  Running post-discovery analysis on novel candidates...")
        analysis_t0 = time.time()
        demoted_count = 0
        analysis_count = 0
        for disc in novel_unproven:
            if disc.family != "continued_fraction":
                continue
            # Limit total analysis time to 5 minutes
            if time.time() - analysis_t0 > 300:
                print(f"  Analysis time limit reached after {analysis_count} candidates")
                break
            analysis_count += 1
            d_dict = disc.to_dict()
            try:
                analysis = analyze_novel_cf(d_dict, prec=200)
            except (Exception, KeyboardInterrupt) as exc:
                analysis = {"analysis_error": str(exc)}
            disc.metadata.update(analysis)
            if analysis.get("is_algebraic"):
                disc.status = "verified_known"
                disc.category = "verified_known"
                disc.metadata["literature_match"] = (
                    f"Algebraic: {analysis.get('exact_form', analysis.get('minimal_polynomial', ''))}"
                )
                disc.metadata["is_novel"] = False
                demoted_count += 1
            elif (analysis.get("pslq_stable") is True
                  and analysis.get("pslq_recognition", {}).get("found")
                  and analysis.get("pslq_recognition", {}).get("max_coeff", 9999) < 100):
                disc.status = "verified_known"
                disc.category = "verified_known"
                disc.metadata["literature_match"] = (
                    f"PSLQ: {analysis.get('pslq_recognition', {}).get('expression', '')}"
                )
                disc.metadata["is_novel"] = False
                demoted_count += 1
            elif analysis.get("bessel_identification", {}).get("identified"):
                best_id = analysis["bessel_identification"].get("best_identification", {})
                disc.status = "verified_known"
                disc.category = "verified_known"
                disc.metadata["literature_match"] = (
                    f"Bessel/HG: {best_id.get('formula', best_id.get('type', ''))[:80]}"
                )
                disc.metadata["is_novel"] = False
                demoted_count += 1
            elif analysis.get("isc_result", {}).get("found"):
                ids = analysis["isc_result"].get("identifications", [])
                direct = [i for i in ids if "→" not in str(i)]
                if direct:
                    disc.status = "verified_known"
                    disc.category = "verified_known"
                    disc.metadata["literature_match"] = (
                        f"ISC: {direct[0][:60]}"
                    )
                    disc.metadata["is_novel"] = False
                    demoted_count += 1
            elif analysis.get("algebraic_degree", {}).get("is_algebraic"):
                deg = analysis["algebraic_degree"].get("degree_bound", "?")
                poly = analysis["algebraic_degree"].get("minimal_polynomial", "")
                disc.status = "verified_known"
                disc.category = "verified_known"
                disc.metadata["literature_match"] = (
                    f"Algebraic deg {deg}: {poly[:60]}"
                )
                disc.metadata["is_novel"] = False
                demoted_count += 1
            # v4.1: Enhanced closed-form demotion
            elif analysis.get("closed_form_identified"):
                cf_expr = analysis.get("closed_form_expression", "")
                cf_type = analysis.get("closed_form_type", "")
                disc.status = "verified_known"
                disc.category = "verified_known"
                disc.metadata["literature_match"] = (
                    f"Closed form ({cf_type}): {cf_expr[:60]}"
                )
                disc.metadata["is_novel"] = False
                demoted_count += 1

            # v4.1: Convergence gating — flag candidates without convergence guarantees
            conv_check = analysis.get("convergence_check", {})
            if not conv_check.get("converges", True):
                disc.metadata["convergence_warning"] = True
                disc.metadata["convergence_flags"] = conv_check.get("flags", [])
            tier = conv_check.get("convergence_tier", "unknown")
            if tier in ("conditional", "divergent_likely"):
                disc.metadata["convergence_warning"] = True
                disc.metadata["convergence_tier"] = tier
        analysis_time = time.time() - analysis_t0
        if demoted_count > 0:
            print(f"  Analysis demoted {demoted_count} CFs to verified_known")
        # Refresh lists after demotion
        novel_unproven = self.bb.query(status="novel_unproven", limit=100)
        verified_known = self.bb.query(status="verified_known", limit=100)
        novel_proven = self.bb.query(status="novel_proven", limit=100)
        stats = self.bb.get_stats()
        print(f"  Post-analysis: {len(novel_unproven)} novel_unproven, "
              f"{len(verified_known)} verified_known "
              f"({analysis_time:.1f}s)")

        # ── Cluster novel CFs by numeric value ──
        novel_dicts = [d.to_dict() for d in novel_unproven]
        clusters = cluster_by_value(novel_dicts)
        distinct_values = len(clusters)
        duplicate_count = len(novel_unproven) - distinct_values
        if duplicate_count > 0:
            print(f"  Value clustering: {len(novel_unproven)} CFs → "
                  f"{distinct_values} distinct values "
                  f"({duplicate_count} duplicates)")

        # ── Build candidate table ──
        candidate_table = build_candidate_table(novel_dicts)
        tier_counts = {}
        for row in candidate_table:
            t = row.get("priority_tier", "unknown")
            tier_counts[t] = tier_counts.get(t, 0) + 1
        tier_summary = ", ".join(f"{k}: {v}" for k, v in sorted(tier_counts.items()))
        print(f"  Candidate table: {len(candidate_table)} entries ({tier_summary})")

        # ── Compile falsification appendix ──
        falsification_appendix = []
        for disc in falsified:
            entry = {
                "expression": disc.expression,
                "family": disc.family,
                "reason": "",
                "reviews": disc.reviews,
            }
            for rev in disc.reviews:
                if rev.get("verdict") == "falsified":
                    entry["reason"] = rev.get("notes", "")
                    break
            falsification_appendix.append(entry)

        # Agent performance
        agent_stats = {}
        for agent in self.agents:
            agent_stats[agent.config.agent_id] = {
                "type": agent.config.agent_type,
                **agent.stats,
            }

        # Family breakdown
        family_reports = {}
        for family in stats.get("by_family", {}):
            family_discs = self.bb.query(family=family, limit=100)
            family_reports[family] = {
                "count": len(family_discs),
                "best": [d.to_dict() for d in family_discs[:5]],
                "max_confidence": max(
                    (d.confidence for d in family_discs), default=0
                ),
                "proven": sum(1 for d in family_discs
                             if d.status in ("novel_proven", "verified_known")),
                "novel": sum(1 for d in family_discs
                             if d.status in ("novel_proven", "novel_unproven")),
                "validated": sum(
                    1 for d in family_discs if d.status == "validated"
                ),
            }

        # ── Generate proof targets ──
        from .validator import Validator
        proof_targets = Validator.generate_proof_targets(novel_unproven)
        if proof_targets:
            print(f"  Generated {len(proof_targets)} proof targets for novel candidates")

        # ── v3.4: Proof engine — automated CAS proof attempts ──
        print("  Running proof engine on novel CF candidates...")
        proof_t0 = time.time()
        proof_queue = build_proof_queue(novel_dicts, max_queue=20)
        proof_results = []
        proof_scaffolds = []
        proofs_formal = 0
        proofs_partial = 0
        for qc in proof_queue:
            try:
                pr = attempt_proof(qc.discovery, prec=100)
                proof_results.append(pr.to_dict())
                scaffold = format_proof_scaffold(pr, qc.discovery)
                proof_scaffolds.append({
                    "candidate_id": qc.disc_id,
                    "expression": qc.expression,
                    "score": qc.score,
                    "reasons": qc.reasons,
                    "status": pr.status,
                    "confidence": pr.confidence,
                    "proof_text": pr.proof_text,
                    "scaffold": scaffold,
                    "convergence_theorem": pr.convergence.get("theorem_used"),
                    "closed_form": pr.closed_form,
                    "gaps": pr.gaps,
                    "time_seconds": pr.time_seconds,
                })
                if pr.status == "formal_proof":
                    proofs_formal += 1
                elif pr.status == "partial_proof":
                    proofs_partial += 1
                save_bootstrap_case(pr, qc.discovery)
            except Exception as exc:
                proof_results.append({
                    "candidate_id": qc.disc_id,
                    "error": str(exc),
                    "status": "error",
                })
        proof_time = time.time() - proof_t0
        print(f"  Proof engine: {len(proof_queue)} candidates → "
              f"{proofs_formal} formal, {proofs_partial} partial "
              f"({proof_time:.1f}s)")

        # ── v4: Theorem Templates ──
        print("  Inducing theorem templates...")
        all_dicts = [d.to_dict() for d in self.bb.get_top(200)]
        templates = induce_templates(all_dicts)
        template_cards = [format_template_card(t) for t in templates]
        print(f"  Templates: {len(templates)} induced "
              f"({sum(1 for t in templates if t.status == 'proven')} proven, "
              f"{sum(1 for t in templates if t.status == 'validated')} validated)")

        # ── v4: Rigor Ladder Assessment ──
        print("  Assessing rigor ladder...")
        rigor_candidates = novel_dicts + [d.to_dict() for d in novel_proven]
        rigor_data = assess_all(rigor_candidates)
        print(f"  {format_rigor_summary(rigor_data)}")

        # ── v4: Meta-Critic Scoring ──
        print("  Running meta-critic...")
        critic_data = score_batch(rigor_candidates,
                                  rigor_assessments=rigor_data,
                                  templates=templates)
        print(f"  {format_critic_summary(critic_data)}")

        report = {
            "title": "Ramanujan Agent v4.6 — CAS-Verified Theorem Machine",
            "total_time": total_time,
            "global_stats": stats,
            "family_reports": family_reports,
            "agent_stats": agent_stats,
            "top_discoveries": [d.to_dict() for d in top],
            "breakthroughs": [d.to_dict() for d in breakthroughs],
            "novel_proven": [d.to_dict() for d in novel_proven],
            "verified_known": [d.to_dict() for d in verified_known],
            "novel_unproven": [d.to_dict() for d in novel_unproven],
            "validated": [d.to_dict() for d in validated],
            "falsification_appendix": falsification_appendix,
            "proof_targets": proof_targets,
            "proof_results": proof_results,
            "proof_scaffolds": proof_scaffolds,
            "proof_queue": [qc.to_dict() for qc in proof_queue],
            "proof_time": proof_time,
            "candidate_table": candidate_table,
            "value_clusters": {
                "distinct_values": distinct_values,
                "duplicate_count": duplicate_count,
                "clusters": [[novel_dicts[i]["expression"]
                              for i in c] for c in clusters if len(c) > 1],
            },
            "analysis_time": analysis_time,
            # v4 new sections
            "theorem_templates": [t.to_dict() for t in templates],
            "template_cards": template_cards,
            "rigor_ladder": rigor_data,
            "meta_critic": critic_data,
            "relay_chain": {
                "snapshots": self.relay_snapshots,
                "latest": self.relay_snapshots[-1] if self.relay_snapshots else {},
            },
            "results_log": self.results_log,
        }

        # Save JSON
        results_path = Path("results/ramanujan_results.json")
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
        print(f"\n📊 Results saved to {results_path}")

        # Print final summary
        print("\n" + "=" * 70)
        print("  FINAL REPORT (v4.6 — CAS-Verified Theorem Machine)")
        print("=" * 70)
        by_nov = stats.get("by_novelty", {})
        print(f"  Total discoveries: {stats['total']}")
        print(f"  Verified known:    {by_nov.get('verified_known', 0)}")
        print(f"  Novel (unproven):  {by_nov.get('novel_unproven', 0)}")
        print(f"  Novel (proven):    {by_nov.get('novel_proven', 0)}")
        print(f"  Validated:         {stats.get('validated_count', 0)}")
        print(f"  Falsified:         {by_nov.get('falsified', 0)}")
        # v4.1: convergence-gated counts
        conv_warned = sum(1 for d in novel_unproven
                          if d.metadata.get("convergence_warning"))
        conv_clean = len(novel_unproven) - conv_warned
        print(f"  Distinct novel values: {distinct_values}")
        print(f"  Convergence-clean novel: {conv_clean} "
              f"(⚠ {conv_warned} with convergence warnings)")
        closed_form_count = sum(
            1 for d in (self.bb.query(status="verified_known", limit=200)
                        + self.bb.query(status="novel_unproven", limit=200)
                        + self.bb.query(status="novel_proven", limit=200))
            if (d.metadata.get("bessel_identification", {}).get("identified")
                or d.metadata.get("closed_form_identified")
                or "Closed form" in str(d.metadata.get("literature_match", "")))
        )
        print(f"  Closed forms found:  {closed_form_count}")
        print(f"  PSLQ precision:    50→100→200 digits")
        print(f"  Max confidence:    {stats.get('max_confidence', 0):.4f}")
        print(f"  Proof engine:      {proofs_formal} formal, "
              f"{proofs_partial} partial ({proof_time:.1f}s)")

        # v4 theorem-first metrics
        rl = rigor_data.get("by_level", {})
        rt = rigor_data.get("by_tag", {})
        print(f"  ── Theorem Metrics (v4) ──")
        print(f"  Theorems (L3):     {rl.get(3, 0)}")
        print(f"  Conditional (L2):  {rl.get(2, 0)}")
        print(f"  Structural (L1):   {rl.get(1, 0)}")
        print(f"  Numeric only (L0): {rl.get(0, 0)}")
        print(f"  Templates induced: {len(templates)}")
        print(f"  Theorem value:     {critic_data.get('total_theorem_value', 0):.1f}")
        print(f"  Kept / Deprioritized / Suppressed: "
              f"{len(critic_data.get('kept', []))} / "
              f"{len(critic_data.get('deprioritized', []))} / "
              f"{len(critic_data.get('suppressed', []))}")

        print(f"  Total time:        {total_time:.1f}s "
              f"(+{analysis_time:.1f}s analysis, +{proof_time:.1f}s proofs)")

        if breakthroughs:
            print(f"\n  Top breakthroughs:")
            for d in breakthroughs[:5]:
                label = d.metadata.get('literature_match', 'novel?') or 'novel?'
                val_str = d.metadata.get('value_20_digits') or f"{d.value}"
                tag = d.metadata.get('epistemic_tag', d.status)
                print(f"     [{d.family}] {d.expression[:80]}")
                print(f"       value={val_str}")
                print(f"       confidence={d.confidence:.4f}  "
                      f"status={d.status}  tag={tag}  [{label}]")

        # Novel candidates
        if novel_unproven:
            print(f"\n  Novel unproven candidates ({len(novel_unproven)}, "
                  f"{distinct_values} distinct values):")
            for d in novel_unproven[:15]:
                val_str = d.metadata.get('value_20_digits') or f"{d.value}"
                pslq_info = ""
                pr = d.metadata.get('pslq_recognition', {})
                if pr.get('found'):
                    pslq_info = f"  PSLQ: {pr.get('expression', '')[:50]}"
                elif pr.get('found') is False:
                    pslq_info = "  PSLQ: no relation"
                tag = d.metadata.get('epistemic_tag', 'conjecture')
                ref = d.metadata.get('referee_verdict', '')
                print(f"     {d.expression[:60]}  [{tag}]")
                print(f"       = {val_str}{pslq_info}")
                if ref:
                    print(f"       Referee: {ref}")
                bessel = d.metadata.get('bessel_identification', {})
                if bessel.get('identified'):
                    best_b = bessel.get('best_identification', {})
                    print(f"       Bessel/HG: {best_b.get('formula', best_b.get('type', ''))[:70]}")
                alg = d.metadata.get('algebraic_degree', {})
                if alg.get('is_algebraic'):
                    print(f"       Algebraic degree ≤ {alg.get('degree_bound', '?')}")

        # Template summary
        if templates:
            print(f"\n  Theorem Templates ({len(templates)}):")
            for t in templates[:5]:
                print(f"     [{t.status.upper()}] {t.template_type}: "
                      f"{t.instance_count} instances, conf={t.confidence:.0%}")
                print(f"       {t.statement[:80]}...")

        # Proof engine summary
        if proof_scaffolds:
            print(f"\n  Proof Engine ({len(proof_scaffolds)} candidates):")
            for ps in proof_scaffolds:
                status_sym = {"formal_proof": "✓", "partial_proof": "△", "numeric_only": "○"}.get(ps["status"], "?")
                thm = ps.get("convergence_theorem") or "none"
                cf_type = ps.get("closed_form", {}).get("type") or "—"
                print(f"     {status_sym} [{ps['status']}] {ps['expression'][:50]}")
                print(f"       Conv: {thm} | SF: {cf_type} | Conf: {ps['confidence']:.0%}")
                if ps.get("gaps"):
                    print(f"       Gaps: {'; '.join(ps['gaps'][:2])}")
        print("=" * 70)

        return report
