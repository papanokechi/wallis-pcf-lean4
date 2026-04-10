"""Validate all PCF conjectures at 300 digits, run perturbation tests, degree sweeps."""
import ramanujan_breakthrough_generator as rbg
from mpmath import mp
import itertools, time, json

# ── Step 1: High-precision validation ────────────────────────────────────────

def validate_conjectures():
    mp.dps = 350
    engine = rbg.PCFEngine(precision=300)

    conjectures = [
        ('e CF1',        [0,-1], [-3,-1], 'e'),
        ('e CF2',        [0,-1], [3,1],   'e'),
        ('phi CF1',      [1,0],  [1,0],   'phi'),
        ('phi CF2',      [4,0],  [-2,0],  'phi'),
        ('phi CF3',      [4,0],  [2,0],   'phi'),
        ('phi CF4',      [1,0],  [-1,0],  'phi'),
        ('pi Brouncker', [0,0,1],[1,2,0], 'pi'),
        ('pi novel',     [0,3,-2],[1,3,0],'pi'),
    ]

    sep = '=' * 78
    print(sep)
    print('  HIGH-PRECISION VALIDATION (300 digits, depth=1000)')
    print(sep)

    results = []
    for name, alpha, beta, tgt in conjectures:
        val, err, conv = engine.evaluate_pcf(alpha, beta, depth=1000)
        if val is None:
            print(f'\n  {name}: FAILED (val=None)')
            continue

        matched, formula, digits = engine.match_known_constant(val, tgt, 300)
        tgt_val = engine._get_constant(tgt)

        best_err = None
        best_label = formula
        if tgt_val:
            checks = []
            for p in range(-8, 9):
                if p == 0: continue
                for q in range(1, 9):
                    r = mp.mpf(p) / q
                    checks.append((f'{p}/{q}*{tgt}', abs(val - r * tgt_val)))
                    checks.append((f'{p}/({q}*{tgt})', abs(val - r / tgt_val)))
                    checks.append((f'{tgt}+{p}/{q}', abs(val - (tgt_val + r))))
            for label, e in checks:
                if best_err is None or e < best_err:
                    best_err = e
                    best_label = label

        digs = -int(mp.log10(best_err)) if best_err and best_err > 0 else 300
        status = 'CONFIRMED' if digs >= 100 else ('STRONG' if digs >= 30 else 'WEAK')

        print(f'\n  [{status}] {name}')
        print(f'    alpha={alpha}  beta={beta}')
        print(f'    Best match: {best_label}')
        print(f'    Digits matched: {digs}  (match_known_constant: {digits}d)')
        if best_err:
            print(f'    Abs error: {float(best_err):.3e}')
        if err:
            print(f'    Convergent err at depth 1000: {float(err):.3e}')

        results.append(dict(name=name, alpha=alpha, beta=beta, target=tgt,
                            formula=best_label, digits=digs, status=status))

    n_conf = sum(1 for r in results if r['status'] == 'CONFIRMED')
    n_str  = sum(1 for r in results if r['status'] == 'STRONG')
    n_weak = sum(1 for r in results if r['status'] == 'WEAK')
    print(f'\n{sep}')
    print(f'  Summary: {n_conf} confirmed, {n_str} strong, {n_weak} weak')
    return results


# ── Step 2: Perturbation stability ───────────────────────────────────────────

def perturbation_tests():
    mp.dps = 80
    engine = rbg.PCFEngine(precision=60)

    conjectures = [
        ('e CF2',        [0,-1], [3,1],   'e'),
        ('phi CF1',      [1,0],  [1,0],   'phi'),
        ('pi Brouncker', [0,0,1],[1,2,0], 'pi'),
    ]

    sep = '=' * 78
    print(f'\n{sep}')
    print('  PERTURBATION STABILITY TEST')
    print(sep)

    for name, alpha, beta, tgt in conjectures:
        tgt_val = engine._get_constant(tgt)
        val0, _, _ = engine.evaluate_pcf(alpha, beta, depth=500)
        if val0 is None:
            continue
        _, _, base_digits = engine.match_known_constant(val0, tgt, 60)

        print(f'\n  {name} (base: {base_digits}d)')
        # Perturb each coefficient by ±1
        all_coeffs = alpha + beta
        for i in range(len(all_coeffs)):
            for delta in [-1, 1]:
                perturbed = all_coeffs[:]
                perturbed[i] += delta
                pa = perturbed[:len(alpha)]
                pb = perturbed[len(alpha):]
                if all(c == 0 for c in pa):
                    continue
                val_p, _, _ = engine.evaluate_pcf(pa, pb, depth=200)
                if val_p is None:
                    print(f'    coeff[{i}]+={delta:+d}: diverged')
                    continue
                _, _, p_digits = engine.match_known_constant(val_p, tgt, 60)
                degraded = base_digits - p_digits
                marker = 'OK' if degraded > 20 else 'SUSPICIOUS'
                print(f'    coeff[{i}]+={delta:+d}: {p_digits}d (lost {degraded}d) [{marker}]')


# ── Step 3: Degree sweep for pi and zeta(3) ──────────────────────────────────

def degree_sweep():
    mp.dps = 80
    engine = rbg.PCFEngine(precision=60)

    sep = '=' * 78
    print(f'\n{sep}')
    print('  DEGREE SWEEP: pi and zeta3')
    print(sep)

    for tgt in ['pi', 'zeta3']:
        print(f'\n  --- {tgt} ---')
        tgt_val = engine._get_constant(tgt)
        best_per_deg = {}

        for da in range(1, 7):
            for db in range(1, 4):
                R = range(-3, 4) if da + db <= 6 else range(-2, 3)
                n_alpha = da + 1
                n_beta = db + 1
                space = len(R) ** (n_alpha + n_beta)
                if space > 200000:
                    continue  # skip huge spaces

                t0 = time.time()
                hits = []
                best_residual = 1e10
                ct = 0
                for coeffs in itertools.product(R, repeat=n_alpha + n_beta):
                    ac = list(coeffs[:n_alpha])
                    bc = list(coeffs[n_alpha:])
                    if all(c == 0 for c in ac) or bc[0] == 0:
                        continue
                    ct += 1
                    try:
                        val, err, conv = engine.evaluate_pcf(ac, bc, depth=100)
                        if val is None:
                            continue
                        matched, formula, digits = engine.match_known_constant(val, tgt, 60)
                        if matched and digits >= 10:
                            hits.append((ac, bc, formula, digits))
                        # Track best residual
                        for p in [-1, 1, 2, -2, 4, -4, 6, -6]:
                            for q in [1, 2, 3, 4, 6]:
                                r = mp.mpf(p) / q
                                d = float(abs(val - r * tgt_val))
                                if d < best_residual:
                                    best_residual = d
                                d2 = float(abs(val - r / tgt_val))
                                if d2 < best_residual:
                                    best_residual = d2
                    except Exception:
                        continue

                elapsed = time.time() - t0
                key = f'deg({da},{db})'
                best_per_deg[key] = (len(hits), best_residual, ct)

                if hits:
                    print(f'    {key}: {len(hits)} HITS in {ct} candidates ({elapsed:.1f}s)')
                    seen = set()
                    for a, b, f, d in sorted(hits, key=lambda x: -x[3]):
                        if f not in seen:
                            seen.add(f)
                            print(f'      a={a} b={b} -> {f} ({d}d)')
                        if len(seen) >= 3:
                            break
                elif ct > 0:
                    print(f'    {key}: 0 hits, best_residual={best_residual:.2e} ({ct} cands, {elapsed:.1f}s)')

        print(f'\n    Best degrees for {tgt}:')
        for k, (h, r, c) in sorted(best_per_deg.items(), key=lambda x: -x[1][0] if x[1][0] else x[1][1]):
            if h > 0:
                print(f'      {k}: {h} hits')


# ── Step 4: Targeted Apery neighborhood ──────────────────────────────────────

def apery_neighborhood():
    mp.dps = 150
    engine = rbg.PCFEngine(precision=120)

    sep = '=' * 78
    print(f'\n{sep}')
    print('  TARGETED APERY NEIGHBORHOOD SEARCH')
    print(sep)

    # Known Apery: alpha=[0,0,0,0,0,0,-1] (=-n^6), beta=[5,27,51,34]
    # Search ±3 around each Apery beta coefficient, keep alpha=-n^6 fixed
    alpha_apery = [0, 0, 0, 0, 0, 0, -1]
    beta_center = [5, 27, 51, 34]

    hits = []
    ct = 0
    t0 = time.time()
    R = range(-3, 4)  # perturbation range
    for d0, d1, d2, d3 in itertools.product(R, repeat=4):
        beta = [beta_center[0]+d0, beta_center[1]+d1, beta_center[2]+d2, beta_center[3]+d3]
        if beta[0] == 0:
            continue
        ct += 1
        try:
            val, err, conv = engine.evaluate_pcf(alpha_apery, beta, depth=500)
            if val is None:
                continue
            matched, formula, digits = engine.match_known_constant(val, 'zeta3', 120)
            if matched and digits >= 10:
                is_exact = (d0 == 0 and d1 == 0 and d2 == 0 and d3 == 0)
                label = ' [KNOWN APERY]' if is_exact else ' [NEW!]'
                hits.append((beta, formula, digits, label))
                print(f'    HIT: beta={beta} -> {formula} ({digits}d){label}')
        except Exception:
            continue

    elapsed = time.time() - t0
    print(f'\n    Searched {ct} beta perturbations in {elapsed:.1f}s')
    print(f'    Total hits: {len(hits)}')

    # Also try different alpha forms around -n^6
    print(f'\n  Searching alpha perturbations (beta=Apery fixed)...')
    alpha_hits = []
    ct2 = 0
    t0 = time.time()
    # Try alpha = c * n^k for various k and small c
    for deg in [4, 5, 6, 7, 8]:
        for c in [-2, -1, 1, 2]:
            alpha = [0] * deg + [c]
            ct2 += 1
            try:
                val, err, conv = engine.evaluate_pcf(alpha, beta_center, depth=500)
                if val is None:
                    continue
                matched, formula, digits = engine.match_known_constant(val, 'zeta3', 120)
                if matched and digits >= 10:
                    alpha_hits.append((alpha, formula, digits))
                    print(f'    HIT: alpha=...{c}*n^{deg} -> {formula} ({digits}d)')
            except Exception:
                continue

    elapsed = time.time() - t0
    print(f'    Searched {ct2} alpha variants in {elapsed:.1f}s, {len(alpha_hits)} hits')


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    results = validate_conjectures()
    perturbation_tests()
    degree_sweep()
    apery_neighborhood()
    print('\n' + '=' * 78)
    print('  ALL VALIDATION COMPLETE')
    print('=' * 78)
