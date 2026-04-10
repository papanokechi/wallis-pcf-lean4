"""Combined status checker for all Ramanujan search processes."""
import json
from pathlib import Path
from collections import Counter

SEP = '=' * 70
DASH = '-' * 50

def check_log(logfile, label):
    lf = Path(logfile)
    if not lf.exists():
        print("  %s: no log file yet" % label)
        return []
    lines = [l for l in lf.read_text().strip().split('\n') if l.strip()]
    data = [json.loads(l) for l in lines]
    seen = {}
    for d in data:
        if 'a' not in d or 'b' not in d:
            continue
        key = (tuple(d['a']), tuple(d['b']))
        seen[key] = d
    types = Counter(d.get('type', '?') for d in data)
    print("  %s: %d entries, %d unique CFs" % (label, len(data), len(seen)))
    print("    Types: %s" % dict(types))

    # Show non-trivial matches
    interesting = []
    for d in seen.values():
        m = d['match']
        try:
            int(m)
            continue
        except ValueError:
            pass
        if '**(' in m and m.count('/') > 3:
            continue
        if m.count('*') > 4:
            continue
        interesting.append(d)

    # Group by target constant
    targets = Counter()
    for d in interesting:
        m = d['match']
        if '*' in m:
            targets[m.split('*', 1)[-1]] += 1
        else:
            targets[m] += 1

    if targets:
        print("    Targets: %s" % dict(targets.most_common(10)))

    # Show newest 5
    recent = sorted(data, key=lambda x: x.get('timestamp', ''))[-5:]
    if recent:
        print("    Latest:")
        for d in recent:
            vd = d.get('verified_digits', '?')
            print("      a=%-22s b=%-12s -> %-25s (vd=%s)" % (
                str(d['a']), str(d['b']), d['match'][:25], vd))

    return data


def main():
    print(SEP)
    print("  COMBINED STATUS REPORT")
    print(SEP)

    # Main search state
    sf = Path('ramanujan_state.json')
    if sf.exists():
        s = json.loads(sf.read_text())
        print("\n  Main Search State:")
        print("    Cycle: %d | T: %.3f | Discoveries: %d" % (
            s['cycle'], s['temperature'], s['discoveries']))
        print("    Timestamp: %s" % s['timestamp'])
        scores = s.get('best_scores', [])
        if scores:
            print("    Recent top scores: %s" % [round(x, 1) for x in scores[-5:]])
        ldc = s.get('last_discovery_cycle', 0)
        stale = s['cycle'] - ldc
        print("    Stale cycles: %d (last discovery at cycle %d)" % (stale, ldc))
    else:
        print("\n  No main search state file.")

    # All logs
    print("\n" + DASH)
    all_data = []
    for logfile, label in [
        ('ramanujan_discoveries.jsonl', 'Main (evolve)'),
        ('zeta3_discoveries.jsonl', 'Zeta(3) CMF'),
        ('catalan_discoveries.jsonl', 'Catalan CMF'),
    ]:
        data = check_log(logfile, label)
        all_data.extend(data)

    # Cross-log summary
    print("\n" + DASH)
    if all_data:
        all_unique = {}
        for d in all_data:
            if 'a' not in d or 'b' not in d:
                continue
            key = (tuple(d['a']), tuple(d['b']))
            if key not in all_unique or d.get('verified_digits', 0) > all_unique[key].get('verified_digits', 0):
                all_unique[key] = d

        # Best by verified digits
        verified = [(k, v) for k, v in all_unique.items()
                    if isinstance(v.get('verified_digits'), (int, float)) and v['verified_digits'] > 50]
        verified.sort(key=lambda x: x[1]['verified_digits'], reverse=True)

        print("  Top verified CFs (>50 digits):")
        for (a, b), d in verified[:10]:
            print("    a=%-22s b=%-12s -> %-25s (%dd verified)" % (
                str(list(a)), str(list(b)), d['match'][:25], int(d['verified_digits'])))

        # Highlight any non-pi, non-phi, non-S^ discoveries
        novel = [d for d in all_unique.values()
                 if not any(x in d['match'] for x in ['4/pi', 'S^', 'phi', '1', '2', '3', '4', '5'])]
        if novel:
            print("\n  NOVEL (non-pi/phi) discoveries:")
            for d in novel:
                print("    a=%-22s b=%-12s -> %s" % (str(d['a']), str(d['b']), d['match']))
    else:
        print("  No discoveries across any log.")

    print("\n" + SEP)


if __name__ == '__main__':
    main()
