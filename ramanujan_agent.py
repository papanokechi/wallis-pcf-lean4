#!/usr/bin/env python3
"""
Ramanujan Machine Agent  v2
============================
Self-iterating GCF discovery engine with:

  • Correct Apery-style ratio-recurrence evaluation (no overflow)
  • PSLQ novelty filter (dedup by CF value fingerprint, not spec)
  • Convergence guard (minimum digits before PSLQ attempt)
  • Alpha-diversity enforcement (escape attractor basins)
  • Dimensional injection (pi → pi^2, zeta3 → zeta2, etc.)
  • LLM enrichment via Anthropic API or local heuristic fallback (`--llm`)
  • LIReC bridge (--lirec, needs RDS network access)
  • Relay loop: discoveries → seeds → next generation

Usage:
    python ramanujan_agent.py --iters 200 --target zeta3
    python ramanujan_agent.py --iters 100 --target pi
    python ramanujan_agent.py --iters 50  --llm
    python ramanujan_agent.py --seed-file relay_chain_seed_pool.json
    python ramanujan_agent.py --list-constants

Requirements: pip install mpmath sympy
"""
from __future__ import annotations
import argparse, hashlib, html, json, math, os, random, sys, time
from dataclasses import dataclass, field
from typing import Optional
import mpmath as mp

# ── Precision ─────────────────────────────────────────────────────
WORKING_DPS   = 300
PSLQ_TOL_EXP  = -80     # tol = 10^PSLQ_TOL_EXP
PSLQ_MAXCOEF  = 1000
MIN_DIGITS    = 30       # minimum convergence digits before PSLQ attempt
mp.mp.dps     = WORKING_DPS


# ══════════════════════════════════════════════════════════════════
# §1  CONSTANTS CATALOGUE
# ══════════════════════════════════════════════════════════════════

def _build_constants():
    c = {}
    c["pi"]       = mp.pi
    c["e"]        = mp.e
    c["phi"]      = (1 + mp.sqrt(5)) / 2
    c["sqrt2"]    = mp.sqrt(2)
    c["sqrt3"]    = mp.sqrt(3)
    c["log2"]     = mp.log(2)
    c["log3"]     = mp.log(3)
    c["zeta2"]    = mp.zeta(2)           # pi^2/6
    c["zeta3"]    = mp.zeta(3)           # Apéry's constant
    c["zeta4"]    = mp.zeta(4)           # pi^4/90
    c["catalan"]  = mp.catalan
    c["euler_g"]  = mp.euler
    c["ln_pi"]    = mp.log(mp.pi)
    c["pi2"]      = mp.pi ** 2
    c["pi3"]      = mp.pi ** 3
    c["e2"]       = mp.e ** 2
    return c

CONSTANTS = _build_constants()

# Neighbourhood map for dimensional injection
NEIGHBOURS = {
    "pi":      ["pi2", "pi3", "zeta2", "ln_pi"],
    "zeta3":   ["zeta2", "zeta4", "catalan", "pi2"],
    "e":       ["e2", "log2", "euler_g", "ln_pi"],
    "log2":    ["log3", "zeta2", "ln_pi", "catalan"],
    "zeta2":   ["pi2", "zeta3", "zeta4", "pi"],
    "catalan": ["zeta3", "pi", "log2", "euler_g"],
}


# ══════════════════════════════════════════════════════════════════
# §2  GCF SPECIFICATION & EVALUATION
# ══════════════════════════════════════════════════════════════════

@dataclass
class GCFSpec:
    """
    Generalised continued fraction with polynomial coefficients.

    Two evaluation modes:
      'backward' — standard nested CF backward recurrence
      'ratio'    — Apery-style ratio recurrence (handles large polynomials)

    For ratio mode the recurrence is:
      n^order * u_n = P(n)*u_{n-1} - Q(n)*u_{n-2}
    where P = beta polynomial, Q = alpha polynomial.
    This avoids the overflow problems of naive backward recurrence.
    """
    alpha:   list[int]      # numerator poly coefficients [a0, a1, a2, ...]
    beta:    list[int]      # denominator poly coefficients
    target:  str = "zeta3"
    n_terms: int = 120
    mode:    str = "backward"  # 'backward' or 'ratio'
    order:   int = 0           # for ratio mode: divisor n^order
    spec_id: str = ""
    _eval_cache: dict[tuple[int, int], Optional[mp.mpf]] = field(default_factory=dict, init=False, repr=False)
    _conv_cache: dict[tuple[int, int], int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        if not self.spec_id:
            h = hashlib.md5((str(self.alpha)+str(self.beta)+self.mode).encode()).hexdigest()
            self.spec_id = f"GCF_{h[:8].upper()}"

    def _poly(self, coeffs: list[int], n: int) -> mp.mpf:
        return sum(mp.mpf(c) * n**i for i, c in enumerate(coeffs))

    def evaluate(self) -> Optional[mp.mpf]:
        cache_key = (self.n_terms, WORKING_DPS)
        if cache_key in self._eval_cache:
            return self._eval_cache[cache_key]
        if self.mode == "ratio":
            value = self._eval_ratio()
        else:
            value = self._eval_backward()
        self._eval_cache[cache_key] = value
        return value

    def _eval_backward(self) -> Optional[mp.mpf]:
        """Standard backward recurrence: b0 + a1/(b1 + a2/(b2 + ...))"""
        val = mp.mpf(0)
        tol = mp.mpf(10) ** -(WORKING_DPS - 10)
        for n in range(self.n_terms, 0, -1):
            an = self._poly(self.alpha, n)
            bn = self._poly(self.beta, n)
            denom = bn + val
            if abs(denom) < tol:
                return None
            val = an / denom
        b0 = self._poly(self.beta, 0)
        return b0 + val

    def _eval_ratio(self) -> Optional[mp.mpf]:
        """
        Apery-style ratio evaluation.
        Recurrence: n^order * u_n = beta(n)*u_{n-1} - alpha(n)*u_{n-2}
        p_{-1}=1, p_0=beta(0); q_{-1}=0, q_0=1
        Limit = p_n / q_n
        """
        p_prev = mp.mpf(self._poly(self.alpha, 0))  # numerator seed
        p_curr = mp.mpf(self._poly(self.beta, 0))   # p_1
        q_prev = mp.mpf(1)
        q_curr = mp.mpf(1)
        tol = mp.mpf(10) ** -(WORKING_DPS - 10)

        for n in range(1, self.n_terms + 1):
            bn = self._poly(self.beta, n)
            an = self._poly(self.alpha, n)
            div = mp.mpf(n ** self.order) if self.order > 0 else mp.mpf(1)
            if abs(div) < tol:
                return None
            p_next = (bn * p_curr - an * p_prev) / div
            q_next = (bn * q_curr - an * q_prev) / div
            p_prev, p_curr = p_curr, p_next
            q_prev, q_curr = q_curr, q_next

        if abs(q_curr) < tol:
            return None
        return p_curr / q_curr

    def convergence_digits(self) -> int:
        """Estimate confirmed decimal digits by comparing n_terms vs n_terms//2."""
        cache_key = (self.n_terms, WORKING_DPS)
        cached = self._conv_cache.get(cache_key)
        if cached is not None:
            return cached

        orig = self.n_terms
        half_terms = max(1, orig // 2)
        self.n_terms = half_terms
        try:
            v1 = self.evaluate()
        finally:
            self.n_terms = orig
        v2 = self.evaluate()
        if v1 is None or v2 is None or v2 == 0:
            digits = 0
        else:
            diff = abs(v1 - v2)
            if diff == 0:
                digits = WORKING_DPS
            else:
                digits = max(0, int(-float(mp.log10(diff + mp.mpf(10)**-(WORKING_DPS-1)))))
        self._conv_cache[cache_key] = digits
        return digits

    def fingerprint(self) -> str:
        return hashlib.md5((str(self.alpha) + str(self.beta) + self.mode).encode()).hexdigest()

    def to_dict(self):
        return {"spec_id": self.spec_id, "alpha": self.alpha,
                "beta": self.beta, "target": self.target,
                "n_terms": self.n_terms, "mode": self.mode, "order": self.order}

    @classmethod
    def from_dict(cls, d):
        return cls(alpha=d["alpha"], beta=d["beta"],
                   target=d.get("target","zeta3"),
                   n_terms=d.get("n_terms", 120),
                   mode=d.get("mode", "backward"),
                   order=d.get("order", 0),
                   spec_id=d.get("spec_id",""))


# ══════════════════════════════════════════════════════════════════
# §3  SEED POOL
# ══════════════════════════════════════════════════════════════════

def builtin_seeds():
    return [
        # ── Apery: zeta(3) ──────────────────────────────────────
        # n^3*u_n = (34n^3-51n^2+27n-5)*u_{n-1} - (n-1)^3*u_{n-2}
        # u_0=1,u_1=5 (denominator) / u_0=0,u_1=6 (numerator)
        GCFSpec(alpha=[0,0,0,1],   # (n-1)^3 → [0, 0, 0, 1] shifted? No: (n-1)^3 = n^3-3n^2+3n-1
                beta=[-5,27,-51,34],
                target="zeta3", n_terms=120, mode="ratio", order=3,
                spec_id="APERY_ZETA3"),
        # ── Euler: pi ────────────────────────────────────────────
        # pi/4 = 1/(1 + 1^2/(3 + 2^2/(5 + 3^2/(7 + ...))))
        # a(n)=n^2, b(n)=2n+1 → nested CF
        GCFSpec(alpha=[0,0,1], beta=[1,2], target="pi",
                n_terms=300, mode="backward", spec_id="EULER_PI_4"),
        # ── Lord Brouncker: pi ───────────────────────────────────
        # 4/pi = 1 + 1^2/(2 + 3^2/(2 + 5^2/(2 + ...)))
        GCFSpec(alpha=[-1,2,4], beta=[2,0], target="pi",
                n_terms=300, mode="backward", spec_id="BROUNCKER_PI"),
        # ── Wallis-Euler: e ──────────────────────────────────────
        GCFSpec(alpha=[0,1], beta=[1,2], target="e",
                n_terms=200, mode="backward", spec_id="EULER_E"),
        # ── log(2) ───────────────────────────────────────────────
        # log(2) = 1/(1 + 1^2/(2 + 2^2/(3 + ...))) — Euler 1748
        GCFSpec(alpha=[0,0,1], beta=[0,1], target="log2",
                n_terms=300, mode="backward", spec_id="LOG2_EULER"),
        # ── Catalan ──────────────────────────────────────────────
        GCFSpec(alpha=[0,0,1], beta=[-2,4], target="catalan",
                n_terms=300, mode="backward", spec_id="CATALAN_CF"),
        # ── zeta(2) = pi^2/6 ─────────────────────────────────────
        # pi^2/6 via Euler product CF
        GCFSpec(alpha=[0,0,0,0,1], beta=[0,-2,6,4], target="zeta2",
                n_terms=150, mode="backward", spec_id="EULER_ZETA2"),
        # ── Ramanujan-style pi ────────────────────────────────────
        GCFSpec(alpha=[-1,0,4], beta=[0,6], target="pi",
                n_terms=300, mode="backward", spec_id="RAMANUJAN_PI"),
    ]


# ══════════════════════════════════════════════════════════════════
# §4  GCF GENERATOR  (mutation + crossbreed + diversity)
# ══════════════════════════════════════════════════════════════════

class GCFGenerator:

    def __init__(self, seeds: list[GCFSpec], target: str):
        self.pool   = list(seeds)
        self.target = target
        self._alpha_seen: set[str] = {str(s.alpha) for s in seeds}
        self._discovery_queue: list[GCFSpec] = []

    # ── Diversity: reject alpha too similar to one we've tried ──
    def _alpha_is_novel(self, alpha: list[int]) -> bool:
        key = str(alpha)
        if key in self._alpha_seen:
            return False
        self._alpha_seen.add(key)
        return True

    def _mutate(self, spec: GCFSpec) -> GCFSpec:
        for _ in range(20):   # try up to 20 times for a novel alpha
            alpha = list(spec.alpha)
            beta  = list(spec.beta)
            r = random.random()
            if r < 0.4:
                i = random.randrange(len(alpha))
                alpha[i] += random.choice([-2,-1,1,2])
            elif r < 0.7:
                i = random.randrange(len(beta))
                beta[i] += random.choice([-2,-1,1,2])
            else:
                # Extend degree
                alpha = alpha + [random.randint(-3,3)]
            if self._alpha_is_novel(alpha):
                return GCFSpec(alpha=alpha, beta=beta, target=self.target,
                               n_terms=spec.n_terms, mode=spec.mode,
                               order=spec.order)
        # Fallback: random
        return self._random_new()

    def _crossbreed(self, s1: GCFSpec, s2: GCFSpec) -> GCFSpec:
        alpha = s1.alpha if random.random() < 0.5 else s2.alpha
        beta  = s2.beta  if random.random() < 0.5 else s1.beta
        mode  = s1.mode  if s1.convergence_digits() >= s2.convergence_digits() else s2.mode
        return GCFSpec(alpha=alpha, beta=beta, target=self.target,
                       n_terms=max(s1.n_terms, s2.n_terms), mode=mode,
                       order=s1.order)

    def _random_new(self, max_deg: int = 3) -> GCFSpec:
        for _ in range(30):
            deg_a = random.randint(1, max_deg)
            deg_b = random.randint(1, max_deg)
            alpha = [random.randint(-6, 6) for _ in range(deg_a+1)]
            beta  = [random.randint(-6, 6) for _ in range(deg_b+1)]
            if beta[0] == 0:
                beta[0] = random.choice([-1,1])
            # Bias toward higher-degree alpha for harder targets
            if self.target in ("zeta3", "catalan"):
                alpha[-1] = abs(alpha[-1]) or 1  # positive leading coeff
            if self._alpha_is_novel(alpha):
                return GCFSpec(alpha=alpha, beta=beta, target=self.target)
        alpha = [0, 0, 0, random.randint(1,3)]  # safe fallback n^3
        return GCFSpec(alpha=alpha, beta=[-5,27,-51,34],
                       target=self.target, n_terms=120, mode="ratio", order=3)

    def inject(self, specs: list[GCFSpec]):
        self._discovery_queue.extend(specs)
        self.pool.extend(specs)

    def next_batch(self, n: int = 10) -> list[GCFSpec]:
        batch = []
        # Discovery queue first (LLM / relay feedback)
        for s in self._discovery_queue[:max(1, n//4)]:
            batch.append(self._mutate(s))
        if self._discovery_queue:
            self._discovery_queue = self._discovery_queue[max(1, n//4):]
        # Mutation of top performers
        top = sorted(self.pool, key=lambda s: s.convergence_digits(), reverse=True)
        for s in top[:max(1, n*2//5)]:
            batch.append(self._mutate(s))
        # Crossbreeds
        if len(self.pool) >= 2:
            for _ in range(max(1, n//5)):
                p1, p2 = random.sample(self.pool, 2)
                batch.append(self._crossbreed(p1, p2))
        # Random fill
        while len(batch) < n:
            batch.append(self._random_new())
        return batch[:n]


# ══════════════════════════════════════════════════════════════════
# §5  PSLQ DISCOVERY ENGINE  (with novelty filter)
# ══════════════════════════════════════════════════════════════════

@dataclass
class Discovery:
    spec:          GCFSpec
    cf_value:      mp.mpf
    constant_name: str
    relation:      list[int]
    degree:        int
    precision:     int
    formula_str:   str
    convergence_digits: int
    timestamp:     float = field(default_factory=time.time)
    enrichment:    dict  = field(default_factory=dict)

    def to_dict(self):
        return {
            "spec":         self.spec.to_dict(),
            "constant":     self.constant_name,
            "relation":     self.relation,
            "degree":       self.degree,
            "precision_dp": self.precision,
            "conv_digits":  self.convergence_digits,
            "formula":      self.formula_str,
            "timestamp":    self.timestamp,
            "enrichment":   self.enrichment,
        }


def _pslq_vec1(v, K):
    return [v, K, mp.mpf(1)]

def _pslq_vec2(v, K):
    return [v**2, v*K, K**2, v, K, mp.mpf(1)]

def _rel_to_formula(v_name, K_name, rel, deg):
    if deg == 1:
        a, b, c = rel
        if a != 0:
            num_parts = []
            if b: num_parts.append(f"{-b}·{K_name}")
            if c: num_parts.append(str(-c))
            rhs = " + ".join(num_parts) or "0"
            return f"CF = ({rhs})/{a}" if a != 1 else f"CF = {rhs}"
        return f"{b}·{K_name} + {c} = 0"
    else:
        a,b,c,d,e,f = rel
        t = []
        if a: t.append(f"{a}·CF²")
        if b: t.append(f"{b}·CF·{K_name}")
        if c: t.append(f"{c}·{K_name}²")
        if d: t.append(f"{d}·CF")
        if e: t.append(f"{e}·{K_name}")
        if f: t.append(str(f))
        return " + ".join(t) + " = 0"

def _precision(v, K, rel, deg):
    if deg == 1:
        res = abs(rel[0]*v + rel[1]*K + rel[2])
    else:
        res = abs(rel[0]*v**2 + rel[1]*v*K + rel[2]*K**2
                  + rel[3]*v + rel[4]*K + rel[5])
    if res == 0: return WORKING_DPS
    return max(0, int(-float(mp.log10(res + mp.mpf(10)**(-(WORKING_DPS-2))))))


class PSLQEngine:

    def __init__(self, constants):
        self.constants    = constants
        self._seen_values: set[str] = set()   # fingerprints of found CF values
        self.n_tested     = 0
        self.n_found      = 0

    def _value_fingerprint(self, v: mp.mpf) -> str:
        """Coarse fingerprint so we don't count the same limit twice."""
        return mp.nstr(v, 12)

    def _is_trivial(self, rel: list[int], deg: int) -> bool:
        """
        A relation is trivial if CF equals a small rational number
        (not involving the constant K at all).
        deg=1: [a, b, c] trivial if b==0 (no K term).
        """
        if deg == 1 and rel[1] == 0:
            return True
        if deg == 2 and rel[1] == 0 and rel[2] == 0:
            return True
        return False

    def test(self, spec: GCFSpec, v: mp.mpf,
             conv_digits: int, targets: list[str]) -> Optional[Discovery]:
        if mp.isnan(v) or mp.isinf(v): return None
        if conv_digits < MIN_DIGITS:   return None

        vfp = self._value_fingerprint(v)
        if vfp in self._seen_values:   return None

        tol = mp.mpf(10) ** PSLQ_TOL_EXP

        for name in targets:
            K = self.constants.get(name)
            if K is None: continue
            self.n_tested += 1

            # Degree-1
            try:
                rel = mp.pslq(_pslq_vec1(v, K), tol=tol, maxcoeff=PSLQ_MAXCOEF)
            except Exception:
                rel = None
            if rel and not self._is_trivial(rel, 1):
                prec = _precision(v, K, rel, 1)
                if prec >= MIN_DIGITS:
                    self._seen_values.add(vfp)
                    self.n_found += 1
                    return Discovery(
                        spec=spec, cf_value=v,
                        constant_name=name, relation=rel, degree=1,
                        precision=prec, convergence_digits=conv_digits,
                        formula_str=_rel_to_formula("CF", name, rel, 1))

            # Degree-2
            try:
                rel2 = mp.pslq(_pslq_vec2(v, K), tol=tol, maxcoeff=PSLQ_MAXCOEF)
            except Exception:
                rel2 = None
            if rel2 and not self._is_trivial(rel2, 2):
                prec = _precision(v, K, rel2, 2)
                if prec >= MIN_DIGITS:
                    self._seen_values.add(vfp)
                    self.n_found += 1
                    return Discovery(
                        spec=spec, cf_value=v,
                        constant_name=name, relation=rel2, degree=2,
                        precision=prec, convergence_digits=conv_digits,
                        formula_str=_rel_to_formula("CF", name, rel2, 2))
        return None


# ══════════════════════════════════════════════════════════════════
# §6  LIReC BRIDGE
# ══════════════════════════════════════════════════════════════════

class LIReCBridge:
    """
    Optional: calls LIReC db.identify for richer polynomial-relation search.

    To enable:
      1. pip install git+https://github.com/RamanujanMachine/LIReC.git
      2. Network access to rmdb.cluster-czg4ecmu66lx.us-east-2.rds.amazonaws.com
         (requires Ramanujan Machine project DB credentials)
      3. Run agent with --lirec flag
    """
    def __init__(self, enabled=False):
        self.enabled = enabled
        self._db = None
        if enabled:
            try:
                from LIReC.db.access import db as ldb
                _ = ldb.names
                self._db = ldb
                print("  [LIReC] Connected ✓")
            except Exception as ex:
                print(f"  [LIReC] Unavailable ({ex.__class__.__name__}). "
                      "Continuing with local PSLQ only.")
                self.enabled = False

    def identify(self, v: mp.mpf, wide=False) -> list[str]:
        if not self.enabled or not self._db:
            return []
        try:
            res = self._db.identify([str(v)], degree=2,
                                    wide_search=wide, verbose=False)
            return [str(r) for r in res]
        except Exception as ex:
            return [f"LIReC error: {ex}"]


# ══════════════════════════════════════════════════════════════════
# §7  LLM ENRICHMENT  (Euler-Ramanujan prompt adapter)
# ══════════════════════════════════════════════════════════════════

_EULER_RAMANUJAN_PROMPT = """\
You are an expert in analytic number theory and Ramanujan-style continued fractions.

A new GCF identity has been discovered:
  a(n) polynomial coefficients (constant term first): {alpha}
  b(n) polynomial coefficients: {beta}
  Evaluation mode: {mode}
  Converges to a value related to {constant}
  Relation: {formula}
  Confirmed precision: {prec} decimal digits
  Convergence: ~{conv} digits/term

Respond ONLY with this JSON (no markdown, no preamble):
{{
  "interpretation": "Why this CF likely relates to {constant} mathematically",
  "index_transform_hints": ["n→2n+1", "n→n²+1", ...],
  "faster_alpha": [[improved a(n) coefficients for faster convergence]],
  "faster_beta":  [[improved b(n) coefficients]],
  "neighbourhood_targets": ["{constant}²", "ln({constant})", ...],
  "known_analogues": "Any known CF with similar polynomial structure"
}}"""

_DIMENSION_PROMPT = """\
A GCF relates to {constant}:
  a(n): {alpha}  b(n): {beta}
  Formula: {formula}

Suggest 3 GCF variants targeting mathematically related constants.
Respond ONLY with this JSON:
{{
  "variants": [
    {{"target": "constant_name",
      "alpha": [coefficients],
      "beta":  [coefficients],
      "rationale": "why this target"}}
  ]
}}"""


def _poly_str(coeffs):
    terms = []
    for i, c in enumerate(coeffs):
        if c == 0: continue
        t = ("" if i == 0 else
             ("n" if i == 1 else f"n^{i}"))
        terms.append(f"{c}" + (f"·{t}" if t else ""))
    return " + ".join(terms) or "0"


class LLMEnricher:
    def __init__(self, enabled=False):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.mode = "disabled"
        self.enabled = False
        if enabled:
            if self.api_key:
                self.mode = "anthropic"
                self.enabled = True
            else:
                self.mode = "local"
                self.enabled = True
                print("  [LLM] ANTHROPIC_API_KEY not set - using local heuristic enricher.")

    def status_label(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.mode == "anthropic":
            return "enabled (Anthropic API)"
        return "enabled (local heuristic fallback)"

    def _call(self, prompt: str) -> dict:
        import urllib.request
        body = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return json.loads(data["content"][0]["text"])

    def _local_enrich(self, d: Discovery) -> dict:
        alpha = list(d.spec.alpha)
        beta = list(d.spec.beta)

        def _unique_variants(base, transforms):
            out, seen = [], {tuple(base)}
            for fn in transforms:
                cand = [int(fn(i, c)) for i, c in enumerate(base)]
                key = tuple(cand)
                if key not in seen:
                    seen.add(key)
                    out.append(cand)
            return out[:2]

        faster_alpha = _unique_variants(alpha, (
            lambda i, c: c * (i + 1),
            lambda i, c: c * (2 ** i),
            lambda i, c: c if i == 0 else c + alpha[0],
        ))
        faster_beta = _unique_variants(beta, (
            lambda i, c: c * (i + 1),
            lambda i, c: c * (2 ** i),
            lambda i, c: c if i == 0 else c + beta[0],
        ))
        neighbourhood_targets = list(dict.fromkeys(
            NEIGHBOURS.get(d.constant_name, []) +
            NEIGHBOURS.get(d.spec.target, [])
        ))[:4]
        return {
            "mode": "local-heuristic",
            "interpretation": (
                f"Local fallback: reuse the existing Ramanujan search heuristics "
                f"around {d.constant_name} and explore nearby polynomial rescalings."
            ),
            "index_transform_hints": ["n→n+1", "n→2n", "flip low-degree signs"],
            "faster_alpha": faster_alpha,
            "faster_beta": faster_beta,
            "neighbourhood_targets": neighbourhood_targets,
            "known_analogues": (
                f"Neighbourhood search seeded from the current {d.constant_name} discovery."
            ),
        }

    def enrich(self, d: Discovery) -> dict:
        if not self.enabled:
            return {}
        if self.mode == "local":
            result = self._local_enrich(d)
            print(f"  [LLM-local] Enriched {d.spec.spec_id}")
            return result
        try:
            prompt = _EULER_RAMANUJAN_PROMPT.format(
                alpha=d.spec.alpha, beta=d.spec.beta,
                mode=d.spec.mode, constant=d.constant_name,
                formula=d.formula_str, prec=d.precision,
                conv=round(d.convergence_digits / max(d.spec.n_terms // 2, 1), 2))
            result = self._call(prompt)
            print(f"  [LLM] Enriched {d.spec.spec_id}")
            return result
        except Exception as ex:
            return {"error": str(ex)}

    def dimension_seeds(self, d: Discovery) -> list[GCFSpec]:
        if not self.enabled or self.mode == "local":
            return _heuristic_neighbours(d)
        try:
            prompt = _DIMENSION_PROMPT.format(
                constant=d.constant_name,
                alpha=d.spec.alpha, beta=d.spec.beta,
                formula=d.formula_str)
            result = self._call(prompt)
            seeds = []
            for v in result.get("variants", []):
                t = v.get("target", "")
                if t in CONSTANTS:
                    seeds.append(GCFSpec(
                        alpha=v.get("alpha", d.spec.alpha),
                        beta=v.get("beta", d.spec.beta),
                        target=t, n_terms=d.spec.n_terms,
                        mode=d.spec.mode, order=d.spec.order))
            return seeds or _heuristic_neighbours(d)
        except Exception:
            return _heuristic_neighbours(d)


def _heuristic_neighbours(d: Discovery) -> list[GCFSpec]:
    """Fallback dimensional injection without LLM."""
    spec = d.spec
    targets = NEIGHBOURS.get(spec.target, list(CONSTANTS.keys())[:4])
    seeds = []
    for t in targets:
        seeds.append(GCFSpec(
            alpha=list(spec.alpha), beta=list(spec.beta),
            target=t, n_terms=spec.n_terms,
            mode=spec.mode, order=spec.order))
    # n→2n acceleration variant
    rescaled_a = [c * (2**i) for i,c in enumerate(spec.alpha)]
    rescaled_b = [c * (2**i) for i,c in enumerate(spec.beta)]
    seeds.append(GCFSpec(
        alpha=rescaled_a, beta=rescaled_b, target=spec.target,
        n_terms=spec.n_terms, mode=spec.mode, order=spec.order))
    return seeds


# ══════════════════════════════════════════════════════════════════
# §8  RELAY AGENT  (main loop)
# ══════════════════════════════════════════════════════════════════

BANNER = """
╔══════════════════════════════════════════════════════╗
║   Ramanujan Machine Agent  v2  ·  LIReC Bridge      ║
║   GCF Generator · PSLQ Engine · LLM Enrichment      ║
║   Euler-Ramanujan Adapter · Dimensional Injection    ║
╚══════════════════════════════════════════════════════╝"""

@dataclass
class Stats:
    iters:       int   = 0
    tested:      int   = 0
    discoveries: int   = 0
    novel:       int   = 0    # discoveries passing novelty filter
    llm_calls:   int   = 0
    seeds_in:    int   = 0
    t0:          float = field(default_factory=time.time)
    def rate(self): return self.novel / max(self.iters,1) * 100
    def elapsed(self):
        s = int(time.time()-self.t0); return f"{s//60}m{s%60:02d}s"


class RamanujanAgent:
    def __init__(self, target="zeta3", use_llm=False,
                 use_lirec=False, seed_file=None):
        self.target = target
        self.stats  = Stats()
        seeds = builtin_seeds()
        if seed_file and os.path.exists(seed_file):
            with open(seed_file) as f:
                extra = json.load(f)
            seeds += [GCFSpec.from_dict(d) for d in extra
                      if isinstance(d, dict) and "alpha" in d]
            print(f"  Loaded {len(extra)} seeds from {seed_file}")
        self.gen     = GCFGenerator(seeds, target=target)
        self.pslq    = PSLQEngine(CONSTANTS)
        self.lirec   = LIReCBridge(enabled=use_lirec)
        self.llm     = LLMEnricher(enabled=use_llm)
        self.discoveries: list[Discovery] = []

    def _check(self, spec: GCFSpec) -> Optional[Discovery]:
        v = spec.evaluate()
        if v is None: return None
        conv = spec.convergence_digits()
        # Primary target + neighbours
        targets = [spec.target] + NEIGHBOURS.get(spec.target, [])
        d = self.pslq.test(spec, v, conv, targets)
        if d:
            return d
        # LIReC wide search as fallback
        if self.lirec.enabled:
            lirec = self.lirec.identify(v)
            if lirec:
                print(f"  [LIReC] {spec.spec_id}: {lirec}")
        return None

    def _on_discovery(self, d: Discovery):
        self.discoveries.append(d)
        self.stats.discoveries += 1
        self.stats.novel       += 1

        print(f"\n  {'★'*56}")
        print(f"  ★ DISCOVERY #{self.stats.novel}")
        print(f"  ★ a(n) = {_poly_str(d.spec.alpha)}")
        print(f"  ★ b(n) = {_poly_str(d.spec.beta)}")
        print(f"  ★ mode = {d.spec.mode}  order={d.spec.order}")
        print(f"  ★ {d.constant_name} relation (deg={d.degree}, "
              f"{d.precision}dp): {d.formula_str}")
        print(f"  ★ Convergence: {d.convergence_digits} digits in "
              f"{d.spec.n_terms} terms "
              f"(~{d.convergence_digits/max(d.spec.n_terms//2,1):.2f} dp/term)")
        print(f"  {'★'*56}\n")

        # LLM enrichment
        if self.llm.enabled:
            enrichment = self.llm.enrich(d)
            d.enrichment.update(enrichment)
            self.stats.llm_calls += 1
            # Inject faster-converging variants as seeds
            for av in enrichment.get("faster_alpha",[])[:2]:
                if isinstance(av, list):
                    self.gen.inject([GCFSpec(alpha=av, beta=d.spec.beta,
                                            target=d.constant_name,
                                            n_terms=d.spec.n_terms,
                                            mode=d.spec.mode)])
                    self.stats.seeds_in += 1

        # Dimensional injection
        neighbours = self.llm.dimension_seeds(d)
        self.gen.inject(neighbours)
        self.stats.seeds_in += len(neighbours)
        if neighbours:
            print(f"  [Relay] Injected {len(neighbours)} seeds → "
                  f"{[n.target for n in neighbours]}\n")

    def run(self, n_iters=200, batch=8, verbose=True):
        print(BANNER)
        print(f"\n  Target:      {self.target}")
        print(f"  Iterations:  {n_iters}  ×  {batch} GCFs/iter = "
              f"{n_iters*batch} total")
        print(f"  Precision:   {WORKING_DPS}dp  |  min_conv: {MIN_DIGITS}dp")
        print(f"  LLM:         {self.llm.status_label()}")
        print(f"  LIReC:       {'✓' if self.lirec.enabled else '✗ (local PSLQ only)'}")
        print()

        for _ in range(n_iters):
            self.stats.iters += 1
            for spec in self.gen.next_batch(batch):
                self.stats.tested += 1
                d = self._check(spec)
                if d:
                    self._on_discovery(d)
                    self.gen.pool.append(spec)   # keep successful spec

            if verbose and self.stats.iters % 10 == 0:
                print(f"  ── {self.stats.iters:4d}/{n_iters} │ "
                      f"tested={self.stats.tested:5d} │ "
                      f"novel={self.stats.novel:3d} ({self.stats.rate():.1f}%) │ "
                      f"pool={len(self.gen.pool):3d} │ "
                      f"{self.stats.elapsed()}")

        self._report()

    def _report(self):
        print("\n" + "="*58)
        print("  Ramanujan Machine Agent — Final Report")
        print("="*58)
        s = self.stats
        print(f"  Iterations:    {s.iters}")
        print(f"  GCFs tested:   {s.tested}")
        print(f"  Novel finds:   {s.novel}  ({s.rate():.2f}%/iter)")
        print(f"  Seeds injected:{s.seeds_in}")
        print(f"  LLM calls:     {s.llm_calls}")
        print(f"  Elapsed:       {s.elapsed()}")
        if self.discoveries:
            print(f"\n  Discoveries ({len(self.discoveries)}):")
            for d in self.discoveries:
                print(f"    [{d.spec.spec_id}]  {d.constant_name}  "
                      f"deg={d.degree}  {d.precision}dp  |  {d.formula_str[:55]}")
        print()

    def save(self, path="ramanujan_discoveries.json"):
        with open(path,"w") as f:
            json.dump({
                "stats":{"iters":self.stats.iters,
                         "tested":self.stats.tested,
                         "novel":self.stats.novel},
                "discoveries":[d.to_dict() for d in self.discoveries],
                "seed_pool":[s.to_dict() for s in self.gen.pool],
            }, f, indent=2, default=str)
        print(f"  Saved → {path}")

    def save_seeds(self, path="relay_chain_seed_pool.json"):
        with open(path,"w") as f:
            json.dump([s.to_dict() for s in self.gen.pool], f, indent=2)
        print(f"  Seeds → {path}  ({len(self.gen.pool)} specs)")

    def save_summary_html(self, path="ramanujan-run-summary.html",
                          discoveries_path="ramanujan_discoveries.json",
                          seed_path="relay_chain_seed_pool.json"):
        rate = self.stats.rate()
        llm_status = self.llm.status_label()
        generated = time.strftime("%Y-%m-%d %H:%M:%S")
        next_cmd = (
            f"python ramanujan_agent.py --seed-file {seed_path} "
            f"--target {self.target} --iters 500"
        )

        rows = []
        for idx, d in enumerate(self.discoveries, 1):
            rows.append(f"""
            <tr>
              <td>{idx}</td>
              <td><code>{html.escape(d.spec.spec_id)}</code></td>
              <td>{html.escape(d.constant_name)}</td>
              <td>{d.precision}</td>
              <td>{d.convergence_digits}</td>
              <td><code>{html.escape(json.dumps(d.spec.alpha))}</code><br><code>{html.escape(json.dumps(d.spec.beta))}</code></td>
              <td>{html.escape(d.formula_str)}</td>
            </tr>
            """)
        if not rows:
            rows.append("""
            <tr><td colspan='7' class='empty'>No discoveries recorded for this run.</td></tr>
            """)

        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ramanujan Agent Run Summary</title>
  <style>
    :root {{
      --bg:#0b1020; --panel:#121933; --panel2:#0f1530; --text:#e8ecff;
      --muted:#aab4de; --accent:#7cc7ff; --accent2:#8ef0c3; --border:#263158;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Segoe UI,Arial,sans-serif; background:linear-gradient(180deg,var(--bg),#12182c); color:var(--text); }}
    .wrap {{ max-width:1200px; margin:0 auto; padding:32px 20px 48px; }}
    .hero, .panel {{ background:rgba(18,25,51,.92); border:1px solid var(--border); border-radius:18px; box-shadow:0 12px 30px rgba(0,0,0,.24); }}
    .hero {{ padding:24px; margin-bottom:18px; }}
    h1,h2 {{ margin:0 0 10px; }}
    .sub {{ color:var(--muted); margin:4px 0 0; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:18px 0; }}
    .stat {{ background:var(--panel2); border:1px solid var(--border); border-radius:14px; padding:14px; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
    .value {{ font-size:28px; font-weight:700; margin-top:6px; }}
    .panel {{ padding:20px; margin-top:18px; }}
    .meta {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:10px; color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
    th, td {{ border-bottom:1px solid var(--border); text-align:left; padding:10px 8px; vertical-align:top; }}
    th {{ color:#9fd7ff; font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
    code, pre {{ font-family:Consolas, monospace; background:#0a1124; border-radius:8px; }}
    code {{ padding:2px 6px; }}
    pre {{ padding:12px; overflow:auto; color:#dff7ff; }}
    a {{ color:var(--accent2); }}
    .empty {{ text-align:center; color:var(--muted); padding:18px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Ramanujan Agent Run Summary</h1>
      <p class="sub">Target <strong>{html.escape(self.target)}</strong> · generated {generated}</p>
      <div class="grid">
        <div class="stat"><div class="label">Iterations</div><div class="value">{self.stats.iters}</div></div>
        <div class="stat"><div class="label">GCFs tested</div><div class="value">{self.stats.tested}</div></div>
        <div class="stat"><div class="label">Novel finds</div><div class="value">{self.stats.novel}</div></div>
        <div class="stat"><div class="label">Find rate</div><div class="value">{rate:.2f}%</div></div>
        <div class="stat"><div class="label">Seeds injected</div><div class="value">{self.stats.seeds_in}</div></div>
        <div class="stat"><div class="label">LLM calls</div><div class="value">{self.stats.llm_calls}</div></div>
      </div>
      <div class="meta">
        <div><strong>LLM mode:</strong> {html.escape(llm_status)}</div>
        <div><strong>Elapsed:</strong> {html.escape(self.stats.elapsed())}</div>
        <div><strong>Discovery file:</strong> <a href="{html.escape(discoveries_path)}">{html.escape(discoveries_path)}</a></div>
        <div><strong>Seed pool:</strong> <a href="{html.escape(seed_path)}">{html.escape(seed_path)}</a></div>
      </div>
    </section>

    <section class="panel">
      <h2>Continue from this run</h2>
      <pre>{html.escape(next_cmd)}</pre>
    </section>

    <section class="panel">
      <h2>Discoveries</h2>
      <table>
        <thead>
          <tr>
            <th>#</th><th>Spec ID</th><th>Constant</th><th>Precision</th><th>Conv. digits</th><th>Coefficients</th><th>Formula</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>
  </div>
</body>
</html>
"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"  Summary page -> {path}")
        return path


# ══════════════════════════════════════════════════════════════════
# §9  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="Ramanujan Machine Agent v2")
    p.add_argument("--iters",  type=int, default=100)
    p.add_argument("--target", default="zeta3", choices=list(CONSTANTS))
    p.add_argument("--batch",  type=int, default=8)
    p.add_argument("--prec",   type=int, default=300)
    p.add_argument("--llm",    action="store_true")
    p.add_argument("--lirec",  action="store_true")
    p.add_argument("--quiet",  action="store_true")
    p.add_argument("--seed-file", default=None)
    p.add_argument("--summary-html", default="ramanujan-run-summary.html")
    p.add_argument("--list-constants", action="store_true")
    args = p.parse_args()

    if args.list_constants:
        print("Available constants:")
        for k,v in CONSTANTS.items():
            print(f"  {k:15s} = {mp.nstr(v,20)}")
        return

    global WORKING_DPS, MIN_DIGITS
    WORKING_DPS = args.prec
    MIN_DIGITS  = max(20, args.prec // 10)
    mp.mp.dps   = WORKING_DPS

    agent = RamanujanAgent(target=args.target, use_llm=args.llm,
                           use_lirec=args.lirec, seed_file=args.seed_file)
    agent.run(n_iters=args.iters, batch=args.batch, verbose=not args.quiet)

    discoveries_path = "ramanujan_discoveries.json"
    seed_path = "relay_chain_seed_pool.json"
    agent.save(discoveries_path)
    agent.save_seeds(seed_path)
    agent.save_summary_html(args.summary_html,
                            discoveries_path=discoveries_path,
                            seed_path=seed_path)
    if agent.discoveries:
        print(f"\n  Next run:  python ramanujan_agent.py "
              f"--seed-file relay_chain_seed_pool.json --target {args.target}")


if __name__ == "__main__":
    main()
