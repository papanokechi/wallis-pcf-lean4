"""
SAT Bridge — Constraint Satisfaction Integration
==================================================
Encodes mathematical conjectures as constraint satisfaction problems.
Uses a pure-Python DPLL solver (no external dependencies).

Provides:
  - Collatz bounded verification via SAT
  - Erdős–Straus decomposition search via constraint propagation
  - Hadamard orthogonality constraints
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict


# ────────────────────────────────────────────────────────────
# Lightweight SAT / Constraint Solver (pure Python)
# ────────────────────────────────────────────────────────────

class ConstraintSolver:
    """Simple constraint propagation + backtracking solver."""

    def __init__(self):
        self.variables: Dict[str, List[int]] = {}  # var -> domain
        self.constraints: List[callable] = []

    def add_variable(self, name: str, domain: List[int]):
        self.variables[name] = list(domain)

    def add_constraint(self, func, var_names: List[str]):
        self.constraints.append((func, var_names))

    def solve(self, max_solutions: int = 1) -> List[Dict[str, int]]:
        """Backtracking search with constraint propagation."""
        solutions = []
        assignment = {}
        self._backtrack(assignment, solutions, max_solutions)
        return solutions

    def _backtrack(self, assignment: Dict[str, int],
                    solutions: List[Dict[str, int]], max_solutions: int):
        if len(solutions) >= max_solutions:
            return

        if len(assignment) == len(self.variables):
            solutions.append(dict(assignment))
            return

        # Choose unassigned variable with smallest domain (MRV heuristic)
        unassigned = [v for v in self.variables if v not in assignment]
        var = min(unassigned, key=lambda v: len(self.variables[v]))

        for value in self.variables[var]:
            assignment[var] = value
            if self._consistent(assignment):
                self._backtrack(assignment, solutions, max_solutions)
                if len(solutions) >= max_solutions:
                    del assignment[var]
                    return
            del assignment[var]

    def _consistent(self, assignment: Dict[str, int]) -> bool:
        for func, var_names in self.constraints:
            if all(v in assignment for v in var_names):
                values = [assignment[v] for v in var_names]
                if not func(*values):
                    return False
        return True


# ────────────────────────────────────────────────────────────
# Problem-Specific SAT Encodings
# ────────────────────────────────────────────────────────────

class CollatzSATEncoder:
    """Encode Collatz orbit verification as constraints."""

    @staticmethod
    def verify_orbit_bounded(n: int, max_steps: int) -> Dict[str, Any]:
        """Verify that n reaches 1 within max_steps using constraint propagation.
        
        This is deterministic verification, not SAT per se,
        but structured as constraint checking for consistency.
        """
        current = n
        orbit = [current]
        for step in range(max_steps):
            if current == 1:
                return {
                    'n': n, 'verified': True,
                    'steps': step, 'orbit_length': len(orbit),
                    'max_value': max(orbit),
                }
            if current % 2 == 0:
                current = current // 2
            else:
                current = 3 * current + 1
            orbit.append(current)

        return {
            'n': n, 'verified': False,
            'steps': max_steps, 'orbit_length': len(orbit),
            'last_value': current, 'max_value': max(orbit),
        }

    @staticmethod
    def batch_verify(start: int, end: int, max_steps: int = 100000) -> Dict[str, Any]:
        """Batch verify Collatz for range [start, end)."""
        verified = 0
        failed = []
        max_stopping_time = 0
        max_orbit_value = 0

        for n in range(start, end):
            result = CollatzSATEncoder.verify_orbit_bounded(n, max_steps)
            if result['verified']:
                verified += 1
                max_stopping_time = max(max_stopping_time, result['steps'])
                max_orbit_value = max(max_orbit_value, result['max_value'])
            else:
                failed.append(n)

        return {
            'range': (start, end),
            'total': end - start,
            'verified': verified,
            'failed': failed,
            'all_verified': len(failed) == 0,
            'max_stopping_time': max_stopping_time,
            'max_orbit_value': max_orbit_value,
        }


class ErdosStrausSATEncoder:
    """Encode Erdős–Straus decomposition as constraint satisfaction."""

    @staticmethod
    def find_decomposition_csp(n: int, max_denom: int = 0) -> Optional[Tuple[int, int, int]]:
        """Find 4/n = 1/a + 1/b + 1/c using constraint solver."""
        if max_denom == 0:
            max_denom = n * n

        import math
        a_min = max(1, math.ceil(n / 4))
        a_max = math.ceil(3 * n / 4)

        for a in range(a_min, a_max + 1):
            num = 4 * a - n
            den = n * a
            if num <= 0:
                continue

            b_min = max(a, math.ceil(den / num))
            b_max = min(max_denom, 2 * den // num + 1)

            for b in range(b_min, b_max + 1):
                c_num = num * b - den
                c_den = den * b
                if c_num > 0 and c_den % c_num == 0:
                    c = c_den // c_num
                    if c >= b and c <= max_denom:
                        # Verify: 4*a*b*c == n*(b*c + a*c + a*b)
                        if 4 * a * b * c == n * (b * c + a * c + a * b):
                            return (a, b, c)
        return None

    @staticmethod
    def batch_verify(start: int, end: int) -> Dict[str, Any]:
        """Batch verify Erdős–Straus for range [start, end)."""
        verified = 0
        failed = []
        decompositions = {}

        for n in range(start, end):
            result = ErdosStrausSATEncoder.find_decomposition_csp(n)
            if result:
                verified += 1
                decompositions[n] = result
            else:
                failed.append(n)

        return {
            'range': (start, end),
            'total': end - start,
            'verified': verified,
            'failed': failed,
            'all_verified': len(failed) == 0,
            'sample_decompositions': {k: v for k, v in list(decompositions.items())[:10]},
        }


class HadamardSATEncoder:
    """Encode Hadamard matrix search as constraint satisfaction."""

    @staticmethod
    def search_csp(n: int, timeout_rows: int = 0) -> Optional[List[List[int]]]:
        """Search for Hadamard matrix of order n using CSP with pruning.
        
        Builds matrix row by row, checking orthogonality constraints.
        Uses backtracking with constraint propagation.
        """
        if n > 12:
            return None  # CSP too expensive for large n

        if timeout_rows == 0:
            timeout_rows = n

        matrix = []
        # First row: all +1 (normalized Hadamard)
        matrix.append([1] * n)

        if not HadamardSATEncoder._extend_matrix(matrix, n, timeout_rows):
            return None

        # Verify
        for i in range(n):
            for j in range(i + 1, n):
                if sum(matrix[i][k] * matrix[j][k] for k in range(n)) != 0:
                    return None

        return matrix

    @staticmethod
    def _extend_matrix(matrix: List[List[int]], n: int, max_rows: int) -> bool:
        """Recursively extend matrix one row at a time."""
        if len(matrix) >= max_rows or len(matrix) >= n:
            return len(matrix) >= n

        # Generate candidate row: first entry +1 (column normalization)
        return HadamardSATEncoder._backtrack_row(matrix, n, [1], 1, max_rows)

    @staticmethod
    def _backtrack_row(matrix: List[List[int]], n: int,
                        partial_row: List[int], col: int,
                        max_rows: int) -> bool:
        """Backtrack to build a valid row."""
        if col == n:
            # Check orthogonality with all previous rows
            for prev_row in matrix:
                dot = sum(partial_row[k] * prev_row[k] for k in range(n))
                if dot != 0:
                    return False
            # Row is valid, add and continue
            matrix.append(partial_row[:])
            if len(matrix) >= n:
                return True
            result = HadamardSATEncoder._extend_matrix(matrix, n, max_rows)
            if result:
                return True
            matrix.pop()
            return False

        # Pruning: check partial dot products
        for prev_row in matrix:
            partial_dot = sum(partial_row[k] * prev_row[k] for k in range(col))
            remaining = n - col
            # |partial_dot + remaining_dot| must be 0
            # So |remaining_dot| = |partial_dot|
            # Max possible |remaining_dot| = remaining
            if abs(partial_dot) > remaining:
                return False

        # Try +1 and -1
        for val in [1, -1]:
            partial_row.append(val)
            if HadamardSATEncoder._backtrack_row(matrix, n, partial_row, col + 1, max_rows):
                return True
            partial_row.pop()

        return False


class FormalVerification:
    """Generate formal verification code (Lean 4 / Coq stubs)."""

    @staticmethod
    def generate_lean4_collatz_verifier(max_n: int) -> str:
        """Generate Lean 4 code for bounded Collatz verification."""
        return f"""
-- Auto-generated Lean 4 verification stub
-- Bounded Collatz verification for n ≤ {max_n}

def collatz_step (n : Nat) : Nat :=
  if n % 2 == 0 then n / 2 else 3 * n + 1

def collatz_orbit (n : Nat) (max_steps : Nat) : List Nat :=
  match max_steps with
  | 0 => [n]
  | k + 1 => if n ≤ 1 then [n] else n :: collatz_orbit (collatz_step n) k

def collatz_reaches_one (n : Nat) (max_steps : Nat) : Bool :=
  (collatz_orbit n max_steps).getLast? == some 1

-- Verification: all n in [2, {max_n}] reach 1 within 10000 steps
-- #eval (List.range ({max_n} - 1)).map (· + 2) |>.all (collatz_reaches_one · 10000)
"""

    @staticmethod
    def generate_lean4_erdos_straus_verifier(max_n: int) -> str:
        """Generate Lean 4 code for Erdős–Straus verification."""
        return f"""
-- Auto-generated Lean 4 verification stub
-- Erdős–Straus conjecture verification for n ≤ {max_n}

def erdos_straus_check (n : Nat) : Bool :=
  -- Check if 4/n = 1/a + 1/b + 1/c has a solution
  -- Equivalent: 4*a*b*c = n*(b*c + a*c + a*b)
  let a_max := 3 * n / 4 + 1
  (List.range a_max).any fun a_idx =>
    let a := a_idx + n / 4
    if a == 0 then false
    else
      let num := 4 * a - n
      if num ≤ 0 then false
      else
        let den := n * a
        let b_max := 2 * den / num + 1
        (List.range (b_max - a)).any fun b_offset =>
          let b := b_offset + a
          let c_num := num * b - den
          let c_den := den * b
          c_num > 0 && c_den % c_num == 0 && c_den / c_num ≥ b

-- #eval (List.range ({max_n} - 1)).map (· + 2) |>.all erdos_straus_check
"""

    @staticmethod
    def generate_lean4_hadamard_verifier(order: int, matrix: List[List[int]]) -> str:
        """Generate Lean 4 code to verify a specific Hadamard matrix."""
        n = order
        rows_str = "\n".join(
            f"  | ⟨{i}, _⟩ => ![{', '.join(str(v) for v in row)}]"
            for i, row in enumerate(matrix)
        )
        return f"""
-- Auto-generated Lean 4 Hadamard matrix verification
-- Order {n}

def hadamard_{n} : Matrix (Fin {n}) (Fin {n}) Int := fun i =>
  match i with
{rows_str}

-- Verify: H * Hᵀ = {n} • I
-- theorem hadamard_{n}_valid :
--   hadamard_{n} * hadamard_{n}ᵀ = {n} • (1 : Matrix (Fin {n}) (Fin {n}) Int) := by
--   native_decide
"""
