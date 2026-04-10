"""
runner.py — Main entry point for the Ramanujan Agent.

Usage:
    python -m ramanujan_agent                  # default (5 rounds)
    python -m ramanujan_agent --rounds 10      # 10 rounds
    python -m ramanujan_agent --fast           # quick 3-round demo
"""

from __future__ import annotations
import argparse
import sys
import time
import platform
from datetime import datetime, timezone
from pathlib import Path

from .orchestrator import Orchestrator
from .relay_chain import run_from_state_file
from .visualization import generate_html_report


def _reproducibility_header(config: dict) -> dict:
    """Build a YAML-style reproducibility metadata block."""
    import mpmath
    import sympy
    return {
        "agent_version": "4.6.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "mpmath_version": mpmath.__version__,
        "sympy_version": sympy.__version__,
        "config": config,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ramanujan Agent — Self-iterating mathematical discovery"
    )
    parser.add_argument("--rounds", type=int, default=5,
                        help="Number of discovery rounds (default: 5)")
    parser.add_argument("--budget", type=int, default=15,
                        help="Budget per agent per strategy (default: 15)")
    parser.add_argument("--fast", action="store_true",
                        help="Quick demo mode (3 rounds, budget=8)")
    parser.add_argument("--no-html", action="store_true",
                        help="Skip HTML report generation")
    parser.add_argument("--output", type=str, default="",
                        help="Custom HTML output path")
    parser.add_argument("--relay-only", action="store_true",
                        help="Run the relay-chain analysis on saved results and exit")
    parser.add_argument("--state", type=str, default="results/ramanujan_state.json",
                        help="State/results JSON used for relay-only mode")
    parser.add_argument("--seed-count", type=int, default=10,
                        help="Maximum number of relay-chain seed suggestions to emit")
    parser.add_argument("--prompt-limit", type=int, default=12,
                        help="Maximum number of relay-chain LLM prompts to emit")
    parser.add_argument("--lirec-input", type=str, default="",
                        help="Optional LIReC/JSON/CSV export to merge into relay-only mode")
    parser.add_argument("--scrape-results", action="store_true",
                        help="Scrape the Ramanujan Machine public results page during relay-only mode")
    parser.add_argument("--results-url", type=str,
                        default="https://www.ramanujanmachine.com/results/",
                        help="Results-page URL used with --scrape-results")
    args = parser.parse_args()

    if args.fast:
        args.rounds = 3
        args.budget = 8

    if args.relay_only:
        summary = run_from_state_file(
            args.state,
            output_dir="results",
            max_seeds=args.seed_count,
            lirec_input=args.lirec_input or None,
            scrape_results=args.scrape_results,
            results_url=args.results_url,
            prompt_limit=args.prompt_limit,
        )
        print()
        print("  Relay chain summary")
        print(f"     Recognized patterns: {summary.get('recognized_count', 0)}")
        print(f"     Templates induced:   {summary.get('template_count', 0)}")
        print(f"     LLM prompts:         {summary.get('prompt_count', 0)}")
        print(f"     Seed suggestions:    {summary.get('seed_count', 0)}")
        print(f"     Seed pool path:      {summary.get('seed_pool_path', '')}")
        if summary.get('results_catalog_path'):
            print(f"     Results catalog:     {summary.get('results_catalog_path', '')}")
        print()
        return summary

    config = {
        "max_rounds": args.rounds,
        "budget_per_agent": args.budget,
        "pollinate_every": max(1, args.rounds // 3),
        "meta_learn_every": max(1, args.rounds // 3),
        "persist_path": "results/ramanujan_state.json",
    }

    repro = _reproducibility_header(config)
    print()
    print("  Ramanujan Agent v4.6 (Bessel K Ratio · Proof Pipeline 2× · Linear-b Priority Boost)")
    print(f"     Rounds: {config['max_rounds']} | "
          f"Budget: {config['budget_per_agent']} | "
          f"Pollinate every: {config['pollinate_every']} | "
          f"Meta-learn every: {config['meta_learn_every']}")
    print(f"     Timestamp: {repro['timestamp_utc']}")
    print(f"     Python {repro['python_version']} | "
          f"mpmath {repro['mpmath_version']} | "
          f"sympy {repro['sympy_version']}")
    print()

    # Run discovery
    orchestrator = Orchestrator(config)
    results = orchestrator.run()
    results["reproducibility"] = repro

    # Save reproducibility bundle alongside results
    import json
    repro_path = Path("results/reproducibility.json")
    repro_path.parent.mkdir(parents=True, exist_ok=True)
    repro_bundle = {
        **repro,
        "literature_db_size": len(__import__('ramanujan_agent.blackboard', fromlist=['KNOWN_RESULTS']).KNOWN_RESULTS),
        "search_families": ["pi_series", "continued_fraction", "nonpoly_cf", "q_series", "pslq", "partition", "tau_function"],
        "validation_stages": ["numeric_escalation", "symbolic", "pslq_verify", "convergence", "cf_fixedpoint", "algebraic_detection"],
        "novelty_criteria": {
            "numeric_uniqueness": "ISC-style lookup: 15 constants x 40 multipliers + algebraic transforms",
            "structural_novelty": "polynomial degree, coefficient magnitude, period length",
            "algebraic_filter": "minimal polynomial degree <= 8 with small coefficients",
            "literature_match": f"{len(__import__('ramanujan_agent.blackboard', fromlist=['KNOWN_RESULTS']).KNOWN_RESULTS)} known results + periodic CF detection",
        },
    }
    repro_path.write_text(
        json.dumps(repro_bundle, indent=2, default=str), encoding="utf-8"
    )

    # Save proof targets if available
    if results.get("proof_targets"):
        targets_path = Path("results/proof_targets.json")
        targets_path.write_text(
            json.dumps(results["proof_targets"], indent=2, default=str), encoding="utf-8"
        )
        print(f"  Proof targets saved to {targets_path}")

    # Generate HTML report
    if not args.no_html:
        output = args.output or "ramanujan-discovery-report.html"
        print(f"\n  Generating HTML report -> {output}")
        generate_html_report(results, output_path=output)
        print(f"  Report saved to {output}")

    return results


if __name__ == "__main__":
    main()
