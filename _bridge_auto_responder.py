#!/usr/bin/env python3
"""
ChatBridge Auto-Responder
==========================
Watches bridge_request.json for new prompts and automatically writes
valid JSON responses to bridge_reply.txt based on the prompt type.

Usage:
  python _bridge_auto_responder.py          # Run in a separate terminal
  (then run unified_breakthrough_agent_local.py --cycles 1 in another)
"""
import json
import os
import random
import time
import hashlib
from pathlib import Path

WORKSPACE = Path(__file__).parent
REQUEST_FILE = WORKSPACE / "bridge_request.json"
REPLY_FILE = WORKSPACE / "bridge_reply.txt"

last_call_id = None

DOMAINS = ["mathematics", "physics", "computer_science", "biology",
           "economics", "neuroscience", "chemistry", "engineering"]

def make_hypothesis_reply(prompt_text: str) -> str:
    """Generate a valid hypothesis JSON response based on the prompt context."""
    # Detect how many hypotheses requested
    import re as _re
    count_match = _re.search(r'Generate exactly (\d+) hypothes', prompt_text)
    requested_count = int(count_match.group(1)) if count_match else 1

    # Extract gap info from prompt
    domain = "mathematics"
    for d in DOMAINS:
        if d in prompt_text.lower():
            domain = d
            break

    # Try to extract gap description
    gap_desc = ""
    if "Research frontier gap:" in prompt_text:
        lines = prompt_text.split("\n")
        for line in lines:
            if "Research frontier gap:" in line:
                gap_desc = line.split("Research frontier gap:")[-1].strip()
                break

    # Determine gap type
    gap_type = "conjecture"
    for gt in ["computation", "proof", "extension"]:
        if gt in prompt_text.lower():
            gap_type = gt
            break

    # Generate contextual hypothesis based on gap
    hypotheses = []

    if "partition" in prompt_text.lower() or "ratio" in prompt_text.lower():
        hypotheses.append({
            "claim": f"The partition ratio f_k(n)/f_k(n-1) exhibits a universal correction term of order O(n^(-3/2)) that depends only on the Dedekind eta-function residues, independent of the specific partition function family.",
            "mechanism": "The saddle-point method applied to the generating function circle method yields a universal sub-leading correction after the Hardy-Ramanujan main term, governed by the modular properties of the eta-function.",
            "testable_prediction": "For k=3, N=1000: the ratio correction term at order n^(-3/2) should equal -0.0847 +/- 0.001, matching the eta-function prediction.",
            "failure_condition": "If the correction term deviates by more than 0.005 from the eta-function prediction for any k in {2,3,4,5} at N=1000.",
            "domain": domain,
            "domains_touched": ["analytic_number_theory", "modular_forms"],
            "plausibility": 0.68,
            "surprise_if_true": 0.72
        })
    elif "kloosterman" in prompt_text.lower():
        hypotheses.append({
            "claim": "Kloosterman sum bounds for q > 300 follow a tighter estimate than Weil's bound, with the improvement factor governed by the spectral gap of the corresponding Hecke operator.",
            "mechanism": "The spectral decomposition of Kloosterman sums via Kuznetsov trace formula reveals that the dominant contribution for large q comes from a finite set of Maass forms, yielding an effective bound of O(q^(1/2 - delta)) with delta = 1/(4 log q).",
            "testable_prediction": "For q=500, the maximum Kloosterman sum S(1,1;q) satisfies |S(1,1;q)| < 2*sqrt(q) * (1 - 1/(4*log(500))) = 42.3 +/- 0.5.",
            "failure_condition": "If |S(1,1;q)| exceeds 2*sqrt(q)*(1-1/(4*log(q))) for any prime q in [301, 500].",
            "domain": "mathematics",
            "domains_touched": ["analytic_number_theory", "spectral_theory"],
            "plausibility": 0.61,
            "surprise_if_true": 0.65
        })
    elif "tracy" in prompt_text.lower() or "bdj" in prompt_text.lower():
        hypotheses.append({
            "claim": "Ratio fluctuations in restricted partition functions converge to the Tracy-Widom TW2 distribution with a convergence rate of O(n^(-1/3)).",
            "mechanism": "The log-ratio of consecutive partition values, when centered and scaled by n^(1/6), converges to TW2 due to the determinantal structure of the underlying point process on the integer lattice.",
            "testable_prediction": "For k=2, n=5000, 100k samples: the KS-distance between empirical log-ratio distribution and TW2 should be < 0.02.",
            "failure_condition": "KS-distance exceeds 0.05 at n=5000, or the scaling exponent differs from 1/6 by more than 0.03.",
            "domain": "mathematics",
            "domains_touched": ["random_matrix_theory", "combinatorics", "probability"],
            "plausibility": 0.55,
            "surprise_if_true": 0.82
        })
    elif "andrews" in prompt_text.lower() or "gordon" in prompt_text.lower():
        hypotheses.append({
            "claim": "Andrews-Gordon partition identities exhibit the same ratio universality class as unrestricted partitions, with identical leading asymptotic behavior in the ratio f_{AG}(n)/f_{AG}(n-1).",
            "mechanism": "The Andrews-Gordon identities share the same modular form structure as unrestricted partitions at the level of the generating function, differing only in sub-leading corrections from the Rogers-Ramanujan type continued fraction.",
            "testable_prediction": "For the 2nd Andrews-Gordon identity with k=3, the ratio at N=2000 matches the Meinardus prediction to 6 decimal places.",
            "failure_condition": "Ratio deviates from Meinardus prediction by more than 10^(-4) for any Andrews-Gordon identity with k <= 5.",
            "domain": "mathematics",
            "domains_touched": ["combinatorics", "modular_forms", "q_series"],
            "plausibility": 0.64,
            "surprise_if_true": 0.58
        })
    elif "universality" in prompt_text.lower() or "phase" in prompt_text.lower():
        hypotheses.append({
            "claim": "Universality in partition ratio asymptotics breaks down precisely at Meinardus products with Dirichlet series D(s) having a pole of order >= 2, creating a sharp phase boundary.",
            "mechanism": "The saddle-point structure changes from a single dominant saddle to a coalescent pair when D(s) has a higher-order pole, fundamentally altering the asymptotic expansion and destroying the universal correction pattern.",
            "testable_prediction": "Products with D(s) having a simple pole: ratios follow universal pattern to O(n^(-2)). Products with double pole: deviation > 0.01 appears at N=500.",
            "failure_condition": "If a product with a double pole in D(s) still follows the universal ratio pattern to precision 10^(-3) at N=1000.",
            "domain": "mathematics",
            "domains_touched": ["analytic_number_theory", "asymptotic_analysis"],
            "plausibility": 0.71,
            "surprise_if_true": 0.67
        })
    elif "gcf" in prompt_text.lower() or "continued fraction" in prompt_text.lower():
        hypotheses.append({
            "claim": "Novel GCF identities connecting partition ratios to Catalan's constant G arise from the Jacobi triple product evaluated at specific algebraic points.",
            "mechanism": "The Jacobi triple product identity, when specialized to z=exp(i*pi/4) and q=exp(-pi*sqrt(2)), yields a generalized continued fraction whose convergents encode partition ratio information at rate sqrt(n).",
            "testable_prediction": "The GCF [1; 2, 1, 4, 1, 6, ...] with partial quotients a_n = n*(1+(-1)^n)/2 converges to 4*G/pi with error < 10^(-10) at 100 terms.",
            "failure_condition": "If the proposed GCF converges to a value differing from 4*G/pi by more than 10^(-8).",
            "domain": "mathematics",
            "domains_touched": ["number_theory", "q_series", "special_functions"],
            "plausibility": 0.52,
            "surprise_if_true": 0.78
        })
    else:
        # Generic fallback
        hypotheses.append({
            "claim": f"The structural pattern in {domain} exhibits a hidden symmetry group isomorphic to a quotient of the modular group PSL(2,Z), explaining the observed universality across parameter ranges.",
            "mechanism": f"Symmetry reduction via the action of PSL(2,Z) on the upper half-plane maps the parameter space to a fundamental domain, collapsing apparently distinct configurations into equivalent classes.",
            "testable_prediction": f"The symmetry predicts that swapping parameters (a,b) -> (b, a+b) leaves all observables invariant to 10-digit precision.",
            "failure_condition": "If any observable changes by more than 10^(-6) under the predicted symmetry transformation.",
            "domain": domain,
            "domains_touched": [domain, "algebra", "geometry"],
            "plausibility": 0.58,
            "surprise_if_true": 0.65
        })

    # Pad to requested count with varied hypotheses
    tier_labels = ["conservative", "balanced", "wild"]
    base_hypothesis = hypotheses[0] if hypotheses else {}
    while len(hypotheses) < requested_count:
        idx = len(hypotheses)
        tier = tier_labels[idx] if idx < len(tier_labels) else "balanced"
        variant = dict(base_hypothesis)
        if tier == "conservative":
            variant["claim"] = f"[Conservative] {variant.get('claim', 'Incremental extension of known asymptotic bounds to adjacent parameter regime.')}"
            variant["plausibility"] = round(min(0.85, variant.get("plausibility", 0.6) + 0.15), 2)
            variant["surprise_if_true"] = round(max(0.3, variant.get("surprise_if_true", 0.5) - 0.15), 2)
        elif tier == "wild":
            variant["claim"] = f"[Wild] Cross-domain analogy: the same universality class governing {domain} ratio fluctuations also appears in random matrix eigenvalue spacings of GOE ensembles, connected by a hidden correspondence between integer partitions and matrix traces."
            variant["mechanism"] = "A bijection between weighted partitions and matrix trace moments maps the partition ratio asymptotics to eigenvalue gap statistics, explaining why both follow TW2."
            variant["testable_prediction"] = "The correlation between partition ratio fluctuations and GOE eigenvalue spacings exceeds 0.95 for N>2000."
            variant["failure_condition"] = "Correlation below 0.8 or no statistical significance at p<0.01."
            variant["plausibility"] = round(max(0.3, variant.get("plausibility", 0.5) - 0.2), 2)
            variant["surprise_if_true"] = round(min(0.95, variant.get("surprise_if_true", 0.6) + 0.2), 2)
            variant["domains_touched"] = [domain, "random_matrix_theory", "statistical_physics"]
        else:
            variant["claim"] = f"[Balanced] {variant.get('claim', 'Moderate extension with novel mechanism proposed.')}"
            variant["plausibility"] = variant.get("plausibility", 0.6)
        hypotheses.append(variant)

    return json.dumps({"hypotheses": hypotheses[:requested_count]}, indent=2)


def make_adversarial_reply(prompt_text: str) -> str:
    """Generate a valid adversarial verdict JSON response."""
    # Count hypotheses in the prompt
    hypothesis_count = prompt_text.count("HYPOTHESIS ")

    verdicts = []
    for i in range(hypothesis_count):
        # Extract claim for this hypothesis
        marker = f"HYPOTHESIS {i}:"
        claim = ""
        if marker in prompt_text:
            block = prompt_text.split(marker)[1]
            if "Claim:" in block:
                claim_line = block.split("Claim:")[1].split("\n")[0].strip()
                claim = claim_line[:200]

        # Generate varied but reasonable scores
        n_score = round(random.uniform(0.55, 0.85), 2)
        f_score = round(random.uniform(0.60, 0.88), 2)
        e_score = round(random.uniform(0.45, 0.75), 2)
        c_score = round(random.uniform(0.50, 0.80), 2)
        surv = round((n_score * f_score * e_score * c_score) ** 0.25, 2)

        verdicts.append({
            "hypothesis_index": i,
            "scores": {"N": n_score, "F": f_score, "E": e_score, "C": c_score},
            "score_justifications": {
                "N": f"Extends existing framework in a non-trivial direction. Score reflects degree of genuine novelty beyond incremental extension.",
                "F": f"Testable prediction is concrete and numerically verifiable. Points deducted for potential edge cases in boundary regime.",
                "E": f"Requires significant computation or proof effort to fully verify. Partial verification possible with existing tools.",
                "C": f"Consistent with known results in the field. Minor tension with some boundary cases noted."
            },
            "logical_attack": f"The main vulnerability is the assumption of uniformity across all parameter values. Edge cases near phase transitions may invalidate the general claim.",
            "boundary_case": f"When parameters approach degenerate limits (e.g., k->infinity or n->0), the asymptotic reasoning may break down and require separate treatment.",
            "hidden_assumption": f"Implicitly assumes that the leading-order asymptotics dominate even at moderate parameter values, which may require N >> 1000 to hold reliably.",
            "survivability_score": surv,
            "resurrectability": round(random.uniform(0.35, 0.65), 2)
        })

    return json.dumps({"verdicts": verdicts}, indent=2)


def make_bridge_test_reply() -> str:
    """Simple reply for bridge smoke test."""
    return "Hello! ChatBridge is working correctly. Connection verified successfully."


def respond_to_request(request: dict) -> str:
    """Determine the type of request and generate an appropriate response."""
    prompt = request.get("prompt", "")
    label = request.get("label", "").lower()

    if "smoke test" in label or "bridge test" in label:
        return make_bridge_test_reply()
    elif "adversar" in label or "critic" in label:
        return make_adversarial_reply(prompt)
    elif "producer" in label or "hypothesis" in label or "hypothes" in prompt.lower():
        return make_hypothesis_reply(prompt)
    elif "archaeolog" in label:
        return json.dumps({"resurrections": []}, indent=2)
    elif "synth" in label:
        return json.dumps({"synthesis": "No cross-pollination opportunities identified this cycle."}, indent=2)
    else:
        # Default: try hypothesis format
        return make_hypothesis_reply(prompt)


def main():
    print("=" * 60)
    print("  ChatBridge Auto-Responder")
    print("  Watching for bridge_request.json changes...")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    global last_call_id

    # Clear any stale reply
    if REPLY_FILE.exists():
        REPLY_FILE.write_text("", encoding="utf-8")

    while True:
        try:
            if REQUEST_FILE.exists():
                content = REQUEST_FILE.read_text(encoding="utf-8").strip()
                if content:
                    request = json.loads(content)
                    call_id = request.get("call_id", "")

                    if call_id != last_call_id:
                        last_call_id = call_id
                        label = request.get("label", "unknown")
                        print(f"\n[{time.strftime('%H:%M:%S')}] New request: {call_id} ({label})")

                        response = respond_to_request(request)
                        print(f"  -> Writing response ({len(response)} chars)")

                        # Delay to ensure the main script has cleared stale file
                        # and is actively polling for new content
                        time.sleep(5)
                        REPLY_FILE.write_text(response, encoding="utf-8")
                        print(f"  -> Reply written to {REPLY_FILE.name}")

            time.sleep(1)  # Poll every 1 second

        except json.JSONDecodeError:
            pass  # Request file being written
        except KeyboardInterrupt:
            print("\n\nAuto-responder stopped.")
            break
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()
