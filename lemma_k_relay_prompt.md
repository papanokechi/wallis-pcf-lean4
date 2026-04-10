# Lemma K Relay Prompt — H-0025 / G-01

Use this prompt when handing the remaining `k \ge 5` proof frontier to an external developer-facing AI.

---

You are preparing a **derivation-grade proof relay packet** for the remaining `k \ge 5` frontier in Paper 14, starting with `k = 5`.

## Core rule
Do **not** claim the theorem is proved unless each step below is actually closed. If a step is incomplete, say so explicitly.

After **every** step, append exactly:
- `GAP: ...`
- `SEVERITY: blocks | partial | cosmetic`

Use `blocks` if the missing justification prevents the proof from going through, `partial` if the structure is right but a lemma still needs to be filled in, and `cosmetic` only for presentation-level cleanup.

## Required 5-step cascade

### Step 1 — Multiplier system
1. Write the eta-multiplier for `\eta(\tau)^{-k}`.
2. Derive the conductor formula `N_k = 24 / gcd(k,24)`.
3. Make the `k = 5` normalization explicit, including any cusp/root-of-unity factors.

### Step 2 — CRT / local reduction
1. Reduce the relevant Kloosterman phase to prime-power pieces.
2. Isolate the `2`-adic quintic obstruction for `k = 5`.
3. State exactly what local estimate still needs to be bounded.

### Step 3 — Weil / spectral bound
1. State the precise Kloosterman-type bound being invoked.
2. Say whether it comes from classical Weil, Petersson/Kuznetsov, or Goldfeld–Sarnak-style half-integral-weight input.
3. Identify which constants depend on `k` and which are uniform.

### Step 4 — Error-term insertion
1. Insert the bound into the circle-method / Rademacher tail.
2. Show the resulting error term is strong enough for Lemma K.
3. Track the dependence on truncation level and conductor.

### Step 5 — Generalisation
1. Explain what changes when passing from `k = 5` to general `k \ge 5`.
2. Separate what is already proved, what follows formally from the same argument, and what still needs a local lemma.

## Reference anchors
If used, cite them explicitly and tie them to the exact step they justify:
- **Petersson** for eta-multiplier / circle-method setup
- **Weil** for Kloosterman-type exponential sum bounds
- **Goldfeld–Sarnak** for the spectral / half-integral-weight control layer
- Optional: `Iwaniec`, `Kowalski`, `Kuznetsov`, or equivalent half-integral-weight notes

## Output format
Return exactly these sections:
1. `Executive status`
2. `Step 1` through `Step 5`
3. `Blocked point summary`
4. `Minimal theorem statement actually justified`
5. `BATON TO AGENT 3`

## BATON TO AGENT 3
End with a machine-actionable block for the local zero-API checker that includes:
- the conductor formula being checked,
- the sample moduli / `(m,n,c)` cases to test,
- the bound shape to compare numerically,
- any constants or normalizations that still require verification by SymPy/mpmath.

Use this exact header:

`BATON TO AGENT 3:`
