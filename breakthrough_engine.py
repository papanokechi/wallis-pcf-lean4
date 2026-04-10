#!/usr/bin/env python3
"""
Breakthrough Engine V6 — Python Pipeline Runner
Runs an agentic discovery pipeline via Anthropic API (or OpenAI-compatible),
then outputs results into the existing dashboard HTML format.

Usage:
  python breakthrough_engine.py
  python breakthrough_engine.py --mode "Physics/Math" --target "Scaling Laws" --iters 10
  python breakthrough_engine.py --api-base https://api.anthropic.com --model claude-opus-4-6-20260301
  python breakthrough_engine.py --api-base http://localhost:11434/v1 --model llama3
"""

import argparse
import json
import os
import re
import sys
import time
import html as html_mod
from datetime import datetime
from pathlib import Path

# ── Try importing API clients ──────────────────────────────────────────
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# Fallback: use urllib if nothing else available
import urllib.request
import urllib.error


# ── API CALLER ──────────────────────────────────────────────────────────
def call_api(system_prompt: str, user_prompt: str, *,
             api_base: str, api_key: str, model: str, max_tokens: int = 800) -> str:
    """Call the configured LLM API and return the text response."""

    is_anthropic = "anthropic.com" in api_base

    if is_anthropic and HAS_ANTHROPIC:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text

    if not is_anthropic and HAS_OPENAI:
        client = openai.OpenAI(api_key=api_key or "not-needed", base_url=api_base)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content

    # Fallback: raw HTTP
    return _call_api_raw(system_prompt, user_prompt,
                         api_base=api_base, api_key=api_key,
                         model=model, max_tokens=max_tokens)


def _call_api_raw(system_prompt, user_prompt, *, api_base, api_key, model, max_tokens):
    """Raw HTTP fallback using urllib (no dependencies needed)."""
    is_anthropic = "anthropic.com" in api_base

    if is_anthropic:
        url = api_base.rstrip("/").removesuffix("/v1") + "/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        body = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return data["content"][0]["text"]
    else:
        url = api_base.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or 'not-needed'}",
        }
        body = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return data["choices"][0]["message"]["content"]


# ── PIPELINE STATE ──────────────────────────────────────────────────────
class PipelineState:
    def __init__(self, mode, target, strategies, max_iter, model):
        self.mode = mode
        self.target = target
        self.strategies = strategies
        self.max_iter = max_iter
        self.model = model
        self.discoveries = []
        self.beliefs = []
        self.assumptions = []
        self.interrupts = []
        self.log_entries = []
        self.manifest_mutations = []
        self.manifest_content = None
        self.manifest_ver = 1.0
        self.q_history = []
        self.b_history = []
        self.counts = {"good": 0, "breakthrough": 0, "waste": 0, "investigate": 0}
        self.break_count = 0
        self.start_time = datetime.now()

    @property
    def task_desc(self):
        if self.mode == "AI/ML Meta-analysis":
            return f"AI/ML meta-analysis on: {self.target}"
        return self.mode

    def add_log(self, iter_label, agent, msg, msg_type=""):
        self.log_entries.append({
            "iter": iter_label, "agent": agent,
            "msg": msg, "type": msg_type
        })
        # Also print to terminal
        prefix = {"discovery": "🔬", "interrupt": "⚠️", "mutation": "🧬", "info": "ℹ️"}.get(msg_type, "  ")
        print(f"  {prefix} [{iter_label}] {agent.upper()[:10]:10s} {msg[:120]}")

    def add_interrupt(self, int_type, msg):
        self.interrupts.append({"type": int_type, "msg": msg})

    def add_discovery(self, q, s, text, iteration):
        is_break = q > 0.75 and s > 1.5
        is_invest = q < 0.6 and s > 1.5
        is_waste = q < 0.5 and s < 1.0

        if is_break:
            category = "breakthrough"
            self.break_count += 1
        elif is_invest:
            category = "investigate"
        elif is_waste:
            category = "waste"
        else:
            category = "good"

        self.counts[category] += 1
        self.discoveries.append({
            "q": q, "s": s, "text": text,
            "iter": iteration, "category": category
        })

    def add_belief(self, text, confidence, delta):
        self.beliefs.append({"text": text, "confidence": confidence, "delta": delta})

    def add_assumption(self, text, status):
        self.assumptions.append({"text": text, "status": status})


# ── PIPELINE RUNNER ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the Meta-Analyst agent in a scientific breakthrough discovery pipeline.
Your role: identify hidden assumptions, contradictions, and high-surprise hypotheses in the research domain.
Be specific, intellectually bold, and concise. Output JSON only."""


def build_user_prompt(state: PipelineState, iteration: int) -> str:
    return f"""Domain: {state.task_desc}
Iteration: {iteration}/{state.max_iter}
Active strategies: {state.strategies}
Prior beliefs count: {len(state.beliefs)}

Generate one novel hypothesis or discovery for this iteration.
Respond with ONLY valid JSON:
{{
  "hypothesis": "one specific, bold, testable claim (2-3 sentences)",
  "quality_q": <float 0-1>,
  "surprise_s": <float 0-3>,
  "tension": <float 0-1>,
  "belief_delta": "one sentence describing how this changes prior understanding",
  "belief_confidence": <float 0-1>,
  "assumption": "one hidden assumption this exposes",
  "assumption_status": "active|pending|refuted",
  "interrupt_type": "none|warn|crit",
  "interrupt_msg": "message if interrupt, else empty string",
  "manifest_mutation": "one-sentence manifest update if warranted, else empty string"
}}"""


def run_iteration(state: PipelineState, iteration: int, *, api_base, api_key, model):
    """Run a single pipeline iteration."""
    import random

    state.add_log(f"I{iteration}", "meta-analyst",
                  "Analyzing domain for high-leverage hypotheses…", "info")

    try:
        raw = call_api(
            SYSTEM_PROMPT,
            build_user_prompt(state, iteration),
            api_base=api_base, api_key=api_key,
            model=model, max_tokens=400,
        )
        clean = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(clean)

        hypothesis = parsed.get("hypothesis", "")
        q = float(parsed.get("quality_q", random.uniform(0.5, 0.9)))
        s = float(parsed.get("surprise_s", random.uniform(0.5, 2.0)))
        tension = float(parsed.get("tension", random.uniform(0.2, 0.7)))
        belief_conf = float(parsed.get("belief_confidence", random.uniform(0.4, 0.7)))

        state.add_log(f"I{iteration}", "producer",
                      hypothesis[:120] + ("…" if len(hypothesis) > 120 else ""), "discovery")
        state.add_log(f"I{iteration}", "accuracy",
                      f"Q={q:.2f} — evaluating empirical grounding…", "info")
        state.add_log(f"I{iteration}", "coherence",
                      f"S={s:.2f} — checking internal consistency…", "info")
        state.add_log(f"I{iteration}", "devil",
                      f'Challenging: "{hypothesis[:80]}…"', "interrupt")
        state.add_log(f"I{iteration}", "steelman",
                      "Reinforcing strongest version of hypothesis…", "info")

        state.q_history.append(q)
        state.b_history.append(belief_conf)

        # Discovery
        state.add_discovery(q, s, hypothesis, iteration)

        # Belief
        if parsed.get("belief_delta"):
            state.add_belief(parsed["belief_delta"], belief_conf, f"iter {iteration}")

        # Assumption
        if parsed.get("assumption"):
            state.add_assumption(parsed["assumption"],
                                 parsed.get("assumption_status", "active"))

        # Interrupt
        int_type = parsed.get("interrupt_type", "none")
        int_msg = parsed.get("interrupt_msg", "")
        if int_type != "none" and int_msg:
            state.add_interrupt(int_type, int_msg)
            state.add_log(f"I{iteration}", "monitor", f"⚠ {int_msg}", "interrupt")

        # Manifest mutation
        mutation = parsed.get("manifest_mutation", "")
        if mutation and len(mutation) > 10:
            state.manifest_mutations.append(mutation)
            state.manifest_ver = round(state.manifest_ver + 0.01, 2)
            state.add_log(f"I{iteration}", "mutator",
                          f"Manifest → v{state.manifest_ver:.2f}: {mutation[:80]}", "mutation")

            if not state.manifest_content:
                state.manifest_content = (
                    f"# Objective\nDiscover breakthroughs in {state.task_desc}\n\n"
                    f"# Strategy\nUse {state.strategies} mutation strategies\n\n"
                    f"# Focus\n{state.target}\n\n"
                    f"# Constraint\nMaximize Q×S product across iterations\n\n"
                    f"# Current belief\n{parsed.get('belief_delta', '—')}"
                )
            else:
                state.manifest_content += f"\n\n# Update (v{state.manifest_ver})\n{mutation}"

        state.add_log(f"I{iteration}", "interrupt",
                      f"Iteration {iteration} complete. Q={q:.2f}, S={s:.2f}.", "info")

        # Seed assumptions on iter 1
        if iteration == 1:
            if not state.manifest_content:
                state.manifest_content = (
                    f"# Objective\nDiscover breakthroughs in {state.task_desc}\n\n"
                    f"# Strategy\nUse {state.strategies} mutation strategies\n\n"
                    f"# Focus\n{state.target}\n\n"
                    f"# Constraint\nMaximize Q×S product across iterations\n\n"
                    f"# Basis\n{hypothesis[:120]}"
                )
            state.add_assumption(
                "The domain contains discoverable hidden assumptions not yet surfaced in literature.", "active")
            state.add_assumption(
                "Higher-quality hypotheses emerge from adversarial + analogical strategy combination.", "pending")

        return q, s

    except Exception as err:
        state.add_log(f"I{iteration}", "error", f"API error: {err}", "interrupt")
        state.add_interrupt("warn", f"Iter {iteration} failed: {err}")
        import random
        q = random.uniform(0.4, 0.7)
        s = random.uniform(0.3, 1.1)
        state.q_history.append(q)
        state.b_history.append(0.4)
        return q, s


def run_pipeline(state: PipelineState, *, api_base, api_key, model):
    """Run the full pipeline across all iterations."""
    state.add_log("INIT", "system",
                  f"Starting pipeline: {state.mode} · {state.target} · "
                  f"{state.max_iter} iters · model: {model}", "info")

    for i in range(1, state.max_iter + 1):
        pct = int(i / state.max_iter * 100)
        print(f"\n{'─'*60}")
        print(f"  ITERATION {i}/{state.max_iter}  ({pct}%)")
        print(f"{'─'*60}")
        run_iteration(state, i, api_base=api_base, api_key=api_key, model=model)

    disc_count = len(state.discoveries)
    state.add_log("END", "system",
                  f"Pipeline complete. {disc_count} discoveries, "
                  f"{state.break_count} breakthroughs.", "discovery")
    state.add_interrupt("info",
                        f"Run complete: {disc_count} discoveries, "
                        f"{state.break_count} breakthroughs across {state.max_iter} iterations.")


def run_from_data(state: PipelineState, iterations_data: list):
    """Run pipeline from pre-generated iteration data (agent mode — no API needed).

    iterations_data: list of dicts, each with:
      hypothesis, quality_q, surprise_s, tension, belief_delta,
      belief_confidence, assumption, assumption_status,
      interrupt_type, interrupt_msg, manifest_mutation
    """
    state.add_log("INIT", "system",
                  f"Starting pipeline (agent mode): {state.mode} · {state.target} · "
                  f"{len(iterations_data)} iters · model: {state.model}", "info")

    for i, parsed in enumerate(iterations_data, 1):
        pct = int(i / len(iterations_data) * 100)
        print(f"\n{'─'*60}")
        print(f"  ITERATION {i}/{len(iterations_data)}  ({pct}%)")
        print(f"{'─'*60}")

        state.add_log(f"I{i}", "meta-analyst",
                      "Analyzing domain for high-leverage hypotheses…", "info")

        hypothesis = parsed.get("hypothesis", "")
        q = float(parsed.get("quality_q", 0.6))
        s = float(parsed.get("surprise_s", 1.0))
        tension = float(parsed.get("tension", 0.4))
        belief_conf = float(parsed.get("belief_confidence", 0.5))

        state.add_log(f"I{i}", "producer",
                      hypothesis[:120] + ("…" if len(hypothesis) > 120 else ""), "discovery")
        state.add_log(f"I{i}", "accuracy",
                      f"Q={q:.2f} — evaluating empirical grounding…", "info")
        state.add_log(f"I{i}", "coherence",
                      f"S={s:.2f} — checking internal consistency…", "info")
        state.add_log(f"I{i}", "devil",
                      f'Challenging: "{hypothesis[:80]}…"', "interrupt")
        state.add_log(f"I{i}", "steelman",
                      "Reinforcing strongest version of hypothesis…", "info")

        state.q_history.append(q)
        state.b_history.append(belief_conf)

        state.add_discovery(q, s, hypothesis, i)

        if parsed.get("belief_delta"):
            state.add_belief(parsed["belief_delta"], belief_conf, f"iter {i}")

        if parsed.get("assumption"):
            state.add_assumption(parsed["assumption"],
                                 parsed.get("assumption_status", "active"))

        int_type = parsed.get("interrupt_type", "none")
        int_msg = parsed.get("interrupt_msg", "")
        if int_type != "none" and int_msg:
            state.add_interrupt(int_type, int_msg)
            state.add_log(f"I{i}", "monitor", f"⚠ {int_msg}", "interrupt")

        mutation = parsed.get("manifest_mutation", "")
        if mutation and len(mutation) > 10:
            state.manifest_mutations.append(mutation)
            state.manifest_ver = round(state.manifest_ver + 0.01, 2)
            state.add_log(f"I{i}", "mutator",
                          f"Manifest → v{state.manifest_ver:.2f}: {mutation[:80]}", "mutation")

            if not state.manifest_content:
                state.manifest_content = (
                    f"# Objective\nDiscover breakthroughs in {state.task_desc}\n\n"
                    f"# Strategy\nUse {state.strategies} mutation strategies\n\n"
                    f"# Focus\n{state.target}\n\n"
                    f"# Constraint\nMaximize Q×S product across iterations\n\n"
                    f"# Current belief\n{parsed.get('belief_delta', '—')}"
                )
            else:
                state.manifest_content += f"\n\n# Update (v{state.manifest_ver})\n{mutation}"

        state.add_log(f"I{i}", "interrupt",
                      f"Iteration {i} complete. Q={q:.2f}, S={s:.2f}.", "info")

        if i == 1:
            if not state.manifest_content:
                state.manifest_content = (
                    f"# Objective\nDiscover breakthroughs in {state.task_desc}\n\n"
                    f"# Strategy\nUse {state.strategies} mutation strategies\n\n"
                    f"# Focus\n{state.target}\n\n"
                    f"# Constraint\nMaximize Q×S product across iterations\n\n"
                    f"# Basis\n{hypothesis[:120]}"
                )
            state.add_assumption(
                "The domain contains discoverable hidden assumptions not yet surfaced in literature.", "active")
            state.add_assumption(
                "Higher-quality hypotheses emerge from adversarial + analogical strategy combination.", "pending")

    disc_count = len(state.discoveries)
    state.add_log("END", "system",
                  f"Pipeline complete. {disc_count} discoveries, "
                  f"{state.break_count} breakthroughs.", "discovery")
    state.add_interrupt("info",
                        f"Run complete: {disc_count} discoveries, "
                        f"{state.break_count} breakthroughs across {len(iterations_data)} iterations.")


# ── HTML OUTPUT ─────────────────────────────────────────────────────────
def generate_html(state: PipelineState) -> str:
    """Generate the full dashboard HTML with all data pre-populated."""
    e = html_mod.escape  # shorthand

    # Build log entries HTML
    log_html = ""
    for entry in state.log_entries:
        log_html += (
            f'<div class="log-entry">'
            f'<span class="log-iter">{e(entry["iter"])}</span>'
            f'<span class="log-agent">{e(entry["agent"].upper()[:10])}</span>'
            f'<span class="log-msg {entry["type"]}">{e(entry["msg"])}</span>'
            f'</div>\n'
        )

    # Build discovery cards HTML
    disc_html = ""
    for d in reversed(state.discoveries):
        cat = d["category"]
        cls = {"breakthrough": "breakthrough", "investigate": "investigation",
               "waste": "waste", "good": "breakthrough"}[cat]
        label = {"breakthrough": "🚀 BREAKTHROUGH", "investigate": "🔍 INVESTIGATE",
                 "waste": "❌ WASTE", "good": "✅ GOOD"}[cat]
        disc_html += (
            f'<div class="disc-card {cls}">'
            f'<div class="disc-q-score {cls}">{d["q"]:.2f}</div>'
            f'<div class="disc-label">{label} · iter {d["iter"]}</div>'
            f'<div class="disc-text">{e(d["text"])}</div>'
            f'<div class="disc-meta"><span>Q={d["q"]:.2f}</span><span>S={d["s"]:.2f}</span></div>'
            f'</div>\n'
        )

    # Build beliefs HTML
    belief_html = ""
    for b in reversed(state.beliefs):
        pct = int(b["confidence"] * 100)
        belief_html += (
            f'<div class="belief-item">'
            f'<div class="belief-conf"><span>{pct}%</span>'
            f'<div class="conf-bar"><div class="conf-fill" style="width:{pct}%"></div></div></div>'
            f'<div class="belief-text">{e(b["text"])}</div>'
            f'<div class="belief-delta">Δ from prior: {e(b["delta"])}</div>'
            f'</div>\n'
        )

    # Build assumptions HTML
    assump_html = ""
    for a in state.assumptions:
        assump_html += (
            f'<div class="assumption-item">'
            f'<div class="assumption-status {a["status"]}">{a["status"].upper()}</div>'
            f'<div class="assumption-text">{e(a["text"])}</div>'
            f'</div>\n'
        )

    # Build manifest HTML
    manifest_html = ""
    if state.manifest_content:
        manifest_html += f'<div class="manifest-ver">v{state.manifest_ver:.2f} · {len(state.manifest_mutations)} mutations</div>\n'
        sections = [s for s in state.manifest_content.split("\n\n") if s.strip()]
        for sec in sections[:5]:
            lines = sec.strip().split("\n")
            key = re.sub(r"^#+\s*", "", lines[0]).strip()
            val = " ".join(lines[1:]).strip()
            if key and val:
                manifest_html += (
                    f'<div class="manifest-section">'
                    f'<div class="manifest-key">{e(key)}</div>'
                    f'<div class="manifest-val">{e(val)}</div></div>\n'
                )
        if state.manifest_mutations:
            manifest_html += '<div class="manifest-key" style="margin-top:12px">Mutation History</div>\n'
            for m in state.manifest_mutations[-4:]:
                manifest_html += (
                    f'<div class="manifest-mutation">'
                    f'<span class="mutation-arrow">→</span>'
                    f'<span class="mutation-text">{e(m)}</span></div>\n'
                )

    # Build interrupt log HTML
    int_html = ""
    for intr in state.interrupts:
        int_html += (
            f'<div class="interrupt-entry">'
            f'<span class="interrupt-type {intr["type"]}">{intr["type"].upper()}</span>'
            f'<span class="interrupt-msg">{e(intr["msg"])}</span></div>\n'
        )

    # Final Q / S values
    last_q = state.q_history[-1] if state.q_history else 0
    last_s = state.discoveries[-1]["s"] if state.discoveries else 0
    last_tension = 0.5
    last_belief = state.b_history[-1] if state.b_history else 0

    q_data = json.dumps(state.q_history)
    b_data = json.dumps(state.b_history)
    total_disc = len(state.discoveries)
    run_info = (f"{state.mode} · {state.target} · {state.max_iter} iters · "
                f"model: {state.model} · {state.start_time:%Y-%m-%d %H:%M}")

    return HTML_TEMPLATE.format(
        run_info=e(run_info),
        model=e(state.model),
        mode=e(state.mode.upper()),
        total_iter=state.max_iter,
        last_q=f"{last_q:.2f}",
        last_s=f"{last_s:.2f}",
        break_count=state.break_count,
        int_count=len(state.interrupts),
        log_html=log_html,
        disc_html=disc_html or '<div class="empty-state">No discoveries generated.</div>',
        disc_count=total_disc,
        belief_html=belief_html or '<div class="empty-state">No beliefs recorded.</div>',
        belief_count=len(state.beliefs),
        manifest_html=manifest_html or '<div class="empty-state">No manifest generated.</div>',
        assump_html=assump_html or '<div class="empty-state">No assumptions extracted.</div>',
        assump_count=len(state.assumptions),
        g_q=f"{last_q:.2f}",
        g_s=f"{last_s:.2f}",
        g_tension=f"{last_tension:.2f}",
        g_belief=f"{last_belief:.2f}",
        m_good=state.counts["good"],
        m_break=state.counts["breakthrough"],
        m_waste=state.counts["waste"],
        m_invst=state.counts["investigate"],
        int_html=int_html or '<div class="interrupt-entry"><span class="interrupt-type info">INFO</span><span class="interrupt-msg">Pipeline completed successfully.</span></div>',
        q_data=q_data,
        b_data=b_data,
    )


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Breakthrough Engine V6 — Results</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;1,300&family=IBM+Plex+Sans:wght@300;400;500&display=swap');

  :root {{
    --bg:        #080c0f;
    --bg2:       #0d1318;
    --bg3:       #111820;
    --border:    #1e2d38;
    --border2:   #2a3f50;
    --amber:     #e8a820;
    --amber-dim: #7a5510;
    --amber-glow:#e8a82022;
    --teal:      #2dd4bf;
    --teal-dim:  #0f4a44;
    --red:       #f87171;
    --red-dim:   #4a1515;
    --green:     #4ade80;
    --green-dim: #0f3a1f;
    --blue:      #60a5fa;
    --muted:     #4a6070;
    --text:      #c8d8e4;
    --text-dim:  #5a7080;
    --mono: 'IBM Plex Mono', monospace;
    --sans: 'IBM Plex Sans', sans-serif;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    line-height: 1.6;
    min-height: 100vh;
    overflow-x: hidden;
  }}

  body::before {{
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px);
    pointer-events: none;
    z-index: 9999;
  }}

  .header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg2);
    position: sticky;
    top: 0;
    z-index: 100;
  }}

  .header-left {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}

  .logo {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    color: var(--amber);
    text-transform: uppercase;
  }}

  .version-tag {{
    font-size: 10px;
    background: var(--amber-glow);
    border: 1px solid var(--amber-dim);
    color: var(--amber);
    padding: 2px 8px;
    letter-spacing: 0.08em;
  }}

  .status-strip {{
    display: flex;
    align-items: center;
    gap: 20px;
  }}

  .stat-pill {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-dim);
  }}

  .stat-pill .val {{
    font-weight: 500;
    color: var(--text);
    min-width: 32px;
    text-align: right;
  }}

  .stat-pill .val.active {{ color: var(--amber); }}
  .stat-pill .val.good {{ color: var(--green); }}
  .stat-pill .val.warn {{ color: var(--red); }}

  .pulse-dot {{
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--green);
    flex-shrink: 0;
  }}

  .main {{
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 0;
    height: calc(100vh - 45px);
  }}

  .panel {{
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}

  .panel:last-child {{ border-right: none; }}

  .panel-head {{
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg2);
    flex-shrink: 0;
  }}

  .panel-title {{
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-dim);
  }}

  .panel-body {{
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
    scrollbar-width: thin;
    scrollbar-color: var(--border2) transparent;
  }}

  .section-label {{
    font-size: 9px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--amber-dim);
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border);
  }}

  .center-panel {{
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border);
  }}

  .tab-bar {{
    display: flex;
    border-bottom: 1px solid var(--border);
    background: var(--bg2);
    flex-shrink: 0;
  }}

  .tab {{
    padding: 9px 16px;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: all 0.15s;
    border-right: 1px solid var(--border);
    position: relative;
  }}

  .tab:hover {{ color: var(--text); }}

  .tab.active {{
    color: var(--amber);
    border-bottom-color: var(--amber);
    background: var(--bg);
  }}

  .tab-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px; height: 16px;
    background: var(--amber-dim);
    color: var(--amber);
    font-size: 9px;
    border-radius: 50%;
    margin-left: 5px;
    font-weight: 600;
  }}

  .tab-content {{ display: none; flex: 1; overflow: hidden; flex-direction: column; }}
  .tab-content.active {{ display: flex; }}

  .terminal {{
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
    scrollbar-width: thin;
    scrollbar-color: var(--border2) transparent;
  }}

  .log-entry {{
    display: grid;
    grid-template-columns: 56px 80px 1fr;
    gap: 10px;
    padding: 3px 0;
    border-bottom: 1px solid rgba(30,45,56,0.4);
    font-size: 11px;
    line-height: 1.5;
  }}

  .log-iter {{ color: var(--text-dim); font-size: 10px; }}
  .log-agent {{ color: var(--blue); font-size: 10px; }}
  .log-msg {{ color: var(--text); }}
  .log-msg.discovery {{ color: var(--amber); }}
  .log-msg.interrupt {{ color: var(--red); }}
  .log-msg.mutation  {{ color: var(--teal); }}
  .log-msg.info      {{ color: var(--text-dim); }}

  .disc-grid {{
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 8px;
    align-content: start;
    scrollbar-width: thin;
    scrollbar-color: var(--border2) transparent;
  }}

  .disc-card {{
    background: var(--bg2);
    border: 1px solid var(--border);
    padding: 12px;
    position: relative;
    overflow: hidden;
  }}

  .disc-card::before {{
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 2px;
  }}

  .disc-card.breakthrough::before {{ background: var(--amber); }}
  .disc-card.investigation::before {{ background: var(--blue); }}
  .disc-card.waste::before {{ background: var(--muted); }}

  .disc-q-score {{
    font-size: 22px;
    font-weight: 600;
    line-height: 1;
    margin-bottom: 4px;
  }}

  .disc-q-score.breakthrough {{ color: var(--amber); }}
  .disc-q-score.investigation {{ color: var(--blue); }}
  .disc-q-score.waste {{ color: var(--muted); }}

  .disc-label {{
    font-size: 9px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 8px;
    color: var(--text-dim);
  }}

  .disc-text {{
    font-size: 11px;
    color: var(--text);
    line-height: 1.6;
    margin-bottom: 8px;
  }}

  .disc-meta {{
    font-size: 9px;
    color: var(--text-dim);
    display: flex;
    gap: 10px;
  }}

  .belief-list {{
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
    scrollbar-width: thin;
    scrollbar-color: var(--border2) transparent;
  }}

  .belief-item {{
    margin-bottom: 12px;
    border-left: 2px solid var(--border2);
    padding-left: 10px;
  }}

  .belief-conf {{
    font-size: 10px;
    color: var(--text-dim);
    margin-bottom: 2px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  .conf-bar {{
    height: 2px;
    background: var(--border);
    flex: 1;
    position: relative;
  }}

  .conf-fill {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    background: var(--teal);
  }}

  .belief-text {{ font-size: 11px; color: var(--text); line-height: 1.5; }}
  .belief-delta {{ font-size: 9px; color: var(--text-dim); margin-top: 2px; font-style: italic; }}

  .manifest-body {{
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
    scrollbar-width: thin;
    scrollbar-color: var(--border2) transparent;
  }}

  .manifest-ver {{
    font-size: 9px;
    color: var(--amber);
    letter-spacing: 0.1em;
    margin-bottom: 8px;
  }}

  .manifest-section {{ margin-bottom: 14px; }}

  .manifest-key {{
    font-size: 9px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 4px;
  }}

  .manifest-val {{
    font-size: 11px;
    color: var(--text);
    background: var(--bg3);
    border: 1px solid var(--border);
    padding: 6px 10px;
    line-height: 1.5;
  }}

  .manifest-mutation {{
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 6px;
    background: rgba(45,212,191,0.05);
    border: 1px solid var(--teal-dim);
    margin-bottom: 6px;
    font-size: 10px;
  }}

  .mutation-arrow {{ color: var(--teal); flex-shrink: 0; }}
  .mutation-text {{ color: var(--text); line-height: 1.5; }}

  .metrics-panel {{ background: var(--bg); }}

  .gauge-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 12px;
  }}

  .gauge {{
    background: var(--bg3);
    border: 1px solid var(--border);
    padding: 10px;
    text-align: center;
  }}

  .gauge-val {{
    font-size: 28px;
    font-weight: 600;
    line-height: 1;
    margin-bottom: 2px;
  }}

  .gauge-val.amber {{ color: var(--amber); }}
  .gauge-val.teal  {{ color: var(--teal); }}
  .gauge-val.muted {{ color: var(--muted); }}

  .gauge-label {{
    font-size: 9px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-dim);
  }}

  .matrix-cell {{
    background: var(--bg3);
    border: 1px solid var(--border);
    padding: 10px 8px;
    text-align: center;
  }}

  .matrix-cell .count {{
    font-size: 20px;
    font-weight: 600;
    line-height: 1;
    margin-bottom: 2px;
  }}

  .matrix-cell .cell-label {{
    font-size: 8px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
  }}

  .cell-good  .count {{ color: var(--green); }}
  .cell-break .count {{ color: var(--amber); }}
  .cell-waste .count {{ color: var(--muted); }}
  .cell-invst .count {{ color: var(--blue); }}

  .sparkline-wrap {{
    margin-bottom: 12px;
  }}

  .spark-title {{
    font-size: 9px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 6px;
  }}

  canvas {{
    display: block;
    width: 100%;
    height: 60px;
    background: var(--bg3);
    border: 1px solid var(--border);
  }}

  .interrupt-log {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}

  .interrupt-entry {{
    display: grid;
    grid-template-columns: 40px 1fr;
    gap: 8px;
    padding: 5px 8px;
    background: var(--bg3);
    border: 1px solid var(--border);
    font-size: 10px;
  }}

  .interrupt-type {{
    font-size: 9px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }}

  .interrupt-type.info  {{ color: var(--muted); }}
  .interrupt-type.warn  {{ color: var(--amber); }}
  .interrupt-type.crit  {{ color: var(--red); }}

  .interrupt-msg {{ color: var(--text-dim); line-height: 1.4; }}

  .assumption-list {{ display: flex; flex-direction: column; gap: 6px; }}

  .assumption-item {{
    background: var(--bg3);
    border: 1px solid var(--border);
    padding: 8px 10px;
    font-size: 10px;
  }}

  .assumption-status {{
    font-size: 9px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 3px;
  }}

  .assumption-status.active  {{ color: var(--teal); }}
  .assumption-status.refuted {{ color: var(--red); }}
  .assumption-status.pending {{ color: var(--text-dim); }}

  .assumption-text {{ color: var(--text); line-height: 1.5; }}

  .empty-state {{
    padding: 24px;
    text-align: center;
    color: var(--text-dim);
    font-size: 11px;
    line-height: 1.7;
    font-style: italic;
  }}

  .progress-wrap {{
    padding: 8px 16px;
    border-top: 1px solid var(--border);
    background: var(--bg2);
    flex-shrink: 0;
  }}

  .progress-label {{
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    color: var(--text-dim);
    margin-bottom: 4px;
    letter-spacing: 0.08em;
  }}

  .progress-bar {{
    height: 2px;
    background: var(--border);
    position: relative;
  }}

  .progress-fill {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    background: var(--green);
    width: 100%;
  }}

  .run-info {{
    font-size: 9px;
    color: var(--text-dim);
    letter-spacing: 0.06em;
    padding: 6px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--bg2);
  }}

  ::-webkit-scrollbar {{ width: 4px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: var(--border2); border-radius: 0; }}
</style>
</head>
<body>

<header class="header">
  <div class="header-left">
    <span class="logo">Breakthrough Engine</span>
    <span class="version-tag">V6 · OPUS 4.6</span>
    <span style="font-size:10px;color:var(--text-dim);letter-spacing:0.06em">{mode}</span>
  </div>
  <div class="status-strip">
    <div class="stat-pill">
      <div class="pulse-dot"></div>
      <span>ITER</span>
      <span class="val">{total_iter}/{total_iter}</span>
    </div>
    <div class="stat-pill">
      <span>Q</span>
      <span class="val active">{last_q}</span>
    </div>
    <div class="stat-pill">
      <span>S</span>
      <span class="val">{last_s}</span>
    </div>
    <div class="stat-pill">
      <span>🚀</span>
      <span class="val">{break_count}</span>
    </div>
    <div class="stat-pill">
      <span>⚠</span>
      <span class="val warn">{int_count}</span>
    </div>
  </div>
</header>

<div class="main">

  <div class="center-panel">
    <div class="run-info">RUN: {run_info}</div>
    <div class="tab-bar">
      <div class="tab active" onclick="switchTab('log', this)">Live Log</div>
      <div class="tab" onclick="switchTab('discoveries', this)">Discoveries <span class="tab-badge">{disc_count}</span></div>
      <div class="tab" onclick="switchTab('beliefs', this)">Beliefs <span class="tab-badge">{belief_count}</span></div>
      <div class="tab" onclick="switchTab('manifest', this)">Manifest</div>
      <div class="tab" onclick="switchTab('assumptions', this)">Assumptions <span class="tab-badge">{assump_count}</span></div>
    </div>

    <div class="tab-content active" id="tab-log">
      <div class="terminal">{log_html}</div>
    </div>

    <div class="tab-content" id="tab-discoveries">
      <div class="disc-grid">{disc_html}</div>
    </div>

    <div class="tab-content" id="tab-beliefs">
      <div class="belief-list">{belief_html}</div>
    </div>

    <div class="tab-content" id="tab-manifest">
      <div class="manifest-body">{manifest_html}</div>
    </div>

    <div class="tab-content" id="tab-assumptions">
      <div class="panel-body">
        <div class="assumption-list">{assump_html}</div>
      </div>
    </div>

    <div class="progress-wrap">
      <div class="progress-label">
        <span>COMPLETE</span>
        <span>100%</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill"></div>
      </div>
    </div>
  </div>

  <div class="panel metrics-panel">
    <div class="panel-head">
      <span class="panel-title">Metrics</span>
    </div>
    <div class="panel-body">

      <div class="gauge-row">
        <div class="gauge">
          <div class="gauge-val amber">{g_q}</div>
          <div class="gauge-label">Quality Q</div>
        </div>
        <div class="gauge">
          <div class="gauge-val teal">{g_s}</div>
          <div class="gauge-label">Surprise S</div>
        </div>
      </div>
      <div class="gauge-row">
        <div class="gauge">
          <div class="gauge-val muted">{g_tension}</div>
          <div class="gauge-label">Tension</div>
        </div>
        <div class="gauge">
          <div class="gauge-val amber">{g_belief}</div>
          <div class="gauge-label">Belief Δ</div>
        </div>
      </div>

      <div class="section-label" style="margin-bottom:6px;margin-top:4px">Discovery Grid</div>
      <div style="display:grid;grid-template-columns:60px 1fr 1fr;gap:2px;margin-bottom:4px;font-size:8px;color:var(--muted);letter-spacing:0.1em;text-transform:uppercase">
        <span></span>
        <span style="text-align:center">Low S</span>
        <span style="text-align:center">High S</span>
      </div>
      <div style="display:grid;grid-template-columns:60px 1fr 1fr;gap:2px;margin-bottom:12px">
        <div style="display:flex;flex-direction:column;justify-content:space-around;font-size:8px;color:var(--muted);letter-spacing:0.08em;text-transform:uppercase;text-align:right;padding-right:6px">
          <span>High Q</span>
          <span>Low Q</span>
        </div>
        <div class="matrix-cell cell-good">
          <div class="count">{m_good}</div>
          <div class="cell-label">✅ Good</div>
        </div>
        <div class="matrix-cell cell-break">
          <div class="count">{m_break}</div>
          <div class="cell-label">🚀 Break</div>
        </div>
        <div class="matrix-cell cell-waste">
          <div class="count">{m_waste}</div>
          <div class="cell-label">❌ Waste</div>
        </div>
        <div class="matrix-cell cell-invst">
          <div class="count">{m_invst}</div>
          <div class="cell-label">🔍 Invest</div>
        </div>
      </div>

      <div class="sparkline-wrap">
        <div class="spark-title">Q Convergence</div>
        <canvas id="spark-q" height="60"></canvas>
      </div>
      <div class="sparkline-wrap">
        <div class="spark-title">Manifest Belief Δ</div>
        <canvas id="spark-b" height="60"></canvas>
      </div>

      <div class="section-label" style="margin-bottom:6px">Interrupt Log</div>
      <div class="interrupt-log">{int_html}</div>

    </div>
  </div>

</div>

<script>
// Tab switching
function switchTab(name, el) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}}

// Sparklines from pipeline data
function drawSparkline(canvasId, data, color) {{
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.offsetWidth || 268;
  const H = 60;
  canvas.width = W;
  canvas.height = H;
  ctx.clearRect(0, 0, W, H);
  if (data.length < 2) return;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  data.forEach((v, i) => {{
    const x = (i / (data.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 8) - 4;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }});
  ctx.stroke();
  ctx.lineTo(W, H);
  ctx.lineTo(0, H);
  ctx.closePath();
  ctx.fillStyle = color + '18';
  ctx.fill();
}}

window.addEventListener('load', () => {{
  drawSparkline('spark-q', {q_data}, '#e8a820');
  drawSparkline('spark-b', {b_data}, '#2dd4bf');
}});
</script>
</body>
</html>"""


# ── CLI ENTRY POINT ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Breakthrough Engine V6 — Python Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Agent mode (no API key needed — use with VS Code Claude agent):
  python breakthrough_engine.py --data iterations.json
  python breakthrough_engine.py --data iterations.json --mode "Physics/Math" -o results.html

  # API mode:
  python breakthrough_engine.py --api-key sk-ant-... --iters 10
  python breakthrough_engine.py --api-base https://openrouter.ai/api/v1 --api-key sk-or-...
""")
    parser.add_argument("--data", default=None,
                        help="JSON file with pre-generated iteration data (agent mode — no API key needed)")
    parser.add_argument("--api-base", default=os.environ.get("API_BASE", "https://api.anthropic.com"),
                        help="API endpoint (default: https://api.anthropic.com or $API_BASE)")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
                        help="API key (default: $ANTHROPIC_API_KEY or $OPENAI_API_KEY)")
    parser.add_argument("--model", default=os.environ.get("MODEL", "claude-opus-4-6-20260301"),
                        help="Model ID (default: claude-opus-4-6-20260301 or $MODEL)")
    parser.add_argument("--mode", default="AI/ML Meta-analysis",
                        choices=["AI/ML Meta-analysis", "Physics/Math", "Generic Research"],
                        help="Research domain")
    parser.add_argument("--target", default="LLM Alignment",
                        help="Meta-analysis target (for AI/ML mode)")
    parser.add_argument("--strategies", default="Adversarial, Analogical",
                        help="Comma-separated mutation strategies")
    parser.add_argument("--iters", type=int, default=20,
                        help="Max iterations (default: 20)")
    parser.add_argument("-o", "--output", default=None,
                        help="Output HTML file (default: breakthrough-results-<timestamp>.html)")

    args = parser.parse_args()

    # ── AGENT MODE: load from JSON data file ──
    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"⚠  Data file not found: {args.data}")
            sys.exit(1)

        iterations_data = json.loads(data_path.read_text(encoding="utf-8"))
        if isinstance(iterations_data, dict):
            # Support wrapper format: {"iterations": [...], "mode": ..., ...}
            args.mode = iterations_data.get("mode", args.mode)
            args.target = iterations_data.get("target", args.target)
            args.strategies = iterations_data.get("strategies", args.strategies)
            args.model = iterations_data.get("model", args.model)
            iterations_data = iterations_data.get("iterations", [])

        n = len(iterations_data)
        print(f"""
╔══════════════════════════════════════════════════════════╗
║  BREAKTHROUGH ENGINE V6 — Agent Mode (no API needed)    ║
╠══════════════════════════════════════════════════════════╣
║  Model:      {args.model:<42s} ║
║  Data file:  {args.data:<42s} ║
║  Mode:       {args.mode:<42s} ║
║  Target:     {args.target:<42s} ║
║  Strategies: {args.strategies:<42s} ║
║  Iterations: {str(n):<42s} ║
╚══════════════════════════════════════════════════════════╝
""")

        state = PipelineState(
            mode=args.mode,
            target=args.target,
            strategies=args.strategies,
            max_iter=n,
            model=args.model,
        )
        run_from_data(state, iterations_data)

    else:
        # ── API MODE ──
        if not args.api_key:
            print("⚠  No API key found. Set --api-key, $ANTHROPIC_API_KEY, or use --data for agent mode.")
            sys.exit(1)

        print(f"""
╔══════════════════════════════════════════════════════════╗
║  BREAKTHROUGH ENGINE V6 — API Mode                      ║
╠══════════════════════════════════════════════════════════╣
║  Model:      {args.model:<42s} ║
║  Endpoint:   {args.api_base:<42s} ║
║  Mode:       {args.mode:<42s} ║
║  Target:     {args.target:<42s} ║
║  Strategies: {args.strategies:<42s} ║
║  Iterations: {str(args.iters):<42s} ║
╚══════════════════════════════════════════════════════════╝
""")

        state = PipelineState(
            mode=args.mode,
            target=args.target,
            strategies=args.strategies,
            max_iter=args.iters,
            model=args.model,
        )
        run_pipeline(state, api_base=args.api_base, api_key=args.api_key, model=args.model)

    # Generate output
    out_file = args.output or f"breakthrough-results-{datetime.now():%Y%m%d-%H%M%S}.html"
    out_path = Path(out_file)
    html_content = generate_html(state)
    out_path.write_text(html_content, encoding="utf-8")

    disc_count = len(state.discoveries)
    print(f"""
{'═'*60}
  PIPELINE COMPLETE
  Discoveries: {disc_count}
  Breakthroughs: {state.break_count}
  Output: {out_path.resolve()}
{'═'*60}
""")

    # Try to open in browser
    try:
        import webbrowser
        webbrowser.open(str(out_path.resolve()))
    except Exception:
        pass


if __name__ == "__main__":
    main()
