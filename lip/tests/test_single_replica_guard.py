"""Regression tests for single_replica opt-in guard (B3-04, B7-02, B7-10).

Modules that store state in-memory must refuse construction without
``single_replica=True`` to prevent silent state loss in multi-replica
deployments.
"""

from __future__ import annotations

import logging

import pytest

from lip.c6_aml_velocity.tenant_velocity import StructuringDetector
from lip.c6_aml_velocity.velocity_bridge import RustVelocityChecker
from lip.c8_license_manager.query_metering import RegulatoryQueryMetering

_SALT = b"test_salt_32bytes_long_exactly__"
_METERING_KEY = b"test_metering_key_32bytes_guard!"


class TestRegulatoryQueryMeteringGuard:
    """B3-04: RegulatoryQueryMetering must refuse without single_replica."""

    def test_construction_without_flag_raises(self) -> None:
        # No single_replica kwarg at all → must get the single_replica error
        # (metering_key check comes after, so the b"" default does not fire first).
        with pytest.raises(ValueError, match="single_replica"):
            RegulatoryQueryMetering()

    def test_construction_with_flag_succeeds(self) -> None:
        meter = RegulatoryQueryMetering(metering_key=_METERING_KEY, single_replica=True)
        assert meter is not None

    def test_construction_with_flag_logs_warning(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            RegulatoryQueryMetering(metering_key=_METERING_KEY, single_replica=True)
        assert "single_replica" in caplog.text

    def test_empty_metering_key_raises(self) -> None:
        """B3-08: empty HMAC key is refused even when single_replica=True."""
        with pytest.raises(ValueError, match="metering_key"):
            RegulatoryQueryMetering(metering_key=b"", single_replica=True)


class TestStructuringDetectorGuard:
    """B7-10: StructuringDetector must refuse without single_replica."""

    def test_construction_without_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="single_replica"):
            StructuringDetector()

    def test_construction_with_flag_succeeds(self) -> None:
        detector = StructuringDetector(single_replica=True)
        assert detector is not None

    def test_construction_with_flag_logs_warning(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            StructuringDetector(single_replica=True)
        assert "single_replica" in caplog.text


class TestVelocityBridgeGuard:
    """B7-02: VelocityBridge (RustVelocityChecker) must refuse without single_replica."""

    def test_construction_without_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="single_replica"):
            RustVelocityChecker(salt=_SALT)

    def test_construction_with_flag_succeeds(self) -> None:
        checker = RustVelocityChecker(salt=_SALT, single_replica=True)
        assert checker is not None

    def test_construction_with_flag_logs_warning(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            RustVelocityChecker(salt=_SALT, single_replica=True)
        assert "single_replica" in caplog.text
