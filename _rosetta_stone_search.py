"""
_rosetta_stone_search.py
========================
Systematic search for new PCF families using the S^(m) bifurcation theorem
as a template. Searches for quadratic a_n, linear b_n over small integers,
flags families with exact rational inter-member ratios, maps to hypergeometric
identities, and tests half-integer / complex bifurcation parameters.

Three phases:
  Phase 1 – Heuristic grid search with "Wallis-Check" rational ratio filter
  Phase 2 – Hypergeometric mapping (₂F₁ → ₃F₂) + non-integer bifurcation
  Phase 3 – Formalization export (1000dp verification, proof sketch, cert table)

Usage:
  python _rosetta_stone_search.py                    # full pipeline
  python _rosetta_stone_search.py --phase 1          # search only
  python _rosetta_stone_search.py --phase 2          # map existing hits
  python _rosetta_stone_search.py --workers 4        # parallel workers
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import multiprocessing as mproc
import os
import platform
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from mpmath import (
        mp, mpf, nstr, pi, log, sqrt, zeta, euler, gamma, nsum, inf,
        binomial, rf, ff, hyp2f1, hyp3f2, fac, fac2, identify,
    )
    import mpmath as mpm
except ImportError:
    sys.exit("mpmath required: pip install mpmath")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ─── Constants ────────────────────────────────────────────────────────────────
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)
DISCOVERY_FILE = Path("rosetta_discoveries.jsonl")
CERT_TABLE_FILE = RESULTS_DIR / "rosetta_cert_table.json"

BATCH_SIZE = 1000            # candidates per thermal check
THERMAL_CPU_LIMIT = 92.0     # % CPU to trigger throttle
THERMAL_RAM_LIMIT = 85.0     # % RAM to trigger throttle
THERMAL_COOLDOWN = 3.0       # seconds to pause on overheat

# ─── Logging ──────────────────────────────────────────────────────────────────
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log_main = logging.getLogger("rosetta")


# ═══════════════════════════════════════════════════════════════════════════════
#  THERMAL GUARD
# ═══════════════════════════════════════════════════════════════════════════════
class ThermalGuard:
    """Monitor CPU/RAM and throttle when limits exceeded."""

    def __init__(self, cpu_limit=THERMAL_CPU_LIMIT, ram_limit=THERMAL_RAM_LIMIT):
        self.cpu_limit = cpu_limit
        self.ram_limit = ram_limit
        self.throttle_count = 0

    def check(self):
        if not HAS_PSUTIL:
            return
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        if cpu > self.cpu_limit or ram > self.ram_limit:
            self.throttle_count += 1
            time.sleep(THERMAL_COOLDOWN)

    def status(self) -> str:
        if not HAS_PSUTIL:
            return "psutil unavailable"
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        return f"CPU={cpu:.0f}% RAM={ram:.0f}% throttles={self.throttle_count}"


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE PCF EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════
def eval_pcf(a_coeffs, b_coeffs, depth=800):
    """Bottom-up evaluation of PCF b(0) + a(1)/(b(1)+a(2)/(b(2)+...))."""
    try:
        def a(n):
            return sum(mpf(c) * n**i for i, c in enumerate(a_coeffs))
        def b(n):
            return sum(mpf(c) * n**i for i, c in enumerate(b_coeffs))
        val = mpf(0)
        for n in range(depth, 0, -1):
            denom = b(n) + val
            if abs(denom) < mpf(10)**(-mp.dps + 5):
                return None
            val = a(n) / denom
        return b(0) + val
    except Exception:
        return None


def eval_pcf_convergence(a_coeffs, b_coeffs, depth=800):
    """Evaluate PCF and return (value, stable_digits) by comparing depths."""
    v1 = eval_pcf(a_coeffs, b_coeffs, depth=depth)
    if v1 is None:
        return None, 0
    v2 = eval_pcf(a_coeffs, b_coeffs, depth=depth // 2)
    if v2 is None:
        return None, 0
    diff = abs(v1 - v2)
    if diff == 0:
        return v1, mp.dps - 5
    digits = max(0, int(float(-log(diff, 10))))
    return v1, digits


def is_reasonable(val):
    if val is None:
        return False
    try:
        f = float(val)
        return math.isfinite(f) and 1e-8 < abs(f) < 1e8
    except Exception:
        return False


def is_telescoping(a_coeffs, b_coeffs, depth=200):
    """Quick check: if value ≈ b(0) at two depths, likely telescoping."""
    try:
        v1 = eval_pcf(a_coeffs, b_coeffs, depth=50)
        v2 = eval_pcf(a_coeffs, b_coeffs, depth=200)
        if v1 is None or v2 is None:
            return False
        b0 = mpf(b_coeffs[0]) if b_coeffs else mpf(0)
        if abs(v1 - b0) < mpf(10)**(-20) and abs(v2 - b0) < mpf(10)**(-20):
            return True
        return False
    except Exception:
        return False


def eval_pcf_float(a_coeffs, b_coeffs, depth=200):
    """Ultra-fast float64 PCF evaluation for prescreening."""
    try:
        def a(n):
            return sum(float(c) * n**i for i, c in enumerate(a_coeffs))
        def b(n):
            return sum(float(c) * n**i for i, c in enumerate(b_coeffs))
        val = 0.0
        for n in range(depth, 0, -1):
            denom = b(n) + val
            if abs(denom) < 1e-100:
                return None
            val = a(n) / denom
        result = b(0) + val
        if not math.isfinite(result) or abs(result) < 1e-8 or abs(result) > 1e8:
            return None
        return result
    except Exception:
        return None


def wallis_check_fast(a_template, b_coeffs, m_values=(0, 1, 2, 3)):
    """Fast float64 Wallis-Check: screen for potentially rational ratios."""
    values = {}
    for m in m_values:
        a_coeffs = [c0 + c1 * m for (c0, c1) in a_template]
        a_int = [int(round(c)) for c in a_coeffs]
        if all(c == 0 for c in a_int):
            continue
        v = eval_pcf_float(a_int, b_coeffs, depth=200)
        if v is None:
            continue
        values[m] = v

    if len(values) < 3:
        return False

    # Check if consecutive ratios look rational (within float64 tolerance)
    for m in m_values:
        if m == m_values[0]:
            continue
        if m not in values or (m - 1) not in values:
            return False
        if abs(values[m - 1]) < 1e-15:
            return False
        r = values[m] / values[m - 1]
        # Check if r ≈ p/q for small q
        found = False
        for q in range(1, 200):
            p = round(r * q)
            if p == 0:
                continue
            residual = abs(r * q - p) / abs(p)
            if residual < 1e-10:
                found = True
                break
        if not found:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  PARAMETRIC FAMILY: BIFURCATION VIA PARAMETER m
# ═══════════════════════════════════════════════════════════════════════════════
def make_parametric_a(template, m):
    """Given template coefficients with symbolic 'm', produce concrete a_coeffs.

    For the S^(m) family, a(n) = -n(2n - 2m - 1) = -(2m+1)n + 2n².
    Template: a_coeffs = [gamma, beta(m), alpha] where beta depends on m.

    We support a general linear-in-m parametrization:
      a_coeffs[i] = template[i][0] + template[i][1] * m
    where template[i] is (constant_part, m_coefficient).
    """
    return [c0 + c1 * m for (c0, c1) in template]


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 1: HEURISTIC SEARCH + WALLIS-CHECK
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class FamilyCandidate:
    """A parametric PCF family candidate with m-bifurcation."""
    a_template: list       # [(c0, c1), ...] so a_i = c0 + c1*m
    b_coeffs: list         # fixed b polynomial
    values: dict           # {m: mpf_value}
    ratios: dict           # {m: V(m)/V(m-1) as Fraction or None}
    rational_ratios: bool  # True if all ratios are exact rationals
    description: str = ""
    match_info: dict = field(default_factory=dict)


def detect_rational(val: mpf, max_q=500, tol_digits=25) -> Optional[Fraction]:
    """Try to express val as an exact rational p/q with q <= max_q.
    Returns Fraction if match to tol_digits, else None."""
    for q in range(1, max_q + 1):
        p_approx = val * q
        p_round = int(round(float(p_approx)))
        if p_round == 0:
            continue
        residual = abs(p_approx - p_round)
        if residual > 0:
            digits = float(-log(residual / max(1, abs(p_round)), 10))
            if digits >= tol_digits:
                return Fraction(p_round, q)
        elif residual == 0:
            return Fraction(p_round, q)
    return None


def wallis_check(a_template, b_coeffs, m_values=(0, 1, 2, 3),
                 prec=60, depth=800, ratio_tol=25):
    """Evaluate parametric family at several m values, check ratio rationality.

    Returns FamilyCandidate with populated values/ratios/rational_ratios.
    """
    saved_dps = mp.dps
    mp.dps = prec

    values = {}
    for m in m_values:
        a_coeffs = make_parametric_a(a_template, m)
        a_int = [int(round(c)) for c in a_coeffs]
        # Skip trivial / telescoping
        if all(c == 0 for c in a_int):
            continue
        v = eval_pcf(a_int, b_coeffs, depth=depth)
        if v is not None and is_reasonable(v):
            if not is_telescoping(a_int, b_coeffs):
                values[m] = v

    ratios = {}
    all_rational = len(values) >= 3  # need at least 3 values
    for m in m_values:
        if m == m_values[0]:
            continue
        if m in values and (m - 1) in values and values[m - 1] != 0:
            r = values[m] / values[m - 1]
            frac = detect_rational(r, max_q=500, tol_digits=ratio_tol)
            ratios[m] = frac
            if frac is None:
                all_rational = False
        else:
            all_rational = False

    mp.dps = saved_dps
    return FamilyCandidate(
        a_template=a_template,
        b_coeffs=b_coeffs,
        values=values,
        ratios=ratios,
        rational_ratios=all_rational and len(ratios) >= 2,
    )


def generate_search_space(coeff_range=4, include_cubic=False):
    """Generate parametric a-templates and b-coefficients for systematic scan.

    a(n) = (γ₀+γ₁m) + (β₀+β₁m)n + (α₀+α₁m)n²  [+ optional cubic term]
    b(n) = ε + δn

    We fix the m-dependence structure: a₀ has no m-dep, a₁ is linear in m,
    a₂ is fixed (no m-dep). This covers the S^(m) pattern plus generalizations.
    """
    R = range(-coeff_range, coeff_range + 1)
    R_pos = range(1, coeff_range + 1)
    R_nonneg = range(0, coeff_range + 1)

    candidates = []

    # Pattern 1: a(n) = γ + (β₀ + β₁·m)n + α·n²
    # S^(m) is γ=0, β₀=1, β₁=2, α=-2, b=[1,3] → a(n) = (1+2m)n - 2n²
    # which gives a(n) = -(2n² - (2m+1)n) = -n(2n - 2m - 1) ✓
    for gamma in range(-3, 4):
        for beta0 in range(-4, 5):
            for beta1 in [1, 2, -1, -2, 3, -3]:  # m-coefficient of linear term
                for alpha in range(-4, 5):
                    if alpha == 0 and beta0 == 0 and gamma == 0:
                        continue  # skip zero a(n)
                    a_template = [(gamma, 0), (beta0, beta1), (alpha, 0)]
                    candidates.append(a_template)

    # Pattern 2: a(n) = γ + β·n + (α₀ + α₁·m)n²
    # m enters the quadratic coefficient
    for gamma in range(-3, 4):
        for beta in range(-4, 5):
            for alpha0 in range(-3, 4):
                for alpha1 in [1, -1, 2, -2]:
                    if alpha0 == 0 and alpha1 == 0 and beta == 0 and gamma == 0:
                        continue
                    a_template = [(gamma, 0), (beta, 0), (alpha0, alpha1)]
                    candidates.append(a_template)

    # Pattern 3: m enters constant term (bifurcation at ground level)
    for gamma0 in range(-2, 3):
        for gamma1 in [1, -1, 2, -2]:
            for beta in range(-4, 5):
                for alpha in range(-4, 5):
                    if alpha == 0 and beta == 0 and gamma0 == 0 and gamma1 == 0:
                        continue
                    a_template = [(gamma0, gamma1), (beta, 0), (alpha, 0)]
                    candidates.append(a_template)

    # b(n) variations
    b_candidates = []
    for eps in R_pos:
        for delta in range(1, coeff_range + 1):
            b_candidates.append([eps, delta])

    log_main.info(f"Search space: {len(candidates)} a-templates × "
                  f"{len(b_candidates)} b-coeffs = "
                  f"{len(candidates) * len(b_candidates)} total families")
    return candidates, b_candidates


def run_phase1(args):
    """Phase 1: Systematic grid search with Wallis-Check filter."""
    log_main.info("=" * 70)
    log_main.info("  PHASE 1: HEURISTIC SEARCH + WALLIS-CHECK")
    log_main.info("=" * 70)

    guard = ThermalGuard()
    a_templates, b_candidates = generate_search_space(
        coeff_range=args.coeff_range,
        include_cubic=args.include_cubic,
    )

    # ── Control group: verify S^(m) family is detected ───────────────────
    log_main.info("Verifying control group: S^(m) family...")
    mp.dps = 60
    sm_template = [(0, 0), (1, 2), (-2, 0)]  # a(n) = (1+2m)n - 2n² = -n(2n-2m-1)
    sm_result = wallis_check(sm_template, [1, 3], m_values=(0, 1, 2, 3, 4))
    if not sm_result.rational_ratios:
        log_main.error("CONTROL FAILURE: S^(m) not detected as rational-ratio family!")
        log_main.error(f"  Ratios: {sm_result.ratios}")
        return []
    log_main.info(f"  Control OK: ratios = {sm_result.ratios}")
    for m, v in sorted(sm_result.values.items()):
        log_main.info(f"  S^({m}) = {nstr(v, 25)}")

    # ── Main grid scan ────────────────────────────────────────────────────
    highly_significant = []
    near_misses = []
    total = len(a_templates) * len(b_candidates)
    scanned = 0
    t0 = time.time()

    for batch_start in range(0, total, BATCH_SIZE):
        guard.check()
        batch_end = min(batch_start + BATCH_SIZE, total)

        for idx in range(batch_start, batch_end):
            a_idx = idx // len(b_candidates)
            b_idx = idx % len(b_candidates)
            a_tmpl = a_templates[a_idx]
            b_coeff = b_candidates[b_idx]

            # Quick pre-filter: float64 prescreener
            if not wallis_check_fast(a_tmpl, b_coeff):
                scanned += 1
                continue

            # Full Wallis-Check at m=0,1,2,3
            result = wallis_check(a_tmpl, b_coeff, m_values=(0, 1, 2, 3),
                                  prec=50, depth=500, ratio_tol=20)

            if result.rational_ratios:
                # Verify at higher precision
                result_hp = wallis_check(a_tmpl, b_coeff,
                                         m_values=(0, 1, 2, 3, 4, 5),
                                         prec=80, depth=800, ratio_tol=30)
                if result_hp.rational_ratios:
                    # Skip if it's just the known S^(m) family
                    if a_tmpl == sm_template and b_coeff == [1, 3]:
                        scanned += 1
                        continue
                    result_hp.description = (
                        f"a_tmpl={a_tmpl} b={b_coeff} "
                        f"ratios={result_hp.ratios}"
                    )
                    highly_significant.append(result_hp)
                    log_main.info(
                        f"  ★ HIGHLY SIGNIFICANT: {result_hp.description}"
                    )
                    for m, v in sorted(result_hp.values.items()):
                        log_main.info(f"    V({m}) = {nstr(v, 30)}")
                    for m, r in sorted(result_hp.ratios.items()):
                        log_main.info(f"    V({m})/V({m-1}) = {r}")
            elif len(result.ratios) >= 1:
                # Near miss: at least one rational ratio
                rat_count = sum(1 for r in result.ratios.values() if r is not None)
                if rat_count >= 1 and len(result.values) >= 3:
                    near_misses.append(result)

            scanned += 1

        elapsed = time.time() - t0
        rate = scanned / max(elapsed, 0.01)
        pct = 100.0 * scanned / total
        log_main.info(
            f"  Scanned {scanned}/{total} ({pct:.1f}%) "
            f"rate={rate:.0f}/s  hits={len(highly_significant)} "
            f"near={len(near_misses)}  {guard.status()}"
        )

    elapsed = time.time() - t0
    log_main.info(f"\nPhase 1 complete: {elapsed:.1f}s, "
                  f"{len(highly_significant)} significant families, "
                  f"{len(near_misses)} near-misses")

    # ── Deduplicate: families that are m-scaled versions of each other ────
    unique_families = deduplicate_families(highly_significant)
    log_main.info(f"After dedup: {len(unique_families)} unique families")

    # Save Phase 1 results
    save_phase1_results(unique_families, near_misses)
    return unique_families


def deduplicate_families(families):
    """Remove duplicate families (same ratio sequence = same family)."""
    seen = set()
    unique = []
    for f in families:
        # Key: sorted tuple of ratio fractions
        ratio_key = tuple(sorted(
            (m, str(r)) for m, r in f.ratios.items() if r is not None
        ))
        if ratio_key not in seen:
            seen.add(ratio_key)
            unique.append(f)
    return unique


def save_phase1_results(families, near_misses):
    """Persist Phase 1 findings."""
    with open(DISCOVERY_FILE, "a", encoding="utf-8") as fout:
        for f in families:
            record = {
                "phase": 1,
                "type": "highly_significant",
                "a_template": f.a_template,
                "b_coeffs": f.b_coeffs,
                "ratios": {str(k): str(v) for k, v in f.ratios.items()},
                "values": {str(k): nstr(v, 40) for k, v in f.values.items()},
                "description": f.description,
                "timestamp": datetime.now().isoformat(),
            }
            fout.write(json.dumps(record) + "\n")
    log_main.info(f"Saved {len(families)} families to {DISCOVERY_FILE}")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 2: HYPERGEOMETRIC MAPPING + NON-INTEGER BIFURCATION
# ═══════════════════════════════════════════════════════════════════════════════

def gauss_cf_parameters(a_coeffs, b_coeffs):
    """Attempt to map a PCF recurrence to the Gauss continued fraction for ₂F₁.

    The Gauss CF for ₂F₁(a,b;c;z) has:
      a_n (even)  = -z · (b + n/2 - 1)(c - a + n/2 - 1) / ((c+n-2)(c+n-1))
      a_n (odd)   = -z · (a + (n-1)/2)(c - b + (n-1)/2) / ((c+n-2)(c+n-1))
    with b_n = 1 for all n.

    For quadratic a_n = α·n² + β·n + γ and b_n = δ·n + ε, we try z=1
    and solve for (a_hyp, b_hyp, c_hyp) if possible.

    Returns: dict with hypergeometric parameters or None.
    """
    # For the S^(m) family: a(n) = -n(2n-2m-1) = -2n² + (2m+1)n
    # This matches the Euler CF for ₂F₁(1/2, m+1/2; 3/2; 1) via:
    #   The even-contraction of ₂F₁ gives quadratic a_n.
    # We attempt matching via numerical experiments.

    if len(a_coeffs) < 3 or len(b_coeffs) < 2:
        return None

    alpha = a_coeffs[2] if len(a_coeffs) > 2 else 0
    beta = a_coeffs[1] if len(a_coeffs) > 1 else 0
    gamma_c = a_coeffs[0]
    delta = b_coeffs[1] if len(b_coeffs) > 1 else 0
    epsilon = b_coeffs[0]

    # For even-contraction of ₂F₁(a,b;c;z):
    # After even contraction (Euler's method), the CF has:
    #   b_n = (c + 2n-1) and a_n = -z·(a+n-1)(b+n-1) for the "odd part"
    # Actually for the CF representation of ₂F₁(a,b;c;z)/₂F₁(a,b+1;c+1;z):
    #   a_n = z·(b+n)(c-a+n) / ((c+2n)(c+2n+1))  ... gets complicated.
    #
    # Simpler: match numerically. Evaluate the PCF and compare with ₂F₁ values.
    results = {}

    try:
        saved_dps = mp.dps
        mp.dps = 60

        pcf_val = eval_pcf(a_coeffs, b_coeffs, depth=800)
        if pcf_val is None or not is_reasonable(pcf_val):
            mp.dps = saved_dps
            return None

        # Try matching: PCF value = c₁ · ₂F₁(a,b;c;z) / ₂F₁(a',b';c';z)
        # or simpler: PCF value = c₁ · ₂F₁(a,b;c;1) using Gauss summation
        #   ₂F₁(a,b;c;1) = Γ(c)Γ(c-a-b) / (Γ(c-a)Γ(c-b))  when Re(c-a-b) > 0

        # Test a grid of (a,b,c) half-integer parameters
        best_match = None
        best_digits = 0

        for a_h in [mpf(k)/2 for k in range(-4, 8)]:
            for b_h in [mpf(k)/2 for k in range(-4, 8)]:
                for c_h in [mpf(k)/2 for k in range(1, 12)]:
                    # Gauss summation condition
                    if float(c_h - a_h - b_h) <= 0:
                        continue
                    try:
                        hyp_val = (gamma(c_h) * gamma(c_h - a_h - b_h) /
                                   (gamma(c_h - a_h) * gamma(c_h - b_h)))
                    except Exception:
                        continue
                    if not is_reasonable(hyp_val):
                        continue

                    # Check direct match
                    diff = abs(pcf_val - hyp_val)
                    if diff > 0:
                        digits = float(-log(diff, 10))
                    else:
                        digits = 50
                    if digits > best_digits:
                        best_digits = digits
                        best_match = {
                            "type": "2F1_gauss",
                            "a": float(a_h), "b": float(b_h), "c": float(c_h),
                            "z": 1.0,
                            "hyp_value": nstr(hyp_val, 30),
                            "pcf_value": nstr(pcf_val, 30),
                            "digits": digits,
                        }

                    # Check rational multiples p/q · ₂F₁
                    for q in range(1, 13):
                        p_approx = pcf_val / hyp_val * q
                        p_round = int(round(float(p_approx)))
                        if p_round == 0:
                            continue
                        residual = abs(p_approx - p_round)
                        if residual > 0:
                            d = float(-log(residual / abs(p_round), 10))
                        else:
                            d = 50
                        if d > best_digits:
                            best_digits = d
                            best_match = {
                                "type": "2F1_gauss_rational",
                                "a": float(a_h), "b": float(b_h), "c": float(c_h),
                                "z": 1.0,
                                "multiplier": f"{p_round}/{q}",
                                "digits": d,
                            }

        mp.dps = saved_dps

        if best_match and best_digits > 20:
            return best_match

    except Exception as e:
        log_main.debug(f"gauss_cf_parameters error: {e}")

    return None


def try_3f2_mapping(a_coeffs, b_coeffs, pcf_val):
    """Attempt matching PCF value to ₃F₂ at unit argument.

    ₃F₂(a₁,a₂,a₃; b₁,b₂; 1) via Pfaff-Saalschütz / Dixon / Whipple.
    """
    saved_dps = mp.dps
    mp.dps = 60
    best_match = None
    best_digits = 0

    # Search over small half-integer parameters
    half_ints = [mpf(k) / 2 for k in range(-3, 8)]

    for a1 in half_ints:
        for a2 in half_ints:
            for a3 in half_ints:
                for b1 in [mpf(k) / 2 for k in range(1, 10)]:
                    for b2 in [mpf(k) / 2 for k in range(1, 10)]:
                        # Convergence condition: Re(b1+b2-a1-a2-a3) > 0
                        if float(b1 + b2 - a1 - a2 - a3) <= 0:
                            continue
                        try:
                            hv = hyp3f2(a1, a2, a3, b1, b2, 1)
                        except Exception:
                            continue
                        if not is_reasonable(hv):
                            continue
                        diff = abs(pcf_val - hv)
                        if diff > 0:
                            d = float(-log(diff, 10))
                        else:
                            d = 50
                        if d > best_digits:
                            best_digits = d
                            best_match = {
                                "type": "3F2_unit",
                                "params": [float(a1), float(a2), float(a3),
                                           float(b1), float(b2)],
                                "digits": d,
                            }
                        # Check rational multiples
                        for q in range(1, 7):
                            pa = pcf_val / hv * q
                            pr = int(round(float(pa)))
                            if pr == 0:
                                continue
                            res = abs(pa - pr)
                            if res > 0:
                                dd = float(-log(res / abs(pr), 10))
                            else:
                                dd = 50
                            if dd > best_digits:
                                best_digits = dd
                                best_match = {
                                    "type": "3F2_unit_rational",
                                    "params": [float(a1), float(a2), float(a3),
                                               float(b1), float(b2)],
                                    "multiplier": f"{pr}/{q}",
                                    "digits": dd,
                                }

    mp.dps = saved_dps
    if best_match and best_digits > 20:
        return best_match
    return None


def test_noninteger_bifurcation(a_template, b_coeffs, test_m_values=None):
    """Test family at half-integer and complex m values.

    Check if convergence holds and whether values match known constants
    (ζ(s), G, L-functions, etc.).
    """
    if test_m_values is None:
        test_m_values = [
            mpf("0.5"), mpf("1.5"), mpf("2.5"), mpf("3.5"),
            mpf("-0.5"), mpf("-1.5"),
        ]

    saved_dps = mp.dps
    mp.dps = 80

    # Build constant targets for matching
    pi_val = pi
    targets = {
        "zeta3": zeta(3),
        "zeta5": zeta(5),
        "catalan": mpm.catalan,
        "log2": log(2),
        "log3": log(3),
        "pi": pi_val,
        "4/pi": mpf(4) / pi_val,
        "pi/4": pi_val / 4,
        "sqrt_pi": sqrt(pi_val),
        "euler_gamma": euler,
        "phi": (1 + sqrt(5)) / 2,
        "Gamma_1_4": gamma(mpf(1) / 4),
        "Gamma_1_3": gamma(mpf(1) / 3),
    }

    results = {}
    for m_val in test_m_values:
        a_coeffs_f = make_parametric_a(a_template, float(m_val))
        # For non-integer m, coefficients are real-valued — use mpf directly
        a_mpf = [mpf(c) for c in a_coeffs_f]

        # Evaluate with mpf coefficients
        try:
            def a_func(n, _a=a_mpf):
                return sum(c * mpf(n)**i for i, c in enumerate(_a))
            def b_func(n, _b=b_coeffs):
                return sum(mpf(c) * mpf(n)**i for i, c in enumerate(_b))

            val = mpf(0)
            depth = 800
            for n in range(depth, 0, -1):
                denom = b_func(n) + val
                if abs(denom) < mpf(10)**(-mp.dps + 5):
                    val = None
                    break
                val = a_func(n) / denom

            if val is None:
                results[str(m_val)] = {"status": "diverged"}
                continue
            val = b_func(0) + val
        except Exception:
            results[str(m_val)] = {"status": "error"}
            continue

        if not is_reasonable(val):
            results[str(m_val)] = {"status": "unreasonable", "value": nstr(val, 20)}
            continue

        # Match against targets
        best_name, best_digits = None, 0
        for cname, cval in targets.items():
            diff = abs(val - cval)
            if diff > 0:
                d = float(-log(diff, 10))
            else:
                d = 50
            if d > best_digits:
                best_digits = d
                best_name = cname

            # Rational multiples
            if cval != 0:
                for q in range(1, 13):
                    pa = val / cval * q
                    pr = int(round(float(pa)))
                    if pr == 0:
                        continue
                    res = abs(pa - pr)
                    if res > 0:
                        dd = float(-log(res / abs(pr), 10))
                    else:
                        dd = 50
                    if dd > best_digits:
                        best_digits = dd
                        best_name = f"({pr}/{q})*{cname}"

        results[str(m_val)] = {
            "status": "converged",
            "value": nstr(val, 40),
            "best_match": best_name,
            "match_digits": best_digits,
        }

    mp.dps = saved_dps
    return results


def run_phase2(families, args):
    """Phase 2: Hypergeometric mapping and non-integer bifurcation for each family."""
    log_main.info("=" * 70)
    log_main.info("  PHASE 2: HYPERGEOMETRIC MAPPING & EXPANSION")
    log_main.info("=" * 70)

    guard = ThermalGuard()
    results = []

    for i, fam in enumerate(families):
        guard.check()
        log_main.info(f"\n─── Family {i+1}/{len(families)}: {fam.description} ───")

        # 2a. ₂F₁ Gauss CF mapping for each member
        log_main.info("  Attempting ₂F₁ Gauss mapping...")
        hyp_results = {}
        for m, v in sorted(fam.values.items()):
            a_coeffs = [int(round(c)) for c in make_parametric_a(fam.a_template, m)]
            mapping = gauss_cf_parameters(a_coeffs, fam.b_coeffs)
            if mapping:
                hyp_results[m] = mapping
                log_main.info(f"    m={m}: {mapping['type']} "
                              f"({mapping.get('digits', 0):.1f} digits) "
                              f"a={mapping.get('a')}, b={mapping.get('b')}, "
                              f"c={mapping.get('c')}")

        # 2b. Try ₃F₂ if ₂F₁ fails
        if not hyp_results:
            log_main.info("  No ₂F₁ match — trying ₃F₂...")
            mp.dps = 60
            for m, v in sorted(fam.values.items()):
                a_coeffs = [int(round(c)) for c in make_parametric_a(fam.a_template, m)]
                mapping3 = try_3f2_mapping(a_coeffs, fam.b_coeffs, v)
                if mapping3:
                    hyp_results[m] = mapping3
                    log_main.info(f"    m={m}: {mapping3['type']} "
                                  f"({mapping3.get('digits', 0):.1f} digits)")

        # 2c. Non-integer bifurcation
        log_main.info("  Testing non-integer bifurcation (m = 1/2, 3/2, ...)...")
        bif_results = test_noninteger_bifurcation(fam.a_template, fam.b_coeffs)
        for m_str, info in bif_results.items():
            if info.get("status") == "converged":
                bm = info.get("best_match", "?")
                bd = info.get("match_digits", 0)
                log_main.info(f"    m={m_str}: {info.get('value', '?')[:30]}... "
                              f"≈ {bm} ({bd:.1f}d)")

        # Aggregate
        fam.match_info = {
            "hypergeometric": hyp_results,
            "bifurcation": bif_results,
        }
        results.append(fam)

    # Save Phase 2 data
    save_phase2_results(results)
    return results


def save_phase2_results(families):
    """Append Phase 2 findings."""
    with open(DISCOVERY_FILE, "a", encoding="utf-8") as fout:
        for f in families:
            record = {
                "phase": 2,
                "type": "hypergeometric_mapped",
                "a_template": f.a_template,
                "b_coeffs": f.b_coeffs,
                "ratios": {str(k): str(v) for k, v in f.ratios.items()},
                "hypergeometric": f.match_info.get("hypergeometric", {}),
                "bifurcation": {k: v for k, v in
                                f.match_info.get("bifurcation", {}).items()},
                "timestamp": datetime.now().isoformat(),
            }
            fout.write(json.dumps(record, default=str) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 3: FORMALIZATION & EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def verify_at_1000dp(a_template, b_coeffs, m_values=(0, 1, 2, 3)):
    """High-precision 1000dp verification of family members."""
    saved_dps = mp.dps
    mp.dps = 1050

    verified = {}
    for m in m_values:
        a_coeffs = [int(round(c)) for c in make_parametric_a(a_template, m)]
        v1 = eval_pcf(a_coeffs, b_coeffs, depth=3000)
        v2 = eval_pcf(a_coeffs, b_coeffs, depth=2000)
        if v1 is None or v2 is None:
            verified[m] = {"status": "diverged"}
            continue
        diff = abs(v1 - v2)
        if diff > 0:
            stable = int(float(-log(diff, 10)))
        else:
            stable = 1000
        verified[m] = {
            "value_1000dp": nstr(v1, 1000),
            "stable_digits": stable,
            "status": "verified" if stable >= 500 else "partial",
        }

    mp.dps = saved_dps
    return verified


def generate_proof_sketch(family):
    """Generate a Lean 4-style proof sketch for a rational-ratio family.

    Path: PCF → ₂F₁ → Gauss Summation → Legendre Duplication → Closed Form
    """
    sketch_lines = []
    sketch_lines.append("-- Proof sketch: PCF → ₂F₁ → Gamma reduction")
    sketch_lines.append(f"-- Family: a_template={family.a_template}, b={family.b_coeffs}")
    sketch_lines.append(f"-- Ratios: {family.ratios}")
    sketch_lines.append("")

    hyp = family.match_info.get("hypergeometric", {})
    if hyp:
        for m, info in sorted(hyp.items()):
            if "a" in info:
                a_h, b_h, c_h = info["a"], info["b"], info["c"]
                sketch_lines.append(f"-- m={m}: Value = (p/q) · ₂F₁({a_h}, {b_h}; {c_h}; 1)")
                sketch_lines.append(f"--   By Gauss summation: ₂F₁(a,b;c;1) = Γ(c)Γ(c-a-b)/(Γ(c-a)Γ(c-b))")
                if c_h - a_h - b_h > 0:
                    sketch_lines.append(f"--   Condition c-a-b = {c_h - a_h - b_h} > 0 ✓")
                sketch_lines.append(f"--   Apply Legendre duplication: Γ(z)Γ(z+1/2) = √π·Γ(2z)/2^(2z-1)")
                sketch_lines.append("")

    sketch_lines.append("-- theorem family_closed_form (m : ℕ) :")
    sketch_lines.append("--   V(m) = [closed form expression] := by")
    sketch_lines.append("--   induction m with")
    sketch_lines.append("--   | zero => simp [V, pcf_eval, hyp2f1_gauss]")
    sketch_lines.append("--   | succ n ih => ")
    sketch_lines.append("--     rw [V_ratio_recurrence]  -- V(n+1)/V(n) = r(n)")
    sketch_lines.append("--     exact ih ▸ ratio_closed_form n")

    return "\n".join(sketch_lines)


def build_cert_table(families_verified):
    """Build certification table for arXiv export."""
    table = {
        "title": "Rosetta Stone PCF Family Certification Table",
        "generated": datetime.now().isoformat(),
        "families": [],
    }

    for fam, verified in families_verified:
        entry = {
            "a_template": fam.a_template,
            "b_coeffs": fam.b_coeffs,
            "ratios": {str(k): str(v) for k, v in fam.ratios.items()},
            "members": {},
        }

        for m, vinfo in verified.items():
            entry["members"][str(m)] = {
                "stable_digits": vinfo.get("stable_digits", 0),
                "value_50dp": vinfo.get("value_1000dp", "?")[:55],
                "status": vinfo.get("status", "?"),
            }

        # Include hypergeometric identity if found
        hyp = fam.match_info.get("hypergeometric", {})
        if hyp:
            entry["hypergeometric_identities"] = {}
            for m_key, info in hyp.items():
                entry["hypergeometric_identities"][str(m_key)] = info

        # Include proof sketch
        entry["proof_sketch"] = generate_proof_sketch(fam)

        table["families"].append(entry)

    return table


def run_phase3(families, args):
    """Phase 3: 1000dp verification, proof sketches, certification table."""
    log_main.info("=" * 70)
    log_main.info("  PHASE 3: FORMALIZATION & EXPORT")
    log_main.info("=" * 70)

    guard = ThermalGuard()
    families_verified = []

    # Also verify the S^(m) control family at 1000dp
    log_main.info("Verifying S^(m) control family at 1000dp...")
    sm_template = [(0, 0), (1, 2), (-2, 0)]
    sm_verified = verify_at_1000dp(sm_template, [1, 3], m_values=(0, 1, 2, 3))
    for m, info in sorted(sm_verified.items()):
        log_main.info(f"  S^({m}): {info.get('stable_digits', 0)} stable digits")

    # Verify each discovered family
    for i, fam in enumerate(families):
        guard.check()
        log_main.info(f"\nVerifying family {i+1}/{len(families)}: {fam.description}")

        m_vals = tuple(sorted(fam.values.keys()))[:6]  # up to 6 members
        verified = verify_at_1000dp(fam.a_template, fam.b_coeffs, m_values=m_vals)

        for m, info in sorted(verified.items()):
            sd = info.get("stable_digits", 0)
            status = info.get("status", "?")
            log_main.info(f"  m={m}: {sd} stable digits [{status}]")

        families_verified.append((fam, verified))

        # Generate proof sketch
        sketch = generate_proof_sketch(fam)
        log_main.info(f"  Proof sketch:\n{sketch}")

    # Build and save certification table
    cert_table = build_cert_table(families_verified)
    with open(CERT_TABLE_FILE, "w", encoding="utf-8") as f:
        json.dump(cert_table, f, indent=2, default=str)
    log_main.info(f"\nCertification table saved to {CERT_TABLE_FILE}")

    # Final summary
    log_main.info("\n" + "=" * 70)
    log_main.info("  ROSETTA STONE SEARCH — FINAL SUMMARY")
    log_main.info("=" * 70)
    log_main.info(f"  Families discovered: {len(families)}")
    for i, (fam, ver) in enumerate(families_verified):
        log_main.info(f"\n  Family {i+1}: {fam.description}")
        log_main.info(f"    Ratios: {fam.ratios}")
        hyp = fam.match_info.get("hypergeometric", {})
        if hyp:
            for m_key, info in hyp.items():
                log_main.info(f"    m={m_key}: {info.get('type', '?')} "
                              f"({info.get('digits', 0):.1f}d)")
        bif = fam.match_info.get("bifurcation", {})
        interesting_bif = {k: v for k, v in bif.items()
                          if v.get("match_digits", 0) > 10}
        if interesting_bif:
            log_main.info(f"    Non-integer bifurcation hits:")
            for m_str, info in interesting_bif.items():
                log_main.info(f"      m={m_str}: ≈ {info.get('best_match')} "
                              f"({info.get('match_digits', 0):.1f}d)")

    return families_verified


# ═══════════════════════════════════════════════════════════════════════════════
#  PARALLEL WORKER (for Phase 1 acceleration)
# ═══════════════════════════════════════════════════════════════════════════════

def _worker_scan_batch(task):
    """Worker function for parallel Phase 1 scanning."""
    a_templates_batch, b_candidates, prec, depth = task
    mp.dps = prec

    hits = []
    for a_tmpl in a_templates_batch:
        for b_coeff in b_candidates:
            # Stage 1: float64 prescreener (very fast)
            if not wallis_check_fast(a_tmpl, b_coeff):
                continue

            # Stage 2: mpmath verification at moderate precision
            result = wallis_check(a_tmpl, b_coeff, m_values=(0, 1, 2, 3),
                                  prec=prec, depth=depth, ratio_tol=20)
            if result.rational_ratios:
                # Serialize for cross-process transport
                hits.append({
                    "a_template": a_tmpl,
                    "b_coeffs": b_coeff,
                    "ratios": {str(k): str(v) for k, v in result.ratios.items()},
                    "values": {str(k): float(v) for k, v in result.values.items()},
                })
    return hits


def run_phase1_parallel(args):
    """Parallel Phase 1 using multiprocessing."""
    log_main.info("=" * 70)
    log_main.info("  PHASE 1 (PARALLEL): HEURISTIC SEARCH + WALLIS-CHECK")
    log_main.info(f"  Workers: {args.workers}")
    log_main.info("=" * 70)

    guard = ThermalGuard()

    # Verify control group first (single-threaded)
    mp.dps = 60
    sm_template = [(0, 0), (1, 2), (-2, 0)]  # a(n) = (1+2m)n - 2n²
    sm_result = wallis_check(sm_template, [1, 3], m_values=(0, 1, 2, 3, 4))
    if not sm_result.rational_ratios:
        log_main.error("CONTROL FAILURE: S^(m) not detected!")
        return []
    log_main.info(f"Control OK: S^(m) ratios = {sm_result.ratios}")

    a_templates, b_candidates = generate_search_space(
        coeff_range=args.coeff_range,
        include_cubic=args.include_cubic,
    )

    # Split a_templates into worker batches
    n_workers = args.workers
    chunk_size = max(1, len(a_templates) // (n_workers * 4))
    batches = []
    for i in range(0, len(a_templates), chunk_size):
        chunk = a_templates[i:i + chunk_size]
        batches.append((chunk, b_candidates, 50, 500))

    log_main.info(f"  Dispatching {len(batches)} batches across {n_workers} workers...")
    t0 = time.time()

    all_hits = []
    with mproc.Pool(processes=n_workers) as pool:
        for batch_idx, result in enumerate(pool.imap_unordered(_worker_scan_batch, batches)):
            all_hits.extend(result)
            if (batch_idx + 1) % 10 == 0:
                elapsed = time.time() - t0
                log_main.info(f"  Batch {batch_idx+1}/{len(batches)} "
                              f"hits={len(all_hits)} elapsed={elapsed:.1f}s "
                              f"{guard.status()}")
                guard.check()

    elapsed = time.time() - t0
    log_main.info(f"\nParallel scan complete: {elapsed:.1f}s, {len(all_hits)} raw hits")

    # Reconstruct FamilyCandidate objects and verify at higher precision
    log_main.info("Verifying hits at higher precision...")
    families = []
    sm_key = str([(0, 0), (1, 2), (-2, 0)])

    for hit in all_hits:
        a_tmpl = hit["a_template"]
        b_coeff = hit["b_coeffs"]

        # Skip known S^(m)
        if str(a_tmpl) == sm_key and b_coeff == [1, 3]:
            continue

        result_hp = wallis_check(a_tmpl, b_coeff,
                                 m_values=(0, 1, 2, 3, 4, 5),
                                 prec=80, depth=800, ratio_tol=30)
        if result_hp.rational_ratios:
            result_hp.description = (
                f"a_tmpl={a_tmpl} b={b_coeff} ratios={result_hp.ratios}"
            )
            families.append(result_hp)
            log_main.info(f"  ★ CONFIRMED: {result_hp.description}")

    unique = deduplicate_families(families)
    log_main.info(f"After dedup: {len(unique)} unique families")
    save_phase1_results(unique, [])
    return unique


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Rosetta Stone PCF family discovery engine"
    )
    parser.add_argument("--phase", type=int, default=0,
                        help="Run only phase 1, 2, or 3 (0=all)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel workers for Phase 1")
    parser.add_argument("--coeff-range", type=int, default=4,
                        help="Coefficient range for search space")
    parser.add_argument("--include-cubic", action="store_true",
                        help="Include cubic a(n) templates")
    parser.add_argument("--precision", type=int, default=60,
                        help="Working precision (decimal digits)")
    parser.add_argument("--depth", type=int, default=800,
                        help="CF evaluation depth")
    parser.add_argument("--skip-1000dp", action="store_true",
                        help="Skip 1000dp verification in Phase 3")
    args = parser.parse_args()

    log_main.info("╔══════════════════════════════════════════════════════════╗")
    log_main.info("║     ROSETTA STONE — PCF Family Discovery Engine         ║")
    log_main.info("║     Template: S^(m) Bifurcation Theorem                 ║")
    log_main.info("╚══════════════════════════════════════════════════════════╝")
    log_main.info(f"  Platform: {platform.processor()} / "
                  f"{os.cpu_count()} cores / "
                  f"{'psutil OK' if HAS_PSUTIL else 'no psutil'}")
    log_main.info(f"  Settings: workers={args.workers} coeff_range={args.coeff_range} "
                  f"prec={args.precision} depth={args.depth}")

    mp.dps = args.precision

    families = []

    # ── Phase 1 ──
    if args.phase in (0, 1):
        if args.workers > 1:
            families = run_phase1_parallel(args)
        else:
            families = run_phase1(args)

    # ── Load from disk if skipping Phase 1 ──
    if args.phase in (2, 3) and not families:
        families = load_phase1_results()

    # ── Phase 2 ──
    if args.phase in (0, 2) and families:
        families = run_phase2(families, args)

    # ── Phase 3 ──
    if args.phase in (0, 3) and families:
        if not args.skip_1000dp:
            run_phase3(families, args)
        else:
            log_main.info("Skipping 1000dp verification (--skip-1000dp)")

    if not families:
        log_main.info("\nNo new families discovered. Search space may need expansion.")
        log_main.info("Try: --coeff-range 5 or --include-cubic")


def load_phase1_results():
    """Load Phase 1 families from discovery log."""
    families = []
    if not DISCOVERY_FILE.exists():
        log_main.warning(f"No discovery file found: {DISCOVERY_FILE}")
        return families

    with open(DISCOVERY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("phase") == 1 and rec.get("type") == "highly_significant":
                fam = FamilyCandidate(
                    a_template=rec["a_template"],
                    b_coeffs=rec["b_coeffs"],
                    values={int(k): mpf(v) for k, v in rec.get("values", {}).items()},
                    ratios={int(k): Fraction(v) if v != "None" else None
                            for k, v in rec.get("ratios", {}).items()},
                    rational_ratios=True,
                    description=rec.get("description", ""),
                )
                families.append(fam)

    log_main.info(f"Loaded {len(families)} families from {DISCOVERY_FILE}")
    return families


if __name__ == "__main__":
    main()
