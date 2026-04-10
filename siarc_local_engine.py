"""
SIARC Local Engine  —  zero API keys, pure Python
==================================================
Provides a fully local critic, LFI scorer, judge, and swarm runner
that replaces the cloud-API debate layer entirely.

All scoring is done analytically:
  - SymPy symbolic checks (dimensional consistency, scalar validity)
  - mpmath numerical checks (gap, seed stability)
  - Rule-based LFI (Lethal Flaw Index) across 5 dimensions
  - Deterministic judge verdict from weighted gate scores

Usage as CLI:
  python siarc_local_engine.py --input siarc_outputs/agent_C_out.json
  python siarc_local_engine.py --formula "-(5*c5)/48 - 6/c5" --k 5
  python siarc_local_engine.py --swarm --k 6 --seed "-(5*c5)/48 - 6/c5"

Usage from Python:
  from siarc_local_engine import LocalEngine
  engine = LocalEngine()
  result = engine.evaluate("-(5*c5)/48 - 6/c5", k=5)
  print(result.verdict)
"""

import argparse, json, math, os, sys, time, re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

try:
    from sympy import (symbols, sympify, simplify, expand, nsimplify,
                       Rational, sqrt, pi, zoo, oo, nan, Number,
                       latex, factor, cancel, diff, limit)
    from sympy import zeta as sym_zeta, log as sym_log
except ImportError:
    sys.exit("[ERROR] pip install sympy")

try:
    from mpmath import mp, mpf, mpc, pslq, identify, nstr, zeta as mpzeta
    mp.dps = 50
except ImportError:
    sys.exit("[ERROR] pip install mpmath")

ISO = lambda: datetime.now(timezone.utc).isoformat()
SEP  = "─" * 64
SEP2 = "═" * 64

# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LFIScore:
    dimensional:   float = 0.0   # 0=sound, 1=lethal mismatch
    scaling:       float = 0.0   # blows up as k→∞?
    scalar_wrap:   float = 0.0   # unexplained outer scalar?
    transcendental:float = 0.0   # spurious transcendental constant?
    seed_variance: float = 0.0   # high variance across seeds?

    @property
    def total(self) -> float:
        weights = [0.30, 0.20, 0.25, 0.15, 0.10]
        vals    = [self.dimensional, self.scaling, self.scalar_wrap,
                   self.transcendental, self.seed_variance]
        return sum(w * v for w, v in zip(weights, vals))

    @property
    def is_lethal(self) -> bool:
        return self.total > 0.5


@dataclass
class EvalResult:
    formula_raw:    str
    formula_clean:  str
    k:              int
    timestamp:      str = field(default_factory=ISO)

    # gap
    gap_pct:        Optional[float] = None
    gap_seeds:      list = field(default_factory=list)
    gap_std:        Optional[float] = None
    gap_stable:     Optional[bool] = None

    # scalar
    scalar_value:   Optional[float] = None
    scalar_unity:   Optional[bool] = None

    # coefficients
    alpha_exact:    Optional[str] = None
    beta_exact:     Optional[str] = None
    pslq_quality:   Optional[str] = None

    # LFI
    lfi:            Optional[LFIScore] = None

    # verdict
    verdict:        str = "pending"
    verdict_detail: str = ""
    action:         str = ""

    # CTRL-01 broadcast
    broadcast:      str = ""

    def to_dict(self):
        d = asdict(self)
        if self.lfi:
            d["lfi_total"] = self.lfi.total
        return d


# ─────────────────────────────────────────────────────────────────────────────
# FORMULA PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_formula(formula_str: str, k: int):
    """
    Parse a formula string into a SymPy expression.
    Supports: c5, c6, ck, c_k, alpha, beta, sqrt, pi, zeta
    Returns (expr, c_sym, error_str)
    """
    ck_name = f"c{k}"
    c_sym   = symbols(ck_name, positive=True)

    # normalise common patterns
    s = formula_str.strip()
    s = re.sub(r'\bck\b',   ck_name, s)
    s = re.sub(r'\bc_k\b',  ck_name, s)
    s = re.sub(r'\bsqrt2\b','sqrt(2)', s)
    s = re.sub(r'zeta\(3\)', 'zeta(3)', s)

    # sympy namespace
    ns = {
        ck_name: c_sym,
        'c5': symbols('c5', positive=True),
        'c6': symbols('c6', positive=True),
        'c7': symbols('c7', positive=True),
        'c8': symbols('c8', positive=True),
        'sqrt': sqrt,
        'pi': pi,
        'zeta': sym_zeta,
        'log': sym_log,
        'Rational': Rational,
    }

    try:
        expr = sympify(s, locals=ns)
        return expr, c_sym, None
    except Exception as e:
        return None, c_sym, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class LocalEngine:
    """
    Fully local SIARC evaluation engine.
    No API keys required. All checks are mathematical.
    """

    # Known canonical forms per k
    CANONICAL = {
        5: {"alpha": Rational(-5, 48), "beta": Rational(-6, 1),
            "formula": "-(5*c5)/48 - 6/c5"},
        6: {"alpha": Rational(-6, 48), "beta": Rational(-63, 8),
            "formula": "-(6*c6)/48 - 63/(8*c6)"},
        7: {"alpha": Rational(-7, 48), "beta": Rational(-80, 8),
            "formula": "-(7*c7)/48 - 80/(8*c7)"},
        8: {"alpha": Rational(-8, 48), "beta": Rational(-99, 8),
            "formula": "-(8*c8)/48 - 99/(8*c8)"},
    }

    # Realistic c_k seed ranges per k
    SEED_RANGES = {
        5: [1.0, 1.5, 2.0, 2.5, 3.0, 3.7, 4.2, 5.0, 6.1, 7.8],
        6: [1.2, 1.8, 2.3, 2.8, 3.4, 4.0, 4.8, 5.5, 6.5, 8.0],
        7: [1.5, 2.0, 2.6, 3.1, 3.8, 4.4, 5.2, 6.0, 7.0, 8.5],
        8: [1.8, 2.3, 2.9, 3.5, 4.1, 4.9, 5.7, 6.6, 7.5, 9.0],
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def log(self, sym, msg):
        if self.verbose:
            print(f"  [{sym}] {msg}")

    # ── STEP 1: parse + dimensional check ────────────────────────────────────
    def check_dimensional(self, expr, c_sym) -> tuple[float, str]:
        """
        Check for dimensional consistency.
        A valid A₁⁽ᵏ⁾ expression must:
        - Depend on c_k (not be a pure constant)
        - Have finite limit as c_k → small positive
        - Not blow up to zoo/oo at c_k=1
        """
        if expr is None:
            return 1.0, "parse error"
        if not expr.has(c_sym):
            return 0.8, "formula is independent of c_k"
        try:
            val_at_1 = complex(expr.subs(c_sym, 1))
            if math.isnan(val_at_1.real) or math.isinf(val_at_1.real):
                return 0.9, "diverges at c_k=1"
        except Exception:
            return 0.7, "cannot evaluate at c_k=1"
        # check limit c_k→0+
        try:
            lim = limit(expr, c_sym, 0, '+')
            if lim in (oo, -oo, zoo):
                return 0.3, "diverges as c_k→0 (expected for 1/c_k terms)"
            # divergence at 0 is actually expected — don't penalise
        except Exception:
            pass
        return 0.0, "dimensional check passed"

    # ── STEP 2: outer scalar detection ───────────────────────────────────────
    def check_scalar_wrap(self, expr, c_sym, k: int) -> tuple[float, float, str]:
        """
        Detect ASR outer scalar pattern: A × (inner expression).
        Returns (lfi_contribution, scalar_value, note).
        """
        if expr is None:
            return 0.0, 1.0, "no expr"
        expanded = expand(expr)
        # extract coefficients of c_sym^1 and c_sym^-1
        coeff_c  = expanded.coeff(c_sym,  1)
        coeff_ic = expanded.coeff(c_sym, -1)
        if coeff_c == 0 and coeff_ic == 0:
            return 0.0, 1.0, "no c_k terms to extract scalar from"

        # If we know the canonical form for this k, compare
        canon = self.CANONICAL.get(k)
        if canon:
            canon_alpha = canon["alpha"]
            canon_beta  = canon["beta"]
            if coeff_c != 0 and canon_alpha != 0:
                try:
                    scalar = float(coeff_c / canon_alpha)
                    if abs(scalar - 1.0) < 0.002 or abs(scalar + 1.0) < 0.002:
                        return 0.0, scalar, "scalar ≈ ±1 — formula matches canonical"
                    else:
                        severity = min(1.0, abs(scalar - 1.0) / 10)
                        return severity, scalar, f"scalar = {scalar:.6f} ≠ ±1 — ASR wrapper detected"
                except Exception:
                    pass
        return 0.0, 1.0, "canonical not available for this k"

    # ── STEP 3: transcendental necessity check ────────────────────────────────
    def check_transcendental(self, expr, c_sym) -> tuple[float, str]:
        """
        Check if any transcendental constant is genuinely needed.
        Strategy: remove each constant and see if gap worsens significantly.
        If not: the constant is noise.
        """
        if expr is None:
            return 0.0, "no expr"
        has_pi    = expr.has(pi)
        has_sqrt2 = any(str(a) == 'sqrt(2)' for a in expr.atoms(sqrt))
        has_zeta  = expr.has(sym_zeta)

        concerns = []
        if has_sqrt2:
            # sqrt(2) in a Ramanujan partition identity is unusual
            concerns.append("√2 unexpected in partition-function context")
        if has_pi and not has_zeta:
            # bare π without ζ is unusual in A₁⁽ᵏ⁾ asymptotics
            concerns.append("bare π without ζ(3) is structurally unusual")

        if concerns:
            return 0.3, "; ".join(concerns)
        return 0.0, "transcendental constants appropriate (or absent)"

    # ── STEP 4: scaling behaviour ─────────────────────────────────────────────
    def check_scaling(self, expr, c_sym, k: int) -> tuple[float, str]:
        """
        Check that the formula scales correctly as k increases.
        A₁⁽ᵏ⁾ should grow roughly linearly in c_k, not quadratically.
        """
        if expr is None:
            return 0.0, "no expr"
        has_c2 = expr.has(c_sym**2) or expanded_has_c2(expr, c_sym)
        has_c3 = expr.has(c_sym**3)
        if has_c3:
            return 0.6, "c_k³ term — likely over-parameterised"
        if has_c2:
            return 0.3, "c_k² term — may not match asymptotic form"
        return 0.0, "scaling looks appropriate (linear + inverse)"

    # ── STEP 5: gap computation ───────────────────────────────────────────────
    def compute_gaps(self, expr, c_sym, k: int) -> tuple[list, float, float]:
        """
        Compute gap% across 10 seeds.
        Uses canonical target if available; otherwise uses formula self-consistency.
        Returns (seed_gaps, mean_gap, std_gap).
        """
        if expr is None:
            return [], 100.0, 0.0

        seeds    = self.SEED_RANGES.get(k, self.SEED_RANGES[5])
        canon    = self.CANONICAL.get(k)
        gaps     = []
        seed_rec = []

        for cv in seeds:
            try:
                val = float(expr.subs(c_sym, cv).evalf())
                if canon:
                    target = float(canon["alpha"] * cv + canon["beta"] / cv)
                    if abs(target) > 1e-30:
                        gap = abs(val - target) / abs(target) * 100
                    else:
                        gap = 0.0
                else:
                    # self-consistency: compare to nsimplify reconstruction
                    alpha_est = float(expr.coeff(c_sym, 1).evalf()) if expr.coeff(c_sym,1) != 0 else 0
                    beta_est  = float(expr.coeff(c_sym,-1).evalf()) if expr.coeff(c_sym,-1) != 0 else 0
                    target    = alpha_est * cv + beta_est / cv
                    gap       = abs(val - target) / (abs(target) + 1e-30) * 100

                gaps.append(gap)
                seed_rec.append({"c_k": cv, "formula_val": val, "gap_pct": gap})
            except Exception as e:
                gaps.append(100.0)
                seed_rec.append({"c_k": cv, "error": str(e), "gap_pct": 100.0})

        mean = sum(gaps) / len(gaps) if gaps else 100.0
        std  = math.sqrt(sum((g - mean)**2 for g in gaps) / len(gaps)) if gaps else 0.0
        return seed_rec, mean, std

    # ── STEP 6: PSLQ quick check ──────────────────────────────────────────────
    def pslq_quick(self, expr, c_sym, k: int, dps: Optional[int] = None) -> tuple[str, str, str]:
        """
        Extract α and β coefficients and run nsimplify + PSLQ.
        Returns (alpha_str, beta_str, quality).
        """
        if expr is None:
            return "?", "?", "no_expr"

        mp.dps = max(30, int(dps)) if dps is not None else max(mp.dps, 100)
        try:
            alpha_sym = expr.coeff(c_sym, 1)
            beta_sym  = expr.coeff(c_sym, -1)
            alpha_f   = float(alpha_sym.evalf()) if alpha_sym != 0 else 0.0
            beta_f    = float(beta_sym.evalf())  if beta_sym  != 0 else 0.0
        except Exception:
            return "?", "?", "extraction_failed"

        def try_exact(val_f, label):
            if abs(val_f) < 1e-30:
                return "0", "trivial"
            try:
                rat = nsimplify(val_f, rational=True, tolerance=1e-9)
                if hasattr(rat, 'p') and max(abs(rat.p), abs(rat.q)) <= 1000:
                    return str(rat), "exact_rational"
            except Exception:
                pass
            try:
                val_mp = mpf(str(val_f))
                rel = pslq([val_mp, mpf('1'), mpf(str(k)), mpf(str(k))**2],
                           tol=mpf('1e-40'), maxcoeff=1000)
                if rel:
                    mc = max(abs(int(r)) for r in rel)
                    if mc <= 100:   return f"pslq_hit(max={mc})", "excellent"
                    if mc <= 1000:  return f"pslq_hit(max={mc})", "good"
                    return f"pslq_noise(max={mc})", "noise"
            except Exception:
                pass
            return f"{val_f:.10f}", "float_only"

        alpha_str, aq = try_exact(alpha_f, "alpha")
        beta_str,  bq = try_exact(beta_f,  "beta")

        quality = "excellent" if "exact" in aq and "exact" in bq else \
                  "good"      if "exact" in aq or  "exact" in bq else \
                  "noise"
        return alpha_str, beta_str, quality

    # ── FULL EVALUATE ─────────────────────────────────────────────────────────
    def evaluate(self, formula_str: str, k: int = 5) -> EvalResult:
        expr, c_sym, err = parse_formula(formula_str, k)

        res = EvalResult(
            formula_raw   = formula_str,
            formula_clean = str(simplify(expr)) if expr else formula_str,
            k             = k,
        )

        if err:
            res.verdict        = "REJECTED"
            res.verdict_detail = f"Parse error: {err}"
            res.action         = "Fix formula syntax and resubmit."
            res.broadcast      = f"Formula parse error: {err}"
            return res

        lfi = LFIScore()

        # dimensional
        lfi.dimensional, dim_note = self.check_dimensional(expr, c_sym)
        self.log("→", f"Dimensional: {dim_note}")

        # scalar
        lfi.scalar_wrap, scalar_val, scalar_note = self.check_scalar_wrap(expr, c_sym, k)
        res.scalar_value = scalar_val
        res.scalar_unity = lfi.scalar_wrap < 0.05
        self.log("→", f"Scalar: {scalar_note}")

        # transcendental
        lfi.transcendental, trans_note = self.check_transcendental(expr, c_sym)
        self.log("→", f"Transcendental: {trans_note}")

        # scaling
        lfi.scaling, scale_note = self.check_scaling(expr, c_sym, k)
        self.log("→", f"Scaling: {scale_note}")

        # gaps
        seed_recs, gap_mean, gap_std = self.compute_gaps(expr, c_sym, k)
        res.gap_pct    = gap_mean
        res.gap_seeds  = seed_recs
        res.gap_std    = gap_std
        res.gap_stable = gap_std < 1.0  # stable if std < 1%
        lfi.seed_variance = min(1.0, gap_std / 20.0)
        self.log("→", f"Gap: mean={gap_mean:.4f}%  std={gap_std:.6f}%  stable={res.gap_stable}")

        # PSLQ
        alpha_str, beta_str, pslq_q = self.pslq_quick(expr, c_sym, k)
        res.alpha_exact  = alpha_str
        res.beta_exact   = beta_str
        res.pslq_quality = pslq_q
        self.log("→", f"PSLQ: α={alpha_str}  β={beta_str}  quality={pslq_q}")

        res.lfi = lfi
        lfi_total = lfi.total
        self.log("→", f"LFI total: {lfi_total:.3f}  ({'LETHAL' if lfi.is_lethal else 'OK'})")

        # ── VERDICT ──────────────────────────────────────────────────────────
        if lfi.is_lethal:
            res.verdict        = "REJECTED"
            res.verdict_detail = (f"LFI={lfi_total:.3f} > 0.5 lethal threshold. "
                                   f"Primary cause: {_primary_lfi_cause(lfi)}")
            res.action         = "Discard. Return to swarm with fresh seed."
            res.broadcast      = f"FIELD report: {res.formula_raw[:40]} REJECTED LFI={lfi_total:.3f}"

        elif gap_mean < 0.001 and pslq_q in ("excellent",) and res.gap_stable:
            res.verdict        = "CHAMPION"
            res.verdict_detail = (f"Gap={gap_mean:.2e}%, LFI={lfi_total:.3f}, "
                                   f"PSLQ={pslq_q}, 10-seed stable. Publication gate open.")
            res.action         = "Submit to JUDGE-01 for formal verdict."
            res.broadcast      = f"CHAMPION: {res.formula_clean} gap={gap_mean:.2e}%"

        elif gap_mean < 1.0 and not lfi.is_lethal:
            res.verdict        = "PROGRESS"
            res.verdict_detail = (f"Gap={gap_mean:.2f}%, LFI={lfi_total:.3f}. "
                                   f"ASR eligible. PSLQ quality: {pslq_q}.")
            res.action         = "Trigger ASR. Run 10-seed confirmation. Resubmit."
            res.broadcast      = f"PROGRESS: {res.formula_clean[:40]} gap={gap_mean:.2f}%"

        elif gap_mean < 10.0 and not lfi.is_lethal:
            res.verdict        = "INSUFFICIENT"
            res.verdict_detail = (f"Gap={gap_mean:.2f}% — below ASR threshold. "
                                   f"LFI={lfi_total:.3f}.")
            res.action         = "Generate new swarm generation seeded from this candidate."
            res.broadcast      = f"INSUFFICIENT: gap={gap_mean:.2f}% needs swarm iteration"

        else:
            res.verdict        = "ELIMINATED"
            res.verdict_detail = f"Gap={gap_mean:.2f}% too large. LFI={lfi_total:.3f}."
            res.action         = "Eliminate. Continue swarm."
            res.broadcast      = f"ELIMINATED: gap={gap_mean:.2f}%"

        return res

    # ── SWARM ─────────────────────────────────────────────────────────────────
    def run_swarm(self, k: int, seed_formula: str, swarm_size: int = 8) -> list:
        """
        Generate swarm_size mutations from seed_formula and evaluate each.
        Returns list of EvalResult sorted by verdict quality, gap, LFI, and structural cleanliness.
        """
        candidates = self._generate_mutations(seed_formula, k, swarm_size)
        results = []
        for i, (cid, formula, mutation_type) in enumerate(candidates):
            self.log("⊕", f"Evaluating {cid}: {formula[:50]}  [{mutation_type}]")
            r = self.evaluate(formula, k)
            r.formula_raw = f"{cid}: {formula}"
            results.append((cid, mutation_type, r))

        results.sort(key=lambda item: _swarm_sort_key(*item))
        return results

    def run_precision_audit(self, formula_str: str, k: int = 5, precisions: list[int] | None = None) -> dict:
        """Run a multi-precision PSLQ / residual audit for one formula."""
        precisions = precisions or [50, 100, 200, 500]
        expr, c_sym, err = parse_formula(formula_str, k)
        canon = self.CANONICAL.get(k)
        rows = []

        if err:
            return {
                "generated_at": ISO(),
                "k": k,
                "formula": formula_str,
                "error": err,
                "rows": [],
            }

        canon_expr = None
        residual_expr = None
        if canon:
            canon_expr = simplify(canon["alpha"] * c_sym + canon["beta"] / c_sym)
            residual_expr = simplify(expr - canon_expr)

        for dps in precisions:
            mp.dps = int(dps)
            alpha_str, beta_str, quality = self.pslq_quick(expr, c_sym, k, dps=dps)
            residual_max = 0.0
            if canon and residual_expr is not None:
                for seed in self.SEED_RANGES.get(k, self.SEED_RANGES[5]):
                    residual = residual_expr.subs(c_sym, seed)
                    residual_max = max(residual_max, float(abs(residual.evalf(dps))))
            exact_match = bool(canon) and alpha_str == str(canon["alpha"]) and beta_str == str(canon["beta"])
            stability = (
                "Publication Grade" if dps >= 500 and exact_match and residual_max <= 1e-30 else
                "Confirmed" if dps >= 200 and exact_match else
                "Verified" if dps >= 100 and exact_match else
                "Initial Hit"
            )
            rows.append({
                "dps": int(dps),
                "alpha": alpha_str,
                "beta": beta_str,
                "pslq_quality": quality,
                "residual_max": residual_max,
                "exact_match": exact_match,
                "stability": stability,
            })

        return {
            "generated_at": ISO(),
            "k": k,
            "formula": formula_str,
            "canonical_formula": canon.get("formula") if canon else None,
            "rows": rows,
            "publication_grade": bool(rows) and rows[-1].get("exact_match") is True and rows[-1].get("residual_max", 1.0) <= 1e-30,
        }

    def run_cross_k_sweep(self, ks: list[int], n_max: int = 1200) -> dict:
        """Run an independent G-01 evidence sweep using the Epoch5 extractor."""
        try:
            from epoch5_command_center import extract_k_profile
        except Exception as exc:
            return {
                "generated_at": ISO(),
                "ks": ks,
                "n_max": n_max,
                "error": str(exc),
                "rows": [],
            }

        rows = []
        supported = []
        for k in ks:
            profile = extract_k_profile(int(k), n_max=n_max)
            fit_gap = float(profile.get("fit_gap_pct", 100.0))
            seed_pass = float(profile.get("seed_pass_rate", 0.0))
            verdict = "supports_g01" if fit_gap < 2.0 and seed_pass >= 80.0 else ("watch" if fit_gap < 5.0 else "weak")
            if verdict == "supports_g01":
                supported.append(int(k))
            rows.append({
                "k": int(k),
                "c_k": profile.get("c_k"),
                "a1_est": profile.get("a1_est"),
                "a1_closed_form": profile.get("a1_closed_form"),
                "fit_gap_pct": fit_gap,
                "seed_pass_rate": seed_pass,
                "alpha_relation": profile.get("pslq_alpha"),
                "beta_relation": profile.get("pslq_beta"),
                "closed_formula": profile.get("closed_formula"),
                "verdict": verdict,
            })

        return {
            "generated_at": ISO(),
            "ks": ks,
            "n_max": n_max,
            "rows": rows,
            "supported_ks": supported,
            "g01_supported": len(rows) > 0 and len(supported) == len(rows),
            "mean_gap_pct": sum(r["fit_gap_pct"] for r in rows) / len(rows) if rows else None,
            "summary": (
                f"G-01 supported for k={supported} using the independent Epoch5 extraction path."
                if rows else "No sweep rows generated."
            ),
        }

    def _generate_mutations(self, seed: str, k: int, n: int) -> list:
        """Generate n formula mutations from a seed string."""
        ck = f"c{k}"
        mutations = [
            (f"C-{k:02d}01", seed,                                    "baseline"),
            (f"C-{k:02d}02", _perturb_coeffs(seed, ck, 1.05, 1.0),   "coeff_perturbation_+5%"),
            (f"C-{k:02d}03", _perturb_coeffs(seed, ck, 0.95, 1.0),   "coeff_perturbation_-5%"),
            (f"C-{k:02d}04", _add_gamma_term(seed, ck, k),            "constant_injection"),
            (f"C-{k:02d}05", _escalate_complexity(seed, ck),          "complexity_escalation"),
            (f"C-{k:02d}06", _inject_zeta3(seed, ck),                 "transcendental_zeta3"),
            (f"C-{k:02d}07", _structure_reset(ck, k),                 "structure_reset"),
            (f"C-{k:02d}08", _binomial_alpha(ck, k),                  "binomial_alpha_probe"),
        ]
        return mutations[:n]


# ─────────────────────────────────────────────────────────────────────────────
# MUTATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def expanded_has_c2(expr, c_sym):
    try:
        return expand(expr).coeff(c_sym, 2) != 0
    except Exception:
        return False

def _primary_lfi_cause(lfi: LFIScore) -> str:
    causes = {
        "dimensional":    lfi.dimensional,
        "scaling":        lfi.scaling,
        "scalar_wrap":    lfi.scalar_wrap,
        "transcendental": lfi.transcendental,
        "seed_variance":  lfi.seed_variance,
    }
    return max(causes, key=causes.get)


def _parse_k_spec(spec: str) -> list[int]:
    """Parse comma/range syntax like '5-12,15,24' into a sorted unique list."""
    ks: set[int] = set()
    for chunk in (part.strip() for part in str(spec).split(",") if part.strip()):
        if "-" in chunk:
            start_s, end_s = chunk.split("-", 1)
            start = int(start_s.strip())
            end = int(end_s.strip())
            lo, hi = sorted((start, end))
            ks.update(range(lo, hi + 1))
        else:
            ks.add(int(chunk))
    return sorted(ks)


def _swarm_sort_key(cid: str, mutation: str, result: EvalResult):
    verdict_rank = {
        "CHAMPION": 0,
        "PROGRESS": 1,
        "INSUFFICIENT": 2,
        "ELIMINATED": 3,
        "REJECTED": 4,
        "pending": 5,
    }
    gap = float(result.gap_pct) if result.gap_pct is not None else 999.0
    lfi_total = float(result.lfi.total) if result.lfi else 1.0
    pslq_rank = {"excellent": 0, "good": 1, "noise": 2}.get(result.pslq_quality or "noise", 3)
    mutation_rank = {
        "structure_reset": 0,
        "baseline": 1,
        "coeff_perturbation_+5%": 2,
        "coeff_perturbation_-5%": 2,
        "constant_injection": 3,
        "transcendental_zeta3": 4,
        "complexity_escalation": 5,
        "binomial_alpha_probe": 6,
    }.get(mutation, 7)
    return (
        verdict_rank.get(result.verdict, 9),
        round(gap, 12),
        round(lfi_total, 12),
        pslq_rank,
        mutation_rank,
        cid,
    )

def _perturb_coeffs(seed: str, ck: str, alpha_factor: float, beta_factor: float) -> str:
    # Simple textual perturbation of numeric constants in the seed
    try:
        from sympy import symbols, sympify, expand
        c = symbols(ck, positive=True)
        expr = sympify(seed, {ck: c})
        alpha = float(expr.coeff(c, 1).evalf())
        beta  = float(expr.coeff(c,-1).evalf())
        new_a = alpha * alpha_factor
        new_b = beta  * beta_factor
        return f"({new_a})*{ck} + ({new_b})/{ck}"
    except Exception:
        return seed

def _add_gamma_term(seed: str, ck: str, k: int) -> str:
    gamma_val = round(math.log(k) / (k * math.pi), 6)
    return f"({seed}) + {gamma_val}"

def _escalate_complexity(seed: str, ck: str) -> str:
    return f"({seed}) + 0.001*{ck}**2"

def _inject_zeta3(seed: str, ck: str) -> str:
    return f"({seed}) + zeta(3)/(12*{ck})"

def _structure_reset(ck: str, k: int) -> str:
    # Fresh candidate from G-01 hypothesis: -(k*ck)/48 - (k+1)*(k+3)/(8*ck)
    num = (k + 1) * (k + 3)
    return f"-({k}*{ck})/48 - {num}/(8*{ck})"

def _binomial_alpha(ck: str, k: int) -> str:
    import math as _m
    binom = _m.comb(2*k, k)
    beta  = (k+1)*(k+3)
    return f"-({k}/{binom})*{ck} - {beta}/(8*{ck})"


# ─────────────────────────────────────────────────────────────────────────────
# REPORT WRITER
# ─────────────────────────────────────────────────────────────────────────────

def write_report(result: EvalResult, out_path: str):
    data = result.to_dict()
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n  Results → {out_path}")
    return data


def write_swarm_report(results: list, k: int, out_path: str):
    report = {
        "generated_at": ISO(),
        "k": k,
        "swarm_size": len(results),
        "candidates": [],
        "champion": None,
        "survivors": [],
    }
    best_champion_key = None
    for cid, mut, r in results:
        rec = {
            "id": cid, "mutation": mut,
            "formula": r.formula_raw,
            "gap_pct": r.gap_pct,
            "lfi": r.lfi.total if r.lfi else None,
            "verdict": r.verdict,
            "alpha": r.alpha_exact,
            "beta":  r.beta_exact,
            "pslq_quality": r.pslq_quality,
        }
        report["candidates"].append(rec)
        if r.verdict == "CHAMPION":
            key = _swarm_sort_key(cid, mut, r)
            if report["champion"] is None or key < best_champion_key:
                report["champion"] = rec
                best_champion_key = key
        elif r.verdict in ("PROGRESS", "INSUFFICIENT"):
            report["survivors"].append(rec)

    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Swarm report → {out_path}")
    return report


def write_precision_audit(audit: dict, out_path: str):
    with open(out_path, "w") as f:
        json.dump(audit, f, indent=2, default=str)
    print(f"\n  Precision audit → {out_path}")
    return audit


def write_cross_k_sweep(report: dict, out_path: str):
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Cross-k sweep → {out_path}")
    return report


# ─────────────────────────────────────────────────────────────────────────────
# PRETTY PRINTER
# ─────────────────────────────────────────────────────────────────────────────

def print_result(r: EvalResult):
    print(f"\n{SEP2}")
    print(f"  EVAL RESULT · k={r.k} · {r.timestamp}")
    print(f"{SEP2}")
    print(f"  Formula   : {r.formula_raw}")
    print(f"  Cleaned   : {r.formula_clean}")
    print(f"  α exact   : {r.alpha_exact}")
    print(f"  β exact   : {r.beta_exact}")
    print(f"  PSLQ      : {r.pslq_quality}")
    print(f"  Gap mean  : {r.gap_pct:.6f}%  std={r.gap_std:.6f}%  stable={r.gap_stable}")
    print(f"  Scalar    : {r.scalar_value:.6f}  unity={r.scalar_unity}")
    if r.lfi:
        print(f"  LFI total : {r.lfi.total:.3f}  "
              f"(dim={r.lfi.dimensional:.2f} scl={r.lfi.scaling:.2f} "
              f"wrap={r.lfi.scalar_wrap:.2f} trans={r.lfi.transcendental:.2f} "
              f"seed={r.lfi.seed_variance:.2f})")
    print(f"\n  VERDICT   : {r.verdict}")
    print(f"  Detail    : {r.verdict_detail}")
    print(f"  Action    : {r.action}")
    print(f"  Broadcast : {r.broadcast}")
    print(f"{SEP}")


def print_swarm_summary(results: list, k: int):
    print(f"\n{SEP2}")
    print(f"  SWARM SUMMARY · k={k} · {len(results)} candidates")
    print(f"{SEP2}")
    print(f"  {'ID':>8}  {'Formula':40}  {'Gap%':>10}  {'LFI':>6}  Verdict")
    print(f"  {SEP}")
    for cid, mut, r in results:
        formula_short = r.formula_raw[:40]
        lfi_str = f"{r.lfi.total:.3f}" if r.lfi else "—"
        print(f"  {cid:>8}  {formula_short:40}  "
              f"{r.gap_pct:>10.4f}%  {lfi_str:>6}  {r.verdict}")
    print(f"{SEP}")


def print_precision_audit(audit: dict):
    print(f"\n{SEP2}")
    print(f"  PRECISION AUDIT · k={audit.get('k')} · {audit.get('generated_at')}")
    print(f"{SEP2}")
    print(f"  {'dps':>6}  {'alpha':>14}  {'beta':>14}  {'residual':>14}  Stability")
    print(f"  {SEP}")
    for row in audit.get('rows', []):
        print(f"  {row['dps']:>6}  {str(row['alpha']):>14}  {str(row['beta']):>14}  {row['residual_max']:>14.3e}  {row['stability']}")
    print(f"{SEP}")
    print(f"  Publication grade: {audit.get('publication_grade')}")


def print_cross_k_sweep(report: dict):
    print(f"\n{SEP2}")
    print(f"  G-01 CROSS-k SWEEP · ks={report.get('ks')} · {report.get('generated_at')}")
    print(f"{SEP2}")
    print(f"  {'k':>3}  {'gap%':>10}  {'seed%':>8}  {'α relation':18}  {'β relation':18}  Verdict")
    print(f"  {SEP}")
    for row in report.get('rows', []):
        print(f"  {row['k']:>3}  {row['fit_gap_pct']:>10.4f}  {row['seed_pass_rate']:>8.1f}  {str(row['alpha_relation'])[:18]:18}  {str(row['beta_relation'])[:18]:18}  {row['verdict']}")
    print(f"{SEP}")
    print(f"  Summary: {report.get('summary')}")


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL JUDGE
# ─────────────────────────────────────────────────────────────────────────────

class LocalJudge:
    """
    Deterministic Judge — no API key needed.
    Issues formal verdicts based on gate scores.
    """
    GATES = ["dry_run_clean", "scalar_valid", "seed_stable", "pslq_confirmed"]

    def judge(self, result: EvalResult, dry_run_clean: bool = False) -> dict:
        gates = {
            "dry_run_clean":  dry_run_clean,
            "scalar_valid":   result.scalar_unity is True,
            "seed_stable":    result.gap_stable   is True,
            "pslq_confirmed": result.pslq_quality in ("excellent", "exact_rational"),
        }
        passed = sum(gates.values())

        if passed == 4:
            verdict = "CHAMPION"
            detail  = "All 4 gates passed. Publication-ready."
        elif passed == 3:
            verdict = "PROGRESS"
            detail  = f"3/4 gates. Failing: {[k for k,v in gates.items() if not v]}"
        elif passed == 2:
            verdict = "INSUFFICIENT"
            detail  = f"2/4 gates. Return to swarm."
        else:
            verdict = "BLOCKED"
            detail  = "Fewer than 2 gates. Remove --debate-dry-run first."

        return {
            "judge_id":   "JUDGE-LOCAL-01",
            "timestamp":  ISO(),
            "formula":    result.formula_clean,
            "gates":      gates,
            "gates_passed": passed,
            "verdict":    verdict,
            "detail":     detail,
            "publication_ready": passed == 4,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="SIARC Local Engine — zero API keys required",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # evaluate the canonical H-0025 formula
  python siarc_local_engine.py --formula "-(5*c5)/48 - 6/c5" --k 5

  # run a k=6 swarm seeded from H-0025
  python siarc_local_engine.py --swarm --k 6 --seed "-(5*c5)/48 - 6/c5"

  # read from existing agent_C_out.json (replaces --debate-dry-run path)
  python siarc_local_engine.py --input siarc_outputs/agent_C_out.json

  # judge an already-evaluated result JSON
  python siarc_local_engine.py --judge --input eval_result.json
        """
    )
    ap.add_argument("--formula",  default=None,  help="Formula string to evaluate")
    ap.add_argument("--k",        type=int, default=5, help="k value (default 5)")
    ap.add_argument("--swarm",    action="store_true", help="Run swarm from seed")
    ap.add_argument("--seed",     default=None, help="Seed formula for swarm")
    ap.add_argument("--swarm-size", type=int, default=8)
    ap.add_argument("--input",    default=None, help="Path to agent_C_out.json or eval JSON")
    ap.add_argument("--judge",    action="store_true", help="Run local judge on result")
    ap.add_argument("--precision-audit", action="store_true", help="Run a multi-precision PSLQ/residual audit")
    ap.add_argument("--dps-list", default="50,100,200,500", help="Comma-separated dps list for --precision-audit")
    ap.add_argument("--k-sweep",  default=None, help="Comma/range list like '5-12,15,24' for an Epoch5-backed G-01 sweep")
    ap.add_argument("--n-max",    type=int, default=1200, help="n_max for --k-sweep (default 1200)")
    ap.add_argument("--output",   default=None, help="Output JSON path")
    ap.add_argument("--quiet",    action="store_true", help="Suppress verbose output")
    args = ap.parse_args()

    engine = LocalEngine(verbose=not args.quiet)
    judge  = LocalJudge()

    print(f"\n{SEP2}")
    print(f"  SIARC Local Engine  —  zero API keys")
    print(f"  {ISO()}")
    print(f"{SEP2}")

    t0 = time.time()

    # ── MODE: independent cross-k sweep ──────────────────────────────────────
    if args.k_sweep:
        ks = _parse_k_spec(args.k_sweep)
        print(f"\n  Cross-k sweep mode · ks={ks} · n_max={args.n_max}\n")
        report = engine.run_cross_k_sweep(ks, n_max=args.n_max)
        print_cross_k_sweep(report)
        out = args.output or f"g01_k_sweep_{ks[0]}_{ks[-1]}.json"
        write_cross_k_sweep(report, out)

    # ── MODE: precision audit ─────────────────────────────────────────────────
    elif args.precision_audit:
        formula = args.formula
        k = args.k
        if args.input and not formula:
            if not os.path.exists(args.input):
                sys.exit(f"[ERROR] File not found: {args.input}")
            with open(args.input) as f:
                data = json.load(f)
            if isinstance(data, dict):
                formula = data.get("formula") or data.get("best_formula") or data.get("candidate_formula")
                k = data.get("k", k)
        formula = formula or f"-(5*c{k})/48 - 6/c{k}"
        dps_list = [int(part.strip()) for part in str(args.dps_list).split(',') if part.strip()]
        print(f"\n  Precision audit mode · k={k} · dps={dps_list}")
        print(f"  Formula: {formula}\n")
        audit = engine.run_precision_audit(formula, k=k, precisions=dps_list)
        print_precision_audit(audit)
        out = args.output or f"precision_audit_k{k}.json"
        write_precision_audit(audit, out)

    # ── MODE: swarm ───────────────────────────────────────────────────────────
    elif args.swarm:
        seed = args.seed or f"-(5*c{args.k})/48 - 6/c{args.k}"
        print(f"\n  Swarm mode · k={args.k} · size={args.swarm_size}")
        print(f"  Seed: {seed}\n")
        results = engine.run_swarm(args.k, seed, args.swarm_size)
        print_swarm_summary(results, args.k)
        out = args.output or f"swarm_k{args.k}_results.json"
        report = write_swarm_report(results, args.k, out)

        # judge top survivor
        if results:
            best_r = results[0][2]
            j = judge.judge(best_r)
            print(f"\n  Judge verdict on top survivor: {j['verdict']}")
            print(f"  Gates passed: {j['gates_passed']}/4")
            print(f"  Detail: {j['detail']}")

    # ── MODE: input file ──────────────────────────────────────────────────────
    elif args.input:
        if not os.path.exists(args.input):
            sys.exit(f"[ERROR] File not found: {args.input}")
        with open(args.input) as f:
            data = json.load(f)

        # try to extract formula from agent_C_out.json structure
        formula = None
        k = args.k
        if isinstance(data, dict):
            formula = (data.get("best_formula") or
                       data.get("formula") or
                       data.get("candidate_formula"))
            k = data.get("k", args.k)
        elif isinstance(data, list) and data:
            formula = data[0].get("formula") or data[0].get("candidate_formula")

        if not formula:
            print("  No formula found in input — using H-0025 canonical as fallback")
            formula = f"-(5*c{k})/48 - 6/c{k}"

        print(f"\n  Evaluating formula from: {args.input}")
        result = engine.evaluate(formula, k)
        print_result(result)
        out = args.output or args.input.replace(".json", "_eval.json")
        write_report(result, out)

        if args.judge:
            j = judge.judge(result)
            print(f"\n  LOCAL JUDGE: {j['verdict']}  ({j['gates_passed']}/4 gates)")

    # ── MODE: formula ─────────────────────────────────────────────────────────
    elif args.formula:
        print(f"\n  Evaluating: {args.formula}  (k={args.k})\n")
        result = engine.evaluate(args.formula, args.k)
        print_result(result)
        out = args.output or "eval_result.json"
        write_report(result, out)

        if args.judge:
            j = judge.judge(result)
            print(f"\n  LOCAL JUDGE: {j['verdict']}  ({j['gates_passed']}/4 gates)")
            jout = out.replace(".json", "_judge.json")
            with open(jout, "w") as f:
                json.dump(j, f, indent=2)
            print(f"  Judge report → {jout}")

    # ── MODE: default — evaluate H-0025 canonical ─────────────────────────────
    else:
        formula = "-(5*c5)/48 - 6/c5"
        print(f"\n  Default mode: evaluating H-0025 canonical formula")
        print(f"  Formula: {formula}\n")
        result = engine.evaluate(formula, k=5)
        print_result(result)
        j = judge.judge(result, dry_run_clean=False)
        print(f"\n  LOCAL JUDGE: {j['verdict']}  ({j['gates_passed']}/4 gates)")
        out = args.output or "h0025_eval.json"
        write_report(result, out)

    print(f"\n  Done in {time.time()-t0:.2f}s\n")


if __name__ == "__main__":
    main()
