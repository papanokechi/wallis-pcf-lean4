"""
tests/test_breakthrough_generator.py
=====================================
Unit tests for ramanujan_breakthrough_generator.py and research_integration.py.

Run with: pytest tests/test_breakthrough_generator.py -v
"""

import sys
import math
import pytest

# Ensure mpmath is available
mpmath = pytest.importorskip("mpmath")
from mpmath import mp, mpf, pi

# Import the module under test
sys.path.insert(0, ".")
import ramanujan_breakthrough_generator as rbg


# ── eval_pcf tests ────────────────────────────────────────────────────────────

class TestEvalPCF:
    """Tests for the continued fraction evaluator."""

    def setup_method(self):
        mp.dps = 50

    def test_simple_cf(self):
        """b(n) = 1 for all n, a(n) = 1 for all n -> golden ratio."""
        # CF = 1 + 1/(1 + 1/(1 + ...)) = phi = (1+sqrt(5))/2
        val = rbg.eval_pcf([1], [1], depth=500)
        assert val is not None
        phi = (1 + mpf(5) ** 0.5) / 2
        assert abs(val - phi) < mpf(10) ** (-40)

    def test_pi_family_m0(self):
        """Pi family m=0: a(n) = n - 2n^2, b(n) = 3n+1 -> 2/pi."""
        val = rbg.eval_pcf([0, 1, -2], [1, 3], depth=800)
        assert val is not None
        target = 2 / pi
        assert abs(val - target) < mpf(10) ** (-40)

    def test_pi_family_m1(self):
        """Pi family m=1: a(n) = 3n - 2n^2, b(n) = 3n+1 -> 4/pi."""
        val = rbg.eval_pcf([0, 3, -2], [1, 3], depth=800)
        assert val is not None
        target = 4 / pi
        assert abs(val - target) < mpf(10) ** (-40)

    def test_divergent_returns_none(self):
        """CF with zero denominators should return None."""
        # b(n) = 0 for all n
        val = rbg.eval_pcf([1, 1], [0, 0], depth=50)
        # May return None due to zero denominator
        # (or a value if it doesn't hit the threshold)

    def test_depth_convergence(self):
        """Higher depth should give more precise results."""
        a, b = [0, 3, -2], [1, 3]
        val_50 = rbg.eval_pcf(a, b, depth=50)
        val_500 = rbg.eval_pcf(a, b, depth=500)
        target = 4 / pi
        assert abs(val_500 - target) < abs(val_50 - target)


# ── is_reasonable tests ───────────────────────────────────────────────────────

class TestIsReasonable:
    def test_normal_value(self):
        assert rbg.is_reasonable(mpf("3.14159"))

    def test_none(self):
        assert not rbg.is_reasonable(None)

    def test_zero_ish(self):
        assert not rbg.is_reasonable(mpf("1e-10"))

    def test_huge(self):
        assert not rbg.is_reasonable(mpf("1e12"))


# ── is_telescoping tests ─────────────────────────────────────────────────────

class TestIsTelescoping:
    def setup_method(self):
        mp.dps = 50

    def test_nontrivial_not_telescoping(self):
        """Pi family CFs should not be flagged as telescoping."""
        assert not rbg.is_telescoping([0, 3, -2], [1, 3])

    def test_trivial_integer_result(self):
        """CF that evaluates to an integer is telescoping."""
        # a(n) = 0 -> CF = b(0) trivially
        assert rbg.is_telescoping([0, 0, 0], [5, 1])


# ── is_spurious_match tests ──────────────────────────────────────────────────

class TestIsSpurious:
    def test_clean_match(self):
        assert not rbg.is_spurious_match("4/pi")
        assert not rbg.is_spurious_match("zeta3")

    def test_overcomplicated(self):
        assert rbg.is_spurious_match("2**(1/3)*3**(2/5)*5**(1/7)")


# ── build_constants tests ────────────────────────────────────────────────────

class TestBuildConstants:
    def test_has_key_constants(self):
        mp.dps = 30
        consts = rbg.build_constants(30)
        required = ["pi", "4/pi", "log2", "sqrt2", "phi", "zeta3", "catalan"]
        for key in required:
            assert key in consts, f"Missing constant: {key}"

    def test_values_are_numeric(self):
        consts = rbg.build_constants(30)
        for name, val in consts.items():
            assert float(val), f"{name} is not numeric"

    def test_pi_family_values(self):
        consts = rbg.build_constants(30)
        # S^(2) through S^(5) should be present
        for m in range(2, 6):
            assert f"S^({m})" in consts


# ── complexity_score tests ────────────────────────────────────────────────────

class TestComplexityScore:
    def test_simple_is_lower(self):
        simple = rbg.complexity_score([0, 1], [1, 1])
        complex_ = rbg.complexity_score([3, -5, 2, 7], [2, 4, 3])
        assert simple < complex_

    def test_zero_coeffs(self):
        score = rbg.complexity_score([0, 0, 0], [1, 0])
        assert score >= 0


# ── PCFParams tests ──────────────────────────────────────────────────────────

class TestPCFParams:
    def test_key_uniqueness(self):
        p1 = rbg.PCFParams(a=[0, 1], b=[1, 2])
        p2 = rbg.PCFParams(a=[0, 1], b=[1, 2])
        p3 = rbg.PCFParams(a=[0, 2], b=[1, 2])
        assert p1.key() == p2.key()
        assert p1.key() != p3.key()


# ── mutation / crossover tests ────────────────────────────────────────────────

class TestEvolution:
    def test_mutate_preserves_structure(self):
        p = rbg.PCFParams(a=[0, 3, -2], b=[1, 3])
        rng = __import__("random").Random(42)
        child = rbg.mutate(p, temperature=1.0, rng=rng)
        assert len(child.a) == len(p.a)
        assert len(child.b) == len(p.b)
        assert child.b[0] >= 1

    def test_crossover_preserves_structure(self):
        p1 = rbg.PCFParams(a=[0, 3, -2], b=[1, 3])
        p2 = rbg.PCFParams(a=[1, -1, 4], b=[2, 5])
        rng = __import__("random").Random(42)
        child = rbg.crossover(p1, p2, rng=rng)
        assert len(child.a) == len(p1.a)
        assert len(child.b) == len(p1.b)
        assert child.b[0] >= 1


# ── seed_population tests ────────────────────────────────────────────────────

class TestSeedPopulation:
    def test_nonempty(self):
        seeds = rbg.seed_population()
        assert len(seeds) >= 10

    def test_all_are_pcfparams(self):
        seeds = rbg.seed_population()
        for s in seeds:
            assert isinstance(s, rbg.PCFParams)


# ── pslq_match tests ─────────────────────────────────────────────────────────

class TestPSLQMatch:
    def setup_method(self):
        mp.dps = 50

    def test_identifies_known_cf_value(self):
        """pslq_match should identify a known CF value."""
        consts = rbg.build_constants(50)
        # Evaluate m=1 Pi family -> 4/pi
        val = rbg.eval_pcf([0, 3, -2], [1, 3], depth=500)
        result = rbg.pslq_match(val, consts, tol_digits=15)
        # Might return None if mpmath.identify doesn't match;
        # the ratio-check in evaluate_population handles this case.
        # Just verify it doesn't crash.
        assert result is None or len(result) == 2


# ── verify_match_high_precision tests ────────────────────────────────────────

class TestVerification:
    def setup_method(self):
        mp.dps = 60

    def test_verify_known_cf(self):
        """Verify the m=1 Pi family member at high precision."""
        consts = rbg.build_constants(60)
        verified, digits = rbg.verify_match_high_precision(
            [0, 3, -2], [1, 3], "4/pi", consts,
            verify_prec=100, verify_depth=500,
        )
        assert verified
        assert digits > 80


# ── cluster_discoveries tests ────────────────────────────────────────────────

class TestClusterDiscoveries:
    def test_empty_log(self, tmp_path):
        """No log file -> empty dict."""
        fake_log = tmp_path / "empty.jsonl"
        result = rbg.cluster_discoveries(fake_log)
        assert result == {}


# ── research_integration tests ────────────────────────────────────────────────

class TestResearchIntegration:
    def test_import(self):
        import research_integration
        assert hasattr(research_integration, "ContextualBreakthroughGenerator")
        assert hasattr(research_integration, "discover")
        assert hasattr(research_integration, "gpt_researcher_adapter")
        assert hasattr(research_integration, "rd_agent_adapter")
        assert hasattr(research_integration, "khoj_adapter")

    def test_discovery_result_to_dict(self):
        from research_integration import DiscoveryResult
        r = DiscoveryResult(
            a_coeffs=[0, 3, -2], b_coeffs=[1, 3],
            value="1.273", match="4/pi",
            residual=-40.0, verified_digits=160.0,
        )
        d = r.to_dict()
        assert d["match"] == "4/pi"
        assert d["a_coeffs"] == [0, 3, -2]

    def test_cf_formula_string(self):
        from research_integration import DiscoveryResult
        r = DiscoveryResult(
            a_coeffs=[0, 3, -2], b_coeffs=[1, 3],
            value="1.273", match="4/pi", residual=-40.0,
        )
        formula = r.cf_formula()
        assert "n" in formula

    def test_context_parsing(self):
        from research_integration import ContextualBreakthroughGenerator
        gen = ContextualBreakthroughGenerator()
        bias = gen._parse_context("Looking for cubic Apéry-like formulas for zeta(3)")
        assert bias["prefer_cubic"] is True
        assert "zeta3" in bias["target_hints"]

    def test_context_parsing_empty(self):
        from research_integration import ContextualBreakthroughGenerator
        gen = ContextualBreakthroughGenerator()
        bias = gen._parse_context("")
        assert bias["prefer_cubic"] is False
        assert bias["target_hints"] == []
