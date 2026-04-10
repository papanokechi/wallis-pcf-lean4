#!/usr/bin/env python3
"""Task 1: Symbolic generalization of contiguous relations for Pi Family."""
from fractions import Fraction

# Compute families
families = {}
for m in range(5):
    p = [Fraction(1), Fraction(1)]
    q = [Fraction(0), Fraction(1)]
    for n in range(1, 25):
        a_n = Fraction(-n * (2 * n - 2 * m - 1))
        b_n = Fraction(3 * n + 1)
        p.append(b_n * p[-1] + a_n * p[-2])
        q.append(b_n * q[-1] + a_n * q[-2])
    families[m] = {"p": p, "q": q}


def solve_AB(pm, pm1, n):
    """Solve P_n^(m+1) = A*P_n^(m) + B*P_{n-1}^(m) using n and n+1."""
    a11, a12 = pm[n + 1], pm[n]
    a21, a22 = pm[n + 2], pm[n + 1]
    r1, r2 = pm1[n + 1], pm1[n + 2]
    det = a11 * a22 - a12 * a21
    if det == 0:
        return None, None
    A = (r1 * a22 - r2 * a12) / det
    B = (a11 * r2 - a21 * r1) / det
    return A, B


# ================================================================
# TASK 1a: Determine A(n), B(n) for each m transition
# ================================================================
print("=" * 70)
print("TASK 1a: Contiguous relation coefficients A(n), B(n)")
print("  P_n^(m+1) = A(n) P_n^(m) + B(n) P_{n-1}^(m)")
print("=" * 70)

for m in range(4):
    pm = families[m]["p"]
    pm1 = families[m + 1]["p"]
    print(f"\n--- Transition m={m} -> {m+1} ---")

    AB = []
    for k in range(1, 18):
        A, B = solve_AB(pm, pm1, k)
        if A is not None:
            AB.append((k, A, B))

    for k, A, B in AB[:10]:
        print(f"  n={k:2d}: A = {str(A):>15s}   B = {str(B):>15s}")

    # Check if A(n) * h_n^(m) is a nice polynomial
    # For m=0: h_n^(0) = 2n+1, A(n)=n+2, A*h = (n+2)(2n+1)
    # For m=1: h_n^(1) = n^2+3n+1
    if m == 1:
        print("\n  A(n) * h_n^(1) where h_n = n^2+3n+1:")
        for k, A, B in AB[:10]:
            h = Fraction(k * k + 3 * k + 1)
            prod = A * h
            print(f"    n={k}: A*h = {prod}")

    if m >= 1:
        # Check if A(n) = f(n) / g_n where g_n = q_n^(m) / q_{n-1}^(m)?
        # Actually try: is the DENOMINATOR of A(n) related to q_n / (2n-1)!! ?
        # Or is it the Casoratian W_n^(m) = h_n g_{n-1} - h_{n-1} g_n?
        pass

# ================================================================
# TASK 1b: THREE-TERM operator: use P^(m), P^(m-1) jointly
# ================================================================
print("\n" + "=" * 70)
print("TASK 1b: Three-term relation")
print("  P_n^(m+1) = A(n) P_n^(m) + B(n) P_n^(m-1)")
print("=" * 70)

for m in range(1, 4):
    pm_prev = families[m - 1]["p"]
    pm = families[m]["p"]
    pm_next = families[m + 1]["p"]
    print(f"\n--- {m-1},{m} -> {m+1} ---")

    AB3 = []
    for k in range(1, 15):
        # Solve: A * P_n^(m) + B * P_n^(m-1) = P_n^(m+1) at n=k and n=k+1
        a11, a12 = pm[k + 1], pm_prev[k + 1]
        a21, a22 = pm[k + 2], pm_prev[k + 2]
        r1, r2 = pm_next[k + 1], pm_next[k + 2]
        det = a11 * a22 - a12 * a21
        if det == 0:
            continue
        A = (r1 * a22 - r2 * a12) / det
        B = (a11 * r2 - a21 * r1) / det
        AB3.append((k, A, B))

    for k, A, B in AB3[:10]:
        print(f"  n={k:2d}: A = {str(A):>15s}   B = {str(B):>15s}")

    # Check polynomial/rational structure
    A_vals = [v[1] for v in AB3[:10]]
    B_vals = [v[2] for v in AB3[:10]]

    A_d1 = [A_vals[i + 1] - A_vals[i] for i in range(len(A_vals) - 1)]
    A_d2 = [A_d1[i + 1] - A_d1[i] for i in range(len(A_d1) - 1)]

    if all(d == A_d1[0] for d in A_d1[:6]):
        print(f"  A(n) is LINEAR: slope={A_d1[0]}")
    elif all(d == A_d2[0] for d in A_d2[:5]):
        print(f"  A(n) is QUADRATIC: 2nd-diff={A_d2[0]}")
    else:
        print(f"  A(n) diffs: {[float(d) for d in A_d1[:5]]}")
        print(f"  A(n) 2nd-diffs: {[float(d) for d in A_d2[:4]]}")

    B_d1 = [B_vals[i + 1] - B_vals[i] for i in range(len(B_vals) - 1)]
    B_d2 = [B_d1[i + 1] - B_d1[i] for i in range(len(B_d1) - 1)]

    if all(d == B_d1[0] for d in B_d1[:6]):
        print(f"  B(n) is LINEAR: slope={B_d1[0]}")
    elif all(d == B_d2[0] for d in B_d2[:5]):
        print(f"  B(n) is QUADRATIC: 2nd-diff={B_d2[0]}")
    else:
        print(f"  B(n) diffs: {[float(d) for d in B_d1[:5]]}")

# ================================================================
# TASK 1c: Master operator — three-term in m at FIXED n
# P_n^(m+1) = alpha(m) P_n^(m) + beta(m) P_n^(m-1)
# ================================================================
print("\n" + "=" * 70)
print("TASK 1c: m-recurrence at fixed n")
print("  P_n^(m+1) = alpha_n(m) P_n^(m) + beta_n(m) P_n^(m-1)")
print("=" * 70)

for n_fixed in [3, 5, 8, 12]:
    print(f"\n  n = {n_fixed}:")
    for m in range(1, 4):
        pmp1 = families[m + 1]["p"][n_fixed + 1]
        pm_val = families[m]["p"][n_fixed + 1]
        pmm1 = families[m - 1]["p"][n_fixed + 1]
        # Also need second equation at same n: use m-1,m -> m+1
        # A * pm + B * pmm1 = pmp1
        # At two different m? No, single equation.
        # Use n_fixed and n_fixed-1 for same m:
        pmp1_prev = families[m + 1]["p"][n_fixed]
        pm_val_prev = families[m]["p"][n_fixed]
        pmm1_prev = families[m - 1]["p"][n_fixed]

        det = pm_val * pmm1_prev - pmm1 * pm_val_prev
        if det != 0:
            A = (pmp1 * pmm1_prev - pmp1_prev * pmm1) / det
            B = (pm_val * pmp1_prev - pm_val_prev * pmp1) / det
            print(f"    m={m}: A={float(A):.10f}  B={float(B):.10f}")

# ================================================================
# TASK 2: Poincare growth analysis
# ================================================================
print("\n" + "=" * 70)
print("TASK 2: Growth rate analysis")
print("=" * 70)

# The recurrence f_n = (3n+1)f_{n-1} - n(2n-2m-1)f_{n-2}
# Divide by f_{n-1}: r_n = f_n/f_{n-1} = (3n+1) - n(2n-2m-1)/r_{n-1}
# By Poincare: as n->inf, r_n -> root of x = 3n - 2n/x -> x^2 = 3nx - 2n^2
# -> x^2 - 3nx + 2n^2 = 0 -> x = n(3 +/- 1)/2 -> x = 2n or x = n
# Dominant: r_n ~ 2n, subdominant: r_n ~ n

print("\nPoincare analysis: f_n = (3n+1)f_{n-1} - n(2n-2m-1)f_{n-2}")
print("Characteristic eq (leading): x^2 - 3nx + 2n^2 = 0")
print("Roots: x = 2n, x = n")
print("=> Dominant solution grows like (2n)!! = 2^n n!")
print("=> Subdominant solution grows like n!")
print("=> Q_n^(m) ~ C_m (2n)!! (dominant)")
print("=> P_n^(m) ~ D_m (2n)!! (also dominant, same rate)")
print("=> Ratio P/Q -> D_m/C_m = S^(m)")

# Verify growth rates numerically
for m in [0, 1]:
    print(f"\n  m={m}: Q_n^(m) / (2n)!!:")
    for n in [5, 8, 12, 16, 20]:
        qn = families[m]["q"][n + 1]
        dn_fac = Fraction(1)
        for k in range(1, n + 1):
            dn_fac *= 2 * k
        ratio = qn / dn_fac
        print(f"    n={n}: Q/{(2*n)}!! = {float(ratio):.10f}")

# Check L(P)/L(Q) convergence to 2
print("\n  L(P^(0))_n / L(Q^(0))_n:")
p0 = families[0]["p"]
q0 = families[0]["q"]
for n in [5, 8, 12, 16, 20]:
    LP = (n + 2) * p0[n + 1] - (n + 1) ** 2 * p0[n]
    LQ = (n + 2) * q0[n + 1] - (n + 1) ** 2 * q0[n]
    r = LP / LQ
    s0 = p0[n + 1] / q0[n + 1]
    print(f"    n={n}: LP/LQ = {float(r):.12f}  P/Q = {float(s0):.12f}  LP/LQ / (P/Q) = {float(r/s0):.12f}")

print("\n  As n->inf: LP_n/LQ_n -> 2*S^(0) (the factor 2 from c_Q=2)")
print("  Because LP = P^(1) and LQ = 2*Q^(1), so LP/LQ = P^(1)/(2*Q^(1)) = S^(1)/2")
print("  And S^(1) = 4/pi = 2 * (2/pi) = 2*S^(0)  QED")
