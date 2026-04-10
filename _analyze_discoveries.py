"""Analyze Ramanujan discovery log: patterns, clustering, dominant families."""
import json
from collections import Counter
from pathlib import Path

data = []
for line in Path('ramanujan_discoveries.jsonl').read_text().splitlines():
    if line.strip():
        data.append(json.loads(line))

print(f"Total log entries: {len(data)}")

# --- By type ---
types = Counter(d.get('type', 'evo') for d in data)
print(f"\nBy type: {dict(types)}")

# --- By match target ---
match_names = Counter()
for d in data:
    m = d['match']
    # Normalize: extract the constant name from "3/4*pi" etc.
    if '*' in m:
        parts = m.split('*', 1)
        match_names[parts[-1]] += 1
    else:
        match_names[m] += 1
print(f"\nTarget constant frequency (top 15):")
for name, count in match_names.most_common(15):
    print(f"  {name:25s}  {count}")

# --- Dominant a(n) degree ---
a_deg = Counter(len(d['a'])-1 for d in data)
b_deg = Counter(len(d['b'])-1 for d in data)
print(f"\na(n) degree distribution: {dict(sorted(a_deg.items()))}")
print(f"b(n) degree distribution: {dict(sorted(b_deg.items()))}")

# --- Top b(n) families ---
b_families = Counter(tuple(d['b']) for d in data)
print(f"\nTop 10 b(n) families:")
for bk, count in b_families.most_common(10):
    print(f"  b(n)={str(list(bk)):20s}  ({count} members)")

# --- Top a(n) patterns ---
ab_pairs = Counter((tuple(d['a']), tuple(d['b'])) for d in data)
print(f"\nTop 10 most repeated (a,b) pairs:")
for (a, b), count in ab_pairs.most_common(10):
    if count > 1:
        d0 = next(d for d in data if tuple(d['a'])==a and tuple(d['b'])==b)
        print(f"  a={list(a)} b={list(b)} -> {d0['match']}  (repeated {count}x)")

# --- Coefficient magnitude distribution ---
all_coeffs = []
for d in data:
    all_coeffs.extend(abs(c) for c in d['a'])
    all_coeffs.extend(abs(c) for c in d['b'])
print(f"\nCoefficient stats: max={max(all_coeffs)}, mean={sum(all_coeffs)/len(all_coeffs):.1f}")

# --- Non-trivial discoveries (not integers, not spurious) ---
interesting = []
for d in data:
    m = d['match']
    # Skip pure integers
    try:
        int(m)
        continue
    except ValueError:
        pass
    # Skip overly complex algebraic PSLQ matches
    if '**(' in m and m.count('/') > 3:
        continue
    if m.count('*') > 4:
        continue
    interesting.append(d)

print(f"\n=== NON-TRIVIAL discoveries: {len(interesting)} ===")
for d in interesting:
    vd = d.get('verified_digits', '?')
    cx = d.get('complexity', '?')
    print(f"  a={str(d['a']):25s} b={str(d['b']):15s} -> {d['match']:30s}  (vd={vd}, cx={cx})")

# --- Zeta(3) specific ---
zeta_hits = [d for d in data if 'zeta' in d['match'].lower()]
print(f"\nZeta-related hits: {len(zeta_hits)}")
for d in zeta_hits:
    print(f"  a={d['a']} b={d['b']} -> {d['match']}")

# --- Catalan specific ---
cat_hits = [d for d in data if 'catalan' in d['match'].lower()]
print(f"\nCatalan-related hits: {len(cat_hits)}")
for d in cat_hits[:10]:
    print(f"  a={d['a']} b={d['b']} -> {d['match']}")
