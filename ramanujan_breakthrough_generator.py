"""
ramanujan_breakthrough_generator.py
====================================
Self-iterating PCF discovery engine for Ramanujan-inspired mathematical
breakthroughs via evolutionary search, PSLQ matching, and high-precision
verification.

Each evolutionary cycle:
  1. Evaluates a population of polynomial continued fractions (PCFs)
  2. PSLQ-matches values against a library of 25+ mathematical constants
  3. Mutates polynomial coefficients toward promising regions
  4. Logs verified discoveries and adjusts search temperature

Search modes:
  - evolve : Genetic algorithm with adaptive temperature (default)
  - dr     : Degree-restricted random sampling
  - cmf    : Exhaustive coefficient sweep (Conservative Matrix Field)

Usage:
  python ramanujan_breakthrough_generator.py --cycles 30 --seed 42
  python ramanujan_breakthrough_generator.py --mode cmf --coeff-range 3
  python ramanujan_breakthrough_generator.py --target zeta3 --cycles 50
  python ramanujan_breakthrough_generator.py --report

For research agent integration, see research_integration.py.
"""

from __future__ import annotations

import json, time, math, random, argparse, sys, itertools, re, logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Tuple, Any

# ── logging setup ─────────────────────────────────────────────────────────────
logger = logging.getLogger("ramanujan")


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the discovery engine."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


try:
    from mpmath import mp, mpf, nstr, pi, log, sqrt, zeta, euler, gamma, nsum, inf
    import mpmath as mpm
except ImportError:
    sys.exit("mpmath required: pip install mpmath")

try:
    from sympy.ntheory.factor_ import factorint  # lightweight import
except ImportError:
    factorint = None

# ── optional: use mpmath's pslq directly ─────────────────────────────────────
def pslq_match(
    val: mpf,
    constants: Dict[str, mpf],
    tol_digits: int = 15,
) -> Optional[Tuple[str, mpf]]:
    """Attempt to identify *val* as an integer-linear combination of known constants.

    Uses mpmath.identify for symbolic recognition, falling back to PSLQ
    integer relation detection.

    Returns:
        (relation_string, residual) on success, or None.
    """
    try:
        vec = [val] + list(constants.values())
        rel = mpm.identify(val, tol=mpf(10)**(-tol_digits))
        if rel:
            return rel, mpf(0)
        # fallback: mpmath pslq
        mp.dps += 10
        result = mpm.pslq(vec, maxcoeff=100, tol=mpf(10)**(-tol_digits + 2))
        mp.dps -= 10
        if result and result[0] != 0:
            names = ['x'] + list(constants.keys())
            terms = [f"{result[i]}*{names[i]}" for i in range(len(result)) if result[i] != 0]
            residual = sum(result[i] * vec[i] for i in range(len(result)))
            return ' + '.join(terms) + ' = 0', abs(residual)
    except Exception:
        pass
    return None


# ── PCF evaluation ────────────────────────────────────────────────────────────
def eval_pcf(
    a_coeffs: List[int],
    b_coeffs: List[int],
    depth: int = 500,
    check_convergence: bool = False,
) -> Optional[mpf]:
    """Evaluate a polynomial continued fraction.

    Computes ``b(0) + a(1)/(b(1) + a(2)/(b(2) + ...))`` where::

        a(n) = sum(a_coeffs[i] * n**i  for i in range(len(a_coeffs)))
        b(n) = sum(b_coeffs[i] * n**i  for i in range(len(b_coeffs)))

    Uses bottom-up (backward) evaluation for numerical stability.

    Args:
        a_coeffs: Polynomial coefficients for the numerator a(n).
        b_coeffs: Polynomial coefficients for the denominator b(n).
        depth: Number of convergents to compute.
        check_convergence: If True, also evaluate at depth//2 and return
            None if the two values don't agree to at least 10 digits
            (indicates poor convergence).

    Returns:
        The CF value as an mpf, or None if the CF diverges.
    """
    try:
        def a(n): return sum(mpf(c) * n**i for i, c in enumerate(a_coeffs))
        def b(n): return sum(mpf(c) * n**i for i, c in enumerate(b_coeffs))

        # bottom-up evaluation (more stable)
        val = mpf(0)
        for n in range(depth, 0, -1):
            bn = b(n)
            an = a(n)
            denom = bn + val
            if abs(denom) < mpf(10)**(-mp.dps + 5):
                return None
            val = an / denom
        result = b(0) + val

        if check_convergence:
            # Evaluate at half depth to check convergence rate
            val2 = mpf(0)
            half = max(depth // 2, 20)
            for n in range(half, 0, -1):
                bn = b(n)
                an = a(n)
                denom = bn + val2
                if abs(denom) < mpf(10)**(-mp.dps + 5):
                    return None
                val2 = an / denom
            result2 = b(0) + val2
            # Require at least 10 digits agreement
            if abs(result - result2) > mpf(10)**(-10):
                return None

        return result
    except Exception:
        return None


def is_reasonable(val):
    """Filter out NaN, inf, near-zero, or huge values."""
    if val is None:
        return False
    try:
        f = float(val)
        return math.isfinite(f) and 1e-6 < abs(f) < 1e8
    except Exception:
        return False


# ── telescoping / trivial CF detection ────────────────────────────────────────
def is_telescoping(a_coeffs, b_coeffs, depth=200):
    """Detect CFs that converge to b(0) regardless of b(n) for n>=1.
    Key pattern: a(n) = c*(n-1)*(n-k) for some c,k — these telescope.
    Also catches a(n) that factors as a(n) = -c*n*(n-1) variants."""
    # Quick numerical test: evaluate at two different depths
    # If value == b(0) to high precision, it's telescoping
    try:
        val1 = eval_pcf(a_coeffs, b_coeffs, depth=50)
        val2 = eval_pcf(a_coeffs, b_coeffs, depth=200)
        if val1 is None or val2 is None:
            return False
        b0 = mpf(b_coeffs[0]) if b_coeffs else mpf(0)
        # If CF value equals b(0) at both depths, it's trivially telescoping
        if abs(val1 - b0) < mpf(10)**(-30) and abs(val2 - b0) < mpf(10)**(-30):
            return True
        # If convergence is suspiciously fast (identical at depth 50 and 200)
        if abs(val1 - val2) < mpf(10)**(-mp.dps + 10):
            # Check if it's just an integer
            rounded = round(float(val1))
            if abs(val1 - rounded) < mpf(10)**(-30):
                return True
    except Exception:
        pass
    # Algebraic check: a(n) = c*(n-r1)*(n-r2) where r1,r2 are small integers
    if len(a_coeffs) == 3:
        c2, c1, c0 = a_coeffs[2], a_coeffs[1], a_coeffs[0]
        if c2 != 0:
            disc = c1*c1 - 4*c2*c0
            if disc >= 0:
                sd = math.isqrt(abs(disc)) if disc == int(disc) else -1
                if sd >= 0 and sd*sd == disc:
                    # Roots are rational — likely telescoping
                    r1 = (-c1 + sd) / (2*c2)
                    r2 = (-c1 - sd) / (2*c2)
                    if r1 == int(r1) and r2 == int(r2):
                        r1, r2 = int(r1), int(r2)
                        if 0 <= r1 <= 3 or 0 <= r2 <= 3:
                            return True
    return False


# ── high-precision verification ───────────────────────────────────────────────
_constants_cache = {}  # keyed by precision


def _get_constants(prec):
    """Get constants at the requested precision, using cache."""
    if prec not in _constants_cache:
        _constants_cache[prec] = build_constants(prec)
    return _constants_cache[prec]


def verify_match_high_precision(a_coeffs, b_coeffs, match_label, constants,
                                verify_prec=200, verify_depth=1000):
    """Re-evaluate CF and target constant at much higher precision.
    Returns (verified: bool, residual_digits: float)."""
    saved_dps = mp.dps
    try:
        mp.dps = verify_prec + 50
        val = eval_pcf(a_coeffs, b_coeffs, depth=verify_depth)
        if val is None:
            return False, 0.0

        hi_constants = _get_constants(verify_prec)
        target = _parse_match_target(match_label, hi_constants)
        if target is None:
            target = _parse_match_target(match_label, constants)
        if target is None:
            return False, 0.0

        residual = abs(val - target)
        if residual == 0:
            return True, verify_prec
        digits = float(-mpm.log10(residual))
        return digits > verify_prec * 0.8, digits
    except Exception:
        return False, 0.0
    finally:
        mp.dps = saved_dps


def _parse_match_target(label, constants):
    """Parse a match label like '3/4*pi' back into a numeric value."""
    # Direct constant match
    if label in constants:
        return constants[label]
    # Pattern: numer/denom*const_name
    m = re.match(r'^(\d+)/(\d+)\*(.+)$', label)
    if m:
        numer, denom, cname = int(m.group(1)), int(m.group(2)), m.group(3)
        if cname in constants:
            return mpf(numer) / denom * constants[cname]
    return None


# ── spurious match filter ─────────────────────────────────────────────────────
def is_spurious_match(match_label):
    """Filter out mpmath.identify garbage: overcomplicated algebraic expressions."""
    if '**(' in match_label and match_label.count('/') > 3:
        return True
    if match_label.count('*') > 4:
        return True
    # Expressions with many different primes raised to fractional powers
    if re.search(r'\d+\*\*\(\d+/\d+\)', match_label) and match_label.count('**') > 2:
        return True
    return False


# ── complexity penalty ────────────────────────────────────────────────────────
def complexity_score(a_coeffs, b_coeffs):
    """Penalize complex CFs. Lower = simpler = better."""
    total_degree = (len(a_coeffs) - 1) + (len(b_coeffs) - 1)
    coeff_magnitude = sum(abs(c) for c in a_coeffs) + sum(abs(c) for c in b_coeffs)
    nonzero_terms = sum(1 for c in a_coeffs if c != 0) + sum(1 for c in b_coeffs if c != 0)
    return 0.5 * total_degree + 0.1 * coeff_magnitude + 0.3 * nonzero_terms


# ── Phase 2: Fitness trap detection & structural diversity ────────────────────
# Constants whose CFs are well-known — high scores from these are "fitness traps"
_FITNESS_TRAP_BASES = {
    'phi', 'e', '4/pi', '2/pi', 'pi/4', 'pi/2', 'pi', 'sqrt2', 'sqrt3',
    'log2', 'S^(2)', 'S^(3)', 'S^(4)', 'S^(5)',
}


def is_fitness_trap(match_label):
    """Return True if this match is a well-known CF (fitness trap).
    These dominate the score landscape but offer no path to novel discovery."""
    # Strip ratio prefixes like '3/4*' to get the base constant
    base = match_label
    if '*' in match_label:
        parts = match_label.split('*', 1)
        if '/' in parts[0] and len(parts[0]) <= 5:  # ratio prefix like '3/4'
            base = parts[1]
    return base in _FITNESS_TRAP_BASES


def fitness_trap_penalty(match_label, raw_score):
    """Score penalty for known-constant matches.
    Returns a penalty that brings them below novel candidates."""
    if not is_fitness_trap(match_label):
        return 0.0
    # Scale penalty: stronger for higher-scoring traps (> 90d)
    if raw_score > 90:
        return 40.0   # aggressive: drops a 130d phi to ~90d
    elif raw_score > 50:
        return 20.0
    return 10.0


def structural_diversity_index(population, top_n=20):
    """Compute the number of unique (deg_a, deg_b) degree combinations
    in the top N members. Higher = more diverse exploration."""
    degree_combos = set()
    for p in population[:top_n]:
        deg_a = len(p.a) - 1  # polynomial degree
        deg_b = len(p.b) - 1
        degree_combos.add((deg_a, deg_b))
    return len(degree_combos), degree_combos


def structural_report(population, top_n=20):
    """Print a structural diversity summary of the top N."""
    sdi, combos = structural_diversity_index(population, top_n)
    # Count per combo
    combo_counts = defaultdict(int)
    for p in population[:top_n]:
        combo_counts[(len(p.a)-1, len(p.b)-1)] += 1
    # Identify asymmetric (novel) structures: deg_a >= 3 or deg_b >= 2
    novel_struct = sum(1 for p in population[:top_n]
                       if (len(p.a)-1) >= 3 or (len(p.b)-1) >= 2)
    trap_count = sum(1 for p in population[:top_n] if p.hit and is_fitness_trap(p.hit))
    # One-line summary
    combo_str = ' '.join(f'({da},{db}):{c}' for (da,db),c
                         in sorted(combo_counts.items(), key=lambda x: -x[1]))
    print(f"         SDI={sdi} | novel_struct={novel_struct}/{top_n} | "
          f"traps={trap_count} | {combo_str}")
    return sdi


# ── constant library ──────────────────────────────────────────────────────────
def _eval_pi_family(m, depth=800):
    """Compute S^(m) = CF value with a_m(n)=-n(2n-2m-1), b(n)=3n+1."""
    val = mpf(0)
    for n in range(depth, 0, -1):
        an = -mpf(n) * (2*n - 2*m - 1)
        bn = mpf(3*n + 1)
        denom = bn + val
        if abs(denom) < mpf(10)**(-mp.dps + 5):
            return None
        val = an / denom
    return mpf(1) + val   # b(0) = 1


def build_constants(prec: int) -> Dict[str, mpf]:
    """Build the target constant library at the given decimal precision.

    Returns a dict mapping human-readable names to mpf values for 25+
    mathematical constants including π-family, logarithms, algebraic
    irrationals, Gamma values, and Apéry's constant.
    """
    mp.dps = prec + 20
    pi_val = pi
    e_val = mpm.e
    log2_val = log(2)
    log3_val = log(3)
    sqrt2_val = sqrt(2)
    sqrt3_val = sqrt(3)
    sqrt5_val = sqrt(5)
    phi_val = (1 + sqrt5_val) / 2
    euler_val = euler
    zeta3_val = zeta(3)
    zeta5_val = zeta(5)
    catalan_val = mpm.catalan
    gamma14 = gamma(mpf(1)/4)
    gamma34 = gamma(mpf(3)/4)

    consts = {
        # ── pi family ─────────────────────────────────────────────────
        '4/pi':        mpf(4) / pi_val,
        '2/pi':        mpf(2) / pi_val,
        'pi/4':        pi_val / 4,
        'pi/2':        pi_val / 2,
        'pi':          pi_val,
        'pi^2/6':      pi_val**2 / 6,
        'pi^2/8':      pi_val**2 / 8,
        'pi^2/12':     pi_val**2 / 12,
        'pi^3/32':     pi_val**3 / 32,
        'pi^4/90':     pi_val**4 / 90,
        '6/pi^2':      mpf(6) / pi_val**2,
        'sqrt_pi':     sqrt(pi_val),
        '1/sqrt_pi':   1 / sqrt(pi_val),
        '2/sqrt_pi':   2 / sqrt(pi_val),
        # ── logarithms ────────────────────────────────────────────────
        'log2':        log2_val,
        'log3':        log3_val,
        'log5':        log(5),
        'log10':       log(10),
        'log2^2':      log2_val**2,
        'log3/log2':   log3_val / log2_val,
        # ── algebraic irrationals ─────────────────────────────────────
        'sqrt2':       sqrt2_val,
        'sqrt3':       sqrt3_val,
        'sqrt5':       sqrt5_val,
        'sqrt6':       sqrt(6),
        'sqrt7':       sqrt(7),
        'phi':         phi_val,
        '1/phi':       1 / phi_val,
        'sqrt2+1':     sqrt2_val + 1,
        'sqrt3+1':     sqrt3_val + 1,
        # ── exponential / e ───────────────────────────────────────────
        'e':           e_val,
        '1/e':         1 / e_val,
        'e^2':         e_val**2,
        'e*pi':        e_val * pi_val,
        # ── Euler-Mascheroni ──────────────────────────────────────────
        'euler_g':     euler_val,
        'euler_g^2':   euler_val**2,
        # ── zeta values ───────────────────────────────────────────────
        'zeta3':       zeta3_val,
        'zeta5':       zeta5_val,
        'zeta7':       zeta(7),
        '1/zeta3':     1 / zeta3_val,
        'zeta3/pi^3':  zeta3_val / pi_val**3,
        'zeta3*pi':    zeta3_val * pi_val,
        # ── Catalan's constant ────────────────────────────────────────
        'catalan':     catalan_val,
        'catalan/pi':  catalan_val / pi_val,
        'catalan*4/pi': catalan_val * 4 / pi_val,
        'pi*catalan':  pi_val * catalan_val,
        # ── Gamma function values ─────────────────────────────────────
        'Gamma_1_4':   gamma14,
        'Gamma_3_4':   gamma34,
        'Gamma_1_3':   gamma(mpf(1)/3),
        'Gamma_2_3':   gamma(mpf(2)/3),
        'Gamma_1_6':   gamma(mpf(1)/6),
        'Gamma14^2/sqrt_pi': gamma14**2 / sqrt(pi_val),
        # ── Khinchin / Glaisher / Mertens ─────────────────────────────
        'ln2/pi':      log2_val / pi_val,
    }
    # Pi family S^(m) values for m=2..8 (extended)
    for m in range(2, 9):
        sv = _eval_pi_family(m, depth=800)
        if sv is not None:
            consts[f'S^({m})'] = sv
    return consts


# ── parameter space ───────────────────────────────────────────────────────────
@dataclass
class PCFParams:
    """Polynomial coefficients for a(n) and b(n)."""
    a: list  # e.g. [0, -1, 1] means a(n) = 0 - n + n^2
    b: list  # e.g. [1, 3]    means b(n) = 1 + 3n
    score: float = 0.0       # quality metric (lower residual = higher score)
    hit: Optional[str] = None

    def key(self):
        return (tuple(self.a), tuple(self.b))


def random_params(a_deg=2, b_deg=1, coeff_range=5, rng=None):
    if rng is None:
        rng = random
    a = [rng.randint(-coeff_range, coeff_range) for _ in range(a_deg + 1)]
    b = [rng.randint(0, coeff_range) for _ in range(b_deg + 1)]
    b[0] = max(1, b[0])   # b(0) > 0 to avoid zero start
    return PCFParams(a=a, b=b)


def mutate(params, temperature=1.0, rng=None):
    """Gaussian mutation on coefficients."""
    if rng is None:
        rng = random
    sigma = max(0.5, temperature)

    def perturb(coeffs):
        return [int(round(c + rng.gauss(0, sigma))) for c in coeffs]

    new_a = perturb(params.a)
    new_b = perturb(params.b)
    new_b[0] = max(1, new_b[0])
    return PCFParams(a=new_a, b=new_b)


def crossover(p1, p2, rng=None):
    """Single-point crossover on flattened coefficient vector.
    Handles parents with different-length coefficient vectors."""
    if rng is None:
        rng = random
    # Pad to same length
    la = max(len(p1.a), len(p2.a))
    lb = max(len(p1.b), len(p2.b))
    a1 = p1.a + [0] * (la - len(p1.a))
    a2 = p2.a + [0] * (la - len(p2.a))
    b1 = p1.b + [0] * (lb - len(p1.b))
    b2 = p2.b + [0] * (lb - len(p2.b))
    v1 = a1 + b1
    v2 = a2 + b2
    cut = rng.randint(1, len(v1) - 1)
    child = v1[:cut] + v2[cut:]
    new_a = child[:la]
    new_b = child[la:]
    if not new_b:
        new_b = [1]
    new_b[0] = max(1, new_b[0])
    return PCFParams(a=new_a, b=new_b)


# ── seeded population ─────────────────────────────────────────────────────────
def seed_population():
    """Known-good CFs as starting seeds."""
    seeds = [
        # ── Pi family: a_m(n)=-n(2n-2m-1), b(n)=3n+1 ──────────────────────
        # m=0: S^(0)=2/pi
        PCFParams(a=[0, 1, -2], b=[1, 3]),
        # m=1: S^(1)=4/pi  (our novel CF)
        PCFParams(a=[0, 3, -2], b=[1, 3]),
        # m=2: S^(2)=16/(3*pi)
        PCFParams(a=[0, 5, -2], b=[1, 3]),
        # m=3: S^(3)=32/(15*pi)
        PCFParams(a=[0, 7, -2], b=[1, 3]),
        # m=4: S^(4)
        PCFParams(a=[0, 9, -2], b=[1, 3]),
        # m=5: S^(5)
        PCFParams(a=[0, 11, -2], b=[1, 3]),
        # ── Brouncker / classical ─────────────────────────────────────────
        PCFParams(a=[-1, 0, 4], b=[2, 0]),
        # ── Linear a, linear b ────────────────────────────────────────────
        PCFParams(a=[1, -1], b=[1, 2]),
        PCFParams(a=[1, -2], b=[1, 4]),
        PCFParams(a=[0, -3], b=[1, 2]),
        PCFParams(a=[2, -1, -1], b=[1, 2]),
        PCFParams(a=[0, 1, -1], b=[2, 2]),
        # ── Apéry-like cubic: a(n)=-n^3 ──────────────────────────────────
        PCFParams(a=[0, 0, 0, -1], b=[1, 3, 3]),
        PCFParams(a=[0, -1, 0, 1], b=[1, 1, 2]),
        # ── Near-misses: perturbed Pi family (search for alt structure) ───
        PCFParams(a=[0, 3, -2], b=[1, 4]),
        PCFParams(a=[0, 3, -2], b=[2, 3]),
        PCFParams(a=[1, 3, -2], b=[1, 3]),
        PCFParams(a=[0, 5, -3], b=[1, 3]),
        # ── Apéry CF: a(n)=-n^6, b(n)=34n^3-51n^2+27n-5 → 6/zeta(3) ────
        PCFParams(a=[0, 0, 0, 0, 0, 0, -1], b=[-5, 27, -51, 34]),
        # ── Apéry-like cubic seeds for zeta(3) region ─────────────────
        PCFParams(a=[0, 0, 0, -1], b=[1, 5, 5]),
        PCFParams(a=[0, 0, 0, -1], b=[0, 5, 5]),
        PCFParams(a=[0, 0, 0, -8], b=[1, 10, 12]),
        PCFParams(a=[0, 0, 0, 1], b=[1, 3, 3, 1]),
        PCFParams(a=[0, 0, -1, -1], b=[1, 5, 5]),
        PCFParams(a=[0, 1, 0, -1], b=[1, 3, 3]),
        # ── Extended zeta(3) / Apéry-cubic seeds ─────────────────────
        PCFParams(a=[0, 0, 0, -2], b=[1, 5, 5]),       # scaled cubic
        PCFParams(a=[0, 0, 0, -1], b=[2, 7, 7]),       # shifted linear term
        PCFParams(a=[0, 0, -1, -1], b=[0, 3, 3]),      # zero-b0 cubic
        PCFParams(a=[0, 0, 0, 0, 0, 0, -1], b=[-3, 25, -50, 34]),  # perturbed Apéry sextic
        PCFParams(a=[0, 0, 0, 0, 0, 0, -1], b=[-5, 27, -51, 35]),  # Apéry b3 +1
        PCFParams(a=[0, 0, 0, 0, 0, 0, -2], b=[-5, 27, -51, 34]),  # doubled a6
        PCFParams(a=[0, 0, 0, -1, 0, 0, -1], b=[-5, 27, -51, 34]), # mixed cubic+sextic
        PCFParams(a=[0, 0, 0, 0, -1], b=[1, 6, 10, 4]),            # quartic a, cubic b
        # ── Catalan-targeting seeds ───────────────────────────────────
        PCFParams(a=[0, -1, 0, 0, 1], b=[1, 0, 4]),
        PCFParams(a=[0, 0, -1], b=[1, 4]),
        PCFParams(a=[0, -1, 4], b=[2, 0]),
        # ── Higher-degree exploration ─────────────────────────────────
        PCFParams(a=[0, 0, 0, 0, -1], b=[1, 4, 6, 4]),
        PCFParams(a=[0, 0, 1, 0, -1], b=[1, 2, 3]),
    ]
    return seeds


# ── discovery log ─────────────────────────────────────────────────────────────
LOGFILE = Path("ramanujan_discoveries.jsonl")
STATEFILE = Path("ramanujan_state.json")


def log_discovery(record):
    with LOGFILE.open('a') as f:
        f.write(json.dumps(record) + '\n')
    vd = record.get('verified_digits', '?')
    cx = record.get('complexity', '?')
    print(f"\n{'='*60}")
    print(f"  DISCOVERY: {record['match']}")
    print(f"  CF: a={record['a']}, b={record['b']}")
    print(f"  Value: {record['value'][:40]}...")
    print(f"  Residual: {record['residual']}  |  Verified: {vd}d  |  Complexity: {cx}")
    print(f"{'='*60}\n")


def save_state(cycle, population, discoveries, temperature, best_scores,
               last_discovery_cycle=0):
    sdi, combos = structural_diversity_index(population, min(20, len(population)))
    trap_count = sum(1 for p in population[:20] if p.hit and is_fitness_trap(p.hit))
    state = {
        'cycle': cycle,
        'timestamp': datetime.now().isoformat(),
        'temperature': temperature,
        'discoveries': len(discoveries),
        'last_discovery_cycle': last_discovery_cycle,
        'best_scores': best_scores[-20:],
        'elite_population': [asdict(p) for p in population[:10]],
        'structural_diversity_index': sdi,
        'degree_combos': sorted([list(c) for c in combos]),
        'fitness_traps_in_top20': trap_count,
    }
    STATEFILE.write_text(json.dumps(state, indent=2))


def load_state():
    if STATEFILE.exists():
        return json.loads(STATEFILE.read_text())
    return None


def load_seen_hits_from_log():
    """Rebuild seen_hits set from the discovery log to avoid re-logging on resume."""
    seen = set()
    if LOGFILE.exists():
        for line in LOGFILE.read_text().strip().split('\n'):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                seen.add((tuple(d['a']), tuple(d['b'])))
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


# ── leaderboard ───────────────────────────────────────────────────────────────
def _leaderboard_score(entry):
    """Score for leaderboard ranking: verified_digits - 2*complexity."""
    vd = entry.get('verified_digits', 0) or 0
    cx = entry.get('complexity', 5) or 5
    return vd - 2 * cx


def build_leaderboard(logfile=None, top_n=10):
    """Build top-N leaderboard from discovery log."""
    if logfile is None:
        logfile = LOGFILE
    if not logfile.exists():
        return []

    entries = []
    seen_keys = set()
    for line in logfile.read_text().strip().split('\n'):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Skip trivial
        m = d.get('match', '')
        if m in ('1','2','3','4','5','6','7','8'):
            continue
        if is_spurious_match(m):
            continue
        if 'a' not in d or 'b' not in d:
            continue
        key = (tuple(d['a']), tuple(d['b']))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        entries.append(d)

    entries.sort(key=_leaderboard_score, reverse=True)
    return entries[:top_n]


def print_leaderboard(logfile=None, top_n=10):
    """Print top-N discoveries ranked by quality score."""
    board = build_leaderboard(logfile, top_n)
    if not board:
        return

    print("\n" + "-"*70)
    print(f"  TOP {len(board)} LEADERBOARD  (score = verified_digits - 2*complexity)")
    print("-"*70)
    for i, entry in enumerate(board, 1):
        vd = entry.get('verified_digits', 0) or 0
        cx = entry.get('complexity', 0) or 0
        score = _leaderboard_score(entry)
        a_str = str(entry['a'])
        b_str = str(entry['b'])
        match = entry['match']
        print(f"  {i:2d}. {match:22s}  a={a_str:18s} b={b_str:10s}  "
              f"vd={vd:5.1f}  cx={cx:.1f}  score={score:.1f}")
    print("-"*70 + "\n")

    return board


# ── leaderboard watch: convergents table + Wronskian stability ────────────────
WATCH_THRESHOLD = 300  # trigger detailed analysis when score exceeds this

def _convergents_table(a_coeffs, b_coeffs, depths=(10, 20, 50, 100, 200, 500)):
    """Compute convergent values at increasing depths for a LaTeX-ready table."""
    saved_dps = mp.dps
    mp.dps = 250
    rows = []
    prev = None
    for d in depths:
        val = eval_pcf(a_coeffs, b_coeffs, depth=d)
        if val is None:
            rows.append((d, None, None))
            continue
        if prev is not None and prev != 0:
            diff = abs(val - prev)
            digits = float(-mpm.log10(diff)) if diff > 0 else 250.0
        else:
            digits = 0.0
        rows.append((d, nstr(val, 40), round(digits, 1)))
        prev = val
    mp.dps = saved_dps
    return rows


def _wronskian_stability(a_coeffs, b_coeffs, depth=500):
    """Check Wronskian-style stability: compare forward vs backward CF evaluation.
    A well-conditioned CF should give the same value either way.
    Returns (stable: bool, agreement_digits: float)."""
    saved_dps = mp.dps
    mp.dps = 250
    try:
        backward_val = eval_pcf(a_coeffs, b_coeffs, depth=depth)
        if backward_val is None:
            return False, 0.0

        # Forward evaluation (Euler-Wallis recurrence)
        def a(n): return sum(mpf(c) * n**i for i, c in enumerate(a_coeffs))
        def b(n): return sum(mpf(c) * n**i for i, c in enumerate(b_coeffs))

        p_prev, p_curr = mpf(1), b(0)
        q_prev, q_curr = mpf(0), mpf(1)
        for n in range(1, depth + 1):
            an, bn = a(n), b(n)
            p_new = bn * p_curr + an * p_prev
            q_new = bn * q_curr + an * q_prev
            p_prev, p_curr = p_curr, p_new
            q_prev, q_curr = q_curr, q_new
            # Renormalize to prevent overflow
            if abs(q_curr) > mpf(10)**100:
                scale = q_curr
                p_prev /= scale; p_curr /= scale
                q_prev /= scale; q_curr /= scale

        if abs(q_curr) < mpf(10)**(-200):
            return False, 0.0
        forward_val = p_curr / q_curr

        diff = abs(forward_val - backward_val)
        if diff == 0:
            return True, 250.0
        digits = float(-mpm.log10(diff))
        return digits > 100, round(digits, 1)
    except Exception:
        return False, 0.0
    finally:
        mp.dps = saved_dps


def leaderboard_watch(entry):
    """Triggered when a discovery exceeds WATCH_THRESHOLD score.
    Generates a convergents table and Wronskian stability report."""
    score = _leaderboard_score(entry)
    if score < WATCH_THRESHOLD:
        return

    a, b = entry['a'], entry['b']
    match = entry['match']

    sep = '#' * 70
    print(f"\n{sep}")
    print(f"  LEADERBOARD WATCH TRIGGERED  (score={score:.1f} > {WATCH_THRESHOLD})")
    print(f"  Discovery: {match}")
    print(f"  CF: a={a}, b={b}")
    print(sep)

    # Convergents table
    print("\n  CONVERGENTS TABLE (for LaTeX):")
    print(f"  {'Depth':>8s}  {'Value (40 digits)':>44s}  {'Δ digits':>10s}")
    print(f"  {'-'*8}  {'-'*44}  {'-'*10}")
    rows = _convergents_table(a, b)
    for depth, val, digits in rows:
        val_str = val if val else "diverges"
        dig_str = f"{digits:.1f}" if digits else "-"
        print(f"  {depth:>8d}  {val_str:>44s}  {dig_str:>10s}")

    # Wronskian stability
    stable, agree_digits = _wronskian_stability(a, b)
    status = "STABLE" if stable else "UNSTABLE"
    print(f"\n  WRONSKIAN STABILITY: {status} ({agree_digits:.1f} digits agreement)")

    # Save detailed report
    report = {
        'match': match, 'a': a, 'b': b, 'score': score,
        'convergents': rows,
        'wronskian_stable': stable,
        'wronskian_digits': agree_digits,
        'timestamp': datetime.now().isoformat(),
    }
    report_file = Path(f"watch_report_{match.replace('/', '_').replace('*', 'x')}.json")
    report_file.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n  Report saved to {report_file}")
    print(sep + "\n")


# ── evaluation cycle ──────────────────────────────────────────────────────────
def evaluate_population(population, constants, depth, tol_digits, seen_hits,
                        verify=True, verify_prec=200, verify_depth=1000):
    results = []
    for p in population:
        # Skip known-telescoping CFs early
        if is_telescoping(p.a, p.b):
            p.score = -2
            results.append(p)
            continue

        val = eval_pcf(p.a, p.b, depth=depth)
        if not is_reasonable(val):
            p.score = -1
            results.append(p)
            continue

        # Quick ratio check against constants
        best_residual = mpf(1)
        best_match = None
        val_str = nstr(val, 20)

        for name, cval in constants.items():
            for numer in [1, 2, 3, 4]:
                for denom in [1, 2, 3, 4, 6, 8]:
                    ratio = mpf(numer) / denom * cval
                    res = abs(val - ratio)
                    if res < best_residual:
                        best_residual = res
                        label = f"{numer}/{denom}*{name}" if (numer != 1 or denom != 1) else name
                        best_match = (label, res)

        # Score = negative log residual (higher is better) minus complexity penalty
        # Phase 2: subtract fitness trap penalty for known-constant matches
        if best_match:
            raw_score = float(-mpm.log10(max(best_match[1], mpf(10)**(-mp.dps + 5))))
            penalty = complexity_score(p.a, p.b)
            trap_pen = fitness_trap_penalty(best_match[0], raw_score)
            p.score = raw_score - penalty - trap_pen

            seen_key = (tuple(p.a), tuple(p.b))
            if raw_score > tol_digits and seen_key not in seen_hits:
                # Filter spurious mpmath.identify matches
                if is_spurious_match(best_match[0]):
                    seen_hits.add(seen_key)
                    results.append(p)
                    continue

                # High-precision verification gate
                verified = True
                verify_digits = raw_score
                if verify and raw_score > tol_digits + 5:
                    verified, verify_digits = verify_match_high_precision(
                        p.a, p.b, best_match[0], constants,
                        verify_prec=verify_prec, verify_depth=verify_depth
                    )

                if verified:
                    p.hit = best_match[0]
                    record = {
                        'cycle': None,
                        'a': p.a, 'b': p.b,
                        'value': val_str,
                        'match': best_match[0],
                        'residual': float(mpm.log10(max(best_match[1], mpf(10)**(-mp.dps+5)))),
                        'verified_digits': round(verify_digits, 1),
                        'complexity': round(penalty, 2),
                        'timestamp': datetime.now().isoformat(),
                    }
                    log_discovery(record)
                    leaderboard_watch(record)
                    # Adaptive: trigger conjecture verification + convergence map
                    try:
                        from adaptive_discovery import on_discovery
                        on_discovery(record)
                    except Exception:
                        pass
                else:
                    # Near-miss: high raw score but failed verification
                    if raw_score > tol_digits + 3:
                        try:
                            from adaptive_discovery import on_near_miss
                            on_near_miss({
                                'a': p.a, 'b': p.b,
                                'value': val_str,
                                'match': best_match[0],
                                'residual': float(mpm.log10(max(best_match[1], mpf(10)**(-mp.dps+5)))),
                                'verified_digits': round(verify_digits, 1),
                                'timestamp': datetime.now().isoformat(),
                            })
                        except Exception:
                            pass
                seen_hits.add(seen_key)
        else:
            p.score = 0.0

        results.append(p)

    return sorted(results, key=lambda p: p.score, reverse=True)


# ── adaptive mutation strategy ────────────────────────────────────────────────
# Track reheat state across calls
_reheat_sustain_until = 0   # cycle until which high-T is sustained
_last_reheat_tier = 0       # highest tier triggered so far in current stale run

def adapt_temperature(temperature, recent_scores, cycle, last_discovery_cycle=0):
    """
    Cool if we're finding good hits; heat up if stuck.
    Periodic reheat to escape local optima.
    Enhanced: tiered reheat with sustained heating window.
    Phase 2: auto-escalation — progressively higher tiers without manual intervention.
    """
    global _reheat_sustain_until, _last_reheat_tier

    if len(recent_scores) < 5:
        return temperature

    avg = sum(recent_scores[-5:]) / 5
    prev_avg = sum(recent_scores[-10:-5]) / 5 if len(recent_scores) >= 10 else avg

    # Cosine annealing with warm restarts every 200 cycles
    period = 200
    phase = (cycle % period) / period  # 0..1
    cosine_temp = 0.5 + 2.5 * (1 + math.cos(math.pi * phase)) / 2  # range [0.5, 3.0]

    # Sustained reheat window: don't cool down during active reheat
    if cycle < _reheat_sustain_until:
        return max(temperature, 1.5)

    # Reset tier tracker when a discovery happens
    cycles_since_discovery = cycle - last_discovery_cycle
    if cycles_since_discovery == 0:
        _last_reheat_tier = 0

    # Tiered reheat: escalating intensity the longer we're stuck
    # Phase 2: each tier fires once per stale run, regardless of current T
    if cycles_since_discovery > 200 and _last_reheat_tier < 3:
        # Tier 3: extreme reheat — nearly full randomization
        new_temp = 4.0
        sustain = 30
        _last_reheat_tier = 3
        print(f"\n  >> REHEAT T3 (EXTREME): stale {cycles_since_discovery} cycles, T→{new_temp}")
        _reheat_sustain_until = cycle + sustain
        return new_temp
    elif cycles_since_discovery > 120 and _last_reheat_tier < 2:
        # Tier 2: strong reheat — auto-escalation (no manual approval needed)
        new_temp = 2.5
        sustain = 20
        _last_reheat_tier = 2
        print(f"\n  >> REHEAT T2 (STRONG): stale {cycles_since_discovery} cycles, T→{new_temp}")
        _reheat_sustain_until = cycle + sustain
        return new_temp
    elif cycles_since_discovery > 80 and _last_reheat_tier < 1:
        # Tier 1: standard reheat
        new_temp = 1.5
        sustain = 15
        _last_reheat_tier = 1
        print(f"\n  >> REHEAT T1: stale {cycles_since_discovery} cycles, T→{new_temp}")
        _reheat_sustain_until = cycle + sustain
        return new_temp

    # Blend: use cosine schedule as baseline, adjust by performance
    if avg > prev_avg + 0.5:        # improving: cool slightly
        temperature = max(0.3, temperature * 0.92)
    elif avg < prev_avg - 0.5:      # degrading: heat up
        temperature = min(8.0, temperature * 1.15)
    else:
        # Drift toward cosine schedule
        temperature = 0.7 * temperature + 0.3 * cosine_temp

    # Floor: never go below 0.3 (keeps exploration alive)
    temperature = max(0.3, temperature)
    return round(temperature, 3)


# ── fertile form generators ───────────────────────────────────────────────────
def random_fertile_params(rng):
    """Generate CFs biased toward known fertile structures.
    Weights based on historical success rate of each family type.
    v2: boosted Apéry-cubic/sextic for ζ(3) deep search."""
    form = rng.random()

    if form < 0.12:
        # Pi-family neighborhood: a(n) = c0 + c1*n + c2*n^2, b(n) = b0 + b1*n
        c2 = rng.choice([-3, -2, -1, 1, 2, 3])
        c1 = rng.choice([i for i in range(-11, 12) if i % 2 == 1])
        c0 = rng.randint(-3, 3)
        b0 = rng.randint(1, 5)
        b1 = rng.choice([1, 2, 3, 4, 5])
        return PCFParams(a=[c0, c1, c2], b=[b0, b1])

    elif form < 0.22:
        # e-family: classical CFs for e use linear a(n), linear b(n)
        # e = [2; 1,2,1, 1,4,1, 1,6,1, ...] but as GCF:
        # a(n)=-n, b(n)=n+c  or  a(n)=-cn, b(n)=dn+e
        variant = rng.random()
        if variant < 0.4:
            # a(n) = -c*n, b(n) = d*n + e
            c = rng.choice([1, 2, 3, 4])
            d = rng.choice([1, 2, 3, 4])
            e = rng.randint(1, 8)
            return PCFParams(a=[0, -c], b=[e, d])
        elif variant < 0.7:
            # a(n) = -c*n^2, b(n) = d*n + e  (exponential-related)
            c = rng.choice([1, 2, 4])
            d = rng.choice([1, 2, 3, 4, 6])
            e = rng.randint(1, 6)
            return PCFParams(a=[0, 0, -c], b=[e, d])
        else:
            # tanh-type: a(n) = n^2, b(n) = (2n+1)*c
            c = rng.choice([1, 2, 3, 5])
            return PCFParams(a=[0, 0, 1], b=[c, 2*c])

    elif form < 0.30:
        # Golden ratio / quadratic irrationals: a(n)=const, b(n)=const or linear
        a0 = rng.choice([1, 2, 3, 4, -1, -2, -3])
        b_const = rng.randint(1, 5)
        b_lin = rng.choice([0, 0, 0, 1, 2])
        return PCFParams(a=[a0], b=[b_const, b_lin])

    elif form < 0.36:
        # Brouncker-family: a(n) = c*n^2 + d, b(n) = e*n + f
        c = rng.choice([-4, -2, -1, 1, 2, 4])
        d = rng.randint(-5, 5)
        e = rng.choice([0, 1, 2, 3, 4])
        f = rng.randint(1, 5)
        return PCFParams(a=[d, 0, c], b=[f, e])

    elif form < 0.54:
        # Apéry-like cubic: a(n) = c0 + c1*n + c2*n^2 + c3*n^3
        c3 = rng.choice([-2, -1, 1, 2])
        c2 = rng.randint(-3, 3)
        c1 = rng.randint(-3, 3)
        c0 = rng.randint(-2, 2)
        b0 = rng.randint(1, 4)
        b1 = rng.randint(0, 5)
        b2 = rng.randint(0, 4)
        return PCFParams(a=[c0, c1, c2, c3], b=[b0, b1, b2])

    elif form < 0.71:
        # Apéry-neighborhood: perturb a(n)=-n^6, b(n)=34n^3-51n^2+27n-5
        base_a = [0, 0, 0, 0, 0, 0, -1]
        base_b = [-5, 27, -51, 34]
        a_out = [c + rng.randint(-1, 1) for c in base_a]
        b_out = [c + rng.randint(-2, 2) for c in base_b]
        b_out[0] = min(-1, b_out[0])
        return PCFParams(a=a_out, b=b_out)

    elif form < 0.78:
        # Extended pi-family: vary b(n) slope around known b(n)=3n+1
        c2 = -2
        c1 = rng.choice([i for i in range(-1, 14) if i % 2 == 1])
        c0 = rng.randint(-2, 2)
        b0 = rng.randint(1, 3)
        b1 = rng.choice([2, 3, 4, 5])
        return PCFParams(a=[c0, c1, c2], b=[b0, b1])

    elif form < 0.85:
        # Log-family: CFs related to log(1+x), log(2), log(3)
        # a(n) pattern: alternating signs, n^2 or n*(n+k)
        k = rng.randint(0, 4)
        sign = rng.choice([-1, 1])
        c = rng.choice([1, 2, 4])
        b0 = rng.randint(1, 4)
        b1 = rng.choice([1, 2, 3])
        return PCFParams(a=[0, sign*k, sign*c], b=[b0, b1])

    elif form < 0.92:
        # Quartic/quintic a(n) with quadratic b(n) — deeper structure
        deg_a = rng.choice([4, 4, 5, 6])
        deg_b = rng.choice([2, 3, 3])
        a_out = [rng.randint(-3, 3) for _ in range(deg_a)]
        a_out.append(rng.choice([-2, -1, 1, 2]))
        b_out = [rng.randint(1, 5)]
        b_out += [rng.randint(-5, 5) for _ in range(deg_b)]
        return PCFParams(a=a_out, b=b_out)

    elif form < 0.97:
        # Deep Space: symmetry-constrained CFs
        try:
            from deep_space import generate_symmetry_constrained
            a, b, _ = generate_symmetry_constrained(rng)
            return PCFParams(a=a, b=b)
        except ImportError:
            pass
        # Fallback to wild card
        a_deg = rng.choice([1, 2, 2, 2, 3])
        b_deg = rng.choice([1, 1, 1, 2])
        return random_params(a_deg=a_deg, b_deg=b_deg,
                           coeff_range=rng.randint(3, 7), rng=rng)

    else:
        # Wild card: purely random
        a_deg = rng.choice([1, 2, 2, 2, 3])
        b_deg = rng.choice([1, 1, 1, 2])
        return random_params(a_deg=a_deg, b_deg=b_deg,
                           coeff_range=rng.randint(3, 7), rng=rng)


def evolve_population(population, pop_size, temperature, rng):
    """Tournament selection + mutation + crossover to fill next generation.
    Biased toward fertile polynomial forms.
    During reheat (T > 1.3): purge elites, inject structural diversity.
    Phase 2: structural injection when degree diversity drops below threshold."""
    is_reheat = temperature > 1.3

    # Phase 2: check structural diversity — inject if clustering detected
    sdi, combos = structural_diversity_index(population, min(20, len(population)))
    needs_structural_injection = (sdi <= 3)  # fewer than 4 unique degree combos

    if is_reheat:
        # Reheat mode: keep only top 2 *unique* elites, flood with diversity
        # Deduplicate by (a, b) to prevent monoculture carry-over
        seen_structs = set()
        elite = []
        for p in population:
            key = (tuple(p.a), tuple(p.b))
            if key not in seen_structs:
                seen_structs.add(key)
                elite.append(p)
                if len(elite) >= 2:
                    break
        if not elite:
            elite = population[:1]
    else:
        elite_n = max(2, pop_size // 5)
        elite = population[:elite_n]
    new_pop = list(elite)

    while len(new_pop) < pop_size:
        strategy = rng.random()

        if is_reheat:
            # Reheat strategy mix: heavily biased toward exploration
            if strategy < 0.10:
                # Small fraction: mutate surviving elite
                parent = rng.choice(elite)
                child = mutate(parent, temperature, rng)
            elif strategy < 0.35:
                # Fertile-form biased random (known productive families)
                child = random_fertile_params(rng)
            elif strategy < 0.55:
                # Higher-degree exploration (cubic a, quadratic b)
                a_deg = rng.choice([2, 3, 3, 4])
                b_deg = rng.choice([1, 2, 2, 3])
                child = random_params(
                    a_deg=a_deg,
                    b_deg=b_deg,
                    coeff_range=max(5, int(temperature * 3)),
                    rng=rng,
                )
            elif strategy < 0.75:
                # Offset seeds: known hits + random perturbation
                seeds = seed_population()
                base = rng.choice(seeds)
                child = mutate(base, temperature * 1.5, rng)
            else:
                # Pure random with wide coefficient range
                a_deg = rng.choice([1, 2, 2, 3])
                b_deg = rng.choice([1, 1, 2])
                child = random_params(
                    a_deg=a_deg,
                    b_deg=b_deg,
                    coeff_range=max(8, int(temperature * 4)),
                    rng=rng,
                )
            new_pop.append(child)
        elif needs_structural_injection:
            # Phase 2: force structural diversity when degrees cluster
            if strategy < 0.30:
                parent = rng.choice(elite)
                child = mutate(parent, temperature, rng)
            elif strategy < 0.50:
                # Force cubic/quartic a(n) with quadratic/cubic b(n)
                a_deg = rng.choice([3, 3, 4, 4, 5])
                b_deg = rng.choice([2, 2, 3])
                child = random_params(
                    a_deg=a_deg,
                    b_deg=b_deg,
                    coeff_range=max(4, int(temperature * 2)),
                    rng=rng,
                )
            elif strategy < 0.70:
                child = random_fertile_params(rng)
            else:
                # Asymmetric: high deg_a, low deg_b or vice versa
                if rng.random() < 0.5:
                    a_deg = rng.choice([4, 5, 6])
                    b_deg = 1
                else:
                    a_deg = rng.choice([1, 2])
                    b_deg = rng.choice([3, 4])
                child = random_params(
                    a_deg=a_deg,
                    b_deg=b_deg,
                    coeff_range=max(3, int(temperature * 2)),
                    rng=rng,
                )
            new_pop.append(child)
        else:
            # Normal mode
            if strategy < 0.35:
                parent = rng.choice(elite)
                child = mutate(parent, temperature, rng)
            elif strategy < 0.55 and len(elite) >= 2:
                p1, p2 = rng.sample(elite, 2)
                child = crossover(p1, p2, rng)
                child = mutate(child, temperature * 0.5, rng)
            elif strategy < 0.80:
                child = random_fertile_params(rng)
            else:
                a_deg = rng.choice([1, 2, 2, 3, 3])
                b_deg = rng.choice([1, 1, 2])
                child = random_params(
                    a_deg=a_deg,
                    b_deg=b_deg,
                    coeff_range=max(3, int(temperature * 2)),
                    rng=rng,
                )
            new_pop.append(child)

    return new_pop


# ── systematic grid scan (every N cycles) ────────────────────────────────────
def systematic_scan(constants, depth, tol_digits, coeff_range=3, seen_hits=None):
    """Exhaustive small-coefficient search."""
    if seen_hits is None:
        seen_hits = set()
    hits = []
    total = 0
    r = range(-coeff_range, coeff_range + 1)
    for a0, a1, a2, b0, b1 in itertools.product(r, r, r, range(1, coeff_range+1), r):
        p = PCFParams(a=[a0, a1, a2], b=[b0, b1])
        val = eval_pcf(p.a, p.b, depth=depth)
        if not is_reasonable(val):
            continue
        total += 1
        for name, cval in constants.items():
            res = abs(val - cval)
            if res < mpf(10)**(-tol_digits):
                key = name + str(p.a) + str(p.b)
                if key not in seen_hits:
                    seen_hits.add(key)
                    hits.append((p, name, res))
    return hits, total


# ── family clustering & summary report ────────────────────────────────────────
def cluster_discoveries(logfile=None):
    """Read discovery log and cluster by b(n) polynomial form."""
    if logfile is None:
        logfile = LOGFILE
    if not logfile.exists():
        return {}

    lines = logfile.read_text().strip().split('\n')
    families = defaultdict(list)

    for line in lines:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if 'a' not in d or 'b' not in d:
            continue
        b_key = tuple(d['b'])
        families[b_key].append(d)

    return dict(families)


def print_family_report(logfile=None):
    """Print clustered discovery report grouped by b(n) form."""
    families = cluster_discoveries(logfile)
    if not families:
        print("No discoveries to report.")
        return

    # Filter: skip families where all matches are trivial integers
    interesting_families = {}
    for b_key, members in families.items():
        non_trivial = [m for m in members
                       if m['match'] not in ('1','2','3','4','5','6','7','8')
                       and not is_spurious_match(m['match'])]
        if non_trivial:
            interesting_families[b_key] = non_trivial

    sep = '=' * 70
    dash = '-' * 50
    print(f"\n{sep}")
    print(f"  FAMILY REPORT  ({len(interesting_families)} non-trivial families)")
    print(sep)

    for b_key in sorted(interesting_families, key=lambda k: len(interesting_families[k]), reverse=True):
        members = interesting_families[b_key]
        b_str = ' + '.join(f'{c}n^{i}' if i > 0 else str(c)
                          for i, c in enumerate(b_key) if c != 0) or '0'
        print(f"\n  b(n) = {b_str}  ({len(members)} members)")
        print(f"  {dash}")

        for m in sorted(members, key=lambda x: str(x['a'])):
            a_str = str(m['a'])
            vd = m.get('verified_digits', '?')
            cx = m.get('complexity', '?')
            match_str = m['match']
            print(f"    a={a_str:20s}  ->  {match_str:25s}  ({vd}d verified, cx={cx})")

    # Highlight parametric patterns
    pi_family = interesting_families.get((1, 3), [])
    if len(pi_family) >= 3:
        print("\n  >> PARAMETRIC PATTERN DETECTED in b(n)=3n+1 family:")
        print("     a(n) = -2n^2 + (2k+1)n  for k=0,1,2,...")
        print("     Producing rational multiples of 1/pi")

    print(f"\n{sep}\n")


# ── degree-restricted random search mode ──────────────────────────────────────
def run_dr_mode(args, constants):
    """Degree-restricted random search: random polynomial CFs with PSLQ matching."""
    mp.dps = args.precision + 20
    rng = random.Random(args.seed)
    seen_hits = set()
    discoveries = []

    # Filter constants if target specified
    if args.target:
        target_consts = {}
        target_key = args.target.lower().replace('_', '').replace('-', '')
        for name, val in constants.items():
            nk = name.lower().replace('_', '').replace('-', '').replace('^', '').replace('/', '').replace('*', '')
            if target_key in nk or nk in target_key:
                target_consts[name] = val
        if not target_consts:
            # Try exact match fallback
            for name, val in constants.items():
                if args.target.lower() == name.lower():
                    target_consts[name] = val
                    break
        if not target_consts:
            print(f"Warning: target '{args.target}' not found in constants. Using all constants.")
            target_consts = constants
        else:
            print(f"Targeting: {list(target_consts.keys())}")
    else:
        target_consts = constants

    print(f"\nDR Mode: deg_alpha={args.deg_alpha}, deg_beta={args.deg_beta}, "
          f"coeff_range={args.coeff_range}")
    print(f"  Precision: {args.precision} dps | Depth: {args.depth} | "
          f"Tol: {args.tol} digits | Pop/cycle: {args.pop}")
    print(f"  Searching {len(target_consts)} target constants\n")

    max_cycles = args.cycles if args.cycles > 0 else float('inf')
    cycle = 0
    total_evaluated = 0

    try:
        while cycle < max_cycles:
            cycle += 1
            t0 = time.time()
            batch_hits = 0

            for _ in range(args.pop):
                p = random_params(
                    a_deg=args.deg_alpha,
                    b_deg=args.deg_beta,
                    coeff_range=args.coeff_range,
                    rng=rng,
                )
                val = eval_pcf(p.a, p.b, depth=args.depth)
                if not is_reasonable(val):
                    continue
                total_evaluated += 1

                # PSLQ match against targets
                for name, cval in target_consts.items():
                    for numer in [1, 2, 3, 4, 6, 8]:
                        for denom in [1, 2, 3, 4, 6, 8, 12, 16]:
                            ratio = mpf(numer) / denom * cval
                            res = abs(val - ratio)
                            if res < mpf(10)**(-args.tol):
                                key = (tuple(p.a), tuple(p.b))
                                if key not in seen_hits:
                                    seen_hits.add(key)
                                    batch_hits += 1
                                    label = f"{numer}/{denom}*{name}" if (numer != 1 or denom != 1) else name
                                    record = {
                                        'cycle': cycle, 'type': 'dr',
                                        'a': p.a, 'b': p.b,
                                        'value': nstr(val, 20),
                                        'match': label,
                                        'residual': float(mpm.log10(max(res, mpf(10)**(-mp.dps+5)))),
                                        'timestamp': datetime.now().isoformat(),
                                    }
                                    discoveries.append(record)
                                    log_discovery(record)

                # Also try full PSLQ
                if total_evaluated % 100 == 0:
                    result = pslq_match(val, target_consts, tol_digits=args.tol)
                    if result:
                        key = (tuple(p.a), tuple(p.b))
                        if key not in seen_hits:
                            seen_hits.add(key)
                            batch_hits += 1
                            record = {
                                'cycle': cycle, 'type': 'dr-pslq',
                                'a': p.a, 'b': p.b,
                                'value': nstr(val, 20),
                                'match': result[0],
                                'residual': float(result[1]) if result[1] else 0,
                                'timestamp': datetime.now().isoformat(),
                            }
                            discoveries.append(record)
                            log_discovery(record)

            elapsed = time.time() - t0
            print(f"Cycle {cycle:4d} | evaluated={total_evaluated} | "
                  f"hits={batch_hits} | total_disc={len(discoveries)} | {elapsed:.1f}s")

            if cycle % 5 == 0:
                save_state(cycle, [], discoveries, 0, [])

    except KeyboardInterrupt:
        print("\nInterrupted.")

    print(f"\nDR mode done. {len(discoveries)} discoveries from {total_evaluated} evaluations.")


# ── CMF exhaustive coefficient sweep ──────────────────────────────────────────
def run_cmf_mode(args, constants):
    """Conservative Matrix Field search: exhaustive enumeration of polynomial
    coefficient space with PSLQ matching against target constants."""
    mp.dps = args.precision + 20
    seen_hits = set()
    discoveries = []

    # Filter constants if target specified
    if args.target:
        target_consts = {}
        target_key = args.target.lower().replace('_', '').replace('-', '')
        for name, val in constants.items():
            nk = name.lower().replace('_', '').replace('-', '').replace('^', '').replace('/', '').replace('*', '')
            if target_key in nk or nk in target_key:
                target_consts[name] = val
        if not target_consts:
            for name, val in constants.items():
                if args.target.lower() == name.lower():
                    target_consts[name] = val
                    break
        if not target_consts:
            print(f"Warning: target '{args.target}' not found in constants. Using all constants.")
            target_consts = constants
        else:
            print(f"  Targeting: {list(target_consts.keys())}")
    else:
        target_consts = constants

    da = args.deg_alpha
    db = args.deg_beta
    cr = args.coeff_range
    depth = args.depth
    tol = args.tol

    print(f"\nCMF Exhaustive Coefficient Sweep")
    print(f"  deg(alpha)={da}, deg(beta)={db}, coeff_range=[-{cr},{cr}]")
    print(f"  Precision: {args.precision} dps  |  Depth: {depth}")
    print(f"  Tolerance: {tol} digits  |  Target constants: {len(target_consts)}")
    print(f"  Log: {LOGFILE}")

    # Build all coefficient tuples for alpha: (da+1) coefficients in [-cr, cr]
    # Beta: (db+1) coefficients, but b[0] >= 1 to avoid zero start
    a_range = range(-cr, cr + 1)
    b_range = range(-cr, cr + 1)
    b0_range = range(1, cr + 1)

    # Count total combinations
    a_combos = (2 * cr + 1) ** (da + 1)
    b_combos = cr * ((2 * cr + 1) ** db)
    total = a_combos * b_combos
    print(f"  Total combinations: {total:,}")
    print()

    evaluated = 0
    matched = 0
    t_start = time.time()
    last_report = t_start

    # Generate alpha coefficient tuples
    a_indices = list(range(da + 1))
    b_indices = list(range(db + 1))

    for a_coeffs in itertools.product(a_range, repeat=da + 1):
        # Skip trivial: all-zero alpha
        if all(c == 0 for c in a_coeffs):
            continue

        for b0 in b0_range:
            for b_rest in itertools.product(b_range, repeat=db):
                b_coeffs = [b0] + list(b_rest)

                val = eval_pcf(list(a_coeffs), list(b_coeffs), depth=depth)
                evaluated += 1

                if not is_reasonable(val):
                    continue

                # Check against target constants with small integer ratios
                for name, cval in target_consts.items():
                    for numer in [1, 2, 3, 4]:
                        for denom in [1, 2, 3, 4, 6, 8]:
                            ratio = mpf(numer) / denom * cval
                            res = abs(val - ratio)
                            if res < mpf(10)**(-tol):
                                key = (tuple(a_coeffs), tuple(b_coeffs), name, numer, denom)
                                if key not in seen_hits:
                                    seen_hits.add(key)
                                    matched += 1
                                    label = f"{numer}/{denom}*{name}" if (numer != 1 or denom != 1) else name
                                    record = {
                                        'cycle': 0, 'type': 'cmf',
                                        'a': list(a_coeffs), 'b': list(b_coeffs),
                                        'value': nstr(val, 20),
                                        'match': label,
                                        'residual': float(mpm.log10(max(res, mpf(10)**(-mp.dps+5)))),
                                        'timestamp': datetime.now().isoformat(),
                                    }
                                    log_discovery(record)
                                    discoveries.append(record)

                # Also try PSLQ for deeper matching
                match_result = pslq_match(val, target_consts, tol_digits=tol)
                if match_result:
                    rel_str, residual = match_result
                    pkey = (tuple(a_coeffs), tuple(b_coeffs), 'pslq')
                    if pkey not in seen_hits:
                        seen_hits.add(pkey)
                        matched += 1
                        record = {
                            'cycle': 0, 'type': 'cmf_pslq',
                            'a': list(a_coeffs), 'b': list(b_coeffs),
                            'value': nstr(val, 20),
                            'match': rel_str,
                            'residual': float(residual) if residual else 0.0,
                            'timestamp': datetime.now().isoformat(),
                        }
                        log_discovery(record)
                        discoveries.append(record)

                # Progress report every 10 seconds
                now = time.time()
                if now - last_report > 10:
                    elapsed = now - t_start
                    rate = evaluated / elapsed if elapsed > 0 else 0
                    pct = 100.0 * evaluated / total if total > 0 else 0
                    print(f"  [{pct:5.1f}%] {evaluated:,}/{total:,} evaluated | "
                          f"{matched} hits | {rate:.0f}/s | {elapsed:.0f}s elapsed",
                          flush=True)
                    last_report = now

    elapsed = time.time() - t_start
    print(f"\nCMF sweep done. {len(discoveries)} discoveries from {evaluated:,} evaluations in {elapsed:.1f}s.")


# ── main loop ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='Ramanujan Breakthrough Generator — self-iterating PCF discovery engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --cycles 30 --seed 42
  %(prog)s --mode cmf --coeff-range 3 --target pi
  %(prog)s --mode dr --deg-alpha 3 --deg-beta 2 --cycles 100
  %(prog)s --report
  %(prog)s --query "Apéry-like cubic numerators for zeta(3)" --cycles 50
""",
    )
    parser.add_argument('--mode', choices=['evolve', 'dr', 'mitm', 'cmf'], default='evolve',
                        help='Search mode: evolve (GA), dr (degree-restricted random), '
                             'mitm (meet-in-middle), cmf (exhaustive coefficient sweep)')
    parser.add_argument('--query', type=str, default=None,
                        help='Natural-language research context/query to guide search '
                             '(used by research agent integration)')
    parser.add_argument('--style', choices=['ramanujan', 'apery', 'apery4', 'brouncker', 'wild'],
                        default='ramanujan',
                        help='Discovery style bias: ramanujan (pi-family emphasis), '
                             'apery (cubic numerators), apery4 (quartic/sextic), '
                             'brouncker (quadratic), wild (random)')
    parser.add_argument('--num', type=int, default=None,
                        help='Alias for --cycles (number of formulas/cycles to generate)')
    parser.add_argument('--validation-level', choices=['none', 'fast', 'full'], default='full',
                        help='Validation rigor: none, fast (50d), full (200d+)')
    parser.add_argument('--target', type=str, default=None,
                        help='Target constant name (e.g. zeta3, pi, log2). None = search all.')
    parser.add_argument('--deg-alpha', type=int, default=2,
                        help='Degree of a(n) polynomial')
    parser.add_argument('--deg-beta', type=int, default=1,
                        help='Degree of b(n) polynomial')
    parser.add_argument('--coeff-range', type=int, default=5,
                        help='Coefficient range [-R, R] for polynomial coefficients')
    parser.add_argument('--cycles', type=int, default=0,
                        help='Number of cycles to run (0 = infinite)')
    parser.add_argument('--precision', type=int, default=60,
                        help='mpmath decimal precision')
    parser.add_argument('--depth', type=int, default=300,
                        help='CF evaluation depth (convergents)')
    parser.add_argument('--pop', type=int, default=40,
                        help='Population size per cycle')
    parser.add_argument('--tol', type=int, default=15,
                        help='PSLQ match tolerance (digits)')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--scan-every', type=int, default=10,
                        help='Run systematic grid scan every N cycles')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from saved state')
    parser.add_argument('--fresh', action='store_true',
                        help='Clear discovery log and state, start fresh')
    parser.add_argument('--init-temp', type=float, default=2.0,
                        help='Initial temperature (default 2.0; use 0.8-1.0 for focused search)')
    parser.add_argument('--report', action='store_true',
                        help='Print family report from existing discoveries and exit')
    parser.add_argument('--no-verify', action='store_true',
                        help='Skip high-precision verification (faster but noisier)')
    parser.add_argument('--verify-prec', type=int, default=200,
                        help='Precision for verification step (digits)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default='INFO', help='Logging verbosity')
    parser.add_argument('--parallel', action='store_true',
                        help='Run parallel Commander-Worker engine across all CPU cores')
    parser.add_argument('--workers', type=int, default=None,
                        help='Number of parallel workers (default: cpu_count - 1, requires --parallel)')
    args = parser.parse_args()

    # Handle aliases
    if args.num and not args.cycles:
        args.cycles = args.num
    if args.validation_level == 'none':
        args.no_verify = True
    elif args.validation_level == 'fast':
        args.verify_prec = 50

    # Apply style presets
    if args.style == 'apery':
        args.deg_alpha = max(args.deg_alpha, 3)
    elif args.style == 'apery4':
        args.deg_alpha = max(args.deg_alpha, 4)
        args.deg_beta = max(args.deg_beta, 3)
        args.coeff_range = max(args.coeff_range, 6)
    elif args.style == 'wild':
        args.coeff_range = max(args.coeff_range, 8)

    setup_logging(args.log_level)

    if args.query:
        logger.info("Research context: %s", args.query[:100])

    mp.dps = args.precision + 20
    rng = random.Random(args.seed)
    constants = build_constants(args.precision)

    # Deep Space: merge composite targets from near-miss analysis
    try:
        from deep_space import merge_composite_into_constants
        constants = merge_composite_into_constants(constants, max_composite=15)
    except ImportError:
        pass
    except Exception:
        pass  # non-critical: proceed with base constants

    # Dispatch by mode
    if args.report:
        print_leaderboard()
        print_family_report()
        return

    # Fresh start: clear log and state
    if args.fresh:
        LOGFILE.unlink(missing_ok=True)
        STATEFILE.unlink(missing_ok=True)
        print("  Cleared discovery log and state file.")

    # Parallel mode: dispatch to Commander-Worker engine
    if getattr(args, 'parallel', False):
        try:
            from parallel_engine import CommanderPool
            pool = CommanderPool(
                workers=args.workers,
                precision=args.precision,
                depth=args.depth,
                tol_digits=args.tol,
                pop_size=args.pop,
                verify=not args.no_verify,
                verify_prec=args.verify_prec,
            )
            pool.run(cycles=args.cycles or 100, seed=args.seed)
            return
        except ImportError:
            print("ERROR: parallel_engine.py not found. Falling back to single-process mode.")
        except Exception as e:
            print(f"Parallel engine failed: {e}. Falling back to single-process mode.")

    if args.mode == 'dr':
        return run_dr_mode(args, constants)
    if args.mode == 'cmf':
        return run_cmf_mode(args, constants)

    print(f"\nRamanujan Breakthrough Generator v2")
    print(f"  Precision: {args.precision} dps  |  Depth: {args.depth}  |  Pop: {args.pop}")
    print(f"  Tolerance: {args.tol} digits  |  Constants: {len(constants)}")
    print(f"  Verify: {'OFF' if args.no_verify else f'{args.verify_prec}d'}  |  Log: {LOGFILE}")
    print()

    # Initialize or resume
    start_cycle = 1
    temperature = args.init_temp
    discoveries = []
    recent_scores = []
    seen_hits = set()
    last_discovery_cycle = 0

    # Pre-seed trivial known CFs so they never count as "discoveries"
    _trivial_known = [
        ((1,), (1, 0)),           # phi = [1;1,1,1,...] golden ratio
        ((1,), (1,)),             # phi alternate
        ((0, 1, -2), (1, 3)),    # 4/pi Brouncker-family seed
        ((-1, 0, 4), (2, 0)),    # 4/pi Brouncker CF
    ]
    for tk in _trivial_known:
        seen_hits.add(tk)

    if args.resume and (state := load_state()):
        start_cycle = state['cycle'] + 1
        temperature = state['temperature']
        discoveries = [None] * state['discoveries']
        last_discovery_cycle = state.get('last_discovery_cycle', 0)
        # Rebuild seen_hits from discovery log to prevent re-logging
        seen_hits = load_seen_hits_from_log()
        print(f"Resuming from cycle {start_cycle}, T={temperature:.2f}, "
              f"{len(discoveries)} prior discoveries, "
              f"{len(seen_hits)} known CFs loaded\n")
        population = [PCFParams(**p) for p in state['elite_population']]
        # Detect elite monoculture and inject diversity on resume
        unique_structs = set((tuple(p.a), tuple(p.b)) for p in population)
        stale_cycles = start_cycle - 1 - last_discovery_cycle
        if len(unique_structs) <= 2 or stale_cycles > 60:
            print(f"  Elite monoculture detected ({len(unique_structs)} unique in "
                  f"{len(population)}). Injecting seed diversity.")
            seeds = seed_population()
            population = population[:2] + seeds
            # Force sustained reheat if resuming into a stale run
            if stale_cycles > 80:
                global _reheat_sustain_until, _last_reheat_tier
                _reheat_sustain_until = start_cycle + 20
                # Set tier tracker so we don't repeat T1, go straight to next tier
                if stale_cycles > 200:
                    _last_reheat_tier = 2  # next trigger will go T3
                elif stale_cycles > 120:
                    _last_reheat_tier = 1  # next trigger will go T2
                temperature = max(temperature, 2.0)
                print(f"  Forcing sustained reheat: T={temperature:.2f}, "
                      f"sustain until cycle {_reheat_sustain_until}, "
                      f"tier={_last_reheat_tier}")
        # Pad with diverse methods
        while len(population) < args.pop:
            if rng.random() < 0.5:
                population.append(random_fertile_params(rng))
            else:
                population.append(mutate(rng.choice(population), temperature, rng))
    else:
        population = seed_population()
        while len(population) < args.pop:
            population.append(random_params(rng=rng))

    max_cycles = args.cycles if args.cycles > 0 else float('inf')
    cycle = start_cycle

    # Adaptive scaling state
    _adaptive_scan_every = args.scan_every
    _adaptive_precision = args.precision
    _adaptive_depth = args.depth

    try:
        while cycle <= max_cycles:
            t0 = time.time()
            print(f"Cycle {cycle:4d} | T={temperature:.2f} | ", end='', flush=True)

            # ── hot-start injection every 100 cycles ─────────────────────────
            if cycle % 100 == 0 and cycle > start_cycle:
                try:
                    from adaptive_discovery import get_hot_start_population
                    hs_params = get_hot_start_population(pop_size=5, rng=rng)
                    if hs_params:
                        for hp in hs_params:
                            population.append(PCFParams(a=hp['a'], b=hp['b']))
                        print(f"hot-start +{len(hs_params)} | ", end='', flush=True)
                except Exception:
                    pass

            # ── systematic scan every N cycles ──────────────────────────────
            if cycle % _adaptive_scan_every == 0:
                # Widen grid scan during reheat for fresh territory
                scan_range = 3 if temperature > 1.3 else 2
                print(f"grid scan (r={scan_range})... ", end='', flush=True)
                hits, total = systematic_scan(
                    constants, min(args.depth, 200), args.tol,
                    coeff_range=scan_range, seen_hits=seen_hits
                )
                verified_hits = 0
                for p, name, res in hits:
                    scan_key = (tuple(p.a), tuple(p.b))
                    if scan_key in seen_hits:
                        continue
                    if is_telescoping(p.a, p.b):
                        seen_hits.add(scan_key)
                        continue
                    if is_spurious_match(name):
                        seen_hits.add(scan_key)
                        continue
                    # Verify grid scan hits at higher precision too
                    if not args.no_verify:
                        ok, vd = verify_match_high_precision(
                            p.a, p.b, name, constants,
                            verify_prec=args.verify_prec,
                            verify_depth=min(args.depth * 2, 1000),
                        )
                        if not ok:
                            seen_hits.add(scan_key)
                            continue
                    else:
                        vd = float(-mpm.log10(max(res, mpf(10)**(-mp.dps+5))))
                    cx = complexity_score(p.a, p.b)
                    verified_hits += 1
                    discoveries.append({'type': 'scan', 'match': name})
                    last_discovery_cycle = cycle
                    seen_hits.add(scan_key)
                    log_discovery({
                        'cycle': cycle, 'type': 'scan',
                        'a': p.a, 'b': p.b,
                        'value': nstr(eval_pcf(p.a, p.b, depth=args.depth), 20),
                        'match': name,
                        'residual': float(mpm.log10(max(res, mpf(10)**(-mp.dps+5)))),
                        'verified_digits': round(vd, 1),
                        'complexity': round(cx, 2),
                        'timestamp': datetime.now().isoformat(),
                    })
                print(f"scanned {total}, {verified_hits} verified | ", end='', flush=True)

            # ── evaluate current population ──────────────────────────────────
            prev_seen_count = len(seen_hits)
            population = evaluate_population(
                population, constants, args.depth, args.tol, seen_hits,
                verify=not args.no_verify,
                verify_prec=args.verify_prec,
            )

            # Track new discoveries (count newly added to seen_hits)
            new_discoveries = len(seen_hits) - prev_seen_count
            if new_discoveries > 0:
                last_discovery_cycle = cycle

            top_score = population[0].score if population else 0
            hit_count = sum(1 for p in population if p.hit)
            recent_scores.append(top_score)

            elapsed = time.time() - t0
            stale = cycle - last_discovery_cycle
            print(f"top={top_score:.1f}d | hits={hit_count} | stale={stale} | {elapsed:.1f}s")

            # ── Phase 2: structural diversity report every 10 cycles ─────────
            if cycle % 10 == 0:
                structural_report(population, min(20, len(population)))

            # ── adapt temperature ────────────────────────────────────────────
            temperature = adapt_temperature(
                temperature, recent_scores, cycle, last_discovery_cycle
            )

            # ── evolve ──────────────────────────────────────────────────────
            population = evolve_population(population, args.pop, temperature, rng)

            # ── save state every 5 cycles ────────────────────────────────────
            if cycle % 5 == 0:
                save_state(cycle, population, discoveries, temperature,
                          recent_scores, last_discovery_cycle)
                print(f"         State saved. Total discoveries: {len(discoveries)}")

            # ── adaptive scaling every 25 cycles ─────────────────────────────
            if cycle % 25 == 0:
                try:
                    from adaptive_discovery import compute_scaling, record_cycle_timing
                    record_cycle_timing(time.time() - t0)
                    decision = compute_scaling(
                        current_scan_every=_adaptive_scan_every,
                        current_precision=_adaptive_precision,
                        current_depth=_adaptive_depth,
                        cycle=cycle,
                        last_discovery_cycle=last_discovery_cycle,
                    )
                    if decision.reason != "no adjustment needed":
                        _adaptive_scan_every = decision.scan_every
                        _adaptive_depth = decision.depth
                        if decision.precision != _adaptive_precision:
                            _adaptive_precision = decision.precision
                            mp.dps = _adaptive_precision + 20
                        print(f"         Scaling: {decision.reason}")
                except Exception:
                    pass

            # ── Deep Space periodic update (composite targets + manifold) ────
            try:
                from deep_space import periodic_deep_space_update
                periodic_deep_space_update(cycle, update_every=200)
            except ImportError:
                pass
            except Exception:
                pass  # never block the search loop

            # ── GitHub sync (non-blocking background thread) ──────────────────
            try:
                from github_research_sync import maybe_sync
                maybe_sync(cycle, sync_every=_adaptive_scan_every)
            except ImportError:
                pass
            except Exception:
                pass  # never block the search loop

            # ── periodic leaderboard every 50 cycles ─────────────────────────
            if cycle % 50 == 0:
                board = print_leaderboard()
                if board:
                    for entry in board:
                        leaderboard_watch(entry)

            # ── periodic family report every 500 cycles ──────────────────────
            if cycle % 500 == 0:
                print_family_report()

            cycle += 1

    except KeyboardInterrupt:
        print("\nInterrupted. Saving state...")
        save_state(cycle - 1, population, discoveries, temperature,
                  recent_scores, last_discovery_cycle)

    # Final report
    print_leaderboard()
    print_family_report()
    print(f"\nDone. {len(discoveries)} discoveries logged to {LOGFILE}")


if __name__ == '__main__':
    main()
