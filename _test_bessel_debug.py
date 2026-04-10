"""Debug Bessel ID: trace the Perron formula step by step."""
import mpmath

mp = mpmath.mp.clone()
mp.dps = 100

A, alpha, beta = -6, 8, 7
print("CF a=[-6], b=[8,7]")
print(f"  b(n) = {alpha}*n + {beta} for n>=0")
print(f"  a(n) = {A} for n>=1")
print()

# The CF representation:
# CF = b(0) + a(1)/(b(1) + a(2)/(b(2) + ...))
# b(0)=7, b(1)=15, b(2)=23, b(3)=31, ...
# a(n)=-6 for all n>=1

# So CF = 7 + (-6)/(15 + (-6)/(23 + (-6)/(31 + ...)))
# The tail starting from n=1:
# T = a(1)/(b(1) + a(2)/(b(2) + ...))
# = -6/(15 + -6/(23 + -6/(31 + ...)))

# Perron's formula: for K_{n=1}^inf c/(n*alpha' + beta')
# where the partial fractions are a(n)/b(n)
# We need this in the form K_{m=0}^inf c'/(m + a0)

# The CF without b(0):
# tail = K_{n=1}^inf A/(alpha*n + beta)
# = A/((alpha+beta) + A/((2*alpha+beta) + ...))

# Divide out alpha:
# = (A/alpha) / ((1 + beta/alpha) + (A/alpha)/((2 + beta/alpha) + ...))
# = c / (a0 + c / (a0+1 + c / (a0+2 + ...)))
# where c = A/alpha, a0 = 1 + beta/alpha

c = mp.mpf(A) / mp.mpf(alpha)  # -0.75
a0 = 1 + mp.mpf(beta) / mp.mpf(alpha)  # 1.875
print(f"c = {float(c)}, a0 = {float(a0)}")

# But wait - alpha is in front:
# tail = alpha * K_{m=0}^inf c / (m + a0)
# No - let me re-derive.

# K_{n=1}^inf A / (alpha*n + beta)
# = A / ((alpha + beta) + A / ((2*alpha + beta) + A / ...))
# Factor out alpha from each denominator:
# = A / (alpha*(1 + beta/alpha) + A / (alpha*(2 + beta/alpha) + ...))
# This is NOT the same as alpha * K{...} unless we equivalence-transform.

# Actually the standard Perron result is:
# K_{n=1}^inf a_n/b_n with a_n = A, b_n = alpha*n + beta
# = -alpha * f  where f solves some recurrence
# No... Let me just use the Gauss formula directly.

# The Perron/Gauss CF for Bessel:
# I_v(z)/I_{v-1}(z) = (z/2) / (v + (z/2)^2 / (v+1 + (z/2)^2 / (v+2 + ...)))
# = K_{n=0}^inf (z/2)^2 / (v + n)

# So K_{n=0}^inf q / (v + n) = (z/2) * I_v(z) / I_{v-1}(z)
# where q = (z/2)^2

# Our tail (after removing b(0)=7) is:
# T = A / (b(1) + A/(b(2) + ...))
# = A / ((alpha + beta) + A/((2*alpha + beta) + ...))

# b(n) for n>=1: alpha*n + beta
# So the inner CF from n=1 is:
# K_{n=1}^inf A / (alpha*n + beta)

# Let's match this to K_{n=0}^inf q / (v + n):
# We need: A / (alpha*n + beta) = q / (n + v)
# where n starts from 1, but the Perron CF starts from 0.

# Shift: let m = n-1, so n=m+1:
# K_{m=0}^inf A / (alpha*(m+1) + beta) = K_{m=0}^inf A / (alpha*m + alpha + beta)
# = K_{m=0}^inf (A/alpha) / (m + (alpha+beta)/alpha)
# = K_{m=0}^inf c / (m + a0)
# where c = A/alpha = -0.75, a0 = (alpha+beta)/alpha = 15/8 = 1.875

# NOW: K_{m=0}^inf c / (m + a0)
# If c > 0 (say q): f(a0, q) = sqrt(q) * I_{a0}(2*sqrt(q)) / I_{a0-1}(2*sqrt(q))
# If c < 0, let c = -|c|:
# f(a0, -|c|) = -sqrt(|c|) * J_{a0}(2*sqrt(|c|)) / J_{a0-1}(2*sqrt(|c|))

# BUT: our original tail was:
# T = K_{n=1}^inf A / (alpha*n + beta)
# After the shift, this becomes:
# T = K_{m=0}^inf A / (alpha*(m+1) + beta)
# But the denominators in the original CF are alpha*n + beta (the first one is alpha+beta),
# and each numerator is A.
# After equivalence transform dividing by alpha:
# T = (1/1) * K_{m=0}^inf c / (m + a0)  ... but with a factor of alpha?

# Actually no. K_{n=1}^inf A/(alpha*n+beta) means:
# A/(alpha+beta + A/(2*alpha+beta + A/(3*alpha+beta + ...)))
# = A/(alpha*(1+beta/alpha) + A/(alpha*(2+beta/alpha) + ...))

# To factor alpha out of EVERY denominator, use equivalence transform:
# K a_n/b_n = K (a_n/b_n) = K (A/(alpha*n+beta))
# After equivalence: (A/alpha) / ((n + beta/alpha) + ...)
# Actually equivalence transforms are tricky. Let me just compute numerically.

# Compute the normalized CF K_{m=0}^inf c / (m + a0) directly:
print("\nCompute normalized CF K_{m=0}^inf c/(m+a0):")
val_norm = mp.mpf(a0)  # = 0 + a0 from start
tiny = mp.mpf(10)**(-100)
C = val_norm if val_norm != 0 else tiny
D = mp.mpf(0)
for m in range(0, 500):
    an = c
    bn = mp.mpf(m + 1) + a0  # wait, that's wrong.
    # K_{m=0}^inf c/(m+a0) means:
    # c/(a0 + c/(a0+1 + c/(a0+2 + ...)))
    # So b_m = m + a0 for m >= 0
    # But actually the CF starts as:
    # f = c / (a0 + c / (1+a0 + c / (2+a0 + ...)))
    # No: K_{m=0}^inf c/(m+a0) = c/(a0 + c/((1+a0) + c/((2+a0) + ...)))
    pass

# Let me just compute it with Lentz properly
# CF = c / (a0 + c / (a0+1 + c / (a0+2 + ...)))
# In standard notation: b0 = a0, a_m = c, b_m = m + a0 for m >= 1
# So f = a0 + c/(a0+1 + c/(a0+2 + ...)), then CF_value = c/f? No.
# Actually K_{m=0}^inf c/(m+a0) in the Gauss notation means:
# c/(a0 + c/(a0+1 + c/(a0+2 + ...)))
# f = a0 + c/(a0+1 + c/(a0+2 + ...))
# Then the whole thing = c/f.

# Hmm let me just compute raw using Lentz from the definition.
print("Recomputing with explicit Lentz:")
# CF_tail = A/(b1 + A/(b2 + A/(b3 + ...)))
# b_n = alpha*n + beta for n >= 1
# a_n = A for n >= 1
f_tail = mp.mpf(alpha + beta)
C = f_tail if f_tail != 0 else tiny
D = mp.mpf(0)
for n in range(2, 500):
    an = mp.mpf(A)
    bn = mp.mpf(alpha * n + beta)
    D = bn + an * D
    if D == 0: D = tiny
    C = bn + an / C
    if C == 0: C = tiny
    D = 1 / D
    f_tail *= C * D
# f_tail is now b1 + A/(b2 + ...), so CF_tail = A / f_tail
tail = mp.mpf(A) / f_tail
print(f"  Tail (A/f) = {mp.nstr(tail, 22)}")
print(f"  beta + tail = {mp.nstr(mp.mpf(beta) + tail, 22)}")

# Now compute Perron prediction for the tail
# tail = K_{n=1}^inf A/(alpha*n+beta)
# shift: K_{m=0}^inf c/(m+a0) where c = A/alpha, a0 = 1 + beta/alpha
# The Perron formula gives the VALUE of the CF K_{m=0}^inf c/(m+a0)
# For c = -|c| < 0:
# K = -sqrt(|c|) * J_{a0}(2*sqrt(|c|)) / J_{a0-1}(2*sqrt(|c|))

abs_c = abs(c)
z = 2 * mp.sqrt(abs_c)
Ja0 = mp.besselj(a0, z)
Ja0m1 = mp.besselj(a0 - 1, z)
f_perron = -mp.sqrt(abs_c) * Ja0 / Ja0m1
print(f"\n  Perron f = -sqrt(|c|) * J_a0(z) / J_(a0-1)(z)")
print(f"  = -sqrt({float(abs_c)}) * J_{float(a0)}({float(z)}) / J_{float(a0-1)}({float(z)})")
print(f"  = {mp.nstr(f_perron, 22)}")

# But tail = alpha * f_perron (scaling from equivalence transform)
# NO! The shift K_{m=0}^inf c/(m+a0) is NOT the same as tail/alpha.
# Let me think again...

# tail = A / ((alpha+beta) + A/((2*alpha+beta) + ...))
# Let me factor alpha out of denominators using equivalence transform:
# = A / (alpha * (1+beta/alpha) + A / (alpha * (2+beta/alpha) + ...))
# Equivalence: multiply each denominator-pair by (1/alpha):
# = (A/alpha) / ((1+beta/alpha) + (A/alpha^2) / ((2+beta/alpha) + ...))
# Hmm, that doesn't quite work because the numerators change differently.

# Actually the equivalence transformation for CFs:
# K a_n/b_n = K (c_n*a_n)/(c_n*b_n) for any c_n != 0
# But we need to use c_n to normalize b_n to (n + a0).

# Standard approach: b_n = alpha*n + beta. Set c_n = 1/alpha for all n.
# Then K A/(alpha*n+beta) = K (A/alpha)/(n + beta/alpha) ... but with n starting from 1.
# With the shift m = n-1:
# = K (A/alpha) / ((m+1) + beta/alpha) = K c / (m + 1 + beta/alpha) = K c / (m + a0)
# where a0 = 1 + beta/alpha.
# WAIT: this requires the equivalence c_n = 1/alpha for the n-th fraction.
# The full equivalence: K a_n/b_n with c_0=1, c_n = 1/alpha for n >= 1
# gives: K (a_n * c_n) / (b_n * c_n + ... ) -- no, the formula is:
# a_n'/b_n' = (c_n * c_{n-1} * a_n) / (c_n * b_n)
# So a_n' = c_n * c_{n-1} * a_n, b_n' = c_n * b_n

# With c_n = 1/alpha for n >= 1, c_0 = 1:
# b_1' = (1/alpha) * (alpha+beta) = 1 + beta/alpha = a0 ✓
# a_1' = c_1 * c_0 * A = (1/alpha) * 1 * A = A/alpha = c ✓
# b_2' = (1/alpha) * (2*alpha+beta) = 2 + beta/alpha = 1 + a0 ✓
# a_2' = c_2 * c_1 * A = (1/alpha) * (1/alpha) * A = A/alpha^2  ← NOT c!

# So a_n' = A / alpha^n  (geometrically shrinking!) ← This is WRONG for Perron.
# We need constant numerators!

# OK so the direct Perron equivalence doesn't work this way.
# Let me use the CORRECT transformation.

# For linear-b denominator CF: K_{n=1}^inf A/(alpha*n + beta)
# Use the modified Lentz for the normalized form.
# 
# The correct Perron formula for K_{n=1}^inf c/(a0+n-1) where c is constant:
# = c / (a0 + c/(a0+1 + ...)) (shifting n -> starting from a0)
# 
# But our factor pattern is A / (alpha*n + beta) = A/alpha / (n + beta/alpha)
# The n goes 1, 2, 3, ... so denominators are 1+beta/alpha, 2+beta/alpha, ...
# = a0, a0+1, a0+2, ...
#
# So the CF is: (A/alpha) / (a0 + (A/alpha)/(a0+1 + (A/alpha)/(a0+2 + ...)))
# ... but only if numerators are ALL A/alpha. With the equivalence c_n approach
# the numerators DON'T stay constant!
#
# The issue: K A/(alpha*n+beta) ≠ K (A/alpha)/(n+beta/alpha) because
# in a regular CF, you can't just divide one b and one a independently.

# Actually, I think there's a simpler identity:
# K_{n=1}^inf A / (alpha*n + beta)
# = alpha * K_{n=1}^inf (A/alpha^2) / (n + beta/alpha)
# NO, that's also wrong.

# The CORRECT transformation for K_{n=1}^inf a_n/b_n:
# By equivalence with d_1 = 1, d_n = 1/alpha for n >= 2:
# a_1' = d_1 * a_1 = A (unchanged)
# b_1' = d_1 * b_1 = alpha + beta (unchanged)  
# a_2' = d_2 * a_2 / d_1 = A/alpha
# b_2' = d_2 * b_2 = (2*alpha+beta)/alpha
# Hmm no, let me just use the direct formula.

# OK forget the algebra. Let me just numerically check if the formula matches.
# The Perron formula for K_{n=0}^inf c/(m+a) is:
# = sqrt(c) * I_a(2*sqrt(c)) / I_{a-1}(2*sqrt(c))   for c > 0
# = -sqrt(|c|) * J_a(2*sqrt(|c|)) / J_{a-1}(2*sqrt(|c|))   for c < 0

# But this applies to the NORMALIZED CF where EVERY numerator is c 
# and every denominator is m+a.

# Our tail is NOT in this form because the numerators are A (constant)
# but the denominators are alpha*n+beta (linear in n). These are NOT
# the same as n + a0 unless alpha = 1.

# For alpha = 1: K_{n=1}^inf A/(n+beta) = K_{m=0}^inf A/(m+1+beta)
# This IS Perron form with c = A, a = 1+beta. WORKS.

# For alpha != 1: The CF is NOT in Perron form!
# We need a different formula.

# The correct approach for alpha != 1:
# Use Euler's equivalence transform to convert to Perron form.
# K_{n=1}^inf A/(alpha*n+beta) 
# After applying Euler's contraction/expansion, we get...

# Actually, let me check: does the code (analysis.py bessel_identification)
# actually match? It computes f_target = (val - beta) / alpha.
# Let me check what f_target is vs f_perron.

actual_cf = mp.mpf(beta) + tail  # = beta + tail
f_target = (actual_cf - mp.mpf(beta)) / mp.mpf(alpha)
print(f"\n  f_target = (CF - beta)/alpha = {mp.nstr(f_target, 22)}")
print(f"  f_perron = {mp.nstr(f_perron, 22)}")
print(f"  diff = {float(abs(f_target - f_perron)):.6e}")

# So the question is: does tail = alpha * f_perron?
print(f"\n  tail = {mp.nstr(tail, 22)}")  
print(f"  alpha * f_perron = {mp.nstr(mp.mpf(alpha) * f_perron, 22)}")
print(f"  Match? {abs(tail - mp.mpf(alpha) * f_perron) < mp.mpf(10)**(-20)}")

# The formula S = alpha * f assumes the equivalence K A/(alpha*n+beta) = alpha * K c/(m+a0)
# which is only true if alpha = 1 or after proper scaling.
# For alpha != 1, the ACTUAL relationship is more complex.
