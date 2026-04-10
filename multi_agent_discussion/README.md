# Multi-Agent Discussion System

A controller-mediated debate loop for a **GPT strategist** and **Claude critic** inside your VS Code workspace.

## Overview

This setup follows the pattern you described:

1. **`gpt-4o`** acts as the **Strategist** by default
2. **`claude-opus-4-5`** acts as the **Critic** by default
3. The controller passes critique back to GPT for refinement
4. The loop stops on convergence or after a max number of iterations
5. An optional **Judge** pass can review the final answer

> No model talks to another model directly. All communication goes through `controller.py`.

---

## Files

- `multi_agent_discussion/controller.py` — main debate controller
- `multi_agent_discussion/requirements.txt` — optional SDK dependencies
- `multi_agent_discussion/runs/` — JSON + Markdown logs created automatically

---

## Quick Start

### 1) Install dependencies

```powershell
py -m pip install -r multi_agent_discussion/requirements.txt
```

### 2) Set API keys in PowerShell

```powershell
$env:OPENAI_API_KEY="your-openai-key"
$env:ANTHROPIC_API_KEY="your-anthropic-key"
```

Optional model overrides:

```powershell
$env:OPENAI_MODEL="gpt-4o"
$env:ANTHROPIC_MODEL="claude-opus-4-5"
$env:DEBATE_MAX_ITERATIONS="4"
```

### 3) Run a real debate

```powershell
py multi_agent_discussion/controller.py `
  --task "Design a secure multi-tenant file upload architecture" `
  --iterations 4 `
  --with-judge
```

### 4) Run a local dry test

```powershell
py multi_agent_discussion/controller.py `
  --task "Create a release checklist for a VS Code extension" `
  --iterations 3 `
  --with-judge `
  --dry-run
```

---

## Input Options

You can pass a direct prompt:

```powershell
py multi_agent_discussion/controller.py --task "Explain how to roll out feature flags safely"
```

Or pass a file:

```powershell
py multi_agent_discussion/controller.py --task-file prompts/my_task.md --iterations 3
```

---

## Output

Each run creates:

- a structured `*.json` log with per-round outputs
- a human-readable `*.md` report with the final answer and critique trail

These are saved in:

```text
multi_agent_discussion/runs/
```

---

## Architecture

```text
User Input
   -> Controller
      -> gpt-4o (Strategist)
      -> claude-opus-4-5 (Critic)
      -> gpt-4o refinement
      -> repeat N times
      -> Final Output
```

---

## Notes

- **API keys stay in the backend** via environment variables.
- **Iterations are capped** to control cost and latency.
- **Convergence checking** stops early if the strategist answer stabilizes.
- The **Judge role** is optional.

If you want a web UI or VS Code panel next, this controller can be used as the backend engine.

---

## SIARC integration

The same debate engine now plugs into `siarc.py` as an optional **Agent D** upgrade.

### Dry-run integration test

```powershell
py siarc.py --agent D --input siarc_outputs/agent_C_out.json --debate-critic --debate-dry-run
```

### Full-chain run with the debate critic enabled

```powershell
py siarc.py --agent full --cycles 1 --debate-critic --debate-dry-run
```

### Exponential / swarm search mode

```powershell
py siarc.py --agent full --cycles 1 --debate-critic --debate-dry-run --debate-swarm --swarm-size 6 --swarm-survivors 2
```

> Swarm mode now includes **Active Symbolic Refinement (ASR)** via `sympy` + `scipy.optimize`, so near-miss survivors can be coefficient-calibrated before the Red-Team / LFI pass.

### Live API mode

```powershell
py siarc.py --agent full --cycles 1 --debate-critic --debate-live --debate-judge
```
