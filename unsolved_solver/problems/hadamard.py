"""
Hadamard Conjecture Problem Domain
====================================
The Hadamard conjecture states that a Hadamard matrix of order n
exists for every n that is a multiple of 4 (for n > 2).

A Hadamard matrix H of order n satisfies H·Hᵀ = n·Iₙ,
where all entries are +1 or -1.

This module provides:
  - Known constructions (Sylvester, Paley, tensor product)
  - Matrix validation and scoring
  - Optimization-based search for unknown orders
  - Structural feature extraction
  - Construction method discovery
"""

import math
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any


class HadamardMatrix:
    """Represents and validates a candidate Hadamard matrix."""

    def __init__(self, matrix: List[List[int]], method: str = 'unknown'):
        self.matrix = matrix
        self.n = len(matrix)
        self.method = method
        self._valid = None

    def is_valid(self) -> bool:
        """Check if H·Hᵀ = n·I exactly."""
        if self._valid is not None:
            return self._valid

        n = self.n
        # Check all entries are ±1
        for row in self.matrix:
            if len(row) != n:
                self._valid = False
                return False
            for val in row:
                if val not in (1, -1):
                    self._valid = False
                    return False

        # Check H·Hᵀ = n·I
        for i in range(n):
            for j in range(n):
                dot = sum(self.matrix[i][k] * self.matrix[j][k] for k in range(n))
                expected = n if i == j else 0
                if dot != expected:
                    self._valid = False
                    return False

        self._valid = True
        return True

    def hadamard_score(self) -> float:
        """Score how close the matrix is to being Hadamard (0=perfect, higher=worse).
        
        Uses Frobenius norm of (H·Hᵀ - n·I).
        """
        n = self.n
        total_error = 0.0
        for i in range(n):
            for j in range(n):
                dot = sum(self.matrix[i][k] * self.matrix[j][k] for k in range(n))
                expected = n if i == j else 0
                total_error += (dot - expected) ** 2
        return math.sqrt(total_error) / n

    def spectral_features(self) -> Dict[str, float]:
        """Extract spectral and structural features."""
        n = self.n
        features = {}

        # Row sums
        row_sums = [sum(row) for row in self.matrix]
        features['mean_row_sum'] = sum(row_sums) / n
        features['var_row_sum'] = sum((s - features['mean_row_sum']) ** 2 for s in row_sums) / n

        # Column sums
        col_sums = [sum(self.matrix[i][j] for i in range(n)) for j in range(n)]
        features['mean_col_sum'] = sum(col_sums) / n
        features['var_col_sum'] = sum((s - features['mean_col_sum']) ** 2 for s in col_sums) / n

        # Sign balance per row
        pos_counts = [sum(1 for v in row if v == 1) for row in self.matrix]
        features['mean_pos_fraction'] = sum(p / n for p in pos_counts) / n

        # Autocorrelation (adjacent entries)
        auto_corr = 0
        count = 0
        for row in self.matrix:
            for k in range(n - 1):
                auto_corr += row[k] * row[k + 1]
                count += 1
        features['row_autocorrelation'] = auto_corr / count if count > 0 else 0

        # Gram matrix off-diagonal stats
        off_diag = []
        for i in range(n):
            for j in range(i + 1, n):
                dot = sum(self.matrix[i][k] * self.matrix[j][k] for k in range(n))
                off_diag.append(dot)
        if off_diag:
            features['mean_off_diag'] = sum(off_diag) / len(off_diag)
            features['max_off_diag'] = max(abs(d) for d in off_diag)
            features['rms_off_diag'] = math.sqrt(sum(d * d for d in off_diag) / len(off_diag))

        return features

    def sign_pattern(self) -> str:
        """Compact string representation of the sign pattern."""
        return '\n'.join(''.join('+' if v == 1 else '-' for v in row)
                        for row in self.matrix)


class HadamardConstructor:
    """Generate Hadamard matrices via known constructions."""

    @staticmethod
    def sylvester(k: int) -> HadamardMatrix:
        """Sylvester construction: order 2^k via Kronecker product.
        
        H_1 = [[1]]
        H_{k+1} = [[H_k, H_k], [H_k, -H_k]]
        """
        H = [[1]]
        for _ in range(k):
            n = len(H)
            new_H = []
            for i in range(n):
                new_H.append(H[i] + H[i])
            for i in range(n):
                new_H.append(H[i] + [-v for v in H[i]])
            H = new_H
        return HadamardMatrix(H, f'sylvester_2^{k}')

    @staticmethod
    def paley_type1(q: int) -> Optional[HadamardMatrix]:
        """Paley Type I construction for q ≡ 3 (mod 4), q prime power.
        
        Gives Hadamard matrix of order q + 1.
        Only implemented for prime q here.
        """
        if q < 3 or q % 4 != 3:
            return None
        if not HadamardConstructor._is_prime(q):
            return None

        n = q + 1

        # Build Quadratic Residue matrix Q
        # Q[i][j] = Legendre(i-j, q) for i,j in {0,...,q-1}
        qr = set()
        for x in range(1, q):
            qr.add((x * x) % q)

        def legendre(a, p):
            a = a % p
            if a == 0:
                return 0
            return 1 if a in qr else -1

        # Construct (q+1) × (q+1) matrix
        # Bordered Jacobsthal matrix
        S = [[0] * q for _ in range(q)]
        for i in range(q):
            for j in range(q):
                if i == j:
                    S[i][j] = 0
                else:
                    S[i][j] = legendre(i - j, q)

        # H = I + S bordered by 1s
        # Top row: [1, 1, 1, ..., 1]
        # Left col: [1, -1, -1, ..., -1]ᵀ (except top)
        # Interior: I + S (off-diagonal from Jacobsthal)
        H = [[0] * n for _ in range(n)]
        # First row all 1s
        for j in range(n):
            H[0][j] = 1
        # First column: 1, then -1s
        for i in range(1, n):
            H[i][0] = -1
        # Interior: I_q + S (adjusted with -1 border)
        for i in range(q):
            for j in range(q):
                if i == j:
                    H[i + 1][j + 1] = -1 + S[i][j]  # diagonal: -1 + 0 = -1? No...
                else:
                    H[i + 1][j + 1] = S[i][j]

        # Correct construction: H = [[1, j], [-j^T, Q - I]]
        # where j = all-ones row, Q is Jacobsthal
        # Let's redo properly
        H = [[0] * n for _ in range(n)]
        H[0][0] = 1
        for j in range(1, n):
            H[0][j] = 1
            H[j][0] = 1

        for i in range(q):
            for j in range(q):
                if i == j:
                    H[i + 1][j + 1] = -1
                else:
                    H[i + 1][j + 1] = legendre(i - j, q)

        result = HadamardMatrix(H, f'paley_type1_q{q}')
        if result.is_valid():
            return result

        # Try with negated border
        for i in range(1, n):
            H[i][0] = -1
        result = HadamardMatrix(H, f'paley_type1_q{q}')
        if result.is_valid():
            return result

        return None

    @staticmethod
    def tensor_product(H1: HadamardMatrix, H2: HadamardMatrix) -> HadamardMatrix:
        """Kronecker product of two Hadamard matrices."""
        n1, n2 = H1.n, H2.n
        n = n1 * n2
        H = [[0] * n for _ in range(n)]
        for i1 in range(n1):
            for j1 in range(n1):
                for i2 in range(n2):
                    for j2 in range(n2):
                        H[i1 * n2 + i2][j1 * n2 + j2] = H1.matrix[i1][j1] * H2.matrix[i2][j2]
        return HadamardMatrix(H, f'tensor_{H1.method}⊗{H2.method}')

    @staticmethod
    def _is_prime(n: int) -> bool:
        if n < 2:
            return False
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


class HadamardSearcher:
    """Search for Hadamard matrices of unknown orders via optimization."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.best_found: Dict[int, HadamardMatrix] = {}
        self.search_history: List[Dict[str, Any]] = []

    def random_pm_matrix(self, n: int) -> List[List[int]]:
        """Generate a random ±1 matrix."""
        return [[self.rng.choice([1, -1]) for _ in range(n)] for _ in range(n)]

    def local_search(self, n: int, max_iter: int = 10000,
                     restarts: int = 10) -> Optional[HadamardMatrix]:
        """Stochastic local search: flip entries to minimize Hadamard score.
        
        Uses steepest descent with random restarts.
        """
        best_score = float('inf')
        best_matrix = None

        for restart in range(restarts):
            matrix = self.random_pm_matrix(n)
            score = self._compute_score(matrix, n)

            for iteration in range(max_iter):
                if score == 0:
                    result = HadamardMatrix(matrix, f'local_search_n{n}')
                    if result.is_valid():
                        self.best_found[n] = result
                        return result

                # Try flipping each entry, keep best improvement
                best_flip = None
                best_new_score = score

                # Sample random positions to flip (don't check all for large n)
                positions = []
                if n <= 16:
                    positions = [(i, j) for i in range(n) for j in range(n)]
                else:
                    for _ in range(n * 4):
                        positions.append((self.rng.randint(0, n - 1),
                                          self.rng.randint(0, n - 1)))

                for i, j in positions:
                    matrix[i][j] *= -1
                    new_score = self._compute_score(matrix, n)
                    if new_score < best_new_score:
                        best_new_score = new_score
                        best_flip = (i, j)
                    matrix[i][j] *= -1  # flip back

                if best_flip is None:
                    break  # local minimum
                i, j = best_flip
                matrix[i][j] *= -1
                score = best_new_score

            if score < best_score:
                best_score = score
                best_matrix = [row[:] for row in matrix]

            self.search_history.append({
                'n': n, 'restart': restart,
                'final_score': score,
                'found_exact': score == 0
            })

        if best_matrix:
            result = HadamardMatrix(best_matrix, f'local_search_n{n}_score{best_score:.4f}')
            if n not in self.best_found or result.hadamard_score() < self.best_found[n].hadamard_score():
                self.best_found[n] = result
            return result
        return None

    def simulated_annealing(self, n: int, max_iter: int = 50000,
                             T_start: float = 2.0, T_end: float = 0.01) -> Optional[HadamardMatrix]:
        """Simulated annealing search for Hadamard matrix of order n."""
        matrix = self.random_pm_matrix(n)
        score = self._compute_score(matrix, n)
        best_score = score
        best_matrix = [row[:] for row in matrix]

        for iteration in range(max_iter):
            if score == 0:
                result = HadamardMatrix(matrix, f'sa_n{n}')
                if result.is_valid():
                    self.best_found[n] = result
                    return result

            T = T_start * (T_end / T_start) ** (iteration / max_iter)

            # Random flip
            i = self.rng.randint(0, n - 1)
            j = self.rng.randint(0, n - 1)
            matrix[i][j] *= -1
            new_score = self._compute_score(matrix, n)

            delta = new_score - score
            if delta <= 0 or self.rng.random() < math.exp(-delta / T):
                score = new_score
                if score < best_score:
                    best_score = score
                    best_matrix = [row[:] for row in matrix]
            else:
                matrix[i][j] *= -1  # reject

        result = HadamardMatrix(best_matrix, f'sa_n{n}_score{best_score:.4f}')
        if n not in self.best_found or result.hadamard_score() < self.best_found[n].hadamard_score():
            self.best_found[n] = result
        return result

    def row_by_row_construction(self, n: int, max_attempts: int = 1000) -> Optional[HadamardMatrix]:
        """Greedy row-by-row construction with backtracking.
        
        Build H one row at a time, ensuring orthogonality with all previous rows.
        Uses randomized greedy search.
        """
        for attempt in range(max_attempts):
            rows = [[1] * n]  # First row: all +1 (normalized)

            for row_idx in range(1, n):
                # Try to find a row orthogonal to all previous rows
                best_row = None
                best_violation = float('inf')

                for trial in range(100):
                    # Generate candidate row: starts with +1 (normalized), rest random
                    candidate = [1] + [self.rng.choice([1, -1]) for _ in range(n - 1)]

                    # Check orthogonality with all previous rows
                    violation = 0
                    for prev_row in rows:
                        dot = sum(candidate[k] * prev_row[k] for k in range(n))
                        violation += dot * dot

                    if violation < best_violation:
                        best_violation = violation
                        best_row = candidate

                    if violation == 0:
                        break

                if best_row is not None:
                    rows.append(best_row)
                else:
                    break

            if len(rows) == n:
                result = HadamardMatrix(rows, f'row_by_row_n{n}')
                if result.is_valid():
                    self.best_found[n] = result
                    return result

        return None

    def _compute_score(self, matrix: List[List[int]], n: int) -> float:
        """Compute score = sum of squared off-diagonal entries in H·Hᵀ."""
        score = 0
        for i in range(n):
            for j in range(i + 1, n):
                dot = sum(matrix[i][k] * matrix[j][k] for k in range(n))
                score += dot * dot
        return score


class HadamardAnalyzer:
    """Analyze Hadamard matrix landscape and discover patterns."""

    def __init__(self):
        self.constructor = HadamardConstructor()
        self.searcher = HadamardSearcher()
        self.known_orders: Dict[int, HadamardMatrix] = {}
        self.unknown_orders: List[int] = []
        self.features_db: Dict[int, Dict[str, float]] = {}

    def survey_known_constructions(self, max_order: int = 200) -> Dict[str, Any]:
        """Survey which orders have known Hadamard matrices."""
        constructible = {}

        # Sylvester: powers of 2
        for k in range(1, 20):
            n = 2 ** k
            if n > max_order:
                break
            H = self.constructor.sylvester(k)
            if H.is_valid():
                constructible[n] = H
                self.known_orders[n] = H

        # Paley Type I: q+1 where q ≡ 3 (mod 4), q prime
        for q in range(3, max_order, 4):
            if self.constructor._is_prime(q) and q + 1 <= max_order:
                H = self.constructor.paley_type1(q)
                if H is not None and H.is_valid():
                    constructible[q + 1] = H
                    self.known_orders[q + 1] = H

        # Tensor products of known constructions (limit to order ≤ 100 for speed)
        known_list = sorted(constructible.keys())
        for i, n1 in enumerate(known_list):
            if n1 > 50:
                break
            for n2 in known_list[i:]:
                n = n1 * n2
                if n > min(max_order, 100) or n in constructible:
                    continue
                H = self.constructor.tensor_product(constructible[n1], constructible[n2])
                if H.is_valid():
                    constructible[n] = H
                    self.known_orders[n] = H

        # Identify unknown orders (multiples of 4 not yet found)
        self.unknown_orders = []
        for n in range(4, max_order + 1, 4):
            if n not in constructible:
                self.unknown_orders.append(n)

        return {
            'max_order': max_order,
            'known_count': len(constructible),
            'known_orders': sorted(constructible.keys()),
            'unknown_orders': self.unknown_orders,
            'methods': {n: H.method for n, H in sorted(constructible.items())},
        }

    def extract_features(self) -> Dict[int, Dict[str, float]]:
        """Extract structural features from all known matrices."""
        for n, H in self.known_orders.items():
            self.features_db[n] = H.spectral_features()
        return self.features_db

    def search_unknown_orders(self, orders: Optional[List[int]] = None,
                               max_iter: int = 20000) -> Dict[str, Any]:
        """Search for Hadamard matrices of unknown orders."""
        if orders is None:
            orders = self.unknown_orders[:5]  # limit for time

        results = {}
        for n in orders:
            # Try multiple methods
            H = self.searcher.local_search(n, max_iter=max_iter // 2, restarts=5)
            if H and H.is_valid():
                results[n] = {'found': True, 'method': H.method, 'matrix': H}
                self.known_orders[n] = H
                continue

            H = self.searcher.simulated_annealing(n, max_iter=max_iter)
            if H and H.is_valid():
                results[n] = {'found': True, 'method': H.method, 'matrix': H}
                self.known_orders[n] = H
            else:
                best = self.searcher.best_found.get(n)
                results[n] = {
                    'found': False,
                    'best_score': best.hadamard_score() if best else float('inf'),
                    'best_method': best.method if best else None
                }

        return results

    def generate_report(self) -> Dict[str, Any]:
        return {
            'known_orders': len(self.known_orders),
            'unknown_orders': len(self.unknown_orders),
            'features_extracted': len(self.features_db),
            'search_results': len(self.searcher.search_history),
        }
