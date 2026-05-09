#!/usr/bin/env python3
"""
emit_agent_cards.py

Emit `.github/agents/{name}.agent.md` cards from `.fleet.yaml`, one per
agent, per the SIARC fleet/v1 schema's `setup.bootstrap.on_first_run`
directive.

Each card has:
  - YAML frontmatter with the keys named in
    `setup.bootstrap.frontmatter_keys`
  - The agent's `instructions:` string as the markdown body

Idempotent: overwrites with bytewise-stable output (sorted keys + LF
newlines + trailing newline). Re-running with no YAML edits produces
no diff.

Usage:
  python scripts/emit_agent_cards.py [--config .fleet.yaml]
                                     [--target-dir .github/agents]
                                     [--check]

`--check` (CI-style): do not write; exit 1 if outputs would differ
from existing files.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml


def load_fleet_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_card(agent: dict, frontmatter_keys: list[str]) -> str:
    front = {}
    for key in frontmatter_keys:
        if key in agent:
            front[key] = agent[key]
    fm_yaml = yaml.safe_dump(
        front,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )
    body = (agent.get("instructions") or "").rstrip() + "\n"
    return f"---\n{fm_yaml}---\n\n{body}"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=".fleet.yaml")
    parser.add_argument("--target-dir", default=None,
                        help="override setup.bootstrap.target_dir")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if any card would change on disk")
    args = parser.parse_args()

    cfg_path = Path(args.config).resolve()
    cfg = load_fleet_config(cfg_path)

    setup = (cfg.get("setup") or {}).get("bootstrap") or {}
    target_dir = Path(args.target_dir or setup.get("target_dir", ".github/agents"))
    naming = setup.get("naming", "{name}.agent.md")
    fm_keys = setup.get("frontmatter_keys",
                        ["name", "description", "model", "tools",
                         "triggers", "allowed_files"])

    target_dir.mkdir(parents=True, exist_ok=True)

    agents = cfg.get("agents") or []
    if not agents:
        print("ERROR: no agents defined in", cfg_path, file=sys.stderr)
        return 2

    drift = False
    written = []
    for agent in agents:
        name = agent.get("name")
        if not name:
            print("WARN: skipping agent without name:", agent, file=sys.stderr)
            continue
        out = target_dir / naming.format(name=name)
        rendered = render_card(agent, fm_keys).encode("utf-8")
        existing = out.read_bytes() if out.exists() else b""
        if rendered == existing:
            status = "unchanged"
        else:
            if args.check:
                drift = True
                status = "DRIFT"
            else:
                out.write_bytes(rendered)
                status = "wrote" if not existing else "updated"
        written.append({
            "name": name,
            "path": str(out),
            "bytes": len(rendered),
            "sha256": sha256_bytes(rendered),
            "status": status,
        })

    print(f"# emit_agent_cards: {len(written)} agents -> {target_dir}")
    print(f"# config={cfg_path}")
    print(f"{'STATUS':10s} {'BYTES':>7s} {'SHA256':16s} NAME")
    for w in written:
        print(f"{w['status']:10s} {w['bytes']:7d} {w['sha256'][:16]} {w['name']}")

    if args.check and drift:
        print("CHECK FAILED: cards differ from .fleet.yaml output", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
