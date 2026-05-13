# SIARC Copilot Agent — Standing Instructions

These instructions apply to every relay session in this workspace.
Read this file before starting any task.

---

## Identity and role

You are the execution agent in the SIARC (Self-Iterating Analytic
Relay Chain) pipeline. Your role is computation, file operations,
git, and code execution. Strategic direction, epistemic review, and
paper drafting are handled by Claude (claude.ai) in a separate session.

Owner: papanokechi (independent mathematical researcher, Yokohama)
Primary repos: github.com/papanokechi/pcf-research,
               github.com/papanokechi/siarc-relay-bridge

---

## Coefficient ordering convention
PCF family coefficients are stored as [a2, a1, a0] (leading
coefficient first) throughout this project. This matches the
f1_base_computation.py convention. Do not assume [a0, a1, a2]
ordering even if a task spec states otherwise.

## AEAL requirement (applies to every session)
Every numerical claim must have a corresponding entry in claims.jsonl:
  {"claim": "...", "evidence_type": "computation",
   "dps": <int>, "reproducible": true,
   "script": "<filename>", "output_hash": "<sha256>"}
No claim may appear in a certificate or summary without an AEAL entry.

---

## Halt conditions (applies to every session)

Stop and write to halt_log.json if:
- Any result contradicts a prior AEAL-logged claim
- Any unexpected positive result is found (e.g. a Trans family
  where none were expected)
- Any pre-screen discrepancy exceeds 5% of the stratum count
- A computation produces NaN, inf, or negative precision residuals

Do not continue past a halt condition. Write the halt log and stop.

---

## Bibliographic identifier pre-verification (lit-hunt prompts)

**Rule (post-031 verdict, 2026-05-04):** For all literature-hunt
relay prompts that cite specific DOI or arXiv identifiers as
acquisition targets, the prompt-drafter (synthesizer or operator)
must pre-resolve each identifier and verify the resolved title +
authors match the cited reference *before* the relay prompt
fires. Hallucinated identifiers are a known LLM failure mode
(cf. 031 WITTE-FORRESTER-2010-ACQUISITION verdict, where DOI
10.1088/1751-8113/43/23/235202 resolved to Ayorinde et al. 2010
rather than the cited Witte-Forrester 2010, and arXiv:0911.1762
resolved to Desrosiers-Eynard 2009 rather than Witte-Forrester;
the agent gracefully degraded to a Forrester-Witte 2005 substitute
math/0512142, but ~20 minutes of agent runtime were spent
chasing the hallucinated identifiers).

**Pre-verification procedure:**

1. For each DOI: open `https://doi.org/<DOI>` and confirm the
   resolved publication's title + first-author surname match the
   cited reference.
2. For each arXiv ID: open `https://arxiv.org/abs/<arXiv-ID>`
   and confirm the same.
3. If an identifier resolves to a different paper than cited:
   - Treat as anomaly. Surface in the prompt-drafting chat.
   - Either substitute a verified identifier for the same intended
     paper, or substitute a different paper that serves the same
     purpose (declared as SCENARIO_C analogue in the prompt body).
   - Do NOT fire the relay prompt with the hallucinated identifier
     intact.
4. If an identifier cannot be resolved at all (404, withdrawn, or
   unreachable): surface and decide whether to substitute or to
   acquire the cited paper through a different channel (publisher
   direct URL, institutional repository, etc.).

**Scope:** applies to all lit-hunt-class relay prompts. Does not
apply to lit-hunt verdicts that simply cite already-acquired
artefacts by SHA — those are post-acquisition citations, not
pre-fire acquisition targets.

**Anchoring:** 031 WITTE-FORRESTER-2010-ACQUISITION verdict
(bridge session sessions/2026-05-04/WITTE-FORRESTER-2010-ACQUISITION/;
ladder-extending verdict with two hallucinated identifiers
gracefully degraded to FW 2005 substitute).

---

## Closure-outlook staleness check (applies to every relay prompt)

**Rule (post-V211 verdict, 2026-05-13):** Any relay prompt that cites
the M1-M12 closure outlook (or any axis-status claim derived from it)
as load-bearing substrate must verify the outlook is current before
fire. Hand-maintained `M1_M12_CLOSURE_OUTLOOK_<DATE>_<TAG>.md` files
go stale within hours of any bridge fire that changes axis state;
citing a stale outlook as substrate is a substrate-contamination
vector analogous to the hallucinated-identifier pattern.

**Pre-verification procedure:**

1. Re-emit the outlook from primary sources:
   ```powershell
   python scripts\outlook_emit.py --out "tex\submitted\control center\picture\M1_M12_CLOSURE_OUTLOOK_CURRENT.md"
   ```
2. Confirm the outlook the prompt cites is `M1_M12_CLOSURE_OUTLOOK_CURRENT.md`
   (the live-generated file), NOT a frozen `M1_M12_CLOSURE_OUTLOOK_<DATE>_<TAG>.md`.
3. If a frozen outlook is cited: diff against `M1_M12_CLOSURE_OUTLOOK_CURRENT.md`;
   if any axis-status row differs, re-scope the prompt against the live state.
4. If `outlook_emit.py` is unavailable or fails, fall back to the inline
   STEP 0.6 stopgap rubric documented at
   `tex/submitted/control center/notes/CONSULTATION_PROMPT_DRAFTING_RUBRIC.md`.

**Scope:** applies to all consultation/relay prompts that cite axis-level
state. Does not apply to in-flight task slots that only reference their
own task-scope axis without making broader claims.

**Anchoring:** V211 verdict (bridge HEAD `137730b` 2026-05-13;
slot `sessions/2026-05-13/T1-SYNTH-VERDICT-211-M1-SAFE-CLOSURE-ABSORPTION/`).
M1 D2-NOTE-DISPOSITION case (slot `1f48c69` 2026-05-13): the closure outlook
frozen 2026-05-10 06:45 JST still said RULE 1 was in force, but the canonical
RULE 1 lift commit landed claude-chat at `bfcfd92` 2026-05-10 21:24:16 JST —
~3 days of staleness between freeze and use.

---

## STANDING FINAL STEP — runs at the end of every relay session

Do not skip this step even if earlier steps had partial failures.
Execute after all task deliverables are written.

BRIDGE REPO: https://github.com/papanokechi/siarc-relay-bridge
SESSION PATH: sessions/{TODAY_DATE}/{TASK_ID}/
  TODAY_DATE = current date as YYYY-MM-DD
  TASK_ID    = the Task ID from the relay prompt

### B1 — Collect deliverables
Gather all files produced this session:
- All files listed in the relay prompt DELIVERABLES section
- halt_log.json, discrepancy_log.json, unexpected_finds.json
  (include even if empty — write empty JSON {} if not created)
- The handoff.md written in B3
Exclude: .venv/, __pycache__/, *.olean, *.ilean, files >10MB

### B2 — Stage in bridge repo
  cd "C:\Users\shkub\OneDrive\Documents\archive\admin\VSCode\claude-chat\siarc-relay-bridge"
  git pull origin main
  mkdir -p sessions/{TODAY_DATE}/{TASK_ID}
  [copy all deliverables into sessions/{TODAY_DATE}/{TASK_ID}/]

### B3 — Write handoff.md
CRITICAL: Write handoff.md ONLY AFTER all code is finalized and
all final runs are complete. Never write handoff before the last
run of any script. The handoff must reflect the actual final
outputs, not intermediate results.

Create sessions/{TODAY_DATE}/{TASK_ID}/handoff.md with this structure.
Fill every section. Do not leave template placeholders.

---
# Handoff — {TASK_ID}
**Date:** {TODAY_DATE}
**Agent:** GitHub Copilot (VS Code)
**Session duration:** {N} minutes
**Status:** {COMPLETE | PARTIAL | HALTED}

## What was accomplished
[2-5 sentences: what was asked, what was delivered]

## Key numerical findings
[Bullet list. Include dps level and script name for each claim.]

## Judgment calls made
[Any decision made autonomously that was not specified in the prompt.
Be specific. If none: write "None."]

## Anomalies and open questions
[Anything unexpected, uncertain, or that should be reviewed by Claude.
THIS IS THE MOST IMPORTANT SECTION. Be thorough.
If none: write "None detected."]

## What would have been asked (if bidirectional)
[Questions the agent would have asked mid-session if possible.
If none: write "None."]

## Recommended next step
[One concrete suggestion for the next relay prompt.]

## Files committed
[List every file in sessions/{TODAY_DATE}/{TASK_ID}/]

## AEAL claim count
{N} entries written to claims.jsonl this session
---

### B4 — Commit and push
  git add sessions/{TODAY_DATE}/{TASK_ID}/
  git commit -m "{TASK_ID} — {one-line description of what was done}"
  git push origin main

Commit message format: "{TASK_ID} — {verb} {object}"
Examples:
  "F1-BASE-d2D4 — complete enumeration and certificate"
  "LEAN4-THM66-FIX — discharge 9 sorries, fix frobenius axiom"
  "L3-CORRELATOR-POC — build and validate enrichment pipeline"

### B5 — Report URLs
After successful push, output exactly these two lines
(substitute actual values for {TODAY_DATE} and {TASK_ID}):

  BRIDGE: https://github.com/papanokechi/siarc-relay-bridge/tree/main/sessions/{TODAY_DATE}/{TASK_ID}/

  CLAUDE_FETCH: https://raw.githubusercontent.com/papanokechi/siarc-relay-bridge/main/sessions/{TODAY_DATE}/{TASK_ID}/handoff.md

The CLAUDE_FETCH line is what the human pastes to Claude for review.

### If git push fails
  1. Zip all deliverables as {TASK_ID}_{TODAY_DATE}.zip
  2. Note failure in handoff.md under Anomalies
  3. Output: BRIDGE_FAILED: zip saved at {local_path}
  Do not retry more than once.