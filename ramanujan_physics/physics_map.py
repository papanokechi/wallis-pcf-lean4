"""
physics_map.py - Maps mathematical structures in Ramanujan formulas
to physics concepts across black holes, string theory, QFT, and statistical mechanics.

The PhysicsBridge class takes decomposed formula components and finds
all physics interpretations, scoring each connection by strength.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PhysicsConcept:
    """A physics concept with its mathematical signature."""
    id: str
    domain: str
    name: str
    description: str
    math_signatures: list       # what math patterns trigger this concept
    key_formula: str            # the defining equation
    energy_scale: str           # "Planck", "QCD", "electroweak", "condensed_matter"
    discovered_year: int
    references: list = field(default_factory=list)


@dataclass
class BridgeConnection:
    """A discovered connection between a Ramanujan structure and physics."""
    formula_id: str
    formula_component: str
    physics_concept_id: str
    mapping_description: str
    strength: float             # 0-1
    mechanism: str              # how the math maps
    testable_prediction: str    # what the connection predicts
    is_novel: bool = False      # discovered by agent vs. known
    generation: int = 0         # iteration when discovered


# ---------------------------------------------------------------------------
# Physics concept database: the target space for mapping
# ---------------------------------------------------------------------------

PHYSICS_CONCEPTS = [
    # === BLACK HOLES ===
    PhysicsConcept(
        "BH-ENTROPY", "black_holes", "Bekenstein-Hawking entropy",
        "S = A/(4*G_N*hbar) = pi*r_s^2/(l_P^2). Black hole entropy is proportional to "
        "horizon area, not volume. This is the holographic principle.",
        ["exponential_growth_sqrt_n", "partition_count", "saddle_point", "modular_weight"],
        "S_BH = A / (4 G_N)", "Planck", 1973,
        ["Bekenstein 1973", "Hawking 1975"]
    ),
    PhysicsConcept(
        "BH-MICROSTATE", "black_holes", "Black hole microstate counting",
        "Strominger-Vafa: Omega(N) = p(N) ~ exp(pi*sqrt(2N/3)) for D-brane bound states. "
        "The degeneracy of BPS states exactly reproduces Bekenstein-Hawking entropy.",
        ["partition_function", "hardy_ramanujan_asymptotic", "modular_form"],
        "Omega(Q) = p(Q_L) * p(Q_R)", "Planck", 1996,
        ["Strominger & Vafa 1996"]
    ),
    PhysicsConcept(
        "BH-QUANTUM", "black_holes", "Quantum corrections to BH entropy",
        "Beyond leading order: exact BH entropy via Rademacher expansion. "
        "Each term k=1,2,... in the Rademacher sum corresponds to a saddle-point "
        "geometry (orbifold) in the gravitational path integral.",
        ["rademacher_sum", "bessel_integral", "kloosterman_sum", "mock_theta"],
        "Omega_exact(n) = 2*pi/(24n-1)^{3/4} * Sum A_k(n)/k * I_{3/2}(...)", "Planck", 2000,
        ["Dijkgraaf et al. 2000", "Dabholkar, Murthy & Zagier 2012"]
    ),
    PhysicsConcept(
        "BH-MOCK", "black_holes", "Mock modular forms and BH degeneracies",
        "1/4-BPS black holes in N=4 string theory have exact degeneracies given by "
        "mock modular forms. The non-modularity encodes wall-crossing.",
        ["mock_theta", "appell_lerch", "harmonic_maass"],
        "d(n,l) = Coeff of mock Jacobi form", "Planck", 2012,
        ["Dabholkar, Murthy & Zagier 2012"]
    ),

    # === STRING THEORY ===
    PhysicsConcept(
        "ST-DIMENSION", "string_theory", "Critical dimension from zeta regularisation",
        "Bosonic string: sum_{n=1}^inf n = zeta(-1) = -1/12. "
        "Requiring Lorentz invariance: (D-2)*(-1/12) = -1 => D = 26.",
        ["zeta_regularisation", "bernoulli", "dirichlet_series"],
        "D = 2 - 24*zeta(-1) = 26", "Planck", 1970,
        ["Polchinski 2005"]
    ),
    PhysicsConcept(
        "ST-AMPLITUDE", "string_theory", "String amplitude modular invariance",
        "One-loop string amplitudes integrate over the modular fundamental domain. "
        "The integrand is built from eta, theta, and Eisenstein series.",
        ["dedekind_eta", "theta_function", "eisenstein_series", "modular_weight"],
        "A_1-loop = integral_{F} d^2tau/tau_2^2 * Z(tau,bar{tau})", "Planck", 1987,
        ["Green, Schwarz & Witten 1987"]
    ),
    PhysicsConcept(
        "ST-CY-PERIOD", "string_theory", "Calabi-Yau periods and pi formulas",
        "The Ramanujan-Chudnovsky pi series compute period integrals of specific CY 3-folds. "
        "These periods determine gauge couplings in N=2 compactifications.",
        ["hypergeometric_sum", "factorial_ratio", "exponential_decay"],
        "omega_i = integral_{gamma_i} Omega_CY", "Planck", 1991,
        ["Candelas et al. 1991"]
    ),
    PhysicsConcept(
        "ST-MOONSHINE", "string_theory", "Monstrous moonshine",
        "The j-function Fourier coefficients = dimensions of Monster group representations. "
        "The moonshine module is a c=24 CFT (vertex operator algebra).",
        ["j_function", "eisenstein_series", "q_product"],
        "j(tau) = q^{-1} + 744 + 196884q + ...", "Planck", 1979,
        ["Conway & Norton 1979", "Borcherds 1992"]
    ),
    PhysicsConcept(
        "ST-S-DUALITY", "string_theory", "S-duality and Eisenstein series",
        "Non-holomorphic Eisenstein series are the unique SL(2,Z)-invariant functions "
        "giving exact answers for graviton scattering at each derivative order.",
        ["eisenstein_series", "modular_weight"],
        "E_{3/2}(Omega) = sum_{(m,n) != (0,0)} Omega_2^{3/2}/|m+n*Omega|^3", "Planck", 1997,
        ["Green & Gutperle 1997"]
    ),
    PhysicsConcept(
        "ST-DBRANE", "string_theory", "D-brane partition function",
        "The partition function of N coincident D-branes is given by "
        "the symmetric product orbifold, whose states map to integer partitions.",
        ["q_product", "partition_function", "factorial_ratio"],
        "Z_N = prod_{n>=1} 1/(1-q^n)^N", "Planck", 1995,
        ["Polchinski 1995"]
    ),

    # === QUANTUM FIELD THEORY ===
    PhysicsConcept(
        "QFT-CASIMIR", "qft", "Casimir effect",
        "Zero-point energy between plates = -pi^2*hbar*c/(720*a^3) per unit area. "
        "Uses zeta regularisation sum n = -1/12.",
        ["zeta_regularisation", "bernoulli"],
        "E_Casimir = -pi^2/(720*a^3)", "electroweak", 1948,
        ["Casimir 1948", "Lamoreaux 1997"]
    ),
    PhysicsConcept(
        "QFT-INSTANTON", "qft", "Instanton contributions (Nekrasov)",
        "N=2 gauge theory instanton partition function involves eta-products "
        "and equivariant counting on moduli spaces of instantons.",
        ["q_product", "eisenstein_series"],
        "Z_inst = sum q^k * Z_k", "electroweak", 2003,
        ["Nekrasov 2003"]
    ),
    PhysicsConcept(
        "QFT-VW", "qft", "Vafa-Witten partition functions",
        "Partition functions of topologically twisted N=4 SYM on 4-manifolds "
        "are mock modular forms. Wall-crossing creates the shadow.",
        ["mock_theta", "modular_weight", "q_product"],
        "Z_VW(tau) = mock modular form", "electroweak", 1994,
        ["Vafa & Witten 1994"]
    ),

    # === STATISTICAL MECHANICS ===
    PhysicsConcept(
        "SM-ISING", "stat_mech", "Ising model partition function",
        "2D Ising at criticality: partition function built from theta functions. "
        "Critical exponents from conformal weights of Virasoro representations.",
        ["theta_function", "q_product", "modular_weight"],
        "Z_Ising = |theta_3|^{1/2} + |theta_4|^{1/2} + |theta_2|^{1/2}", "condensed_matter", 1944,
        ["Onsager 1944"]
    ),
    PhysicsConcept(
        "SM-HEXAGON", "stat_mech", "Hard hexagon model (exact solution)",
        "Baxter solved the hard hexagon model using Rogers-Ramanujan identities. "
        "The order parameter is an algebraic function of the RR continued fraction.",
        ["continued_fraction", "q_product", "theta_function"],
        "kappa = R(q)^5 where R is Rogers-Ramanujan CF", "condensed_matter", 1980,
        ["Baxter 1980"]
    ),
    PhysicsConcept(
        "SM-BOSE", "stat_mech", "Bose-Einstein statistics and partitions",
        "Integer partitions = boson occupation numbers. p(n) counts ways "
        "to distribute n quanta among harmonic oscillator modes.",
        ["partition_function", "q_product"],
        "Z_BE = prod 1/(1-q^n) = sum p(n) q^n", "condensed_matter", 1924,
        ["Bose 1924", "Einstein 1925"]
    ),

    # === CFT ===
    PhysicsConcept(
        "CFT-VIRASORO", "cft", "Virasoro minimal model characters",
        "Characters of irreducible Virasoro representations for minimal models "
        "are given by Rogers-Ramanujan type identities.",
        ["continued_fraction", "q_product", "theta_function"],
        "chi_{r,s}(q) = q^{h-c/24} * RR-type product", "Planck", 1985,
        ["Rocha-Caridi 1985"]
    ),
    PhysicsConcept(
        "CFT-CENTRAL", "cft", "Central charge and conformal anomaly",
        "The q^{c/24} prefactor in q-expansion = e^{-beta*E_0} where "
        "E_0 = -pi*c/(6*L) is the Casimir energy of the CFT on a circle.",
        ["q_product", "bernoulli", "modular_weight"],
        "Z = q^{-c/24} * sum d(n) q^n", "Planck", 1986,
        ["Cardy 1986"]
    ),

    # === QUANTUM GRAVITY ===
    PhysicsConcept(
        "QG-ADS3", "quantum_gravity", "AdS_3 gravity and modular forms",
        "Pure 3D gravity partition function is a modular function. "
        "The sum over geometries = sum over SL(2,Z) images of thermal AdS.",
        ["modular_weight", "rademacher_sum", "eisenstein_series"],
        "Z_grav(tau) = |j(tau)-744|^2 (conjectured)", "Planck", 2007,
        ["Witten 2007", "Maloney & Witten 2010"]
    ),
    PhysicsConcept(
        "QG-3MANIFOLD", "quantum_gravity", "3-manifold invariants and mock theta",
        "WRT invariants of 3-manifolds are quantum modular forms, closely "
        "related to Ramanujan's mock theta functions.",
        ["mock_theta", "rademacher_sum"],
        "Z_WRT(M; q) ~ mock theta function", "Planck", 1999,
        ["Lawrence & Zagier 1999"]
    ),

    # === HIGH ENERGY PHYSICS / PHENOMENOLOGY ===
    PhysicsConcept(
        "HEP-COSMO", "cosmology", "Cosmological constant and vacuum energy",
        "The cosmological constant Lambda ~ <rho_vac> involves summing "
        "zero-point energies of all fields. Zeta regularisation is standard tool.",
        ["zeta_regularisation", "bernoulli", "dirichlet_series"],
        "Lambda = 8*pi*G*<rho_vac>", "Planck", 1989,
        ["Weinberg 1989"]
    ),
    PhysicsConcept(
        "HEP-AMPLITUDES", "high_energy_physics", "Scattering amplitudes and periods",
        "Multi-loop Feynman integrals evaluate to periods of algebraic varieties. "
        "The same hypergeometric functions in Ramanujan pi-series appear here.",
        ["hypergeometric_sum", "factorial_ratio", "bessel_integral"],
        "I_Feynman = integral of algebraic function = period", "electroweak", 2010,
        ["Bloch, Kerr & Vanhove 2015"]
    ),
]


# ---------------------------------------------------------------------------
# Mapping rules: which formula primitives trigger which physics concepts
# ---------------------------------------------------------------------------

PRIMITIVE_TO_PHYSICS = {
    "hypergeometric_sum": ["ST-CY-PERIOD", "HEP-AMPLITUDES"],
    "factorial_ratio": ["ST-CY-PERIOD", "BH-MICROSTATE", "ST-DBRANE", "HEP-AMPLITUDES"],
    "exponential_decay": ["BH-ENTROPY", "ST-CY-PERIOD", "SM-BOSE"],
    "modular_weight": ["ST-AMPLITUDE", "BH-ENTROPY", "SM-ISING", "CFT-CENTRAL", "QG-ADS3", "ST-S-DUALITY"],
    "continued_fraction": ["SM-HEXAGON", "CFT-VIRASORO"],
    "q_product": ["ST-AMPLITUDE", "ST-DBRANE", "SM-BOSE", "SM-ISING", "SM-HEXAGON",
                  "QFT-INSTANTON", "QFT-VW", "CFT-CENTRAL"],
    "theta_function": ["SM-ISING", "ST-AMPLITUDE", "CFT-VIRASORO"],
    "eisenstein_series": ["ST-S-DUALITY", "ST-AMPLITUDE", "ST-MOONSHINE", "QG-ADS3"],
    "mock_theta": ["BH-MOCK", "BH-QUANTUM", "QFT-VW", "QG-3MANIFOLD"],
    "rademacher_sum": ["BH-QUANTUM", "QG-ADS3"],
    "pochhammer": ["HEP-AMPLITUDES"],
    "bernoulli": ["ST-DIMENSION", "QFT-CASIMIR", "HEP-COSMO", "CFT-CENTRAL"],
    "ramanujan_tau": ["ST-MOONSHINE"],
    "dirichlet_series": ["ST-DIMENSION", "HEP-COSMO"],
    "bessel_integral": ["BH-QUANTUM", "HEP-AMPLITUDES"],
    "saddle_point": ["BH-ENTROPY", "BH-QUANTUM"],
}


class PhysicsBridge:
    """Maps mathematical structures in Ramanujan formulas to physics concepts."""

    def __init__(self):
        self.concepts = {c.id: c for c in PHYSICS_CONCEPTS}
        self.connections_found = []
        self.generation = 0

    def map_formula(self, formula):
        """Find all physics connections for a given RamanujanFormula."""
        connections = []

        for comp in formula.components:
            prim = comp.primitive
            if prim in PRIMITIVE_TO_PHYSICS:
                for concept_id in PRIMITIVE_TO_PHYSICS[prim]:
                    concept = self.concepts.get(concept_id)
                    if not concept:
                        continue
                    # Score the connection strength
                    strength = self._score_connection(formula, comp, concept)
                    conn = BridgeConnection(
                        formula_id=formula.id,
                        formula_component=prim,
                        physics_concept_id=concept_id,
                        mapping_description=self._describe_mapping(formula, comp, concept),
                        strength=strength,
                        mechanism=comp.physics_hint or concept.description,
                        testable_prediction=self._generate_prediction(formula, concept),
                        generation=self.generation,
                    )
                    connections.append(conn)

        # Check for synergistic connections (multiple primitives pointing to same physics)
        concept_scores = {}
        for c in connections:
            if c.physics_concept_id not in concept_scores:
                concept_scores[c.physics_concept_id] = []
            concept_scores[c.physics_concept_id].append(c.strength)

        # Boost strength when multiple components connect to same concept
        for c in connections:
            scores = concept_scores[c.physics_concept_id]
            if len(scores) > 1:
                boost = min(0.15, 0.05 * (len(scores) - 1))
                c.strength = min(1.0, c.strength + boost)

        self.connections_found.extend(connections)
        return connections

    def discover_cross_formula(self, db):
        """Find connections BETWEEN formulas via shared physics concepts."""
        cross = []
        # Build: concept_id -> list of formula_ids
        concept_to_formulas = {}
        for f in db:
            for comp in f.components:
                prim = comp.primitive
                if prim in PRIMITIVE_TO_PHYSICS:
                    for cid in PRIMITIVE_TO_PHYSICS[prim]:
                        if cid not in concept_to_formulas:
                            concept_to_formulas[cid] = set()
                        concept_to_formulas[cid].add(f.id)

        for cid, fids in concept_to_formulas.items():
            fid_list = sorted(fids)
            for i in range(len(fid_list)):
                for j in range(i+1, len(fid_list)):
                    concept = self.concepts.get(cid)
                    cross.append({
                        "formula_a": fid_list[i],
                        "formula_b": fid_list[j],
                        "physics_bridge": cid,
                        "concept_name": concept.name if concept else cid,
                        "domain": concept.domain if concept else "unknown",
                        "description": f"Both {fid_list[i]} and {fid_list[j]} connect to "
                                       f"{concept.name if concept else cid} via shared mathematical structure.",
                    })
        return cross

    def find_missing_links(self, db):
        """Identify physics concepts that SHOULD connect to a formula but don't yet.
        These are predictions: the agent suggests new connections to investigate."""
        missing = []
        for f in db:
            connected_concepts = set()
            for comp in f.components:
                if comp.primitive in PRIMITIVE_TO_PHYSICS:
                    connected_concepts.update(PRIMITIVE_TO_PHYSICS[comp.primitive])

            # Check: are there physics concepts with similar math_signatures not yet linked?
            formula_primitives = {comp.primitive for comp in f.components}
            for concept in PHYSICS_CONCEPTS:
                if concept.id in connected_concepts:
                    continue
                # Count how many of the concept's math_signatures overlap
                overlap = len(set(concept.math_signatures) & formula_primitives)
                if overlap > 0:
                    missing.append({
                        "formula_id": f.id,
                        "concept_id": concept.id,
                        "concept_name": concept.name,
                        "overlap_primitives": list(set(concept.math_signatures) & formula_primitives),
                        "overlap_score": overlap / max(len(concept.math_signatures), 1),
                        "suggestion": f"Investigate whether {f.name} connects to {concept.name} "
                                      f"via shared {', '.join(set(concept.math_signatures) & formula_primitives)}",
                    })

        missing.sort(key=lambda x: x["overlap_score"], reverse=True)
        return missing

    def _score_connection(self, formula, component, concept):
        """Score how strong a formula-component -> physics connection is.

        Scoring rubric
        ---------------
        All scores reflect *structural-pattern matching*, not causal evidence.
        A high score means the mathematical primitive maps well to the physics
        concept -- it does *not* mean a causal link is proven.

        base score:  0.3 (any primitive match via PRIMITIVE_TO_PHYSICS)
          +up to 0.7 if formula carries a pre-annotated PhysicsLink whose
                      domain matches the concept (takes whichever is higher)
          +0.1       if the component's physics_hint text mentions the
                      concept's domain keyword
          +0.05      if the formula has modular properties AND the concept
                      lists 'modular_weight' in its math_signatures
          +0.05-0.15 synergy boost (applied in map_formula) when multiple
                      components of the same formula point to the same concept

        Thresholds used downstream:
          strong:  score >= 0.7
          medium:  0.4 <= score < 0.7
          weak:    score < 0.4
        """
        base = 0.3  # All primitive-based matches start at 0.3

        # Boost if the formula already has annotated physics connections to this domain
        for pl in formula.physics_connections:
            if pl.domain == concept.domain:
                base = max(base, pl.strength)

        # Boost if the component's physics_hint mentions the concept's domain
        if concept.domain in component.physics_hint.lower():
            base = min(1.0, base + 0.1)

        # Boost for modular properties match
        if formula.modular_properties and concept.math_signatures:
            if "modular_weight" in concept.math_signatures and formula.modular_properties:
                base = min(1.0, base + 0.05)

        return round(base, 3)

    def _describe_mapping(self, formula, component, concept):
        """Generate a human-readable description of the mapping."""
        return (f"The {component.primitive} structure in {formula.name} "
                f"({component.role}) maps to {concept.name}: "
                f"{component.physics_hint or 'structural analogy'}")

    def _generate_prediction(self, formula, concept):
        """Generate a testable prediction from the connection."""
        predictions = {
            "BH-ENTROPY": f"The asymptotic growth of {formula.name} should match S_BH = pi*sqrt(2N/3)",
            "BH-MICROSTATE": f"D-brane bound state counting should reproduce {formula.name} coefficients",
            "BH-QUANTUM": f"Rademacher-type corrections to {formula.name} should match quantum BH entropy",
            "BH-MOCK": f"Wall-crossing corrections to {formula.name} should be captured by mock modular completion",
            "ST-DIMENSION": f"Regularisation of {formula.name} should give critical dimension constraint",
            "ST-AMPLITUDE": f"Modular integration of {formula.name} should give finite string amplitude",
            "ST-CY-PERIOD": f"The parameters in {formula.name} should correspond to CY moduli",
            "ST-MOONSHINE": f"Coefficients of {formula.name} should decompose into Monster group representations",
            "QFT-CASIMIR": f"The regularised value of {formula.name} should match Casimir energy measurement",
            "SM-ISING": f"Critical behavior near q->1 in {formula.name} should give Ising critical exponents",
            "SM-HEXAGON": f"The {formula.name} at specific q should give hard hexagon order parameter",
        }
        return predictions.get(concept.id,
                               f"The mathematical structure of {formula.name} should appear in {concept.name}")

    def advance_generation(self):
        """Move to next iteration."""
        self.generation += 1

    def get_statistics(self):
        """Summarise all connections found."""
        by_domain = {}
        by_formula = {}
        by_strength = {"strong": 0, "medium": 0, "weak": 0}
        novel_count = 0

        for c in self.connections_found:
            concept = self.concepts.get(c.physics_concept_id)
            domain = concept.domain if concept else "unknown"
            by_domain[domain] = by_domain.get(domain, 0) + 1
            by_formula[c.formula_id] = by_formula.get(c.formula_id, 0) + 1
            if c.strength >= 0.8:
                by_strength["strong"] += 1
            elif c.strength >= 0.5:
                by_strength["medium"] += 1
            else:
                by_strength["weak"] += 1
            if c.is_novel:
                novel_count += 1

        return {
            "total_connections": len(self.connections_found),
            "by_domain": by_domain,
            "by_formula": by_formula,
            "by_strength": by_strength,
            "novel_count": novel_count,
            "generation": self.generation,
        }
