"""
Erdős–Straus Conjecture Problem Domain
========================================
The conjecture states that for every integer n ≥ 2,
4/n can be written as 4/n = 1/a + 1/b + 1/c
where a, b, c are positive integers.

This module provides:
  - Egyptian fraction decomposition generators
  - Construction method classification
  - Coverage analysis (which n are solved by which method)
  - General family discovery
  - Residue class analysis
"""

import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any, Set


class EgyptianFractionDecomposition:
    """A single decomposition 4/n = 1/a + 1/b + 1/c."""

    __slots__ = ('n', 'a', 'b', 'c', 'method')

    def __init__(self, n: int, a: int, b: int, c: int, method: str = 'brute'):
        self.n = n
        self.a, self.b, self.c = sorted([a, b, c])
        self.method = method

    def verify(self) -> bool:
        """Verify 4/n = 1/a + 1/b + 1/c exactly using integer arithmetic."""
        if self.a <= 0 or self.b <= 0 or self.c <= 0:
            return False
        # 4/n = 1/a + 1/b + 1/c
        # 4*a*b*c = n*(b*c + a*c + a*b)
        lhs = 4 * self.a * self.b * self.c
        rhs = self.n * (self.b * self.c + self.a * self.c + self.a * self.b)
        return lhs == rhs

    @property
    def max_denominator(self) -> int:
        return self.c

    def __repr__(self):
        return f"4/{self.n} = 1/{self.a} + 1/{self.b} + 1/{self.c} [{self.method}]"


class ErdosStrausAnalyzer:
    """Comprehensive analyzer for the Erdős–Straus conjecture."""

    def __init__(self, max_n: int = 0):
        self.decompositions: Dict[int, List[EgyptianFractionDecomposition]] = defaultdict(list)
        self.coverage: Dict[str, Set[int]] = defaultdict(set)  # method -> covered n
        self.families: List[Dict[str, Any]] = []
        self.unsolved_n: Set[int] = set()
        # Smallest-prime-factor sieve for fast factorization
        self._spf: List[int] = []
        if max_n > 0:
            self._build_sieve(max_n)

    def _build_sieve(self, limit: int):
        """Build smallest-prime-factor sieve up to limit."""
        self._spf = list(range(limit + 1))  # spf[i] = i initially
        for i in range(2, int(limit ** 0.5) + 1):
            if self._spf[i] == i:  # i is prime
                for j in range(i * i, limit + 1, i):
                    if self._spf[j] == j:
                        self._spf[j] = i

    def _fast_factorize(self, n: int) -> List[tuple]:
        """Factorize using sieve if available, else trial division."""
        if n <= 1:
            return []
        if self._spf and n < len(self._spf):
            factors = {}
            while n > 1:
                p = self._spf[n]
                factors[p] = factors.get(p, 0) + 1
                n //= p
            return sorted(factors.items())
        # Fallback: trial division
        factors = []
        d = 2
        while d * d <= n:
            if n % d == 0:
                exp = 0
                while n % d == 0:
                    n //= d
                    exp += 1
                factors.append((d, exp))
            d += 1
        if n > 1:
            factors.append((n, 1))
        return factors

    def find_decompositions_brute(self, n: int, max_denom: int = 0) -> List[EgyptianFractionDecomposition]:
        """Find all decompositions by bounded search.
        
        4/n = 1/a + 1/b + 1/c with a ≤ b ≤ c.
        Since 1/a ≤ 4/n ≤ 3/a, we have a ≥ ceil(n/4) and a ≤ ceil(3n/4).
        """
        if max_denom == 0:
            max_denom = n * n  # reasonable bound

        results = []
        a_min = max(1, math.ceil(n / 4))
        a_max = math.ceil(3 * n / 4)

        for a in range(a_min, a_max + 1):
            # 4/n - 1/a = (4a - n) / (na)
            num = 4 * a - n
            den = n * a
            if num <= 0:
                continue

            # Need 1/b + 1/c = num/den with b ≤ c
            # b ≥ ceil(den/num) (from 1/b ≤ num/den)
            # b ≤ 2*den/num (from 1/b ≥ (num/den)/2)
            b_min = max(a, math.ceil(den / num))
            b_max = min(max_denom, 2 * den // num + 1)

            for b in range(b_min, b_max + 1):
                # 1/c = num/den - 1/b = (num*b - den) / (den*b)
                c_num = num * b - den
                c_den = den * b
                if c_num <= 0:
                    continue
                if c_den % c_num == 0:
                    c = c_den // c_num
                    if c >= b and c <= max_denom:
                        dec = EgyptianFractionDecomposition(n, a, b, c, 'brute_force')
                        if dec.verify():
                            results.append(dec)

        return results

    def apply_parametric_families(self, n: int) -> List[EgyptianFractionDecomposition]:
        """Apply known parametric construction families."""
        results = []

        # Family 1: n ≡ 0 (mod 4) → 4/n = 1/(n/4) + ... trivial
        if n % 4 == 0:
            k = n // 4
            # 4/n = 4/(4k) = 1/k = 1/k + 1/(k+1) + 1/(k(k+1)) ... various
            # Simplest: 1/(k) + 1/(k+1) + 1/(k(k+1))
            a, b = k, k + 1
            c = k * (k + 1)
            dec = EgyptianFractionDecomposition(n, a, b, c, 'family_mod4_eq0')
            if dec.verify():
                results.append(dec)
                self.coverage['mod4_eq0'].add(n)

        # Family 2: n ≡ 2 (mod 4)
        if n % 4 == 2:
            # 4/n = 2/(n/2). Let m = n/2 (odd).
            # 2/m = 1/m + 1/m ... but need 3 unit fractions for 4/n
            # Try: 4/n = 1/(ceil(n/4)) + remainder
            m = n // 2
            a = m
            # 4/n - 1/m = 4/n - 2/n = 2/n = 1/b + 1/c
            # 2/n: b = n, c = n → 1/n + 1/n = 2/n
            dec = EgyptianFractionDecomposition(n, m, n, n, 'family_mod4_eq2')
            if dec.verify():
                results.append(dec)
                self.coverage['mod4_eq2'].add(n)

        # Family 3: n ≡ 3 (mod 4) — Schinzel-type
        if n % 4 == 3:
            # 4/n = 1/((n+1)/4) + ... if n ≡ 3 mod 4 then (n+1)/4 is integer
            k = (n + 1) // 4
            # 4/n - 1/k = (4k - n)/(nk)
            num = 4 * k - n
            den = n * k
            if num > 0 and den % num == 0:
                b = den // num
                # 4/n = 1/k + 1/b + 0? No, need 3 terms.
                # Split 1/b into 1/(b+1) + 1/(b(b+1))
                c = b * (b + 1)
                b_new = b + 1
                dec = EgyptianFractionDecomposition(n, k, b_new, c, 'family_mod4_eq3_schinzel')
                if dec.verify():
                    results.append(dec)
                    self.coverage['mod4_eq3_schinzel'].add(n)

        # Family 4: n = p prime, try p-based constructions
        if self._is_prime(n):
            a = math.ceil(n / 4)
            dec = self._divisor_decompose(n, a, 'family_prime')
            if dec:
                results.append(dec)
                self.coverage['prime_construction'].add(n)

        # Family 5: Modular constructions for n ≡ r (mod 12)
        r12 = n % 12
        if r12 == 1 and (n + 3) % 4 == 0:
            a = (n + 3) // 4
            dec = self._divisor_decompose(n, a, f'family_mod12_{r12}')
            if dec:
                results.append(dec)
                self.coverage[f'mod12_{r12}'].add(n)

        # Family 6: Divisor-based fast decomposition (replaces slow greedy)
        # Uses identity: (num*b - den)(num*c - den) = den² to enumerate
        # solutions via divisors of den². Cap at 200 a-values for speed.
        if not results:
            a_start = math.ceil(n / 4)
            a_end = min(n + 1, a_start + 200)
            for a in range(a_start, a_end):
                dec = self._divisor_decompose(n, a, 'divisor_fast')
                if dec:
                    results.append(dec)
                    self.coverage['divisor_fast'].add(n)
                    break

        return results

    def analyze_coverage(self, max_n: int, progress_every: int = 0) -> Dict[str, Any]:
        """Run all construction methods and analyze coverage.
        
        Args:
            max_n: Upper bound for n values to test.
            progress_every: Print progress every N values (0 = no progress).
        """
        all_covered = set()
        method_stats = defaultdict(int)

        for n in range(2, max_n + 1):
            if progress_every > 0 and n % progress_every == 0:
                pct = len(all_covered) / max(1, n - 2) * 100
                print(f"    E-S coverage: n={n:,}/{max_n:,} "
                      f"({pct:.2f}% covered, {len(self.unsolved_n)} unsolved)")

            decs = self.apply_parametric_families(n)
            if decs:
                self.decompositions[n] = decs
                all_covered.add(n)
                for d in decs:
                    method_stats[d.method] += 1
            else:
                # Extended divisor search: try more a-values
                found = False
                a_start = math.ceil(n / 4)
                for a in range(a_start + 200, min(n + 1, a_start + 1000)):
                    dec = self._divisor_decompose(n, a, 'divisor_extended')
                    if dec:
                        self.decompositions[n] = [dec]
                        all_covered.add(n)
                        method_stats['divisor_extended'] += 1
                        found = True
                        break
                if not found:
                    self.unsolved_n.add(n)

        return {
            'range': (2, max_n),
            'total': max_n - 1,
            'covered': len(all_covered),
            'uncovered': len(self.unsolved_n),
            'coverage_pct': len(all_covered) / (max_n - 1) * 100,
            'method_stats': dict(method_stats),
            'unsolved_examples': sorted(list(self.unsolved_n))[:200],
            'unsolved_primes': sorted([n for n in self.unsolved_n if self._is_prime(n)])[:200],
        }

    def discover_new_families(self) -> List[Dict[str, Any]]:
        """Analyze existing decompositions to discover new parametric families.
        
        Look for patterns: for which residue classes do specific constructions work?
        """
        families = []

        # Analyze by modulus m
        for m in [3, 4, 5, 6, 7, 8, 9, 12, 16, 20, 24]:
            by_residue = defaultdict(list)
            for n, decs in self.decompositions.items():
                if decs:
                    d = decs[0]
                    by_residue[n % m].append({
                        'n': n,
                        'a_ratio': d.a / n if n > 0 else 0,
                        'b_ratio': d.b / n if n > 0 else 0,
                        'c_ratio': d.c / n if n > 0 else 0,
                        'method': d.method
                    })

            for r, entries in by_residue.items():
                if len(entries) >= 5:
                    # Check if a/n ratios cluster
                    a_ratios = [e['a_ratio'] for e in entries]
                    mean_a = sum(a_ratios) / len(a_ratios)
                    var_a = sum((x - mean_a) ** 2 for x in a_ratios) / len(a_ratios)

                    if var_a < 0.01:  # tight clustering
                        families.append({
                            'modulus': m,
                            'residue': r,
                            'count': len(entries),
                            'a_over_n': mean_a,
                            'a_over_n_var': var_a,
                            'suggested_a': f'ceil({mean_a:.4f} * n)',
                            'description': f'For n ≡ {r} (mod {m}): a ≈ {mean_a:.4f}·n'
                        })

        self.families = families
        return families

    def classify_prime_difficulty(self, max_p: int = 10000) -> Dict[str, Any]:
        """Classify primes by difficulty of finding decompositions.
        
        Primes are the hardest cases for Erdős–Straus.
        """
        easy_primes = []  # found with parametric family
        medium_primes = []  # found with brute force small bound
        hard_primes = []  # need large denominators

        for p in range(2, max_p + 1):
            if not self._is_prime(p):
                continue
            decs = self.apply_parametric_families(p)
            if decs:
                easy_primes.append(p)
            else:
                decs = self.find_decompositions_brute(p, max_denom=p * 10)
                if decs:
                    medium_primes.append(p)
                    self.decompositions[p] = decs
                else:
                    hard_primes.append(p)

        return {
            'easy': len(easy_primes),
            'medium': len(medium_primes),
            'hard': len(hard_primes),
            'hard_primes': hard_primes[:100],
            'hard_residues_mod24': defaultdict(int,
                Counter(p % 24 for p in hard_primes)) if hard_primes else {}
        }

    def _divisor_decompose(self, n: int, a: int,
                           method: str) -> Optional[EgyptianFractionDecomposition]:
        """Fast decomposition via divisor enumeration.

        Uses the identity: for 1/b + 1/c = num/den,
          (num*b - den)(num*c - den) = den²
        Factorizes n and a separately (sieve range) then combines.
        """
        num = 4 * a - n
        den = n * a
        if num <= 0:
            return None

        g = math.gcd(num, den)
        num_r = num // g
        den_r = den // g
        target = den_r * den_r

        # Congruence filter: u ≡ (-den_r) mod num_r
        req = (-den_r) % num_r

        # Factorize den_r = n*a/g by factorizing n and a separately (sieve range)
        # then combining and dividing out gcd factors
        factors_na = self._combine_factors(
            self._fast_factorize(n), self._fast_factorize(a))
        factors_g = self._fast_factorize(g)
        factors_den = self._subtract_factors(factors_na, factors_g)
        # Square the exponents for den_r²
        factors_sq = [(p, 2 * e) for p, e in factors_den]

        divs = [1]
        for p, e in factors_sq:
            new_divs = []
            pe = 1
            for _ in range(e + 1):
                for d in divs:
                    new_divs.append(d * pe)
                pe *= p
            divs = new_divs
        divs.sort()

        for u in divs:
            if u % num_r != req:
                continue
            v = target // u
            if (den_r + v) % num_r != 0:
                continue
            b = (den_r + u) // num_r
            c = (den_r + v) // num_r
            if b > 0 and c > 0:
                dec = EgyptianFractionDecomposition(n, a, b, c, method)
                if dec.verify():
                    return dec

        return None

    @staticmethod
    def _combine_factors(f1: List[tuple], f2: List[tuple]) -> List[tuple]:
        """Multiply factorizations: combine (prime, exp) lists."""
        d = dict(f1)
        for p, e in f2:
            d[p] = d.get(p, 0) + e
        return sorted(d.items())

    @staticmethod
    def _subtract_factors(f_num: List[tuple], f_den: List[tuple]) -> List[tuple]:
        """Divide factorizations: subtract exponents."""
        d = dict(f_num)
        for p, e in f_den:
            d[p] = d.get(p, 0) - e
            if d[p] <= 0:
                del d[p]
        return sorted(d.items())

    def _is_prime(self, n: int) -> bool:
        if n < 2:
            return False
        if self._spf and n < len(self._spf):
            return self._spf[n] == n  # n is prime iff its smallest factor is itself
        if n < 4:
            return True
        if n % 2 == 0 or n % 3 == 0:
            return False
        i = 5
        while i * i <= n:
            if n % i == 0 or n % (i + 2) == 0:
                return False
            i += 6
        return True

    @staticmethod
    def _divisors(n: int) -> List[int]:
        divs = []
        for i in range(1, int(math.sqrt(n)) + 1):
            if n % i == 0:
                divs.append(i)
                if i != n // i:
                    divs.append(n // i)
        return sorted(divs)

    def generate_report(self) -> Dict[str, Any]:
        return {
            'total_decompositions': sum(len(v) for v in self.decompositions.values()),
            'n_covered': len(self.decompositions),
            'n_unsolved': len(self.unsolved_n),
            'families_discovered': len(self.families),
            'coverage_methods': {k: len(v) for k, v in self.coverage.items()},
        }


# Utility: import Counter at module level
from collections import Counter
