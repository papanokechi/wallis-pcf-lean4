import json
with open("ramanujan_discoveries.jsonl") as f:
    lines = f.readlines()
print(f"Total: {len(lines)}")
print("\nNew entries (65+):")
for i, line in enumerate(lines[65:], 66):
    d = json.loads(line)
    vd = d.get("verified_digits", "?")
    m = d.get("match", "?")
    a = d.get("a", "?")
    b = d.get("b", "?")
    tp = d.get("type", "?")
    print(f"  #{i}: {vd}d | {m:30s} | a={str(a):20s} b={str(b):12s} | {tp}")
