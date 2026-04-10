from functools import lru_cache

@lru_cache(maxsize=None)
def partition(n):
    if n < 0: return 0
    if n == 0: return 1
    s = 0
    for j in range(1, n + 1):
        g1 = j * (3 * j - 1) // 2
        g2 = j * (3 * j + 1) // 2
        sign = (-1) ** (j + 1)
        if g1 > n and g2 > n: break
        if g1 <= n: s += sign * partition(n - g1)
        if g2 <= n: s += sign * partition(n - g2)
    return s

A002865 = [1,0,1,1,2,2,4,4,7,8,12,14,21,24,34,41,55,66,88,105,137,163,210,
           248,315,373,464,549,680,800,983,1157,1407,1654,2000,2344,2816]

print("p(n) for n=0..9:", [partition(i) for i in range(10)])
print()

# Test 1: a(n) = p(n) - p(n-1)
print("Test a(n) = p(n) - p(n-1):")
match1 = 0
for n in range(len(A002865)):
    computed = partition(n) - partition(n - 1)
    ok = (computed == A002865[n])
    if ok:
        match1 += 1
    if n < 8:
        tag = "OK" if ok else "FAIL"
        print(f"  n={n}: p({n})-p({n-1}) = {partition(n)}-{partition(n-1)} = {computed}, expected {A002865[n]} [{tag}]")
print(f"  => {match1}/{len(A002865)} match\n")

# Test 2: a(n) = p(n-2)
print("Test a(n) = p(n-2):")
match2 = 0
for n in range(len(A002865)):
    computed = partition(n - 2)
    ok = (computed == A002865[n])
    if ok:
        match2 += 1
    if n < 8:
        tag = "OK" if ok else "FAIL"
        print(f"  n={n}: p({n-2}) = {computed}, expected {A002865[n]} [{tag}]")
print(f"  => {match2}/{len(A002865)} match\n")

# The combinatorial identity: partitions of n with no 1s = p(n) - p(n-1)
# This is because removing a 1 from any partition of n containing a 1 gives
# a partition of n-1, and this is a bijection.
print("CONCLUSION:")
if match1 == len(A002865):
    print("  a(n) = p(n) - p(n-1) is CORRECT (standard combinatorial identity)")
if match2 == len(A002865):
    print("  a(n) = p(n-2) is CORRECT")
if match1 < len(A002865) and match2 < len(A002865):
    print("  NEITHER identity holds for all terms — check data!")
