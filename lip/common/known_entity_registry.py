"""
known_entity_registry.py — GAP-11: Known-entity tier-override registry.

Established, investment-grade banks that are new to LIP have no transaction
history in the system, so the standard data-availability rule classifies them
as Tier 3 (thin-file → 900–1500 bps fee).  This is economically incorrect
for well-known counterparties whose creditworthiness is already established
through public ratings and market relationships.

The ``KnownEntityRegistry`` provides a manual override layer: a compliance or
credit officer registers a BIC with an authoritative tier, and the C2 inference
engine checks the registry *before* running the data-availability assignment.
This preserves the deterministic tier-assignment rule for anonymous counterparties
while allowing trusted institutions to bypass it.

Usage::

    registry = KnownEntityRegistry()
    registry.register("JPMORGAN", Tier.TIER_1)
    tier = registry.lookup("JPMORGAN")  # → Tier.TIER_1
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from lip.c2_pd_model.tier_assignment import Tier

logger = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "lip:known_entity:"


class KnownEntityRegistry:
    """Maps BIC codes → manual Tier overrides for creditworthy entities.

    Thread-safe via ``threading.Lock`` (GAP-21).
    Optional Redis persistence (GAP-11): write-through on mutate,
    in-memory authoritative for reads, Redis for restart recovery.

    Args:
        overrides: Optional pre-populated BIC → Tier mapping.  BICs are
            uppercased and stored case-insensitively.
        redis_client: Optional Redis client. When None, pure in-memory.
    """

    def __init__(
        self,
        overrides: dict[str, Tier] | None = None,
        redis_client: Any = None,
    ) -> None:
        self._lock = threading.Lock()
        self._redis = redis_client
        self._overrides: dict[str, Tier] = {}
        for bic, tier in (overrides or {}).items():
            self._overrides[bic.upper()] = tier
        if self._redis is not None:
            self._load_from_redis()

    def _load_from_redis(self) -> None:
        try:
            cursor = 0
            while True:
                cursor, keys = self._redis.scan(cursor, match=f"{_REDIS_KEY_PREFIX}*", count=100)
                for key in keys:
                    key_str = key.decode() if isinstance(key, bytes) else str(key)
                    bic = key_str[len(_REDIS_KEY_PREFIX):]
                    val = self._redis.get(key)
                    if val is not None:
                        tier_int = int(val.decode() if isinstance(val, bytes) else val)
                        self._overrides[bic.upper()] = Tier(tier_int)
                if cursor == 0:
                    break
            logger.info("Loaded %d known entity overrides from Redis", len(self._overrides))
        except Exception as exc:
            logger.warning("Failed to load known entities from Redis: %s", exc)

    def register(self, bic: str, tier: Tier) -> None:
        """Register a BIC with a manual tier override.

        Args:
            bic: SWIFT BIC code of the entity.
            tier: Manual tier assignment for this entity.
        """
        normalized = bic.upper()
        with self._lock:
            self._overrides[normalized] = tier
        if self._redis is not None:
            try:
                self._redis.set(f"{_REDIS_KEY_PREFIX}{normalized}", str(tier.value))
            except Exception as exc:
                logger.warning("Redis set failed for known entity %s: %s", normalized, exc)

    def unregister(self, bic: str) -> None:
        """Remove a BIC's tier override.

        No-op if the BIC is not registered.

        Args:
            bic: SWIFT BIC code to remove.
        """
        normalized = bic.upper()
        with self._lock:
            self._overrides.pop(normalized, None)
        if self._redis is not None:
            try:
                self._redis.delete(f"{_REDIS_KEY_PREFIX}{normalized}")
            except Exception as exc:
                logger.warning("Redis delete failed for known entity %s: %s", normalized, exc)

    def lookup(self, bic: str) -> Tier | None:
        """Return the overridden tier for a BIC, or ``None`` if not registered.

        Args:
            bic: SWIFT BIC code to look up.  Case-insensitive.

        Returns:
            :class:`~lip.c2_pd_model.tier_assignment.Tier` override, or
            ``None`` when the entity is not in the registry.
        """
        normalized = bic.upper()
        with self._lock:
            result = self._overrides.get(normalized)
            if result is not None:
                return result
        # Redis fallback
        if self._redis is not None:
            try:
                val = self._redis.get(f"{_REDIS_KEY_PREFIX}{normalized}")
                if val is not None:
                    tier = Tier(int(val.decode() if isinstance(val, bytes) else val))
                    with self._lock:
                        self._overrides[normalized] = tier
                    return tier
            except Exception as exc:
                logger.warning("Redis get failed for known entity %s: %s", normalized, exc)
        return None

    def is_registered(self, bic: str) -> bool:
        """Return ``True`` when the BIC has a registered tier override.

        Args:
            bic: SWIFT BIC code to test.  Case-insensitive.
        """
        return self.lookup(bic) is not None

    def list_all(self) -> dict[str, Tier]:
        """Return a snapshot copy of all registered BIC → Tier overrides.

        Returns:
            Dict mapping uppercased BIC strings to their :class:`Tier` values.
            Modifying the returned dict does not affect the registry.
        """
        with self._lock:
            return dict(self._overrides)
