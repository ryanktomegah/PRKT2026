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

from lip.c2_pd_model.tier_assignment import Tier


class KnownEntityRegistry:
    """Maps BIC codes → manual Tier overrides for creditworthy entities.

    Thread-safety: NOT thread-safe.  Callers responsible for external locking
    when used in concurrent contexts.

    Args:
        overrides: Optional pre-populated BIC → Tier mapping.  BICs are
            uppercased and stored case-insensitively.
    """

    def __init__(self, overrides: dict[str, Tier] | None = None) -> None:
        self._overrides: dict[str, Tier] = {}
        for bic, tier in (overrides or {}).items():
            self._overrides[bic.upper()] = tier

    def register(self, bic: str, tier: Tier) -> None:
        """Register a BIC with a manual tier override.

        Args:
            bic: SWIFT BIC code of the entity.
            tier: Manual tier assignment for this entity.
        """
        self._overrides[bic.upper()] = tier

    def unregister(self, bic: str) -> None:
        """Remove a BIC's tier override.

        No-op if the BIC is not registered.

        Args:
            bic: SWIFT BIC code to remove.
        """
        self._overrides.pop(bic.upper(), None)

    def lookup(self, bic: str) -> Tier | None:
        """Return the overridden tier for a BIC, or ``None`` if not registered.

        Args:
            bic: SWIFT BIC code to look up.  Case-insensitive.

        Returns:
            :class:`~lip.c2_pd_model.tier_assignment.Tier` override, or
            ``None`` when the entity is not in the registry.
        """
        return self._overrides.get(bic.upper())

    def is_registered(self, bic: str) -> bool:
        """Return ``True`` when the BIC has a registered tier override.

        Args:
            bic: SWIFT BIC code to test.  Case-insensitive.
        """
        return bic.upper() in self._overrides

    def list_all(self) -> dict[str, Tier]:
        """Return a snapshot copy of all registered BIC → Tier overrides.

        Returns:
            Dict mapping uppercased BIC strings to their :class:`Tier` values.
            Modifying the returned dict does not affect the registry.
        """
        return dict(self._overrides)
