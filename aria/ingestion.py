"""
Layer 0 — Knowledge Ingestion

Ingests heterogeneous numerical and structural data, normalising everything
into unified tuples: (sequence, generating_function_hint, domain_tag, uncertainty_score).

Pilot sources:
  - Integer sequences (OEIS-style: hardcoded seed bank + file loading)
  - Physical constants (NIST CODATA subset)
  - Mathematical constants and special values
  - Partition function values
  - Mock theta function evaluations

Each DataObject is the universal currency of ARIA — it sits in a shared
search space regardless of its origin domain.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence


class Domain(Enum):
    """Source domain tags."""
    INTEGER_SEQ = "integer_sequence"
    PHYSICS = "physics"
    MATH_CONST = "math_constant"
    PARTITION = "partition"
    MOCK_THETA = "mock_theta"
    BIOLOGY = "biology"
    FINANCE = "finance"
    MUSIC = "music"
    CUSTOM = "custom"


@dataclass
class DataObject:
    """Universal representation of an ingested object.

    Every object in ARIA lives as this tuple regardless of its origin.
    """
    id: str
    sequence: list[float]  # primary numerical data (finite prefix)
    gf_hint: str | None = None  # generating function hint (symbolic string)
    domain: Domain = Domain.CUSTOM
    uncertainty: float = 0.0  # measurement / truncation uncertainty
    metadata: dict = field(default_factory=dict)
    name: str = ""

    def __post_init__(self):
        if not self.id:
            import hashlib
            raw = f"{self.name}:{self.sequence[:8]}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════
#  SEED DATA BANKS
# ═══════════════════════════════════════════════════════════════════

def _partition_values(n_max: int = 200) -> list[int]:
    """Compute p(0)..p(n_max) via dynamic programming."""
    p = [0] * (n_max + 1)
    p[0] = 1
    for k in range(1, n_max + 1):
        for j in range(k, n_max + 1):
            p[j] += p[j - k]
    return p


def _fibonacci(n: int = 50) -> list[int]:
    fibs = [1, 1]
    for _ in range(n - 2):
        fibs.append(fibs[-1] + fibs[-2])
    return fibs


def _catalan_numbers(n: int = 30) -> list[int]:
    c = [1]
    for k in range(1, n):
        c.append(c[-1] * 2 * (2 * k - 1) // (k + 1))
    return c


def _bell_numbers(n: int = 30) -> list[int]:
    """Bell numbers via Bell triangle."""
    bell = [1]
    row = [1]
    for i in range(1, n):
        new_row = [row[-1]]
        for j in range(1, i + 1):
            new_row.append(new_row[j - 1] + row[j - 1])
        bell.append(new_row[-1])
        row = new_row
    return bell


def _prime_gaps(n: int = 200) -> list[int]:
    """First n prime gaps."""
    from sympy import nextprime
    gaps = []
    p = 2
    for _ in range(n):
        q = nextprime(p)
        gaps.append(q - p)
        p = q
    return gaps


# NIST CODATA 2018 subset — exact or high-precision values
PHYSICAL_CONSTANTS = {
    "speed_of_light": (299792458.0, 0.0, "m/s"),
    "planck_constant": (6.62607015e-34, 0.0, "J·s"),
    "boltzmann": (1.380649e-23, 0.0, "J/K"),
    "avogadro": (6.02214076e23, 0.0, "1/mol"),
    "fine_structure": (7.2973525693e-3, 1.1e-12, ""),
    "electron_mass": (9.1093837015e-31, 2.8e-40, "kg"),
    "proton_mass": (1.67262192369e-27, 5.1e-37, "kg"),
    "gravitational_G": (6.67430e-11, 1.5e-15, "m³/(kg·s²)"),
    "rydberg": (10973731.568160, 2.1e-5, "1/m"),
    "euler_mascheroni": (0.5772156649015329, 0.0, ""),
}

MATH_CONSTANTS = {
    "pi": (math.pi, 0.0),
    "e": (math.e, 0.0),
    "golden_ratio": ((1 + math.sqrt(5)) / 2, 0.0),
    "sqrt2": (math.sqrt(2), 0.0),
    "sqrt3": (math.sqrt(3), 0.0),
    "ln2": (math.log(2), 0.0),
    "catalan_G": (0.9159655941772190, 0.0),
    "apery_zeta3": (1.2020569031595943, 0.0),
    "khinchin": (2.6854520010653064, 0.0),
    "feigenbaum_delta": (4.669201609102990, 0.0),
    "feigenbaum_alpha": (2.502907875095893, 0.0),
    "twin_prime_C2": (1.3203236316455260, 0.0),
}


class KnowledgeIngestor:
    """Layer 0: Ingests heterogeneous data into DataObjects."""

    def __init__(self):
        self.objects: dict[str, DataObject] = {}

    def ingest_all_seeds(self) -> list[DataObject]:
        """Load all built-in seed data banks."""
        results = []
        results.extend(self._ingest_integer_sequences())
        results.extend(self._ingest_physical_constants())
        results.extend(self._ingest_math_constants())
        results.extend(self._ingest_partitions())
        results.extend(self._ingest_mock_theta())
        return results

    def _ingest_integer_sequences(self) -> list[DataObject]:
        objs = []

        # Partition counts
        pvals = _partition_values(200)
        obj = DataObject(
            id="iseq_partition",
            sequence=[float(x) for x in pvals],
            gf_hint="prod_{k>=1} 1/(1 - x^k)",
            domain=Domain.PARTITION,
            name="partition_function",
            metadata={"oeis": "A000041"},
        )
        self._register(obj)
        objs.append(obj)

        # Fibonacci
        fib = _fibonacci(50)
        obj = DataObject(
            id="iseq_fibonacci",
            sequence=[float(x) for x in fib],
            gf_hint="x/(1 - x - x^2)",
            domain=Domain.INTEGER_SEQ,
            name="fibonacci",
            metadata={"oeis": "A000045"},
        )
        self._register(obj)
        objs.append(obj)

        # Catalan
        cat = _catalan_numbers(30)
        obj = DataObject(
            id="iseq_catalan",
            sequence=[float(x) for x in cat],
            gf_hint="(1 - sqrt(1-4x))/(2x)",
            domain=Domain.INTEGER_SEQ,
            name="catalan_numbers",
            metadata={"oeis": "A000108"},
        )
        self._register(obj)
        objs.append(obj)

        # Bell
        bell = _bell_numbers(30)
        obj = DataObject(
            id="iseq_bell",
            sequence=[float(x) for x in bell],
            gf_hint="exp(e^x - 1)",
            domain=Domain.INTEGER_SEQ,
            name="bell_numbers",
            metadata={"oeis": "A000110"},
        )
        self._register(obj)
        objs.append(obj)

        # Prime gaps
        try:
            gaps = _prime_gaps(200)
            obj = DataObject(
                id="iseq_prime_gaps",
                sequence=[float(x) for x in gaps],
                domain=Domain.INTEGER_SEQ,
                name="prime_gaps",
                metadata={"oeis": "A001223"},
            )
            self._register(obj)
            objs.append(obj)
        except ImportError:
            pass  # sympy not available

        return objs

    def _ingest_physical_constants(self) -> list[DataObject]:
        objs = []
        for name, (val, unc, unit) in PHYSICAL_CONSTANTS.items():
            obj = DataObject(
                id=f"phys_{name}",
                sequence=[val],
                domain=Domain.PHYSICS,
                uncertainty=unc,
                name=name,
                metadata={"unit": unit, "source": "NIST_CODATA_2018"},
            )
            self._register(obj)
            objs.append(obj)
        return objs

    def _ingest_math_constants(self) -> list[DataObject]:
        objs = []
        for name, (val, unc) in MATH_CONSTANTS.items():
            obj = DataObject(
                id=f"math_{name}",
                sequence=[val],
                domain=Domain.MATH_CONST,
                uncertainty=unc,
                name=name,
            )
            self._register(obj)
            objs.append(obj)
        return objs

    def _ingest_partitions(self) -> list[DataObject]:
        """Ingest partition function subsequences for various moduli."""
        pvals = _partition_values(200)
        objs = []
        for m in [5, 7, 11, 13, 17, 19, 23]:
            for r in range(m):
                subseq = [float(pvals[i]) for i in range(r, 201, m)]
                obj = DataObject(
                    id=f"part_mod{m}_r{r}",
                    sequence=subseq,
                    gf_hint=f"p(n) for n ≡ {r} (mod {m})",
                    domain=Domain.PARTITION,
                    name=f"partition_mod{m}_residue{r}",
                    metadata={"modulus": m, "residue": r},
                )
                self._register(obj)
                objs.append(obj)
        return objs

    def _ingest_mock_theta(self) -> list[DataObject]:
        """Evaluate Ramanujan's mock theta functions at sample q values."""
        objs = []
        try:
            import mpmath as mp
            mp.mp.dps = 50

            for q_val in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
                # f_0(q) mock theta
                q = mp.mpf(q_val)
                s = mp.mpf(0)
                for n in range(60):
                    num = q ** (n * n)
                    den = mp.mpf(1)
                    for m_idx in range(1, n + 1):
                        den *= (1 + q ** m_idx) ** 2
                    if abs(den) < mp.mpf(10) ** (-40):
                        break
                    s += num / den

                obj = DataObject(
                    id=f"mock_f0_q{int(q_val * 10)}",
                    sequence=[float(s)],
                    gf_hint=f"f_0(q) = Sum_n q^(n^2)/prod(1+q^m)^2, q={q_val}",
                    domain=Domain.MOCK_THETA,
                    name=f"mock_theta_f0_q{q_val}",
                    metadata={"function": "f0", "q": q_val},
                )
                self._register(obj)
                objs.append(obj)
        except ImportError:
            pass  # mpmath not available
        return objs

    def ingest_custom(self, name: str, sequence: list[float],
                      domain: Domain = Domain.CUSTOM,
                      gf_hint: str | None = None,
                      metadata: dict | None = None) -> DataObject:
        """Ingest a custom sequence from the user."""
        obj = DataObject(
            id="",
            sequence=sequence,
            gf_hint=gf_hint,
            domain=domain,
            name=name,
            metadata=metadata or {},
        )
        self._register(obj)
        return obj

    def ingest_from_file(self, path: str, domain: Domain = Domain.CUSTOM) -> list[DataObject]:
        """Load sequences from a JSON file.

        Expected format: [{"name": "...", "sequence": [...], "gf_hint": "...", "metadata": {...}}, ...]
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        objs = []
        for entry in data:
            obj = DataObject(
                id="",
                sequence=entry["sequence"],
                gf_hint=entry.get("gf_hint"),
                domain=domain,
                name=entry.get("name", "unnamed"),
                uncertainty=entry.get("uncertainty", 0.0),
                metadata=entry.get("metadata", {}),
            )
            self._register(obj)
            objs.append(obj)
        return objs

    def _register(self, obj: DataObject) -> None:
        self.objects[obj.id] = obj

    def get_all(self) -> list[DataObject]:
        return list(self.objects.values())

    def get_by_domain(self, domain: Domain) -> list[DataObject]:
        return [o for o in self.objects.values() if o.domain == domain]

    def summary(self) -> dict:
        from collections import Counter
        domain_counts = Counter(o.domain.value for o in self.objects.values())
        return {
            "total_objects": len(self.objects),
            "by_domain": dict(domain_counts),
        }
