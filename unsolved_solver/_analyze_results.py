"""Analyze solver results for v3 paper."""
import json

with open('results/unsolved_solver_results.json') as f:
    r = json.load(f)

gs = r.get('global_stats', {})
print('=== GLOBAL STATS ===')
for k, v in gs.items():
    print(f'  {k}: {v}')
print()

# Domain breakdown
for domain, report in r.get('domain_reports', {}).items():
    print(f'=== {domain.upper()} ===')
    for k, v in report.items():
        if k == 'proof_sketches':
            print(f'  proof_sketches: {len(v)}')
        else:
            print(f'  {k}: {v}')
    print()

# Count by status
bb = r.get('blackboard_state', {})
print('=== BLACKBOARD STATS ===')
total_entries = 0
status_counts = {}
cat_counts = {}
for domain, entries in bb.items():
    if isinstance(entries, list):
        total_entries += len(entries)
        for e in entries:
            s = e.get('status', 'unknown')
            status_counts[s] = status_counts.get(s, 0) + 1
            c = e.get('category', 'unknown')
            cat_counts[c] = cat_counts.get(c, 0) + 1

print(f'  Total entries: {total_entries}')
print(f'  By status: {status_counts}')
print(f'  By category: {cat_counts}')
print()

# Top validated
top = r.get('top_discoveries', [])
print(f'=== TOP DISCOVERIES ({len(top)}) ===')
for d in top[:10]:
    c = d.get('content', {})
    desc = c.get('description', c.get('type', c.get('name', '?')))
    print(f'  [{d.get("domain")}] {d.get("category")} '
          f'(conf={d.get("confidence", 0):.2f}, status={d.get("status", "?")}): '
          f'{str(desc)[:70]}')

# SAT verification
sat = r.get('sat_verification', {})
print(f'\n=== SAT VERIFICATION ===')
for k, v in sat.items():
    if isinstance(v, dict):
        print(f'  {k}: verified={v.get("verified")}, total={v.get("total")}, all={v.get("all_verified")}')
    else:
        print(f'  {k}: {v}')
