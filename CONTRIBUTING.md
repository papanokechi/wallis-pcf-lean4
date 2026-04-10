# Contributing to Ramanujan Breakthrough Generator

Thank you for your interest in contributing! This project discovers new polynomial continued fraction identities via evolutionary search and PSLQ matching. Contributions from mathematicians, computer scientists, and hobbyists alike are welcome.

---

## Quick Start

```bash
git clone https://github.com/ramanujan-breakthrough/ramanujan-breakthrough-generator.git
cd ramanujan-breakthrough-generator
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -e ".[dev]"
pytest -v
```

---

## Ways to Contribute

### 1. Add New Target Constants

The constant library lives in `build_constants()` inside `ramanujan_breakthrough_generator.py`. To add a new constant:

```python
# In build_constants():
consts["my_constant"] = mp.mpf("0.123456789...")  # high-precision value
```

**Guidelines:**
- Use `mp.mpf()` with at least 30 decimal digits.
- Include both the constant and simple rational multiples (e.g., `2*G`, `G/pi`).
- Add a comment citing the source (OEIS, Mathworld, etc.).
- Suitable constants: Clausen values, polylogarithms, MZVs, Dirichlet L-values, Gamma ratios, Bessel special values.

### 2. Implement New Search Strategies

Search modes are defined in the main module. To add a new strategy:

1. Define a generation function that produces `PCFParams` objects.
2. Register it alongside the existing `evolve`, `dr`, `cmf` modes.
3. Add tests in `tests/test_breakthrough_generator.py`.

### 3. Improve Proof Automation

The `irrationality_toolkit.py` module contains tools for connecting discovered CFs to formal proofs. Contributions here include:
- Connecting to Lean 4 / Coq proof assistants
- Automating Apéry-style irrationality proofs
- Implementing convergence rate bounds

### 4. Submit Discovered Conjectures

If you've found an interesting CF identity using this tool:

1. **Verify** it at 200+ digit precision.
2. Open an issue with the title `[Discovery] <brief description>`.
3. Include: `a(n)` coefficients, `b(n)` coefficients, matched constant, verified digit count.
4. We'll add it to the Conjecture Gallery in `results/conjecture_gallery.md`.

### 5. Performance & Parallelism

- Parallelize CF evaluation with `multiprocessing` or `concurrent.futures`.
- Optimize the PSLQ bottleneck for large constant libraries.
- Profile and reduce per-cycle overhead.

---

## Development Workflow

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/my-contribution
   ```

2. **Make your changes** and add tests.

3. **Run the test suite:**
   ```bash
   pytest tests/ -v
   ```

4. **Run a quick smoke test:**
   ```bash
   python ramanujan_breakthrough_generator.py --cycles 5 --seed 42
   ```

5. **Submit a pull request** against `main`.

---

## Code Style

- Python 3.10+ with type hints where practical.
- Use `mpmath` types (`mpf`) for all high-precision arithmetic — never `float`.
- Keep the core module (`ramanujan_breakthrough_generator.py`) self-contained with minimal dependencies.
- Follow existing naming conventions: `snake_case` for functions, `PascalCase` for classes.

---

## Reporting Issues

- **Bug reports**: Include Python version, OS, full traceback, and the command you ran.
- **Feature requests**: Describe the mathematical motivation and expected behavior.
- **False positives**: If a "discovery" is actually a known result, open an issue with the CF parameters and the known identity.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
