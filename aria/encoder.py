"""
Layer 1 — Ramanujan Encoder

Encodes DataObjects using three Ramanujan-specific primitives instead of
generic semantic vectors:

1. Partition Shape Fingerprinting — fit to Meinardus growth form
   f(n) ~ C · n^κ · e^(c·√n), extracting signature (c, κ).
   Objects from different domains with matching signatures → isomorphism candidates.

2. Modular Form Embedding — project sequences onto a basis of modular forms
   (η(τ), theta series, mock theta functions). Maintains an "orphan registry"
   for sequences with strong projection but no known interpretation.

3. Continued Fraction Depth Score — Rogers-Ramanujan depth: how many CF levels
   to represent the object's core identity. Shallow = trivial, moderate = sweet spot,
   deep = lost notebook material.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from .ingestion import DataObject, Domain


@dataclass
class PartitionSignature:
    """Meinardus-class growth signature (c, κ).

    From f(n) ~ C · n^κ · e^(c·√n):
      c  = exponential growth rate
      κ  = polynomial correction exponent
      C  = leading constant (optional)
      L  = selection rule: c²/8 + κ (Paper 14 universality)
      fit_quality = R² of the log-linear regression
    """
    c: float
    kappa: float
    C: float = 1.0
    L: float = 0.0  # c²/8 + κ
    fit_quality: float = 0.0

    def __post_init__(self):
        self.L = self.c ** 2 / 8.0 + self.kappa


@dataclass
class ModularEmbedding:
    """Projection coefficients onto modular form basis."""
    eta_coeff: float = 0.0       # Dedekind eta
    theta_coeff: float = 0.0     # Jacobi theta
    mock_f0_coeff: float = 0.0   # Ramanujan mock theta f₀
    mock_phi_coeff: float = 0.0  # Ramanujan mock theta φ
    residual: float = 1.0        # unexplained variance (1.0 = no fit)
    is_orphan: bool = False       # strong projection, no known interpretation


@dataclass
class CFDepthScore:
    """Rogers-Ramanujan depth score for a continued fraction representation.

    depth 1-2: likely trivial / already known
    depth 3-5: sweet spot — non-obvious, tractable
    depth 6+:  lost notebook material, pending more axioms
    """
    depth: int = 0
    convergents: list[float] = field(default_factory=list)
    convergence_rate: float = 0.0  # how fast the CF converges
    category: str = "unknown"  # trivial / sweet_spot / deep

    def __post_init__(self):
        if self.depth <= 2:
            self.category = "trivial"
        elif self.depth <= 5:
            self.category = "sweet_spot"
        else:
            self.category = "deep"


@dataclass
class EncodedObject:
    """Fully encoded representation of a DataObject through the Ramanujan lens."""
    source: DataObject
    partition_sig: PartitionSignature | None = None
    modular_emb: ModularEmbedding | None = None
    cf_depth: CFDepthScore | None = None

    @property
    def signature_vector(self) -> tuple[float, ...]:
        """Compact numerical vector for distance computations."""
        v = []
        if self.partition_sig:
            v.extend([self.partition_sig.c, self.partition_sig.kappa, self.partition_sig.L])
        else:
            v.extend([0.0, 0.0, 0.0])
        if self.modular_emb:
            v.extend([self.modular_emb.eta_coeff, self.modular_emb.theta_coeff,
                       self.modular_emb.mock_f0_coeff])
        else:
            v.extend([0.0, 0.0, 0.0])
        if self.cf_depth:
            v.extend([float(self.cf_depth.depth), self.cf_depth.convergence_rate])
        else:
            v.extend([0.0, 0.0])
        return tuple(v)


class RamanujanEncoder:
    """Layer 1: Encodes DataObjects using Ramanujan primitives."""

    def __init__(self, precision: int = 50):
        self.precision = precision
        self.encoded: dict[str, EncodedObject] = {}
        self.orphan_registry: list[EncodedObject] = []

    def encode(self, obj: DataObject) -> EncodedObject:
        """Full Ramanujan encoding of a DataObject."""
        psig = self._fit_partition_signature(obj)
        memb = self._compute_modular_embedding(obj)
        cf = self._compute_cf_depth(obj)

        enc = EncodedObject(
            source=obj,
            partition_sig=psig,
            modular_emb=memb,
            cf_depth=cf,
        )
        self.encoded[obj.id] = enc

        # Check for orphan status
        if memb and memb.is_orphan:
            self.orphan_registry.append(enc)

        return enc

    def encode_all(self, objects: list[DataObject]) -> list[EncodedObject]:
        return [self.encode(obj) for obj in objects]

    def _fit_partition_signature(self, obj: DataObject) -> PartitionSignature | None:
        """Fit sequence to Meinardus growth form f(n) ~ C·n^κ·e^(c·√n).

        Method: log-linear regression on log(f(n)) = log(C) + κ·log(n) + c·√n.
        """
        seq = obj.sequence
        if len(seq) < 10:
            return None

        # Filter positive values and indices where n >= 2
        points = [(i, seq[i]) for i in range(2, len(seq)) if seq[i] > 0]
        if len(points) < 5:
            return None

        # Try log-regression: log(f(n)) ≈ a + κ·log(n) + c·√n
        # Use least squares: Y = [1, log(n), √n] · [a, κ, c]ᵀ
        try:
            n_pts = len(points)
            # Build matrices
            A = []
            Y = []
            for n, val in points:
                if val <= 0:
                    continue
                A.append([1.0, math.log(n), math.sqrt(n)])
                Y.append(math.log(val))

            if len(Y) < 5:
                return None

            # Solve via normal equations: (AᵀA)x = AᵀY
            cols = 3
            ATA = [[0.0] * cols for _ in range(cols)]
            ATY = [0.0] * cols
            for i in range(len(Y)):
                for j in range(cols):
                    for k in range(cols):
                        ATA[j][k] += A[i][j] * A[i][k]
                    ATY[j] += A[i][j] * Y[i]

            # Solve 3x3 system via Cramer's rule
            x = _solve_3x3(ATA, ATY)
            if x is None:
                return None

            log_C, kappa, c = x

            # Compute R²
            y_mean = sum(Y) / len(Y)
            ss_tot = sum((y - y_mean) ** 2 for y in Y)
            ss_res = sum(
                (Y[i] - (log_C + kappa * A[i][1] + c * A[i][2])) ** 2
                for i in range(len(Y))
            )
            r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

            return PartitionSignature(
                c=c,
                kappa=kappa,
                C=math.exp(log_C),
                fit_quality=max(0.0, r_sq),
            )
        except (ValueError, OverflowError, ZeroDivisionError):
            return None

    def _compute_modular_embedding(self, obj: DataObject) -> ModularEmbedding | None:
        """Project sequence onto modular form basis functions.

        Pilot: uses correlation with precomputed basis sequences.
        """
        seq = obj.sequence
        if len(seq) < 5:
            return None

        try:
            n = min(len(seq), 100)
            s = seq[:n]

            # Compute basis sequences for comparison
            # η-like: alternating pentagonal number contributions
            eta_basis = self._eta_sequence(n)
            # θ-like: sum of squares representations
            theta_basis = self._theta_sequence(n)
            # mock θ f₀-like: partition with sign alternation
            mock_basis = self._mock_f0_sequence(n)

            # Correlation coefficients
            eta_c = _correlation(s, eta_basis)
            theta_c = _correlation(s, theta_basis)
            mock_c = _correlation(s, mock_basis)

            residual = 1.0 - max(abs(eta_c), abs(theta_c), abs(mock_c))

            # Orphan: strong modular projection but unknown domain
            is_orphan = (
                residual < 0.5
                and obj.domain in (Domain.CUSTOM, Domain.PHYSICS, Domain.BIOLOGY)
            )

            return ModularEmbedding(
                eta_coeff=eta_c,
                theta_coeff=theta_c,
                mock_f0_coeff=mock_c,
                residual=max(0.0, residual),
                is_orphan=is_orphan,
            )
        except (ValueError, ZeroDivisionError):
            return None

    def _compute_cf_depth(self, obj: DataObject) -> CFDepthScore | None:
        """Compute Rogers-Ramanujan depth score.

        Represents the object's characteristic value as a continued fraction
        and measures convergence depth.
        """
        # Use the first value or a characteristic value
        if not obj.sequence:
            return None

        if len(obj.sequence) == 1:
            target = obj.sequence[0]
        else:
            # Use ratio of consecutive terms as characteristic
            ratios = []
            for i in range(1, min(len(obj.sequence), 20)):
                if obj.sequence[i - 1] != 0:
                    ratios.append(obj.sequence[i] / obj.sequence[i - 1])
            if not ratios:
                return None
            target = ratios[-1]  # asymptotic ratio

        if not math.isfinite(target) or target == 0:
            return None

        # Extract continued fraction coefficients
        cf_coeffs = _to_continued_fraction(target, max_depth=20)
        convergents = _cf_convergents(cf_coeffs)

        # Depth = number of coefficients needed for relative error < 1e-10
        depth = len(cf_coeffs)
        for i, conv in enumerate(convergents):
            if abs(target) > 0 and abs(conv - target) / abs(target) < 1e-10:
                depth = i + 1
                break

        # Convergence rate: how fast convergents approach target
        if len(convergents) >= 2 and abs(target) > 0:
            errors = [abs(c - target) / abs(target) for c in convergents if c != target]
            if len(errors) >= 2 and errors[0] > 0:
                rate = -math.log(errors[-1] / errors[0]) / len(errors) if errors[-1] > 0 else 10.0
            else:
                rate = 10.0
        else:
            rate = 0.0

        return CFDepthScore(
            depth=depth,
            convergents=convergents[:10],  # store first 10
            convergence_rate=rate,
        )

    # ── Basis sequence generators ──

    def _eta_sequence(self, n: int) -> list[float]:
        """Dedekind eta-like: Euler's pentagonal number sequence."""
        # p(n) with pentagonal number signs
        seq = [0.0] * n
        for k in range(n):
            # Pentagonal contribution: generalized pentagonal numbers
            val = 0.0
            for j in range(1, k + 1):
                pent = j * (3 * j - 1) // 2
                if pent > k:
                    break
                sign = (-1) ** (j + 1)
                val += sign
            seq[k] = val
        return seq

    def _theta_sequence(self, n: int) -> list[float]:
        """Jacobi theta-like: number of representations as sum of 2 squares."""
        seq = [0.0] * n
        limit = int(math.sqrt(n)) + 1
        for a in range(-limit, limit + 1):
            for b in range(-limit, limit + 1):
                s = a * a + b * b
                if 0 <= s < n:
                    seq[s] += 1.0
        return seq

    def _mock_f0_sequence(self, n: int) -> list[float]:
        """Mock theta f₀-like: partition with alternating restriction."""
        # Partitions into distinct parts (related to mock theta)
        seq = [0.0] * n
        seq[0] = 1.0
        for k in range(1, n):
            for j in range(n - 1, k - 1, -1):
                seq[j] += seq[j - k]
        return seq

    def find_signature_matches(self, threshold: float = 0.1) -> list[tuple[EncodedObject, EncodedObject, float]]:
        """Find pairs of objects from different domains with matching (c, κ) signatures.

        This is the core discovery primitive — two objects from different domains
        with the same Meinardus signature are isomorphism candidates.
        """
        matches = []
        objects = list(self.encoded.values())

        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                a, b = objects[i], objects[j]
                if a.source.domain == b.source.domain:
                    continue  # same domain, skip
                if not a.partition_sig or not b.partition_sig:
                    continue
                if a.partition_sig.fit_quality < 0.5 or b.partition_sig.fit_quality < 0.5:
                    continue  # poor fits, unreliable

                # L-distance (Paper 14 universality)
                L_dist = abs(a.partition_sig.L - b.partition_sig.L)
                if L_dist < threshold:
                    matches.append((a, b, L_dist))

        matches.sort(key=lambda x: x[2])
        return matches

    def get_orphans(self) -> list[EncodedObject]:
        """Return objects with strong modular projection but unknown interpretation."""
        return self.orphan_registry

    def summary(self) -> dict:
        encoded_count = len(self.encoded)
        orphan_count = len(self.orphan_registry)
        sig_count = sum(1 for e in self.encoded.values() if e.partition_sig)
        mod_count = sum(1 for e in self.encoded.values() if e.modular_emb)
        cf_count = sum(1 for e in self.encoded.values() if e.cf_depth)
        sweet_spot = sum(
            1 for e in self.encoded.values()
            if e.cf_depth and e.cf_depth.category == "sweet_spot"
        )
        return {
            "total_encoded": encoded_count,
            "with_partition_sig": sig_count,
            "with_modular_emb": mod_count,
            "with_cf_depth": cf_count,
            "cf_sweet_spot": sweet_spot,
            "orphans": orphan_count,
        }


# ═══════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════

def _solve_3x3(A: list[list[float]], b: list[float]) -> list[float] | None:
    """Solve 3x3 linear system via Cramer's rule."""
    def det3(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))

    D = det3(A)
    if abs(D) < 1e-15:
        return None

    result = []
    for col in range(3):
        M = [row[:] for row in A]
        for row in range(3):
            M[row][col] = b[row]
        result.append(det3(M) / D)
    return result


def _correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient between two sequences."""
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    mx = sum(x[:n]) / n
    my = sum(y[:n]) / n
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sx = math.sqrt(max(0, sum((x[i] - mx) ** 2 for i in range(n))))
    sy = math.sqrt(max(0, sum((y[i] - my) ** 2 for i in range(n))))
    if sx < 1e-15 or sy < 1e-15:
        return 0.0
    return cov / (sx * sy)


def _to_continued_fraction(x: float, max_depth: int = 20) -> list[int]:
    """Convert a real number to its continued fraction representation."""
    if not math.isfinite(x):
        return [0]
    coeffs = []
    val = x
    for _ in range(max_depth):
        a = int(math.floor(val))
        coeffs.append(a)
        frac = val - a
        if abs(frac) < 1e-12:
            break
        val = 1.0 / frac
        if abs(val) > 1e15:
            break
    return coeffs


def _cf_convergents(coeffs: list[int]) -> list[float]:
    """Compute convergents of a continued fraction [a0; a1, a2, ...]."""
    if not coeffs:
        return []
    convergents = []
    h_prev, h_curr = 1, coeffs[0]
    k_prev, k_curr = 0, 1
    convergents.append(h_curr / k_curr if k_curr != 0 else float('inf'))

    for i in range(1, len(coeffs)):
        h_new = coeffs[i] * h_curr + h_prev
        k_new = coeffs[i] * k_curr + k_prev
        if k_new != 0:
            convergents.append(h_new / k_new)
        h_prev, h_curr = h_curr, h_new
        k_prev, k_curr = k_curr, k_new

    return convergents
