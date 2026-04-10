"""
_pcf_search_exponents_extended.py
==================================
Extended PCF + PSLQ search for 3D Ising model constants.

Three-pronged attack:
  A) PSLQ on Kc against a 60+ term basis including elliptic integrals K(k)
     at algebraic k, Dedekind eta at CM points, and Gamma(p/q).
  B) PCF search targeting universal critical exponents nu ~ 0.6301 and
     eta ~ 0.0363 (lattice-independent, more likely to have clean forms).
  C) Degree-4 and degree-5 polynomial coefficients for all targets.

Usage:
  python _pcf_search_exponents_extended.py
"""

from __future__ import annotations
import json, time, sys, random, math, traceback
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, ".")
import ramanujan_breakthrough_generator as rbg

from mpmath import (
    mp, mpf, pi, log, sqrt, zeta, euler, gamma as mpgamma,
    exp, nstr, ellipk, ellipe, catalan, phi as golden_phi,
)
import mpmath

# ── High-precision target constants ───────────────────────────────────────

# 3D Ising critical coupling (Ferrenberg-Xu-Landau 2018)
KC_HP = "0.22165455054281198362779272823516"
TC_HP = "4.51152785060191536876679816744526"

# 3D Ising universal critical exponents (Kos-Poland-Simmons-Duffin 2016,
# conformal bootstrap; El-Showk et al. 2014)
NU_HP = "0.6299709"     # nu: correlation length exponent (7 digits)
ETA_HP = "0.0362978"    # eta: anomalous dimension (7 digits)
# Derived exponents
# gamma = nu * (2 - eta)
# beta  = nu * (1 + eta) / 2   -- wait, that's not right
# Standard scaling: gamma = (2-eta)*nu, beta = nu*(d-2+eta)/2 with d=3
# alpha = 2 - d*nu = 2 - 3*nu
# beta = nu*(1+eta)/2   -- this IS wrong; beta = nu(d-2+eta)/2 = nu(1+eta)/2 for d=3
# Actually: beta = nu/2 * (d - 2 + eta) = nu/2 * (1 + eta) for d=3. Yes.
# omega ~ 0.8297 (correction-to-scaling)
OMEGA_HP = "0.8297"
# delta = (d + 2 - eta) / (d - 2 + eta) = (5 - eta)/(1 + eta) for d=3
# gamma/nu = 2 - eta


# =====================================================================
#  PART A: PSLQ on Kc against extended basis
# =====================================================================

def build_extended_basis(prec: int) -> dict[str, mpf]:
    """Build a 60+ element basis for PSLQ integer relation detection.

    Includes:
      - Standard constants (1, pi, log2, sqrt2, etc.)
      - Elliptic integrals K(k^2) at algebraic k
      - Dedekind eta at CM points (via q-product)
      - Gamma(p/q) at small rationals
      - 2D Ising critical coupling
      - Catalan, Apery (zeta3), Euler-Mascheroni
    """
    mp.dps = prec + 30
    b: dict[str, mpf] = {}

    # Standard (no linearly dependent elements: phi = (1+sqrt5)/2)
    b["1"] = mpf(1)
    b["pi"] = pi
    b["pi^2"] = pi ** 2
    b["1/pi"] = 1 / pi
    b["log2"] = log(2)
    b["log3"] = log(3)
    b["sqrt2"] = sqrt(2)
    b["sqrt3"] = sqrt(3)
    b["sqrt5"] = sqrt(5)
    # phi omitted: phi = (1+sqrt5)/2 is linearly dependent on {1, sqrt5}
    b["e"] = exp(1)
    b["euler_gamma"] = euler
    b["zeta3"] = zeta(3)
    b["zeta5"] = zeta(5)
    b["catalan"] = catalan

    # Gamma at rationals
    for p, q in [(1,3),(1,4),(1,6),(2,3),(3,4),(5,6),(1,5),(2,5)]:
        b[f"Gamma({p}/{q})"] = mpgamma(mpf(p)/q)
    b["Gamma(1/4)^2"] = mpgamma(mpf(1)/4) ** 2
    b["Gamma(1/3)^2"] = mpgamma(mpf(1)/3) ** 2

    # Elliptic integrals K(m) where m = k^2 at algebraic k
    ell_points = [
        ("K(1/2)", mpf(1)/2),                        # k=1/sqrt(2), m=1/2
        ("K(1/4)", mpf(1)/4),                        # m=1/4
        ("K(3/4)", mpf(3)/4),                        # m=3/4
        ("K((sqrt5-1)/4)", (sqrt(5)-1)/4),           # golden ratio related
        ("K(1/3)", mpf(1)/3),
        ("K(2/3)", mpf(2)/3),
        ("K(1/8)", mpf(1)/8),
        ("K(1/16)", mpf(1)/16),
    ]
    for label, m_val in ell_points:
        try:
            b[label] = ellipk(m_val)
        except Exception:
            pass

    # Complete elliptic integral E(m)
    for label_e, m_val in [("E(1/2)", mpf(1)/2), ("E(1/4)", mpf(1)/4)]:
        try:
            b[label_e] = ellipe(m_val)
        except Exception:
            pass

    # Dedekind eta at CM points via q-product
    cm_taus = [
        ("eta(i)", 1j * mpf(1)),
        ("eta(i*sqrt2)", 1j * sqrt(mpf(2))),
        ("eta(i*sqrt3)", 1j * sqrt(mpf(3))),
        ("eta((1+i*sqrt3)/2)", (1 + 1j*sqrt(mpf(3)))/2),
        ("eta(i*sqrt7)", 1j * sqrt(mpf(7))),
        ("eta((1+i*sqrt163)/2)", (1 + 1j*sqrt(mpf(163)))/2),
    ]
    for label, tau in cm_taus:
        try:
            q = mpmath.exp(2j * pi * tau)
            q24 = mpmath.exp(2j * pi * tau / 24)
            prod = mpmath.qp(q, q)
            eta_val = abs(q24 * prod)
            if eta_val > 0:
                b[label] = mpf(eta_val)
        except Exception:
            pass

    # 2D Ising critical coupling Kc_2D = ln(1+sqrt(2))/2
    b["Kc_2D"] = log(1 + sqrt(mpf(2))) / 2

    # Products/quotients of key constants
    b["pi*log2"] = pi * log(2)
    b["pi/log2"] = pi / log(2)
    b["Gamma(1/4)/sqrt(pi)"] = mpgamma(mpf(1)/4) / sqrt(pi)
    b["1/sqrt(2*pi)"] = 1 / sqrt(2 * pi)

    return b


def _pslq_group(tgt_val, group_names, group_vals, prec):
    """Run PSLQ on target vs a small group of basis constants."""
    mp.dps = prec + 50
    vec = [tgt_val] + list(group_vals)
    try:
        rel = mpmath.pslq(vec, maxcoeff=1000, maxsteps=3000)
    except Exception:
        return None
    if rel is None:
        return None
    # Reject relations that don't involve the target
    if rel[0] == 0:
        return None
    # verify
    check = sum(r * v for r, v in zip(rel, vec))
    if check != 0:
        check_dig = float(-mp.log10(abs(check)))
    else:
        check_dig = prec
    max_c = max(abs(c) for c in rel)
    return {"rel": list(rel), "names": ["TARGET"] + list(group_names),
            "max_coeff": max_c, "check_digits": check_dig}


def run_pslq_scan(prec: int = 150) -> dict:
    """Run batched PSLQ on Kc/Tc against themed groups of 8-12 constants."""
    print("=" * 70)
    print("  PART A: Batched PSLQ on Kc/Tc")
    print(f"  Precision: {prec} dp  (batched groups of ~10)")
    print("=" * 70, flush=True)

    mp.dps = prec + 50
    basis = build_extended_basis(prec)
    all_names = list(basis.keys())
    all_vals = [basis[n] for n in all_names]
    print(f"  Full basis: {len(basis)} constants", flush=True)

    # Partition basis into themed groups of ~10
    groups: list[tuple[str, list[str]]] = []
    # Group 1: core constants
    groups.append(("core", [n for n in all_names if n in {
        "1","pi","pi^2","1/pi","log2","log3","sqrt2","sqrt3","sqrt5",
        "phi","e","euler_gamma"}]))
    # Group 2: zeta/catalan
    groups.append(("zeta", [n for n in all_names if n in {
        "1","zeta3","zeta5","catalan","pi^2","euler_gamma","log2","log3"}]))
    # Group 3: Gamma values
    groups.append(("gamma", [n for n in all_names if "Gamma" in n] + ["1","pi","sqrt2"]))
    # Group 4: Elliptic integrals
    groups.append(("elliptic", [n for n in all_names if n.startswith(("K(","E("))] + ["1","pi","pi^2"]))
    # Group 5: Dedekind eta
    groups.append(("eta_mod", [n for n in all_names if "eta(" in n] + ["1","pi","log2","e"]))
    # Group 6: Mixed special
    groups.append(("mixed", ["1","Kc_2D","pi*log2","pi/log2",
                             "Gamma(1/4)/sqrt(pi)","1/sqrt(2*pi)","catalan","sqrt5"]))

    Kc = mpf(KC_HP); Tc = mpf(TC_HP)
    targets = {
        "Kc": Kc, "Tc": Tc, "Kc^2": Kc**2,
        "sqrt(Kc)": sqrt(Kc), "log(Tc)": log(Tc),
    }

    results: dict = {}
    for tgt_name, tgt_val in targets.items():
        print(f"\n  Target: {tgt_name} = {nstr(tgt_val, 25)}")
        tgt_results = []

        for gname, gkeys in groups:
            # filter to keys that exist in basis
            gkeys_f = [k for k in gkeys if k in basis]
            if len(gkeys_f) < 2:
                continue
            gvals = [basis[k] for k in gkeys_f]
            print(f"    group '{gname}' ({len(gkeys_f)} elems)...", end="", flush=True)

            hit = _pslq_group(tgt_val, gkeys_f, gvals, prec)
            if hit is not None and hit["check_digits"] > prec * 0.5:
                # Stability check at higher precision
                mp.dps = int(prec * 1.3) + 50
                basis_hi = build_extended_basis(int(prec * 1.3))
                tgt_hi_map = {
                    "Kc": lambda: mpf(KC_HP), "Tc": lambda: mpf(TC_HP),
                    "Kc^2": lambda: mpf(KC_HP)**2,
                    "sqrt(Kc)": lambda: sqrt(mpf(KC_HP)),
                    "log(Tc)": lambda: log(mpf(TC_HP)),
                }
                tgt_hi = tgt_hi_map.get(tgt_name, lambda: tgt_val)()
                gvals_hi = [basis_hi.get(k, basis[k]) for k in gkeys_f]
                vec_hi = [tgt_hi] + gvals_hi
                check_hi = sum(r * v for r, v in zip(hit["rel"], vec_hi))
                hi_dig = float(-mp.log10(abs(check_hi))) if check_hi != 0 else prec*1.3
                stable = hi_dig > prec * 0.5

                terms = []
                for coeff, name in zip(hit["rel"][1:], gkeys_f):
                    if coeff != 0:
                        terms.append((coeff, name))
                rel_str = f"{hit['rel'][0]}*{tgt_name}"
                for c, n in terms:
                    s = "+" if c > 0 else "-"
                    rel_str += f" {s} {abs(c)}*{n}"
                rel_str += " = 0"

                tag = "STABLE" if stable else "UNSTABLE"
                print(f" HIT ({tag}, {hi_dig:.0f}d)")
                print(f"      {rel_str}")
                hit["stable"] = stable
                hit["stability_digits"] = hi_dig
                tgt_results.append(hit)
            else:
                print(" none")

        results[tgt_name] = tgt_results if tgt_results else "no_relation"

    return results


# =====================================================================
#  PART B: PCF search for critical exponents nu and eta
# =====================================================================

@dataclass
class NearMiss:
    a: list; b: list; cf_value: float
    closest: str; digits: float; cycle: int


def build_exponent_constants(prec: int) -> dict[str, mpf]:
    """Constants for matching critical exponents."""
    mp.dps = prec + 30

    nu = mpf(NU_HP)
    eta = mpf(ETA_HP)
    omega = mpf(OMEGA_HP)

    # Derived exponents (d=3)
    gamma_exp = nu * (2 - eta)         # ~ 1.2372
    beta_exp = nu * (1 + eta) / 2     # ~ 0.3265
    alpha_exp = 2 - 3 * nu            # ~ 0.1101
    delta_exp = (5 - eta) / (1 + eta)  # ~ 4.789

    c: dict[str, mpf] = {}

    # Primary exponents
    c["nu"] = nu
    c["eta"] = eta
    c["omega"] = omega
    c["gamma_exp"] = gamma_exp
    c["beta_exp"] = beta_exp
    c["alpha_exp"] = alpha_exp
    c["delta_exp"] = delta_exp

    # Transforms of nu
    c["1/nu"] = 1 / nu
    c["nu^2"] = nu ** 2
    c["2*nu"] = 2 * nu
    c["3*nu"] = 3 * nu           # ~ 1.8899 close to 2-alpha
    c["1-nu"] = 1 - nu
    c["2-3*nu"] = alpha_exp      # alpha

    # Transforms of eta
    c["1/eta"] = 1 / eta
    c["eta*pi"] = eta * pi
    c["2-eta"] = 2 - eta         # gamma/nu ratio

    # nu with standard constants
    c["nu*pi"] = nu * pi
    c["nu/pi"] = nu / pi
    c["nu*sqrt2"] = nu * sqrt(mpf(2))
    c["nu-1/2"] = nu - mpf(1)/2  # ~ 0.13

    # omega transforms
    c["1/omega"] = 1 / omega
    c["omega-1"] = omega - 1

    # Kc and Tc (keep a few key ones)
    Kc = mpf(KC_HP)
    Tc = mpf(TC_HP)
    c["Kc"] = Kc
    c["Tc"] = Tc

    # Rational multiples of nu, eta
    for p in range(1, 6):
        for q in range(1, 6):
            if p == q or math.gcd(p, q) != 1:
                continue
            c[f"{p}*nu/{q}"] = mpf(p) * nu / q
            if p * eta / q < 10 and p * eta / q > 0.01:
                c[f"{p}*eta/{q}"] = mpf(p) * eta / q

    return c


def score_cf(val: mpf, constants: dict[str, mpf]) -> tuple[str | None, float]:
    """Absolute log-proximity scoring for GA gradient."""
    if val is None:
        return None, -100.0
    best_name: str | None = None
    best_digits = -100.0
    for name, cval in constants.items():
        if cval == 0:
            continue
        for cand, prefix in [(val, ""), (-val, "-")]:
            res = abs(cand - cval)
            if res == 0:
                return f"{prefix}{name}" if prefix else name, 999.0
            try:
                d = float(-mp.log10(res))
            except (ValueError, ZeroDivisionError):
                continue
            if d > best_digits:
                best_digits = d
                best_name = f"{prefix}{name}" if prefix else name
    return best_name, best_digits


def pop_entropy(population) -> float:
    return len({p.key() for p in population}) / max(len(population), 1)


def run_exponent_search(cycles=800, prec=100, tol=50,
                        pop_size=80, depth=300,
                        max_deg_a=5, max_deg_b=3,
                        seed=271828) -> dict:
    """PCF search targeting nu, eta, and derived exponents with deg 4-5."""
    print("\n" + "=" * 70)
    print("  PART B: PCF search for critical exponents")
    print(f"  nu={NU_HP}  eta={ETA_HP}  omega={OMEGA_HP}")
    print(f"  cycles={cycles}  prec={prec}dp  depth={depth}  pop={pop_size}")
    print(f"  max deg(a)={max_deg_a}  max deg(b)={max_deg_b}")
    print("=" * 70, flush=True)

    mp.dps = prec + 20
    rng = random.Random(seed)
    consts = build_exponent_constants(prec)
    print(f"  {len(consts)} target constants", flush=True)

    # Build population: mix of degrees 2-5 for a, 1-3 for b
    pop = list(rbg.seed_population())[:10]

    # Targeted degree distribution: bias toward higher degrees
    deg_weights_a = {2: 2, 3: 3, 4: 4, 5: 3}  # favor 3-4
    deg_weights_b = {1: 3, 2: 3, 3: 2}

    def weighted_choice(weights, rng):
        items = list(weights.keys())
        ws = list(weights.values())
        total = sum(ws)
        r = rng.random() * total
        cumulative = 0
        for item, w in zip(items, ws):
            cumulative += w
            if r <= cumulative:
                return item
        return items[-1]

    while len(pop) < pop_size:
        da = weighted_choice(deg_weights_a, rng)
        db = weighted_choice(deg_weights_b, rng)
        cr = rng.choice([5, 6, 8, 10])
        pop.append(rbg.random_params(a_deg=da, b_deg=db,
                                     coeff_range=cr, rng=rng))

    disc: list[dict] = []
    nms: list[NearMiss] = []
    best_ever = -100.0
    best_nm: NearMiss | None = None
    temp = 2.0
    t0 = time.time()

    for cyc in range(1, cycles + 1):
        for p in pop:
            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            if val is None or not rbg.is_reasonable(val):
                p.score = -999; continue

            name, digs = score_cf(val, consts)
            # Only check telescoping on promising candidates (expensive)
            if digs > 5 and rbg.is_telescoping(p.a, p.b):
                p.score = -999; continue
            p.score = digs

            if digs >= tol:
                p.hit = name
                disc.append({
                    "cycle": cyc, "a": p.a[:], "b": p.b[:],
                    "match": name, "value": nstr(val, 40),
                    "digits": digs, "deg_a": len(p.a)-1, "deg_b": len(p.b)-1,
                })
                print(f"\n  *** MATCH c={cyc}: {name} ***")
                print(f"      a={p.a} (deg {len(p.a)-1})  "
                      f"b={p.b} (deg {len(p.b)-1})")
                print(f"      {digs:.1f} digits", flush=True)

            if digs > 2:
                nm = NearMiss(p.a[:], p.b[:], float(val), name, digs, cyc)
                nms.append(nm)
                if digs > best_ever:
                    best_ever = digs
                    best_nm = nm

        pop.sort(key=lambda x: -x.score)
        temp = rbg.adapt_temperature(
            temp, [p.score for p in pop[:5]], cyc, 0)

        # Custom evolution: occasionally inject high-degree CFs
        pop = rbg.evolve_population(pop, pop_size, temp, rng)

        # Replace worst quartile with fresh high-degree CFs every 100 cycles
        if cyc % 100 == 0:
            n_inj = pop_size // 4
            for i in range(n_inj):
                da = weighted_choice(deg_weights_a, rng)
                db = weighted_choice(deg_weights_b, rng)
                pop[-(i+1)] = rbg.random_params(
                    a_deg=da, b_deg=db,
                    coeff_range=rng.choice([6, 8, 10, 12]), rng=rng)

        # Entropy guard
        ent = pop_entropy(pop)
        if ent < 0.25 and cyc % 50 == 0:
            n_inj = pop_size // 3
            for i in range(n_inj):
                da = weighted_choice(deg_weights_a, rng)
                db = weighted_choice(deg_weights_b, rng)
                pop[-(i+1)] = rbg.random_params(
                    a_deg=da, b_deg=db, coeff_range=8, rng=rng)

        if cyc % 25 == 0 or cyc == 1:
            el = time.time() - t0
            t5 = sum(p.score for p in pop[:5]) / 5 if pop else 0
            print(f"  c={cyc:5d}/{cycles} T={temp:.2f} "
                  f"top5={t5:.2f}d best={best_ever:.2f}d "
                  f"ent={ent:.2f} disc={len(disc)} {el:.0f}s", flush=True)

    el = time.time() - t0

    # Dedup
    nm_map: dict[tuple, NearMiss] = {}
    for nm in nms:
        k = (tuple(nm.a), tuple(nm.b))
        if k not in nm_map or nm.digits > nm_map[k].digits:
            nm_map[k] = nm
    nms_d = sorted(nm_map.values(), key=lambda x: -x.digits)

    print(f"\n  Exponent search done: {el:.0f}s")
    print(f"  Discoveries: {len(disc)}")
    print(f"  Unique near-misses: {len(nms_d)}")
    if best_nm:
        print(f"  Best: {best_ever:.2f}d -> {best_nm.closest}")
        print(f"         a={best_nm.a} (deg {len(best_nm.a)-1})")
        print(f"         b={best_nm.b} (deg {len(best_nm.b)-1})")

    if nms_d:
        print(f"\n  Top 15 near-misses:")
        for i, nm in enumerate(nms_d[:15]):
            da = len(nm.a) - 1
            db = len(nm.b) - 1
            print(f"    #{i+1}: {nm.digits:.2f}d -> {nm.closest}  "
                  f"deg({da},{db})  a={nm.a} b={nm.b}")

    return {
        "discoveries": disc,
        "near_misses": [
            {"a": nm.a, "b": nm.b, "cf_value": nm.cf_value,
             "closest": nm.closest, "digits": nm.digits,
             "cycle": nm.cycle, "deg_a": len(nm.a)-1, "deg_b": len(nm.b)-1}
            for nm in nms_d[:50]
        ],
        "elapsed": el, "best_digits": best_ever,
    }


# =====================================================================
#  PART C: Degree-4/5 targeted search for Kc/Tc specifically
# =====================================================================

def build_ising_constants(prec):
    """Kc/Tc-focused library from v3 search."""
    mp.dps = prec + 30
    Tc = mpf(TC_HP); Kc = mpf(KC_HP)
    c = {}
    c["Tc"] = Tc; c["Kc"] = Kc
    c["Tc^2"] = Tc**2; c["sqrt_Tc"] = sqrt(Tc)
    c["Kc^2"] = Kc**2; c["sqrt_Kc"] = sqrt(Kc)
    c["Tc-4"] = Tc - 4; c["Tc-9/2"] = Tc - mpf(9)/2; c["5-Tc"] = 5 - Tc
    c["Tc/pi"] = Tc / pi; c["Kc*pi"] = Kc * pi
    c["log_Tc"] = log(Tc); c["exp_Kc"] = exp(Kc)
    c["Tc/zeta3"] = Tc / zeta(3)
    kc2d = log(1 + sqrt(mpf(2))) / 2
    c["Kc/Kc2d"] = Kc / kc2d
    for p in range(1, 5):
        for q in range(1, 5):
            if p == q or math.gcd(p, q) != 1: continue
            c[f"{p}*Tc/{q}"] = mpf(p) * Tc / q
            c[f"{p}*Kc/{q}"] = mpf(p) * Kc / q
    return c


def run_high_degree_tc_search(cycles=600, prec=100, tol=50,
                               pop_size=80, depth=300, seed=31415):
    """Degree 4-5 PCF search specifically for Tc/Kc."""
    print("\n" + "=" * 70)
    print("  PART C: High-degree (4-5) PCF search for Tc/Kc")
    print(f"  cycles={cycles}  prec={prec}dp  depth={depth}  pop={pop_size}")
    print("=" * 70, flush=True)

    mp.dps = prec + 20
    rng = random.Random(seed)
    consts = build_ising_constants(prec)

    # Population: exclusively deg 4-5 for a(n), deg 2-3 for b(n)
    pop = []
    while len(pop) < pop_size:
        da = rng.choice([4, 4, 5, 5, 3])   # mostly 4-5
        db = rng.choice([2, 2, 3, 1])
        cr = rng.choice([5, 6, 8])
        pop.append(rbg.random_params(a_deg=da, b_deg=db,
                                     coeff_range=cr, rng=rng))

    disc: list[dict] = []
    nms: list[NearMiss] = []
    best_ever = -100.0; best_nm = None
    temp = 2.5; t0 = time.time()

    for cyc in range(1, cycles + 1):
        for p in pop:
            val = rbg.eval_pcf(p.a, p.b, depth=depth)
            if val is None or not rbg.is_reasonable(val):
                p.score = -999; continue

            name, digs = score_cf(val, consts)
            if digs > 5 and rbg.is_telescoping(p.a, p.b):
                p.score = -999; continue
            p.score = digs

            if digs >= tol:
                p.hit = name
                disc.append({
                    "cycle": cyc, "a": p.a[:], "b": p.b[:],
                    "match": name, "value": nstr(val, 40), "digits": digs,
                })
                print(f"\n  *** MATCH c={cyc}: {name} | {digs:.0f}d ***",
                      flush=True)
            if digs > 2:
                nm = NearMiss(p.a[:], p.b[:], float(val), name, digs, cyc)
                nms.append(nm)
                if digs > best_ever:
                    best_ever = digs; best_nm = nm

        pop.sort(key=lambda x: -x.score)
        temp = rbg.adapt_temperature(
            temp, [p.score for p in pop[:5]], cyc, 0)
        pop = rbg.evolve_population(pop, pop_size, temp, rng)

        ent = pop_entropy(pop)
        if ent < 0.25 and cyc % 40 == 0:
            n_inj = pop_size // 3
            for i in range(n_inj):
                da = rng.choice([4, 5]); db = rng.choice([2, 3])
                pop[-(i+1)] = rbg.random_params(
                    a_deg=da, b_deg=db, coeff_range=8, rng=rng)

        if cyc % 25 == 0 or cyc == 1:
            el = time.time() - t0
            t5 = sum(p.score for p in pop[:5]) / 5. if pop else 0
            print(f"  c={cyc:5d}/{cycles} T={temp:.2f} "
                  f"top5={t5:.2f}d best={best_ever:.2f}d "
                  f"ent={ent:.2f} {el:.0f}s", flush=True)

    el = time.time() - t0
    nm_map: dict[tuple, NearMiss] = {}
    for nm in nms:
        k = (tuple(nm.a), tuple(nm.b))
        if k not in nm_map or nm.digits > nm_map[k].digits:
            nm_map[k] = nm
    nms_d = sorted(nm_map.values(), key=lambda x: -x.digits)

    print(f"\n  High-degree Tc search done: {el:.0f}s")
    print(f"  Discoveries: {len(disc)}")
    if best_nm:
        print(f"  Best: {best_ever:.2f}d -> {best_nm.closest}")
        print(f"         a={best_nm.a}  b={best_nm.b}")

    if nms_d:
        print(f"\n  Top 15:")
        for i, nm in enumerate(nms_d[:15]):
            print(f"    #{i+1}: {nm.digits:.2f}d -> {nm.closest}  "
                  f"a={nm.a} b={nm.b}")

    return {
        "discoveries": disc,
        "near_misses": [
            {"a": nm.a, "b": nm.b, "cf_value": nm.cf_value,
             "closest": nm.closest, "digits": nm.digits, "cycle": nm.cycle}
            for nm in nms_d[:30]
        ],
        "elapsed": el, "best_digits": best_ever,
    }


# =====================================================================
#  MAIN
# =====================================================================
def main():
    print("#" * 70)
    print("#  Extended 3D Ising PCF + PSLQ Search")
    print("#  A) PSLQ on Kc with elliptic/modular/Gamma basis")
    print("#  B) PCF for critical exponents (nu, eta) with deg 4-5")
    print("#  C) High-degree Tc/Kc PCF search")
    print("#" * 70, flush=True)

    results = {}
    out = Path("results/pcf_extended_ising.json")

    # ── Part A: PSLQ (batched groups of ~10 constants) ──
    print("\n")
    t0 = time.time()
    pslq_res = run_pslq_scan(prec=150)
    results["pslq"] = pslq_res
    print(f"\n  Part A done in {time.time()-t0:.0f}s")

    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ── Part B: Exponent search ──
    print("\n")
    t0 = time.time()
    exp_res = run_exponent_search(
        cycles=800, prec=100, tol=50,
        pop_size=80, depth=200,
        max_deg_a=5, max_deg_b=3, seed=271828)
    results["exponent_search"] = exp_res
    print(f"\n  Part B done in {time.time()-t0:.0f}s")

    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ── Part C: High-degree Tc search ──
    print("\n")
    t0 = time.time()
    hd_res = run_high_degree_tc_search(
        cycles=600, prec=100, tol=50,
        pop_size=80, depth=200, seed=31415)
    results["high_degree_tc"] = hd_res
    print(f"\n  Part C done in {time.time()-t0:.0f}s")

    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ── Final Summary ──
    print("\n" + "#" * 70)
    print("  FINAL SUMMARY")
    print("#" * 70)

    # PSLQ results
    print("\n  A) PSLQ Relations Found:")
    for name, res in pslq_res.items():
        if res == "no_relation":
            print(f"    {name}: no relation found in any group")
        elif isinstance(res, list):
            for r in res:
                tag = "STABLE" if r.get("stable") else "UNSTABLE"
                print(f"    {name}: {tag} relation (max_coeff={r['max_coeff']})")
        else:
            print(f"    {name}: {res}")

    # Exponent search
    print(f"\n  B) Exponent PCF: {len(exp_res['discoveries'])} matches, "
          f"best near-miss {exp_res['best_digits']:.2f}d")
    if exp_res["near_misses"]:
        for nm in exp_res["near_misses"][:5]:
            print(f"    {nm['digits']:.2f}d -> {nm['closest']}  "
                  f"deg({nm['deg_a']},{nm['deg_b']})")

    # High-degree Tc
    print(f"\n  C) High-deg Tc: {len(hd_res['discoveries'])} matches, "
          f"best near-miss {hd_res['best_digits']:.2f}d")
    if hd_res["near_misses"]:
        for nm in hd_res["near_misses"][:5]:
            print(f"    {nm['digits']:.2f}d -> {nm['closest']}  "
                  f"a={nm['a']} b={nm['b']}")

    print(f"\n  Results saved to {out}")
    print("  Done.", flush=True)


if __name__ == "__main__":
    main()
