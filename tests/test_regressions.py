"""Regression tests for ramanujan_breakthrough_generator.py"""
from mpmath import mp, zeta
import ramanujan_breakthrough_generator as rbg


def test_apery_converges():
    """Apéry PCF α=-n^6, β=5+27n+51n²+34n³ → 6/ζ(3) at ≥50 digits."""
    mp.dps = 120
    engine = rbg.PCFEngine(precision=100)
    alpha = [0, 0, 0, 0, 0, 0, -1]   # a_n = -n^6
    beta  = [5, 27, 51, 34]           # b_n = 5 + 27n + 51n^2 + 34n^3
    val, err, conv = engine.evaluate_pcf(alpha, beta, depth=500)
    assert val is not None, "evaluate_pcf returned None"
    diff = abs(val - 6 / mp.zeta(3))
    assert diff < mp.mpf('1e-50'), f"Apéry match only {-int(mp.log10(diff))} digits"


def test_evaluate_pcf_returns_tuple():
    """evaluate_pcf must return (value, error, convergents) 3-tuple."""
    mp.dps = 60
    engine = rbg.PCFEngine(precision=50)
    result = engine.evaluate_pcf([0], [1], depth=10)
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 3, f"Expected 3-tuple, got {len(result)}-tuple"


def test_get_constant_string():
    """_get_constant must resolve 'zeta3' to ζ(3)."""
    mp.dps = 30
    engine = rbg.PCFEngine(precision=20)
    val = engine._get_constant("zeta3")
    assert val is not None, "_get_constant('zeta3') returned None"
    assert abs(val - mp.zeta(3)) < mp.mpf('1e-15')


def test_match_known_constant_apery():
    """match_known_constant should find 6/ζ(3) as '6/1 * zeta3' or similar."""
    mp.dps = 80
    engine = rbg.PCFEngine(precision=60)
    target_val = 6 / mp.zeta(3)
    matched, formula, digits = engine.match_known_constant(target_val, "zeta3", 60)
    assert matched, f"Failed to match 6/ζ(3); formula={formula}, digits={digits}"
    assert digits >= 15, f"Only {digits} digits matched"


def test_mitm_search_accepts_string_target():
    """MITMSearch.run must accept a string target like 'zeta3'."""
    mp.dps = 40
    engine = rbg.PCFEngine(precision=30)
    searcher = rbg.MITMSearch(engine)
    # Very small budget — just verify it doesn't crash
    hits = searcher.run(
        target="zeta3", deg_alpha=1, deg_beta=1,
        coeff_range=2, budget=10, depth=20,
    )
    assert isinstance(hits, list)


def test_descent_repel_accepts_string_target():
    """DescentRepelSearch.run must accept a string target like 'zeta3'."""
    mp.dps = 40
    engine = rbg.PCFEngine(precision=30)
    searcher = rbg.DescentRepelSearch(engine)
    hits = searcher.run(
        target="zeta3", deg_alpha=1, deg_beta=1,
        coeff_range=2, budget=50, depth=20,
    )
    assert isinstance(hits, list)
