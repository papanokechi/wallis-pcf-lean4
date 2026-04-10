"""Quick integration test: Phase F Heisenberg transfer (minimal params)."""
import sys, os, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings('ignore', category=RuntimeWarning)

from multi_agent_discovery.heisenberg_kernel import (
    heisenberg_transfer_experiment,
    benchmark_heisenberg,
    heisenberg_pedestal_prediction,
)

print("=== Minimal Heisenberg Transfer Test ===")
print("(L=[4,6], 5 temps, 50 measurements — should take <30s)\n")

result = heisenberg_transfer_experiment(
    L_sizes=[4, 6],
    T_range=(1.2, 1.7),
    n_temps=5,
    n_equil=100,
    n_measure=50,
    n_or=5,
    n_wolff=3,
    seed=42,
)

print(f"\n--- Return dict keys: {sorted(result.keys())}")
print(f"  system: {result['system']}")
print(f"  Tc_consensus: {result['Tc_consensus']:.4f} ± {result['Tc_std']:.4f}")
print(f"  Tc_error_pct: {result['Tc_error_pct']:.1f}%")
print(f"  beta_results: {list(result['beta_results'].keys())}")
print(f"  gamma_results: {list(result['gamma_results'].keys())}")
print(f"  pedestal: {result['pedestal_prediction']['hypothesis']}")
print(f"  total_mc_time: {result['total_mc_time']:.1f}s")

# Verify multi_L structure
for L, data in result['multi_L'].items():
    print(f"  L={L}: {len(data)} temp points, keys={sorted(data[0].keys())}")

print("\n=== PASS: Integration test completed successfully ===")
