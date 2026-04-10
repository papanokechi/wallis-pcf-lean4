"""Fix bugs in §33 (spurious PSLQ), §34 (precision underflow), §35 (redundant basis)."""
import json

with open('gcf_borel_verification.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

code_cells = [(i, c) for i, c in enumerate(nb['cells']) if c['cell_type'] == 'code']

# ── Fix 1: §33 (code cell 32) — check that V_quad has nonzero coefficient ──
ci32, cell32 = code_cells[32]
src32 = ''.join(cell32['source'])

# Replace the pslq_test function to filter spurious matches
old_pslq = """def pslq_test(name, basis, prec=200, maxcoeff=10000):
    # Run PSLQ and report result.
    mp.mp.dps = prec
    try:
        rel = mp.pslq(basis, tol=mp.power(10, -prec+20), maxcoeff=maxcoeff)
        if rel:
            active = [(c, i) for i, c in enumerate(rel) if c != 0]
            results.append((name, 'POSITIVE', str(active)))
            return rel
        else:
            results.append((name, 'NEGATIVE', f'{prec}d, coeff<={maxcoeff}'))
            return None
    except Exception as e:
        results.append((name, 'ERROR', str(e)[:60]))
        return None"""

new_pslq = """def pslq_test(name, basis, prec=200, maxcoeff=10000):
    # Run PSLQ and report result. basis[0] = V_quad always.
    mp.mp.dps = prec
    try:
        rel = mp.pslq(basis, tol=mp.power(10, -prec+20), maxcoeff=maxcoeff)
        if rel:
            if rel[0] == 0:
                # V_quad not involved -- spurious relation among other basis elements
                results.append((name, 'NEGATIVE', f'{prec}d (spurious: V not in rel)'))
                return None
            active = [(c, i) for i, c in enumerate(rel) if c != 0]
            results.append((name, 'POSITIVE', str(active)))
            return rel
        else:
            results.append((name, 'NEGATIVE', f'{prec}d, coeff<={maxcoeff}'))
            return None
    except Exception as e:
        results.append((name, 'ERROR', str(e)[:60]))
        return None"""

src32 = src32.replace(old_pslq, new_pslq)
cell32['source'] = [line + '\n' if i < len(src32.split('\n'))-1 else line 
                    for i, line in enumerate(src32.split('\n'))]
nb['cells'][ci32] = cell32
print("Fixed §33: PSLQ now filters spurious relations where V_quad has zero coefficient")

# ── Fix 2: §34 (code cell 33) — increase precision and handle zero division ──
ci33, cell33 = code_cells[33]
src33 = ''.join(cell33['source'])

# Fix 1: Use higher precision for forward recurrence
src33 = src33.replace('mp.mp.dps = 60', 'mp.mp.dps = 120')
# Fix 2: Handle division by zero in R_n/R_prev
src33 = src33.replace(
    '        actual = R_n/R_prev\n        predicted = mp.mpf(-1)/(3*n**2 + n + 1)\n        rel_err = abs(actual/predicted - 1)',
    '        if abs(R_prev) < mp.mpf(10)**(-100):\n            print(f"  n={n:3d}: R_prev underflow (precision limit)")\n            continue\n        actual = R_n/R_prev\n        predicted = mp.mpf(-1)/(3*n**2 + n + 1)\n        rel_err = abs(actual/predicted - 1) if abs(predicted) > 0 else mp.mpf(0)'
)
# Fix 3: Handle sigma_n division by zero
src33 = src33.replace(
    '    R_n = As[n] - V*Bs[n]\n    sigma = R_n * prod_b\n    if n <= 5 or n % 10 == 0:',
    '    R_n = As[n] - V*Bs[n]\n    if abs(R_n) < mp.mpf(10)**(-100):\n        if n <= 5 or n % 10 == 0:\n            print(f"    n={n:3d}: R_n underflow")\n        continue\n    sigma = R_n * prod_b\n    if n <= 5 or n % 10 == 0:'
)
cell33['source'] = [line + '\n' if i < len(src33.split('\n'))-1 else line
                    for i, line in enumerate(src33.split('\n'))]
nb['cells'][ci33] = cell33
print("Fixed §34: Increased precision to 120dps, added underflow guards")

# ── Fix 3: §35 (code cell 34) — remove redundant m(P) from basis ──
ci34, cell34 = code_cells[34]
src34 = ''.join(cell34['source'])

# Replace the first PSLQ basis to not include m(P) since m(P) = log(3) exactly
src34 = src34.replace(
    "basis_mahler = [V, mp.mpf(1), m_P, L_chi_2, mp.pi, mp.log(3), mp.sqrt(11)]\nlabels_mahler = ['V', '1', 'm(P)', 'L(chi,2)', 'pi', 'log3', 'sqrt11']",
    "# Note: m(P) = log(3) exactly (both roots inside unit disk), so we don't\n# include both. Instead test V against L-values and arithmetic constants.\nbasis_mahler = [V, mp.mpf(1), L_chi_2, mp.pi, mp.log(3), mp.sqrt(11)]\nlabels_mahler = ['V', '1', 'L(chi,2)', 'pi', 'log3', 'sqrt11']"
)

# Fix Jensen integral (was computing log|P(e^it)| not log|3e^{2it}+e^{it}+1|, and the
# formula already includes log(3) as a separate term, so we should not add it again)
src34 = src34.replace(
    "jensen = mp.log(3) + mp.quad(lambda t: mp.log(abs(3*mp.expj(2*t) + mp.expj(t) + 1)), [0, 2*mp.pi]) / (2*mp.pi)",
    "# m(P) = (1/2pi) * int_0^{2pi} log|P(e^{it})| dt = (1/2pi) * int log|3e^{2it}+e^{it}+1| dt\njensen = mp.quad(lambda t: mp.log(abs(3*mp.expj(2*t) + mp.expj(t) + 1)), [0, 2*mp.pi]) / (2*mp.pi)"
)

# Fix the summary to match the new basis
src34 = src34.replace(
    'print("  PSLQ against [V, 1, m(P), L(chi,2), pi, log3, sqrt(11)]: NEGATIVE")',
    'print("  PSLQ against [V, 1, L(chi,2), pi, log3, sqrt(11)]: NEGATIVE")'
)

cell34['source'] = [line + '\n' if i < len(src34.split('\n'))-1 else line
                    for i, line in enumerate(src34.split('\n'))]
nb['cells'][ci34] = cell34
print("Fixed §35: Removed redundant m(P) from PSLQ basis, fixed Jensen integral")

with open('gcf_borel_verification.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("\nAll fixes applied. Re-run _run_v7_cells.py to get corrected outputs.")
