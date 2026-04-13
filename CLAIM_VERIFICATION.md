# Claim Verification Wrapper

This workspace now includes a lightweight runtime verifier for numerical-result claims:

- `verify_claim.py` — replay + validation wrapper
- `claim_schema_v1.json` — machine-readable schema
- `claim_template.json` — starting template for new claims

## Goal

Force every numerical claim to carry a minimal reproducible certificate that can be checked in under 60 seconds.

## Required fields

```json
{
  "inputs": {...},
  "raw_output": "...",
  "comparison": {...},
  "reproduce": "...",
  "evidence_class": "near_miss | numerical_identity | independently_verified | formalized",
  "environment": {...},
  "provenance": {...}
}
```

## Status codes

- `VERIFIED` — schema valid, provenance consistent, replay succeeded, output matched
- `MISMATCH` — replayed result or provenance disagrees with the claim
- `EXECUTION_FAILED` — reproduce command did not run successfully
- `SCHEMA_INVALID` — missing or inconsistent required fields

## Example usage

```powershell
c:/Users/shkub/OneDrive/Documents/archive/admin/VSCode/claude-chat/.venv/Scripts/python.exe .\verify_claim.py .\claim_template.json
```

## Notes

1. **Prompt rules are not enough.** This wrapper enforces runtime checks.
2. **`evidence_class` limits overclaiming.**
3. **`git_commit` + `implementation_hash` only help when `provenance.code_path` names the research script under audit.**
4. **Do not point `provenance.code_path` at `verify_claim.py`.** Use the producing script, e.g. `ramanujan_breakthrough_generator.py`.
5. For stronger checking, include `comparison.target_value` as a machine-evaluable expression such as `2/mp.pi`.
