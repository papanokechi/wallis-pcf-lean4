#!/usr/bin/env python3
"""
roadmap_runner.py — Chain all phase scripts in sequence.
=========================================================
Runs Phase 0 → 0c → 1 → 2 → 3 → 4 and collects results.
Can also run individual phases or the integrated generator modes.

Usage:
  python roadmap_runner.py                  # run all phases
  python roadmap_runner.py --phase 0        # just Phase 0
  python roadmap_runner.py --phase 0c 1 2   # selected phases
  python roadmap_runner.py --quick           # fast mode (reduced budgets)
  python roadmap_runner.py --generator-only  # run generator integrated modes
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PHASES = {
    '0':  ('_phase0_seed_generator.py',  'Phase 0: Seed Generator — Pi Family Closed Forms'),
    '0b': ('_phase0b_extended_guess.py',  'Phase 0b: Extended Guess (m≥2)'),
    '0c': ('_phase0c_higher_m.py',        'Phase 0c: Higher-m via polynomial-in-m insight'),
    '1':  ('_phase1_generalize.py',        'Phase 1: Generalize — Parity, Meta-Family, Universality'),
    '2':  ('_phase2_vquad_hunt.py',        'Phase 2: V_quad — Quadratic GCF Hunt + PSLQ'),
    '3':  ('_phase3_dashboard.py',         'Phase 3: Visual Executive Dashboard'),
    '4':  ('_phase4_higher_degree.py',     'Phase 4: Higher-Degree PCFs + LaTeX Bundle'),
    '5':  ('_phase5_hypergeometric.py',    'Phase 5: Hypergeometric Attack + Discriminant-5'),
}

DEFAULT_ORDER = ['0', '0c', '1', '2', '3', '4', '5']


def run_phase(phase_id, python_exe):
    """Run a single phase script and return (success, elapsed)."""
    script, desc = PHASES[phase_id]
    script_path = Path(script)
    
    if not script_path.exists():
        print(f"  ⚠ {script} not found, skipping.")
        return False, 0
    
    print(f"\n{'═' * 74}")
    print(f"  RUNNING: {desc}")
    print(f"  Script:  {script}")
    print(f"{'═' * 74}\n")
    
    t0 = time.time()
    try:
        result = subprocess.run(
            [python_exe, str(script_path)],
            capture_output=False,
            text=True,
            timeout=900,  # 15 min max per phase
            env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        elapsed = time.time() - t0
        ok = result.returncode == 0
        status = "✓" if ok else f"✗ (exit {result.returncode})"
        print(f"\n  {status} {desc} — {elapsed:.1f}s")
        return ok, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        print(f"\n  ⚠ TIMEOUT after {elapsed:.0f}s — {desc}")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n  ✗ ERROR: {e}")
        return False, elapsed


def run_generator_modes(python_exe):
    """Run the three integrated generator modes."""
    gen_script = 'ramanujan_breakthrough_generator.py'
    if not Path(gen_script).exists():
        print(f"  ⚠ {gen_script} not found.")
        return
    
    modes = [
        ('conjecture_prover', ['--mode', 'conjecture_prover', '--depth', '200', '--no-ai']),
        ('parity',            ['--mode', 'parity', '--depth', '2000', '--no-ai']),
        ('quadratic_gcf',     ['--mode', 'quadratic_gcf', '--budget', '200', '--precision', '200', '--no-ai']),
        ('hypergeometric_guess', ['--mode', 'hypergeometric_guess', '--depth', '2000', '--precision', '100', '--no-ai']),
    ]
    
    for name, args in modes:
        print(f"\n{'─' * 74}")
        print(f"  Generator mode: {name}")
        print(f"{'─' * 74}\n")
        
        t0 = time.time()
        subprocess.run(
            [python_exe, gen_script] + args,
            timeout=300,
            env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        elapsed = time.time() - t0
        print(f"  Done: {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Run PCF & V_quad roadmap phases")
    parser.add_argument('--phase', nargs='*', choices=list(PHASES.keys()),
                        help='Specific phases to run (default: all)')
    parser.add_argument('--quick', action='store_true',
                        help='Skip slow phases (0b, 2)')
    parser.add_argument('--generator-only', action='store_true',
                        help='Run only the integrated generator modes')
    parser.add_argument('--python', type=str, default=None,
                        help='Python executable path')
    args = parser.parse_args()
    
    # Find Python
    python_exe = args.python
    if python_exe is None:
        venv_python = Path('.venv/Scripts/python.exe')
        if venv_python.exists():
            python_exe = str(venv_python)
        else:
            python_exe = sys.executable
    
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          PCF & V_quad ROADMAP RUNNER                       ║")
    print("║   Chains all phase scripts in sequence                     ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Python: {python_exe}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    if args.generator_only:
        run_generator_modes(python_exe)
        return
    
    phases_to_run = args.phase if args.phase else DEFAULT_ORDER
    if args.quick:
        phases_to_run = [p for p in phases_to_run if p not in ('0b', '2')]
    
    print(f"  Phases: {' → '.join(phases_to_run)}")
    
    t0_total = time.time()
    results = {}
    
    for phase_id in phases_to_run:
        ok, elapsed = run_phase(phase_id, python_exe)
        results[phase_id] = {'success': ok, 'elapsed': round(elapsed, 1)}
    
    total_elapsed = time.time() - t0_total
    
    # Summary
    print(f"\n{'═' * 74}")
    print(f"  ROADMAP RUNNER SUMMARY")
    print(f"{'═' * 74}")
    for pid, info in results.items():
        sym = "✓" if info['success'] else "✗"
        _, desc = PHASES[pid]
        print(f"  {sym} {desc} ({info['elapsed']:.1f}s)")
    print(f"\n  Total time: {total_elapsed:.1f}s")
    
    # Check output files
    output_files = [
        'phase0_results.json', 'phase0c_results.json',
        'phase1_results.json', 'phase2_results.json',
        'phase4_results.json',
        'pcf_vquad_dashboard.html', 'pcf_vquad_paper.tex',
    ]
    print(f"\n  Output files:")
    for f in output_files:
        exists = Path(f).exists()
        size = Path(f).stat().st_size if exists else 0
        print(f"    {'✓' if exists else '✗'} {f}" + (f" ({size:,} bytes)" if exists else ""))
    
    # Save run summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_seconds': round(total_elapsed, 1),
        'phases': results,
    }
    Path('roadmap_run_summary.json').write_text(json.dumps(summary, indent=2))
    print(f"\n  Run summary: roadmap_run_summary.json")


if __name__ == '__main__':
    main()
