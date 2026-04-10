RAMANUJAN PARAMETER SETS — CONJECTURE
Generated: 20260407_071659
============================================================
Total runs:          6
Estimated total:     70 min (1.2 hr)

PRIORITY SUMMARY
----------------------------------------
  CRITICAL    : 2 run(s)
  HIGH        : 2 run(s)
  MEDIUM      : 2 run(s)

RUN DETAILS
----------------------------------------

[01] conjecture_proof_quick
     Priority  : critical
     Mode      : conjecture_prover
     ETA       : ~30s
     Rationale : Quick symbolic proof via Lagrange interpolation + sympy induction for m=0..5
     Notes     : If m=1 shows PROVED, Conjecture 1 is done. Check output for status=PROVED.
     Tags      : Pi_Family, Conjecture_1, sympy, induction

[02] conjecture_proof_deep
     Priority  : critical
     Mode      : conjecture_prover
     ETA       : ~2 min
     Rationale : Extend N=500 to stress-test Lagrange polynomial fit and induction far from base cases
     Notes     : Look for no_poly_fit status — means the (2n-1)!! ansatz breaks at large n.
     Tags      : Pi_Family, Conjecture_1, verification, deep

[03] hypergeometric_standard
     Priority  : high
     Mode      : hypergeometric_guess
     ETA       : ~3 min
     Rationale : Verify val(m) = 2Γ(m+1)/(√π·Γ(m+½)) for integer and half-integer m
     Notes     : Half-integers → exact rationals; integers → π-multiples. Ratio check proves recurrence.
     Tags      : Pi_Family, Gamma_formula, hypergeometric

[04] hypergeometric_highprec
     Priority  : high
     Mode      : hypergeometric_guess
     ETA       : ~15 min
     Rationale : 150-digit Γ-formula verification — publication-grade evidence for all m in paper
     Notes     : Γ-match digits should equal precision for all m. If any < 150, increase depth.
     Tags      : Pi_Family, Gamma_formula, high_precision, publication

[05] pi_family_cmf_deg3
     Priority  : medium
     Mode      : cmf
     ETA       : ~20 min
     Rationale : CMF search for new Pi Family members with degree-3 numerators (needed for m≥2)
     Notes     : Degree-3 α(n) matches Pi Family structure for m≥2. seed_boost=2 tight around known seeds.
     Tags      : Pi_Family, CMF, deg3, new_PCF

[06] pi_family_hybrid
     Priority  : medium
     Mode      : hybrid
     ETA       : ~30 min
     Rationale : Hybrid CMF→D&R to find π PCFs not reachable by pure CMF
     Notes     : D&R phase perturbs around CMF hits; diversifies the search landscape.
     Tags      : Pi_Family, hybrid, DR, CMF

ADDING MISSING CONSTANTS
----------------------------------------
Several runs reference targets not yet in CONSTANTS dict.
Add these lines to ramanujan_breakthrough_generator.py:

  In CONSTANTS dict:
    "ln_3_2":  ("1/ln(3/2)",  "1.82047..."),
    "ln_5_4":  ("1/ln(5/4)",  "4.48142..."),
    "pi_fam1": ("2^3/(π·C(2,1))", "1.27324..."),

  In PCFEngine._get_constant():
    "ln_3_2":  mpmath.mpf(1) / mpmath.log(mpmath.mpf(3)/2),
    "ln_5_4":  mpmath.mpf(1) / mpmath.log(mpmath.mpf(5)/4),
    "pi_fam1": mpmath.mpf(8) / (mpmath.pi * 2),  # 2^3/(π·C(2,1))
