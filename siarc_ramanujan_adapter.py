#!/usr/bin/env python3
"""Lightweight SIARC-facing adapter for `ramanujan_agent_v2_fast.py`.

This lets the fast Ramanujan search engine act as a high-throughput search
kernel that returns structured discoveries directly to an orchestrator.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from ramanujan_agent_v2_fast import run_search_kernel


@dataclass
class RamanujanSearchSpec:
    target: str = "zeta3"
    iters: int = 50
    batch: int = 64
    prec: int = 300
    workers: int = 0            # 0 = auto
    executor: str = "process"  # process is the verified default on Windows
    quiet: bool = True
    seed: int | None = None
    seed_file: str | None = None
    use_llm: bool = False
    use_lirec: bool = False
    priority_map: dict[str, float] = field(default_factory=dict)
    deep_mode: bool = False


@dataclass
class MultiTargetSweepSpec:
    targets: list[str] = field(default_factory=lambda: ["zeta3", "pi", "e", "log2"])
    iters: int = 3
    batch: int = 32
    prec: int = 300
    workers: int = 0
    executor: str = "process"
    quiet: bool = True
    seed: int | None = None
    seed_file: str | None = None
    use_llm: bool = False
    use_lirec: bool = False
    priority_map: dict[str, float] = field(default_factory=dict)
    cross_pollinate: bool = True
    promotion_boost: float = 0.35


def run_ramanujan_search(spec: RamanujanSearchSpec | None = None) -> dict[str, Any]:
    """Run the fast Ramanujan agent and return a structured payload.

    The returned dict is SIARC-friendly and avoids file-based handoffs.
    """
    spec = spec or RamanujanSearchSpec()
    result = run_search_kernel(
        target=spec.target,
        iters=spec.iters,
        batch=spec.batch,
        prec=spec.prec,
        workers=spec.workers,
        executor=spec.executor,
        quiet=spec.quiet,
        use_llm=spec.use_llm,
        use_lirec=spec.use_lirec,
        seed=spec.seed,
        seed_file=spec.seed_file,
        priority_map=spec.priority_map,
        deep_mode=spec.deep_mode,
    )
    return {
        "search_spec": asdict(spec),
        "summary": result["summary"],
        "discoveries": result["discoveries"],
    }


def discoveries_as_siarc_payload(spec: RamanujanSearchSpec | None = None) -> list[dict[str, Any]]:
    """Convert discoveries into a simple SIARC relay payload list."""
    result = run_ramanujan_search(spec)
    payload = []
    for discovery in result["discoveries"]:
        enrichment = discovery.get("enrichment") or {}
        payload.append({
            "source": "ramanujan_agent_v2_fast",
            "kind": "ramanujan_discovery",
            "target": discovery.get("constant"),
            "formula": discovery.get("formula"),
            "closed_form": enrichment.get("closed_form"),
            "closed_form_source": enrichment.get("closed_form_source"),
            "identify_ratio": enrichment.get("identify_ratio"),
            "cf_approx": discovery.get("cf_approx"),
            "conv_digits": discovery.get("conv_digits"),
            "precision_dp": discovery.get("precision_dp"),
            "spec": discovery.get("spec"),
            "enrichment": enrichment,
        })
    return payload


def _poly_degree(coeffs: list[Any] | None) -> int:
    coeff_list = list(coeffs or [])
    for idx in range(len(coeff_list) - 1, -1, -1):
        if coeff_list[idx] != 0:
            return idx
    return 0


def _structural_signature(discovery: dict[str, Any]) -> str:
    spec = discovery.get("spec") or {}
    alpha = spec.get("alpha") or []
    beta = spec.get("beta") or []
    mode = spec.get("mode", "backward")
    order = spec.get("order", 0)
    return (
        f"adeg={_poly_degree(alpha)}|"
        f"bdeg={_poly_degree(beta)}|"
        f"mode={mode}|order={order}"
    )


def run_multi_target_sweep(spec: MultiTargetSweepSpec | None = None) -> dict[str, Any]:
    """Cycle the fast kernel across multiple constants and aggregate findings."""
    spec = spec or MultiTargetSweepSpec()
    targets = [str(t).strip() for t in spec.targets if str(t).strip()]

    per_target: list[dict[str, Any]] = []
    pattern_targets: dict[str, set[str]] = defaultdict(set)
    pattern_examples: dict[str, dict[str, Any]] = {}
    # Per-target learned maps instead of one shared map
    learned_per_target: dict[str, dict[str, float]] = {
        t: dict(spec.priority_map or {}) for t in targets
    }
    total_discoveries = 0
    total_novel = 0
    total_elapsed = 0.0

    for idx, target in enumerate(targets):
        search_seed = None if spec.seed is None else spec.seed + idx
        priority_map_used = dict(learned_per_target.get(target, {}))
        result = run_ramanujan_search(
            RamanujanSearchSpec(
                target=target,
                iters=spec.iters,
                batch=spec.batch,
                prec=spec.prec,
                workers=spec.workers,
                executor=spec.executor,
                quiet=spec.quiet,
                seed=search_seed,
                seed_file=spec.seed_file,
                use_llm=spec.use_llm,
                use_lirec=spec.use_lirec,
                priority_map=priority_map_used,
            )
        )
        discoveries = result.get("discoveries", [])
        summary = result.get("summary", {})
        stats = summary.get("stats", {})
        signature_counts: dict[str, int] = defaultdict(int)

        total_discoveries += len(discoveries)
        total_novel += int(stats.get("novel", 0) or 0)
        total_elapsed += float(stats.get("elapsed_seconds", 0.0) or 0.0)

        for discovery in discoveries:
            signature = _structural_signature(discovery)
            signature_counts[signature] += 1
            pattern_targets[signature].add(target)
            pattern_examples.setdefault(signature, {
                "target": target,
                "spec_id": (discovery.get("spec") or {}).get("spec_id"),
                "formula": discovery.get("formula"),
                "closed_form": (discovery.get("enrichment") or {}).get("closed_form"),
            })

        # Update only this target's learned map
        for signature, count in signature_counts.items():
            tmap = learned_per_target.setdefault(target, {})
            tmap[signature] = tmap.get(signature, 0.0) + spec.promotion_boost * max(1, count)

        per_target.append({
            "target": target,
            "seed": search_seed,
            "summary": summary,
            "discoveries": discoveries,
            "discovery_count": len(discoveries),
            "novel_count": int(stats.get("novel", 0) or 0),
            "elapsed_seconds": float(stats.get("elapsed_seconds", 0.0) or 0.0),
            "priority_map_used": priority_map_used,
            "signature_counts": dict(signature_counts),
        })

    # Cross-pollinate only signatures that appear in 3+ targets consistently
    if spec.cross_pollinate:
        for signature, hit_targets in pattern_targets.items():
            if len(hit_targets) >= 3:
                for t in targets:
                    if t not in hit_targets:
                        tmap = learned_per_target.setdefault(t, {})
                        tmap[signature] = tmap.get(signature, 0.0) + spec.promotion_boost

    # Flatten for backward-compat aggregate output
    merged_learned: dict[str, float] = {}
    for tmap in learned_per_target.values():
        for sig, w in tmap.items():
            merged_learned[sig] = max(merged_learned.get(sig, 0.0), w)

    shared_patterns = []
    for signature, hit_targets in sorted(pattern_targets.items()):
        if len(hit_targets) < 2:
            continue
        shared_patterns.append({
            "signature": signature,
            "targets": sorted(hit_targets),
            "example": pattern_examples.get(signature, {}),
        })

    return {
        "sweep_spec": asdict(spec),
        "targets": per_target,
        "aggregate": {
            "target_count": len(targets),
            "total_discoveries": total_discoveries,
            "total_novel": total_novel,
            "elapsed_seconds": round(total_elapsed, 3),
            "shared_pattern_count": len(shared_patterns),
            "learned_priority_map": merged_learned,
            "learned_per_target": {t: dict(m) for t, m in learned_per_target.items()},
        },
        "shared_patterns": shared_patterns,
    }


def multi_target_discoveries_as_siarc_payload(spec: MultiTargetSweepSpec | None = None) -> list[dict[str, Any]]:
    """Flatten a multi-target sweep into a single SIARC-friendly payload list."""
    result = run_multi_target_sweep(spec)
    payload: list[dict[str, Any]] = []
    for target_block in result.get("targets", []):
        for discovery in target_block.get("discoveries", []):
            enrichment = discovery.get("enrichment") or {}
            payload.append({
                "source": "ramanujan_agent_v2_fast",
                "kind": "ramanujan_discovery",
                "sweep_target": target_block.get("target"),
                "target": discovery.get("constant"),
                "formula": discovery.get("formula"),
                "closed_form": enrichment.get("closed_form"),
                "identify_ratio": enrichment.get("identify_ratio"),
                "cf_approx": discovery.get("cf_approx"),
                "precision_dp": discovery.get("precision_dp"),
                "conv_digits": discovery.get("conv_digits"),
                "pattern_signature": _structural_signature(discovery),
                "spec": discovery.get("spec"),
                "enrichment": enrichment,
            })
    return payload


if __name__ == "__main__":
    payload = run_ramanujan_search(RamanujanSearchSpec())
    print(f"Discoveries: {len(payload['discoveries'])}")
    print(f"Target: {payload['summary']['target']}")
