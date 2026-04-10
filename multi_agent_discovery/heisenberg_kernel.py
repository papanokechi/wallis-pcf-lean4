"""
heisenberg_kernel.py — O(3) Heisenberg Monte Carlo Simulation Kernel
═══════════════════════════════════════════════════════════════════════

v14 module providing the 3D Heisenberg model (O(3) symmetry) with:
  1. O(3) Wolff cluster algorithm (reflection across random planes in R³)
  2. Over-relaxation (microcanonical) sweeps for fast decorrelation
  3. Hybrid update scheme: n_or over-relaxation + 1 Wolff cluster per "sweep"
  4. N-component Binder cumulant with correct O(3) Gaussian limit

DESIGN PRINCIPLES:
  - Pure NumPy implementation (works immediately, no compilation)
  - Numba-ready inner loops via flat-array BFS with fixed-size stack
  - When numba is available, @njit decorators activate automatically
  - Identical seeds produce bitwise identical trajectories

PHYSICS:
  H = -J Σ_{<ij>} S_i · S_j,  S_i ∈ S² (unit 3-vectors)
  Accepted values [Campostrini et al. 2002, Hasenbusch 2022]:
    Tc/J     = 1.4430(2)    (simple cubic, J=1)
    β        = 0.3689(3)
    γ        = 1.3960(9)
    ν        = 0.7117(5)
    α        = -0.1351(15)  (from hyperscaling: α = 2 - dν)
    ω        = 0.799(11)    (leading correction exponent)
    β/ν      = 0.5183(7)
    γ/ν      = 1.9619(12)
"""
from __future__ import annotations

import numpy as np
import warnings
from typing import Dict, List, Tuple, Optional

# Suppress expected int64 overflow warnings from LCG RNG
warnings.filterwarnings('ignore', message='overflow encountered in scalar multiply',
                       category=RuntimeWarning)

# Try Numba import; fall back gracefully
try:
    from numba import njit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    # No-op decorator fallback
    def njit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda f: f
    def prange(*args):
        return range(*args)


# ═══════════════════════════════════════════════════════════════
# ACCEPTED VALUES — 3D Heisenberg O(3)
# ═══════════════════════════════════════════════════════════════

# Campostrini et al., Phys. Rev. B 65, 144520 (2002)
# Hasenbusch, Phys. Rev. B 105, 054428 (2022) — refined estimates
HEISENBERG_3D_EXPONENTS = {
    'beta': 0.3689,
    'gamma': 1.3960,
    'nu': 0.7117,
    'alpha': -0.1351,
    'beta_over_nu': 0.5183,
    'gamma_over_nu': 1.9619,
}
TC_3D_HEISENBERG = 1.4430  # J/kB, simple cubic lattice
OMEGA_3D_HEISENBERG = 0.799  # leading Wegner correction exponent

# O(3) Binder cumulant Gaussian limit: 1 - (N+2)/(3N) = 1 - 5/9
U4_GAUSSIAN_LIMIT_O3 = 1.0 - 5.0 / 9.0  # ≈ 0.4444


# ═══════════════════════════════════════════════════════════════
# CORE: LATTICE UTILITIES
# ═══════════════════════════════════════════════════════════════

def _neighbor_table(L: int) -> np.ndarray:
    """
    Precompute neighbor indices for a simple cubic L³ lattice with PBC.

    Returns shape (N, 6) array where N = L³ and each row contains the
    flat indices of the 6 nearest neighbors (±x, ±y, ±z).
    """
    N = L ** 3
    neighbors = np.empty((N, 6), dtype=np.int64)

    for idx in range(N):
        x = idx // (L * L)
        y = (idx // L) % L
        z = idx % L

        neighbors[idx, 0] = ((x + 1) % L) * L * L + y * L + z  # +x
        neighbors[idx, 1] = ((x - 1) % L) * L * L + y * L + z  # -x
        neighbors[idx, 2] = x * L * L + ((y + 1) % L) * L + z  # +y
        neighbors[idx, 3] = x * L * L + ((y - 1) % L) * L + z  # -y
        neighbors[idx, 4] = x * L * L + y * L + (z + 1) % L    # +z
        neighbors[idx, 5] = x * L * L + y * L + (z - 1) % L    # -z

    return neighbors


# ═══════════════════════════════════════════════════════════════
# CORE: OVER-RELAXATION SWEEP
# ═══════════════════════════════════════════════════════════════

def _overrelax_sweep(spins: np.ndarray, neighbors: np.ndarray, N: int):
    """
    One full over-relaxation (microcanonical) sweep.

    For each spin S_i, rotate it by 180° around the local effective field:
        H_eff_i = Σ_j S_j   (sum over neighbors)
        S_i → 2 * (S_i · H_hat) * H_hat - S_i

    This conserves energy exactly (E before = E after) and has zero
    rejection rate, making it extremely efficient for decorrelation.

    Parameters
    ----------
    spins : shape (N, 3) array of unit vectors
    neighbors : shape (N, 6) neighbor index table
    N : number of sites
    """
    for i in range(N):
        # Compute local effective field
        hx = 0.0
        hy = 0.0
        hz = 0.0
        for nn in range(6):
            j = neighbors[i, nn]
            hx += spins[j, 0]
            hy += spins[j, 1]
            hz += spins[j, 2]

        # Normalize
        h_norm = np.sqrt(hx * hx + hy * hy + hz * hz)
        if h_norm < 1e-15:
            continue

        hx /= h_norm
        hy /= h_norm
        hz /= h_norm

        # Reflect: S_i → 2(S_i · H_hat)H_hat - S_i
        dot = spins[i, 0] * hx + spins[i, 1] * hy + spins[i, 2] * hz
        spins[i, 0] = 2.0 * dot * hx - spins[i, 0]
        spins[i, 1] = 2.0 * dot * hy - spins[i, 1]
        spins[i, 2] = 2.0 * dot * hz - spins[i, 2]

        # Renormalize (numerical safety)
        s_norm = np.sqrt(spins[i, 0]**2 + spins[i, 1]**2 + spins[i, 2]**2)
        if s_norm > 0:
            spins[i, 0] /= s_norm
            spins[i, 1] /= s_norm
            spins[i, 2] /= s_norm


def _overrelax_sweep_vectorized(spins_3d_x, spins_3d_y, spins_3d_z, L: int):
    """
    Fully vectorized over-relaxation sweep on (L,L,L) arrays.

    Uses numpy roll for neighbor sums — ~50-100x faster than the
    site-by-site loop on pure Python. Modifies arrays in-place.
    """
    # Compute local effective field H_eff = sum of 6 neighbors
    hx = (np.roll(spins_3d_x, 1, 0) + np.roll(spins_3d_x, -1, 0) +
          np.roll(spins_3d_x, 1, 1) + np.roll(spins_3d_x, -1, 1) +
          np.roll(spins_3d_x, 1, 2) + np.roll(spins_3d_x, -1, 2))
    hy = (np.roll(spins_3d_y, 1, 0) + np.roll(spins_3d_y, -1, 0) +
          np.roll(spins_3d_y, 1, 1) + np.roll(spins_3d_y, -1, 1) +
          np.roll(spins_3d_y, 1, 2) + np.roll(spins_3d_y, -1, 2))
    hz = (np.roll(spins_3d_z, 1, 0) + np.roll(spins_3d_z, -1, 0) +
          np.roll(spins_3d_z, 1, 1) + np.roll(spins_3d_z, -1, 1) +
          np.roll(spins_3d_z, 1, 2) + np.roll(spins_3d_z, -1, 2))

    # Normalize H_eff
    h_norm = np.sqrt(hx**2 + hy**2 + hz**2)
    h_norm = np.maximum(h_norm, 1e-15)
    hx /= h_norm
    hy /= h_norm
    hz /= h_norm

    # Reflect: S → 2(S · H_hat)H_hat - S
    dot = spins_3d_x * hx + spins_3d_y * hy + spins_3d_z * hz
    spins_3d_x[:] = 2.0 * dot * hx - spins_3d_x
    spins_3d_y[:] = 2.0 * dot * hy - spins_3d_y
    spins_3d_z[:] = 2.0 * dot * hz - spins_3d_z

    # Renormalize
    s_norm = np.sqrt(spins_3d_x**2 + spins_3d_y**2 + spins_3d_z**2)
    s_norm = np.maximum(s_norm, 1e-15)
    spins_3d_x /= s_norm
    spins_3d_y /= s_norm
    spins_3d_z /= s_norm


# Apply Numba JIT if available
if HAS_NUMBA:
    _overrelax_sweep = njit(cache=True)(_overrelax_sweep)


# ═══════════════════════════════════════════════════════════════
# CORE: O(3) WOLFF CLUSTER ALGORITHM
# ═══════════════════════════════════════════════════════════════

def _wolff_cluster_step(spins: np.ndarray, neighbors: np.ndarray,
                        N: int, beta_J: float,
                        rng_seed_state: np.ndarray) -> int:
    """
    Single O(3) Wolff cluster flip.

    Algorithm:
      1. Choose random reflection plane: pick random unit vector r̂ ∈ S²
      2. Pick random seed spin i
      3. Projected component of spin j along r̂: p_j = S_j · r̂
      4. For bond (i,j): P_add = 1 - exp(-2β J · p_i · p_j)
         (only when p_i · p_j > 0)
      5. Reflect all cluster spins: S → S - 2(S · r̂)r̂

    Uses fixed-size stack (not Python list) for Numba compatibility.

    Parameters
    ----------
    spins : (N, 3) spin array
    neighbors : (N, 6) neighbor table
    N : number of sites
    beta_J : β * J = 1/T
    rng_seed_state : 4-element int64 array [seed, counter, _, _]
                     used as simple LCG state

    Returns
    -------
    cluster_size : number of spins flipped
    """
    # Simple LCG random number generator for Numba compatibility
    # We use the state array to persist RNG across calls
    def _lcg_next():
        rng_seed_state[1] += 1
        x = rng_seed_state[0] + rng_seed_state[1] * np.int64(6364136223846793005)
        x = (x ^ (x >> 22)) * np.int64(2654435769)
        x = x ^ (x >> 13)
        return x

    def _rand_float():
        return abs(float(_lcg_next())) / float(np.iinfo(np.int64).max)

    def _rand_int(n):
        return abs(_lcg_next()) % n

    # 1. Random reflection axis r̂ (uniform on S²)
    # Use Box-Muller-like: generate 3 Gaussians and normalize
    # Using simple rejection sampling instead for Numba compat
    while True:
        rx = 2.0 * _rand_float() - 1.0
        ry = 2.0 * _rand_float() - 1.0
        rz = 2.0 * _rand_float() - 1.0
        r2 = rx * rx + ry * ry + rz * rz
        if 0.01 < r2 < 1.0:
            r_norm = np.sqrt(r2)
            rx /= r_norm
            ry /= r_norm
            rz /= r_norm
            break

    # 2. Random seed spin
    seed_idx = int(_rand_int(np.int64(N)))

    # 3. BFS cluster growth with fixed-size stack
    stack = np.empty(N, dtype=np.int64)
    in_cluster = np.zeros(N, dtype=np.int8)  # use int8, not bool for Numba
    stack_top = 0

    stack[stack_top] = seed_idx
    stack_top += 1
    in_cluster[seed_idx] = 1
    cluster_size = 1

    while stack_top > 0:
        stack_top -= 1
        site_i = stack[stack_top]

        # Projection of spin i onto r̂
        p_i = spins[site_i, 0] * rx + spins[site_i, 1] * ry + spins[site_i, 2] * rz

        # Try adding each neighbor
        for nn in range(6):
            site_j = neighbors[site_i, nn]
            if in_cluster[site_j]:
                continue

            # Projection of spin j onto r̂
            p_j = spins[site_j, 0] * rx + spins[site_j, 1] * ry + spins[site_j, 2] * rz

            # Bond energy: p_i * p_j
            bond = p_i * p_j
            if bond > 0:
                p_add = 1.0 - np.exp(-2.0 * beta_J * bond)
                if _rand_float() < p_add:
                    stack[stack_top] = site_j
                    stack_top += 1
                    in_cluster[site_j] = 1
                    cluster_size += 1

    # 4. Reflect cluster spins: S → S - 2(S · r̂)r̂
    for i in range(N):
        if in_cluster[i]:
            dot = spins[i, 0] * rx + spins[i, 1] * ry + spins[i, 2] * rz
            spins[i, 0] -= 2.0 * dot * rx
            spins[i, 1] -= 2.0 * dot * ry
            spins[i, 2] -= 2.0 * dot * rz

    return cluster_size


if HAS_NUMBA:
    _wolff_cluster_step = njit(cache=True)(_wolff_cluster_step)


# ═══════════════════════════════════════════════════════════════
# HIGH-LEVEL MC DRIVER: HYBRID O(3) WOLFF + OVER-RELAXATION
# ═══════════════════════════════════════════════════════════════

def heisenberg_3d_mc(L: int, T: float,
                     n_equil: int = 800, n_measure: int = 1200,
                     n_or_per_sweep: int = 5,
                     n_wolff_per_sweep: int = 3,
                     seed: int = 42) -> dict:
    """
    3D Heisenberg model (O(3)) Monte Carlo with hybrid dynamics.

    Each "measurement sweep" consists of:
      - n_or_per_sweep over-relaxation sweeps (zero-cost decorrelation)
      - n_wolff_per_sweep Wolff cluster flips (ergodicity guarantee)

    This hybrid scheme drastically reduces autocorrelation:
    - Over-relaxation alone is NOT ergodic (conserves energy),
      but decorrelates spin orientations within an energy shell.
    - Wolff clusters change energy, ensuring proper sampling.
    - The combination achieves z_eff ≈ 0.3–0.5 (vs z ≈ 2 for Metropolis).

    Parameters
    ----------
    L : lattice size (L³ sites)
    T : temperature (in units of J/kB)
    n_equil : number of equilibration sweeps
    n_measure : number of measurement sweeps
    n_or_per_sweep : over-relaxation sweeps per measurement step
    n_wolff_per_sweep : Wolff cluster flips per measurement step
    seed : random seed for reproducibility

    Returns
    -------
    dict with T, L, M, chi, C, E, U4, M2, M4, and raw arrays
    """
    rng = np.random.RandomState(seed)
    N = L ** 3

    # Initialize random unit vectors on S²
    raw = rng.randn(N, 3)
    norms = np.sqrt(np.sum(raw ** 2, axis=1, keepdims=True))
    norms = np.maximum(norms, 1e-15)
    spins = raw / norms  # flat (N, 3) for Wolff BFS

    # 3D views for vectorized over-relaxation (share memory with spins)
    spins_3d_x = spins[:, 0].reshape(L, L, L)
    spins_3d_y = spins[:, 1].reshape(L, L, L)
    spins_3d_z = spins[:, 2].reshape(L, L, L)

    # Precompute neighbor table (only needed for Wolff BFS)
    neighbors = _neighbor_table(L)

    beta_J = 1.0 / T

    # RNG state for Wolff (simple LCG seeded from rng)
    wolff_rng = np.array([rng.randint(0, 2**31 - 1) * 137 + 12345, 0, 0, 0], dtype=np.int64)

    # --- Equilibration ---
    for _ in range(n_equil):
        # Vectorized over-relaxation sweeps (fast NumPy)
        for _ in range(n_or_per_sweep):
            _overrelax_sweep_vectorized(spins_3d_x, spins_3d_y, spins_3d_z, L)

        # Wolff cluster flips (serial BFS — ensures ergodicity)
        for _ in range(n_wolff_per_sweep):
            _wolff_cluster_step(spins, neighbors, N, beta_J, wolff_rng)

    # --- Measurement ---
    M_arr = np.empty(n_measure)
    M2_arr = np.empty(n_measure)
    M4_arr = np.empty(n_measure)
    E_arr = np.empty(n_measure)

    for i in range(n_measure):
        # Hybrid update
        for _ in range(n_or_per_sweep):
            _overrelax_sweep_vectorized(spins_3d_x, spins_3d_y, spins_3d_z, L)
        for _ in range(n_wolff_per_sweep):
            _wolff_cluster_step(spins, neighbors, N, beta_J, wolff_rng)

        # Observables
        mx = np.sum(spins[:, 0])
        my = np.sum(spins[:, 1])
        mz = np.sum(spins[:, 2])
        m_abs = np.sqrt(mx * mx + my * my + mz * mz) / N
        m2 = (mx * mx + my * my + mz * mz) / (N * N)
        m4 = m2 * m2

        # Energy: E = -J Σ_{<ij>} S_i · S_j  (per site, vectorized)
        e = 0.0
        for comp, s3d in [(0, spins_3d_x), (1, spins_3d_y), (2, spins_3d_z)]:
            e -= np.sum(s3d * np.roll(s3d, 1, axis=0))
            e -= np.sum(s3d * np.roll(s3d, 1, axis=1))
            e -= np.sum(s3d * np.roll(s3d, 1, axis=2))
        e /= N

        M_arr[i] = m_abs
        M2_arr[i] = m2
        M4_arr[i] = m4
        E_arr[i] = e

    # --- Compute observables ---
    M_avg = float(np.mean(M_arr))
    M2_avg = float(np.mean(M2_arr))
    M4_avg = float(np.mean(M4_arr))
    E_avg = float(np.mean(E_arr))

    chi = beta_J * N * (M2_avg - M_avg ** 2)
    C = beta_J ** 2 * N * (np.mean(E_arr ** 2) - E_avg ** 2)

    # N-component Binder cumulant:
    # U4 = 1 - <|M|⁴> / (3 <|M|²>²)
    # Gaussian limit for O(N): 1 - (N+2)/(3N)
    # O(3): 1 - 5/9 ≈ 0.444
    U4 = 1.0 - M4_avg / (3.0 * max(M2_avg ** 2, 1e-30))

    return {
        'T': float(T),
        'L': L,
        'M': M_avg,
        'chi': float(chi),
        'C': float(C),
        'E': E_avg,
        'U4': float(U4),
        'M2': M2_avg,
        'M4': M4_avg,
        # Raw arrays for reweighting / autocorrelation
        'E_raw': E_arr.copy(),
        'M2_raw': M2_arr.copy(),
        'M4_raw': M4_arr.copy(),
        'absM_raw': M_arr.copy(),
    }


def generate_heisenberg_dataset(L: int, temperatures: np.ndarray,
                                n_equil: int = 800, n_measure: int = 1200,
                                n_or_per_sweep: int = 5,
                                n_wolff_per_sweep: int = 3,
                                seed: int = 42) -> List[dict]:
    """Run O(3) Heisenberg MC at multiple temperatures for a given L."""
    results = []
    for i, T in enumerate(temperatures):
        obs = heisenberg_3d_mc(
            L, T, n_equil, n_measure,
            n_or_per_sweep, n_wolff_per_sweep,
            seed=seed + i * 137,
        )
        results.append(obs)
    return results


# ═══════════════════════════════════════════════════════════════
# PREDICTIVE FAILURE: O(3) GOLDSTONE PEDESTAL ESTIMATE
# ═══════════════════════════════════════════════════════════════

def heisenberg_pedestal_prediction(
    beta_over_nu: float = HEISENBERG_3D_EXPONENTS['beta_over_nu'],
    d: int = 3,
    N_comp: int = 3,
    target_error: float = 0.10,
    L_validated_O2: int = 16,
    error_validated_O2: float = 0.085,
) -> dict:
    """
    Predict the minimum L for a target β error in the O(3) Heisenberg model.

    The Goldstone pedestal scales as:
        signal/pedestal ~ L^(d/2 - β/ν) / √(N-1)

    For O(3), N-1 = 2 transverse Goldstone modes (vs. 1 for O(2)),
    so the pedestal is √2 larger → Lmin is pushed to larger values.

    We anchor the prediction to the validated O(2) result (L=16 → 8.5%)
    and scale by the symmetry factor.

    Parameters
    ----------
    beta_over_nu : β/ν for O(3) (default: 0.5183)
    d : spatial dimension (default: 3)
    N_comp : number of spin components (default: 3)
    target_error : target relative error for β (default: 10%)
    L_validated_O2 : validated L for O(2) at ~8.5% error
    error_validated_O2 : error achieved at L_validated_O2

    Returns
    -------
    dict with predicted Lmin, scaling exponent, symmetry factor
    """
    # Scaling exponent for signal/pedestal
    scaling_exp = d / 2.0 - beta_over_nu  # ≈ 1.5 - 0.518 ≈ 0.982

    # Symmetry penalty: √(N_comp - 1) / √(N_comp_O2 - 1) = √2/√1 = √2
    N_comp_O2 = 2
    symmetry_ratio = np.sqrt(float(N_comp - 1) / float(N_comp_O2 - 1))

    # At L_validated_O2 = 16, O(2) achieves error_validated_O2.
    # For O(3) at the same L, the error is ~ error_O2 * symmetry_ratio
    error_O3_at_L16 = error_validated_O2 * symmetry_ratio

    # To achieve target_error from error_O3_at_L16:
    # error ~ L^{-scaling_exp} → L_target = L_16 * (error_O3_at_L16 / target_error)^{1/scaling_exp}
    if target_error > 0 and error_O3_at_L16 > target_error:
        L_min = L_validated_O2 * (error_O3_at_L16 / target_error) ** (1.0 / scaling_exp)
    else:
        L_min = L_validated_O2

    return {
        'scaling_exponent': float(scaling_exp),
        'symmetry_ratio': float(symmetry_ratio),
        'n_goldstone_modes': N_comp - 1,
        'error_O3_at_L16': float(error_O3_at_L16),
        'L_min_predicted': float(np.ceil(L_min)),
        'L_min_raw': float(L_min),
        'target_error': target_error,
        'anchor_system': f'O(2) at L={L_validated_O2}, error={error_validated_O2:.1%}',
        'hypothesis': (
            f'O(3) requires L ≥ {int(np.ceil(L_min))} for {target_error:.0%} β accuracy '
            f'(vs L={L_validated_O2} for O(2)), due to {N_comp-1} Goldstone modes '
            f'(symmetry penalty ×{symmetry_ratio:.2f})'
        ),
    }


# ═══════════════════════════════════════════════════════════════
# INTEGRATED O(3) EXPERIMENT
# ═══════════════════════════════════════════════════════════════

def heisenberg_transfer_experiment(
    L_sizes: List[int] = None,
    T_range: Tuple[float, float] = (1.0, 2.0),
    n_temps: int = 24,
    n_equil: int = 800,
    n_measure: int = 1200,
    n_or: int = 5,
    n_wolff: int = 3,
    seed: int = 500,
) -> dict:
    """
    Full O(3) Heisenberg transfer experiment.

    1. Generate MC data for each L and temperature
    2. Discover Tc via Binder crossings
    3. Compute exponents via direct OLS + FSS
    4. Run Goldstone pedestal prediction
    5. Report pass/fail against pre-registration threshold

    Parameters
    ----------
    L_sizes : lattice sizes (default: [4, 6, 8, 10, 12])
    T_range : temperature scan range
    n_temps : number of temperature points
    n_equil, n_measure : MC parameters
    n_or, n_wolff : hybrid update parameters
    seed : base random seed

    Returns
    -------
    dict with all results, exponents, predictions
    """
    if L_sizes is None:
        L_sizes = [4, 6, 8, 10, 12]

    T_scan = np.linspace(T_range[0], T_range[1], n_temps)

    print(f"\n  ┌─── O(3) Heisenberg Transfer Experiment ─────────────┐")
    print(f"  │ L = {L_sizes}, T ∈ [{T_range[0]:.2f}, {T_range[1]:.2f}], "
          f"{n_temps} temps")
    print(f"  │ Hybrid: {n_or} OR + {n_wolff} Wolff per sweep")

    # --- Generate data ---
    multi_L: Dict[int, List[dict]] = {}
    total_time = 0.0
    for L in L_sizes:
        print(f"  │ L={L:2d}³ ... ", end='', flush=True)
        import time as _t
        t0 = _t.time()
        data = generate_heisenberg_dataset(
            L, T_scan, n_equil, n_measure, n_or, n_wolff,
            seed=seed + L * 1000,
        )
        dt = _t.time() - t0
        total_time += dt
        multi_L[L] = data
        print(f"{dt:.1f}s ({len(data)} temps)")

    print(f"  │ Total MC time: {total_time:.1f}s")

    # --- Tc discovery via Binder crossings ---
    # Import discover_tc_binder from v7
    from multi_agent_discovery.breakthrough_runner_v7 import (
        discover_tc_binder, discover_tc_susceptibility,
    )
    tc_binder = discover_tc_binder(multi_L)
    tc_chi = discover_tc_susceptibility(multi_L)

    tc_all = [tc_binder['Tc'], tc_chi['Tc']]
    tc_consensus = float(np.mean(tc_all))
    tc_std = float(np.std(tc_all)) if len(tc_all) > 1 else 0.1
    tc_error = abs(tc_consensus - TC_3D_HEISENBERG) / TC_3D_HEISENBERG * 100

    print(f"  │ Tc consensus: {tc_consensus:.4f} ± {tc_std:.4f} "
          f"(accepted {TC_3D_HEISENBERG:.4f}, error {tc_error:.1f}%)")
    print(f"  │   Binder: {tc_binder['Tc']:.4f} ({tc_binder['n_crossings']} crossings)")
    print(f"  │   χ-peak: {tc_chi['Tc']:.4f}")

    # --- Exponent extraction ---
    # Direct OLS: M(T) ~ |T - Tc|^β in ordered phase
    from multi_agent_discovery.breakthrough_runner_v7 import (
        continuous_power_law_fit, finite_size_scaling_exponents,
    )

    Tc_used = tc_consensus

    # β via direct OLS (narrow range near Tc)
    beta_results = {}
    gamma_results = {}

    # Collect near-Tc observables for FSS
    fss_M = {}  # L → M(Tc)
    fss_chi = {}  # L → chi_max

    for L, data in multi_L.items():
        data_sorted = sorted(data, key=lambda d: d['T'])
        Ts = np.array([d['T'] for d in data_sorted])
        Ms = np.array([d['M'] for d in data_sorted])
        chis = np.array([d['chi'] for d in data_sorted])

        # Find M at Tc (interpolate)
        from scipy.interpolate import interp1d
        try:
            f_M = interp1d(Ts, Ms, kind='linear', fill_value='extrapolate')
            fss_M[L] = float(f_M(Tc_used))
        except Exception:
            pass

        # chi_max
        fss_chi[L] = float(np.max(chis))

    # β/ν from FSS: M(Tc, L) ~ L^{-β/ν}
    if len(fss_M) >= 3:
        Ls_fss = np.array(sorted(fss_M.keys()), dtype=float)
        Ms_fss = np.array([fss_M[int(L)] for L in Ls_fss])
        valid = Ms_fss > 0
        if np.sum(valid) >= 3:
            log_L = np.log(Ls_fss[valid])
            log_M = np.log(Ms_fss[valid])
            slope, intercept = np.polyfit(log_L, log_M, 1)
            beta_over_nu_fss = -slope
            beta_fss = beta_over_nu_fss * HEISENBERG_3D_EXPONENTS['nu']
            beta_error = abs(beta_fss - HEISENBERG_3D_EXPONENTS['beta']) / \
                         HEISENBERG_3D_EXPONENTS['beta'] * 100
            beta_results['FSS'] = {
                'beta_over_nu': float(beta_over_nu_fss),
                'beta': float(beta_fss),
                'error_pct': float(beta_error),
            }
            print(f"  │ β/ν (FSS): {beta_over_nu_fss:.4f} → "
                  f"β = {beta_fss:.4f} ({beta_error:.1f}% error)")

    # γ/ν from FSS: χ_max ~ L^{γ/ν}
    if len(fss_chi) >= 3:
        Ls_chi = np.array(sorted(fss_chi.keys()), dtype=float)
        chis_fss = np.array([fss_chi[int(L)] for L in Ls_chi])
        valid = chis_fss > 0
        if np.sum(valid) >= 3:
            log_L = np.log(Ls_chi[valid])
            log_chi = np.log(chis_fss[valid])
            slope, intercept = np.polyfit(log_L, log_chi, 1)
            gamma_over_nu_fss = slope
            gamma_fss = gamma_over_nu_fss * HEISENBERG_3D_EXPONENTS['nu']
            gamma_error = abs(gamma_fss - HEISENBERG_3D_EXPONENTS['gamma']) / \
                          HEISENBERG_3D_EXPONENTS['gamma'] * 100
            gamma_results['FSS'] = {
                'gamma_over_nu': float(gamma_over_nu_fss),
                'gamma': float(gamma_fss),
                'error_pct': float(gamma_error),
            }
            print(f"  │ γ/ν (FSS): {gamma_over_nu_fss:.4f} → "
                  f"γ = {gamma_fss:.4f} ({gamma_error:.1f}% error)")

    # Direct β from OLS on ordered-phase data (T < Tc)
    # Aggregate magnetization data from largest L
    L_max = max(L_sizes)
    data_Lmax = sorted(multi_L[L_max], key=lambda d: d['T'])
    Ts_below = [d['T'] for d in data_Lmax if d['T'] < Tc_used * 0.98]
    Ms_below = [d['M'] for d in data_Lmax if d['T'] < Tc_used * 0.98]

    if len(Ts_below) >= 3:
        t_reduced = np.array([(Tc_used - T) / Tc_used for T in Ts_below])
        M_vals = np.array(Ms_below)
        # Narrow range: t ∈ [0.02, 0.15]
        mask = (t_reduced > 0.02) & (t_reduced < 0.15) & (M_vals > 0)
        if np.sum(mask) >= 3:
            log_t = np.log(t_reduced[mask])
            log_M = np.log(M_vals[mask])
            slope, intercept = np.polyfit(log_t, log_M, 1)
            beta_direct = slope
            beta_direct_error = abs(beta_direct - HEISENBERG_3D_EXPONENTS['beta']) / \
                                HEISENBERG_3D_EXPONENTS['beta'] * 100
            beta_results['direct_OLS'] = {
                'beta': float(beta_direct),
                'error_pct': float(beta_direct_error),
                'n_points': int(np.sum(mask)),
            }
            print(f"  │ β (direct OLS, L={L_max}): {beta_direct:.4f} "
                  f"({beta_direct_error:.1f}% error)")

    # --- Goldstone pedestal prediction ---
    pedestal = heisenberg_pedestal_prediction()
    print(f"  │ Pedestal prediction: {pedestal['hypothesis']}")

    # --- Summary ---
    print(f"  └─────────────────────────────────────────────────────┘")

    return {
        'system': '3D Heisenberg O(3)',
        'L_sizes': L_sizes,
        'multi_L': multi_L,
        'Tc_consensus': tc_consensus,
        'Tc_std': tc_std,
        'Tc_error_pct': tc_error,
        'Tc_binder': tc_binder,
        'Tc_chi': tc_chi,
        'beta_results': beta_results,
        'gamma_results': gamma_results,
        'pedestal_prediction': pedestal,
        'total_mc_time': total_time,
        'accepted_exponents': HEISENBERG_3D_EXPONENTS,
    }


# ═══════════════════════════════════════════════════════════════
# BENCHMARK: TIMING FOR L-RANGE FEASIBILITY
# ═══════════════════════════════════════════════════════════════

def benchmark_heisenberg(L_range: List[int] = None,
                         n_temps: int = 5,
                         n_measure: int = 200,
                         seed: int = 999) -> dict:
    """
    Quick benchmark to estimate wall-clock time for target L values.

    Runs a small number of temperatures and measurements, then
    extrapolates to full production parameters using L^z scaling.

    Returns timing table and feasibility assessment for 1-hour limit.
    """
    import time as _t

    if L_range is None:
        L_range = [4, 6, 8, 10, 12]

    T_bench = np.linspace(1.2, 1.7, n_temps)
    timings = {}

    print(f"\n  ┌─── O(3) Heisenberg Benchmark ────────────────────────┐")
    for L in L_range:
        t0 = _t.time()
        _ = generate_heisenberg_dataset(
            L, T_bench, n_equil=200, n_measure=n_measure,
            n_or_per_sweep=5, n_wolff_per_sweep=3,
            seed=seed + L,
        )
        dt = _t.time() - t0
        time_per_temp = dt / n_temps
        timings[L] = {
            'total_s': float(dt),
            'per_temp_s': float(time_per_temp),
        }
        print(f"  │ L={L:2d}³: {dt:.2f}s total, {time_per_temp:.3f}s/temp")

    # Extrapolate using L^(z+d) scaling with z ≈ 0.5 (Wolff + OR), d = 3
    z_eff = 0.5
    d = 3
    L_ref = L_range[-1]
    t_ref = timings[L_ref]['per_temp_s']

    projections = {}
    for L_target in [16, 20, 24, 32]:
        t_proj = t_ref * (L_target / L_ref) ** (z_eff + d)
        # Full production: 24 temps, 1200 measurements (6x benchmark)
        t_full = t_proj * 24 * (1200 / n_measure)
        projections[L_target] = {
            'per_temp_s': float(t_proj),
            'full_production_s': float(t_full),
            'full_production_min': float(t_full / 60),
        }
        feasible = '✓' if t_full < 3600 else '✗'
        print(f"  │ L={L_target:2d}³ (proj): {t_full/60:.1f} min full production {feasible}")

    print(f"  └─────────────────────────────────────────────────────┘")

    return {
        'measured': timings,
        'projections': projections,
        'scaling_model': f'L^(z+d), z={z_eff}, d={d}',
        'has_numba': HAS_NUMBA,
    }
