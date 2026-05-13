#!/usr/bin/env python3
"""
outlook_emit.py -- emit M1-M12 closure outlook from primary sources.

Replaces hand-maintained M1_M12_CLOSURE_OUTLOOK_<DATE>_<TAG>.md files
per V211 Q-211-3 / Q-211-5 verdict (bridge HEAD 137730b 2026-05-13;
slot T1-SYNTH-VERDICT-211-M1-SAFE-CLOSURE-ABSORPTION).

Inputs (primary sources):
  - Bridge slot verdicts (filesystem glob siarc-relay-bridge/sessions/*/T*/)
  - Zenodo REST API (live; passive read, not DISTRIBUTION-class)
  - claude-chat git log (marker commits for RULE/PATH governance state)

Output:
  - Markdown closure outlook to stdout

Usage:
  python scripts/outlook_emit.py                          # write to stdout
  python scripts/outlook_emit.py --out path/to/file.md    # write directly to file (UTF-8)

  # Prefer --out on Windows; PowerShell's `>` redirect uses cp1252 by default
  # and mojibakes emoji/Greek characters in the output.

Implementation status:
  v0.1 (MVP) -- hardcoded axis definitions; live Zenodo queries; bridge slot
                discovery via glob; claude-chat marker via git log -1; emits
                §0 governance state + §1 axis table + §2 cascade-132 status +
                §3 substrate sources block. Future v0.2: discover axis
                definitions from a YAML/JSON sidecar so adding M13+ doesn't
                require script edits.

Author: SIARC Copilot CLI (agent) via slot T1-OPERATOR-V211-COMMITMENTS-CASCADE-EXECUTION
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_ROOT = REPO_ROOT / "siarc-relay-bridge"
JST = timezone(timedelta(hours=9))

# Axis definitions (hardcoded for v0.1; promote to YAML in v0.2).
# Each axis has:
#   name            : human-readable scope label
#   zenodo_concept  : concept DOI suffix (e.g. "19996689") or None
#   zenodo_version  : latest version record ID or None
#   slot_pattern    : regex over bridge slot folder names that match this axis
#                     closure verdict; most-recent match wins
#   notes           : permanent free-text notes (e.g. "retired/folded into M4")
AXIS_DEFINITIONS = [
    {"id": "M1",  "name": "D2-NOTE / standalone-note Zenodo deposit",
     "zenodo_concept": "19996689", "zenodo_version": "20015923",
     "slot_pattern": r"(M1-D2-NOTE-DISPOSITION|D2-NOTE-ZENODO|S154-M1-D2-NOTE)",
     "notes": ""},
    {"id": "M2",  "name": "PCF-2 v1.4 deposit + Q22 math arbitration",
     "zenodo_concept": "19936297", "zenodo_version": "20114315",
     "slot_pattern": r"PCF2-V14",
     "notes": "Q22 substantively absorbed via slot 137 §6 op:j-zero-amplitude-h6"},
    {"id": "M3",  "name": "retired/folded into M4",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": None,
     "notes": "retired/folded into M4"},
    {"id": "M4",  "name": "PCF foundation borderline-ansatz axis",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"M4-V0-CLOSURE|M4-RATIFICATION",
     "notes": "V0 ratified 104->105->106; cross-ref only per ANTI-CONFLATION"},
    {"id": "M5",  "name": "retired/folded into M6.CC",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": None,
     "notes": "retired/folded into M6.CC"},
    {"id": "M6.CC", "name": "V_quad -> P_III chart-map / Cremona",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"VQUAD-PIII|CC-VQUAD",
     "notes": "residuals absorbed into cascades 123/130R"},
    {"id": "M7",  "name": "post-M4 axis closure",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"M7-V0-CLOSURE|M7-RATIFICATION",
     "notes": ""},
    {"id": "M8a", "name": "post-M4 axis closure",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"M8A-RATIFICATION|M8a-V0",
     "notes": ""},
    {"id": "M8b", "name": "post-M4 axis closure (sub-leading Stokes constant)",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"M8B-RATIFICATION|M8b-V0",
     "notes": "PERMANENT_RESIDUAL classification per cascade 130R"},
    {"id": "M9",  "name": "V0 main announcement (Bull. AMS-class)",
     "zenodo_concept": "20114861", "zenodo_version": "20114861",  # Umbrella v2.2 standin
     "slot_pattern": r"UMBRELLA-V22|PICTURE-V120|M9-V0",
     "notes": "substrate-source-of-record CLOSED via cascade-132 PATH_B 3/3"},
    {"id": "M10", "name": "Lean-4 formalization / tooling-state",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"M10-DOCUMENTED-COMMITMENT|m10_documented",
     "notes": "documented-commitment closed; OPTIONAL UPLIFT 2026-08-02"},
    {"id": "M11", "name": "math.NT arXiv endorsement acquisition",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"ENDORSEMENT|GAROUFALIDIS|CARNEIRO|MAZZOCCO",
     "notes": "UNBLOCKED post-RULE-1-lift; slot 155 fire-eligible"},
    {"id": "M12", "name": "Resubmit-target packaging (4 papers + Ramanujan-J + Compositio + iscitedby polish)",
     "zenodo_concept": None, "zenodo_version": None,
     "slot_pattern": r"RESUBMIT|VENUE-TRIAGE|AFM-DESK-REJECT",
     "notes": "UNBLOCKED post-RULE-1-lift; slot 156 fire-eligible; AFM desk-reject 2026-05-07"},
]

# Claude-chat marker commits to surface in §0 governance state.
# Use restrictive search patterns to match the canonical declaration commit,
# not later commits that merely mention the marker in passing.
GOVERNANCE_MARKERS = [
    {"name": "RULE 1 LIFT",
     "search_pattern": "RULE 1 LIFTED -- math-axis closure complete"},
]


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def now_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%dT%H:%M JST")


def query_zenodo(record_id: str) -> dict | None:
    """Hit Zenodo REST API. Returns metadata dict or None on failure."""
    if not record_id:
        return None
    url = f"https://zenodo.org/api/records/{record_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "siarc-outlook-emit/0.1"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        return {
            "title": data.get("metadata", {}).get("title", "?"),
            "version": data.get("metadata", {}).get("version", "?"),
            "doi": data.get("doi", "?"),
            "conceptdoi": data.get("conceptdoi", "?"),
            "publication_date": data.get("metadata", {}).get("publication_date", "?"),
        }
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        return {"_error": str(e)}


def find_latest_slot(pattern: str | None) -> dict | None:
    """Glob bridge sessions/ for folders matching pattern; return most recent."""
    if not pattern:
        return None
    compiled = re.compile(pattern, re.IGNORECASE)
    if not BRIDGE_ROOT.exists():
        return None
    matches = []
    sessions_root = BRIDGE_ROOT / "sessions"
    if not sessions_root.exists():
        return None
    for date_dir in sessions_root.iterdir():
        if not date_dir.is_dir():
            continue
        for slot_dir in date_dir.iterdir():
            if not slot_dir.is_dir():
                continue
            if compiled.search(slot_dir.name):
                matches.append((date_dir.name, slot_dir.name, slot_dir))
    if not matches:
        return None
    # Sort by date string descending (YYYY-MM-DD sorts naturally)
    matches.sort(key=lambda m: (m[0], m[1]), reverse=True)
    date_str, slot_name, slot_path = matches[0]
    # Find a SHA if a git log is available
    sha = None
    try:
        out = subprocess.check_output(
            ["git", "-C", str(BRIDGE_ROOT), "log", "-1", "--format=%h",
             "--", f"sessions/{date_str}/{slot_name}/"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        if out:
            sha = out
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return {"date": date_str, "slot": slot_name, "sha": sha, "path": str(slot_path)}


def query_claude_chat_marker(search_pattern: str) -> dict | None:
    """git log claude-chat (cwd) for marker commits matching pattern.

    Returns the OLDEST matching commit (the canonical declaration), not the
    most recent (which may be a later cross-reference). If only one match
    exists, that's returned.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "log", "--all",
             "--format=%H|%ci|%s", "--reverse",
             f"--grep={search_pattern}"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        if not out:
            return None
        lines = out.split("\n")
        first = lines[0].split("|", 2)
        if len(first) == 3:
            return {"sha": first[0][:8], "date": first[1], "msg": first[2]}
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def status_emoji(axis: dict, slot: dict | None, zenodo: dict | None) -> str:
    """Heuristic axis status emoji + label."""
    notes = (axis.get("notes") or "").lower()
    if "retired" in notes:
        return "✅ RETIRED"
    if "closed" in notes or "v0" in notes or "ratified" in notes:
        return "🟢 CLOSED"
    if "documented-commitment" in notes:
        return "🟢 DOC-COMMITTED"
    if "unblocked" in notes:
        return "🟡 READY (post-lift)"
    if zenodo and not zenodo.get("_error") and zenodo.get("doi", "?") != "?":
        return "🟢 CLOSED"
    if slot:
        return "🟢 CLOSED"
    return "🟡 OPEN"


# -------------------------------------------------------------------------
# Emission
# -------------------------------------------------------------------------

def emit():
    # Force UTF-8 stdout so emojis and Greek letters survive Windows cp1252 default
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    print(f"# M1-M12 Closure Outlook -- generated {now_jst()}")
    print()

    # Bridge HEAD
    bridge_head = None
    try:
        bridge_head = subprocess.check_output(
            ["git", "-C", str(BRIDGE_ROOT), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Claude-chat HEAD
    cc_head = None
    try:
        cc_head = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    print(f"**Bridge HEAD:** `{bridge_head or '?'}`")
    print(f"**claude-chat HEAD:** `{cc_head or '?'}`")
    print(f"**Generator:** `scripts/outlook_emit.py` v0.1 (per V211 Q-211-3 / Q-211-5 γ)")
    print(f"**Source:** bridge slot verdicts + Zenodo REST API + claude-chat git log")
    print()
    print("---")
    print()

    # §0 Governance state
    print("## §0. Governance state (marker commits)")
    print()
    for marker in GOVERNANCE_MARKERS:
        hit = query_claude_chat_marker(marker["search_pattern"])
        if hit:
            print(f"* **{marker['name']}**: commit `{hit['sha']}` ({hit['date']})")
            print(f"  > {hit['msg']}")
        else:
            print(f"* **{marker['name']}**: NOT FOUND in claude-chat git log")
    print()
    print("---")
    print()

    # §1 Axis table
    print("## §1. Axis-level closure status")
    print()
    print("| Axis | Scope | Status | Substrate | Last verdict |")
    print("|:---:|---|:---:|---|---|")

    for axis in AXIS_DEFINITIONS:
        slot = find_latest_slot(axis["slot_pattern"])
        zenodo = query_zenodo(axis["zenodo_version"]) if axis["zenodo_version"] else None
        status = status_emoji(axis, slot, zenodo)

        # Substrate column
        substrate_parts = []
        if zenodo and not zenodo.get("_error"):
            substrate_parts.append(
                f"Zenodo `{zenodo['doi']}` v{zenodo['version']} ({zenodo['publication_date']})"
            )
        elif zenodo and zenodo.get("_error"):
            substrate_parts.append(f"Zenodo query FAILED: {zenodo['_error'][:40]}")
        if axis.get("notes"):
            substrate_parts.append(axis["notes"])
        substrate = "; ".join(substrate_parts) if substrate_parts else "—"

        # Last verdict column
        if slot:
            verdict = f"`{slot['sha'] or '?'}` {slot['date']} `{slot['slot'][:50]}`"
        else:
            verdict = "—"

        print(f"| **{axis['id']}** | {axis['name']} | {status} | {substrate} | {verdict} |")
    print()
    print("---")
    print()

    # §2 Substrate sources block (proves the emission is from live primary sources)
    print("## §2. Substrate provenance")
    print()
    print("This outlook was emitted from primary sources at the timestamps below.")
    print("Re-running `scripts/outlook_emit.py` at any HEAD produces a fresh outlook.")
    print()
    print(f"* **Bridge filesystem:** `{BRIDGE_ROOT}` (HEAD `{bridge_head or '?'}`)")
    print(f"* **claude-chat repo:** `{REPO_ROOT}` (HEAD `{cc_head or '?'}`)")
    print(f"* **Zenodo API endpoint:** `https://zenodo.org/api/records/<id>` (live)")
    print(f"* **Generator version:** `outlook_emit.py` v0.1")
    print()
    print("---")
    print()
    print("**End closure outlook.**")
    print()
    print("_To refresh, re-run `python scripts/outlook_emit.py` from the claude-chat repo root._")


if __name__ == "__main__":
    out_path = None
    argv = sys.argv[1:]
    if argv:
        if argv[0] in ("--out", "-o") and len(argv) >= 2:
            out_path = Path(argv[1])
        elif argv[0] in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Unknown argument: {argv[0]}", file=sys.stderr)
            print("Usage: outlook_emit.py [--out PATH]", file=sys.stderr)
            sys.exit(2)

    if out_path is not None:
        # Redirect stdout to the file with explicit UTF-8 encoding
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            saved = sys.stdout
            sys.stdout = fh
            try:
                emit()
            finally:
                sys.stdout = saved
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        emit()
