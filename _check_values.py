"""Show the actual values and check if they are really non-trivial."""
import json, mpmath

d = json.load(open('results/ramanujan_results.json', 'r', encoding='utf-8'))

novel = d.get('novel_unproven', [])
print(f"Novel unproven: {len(novel)}")

for i, n in enumerate(novel):
    expr = n['expression']
    params = n.get('params', {})
    an = params.get('an')
    bn = params.get('bn')
    val = n.get('value', 0)
    
    # Check if this is actually an algebraic number via fixed-point equation
    # For GCF with polynomial a(n), b(n), the fixed-point equation for
    # constant-coefficient CFs (degree 0 in a, degree 1 in b) is well-known.
    # But for general polynomial CFs, values can be transcendental.
    
    print(f"\n{i+1}. {expr}")
    print(f"   value = {val}")
    print(f"   an={an}, bn={bn}")
    
    # Check degree of a(n) and b(n) polynomials
    if an is not None:
        a_deg = len(an) - 1
        b_deg = len(bn) - 1 if bn else 0
        print(f"   a(n) deg={a_deg}, b(n) deg={b_deg}")
        # Higher degree polynomials give transcendental values typically
        if a_deg >= 1 or b_deg >= 1:
            print(f"   -> Non-constant polynomial CF -> potentially transcendental")
        else:
            print(f"   -> Constant-coefficient CF -> algebraic (fixed-point)")
