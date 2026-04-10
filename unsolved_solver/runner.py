"""
Runner — Main Entry Point
===========================
Executes the full self-iterative collaborative AI problem solver.
Produces JSON results + interactive HTML report.
"""

import json
import time
import os
import sys

from unsolved_solver.orchestrator import Orchestrator
from unsolved_solver.sat_bridge import (
    CollatzSATEncoder, ErdosStrausSATEncoder,
    HadamardSATEncoder, FormalVerification
)
from unsolved_solver.visualization import generate_html_report


def main():
    """Run the self-iterative collaborative AI problem solver."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Self-Iterative Collaborative AI Problem Solver  v1.0      ║")
    print("║  ─────────────────────────────────────────────────────────  ║")
    print("║  Targets:                                                  ║")
    print("║    • Collatz Conjecture                                    ║")
    print("║    • Erdős–Straus Conjecture                               ║")
    print("║    • Hadamard Conjecture                                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # ── Phase 0: Pre-computation SAT verification ──
    print("Phase 0: Bounded verification via constraint solving...")
    t0 = time.time()

    collatz_sat = CollatzSATEncoder.batch_verify(2, 10001, max_steps=50000)
    print(f"  Collatz verified [2, 10000]: {collatz_sat['verified']}/{collatz_sat['total']} "
          f"({'✓ ALL' if collatz_sat['all_verified'] else '✗ FAILED'})")
    print(f"    Max stopping time: {collatz_sat['max_stopping_time']} "
          f"| Max orbit value: {collatz_sat['max_orbit_value']:,}")

    erdos_sat = ErdosStrausSATEncoder.batch_verify(2, 1001)
    print(f"  Erdős–Straus verified [2, 1000]: {erdos_sat['verified']}/{erdos_sat['total']} "
          f"({'✓ ALL' if erdos_sat['all_verified'] else '✗ FAILED: ' + str(erdos_sat['failed'][:5])})")

    # Small Hadamard CSP search
    hadamard_csp = {}
    for n in [4, 8, 12]:
        result = HadamardSATEncoder.search_csp(n)
        hadamard_csp[n] = result is not None
        status = '✓' if result is not None else '✗'
        print(f"  Hadamard CSP order {n}: {status}")

    print(f"  Phase 0 time: {time.time() - t0:.1f}s")

    # ── Phase 1: Multi-Agent Solving ──
    print("\nPhase 1: Multi-agent self-iterative solving...")

    config = {
        'max_rounds': 8,
        'max_workers': 1,  # sequential for stability
        'domains': ['collatz', 'erdos_straus', 'hadamard'],
        'pollinate_every': 2,
        'meta_learn_every': 2,
        'formalize_every': 2,
        'adversary_time_budget': 120,  # 50/50 search vs review split
        'agents_per_type': {
            'explorer': 1,
            'pattern_miner': 1,
            'adversary': 1,
            'refiner': 1,
            'formalizer': 1,
            'meta_learner': 1,
            'pollinator': 1,
        },
        'verbose': True,
    }

    orchestrator = Orchestrator(config)
    results = orchestrator.run()

    # Inject SAT pre-computation results
    results['sat_verification'] = {
        'collatz': collatz_sat,
        'erdos_straus': erdos_sat,
        'hadamard_csp': hadamard_csp,
    }

    # ── Phase 2: Formal verification code generation ──
    print("\nPhase 2: Generating formal verification stubs...")

    lean_collatz = FormalVerification.generate_lean4_collatz_verifier(10000)
    lean_erdos = FormalVerification.generate_lean4_erdos_straus_verifier(1000)

    results['formal_verification'] = {
        'lean4_collatz': lean_collatz,
        'lean4_erdos_straus': lean_erdos,
    }
    print("  Generated Lean 4 stubs for Collatz and Erdős–Straus")

    # ── Phase 3: Save results ──
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
    os.makedirs(results_dir, exist_ok=True)

    json_path = os.path.join(results_dir, 'unsolved_solver_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {json_path}")

    # ── Phase 4: HTML report ──
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'unsolved-solver-report.html')
    generate_html_report(results, html_path)
    print(f"  HTML report: {html_path}")

    # ── Summary ──
    print()
    print("=" * 62)
    print("  SUMMARY")
    print("=" * 62)
    stats = results.get('global_stats', {})
    print(f"  Total discoveries: {stats.get('total_discoveries', 0)}")
    print(f"  Validated:         {stats.get('total_validated', 0)}")
    print(f"  Falsified:         {stats.get('total_falsified', 0)}")
    print(f"  Proof sketches:    {sum(1 for d in results.get('top_discoveries', []) if d.get('category') == 'proof_sketch')}")
    # Also count from domain reports
    total_proofs = sum(len(dr.get('proof_sketches', []))
                       for dr in results.get('domain_reports', {}).values())
    if total_proofs > 0:
        print(f"  (total across domains: {total_proofs})")
    print(f"  Total time:        {results.get('total_time', 0):.1f}s")
    print(f"  Pre-reg hash:      {results.get('preregistration_hash', '')[:32]}...")
    print()

    # Print top discoveries
    top = results.get('top_discoveries', [])[:5]
    if top:
        print("  Top Discoveries:")
        for i, d in enumerate(top, 1):
            desc = d.get('content', {}).get('description',
                   d.get('content', {}).get('type',
                   d.get('content', {}).get('name', '?')))
            print(f"  {i}. [{d.get('domain', '')}] {d.get('category', '')}"
                  f" (conf={d.get('confidence', 0):.2f}): {str(desc)[:50]}")

    print()
    print("Done.")
    return results


if __name__ == '__main__':
    main()
