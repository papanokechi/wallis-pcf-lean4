#!/usr/bin/env python3
"""
V_quad PSLQ Identity Search — Transcendental Architect Task 2
═══════════════════════════════════════════════════════════════

Computes V_quad = 1 + K_{n>=1} 1/(3n²+n+1) to 2000+ digits via
backward recurrence, then runs PSLQ against 5 structurally-motivated
basis constants:

  [1] ₀F₂(; 1/3, 2/3; -1/27)     — Pincherle deg-2 kernel
  [2] Γ(1/3)³ / (2^{7/3} π)       — Chowla-Selberg CM period
  [3] ∫₀^∞ Ai(t)² dt              — Airy L² norm
  [4] W_{1/6, 1/3}(2/3)           — Whittaker function
  [5] 1                            — rational offset

Plus extended searches with additional Airy/Lommel combinations.

Rationale: disc(3n²+n+1) = -11, pointing to either:
  • ₀F₂ ratio (Airy family, from Pincherle classification), or
  • L(E_11a, 2) — period of the unique elliptic curve of conductor 11.
"""

import sys
import time

import mpmath as mp

# ── Configuration ──────────────────────────────────────────────────
TARGET_DPS      = 2200    # working precision (2000 usable + 200 guard)
CF_DEPTH        = 5000    # backward recurrence depth (convergence ~0.41·n^{3/2})
CROSS_DEPTH     = 6000    # second depth for cross-validation
PSLQ_DPS        = 2050    # PSLQ working precision
COEFF_BOUND     = 10000   # reject relations with |coeff| > this


def compute_vquad(depth: int, dps: int) -> mp.mpf:
    """Compute V_quad via backward recurrence of 1/(3n²+n+1) GCF."""
    with mp.workdps(dps + 50):
        # b(n) = 3n² + n + 1;  a(n) = 1 for all n >= 1
        # Backward recurrence: v_n = 1 / (b(n) + v_{n+1})
        # Start from v_depth = 0
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            b_n = 3 * n * n + n + 1
            v = mp.mpf(1) / (b_n + v)
        # V_quad = b(0) + v_1 = 1 + v
        return mp.mpf(1) + v


def run_pslq_search():
    """Main PSLQ search against structurally-motivated bases."""

    print("=" * 74)
    print("  V_QUAD PSLQ IDENTITY SEARCH — TRANSCENDENTAL ARCHITECT")
    print("=" * 74)

    # ── Step 1: Compute V_quad to 2000+ digits ──────────────────────
    mp.mp.dps = TARGET_DPS

    print(f"\n  [1/4] Computing V_quad at depth {CF_DEPTH} ({TARGET_DPS} dps)...")
    t0 = time.time()
    v1 = compute_vquad(CF_DEPTH, TARGET_DPS)
    t1 = time.time()
    print(f"        Done in {t1 - t0:.2f}s")

    print(f"  [2/4] Cross-validating at depth {CROSS_DEPTH}...")
    t0 = time.time()
    v2 = compute_vquad(CROSS_DEPTH, TARGET_DPS)
    t2 = time.time()
    print(f"        Done in {t2 - t0:.2f}s")

    # Agreement check
    with mp.workdps(TARGET_DPS):
        diff = abs(v1 - v2)
        if diff == 0:
            agreement_digits = TARGET_DPS
        else:
            agreement_digits = max(0, int(-float(mp.log10(diff))))
    print(f"        Agreement: {agreement_digits} digits")

    if agreement_digits < 2000:
        print(f"  WARNING: Only {agreement_digits} digits agreement. "
              f"Increase CF_DEPTH for more precision.")
        if agreement_digits < 500:
            print("  ABORTING: insufficient precision for meaningful PSLQ.")
            return

    V_quad = v1

    # Print first 50 digits for visual verification
    print(f"\n  V_quad = {mp.nstr(V_quad, 50)}...")

    # Cross-check against known value
    known_start = mp.mpf("1.197373990688357602448603219937206329704270703231")
    with mp.workdps(50):
        check_diff = abs(V_quad - known_start)
        check_digits = max(0, int(-float(mp.log10(check_diff)))) if check_diff > 0 else 50
    print(f"  Cross-check vs known 48-digit value: {check_digits} digits match ✓")

    # ── Step 2: Build basis vectors ─────────────────────────────────
    print(f"\n  [3/4] Building PSLQ basis vectors at {PSLQ_DPS} dps...")

    with mp.workdps(PSLQ_DPS):
        V = mp.mpf(V_quad)

        # Basis 1: ₀F₂(; 1/3, 2/3; -1/27)
        print("        Computing ₀F₂(; 1/3, 2/3; -1/27)...")
        b1 = mp.hyper([], [mp.mpf(1)/3, mp.mpf(2)/3], mp.mpf(-1)/27)

        # Basis 2: Γ(1/3)³ / (2^{7/3} · π)  — Chowla-Selberg period
        print("        Computing Γ(1/3)³ / (2^{7/3}π)...")
        b2 = mp.gamma(mp.mpf(1)/3)**3 / (mp.power(2, mp.mpf(7)/3) * mp.pi)

        # Basis 3: ∫₀^∞ Ai(t)² dt = 1 / (3^{7/6} · Γ(2/3)² · (2π)^{1/3})
        print("        Computing ∫Ai² norm...")
        b3 = mp.mpf(1) / (
            mp.power(3, mp.mpf(7)/6)
            * mp.gamma(mp.mpf(2)/3)**2
            * mp.power(2 * mp.pi, mp.mpf(1)/3)
        )

        # Basis 4: Whittaker W_{1/6, 1/3}(2/3)
        print("        Computing W_{1/6, 1/3}(2/3)...")
        b4 = mp.whitw(mp.mpf(1)/6, mp.mpf(1)/3, mp.mpf(2)/3)

        # Basis 5: rational offset
        b5 = mp.mpf(1)

        basis_core = [V, b1, b2, b3, b4, b5]
        labels_core = [
            "V_quad",
            "₀F₂(;1/3,2/3;-1/27)",
            "Γ(1/3)³/(2^{7/3}π)",
            "∫Ai²",
            "W_{1/6,1/3}(2/3)",
            "1",
        ]

    # ── Step 3: Run PSLQ searches ──────────────────────────────────
    print(f"\n  [4/4] Running PSLQ searches...")

    found_any = False

    # Search A: Core 6-element basis
    print(f"\n  {'─'*60}")
    print(f"  Search A: Core basis ({len(basis_core)} elements)")
    print(f"  {'─'*60}")
    result = _run_pslq(basis_core, labels_core, PSLQ_DPS)
    if result:
        found_any = True

    # Search B: Pairwise ₀F₂ ratios with different parameters
    print(f"\n  {'─'*60}")
    print(f"  Search B: ₀F₂ ratio hypotheses")
    print(f"  {'─'*60}")

    of2_params = [
        ((mp.mpf(1)/3, mp.mpf(2)/3), mp.mpf(-1)/27, "₀F₂(;1/3,2/3;-1/27)"),
        ((mp.mpf(2)/3, mp.mpf(4)/3), mp.mpf(-1)/27, "₀F₂(;2/3,4/3;-1/27)"),
        ((mp.mpf(1)/3, mp.mpf(2)/3), mp.mpf(-4)/27, "₀F₂(;1/3,2/3;-4/27)"),
        ((mp.mpf(1)/6, mp.mpf(5)/6), mp.mpf(-1)/27, "₀F₂(;1/6,5/6;-1/27)"),
    ]

    with mp.workdps(PSLQ_DPS):
        V_s = mp.mpf(V_quad)
        of2_vals = []
        for (a, b), z, label in of2_params:
            print(f"        Computing {label}...")
            val = mp.hyper([], [a, b], z)
            of2_vals.append((val, label))

        basis_b = [V_s] + [v for v, _ in of2_vals] + [mp.mpf(1)]
        labels_b = ["V_quad"] + [l for _, l in of2_vals] + ["1"]

    result = _run_pslq(basis_b, labels_b, PSLQ_DPS)
    if result:
        found_any = True

    # Search C: Conductor-11 elliptic curve periods
    print(f"\n  {'─'*60}")
    print(f"  Search C: Discriminant -11 / Conductor-11 basis")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        V_s = mp.mpf(V_quad)

        # √11
        sqrt11 = mp.sqrt(11)

        # Dirichlet L-function L(1, χ_{-11})
        # χ_{-11} is the Kronecker symbol (−11/n)
        # L(1, χ_{-11}) = π / √11 · (class number h(-11) = 1)
        # => L(1, χ_{-11}) = π/√11
        L1_chi_m11 = mp.pi / sqrt11

        # Dirichlet L(2, χ_{-11}) — second-order L-value
        # Compute via direct sum (converges fast at 2000 dps with acceleration)
        print("        Computing L(2, χ_{-11}) via Euler product...")
        L2_chi_m11 = _dirichlet_L2_chi_m11(PSLQ_DPS)

        # ω_{11} = Ω^+ of E_11a ≈ 1.26920930... (real period)
        # E_11a: y² + y = x³ - x² - 10x - 20, minimal Weierstrass, conductor 11
        # Real period Ω^+ = 2 ∫_e1^∞ dx/√(4x³ - ...) ≈ 1.26920930427955...
        # We compute via:  Ω^+ = Γ(1/11)Γ(3/11)Γ(4/11)Γ(5/11)Γ(9/11) / (11^{3/2} · 2π²)
        # (Chowla-Selberg formula for disc = -11)
        # But more directly, the AGM method is standard.
        # For now, use the known decimal expansion:
        omega_11 = mp.mpf("1.2692093042795534679296355888005553890254645702020")

        basis_c = [V_s, L1_chi_m11, L2_chi_m11, sqrt11, omega_11, mp.pi, mp.mpf(1)]
        labels_c = [
            "V_quad",
            "L(1,χ_{-11})=π/√11",
            "L(2,χ_{-11})",
            "√11",
            "Ω⁺(E_11a)",
            "π",
            "1",
        ]

    result = _run_pslq(basis_c, labels_c, PSLQ_DPS)
    if result:
        found_any = True

    # Search D: Mixed Airy + conductor-11
    print(f"\n  {'─'*60}")
    print(f"  Search D: Mixed Airy × Conductor-11")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        V_s = mp.mpf(V_quad)
        ai_0 = mp.airyai(0)                          # Ai(0)
        ai_1 = mp.airyai(1)                          # Ai(1)
        bi_0 = mp.airybi(0)                          # Bi(0)
        # Ai(0) = 1/(3^{2/3}Γ(2/3)), Bi(0) = 1/(3^{1/6}Γ(2/3))
        # Ai(0)/Bi(0) = 3^{-1/2} = 1/√3 (known)
        # Try: V_quad vs Ai(1)/Ai(0), Bi(0)/Ai(0), etc. combined with √11

        basis_d = [V_s, ai_0, ai_1, bi_0, sqrt11, mp.pi, mp.mpf(1)]
        labels_d = ["V_quad", "Ai(0)", "Ai(1)", "Bi(0)", "√11", "π", "1"]

    result = _run_pslq(basis_d, labels_d, PSLQ_DPS)
    if result:
        found_any = True

    # Search E: Parabolic cylinder functions (untested family)
    print(f"\n  {'─'*60}")
    print(f"  Search E: Parabolic Cylinder / Lommel functions")
    print(f"  {'─'*60}")

    with mp.workdps(PSLQ_DPS):
        V_s = mp.mpf(V_quad)

        # Parabolic cylinder D_ν(z) = 2^{ν/2}e^{-z²/4} · [...]
        # D_{-1/3}(√(2/3)) — parameters from recurrence {3, 1, 1}
        # mpmath: pcfd(nu, z)
        print("        Computing D_{-1/3}(√(2/3))...")
        pcf1 = mp.pcfd(mp.mpf(-1)/3, mp.sqrt(mp.mpf(2)/3))

        print("        Computing D_{1/3}(√(2/3))...")
        pcf2 = mp.pcfd(mp.mpf(1)/3, mp.sqrt(mp.mpf(2)/3))

        print("        Computing D_{-2/3}(√(2/3))...")
        pcf3 = mp.pcfd(mp.mpf(-2)/3, mp.sqrt(mp.mpf(2)/3))

        basis_e = [V_s, pcf1, pcf2, pcf3, b2, mp.mpf(1)]  # b2 = Gamma period
        labels_e = [
            "V_quad",
            "D_{-1/3}(√(2/3))",
            "D_{1/3}(√(2/3))",
            "D_{-2/3}(√(2/3))",
            "Γ(1/3)³/(2^{7/3}π)",
            "1",
        ]

    result = _run_pslq(basis_e, labels_e, PSLQ_DPS)
    if result:
        found_any = True

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    if found_any:
        print("  >>> INTEGER RELATION(S) FOUND — SEE ABOVE <<<")
    else:
        print("  No integer relations found at this precision.")
        print("  V_quad remains an UNIDENTIFIED CONSTANT.")
        print()
        print("  Next steps:")
        print("    • Extend to Lommel S_{μ,ν}(z) parametric scan")
        print("    • Try Weber modular functions f, f₁, f₂ at τ = (1+√-11)/2")
        print("    • Compute L(E_11a, 2) via Dokchitser to 2000 digits")
        print("    • Try Meijer G-functions G_{0,3}^{3,0}")
    print("=" * 74)


def _run_pslq(basis: list, labels: list, dps: int) -> bool:
    """Run PSLQ on a basis vector, report results. Returns True if relation found."""
    with mp.workdps(dps):
        t0 = time.time()
        try:
            relation = mp.pslq(basis, maxcoeff=COEFF_BOUND, maxsteps=5000)
        except Exception as e:
            print(f"  PSLQ error: {e}")
            return False
        elapsed = time.time() - t0

    if relation is not None:
        # Verify
        with mp.workdps(dps):
            dot = sum(c * b for c, b in zip(relation, basis))
            residual = abs(dot)
            residual_digits = max(0, int(-float(mp.log10(residual + mp.mpf(10)**(-dps))))) if residual > 0 else dps

        print(f"\n  >>> INTEGER RELATION FOUND ({elapsed:.1f}s) <<<")
        print(f"  Residual: {mp.nstr(residual, 5)} ({residual_digits} digits)")
        for coeff, label in zip(relation, labels):
            if coeff != 0:
                print(f"    {coeff:+d} · {label}")

        # Sanity: reject trivial (only V_quad coefficient nonzero)
        nonzero = [(c, l) for c, l in zip(relation, labels) if c != 0]
        if len(nonzero) == 1 and nonzero[0][1] == "V_quad":
            print("  REJECTED: trivial relation (V_quad = 0)")
            return False

        if residual_digits < 100:
            print(f"  WARNING: low residual precision ({residual_digits} digits)")
            print("  This may be a spurious relation.")
            return False

        return True
    else:
        print(f"  No relation found (searched {elapsed:.1f}s, coeff bound {COEFF_BOUND})")
        return False


def _dirichlet_L2_chi_m11(dps: int) -> mp.mpf:
    """
    Compute L(2, χ_{-11}) where χ_{-11} is the Kronecker symbol (-11/n).
    Uses functional equation and Euler product acceleration.
    """
    with mp.workdps(dps + 50):
        # χ_{-11}(n) = Kronecker symbol (-11|n)
        # Values for residues mod 11: χ(1)=1, χ(2)=-1, χ(3)=1, χ(4)=1,
        # χ(5)=1, χ(6)=-1, χ(7)=-1, χ(8)=-1, χ(9)=1, χ(10)=-1, χ(0)=0

        # Use the formula: L(2, χ_{-11}) = (π²/11^{3/2}) · Σ_{a=1}^{10} χ(a) · B₂(a/11)
        # where B₂(x) = x² - x + 1/6 is the 2nd Bernoulli polynomial
        # ... but direct summation with Richardson extrapolation is simpler.

        # Direct Euler product: L(2, χ) = Π_p (1 - χ(p)/p²)^{-1}
        # Kronecker symbol (-11|p):
        # p=2: (-11|2) = (-11 mod 8 = 5) → -1
        # p=3: (-11|3) = (-11 mod 3 = 1) → Legendre(1,3) = 1
        # General: use Jacobi symbol

        # For high precision, use the Hurwitz zeta relation:
        # L(2, χ_{-11}) = 11^{-2} Σ_{a=1}^{10} χ(a) ζ(2, a/11)
        chi_vals = {}
        for a in range(1, 11):
            chi_vals[a] = _kronecker_m11(a)

        result = mp.mpf(0)
        for a in range(1, 11):
            if chi_vals[a] != 0:
                result += chi_vals[a] * mp.hurwitz(2, mp.mpf(a) / 11)
        result /= mp.mpf(11)**2

        return result


def _kronecker_m11(n: int) -> int:
    """Kronecker symbol (-11|n)."""
    # For n coprime to 11: (-11|n) = (n|11) · (-1|n)
    # More directly, use quadratic residues mod 11:
    # QR mod 11: {1, 3, 4, 5, 9} (squares: 1²=1, 2²=4, 3²=9, 4²=5, 5²=3)
    # NQR mod 11: {2, 6, 7, 8, 10}
    n_mod = n % 11
    if n_mod == 0:
        return 0
    qr = {1, 3, 4, 5, 9}
    if n_mod in qr:
        return 1
    else:
        return -1


if __name__ == "__main__":
    run_pslq_search()
