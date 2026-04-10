"""Quick test of v14 weighted-crossing logic."""
import numpy as np
from multi_agent_discovery.breakthrough_runner_v14 import (
    weighted_median, allpairs_binder_crossings,
    weighted_crossing_tc, calibrate_crossing_alpha,
    ising_2d_mc_with_U4,
)

# 1. Test weighted_median
vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
wts = np.array([1.0, 1.0, 1.0, 1.0, 100.0])
wm = weighted_median(vals, wts)
print(f"weighted_median([1..5], heavy=5) = {wm}")
assert wm == 5.0, f"Expected 5.0, got {wm}"

wm2 = weighted_median(vals, np.ones(5))
print(f"weighted_median([1..5], uniform) = {wm2}")
assert wm2 == 3.0

# 2. Test 2D Ising MC with U4
print("\nGenerating 2D Ising test data...")
T_test = np.linspace(2.0, 2.6, 10)
multi_2d = {}
for L in [4, 8, 12]:
    data = []
    for i, T in enumerate(T_test):
        obs = ising_2d_mc_with_U4(L, T, n_equil=500, n_measure=500, seed=42+L*100+i)
        data.append(obs)
    multi_2d[L] = data
    u4_vals = [d["U4"] for d in data]
    print(f"  L={L}: U4 range = [{min(u4_vals):.3f}, {max(u4_vals):.3f}]")

# 3. Test allpairs_binder_crossings
crossings = allpairs_binder_crossings(multi_2d)
print(f"\nAll-pairs crossings: {len(crossings)} total")
for c in crossings[:5]:
    print(f"  Tc={c['Tc']:.4f}, L=({c['L_i']},{c['L_j']}), Lprod={c['L_product']}")

# 4. Test weighted_crossing_tc
TC_2D = 2.0 / np.log(1.0 + np.sqrt(2.0))
print(f"\nExact 2D Ising Tc = {TC_2D:.5f}")
for alpha in [0.0, 1.0, 2.0]:
    r = weighted_crossing_tc(crossings, alpha=alpha)
    err = abs(r["Tc_weighted"] - TC_2D) / TC_2D * 100
    print(f"  alpha={alpha:.1f}: Tc={r['Tc_weighted']:.4f} +- {r['Tc_std_weighted']:.4f} (err={err:.2f}%)")

# 5. Test calibrate_crossing_alpha
print("\nCalibrating alpha via LOO...")
calib = calibrate_crossing_alpha(multi_2d, TC_2D)
print(f"  alpha_best = {calib['alpha_best']:.2f}")
print(f"  LOO error: {calib['loo_error_best']:.5f} (weighted)")
if calib.get("loo_error_unweighted"):
    print(f"             {calib['loo_error_unweighted']:.5f} (unweighted)")
if calib.get("improvement"):
    print(f"  Improvement: {calib['improvement']:.1f}x")

print("\n=== ALL TESTS PASSED ===")
