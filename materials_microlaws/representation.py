"""
Representation Learner Module
==============================
Graph Neural Network and equivariant models that map crystal/molecular
structures into latent feature vectors for symbolic regression.

Provides:
  - CrystalGraphEncoder: simple GCN-based encoder for crystal graphs
  - DescriptorAutoencoder: learns compressed descriptors from raw features
  - EquivariantFeaturizer: wrapper for SE(3)-equivariant representations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from loguru import logger

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not available; representation learner will use fallback PCA features.")

try:
    from torch_geometric.nn import GCNConv, global_mean_pool
    HAS_TORCH_GEOMETRIC = True
except ImportError:
    HAS_TORCH_GEOMETRIC = False


# ---------------------------------------------------------------------------
# Crystal Graph Encoder (GNN-based)
# ---------------------------------------------------------------------------

if HAS_TORCH:

    class CrystalGraphEncoder(nn.Module):
        """
        GCN-based encoder that maps a crystal graph to a fixed-size latent vector.

        Input: batched PyG Data objects with node features x and edge_index.
        Output: (batch_size, latent_dim) tensor.
        """

        def __init__(
            self,
            node_feat_dim: int = 92,  # one-hot atomic number
            hidden_dim: int = 128,
            latent_dim: int = 32,
            n_layers: int = 3,
            dropout: float = 0.1,
        ):
            super().__init__()
            self.layers = nn.ModuleList()
            self.layers.append(GCNConv(node_feat_dim, hidden_dim) if HAS_TORCH_GEOMETRIC
                               else nn.Linear(node_feat_dim, hidden_dim))
            for _ in range(n_layers - 1):
                self.layers.append(GCNConv(hidden_dim, hidden_dim) if HAS_TORCH_GEOMETRIC
                                   else nn.Linear(hidden_dim, hidden_dim))
            self.proj = nn.Linear(hidden_dim, latent_dim)
            self.dropout = dropout

        def forward(self, x, edge_index=None, batch=None):
            h = x
            for layer in self.layers:
                if HAS_TORCH_GEOMETRIC and isinstance(layer, GCNConv):
                    h = layer(h, edge_index)
                else:
                    h = layer(h)
                h = F.relu(h)
                h = F.dropout(h, p=self.dropout, training=self.training)

            # Global pooling
            if HAS_TORCH_GEOMETRIC and batch is not None:
                h = global_mean_pool(h, batch)
            elif batch is None:
                h = h.mean(dim=0, keepdim=True)

            return self.proj(h)


    class DescriptorAutoencoder(nn.Module):
        """
        Learn compressed, nonlinearly mixed descriptors from the raw descriptor matrix.

        This serves as the "representation learner" when we don't have crystal graphs
        but do have a set of physically meaningful descriptors.
        """

        def __init__(self, input_dim: int, latent_dim: int = 8, hidden_dim: int = 64):
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, latent_dim),
            )
            self.decoder = nn.Sequential(
                nn.Linear(latent_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, input_dim),
            )

        def forward(self, x):
            z = self.encoder(x)
            x_hat = self.decoder(z)
            return x_hat, z

        def encode(self, x):
            return self.encoder(x)


# ---------------------------------------------------------------------------
# Fallback: PCA-based feature compression (no PyTorch needed)
# ---------------------------------------------------------------------------

class PCAFeaturizer:
    """Simple PCA-based descriptor compression as a lightweight fallback."""

    def __init__(self, n_components: int = 8):
        self.n_components = n_components
        self._mean = None
        self._components = None
        self._fitted = False

    def fit(self, X: np.ndarray) -> "PCAFeaturizer":
        self._mean = X.mean(axis=0)
        X_centered = X - self._mean
        # SVD-based PCA
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        self._components = Vt[:self.n_components]
        self._fitted = True
        explained = (S[:self.n_components] ** 2).sum() / (S ** 2).sum()
        logger.info(f"PCA fitted: {self.n_components} components, "
                    f"explained variance = {explained:.3f}")
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("PCAFeaturizer not fitted yet")
        return (X - self._mean) @ self._components.T


# ---------------------------------------------------------------------------
# Unified representation learning interface
# ---------------------------------------------------------------------------

@dataclass
class LearnedFeatures:
    """Container for learned latent features alongside original descriptors."""
    original: np.ndarray       # (N, D_orig)
    latent: np.ndarray         # (N, D_latent)
    descriptor_names: list[str]
    latent_names: list[str]
    importance_scores: Optional[np.ndarray] = None  # (D_orig,) feature importance


def learn_representations(
    X: np.ndarray,
    descriptor_names: list[str],
    method: str = "autoencoder",
    latent_dim: int = 8,
    epochs: int = 200,
    lr: float = 1e-3,
) -> LearnedFeatures:
    """
    Learn compressed representations from descriptor matrix.

    Parameters
    ----------
    X : (N, D) array of descriptor values
    descriptor_names : names of each descriptor column
    method : "autoencoder" (requires torch) or "pca"
    latent_dim : dimension of latent space
    epochs : training epochs for autoencoder
    lr : learning rate
    """
    if method == "autoencoder" and HAS_TORCH:
        return _learn_autoencoder(X, descriptor_names, latent_dim, epochs, lr)
    else:
        return _learn_pca(X, descriptor_names, latent_dim)


def _learn_autoencoder(
    X: np.ndarray, names: list[str], latent_dim: int, epochs: int, lr: float
) -> LearnedFeatures:
    """Train autoencoder and extract latent features + importance."""
    logger.info(f"Training DescriptorAutoencoder: {X.shape[1]}→{latent_dim}, {epochs} epochs")

    # Normalize
    mu, sigma = X.mean(0), X.std(0) + 1e-8
    X_norm = (X - mu) / sigma

    model = DescriptorAutoencoder(X.shape[1], latent_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    X_t = torch.tensor(X_norm, dtype=torch.float32)

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        x_hat, z = model(X_t)
        loss = F.mse_loss(x_hat, X_t)
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 50 == 0:
            logger.debug(f"  Epoch {epoch+1}/{epochs}, loss={loss.item():.5f}")

    model.eval()
    with torch.no_grad():
        _, Z = model(X_t)
        Z_np = Z.numpy()

    # Feature importance via gradient magnitude
    X_t.requires_grad_(True)
    _, z = model(X_t)
    grad_sum = torch.zeros(X.shape[1])
    for j in range(latent_dim):
        model.zero_grad()
        if X_t.grad is not None:
            X_t.grad.zero_()
        z[:, j].sum().backward(retain_graph=True)
        grad_sum += X_t.grad.abs().mean(dim=0)
    importance = grad_sum.detach().numpy()
    importance = importance / importance.sum()

    latent_names = [f"z_{i}" for i in range(latent_dim)]

    logger.info(f"  Top-3 important descriptors: "
                f"{', '.join(names[i] for i in np.argsort(-importance)[:3])}")

    return LearnedFeatures(
        original=X, latent=Z_np,
        descriptor_names=names, latent_names=latent_names,
        importance_scores=importance,
    )


def _learn_pca(X: np.ndarray, names: list[str], latent_dim: int) -> LearnedFeatures:
    """PCA fallback for representation learning."""
    pca = PCAFeaturizer(n_components=latent_dim)
    pca.fit(X)
    Z = pca.transform(X)

    # Importance = loading magnitudes
    importance = np.abs(pca._components).sum(axis=0)
    importance = importance / importance.sum()

    latent_names = [f"pc_{i}" for i in range(latent_dim)]

    return LearnedFeatures(
        original=X, latent=Z,
        descriptor_names=names, latent_names=latent_names,
        importance_scores=importance,
    )
