"""
visualization.py - Interactive HTML report generator for the Ramanujan-Physics Bridge.

Produces a single-file, self-contained HTML report with:
  - Grand narrative threads
  - Connection web visualisation
  - Formula decomposition cards
  - Physics domain explorer
  - Cross-formula bridge map
  - Missing links / predictions
  - Proposal status tracker
"""

import json
from pathlib import Path


def generate_html_report(report, output_path="ramanujan-physics-bridge.html"):
    """Generate the full interactive HTML report."""

    meta = report["meta"]
    stats = report["statistics"]
    connections = report["connections"]
    patterns = report["patterns"]
    narrative = report["grand_narrative"]
    cross_bridges = report["cross_formula_bridges"]
    missing = report["missing_links"]
    proposals = report["proposals"]
    decomps = report["decompositions"]
    round_logs = report["round_logs"]

    # Group connections by domain
    by_domain = {}
    for c in connections:
        d = c.get("physics_concept", "").split("-")[0] if "-" in c.get("physics_concept", "") else "other"
        domain_names = {
            "BH": "Black Holes", "ST": "String Theory", "QFT": "Quantum Field Theory",
            "SM": "Statistical Mechanics", "CFT": "Conformal Field Theory",
            "QG": "Quantum Gravity", "HEP": "High-Energy Physics"
        }
        dn = domain_names.get(d, d)
        if dn not in by_domain:
            by_domain[dn] = []
        by_domain[dn].append(c)

    # Group connections by formula
    by_formula = {}
    for c in connections:
        fid = c["formula_id"]
        if fid not in by_formula:
            by_formula[fid] = []
        by_formula[fid].append(c)

    # Build narrative HTML cards
    narrative_html = ""
    thread_colors = {
        "Partitions and Black Hole Entropy": "#ff6b6b",
        "Ramanujan Pi-Series and Calabi-Yau Periods": "#4ecdc4",
        "Mock Theta Functions and Quantum Black Holes": "#a855f7",
        "Zeta Regularisation and the Critical Dimension": "#f59e0b",
        "Rogers-Ramanujan, Hard Hexagons, and CFT": "#22c55e",
        "Moonshine and Monstrous Symmetry": "#3b82f6",
        "Pi as a Structural Connector": "#ec4899",
    }
    tier_style = {
        "well-established": ("Well-established", "#22c55e"),
        "strongly_suggestive": ("Strongly suggestive", "#4ecdc4"),
        "mixed": ("Mixed evidence", "#f59e0b"),
        "speculative": ("Speculative", "#ff6b6b"),
        "interpretive": ("Interpretive synthesis", "#a855f7"),
    }
    for i, n in enumerate(narrative):
        color = thread_colors.get(n["thread"], "#6b7280")
        depth_badge = {
            "exact_match": "Exact Match",
            "structural_identity": "Structural Identity",
            "exact_calculation": "Exact Calculation",
            "deep_structural": "Deep Structural",
            "universal": "Universal",
            "interpretive_synthesis": "Interpretive Synthesis",
        }.get(n.get("depth", ""), n.get("depth", ""))

        # Evidence tier badge
        tier_key = n.get("evidence_tier", "")
        tier_label, tier_color = tier_style.get(tier_key, (tier_key or "unclassified", "#6b7280"))
        tier_html = (f'<span class="evidence-tier" style="background: {tier_color}20; '
                     f'color: {tier_color}; border: 1px solid {tier_color}40">'
                     f'{tier_label}</span>')

        # Evidence note
        evidence_note = n.get("evidence_note", "")
        evidence_note_html = (f'<p class="evidence-note">{_escape(evidence_note)}</p>'
                              if evidence_note else "")

        # Citations
        citations = n.get("citations", [])
        citations_html = ""
        if citations:
            cite_items = "".join(f'<li>{_escape(c)}</li>' for c in citations)
            citations_html = f'<details class="citations"><summary>References ({len(citations)})</summary><ul>{cite_items}</ul></details>'

        formulas_html = ""
        for fid in n.get("key_formulas", []):
            if fid != "all":
                formulas_html += f'<span class="tag formula-tag">{fid}</span>'

        physics_html = ""
        for pid in n.get("key_physics", []):
            if pid != "all":
                physics_html += f'<span class="tag physics-tag">{pid}</span>'

        narrative_html += f'''
        <div class="narrative-card" style="border-left: 4px solid {color}">
            <div class="narrative-header">
                <span class="thread-label" style="background: {color}20; color: {color}">{n["thread"]}</span>
                <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap">
                    {tier_html}
                    <span class="depth-badge" style="background: {color}">{depth_badge}</span>
                </div>
            </div>
            <h3>{n["title"]}</h3>
            <p class="narrative-text">{n["summary"]}</p>
            {evidence_note_html}
            {citations_html}
            <div class="tag-row">
                {formulas_html}
                {physics_html}
            </div>
        </div>
        '''

    # Build pattern cards
    patterns_html = ""
    for p in patterns:
        conf_pct = int(p["confidence"] * 100)
        formulas_tags = "".join(f'<span class="tag formula-tag">{f}</span>' for f in p["formulas"][:4])
        patterns_html += f'''
        <div class="pattern-card">
            <div class="pattern-header">
                <h4>{_escape(p["name"])}</h4>
                <div class="confidence-bar-mini">
                    <div class="confidence-fill" style="width: {conf_pct}%"></div>
                    <span>{conf_pct}%</span>
                </div>
            </div>
            <p>{_escape(p["description"][:300])}{"..." if len(p["description"]) > 300 else ""}</p>
            <p class="physics-impl"><strong>Physics:</strong> {_escape(p["physics_implication"][:200])}</p>
            <div class="tag-row">{formulas_tags}</div>
        </div>
        '''

    # Build connection table rows
    conn_rows = ""
    seen_conns = set()
    sorted_conns = sorted(connections, key=lambda c: c["strength"], reverse=True)
    for c in sorted_conns[:60]:
        key = (c["formula_id"], c["physics_concept"])
        if key in seen_conns:
            continue
        seen_conns.add(key)
        strength_class = "strong" if c["strength"] >= 0.8 else "medium" if c["strength"] >= 0.5 else "weak"
        conn_rows += f'''
        <tr class="conn-{strength_class}">
            <td><span class="tag formula-tag">{c["formula_id"]}</span></td>
            <td>{_escape(c["component"])}</td>
            <td><span class="tag physics-tag">{c["physics_concept"]}</span></td>
            <td>
                <div class="strength-bar">
                    <div class="strength-fill strength-{strength_class}" style="width: {int(c['strength']*100)}%"></div>
                </div>
                <span class="strength-val">{c['strength']:.2f}</span>
            </td>
            <td class="mapping-text">{_escape(c["mapping"][:120])}</td>
        </tr>
        '''

    # Domain stats for the pie chart
    domain_data_js = json.dumps(stats.get("by_domain", {}))

    # Missing links cards
    missing_html = ""
    for m in missing[:12]:
        missing_html += f'''
        <div class="missing-card">
            <div class="missing-header">
                <span class="tag formula-tag">{m["formula_id"]}</span>
                <span class="arrow">---</span>
                <span class="tag physics-tag">{m["concept_id"]}</span>
            </div>
            <p>{_escape(m["suggestion"])}</p>
            <div class="overlap-bar">
                <div class="overlap-fill" style="width: {int(m['overlap_score']*100)}%"></div>
                <span>Overlap: {m['overlap_score']:.0%}</span>
            </div>
        </div>
        '''

    # Proposals table
    proposal_rows = ""
    for p in proposals:
        status_class = {"proposed": "status-proposed", "confirmed": "status-confirmed",
                        "falsified": "status-falsified", "tested": "status-tested"}.get(p["status"], "")
        proposal_rows += f'''
        <tr>
            <td>{_escape(p["id"])}</td>
            <td>{_escape(p["source"])}</td>
            <td class="{status_class}">{p["status"].upper()}</td>
            <td>{_escape(p["predicted"])}</td>
            <td class="motivation-text">{_escape(p["motivation"][:150])}</td>
        </tr>
        '''

    # Round timeline
    round_timeline_html = ""
    for rl in round_logs:
        round_timeline_html += f'''
        <div class="round-card">
            <div class="round-num">R{rl["round"]}</div>
            <div class="round-stats">
                <span title="Decompositions">D:{rl["decompositions"]}</span>
                <span title="Connections">C:{rl["connections"]}</span>
                <span title="Patterns">P:{rl["patterns"]}</span>
                <span title="Bridges">B:{rl["cross_bridges"]}</span>
                <span title="Proposals">G:{rl["proposals"]}</span>
                <span title="Time">{rl.get("time_sec", 0)}s</span>
            </div>
        </div>
        '''

    # Decomposition cards
    decomp_html = ""
    for d in decomps:
        comps_html = ""
        for comp in d.get("components", []):
            comps_html += f'''
            <div class="comp-item">
                <span class="comp-primitive">{_escape(comp["primitive"])}</span>
                <span class="comp-role">{_escape(comp["role"])}</span>
                {f'<span class="comp-hint">{_escape(comp["physics_hint"])}</span>' if comp.get("physics_hint") else ""}
            </div>
            '''
        hidden_html = ""
        for h in d.get("hidden_constants", []):
            hidden_html += f'<div class="hidden-item">{_escape(str(h.get("significance", h.get("relationship", str(h)))))}</div>'

        sym_html = ""
        for s in d.get("symmetries", []):
            sym_html += f'<div class="sym-item"><strong>{_escape(s["type"])}</strong>: {_escape(s.get("physics", ""))}</div>'

        decomp_html += f'''
        <div class="decomp-card">
            <h4>{_escape(d["formula_id"])} <span class="family-badge">{_escape(d["family"])}</span></h4>
            <div class="comp-list">{comps_html}</div>
            {f'<div class="hidden-constants"><strong>Hidden constants:</strong>{hidden_html}</div>' if hidden_html else ""}
            {f'<div class="symmetries"><strong>Symmetries:</strong>{sym_html}</div>' if sym_html else ""}
        </div>
        '''

    # Cross bridges summary
    bridge_summary = {}
    for b in cross_bridges:
        d = b.get("domain", "unknown")
        bridge_summary[d] = bridge_summary.get(d, 0) + 1
    bridge_summary_html = ""
    for d, count in sorted(bridge_summary.items(), key=lambda x: -x[1]):
        bridge_summary_html += f'<div class="bridge-stat"><span class="bridge-domain">{_escape(d)}</span><span class="bridge-count">{count}</span></div>'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ramanujan-Physics Bridge: Pi, Black Holes &amp; High-Energy Physics</title>
<style>
:root {{
    --bg: #0f0f1a;
    --surface: #1a1a2e;
    --surface2: #222240;
    --text: #e0e0f0;
    --text2: #a0a0c0;
    --accent1: #ff6b6b;
    --accent2: #4ecdc4;
    --accent3: #a855f7;
    --accent4: #f59e0b;
    --accent5: #22c55e;
    --accent6: #3b82f6;
    --accent7: #ec4899;
    --border: #333355;
    --strong: #00ff88;
    --medium: #ffaa00;
    --weak: #ff4444;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 2.2em; margin-bottom: 10px; background: linear-gradient(135deg, var(--accent1), var(--accent3), var(--accent6));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
h2 {{ font-size: 1.5em; margin: 30px 0 15px; color: var(--accent2); border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
h3 {{ font-size: 1.2em; margin: 10px 0; color: var(--text); }}
h4 {{ font-size: 1.05em; color: var(--accent2); }}
p {{ margin: 8px 0; }}
.subtitle {{ color: var(--text2); font-size: 1.1em; margin-bottom: 20px; }}
.meta-bar {{ display: flex; gap: 20px; flex-wrap: wrap; padding: 15px; background: var(--surface); border-radius: 10px; margin-bottom: 25px; font-size: 0.9em; }}
.meta-item {{ display: flex; align-items: center; gap: 6px; }}
.meta-label {{ color: var(--text2); }}
.meta-value {{ color: var(--accent2); font-weight: 600; }}

/* Stats grid */
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat-card {{ background: var(--surface); border-radius: 10px; padding: 15px; text-align: center; border: 1px solid var(--border); }}
.stat-value {{ font-size: 2em; font-weight: 700; }}
.stat-label {{ color: var(--text2); font-size: 0.85em; }}
.stat-card:nth-child(1) .stat-value {{ color: var(--accent1); }}
.stat-card:nth-child(2) .stat-value {{ color: var(--accent2); }}
.stat-card:nth-child(3) .stat-value {{ color: var(--accent3); }}
.stat-card:nth-child(4) .stat-value {{ color: var(--accent4); }}
.stat-card:nth-child(5) .stat-value {{ color: var(--accent5); }}
.stat-card:nth-child(6) .stat-value {{ color: var(--accent6); }}

/* Tabs */
.tabs {{ display: flex; gap: 0; border-bottom: 2px solid var(--border); margin-bottom: 20px; flex-wrap: wrap; }}
.tab {{ padding: 10px 20px; cursor: pointer; color: var(--text2); border-bottom: 2px solid transparent;
    margin-bottom: -2px; transition: all 0.2s; user-select: none; }}
.tab:hover {{ color: var(--text); background: var(--surface); }}
.tab.active {{ color: var(--accent2); border-bottom-color: var(--accent2); }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; animation: fadeIn 0.3s; }}
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(5px); }} to {{ opacity: 1; transform: none; }} }}

/* Narrative cards */
.narrative-card {{ background: var(--surface); border-radius: 10px; padding: 20px; margin: 15px 0;
    border: 1px solid var(--border); transition: transform 0.2s; }}
.narrative-card:hover {{ transform: translateX(4px); }}
.narrative-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }}
.thread-label {{ padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: 600; }}
.depth-badge {{ padding: 3px 10px; border-radius: 12px; font-size: 0.75em; color: white; font-weight: 600; }}
.narrative-text {{ color: var(--text2); font-size: 0.95em; line-height: 1.7; }}

/* Evidence tiers */
.evidence-tier {{ padding: 3px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 600; }}
.evidence-note {{ color: var(--text2); font-size: 0.85em; font-style: italic; margin: 8px 0 4px; padding: 8px 12px;
    border-left: 2px solid var(--border); background: var(--bg); border-radius: 4px; }}
.citations {{ margin-top: 8px; font-size: 0.82em; color: var(--text2); }}
.citations summary {{ cursor: pointer; color: var(--accent6); font-weight: 500; }}
.citations ul {{ margin: 6px 0 0 20px; }}
.citations li {{ margin: 3px 0; }}

/* Tags */
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.78em; margin: 2px; font-family: monospace; }}
.formula-tag {{ background: var(--accent6)20; color: var(--accent6); border: 1px solid var(--accent6)40; }}
.physics-tag {{ background: var(--accent1)20; color: var(--accent1); border: 1px solid var(--accent1)40; }}
.tag-row {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 4px; }}

/* Patterns */
.pattern-card {{ background: var(--surface); border-radius: 10px; padding: 15px; margin: 10px 0;
    border: 1px solid var(--border); }}
.pattern-header {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
.confidence-bar-mini {{ width: 80px; height: 20px; background: var(--bg); border-radius: 10px; position: relative; overflow: hidden; }}
.confidence-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent5), var(--accent2)); border-radius: 10px; }}
.confidence-bar-mini span {{ position: absolute; right: 6px; top: 1px; font-size: 0.7em; color: white; }}
.physics-impl {{ color: var(--accent4); font-size: 0.9em; font-style: italic; }}

/* Connection table */
.conn-table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
.conn-table th {{ background: var(--surface2); padding: 10px; text-align: left; color: var(--accent2); font-weight: 600; }}
.conn-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); }}
.conn-table tr:hover {{ background: var(--surface2); }}
.strength-bar {{ width: 60px; height: 8px; background: var(--bg); border-radius: 4px; display: inline-block; overflow: hidden; }}
.strength-fill {{ height: 100%; border-radius: 4px; }}
.strength-strong {{ background: var(--strong); }}
.strength-medium {{ background: var(--medium); }}
.strength-weak {{ background: var(--weak); }}
.strength-val {{ font-size: 0.85em; color: var(--text2); margin-left: 6px; }}
.mapping-text {{ color: var(--text2); font-size: 0.85em; max-width: 300px; }}

/* Missing links */
.missing-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
.missing-card {{ background: var(--surface); border-radius: 10px; padding: 15px; border: 1px solid var(--accent4)40;
    border-left: 3px solid var(--accent4); }}
.missing-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
.arrow {{ color: var(--accent4); font-weight: bold; }}
.overlap-bar {{ width: 100%; height: 6px; background: var(--bg); border-radius: 3px; margin-top: 8px; position: relative; }}
.overlap-fill {{ height: 100%; background: var(--accent4); border-radius: 3px; }}
.overlap-bar span {{ font-size: 0.75em; color: var(--text2); position: absolute; right: 0; top: -16px; }}

/* Proposals */
.proposals-table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
.proposals-table th {{ background: var(--surface2); padding: 10px; text-align: left; color: var(--accent3); }}
.proposals-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); }}
.status-proposed {{ color: var(--accent4); font-weight: 600; }}
.status-confirmed {{ color: var(--accent5); font-weight: 600; }}
.status-falsified {{ color: var(--accent1); font-weight: 600; }}
.status-tested {{ color: var(--accent6); font-weight: 600; }}
.motivation-text {{ color: var(--text2); font-size: 0.85em; }}

/* Decomposition */
.decomp-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 15px; }}
.decomp-card {{ background: var(--surface); border-radius: 10px; padding: 15px; border: 1px solid var(--border); }}
.family-badge {{ font-size: 0.75em; padding: 2px 8px; border-radius: 10px; background: var(--accent3)20; color: var(--accent3); margin-left: 8px; }}
.comp-list {{ margin: 10px 0; }}
.comp-item {{ padding: 6px 10px; margin: 4px 0; background: var(--bg); border-radius: 6px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
.comp-primitive {{ font-family: monospace; color: var(--accent2); font-size: 0.9em; }}
.comp-role {{ font-size: 0.8em; color: var(--text2); padding: 1px 6px; background: var(--surface2); border-radius: 4px; }}
.comp-hint {{ font-size: 0.8em; color: var(--accent4); font-style: italic; }}
.hidden-constants, .symmetries {{ margin-top: 8px; font-size: 0.88em; }}
.hidden-item, .sym-item {{ padding: 4px 0; color: var(--text2); border-top: 1px solid var(--border); }}

/* Timeline */
.round-timeline {{ display: flex; gap: 15px; overflow-x: auto; padding: 10px 0; }}
.round-card {{ background: var(--surface); border-radius: 10px; padding: 12px; min-width: 120px; text-align: center;
    border: 1px solid var(--border); flex-shrink: 0; }}
.round-num {{ font-size: 1.3em; font-weight: 700; color: var(--accent2); }}
.round-stats {{ font-size: 0.75em; color: var(--text2); margin-top: 6px; display: flex; flex-direction: column; gap: 2px; }}
.round-stats span {{ display: block; }}

/* Bridge summary */
.bridge-stats {{ display: flex; gap: 10px; flex-wrap: wrap; }}
.bridge-stat {{ background: var(--surface); padding: 8px 15px; border-radius: 20px; display: flex; gap: 8px; align-items: center; }}
.bridge-domain {{ color: var(--text2); font-size: 0.9em; }}
.bridge-count {{ color: var(--accent2); font-weight: 700; }}

/* Canvas */
canvas {{ background: var(--surface); border-radius: 10px; border: 1px solid var(--border); }}

/* Domain pie */
.domain-chart {{ display: flex; justify-content: center; padding: 20px; }}

/* Footer */
.footer {{ text-align: center; color: var(--text2); font-size: 0.85em; padding: 30px 0; border-top: 1px solid var(--border); margin-top: 40px; }}

@media (max-width: 768px) {{
    .container {{ padding: 10px; }}
    h1 {{ font-size: 1.5em; }}
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .decomp-grid {{ grid-template-columns: 1fr; }}
    .missing-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="container">

<h1>Ramanujan-Physics Bridge</h1>
<p class="subtitle">Self-Iterating Agent for Reverse-Engineering Ramanujan Formulas &mdash;
Connecting Pi, Black Holes &amp; High-Energy Physics</p>

<div class="meta-bar">
    <div class="meta-item"><span class="meta-label">Engine:</span><span class="meta-value">{meta['engine']}</span></div>
    <div class="meta-item"><span class="meta-label">Rounds:</span><span class="meta-value">{meta['rounds']}</span></div>
    <div class="meta-item"><span class="meta-label">Formulas:</span><span class="meta-value">{meta['formula_count']}</span></div>
    <div class="meta-item"><span class="meta-label">Precision:</span><span class="meta-value">{meta['precision']} digits</span></div>
    <div class="meta-item"><span class="meta-label">Elapsed:</span><span class="meta-value">{meta['elapsed_seconds']}s</span></div>
    <div class="meta-item"><span class="meta-label">Generated:</span><span class="meta-value">{meta['timestamp']}</span></div>
</div>

<!-- Stats overview -->
<p style="color: var(--text2); font-size: 0.88em; margin-bottom: 10px">Statistics below count <em>pattern-match mappings</em> (formula-primitive &rarr; physics-concept), not causal links.
See the <span style="color:var(--accent2); cursor:pointer" onclick="document.querySelector('[data-tab=methodology]').click()">Methodology</span> tab for scoring definitions.</p>
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-value">{meta['formula_count']}</div>
        <div class="stat-label">Formulas Analysed</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{len(stats.get('by_domain', dict()))}</div>
        <div class="stat-label">Physics Domains</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{len(narrative)}</div>
        <div class="stat-label">Narrative Threads</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{len(patterns)}</div>
        <div class="stat-label">Structural Patterns</div>
    </div>
    <div class="stat-card" title="Formula-concept pairs sharing mathematical structure but not yet mapped by the engine">
        <div class="stat-value">{len(missing)}</div>
        <div class="stat-label">Predicted Links</div>
    </div>
    <div class="stat-card" title="New formula variants proposed by extrapolating structural patterns in existing identities">
        <div class="stat-value">{len(proposals)}</div>
        <div class="stat-label">Generalisations</div>
    </div>
</div>
<p style="color: var(--text2); font-size: 0.82em; margin-top: 6px"><em>Predicted Links</em> = formula-concept pairs with shared primitives not yet mapped; <em>Generalisations</em> = new formula variants proposed by extrapolating structural patterns.</p>

<!-- Tabs -->
<div class="tabs">
    <div class="tab active" data-tab="narrative">Grand Narrative</div>
    <div class="tab" data-tab="connections">Connection Web</div>
    <div class="tab" data-tab="decomp">Formula Decomposition</div>
    <div class="tab" data-tab="patterns">Structural Patterns</div>
    <div class="tab" data-tab="missing">Missing Links</div>
    <div class="tab" data-tab="proposals">Proposals</div>
    <div class="tab" data-tab="timeline">Discovery Timeline</div>
    <div class="tab" data-tab="methodology">Methodology</div>
</div>

<!-- Tab: Grand Narrative -->
<div class="tab-content active" id="tab-narrative">
    <h2>The Seven Threads: How Ramanujan Connects Pi, Black Holes &amp; HEP</h2>
    <p style="color: var(--text2); margin-bottom: 15px;">Each thread traces a path from Ramanujan's mathematics
    to modern physics. Together, they form a web of structural analogies and proven identities.
    Evidence tiers indicate which claims rest on rigorous proofs versus conjectural analogies.</p>
    {narrative_html}
</div>

<!-- Tab: Connections -->
<div class="tab-content" id="tab-connections">
    <h2>Connection Web: Formulas &harr; Physics</h2>
    <div class="domain-chart">
        <canvas id="domainCanvas" width="600" height="350"></canvas>
    </div>
    <h3 style="margin-top:20px">All Connections (sorted by strength)</h3>
    <div style="overflow-x: auto;">
    <table class="conn-table">
        <thead><tr>
            <th>Formula</th><th>Component</th><th>Physics Concept</th><th>Strength</th><th>Mapping</th>
        </tr></thead>
        <tbody>{conn_rows}</tbody>
    </table>
    </div>
</div>

<!-- Tab: Decomposition -->
<div class="tab-content" id="tab-decomp">
    <h2>Structural Decomposition of Ramanujan Formulas</h2>
    <p style="color: var(--text2)">Each formula is broken into primitive building blocks, revealing
    hidden constants and symmetries that connect to physics.</p>
    <div class="decomp-grid">
        {decomp_html}
    </div>
</div>

<!-- Tab: Patterns -->
<div class="tab-content" id="tab-patterns">
    <h2>Cross-Formula Structural Patterns</h2>
    <p style="color: var(--text2)">Patterns discovered by comparing the structural decompositions
    of different formulas. These reveal deep connections.</p>
    {patterns_html}

    <h3 style="margin-top: 25px">Cross-Formula Bridge Summary</h3>
    <div class="bridge-stats">{bridge_summary_html}</div>
    <p style="color: var(--text2); margin-top: 10px">{len(cross_bridges)} total cross-formula bridges found</p>
</div>

<!-- Tab: Missing Links -->
<div class="tab-content" id="tab-missing">
    <h2>Missing Links: Predicted Connections to Investigate</h2>
    <p style="color: var(--text2)">The agent identified formulas that SHOULD connect to physics concepts
    (based on shared mathematical structure) but where the connection isn't yet established.
    These are research directions.</p>
    <div class="missing-grid">
        {missing_html}
    </div>
</div>

<!-- Tab: Proposals -->
<div class="tab-content" id="tab-proposals">
    <h2>Generalisation Proposals</h2>
    <p style="color: var(--text2)">New formulas proposed by extrapolating structural patterns.
    Each proposal has a physics motivation.</p>
    <div style="overflow-x: auto;">
    <table class="proposals-table">
        <thead><tr>
            <th>ID</th><th>Source</th><th>Status</th><th>Predicted</th><th>Motivation</th>
        </tr></thead>
        <tbody>{proposal_rows}</tbody>
    </table>
    </div>
</div>

<!-- Tab: Timeline -->
<div class="tab-content" id="tab-timeline">
    <h2>Discovery Timeline</h2>
    <p style="color: var(--text2)">Progress across {meta['rounds']} rounds of self-iterating discovery.</p>
    <div class="round-timeline">
        {round_timeline_html}
    </div>
</div>

<!-- Tab: Methodology -->
<div class="tab-content" id="tab-methodology">
    <h2>Methodology &amp; Scoring Rubric</h2>

    <div style="background: var(--surface); border-radius: 10px; padding: 20px; margin: 15px 0; border: 1px solid var(--border);">
        <h3 style="color: var(--accent4)">Important Disclaimer</h3>
        <p style="color: var(--text2); line-height: 1.7">
        This report maps <em>structural analogies</em> between Ramanujan's mathematics and modern physics.
        A high connection score means the mathematical primitive pattern-matches well to a physics concept;
        it does <strong>not</strong> imply a causal or explanatory link has been proven.
        Claims are graded by evidence tier so readers can distinguish rigorous proofs from conjectural bridges.
        </p>
    </div>

    <h3 style="margin-top: 25px; color: var(--accent2)">Connection Scoring Rubric</h3>
    <div style="background: var(--surface); border-radius: 10px; padding: 20px; margin: 10px 0; border: 1px solid var(--border);">
        <table class="conn-table" style="font-size: 0.9em">
            <thead><tr><th>Component</th><th>Score Contribution</th><th>Description</th></tr></thead>
            <tbody>
                <tr><td>Base match</td><td style="color: var(--accent2)">0.30</td>
                    <td style="color: var(--text2)">Any formula primitive that maps to a physics concept via PRIMITIVE_TO_PHYSICS lookup</td></tr>
                <tr><td>Pre-annotated link</td><td style="color: var(--accent2)">up to +0.40</td>
                    <td style="color: var(--text2)">Formula already carries a PhysicsLink to the same domain (takes whichever strength is higher)</td></tr>
                <tr><td>Domain-hint match</td><td style="color: var(--accent2)">+0.10</td>
                    <td style="color: var(--text2)">Component's physics_hint text mentions the physics concept's domain keyword</td></tr>
                <tr><td>Modular-property match</td><td style="color: var(--accent2)">+0.05</td>
                    <td style="color: var(--text2)">Formula has modular properties and concept lists modular_weight in math_signatures</td></tr>
                <tr><td>Synergy boost</td><td style="color: var(--accent2)">+0.05 to +0.15</td>
                    <td style="color: var(--text2)">Multiple components of the same formula point to the same physics concept</td></tr>
            </tbody>
        </table>
        <p style="color: var(--text2); margin-top: 15px; font-size: 0.88em">
            <strong style="color: var(--strong)">Strong (&ge; 0.7)</strong> &mdash;
            <strong style="color: var(--medium)">Medium (0.4 &ndash; 0.7)</strong> &mdash;
            <strong style="color: var(--weak)">Weak (&lt; 0.4)</strong>
        </p>
    </div>

    <h3 style="margin-top: 25px; color: var(--accent3)">Evidence Tiers</h3>
    <div style="background: var(--surface); border-radius: 10px; padding: 20px; margin: 10px 0; border: 1px solid var(--border);">
        <div style="display: grid; gap: 10px;">
            <div style="display:flex; gap:10px; align-items:center">
                <span class="evidence-tier" style="background: #22c55e20; color: #22c55e; border: 1px solid #22c55e40; min-width: 160px; text-align:center">Well-established</span>
                <span style="color: var(--text2); font-size: 0.9em">Proven theorems or experimentally confirmed results</span>
            </div>
            <div style="display:flex; gap:10px; align-items:center">
                <span class="evidence-tier" style="background: #4ecdc420; color: #4ecdc4; border: 1px solid #4ecdc440; min-width: 160px; text-align:center">Strongly suggestive</span>
                <span style="color: var(--text2); font-size: 0.9em">Substantial evidence from multiple independent lines; not yet fully proven</span>
            </div>
            <div style="display:flex; gap:10px; align-items:center">
                <span class="evidence-tier" style="background: #f59e0b20; color: #f59e0b; border: 1px solid #f59e0b40; min-width: 160px; text-align:center">Mixed evidence</span>
                <span style="color: var(--text2); font-size: 0.9em">Some rigorous results combined with conjectural extensions</span>
            </div>
            <div style="display:flex; gap:10px; align-items:center">
                <span class="evidence-tier" style="background: #ff6b6b20; color: #ff6b6b; border: 1px solid #ff6b6b40; min-width: 160px; text-align:center">Speculative</span>
                <span style="color: var(--text2); font-size: 0.9em">Plausible structural analogies without direct proof</span>
            </div>
            <div style="display:flex; gap:10px; align-items:center">
                <span class="evidence-tier" style="background: #a855f720; color: #a855f7; border: 1px solid #a855f740; min-width: 160px; text-align:center">Interpretive synthesis</span>
                <span style="color: var(--text2); font-size: 0.9em">Well-motivated synthesis of established results into a unifying narrative</span>
            </div>
        </div>
    </div>

    <h3 style="margin-top: 25px; color: var(--accent6)">Reproducibility</h3>
    <div style="background: var(--surface); border-radius: 10px; padding: 20px; margin: 10px 0; border: 1px solid var(--border); font-size: 0.9em;">
        <p style="color: var(--text2)"><strong>Engine:</strong> {meta.get('engine', 'N/A')}</p>
        <p style="color: var(--text2)"><strong>Python:</strong> {meta.get('libraries', dict()).get('python', 'N/A')}</p>
        <p style="color: var(--text2)"><strong>mpmath:</strong> {meta.get('libraries', dict()).get('mpmath', 'N/A')}</p>
        <p style="color: var(--text2)"><strong>Corpus:</strong> {meta.get('corpus', '14 formulas x 24 physics concepts')}</p>
        <p style="color: var(--text2)"><strong>Matching rules:</strong> PRIMITIVE_TO_PHYSICS lookup (17 primitives &rarr; 24 concepts)</p>
    </div>

    <h3 style="margin-top: 25px; color: var(--accent1)">Suggested Research Experiments</h3>
    <div style="background: var(--surface); border-radius: 10px; padding: 20px; margin: 10px 0; border: 1px solid var(--border); font-size: 0.9em;">
        <ol style="color: var(--text2); line-height: 1.8; padding-left: 20px;">
            <li><strong style="color: var(--accent2)">CY period &harr; Ramanujan series matching.</strong>
                Compute the Picard-Fuchs periods of the mirror quintic family at CM points
                tau = (1+i*sqrt(d))/2 for d in {{163, 67, 43, 19, 11}} and compare the resulting
                hypergeometric series coefficients to known Ramanujan-type 1/pi formulas.
                <em>Predicted outcome:</em> each CM point yields a distinct Ramanujan-type series
                whose convergence rate is proportional to log(j(tau)).</li>
            <li><strong style="color: var(--accent2)">Mock Jacobi expansions for other BPS indices.</strong>
                Extend the Dabholkar-Murthy-Zagier mock modular form computation to 1/8-BPS
                black holes in N=2 CHL orbifolds. Compute the first 50 Fourier coefficients
                of the mock Jacobi form psi_{10,1}(tau, z) and compare to the Rademacher
                expansion prediction for degeneracies at mass level N &le; 100.
                <em>Null test:</em> disagreement would falsify a specific string duality.</li>
            <li><strong style="color: var(--accent2)">Moonshine module for non-Monstrous groups.</strong>
                Construct explicit vertex operator algebra modules for umbral moonshine groups
                (Mathieu M_24, Conway Co_0) and compute their elliptic-genus mock modular forms.
                Compare to K3 surface twining genera (Gaberdiel, Hohenegger, Volpato 2010) to
                test whether Umbral moonshine admits a string-theoretic explanation analogous
                to FLM's Monstrous construction.</li>
        </ol>
    </div>

    <h3 style="margin-top: 25px; color: var(--accent5)">Prerequisites &amp; Reading Roadmap</h3>
    <div style="background: var(--surface); border-radius: 10px; padding: 20px; margin: 10px 0; border: 1px solid var(--border); font-size: 0.9em;">
        <p style="color: var(--text2); margin-bottom: 12px">This report bridges number theory and theoretical physics. A minimal reading path for each side:</p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px">
            <div>
                <h4 style="color: var(--accent6)">Mathematics side</h4>
                <ol style="color: var(--text2); line-height: 1.7; padding-left: 18px">
                    <li><em>Modular forms:</em> Diamond &amp; Shurman, <em>A First Course in Modular Forms</em> (Springer, 2005), Ch. 1&ndash;5</li>
                    <li><em>Partitions &amp; q-series:</em> Andrews, <em>The Theory of Partitions</em> (Cambridge, 1998), Ch. 1&ndash;6</li>
                    <li><em>Mock modular forms:</em> Zagier, &ldquo;Ramanujan&rsquo;s mock theta functions&rdquo; (S&eacute;m. Bourbaki 986, 2007)</li>
                    <li><em>Pi formulas &amp; CY periods:</em> Borwein &amp; Borwein, <em>Pi and the AGM</em> (Wiley, 1987), Ch. 5</li>
                </ol>
            </div>
            <div>
                <h4 style="color: var(--accent1)">Physics side</h4>
                <ol style="color: var(--text2); line-height: 1.7; padding-left: 18px">
                    <li><em>String theory basics:</em> Polchinski, <em>String Theory</em> vol. 1 (Cambridge, 1998), Ch. 1&ndash;4</li>
                    <li><em>Black hole entropy:</em> Strominger &amp; Vafa, Phys. Lett. B 379 (1996); then Sen, Gen. Rel. Grav. 40 (2008) for a review</li>
                    <li><em>CFT &amp; modular invariance:</em> Di Francesco, Mathieu &amp; S&eacute;n&eacute;chal, <em>Conformal Field Theory</em> (Springer, 1997), Ch. 10</li>
                    <li><em>Moonshine:</em> Gannon, <em>Moonshine beyond the Monster</em> (Cambridge, 2006)</li>
                </ol>
            </div>
        </div>
    </div>
</div>

<div class="footer">
    Ramanujan-Physics Bridge v1.1 &mdash; Self-Iterating Discovery Engine<br>
    Scores reflect structural-pattern matching, not causal evidence.<br>
    Generated {meta['timestamp']}
</div>

</div>

<script>
// Tab switching
document.querySelectorAll('.tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    }});
}});

// Domain distribution chart
(function() {{
    const canvas = document.getElementById('domainCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const data = {domain_data_js};
    const entries = Object.entries(data).sort((a,b) => b[1]-a[1]);
    const total = entries.reduce((s, e) => s + e[1], 0);
    const colors = ['#ff6b6b','#4ecdc4','#a855f7','#f59e0b','#22c55e','#3b82f6','#ec4899','#6b7280'];

    // Bar chart
    const barW = 45, gap = 15, startX = 60, startY = 30;
    const maxVal = Math.max(...entries.map(e => e[1]));
    const chartH = 250;

    ctx.fillStyle = '#e0e0f0';
    ctx.font = '14px Segoe UI';
    ctx.fillText('Connections by Physics Domain', startX, 22);

    entries.forEach((e, i) => {{
        const x = startX + i * (barW + gap);
        const h = (e[1] / maxVal) * chartH;
        const y = startY + chartH - h;

        ctx.fillStyle = colors[i % colors.length];
        ctx.fillRect(x, y, barW, h);

        // Value on top
        ctx.fillStyle = '#e0e0f0';
        ctx.font = '12px Segoe UI';
        ctx.textAlign = 'center';
        ctx.fillText(e[1], x + barW/2, y - 5);

        // Label below
        ctx.fillStyle = '#a0a0c0';
        ctx.font = '10px Segoe UI';
        ctx.save();
        ctx.translate(x + barW/2, startY + chartH + 12);
        ctx.rotate(-0.4);
        ctx.fillText(e[0], 0, 0);
        ctx.restore();
    }});

    // Percentage labels on right
    ctx.textAlign = 'left';
    ctx.font = '11px Segoe UI';
    let ly = startY + 10;
    entries.forEach((e, i) => {{
        ctx.fillStyle = colors[i % colors.length];
        ctx.fillRect(480, ly - 8, 10, 10);
        ctx.fillStyle = '#a0a0c0';
        ctx.fillText(e[0] + ' (' + Math.round(e[1]/total*100) + '%)', 496, ly);
        ly += 18;
    }});
}})();
</script>
</body>
</html>'''

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def _escape(s):
    """Escape HTML entities."""
    if not isinstance(s, str):
        s = str(s)
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))
