"""Check what nsimplify returns for various candidates."""
import sympy
from sympy import nsimplify, pi, E, EulerGamma, sqrt, log
import mpmath

tests = [
    ("GCF a=-5, b=2n²+2n+2", 1.1131386359376903),
    ("GCF a=-3, b=2n²+5n+5", 4.7472431671753495),
    ("GCF a=-1, b=2n²-3n+1", 0.59175170953613697),
    ("GCF a=5, b=-n²+5n+4", -4.4286834753549),
    ("GCF a=4, b=9n-8", -1.1666666666666667),  # linear-b
]

for name, val in tests:
    print(f"\n{name}: {val}")
    for constants in [
        [pi, E, EulerGamma],
        [pi, sqrt(2), sqrt(3)],
        [pi, E, log(2)],
    ]:
        try:
            exact = nsimplify(val, constants=constants, tolerance=1e-15, rational=False)
            expr_str = str(exact)
            if len(expr_str) <= 40:
                # Check if it's just a number
                try:
                    float(expr_str)
                    is_numeric = True
                except ValueError:
                    is_numeric = False
                print(f"  nsimplify w/ {[str(c) for c in constants]}: {expr_str} {'[NUMERIC]' if is_numeric else '[SYMBOLIC]'}")
        except Exception as e:
            pass
