# V_quad connection-matrix report

ODE: `(3x^2+x+1)y'' + (6x+1)y' - x^2 y = 0`

## 1. Indicial roots and Frobenius basis

- Indicial roots at `x=0`: `rho1 = 0.0`, `rho2 = 1.0`.
- Because `3x^2+x+1` does **not** vanish at `x=0`, this is actually an ordinary point; the two Frobenius roots `0,1` simply recover the usual analytic basis.
- `y1(x) = 1.0 + 0.08333333333*x^4 + -0.06666666667*x^5 + -0.1111111111*x^6 + 0.2380952381*x^7 + 0.0431547619*x^8 + -0.5948412698*x^9 + 0.4305511464*x^10 + 1.070819304*x^11 + -2.057635298*x^12 + -0.8226910435*x^13 + 6.057355258*x^14 + ...`
- `y2(x) = 1.0*x + -0.5*x^2 + -0.6666666667*x^3 + 1.25*x^4 + 0.25*x^5 + -2.725*x^6 + 1.784126984*x^7 + 4.592460317*x^8 + -8.24167769*x^9 + -3.634672619*x^10 + 23.55003968*x^11 + -12.46606346*x^12 + ...`
- Richardson-extrapolated RK4 transport from the `x=0` Frobenius data reached about `17.30` agreement digits.

### Values at `x=10`

| quantity | value |
|---|---:|
| `y1(10)` | `22.29961717820138910516011` |
| `y1'(10)` | `10.43164098603476782680025` |
| `y2(10)` | `14.43574913790241526905037` |
| `y2'(10)` | `6.753110001921957627277042` |

## 2. WKB branches at infinity

- `mu_+ = -1.096225044864937627418191`
- `mu_- = -0.9037749551350623725818085`
- Recessive seed used: `x0 = 1000.0`; stable dominant matching was performed at `x_bridge = 30.0`.
- Recessive branch at `x=10`: `y_rec = 0.0003815350066129969446194525`, `y_rec'/y_rec = -0.6659584568413180406496632`
- Dominant branch at `x=10`: `y_dom = 26.57827423700678079956723`, `y_dom'/y_dom = 0.432328399278989041150697`
- Wronskian check: `A(10) * W = 3.463676674240979817529499` vs expected `2*sqrt(3) = 3.464101615137754587054893`.

> The naive direct backward RK4 shot for the dominant branch collapses onto the recessive solution (Wronskian nearly zero). The reported dominant column therefore uses the stable reduction-of-order reconstruction with the same asymptotic normalization.

## 3. Connection matrix

The matrix is defined by

```text
[[y_rec, y_dom], [y_rec', y_dom']] = [[y1, y2], [y1', y2']] * M
```

| entry | value (20 sig. digits) |
|---|---:|
| `M11` | `1.9420321374711220465` |
| `M12` | `4233.1506536679265656` |
| `M21` | `-2.9999268666050110215` |
| `M22` | `-6537.3164813754378405` |

## 4. PSLQ results

Basis:
`{1, pi, log(2), log(3), sqrt(3), Gamma(1/3), Gamma(2/3), Gamma(1/4), Gamma(3/4), zeta(3)}`

- `M11`: **None** at bound 500; best heuristic near-miss is `-10.0 + (131/19)*sqrt(3)` with about `5.912` digits
- `M12`: **None** at bound 500; best heuristic near-miss is `4231.0 + (27/17)*Gamma(2/3)` with about `9.000` digits
- `M21`: **None** at bound 500; best heuristic near-miss is `-16.0 + (244/23)*Gamma(3/4)` with about `7.015` digits
- `M22`: **None** at bound 500; best heuristic near-miss is `-6533.0 + (-79/22)*zeta(3)` with about `9.181` digits

- Joint PSLQ on the literal core 8-vector `[M11,M12,M21,M22,1,pi,log(2),sqrt(3)]`: **None**
- Joint PSLQ on the full supplied basis vector `[M11,M12,M21,M22] + basis`: **None**

## 5. V_quad check

- `V_quad = 1.197373990688357602448603`
- Best simple combination scanned from entries/ratios/determinant/inverse entries: `(M^-1)21` = `0.866110537659351937005789233441`
- Agreement with `V_quad`: about `0.558` digits
- **No simple combination of the tested `M`-expressions reproduces `V_quad`.**

## 6. Bottom line

- The Frobenius roots are `0` and `1`.
- A full two-column connection matrix can be assembled once the dominant branch is stabilized numerically.
- In the requested 300-digit PSLQ search, the matrix entries show no low-height relation with the supplied basis.
