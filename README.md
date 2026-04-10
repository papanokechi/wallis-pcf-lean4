# A One-Parameter Family of Wallis-Type Polynomial Continued Fractions: Discovery and Formal Verification

This repository contains the supplementary material for the paper **"A One-Parameter Family of Wallis-Type Polynomial Continued Fractions: Discovery and Formal Verification"** (April 2026).

## Result (one paragraph)
We present a new one-parameter family of second-order polynomial continued fractions (PCFs) that evaluate exactly to reciprocal Wallis integrals. The family was discovered via a Ramanujan-Machine-style low-height search and rigorously verified with (i) symbolic recurrence normalization, (ii) a complete zero-`sorry` Lean 4 formalization based on a general intertwining lemma, and (iii) independent 1000-digit certification via backward recurrence in mpmath. The proof reduces the entire parametric tower to the classical Wallis product via an explicit affine intertwiner, providing a clean reusable pattern for similar PCF identities.

## How to run the Lean 4 proof
1. Install Lean 4[](https://lean-lang.org/).
2. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/wallis-pcf-lean4.git
   cd wallis-pcf-lean4/lean
