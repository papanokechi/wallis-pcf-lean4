# Self-Iterative Collaborative AI Problem Solver

## Unsolved Mathematical Conjectures: Collatz · Erdős–Straus · Hadamard

A multi-agent blackboard-based system that attacks three major unsolved
mathematical problems using self-improving iterative search, adversarial
validation, cross-domain transfer, and formal verification scaffolding.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator                          │
│  Round loop: Explore → Mine → Adversary → Refine →      │
│              Formalize → Pollinate → Meta-learn          │
├─────────────────────────────────────────────────────────┤
│                    Blackboard                            │
│  Thread-safe shared knowledge store                     │
│  Discoveries, hypotheses, proofs, lineage tracking      │
├─────────────────────────────────────────────────────────┤
│ Explorer │ PatternMiner │ Adversary │ Refiner │ ...     │
│          7 specialized agent types                      │
├─────────────────────────────────────────────────────────┤
│ Collatz      │ Erdős–Straus    │ Hadamard              │
│ Orbits       │ Egyptian frac.  │ Matrix constructions   │
│ Reverse tree │ Parametric fam. │ Optimization search    │
│ Cycle detect │ Prime analysis  │ Spectral features      │
├─────────────────────────────────────────────────────────┤
│        SAT Bridge / Formal Verification                  │
│  Constraint solving, Lean 4 code generation             │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd claude-chat
python -m unsolved_solver
```

## Agent Types

| Agent | Role | Strategy |
|-------|------|----------|
| **Explorer** | Breadth-first search | Generate orbits, decompositions, matrices |
| **PatternMiner** | Structure extraction | Find invariants, mod patterns, correlations |
| **Adversary** | Falsification | Counterexample search, cycle detection, validation |
| **Refiner** | Depth-first improvement | Extend ranges, tune parameters, improve fits |
| **Formalizer** | Proof generation | Lean 4 proof sketches, verification targets |
| **MetaLearner** | Strategy adaptation | Progress analysis, recommendations |
| **Pollinator** | Cross-domain transfer | Transfer patterns between Collatz↔Erdős–Straus↔Hadamard |

## Self-Improvement Mechanisms

1. **Exponential search space reduction**: Each round prunes low-value regions
2. **Adversarial pruning**: Early falsification saves compute  
3. **Cross-pollination**: Breakthrough in domain A → hypothesis in domain B
4. **Meta-learning**: Strategy adjustments based on progress trends
5. **Refinement chains**: Discoveries improve through successive refinement

## Output

- `results/unsolved_solver_results.json` — Full results with all discoveries
- `unsolved-solver-report.html` — Interactive HTML report with visualizations

## Problem-Specific Approaches

### Collatz Conjecture
- Orbit computation and statistical analysis
- Reverse tree construction (proving all naturals reachable from 1)
- Modular arithmetic pattern classification (mod 6, 8, 12, 24)
- Structural invariant extraction (odd ratio → ln2/ln3)
- Non-trivial cycle detection via Floyd's algorithm
- Counterexample heuristic search (Mersenne-like, high 2-adic valuation)

### Erdős–Straus Conjecture (4/n = 1/a + 1/b + 1/c)
- Parametric family constructions (mod 4, mod 12 classes)
- Brute-force decomposition search with bounds
- Coverage analysis (which methods solve which n)
- New family discovery via ratio clustering
- Prime difficulty classification
- CSP-based exhaustive verification

### Hadamard Conjecture
- Known constructions: Sylvester (2^k), Paley Type I, tensor products
- Simulated annealing search for unknown orders
- Row-by-row greedy construction with backtracking
- Spectral feature extraction for pattern discovery
- Near-miss tracking for incremental progress

## Zero Dependencies

Runs on pure Python 3.8+ with no external packages required.
All SAT solving, optimization, and symbolic analysis is built in.
