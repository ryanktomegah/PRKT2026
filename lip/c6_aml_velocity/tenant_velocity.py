"""
tenant_velocity.py — Cross-tenant velocity isolation for P3 Platform Licensing.
Sprint 2b: C6 Extension.

Dual-write pattern:
  1. Tenant-scoped window: SHA-256(entity_id + salt + tenant_id)
     → enforces per-processor AML caps
  2. BPI-scoped window: SHA-256(entity_id + salt)
     → shared across all processors for cross-processor structuring detection

CIPHER domain: tenant isolation is a security boundary.
A BIC authorized under Processor A must NEVER have its velocity data
visible to Processor B.

The existing VelocityChecker is reused unmodified — tenant scoping is
achieved by computing a derived salt (salt + tenant_id bytes) so that
the same entity_id produces a different hash per tenant.
"""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, FrozenSet, Optional

from .velocity import RollingWindow, VelocityChecker, VelocityResult

logger = logging.getLogger(__name__)


@dataclass
class StructuringResult:
    """Result of cross-processor structuring detection.

    Attributes:
        flagged: True when the same entity appears in 2+ processor tenants
            with combined volume exceeding the dollar cap (soft flag only).
        tenant_count: Number of distinct processor tenants that recorded
            transactions for this entity.
        combined_volume: Total USD volume across all processor tenants.
        tenants: Frozenset of tenant IDs that recorded transactions.
    """

    flagged: bool
    tenant_count: int
    combined_volume: Decimal
    tenants: FrozenSet[str]


class StructuringDetector:
    """Detects cross-processor structuring (FATF R.21).

    Tracks which processor tenants have recorded transactions for each
    entity (by BPI-level hash) and the combined volume.  When the same
    entity appears in 2+ tenants AND combined volume exceeds the dollar
    cap, the detector flags it for CIPHER review.

    This is a **soft flag** — it does not block transactions. The flag
    is surfaced in the AMLResult for human review.

    In-memory storage for now. Redis-backed persistence will be added
    when the MIPLO API gateway is built (Sprint 2c).
    """

    def __init__(self, *, single_replica: bool = False) -> None:
        if not single_replica:
            raise ValueError(
                "StructuringDetector uses in-memory state that resets on "
                "redeploy and multiplies N× across replicas. Pass "
                "single_replica=True to acknowledge single-replica constraint, "
                "or configure a Redis-backed store (B7-10)."
            )
        if single_replica:
            import logging
            logging.getLogger(__name__).warning(
                "StructuringDetector running with single_replica=True — "
                "cross-tenant structuring detection will not work across replicas"
            )
        # entity_hash → {tenant_id: cumulative_volume}
        self._registry: Dict[str, Dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(Decimal)
        )

    def record(
        self,
        entity_hash: str,
        tenant_id: str,
        amount: Decimal,
    ) -> None:
        """Record a transaction for structuring detection.

        Called after a passing velocity check. Accumulates volume per
        (entity_hash, tenant_id) pair.

        Args:
            entity_hash: BPI-scoped SHA-256 hash of the entity.
            tenant_id: Processor tenant identifier.
            amount: Transaction amount in USD.
        """
        self._registry[entity_hash][tenant_id] += amount

    def check(
        self,
        entity_hash: str,
        dollar_cap: Decimal,
    ) -> StructuringResult:
        """Check for cross-processor structuring.

        Returns flagged=True when:
          1. Entity appears in 2+ processor tenants, AND
          2. Combined volume across all tenants exceeds dollar_cap

        When dollar_cap is 0 (unlimited), the volume check is skipped
        and only the multi-tenant presence is evaluated (but not flagged,
        since unlimited cap means no structuring concern).

        Args:
            entity_hash: BPI-scoped SHA-256 hash of the entity.
            dollar_cap: AML dollar cap from C8 token (0 = unlimited).

        Returns:
            StructuringResult with detection outcome.
        """
        tenant_volumes = self._registry.get(entity_hash, {})
        tenant_count = len(tenant_volumes)
        combined = sum(tenant_volumes.values(), Decimal("0"))
        tenants = frozenset(tenant_volumes.keys())

        # Must have 2+ tenants AND volume above cap to flag
        flagged = False
        if tenant_count >= 2 and dollar_cap > 0 and combined > dollar_cap:
            flagged = True
            logger.warning(
                "Cross-processor structuring detected: entity_hash=%s… "
                "tenants=%d combined_volume=%s cap=%s",
                entity_hash[:8],
                tenant_count,
                combined,
                dollar_cap,
            )

        return StructuringResult(
            flagged=flagged,
            tenant_count=tenant_count,
            combined_volume=combined,
            tenants=tenants,
        )


class TenantVelocityChecker:
    """Tenant-aware velocity checker with dual-write (P3 Platform Licensing).

    Wraps the existing VelocityChecker to provide:
      1. Tenant-scoped cap enforcement (derived salt = salt + tenant_id)
      2. BPI-level dual-write for cross-processor detection

    The underlying VelocityChecker is reused unmodified — all existing
    behavior (Lua atomic script, in-memory locking, EPG-25 TOCTOU
    protection) is preserved.

    Parameters
    ----------
    salt:
        Base salt bytes (same as direct-bank deployments use).
    tenant_id:
        Processor tenant identifier (e.g., 'FINASTRA_EU_001').
    bpi_rolling_window:
        Optional shared RollingWindow for BPI-level dual-write.
        When None, dual-write is skipped (tenant-only mode).
    redis_client:
        Optional Redis client for distributed state.
    """

    def __init__(
        self,
        salt: bytes,
        tenant_id: str,
        bpi_rolling_window: Optional[RollingWindow] = None,
        redis_client=None,
    ) -> None:
        self._tenant_id = tenant_id
        self._bpi_salt = salt
        # Derived salt: appending tenant_id bytes changes the hash for the
        # same entity, achieving namespace isolation without modifying
        # VelocityChecker internals.
        tenant_salt = salt + tenant_id.encode()
        self._tenant_checker = VelocityChecker(
            salt=tenant_salt, redis_client=redis_client,
        )
        self._bpi_window = bpi_rolling_window

    def tenant_entity_hash(self, entity_id: str) -> str:
        """Return the tenant-scoped SHA-256 hash for an entity.

        Exposed for testing — callers should not need this in production.
        """
        return self._tenant_checker._hash_entity(entity_id)

    def bpi_entity_hash(self, entity_id: str) -> str:
        """Return the BPI-scoped SHA-256 hash for an entity.

        This is the hash used for cross-processor structuring detection.
        """
        return hashlib.sha256(entity_id.encode() + self._bpi_salt).hexdigest()

    def _bpi_beneficiary_hash(self, beneficiary_id: str) -> str:
        """Return the BPI-scoped SHA-256 hash for a beneficiary."""
        return hashlib.sha256(beneficiary_id.encode() + self._bpi_salt).hexdigest()

    def check_and_record(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> VelocityResult:
        """Atomic check-and-record with dual-write.

        1. Enforce caps against the TENANT-scoped window (isolated per processor).
        2. If passing, also record in the BPI-scoped window (shared, for
           cross-processor structuring detection).
        3. If blocked, do NOT write to BPI window (blocked txns are not executed).

        Returns VelocityResult from the tenant-scoped check.
        """
        result = self._tenant_checker.check_and_record(
            entity_id, amount, beneficiary_id,
            dollar_cap_override=dollar_cap_override,
            count_cap_override=count_cap_override,
        )

        if result.passed and self._bpi_window is not None:
            bpi_entity_hash = self.bpi_entity_hash(entity_id)
            bpi_bene_hash = self._bpi_beneficiary_hash(beneficiary_id)
            self._bpi_window.add(bpi_entity_hash, amount, bpi_bene_hash)
            logger.debug(
                "Dual-write: tenant=%s entity_bpi_hash=%s… amount=%s",
                self._tenant_id,
                bpi_entity_hash[:8],
                amount,
            )

        return result
