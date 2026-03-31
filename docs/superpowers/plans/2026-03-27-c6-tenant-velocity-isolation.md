# Sprint 2b: C6 Cross-Tenant Velocity Isolation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tenant isolation to C6 AML velocity controls so each processor's velocity counters are partitioned, while BPI retains a platform-wide view for cross-processor structuring detection.

**Architecture:** A new `TenantVelocityChecker` wraps the existing `VelocityChecker` with dual-write: cap enforcement uses tenant-scoped hashing (`SHA-256(entity_id + salt + tenant_id)`), while a shared BPI-level `RollingWindow` records every passing transaction for cross-processor detection. A new `StructuringDetector` flags entities that appear across 2+ processor tenants within 24 hours with combined volume exceeding the AML dollar cap. `AMLChecker` gains an optional `tenant_id` parameter — when absent, existing single-tenant behavior is preserved (100% backward compatible).

**Tech Stack:** Python 3.14, dataclasses, hashlib SHA-256, threading locks, Decimal arithmetic, pytest, ruff

---

## Context

This is Sprint 2b in Phase 2 of a 23-session build program. Sprint 2a (C8 processor token extension) is complete — `LicenseToken` now supports `PROCESSOR` type with `sub_licensee_bics`, `ProcessorLicenseeContext`, and revenue metering.

**What exists:** C6 has a fully functional `VelocityChecker` with Redis and in-memory backends, `AMLChecker` facade (sanctions → velocity → anomaly), `CrossLicenseeAggregator` for cross-licensee aggregation, and `SaltRotationManager` for annual salt rotation with 30-day overlap.

**What this builds:** Tenant-scoped velocity partitioning, dual-write to BPI-level window, cross-processor structuring detection, and `AMLChecker` tenant awareness. No existing classes are modified structurally — all new logic lives in a new file, and `AMLChecker` gains a backward-compatible parameter.

**What this enables:** Sprint 2c (MIPLO API gateway) can pass `TenantContext.tenant_id` through the pipeline to C6, and Sprint 2d (multi-tenant settlement) can scope C3 tracking by tenant.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/c6_aml_velocity/tenant_velocity.py` | TenantVelocityChecker (dual-write), StructuringDetector, StructuringResult |
| Modify | `lip/c6_aml_velocity/aml_checker.py` | Add `tenant_id` param to `check()`, lazy tenant checker registry |
| Modify | `lip/c6_aml_velocity/__init__.py` | Export new classes |
| Create | `lip/tests/test_c6_tenant_velocity.py` | TDD tests for tenant isolation + structuring detection |

**NOT modified (important):**
- `velocity.py` — existing `VelocityChecker` and `RollingWindow` are reused as-is
- `cross_licensee.py` — existing `CrossLicenseeAggregator` untouched (it handles cross-LICENSEE aggregation; this sprint handles cross-PROCESSOR aggregation within a single licensee deployment)
- `pipeline.py` — pipeline integration deferred to Sprint 2c (MIPLO API gateway)

---

## Design Decisions

### D1: Wrapper vs. In-Place Modification
`TenantVelocityChecker` wraps `VelocityChecker` rather than modifying it. Reason: `VelocityChecker` has 11 existing tests, a Lua atomic script, and dual Redis/in-memory backends. Modifying it risks breaking existing non-tenant deployments. The wrapper creates a tenant-scoped instance by computing a derived salt (`salt + tenant_id.encode()`) and delegates all cap enforcement logic to the existing tested code.

### D2: BPI-Level Window Sharing
The BPI-level `RollingWindow` is created externally and passed into each `TenantVelocityChecker`. In production (Redis backend), all processors naturally share the same Redis sorted sets. In tests (in-memory), the test harness creates one `RollingWindow` and passes it to multiple tenant checkers. This mirrors the production sharing without requiring any Redis-specific test infrastructure.

### D3: Structuring Detection Scope
Structuring detection is a **soft flag** (like anomaly detection), not a hard block. Reason: cross-processor structuring could be legitimate (a bank's corporate treasury legitimately using multiple processors). The flag triggers CIPHER review, not automatic rejection. This matches FATF R.21 guidance — suspicious activity reporting, not automatic blocking.

### D4: Backward Compatibility
When `tenant_id` is `None` (default), `AMLChecker.check()` follows the exact existing code path. No existing test changes. No behavioral change for single-tenant (BANK-type) deployments.

---

## Task 1: Write TDD Tests for Tenant Velocity Isolation

**Files:**
- Create: `lip/tests/test_c6_tenant_velocity.py`

- [ ] **Step 1: Write the complete test file**

```python
"""
test_c6_tenant_velocity.py — Tests for P3 Sprint 2b: C6 cross-tenant velocity isolation.

CIPHER domain: tenant isolation is a security boundary. A BIC authorized under
Processor A must NEVER have its velocity data visible to Processor B.

QUANT domain: structuring detection arithmetic must be exact (Decimal).
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.c6_aml_velocity.velocity import RollingWindow, VelocityChecker
from lip.c6_aml_velocity.tenant_velocity import (
    StructuringDetector,
    StructuringResult,
    TenantVelocityChecker,
)
from lip.c6_aml_velocity.aml_checker import AMLChecker

_SALT = b"test_salt_32bytes_long_exactly__"
_TEST_DOLLAR_CAP = Decimal("1000000")
_TEST_COUNT_CAP = 100


# ── Tenant Velocity Isolation Tests (CIPHER) ────────────────────────────────


class TestTenantVelocityIsolation:
    """CIPHER: tenant A's velocity must be invisible to tenant B."""

    def test_same_entity_different_tenants_isolated(self):
        """Same entity_id under two tenants produces different hashes → separate windows."""
        shared_bpi_window = RollingWindow()
        checker_a = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=shared_bpi_window,
        )
        checker_b = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_B",
            bpi_rolling_window=shared_bpi_window,
        )

        # Saturate entity under tenant A
        checker_a.check_and_record(
            "entity_1", _TEST_DOLLAR_CAP - Decimal("1"), "bene_1",
            dollar_cap_override=_TEST_DOLLAR_CAP,
        )

        # Same entity under tenant B should still pass (isolated window)
        result = checker_b.check_and_record(
            "entity_1", Decimal("500000"), "bene_1",
            dollar_cap_override=_TEST_DOLLAR_CAP,
        )
        assert result.passed is True

    def test_same_tenant_same_entity_accumulates(self):
        """Within the same tenant, velocity accumulates normally."""
        shared_bpi_window = RollingWindow()
        checker = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=shared_bpi_window,
        )

        checker.check_and_record(
            "entity_2", _TEST_DOLLAR_CAP - Decimal("1"), "bene_1",
            dollar_cap_override=_TEST_DOLLAR_CAP,
        )
        result = checker.check_and_record(
            "entity_2", Decimal("2"), "bene_2",
            dollar_cap_override=_TEST_DOLLAR_CAP,
        )
        assert result.passed is False
        assert result.reason == "DOLLAR_CAP_EXCEEDED"

    def test_tenant_hash_differs_from_bpi_hash(self):
        """Tenant-scoped hash must differ from BPI-scoped hash for the same entity."""
        checker = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=RollingWindow(),
        )
        tenant_hash = checker.tenant_entity_hash("entity_x")
        bpi_hash = checker.bpi_entity_hash("entity_x")
        assert tenant_hash != bpi_hash
        assert len(tenant_hash) == 64
        assert len(bpi_hash) == 64


class TestDualWrite:
    """CIPHER: every passing transaction must be recorded in BOTH windows."""

    def test_passing_transaction_written_to_bpi_window(self):
        """After a passing check, the BPI-level window must have the record."""
        shared_bpi_window = RollingWindow()
        checker = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=shared_bpi_window,
        )

        result = checker.check_and_record(
            "entity_3", Decimal("100000"), "bene_1",
        )
        assert result.passed is True

        bpi_hash = checker.bpi_entity_hash("entity_3")
        bpi_volume = shared_bpi_window.get_volume(bpi_hash)
        assert bpi_volume == Decimal("100000")

    def test_blocked_transaction_not_written_to_bpi_window(self):
        """A blocked transaction must NOT be written to the BPI window."""
        shared_bpi_window = RollingWindow()
        checker = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=shared_bpi_window,
        )

        # Saturate tenant window
        checker.check_and_record(
            "entity_4", _TEST_DOLLAR_CAP - Decimal("1"), "bene_1",
            dollar_cap_override=_TEST_DOLLAR_CAP,
        )
        # This should be blocked
        result = checker.check_and_record(
            "entity_4", Decimal("2"), "bene_2",
            dollar_cap_override=_TEST_DOLLAR_CAP,
        )
        assert result.passed is False

        # BPI window should only have the first transaction (not the blocked one)
        bpi_hash = checker.bpi_entity_hash("entity_4")
        bpi_volume = shared_bpi_window.get_volume(bpi_hash)
        assert bpi_volume == _TEST_DOLLAR_CAP - Decimal("1")

    def test_dual_write_both_tenants_accumulate_in_bpi(self):
        """BPI-level window accumulates volume from BOTH tenants."""
        shared_bpi_window = RollingWindow()
        checker_a = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=shared_bpi_window,
        )
        checker_b = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_B",
            bpi_rolling_window=shared_bpi_window,
        )

        checker_a.check_and_record("entity_5", Decimal("300000"), "bene_1")
        checker_b.check_and_record("entity_5", Decimal("400000"), "bene_2")

        # BPI-level sees combined volume
        bpi_hash = checker_a.bpi_entity_hash("entity_5")
        bpi_volume = shared_bpi_window.get_volume(bpi_hash)
        assert bpi_volume == Decimal("700000")

    def test_no_bpi_window_still_works(self):
        """When bpi_rolling_window is None, tenant checker works without dual-write."""
        checker = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=None,
        )
        result = checker.check_and_record(
            "entity_6", Decimal("1000"), "bene_1",
        )
        assert result.passed is True


# ── Structuring Detection Tests (CIPHER + QUANT) ────────────────────────────


class TestStructuringDetector:
    """Cross-processor structuring: same entity across 2+ tenants within 24h."""

    def test_single_tenant_no_flag(self):
        """Entity in only one tenant is not structuring."""
        detector = StructuringDetector()
        detector.record("entity_hash_abc", "PROCESSOR_A", Decimal("500000"))

        result = detector.check("entity_hash_abc", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is False

    def test_two_tenants_below_cap_no_flag(self):
        """Entity in 2 tenants but combined volume below cap: not flagged."""
        detector = StructuringDetector()
        detector.record("entity_hash_def", "PROCESSOR_A", Decimal("100000"))
        detector.record("entity_hash_def", "PROCESSOR_B", Decimal("200000"))

        result = detector.check("entity_hash_def", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is False

    def test_two_tenants_above_cap_flagged(self):
        """Entity in 2 tenants with combined volume above cap: flagged."""
        detector = StructuringDetector()
        detector.record("entity_hash_ghi", "PROCESSOR_A", Decimal("600000"))
        detector.record("entity_hash_ghi", "PROCESSOR_B", Decimal("500000"))

        result = detector.check("entity_hash_ghi", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is True
        assert result.tenant_count == 2
        assert result.combined_volume == Decimal("1100000")

    def test_three_tenants_flagged(self):
        """Entity across 3 tenants: flagged when above cap."""
        detector = StructuringDetector()
        detector.record("entity_hash_jkl", "PROC_A", Decimal("400000"))
        detector.record("entity_hash_jkl", "PROC_B", Decimal("400000"))
        detector.record("entity_hash_jkl", "PROC_C", Decimal("400000"))

        result = detector.check("entity_hash_jkl", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is True
        assert result.tenant_count == 3

    def test_unlimited_cap_never_flags_for_volume(self):
        """When dollar_cap is 0 (unlimited), volume check is skipped."""
        detector = StructuringDetector()
        detector.record("entity_hash_mno", "PROC_A", Decimal("99999999"))
        detector.record("entity_hash_mno", "PROC_B", Decimal("99999999"))

        result = detector.check("entity_hash_mno", dollar_cap=Decimal("0"))
        assert result.flagged is False

    def test_result_has_correct_fields(self):
        """StructuringResult exposes flagged, tenant_count, combined_volume, tenants."""
        detector = StructuringDetector()
        detector.record("entity_hash_pqr", "PROC_X", Decimal("800000"))
        detector.record("entity_hash_pqr", "PROC_Y", Decimal("300000"))

        result = detector.check("entity_hash_pqr", dollar_cap=_TEST_DOLLAR_CAP)
        assert isinstance(result, StructuringResult)
        assert isinstance(result.flagged, bool)
        assert isinstance(result.tenant_count, int)
        assert isinstance(result.combined_volume, Decimal)
        assert isinstance(result.tenants, frozenset)

    def test_same_tenant_recorded_twice_counts_once(self):
        """Multiple transactions from same tenant count as 1 tenant."""
        detector = StructuringDetector()
        detector.record("entity_hash_stu", "PROC_A", Decimal("200000"))
        detector.record("entity_hash_stu", "PROC_A", Decimal("300000"))

        result = detector.check("entity_hash_stu", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.tenant_count == 1
        assert result.combined_volume == Decimal("500000")
        assert result.flagged is False


# ── AMLChecker Tenant Integration Tests ──────────────────────────────────────


class TestAMLCheckerTenantIntegration:
    """AMLChecker with tenant_id routes through TenantVelocityChecker."""

    def _make_tenant_aml_checker(self) -> AMLChecker:
        return AMLChecker(
            velocity_checker=VelocityChecker(salt=_SALT),
            entity_name_resolver=None,
        )

    def test_check_without_tenant_id_uses_existing_path(self):
        """Backward compat: no tenant_id → existing VelocityChecker path."""
        checker = self._make_tenant_aml_checker()
        result = checker.check("entity_ok", Decimal("1000"), "bene_ok")
        assert result.passed is True
        assert result.structuring_flagged is False

    def test_check_with_tenant_id_uses_tenant_checker(self):
        """With tenant_id, C6 uses TenantVelocityChecker."""
        checker = self._make_tenant_aml_checker()
        result = checker.check(
            "entity_ok", Decimal("1000"), "bene_ok",
            tenant_id="PROCESSOR_A",
        )
        assert result.passed is True

    def test_tenant_isolation_through_aml_checker(self):
        """Two tenants via AMLChecker: tenant A's cap doesn't affect tenant B."""
        checker = self._make_tenant_aml_checker()

        # Saturate tenant A
        checker.check(
            "entity_shared", _TEST_DOLLAR_CAP - Decimal("1"), "bene_1",
            dollar_cap_override=_TEST_DOLLAR_CAP,
            tenant_id="PROCESSOR_A",
        )
        # Tenant A blocked
        result_a = checker.check(
            "entity_shared", Decimal("2"), "bene_2",
            dollar_cap_override=_TEST_DOLLAR_CAP,
            tenant_id="PROCESSOR_A",
        )
        assert result_a.passed is False

        # Tenant B still passes
        result_b = checker.check(
            "entity_shared", Decimal("500000"), "bene_3",
            dollar_cap_override=_TEST_DOLLAR_CAP,
            tenant_id="PROCESSOR_B",
        )
        assert result_b.passed is True

    def test_cross_processor_structuring_detected(self):
        """Entity across 2 tenants above cap triggers structuring flag."""
        checker = self._make_tenant_aml_checker()

        checker.check(
            "entity_struct", Decimal("600000"), "bene_1",
            dollar_cap_override=_TEST_DOLLAR_CAP,
            tenant_id="PROCESSOR_A",
        )
        result = checker.check(
            "entity_struct", Decimal("500000"), "bene_2",
            dollar_cap_override=_TEST_DOLLAR_CAP,
            tenant_id="PROCESSOR_B",
        )
        assert result.passed is True  # velocity passes per-tenant
        assert result.structuring_flagged is True  # but BPI-level structuring detected


class TestTenantVelocityCheckerConcurrency:
    """EPG-25: tenant check_and_record must be atomic (no TOCTOU)."""

    def test_concurrent_check_and_record_respects_cap(self):
        """Multiple threads on same tenant must not exceed cap."""
        import threading

        count_cap = 3
        shared_bpi_window = RollingWindow()
        checker = TenantVelocityChecker(
            salt=_SALT, tenant_id="PROCESSOR_A",
            bpi_rolling_window=shared_bpi_window,
        )

        passes = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            result = checker.check_and_record(
                "entity_conc", Decimal("100000"), "bene_conc",
                count_cap_override=count_cap,
            )
            if result.passed:
                passes.append(1)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(passes) == count_cap
```

- [ ] **Step 2: Run tests to verify they fail (no implementation yet)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_tenant_velocity.py -v 2>&1 | head -15`
Expected: ImportError for `TenantVelocityChecker`, `StructuringDetector`, `StructuringResult`

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_c6_tenant_velocity.py
git commit -m "test(c6): add TDD suite for tenant velocity isolation and structuring detection"
```

---

## Task 2: Implement TenantVelocityChecker and StructuringDetector

**Files:**
- Create: `lip/c6_aml_velocity/tenant_velocity.py`

- [ ] **Step 1: Write the tenant velocity module**

```python
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

    def __init__(self) -> None:
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
```

- [ ] **Step 2: Run the TDD tests (tenant velocity + structuring)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_tenant_velocity.py::TestTenantVelocityIsolation -v`
Expected: ALL PASS

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_tenant_velocity.py::TestDualWrite -v`
Expected: ALL PASS

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_tenant_velocity.py::TestStructuringDetector -v`
Expected: ALL PASS

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_tenant_velocity.py::TestTenantVelocityCheckerConcurrency -v`
Expected: ALL PASS

- [ ] **Step 3: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/c6_aml_velocity/tenant_velocity.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add lip/c6_aml_velocity/tenant_velocity.py
git commit -m "feat(c6): implement TenantVelocityChecker with dual-write and StructuringDetector"
```

---

## Task 3: Extend AMLChecker with Tenant Support

**Files:**
- Modify: `lip/c6_aml_velocity/aml_checker.py`

- [ ] **Step 1: Add structuring_flagged field to AMLResult (line 82, after velocity_result)**

Add after `velocity_result: Optional[VelocityResult] = None`:

```python
    structuring_flagged: bool = False
```

- [ ] **Step 2: Replace velocity import and add tenant imports (line 24)**

Replace the existing line 24:
```python
from .velocity import VelocityChecker, VelocityResult
```
With:
```python
from .tenant_velocity import StructuringDetector, TenantVelocityChecker
from .velocity import DOLLAR_CAP_USD, RollingWindow, VelocityChecker, VelocityResult
```

- [ ] **Step 3: Add tenant infrastructure to __init__ (after line 170, after self._resolve_name)**

Add after `self._resolve_name = entity_name_resolver`:

```python
        # P3 tenant velocity infrastructure (Sprint 2b)
        self._tenant_checkers: dict[str, TenantVelocityChecker] = {}
        self._bpi_rolling_window = RollingWindow(redis_client=redis_client)
        self._structuring_detector = StructuringDetector()
        self._base_salt = velocity_checker.salt
```

- [ ] **Step 4: Add tenant_id parameter to check() method (line 174)**

Update `check()` signature — add `tenant_id: Optional[str] = None` parameter:

Change:
```python
    def check(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        entity_name: Optional[str] = None,
        beneficiary_name: Optional[str] = None,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> AMLResult:
```

To:
```python
    def check(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        entity_name: Optional[str] = None,
        beneficiary_name: Optional[str] = None,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
        tenant_id: Optional[str] = None,
    ) -> AMLResult:
```

- [ ] **Step 5: Add _get_or_create_tenant_checker helper method (after check())**

Add after the `check()` method:

```python
    def _get_or_create_tenant_checker(self, tenant_id: str) -> TenantVelocityChecker:
        """Lazily create a TenantVelocityChecker for the given tenant."""
        if tenant_id not in self._tenant_checkers:
            self._tenant_checkers[tenant_id] = TenantVelocityChecker(
                salt=self._base_salt,
                tenant_id=tenant_id,
                bpi_rolling_window=self._bpi_rolling_window,
                redis_client=self._velocity._redis,
            )
            logger.info("Created TenantVelocityChecker for tenant=%s", tenant_id)
        return self._tenant_checkers[tenant_id]
```

- [ ] **Step 6: Replace velocity step in check() to route through tenant checker when tenant_id is set**

Replace the velocity step (the block starting with `# ── Step 2: Velocity controls`) with:

```python
        # ── Step 2: Velocity controls (atomic check-and-record — EPG-25) ────────
        structuring_flagged = False

        if tenant_id is not None:
            # P3 tenant-aware path: dual-write to tenant + BPI windows
            tenant_checker = self._get_or_create_tenant_checker(tenant_id)
            vel_result = tenant_checker.check_and_record(
                entity_id, amount, beneficiary_id,
                dollar_cap_override=dollar_cap_override,
                count_cap_override=count_cap_override,
            )

            if vel_result.passed:
                # Record for structuring detection
                bpi_hash = tenant_checker.bpi_entity_hash(entity_id)
                self._structuring_detector.record(bpi_hash, tenant_id, amount)
                # Check cross-processor structuring (soft flag)
                structuring_result = self._structuring_detector.check(
                    bpi_hash,
                    dollar_cap=dollar_cap_override if dollar_cap_override is not None else DOLLAR_CAP_USD,
                )
                if structuring_result.flagged:
                    structuring_flagged = True
                    triggered_rules.append("CROSS_PROCESSOR_STRUCTURING")
                    logger.warning(
                        "Cross-processor structuring: entity_bpi_hash=%s… "
                        "tenants=%d volume=%s",
                        bpi_hash[:8],
                        structuring_result.tenant_count,
                        structuring_result.combined_volume,
                    )
        else:
            # Existing single-tenant path (backward compatible)
            vel_result = self._velocity.check_and_record(
                entity_id, amount, beneficiary_id,
                dollar_cap_override=dollar_cap_override,
                count_cap_override=count_cap_override,
            )

        if not vel_result.passed:
            triggered_rules.append(vel_result.reason or "VELOCITY_BLOCKED")
            logger.warning(
                "Velocity hard block: reason=%s entity_hash=%s",
                vel_result.reason,
                vel_result.entity_id_hash[:8],
            )
            return AMLResult(
                passed=False,
                reason=vel_result.reason,
                anomaly_flagged=False,
                triggered_rules=triggered_rules,
                sanctions_hits=[],
                velocity_result=vel_result,
                structuring_flagged=False,
            )
```

- [ ] **Step 7: Update the return statement at the end of check() to include structuring_flagged**

Change the final return (around line 303):

```python
        return AMLResult(
            passed=True,
            reason=None,
            anomaly_flagged=anomaly_flagged,
            triggered_rules=triggered_rules,
            sanctions_hits=[],
            velocity_result=vel_result,
            structuring_flagged=structuring_flagged,
        )
```

- [ ] **Step 8: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/c6_aml_velocity/aml_checker.py`
Expected: no errors

- [ ] **Step 9: Run AMLChecker tenant integration tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_tenant_velocity.py::TestAMLCheckerTenantIntegration -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add lip/c6_aml_velocity/aml_checker.py
git commit -m "feat(c6): add tenant_id param to AMLChecker with lazy tenant checker + structuring detection"
```

---

## Task 4: Update Exports

**Files:**
- Modify: `lip/c6_aml_velocity/__init__.py`

- [ ] **Step 1: Add new exports**

Change:
```python
from .aml_checker import AMLChecker, AMLResult
from .anomaly import AnomalyDetector
from .cross_licensee import CrossLicenseeAggregator
from .salt_rotation import SaltRotationManager
from .sanctions import SanctionsScreener
from .velocity import VelocityChecker, VelocityResult

__all__ = [
    "VelocityChecker", "VelocityResult", "CrossLicenseeAggregator",
    "SanctionsScreener", "AnomalyDetector", "SaltRotationManager",
    "AMLChecker", "AMLResult",
]
```

To:
```python
from .aml_checker import AMLChecker, AMLResult
from .anomaly import AnomalyDetector
from .cross_licensee import CrossLicenseeAggregator
from .salt_rotation import SaltRotationManager
from .sanctions import SanctionsScreener
from .tenant_velocity import StructuringDetector, StructuringResult, TenantVelocityChecker
from .velocity import VelocityChecker, VelocityResult

__all__ = [
    "VelocityChecker", "VelocityResult", "CrossLicenseeAggregator",
    "SanctionsScreener", "AnomalyDetector", "SaltRotationManager",
    "AMLChecker", "AMLResult",
    "TenantVelocityChecker", "StructuringDetector", "StructuringResult",
]
```

- [ ] **Step 2: Commit**

```bash
git add lip/c6_aml_velocity/__init__.py
git commit -m "feat(c6): export TenantVelocityChecker, StructuringDetector, StructuringResult"
```

---

## Task 5: Regression Check

- [ ] **Step 1: Run all new tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_tenant_velocity.py -v`
Expected: ALL PASS (should be ~20 tests)

- [ ] **Step 2: Run existing C6 tests (backward compatibility)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c6_aml.py -v`
Expected: ALL PASS (27 existing tests, no changes)

- [ ] **Step 3: Run ruff on entire lip/ directory**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/`
Expected: zero errors

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py -q 2>&1 | tail -10`
Expected: ~1592+ tests pass, zero failures

---

## Verification Checklist

Before declaring Sprint 2b complete:

1. [ ] `ruff check lip/` — zero errors
2. [ ] `python -m pytest lip/tests/test_c6_aml.py -v` — all 27 existing C6 tests pass (backward compat)
3. [ ] `python -m pytest lip/tests/test_c6_tenant_velocity.py -v` — all new tests pass
4. [ ] `python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py` — no regressions
5. [ ] Manual: `TenantVelocityChecker` uses derived salt (`salt + tenant_id.encode()`)
6. [ ] Manual: BPI-scoped window shared across tenant checkers (single `RollingWindow` instance)
7. [ ] Manual: Blocked transactions NOT written to BPI window
8. [ ] Manual: `StructuringDetector` flags only when 2+ tenants AND volume > cap
9. [ ] Manual: `AMLChecker.check()` without `tenant_id` follows exact existing code path
10. [ ] Manual: No secrets, artifacts/, or c6_corpus_*.json in any committed file

---

## CIPHER / QUANT Review Notes

**CIPHER — Tenant Isolation Boundary:**
The derived salt (`salt + tenant_id.encode()`) produces a completely different SHA-256 hash for the same entity under different tenants. Even with access to Redis, Processor A cannot derive Processor B's entity hashes without knowing B's tenant_id. This is defense-in-depth on top of L1 (token auth) and L2 (Redis namespace).

**CIPHER — Structuring Detection is Soft:**
Cross-processor structuring detection is advisory (soft flag). It does NOT block transactions because legitimate cross-processor volume exists (e.g., bank treasury using multiple PSPs). The flag triggers CIPHER review through the triggered_rules audit trail. Hard-blocking structuring would require regulatory counsel sign-off per FATF R.21.

**CIPHER — BPI Window Privacy:**
The BPI-level window uses `SHA-256(entity_id + salt)` — the SAME hash as single-tenant mode. This means BPI staff with Redis access can see aggregate entity volume but cannot attribute it to a specific processor tenant (unless they also have the structuring detector's tenant_registry). Tenant attribution requires application-level access, not Redis-level.

**QUANT — No Financial Math Changes:**
This sprint does not modify fee calculations, maturity windows, or any QUANT-controlled constant. The only Decimal arithmetic is in StructuringDetector (volume accumulation), which is trivial summation.

---

## Next Sprint: 2c — C7 MIPLO API Gateway

Sprint 2c builds the multi-tenant API gateway:
- FastAPI router with 4 endpoints: classify, price, execute, portfolio
- TenantContext extraction from C8 token → pipeline
- Pipeline.process_payment() gains optional tenant_id
- Per-tenant decision log partitioning
