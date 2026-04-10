#!/usr/bin/env python3
"""
github_research_sync.py
-----------------------
Non-blocking GitHub integration for ramanujan_breakthrough_generator.py.

Features:
  1. Discovery Committer -- branch + commit + PR per new discovery
  2. Status Orchestrator -- updates README.md with live discovery table
  3. Background threading -- never blocks the evolutionary search loop

Usage (standalone):
  python github_research_sync.py --sync          # push pending discoveries
  python github_research_sync.py --update-readme  # refresh README status block
  python github_research_sync.py --daemon 60      # background every 60s

Integration (from generator main loop):
  from github_research_sync import maybe_sync
  maybe_sync(cycle, scan_every=10)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# ASCII-only logger (Windows safe)
# ---------------------------------------------------------------------------
_log = logging.getLogger("gh_sync")
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[gh_sync %(levelname)s] %(message)s"))
_log.addHandler(_handler)
_log.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parent
LOGFILE = WORKSPACE / "ramanujan_discoveries.jsonl"
STATEFILE = WORKSPACE / "ramanujan_state.json"
SYNC_LEDGER = WORKSPACE / ".gh_sync_ledger.json"
DISCOVERIES_DIR = "discoveries"
README_PATH = WORKSPACE / "README.md"

# README markers
README_BEGIN = "<!-- DISCOVERY_STATUS_BEGIN -->"
README_END = "<!-- DISCOVERY_STATUS_END -->"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Load .env if python-dotenv is available; otherwise fall through."""
    try:
        from dotenv import load_dotenv
        load_dotenv(WORKSPACE / ".env")
    except ImportError:
        pass


def _github_token() -> str | None:
    _load_env()
    return os.environ.get("GITHUB_TOKEN")


def _repo_slug() -> str | None:
    """Return 'owner/repo' from env or git remote."""
    _load_env()
    slug = os.environ.get("GITHUB_REPO")
    if slug:
        return slug
    # Fallback: parse git remote
    try:
        import subprocess
        out = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(WORKSPACE),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Ledger -- tracks which discoveries have been pushed
# ---------------------------------------------------------------------------

def _load_ledger() -> dict[str, Any]:
    if SYNC_LEDGER.exists():
        try:
            return json.loads(SYNC_LEDGER.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"pushed": [], "last_readme_update": None}


def _save_ledger(ledger: dict[str, Any]) -> None:
    SYNC_LEDGER.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _load_discoveries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not LOGFILE.exists():
        return entries
    for line in LOGFILE.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _discovery_id(d: dict[str, Any]) -> str:
    """Deterministic short id from coefficients."""
    a_part = "_".join(str(c) for c in d.get("a", []))
    b_part = "_".join(str(c) for c in d.get("b", []))
    return f"a{a_part}__b{b_part}"


def _discovery_filename(d: dict[str, Any]) -> str:
    ts = d.get("timestamp", datetime.now(timezone.utc).isoformat())
    date = ts[:10]
    did = _discovery_id(d)
    # sanitize
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", did)[:80]
    return f"{date}_{safe}.json"


def _latex_cf(d: dict[str, Any]) -> str:
    """Build a LaTeX representation of the PCF (ASCII safe)."""
    a_coeffs = d.get("a", [])
    b_coeffs = d.get("b", [])

    def _poly_str(coeffs: list, var: str = "n") -> str:
        if not coeffs:
            return "0"
        terms = []
        for i, c in enumerate(coeffs):
            if c == 0:
                continue
            if i == 0:
                terms.append(str(c))
            elif i == 1:
                if c == 1:
                    terms.append(var)
                elif c == -1:
                    terms.append(f"-{var}")
                else:
                    terms.append(f"{c}{var}")
            else:
                if c == 1:
                    terms.append(f"{var}^{i}")
                elif c == -1:
                    terms.append(f"-{var}^{i}")
                else:
                    terms.append(f"{c}{var}^{i}")
        return " + ".join(terms).replace("+ -", "- ") if terms else "0"

    a_str = _poly_str(a_coeffs)
    b_str = _poly_str(b_coeffs)
    match = d.get("match", "?")
    vd = d.get("verified_digits", "?")
    return (
        f"$$\\text{{CF}}\\bigl(a(n)={a_str},\\; b(n)={b_str}\\bigr) "
        f"= {match}$$\n\nVerified to **{vd}** digits."
    )

# ---------------------------------------------------------------------------
# 1. Discovery Committer
# ---------------------------------------------------------------------------

def commit_discovery(d: dict[str, Any], token: str, repo_slug: str) -> str | None:
    """Create branch, commit discovery JSON, open PR. Returns PR URL or None."""
    try:
        from github import Github, GithubException
    except ImportError:
        _log.warning("PyGithub not installed -- skipping commit (pip install PyGithub)")
        return None

    did = _discovery_id(d)
    fname = _discovery_filename(d)
    ts = d.get("timestamp", datetime.now(timezone.utc).isoformat())
    date = ts[:10]
    branch_name = f"discovery/{date}_{did}"[:128]
    match_name = d.get("match", "unknown")

    try:
        gh = Github(token)
        repo = gh.get_repo(repo_slug)
        default_branch = repo.default_branch
        ref = repo.get_git_ref(f"heads/{default_branch}")
        sha = ref.object.sha

        # Create branch
        try:
            repo.create_git_ref(f"refs/heads/{branch_name}", sha)
        except GithubException as exc:
            if exc.status == 422:
                _log.info("Branch %s already exists -- skipping", branch_name)
                return None
            raise

        # Commit discovery file
        file_path = f"{DISCOVERIES_DIR}/{fname}"
        content = json.dumps(d, indent=2, ensure_ascii=True)
        commit_msg = f"discovery: {match_name} (a={d.get('a')}, b={d.get('b')})"
        repo.create_file(
            path=file_path,
            message=commit_msg,
            content=content,
            branch=branch_name,
        )

        # Open PR
        # Conjecture verification via adaptive_discovery
        pr_flag = "Unverified"
        closed_form_note = ""
        try:
            from adaptive_discovery import attempt_closed_form
            verif = attempt_closed_form(
                a_coeffs=d.get("a", []),
                b_coeffs=d.get("b", []),
                match_label=match_name,
            )
            pr_flag = verif.get("pr_flag", "Unverified")
            if verif.get("closed_form"):
                closed_form_note = (
                    f"\n\n**Closed form (SymPy):** {verif['closed_form']}\n"
                )
            elif verif.get("is_novel"):
                closed_form_note = (
                    "\n\n> **Flag:** No known closed form found. "
                    "This may represent a **Potential New Mathematical Identity**.\n"
                )
        except Exception:
            pass

        # Convergence map image
        convergence_note = ""
        try:
            from adaptive_discovery import generate_convergence_map
            img_path = generate_convergence_map(
                a_coeffs=d.get("a", []),
                b_coeffs=d.get("b", []),
                match_label=match_name,
            )
            if img_path:
                rel_path = f"discoveries/assets/{img_path.name}"
                # Commit the image to the branch
                with open(str(img_path), "rb") as img_f:
                    img_bytes = img_f.read()
                import base64
                repo.create_file(
                    path=rel_path,
                    message=f"asset: convergence map for {match_name}",
                    content=base64.b64encode(img_bytes).decode("ascii"),
                    branch=branch_name,
                )
                convergence_note = f"\n\n![Convergence Map]({rel_path})\n"
        except Exception:
            pass

        # Deep Space: elegance scoring
        elegance_note = ""
        elegance_tag = ""
        try:
            from deep_space import compute_elegance_for_discovery
            eleg = compute_elegance_for_discovery(d)
            elegance_tag = eleg.get("elegance_tier", "")
            if elegance_tag and elegance_tag != "Standard":
                elegance_note = (
                    f"\n\n> **Elegance:** {eleg['elegance_score']:.3f} "
                    f"(vd={eleg['verified_digits']:.1f} / "
                    f"dl={eleg['description_length']}) "
                    f"-- **{elegance_tag}**\n"
                )
        except Exception:
            pass

        # Build PR title with elegance tag
        pr_title_tag = f" [{elegance_tag}]" if elegance_tag and elegance_tag != "Standard" else ""
        pr_body = (
            f"## New PCF Discovery [{pr_flag}]{pr_title_tag}\n\n"
            f"{_latex_cf(d)}\n\n"
            f"{closed_form_note}"
            f"{convergence_note}"
            f"{elegance_note}"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| **Constant** | `{match_name}` |\n"
            f"| **a(n)** | `{d.get('a')}` |\n"
            f"| **b(n)** | `{d.get('b')}` |\n"
            f"| **Verified digits** | {d.get('verified_digits', '?')} |\n"
            f"| **Complexity** | {d.get('complexity', '?')} |\n"
            f"| **Residual** | {d.get('residual', '?')} |\n"
            f"| **Type** | {d.get('type', '?')} |\n"
            f"| **Cycle** | {d.get('cycle', '?')} |\n"
            f"| **Status** | {pr_flag} |\n"
        )
        pr = repo.create_pull(
            title=f"Discovery: {match_name} via PCF a={d.get('a')}, b={d.get('b')}{pr_title_tag}",
            body=pr_body,
            head=branch_name,
            base=default_branch,
        )
        _log.info("PR created: %s", pr.html_url)
        return pr.html_url

    except Exception:
        _log.error("Failed to commit discovery:\n%s", traceback.format_exc())
        return None

# ---------------------------------------------------------------------------
# 2. Status Orchestrator -- README updater
# ---------------------------------------------------------------------------

def _build_status_block() -> str:
    """Build Markdown status table from discovery log + state."""
    discoveries = _load_discoveries()
    total = len(discoveries)

    # Unique CFs by (a, b) tuple
    unique_cfs: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    constant_counts: dict[str, int] = {}
    wall_of_fame: list[dict[str, Any]] = []

    for d in discoveries:
        key = (tuple(d.get("a", [])), tuple(d.get("b", [])))
        unique_cfs.add(key)
        m = d.get("match", "unknown")
        constant_counts[m] = constant_counts.get(m, 0) + 1

    # Sort by verified_digits descending for Wall of Fame (top 10)
    ranked = sorted(
        discoveries,
        key=lambda x: -(x.get("verified_digits", 0) or 0),
    )
    # Deduplicate by (a, b) for wall of fame
    seen_keys: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for d in ranked:
        key = (tuple(d.get("a", [])), tuple(d.get("b", [])))
        if key not in seen_keys:
            seen_keys.add(key)
            wall_of_fame.append(d)
        if len(wall_of_fame) >= 10:
            break

    # Read cycle count from state file
    cycles_run = "?"
    if STATEFILE.exists():
        try:
            state = json.loads(STATEFILE.read_text(encoding="utf-8"))
            cycles_run = state.get("cycle", "?")
        except (json.JSONDecodeError, OSError):
            pass

    lines = [
        README_BEGIN,
        "",
        "### Discovery Status",
        "",
        f"*Auto-updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Cycles run | {cycles_run} |",
        f"| Total discoveries | {total} |",
        f"| Unique CFs | {len(unique_cfs)} |",
        f"| Distinct constants | {len(constant_counts)} |",
        "",
    ]

    if constant_counts:
        lines.append("**Constants found:** " + ", ".join(
            f"`{k}` ({v})" for k, v in
            sorted(constant_counts.items(), key=lambda x: -x[1])
        ))
        lines.append("")

    if wall_of_fame:
        lines.append("#### Wall of Fame (top verified CFs)")
        lines.append("")
        lines.append("| # | Constant | a(n) | b(n) | Digits | Complexity |")
        lines.append("|---|----------|------|------|--------|------------|")
        for i, d in enumerate(wall_of_fame, 1):
            lines.append(
                f"| {i} "
                f"| `{d.get('match', '?')}` "
                f"| `{d.get('a', '?')}` "
                f"| `{d.get('b', '?')}` "
                f"| {d.get('verified_digits', '?')} "
                f"| {d.get('complexity', '?')} |"
            )
        lines.append("")

    lines.append(README_END)
    return "\n".join(lines)


def update_readme(token: str | None = None, repo_slug: str | None = None) -> bool:
    """Replace the status block in README.md (local + optional remote push)."""
    new_block = _build_status_block()

    # --- local update ---
    if README_PATH.exists():
        content = README_PATH.read_text(encoding="utf-8")
    else:
        content = ""

    if README_BEGIN in content and README_END in content:
        pattern = re.compile(
            re.escape(README_BEGIN) + r".*?" + re.escape(README_END),
            re.DOTALL,
        )
        content = pattern.sub(new_block, content)
    else:
        # Append block at end
        content = content.rstrip() + "\n\n" + new_block + "\n"

    README_PATH.write_text(content, encoding="utf-8")
    _log.info("README.md updated locally")

    # --- optional remote push via API ---
    if token and repo_slug:
        try:
            from github import Github
            gh = Github(token)
            repo = gh.get_repo(repo_slug)
            remote_file = repo.get_contents("README.md", ref=repo.default_branch)
            repo.update_file(
                path="README.md",
                message="status: update discovery dashboard",
                content=content,
                sha=remote_file.sha,
                branch=repo.default_branch,
            )
            _log.info("README.md pushed to %s", repo_slug)
        except Exception:
            _log.warning("Remote README push failed:\n%s", traceback.format_exc())
            return False

    return True

# ---------------------------------------------------------------------------
# 3. Sync orchestrator (push pending + update readme)
# ---------------------------------------------------------------------------

def sync_pending(dry_run: bool = False) -> int:
    """Push any un-synced discoveries. Returns count pushed."""
    token = _github_token()
    slug = _repo_slug()
    if not token or not slug:
        _log.debug("GITHUB_TOKEN or GITHUB_REPO not set -- sync skipped")
        return 0

    ledger = _load_ledger()
    pushed_ids = set(ledger.get("pushed", []))
    discoveries = _load_discoveries()

    count = 0
    for d in discoveries:
        did = _discovery_id(d)
        if did in pushed_ids:
            continue
        if dry_run:
            _log.info("[dry-run] Would push: %s (%s)", did, d.get("match"))
            count += 1
            continue
        url = commit_discovery(d, token, slug)
        if url is not None:
            pushed_ids.add(did)
            count += 1

    ledger["pushed"] = list(pushed_ids)
    if not dry_run:
        _save_ledger(ledger)
        update_readme(token, slug)
        ledger["last_readme_update"] = datetime.now(timezone.utc).isoformat()
        _save_ledger(ledger)

    _log.info("Sync complete: %d discoveries pushed", count)
    return count

# ---------------------------------------------------------------------------
# 4. Non-blocking integration hook
# ---------------------------------------------------------------------------

_sync_lock = threading.Lock()
_sync_thread: threading.Thread | None = None


def maybe_sync(cycle: int, sync_every: int = 10) -> None:
    """Call from the generator main loop.  Fires a background sync every
    *sync_every* cycles.  If a previous sync is still running, silently skips.
    """
    global _sync_thread

    if cycle % sync_every != 0:
        return

    if _sync_lock.locked():
        _log.debug("Sync already in progress -- skipping cycle %d", cycle)
        return

    def _bg_sync() -> None:
        with _sync_lock:
            try:
                sync_pending()
            except Exception:
                _log.warning("Background sync failed:\n%s", traceback.format_exc())

    _sync_thread = threading.Thread(target=_bg_sync, daemon=True, name="gh_sync")
    _sync_thread.start()


def sync_blocking() -> int:
    """Synchronous version -- used by CLI and tests."""
    return sync_pending()

# ---------------------------------------------------------------------------
# 5. Daemon mode
# ---------------------------------------------------------------------------

def run_daemon(interval: int = 60) -> None:
    """Poll-and-push loop. Ctrl-C to stop."""
    _log.info("Daemon started (interval=%ds). Ctrl-C to stop.", interval)
    while True:
        try:
            sync_pending()
        except Exception:
            _log.warning("Daemon tick failed:\n%s", traceback.format_exc())
        time.sleep(interval)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Sync Ramanujan discoveries to GitHub",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sync", action="store_true",
                       help="Push pending discoveries and update README")
    group.add_argument("--update-readme", action="store_true",
                       help="Only refresh the local README status block")
    group.add_argument("--daemon", type=int, metavar="SECS",
                       help="Run background sync every SECS seconds")
    group.add_argument("--dry-run", action="store_true",
                       help="Show what would be pushed without pushing")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        _log.setLevel(logging.DEBUG)

    if args.sync:
        sync_blocking()
    elif args.update_readme:
        update_readme()
    elif args.daemon:
        run_daemon(args.daemon)
    elif args.dry_run:
        sync_pending(dry_run=True)


if __name__ == "__main__":
    _cli()
