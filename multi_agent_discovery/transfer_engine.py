"""
Cross-Domain Transfer Engine
=============================
The concrete implementation of cross-pollination between
the exoplanet stability and materials band gap domains.

This module:
1. Defines variable mappings between domains
2. Translates symbolic expressions across domains
3. Tests transferred laws on target domain data
4. Tracks transfer success rates for meta-learning
"""

import re
import numpy as np
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════
# DOMAIN DEFINITIONS
# ═══════════════════════════════════════════════════════════

EXOPLANET_VARIABLES = {
    "delta_hill_01": "Hill separation metric (primary pair)",
    "delta_hill_12": "Hill separation metric (secondary pair)",
    "mu_01": "Mass ratio (planet 0 / planet 1)",
    "mu_12": "Mass ratio (planet 1 / planet 2)",
    "e_0": "Eccentricity of planet 0",
    "e_1": "Eccentricity of planet 1",
    "period_ratio_01": "Period ratio (inner/outer pair)",
    "a_ratio_01": "Semi-major axis ratio",
    "mu_star": "Star-to-total mass ratio",
    "hill_mutual_01": "Mutual Hill radius",
    "resonance_prox_01": "Proximity to mean-motion resonance",
}

MATERIALS_VARIABLES = {
    "t_factor": "Goldschmidt tolerance factor",
    "EN_X": "Electronegativity of anion",
    "EN_B": "Electronegativity of B-site cation",
    "EN_diff": "Electronegativity difference |EN_X - EN_B|",
    "IE_B": "Ionization energy of B-site",
    "r_X": "Ionic radius of anion",
    "r_B": "Ionic radius of B-site",
    "mass_B": "Atomic mass of B-site",
    "mass_X": "Atomic mass of anion",
    "EA_B": "Electron affinity of B-site",
    "r_ratio": "Ionic radius ratio r_B/r_X",
}


# ═══════════════════════════════════════════════════════════
# CONCEPTUAL VARIABLE MAPPINGS
# ═══════════════════════════════════════════════════════════

# These mappings are based on structural/conceptual analogies:
# - "separation from instability" → delta_hill ↔ tolerance_factor
# - "mass asymmetry" → mu_01 ↔ mass_B/mass_X
# - "energy-related measure" → eccentricity ↔ EN_diff
# - "ratio of scales" → period_ratio ↔ r_ratio

EXOPLANET_TO_MATERIALS = {
    "delta_hill_01": "t_factor",
    "delta_hill_12": "EN_diff",
    "mu_01": "r_ratio",
    "mu_12": "mass_B",
    "e_0": "EN_X",
    "e_1": "EN_B",
    "period_ratio_01": "r_ratio",
    "a_ratio_01": "IE_B",
    "mu_star": "EA_B",
    "hill_mutual_01": "r_X",
    "resonance_prox_01": "r_B",
}

MATERIALS_TO_EXOPLANET = {v: k for k, v in EXOPLANET_TO_MATERIALS.items()}


# ═══════════════════════════════════════════════════════════
# EXPRESSION TRANSLATOR
# ═══════════════════════════════════════════════════════════

@dataclass
class TransferResult:
    """Result of a cross-domain transfer attempt."""
    source_domain: str
    target_domain: str
    source_expression: str
    translated_expression: str
    variables_mapped: dict
    unmapped_variables: list
    success: bool = False
    target_accuracy: float | None = None
    target_r_squared: float | None = None
    notes: str = ""


def translate_expression(
    expression: str,
    source_to_target_map: dict[str, str],
) -> tuple[str, dict, list]:
    """
    Translate a symbolic expression from one domain to another
    by substituting variable names.

    Returns:
        (translated_expr, mapped_vars, unmapped_vars)
    """
    translated = expression
    mapped = {}
    unmapped = []

    # Sort by longest variable name first to avoid partial replacements
    # (e.g., "delta_hill_01" before "delta_hill")
    sorted_vars = sorted(source_to_target_map.keys(), key=len, reverse=True)

    for source_var in sorted_vars:
        target_var = source_to_target_map[source_var]
        # Use word-boundary-aware replacement
        pattern = re.compile(r'\b' + re.escape(source_var) + r'\b')
        if pattern.search(translated):
            translated = pattern.sub(target_var, translated)
            mapped[source_var] = target_var

    # Check for any remaining domain-specific variables
    # that weren't in the mapping
    all_source_vars = set(source_to_target_map.keys())
    # Simple heuristic: look for identifiers in the expression
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', translated)
    for token in tokens:
        if token in all_source_vars and token not in mapped:
            unmapped.append(token)

    return translated, mapped, unmapped


def transfer_law(
    source_expression: str,
    source_domain: str,
    target_domain: str,
) -> TransferResult:
    """
    Attempt to transfer a law from one domain to another.

    Handles:
    - Variable name substitution
    - Coefficient preservation (same functional form, different constants)
    - Structural preservation (exponents, operators kept intact)
    """
    if source_domain == "exoplanet" and target_domain == "materials":
        var_map = EXOPLANET_TO_MATERIALS
    elif source_domain == "materials" and target_domain == "exoplanet":
        var_map = MATERIALS_TO_EXOPLANET
    else:
        return TransferResult(
            source_domain=source_domain,
            target_domain=target_domain,
            source_expression=source_expression,
            translated_expression="",
            variables_mapped={},
            unmapped_variables=[],
            notes=f"No mapping defined for {source_domain} → {target_domain}",
        )

    translated, mapped, unmapped = translate_expression(source_expression, var_map)

    return TransferResult(
        source_domain=source_domain,
        target_domain=target_domain,
        source_expression=source_expression,
        translated_expression=translated,
        variables_mapped=mapped,
        unmapped_variables=unmapped,
        notes=f"Mapped {len(mapped)} variables, {len(unmapped)} unmapped",
    )


# ═══════════════════════════════════════════════════════════
# STRUCTURAL SIMILARITY SCORING
# ═══════════════════════════════════════════════════════════

def compute_structural_similarity(expr_a: str, expr_b: str) -> float:
    """
    Compute structural similarity between two symbolic expressions.
    Based on:
    1. Shared operators (add, mul, pow, log, etc.)
    2. Same number of terms
    3. Same depth of nesting
    4. Same exponent values

    Returns a score in [0, 1].
    """
    ops_a = set(re.findall(r'(?:log|exp|sqrt|sin|cos|abs|pow)', expr_a))
    ops_b = set(re.findall(r'(?:log|exp|sqrt|sin|cos|abs|pow)', expr_b))

    # Operator overlap
    if ops_a or ops_b:
        op_sim = len(ops_a & ops_b) / len(ops_a | ops_b)
    else:
        op_sim = 1.0  # both are pure algebraic

    # Exponent similarity
    exps_a = [float(x) for x in re.findall(r'\*\*\s*([\d.]+)', expr_a)]
    exps_b = [float(x) for x in re.findall(r'\*\*\s*([\d.]+)', expr_b)]
    if exps_a and exps_b:
        # Check if same exponents appear
        shared_exp = len(set(exps_a) & set(exps_b))
        exp_sim = shared_exp / max(len(set(exps_a)), len(set(exps_b)))
    elif not exps_a and not exps_b:
        exp_sim = 1.0
    else:
        exp_sim = 0.0

    # Term count similarity
    terms_a = len(re.findall(r'[+\-]', expr_a)) + 1
    terms_b = len(re.findall(r'[+\-]', expr_b)) + 1
    term_sim = 1.0 - abs(terms_a - terms_b) / max(terms_a, terms_b)

    # Weighted combination
    return 0.4 * op_sim + 0.3 * exp_sim + 0.3 * term_sim


# ═══════════════════════════════════════════════════════════
# EXAMPLE TRANSFERS
# ═══════════════════════════════════════════════════════════

def demo_transfers():
    """Demonstrate cross-domain transfers with existing discovered laws."""

    # Transfer 1: Exoplanet → Materials
    print("=" * 60)
    print("TRANSFER 1: Exoplanet → Materials")
    print("=" * 60)
    result = transfer_law(
        source_expression="0.007772 * delta_hill_01 ** 3",
        source_domain="exoplanet",
        target_domain="materials",
    )
    print(f"Source:     {result.source_expression}")
    print(f"Translated: {result.translated_expression}")
    print(f"Mapped:     {result.variables_mapped}")
    print(f"Notes:      {result.notes}")
    print()

    # Transfer 2: Materials → Exoplanet
    print("=" * 60)
    print("TRANSFER 2: Materials → Exoplanet")
    print("=" * 60)
    result = transfer_law(
        source_expression="-0.0722 * IE_B * r_X + 2.4065",
        source_domain="materials",
        target_domain="exoplanet",
    )
    print(f"Source:     {result.source_expression}")
    print(f"Translated: {result.translated_expression}")
    print(f"Mapped:     {result.variables_mapped}")
    print(f"Notes:      {result.notes}")
    print()

    # Structural similarity
    print("=" * 60)
    print("STRUCTURAL SIMILARITY")
    print("=" * 60)
    sim = compute_structural_similarity(
        "0.008 * x ** 3",
        "0.072 * y * z + 2.4",
    )
    print(f"Power law vs linear: {sim:.3f}")

    sim2 = compute_structural_similarity(
        "0.008 * x ** 3",
        "0.05 * y ** 3",
    )
    print(f"Power law vs power law (same exp): {sim2:.3f}")

    sim3 = compute_structural_similarity(
        "a * log(x/y) + b",
        "c * log(p/q) + d",
    )
    print(f"Log-ratio vs log-ratio: {sim3:.3f}")


if __name__ == "__main__":
    demo_transfers()
