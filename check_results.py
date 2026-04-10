import json
d = json.load(open('results/ramanujan_results.json', 'r', encoding='utf-8'))
s = d['global_stats']
print('Total:', s['total'])
print('By status:', s['by_status'])
print('By novelty:', s['by_novelty'])
print('Novel_unproven:', len(d.get('novel_unproven', [])))
print()
for x in d['top_discoveries'][:15]:
    fam = x['family']
    expr = x['expression'][:70]
    status = x['status']
    lit = x.get('metadata', {}).get('literature_match', '')
    known = x.get('metadata', {}).get('is_known_transform', '')
    print(f"  [{fam}] {expr}  status={status}  lit={lit}  known_tf={known}")
