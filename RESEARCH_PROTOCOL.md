# Research Integrity Protocol

This workspace uses a low-trust numerical research workflow.

## Required claim package

Any claim worth keeping must include:

- `inputs`
- `raw_output`
- `comparison`
- `reproduce`
- `evidence_class`
- `environment`
- `provenance`

## Mandatory provenance rule

`provenance.code_path` must point to the **research script that produced the computation**.

- Good: `ramanujan_breakthrough_generator.py`
- Bad: `verify_claim.py`

The hash is meant to pin the implementation under audit, not the verifier.

## Allowed claim language

Narrative strength must match `evidence_class`:

- `near_miss` → no words like `breakthrough`, `proved`, or `theorem`
- `numerical_identity` → numerical evidence only
- `independently_verified` → replay confirmed by an independent check
- `formalized` → only for actual formal proof artifacts

## Session-closing rule

Before closing a session:

1. Run `verify_claim.py` on the claim package.
2. Require `VERIFIED` before making a success claim.
3. Commit the integrity scaffold with a git-anchored message.

## Objective

Prevent parameter laundering, narrative overclaim, artifact drift, and unverifiable numerical assertions.
