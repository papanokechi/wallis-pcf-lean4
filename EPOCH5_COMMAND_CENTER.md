# Epoch 5 Generalization Command Center

## Quick start

```powershell
py -3 epoch5_command_center.py --run-all --build-only
py -3 epoch5_command_center.py --serve --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

## What it does

- **k-Space Mission Control**
  - runs cross-k numerical extraction for `k=5,6,7,8`
  - estimates `A₁^(k)` from partition-ratio asymptotics
  - compares extracted values against the closed-law candidate

- **Swarm Live**
  - reads the latest `siarc_outputs/agent_D_out.json`
  - shows ASR-refined survivors, their gaps, and status tags

- **Pattern Inference**
  - evaluates three generalization hypotheses:
    - `G-01`: `A₁^(k) = -(k*c_k)/48 - ((k+1)(k+3))/(8*c_k)`
    - `G-02`: empirical quadratic fit in `k`
    - `G-03`: binomial `α(k)` probe
  - uses `sympy.nsimplify` as a lightweight PSLQ-style coefficient recovery step

- **Agent Log**
  - streams recent ASR / Judge milestones from `multi_agent_discussion/self_correction_log.json`

- **H-0025 Report**
  - surfaces the Judge verdict from `siarc_outputs/agent_J_out.json`
  - shows which publication checks are closed vs pending

## Current verified snapshot

From the generated `epoch5_state.json`:
- strongest hypothesis: `G-01` at `91.9%` confidence
- `k=6` extracted `A₁ ≈ -2.0138`, closed-law `≈ -2.0387`, gap `≈ 1.22%`
- `k=7` extracted `A₁ ≈ -2.4310`, closed-law `≈ -2.4632`, gap `≈ 1.31%`
- `k=8` extracted `A₁ ≈ -2.8747`, closed-law `≈ -2.9149`, gap `≈ 1.38%`

## Notes

- This is a **real cross-k numerical check**, not a mock panel.
- The dashboard uses local browser `fetch()` calls to the Python server (`/api/state`, `/api/run-k`, `/api/run-all`, `/api/test-hypothesis`).
- The current Judge status for `H-0025` remains:
  - **NUMERICALLY VERIFIED — FORMAL PROOF PENDING**
