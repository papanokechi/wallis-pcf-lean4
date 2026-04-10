#!/usr/bin/env python3
"""Quick analysis of deep sweep results."""
import json

d = json.load(open("deep_sweep_zeta5_full.json"))
hv = d["results"][0]["high_value"]

multi = [x for x in hv if x["is_multi_constant"]]
deep = [x for x in hv if x["alpha_deg"] >= 4 or x["beta_deg"] >= 4]
zeta5_hits = [x for x in hv if "zeta5" in x["constant"]]
zeta7_hits = [x for x in hv if "zeta7" in x["constant"]]
hi_prec = [x for x in hv if x["precision"] >= 200]

print("=== Deep Sweep Analysis ===")
print(f"  Total high-value: {len(hv)}")
print(f"  Multi-constant:   {len(multi)}")
print(f"  Deep (deg>=4):    {len(deep)}")
print(f"  zeta5 relations:  {len(zeta5_hits)}")
print(f"  zeta7 relations:  {len(zeta7_hits)}")
print(f"  precision>=200:   {len(hi_prec)}")
print()

if multi:
    print("Multi-constant discoveries:")
    for m in multi:
        print(f"  {m['constant']}  deg=({m['alpha_deg']},{m['beta_deg']})  {m['precision']}dp")
        print(f"    {m['formula']}")
    print()

if deep:
    print(f"Deep (high-order) discoveries ({len(deep)}):")
    for dd in deep[:10]:
        print(f"  {dd['constant']}  deg=({dd['alpha_deg']},{dd['beta_deg']})  {dd['precision']}dp")
        print(f"    {dd['formula'][:90]}")
    print()

if zeta7_hits:
    print(f"zeta7 discoveries ({len(zeta7_hits)}):")
    for z in zeta7_hits:
        print(f"  deg=({z['alpha_deg']},{z['beta_deg']})  {z['precision']}dp")
        print(f"    {z['formula'][:90]}")
    print()

# Distribution by constant
from collections import Counter
const_dist = Counter(x["constant"] for x in hv)
print("Distribution by constant:")
for k, v in const_dist.most_common():
    print(f"  {k}: {v}")
