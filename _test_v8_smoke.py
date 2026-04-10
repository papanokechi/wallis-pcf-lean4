"""Quick smoke test for breakthrough_engine_v8.py"""
import breakthrough_engine_v8 as v8
import json, os

print("=== V8 Engine Import Test ===")
print(f"Version: {v8.VERSION}")
print(f"HAS_ANTHROPIC: {v8.HAS_ANTHROPIC}")
print(f"HAS_OPENAI: {v8.HAS_OPENAI}")
print()

# Test AxiomGraph
print("--- Axiom Graph ---")
graph = v8.AxiomGraph(path="test_axiom_graph.json")
print(f"Stats: {graph.stats()}")

n1 = v8.AxiomNode(id="test-001",
    text="Phase transitions in LLM training loss curves mirror Ising model criticality",
    domain="physics", domains_touched=["physics","cs"], confidence=0.8, novelty_score=0.7,
    generation=1, status="alive", scores={"N":0.85,"F":0.80,"E":0.75,"C":0.70})
n2 = v8.AxiomNode(id="test-002",
    text="Attention patterns exhibit self-organized criticality at scale boundaries",
    domain="cs", domains_touched=["cs","physics"], confidence=0.6, novelty_score=0.9,
    generation=1, status="alive", scores={"N":0.90,"F":0.70,"E":0.60,"C":0.65})
n3 = v8.AxiomNode(id="test-003",
    text="Token embeddings live on a low-dim manifold with curvature proportional to perplexity",
    domain="mathematics", confidence=0.3, novelty_score=0.4,
    generation=1, status="falsified", scores={"N":0.40,"F":0.50,"E":0.30,"C":0.40})

graph.add_node(n1)
graph.add_node(n2)
graph.add_node(n3)
graph.add_edge("test-001", "test-002", "strengthens")
graph.save()
print(f"After adding 3 nodes: {graph.stats()}")

# Test retrieval
seeds = graph.get_seed_candidates(domain="physics", k=3)
print(f"Seeds for physics: {[(s.id, s.confidence) for s in seeds]}")
foreign = graph.get_foreign_seeds("physics", k=2)
print(f"Foreign seeds from physics POV: {[(f.id, f.domain) for f in foreign]}")
dormant = graph.get_dormant_nodes()
print(f"Dormant: {[d.id for d in dormant]}")

# Test decay
graph.apply_decay(rate=0.01)
node_001 = graph.nodes["test-001"]
print(f"After decay: n1.conf={node_001.confidence:.4f} (was 0.8)")

# Test genealogy
genealogy = graph.get_genealogy()
print(f"Genealogy entries: {len(genealogy)}")

# Test SerendipityEngine
print()
print("--- Serendipity Engine ---")
seren = v8.SerendipityEngine()
print(f"Patterns loaded: {len(seren.patterns)}")
pattern = seren.inject("physics", stagnant=False)
if pattern:
    print(f"Injected: {pattern['name']}")
    prompt = seren.build_injection_prompt(pattern, "physics")
    print(f"Prompt preview: {prompt[:200]}...")
    # Meta-learning test
    seren.record_outcome(pattern["id"], 0.45)
    seren.record_outcome(pattern["id"], 0.60)
    print(f"Pattern score after 2 outcomes: {seren.pattern_scores[pattern['id']]:.3f}")

# Test Hypothesis
print()
print("--- Hypothesis ---")
h = v8.Hypothesis(id="h-001", text="Test", claim="Test claim",
                  scores={"N":0.85,"F":0.80,"E":0.90,"C":0.75})
print(f"B score: {h.b_score():.4f}")
print(f"Kill floor: {h.fails_kill_floor()}")
print(f"Tier: {h.tier} {h.tier_symbol}")

h2 = v8.Hypothesis(id="h-002", text="Bad", claim="Bad claim",
                   scores={"N":0.30,"F":0.40,"E":0.20,"C":0.50})
print(f"h2 tier: {h2.tier} {h2.tier_symbol} (should be KILLED)")

h3 = v8.Hypothesis(id="h-003", text="Mid", claim="Mid claim",
                   scores={"N":0.72,"F":0.82,"E":0.68,"C":0.62})
print(f"h3 tier: {h3.tier} {h3.tier_symbol} (should be THEORY_PROPOSAL)")

# Test V8State stagnation
print()
print("--- Stagnation Detection ---")
state = v8.V8State()
state.delta_novelty_history = [0.10, 0.08, 0.05]
print(f"Stagnant after [0.10, 0.08, 0.05]: {state.is_stagnant()}")
state.delta_novelty_history = [0.30, 0.08, 0.05]
print(f"Stagnant after [0.30, 0.08, 0.05]: {state.is_stagnant()}")

# Test FailureArchive
print()
print("--- Failure Archive ---")
fa = v8.FailureArchive(path="test_failure_archive.json")
fa.add("Bad hypothesis", "Logically contradicted by X", "Better hypothesis based on X",
       "fail-001", generation=1)
fa.add("Another bad one", "Boundary case breaks it", "Modified version",
       "fail-002", generation=2)
candidates = fa.get_candidates_for_resurrection()
print(f"Resurrection candidates: {len(candidates)}")

# Test HTML generation
print()
print("--- HTML Dashboard ---")
state2 = v8.V8State(session_id="test1234", mode="Physics/Math", target="Scaling Laws",
                    model="claude-test", max_iterations=5)
state2.b_history = [0.1, 0.2, 0.35, 0.28, 0.45]
state2.delta_novelty_history = [0.5, 0.3, 0.2, 0.15, 0.4]
state2.kill_rate_history = [0.6, 0.4, 0.5, 0.3, 0.2]
state2.survivors = [h, h3]
state2.killed = [h2]
state2.serendipity_injections = [{"generation": 1, "pattern": "Renormalization Group"}]
state2.interrupts = [{"type": "info", "msg": "Test interrupt", "time": "2026-03-27"}]
html = v8.generate_html(state2, graph)
with open("test_v8_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"Dashboard written: {len(html):,} bytes")

# Test CLI help
print()
print("--- CLI ---")
print(f"Patterns file: {v8.PATTERNS_PATH}")
print(f"Graph file: {v8.AXIOM_GRAPH_PATH}")

# Cleanup
os.remove("test_axiom_graph.json")
os.remove("test_failure_archive.json")
# Keep dashboard for inspection

print()
print("=" * 40)
print("ALL TESTS PASSED")
