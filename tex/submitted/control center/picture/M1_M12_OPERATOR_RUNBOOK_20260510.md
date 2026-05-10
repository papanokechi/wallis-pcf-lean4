# M1-M12 closure -- operator-action runbook (6 OP_* items)

**Cut at:** 2026-05-10 ~14:45 JST
**Companion to:** `M1_M12_CLOSURE_ROADMAP_PROMPT_SERIES_20260510.md` (sec 4 OP_* table)
**Class:** operator-runbook artefact (concrete commands + acceptance criteria; not a prompt)
**Status:** RULE 1 in force; M10 V0 sole open math axis

This file expands each of the 6 OP_* items from the roadmap into copy-pasteable commands and pass/fail criteria. Operator owns execution; CLI agent verifies acceptance criteria before unblocking the downstream prompt.

Repo layout (operator-side):
- claude-chat repo: `C:\Users\shkub\OneDrive\Documents\archive\admin\VSCode\claude-chat` (this repo; holds `.fleet.yaml`, `tex/submitted/control center/`)
- wallis-pcf-lean4 repo: `papanokechi/wallis-pcf-lean4` (SEPARATE repo; holds `lean/` subtree); operator navigates there for OP_A / OP_C3 / OP_C3PLUS

---

## OP_A -- OPT_A remediation (commit/stash lean/ working tree)

**Predecessor:** none (any time)
**Unblocks:** S148R (slot 148 re-fire)
**Owner:** operator (papanokechi)
**Repo:** `papanokechi/wallis-pcf-lean4`
**Approx duration:** 5-15 minutes

### Scope

The slot 148 first-fire HALTED at STEP 0.4(c) PRECONDITION_DIRTY_TREE because the `lean/` subtree was mid-iteration:
- 3 tracked-modified files: `lean/WallisFamily.lean` (+62/-46), `lean/lakefile.lean` (+9/-1), `lean/lean-toolchain` (+1/-1)
- 1 untracked target file (slot 148 needs to edit it): `lean/Thm66_ApparentSingularity.lean`
- ~20 other untracked files (logs, intermediates) -- not blocking

Slot 148 needs a clean tracked state on its target file before applying Pattern alpha refactor.

### Option A.i -- COMMIT (recommended if iter-13 work is reviewable)

```powershell
cd <path-to-wallis-pcf-lean4>
git status -s -- lean/
git diff --stat -- lean/WallisFamily.lean lean/lakefile.lean lean/lean-toolchain

# review diffs; if iter-13 work is in a coherent state:
git add lean/WallisFamily.lean lean/lakefile.lean lean/lean-toolchain
git add lean/Thm66_ApparentSingularity.lean
git commit -m "M10 iter-13 mid-pass commit + add Thm66_ApparentSingularity.lean to tracking" -m "Pre-slot-148 OPT_A remediation. WallisFamily.lean +62/-46; lakefile +9/-1; lean-toolchain +1/-1. Tracking added for Thm66_ApparentSingularity.lean (slot 148 target)."
git push origin <branch>
```

### Option A.ii -- STASH (recommended if iter-13 work is unstable)

```powershell
cd <path-to-wallis-pcf-lean4>
git stash push -u -- lean/WallisFamily.lean lean/lakefile.lean lean/lean-toolchain -m "M10 iter-13 mid-pass stash; OPT_A remediation pre-slot-148"
git add lean/Thm66_ApparentSingularity.lean
git commit -m "Add Thm66_ApparentSingularity.lean to tracking (pre-slot-148)" -m "OPT_A remediation; WallisFamily / lakefile / toolchain changes stashed."
git push origin <branch>
```

### Acceptance criteria (CLI agent re-verifies before S148R)

```powershell
cd <path-to-wallis-pcf-lean4>
git status --porcelain -- lean/WallisFamily.lean lean/lakefile.lean lean/lean-toolchain lean/Thm66_ApparentSingularity.lean
# Expected output: empty (no lines)
```

If output is empty, OP_A is complete. Other untracked files in `lean/` (logs, intermediates) are acceptable -- only the 4 paths above gate slot 148.

---

## OP_A1 -- M10 documented-commitment paragraph fill

**Predecessor:** none (parallel to OP_A; can run any time)
**Unblocks:** S152 (synth-review of paragraph)
**Owner:** operator
**File:** `tex/submitted/control center/picture/m10_documented_commitment.md` Section 3

NOTE: This OP fills the M10 commitment-paragraph that gates the M9 V0 announcement-flag flip in `.fleet.yaml` (per `gate: [slot-135-landed, slot-136-landed, slot-137-landed, m10-resolved]`). It is labeled "M9 commitment-paragraph" in some predecessor outlooks; canonical is "M10 documented-commitment paragraph that resolves m10-resolved gate."

### Scope

Section 3 currently contains a placeholder block:

```
COMMITMENT (operator to fill):
  delivery: complete-by-{YYYY-MM-DD}  OR  report-status-by-{YYYY-MM-DD}
  delegation: {self / specific-collaborator / external-team}
  notes: {free-form}
  status: COMMITTED-{YYYY-MM-DD}
```

Replace the four `{...}` placeholders with concrete values. Constraints from cascade-132 PATH_B Option alpha precedent at bridge `fd669d3` sec 5:
- delivery date: a real future date OR a "report-status-by" date if completion timing is uncertain
- delegation: who actually does the M10 sorry-discharge work (operator self vs collaborator)
- notes: free-form operator commentary; should NOT reference Zenodo timelines, endorsement plans, or venue resubmission cadence (RULE-1 leakage; checked at S152)
- status: `COMMITTED-{YYYY-MM-DD}` where YYYY-MM-DD is the fill date

### Edit procedure

```powershell
cd 'C:\Users\shkub\OneDrive\Documents\archive\admin\VSCode\claude-chat'
# edit tex/submitted/control center/picture/m10_documented_commitment.md sec 3 in your editor
# replace 4 placeholders; keep the YAML-like indentation; ASCII-pure

git add 'tex/submitted/control center/picture/m10_documented_commitment.md'
git commit -m "M10-COMMITMENT-FILLED -- operator-issued delivery commitment" -m "Section 3 commitment-paragraph filled per cascade-132 PATH_B Option alpha precedent (bridge fd669d3 sec 5). Status flipped to COMMITTED-{YYYY-MM-DD}."
git push origin HEAD
```

### Acceptance criteria (S152 pre-flight checks)

- Section 3 contains no `{...}` placeholders
- Section 3 contains no token strings: `Zenodo`, `endorsement`, `arXiv`, `Compositio`, `Ramanujan`, `AFM`, `Mahboubi` (RULE-1 leakage indicators)
- `status:` field matches pattern `COMMITTED-\d{4}-\d{2}-\d{2}`
- File is ASCII-pure
- Section 3 is between 3 and ~15 lines (sanity bound; not enforced strictly)

S152 is a T1-Synth review fire; if synth verdict is `RATIFY`, OP_A2 unlocks. If `RATIFY_WITH_AMENDMENT`, operator applies amendments first.

---

## OP_A2 -- `.fleet.yaml` commitments[0] status flip

**Predecessor:** S152 verdict `RATIFY` (or `RATIFY_WITH_AMENDMENT` with amendments applied)
**Unblocks:** OP_DP0 (and indirectly the M9 V0 milestone gate-fill)
**Owner:** operator
**File:** `.fleet.yaml` line 693

### Scope

Edit one line in `.fleet.yaml`:

Before (current):
```
  - id: m10-lean4-sorry-discharge
    axis: M10
    scope: post-rule-1-lift work-stream
    status: COMMITMENT-PARAGRAPH-PENDING-OPERATOR
    substrate: "tex/submitted/control center/picture/m10_documented_commitment.md"
```

After:
```
  - id: m10-lean4-sorry-discharge
    axis: M10
    scope: post-rule-1-lift work-stream
    status: COMMITTED-{YYYY-MM-DD}
    substrate: "tex/submitted/control center/picture/m10_documented_commitment.md"
```

The `{YYYY-MM-DD}` should match the date used in m10_documented_commitment.md sec 3 status field (consistency check).

### Edit procedure

```powershell
cd 'C:\Users\shkub\OneDrive\Documents\archive\admin\VSCode\claude-chat'
# edit .fleet.yaml line 693 in your editor
# replace 'COMMITMENT-PARAGRAPH-PENDING-OPERATOR' with 'COMMITTED-YYYY-MM-DD'

# YAML re-validation
python -c "import yaml; yaml.safe_load(open('.fleet.yaml', 'r', encoding='utf-8').read()); print('YAML OK')"

git add '.fleet.yaml'
git commit -m "M10 commitment status COMMITTED-{YYYY-MM-DD} -- post S152 RATIFY" -m "OP_A2 .fleet.yaml flip; m10-resolved flag now true; M9 V0 milestone gate satisfied."
git push origin HEAD
```

### Acceptance criteria

- `.fleet.yaml` parses as valid YAML
- Line 693 (or equivalent line for `commitments[0].status`) matches `COMMITTED-\d{4}-\d{2}-\d{2}`
- Date matches `m10_documented_commitment.md` sec 3 status field

---

## OP_C3 -- C.3 commit (post-S148R green build)

**Predecessor:** S148R LANDED with build green
**Unblocks:** OP_C3PLUS (C.3+ 4-step gate)
**Owner:** operator
**Repo:** `papanokechi/wallis-pcf-lean4`

### Scope

After S148R lands, the agent has applied Pattern alpha refactor to `Thm66_ApparentSingularity.lean` (deleted redundant `h_exact` parameter; closed S1+S2 sorries by deletion). Build should be green:
- `lake build` exit 0
- 0 sorries in tracked `.lean` files

Operator commits the post-refactor state and any associated lake artefacts.

### Commands

```powershell
cd <path-to-wallis-pcf-lean4>

# verify build
lake build
echo "build exit code: $LASTEXITCODE"
# expected 0

# verify sorry-count (literal-match per slot 149 sec 8)
grep -rn 'by sorry\|:= sorry' lean/ --include='*.lean' | wc -l
# expected 0

# stage and commit
git status -s -- lean/
git add lean/Thm66_ApparentSingularity.lean lean/WallisFamily.lean lean/lakefile.lean lean/lean-toolchain lean/lake-manifest.json
# add other tracked files updated by S148R as needed

git commit -m "M10 C.3 -- green build + Pattern alpha closes S1+S2 by deletion" -m "Post-S148R lean/ tree commit. lake build exit 0; sorry-count 0; toolchain pin {version} unchanged from pre-refactor."
git push origin <branch>
```

### Acceptance criteria

- `lake build` returns exit 0 on the committed state
- `grep -rn 'by sorry\|:= sorry' lean/ --include='*.lean'` returns 0 matches
- `git status --porcelain -- lean/` returns empty (apart from explicitly-untracked logs/intermediates)
- Commit SHA recorded for OP_C3PLUS reference

---

## OP_C3PLUS -- C.3+ 4-step gate (clean-clone reproducibility check)

**Predecessor:** OP_C3
**Unblocks:** S145 (M10 V0 substrate-prep fire)
**Owner:** operator (re-runnable by CLI agent if operator delegates)
**Repo:** fresh clone of `papanokechi/wallis-pcf-lean4` at OP_C3 commit SHA

### Scope (per slot 143R verdict C-143-6 4-step gate)

```powershell
# clean clone
$tmp = "$env:TEMP\wallis-c3plus-$(Get-Date -Format yyyyMMdd-HHmmss)"
git clone https://github.com/papanokechi/wallis-pcf-lean4.git $tmp
cd $tmp
git checkout <OP_C3-commit-SHA>

# step (a) -- lake build green
lake build
if ($LASTEXITCODE -ne 0) { Write-Host "STEP a FAIL"; exit 1 } else { Write-Host "STEP a PASS" }

# step (b) -- lake test green (or NO_TEST_TARGET acceptable)
lake test 2>&1 | Tee-Object -Variable testOut
if ($LASTEXITCODE -eq 0) {
  Write-Host "STEP b PASS"
} elseif ($testOut -match "no test target|NO_TEST_TARGET|unknown command") {
  Write-Host "STEP b PASS (NO_TEST_TARGET)"
} else {
  Write-Host "STEP b FAIL"; exit 1
}

# step (c) -- sorry-count assertion
$count = (Select-String -Path 'lean/*.lean','lean/**/*.lean' -Pattern 'by sorry|:= sorry' -ErrorAction SilentlyContinue).Count
if ($count -eq 0) { Write-Host "STEP c PASS" } else { Write-Host "STEP c FAIL ($count matches)"; exit 1 }

# step (d) -- toolchain pin + lakefile-orphans
$tc = Get-Content lean/lean-toolchain -Raw
Write-Host "toolchain: $tc"
# operator should check that $tc matches pre-refactor pin manually

$orphans = @()
if (Test-Path 'lean/proof_targets.lean') { $orphans += 'proof_targets.lean' }
if (Test-Path 'lean/CardEvenOfInvolution.lean') { $orphans += 'CardEvenOfInvolution.lean' }
# orphans should be either added to lean_lib root in lakefile.lean or moved to staging dir
# operator inspects lakefile.lean to confirm

if ($orphans.Count -gt 0) {
  Write-Host "STEP d ORPHAN-CHECK: $($orphans -join ',') -- inspect lakefile.lean"
} else {
  Write-Host "STEP d ORPHAN-CHECK: none"
}
```

### Acceptance criteria

- Steps (a) (b) (c) (d) all PASS
- Output captured as `c3plus_pass_log.md` (operator deposits at convenient location; referenced by S145 STEP 0.3 G7)
- Clean-clone HEAD SHA recorded

---

## OP_DP0 -- RULE 1 lift directive

**Predecessor:** S147 LANDED + OP_A2 LANDED (M-axis closure series complete + M10 commitment status flipped)
**Unblocks:** S142 (RULE 1 lift authorization fire)
**Owner:** operator
**Form:** one-line operator instruction (text message in chat OR commit message)

### Scope

Operator issues an unambiguous lift directive. Recommended form:

```
RULE 1 lift authorized; proceed with admin / distribution work-streams (M1 D2-NOTE Zenodo, M11 endorsement, M12 resubmissions, Zenodo deposit cascade).
```

Or in committed form (preferred for AEAL anchoring):

```powershell
cd 'C:\Users\shkub\OneDrive\Documents\archive\admin\VSCode\claude-chat'
# create empty marker commit
git commit --allow-empty -m "RULE 1 LIFTED -- math-axis closure complete; admin work-streams unblocked" -m "Predecessor: S147 (M10 V0 cascade-absorption) + OP_A2 (.fleet.yaml COMMITTED). Slot 142 RULE 1 lift authorization fire now pre-flight-eligible."
git push origin HEAD
```

### Acceptance criteria

- Operator instruction unambiguous (no hedging language like "soft-lift" or "partial")
- Predecessor verified: S147 bridge folder LANDED (verdict `RATIFY` or equivalent) AND `.fleet.yaml` `commitments[0].status` matches `COMMITTED-\d{4}-\d{2}-\d{2}`
- Optional: empty marker commit on claude-chat for AEAL anchoring

S142 fire then assembles the lift authorization packet and cuts `M1_M12_CLOSURE_OUTLOOK_<YYYYMMDD>_POST_LIFT.md` successor outlook.

---

## sec X -- ordering summary (sequenced)

```
                         OP_A1 (paragraph fill)
                              |
                              v
OP_A (lean/ stash/commit)    S152 (synth review)
       |                      |
       v                      v
     S148R                   OP_A2 (.fleet.yaml flip)
       |                      |
       v                      |
     OP_C3                    |
       |                      |
       v                      |
   OP_C3PLUS                  |
       |                      |
       v                      |
     S145 -> S146 -> S147     |
                       |      |
                       +------+
                       |
                       v
                     OP_DP0
                       |
                       v
                     S142
                       |
                       v
                     S153 / S154 / S155 / S156
```

Two parallel tracks merge at OP_DP0:
- math-closure track: OP_A -> S148R -> OP_C3 -> OP_C3PLUS -> S145 -> S146 -> S147
- commitment track: OP_A1 -> S152 -> OP_A2

Both must complete before OP_DP0 fires.

---

## sec Y -- minimum operator path (fastest to RULE 1 lift)

If operator wants to minimize operator-side time-on-task:

1. **OP_A (5-15 min):** stash lean/ tree, commit Thm66 tracking add. Unblocks S148R.
2. **OP_A1 (10-30 min):** fill m10_documented_commitment.md sec 3. Unblocks S152.
3. **Wait** for S148R + S152 to land (CLI agent + claude.ai web).
4. **OP_C3 (10-20 min after S148R):** verify lake build green; commit lean/ tree.
5. **OP_C3PLUS (15-30 min after OP_C3):** clean-clone reproducibility check.
6. **OP_A2 (2-5 min after S152 RATIFY):** flip .fleet.yaml status field.
7. **Wait** for S145 + S146 + S147 to cascade-land.
8. **OP_DP0 (1-2 min):** issue lift directive.

**Total operator-side time-on-task estimate:** 45-100 minutes spread across the window between OP_A start and OP_DP0 fire (most of the wall-clock time is agent-side fires + synth turnaround).

---

*End of operator runbook. ASCII-pure; FV-disciplined; ANTI-CONFLATION-clean.*
