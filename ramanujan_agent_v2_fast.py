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
import argparse, hashlib, heapq, html, json, math, os, platform, random, sys, time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional
import mpmath as mp

try:
    import sympy as sp
except Exception:
    sp = None

# Ensure the Unicode banner/status output does not crash on Windows cp1252
# or when stdout/stderr are piped through a non-UTF-8 host.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ── Precision ─────────────────────────────────────────────────────
WORKING_DPS   = 300
SCREEN_DPS    = 15       # cheap float screening before full PSLQ
PSLQ_DPS      = 80       # precision used for PSLQ (sufficient, not 300)
PSLQ_TOL_EXP  = -60      # tol = 10^PSLQ_TOL_EXP  (matched to PSLQ_DPS)
PSLQ_MAXCOEF  = 1000
PSLQ_SCREEN_COEFF = 4    # cheap low-precision integer-relation scan width
PSLQ_PRIMARY_MIN_SIGNAL = 3
PSLQ_DEG2_MIN_SIGNAL = 5
PSLQ_DEG2_EXTRA_DIGITS = 8
PSLQ_NEIGHBOUR_MIN_SIGNAL = 4
PSLQ_NEIGHBOUR_EXTRA_DIGITS = 12
PSLQ_NEIGHBOUR_LIMIT = 2
POOL_ELITE_SIZE = 48
POOL_MAX_SIZE = 160
MIN_DIGITS    = 30       # minimum convergence digits before PSLQ attempt
ADAPTIVE_CHECKPOINT_TERMS = 50
ADAPTIVE_MIN_TERMS = 50
ADAPTIVE_PROGRESS_RATIO = 0.20
AUTO_PARALLEL_MIN_JOBS = 200
AUTO_WORKER_MEDIUM_JOBS = 320
AUTO_WORKER_LARGE_JOBS = 640
AUTO_WORKER_MEDIUM_BATCH = 32
AUTO_WORKER_LARGE_BATCH = 96
AUTO_WORKER_CAP = 4
PERSISTENT_SEED_PATH = "ramanujan_persistent_seeds.json"
MAX_PERSISTENT_SEEDS = 64
GENETIC_PRIORITY_DRAW_RATE = 0.50
GENETIC_PRIORITY_BOOST = 0.35

# ── Near-miss detection ───────────────────────────────────────────
# A "near-miss" is a PSLQ relation that achieves high but not full
# precision.  These often indicate a missing constant in the basis.
NEAR_MISS_MIN_DIGITS = 15     # minimum digits to qualify as near-miss
NEAR_MISS_MAX_ENTRIES = 50    # cap stored near-misses per engine

# ── Deep search configuration ─────────────────────────────────────
DEEP_MIN_ADEG = 4
DEEP_MIN_BDEG = 4
DEEP_MAX_DEG  = 7
DEEP_N_TERMS  = 500
DEEP_MIN_PREC = 200
DEEP_COEFF_RANGE = 10
DEFAULT_SIGNATURE_PRIORITY_MAP: dict[str, dict[str, float]] = {
    "zeta3":   {"adeg=3|bdeg=3|mode=ratio|order=3": 5.0,
                "adeg=2|bdeg=2|mode=backward|order=0": 2.0},
    "pi":      {"adeg=2|bdeg=1|mode=backward|order=0": 5.0,
                "adeg=1|bdeg=1|mode=backward|order=0": 3.0},
    "e":       {"adeg=1|bdeg=1|mode=backward|order=0": 5.0},
    "log2":    {"adeg=2|bdeg=1|mode=backward|order=0": 3.0,
                "adeg=1|bdeg=1|mode=backward|order=0": 3.0},
    "catalan": {"adeg=2|bdeg=1|mode=backward|order=0": 4.0},
    "zeta5":   {"adeg=5|bdeg=5|mode=ratio|order=5": 5.0,
                "adeg=4|bdeg=4|mode=ratio|order=4": 3.0,
                "adeg=3|bdeg=3|mode=backward|order=0": 2.0},
    "zeta7":   {"adeg=7|bdeg=7|mode=ratio|order=7": 5.0,
                "adeg=6|bdeg=6|mode=ratio|order=6": 3.0,
                "adeg=5|bdeg=5|mode=ratio|order=5": 2.0},
}
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
    c["zeta5"]    = mp.zeta(5)           # open: irrationality unknown
    c["zeta6"]    = mp.zeta(6)           # pi^6/945
    c["zeta7"]    = mp.zeta(7)           # open: irrationality unknown
    c["catalan"]  = mp.catalan
    c["euler_g"]  = mp.euler
    c["ln_pi"]    = mp.log(mp.pi)
    c["pi2"]      = mp.pi ** 2
    c["pi3"]      = mp.pi ** 3
    c["pi5"]      = mp.pi ** 5
    c["pi7"]      = mp.pi ** 7
    c["e2"]       = mp.e ** 2
    return c

CONSTANTS = _build_constants()


def _system_metadata() -> dict[str, object]:
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count() or 1,
        "mpmath": getattr(mp, "__version__", "unknown"),
    }


def _auto_worker_count(n_iters: int, batch: int) -> int:
    cpu_cap = min(os.cpu_count() or 1, AUTO_WORKER_CAP)
    total_jobs = max(0, int(n_iters)) * max(0, int(batch))
    if cpu_cap <= 1:
        return 1
    if batch < 10 or total_jobs < AUTO_PARALLEL_MIN_JOBS:
        return 1
    if batch >= AUTO_WORKER_LARGE_BATCH or total_jobs >= AUTO_WORKER_LARGE_JOBS:
        return min(cpu_cap, 4)
    if batch >= AUTO_WORKER_MEDIUM_BATCH or total_jobs >= AUTO_WORKER_MEDIUM_JOBS:
        return min(cpu_cap, 2)
    return 1


def _effective_batch_size(batch: int, workers: int) -> int:
    return max(batch, workers * 8) if workers > 1 else batch


def _poly_degree_from_coeffs(coeffs: list[int] | None) -> int:
    coeff_list = list(coeffs or [])
    for idx in range(len(coeff_list) - 1, -1, -1):
        if coeff_list[idx] != 0:
            return idx
    return 0


def _structural_signature_from_spec(spec: "GCFSpec | dict[str, object]") -> str:
    if isinstance(spec, dict):
        alpha = list(spec.get("alpha", []))
        beta = list(spec.get("beta", []))
        mode = str(spec.get("mode", "backward"))
        order = int(spec.get("order", 0) or 0)
    else:
        alpha = list(spec.alpha)
        beta = list(spec.beta)
        mode = spec.mode
        order = spec.order
    return (
        f"adeg={_poly_degree_from_coeffs(alpha)}|"
        f"bdeg={_poly_degree_from_coeffs(beta)}|"
        f"mode={mode}|order={order}"
    )


def _merge_priority_maps(priority_map: Optional[dict[str, float]] = None,
                         target: str = "") -> dict[str, float]:
    # Start from per-target defaults if available, else empty
    defaults = DEFAULT_SIGNATURE_PRIORITY_MAP.get(target, {})
    merged = dict(defaults)
    for key, value in (priority_map or {}).items():
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            merged[str(key)] = weight
    return merged


def _closed_form_is_simple(text: object) -> bool:
    expr = str(text or "").strip()
    if not expr or len(expr) > 48:
        return False
    allowed = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-*/()[]{}_. ")
    return all(ch in allowed for ch in expr)


# Neighbourhood map for dimensional injection
NEIGHBOURS = {
    "pi":      ["pi2", "pi3", "zeta2", "ln_pi"],
    "zeta3":   ["zeta2", "zeta4", "catalan", "pi2", "zeta5"],
    "zeta5":   ["zeta3", "zeta4", "zeta6", "zeta7", "pi5", "pi3"],
    "zeta7":   ["zeta5", "zeta6", "zeta3", "pi7", "pi5"],
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
    _eval_cache: dict[tuple[object, ...], Optional[mp.mpf]] = field(default_factory=dict, init=False, repr=False)
    _conv_cache: dict[tuple[object, ...], int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        if not self.spec_id:
            h = hashlib.md5((str(self.alpha)+str(self.beta)+self.mode).encode()).hexdigest()
            self.spec_id = f"GCF_{h[:8].upper()}"

    def _poly(self, coeffs: list[int], n: int) -> mp.mpf:
        # Horner's rule with single n→mpf conversion
        n_mpf = mp.mpf(n)
        result = mp.mpf(coeffs[-1])
        for c in coeffs[-2::-1]:
            result = result * n_mpf + c   # c is int, mpmath auto-converts
        return result

    def _poly_f(self, coeffs: list[int], n: float) -> float:
        """Fast float version of Horner for SCREEN_DPS pre-filter."""
        result = float(coeffs[-1])
        for c in reversed(coeffs[:-1]):
            result = result * n + float(c)
        return result

    def evaluate(self, check_convergence: bool = True,
                 min_digits: Optional[int] = None) -> Optional[mp.mpf]:
        target_digits = int(MIN_DIGITS if min_digits is None else min_digits)
        cache_key = (self.n_terms, WORKING_DPS, int(bool(check_convergence)), target_digits)
        if cache_key in self._eval_cache:
            return self._eval_cache[cache_key]
        if check_convergence and not self._adaptive_convergence_ok(target_digits):
            self._eval_cache[cache_key] = None
            return None
        value = self._evaluate_with_terms(self.n_terms)
        self._eval_cache[cache_key] = value
        return value

    def _evaluate_with_terms(self, n_terms: int) -> Optional[mp.mpf]:
        if self.mode == "ratio":
            return self._eval_ratio(n_terms)
        return self._eval_backward(n_terms)

    def _adaptive_convergence_ok(self, min_digits: int) -> bool:
        checkpoint_terms = min(self.n_terms, ADAPTIVE_CHECKPOINT_TERMS)
        probe_terms = max(2, checkpoint_terms // 2)
        if checkpoint_terms <= probe_terms or checkpoint_terms < ADAPTIVE_MIN_TERMS:
            return True

        cache_key = ("adaptive", self.mode, self.n_terms, min_digits, WORKING_DPS)
        cached = self._conv_cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        check_dps = max(40, min(WORKING_DPS, max(PSLQ_DPS, min_digits * 2)))
        required_digits = max(4, int(math.ceil(min_digits * ADAPTIVE_PROGRESS_RATIO)))

        with mp.workdps(check_dps):
            v_probe = self._evaluate_with_terms(probe_terms)
            v_mid = self._evaluate_with_terms(checkpoint_terms)

        if v_probe is None or v_mid is None:
            self._conv_cache[cache_key] = 0
            return False

        diff = abs(v_mid - v_probe)
        if diff == 0:
            digits = check_dps
        else:
            eps = mp.mpf(10) ** -(check_dps - 6)
            digits = max(0, int(-float(mp.log10(diff + eps))))

        ok = digits >= required_digits
        self._conv_cache[cache_key] = 1 if ok else 0
        return ok

    def _eval_backward(self, n_terms: Optional[int] = None) -> Optional[mp.mpf]:
        """Standard backward recurrence: b0 + a1/(b1 + a2/(b2 + ...))

        SPEEDUP: fast float pre-screen rejects diverging CFs before
        paying the cost of full mpmath arithmetic.
        """
        n_total = self.n_terms if n_terms is None else max(1, int(n_terms))

        # ── Fast float pre-screen (50 terms) ─────────────────────────
        val_f = 0.0
        n_screen = min(50, n_total)
        try:
            for n in range(n_screen, 0, -1):
                an = self._poly_f(self.alpha, n)
                bn = self._poly_f(self.beta, n)
                denom = bn + val_f
                if abs(denom) < 1e-30:
                    return None
                val_f = an / denom
            b0_f = self._poly_f(self.beta, 0)
            result_f = b0_f + val_f
            if not (math.isfinite(result_f) and abs(result_f) < 1e15):
                return None   # clearly diverging — skip full precision
        except (ZeroDivisionError, OverflowError):
            return None

        # ── Full mpmath precision ─────────────────────────────────────
        val = mp.mpf(0)
        tol = mp.mpf(10) ** -(max(mp.mp.dps, 20) - 10)
        for n in range(n_total, 0, -1):
            an = self._poly(self.alpha, n)
            bn = self._poly(self.beta, n)
            denom = bn + val
            if abs(denom) < tol:
                return None
            val = an / denom
        b0 = self._poly(self.beta, 0)
        return b0 + val

    def _eval_ratio(self, n_terms: Optional[int] = None) -> Optional[mp.mpf]:
        """
        Apery-style ratio evaluation.
        Recurrence: n^order * u_n = beta(n)*u_{n-1} - alpha(n)*u_{n-2}
        p_{-1}=1, p_0=beta(0); q_{-1}=0, q_0=1
        Limit = p_n / q_n
        """
        n_total = self.n_terms if n_terms is None else max(1, int(n_terms))
        p_prev = mp.mpf(self._poly(self.alpha, 0))  # numerator seed
        p_curr = mp.mpf(self._poly(self.beta, 0))   # p_1
        q_prev = mp.mpf(1)
        q_curr = mp.mpf(1)
        tol = mp.mpf(10) ** -(max(mp.mp.dps, 20) - 10)

        for n in range(1, n_total + 1):
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

    def _eval_backward_f(self, n_terms: int) -> Optional[float]:
        """Pure-float backward eval for cheap screening (no mpmath)."""
        val = 0.0
        try:
            for n in range(n_terms, 0, -1):
                an = self._poly_f(self.alpha, n)
                bn = self._poly_f(self.beta, n)
                denom = bn + val
                if abs(denom) < 1e-30:
                    return None
                val = an / denom
            b0 = self._poly_f(self.beta, 0)
            result = b0 + val
            return result if math.isfinite(result) else None
        except (ZeroDivisionError, OverflowError):
            return None

    def _eval_ratio_f(self, n_terms: int) -> Optional[float]:
        """Pure-float ratio eval for cheap screening (no mpmath)."""
        try:
            p_prev = self._poly_f(self.alpha, 0)
            p_curr = self._poly_f(self.beta, 0)
            q_prev, q_curr = 1.0, 1.0
            for n in range(1, n_terms + 1):
                bn = self._poly_f(self.beta, n)
                an = self._poly_f(self.alpha, n)
                div = float(n ** self.order) if self.order > 0 else 1.0
                if abs(div) < 1e-30:
                    return None
                p_next = (bn * p_curr - an * p_prev) / div
                q_next = (bn * q_curr - an * q_prev) / div
                p_prev, p_curr = p_curr, p_next
                q_prev, q_curr = q_curr, q_next
                # Guard against blowup in ratio mode
                if abs(p_curr) > 1e100 or abs(q_curr) > 1e100:
                    p_prev /= 1e50; p_curr /= 1e50
                    q_prev /= 1e50; q_curr /= 1e50
            if abs(q_curr) < 1e-30:
                return None
            result = p_curr / q_curr
            return result if math.isfinite(result) else None
        except (ZeroDivisionError, OverflowError):
            return None

    def fast_screen_digits(self) -> int:
        """Cheap convergence estimate using pure Python floats — zero mpmath cost.
        Used for pool sorting and crossbreed selection."""
        screen_key = ("screen", self.n_terms)
        cached = self._conv_cache.get(screen_key)
        if cached is not None:
            return cached

        half = max(1, self.n_terms // 2)
        if self.mode == "ratio":
            v1 = self._eval_ratio_f(half)
            v2 = self._eval_ratio_f(self.n_terms)
        else:
            v1 = self._eval_backward_f(half)
            v2 = self._eval_backward_f(self.n_terms)

        if v1 is None or v2 is None:
            result = 0
        else:
            diff = abs(v1 - v2)
            if diff == 0.0:
                # Converged beyond float precision — definitely passes MIN_DIGITS;
                # return a high sentinel so full convergence_digits() runs.
                result = WORKING_DPS
            else:
                try:
                    result = max(0, int(-math.log10(diff + 1e-16)))
                except (ValueError, OverflowError):
                    result = 0
        self._conv_cache[screen_key] = result
        return result

    def convergence_digits(self) -> int:
        """Estimate confirmed decimal digits by comparing n_terms vs n_terms//2."""
        cache_key = (self.n_terms, WORKING_DPS)
        cached = self._conv_cache.get(cache_key)
        if cached is not None:
            return cached

        # ── Quick reject: if cheap screen shows < MIN_DIGITS, skip 300dp eval
        cheap = self.fast_screen_digits()
        if cheap < MIN_DIGITS:
            self._conv_cache[cache_key] = cheap
            return cheap

        # ── Adaptive short-circuit: if the 25→50 term checkpoint fails to
        # build even a small fraction of the target precision, abort early.
        if not self._adaptive_convergence_ok(MIN_DIGITS):
            self._conv_cache[cache_key] = 0
            return 0

        half_terms = max(1, self.n_terms // 2)
        v1 = self._evaluate_with_terms(half_terms)
        v2 = self._evaluate_with_terms(self.n_terms)
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

def _load_persistent_seed_entries(path: str = PERSISTENT_SEED_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict) and "alpha" in d and "beta" in d]


def _persist_promoted_seed(spec: GCFSpec, closed_form: str, signature: str,
                           path: str = PERSISTENT_SEED_PATH) -> bool:
    try:
        entries = _load_persistent_seed_entries(path)
        fingerprint = spec.fingerprint()
        if any(str(entry.get("_fingerprint", "")) == fingerprint for entry in entries):
            return False

        payload = spec.to_dict()
        payload.update({
            "_fingerprint": fingerprint,
            "_closed_form": closed_form,
            "_signature": signature,
            "_promoted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        entries.insert(0, payload)
        entries = entries[:MAX_PERSISTENT_SEEDS]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        return True
    except Exception:
        return False


def builtin_seeds():
    seeds = [
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
        # ── zeta(5) probe — degree-5 ratio (Apéry extrapolation) ──
        GCFSpec(alpha=[0,0,0,0,0,1],
                beta=[-7,85,-225,274,-120,1],
                target="zeta5", n_terms=500, mode="ratio", order=5,
                spec_id="ZETA5_PROBE"),
    ]

    seen = {seed.fingerprint() for seed in seeds}
    for payload in _load_persistent_seed_entries():
        try:
            spec = GCFSpec.from_dict(payload)
        except Exception:
            continue
        fingerprint = spec.fingerprint()
        if fingerprint in seen:
            continue
        seeds.append(spec)
        seen.add(fingerprint)
    return seeds


# ══════════════════════════════════════════════════════════════════
# §4  GCF GENERATOR  (mutation + crossbreed + diversity)
# ══════════════════════════════════════════════════════════════════

class GCFGenerator:

    def __init__(self, seeds: list[GCFSpec], target: str,
                 priority_map: Optional[dict[str, float]] = None,
                 deep_mode: bool = False):
        self.pool = list(seeds)
        self.target = target
        self.elite_size = POOL_ELITE_SIZE
        self.max_pool_size = POOL_MAX_SIZE
        self.priority_map = _merge_priority_maps(priority_map, target=target)
        self.success_signatures: dict[str, int] = {}
        self.persistent_seed_path = PERSISTENT_SEED_PATH
        self._alpha_seen: set[str] = {str(s.alpha) for s in seeds}
        self._discovery_queue: list[GCFSpec] = []
        self.deep_mode = deep_mode

    def _pool_score(self, spec: GCFSpec) -> int:
        return spec.fast_screen_digits()

    def _prune_pool(self):
        if len(self.pool) <= self.max_pool_size:
            return
        self.pool = heapq.nlargest(self.max_pool_size, self.pool, key=self._pool_score)

    def _elite_pool(self, limit: int | None = None) -> list[GCFSpec]:
        if not self.pool:
            return []
        keep = min(len(self.pool), limit or self.elite_size)
        return heapq.nlargest(keep, self.pool, key=self._pool_score)

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
        # Use cheap screen for crossbreed mode selection
        mode  = s1.mode  if s1.fast_screen_digits() >= s2.fast_screen_digits() else s2.mode
        return GCFSpec(alpha=alpha, beta=beta, target=self.target,
                       n_terms=max(s1.n_terms, s2.n_terms), mode=mode,
                       order=s1.order)

    def _priority_signature_choice(self) -> Optional[str]:
        if not self.priority_map or random.random() > GENETIC_PRIORITY_DRAW_RATE:
            return None
        weighted = [(sig, weight) for sig, weight in self.priority_map.items() if weight and weight > 0]
        if not weighted:
            return None
        labels = [sig for sig, _ in weighted]
        weights = [float(weight) for _, weight in weighted]
        return random.choices(labels, weights=weights, k=1)[0]

    def _random_from_signature(self, signature: str, max_deg: int = 3) -> Optional[GCFSpec]:
        parts = {}
        for piece in str(signature).split("|"):
            if "=" in piece:
                key, value = piece.split("=", 1)
                parts[key.strip()] = value.strip()

        try:
            deg_a = max(1, min(max_deg, int(parts.get("adeg", 1))))
            deg_b = max(1, min(max_deg + 1, int(parts.get("bdeg", 1))))
            mode = parts.get("mode", "backward")
            order = int(parts.get("order", 0) or 0)
        except (TypeError, ValueError):
            return None

        for _ in range(16):
            alpha = [random.randint(-6, 6) for _ in range(deg_a + 1)]
            beta = [random.randint(-6, 6) for _ in range(deg_b + 1)]
            if beta[0] == 0:
                beta[0] = random.choice([-1, 1])
            alpha[-1] = alpha[-1] or random.choice([-3, -2, -1, 1, 2, 3])
            beta[-1] = beta[-1] or random.choice([-3, -2, -1, 1, 2, 3])
            if self.target in ("zeta3", "catalan"):
                alpha[-1] = abs(alpha[-1]) or 1
            if self._alpha_is_novel(alpha):
                n_terms = 300 if mode == "backward" and deg_a >= 2 else 200 if mode == "backward" else 120
                return GCFSpec(alpha=alpha, beta=beta, target=self.target,
                               n_terms=n_terms, mode=mode, order=order)
        return None

    def _random_deep(self) -> GCFSpec:
        """Generate a high-order GCF for deep search (Pillar 1).

        Targets polynomial degrees >= DEEP_MIN_ADEG with large n_terms
        to probe unexplored regions of the coefficient space.
        """
        for _ in range(30):
            deg_a = random.randint(DEEP_MIN_ADEG, DEEP_MAX_DEG)
            deg_b = random.randint(DEEP_MIN_BDEG, DEEP_MAX_DEG)
            cr = DEEP_COEFF_RANGE

            # Choose mode: high-order targets favour ratio mode (Apéry-like)
            if self.target in ("zeta3", "zeta5", "zeta7", "zeta4", "zeta6"):
                mode = "ratio" if random.random() < 0.7 else "backward"
                order = deg_a if mode == "ratio" else 0
            else:
                mode = "backward" if random.random() < 0.6 else "ratio"
                order = deg_a if mode == "ratio" else 0

            alpha = [random.randint(-cr, cr) for _ in range(deg_a + 1)]
            beta = [random.randint(-cr, cr) for _ in range(deg_b + 1)]
            # Ensure leading coefficients and b0 are nonzero
            alpha[-1] = alpha[-1] or random.choice([-3, -2, -1, 1, 2, 3])
            beta[-1] = beta[-1] or random.choice([-3, -2, -1, 1, 2, 3])
            if beta[0] == 0:
                beta[0] = random.choice([-1, 1])

            # For zeta-like targets, bias leading alpha positive (Pochhammer structure)
            if self.target in ("zeta3", "zeta5", "zeta7"):
                alpha[-1] = abs(alpha[-1]) or 1

            if self._alpha_is_novel(alpha):
                return GCFSpec(alpha=alpha, beta=beta, target=self.target,
                               n_terms=DEEP_N_TERMS, mode=mode, order=order)
        # Fallback
        return self._random_new(max_deg=DEEP_MAX_DEG)

    def record_success(self, d: Discovery) -> dict[str, object]:
        signature = _structural_signature_from_spec(d.spec)
        self.success_signatures[signature] = self.success_signatures.get(signature, 0) + 1
        self.priority_map[signature] = min(8.0, self.priority_map.get(signature, 0.5) + GENETIC_PRIORITY_BOOST)

        closed_form = str((d.enrichment or {}).get("closed_form", "")).strip()
        promoted = False
        if d.precision >= 50 and _closed_form_is_simple(closed_form):
            promoted = _persist_promoted_seed(d.spec, closed_form, signature,
                                              path=self.persistent_seed_path)
        return {"signature": signature, "promoted": promoted, "closed_form": closed_form}

    def _random_new(self, max_deg: int = 3) -> GCFSpec:
        priority_signature = self._priority_signature_choice()
        if priority_signature:
            priority_spec = self._random_from_signature(priority_signature, max_deg=max_deg)
            if priority_spec is not None:
                return priority_spec

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
        self._prune_pool()

    def next_batch(self, n: int = 10) -> list[GCFSpec]:
        batch = []
        self._prune_pool()

        # Discovery queue first (LLM / relay feedback)
        for s in self._discovery_queue[:max(1, n//4)]:
            batch.append(self._mutate(s))
        if self._discovery_queue:
            self._discovery_queue = self._discovery_queue[max(1, n//4):]

        # Mutation of elite performers — use cheap screen without sorting the full pool.
        elite = self._elite_pool(max(self.elite_size, n))
        for s in elite[:max(1, n*2//5)]:
            batch.append(self._mutate(s))

        # Crossbreeds from the elite pool to limit overhead as the seed set grows.
        breeding_pool = elite if len(elite) >= 2 else self.pool
        if len(breeding_pool) >= 2:
            for _ in range(max(1, n//5)):
                p1, p2 = random.sample(breeding_pool, 2)
                batch.append(self._crossbreed(p1, p2))

        # Random fill (deep mode uses _random_deep for 50% of random slots)
        while len(batch) < n:
            if self.deep_mode and random.random() < 0.5:
                batch.append(self._random_deep())
            else:
                batch.append(self._random_new())
        return batch[:n]


# ══════════════════════════════════════════════════════════════════
# §4b  ARCHITECT GENERATOR  (Pillar 3: pattern-based synthesis)
# ══════════════════════════════════════════════════════════════════

# Known structural templates for mathematically motivated GCF families
_ARCHITECT_TEMPLATES: dict[str, list[dict]] = {
    "zeta3": [
        # Apéry-like: b(n) ~ 34n³-51n²+27n-5, a(n) ~ n³ (Pochhammer)
        {"alpha_base": [0, 0, 0, 1], "beta_base": [-5, 27, -51, 34],
         "mode": "ratio", "order": 3, "label": "apery_cubic"},
        # Zudilin variant: b(n) ~ 20n³-..., a(n) ~ n³
        {"alpha_base": [0, 0, 0, 1], "beta_base": [-3, 15, -25, 20],
         "mode": "ratio", "order": 3, "label": "zudilin_cubic"},
        # Higher-order probe: quintic b(n), cubic a(n)
        {"alpha_base": [0, 0, 0, 1, 0, 0], "beta_base": [0, 0, 0, 0, 0, 1],
         "mode": "ratio", "order": 5, "label": "quintic_probe"},
    ],
    "zeta5": [
        # Extrapolated from zeta3 Apéry: degree+2 heuristic
        {"alpha_base": [0, 0, 0, 0, 0, 1], "beta_base": [0, 0, 0, 0, 0, 0, 1],
         "mode": "ratio", "order": 5, "label": "apery_quintic"},
        # Mixed: high-order backward
        {"alpha_base": [0, 0, 0, 0, 1], "beta_base": [0, 0, 0, 0, 0, 1],
         "mode": "backward", "order": 0, "label": "deep_backward"},
    ],
    "pi": [
        # Ramanujan 1/π family
        {"alpha_base": [-1, 0, 4], "beta_base": [0, 6],
         "mode": "backward", "order": 0, "label": "ramanujan_pi"},
    ],
    "catalan": [
        # Catalan via degree-3 backward
        {"alpha_base": [0, 0, 0, 1], "beta_base": [-2, 4, 0, 1],
         "mode": "backward", "order": 0, "label": "cubic_catalan"},
    ],
    "zeta7": [
        # Extrapolated from zeta5 Apéry: degree+2 heuristic
        {"alpha_base": [0, 0, 0, 0, 0, 0, 0, 1],
         "beta_base": [0, 0, 0, 0, 0, 0, 0, 0, 1],
         "mode": "ratio", "order": 7, "label": "apery_septic"},
        # Lower-order probe
        {"alpha_base": [0, 0, 0, 0, 0, 1],
         "beta_base": [0, 0, 0, 0, 0, 0, 0, 1],
         "mode": "ratio", "order": 5, "label": "quintic_ratio_probe"},
        # High-order backward
        {"alpha_base": [0, 0, 0, 0, 0, 0, 1],
         "beta_base": [0, 0, 0, 0, 0, 0, 0, 1],
         "mode": "backward", "order": 0, "label": "deep_backward_7"},
    ],
}


class ArchitectGenerator:
    """Pillar 3: Propose GCF specs based on structural pattern analysis.

    Instead of random mutations, the architect reads successful formula
    signatures and generates structurally-informed candidates using known
    mathematical templates and learned perturbation strategies.
    """

    def __init__(self, target: str):
        self.target = target
        self.discovery_log: list[dict] = []  # signature -> spec snapshots
        self._template_index = 0

    def record(self, d: Discovery):
        """Record a discovery for pattern learning."""
        self.discovery_log.append({
            "alpha": list(d.spec.alpha),
            "beta": list(d.spec.beta),
            "mode": d.spec.mode,
            "order": d.spec.order,
            "degree": d.degree,
            "precision": d.precision,
            "constant": d.constant_name,
        })

    def propose(self, count: int = 4) -> list[GCFSpec]:
        """Generate structurally-informed GCF candidates."""
        specs: list[GCFSpec] = []

        # Strategy 1: Template perturbation
        templates = _ARCHITECT_TEMPLATES.get(self.target, [])
        if templates:
            for _ in range(min(count, len(templates))):
                tmpl = templates[self._template_index % len(templates)]
                self._template_index += 1
                spec = self._perturb_template(tmpl)
                if spec:
                    specs.append(spec)

        # Strategy 2: Discovery-seeded structural analogues
        if self.discovery_log:
            for entry in self.discovery_log[-3:]:
                analogue = self._structural_analogue(entry)
                if analogue:
                    specs.append(analogue)

        return specs[:count]

    def _perturb_template(self, tmpl: dict) -> Optional[GCFSpec]:
        """Create a perturbation of a known mathematical template."""
        alpha = list(tmpl["alpha_base"])
        beta = list(tmpl["beta_base"])

        # Controlled perturbation: small integer noise on coefficients
        for i in range(len(alpha)):
            if alpha[i] != 0 or random.random() < 0.3:
                alpha[i] += random.choice([-2, -1, 0, 0, 0, 1, 2])
        for i in range(len(beta)):
            if beta[i] != 0 or random.random() < 0.3:
                beta[i] += random.choice([-2, -1, 0, 0, 0, 1, 2])

        # Ensure structural integrity
        if all(c == 0 for c in alpha[1:]) or all(c == 0 for c in beta[1:]):
            return None

        mode = tmpl["mode"]
        order = tmpl["order"]
        n_terms = DEEP_N_TERMS if len(alpha) > 4 else 300
        return GCFSpec(alpha=alpha, beta=beta, target=self.target,
                       n_terms=n_terms, mode=mode, order=order)

    def _structural_analogue(self, entry: dict) -> Optional[GCFSpec]:
        """Create a structural analogue of a successful discovery.

        Key insight: if b(n) was cubic for zeta(3), try the same structure
        with small coefficient variations — resembling Pochhammer symbols.
        """
        alpha = list(entry["alpha"])
        beta = list(entry["beta"])

        # Degree escalation: add one more coefficient
        if random.random() < 0.4:
            alpha.append(random.choice([-1, 0, 1]))
            beta.append(random.choice([-1, 0, 1]))

        # Coefficient reflection: negate alternating terms
        if random.random() < 0.3:
            for i in range(0, len(beta), 2):
                beta[i] = -beta[i]

        # Scale shift: multiply by small factor
        scale = random.choice([1, 1, 2, 3])
        if scale > 1 and random.random() < 0.3:
            beta = [c * scale for c in beta]

        n_terms = DEEP_N_TERMS if len(alpha) > 4 else 300
        return GCFSpec(alpha=alpha, beta=beta, target=self.target,
                       n_terms=n_terms, mode=entry["mode"],
                       order=entry.get("order", 0))


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
        cf_approx = None
        try:
            if self.cf_value is not None and not mp.isnan(self.cf_value) and not mp.isinf(self.cf_value):
                cf_approx = mp.nstr(self.cf_value, 50)
        except Exception:
            cf_approx = None
        return {
            "spec":         self.spec.to_dict(),
            "constant":     self.constant_name,
            "relation":     self.relation,
            "degree":       self.degree,
            "precision_dp": self.precision,
            "conv_digits":  self.convergence_digits,
            "formula":      self.formula_str,
            "cf_approx":    cf_approx,
            "timestamp":    self.timestamp,
            "enrichment":   self.enrichment,
        }

    @classmethod
    def from_dict(cls, payload: dict, cf_value: Optional[mp.mpf] = None):
        approx = payload.get("cf_approx")
        if cf_value is None and approx not in (None, ""):
            try:
                cf_value = mp.mpf(str(approx))
            except Exception:
                cf_value = mp.mpf("nan")
        return cls(
            spec=GCFSpec.from_dict(payload["spec"]),
            cf_value=cf_value if cf_value is not None else mp.mpf("nan"),
            constant_name=payload["constant"],
            relation=list(payload["relation"]),
            degree=payload["degree"],
            precision=payload["precision_dp"],
            formula_str=payload["formula"],
            convergence_digits=payload["conv_digits"],
            timestamp=payload.get("timestamp", time.time()),
            enrichment=payload.get("enrichment", {}),
        )


def _pslq_vec1(v, K):
    return [v, K, mp.mpf(1)]

def _pslq_vec2(v, K):
    return [v**2, v*K, K**2, v, K, mp.mpf(1)]


# ── Multi-constant PSLQ (Pillar 2) ───────────────────────────────

# Groups of constants to try together for cross-constant coupling
MULTI_CONSTANT_GROUPS: dict[str, list[list[str]]] = {
    "zeta3": [["zeta3", "pi3"], ["zeta3", "pi2"], ["zeta3", "zeta5"],
              ["zeta3", "pi3", "pi2"], ["zeta3", "zeta5", "zeta7"]],
    "zeta5": [["zeta5", "zeta3"], ["zeta5", "pi5"], ["zeta5", "pi3"],
              ["zeta5", "zeta3", "pi5"], ["zeta5", "zeta7"],
              ["zeta5", "zeta3", "zeta7"]],
    "zeta7": [["zeta7", "zeta5"], ["zeta7", "zeta3"], ["zeta7", "pi7"],
              ["zeta7", "zeta5", "zeta3"], ["zeta7", "pi7", "pi5"],
              ["zeta7", "zeta5", "zeta3", "pi7"]],
    "pi":    [["pi", "log2"], ["pi", "euler_g"]],
    "e":     [["e", "pi"], ["e", "log2"]],
    "log2":  [["log2", "pi"], ["log2", "euler_g"]],
    "catalan": [["catalan", "zeta3"], ["catalan", "pi2"]],
}


def _pslq_vec_multi(v: mp.mpf, constants: list[mp.mpf]) -> list[mp.mpf]:
    """Build PSLQ basis: [CF, K1, K2, ..., 1] for linear multi-constant search."""
    return [v] + list(constants) + [mp.mpf(1)]


def _multi_rel_to_formula(v_name: str, const_names: list[str],
                          rel: list[int]) -> str:
    """Format a multi-constant relation as a human-readable equation."""
    # rel = [a_cf, a_K1, a_K2, ..., a_const]
    terms = []
    if rel[0]:
        terms.append(f"{rel[0]}·{v_name}")
    for i, name in enumerate(const_names):
        coeff = rel[i + 1]
        if coeff:
            terms.append(f"{coeff}·{name}")
    if rel[-1]:
        terms.append(str(rel[-1]))
    return " + ".join(terms) + " = 0" if terms else "0 = 0"


def _multi_precision(v: mp.mpf, constants: list[mp.mpf],
                     rel: list[int]) -> int:
    """Compute precision of a multi-constant relation."""
    res = rel[0] * v
    for i, K in enumerate(constants):
        res += rel[i + 1] * K
    res += rel[-1]
    res = abs(res)
    if res == 0:
        return WORKING_DPS
    return max(0, int(-float(mp.log10(res + mp.mpf(10) ** (-(WORKING_DPS - 2))))))


def _multi_rel_is_trivial(rel: list[int]) -> bool:
    """Trivial if CF coefficient is zero OR all constant coefficients are zero.

    A relation like 1·CF + 0·K1 + 0·K2 + -1 = 0 (i.e. CF=1) is trivial
    because it doesn't actually couple CF to any constant.
    """
    if rel[0] == 0:
        return True
    # Check that at least one constant coefficient (indices 1..n-1) is nonzero
    # rel = [a_cf, a_K1, a_K2, ..., a_const]
    constant_coeffs = rel[1:-1]  # exclude CF coeff and free term
    return all(c == 0 for c in constant_coeffs)

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


def _fraction_str(value: Fraction | int) -> str:
    frac = value if isinstance(value, Fraction) else Fraction(int(value), 1)
    if frac.denominator == 1:
        return str(frac.numerator)
    return f"{frac.numerator}/{frac.denominator}"


def _constant_label(name: str) -> str:
    return {
        "pi": "pi",
        "e": "e",
        "phi": "phi",
        "sqrt2": "sqrt(2)",
        "sqrt3": "sqrt(3)",
        "log2": "log(2)",
        "log3": "log(3)",
        "zeta2": "zeta(2)",
        "zeta3": "zeta(3)",
        "zeta4": "zeta(4)",
        "zeta5": "zeta(5)",
        "zeta6": "zeta(6)",
        "zeta7": "zeta(7)",
        "catalan": "Catalan",
        "euler_g": "EulerGamma",
        "ln_pi": "log(pi)",
        "pi2": "pi**2",
        "pi3": "pi**3",
        "pi5": "pi**5",
        "pi7": "pi**7",
        "e2": "e**2",
    }.get(name, name)


def _format_linear_closed_form(scale: Fraction, constant_name: str, offset: Fraction) -> str:
    label = _constant_label(constant_name)
    pieces: list[str] = []

    if scale:
        if scale == 1:
            pieces.append(label)
        elif scale == -1:
            pieces.append(f"-{label}")
        else:
            coeff = _fraction_str(abs(scale))
            prefix = "-" if scale < 0 else ""
            pieces.append(f"{prefix}{coeff}*{label}")

    if offset:
        offset_text = _fraction_str(abs(offset))
        if pieces:
            pieces.append(f"{'+' if offset > 0 else '-'} {offset_text}")
        else:
            pieces.append(_fraction_str(offset))

    return " ".join(pieces) or "0"


def _simple_identify_text(value: mp.mpf) -> Optional[str]:
    try:
        text = str(mp.identify(value)).strip()
    except Exception:
        return None
    if not text:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    allowed = set("0123456789+-*/() ")
    if len(text) > 40 or any(ch not in allowed for ch in text):
        return None
    return text


def _sympy_constant_expr(name: str):
    if sp is None:
        return None
    return {
        "pi": sp.pi,
        "e": sp.E,
        "phi": (1 + sp.sqrt(5)) / 2,
        "sqrt2": sp.sqrt(2),
        "sqrt3": sp.sqrt(3),
        "log2": sp.log(2),
        "log3": sp.log(3),
        "zeta2": sp.zeta(2),
        "zeta3": sp.zeta(3),
        "zeta4": sp.zeta(4),
        "catalan": sp.Catalan,
        "euler_g": sp.EulerGamma,
        "ln_pi": sp.log(sp.pi),
        "pi2": sp.pi**2,
        "pi3": sp.pi**3,
        "e2": sp.E**2,
    }.get(name)


class SymbolicSimplifier:
    """Attach a compact closed-form hypothesis to numerical discoveries."""

    def __init__(self):
        self.enabled = True
        self.sympy_available = sp is not None

    def _linear_hypothesis(self, d: Discovery) -> dict:
        if d.degree != 1 or len(d.relation) != 3:
            return {}
        a, b, c = (int(x) for x in d.relation)
        if a == 0:
            return {}
        scale = Fraction(-b, a)
        offset = Fraction(-c, a)
        kind = "rational_multiple" if scale and not offset else (
            "affine_target" if scale else "rational_constant"
        )
        return {
            "closed_form": _format_linear_closed_form(scale, d.constant_name, offset),
            "closed_form_source": "pslq_linear",
            "closed_form_kind": kind,
            "target_multiple": _fraction_str(scale),
            "target_offset": _fraction_str(offset),
        }

    def _ratio_hint(self, d: Discovery) -> Optional[str]:
        K = CONSTANTS.get(d.constant_name)
        if K in (None, 0):
            return None
        try:
            return _simple_identify_text(d.cf_value / K)
        except Exception:
            return None

    def _sympy_hypothesis(self, d: Discovery) -> dict:
        if not self.sympy_available:
            return {}
        K = _sympy_constant_expr(d.constant_name)
        if K is None:
            return {}

        x = sp.Symbol("CF", real=True)
        try:
            if d.degree == 1 and len(d.relation) == 3:
                a, b, c = (sp.Integer(int(v)) for v in d.relation)
                exprs = [sp.solve(sp.Eq(a * x + b * K + c, 0), x)]
            elif d.degree == 2 and len(d.relation) == 6:
                a, b, c, d1, e, f = (sp.Integer(int(v)) for v in d.relation)
                poly = a*x**2 + b*x*K + c*K**2 + d1*x + e*K + f
                exprs = [sp.solve(sp.Eq(poly, 0), x)]
            else:
                return {}
        except Exception:
            return {}

        roots = []
        for chunk in exprs:
            if isinstance(chunk, list):
                roots.extend(chunk)
            elif chunk is not None:
                roots.append(chunk)

        best_expr = None
        best_err = None
        for root in roots:
            try:
                simplified = sp.simplify(root)
                numeric = sp.N(simplified, 80)
                imag_part = sp.N(sp.im(numeric), 30)
                if abs(float(imag_part)) > 1e-20:
                    continue
                real_part = sp.N(sp.re(numeric), 80)
                err = abs(d.cf_value - mp.mpf(str(real_part)))
            except Exception:
                continue
            if best_err is None or err < best_err:
                best_expr = simplified
                best_err = err

        if best_expr is None:
            return {}

        threshold = mp.mpf(10) ** (-min(max(12, d.precision // 2), 30))
        if best_err is not None and best_err > threshold:
            return {}

        expr_text = sp.sstr(best_expr)
        if not expr_text or len(expr_text) > 120:
            return {}
        return {
            "closed_form": expr_text,
            "closed_form_source": "sympy_relation",
            "closed_form_kind": "algebraic_root",
        }

    def refine(self, d: Discovery) -> dict:
        info = self._linear_hypothesis(d)
        ratio_hint = self._ratio_hint(d)
        if ratio_hint:
            info["identify_ratio"] = ratio_hint

        sympy_info = self._sympy_hypothesis(d)
        if sympy_info:
            current = str(info.get("closed_form", ""))
            candidate = str(sympy_info.get("closed_form", ""))
            if not current or (candidate and len(candidate) <= len(current) + 4):
                info.update(sympy_info)

        return info


class PSLQEngine:

    def __init__(self, constants):
        self.constants = constants
        self._constant_cache: dict[str, dict[str, object]] = {}
        for name, value in constants.items():
            try:
                value_f = float(value)
            except (TypeError, ValueError, OverflowError):
                value_f = None
            self._constant_cache[name] = {"mpf": mp.mpf(value), "float": value_f}

        self._small_linear_coeffs = [
            (a, b, c)
            for a in range(-PSLQ_SCREEN_COEFF, PSLQ_SCREEN_COEFF + 1)
            for b in range(-PSLQ_SCREEN_COEFF, PSLQ_SCREEN_COEFF + 1)
            for c in range(-2 * PSLQ_SCREEN_COEFF, 2 * PSLQ_SCREEN_COEFF + 1)
            if a != 0 and not (b == 0 and c == 0)
        ]
        self._seen_values: set[str] = set()   # fingerprints of found CF values
        self.n_tested = 0
        self.n_found = 0
        self.n_pslq_calls = 0
        self.n_degree2_calls = 0
        self.n_prefilter_skips = 0
        self.n_neighbour_attempts = 0
        self.n_neighbour_skips = 0
        # Near-miss tracking: PSLQ relations with partial but not full precision
        self.near_misses: list[dict] = []

    def _record_near_miss(self, spec: GCFSpec, constant_name: str,
                          relation: list[int], degree: int,
                          precision: int, conv_digits: int,
                          formula: str, basis_type: str = "single"):
        """Record a PSLQ relation that has partial precision (near-miss)."""
        if len(self.near_misses) >= NEAR_MISS_MAX_ENTRIES:
            # Evict the lowest-precision near-miss
            self.near_misses.sort(key=lambda x: x["precision"], reverse=True)
            self.near_misses = self.near_misses[:NEAR_MISS_MAX_ENTRIES - 1]
        max_coeff = max(abs(c) for c in relation) if relation else 0
        # Significance score: higher precision, lower coefficients = more interesting
        sig_score = precision / max(1, math.log2(max_coeff + 1))
        self.near_misses.append({
            "spec_id": spec.spec_id,
            "alpha": list(spec.alpha),
            "beta": list(spec.beta),
            "mode": spec.mode,
            "order": spec.order,
            "constant": constant_name,
            "relation": list(relation),
            "degree": degree,
            "precision": precision,
            "conv_digits": conv_digits,
            "formula": formula,
            "basis_type": basis_type,
            "max_coeff": max_coeff,
            "significance_score": round(sig_score, 2),
            "timestamp": time.time(),
        })

    def _value_fingerprint(self, v: mp.mpf) -> str:
        """Coarse fingerprint so we don't count the same limit twice."""
        return mp.nstr(v, 12)

    def _is_trivial(self, rel: list[int], deg: int) -> bool:
        """
        A relation is trivial if CF equals a small rational number
        (not involving the constant K at all).
        deg=1: [a, b, c] trivial if b==0 (no K term).
        deg=2: [a, b, c, d, e] trivial if b==0 and c==0 (no CF·K or CF terms),
               OR if CF is rational — any degree-2 relation with a rational CF
               is automatically satisfied via trivial factoring.
        """
        if deg == 1 and rel[1] == 0:
            return True
        if deg == 2 and rel[1] == 0 and rel[2] == 0:
            return True
        return False

    def _is_cf_rational(self, v: mp.mpf, max_denom: int = 10000) -> bool:
        """Check if CF value is a rational p/q with small denominator.
        If rational, degree-2 PSLQ relations are trivially satisfied."""
        with mp.workdps(min(mp.mp.dps, 200)):
            try:
                rel = mp.pslq([v, mp.mpf(1)], maxcoeff=max_denom, maxsteps=500)
                if rel and rel[0] != 0:
                    expected = mp.mpf(-rel[1]) / mp.mpf(rel[0])
                    diff = abs(v - expected)
                    return diff < mp.mpf(10) ** (-100)
            except Exception:
                pass
        return False

    def _cheap_linear_signal(self, v: mp.mpf, name: str) -> int:
        """Cheap float-based proxy for whether a low-degree PSLQ relation is plausible."""
        info = self._constant_cache.get(name)
        if info is None:
            return 0
        kf = info.get("float")
        if kf is None:
            return 0
        try:
            vf = float(v)
        except (TypeError, ValueError, OverflowError):
            return 0
        if not (math.isfinite(vf) and math.isfinite(kf)):
            return 0

        best = min(abs(vf), abs(vf - 1.0), abs(vf + 1.0), abs(vf - 2.0), abs(vf + 2.0))
        for a, b, c in self._small_linear_coeffs:
            residual = abs(a * vf + b * kf + c)
            if residual < best:
                best = residual
                if best < 1e-12:
                    break
        if best == 0.0:
            return SCREEN_DPS
        return max(0, int(-math.log10(best + 1e-16)))

    def _should_try_degree2(self, conv_digits: int, signal_digits: int) -> bool:
        return signal_digits >= PSLQ_DEG2_MIN_SIGNAL or conv_digits >= MIN_DIGITS + PSLQ_DEG2_EXTRA_DIGITS

    def _should_try_neighbours(self, conv_digits: int, primary_signal: int) -> bool:
        return primary_signal >= PSLQ_NEIGHBOUR_MIN_SIGNAL or conv_digits >= MIN_DIGITS + PSLQ_NEIGHBOUR_EXTRA_DIGITS

    def _candidate_targets(self, spec: GCFSpec, targets: list[str], v: mp.mpf,
                           conv_digits: int) -> list[tuple[str, int, bool]]:
        ordered = [name for name in dict.fromkeys(targets) if name in self._constant_cache]
        if not ordered:
            return []

        primary = spec.target if spec.target in self._constant_cache else ordered[0]
        primary_signal = self._cheap_linear_signal(v, primary)
        if primary_signal < PSLQ_PRIMARY_MIN_SIGNAL and conv_digits < MIN_DIGITS + 2:
            self.n_prefilter_skips += 1
            return []

        selected: list[tuple[str, int, bool]] = [
            (primary, primary_signal, self._should_try_degree2(conv_digits, primary_signal))
        ]

        neighbour_names = [name for name in ordered if name != primary]
        if not neighbour_names:
            return selected

        if not self._should_try_neighbours(conv_digits, primary_signal):
            self.n_neighbour_skips += len(neighbour_names)
            return selected

        ranked = []
        for name in neighbour_names:
            signal = self._cheap_linear_signal(v, name)
            if signal >= PSLQ_NEIGHBOUR_MIN_SIGNAL or conv_digits >= MIN_DIGITS + PSLQ_NEIGHBOUR_EXTRA_DIGITS:
                ranked.append((signal, name))
            else:
                self.n_neighbour_skips += 1

        ranked.sort(reverse=True)
        for signal, name in ranked[:PSLQ_NEIGHBOUR_LIMIT]:
            self.n_neighbour_attempts += 1
            selected.append((name, signal, self._should_try_degree2(conv_digits, signal)))
        self.n_neighbour_skips += max(0, len(ranked) - PSLQ_NEIGHBOUR_LIMIT)
        return selected

    def _run_target_pslq(self, spec: GCFSpec, v: mp.mpf, v_s: mp.mpf,
                         conv_digits: int, name: str,
                         allow_degree2: bool) -> Optional[Discovery]:
        info = self._constant_cache.get(name)
        if info is None:
            return None
        K = info["mpf"]
        self.n_tested += 1

        tol_fast = mp.mpf(10) ** (PSLQ_TOL_EXP + 20)
        K_s = mp.mpf(K)
        try:
            self.n_pslq_calls += 1
            rel = mp.pslq(_pslq_vec1(v_s, K_s), tol=tol_fast,
                          maxcoeff=PSLQ_MAXCOEF)
        except Exception:
            rel = None

        rel2 = None
        if allow_degree2 and not (rel and not self._is_trivial(rel, 1)):
            try:
                self.n_pslq_calls += 1
                self.n_degree2_calls += 1
                rel2 = mp.pslq(_pslq_vec2(v_s, K_s), tol=tol_fast,
                               maxcoeff=PSLQ_MAXCOEF)
            except Exception:
                rel2 = None

        if rel and not self._is_trivial(rel, 1):
            prec = _precision(v, K, rel, 1)
            if prec >= MIN_DIGITS:
                self.n_found += 1
                return Discovery(
                    spec=spec, cf_value=v,
                    constant_name=name, relation=rel, degree=1,
                    precision=prec, convergence_digits=conv_digits,
                    formula_str=_rel_to_formula("CF", name, rel, 1))
            elif prec >= NEAR_MISS_MIN_DIGITS:
                self._record_near_miss(
                    spec, name, rel, 1, prec, conv_digits,
                    _rel_to_formula("CF", name, rel, 1))

        if rel2 and not self._is_trivial(rel2, 2):
            # CRITICAL FIX: reject degree-2 relations when CF is rational.
            # A rational CF trivially satisfies any degree-2 relation
            # involving a transcendental constant K, because the relation
            # factors as f(CF) * g(K) = 0 where f(CF) = 0.
            if self._is_cf_rational(v_s):
                pass  # skip — trivial rational CF
            else:
                prec = _precision(v, K, rel2, 2)
                if prec >= MIN_DIGITS:
                    self.n_found += 1
                    return Discovery(
                        spec=spec, cf_value=v,
                        constant_name=name, relation=rel2, degree=2,
                        precision=prec, convergence_digits=conv_digits,
                        formula_str=_rel_to_formula("CF", name, rel2, 2))
                elif prec >= NEAR_MISS_MIN_DIGITS:
                    self._record_near_miss(
                        spec, name, rel2, 2, prec, conv_digits,
                        _rel_to_formula("CF", name, rel2, 2))
        return None

    def _run_multi_constant_pslq(self, spec: GCFSpec, v: mp.mpf, v_s: mp.mpf,
                                  conv_digits: int) -> Optional[Discovery]:
        """Pillar 2: search for CF = linear combination of multiple constants."""
        groups = MULTI_CONSTANT_GROUPS.get(spec.target, [])
        if not groups:
            return None

        tol_fast = mp.mpf(10) ** (PSLQ_TOL_EXP + 20)
        for const_names in groups:
            consts_mpf = []
            valid = True
            for name in const_names:
                info = self._constant_cache.get(name)
                if info is None:
                    valid = False
                    break
                consts_mpf.append(mp.mpf(info["mpf"]))
            if not valid:
                continue

            try:
                self.n_pslq_calls += 1
                vec = _pslq_vec_multi(v_s, consts_mpf)
                rel = mp.pslq(vec, tol=tol_fast, maxcoeff=PSLQ_MAXCOEF)
            except Exception:
                rel = None

            if rel and not _multi_rel_is_trivial(rel):
                prec = _multi_precision(v, consts_mpf, rel)
                if prec >= MIN_DIGITS:
                    self.n_found += 1
                    formula = _multi_rel_to_formula("CF", const_names, rel)
                    # Use first constant in group as the discovery's constant_name
                    return Discovery(
                        spec=spec, cf_value=v,
                        constant_name="+".join(const_names),
                        relation=rel, degree=1,
                        precision=prec, convergence_digits=conv_digits,
                        formula_str=formula)
                elif prec >= NEAR_MISS_MIN_DIGITS:
                    formula = _multi_rel_to_formula("CF", const_names, rel)
                    self._record_near_miss(
                        spec, "+".join(const_names), rel, 1, prec,
                        conv_digits, formula, basis_type="multi")
        return None

    def test(self, spec: GCFSpec, v: mp.mpf,
             conv_digits: int, targets: list[str],
             use_seen: bool = True) -> Optional[Discovery]:
        if mp.isnan(v) or mp.isinf(v): return None
        if conv_digits < MIN_DIGITS:   return None

        vfp = self._value_fingerprint(v)
        if use_seen and vfp in self._seen_values:
            return None

        candidate_targets = self._candidate_targets(spec, targets, v, conv_digits)
        if not candidate_targets:
            return None

        found_before = self.n_found
        with mp.workdps(PSLQ_DPS):
            v_s = mp.mpf(v)
            for name, _signal, allow_degree2 in candidate_targets:
                discovery = self._run_target_pslq(spec, v, v_s, conv_digits,
                                                  name, allow_degree2)
                if discovery:
                    if use_seen:
                        self._seen_values.add(vfp)
                    return discovery

            # Pillar 2: Multi-constant coupling search (fallback)
            if conv_digits >= MIN_DIGITS + 10:
                multi_disc = self._run_multi_constant_pslq(spec, v, v_s, conv_digits)
                if multi_disc:
                    if use_seen:
                        self._seen_values.add(vfp)
                    return multi_disc

        if not use_seen:
            self.n_found = found_before
        return None

    def merge_stats(self, stats: dict[str, int]):
        self.n_tested += stats.get("tested_targets", 0)
        self.n_pslq_calls += stats.get("pslq_calls", 0)
        self.n_degree2_calls += stats.get("degree2_calls", 0)
        self.n_prefilter_skips += stats.get("prefilter_skips", 0)
        self.n_neighbour_attempts += stats.get("neighbour_attempts", 0)
        self.n_neighbour_skips += stats.get("neighbour_skips", 0)

    def accept_discovery(self, d: Discovery) -> bool:
        vfp = self._value_fingerprint(d.cf_value)
        if vfp in self._seen_values:
            return False
        self._seen_values.add(vfp)
        self.n_found += 1
        return True


_WORKER_PSLQ_ENGINE: Optional[PSLQEngine] = None
_WORKER_ENGINE_CONFIG: Optional[tuple[int, int, int, int]] = None


def _parallel_check_worker(task: tuple[dict, dict]) -> dict:
    """Picklable worker for ProcessPoolExecutor batch evaluation."""
    global _WORKER_PSLQ_ENGINE, _WORKER_ENGINE_CONFIG, WORKING_DPS, MIN_DIGITS, PSLQ_DPS

    spec_payload, config = task
    working_dps = int(config.get("working_dps", WORKING_DPS))
    min_digits = int(config.get("min_digits", MIN_DIGITS))
    pslq_dps = int(config.get("pslq_dps", PSLQ_DPS))
    pslq_maxcoef = int(config.get("pslq_maxcoef", PSLQ_MAXCOEF))

    WORKING_DPS = working_dps
    MIN_DIGITS = min_digits
    PSLQ_DPS = pslq_dps
    globals()["PSLQ_MAXCOEF"] = pslq_maxcoef
    mp.mp.dps = working_dps

    engine_config = (working_dps, min_digits, pslq_dps, pslq_maxcoef)
    if _WORKER_PSLQ_ENGINE is None or _WORKER_ENGINE_CONFIG != engine_config:
        _WORKER_PSLQ_ENGINE = PSLQEngine(CONSTANTS)
        _WORKER_ENGINE_CONFIG = engine_config
    engine = _WORKER_PSLQ_ENGINE

    before = {
        "tested_targets": engine.n_tested,
        "pslq_calls": engine.n_pslq_calls,
        "degree2_calls": engine.n_degree2_calls,
        "prefilter_skips": engine.n_prefilter_skips,
        "neighbour_attempts": engine.n_neighbour_attempts,
        "neighbour_skips": engine.n_neighbour_skips,
    }

    spec = GCFSpec.from_dict(spec_payload)
    cheap = spec.fast_screen_digits()
    if cheap < MIN_DIGITS:
        return {"discovery": None, "cf_value": None,
                "pslq": {k: 0 for k in before}}

    conv = spec.convergence_digits()
    if conv < MIN_DIGITS:
        return {"discovery": None, "cf_value": None,
                "pslq": {k: 0 for k in before}}

    v = spec.evaluate(check_convergence=False)
    if v is None:
        return {"discovery": None, "cf_value": None,
                "pslq": {k: 0 for k in before}}

    targets = [spec.target] + NEIGHBOURS.get(spec.target, [])
    discovery = engine.test(spec, v, conv, targets, use_seen=False)

    after = {
        "tested_targets": engine.n_tested,
        "pslq_calls": engine.n_pslq_calls,
        "degree2_calls": engine.n_degree2_calls,
        "prefilter_skips": engine.n_prefilter_skips,
        "neighbour_attempts": engine.n_neighbour_attempts,
        "neighbour_skips": engine.n_neighbour_skips,
    }
    delta = {k: after[k] - before[k] for k in before}
    return {
        "discovery": discovery.to_dict() if discovery else None,
        "cf_value": mp.nstr(v, 50),
        "pslq": delta,
    }


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
    persistent_promotions: int = 0
    t0:          float = field(default_factory=time.time)

    def rate(self):
        return self.novel / max(self.iters, 1) * 100

    def elapsed_seconds(self):
        return max(0.0, time.time() - self.t0)

    def throughput(self):
        return self.tested / max(self.elapsed_seconds(), 1e-9)

    def elapsed(self):
        s = int(self.elapsed_seconds())
        return f"{s//60}m{s%60:02d}s"


class RamanujanAgent:
    def __init__(self, target="zeta3", use_llm=False,
                 use_lirec=False, seed_file=None,
                 priority_map: Optional[dict[str, float]] = None,
                 deep_mode: bool = False):
        self.target = target
        self.deep_mode = deep_mode
        self.stats  = Stats()
        self.verbose = True
        self.workers = 1
        self.executor_kind = "process"
        self.priority_map = _merge_priority_maps(priority_map, target=target)
        seeds = builtin_seeds()
        if seed_file and os.path.exists(seed_file):
            with open(seed_file, encoding="utf-8") as f:
                extra = json.load(f)
            seeds += [GCFSpec.from_dict(d) for d in extra
                      if isinstance(d, dict) and "alpha" in d]
            print(f"  Loaded {len(extra)} seeds from {seed_file}")
        self.gen     = GCFGenerator(seeds, target=target, priority_map=self.priority_map,
                                    deep_mode=deep_mode)
        self.pslq    = PSLQEngine(CONSTANTS)
        self.lirec   = LIReCBridge(enabled=use_lirec)
        self.llm     = LLMEnricher(enabled=use_llm)
        self.symbolic = SymbolicSimplifier()
        self.architect = ArchitectGenerator(target=target)
        self.discoveries: list[Discovery] = []

    def _check(self, spec: GCFSpec) -> Optional[Discovery]:
        cheap = spec.fast_screen_digits()
        if cheap < MIN_DIGITS:
            return None

        conv = spec.convergence_digits()
        if conv < MIN_DIGITS:
            return None

        v = spec.evaluate(check_convergence=False)
        if v is None:
            return None

        # Primary target + neighbours
        targets = [spec.target] + NEIGHBOURS.get(spec.target, [])
        d = self.pslq.test(spec, v, conv, targets)
        if d:
            return d
        # LIReC wide search as fallback
        if self.lirec.enabled:
            lirec = self.lirec.identify(v)
            if lirec and self.verbose:
                print(f"  [LIReC] {spec.spec_id}: {lirec}")
        return None

    def _merge_parallel_result(self, result: dict) -> Optional[Discovery]:
        self.pslq.merge_stats(result.get("pslq", {}))
        payload = result.get("discovery")
        cf_value = result.get("cf_value")
        if not payload or cf_value is None:
            return None
        try:
            d = Discovery.from_dict(payload, cf_value=mp.mpf(cf_value))
        except Exception:
            return None
        if not self.pslq.accept_discovery(d):
            return None
        return d

    def _on_discovery(self, d: Discovery):
        self.discoveries.append(d)
        self.stats.discoveries += 1
        self.stats.novel       += 1

        symbolic = self.symbolic.refine(d)
        if symbolic:
            d.enrichment.update(symbolic)

        genetic_update = self.gen.record_success(d)
        if genetic_update.get("promoted"):
            self.stats.persistent_promotions += 1
            if self.verbose:
                print(f"  [Evolution] Promoted {d.spec.spec_id} → {PERSISTENT_SEED_PATH}"
                      f" ({genetic_update.get('closed_form')})")

        if self.verbose:
            print(f"\n  {'★'*56}")
            print(f"  ★ DISCOVERY #{self.stats.novel}")
            print(f"  ★ a(n) = {_poly_str(d.spec.alpha)}")
            print(f"  ★ b(n) = {_poly_str(d.spec.beta)}")
            print(f"  ★ mode = {d.spec.mode}  order={d.spec.order}")
            print(f"  ★ {d.constant_name} relation (deg={d.degree}, "
                  f"{d.precision}dp): {d.formula_str}")
            closed_form = d.enrichment.get("closed_form")
            if closed_form:
                print(f"  ★ Closed-form hypothesis: CF = {closed_form}")
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
        if neighbours and self.verbose:
            print(f"  [Relay] Injected {len(neighbours)} seeds → "
                  f"{[n.target for n in neighbours]}\n")

        # Architect injection (Pillar 3)
        self.architect.record(d)
        architect_specs = self.architect.propose(count=4)
        if architect_specs:
            self.gen.inject(architect_specs)
            self.stats.seeds_in += len(architect_specs)
            if self.verbose:
                print(f"  [Architect] Proposed {len(architect_specs)} structural candidates")

    def run(self, n_iters=200, batch=8, verbose=True, workers=0,
            executor_kind="process", print_report=True):
        self.verbose = verbose
        self.executor_kind = executor_kind
        requested_workers = int(workers or 0)
        total_jobs = n_iters * batch

        if requested_workers == 0:
            self.workers = _auto_worker_count(n_iters, batch)
        else:
            self.workers = max(1, requested_workers)
            if batch < 10 or total_jobs < AUTO_PARALLEL_MIN_JOBS:
                self.workers = 1

        effective_batch = _effective_batch_size(batch, self.workers)

        if self.verbose:
            print(BANNER)
            print(f"\n  Target:      {self.target}")
            print(f"  Iterations:  {n_iters}  ×  {effective_batch} GCFs/iter = "
                  f"{n_iters*effective_batch} total")
            if requested_workers == 0:
                print(f"  Auto workers: heuristic selected {self.workers} (cap={AUTO_WORKER_CAP})")
            if effective_batch != batch:
                print(f"  Requested batch: {batch}  → auto-scaled to {effective_batch} for parallel workers")
            if (batch < 10 or total_jobs < AUTO_PARALLEL_MIN_JOBS) and requested_workers > 1:
                print(f"  Small run detected ({total_jobs} jobs, batch={batch}) → forcing sequential mode")
            print(f"  Precision:   {WORKING_DPS}dp  |  min_conv: {MIN_DIGITS}dp")
            print(f"  Workers:     {self.workers}  ({self.executor_kind if self.workers > 1 else 'sequential'})")
            print(f"  LLM:         {self.llm.status_label()}")
            print(f"  LIReC:       {'✓' if self.lirec.enabled else '✗ (local PSLQ only)'}")
            print()

        if self.workers > 1:
            executor_cls = ThreadPoolExecutor if self.executor_kind == "thread" else ProcessPoolExecutor
            executor = executor_cls(max_workers=self.workers)
        else:
            executor = None
        try:
            for _ in range(n_iters):
                self.stats.iters += 1
                batch_specs = self.gen.next_batch(effective_batch)

                if executor is not None:
                    try:
                        worker_config = {
                            "working_dps": WORKING_DPS,
                            "min_digits": MIN_DIGITS,
                            "pslq_dps": PSLQ_DPS,
                            "pslq_maxcoef": PSLQ_MAXCOEF,
                        }
                        tasks = [(spec.to_dict(), worker_config) for spec in batch_specs]
                        chunk = max(1, len(tasks) // max(1, self.workers * 2))
                        results = list(executor.map(_parallel_check_worker, tasks, chunksize=chunk))
                    except Exception as ex:
                        if self.verbose:
                            print(f"  [Parallel] Falling back to sequential mode ({ex.__class__.__name__}: {ex})")
                        executor.shutdown(wait=False, cancel_futures=True)
                        executor = None
                        self.workers = 1
                        results = None

                    if results is not None:
                        for spec, result in zip(batch_specs, results):
                            self.stats.tested += 1
                            d = self._merge_parallel_result(result)
                            if d:
                                self._on_discovery(d)
                                self.gen.pool.append(spec)   # keep successful spec
                                self.gen._prune_pool()
                        if verbose and self.stats.iters % 10 == 0:
                            print(f"  ── {self.stats.iters:4d}/{n_iters} │ "
                                  f"tested={self.stats.tested:5d} │ "
                                  f"novel={self.stats.novel:3d} ({self.stats.rate():.1f}%) │ "
                                  f"pool={len(self.gen.pool):3d} │ "
                                  f"{self.stats.elapsed()}")
                        continue

                for spec in batch_specs:
                    self.stats.tested += 1
                    d = self._check(spec)
                    if d:
                        self._on_discovery(d)
                        self.gen.pool.append(spec)   # keep successful spec
                        self.gen._prune_pool()

                if verbose and self.stats.iters % 10 == 0:
                    print(f"  ── {self.stats.iters:4d}/{n_iters} │ "
                          f"tested={self.stats.tested:5d} │ "
                          f"novel={self.stats.novel:3d} ({self.stats.rate():.1f}%) │ "
                          f"pool={len(self.gen.pool):3d} │ "
                          f"{self.stats.elapsed()}")
        finally:
            if executor is not None:
                executor.shutdown()

        if print_report:
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
        print(f"  Seed promotions:{s.persistent_promotions}")
        print(f"  Workers:       {self.workers} ({self.executor_kind if self.workers > 1 else 'sequential'})")
        print(f"  Throughput:    {s.throughput():.2f} GCF/s")
        print(f"  PSLQ calls:    {self.pslq.n_pslq_calls}  (deg2={self.pslq.n_degree2_calls})")
        print(f"  Screen skips:  {self.pslq.n_prefilter_skips}  |  neighbour tries={self.pslq.n_neighbour_attempts} skips={self.pslq.n_neighbour_skips}")
        print(f"  Near-misses:   {len(self.pslq.near_misses)}")
        print(f"  Elapsed:       {s.elapsed()}")
        if self.discoveries:
            print(f"\n  Discoveries ({len(self.discoveries)}):")
            for d in self.discoveries:
                closed = (d.enrichment or {}).get("closed_form")
                suffix = f"  ⇒  {closed}" if closed else ""
                print(f"    [{d.spec.spec_id}]  {d.constant_name}  "
                      f"deg={d.degree}  {d.precision}dp  |  {d.formula_str[:55]}{suffix[:70]}")
        if self.pslq.near_misses:
            top_misses = sorted(self.pslq.near_misses,
                                key=lambda x: x["precision"], reverse=True)[:10]
            print(f"\n  Near-misses (top {len(top_misses)}/{len(self.pslq.near_misses)}):")
            for nm in top_misses:
                tag = " [MULTI]" if nm["basis_type"] == "multi" else ""
                print(f"    [{nm['spec_id']}]  {nm['constant']}  "
                      f"{nm['precision']}dp/{nm['conv_digits']}conv  "
                      f"|  {nm['formula'][:55]}{tag}")
        print()

    def save(self, path="ramanujan_discoveries.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "stats": {"iters": self.stats.iters,
                          "tested": self.stats.tested,
                          "novel": self.stats.novel},
                "discoveries": [d.to_dict() for d in self.discoveries],
                "seed_pool": [s.to_dict() for s in self.gen.pool],
            }, f, indent=2, default=str)
        print(f"  Saved → {path}")

    def save_seeds(self, path="relay_chain_seed_pool.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self.gen.pool], f, indent=2)
        print(f"  Seeds → {path}  ({len(self.gen.pool)} specs)")

    def summary_dict(self, discoveries_path="ramanujan_discoveries.json",
                     seed_path="relay_chain_seed_pool.json",
                     run_config=None, profile_path=None):
        elapsed_seconds = round(self.stats.elapsed_seconds(), 3)
        return {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "script": os.path.basename(sys.argv[0]) or "ramanujan_agent_v2_fast.py",
            "target": self.target,
            "llm_mode": self.llm.status_label(),
            "lirec_enabled": self.lirec.enabled,
            "stats": {
                "iters": self.stats.iters,
                "tested": self.stats.tested,
                "discoveries": self.stats.discoveries,
                "novel": self.stats.novel,
                "rate_percent": round(self.stats.rate(), 3),
                "seeds_injected": self.stats.seeds_in,
                "llm_calls": self.stats.llm_calls,
                "persistent_promotions": self.stats.persistent_promotions,
                "elapsed_human": self.stats.elapsed(),
                "elapsed_seconds": elapsed_seconds,
                "gcf_per_sec": round(self.stats.throughput(), 3),
            },
            "environment": _system_metadata(),
            "artifacts": {
                "discoveries_path": discoveries_path,
                "seed_path": seed_path,
                "profile_path": profile_path,
            },
            "pslq": {
                "tested_targets": self.pslq.n_tested,
                "pslq_calls": self.pslq.n_pslq_calls,
                "degree2_calls": self.pslq.n_degree2_calls,
                "prefilter_skips": self.pslq.n_prefilter_skips,
                "neighbour_attempts": self.pslq.n_neighbour_attempts,
                "neighbour_skips": self.pslq.n_neighbour_skips,
                "found": self.pslq.n_found,
                "near_misses": len(self.pslq.near_misses),
            },
            "near_misses": sorted(self.pslq.near_misses,
                                  key=lambda x: x["precision"],
                                  reverse=True)[:20],
            "run_config": run_config or {},
            "discoveries": [d.to_dict() for d in self.discoveries],
        }

    def save_summary_json(self, path="ramanujan-run-summary.json",
                          discoveries_path="ramanujan_discoveries.json",
                          seed_path="relay_chain_seed_pool.json",
                          run_config=None, profile_path=None):
        payload = self.summary_dict(discoveries_path=discoveries_path,
                                    seed_path=seed_path,
                                    run_config=run_config,
                                    profile_path=profile_path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"  Summary JSON -> {path}")
        return path

    def save_summary_html(self, path="ramanujan-run-summary.html",
                          discoveries_path="ramanujan_discoveries.json",
                          seed_path="relay_chain_seed_pool.json",
                          run_config=None, profile_path=None):
        summary = self.summary_dict(discoveries_path=discoveries_path,
                                    seed_path=seed_path,
                                    run_config=run_config,
                                    profile_path=profile_path)
        stats = summary["stats"]
        env = summary["environment"]
        rate = stats["rate_percent"]
        llm_status = self.llm.status_label()
        generated = summary["generated_at"]
        throughput = stats["gcf_per_sec"]
        profile_label = summary["artifacts"]["profile_path"] or "not captured"
        next_script = summary["script"]
        next_cmd = (
            f"python {next_script} --seed-file {seed_path} "
            f"--target {self.target} --iters 500"
        )

        rows = []
        for idx, d in enumerate(self.discoveries, 1):
            closed_form = (d.enrichment or {}).get("closed_form")
            closed_html = f"<div><strong>Closed form:</strong> <code>{html.escape(str(closed_form))}</code></div>" if closed_form else ""
            approx_html = ""
            try:
                if d.cf_value is not None and not mp.isnan(d.cf_value) and not mp.isinf(d.cf_value):
                    approx_html = f"<div><strong>Approx:</strong> <code>{html.escape(mp.nstr(d.cf_value, 24))}</code></div>"
            except Exception:
                approx_html = ""
            rows.append(f"""
            <tr>
              <td>{idx}</td>
              <td><code>{html.escape(d.spec.spec_id)}</code></td>
              <td>{html.escape(d.constant_name)}</td>
              <td>{d.precision}</td>
              <td>{d.convergence_digits}</td>
              <td><code>{html.escape(json.dumps(d.spec.alpha))}</code><br><code>{html.escape(json.dumps(d.spec.beta))}</code></td>
              <td>{html.escape(d.formula_str)}{closed_html}{approx_html}</td>
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
        <div class="stat"><div class="label">Iterations</div><div class="value">{stats['iters']}</div></div>
        <div class="stat"><div class="label">GCFs tested</div><div class="value">{stats['tested']}</div></div>
        <div class="stat"><div class="label">Novel finds</div><div class="value">{stats['novel']}</div></div>
        <div class="stat"><div class="label">Find rate</div><div class="value">{rate:.2f}%</div></div>
        <div class="stat"><div class="label">Seeds injected</div><div class="value">{stats['seeds_injected']}</div></div>
        <div class="stat"><div class="label">GCFs / sec</div><div class="value">{throughput:.2f}</div></div>
        <div class="stat"><div class="label">LLM calls</div><div class="value">{stats['llm_calls']}</div></div>
      </div>
      <div class="meta">
        <div><strong>LLM mode:</strong> {html.escape(llm_status)}</div>
        <div><strong>Elapsed:</strong> {html.escape(stats['elapsed_human'])} ({stats['elapsed_seconds']:.3f}s)</div>
        <div><strong>Python:</strong> {html.escape(str(env['python']))} · mpmath {html.escape(str(env['mpmath']))}</div>
        <div><strong>Platform:</strong> {html.escape(str(env['platform']))}</div>
        <div><strong>CPU count:</strong> {html.escape(str(env['cpu_count']))}</div>
        <div><strong>Discovery file:</strong> <a href="{html.escape(discoveries_path)}">{html.escape(discoveries_path)}</a></div>
        <div><strong>Seed pool:</strong> <a href="{html.escape(seed_path)}">{html.escape(seed_path)}</a></div>
        <div><strong>Profile:</strong> {html.escape(str(profile_label))}</div>
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

def _run_agent_with_profile(agent: RamanujanAgent, *, n_iters: int, batch: int,
                            verbose: bool, output_path: str,
                            sort_by: str = "cumulative", top_n: int = 20,
                            workers: int = 0, executor_kind: str = "process"):
    import cProfile
    import io
    import pstats

    profiler = cProfile.Profile()
    profiler.enable()
    agent.run(n_iters=n_iters, batch=batch, verbose=verbose,
              workers=workers, executor_kind=executor_kind,
              print_report=True)
    profiler.disable()

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        profiler.dump_stats(output_path)

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats(sort_by).print_stats(max(1, top_n))
    print(f"\n  Profile summary (top {max(1, top_n)}, sort={sort_by}):")
    print(stream.getvalue().rstrip())
    if output_path:
        print(f"  Profile saved -> {output_path}")
    return output_path or None


def run_search_kernel(*, target="zeta3", iters=100, batch=8, prec=300,
                      workers=0, executor="process", quiet=True,
                      use_llm=False, use_lirec=False, seed=None,
                      seed_file=None, priority_map: Optional[dict[str, float]] = None,
                      deep_mode: bool = False) -> dict:
    """Programmatic entry point for SIARC or other orchestrators.

    Returns a structured payload with `summary` and `discoveries` so callers can
    consume results directly without intermediate JSON handoffs.
    """
    global WORKING_DPS, MIN_DIGITS, PSLQ_DPS, PSLQ_TOL_EXP
    WORKING_DPS = prec
    MIN_DIGITS = max(20, prec // 10)
    # Scale PSLQ precision with working precision for high-prec runs
    if prec > 300:
        PSLQ_DPS = max(80, prec // 4)
        PSLQ_TOL_EXP = -(PSLQ_DPS - 20)
    mp.mp.dps = WORKING_DPS
    if seed is not None:
        random.seed(seed)

    agent = RamanujanAgent(target=target, use_llm=use_llm,
                           use_lirec=use_lirec, seed_file=seed_file,
                           priority_map=priority_map,
                           deep_mode=deep_mode)
    agent.run(n_iters=iters, batch=batch, verbose=not quiet,
              workers=workers, executor_kind=executor,
              print_report=not quiet)
    run_config = {
        "target": target,
        "iters": iters,
        "batch": batch,
        "effective_batch": _effective_batch_size(batch, agent.workers),
        "workers": workers,
        "resolved_workers": agent.workers,
        "auto_worker_cap": AUTO_WORKER_CAP,
        "executor": executor,
        "prec": prec,
        "quiet": quiet,
        "seed": seed,
        "seed_file": seed_file,
        "llm": use_llm,
        "lirec": use_lirec,
        "priority_map": priority_map or {},
        "deep_mode": deep_mode,
    }
    return {
        "summary": agent.summary_dict(run_config=run_config),
        "discoveries": [d.to_dict() for d in agent.discoveries],
    }


def main():
    p = argparse.ArgumentParser(
        description="Ramanujan Machine Agent v2",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--iters", type=int, default=100,
                   help="Number of outer search iterations.")
    p.add_argument("--target", default="zeta3", choices=list(CONSTANTS),
                   help="Primary mathematical constant to target.")
    p.add_argument("--batch", type=int, default=8,
                   help="Number of GCF candidates to generate per iteration.")
    p.add_argument("--workers", type=int, default=0,
                   help="Number of workers for parallel batch evaluation. Use 0 for fast auto mode.")
    p.add_argument("--executor", default="process", choices=["process", "thread"],
                   help="Parallel executor backend to use when workers > 1.")
    p.add_argument("--prec", type=int, default=300,
                   help="Working decimal precision for verification.")
    p.add_argument("--llm", action="store_true",
                   help="Enable heuristic/Anthropic enrichment for discoveries.")
    p.add_argument("--lirec", action="store_true",
                   help="Enable the optional LIReC database bridge.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress the banner, per-discovery blocks, and progress updates.")
    p.add_argument("--seed-file", default=None,
                   help="Optional JSON seed pool to continue from a previous run.")
    p.add_argument("--summary-html", default="ramanujan-run-summary.html",
                   help="Path for the HTML summary artifact.")
    p.add_argument("--json-summary", default=None,
                   help="Optional path for a machine-readable JSON run summary.")
    p.add_argument("--seed", type=int, default=None,
                   help="Optional RNG seed for reproducible search/benchmark runs.")
    p.add_argument("--profile", action="store_true",
                   help="Profile the main search loop with cProfile.")
    p.add_argument("--profile-output", default="ramanujan_agent_profile.prof",
                   help="Where to save raw cProfile stats when --profile is enabled.")
    p.add_argument("--profile-sort", default="cumulative",
                   choices=["cumulative", "time", "calls"],
                   help="Sort key for the printed profile summary.")
    p.add_argument("--profile-top", type=int, default=20,
                   help="Number of profile rows to print when profiling.")
    p.add_argument("--list-constants", action="store_true",
                   help="List supported constants and exit.")
    p.add_argument("--deep", action="store_true",
                   help="Enable deep search mode (high-order polynomials, Pillar 1).")
    args = p.parse_args()

    if args.list_constants:
        print("Available constants:")
        for k, v in CONSTANTS.items():
            print(f"  {k:15s} = {mp.nstr(v, 20)}")
        return

    global WORKING_DPS, MIN_DIGITS, PSLQ_DPS, PSLQ_TOL_EXP
    WORKING_DPS = args.prec
    MIN_DIGITS  = max(20, args.prec // 10)
    if args.prec > 300:
        PSLQ_DPS = max(80, args.prec // 4)
        PSLQ_TOL_EXP = -(PSLQ_DPS - 20)
    mp.mp.dps   = WORKING_DPS
    if args.seed is not None:
        random.seed(args.seed)

    resolved_workers = _auto_worker_count(args.iters, args.batch) if args.workers == 0 else max(1, args.workers)
    if args.workers > 0 and (args.batch < 10 or args.iters * args.batch < AUTO_PARALLEL_MIN_JOBS):
        resolved_workers = 1

    run_config = {
        "iters": args.iters,
        "target": args.target,
        "batch": args.batch,
        "effective_batch": _effective_batch_size(args.batch, resolved_workers),
        "workers": args.workers,
        "resolved_workers": resolved_workers,
        "auto_worker_cap": AUTO_WORKER_CAP,
        "executor": args.executor,
        "prec": args.prec,
        "quiet": args.quiet,
        "seed": args.seed,
        "llm": args.llm,
        "lirec": args.lirec,
        "seed_file": args.seed_file,
        "deep_mode": args.deep,
    }

    agent = RamanujanAgent(target=args.target, use_llm=args.llm,
                           use_lirec=args.lirec, seed_file=args.seed_file,
                           deep_mode=args.deep)
    profile_path = None
    if args.profile:
        profile_path = _run_agent_with_profile(
            agent,
            n_iters=args.iters,
            batch=args.batch,
            verbose=not args.quiet,
            output_path=args.profile_output,
            sort_by=args.profile_sort,
            top_n=args.profile_top,
            workers=args.workers,
            executor_kind=args.executor,
        )
    else:
        agent.run(n_iters=args.iters, batch=args.batch, verbose=not args.quiet,
                  workers=args.workers, executor_kind=args.executor)

    discoveries_path = "ramanujan_discoveries.json"
    seed_path = "relay_chain_seed_pool.json"
    agent.save(discoveries_path)
    agent.save_seeds(seed_path)
    if args.json_summary:
        agent.save_summary_json(args.json_summary,
                                discoveries_path=discoveries_path,
                                seed_path=seed_path,
                                run_config=run_config,
                                profile_path=profile_path)
    agent.save_summary_html(args.summary_html,
                            discoveries_path=discoveries_path,
                            seed_path=seed_path,
                            run_config=run_config,
                            profile_path=profile_path)
    if agent.discoveries:
        script_name = os.path.basename(sys.argv[0]) or "ramanujan_agent_v2_fast.py"
        print(f"\n  Next run:  python {script_name} "
              f"--seed-file relay_chain_seed_pool.json --target {args.target}")


if __name__ == "__main__":
    main()
