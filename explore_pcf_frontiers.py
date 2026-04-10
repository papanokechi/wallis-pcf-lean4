#!/usr/bin/env python3
"""
PCF Frontier Explorer
=====================
Systematic exploration of three research frontiers using the
Ramanujan Breakthrough Generator's PCFEngine:

  Part A — Parametric Generalization (d=3→d=5, log ladder, hypergeometric bridge)
  Part B — Discriminant-based Quadratic CFs (Heegner numbers -11,-19,-43,-67,-163)
  Part C — Discovery Methodology (modular signature sweep, PSLQ exclusion signatures)

Uses: ramanujan_breakthrough_generator.PCFEngine
"""
from __future__ import annotations

import itertools
import json
import math
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import mpmath
from mpmath import mp, mpf, pi, zeta, log, sqrt, euler, catalan

# Import the engine from the breakthrough generator
sys.path.insert(0, ".")
from ramanujan_breakthrough_generator import PCFEngine, poly_to_str

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

PRECISION = 50
mp.dps = PRECISION + 30

# Extended constant library for matching
EXTENDED_CONSTANTS = {
    "pi":        pi,
    "e":         mpmath.e,
    "zeta3":     zeta(3),
    "zeta5":     zeta(5),
    "zeta7":     zeta(7),
    "catalan":   catalan,
    "ln2":       log(2),
    "ln3":       log(3),
    "ln5":       log(5),
    "sqrt2":     sqrt(2),
    "sqrt3":     sqrt(3),
    "sqrt5":     sqrt(5),
    "phi":       (1 + sqrt(5)) / 2,
    "euler":     euler,
    "pi2":       pi**2,
    "pi2_6":     pi**2 / 6,       # = zeta(2)
    "1/pi":      1 / pi,
    "4/pi":      4 / pi,
    "pi/4":      pi / 4,
    "Li2_1/2":   mpmath.polylog(2, mpf(1)/2),  # Li_2(1/2)
    "G":         catalan,         # Catalan's G
    "Apery":     zeta(3),
}


@dataclass
class Discovery:
    part: str
    family: str
    alpha_coeffs: list
    beta_coeffs: list
    value: str
    matched_constant: str
    formula: str
    digits: int
    convergence: str
    factorial_reduction: bool
    notes: str


results: list[Discovery] = []
engine = PCFEngine(precision=PRECISION)


def banner(title: str):
    w = 72
    print(f"\n{'═' * w}")
    print(f" {title}")
    print(f"{'═' * w}")


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f" {title}")
    print(f"{'─' * 60}")


def match_extended(value, min_digits: int = 15) -> list[tuple[str, str, int]]:
    """Try matching value against extended constant library with rational multiples."""
    if value is None:
        return []
    hits = []
    tol = mpf(10) ** (-min_digits)
    for name, const_val in EXTENDED_CONSTANTS.items():
        if const_val == 0:
            continue
        for p in range(-8, 9):
            if p == 0:
                continue
            for q in range(1, 9):
                # value ≈ (p/q) * const
                trial = mpf(p) / q * const_val
                diff = abs(value - trial)
                if diff < tol and diff > 0:
                    digs = min(int(-mpmath.log10(diff)), PRECISION)
                    if digs >= min_digits:
                        frac = f"{p}/{q}" if q != 1 else str(p)
                        hits.append((name, f"{frac} * {name}", digs))
                elif diff == 0:
                    frac = f"{p}/{q}" if q != 1 else str(p)
                    hits.append((name, f"{frac} * {name}", PRECISION))
                # value ≈ const / (p/q) = q*const/p
                if p != 0:
                    trial2 = mpf(q) / p * const_val
                    diff2 = abs(value - trial2)
                    if diff2 > 0 and diff2 < tol:
                        digs2 = min(int(-mpmath.log10(diff2)), PRECISION)
                        if digs2 >= min_digits:
                            frac = f"{p}/{q}" if q != 1 else str(p)
                            hits.append((name, f"{name} / ({frac})", digs2))
    # Deduplicate by formula
    seen = set()
    unique = []
    for h in sorted(hits, key=lambda x: -x[2]):
        if h[1] not in seen:
            seen.add(h[1])
            unique.append(h)
    return unique[:5]


# ═══════════════════════════════════════════════════════════════════════════════
# PART A: PARAMETRIC GENERALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def part_a():
    banner("PART A: PARAMETRIC GENERALIZATION")

    # ── A1: Verify known families ──
    section("A1: Verify Known Families")

    # Logarithmic ladder: a(n) = -k*n^2,  b(n) = (k+1)*n + k  →  1/ln(k/(k-1))
    print("\n  Logarithmic Ladder Family: a(n) = -k*n², b(n) = (k+1)n + k")
    print(f"  {'k':>3}  {'Expected':>20}  {'PCF value':>20}  {'Digits':>6}  {'Match':>5}")
    print(f"  {'─'*3}  {'─'*20}  {'─'*20}  {'─'*6}  {'─'*5}")

    for k in range(2, 15):
        # a(n) = -k*n^2  → coeffs [0, 0, -k]
        # b(n) = (k+1)*n + k → coeffs [k, k+1]
        alpha_c = [0, 0, -k]
        beta_c = [k, k + 1]
        expected = 1 / log(mpf(k) / (k - 1))
        val, err, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=500)
        if val is not None:
            diff = abs(val - expected)
            digs = int(-mpmath.log10(diff)) if diff > 0 else PRECISION
            ok = "✓" if digs >= 30 else "✗"
            print(f"  {k:3d}  {float(expected):20.12f}  {float(val):20.12f}  {digs:6d}  {ok:>5}")
            if digs >= 30:
                results.append(Discovery(
                    part="A", family="log_ladder", alpha_coeffs=alpha_c, beta_coeffs=beta_c,
                    value=str(val)[:40], matched_constant=f"1/ln({k}/{k-1})",
                    formula=f"a(n)=-{k}n², b(n)={(k+1)}n+{k}",
                    digits=digs, convergence="polynomial", factorial_reduction=False,
                    notes=f"Logarithmic ladder k={k}"
                ))

    # Pi family d=3: a(n) = -n(2n-(2m+1)),  b(n) = 3n+1
    section("A2: Pi Family (d=3): a(n) = -n(2n-(2m+1)), b(n) = 3n+1")
    print(f"  {'m':>3}  {'PCF value':>20}  {'Match':>30}  {'Digits':>6}")
    print(f"  {'─'*3}  {'─'*20}  {'─'*30}  {'─'*6}")

    for m in range(-3, 8):
        # a(n) = -n * (2n - (2m+1)) = -(2n^2 - (2m+1)n) = (2m+1)n - 2n^2
        # coeffs: [0, (2m+1), -2]
        alpha_c = [0, 2 * m + 1, -2]
        beta_c = [1, 3]
        val, err, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=500)
        if val is not None and abs(val) > 1e-10 and abs(val) < 1e10:
            hits = match_extended(val, 20)
            best = hits[0] if hits else ("?", "?", 0)
            print(f"  {m:3d}  {float(val):20.12f}  {best[1]:>30}  {best[2]:6d}")
            if best[2] >= 20:
                results.append(Discovery(
                    part="A", family="pi_d3", alpha_coeffs=alpha_c, beta_coeffs=beta_c,
                    value=str(val)[:40], matched_constant=best[1],
                    formula=f"a(n)=-n(2n-{2*m+1}), b(n)=3n+1",
                    digits=best[2], convergence="polynomial", factorial_reduction=False,
                    notes=f"Pi family d=3, m={m}"
                ))

    # ── A3: d=4 exploration ──
    section("A3: d=4 Search — b(n) = 4n+c₀, a(n) quadratic")
    print("  Searching a(n) = a₂n² + a₁n, b(n) = 4n + c₀ ...")
    print(f"  {'a₂':>4} {'a₁':>4} {'c₀':>4}  {'PCF value':>20}  {'Match':>30}  {'Dig':>4}")

    d4_hits = 0
    for a2 in range(-5, 6):
        for a1 in range(-5, 6):
            if a2 == 0 and a1 == 0:
                continue
            for c0 in range(0, 4):
                alpha_c = [0, a1, a2]
                beta_c = [c0, 4]
                try:
                    val, err, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=150)
                    if val is None or abs(val) > 1e8 or abs(val) < 1e-8:
                        continue
                    hits = match_extended(val, 20)
                    if hits:
                        best = hits[0]
                        print(f"  {a2:4d} {a1:4d} {c0:4d}  {float(val):20.12f}  {best[1]:>30}  {best[2]:4d}")
                        d4_hits += 1
                        results.append(Discovery(
                            part="A", family="d4_search", alpha_coeffs=alpha_c, beta_coeffs=beta_c,
                            value=str(val)[:40], matched_constant=best[1],
                            formula=f"a(n)={a2}n²+{a1}n, b(n)=4n+{c0}",
                            digits=best[2], convergence="unknown", factorial_reduction=False,
                            notes=f"d=4 family search hit"
                        ))
                except Exception:
                    continue
    print(f"  → d=4 total hits: {d4_hits}")

    # ── A4: d=5 exploration ──
    section("A4: d=5 Search — b(n) = 5n+c₀, a(n) quadratic")
    print("  Searching a(n) = a₂n² + a₁n, b(n) = 5n + c₀ ...")
    print(f"  {'a₂':>4} {'a₁':>4} {'c₀':>4}  {'PCF value':>20}  {'Match':>30}  {'Dig':>4}")

    d5_hits = 0
    for a2 in range(-5, 6):
        for a1 in range(-5, 6):
            if a2 == 0 and a1 == 0:
                continue
            for c0 in range(0, 5):
                alpha_c = [0, a1, a2]
                beta_c = [c0, 5]
                try:
                    val, err, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=150)
                    if val is None or abs(val) > 1e8 or abs(val) < 1e-8:
                        continue
                    hits = match_extended(val, 20)
                    if hits:
                        best = hits[0]
                        print(f"  {a2:4d} {a1:4d} {c0:4d}  {float(val):20.12f}  {best[1]:>30}  {best[2]:4d}")
                        d5_hits += 1
                        results.append(Discovery(
                            part="A", family="d5_search", alpha_coeffs=alpha_c, beta_coeffs=beta_c,
                            value=str(val)[:40], matched_constant=best[1],
                            formula=f"a(n)={a2}n²+{a1}n, b(n)=5n+{c0}",
                            digits=best[2], convergence="unknown", factorial_reduction=False,
                            notes=f"d=5 family search hit"
                        ))
                except Exception:
                    continue
    print(f"  → d=5 total hits: {d5_hits}")

    # ── A5: Hypergeometric Bridge Search ──
    section("A5: Hypergeometric Bridge — unifying log ladder and pi family")
    print("  Testing a(n) = α₂n² + α₁n, b(n) = dn + c₀ for d=2..6")
    print("  Looking for constants matching BOTH log-type and pi-type...")

    bridge_hits = []
    for d_val in range(2, 7):
        for c0 in range(0, d_val + 1):
            for a2 in range(-5, 6):
                for a1 in range(-5, 6):
                    if a2 == 0 and a1 == 0:
                        continue
                    alpha_c = [0, a1, a2]
                    beta_c = [c0, d_val]
                    try:
                        val, err, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=100)
                        if val is None or abs(val) > 1e6 or abs(val) < 1e-6:
                            continue
                        hits = match_extended(val, 25)
                        if hits and hits[0][2] >= 25:
                            best = hits[0]
                            bridge_hits.append((d_val, c0, a2, a1, float(val), best[1], best[2]))
                    except Exception:
                        continue

    # Print unique bridges (constants that appear for multiple d values)
    from collections import Counter
    const_counts = Counter(h[5] for h in bridge_hits)
    multi_d = {c for c, cnt in const_counts.items() if cnt >= 2}
    print(f"\n  Constants appearing across multiple d-values:")
    for const in sorted(multi_d):
        entries = [h for h in bridge_hits if h[5] == const]
        d_vals = sorted(set(h[0] for h in entries))
        print(f"    {const}: d ∈ {d_vals}")
        for h in entries[:3]:
            print(f"      d={h[0]}, c₀={h[1]}, a₂={h[2]}, a₁={h[3]} → {h[4]:.12f} ({h[6]}d)")

    # ── A6: Higher-degree a(n) for zeta(3), Catalan ──
    section("A6: Cubic a(n) search for ζ(3) and Catalan's G")
    print("  a(n) = a₃n³ + a₂n² + a₁n, b(n) = dn + c₀")

    for target_name, target_val, target_str in [
        ("zeta3", zeta(3), "ζ(3)"),
        ("catalan", catalan, "G"),
    ]:
        print(f"\n  Target: {target_str}")
        for d_val in [3, 4, 5]:
            for c0 in range(0, min(d_val + 1, 4)):
                for a3 in range(-2, 3):
                    for a2 in range(-2, 3):
                        for a1 in range(-2, 3):
                            if a3 == 0 and a2 == 0 and a1 == 0:
                                continue
                            alpha_c = [0, a1, a2, a3]
                            beta_c = [c0, d_val]
                            try:
                                val, err, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=100)
                                if val is None or abs(val) > 1e6 or abs(val) < 1e-6:
                                    continue
                                # Check rational multiples of target
                                for p in range(-8, 9):
                                    if p == 0:
                                        continue
                                    for q in range(1, 9):
                                        diff = abs(val - mpf(p)/q * target_val)
                                        if diff > 0 and diff < mpf(10)**(-25):
                                            digs = int(-mpmath.log10(diff))
                                            frac = f"{p}/{q}" if q != 1 else str(p)
                                            print(f"    d={d_val} c₀={c0} a=[{a1},{a2},{a3}]: "
                                                  f"{frac}*{target_str} ({digs}d)")
                                            results.append(Discovery(
                                                part="A", family=f"cubic_{target_name}",
                                                alpha_coeffs=alpha_c, beta_coeffs=beta_c,
                                                value=str(val)[:40],
                                                matched_constant=f"{frac}*{target_str}",
                                                formula=f"a(n)={a3}n³+{a2}n²+{a1}n, b(n)={d_val}n+{c0}",
                                                digits=digs, convergence="unknown",
                                                factorial_reduction=False,
                                                notes=f"Cubic numerator for {target_str}"
                                            ))
                            except Exception:
                                continue


# ═══════════════════════════════════════════════════════════════════════════════
# PART B: DISCRIMINANT-BASED QUADRATIC CONTINUED FRACTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def eval_quadratic_cf(a_lin: int, a_const: int, b_lin: int, b_const: int,
                      depth: int = 1000) -> tuple:
    """
    Evaluate quadratic CF:  b₀ + a₁/(b₁ + a₂/(b₂ + ...))
    where a(n) = a_lin*n + a_const, b(n) = b_lin*n + b_const
    Returns (value, discriminant, last_error).
    """
    with mpmath.workdps(PRECISION + 30):
        p_prev, p_curr = mpf(1), mpf(b_const)
        q_prev, q_curr = mpf(0), mpf(1)
        prev_val = None
        for n in range(1, depth + 1):
            a_n = mpf(a_lin * n + a_const)
            b_n = mpf(b_lin * n + b_const)
            p_new = b_n * p_curr + a_n * p_prev
            q_new = b_n * q_curr + a_n * q_prev
            p_prev, p_curr = p_curr, p_new
            q_prev, q_curr = q_curr, q_new
        if q_curr == 0:
            return None, None, None
        val = p_curr / q_curr
        # Discriminant of the quadratic n → (a_lin*n + a_const)/(b_lin*n + b_const)
        # For a(n)/b(n) as n→∞ the CF has quadratic character with disc = b_lin² + 4*a_lin
        disc = b_lin**2 + 4 * a_lin
        # Error from second-to-last convergent
        p_check = b_lin * (depth - 1) + b_const
        err = None
        return val, disc, err


def part_b():
    banner("PART B: DISCRIMINANT-BASED QUADRATIC CFs (HEEGNER NUMBERS)")

    # Heegner discriminants → class number 1 imaginary quadratic fields
    # -3, -4, -7, -8, -11, -19, -43, -67, -163
    heegner_discs = [-3, -4, -7, -8, -11, -19, -43, -67, -163]

    # For disc = b² + 4a, we parameterize:
    # Given target disc D, choose b_lin, compute a_lin = (D - b_lin²)/4
    # Need a_lin integer → D ≡ b_lin² (mod 4)

    section("B1: Quadratic CFs for each Heegner discriminant")
    print(f"  {'Disc':>5}  {'b_l':>4} {'a_l':>5} {'b_c':>4} {'a_c':>4}  "
          f"{'Value':>20}  {'Match':>30}  {'Dig':>4}")

    heegner_hits = []

    for D in heegner_discs:
        found_for_D = 0
        for b_lin in range(-4, 5):
            if b_lin == 0:
                continue
            remainder = D - b_lin * b_lin
            if remainder % 4 != 0:
                continue
            a_lin = remainder // 4
            if a_lin == 0:
                continue

            for b_const in range(0, 5):
                for a_const in range(-3, 4):
                    try:
                        val, err, _ = eval_quadratic_cf(a_lin, a_const, b_lin, b_const, depth=400)
                        if val is None or abs(val) > 1e8 or abs(val) < 1e-8:
                            continue
                        hits = match_extended(val, 15)
                        if hits:
                            best = hits[0]
                            if best[2] >= 15:
                                print(f"  {D:5d}  {b_lin:4d} {a_lin:5d} {b_const:4d} {a_const:4d}  "
                                      f"{float(val):20.12f}  {best[1]:>30}  {best[2]:4d}")
                                heegner_hits.append((D, b_lin, a_lin, b_const, a_const,
                                                     float(val), best[1], best[2]))
                                found_for_D += 1
                                results.append(Discovery(
                                    part="B", family=f"heegner_D{abs(D)}",
                                    alpha_coeffs=[a_const, a_lin],
                                    beta_coeffs=[b_const, b_lin],
                                    value=str(val)[:40], matched_constant=best[1],
                                    formula=f"a(n)={a_lin}n+{a_const}, b(n)={b_lin}n+{b_const} [D={D}]",
                                    digits=best[2], convergence="unknown",
                                    factorial_reduction=False,
                                    notes=f"Heegner disc D={D}"
                                ))
                    except Exception:
                        continue
            if found_for_D >= 20:
                break  # enough for this discriminant

    # ── B2: PSLQ exclusion for unmatched values ──
    section("B2: Unmatched quadratic CF values — PSLQ exclusion test")
    print("  Testing values that don't match known constants...")
    print("  (looking for potential NEW transcendental constants)\n")

    new_candidates = []
    for D in heegner_discs:
        for b_lin in range(-3, 4):
            if b_lin == 0:
                continue
            remainder = D - b_lin * b_lin
            if remainder % 4 != 0:
                continue
            a_lin = remainder // 4
            if a_lin == 0:
                continue

            for b_const in [1, 2, 3]:
                for a_const in [0, 1, -1]:
                    try:
                        val, disc, _ = eval_quadratic_cf(a_lin, a_const, b_lin, b_const, depth=500)
                        if val is None or abs(val) > 100 or abs(val) < 0.01:
                            continue
                        hits = match_extended(val, 12)
                        if not hits:
                            # This value doesn't match any known constant — candidate!
                            # Run PSLQ against a basis of known constants
                            basis_names = ["1", "π", "ln2", "ζ(3)", "G", "√2", "e", "γ"]
                            basis_vals = [mpf(1), pi, log(2), zeta(3), catalan,
                                          sqrt(2), mpmath.e, euler]
                            pslq_vec = [val] + basis_vals
                            try:
                                rel = mpmath.pslq(pslq_vec, maxcoeff=10000, tol=mpf(10)**(-40))
                            except Exception:
                                rel = None
                            if rel is None:
                                # No integer relation found — genuinely new?
                                new_candidates.append({
                                    "disc": D, "b_lin": b_lin, "a_lin": a_lin,
                                    "b_const": b_const, "a_const": a_const,
                                    "value": str(val)[:50],
                                })
                                print(f"  ★ NEW? D={D}, a(n)={a_lin}n+{a_const}, "
                                      f"b(n)={b_lin}n+{b_const}")
                                print(f"         val = {str(val)[:50]}")
                                print(f"         PSLQ found NO relation with "
                                      f"{{1,π,ln2,ζ(3),G,√2,e,γ}}")
                                results.append(Discovery(
                                    part="B", family=f"NEW_heegner_D{abs(D)}",
                                    alpha_coeffs=[a_const, a_lin],
                                    beta_coeffs=[b_const, b_lin],
                                    value=str(val)[:50],
                                    matched_constant="NONE (potential new constant)",
                                    formula=f"a(n)={a_lin}n+{a_const}, b(n)={b_lin}n+{b_const} [D={D}]",
                                    digits=0, convergence="unknown",
                                    factorial_reduction=False,
                                    notes=f"PSLQ exclusion: no relation in span{{1,π,ln2,ζ(3),G,√2,e,γ}}"
                                ))
                            else:
                                # Relation found — express it
                                terms = []
                                for i, (c, name) in enumerate(zip(rel, ["val"] + basis_names)):
                                    if c != 0:
                                        terms.append(f"{c}*{name}")
                                relstr = " + ".join(terms) + " = 0"
                                # Only print if nontrivial
                                if abs(rel[0]) > 0 and any(abs(r) > 0 for r in rel[1:]):
                                    pass  # known relation, skip
                    except Exception:
                        continue

    print(f"\n  Total NEW constant candidates: {len(new_candidates)}")

    # ── B3: Wronskian-based linear independence check ──
    section("B3: Wronskian Structure Analysis")
    print("  Computing Wronskian determinants W(p_n, q_n) for Heegner CFs...")

    for D in [-11, -19, -43, -67, -163]:
        best_params = None
        for b_lin in range(1, 4):
            remainder = D - b_lin * b_lin
            if remainder % 4 != 0:
                continue
            a_lin = remainder // 4
            if a_lin == 0:
                continue
            best_params = (a_lin, 0, b_lin, 1)
            break
        if best_params is None:
            continue

        a_lin, a_const, b_lin, b_const = best_params
        print(f"\n  D = {D}: a(n)={a_lin}n+{a_const}, b(n)={b_lin}n+{b_const}")

        # Compute convergents and Wronskian
        with mpmath.workdps(PRECISION + 30):
            p_prev, p_curr = mpf(1), mpf(b_const)
            q_prev, q_curr = mpf(0), mpf(1)
            wronskians = []
            for n in range(1, 201):
                a_n = mpf(a_lin * n + a_const)
                b_n = mpf(b_lin * n + b_const)
                p_new = b_n * p_curr + a_n * p_prev
                q_new = b_n * q_curr + a_n * q_prev
                # Wronskian W_n = p_n * q_{n-1} - p_{n-1} * q_n
                W_n = p_curr * q_prev - p_prev * q_curr
                wronskians.append(float(abs(W_n)) if W_n != 0 else 0)
                p_prev, p_curr = p_curr, p_new
                q_prev, q_curr = q_curr, q_new

            # Check Wronskian growth pattern
            nonzero_w = [w for w in wronskians if w > 0]
            if len(nonzero_w) >= 10:
                # Check if |W_n| = product of |a_k| (standard for CFs)
                log_w = [math.log(max(w, 1e-300)) for w in nonzero_w[-20:]]
                growth_rate = (log_w[-1] - log_w[0]) / len(log_w) if len(log_w) > 1 else 0
                print(f"    |W_n| growth rate (per step): {growth_rate:.4f}")
                print(f"    |W_200| ≈ {wronskians[-1]:.4e}")
                if growth_rate > 0:
                    print(f"    → Wronskian DIVERGES (growth > 0): strong irrationality evidence")
                else:
                    print(f"    → Wronskian bounded or decays")


# ═══════════════════════════════════════════════════════════════════════════════
# PART C: DISCOVERY METHODOLOGY
# ═══════════════════════════════════════════════════════════════════════════════

def part_c():
    banner("PART C: DISCOVERY METHODOLOGY")

    # ── C1: Modular Signature Sweep ──
    section("C1: Modular Signature Sweep")
    print("  Strategy: prioritize a(n) that produce vanishing determinants")
    print("  or convergent interlacing patterns.\n")

    # Compute the 'modular signature' of a PCF: the sequence of signs of
    # (convergent_{n} - convergent_{n-1}), which reveals interlacing structure
    targets = {
        "pi": pi, "zeta3": zeta(3), "catalan": catalan,
        "ln2": log(2), "e": mpmath.e
    }

    signature_map = {}  # signature → [(alpha, beta, target, digits)]
    tested = 0
    sweep_hits = 0

    print("  Sweeping d=2..5, quadratic a(n), checking modular signatures...")
    for d_val in range(2, 6):
        for c0 in range(0, d_val):
            for a2 in range(-3, 4):
                for a1 in range(-3, 4):
                    if a2 == 0 and a1 == 0:
                        continue
                    alpha_c = [0, a1, a2]
                    beta_c = [c0, d_val]
                    tested += 1

                    try:
                        val, err, convergents = engine.evaluate_pcf(alpha_c, beta_c, depth=200)
                        if val is None or len(convergents) < 5:
                            continue
                        if abs(val) > 1e6 or abs(val) < 1e-6:
                            continue

                        # Compute signature: signs of successive differences
                        diffs = [convergents[i] - convergents[i-1]
                                 for i in range(1, len(convergents))]
                        sig = tuple(1 if d > 0 else -1 for d in diffs[:8])

                        # Check if this matches any known constant
                        for tname, tval in targets.items():
                            for p in range(-6, 7):
                                if p == 0:
                                    continue
                                for q in range(1, 7):
                                    diff = abs(val - mpf(p)/q * tval)
                                    if diff > 0 and diff < mpf(10)**(-25):
                                        digs = int(-mpmath.log10(diff))
                                        frac = f"{p}/{q}" if q != 1 else str(p)
                                        key = sig
                                        if key not in signature_map:
                                            signature_map[key] = []
                                        signature_map[key].append(
                                            (alpha_c[:], beta_c[:], f"{frac}*{tname}", digs))
                                        sweep_hits += 1
                    except Exception:
                        continue

    print(f"  Tested: {tested}, Hits: {sweep_hits}")
    print(f"  Unique signatures with hits: {len(signature_map)}")

    # Find signatures that yield MULTIPLE different constants
    print("\n  Productive signatures (yield ≥2 distinct constants):")
    for sig, entries in sorted(signature_map.items(), key=lambda x: -len(x[1])):
        const_names = set(e[2].split("*")[-1] if "*" in e[2] else e[2] for e in entries)
        if len(const_names) >= 2:
            sig_str = "".join("+" if s > 0 else "-" for s in sig)
            print(f"    sig={sig_str} → {len(entries)} hits, "
                  f"constants: {', '.join(sorted(const_names))}")
            for e in entries[:3]:
                print(f"      α={e[0]} β={e[1]} → {e[2]} ({e[3]}d)")

    # ── C2: PSLQ Exclusion-based "Signature of Newness" ──
    section("C2: PSLQ Exclusion — Signature of Newness")
    print("  For each hit from Part A d=4/d=5, test PSLQ exclusion depth.\n")
    print("  A value with no PSLQ relation at high coeff bound = 'more novel'\n")

    # Collect all unmatched PCF values and test PSLQ at increasing bounds
    novelty_scores = []
    test_params = [
        # (alpha, beta, desc) — from known productive regions
        ([0, -2, -3], [1, 4], "d=4 sample 1"),
        ([0, 3, -2], [2, 4], "d=4 sample 2"),
        ([0, -1, -4], [1, 5], "d=5 sample 1"),
        ([0, 2, -3], [3, 5], "d=5 sample 2"),
        ([0, -5, 1], [1, 3], "d=3 sample"),
        ([0, 1, -6], [0, 4], "d=4 extreme"),
    ]

    for alpha_c, beta_c, desc in test_params:
        try:
            val, err, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=500)
            if val is None or abs(val) > 1e6:
                continue

            # Escalating PSLQ
            basis = [val, mpf(1), pi, log(2), zeta(3), catalan, sqrt(2), mpmath.e, euler]
            max_bound_passed = 0
            for bound in [100, 1000, 5000, 10000]:
                try:
                    rel = mpmath.pslq(basis, maxcoeff=bound, tol=mpf(10)**(-50))
                    if rel is not None:
                        break
                    max_bound_passed = bound
                except Exception:
                    max_bound_passed = bound

            novelty_score = max_bound_passed
            novelty_scores.append((desc, alpha_c, beta_c, float(val), novelty_score))
            status = "★ NOVEL" if novelty_score >= 5000 else "○ known" if novelty_score == 0 else "◐ borderline"
            print(f"  {desc:20s}: val={float(val):16.10f}  "
                  f"PSLQ-exclusion≥{novelty_score:>6}  {status}")
        except Exception as e:
            print(f"  {desc:20s}: error — {e}")

    # ── C3: Convergence Rate Comparison ──
    section("C3: Convergence Rate Comparison across discriminants")
    print("  Comparing how fast quadratic CFs converge for different D values\n")

    for D in [-11, -19, -43, -67, -163]:
        for b_lin in range(1, 5):
            remainder = D - b_lin * b_lin
            if remainder % 4 != 0:
                continue
            a_lin = remainder // 4
            if a_lin == 0:
                continue

            alpha_c = [0, a_lin]
            beta_c = [1, b_lin]
            conv_type = engine.measure_convergence(alpha_c, beta_c)

            # Measure digits of convergence at various depths
            val_deep, _, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=1000)
            if val_deep is None:
                continue
            digits_at_depth = []
            for d in [50, 100, 200, 500]:
                v, _, _ = engine.evaluate_pcf(alpha_c, beta_c, depth=d)
                if v is not None:
                    diff = abs(v - val_deep)
                    digs = int(-mpmath.log10(diff)) if diff > 0 else PRECISION
                    digits_at_depth.append((d, digs))

            digs_str = "  ".join(f"d={dd}:{dg}d" for dd, dg in digits_at_depth)
            print(f"  D={D:4d}  b_l={b_lin} a_l={a_lin:3d}  "
                  f"conv={conv_type:15s}  {digs_str}")
            break  # one example per D


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    banner("PCF FRONTIER EXPLORER")
    print(f"  Precision: {PRECISION} digits")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"  Engine:    ramanujan_breakthrough_generator.PCFEngine")

    # Run all three parts
    part_a()
    part_b()
    part_c()

    # ── Summary ──
    elapsed = time.time() - t0
    banner("SUMMARY")
    print(f"  Total discoveries: {len(results)}")
    print(f"  Elapsed: {elapsed:.1f}s\n")

    # Breakdown by part
    for part_label, part_name in [("A", "Parametric Generalization"),
                                   ("B", "Heegner Discriminants"),
                                   ("C", "Discovery Methodology")]:
        part_results = [r for r in results if r.part == part_label]
        print(f"  Part {part_label} ({part_name}): {len(part_results)} discoveries")
        # Group by family
        families = {}
        for r in part_results:
            families.setdefault(r.family, []).append(r)
        for fam, entries in sorted(families.items()):
            print(f"    {fam}: {len(entries)} hits")
            for e in entries[:3]:
                print(f"      {e.formula} → {e.matched_constant} ({e.digits}d)")
            if len(entries) > 3:
                print(f"      ... and {len(entries)-3} more")

    # Novel candidates (Part B PSLQ exclusion)
    novel = [r for r in results if "NEW" in r.family]
    if novel:
        print(f"\n  ★ POTENTIAL NEW CONSTANTS ({len(novel)}):")
        for r in novel:
            print(f"    {r.formula}")
            print(f"      value = {r.value}")
            print(f"      {r.notes}")

    # Save results
    out_path = Path("pcf_frontier_results.json")
    out_data = {
        "timestamp": datetime.now().isoformat(),
        "precision": PRECISION,
        "elapsed_seconds": round(elapsed, 1),
        "total_discoveries": len(results),
        "discoveries": [asdict(r) for r in results],
    }
    out_path.write_text(json.dumps(out_data, indent=2))
    print(f"\n  Results saved → {out_path}")


if __name__ == "__main__":
    main()
