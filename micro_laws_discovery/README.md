# Exponential Self-Improving Discovery of Micro-Laws in Exoplanet Dynamics

An automated, exponentially iterated discovery loop that learns symbolic
**micro-laws** governing exoplanet and multi-body orbital dynamics from
simulation data.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│               Self-Improvement Controller                │
│  • Refine data distribution (boundary focus)             │
│  • Prune operator/exponent vocabulary (exponential)      │
│  • Update priors on dimensionless groups                 │
│  • Track convergence                                     │
└────────────┬────────────────────────────┬────────────────┘
             │                            │
     ┌───────▼────────┐          ┌───────▼──────────┐
     │ Neural Surrogate│          │ Symbolic          │
     │ (MLP / GBT)     │◄────────►│ Distillation      │
     │                  │ soft     │ (PySR / builtin)  │
     │ features → P(s)  │ targets  │ → compact laws    │
     └───────▲──────────┘          └──────────────────┘
             │
     ┌───────┴──────────┐
     │ N-body Integrator │
     │ (Wisdom–Holman)   │
     │ + MEGNO labels    │
     └──────────────────┘
```

## Three Core Components

| # | Component | Module | Role |
|---|-----------|--------|------|
| 1 | **Neural Dynamical Surrogate** | `surrogate.py` | MLP with residual blocks; maps dimensionless orbital features → stability probability. Gradient-based feature importance guides symbolic search. |
| 2 | **Symbolic Distillation Engine** | `symbolic_engine.py` | PySR (Julia SR) or built-in power-law search; extracts compact equations from surrogate predictions with sparsity + complexity penalties. |
| 3 | **Self-Improvement Controller** | `controller.py` | Each round: prune unused operators (exponential search-space reduction), refocus data on decision boundaries, tighten complexity bounds. |

## Key Features

- **Dimensional analysis**: Buckingham Π theorem auto-constructs dimensionless groups (`dimensional.py`); all candidate laws are checked for dimensional consistency.
- **Symmetry enforcement**: Kepler scaling, rotational symmetry, time-reversibility, permutation symmetry for identical planets.
- **Provable properties**:
  - *Identifiability guarantee*: Power-law exponents are identifiable to O(σ/√n) under Gaussian noise (verified via bootstrap).
  - *Generalisation bound*: PAC-Rademacher bound on true risk for bounded-complexity symbolic expressions.
- **Falsifiable prediction**: After K rounds, the best discovered law predicts stability with ≥X% accuracy at Y× speedup — testable on fresh systems.
- **Exponential convergence**: Operator/exponent vocabulary shrinks exponentially across rounds; verified by fitting log(search_space) vs round.

## Quick Start

```bash
# Install dependencies
pip install -r micro_laws_discovery/requirements.txt

# Run fast demo (3 rounds, small dataset)
python -m micro_laws_discovery.main --fast

# Full run (8 rounds, 300 training systems)
python -m micro_laws_discovery.main --rounds 8 --n-train 300

# With PySR backend (requires Julia)
python -m micro_laws_discovery.main --sr-backend pysr --rounds 10
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--rounds` | 8 | Max self-improvement rounds |
| `--n-train` | 300 | Training systems to generate |
| `--n-test` | 100 | Held-out test systems |
| `--integration-steps` | 3000 | N-body steps per system |
| `--epochs` | 80 | Surrogate training epochs/round |
| `--sr-backend` | auto | `pysr`, `builtin`, or `auto` |
| `--output-dir` | results/ | Where to write results |
| `--seed` | 42 | Random seed |
| `--fast` | off | Quick test mode |

## Output

Results are written to `results/`:
- **`discovery_results.json`** — full structured results (laws, metrics, guarantees, convergence)
- **`discovered_laws.txt`** — human-readable summary of all discovered micro-laws

## Known Benchmarks Checked

The system verifies discovered laws against:
- **Gladman (1993)**: Δ > 2√3 mutual Hill radii for stability
- **Chambers (1996)**: Δ > 3.5 R_H for long-term stability
- **Wisdom (1980)**: Resonance overlap width ∝ μ^{2/7}
- **Petit et al. (2018)**: AMD stability criterion

## File Structure

```
micro_laws_discovery/
├── __init__.py          # Package metadata
├── __main__.py          # python -m entry point
├── main.py              # Orchestration loop (Phases 0–7)
├── nbody.py             # Wisdom–Holman integrator, MEGNO, data generation
├── dimensional.py       # Buckingham Π, symmetry constraints
├── surrogate.py         # Neural MLP surrogate (PyTorch / sklearn fallback)
├── symbolic_engine.py   # PySR wrapper + built-in power-law search
├── controller.py        # Self-improvement controller
├── evaluation.py        # Held-out eval, provable guarantees, falsifiable predictions
└── requirements.txt     # Dependencies
```
