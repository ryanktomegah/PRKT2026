"""
test_c6_tenant_velocity.py — Tests for P3 Sprint 2b: C6 cross-tenant velocity isolation.

CIPHER domain: tenant isolation is a security boundary. A BIC authorized under
Processor A must NEVER have its velocity data visible to Processor B.

QUANT domain: structuring detection arithmetic must be exact (Decimal).
"""
from __future__ import annotations

from decimal import Decimal

from lip.c6_aml_velocity.aml_checker import AMLChecker
from lip.c6_aml_velocity.tenant_velocity import (
    StructuringDetector,
    StructuringResult,
    TenantVelocityChecker,
)
from lip.c6_aml_velocity.velocity import RollingWindow, VelocityChecker

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
        detector = StructuringDetector(single_replica=True)
        detector.record("entity_hash_abc", "PROCESSOR_A", Decimal("500000"))

        result = detector.check("entity_hash_abc", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is False

    def test_two_tenants_below_cap_no_flag(self):
        """Entity in 2 tenants but combined volume below cap: not flagged."""
        detector = StructuringDetector(single_replica=True)
        detector.record("entity_hash_def", "PROCESSOR_A", Decimal("100000"))
        detector.record("entity_hash_def", "PROCESSOR_B", Decimal("200000"))

        result = detector.check("entity_hash_def", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is False

    def test_two_tenants_above_cap_flagged(self):
        """Entity in 2 tenants with combined volume above cap: flagged."""
        detector = StructuringDetector(single_replica=True)
        detector.record("entity_hash_ghi", "PROCESSOR_A", Decimal("600000"))
        detector.record("entity_hash_ghi", "PROCESSOR_B", Decimal("500000"))

        result = detector.check("entity_hash_ghi", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is True
        assert result.tenant_count == 2
        assert result.combined_volume == Decimal("1100000")

    def test_three_tenants_flagged(self):
        """Entity across 3 tenants: flagged when above cap."""
        detector = StructuringDetector(single_replica=True)
        detector.record("entity_hash_jkl", "PROC_A", Decimal("400000"))
        detector.record("entity_hash_jkl", "PROC_B", Decimal("400000"))
        detector.record("entity_hash_jkl", "PROC_C", Decimal("400000"))

        result = detector.check("entity_hash_jkl", dollar_cap=_TEST_DOLLAR_CAP)
        assert result.flagged is True
        assert result.tenant_count == 3

    def test_unlimited_cap_never_flags_for_volume(self):
        """When dollar_cap is 0 (unlimited), volume check is skipped."""
        detector = StructuringDetector(single_replica=True)
        detector.record("entity_hash_mno", "PROC_A", Decimal("99999999"))
        detector.record("entity_hash_mno", "PROC_B", Decimal("99999999"))

        result = detector.check("entity_hash_mno", dollar_cap=Decimal("0"))
        assert result.flagged is False

    def test_result_has_correct_fields(self):
        """StructuringResult exposes flagged, tenant_count, combined_volume, tenants."""
        detector = StructuringDetector(single_replica=True)
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
        detector = StructuringDetector(single_replica=True)
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
