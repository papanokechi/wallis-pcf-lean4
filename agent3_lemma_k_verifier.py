#!/usr/bin/env python3
from __future__ import annotations

"""Agent 3 numerical verification hook for the Lemma K / G-01 relay chain.

This is a zero-API companion script for external proof packets. It does not prove
Lemma K symbolically; instead it numerically checks the parts that an external AI
should specify explicitly:

1. conductor formula `N_k = 24 / gcd(k,24)`
2. representative Kloosterman sums against a Weil-type upper bound
3. monotone decay of a circle-method / Rademacher-style tail proxy

Usage:
    python agent3_lemma_k_verifier.py
"""

import cmath
import math
from dataclasses import dataclass


@dataclass(slots=True)
class LemmaKClaim:
    k: int = 5
    claimed_conductor: int = 24
    sample_m: int = 1
    sample_n: int = 1
    weil_constant: float = 1.0
    tail_cutoffs: tuple[int, ...] = (8, 16, 32, 64)


def expected_conductor(k: int) -> int:
    return 24 // math.gcd(k, 24)


def divisor_count(n: int) -> int:
    total = 0
    root = int(math.isqrt(n))
    for d in range(1, root + 1):
        if n % d == 0:
            total += 1 if d * d == n else 2
    return total


def inv_mod(a: int, m: int) -> int:
    return pow(a, -1, m)


def kloosterman_sum(m: int, n: int, c: int) -> complex:
    total = 0j
    for d in range(1, c + 1):
        if math.gcd(d, c) != 1:
            continue
        d_inv = inv_mod(d, c)
        phase = 2j * math.pi * (m * d + n * d_inv) / c
        total += cmath.exp(phase)
    return total


def weil_bound(m: int, n: int, c: int, constant: float = 1.0) -> float:
    return constant * divisor_count(c) * math.gcd(m, n, c) ** 0.5 * c ** 0.5


def tail_proxy(claim: LemmaKClaim, n0: int = 80) -> list[tuple[int, float]]:
    """A numerical proxy for tail decay.

    This is not a proof step; it is a sanity check that the claimed bound shape
    is at least numerically compatible with decreasing tail size as the cut-off
    moves outward.
    """
    out: list[tuple[int, float]] = []
    for cutoff in claim.tail_cutoffs:
        total = 0.0
        for c in range(cutoff, cutoff + 120):
            weight = weil_bound(claim.sample_m, claim.sample_n, c, claim.weil_constant)
            total += (weight / max(c**2, 1)) * math.exp(-math.pi * c / max(1.0, math.sqrt(n0)))
        out.append((cutoff, total))
    return out


def main() -> None:
    claim = LemmaKClaim()

    print("=== Agent 3 - Lemma K numerical hook ===")
    print(f"k = {claim.k}")
    print(f"claimed conductor = {claim.claimed_conductor}")
    print(f"expected conductor = {expected_conductor(claim.k)}")
    if claim.claimed_conductor != expected_conductor(claim.k):
        print("GAP: conductor mismatch")
        print("SEVERITY: blocks")
    else:
        print("GAP: none (conductor formula matches)")
        print("SEVERITY: cosmetic")

    print("\n-- Sample Weil-type checks --")
    for c in (5, 8, 12, 24, 25, 48):
        ks = kloosterman_sum(claim.sample_m, claim.sample_n, c)
        lhs = abs(ks)
        rhs = weil_bound(claim.sample_m, claim.sample_n, c, claim.weil_constant)
        verdict = "PASS" if lhs <= rhs * 1.0000001 else "FAIL"
        print(f"c={c:>2d}  |K(m,n;c)|={lhs:>10.6f}   Weil-bound={rhs:>10.6f}   {verdict}")

    print("\n-- Tail proxy trend --")
    previous = None
    for cutoff, value in tail_proxy(claim):
        trend = "start" if previous is None else ("down" if value <= previous else "up")
        print(f"cutoff={cutoff:>2d}   proxy_tail={value:.6e}   trend={trend}")
        previous = value

    print("\nBATON BACK:")
    print("Fill in the exact normalization constants from the external proof packet,")
    print("rerun this hook, and record any mismatch under `GAP:` / `SEVERITY:` in the SIARC log.")


if __name__ == "__main__":
    main()
