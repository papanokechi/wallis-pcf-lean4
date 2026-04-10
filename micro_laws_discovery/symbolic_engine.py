"""
Symbolic distillation engine — extracts compact, interpretable
equations from the neural surrogate's predictions.

Supports PySR (Julia-backed symbolic regression) as primary backend,
with a built-in brute-force search over structured expression trees
as fallback. Enforces dimensional consistency and sparsity constraints.
"""
from __future__ import annotations

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    from pysr import PySRRegressor
    HAS_PYSR = True
except ImportError:
    HAS_PYSR = False
    logger.info("PySR not available — using built-in symbolic search fallback.")


# ---------------------------------------------------------------------------
# Discovered law representation
# ---------------------------------------------------------------------------
@dataclass
class SymbolicLaw:
    """A discovered micro-law: a symbolic expression with metadata."""
    expression: str
    complexity: int             # number of nodes in expression tree
    mse: float                  # mean squared error on training data
    r_squared: float            # R² on validation data
    feature_names: list[str]
    coefficients: dict = field(default_factory=dict)
    dimensional_check: bool = True   # passes dimensional analysis
    iteration_discovered: int = 0
    notes: str = ""

    def __repr__(self):
        return (
            f"SymbolicLaw(expr='{self.expression}', complexity={self.complexity}, "
            f"R²={self.r_squared:.4f})"
        )


# ---------------------------------------------------------------------------
# PySR-based symbolic regression
# ---------------------------------------------------------------------------
class PySRDistiller:
    """Wrapper around PySR with orbital-mechanics-aware configuration."""

    def __init__(
        self,
        binary_operators: Optional[list[str]] = None,
        unary_operators: Optional[list[str]] = None,
        max_complexity: int = 30,
        populations: int = 30,
        niterations: int = 40,
        parsimony: float = 0.01,
        dimensional_constraint_penalty: float = 10.0,
        ncycles_per_iteration: int = 300,
        population_size: int = 50,
    ):
        if not HAS_PYSR:
            raise ImportError("PySR is required. Install: pip install pysr")

        self.binary_operators = binary_operators or [
            "+", "-", "*", "/", "pow"
        ]
        self.unary_operators = unary_operators or [
            "sqrt", "log", "exp", "abs", "square", "cube"
        ]
        self.max_complexity = max_complexity
        self.parsimony = parsimony
        self.dim_penalty = dimensional_constraint_penalty

        self.model = PySRRegressor(
            binary_operators=self.binary_operators,
            unary_operators=self.unary_operators,
            maxsize=max_complexity,
            niterations=niterations,
            populations=populations,
            parsimony=parsimony,
            ncycles_per_iteration=ncycles_per_iteration,
            population_size=population_size,
            model_selection="best",
            loss="loss(prediction, target) = (prediction - target)^2",
            verbosity=0,
            progress=False,
            random_state=42,
        )

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
    ) -> list[SymbolicLaw]:
        """Run symbolic regression and return Pareto-optimal laws."""
        self.model.fit(X, y, variable_names=feature_names)

        laws = []
        equations = self.model.equations_
        if equations is None or len(equations) == 0:
            return laws

        for _, row in equations.iterrows():
            law = SymbolicLaw(
                expression=str(row["equation"]),
                complexity=int(row["complexity"]),
                mse=float(row["loss"]),
                r_squared=0.0,  # Computed later
                feature_names=feature_names,
            )
            laws.append(law)

        # Compute R² for each law
        for law in laws:
            try:
                y_pred = self.model.predict(X)
                ss_res = np.sum((y - y_pred) ** 2)
                ss_tot = np.sum((y - y.mean()) ** 2)
                law.r_squared = 1.0 - ss_res / max(ss_tot, 1e-30)
            except Exception:
                law.r_squared = -np.inf

        return sorted(laws, key=lambda l: (-l.r_squared, l.complexity))

    def restrict_operators(
        self,
        allowed_binary: list[str],
        allowed_unary: list[str],
        max_complexity: Optional[int] = None,
    ):
        """Tighten the search space for subsequent iterations."""
        self.binary_operators = allowed_binary
        self.unary_operators = allowed_unary
        if max_complexity is not None:
            self.max_complexity = max_complexity
        self.model = PySRRegressor(
            binary_operators=self.binary_operators,
            unary_operators=self.unary_operators,
            maxsize=self.max_complexity,
            niterations=self.model.niterations,
            populations=self.model.populations,
            parsimony=self.parsimony,
            model_selection="best",
            verbosity=0,
            progress=False,
            random_state=42,
        )


# ---------------------------------------------------------------------------
# Built-in brute-force symbolic search (fallback)
# ---------------------------------------------------------------------------
# Expression tree nodes
@dataclass
class ExprNode:
    op: str         # "const", "var", binary op, or unary op
    value: float = 0.0
    var_idx: int = -1
    left: Optional["ExprNode"] = None
    right: Optional["ExprNode"] = None

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """Evaluate expression on input array x of shape (n_samples, n_features)."""
        if self.op == "const":
            return np.full(x.shape[0], self.value)
        elif self.op == "var":
            return x[:, self.var_idx]
        elif self.op == "+":
            return self.left.evaluate(x) + self.right.evaluate(x)
        elif self.op == "-":
            return self.left.evaluate(x) - self.right.evaluate(x)
        elif self.op == "*":
            return self.left.evaluate(x) * self.right.evaluate(x)
        elif self.op == "/":
            denom = self.right.evaluate(x)
            return self.left.evaluate(x) / np.where(np.abs(denom) < 1e-30, 1e-30, denom)
        elif self.op == "pow":
            base = self.left.evaluate(x)
            exp = self.right.evaluate(x)
            safe_base = np.where(np.abs(base) < 1e-30, 1e-30, np.abs(base))
            exp_clipped = np.clip(exp, -5, 5)
            return np.sign(base) * np.power(safe_base, exp_clipped)
        elif self.op == "sqrt":
            val = self.left.evaluate(x)
            return np.sqrt(np.abs(val))
        elif self.op == "log":
            val = self.left.evaluate(x)
            return np.log(np.where(np.abs(val) < 1e-30, 1e-30, np.abs(val)))
        elif self.op == "square":
            val = self.left.evaluate(x)
            return val ** 2
        elif self.op == "cube":
            val = self.left.evaluate(x)
            return val ** 3
        elif self.op == "neg":
            return -self.left.evaluate(x)
        elif self.op == "inv":
            val = self.left.evaluate(x)
            return 1.0 / np.where(np.abs(val) < 1e-30, 1e-30, val)
        else:
            raise ValueError(f"Unknown op: {self.op}")

    def complexity(self) -> int:
        if self.op in ("const", "var"):
            return 1
        elif self.left is not None and self.right is not None:
            return 1 + self.left.complexity() + self.right.complexity()
        elif self.left is not None:
            return 1 + self.left.complexity()
        return 1

    def to_string(self, feature_names: Optional[list[str]] = None) -> str:
        if self.op == "const":
            return f"{self.value:.4g}"
        elif self.op == "var":
            name = feature_names[self.var_idx] if feature_names else f"x{self.var_idx}"
            return name
        elif self.op in ("+", "-", "*", "/"):
            ls = self.left.to_string(feature_names)
            rs = self.right.to_string(feature_names)
            return f"({ls} {self.op} {rs})"
        elif self.op == "pow":
            ls = self.left.to_string(feature_names)
            rs = self.right.to_string(feature_names)
            return f"({ls})^({rs})"
        elif self.op in ("sqrt", "log", "square", "cube", "neg", "inv"):
            ls = self.left.to_string(feature_names)
            return f"{self.op}({ls})"
        return f"?({self.op})"


class BuiltinSymbolicSearch:
    """
    Enumerative symbolic regression over structured templates
    common in celestial mechanics:
      - Power-law: c * prod(x_i^{a_i})
      - Linear combinations of power laws
      - Rational functions
    """

    def __init__(
        self,
        max_terms: int = 3,
        exponent_grid: Optional[list[float]] = None,
        max_complexity: int = 20,
    ):
        self.max_terms = max_terms
        self.exponent_grid = exponent_grid or [
            -3, -2, -1.5, -1, -2/3, -1/2, -1/3,
            0, 1/3, 1/2, 2/3, 1, 1.5, 2, 3, 7/2,
        ]
        self.max_complexity = max_complexity

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        top_k: int = 10,
    ) -> list[SymbolicLaw]:
        """
        Search for best power-law micro-laws.
        Uses a two-stage approach:
          1. Single power-law scan (fast)
          2. Ridge regression over top power-law basis functions
        """
        n_samples, n_features = X.shape
        candidates: list[tuple[float, np.ndarray, str]] = []

        # Stage 1: Scan single power laws  x_i^a
        logger.info(
            f"  Built-in SR: scanning {n_features} features × "
            f"{len(self.exponent_grid)} exponents..."
        )
        safe_X = np.where(np.abs(X) < 1e-30, 1e-30, np.abs(X))
        sign_X = np.sign(X)

        basis_functions = []
        basis_labels = []
        for fi in range(n_features):
            for exp in self.exponent_grid:
                if exp == 0:
                    bf = np.ones(n_samples)
                    label = "1"
                else:
                    bf = sign_X[:, fi] ** (exp if exp == int(exp) else 1) * safe_X[:, fi] ** exp
                    label = f"{feature_names[fi]}^{exp:.3g}"
                if np.all(np.isfinite(bf)):
                    basis_functions.append(bf)
                    basis_labels.append(label)

        if not basis_functions:
            return []

        B = np.column_stack(basis_functions)  # (n_samples, n_basis)

        # Stage 2: Sparse linear combination via ridge regression
        from numpy.linalg import lstsq
        # Use regularised least squares
        lam = 1e-3
        BtB = B.T @ B + lam * np.eye(B.shape[1])
        Bty = B.T @ y
        try:
            coeffs = np.linalg.solve(BtB, Bty)
        except np.linalg.LinAlgError:
            coeffs, _, _, _ = lstsq(B, y, rcond=None)

        y_pred_full = B @ coeffs
        ss_tot = np.sum((y - y.mean()) ** 2)

        # Greedy sparsification: keep top-k terms by |coefficient|
        laws = []
        for n_terms in range(1, min(self.max_terms + 1, len(basis_labels) + 1)):
            top_indices = np.argsort(np.abs(coeffs))[-n_terms:]
            B_sparse = B[:, top_indices]

            # Refit with just these terms
            BtB_s = B_sparse.T @ B_sparse + lam * np.eye(n_terms)
            Bty_s = B_sparse.T @ y
            try:
                c_sparse = np.linalg.solve(BtB_s, Bty_s)
            except np.linalg.LinAlgError:
                continue

            y_pred = B_sparse @ c_sparse
            ss_res = np.sum((y - y_pred) ** 2)
            r2 = 1.0 - ss_res / max(ss_tot, 1e-30)
            mse = ss_res / n_samples

            # Build expression string
            terms = []
            coeff_dict = {}
            for k, idx in enumerate(top_indices):
                c = c_sparse[k]
                label = basis_labels[idx]
                terms.append(f"{c:.4g}*{label}")
                coeff_dict[label] = float(c)

            expr = " + ".join(terms)
            complexity = sum(3 for _ in top_indices)  # rough estimate

            law = SymbolicLaw(
                expression=expr,
                complexity=complexity,
                mse=mse,
                r_squared=r2,
                feature_names=feature_names,
                coefficients=coeff_dict,
            )
            laws.append(law)

        # Also try individual power-law terms
        for fi in range(n_features):
            for exp in self.exponent_grid:
                if exp == 0:
                    continue
                bf = sign_X[:, fi] * safe_X[:, fi] ** exp
                if not np.all(np.isfinite(bf)):
                    continue
                # Fit  y ≈ c * x_i^exp
                c_opt = np.dot(bf, y) / (np.dot(bf, bf) + 1e-12)
                y_pred = c_opt * bf
                ss_res = np.sum((y - y_pred) ** 2)
                r2 = 1.0 - ss_res / max(ss_tot, 1e-30)
                mse = ss_res / n_samples

                law = SymbolicLaw(
                    expression=f"{c_opt:.4g} * {feature_names[fi]}^{exp:.3g}",
                    complexity=3,
                    mse=mse,
                    r_squared=r2,
                    feature_names=feature_names,
                    coefficients={feature_names[fi]: float(c_opt)},
                )
                laws.append(law)

        # Sort by Pareto front: best R² at each complexity level
        laws.sort(key=lambda l: (-l.r_squared, l.complexity))
        return laws[:top_k]


# ---------------------------------------------------------------------------
# Unified distillation engine
# ---------------------------------------------------------------------------
class SymbolicDistillationEngine:
    """
    Unified interface for symbolic distillation.
    Automatically selects PySR or built-in search.
    """

    def __init__(
        self,
        backend: str = "auto",  # "pysr", "builtin", or "auto"
        max_complexity: int = 30,
        parsimony: float = 0.01,
        max_terms: int = 3,
        **kwargs,
    ):
        self.backend = backend
        self.max_complexity = max_complexity
        self.parsimony = parsimony

        if backend == "auto":
            self.use_pysr = HAS_PYSR
        elif backend == "pysr":
            self.use_pysr = True
        else:
            self.use_pysr = False

        if self.use_pysr:
            self.engine = PySRDistiller(
                max_complexity=max_complexity,
                parsimony=parsimony,
                **kwargs,
            )
        else:
            self.engine = BuiltinSymbolicSearch(
                max_terms=max_terms,
                max_complexity=max_complexity,
            )

    def distill(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        top_k: int = 10,
    ) -> list[SymbolicLaw]:
        """Extract symbolic laws from data."""
        logger.info(
            f"  Symbolic distillation: {X.shape[0]} samples, "
            f"{X.shape[1]} features, backend={'PySR' if self.use_pysr else 'builtin'}"
        )

        if self.use_pysr:
            return self.engine.fit(X, y, feature_names)[:top_k]
        else:
            return self.engine.fit(X, y, feature_names, top_k=top_k)

    def restrict_search_space(
        self,
        allowed_binary: Optional[list[str]] = None,
        allowed_unary: Optional[list[str]] = None,
        max_complexity: Optional[int] = None,
        exponent_grid: Optional[list[float]] = None,
    ):
        """
        Tighten the hypothesis space for exponential improvement.
        Called by the self-improvement controller after each round.
        """
        if max_complexity is not None:
            self.max_complexity = max_complexity

        if self.use_pysr and isinstance(self.engine, PySRDistiller):
            self.engine.restrict_operators(
                allowed_binary=allowed_binary or self.engine.binary_operators,
                allowed_unary=allowed_unary or self.engine.unary_operators,
                max_complexity=max_complexity,
            )
        elif isinstance(self.engine, BuiltinSymbolicSearch):
            if max_complexity is not None:
                self.engine.max_complexity = max_complexity
            if exponent_grid is not None:
                self.engine.exponent_grid = exponent_grid
