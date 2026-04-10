"""
ARIA — Run as module: python -m aria
"""
from .orchestrator import run_aria

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="ARIA — Autonomous Reasoning & Intuition Architecture"
    )
    parser.add_argument("--iterations", type=int, default=3,
                        help="Number of self-iteration cycles (default: 3)")
    parser.add_argument("--rounds", type=int, default=4,
                        help="Max telescoping verifier rounds 1-4 (default: 4)")
    parser.add_argument("--threshold", type=float, default=0.15,
                        help="Resonance threshold for signature matching")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose output")
    parser.add_argument("--output-dir", type=str, default="results/aria",
                        help="Output directory for reports")

    args = parser.parse_args()

    config = {
        "max_iterations": args.iterations,
        "verifier_max_rounds": args.rounds,
        "resonance_threshold": args.threshold,
        "verbose": not args.quiet,
        "output_dir": args.output_dir,
        "axiom_persist_path": f"{args.output_dir}/axiom_bank.json",
    }

    result = run_aria(config)

    if args.quiet:
        import json
        print(json.dumps(result.get("cumulative", {}), indent=2))
