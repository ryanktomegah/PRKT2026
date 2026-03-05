"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

embeddings.py — Corridor embedding pipeline
C1 Spec Section 8: 128-dim vectors in Redis, weekly rebuild, cold start
"""

import hashlib
import json
import logging
import time
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM: int = 128
"""Dimensionality of stored corridor embeddings (C1 Spec §8.1)."""

EMBEDDING_TTL_SECONDS: int = 7 * 24 * 3600  # weekly
"""Default time-to-live for corridor embeddings (7 days)."""

_REDIS_KEY_PREFIX: str = "lip:embedding:"
_REDIS_META_PREFIX: str = "lip:embedding_meta:"


# ---------------------------------------------------------------------------
# CorridorEmbeddingPipeline
# ---------------------------------------------------------------------------

class CorridorEmbeddingPipeline:
    """Manages 128-dim corridor embeddings with Redis backing and cold-start.

    When no Redis client is provided the pipeline falls back to a pure
    in-memory dictionary, which is suitable for testing and local
    development.  In production, pass a connected ``redis.Redis`` instance.

    C1 Spec Section 8:
    - Embeddings are rebuilt weekly (TTL = 7 days).
    - Cold-start strategy: return the mean of same-currency-group embeddings,
      or a zero vector if none are available.

    Parameters
    ----------
    redis_client:
        Optional ``redis.Redis`` (or compatible) client.  When *None* an
        in-memory ``dict`` is used as a substitute.
    """

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client
        # In-memory fallback store: {key: (embedding_bytes, stored_at)}
        self._memory: Dict[str, tuple] = {}
        logger.info(
            "CorridorEmbeddingPipeline initialised (backend=%s)",
            "redis" if redis_client is not None else "in-memory",
        )

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(currency_pair: str) -> str:
        """Build the Redis / in-memory key for a currency pair.

        Parameters
        ----------
        currency_pair:
            Normalised pair string, e.g. ``"USD_EUR"``.

        Returns
        -------
        str
            Key of the form ``"lip:embedding:USD_EUR"``.
        """
        normalised = currency_pair.upper().replace("/", "_")
        return f"{_REDIS_KEY_PREFIX}{normalised}"

    @staticmethod
    def _make_meta_key(currency_pair: str) -> str:
        normalised = currency_pair.upper().replace("/", "_")
        return f"{_REDIS_META_PREFIX}{normalised}"

    # ------------------------------------------------------------------
    # Store / retrieve
    # ------------------------------------------------------------------

    def store(self, currency_pair: str, embedding: np.ndarray) -> None:
        """Persist a corridor embedding.

        Parameters
        ----------
        currency_pair:
            Identifier for the corridor (e.g. ``"USD_EUR"``).
        embedding:
            1-D array of shape ``(EMBEDDING_DIM,)`` = ``(128,)``.
        """
        if embedding.shape != (EMBEDDING_DIM,):
            raise ValueError(
                f"Expected embedding shape ({EMBEDDING_DIM},), got {embedding.shape}"
            )
        key = self._make_key(currency_pair)
        emb_bytes = embedding.astype(np.float64).tobytes()
        meta = json.dumps({"stored_at": time.time(), "currency_pair": currency_pair})

        if self._redis is not None:
            self._redis.set(key, emb_bytes, ex=EMBEDDING_TTL_SECONDS)
            self._redis.set(self._make_meta_key(currency_pair), meta, ex=EMBEDDING_TTL_SECONDS)
        else:
            self._memory[key] = (emb_bytes, time.time())

        logger.debug("Stored embedding for %s", currency_pair)

    def retrieve(self, currency_pair: str) -> Optional[np.ndarray]:
        """Fetch the stored embedding for a corridor, if present and not expired.

        Parameters
        ----------
        currency_pair:
            Corridor identifier.

        Returns
        -------
        np.ndarray or None
            128-dim float64 array, or *None* if not found / expired.
        """
        key = self._make_key(currency_pair)

        if self._redis is not None:
            raw = self._redis.get(key)
            if raw is None:
                return None
            return np.frombuffer(raw, dtype=np.float64).copy()

        if key not in self._memory:
            return None
        emb_bytes, stored_at = self._memory[key]
        if time.time() - stored_at > EMBEDDING_TTL_SECONDS:
            del self._memory[key]
            return None
        return np.frombuffer(emb_bytes, dtype=np.float64).copy()

    # ------------------------------------------------------------------
    # Cold-start
    # ------------------------------------------------------------------

    def cold_start_embedding(
        self, currency_pair: str, all_pairs: List[str]
    ) -> np.ndarray:
        """Produce a cold-start embedding for an unseen corridor.

        Strategy (C1 Spec §8.3):

        1. Find all *all_pairs* that share the same base or quote currency.
        2. Return the mean of their stored embeddings.
        3. If no related embeddings exist, return a zero vector.

        Parameters
        ----------
        currency_pair:
            Target corridor with no stored embedding.
        all_pairs:
            Full list of known currency-pair identifiers to search.

        Returns
        -------
        np.ndarray
            Shape ``(128,)``, dtype ``float64``.
        """
        parts = set(currency_pair.upper().replace("/", "_").split("_"))

        related: List[np.ndarray] = []
        for pair in all_pairs:
            if pair == currency_pair:
                continue
            pair_parts = set(pair.upper().replace("/", "_").split("_"))
            if parts & pair_parts:  # non-empty intersection
                emb = self.retrieve(pair)
                if emb is not None:
                    related.append(emb)

        if related:
            result = np.mean(np.stack(related, axis=0), axis=0)
            logger.info(
                "cold_start_embedding: %s — averaged %d related embeddings",
                currency_pair, len(related),
            )
            return result.astype(np.float64)

        logger.warning(
            "cold_start_embedding: no related embeddings for %s — returning zeros",
            currency_pair,
        )
        return np.zeros(EMBEDDING_DIM, dtype=np.float64)

    def get_or_cold_start(
        self, currency_pair: str, all_pairs: List[str]
    ) -> np.ndarray:
        """Return the stored embedding or fall back to cold-start.

        Parameters
        ----------
        currency_pair:
            Target corridor identifier.
        all_pairs:
            Full list of known pairs for cold-start search.

        Returns
        -------
        np.ndarray
            Shape ``(128,)``, dtype ``float64``.
        """
        emb = self.retrieve(currency_pair)
        if emb is not None:
            return emb
        return self.cold_start_embedding(currency_pair, all_pairs)

    # ------------------------------------------------------------------
    # Weekly rebuild
    # ------------------------------------------------------------------

    def rebuild_all(self, payments: List[dict], model: object) -> int:
        """Rebuild all corridor embeddings from a payment batch.

        Iterates over every unique ``currency_pair`` found in *payments*,
        runs the model's embedding extraction, and stores the result with a
        fresh TTL.

        The *model* object must expose either:

        - ``embed_corridor(payments_for_pair: list) -> np.ndarray``  (preferred), or
        - ``graphsage.forward(node_features, [], []) -> np.ndarray``  (fallback).

        Parameters
        ----------
        payments:
            Raw payment dicts, each with at minimum a ``"currency_pair"`` key.
        model:
            Trained model used to generate corridor embeddings.

        Returns
        -------
        int
            Number of corridor embeddings stored.
        """
        from collections import defaultdict

        pair_to_payments: Dict[str, list] = defaultdict(list)
        for p in payments:
            cp = str(p.get("currency_pair", "UNKNOWN"))
            pair_to_payments[cp].append(p)

        count = 0
        for currency_pair, pair_payments in pair_to_payments.items():
            try:
                if hasattr(model, "embed_corridor"):
                    embedding_full = model.embed_corridor(pair_payments)
                else:
                    # Fallback: use zero node features via GraphSAGE
                    from .features import NODE_FEATURE_DIM
                    node_feat = np.zeros(NODE_FEATURE_DIM, dtype=np.float64)
                    embedding_full = model.graphsage.forward(node_feat, [], [])

                # Project 384-dim GraphSAGE embedding down to 128-dim
                embedding_128 = self._project_to_128(embedding_full)
                self.store(currency_pair, embedding_128)
                count += 1
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                logger.error("rebuild_all: failed for %s: %s", currency_pair, exc)

        logger.info("rebuild_all: stored %d corridor embeddings", count)
        return count

    @staticmethod
    def _project_to_128(embedding: np.ndarray) -> np.ndarray:
        """Deterministically project an arbitrary-length vector to 128 dims.

        Uses a fixed random projection matrix seeded from a constant to
        ensure reproducibility across rebuilds.

        Parameters
        ----------
        embedding:
            Input vector of any length ≥ 1.

        Returns
        -------
        np.ndarray
            Shape ``(128,)``, dtype ``float64``.
        """
        if embedding.shape[0] == EMBEDDING_DIM:
            return embedding.astype(np.float64)

        rng = np.random.default_rng(seed=2024)
        proj = rng.standard_normal((embedding.shape[0], EMBEDDING_DIM))
        # Normalise columns for approximate isometry
        proj /= np.linalg.norm(proj, axis=0, keepdims=True) + 1e-12
        result = embedding.astype(np.float64) @ proj
        norm = np.linalg.norm(result)
        return (result / (norm + 1e-12)).astype(np.float64)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def embedding_age_seconds(self, currency_pair: str) -> Optional[float]:
        """Return how many seconds ago the embedding was stored.

        Parameters
        ----------
        currency_pair:
            Target corridor identifier.

        Returns
        -------
        float or None
            Age in seconds, or *None* if not found.
        """
        key = self._make_key(currency_pair)

        if self._redis is not None:
            meta_raw = self._redis.get(self._make_meta_key(currency_pair))
            if meta_raw is None:
                return None
            meta = json.loads(meta_raw)
            return time.time() - float(meta["stored_at"])

        if key not in self._memory:
            return None
        _, stored_at = self._memory[key]
        age = time.time() - stored_at
        if age > EMBEDDING_TTL_SECONDS:
            return None
        return age
