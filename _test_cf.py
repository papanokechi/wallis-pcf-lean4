from ramanujan_agent.generator import ConjectureGenerator
g = ConjectureGenerator(prec=60, seed=42)
g.set_generation(1)
cfs = g.generate_continued_fractions(budget=60)
novel = [c for c in cfs if c.metadata.get('is_novel')]
known = [c for c in cfs if c.metadata.get('is_known_transform')]
print(f"Total CFs: {len(cfs)}, Known: {len(known)}, Novel candidates: {len(novel)}")
for c in novel[:8]:
    ce = c.metadata.get("convergence_error", "?")
    print(f"  {c.expression}  val={c.value:.12f}  conv_err={ce}")

# Test nonpoly CFs too
print()
npcfs = g.generate_nonpoly_cfs(budget=40)
novel_np = [c for c in npcfs if c.metadata.get('is_novel')]
known_np = [c for c in npcfs if c.metadata.get('is_known_transform')]
print(f"Nonpoly CFs: {len(npcfs)}, Known: {len(known_np)}, Novel: {len(novel_np)}")
for c in novel_np[:8]:
    ce = c.metadata.get("convergence_error", "?")
    print(f"  {c.expression}  val={c.value:.12f}  conv_err={ce}")
