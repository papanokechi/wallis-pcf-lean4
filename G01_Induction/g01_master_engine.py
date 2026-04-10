"""Thin wrapper for the existing workspace G-01 engine.

The canonical implementation currently lives in `g01_ladder.py`. This file is a
stable hand-off point for the induction folder structure suggested in the log.
"""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    print(
        "Use `g01_ladder.py` as the current master engine. "
        f"This wrapper exists to anchor the G01_Induction scaffold at {Path(__file__).resolve().parent}."
    )


if __name__ == "__main__":
    main()
