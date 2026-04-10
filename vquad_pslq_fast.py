#!/usr/bin/env python3
"""
V_quad PSLQ — Fast Edition (500 dps)
═════════════════════════════════════

Practical-speed PSLQ searches against all 5 basis families.
500-digit precision is more than sufficient to detect integer relations
with coefficients ≤ 10000 (PSLQ theory: need ~N·log₁₀(H) digits
where N=basis size, H=coeff bound → 6·4 = 24 digits minimum).

For the overnight high-precision run, use vquad_pslq_2000digit.py.
"""

import sys
import time
import mpmath as mp

WORK_DPS    = 600    # working precision
CF_DEPTH    = 1500   # backward recurrence depth (gives ~500+ digits)
PSLQ_DPS    = 500    # PSLQ search precision
COEFF_BOUND = 10000

def compute_vquad(depth, dps):
    with mp.workdps(dps + 50):
        v = mp.mpf(0)
        for n in range(depth, 0, -1):
            v = mp.mpf(1) / (3*n*n + n + 1 + v)
        return mp.mpf(1) + v

def kronecker_m11(n):
    n_mod = n % 11
    if n_mod == 0: return 0
    return 1 if n_mod in {1, 3, 4, 5, 9} else -1

def dirichlet_L2_chi_m11(dps):
    with mp.workdps(dps + 50):
        result = mp.mpf(0)
        for a in range(1, 11):
            chi = kronecker_m11(a)
            if chi != 0:
                result += chi * mp.hurwitz(2, mp.mpf(a)/11)
        return result / mp.mpf(121)

def run_pslq(basis, labels, dps, coeff_bound=COEFF_BOUND):
    with mp.workdps(dps):
        t0 = time.time()
        try:
            rel = mp.pslq(basis, maxcoeff=coeff_bound, maxsteps=5000)
        except Exception as e:
            print(f"  PSLQ error: {e}")
            return False
        elapsed = time.time() - t0

    if rel is not None:
        with mp.workdps(dps):
            dot = sum(c*b for c,b in zip(rel, basis))
            residual = abs(dot)
            rd = max(0, int(-float(mp.log10(residual + mp.mpf(10)**(-dps))))) if residual > 0 else dps
        nonzero = [(c,l) for c,l in zip(rel, labels) if c != 0]
        if len(nonzero) == 1 and nonzero[0][1] == "V_quad":
            print(f"  REJECTED: trivial ({elapsed:.1f}s)")
            return False
        if rd < 50:
            print(f"  SPURIOUS: residual only {rd} digits ({elapsed:.1f}s)")
            return False
        print(f"\n  >>> INTEGER RELATION FOUND ({elapsed:.1f}s, {rd} digit residual) <<<")
        for c, l in zip(rel, labels):
            if c != 0: print(f"    {c:+d} · {l}")
        return True
    else:
        print(f"  No relation ({elapsed:.1f}s)")
        return False

def main():
    mp.mp.dps = WORK_DPS
    print("=" * 70)
    print("  V_QUAD PSLQ SEARCH — FAST EDITION (500 dps)")
    print("=" * 70)

    # ── Compute V_quad ──
    print(f"\n  Computing V_quad at depth {CF_DEPTH}...")
    t0 = time.time()
    V = compute_vquad(CF_DEPTH, WORK_DPS)
    print(f"  Done in {time.time()-t0:.2f}s")
    print(f"  V_quad = {mp.nstr(V, 30)}...")

    found_any = False

    # ═══ Search A: Core Airy/Lommel basis ═══
    print(f"\n{'─'*70}")
    print("  Search A: ₀F₂ + Chowla-Selberg + Airy + Whittaker")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        b1 = mp.hyper([], [mp.mpf(1)/3, mp.mpf(2)/3], mp.mpf(-1)/27)
        b2 = mp.gamma(mp.mpf(1)/3)**3 / (mp.power(2, mp.mpf(7)/3) * mp.pi)
        b3 = 1 / (mp.power(3, mp.mpf(7)/6) * mp.gamma(mp.mpf(2)/3)**2
                   * mp.power(2*mp.pi, mp.mpf(1)/3))
        print("  Computing Whittaker W_{1/6,1/3}(2/3)...")
        b4 = mp.whitw(mp.mpf(1)/6, mp.mpf(1)/3, mp.mpf(2)/3)
        basis_a = [Vs, b1, b2, b3, b4, mp.mpf(1)]
        labels_a = ["V_quad", "₀F₂(;1/3,2/3;-1/27)", "Γ(1/3)³/(2^{7/3}π)",
                     "∫Ai²", "W_{1/6,1/3}(2/3)", "1"]
    if run_pslq(basis_a, labels_a, PSLQ_DPS): found_any = True

    # ═══ Search B: ₀F₂ ratio hypotheses ═══
    print(f"\n{'─'*70}")
    print("  Search B: ₀F₂ ratios at different parameters")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        f1 = mp.hyper([], [mp.mpf(1)/3, mp.mpf(2)/3], mp.mpf(-1)/27)
        f2 = mp.hyper([], [mp.mpf(2)/3, mp.mpf(4)/3], mp.mpf(-1)/27)
        f3 = mp.hyper([], [mp.mpf(1)/3, mp.mpf(2)/3], mp.mpf(-4)/27)
        f4 = mp.hyper([], [mp.mpf(1)/6, mp.mpf(5)/6], mp.mpf(-1)/27)
        basis_b = [Vs, f1, f2, f3, f4, mp.mpf(1)]
        labels_b = ["V_quad", "₀F₂(;1/3,2/3;-1/27)", "₀F₂(;2/3,4/3;-1/27)",
                     "₀F₂(;1/3,2/3;-4/27)", "₀F₂(;1/6,5/6;-1/27)", "1"]
    if run_pslq(basis_b, labels_b, PSLQ_DPS): found_any = True

    # ═══ Search C: Conductor-11 / disc=-11 basis ═══
    print(f"\n{'─'*70}")
    print("  Search C: Conductor-11 (L-functions, √11, periods)")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        sqrt11 = mp.sqrt(11)
        L1 = mp.pi / sqrt11    # L(1, χ_{-11}) = π/√11
        L2 = dirichlet_L2_chi_m11(PSLQ_DPS)
        omega = mp.mpf("1.2692093042795534679296355888005553890254645702020")
        basis_c = [Vs, L1, L2, sqrt11, omega, mp.pi, mp.mpf(1)]
        labels_c = ["V_quad", "L(1,χ_{-11})", "L(2,χ_{-11})", "√11",
                     "Ω⁺(E_11a)", "π", "1"]
    if run_pslq(basis_c, labels_c, PSLQ_DPS): found_any = True

    # ═══ Search D: Airy pointwise + √11 ═══
    print(f"\n{'─'*70}")
    print("  Search D: Airy function values + conductor-11")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        ai0 = mp.airyai(0)
        ai1 = mp.airyai(1)
        bi0 = mp.airybi(0)
        basis_d = [Vs, ai0, ai1, bi0, sqrt11, mp.pi, mp.mpf(1)]
        labels_d = ["V_quad", "Ai(0)", "Ai(1)", "Bi(0)", "√11", "π", "1"]
    if run_pslq(basis_d, labels_d, PSLQ_DPS): found_any = True

    # ═══ Search E: Parabolic cylinder functions ═══
    print(f"\n{'─'*70}")
    print("  Search E: Parabolic cylinder D_ν(z)")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        z0 = mp.sqrt(mp.mpf(2)/3)
        pc1 = mp.pcfd(mp.mpf(-1)/3, z0)
        pc2 = mp.pcfd(mp.mpf(1)/3, z0)
        pc3 = mp.pcfd(mp.mpf(-2)/3, z0)
        basis_e = [Vs, pc1, pc2, pc3, b2, mp.mpf(1)]
        labels_e = ["V_quad", "D_{-1/3}(√(2/3))", "D_{1/3}(√(2/3))",
                     "D_{-2/3}(√(2/3))", "Γ(1/3)³/(2^{7/3}π)", "1"]
    if run_pslq(basis_e, labels_e, PSLQ_DPS): found_any = True

    # ═══ Search F: ₀F₂ with discriminant-matched args ═══
    print(f"\n{'─'*70}")
    print("  Search F: ₀F₂ at disc=-11 matched arguments")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        # Arguments derived from disc = 1 - 4·3·1 = -11
        # z = -disc/108 = 11/108 ≈ 0.1019
        z_disc = mp.mpf(11)/108
        g1 = mp.hyper([], [mp.mpf(1)/3, mp.mpf(2)/3], z_disc)
        g2 = mp.hyper([], [mp.mpf(1)/3, mp.mpf(2)/3], -z_disc)
        g3 = mp.hyper([], [mp.mpf(2)/3, mp.mpf(4)/3], z_disc)
        g4 = mp.hyper([], [mp.mpf(2)/3, mp.mpf(4)/3], -z_disc)
        basis_f = [Vs, g1, g2, g3, g4, mp.mpf(1)]
        labels_f = ["V_quad", "₀F₂(;1/3,2/3;11/108)", "₀F₂(;1/3,2/3;-11/108)",
                     "₀F₂(;2/3,4/3;11/108)", "₀F₂(;2/3,4/3;-11/108)", "1"]
    if run_pslq(basis_f, labels_f, PSLQ_DPS): found_any = True

    # ═══ Search G: Bessel at disc-derived args ═══
    print(f"\n{'─'*70}")
    print("  Search G: Bessel I/K at disc=-11 arguments")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        # ν=1/3 from leading coeff 3, argument from discriminant
        z_b = 2*mp.sqrt(mp.mpf(11))/mp.mpf(3*mp.sqrt(3))  # 2√11/(3√3)
        bi1 = mp.besseli(mp.mpf(1)/3, z_b)
        bi2 = mp.besseli(mp.mpf(-1)/3, z_b)
        bk1 = mp.besselk(mp.mpf(1)/3, z_b)
        basis_g = [Vs, bi1, bi2, bk1, mp.pi, mp.mpf(1)]
        labels_g = ["V_quad", "I_{1/3}(2√11/3√3)", "I_{-1/3}(2√11/3√3)",
                     "K_{1/3}(2√11/3√3)", "π", "1"]
    if run_pslq(basis_g, labels_g, PSLQ_DPS): found_any = True

    # ═══ Search H: Simple algebraic / elementary ═══
    print(f"\n{'─'*70}")
    print("  Search H: Extended elementary basis")
    print(f"{'─'*70}")
    with mp.workdps(PSLQ_DPS):
        Vs = mp.mpf(V)
        basis_h = [Vs, mp.pi, mp.pi**2, mp.euler, mp.catalan,
                   mp.log(2), mp.sqrt(11), mp.mpf(1)]
        labels_h = ["V_quad", "π", "π²", "γ", "G", "log(2)", "√11", "1"]
    if run_pslq(basis_h, labels_h, PSLQ_DPS): found_any = True

    # ═══ Summary ═══
    print("\n" + "=" * 70)
    if found_any:
        print("  >>> RELATION(S) FOUND — SEE ABOVE <<<")
    else:
        print("  NO RELATIONS FOUND across 8 basis families at 500 dps.")
        print("  V_quad = 1.19737399068... remains UNIDENTIFIED.")
        print()
        print("  Exhausted families:")
        print("    A: ₀F₂ + Chowla-Selberg + Airy norm + Whittaker")
        print("    B: ₀F₂ ratio space (4 parameter sets)")
        print("    C: Conductor-11 L-values + periods")
        print("    D: Airy pointwise + √11")
        print("    E: Parabolic cylinder functions")
        print("    F: ₀F₂ at discriminant-matched arguments")
        print("    G: Bessel I/K at discriminant-derived arguments")
        print("    H: Extended elementary constants")
        print()
        print("  Remaining targets for next iteration:")
        print("    • Lommel S_{μ,ν}(z) parametric scan")
        print("    • Weber modular functions at τ=(1+√-11)/2")
        print("    • Meijer G-functions G_{0,3}^{3,0}")
        print("    • Full L(E_11a, 2) at 2000 digits (Dokchitser)")
    print("=" * 70)

if __name__ == "__main__":
    main()
