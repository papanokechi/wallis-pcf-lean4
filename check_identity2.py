from functools import lru_cache
import sys

sys.setrecursionlimit(10000)

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

# First verify partition function against known values (A000041)
known_p = [1, 1, 2, 3, 5, 7, 11, 15, 22, 30, 42, 56, 77, 101, 135, 176, 231,
           297, 385, 490, 627, 792, 1002, 1255, 1575, 1958, 2436, 3010, 3718,
           4565, 5604, 6842, 8349, 10143, 12310, 14883, 17977]
print("Verifying partition function p(n):")
p_ok = True
for i, expected in enumerate(known_p):
    computed = partition(i)
    if computed != expected:
        print(f"  FAIL: p({i}) = {computed}, expected {expected}")
        p_ok = False
if p_ok:
    print(f"  All {len(known_p)} values match A000041 ✓")
else:
    print("  PARTITION FUNCTION IS WRONG!")
print()

# A002865: Number of partitions of n that do not contain 1 as a part
A002865 = [1,0,1,1,2,2,4,4,7,8,12,14,21,24,34,41,55,66,88,105,137,163,210,
           248,315,373,464,549,680,800,983,1157,1407,1654,2000,2344,2816]

print("Checking a(n) = p(n) - p(n-1) for ALL terms:")
all_ok = True
for n in range(len(A002865)):
    computed = partition(n) - partition(n - 1)
    expected = A002865[n]
    if computed != expected:
        print(f"  n={n}: p({n})-p({n-1}) = {partition(n)}-{partition(n-1)} = {computed} != {expected}")
        all_ok = False
if all_ok:
    print(f"  All {len(A002865)} terms match ✓")
else:
    print(f"  Some mismatches found!")
print()

# Let me also verify by direct enumeration for small n
print("Direct enumeration check (partitions of n with no 1s):")
def partitions_no_ones(n, min_part=2):
    """Count partitions of n where all parts >= 2."""
    if n == 0: return 1
    if n < 0: return 0
    count = 0
    for p in range(min_part, n + 1):
        count += partitions_no_ones(n - p, p)
    return count

for n in range(15):
    direct = partitions_no_ones(n)
    formula = partition(n) - partition(n - 1)
    oeis = A002865[n] if n < len(A002865) else "?"
    match_d = "✓" if direct == oeis else "✗"
    match_f = "✓" if formula == oeis else "✗"
    print(f"  n={n:2d}: direct={direct:4d}, p(n)-p(n-1)={formula:4d}, OEIS={oeis} [direct:{match_d}, formula:{match_f}]")
