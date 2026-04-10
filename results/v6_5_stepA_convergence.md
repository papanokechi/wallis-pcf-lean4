# Step A — V_quad island convergence check

_Timestamp: 2026-04-09 07:30:59_

- Spec: `{'family': 'fixed_alpha', 'a1': -15, 'a2': -1, 'b1': -4, 'b2': 0, 'c_value': '5/4', 'bridge': 1}`
- Reference depth: `3000`
- `|x_ref - 5*V_quad| = 0.002871901048069621902`
- Verdict: `stable-limit-offset`

| depth | digits vs ref | `|x_n - x_ref|` |
|---:|---:|---:|
| 100 | 298.612918 | `2.4382694358905577705e-299` |
| 200 | 589.999997 | `6.6892454244204699872e-596` |
| 500 | 999.0 | `0.0` |
| 1000 | 999.0 | `0.0` |
| 1500 | 999.0 | `0.0` |
| 2000 | 999.0 | `0.0` |

> The agreement with the depth-3000 reference is already very high at shallow depth, so the `0.002871901...` separation from `5*V_quad` is a real limiting gap, not a slow transient.
