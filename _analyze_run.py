"""Analyze a ramanujan_breakthrough_generator run — rich analysis."""
import json, sys
from pathlib import Path
from collections import Counter, defaultdict

logfile = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ramanujan_discoveries.jsonl")
if not logfile.exists():
    print(f"No log file: {logfile}")
    sys.exit(1)

lines = logfile.read_text().strip().split('\n')
all_entries = []
seen = {}
for l in lines:
    d = json.loads(l)
    all_entries.append(d)
    key = (tuple(d['a']), tuple(d['b']))
    # Keep the best version (highest verified_digits)
    if key not in seen or (d.get('verified_digits', 0) or 0) > (seen[key].get('verified_digits', 0) or 0):
        seen[key] = d

# ── Categorize ────────────────────────────────────────────────────────────────
categories = defaultdict(list)
for v in seen.values():
    m = v['match']
    if 'pi' in m.lower() or 'S^(' in m:
        categories['pi'].append(v)
    elif 'phi' in m.lower() or 'sqrt(5)' in m:
        categories['phi'].append(v)
    elif m in ('e',) or ('e' in m and 'euler' not in m.lower() and 'zeta' not in m.lower()):
        categories['e'].append(v)
    elif 'log' in m.lower():
        categories['log'].append(v)
    elif 'zeta' in m.lower():
        categories['zeta'].append(v)
    elif 'euler' in m.lower():
        categories['euler_gamma'].append(v)
    elif 'sqrt' in m.lower():
        categories['sqrt'].append(v)
    elif 'catalan' in m.lower():
        categories['catalan'].append(v)
    elif 'Gamma' in m:
        categories['Gamma'].append(v)
    elif v['a'] == [-2,4,-2] or m in ('1','2','3','4','5','6','7','8'):
        categories['trivial'].append(v)
    elif '**(' in m and m.count('/') > 3:
        categories['spurious'].append(v)
    else:
        categories['rational'].append(v)

# ── b(n) family distribution ─────────────────────────────────────────────────
b_families = Counter(tuple(v['b']) for v in seen.values())
b_family_details = defaultdict(list)
for v in seen.values():
    b_family_details[tuple(v['b'])].append(v)

# ── Print report ──────────────────────────────────────────────────────────────
interesting_cats = ['pi', 'phi', 'e', 'log', 'zeta', 'euler_gamma', 'sqrt', 'catalan', 'Gamma']
total_interesting = sum(len(categories[c]) for c in interesting_cats)

print(f"{'='*70}")
print(f"  RUN ANALYSIS: {logfile}")
print(f"{'='*70}")
print(f"Log entries: {len(lines)}  |  Unique CFs: {len(seen)}")
print()
print("Category breakdown:")
for cat in interesting_cats:
    if categories[cat]:
        print(f"  {cat:15s}: {len(categories[cat])}")
print(f"  {'rational':15s}: {len(categories['rational'])}")
print(f"  {'trivial':15s}: {len(categories['trivial'])}")
print(f"  {'spurious':15s}: {len(categories['spurious'])}")
print(f"\nSignal-to-noise: {total_interesting}/{len(seen)} = "
      f"{100*total_interesting/max(len(seen),1):.1f}%")

# ── Top 10 by quality score ──────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"  TOP 10 BY QUALITY  (score = verified_digits - 2*complexity)")
print(f"{'─'*70}")
scored = []
for v in seen.values():
    m = v['match']
    if m in ('1','2','3','4','5','6','7','8'):
        continue
    if '**(' in m and m.count('/') > 3:
        continue
    vd = v.get('verified_digits', 0) or 0
    cx = v.get('complexity', 5) or 5
    score = vd - 2 * cx
    scored.append((score, vd, cx, v))
scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
for i, (score, vd, cx, v) in enumerate(scored[:10], 1):
    a_str = str(v['a'])
    b_str = str(v['b'])
    print(f"  {i:2d}. {v['match']:22s}  a={a_str:18s} b={b_str:10s}  "
          f"vd={vd:5.1f}  cx={cx:.1f}  score={score:.1f}")

# ── Detailed irrational hits ─────────────────────────────────────────────────
for cat in interesting_cats:
    hits = categories[cat]
    if not hits:
        continue
    print(f"\n{cat.upper()} hits ({len(hits)}):")
    for v in sorted(hits, key=lambda x: str(x['a'])):
        cx = v.get('complexity', '?')
        vd = v.get('verified_digits', '?')
        a, b = str(v['a']), str(v['b'])
        print(f"  a={a:20s} b={b:10s} -> {v['match']:22s}  cx={cx}  vd={vd}")

# ── Family size distribution ─────────────────────────────────────────────────
print(f"\nTop 10 b(n) families by size:")
for bkey, count in b_families.most_common(10):
    bstr = ' + '.join(f'{c}n^{i}' if i > 0 else str(c) for i, c in enumerate(bkey) if c != 0) or '0'
    # Average verified digits for this family
    members = b_family_details[bkey]
    vds = [m.get('verified_digits', 0) or 0 for m in members if m.get('verified_digits')]
    avg_vd = sum(vds) / len(vds) if vds else 0.0
    n_interesting = sum(1 for m in members
                       if m['match'] not in ('1','2','3','4','5','6','7','8')
                       and not ('**(' in m['match'] and m['match'].count('/') > 3))
    print(f"  b(n) = {bstr:20s}  ({count} total, {n_interesting} interesting, "
          f"avg_vd={avg_vd:.0f})")

# ── Discovery rate over time ─────────────────────────────────────────────────
cycle_nums = []
for e in all_entries:
    c = e.get('cycle', 0)
    if c:
        cycle_nums.append(c)
if cycle_nums:
    max_cycle = max(cycle_nums)
    bins = min(10, max_cycle)
    if bins > 0:
        bin_size = max_cycle // bins
        if bin_size > 0:
            print(f"\nDiscovery rate by cycle range:")
            for i in range(bins):
                lo = i * bin_size + 1
                hi = (i + 1) * bin_size
                count = sum(1 for c in cycle_nums if lo <= c <= hi)
                bar = '#' * count
                print(f"  {lo:5d}-{hi:5d}: {count:3d} {bar}")

print(f"\n{'='*70}")
