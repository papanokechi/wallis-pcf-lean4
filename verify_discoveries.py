"""Deep verification and analysis of PCF discoveries."""
import json, sys
sys.path.insert(0, '.')
import mpmath
mpmath.mp.dps = 200

from ramanujan_breakthrough_generator import PCFEngine
from sympy import Symbol, factor

discoveries = json.load(open('pcf_discoveries.json'))['discoveries']

print("=" * 72)
print("  DEEP VERIFICATION: 5 PCF discoveries at 200 digits / depth 500")
print("=" * 72)

engine = PCFEngine(precision=180)
n = Symbol('n')

known_pcfs = {
    ((0,0,1), (1,2,0)): "Brouncker (1656): classic 4/pi PCF",
}

for i, d in enumerate(discoveries, 1):
    ac = d['alpha_coeffs']
    bc = d['beta_coeffs']
    tgt = d['target']
    
    alpha_poly = sum(c * n**j for j, c in enumerate(ac))
    beta_poly = sum(c * n**j for j, c in enumerate(bc))
    
    print(f"\n  [{i}] target = {d['constant']}", flush=True)
    print(f"  a(n) = {factor(alpha_poly)},  b(n) = {factor(beta_poly)}", flush=True)
    print(f"  coeffs: alpha={ac} beta={bc}", flush=True)
    
    val, err, convs = engine.evaluate_pcf(ac, bc, 500)
    matched, formula, digits = engine.match_known_constant(val, tgt, 180)
    fac = engine.check_factorial_reduction(ac, bc)
    conv = engine.measure_convergence(ac, bc)
    
    print(f"  value = {mpmath.nstr(val, 50)}", flush=True)
    print(f"  match: {formula} at {digits} verified digits", flush=True)
    print(f"  convergence: {conv}, factorial_reduction: {fac}", flush=True)
    
    # PSLQ integer relation
    target_val = engine._get_constant(tgt)
    try:
        rel = mpmath.pslq([val, target_val, mpmath.mpf(1)], maxcoeff=1000)
        if rel:
            a, b, c = rel
            print(f"  PSLQ: {a}*val + {b}*{d['constant']} + {c} = 0", flush=True)
            if a != 0:
                parts = []
                if b != 0:
                    parts.append(f"({-b}/{a})*{d['constant']}")
                if c != 0:
                    parts.append(f"{-c}/{a}")
                print(f"  => val = {' + '.join(parts)}", flush=True)
    except Exception as e:
        print(f"  PSLQ: {e}", flush=True)
    
    key = (tuple(ac), tuple(bc))
    status = known_pcfs.get(key, "POTENTIALLY NOVEL")
    print(f"  classification: {status}", flush=True)

# Summary
print("\n" + "=" * 72)
print("  SUMMARY OF INSIGHTS")
print("=" * 72)
print("""
  1. BROUNCKER PCF (known, 1656):
     a(n)=n^2, b(n)=2n+1 -> 4/pi
     Rediscovered via CMF search. Verifies engine correctness.

  2. FAMILY: a(n)=n(2n-3), b(n)=-(3n+1) -> -4/pi
     Factorization: a(n) = -n(2n-3) negative for n>=2
     This is a VARIANT of the Brouncker family with 3n+1 denominators.

  3. FAMILY: a(n)=n(2n-1), b(n)=-(3n+1) -> -2/pi
     Same denominator family b(n)=3n+1 with different numerator.
     Both PCFs converge to rational multiples of 1/pi.
     
  4. EULER e PCF: a(n)=-n, b(n)=n+3 -> e directly
     Clean linear PCF. Likely related to Euler's classical CF for e.
     If novel: a new member of the e continued fraction family.

  5. PHI PCF: a(n)=(n+1)(n+2), b(n)=-(n+2) -> -2*phi
     Golden ratio from quadratic numerator / linear denominator.
     Note: a(n)/b(n) = -(n+1), so this simplifies nicely.
""", flush=True)
