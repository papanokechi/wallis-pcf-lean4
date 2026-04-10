# SIARC v6.4 Handoff Note

**Date:** 2026-04-09  
**Branch state:** `1060` SIARC iterations on the `VQUAD_TRANSCENDENCE` track  
**Primary objective:** push past the Wallis/PCF noise floor with a high-depth verification pass

## 1. Technical Optimization Applied

- Installed `numba` into the workspace `.venv`.
- Updated `_third_order_wallis_scan.py` to use optional `@njit(cache=True)` acceleration for the inner recurrence basis builder.
- Preserved the NumPy fallback so the scan remains portable if JIT becomes unavailable.
- The scan now records its active acceleration mode in the JSON protocol block.

## 2. Verified Commands

### Install / acceleration path
```bash
python -m pip install numba
```

### High-depth deep scan
```bash
python _third_order_wallis_scan.py --workers 8 --range 3 --depth 250 --verify-top 5 --verify-dps 300 --verify-depths 90 110 140 180 250 --guard-every 1
```

### Direct re-check of the former 0.19d candidate
```bash
python -c "from _third_order_wallis_scan import Candidate,_verify_candidate,_make_target_grid; ..."
```

## 3. Main Findings

| Check | Result |
| --- | --- |
| Acceleration mode | `Numba @njit` active |
| CPU usage during falling scan | `100.0%` |
| RAM usage during falling scan | `92.1%` to `92.6%` |
| ThermalGuard status | cooldown condition triggered on the falling-family pass |
| Best verified candidate at depth 250 | `0.00d` |
| Previous `0.19d` near-match | **collapsed to `0.00d`** |
| New teleport events during verification | `none` |

## 4. Clarification of the Former 0.19d Candidate

The previously leading near-match

- family: `power`
- tuple: `(alpha, beta, gamma, delta) = (1, -2, -3, -1)`

**does not stabilize** at higher depth. At verification depths `90, 110, 140, 180, 250` the ratio values become:

```text
-0.09554640742673444
-1.89344262295082
-1.25
-1.458333333333333
 3.125
```

This yields `verified_digits = 0.00` at `300` dps, so the candidate is now classified as **noise / false structure**, not a viable Wallis-type identity.

## 5. Deep-Scan Interpretation

- The depth-250 run filtered out the old `0.19d` class entirely.
- No candidate in the scanned `[-3,3]^4` box stabilizes above `10` digits.
- The Wallis-type box remains negative at this precision/depth.
- The practical bottleneck is now **structural expressiveness**, not raw CPU availability.

## 6. Recommended Next Step

Shift v6.4+ work from broad box expansion toward one of:

1. **symmetry-reduced targeted families** with analytic priors,
2. **higher-order invariants / recurrence fingerprints** before PSLQ matching,
3. **proof-oriented filtering** for Vquad-related structures instead of deeper brute-force scans in the same 4-parameter box.

## 7. Files of Record

- `results/third_order_wallis_scan.json`
- `siarc_v6_final_portfolio.md`
- `siarc_v6_4_handoff_note.md`
- `_third_order_wallis_scan.py`
