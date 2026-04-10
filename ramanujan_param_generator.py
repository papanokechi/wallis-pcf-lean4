"""
ramanujan_param_generator.py
============================
Generates parameter sets (command lines + JSON manifests) for
ramanujan_breakthrough_generator.py v2.0.

Usage
-----
    python ramanujan_param_generator.py                     # interactive menu
    python ramanujan_param_generator.py --goal conjecture   # Pi Family proof runs
    python ramanujan_param_generator.py --goal vquad        # V_quad companion hunt
    python ramanujan_param_generator.py --goal parity       # parity theorem sweep
    python ramanujan_param_generator.py --goal logarithm    # Logarithmic Ladder checks
    python ramanujan_param_generator.py --goal sweep        # broad overnight sweep
    python ramanujan_param_generator.py --goal all          # every goal, full manifest
    python ramanujan_param_generator.py --list-goals        # show all goals

Optional flags
    --out-dir PATH      where to write run scripts (default: ./rbg_runs)
    --generator PATH    path to ramanujan_breakthrough_generator.py
                        (default: ./ramanujan_breakthrough_generator.py)
    --format bat|sh     shell format (default: auto-detect OS; sh on Linux/Mac, bat on Windows)
    --dry-run           print commands without writing files
    --json-only         only write the JSON manifest, not shell scripts

The generator produces:
  rbg_runs/
    manifest_<goal>_<timestamp>.json      — full parameter manifest
    run_<goal>_<timestamp>.sh/.bat        — ready-to-execute shell script
    README_<goal>_<timestamp>.txt         — human-readable notes
"""

import argparse
import json
import os
import platform
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETER SET DATA STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ParamSet:
    """One complete run specification for ramanujan_breakthrough_generator.py."""
    run_id: str                         # e.g. "pi_family_m1_proof_001"
    goal: str                           # human-readable goal category
    priority: str                       # "critical" | "high" | "medium" | "exploratory"
    mode: str                           # CLI --mode value
    target: str = "pi"                  # CLI --target
    deg_alpha: int = 2                  # CLI --deg-alpha
    deg_beta: int = 2                   # CLI --deg-beta
    coeff_range: int = 10               # CLI --coeff-range
    depth: int = 200                    # CLI --depth
    precision: int = 50                 # CLI --precision
    budget: int = 500                   # CLI --budget
    seed_boost: int = 3                 # CLI --seed-boost
    no_ai: bool = False                 # CLI --no-ai flag
    max_time: int = 0                   # CLI --max-time (0 = unlimited)
    formula: str = ""                   # CLI --formula
    analysis_mode: str = ""             # CLI --analysis-mode
    filter_novelty: str = ""            # CLI --filter-novelty
    min_digits: int = 0                 # CLI --min-digits
    export: str = ""                    # CLI --export (auto-filled if empty)
    # Metadata
    rationale: str = ""                 # why this run
    expected_runtime_min: float = 0.0   # rough estimate in minutes
    notes: str = ""                     # extra notes / what to look for
    tags: list = field(default_factory=list)

    def to_cli(self, generator_path: str = "ramanujan_breakthrough_generator.py",
               export_dir: str = ".") -> str:
        """Build the full CLI command string."""
        parts = [f"python {generator_path}"]
        parts.append(f"--mode {self.mode}")

        # Only include target for search modes
        search_modes = {"mitm", "dr", "cmf", "hybrid", "analyze"}
        if self.mode in search_modes:
            parts.append(f"--target {self.target}")

        # Degree flags — only for search modes
        if self.mode in {"mitm", "dr", "cmf", "hybrid"}:
            parts.append(f"--deg-alpha {self.deg_alpha}")
            parts.append(f"--deg-beta {self.deg_beta}")
            parts.append(f"--coeff-range {self.coeff_range}")

        # Universal numeric flags
        parts.append(f"--depth {self.depth}")
        parts.append(f"--precision {self.precision}")

        if self.mode in {"mitm", "dr", "cmf", "hybrid", "quadratic_gcf"}:
            parts.append(f"--budget {self.budget}")

        if self.mode in {"cmf", "hybrid"}:
            parts.append(f"--seed-boost {self.seed_boost}")

        if self.max_time > 0:
            parts.append(f"--max-time {self.max_time}")

        if self.formula:
            parts.append(f'--formula "{self.formula}"')

        if self.analysis_mode:
            parts.append(f"--analysis-mode {self.analysis_mode}")

        if self.filter_novelty:
            parts.append(f"--filter-novelty {self.filter_novelty}")

        if self.min_digits > 0:
            parts.append(f"--min-digits {self.min_digits}")

        if self.no_ai:
            parts.append("--no-ai")

        # Auto-generate export path if not set
        export_path = self.export or str(
            Path(export_dir) / f"session_{self.run_id}.json"
        )
        parts.append(f"--export {export_path}")

        return " ".join(parts)

    def estimated_runtime_str(self) -> str:
        t = self.expected_runtime_min
        if t == 0:
            return "unknown"
        if t < 1:
            return f"~{int(t*60)}s"
        if t < 60:
            return f"~{t:.0f} min"
        return f"~{t/60:.1f} hr"


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETER LIBRARIES — one function per research goal
# ═══════════════════════════════════════════════════════════════════════════════

def goal_conjecture() -> list:
    """
    Pi Family Conjecture 1: prove p_n = (2n−1)!! · P(n) for m=0..5.
    Escalating depth/precision to harden the proof across m values.
    Also includes hypergeometric Γ-formula verification as a companion.
    """
    sets = []

    # Phase 1: Quick symbolic proof attempt (sympy induction)
    sets.append(ParamSet(
        run_id="conjecture_proof_quick",
        goal="conjecture",
        priority="critical",
        mode="conjecture_prover",
        depth=200,
        precision=50,   # not used internally but sets context
        rationale="Quick symbolic proof via Lagrange interpolation + sympy induction for m=0..5",
        expected_runtime_min=0.5,
        notes="If m=1 shows PROVED, Conjecture 1 is done. Check output for status=PROVED.",
        tags=["Pi_Family", "Conjecture_1", "sympy", "induction"],
    ))

    # Phase 2: Deeper N to verify polynomial fit holds far out
    sets.append(ParamSet(
        run_id="conjecture_proof_deep",
        goal="conjecture",
        priority="critical",
        mode="conjecture_prover",
        depth=500,
        precision=50,
        rationale="Extend N=500 to stress-test Lagrange polynomial fit and induction far from base cases",
        expected_runtime_min=2.0,
        notes="Look for no_poly_fit status — means the (2n-1)!! ansatz breaks at large n.",
        tags=["Pi_Family", "Conjecture_1", "verification", "deep"],
    ))

    # Phase 3: Hypergeometric Γ-formula at standard precision
    sets.append(ParamSet(
        run_id="hypergeometric_standard",
        goal="conjecture",
        priority="high",
        mode="hypergeometric_guess",
        depth=3000,
        precision=100,
        rationale="Verify val(m) = 2Γ(m+1)/(√π·Γ(m+½)) for integer and half-integer m",
        expected_runtime_min=3.0,
        notes="Half-integers → exact rationals; integers → π-multiples. Ratio check proves recurrence.",
        tags=["Pi_Family", "Gamma_formula", "hypergeometric"],
    ))

    # Phase 4: Hypergeometric high precision (publication-grade)
    sets.append(ParamSet(
        run_id="hypergeometric_highprec",
        goal="conjecture",
        priority="high",
        mode="hypergeometric_guess",
        depth=5000,
        precision=200,
        rationale="150-digit Γ-formula verification — publication-grade evidence for all m in paper",
        expected_runtime_min=15.0,
        notes="Γ-match digits should equal precision for all m. If any < 150, increase depth.",
        tags=["Pi_Family", "Gamma_formula", "high_precision", "publication"],
    ))

    # Phase 5: CMF search for new Pi Family PCFs (deg 3 numerators for m≥2)
    sets.append(ParamSet(
        run_id="pi_family_cmf_deg3",
        goal="conjecture",
        priority="medium",
        mode="cmf",
        target="pi",
        deg_alpha=3,
        deg_beta=2,
        coeff_range=12,
        depth=300,
        precision=100,
        budget=1000,
        seed_boost=2,
        no_ai=True,
        rationale="CMF search for new Pi Family members with degree-3 numerators (needed for m≥2)",
        expected_runtime_min=20.0,
        notes="Degree-3 α(n) matches Pi Family structure for m≥2. seed_boost=2 tight around known seeds.",
        tags=["Pi_Family", "CMF", "deg3", "new_PCF"],
    ))

    # Phase 6: Hybrid search — CMF seeds → D&R refinement
    sets.append(ParamSet(
        run_id="pi_family_hybrid",
        goal="conjecture",
        priority="medium",
        mode="hybrid",
        target="pi",
        deg_alpha=2,
        deg_beta=2,
        coeff_range=10,
        depth=250,
        precision=80,
        budget=800,
        seed_boost=3,
        no_ai=True,
        rationale="Hybrid CMF→D&R to find π PCFs not reachable by pure CMF",
        expected_runtime_min=30.0,
        notes="D&R phase perturbs around CMF hits; diversifies the search landscape.",
        tags=["Pi_Family", "hybrid", "DR", "CMF"],
    ))

    return sets


def goal_vquad() -> list:
    """
    V_quad companion hunt: find new unidentifiable constants from quadratic GCFs.
    Escalating precision and budget to build the V_quad family.
    """
    sets = []

    # Standard hunt
    sets.append(ParamSet(
        run_id="vquad_standard",
        goal="vquad",
        priority="high",
        mode="quadratic_gcf",
        budget=500,
        precision=200,
        rationale="Standard V_quad family sweep: A∈[1,7], B∈[-6,6], C∈[1,7]",
        expected_runtime_min=10.0,
        notes="Candidates printed with discriminant tag. Negative disc → elliptic-type behaviour.",
        tags=["V_quad", "quadratic_GCF", "new_constants"],
    ))

    # High-budget overnight
    sets.append(ParamSet(
        run_id="vquad_overnight",
        goal="vquad",
        priority="high",
        mode="quadratic_gcf",
        budget=2000,
        precision=300,
        rationale="Overnight high-precision sweep to find weaker candidates missed at 200 digits",
        expected_runtime_min=120.0,
        notes="300 dps → mp.dps=350. Increases chance of catching near-algebraic constants.",
        tags=["V_quad", "quadratic_GCF", "overnight", "high_precision"],
    ))

    # PSLQ exclusion analysis of V_quad itself
    sets.append(ParamSet(
        run_id="vquad_pslq_analysis",
        goal="vquad",
        priority="high",
        mode="analyze",
        target="pi",  # not used in analyze mode
        formula="V_quad ≈ 1.19737... — GCF with b(n)=n^2+n+1, a(n)=1",
        analysis_mode="pslq",
        depth=150,
        precision=150,
        rationale="PSLQ exclusion analysis of V_quad from all 16 known function families",
        expected_runtime_min=5.0,
        notes="Adds Heun-type and weight-3 motivic periods to exclusion basis.",
        tags=["V_quad", "PSLQ", "exclusion", "transcendence"],
    ))

    # Irrationality bound check
    sets.append(ParamSet(
        run_id="vquad_irrationality",
        goal="vquad",
        priority="medium",
        mode="analyze",
        formula="V_quad ≈ 1.19737... — μ=2 irrationality measure via Wronskian",
        analysis_mode="irrationality",
        depth=150,
        precision=150,
        rationale="Irrationality measure μ=2 confirmation via Wronskian method",
        expected_runtime_min=3.0,
        notes="Should confirm μ=2 (provably irrational). Check if AI suggests μ>2 path.",
        tags=["V_quad", "irrationality_measure", "Wronskian"],
    ))

    # MITM search for V_quad relatives
    sets.append(ParamSet(
        run_id="vquad_mitm_relatives",
        goal="vquad",
        priority="medium",
        mode="mitm",
        target="zeta3",   # V_quad is near ζ(3) territory
        deg_alpha=1,
        deg_beta=2,
        coeff_range=8,
        depth=200,
        precision=80,
        budget=3000,
        no_ai=True,
        rationale="MITM sweep for degree-(1,2) PCFs near ζ(3) — probes V_quad algebraic relatives",
        expected_runtime_min=25.0,
        notes="a(n)=linear, b(n)=quadratic matches V_quad family structure exactly.",
        tags=["V_quad", "MITM", "relatives", "zeta3"],
    ))

    return sets


def goal_parity() -> list:
    """
    Parity theorem verification: even c → rational, odd c → π-multiple.
    Multiple depth/precision tiers up to publication-grade.
    """
    sets = []

    # Standard (paper result)
    sets.append(ParamSet(
        run_id="parity_standard",
        goal="parity",
        priority="critical",
        mode="parity",
        depth=3000,
        precision=80,   # internally hardcoded to 80 dps; this is context only
        rationale="Parity theorem verification c=1..20 at standard depth",
        expected_runtime_min=5.0,
        notes="All ✓ expected. Any ? → increase depth. Even c should give exact rational via a(c/2)=0.",
        tags=["parity", "Pi_Family", "theorem", "verification"],
    ))

    # Deep verification
    sets.append(ParamSet(
        run_id="parity_deep",
        goal="parity",
        priority="high",
        mode="parity",
        depth=5000,
        precision=80,
        rationale="Deep parity verification: extra convergence margin for large c",
        expected_runtime_min=15.0,
        notes="For c=19,20 (large m), depth=3000 may leave only 50-digit agreement. 5000 should hit 70+.",
        tags=["parity", "Pi_Family", "deep", "publication"],
    ))

    # Extended c range (beyond paper, exploratory)
    sets.append(ParamSet(
        run_id="parity_extended_c",
        goal="parity",
        priority="exploratory",
        mode="parity",
        depth=4000,
        precision=80,
        rationale="Extend parity check to c=1..30 (edit c_range in source: range(1,31))",
        expected_runtime_min=25.0,
        notes="Requires modifying c_range in run_parity_theorem() to range(1,31). "
              "Tests whether parity persists beyond c=20.",
        tags=["parity", "exploratory", "extended"],
    ))

    return sets


def goal_logarithm() -> list:
    """
    Logarithmic Ladder: verify 1/ln(k/(k-1)) at multiple k values,
    and search for new PCF representations.
    """
    sets = []

    # Verification at k=2 (ln2 target)
    sets.append(ParamSet(
        run_id="logladder_ln2_verify",
        goal="logarithm",
        priority="critical",
        mode="cmf",
        target="ln2",
        deg_alpha=2,
        deg_beta=2,
        coeff_range=10,
        depth=200,
        precision=100,
        budget=500,
        seed_boost=1,
        no_ai=True,
        rationale="CMF verification of Logarithmic Ladder at k=2 (target = ln2 = 1/ln(2/1))",
        expected_runtime_min=8.0,
        notes="seed_boost=1 tight — should immediately hit the known PCF from the paper.",
        tags=["LogLadder", "ln2", "CMF", "verification"],
    ))

    # Verification at k=3 (ln(3/2) = ln3 - ln2)
    sets.append(ParamSet(
        run_id="logladder_ln32_verify",
        goal="logarithm",
        priority="high",
        mode="mitm",
        target="ln2",  # 1/ln(3/2) = 1/(ln3-ln2); not in dict — closest proxy
        deg_alpha=2,
        deg_beta=2,
        coeff_range=12,
        depth=200,
        precision=80,
        budget=2000,
        no_ai=True,
        rationale="MITM search for k=3 Ladder: 1/ln(3/2). Note: add 'ln_3_2' to CONSTANTS dict first.",
        expected_runtime_min=20.0,
        notes="Add to CONSTANTS: 'ln_3_2': ('1/ln(3/2)', '1.8204...') and to _get_constant(): "
              "mpmath.mpf(1)/mpmath.log(mpmath.mpf(3)/2). Then use --target ln_3_2.",
        tags=["LogLadder", "k=3", "MITM", "new_verification"],
    ))

    # New k values: k=5 (1/ln(5/4))
    sets.append(ParamSet(
        run_id="logladder_k5",
        goal="logarithm",
        priority="high",
        mode="dr",
        target="ln2",  # proxy — replace with ln_5_4 after adding to dict
        deg_alpha=2,
        deg_beta=2,
        coeff_range=12,
        depth=250,
        precision=80,
        budget=1500,
        no_ai=True,
        rationale="D&R search for k=5 Logarithmic Ladder: 1/ln(5/4). Add 'ln_5_4' to dict first.",
        expected_runtime_min=30.0,
        notes="Add: mpmath.mpf(1)/mpmath.log(mpmath.mpf(5)/4). "
              "The Ladder formula gives explicit α,β polynomials — hardcode as CMF seeds too.",
        tags=["LogLadder", "k=5", "DR", "new_k"],
    ))

    # Factorial reduction check on Ladder PCF
    sets.append(ParamSet(
        run_id="logladder_factorial_check",
        goal="logarithm",
        priority="medium",
        mode="analyze",
        formula="Log Ladder PCF: alpha(n) = n*(n-1), beta(n) = 2n-1 (k=2 case)",
        analysis_mode="factorial",
        depth=100,
        precision=60,
        rationale="Factorial reduction check on known Ladder PCF — confirms Taylor-series proof structure",
        expected_runtime_min=1.0,
        notes="Should report FR=yes; gcd(p_n,q_n) grows factorially matching (n-1)! in denominator.",
        tags=["LogLadder", "factorial_reduction", "analysis"],
    ))

    # CMF seed hunt across all log-type constants
    sets.append(ParamSet(
        run_id="logladder_cmf_alllog",
        goal="logarithm",
        priority="medium",
        mode="cmf",
        target="ln3",
        deg_alpha=2,
        deg_beta=2,
        coeff_range=10,
        depth=200,
        precision=80,
        budget=600,
        seed_boost=3,
        no_ai=True,
        rationale="CMF search for ln3-related PCFs — extends Ladder family to log(3/2) territory",
        expected_runtime_min=10.0,
        notes="Results can be combined: 1/ln(3/2) = 1/(ln3-ln2). Look for additive combinations.",
        tags=["LogLadder", "ln3", "CMF", "family_extension"],
    ))

    return sets


def goal_heun() -> list:
    """
    4/π Heun-type strand: explore the Pochhammer obstruction
    and Padé near-miss structure.
    """
    sets = []

    # MITM for 4/pi with phi-related numerators
    sets.append(ParamSet(
        run_id="heun_4pi_mitm",
        goal="heun",
        priority="high",
        mode="mitm",
        target="pi",
        deg_alpha=3,
        deg_beta=3,
        coeff_range=8,
        depth=300,
        precision=100,
        budget=2000,
        no_ai=True,
        rationale="MITM for 4/π with degree-3 polynomials — targets Heun-type structure",
        expected_runtime_min=40.0,
        notes="Heun equations have 4 singular points → degree-3 or higher polynomials. "
              "Look for hits near 4/π = 1.2732...",
        tags=["Heun", "4_over_pi", "MITM", "deg3"],
    ))

    # Phi-seeded CMF
    sets.append(ParamSet(
        run_id="heun_phi_cmf",
        goal="heun",
        priority="high",
        mode="cmf",
        target="phi",
        deg_alpha=2,
        deg_beta=2,
        coeff_range=10,
        depth=250,
        precision=80,
        budget=800,
        seed_boost=2,
        no_ai=True,
        rationale="CMF near φ (golden ratio) — probes Pochhammer-φ numerator structure",
        expected_runtime_min=15.0,
        notes="Golden-ratio Pochhammer roots are the key feature. Look for PCFs whose value "
              "is a rational function of φ and π.",
        tags=["Heun", "phi", "Pochhammer", "CMF"],
    ))

    # Pade near-miss analysis
    sets.append(ParamSet(
        run_id="heun_pade_analysis",
        goal="heun",
        priority="medium",
        mode="analyze",
        formula="4/pi PCF with Pochhammer numerators involving golden-ratio roots — Pade near-miss",
        analysis_mode="cmf",
        depth=200,
        precision=100,
        rationale="CMF analysis of the Padé near-miss structure — classify as Heun or _3F2",
        expected_runtime_min=2.0,
        notes="The Padé near-miss suggests a _3F2 hypergeometric underlying the PCF. "
              "AI analysis mode 'cmf' will attempt to classify the CMF family.",
        tags=["Heun", "Pade", "3F2", "analysis"],
    ))

    return sets


def goal_sweep() -> list:
    """
    Broad overnight sweep across multiple targets and algorithms.
    Maximises chance of finding something genuinely new.
    """
    targets = ["pi", "zeta3", "catalan", "euler_gamma"]
    modes = [
        ("mitm", 2, 2, 10, 300),   # (mode, deg_a, deg_b, coeff_r, budget)
        ("dr",   2, 2, 10, 500),
        ("cmf",  2, 2, 10, 400),
        ("cmf",  3, 2, 8,  300),
    ]
    sets = []
    for target in targets:
        for mode, da, db, cr, bud in modes:
            run_id = f"sweep_{target}_{mode}_d{da}{db}"
            sets.append(ParamSet(
                run_id=run_id,
                goal="sweep",
                priority="medium",
                mode=mode,
                target=target,
                deg_alpha=da,
                deg_beta=db,
                coeff_range=cr,
                depth=250,
                precision=80,
                budget=bud,
                seed_boost=3,
                no_ai=True,
                max_time=600,  # 10 min per run in sweep mode
                rationale=f"Broad sweep: {target} via {mode} deg({da},{db})",
                expected_runtime_min=10.0,
                notes="Part of overnight sweep. --max-time 600 prevents runaway.",
                tags=["sweep", target, mode, f"deg{da}{db}"],
            ))
    return sets


def goal_all() -> list:
    """Aggregate all goals."""
    sets = []
    for fn in [goal_conjecture, goal_vquad, goal_parity,
               goal_logarithm, goal_heun, goal_sweep]:
        sets.extend(fn())
    return sets


GOAL_REGISTRY = {
    "conjecture": (goal_conjecture, "Pi Family Conjecture 1 proof + Gamma-formula verification"),
    "vquad":      (goal_vquad,      "V_quad companion constant hunt + PSLQ exclusion analysis"),
    "parity":     (goal_parity,     "Even/odd parity theorem verification (all tiers)"),
    "logarithm":  (goal_logarithm,  "Logarithmic Ladder verification at multiple k values"),
    "heun":       (goal_heun,       "4/π Heun-type strand: Pochhammer obstruction + Padé near-miss"),
    "sweep":      (goal_sweep,      "Broad overnight sweep across 4 targets × 4 algorithms"),
    "all":        (goal_all,        "Everything — full manifest for the research roadmap"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT WRITERS
# ═══════════════════════════════════════════════════════════════════════════════

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "exploratory": 3}

def sorted_sets(sets: list) -> list:
    return sorted(sets, key=lambda s: PRIORITY_ORDER.get(s.priority, 9))


def write_manifest(sets: list, goal: str, out_dir: Path, ts: str) -> Path:
    """Write JSON manifest of all parameter sets."""
    data = {
        "generated_at": ts,
        "goal": goal,
        "generator_version": "v2.0",
        "total_runs": len(sets),
        "estimated_total_min": sum(s.expected_runtime_min for s in sets),
        "runs": [asdict(s) for s in sets],
    }
    path = out_dir / f"manifest_{goal}_{ts}.json"
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return path


def write_shell_script(sets: list, goal: str, out_dir: Path, ts: str,
                       generator_path: str, fmt: str) -> Path:
    """Write executable shell script (sh or bat)."""
    ext = "bat" if fmt == "bat" else "sh"
    path = out_dir / f"run_{goal}_{ts}.{ext}"
    export_dir = str(out_dir)

    lines = []
    if fmt == "bat":
        lines += [
            "@echo off",
            f"REM Ramanujan Breakthrough Generator — {goal} runs",
            f"REM Generated: {ts}",
            f"REM Runs: {len(sets)}",
            f"REM Estimated total time: {sum(s.expected_runtime_min for s in sets):.0f} min",
            "",
            f"SET GENERATOR={generator_path}",
            f"SET EXPORT_DIR={export_dir}",
            "",
        ]
        for s in sets:
            lines += [
                f"REM ── [{s.priority.upper()}] {s.run_id} ──",
                f"REM {s.rationale}",
                f"REM ETA: {s.estimated_runtime_str()}",
                s.to_cli(generator_path, export_dir),
                "",
            ]
    else:
        lines += [
            "#!/usr/bin/env bash",
            f"# Ramanujan Breakthrough Generator — {goal} runs",
            f"# Generated: {ts}",
            f"# Runs: {len(sets)}",
            f"# Estimated total time: {sum(s.expected_runtime_min for s in sets):.0f} min",
            "",
            f"GENERATOR={generator_path}",
            f"EXPORT_DIR={export_dir}",
            "",
            'set -e  # stop on first error; remove if you want all runs to attempt',
            "",
        ]
        for s in sets:
            lines += [
                f"# ── [{s.priority.upper()}] {s.run_id} ──",
                f"# {s.rationale}",
                f"# ETA: {s.estimated_runtime_str()}",
                s.to_cli(f"$GENERATOR", "$EXPORT_DIR"),
                "",
            ]

    path.write_text("\n".join(lines), encoding='utf-8')
    if fmt != "bat":
        path.chmod(0o755)
    return path


def write_readme(sets: list, goal: str, out_dir: Path, ts: str) -> Path:
    """Write human-readable README with all run details."""
    path = out_dir / f"README_{goal}_{ts}.txt"
    lines = [
        f"RAMANUJAN PARAMETER SETS — {goal.upper()}",
        f"Generated: {ts}",
        "=" * 60,
        f"Total runs:          {len(sets)}",
        f"Estimated total:     {sum(s.expected_runtime_min for s in sets):.0f} min "
        f"({sum(s.expected_runtime_min for s in sets)/60:.1f} hr)",
        "",
        "PRIORITY SUMMARY",
        "-" * 40,
    ]
    for pri in ("critical", "high", "medium", "exploratory"):
        count = sum(1 for s in sets if s.priority == pri)
        if count:
            lines.append(f"  {pri.upper():12s}: {count} run(s)")

    lines += ["", "RUN DETAILS", "-" * 40, ""]
    for i, s in enumerate(sets, 1):
        lines += [
            f"[{i:02d}] {s.run_id}",
            f"     Priority  : {s.priority}",
            f"     Mode      : {s.mode}",
            f"     ETA       : {s.estimated_runtime_str()}",
            f"     Rationale : {s.rationale}",
            f"     Notes     : {s.notes}" if s.notes else "",
            f"     Tags      : {', '.join(s.tags)}",
            "",
        ]

    lines += [
        "ADDING MISSING CONSTANTS",
        "-" * 40,
        "Several runs reference targets not yet in CONSTANTS dict.",
        "Add these lines to ramanujan_breakthrough_generator.py:",
        "",
        "  In CONSTANTS dict:",
        '    "ln_3_2":  ("1/ln(3/2)",  "1.82047..."),',
        '    "ln_5_4":  ("1/ln(5/4)",  "4.48142..."),',
        '    "pi_fam1": ("2^3/(π·C(2,1))", "1.27324..."),',
        "",
        "  In PCFEngine._get_constant():",
        '    "ln_3_2":  mpmath.mpf(1) / mpmath.log(mpmath.mpf(3)/2),',
        '    "ln_5_4":  mpmath.mpf(1) / mpmath.log(mpmath.mpf(5)/4),',
        '    "pi_fam1": mpmath.mpf(8) / (mpmath.pi * 2),  # 2^3/(π·C(2,1))',
        "",
    ]

    path.write_text("\n".join(l for l in lines if l is not None), encoding='utf-8')
    return path


def print_summary(sets: list, goal: str):
    """Print a compact table to stdout."""
    total_min = sum(s.expected_runtime_min for s in sets)
    print(f"\n  Goal: {goal}  |  {len(sets)} runs  |  ~{total_min:.0f} min total\n")
    print(f"  {'#':>3}  {'PRIORITY':<12} {'RUN ID':<35} {'MODE':<20} {'ETA'}")
    print(f"  {'─'*3}  {'─'*12} {'─'*35} {'─'*20} {'─'*8}")
    for i, s in enumerate(sets, 1):
        pri_marker = {"critical": "★★", "high": "★ ", "medium": "  ", "exploratory": "· "}.get(s.priority, "  ")
        print(f"  {i:>3}  {pri_marker}{s.priority:<10} {s.run_id:<35} {s.mode:<20} {s.estimated_runtime_str()}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
# ═══════════════════════════════════════════════════════════════════════════════

def interactive_menu(args):
    print("\n  ╔══════════════════════════════════════════════════════╗")
    print("  ║       RAMANUJAN PARAMETER SET GENERATOR              ║")
    print("  ╚══════════════════════════════════════════════════════╝\n")
    print("  Available goals:\n")
    for key, (_, desc) in GOAL_REGISTRY.items():
        print(f"    {key:<12}  {desc}")
    print()

    goal = input("  Goal [all]: ").strip() or "all"
    if goal not in GOAL_REGISTRY:
        print(f"  Unknown goal '{goal}'. Valid: {', '.join(GOAL_REGISTRY)}")
        sys.exit(1)

    fmt_default = "bat" if platform.system() == "Windows" else "sh"
    fmt = input(f"  Shell format [sh/bat, default {fmt_default}]: ").strip() or fmt_default
    dry = input("  Dry run? (preview only, no files) [y/N]: ").strip().lower() == "y"

    args.goal = goal
    args.format = fmt
    args.dry_run = dry
    return args


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        description="Generate parameter sets for ramanujan_breakthrough_generator.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--goal", choices=list(GOAL_REGISTRY.keys()),
                   help="Research goal to generate parameter sets for")
    p.add_argument("--out-dir", default="./rbg_runs",
                   help="Output directory for generated files (default: ./rbg_runs)")
    p.add_argument("--generator",
                   default="ramanujan_breakthrough_generator.py",
                   help="Path to the generator script")
    p.add_argument("--format", choices=["sh", "bat"],
                   help="Shell script format (default: auto-detect OS)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print commands without writing files")
    p.add_argument("--json-only", action="store_true",
                   help="Only write JSON manifest, skip shell script and README")
    p.add_argument("--list-goals", action="store_true",
                   help="List all available goals and exit")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_goals:
        print("\n  Available goals:\n")
        for key, (_, desc) in GOAL_REGISTRY.items():
            print(f"    {key:<12}  {desc}")
        print()
        return

    # Interactive if no goal supplied
    if not args.goal:
        args = interactive_menu(args)

    # Shell format default
    if not args.format:
        args.format = "bat" if platform.system() == "Windows" else "sh"

    goal = args.goal
    goal_fn, goal_desc = GOAL_REGISTRY[goal]
    sets = sorted_sets(goal_fn())
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print_summary(sets, goal)

    if args.dry_run:
        print("  ── DRY RUN: commands ──\n")
        for s in sets:
            print(f"  # [{s.priority}] {s.run_id}")
            print(f"  {s.to_cli(args.generator, args.out_dir)}\n")
        return

    # Create output directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest
    manifest_path = write_manifest(sets, goal, out_dir, ts)
    print(f"  ✓ Manifest  → {manifest_path}")

    if not args.json_only:
        # Write shell script
        script_path = write_shell_script(
            sets, goal, out_dir, ts, args.generator, args.format)
        print(f"  ✓ Script    → {script_path}")

        # Write README
        readme_path = write_readme(sets, goal, out_dir, ts)
        print(f"  ✓ README    → {readme_path}")

    total = sum(s.expected_runtime_min for s in sets)
    print(f"\n  {len(sets)} parameter sets  |  ~{total:.0f} min total  |  goal: {goal}")
    if not args.json_only:
        print(f"\n  To run:  bash {script_path}" if args.format == "sh"
              else f"\n  To run:  {script_path}")
    print()


if __name__ == "__main__":
    main()
