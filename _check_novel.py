import json
d = json.load(open('results/ramanujan_results.json', 'r', encoding='utf-8'))
from collections import Counter

# All discoveries from results_log
all_disc = d.get('results_log', [])
fam = Counter(x.get('family','?') for x in all_disc)
print('By family:', dict(fam))

status = Counter(x.get('status','?') for x in all_disc)
print('By status:', dict(status))

# Show ALL CFs
cfs = [x for x in all_disc if x.get('family') == 'continued_fraction']
print(f'\nTotal CFs: {len(cfs)}')
for c in cfs[:30]:
    m = c.get('metadata', {})
    print(f'  [{c.get("status","?")}] {c.get("expression","?")[:65]}  novel={m.get("is_novel")}  known_tf={m.get("is_known_transform")}  conv={m.get("convergence_error","?")}')

# Show any novel candidates
print('\n--- All entries with is_novel=True ---')
novel = [x for x in all_disc if x.get('metadata', {}).get('is_novel')]
print(f'Count: {len(novel)}')
for c in novel[:20]:
    print(f'  [{c.get("status","?")}] [{c.get("family","?")}] {c.get("expression","?")[:65]}  conf={c.get("confidence","?")}')

# Also check top_discoveries
print('\n--- top_discoveries ---')
for td in d.get('top_discoveries', [])[:10]:
    print(f'  [{td.get("status","?")}] [{td.get("family","?")}] {td.get("expression","?")[:65]}')

# Check novel_unproven list
print(f'\nnovel_unproven count: {len(d.get("novel_unproven",[]))}')
print(f'novel_proven count: {len(d.get("novel_proven",[]))}')
print(f'verified_known count: {len(d.get("verified_known",[]))}')
print(f'breakthroughs count: {len(d.get("breakthroughs",[]))}')

# Check for discoveries from strategies containing 'cf' 
print('\n--- CF-type discoveries in validated ---')
for v in d.get('validated', [])[:20]:
    if 'cf' in str(v.get('params',{}).get('strategy','')).lower() or \
       v.get('family') == 'continued_fraction':
        m = v.get('metadata', {})
        print(f'  [{v.get("status","?")}] {v.get("expression","?")[:65]}  novel={m.get("is_novel")}  conv={m.get("convergence_error","?")}')