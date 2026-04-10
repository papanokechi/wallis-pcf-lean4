"""Investigate the surviving PSLQ relation for f0(q=0.2)."""
import mpmath

def mock_theta_f0(q_val, prec=60):
    mpmath.mp.dps = prec
    q = mpmath.mpf(q_val)
    s = mpmath.mpf(0)
    for n in range(100):
        num = q**(n*n)
        den = mpmath.mpf(1)
        for m in range(1, n + 1):
            den *= (1 + q**m)**2
        if abs(den) < mpmath.mpf(10)**(-prec + 5):
            break
        s += num / den
    return s

rel = [30, 33, -9, 1, 2, -13, 28, 16, -9, -28, -3]
basis_names = ["1", "pi", "pi^2", "ln2", "sqrt(2)",
               "euler_gamma", "catalan", "zeta(3)", "sqrt(3)", "ln3"]

print("PSLQ STABILITY TABLE for f0(q=0.2)")
print("=" * 70)

for prec in [60, 120, 240, 500]:
    mpmath.mp.dps = prec
    val = mock_theta_f0(0.2, prec)
    basis = [
        mpmath.mpf(1), mpmath.pi, mpmath.pi**2, mpmath.ln(2),
        mpmath.sqrt(2), mpmath.euler, mpmath.catalan,
        mpmath.zeta(3), mpmath.sqrt(3), mpmath.ln(3),
    ]
    residual = rel[0]*val + sum(c*v for c, v in zip(rel[1:], basis))
    print(f"  prec={prec:3d}: f0 = {float(val):.20f}, |residual| = {float(abs(residual)):.4e}")

    # Also re-run PSLQ from scratch at this precision
    vec = [val] + basis
    try:
        new_rel = mpmath.pslq(vec, maxcoeff=1000, maxsteps=5000)
        if new_rel:
            matches = (list(new_rel) == rel)
            check = sum(r*v for r, v in zip(new_rel, vec))
            print(f"           PSLQ found: {list(new_rel)}")
            print(f"           matches original: {matches}, check: {float(abs(check)):.4e}")
        else:
            print(f"           PSLQ: no relation found")
    except Exception as e:
        print(f"           PSLQ error: {e}")
    print()
