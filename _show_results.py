import json

d = json.load(open('results/ramanujan_results.json', 'r', encoding='utf-8'))
gs = d.get('global_stats', {})
print(f"Total: {gs.get('total')}")
print(f"By status: {gs.get('by_status')}")
print(f"By novelty: {gs.get('by_novelty')}")
print(f"Time: {d.get('total_time', 0):.1f}s")

print(f"\n=== Novel Unproven ({len(d.get('novel_unproven', []))}) ===")
for n in d.get('novel_unproven', []):
    meta = n.get('metadata', {})
    print(f"  [{n['family']}] {n['expression'][:80]}")
    print(f"    status={n['status']}  conf={n.get('confidence',0):.3f}  err={n.get('error','?')}")
    print(f"    is_novel={meta.get('is_novel')}  conv={meta.get('convergence_error','?')}  cf_type={meta.get('cf_type','?')}")
    print()

print(f"\n=== Verified Known ({len(d.get('verified_known', []))}) ===")
for n in d.get('verified_known', [])[:5]:
    print(f"  [{n['family']}] {n['expression'][:70]}  lit={n.get('metadata',{}).get('literature_match','?')[:40]}")

print(f"\n=== Top Discoveries ===")
for n in d.get('top_discoveries', [])[:10]:
    print(f"  [{n['status']}] [{n['family']}] {n['expression'][:60]}  conf={n.get('confidence',0):.3f}")
