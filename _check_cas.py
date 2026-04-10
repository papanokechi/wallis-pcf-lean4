"""Check CAS verification results for partial_proof candidates."""
import json

d = json.load(open('results/ramanujan_results.json'))

# Look at proof targets
pt = json.load(open('results/proof_targets.json'))
for t in pt[:3]:
    print("ID:", t.get("id", "?")[:12])
    print("  Expression:", t.get("expression", "?")[:60])
    pr = t.get("proof_result", {})
    print("  Status:", pr.get("status", "?"))
    print("  Convergence proven:", pr.get("convergence", {}).get("proven"))
    print("  Convergence theorem:", pr.get("convergence", {}).get("theorem_used"))
    cf = pr.get("closed_form", {})
    print("  Closed form identified:", cf.get("identified"))
    if cf.get("best"):
        print("  Best type:", cf["best"].get("type"))
        print("  Best expr:", str(cf["best"].get("expression", cf["best"].get("formula", "")))[:60])
    v = pr.get("verification", {})
    print("  CAS verified:", v.get("verified"))
    print("  CAS match_digits:", v.get("match_digits"))
    print("  CAS error:", v.get("error", "none"))
    print()
