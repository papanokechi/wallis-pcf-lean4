"""Test Bessel identification for the 2 novel linear-b CFs from v4.1."""
import mpmath

mp = mpmath.mp.clone()
mp.dps = 100

for name, A, alpha, beta in [
    ("CF a=[-6], b=[8,7]", -6, 8, 7),
    ("CF a=[-9], b=[-7,8]", -9, -7, 8),
]:
    print(f"\n=== {name} ===")
    c = mp.mpf(A) / mp.mpf(alpha)
    a0 = 1 + mp.mpf(beta) / mp.mpf(alpha)
    print(f"  A={A}, alpha={alpha}, beta={beta}")
    print(f"  c = {float(c):.6f}, a0 = {float(a0):.6f}")

    # Compute actual CF value via Lentz
    val = mp.mpf(beta)  # b(0)
    tiny = mp.mpf(10) ** (-100)
    C = val if val != 0 else tiny
    D = mp.mpf(0)
    for n in range(1, 500):
        an = mp.mpf(A)
        bn = mp.mpf(alpha * n + beta)
        D = bn + an * D
        if D == 0: D = tiny
        C = bn + an / C
        if C == 0: C = tiny
        D = 1 / D
        val *= C * D
    actual = val
    print(f"  Actual CF value: {mp.nstr(actual, 22)}")

    # Bessel prediction
    if c > 0:
        z = 2 * mp.sqrt(c)
        f = mp.sqrt(c) * mp.besseli(a0, z) / mp.besseli(a0 - 1, z)
        predicted = mp.mpf(beta) + mp.mpf(alpha) * f
        btype = "I"
    elif c < 0:
        z = 2 * mp.sqrt(-c)
        Ja = mp.besselj(a0, z)
        Jam1 = mp.besselj(a0 - 1, z)
        print(f"  J_{float(a0):.4f}({float(z):.4f}) = {float(Ja):.15f}")
        print(f"  J_{float(a0-1):.4f}({float(z):.4f}) = {float(Jam1):.15f}")
        f = -mp.sqrt(-c) * Ja / Jam1
        predicted = mp.mpf(beta) + mp.mpf(alpha) * f
        btype = "J"
    else:
        print("  c=0, skip")
        continue

    print(f"  Bessel {btype} prediction: {mp.nstr(predicted, 22)}")
    diff = abs(actual - predicted)
    print(f"  diff = {float(diff):.4e}")
    print(f"  threshold (prec//3=33): {float(mp.mpf(10)**(-33)):.4e}")
    print(f"  MATCH at prec//3? {diff < mp.mpf(10)**(-33)}")
