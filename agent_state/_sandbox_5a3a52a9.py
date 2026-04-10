
import mpmath as mp
import json
mp.mp.dps = 100

k = 5
N = 2000

# f_k(n) via recurrence: n*f_k(n) = sum_{j=1}^n k*sigma_1(j)*f_k(n-j)
f = [mp.mpf(0)] * (N + 1)
f[0] = mp.mpf(1)

sigma1 = [mp.mpf(0)] * (N + 1)
for j in range(1, N + 1):
    s = mp.mpf(0)
    d = 1
    while d * d <= j:
        if j % d == 0:
            s += d
            if d != j // d:
                s += j // d
        d += 1
    sigma1[j] = s

for n in range(1, N + 1):
    s = mp.mpf(0)
    for j in range(1, n + 1):
        s += k * sigma1[j] * f[n - j]
    f[n] = s / n

# Extract last 20 ratios
ratios = []
for m in range(max(1, N-20), N + 1):
    if f[m-1] != 0:
        ratios.append({"m": m, "ratio": str(mp.nstr(f[m]/f[m-1], 40))})

print(json.dumps({"k": k, "N": N, "n_ratios": N, "tail_ratios": ratios}))
