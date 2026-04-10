"""Quick integration tests for deep_space.py"""
import random

rng = random.Random(42)

# Test 1: Symmetry-Invariant Search
from deep_space import generate_symmetry_constrained, classify_symmetry
for ctype in ['factored_b', 'shared_root', 'gcd_symmetric', 'palindromic_b']:
    a, b, name = generate_symmetry_constrained(rng, constraint=ctype)
    sym = classify_symmetry(a, b)
    print(f'[{ctype:15s}] a={a}, b={b} -> classified as {sym}')

print()

# Test 2: Elegance scoring
from deep_space import elegance_score, elegance_tier, description_length, compute_elegance_for_discovery
dl = description_length([0, 3, -2], [1, 3])
es = elegance_score(130.5, [0, 3, -2], [1, 3])
tier = elegance_tier(es)
print(f'Elegance: dl={dl}, score={es}, tier={tier}')

rec = {'a': [0, 3, -2], 'b': [1, 3], 'verified_digits': 130.5, 'match': '4/pi'}
eleg = compute_elegance_for_discovery(rec)
print(f'Discovery elegance: {eleg}')

print()

# Test 3: Symmetry correlation map (empty is fine)
from deep_space import symmetry_correlation_map
corr = symmetry_correlation_map()
print(f'Symmetry map entries: {len(corr)}')

# Test 4: on_deep_space_discovery enrichment
from deep_space import on_deep_space_discovery
rec2 = {'a': [0, 3, -2], 'b': [1, 3], 'verified_digits': 130.5, 'match': '4/pi'}
enriched = on_deep_space_discovery(rec2)
print(f'Enriched: elegance_score={enriched["elegance_score"]}, '
      f'tier={enriched["elegance_tier"]}, sym={enriched["symmetry_type"]}')

# Test 5: Symmetry population
from deep_space import get_symmetry_population
pop = get_symmetry_population(5, rng=rng)
print(f'Symmetry pop: {len(pop)} members')
for p in pop[:3]:
    print(f'  a={p["a"]}, b={p["b"]}, hint={p["hint_target"]}')

# Test 6: Composite targets (empty without data but should not crash)
from deep_space import build_composite_targets, load_composite_targets
targets = build_composite_targets()
cached = load_composite_targets()
print(f'Composite targets: generated={len(targets)}, cached={len(cached)}')

# Test 7: Manifold (empty with <30 entries but should not crash)
from deep_space import compute_manifold, load_ridge_hints
ridges = compute_manifold(min_entries=5)
hints = load_ridge_hints()
print(f'Ridges: {len(ridges)}, hints: {len(hints)}')

# Test 8: Elegance leaderboard
from deep_space import elegance_leaderboard
board = elegance_leaderboard()
if board:
    top = board[0]
    print(f'Top elegant: {top["match"]} score={top["elegance_score"]} tier={top["elegance_tier"]}')
else:
    print('No elegance leaderboard (empty log)')

print()
print('ALL DEEP SPACE TESTS PASSED')
