import json

lines = open('ramanujan_discoveries.jsonl').readlines()
print(f'Total discoveries: {len(lines)}')
for i, line in enumerate(lines):
    d = json.loads(line)
    cyc = d.get('cycle', '?')
    match = d.get('match', '?')
    a = d.get('a', '?')
    b = d.get('b', '?')
    vd = d.get('verified_digits', '?')
    tp = d.get('type', '?')
    print(f'  [{i+1:2d}] cycle={cyc} type={tp} match={match} a={a} b={b} vd={vd}d')
