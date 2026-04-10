"""
Find P_n^(m) closed forms for m=2,3,4 to test general pattern.

For m=1: P_n = (2n-1)!! * (n^2 + 3n + 1)
Does P_n/(2n-1)!! give a polynomial for m ≥ 2?
"""

from mpmath import mp, mpf

mp.dps = 50

def double_fact(n):
    if n <= 0: return mpf(1)
    r = mpf(1)
    for k in range(1, n+1):
        r *= (2*k - 1)
    return r

def compute_Pn(m_val, N=20):
    """Compute P_n for a_m(n) = -n(2n - (2m+1)), b(n) = 3n+1"""
    c = 2*m_val + 1  # a(n) = -n(2n - c)
    
    def a(n): return -n * (2*n - c)
    def b(n): return 3*n + 1
    
    Pm1, P0 = mpf(1), mpf(b(0))  # P_{-1}=1, P_0=b(0)=1
    Ps = [P0]
    
    Pprev2, Pprev1 = Pm1, P0
    for n in range(1, N+1):
        Pn = b(n)*Pprev1 + a(n)*Pprev2
        Ps.append(Pn)
        Pprev2, Pprev1 = Pprev1, Pn
    
    return Ps

for m in range(0, 6):
    Ps = compute_Pn(m, N=15)
    c = 2*m + 1
    print(f"\n{'='*60}")
    print(f"  m={m}, c={c}, a(n) = -n(2n-{c})")
    print(f"{'='*60}")
    
    print(f"  P_n / (2n-1)!! :")
    ratios = []
    for n in range(16):
        df = double_fact(n)
        ratio = Ps[n] / df
        ratios.append(ratio)
        print(f"    n={n:2d}: {float(ratio):.6f}")
    
    # Check if ratios form a polynomial sequence
    # First differences
    diffs1 = [ratios[n+1] - ratios[n] for n in range(len(ratios)-1)]
    diffs2 = [diffs1[n+1] - diffs1[n] for n in range(len(diffs1)-1)]
    diffs3 = [diffs2[n+1] - diffs2[n] for n in range(len(diffs2)-1)]
    
    print(f"\n  First diffs: {[float(d) for d in diffs1[:10]]}")
    print(f"  Second diffs: {[float(d) for d in diffs2[:10]]}")
    print(f"  Third diffs: {[float(d) for d in diffs3[:8]]}")
    
    # Check if second diffs are constant (quadratic polynomial)
    if all(abs(float(diffs2[i] - diffs2[0])) < 0.001 for i in range(min(8, len(diffs2)))):
        # Fit quadratic: ratio_n = a*n^2 + b*n + c
        # Using n=0,1,2:
        r0, r1, r2 = float(ratios[0]), float(ratios[1]), float(ratios[2])
        A = (r2 - 2*r1 + r0) / 2
        B = r1 - r0 - A
        C = r0
        print(f"\n  *** QUADRATIC FIT: ratio_n = {A:.1f}*n^2 + {B:.1f}*n + {C:.1f}")
        
        # Verify
        print(f"  Verification:")
        ok = True
        for n in range(10):
            pred = A*n*n + B*n + C
            actual = float(ratios[n])
            if abs(pred - actual) > 0.01:
                ok = False
            print(f"    n={n}: pred={pred:.4f}, actual={actual:.4f}, ok={abs(pred-actual)<0.01}")
        if ok:
            print(f"  *** P_n^({m}) = (2n-1)!! * ({A:.0f}*n^2 + {B:.0f}*n + {C:.0f})")
    elif all(abs(float(diffs3[i] - diffs3[0])) < 0.001 for i in range(min(6, len(diffs3)))):
        print(f"  → Cubic polynomial in n")
        # Fit cubic
        r0, r1, r2, r3 = [float(ratios[i]) for i in range(4)]
        # Use Lagrange or Newton's method
        d3 = float(diffs3[0])
        A = d3 / 6  # coefficient of n^3
        # Subtract cubic part and fit quadratic
        # Actually use direct system:
        # ratio_n = A*n^3 + B*n^2 + C*n + D
        # n=0: D = r0
        # n=1: A + B + C + D = r1
        # n=2: 8A + 4B + 2C + D = r2
        # n=3: 27A + 9B + 3C + D = r3
        D = r0
        # A + B + C = r1 - D
        # 8A + 4B + 2C = r2 - D
        # 27A + 9B + 3C = r3 - D
        s1, s2, s3 = r1-D, r2-D, r3-D
        # From differences:
        # 7A + 3B + C = s2 - s1
        # 19A + 5B + C = s3 - s2
        # 12A + 2B = (s3-s2) - (s2-s1)
        d21 = s2 - s1
        d32 = s3 - s2
        # 12A + 2B = d32 - d21
        # A + B + C = s1
        # 7A + 3B + C = d21+s1  Wait no: 7A + 3B + C = s2-s1+?
        # Let me just solve the system directly
        # A + B + C = s1
        # 8A + 4B + 2C = s2
        # 27A + 9B + 3C = s3
        # From eq1: C = s1 - A - B
        # Sub into eq2: 8A + 4B + 2(s1-A-B) = s2 → 6A + 2B = s2 - 2*s1
        # Sub into eq3: 27A + 9B + 3(s1-A-B) = s3 → 24A + 6B = s3 - 3*s1
        # From 6A + 2B = s2-2s1 → B = (s2-2s1-6A)/2
        # 24A + 3(s2-2s1-6A) = s3-3s1
        # 24A + 3s2 - 6s1 - 18A = s3 - 3s1
        # 6A = s3 - 3s1 - 3s2 + 6s1 = s3 + 3s1 - 3s2
        A = (s3 + 3*s1 - 3*s2) / 6
        B = (s2 - 2*s1 - 6*A) / 2
        C = s1 - A - B
        print(f"  *** CUBIC FIT: ratio_n = {A:.4f}*n^3 + {B:.4f}*n^2 + {C:.4f}*n + {D:.4f}")
        
        print(f"  Verification:")
        for n in range(10):
            pred = A*n**3 + B*n**2 + C*n + D
            actual = float(ratios[n])
            print(f"    n={n}: pred={pred:.6f}, actual={actual:.6f}, diff={abs(pred-actual):.2e}")
    else:
        print(f"  → Not a low-degree polynomial")
        # Check if it's a polynomial of any degree by looking at higher diffs
        for deg in range(4, 8):
            d = list(ratios[:15])
            for _ in range(deg+1):
                d = [d[i+1]-d[i] for i in range(len(d)-1)]
            if d and all(abs(float(x)) < 0.01 for x in d[:5]):
                print(f"  → Degree {deg} polynomial fits!")
                break
