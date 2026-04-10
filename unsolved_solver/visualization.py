"""
Visualization — HTML Report Generator
=======================================
Generates a comprehensive interactive HTML report of all findings,
including proof space visualization, pattern graphs, and discovery lineage.
"""

import json
import html
import time
from typing import Any, Dict, List


def generate_html_report(results: Dict[str, Any], output_path: str = '') -> str:
    """Generate a full HTML report from orchestrator results."""

    total_time = results.get('total_time', 0)
    rounds = results.get('rounds_completed', 0)
    stats = results.get('global_stats', {})
    domain_reports = results.get('domain_reports', {})
    agent_stats = results.get('agent_stats', {})
    top_discoveries = results.get('top_discoveries', [])
    pre_hash = results.get('preregistration_hash', '')

    # Build domain sections
    domain_sections = []
    for domain_key, label, icon in [
        ('collatz', 'Collatz Conjecture', '🌀'),
        ('erdos_straus', 'Erdős–Straus Conjecture', '🔢'),
        ('hadamard', 'Hadamard Conjecture', '🔲'),
    ]:
        dr = domain_reports.get(domain_key, {})
        summary = dr.get('summary', {})
        breakthroughs = dr.get('breakthroughs', [])
        proof_sketches = dr.get('proof_sketches', [])

        breakthrough_cards = '\n'.join(_discovery_card(b) for b in breakthroughs[:5])
        proof_cards = '\n'.join(_proof_card(p) for p in proof_sketches[:5])

        by_cat = summary.get('by_category', {})
        by_status = summary.get('by_status', {})

        domain_sections.append(f"""
        <div class="domain-section" id="{domain_key}">
            <h2>{icon} {label}</h2>
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value">{summary.get('count', 0)}</div>
                    <div class="stat-label">Discoveries</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary.get('max_confidence', 0):.3f}</div>
                    <div class="stat-label">Max Confidence</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(proof_sketches)}</div>
                    <div class="stat-label">Proof Sketches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(breakthroughs)}</div>
                    <div class="stat-label">Breakthroughs</div>
                </div>
            </div>
            <div class="category-bar">
                {_category_bar(by_cat)}
            </div>
            <div class="status-bar">
                {_status_bar(by_status)}
            </div>
            {'<h3>🌟 Breakthroughs</h3><div class="discovery-list">' + breakthrough_cards + '</div>' if breakthrough_cards else ''}
            {'<h3>📝 Proof Sketches</h3><div class="proof-list">' + proof_cards + '</div>' if proof_cards else ''}
        </div>
        """)

    # Top discoveries section
    top_cards = '\n'.join(_discovery_card(d) for d in top_discoveries[:15])

    # Agent performance table
    agent_rows = '\n'.join(f"""
        <tr>
            <td><code>{html.escape(aid)}</code></td>
            <td>{a.get('type', '')}</td>
            <td>{a.get('rounds', 0)}</td>
            <td>{a.get('discoveries', 0)}</td>
            <td>{a.get('time_spent', 0):.1f}s</td>
        </tr>
    """ for aid, a in sorted(agent_stats.items()))

    # Progress chart data
    progress_data = json.dumps(results.get('results_log', []), default=str)

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Self-Iterative AI Problem Solver — Results Report</title>
<style>
:root {{
    --bg: #0d1117; --surface: #161b22; --surface2: #21262d;
    --border: #30363d; --text: #e6edf3; --text2: #8b949e;
    --accent: #58a6ff; --success: #3fb950; --warning: #d29922;
    --danger: #f85149; --purple: #bc8cff; --pink: #f778ba;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
h1 {{ font-size: 2rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, var(--accent), var(--purple), var(--pink)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
h2 {{ font-size: 1.5rem; margin: 2rem 0 1rem; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
h3 {{ font-size: 1.2rem; margin: 1.5rem 0 0.5rem; color: var(--purple); }}
.subtitle {{ color: var(--text2); margin-bottom: 2rem; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; text-align: center; }}
.stat-value {{ font-size: 1.8rem; font-weight: bold; color: var(--accent); }}
.stat-label {{ font-size: 0.85rem; color: var(--text2); }}
.domain-section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0; }}
.discovery-card {{ background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 0.5rem 0; }}
.discovery-card .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
.discovery-card .category {{ font-size: 0.8rem; padding: 2px 8px; border-radius: 12px; font-weight: 600; }}
.cat-pattern {{ background: #1f3a5f; color: var(--accent); }}
.cat-invariant {{ background: #1a3a1a; color: var(--success); }}
.cat-hypothesis {{ background: #3a2a0a; color: var(--warning); }}
.cat-proof_sketch {{ background: #2a1a3a; color: var(--purple); }}
.cat-counterexample {{ background: #3a1a1a; color: var(--danger); }}
.cat-construction {{ background: #1a2a3a; color: var(--pink); }}
.cat-family {{ background: #2a2a1a; color: #e3c97a; }}
.cat-transfer {{ background: #1a3a3a; color: #7ae3c9; }}
.confidence-bar {{ height: 4px; border-radius: 2px; background: var(--border); margin-top: 0.5rem; }}
.confidence-fill {{ height: 100%; border-radius: 2px; transition: width 0.3s; }}
.conf-high {{ background: var(--success); }}
.conf-med {{ background: var(--warning); }}
.conf-low {{ background: var(--danger); }}
.content-preview {{ font-size: 0.85rem; color: var(--text2); margin: 0.5rem 0; max-height: 100px; overflow: hidden; }}
.proof-code {{ background: #0d1117; border: 1px solid var(--border); border-radius: 6px; padding: 0.8rem; font-family: 'Cascadia Code', monospace; font-size: 0.8rem; white-space: pre-wrap; overflow-x: auto; margin: 0.5rem 0; max-height: 300px; overflow-y: auto; color: #c9d1d9; }}
.category-bar, .status-bar {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.5rem 0; }}
.badge {{ font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; background: var(--surface2); border: 1px solid var(--border); }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
th, td {{ padding: 0.5rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ color: var(--text2); font-weight: 600; font-size: 0.85rem; }}
td {{ font-size: 0.9rem; }}
tr:hover {{ background: var(--surface2); }}
.chart-container {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0; }}
canvas {{ width: 100% !important; height: 300px !important; }}
.hash {{ font-family: monospace; font-size: 0.75rem; color: var(--text2); word-break: break-all; background: var(--surface); padding: 0.5rem; border-radius: 4px; }}
.nav {{ position: sticky; top: 0; z-index: 100; background: var(--bg); border-bottom: 1px solid var(--border); padding: 0.8rem 2rem; display: flex; gap: 1rem; flex-wrap: wrap; }}
.nav a {{ color: var(--accent); text-decoration: none; font-size: 0.9rem; padding: 4px 12px; border-radius: 6px; }}
.nav a:hover {{ background: var(--surface); }}
.expand-btn {{ cursor: pointer; color: var(--accent); font-size: 0.8rem; margin-top: 0.3rem; }}
</style>
</head>
<body>
<nav class="nav">
    <a href="#overview">Overview</a>
    <a href="#collatz">Collatz</a>
    <a href="#erdos_straus">Erdős–Straus</a>
    <a href="#hadamard">Hadamard</a>
    <a href="#discoveries">Top Discoveries</a>
    <a href="#agents">Agents</a>
    <a href="#progress">Progress</a>
</nav>

<div class="container">
    <h1>Self-Iterative Collaborative AI Problem Solver</h1>
    <p class="subtitle">Attacking Collatz · Erdős–Straus · Hadamard conjectures via multi-agent swarm intelligence</p>

    <div id="overview">
        <h2>📊 Overview</h2>
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-value">{rounds}</div>
                <div class="stat-label">Rounds Completed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_discoveries', 0)}</div>
                <div class="stat-label">Total Discoveries</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_validated', 0)}</div>
                <div class="stat-label">Validated</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_falsified', 0)}</div>
                <div class="stat-label">Falsified</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_time:.1f}s</div>
                <div class="stat-label">Total Time</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(agent_stats)}</div>
                <div class="stat-label">Active Agents</div>
            </div>
        </div>
        <p class="hash">Pre-registration SHA-256: {pre_hash}</p>
    </div>

    {''.join(domain_sections)}

    <div id="discoveries">
        <h2>🏆 Top Discoveries (All Domains)</h2>
        <div class="discovery-list">
            {top_cards}
        </div>
    </div>

    <div id="agents">
        <h2>🤖 Agent Performance</h2>
        <table>
            <thead>
                <tr><th>Agent</th><th>Type</th><th>Rounds</th><th>Discoveries</th><th>Time</th></tr>
            </thead>
            <tbody>
                {agent_rows}
            </tbody>
        </table>
    </div>

    <div id="progress" class="chart-container">
        <h2>📈 Discovery Progress</h2>
        <canvas id="progressChart"></canvas>
    </div>
</div>

<script>
// Simple chart rendering using Canvas API
const progressData = {progress_data};
const canvas = document.getElementById('progressChart');
if (canvas && progressData.length > 0) {{
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.parentElement.clientWidth - 48;
    const H = canvas.height = 280;
    const pad = {{ top: 30, right: 20, bottom: 40, left: 50 }};
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    // Extract data
    const rounds = progressData.map(d => d.round);
    const discoveries = progressData.map(d => d.discoveries);
    const cumulative = discoveries.reduce((acc, v) => {{
        acc.push((acc.length > 0 ? acc[acc.length-1] : 0) + v);
        return acc;
    }}, []);

    const maxY = Math.max(...cumulative, 1);
    const scaleX = (i) => pad.left + (i / Math.max(rounds.length - 1, 1)) * plotW;
    const scaleY = (v) => pad.top + plotH - (v / maxY) * plotH;

    // Grid
    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {{
        const y = pad.top + (i / 4) * plotH;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
    }}

    // Cumulative line
    ctx.strokeStyle = '#58a6ff';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    cumulative.forEach((v, i) => {{
        const x = scaleX(i), y = scaleY(v);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }});
    ctx.stroke();

    // Per-round bars
    const barW = Math.max(plotW / rounds.length * 0.6, 4);
    ctx.fillStyle = 'rgba(188, 140, 255, 0.5)';
    discoveries.forEach((v, i) => {{
        const x = scaleX(i) - barW/2;
        const h = (v / maxY) * plotH;
        ctx.fillRect(x, pad.top + plotH - h, barW, h);
    }});

    // Points
    ctx.fillStyle = '#58a6ff';
    cumulative.forEach((v, i) => {{
        ctx.beginPath();
        ctx.arc(scaleX(i), scaleY(v), 4, 0, Math.PI * 2);
        ctx.fill();
    }});

    // Labels
    ctx.fillStyle = '#8b949e';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    rounds.forEach((r, i) => {{
        ctx.fillText('R' + r, scaleX(i), H - 10);
    }});
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {{
        const v = Math.round(maxY * (4 - i) / 4);
        ctx.fillText(v, pad.left - 8, pad.top + (i / 4) * plotH + 4);
    }}
    ctx.textAlign = 'center';
    ctx.fillStyle = '#58a6ff';
    ctx.fillText('Cumulative Discoveries', W/2, 18);
}}

// Expand/collapse
document.querySelectorAll('.expand-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        const target = btn.previousElementSibling;
        if (target) {{
            target.style.maxHeight = target.style.maxHeight === 'none' ? '100px' : 'none';
            btn.textContent = target.style.maxHeight === 'none' ? '▲ collapse' : '▼ expand';
        }}
    }});
}});
</script>
</body>
</html>"""

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_html)

    return report_html


def _discovery_card(d: Dict[str, Any]) -> str:
    """Render a single discovery as an HTML card."""
    cat = d.get('category', 'unknown')
    conf = d.get('confidence', 0)
    conf_class = 'conf-high' if conf > 0.7 else 'conf-med' if conf > 0.3 else 'conf-low'
    content = d.get('content', {})

    # Extract preview text
    desc = content.get('description', content.get('type', content.get('name', '')))
    if not desc and isinstance(content, dict):
        desc = ', '.join(f"{k}={v}" for k, v in list(content.items())[:3]
                        if k not in ('lean4_code', 'matrix', 'stats'))

    preview = html.escape(str(desc)[:200])

    return f"""
    <div class="discovery-card">
        <div class="header">
            <span>
                <strong>{html.escape(d.get('id', ''))}</strong>
                <span class="category cat-{cat}">{cat}</span>
                <span class="badge">{html.escape(d.get('domain', ''))}</span>
            </span>
            <span style="color: var(--text2)">{conf:.2f}</span>
        </div>
        <div class="content-preview">{preview}</div>
        <span class="expand-btn">▼ expand</span>
        <div class="confidence-bar">
            <div class="confidence-fill {conf_class}" style="width: {conf*100:.0f}%"></div>
        </div>
    </div>
    """


def _proof_card(d: Dict[str, Any]) -> str:
    """Render a proof sketch as an HTML card."""
    content = d.get('content', {})
    lean_code = content.get('lean4_code', '')
    strategy = content.get('proof_strategy', content.get('type', ''))

    return f"""
    <div class="discovery-card">
        <div class="header">
            <span>
                <strong>{html.escape(d.get('id', ''))}</strong>
                <span class="category cat-proof_sketch">proof_sketch</span>
            </span>
            <span style="color: var(--purple)">{strategy}</span>
        </div>
        {'<div class="proof-code">' + html.escape(lean_code) + '</div>' if lean_code else ''}
    </div>
    """


def _category_bar(by_cat: Dict) -> str:
    """Render category distribution as badges."""
    if not by_cat:
        return ''
    return ' '.join(f'<span class="badge cat-{html.escape(str(k))}">{html.escape(str(k))}: {v}</span>'
                    for k, v in sorted(by_cat.items(), key=lambda x: -x[1]))


def _status_bar(by_status: Dict) -> str:
    """Render status distribution as badges."""
    if not by_status:
        return ''
    colors = {'proposed': '#8b949e', 'validated': '#3fb950',
              'falsified': '#f85149', 'refined': '#d29922'}
    return ' '.join(
        f'<span class="badge" style="color:{colors.get(str(k),"#8b949e")}">'
        f'{html.escape(str(k))}: {v}</span>'
        for k, v in sorted(by_status.items(), key=lambda x: -x[1]))
