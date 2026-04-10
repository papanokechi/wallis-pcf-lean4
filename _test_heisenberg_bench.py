"""Quick benchmark of the Heisenberg kernel."""
from multi_agent_discovery.heisenberg_kernel import benchmark_heisenberg, heisenberg_3d_mc
import time

print("=== O(3) Heisenberg Kernel Benchmark (vectorized OR) ===\n")

# Quick physics test first
print("Single-point MC: L=4, T=1.5 (near Tc=1.443)")
t0 = time.time()
obs = heisenberg_3d_mc(L=4, T=1.5, n_equil=50, n_measure=100, seed=42)
dt = time.time() - t0
print(f"  Time: {dt:.2f}s")
for k in ['M', 'chi', 'U4', 'C', 'E']:
    print(f"  {k} = {obs[k]:.4f}")

print("\nSingle-point MC: L=8, T=1.44 (at Tc)")
t0 = time.time()
obs = heisenberg_3d_mc(L=8, T=1.44, n_equil=100, n_measure=200, seed=42)
dt = time.time() - t0
print(f"  Time: {dt:.2f}s")
for k in ['M', 'chi', 'U4', 'C', 'E']:
    print(f"  {k} = {obs[k]:.4f}")

# Full benchmark
print("\n")
r = benchmark_heisenberg(L_range=[4, 6, 8], n_temps=3, n_measure=100)
print(f"\nHas Numba: {r['has_numba']}")
print("\nDone!")
