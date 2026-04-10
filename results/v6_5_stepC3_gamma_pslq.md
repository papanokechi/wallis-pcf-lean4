# Step C.4 — Gamma-basis PSLQ for the asymptotic coefficient C

_Timestamp: 2026-04-09 08:42:31_

- Working precision: `350 dps`
- Tail-fit exponent used in `C` estimation: `1.484289`
- `C ≈ 0.0266831927750349195971324434140115045011`
- `C*pi/Gamma(1/4)^2 ≈ 0.00637713361381469990764041346988`
- `C*pi*sqrt(2)/Gamma(1/4)^2 ≈ 0.00901862884572209614120630518452`
- `C/zeta(3)^(1/4) ≈ 0.0254833510585776035289581752332`
- `C/zeta(3)^(3/4) ≈ 0.0232430985538043000145617931209`

## Tail data used for the fit

| m | epsilon(m) | m^(3/2) epsilon(m) |
|---:|---:|---:|
| 5 | `0.00232355557538777757968649117787` | `0.0259781410803285409559243008679` |
| 6 | `0.00177059813623651407374538184917` | `0.0260223718398141211842889689028` |
| 7 | `0.00141086547437232124305271408485` | `0.0261295942498943437494148178614` |
| 8 | `0.00115957150576333795747128124824` | `0.0262381079998704672236202249777` |
| 9 | `0.000975048959993094151692536514698` | `0.0263263219198135420956984858968` |
| 10 | `0.000834452160606015516471712232549` | `0.0263876942596363936360061197203` |
| 11 | `0.000724221913552673839977902697127` | `0.0264216958742816582345624049986` |
| 12 | `0.000635811498184810414005365703557` | `0.0264301876534218880155790286208` |
| 13 | `0.000563572696748106283905501547834` | `0.0264158733224985916381712338072` |
| 14 | `0.000503627470949225169906146957238` | `0.0263816202560322570808083830722` |
| 15 | `0.00045322796826536481518715788248` | `0.0263301655969077232876923090305` |

## PSLQ attempts

| target | basis | found | maxcoeff | residual | relation |
|---|---|---:|---:|---:|---|
| C | Gamma basis | False | 5000 | `n/a` | `none up to bound` |
| C/(zeta3^(1/4)) | Gamma+zeta basis | False | 5000 | `n/a` | `none up to bound` |
| C/(zeta3^(3/4)) | Gamma+zeta basis | False | 5000 | `n/a` | `none up to bound` |
| C*pi/Gamma14^2 | Rationalized ratio basis | False | 5000 | `n/a` | `none up to bound` |
| C*pi*sqrt2/Gamma14^2 | Rationalized ratio basis | False | 5000 | `n/a` | `none up to bound` |

> No low-height Gamma/Apéry-style relation was detected for `C` in the tested basis up to coefficient bound `5000`. This is strong negative evidence against the simplest `Gamma(1/4)` normalizations, though a subtler higher-weight expression is still possible.
