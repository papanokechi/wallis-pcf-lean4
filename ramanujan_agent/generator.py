"""
generator.py — Conjecture generation engine v2.

v2 changes:
 - Provenance metadata on every conjecture (seed, precision, source)
 - Expanded partition search: Ono (2000) moduli, higher ranges, corollary filtering
 - Deeper Lehmer verification (up to n=500)
 - PSLQ multi-precision stability checks
 - Quality metric includes novelty bonus
"""

from __future__ import annotations
import random
import itertools
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

import mpmath

from .formulas import (
    _generalised_pi_series, _generalised_cf, _jacobi_theta3,
    _euler_q_product, _ramanujan_theta, _mock_theta_f0,
    _mock_theta_phi, _partition_count, _ramanujan_tau, _pslq_search,
    _mp, get_all_templates,
)

_PREC = 60


@dataclass
class Conjecture:
    """A candidate mathematical identity / relation with provenance."""
    id: str
    family: str
    expression: str
    value: float
    target: str | None = None
    target_value: float | None = None
    error: float = float('inf')
    params: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    source: str = "generator"
    generation: int = 0
    # v2 provenance
    provenance: dict = field(default_factory=dict)

    @property
    def quality(self) -> float:
        """Score: lower error + simpler expression + structural novelty = higher quality.

        v3.1: Incorporates structural novelty bonus:
        - Higher polynomial degree in CF coefficients → more novel
        - Non-constant CF (len(an) > 1 or len(bn) > 1) → bonus
        - Relations involving more basis constants → bonus
        """
        if self.error == float('inf') or self.error > 1.0:
            return 0.0
        import math
        err_score = max(0, -math.log10(max(self.error, 1e-100)))
        complexity = len(self.expression)
        comp_penalty = max(0, complexity - 50) * 0.01
        novelty_bonus = self._structural_novelty()
        return err_score - comp_penalty + novelty_bonus

    def _structural_novelty(self) -> float:
        """Compute a structural novelty bonus based on the conjecture's form."""
        bonus = 0.0
        params = self.params or {}

        if self.family == "continued_fraction":
            an = params.get("an", [])
            bn = params.get("bn", [])
            # Non-constant coefficients are more interesting
            if len(an) > 1:
                bonus += 1.0 * (len(an) - 1)
            if len(bn) > 1:
                bonus += 0.5 * (len(bn) - 1)
            # Higher max coefficient → less likely to be a simple algebraic number
            max_c = max((abs(c) for c in an + bn), default=0)
            if max_c > 5:
                bonus += 0.5

        elif self.family == "integer_relation":
            rel = params.get("relation", [])
            # More terms in the relation → potentially more interesting
            nonzero = sum(1 for r in rel if r != 0)
            if nonzero > 3:
                bonus += 0.5 * (nonzero - 3)

        elif self.family == "partition":
            a = params.get("a", 0)
            m = params.get("m", 0)
            # Non-prime moduli or non-Ramanujan-type are more novel
            if m not in (5, 7, 11) and m > 0:
                bonus += 2.0
            if a > 11:
                bonus += 1.0

        # Flag from metadata: generator already assessed novelty
        if self.metadata.get("is_novel"):
            bonus += 2.0

        return bonus


def _make_id(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:12]


# ===================================================================
#  GENERATION STRATEGIES
# ===================================================================

class ConjectureGenerator:
    """Main engine: produces candidate conjectures via multiple strategies."""

    def __init__(self, prec: int = _PREC, seed: int | None = None):
        self.prec = prec
        self.rng = random.Random(seed)
        self.mp = _mp(prec)
        self.generation = 0
        # Track successful parameter regions for guided search
        self._good_params: list[dict] = []
        self._relay_seed_pool_path = "results/relay_chain_seed_pool.json"

    def set_generation(self, gen: int):
        self.generation = gen

    def feedback(self, good_params: list[dict]):
        """Receive feedback on which parameter regions produced good results."""
        self._good_params.extend(good_params)

    def load_relay_seed_pool(self, path: str | None = None, limit: int = 12) -> list[dict]:
        """Load AI-generated relay seeds, if available, for guided exploration."""
        import json
        from pathlib import Path

        seed_path = Path(path or self._relay_seed_pool_path)
        if not seed_path.exists():
            return []

        try:
            data = json.loads(seed_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        seeds = data if isinstance(data, list) else data.get("seeds", [])
        params = []
        for seed in seeds[:limit]:
            p = dict(seed.get("params", {}))
            if p:
                params.append(p)
        return params

    # ---------------------------------------------------------------
    #  Strategy 1: Generalised pi series sweep
    # ---------------------------------------------------------------
    def generate_pi_series(self, budget: int = 50) -> list[Conjecture]:
        """Sweep (a,b,c,d) for generalised 1/pi formulas."""
        results = []
        # If we have good params, explore nearby
        base_regions = self._good_params_for("pi_series")
        for _ in range(budget):
            if base_regions and self.rng.random() < 0.4:
                # Exploit: perturb good params
                base = self.rng.choice(base_regions)
                a = base.get("a", 1) + self.rng.randint(-2, 2)
                b = base.get("b", 1) + self.rng.randint(-20, 20)
                c = base.get("c", 64) + self.rng.randint(-10, 10)
                d = base.get("d", 1) + self.rng.randint(-5, 5)
            else:
                # Explore: random
                a = self.rng.randint(1, 40)
                b = self.rng.randint(1, 2000)
                c = self.rng.choice([64, 256, 396, 640320, 4096,
                                      self.rng.randint(2, 500)])
                d = self.rng.choice([1, 2, 4, 8, 16, 32])

            if c <= 0 or a <= 0:
                continue
            try:
                r = _generalised_pi_series(a, b, c, d, num_terms=60, prec=self.prec)
            except Exception:
                continue
            if not r.get("converges", False):
                continue
            cj = Conjecture(
                id=_make_id(f"pi_{a}_{b}_{c}_{d}"),
                family="pi_series",
                expression=r["expression"],
                value=r["value"],
                target="pi", target_value=r["target"],
                error=r["error"],
                params={"a": a, "b": b, "c": c, "d": d},
                source="pi_series_sweep",
                generation=self.generation,
                provenance={
                    "method": "generalised_pi_series",
                    "params": {"a": a, "b": b, "c": c, "d": d},
                    "num_terms": 60, "prec": self.prec,
                },
            )
            results.append(cj)
        return results

    # ---------------------------------------------------------------
    #  Strategy 2: Continued fraction search
    # ---------------------------------------------------------------
    def generate_continued_fractions(self, budget: int = 40) -> list[Conjecture]:
        """Search GCFs with polynomial a_n, b_n.

        v3: Also keeps CFs that converge to values NOT matching any known
        constant — these are the genuinely novel candidates.
        v4.1: Expanded coefficient range (-10..10 / -8..10), pre-convergence
        ratio check to reduce falsification rate.
        """
        results = []
        base_regions = self._good_params_for("continued_fraction")
        for _ in range(budget):
            # Prefer relay / prior-good regions some of the time.
            if base_regions and self.rng.random() < 0.45:
                base = dict(self.rng.choice(base_regions))
                an = [int(x) for x in (base.get("an", [1]) or [1])]
                bn = [int(x) for x in (base.get("bn", [1, 1]) or [1, 1])]
                an = [max(-10, min(10, c + self.rng.randint(-1, 1))) for c in an]
                bn = [max(-8, min(10, c + self.rng.randint(-2, 2))) for c in bn]
                if an and an[0] == 0:
                    an[0] = 1
                if bn and bn[0] == 0:
                    bn[0] = 1
            else:
                # v4.1: Wider coefficient range + richer degree distribution
                degree = self.rng.choice([1, 1, 2, 2, 3, 3, 4])
                an = [self.rng.randint(-10, 10) for _ in range(degree)]
                bn = [self.rng.randint(-8, 10) for _ in range(self.rng.choice([1, 2]))]

            if all(x == 0 for x in an) or all(x == 0 for x in bn):
                continue

            # v4.1: Pre-convergence ratio check — reject CFs where
            # |a_n/b_n| → ratio ≥ 1 (Pringsheim bound) before expensive eval
            if len(bn) == 2 and bn[0] != 0 and len(an) >= 1:
                lead_a = abs(an[0])
                lead_b = abs(bn[0])
                if lead_b > 0:
                    asym_ratio = lead_a / lead_b
                    # degree(a) > degree(b)=1 → definitely divergent
                    if len(an) - 1 > 1:
                        continue
                    # same degree but ratio ≥ 1.5 → very likely divergent
                    if len(an) - 1 == 1 and asym_ratio >= 1.5:
                        continue

            try:
                r = _generalised_cf(an, bn, prec=self.prec)
            except Exception:
                continue

            # v3: keep CFs that converge, regardless of constant matching
            if not r.get("converged", False):
                continue

            is_known = r.get("is_known_transform", False)
            is_novel_candidate = r.get("is_potentially_novel", False)

            if not is_known and not is_novel_candidate:
                continue  # doesn't converge or isn't interesting

            error = r["best_error"] if is_known else r.get("convergence_error", 1e-10)
            target = r.get("best_match") if is_known else "novel_constant?"

            cj = Conjecture(
                id=_make_id(f"cf_{an}_{bn}"),
                family="continued_fraction",
                expression=r["expression"],
                value=r["value"],
                target=target,
                error=error,
                params={"an": an, "bn": bn},
                source="cf_search",
                generation=self.generation,
                metadata={
                    "max_coeff": r.get("max_coeff", 0),
                    "is_novel": is_novel_candidate,
                    "is_known_transform": is_known,
                    "matched_constant": r.get("matched_constant"),
                    "matched_multiplier": r.get("matched_multiplier"),
                    "literature_match": r.get("transform_citation"),
                    "convergence_error": r.get("convergence_error"),
                },
                provenance={
                    "method": "generalised_cf",
                    "an": an, "bn": bn, "prec": self.prec,
                },
            )
            results.append(cj)
        return results

    # ---------------------------------------------------------------
    #  Strategy 3: q-series identity hunting
    # ---------------------------------------------------------------
    def generate_q_series_identities(self, budget: int = 30) -> list[Conjecture]:
        """Look for relations between q-series at special q values."""
        results = []
        mp = self.mp
        # Special q-values related to modular forms
        special_qs = [
            mp.exp(-mp.pi),             # e^{-pi}
            mp.exp(-mp.pi * mp.sqrt(2)),
            mp.exp(-mp.pi * mp.sqrt(3)),
            mp.exp(-2 * mp.pi),
            0.5, 0.25, 0.1,
        ]
        targets = {
            "pi": float(mp.pi), "e": float(mp.e),
            "sqrt2": float(mp.sqrt(2)), "phi": float(mp.phi),
            "ln2": float(mp.ln(2)), "euler_gamma": float(mp.euler),
            "catalan": float(mp.catalan), "apery": float(mp.zeta(3)),
            "pi^2/6": float(mp.pi**2 / 6),
        }

        for _ in range(budget):
            q = float(self.rng.choice(special_qs))
            try:
                th3 = _jacobi_theta3(q, prec=self.prec)
                euler = _euler_q_product(q, prec=self.prec)
            except Exception:
                continue
            v3 = th3.get("value", 0)
            ve = euler.get("value", 0)
            if v3 == 0 or ve == 0:
                continue

            # Check combinations against known constants
            combos = {
                "theta3": v3,
                "euler_prod": ve,
                "theta3^2": v3**2,
                "theta3*euler": v3 * ve,
                "theta3/euler": v3 / ve if ve != 0 else None,
                "euler^2": ve**2,
            }
            for combo_name, combo_val in combos.items():
                if combo_val is None:
                    continue
                for tname, tval in targets.items():
                    if tval == 0:
                        continue
                    for mult in [1, 2, 4, 0.5, 0.25]:
                        err = abs(combo_val * mult - tval)
                        if err < 1e-8:
                            cj = Conjecture(
                                id=_make_id(f"qser_{combo_name}_{q}_{tname}_{mult}"),
                                family="q_series",
                                expression=f"{mult}*{combo_name}(q={q:.6f}) ≈ {tname}",
                                value=combo_val * mult,
                                target=tname, target_value=tval,
                                error=err,
                                params={"q": q, "combo": combo_name, "mult": mult},
                                source="q_series_hunt",
                                generation=self.generation,
                                provenance={
                                    "method": "q_series_identity",
                                    "q": q, "combo": combo_name,
                                    "prec": self.prec,
                                },
                            )
                            results.append(cj)
        return results

    # ---------------------------------------------------------------
    #  Strategy 4: PSLQ integer relation discovery
    # ---------------------------------------------------------------
    def generate_pslq_relations(self, budget: int = 20) -> list[Conjecture]:
        """Use PSLQ to find integer relations among special values.

        v3: True multi-precision pipeline — target values and basis are
        recomputed as native mpf at each precision tier instead of
        passing through Python float (which truncates to 15 digits).
        """
        results = []
        mp = self.mp
        # v3: Expanded basis with exotic constants
        basis_names = ["1", "pi", "pi^2", "ln2", "sqrt(2)", "euler_gamma",
                        "catalan", "zeta(3)", "sqrt(3)", "ln3",
                        "zeta(5)", "ln(pi)", "pi^3", "sqrt(5)"]
        # v3: pass mpf values, NOT float()
        basis_vals = [
            mp.mpf(1), mp.pi, mp.pi**2, mp.ln(2),
            mp.sqrt(2), mp.euler, mp.catalan,
            mp.zeta(3), mp.sqrt(3), mp.ln(3),
            mp.zeta(5), mp.ln(mp.pi), mp.pi**3, mp.sqrt(5),
        ]

        # Generate target values from mock theta / q-series evaluations
        # v3: store q as mpf alongside name for precision preservation
        # v3: expanded q-values including exotic Ramanujan-type singular moduli
        target_sources = []
        q_registry = {}  # name → mpf q-value for hi-prec recomputation
        q_values = [
            0.1, 0.2, 0.3, 0.5,
            float(mp.exp(-mp.pi)),                   # e^(-π)
            float(mp.exp(-mp.pi * mp.sqrt(2))),      # e^(-π√2)
            float(mp.exp(-mp.pi * mp.sqrt(3))),      # e^(-π√3)
            float(mp.exp(-2 * mp.pi)),                # e^(-2π)
        ]
        for q in q_values:
            try:
                mth = _mock_theta_f0(q, prec=self.prec)
                if mth.get("value"):
                    # v3: use mpf value to preserve full precision
                    mpf_val = mth.get("value_mpf", mp.mpf(mth["value"]))
                    tname = f"f0(q={q})"
                    target_sources.append((tname, mpf_val))
                    q_registry[tname] = q
                phi = _mock_theta_phi(q, prec=self.prec)
                if phi.get("value"):
                    mpf_val = phi.get("value_mpf", mp.mpf(phi["value"]))
                    tname = f"phi(q={q})"
                    target_sources.append((tname, mpf_val))
                    q_registry[tname] = q
            except Exception:
                continue

        self.rng.shuffle(target_sources)
        for name, val in target_sources[:budget]:
            try:
                r = _pslq_search(val, basis_names, basis_vals, prec=self.prec)
            except Exception:
                continue
            if not r.get("found", False):
                continue
            if r.get("max_coeff", 999) > 500:
                continue

            # v3: Multi-precision stability check — recompute target AND
            # basis at each tier using native mpf (fixing the float-truncation
            # bug that caused spurious PSLQ relations to "pass" stability).
            stability_table = [
                {"precision": self.prec, "relation": r["relation"],
                 "residual": r["residual"], "max_coeff": r["max_coeff"]},
            ]
            stable = False
            try:
                hi_prec = max(self.prec * 2, 120)
                mp_hi = _mp(hi_prec)
                basis_hi = [
                    mp_hi.mpf(1), mp_hi.pi, mp_hi.pi**2,
                    mp_hi.ln(2), mp_hi.sqrt(2),
                    mp_hi.euler, mp_hi.catalan,
                    mp_hi.zeta(3), mp_hi.sqrt(3),
                    mp_hi.ln(3),
                    mp_hi.zeta(5), mp_hi.ln(mp_hi.pi),
                    mp_hi.pi**3, mp_hi.sqrt(5),
                ]
                # v3: Use q_registry for exact q-value (avoid parsing + float truncation)
                q_val = q_registry.get(name)
                if q_val is not None and "f0" in name:
                    hi_target = _mock_theta_f0(q_val, prec=hi_prec)
                    val_hi = hi_target.get("value_mpf", mp_hi.mpf(hi_target["value"]))
                elif q_val is not None and "phi" in name:
                    hi_target = _mock_theta_phi(q_val, prec=hi_prec)
                    val_hi = hi_target.get("value_mpf", mp_hi.mpf(hi_target["value"]))
                else:
                    val_hi = mp_hi.mpf(float(val))  # fallback
                r2 = _pslq_search(val_hi, basis_names, basis_hi, prec=hi_prec)
                stability_table.append({
                    "precision": hi_prec,
                    "relation": r2.get("relation"),
                    "residual": r2.get("residual"),
                    "max_coeff": r2.get("max_coeff"),
                    "found": r2.get("found", False),
                })
                if r2.get("found") and r2["relation"] == r["relation"]:
                    stable = True
                    # Level 3: ultra-high precision
                    try:
                        ultra_prec = hi_prec * 2
                        mp_u = _mp(ultra_prec)
                        basis_u = [
                            mp_u.mpf(1), mp_u.pi, mp_u.pi**2,
                            mp_u.ln(2), mp_u.sqrt(2),
                            mp_u.euler, mp_u.catalan,
                            mp_u.zeta(3), mp_u.sqrt(3),
                            mp_u.ln(3),
                            mp_u.zeta(5), mp_u.ln(mp_u.pi),
                            mp_u.pi**3, mp_u.sqrt(5),
                        ]
                        if q_val is not None and "f0" in name:
                            u_target = _mock_theta_f0(q_val, prec=ultra_prec)
                            val_u = u_target.get("value_mpf", mp_u.mpf(u_target["value"]))
                        elif q_val is not None and "phi" in name:
                            u_target = _mock_theta_phi(q_val, prec=ultra_prec)
                            val_u = u_target.get("value_mpf", mp_u.mpf(u_target["value"]))
                        else:
                            val_u = mp_u.mpf(val)
                        r3 = _pslq_search(val_u, basis_names, basis_u,
                                           prec=ultra_prec)
                        stability_table.append({
                            "precision": ultra_prec,
                            "relation": r3.get("relation"),
                            "residual": r3.get("residual"),
                            "max_coeff": r3.get("max_coeff"),
                            "found": r3.get("found", False),
                        })
                        if r3.get("found") and r3["relation"] != r["relation"]:
                            stable = False  # broke at ultra-high precision
                    except Exception:
                        pass
            except Exception:
                pass  # If hi-prec fails, mark unstable

            cj = Conjecture(
                id=_make_id(f"pslq_{name}_{r['expression'][:30]}"),
                family="integer_relation",
                expression=r["expression"],
                value=val,
                target=name,
                error=r["residual"],
                params={"relation": r["relation"], "basis": basis_names},
                source="pslq",
                generation=self.generation,
                metadata={
                    "max_coeff": r["max_coeff"],
                    "pslq_stable": stable,
                    "prec_levels": [t["precision"] for t in stability_table],
                    "stability_table": stability_table,
                },
                provenance={
                    "method": "pslq_integer_relation",
                    "prec": self.prec,
                    "stability_checked": stable,
                    "basis": basis_names,
                    "stability_table": stability_table,
                },
            )
            results.append(cj)
        return results

    # ---------------------------------------------------------------
    #  Strategy 5: Partition congruence search (v2 — Ono framework)
    # ---------------------------------------------------------------
    def generate_partition_congruences(self, budget: int = 20) -> list[Conjecture]:
        """Search for partition congruences including Ono (2000) moduli.

        v2: Searches beyond Ramanujan's three (mod 5,7,11) into:
         - Higher powers: mod 25, 49, 121, 125, 343
         - Ono primes: mod 13, 17, 19, 23, 29, 31, 37, 41, 43
         - Composite Ramanujan moduli: mod 35, 55, 77
        Also extends verification to n=1000 and flags corollaries.
        """
        results = []
        max_n = min(500 + self.generation * 100, 1000)
        p = [0] * (max_n + 1)
        p[0] = 1
        for k in range(1, max_n + 1):
            for j in range(k, max_n + 1):
                p[j] += p[j - k]

        # v2: Extended moduli list (Ono framework)
        moduli = [5, 7, 11, 13, 17, 19, 23, 25, 29, 31, 37, 41, 43,
                  49, 121, 125, 35, 55, 77]
        tested = 0
        for m in moduli:
            # v2: search wider range of (a, b)
            max_a = min(60 + self.generation * 10, 100)
            for a in range(2, max_a):
                for b in range(a):
                    vals = [p[a*n + b] for n in range(max_n // a)
                            if a*n + b <= max_n]
                    if len(vals) < 5:
                        continue
                    residues = [v % m for v in vals]
                    if all(r == 0 for r in residues):
                        # v2: Check if this is a corollary of known results
                        from .blackboard import _is_partition_corollary
                        citation = _is_partition_corollary(a, b, m)
                        is_novel = citation is None
                        cj = Conjecture(
                            id=_make_id(f"part_cong_{a}_{b}_{m}"),
                            family="partition",
                            expression=f"p({a}n+{b}) ≡ 0 (mod {m})",
                            value=0,
                            target=f"partition_congruence_mod{m}",
                            error=0.0,
                            params={"a": a, "b": b, "m": m,
                                    "verified_up_to": max_n},
                            source="partition_search",
                            generation=self.generation,
                            metadata={
                                "sample_values": vals[:10],
                                "n_tested": len(vals),
                                "is_novel": is_novel,
                                "literature_match": citation,
                            },
                            provenance={
                                "method": "exhaustive_mod_check",
                                "range": f"n=0..{max_n}",
                                "modulus": m,
                                "generation": self.generation,
                            },
                        )
                        results.append(cj)
                    tested += 1
                    if tested >= budget * 8:
                        return results
        return results

    # ---------------------------------------------------------------
    #  Strategy 6: Tau function pattern search (v2 — deeper Lehmer)
    # ---------------------------------------------------------------
    def generate_tau_patterns(self, budget: int = 15) -> list[Conjecture]:
        """Search for patterns in Ramanujan's tau function.

        v2: Extends Lehmer check to n=min(500, 50+gen*50) and adds
        multi-modulus congruence analysis with Swinnerton-Dyer primes.
        """
        results = []
        # v2: deeper computation
        max_n = min(50 + self.generation * 50, 500)
        tau_vals = {}
        for n in range(1, max_n + 1):
            try:
                r = _ramanujan_tau(n)
                tau_vals[n] = r["value"]
            except Exception:
                break

        if len(tau_vals) < 10:
            return results

        n_computed = len(tau_vals)

        # Lehmer's conjecture check
        zeros = [n for n, v in tau_vals.items() if v == 0]
        cj = Conjecture(
            id=_make_id(f"lehmer_check_{n_computed}"),
            family="tau_function",
            expression=f"tau(n) ≠ 0 for n=1..{n_computed} (Lehmer's conjecture)",
            value=len(zeros),
            target="lehmer_conjecture",
            error=0.0 if len(zeros) == 0 else 1.0,
            params={"max_n": n_computed, "zeros_found": zeros},
            source="tau_search",
            generation=self.generation,
            metadata={
                "n_computed": n_computed,
                "literature_frontier": "Verified to n > 10^24 by Bosman et al.",
                "is_novel": False,
                "literature_match": "Lehmer's conjecture (1947); verified computationally to n > 10^24",
            },
            provenance={
                "method": "exhaustive_computation",
                "range": f"n=1..{n_computed}",
                "algorithm": "eta^24_convolution",
            },
        )
        results.append(cj)

        # v2: Swinnerton-Dyer moduli (known: tau(n) mod l for l in {2,3,5,7,23,691})
        sd_primes = [2, 3, 5, 7, 11, 13, 23, 691]
        for m in sd_primes:
            residues = {n: v % m for n, v in tau_vals.items() if v is not None}
            zero_count = sum(1 for r in residues.values() if r == 0)
            total = len(residues)
            if total == 0:
                continue
            density = zero_count / total
            zero_ns = [n for n, r in residues.items() if r == 0]

            # Record pattern (whether known or not)
            is_sd_known = m in [2, 3, 5, 7, 23, 691]
            if density > 0.15 and len(zero_ns) >= 3:
                # Only exact congruences (100%) get error=0; statistical get 1-density
                is_exact = abs(density - 1.0) < 1e-9
                cj = Conjecture(
                    id=_make_id(f"tau_cong_{m}_{n_computed}"),
                    family="tau_function",
                    expression=(
                        f"tau(n) ≡ 0 (mod {m}) for all n=1..{n_computed}"
                        if is_exact else
                        f"tau(n) ≡ 0 (mod {m}): density {density:.1%} for n=1..{n_computed} (statistical)"
                    ),
                    value=density,
                    target=f"tau_congruence_mod{m}",
                    error=0.0 if is_exact else 1.0 - density,
                    params={"modulus": m, "zero_ns": zero_ns[:30],
                            "max_n": n_computed, "density": density},
                    source="tau_search",
                    generation=self.generation,
                    metadata={
                        "is_novel": not is_sd_known,
                        "is_exact_congruence": is_exact,
                        "literature_match": (
                            f"Swinnerton-Dyer congruence mod {m} (classical)"
                            if is_sd_known else None
                        ),
                    },
                    provenance={
                        "method": "modular_residue_scan",
                        "range": f"n=1..{n_computed}",
                        "modulus": m,
                    },
                )
                results.append(cj)
        return results

    # ---------------------------------------------------------------
    #  Strategy 7: Nonpolynomial CF search (v3 — deeper exploration)
    # ---------------------------------------------------------------
    def generate_nonpoly_cfs(self, budget: int = 30) -> list[Conjecture]:
        """Search CFs with nonpolynomial coefficient sequences.

        v3: Uses convergence-based filtering and ISC lookup.
        v4.3: Added alternating factorial strategy for better convergence.
        Keeps CFs that converge to unrecognised values as novel candidates.
        """
        results = []
        mp = self.mp
        from .formulas import _evaluate_gcf

        SMALL_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
                        31, 37, 41, 43, 47, 53, 59, 61, 67, 71]

        # v3: ISC-style constant recognition using mpf for accuracy
        targets = {
            "pi": mp.pi, "e": mp.e, "phi": mp.phi,
            "sqrt2": mp.sqrt(2), "sqrt3": mp.sqrt(3), "sqrt5": mp.sqrt(5),
            "ln2": mp.ln(2), "ln3": mp.ln(3),
            "euler": mp.euler, "catalan": mp.catalan,
            "apery": mp.zeta(3), "pi^2/6": mp.pi**2 / 6,
            "pi/4": mp.pi / 4, "1/pi": 1 / mp.pi,
            "1/phi": 1 / mp.phi,
        }
        multipliers_mpf = []
        for p in range(-4, 5):
            for q in range(1, 5):
                if p == 0:
                    continue
                multipliers_mpf.append(mp.mpf(p) / mp.mpf(q))

        for _ in range(budget):
            strategy = self.rng.choice([
                "factorial", "factorial", "fibonacci", "prime_mix",
                "exponential", "alt_factorial",
            ])

            if strategy == "factorial":
                k = self.rng.choice([1, -1, 2, -2, 3])
                b_const = self.rng.randint(1, 6)
                def a_func(n, _k=k):
                    f = 1
                    for i in range(1, max(n, 1) + 1):
                        f *= i
                    return _k * f
                def b_func(n, _b=b_const):
                    return _b
                label = f"cf_fact_k{k}_b{b_const}"
                expr = f"GCF a(n)={k}·n!, b(n)={b_const}"

            elif strategy == "fibonacci":
                k = self.rng.choice([1, -1, 2, -2])
                b_lin = self.rng.randint(0, 3)
                b_const = self.rng.randint(1, 5)
                def a_func(n, _k=k):
                    a, b = 0, 1
                    for _ in range(max(n, 1)):
                        a, b = b, a + b
                    return _k * b
                def b_func(n, _bl=b_lin, _bc=b_const):
                    return _bl * n + _bc
                label = f"cf_fib_k{k}_b{b_lin}n+{b_const}"
                expr = f"GCF a(n)={k}·F(n), b(n)={b_lin}n+{b_const}"

            elif strategy == "exponential":
                base = self.rng.choice([2, 3])
                k = self.rng.choice([1, -1])
                b_const = self.rng.randint(1, 5)
                def a_func(n, _k=k, _base=base):
                    return _k * (_base ** min(n, 50))  # cap to avoid overflow
                def b_func(n, _b=b_const):
                    return _b * n + 1
                label = f"cf_exp_{base}^n_k{k}_b{b_const}"
                expr = f"GCF a(n)={k}·{base}^n, b(n)={b_const}n+1"

            else:  # prime_mix
                alpha = self.rng.choice([-3, -2, -1, 1, 2, 3])
                b_const = self.rng.randint(1, 4)
                def a_func(n, _a=alpha, _p=SMALL_PRIMES):
                    p = _p[n % len(_p)]
                    return _a * n * n + p
                def b_func(n, _b=b_const):
                    return _b
                label = f"cf_pmix_a{alpha}_b{b_const}"
                expr = f"GCF a(n)={alpha}n²+prime(n), b(n)={b_const}"
            # v4.3: Override for alternating factorial strategy
            if strategy == "alt_factorial":
                k = self.rng.choice([1, 2, 3])
                b_const = self.rng.randint(1, 8)
                def a_func(n, _k=k):
                    f = 1
                    for i in range(1, max(n, 1) + 1):
                        f *= i
                    return ((-1) ** n) * _k * f
                def b_func(n, _b=b_const):
                    return _b
                label = f"cf_altfact_k{k}_b{b_const}"
                expr = f"GCF a(n)=(-1)^n\u00b7{k}\u00b7n!, b(n)={b_const}"
            try:
                val = _evaluate_gcf(a_func, b_func, depth=200, prec=self.prec)
                # Convergence test: compare depth 200 vs depth 100
                val2 = _evaluate_gcf(a_func, b_func, depth=100, prec=self.prec)
                conv_err = float(abs(val - val2))
                val_f = float(val)
            except Exception:
                continue

            if not (1e-15 < abs(val_f) < 1e15):
                continue
            if val_f != val_f:  # NaN
                continue
            if conv_err > 1e-8:
                continue  # doesn't converge

            # v3: ISC-style constant matching with proper mpf
            best_match, best_error = None, float('inf')
            best_const = None
            for name, tval in targets.items():
                for mult in multipliers_mpf:
                    e = float(abs(val * mult - tval))
                    if e < best_error:
                        best_error = e
                        best_const = name
                        best_match = (
                            f"{float(mult)}*CF={name}" if mult != 1 else name
                        )

            is_known = best_error < 1e-10
            # Also check if value is a simple rational
            is_rational = False
            for denom in range(1, 51):
                numer = round(val_f * denom)
                if abs(numer) <= 50 and abs(val_f - numer / denom) < 1e-10:
                    is_rational = True
                    break
            if is_rational:
                is_known = True
            # Check if value is a simple algebraic number (root of quadratic)
            is_simple_algebraic = False
            if not is_known:
                for a_coeff in range(1, 10):
                    for b_coeff in range(-20, 21):
                        for c_coeff in range(-20, 21):
                            test = a_coeff * val_f * val_f + b_coeff * val_f + c_coeff
                            if abs(test) < 1e-8:
                                is_simple_algebraic = True
                                break
                        if is_simple_algebraic:
                            break
                    if is_simple_algebraic:
                        break
                if is_simple_algebraic:
                    is_known = True
            is_novel_candidate = conv_err < 1e-10 and not is_known

            if not is_known and not is_novel_candidate:
                continue

            error = best_error if is_known else conv_err
            target = best_match if is_known else "novel_constant?"
            lit = None
            if is_rational:
                lit = "Rational number"
            elif is_known:
                lit = f"Algebraic transform of {best_const}"

            cj = Conjecture(
                id=_make_id(label),
                family="continued_fraction",
                expression=expr,
                value=val_f,
                target=target,
                error=error,
                params={"strategy": strategy, "label": label},
                source="nonpoly_cf_search",
                generation=self.generation,
                metadata={
                    "is_novel": is_novel_candidate,
                    "is_known_transform": is_known,
                    "cf_type": strategy,
                    "matched_constant": best_const if (is_known and not is_rational) else ("rational" if is_rational else None),
                    "literature_match": lit,
                    "convergence_error": conv_err,
                },
                provenance={
                    "method": f"nonpolynomial_cf_{strategy}",
                    "prec": self.prec,
                    "depth": 200,
                },
            )
            results.append(cj)

        return results

    # ---------------------------------------------------------------
    #  Strategy 8: Quadratic-b CF search (v4.3 — Lommel/Weber territory)
    # ---------------------------------------------------------------
    def generate_quadratic_b_cfs(self, budget: int = 25) -> list[Conjecture]:
        """Search GCFs with constant a(n), quadratic b(n) = alpha*n^2 + beta*n + gamma.

        v4.3: These CFs connect to Lommel and Weber functions, which are
        less explored than the linear-b Bessel/HG territory. They may
        yield genuinely novel constants.
        """
        results = []
        from .formulas import _evaluate_gcf

        for _ in range(budget):
            # Constant a(n), quadratic b(n)
            A = self.rng.choice([-5, -3, -2, -1, 1, 2, 3, 5])
            alpha = self.rng.choice([1, 2, 3, -1, -2])
            beta = self.rng.randint(-5, 5)
            gamma = self.rng.randint(1, 8)

            if alpha == 0:
                continue

            def a_func(n, _A=A):
                return _A
            def b_func(n, _a=alpha, _b=beta, _g=gamma):
                return _a * n * n + _b * n + _g

            try:
                val = _evaluate_gcf(a_func, b_func, depth=200, prec=self.prec)
                val2 = _evaluate_gcf(a_func, b_func, depth=100, prec=self.prec)
                conv_err = float(abs(val - val2))
                val_f = float(val)
            except Exception:
                continue

            if not (1e-15 < abs(val_f) < 1e15):
                continue
            if val_f != val_f:
                continue
            if conv_err > 1e-8:
                continue

            # ISC-style matching
            mp = self.mp
            targets = {
                "pi": mp.pi, "e": mp.e, "phi": mp.phi,
                "sqrt2": mp.sqrt(2), "sqrt3": mp.sqrt(3),
                "ln2": mp.ln(2), "euler": mp.euler,
                "catalan": mp.catalan, "apery": mp.zeta(3),
            }
            best_match, best_error = None, float('inf')
            best_const = None
            for name, tval in targets.items():
                for mult_p in range(-4, 5):
                    for mult_q in range(1, 5):
                        if mult_p == 0:
                            continue
                        m = mp.mpf(mult_p) / mp.mpf(mult_q)
                        e = float(abs(val * m - tval))
                        if e < best_error:
                            best_error = e
                            best_const = name
                            best_match = f"{float(m)}*CF={name}" if m != 1 else name

            is_known = best_error < 1e-10
            is_rational = False
            for denom in range(1, 51):
                numer = round(val_f * denom)
                if abs(numer) <= 50 and abs(val_f - numer / denom) < 1e-10:
                    is_rational = True
                    break
            if is_rational:
                is_known = True

            is_novel_candidate = conv_err < 1e-10 and not is_known
            if not is_known and not is_novel_candidate:
                continue

            error = best_error if is_known else conv_err
            target = best_match if is_known else "novel_constant?"
            an_coeffs = [A]
            bn_coeffs = [alpha, beta, gamma]

            cj = Conjecture(
                id=_make_id(f"qbcf_{A}_{alpha}_{beta}_{gamma}"),
                family="continued_fraction",
                expression=f"GCF a(n)={A}, b(n)={alpha}n\u00b2+{beta}n+{gamma}",
                value=val_f,
                target=target,
                error=error,
                params={"an": an_coeffs, "bn": bn_coeffs,
                        "strategy": "quadratic_b"},
                source="quadratic_b_cf_search",
                generation=self.generation,
                metadata={
                    "is_novel": is_novel_candidate,
                    "is_known_transform": is_known,
                    "cf_type": "quadratic_b",
                    "matched_constant": best_const if is_known else None,
                    "literature_match": f"Known transform of {best_const}" if is_known else None,
                    "convergence_error": conv_err,
                },
                provenance={
                    "method": "quadratic_b_cf",
                    "an": an_coeffs, "bn": bn_coeffs,
                    "prec": self.prec,
                },
            )
            results.append(cj)

        return results

    # ---------------------------------------------------------------
    #  Master generation: run all strategies
    # ---------------------------------------------------------------
    def generate_all(self, budget_per_strategy: int = 20) -> list[Conjecture]:
        """Run all generation strategies and return combined results."""
        all_conjectures = []
        strategies = [
            ("pi_series", self.generate_pi_series),
            ("continued_fractions", self.generate_continued_fractions),
            ("nonpoly_cfs", self.generate_nonpoly_cfs),
            ("quadratic_b_cfs", self.generate_quadratic_b_cfs),
            ("q_series", self.generate_q_series_identities),
            ("pslq", self.generate_pslq_relations),
            ("partitions", self.generate_partition_congruences),
            ("tau", self.generate_tau_patterns),
        ]
        for name, func in strategies:
            try:
                # v4.6: Double budget for linear-b CFs (provable via Bessel)
                strat_budget = budget_per_strategy
                if name == "continued_fractions":
                    strat_budget = budget_per_strategy * 2
                batch = func(budget=strat_budget)
                all_conjectures.extend(batch)
            except Exception as exc:
                all_conjectures.append(Conjecture(
                    id=_make_id(f"error_{name}_{self.generation}"),
                    family=name,
                    expression=f"[ERROR in {name}: {exc}]",
                    value=0, error=float('inf'),
                    source=f"{name}_error",
                    generation=self.generation,
                ))
        return all_conjectures

    # ---------------------------------------------------------------
    #  Helpers
    # ---------------------------------------------------------------
    def _good_params_for(self, family: str) -> list[dict]:
        return [p for p in self._good_params if p.get("_family") == family]
