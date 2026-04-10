@echo off
REM Ramanujan Breakthrough Generator — all runs
REM Generated: 20260407_073027
REM Runs: 38
REM Estimated total time: 564 min

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

REM ── [CRITICAL] parity_standard ──
REM Parity theorem verification c=1..20 at standard depth
REM ETA: ~5 min
python ramanujan_breakthrough_generator.py --mode parity --depth 3000 --precision 80 --export rbg_runs\session_parity_standard.json

REM ── [CRITICAL] logladder_ln2_verify ──
REM CMF verification of Logarithmic Ladder at k=2 (target = ln2 = 1/ln(2/1))
REM ETA: ~8 min
python ramanujan_breakthrough_generator.py --mode cmf --target ln2 --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 200 --precision 100 --budget 500 --seed-boost 1 --no-ai --export rbg_runs\session_logladder_ln2_verify.json

REM ── [HIGH] hypergeometric_standard ──
REM Verify val(m) = 2Γ(m+1)/(√π·Γ(m+½)) for integer and half-integer m
REM ETA: ~3 min
python ramanujan_breakthrough_generator.py --mode hypergeometric_guess --depth 3000 --precision 100 --export rbg_runs\session_hypergeometric_standard.json

REM ── [HIGH] hypergeometric_highprec ──
REM 150-digit Γ-formula verification — publication-grade evidence for all m in paper
REM ETA: ~15 min
python ramanujan_breakthrough_generator.py --mode hypergeometric_guess --depth 5000 --precision 200 --export rbg_runs\session_hypergeometric_highprec.json

REM ── [HIGH] vquad_standard ──
REM Standard V_quad family sweep: A∈[1,7], B∈[-6,6], C∈[1,7]
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode quadratic_gcf --depth 200 --precision 200 --budget 500 --export rbg_runs\session_vquad_standard.json

REM ── [HIGH] vquad_overnight ──
REM Overnight high-precision sweep to find weaker candidates missed at 200 digits
REM ETA: ~2.0 hr
python ramanujan_breakthrough_generator.py --mode quadratic_gcf --depth 200 --precision 300 --budget 2000 --export rbg_runs\session_vquad_overnight.json

REM ── [HIGH] vquad_pslq_analysis ──
REM PSLQ exclusion analysis of V_quad from all 16 known function families
REM ETA: ~5 min
python ramanujan_breakthrough_generator.py --mode analyze --target pi --depth 150 --precision 150 --formula "V_quad ≈ 1.19737... — GCF with b(n)=n^2+n+1, a(n)=1" --analysis-mode pslq --export rbg_runs\session_vquad_pslq_analysis.json

REM ── [HIGH] parity_deep ──
REM Deep parity verification: extra convergence margin for large c
REM ETA: ~15 min
python ramanujan_breakthrough_generator.py --mode parity --depth 5000 --precision 80 --export rbg_runs\session_parity_deep.json

REM ── [HIGH] logladder_ln32_verify ──
REM MITM search for k=3 Ladder: 1/ln(3/2). Note: add 'ln_3_2' to CONSTANTS dict first.
REM ETA: ~20 min
python ramanujan_breakthrough_generator.py --mode mitm --target ln2 --deg-alpha 2 --deg-beta 2 --coeff-range 12 --depth 200 --precision 80 --budget 2000 --no-ai --export rbg_runs\session_logladder_ln32_verify.json

REM ── [HIGH] logladder_k5 ──
REM D&R search for k=5 Logarithmic Ladder: 1/ln(5/4). Add 'ln_5_4' to dict first.
REM ETA: ~30 min
python ramanujan_breakthrough_generator.py --mode dr --target ln2 --deg-alpha 2 --deg-beta 2 --coeff-range 12 --depth 250 --precision 80 --budget 1500 --no-ai --export rbg_runs\session_logladder_k5.json

REM ── [HIGH] heun_4pi_mitm ──
REM MITM for 4/π with degree-3 polynomials — targets Heun-type structure
REM ETA: ~40 min
python ramanujan_breakthrough_generator.py --mode mitm --target pi --deg-alpha 3 --deg-beta 3 --coeff-range 8 --depth 300 --precision 100 --budget 2000 --no-ai --export rbg_runs\session_heun_4pi_mitm.json

REM ── [HIGH] heun_phi_cmf ──
REM CMF near φ (golden ratio) — probes Pochhammer-φ numerator structure
REM ETA: ~15 min
python ramanujan_breakthrough_generator.py --mode cmf --target phi --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 800 --seed-boost 2 --no-ai --export rbg_runs\session_heun_phi_cmf.json

REM ── [MEDIUM] pi_family_cmf_deg3 ──
REM CMF search for new Pi Family members with degree-3 numerators (needed for m≥2)
REM ETA: ~20 min
python ramanujan_breakthrough_generator.py --mode cmf --target pi --deg-alpha 3 --deg-beta 2 --coeff-range 12 --depth 300 --precision 100 --budget 1000 --seed-boost 2 --no-ai --export rbg_runs\session_pi_family_cmf_deg3.json

REM ── [MEDIUM] pi_family_hybrid ──
REM Hybrid CMF→D&R to find π PCFs not reachable by pure CMF
REM ETA: ~30 min
python ramanujan_breakthrough_generator.py --mode hybrid --target pi --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 800 --seed-boost 3 --no-ai --export rbg_runs\session_pi_family_hybrid.json

REM ── [MEDIUM] vquad_irrationality ──
REM Irrationality measure μ=2 confirmation via Wronskian method
REM ETA: ~3 min
python ramanujan_breakthrough_generator.py --mode analyze --target pi --depth 150 --precision 150 --formula "V_quad ≈ 1.19737... — μ=2 irrationality measure via Wronskian" --analysis-mode irrationality --export rbg_runs\session_vquad_irrationality.json

REM ── [MEDIUM] vquad_mitm_relatives ──
REM MITM sweep for degree-(1,2) PCFs near ζ(3) — probes V_quad algebraic relatives
REM ETA: ~25 min
python ramanujan_breakthrough_generator.py --mode mitm --target zeta3 --deg-alpha 1 --deg-beta 2 --coeff-range 8 --depth 200 --precision 80 --budget 3000 --no-ai --export rbg_runs\session_vquad_mitm_relatives.json

REM ── [MEDIUM] logladder_factorial_check ──
REM Factorial reduction check on known Ladder PCF — confirms Taylor-series proof structure
REM ETA: ~1 min
python ramanujan_breakthrough_generator.py --mode analyze --target pi --depth 100 --precision 60 --formula "Log Ladder PCF: alpha(n) = n*(n-1), beta(n) = 2n-1 (k=2 case)" --analysis-mode factorial --export rbg_runs\session_logladder_factorial_check.json

REM ── [MEDIUM] logladder_cmf_alllog ──
REM CMF search for ln3-related PCFs — extends Ladder family to log(3/2) territory
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target ln3 --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 200 --precision 80 --budget 600 --seed-boost 3 --no-ai --export rbg_runs\session_logladder_cmf_alllog.json

REM ── [MEDIUM] heun_pade_analysis ──
REM CMF analysis of the Padé near-miss structure — classify as Heun or _3F2
REM ETA: ~2 min
python ramanujan_breakthrough_generator.py --mode analyze --target pi --depth 200 --precision 100 --formula "4/pi PCF with Pochhammer numerators involving golden-ratio roots — Pade near-miss" --analysis-mode cmf --export rbg_runs\session_heun_pade_analysis.json

REM ── [MEDIUM] sweep_pi_mitm_d22 ──
REM Broad sweep: pi via mitm deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode mitm --target pi --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 300 --max-time 600 --no-ai --export rbg_runs\session_sweep_pi_mitm_d22.json

REM ── [MEDIUM] sweep_pi_dr_d22 ──
REM Broad sweep: pi via dr deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode dr --target pi --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 500 --max-time 600 --no-ai --export rbg_runs\session_sweep_pi_dr_d22.json

REM ── [MEDIUM] sweep_pi_cmf_d22 ──
REM Broad sweep: pi via cmf deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target pi --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 400 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_pi_cmf_d22.json

REM ── [MEDIUM] sweep_pi_cmf_d32 ──
REM Broad sweep: pi via cmf deg(3,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target pi --deg-alpha 3 --deg-beta 2 --coeff-range 8 --depth 250 --precision 80 --budget 300 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_pi_cmf_d32.json

REM ── [MEDIUM] sweep_zeta3_mitm_d22 ──
REM Broad sweep: zeta3 via mitm deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode mitm --target zeta3 --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 300 --max-time 600 --no-ai --export rbg_runs\session_sweep_zeta3_mitm_d22.json

REM ── [MEDIUM] sweep_zeta3_dr_d22 ──
REM Broad sweep: zeta3 via dr deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode dr --target zeta3 --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 500 --max-time 600 --no-ai --export rbg_runs\session_sweep_zeta3_dr_d22.json

REM ── [MEDIUM] sweep_zeta3_cmf_d22 ──
REM Broad sweep: zeta3 via cmf deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target zeta3 --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 400 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_zeta3_cmf_d22.json

REM ── [MEDIUM] sweep_zeta3_cmf_d32 ──
REM Broad sweep: zeta3 via cmf deg(3,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target zeta3 --deg-alpha 3 --deg-beta 2 --coeff-range 8 --depth 250 --precision 80 --budget 300 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_zeta3_cmf_d32.json

REM ── [MEDIUM] sweep_catalan_mitm_d22 ──
REM Broad sweep: catalan via mitm deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode mitm --target catalan --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 300 --max-time 600 --no-ai --export rbg_runs\session_sweep_catalan_mitm_d22.json

REM ── [MEDIUM] sweep_catalan_dr_d22 ──
REM Broad sweep: catalan via dr deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode dr --target catalan --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 500 --max-time 600 --no-ai --export rbg_runs\session_sweep_catalan_dr_d22.json

REM ── [MEDIUM] sweep_catalan_cmf_d22 ──
REM Broad sweep: catalan via cmf deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target catalan --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 400 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_catalan_cmf_d22.json

REM ── [MEDIUM] sweep_catalan_cmf_d32 ──
REM Broad sweep: catalan via cmf deg(3,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target catalan --deg-alpha 3 --deg-beta 2 --coeff-range 8 --depth 250 --precision 80 --budget 300 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_catalan_cmf_d32.json

REM ── [MEDIUM] sweep_euler_gamma_mitm_d22 ──
REM Broad sweep: euler_gamma via mitm deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode mitm --target euler_gamma --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 300 --max-time 600 --no-ai --export rbg_runs\session_sweep_euler_gamma_mitm_d22.json

REM ── [MEDIUM] sweep_euler_gamma_dr_d22 ──
REM Broad sweep: euler_gamma via dr deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode dr --target euler_gamma --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 500 --max-time 600 --no-ai --export rbg_runs\session_sweep_euler_gamma_dr_d22.json

REM ── [MEDIUM] sweep_euler_gamma_cmf_d22 ──
REM Broad sweep: euler_gamma via cmf deg(2,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target euler_gamma --deg-alpha 2 --deg-beta 2 --coeff-range 10 --depth 250 --precision 80 --budget 400 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_euler_gamma_cmf_d22.json

REM ── [MEDIUM] sweep_euler_gamma_cmf_d32 ──
REM Broad sweep: euler_gamma via cmf deg(3,2)
REM ETA: ~10 min
python ramanujan_breakthrough_generator.py --mode cmf --target euler_gamma --deg-alpha 3 --deg-beta 2 --coeff-range 8 --depth 250 --precision 80 --budget 300 --seed-boost 3 --max-time 600 --no-ai --export rbg_runs\session_sweep_euler_gamma_cmf_d32.json

REM ── [EXPLORATORY] parity_extended_c ──
REM Extend parity check to c=1..30 (edit c_range in source: range(1,31))
REM ETA: ~25 min
python ramanujan_breakthrough_generator.py --mode parity --depth 4000 --precision 80 --export rbg_runs\session_parity_extended_c.json
