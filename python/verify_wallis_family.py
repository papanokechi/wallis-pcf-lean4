#!/usr/bin/env python3
"""High-precision numerical certification for the Wallis PCF family.

Example:
    python python/verify_wallis_family.py --dps 1100 --depth 9000 --max-m 20 \
        --json results/wallis_family_certification.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mpmath import mp


def eval_wallis_pcf(m: int, depth: int) -> mp.mpf:
    """Evaluate S^(m) by backward recurrence."""
    tail = mp.mpf("0")
    for n in range(depth, 0, -1):
        a_n = -n * (2 * n - (2 * m + 1))
        b_n = 3 * n + 1
        tail = a_n / (b_n + tail)
    return 1 + tail


def target_value(m: int) -> mp.mpf:
    """Closed form 2^(2m+1)/(pi * binomial(2m,m))."""
    return mp.mpf(2) ** (2 * m + 1) / (mp.pi * mp.binomial(2 * m, m))


def certified_digits(value: mp.mpf, target: mp.mpf) -> str:
    err = abs(value - target)
    if err == 0:
        return f">={mp.dps}"
    return str(int(mp.floor(-mp.log10(err))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dps", type=int, default=1100, help="working precision")
    parser.add_argument("--depth", type=int, default=9000, help="backward-recurrence depth")
    parser.add_argument("--max-m", type=int, default=20, help="verify m = 0, ..., max-m")
    parser.add_argument("--min-digits", type=int, default=1000, help="required certification threshold")
    parser.add_argument("--json", type=Path, default=None, help="optional JSON export path")
    args = parser.parse_args()

    mp.dps = args.dps
    rows: list[dict[str, str | int]] = []
    ok = True

    print(f"Verifying Wallis PCF family with dps={args.dps}, depth={args.depth}, max_m={args.max_m}")
    for m in range(args.max_m + 1):
        value = eval_wallis_pcf(m, args.depth)
        target = target_value(m)
        err = abs(value - target)
        digits = certified_digits(value, target)
        digits_int = args.dps if digits.startswith(">=") else int(digits)
        ok = ok and digits_int >= args.min_digits
        print(
            f"m={m:2d}  value={mp.nstr(value, 25)}  target={mp.nstr(target, 25)}  "
            f"digits={digits}"
        )
        rows.append(
            {
                "m": m,
                "value": mp.nstr(value, 50),
                "target": mp.nstr(target, 50),
                "abs_error": mp.nstr(err, 20),
                "certified_digits": digits,
            }
        )

    payload = {
        "dps": args.dps,
        "depth": args.depth,
        "max_m": args.max_m,
        "min_digits": args.min_digits,
        "verified": ok,
        "results": rows,
    }

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved JSON report to {args.json}")

    if ok:
        print(f"\nAll cases met the {args.min_digits}-digit threshold.")
        return 0

    print(f"\nAt least one case fell below the {args.min_digits}-digit threshold.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
