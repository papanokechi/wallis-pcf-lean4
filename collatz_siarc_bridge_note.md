# Collatz ↔ SIARC Bridge Note

## High-level context
SIARC v6.3 is a synthetic discovery / verification engine for modular and Borel-style candidate families. Its artifacts are computational certificates and structural witnesses that can support, but do not by themselves replace, the main Collatz drift and cycle-exclusion program.

## Portfolio distinction to preserve
- Canonical Borel witness: `K-377160-520` (6/6 structural closure on its explicit k-band).
- Portfolio-level k=24 certificate: `E-075920-439` via the resolved `K24_BOSS` gap.
- Full k>=5..24 support therefore comes from the combined SIARC portfolio, not from a single Borel descendant alone.

## External verification prior
Independent brute-force computation has verified the Collatz conjecture up to roughly `2^71 ≈ 2.36 × 10^21` as of the 2025/2026 literature. SIARC should be described as complementary structural evidence layered on top of that prior.

## Suggested next relay integration
1. Feed the SIARC gate analysis back into the reduced-map drift chain.
2. Measure the empirical distribution of ν₂(3n+1), low-valuation run lengths, and cumulative log-drift.
3. Keep a parallel cycle/Baker branch alive while formalization work proceeds in Lean.

## Ready-to-copy Round 3 prompt
```prompt
You are continuing the Collatz relay chain.

Incorporate this SIARC v6.3 handoff:
- Canonical Borel structural witness: `K-377160-520`
- k=24 certificate carried separately by `E-075920-439` and the resolved `K24_BOSS` gap
- Full coverage is portfolio-level, not single-hypothesis-level

Now continue from STAGE 2.1 (reduced-map drift). Perform STAGE 2.2 (Computational Explorer) focused on:
- empirical distribution of ν₂(3n+1)
- exponential decay of low-valuation runs
- running averages of cumulative log-drift

Then complete STAGE 2.3 and 2.4, explicitly discussing how SIARC gate-passing and K24_BOSS-style certification might support or reformulate the drift/tail bounds.
```

This note is intended as a relay handoff artifact for the Collatz branch.
