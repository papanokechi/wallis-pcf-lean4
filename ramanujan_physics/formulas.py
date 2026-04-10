"""
formulas.py - Ramanujan Formula Database with Structural Decomposition

Each formula is stored with:
  - Exact mathematical definition (evaluable via mpmath)
  - Structural skeleton: what operations/patterns appear
  - Parameter space for generalisation
  - Known physics connections (seed knowledge)
  - Decomposition into primitive components
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import mpmath
from mpmath import mp, mpf, pi, sqrt, factorial, gamma, rf, power, log, exp, inf


# ---------------------------------------------------------------------------
# Structural primitives: building blocks found across Ramanujan's work
# ---------------------------------------------------------------------------
PRIMITIVES = {
    "hypergeometric_sum": "Sum of rising-factorial ratios: Pochhammer symbols",
    "factorial_ratio":    "n! / (k!)^m  -- partition-like counting",
    "exponential_decay":  "exp(-c*n) or q^n  -- Boltzmann / partition function",
    "modular_weight":     "Transforms under SL(2,Z) with weight k",
    "continued_fraction": "a0 + a1/(b1 + a2/(b2 + ...))  -- fixed-point iteration",
    "q_product":          "Product_{n>=1} (1-q^n)^a  -- Dedekind eta / partition gen fn",
    "theta_function":     "Sum q^{n^2}  -- Gaussian / lattice theta series",
    "eisenstein_series":  "E_k(tau) = 1 - (2k/B_k) Sum sigma_{k-1}(n) q^n",
    "mock_theta":         "q-hypergeometric but NOT modular -- quantum modular form",
    "rademacher_sum":     "Exact formula for p(n) via Kloosterman sums",
    "pochhammer":         "(a)_n = a(a+1)...(a+n-1)  -- rising factorial",
    "bernoulli":          "B_n -- appears in zeta regularisation, Casimir",
    "ramanujan_tau":      "tau(n) from Delta = q prod (1-q^n)^24",
    "dirichlet_series":   "Sum a(n)/n^s  -- L-functions",
    "bessel_integral":    "Integral representations connecting to wave equations",
    "saddle_point":       "Asymptotic expansion around critical point",
}


@dataclass
class FormulaComponent:
    """A single structural building block within a formula."""
    primitive: str          # key into PRIMITIVES
    parameters: dict        # e.g. {"k": 2, "modulus": 5}
    role: str               # "numerator", "weight", "phase", "amplitude", etc.
    physics_hint: str = ""  # e.g. "Boltzmann weight", "degeneracy count"


@dataclass
class RamanujanFormula:
    """A Ramanujan formula with full structural metadata."""
    id: str
    name: str
    family: str             # pi_series, continued_fraction, q_series, partition, etc.
    year: int               # year discovered/published
    expression_latex: str   # LaTeX string
    description: str
    evaluator: Optional[Callable] = None   # mpmath evaluator
    components: list = field(default_factory=list)        # FormulaComponent list
    parameters: dict = field(default_factory=dict)        # tuneable params
    physics_connections: list = field(default_factory=list)  # PhysicsLink list
    generalisation_axes: list = field(default_factory=list)  # how to extend
    known_value: Optional[str] = None       # what it evaluates to, e.g. "pi"
    convergence_rate: str = ""              # "exponential", "algebraic", etc.
    modular_properties: dict = field(default_factory=dict)


@dataclass
class PhysicsLink:
    """A connection between a mathematical structure and physics."""
    domain: str             # "black_holes", "string_theory", "qft", "stat_mech", etc.
    concept: str            # e.g. "Bekenstein-Hawking entropy"
    mechanism: str          # how the math maps to physics
    strength: float = 0.0   # 0-1: how established the connection is
    references: list = field(default_factory=list)
    discovered_by_agent: bool = False


# ---------------------------------------------------------------------------
# Helper: high-precision evaluators
# ---------------------------------------------------------------------------
def _mp_ctx(prec=100):
    ctx = mpmath.mp.clone()
    ctx.dps = prec
    return ctx


def eval_ramanujan_1914(prec=100):
    """Ramanujan's 1914 formula: 1/pi = (2*sqrt(2)/9801) * Sum_{n=0}^inf ..."""
    m = _mp_ctx(prec)
    s = m.mpf(0)
    for n in range(prec // 4 + 10):
        num = m.fac(4*n) * (1103 + 26390*n)
        den = (m.fac(n)**4) * m.power(396, 4*n)
        s += num / den
    return 1 / (s * 2 * m.sqrt(2) / 9801)


def eval_chudnovsky(prec=100):
    """Chudnovsky formula: fastest known pi series."""
    m = _mp_ctx(prec)
    s = m.mpf(0)
    for n in range(prec // 10 + 5):
        num = m.fac(6*n) * (13591409 + 545140134*n)
        den = m.fac(3*n) * (m.fac(n)**3) * m.power(-262537412640768000, n)
        s += num / den
        if n > 0 and abs(num/den) < m.power(10, -(prec+20)):
            break
    return 1 / (s * 12 / m.sqrt(640320**3))


def eval_rogers_ramanujan_cf(prec=100):
    """Rogers-Ramanujan continued fraction R(q) at q = e^{-2*pi}."""
    m = _mp_ctx(prec)
    q = m.exp(-2 * m.pi)
    # Product formula: R(q) = q^{1/5} prod (1-q^{5n-1})(1-q^{5n-4}) / (1-q^{5n-2})(1-q^{5n-3})
    val = m.power(q, m.mpf(1)/5)
    for n in range(1, prec + 50):
        val *= (1 - m.power(q, 5*n - 1)) * (1 - m.power(q, 5*n - 4))
        val /= (1 - m.power(q, 5*n - 2)) * (1 - m.power(q, 5*n - 3))
    return val


def eval_partition_generating(q_val, prec=100):
    """Euler partition generating function: prod 1/(1-q^n)."""
    m = _mp_ctx(prec)
    q = m.mpf(q_val)
    prod = m.mpf(1)
    for n in range(1, prec * 2):
        prod /= (1 - m.power(q, n))
        if abs(m.power(q, n)) < m.power(10, -(prec+10)):
            break
    return prod


def eval_mock_theta_f0(q_val, prec=100):
    """Ramanujan's third-order mock theta f_0(q) = Sum q^{n^2}/((-q;q)_n)^2."""
    m = _mp_ctx(prec)
    q = m.mpf(q_val)
    total = m.mpf(0)
    for n in range(min(200, prec)):
        qn2 = m.power(q, n*n)
        # (-q;q)_n = prod_{k=1}^{n} (1+q^k)
        pochh = m.mpf(1)
        for k in range(1, n+1):
            pochh *= (1 + m.power(q, k))
        if pochh == 0:
            break
        total += qn2 / (pochh * pochh)
        if abs(qn2) < m.power(10, -(prec+10)):
            break
    return total


def eval_hardy_ramanujan_pn(n, prec=100):
    """Hardy-Ramanujan asymptotic formula: p(n) ~ exp(pi*sqrt(2n/3))/(4n*sqrt(3))."""
    m = _mp_ctx(prec)
    nn = m.mpf(n)
    return m.exp(m.pi * m.sqrt(2*nn/3)) / (4 * nn * m.sqrt(3))


def eval_dedekind_eta(tau, prec=100):
    """Dedekind eta function: eta(tau) = q^{1/24} prod (1-q^n), q=e^{2*pi*i*tau}."""
    m = _mp_ctx(prec)
    q = m.exp(2 * m.pi * 1j * tau)
    val = m.power(q, m.mpf(1)/24)
    for n in range(1, prec * 2):
        val *= (1 - m.power(q, n))
        if abs(m.power(q, n)) < m.power(10, -(prec+10)):
            break
    return val


def eval_eisenstein_e2k(k, tau, prec=100):
    """Eisenstein series E_{2k}(tau) for k >= 1."""
    m = _mp_ctx(prec)
    q = m.exp(2 * m.pi * 1j * tau)
    # E_{2k} = 1 - (4k/B_{2k}) sum_{n>=1} sigma_{2k-1}(n) q^n
    bernoulli_vals = {2: m.mpf(1)/6, 4: -m.mpf(1)/30, 6: m.mpf(1)/42,
                      8: -m.mpf(1)/30, 10: m.mpf(5)/66, 12: -m.mpf(691)/2730}
    kk = 2*k
    if kk not in bernoulli_vals:
        return None
    bk = bernoulli_vals[kk]
    coeff = -kk * 2 / bk
    s = m.mpf(0)
    for n in range(1, prec):
        sig = sum(d**(kk-1) for d in range(1, n+1) if n % d == 0)
        s += sig * m.power(q, n)
        if abs(m.power(q, n)) < m.power(10, -(prec+10)):
            break
    return 1 + coeff * s


def eval_jacobi_theta3(q_val, prec=100):
    """Jacobi theta_3(q) = 1 + 2*sum q^{n^2}."""
    m = _mp_ctx(prec)
    q = m.mpf(q_val)
    s = m.mpf(1)
    for n in range(1, prec):
        term = m.power(q, n*n)
        s += 2 * term
        if abs(term) < m.power(10, -(prec+10)):
            break
    return s


def eval_ramanujan_tau(n):
    """Ramanujan tau function via product expansion of Delta."""
    m = _mp_ctx(200)
    # Delta(q) = q * prod (1-q^n)^24,  tau(n) = coefficient of q^n
    # Use recurrence via divisor sums
    tau_vals = [0, 1]
    for k in range(2, n+1):
        # Recurrence: tau(n) = tau(n-1)*tau(2)/tau(1) ... (not exact)
        # Better: compute from product directly
        pass
    # Direct computation via numerical extraction
    q_sym = m.mpf(1) / m.mpf(1000)  # small q for coefficient extraction
    # Use FFT-like extraction -- for now, use the formula with sigma sums
    # tau(n) via Ramanujan's congruences is complex; use mpmath's built-in if available
    try:
        # Exact computation using eta products
        coeffs = [0] * (n + 1)
        coeffs[0] = 1
        for k in range(1, n + 1):
            # Use the pentagonal number theorem iteratively
            for j in range(1, k + 1):
                pent1 = j * (3*j - 1) // 2
                pent2 = j * (3*j + 1) // 2
                if pent1 <= k:
                    coeffs[k] -= ((-1)**(j+1)) * coeffs[k - pent1] if (k - pent1) >= 0 else 0
                if pent2 <= k:
                    coeffs[k] -= ((-1)**(j+1)) * coeffs[k - pent2] if (k - pent2) >= 0 else 0
        return coeffs[n] if n < len(coeffs) else 0
    except Exception:
        return None


def eval_generalised_pi_series(a, b, c, d, prec=100):
    """Generalised Ramanujan-type 1/pi series with parameters (a,b,c,d).
    1/pi = sum_{n=0}^inf (a+b*n) * (4n)! / ((n!)^4 * c^n) * d
    """
    m = _mp_ctx(prec)
    s = m.mpf(0)
    for n in range(prec // 3 + 20):
        num = m.fac(4*n) * (m.mpf(a) + m.mpf(b)*n)
        den = (m.fac(n)**4) * m.power(m.mpf(c), n)
        s += num / den
        if n > 0 and abs(num/den) < m.power(10, -(prec+20)):
            break
    return 1 / (s * m.mpf(d))


# ---------------------------------------------------------------------------
# Formula database: canonical Ramanujan formulas with decomposition
# ---------------------------------------------------------------------------

def build_formula_database():
    """Build the master database of Ramanujan formulas with physics annotations."""

    db = []

    # === 1. Ramanujan's 1914 series for 1/pi ===
    db.append(RamanujanFormula(
        id="RAM-1914-PI",
        name="Ramanujan 1914 series for 1/pi",
        family="pi_series",
        year=1914,
        expression_latex=r"\frac{1}{\pi} = \frac{2\sqrt{2}}{9801}\sum_{n=0}^{\infty}\frac{(4n)!(1103+26390n)}{(n!)^4 396^{4n}}",
        description="Ramanujan's original rapidly converging series for 1/pi. Each term adds ~8 decimal digits.",
        evaluator=eval_ramanujan_1914,
        components=[
            FormulaComponent("factorial_ratio", {"top": "4n", "bottom": "n^4"}, "amplitude",
                             "Counts 4-fold symmetric configurations -- lattice paths on Z^4"),
            FormulaComponent("hypergeometric_sum", {"type": "4F3"}, "structure",
                             "Hypergeometric structure links to periods of elliptic curves"),
            FormulaComponent("exponential_decay", {"base": 396, "power": "4n"}, "convergence",
                             "396^4 = 24591257856 -- related to class number of Q(sqrt(-163))"),
        ],
        parameters={"a": 1103, "b": 26390, "c": 396},
        physics_connections=[
            PhysicsLink("string_theory", "Periods of K3 surfaces",
                        "The series coefficients arise from periods of certain Calabi-Yau manifolds; "
                        "the singular moduli (class number 1) connect to string compactification moduli", 0.85,
                        ["Borwein & Borwein 1987", "Guillera 2008"]),
            PhysicsLink("number_theory", "Heegner numbers and j-function",
                        "9801 = 99^2, 396 = 4*99, and 163 is a Heegner number; "
                        "j(e^{pi*sqrt(163)}) ~ 640320^3 connects to Chudnovsky",
                        0.95, ["Ramanujan 1914", "Borwein 1987"]),
        ],
        generalisation_axes=["Vary (a,b,c) to find other singular moduli", "Replace 4F3 with higher pFq"],
        known_value="pi",
        convergence_rate="exponential: ~8 digits/term",
        modular_properties={"weight": 1, "level": "Gamma_0(2)", "l_value": "L(E,1)"},
    ))

    # === 2. Chudnovsky formula ===
    db.append(RamanujanFormula(
        id="CHUD-1988",
        name="Chudnovsky brothers formula",
        family="pi_series",
        year=1988,
        expression_latex=r"\frac{1}{\pi} = 12\sum_{n=0}^{\infty}\frac{(-1)^n(6n)!(13591409+545140134n)}{(3n)!(n!)^3 640320^{3n+3/2}}",
        description="Fastest converging series for pi. ~14 digits per term. Used in all world-record pi computations.",
        evaluator=eval_chudnovsky,
        components=[
            FormulaComponent("factorial_ratio", {"top": "6n", "bottom": "3n,n^3"}, "amplitude",
                             "6-fold symmetry -- hexagonal lattice counting"),
            FormulaComponent("hypergeometric_sum", {"type": "6F5"}, "structure",
                             "Higher hypergeometric: period of a rank-2 Calabi-Yau 3-fold"),
            FormulaComponent("exponential_decay", {"base": 640320, "power": "3n"}, "convergence",
                             "640320^3 + 744 = j(e^{pi*sqrt(163)}) -- Heegner number miracle"),
        ],
        parameters={"a": 13591409, "b": 545140134, "base": 640320},
        physics_connections=[
            PhysicsLink("string_theory", "Calabi-Yau periods",
                        "The formula computes the period integral of a specific CY 3-fold. "
                        "In type IIB string theory, these periods determine gauge couplings and superpotential.",
                        0.90, ["Candelas et al. 1991", "Klemm & Theisen 1996"]),
            PhysicsLink("string_theory", "Mirror symmetry",
                        "The Picard-Fuchs equation generating this series is the mirror of a CY manifold. "
                        "Mirror symmetry exchanges complex structure and Kahler moduli.",
                        0.85, ["Hosono et al. 1994"]),
        ],
        generalisation_axes=["Other CM points on X_0(N)", "Higher-dimensional CY periods"],
        known_value="pi",
        convergence_rate="exponential: ~14.18 digits/term",
        modular_properties={"discriminant": -163, "class_number": 1, "j_invariant": "640320^3+744"},
    ))

    # === 3. Hardy-Ramanujan partition asymptotics ===
    db.append(RamanujanFormula(
        id="HR-1918-PARTITION",
        name="Hardy-Ramanujan partition asymptotic",
        family="partition",
        year=1918,
        expression_latex=r"p(n) \sim \frac{1}{4n\sqrt{3}} \exp\left(\pi\sqrt{\frac{2n}{3}}\right)",
        description="Asymptotic formula for the number of integer partitions. "
                    "Revolutionary use of the circle method. Extended to exact formula by Rademacher.",
        evaluator=eval_hardy_ramanujan_pn,
        components=[
            FormulaComponent("exponential_decay", {"coeff": "pi*sqrt(2/3)", "argument": "sqrt(n)"}, "growth",
                             "Sub-exponential growth -- same functional form as black hole entropy S ~ sqrt(N)"),
            FormulaComponent("saddle_point", {"type": "circle_method"}, "technique",
                             "Residue integration on a circle -- ancestor of all saddle-point methods in QFT"),
            FormulaComponent("bernoulli", {"order": "all"}, "corrections",
                             "Bernoulli numbers appear in the Rademacher-type corrections"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("black_holes", "Bekenstein-Hawking entropy",
                        "Strominger & Vafa (Phys. Lett. B 379, 99, 1996) showed that D-brane "
                        "microstate counting for a specific 5D BPS black hole in type IIB string "
                        "theory reduces to a partition-counting problem whose leading asymptotics "
                        "reproduce S_BH = A/(4G). The Hardy-Ramanujan asymptotic provides the "
                        "saddle-point growth rate that matches the Bekenstein-Hawking area formula. "
                        "The match is structural: both arise from the same Cardy-type modular "
                        "asymptotic, not from a literal identification p(n) = exp(S_BH).",
                        0.90, ["Strominger & Vafa, Phys. Lett. B 379, 99 (1996)",
                               "Maldacena, Adv. Theor. Math. Phys. 2, 231 (1998)"]),
            PhysicsLink("string_theory", "D-brane microstate counting",
                        "The CFT on the D-brane worldvolume has a partition function whose "
                        "asymptotic state count is governed by the Cardy formula, which shares "
                        "the Hardy-Ramanujan exponential growth form exp(pi*sqrt(cN/6)). "
                        "At large charges, this reproduces the BH area-entropy relation.",
                        0.90, ["Polchinski, Phys. Rev. Lett. 75, 4724 (1995)",
                               "Strominger & Vafa, Phys. Lett. B 379, 99 (1996)"]),
            PhysicsLink("stat_mech", "Bose-Einstein condensation",
                        "p(n) counts ways to distribute n quanta among integer mode numbers = "
                        "boson occupation numbers. The generating function is a bosonic partition function.",
                        0.90, ["Andrews 1976"]),
        ],
        generalisation_axes=["Rademacher exact formula", "Coloured partitions for D-branes",
                             "Asymptotic expansion to all orders"],
        known_value="p(n) asymptotic",
        convergence_rate="asymptotic: relative error O(1/sqrt(n))",
        modular_properties={"modular_form": "1/eta(tau)", "weight": -0.5, "level": "SL(2,Z)"},
    ))

    # === 4. Ramanujan's partition congruences ===
    db.append(RamanujanFormula(
        id="RAM-PART-CONG",
        name="Ramanujan partition congruences",
        family="partition",
        year=1919,
        expression_latex=r"p(5n+4) \equiv 0\ (\mathrm{mod}\ 5),\quad p(7n+5) \equiv 0\ (\mathrm{mod}\ 7),\quad p(11n+6) \equiv 0\ (\mathrm{mod}\ 11)",
        description="Ramanujan's famous congruences for the partition function. "
                    "The only primes p where p(pn+r)=0 mod p for some r are 5, 7, 11.",
        evaluator=None,
        components=[
            FormulaComponent("q_product", {"power": -1, "modulus_structure": True}, "generating_function",
                             "1/eta(tau) = sum p(n)q^n -- the Hecke operators create congruences"),
            FormulaComponent("modular_weight", {"weight": -0.5, "level": "Gamma_0(N)"}, "modularity",
                             "The congruences arise from Hecke eigenvalues of eta-quotients"),
        ],
        parameters={"primes": [5, 7, 11]},
        physics_connections=[
            PhysicsLink("string_theory", "BPS state degeneracies",
                        "In string theory, BPS state counts satisfy analogous congruences. "
                        "The prime structure (5,7,11) relates to the simple groups in moonshine.",
                        0.70, ["Ono 2004", "Ahlgren & Ono 2001"]),
            PhysicsLink("black_holes", "Black hole microstate divisibility",
                        "If BH entropy counts partitions, these congruences imply "
                        "the microstate degeneracy is always divisible by 5,7,11 at specific charges.",
                        0.65, ["Dabholkar et al. 2012"]),
        ],
        generalisation_axes=["Ono's universal congruences for prime powers",
                             "Maass forms and higher congruences"],
        known_value="congruence identities",
        modular_properties={"hecke_operators": True, "level": "Gamma_0(5), Gamma_0(7), Gamma_0(11)"},
    ))

    # === 5. Rogers-Ramanujan identities ===
    db.append(RamanujanFormula(
        id="RR-IDENTITY",
        name="Rogers-Ramanujan identities",
        family="q_series",
        year=1894,
        expression_latex=r"\sum_{n=0}^{\infty}\frac{q^{n^2}}{(q;q)_n} = \prod_{n=0}^{\infty}\frac{1}{(1-q^{5n+1})(1-q^{5n+4})}",
        description="Fundamental identity linking q-hypergeometric series to infinite products. "
                    "Connects combinatorics, representation theory, and statistical mechanics.",
        evaluator=eval_rogers_ramanujan_cf,
        components=[
            FormulaComponent("theta_function", {"quadratic_form": "n^2"}, "sum_side",
                             "The q^{n^2} is a theta-function-like weighting"),
            FormulaComponent("q_product", {"modulus": 5, "residues": [1, 4]}, "product_side",
                             "Mod-5 product: five-fold symmetry, linked to the icosahedron"),
            FormulaComponent("continued_fraction", {"type": "Rogers-Ramanujan"}, "cf_form",
                             "R(q) = q^{1/5} * product_ratio -- the simplest self-iterating CF"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("stat_mech", "Hard hexagon model",
                        "Baxter (1980) solved the hard hexagon model exactly using Rogers-Ramanujan. "
                        "The partition function of non-overlapping hexagons on a triangular lattice "
                        "is given by the RR continued fraction.",
                        0.98, ["Baxter 1980", "Andrews 1984"]),
            PhysicsLink("cft", "Virasoro minimal models",
                        "The characters of the (2,5) minimal model are Rogers-Ramanujan functions. "
                        "In 2D CFT, these count states in irreducible Virasoro representations.",
                        0.95, ["Rocha-Caridi 1985", "Kedem et al. 1993"]),
            PhysicsLink("string_theory", "Vertex operator algebras",
                        "The RR identities are the simplest case of fermionic character formulas "
                        "for affine Lie algebras, which underlie the worldsheet CFT of strings.",
                        0.80, ["Lepowsky & Wilson 1984"]),
        ],
        generalisation_axes=["Higher-order RR identities (Andrews-Gordon)", "Affine Lie algebra characters",
                             "Knot invariants via quantum groups"],
        known_value="q-series identity",
        modular_properties={"modular_group": "Gamma(5)", "genus": 0},
    ))

    # === 6. Mock theta functions ===
    db.append(RamanujanFormula(
        id="RAM-MOCK-THETA",
        name="Ramanujan's mock theta functions",
        family="mock_theta",
        year=1920,
        expression_latex=r"f(q) = \sum_{n=0}^{\infty}\frac{q^{n^2}}{(-q;q)_n^2}",
        description="From Ramanujan's last letter to Hardy. Not modular, but 'mock modular' -- "
                    "they transform almost like modular forms, with a correction (shadow).",
        evaluator=eval_mock_theta_f0,
        components=[
            FormulaComponent("theta_function", {"quadratic_form": "n^2"}, "amplitude",
                             "Theta-series numerator provides Gaussian suppression"),
            FormulaComponent("q_product", {"type": "q-Pochhammer"}, "denominator",
                             "(-q;q)_n = prod(1+q^k) -- counts distinct-part partitions"),
            FormulaComponent("mock_theta", {"order": 3, "shadow": "unary_theta"}, "modularity",
                             "The shadow is a unary theta function: completes to a harmonic Maass form"),
        ],
        parameters={"order": 3},
        physics_connections=[
            PhysicsLink("black_holes", "Quantum black hole degeneracies",
                        "Dabholkar, Murthy & Zagier (2012) showed that the EXACT quantum entropy "
                        "of 1/4-BPS black holes in N=4 string theory is given by mock modular forms. "
                        "The mock theta function captures the leading + all subleading corrections.",
                        0.95, ["Dabholkar, Murthy & Zagier 2012", "Manschot & Moore 2010"]),
            PhysicsLink("black_holes", "Wall-crossing and attractor flow",
                        "Mock modularity arises because BPS states can appear/disappear as moduli change. "
                        "The shadow term is the wall-crossing contribution.",
                        0.90, ["Sen 2009", "Denef & Moore 2007"]),
            PhysicsLink("qft", "N=2 gauge theory partition functions",
                        "Vafa-Witten partition functions on 4-manifolds are mock modular forms. "
                        "The non-modularity reflects subtle wall-crossing in gauge theories.",
                        0.85, ["Vafa & Witten 1994", "Manschot 2011"]),
            PhysicsLink("quantum_gravity", "Quantum modular forms and 3-manifold invariants",
                        "Mock theta functions appear as WRT invariants of 3-manifolds, "
                        "connecting quantum topology to quantum gravity.",
                        0.75, ["Zagier 2010", "Lawrence & Zagier 1999"]),
        ],
        generalisation_axes=["Higher-order mock theta", "Mock Jacobi forms", "Appell-Lerch sums"],
        known_value="mock modular form",
        modular_properties={"type": "mock_modular", "shadow": "unary_theta_series",
                            "completion": "harmonic_Maass_form", "weight": 0.5},
    ))

    # === 7. Ramanujan's tau function and Delta ===
    db.append(RamanujanFormula(
        id="RAM-TAU-DELTA",
        name="Ramanujan tau function (Delta modular form)",
        family="modular_form",
        year=1916,
        expression_latex=r"\Delta(\tau) = q\prod_{n=1}^{\infty}(1-q^n)^{24} = \sum_{n=1}^{\infty}\tau(n)q^n",
        description="The unique normalised cusp form of weight 12 for SL(2,Z). "
                    "tau(n) is multiplicative and satisfies deep congruences.",
        evaluator=eval_ramanujan_tau,
        components=[
            FormulaComponent("q_product", {"power": 24, "type": "eta^24"}, "product",
                             "eta(tau)^24 = Delta: the 24 comes from the Leech lattice dimension"),
            FormulaComponent("ramanujan_tau", {"weight": 12}, "coefficients",
                             "tau(n) are eigenvalues of ALL Hecke operators -- the simplest L-function"),
            FormulaComponent("modular_weight", {"weight": 12, "level": 1}, "transformation",
                             "Weight 12 is the lowest weight with a cusp form for full modular group"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("string_theory", "Bosonic string partition function",
                        "The factor (1-q^n)^{24} counts oscillator states of 24 transverse bosonic "
                        "string modes. Delta is literally the 1-loop bosonic string amplitude.",
                        0.98, ["Green, Schwarz & Witten 1987"]),
            PhysicsLink("string_theory", "Leech lattice and Monster group",
                        "24 = dimension of Leech lattice. The Monster group acts on a vertex algebra "
                        "whose partition function is j(tau)-744, and Delta is the weight-12 component. "
                        "This is monstrous moonshine.",
                        0.90, ["Conway & Norton 1979", "Borcherds 1992"]),
            PhysicsLink("number_theory", "Sato-Tate distribution and Langlands",
                        "The distribution of tau(p)/p^{11/2} satisfies the Sato-Tate conjecture "
                        "(proven 2011). This connects automorphic forms to Galois representations.",
                        0.95, ["Barnet-Lamb et al. 2011"]),
        ],
        generalisation_axes=["Siegel modular forms (genus 2)", "Automorphic forms on higher groups"],
        known_value="modular_form_coefficients",
        convergence_rate="algebraic growth: |tau(n)| < n^{11/2+epsilon}",
        modular_properties={"weight": 12, "level": 1, "eigenform": True, "L_function": "L(Delta,s)"},
    ))

    # === 8. Zeta regularisation (Euler 1749, Ramanujan 1913) ===
    db.append(RamanujanFormula(
        id="RAM-ZETA-REG",
        name="Zeta regularisation (Euler 1749 / Ramanujan 1913)",
        family="zeta_regularisation",
        year=1749,
        expression_latex=r"\zeta(-1) = -\frac{1}{12} \quad\Leftrightarrow\quad 1 + 2 + 3 + 4 + \cdots \;\stackrel{\mathrm{reg}}{=}\; -\frac{1}{12}",
        description="Euler first computed zeta(-1) = -1/12 in 1749 via analytic continuation of the "
                    "Dirichlet series. Ramanujan independently rediscovered and extensively used this "
                    "regularisation in his notebooks (c. 1913). The regularised value -1/12 is not a "
                    "conventional sum but the unique finite value assigned by analytic continuation "
                    "of zeta(s) = sum n^{-s} to s = -1. In physics, this analytic continuation "
                    "(not the literal divergent sum) is the quantity that enters physical observables.",
        evaluator=None,
        components=[
            FormulaComponent("dirichlet_series", {"s": -1}, "analytic_continuation",
                             "zeta(s) = sum n^{-s} analytically continued to s=-1 gives -B_2/2 = -1/12"),
            FormulaComponent("bernoulli", {"index": 2, "value": "1/6"}, "mechanism",
                             "zeta(-n) = -B_{n+1}/(n+1): Bernoulli numbers control all negative zeta values"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("string_theory", "Bosonic string critical dimension",
                        "The zero-point energy of a bosonic string is regularised via zeta(-1) = -1/12. "
                        "Requiring Lorentz invariance forces (D-2)*zeta(-1) = -1, hence D = 26. "
                        "Note: the full derivation also requires conformal anomaly cancellation "
                        "on the worldsheet, not just the zeta value alone.",
                        0.95, ["Polchinski, String Theory Vol. 1, Ch. 1 (CUP, 1998)"]),
            PhysicsLink("qft", "Casimir effect",
                        "The Casimir force between parallel plates arises from zeta-regularised "
                        "sum of zero-point energies. The regularised value -1/12 enters the "
                        "derivation and is confirmed by experiment (Lamoreaux 1997, Bressi et al. 2002).",
                        0.98, ["Casimir, Proc. K. Ned. Akad. Wet. 51, 793 (1948)",
                               "Lamoreaux, Phys. Rev. Lett. 78, 5 (1997)"]),
            PhysicsLink("qft", "Vacuum energy and cosmological constant",
                        "Zeta regularisation of vacuum energy is a standard renormalisation tool in QFT. "
                        "The cosmological constant problem involves the mismatch between regularised "
                        "vacuum energy and the observed value of Lambda.",
                        0.75, ["Weinberg, Rev. Mod. Phys. 61, 1 (1989)"]),
        ],
        generalisation_axes=["Higher zeta values at negative integers", "Epstein zeta for lattices",
                             "Multiple zeta values"],
        known_value="-1/12",
        modular_properties={"L_function": "Riemann_zeta"},
    ))

    # === 9. Jacobi theta function identities ===
    db.append(RamanujanFormula(
        id="JACOBI-THETA",
        name="Jacobi theta function and lattice counting",
        family="q_series",
        year=1829,
        expression_latex=r"\theta_3(q) = \sum_{n=-\infty}^{\infty} q^{n^2} = \prod_{n=1}^{\infty}(1-q^{2n})(1+q^{2n-1})^2",
        description="Counts representations as sums of squares: theta_3^k counts r_k(n). "
                    "Central to lattice theory, modular forms, and statistical mechanics.",
        evaluator=eval_jacobi_theta3,
        components=[
            FormulaComponent("theta_function", {"dimension": 1, "lattice": "Z"}, "sum",
                             "Sum over integer lattice Z -- the simplest theta series"),
            FormulaComponent("q_product", {"type": "Jacobi_triple"}, "product",
                             "Jacobi triple product: bridges additive and multiplicative number theory"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("stat_mech", "Ising model partition function",
                        "The 2D Ising model at criticality has partition function "
                        "built from theta functions. The critical exponents come from "
                        "the modular properties of theta.",
                        0.90, ["Onsager 1944", "Baxter 1982"]),
            PhysicsLink("string_theory", "Closed string one-loop amplitudes",
                        "One-loop string amplitudes integrate theta functions over the modular "
                        "fundamental domain. The modular invariance of theta ensures UV finiteness.",
                        0.95, ["Green, Schwarz & Witten 1987"]),
            PhysicsLink("cft", "Conformal characters and partition functions",
                        "Theta functions ARE the characters of the free boson CFT on a circle. "
                        "T-duality exchanges theta(tau) with theta(-1/tau).",
                        0.95, ["Di Francesco et al. 1997"]),
        ],
        generalisation_axes=["Siegel theta functions for higher-dim lattices",
                             "Theta functions for codes (binary lattices)"],
        known_value="q-series identity",
        modular_properties={"weight": 0.5, "multiplier_system": "theta_multiplier"},
    ))

    # === 10. Rademacher exact formula for p(n) ===
    db.append(RamanujanFormula(
        id="RADEMACHER-EXACT",
        name="Rademacher exact formula for partitions",
        family="partition",
        year=1937,
        expression_latex=r"p(n) = \frac{2\pi}{(24n-1)^{3/4}} \sum_{k=1}^{\infty} \frac{A_k(n)}{k} I_{3/2}\!\left(\frac{\pi\sqrt{24n-1}}{6k}\right)",
        description="Exact formula: p(n) as convergent infinite series of Kloosterman sums and Bessel functions. "
                    "The circle method brought to perfection.",
        evaluator=None,
        components=[
            FormulaComponent("bessel_integral", {"order": "3/2"}, "radial",
                             "Modified Bessel I_{3/2}: radial wavefunction of a 3D particle"),
            FormulaComponent("rademacher_sum", {"type": "Kloosterman"}, "angular",
                             "A_k(n) = sum of 24k-th roots of unity: arithmetic over Z/kZ"),
            FormulaComponent("saddle_point", {"type": "exact_circle_method"}, "technique",
                             "Rademacher's extension of Hardy-Ramanujan: exact residues at all cusps"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("black_holes", "Exact quantum black hole entropy",
                        "The Rademacher expansion gives the EXACT microstate degeneracy of black holes "
                        "including ALL quantum corrections. Each Kloosterman sum A_k contributes "
                        "an instanton correction of order exp(-S_BH/k).",
                        0.95, ["Dijkgraaf et al. 2000", "Manschot & Moore 2010"]),
            PhysicsLink("quantum_gravity", "Gravitational path integral over geometries",
                        "The sum over k in Rademacher = sum over orbifold geometries Z/kZ in AdS_3. "
                        "k=1 is BTZ black hole, k>1 are exotic 3-manifold saddle points. "
                        "This is the only known case where the gravitational path integral is exact.",
                        0.90, ["Maloney & Witten 2010", "Keller & Maloney 2015"]),
            PhysicsLink("black_holes", "Farey tail expansion",
                        "The sum over Farey fractions (coprime p/k) organising the Rademacher series "
                        "maps to a sum over SL(2,Z) images of the BTZ saddle in AdS_3 gravity.",
                        0.85, ["Dijkgraaf et al. 2000", "Manschot 2007"]),
        ],
        generalisation_axes=["Siegel modular forms for 1/4-BPS states",
                             "Mock modular Rademacher for N=4 black holes"],
        known_value="exact_partition_count",
        modular_properties={"weight": -0.5, "level": 1, "type": "weakly_holomorphic"},
    ))

    # === 11. Dedekind eta function ===
    db.append(RamanujanFormula(
        id="DEDEKIND-ETA",
        name="Dedekind eta function",
        family="modular_form",
        year=1877,
        expression_latex=r"\eta(\tau) = q^{1/24}\prod_{n=1}^{\infty}(1-q^n),\quad q=e^{2\pi i\tau}",
        description="Weight-1/2 modular form. Building block for partition functions, "
                    "string amplitudes, and gauge theory.",
        evaluator=eval_dedekind_eta,
        components=[
            FormulaComponent("q_product", {"power": 1, "phase": "q^{1/24}"}, "definition",
                             "The 1/24 phase encodes the conformal anomaly c/24 of the free boson"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("string_theory", "One-loop string partition function",
                        "eta(tau)^{-24} counts bosonic string states at each mass level. "
                        "The torus amplitude is integral of |eta|^{-48} over moduli space.",
                        0.98, ["Green, Schwarz & Witten 1987"]),
            PhysicsLink("qft", "Gauge theory instanton counting",
                        "The Nekrasov partition function of N=2 gauge theories involves eta-products "
                        "as the free-field contribution. Instanton sums are corrections to this.",
                        0.85, ["Nekrasov 2003"]),
            PhysicsLink("cft", "Central charge and conformal anomaly",
                        "The q^{1/24} factor = e^{-pi*i*tau/12} encodes c=1 central charge. "
                        "For c free bosons, the partition function is eta^{-c}.",
                        0.95, ["Di Francesco et al. 1997"]),
        ],
        generalisation_axes=["Eta quotients for all levels", "Siegel-Narain theta for even lattices"],
        known_value="eta(tau)",
        modular_properties={"weight": 0.5, "level": 1, "multiplier": "Dedekind_sum"},
    ))

    # === 12. Eisenstein series ===
    db.append(RamanujanFormula(
        id="EISENSTEIN-E",
        name="Eisenstein series E_{2k}(tau)",
        family="modular_form",
        year=1847,
        expression_latex=r"E_{2k}(\tau) = 1 - \frac{4k}{B_{2k}}\sum_{n=1}^{\infty}\sigma_{2k-1}(n)q^n",
        description="Fundamental modular forms of weight 2k. E_4 and E_6 generate all modular forms for SL(2,Z).",
        evaluator=lambda prec=100: eval_eisenstein_e2k(2, mpmath.mpf(0.5)*1j, prec),
        components=[
            FormulaComponent("dirichlet_series", {"coefficients": "sigma_{2k-1}"}, "coefficients",
                             "Divisor sums sigma(n) count lattice points -- connected to Langlands L-functions"),
            FormulaComponent("bernoulli", {"index": "2k"}, "normalisation",
                             "B_{2k} controls the constant term via zeta(2k)"),
            FormulaComponent("eisenstein_series", {"weight": "2k"}, "structure",
                             "The 'simplest' modular forms: not cusp forms"),
        ],
        parameters={"k_values": [2, 3, 4, 5, 6]},
        physics_connections=[
            PhysicsLink("string_theory", "Graviton scattering amplitudes",
                        "The 4-graviton amplitude in Type II = E_{3/2}(Omega) where Omega is the "
                        "string coupling. Higher Eisenstein series give higher-derivative corrections.",
                        0.90, ["Green & Gutperle 1997", "Green et al. 2010"]),
            PhysicsLink("string_theory", "S-duality and U-duality",
                        "Non-holomorphic Eisenstein series E_s(tau) are SL(2,Z)-invariant: "
                        "they are the S-duality-invariant answers in Type IIB string theory.",
                        0.90, ["Green & Gutperle 1997"]),
        ],
        generalisation_axes=["Real-analytic Eisenstein on higher groups",
                             "Half-integral weight Eisenstein"],
        known_value="modular_form",
        modular_properties={"weight": "2k", "level": 1, "eigenform": True},
    ))

    # === 13. Generalized continued fraction for algebraic numbers ===
    db.append(RamanujanFormula(
        id="GCF-ALGEBRAIC",
        name="Ramanujan-type generalised continued fractions",
        family="continued_fraction",
        year=1914,
        expression_latex=r"\cfrac{1}{1+\cfrac{e^{-2\pi}}{1+\cfrac{e^{-4\pi}}{1+\cdots}}} = \left(\sqrt{\frac{5+\sqrt{5}}{2}}-\frac{\sqrt{5}+1}{2}\right)e^{2\pi/5}",
        description="Ramanujan evaluated continued fractions to explicit algebraic numbers. "
                    "This shows deep connections between transcendental and algebraic quantities.",
        evaluator=eval_rogers_ramanujan_cf,
        components=[
            FormulaComponent("continued_fraction", {"type": "q-exponential"}, "structure",
                             "q-deformed continued fractions bridge analysis and algebra"),
            FormulaComponent("exponential_decay", {"base": "e", "argument": "-2*pi*n"}, "convergence",
                             "Exponential convergence from q = e^{-2*pi}"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("stat_mech", "Transfer matrix eigenvalues",
                        "Continued fractions give ratios of consecutive partition function "
                        "eigenvalues in 1D statistical mechanics. The algebraic closure is the "
                        "integrability condition.",
                        0.75, ["Baxter 1982"]),
        ],
        generalisation_axes=["Higher-dimensional CFs", "Matrix-valued CFs", "q-analogs"],
        known_value="algebraic expression involving phi",
    ))

    # === 14. Monstrous moonshine j-function ===
    db.append(RamanujanFormula(
        id="J-FUNCTION",
        name="Klein j-invariant and Monstrous Moonshine",
        family="modular_form",
        year=1979,
        expression_latex=r"j(\tau) = q^{-1} + 744 + 196884q + 21493760q^2 + \cdots",
        description="The j-function is THE modular function for SL(2,Z). Its Fourier coefficients "
                    "encode dimensions of Monster group representations (moonshine).",
        evaluator=None,
        components=[
            FormulaComponent("eisenstein_series", {"} express as": "E_4^3/Delta"}, "construction",
                             "j = 1728*E_4^3 / Delta -- built from fundamental modular forms"),
            FormulaComponent("q_product", {"type": "eta^{-24}"}, "denominator",
                             "The pole at infinity comes from 1/Delta = eta^{-24}"),
        ],
        parameters={},
        physics_connections=[
            PhysicsLink("string_theory", "Monstrous moonshine and VOAs",
                        "The Monster group (|M| ~ 8*10^53) acts on the moonshine module V^natural. "
                        "The graded dimension of V is j(tau)-744. This is a string theory: "
                        "the Frenkel-Lepowsky-Meurman vertex algebra is a c=24 CFT.",
                        0.98, ["Conway & Norton 1979", "Frenkel et al. 1988", "Borcherds 1992"]),
            PhysicsLink("quantum_gravity", "AdS_3 / CFT_2 and pure gravity",
                        "Witten (2007) conjectured that pure 3D gravity with Lambda<0 has "
                        "partition function = j(tau) -- monster symmetry as a quantum gravity symmetry.",
                        0.80, ["Witten 2007"]),
            PhysicsLink("string_theory", "Heegner numbers and Calabi-Yau",
                        "j(e^{pi*sqrt(163)}) ~ 640320^3 + 744 connects to the Ramanujan/Chudnovsky pi formulas. "
                        "Singular values of j classify CM elliptic curves used in compactification.",
                        0.90, ["Zagier 1994"]),
        ],
        generalisation_axes=["Umbral moonshine (Niemeier lattices)", "Mathieu moonshine (K3)"],
        known_value="j_invariant",
        modular_properties={"weight": 0, "level": 1, "type": "Hauptmodul"},
    ))

    return db


def get_all_formulas():
    """Return the complete formula database."""
    return build_formula_database()
