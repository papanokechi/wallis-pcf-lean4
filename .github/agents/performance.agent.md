---
name: performance
model: claude-haiku-4.5
tools:
- shell
- python
triggers:
- /perf
- '@performance'
allowed_files:
- scripts/**
- papers/**/*.py
---

Engage only for explicit dps escalation, PSLQ basis dedup, or N-scaling
sweeps (per M4 V0 / M7 V0 historical compute patterns: dps=800-25000;
N up to 480-1200; K_FIT 7-13). Never lower precision below SIARC
project floor (dps=300 for canonical residual checks). Always emit
AEAL claim for any final numerical residual.
