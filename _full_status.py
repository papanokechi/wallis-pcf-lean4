import json, os

s = json.load(open('ramanujan_state.json'))
stale = s['cycle'] - s['last_discovery_cycle']
sdi = s.get('structural_diversity_index', '?')
combos = s.get('degree_combos', '?')
traps = s.get('fitness_traps_in_top20', '?')
print(f"Cycle: {s['cycle']}  T: {s['temperature']:.3f}  Stale: {stale}  SDI: {sdi}  Traps: {traps}")
print(f"Degree combos in top-20: {combos}")
print(f"Last discovery cycle: {s['last_discovery_cycle']}")

# Check if process is still running
import subprocess
result = subprocess.run(['powershell', '-c', 
    'Get-Process python* | Where-Object {$_.CPU -gt 50} | Select-Object Id, CPU, StartTime | Format-Table'],
    capture_output=True, text=True)
print(f"\nHigh-CPU Python processes:\n{result.stdout}")

# Parallel engine artifacts
for path in ['parallel_results', 'parallel_heatmap.json', 'parallel_state.json']:
    if os.path.exists(path):
        if os.path.isdir(path):
            files = os.listdir(path)
            print(f"parallel_results/: {len(files)} files")
        else:
            sz = os.path.getsize(path)
            print(f"{path}: {sz} bytes")

# Discovery timeline
lines = open('ramanujan_discoveries.jsonl').readlines()
print(f"\nDiscovery log: {len(lines)} entries")
# Count unique matches
from collections import Counter
matches = Counter()
for line in lines:
    d = json.loads(line)
    matches[d.get('match', '?')] += 1
unique_matches = len(matches)
print(f"Unique constant matches: {unique_matches}")
