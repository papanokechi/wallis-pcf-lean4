"""
research_integration.py
========================
Modular adapters for integrating the Ramanujan Breakthrough Generator with
popular research agent frameworks (gpt-researcher, Microsoft RD-Agent,
khoj-ai, and custom agents).

Provides:
  - ContextualBreakthroughGenerator: feed research context → get discoveries
  - Agent adapter functions for plug-and-play integration
  - Structured result objects for downstream pipelines

Usage::

    from research_integration import ContextualBreakthroughGenerator

    gen = ContextualBreakthroughGenerator(precision=80, seed=42)
    results = gen.discover(
        context="Cubic continued fractions for zeta(3)",
        target="zeta3",
        num_formulas=5,
        cycles=30,
    )
"""

from __future__ import annotations

import json
import logging
import re
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ramanujan.integration")

# Lazy imports to keep the module lightweight when used as a library
_rbg = None


def _ensure_rbg():
    """Lazy-import ramanujan_breakthrough_generator to avoid circular deps."""
    global _rbg
    if _rbg is None:
        import ramanujan_breakthrough_generator as rbg
        _rbg = rbg
    return _rbg


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class DiscoveryResult:
    """A single verified mathematical discovery."""

    a_coeffs: List[int]
    b_coeffs: List[int]
    value: str
    match: str
    residual: float
    verified_digits: float = 0.0
    complexity: float = 0.0
    context_used: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def cf_formula(self) -> str:
        """Human-readable CF formula string."""
        def _poly(coeffs: List[int], var: str = "n") -> str:
            terms = []
            for i, c in enumerate(coeffs):
                if c == 0:
                    continue
                if i == 0:
                    terms.append(str(c))
                elif i == 1:
                    terms.append(f"{c}*{var}" if c != 1 else var)
                else:
                    terms.append(f"{c}*{var}^{i}" if c != 1 else f"{var}^{i}")
            return " + ".join(terms) if terms else "0"

        return f"a(n) = {_poly(self.a_coeffs)}, b(n) = {_poly(self.b_coeffs)}"


# ── Context-aware generator ──────────────────────────────────────────────────

class ContextualBreakthroughGenerator:
    """High-level interface for context-driven mathematical discovery.

    Accepts optional research context (paper summaries, hypotheses,
    natural-language descriptions) and uses it to bias the search
    toward relevant parameter regions.

    Args:
        precision: mpmath decimal precision (default 80).
        seed: Random seed for reproducibility.
        depth: CF evaluation depth.
        verify_prec: Precision for high-precision verification.
    """

    def __init__(
        self,
        precision: int = 80,
        seed: int = 42,
        depth: int = 500,
        verify_prec: int = 200,
    ):
        self.precision = precision
        self.seed = seed
        self.depth = depth
        self.verify_prec = verify_prec

    def discover(
        self,
        context: str = "",
        target: Optional[str] = None,
        num_formulas: int = 10,
        cycles: int = 30,
        style: str = "ramanujan",
    ) -> List[DiscoveryResult]:
        """Run discovery guided by optional research context.

        Args:
            context: Natural-language description of the research direction,
                     paper summary, or hypothesis to guide the search.
            target: Target constant name (e.g. 'zeta3', 'pi', 'catalan').
            num_formulas: Target number of distinct discoveries.
            cycles: Number of evolutionary cycles.
            style: Discovery style ('ramanujan', 'apery', 'brouncker', 'wild').

        Returns:
            List of DiscoveryResult objects.
        """
        rbg = _ensure_rbg()
        from mpmath import mp

        mp.dps = self.precision + 20
        rng = random.Random(self.seed)
        constants = rbg.build_constants(self.precision)

        # Parse context to bias search
        bias = self._parse_context(context)

        # Filter constants if target specified
        target_consts = self._filter_constants(constants, target)

        # Choose population strategy based on style + context
        population = self._build_initial_population(
            rng, bias, style, pop_size=max(40, num_formulas * 4)
        )

        seen_hits: set = set()
        results: List[DiscoveryResult] = []
        temperature = 2.0

        logger.info(
            "Starting contextual discovery: target=%s, cycles=%d, style=%s",
            target or "all", cycles, style,
        )
        if context:
            logger.info("Context: %s", context[:200])

        for cycle in range(1, cycles + 1):
            # Evaluate population
            population = rbg.evaluate_population(
                population, target_consts, self.depth,
                tol_digits=15, seen_hits=seen_hits,
                verify=True, verify_prec=self.verify_prec,
            )

            # Collect hits
            for p in population:
                if p.hit and len(results) < num_formulas:
                    results.append(DiscoveryResult(
                        a_coeffs=p.a,
                        b_coeffs=p.b,
                        value=str(rbg.eval_pcf(p.a, p.b, depth=self.depth)),
                        match=p.hit,
                        residual=p.score,
                        verified_digits=p.score,
                        complexity=rbg.complexity_score(p.a, p.b),
                        context_used=context[:200] if context else "",
                    ))

            if len(results) >= num_formulas:
                break

            # Evolve
            temperature = rbg.adapt_temperature(
                temperature, [p.score for p in population[:5]], cycle
            )
            population = rbg.evolve_population(
                population, len(population), temperature, rng
            )

        logger.info("Discovery complete: %d results found", len(results))
        return results

    def _parse_context(self, context: str) -> Dict[str, Any]:
        """Extract search biases from natural-language context."""
        bias: Dict[str, Any] = {
            "prefer_cubic": False,
            "prefer_quadratic": False,
            "target_hints": [],
        }
        if not context:
            return bias

        ctx_lower = context.lower()

        # Detect polynomial degree hints
        if any(w in ctx_lower for w in ["cubic", "degree 3", "n^3", "apéry", "apery"]):
            bias["prefer_cubic"] = True
        if any(w in ctx_lower for w in ["quadratic", "degree 2", "n^2", "brouncker"]):
            bias["prefer_quadratic"] = True

        # Detect target constant hints
        constant_hints = {
            "zeta": "zeta3", "apery": "zeta3", "ζ(3)": "zeta3",
            "pi": "pi", "π": "pi",
            "catalan": "catalan", "log": "log2", "euler": "euler_g",
            "golden": "phi", "phi": "phi", "φ": "phi",
        }
        for keyword, const in constant_hints.items():
            if keyword in ctx_lower:
                bias["target_hints"].append(const)

        return bias

    def _filter_constants(
        self,
        constants: Dict[str, Any],
        target: Optional[str],
    ) -> Dict[str, Any]:
        """Filter constant library by target name."""
        if not target:
            return constants

        target_key = target.lower().replace("_", "").replace("-", "")
        filtered = {}
        for name, val in constants.items():
            nk = name.lower().replace("_", "").replace("-", "").replace("^", "")
            nk = nk.replace("/", "").replace("*", "")
            if target_key in nk or nk in target_key:
                filtered[name] = val
        if not filtered:
            # Exact match fallback
            for name, val in constants.items():
                if target.lower() == name.lower():
                    filtered[name] = val
                    break
        return filtered or constants

    def _build_initial_population(
        self,
        rng: random.Random,
        bias: Dict[str, Any],
        style: str,
        pop_size: int,
    ) -> list:
        """Build initial population biased by context and style."""
        rbg = _ensure_rbg()
        population = list(rbg.seed_population())

        while len(population) < pop_size:
            if bias.get("prefer_cubic") or style == "apery":
                p = rbg.random_params(a_deg=3, b_deg=2, coeff_range=4, rng=rng)
            elif bias.get("prefer_quadratic") or style == "brouncker":
                p = rbg.random_params(a_deg=2, b_deg=1, coeff_range=5, rng=rng)
            elif style == "wild":
                a_deg = rng.choice([1, 2, 3, 4])
                b_deg = rng.choice([1, 2, 3])
                p = rbg.random_params(a_deg=a_deg, b_deg=b_deg,
                                      coeff_range=rng.randint(3, 10), rng=rng)
            else:
                p = rbg.random_fertile_params(rng)
            population.append(p)

        return population


# ── Research agent adapters ───────────────────────────────────────────────────

def gpt_researcher_adapter(
    research_report: str,
    target: Optional[str] = None,
    num_formulas: int = 5,
) -> List[Dict[str, Any]]:
    """Adapter for `gpt-researcher <https://github.com/assafelovic/gpt-researcher>`_.

    Takes a research report (HTML/markdown text from gpt-researcher) and
    feeds it as context into the breakthrough generator.

    Args:
        research_report: Full text of the research report.
        target: Optional target constant.
        num_formulas: Number of formulas to generate.

    Returns:
        List of discovery dicts.

    Example::

        from gpt_researcher import GPTResearcher
        researcher = GPTResearcher(query="continued fractions for pi", report_type="research_report")
        report = await researcher.conduct_research()
        from research_integration import gpt_researcher_adapter
        discoveries = gpt_researcher_adapter(report, target="pi", num_formulas=5)
    """
    gen = ContextualBreakthroughGenerator(precision=60, seed=42)
    results = gen.discover(
        context=research_report[:2000],
        target=target,
        num_formulas=num_formulas,
        cycles=30,
    )
    return [r.to_dict() for r in results]


def rd_agent_adapter(
    hypothesis: str,
    experiment_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Adapter for `Microsoft RD-Agent <https://github.com/microsoft/RD-Agent>`_.

    Maps the RD-Agent hypothesis → experiment → evaluation loop onto
    the breakthrough generator.

    Args:
        hypothesis: A mathematical hypothesis to test.
        experiment_config: Optional dict with keys like 'target', 'cycles', 'precision'.

    Returns:
        Dict with 'discoveries', 'summary', 'verified_count'.

    Example::

        result = rd_agent_adapter(
            hypothesis="Quadratic PCFs with b(n)=3n+1 produce pi-family identities",
            experiment_config={"target": "pi", "cycles": 50},
        )
    """
    config = experiment_config or {}
    gen = ContextualBreakthroughGenerator(
        precision=config.get("precision", 60),
        seed=config.get("seed", 42),
    )
    results = gen.discover(
        context=hypothesis,
        target=config.get("target"),
        num_formulas=config.get("num_formulas", 10),
        cycles=config.get("cycles", 30),
    )
    verified = [r for r in results if r.verified_digits > 20]
    return {
        "hypothesis": hypothesis,
        "discoveries": [r.to_dict() for r in results],
        "verified_count": len(verified),
        "summary": f"Found {len(results)} candidates, {len(verified)} verified "
                   f"at 20+ digits for hypothesis: {hypothesis[:100]}",
    }


def khoj_adapter(
    knowledge_context: str,
    query: str = "mathematical continued fraction identities",
    num_formulas: int = 5,
) -> List[Dict[str, Any]]:
    """Adapter for `khoj-ai <https://github.com/khoj-ai/khoj>`_.

    Uses personal knowledge base context from Khoj to guide discovery.

    Args:
        knowledge_context: Retrieved context from Khoj knowledge base.
        query: The user's query.
        num_formulas: Number of formulas to generate.

    Returns:
        List of discovery dicts.

    Example::

        # After Khoj retrieves relevant notes about Ramanujan's work:
        from research_integration import khoj_adapter
        context = khoj.search("Ramanujan continued fraction identities")
        results = khoj_adapter(context, query="new pi formulas", num_formulas=3)
    """
    combined_context = f"Query: {query}\n\nContext: {knowledge_context[:1500]}"
    gen = ContextualBreakthroughGenerator(precision=60, seed=42)
    results = gen.discover(
        context=combined_context,
        num_formulas=num_formulas,
        cycles=20,
    )
    return [r.to_dict() for r in results]


# ── Standalone discovery function (simplest API) ─────────────────────────────

def discover(
    context: str = "",
    target: Optional[str] = None,
    num_formulas: int = 5,
    cycles: int = 30,
    precision: int = 60,
    seed: int = 42,
    style: str = "ramanujan",
) -> List[Dict[str, Any]]:
    """One-call discovery function.

    This is the simplest entry point for programmatic use.

    Args:
        context: Optional research context string.
        target: Target constant name.
        num_formulas: How many discoveries to aim for.
        cycles: Number of search cycles.
        precision: mpmath decimal precision.
        seed: Random seed.
        style: Discovery style.

    Returns:
        List of discovery dicts with keys: a_coeffs, b_coeffs, value,
        match, residual, verified_digits, complexity, context_used.

    Example::

        from research_integration import discover
        results = discover(target="pi", num_formulas=3, cycles=20)
        for r in results:
            print(f"  {r['match']}: a={r['a_coeffs']}, b={r['b_coeffs']}")
    """
    gen = ContextualBreakthroughGenerator(
        precision=precision, seed=seed
    )
    results = gen.discover(
        context=context,
        target=target,
        num_formulas=num_formulas,
        cycles=cycles,
        style=style,
    )
    return [r.to_dict() for r in results]


# ── Tool-calling / function-calling adapter ───────────────────────────────────

# Schema compatible with OpenAI function calling / tool use patterns.
# LLM agents can invoke this as a structured tool.
# Usage with gpt-researcher: tools=[{"type": "function", "function": TOOL_SCHEMA}]
TOOL_SCHEMA = {
    "name": "ramanujan_discover",
    "description": (
        "Search for new polynomial continued fraction identities matching "
        "mathematical constants like pi, zeta(3), log(2), Catalan's constant, etc. "
        "Uses evolutionary search with PSLQ integer relation detection."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language description of the research direction or target.",
            },
            "target": {
                "type": "string",
                "description": "Target constant: pi, zeta3, log2, catalan, phi, euler_g, sqrt2, etc.",
                "enum": [
                    "pi", "zeta3", "log2", "catalan", "phi",
                    "euler_g", "sqrt2", "sqrt3", "e",
                ],
            },
            "num_formulas": {
                "type": "integer",
                "description": "Number of distinct discoveries to find.",
                "default": 5,
            },
            "style": {
                "type": "string",
                "enum": ["ramanujan", "apery", "brouncker", "wild"],
                "default": "ramanujan",
            },
        },
        "required": ["query"],
    },
}


def tool_call_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a tool/function call from an LLM agent.

    This follows the OpenAI function-calling convention: the agent
    provides ``arguments`` as a dict, and this function returns a
    structured result.

    Args:
        arguments: Dict with keys matching TOOL_SCHEMA['parameters'].

    Returns:
        Dict with 'discoveries' list and 'summary' string.

    Example (inside an LLM agent loop)::

        import json
        from research_integration import tool_call_handler, TOOL_SCHEMA

        # Agent decides to call the tool with these arguments:
        args = {"query": "new pi formulas", "target": "pi", "num_formulas": 3}
        result = tool_call_handler(args)
        print(result["summary"])
        for d in result["discoveries"]:
            print(f"  a={d['a_coeffs']}, b={d['b_coeffs']} -> {d['match']}")
    """
    query = arguments.get("query", "")
    target = arguments.get("target")
    num_formulas = arguments.get("num_formulas", 5)
    style = arguments.get("style", "ramanujan")

    results = discover(
        context=query,
        target=target,
        num_formulas=num_formulas,
        style=style,
        cycles=20,
        precision=60,
    )

    return {
        "discoveries": results,
        "count": len(results),
        "summary": (
            f"Found {len(results)} continued fraction identities"
            + (f" for {target}" if target else "")
            + f" (style={style})."
        ),
    }


# ── End-to-end example function ───────────────────────────────────────────────

def run_example(target: str = "pi", num: int = 3) -> None:
    """Demonstrate the full research -> discovery -> verification pipeline.

    This is a self-contained example that can be run directly::

        python -c "from research_integration import run_example; run_example()"

    Args:
        target: Target constant to search for.
        num: Number of formulas to find.
    """
    print("=== Ramanujan Breakthrough Generator — Example Run ===")
    print(f"Target: {target}, searching for {num} formulas...\n")

    results = discover(
        context=f"Searching for continued fraction representations of {target}",
        target=target,
        num_formulas=num,
        cycles=15,
        precision=50,
    )

    if not results:
        print("No discoveries found in this run. Try more cycles or a different target.")
        return

    for i, r in enumerate(results, 1):
        print(f"Discovery {i}:")
        print(f"  a(n) coeffs: {r['a_coeffs']}")
        print(f"  b(n) coeffs: {r['b_coeffs']}")
        print(f"  Matches:     {r['match']}")
        print(f"  Value:       {r['value'][:40]}...")
        print(f"  Complexity:  {r['complexity']:.1f}")
        print()

    print(f"Total: {len(results)} discoveries for target={target}")
