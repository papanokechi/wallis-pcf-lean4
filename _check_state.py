import json
from collections import Counter

# Check persisted state
try:
    s = json.load(open('results/ramanujan_state.json', 'r', encoding='utf-8'))
    discs = s.get('discoveries', {})
    statuses = Counter(d.get('status', '?') for d in discs.values())
    print(f'Persisted state ({len(discs)} discoveries):')
    print('By status:', dict(statuses))
    novel = [d for d in discs.values() if d.get('status') == 'novel_unproven']
    print(f'Novel unproven: {len(novel)}')
    for n in novel[:10]:
        fam = n.get('family', '?')
        expr = n.get('expression', '?')[:70]
        conf = n.get('confidence', 0)
        meta = n.get('metadata', {})
        is_novel = meta.get('is_novel')
        conv = meta.get('convergence_error', '?')
        print(f'  [{fam}] {expr}  conf={conf:.3f}  is_novel={is_novel}  conv_err={conv}')
except Exception as e:
    print(f'State error: {e}')

# Check results JSON
try:
    d = json.load(open('results/ramanujan_results.json', 'r', encoding='utf-8'))
    gs = d.get('global_stats', {})
    print(f'\nResults JSON - total: {gs.get("total")}')
    print(f'Novel unproven in results: {len(d.get("novel_unproven", []))}')
except Exception as e:
    print(f'Results error: {e}')
