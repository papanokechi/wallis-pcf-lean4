# Step B — PSLQ identification of the V_quad island

_Timestamp: 2026-04-09 07:36:10_

- Spec: `{'family': 'fixed_alpha', 'a1': -15, 'a2': -1, 'b1': -4, 'b2': 0, 'c_value': '5/4', 'bridge': 1}`
- Working precision: `250 dps`
- Depth: `3000`
- Island value `x`: `5.989741854489857634145018295720925846953973777780237906373576722897338284549933`
- Gap `x - 5*V_quad`: `0.00287190104806962190200219603489`
- `mp.identify(x)`: `None`
- `mp.identify(gap)`: `None`
- CF terms for `x`: `[5, 1, 96, 2, 14, 1, 1, 1, 12, 8, 3, 1, 1, 2, 6, 2, 2, 1, 3, 2]`
- CF terms for `|gap|`: `[0, 348, 4, 1, 27, 1, 1, 8, 9, 2, 1, 17, 3, 1, 3, 1, 1, 1, 16, 4]`

## PSLQ attempts

| target | tier | found | maxcoeff tested | residual | relation |
|---|---|---:|---:|---:|---|
| x | Tier 1 | False | 1000 | `n/a` | `none up to bound` |
| x | Tier 2 | False | 1000 | `n/a` | `none up to bound` |
| x | Tier 3 | False | 1000 | `n/a` | `none up to bound` |
| gap | Tier 1 | False | 1000 | `n/a` | `none up to bound` |
| gap | Tier 2 | False | 1000 | `n/a` | `none up to bound` |
| gap | Tier 3 | False | 1000 | `n/a` | `none up to bound` |

> No small-coefficient PSLQ relation was found for the island value or the gap in the tested bases. This is strong negative evidence against a simple low-weight expression in `V_quad`, `ζ(3)`, `π`, `log(2)`, `Catalan`, or the tested algebraic variants.
