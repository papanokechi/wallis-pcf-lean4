import json
from pathlib import Path

sf = Path('ramanujan_state.json')
if sf.exists():
    s = json.loads(sf.read_text())
    print('=== State ===')
    print('Cycle:', s['cycle'], '| T:', s['temperature'], '| Discoveries:', s['discoveries'])
    print('Timestamp:', s['timestamp'])
else:
    print('No state file found.')

lf = Path('ramanujan_discoveries.jsonl')
if lf.exists():
    lines = [l for l in lf.read_text().strip().split('\n') if l.strip()]
    print('\n=== Discovery Log:', len(lines), 'entries ===')
    seen = {}
    for l in lines:
        d = json.loads(l)
        key = (tuple(d['a']), tuple(d['b']))
        seen[key] = d
    print('Unique CFs:', len(seen))
    for v in list(seen.values())[-20:]:
        t = v.get('type', '?')
        print('  [%s] a=%s  b=%s  ->  %s  (res=%s)' % (t, v['a'], v['b'], v['match'], v.get('residual', '?')))
else:
    print('No discovery log found.')
