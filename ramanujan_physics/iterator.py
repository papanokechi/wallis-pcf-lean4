"""
iterator.py - Self-iterating discovery loop for the Ramanujan-Physics bridge.

The DiscoveryEngine runs multiple rounds of:
  1. DECOMPOSE: Structurally analyse all formulas
  2. MAP: Find physics connections for each component
  3. BRIDGE: Discover cross-formula patterns via shared physics
  4. REVERSE: Propose generalisations and new formulas
  5. TEST: Numerically verify proposals
  6. SYNTHESISE: Build the grand connection map
  7. META-LEARN: Adjust strategy based on what worked
"""

import time
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

import mpmath

from ramanujan_physics.formulas import get_all_formulas, eval_generalised_pi_series
from ramanujan_physics.physics_map import PhysicsBridge
from ramanujan_physics.reverse_engineer import ReverseEngineer


class DataclassEncoder(json.JSONEncoder):
    def default(self, obj):
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        if callable(obj):
            return f"<callable: {getattr(obj, '__name__', str(obj))}>"
        return super().default(obj)


class DiscoveryEngine:
    """Self-iterating agent that reverse-engineers Ramanujan formulas
    and maps them to physics."""

    def __init__(self, config=None):
        config = config or {}
        self.max_rounds = config.get("max_rounds", 5)
        self.prec = config.get("precision", 100)
        self.verbose = config.get("verbose", True)

        self.db = get_all_formulas()
        self.bridge = PhysicsBridge()
        self.engineer = ReverseEngineer(prec=self.prec)

        self.round_logs = []
        self.all_decompositions = []
        self.all_connections = []
        self.all_patterns = []
        self.cross_formula_bridges = []
        self.missing_links = []
        self.proposals = []
        self.grand_narrative = []
        self._seen_conn_keys = set()   # dedup connections across rounds
        self._seen_pattern_ids = set()  # dedup patterns across rounds

    def run(self):
        """Execute the full self-iterating discovery loop."""
        t0 = time.time()
        self._log("=" * 70)
        self._log("RAMANUJAN-PHYSICS BRIDGE: Self-Iterating Discovery Engine")
        self._log(f"  Formulas in database: {len(self.db)}")
        self._log(f"  Max rounds: {self.max_rounds}")
        self._log(f"  Precision: {self.prec} digits")
        self._log("=" * 70)

        for round_num in range(1, self.max_rounds + 1):
            self._run_round(round_num)

        # Final synthesis
        self._synthesise_grand_narrative()

        elapsed = time.time() - t0
        report = self._compile_report(elapsed)
        self._log(f"\nTotal elapsed: {elapsed:.1f}s")
        return report

    def _run_round(self, round_num):
        """Execute one round of the discovery loop."""
        t0 = time.time()
        self._log(f"\n{'='*60}")
        self._log(f"  ROUND {round_num} / {self.max_rounds}")
        self._log(f"{'='*60}")

        round_log = {
            "round": round_num,
            "decompositions": 0,
            "connections": 0,
            "patterns": 0,
            "cross_bridges": 0,
            "missing_links": 0,
            "proposals": 0,
            "tested": 0,
        }

        # Phase 1: DECOMPOSE
        self._log("\n  Phase 1: DECOMPOSE -- Structural analysis of all formulas")
        decomps = []
        for formula in self.db:
            d = self.engineer.decompose_formula(formula)
            decomps.append(d)
        round_log["decompositions"] = len(decomps)
        self._log(f"    Decomposed {len(decomps)} formulas")

        if round_num == 1:
            self.all_decompositions = decomps

        # Phase 2: MAP -- Find physics connections
        self._log("\n  Phase 2: MAP -- Physics connections for each component")
        new_connections = []
        for formula in self.db:
            conns = self.bridge.map_formula(formula)
            for c in conns:
                key = (c.formula_id, c.formula_component, c.physics_concept_id)
                if key not in self._seen_conn_keys:
                    self._seen_conn_keys.add(key)
                    new_connections.append(c)
        round_log["connections"] = len(new_connections)
        self.all_connections.extend(new_connections)
        self._log(f"    Found {len(new_connections)} new connections (total unique: {len(self.all_connections)})")

        # Phase 3: BRIDGE -- Cross-formula patterns
        self._log("\n  Phase 3: BRIDGE -- Cross-formula patterns via shared physics")
        patterns = self.engineer.find_cross_formula_patterns(self.db)
        new_patterns = [p for p in patterns if p.id not in self._seen_pattern_ids]
        for p in new_patterns:
            self._seen_pattern_ids.add(p.id)
        round_log["patterns"] = len(new_patterns)
        self.all_patterns.extend(new_patterns)
        self._log(f"    Discovered {len(new_patterns)} new patterns (total: {len(self.all_patterns)})")

        cross = self.bridge.discover_cross_formula(self.db)
        round_log["cross_bridges"] = len(cross)
        self.cross_formula_bridges = cross  # replace each round with updated
        self._log(f"    Found {len(cross)} cross-formula bridges")

        # Phase 4: MISSING LINKS -- What should exist but wasn't found?
        self._log("\n  Phase 4: MISSING LINKS -- Predicted but unverified connections")
        missing = self.bridge.find_missing_links(self.db)
        round_log["missing_links"] = len(missing)
        self.missing_links = missing
        self._log(f"    Identified {len(missing)} missing links to investigate")
        for m in missing[:5]:
            self._log(f"      -> {m['formula_id']} <-> {m['concept_name']} "
                      f"(overlap: {m['overlap_score']:.2f})")

        # Phase 5: PROMOTE -- Upgrade high-overlap missing links to connections
        self._log("\n  Phase 5: PROMOTE -- Upgrading strong missing links")
        promoted = 0
        from ramanujan_physics.physics_map import BridgeConnection
        for m in missing:
            if m["overlap_score"] >= 0.4 and round_num >= 2:
                key = (m["formula_id"], m["overlap_primitives"][0], m["concept_id"])
                if key not in self._seen_conn_keys:
                    self._seen_conn_keys.add(key)
                    conn = BridgeConnection(
                        formula_id=m["formula_id"],
                        formula_component=m["overlap_primitives"][0],
                        physics_concept_id=m["concept_id"],
                        mapping_description=m["suggestion"],
                        strength=0.3 + m["overlap_score"] * 0.4,
                        mechanism=f"Promoted from missing link (overlap {m['overlap_score']:.2f})",
                        testable_prediction=f"Investigate: {m['suggestion']}",
                        is_novel=True,
                        generation=self.bridge.generation,
                    )
                    self.all_connections.append(conn)
                    promoted += 1
        round_log["promoted"] = promoted
        self._log(f"    Promoted {promoted} missing links to novel connections")

        # Phase 6: PROPOSE -- Generalisations
        self._log("\n  Phase 6: PROPOSE -- New formula generalisations")
        new_proposals = self.engineer.propose_generalisations(self.db, new_patterns)
        seen_prop_ids = {p.id for p in self.proposals}
        new_proposals = [p for p in new_proposals if p.id not in seen_prop_ids]
        round_log["proposals"] = len(new_proposals)
        self.proposals.extend(new_proposals)
        self._log(f"    Generated {len(new_proposals)} new proposals (total: {len(self.proposals)})")

        # Phase 7: TEST -- Numerical verification
        self._log("\n  Phase 7: TEST -- Numerical verification of proposals")
        tested = 0
        for p in new_proposals:
            if p.predicted_value == "pi" and p.source_formula in ("CHUD-1988", "RAM-1914-PI"):
                self.engineer.test_proposal(p, evaluator=eval_generalised_pi_series)
                tested += 1
        round_log["tested"] = tested
        self._log(f"    Tested {tested} proposals")

        # Phase 8: REFINE -- Strengthen connections with cross-evidence
        self._log("\n  Phase 8: REFINE -- Strengthening connections with cross-evidence")
        refined = 0
        concept_formula_counts = {}
        for c in self.all_connections:
            key = c.physics_concept_id
            if key not in concept_formula_counts:
                concept_formula_counts[key] = set()
            concept_formula_counts[key].add(c.formula_id)
        for c in self.all_connections:
            nf = len(concept_formula_counts.get(c.physics_concept_id, set()))
            if nf >= 3 and c.strength < 0.95:
                boost = min(0.05, 0.015 * (nf - 2))
                c.strength = min(1.0, round(c.strength + boost, 4))
                refined += 1
        self._log(f"    Refined {refined} connection strengths")

        # Phase 9: META-LEARN -- Adjust strategy
        self._log("\n  Phase 9: META-LEARN -- Strategy adjustment")
        stats = self.bridge.get_statistics()
        self._log(f"    Connection stats: {stats['by_strength']}")
        self._log(f"    Domain distribution: {stats['by_domain']}")

        # Advance generation counters
        self.bridge.advance_generation()
        self.engineer.advance_generation()

        elapsed = time.time() - t0
        round_log["time_sec"] = round(elapsed, 2)
        self.round_logs.append(round_log)
        self._log(f"\n  Round {round_num} completed in {elapsed:.1f}s")

    def _synthesise_grand_narrative(self):
        """Build the grand narrative connecting pi, black holes, and HEP."""
        self._log("\n" + "=" * 70)
        self._log("  GRAND SYNTHESIS: How Pi, Black Holes, and HEP Connect")
        self._log("=" * 70)

        narrative = []

        # === Thread 1: Partitions -> Black Holes ===
        narrative.append({
            "thread": "Partitions and Black Hole Entropy",
            "title": "Partition Asymptotics as a Key Tool in Black Hole Microstate Counting",
            "summary": (
                "Hardy and Ramanujan's 1918 asymptotic formula p(n) ~ exp(pi*sqrt(2n/3))/(4n*sqrt(3)) "
                "gives the growth rate of integer partitions. In 1996, Strominger and Vafa showed that "
                "the microscopic entropy of a specific class of 5-dimensional BPS black holes in "
                "type IIB string theory can be computed by counting D-brane bound states. The "
                "state-counting reduces to a partition-like problem whose asymptotic growth is "
                "governed by the Cardy formula -- which shares the same exponential structure "
                "exp(pi*sqrt(cN/6)) as the Hardy-Ramanujan result. The match between the microscopic "
                "count and the Bekenstein-Hawking area formula S_BH = A/(4G) was the first "
                "successful statistical derivation of black hole entropy. Importantly, the "
                "connection is structural: both Hardy-Ramanujan and the Cardy formula arise from "
                "modular properties of the underlying partition function (1/eta(tau) for integer "
                "partitions, the CFT partition function for D-branes), not from a literal "
                "identification p(n) = number of black hole microstates. The Rademacher exact "
                "formula (1937) extends this to all orders, and each correction term corresponds "
                "to a distinct saddle-point geometry in the dual gravitational path integral."
            ),
            "key_formulas": ["HR-1918-PARTITION", "RADEMACHER-EXACT", "RAM-PART-CONG"],
            "key_physics": ["BH-ENTROPY", "BH-MICROSTATE", "BH-QUANTUM"],
            "evidence_tier": "well-established",
            "evidence_note": "Proven mathematical theorem (Hardy-Ramanujan) + rigorous string theory "
                             "calculation (Strominger-Vafa). The structural analogy is exact; the "
                             "physical identification requires specific string compactification.",
            "citations": [
                "Hardy & Ramanujan, Proc. London Math. Soc. 17, 75 (1918)",
                "Rademacher, Proc. London Math. Soc. 43, 241 (1937)",
                "Strominger & Vafa, Phys. Lett. B 379, 99 (1996)",
                "Dijkgraaf, Maldacena, Moore & Verlinde, hep-th/0005003 (2000)",
            ],
            "depth": "structural_analogy",
        })

        # === Thread 2: Pi formulas -> CY periods -> String compactification ===
        narrative.append({
            "thread": "Pi Formulas and Calabi-Yau Periods",
            "title": "Ramanujan-Type Pi Series and Their Connection to String Compactification Moduli",
            "summary": (
                "Ramanujan's 1914 series for 1/pi and the Chudnovsky brothers' 1988 formula "
                "are instances of hypergeometric functions that also appear as period integrals "
                "of specific Calabi-Yau manifolds. The Picard-Fuchs differential equations "
                "governing these periods are the same equations that generate the Ramanujan-type "
                "series coefficients. In type IIB string theory, CY period integrals determine "
                "gauge coupling constants and the superpotential in N=2 compactifications. "
                "However, the connection is specific: only the particular CY manifolds associated "
                "with CM (complex multiplication) elliptic curves at Heegner discriminants "
                "(d = 163, 67, 43, ...) produce Ramanujan-type rapidly converging pi formulas. "
                "The convergence rate (~14 digits/term for Chudnovsky) reflects the arithmetic "
                "of the j-invariant: j(e^{pi*sqrt(163)}) = 640320^3 + 744. In string theory, "
                "these CM points correspond to special loci in CY moduli space with enhanced "
                "symmetry, not generic compactification geometries. "
                "Concretely: the one-parameter CY threefold defined by "
                "x_1^5+x_2^5+x_3^5+x_4^5+x_5^5 - 5*psi*x_1*x_2*x_3*x_4*x_5 = 0 "
                "(the mirror quintic, studied by Candelas et al. 1991) has a Picard-Fuchs "
                "equation whose solutions at the maximally unipotent monodromy point yield "
                "a 4F3 hypergeometric that is structurally identical to the generating function "
                "of Ramanujan-type series. Similarly, the Apery-like sequence "
                "a(n) = Sum_{k=0}^{n} C(n,k)^2 C(n+k,k)^2 satisfies a degree-3 recurrence "
                "whose associated Picard-Fuchs operator governs periods of a rigid CY threefold "
                "(Beauville, 1986; Zagier, 2009). The resulting 1/pi formula was proven by "
                "Guillera (2002). At the level of individual constants: the Chudnovsky formula "
                "gives 1/pi via the CM point tau = (1+i*sqrt(163))/2 on the modular curve X_0(1)."
            ),
            "key_formulas": ["RAM-1914-PI", "CHUD-1988"],
            "key_physics": ["ST-CY-PERIOD", "ST-MOONSHINE"],
            "evidence_tier": "mixed",
            "evidence_note": (
                "Mathematics: well-established. The Picard-Fuchs / hypergeometric identity "
                "between Ramanujan-type series and CY period integrals is rigorously proven "
                "(Lian-Yau 1996, Yang 2004). The mirror quintic and Apery-like recurrences "
                "provide concrete, fully worked examples. "
                "Physics: strongly suggestive. The interpretation of these periods as "
                "string coupling constants applies only at specific CM points in CY moduli "
                "space, not to arbitrary compactifications."
            ),
            "citations": [
                "Ramanujan, Quart. J. Math. 45, 350 (1914)",
                "Chudnovsky & Chudnovsky, Lect. Notes Math. 1240 (1987)",
                "Candelas, de la Ossa, Green & Parkes, Nucl. Phys. B 359, 21 (1991)",
                "Borwein & Borwein, Pi and the AGM (Wiley, 1987)",
                "Lian & Yau, Comm. Math. Phys. 176, 163 (1996)",
                "Zagier, in Higher-Dimensional Geometry over Finite Fields (IOS Press, 2009)",
                "Guillera, Adv. Appl. Math. 29, 599 (2002)",
            ],
            "depth": "structural_identity",
        })

        # === Thread 3: Mock theta -> Quantum BH ===
        narrative.append({
            "thread": "Mock Theta Functions and Quantum Black Holes",
            "title": "Mock Modular Forms as the Mathematical Framework for Exact BPS Entropy",
            "summary": (
                "In his final letter to Hardy (January 1920), Ramanujan introduced 'mock theta "
                "functions' -- q-hypergeometric functions that transform almost like modular forms "
                "but fail full modularity by a computable 'error' term. In 2002, Zwegers showed "
                "that mock theta functions are the holomorphic parts of harmonic Maass forms, "
                "with the error term (the 'shadow') being a unary theta series. In 2012, "
                "Dabholkar, Murthy, and Zagier demonstrated that the exact degeneracies of "
                "1/4-BPS black holes in N=4 string theory are encoded by mock Jacobi forms -- "
                "a higher-dimensional generalisation of Ramanujan's mock theta functions. The "
                "'non-modularity' that puzzled mathematicians for 80 years corresponds precisely "
                "to the wall-crossing phenomenon in physics: BPS states appear or disappear as "
                "string moduli cross walls of marginal stability, and the shadow term captures "
                "these jumps. This is one of the deepest and most precisely established connections "
                "between Ramanujan's mathematics and modern physics, though it applies specifically "
                "to BPS black holes in N=4 string compactifications, not to quantum gravity in general."
            ),
            "key_formulas": ["RAM-MOCK-THETA"],
            "key_physics": ["BH-MOCK", "BH-QUANTUM", "QFT-VW"],
            "evidence_tier": "well-established",
            "evidence_note": "Rigorous: Zwegers' thesis (2002) + Dabholkar-Murthy-Zagier (2012) "
                             "provide both the mathematical framework and the physical application. "
                             "The connection is exact within N=4 string theory.",
            "citations": [
                "Ramanujan, letter to Hardy, January 1920 (published in Lost Notebook)",
                "Zwegers, Mock Theta Functions, PhD thesis, Utrecht (2002)",
                "Dabholkar, Murthy & Zagier, J. High Energy Phys. 2014:23 (2014), arXiv:1208.4074",
                "Manschot & Moore, Commun. Math. Phys. 299, 827 (2010)",
            ],
            "depth": "exact_match",
        })

        # === Thread 4: zeta(-1) = -1/12 -> Critical dimension ===
        narrative.append({
            "thread": "Zeta Regularisation and String Theory Dimensions",
            "title": "How Analytic Continuation of the Zeta Function Constrains Spacetime Dimension",
            "summary": (
                "Euler first computed zeta(-1) = -1/12 in 1749 via analytic continuation of "
                "sum n^{-s}. Ramanujan independently arrived at the same result in his notebooks "
                "(c. 1913) and used it extensively. In bosonic string theory, the zero-point energy "
                "of the transverse oscillators is regularised as (D-2) * zeta(-1) = -(D-2)/12. "
                "Requiring the absence of negative-norm states (Lorentz invariance) forces this "
                "to equal -1, yielding the critical dimension D = 26. The superstring analogue "
                "gives D = 10. Note that the full derivation requires more than just the zeta "
                "value: conformal anomaly cancellation on the worldsheet and the no-ghost theorem "
                "provide independent confirmations. The same regularisation underlies the Casimir "
                "effect -- a measurable force between conducting plates where the zeta-regularised "
                "vacuum energy contributes -pi^2/(720*a^3) per unit area, in agreement with "
                "experiment (Lamoreaux 1997, Bressi et al. 2002)."
            ),
            "key_formulas": ["RAM-ZETA-REG"],
            "key_physics": ["ST-DIMENSION", "QFT-CASIMIR", "HEP-COSMO"],
            "evidence_tier": "well-established",
            "evidence_note": "The zeta regularisation is a rigorous mathematical procedure. "
                             "The Casimir effect is experimentally confirmed. The D=26 derivation "
                             "is a standard textbook result, though it rests on multiple consistency "
                             "conditions beyond zeta(-1) alone.",
            "citations": [
                "Euler, Novi Commentarii Acad. Sci. Petropolitanae 14, 129 (1749)",
                "Polchinski, String Theory, Vol. 1, Ch. 1 (CUP, 1998)",
                "Casimir, Proc. K. Ned. Akad. Wet. 51, 793 (1948)",
                "Lamoreaux, Phys. Rev. Lett. 78, 5 (1997)",
                "Bressi et al., Phys. Rev. Lett. 88, 041804 (2002)",
            ],
            "depth": "exact_calculation",
        })

        # === Thread 5: Rogers-Ramanujan -> Integrable models -> CFT ===
        narrative.append({
            "thread": "Rogers-Ramanujan Identities, Integrable Models, and CFT",
            "title": "The Chain from Combinatorial Identities to Exactly Solved Physical Models",
            "summary": (
                "The Rogers-Ramanujan identities (Rogers 1894, independently Ramanujan c. 1913) "
                "equate q-hypergeometric sums with infinite products filtered by residues mod 5. "
                "In 1980, Baxter showed that the order parameter of the hard hexagon model -- a "
                "statistical mechanics model of non-overlapping hexagons on a triangular lattice -- "
                "is expressed in terms of the Rogers-Ramanujan continued fraction. This was the "
                "first instance of a two-dimensional lattice model solved exactly using "
                "q-series identities. In 2D conformal field theory, the characters of the (2,5) "
                "Virasoro minimal model (central charge c = 2/5) are precisely the Rogers-Ramanujan "
                "functions. This three-way connection -- combinatorics (partitions with gap conditions), "
                "statistical mechanics (exactly solvable lattice model), and CFT (Virasoro "
                "representation theory) -- is one of the cleanest examples of how Ramanujan's "
                "identities underpin modern mathematical physics."
            ),
            "key_formulas": ["RR-IDENTITY", "JACOBI-THETA"],
            "key_physics": ["SM-HEXAGON", "CFT-VIRASORO", "SM-ISING"],
            "evidence_tier": "well-established",
            "evidence_note": "All three connections are proven: Baxter's exact solution (1980), "
                             "and the RR = minimal model character identification (Rocha-Caridi 1985, "
                             "Kedem et al. 1993).",
            "citations": [
                "Rogers, Proc. London Math. Soc. 25, 318 (1894)",
                "Baxter, J. Phys. A: Math. Gen. 13, L61 (1980)",
                "Rocha-Caridi, in Vertex Operators in Mathematics and Physics (Springer, 1985)",
                "Kedem, Klassen, McCoy & Melzer, Phys. Lett. B 307, 68 (1993)",
            ],
            "depth": "structural_identity",
        })

        # === Thread 6: Moonshine -> Monster -> String Symmetry ===
        narrative.append({
            "thread": "Moonshine, the Monster Group, and String Theory",
            "title": "How the j-Function Connects Number Theory to String Symmetry via Vertex Algebras",
            "summary": (
                "The j-function j(tau) = q^{-1} + 744 + 196884q + ... has Fourier coefficients "
                "that encode dimensions of representations of the Monster group, the largest "
                "sporadic simple group (|M| ~ 8*10^53). Conway and Norton (1979) conjectured "
                "this 'monstrous moonshine', and Borcherds (1992) proved it using a string "
                "theory construction: the moonshine module V^natural is a c=24 vertex operator "
                "algebra (equivalently, a bosonic string compactified on the Leech lattice). "
                "Witten (2007) conjectured that pure 3D gravity with negative cosmological "
                "constant might have the Monster as its symmetry group, with partition function "
                "J(tau) = j(tau) - 744. This remains an open conjecture. The j-function also "
                "connects to Ramanujan's pi formulas via singular moduli of CM elliptic curves: "
                "j(e^{pi*sqrt(163)}) = 640320^3 + 744, which is the convergence base of the "
                "Chudnovsky formula. These are established mathematical facts; the interpretation "
                "of Monster symmetry as a fundamental symmetry of quantum gravity remains speculative."
            ),
            "key_formulas": ["J-FUNCTION", "RAM-TAU-DELTA", "DEDEKIND-ETA"],
            "key_physics": ["ST-MOONSHINE", "QG-ADS3", "ST-AMPLITUDE"],
            "evidence_tier": "mixed",
            "evidence_note": "Monstrous moonshine is a proven theorem (Borcherds 1992, Fields Medal). "
                             "The VOA construction is rigorous string theory. Witten's pure gravity "
                             "conjecture (2007) is speculative and not universally accepted.",
            "citations": [
                "Conway & Norton, Bull. London Math. Soc. 11, 308 (1979)",
                "Frenkel, Lepowsky & Meurman, Vertex Operator Algebras and the Monster (Academic, 1988)",
                "Borcherds, Invent. Math. 109, 405 (1992)",
                "Witten, arXiv:0706.3359 (2007)",
            ],
            "depth": "deep_structural",
        })

        # === Thread 7: The Master Thread -- How Pi connects everything ===
        narrative.append({
            "thread": "Pi as a Structural Connector",
            "title": "Why Pi Appears Across These Connections: Modular Symmetry as the Unifying Principle",
            "summary": (
                "Pi recurs across all these connections not as a coincidence but because of a "
                "common mathematical substrate: modular symmetry. Modular forms are functions on "
                "the upper half-plane quotiented by SL(2,Z), and the Fourier variable q = e^{2*pi*i*tau} "
                "injects pi into every expansion. The specific mechanisms are: "
                "(1) Partition asymptotics: the circle method evaluates contour integrals in the "
                "tau-plane, producing exp(pi*sqrt(2n/3)) from the modular properties of 1/eta(tau). "
                "The same modular structure, via the Cardy formula, gives the CFT state count that "
                "reproduces black hole entropy in specific string compactifications. "
                "(2) Ramanujan-type pi series: these compute a specific period (1/pi) of CM "
                "elliptic curves at Heegner discriminants. The Heegner property (class number 1) "
                "ensures rapid convergence. In string theory, the same CM points appear as enhanced-"
                "symmetry loci in CY moduli space, though not all CY periods reduce to pi formulas. "
                "(3) Zeta regularisation: zeta(-1) = -B_2/2 = -1/12 enters string theory via "
                "the worldsheet conformal anomaly, and the Casimir effect via vacuum energy sums. "
                "(4) Mock modularity: the shadow of a mock modular form is fixed by the modular "
                "completion, with pi entering through the non-holomorphic Eichler integral. "
                "The unifying principle is that modular symmetry -- the requirement that physics "
                "be invariant under large diffeomorphisms of the worldsheet torus -- forces pi "
                "to appear whenever partition-counting, spectral, or path-integral structures "
                "are governed by SL(2,Z) or its subgroups."
            ),
            "key_formulas": ["all"],
            "key_physics": ["all"],
            "evidence_tier": "interpretive",
            "evidence_note": (
                "Each individual mechanism (circle method, Cardy formula, CY periods, "
                "zeta regularisation) is rigorously established. The unifying narrative "
                "that modular symmetry is the common thread is a well-motivated "
                "interpretation, not a single proven theorem."
            ),
            "citations": [
                "Cardy, Nucl. Phys. B 270, 186 (1986)",
                "Di Francesco, Mathieu & Senechal, Conformal Field Theory (Springer, 1997)",
                "Zagier, in Frontiers in Number Theory, Physics, and Geometry I (Springer, 2006)",
            ],
            "depth": "interpretive_synthesis",
        })

        self.grand_narrative = narrative

        for n in narrative:
            self._log(f"\n  THREAD: {n['thread']}")
            self._log(f"  {n['title']}")
            tier = n.get('evidence_tier', 'unclassified')
            self._log(f"  Evidence tier: {tier} | Depth: {n['depth']}")

    def _compile_report(self, elapsed):
        """Compile the full results report."""
        stats = self.bridge.get_statistics()

        report = {
            "meta": {
                "engine": "Ramanujan-Physics Bridge v1.1",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "elapsed_seconds": round(elapsed, 2),
                "rounds": self.max_rounds,
                "formula_count": len(self.db),
                "precision": self.prec,
                "libraries": {
                    "mpmath": mpmath.__version__,
                    "python": sys.version.split()[0],
                },
                "scoring_rubric": {
                    "base_score": 0.3,
                    "annotated_match_boost": "+0.4 when formula carries pre-annotated physics_connections matching the concept",
                    "domain_hint_boost": "+0.2 when formula's physics_hint domain matches concept domain",
                    "modular_property_boost": "+0.15 when formula has modular properties and concept involves modular forms",
                    "thresholds": {
                        "strong": ">= 0.7",
                        "medium": "0.4 -- 0.7",
                        "weak": "< 0.4",
                    },
                    "note": "Scores reflect structural-pattern matching, not causal evidence. "
                            "A high score means the mathematical primitive maps well to the "
                            "physics concept, not that a causal link is established.",
                },
                "evidence_tiers": {
                    "well-established": "Proven theorems or experimentally confirmed results",
                    "strongly_suggestive": "Substantial evidence from multiple independent lines; not yet fully proven",
                    "mixed": "Some rigorous results combined with conjectural extensions",
                    "speculative": "Plausible structural analogies without direct proof",
                    "interpretive": "Well-motivated synthesis of established results into a narrative",
                },
                "corpus": "14 canonical Ramanujan-adjacent formulas x 24 physics concepts across 8 domains",
            },
            "statistics": stats,
            "round_logs": self.round_logs,
            "decompositions": self.all_decompositions,
            "connections": [
                {
                    "formula_id": c.formula_id,
                    "component": c.formula_component,
                    "physics_concept": c.physics_concept_id,
                    "strength": c.strength,
                    "mapping": c.mapping_description,
                    "mechanism": c.mechanism,
                    "prediction": c.testable_prediction,
                    "generation": c.generation,
                }
                for c in self.all_connections
            ],
            "patterns": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "formulas": p.formulas_involved,
                    "confidence": p.confidence,
                    "physics_implication": p.physics_implication,
                }
                for p in self.all_patterns
            ],
            "cross_formula_bridges": self.cross_formula_bridges[:50],
            "missing_links": self.missing_links[:20],
            "proposals": [
                {
                    "id": p.id,
                    "source": p.source_formula,
                    "params": str(p.new_parameters),
                    "predicted": p.predicted_value,
                    "actual": p.actual_value,
                    "status": p.status,
                    "motivation": p.physics_motivation,
                }
                for p in self.proposals
            ],
            "grand_narrative": self.grand_narrative,
        }

        # Save JSON
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        with open(results_dir / "ramanujan_physics_results.json", "w") as f:
            json.dump(report, f, indent=2, cls=DataclassEncoder)
        self._log(f"\nResults saved to results/ramanujan_physics_results.json")

        return report

    def _log(self, msg):
        if self.verbose:
            print(msg)


def run_discovery(rounds=5, precision=100, verbose=True):
    """Convenience function to run the discovery engine."""
    config = {
        "max_rounds": rounds,
        "precision": precision,
        "verbose": verbose,
    }
    engine = DiscoveryEngine(config)
    return engine.run()
