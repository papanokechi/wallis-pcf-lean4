"""Export discovery data for the markdown report."""
import json
from collections import defaultdict

files = ['master_discoveries.jsonl', 'ramanujan_discoveries.jsonl',
         'deep_space_discoveries.jsonl', 'even_k_discoveries.jsonl']
all_disc = {}
for f in files:
    try:
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                k = json.dumps([d.get('a'), d.get('b')])
                vd = d.get('verified_digits', 0) or 0
                if k not in all_disc or vd > (all_disc[k].get('verified_digits', 0) or 0):
                    all_disc[k] = d
    except FileNotFoundError:
        pass

ranked = sorted(all_disc.values(), key=lambda x: -(x.get('verified_digits', 0) or 0))

# Categorize
categories = defaultdict(list)
for d in ranked:
    m = str(d.get('match', d.get('constant', '?')))
    if 'S^(' in m:
        categories['S^(m) Pi Family'].append(d)
    elif '4/pi' in m or 'pi' in m.lower():
        categories['Pi-Related'].append(d)
    elif 'phi' in m.lower():
        categories['Golden Ratio'].append(d)
    elif 'sqrt' in m.lower():
        categories['Algebraic Irrationals'].append(d)
    elif m.strip() == 'e' or '*e' in m:
        categories['Euler e'].append(d)
    else:
        categories['Rational / Other'].append(d)

timestamps = sorted([d.get('timestamp', '') for d in all_disc.values() if d.get('timestamp')])

print(f"TOTAL_UNIQUE: {len(all_disc)}")
print(f"FIRST_TS: {timestamps[0] if timestamps else 'N/A'}")
print(f"LAST_TS: {timestamps[-1] if timestamps else 'N/A'}")
print()

for cat_name in ['S^(m) Pi Family', 'Pi-Related', 'Golden Ratio',
                 'Algebraic Irrationals', 'Euler e', 'Rational / Other']:
    items = categories.get(cat_name, [])
    if items:
        best = max(items, key=lambda x: x.get('verified_digits', 0) or 0)
        bvd = best.get('verified_digits', 0)
        bm = best.get('match', '?')
        print(f"CAT|{cat_name}|{len(items)}|{bvd}|{bm}")

print()
print("=== TOP 50 DEDUPLICATED ===")
seen = set()
count = 0
for d in ranked:
    a = tuple(d.get('a', []))
    b = tuple(d.get('b', []))
    key = (a, b)
    if key in seen:
        continue
    seen.add(key)
    if count >= 50:
        break
    count += 1
    vd = d.get('verified_digits', 0) or 0
    m = str(d.get('match', d.get('constant', '?')))
    val = d.get('value', '?')
    cx = d.get('complexity', '?')
    src = d.get('shard', d.get('source', '?'))
    print(f"ROW|{count}|{vd}|{list(a)}|{list(b)}|{m}|{val}|{cx}|{src}")
