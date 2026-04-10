#!/usr/bin/env python3
"""
Relay Chain v2 — Round 1 — Agent 1 (Conjecture Agent)
3D Edwards-Anderson Spin Glass: AT Line Investigation
Parallel Tempering Monte Carlo with Disorder Averaging

Target: Binder cumulant g(L, T, h) for the spin-glass overlap q,
        scanning T at fixed h to detect AT line crossing.
"""

import numpy as np
import time
import json
import sys
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
# CORE: 3D Edwards-Anderson Spin Glass with Parallel Tempering
# ═══════════════════════════════════════════════════════════════

class EASpinGlass3D:
    """
    3D Edwards-Anderson ±J spin glass on L×L×L cubic lattice.
    Implements parallel tempering (replica exchange) MC.
    Two independent replicas per temperature for overlap measurement.
    """

    def __init__(self, L, h, temperatures, couplings, seed=None):
        """
        L: linear lattice size
        h: external field strength
        temperatures: array of temperatures for parallel tempering
        couplings: (L,L,L,3) array of ±1 couplings (pre-generated for this disorder sample)
        seed: RNG seed
        """
        self.L = L
        self.N = L ** 3
        self.h = h
        self.temps = np.array(temperatures, dtype=np.float64)
        self.n_temps = len(temperatures)
        self.J = couplings  # shape (L,L,L,3): bonds in +x, +y, +z directions
        self.rng = np.random.RandomState(seed)

        # Two independent replicas at each temperature (for overlap q)
        self.spins_a = [self.rng.choice([-1, 1], size=(L, L, L)).astype(np.int8)
                        for _ in range(self.n_temps)]
        self.spins_b = [self.rng.choice([-1, 1], size=(L, L, L)).astype(np.int8)
                        for _ in range(self.n_temps)]

    def _compute_energy(self, spins):
        """Compute total energy for a spin configuration."""
        L = self.L
        # Nearest-neighbor interaction with disordered couplings
        E_bond = 0.0
        E_bond -= np.sum(self.J[:,:,:,0] * spins * np.roll(spins, -1, axis=0))
        E_bond -= np.sum(self.J[:,:,:,1] * spins * np.roll(spins, -1, axis=1))
        E_bond -= np.sum(self.J[:,:,:,2] * spins * np.roll(spins, -1, axis=2))
        # External field
        E_field = -self.h * np.sum(spins)
        return float(E_bond + E_field)

    def _metropolis_sweep(self, spins, beta):
        """One full Metropolis sweep using checkerboard decomposition."""
        L = self.L
        idx = np.indices((L, L, L))
        J = self.J

        for parity in (0, 1):
            mask = ((idx[0] + idx[1] + idx[2]) % 2 == parity)

            # Sum of J_ij * sigma_j over 6 neighbors
            nn_field = (
                J[:,:,:,0] * np.roll(spins, -1, axis=0) +  # +x neighbor
                np.roll(J[:,:,:,0] * spins, 1, axis=0) +    # -x neighbor (bond from -x)
                J[:,:,:,1] * np.roll(spins, -1, axis=1) +  # +y neighbor
                np.roll(J[:,:,:,1] * spins, 1, axis=1) +    # -y neighbor
                J[:,:,:,2] * np.roll(spins, -1, axis=2) +  # +z neighbor
                np.roll(J[:,:,:,2] * spins, 1, axis=2)      # -z neighbor
            )

            # dE = 2 * sigma_i * (sum_j J_ij sigma_j + h)
            local_field = nn_field + self.h
            dE = 2.0 * spins.astype(np.float64) * local_field

            # Metropolis acceptance
            accept = (dE <= 0) | (self.rng.random((L, L, L)) < np.exp(-beta * np.clip(dE, 0, 40)))
            flip = mask & accept
            spins[flip] *= -1

    def _replica_exchange(self):
        """Attempt swap between adjacent temperature replicas."""
        # For both replica sets (a and b)
        for spins_set in [self.spins_a, self.spins_b]:
            # Sweep odd/even pairs alternately
            for offset in [0, 1]:
                for i in range(offset, self.n_temps - 1, 2):
                    beta_i = 1.0 / self.temps[i]
                    beta_j = 1.0 / self.temps[i + 1]
                    E_i = self._compute_energy(spins_set[i])
                    E_j = self._compute_energy(spins_set[i + 1])
                    delta = (beta_i - beta_j) * (E_j - E_i)
                    if delta <= 0 or self.rng.random() < np.exp(-delta):
                        spins_set[i], spins_set[i + 1] = spins_set[i + 1], spins_set[i]

    def compute_overlap(self, temp_idx):
        """Compute spin overlap q between replica a and b at temperature index."""
        q = np.mean(self.spins_a[temp_idx].astype(np.float64) *
                    self.spins_b[temp_idx].astype(np.float64))
        return float(q)

    def run(self, n_equil=500, n_measure=1000, measure_every=2):
        """
        Run parallel tempering simulation.
        Returns overlap measurements at each temperature.
        """
        # Equilibration
        for step in range(n_equil):
            for t_idx in range(self.n_temps):
                beta = 1.0 / self.temps[t_idx]
                self._metropolis_sweep(self.spins_a[t_idx], beta)
                self._metropolis_sweep(self.spins_b[t_idx], beta)
            if step % 3 == 0:
                self._replica_exchange()

        # Measurement
        overlaps = {t_idx: [] for t_idx in range(self.n_temps)}

        for step in range(n_measure * measure_every):
            for t_idx in range(self.n_temps):
                beta = 1.0 / self.temps[t_idx]
                self._metropolis_sweep(self.spins_a[t_idx], beta)
                self._metropolis_sweep(self.spins_b[t_idx], beta)

            if step % 3 == 0:
                self._replica_exchange()

            if step % measure_every == 0:
                for t_idx in range(self.n_temps):
                    q = self.compute_overlap(t_idx)
                    overlaps[t_idx].append(q)

        return overlaps


def generate_disorder(L, rng, distribution='bimodal'):
    """Generate random couplings J_ij for one disorder realization."""
    if distribution == 'bimodal':
        J = rng.choice([-1, 1], size=(L, L, L, 3)).astype(np.int8)
    else:  # Gaussian
        J = rng.randn(L, L, L, 3).astype(np.float64)
    return J


def compute_sg_observables(overlaps_list):
    """
    From a list of overlap arrays (one per disorder sample),
    compute the disorder-averaged spin-glass Binder cumulant and susceptibility.

    g = 0.5 * (3 - [<q^4>] / [<q^2>]^2)

    where <...> is thermal average and [...] is disorder average.
    """
    q2_samples = []
    q4_samples = []

    for overlaps in overlaps_list:
        q_arr = np.array(overlaps)
        q2 = np.mean(q_arr ** 2)  # thermal average of q^2
        q4 = np.mean(q_arr ** 4)  # thermal average of q^4
        q2_samples.append(q2)
        q4_samples.append(q4)

    q2_avg = np.mean(q2_samples)  # disorder average
    q4_avg = np.mean(q4_samples)

    # Binder cumulant for spin glass
    if q2_avg > 1e-15:
        g = 0.5 * (3.0 - q4_avg / (q2_avg ** 2))
    else:
        g = 0.0

    # Spin-glass susceptibility
    chi_sg = len(overlaps_list[0]) * q2_avg if overlaps_list else 0.0

    # Bootstrap error estimate on g
    n_boot = 200
    rng_boot = np.random.RandomState(42)
    g_boots = []
    n_dis = len(q2_samples)
    for _ in range(n_boot):
        idx = rng_boot.randint(0, n_dis, n_dis)
        q2_b = np.mean([q2_samples[i] for i in idx])
        q4_b = np.mean([q4_samples[i] for i in idx])
        if q2_b > 1e-15:
            g_boots.append(0.5 * (3.0 - q4_b / (q2_b ** 2)))
    g_err = np.std(g_boots) if g_boots else 0.0

    return {
        'g': float(g),
        'g_err': float(g_err),
        'q2_avg': float(q2_avg),
        'q4_avg': float(q4_avg),
        'chi_sg': float(chi_sg),
        'n_disorder': n_dis,
    }


# ═══════════════════════════════════════════════════════════════
# ZERO-FIELD CALIBRATION CHECKPOINT
# ═══════════════════════════════════════════════════════════════

def run_calibration(L=8, n_disorder=50, n_equil=400, n_measure=800):
    """
    Calibration: zero-field (h=0) Binder cumulant crossing to verify T_c ~ 1.102.
    Run at L=4, 6, 8 and find crossing.
    """
    print("=" * 70)
    print("CALIBRATION CHECKPOINT: Zero-field T_c verification")
    print("=" * 70)

    temps_scan = np.linspace(0.7, 1.5, 16)
    # Parallel tempering temperature ladder for equilibration
    pt_temps = np.linspace(0.5, 2.0, 16)

    results = {}

    for L_cal in [4, 6, 8]:
        print(f"\n  L = {L_cal}:")
        results[L_cal] = {}

        for T_target in temps_scan:
            # Find closest PT temperature index
            t_idx = np.argmin(np.abs(pt_temps - T_target))

            all_overlaps = []
            n_dis = n_disorder if L_cal <= 6 else max(30, n_disorder)

            for sample in range(n_dis):
                rng = np.random.RandomState(1000 * L_cal + sample)
                J = generate_disorder(L_cal, rng, 'bimodal')

                sim = EASpinGlass3D(
                    L=L_cal, h=0.0, temperatures=pt_temps,
                    couplings=J, seed=2000 * L_cal + sample
                )
                overlaps = sim.run(
                    n_equil=n_equil,
                    n_measure=n_measure,
                    measure_every=2
                )
                all_overlaps.append(overlaps[t_idx])

            obs = compute_sg_observables(all_overlaps)
            results[L_cal][float(T_target)] = obs
            print(f"    T={T_target:.3f}: g={obs['g']:.4f} ± {obs['g_err']:.4f}")

    # Find crossings
    print("\n  Crossing analysis (h=0):")
    L_pairs = [(4, 6), (6, 8), (4, 8)]
    crossings_found = []

    for L1, L2 in L_pairs:
        temps_sorted = sorted(results[L1].keys())
        for i in range(len(temps_sorted) - 1):
            T_lo = temps_sorted[i]
            T_hi = temps_sorted[i + 1]
            g1_lo = results[L1][T_lo]['g']
            g1_hi = results[L1][T_hi]['g']
            g2_lo = results[L2][T_lo]['g']
            g2_hi = results[L2][T_hi]['g']

            diff_lo = g1_lo - g2_lo
            diff_hi = g1_hi - g2_hi

            if diff_lo * diff_hi < 0:  # sign change = crossing
                # Linear interpolation
                frac = diff_lo / (diff_lo - diff_hi)
                T_cross = T_lo + frac * (T_hi - T_lo)
                crossings_found.append((L1, L2, T_cross))
                print(f"    L={L1}/{L2} crossing at T* ≈ {T_cross:.3f}")

    if crossings_found:
        avg_Tc = np.mean([c[2] for c in crossings_found])
        print(f"\n  Average crossing T_c ≈ {avg_Tc:.3f}")
        print(f"  Expected T_c = 1.102")
        print(f"  Deviation: {abs(avg_Tc - 1.102) / 1.102 * 100:.1f}%")
        cal_pass = abs(avg_Tc - 1.102) / 1.102 < 0.15  # 15% tolerance for small L
        print(f"  Calibration {'PASS' if cal_pass else 'WARNING - large deviation'}")
    else:
        print("  WARNING: No clear crossings found in calibration scan")
        cal_pass = False

    return results, crossings_found, cal_pass


# ═══════════════════════════════════════════════════════════════
# AT LINE PROBE: FIELD SCANS
# ═══════════════════════════════════════════════════════════════

def run_at_line_scan(h=0.1, L_values=None, n_disorder=50, n_equil=500, n_measure=1000):
    """
    Scan Binder cumulant g(L, T, h) for fixed h across temperatures.
    Look for L-dependent crossings to detect AT line.
    """
    if L_values is None:
        L_values = [4, 6, 8]

    print(f"\n{'=' * 70}")
    print(f"AT LINE SCAN: h = {h}")
    print(f"{'=' * 70}")

    # Temperature scan: focus on region below T_c(h=0) = 1.102
    temps_scan = np.linspace(0.5, 1.2, 14)

    # PT ladder spans wider range for good mixing
    pt_temps = np.linspace(0.4, 1.8, 20)

    results = {}

    for L in L_values:
        print(f"\n  L = {L}:")
        results[L] = {}

        n_dis = n_disorder
        if L >= 10:
            n_dis = max(30, n_disorder // 2)

        for T_target in temps_scan:
            t_idx = np.argmin(np.abs(pt_temps - T_target))

            all_overlaps = []
            t_start = time.time()

            for sample in range(n_dis):
                rng = np.random.RandomState(5000 * L + 100 * int(h * 100) + sample)
                J = generate_disorder(L, rng, 'bimodal')

                sim = EASpinGlass3D(
                    L=L, h=h, temperatures=pt_temps,
                    couplings=J, seed=6000 * L + 100 * int(h * 100) + sample
                )
                overlaps = sim.run(
                    n_equil=n_equil,
                    n_measure=n_measure,
                    measure_every=2
                )
                all_overlaps.append(overlaps[t_idx])

            obs = compute_sg_observables(all_overlaps)
            results[L][float(T_target)] = obs

            elapsed = time.time() - t_start
            print(f"    T={T_target:.3f}: g={obs['g']:.4f} ± {obs['g_err']:.4f}  "
                  f"q2={obs['q2_avg']:.4f}  [{elapsed:.1f}s]")

    return results


def find_crossings_and_drift(results, h):
    """
    Analyze crossing temperatures T*(L1, L2, h) and determine drift direction.
    This is the KEY diagnostic for AT line existence.
    """
    print(f"\n{'=' * 70}")
    print(f"CROSSING & DRIFT ANALYSIS: h = {h}")
    print(f"{'=' * 70}")

    L_values = sorted(results.keys())
    crossings = {}

    for i in range(len(L_values)):
        for j in range(i + 1, len(L_values)):
            L1, L2 = L_values[i], L_values[j]
            temps_sorted = sorted(results[L1].keys())

            for k in range(len(temps_sorted) - 1):
                T_lo = temps_sorted[k]
                T_hi = temps_sorted[k + 1]

                if T_lo not in results[L2] or T_hi not in results[L2]:
                    continue

                g1_lo = results[L1][T_lo]['g']
                g1_hi = results[L1][T_hi]['g']
                g2_lo = results[L2][T_lo]['g']
                g2_hi = results[L2][T_hi]['g']

                diff_lo = g1_lo - g2_lo
                diff_hi = g1_hi - g2_hi

                if diff_lo * diff_hi < 0:
                    frac = diff_lo / (diff_lo - diff_hi)
                    T_cross = T_lo + frac * (T_hi - T_lo)
                    crossings[(L1, L2)] = T_cross
                    print(f"  L={L1}/{L2}: T*(h={h}) ≈ {T_cross:.4f}")

    # Drift analysis
    print(f"\n  Drift analysis:")
    if len(crossings) >= 2:
        # Compare crossings involving successively larger L
        cross_list = sorted(crossings.items(), key=lambda x: x[0][1])
        for (L1, L2), T_cross in cross_list:
            print(f"    ({L1},{L2}): T* = {T_cross:.4f}")

        # Key test: does T* drift toward 0 or stabilize at finite T?
        if (4, 6) in crossings and (4, 8) in crossings:
            drift_46_to_48 = crossings[(4, 8)] - crossings[(4, 6)]
            print(f"\n  T*(4,8) - T*(4,6) = {drift_46_to_48:.4f}")
            if drift_46_to_48 < -0.05:
                print(f"  → Drift DOWNWARD: T* decreasing with L (droplet-like)")
                drift_dir = "downward"
            elif drift_46_to_48 > 0.05:
                print(f"  → Drift UPWARD: T* increasing with L")
                drift_dir = "upward"
            else:
                print(f"  → Drift STABLE: T* approximately constant (AT-line-like)")
                drift_dir = "stable"
        elif (6, 8) in crossings:
            print(f"  Only (6,8) crossing found at T* = {crossings[(6,8)]:.4f}")
            drift_dir = "insufficient_data"
        else:
            drift_dir = "insufficient_data"
    else:
        drift_dir = "no_crossings"
        print(f"  Fewer than 2 crossings found — cannot determine drift")

    return crossings, drift_dir


# ═══════════════════════════════════════════════════════════════
# ADDITIONAL OBSERVABLE: OVERLAP DISTRIBUTION P(q)
# ═══════════════════════════════════════════════════════════════

def compute_overlap_distribution(all_overlaps, n_bins=50):
    """
    Compute the disorder-averaged overlap distribution P(q).
    RSB prediction: broad P(q) with non-trivial support between q_EA and 1.
    Droplet prediction: P(q) collapses to two peaks at ±q_EA.
    """
    all_q = []
    for overlaps in all_overlaps:
        all_q.extend(overlaps)

    all_q = np.array(all_q)
    hist, bin_edges = np.histogram(all_q, bins=n_bins, range=(-1, 1), density=True)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    # Width of P(q) around peaks — wider = more RSB-like
    # Use interquartile range of |q|
    abs_q = np.abs(all_q)
    q_median = np.median(abs_q)
    q_iqr = np.percentile(abs_q, 75) - np.percentile(abs_q, 25)

    return {
        'bin_centers': bin_centers.tolist(),
        'histogram': hist.tolist(),
        'q_median': float(q_median),
        'q_iqr': float(q_iqr),
        'q_mean_abs': float(np.mean(abs_q)),
    }


# ═══════════════════════════════════════════════════════════════
# LINK OVERLAP (new observable not in prior rounds)
# ═══════════════════════════════════════════════════════════════

def compute_link_overlap_from_sim(sim, temp_idx):
    """
    Link overlap: q_l = (1/N_bonds) sum_{<ij>} sigma_i^a sigma_j^a * sigma_i^b sigma_j^b
    More sensitive to AT line than spin overlap in some analyses.
    """
    L = sim.L
    sa = sim.spins_a[temp_idx].astype(np.float64)
    sb = sim.spins_b[temp_idx].astype(np.float64)

    # Bond products for replica a
    bond_a_x = sa * np.roll(sa, -1, axis=0)
    bond_a_y = sa * np.roll(sa, -1, axis=1)
    bond_a_z = sa * np.roll(sa, -1, axis=2)

    # Bond products for replica b
    bond_b_x = sb * np.roll(sb, -1, axis=0)
    bond_b_y = sb * np.roll(sb, -1, axis=1)
    bond_b_z = sb * np.roll(sb, -1, axis=2)

    # Link overlap
    ql = np.mean(bond_a_x * bond_b_x + bond_a_y * bond_b_y + bond_a_z * bond_b_z) / 3.0
    return float(ql)


# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Relay Chain v2 — Round 1 — Agent 1 (Conjecture Agent)     ║")
    print("║  3D Edwards-Anderson ±J Spin Glass                         ║")
    print("║  Target: AT Line Existence via Binder Cumulant Drift       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # ───────────────────────────────────────────
    # PRE-REGISTRATION (committed before any computation)
    # ───────────────────────────────────────────
    pre_reg = {
        'Agent_ID': 'Agent-1-Conjecture',
        'Round': 1,
        'Prediction': 'Yes — the AT line exists in d=3',
        'Predicted_observable': (
            'Binder cumulant g(L,T,h=0.1) for L in {4,6,8} shows crossings '
            'at T*(L) > 0 that do NOT drift to zero as L increases'
        ),
        'Predicted_direction': (
            'Binder cumulant crossing T*(L1,L2) remains approximately stable '
            'or drifts only weakly downward (|ΔT*| < 0.1) between L=4/6 and L=4/8 pairs'
        ),
        'Falsification_condition': (
            'If T*(4,8) - T*(4,6) < -0.15, indicating systematic downward drift '
            'toward T*=0, the AT line existence prediction is falsified for these sizes'
        ),
        'Committed': 'Yes'
    }

    print("PRE-REGISTRATION BLOCK (committed before any computation):")
    print("-" * 60)
    for k, v in pre_reg.items():
        print(f"  {k}: {v}")
    print("-" * 60)
    print()

    all_results = {}

    # ───────────────────────────────────────────
    # PHASE 1: Zero-field calibration
    # ───────────────────────────────────────────
    print("\n" + "=" * 70)
    print("PHASE 1: ZERO-FIELD CALIBRATION")
    print("=" * 70)

    t0 = time.time()
    cal_results, cal_crossings, cal_pass = run_calibration(
        L=8, n_disorder=50, n_equil=300, n_measure=600
    )
    cal_time = time.time() - t0
    print(f"\nCalibration completed in {cal_time:.1f}s")
    all_results['calibration'] = {
        'results': {str(L): {str(T): v for T, v in Tdict.items()}
                    for L, Tdict in cal_results.items()},
        'crossings': [(L1, L2, float(Tc)) for L1, L2, Tc in cal_crossings],
        'passed': cal_pass
    }

    if not cal_pass:
        print("\n⚠ WARNING: Calibration deviation above 15%. Proceeding with caution.")
        print("  (Small-L deviations are expected; signal is the TREND, not the absolute value)")

    # ───────────────────────────────────────────
    # PHASE 2: AT line scan at h = 0.1
    # ───────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("PHASE 2: AT LINE SCAN (h = 0.1)")
    print("=" * 70)

    t1 = time.time()
    field_results_01 = run_at_line_scan(
        h=0.1, L_values=[4, 6, 8],
        n_disorder=50, n_equil=400, n_measure=800
    )
    scan_time_01 = time.time() - t1
    print(f"\nh=0.1 scan completed in {scan_time_01:.1f}s")

    crossings_01, drift_01 = find_crossings_and_drift(field_results_01, h=0.1)

    all_results['h01'] = {
        'results': {str(L): {str(T): v for T, v in Tdict.items()}
                    for L, Tdict in field_results_01.items()},
        'crossings': {f"{L1},{L2}": float(Tc) for (L1, L2), Tc in crossings_01.items()},
        'drift_direction': drift_01
    }

    # ───────────────────────────────────────────
    # PHASE 3: AT line scan at h = 0.05 (weaker field)
    # ───────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("PHASE 3: AT LINE SCAN (h = 0.05)")
    print("=" * 70)

    t2 = time.time()
    field_results_005 = run_at_line_scan(
        h=0.05, L_values=[4, 6, 8],
        n_disorder=50, n_equil=400, n_measure=800
    )
    scan_time_005 = time.time() - t2
    print(f"\nh=0.05 scan completed in {scan_time_005:.1f}s")

    crossings_005, drift_005 = find_crossings_and_drift(field_results_005, h=0.05)

    all_results['h005'] = {
        'results': {str(L): {str(T): v for T, v in Tdict.items()}
                    for L, Tdict in field_results_005.items()},
        'crossings': {f"{L1},{L2}": float(Tc) for (L1, L2), Tc in crossings_005.items()},
        'drift_direction': drift_005
    }

    # ───────────────────────────────────────────
    # PHASE 4: P(q) overlap distribution at select (T, h) points
    # ───────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("PHASE 4: OVERLAP DISTRIBUTION P(q) AT KEY POINTS")
    print("=" * 70)

    # Run targeted simulations for P(q) at a few critical points
    pt_temps = np.linspace(0.4, 1.8, 20)
    pq_results = {}

    for L_pq in [4, 8]:
        for T_pq in [0.7, 0.9]:
            t_idx = np.argmin(np.abs(pt_temps - T_pq))
            all_overlaps = []

            for sample in range(50):
                rng = np.random.RandomState(9000 * L_pq + sample)
                J = generate_disorder(L_pq, rng, 'bimodal')
                sim = EASpinGlass3D(
                    L=L_pq, h=0.1, temperatures=pt_temps,
                    couplings=J, seed=9500 * L_pq + sample
                )
                overlaps = sim.run(n_equil=400, n_measure=800, measure_every=2)
                all_overlaps.append(overlaps[t_idx])

            pq = compute_overlap_distribution(all_overlaps)
            key = f"L{L_pq}_T{T_pq:.1f}_h0.1"
            pq_results[key] = pq
            print(f"  {key}: <|q|>={pq['q_mean_abs']:.4f}, IQR={pq['q_iqr']:.4f}, "
                  f"median|q|={pq['q_median']:.4f}")

    all_results['pq'] = pq_results

    # ───────────────────────────────────────────
    # PHASE 5: Link overlap at key points (new observable)
    # ───────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("PHASE 5: LINK OVERLAP q_l AT KEY POINTS")
    print("=" * 70)

    ql_results = {}
    for L_ql in [4, 6, 8]:
        for T_ql in [0.7, 0.9, 1.0]:
            t_idx = np.argmin(np.abs(pt_temps - T_ql))
            ql_samples = []

            for sample in range(40):
                rng = np.random.RandomState(7000 * L_ql + sample)
                J = generate_disorder(L_ql, rng, 'bimodal')
                sim = EASpinGlass3D(
                    L=L_ql, h=0.1, temperatures=pt_temps,
                    couplings=J, seed=7500 * L_ql + sample
                )
                sim.run(n_equil=300, n_measure=200, measure_every=2)
                ql = compute_link_overlap_from_sim(sim, t_idx)
                ql_samples.append(ql)

            ql_avg = np.mean(ql_samples)
            ql_std = np.std(ql_samples) / np.sqrt(len(ql_samples))
            key = f"L{L_ql}_T{T_ql:.1f}"
            ql_results[key] = {'ql': float(ql_avg), 'ql_err': float(ql_std)}
            print(f"  {key}: q_l = {ql_avg:.4f} ± {ql_std:.4f}")

    all_results['link_overlap'] = ql_results

    # ───────────────────────────────────────────
    # SUMMARY
    # ───────────────────────────────────────────
    total_time = time.time() - t0
    print(f"\n\n{'=' * 70}")
    print(f"TOTAL RUNTIME: {total_time:.1f}s")
    print(f"{'=' * 70}")

    print("\n\nSUMMARY OF DRIFT ANALYSIS:")
    print(f"  h=0.10: drift = {drift_01}")
    print(f"  h=0.05: drift = {drift_005}")

    if crossings_01:
        print(f"\n  h=0.1 crossings:")
        for (L1, L2), Tc in sorted(crossings_01.items()):
            print(f"    L={L1}/{L2}: T* = {Tc:.4f}")

    if crossings_005:
        print(f"\n  h=0.05 crossings:")
        for (L1, L2), Tc in sorted(crossings_005.items()):
            print(f"    L={L1}/{L2}: T* = {Tc:.4f}")

    # Save all results
    serializable_results = json.loads(json.dumps(all_results, default=str))
    with open('relay_v2_round1_results.json', 'w') as f:
        json.dump(serializable_results, f, indent=2)
    print("\nResults saved to relay_v2_round1_results.json")

    return all_results


if __name__ == '__main__':
    results = main()
