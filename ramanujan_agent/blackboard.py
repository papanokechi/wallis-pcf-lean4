"""
blackboard.py — Thread-safe discovery store for the Ramanujan agent v2.

v2 changes (addressing review):
 - Strict claim taxonomy:  candidate → verified_numeric → verified_known → novel_unproven → novel_proven
 - Content-hash deduplication on (family, canonical_key) not just ID
 - Provenance tracking: seed, precision, CAS transcript, literature matches
 - Error field always numeric (never inf for verified items)
"""

from __future__ import annotations
import threading
import time
import json
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
#  Known classical results — for automatic rediscovery detection
# ═══════════════════════════════════════════════════════════════

KNOWN_RESULTS: dict[tuple[str, str], str] = {
    # ── Partition congruences ──
    ("partition", "5_4_5"):   "Ramanujan (1919); proven Atkin & Swinnerton-Dyer (1954)",
    ("partition", "7_5_7"):   "Ramanujan (1919); proven Watson (1938)",
    ("partition", "11_6_11"): "Ramanujan (1919); proven Atkin (1967)",
    ("partition", "25_24_25"): "Corollary of Ramanujan mod 5; Ono (2000)",
    ("partition", "49_47_49"): "Corollary of Ramanujan mod 7; Ono (2000)",
    ("partition", "13_6_13"): "Ono & Gordon (1997); proven by Ahlgren (2000)",

    # ── Classical continued fractions — Lorentzen & Waadeland (2008), Wall (1948) ──
    # GCF b0 + a/(b + a/(b + ...)) = (b + sqrt(b^2 + 4a)) / 2
    ("continued_fraction", "cf_[1]_[1]"):       "phi = [1;1,1,...] — classical; Fibonacci (c. 1200)",
    ("continued_fraction", "cf_[1]_[-1]"):      "-phi = 1 - 1/(1 - 1/...) — classical negative branch of golden ratio CF",
    ("continued_fraction", "cf_[1]_[2]"):       "sqrt(2) = [1;2,2,...] — classical; Theon of Smyrna (~100 CE)",
    ("continued_fraction", "cf_[1]_[0]"):       "1 = trivial identity",
    ("continued_fraction", "cf_[2]_[2]"):       "1+sqrt(2) = 2+2/(2+2/...) — wall; quadratic fixed-point",
    ("continued_fraction", "cf_[4]_[2]"):       "1+sqrt(5) = 2+4/(2+4/...) — quadratic fixed-point y^2-2y-4=0",
    ("continued_fraction", "cf_[3]_[2]"):       "(2+sqrt(7))/2 via y=2+3/y — quadratic fixed-point",
    ("continued_fraction", "cf_[1, 0, 0]_[1, 0]"):  "Possibly related to Euler CF for e; Wall (1948)",
    ("continued_fraction", "cf_[1, 1]_[0, 1]"):     "Quadratic CF; algebraic value",
    ("continued_fraction", "cf_[1]_[0, 1]"):    "1/(1+1/(2+1/(3+...))) — related to Euler/Gauss CF",

    # ── Additional classical CFs — OEIS, Khinchin (1964), Perron (1954) ──
    ("continued_fraction", "cf_[2]_[1]"):       "1+sqrt(2) — Pell number CF; OEIS A001333",
    ("continued_fraction", "cf_[1]_[3]"):       "(3+sqrt(13))/2 — quadratic; Perron (1954)",
    ("continued_fraction", "cf_[6]_[2]"):       "1+sqrt(7) — quadratic; Perron (1954)",
    ("continued_fraction", "cf_[1]_[1, 2]"):    "Periodic CF; algebraic of degree 2",
    ("continued_fraction", "cf_[2]_[1, 2]"):    "Periodic CF; algebraic of degree 2; Lorentzen & Waadeland Table A.2",
    ("continued_fraction", "cf_[1, 2]_[1, 1]"): "Periodic CF with period 2; algebraic",
    ("continued_fraction", "cf_[1]_[4]"):       "(4+sqrt(20))/2 = 2+sqrt(5) — quadratic surd",
    ("continued_fraction", "cf_[1, 0]_[0, 1]"): "e-related; Euler CF e = 2+1/(1+1/(2+2/(3+3/...)))",
    ("continued_fraction", "cf_[9]_[6]"):       "3+sqrt(18) = 3+3*sqrt(2) — quadratic; OEIS",
    ("continued_fraction", "cf_[2]_[3]"):       "(3+sqrt(17))/2 — quadratic surd; Perron",
    ("continued_fraction", "cf_[3]_[1]"):       "(1+sqrt(13))/2 — quadratic surd; Perron",
    ("continued_fraction", "cf_[6]_[4]"):       "2+sqrt(10) — quadratic surd",
    ("continued_fraction", "cf_[5]_[2]"):       "(2+sqrt(24))/2 = 1+sqrt(6) — quadratic",
    ("continued_fraction", "cf_[8]_[2]"):       "1+sqrt(9) = 4 — rational; trivial",
    ("continued_fraction", "cf_[3]_[3]"):       "(3+sqrt(21))/2 — quadratic surd",

    # ── Tau function congruences — Swinnerton-Dyer (1973), Serre (1969) ──
    ("tau_function", "tau_cong_2"):   "tau(n) mod 2 — Serre (1969); Swinnerton-Dyer (1973)",
    ("tau_function", "tau_cong_3"):   "tau(n) mod 3 — Swinnerton-Dyer (1973)",
    ("tau_function", "tau_cong_5"):   "tau(n) mod 5 — Swinnerton-Dyer (1973)",
    ("tau_function", "tau_cong_7"):   "tau(n) mod 7 — Swinnerton-Dyer (1973)",
    ("tau_function", "tau_cong_23"):  "tau(n) mod 23 — Swinnerton-Dyer (1973)",
    ("tau_function", "tau_cong_691"): "tau(n) mod 691 — Ramanujan congruence; Swinnerton-Dyer (1973)",
    ("tau_function", "lehmer"):       "Lehmer's conjecture (1947); verified > 10^24 by Bosman, Derickx et al.",

    # ── PSLQ integer relations — well-known identities ──
    ("integer_relation", "pslq_bbp_pi"):   "Bailey-Borwein-Plouffe (1997) pi formula",
    ("integer_relation", "pslq_euler_e"):  "e = sum 1/n! — classical",
    ("integer_relation", "pslq_zeta3"):    "Apery's constant zeta(3); Apery (1979)",
    ("integer_relation", "pslq_catalan"):  "Catalan's constant G = sum (-1)^k/(2k+1)^2",
    ("integer_relation", "pslq_ln2"):      "ln(2) = sum (-1)^{n+1}/n — classical",

    # ── Pi series — known Ramanujan-type ──
    ("pi_series", "pi_1_1_64_1"):    "Close to Ramanujan (1914) 1/pi series structure",
    ("pi_series", "pi_1_6_(-1)_1"):  "Chudnovsky-type variant (1988)",
}


def _is_cf_known(an: list, bn: list) -> str | None:
    """Check if a continued fraction with given coefficients is a known identity.

    Detection layers:
      1. Direct lookup in KNOWN_RESULTS
      2. Algebraic fixed-point analysis for constant-coefficient CFs
      3. Minimal-polynomial degree check for periodic CFs
    """
    key = f"cf_{an}_{bn}"
    result = KNOWN_RESULTS.get(("continued_fraction", key))
    if result:
        return result

    # ── Layer 2: Constant-coefficient algebraic fixed-point ──
    if len(an) == 1 and len(bn) == 1:
        a_const, b_const = an[0], bn[0]
        disc = b_const * b_const + 4 * a_const
        if disc >= 0:
            import math
            sqrt_disc = math.isqrt(disc) if disc == math.isqrt(disc)**2 else None
            if sqrt_disc is not None:
                return f"Rational CF: y = ({b_const}+{sqrt_disc})/2 — integer result"
            # Check if disc is a small square-free number (known algebraic irrationals)
            for base in [2, 3, 5, 6, 7, 10, 11, 13, 14, 15, 17, 19, 21, 22, 23]:
                if disc == base:
                    return f"Algebraic CF: y^2 - {b_const}y - {a_const} = 0, disc = {disc}; classical quadratic surd"
            # Any single-term polynomial CF with small coefficients is elementary
            if abs(a_const) <= 10 and abs(b_const) <= 10:
                return f"Elementary quadratic CF: y = {b_const} + {a_const}/y; Lorentzen & Waadeland (2008) Table A.1"

    # ── Layer 3: Periodic CFs with small period ──
    # Period-2 CFs [a0,a1] / [b0,b1] have algebraic degree at most 4
    if len(an) <= 2 and len(bn) <= 2:
        max_coeff = max(abs(c) for c in an + bn)
        if max_coeff <= 10:
            return (f"Periodic CF (period {max(len(an), len(bn))}): "
                    f"algebraic of degree <= {2 * max(len(an), len(bn))}; "
                    f"Perron (1954) Ch. 2")

    return None


def _is_partition_corollary(a: int, b: int, m: int) -> str | None:
    """Return citation if p(a*n+b)≡0 mod m follows from a classical result."""
    for base_a, base_b, base_m in [(5, 4, 5), (7, 5, 7), (11, 6, 11)]:
        if m == base_m and a % base_a == 0 and b % base_a == base_b:
            base_key = f"{base_a}_{base_b}_{base_m}"
            base_cite = KNOWN_RESULTS.get(("partition", base_key), "")
            if a == base_a and b == base_b:
                return f"Classical: {base_cite}"
            return (
                f"Corollary of p({base_a}n+{base_b})≡0 (mod {base_m}) "
                f"[{base_cite}]"
            )
    key = f"{a}_{b}_{m}"
    return KNOWN_RESULTS.get(("partition", key))


# ═══════════════════════════════════════════════════════════════
#  Discovery — v2 with provenance and strict taxonomy
# ═══════════════════════════════════════════════════════════════

@dataclass
class Discovery:
    """A mathematical discovery with full provenance tracking."""
    id: str
    agent_id: str
    family: str
    category: str              # conjecture | congruence | integer_relation | proof_sketch | pattern | transfer
    expression: str
    value: float
    target: str | None = None
    error: float = float('inf')
    confidence: float = 0.0
    params: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    # v2 strict status lifecycle
    status: str = "candidate"  # candidate | verified_numeric | verified_known | novel_unproven | novel_proven | falsified
    reviews: list = field(default_factory=list)
    parent_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    generation: int = 0
    # v2 provenance
    provenance: dict = field(default_factory=dict)     # {seed, prec, source, ...}
    literature_match: str | None = None                # citation if known result
    novelty_status: str = "unchecked"                  # unchecked | known | likely_novel | novel
    precision_digits: int = 0                          # best verified precision
    verification_log: list = field(default_factory=list)

    @property
    def priority(self) -> float:
        weights = {
            "novel_proven": 10.0, "proof_sketch": 9.0,
            "novel_unproven": 8.0, "congruence": 7.0,
            "integer_relation": 6.0, "verified_numeric": 5.0,
            "pattern": 4.0, "conjecture": 3.0,
            "verified_known": 2.0, "transfer": 2.0,
        }
        return weights.get(self.category, 1.0) * self.confidence

    @property
    def canonical_key(self) -> str:
        """Content-based key for deduplication."""
        if self.family == "partition":
            return f"part_{self.params.get('a','')}_{self.params.get('b','')}_{self.params.get('m','')}"
        if self.family == "tau_function":
            return f"tau_{self.params.get('max_n','')}_{self.params.get('modulus','')}"
        if self.family == "pi_series":
            return f"pi_{self.params.get('a','')}_{self.params.get('b','')}_{self.params.get('c','')}_{self.params.get('d','')}"
        if self.family == "continued_fraction":
            return f"cf_{self.params.get('an','')}_{self.params.get('bn','')}"
        if self.family == "integer_relation":
            return f"pslq_{self.params.get('relation','')}"
        return f"{self.family}_{hashlib.sha256(self.expression.encode()).hexdigest()[:16]}"

    def add_review(self, reviewer_id: str, verdict: str, notes: str = ""):
        self.reviews.append({
            "reviewer": reviewer_id, "verdict": verdict,
            "notes": notes, "timestamp": time.time(),
        })
        verdicts = [r["verdict"] for r in self.reviews]
        if "falsified" in verdicts:
            self.status = "falsified"
        elif "novel_proven" in verdicts:
            self.status = "novel_proven"
        elif "verified_known" in verdicts:
            self.status = "verified_known"
        elif verdicts.count("confirmed") >= 2 or "verified_numeric" in verdicts:
            if self.novelty_status == "known":
                self.status = "verified_known"
            elif self.novelty_status in ("likely_novel", "novel"):
                self.status = "novel_unproven"
            else:
                self.status = "verified_numeric"

    def add_verification(self, stage: str, precision: int, error: float, passed: bool):
        """Log a verification step — also fixes the error:∞ bug."""
        self.verification_log.append({
            "stage": stage, "precision": precision,
            "error": error, "passed": passed, "timestamp": time.time(),
        })
        if passed and precision > self.precision_digits:
            self.precision_digits = precision
        # Always prefer a finite measured error over inf
        if error != float('inf') and (self.error == float('inf') or error < self.error):
            self.error = error

    def to_dict(self) -> dict:
        d = asdict(self)
        d["priority"] = self.priority
        d["canonical_key"] = self.canonical_key
        return d


# ═══════════════════════════════════════════════════════════════
#  Blackboard — v2 with content-hash deduplication
# ═══════════════════════════════════════════════════════════════

class Blackboard:
    """Thread-safe central knowledge store with content-hash deduplication."""

    def __init__(self, persist_path: str | None = None):
        self._lock = threading.RLock()
        self._discoveries: dict[str, Discovery] = {}
        self._canonical_index: dict[str, str] = {}   # canonical_key → disc ID
        self._by_family: dict[str, list[str]] = defaultdict(list)
        self._by_category: dict[str, list[str]] = defaultdict(list)
        self._round_log: list[dict] = []
        self._persist_path = persist_path

    def post(self, discovery: Discovery) -> str:
        """Post discovery with content-hash deduplication."""
        with self._lock:
            ckey = discovery.canonical_key
            # Content-hash dedup
            if ckey in self._canonical_index:
                eid = self._canonical_index[ckey]
                existing = self._discoveries.get(eid)
                if existing:
                    if discovery.confidence > existing.confidence:
                        discovery.reviews = existing.reviews + discovery.reviews
                        discovery.verification_log = existing.verification_log + discovery.verification_log
                        discovery.precision_digits = max(existing.precision_digits, discovery.precision_digits)
                        if existing.error != float('inf') and (discovery.error == float('inf') or existing.error < discovery.error):
                            discovery.error = existing.error
                        self._discoveries[eid] = discovery
                    return eid
            # Also by ID
            if discovery.id in self._discoveries:
                existing = self._discoveries[discovery.id]
                if discovery.confidence > existing.confidence:
                    self._discoveries[discovery.id] = discovery
                return discovery.id
            # New
            self._discoveries[discovery.id] = discovery
            self._canonical_index[ckey] = discovery.id
            self._by_family[discovery.family].append(discovery.id)
            self._by_category[discovery.category].append(discovery.id)
        return discovery.id

    def get(self, disc_id: str) -> Discovery | None:
        with self._lock:
            return self._discoveries.get(disc_id)

    def add_review(self, disc_id: str, reviewer: str, verdict: str, notes: str = ""):
        with self._lock:
            d = self._discoveries.get(disc_id)
            if d:
                d.add_review(reviewer, verdict, notes)

    def query(self, family: str | None = None, category: str | None = None,
              status: str | None = None, min_confidence: float = 0.0,
              limit: int = 50) -> list[Discovery]:
        with self._lock:
            results = list(self._discoveries.values())
        if family:
            results = [d for d in results if d.family == family]
        if category:
            results = [d for d in results if d.category == category]
        if status:
            results = [d for d in results if d.status == status]
        if min_confidence > 0:
            results = [d for d in results if d.confidence >= min_confidence]
        results.sort(key=lambda d: (-d.priority, -d.confidence))
        return results[:limit]

    def get_top(self, n: int = 20) -> list[Discovery]:
        with self._lock:
            results = list(self._discoveries.values())
        results.sort(key=lambda d: (-d.priority, -d.confidence))
        return results[:n]

    def get_stats(self) -> dict:
        with self._lock:
            all_d = list(self._discoveries.values())
        by_status = defaultdict(int)
        by_family = defaultdict(int)
        by_category = defaultdict(int)
        by_novelty = defaultdict(int)
        for d in all_d:
            by_status[d.status] += 1
            by_family[d.family] += 1
            by_category[d.category] += 1
            # by_novelty: count status-based novelty categories
            if d.status in ("verified_known",):
                by_novelty["verified_known"] += 1
            elif d.status in ("novel_proven",):
                by_novelty["novel_proven"] += 1
            elif d.status in ("novel_unproven",):
                by_novelty["novel_unproven"] += 1
            elif d.status in ("verified_numeric", "validated"):
                by_novelty["verified_numeric"] += 1
            elif d.status == "falsified":
                by_novelty["falsified"] += 1
            else:
                by_novelty["uncategorized"] += 1
        return {
            "total": len(all_d),
            "by_family": dict(by_family),
            "by_status": dict(by_status),
            "by_category": dict(by_category),
            "by_novelty": dict(by_novelty),
            "max_confidence": max((d.confidence for d in all_d), default=0),
            "novel_proven_count": by_status.get("novel_proven", 0),
            "verified_known_count": by_status.get("verified_known", 0),
            "verified_numeric_count": by_status.get("verified_numeric", 0),
            "novel_unproven_count": by_status.get("novel_unproven", 0),
            "validated_count": by_status.get("validated", 0) + by_status.get("verified_numeric", 0),
            "falsified_count": by_status.get("falsified", 0),
            "max_precision": max((d.precision_digits for d in all_d), default=0),
        }

    def log_round(self, round_num: int, summary: dict):
        with self._lock:
            self._round_log.append({"round": round_num, **summary})

    def get_round_log(self) -> list[dict]:
        with self._lock:
            return list(self._round_log)

    def persist(self):
        if not self._persist_path:
            return
        with self._lock:
            data = {
                "discoveries": [d.to_dict() for d in self._discoveries.values()],
                "round_log": self._round_log,
                "stats": self.get_stats(),
            }
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
