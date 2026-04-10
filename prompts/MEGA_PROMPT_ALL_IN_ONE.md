# ALL-IN-ONE: World-Class Math Discovery Paper — Single-Session Mega-Prompt

## Usage
Copy everything below the line into an AI conversation (Claude, GPT-5.1, Gemini, etc.) together with a **specific mathematical discovery challenge** at the end.

---

# ═══════════════════════════════════════════════════════════════
# INSTRUCTION: SELF-IMPROVING MATHEMATICAL DISCOVERY PIPELINE
# ═══════════════════════════════════════════════════════════════

You will execute an 8-stage pipeline to generate a world-class academic paper on **automated mathematical discovery using generative AI** for the topic given at the end. Execute ALL stages sequentially. Do not skip any stage. Do not abbreviate. Each stage must produce its full structured output before proceeding.

The core challenge:
Design and analyze a **generative, exponentially iterated discovery loop** that can autonomously propose, test, refine, and formalize **new mathematical conjectures, invariants, or constructions** beyond current human-written theory.

## GLOBAL CONSTRAINTS

- The paper must introduce **genuinely novel** theoretical contributions in **AI-driven mathematical discovery** (not just rephrasing existing conjecture/prover frameworks).
- It must contain at least one **falsifiable numerical prediction** about the performance or yield of the discovery loop (e.g., conjectures per iteration, probability of correctness, expected proof rate) with a specific experimental protocol on a concrete domain (e.g., graphs, number theory, topology).
- At least one core algorithm must exploit **explicit exponential iteration / self-improvement** (e.g., RISE-style self-improvement, evolutionary loops, or multi-agent conjecturer-prover cycles) and the paper must analyze how performance scales with iterations.
- All stated theorems about the algorithm, invariants, or convergence properties must have **complete proofs** (no "it can be shown").
- The final output must score **≥ 90/100** on the evaluation rubric in Stage 6.
- Use LaTeX math notation: `\(...\)` inline, `\[...\]` display.

---

## STAGE 1 — FIELD CARTOGRAPHY & GAP ANALYSIS

Survey the relevant areas: automated conjecturing, automated theorem proving, and AI-guided mathematical discovery. Produce:

1. **Field Landscape**
   - 5–10 foundational results with year and status (e.g., Graffiti/TxGraffiti, DeepMind/Google ML for conjectures, LeanConjecturer, AlphaZero-style search in math).
   - Major recent advances (last 5–7 years), including LLM-assisted theorem proving and conjecture generation.
   - Dominant paradigms (symbolic search, data-driven, conjecturer-prover agents) and key disagreements.

2. **Open Problems**
   - ≥ 5 genuine open problems in automated mathematical discovery, each with:
     - precise statement,
     - why it matters,
     - difficulty (Incremental / Hard / Fundamental),
     - partial results,
     - blocking obstacles (e.g., interestingness metrics, trustworthiness, scaling).

3. **Cross-Domain Connections**
   - ≥ 3 underexplored links to other fields (e.g., evolutionary algorithms, test-time training/discover-style methods, information geometry of conjecture spaces).

4. **Breakthrough Ranking**
   - Table ranking the open problems by Impact × Tractability × Novelty, with short justifications.

5. **Literature Foundation**
   - 20 essential references (mix of classic systems like Graffiti, recent LLM-based systems like LeanConjecturer and GraphMind/GraffitiAI talks, and survey papers on AI for mathematics).

---

## STAGE 2 — BREAKTHROUGH HYPOTHESIS GENERATION

Generate ≥ 3 candidate **breakthrough hypotheses** specifically about generative, iterated discovery loops. For each hypothesis:

- **Core claim**: One falsifiable sentence about what the loop can achieve (e.g., "After \(T\) exponential iterations, the system's conjecture-acceptance precision exceeds \(p_*\) on a held-out domain of graph invariants").
- **Mathematical setup**:
  - precisely defined object class (e.g., finite graphs, integer sequences, simplicial complexes),
  - definition of the conjecture space, proof oracle, and evaluation metrics.
- **Key new insight / mechanism**:
  - what makes this different from existing conjecture/prover frameworks (e.g., a new interestingness functional, a provable convergence property, or a new invariant family).
- **Falsifiable prediction(s)**:
  - specific numerical predictions (e.g., "The expected number of non-trivial conjectures provable by Lean per 1,000 proposals doubles after 4 self-improvement epochs on domain \(D\)").
  - clearly defined experimental protocol to test them.
- **Risk assessment**:
  - whether the hypothesis collapses to a trivial restatement of known results,
  - whether assumptions are realistic given current theorem proving and LLM capabilities.
- **Comparative scoring table**:
  - rank hypotheses on Novelty, Rigor potential, Experimental testability, and Exponential-improvement character.
  - Select the **best hypothesis** and outline a development path.

---

## STAGE 3 — CONTINUOUS IMPROVEMENT DISCUSSION (3 ROUNDS)

Simulate 3 experts debating the selected hypothesis:

- **Expert A (Formalist)**:
  - checks definitions, formal soundness, and proof gaps;
  - pushes toward Lean/Coq formalizability.

- **Expert B (Skeptic)**:
  - attacks novelty (e.g., "Is this just Graffiti/GraphMind/LeanConjecturer in disguise?"),
  - tries to reduce it to existing frameworks or find counterexamples.

- **Expert C (Experimentalist)**:
  - tests robustness of the predictions;
  - evaluates feasibility of experiments (e.g., how many iterations, compute required, appropriate benchmarks like finite graph theory, knot invariants, or algebraic identities).

Structure:

- **Round 1**:
  - Each expert provides a 4-point critique.
  - Synthesize issues as Critical / Major / Minor.

- **Round 2**:
  - Address all issues.
  - Present **REFINED HYPOTHESIS v2**.
  - Each expert re-evaluates and updates their position.

- **Round 3 (Adversarial stress test)**:
  - Attempt explicit counterexamples or reductions to known work.
  - Test prediction robustness under at least 3 parameter settings (e.g., different domains, different iteration budgets, different proof oracles).
  - Issue a **FINAL VERDICT**: [APPROVED / NEEDS REVISION / REJECTED] with confidence level and final **Hypothesis v3**.

---

## STAGE 4 — FORMAL PROOF CONSTRUCTION

Build the formal mathematical apparatus around the chosen hypothesis:

1. **Definitions**
   - Define the discovery loop (states, transitions, reward/interestingness functional, self-improvement update rule).
   - Define the class of conjectures and proofs, and any invariants studied.

2. **Notation table**
   - Every symbol and operator must be explicitly defined.

3. **Dependency graph**
   - Logical structure: assumptions → lemmas → main theorems → corollaries.

4. **Lemmas**
   - Each lemma with a complete proof (e.g., monotonicity properties, bounds on failure rates, sample-complexity bounds).

5. **Main Theorems**
   - e.g., theorems about convergence, improvement rate under iteration, or guarantees on the fraction of non-trivial/true conjectures generated after \(k\) rounds.

6. **Corollaries**
   - Include at least one corollary encoding the **falsifiable numerical prediction** (e.g., a bound that can be tested against empirical results from a concrete system such as a Lean-integrated LLM conjecturer).

7. **Verification checklist**
   - Ensure: all variables bound, no circular reasoning, asymptotic claims properly quantified, edge cases (e.g., degenerate conjecture spaces) handled.

---

## STAGE 5 — FULL PAPER DRAFT

Write the complete paper:

- **Title**
  - Precise and evocative, clearly indicating exponential, self-improving AI for mathematical discovery.

- **Abstract** (150–250 words)
  - Context, core problem, method (the loop), main theoretical results, key prediction, broader significance.

- **§1 Introduction**
  - Motivation: limitations of current AI-for-math systems (local search, single-shot LLMs).
  - Problem: need for self-improving, iterated discovery engines.
  - Why existing approaches are insufficient.
  - Contribution preview and highlight of the main falsifiable prediction.

- **§2 Background & Related Work**
  - Automated conjecturing (Graffiti, TxGraffiti, GraphMind/GraffitiAI).
  - LLM-driven conjecture generators (e.g., LeanConjecturer).
  - AI-for-math surveys and intuition-guiding ML for discovery.
  - Explicitly distinguish what is new.

- **§3 Formal Framework**
  - Discovery loop, state space, update rule, evaluation metrics.
  - Assumption justification (e.g., about prover strength, data availability, computational limits).

- **§4 Main Results**
  - Theorems and proofs in full.
  - Discussion of implications (e.g., scaling laws in conjecture yield vs. iterations).

- **§5 Falsifiable Predictions & Experiments**
  - Derive the numerical prediction (e.g., expected improvement curve).
  - Design experiments: concrete domains, benchmarks, iteration counts, comparison baselines (non-iterated LLM, non-improving search, etc.).
  - State null hypotheses and evaluation criteria.

- **§6 Discussion**
  - Connections to broader AI-for-science, symbolic-neural hybrids, and human-AI collaboration in math.
  - Limitations and open problems.

- **§7 Conclusion**
  - Bullet-point contributions and key takeaways.

- **References**
  - 12–20 real works, covering both math-AI systems and theoretical underpinnings.

---

## STAGE 6 — TRIPLE PEER REVIEW

Simulate 3 independent reviews:

- **Reviewer 1 (Senior Theorist)**
  - Focus: mathematical rigor, proof correctness, clarity of assumptions.

- **Reviewer 2 (AI/ML for Math Researcher)**
  - Focus: novelty relative to existing AI-for-math systems, experimental design, realism of the discovery loop.

- **Reviewer 3 (Automated Reasoning / Formal Methods Expert)**
  - Focus: integration with theorem provers, formalizability, practical impact for Lean/Coq/Isabelle ecosystems.

Each reviewer provides:

- Score (1–10) and accept/reject recommendation.
- ≥ 3 strengths and ≥ 3 weaknesses.
- Questions and technical comments.

Then produce a **Meta-Review**:

- Average scores.
- Consensus strengths/weaknesses.
- Conflicting opinions.
- Critical issues list.

Use the **Dimensional Scoring (100-point rubric):**

| Dimension              | Weight |
|------------------------|--------|
| Scientific Novelty     | 20     |
| Mathematical Rigor     | 20     |
| Falsifiability         | 15     |
| Internal Coherence     | 15     |
| Significance           | 10     |
| Clarity                | 10     |
| Completeness           | 10     |

---

## STAGE 7 — REVISION & REFINEMENT

Address every issue from the reviews:

1. **Response Letter**
   - For each reviewer comment, provide a substantive response and specify exact changes.

2. **Change Summary Table**
   - Columns: Section, change type (clarification/proof fix/scope scaling/experiment detail), description, which reviewer prompted it.

3. **Complete Revised Paper**
   - Integrate all changes into a clean, revised version.

4. **Score Re-assessment**
   - Pre/post revision scores on each dimension, with deltas and justifications.
   - Ensure the final version plausibly reaches **≥ 90/100**.

---

## STAGE 8 — FINAL HTML OUTPUT

Convert the revised paper into a **single self-contained HTML file** with:

- Google Fonts (EB Garamond, Cormorant Garamond, JetBrains Mono).
- MathJax CDN for equation rendering.
- Warm paper palette (#faf8f4 background, #1a1612 ink, #8b2020 accent).
- Running header (fixed on scroll).
- Centered title block with journal label and peer-review grade badge.
- Abstract block with accent-colored left border.
- Numbered sections (§1, §2, …) with decorative rules.
- Theorem/Definition/Corollary boxes with colored left borders and type labels.
- Proof blocks with QED symbol (□).
- Gold-bordered highlight box for the key numerical prediction.
- Score table with animated fill bars for review scores.
- Ornamental dividers (· · ·) between major sections.
- Properly formatted references with auto-numbered brackets.
- Footer with paper title and year.
- Scroll-triggered fade-in animations for sections.
- Mobile-responsive layout (640px breakpoint).
- Print styles (hide header, full width).
- Paper-grain SVG overlay.

Output the **complete HTML file**, ready to open in a browser.

---

## ═══ YOUR SPECIFIC CHALLENGE ═══

Replace the text inside the block below with a concrete challenge. For example:

- "Exponential self-improving conjecture discovery for finite graph invariants"
- "Generative AI for discovering new inequalities in additive combinatorics via iterative search"
- "Multi-agent conjecturer-prover loops for discovering new invariants in low-dimensional topology"

```text
[INSERT YOUR SPECIFIC AUTOMATED MATH DISCOVERY CHALLENGE HERE]
```

---

## EXECUTION ORDER
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

Begin with Stage 1 now. Execute each stage completely before moving to the next. Output all 8 stages without omission.