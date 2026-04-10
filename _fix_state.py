"""Fix the monoculture in ramanujan_state.json before resuming."""
import json

with open('ramanujan_state.json', 'r') as f:
    state = json.load(f)

print(f"Before: {len(state['elite_population'])} elites")
for e in state['elite_population']:
    print(f"  a={e['a']} b={e['b']} score={e['score']} hit={e.get('hit')}")

# Force reheat conditions
state['temperature'] = 2.5  # T2-level forced heat
state['last_discovery_cycle'] = state['cycle']  # Reset stale counter

# Diversify elite - keep only 1 sqrt2+1, inject structural variety
diverse_elites = [
    state['elite_population'][0],  # Keep one sqrt2+1 as anchor
    {'a': [0, 0, -1], 'b': [1, 3], 'score': 0.0, 'hit': None},        # S-family template (quadratic a)
    {'a': [0, 0, 0, 1], 'b': [1, 5], 'score': 0.0, 'hit': None},      # cubic a, linear b
    {'a': [1, 0, -2], 'b': [1, 1], 'score': 0.0, 'hit': None},        # quadratic a, linear b
    {'a': [0, 1, -1], 'b': [2, 1, 1], 'score': 0.0, 'hit': None},     # deg2 a, deg2 b
    {'a': [0, -1, 0, 0, 1], 'b': [1, 3], 'score': 0.0, 'hit': None},  # quartic a, linear b
    {'a': [1, 2], 'b': [1, 0, 1], 'score': 0.0, 'hit': None},         # linear a, quadratic b
    {'a': [3, 0, -1], 'b': [0, 1, 1], 'score': 0.0, 'hit': None},     # quadratic both
    {'a': [-1, 0, 1], 'b': [3, 2], 'score': 0.0, 'hit': None},        # quadratic a, linear b variant
    {'a': [0, 0, 1, -1], 'b': [1, 1, 0, 1], 'score': 0.0, 'hit': None},  # cubic both
]

state['elite_population'] = diverse_elites
state['structural_diversity_index'] = len(set(
    (len(e['a'])-1, len(e['b'])-1) for e in diverse_elites
))
state['degree_combos'] = list(set(
    (len(e['a'])-1, len(e['b'])-1) for e in diverse_elites
))

print(f"\nAfter: {len(state['elite_population'])} elites, SDI={state['structural_diversity_index']}")
print(f"Degree combos: {state['degree_combos']}")
print(f"Temperature: {state['temperature']}")

for e in state['elite_population']:
    print(f"  a={e['a']} b={e['b']}")

with open('ramanujan_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print("\nState file updated successfully.")
