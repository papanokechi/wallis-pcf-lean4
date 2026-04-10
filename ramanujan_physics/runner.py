"""
runner.py - CLI entry point for the Ramanujan-Physics Bridge.
"""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(
        description="Ramanujan-Physics Bridge: Self-iterating discovery engine")
    parser.add_argument("--rounds", type=int, default=5,
                        help="Number of discovery rounds (default: 5)")
    parser.add_argument("--fast", action="store_true",
                        help="Quick 3-round demo")
    parser.add_argument("--precision", type=int, default=100,
                        help="Precision in decimal digits (default: 100)")
    parser.add_argument("--no-html", action="store_true",
                        help="Skip HTML report generation")
    parser.add_argument("--output", type=str, default=None,
                        help="Output HTML file path")
    args = parser.parse_args()

    if args.fast:
        args.rounds = 3
        args.precision = 50

    print("=" * 70)
    print("  RAMANUJAN-PHYSICS BRIDGE")
    print("  Self-Iterating Agent for Reverse-Engineering Ramanujan Formulas")
    print("  Connecting Pi, Black Holes, and High-Energy Physics")
    print("=" * 70)
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Rounds: {args.rounds}")
    print(f"  Precision: {args.precision} digits")
    print()

    from ramanujan_physics.iterator import run_discovery
    report = run_discovery(
        rounds=args.rounds,
        precision=args.precision,
        verbose=True,
    )

    if not args.no_html:
        from ramanujan_physics.visualization import generate_html_report
        output_path = args.output or "ramanujan-physics-bridge.html"
        generate_html_report(report, output_path)
        print(f"\nHTML report: {output_path}")

    # Print summary
    stats = report["statistics"]
    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(f"  Total connections found:  {stats['total_connections']}")
    print(f"  Strong (>=0.8):           {stats['by_strength']['strong']}")
    print(f"  Medium (0.5-0.8):         {stats['by_strength']['medium']}")
    print(f"  Weak (<0.5):              {stats['by_strength']['weak']}")
    print(f"  Domains covered:          {len(stats['by_domain'])}")
    print(f"  Patterns discovered:      {len(report['patterns'])}")
    print(f"  Cross-formula bridges:    {len(report['cross_formula_bridges'])}")
    print(f"  Missing links to explore: {len(report['missing_links'])}")
    print(f"  Proposals generated:      {len(report['proposals'])}")
    print(f"  Grand narrative threads:  {len(report['grand_narrative'])}")
    print(f"  Elapsed:                  {report['meta']['elapsed_seconds']}s")
    print("=" * 70)
