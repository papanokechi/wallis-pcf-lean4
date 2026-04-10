import json, os

# Main discoveries
lines = [l for l in open('ramanujan_discoveries.jsonl').readlines() if l.strip()]
entries = [json.loads(l) for l in lines]

# Dedup by (a, b) keeping best vd
best = {}
for d in entries:
    if 'a' not in d or 'b' not in d:
        continue
    key = (tuple(d['a']), tuple(d['b']))
    vd = d.get('verified_digits', 0) or 0
    if key not in best or vd > (best[key].get('verified_digits', 0) or 0):
        best[key] = d

# Classify
pi_family_names = set(f'S^({m})' for m in range(2, 20))

families = {'pi_family': [], 'algebraic': [], 'transcendental_known': [], 'novel': []}
for key, d in sorted(best.items(), key=lambda x: -(x[1].get('verified_digits', 0) or 0)):
    m = d.get('match', '?')
    base = m.split('*')[-1] if '*' in m else m
    if base in pi_family_names or '4/pi' in m or '2/pi' in m or '3/8' in m or '3/4' in m or '4/3' in m:
        families['pi_family'].append(d)
    elif 'sqrt' in base or 'phi' in base:
        families['algebraic'].append(d)
    elif base in ('e', 'log2', 'log3', 'euler_g', 'zeta3', 'catalan'):
        families['transcendental_known'].append(d)
    else:
        families['novel'].append(d)

s = json.load(open('ramanujan_state.json'))
stale = s['cycle'] - s['last_discovery_cycle']

print('=' * 65)
print('  RAMANUJAN BREAKTHROUGH GENERATOR -- STATUS REPORT')
print('=' * 65)
print(f"  Cycle: {s['cycle']}  |  T: {s['temperature']:.3f}  |  Stale: {stale}")
print(f"  SDI: {s.get('structural_diversity_index', '?')}  |  Traps in top-20: {s.get('fitness_traps_in_top20', '?')}")
print(f"  State saved: {s['timestamp'][:19]}")
print(f"  Total log entries: {len(entries)}  |  Unique CFs: {len(best)}")
print()

for cat, label in [('pi_family', 'PI FAMILY (b=3n+1)'),
                    ('algebraic', 'ALGEBRAIC IRRATIONALS'),
                    ('transcendental_known', 'TRANSCENDENTAL (KNOWN)'),
                    ('novel', 'POTENTIALLY NOVEL')]:
    items = families[cat]
    if not items:
        continue
    print(f'  --- {label} ({len(items)}) ---')
    for d in items[:8]:
        vd = d.get('verified_digits', 0) or 0
        m = d.get('match', '?')
        a_s = str(d['a'])
        b_s = str(d['b'])
        print(f'    {m:22s}  a={a_s:22s} b={b_s:10s}  {vd:.0f}d')
    if len(items) > 8:
        print(f'    ... and {len(items) - 8} more')
    print()

# Assets
assets = os.listdir('discoveries/assets') if os.path.exists('discoveries/assets') else []
print(f'  Convergence maps: {len(assets)} PNGs in discoveries/assets/')

# New modules
for mod in ['deep_space.py', 'parallel_engine.py']:
    if os.path.exists(mod):
        sz = os.path.getsize(mod)
        print(f'  Module: {mod} ({sz // 1024}KB)')

print('=' * 65)
