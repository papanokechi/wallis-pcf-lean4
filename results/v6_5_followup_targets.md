# v6.5 Follow-up Execution

_Timestamp: 2026-04-09 07:34:10_

## 1. V_quad island depth push

- Spec: `{'family': 'fixed_alpha', 'a1': -15, 'a2': -1, 'b1': -4, 'b2': 0, 'c_value': '5/4', 'bridge': 1}`

| m | depth | digits from previous | digits/term | `|x-5V_quad|` |
|---:|---:|---:|---:|---:|
| 0 | 500 | 0.0 | 0.0 | `0.00287190104807` |
| 0 | 1000 | 999.0 | 1.998 | `0.00287190104807` |
| 0 | 2000 | 999.0 | 0.999 | `0.00287190104807` |
| 1 | 500 | 0.0 | 0.0 | `4.09096487392` |
| 1 | 1000 | 5.738523 | 0.01147705 | `4.09096669982` |
| 1 | 2000 | 5.919913 | 0.00591991 | `4.09096549732` |
| 1 | 5000 | 5.834359 | 0.00194479 | `4.09096403298` |
| 2 | 500 | 0.0 | 0.0 | `7.97506000173` |
| 2 | 1000 | 999.0 | 1.998 | `7.97506000173` |
| 2 | 2000 | 999.0 | 0.999 | `7.97506000173` |
| 3 | 500 | 0.0 | 0.0 | `11.9816162894` |
| 3 | 1000 | 999.0 | 1.998 | `11.9816162894` |
| 3 | 2000 | 999.0 | 0.999 | `11.9816162894` |

### Step A: convergence to the depth-3000 reference at `m=0`

| depth | digits vs reference | `|x_n - x_ref|` |
|---:|---:|---:|
| 100 | 298.612918 | `2.4382694358905577705e-299` |
| 200 | 589.999997 | `6.6892454244204699872e-596` |
| 500 | 590.0 | `0.0` |
| 1000 | 590.0 | `0.0` |
| 1500 | 590.0 | `0.0` |
| 2000 | 590.0 | `0.0` |

## 2. Apéry basin PSLQ / sequence check

- Spec: `{'family': 'fixed_alpha', 'a1': -15, 'a2': 0, 'b1': -4, 'b2': 0, 'c_value': '1', 'bridge': 0}`
- PSLQ: `-1*x + 6*(1/zeta3) + 0 = 0`
- PSLQ residual: `0.0`
- kernel matches standard Apéry coefficients: `True`
- direct `q_n = A_n` termwise match: `False`
- direct `p_n = B_n` termwise match: `False`

## 3. Möbius extension (height 3)

- `(-2m+3)/(1m+2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.219477` at `m=2`
- `(-1m+3)/(-3m+2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.219477` at `m=2`
- `(1m-3)/(3m-2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.219477` at `m=2`
- `(2m-3)/(-1m-2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.219477` at `m=2`
- `(-3m-3)/(-1m-2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.167399` at `m=1`
- `(-1m-3)/(0m-2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.167399` at `m=1`
- `(1m+3)/(0m+2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.167399` at `m=1`
- `(3m+3)/(1m+2)` → zeta digits at `m=0`: `3.230115`, best V_quad overlap: `2.167399` at `m=1`

## Conclusion

- The Apéry-basin hit is confirmed: the kernel is exactly the standard Apéry `-n^6` / `(2n+1)(17n^2+17n+5)` kernel, and PSLQ recovers a linear relation with `1/zeta(3)`. The raw convergent sequences are not termwise identical to the classical Apéry A/B tables, so this behaves as the reciprocal/Pincherle-side realization rather than a literal A/B copy. Step A shows the V_quad-island value at m=0 already agrees with the depth-3000 reference to at least 298.612918 digits across the probe depths, so the persistent offset of about 0.002871901 from 5*Vquad is a real limiting gap rather than a pre-asymptotic transient.
