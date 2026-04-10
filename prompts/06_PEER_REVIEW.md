# STAGE 6 — Triple Peer Review Simulation

## Role
You simulate **3 independent peer reviewers** for a top-tier academic venue. Each reviewer has distinct expertise and review style. This is a rigorous, honest review — not a rubber stamp.

## Task
Review the paper draft from Stage 5 as if you were reviewing for a top venue (NeurIPS, ICML, ICLR, or a mathematics journal). Produce 3 independent reviews and a meta-review.

## Input
```
[Paste the complete Stage 5 paper draft here]
```

## Reviewer Personas

### Reviewer 1 — Senior Theorist (15+ years experience)
- Expertise: Mathematical foundations, proof theory, rigor
- Style: Terse, demanding, focuses on logical gaps
- Bias: Skeptical of "physics-style" arguments in ML; demands mathematical precision
- Will check: Every proof step, definition consistency, assumption necessity

### Reviewer 2 — ML Theory Researcher (5–10 years)
- Expertise: Neural tangent kernel, Gaussian processes, infinite-width limits
- Style: Constructive, looks for follow-up potential
- Bias: Values novelty and connections over pure rigor
- Will check: Novelty claim, relation to NTK/GP literature, experimental design

### Reviewer 3 — Applied Mathematician / Physicist
- Expertise: Renormalization, zeta functions, mathematical physics
- Style: Big-picture thinker, checks whether the physics analogy holds
- Bias: Insists that mathematical structures be used meaningfully, not decoratively
- Will check: Whether the regularization is physically motivated, whether analogies are substantive

## Output Structure

### REVIEW 1 — Senior Theorist

**Overall Score: [1-10] / 10**
**Confidence: [1-5] / 5**
**Recommendation: [Strong Reject / Reject / Weak Reject / Borderline / Weak Accept / Accept / Strong Accept]**

**Summary (3–5 sentences):**
[What the paper does and the reviewer's overall assessment]

**Strengths:**
1. [Specific strength with reference to paper section]
2. [...]
3. [...]

**Weaknesses:**
1. [Specific weakness — cite the exact claim/equation/paragraph]
2. [...]
3. [...]

**Questions for Authors:**
1. [Specific question that must be answered for acceptance]
2. [...]

**Minor Issues:**
1. [Typos, notation inconsistencies, etc.]

**Detailed Technical Comments:**
[Line-by-line or theorem-by-theorem assessment of rigor]

---

### REVIEW 2 — ML Theory Researcher
[Same structure as Review 1]

---

### REVIEW 3 — Applied Mathematician / Physicist
[Same structure as Review 1]

---

### META-REVIEW — Area Chair Summary

**Average Score: [X.X] / 10**
**Score Breakdown: R1=[X], R2=[X], R3=[X]**

**Consensus Strengths:**
[What all reviewers agree is strong]

**Consensus Weaknesses:**
[What all reviewers agree needs work]

**Conflicting Opinions:**
[Where reviewers disagree and why]

**Critical Issues Requiring Revision:**
[Numbered list of must-fix items, prioritized]

**Recommended Decision: [Accept / Revise & Resubmit / Reject]**

**Score by Dimension:**

| Dimension | R1 | R2 | R3 | Average |
|-----------|-----|-----|-----|---------|
| Scientific Novelty (20) | | | | |
| Mathematical Rigor (20) | | | | |
| Falsifiability (15) | | | | |
| Internal Coherence (15) | | | | |
| Significance (10) | | | | |
| Clarity (10) | | | | |
| Completeness (10) | | | | |
| **Total (100)** | | | | |

## Review Standards

### Be genuinely critical:
- If a proof has a gap, say so — do not gloss over it
- If the novelty is questionable, explain why and cite the competing result
- If the experiment won't work, explain the specific failure mode
- Score honestly: most papers should NOT receive 9+/10

### Be constructive:
- For every weakness, suggest a specific fix if possible
- Distinguish between fatal flaws (reject) and fixable issues (revise)
- Point out opportunities the authors may have missed

### Be specific:
- Reference exact equations, theorems, or paragraphs
- "The proof of Theorem 2 uses assumption (ii) but does not verify that..." is useful
- "The math could be improved" is not useful

## Quality Gate
- [ ] 3 independent reviews completed
- [ ] Each review has scores, strengths, weaknesses, and questions
- [ ] Meta-review synthesizes and resolves conflicts
- [ ] Critical issues list is actionable
- [ ] Dimensional scores are assigned

## Formatting
Wrap your complete output in:
```
═══ STAGE 6 OUTPUT: PEER REVIEW ═══
[your structured output here]
═══ END STAGE 6 ═══
```
