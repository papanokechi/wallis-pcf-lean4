"""
Neural dynamical surrogate — predicts short-horizon trajectories
and stability labels from dimensionless orbital features.

Architecture: MLP with residual connections, trained to map
initial orbital features → stability proxy / trajectory embedding.
Supports both classification (stable/unstable) and regression
(MEGNO value, Lyapunov time) targets.
"""
from __future__ import annotations

import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not found — surrogate will use sklearn fallback.")


# ---------------------------------------------------------------------------
# PyTorch MLP surrogate
# ---------------------------------------------------------------------------
if HAS_TORCH:

    class ResidualBlock(nn.Module):
        def __init__(self, dim: int, dropout: float = 0.1):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(dim, dim),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(dim, dim),
            )
            self.norm = nn.LayerNorm(dim)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.norm(x + self.net(x))

    class SurrogateNet(nn.Module):
        """
        MLP surrogate: features → stability logit / MEGNO regression.
        """
        def __init__(
            self,
            input_dim: int,
            hidden_dim: int = 128,
            n_blocks: int = 4,
            dropout: float = 0.1,
            task: str = "classification",  # or "regression"
        ):
            super().__init__()
            self.task = task
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.GELU(),
            )
            self.blocks = nn.Sequential(
                *[ResidualBlock(hidden_dim, dropout) for _ in range(n_blocks)]
            )
            self.head = nn.Linear(hidden_dim, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            h = self.encoder(x)
            h = self.blocks(h)
            out = self.head(h).squeeze(-1)
            return out

        def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
            with torch.no_grad():
                logits = self.forward(x)
                return torch.sigmoid(logits)


# ---------------------------------------------------------------------------
# Sklearn fallback surrogate
# ---------------------------------------------------------------------------
class SklearnSurrogate:
    """Gradient-boosted tree surrogate when PyTorch is unavailable."""

    def __init__(self, task: str = "classification"):
        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
        self.task = task
        if task == "classification":
            self.model = GradientBoostingClassifier(
                n_estimators=200, max_depth=5, learning_rate=0.1
            )
        else:
            self.model = GradientBoostingRegressor(
                n_estimators=200, max_depth=5, learning_rate=0.1
            )

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.model.fit(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.task == "classification":
            return self.model.predict_proba(X)[:, 1]
        return self.model.predict(X)

    def feature_importances(self) -> np.ndarray:
        return self.model.feature_importances_


# ---------------------------------------------------------------------------
# Unified surrogate wrapper
# ---------------------------------------------------------------------------
class DynamicalSurrogate:
    """
    Unified interface for the neural/tree surrogate.
    Handles training, prediction, and feature-importance extraction.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        n_blocks: int = 4,
        dropout: float = 0.1,
        task: str = "classification",
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        device: str = "cpu",
    ):
        self.input_dim = input_dim
        self.task = task
        self.device = device
        self.use_torch = HAS_TORCH

        if self.use_torch:
            self.model = SurrogateNet(
                input_dim, hidden_dim, n_blocks, dropout, task
            ).to(device)
            self.optimizer = optim.AdamW(
                self.model.parameters(), lr=lr, weight_decay=weight_decay
            )
            if task == "classification":
                self.criterion = nn.BCEWithLogitsLoss()
            else:
                self.criterion = nn.MSELoss()
        else:
            self.model = SklearnSurrogate(task)

        self._feature_names: list[str] = []
        self._train_losses: list[float] = []
        self._val_losses: list[float] = []

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 64,
        verbose: bool = True,
    ) -> dict:
        """Train the surrogate. Returns training history."""
        self._train_losses = []
        self._val_losses = []

        if not self.use_torch:
            self.model.fit(X_train, y_train)
            return {"train_losses": [], "val_losses": []}

        # Normalise features
        self._mean = X_train.mean(axis=0)
        self._std = X_train.std(axis=0) + 1e-8
        X_train_n = (X_train - self._mean) / self._std

        train_ds = TensorDataset(
            torch.tensor(X_train_n, dtype=torch.float32),
            torch.tensor(y_train, dtype=torch.float32),
        )
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

        if X_val is not None:
            X_val_n = (X_val - self._mean) / self._std
            X_val_t = torch.tensor(X_val_n, dtype=torch.float32).to(self.device)
            y_val_t = torch.tensor(y_val, dtype=torch.float32).to(self.device)

        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            n_batches = 0
            for xb, yb in train_loader:
                xb, yb = xb.to(self.device), yb.to(self.device)
                self.optimizer.zero_grad()
                pred = self.model(xb)
                loss = self.criterion(pred, yb)
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1

            avg_train = epoch_loss / max(n_batches, 1)
            self._train_losses.append(avg_train)

            if X_val is not None:
                self.model.eval()
                with torch.no_grad():
                    val_pred = self.model(X_val_t)
                    val_loss = self.criterion(val_pred, y_val_t).item()
                self._val_losses.append(val_loss)
                self.model.train()
            else:
                val_loss = float("nan")

            if verbose and (epoch + 1) % 20 == 0:
                logger.info(
                    f"  Epoch {epoch+1}/{epochs}: "
                    f"train_loss={avg_train:.4f}, val_loss={val_loss:.4f}"
                )

        return {
            "train_losses": self._train_losses,
            "val_losses": self._val_losses,
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.use_torch:
            return self.model.predict(X)
        self.model.eval()
        X_n = (X - self._mean) / self._std
        with torch.no_grad():
            xt = torch.tensor(X_n, dtype=torch.float32).to(self.device)
            logits = self.model(xt).cpu().numpy()
        if self.task == "classification":
            return (logits > 0).astype(int)
        return logits

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.use_torch:
            return self.model.predict_proba(X)
        self.model.eval()
        X_n = (X - self._mean) / self._std
        with torch.no_grad():
            xt = torch.tensor(X_n, dtype=torch.float32).to(self.device)
            probs = self.model.predict_proba(xt).cpu().numpy()
        return probs

    def get_gradient_importances(self, X: np.ndarray) -> np.ndarray:
        """
        Compute gradient-based feature importances (mean |∂output/∂input|).
        Only available with PyTorch backend.
        """
        if not self.use_torch:
            return self.model.feature_importances()

        self.model.eval()
        X_n = (X - self._mean) / self._std
        xt = torch.tensor(X_n, dtype=torch.float32, requires_grad=True).to(self.device)
        out = self.model(xt)
        out.sum().backward()
        grads = xt.grad.abs().mean(dim=0).cpu().numpy()
        return grads / (grads.sum() + 1e-12)

    def extract_latent(self, X: np.ndarray) -> np.ndarray:
        """Extract penultimate-layer representations for symbolic regression."""
        if not self.use_torch:
            return X  # No latent space for tree models

        self.model.eval()
        X_n = (X - self._mean) / self._std
        with torch.no_grad():
            xt = torch.tensor(X_n, dtype=torch.float32).to(self.device)
            h = self.model.encoder(xt)
            h = self.model.blocks(h)
            return h.cpu().numpy()
