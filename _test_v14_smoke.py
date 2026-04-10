"""Quick smoke test for v14 algorithms."""
import sys, numpy as np
sys.path.insert(0, '.')
from multi_agent_discovery.breakthrough_runner_v14 import (
    scaling_collapse, wegner_corrected_fss, nu_cross_consistency
)

np.random.seed(42)
Tc = 4.51
multi_L = {}
for L in [4, 6, 8, 10, 12]:
    data = []
    for T in np.linspace(3.5, 5.5, 20):
        t = (T - Tc) / Tc
        M = abs(t)**0.3265 * L**(-0.518) if t < 0 else 0.01 * L**(-0.518)
        M += np.random.normal(0, 0.005)
        chi = abs(t)**(-1.237) * L**(1.964) * 0.001 if abs(t) > 0.01 else L**(1.964) * 0.1
        chi += abs(np.random.normal(0, chi * 0.05))
        C = 1.0 + 0.5 * np.log(L) + np.random.normal(0, 0.1)
        U4 = 0.6 - 0.3 * t / (1 + abs(t)) + np.random.normal(0, 0.02)
        data.append({'T': T, 'L': L, 'M': max(M, 0.001), 'chi': max(chi, 0.01),
                     'C': max(C, 0.1), 'U4': U4, 'E': -1.5})
    multi_L[L] = data

# Test 1: Scaling collapse
print('=== Scaling Collapse (M) ===')
r = scaling_collapse(multi_L, Tc, 'M', n_bootstrap=20, seed=42)
print(f"  Status: {r['status']}, S={r['collapse_quality_S']:.4f} ({r['quality_label']})")
print(f"  beta/nu={r['exponents']['beta_over_nu']:.3f}, 1/nu={r['exponents']['one_over_nu']:.3f}")

# Test 2: Wegner corrections
print('=== Wegner Corrections (M) ===')
w = wegner_corrected_fss(multi_L, Tc, 'M', known_omega=0.832)
print(f"  Status: {w['status']}, p={w['best_exponent']:.3f}")
print(f"  Needs correction: {w['needs_correction']}")
print(f"  Selection: {w['model_selection']['reason']}")

# Test 3: nu consistency
print('=== nu Cross-Consistency ===')
n = nu_cross_consistency(multi_L, Tc, 0.1, accepted_nu=0.6301)
print(f"  Status: {n['status']}")
methods = list(n['estimates'].keys())
print(f"  Methods: {methods}")
if n.get('consistency'):
    print(f"  Verdict: {n['consistency']['verdict']}")

print('\nAll v14 algorithms smoke-tested successfully!')
