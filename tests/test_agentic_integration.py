"""
tests/test_agentic_integration.py
==================================
End-to-end integration test simulating an LLM agent invoking the
Ramanujan Breakthrough Generator via the TOOL_SCHEMA interface.

This tests the full loop:
  1. Agent receives a user query about a mathematical constant.
  2. Agent parses intent and constructs a tool_call with arguments.
  3. tool_call_handler() runs the discovery engine.
  4. Agent interprets the structured results.

Run with: pytest tests/test_agentic_integration.py -v
"""

import sys
import json
import pytest

mpmath = pytest.importorskip("mpmath")

sys.path.insert(0, ".")
from research_integration import (
    TOOL_SCHEMA,
    tool_call_handler,
    discover,
    ContextualBreakthroughGenerator,
    DiscoveryResult,
)


# ── TOOL_SCHEMA validation ───────────────────────────────────────────────────

class TestToolSchema:
    """Verify the TOOL_SCHEMA is well-formed for LLM function-calling."""

    def test_schema_has_required_keys(self):
        assert "name" in TOOL_SCHEMA
        assert "description" in TOOL_SCHEMA
        assert "parameters" in TOOL_SCHEMA

    def test_schema_name(self):
        assert TOOL_SCHEMA["name"] == "ramanujan_discover"

    def test_parameters_is_object(self):
        params = TOOL_SCHEMA["parameters"]
        assert params["type"] == "object"
        assert "properties" in params

    def test_query_is_required(self):
        assert "query" in TOOL_SCHEMA["parameters"]["required"]

    def test_target_has_enum(self):
        target = TOOL_SCHEMA["parameters"]["properties"]["target"]
        assert "enum" in target
        assert "pi" in target["enum"]
        assert "zeta3" in target["enum"]

    def test_style_has_enum(self):
        style = TOOL_SCHEMA["parameters"]["properties"]["style"]
        assert "enum" in style
        assert "ramanujan" in style["enum"]
        assert "apery" in style["enum"]

    def test_schema_serializable(self):
        """Schema must be JSON-serializable for OpenAI/Anthropic API."""
        serialized = json.dumps(TOOL_SCHEMA)
        roundtrip = json.loads(serialized)
        assert roundtrip["name"] == TOOL_SCHEMA["name"]


# ── Simulated agent intent parsing ────────────────────────────────────────────

def simulate_agent_intent(user_query: str) -> dict:
    """Simulate an LLM agent parsing a user query into tool_call arguments.

    This is a rule-based mock of what an LLM would do in practice.
    In production, the LLM generates these arguments via function-calling.
    """
    query_lower = user_query.lower()
    args = {"query": user_query}

    # Target detection
    target_map = {
        "pi": "pi", "zeta(3)": "zeta3", "zeta3": "zeta3",
        "catalan": "catalan", "log 2": "log2", "log(2)": "log2",
        "euler": "euler_g", "golden": "phi", "sqrt(2)": "sqrt2",
    }
    for keyword, target in target_map.items():
        if keyword in query_lower:
            args["target"] = target
            break

    # Style detection
    if any(w in query_lower for w in ["apery", "apéry", "cubic"]):
        args["style"] = "apery"
    elif any(w in query_lower for w in ["brouncker", "wallis", "quadratic"]):
        args["style"] = "brouncker"
    elif any(w in query_lower for w in ["wild", "random", "exploratory"]):
        args["style"] = "wild"

    # Keep small for tests
    args["num_formulas"] = 3

    return args


class TestAgentIntentParsing:
    """Test that simulated agent correctly maps queries to tool args."""

    def test_zeta3_query(self):
        args = simulate_agent_intent(
            "Find a new continued fraction representation for zeta(3)"
        )
        assert args["target"] == "zeta3"
        assert "zeta(3)" in args["query"]

    def test_pi_apery_query(self):
        args = simulate_agent_intent(
            "Search for Apéry-style cubic numerator CFs converging to pi"
        )
        assert args["target"] == "pi"
        assert args["style"] == "apery"

    def test_catalan_query(self):
        args = simulate_agent_intent(
            "Discover new formulas for Catalan's constant"
        )
        assert args["target"] == "catalan"

    def test_open_ended_query(self):
        args = simulate_agent_intent(
            "Find interesting continued fraction identities"
        )
        assert "target" not in args  # No specific target


# ── Full agentic loop ────────────────────────────────────────────────────────

class TestAgenticLoop:
    """End-to-end: user query -> agent -> tool_call -> results -> interpretation."""

    def test_pi_discovery_loop(self):
        """Agent asks for pi formulas and gets structured results."""
        # Step 1: Agent parses user intent
        user_query = "Find new continued fraction representations of pi"
        args = simulate_agent_intent(user_query)
        assert args["target"] == "pi"

        # Step 2: Agent calls the tool
        result = tool_call_handler(args)

        # Step 3: Validate response structure
        assert "discoveries" in result
        assert "count" in result
        assert "summary" in result
        assert isinstance(result["discoveries"], list)
        assert isinstance(result["count"], int)

        # Step 4: Agent interprets results
        summary = result["summary"]
        assert "pi" in summary.lower() or "continued fraction" in summary.lower()

    def test_zeta3_apery_loop(self):
        """Agent searches for Apery-style zeta(3) formulas."""
        args = simulate_agent_intent(
            "Search for Apéry-like cubic continued fractions for zeta(3)"
        )
        result = tool_call_handler(args)

        assert "discoveries" in result
        assert result["count"] >= 0  # May find 0 in brief run

        # Each discovery has the expected keys
        for d in result["discoveries"]:
            assert "a_coeffs" in d
            assert "b_coeffs" in d
            assert "match" in d
            assert "value" in d
            assert "verified_digits" in d

    def test_open_ended_loop(self):
        """Agent runs without a specific target."""
        args = {"query": "Explore novel continued fraction identities", "num_formulas": 2}
        result = tool_call_handler(args)
        assert "discoveries" in result

    def test_tool_call_with_all_params(self):
        """Agent provides all optional parameters."""
        args = {
            "query": "Quadratic PCFs for Catalan's constant",
            "target": "catalan",
            "num_formulas": 2,
            "style": "brouncker",
        }
        result = tool_call_handler(args)
        assert isinstance(result["discoveries"], list)


# ── Context-driven discovery ──────────────────────────────────────────────────

class TestContextualDiscovery:
    """Test the ContextualBreakthroughGenerator with research-like context."""

    def test_context_biases_search(self):
        """Context about cubic CFs should bias toward higher-degree polynomials."""
        gen = ContextualBreakthroughGenerator(precision=40, seed=42)
        bias = gen._parse_context(
            "Recent work by Zudilin on Apéry-like sequences suggests "
            "cubic numerators a(n) = n^3 + cn may yield new zeta(3) representations."
        )
        assert bias["prefer_cubic"] is True
        assert "zeta3" in bias["target_hints"]

    def test_discover_returns_results(self):
        """discover() with small budget should run without errors."""
        results = discover(
            context="Searching for pi representations",
            target="pi",
            num_formulas=2,
            cycles=5,
            precision=40,
            seed=42,
        )
        assert isinstance(results, list)
        for r in results:
            assert "a_coeffs" in r
            assert "b_coeffs" in r


# ── Result format tests ──────────────────────────────────────────────────────

class TestResultFormat:
    """Verify discovery results conform to the expected schema for downstream agents."""

    def test_discovery_result_json_roundtrip(self):
        r = DiscoveryResult(
            a_coeffs=[0, 3, -2], b_coeffs=[1, 3],
            value="1.2732395447351626862",
            match="4/pi", residual=-49.3,
            verified_digits=160.0, complexity=4.2,
            context_used="test context",
            metadata={"source": "pi_family"},
        )
        d = r.to_dict()
        j = json.dumps(d)
        parsed = json.loads(j)
        assert parsed["match"] == "4/pi"
        assert parsed["a_coeffs"] == [0, 3, -2]
        assert parsed["verified_digits"] == 160.0

    def test_discovery_result_cf_formula(self):
        r = DiscoveryResult(
            a_coeffs=[0, 3, -2], b_coeffs=[1, 3],
            value="1.273", match="4/pi", residual=-40.0,
        )
        formula = r.cf_formula()
        # Should contain polynomial terms
        assert "n" in formula
        assert "a(n)" in formula

    def test_empty_discoveries_valid(self):
        """tool_call_handler with impossible target should still return valid structure."""
        result = tool_call_handler({
            "query": "test",
            "num_formulas": 1,
            "style": "ramanujan",
        })
        assert "discoveries" in result
        assert "count" in result
        assert result["count"] == len(result["discoveries"])


# ── Multi-adapter tests ───────────────────────────────────────────────────────

class TestAdapters:
    """Test that all research agent adapters produce valid output."""

    def test_gpt_researcher_adapter(self):
        from research_integration import gpt_researcher_adapter
        results = gpt_researcher_adapter(
            research_report="Cubic continued fractions for pi: recent advances...",
            target="pi",
            num_formulas=2,
        )
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, dict)
            assert "a_coeffs" in r

    def test_rd_agent_adapter(self):
        from research_integration import rd_agent_adapter
        result = rd_agent_adapter(
            hypothesis="Quadratic PCFs with b(n)=3n+1 produce pi-multiples",
            experiment_config={"target": "pi", "cycles": 5, "precision": 40},
        )
        assert "discoveries" in result
        assert "verified_count" in result
        assert "summary" in result

    def test_khoj_adapter(self):
        from research_integration import khoj_adapter
        results = khoj_adapter(
            knowledge_context="Notes on Ramanujan's nested radicals and CF identities",
            query="pi formulas",
            num_formulas=2,
        )
        assert isinstance(results, list)
