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
- Do not make a numerical success claim unless a claim package is replayed with verify_claim.py and returns VERIFIED
- Do not set provenance.code_path to verify_claim.py; it must point to the actual research script under audit
- Do not use stronger narrative language than the chosen evidence_class permits
- Do not close the session without rerunning the verifier and keeping the git-anchored integrity scaffold in sync

### Context summary
[maximum 5 sentences — what has been established, what remains open]
