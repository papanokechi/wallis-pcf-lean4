from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ramanujan_agent.relay_chain import (
    build_semantic_prompts,
    execute_relay_chain,
    fit_polynomial_from_sequence,
    parse_results_html,
)


def test_fit_polynomial_from_sequence() -> None:
    seq = [6, 20, 42, 72]
    fitted = fit_polynomial_from_sequence(seq)
    assert fitted["degree"] == 2
    assert fitted["coefficients"] == [4, 2, 0]
    assert fitted["formula"] == "4*n^2 + 2*n"


def test_execute_relay_chain_creates_seed_pool() -> None:
    discoveries = [
        {
            "id": "d1",
            "family": "continued_fraction",
            "status": "novel_proven",
            "confidence": 0.95,
            "target": "pi",
            "params": {"an": [3], "bn": [5, 5]},
            "metadata": {"proof_result": {"closed_form": {"type": "bessel_ratio"}}},
        },
        {
            "id": "d2",
            "family": "continued_fraction",
            "status": "novel_proven",
            "confidence": 0.92,
            "target": "zeta3",
            "params": {"an": [4], "bn": [6, 2]},
            "metadata": {"proof_result": {"closed_form": {"type": "bessel_ratio"}}},
        },
    ]

    with tempfile.TemporaryDirectory() as tmp:
        summary = execute_relay_chain(discoveries, output_dir=tmp, max_seeds=6)
        assert summary["recognized_count"] == 2
        assert summary["seed_count"] > 0
        assert summary["prompt_count"] > 0

        seed_path = Path(tmp) / "relay_chain_seed_pool.json"
        assert seed_path.exists()
        seeds = json.loads(seed_path.read_text(encoding="utf-8"))
        assert seeds[0]["params"]["_family"] == "continued_fraction"
        assert "bn" in seeds[0]["params"]
        assert any(seed.get("candidate_targets") for seed in seeds)
        assert any(seed.get("source") == "relay_index_transform" for seed in seeds)

        prompt_path = Path(tmp) / "relay_chain_llm_prompts.json"
        assert prompt_path.exists()


def test_build_semantic_prompts_adds_math_neighborhood() -> None:
    encoded_patterns = [
        {
            "id": "d1",
            "target": "pi",
            "shape": "constant_a / linear_b",
            "a_formula": "3",
            "b_formula": "5*n + 5",
            "b_fit": {"degree": 1, "formula": "5*n + 5"},
            "closed_form_type": "bessel_ratio",
            "confidence": 0.95,
        }
    ]

    prompts = build_semantic_prompts(encoded_patterns)
    assert prompts
    assert "pi^2" in prompts[0]["target_neighborhood"]
    assert "ln2" in prompts[0]["target_neighborhood"]
    assert "Apéry" in prompts[0]["prompt"] or "Apery" in prompts[0]["prompt"]
    assert "n->2n" in prompts[0]["index_transform_hints"]
    assert prompts[0]["response_schema"]["required"] == [
        "hypothesis", "transformations", "suggested_targets", "search_space"
    ]
    assert "mp.mp.dps = 150" in prompts[0]["lirec_identify_snippet"]


def test_parse_results_html_extracts_pdf_catalog() -> None:
    html = """
    <html><body>
      <h3>Conjectures for Apéry’s constant</h3>
      <a href="http://example.com/zeta3.pdf">zeta3 pdf</a>
      <h3>Conjectures for Catalan’s constant</h3>
      <a href="/catalan.pdf">catalan pdf</a>
    </body></html>
    """
    catalog = parse_results_html(html, base_url="https://www.ramanujanmachine.com/results/")
    assert len(catalog) == 2
    assert catalog[0]["label"] == "Conjectures for Apéry’s constant"
    assert catalog[0]["pdf_links"][0].endswith("zeta3.pdf")
    assert catalog[1]["pdf_links"][0].endswith("catalan.pdf")


if __name__ == "__main__":
    test_fit_polynomial_from_sequence()
    test_execute_relay_chain_creates_seed_pool()
    test_build_semantic_prompts_adds_math_neighborhood()
    test_parse_results_html_extracts_pdf_catalog()
    print("relay_chain tests passed")
