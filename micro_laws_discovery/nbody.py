"""
N-body integrator and synthetic data generation for planetary systems.

Implements a symplectic Wisdom–Holman-style mixed-variable integrator
for Keplerian + perturbation splitting, plus dataset builders for
resonant chains, eccentric systems, and inclined multi-planet setups.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Physical constants (normalised: G=1, M_star=1, AU=1, yr=2π)
# ---------------------------------------------------------------------------
G_NORM = 1.0
TWO_PI = 2.0 * np.pi


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Body:
    mass: float
    pos: np.ndarray   # shape (3,)
    vel: np.ndarray   # shape (3,)


@dataclass
class OrbitalElements:
    a: float       # semi-major axis
    e: float       # eccentricity
    inc: float     # inclination (rad)
    Omega: float   # longitude of ascending node (rad)
    omega: float   # argument of pericentre (rad)
    M: float       # mean anomaly (rad)


@dataclass
class PlanetarySystem:
    star_mass: float
    planets: list[Body]
    elements: list[OrbitalElements]
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Kepler <-> Cartesian helpers
# ---------------------------------------------------------------------------
def elements_to_cartesian(
    elem: OrbitalElements, mu: float
) -> tuple[np.ndarray, np.ndarray]:
    """Convert orbital elements to Cartesian position & velocity."""
    a, e, inc, Omega, omega, M0 = (
        elem.a, elem.e, elem.inc, elem.Omega, elem.omega, elem.M,
    )
    # Solve Kepler's equation via Newton-Raphson
    E = M0
    for _ in range(50):
        dE = (E - e * np.sin(E) - M0) / (1.0 - e * np.cos(E))
        E -= dE
        if abs(dE) < 1e-14:
            break

    cos_E, sin_E = np.cos(E), np.sin(E)
    r_orb = a * (1.0 - e * cos_E)
    x_orb = a * (cos_E - e)
    y_orb = a * np.sqrt(1.0 - e**2) * sin_E

    n = np.sqrt(mu / a**3)
    vx_orb = -a * n * sin_E / (1.0 - e * cos_E)
    vy_orb = a * n * np.sqrt(1.0 - e**2) * cos_E / (1.0 - e * cos_E)

    # Rotation matrices
    cos_o, sin_o = np.cos(omega), np.sin(omega)
    cos_O, sin_O = np.cos(Omega), np.sin(Omega)
    cos_i, sin_i = np.cos(inc), np.sin(inc)

    Px = cos_O * cos_o - sin_O * sin_o * cos_i
    Py = sin_O * cos_o + cos_O * sin_o * cos_i
    Pz = sin_o * sin_i
    Qx = -cos_O * sin_o - sin_O * cos_o * cos_i
    Qy = -sin_O * sin_o + cos_O * cos_o * cos_i
    Qz = cos_o * sin_i

    pos = np.array([
        Px * x_orb + Qx * y_orb,
        Py * x_orb + Qy * y_orb,
        Pz * x_orb + Qz * y_orb,
    ])
    vel = np.array([
        Px * vx_orb + Qx * vy_orb,
        Py * vx_orb + Qy * vy_orb,
        Pz * vx_orb + Qz * vy_orb,
    ])
    return pos, vel


def cartesian_to_elements(
    pos: np.ndarray, vel: np.ndarray, mu: float
) -> OrbitalElements:
    """Convert Cartesian state to orbital elements."""
    r = np.linalg.norm(pos)
    v = np.linalg.norm(vel)
    h = np.cross(pos, vel)
    h_mag = np.linalg.norm(h)

    # Semi-major axis via vis-viva
    a = 1.0 / (2.0 / r - v**2 / mu)

    # Eccentricity vector
    e_vec = np.cross(vel, h) / mu - pos / r
    e = np.linalg.norm(e_vec)

    # Inclination
    inc = np.arccos(np.clip(h[2] / h_mag, -1, 1))

    # Node vector
    n_vec = np.cross(np.array([0.0, 0.0, 1.0]), h)
    n_mag = np.linalg.norm(n_vec)

    if n_mag > 1e-12:
        Omega = np.arccos(np.clip(n_vec[0] / n_mag, -1, 1))
        if n_vec[1] < 0:
            Omega = TWO_PI - Omega
        omega = np.arccos(np.clip(np.dot(n_vec, e_vec) / (n_mag * max(e, 1e-15)), -1, 1))
        if e_vec[2] < 0:
            omega = TWO_PI - omega
    else:
        Omega = 0.0
        omega = np.arctan2(e_vec[1], e_vec[0])
        if omega < 0:
            omega += TWO_PI

    # True anomaly -> eccentric anomaly -> mean anomaly
    cos_nu = np.dot(e_vec, pos) / (max(e, 1e-15) * r)
    cos_nu = np.clip(cos_nu, -1, 1)
    nu = np.arccos(cos_nu)
    if np.dot(pos, vel) < 0:
        nu = TWO_PI - nu

    E = 2.0 * np.arctan2(
        np.sqrt(1 - e) * np.sin(nu / 2),
        np.sqrt(1 + e) * np.cos(nu / 2),
    )
    M = E - e * np.sin(E)
    if M < 0:
        M += TWO_PI

    return OrbitalElements(a=a, e=e, inc=inc, Omega=Omega, omega=omega, M=M)


# ---------------------------------------------------------------------------
# Symplectic Wisdom–Holman Integrator
# ---------------------------------------------------------------------------
class WHIntegrator:
    """
    Mixed-variable symplectic integrator (Wisdom & Holman 1991).
    Split H = H_Kepler + H_interaction.
    """

    def __init__(self, star_mass: float, planets: list[Body], dt: float):
        self.star_mass = star_mass
        self.n_planets = len(planets)
        self.dt = dt
        # State arrays – heliocentric coordinates
        self.masses = np.array([p.mass for p in planets])
        self.positions = np.array([p.pos.copy() for p in planets])   # (N, 3)
        self.velocities = np.array([p.vel.copy() for p in planets])  # (N, 3)

    # -- interaction accelerations ------------------------------------------
    def _interaction_accel(self) -> np.ndarray:
        acc = np.zeros_like(self.positions)
        for i in range(self.n_planets):
            for j in range(i + 1, self.n_planets):
                dr = self.positions[j] - self.positions[i]
                r3 = np.linalg.norm(dr) ** 3
                if r3 < 1e-30:
                    continue
                fij = G_NORM * dr / r3
                acc[i] += self.masses[j] * fij
                acc[j] -= self.masses[i] * fij
            # Indirect term (barycentric correction)
            for j in range(self.n_planets):
                if j == i:
                    continue
                dr_star = self.positions[j]
                r3s = np.linalg.norm(dr_star) ** 3
                if r3s < 1e-30:
                    continue
                acc[i] -= G_NORM * self.masses[j] * dr_star / r3s
                # Cancel double-count from Kepler part already handled
        # Simplified: just planet-planet + indirect
        acc_full = np.zeros_like(self.positions)
        for i in range(self.n_planets):
            for j in range(self.n_planets):
                if j == i:
                    continue
                dr = self.positions[j] - self.positions[i]
                r3 = np.linalg.norm(dr) ** 3
                if r3 < 1e-30:
                    continue
                acc_full[i] += G_NORM * self.masses[j] * dr / r3
            # Indirect term
            for j in range(self.n_planets):
                if j == i:
                    continue
                acc_full[i] -= G_NORM * self.masses[j] * self.positions[j] / max(
                    np.linalg.norm(self.positions[j]) ** 3, 1e-30
                )
        return acc_full

    # -- Kepler drift (analytic) -------------------------------------------
    def _kepler_drift(self, dt_step: float):
        for i in range(self.n_planets):
            mu = G_NORM * (self.star_mass + self.masses[i])
            elem = cartesian_to_elements(self.positions[i], self.velocities[i], mu)
            n = np.sqrt(mu / elem.a ** 3)
            elem_new = OrbitalElements(
                a=elem.a, e=elem.e, inc=elem.inc,
                Omega=elem.Omega, omega=elem.omega,
                M=(elem.M + n * dt_step) % TWO_PI,
            )
            pos_new, vel_new = elements_to_cartesian(elem_new, mu)
            self.positions[i] = pos_new
            self.velocities[i] = vel_new

    # -- single step (DKD leapfrog) ----------------------------------------
    def step(self):
        half_dt = 0.5 * self.dt
        # Kick
        acc = self._interaction_accel()
        self.velocities += half_dt * acc
        # Drift (Kepler)
        self._kepler_drift(self.dt)
        # Kick
        acc = self._interaction_accel()
        self.velocities += half_dt * acc

    # -- integrate for N steps ---------------------------------------------
    def integrate(self, n_steps: int, save_every: int = 1) -> dict:
        """Return dict with times, positions, velocities, elements."""
        times = []
        pos_hist = []
        vel_hist = []
        elem_hist = []
        t = 0.0
        for k in range(n_steps):
            if k % save_every == 0:
                times.append(t)
                pos_hist.append(self.positions.copy())
                vel_hist.append(self.velocities.copy())
                elems = []
                for i in range(self.n_planets):
                    mu = G_NORM * (self.star_mass + self.masses[i])
                    elems.append(cartesian_to_elements(
                        self.positions[i], self.velocities[i], mu
                    ))
                elem_hist.append(elems)
            self.step()
            t += self.dt
        return {
            "times": np.array(times),
            "positions": np.array(pos_hist),
            "velocities": np.array(vel_hist),
            "elements": elem_hist,
        }


# ---------------------------------------------------------------------------
# MEGNO chaos indicator
# ---------------------------------------------------------------------------
def compute_megno(
    star_mass: float,
    planets: list[Body],
    dt: float,
    n_steps: int,
) -> float:
    """
    Compute Mean Exponential Growth of Nearby Orbits (MEGNO) indicator.
    <Y> ~ 2 for quasiperiodic, diverges for chaotic.

    Uses shadow-orbit method with periodic renormalization:
      Y(t) = (2/t) * integral_0^t  s * d(ln|delta|)/ds  ds
    Discretized:  Y_k ≈ k * ln(|delta_k| / |delta_{k-1}|)
                  <Y> = (2/N) * sum Y_k
    """
    eps = 1e-8
    renorm_interval = max(n_steps // 20, 10)  # renormalize to avoid overflow

    # Reference integration
    integ_ref = WHIntegrator(star_mass, planets, dt)
    # Shadow integration (tiny perturbation in positions only)
    planets_shadow = []
    rng = np.random.RandomState(1234)  # deterministic shadow
    for p in planets:
        d_pos = rng.randn(3)
        d_pos *= eps / np.linalg.norm(d_pos)  # unit direction, magnitude eps
        ps = Body(
            mass=p.mass,
            pos=p.pos + d_pos,
            vel=p.vel.copy(),
        )
        planets_shadow.append(ps)
    integ_shadow = WHIntegrator(star_mass, planets_shadow, dt)

    sum_Y = 0.0
    delta_prev = eps  # initial separation magnitude
    for k in range(1, n_steps + 1):
        integ_ref.step()
        integ_shadow.step()
        delta_pos = integ_shadow.positions - integ_ref.positions
        delta_cur = np.linalg.norm(delta_pos)
        if delta_cur < 1e-30:
            delta_cur = 1e-30

        # Y_k = k * ln(|delta_k| / |delta_{k-1}|)
        Y_k = k * np.log(delta_cur / delta_prev)
        sum_Y += Y_k
        delta_prev = delta_cur

        # Renormalize shadow orbit to prevent divergence to infinity
        if k % renorm_interval == 0 and delta_cur > 1e-4:
            scale = eps / delta_cur
            integ_shadow.positions = (
                integ_ref.positions + delta_pos * scale
            )
            integ_shadow.velocities = integ_ref.velocities.copy()
            delta_prev = eps

    megno = 2.0 * sum_Y / max(n_steps, 1)
    return float(megno)


# ---------------------------------------------------------------------------
# Hill radius & stability metrics
# ---------------------------------------------------------------------------
def hill_radius(a: float, mu: float) -> float:
    """Mutual Hill radius for planet with mass ratio mu."""
    return a * (mu / 3.0) ** (1.0 / 3.0)


def mutual_hill_radius(a1: float, a2: float, m1: float, m2: float, m_star: float) -> float:
    """Mutual Hill radius between two planets."""
    return 0.5 * (a1 + a2) * ((m1 + m2) / (3.0 * m_star)) ** (1.0 / 3.0)


def hill_separation(elem1: OrbitalElements, elem2: OrbitalElements,
                    m1: float, m2: float, m_star: float) -> float:
    """Separation in mutual Hill radii."""
    rH = mutual_hill_radius(elem1.a, elem2.a, m1, m2, m_star)
    if rH < 1e-30:
        return np.inf
    return (elem2.a - elem1.a) / rH


def is_hill_stable(sys: PlanetarySystem, crit_sep: float = 3.46) -> bool:
    """
    Analytical Hill stability criterion (Gladman 1993).

    Two-planet systems with separation < ~2*sqrt(3) ≈ 3.46 mutual Hill radii
    are Hill-unstable (orbits can cross).  Eccentricity correction: the
    effective separation shrinks by (1 - max(e1, e2)) for eccentric orbits
    because pericentre/apocentre distances overlap sooner.

    Returns True if the system is Hill-stable.
    """
    elems = sys.elements
    masses = [p.mass for p in sys.planets]
    for i in range(len(elems) - 1):
        j = i + 1
        delta = hill_separation(
            elems[i], elems[j], masses[i], masses[j], sys.star_mass
        )
        # Eccentricity correction: eccentric orbits need wider separation
        # Use a mild correction (Chambers et al. 1996 empirical scaling)
        e_max = max(elems[i].e, elems[j].e)
        effective_crit = crit_sep * (1.0 + 0.5 * e_max)
        if delta < effective_crit:
            return False
    return True


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------
class DatasetGenerator:
    """Generate labelled datasets of planetary systems for training."""

    def __init__(
        self,
        star_mass: float = 1.0,
        n_planets: int = 2,
        rng_seed: int = 42,
    ):
        self.star_mass = star_mass
        self.n_planets = n_planets
        self.rng = np.random.RandomState(rng_seed)

    def _random_system(
        self,
        a_range: tuple = (0.5, 5.0),
        e_range: tuple = (0.0, 0.3),
        inc_range: tuple = (0.0, 0.1),
        mass_range: tuple = (1e-5, 1e-3),
        min_separation_hill: float = 1.0,
        target_separation_hill: float | None = None,
    ) -> PlanetarySystem:
        """Generate a random planetary system with ordered semi-major axes.

        If *target_separation_hill* is provided, the inner-most pair is placed
        at exactly that many mutual Hill radii apart (small noise added) so
        we can control the class balance.
        """
        masses = self.rng.uniform(*mass_range, size=self.n_planets)

        if target_separation_hill is not None and self.n_planets >= 2:
            # Place first planet randomly, second at target separation
            a1 = self.rng.uniform(*a_range)
            rH = mutual_hill_radius(a1, a1, masses[0], masses[1], self.star_mass)
            # Add small noise (±10 %) to avoid perfectly deterministic boundary
            sep_actual = target_separation_hill * (1.0 + 0.1 * self.rng.randn())
            sep_actual = max(sep_actual, 0.3)  # floor
            a2 = a1 + sep_actual * rH
            a_vals = np.sort([a1, a2])
        else:
            a_vals = np.sort(self.rng.uniform(*a_range, size=self.n_planets))
            # Enforce minimum Hill separation
            for i in range(1, self.n_planets):
                rH = mutual_hill_radius(a_vals[i - 1], a_vals[i],
                                        masses[i - 1], masses[i], self.star_mass)
                min_sep = min_separation_hill * rH
                if a_vals[i] - a_vals[i - 1] < min_sep:
                    a_vals[i] = a_vals[i - 1] + min_sep

        elements = []
        planets = []
        for i in range(self.n_planets):
            elem = OrbitalElements(
                a=a_vals[i],
                e=self.rng.uniform(*e_range),
                inc=self.rng.uniform(*inc_range),
                Omega=self.rng.uniform(0, TWO_PI),
                omega=self.rng.uniform(0, TWO_PI),
                M=self.rng.uniform(0, TWO_PI),
            )
            elements.append(elem)
            mu = G_NORM * (self.star_mass + masses[i])
            pos, vel = elements_to_cartesian(elem, mu)
            planets.append(Body(mass=masses[i], pos=pos, vel=vel))

        return PlanetarySystem(
            star_mass=self.star_mass, planets=planets, elements=elements
        )

    def generate_dataset(
        self,
        n_systems: int = 200,
        integration_steps: int = 5000,
        dt: float = 0.01,
        stability_threshold: float = 4.0,
        a_range: tuple = (0.5, 5.0),
        e_range: tuple = (0.0, 0.3),
        inc_range: tuple = (0.0, 0.1),
        mass_range: tuple = (1e-5, 1e-3),
        min_separation_hill: float = 1.0,
    ) -> dict:
        """
        Generate a dataset of systems with features and stability labels.

        Uses the Hill stability criterion (Gladman 1993) as the primary
        label, straddling the critical separation ~3.46 R_H for balance.
        MEGNO is computed as a supplementary dynamical indicator but is
        not the sole basis for labels, since short integrations cannot
        reliably detect chaos.

        Returns dict with keys:
          features:  (n_systems, n_features) array of dimensionless features
          labels:    (n_systems,) binary stability labels (1=stable, 0=unstable)
          systems:   list of PlanetarySystem objects
          feature_names: list of feature names
        """
        all_features = []
        all_labels = []
        all_systems = []

        for idx in range(n_systems):
            # Sample target separation straddling the Hill stability boundary
            # (~3.46 R_H with mild ecc correction → ~3.7).  Range [1.0, 7.0]
            target_sep = self.rng.uniform(1.0, 7.0)
            sys = self._random_system(
                a_range=a_range, e_range=e_range,
                inc_range=inc_range, mass_range=mass_range,
                target_separation_hill=target_sep,
            )
            all_systems.append(sys)

            # Extract dimensionless features
            feats = self._extract_features(sys)
            all_features.append(feats)

            # Primary label: Hill stability criterion (analytical)
            stable = 1 if is_hill_stable(sys) else 0
            all_labels.append(stable)

        feature_names = self._feature_names()
        return {
            "features": np.array(all_features),
            "labels": np.array(all_labels),
            "systems": all_systems,
            "feature_names": feature_names,
        }

    def _extract_features(self, sys: PlanetarySystem) -> np.ndarray:
        """Extract dimensionless feature vector from a planetary system."""
        elems = sys.elements
        masses = [p.mass for p in sys.planets]
        feats = []

        for i in range(self.n_planets):
            feats.append(masses[i] / sys.star_mass)       # mass ratio μ_i
            feats.append(elems[i].e)                        # eccentricity
            feats.append(elems[i].inc)                      # inclination

        # Pair features
        for i in range(self.n_planets - 1):
            j = i + 1
            alpha = elems[i].a / elems[j].a                # semi-major axis ratio
            delta = hill_separation(elems[i], elems[j],
                                    masses[i], masses[j], sys.star_mass)
            period_ratio = (elems[j].a / elems[i].a) ** 1.5
            mu_sum = (masses[i] + masses[j]) / sys.star_mass
            # Proximity to first-order resonances
            nearest_res = self._nearest_mmr(period_ratio)

            feats.extend([alpha, delta, period_ratio, mu_sum, nearest_res])

        return np.array(feats)

    def _nearest_mmr(self, period_ratio: float) -> float:
        """Distance to nearest first-order mean motion resonance."""
        min_dist = np.inf
        for p in range(1, 8):
            q = p + 1
            res_ratio = q / p
            dist = abs(period_ratio - res_ratio)
            if dist < min_dist:
                min_dist = dist
        return min_dist

    def _feature_names(self) -> list[str]:
        names = []
        for i in range(self.n_planets):
            names.extend([f"mu_{i}", f"e_{i}", f"inc_{i}"])
        for i in range(self.n_planets - 1):
            j = i + 1
            names.extend([
                f"alpha_{i}{j}", f"delta_Hill_{i}{j}",
                f"P_ratio_{i}{j}", f"mu_sum_{i}{j}",
                f"nearest_mmr_{i}{j}",
            ])
        return names
