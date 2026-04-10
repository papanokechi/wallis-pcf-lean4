# Materials Micro-Laws Discovery Framework

**Generative AI for Interpretable Materials Micro-Laws Under Symbolic Physical Constraints**

An exponentially iterated generative framework that discovers symbolic "micro-laws" for materials properties (band gap, bulk modulus, formation energy) from high-dimensional materials databases, while enforcing hard physical and symmetry constraints.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ITERATIVE REFINEMENT LOOP                        │
│                                                                     │
│  ┌──────────────┐   ┌──────────────────┐   ┌───────────────────┐   │
│  │ Representation│   │    Symbolic      │   │   Constraint     │   │
│  │   Learner    │──►│   Regression     │──►│    Engine        │   │
│  │ (GNN / PCA)  │   │ (PySR / builtin) │   │ (dim/mono/bound) │   │
│  └──────────────┘   └──────────────────┘   └───────────────────┘   │
│         ▲                                           │               │
│         │           ┌──────────────────┐            │               │
│         └───────────│    Feedback &    │◄───────────┘               │
│                     │  Template Evol.  │                            │
│                     └──────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Components

1. **Representation Learner** (`representation.py`)
   - `CrystalGraphEncoder`: GCN-based encoder for crystal graph → latent vectors
   - `DescriptorAutoencoder`: Neural compression of tabular descriptors
   - `PCAFeaturizer`: Lightweight SVD-based fallback
   - Computes feature importance via gradient magnitude or loading analysis

2. **Symbolic Regression Core** (`symbolic_regression.py`)
   - **PySR integration**: Production-grade GP-based SR (requires Julia backend)
   - **Built-in search**: Template enumeration with unary/binary ops and linear fitting
   - **Physical templates**: Pre-defined formula patterns from materials science literature
   - Returns ranked `CandidateFormula` objects with sympy expressions

3. **Constraint Engine** (`constraints.py`)
   - **Dimensional analysis**: Ensures transcendental function arguments are dimensionless
   - **Monotonicity**: Verifies known structure-property trends via symbolic diff
   - **Boundedness**: Band gap ≥ 0, no divergences for realistic descriptor ranges
   - **Complexity**: Occam's razor — max AST operations, max variables
   - Hard constraints reject; soft constraints add score penalties

4. **Iterative Loop** (`iteration_loop.py`)
   - Each iteration: learn repr → SR → filter → evaluate → update templates
   - Descriptors pruned by importance; templates evolved from best formulas
   - Constraint strictness tightens across iterations
   - Tracks cumulative search-space reduction factor

---

## Theoretical Framework

### Theorem 1: Search Space Reduction Under Physical Constraints

Let $S_0$ be the unconstrained hypothesis space with $D$ descriptors and max complexity $C$:

$$|S_0| \leq D^C \cdot (|O_{\text{bin}}| + |O_{\text{un}}|)^C \cdot C_C$$

where $C_C$ is the $C$-th Catalan number. Under $K$ independent hard constraints $\Phi = \{\phi_1, \ldots, \phi_K\}$ with individual pass probabilities $p_k$:

$$|S_\Phi| \leq |S_0| \cdot \prod_{k=1}^K p_k$$

**Reduction factor:**

$$R(\Phi) = \frac{|S_0|}{|S_\Phi|} \geq \prod_{k=1}^K \frac{1}{p_k}$$

For perovskite band gap with dimensional ($p \approx 0.1$), monotonicity ($p \approx 0.4$, 2 rules), and boundedness ($p \approx 0.5$) constraints:

$$R \approx 10 \times 6.25 \times 2 = 125\times \text{ per iteration}$$

Cumulative across $K_\text{iter}$ iterations with diminishing returns factor $\alpha \in (0.6, 1.0)$:

$$R_\text{total}(K_\text{iter}) = \prod_{t=1}^{K_\text{iter}} R_t \geq R_1^{\alpha \cdot K_\text{iter}}$$

### Theorem 2: Spurious Law Probability Bound

Under sub-Gaussian noise $\sigma$, the probability a constrained formula with training MAE $\leq \varepsilon$ has population MAE $> \varepsilon + \delta$:

$$P(\text{spurious}) \leq |S_\Phi| \cdot \exp\!\left(-\frac{N \delta^2}{8\sigma^2}\right)$$

Required samples for $P(\text{spurious}) \leq \eta$:

$$N \geq \frac{8\sigma^2}{\delta^2}\left(\ln|S_\Phi| + \ln\frac{1}{\eta}\right)$$

**Key insight:** A $100\times$ reduction in $|S_\Phi|$ reduces required samples by $\frac{8\sigma^2 \ln 100}{\delta^2}$.

---

## Falsifiable Numerical Predictions

After $K = 5$ self-improvement iterations on ABX₃ halide perovskite data (≥ 30 compounds):

| Prediction | Statement | Threshold |
|-----------|-----------|-----------|
| **P1** | Discovered formula MAE on held-out compositions | $\leq 0.15$ eV |
| **P1b** | Improvement over unconstrained SR baseline | $\geq 30\%$ |
| **P2** | Best formula complexity (AST operations) | $\leq 12$ |
| **P3** | Fraction of hypothesis space evaluated | $\leq 1\%$ |

**Falsification:** Any one prediction failing to hold invalidates the claimed performance bounds.

---

## Quick Start

### Minimal Dependencies (synthetic data, built-in SR)

```bash
pip install numpy scipy pandas scikit-learn sympy loguru
```

### Full Dependencies (real data, PySR, neural representation)

```bash
pip install -r requirements.txt
```

### Run

```bash
# Full demo with synthetic perovskite data
python run_experiment.py

# Print theoretical analysis only
python run_experiment.py --theory-only

# 10 iterations with autoencoder representations
python run_experiment.py --iterations 10 --repr autoencoder

# Use PySR engine (requires Julia + PySR)
python run_experiment.py --sr pysr --iterations 5

# Save results to directory
python run_experiment.py --output results/ --iterations 5
```

### Example Output

```
OVERALL BEST FORMULA:
  0.45*(EN_X - EN_B) + 0.8/t_factor - 0.3*octahedral_factor + 0.12*(IE_B - EA_B) - 0.5
  MAE: 0.078 eV
  R²:  0.962
  Complexity: 11

PREDICTION EVALUATION:
  P1_accuracy:     ✓ PASS (value=0.0780, threshold=0.1500)
  P1_improvement:  ✓ PASS (value=0.4200, threshold=0.3000)
  P2_parsimony:    ✓ PASS (value=11, threshold=12)
  P3_efficiency:   ✓ PASS (value=0.0031, threshold=0.0100)
```

---

## Project Structure

```
materials_microlaws/
├── __init__.py              # Package init
├── data_loader.py           # Dataset loading + descriptor definitions
├── representation.py        # GNN / autoencoder / PCA representation learning
├── symbolic_regression.py   # PySR + built-in symbolic search + templates
├── constraints.py           # Physical constraint engine
├── iteration_loop.py        # Main iterative refinement orchestrator
├── theory.py                # Theorems, bounds, and numerical predictions
├── evaluation.py            # Metrics and comparison utilities
├── run_experiment.py        # CLI entry point
├── requirements.txt         # Dependencies
└── README.md                # This file
```

---

## Target Property Regimes

| Property | Data Source | Descriptor Basis | Status |
|----------|-----------|------------------|--------|
| ABX₃ perovskite band gap | Synthetic / Matminer (Castelli) | Ionic radii, EN, tolerance factor | ✅ Implemented |
| Alloy formation energy | Materials Project | Composition features | 🔜 Planned |
| Catalytic activity (OER) | Catalysis-hub | Electronic + geometric | 🔜 Planned |
| Bulk modulus | AFLOW | Elastic + structural | 🔜 Planned |

---

## Citation

If you use this framework, please cite the underlying methods:

- **PySR**: Cranmer, M. (2023). Interpretable Machine Learning for Science with PySR and SymbolicRegression.jl. arXiv:2305.01582
- **AI-Feynman**: Udrescu & Tegmark (2020). AI Feynman 2.0. NeurIPS.
- **LLM-guided SR**: Recent work on LLM-guided symbolic law discovery for perovskites.
