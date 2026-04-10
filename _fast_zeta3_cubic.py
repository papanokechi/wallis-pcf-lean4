"""
Ultra-fast cubic/cubic ζ(3) PCF search using float64 screening.

Strategy:
  Pass 1: float64 evaluation (fast, ~100K/s) → screen for 8-digit near-misses
  Pass 2: mpmath 200dp verification of candidates only
  
This makes the 19M combination space tractable.
"""

import itertools
import json
import math
import time
from datetime import datetime

# ── float64 targets ──────────────────────────────────────────────────────────
ZETA3 = 1.2020569031595942853997381

TARGETS = {}
for num in range(1, 9):
    for den in range(1, 9):
        val = ZETA3 * num / den
        label = f"{num}*z3/{den}" if den > 1 else (f"{num}*z3" if num > 1 else "z3")
        if num == den:
            label = "z3"
            val = ZETA3
        TARGETS[label] = val
# Deduplicate by value (keep first label)
seen_vals = {}
deduped = {}
for label, val in TARGETS.items():
    key = round(val, 12)
    if key not in seen_vals:
        seen_vals[key] = label
        deduped[label] = val
TARGETS = deduped
# Add reciprocals and pi-related
TARGETS["1/z3"] = 1.0 / ZETA3
TARGETS["2/z3"] = 2.0 / ZETA3
TARGETS["z3/pi"] = ZETA3 / math.pi
TARGETS["z3*pi"] = ZETA3 * math.pi
TARGETS["z3/pi2"] = ZETA3 / (math.pi**2)

TARGET_VALS = list(TARGETS.values())
TARGET_LABELS = list(TARGETS.keys())
N_TARGETS = len(TARGET_VALS)


def eval_pcf_float(a_coeffs, b_coeffs, depth=60):
    """Evaluate PCF using float64. Returns value or None if divergent."""
    a0, a1, a2, a3 = a_coeffs
    b0, b1, b2, b3 = b_coeffs
    
    # P_{-1}=1, P_0=b(0)=b0, Q_{-1}=0, Q_0=1
    Pp2, Pp1 = 1.0, float(b0)
    Qp2, Qp1 = 0.0, 1.0
    
    for n in range(1, depth + 1):
        an = a0 + n * (a1 + n * (a2 + n * a3))
        bn = b0 + n * (b1 + n * (b2 + n * b3))
        
        Pn = bn * Pp1 + an * Pp2
        Qn = bn * Qp1 + an * Qp2
        
        # Overflow control
        ap = abs(Pn)
        aq = abs(Qn)
        if ap > 1e150 or aq > 1e150:
            if aq < 1e-300:
                return None
            scale = max(ap, aq)
            Pn /= scale
            Qn /= scale
            Pp1 /= scale
            Qp1 /= scale
        
        Pp2, Pp1 = Pp1, Pn
        Qp2, Qp1 = Qp1, Qn
    
    if abs(Qp1) < 1e-300:
        return None
    return Pp1 / Qp1


def screen_match(val, tol=1e-8):
    """Check val against targets. Returns (label, digits) or None."""
    if val is None or math.isnan(val) or math.isinf(val):
        return None
    if abs(val) > 1e6 or abs(val) < 1e-6:
        return None
    
    best_label = None
    best_digits = 0
    
    for i in range(N_TARGETS):
        tval = TARGET_VALS[i]
        diff = abs(val - tval)
        if diff < tol * max(abs(tval), 1.0):
            if diff == 0:
                return (TARGET_LABELS[i], 15.0)
            digits = -math.log10(diff / max(abs(tval), 1.0))
            if digits > best_digits:
                best_digits = digits
                best_label = TARGET_LABELS[i]
    
    if best_label and best_digits >= 8:
        return (best_label, best_digits)
    return None


def verify_mpmath(a_coeffs, b_coeffs, depth=500, dps=200):
    """High-precision verification using mpmath."""
    from mpmath import mp, mpf, nstr, fabs, log10, zeta, pi
    
    mp.dps = dps + 10
    z3 = zeta(3)
    
    # Build high-prec targets
    hp_targets = {}
    for num in range(1, 9):
        for den in range(1, 9):
            val = z3 * num / den
            label = f"{num}*z3/{den}" if den > 1 else (f"{num}*z3" if num > 1 else "z3")
            if num == den:
                label = "z3"
                val = z3
            hp_targets[label] = val
    hp_targets["1/z3"] = 1/z3
    hp_targets["2/z3"] = 2/z3
    hp_targets["z3/pi"] = z3/pi
    hp_targets["z3*pi"] = z3*pi
    hp_targets["z3/pi2"] = z3/pi**2
    
    # Evaluate CF
    def poly_eval(coeffs, n):
        result = mpf(0)
        nk = mpf(1)
        for c in coeffs:
            result += c * nk
            nk *= n
        return result
    
    b0 = poly_eval(b_coeffs, 0)
    Pp2, Pp1 = mpf(1), b0
    Qp2, Qp1 = mpf(0), mpf(1)
    
    for n in range(1, depth + 1):
        an = poly_eval(a_coeffs, n)
        bn = poly_eval(b_coeffs, n)
        Pn = bn * Pp1 + an * Pp2
        Qn = bn * Qp1 + an * Qp2
        Pp2, Pp1 = Pp1, Pn
        Qp2, Qp1 = Qp1, Qn
    
    if Qp1 == 0:
        return None
    
    val = Pp1 / Qp1
    
    best = None
    for label, tval in hp_targets.items():
        diff = fabs(val - tval)
        if diff == 0:
            return (label, float(dps), nstr(val, 30))
        digits = float(-log10(diff / max(fabs(tval), mpf(1))))
        if digits >= 20 and (best is None or digits > best[1]):
            best = (label, digits, nstr(val, 30))
    
    return best


def main():
    COEFF_RANGE = 4
    DEG = 3  # cubic/cubic
    FLOAT_DEPTH = 60
    SCREEN_TOL = 1e-8  # ~8 digits
    
    print("=" * 70)
    print("  ULTRA-FAST CUBIC/CUBIC ζ(3) SEARCH (float64 screening)")
    print("=" * 70)
    
    a_range = list(range(-COEFF_RANGE, COEFF_RANGE + 1))
    b0_range = list(range(1, COEFF_RANGE + 1))
    b_range = list(range(-COEFF_RANGE, COEFF_RANGE + 1))
    
    n_a = len(a_range) ** (DEG + 1)
    n_b = len(b0_range) * len(b_range) ** DEG
    total = n_a * n_b
    
    print(f"  Coeff range: [-{COEFF_RANGE}, {COEFF_RANGE}]")
    print(f"  Total: {total:,} combinations")
    print(f"  Targets: {N_TARGETS}")
    print(f"  Float screen: {FLOAT_DEPTH} depth, 8+ digits")
    print(f"  Verify: mpmath 200dp, 500 depth, 20+ digits")
    print()
    
    hits = []
    candidates = 0
    evaluated = 0
    t0 = time.time()
    last_report = t0
    
    for a_tuple in itertools.product(a_range, repeat=DEG + 1):
        # Skip all-zero
        if all(c == 0 for c in a_tuple):
            continue
        # Skip a(1)=0
        if sum(a_tuple) == 0:
            continue
        
        a_list = list(a_tuple)
        
        for b0 in b0_range:
            for b_rest in itertools.product(b_range, repeat=DEG):
                b_list = [b0] + list(b_rest)
                
                val = eval_pcf_float(a_list, b_list, FLOAT_DEPTH)
                evaluated += 1
                
                result = screen_match(val, SCREEN_TOL)
                
                if result:
                    candidates += 1
                    label, digits = result
                    
                    # Verify at high precision
                    hp_result = verify_mpmath(a_list, b_list)
                    
                    if hp_result:
                        hp_label, hp_digits, hp_val = hp_result
                        print(f"\n  *** CONFIRMED: {hp_label} at {hp_digits:.1f} digits ***")
                        print(f"     a = {a_list}")
                        print(f"     b = {b_list}")
                        print(f"     val = {hp_val}")
                        hits.append({
                            'a': a_list, 'b': b_list,
                            'value': hp_val, 'match': hp_label,
                            'digits': hp_digits,
                            'timestamp': datetime.now().isoformat(),
                        })
                
                # Progress
                now = time.time()
                if now - last_report > 15:
                    elapsed = now - t0
                    rate = evaluated / elapsed
                    pct = 100.0 * evaluated / total
                    eta_s = (total - evaluated) / rate if rate > 0 else 0
                    eta_h = eta_s / 3600
                    print(f"  [{pct:5.1f}%] {evaluated:,}/{total:,} | "
                          f"{len(hits)} hits | {candidates} cands | "
                          f"{rate:.0f}/s | ETA {eta_h:.1f}h", flush=True)
                    last_report = now
    
    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"  DONE: {evaluated:,} evaluated in {elapsed:.0f}s ({evaluated/elapsed:.0f}/s)")
    print(f"  Candidates screened: {candidates}")
    print(f"  Confirmed hits: {len(hits)}")
    
    if hits:
        with open("results/zeta3_cubic_hits.json", "w") as f:
            json.dump(hits, f, indent=2)
        print(f"  Results: results/zeta3_cubic_hits.json")
    
    for h in hits:
        print(f"  → {h['match']} | a={h['a']} b={h['b']} | {h['digits']:.1f}d")
    
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
