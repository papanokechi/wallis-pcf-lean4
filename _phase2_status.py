import json

s = json.load(open('ramanujan_state.json'))
stale = s['cycle'] - s['last_discovery_cycle']
print(f"Cycle: {s['cycle']}  T: {s['temperature']}  LDC: {s['last_discovery_cycle']}  Stale: {stale}")

elites = s['elite_population']
degs = set()
for e in elites:
    degs.add((len(e['a']), len(e['b'])))

print(f"Elite structs: {len(degs)} unique degree combos from {len(elites)} elites")
for i, e in enumerate(elites):
    print(f"  [{i}] a={e['a']}  b={e['b']}  score={e.get('score','?')}  hit={e.get('hit','?')}")

# Discovery log summary
lines = open('ramanujan_discoveries.jsonl').readlines()
print(f"\nDiscovery log: {len(lines)} entries")
seen_matches = {}
for line in lines:
    d = json.loads(line)
    m = d.get('match', '?')
    seen_matches[m] = seen_matches.get(m, 0) + 1
for m, c in sorted(seen_matches.items(), key=lambda x: -x[1]):
    print(f"  {m}: {c}x")
