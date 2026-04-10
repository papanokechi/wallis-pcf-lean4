"""Diagnose: trace a novel CF through the full validation pipeline."""
import os; os.environ["PYTHONUTF8"] = "1"
from ramanujan_agent.generator import ConjectureGenerator
from ramanujan_agent.validator import Validator

g = ConjectureGenerator(prec=60, seed=42)
g.set_generation(1)

# Get one novel poly CF and one novel nonpoly CF
cfs = g.generate_continued_fractions(budget=30)
npcfs = g.generate_nonpoly_cfs(budget=30)

poly_novel = [c for c in cfs if c.metadata.get('is_novel')]
np_novel = [c for c in npcfs if c.metadata.get('is_novel')]

print(f"Poly novel: {len(poly_novel)}, Nonpoly novel: {len(np_novel)}")

v = Validator(max_precision=500)

# Test poly novel CF
if poly_novel:
    cj = poly_novel[0]
    print(f"\n=== POLY CF: {cj.expression} val={cj.value:.12f} ===")
    print(f"  error={cj.error}, quality={cj.quality:.1f}")
    print(f"  metadata: is_novel={cj.metadata.get('is_novel')}, conv_err={cj.metadata.get('convergence_error')}")
    result = v.validate(cj)
    print(f"  VERDICT: {result.verdict}")
    print(f"  confidence={result.confidence:.3f}, best_precision={result.precision_achieved}")
    print(f"  is_novel={result.is_novel}, lit_match={result.literature_match}")
    for ch in result.checks:
        print(f"    check: stage={ch.get('stage','?')} prec={ch.get('precision','?')} "
              f"passed={ch.get('passed')} digits={ch.get('precision_digits','?')} "
              f"error={ch.get('error','?')}"[:120])

# Test nonpoly novel CF
if np_novel:
    cj = np_novel[0]
    print(f"\n=== NONPOLY CF: {cj.expression} val={cj.value:.12f} ===")
    print(f"  error={cj.error}, quality={cj.quality:.1f}")
    print(f"  metadata: is_novel={cj.metadata.get('is_novel')}, conv_err={cj.metadata.get('convergence_error')}")
    print(f"  params: {cj.params}")
    result = v.validate(cj)
    print(f"  VERDICT: {result.verdict}")
    print(f"  confidence={result.confidence:.3f}, best_precision={result.precision_achieved}")
    print(f"  is_novel={result.is_novel}, lit_match={result.literature_match}")
    for ch in result.checks:
        print(f"    check: stage={ch.get('stage','?')} prec={ch.get('precision','?')} "
              f"passed={ch.get('passed')} digits={ch.get('precision_digits','?')} "
              f"error={ch.get('error','?')}"[:120])
