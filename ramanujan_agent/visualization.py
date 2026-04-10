"""
visualization.py — Interactive HTML report generator for Ramanujan Agent.

Generates a comprehensive single-file HTML report with:
 - Executive summary dashboard
 - Family-by-family discovery breakdowns
 - Top discoveries with confidence bars
 - Proof sketches
 - Agent performance table
 - Progress chart (Canvas-based)
 - Discovery timeline
"""

from __future__ import annotations
import html
import json
import time
from pathlib import Path
from typing import Any


def generate_html_report(results: dict, output_path: str = "") -> str:
    """Generate the full interactive HTML report."""

    total_time = results.get("total_time", 0)
    stats = results.get("global_stats", {})
    family_reports = results.get("family_reports", {})
    agent_stats = results.get("agent_stats", {})
    top_discoveries = results.get("top_discoveries", [])
    breakthroughs = results.get("breakthroughs", [])
    novel_proven = results.get("novel_proven", results.get("proven", []))
    verified_known = results.get("verified_known", [])
    novel_unproven = results.get("novel_unproven", [])
    results_log = results.get("results_log", [])
    falsification_appendix = results.get("falsification_appendix", [])
    value_clusters = results.get("value_clusters", {})
    analysis_time = results.get("analysis_time", 0)
    proof_targets = results.get("proof_targets", [])
    candidate_table = results.get("candidate_table", [])
    proof_scaffolds = results.get("proof_scaffolds", [])
    proof_time = results.get("proof_time", 0)
    # v4 new data
    theorem_templates = results.get("theorem_templates", [])
    template_cards_data = results.get("template_cards", [])
    rigor_ladder = results.get("rigor_ladder", {})
    meta_critic = results.get("meta_critic", {})

    # ── Build family sections ──
    family_icons = {
        "pi_series": "π", "continued_fraction": "⋯",
        "q_series": "𝑞", "mock_theta": "θ̃",
        "partition": "𝑝(𝑛)", "tau_function": "τ",
        "integer_relation": "ℤ", "cross_pollination": "🔗",
        "meta": "🧠",
    }
    family_labels = {
        "pi_series": "Pi Series (Ramanujan-type)",
        "continued_fraction": "Continued Fractions",
        "q_series": "q-Series & Theta Functions",
        "mock_theta": "Mock Theta Functions",
        "partition": "Partition Identities",
        "tau_function": "Ramanujan Tau Function",
        "integer_relation": "Integer Relations (PSLQ)",
        "cross_pollination": "Cross-Family Bridges",
        "meta": "Meta-Insights",
    }

    family_sections = []
    for fam_key, fam_data in sorted(family_reports.items(),
                                     key=lambda x: -x[1].get("count", 0)):
        icon = family_icons.get(fam_key, "📐")
        label = family_labels.get(fam_key, fam_key)
        count = fam_data.get("count", 0)
        max_conf = fam_data.get("max_confidence", 0)
        n_proven = fam_data.get("proven", 0)
        n_validated = fam_data.get("validated", 0)
        best = fam_data.get("best", [])

        best_cards = "\n".join(_discovery_card(d) for d in best[:5])

        family_sections.append(f"""
        <div class="family-section" id="family-{html.escape(fam_key)}">
            <h2><span class="family-icon">{icon}</span> {html.escape(label)}</h2>
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value">{count}</div>
                    <div class="stat-label">Discoveries</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{max_conf:.3f}</div>
                    <div class="stat-label">Max Confidence</div>
                </div>
                <div class="stat-card accent">
                    <div class="stat-value">{n_proven}</div>
                    <div class="stat-label">Verified / Proven</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{fam_data.get('novel', 0)}</div>
                    <div class="stat-label">Novel</div>
                </div>
            </div>
            <div class="discovery-list">{best_cards}</div>
        </div>
        """)

    # ── Top discoveries ──
    top_cards = "\n".join(_discovery_card(d) for d in top_discoveries[:15])

    # ── Breakthroughs ──
    breakthrough_cards = "\n".join(_discovery_card(d) for d in breakthroughs[:10])

    # -- Proven identities --
    proven_cards = "\n".join(_discovery_card(d) for d in novel_proven[:10])

    # -- Verified known (v4.2: compact table instead of full cards) --
    known_table_rows = ""
    for d in verified_known[:20]:
        k_expr = html.escape(str(d.get("expression", ""))[:50])
        k_val = html.escape(str(d.get("value", ""))[:15])
        k_meta = d.get("metadata", {})
        k_target = html.escape(str(d.get("target", k_meta.get("matched_constant", "")))[:30])
        k_err = d.get("error", k_meta.get("best_match_error", 0))
        k_err_str = f"{k_err:.1e}" if isinstance(k_err, float) else str(k_err)[:12]
        k_lit = html.escape(str(k_meta.get("literature_match", ""))[:40])
        known_table_rows += (
            f"<tr><td><code>{k_expr}</code></td>"
            f"<td class='mono'>{k_val}</td>"
            f"<td>{k_target}</td>"
            f"<td>{k_err_str}</td>"
            f"<td>{k_lit}</td></tr>\n"
        )

    # -- Novel unproven (show all, not capped at 10) --
    novel_cards = "\n".join(_discovery_card(d) for d in novel_unproven[:30])

    # -- Value clustering info --
    cluster_html = ""
    dup_clusters = value_clusters.get("clusters", [])
    if dup_clusters:
        cluster_items = ""
        for cl in dup_clusters[:10]:
            exprs = ", ".join(html.escape(str(e)[:40]) for e in cl)
            cluster_items += f"<li>{exprs}</li>"
        cluster_html = (
            f'<div class="cluster-info">'
            f'<strong>Value clustering:</strong> '
            f'{value_clusters.get("distinct_values", "?")} distinct values '
            f'({value_clusters.get("duplicate_count", 0)} duplicates)'
            f'<ul>{cluster_items}</ul></div>'
        )

    # -- Falsification appendix --
    falsified_rows = ""
    for entry in falsification_appendix[:30]:
        expr = html.escape(str(entry.get("expression", ""))[:80])
        fam = html.escape(str(entry.get("family", "")))
        reason = html.escape(str(entry.get("reason", ""))[:120])
        falsified_rows += (
            f"<tr><td>{fam}</td><td><code>{expr}</code></td>"
            f"<td>{reason}</td></tr>"
        )

    # -- Candidate analysis table (v3.3) --
    candidate_rows = ""
    for row in candidate_table:
        c_expr = html.escape(str(row.get("expression", ""))[:50])
        c_val = html.escape(str(row.get("value_20_digits", ""))[:22])
        c_tier = row.get("priority_tier", "unknown")
        tier_label = {"tier1_isc_priority": '<span class="badge tier-1">Tier 1</span>',
                      "tier2_flagged": '<span class="badge tier-2">Tier 2</span>',
                      "tier3_novel": '<span class="badge tier-3">Tier 3</span>'}.get(c_tier, c_tier)

        # ISC result
        isc = row.get("isc_result", {})
        if isc.get("found"):
            ids = isc.get("identifications", [])
            isc_str = html.escape(str(ids[0])[:40]) if ids else "—"
        else:
            isc_str = "No match"

        # Algebraic degree
        alg = row.get("algebraic_degree", {})
        if alg.get("is_algebraic"):
            alg_str = f"deg ≤ {alg.get('degree_bound', '?')}"
        else:
            alg_str = "Not alg. (≤6)"

        # Bessel/HG — show exact (ν, z) parameters when identified
        bessel = row.get("bessel_hg_id", {})
        if bessel.get("identified"):
            best = bessel.get("best_identification", {})
            b_type = best.get("type", "")
            b_formula = best.get("formula_short") or best.get("formula", "")
            digits = best.get("match_digits", 0)
            if b_formula and len(b_formula) <= 60:
                bessel_str = html.escape(b_formula) + f" ({digits}d)"
            else:
                bessel_str = html.escape(str(b_type)[:25]) + f" ({digits}d)"
        else:
            bessel_str = "—"

        # Convergence
        conv = row.get("convergence", {})
        if not conv.get("converges", True):
            conv_str = '<span class="conv-flag">⚠ Issue</span>'
        elif conv.get("convergence_tier") == "strong":
            conv_str = "✓ Strong"
        elif conv.get("convergence_tier") == "very_strong":
            conv_str = "✓ V. Strong"
        elif conv.get("convergence_tier") == "superexponential":
            conv_str = "✓ Superexp."
        elif conv.get("convergence_tier") == "exponential":
            conv_str = "✓ Exp."
        elif conv.get("convergence_tier") == "polynomial":
            conv_str = "✓ Poly."
        else:
            conv_str = "✓"

        # Final status
        final = html.escape(str(row.get("final_status", ""))[:40])

        candidate_rows += (
            f"<tr>"
            f"<td>{tier_label}</td>"
            f"<td><code class='cf-expr'>{c_expr}</code></td>"
            f"<td class='mono'>{c_val}</td>"
            f"<td>{isc_str}</td>"
            f"<td>{alg_str}</td>"
            f"<td>{bessel_str}</td>"
            f"<td>{conv_str}</td>"
            f"<td><strong>{final}</strong></td>"
            f"</tr>"
        )

    # ── Agent performance table ──
    agent_rows = "\n".join(f"""
        <tr>
            <td><code>{html.escape(str(aid))}</code></td>
            <td><span class="agent-badge agent-{html.escape(str(a.get('type', '')))}">{html.escape(str(a.get('type', '')))}</span></td>
            <td>{a.get('rounds', 0)}</td>
            <td>{a.get('discoveries_posted', 0)}</td>
            <td>{a.get('time_spent', 0):.1f}s</td>
        </tr>
    """ for aid, a in sorted(agent_stats.items()))

    # ── Progress data ──
    progress_json = json.dumps(results_log, default=str)

    # ── Status breakdown ──
    by_status = stats.get("by_status", {})
    status_items = " ".join(
        f'<span class="badge status-{html.escape(str(k))}">'
        f'{html.escape(str(k))}: {v}</span>'
        for k, v in sorted(by_status.items(), key=lambda x: -x[1])
    )

    # ── Family breakdown ──
    by_family = stats.get("by_family", {})
    family_items = " ".join(
        f'<span class="badge family-badge">'
        f'{family_icons.get(k, "📐")} {html.escape(str(k))}: {v}</span>'
        for k, v in sorted(by_family.items(), key=lambda x: -x[1])
    )

    # v4.2: Count all closed-form identifications (Bessel + enhanced + literature)
    closed_form_count = sum(
        1 for d in (verified_known + novel_unproven + novel_proven)
        if (d.get('metadata', {}).get('bessel_identification', {}).get('identified')
            or d.get('metadata', {}).get('closed_form_identified')
            or 'Closed form' in str(d.get('metadata', {}).get('literature_match', '')))
    )
    conv_clean_novel = sum(
        1 for d in novel_unproven
        if not d.get('metadata', {}).get('convergence_warning')
    )

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ramanujan Agent v4.6 — CAS-Verified Theorem Machine</title>
<style>
{_get_css()}
</style>
</head>
<body>
<div class="report">

<!-- ═══ HEADER ═══ -->
<header class="report-header">
    <div class="header-bg"></div>
    <h1>
        <span class="pi-symbol">π</span>
        Ramanujan Agent v4.6
        <span class="subtitle">CAS-Verified Theorem Machine — Bessel K Ratio · Proof Pipeline 2× · Linear-b Priority Boost</span>
    </h1>
    <p class="header-meta">
        Generated {time.strftime('%Y-%m-%d %H:%M:%S')} ·
        {total_time:.1f}s runtime ·
        {stats.get('total', 0)} discoveries
    </p>
</header>

<!-- ═══ EXECUTIVE SUMMARY ═══ -->
<section class="section" id="summary">
    <h2>📊 Executive Summary</h2>
    <div class="stat-grid stat-grid-wide">
        <div class="stat-card hero">
            <div class="stat-value">{stats.get('total', 0)}</div>
            <div class="stat-label">Total Discoveries</div>
        </div>
        <div class="stat-card accent">
            <div class="stat-value">{stats.get('novel_proven_count', 0)}</div>
            <div class="stat-label">Novel Proven</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats.get('novel_unproven_count', 0)}</div>
            <div class="stat-label">Novel Unproven</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats.get('verified_known_count', 0)}</div>
            <div class="stat-label">Verified Known</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats.get('max_confidence', 0):.4f}</div>
            <div class="stat-label">Max Confidence</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(breakthroughs)}</div>
            <div class="stat-label">Breakthroughs</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{total_time:.1f}s</div>
            <div class="stat-label">Total Time</div>
        </div>
    </div>
    <div class="stat-grid" style="margin-top:10px">
        <div class="stat-card">
            <div class="stat-value">200</div>
            <div class="stat-label">PSLQ Max Digits</div>
        </div>
        <div class="stat-card accent">
            <div class="stat-value">{closed_form_count}</div>
            <div class="stat-label">Closed Forms Found</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{conv_clean_novel}</div>
            <div class="stat-label">Convergence-Clean Novel</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(falsification_appendix)}</div>
            <div class="stat-label">Falsified</div>
        </div>
    </div>
    <div class="breakdown-row">
        <div class="breakdown-block">
            <strong>Status:</strong> {status_items}
        </div>
        <div class="breakdown-block">
            <strong>Families:</strong> {family_items}
        </div>
    </div>
</section>

<!-- ═══ BREAKTHROUGHS ═══ -->
<section class="section" id="breakthroughs">
    <h2>🏆 Breakthroughs</h2>
    {'<div class="discovery-list">' + breakthrough_cards + '</div>' if breakthrough_cards else '<p class="muted">No breakthroughs yet — the agent is still exploring.</p>'}
</section>

<!-- ═══ PROVEN IDENTITIES ═══ -->
<section class="section" id="proven">
    <h2>✅ Novel Proven Identities</h2>
    {'<div class="discovery-list">' + proven_cards + '</div>' if proven_cards else '<p class="muted">No novel proofs generated yet.</p>'}
</section>

<!-- ═══ VERIFIED KNOWN ═══ -->
<section class="section" id="known">
    <h2>📚 Verified Known Results (Rediscoveries)</h2>
    <p class="muted">Known CFs rediscovered by the agent (confirms search covers established territory).</p>
    {'<div class="table-scroll"><table class="data-table"><thead><tr><th>Expression</th><th>Value</th><th>Target</th><th>Error</th><th>Literature</th></tr></thead><tbody>' + known_table_rows + '</tbody></table></div>' if known_table_rows else '<p class="muted">No known results rediscovered.</p>'}
</section>

<!-- ═══ NOVEL UNPROVEN ═══ -->
<section class="section" id="novel-unproven">
    <h2>💡 Novel Unproven Conjectures</h2>
    {cluster_html}
    {'<div class="discovery-list">' + novel_cards + '</div>' if novel_cards else '<p class="muted">No novel unproven conjectures yet.</p>'}
</section>

<!-- ═══ CANDIDATE ANALYSIS TABLE (v3.3) ═══ -->
<section class="section" id="candidate-table">
    <h2>🔬 Candidate Analysis Table</h2>
    <p class="muted">Prioritized analysis of all novel CF candidates. Tier 1 = ISC/Bessel priority (linear-b CFs).
       Tier 2 = flagged convergence issues. Tier 3 = genuinely novel.<br>
       <strong>Analysis time: {analysis_time:.1f}s</strong></p>
    {'<div class="table-scroll"><table class="data-table candidate-tbl"><thead><tr><th>Tier</th><th>Expression</th><th>Value (20 digits)</th><th>ISC</th><th>Algebraic</th><th>Bessel/HG</th><th>Conv.</th><th>Final Status</th></tr></thead><tbody>' + candidate_rows + '</tbody></table></div>' if candidate_rows else '<p class="muted">No candidates to analyze.</p>'}
</section>

<!-- ═══ PROOF TARGETS ═══ -->
<section class="section" id="proof-targets">
    <h2>🎯 Proof Targets</h2>
    <p class="muted">Structured proof plans for top novel candidates. Each target includes mathematical framework, proof strategy, and key lemmas needed.</p>
    {_render_proof_targets(proof_targets)}
</section>

<!-- ═══ PROOF ENGINE RESULTS (v3.4) ═══ -->
<section class="section" id="proof-engine">
    <h2>⚙️ Proof Engine Results</h2>
    <p class="muted">Automated CAS proof attempts using named CF convergence theorems
       (Wall, Śleszyński-Pringsheim, Worpitzky, Gauss-Euler, Van Vleck, Lorentzen-Waadeland)
       + special function identification + SymPy verification.
       <strong>Proof time: {proof_time:.1f}s</strong></p>
    {_render_proof_engine(proof_scaffolds)}
</section>

<!-- ═══ THEOREM TEMPLATES (v4) ═══ -->
<section class="section" id="theorem-templates">
    <h2>📐 Theorem Templates</h2>
    <p class="muted">Parametric theorem families induced from discovered instances.
       Each template covers multiple CFs with a single proven or conjectured identity.</p>
    {_render_theorem_templates(template_cards_data)}
</section>

<!-- ═══ RIGOR LADDER (v4) ═══ -->
<section class="section" id="rigor-ladder">
    <h2>🪜 Rigor Ladder</h2>
    <p class="muted">Classification of all novel candidates by proof completeness level.
       Level 3 = theorem (CAS-verified). Level 2 = conditional (convergence proven).
       Level 1 = structural (function identified). Level 0 = numeric only.</p>
    {_render_rigor_ladder(rigor_ladder)}
</section>

<!-- ═══ META-CRITIC (v4) ═══ -->
<section class="section" id="meta-critic">
    <h2>🧐 Meta-Critic Scoring</h2>
    <p class="muted">Theorem-value scoring: proven theorems score highest (+10),
       structural matches (+3), isolated constants (+0.1).
       Low-value candidates are deprioritized.</p>
    {_render_meta_critic(meta_critic)}
</section>

<!-- ═══ FAMILY DETAILS ═══ -->
<section class="section" id="families">
    <h2>🔬 Discovery by Family</h2>
    {''.join(family_sections)}
</section>

<!-- ═══ TOP DISCOVERIES ═══ -->
<section class="section" id="top">
    <h2>📋 All Top Discoveries</h2>
    <div class="discovery-list">{top_cards}</div>
</section>

<!-- ═══ FALSIFICATION APPENDIX ═══ -->
<section class="section" id="falsified">
    <h2>❌ Falsification Appendix</h2>
    <p class="muted">Candidates falsified by adversarial testing. Listed with the specific test that caused falsification.</p>
    {'<table class="data-table"><thead><tr><th>Family</th><th>Expression</th><th>Reason</th></tr></thead><tbody>' + falsified_rows + '</tbody></table>' if falsified_rows else '<p class="muted">No falsified candidates.</p>'}
</section>

<!-- ═══ AGENT PERFORMANCE ═══ -->
<section class="section" id="agents">
    <h2>🤖 Agent Performance</h2>
    <table class="data-table">
        <thead>
            <tr>
                <th>Agent ID</th>
                <th>Type</th>
                <th>Rounds</th>
                <th>Discoveries</th>
                <th>Time</th>
            </tr>
        </thead>
        <tbody>
            {agent_rows}
        </tbody>
    </table>
</section>

<!-- ═══ PROGRESS CHART ═══ -->
<section class="section" id="progress">
    <h2>📈 Discovery Progress</h2>
    <div class="chart-container">
        <canvas id="progressChart" width="800" height="300"></canvas>
    </div>
</section>

<!-- ═══ METHODOLOGY ═══ -->
<section class="section" id="methodology">
    <h2>📖 Methodology</h2>
    <div class="methodology-grid">
        <div class="method-card">
            <h3>🔍 Exploration</h3>
            <p>Multi-strategy conjecture generation: parameterised pi-series sweeps,
               generalised continued fraction search, q-series identity hunting,
               PSLQ integer relation discovery, partition congruence search,
               and Ramanujan tau function pattern analysis.</p>
        </div>
        <div class="method-card">
            <h3>🔬 Validation</h3>
            <p>Three-tier precision escalation (50→200→500 digits),
               symbolic simplification via SymPy, PSLQ cross-verification,
               convergence rate analysis, CF fixed-point proof engine,
               and algebraic number detection via minimal polynomials (v3.1).</p>
        </div>
        <div class="method-card">
            <h3>⚔️ Adversarial Testing</h3>
            <p>Parameter sensitivity analysis, extreme-precision checks,
               edge-case evaluation, and triviality detection.</p>
        </div>
        <div class="method-card">
            <h3>🔄 Self-Iteration</h3>
            <p>Successful parameter regions feed back into exploration.
               Meta-learner adjusts strategy based on discovery rates
               and validation success.</p>
        </div>
    </div>
</section>

</div><!-- /.report -->

<script>
{_get_js(progress_json)}
</script>

</body>
</html>"""

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report_html, encoding="utf-8")

    return report_html


# ═══════════════════════════════════════════════════════════════
#  Helper renderers
# ═══════════════════════════════════════════════════════════════


def _render_proof_targets(targets: list) -> str:
    """Render proof target cards."""
    if not targets:
        return '<p class="muted">No proof targets generated (no novel_unproven candidates with sufficient confidence).</p>'
    cards = []
    for i, t in enumerate(targets, 1):
        expr = html.escape(str(t.get("expression", ""))[:200])
        family = html.escape(str(t.get("family", "")))
        val = t.get("value", "")
        prec = t.get("precision_verified", 0)
        strategy = html.escape(str(t.get("proof_strategy", "")))
        framework = html.escape(str(t.get("framework", "")))
        lemmas = t.get("key_lemmas", [])
        lemma_html = "".join(f"<li>{html.escape(str(l))}</li>" for l in lemmas)

        cards.append(f"""
        <div class="proof-target-card">
            <div class="proof-target-header">
                <span class="proof-target-num">#{i}</span>
                <span class="badge family-badge">{family}</span>
                <span class="proof-target-prec">Verified to {prec} digits</span>
            </div>
            <div class="proof-target-expr"><code>{expr}</code></div>
            <div class="proof-target-body">
                <p><strong>Framework:</strong> {framework}</p>
                <p><strong>Strategy:</strong> {strategy}</p>
                <p><strong>Key lemmas:</strong></p>
                <ol class="proof-lemmas">{lemma_html}</ol>
            </div>
        </div>""")
    return '<div class="proof-targets-list">' + "\n".join(cards) + "</div>"


def _render_proof_engine(scaffolds: list) -> str:
    """Render proof engine result cards (v3.4)."""
    if not scaffolds:
        return '<p class="muted">No proof engine results (no novel_unproven CF candidates in proof queue).</p>'

    # Summary stats
    formal = sum(1 for s in scaffolds if s.get("status") == "formal_proof")
    partial = sum(1 for s in scaffolds if s.get("status") == "partial_proof")
    numeric = sum(1 for s in scaffolds if s.get("status") == "numeric_only")
    summary = (
        f'<div class="proof-summary">'
        f'<span class="badge proof-formal">✓ Formal: {formal}</span> '
        f'<span class="badge proof-partial">△ Partial: {partial}</span> '
        f'<span class="badge proof-numeric">○ Numeric only: {numeric}</span> '
        f'<span class="muted">({len(scaffolds)} candidates in proof queue)</span>'
        f'</div>'
    )

    cards = []
    for i, s in enumerate(scaffolds, 1):
        expr = html.escape(str(s.get("expression", ""))[:120])
        status = s.get("status", "?")
        conf = s.get("confidence", 0)
        thm = html.escape(str(s.get("convergence_theorem") or "None"))
        cf = s.get("closed_form", {})
        cf_type = html.escape(str(cf.get("type") or "—"))
        cf_expr = html.escape(str(cf.get("expression") or "—")[:80])
        gaps = s.get("gaps", [])
        reasons = s.get("reasons", [])
        scaffold_text = html.escape(str(s.get("scaffold", "")))
        score = s.get("score", 0)

        status_class = {"formal_proof": "proof-formal",
                        "partial_proof": "proof-partial",
                        "numeric_only": "proof-numeric"}.get(status, "")
        status_sym = {"formal_proof": "✓", "partial_proof": "△",
                      "numeric_only": "○"}.get(status, "?")

        gap_html = ""
        if gaps:
            gap_items = "".join(f"<li>{html.escape(g)}</li>" for g in gaps)
            gap_html = f'<div class="proof-gaps"><strong>Gaps:</strong><ul>{gap_items}</ul></div>'

        reason_html = ""
        if reasons:
            reason_items = "".join(f"<li>{html.escape(r)}</li>" for r in reasons[:5])
            reason_html = f'<div class="proof-reasons"><strong>Queue score {score:.1f}:</strong><ul>{reason_items}</ul></div>'

        cards.append(f"""
        <div class="proof-engine-card {status_class}">
            <div class="proof-engine-header">
                <span class="proof-status-badge {status_class}">{status_sym} {html.escape(status)}</span>
                <span class="proof-conf">{conf:.0%}</span>
                <code style="font-size:0.8rem;margin-left:8px">{expr}</code>
            </div>
            <details class="proof-scaffold-details">
                <summary>Convergence: {thm} · Closed form: {cf_type} — <code>{cf_expr}</code></summary>
                <div class="proof-engine-body">
                {gap_html}
                {reason_html}
                <pre class="proof-scaffold-pre">{scaffold_text}</pre>
                </div>
            </details>
        </div>""")

    return summary + '<div class="proof-engine-list">' + "\n".join(cards) + "</div>"


# ═══════════════════════════════════════════════════════════════
#  v4 renderers: Theorem Templates, Rigor Ladder, Meta-Critic
# ═══════════════════════════════════════════════════════════════

def _render_theorem_templates(template_cards: list) -> str:
    """Render theorem template cards (v4)."""
    if not template_cards:
        return '<p class="muted">No theorem templates induced (need ≥2 instances per structural cluster).</p>'

    proven = sum(1 for t in template_cards if t.get("status_badge") == "PROVEN")
    validated = sum(1 for t in template_cards if t.get("status_badge") == "VALIDATED")
    summary = (
        f'<div class="proof-summary">'
        f'<span class="badge proof-formal">PROVEN: {proven}</span> '
        f'<span class="badge proof-partial">VALIDATED: {validated}</span> '
        f'<span class="muted">({len(template_cards)} templates total)</span>'
        f'</div>'
    )

    cards = []
    for t in template_cards:
        status = t.get("status_badge", "?")
        ttype = html.escape(str(t.get("type", "")))
        statement = html.escape(str(t.get("statement", "")))
        mechanism = html.escape(str(t.get("mechanism", "")))
        literature = html.escape(str(t.get("literature", "")))
        sketch = html.escape(str(t.get("proof_sketch", "")))
        inst_count = t.get("instance_count", 0)
        ver_count = t.get("verified_count", 0)
        conf = t.get("confidence", 0)

        status_class = "proof-formal" if status == "PROVEN" else ("proof-partial" if status == "VALIDATED" else "proof-numeric")
        cards.append(f"""
        <div class="proof-engine-card {status_class}">
            <div class="proof-engine-header">
                <span class="proof-status-badge {status_class}">{status}</span>
                <span class="badge family-badge">{ttype}</span>
                <span class="proof-conf">{inst_count} instances ({ver_count} verified) · Conf: {conf:.0%}</span>
            </div>
            <div class="template-statement"><strong>Statement:</strong> {statement}</div>
            <div class="proof-engine-body">
                <p><strong>Mechanism:</strong> {mechanism}</p>
                <p><strong>Literature:</strong> {literature}</p>
                <details class="proof-scaffold-details">
                    <summary>Proof sketch</summary>
                    <pre class="proof-scaffold-pre">{sketch}</pre>
                </details>
            </div>
        </div>""")

    return summary + '<div class="proof-engine-list">' + "\n".join(cards) + "</div>"


def _render_rigor_ladder(rigor_data: dict) -> str:
    """Render rigor ladder visualization (v4)."""
    if not rigor_data:
        return '<p class="muted">No rigor assessment data available.</p>'

    by_level = rigor_data.get("by_level", {})
    by_tag = rigor_data.get("by_tag", {})
    assessments = rigor_data.get("assessments", [])
    promotable = rigor_data.get("promotable", [])
    total = sum(by_level.values()) or 1

    # Bar chart
    levels = [
        (3, "Level 3 — Full Proof", "theorem", "#00e676"),
        (2, "Level 2 — Reduction", "theorem_conditional", "#ffd740"),
        (1, "Level 1 — Structural", "conjecture", "#42a5f5"),
        (0, "Level 0 — Numeric", "conjecture", "#78909c"),
    ]
    bars = ""
    for lv, label, tag, color in levels:
        count = by_level.get(lv, 0)
        pct = count / total * 100
        bars += (
            f'<div class="ladder-row">'
            f'<span class="ladder-label">{label}</span>'
            f'<div class="ladder-bar-outer">'
            f'<div class="ladder-bar" style="width:{pct:.1f}%;background:{color}"></div>'
            f'</div>'
            f'<span class="ladder-count">{count}</span>'
            f'</div>'
        )

    tag_html = " · ".join(
        f'<span class="badge">{tag}: {count}</span>'
        for tag, count in by_tag.items() if count > 0
    )

    details = ""
    if assessments:
        rows = ""
        for a in assessments[:30]:
            disc_id = html.escape(str(a.get("disc_id", ""))[:12])
            level = a.get("level", 0)
            tag = html.escape(str(a.get("tag", "")))
            evidence = "; ".join(a.get("evidence", [])[:2])
            gaps = "; ".join(a.get("gaps", [])[:2])
            rows += (
                f'<tr><td><code>{disc_id}</code></td>'
                f'<td>L{level}</td><td>{html.escape(tag)}</td>'
                f'<td>{html.escape(evidence)[:80]}</td>'
                f'<td>{html.escape(gaps)[:80]}</td></tr>'
            )
        details = (
            f'<details class="proof-scaffold-details"><summary>Detailed assessments ({len(assessments)})</summary>'
            f'<table class="data-table"><thead><tr>'
            f'<th>ID</th><th>Level</th><th>Tag</th><th>Evidence</th><th>Gaps</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></details>'
        )

    return f"""
    <div class="ladder-chart">{bars}</div>
    <div class="proof-summary" style="margin-top:12px">
        {tag_html}
        <span class="muted"> · {len(promotable)} promotable candidates</span>
    </div>
    {details}
    """


def _render_meta_critic(critic_data: dict) -> str:
    """Render meta-critic scoring results (v4)."""
    if not critic_data:
        return '<p class="muted">No meta-critic data available.</p>'

    kept = critic_data.get("kept", [])
    depri = critic_data.get("deprioritized", [])
    suppressed = critic_data.get("suppressed", [])
    total_value = critic_data.get("total_theorem_value", 0)
    scores = critic_data.get("scores", [])

    summary = (
        f'<div class="proof-summary">'
        f'<span class="badge proof-formal">Kept: {len(kept)}</span> '
        f'<span class="badge proof-partial">Deprioritized: {len(depri)}</span> '
        f'<span class="badge proof-numeric">Suppressed: {len(suppressed)}</span> '
        f'<span class="muted">Total theorem value: {total_value:.1f}</span>'
        f'</div>'
    )

    if not scores:
        return summary

    rows = ""
    for s in scores[:30]:
        disc_id = html.escape(str(s.get("disc_id", ""))[:12])
        raw = s.get("raw_score", 0)
        final = s.get("final_score", 0)
        verdict = s.get("verdict", "")
        reason = html.escape(str(s.get("reason", ""))[:60])
        bonuses = ", ".join(f"+{v:.1f} ({n})" for n, v in s.get("bonuses", []))
        penalties = ", ".join(f"{v:.1f} ({n})" for n, v in s.get("penalties", []))
        verdict_class = {"keep": "proof-formal", "deprioritize": "proof-partial",
                         "suppress": "proof-numeric"}.get(verdict, "")
        rows += (
            f'<tr><td><code>{disc_id}</code></td>'
            f'<td>{raw:.1f}</td><td>{final:.1f}</td>'
            f'<td><span class="badge {verdict_class}">{html.escape(verdict)}</span></td>'
            f'<td>{html.escape(bonuses)[:60]}</td>'
            f'<td>{html.escape(penalties)[:60]}</td>'
            f'<td>{reason}</td></tr>'
        )

    table = (
        f'<details class="proof-scaffold-details"><summary>Score details ({len(scores)} candidates)</summary>'
        f'<div class="table-scroll"><table class="data-table"><thead><tr>'
        f'<th>ID</th><th>Raw</th><th>Final</th><th>Verdict</th>'
        f'<th>Bonuses</th><th>Penalties</th><th>Reason</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div></details>'
    )

    return summary + table


def _discovery_card(d: dict) -> str:
    """Render a single discovery card."""
    family = html.escape(str(d.get("family", "")))
    category = html.escape(str(d.get("category", "")))
    expression = html.escape(str(d.get("expression", ""))[:200])
    confidence = d.get("confidence", 0)
    error = d.get("error", float("inf"))
    status = d.get("status", "proposed")
    disc_id = html.escape(str(d.get("id", ""))[:12])
    target = html.escape(str(d.get("target", "") or ""))
    params = d.get("params", {})
    metadata = d.get("metadata", {})
    generation = d.get("generation", 0)

    conf_class = ("conf-high" if confidence > 0.7
                  else "conf-med" if confidence > 0.3
                  else "conf-low")
    status_class = f"status-{status}"

    # Error display
    if error == float("inf") or error > 1e10:
        err_display = "∞"
    elif error == 0:
        err_display = "0 (exact)"
    elif error < 1e-50:
        err_display = f"{error:.2e}"
    else:
        err_display = f"{error:.6e}"

    # Proof sketch
    proof = metadata.get("proof_sketch", "")
    proof_html = (f'<div class="proof-sketch"><strong>Proof sketch:</strong> '
                  f'{html.escape(str(proof))}</div>' if proof else "")

    # v2: Literature match / novelty badge
    lit_match = metadata.get("literature_match") or d.get("literature_match")
    is_novel = metadata.get("is_novel", None)
    novelty_html = ""
    if lit_match:
        novelty_html = (f'<div class="lit-match"><strong>Literature:</strong> '
                        f'{html.escape(str(lit_match))}</div>')
    elif is_novel is True:
        novelty_html = '<div class="novelty-badge novel">Potentially novel</div>'
    elif is_novel is False:
        novelty_html = '<div class="novelty-badge known">Known result</div>'

    # v2: Provenance
    provenance = d.get("provenance", {})
    prov_html = ""
    if provenance:
        prov_items = ", ".join(f"{k}={v}" for k, v in list(provenance.items())[:4])
        prov_html = f'<div class="provenance">Provenance: {html.escape(prov_items)}</div>'

    # v3: PSLQ stability table
    stab_table = metadata.get("stability_table", [])
    stab_html = ""
    if stab_table and len(stab_table) > 1:
        rows = ""
        for row in stab_table:
            prec_val = row.get("precision", "?")
            rel = row.get("relation", "—")
            res = row.get("residual")
            found = row.get("found", False)
            matches = row.get("matches_original", None)
            res_str = f"{res:.2e}" if res is not None else "—"
            status_sym = "✓" if (found and matches is not False) else "✗" if found is False else "?"
            rows += (f"<tr><td>{prec_val}</td><td>{status_sym}</td>"
                     f"<td>{res_str}</td>"
                     f"<td style='font-size:0.75rem'>{str(rel)[:60]}</td></tr>")
        stab_html = (
            '<div class="stability-table">'
            '<strong>PSLQ Stability Table:</strong>'
            '<table class="mini-table"><thead><tr>'
            '<th>Precision</th><th>Status</th><th>Residual</th><th>Relation</th>'
            '</tr></thead><tbody>' + rows + '</tbody></table></div>'
        )

    # v3: Known-transform badge
    known_tf_html = ""
    if metadata.get("is_known_transform"):
        const = html.escape(str(metadata.get("matched_constant", "")))
        known_tf_html = (
            f'<div class="novelty-badge known">Known constant transform: {const}</div>'
        )

    # v3.2: High-precision numeric value
    value_html = ""
    val_20 = metadata.get("value_20_digits") or metadata.get("value_hi_prec")
    if val_20:
        value_html = (
            f'<div class="hi-prec-value">'
            f'<strong>Value:</strong> <code>{html.escape(str(val_20))}</code>'
            f'</div>'
        )
    elif d.get("value") is not None and d.get("value") != 0:
        value_html = (
            f'<div class="hi-prec-value">'
            f'<strong>Value:</strong> <code>{d["value"]:.15f}</code>'
            f'</div>'
        )

    # v3.2: Algebraic analysis
    alg_html = ""
    alg_analysis = metadata.get("algebraic_analysis")
    if alg_analysis:
        exact = metadata.get("exact_form", "")
        exact_str = f" → {html.escape(str(exact))}" if exact else ""
        alg_html = (
            f'<div class="analysis-note">'
            f'<strong>Algebraic analysis:</strong> '
            f'{html.escape(str(alg_analysis))}{exact_str}'
            f'</div>'
        )

    # v3.2: PSLQ constant recognition
    pslq_html = ""
    pslq_rec = metadata.get("pslq_recognition", {})
    if pslq_rec.get("found") is True:
        pexpr = html.escape(str(pslq_rec.get("expression", ""))[:120])
        pres = pslq_rec.get("residual", "?")
        pres_str = f"{pres:.2e}" if isinstance(pres, float) else str(pres)
        pslq_html = (
            f'<div class="pslq-match">'
            f'<strong>PSLQ match:</strong> <code>{pexpr}</code> '
            f'(residual: {pres_str})'
            f'</div>'
        )
    elif pslq_rec.get("found") is False:
        pslq_html = (
            '<div class="pslq-no-match">'
            '<strong>PSLQ:</strong> No integer relation found against 15-constant basis'
            '</div>'
        )

    # v3.3: Bessel / Hypergeometric identification
    bessel_html = ""
    bessel_data = metadata.get("bessel_identification", {})
    if bessel_data.get("identified"):
        best_b = bessel_data.get("best_identification", {})
        b_formula = html.escape(str(best_b.get("formula", best_b.get("type", "")))[:120])
        b_match = best_b.get("match_digits", 0)
        b_val = html.escape(str(best_b.get("computed_value", ""))[:25])
        bessel_html = (
            f'<div class="bessel-match">'
            f'<strong>Bessel/HG:</strong> <code>{b_formula}</code>'
            f'<br><small>Computed: {b_val} ({b_match} digits match)</small>'
            f'</div>'
        )
    elif bessel_data.get("candidates"):
        # Partial matches
        cands = bessel_data["candidates"][:2]
        items = ", ".join(html.escape(str(c.get("type", ""))[:30]) for c in cands)
        bessel_html = (
            f'<div class="bessel-partial">'
            f'<strong>Bessel/HG:</strong> Partial matches: {items}'
            f'</div>'
        )

    # v3.3: ISC (mpmath.identify) result
    isc_html = ""
    isc_data = metadata.get("isc_result", {})
    if isc_data.get("found"):
        ids = isc_data.get("identifications", [])
        id_items = "<br>".join(f"<code>{html.escape(str(i)[:80])}</code>" for i in ids[:3])
        isc_html = (
            f'<div class="isc-match">'
            f'<strong>ISC lookup:</strong> {id_items}'
            f'</div>'
        )
    elif isc_data.get("found") is False:
        isc_html = (
            '<div class="isc-no-match">'
            '<strong>ISC:</strong> No closed form found'
            '</div>'
        )

    # v3.3: Algebraic degree bound
    alg_deg_html = ""
    alg_deg = metadata.get("algebraic_degree", {})
    if alg_deg.get("is_algebraic"):
        deg = alg_deg.get("degree_bound", "?")
        poly = html.escape(str(alg_deg.get("minimal_polynomial", ""))[:80])
        alg_deg_html = (
            f'<div class="alg-degree-match">'
            f'<strong>Algebraic:</strong> degree ≤ {deg} — <code>{poly}</code>'
            f'</div>'
        )
    elif alg_deg.get("polynomials"):
        alg_deg_html = (
            '<div class="alg-degree-no-match">'
            '<strong>Algebraic degree:</strong> Not algebraic up to degree 6'
            '</div>'
        )

    # v3.3: Convergence diagnostics
    conv_html = ""
    conv_data = metadata.get("convergence_check", {})
    if conv_data.get("flags"):
        flag_items = "<br>".join(html.escape(str(f)[:100]) for f in conv_data["flags"][:3])
        conv_class = "conv-ok" if conv_data.get("converges", True) else "conv-warn"
        conv_html = (
            f'<div class="convergence-note {conv_class}">'
            f'<strong>Convergence:</strong> {flag_items}'
            f'</div>'
        )

    # v4.1: Convergence warning badge
    conv_warning_html = ""
    if metadata.get("convergence_warning"):
        tier = metadata.get("convergence_tier", "unknown")
        conv_warning_html = (
            f'<div class="novelty-badge" style="background:#ff5252;color:#fff">'
            f'⚠ Convergence: {html.escape(tier)} — value may be unreliable'
            f'</div>'
        )

    # v4.1: Enhanced closed-form identification
    ecf_html = ""
    ecf_data = metadata.get("enhanced_closed_form", {})
    if ecf_data.get("found"):
        best_cf = ecf_data.get("best_match", {})
        cf_formula = html.escape(str(best_cf.get("formula", ""))[:120])
        cf_digits = best_cf.get("match_digits", 0)
        cf_type = html.escape(str(best_cf.get("type", "")))
        ecf_html = (
            f'<div class="bessel-match">'
            f'<strong>Closed form ({cf_type}):</strong> <code>{cf_formula}</code>'
            f'<br><small>{cf_digits} digits match</small>'
            f'</div>'
        )

    # v3.2: PSLQ stability table (from post-analysis)
    pslq_stab = metadata.get("pslq_stability_table", [])
    if not pslq_stab:
        # Fall back to generator-time stability table
        pslq_stab = stab_table

    stab_html = ""
    if pslq_stab and len(pslq_stab) > 1:
        rows = ""
        for row in pslq_stab:
            prec_val = row.get("precision", "?")
            rel = row.get("relation", "—")
            res = row.get("residual")
            found = row.get("found", False)
            matches = row.get("matches_reference", row.get("matches_original", None))
            res_str = f"{res:.2e}" if isinstance(res, (int, float)) and res is not None else "—"
            status_sym = "✓" if (found and matches is not False) else "✗" if found is False else "?"
            max_c = row.get("max_coeff", "")
            max_c_str = f" (|c|≤{max_c})" if max_c else ""
            rows += (f"<tr><td>{prec_val}</td><td>{status_sym}</td>"
                     f"<td>{res_str}</td>"
                     f"<td style='font-size:0.75rem'>{str(rel)[:60]}{max_c_str}</td></tr>")
        stab_html = (
            '<div class="stability-table">'
            '<strong>PSLQ Stability Table:</strong>'
            '<table class="mini-table"><thead><tr>'
            '<th>Precision</th><th>Status</th><th>Residual</th><th>Relation</th>'
            '</tr></thead><tbody>' + rows + '</tbody></table></div>'
        )

    # Params preview
    param_items = []
    for k, v in list(params.items())[:6]:
        if k.startswith("_"):
            continue
        param_items.append(f"<span class='param'>{html.escape(str(k))}="
                           f"{html.escape(str(v)[:30])}</span>")
    params_html = " ".join(param_items) if param_items else ""

    return f"""<div class="discovery-card {status_class}">
        <div class="card-header">
            <span class="disc-id">{disc_id}</span>
            <span class="badge cat-{category}">{category}</span>
            <span class="badge family-badge">{family}</span>
            {'<span class="badge target-badge">→ ' + target + '</span>' if target else ''}
            <span class="badge {status_class}">{status}</span>
            <span class="gen-label">gen {generation}</span>
        </div>
        <div class="expression">{expression}</div>
        {value_html}
        {f'<div class="params-row">{params_html}</div>' if params_html else ''}
        <div class="metrics-row">
            <span class="metric">confidence: <strong>{confidence:.4f}</strong></span>
            <span class="metric">error: <strong>{err_display}</strong></span>
        </div>
        {proof_html}
        {alg_html}
        {pslq_html}
        {bessel_html}
        {isc_html}
        {ecf_html}
        {alg_deg_html}
        {conv_html}
        {conv_warning_html}
        {novelty_html}
        {known_tf_html}
        {stab_html}
        {prov_html}
        <div class="confidence-bar">
            <div class="confidence-fill {conf_class}" style="width: {confidence*100:.0f}%"></div>
        </div>
    </div>"""


def _get_css() -> str:
    return """
:root {
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #21262d;
    --surface3: #30363d;
    --border: #30363d;
    --text: #e6edf3;
    --text2: #8b949e;
    --accent: #58a6ff;
    --accent2: #79c0ff;
    --success: #3fb950;
    --warning: #d29922;
    --danger: #f85149;
    --purple: #bc8cff;
    --pink: #f778ba;
    --teal: #39d5c9;
    --gold: #f0c000;
    --orange: #f0883e;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
}
.report {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

/* ── Header ── */
.report-header {
    position: relative;
    text-align: center;
    padding: 3rem 2rem 2rem;
    margin-bottom: 2rem;
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #1a1e2e 100%);
    border-radius: 16px;
    border: 1px solid var(--border);
    overflow: hidden;
}
.header-bg {
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(circle at 30% 40%, rgba(88,166,255,0.08) 0%, transparent 50%),
                radial-gradient(circle at 70% 60%, rgba(188,140,255,0.06) 0%, transparent 50%);
}
.report-header h1 {
    position: relative;
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--purple), var(--pink));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.pi-symbol {
    font-size: 3rem;
    margin-right: 0.3em;
    opacity: 0.9;
}
.subtitle {
    display: block;
    font-size: 1rem;
    font-weight: 400;
    background: linear-gradient(90deg, var(--text2), var(--teal));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-top: 0.3rem;
}
.header-meta {
    position: relative;
    color: var(--text2);
    margin-top: 1rem;
    font-size: 0.9rem;
}

/* ── Sections ── */
.section {
    margin: 2rem 0;
    padding: 1.5rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
}
.section h2 {
    font-size: 1.4rem;
    margin-bottom: 1.2rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid var(--border);
    color: var(--accent2);
}

/* ── Stat Grid ── */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
}
.stat-grid-wide {
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}
.stat-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    text-align: center;
    transition: transform 0.2s, border-color 0.2s;
}
.stat-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent);
}
.stat-card.hero {
    border-color: var(--accent);
    background: linear-gradient(135deg, var(--surface2), rgba(88,166,255,0.08));
}
.stat-card.accent {
    border-color: var(--success);
}
.stat-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--text);
}
.stat-label {
    font-size: 0.8rem;
    color: var(--text2);
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Breakdown ── */
.breakdown-row {
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
    margin-top: 1rem;
}
.breakdown-block {
    flex: 1;
    min-width: 200px;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    padding: 0.15em 0.6em;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 0.15em;
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text2);
}
.status-proposed { color: var(--text2); }
.status-validated { color: var(--success); border-color: var(--success); }
.status-proven { color: var(--gold); border-color: var(--gold); background: rgba(240,192,0,0.08); }
.status-falsified { color: var(--danger); border-color: var(--danger); }
.cat-conjecture { color: var(--accent); }
.cat-validated { color: var(--success); }
.cat-proven { color: var(--gold); }
.cat-congruence { color: var(--purple); }
.cat-integer_relation { color: var(--teal); }
.cat-proof_sketch { color: var(--pink); }
.cat-pattern { color: var(--orange); }
.cat-transfer { color: var(--accent2); }
.family-badge { color: var(--purple); }
.target-badge { color: var(--teal); }
.gen-label { font-size: 0.7rem; color: var(--text2); margin-left: auto; }

/* ── Discovery Cards ── */
.discovery-list { margin: 1rem 0; }
.discovery-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    margin: 0.8rem 0;
    transition: border-color 0.2s;
}
.discovery-card:hover { border-color: var(--accent); }
.discovery-card.status-proven { border-left: 3px solid var(--gold); }
.discovery-card.status-validated { border-left: 3px solid var(--success); }
.card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.6rem;
}
.disc-id {
    font-family: 'Fira Code', monospace;
    font-size: 0.75rem;
    color: var(--text2);
    background: var(--surface3);
    padding: 0.1em 0.5em;
    border-radius: 4px;
}
.expression {
    font-family: 'Fira Code', 'Cascadia Code', monospace;
    font-size: 0.85rem;
    color: var(--text);
    background: var(--bg);
    padding: 0.8rem;
    border-radius: 6px;
    margin: 0.5rem 0;
    word-break: break-word;
    border: 1px solid var(--surface3);
}
.params-row {
    margin: 0.4rem 0;
}
.param {
    font-size: 0.75rem;
    color: var(--text2);
    background: var(--bg);
    padding: 0.1em 0.4em;
    border-radius: 3px;
    margin-right: 0.3rem;
    font-family: monospace;
}
.metrics-row {
    display: flex;
    gap: 1.5rem;
    margin: 0.5rem 0;
}
.metric {
    font-size: 0.8rem;
    color: var(--text2);
}
.metric strong {
    color: var(--text);
}
.proof-sketch {
    margin-top: 0.6rem;
    padding: 0.8rem;
    background: rgba(240,192,0,0.05);
    border: 1px solid rgba(240,192,0,0.2);
    border-radius: 6px;
    font-size: 0.85rem;
    color: var(--gold);
}
.lit-match {
    margin-top: 0.5rem;
    padding: 0.6rem 0.8rem;
    background: rgba(188,140,255,0.05);
    border: 1px solid rgba(188,140,255,0.2);
    border-radius: 6px;
    font-size: 0.82rem;
    color: var(--purple);
}
.novelty-badge {
    display: inline-block;
    margin-top: 0.5rem;
    padding: 0.2rem 0.7rem;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
}
.novelty-badge.novel { background: rgba(63,185,80,0.15); color: var(--success); }
.novelty-badge.known { background: rgba(139,148,158,0.15); color: var(--text2); }
.provenance {
    margin-top: 0.4rem;
    font-size: 0.75rem;
    color: var(--text2);
    font-style: italic;
}
.stability-table {
    margin-top: 0.6rem;
    padding: 0.5rem;
    background: var(--surface);
    border-radius: 6px;
    border: 1px solid var(--border);
}
.stability-table strong {
    font-size: 0.8rem;
    color: var(--accent);
}
.mini-table {
    width: 100%;
    margin-top: 0.3rem;
    border-collapse: collapse;
    font-size: 0.75rem;
}
.mini-table th {
    text-align: left;
    padding: 0.2rem 0.4rem;
    border-bottom: 1px solid var(--border);
    color: var(--text2);
}
.mini-table td {
    padding: 0.2rem 0.4rem;
    border-bottom: 1px solid var(--surface3);
}
.status-verified_known { background: rgba(188,140,255,0.15); color: var(--purple); }
.status-novel_unproven { background: rgba(247,120,186,0.15); color: var(--pink); }
.status-novel_proven { background: rgba(63,185,80,0.15); color: var(--success); }

/* ── v3.2 Analysis display ── */
.hi-prec-value {
    margin: 0.3rem 0;
    padding: 0.4rem 0.6rem;
    background: var(--surface3);
    border-radius: 6px;
    font-size: 0.85rem;
}
.hi-prec-value code {
    color: var(--gold);
    font-size: 0.9rem;
}
.analysis-note {
    margin: 0.3rem 0;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
    color: var(--text2);
    border-left: 2px solid var(--teal);
}
.pslq-match {
    margin: 0.3rem 0;
    padding: 0.3rem 0.6rem;
    background: rgba(240,192,0,0.08);
    border-radius: 4px;
    font-size: 0.8rem;
}
.pslq-match code { color: var(--warning); }
.pslq-no-match {
    margin: 0.3rem 0;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
    color: var(--success);
}

/* ── v3.3: Bessel/HG identification ── */
.bessel-match {
    margin: 0.3rem 0;
    padding: 0.4rem 0.6rem;
    background: rgba(136,57,239,0.12);
    border-left: 3px solid #8839ef;
    border-radius: 4px;
    font-size: 0.8rem;
}
.bessel-match code { color: #c6a0f6; }
.bessel-partial {
    margin: 0.3rem 0;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
    color: var(--text2);
}

/* ── v3.3: ISC lookup ── */
.isc-match {
    margin: 0.3rem 0;
    padding: 0.4rem 0.6rem;
    background: rgba(240,192,0,0.1);
    border-left: 3px solid #f0c000;
    border-radius: 4px;
    font-size: 0.8rem;
}
.isc-match code { color: #f0c000; }
.isc-no-match {
    margin: 0.3rem 0;
    padding: 0.3rem 0.6rem;
    font-size: 0.75rem;
    color: var(--text2);
}

/* ── v3.3: Algebraic degree ── */
.alg-degree-match {
    margin: 0.3rem 0;
    padding: 0.4rem 0.6rem;
    background: rgba(209,154,102,0.1);
    border-left: 3px solid #d19a66;
    border-radius: 4px;
    font-size: 0.8rem;
}
.alg-degree-match code { color: #d19a66; }
.alg-degree-no-match {
    margin: 0.3rem 0;
    padding: 0.3rem 0.6rem;
    font-size: 0.75rem;
    color: var(--text2);
}

/* ── v3.3: Convergence diagnostics ── */
.convergence-note {
    margin: 0.3rem 0;
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    font-size: 0.78rem;
}
.conv-ok { color: var(--success); background: rgba(63,185,80,0.06); }
.conv-warn { color: var(--warning); background: rgba(240,192,0,0.08); border-left: 3px solid var(--warning); }
.conv-flag { color: var(--warning); font-weight: 600; }

/* ── v3.3: Candidate table ── */
.table-scroll { overflow-x: auto; }
.candidate-tbl { font-size: 0.82rem; }
.candidate-tbl th { font-size: 0.78rem; white-space: nowrap; }
.candidate-tbl td { padding: 0.5rem 0.6rem; vertical-align: top; }
.candidate-tbl .mono { font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 0.78rem; color: var(--gold); }
.candidate-tbl .cf-expr { font-size: 0.75rem; }
.badge.tier-1 { background: rgba(136,57,239,0.2); color: #c6a0f6; }
.badge.tier-2 { background: rgba(240,192,0,0.2); color: #f0c000; }
.badge.tier-3 { background: rgba(63,185,80,0.2); color: var(--success); }
.cluster-info {
    margin: 0.5rem 0 1rem;
    padding: 0.5rem 0.8rem;
    background: var(--surface2);
    border-radius: 8px;
    font-size: 0.85rem;
}
.cluster-info ul {
    margin: 0.3rem 0 0 1.5rem;
    font-size: 0.8rem;
    color: var(--text2);
}

.confidence-bar {
    height: 3px;
    border-radius: 2px;
    background: var(--surface3);
    margin-top: 0.8rem;
}
.confidence-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s;
}
.conf-high { background: var(--success); }
.conf-med { background: var(--warning); }
.conf-low { background: var(--teal); }

/* ── Family Sections ── */
.family-section {
    margin: 1.5rem 0;
    padding: 1.2rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
}
.family-section h2 {
    border: none;
    padding: 0;
    margin-bottom: 1rem;
}
.family-icon {
    font-size: 1.6rem;
    margin-right: 0.3em;
}

/* ── Table ── */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}
.data-table th {
    text-align: left;
    padding: 0.8rem;
    background: var(--surface2);
    border-bottom: 2px solid var(--border);
    color: var(--accent2);
    font-weight: 600;
}
.data-table td {
    padding: 0.6rem 0.8rem;
    border-bottom: 1px solid var(--border);
}
.data-table tr:hover td {
    background: var(--surface2);
}
.agent-badge {
    padding: 0.2em 0.6em;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 600;
}
.agent-explorer { background: rgba(88,166,255,0.15); color: var(--accent); }
.agent-validator { background: rgba(63,185,80,0.15); color: var(--success); }
.agent-adversary { background: rgba(248,81,73,0.15); color: var(--danger); }
.agent-refiner { background: rgba(210,153,34,0.15); color: var(--warning); }
.agent-pollinator { background: rgba(188,140,255,0.15); color: var(--purple); }
.agent-meta_learner { background: rgba(247,120,186,0.15); color: var(--pink); }

/* ── Chart ── */
.chart-container {
    padding: 1rem;
    background: var(--bg);
    border-radius: 10px;
    border: 1px solid var(--border);
}

/* ── Methodology ── */
.methodology-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1rem;
}
.method-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
}
.method-card h3 {
    color: var(--accent);
    margin-bottom: 0.5rem;
    font-size: 1rem;
}
.method-card p {
    color: var(--text2);
    font-size: 0.85rem;
}

/* Proof targets */
.proof-targets-list { display: flex; flex-direction: column; gap: 1rem; }
.proof-target-card {
    background: var(--surface);
    border: 1px solid var(--accent);
    border-radius: 10px;
    padding: 1.2rem;
}
.proof-target-header {
    display: flex; gap: 10px; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap;
}
.proof-target-num {
    font-size: 1.2rem; font-weight: 700; color: var(--accent);
}
.proof-target-prec {
    font-size: 0.8rem; color: var(--success); margin-left: auto;
}
.proof-target-expr {
    background: var(--bg); padding: 8px 12px; border-radius: 6px;
    margin: 8px 0; overflow-x: auto;
}
.proof-target-expr code { font-size: 0.85rem; color: var(--text); }
.proof-target-body p { color: var(--text2); font-size: 0.88rem; margin: 4px 0; line-height: 1.6; }
.proof-target-body strong { color: var(--text); }
.proof-lemmas { color: var(--text2); font-size: 0.85rem; padding-left: 1.5rem; margin-top: 4px; }
.proof-lemmas li { margin: 3px 0; }

/* Proof engine (v3.4) */
.proof-summary { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 1rem; }
.proof-formal { background: var(--success); color: #000; }
.proof-partial { background: var(--warning); color: #000; }
.proof-numeric { background: var(--surface3); color: var(--text2); }
.badge.proof-formal, .badge.proof-partial, .badge.proof-numeric {
    padding: 4px 12px; border-radius: 8px; font-weight: 600; font-size: 0.85rem;
}
.proof-engine-list { display: flex; flex-direction: column; gap: 1rem; }
.proof-engine-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    border-left: 4px solid var(--border);
}
.proof-engine-card.proof-formal { border-left-color: var(--success); }
.proof-engine-card.proof-partial { border-left-color: var(--warning); }
.proof-engine-card.proof-numeric { border-left-color: var(--text2); }
.proof-engine-header {
    display: flex; gap: 10px; align-items: center; margin-bottom: 0.5rem;
}
.proof-status-badge {
    padding: 3px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;
}
.proof-status-badge.proof-formal { background: rgba(63,185,80,0.15); color: var(--success); }
.proof-status-badge.proof-partial { background: rgba(210,153,34,0.15); color: var(--warning); }
.proof-status-badge.proof-numeric { background: rgba(139,148,158,0.1); color: var(--text2); }
.proof-conf { font-size: 0.8rem; color: var(--text2); margin-left: auto; }
.proof-engine-body p { color: var(--text2); font-size: 0.88rem; margin: 4px 0; }
.proof-engine-body strong { color: var(--text); }
.proof-gaps, .proof-reasons { font-size: 0.85rem; margin-top: 6px; }
.proof-gaps ul, .proof-reasons ul { padding-left: 1.5rem; margin-top: 2px; }
.proof-gaps li { color: var(--danger); }
.proof-reasons li { color: var(--text2); }
.proof-scaffold-details { margin-top: 8px; }
.proof-scaffold-details summary {
    cursor: pointer; color: var(--accent); font-size: 0.85rem; font-weight: 600;
}
.proof-scaffold-pre {
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 12px; margin-top: 6px; font-size: 0.78rem; color: var(--text2);
    white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto;
}

/* v4: Rigor Ladder */
.ladder-chart { display: flex; flex-direction: column; gap: 8px; margin: 1rem 0; }
.ladder-row { display: flex; align-items: center; gap: 10px; }
.ladder-label { width: 180px; font-size: 0.85rem; color: var(--text); font-weight: 600; text-align: right; }
.ladder-bar-outer { flex: 1; background: var(--surface); border-radius: 6px; height: 28px; overflow: hidden; border: 1px solid var(--border); }
.ladder-bar { height: 100%; border-radius: 6px; transition: width 0.5s ease; min-width: 2px; }
.ladder-count { width: 40px; font-size: 0.85rem; color: var(--text2); font-weight: 700; }
.template-statement { font-size: 0.9rem; color: var(--text); margin: 8px 0; padding: 8px; background: var(--bg); border-radius: 6px; border-left: 3px solid var(--accent); }

.muted { color: var(--text2); font-style: italic; }

@media (max-width: 768px) {
    .report { padding: 1rem; }
    .stat-grid { grid-template-columns: repeat(2, 1fr); }
    .breakdown-row { flex-direction: column; }
}
"""


def _get_js(progress_json: str) -> str:
    return f"""
(function() {{
    // ── Progress Chart ──
    const data = {progress_json};
    const canvas = document.getElementById('progressChart');
    if (!canvas || !data.length) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const pad = {{ top: 30, right: 30, bottom: 40, left: 60 }};
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    // Extract series
    const rounds = data.map(d => d.round);
    const totals = data.map(d => d.total_discoveries || 0);
    const validated = data.map(d => d.validated || 0);
    const proven_ = data.map(d => d.proven || 0);
    const maxVal = Math.max(...totals, 1);

    function x(i) {{ return pad.left + (i / Math.max(rounds.length - 1, 1)) * plotW; }}
    function y(v) {{ return pad.top + plotH - (v / maxVal) * plotH; }}

    // Background
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = '#21262d';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {{
        const yy = pad.top + (i / 5) * plotH;
        ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(W - pad.right, yy); ctx.stroke();
        ctx.fillStyle = '#8b949e';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(Math.round(maxVal * (1 - i / 5)), pad.left - 8, yy + 4);
    }}

    // X labels
    ctx.textAlign = 'center';
    rounds.forEach((r, i) => {{
        ctx.fillText('R' + r, x(i), H - pad.bottom + 20);
    }});

    // Draw line
    function drawLine(values, color, lw) {{
        ctx.strokeStyle = color;
        ctx.lineWidth = lw || 2;
        ctx.beginPath();
        values.forEach((v, i) => {{
            if (i === 0) ctx.moveTo(x(i), y(v));
            else ctx.lineTo(x(i), y(v));
        }});
        ctx.stroke();
        // Dots
        values.forEach((v, i) => {{
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x(i), y(v), 4, 0, Math.PI * 2);
            ctx.fill();
        }});
    }}

    drawLine(totals, '#58a6ff', 2.5);
    drawLine(validated, '#3fb950', 2);
    drawLine(proven_, '#f0c000', 2);

    // Legend
    const legend = [['Total', '#58a6ff'], ['Validated', '#3fb950'], ['Proven', '#f0c000']];
    legend.forEach(([label, color], i) => {{
        const lx = pad.left + i * 120;
        ctx.fillStyle = color;
        ctx.fillRect(lx, 8, 12, 12);
        ctx.fillStyle = '#e6edf3';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(label, lx + 18, 18);
    }});
}})();
"""
