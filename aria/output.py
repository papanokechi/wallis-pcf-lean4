"""
Layer 6 — Output and Iteration Trigger

Every cycle produces three artifacts:
  1. Human-readable report (conjecture, verification, cross-domain resonances, proof roadmap)
  2. Experiment design spec (for wet lab / simulation teams)
  3. Seed conjectures for next iteration (closing the self-iteration loop)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from .conjecture_engine import Conjecture
from .verifier import VerificationResult, Verdict
from .axiom_bank import Axiom, AxiomBank, LostNotebook
from .synthesis import SynthesisResult, CrossDomainSynthesizer


@dataclass
class IterationReport:
    """Full report for one ARIA iteration cycle."""
    generation: int
    timestamp: float
    conjectures_generated: int
    conjectures_verified: int
    conjectures_falsified: int
    new_axioms: int
    lost_notebook_additions: int
    synthesis_results: int
    seed_conjectures: int  # for next iteration
    axiom_bank_size: int
    lost_notebook_size: int
    top_findings: list[dict] = field(default_factory=list)
    experiment_specs: list[str] = field(default_factory=list)


class OutputFormatter:
    """Layer 6: Formats outputs and generates seed conjectures for iteration."""

    def __init__(self, output_dir: str = "results/aria"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports: list[IterationReport] = []

    def format_report(self, generation: int,
                      conjectures: list[Conjecture],
                      verifications: list[VerificationResult],
                      new_axioms: list[Axiom],
                      lost_entries: int,
                      synth_results: list[SynthesisResult],
                      axiom_bank: AxiomBank,
                      lost_notebook: LostNotebook,
                      seed_conjectures: list[Conjecture]) -> IterationReport:
        """Build a full iteration report."""
        n_falsified = sum(1 for v in verifications if v.verdict == Verdict.FALSIFIED)
        n_verified = sum(1 for v in verifications if v.verdict not in
                        (Verdict.FALSIFIED, Verdict.LOST_NOTEBOOK))

        # Top findings: highest-confidence verified conjectures
        top = sorted(
            [(v, c) for v, c in zip(verifications, conjectures)
             if v.verdict not in (Verdict.FALSIFIED, Verdict.LOST_NOTEBOOK)],
            key=lambda x: x[0].confidence,
            reverse=True,
        )[:5]

        top_findings = []
        for v, c in top:
            top_findings.append({
                "statement": c.statement[:200],
                "family": c.family,
                "confidence": v.confidence,
                "verdict": v.verdict.value,
                "cf_depth": c.cf_depth,
            })

        experiment_specs = [sr.experiment_spec for sr in synth_results
                          if sr.experiment_spec]

        report = IterationReport(
            generation=generation,
            timestamp=time.time(),
            conjectures_generated=len(conjectures),
            conjectures_verified=n_verified,
            conjectures_falsified=n_falsified,
            new_axioms=len(new_axioms),
            lost_notebook_additions=lost_entries,
            synthesis_results=len(synth_results),
            seed_conjectures=len(seed_conjectures),
            axiom_bank_size=axiom_bank.size(),
            lost_notebook_size=lost_notebook.size(),
            top_findings=top_findings,
            experiment_specs=experiment_specs,
        )
        self.reports.append(report)
        return report

    def print_report(self, report: IterationReport, file: TextIO | None = None):
        """Print a human-readable report."""
        import sys
        f = file or sys.stdout

        print(f"\n{'═' * 72}", file=f)
        print(f"  ARIA — Iteration {report.generation} Report", file=f)
        print(f"{'═' * 72}", file=f)
        print(f"  Conjectures generated:     {report.conjectures_generated}", file=f)
        print(f"  Verified:                  {report.conjectures_verified}", file=f)
        print(f"  Falsified:                 {report.conjectures_falsified}", file=f)
        print(f"  New axioms:                {report.new_axioms}", file=f)
        print(f"  Lost notebook additions:   {report.lost_notebook_additions}", file=f)
        print(f"  Cross-domain syntheses:    {report.synthesis_results}", file=f)
        print(f"  Seeds for next iteration:  {report.seed_conjectures}", file=f)
        print(f"  ──────────────────────────────────────", file=f)
        print(f"  Axiom bank total:          {report.axiom_bank_size}", file=f)
        print(f"  Lost notebook total:       {report.lost_notebook_size}", file=f)
        print(f"{'─' * 72}", file=f)

        if report.top_findings:
            print(f"\n  TOP FINDINGS:", file=f)
            for i, finding in enumerate(report.top_findings, 1):
                print(f"  {i}. [{finding['verdict']}] (conf={finding['confidence']:.2f}, "
                      f"depth={finding['cf_depth']})", file=f)
                # Wrap long statements
                stmt = finding['statement']
                while len(stmt) > 65:
                    print(f"     {stmt[:65]}", file=f)
                    stmt = stmt[65:]
                print(f"     {stmt}", file=f)

        if report.experiment_specs:
            print(f"\n  EXPERIMENT SPECS: {len(report.experiment_specs)} generated", file=f)
            for i, spec in enumerate(report.experiment_specs[:2], 1):
                print(f"\n  ── Experiment {i} ──", file=f)
                for line in spec.split('\n')[:8]:
                    print(f"  {line}", file=f)
                if spec.count('\n') > 8:
                    print(f"  ... ({spec.count(chr(10)) - 8} more lines)", file=f)

        print(f"\n{'═' * 72}\n", file=f)

    def save_report(self, report: IterationReport, filename: str | None = None):
        """Save report to JSON file."""
        if not filename:
            filename = f"aria_gen{report.generation}.json"
        path = self.output_dir / filename
        data = {
            "generation": report.generation,
            "timestamp": report.timestamp,
            "conjectures_generated": report.conjectures_generated,
            "conjectures_verified": report.conjectures_verified,
            "conjectures_falsified": report.conjectures_falsified,
            "new_axioms": report.new_axioms,
            "lost_notebook_additions": report.lost_notebook_additions,
            "synthesis_results": report.synthesis_results,
            "seed_conjectures": report.seed_conjectures,
            "axiom_bank_size": report.axiom_bank_size,
            "lost_notebook_size": report.lost_notebook_size,
            "top_findings": report.top_findings,
            "experiment_specs_count": len(report.experiment_specs),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(path)

    def generate_seed_conjectures(self, axiom_bank: AxiomBank,
                                  lost_notebook: LostNotebook,
                                  generation: int) -> list[Conjecture]:
        """Generate seed conjectures for the next iteration.

        Sources:
          1. High-generativity axioms suggest parameter extensions
          2. Lost notebook entries due for review
          3. Open ends of analogy chains
        """
        seeds = []

        # Source 1: Extend high-generativity axioms
        top_axioms = axiom_bank.get_top_generative(limit=3)
        for axiom in top_axioms:
            seed = Conjecture(
                id="",
                statement=(
                    f"SEED: Extend axiom '{axiom.id}' "
                    f"(L={axiom.L_value:.4f}, gen={axiom.generativity:.0f}) "
                    f"to adjacent parameter space. Look for objects with "
                    f"L ∈ [{axiom.L_value - 0.3:.2f}, {axiom.L_value + 0.3:.2f}]."
                ),
                family="axiom_extension",
                confidence=0.2 * min(axiom.generativity + 1, 10) / 10,
                source_objects=axiom.source_objects,
                generation=generation + 1,
                metadata={"parent_axiom": axiom.id, "is_seed": True},
            )
            seeds.append(seed)

        # Source 2: Lost notebook review
        due = lost_notebook.get_due_for_review(generation)
        for entry in due[:3]:
            seed = Conjecture(
                id="",
                statement=(
                    f"SEED: Re-evaluate lost notebook entry '{entry.id}' "
                    f"(quarantined gen {entry.generation}, weirdness={entry.weirdness_score:.2f}). "
                    f"Reason: '{entry.reason}'. "
                    f"Axiom bank has grown by {axiom_bank.size()} since quarantine."
                ),
                family="orphan_match",
                confidence=0.15,
                generation=generation + 1,
                metadata={"lost_notebook_id": entry.id, "is_seed": True},
            )
            seeds.append(seed)
            lost_notebook.mark_reviewed(entry.id, generation,
                                       note="Seeded for re-evaluation")

        return seeds

    def save_html_report(self, extra_data: dict | None = None,
                         filename: str = "aria-report.html") -> str:
        """Save a full self-contained HTML report of all iterations."""
        import html as html_mod
        from datetime import datetime

        path = self.output_dir / filename
        cumul = self.cumulative_summary()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Collect per-iteration rows ──
        iter_rows = ""
        for r in self.reports:
            vr = r.conjectures_verified / max(r.conjectures_generated, 1)
            iter_rows += (
                f"<tr><td>{r.generation}</td>"
                f"<td>{r.conjectures_generated}</td>"
                f"<td>{r.conjectures_verified}</td>"
                f"<td>{r.conjectures_falsified}</td>"
                f"<td>{r.new_axioms}</td>"
                f"<td>{r.lost_notebook_additions}</td>"
                f"<td>{r.synthesis_results}</td>"
                f"<td>{r.seed_conjectures}</td>"
                f"<td>{vr:.0%}</td></tr>\n"
            )

        # ── Top findings across all iterations ──
        all_findings = []
        for r in self.reports:
            for f in r.top_findings:
                f["generation"] = r.generation
                all_findings.append(f)
        all_findings.sort(key=lambda x: x["confidence"], reverse=True)

        finding_cards = ""
        for i, f in enumerate(all_findings[:10], 1):
            verdict_class = "verified" if "verified" in f["verdict"] else "other"
            stmt = html_mod.escape(f["statement"])
            finding_cards += f"""
            <div class="card finding-{verdict_class}">
              <div class="card-header">
                <span class="badge badge-{verdict_class}">{html_mod.escape(f['verdict'])}</span>
                <span class="confidence">Confidence: {f['confidence']:.2f}</span>
                <span class="meta">Gen {f['generation']} &middot; {html_mod.escape(f['family'])} &middot; CF depth {f['cf_depth']}</span>
              </div>
              <p class="statement">{stmt}</p>
            </div>"""

        # ── Experiment specs ──
        exp_html = ""
        exp_count = 0
        for r in self.reports:
            for spec in r.experiment_specs:
                exp_count += 1
                exp_html += f"""
                <div class="card experiment">
                  <h4>Experiment {exp_count} (Iteration {r.generation})</h4>
                  <pre>{html_mod.escape(spec)}</pre>
                </div>"""

        # ── Extra data sections (axiom bank, lost notebook, encoder, etc.) ──
        extra_sections = ""
        if extra_data:
            for section_name, section_data in extra_data.items():
                rows = ""
                if isinstance(section_data, dict):
                    for k, v in section_data.items():
                        rows += f"<tr><td>{html_mod.escape(str(k))}</td><td>{html_mod.escape(str(v))}</td></tr>\n"
                extra_sections += f"""
                <div class="section">
                  <h3>{html_mod.escape(section_name)}</h3>
                  <table class="stats-table"><tbody>{rows}</tbody></table>
                </div>"""

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ARIA — Discovery Report</title>
<style>
  :root {{
    --bg: #0a0a1a; --surface: #12122a; --surface2: #1a1a3a;
    --border: #2a2a5a; --text: #e0e0f0; --text-dim: #8888aa;
    --accent: #6c5ce7; --accent2: #00cec9; --gold: #fdcb6e;
    --green: #00b894; --red: #ff6b6b; --blue: #74b9ff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6;
    min-height: 100vh;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}

  /* Header */
  .hero {{
    text-align: center; padding: 3rem 1rem; margin-bottom: 2rem;
    background: linear-gradient(135deg, #1a1a3a 0%, #0d0d2b 100%);
    border: 1px solid var(--border); border-radius: 12px;
    position: relative; overflow: hidden;
  }}
  .hero::before {{
    content: ''; position: absolute; top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at 30% 50%, rgba(108,92,231,0.08) 0%, transparent 60%),
                radial-gradient(ellipse at 70% 50%, rgba(0,206,201,0.06) 0%, transparent 60%);
    animation: shimmer 15s ease-in-out infinite alternate;
  }}
  @keyframes shimmer {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(3deg); }} }}
  .hero h1 {{ font-size: 2.8rem; letter-spacing: 0.3em; color: var(--accent); position: relative; }}
  .hero .subtitle {{ color: var(--accent2); font-size: 1.1rem; margin-top: 0.5rem; position: relative; }}
  .hero .timestamp {{ color: var(--text-dim); font-size: 0.85rem; margin-top: 1rem; position: relative; }}

  /* Summary grid */
  .summary-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem; margin-bottom: 2rem;
  }}
  .stat-box {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.2rem; text-align: center;
  }}
  .stat-box .value {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
  .stat-box .label {{ font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; }}

  /* Sections */
  .section {{ margin-bottom: 2rem; }}
  .section h2 {{
    font-size: 1.4rem; color: var(--accent2); margin-bottom: 1rem;
    padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);
  }}
  .section h3 {{
    font-size: 1.15rem; color: var(--gold); margin-bottom: 0.75rem;
  }}

  /* Tables */
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: var(--surface2); color: var(--accent2); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  tr:hover {{ background: rgba(108,92,231,0.05); }}
  .stats-table td:first-child {{ color: var(--text-dim); font-weight: 500; width: 50%; }}

  /* Cards */
  .card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 1rem 1.2rem; margin-bottom: 0.8rem;
  }}
  .card-header {{ display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; margin-bottom: 0.5rem; }}
  .badge {{
    display: inline-block; padding: 0.15rem 0.6rem; border-radius: 4px;
    font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
  }}
  .badge-verified {{ background: rgba(0,184,148,0.15); color: var(--green); border: 1px solid rgba(0,184,148,0.3); }}
  .badge-other {{ background: rgba(253,203,110,0.15); color: var(--gold); border: 1px solid rgba(253,203,110,0.3); }}
  .confidence {{ color: var(--blue); font-size: 0.85rem; }}
  .meta {{ color: var(--text-dim); font-size: 0.8rem; margin-left: auto; }}
  .statement {{ font-size: 0.9rem; line-height: 1.5; color: var(--text); }}
  .finding-verified {{ border-left: 3px solid var(--green); }}
  .finding-other {{ border-left: 3px solid var(--gold); }}
  .experiment {{ border-left: 3px solid var(--accent); }}
  .experiment h4 {{ color: var(--accent); margin-bottom: 0.5rem; }}
  .experiment pre {{
    background: var(--bg); padding: 1rem; border-radius: 6px; overflow-x: auto;
    font-size: 0.82rem; line-height: 1.5; color: var(--text-dim);
    white-space: pre-wrap; word-break: break-word;
  }}

  /* Architecture diagram */
  .arch-flow {{
    display: flex; align-items: center; justify-content: center; flex-wrap: wrap;
    gap: 0.5rem; padding: 1.5rem; background: var(--surface); border-radius: 8px;
    border: 1px solid var(--border); margin-bottom: 2rem;
  }}
  .arch-node {{
    padding: 0.5rem 1rem; border-radius: 6px; font-size: 0.8rem; font-weight: 600;
    background: var(--surface2); border: 1px solid var(--border); color: var(--text);
  }}
  .arch-node.active {{ border-color: var(--accent); color: var(--accent); }}
  .arch-arrow {{ color: var(--text-dim); font-size: 1.2rem; }}

  /* Footer */
  .footer {{ text-align: center; padding: 2rem 0; color: var(--text-dim); font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">

  <!-- Hero -->
  <div class="hero">
    <h1>A R I A</h1>
    <p class="subtitle">Autonomous Reasoning &amp; Intuition Architecture &mdash; Discovery Report</p>
    <p class="timestamp">Generated {html_mod.escape(now)} &middot; {cumul.get('iterations', 0)} iterations</p>
  </div>

  <!-- Architecture flow -->
  <div class="arch-flow">
    <span class="arch-node active">Layer 0: Ingest</span><span class="arch-arrow">&rarr;</span>
    <span class="arch-node active">Layer 1: Encode</span><span class="arch-arrow">&rarr;</span>
    <span class="arch-node active">Layer 2: Conjecture</span><span class="arch-arrow">&rarr;</span>
    <span class="arch-node active">Layer 3: Verify</span><span class="arch-arrow">&rarr;</span>
    <span class="arch-node">Layer 4: Axiom Bank / Lost Notebook</span><span class="arch-arrow">&rarr;</span>
    <span class="arch-node">Layer 5: Synthesize</span><span class="arch-arrow">&rarr;</span>
    <span class="arch-node">Layer 6: Iterate</span>
  </div>

  <!-- Summary stats -->
  <div class="summary-grid">
    <div class="stat-box"><div class="value">{cumul.get('total_conjectures_generated', 0)}</div><div class="label">Conjectures</div></div>
    <div class="stat-box"><div class="value">{cumul.get('total_verified', 0)}</div><div class="label">Verified</div></div>
    <div class="stat-box"><div class="value">{cumul.get('total_new_axioms', 0)}</div><div class="label">Axioms</div></div>
    <div class="stat-box"><div class="value">{cumul.get('total_syntheses', 0)}</div><div class="label">Syntheses</div></div>
    <div class="stat-box"><div class="value">{cumul.get('total_experiments', 0)}</div><div class="label">Experiments</div></div>
    <div class="stat-box"><div class="value">{cumul.get('verification_rate', 0):.0%}</div><div class="label">Verification Rate</div></div>
  </div>

  <!-- Iteration table -->
  <div class="section">
    <h2>Iteration History</h2>
    <table>
      <thead><tr>
        <th>Gen</th><th>Generated</th><th>Verified</th><th>Falsified</th>
        <th>New Axioms</th><th>Lost NB</th><th>Syntheses</th><th>Seeds</th><th>Rate</th>
      </tr></thead>
      <tbody>{iter_rows}</tbody>
    </table>
  </div>

  <!-- Top findings -->
  <div class="section">
    <h2>Top Findings</h2>
    {finding_cards if finding_cards else '<p style="color:var(--text-dim)">No verified findings yet.</p>'}
  </div>

  <!-- Experiment specs -->
  <div class="section">
    <h2>Experiment Specifications</h2>
    {exp_html if exp_html else '<p style="color:var(--text-dim)">No experiment specs generated.</p>'}
  </div>

  <!-- Extra data sections -->
  {extra_sections}

  <div class="footer">
    ARIA v0.1.0 &middot; Autonomous Reasoning &amp; Intuition Architecture &middot; Self-iterating Ramanujan discovery engine
  </div>
</div>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(path)

    def cumulative_summary(self) -> dict:
        """Summary across all iterations."""
        if not self.reports:
            return {"iterations": 0}
        total_generated = sum(r.conjectures_generated for r in self.reports)
        total_verified = sum(r.conjectures_verified for r in self.reports)
        total_axioms = sum(r.new_axioms for r in self.reports)
        total_synth = sum(r.synthesis_results for r in self.reports)
        total_experiments = sum(len(r.experiment_specs) for r in self.reports)
        return {
            "iterations": len(self.reports),
            "total_conjectures_generated": total_generated,
            "total_verified": total_verified,
            "total_new_axioms": total_axioms,
            "total_syntheses": total_synth,
            "total_experiments": total_experiments,
            "verification_rate": total_verified / max(total_generated, 1),
            "axiom_rate": total_axioms / max(total_generated, 1),
        }
