"""Find the correct Bessel formula for K_{n=1}^inf A / (alpha*n + beta).

The standard identity (Perron 1954, Wall 1948):
  K_{n=0}^inf z / (n + a) = z * I_a(2z) / I_{a-1}(2z)      [z = sqrt(q)]
  K_{n=0}^inf (-z) / (n + a) = -z * J_a(2z) / J_{a-1}(2z)   [z = sqrt(|q|)]

But our CF has alpha != 1, so denominators are alpha*n + beta, not n + a.
We need the equivalence transform to map to the standard form.

Key insight:
  K_{n=1}^inf A / (alpha*n + beta)
  = A / ((alpha + beta) + A / ((2*alpha + beta) + ...))

Use Euler's equivalence transform with scaling factors e_n such that
  K a_n/b_n = K (a_n' / b_n')
  a_n' = a_n * e_n * e_{n-1}, b_n' = b_n * e_n

For our CF, let e_n = 1/alpha for all n >= 1:
  b_n' = (alpha*n + beta)/alpha = n + beta/alpha
  a_1' = A * e_1 = A/alpha = c
  a_n' = A * e_n * e_{n-1} = A/alpha^2 for n >= 2  ← NOT constant!

So we can't use a uniform scaling. Instead, try a DIFFERENT substitution.

Actually, the proper approach: factor alpha from each denominator via 
equivalence transform:
  K_{n=1}^inf A/(alpha*n+beta)
  
Apply the equivalence trick from Lorentzen-Waadeland:
Set d_0 = 1, d_n = 1/(alpha^n) for n >= 1.

Then the equivalence gives:
  a_n' = d_n * d_{n-1} * A_n / 1  -- wait this isn't standard.

Actually the equivalence theorem states:
  b0 + K(a_n/b_n) = b0*d0 + K(c_n*a_n / (c_n*b_n))  [not right either]

The correct statement is:
  K_{n=1}^inf a_n/b_n = K_{n=1}^inf (a_n * c_n * c_{n-1}) / (b_n * c_n)
  where c_0 = 1 and c_n arbitrary nonzero.

So with c_n = 1/alpha^n for n >= 1, c_0 = 1:
  b_n' = b_n * c_n = (alpha*n + beta) / alpha^n
  a_n' = A * c_n * c_{n-1} = A / alpha^(2n-1) for n >= 1
  
This doesn't help (the numerators and denominators both change with n).

ALTERNATE APPROACH: just numerically scan over Bessel parameters.
For a linear-b CF with a=A (constant), b=alpha*n+beta:
  Try many (nu, z) pairs and check if 
  value = beta + alpha * sqrt(A/alpha) * I_nu(z) / I_{nu-1}(z)
  or similar.

Actually, the SIMPLEST fix is to just compute the value numerically
and match it against a DATABASE of Bessel ratios at rational parameters.
"""
import mpmath

mp = mpmath.mp.clone()
mp.dps = 100

# The actual CF values to match:
test_cases = [
    ("a=[-6], b=[8,7]", 6.592858890863820073572, -6, 8, 7),
    ("a=[-9], b=[-7,8]", 4.671304623311044642098, -9, -7, 8),
]

for name, target, A, alpha, beta in test_cases:
    val = mp.mpf(target)
    print(f"\n=== {name}, value={mp.nstr(val, 15)} ===")
    
    found = False
    # Try: val = p/q * I_nu(z) / I_{nu-1}(z) + r/s
    # or: val = p/q * J_nu(z) / J_{nu-1}(z) + r/s
    # with rational p/q, r/s, nu, z
    
    # Most likely: val involves the CF parameters directly.
    # For alpha=1 CFs: val = beta + sqrt(A)*I_{1+beta}(2*sqrt(A))/I_{beta}(2*sqrt(A))
    # So for alpha != 1, maybe:
    # val = beta + alpha * sqrt(A/alpha^2) * I_{a0}(2*sqrt(A/alpha^2)) / I_{a0-1}(...)
    # where a0 = (alpha+beta)/alpha = 1 + beta/alpha
    
    # OR: the Perron formula with q = A/alpha^2 instead of A/alpha
    for q_denom in [1, 2, 4, 8, 16]:
        q = mp.mpf(A) / (mp.mpf(alpha) ** 2 * q_denom)
        a0 = 1 + mp.mpf(beta) / mp.mpf(alpha)
        
        if q > 0:
            z = 2 * mp.sqrt(q)
            try:
                ratio = mp.besseli(a0, z) / mp.besseli(a0 - 1, z)
                # Try: val = beta + alpha * sqrt(q) * ratio
                predicted = mp.mpf(beta) + mp.mpf(alpha) * mp.sqrt(q) * ratio
                diff = abs(val - predicted)
                if diff < mp.mpf(10)**(-10):
                    print(f"  MATCH! q=A/alpha^2/{q_denom}={float(q):.6f}, I ratio")
                    print(f"  predicted={mp.nstr(predicted, 20)}, diff={float(diff):.2e}")
                    found = True
            except: pass
        elif q < 0:
            z = 2 * mp.sqrt(-q)
            try:
                Ja = mp.besselj(a0, z)
                Jam1 = mp.besselj(a0 - 1, z)
                if abs(Jam1) > mp.mpf(10)**(-50):
                    ratio = Ja / Jam1
                    predicted = mp.mpf(beta) + mp.mpf(alpha) * (-mp.sqrt(-q)) * ratio
                    diff = abs(val - predicted)
                    if diff < mp.mpf(10)**(-10):
                        print(f"  MATCH! q=A/alpha^2/{q_denom}={float(q):.6f}, J ratio")
                        print(f"  predicted={mp.nstr(predicted, 20)}, diff={float(diff):.2e}")
                        found = True
            except: pass
    
    # Brute force: scan nu and z, match val against p*I_nu(z)/I_{nu-1}(z) + r
    if not found:
        print("  Direct parameter scan failed. Trying brute-force grid...")
        best_diff = mp.mpf(1e10)
        best_match = None
        
        for nu_num in range(-6, 20):
            for nu_den in [1, 2, 3, 4]:
                nu = mp.mpf(nu_num) / nu_den
                for z_num in range(1, 20):
                    for z_den in [1, 2, 3, 4]:
                        z = mp.mpf(z_num) / z_den
                        try:
                            Inu = mp.besseli(nu, z)
                            Inum1 = mp.besseli(nu - 1, z)
                            if abs(Inum1) < mp.mpf(10)**(-50):
                                continue
                            ratio = Inu / Inum1
                            # Match val = m * ratio + b_shift
                            for m_num in range(-8, 9):
                                if m_num == 0: continue
                                for m_den in [1, 2, 3, 4]:
                                    m = mp.mpf(m_num) / m_den
                                    residual = val - m * ratio
                                    # Check if residual is rational with small integers
                                    for r_num in range(-20, 21):
                                        for r_den in [1, 2, 3, 4]:
                                            r = mp.mpf(r_num) / r_den
                                            diff = abs(residual - r)
                                            if diff < best_diff:
                                                best_diff = diff
                                                if diff < mp.mpf(10)**(-10):
                                                    best_match = f"val = ({m_num}/{m_den})*I_{float(nu)}({float(z)})/I_{float(nu-1)}({float(z)}) + {r_num}/{r_den}"
                                                    
                        except: continue
        
        if best_match:
            print(f"  FOUND: {best_match}, diff={float(best_diff):.2e}")
        else:
            # Also try J functions
            for nu_num in range(-6, 12):
                for nu_den in [1, 2, 3, 4]:
                    nu = mp.mpf(nu_num) / nu_den
                    for z_num in range(1, 15):
                        for z_den in [1, 2, 3, 4]:
                            z = mp.mpf(z_num) / z_den
                            try:
                                Jnu = mp.besselj(nu, z)
                                Jnum1 = mp.besselj(nu - 1, z)
                                if abs(Jnum1) < mp.mpf(10)**(-50):
                                    continue
                                ratio = Jnu / Jnum1
                                for m_num in range(-8, 9):
                                    if m_num == 0: continue
                                    for m_den in [1, 2, 3, 4]:
                                        m = mp.mpf(m_num) / m_den
                                        residual = val - m * ratio
                                        for r_num in range(-20, 21):
                                            for r_den in [1, 2, 3, 4]:
                                                r = mp.mpf(r_num) / r_den
                                                diff = abs(residual - r)
                                                if diff < best_diff:
                                                    best_diff = diff
                                                    if diff < mp.mpf(10)**(-10):
                                                        best_match = f"val = ({m_num}/{m_den})*J_{float(nu)}({float(z)})/J_{float(nu-1)}({float(z)}) + {r_num}/{r_den}"
                            except: continue
            
            if best_match:
                print(f"  FOUND (J): {best_match}, diff={float(best_diff):.2e}")
            else:
                print(f"  No match found. Best diff = {float(best_diff):.2e}")
