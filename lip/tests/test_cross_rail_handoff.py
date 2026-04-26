"""
test_cross_rail_handoff.py — Phase C cross-rail UETR handoff detection.

A SWIFT pacs.008 with US-domestic destination may be settled via FedNow
last-mile. We track the FedNow UETR as a child of the upstream SWIFT UETR.
If the FedNow leg fails, we route the failure back to the SWIFT UETR for
bridge eligibility.

Patent angle: detecting settlement confirmation from disparate payment
network rails for a single UETR-tracked payment (P9 continuation hook,
flagged in Master-Action-Plan-2026.md:378). Code-only; filing frozen
per CLAUDE.md non-negotiable #6.
"""
from datetime import datetime, timedelta, timezone

import pytest

from lip.common.uetr_tracker import UETRTracker


class TestRegisterHandoff:

    def test_register_then_find_parent(self):
        t = UETRTracker()
        t.register_handoff(
            parent_uetr="SWIFT-UETR-001",
            child_uetr="FEDNOW-UETR-001",
            child_rail="FEDNOW",
        )
        assert t.find_parent("FEDNOW-UETR-001") == "SWIFT-UETR-001"

    def test_find_parent_unknown_returns_none(self):
        t = UETRTracker()
        assert t.find_parent("FEDNOW-UNKNOWN") is None

    def test_handoff_ttl_30_minutes(self):
        t = UETRTracker()
        now = datetime.now(timezone.utc)
        t.register_handoff(
            parent_uetr="SWIFT-001",
            child_uetr="FEDNOW-001",
            child_rail="FEDNOW",
            timestamp=now,
        )
        # Within window
        assert t.find_parent("FEDNOW-001", at=now + timedelta(minutes=29)) == "SWIFT-001"
        # Outside window
        assert t.find_parent("FEDNOW-001", at=now + timedelta(minutes=31)) is None

    def test_register_handoff_validates_rail(self):
        t = UETRTracker()
        with pytest.raises(ValueError, match="child_rail"):
            t.register_handoff(
                parent_uetr="SWIFT-001",
                child_uetr="X-001",
                child_rail="UNKNOWN_RAIL",
            )

    def test_rtp_rail_accepted(self):
        t = UETRTracker()
        t.register_handoff(
            parent_uetr="SWIFT-001", child_uetr="RTP-001", child_rail="RTP"
        )
        assert t.find_parent("RTP-001") == "SWIFT-001"

    def test_sepa_rail_accepted(self):
        t = UETRTracker()
        t.register_handoff(
            parent_uetr="SWIFT-001", child_uetr="SEPA-001", child_rail="SEPA"
        )
        assert t.find_parent("SEPA-001") == "SWIFT-001"

    def test_clear_drops_handoffs(self):
        t = UETRTracker()
        t.register_handoff(
            parent_uetr="SWIFT-001", child_uetr="FEDNOW-001", child_rail="FEDNOW"
        )
        t.clear()
        assert t.find_parent("FEDNOW-001") is None

    def test_case_insensitive_rail(self):
        t = UETRTracker()
        t.register_handoff(
            parent_uetr="SWIFT-001", child_uetr="FEDNOW-001", child_rail="fednow"
        )
        assert t.find_parent("FEDNOW-001") == "SWIFT-001"


class TestDomesticLegFailureRouting:
    """Phase C — pipeline emits DOMESTIC_LEG_FAILURE when a domestic-rail leg
    rejects AND has a registered upstream SWIFT parent UETR.

    The bridge offer is still generated (the underlying payment failure is
    real — someone needs to bridge it) but the outcome label flags the
    cross-rail handoff for audit and patent claim support.
    """

    def test_fednow_rjct_with_registered_parent_emits_domestic_leg_failure(self):
        from decimal import Decimal

        from lip.tests.conftest import make_event
        from lip.tests.test_e2e_pipeline import _make_pipeline

        pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300)
        event = make_event(
            rejection_code="CURR",
            rail="FEDNOW",
            currency="USD",
            amount=Decimal("5000000.00"),
        )
        # Register the upstream parent BEFORE processing the event.
        pipeline._uetr_tracker.register_handoff(
            parent_uetr="SWIFT-PARENT-001",
            child_uetr=event.uetr,
            child_rail="FEDNOW",
        )
        result = pipeline.process(event)
        assert result.outcome == "DOMESTIC_LEG_FAILURE"
        # Bridge offer still generated; carries parent_uetr for cross-rail audit.
        assert result.loan_offer is not None
        assert result.loan_offer.get("parent_uetr") == "SWIFT-PARENT-001"
        # Rail tagging unchanged — child rail is FedNow.
        assert result.loan_offer["rail"] == "FEDNOW"

    def test_fednow_rjct_without_parent_falls_through_to_offered(self):
        from decimal import Decimal

        from lip.tests.conftest import make_event
        from lip.tests.test_e2e_pipeline import _make_pipeline

        pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300)
        event = make_event(
            rejection_code="CURR",
            rail="FEDNOW",
            currency="USD",
            amount=Decimal("5000000.00"),
        )
        # No handoff registered — pipeline falls through to standard OFFERED.
        result = pipeline.process(event)
        assert result.outcome == "OFFERED"
        assert "parent_uetr" not in (result.loan_offer or {})

    def test_swift_event_never_emits_domestic_leg_failure(self):
        """Regression guard: SWIFT events themselves are never tagged
        DOMESTIC_LEG_FAILURE — only their downstream domestic legs are."""
        from decimal import Decimal

        from lip.tests.conftest import make_event
        from lip.tests.test_e2e_pipeline import _make_pipeline

        pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300)
        event = make_event(
            rejection_code="CURR",
            rail="SWIFT",
            currency="USD",
            amount=Decimal("5000000.00"),
        )
        # Even if a handoff existed (it wouldn't, since SWIFT is the parent),
        # SWIFT events should never be tagged as domestic-leg failures.
        result = pipeline.process(event)
        assert result.outcome == "OFFERED"
