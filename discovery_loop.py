"""
Ramanujan Discovery Loop — Exponential Academic Frontier Explorer
=================================================================
Architecture:
  Hypothesis Generator  →  Code & Verify Engine  →  Critic & Rank Agent
         ↑                                                   |
         └──────────── Knowledge Base (JSON) ←──────────────┘

Usage:
  python discovery_loop.py              # Run one full iteration
  python discovery_loop.py --iters 5   # Run 5 iterations
  python discovery_loop.py --show      # Show knowledge base summary

Requirements:
  pip install anthropic mpmath
  export ANTHROPIC_API_KEY="sk-ant-..."
"""

import os
import sys
import json
import time
import argparse
import textwrap
from datetime import datetime
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not found.")
    print("  pip install anthropic")
    sys.exit(1)

try:
    from mpmath import mp, mpf, nstr, quad, exp, inf, e1, besselj, besseli
    from mpmath import gamma, pi, sqrt, log, fabs, power
except ImportError:
    print("ERROR: mpmath not found.  pip install mpmath")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
MODEL          = "claude-opus-4-5"
MAX_TOKENS     = 4096
KB_PATH        = Path("knowledge_base.json")
REPORT_PATH    = Path("discovery_report.md")
VERIFY_DIGITS  = 50
mp.dps         = VERIFY_DIGITS + 10

# ── ANSI colors (VS Code terminal supports these) ─────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    PURPLE = "\033[95m"
    GRAY   = "\033[90m"

def header(title: str):
    w = 70
    print(f"\n{C.CYAN}{'─'*w}")
    print(f"  {C.BOLD}{title}{C.RESET}{C.CYAN}")
    print(f"{'─'*w}{C.RESET}")

def ok(msg):   print(f"{C.GREEN}  ✓ {msg}{C.RESET}")
def warn(msg): print(f"{C.YELLOW}  ⚠ {msg}{C.RESET}")
def err(msg):  print(f"{C.RED}  ✗ {msg}{C.RESET}")
def info(msg): print(f"{C.GRAY}    {msg}{C.RESET}")

# ── Knowledge Base ─────────────────────────────────────────────────────────────
def load_kb() -> dict:
    if KB_PATH.exists():
        return json.loads(KB_PATH.read_text(encoding="utf-8"))
    return {"discoveries": [], "failed": [], "stats": {"iterations": 0, "proven": 0, "conjectured": 0}}

def save_kb(kb: dict):
    KB_PATH.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")

def kb_summary(kb: dict) -> str:
    discoveries = kb["discoveries"]
    if not discoveries:
        return "Knowledge base is empty — this is the first iteration."
    lines = [f"Knowledge base: {len(discoveries)} discoveries so far.\n"]
    for d in discoveries[-5:]:          # last 5 for context window efficiency
        status = d.get("status", "?")
        value  = d.get("numerical_value", "?")
        title  = d.get("title", "unknown")
        lines.append(f"  [{status}] {title}  →  V ≈ {value}")
    if len(discoveries) > 5:
        lines.append(f"  ... and {len(discoveries)-5} earlier discoveries.")
    failed = kb.get("failed", [])
    if failed:
        lines.append(f"\nRecent failed hypotheses (avoid these directions):")
        for f in failed[-3:]:
            lines.append(f"  ✗ {f.get('description','?')}")
    return "\n".join(lines)

# ── Anthropic client ───────────────────────────────────────────────────────────
def make_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        err("ANTHROPIC_API_KEY not set.")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)

def call_claude(client: anthropic.Anthropic, system: str, user: str,
                role_label: str = "Agent") -> str:
    print(f"{C.PURPLE}  [{role_label}] calling Claude Opus...{C.RESET}", end="", flush=True)
    start = time.time()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    elapsed = time.time() - start
    print(f" {C.GRAY}({elapsed:.1f}s){C.RESET}")
    return msg.content[0].text

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Hypothesis Generator
# ══════════════════════════════════════════════════════════════════════════════
HYPO_SYSTEM = textwrap.dedent("""
You are the Hypothesis Generator in an automated mathematical discovery system
focused on continued fractions, special functions, and number theory.

Your role: given the current knowledge base, propose ONE new mathematical
hypothesis that:
1. Is NOVEL — not already in the knowledge base.
2. Is TESTABLE — expressible as a generalized continued fraction (GCF) or
   series that can be numerically verified with mpmath.
3. Has POTENTIAL — connects to known special functions (Bessel, hypergeometric,
   Gamma, Exponential Integral, Airy, Zeta, etc.)

Output ONLY valid JSON (no markdown fences, no commentary) matching:
{
  "title": "Short descriptive title",
  "description": "1-2 sentence mathematical description",
  "hypothesis_type": "GCF" | "series" | "integral" | "recurrence",
  "parameters": {
    "a_n": "formula for numerator at step n (Python expression using n)",
    "b_n": "formula for denominator at step n (Python expression using n)",
    "b_0": "initial denominator (optional, default = b_n at n=0)"
  },
  "expected_closed_form": "Your best guess at the closed form (e.g. '2*e**2*e1(2)')",
  "motivation": "Why this direction is promising given the knowledge base",
  "search_basis": ["list", "of", "transcendentals", "to", "try"]
}

For GCF hypotheses: the continued fraction is
  b_0 + a_1/(b_1 + a_2/(b_2 + a_3/(...)))

Be creative but grounded. Examples of interesting directions:
- Varying the k-shift in Borel-regularizable GCFs
- Quadratic or cubic b_n with constant a_n
- Mixed polynomial a_n and b_n with Bessel-type connections
- Factorial numerators with polynomial denominators
""").strip()

def stage1_hypothesis(client: anthropic.Anthropic, kb: dict) -> dict:
    header("STAGE 1 — Hypothesis Generator")
    context = kb_summary(kb)
    user_prompt = f"""Current knowledge base state:\n{context}\n\nGenerate the next hypothesis."""
    raw = call_claude(client, HYPO_SYSTEM, user_prompt, "HypothesisGen")
    # Strip any accidental markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
    try:
        hypo = json.loads(raw)
        ok(f"Hypothesis: {hypo.get('title','?')}")
        info(f"Type: {hypo.get('hypothesis_type','?')}")
        info(f"a_n = {hypo['parameters'].get('a_n','?')}")
        info(f"b_n = {hypo['parameters'].get('b_n','?')}")
        info(f"Expected form: {hypo.get('expected_closed_form','?')}")
        return hypo
    except json.JSONDecodeError as e:
        err(f"JSON parse failed: {e}")
        warn("Raw output saved to hypothesis_raw.txt")
        Path("hypothesis_raw.txt").write_text(raw)
        raise

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Code & Verify Engine
# ══════════════════════════════════════════════════════════════════════════════

def gcf_backward_recurrence(a_fn, b_fn, depth: int = 80) -> mpf:
    """
    Compute GCF via backward recurrence (Euler-Wallis / tail-collapse):
      b_0 + a_1/(b_1 + a_2/(b_2 + a_3/(...)))
    Start from b_depth and fold inward.
    """
    val = b_fn(depth)
    for n in range(depth - 1, 0, -1):
        val = b_fn(n) + a_fn(n + 1) / val
    return b_fn(0) + a_fn(1) / val

def safe_eval_formula(formula: str, n_val):
    """Safely evaluate a formula string with n substituted."""
    from math import factorial as _fac
    safe_ns = {
        "n": n_val,
        "factorial": _fac,
        "gamma": lambda x: float(gamma(x)),
        "pi": float(pi),
        "exp": lambda x: float(exp(x)),
        "sqrt": lambda x: float(sqrt(x)),
        "log": lambda x: float(log(x)),
        "abs": abs,
        "__builtins__": {},
    }
    # mpmath-aware version
    try:
        return mpf(eval(formula, safe_ns))
    except Exception:
        return mpf(0)

def build_a_b(params: dict):
    a_formula = params.get("a_n", "1")
    b_formula = params.get("b_n", "n + 1")

    def a_fn(n):
        return safe_eval_formula(a_formula, n)

    def b_fn(n):
        return safe_eval_formula(b_formula, n)

    return a_fn, b_fn

def run_verify(hypo: dict) -> dict:
    """Numerically verify the hypothesis, compute GCF value, attempt closed-form match."""
    result = {
        "numerical_value": None,
        "convergents":     [],
        "closed_form_match": None,
        "match_digits":    0,
        "verification_status": "unknown",
        "error": None,
    }
    params = hypo.get("parameters", {})
    try:
        a_fn, b_fn = build_a_b(params)

        # Check convergence by comparing depths
        V40  = gcf_backward_recurrence(a_fn, b_fn, depth=40)
        V80  = gcf_backward_recurrence(a_fn, b_fn, depth=80)
        V120 = gcf_backward_recurrence(a_fn, b_fn, depth=120)

        diff = fabs(V80 - V120)
        result["convergents"] = [nstr(V40, 15), nstr(V80, 15), nstr(V120, 15)]

        if diff > mpf("1e-10"):
            result["verification_status"] = "divergent"
            result["error"] = f"|V80-V120| = {nstr(diff, 6)} — not converging"
            return result

        V = V120
        result["numerical_value"] = nstr(V, VERIFY_DIGITS)

        # Try matching expected closed form
        expected = hypo.get("expected_closed_form", "")
        if expected:
            candidate = try_closed_form(expected, V)
            if candidate is not None:
                result["closed_form_match"] = expected
                result["match_digits"]       = candidate
                result["verification_status"] = "proven" if candidate >= 30 else "conjecture"
            else:
                result["verification_status"] = "conjecture_unmatched"
        else:
            result["verification_status"] = "numerical_only"

    except Exception as e:
        result["verification_status"] = "error"
        result["error"] = str(e)

    return result

def try_closed_form(formula_str: str, V: mpf) -> int | None:
    """
    Try to evaluate a candidate closed-form and count matching digits.
    Returns number of matching digits, or None if evaluation fails.
    """
    # Map common names to mpmath functions
    safe_ns = {
        "e1": e1, "E1": e1,
        "besseli": besseli, "besselj": besselj,
        "gamma": gamma, "Gamma": gamma,
        "pi": pi, "e": mp.e,
        "exp": exp, "sqrt": sqrt, "log": log,
        "mpf": mpf,
    }
    try:
        candidate = mpf(eval(formula_str, {"__builtins__": {}}, safe_ns))
        diff = fabs(V - candidate)
        if diff == 0:
            return VERIFY_DIGITS
        if diff > 1:
            return None
        digits = int(-log(diff, 10))
        return digits if digits >= 5 else None
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Critic & Rank Agent
# ══════════════════════════════════════════════════════════════════════════════
CRITIC_SYSTEM = textwrap.dedent("""
You are the Critic & Rank Agent in an automated mathematical discovery system.
You act as a rigorous peer reviewer for conjectured mathematical identities.

Given a hypothesis and its numerical verification results, produce a structured
evaluation. Output ONLY valid JSON (no markdown fences) matching:
{
  "novelty_score": 0-10,
  "novelty_comment": "Is this genuinely new or a known result?",
  "rigor_score": 0-10,
  "rigor_comment": "How strong is the numerical/symbolic evidence?",
  "significance_score": 0-10,
  "significance_comment": "Mathematical importance and connection to known theory",
  "overall_score": 0-10,
  "status": "proven" | "strong_conjecture" | "weak_conjecture" | "failed" | "rediscovery",
  "recommended_action": "What should the next iteration focus on?",
  "formal_statement": "A concise formal mathematical statement of the result (LaTeX)",
  "open_questions": ["list", "of", "follow-up", "questions"]
}
Be strict: a 'proven' status requires a complete derivation path, not just digit matching.
A 'strong_conjecture' requires >= 30 digits of numerical agreement.
""").strip()

def stage3_critic(client: anthropic.Anthropic, hypo: dict, verify: dict) -> dict:
    header("STAGE 3 — Critic & Rank Agent")
    user_prompt = f"""
Hypothesis:
{json.dumps(hypo, ensure_ascii=False, indent=2)}

Verification results:
{json.dumps(verify, ensure_ascii=False, indent=2)}

Evaluate this discovery.
""".strip()
    raw = call_claude(client, CRITIC_SYSTEM, user_prompt, "Critic")
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
    try:
        critique = json.loads(raw)
        score = critique.get("overall_score", 0)
        status = critique.get("status", "?")
        color = C.GREEN if score >= 7 else (C.YELLOW if score >= 4 else C.RED)
        print(f"{color}  Score: {score}/10  [{status}]{C.RESET}")
        info(f"Novelty:      {critique.get('novelty_score',0)}/10  — {critique.get('novelty_comment','')[:60]}")
        info(f"Rigor:        {critique.get('rigor_score',0)}/10  — {critique.get('rigor_comment','')[:60]}")
        info(f"Significance: {critique.get('significance_score',0)}/10  — {critique.get('significance_comment','')[:60]}")
        return critique
    except json.JSONDecodeError as e:
        err(f"Critic JSON parse failed: {e}")
        Path("critic_raw.txt").write_text(raw)
        raise

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Knowledge Base Update
# ══════════════════════════════════════════════════════════════════════════════
def stage4_update_kb(kb: dict, hypo: dict, verify: dict, critique: dict):
    header("STAGE 4 — Knowledge Base Update")
    status = critique.get("status", "unknown")
    score  = critique.get("overall_score", 0)

    record = {
        "id":               datetime.now().strftime("%Y%m%d_%H%M%S"),
        "title":            hypo.get("title", "?"),
        "description":      hypo.get("description", ""),
        "hypothesis_type":  hypo.get("hypothesis_type", "?"),
        "parameters":       hypo.get("parameters", {}),
        "expected_form":    hypo.get("expected_closed_form", ""),
        "numerical_value":  verify.get("numerical_value"),
        "convergents":      verify.get("convergents", []),
        "closed_form_match":verify.get("closed_form_match"),
        "match_digits":     verify.get("match_digits", 0),
        "status":           status,
        "overall_score":    score,
        "formal_statement": critique.get("formal_statement", ""),
        "open_questions":   critique.get("open_questions", []),
        "recommended_action": critique.get("recommended_action", ""),
        "timestamp":        datetime.now().isoformat(),
    }

    if status in ("proven", "strong_conjecture", "weak_conjecture", "rediscovery"):
        kb["discoveries"].append(record)
        kb["stats"]["proven"]      += (1 if status == "proven" else 0)
        kb["stats"]["conjectured"] += (1 if "conjecture" in status else 0)
        ok(f"Saved to knowledge base: [{status}] score={score}")
    else:
        kb["failed"].append({
            "description": hypo.get("description","?"),
            "reason": critique.get("rigor_comment","failed"),
            "timestamp": datetime.now().isoformat(),
        })
        if len(kb["failed"]) > 20:
            kb["failed"] = kb["failed"][-20:]
        warn(f"Recorded as failed hypothesis — will avoid similar directions.")

    kb["stats"]["iterations"] += 1
    save_kb(kb)
    return record

# ══════════════════════════════════════════════════════════════════════════════
# Report Writer
# ══════════════════════════════════════════════════════════════════════════════
def append_report(record: dict, hypo: dict, verify: dict):
    sep = "\n" + "="*70 + "\n"
    entry = f"""
{sep}
## [{record['status'].upper()}] {record['title']}
**ID:** {record['id']}  |  **Score:** {record['overall_score']}/10  |  **Time:** {record['timestamp']}

### Parameters
- a(n) = `{record['parameters'].get('a_n','?')}`
- b(n) = `{record['parameters'].get('b_n','?')}`

### Numerical Value
```
V ≈ {record['numerical_value']}
```

### Closed Form
{record.get('closed_form_match') or '(not identified)'}
Match: {record.get('match_digits', 0)} digits

### Formal Statement
{record.get('formal_statement','—')}

### Open Questions
{chr(10).join('- ' + q for q in record.get('open_questions',[]))}

### Next Direction
{record.get('recommended_action','—')}
"""
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

# ══════════════════════════════════════════════════════════════════════════════
# Full Iteration
# ══════════════════════════════════════════════════════════════════════════════
def run_iteration(client: anthropic.Anthropic, kb: dict) -> dict | None:
    iteration = kb["stats"]["iterations"] + 1
    print(f"\n{C.BOLD}{C.CYAN}{'═'*70}")
    print(f"  ITERATION {iteration}  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*70}{C.RESET}")

    try:
        # Stage 1: Generate hypothesis
        hypo = stage1_hypothesis(client, kb)

        # Stage 2: Verify numerically
        header("STAGE 2 — Code & Verify Engine")
        print(f"  Computing GCF at {VERIFY_DIGITS}-digit precision...")
        verify = run_verify(hypo)
        v_status = verify.get("verification_status", "?")
        v_value  = verify.get("numerical_value", "?")
        digits   = verify.get("match_digits", 0)

        if v_status == "divergent":
            warn(f"GCF diverges: {verify.get('error','')}")
        elif v_status == "error":
            err(f"Verification error: {verify.get('error','')}")
        else:
            ok(f"V ≈ {str(v_value)[:40]}...")
            if digits:
                ok(f"Closed form matches to {digits} digits")
            else:
                info("No closed form match found yet")

        # Stage 3: Critic
        critique = stage3_critic(client, hypo, verify)

        # Stage 4: Update KB
        record = stage4_update_kb(kb, hypo, verify, critique)

        # Append to markdown report
        append_report(record, hypo, verify)
        ok(f"Report updated: {REPORT_PATH}")
        return record

    except Exception as e:
        err(f"Iteration failed: {e}")
        import traceback
        traceback.print_exc()
        return None

# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════
def show_kb_summary():
    kb = load_kb()
    stats = kb["stats"]
    print(f"\n{C.BOLD}Knowledge Base Summary{C.RESET}")
    print(f"  Iterations:   {stats['iterations']}")
    print(f"  Proven:       {stats['proven']}")
    print(f"  Conjectured:  {stats['conjectured']}")
    print(f"  Discoveries:  {len(kb['discoveries'])}")
    print(f"  Failed:       {len(kb.get('failed',[]))}")
    print()
    for d in kb["discoveries"]:
        score = d.get("overall_score", 0)
        color = C.GREEN if score >= 7 else (C.YELLOW if score >= 4 else C.GRAY)
        print(f"  {color}[{d['status']:<18}] {d['title']:<45} V≈{str(d.get('numerical_value','?'))[:20]}{C.RESET}")

def main():
    parser = argparse.ArgumentParser(
        description="Ramanujan Discovery Loop — exponential academic frontier explorer"
    )
    parser.add_argument("--iters", type=int, default=1,
                        help="Number of iterations to run (default: 1)")
    parser.add_argument("--show",  action="store_true",
                        help="Show knowledge base summary and exit")
    parser.add_argument("--reset", action="store_true",
                        help="Reset knowledge base and start fresh")
    args = parser.parse_args()

    if args.show:
        show_kb_summary()
        return

    if args.reset:
        if KB_PATH.exists():
            KB_PATH.unlink()
            print(f"{C.YELLOW}  Knowledge base reset.{C.RESET}")
        if REPORT_PATH.exists():
            REPORT_PATH.unlink()

    client = make_client()
    kb     = load_kb()

    if not REPORT_PATH.exists():
        REPORT_PATH.write_text(
            f"# Ramanujan Discovery Report\nStarted: {datetime.now().isoformat()}\n",
            encoding="utf-8"
        )

    scores = []
    for i in range(args.iters):
        record = run_iteration(client, kb)
        if record:
            scores.append(record.get("overall_score", 0))
        if i < args.iters - 1:
            time.sleep(1)   # Brief pause between iterations

    # Final summary
    if scores:
        print(f"\n{C.BOLD}{'─'*70}")
        print(f"  Run complete: {len(scores)} iteration(s)")
        print(f"  Avg score:   {sum(scores)/len(scores):.1f}/10")
        print(f"  Knowledge base: {KB_PATH}")
        print(f"  Report:         {REPORT_PATH}")
        print(f"{'─'*70}{C.RESET}")

if __name__ == "__main__":
    main()
