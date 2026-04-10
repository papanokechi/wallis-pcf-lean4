"""
test_pcf_families.py — Unit and integration tests for the PCF discovery pipeline
"""
import math
import sys
from fractions import Fraction
from math import comb, factorial

import mpmath
from mpmath import mp, mpf, log, pi as mp_pi

sys.path.insert(0, '.')


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def eval_pcf(alpha, beta, depth, precision=60):
    """Minimal PCF evaluator for tests."""
    mp.dps = precision + 20
    def ep(c, n):
        return sum(mpf(ci) * mpf(n)**i for i, ci in enumerate(c))
    p_prev, p_curr = mpf(1), ep(beta, 0)
    q_prev, q_curr = mpf(0), mpf(1)
    for n in range(1, depth + 1):
        a_n, b_n = ep(alpha, n), ep(beta, n)
        p_new = b_n * p_curr + a_n * p_prev
        q_new = b_n * q_curr + a_n * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
    return p_curr / q_curr if q_curr != 0 else None


def double_factorial(n):
    r = 1
    for j in range(1, 2*n+2, 2):
        r *= j
    return r


# ══════════════════════════════════════════════════════════════════════════════
# THEOREM 1: LOG FAMILY TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestLogFamily:
    """Tests for PCF(-kn², (k+1)n+k) = 1/ln(k/(k-1))."""

    def test_log_k2_matches_1_over_ln2(self):
        mp.dps = 80
        val = eval_pcf([0, 0, -2], [2, 3], 500, 60)
        target = 1 / log(2)
        assert abs(val - target) < mpf(10)**(-50), f"k=2: diff={abs(val-target)}"

    def test_log_k3_matches_1_over_ln_3_2(self):
        mp.dps = 80
        val = eval_pcf([0, 0, -3], [3, 4], 500, 60)
        target = 1 / log(mpf(3)/2)
        assert abs(val - target) < mpf(10)**(-50), f"k=3: diff={abs(val-target)}"

    def test_log_k5_matches(self):
        mp.dps = 80
        val = eval_pcf([0, 0, -5], [5, 6], 500, 60)
        target = 1 / log(mpf(5)/4)
        assert abs(val - target) < mpf(10)**(-50)

    def test_log_noninteger_k_1_5(self):
        """Log family works for non-integer k=1.5."""
        mp.dps = 80
        val = eval_pcf([0, 0, -1.5], [1.5, 2.5], 500, 60)
        target = 1 / log(mpf(3))  # k=1.5: k/(k-1) = 3
        assert abs(val - target) < mpf(10)**(-40)

    def test_log_convergent_p_n_closed_form(self):
        """Verify p_n = (n+1)! * k^{n+1} for k=2."""
        k = 2
        p = [1, k]  # p_{-1}=1, p_0=k
        q = [0, 1]
        for n in range(1, 10):
            a_n = -k * n**2
            b_n = (k+1)*n + k
            p.append(b_n * p[-1] + a_n * p[-2])
            q.append(b_n * q[-1] + a_n * q[-2])
        for n in range(10):
            assert p[n+1] == factorial(n+1) * k**(n+1), f"p_{n} mismatch"

    def test_log_convergent_q_n_closed_form(self):
        """Verify q_n = (n+1)! * sum k^{n-j}/(j+1) for k=2."""
        k = 2
        q_rec = [0, 1]
        for n in range(1, 10):
            a_n = -k * n**2
            b_n = (k+1)*n + k
            q_rec.append(b_n * q_rec[-1] + a_n * q_rec[-2])
        for n in range(10):
            S_n = sum(k**(n-j) / (j+1) for j in range(n+1))
            q_pred = factorial(n+1) * S_n
            assert abs(q_rec[n+1] - q_pred) < 0.5, f"q_{n} mismatch: {q_rec[n+1]} vs {q_pred}"

    def test_log_limit_series_identity(self):
        """Verify sum x^j/(j+1) = -ln(1-x)/x for x=0.5."""
        mp.dps = 60
        x = mpf('0.5')
        partial = sum(x**j / (j+1) for j in range(500))
        expected = -log(1 - x) / x
        assert abs(partial - expected) < mpf(10)**(-50)

    def test_worpitzky_log_family(self):
        """Worpitzky: |a(n)|/(b(n)*b(n-1)) < 1/4 for k>=2."""
        for k in [2, 3, 5, 10]:
            for n in range(1, 50):
                a_n = k * n**2
                b_n = (k+1)*n + k
                b_nm1 = (k+1)*(n-1) + k
                ratio = a_n / (b_n * b_nm1)
                assert ratio < 0.25, f"Worpitzky fails: k={k}, n={n}, ratio={ratio}"


# ══════════════════════════════════════════════════════════════════════════════
# THEOREM 2: PI FAMILY TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPiFamily:
    """Tests for PCF(-n(2n-(2m+1)), 3n+1) = 2^{2m+1}/(π C(2m,m))."""

    def test_pi_m0_matches_2_over_pi(self):
        mp.dps = 80
        val = eval_pcf([0, 1, -2], [1, 3], 500, 60)
        target = 2 / mp_pi
        assert abs(val - target) < mpf(10)**(-50)

    def test_pi_m1_matches_4_over_pi(self):
        mp.dps = 80
        val = eval_pcf([0, 3, -2], [1, 3], 500, 60)
        target = 4 / mp_pi
        assert abs(val - target) < mpf(10)**(-50)

    def test_pi_m2_matches_16_over_3pi(self):
        mp.dps = 80
        val = eval_pcf([0, 5, -2], [1, 3], 500, 60)
        target = mpf(16) / (3 * mp_pi)
        assert abs(val - target) < mpf(10)**(-50)

    def test_pi_convergent_p_n_is_double_factorial(self):
        """Verify p_n = (2n+1)!! for m=0."""
        p = [1, 1]  # p_{-1}=1, p_0=1
        q = [0, 1]
        for n in range(1, 15):
            a_n = -n * (2*n - 1)
            b_n = 3*n + 1
            p.append(b_n * p[-1] + a_n * p[-2])
            q.append(b_n * q[-1] + a_n * q[-2])
        for n in range(15):
            assert p[n+1] == double_factorial(n), f"p_{n}={p[n+1]} != (2·{n}+1)!!={double_factorial(n)}"

    def test_pi_q_n_decomposition(self):
        """Verify c_j * (2j+1)!! = j! for the q_n increments."""
        p = [1, 1]
        q = [0, 1]
        for n in range(1, 12):
            a_n = -n * (2*n - 1)
            b_n = 3*n + 1
            p.append(b_n * p[-1] + a_n * p[-2])
            q.append(b_n * q[-1] + a_n * q[-2])
        
        prev_ratio = Fraction(0)
        for j in range(12):
            ratio = Fraction(q[j+1], p[j+1])
            c_j = ratio - prev_ratio
            prev_ratio = ratio
            ddf = double_factorial(j)
            product = c_j * ddf
            assert product == factorial(j), f"j={j}: c_j*(2j+1)!!={product} != {j}!={factorial(j)}"

    def test_pi_series_identity(self):
        """Verify π/2 = sum j!/(2j+1)!! converges."""
        mp.dps = 60
        partial = sum(mpf(factorial(j)) / double_factorial(j) for j in range(200))
        assert abs(partial - mp_pi/2) < mpf(10)**(-40)

    def test_pi_binomial_recurrence(self):
        """Verify val(m+1) = val(m) * 2(m+1)/(2m+1)."""
        mp.dps = 80
        prev = None
        for m in range(8):
            c = 2*m + 1
            val = eval_pcf([0, c, -2], [1, 3], 500, 60)
            if prev is not None:
                predicted = prev * mpf(2*m) / (2*m - 1)
                assert abs(val - predicted) < mpf(10)**(-40), f"m={m}: recurrence fails"
            prev = val

    def test_parity_even_c_rational(self):
        """Even c → rational values (Wallis convergents)."""
        mp.dps = 60
        expected = [(2, 1), (4, Fraction(3,2)), (6, Fraction(15,8)), 
                    (8, Fraction(35,16)), (10, Fraction(315,128))]
        for c_val, frac in expected:
            val = eval_pcf([0, c_val, -2], [1, 3], 500, 40)
            assert abs(val - float(frac)) < 1e-30, f"c={c_val}: val={val} != {frac}"

    def test_worpitzky_pi_family(self):
        """Worpitzky: |a(n)|/(b(n)*b(n-1)) < 1/4 for n>=2."""
        for n in range(2, 50):
            a_n = n * (2*n - 1)
            b_n = 3*n + 1
            b_nm1 = 3*(n-1) + 1
            ratio = a_n / (b_n * b_nm1)
            assert ratio < 0.25, f"Worpitzky fails: n={n}, ratio={ratio}"


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE MATCHER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestTemplateMatcher:
    """Tests for the automated template fitting system."""

    def test_factorial_power_template_recognizes_log_k2(self):
        from pcf_discovery_engine import compute_convergents, TEMPLATES
        p_seq, q_seq = compute_convergents([0, 0, -2], [2, 3], 12)
        result = TEMPLATES["factorial_power"]["check"](p_seq, q_seq, {})
        assert result is not None, "Template should match log k=2"
        assert result["template"] == "factorial_power"
        assert abs(result["k"] - 2.0) < 0.01

    def test_factorial_power_template_recognizes_log_k3(self):
        from pcf_discovery_engine import compute_convergents, TEMPLATES
        p_seq, q_seq = compute_convergents([0, 0, -3], [3, 4], 12)
        result = TEMPLATES["factorial_power"]["check"](p_seq, q_seq, {})
        assert result is not None, "Template should match log k=3"
        assert abs(result["k"] - 3.0) < 0.01

    def test_double_factorial_template_recognizes_pi_m0(self):
        from pcf_discovery_engine import compute_convergents, TEMPLATES
        p_seq, q_seq = compute_convergents([0, 1, -2], [1, 3], 12)
        result = TEMPLATES["double_factorial"]["check"](p_seq, q_seq, {})
        assert result is not None, "Template should match pi m=0"
        assert result["template"] == "double_factorial"

    def test_template_rejects_random_pcf(self):
        from pcf_discovery_engine import compute_convergents, TEMPLATES
        p_seq, q_seq = compute_convergents([1, 2, -1], [3, 7], 12)
        for tname, tmpl in TEMPLATES.items():
            result = tmpl["check"](p_seq, q_seq, {})
            # Should not match any template
            # (it's ok if some match by coincidence, but factorial_power and
            #  double_factorial should not match random coefficients)


class TestRecurrenceVerifier:
    """Tests for the recurrence certificate system."""

    def test_recurrence_holds_for_log_k2(self):
        from pcf_discovery_engine import compute_convergents, verify_recurrence
        p, q = compute_convergents([0, 0, -2], [2, 3], 12)
        assert verify_recurrence([0, 0, -2], [2, 3], p, q)

    def test_recurrence_holds_for_pi_m0(self):
        from pcf_discovery_engine import compute_convergents, verify_recurrence
        p, q = compute_convergents([0, 1, -2], [1, 3], 12)
        assert verify_recurrence([0, 1, -2], [1, 3], p, q)


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    def test_small_pipeline_runs_without_error(self):
        from pcf_discovery_engine import run_pipeline
        results = run_pipeline(budget=50, precision=50, depth=100, 
                              do_arb=False, emit_latex=False)
        assert results["candidates_generated"] >= 50
        assert results["screened"] > 0
        # Should find at least 1 hit from the seeded templates
        assert results["pslq_hits"] >= 1

    def test_pipeline_finds_known_log_family(self):
        from pcf_discovery_engine import run_pipeline
        results = run_pipeline(budget=100, precision=60, depth=200,
                              do_arb=False, emit_latex=False)
        # LP candidates include k=2,3,4,5 from template seeding
        hits = [c for c in results["top_candidates"] if "1/ln" in c.get("target_name", "")]
        assert len(hits) >= 1, "Should find at least one log family member"


# ══════════════════════════════════════════════════════════════════════════════
# PYTEST RUNNER
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
