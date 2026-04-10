@echo off
REM Ramanujan Breakthrough Generator — conjecture runs
REM Generated: 20260407_071659
REM Runs: 6
REM Estimated total time: 70 min

SET GENERATOR=ramanujan_breakthrough_generator.py
SET EXPORT_DIR=rbg_runs

REM ── [CRITICAL] conjecture_proof_quick ──
REM Quick symbolic proof via Lagrange interpolation + sympy induction for m=0..5
REM ETA: ~30s
python ramanujan_breakthrough_generator.py --mode conjecture_prover --depth 200 --precision 50 --export rbg_runs\session_conjecture_proof_quick.json

REM ── [CRITICAL] conjecture_proof_deep ──
REM Extend N=500 to stress-test Lagrange polynomial fit and induction far from base cases
REM ETA: ~2 min
python ramanujan_breakthrough_generator.py --mode conjecture_prover --depth 500 --precision 50 --export rbg_runs\session_conjecture_proof_deep.json

REM ── [HIGH] hypergeometric_standard ──
REM Verify val(m) = 2Γ(m+1)/(√π·Γ(m+½)) for integer and half-integer m
REM ETA: ~3 min
python ramanujan_breakthrough_generator.py --mode hypergeometric_guess --depth 3000 --precision 100 --export rbg_runs\session_hypergeometric_standard.json

REM ── [HIGH] hypergeometric_highprec ──
REM 150-digit Γ-formula verification — publication-grade evidence for all m in paper
REM ETA: ~15 min
python ramanujan_breakthrough_generator.py --mode hypergeometric_guess --depth 5000 --precision 200 --export rbg_runs\session_hypergeometric_highprec.json

REM ── [MEDIUM] pi_family_cmf_deg3 ──
REM CMF search for new Pi Family members with degree-3 numerators (needed for m≥2)
REM ETA: ~20 min
python ramanujan_breakthrough_generator.py --mode cmf --target pi --deg-alpha 3 --deg-beta 2 --coeff-range 12 --depth 300 --precision 100 --budget 1000 --seed-boost 2 --no-ai --export rbg_runs\session_pi_family_cmf_deg3.json

REM ── [MEDIUM] pi_family_hybrid ──
REM Hybrid CMF→D&R to find π PCFs not reachable by pure CMF
REM ETA: ~30 min
python ramanujan_breakthrough_generator.py --mode hybrid --target pi --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 800 --seed-boost 3 --no-ai --export rbg_runs\session_pi_family_hybrid.json
