# AEAL Model Handoff Package
## Mandatory — complete before switching models

**Outgoing model:** [model name and version]
**Incoming model:** [model name and version]
**Reason for handoff:** [token limit / capability gap / other]
**Timestamp:** [ISO 8601]
**Git commit at handoff:** [git rev-parse --short HEAD output]

### Last verified claim
[paste claim JSON block, or write NONE]

### Current task
[one sentence, falsifiable — must contain a threshold or stopping condition]

### Capability gaps identified this session
[list, or NONE]

### Files modified this session
[paste: git diff --stat output]

### Health score at handoff
[paste: python verify_claim.py --precommit-check --health-file agent_health_history.json output]

### Prohibited actions for receiving model
- Do not implement functions not present in ramanujan_breakthrough_generator.py at commit above
- Do not report results without raw stdout attached
- Do not create summary files before underlying numbers are confirmed
- Do not use phrases: breakthrough, verified, confirmed, mission complete — unless evidence_class permits

### Context summary
[maximum 5 sentences — what has been established, what remains open]
