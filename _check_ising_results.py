import json
d = json.load(open("results/pcf_search_Tc_3d.json"))
p1 = d["phase1"]
print(f"Phase1: {p1['cycles']} cycles, {p1['prec']}dp")
print(f"  Discoveries: {len(p1['discoveries'])}")
print(f"  Near-misses: {len(p1['near_misses'])}")
print(f"  Best: {p1['best_digits']:.2f}d")
print(f"  Elapsed: {p1['elapsed']:.0f}s")
for nm in p1["near_misses"][:5]:
    print(f"  {nm['digits']:.2f}d -> {nm['closest']}  a={nm['a']} b={nm['b']}")
p2 = d.get("phase2")
if p2:
    print(f"\nPhase2: {p2['prec']}dp, {len(p2['discoveries'])} disc, best={p2['best_digits']:.2f}d")
    for nm in p2.get("near_misses", [])[:5]:
        print(f"  {nm['digits']:.2f}d -> {nm['closest']}  a={nm['a']} b={nm['b']}")
else:
    print("\nPhase2: NOT RUN (only Phase1 completed)")
