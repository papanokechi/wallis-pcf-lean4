"""
relay_chain.py - Generative AI relay chain for Ramanujan-style continued fractions.

This module implements a practical, local version of the four-stage loop:
  1. Pattern recognizer   - recover polynomial rules from coefficient sequences
  2. Symbolic generalizer - cluster discoveries into reusable families/templates
  3. Synthetic seed gen   - propose new polynomial search seeds near good regions
  4. Validation relay     - persist the seed pool for the next exploration round

The implementation is heuristic and deterministic. It is designed to slot into the
existing `ramanujan_agent` workflow without requiring a live LLM or external API.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .theorem_templates import cluster_by_structure, induce_templates


def evaluate_polynomial(coeffs: list[int | float], n: int) -> float:
    """Evaluate a polynomial with coefficients in descending powers."""
    value = 0.0
    for coeff in coeffs:
        value = value * n + float(coeff)
    return value


def sample_polynomial_sequence(
    coeffs: list[int | float],
    start_n: int = 1,
    terms: int = 6,
) -> list[float]:
    """Sample the first `terms` values P(start_n), ..., P(start_n+terms-1)."""
    return [evaluate_polynomial(coeffs, n) for n in range(start_n, start_n + terms)]


def _normalize_number(value: Any) -> int | float:
    """Convert SymPy/Fraction-like values to plain Python numbers."""
    try:
        frac = Fraction(value)
        return frac.numerator if frac.denominator == 1 else float(frac)
    except Exception:
        try:
            fv = float(value)
            return int(fv) if fv.is_integer() else fv
        except Exception:
            return value


def format_polynomial(coeffs: list[int | float], variable: str = "n") -> str:
    """Format coefficients as a readable polynomial string."""
    if not coeffs:
        return "0"

    degree = len(coeffs) - 1
    terms: list[str] = []

    for idx, raw_coeff in enumerate(coeffs):
        coeff = _normalize_number(raw_coeff)
        if coeff == 0:
            continue

        power = degree - idx
        abs_coeff = abs(coeff)

        if power == 0:
            body = f"{abs_coeff}"
        elif power == 1:
            body = variable if abs_coeff == 1 else f"{abs_coeff}*{variable}"
        else:
            body = f"{variable}^{power}" if abs_coeff == 1 else f"{abs_coeff}*{variable}^{power}"

        if not terms:
            terms.append(body if coeff >= 0 else f"-{body}")
        else:
            sign = "+" if coeff >= 0 else "-"
            terms.append(f" {sign} {body}")

    return "".join(terms) if terms else "0"


def _canonical_target_name(target: str | None) -> str:
    """Canonicalize a target constant label for prompt enrichment."""
    raw = (target or "unknown").strip().lower()
    raw = raw.replace(" ", "").replace("_", "")
    raw = raw.replace("’", "").replace("'", "")
    aliases = {
        "apery": "zeta3",
        "aperysconstant": "zeta3",
        "aperysconstant?": "zeta3",
        "phi": "golden_ratio",
        "goldenratio": "golden_ratio",
        "log2": "ln2",
        "log(2)": "ln2",
        "pi2": "pi^2",
        "zeta(3)": "zeta3",
    }
    return aliases.get(raw, raw)


def expand_target_neighborhood(target: str | None) -> list[str]:
    """Return a small mathematical neighborhood around a discovered constant."""
    canonical = _canonical_target_name(target)
    neighborhoods = {
        "pi": ["pi^2", "ln2", "golden_ratio", "catalan", "zeta3"],
        "pi^2": ["pi", "zeta3", "ln2", "catalan", "golden_ratio"],
        "zeta3": ["catalan", "pi^2", "ln2", "golden_ratio", "e"],
        "catalan": ["zeta3", "pi^2", "ln2", "golden_ratio", "pi"],
        "ln2": ["pi", "pi^2", "e", "golden_ratio", "catalan"],
        "golden_ratio": ["pi", "ln2", "catalan", "zeta3", "sqrt2"],
        "e": ["ln2", "pi", "zeta3", "golden_ratio", "catalan"],
        "unknown": ["pi", "pi^2", "zeta3", "catalan", "ln2"],
        "novelconstant?": ["pi", "pi^2", "zeta3", "catalan", "ln2"],
    }
    return neighborhoods.get(canonical, neighborhoods["unknown"])


def _lirec_constant_name(target: str | None) -> str:
    """Map local target aliases to LIReC's common constant names."""
    canonical = _canonical_target_name(target)
    aliases = {
        "pi": "Pi",
        "pi^2": "Pi^2",
        "zeta3": "Zeta3",
        "catalan": "Catalan",
        "ln2": "Log2",
        "golden_ratio": "GoldenRatio",
        "sqrt2": "Sqrt2",
        "e": "E",
        "unknown": "Pi",
        "novelconstant?": "Pi",
    }
    return aliases.get(canonical, str(target or "Pi"))


def build_lirec_identify_snippet(target: str | None, neighborhood: list[str]) -> str:
    """Construct a LIReC-ready numeric-identification snippet."""
    names = [_lirec_constant_name(target)]
    for neighbor in neighborhood[:2]:
        mapped = _lirec_constant_name(neighbor)
        if mapped not in names:
            names.append(mapped)
    quoted_names = ", ".join(repr(name) for name in names)
    return (
        "import mpmath as mp; "
        "from LIReC.db.access import db; "
        "mp.mp.dps = 150; "
        f"db.identify([{quoted_names}], degree=2, order=1, isolate=True, wide_search=[1, 2], verbose=False)"
    )


class _ResultsCatalogHTMLParser(HTMLParser):
    """Collect result-section headings and nearby PDF links from the results page."""

    def __init__(self, base_url: str = ""):
        super().__init__()
        self.base_url = base_url
        self.catalog: list[dict[str, Any]] = []
        self._heading_tag: str | None = None
        self._heading_text: list[str] = []
        self._current_heading = "General results"
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_map = dict(attrs)
        if tag in {"h2", "h3", "h4"}:
            self._heading_tag = tag
            self._heading_text = []
        elif tag == "a":
            href = attr_map.get("href") or ""
            self._link_href = urljoin(self.base_url, href) if href else ""
            self._link_text = []

    def handle_data(self, data: str):
        if self._heading_tag is not None:
            self._heading_text.append(data)
        if self._link_href is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str):
        if self._heading_tag == tag:
            label = " ".join("".join(self._heading_text).split())
            if label:
                self._current_heading = label
                if not any(item["label"] == label for item in self.catalog):
                    self.catalog.append({"label": label, "pdf_links": [], "link_texts": []})
            self._heading_tag = None
            self._heading_text = []

        if tag == "a" and self._link_href is not None:
            href = (self._link_href or "").strip()
            text = " ".join("".join(self._link_text).split())
            if href and ".pdf" in href.lower():
                entry = next((item for item in self.catalog if item["label"] == self._current_heading), None)
                if entry is None:
                    entry = {"label": self._current_heading, "pdf_links": [], "link_texts": []}
                    self.catalog.append(entry)
                if href not in entry["pdf_links"]:
                    entry["pdf_links"].append(href)
                    entry["link_texts"].append(text or href.rsplit("/", 1)[-1])
            self._link_href = None
            self._link_text = []


def parse_results_html(html: str, base_url: str = "") -> list[dict[str, Any]]:
    """Parse the Ramanujan Machine results page into a compact PDF catalog."""
    parser = _ResultsCatalogHTMLParser(base_url=base_url)
    parser.feed(html)
    return [item for item in parser.catalog if item.get("pdf_links")]


def scrape_results_catalog(
    results_url: str = "https://www.ramanujanmachine.com/results/",
    timeout: int = 20,
) -> list[dict[str, Any]]:
    """Fetch and parse the public Ramanujan Machine results catalog."""
    req = Request(results_url, headers={"User-Agent": "Mozilla/5.0 relay-chain"})
    with urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    return parse_results_html(html, base_url=results_url)


def fit_polynomial_from_sequence(sequence: list[int | float]) -> dict[str, Any]:
    """Recover a closed-form polynomial from a short numeric sequence.

    The sequence is interpreted as values at n = 1, 2, 3, ... .
    SymPy interpolation is used when available; a simple fallback keeps the
    function usable even if symbolic interpolation fails.
    """
    if not sequence:
        return {"degree": -1, "coefficients": [], "formula": "0"}

    try:
        import sympy as sp

        n = sp.symbols("n")
        points = [(i + 1, sp.nsimplify(v)) for i, v in enumerate(sequence)]
        poly_expr = sp.expand(sp.interpolate(points, n))
        poly = sp.Poly(poly_expr, n)
        coeffs = [_normalize_number(c) for c in poly.all_coeffs()]
        return {
            "degree": poly.degree(),
            "coefficients": coeffs,
            "formula": str(poly_expr).replace("**", "^"),
        }
    except Exception:
        # Fallback: treat as constant if symbolic fitting is unavailable.
        coeffs = [_normalize_number(sequence[0])]
        return {"degree": 0, "coefficients": coeffs, "formula": format_polynomial(coeffs)}


def _continued_fraction_shape(params: dict[str, Any]) -> str:
    """Return a coarse family label for a continued-fraction parameterization."""
    an = params.get("an", []) or []
    bn = params.get("bn", []) or []

    if len(an) == 1 and len(bn) == 1:
        return "constant_a / constant_b"
    if len(an) == 1 and len(bn) == 2:
        return "constant_a / linear_b"
    if len(an) == 1 and len(bn) == 3:
        return "constant_a / quadratic_b"
    if len(an) == 2 and len(bn) == 2:
        return "linear_a / linear_b"
    return f"deg(a)={max(len(an) - 1, 0)}, deg(b)={max(len(bn) - 1, 0)}"


def _looks_square_like(values: list[float], tol: float = 1e-9) -> bool:
    """Heuristic: are the sampled values close to perfect squares?"""
    if not values:
        return False
    for value in values:
        if value < 0:
            return False
        root = round(value ** 0.5)
        if abs(root * root - value) > tol:
            return False
    return True


def extract_cf_patterns(
    discoveries: list[dict[str, Any]],
    sample_terms: int = 6,
) -> list[dict[str, Any]]:
    """Encode continued-fraction discoveries into explicit sequence-pattern summaries."""
    encoded: list[dict[str, Any]] = []

    for disc in discoveries:
        if disc.get("family") != "continued_fraction":
            continue

        params = disc.get("params", {}) or {}
        an = list(params.get("an", []) or [])
        bn = list(params.get("bn", []) or [])
        if not an or not bn:
            continue

        a_seq = sample_polynomial_sequence(an, terms=sample_terms)
        b_seq = sample_polynomial_sequence(bn, terms=sample_terms)
        a_fit = fit_polynomial_from_sequence(a_seq)
        b_fit = fit_polynomial_from_sequence(b_seq)

        proof_result = (disc.get("metadata", {}) or {}).get("proof_result", {})
        closed_form = (proof_result.get("closed_form", {}) or {}).get("type")

        encoded.append({
            "id": disc.get("id"),
            "status": disc.get("status", "candidate"),
            "confidence": float(disc.get("confidence", 0.0) or 0.0),
            "target": disc.get("target"),
            "shape": _continued_fraction_shape(params),
            "a_coefficients": an,
            "b_coefficients": bn,
            "a_sequence": a_seq,
            "b_sequence": b_seq,
            "a_formula": format_polynomial(an),
            "b_formula": format_polynomial(bn),
            "a_fit": a_fit,
            "b_fit": b_fit,
            "b_square_prefix": _looks_square_like(b_seq),
            "closed_form_type": closed_form,
        })

    encoded.sort(key=lambda item: (-item["confidence"], item["id"] or ""))
    return encoded


def build_meta_conjectures(discoveries: list[dict[str, Any]]) -> dict[str, Any]:
    """Generalize families of successful results into reusable templates."""
    cf_discoveries = [d for d in discoveries if d.get("family") == "continued_fraction"]
    clusters = cluster_by_structure(cf_discoveries)
    templates = induce_templates(cf_discoveries)

    cluster_cards: list[dict[str, Any]] = []
    for key, members in clusters.items():
        if not members:
            continue
        statuses = Counter((m.get("status") or "candidate") for m in members)
        shapes = Counter(_continued_fraction_shape(m.get("params", {}) or {}) for m in members)
        avg_conf = mean(float(m.get("confidence", 0.0) or 0.0) for m in members)
        hypothesis = "Generic polynomial CF family"
        if any(shape == "constant_a / linear_b" for shape in shapes):
            hypothesis = "Linear denominator families tend to collapse to Bessel/hypergeometric ratios"
        elif any(shape == "constant_a / quadratic_b" for shape in shapes):
            hypothesis = "Quadratic denominator families may hide higher special-function structure"
        elif any(shape == "constant_a / constant_b" for shape in shapes):
            hypothesis = "Constant-coefficient CFs reduce to algebraic fixed points"

        cluster_cards.append({
            "cluster_key": key,
            "count": len(members),
            "avg_confidence": round(avg_conf, 4),
            "statuses": dict(statuses),
            "shapes": dict(shapes),
            "hypothesis": hypothesis,
            "sample_ids": [m.get("id") for m in members[:5]],
        })

    cluster_cards.sort(key=lambda card: (-card["avg_confidence"], -card["count"]))

    return {
        "cluster_count": len(clusters),
        "clusters": cluster_cards,
        "template_count": len(templates),
        "templates": [t.to_dict() for t in templates],
    }


def build_semantic_prompts(
    encoded_patterns: list[dict[str, Any]],
    results_catalog: list[dict[str, Any]] | None = None,
    max_prompts: int = 12,
) -> list[dict[str, Any]]:
    """Create LLM-ready 'Euler-Ramanujan' prompts for semantic seed generation."""
    prompts: list[dict[str, Any]] = []
    results_catalog = results_catalog or []

    ranked = sorted(
        encoded_patterns,
        key=lambda item: (-float(item.get("confidence", 0.0) or 0.0), item.get("id") or ""),
    )

    for item in ranked[:max_prompts]:
        target = item.get("target") or "unknown"
        neighborhood = expand_target_neighborhood(target)
        target_key = _canonical_target_name(target)
        related_results = [
            entry for entry in results_catalog
            if target_key in _canonical_target_name(entry.get("label", ""))
            or any(n in _canonical_target_name(entry.get("label", "")) for n in neighborhood)
        ]

        shape = item.get("shape", "unknown")
        transform_hints = ["n->n+1", "n->2n", "n->2n+1", "n->n-1"]
        structural_motifs = ["Apéry-style acceleration", "Ramanujan modular reweighting"]
        if "linear_b" in shape:
            structural_motifs.append("Bessel / hypergeometric ratio")
        if "quadratic_b" in shape:
            structural_motifs.append("quadratic-denominator special-function scan")
        if item.get("closed_form_type"):
            structural_motifs.append(str(item.get("closed_form_type")))

        prompt = (
            "You are an Euler-Ramanujan mathematical intuition engine. "
            "First summarize the structural fingerprint of the continued fraction, then propose the most promising semantic transforms. "
            f"Analyze the family with shape `{shape}` and coefficients a(n)={item.get('a_formula', '?')}, "
            f"b(n)={item.get('b_formula', '?')}. The current target is `{target}`. "
            f"Use the motifs {', '.join(structural_motifs)} and explicitly compare the index transforms {', '.join(transform_hints)}. "
            "Think in terms of Apéry/Ramanujan acceleration, Bessel-hypergeometric ratio identities, and factorial/binomial reweightings. "
            f"Also test the nearby constants {', '.join(neighborhood)} and rank which target/transform pair should be tried first. "
            "Return strict JSON with keys `hypothesis`, `transformations`, `suggested_targets`, and `search_space`."
        )

        prompts.append({
            "id": item.get("id"),
            "target": target,
            "target_neighborhood": neighborhood,
            "confidence": item.get("confidence", 0.0),
            "structural_motifs": structural_motifs,
            "index_transform_hints": transform_hints,
            "response_schema": {
                "type": "object",
                "required": ["hypothesis", "transformations", "suggested_targets", "search_space"],
            },
            "related_results": related_results[:3],
            "lirec_identify_snippet": build_lirec_identify_snippet(target, neighborhood),
            "prompt": prompt,
        })

    return prompts


def _neighbor_coefficients(coeffs: list[int], deltas: tuple[int, ...]) -> list[int]:
    """Apply small integer perturbations while preserving a nonzero leading term."""
    out = list(coeffs)
    for i, delta in enumerate(deltas[: len(out)]):
        out[i] += delta
    if out and out[0] == 0:
        out[0] = 1 if coeffs[0] >= 0 else -1
    return out


def _transform_polynomial_coefficients(coeffs: list[int], scale: int = 1, shift: int = 0) -> list[int]:
    """Return coefficients for P(scale*n + shift)."""
    if not coeffs:
        return []
    try:
        import sympy as sp

        n = sp.symbols("n")
        degree = len(coeffs) - 1
        expr = sum(sp.Integer(coeff) * n ** (degree - idx) for idx, coeff in enumerate(coeffs))
        transformed = sp.expand(expr.subs(n, scale * n + shift))
        poly = sp.Poly(transformed, n)
        return [int(sp.nsimplify(c)) for c in poly.all_coeffs()]
    except Exception:
        samples = [evaluate_polynomial(coeffs, scale * n + shift) for n in range(1, len(coeffs) + 2)]
        fitted = fit_polynomial_from_sequence(samples)
        return [int(round(float(c))) for c in fitted.get("coefficients", coeffs)]


def generate_seed_suggestions(
    discoveries: list[dict[str, Any]],
    encoded_patterns: list[dict[str, Any]],
    template_data: dict[str, Any],
    max_seeds: int = 10,
) -> list[dict[str, Any]]:
    """Generate new candidate polynomial regions to bias future CF search."""
    existing = {
        (tuple((d.get("params", {}) or {}).get("an", []) or []),
         tuple((d.get("params", {}) or {}).get("bn", []) or []))
        for d in discoveries
        if d.get("family") == "continued_fraction"
    }

    scored: list[dict[str, Any]] = []
    successful = [
        p for p in encoded_patterns
        if p.get("status") in ("novel_proven", "verified_known", "novel_unproven")
    ]
    template_bonus = 0.1 if template_data.get("template_count", 0) else 0.0

    # 1. Local extrapolation around successful linear-b families.
    for item in successful:
        an = [int(round(x)) for x in item.get("a_coefficients", [])]
        bn = [int(round(x)) for x in item.get("b_coefficients", [])]
        if len(an) != 1 or len(bn) not in (2, 3):
            continue

        base_score = 0.72 + template_bonus + min(0.15, 0.1 * float(item.get("confidence", 0.0)))
        if len(bn) == 2:
            perturbations = [
                (1, 0, 0), (-1, 0, 0),
                (0, 1, 0), (0, -1, 0),
                (1, 1, -1), (1, -1, 1),
            ]
        else:
            perturbations = [
                (1, 0, 1), (0, 1, 0), (1, -1, 1),
                (0, 2, 1), (1, 1, -1),
            ]

        for delta in perturbations:
            cand_an = _neighbor_coefficients(an, (delta[0],))
            cand_bn = _neighbor_coefficients(bn, delta[1:])
            key = (tuple(cand_an), tuple(cand_bn))
            if key in existing:
                continue
            existing.add(key)

            candidate_targets = [item.get("target") or "unknown", *expand_target_neighborhood(item.get("target"))[:3]]
            scored.append({
                "score": round(base_score, 4),
                "family": "continued_fraction",
                "source": "relay_local_extrapolation",
                "candidate_targets": candidate_targets,
                "rationale": (
                    f"Perturb successful {item['shape']} seed "
                    f"a(n)={item['a_formula']}, b(n)={item['b_formula']}"
                ),
                "params": {
                    "_family": "continued_fraction",
                    "an": cand_an,
                    "bn": cand_bn,
                    "relay_origin": item.get("id"),
                    "candidate_targets": candidate_targets,
                },
            })

    # 2. Index-shift probes inspired by Apéry/Ramanujan accelerants.
    for item in successful:
        an = [int(round(x)) for x in item.get("a_coefficients", [])]
        bn = [int(round(x)) for x in item.get("b_coefficients", [])]
        if not an or not bn:
            continue

        candidate_targets = [item.get("target") or "unknown", *expand_target_neighborhood(item.get("target"))[:3]]
        base_score = 0.84 + template_bonus + min(0.18, 0.12 * float(item.get("confidence", 0.0)))
        for label, scale, shift in (("n->n+1", 1, 1), ("n->2n", 2, 0), ("n->2n+1", 2, 1)):
            cand_an = _transform_polynomial_coefficients(an, scale=scale, shift=shift)
            cand_bn = _transform_polynomial_coefficients(bn, scale=scale, shift=shift)
            key = (tuple(cand_an), tuple(cand_bn))
            if key in existing:
                continue
            existing.add(key)
            scored.append({
                "score": round(base_score, 4),
                "family": "continued_fraction",
                "source": "relay_index_transform",
                "candidate_targets": candidate_targets,
                "rationale": (
                    f"Apply {label} to successful {item['shape']} seed "
                    "for an Euler-Ramanujan style acceleration test"
                ),
                "params": {
                    "_family": "continued_fraction",
                    "an": cand_an,
                    "bn": cand_bn,
                    "relay_origin": item.get("id"),
                    "transform": label,
                    "candidate_targets": candidate_targets,
                },
            })

    # 3. Synthetic probes for square-like quadratic denominators.
    quadratic_seen = any(len((p.get("b_coefficients") or [])) == 3 for p in successful)
    if quadratic_seen or not scored:
        preferred_A = sorted({int(round((p.get("a_coefficients") or [1])[0])) for p in successful}) or [1, 2, 3]
        for A in preferred_A[:3]:
            for k in (2, 3, 4):
                bn = [k * k, 2 * k, 1]
                key = ((A,), tuple(bn))
                if key in existing:
                    continue
                existing.add(key)
                scored.append({
                    "score": 0.63 + template_bonus,
                    "family": "continued_fraction",
                    "source": "relay_quadratic_square_probe",
                    "candidate_targets": ["catalan", "zeta3", "pi^2"],
                    "rationale": (
                        "Probe constant-a / quadratic-b families with square leading term; "
                        "useful for Catalan/zeta-type scans and special-function detection"
                    ),
                    "params": {
                        "_family": "continued_fraction",
                        "an": [A],
                        "bn": bn,
                        "relay_origin": "quadratic_square_family",
                        "candidate_targets": ["catalan", "zeta3", "pi^2"],
                    },
                })

    scored.sort(key=lambda item: (-item["score"], item["source"]))
    return scored[:max_seeds]


def _parse_coeff_list(value: Any) -> list[int]:
    """Normalize coefficient lists from JSON/CSV strings or Python lists."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [int(round(float(v))) for v in value]
    if isinstance(value, tuple):
        return [int(round(float(v))) for v in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [int(round(float(v))) for v in parsed]
    except Exception:
        pass
    nums = re.findall(r"-?\d+", text)
    return [int(n) for n in nums]


def normalize_external_record(record: dict[str, Any], source: str = "external") -> dict[str, Any] | None:
    """Map JSON/CSV rows from LIReC or other corpora into relay-chain discovery format."""
    an = _parse_coeff_list(record.get("an") or record.get("a_n") or record.get("a_coeffs"))
    bn = _parse_coeff_list(record.get("bn") or record.get("b_n") or record.get("b_coeffs"))
    family = record.get("family") or ("continued_fraction" if an or bn else "external")
    if family == "continued_fraction" and not (an and bn):
        return None

    value = record.get("value")
    try:
        value = float(value) if value not in (None, "") else 0.0
    except Exception:
        value = 0.0

    confidence = record.get("confidence", record.get("score", 0.75))
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.75

    return {
        "id": str(record.get("id") or record.get("name") or f"{source}_{abs(hash(str(record))) % 10**8}"),
        "family": family,
        "status": record.get("status", "verified_known"),
        "confidence": confidence,
        "target": record.get("target") or record.get("constant") or record.get("name") or "unknown",
        "expression": record.get("expression") or record.get("formula") or record.get("name") or source,
        "value": value,
        "params": {"an": an, "bn": bn},
        "metadata": {"source": source, "raw_record": record},
    }


def load_discoveries_from_csv(path: str | Path, source: str = "csv") -> list[dict[str, Any]]:
    """Load normalized discovery candidates from a CSV export."""
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            item = normalize_external_record(dict(row), source=source)
            if item is not None:
                rows.append(item)
    return rows


def load_external_discoveries(path: str | Path, source: str = "external") -> list[dict[str, Any]]:
    """Load a JSON or CSV corpus of external results into relay-chain discovery format."""
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        return load_discoveries_from_csv(path, source=source)

    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        for key in ("discoveries", "results", "items", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]

    rows: list[dict[str, Any]] = []
    for row in data if isinstance(data, list) else []:
        if isinstance(row, dict):
            item = normalize_external_record(row, source=source)
            if item is not None:
                rows.append(item)
    return rows


def execute_relay_chain(
    discoveries: list[dict[str, Any]],
    output_dir: str | Path = "results",
    max_seeds: int = 10,
    results_catalog: list[dict[str, Any]] | None = None,
    prompt_limit: int = 12,
) -> dict[str, Any]:
    """Run the full relay chain and persist the resulting artifacts."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    encoded_patterns = extract_cf_patterns(discoveries)
    template_data = build_meta_conjectures(discoveries)
    prompts = build_semantic_prompts(
        encoded_patterns,
        results_catalog=results_catalog,
        max_prompts=prompt_limit,
    )
    seeds = generate_seed_suggestions(discoveries, encoded_patterns, template_data, max_seeds=max_seeds)

    metrics_path = out_dir / "relay_chain_cf_metrics.json"
    templates_path = out_dir / "relay_chain_templates.json"
    prompts_path = out_dir / "relay_chain_llm_prompts.json"
    seeds_path = out_dir / "relay_chain_seed_pool.json"
    summary_path = out_dir / "relay_chain_summary.json"

    metrics_path.write_text(json.dumps(encoded_patterns, indent=2, default=str), encoding="utf-8")
    templates_path.write_text(json.dumps(template_data, indent=2, default=str), encoding="utf-8")
    prompts_path.write_text(json.dumps(prompts, indent=2, default=str), encoding="utf-8")
    seeds_path.write_text(json.dumps(seeds, indent=2, default=str), encoding="utf-8")

    results_catalog_path = None
    if results_catalog:
        results_catalog_path = out_dir / "relay_chain_results_catalog.json"
        results_catalog_path.write_text(json.dumps(results_catalog, indent=2, default=str), encoding="utf-8")

    summary = {
        "recognized_count": len(encoded_patterns),
        "template_count": template_data.get("template_count", 0),
        "prompt_count": len(prompts),
        "seed_count": len(seeds),
        "metrics_path": str(metrics_path),
        "templates_path": str(templates_path),
        "prompts_path": str(prompts_path),
        "seed_pool_path": str(seeds_path),
        "results_catalog_path": str(results_catalog_path) if results_catalog_path else "",
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def load_discoveries_from_json(path: str | Path) -> list[dict[str, Any]]:
    """Load discoveries from either `ramanujan_state.json` or `ramanujan_results.json`."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, dict) and "discoveries" in data:
        return list(data.get("discoveries", []))

    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in (
        "top_discoveries",
        "novel_proven",
        "verified_known",
        "novel_unproven",
        "validated",
    ):
        for item in data.get(key, []):
            disc_id = item.get("id")
            if disc_id and disc_id in seen:
                continue
            if disc_id:
                seen.add(disc_id)
            combined.append(item)
    return combined


def run_from_state_file(
    state_path: str | Path = "results/ramanujan_state.json",
    output_dir: str | Path = "results",
    max_seeds: int = 10,
    lirec_input: str | Path | None = None,
    scrape_results: bool = False,
    results_url: str = "https://www.ramanujanmachine.com/results/",
    prompt_limit: int = 12,
) -> dict[str, Any]:
    """Convenience wrapper for relay-only CLI mode."""
    discoveries = load_discoveries_from_json(state_path)
    if lirec_input:
        discoveries.extend(load_external_discoveries(lirec_input, source="lirec"))

    results_catalog = scrape_results_catalog(results_url) if scrape_results else []
    return execute_relay_chain(
        discoveries,
        output_dir=output_dir,
        max_seeds=max_seeds,
        results_catalog=results_catalog,
        prompt_limit=prompt_limit,
    )


def main() -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run the Ramanujan relay chain on saved discoveries")
    parser.add_argument("--state", default="results/ramanujan_state.json", help="Path to ramanujan_state.json or ramanujan_results.json")
    parser.add_argument("--output-dir", default="results", help="Directory for relay-chain JSON artifacts")
    parser.add_argument("--max-seeds", type=int, default=10, help="Maximum number of synthetic seeds to emit")
    parser.add_argument("--prompt-limit", type=int, default=12, help="Maximum number of LLM semantic prompts to emit")
    parser.add_argument("--lirec-input", default="", help="Optional LIReC/JSON/CSV export to merge into the relay corpus")
    parser.add_argument("--scrape-results", action="store_true", help="Scrape the public Ramanujan Machine results page and save a PDF catalog")
    parser.add_argument("--results-url", default="https://www.ramanujanmachine.com/results/", help="Results-page URL used when --scrape-results is enabled")
    args = parser.parse_args()

    summary = run_from_state_file(
        args.state,
        output_dir=args.output_dir,
        max_seeds=args.max_seeds,
        lirec_input=args.lirec_input or None,
        scrape_results=args.scrape_results,
        results_url=args.results_url,
        prompt_limit=args.prompt_limit,
    )
    print("Relay chain complete")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
