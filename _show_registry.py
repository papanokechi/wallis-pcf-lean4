import json

data = json.load(open('ramanujan_registry.json'))
conjs = data['conjectures']

seen = set()
unique = []
for c in conjs:
    key = (tuple(c['alpha_coeffs']), tuple(c['beta_coeffs']))
    if key not in seen:
        seen.add(key)
        unique.append(c)

print(f"Total conjectures: {len(conjs)}")
print(f"Unique (deduped): {len(unique)}")
print()
print("UNIQUE CONJECTURES:")
print("=" * 80)
for i, c in enumerate(unique, 1):
    tgt = c['target_constant']
    alpha = c['pcf_alpha']
    beta = c['pcf_beta']
    digs = c['digits_verified']
    conv = c['convergence']
    val = c['numerical_value'][:25] if c.get('numerical_value') else '?'
    algo = c['algorithm']
    print(f"  {i}. [{tgt}] a(n)={alpha}, b(n)={beta}")
    print(f"     {digs}d | {conv} | {algo} | val={val}")
print()
from collections import Counter
by_const = Counter(c['target_constant'] for c in unique)
print("By constant:", dict(by_const))
