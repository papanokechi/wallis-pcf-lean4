"""
_test_schema.py — Test suite for the GCF Irrationality Schema
==============================================================
Validates verify_gcf_irrationality() against all conditions (C1)-(C4)
from Theorem [thm:master] in gcf_irrationality_schema.tex.

Tests cover:
  - Unit-numerator quadratic GCFs (the 482 catalogue)
  - d_a = 0,1,2,3 degree boundary cases
  - C1 positivity failures
  - C2 root failures
  - C4 leading-coefficient threshold
  - Borderline |α_2| = β_2 cases
  - Full catalogue sweep
"""
import sys, time
sys.set_int_max_str_digits(100000)

from irrationality_toolkit import (
    verify_gcf_irrationality, verify_unit_numerator,
    generate_standard_catalogue
)

PASS = 0
FAIL = 0

def check(name, result, expected_irrational, expected_conditions=None):
    """Assert schema result matches expectations."""
    global PASS, FAIL
    ok = result["irrational"] == expected_irrational
    if expected_conditions:
        for cond, val in expected_conditions.items():
            if result[cond] != val:
                ok = False
    if ok:
        PASS += 1
        status = "PASS"
    else:
        FAIL += 1
        status = "FAIL"
    tag = "irrational" if result["irrational"] else "inconclusive"
    print(f"  [{status}] {name}: {tag}", end="")
    if not ok:
        print(f"  (expected {'irrational' if expected_irrational else 'inconclusive'})", end="")
        if expected_conditions:
            for c, v in expected_conditions.items():
                if result[c] != v:
                    print(f"  {c}={result[c]} expected {v}", end="")
    print()


# ═══════════════════════════════════════════════════════════════════════
# §1  Unit-numerator cases (d_a = 0, a_n = 1)
# ═══════════════════════════════════════════════════════════════════════
print("\n§1  Unit-numerator quadratic GCFs (d_a=0)")
print("─" * 50)

r = verify_unit_numerator(3, 1, 1)
check("V(3,1,1) flagship", r, True, {"C1": True, "C2": True, "C3": True, "C4": True})

r = verify_unit_numerator(1, 1, 1)
check("V(1,1,1) minimal", r, True)

r = verify_unit_numerator(5, 5, 5)
check("V(5,5,5) large coeffs", r, True)

r = verify_unit_numerator(1, 0, 1)
check("V(1,0,1) zero B", r, True)

r = verify_unit_numerator(1, -1, 1)
check("V(1,-1,1) negative B, pos-def", r, True)


# ═══════════════════════════════════════════════════════════════════════
# §2  C1 positivity failures
# ═══════════════════════════════════════════════════════════════════════
print("\n§2  C1 positivity failures")
print("─" * 50)

r = verify_unit_numerator(1, -3, 1)
check("V(1,-3,1) b(1)=-1", r, False, {"C1": False})

r = verify_unit_numerator(1, -5, 2)
check("V(1,-5,2) deep neg", r, False, {"C1": False})

# β_2 = 0: linear denominator (not quadratic schema)
r = verify_gcf_irrationality([1], [1, 3, 0])
check("b_n=3n+1 (linear, β_2=0)", r, False, {"C1": False})


# ═══════════════════════════════════════════════════════════════════════
# §3  d_a = 1 cases
# ═══════════════════════════════════════════════════════════════════════
print("\n§3  d_a=1 cases (a_n = linear)")
print("─" * 50)

# a_n = n, b_n = n^2+1
r = verify_gcf_irrationality([0, 1], [1, 0, 1])
check("a_n=n, b_n=n^2+1", r, True, {"C4": True})

# a_n = 2n+1, b_n = n^2+n+1
r = verify_gcf_irrationality([1, 2], [1, 1, 1])
check("a_n=2n+1, b_n=n^2+n+1", r, True, {"C4": True})

# a_n = n has root at n=0 but not at n≥1, so C2 should pass
r = verify_gcf_irrationality([0, 1], [1, 1, 1])
check("a_n=n (no root at n≥1, a(0)=0 OK)", r, True, {"C2": True})


# ═══════════════════════════════════════════════════════════════════════
# §4  d_a = 2 cases — C4 conditional on leading coefficient
# ═══════════════════════════════════════════════════════════════════════
print("\n§4  d_a=2 cases (C4 depends on |α_2| vs β_2)")
print("─" * 50)

# a_n = n^2, b_n = 2n^2+1  → |α_2|/β_2 = 1/2 < 1: PASS
r = verify_gcf_irrationality([0, 0, 1], [1, 0, 2])
check("a_n=n^2, b_n=2n^2+1, ratio=0.5", r, True, {"C4": True})

# a_n = 3n^2, b_n = 2n^2+1  → |α_2|/β_2 = 3/2 > 1: FAIL C4
r = verify_gcf_irrationality([0, 0, 3], [1, 0, 2])
check("a_n=3n^2, b_n=2n^2+1, ratio=1.5", r, False, {"C4": False, "C1": True})

# a_n = -n^2+n, b_n = 2n^2+1  → |α_2|/β_2 = 1/2 < 1: PASS
# but a(1) = -1+1 = 0 → C2 fails!
r = verify_gcf_irrationality([0, 1, -1], [1, 0, 2])
check("a_n=-n^2+n (root at n=1)", r, False, {"C2": False})

# a_n = 2n^2+n+1, b_n = 2n^2+1  → |α_2|/β_2 = 1 exactly: borderline
# drift = α_1/α_2 - β_1/β_2 = (1/2) - (0/2) = 0.5 > 0 → product DIVERGES
r = verify_gcf_irrationality([1, 1, 2], [1, 0, 2])
check("a_n=2n^2+n+1, b_n=2n^2+1, ratio=1.0 (drift>0)", r, False, {"C4": False})

# a_n = 2n^2-n+1, b_n = 2n^2+n+1  → |α_2|/β_2 = 1, subleading: α_1/α_2=-1/2, β_1/β_2=1/2
# drift = -1/2 - 1/2 = -1 < 0 → product vanishes
r = verify_gcf_irrationality([1, -1, 2], [1, 1, 2])
check("a_n=2n^2-n+1, b_n=2n^2+n+1, borderline drift=-1", r, True, {"C4": True})


# ═══════════════════════════════════════════════════════════════════════
# §5  d_a = 3 — must FAIL C4
# ═══════════════════════════════════════════════════════════════════════
print("\n§5  d_a=3 (must fail C4)")
print("─" * 50)

r = verify_gcf_irrationality([0, 0, 0, 1], [1, 1, 1])
check("a_n=n^3, b_n=n^2+n+1", r, False, {"C4": False, "C1": True})

r = verify_gcf_irrationality([1, 0, 0, -1], [1, 0, 1])
check("a_n=-n^3+1, b_n=n^2+1", r, False, {"C4": False})

# Pi family: a_n = -2n^2+n, b_n = 3n+1 (linear, so β_2=0 → C1 fails too)
r = verify_gcf_irrationality([0, 1, -2], [1, 3, 0])
check("Pi family a=-2n^2+n, b=3n+1 (linear b)", r, False, {"C1": False})


# ═══════════════════════════════════════════════════════════════════════
# §6  C3 integrality edge cases
# ═══════════════════════════════════════════════════════════════════════
print("\n§6  C3 integrality edge cases")
print("─" * 50)

# Half-integer coefficients: b_n = (1/2)n^2+n+1 → b(0)=1, b(1)=2.5 — NOT int
r = verify_gcf_irrationality([1], [1, 1, 0.5])
check("b_n=0.5n^2+n+1 (non-integer at n=1)", r, False, {"C3": False})

# Integer-valued despite non-integer coeffs: b_n = n(n+1)/2 + 1 = 0.5n^2+0.5n+1
# b(0)=1, b(1)=2, b(2)=4 — all integer!
r = verify_gcf_irrationality([1], [1, 0.5, 0.5])
check("b_n=0.5n^2+0.5n+1 (int-valued)", r, True, {"C3": True})


# ═══════════════════════════════════════════════════════════════════════
# §7  deg(a) = deg(b) case with ratio → 0
# ═══════════════════════════════════════════════════════════════════════
print("\n§7  deg(a_n) = deg(b_n) = 2, ratio from leading coefficients")
print("─" * 50)

# a_n = n^2+1, b_n = 3n^2+1 → |α_2|/β_2 = 1/3 < 1
r = verify_gcf_irrationality([1, 0, 1], [1, 0, 3])
check("a=n^2+1, b=3n^2+1, ratio=1/3", r, True, {"C4": True})

# a_n = 2n^2+1, b_n = 3n^2+1 → |α_2|/β_2 = 2/3 < 1
r = verify_gcf_irrationality([1, 0, 2], [1, 0, 3])
check("a=2n^2+1, b=3n^2+1, ratio=2/3", r, True, {"C4": True})


# ═══════════════════════════════════════════════════════════════════════
# §8  Full catalogue sweep
# ═══════════════════════════════════════════════════════════════════════
print("\n§8  Full catalogue sweep (A_max=5, B∈[-5,5], C_max=5)")
print("─" * 50)

t0 = time.time()
catalogue = generate_standard_catalogue(prec=40)
n_pass = 0
n_fail = 0
for entry in catalogue:
    A, B, C = entry["A"], entry["B"], entry["C"]
    r = verify_unit_numerator(A, B, C)
    if r["irrational"]:
        n_pass += 1
    else:
        n_fail += 1
        print(f"    UNEXPECTED FAIL: V({A},{B},{C})")
dt = time.time() - t0

if n_fail == 0:
    PASS += 1
    print(f"  [PASS] All {n_pass}/{len(catalogue)} catalogue entries verified ({dt:.1f}s)")
else:
    FAIL += 1
    print(f"  [FAIL] {n_fail}/{len(catalogue)} catalogue entries failed ({dt:.1f}s)")


# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "═" * 50)
print(f"  TOTAL: {PASS + FAIL} tests | {PASS} passed | {FAIL} failed")
print("═" * 50)

if FAIL > 0:
    sys.exit(1)
