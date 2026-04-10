"""Quick test of cas_verify precision fix (v4.4)."""
import mpmath
from ramanujan_agent.proof_engine import cas_verify

mp = mpmath.mp.clone()
mp.dps = 100

# Test 1: sqrt(2) — should verify to ~100 digits
val = mp.sqrt(2)
r = cas_verify('sqrt(2)', str(val), prec=100)
print("sqrt(2):", "verified" if r["verified"] else "FAILED",
      f"digits={r['match_digits']}", f"diff={r.get('difference', '?')}")

# Test 2: pi
val2 = mp.pi
r2 = cas_verify('pi', str(val2), prec=100)
print("pi:", "verified" if r2["verified"] else "FAILED",
      f"digits={r2['match_digits']}", f"diff={r2.get('difference', '?')}")

# Test 3: 3+2*sqrt(5)
val3 = 3 + 2 * mp.sqrt(5)
r3 = cas_verify('3 + 2*sqrt(5)', str(val3), prec=100)
print("3+2*sqrt(5):", "verified" if r3["verified"] else "FAILED",
      f"digits={r3['match_digits']}", f"diff={r3.get('difference', '?')}")

# Test 4: wrong value — should NOT verify
r4 = cas_verify('sqrt(3)', str(val), prec=100)
print("sqrt(3) vs sqrt(2):", "WRONGLY verified" if r4["verified"] else "correctly rejected",
      f"digits={r4['match_digits']}")

# Test 5: identify_special_function with quadratic-b
from ramanujan_agent.proof_engine import identify_special_function
# GCF a(n)=-2, b(n)=-1n^2-2n+8
r5 = identify_special_function([-2], [-1, -2, 8], str(mp.mpf("9.06699813605052")), prec=50)
print("\nQuadratic-b identification test:")
print("  identified:", r5["identified"])
for c in r5.get("candidates", []):
    print(f"  {c['type']}: {c.get('formula', c.get('expression', ''))[:80]}")
