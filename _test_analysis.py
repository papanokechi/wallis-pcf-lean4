"""Quick test of the analysis pipeline."""
from ramanujan_agent.analysis import analyze_novel_cf

# Test with a linear-b CF: a(n)=[-4], b(n)=[4, 2]
d = {
    'params': {'an': [-4], 'bn': [4, 2]},
    'value': 1.284,
    'family': 'continued_fraction',
    'expression': 'GCF with a(n)=[-4], b(n)=[4, 2]',
    'metadata': {},
    'provenance': {'prec': 60, 'depth': 300},
}
r = analyze_novel_cf(d, prec=100)
print("value_20_digits:", r.get("value_20_digits"))
print("is_algebraic:", r.get("is_algebraic"))
print("algebraic_analysis:", r.get("algebraic_analysis", "")[:100])
print("cf_class:", r.get("cf_class"))
pr = r.get("pslq_recognition", {})
print("pslq found:", pr.get("found"))
if pr.get("found"):
    print("pslq expr:", pr.get("expression", "")[:100])
    print("pslq residual:", pr.get("residual"))
    print("pslq max_coeff:", pr.get("max_coeff"))
else:
    print("pslq note:", pr.get("note", ""))
print("pslq_stable:", r.get("pslq_stable"))
stab = r.get("pslq_stability_table", [])
for s in stab:
    p = s.get("precision", "?")
    f = s.get("found", "?")
    res = s.get("residual", "?")
    mr = s.get("matches_reference", "?")
    mc = s.get("max_coeff", "?")
    print(f"  [{p} dps] found={f} residual={res} matches_ref={mr} max_coeff={mc}")

repro = r.get("reproducibility", {})
print("\nReproducibility bundle keys:", list(repro.keys()))
print("  env:", repro.get("environment", {}))
