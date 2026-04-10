# Reproducing the PCF Families Discovery

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd pcf-families
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 2. Install dependencies (pinned versions)
pip install -r requirements.txt

# 3. Run the standalone verification (both theorems)
python pcf_families.py

# 4. Run with Arb certification (requires python-flint)
python pcf_families.py --arb --export

# 5. Run the full discovery pipeline
python pcf_discovery_engine.py --budget 500 --arb --emit-latex
```

## Environment

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.14+ | Runtime |
| mpmath | 1.4.1 | Arbitrary-precision arithmetic |
| python-flint | 0.8.0 | Arb ball arithmetic (optional) |
| sympy | 1.14.0 | Symbolic verification (optional) |

## Files

| File | Description |
|------|-------------|
| `pcf_families.py` | Standalone theorem verification (340 lines) |
| `pcf_discovery_engine.py` | Full automated pipeline (400 lines) |
| `pcf_paper_final.tex` | LaTeX paper with proofs (437 lines) |
| `pcf_theorems.json` | Machine-readable theorem statements |
| `pcf_families_results.json` | Verification output |
| `pcf_pipeline_results.json` | Pipeline run metadata |
| `proof_ready/` | Auto-generated LaTeX theorem boxes |

## Reproducing Specific Results

### Theorem 1 (Logarithmic Ladder)
```bash
python pcf_families.py --log-only --precision 200 --depth 2000
```
Expected: all k values match to 200+ digits.

### Theorem 2 (Pi Family)
```bash
python pcf_families.py --pi-only --precision 200 --depth 2000
```
Expected: all m values match to 200+ digits.

### Arb Certification (1500+ digits)
```bash
python pcf_families.py --arb --arb-depth 5000 --arb-bits 10000
```
Expected: 1/ln2 certified to 1509dp, 2/π to 1508dp.

### Full Pipeline Discovery Run
```bash
python pcf_discovery_engine.py --budget 500 --arb --emit-latex
```
Expected: 7 PSLQ hits, 6 provable, 6 Arb-certified. Includes 1/ln(3) at k=1.5.

## Validating Arb Certificates

Each Arb certificate guarantees the PCF limit lies in a rigorously computed interval.
The bracketing uses consecutive convergents C_N and C_{N-1}; since a(n) < 0 and
b(n) > 0, these bracket the true limit (Lorentzen-Waadeland, Theorem 4.35).

To validate independently:
```python
from flint import arb, ctx as flint_ctx
flint_ctx.prec = 8000

# Example: 1/ln(2)
def eval_pcf(ac, bc, depth):
    def ep(c, n): return sum(arb(ci) * arb(n)**i for i, ci in enumerate(c))
    p_prev, p_curr = arb(1), ep(bc, 0)
    q_prev, q_curr = arb(0), arb(1)
    for n in range(1, depth + 1):
        a_n, b_n = ep(ac, n), ep(bc, n)
        p_new = b_n * p_curr + a_n * p_prev
        q_new = b_n * q_curr + a_n * q_prev
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
    return p_curr / q_curr, p_prev / q_prev

c_N, c_Nm1 = eval_pcf([0, 0, -2], [2, 3], 4000)
bracket = abs(c_N - c_Nm1)
target = 1 / arb.log(arb(2))
assert (c_N - target).overlaps(arb(0)) or (c_Nm1 - target).overlaps(arb(0))
print(f"Bracket width: {bracket}")  # < 10^{-1208}
```

## Paper Compilation

```bash
pdflatex pcf_paper_final.tex
pdflatex pcf_paper_final.tex  # second pass for references
```
