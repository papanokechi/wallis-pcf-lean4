"""
ARIA Orchestrator — The self-iterating discovery loop.

Wires all layers together:
  Layer 0 (Ingestion) → Layer 1 (Encoder) → Layer 2 (Conjecture Engine)
  → Layer 3 (Telescoping Verifier) → Layer 4A/4B (Axiom Bank / Lost Notebook)
  → Layer 5 (Cross-Domain Synthesis) → Layer 6 (Output & Iteration)

Each iteration:
  1. Encode all data through the Ramanujan lens
  2. Generate conjectures (leap first)
  3. Telescope through 4 verification rounds (kill fast)
  4. Promote survivors to axiom bank, interesting failures to lost notebook
  5. Synthesize cross-domain results
  6. Generate seed conjectures for next iteration
  7. Re-ingest, re-encode with expanded axiom base
"""

from __future__ import annotations

import time

from .ingestion import KnowledgeIngestor, DataObject, Domain
from .encoder import RamanujanEncoder
from .conjecture_engine import ConjectureEngine, AnalogyGraph, Conjecture
from .verifier import TelescopingVerifier, Verdict
from .axiom_bank import AxiomBank, LostNotebook
from .synthesis import CrossDomainSynthesizer
from .output import OutputFormatter, IterationReport


class ARIAOrchestrator:
    """The self-iterating Ramanujan discovery engine."""

    DEFAULT_CONFIG = {
        "max_iterations": 3,
        "encoder_precision": 50,
        "verifier_max_rounds": 4,
        "resonance_threshold": 0.15,
        "lost_notebook_review_interval": 2,
        "output_dir": "results/aria",
        "axiom_persist_path": "results/aria/axiom_bank.json",
        "verbose": True,
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        # Layer 0: Knowledge Ingestion
        self.ingestor = KnowledgeIngestor()

        # Layer 1: Ramanujan Encoder
        self.encoder = RamanujanEncoder(
            precision=self.config["encoder_precision"]
        )

        # Layer 2: Conjecture Engine
        self.analogy_graph = AnalogyGraph()
        self.engine = ConjectureEngine(self.encoder, self.analogy_graph)

        # Layer 3: Telescoping Verifier
        self.verifier = TelescopingVerifier(
            encoder=self.encoder,
            max_rounds=self.config["verifier_max_rounds"],
        )

        # Layer 4A/4B: Axiom Bank & Lost Notebook
        self.axiom_bank = AxiomBank(
            persist_path=self.config["axiom_persist_path"]
        )
        self.lost_notebook = LostNotebook(
            review_interval=self.config["lost_notebook_review_interval"]
        )

        # Layer 5: Cross-Domain Synthesis
        self.synthesizer = CrossDomainSynthesizer(self.axiom_bank)

        # Layer 6: Output & Iteration
        self.formatter = OutputFormatter(
            output_dir=self.config["output_dir"]
        )

        self.generation = 0

    def run(self) -> dict:
        """Execute the full ARIA self-iterating discovery loop."""
        t_start = time.time()
        max_iter = self.config["max_iterations"]
        verbose = self.config["verbose"]

        if verbose:
            self._print_banner()

        # ── Phase 0: Initial ingestion ──
        if verbose:
            print("  [Layer 0] Ingesting seed data...")
        objects = self.ingestor.ingest_all_seeds()
        if verbose:
            summary = self.ingestor.summary()
            print(f"    → {summary['total_objects']} objects across "
                  f"{len(summary['by_domain'])} domains")

        # ── Phase 1: Initial encoding ──
        if verbose:
            print("  [Layer 1] Encoding through Ramanujan lens...")
        encoded = self.encoder.encode_all(objects)
        if verbose:
            esummary = self.encoder.summary()
            print(f"    → {esummary['total_encoded']} encoded, "
                  f"{esummary['with_partition_sig']} with signatures, "
                  f"{esummary['orphans']} orphans")

        # ── Main iteration loop ──
        all_reports = []
        for iteration in range(1, max_iter + 1):
            self.generation = iteration
            report = self._run_iteration(iteration, verbose)
            all_reports.append(report)

            if verbose:
                self.formatter.print_report(report)

            # Save report
            self.formatter.save_report(report)

        # ── Final summary ──
        elapsed = time.time() - t_start
        cumulative = self.formatter.cumulative_summary()

        if verbose:
            self._print_final_summary(cumulative, elapsed)

        # ── Save HTML report ──
        extra_data = {
            "Axiom Bank": self.axiom_bank.summary(),
            "Lost Notebook": self.lost_notebook.summary(),
            "Verifier Stats": self.verifier.summary(),
            "Encoder Stats": self.encoder.summary(),
            "Synthesizer Stats": self.synthesizer.summary(),
        }
        html_path = self.formatter.save_html_report(
            extra_data=extra_data, filename="aria-report.html"
        )
        if verbose:
            print(f"  HTML report saved → {html_path}")

        return {
            "iterations": max_iter,
            "elapsed_seconds": elapsed,
            "cumulative": cumulative,
            "axiom_bank": self.axiom_bank.summary(),
            "lost_notebook": self.lost_notebook.summary(),
            "verifier": self.verifier.summary(),
            "encoder": self.encoder.summary(),
            "synthesizer": self.synthesizer.summary(),
            "html_report": html_path,
        }

    def _run_iteration(self, iteration: int, verbose: bool) -> IterationReport:
        """Execute one iteration of the ARIA loop."""
        if verbose:
            print(f"\n{'╔' + '═' * 70}")
            print(f"║  ARIA — Iteration {iteration}")
            print(f"{'╚' + '═' * 70}")

        # ── Layer 2: Generate conjectures ──
        if verbose:
            print(f"  [Layer 2] Generating conjectures...")
        conjectures = self.engine.generate_all(
            axiom_bank=self.axiom_bank,
            lost_notebook=self.lost_notebook,
        )
        if verbose:
            print(f"    → {len(conjectures)} conjectures generated")
            fam_counts = {}
            for c in conjectures:
                fam_counts[c.family] = fam_counts.get(c.family, 0) + 1
            for fam, count in fam_counts.items():
                print(f"      {fam}: {count}")

        # ── Layer 3: Telescoping verification ──
        if verbose:
            print(f"  [Layer 3] Adversarial telescoping verification...")
        verifications = self.verifier.verify_batch(conjectures)

        new_axioms = []
        lost_count = 0

        for cj, vr in zip(conjectures, verifications):
            if vr.verdict in (Verdict.VERIFIED_FULL, Verdict.VERIFIED_ADVERSARIAL,
                              Verdict.VERIFIED_SYMBOLIC, Verdict.VERIFIED_NUMERIC):
                axiom = self.axiom_bank.add(cj, vr, iteration)
                new_axioms.append(axiom)
            elif vr.verdict == Verdict.LOST_NOTEBOOK:
                # Interesting failure → quarantine
                weirdness = self._compute_weirdness(cj, vr)
                self.lost_notebook.quarantine(
                    cj, vr,
                    reason=self._extract_failure_reason(vr),
                    generation=iteration,
                    weirdness=weirdness,
                )
                lost_count += 1

        if verbose:
            vstats = self.verifier.summary()
            print(f"    → Killed R1: {vstats['killed_r1']}, R2: {vstats['killed_r2']}, "
                  f"R3: {vstats['killed_r3']}, R4: {vstats['killed_r4']}")
            print(f"    → {len(new_axioms)} new axioms, {lost_count} lost notebook entries")

        # ── Layer 5: Cross-domain synthesis ──
        if verbose:
            print(f"  [Layer 5] Cross-domain synthesis...")
        synth_results = []
        for axiom in new_axioms:
            synth_results.extend(self.synthesizer.synthesize(axiom))
        if verbose:
            print(f"    → {len(synth_results)} synthesis results")
            essential = sum(1 for r in synth_results if r.isomorphism.is_essential)
            print(f"    → {essential} essential isomorphisms")

        # ── Layer 6: Output and seeds ──
        if verbose:
            print(f"  [Layer 6] Generating seeds for next iteration...")
        seeds = self.formatter.generate_seed_conjectures(
            self.axiom_bank, self.lost_notebook, iteration
        )
        if verbose:
            print(f"    → {len(seeds)} seed conjectures for iteration {iteration + 1}")

        # Build report
        report = self.formatter.format_report(
            generation=iteration,
            conjectures=conjectures,
            verifications=verifications,
            new_axioms=new_axioms,
            lost_entries=lost_count,
            synth_results=synth_results,
            axiom_bank=self.axiom_bank,
            lost_notebook=self.lost_notebook,
            seed_conjectures=seeds,
        )

        return report

    def _compute_weirdness(self, cj: Conjecture, vr: VerificationResult) -> float:
        """Compute a weirdness score for a conjecture.

        High weirdness = interesting for the lost notebook.
        """
        score = 0.0

        # Near-miss: high confidence but failed
        if vr.confidence > 0.5:
            score += 2.0

        # Multi-domain: more domains = weirder if it fails
        n_domains = len(set(cj.source_objects))
        score += 0.5 * n_domains

        # High CF depth = unexpectedly deep pattern
        if cj.cf_depth >= 4:
            score += 1.5

        # Orphan match failures are particularly interesting
        if cj.family == "orphan_match":
            score += 1.0

        return min(score, 10.0)

    def _extract_failure_reason(self, vr: VerificationResult) -> str:
        """Extract the main failure reason from verification result."""
        for rr in reversed(vr.round_results):
            if not rr.passed:
                return f"Failed {rr.round_name}: {rr.details[:100]}"
        return "Unknown failure"

    def ingest_custom(self, name: str, sequence: list[float],
                      domain: Domain = Domain.CUSTOM,
                      gf_hint: str | None = None) -> DataObject:
        """Add custom data to the system and encode it."""
        obj = self.ingestor.ingest_custom(name, sequence, domain, gf_hint)
        self.encoder.encode(obj)
        return obj

    def _print_banner(self):
        print()
        print("╔══════════════════════════════════════════════════════════════════════╗")
        print("║                                                                      ║")
        print("║    █████╗ ██████╗ ██╗ █████╗                                         ║")
        print("║   ██╔══██╗██╔══██╗██║██╔══██╗                                        ║")
        print("║   ███████║██████╔╝██║███████║                                         ║")
        print("║   ██╔══██║██╔══██╗██║██╔══██║                                         ║")
        print("║   ██║  ██║██║  ██║██║██║  ██║                                         ║")
        print("║   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝                                      ║")
        print("║                                                                      ║")
        print("║   Autonomous Reasoning & Intuition Architecture v0.1                 ║")
        print("║   Self-iterating Ramanujan discovery engine                          ║")
        print("║                                                                      ║")
        print("║   Layers: Ingest → Encode → Conjecture → Verify → Axiomatize        ║")
        print("║           → Synthesize → Iterate                                     ║")
        print("║                                                                      ║")
        print("╚══════════════════════════════════════════════════════════════════════╝")
        print()

    def _print_final_summary(self, cumulative: dict, elapsed: float):
        print()
        print("╔══════════════════════════════════════════════════════════════════════╗")
        print("║  ARIA — Final Summary                                               ║")
        print("╠══════════════════════════════════════════════════════════════════════╣")
        print(f"║  Iterations completed:     {cumulative['iterations']:>6}                               ║")
        print(f"║  Total conjectures:        {cumulative['total_conjectures_generated']:>6}                               ║")
        print(f"║  Total verified:           {cumulative['total_verified']:>6}                               ║")
        print(f"║  Total new axioms:         {cumulative['total_new_axioms']:>6}                               ║")
        print(f"║  Cross-domain syntheses:   {cumulative['total_syntheses']:>6}                               ║")
        print(f"║  Experiment specs:         {cumulative['total_experiments']:>6}                               ║")
        print(f"║  Verification rate:        {cumulative['verification_rate']:>6.1%}                               ║")
        print(f"║  Elapsed:                  {elapsed:>6.1f}s                               ║")
        print("╠══════════════════════════════════════════════════════════════════════╣")

        ab = self.axiom_bank.summary()
        ln = self.lost_notebook.summary()
        print(f"║  Axiom bank:  {ab.get('total', 0)} axioms"
              f" (avg generativity: {ab.get('avg_generativity', 0):.1f})"
              f"{'':>20}║")
        print(f"║  Lost notebook: {ln.get('total', 0)} entries"
              f" (avg weirdness: {ln.get('avg_weirdness', 0):.1f})"
              f"{'':>18}║")
        print("╚══════════════════════════════════════════════════════════════════════╝")
        print()


def run_aria(config: dict | None = None) -> dict:
    """Convenience function to run ARIA with default or custom config."""
    orchestrator = ARIAOrchestrator(config)
    return orchestrator.run()
