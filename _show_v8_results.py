"""Display V8 live run results."""
import json

d = json.load(open("axiom_graph.json", encoding="utf-8"))
nodes = d["nodes"]
edges = d["edges"]
alive = [n for n in nodes if n["status"] == "alive"]
falsified = [n for n in nodes if n["status"] != "alive"]
domains = sorted(set(n["domain"] for n in nodes))

print(f"{'='*70}")
print(f"  V8 BREAKTHROUGH ENGINE — LIVE RUN RESULTS")
print(f"{'='*70}")
print(f"\n  Axiom Graph: {len(nodes)} nodes, {len(edges)} edges")
print(f"  Alive: {len(alive)}  |  Falsified: {len(falsified)}")
print(f"  Domains: {', '.join(domains)}")

def b_score(n):
    s = n.get("scores", {})
    return s.get("N", 0) * s.get("F", 0) * s.get("E", 0) * s.get("C", 0)

# Sort by B-score
scored = [(b_score(n), n) for n in alive]
scored.sort(key=lambda x: -x[0])

print(f"\n{'─'*70}")
print(f"  TOP 10 HYPOTHESES BY B-SCORE")
print(f"{'─'*70}")
for i, (b, n) in enumerate(scored[:10], 1):
    tier = n.get("tier", "?")
    symbol = {"BREAKTHROUGH_CANDIDATE": "★", "CONDITIONAL_BREAKTHROUGH": "★?",
              "THEORY_PROPOSAL": "◆", "RESEARCH_DIRECTION": "○"}.get(tier, "?")
    s = n.get("scores", {})
    print(f"\n  {i}. {symbol} B={b:.4f}  [{n['domain']}]  {tier}")
    print(f"     N={s.get('N',0):.2f}  F={s.get('F',0):.2f}  "
          f"E={s.get('E',0):.2f}  C={s.get('C',0):.2f}")
    claim = n["text"][:200]
    print(f"     {claim}...")

# Breakthrough count
bt = [n for n in alive if n.get("tier", "").startswith("BREAKTHROUGH") or n.get("tier", "").startswith("CONDITIONAL")]
print(f"\n{'─'*70}")
print(f"  BREAKTHROUGH SUMMARY: {len(bt)} breakthrough-tier hypotheses")
print(f"{'─'*70}")
for n in bt:
    b = b_score(n)
    print(f"  {n.get('tier','?')}: B={b:.4f} [{n['domain']}]")
    print(f"    {n['text'][:140]}...")

# Edge analysis
edge_types = {}
for e in edges:
    t = e.get("type", "?")
    edge_types[t] = edge_types.get(t, 0) + 1
print(f"\n  Edge types: {edge_types}")

# Falsified
print(f"\n{'─'*70}")
print(f"  KILLED HYPOTHESES ({len(falsified)})")
print(f"{'─'*70}")
for n in falsified:
    print(f"  💀 [{n['domain']}] {n['text'][:120]}...")
    if n.get("falsification_evidence"):
        print(f"     Reason: {n['falsification_evidence'][:120]}...")
