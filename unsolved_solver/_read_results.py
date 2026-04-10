"""Read E-S extension results."""
import json

with open('results/erdos_straus_extension.json') as f:
    data = json.load(f)

for target_str, r in data.items():
    cov = r["coverage"]
    ms = r["method_stats"]
    print(f"=== n <= {target_str} ===")
    print(f"  Coverage: {cov['coverage_pct']:.6f}%")
    print(f"  Total: {cov['final_covered']}/{cov['total']}")
    print(f"  Unsolved: {cov['final_unsolved']}")
    print(f"  Time: {r['total_time_seconds']}s")
    print(f"  Families: {r['family_count']}")
    print(f"  Compression: {r['compression_ratio']}x")
    print(f"  Methods:")
    for m, c in sorted(ms.items(), key=lambda x: -x[1]):
        print(f"    {m}: {c} ({c/cov['total']*100:.2f}%)")
    print()
