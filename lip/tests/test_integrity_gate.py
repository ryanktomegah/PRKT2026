"""Tests for lip.integrity.pipeline_gate."""
from __future__ import annotations

from lip.integrity.claims_registry import ClaimsRegistry
from lip.integrity.oss_tracker import OSSAttributionRegistry
from lip.integrity.pipeline_gate import IntegrityGate

_KEY = b"integrity_test__32bytes_________"


def test_gate_passes_with_no_registries():
    """Backward compat: gate with no registries is a graceful no-op."""
    gate = IntegrityGate()
    result = gate.check()
    assert result.gate_passed is True
    assert result.oss_packages_scanned == 0


def test_gate_disabled_always_passes():
    gate = IntegrityGate(enabled=False)
    assert gate.check().gate_passed is True
    assert gate.is_healthy() is True


def test_gate_with_oss_registry_scans_packages():
    gate = IntegrityGate(oss_registry=OSSAttributionRegistry())
    result = gate.check()
    # We don't assert pass/fail here because the live environment may have
    # packages with UNKNOWN licenses; we only assert the scan ran.
    assert result.oss_packages_scanned > 0


def test_gate_with_claims_registry_reports_counts():
    reg = ClaimsRegistry(_KEY)
    gate = IntegrityGate(claims_registry=reg)
    result = gate.check()
    assert result.gate_passed is True
    assert result.claims_count == 0
    assert result.evidence_count == 0
