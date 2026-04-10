"""
Targeted probe of the a=[0, k, -2], b=[1, 3] family.

Tests:
  - k=15 (odd gap, predicted S^(7))
  - Even k = 2, 4, 6, 8, 10, 12, 14 (completely unexplored)
  - Extended odd k = 17, 19 (check if family extends beyond k=15)
  
Also tests new b-vectors: b=[1,5], b=[1,7], b=[2,3], b=[1,3,0]
with a=[0, k, -2] to see if alternative b-families exist.

Then runs PSLQ against the full 59-constant library + Catalan.
"""
from __future__ import annotations
import sys, json, time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from mpmath import mp, mpf, pi, log, sqrt, zeta, euler, nstr
import mpmath as mpm

PREC = 500          # decimal digits for evaluation
DEPTH = 2000        # CF depth for convergence
VERIFY_DEPTH = 4000 # second depth for convergence check
TOL = 15            # PSLQ tolerance digits

LOGFILE = Path(__file__).parent / "ramanujan_discoveries.jsonl"


def eval_pcf(a_coeffs, b_coeffs, depth=2000):
    """Evaluate GCF with polynomial a(n), b(n)."""
    def a(n):
        return sum(mpf(c) * n**i for i, c in enumerate(a_coeffs))
    def b(n):
        return sum(mpf(c) * n**i for i, c in enumerate(b_coeffs))
    
    val = mpf(0)
    for n in range(depth, 0, -1):
        bn = b(n)
        an = a(n)
        denom = bn + val
        if abs(denom) < mpf(10)**(-mp.dps + 5):
            return None
        val = an / denom
    return b(0) + val


def build_extended_constants():
    """Build constant library at high precision, including S^(m) up to m=10."""
    mp.dps = PREC + 50
    pi_val = pi
    e_val = mpm.e
    log2 = log(2)
    log3 = log(3)
    sqrt2 = sqrt(mpf(2))
    sqrt3 = sqrt(mpf(3))
    sqrt5 = sqrt(mpf(5))
    phi = (1 + sqrt5) / 2
    
    consts = {
        '4/pi':      mpf(4) / pi_val,
        '2/pi':      mpf(2) / pi_val,
        'pi/4':      pi_val / 4,
        'pi/2':      pi_val / 2,
        'pi':        pi_val,
        'pi^2/6':    pi_val**2 / 6,
        'pi^2/8':    pi_val**2 / 8,
        'pi^2/12':   pi_val**2 / 12,
        'pi^3/32':   pi_val**3 / 32,
        'pi^4/90':   pi_val**4 / 90,
        '6/pi^2':    mpf(6) / pi_val**2,
        'sqrt_pi':   sqrt(pi_val),
        'log2':      log2,
        'log3':      log3,
        'sqrt2':     sqrt2,
        'sqrt3':     sqrt3,
        'sqrt5':     sqrt5,
        'phi':       phi,
        'sqrt2+1':   sqrt2 + 1,
        'sqrt3+1':   sqrt3 + 1,
        'e':         e_val,
        'euler_g':   euler,
        'zeta3':     zeta(3),
        'zeta5':     zeta(5),
        'catalan':   mpm.catalan,
    }
    
    # S^(m) for m=2..10 via the known CF: a=[0, 2m+1, -2], b=[1, 3]
    for m in range(2, 11):
        k = 2 * m + 1
        val = eval_pcf([0, k, -2], [1, 3], depth=3000)
        if val is not None:
            consts[f'S^({m})'] = val
    
    return consts


def match_against_library(val, constants, label=""):
    """Try to match val against integer-linear combos of constants.
    
    Tests:
      1. Direct ratio val/const for small integer ratios
      2. PSLQ with subsets of constants
    """
    results = []
    
    # 1. Direct ratio check: val = (p/q) * const
    for cname, cval in constants.items():
        if cval == 0:
            continue
        ratio = val / cval
        # Check if ratio is a simple fraction p/q with |p|,|q| <= 20
        for q in range(1, 21):
            p_approx = ratio * q
            p_round = int(round(float(p_approx)))
            if p_round == 0:
                continue
            residual = abs(val - mpf(p_round) / q * cval)
            if residual == 0:
                digits = PREC
            elif residual < mpf(10)**(-TOL):
                digits = float(-mpm.log10(residual))
            else:
                continue
            results.append((digits, f"{p_round}/{q}*{cname}", residual))
    
    # 2. PSLQ against top candidates
    for cname, cval in constants.items():
        try:
            mp.dps = PREC + 20
            vec = [val, cval, mpf(1)]
            rel = mpm.pslq(vec, maxcoeff=100, tol=mpf(10)**(-TOL + 2))
            if rel and rel[0] != 0:
                residual = abs(sum(r * v for r, v in zip(rel, vec)))
                if residual < mpf(10)**(-TOL):
                    digits = float(-mpm.log10(residual)) if residual > 0 else PREC
                    expr = f"{rel[0]}*x + {rel[1]}*{cname} + {rel[2]} = 0"
                    results.append((digits, expr, residual))
        except Exception:
            pass
    
    results.sort(key=lambda x: -x[0])
    return results


def log_discovery(a, b, match, verified_digits, value):
    """Append to the JSONL log."""
    record = {
        'a': a, 'b': b,
        'value': nstr(value, 30),
        'match': match,
        'verified_digits': round(verified_digits, 1),
        'complexity': round(sum(abs(c) for c in a) + sum(abs(c) for c in b), 2),
        'timestamp': datetime.now().isoformat(),
        'type': 'targeted_probe',
        'shard': 'family-gap',
    }
    with open(LOGFILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=True) + '\n')
    return record


def probe_cf(a, b, constants, label=""):
    """Evaluate a single CF and try to identify it."""
    mp.dps = PREC + 50
    
    val1 = eval_pcf(a, b, depth=DEPTH)
    if val1 is None:
        print(f"  {label:30s}  a={str(a):20s} b={str(b):10s}  DIVERGES")
        return None
    
    val2 = eval_pcf(a, b, depth=VERIFY_DEPTH)
    if val2 is None:
        print(f"  {label:30s}  a={str(a):20s} b={str(b):10s}  DIVERGES at depth {VERIFY_DEPTH}")
        return None
    
    agreement = abs(val1 - val2)
    if agreement == 0:
        conv_digits = PREC
    else:
        conv_digits = float(-mpm.log10(agreement))
    
    if conv_digits < 20:
        print(f"  {label:30s}  a={str(a):20s} b={str(b):10s}  "
              f"POOR CONVERGENCE ({conv_digits:.1f}d)")
        return None
    
    # Try matching
    matches = match_against_library(val1, constants, label)
    
    if matches:
        best_digits, best_expr, best_res = matches[0]
        print(f"  {label:30s}  a={str(a):20s} b={str(b):10s}  "
              f"= {best_expr:30s}  ({best_digits:.1f}d, conv={conv_digits:.0f}d)")
        
        if best_digits > 30:
            log_discovery(a, b, best_expr, best_digits, val1)
            return {'match': best_expr, 'digits': best_digits, 'value': val1}
    else:
        # Show numeric value for unmatched CFs
        print(f"  {label:30s}  a={str(a):20s} b={str(b):10s}  "
              f"= {nstr(val1, 25):30s}  NO MATCH (conv={conv_digits:.0f}d)")
    
    return None


def main():
    print("=" * 80)
    print("  TARGETED FAMILY PROBE: a=[0, k, -2], b=[1, 3]")
    print("=" * 80)
    
    t0 = time.time()
    mp.dps = PREC + 50
    
    print("\n  Building extended constant library at %dd..." % PREC)
    constants = build_extended_constants()
    print(f"  {len(constants)} constants loaded ({time.time()-t0:.1f}s)\n")
    
    # ── Section 1: Odd k gap (k=15) and extensions ─────────────────────
    print("-" * 80)
    print("  SECTION 1: Odd k values (known + gap + extensions)")
    print("-" * 80)
    
    # Verify known k values first (sanity check)
    for k in [3, 5, 7, 9, 11, 13]:
        probe_cf([0, k, -2], [1, 3], constants, label=f"k={k} (known)")
    
    # The gap: k=15
    print()
    print("  >>> TESTING k=15 (the gap - predicted S^(7)?) <<<")
    probe_cf([0, 15, -2], [1, 3], constants, label="k=15 (GAP)")
    
    # Extensions: k=17, 19, 21
    print()
    for k in [17, 19, 21]:
        probe_cf([0, k, -2], [1, 3], constants, label=f"k={k} (extension)")
    
    # ── Section 2: Even k values ────────────────────────────────────────
    print()
    print("-" * 80)
    print("  SECTION 2: Even k values (completely unexplored)")
    print("-" * 80)
    
    for k in [2, 4, 6, 8, 10, 12, 14, 16]:
        probe_cf([0, k, -2], [1, 3], constants, label=f"k={k} (even)")
    
    # ── Section 3: New b-vectors ────────────────────────────────────────
    print()
    print("-" * 80)
    print("  SECTION 3: Alternative b-vectors with a=[0, k, -2]")
    print("-" * 80)
    
    test_b_vectors = [
        [1, 5],     # b(n) = 5n + 1
        [1, 7],     # b(n) = 7n + 1
        [2, 3],     # b(n) = 3n + 2
        [1, 3, 0],  # b(n) = 3n + 1 (degree-2, should match b=[1,3])
        [0, 1, 1],  # b(n) = n^2 + n = n(n+1)
        [1, 1, 1],  # b(n) = n^2 + n + 1
        [1, 2],     # b(n) = 2n + 1 (odd numbers)
        [1, 4],     # b(n) = 4n + 1
        [2, 5],     # b(n) = 5n + 2
        [3, 1],     # b(n) = n + 3
    ]
    
    for b in test_b_vectors:
        print(f"\n  --- b={b} ---")
        for k in [1, 3, 5, 7]:
            probe_cf([0, k, -2], b, constants, label=f"k={k}, b={b}")
    
    # ── Section 4: Catalan-targeted sweep ───────────────────────────────
    print()
    print("-" * 80)
    print("  SECTION 4: Catalan's constant sweep")
    print("-" * 80)
    
    catalan_val = mpm.catalan
    print(f"  Catalan G = {nstr(catalan_val, 30)}")
    print()
    
    # Try various a-shapes with b=[1,5] and b=[2,3] (non-saturated b)
    for b in [[1, 5], [2, 3], [1, 7], [1, 4]]:
        print(f"\n  --- b={b}, varying a ---")
        for a0 in range(-2, 3):
            for a1 in range(-5, 8):
                for a2 in [-3, -2, -1, 0, 1, 2]:
                    a = [a0, a1, a2] if a2 != 0 else [a0, a1]
                    if all(c == 0 for c in a):
                        continue
                    val = eval_pcf(a, b, depth=800)
                    if val is None:
                        continue
                    
                    # Quick check against Catalan
                    for p in range(1, 13):
                        for q in range(1, 13):
                            test = abs(val - mpf(p) / q * catalan_val)
                            if test > 0 and float(-mpm.log10(test)) > TOL:
                                digits = float(-mpm.log10(test))
                                print(f"    *** CATALAN HIT: a={a} b={b} "
                                      f"= {p}/{q}*G  ({digits:.1f}d)")
                                log_discovery(a, b, f"{p}/{q}*catalan",
                                              digits, val)
    
    elapsed = time.time() - t0
    print()
    print("=" * 80)
    print(f"  PROBE COMPLETE  ({elapsed:.1f}s)")
    print("=" * 80)


if __name__ == "__main__":
    main()
