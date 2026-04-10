# Design Note: Ramanujan Fast Agent Optimization Phase 2

## Objective
Reduce wall-clock discovery latency for Ramanujan-style generalized continued fractions (GCFs) while preserving discovery parity.

## Key implementations
- **Adaptive `n_terms` short-circuit**: Added a 25→50 term convergence checkpoint with a conservative death criterion (`ADAPTIVE_PROGRESS_RATIO = 0.20`) so weak specs are rejected before full high-precision evaluation.
- **Heuristic PSLQ gating**: Added primary-target-first search, cheap linear-signal prefilters, and degree-2 gating to bypass wasteful PSLQ calls.
- **Parallel architecture**: Added `ProcessPoolExecutor` support with Windows-safe picklable workers, explicit precision/config propagation, pool reuse across iterations, and main-process novelty deduplication.
- **Elite pool management**: Replaced full-pool sorting with a pruned elite pool strategy to keep generator overhead bounded over long runs.
- **Symbolic simplifier**: Added a closed-form interpretation layer using exact rational extraction, `mpmath.identify`, and `SymPy` relation solving so discoveries can surface as expressions like `4/pi` instead of raw coefficient tuples.
- **Live SIARC relay integration**: The fast kernel now feeds `siarc_v6_standalone.py` directly via `RamanujanRelaySeeder`, carrying source labels (`live_kernel` vs `seed_pool`) and symbolic metadata in-process.
- **Reproducibility & observability**: Added `--seed`, `--json-summary`, profiling flags, benchmark CSV/JSON output, HTML summaries, and structured SIARC-friendly programmatic APIs.

## Verified results
- **Sequential baseline** (`zeta3`, `10 iters`, `batch 8`): about `15.178s` and `~5.27 GCF/s`
- **After PSLQ + pool/eval improvements**: about `4.800s` and `~16.67 GCF/s` on the same seeded workload
- **Adaptive gate speedup**: confirmed weak-spec rejection around `0.0006s` versus `0.0145s` for a raw full evaluation (`~24×` faster per rejected spec)
- **Large-batch parallel benchmark** (`zeta3:50:64`, seed `123`):
  - `workers=1`: `132.335s`, `24.322 GCF/s`, `59` novel finds
  - `workers=4`, `executor=process`: `57.014s`, `56.837 GCF/s`, `59` novel finds
- **Scaling sweep** (`zeta3`, `5 iters`, `batch 128`, seed `123`, process backend):
  - `workers=1`: `129.18s`, `5.246 GCF/s`
  - `workers=2`: `38.401s`, `17.868 GCF/s` (`3.41×`)
  - `workers=4`: `30.844s`, `23.999 GCF/s` (`4.58×`, best throughput)
  - `workers=8`: `43.005s`, `18.246 GCF/s` (drop-off from process overhead)
- **SIARC live-relay smoke test**: `siarc_v6_standalone.py --iters 1 --fast-mode --quiet` completed with `SIARC_EXIT=0`, `Ramanujan relays: 2`, and a verified symbolic live relay (`4/pi` for `GCF_93A50D98`)
- **Integrity check**: discovery retention remained stable on seeded benchmarks and the SIARC live path remained healthy after each optimization stage

## Current default policy
- `--workers 0` → auto-select from a measured `1 / 2 / 4` heuristic, capped at **4 workers** on this Windows machine
- `--executor process` → recommended default on Windows
- Small jobs (`batch < 10` or `batch * iters < 200`) automatically run sequentially
- Effective batch size auto-scales to `workers * 8` when parallel mode is active

## SIARC integration path
The fast agent is now usable as an in-process search kernel via:

```python
from siarc_ramanujan_adapter import RamanujanSearchSpec, run_ramanujan_search

result = run_ramanujan_search(
    RamanujanSearchSpec(target="zeta3", iters=50, batch=64, workers=0)
)
```

This returns structured `summary` and `discoveries` payloads directly, avoiding JSON handoffs.

## Stable build commands (verified)
```powershell
# Fast kernel smoke run
python ramanujan_agent_v2_fast.py --iters 2 --batch 16 --target zeta3 --seed 7 --workers 0 --executor process --json-summary ramanujan_adaptive_smoke.json

# SIARC live-relay smoke run
python siarc_v6_standalone.py --iters 1 --fast-mode --quiet

# Worker scaling sweep
python benchmark_ramanujan_agent.py --target zeta3 --iters 5 --batch 128 --workers 1,2,4,8 --seed 123 --trials 1 --executor process --json scaling_results.json --csv scaling_results.csv
```

## Phase 3 kickoff: multi-target sweep
A first Phase 3 sweep runner is now available via:

```powershell
python multi_target_ramanujan_sweep.py --targets zeta3,pi,e,log2 --iters 2 --batch 16 --seed 123 --quiet --json phase3_multi_target.json --csv phase3_multi_target.csv
```

Verified kickoff result (`SWEEP_EXIT=0`):
- `8` total discoveries across `zeta3`, `pi`, `e`, and `log2`
- `1` shared structural pattern: `adeg=2|bdeg=1|mode=backward|order=0`
- Per-target counts from `phase3_multi_target.csv`:
  - `zeta3`: `3` discoveries
  - `pi`: `1` discovery
  - `e`: `2` discoveries
  - `log2`: `2` discoveries

Verified wide sweep (`WIDE_EXIT=0`):
- command: `python multi_target_ramanujan_sweep.py --targets zeta3,pi,e,log2,catalan,zeta2 --iters 4 --batch 32 --seed 123 --quiet --json phase3_multi_target_wide.json --csv phase3_multi_target_wide.csv`
- `31` total discoveries across `6` targets in `71.912s`
- `5` shared structural signatures across the target family
- Per-target counts from `phase3_multi_target_wide.csv`:
  - `zeta3`: `4` discoveries
  - `pi`: `5` discoveries
  - `e`: `7` discoveries
  - `log2`: `4` discoveries
  - `catalan`: `6` discoveries
  - `zeta2`: `5` discoveries
- Strongest shared signature in the wide sweep:
  - `adeg=2|bdeg=1|mode=backward|order=0` across `catalan`, `e`, `log2`, `pi`, `zeta2`, and `zeta3`

## Genetic Priority Map (verified)
The generator now supports a **Genetic Priority Map** that biases random search toward fertile structural signatures while still preserving exploration:
- default weighted family: `adeg=2|bdeg=1|mode=backward|order=0` gets roughly **50%** of the priority-family mass
- successful discoveries increase the weight of their signature automatically
- discoveries with simple `closed_form` output are promoted into `ramanujan_persistent_seeds.json`
- multi-target sweeps now cross-pollinate learned signatures into later target runs

Verified short genetic sweep (`GENETIC_EXIT=0`):
- command: `python multi_target_ramanujan_sweep.py --targets pi,catalan,zeta2 --iters 1 --batch 16 --seed 123 --quiet --json phase3_genetic_test.json --csv phase3_genetic_test.csv`
- `4` discoveries in `11.0s`
- learned priority map surfaced:
  - `adeg=2|bdeg=3|mode=backward|order=0 -> 1.05`
  - `adeg=1|bdeg=3|mode=backward|order=0 -> 0.35`
- persistent promotions recorded in `phase3_genetic_test.csv`:
  - `pi`: `1`
  - `catalan`: `1`
  - `zeta2`: `2`

## Phase 3 recommendations
1. **Multi-target sweep**: expand the target list and batch sizes to surface stronger shared GCF families across constants.
2. **Evolutionary seed tuning**: now that the priority map is active, compare learned-priority sweeps against the documented wide-sweep baseline.
3. **Math-paper summarizer**: let a downstream SIARC agent turn `closed_form` discoveries into draft LaTeX theorem notes and experiment summaries.

## Status
**Phase 2 is stable and complete, and Phase 3 now includes live genetic search biasing**: the kernel is fast, instrumented, symbolically interpretable, live-wired into SIARC, capable of cross-target discovery sweeps, and able to learn from successful signature families.
