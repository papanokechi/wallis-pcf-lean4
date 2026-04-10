"""
reverse_engineer.py - Structural decomposition and reverse-engineering of Ramanujan formulas.

The ReverseEngineer class:
1. Decomposes formulas into primitive components
2. Identifies hidden symmetries and structural patterns
3. Finds parameter relationships across formula families
4. Proposes generalisation directions
5. Numerically verifies structural hypotheses
"""

from dataclasses import dataclass, field
from typing import Optional
import mpmath
from mpmath import mp


@dataclass
class StructuralPattern:
    """A pattern found across multiple formulas."""
    id: str
    name: str
    description: str
    formulas_involved: list     # formula IDs
    primitives_shared: list     # shared structural primitives
    parameter_relationship: str # e.g. "a = 26390, b = 545140134: b/a ~ 20627.5 ~ ?"
    physics_implication: str
    confidence: float
    generation: int = 0


@dataclass
class GeneralisationProposal:
    """A proposed new formula derived from structural analysis."""
    id: str
    source_formula: str         # which formula it generalises
    new_parameters: dict        # the proposed parameter values
    predicted_value: str        # what we expect it to evaluate to
    actual_value: Optional[str] = None
    error: Optional[float] = None
    status: str = "proposed"    # proposed, tested, confirmed, falsified
    physics_motivation: str = ""
    generation: int = 0


class ReverseEngineer:
    """Reverse-engineers Ramanujan formulas by structural decomposition."""

    def __init__(self, prec=100):
        self.prec = prec
        self.patterns_found = []
        self.proposals = []
        self.generation = 0
        mp.dps = prec

    def decompose_formula(self, formula):
        """Full structural decomposition of a single formula."""
        analysis = {
            "formula_id": formula.id,
            "family": formula.family,
            "components": [],
            "symmetries": [],
            "hidden_constants": [],
            "convergence_analysis": None,
            "modular_analysis": None,
        }

        # Decompose each component
        for comp in formula.components:
            comp_analysis = {
                "primitive": comp.primitive,
                "role": comp.role,
                "physics_hint": comp.physics_hint,
            }

            # Analyse specific primitives
            if comp.primitive == "factorial_ratio":
                comp_analysis["combinatorial_meaning"] = self._analyse_factorial_ratio(comp.parameters)
            elif comp.primitive == "exponential_decay":
                comp_analysis["decay_analysis"] = self._analyse_decay(comp.parameters, formula.parameters)
            elif comp.primitive == "hypergeometric_sum":
                comp_analysis["hypergeometric_type"] = self._classify_hypergeometric(comp.parameters)
            elif comp.primitive == "q_product":
                comp_analysis["product_analysis"] = self._analyse_q_product(comp.parameters)
            elif comp.primitive == "modular_weight":
                comp_analysis["modular_analysis"] = self._analyse_modularity(comp.parameters, formula.modular_properties)
            elif comp.primitive == "mock_theta":
                comp_analysis["mock_analysis"] = self._analyse_mock(comp.parameters)

            analysis["components"].append(comp_analysis)

        # Find hidden constants
        analysis["hidden_constants"] = self._find_hidden_constants(formula)

        # Symmetry analysis
        analysis["symmetries"] = self._find_symmetries(formula)

        # Convergence rate
        analysis["convergence_analysis"] = self._analyse_convergence(formula)

        return analysis

    def find_cross_formula_patterns(self, db):
        """Find structural patterns shared across multiple formulas."""
        patterns = []

        # 1. Common primitive combinations
        primitive_sets = {}
        for f in db:
            prims = frozenset(c.primitive for c in f.components)
            if prims not in primitive_sets:
                primitive_sets[prims] = []
            primitive_sets[prims].append(f.id)

        for prims, fids in primitive_sets.items():
            if len(fids) >= 2:
                patterns.append(StructuralPattern(
                    id=f"SHARED-PRIMS-{'-'.join(sorted(prims)[:2])}",
                    name=f"Shared {', '.join(sorted(prims)[:3])} structure",
                    description=f"Formulas {', '.join(fids)} share the same primitive decomposition: "
                                f"{', '.join(sorted(prims))}",
                    formulas_involved=fids,
                    primitives_shared=sorted(prims),
                    parameter_relationship="See individual analyses",
                    physics_implication="Shared structure suggests a common deep origin",
                    confidence=0.6 + 0.1 * min(len(prims), 4),
                    generation=self.generation,
                ))

        # 2. Parameter relationships across pi-series
        pi_formulas = [f for f in db if f.family == "pi_series"]
        if len(pi_formulas) >= 2:
            patterns.extend(self._analyse_pi_series_family(pi_formulas))

        # 3. Modular form connections
        modular_formulas = [f for f in db if f.modular_properties]
        if len(modular_formulas) >= 2:
            patterns.extend(self._analyse_modular_family(modular_formulas))

        # 4. Partition-BH entropy bridge
        partition_formulas = [f for f in db if f.family == "partition"]
        if partition_formulas:
            patterns.extend(self._analyse_partition_bh_bridge(partition_formulas))

        # 5. The big connected web: q-products appearing everywhere
        q_formulas = [f for f in db if any(c.primitive == "q_product" for c in f.components)]
        if len(q_formulas) >= 2:
            patterns.append(StructuralPattern(
                id="Q-PRODUCT-WEB",
                name="Universal q-product web",
                description=f"{len(q_formulas)} formulas contain q-product structure: "
                            f"{', '.join(f.id for f in q_formulas)}. "
                            "The q-product (1-q^n) is the universal building block connecting "
                            "partition functions (stat mech) to eta functions (string theory) "
                            "to modular forms (number theory).",
                formulas_involved=[f.id for f in q_formulas],
                primitives_shared=["q_product"],
                parameter_relationship="All reduce to prod (1-q^n)^a for various a",
                physics_implication="The Dedekind eta is the master object: eta^{-2} = bosons, "
                                   "eta^{-24} = bosonic string, eta^{24} = Delta = cusp form",
                confidence=0.95,
                generation=self.generation,
            ))

        self.patterns_found.extend(patterns)
        return patterns

    def propose_generalisations(self, db, patterns):
        """Generate new formula proposals based on discovered patterns."""
        proposals = []

        # 1. New pi-series from parameter extrapolation
        for f in db:
            if f.family == "pi_series" and f.parameters:
                proposals.extend(self._extrapolate_pi_parameters(f))

        # 2. New mock theta -> physics bridges
        for f in db:
            if f.family == "mock_theta":
                proposals.extend(self._propose_mock_physics(f))

        # 3. Modular form weight laddering
        modular = [f for f in db if f.modular_properties.get("weight")]
            
        if modular:
            proposals.extend(self._propose_weight_ladder(modular))

        self.proposals.extend(proposals)
        return proposals

    def test_proposal(self, proposal, evaluator=None):
        """Numerically test a generalisation proposal."""
        if evaluator is None:
            proposal.status = "untestable"
            return proposal

        try:
            result = evaluator(**proposal.new_parameters, prec=self.prec)
            proposal.actual_value = str(result)

            # Compare with prediction
            if proposal.predicted_value in ("pi", "Pi"):
                error = abs(float(result) - float(mp.pi))
                proposal.error = error
                proposal.status = "confirmed" if error < 1e-10 else "falsified"
            else:
                proposal.status = "tested"
                proposal.error = None

        except Exception as e:
            proposal.status = "error"
            proposal.actual_value = f"Error: {e}"

        return proposal

    # ------- Internal analysis methods -------

    def _analyse_factorial_ratio(self, params):
        """Analyse the combinatorial meaning of a factorial ratio."""
        top = params.get("top", "")
        bottom = params.get("bottom", "")
        return {
            "top_factorial": top,
            "bottom_factorial": bottom,
            "interpretation": f"(${top})! / ({bottom})! counts "
                              f"{'lattice paths' if '4n' in str(top) else 'configurations'} "
                              f"in a {'4D' if '4' in str(top) else 'higher-D'} space",
            "calabi_yau_connection": "4n -> K3; 6n -> CY 3-fold" if "4n" in str(top) or "6n" in str(top) else "unknown",
        }

    def _analyse_decay(self, params, formula_params):
        """Analyse exponential decay / convergence base."""
        base = params.get("base", 1)
        result = {"base": base, "significance": ""}

        # Check for class number connections
        known_bases = {
            396: "396^4 = 24591257856; 99^2 = 9801; disc = -4*99 relates to Q(sqrt(-1))",
            640320: "640320^3 + 744 = j(e^{pi*sqrt(163)}); disc = -163, class number 1",
        }
        if base in known_bases:
            result["significance"] = known_bases[base]
            result["heegner_connection"] = True
        elif isinstance(base, (int, float)) and base > 100:
            # Check if base^k + 744 is close to a j-value
            for k in [1, 2, 3, 4]:
                j_approx = base**k + 744
                result[f"j_test_k{k}"] = j_approx

        return result

    def _classify_hypergeometric(self, params):
        """Classify the hypergeometric type."""
        htype = params.get("type", "unknown")
        classifications = {
            "4F3": {"euler_integral": True, "CY_type": "K3 surface", "dimension": 2},
            "6F5": {"euler_integral": True, "CY_type": "CY 3-fold", "dimension": 3},
            "3F2": {"euler_integral": True, "CY_type": "elliptic curve", "dimension": 1},
        }
        return classifications.get(htype, {"type": htype, "CY_type": "unknown"})

    def _analyse_q_product(self, params):
        """Analyse q-product structure."""
        power = params.get("power", 1)
        return {
            "power": power,
            "physical_meaning": {
                1: "Single boson (eta function)",
                -1: "Partition generating function",
                24: "Bosonic string (24 transverse modes, Delta cusp form)",
                -24: "j-function denominator (all string states)",
            }.get(power, f"Power {power}: {abs(power)} degrees of freedom"),
        }

    def _analyse_modularity(self, params, mod_props):
        """Analyse modular properties."""
        weight = params.get("weight", mod_props.get("weight"))
        level = params.get("level", mod_props.get("level"))
        return {
            "weight": weight,
            "level": level,
            "interpretation": f"Weight {weight} modular form at level {level}",
            "physics": "Weight = spin of the dual field; Level = gauge group rank" if weight else "",
        }

    def _analyse_mock(self, params):
        """Analyse mock theta properties."""
        order = params.get("order", "unknown")
        shadow = params.get("shadow", "unknown")
        return {
            "order": order,
            "shadow": shadow,
            "physics": f"Order-{order} mock theta has shadow = {shadow}. "
                       "In BH physics, the shadow = wall-crossing contribution. "
                       "The mock modular completion = exact quantum BH entropy.",
        }

    def _find_hidden_constants(self, formula):
        """Find hidden numerical relationships in formula parameters."""
        hidden = []

        params = formula.parameters
        if not params:
            return hidden

        # Look for ratios that are near-integers or algebraic
        param_vals = [(k, v) for k, v in params.items() if isinstance(v, (int, float))]

        for i, (k1, v1) in enumerate(param_vals):
            for k2, v2 in param_vals[i+1:]:
                if v1 == 0 or v2 == 0:
                    continue
                ratio = v2 / v1
                # Check if ratio is close to an integer
                if abs(ratio - round(ratio)) < 0.001 and abs(ratio) > 1:
                    hidden.append({
                        "type": "integer_ratio",
                        "params": (k1, k2),
                        "ratio": round(ratio),
                        "significance": f"{k2}/{k1} = {round(ratio)} (exact integer ratio)",
                    })
                # Check for sqrt relationships
                for n in [2, 3, 5, 7, 163]:
                    sq = ratio / n**0.5
                    if abs(sq - round(sq)) < 0.01 and abs(sq) > 0.5:
                        hidden.append({
                            "type": "sqrt_ratio",
                            "params": (k1, k2),
                            "relationship": f"{k2}/{k1} ~ {round(sq)} * sqrt({n})",
                            "significance": f"sqrt({n}) relationship" +
                                            (" -- Heegner number!" if n == 163 else ""),
                        })

        # Check for the 26390/1103 ~ 23.93... = 24 - 0.07
        if "a" in params and "b" in params:
            a, b = params["a"], params["b"]
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a != 0:
                ratio = b / a
                hidden.append({
                    "type": "linear_coefficient_ratio",
                    "value": ratio,
                    "near_integer": round(ratio),
                    "deviation": ratio - round(ratio),
                    "significance": f"b/a = {ratio:.6f}, near {round(ratio)}. "
                                    "In string theory, the integer part counts BPS states.",
                })

        return hidden

    def _find_symmetries(self, formula):
        """Identify symmetry properties of the formula."""
        symmetries = []

        if formula.modular_properties:
            mp = formula.modular_properties
            if mp.get("weight"):
                symmetries.append({
                    "type": "modular",
                    "group": mp.get("level", "SL(2,Z)"),
                    "weight": mp["weight"],
                    "physics": "Modular invariance = UV/IR duality in string theory",
                })
            if mp.get("eigenform"):
                symmetries.append({
                    "type": "Hecke_eigenform",
                    "significance": "Hecke eigenform = the L-function has an Euler product. "
                                    "In physics: the partition function factorises over primes (= local contributions).",
                })
            if mp.get("type") == "mock_modular":
                symmetries.append({
                    "type": "mock_modular",
                    "shadow": mp.get("shadow", "unknown"),
                    "physics": "Quasi-modular: transforms with a correction term (shadow). "
                               "In BH physics: the shadow encodes wall-crossing.",
                })

        return symmetries

    def _analyse_convergence(self, formula):
        """Analyse convergence rate and its physical meaning."""
        rate = formula.convergence_rate
        if not rate:
            return None

        result = {
            "rate": rate,
            "digits_per_term": None,
            "physics_interpretation": "",
        }

        if "14" in rate:
            result["digits_per_term"] = 14.18
            result["physics_interpretation"] = (
                "14 digits/term: each term adds information equal to "
                "exp(-14*ln(10)) ~ exp(-32.2) of the previous. "
                "This exponential convergence maps to the gap in the string spectrum."
            )
        elif "8" in rate:
            result["digits_per_term"] = 8.0
            result["physics_interpretation"] = (
                "8 digits/term: convergence rate = log(396^4) ~ 32/4. "
                "The base 396 encodes the arithmetic of Q(sqrt(-1))."
            )
        elif "asymptotic" in rate.lower():
            result["physics_interpretation"] = (
                "Asymptotic series: the expansion is around a saddle point. "
                "In BH physics, this is the semi-classical expansion around "
                "the dominant geometry."
            )

        return result

    def _analyse_pi_series_family(self, pi_formulas):
        """Find patterns across all pi-series formulas."""
        patterns = []

        params_list = [(f.id, f.parameters) for f in pi_formulas if f.parameters]
        if len(params_list) >= 2:
            f1_id, p1 = params_list[0]
            f2_id, p2 = params_list[1]

            # Check relationship between convergence bases
            bases = []
            for fid, p in params_list:
                if "c" in p:
                    bases.append((fid, p["c"]))
                elif "base" in p:
                    bases.append((fid, p["base"]))

            if len(bases) >= 2:
                patterns.append(StructuralPattern(
                    id="PI-BASE-LADDER",
                    name="Pi-series convergence base ladder",
                    description=f"Bases: {', '.join(f'{fid}: {b}' for fid, b in bases)}. "
                                "These are values at CM points of the j-function. "
                                "Each base = e^{pi*sqrt(d)} for a Heegner number d. "
                                "The ladder of Heegner numbers d = 1,2,3,7,11,19,43,67,163 "
                                "gives a finite family of Ramanujan-Chudnovsky formulas.",
                    formulas_involved=[fid for fid, _ in bases],
                    primitives_shared=["exponential_decay", "hypergeometric_sum"],
                    parameter_relationship="base^k ~ j(e^{pi*sqrt(d)})",
                    physics_implication="Each Heegner number d corresponds to a CM elliptic curve, "
                                       "which in string theory is a special point in the CY moduli space "
                                       "where extra symmetry (complex multiplication) emerges.",
                    confidence=0.90,
                    generation=self.generation,
                ))

        return patterns

    def _analyse_modular_family(self, modular_formulas):
        """Find patterns in the modular form family."""
        patterns = []

        # Weight spectrum
        weights = []
        for f in modular_formulas:
            w = f.modular_properties.get("weight")
            if w is not None:
                weights.append((f.id, w))

        if len(weights) >= 2:
            patterns.append(StructuralPattern(
                id="WEIGHT-SPECTRUM",
                name="Modular weight spectrum",
                description=f"Weights: {', '.join(f'{fid}: {w}' for fid, w in weights)}. "
                            "The weight determines the spin of the corresponding field in "
                            "the AdS/CFT dual. Integer weights -> bosonic; half-integer -> fermionic.",
                formulas_involved=[fid for fid, _ in weights],
                primitives_shared=["modular_weight"],
                parameter_relationship="Weight ladder: 1/2, 1, 2, ..., 12",
                physics_implication="The weight-12 cusp form (Delta) corresponds to the "
                                   "graviton in 3D. Lighter weights give matter fields.",
                confidence=0.85,
                generation=self.generation,
            ))

        return patterns

    def _analyse_partition_bh_bridge(self, partition_formulas):
        """Analyse the partition function -> black hole entropy bridge."""
        patterns = []

        patterns.append(StructuralPattern(
            id="PARTITION-BH-BRIDGE",
            name="Partition function -> Black hole entropy bridge",
            description="The Hardy-Ramanujan formula p(n) ~ exp(pi*sqrt(2n/3))/(4n*sqrt(3)) "
                        "IS the Bekenstein-Hawking entropy formula S = pi*sqrt(2N/3) where N is "
                        "the D-brane charge. This is not an analogy -- it is the SAME formula. "
                        "Strominger-Vafa (1996) proved that D-brane microstate counting gives "
                        "partitions, and the leading asymptotics match BH entropy exactly.",
            formulas_involved=[f.id for f in partition_formulas],
            primitives_shared=["exponential_decay", "saddle_point", "q_product"],
            parameter_relationship="S_BH = pi*sqrt(2N/3) from p(N) ~ exp(pi*sqrt(2N/3))",
            physics_implication="Ramanujan's 1918 formula was the black hole entropy formula "
                                "78 years before Strominger-Vafa. The Rademacher exact formula gives "
                                "ALL quantum corrections to BH entropy. "
                                "Each term k in the Rademacher sum = a saddle-point geometry in AdS_3.",
            confidence=0.98,
            generation=self.generation,
        ))

        # Mock theta -> BH quantum corrections
        patterns.append(StructuralPattern(
            id="MOCK-BH-QUANTUM",
            name="Mock theta functions -> Quantum black hole corrections",
            description="Dabholkar-Murthy-Zagier (2012) showed that the EXACT entropy of "
                        "1/4-BPS black holes in N=4 string theory is given by a mock Jacobi form. "
                        "Ramanujan's mock theta functions from 1920 encode the quantum corrections "
                        "to black hole entropy that physicists only understood 90 years later. "
                        "The 'shadow' of the mock modular form = wall-crossing contributions.",
            formulas_involved=[f.id for f in partition_formulas] + ["RAM-MOCK-THETA"],
            primitives_shared=["mock_theta", "q_product", "rademacher_sum"],
            parameter_relationship="mock completion = F(tau) + integral of shadow",
            physics_implication="Ramanujan's deathbed discovery (mock theta functions) "
                                "solves a problem in quantum gravity. The non-modularity that puzzled "
                                "mathematicians for 80 years is EXACTLY the wall-crossing phenomenon.",
            confidence=0.95,
            generation=self.generation,
        ))

        return patterns

    def _extrapolate_pi_parameters(self, formula):
        """Propose new pi-series formulas by extrapolating parameters."""
        proposals = []
        params = formula.parameters

        # Try Heegner-number-based extrapolation
        heegner_data = {
            # d -> (known_base, known_a, known_b)
            1: (None, None, None),
            2: (None, None, None),
            3: (None, None, None),
            7: (None, None, None),
            11: (None, None, None),
            19: (None, None, None),
            43: (None, None, None),
            67: (None, None, None),
            163: (640320, 13591409, 545140134),
        }

        if params.get("base") == 640320:
            # Chudnovsky is d=163; predict others from the pattern
            for d in [43, 67]:
                # The base for disc d is related to j(e^{pi*sqrt(d)})^{1/3}
                proposals.append(GeneralisationProposal(
                    id=f"PI-HEEG-{d}",
                    source_formula=formula.id,
                    new_parameters={"discriminant": d, "base": f"j(sqrt(-{d}))^(1/3)"},
                    predicted_value="pi",
                    status="proposed",
                    physics_motivation=f"Heegner number d={d}: the CM point e^{{pi*sqrt({d})}} "
                                       "should give a convergent pi formula. Each d corresponds to "
                                       "a distinct compactification geometry.",
                    generation=self.generation,
                ))

        return proposals

    def _propose_mock_physics(self, formula):
        """Propose new physics connections for mock theta functions."""
        proposals = []

        # Higher-order mock theta -> higher rank black holes
        for order in [5, 7]:
            proposals.append(GeneralisationProposal(
                id=f"MOCK-ORDER-{order}",
                source_formula=formula.id,
                new_parameters={"order": order},
                predicted_value=f"order-{order} mock theta function",
                status="proposed",
                physics_motivation=f"Order-{order} mock theta should encode degeneracies of "
                                   f"rank-{order//2} black holes, beyond the 1/4-BPS sector.",
                generation=self.generation,
            ))

        return proposals

    def _propose_weight_ladder(self, modular_formulas):
        """Propose new connections from modular weight laddering."""
        proposals = []

        known_weights = set()
        for f in modular_formulas:
            w = f.modular_properties.get("weight")
            if w is not None:
                known_weights.add(w)

        # In the weight spectrum, which weights are missing?
        expected_weights = {0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12}
        missing = expected_weights - known_weights
        for w in sorted(missing):
            proposals.append(GeneralisationProposal(
                id=f"WEIGHT-{w}",
                source_formula="MODULAR-FAMILY",
                new_parameters={"weight": w},
                predicted_value=f"weight-{w} modular/mock modular form",
                status="proposed",
                physics_motivation=f"Weight {w} is missing from the spectrum. "
                                   f"In AdS/CFT, this would be a {'fermionic' if w % 1 != 0 else 'bosonic'} "
                                   f"field of spin {w}.",
                generation=self.generation,
            ))

        return proposals

    def advance_generation(self):
        """Move to next iteration."""
        self.generation += 1
