"""
Collatz Conjecture Problem Domain
==================================
The Collatz conjecture states that for any positive integer n,
the sequence n -> n/2 (if even), n -> 3n+1 (if odd) always reaches 1.

This module provides:
  - Orbit computation and classification
  - Reverse tree construction  
  - Structural invariant extraction
  - Counterexample search heuristics
  - Modular arithmetic pattern analysis
"""

import math
import random
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple, Any


class CollatzOrbit:
    """Compute and analyze a single Collatz orbit."""

    __slots__ = ('start', 'sequence', 'stopping_time', 'max_value',
                 'odd_count', 'even_count', 'odd_chains')

    def __init__(self, n: int, max_steps: int = 10_000):
        self.start = n
        self.sequence: List[int] = []
        self.stopping_time = 0
        self.max_value = n
        self.odd_count = 0
        self.even_count = 0
        self.odd_chains: List[int] = []  # lengths of consecutive odd steps

        self._compute(n, max_steps)

    def _compute(self, n: int, max_steps: int):
        seq = [n]
        current = n
        odd_chain = 0
        for step in range(max_steps):
            if current == 1:
                self.stopping_time = step
                break
            if current % 2 == 0:
                current = current // 2
                self.even_count += 1
                if odd_chain > 0:
                    self.odd_chains.append(odd_chain)
                    odd_chain = 0
            else:
                current = 3 * current + 1
                self.odd_count += 1
                odd_chain += 1
            seq.append(current)
            if current > self.max_value:
                self.max_value = current
        else:
            self.stopping_time = -1  # did not converge

        if odd_chain > 0:
            self.odd_chains.append(odd_chain)
        self.sequence = seq

    @property
    def glide(self) -> float:
        """Ratio max_value / start — measures orbit excursion."""
        return self.max_value / self.start if self.start > 0 else 0

    @property
    def odd_ratio(self) -> float:
        total = self.odd_count + self.even_count
        return self.odd_count / total if total > 0 else 0

    def mod_signature(self, m: int) -> Tuple[int, ...]:
        """Return the sequence of residues mod m."""
        return tuple(x % m for x in self.sequence[:min(50, len(self.sequence))])


class CollatzAnalyzer:
    """Batch analysis of Collatz orbits for pattern extraction."""

    def __init__(self):
        self.orbits: Dict[int, CollatzOrbit] = {}
        self.patterns: List[Dict[str, Any]] = []
        self.invariants: List[Dict[str, Any]] = []

    def compute_orbits(self, start: int, end: int, max_steps: int = 10_000):
        """Compute orbits for range [start, end)."""
        for n in range(start, end):
            self.orbits[n] = CollatzOrbit(n, max_steps)

    def classify_by_stopping_time(self) -> Dict[int, List[int]]:
        """Group starting values by their stopping time."""
        groups = defaultdict(list)
        for n, orb in self.orbits.items():
            groups[orb.stopping_time].append(n)
        return dict(groups)

    def classify_by_mod(self, m: int) -> Dict[int, Dict[str, float]]:
        """Analyze orbit statistics by residue class mod m."""
        stats = defaultdict(lambda: {'count': 0, 'avg_stop': 0.0,
                                      'avg_glide': 0.0, 'avg_odd_ratio': 0.0})
        for n, orb in self.orbits.items():
            r = n % m
            s = stats[r]
            s['count'] += 1
            s['avg_stop'] += orb.stopping_time
            s['avg_glide'] += orb.glide
            s['avg_odd_ratio'] += orb.odd_ratio

        for r, s in stats.items():
            if s['count'] > 0:
                s['avg_stop'] /= s['count']
                s['avg_glide'] /= s['count']
                s['avg_odd_ratio'] /= s['count']
        return dict(stats)

    def extract_structural_invariants(self) -> List[Dict[str, Any]]:
        """Search for structural invariants across orbits."""
        invariants = []

        # Invariant 1: odd_ratio convergence
        if len(self.orbits) > 100:
            ratios = [o.odd_ratio for o in self.orbits.values()
                      if o.stopping_time > 10]
            if ratios:
                mean_r = sum(ratios) / len(ratios)
                var_r = sum((r - mean_r) ** 2 for r in ratios) / len(ratios)
                # Theoretical prediction: odd_ratio → log(2)/log(3) ≈ 0.6309
                theoretical = math.log(2) / math.log(3)
                invariants.append({
                    'name': 'odd_ratio_convergence',
                    'observed_mean': mean_r,
                    'theoretical': theoretical,
                    'variance': var_r,
                    'deviation': abs(mean_r - theoretical),
                    'description': f'Odd step ratio converges to ln2/ln3 ≈ {theoretical:.4f}'
                })

        # Invariant 2: stopping time ~ log(n) relationship
        if len(self.orbits) > 100:
            pairs = [(math.log(n), o.stopping_time)
                     for n, o in self.orbits.items()
                     if n > 1 and o.stopping_time > 0]
            if len(pairs) > 10:
                xs, ys = zip(*pairs)
                mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
                num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                den = sum((x - mx) ** 2 for x in xs)
                if den > 0:
                    slope = num / den
                    intercept = my - slope * mx
                    # Compute R²
                    ss_res = sum((y - (slope * x + intercept)) ** 2
                                for x, y in zip(xs, ys))
                    ss_tot = sum((y - my) ** 2 for y in ys)
                    r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                    invariants.append({
                        'name': 'stopping_time_log_scaling',
                        'slope': slope,
                        'intercept': intercept,
                        'r_squared': r_sq,
                        'description': f'stopping_time ≈ {slope:.2f} * ln(n) + {intercept:.2f}'
                    })

        # Invariant 3: glide distribution
        glides = [o.glide for o in self.orbits.values() if o.stopping_time > 0]
        if glides:
            log_glides = [math.log(g) for g in glides if g > 0]
            if log_glides:
                mean_lg = sum(log_glides) / len(log_glides)
                invariants.append({
                    'name': 'log_glide_mean',
                    'value': mean_lg,
                    'exp_value': math.exp(mean_lg),
                    'description': f'Mean log-glide = {mean_lg:.4f} (geometric mean ~ {math.exp(mean_lg):.2f})'
                })

        # Invariant 4: mod 6 bias in high-glide orbits
        high_glide = [(n, o) for n, o in self.orbits.items()
                      if o.glide > 10 and o.stopping_time > 0]
        if high_glide:
            mod6 = Counter(n % 6 for n, _ in high_glide)
            total = sum(mod6.values())
            invariants.append({
                'name': 'high_glide_mod6_bias',
                'distribution': {k: v / total for k, v in sorted(mod6.items())},
                'description': 'Residue distribution mod 6 of high-glide orbits'
            })

        self.invariants = invariants
        return invariants

    def build_reverse_tree(self, root: int = 1, depth: int = 20) -> Dict[int, List[int]]:
        """Build the reverse Collatz tree from root upward.
        
        Reverse operations: n -> 2n (always), n -> (n-1)/3 (if (n-1) mod 3 == 0 and (n-1)/3 is odd)
        """
        tree = defaultdict(list)
        frontier = {root}
        visited = {root}

        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                # Always: n -> 2n
                child_even = 2 * n
                tree[n].append(child_even)
                if child_even not in visited:
                    visited.add(child_even)
                    next_frontier.add(child_even)

                # If (n-1) mod 3 == 0 and result is odd: n -> (n-1)/3
                if n > 1 and (n - 1) % 3 == 0:
                    child_odd = (n - 1) // 3
                    if child_odd > 0 and child_odd % 2 == 1 and child_odd != 1:
                        tree[n].append(child_odd)
                        if child_odd not in visited:
                            visited.add(child_odd)
                            next_frontier.add(child_odd)
            frontier = next_frontier

        return dict(tree)

    def search_counterexample_heuristic(self, candidates: Optional[List[int]] = None,
                                         max_steps: int = 100_000) -> Dict[str, Any]:
        """Search for counterexamples using heuristic candidate generation.
        
        Strategy: Focus on numbers with specific mod structure that
        could theoretically sustain long non-converging orbits.
        """
        if candidates is None:
            # Generate candidates: numbers of form 2^a * 3^b - 1
            # and numbers with high 2-adic valuation patterns
            candidates = []
            for a in range(1, 30):
                for b in range(1, 20):
                    val = (2 ** a) * (3 ** b) - 1
                    if val > 0:
                        candidates.append(val)
            # Add Mersenne-like numbers
            for k in range(2, 40):
                candidates.append(2 ** k - 1)
            # Add numbers with dense odd chains (mod 8 ≡ 3 or 7)
            rng = random.Random(42)
            for _ in range(1000):
                base = rng.randint(10**8, 10**12)
                base = base | 1  # make odd
                if base % 8 in (3, 7):
                    candidates.append(base)

        results = {
            'tested': 0,
            'all_converged': True,
            'max_stopping_time': 0,
            'max_stopping_value': 0,
            'non_converged': [],
            'extreme_orbits': []
        }

        for n in candidates:
            orb = CollatzOrbit(n, max_steps)
            results['tested'] += 1

            if orb.stopping_time == -1:
                results['all_converged'] = False
                results['non_converged'].append({
                    'n': n, 'max_reached': orb.max_value,
                    'last_values': orb.sequence[-10:]
                })
            elif orb.stopping_time > results['max_stopping_time']:
                results['max_stopping_time'] = orb.stopping_time
                results['max_stopping_value'] = n

            if orb.glide > 100:
                results['extreme_orbits'].append({
                    'n': n, 'glide': orb.glide,
                    'stopping_time': orb.stopping_time,
                    'max_value': orb.max_value
                })

        results['extreme_orbits'].sort(key=lambda x: x['glide'], reverse=True)
        results['extreme_orbits'] = results['extreme_orbits'][:20]
        return results

    def detect_cycle_candidates(self, max_n: int = 10_000,
                                 max_steps: int = 50_000) -> List[Dict]:
        """Search for non-trivial cycles (not 4-2-1).
        
        A non-trivial cycle would be a counterexample to Collatz.
        Uses Floyd's cycle detection on orbits.
        """
        cycles_found = []
        for n in range(2, max_n):
            # Floyd's tortoise and hare
            slow = n
            fast = n
            for _ in range(max_steps):
                slow = self._collatz_step(slow)
                fast = self._collatz_step(self._collatz_step(fast))
                if slow == fast:
                    break
            else:
                continue

            # Found a meeting point — trace the cycle
            cycle_start = slow
            cycle = [cycle_start]
            current = self._collatz_step(cycle_start)
            while current != cycle_start:
                cycle.append(current)
                current = self._collatz_step(current)
                if len(cycle) > max_steps:
                    break

            # Check if it's the trivial 4-2-1 cycle
            if set(cycle) != {1, 2, 4} and len(cycle) < max_steps:
                cycles_found.append({
                    'start': n,
                    'cycle': cycle,
                    'length': len(cycle),
                    'min_value': min(cycle)
                })

        return cycles_found

    @staticmethod
    def _collatz_step(n: int) -> int:
        return n // 2 if n % 2 == 0 else 3 * n + 1

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report."""
        return {
            'orbits_computed': len(self.orbits),
            'invariants': self.invariants,
            'stopping_time_classes': len(self.classify_by_stopping_time()),
            'convergence_rate': sum(1 for o in self.orbits.values()
                                    if o.stopping_time > 0) / max(len(self.orbits), 1),
        }
