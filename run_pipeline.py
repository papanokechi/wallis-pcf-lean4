#!/usr/bin/env python3
"""
Universal Pipeline — Automation Runbook
════════════════════════════════════════

Single-command execution of the full Transcendental Architect pipeline:
  1. Environment check
  2. Full formalization on latest sweep data
  3. zeta(5) (5,5) deep strike
  4. V_quad Lommel/Weber/Meijer scan
  5. Snapshot artifacts
  6. Summary report

Usage:
    python run_pipeline.py                  # full pipeline
    python run_pipeline.py --step 2         # just formalization
    python run_pipeline.py --step 3         # just zeta5 strike
    python run_pipeline.py --step 4         # just Lommel scan
    python run_pipeline.py --snapshot-only  # just save snapshot
    python run_pipeline.py --status         # check status of all outputs
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime


# ── File inventory ──
ARTIFACTS = {
    # Sweep outputs
    "kloosterman_sweep_results.json": "Kloosterman sweep (100 iters, 209 discoveries)",
    "kloosterman_relay_seeds.json":   "Relay seed pool from sweep",
    "ramanujan_persistent_seeds.json": "Persistent promoted seeds",

    # Formalization outputs
    "discovery_catalog.json":         "Canonical discovery catalog (JSON)",
    "discovery_catalog.csv":          "Canonical discovery catalog (CSV)",
    "verification_results.json":      "High-precision verification (1000dp)",
    "formalization_report.txt":       "Full formalization report",
    "zeta5_architect_templates.json": "zeta(5) templates for next sweep",

    # PSLQ outputs
    "lommel_pslq_results.txt":        "Lommel/Weber/Meijer scan results",

    # zeta(5) strike outputs
    "zeta5_55_sweep_results.json":    "zeta(5) (5,5) deep strike results",
    "zeta5_55_sweep_results.csv":     "zeta(5) (5,5) deep strike CSV",

    # V_quad
    "V_quad_1000digits.txt":          "V_quad to 1000+ digits",
}

PYTHON = sys.executable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def check_status():
    """Print status of all expected artifacts."""
    print("=" * 70)
    print("  PIPELINE STATUS CHECK")
    print("=" * 70)
    for fname, desc in ARTIFACTS.items():
        path = os.path.join(BASE_DIR, fname)
        if os.path.exists(path):
            sz   = os.path.getsize(path)
            mod  = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
            status = "OK" if sz > 100 else "EMPTY"
            print(f"  [{status:5s}] {fname:45s} {sz:>10,} bytes  {mod}")
        else:
            print(f"  [MISS ] {fname:45s} — not found")
    print()

    # Check running processes
    try:
        import psutil
        py_procs = [p for p in psutil.process_iter(['name']) if 'python' in (p.info['name'] or '').lower()]
        print(f"  Python processes running: {len(py_procs)}")
    except ImportError:
        print("  (install psutil for process monitoring)")


def run_step(step_num, name, cmd, timeout=None):
    """Execute a pipeline step."""
    print(f"\n{'='*70}")
    print(f"  STEP {step_num}: {name}")
    print(f"{'='*70}")
    print(f"  Command: {' '.join(cmd)}")
    print(f"  Started: {datetime.now().strftime('%H:%M:%S')}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    t0 = time.time()
    result = subprocess.run(cmd, env=env, capture_output=False, timeout=timeout)
    elapsed = time.time() - t0

    status = "OK" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
    print(f"\n  Step {step_num} {status} in {elapsed:.1f}s")
    return result.returncode == 0


def snapshot_artifacts():
    """Copy all artifacts to a timestamped snapshot directory."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_dir = os.path.join(BASE_DIR, "snapshots", f"snapshot_{ts}")
    os.makedirs(snap_dir, exist_ok=True)

    copied = 0
    for fname in ARTIFACTS:
        src = os.path.join(BASE_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, snap_dir)
            copied += 1

    # Also save environment
    env_file = os.path.join(snap_dir, "requirements_freeze.txt")
    subprocess.run([PYTHON, "-m", "pip", "freeze"], stdout=open(env_file, "w"),
                   capture_output=False)

    print(f"\n  Snapshot: {snap_dir}")
    print(f"  Files copied: {copied}/{len(ARTIFACTS)}")
    return snap_dir


def write_summary(snap_dir):
    """Write a pipeline execution summary."""
    summary_path = os.path.join(BASE_DIR, "pipeline_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("  TRANSCENDENTAL ARCHITECT — PIPELINE EXECUTION SUMMARY\n")
        f.write(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")

        # Discovery catalog stats
        cat_path = os.path.join(BASE_DIR, "discovery_catalog.json")
        if os.path.exists(cat_path):
            with open(cat_path) as cf:
                catalog = json.load(cf)
            f.write(f"  Discoveries cataloged: {len(catalog)}\n")
            from collections import Counter
            targets = Counter(d["target"] for d in catalog)
            f.write("  By target:\n")
            for t, c in targets.most_common():
                f.write(f"    {c:4d}  {t}\n")
            verified = sum(1 for d in catalog if d.get("verified"))
            f.write(f"  Verified at 1000dp: {verified}\n\n")

        # Verification results
        ver_path = os.path.join(BASE_DIR, "verification_results.json")
        if os.path.exists(ver_path):
            with open(ver_path) as vf:
                verifications = json.load(vf)
            ok = sum(1 for v in verifications if v.get("status") == "VERIFIED")
            f.write(f"  Verification: {ok}/{len(verifications)} VERIFIED\n\n")

        # PSLQ results
        pslq_path = os.path.join(BASE_DIR, "lommel_pslq_results.txt")
        if os.path.exists(pslq_path):
            with open(pslq_path) as pf:
                pslq_content = pf.read()
            if "No relations found" in pslq_content:
                f.write("  Lommel/Weber/Meijer scan: NO RELATIONS (V_quad excluded)\n")
            else:
                f.write("  Lommel/Weber/Meijer scan: RELATIONS FOUND — see report\n")
            f.write("\n")

        # zeta5 strike
        z5_path = os.path.join(BASE_DIR, "zeta5_55_sweep_results.json")
        if os.path.exists(z5_path):
            with open(z5_path) as zf:
                z5 = json.load(zf)
            disc = len(z5.get("discoveries", []))
            f.write(f"  zeta(5) (5,5) strike: {disc} discoveries\n\n")

        if snap_dir:
            f.write(f"  Snapshot: {snap_dir}\n")

        f.write("\n" + "=" * 70 + "\n")

    print(f"\n  Summary written to {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Transcendental Architect Pipeline")
    parser.add_argument("--step", type=int, default=0,
                        help="Run only this step (1-4). 0 = all.")
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-snapshot", action="store_true")
    parser.add_argument("--lommel-timeout", type=int, default=3600,
                        help="Timeout for Lommel scan in seconds.")
    parser.add_argument("--zeta5-timeout", type=int, default=7200,
                        help="Timeout for zeta5 strike in seconds.")
    args = parser.parse_args()

    os.chdir(BASE_DIR)

    if args.status:
        check_status()
        return

    if args.snapshot_only:
        snap = snapshot_artifacts()
        write_summary(snap)
        return

    print("=" * 70)
    print("  TRANSCENDENTAL ARCHITECT — UNIVERSAL PIPELINE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    run_all = args.step == 0
    snap_dir = None

    # ── Step 1: Environment check ──
    if run_all or args.step == 1:
        print("\n  [Step 1] Environment check...")
        result = subprocess.run([PYTHON, "-c", "import mpmath; print(f'mpmath {mpmath.__version__}')"],
                               capture_output=True, text=True)
        print(f"    {result.stdout.strip()}")
        check_status()

    # ── Step 2: Full formalization ──
    if run_all or args.step == 2:
        run_step(2, "Full Formalization (209 discoveries)",
                [PYTHON, "formalization_phase.py"])

    # ── Step 3: zeta(5) (5,5) deep strike ──
    if run_all or args.step == 3:
        run_step(3, "zeta(5) (5,5) Transcendental Strike",
                [PYTHON, "run_zeta5_55_strike.py"],
                timeout=args.zeta5_timeout)

    # ── Step 4: Lommel/Weber/Meijer PSLQ scan ──
    if run_all or args.step == 4:
        run_step(4, "V_quad Lommel/Weber/Meijer PSLQ Scan",
                [PYTHON, "vquad_lommel_scan.py"],
                timeout=args.lommel_timeout)

    # ── Step 5: Snapshot ──
    if not args.no_snapshot:
        print(f"\n{'='*70}")
        print("  STEP 5: Snapshot artifacts")
        print(f"{'='*70}")
        snap_dir = snapshot_artifacts()

    # ── Step 6: Summary ──
    print(f"\n{'='*70}")
    print("  STEP 6: Pipeline summary")
    print(f"{'='*70}")
    write_summary(snap_dir)

    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
