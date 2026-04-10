# Three-basis confluent-Heun/Stokes search for V_quad

- Generated: 2026-04-10 10:59:34
- Precision: 120 dps
- V_quad: `1.1973739906883576024486032199372063297042707032314`
- Triple count: `360`

## Confluent-Heun proxy diagnostics

- `z0 = (0.5 + 0.150755672288881811323406j)`
- Branch-0 stability: `35.207` digits
- Branch-1 stability: `35.207` digits

## Verified PSLQ hits

- No non-trivial PSLQ relation involving `V_quad` was found in the tested three-basis space.

## Strongest low-height near misses

| rank | Heun proxy | Stokes basis | CM basis | digits | affine fit | error |
|---:|---|---|---|---:|---|---|
| 1 | `Im(H0'/H0)` | `y0` | `log|eta|` | 5.507602 | `-1.0*H + 1.5*S + 3.0*C + -1` | `3.107403e-06` |
| 2 | `Im(H1'/H1)` | `y0` | `log|eta|` | 5.507602 | `-1.0*H + 1.5*S + 3.0*C + -1` | `3.107403e-06` |
| 3 | `arg(H0/H1)/pi` | `M12/M22` | `log|eta|` | 4.839836 | `1.5*H + 2.5*S + -2.5*C + 2` | `1.445985e-05` |
| 4 | `|Wr(H0,H1)|` | `M21` | `pi^2/11` | 4.497674 | `3.0*H + 0.5*S + 1.5*C + 1` | `3.179260e-05` |
| 5 | `Im(H0'/H0)` | `y0p` | `sqrt(11)` | 4.285017 | `2.0*H + -3.0*S + -2.0*C + 0` | `5.187801e-05` |
| 6 | `Im(H1'/H1)` | `y0p` | `sqrt(11)` | 4.285017 | `2.0*H + -3.0*S + -2.0*C + 0` | `5.187801e-05` |
| 7 | `arg(H0/H1)/pi` | `r0=y'/y` | `sqrt(11)` | 4.145024 | `-3.0*H + -3.0*S + -1.5*C + 1` | `7.161037e-05` |
| 8 | `Re(H0'/H0)` | `M21` | `pi/sqrt(11)` | 4.144528 | `2.0*H + -1.0*S + -2.0*C + 0` | `7.169215e-05` |
| 9 | `Re(H1'/H1)` | `M21` | `pi/sqrt(11)` | 4.144528 | `-2.0*H + -1.0*S + -2.0*C + 0` | `7.169215e-05` |
| 10 | `|H0(z0)|` | `y0p` | `pi/sqrt(11)` | 4.134748 | `0.5*H + -1.0*S + -2.5*C + 0` | `7.332499e-05` |
| 11 | `|H1(z0)|` | `y0p` | `pi/sqrt(11)` | 4.134748 | `0.5*H + -1.0*S + -2.5*C + 0` | `7.332499e-05` |
| 12 | `Re(H0'/H0)` | `y0p` | `sqrt(11)` | 4.127482 | `-2.0*H + 3.0*S + 2.5*C + 2` | `7.456205e-05` |
