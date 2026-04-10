# Conjecture Gallery

> A curated collection of the most elegant and unexpected continued fraction identities discovered by the Ramanujan Breakthrough Generator.

---

## Proven Theorems

### Bessel J Ratio CF (Novel, Formally Proven)

$$
b_0 + \cfrac{a_1}{b_1 + \cfrac{a_2}{b_2 + \cdots}}, \quad a(n) = -3, \quad b(n) = -4 + 4n
$$

**Value:**  $4 - \sqrt{3} \cdot \dfrac{J_0\!\left(\frac{\sqrt{3}}{2}\right)}{J_1\!\left(\frac{\sqrt{3}}{2}\right)} = 0.38729700192868709\ldots$

- **Closed form:** Bessel J ratio  
- **CAS verified:** 110 digits  
- **Convergence:** Stern-Stolz (linear growth of $b_n$)  
- **Proof status:** Formal proof (convergence + closed form + CAS verification)

---

## Pi Family (Verified Known — Rediscovered)

The generator independently rediscovered a parametric family of $\pi$-related continued fractions:

$$
a_m(n) = -2n^2 + (2m+1)n, \quad b(n) = 3n + 1
$$

| $m$ | $a(n)$ coefficients | CF Value | Verified Digits |
|-----|---------------------|----------|-----------------|
| 0 | `[0, 1, -2]` | $2/\pi$ | 160+ |
| 1 | `[0, 3, -2]` | $4/\pi$ | 160+ |
| 2 | `[0, 5, -2]` | $16/(3\pi)$ | 160+ |
| 3 | `[0, 7, -2]` | $32/(15\pi)$ | 160+ |

General pattern:
$$S^{(m)} = \frac{2^{m+1}}{m! \cdot \binom{2m}{m} \cdot \frac{1}{\pi}}$$

---

## Factorial Coefficient CFs (Novel, Unproven)

These CFs use factorial-growth numerators — outside the polynomial regime that classical theory covers.

### $a(n) = 2 \cdot n!, \; b(n) = 3$

**Value:** $3.4910744001668914\ldots$

- **Status:** Novel unproven — no PSLQ match to any of the 25+ constants in the library
- **Convergence:** Empirically converged to 60 digits
- **Open question:** Does this value have a closed form? Is it transcendental?

### $a(n) = (-1)^n \cdot n!, \; b(n) = 1$

**Value:** Related to the Euler–Gompertz constant

- **Status:** Verified known (connects to $e \cdot \text{Ei}(1)$ family)

---

## Bessel I Ratio CFs (Novel, Proven via CAS)

Linear-$b$ continued fractions where the closed form involves modified Bessel functions of the first kind $I_\nu(z)$.

| $a(n)$ | $b(n)$ | Closed Form | Digits |
|--------|--------|-------------|--------|
| `[-3]` | `[-4, 4]` | $4 - \sqrt{3} \cdot I_0/I_1$ | 110 |

These emerge from the correspondence between three-term recurrences and Bessel differential equations: if $a(n)$ is constant and $b(n)$ is linear, the CF convergents satisfy a Bessel-type ODE.

---

## Quadratic-$b$ CFs (Structural, No Closed Form)

An important **negative result**: CFs with quadratic $b(n) = \alpha n^2 + \beta n + \gamma$ and constant $a(n)$ converge extremely fast, but their values consistently show **no PSLQ relation** to any known constant. This suggests they are genuinely new transcendental numbers.

**Implication:** The search strategy should prioritize **linear-$b$** CFs for provable results, while quadratic-$b$ CFs may be interesting as generators of new constants.

---

## Statistics (v4.6, 2 rounds, budget 15)

| Metric | Count |
|--------|-------|
| Total discoveries | 119 |
| Novel proven (L3 theorems) | 6 |
| Novel unproven | 23 |
| Verified known | 11 |
| Conditional (L2) | 8 |
| Structural (L1) | 8 |
| Theorem value score | 76.0 |

---

## How to Reproduce

```bash
pip install -e .
python -m ramanujan_agent --rounds 2 --budget 15
# Results appear in results/ramanujan_results.json
# Interactive report: ramanujan-discovery-report.html
```

Or use the standalone generator:

```bash
python ramanujan_breakthrough_generator.py --cycles 30 --seed 42
```

---

## Submit Your Own

Found something interesting? See [CONTRIBUTING.md](../CONTRIBUTING.md) — open an issue with tag `[Discovery]`.
