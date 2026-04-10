"""Generate ARIA peer-review HTML package."""
import os
import html as html_mod
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
ARIA_DIR = os.path.join(ROOT, "aria")
OUT_PATH = os.path.join(ROOT, "aria-peer-review.html")

FILES_ORDER = [
    "__init__.py", "__main__.py", "ingestion.py", "encoder.py",
    "conjecture_engine.py", "verifier.py", "axiom_bank.py",
    "synthesis.py", "output.py", "orchestrator.py",
]

LAYER_MAP = {
    "__init__.py": ("Package", "Package initialization and version"),
    "__main__.py": ("CLI", "Command-line interface entry point"),
    "ingestion.py": ("Layer 0", "Knowledge Ingestion &mdash; heterogeneous data into unified tuples"),
    "encoder.py": ("Layer 1", "Ramanujan Encoder &mdash; partition fingerprints, modular embeddings, CF depth"),
    "conjecture_engine.py": ("Layer 2", "Conjecture Engine &mdash; cross-domain resonance, analogy traversal, orphan matching"),
    "verifier.py": ("Layer 3", "Adversarial Telescoping Verifier &mdash; 4 rounds: numeric &rarr; symbolic &rarr; adversarial &rarr; domain"),
    "axiom_bank.py": ("Layer 4", "Axiom Bank (4A) + Lost Notebook (4B) &mdash; verified truths + quarantined mysteries"),
    "synthesis.py": ("Layer 5", "Cross-Domain Synthesis &mdash; notation mapping, isomorphism scoring, practical translation"),
    "output.py": ("Layer 6", "Output &amp; Iteration &mdash; reports, experiment specs, seed conjectures, HTML generation"),
    "orchestrator.py": ("Orchestrator", "Main Loop &mdash; wires all layers into the self-iterating discovery engine"),
}


def main():
    sources = {}
    total_lines = 0
    for fname in FILES_ORDER:
        fpath = os.path.join(ARIA_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        sources[fname] = content
        total_lines += content.count("\n") + 1

    # Build nav
    nav_items = []
    for fname in FILES_ORDER:
        layer, desc = LAYER_MAP[fname]
        safe_id = fname.replace(".", "-").replace("_", "-")
        lines = sources[fname].count("\n") + 1
        nav_items.append(
            f'<a href="#{safe_id}" class="nav-item">'
            f'<span class="nav-layer">{html_mod.escape(layer)}</span>'
            f'<span class="nav-file">{html_mod.escape(fname)}</span>'
            f'<span class="nav-lines">{lines}L</span>'
            f'</a>'
        )

    # Build code sections
    code_sections = []
    for fname in FILES_ORDER:
        layer, desc = LAYER_MAP[fname]
        safe_id = fname.replace(".", "-").replace("_", "-")
        lines = sources[fname].count("\n") + 1
        escaped = html_mod.escape(sources[fname])
        code_sections.append(
            f'<div class="code-section" id="{safe_id}">'
            f'<div class="section-header">'
            f'<div class="section-tag">{html_mod.escape(layer)}</div>'
            f'<h2>{html_mod.escape(fname)}</h2>'
            f'<p class="section-desc">{desc}</p>'
            f'<span class="line-count">{lines} lines</span>'
            f'</div>'
            f'<pre><code>{escaped}</code></pre>'
            f'</div>'
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    nav_html = "\n".join(nav_items)
    code_html = "\n".join(code_sections)

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ARIA v0.1.0 — Source Code for Peer Review</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --surface2: #21262d;
    --border: #30363d; --text: #c9d1d9; --text-dim: #8b949e;
    --accent: #7c3aed; --accent2: #06b6d4; --gold: #f59e0b;
    --green: #10b981; --red: #ef4444; --blue: #3b82f6;
    --code-bg: #0d1117; --line-num: #484f58;
    --kw: #ff7b72; --str: #a5d6ff; --num: #79c0ff;
    --fn: #d2a8ff; --cls: #ffa657; --cmt: #8b949e;
    --dec: #ffa657; --op: #ff7b72; --bi: #79c0ff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6;
  }}
  .page {{ display: flex; min-height: 100vh; }}
  .sidebar {{
    width: 280px; background: var(--surface); border-right: 1px solid var(--border);
    position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto; z-index: 10;
    padding: 1.5rem 0;
  }}
  .main {{ margin-left: 280px; flex: 1; padding: 2rem 3rem; max-width: 1000px; }}
  .sidebar-title {{
    padding: 0 1.2rem 1rem; font-size: 1.3rem; font-weight: 700;
    color: var(--accent); letter-spacing: 0.15em;
    border-bottom: 1px solid var(--border); margin-bottom: 1rem;
  }}
  .sidebar-subtitle {{
    padding: 0 1.2rem; font-size: 0.75rem; color: var(--text-dim);
    margin-bottom: 1.5rem;
  }}
  .nav-item {{
    display: flex; align-items: center; gap: 0.5rem; padding: 0.45rem 1.2rem;
    text-decoration: none; color: var(--text); font-size: 0.85rem;
    transition: background 0.15s;
  }}
  .nav-item:hover {{ background: var(--surface2); }}
  .nav-layer {{
    background: var(--surface2); color: var(--accent2); padding: 0.1rem 0.45rem;
    border-radius: 3px; font-size: 0.7rem; font-weight: 600; min-width: 72px;
    text-align: center; white-space: nowrap;
  }}
  .nav-file {{ flex: 1; font-family: 'Cascadia Code', 'Fira Code', monospace; }}
  .nav-lines {{ color: var(--text-dim); font-size: 0.72rem; }}
  .hero {{
    padding: 2.5rem 0 2rem; margin-bottom: 2rem;
    border-bottom: 1px solid var(--border);
  }}
  .hero h1 {{ font-size: 2.2rem; letter-spacing: 0.2em; color: var(--accent); }}
  .hero .sub {{ color: var(--accent2); font-size: 1rem; margin-top: 0.3rem; }}
  .hero .meta {{ color: var(--text-dim); font-size: 0.82rem; margin-top: 0.8rem; }}
  .stats-row {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
  .stat {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.8rem 1.2rem; min-width: 120px;
  }}
  .stat .val {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
  .stat .lbl {{ font-size: 0.7rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.08em; }}
  .arch {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.5rem; margin-bottom: 2rem;
  }}
  .arch h3 {{ color: var(--gold); margin-bottom: 1rem; font-size: 1rem; }}
  .arch-flow {{
    display: flex; align-items: center; justify-content: center; flex-wrap: wrap;
    gap: 0.4rem; padding: 1rem 0; margin-bottom: 1rem;
  }}
  .arch-node {{
    padding: 0.35rem 0.7rem; border-radius: 5px; font-size: 0.75rem; font-weight: 600;
    background: var(--surface2); border: 1px solid var(--border); color: var(--accent2);
  }}
  .arch-arrow {{ color: var(--text-dim); font-size: 1rem; }}
  .arch-desc {{ color: var(--text-dim); font-size: 0.85rem; line-height: 1.7; }}
  .arch-desc strong {{ color: var(--accent2); }}
  .code-section {{ margin-bottom: 3rem; }}
  .section-header {{
    background: var(--surface); border: 1px solid var(--border);
    border-bottom: none; border-radius: 8px 8px 0 0;
    padding: 1rem 1.2rem; display: flex; align-items: center;
    gap: 0.8rem; flex-wrap: wrap;
  }}
  .section-tag {{
    background: var(--accent); color: #fff; padding: 0.15rem 0.6rem;
    border-radius: 4px; font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em;
  }}
  .section-header h2 {{
    font-size: 1.1rem; font-family: 'Cascadia Code', 'Fira Code', monospace;
    color: var(--text); flex: 1;
  }}
  .section-desc {{ width: 100%; color: var(--text-dim); font-size: 0.82rem; margin-top: 0.3rem; }}
  .line-count {{ color: var(--text-dim); font-size: 0.75rem; }}
  pre {{
    background: var(--code-bg); border: 1px solid var(--border);
    border-top: none; border-radius: 0 0 8px 8px;
    padding: 1rem 1.2rem; overflow-x: auto; font-size: 0.82rem;
    line-height: 1.55; tab-size: 4; counter-reset: line;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', Consolas, monospace;
  }}
  code {{ color: var(--text); }}
  .footer {{
    padding: 2rem 0; border-top: 1px solid var(--border);
    color: var(--text-dim); font-size: 0.8rem; text-align: center;
  }}
  @media print {{
    .sidebar {{ display: none; }}
    .main {{ margin-left: 0; max-width: 100%; }}
    pre {{ white-space: pre-wrap; word-break: break-all; font-size: 0.7rem; }}
  }}
  @media (max-width: 768px) {{
    .sidebar {{ display: none; }}
    .main {{ margin-left: 0; padding: 1rem; }}
  }}
</style>
</head>
<body>
<div class="page">

  <nav class="sidebar">
    <div class="sidebar-title">A R I A</div>
    <div class="sidebar-subtitle">v0.1.0 &mdash; Peer Review<br>{html_mod.escape(now)}</div>
    {nav_html}
  </nav>

  <div class="main">

    <div class="hero">
      <h1>A R I A</h1>
      <p class="sub">Autonomous Reasoning &amp; Intuition Architecture &mdash; Source Code for Peer Review</p>
      <p class="meta">v0.1.0 pilot &middot; {html_mod.escape(now)} &middot; {len(FILES_ORDER)} modules &middot; {total_lines:,} lines</p>
    </div>

    <div class="stats-row">
      <div class="stat"><div class="val">{len(FILES_ORDER)}</div><div class="lbl">Modules</div></div>
      <div class="stat"><div class="val">{total_lines:,}</div><div class="lbl">Lines</div></div>
      <div class="stat"><div class="val">7</div><div class="lbl">Layers</div></div>
      <div class="stat"><div class="val">3</div><div class="lbl">Opt. Deps</div></div>
    </div>

    <div class="arch">
      <h3>Architecture Overview</h3>
      <div class="arch-flow">
        <span class="arch-node">L0: Ingest</span><span class="arch-arrow">&rarr;</span>
        <span class="arch-node">L1: Encode</span><span class="arch-arrow">&rarr;</span>
        <span class="arch-node">L2: Conjecture</span><span class="arch-arrow">&rarr;</span>
        <span class="arch-node">L3: Verify</span><span class="arch-arrow">&rarr;</span>
        <span class="arch-node">L4: Axiom / Lost NB</span><span class="arch-arrow">&rarr;</span>
        <span class="arch-node">L5: Synthesize</span><span class="arch-arrow">&rarr;</span>
        <span class="arch-node">L6: Iterate</span><span class="arch-arrow">&circlearrowleft;</span>
      </div>
      <div class="arch-desc">
        <p><strong>Core Philosophy:</strong> Ramanujan didn&rsquo;t prove first and discover second.
        He saw the pattern, stated it, then let others verify. ARIA mirrors this: a
        Conjecture Engine that leaps, a Verifier that kills bad ideas fast,
        and a Cross-Domain Synthesizer that finds the same pattern in multiple domains.</p>
        <br>
        <p><strong>Three Ramanujan Primitives:</strong></p>
        <p>&bull; <strong>Partition Shape Fingerprinting</strong> &mdash; Fit to Meinardus growth form f(n) ~ C&middot;n<sup>&kappa;</sup>&middot;e<sup>c&radic;n</sup>, extract signature (c, &kappa;)</p>
        <p>&bull; <strong>Modular Form Embedding</strong> &mdash; Project onto &eta;, &theta;, mock-&theta; basis; maintain orphan registry for uninterpreted projections</p>
        <p>&bull; <strong>Rogers-Ramanujan CF Depth</strong> &mdash; Continued fraction depth score: trivial (1&ndash;2), sweet spot (3&ndash;5), lost notebook (6+)</p>
        <br>
        <p><strong>Verification Telescoping (4 rounds):</strong> Numeric spot-check &rarr; Symbolic CAS &rarr; Adversarial falsifier &rarr; Domain expert sanity</p>
        <br>
        <p><strong>Key design:</strong> L = c&sup2;/8 + &kappa; serves as the universal selection parameter.
        Objects from different domains with matching L values are isomorphism candidates.
        Verified conjectures become axioms feeding the next generation;
        interesting failures go to the Lost Notebook for periodic re-evaluation.</p>
        <br>
        <p><strong>Dependencies:</strong> Python 3.10+ stdlib only. Optional: mpmath (high-precision), sympy (symbolic/primes), numpy.</p>
      </div>
    </div>

    {code_html}

    <div class="footer">
      ARIA v0.1.0 &middot; Autonomous Reasoning &amp; Intuition Architecture<br>
      Self-contained peer review package &mdash; all source code, no external resources required
    </div>
  </div>
</div>
</body>
</html>"""

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(document)

    size = os.path.getsize(OUT_PATH)
    print(f"Written: {OUT_PATH}")
    print(f"Size: {size:,} bytes ({size/1024:.1f} KB)")
    print(f"Modules: {len(FILES_ORDER)}, Lines: {total_lines:,}")


if __name__ == "__main__":
    main()
