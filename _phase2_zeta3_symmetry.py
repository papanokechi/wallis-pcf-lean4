"""
Phase 2 Track C: zeta(3) symmetry-constrained search.
Constrains PCF coefficients to have palindromic/symmetric structure,
inspired by Apéry's identity where beta(n) = 34n^3+51n^2+27n+5 = (2n+1)(17n^2+17n+5)
has the symmetric factor 17n^2+17n+5 (palindromic coefficients 17,17,5... well, almost).

Strategy:
  - a(n) = -C * n^k * (n-1)^k  for k=2,3 (Apéry-like factored structure)
  - b(n) = (2n+1) * P(n) where P is palindromic
  - Also try b(n) = (2n-1) * P(n) and b(n) = n * P(n)
"""
import mpmath
import itertools

mpmath.mp.dps = 100

z3 = mpmath.zeta(3)
pi = mpmath.pi

TARGETS = {
    'zeta3': z3,
    '6/zeta3': 6/z3,
    'zeta3/pi^2': z3/pi**2,
    'pi^2/zeta3': pi**2/z3,
    '5*zeta3': 5*z3,
    '6*zeta3': 6*z3,
    'zeta3/6': z3/6,
}

DEPTH = 400


def eval_cf(alpha_fn, beta_fn, depth=DEPTH):
    """Evaluate CF with given alpha(n) and beta(n) functions."""
    val = mpmath.mpf(beta_fn(depth))
    for n in range(depth - 1, 0, -1):
        a = alpha_fn(n + 1)
        b = beta_fn(n)
        if val == 0:
            return None
        val = mpmath.mpf(b) + mpmath.mpf(a) / val
    a1 = alpha_fn(1)
    b0 = beta_fn(0)
    if val == 0:
        return None
    return mpmath.mpf(b0) + mpmath.mpf(a1) / val


def check_targets(val):
    """Check if val matches any target."""
    if val is None:
        return None
    for name, target in TARGETS.items():
        d = abs(val - target)
        if d == 0:
            return (name, 100)
        if d < mpmath.mpf(10)**(-15):
            digits = int(-mpmath.log10(d))
            if digits >= 20:
                return (name, digits)
    return None


def main():
    print("=" * 78)
    print("  PHASE 2 TRACK C: zeta(3) SYMMETRY-CONSTRAINED SEARCH")
    print("=" * 78)
    print()

    hits = []
    tested = 0

    # ════════════════════════════════════════════════════════════════
    # Strategy 1: Apéry-like — a(n) = -C*n^3*(n-1)^3, b(n) = (2n-1)*P(n)
    # where P(n) = a*n^2 + a*n + b  (palindromic quadratic)
    # ════════════════════════════════════════════════════════════════
    print("Strategy 1: a(n) = -C*n^3*(n-1)^3, b(n) = (2n-1)*(a*n^2+a*n+b)")
    print("-" * 60)

    for C in [1, -1, 2, -2, 4, -4, 8, -8]:
        for a_coeff in range(1, 40):
            for b_coeff in range(1, 20):
                tested += 1
                alpha_fn = lambda n, C=C: -C * n**3 * (n-1)**3
                beta_fn = lambda n, a=a_coeff, b=b_coeff: (2*n - 1) * (a*n**2 + a*n + b)

                try:
                    val = eval_cf(alpha_fn, beta_fn)
                except (ZeroDivisionError, OverflowError):
                    continue

                match = check_targets(val)
                if match:
                    name, digits = match
                    is_apery = (C == 1 and a_coeff == 17 and b_coeff == 5)
                    tag = "APERY" if is_apery else "NEW!!!"
                    hits.append((C, a_coeff, b_coeff, name, digits, '1'))
                    print(f"  [{tag}] C={C}, P=({a_coeff}n^2+{a_coeff}n+{b_coeff}) -> {name} ({digits}d)")

    print(f"  Tested: {tested}")
    print()

    # ════════════════════════════════════════════════════════════════
    # Strategy 2: a(n) = -C*n^2*(n-1)^2, b(n) = (2n-1)*P(n)
    # ════════════════════════════════════════════════════════════════
    print("Strategy 2: a(n) = -C*n^2*(n-1)^2, b(n) = (2n-1)*(a*n+b)")
    print("-" * 60)
    t2 = 0

    for C in [1, -1, 2, -2, 4, -4]:
        for a_coeff in range(1, 30):
            for b_coeff in range(0, 15):
                t2 += 1
                alpha_fn = lambda n, C=C: -C * n**2 * (n-1)**2
                beta_fn = lambda n, a=a_coeff, b=b_coeff: (2*n - 1) * (a*n + b)

                try:
                    val = eval_cf(alpha_fn, beta_fn)
                except (ZeroDivisionError, OverflowError):
                    continue

                match = check_targets(val)
                if match:
                    name, digits = match
                    hits.append((C, a_coeff, b_coeff, name, digits, '2'))
                    print(f"  C={C}, P=({a_coeff}n+{b_coeff}) -> {name} ({digits}d)")

    tested += t2
    print(f"  Tested: {t2}")
    print()

    # ════════════════════════════════════════════════════════════════
    # Strategy 3: Zudilin-type — a(n) = C*n^4, b(n) = (2n+1)*(a*n^2+a*n+b)
    # ════════════════════════════════════════════════════════════════
    print("Strategy 3: a(n) = C*n^4, b(n) = (2n+1)*(a*n^2+a*n+b)")
    print("-" * 60)
    t3 = 0

    for C in [-1, 1, -2, 2, -4, 4, -8, 8, -16, 16]:
        for a_coeff in range(1, 30):
            for b_coeff in range(1, 15):
                t3 += 1
                alpha_fn = lambda n, C=C: C * n**4
                beta_fn = lambda n, a=a_coeff, b=b_coeff: (2*n + 1) * (a*n**2 + a*n + b)

                try:
                    val = eval_cf(alpha_fn, beta_fn)
                except (ZeroDivisionError, OverflowError):
                    continue

                match = check_targets(val)
                if match:
                    name, digits = match
                    hits.append((C, a_coeff, b_coeff, name, digits, '3'))
                    print(f"  C={C}, P=({a_coeff}n^2+{a_coeff}n+{b_coeff}) -> {name} ({digits}d)")

    tested += t3
    print(f"  Tested: {t3}")
    print()

    # ════════════════════════════════════════════════════════════════
    # Strategy 4: a(n) = -n^6, b(n) = general cubic with (2n+1) factor
    # Apéry has b(n) = (2n+1)(17n^2+17n+5). Try nearby.
    # ════════════════════════════════════════════════════════════════
    print("Strategy 4: a(n) = -n^6, b(n) = (2n+1)*(an^2+bn+c), broad scan")
    print("-" * 60)
    t4 = 0

    for a in range(1, 50):
        for b in range(0, 50):
            for c in range(1, 30):
                t4 += 1
                alpha_fn = lambda n: -n**6
                beta_fn = lambda n, a=a, b=b, c=c: (2*n + 1) * (a*n**2 + b*n + c)

                try:
                    val = eval_cf(alpha_fn, beta_fn)
                except (ZeroDivisionError, OverflowError):
                    continue

                match = check_targets(val)
                if match:
                    name, digits = match
                    is_apery = (a == 17 and b == 17 and c == 5)
                    tag = "APERY" if is_apery else "NEW!!!"
                    hits.append((-1, a, b, name, digits, f'4:c={c}'))
                    print(f"  [{tag}] a={a}, b={b}, c={c} -> {name} ({digits}d)")

    tested += t4
    print(f"  Tested: {t4}")
    print()

    # ════════════════════════════════════════════════════════════════
    # SUMMARY
    # ════════════════════════════════════════════════════════════════
    print("=" * 78)
    print(f"TOTAL: {tested} PCFs tested, {len(hits)} hits")
    for h in hits:
        print(f"  Strategy {h[5]}: C={h[0]}, coeffs=({h[1]},{h[2]}) -> {h[3]} ({h[4]}d)")

    new_hits = [h for h in hits if not (h[0] == 1 and h[1] == 17 and h[2] == 5)]
    if new_hits:
        print(f"\n  *** {len(new_hits)} NEW zeta(3) PCFs DISCOVERED! ***")
    elif hits:
        print(f"\n  Only Apéry recovered. zeta(3) appears UNIQUE in symmetric PCF space.")
    else:
        print(f"\n  No hits at all (Apéry parameters may be outside scan range).")


if __name__ == '__main__':
    main()
