# Consultation Prompt Drafting Rubric

**Owner:** SIARC Copilot CLI (agent) + operator
**Created:** 2026-05-13 (slot T1-OPERATOR-V211-COMMITMENTS-CASCADE-EXECUTION)
**Anchored to:** V211 Q-211-5 γ (bridge HEAD `137730b`); witness recommended
                 inline-blocking checks for consultation-prompt drafters
**Status:** STANDING — refresh when new failure modes surface in retros

---

## Purpose

Pre-flight checklist for consultation/relay-prompt drafters. Designed to be
runnable in <2 minutes BEFORE firing any T1-Synth or T2-Executor consultation
prompt. Catches the most common substrate-staleness and citation-hallucination
failure modes in this project's relay-fire history.

This rubric is mandatory for:

- T1-Synth analytical-guidance consultation prompts
- Operator-tier consultation prompts to claude.ai / Opus
- Any prompt that cites bridge SHAs, Zenodo DOIs, arXiv IDs, or DOIs as
  load-bearing substrate

Optional for: simple T2-Executor task fires that do not cite external substrate.

---

## STEP 0 — pre-fire checks (must all pass GREEN before fire)

### STEP 0.1 — Bridge SHA pre-verification

For each bridge SHA cited in the prompt body:

```powershell
git -C siarc-relay-bridge rev-parse <SHA>
git -C siarc-relay-bridge show --stat=200 <SHA> | Select-Object -First 50
```

GREEN if: SHA resolves AND the path inventory matches the prompt's claimed
slot-folder name AND the commit message names the expected verdict class.

RED if any of the above mismatches → halt; correct the citation; re-run.

Anchoring memory: `substrate verification` (post-105 verdict 2026-05-08;
sha_correction_finding.md). Non-existent SHAs are a recurrent contamination
vector that propagates through subsequent rubber-stamping consultants.

### STEP 0.2 — Bibliographic identifier pre-verification

For each DOI or arXiv ID cited as acquisition-target substrate:

```powershell
# DOI
Invoke-WebRequest "https://doi.org/<DOI>" -MaximumRedirection 10 |
  Select-Object -ExpandProperty Content | Select-String -Pattern "(?i)title"

# arXiv
Invoke-WebRequest "https://arxiv.org/abs/<ARXIV-ID>" |
  Select-Object -ExpandProperty Content | Select-String -Pattern "(?i)<title>"
```

GREEN if: resolved title + first-author match the cited reference.

RED if: identifier resolves to a different paper → substitute a verified
identifier OR substitute a different paper that serves the same purpose
(declared as SCENARIO_C analogue in the prompt body). Do NOT fire the
relay prompt with the hallucinated identifier intact.

Anchoring: copilot-instructions.md §"Bibliographic identifier pre-verification"
(post-031 verdict 2026-05-04).

### STEP 0.3 — Zenodo concept-DOI vs version-DOI discipline

For each Zenodo deposit cited:

- Cite-all references → concept DOI (e.g. `19996689` for D2-NOTE)
- Specific-version references → version DOI (e.g. `20015923` for D2-NOTE v2.1)
- Cross-link `IsSupplementTo` → concept DOI, NOT version DOI

GREEN if: the prompt's citation class (cite-all vs version-specific) matches
the DOI tier used.

RED if: a version DOI is used where a concept DOI was intended (or vice versa)
→ correct before fire.

Anchoring memory: `substrate verification` (PCF-1 concept `19931635` /
v1.3 `19937196`; PCF-2 concept `19936297` / v1.3 `19963298`).

### STEP 0.4 — Prior-fire supersession-gate scan

Before drafting any multi-phase relay prompt, search the bridge for prior
full-fires of the same task scope:

```powershell
Get-ChildItem "siarc-relay-bridge\sessions" -Recurse -Directory |
  Where-Object Name -Match "<task-scope-keyword>" |
  Select-Object FullName
```

GREEN if: no prior LANDED fire of the same scope exists, OR a prior fire is
explicitly noted in the prompt's supersession-gate block (Phase 0 STEP 0.1-0.6).

RED if: a prior LANDED fire exists and is not addressed → re-scope the new
prompt to discharge the residual rather than re-fire.

Anchoring memory: `prompt drafting discipline` (069 v1 case 2026-05-08;
W20 068 case; cite both).

### STEP 0.5 — Path-inventory citation discipline

For any prior bridge SHA cited in the prompt's path-inventory section:

```powershell
git -C siarc-relay-bridge show --stat=200 <SHA> | Select-String "handoff.md"
```

GREEN if: every cited path-inventory entry derives from the actual
`git show --stat=200 <SHA>` output, not from memory.

RED if: any entry was transcribed from memory and may not match the actual
SHA contents → re-derive from `git show`.

Anchoring memory: `prompt drafting discipline` (069r2 DRAFT-FROZEN-V1 case;
6 of 9 entries wrong at draft-time).

### STEP 0.6 — Closure-outlook staleness check (post-V211)

Before citing the M1-M12 closure outlook (or any axis-status claim) as
substrate, verify the outlook is current:

```powershell
# Re-emit the outlook from primary sources
python scripts\outlook_emit.py --out "tex\submitted\control center\picture\M1_M12_CLOSURE_OUTLOOK_CURRENT.md"

# Compare against the document cited in the prompt
git diff --no-index `
  "tex\submitted\control center\picture\M1_M12_CLOSURE_OUTLOOK_CURRENT.md" `
  "<path-to-outlook-cited-in-prompt>"
```

GREEN if: the cited outlook is `M1_M12_CLOSURE_OUTLOOK_CURRENT.md` AND the
re-emit shows no axis-status changes since the cited generation timestamp.

RED if: axis statuses differ (e.g. RULE 1 lift state, Zenodo deposit DOIs,
last-verdict SHAs) → update the prompt to cite the freshly-emitted outlook,
or re-scope based on the new state.

Anchoring: V211 verdict (bridge HEAD `137730b` 2026-05-13);
M1 D2-NOTE-DISPOSITION case (slot `1f48c69` discovered RULE 1 was lifted
2026-05-10 21:24, ~3 days before the operator request, against a closure
outlook frozen 2026-05-10 06:45 JST that still said RULE 1 was in force).

### STEP 0.7 — Prompt rubber-duck QA gate

For high-stakes T1-Synth prompts (analytical-guidance, axis-V0-closure,
amendment-class), perform either:

- **Background agent rubber-duck QA**: launch an explore-class subagent with
  the FULL prompt as input; ask it to identify R-1 (BLOCKING), R-2 (HIGH),
  R-3 (MEDIUM) issues. Treat any R-1 as fire-blocking.
- **Parallel manual operator-tier QA**: operator re-reads the prompt in a
  separate CLI session; report any failures.

GREEN if: at least one QA round complete; no R-1 unresolved.

RED if: R-1 found and not addressed → patch prompt before fire.

Anchoring memory: `rubber-duck QA discipline` (W20 068 case 2026-05-06;
069r2 namespace collision case 2026-05-08 — both R-1 caught pre-fire).

---

## STEP 1 — fire envelope

Once STEPS 0.1–0.7 are all GREEN:

- Append a one-line **PRE-FIRE STATUS** block to the prompt body certifying
  each STEP 0.x check passed (or noting documented exceptions).
- Append the rubric version + commit SHA at which the rubric was applied.

Example:

```
## PRE-FIRE STATUS (per CONSULTATION_PROMPT_DRAFTING_RUBRIC.md @ <commit-SHA>)

* STEP 0.1 bridge SHAs: GREEN (3 SHAs verified)
* STEP 0.2 bibliographic identifiers: N/A (no DOI/arXiv citations)
* STEP 0.3 Zenodo DOIs: GREEN (1 concept-DOI, 0 version-DOIs)
* STEP 0.4 supersession-gate: GREEN (no prior LANDED fire of scope X)
* STEP 0.5 path-inventory: GREEN (4 entries re-derived from git show)
* STEP 0.6 outlook staleness: GREEN (outlook re-emitted 2026-05-13 14:50 JST; no axis-status delta)
* STEP 0.7 rubber-duck QA: GREEN (background agent R-1=0; operator pass)
```

---

## STEP 2 — post-fire absorption discipline

After fire lands and verdict arrives:

- Update SQL todos (`UPDATE todos SET status='done' WHERE id='<prompt-id>'`)
- File a bridge slot per Standing Final Step (B1-B5)
- Add an AEAL claim per verdict-Q-LOCK
- If the verdict surfaces an anomaly that would have been caught by a
  pre-fire check that does not yet exist: propose a new STEP 0.x and
  promote to this rubric.

---

## Maintenance

- This rubric lives at `tex/submitted/control center/notes/CONSULTATION_PROMPT_DRAFTING_RUBRIC.md`.
- New STEP 0.x entries are added when a retro identifies a recurrent failure
  mode the existing checks would not have caught.
- Removals require operator approval and a closeout note explaining why the
  failure mode is no longer believed to be active.
- Promote any new STEP 0.x to `.github/copilot-instructions.md` once the rule
  has held GREEN for ≥3 distinct fires (anchoring discipline mirrors the
  bibliographic-identifier rule's promotion).
