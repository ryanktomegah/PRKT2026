"""
test_c7_offer_delivery.py — Tests for GAP-01: Loan offer delivery and acceptance protocol.

Covers:
  - LoanOfferDelivery, LoanOfferAcceptance, LoanOfferRejection schema validation
  - OfferDeliveryService: deliver, accept, reject, expire_stale_offers
  - Callback wiring (on_accept, on_reject, on_expire)
  - ExecutionAgent integration (offer_delivery parameter)
  - End-to-end: agent offer → ELO accept → C3 callback simulation
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import pytest

from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.c7_execution_agent.offer_delivery import (
    OfferAlreadyResolvedException,
    OfferDeliveryOutcome,
    OfferDeliveryService,
    OfferExpiredException,
    OfferNotFoundException,
)
from lip.common.schemas import LoanOfferAcceptance, LoanOfferDelivery, LoanOfferRejection

_HMAC_KEY = b"test_hmac_key_for_unit_tests_32b"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(offer_delivery=None):
    ks = KillSwitch()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    ho = HumanOverrideInterface()
    dm = DegradedModeManager()
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    return ExecutionAgent(ks, dl, ho, dm, cfg, offer_delivery=offer_delivery)


def _make_payment_context(
    uetr=None,
    failure_prob=0.80,
    pd_score=0.05,
    fee_bps=300,
    loan_amount=500_000,
):
    return {
        "uetr": uetr or str(uuid.uuid4()),
        "individual_payment_id": str(uuid.uuid4()),
        "failure_probability": failure_prob,
        "pd_score": pd_score,
        "fee_bps": fee_bps,
        "loan_amount": str(loan_amount),
        "maturity_days": 7,
        "rejection_code_class": "B",
        "dispute_class": "NOT_DISPUTE",
        "aml_passed": True,
    }


def _deliver_offer(
    svc: OfferDeliveryService,
    uetr: Optional[str] = None,
    expires_in_seconds: float = 900.0,
) -> tuple:
    """Deliver a synthetic offer to the service. Returns (offer_id_str, LoanOfferDelivery)."""
    offer = {
        "loan_id": str(uuid.uuid4()),
        "uetr": uetr or str(uuid.uuid4()),
        "loan_amount": "500000",
        "fee_bps": "300",
        "fee_amount_usd": "2876.71",
        "maturity_days": 7,
        "rejection_code_class": "B",
        "pd_score": 0.05,
        "elo_entity_id": "AAAAGB2LXXX",
        "expires_at": (
            datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in_seconds)
        ).isoformat(),
        "offered_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    delivery = svc.deliver(offer)
    return str(delivery.offer_id), delivery


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestLoanOfferDeliverySchema:
    def test_valid_schema(self):
        now = datetime.now(tz=timezone.utc)
        d = LoanOfferDelivery(
            delivery_id=uuid.uuid4(),
            offer_id=uuid.uuid4(),
            uetr=uuid.uuid4(),
            elo_entity_id="ELO123",
            principal_usd=Decimal("1000000"),
            fee_bps=Decimal("300"),
            fee_amount_usd=Decimal("576.71"),
            maturity_days=7,
            rejection_code_class="B",
            offer_expiry=now + timedelta(minutes=15),
            pd_score=0.05,
            delivered_at=now,
        )
        assert d.principal_usd == Decimal("1000000")
        assert d.rejection_code_class == "B"
        assert d.delivery_endpoint is None

    def test_fee_below_floor_rejected(self):
        with pytest.raises(Exception):
            LoanOfferDelivery(
                delivery_id=uuid.uuid4(),
                offer_id=uuid.uuid4(),
                uetr=uuid.uuid4(),
                elo_entity_id="ELO",
                principal_usd=Decimal("100000"),
                fee_bps=Decimal("299"),   # below 300 bps floor
                fee_amount_usd=Decimal("0"),
                maturity_days=7,
                rejection_code_class="B",
                offer_expiry=datetime.now(tz=timezone.utc) + timedelta(minutes=15),
                pd_score=0.05,
                delivered_at=datetime.now(tz=timezone.utc),
            )

    def test_invalid_rejection_code_class(self):
        with pytest.raises(Exception):
            LoanOfferDelivery(
                delivery_id=uuid.uuid4(),
                offer_id=uuid.uuid4(),
                uetr=uuid.uuid4(),
                elo_entity_id="ELO",
                principal_usd=Decimal("100000"),
                fee_bps=Decimal("300"),
                fee_amount_usd=Decimal("0"),
                maturity_days=7,
                rejection_code_class="X",   # invalid
                offer_expiry=datetime.now(tz=timezone.utc) + timedelta(minutes=15),
                pd_score=0.05,
                delivered_at=datetime.now(tz=timezone.utc),
            )

    def test_delivery_endpoint_optional(self):
        now = datetime.now(tz=timezone.utc)
        d = LoanOfferDelivery(
            delivery_id=uuid.uuid4(),
            offer_id=uuid.uuid4(),
            uetr=uuid.uuid4(),
            elo_entity_id="ELO",
            principal_usd=Decimal("1000"),
            fee_bps=Decimal("300"),
            fee_amount_usd=Decimal("0"),
            maturity_days=3,
            rejection_code_class="A",
            offer_expiry=now + timedelta(minutes=15),
            pd_score=0.1,
            delivery_endpoint="https://bank.example.com/lip/accept",
            delivered_at=now,
        )
        assert d.delivery_endpoint == "https://bank.example.com/lip/accept"


class TestLoanOfferAcceptanceSchema:
    def test_valid_schema(self):
        a = LoanOfferAcceptance(
            acceptance_id=uuid.uuid4(),
            delivery_id=uuid.uuid4(),
            offer_id=uuid.uuid4(),
            uetr=uuid.uuid4(),
            elo_entity_id="ELO123",
            elo_operator_id="TREASURY-OPS-001",
            accepted_at=datetime.now(tz=timezone.utc),
        )
        assert a.elo_operator_id == "TREASURY-OPS-001"

    def test_empty_operator_id_rejected(self):
        with pytest.raises(Exception):
            LoanOfferAcceptance(
                acceptance_id=uuid.uuid4(),
                delivery_id=uuid.uuid4(),
                offer_id=uuid.uuid4(),
                uetr=uuid.uuid4(),
                elo_entity_id="ELO",
                elo_operator_id="",   # violates min_length=1
                accepted_at=datetime.now(tz=timezone.utc),
            )


class TestLoanOfferRejectionSchema:
    def test_valid_schema(self):
        r = LoanOfferRejection(
            rejection_id=uuid.uuid4(),
            delivery_id=uuid.uuid4(),
            offer_id=uuid.uuid4(),
            uetr=uuid.uuid4(),
            elo_entity_id="ELO",
            elo_operator_id="OPS-042",
            rejection_reason="Counterparty risk elevated",
            rejected_at=datetime.now(tz=timezone.utc),
        )
        assert r.rejection_reason == "Counterparty risk elevated"

    def test_empty_reason_rejected(self):
        with pytest.raises(Exception):
            LoanOfferRejection(
                rejection_id=uuid.uuid4(),
                delivery_id=uuid.uuid4(),
                offer_id=uuid.uuid4(),
                uetr=uuid.uuid4(),
                elo_entity_id="ELO",
                elo_operator_id="OPS-042",
                rejection_reason="",   # violates min_length=1
                rejected_at=datetime.now(tz=timezone.utc),
            )


# ---------------------------------------------------------------------------
# OfferDeliveryService — deliver
# ---------------------------------------------------------------------------

class TestOfferDeliveryServiceDeliver:
    def test_deliver_creates_pending_entry(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        assert svc.get_outcome(offer_id) == OfferDeliveryOutcome.PENDING

    def test_deliver_returns_loan_offer_delivery(self):
        svc = OfferDeliveryService()
        offer_id, delivery = _deliver_offer(svc)
        assert isinstance(delivery, LoanOfferDelivery)
        assert str(delivery.offer_id) == offer_id

    def test_deliver_stamps_endpoint(self):
        svc = OfferDeliveryService(delivery_endpoint="https://bank.example.com/lip/accept")
        _, delivery = _deliver_offer(svc)
        assert delivery.delivery_endpoint == "https://bank.example.com/lip/accept"

    def test_deliver_no_endpoint_by_default(self):
        svc = OfferDeliveryService()
        _, delivery = _deliver_offer(svc)
        assert delivery.delivery_endpoint is None

    def test_pending_includes_new_offer(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        assert any(str(d.offer_id) == offer_id for d in svc.get_pending_deliveries())

    def test_multiple_offers_all_pending(self):
        svc = OfferDeliveryService()
        ids = [_deliver_offer(svc)[0] for _ in range(5)]
        assert len(svc.get_pending_deliveries()) == 5
        for oid in ids:
            assert svc.get_outcome(oid) == OfferDeliveryOutcome.PENDING

    def test_deliver_preserves_uetr(self):
        svc = OfferDeliveryService()
        uetr = str(uuid.uuid4())
        _, delivery = _deliver_offer(svc, uetr=uetr)
        assert str(delivery.uetr) == uetr


# ---------------------------------------------------------------------------
# OfferDeliveryService — accept
# ---------------------------------------------------------------------------

class TestOfferDeliveryServiceAccept:
    def test_accept_valid_offer(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        acceptance = svc.accept(offer_id, elo_operator_id="TREASURY-OPS-001")
        assert isinstance(acceptance, LoanOfferAcceptance)
        assert acceptance.elo_operator_id == "TREASURY-OPS-001"
        assert str(acceptance.offer_id) == offer_id

    def test_accept_changes_outcome_to_accepted(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.accept(offer_id, elo_operator_id="OPS-001")
        assert svc.get_outcome(offer_id) == OfferDeliveryOutcome.ACCEPTED

    def test_accept_removes_from_pending(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.accept(offer_id, elo_operator_id="OPS-001")
        assert all(str(d.offer_id) != offer_id for d in svc.get_pending_deliveries())

    def test_accept_fires_callback(self):
        received = []
        svc = OfferDeliveryService(on_accept=received.append)
        offer_id, _ = _deliver_offer(svc)
        svc.accept(offer_id, elo_operator_id="OPS-001")
        assert len(received) == 1
        assert isinstance(received[0], LoanOfferAcceptance)

    def test_get_acceptance_returns_record(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.accept(offer_id, elo_operator_id="OPS-001")
        a = svc.get_acceptance(offer_id)
        assert a is not None
        assert a.elo_operator_id == "OPS-001"

    def test_accept_already_accepted_raises(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.accept(offer_id, elo_operator_id="OPS-001")
        with pytest.raises(OfferAlreadyResolvedException):
            svc.accept(offer_id, elo_operator_id="OPS-002")

    def test_accept_after_reject_raises(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.reject(offer_id, elo_operator_id="OPS-001", rejection_reason="No capacity")
        with pytest.raises(OfferAlreadyResolvedException):
            svc.accept(offer_id, elo_operator_id="OPS-002")

    def test_accept_unknown_offer_raises(self):
        svc = OfferDeliveryService()
        with pytest.raises(OfferNotFoundException):
            svc.accept(str(uuid.uuid4()), elo_operator_id="OPS-001")

    def test_accept_expired_offer_raises(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc, expires_in_seconds=-1)
        with pytest.raises(OfferExpiredException):
            svc.accept(offer_id, elo_operator_id="OPS-001")

    def test_accept_empty_operator_raises(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        with pytest.raises(ValueError):
            svc.accept(offer_id, elo_operator_id="")

    def test_accept_delivery_id_matches_delivery(self):
        svc = OfferDeliveryService()
        offer_id, delivery = _deliver_offer(svc)
        acceptance = svc.accept(offer_id, elo_operator_id="OPS-001")
        assert acceptance.delivery_id == delivery.delivery_id

    def test_accept_uetr_matches_delivery(self):
        svc = OfferDeliveryService()
        uetr = str(uuid.uuid4())
        offer_id, delivery = _deliver_offer(svc, uetr=uetr)
        acceptance = svc.accept(offer_id, elo_operator_id="OPS-001")
        assert acceptance.uetr == delivery.uetr


# ---------------------------------------------------------------------------
# OfferDeliveryService — reject
# ---------------------------------------------------------------------------

class TestOfferDeliveryServiceReject:
    def test_reject_valid_offer(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        rejection = svc.reject(
            offer_id,
            elo_operator_id="OPS-001",
            rejection_reason="Elevated counterparty risk",
        )
        assert isinstance(rejection, LoanOfferRejection)
        assert rejection.rejection_reason == "Elevated counterparty risk"

    def test_reject_changes_outcome(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.reject(offer_id, elo_operator_id="OPS-001", rejection_reason="Test")
        assert svc.get_outcome(offer_id) == OfferDeliveryOutcome.REJECTED

    def test_reject_fires_callback(self):
        received = []
        svc = OfferDeliveryService(on_reject=received.append)
        offer_id, _ = _deliver_offer(svc)
        svc.reject(offer_id, elo_operator_id="OPS-001", rejection_reason="Test")
        assert len(received) == 1
        assert isinstance(received[0], LoanOfferRejection)

    def test_get_rejection_returns_record(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.reject(offer_id, elo_operator_id="OPS-001", rejection_reason="No capacity")
        r = svc.get_rejection(offer_id)
        assert r is not None
        assert r.rejection_reason == "No capacity"

    def test_reject_after_accept_raises(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.accept(offer_id, elo_operator_id="OPS-001")
        with pytest.raises(OfferAlreadyResolvedException):
            svc.reject(offer_id, elo_operator_id="OPS-002", rejection_reason="Too late")

    def test_reject_empty_reason_raises(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        with pytest.raises(ValueError):
            svc.reject(offer_id, elo_operator_id="OPS-001", rejection_reason="")

    def test_reject_empty_operator_raises(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        with pytest.raises(ValueError):
            svc.reject(offer_id, elo_operator_id="", rejection_reason="Test")

    def test_reject_removes_from_pending(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.reject(offer_id, elo_operator_id="OPS-001", rejection_reason="Test")
        assert all(str(d.offer_id) != offer_id for d in svc.get_pending_deliveries())


# ---------------------------------------------------------------------------
# OfferDeliveryService — expiry
# ---------------------------------------------------------------------------

class TestOfferDeliveryServiceExpiry:
    def test_expire_stale_marks_expired(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc, expires_in_seconds=-1)
        expiries = svc.expire_stale_offers()
        expired_ids = [str(e.offer_id) for e in expiries]
        assert offer_id in expired_ids
        assert svc.get_outcome(offer_id) == OfferDeliveryOutcome.EXPIRED

    def test_expire_fresh_offers_not_touched(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc, expires_in_seconds=3600)
        expiries = svc.expire_stale_offers()
        expired_ids = [str(e.offer_id) for e in expiries]
        assert offer_id not in expired_ids
        assert svc.get_outcome(offer_id) == OfferDeliveryOutcome.PENDING

    def test_expire_fires_on_expire_callback(self):
        fired = []
        svc = OfferDeliveryService(on_expire=fired.append)
        offer_id, _ = _deliver_offer(svc, expires_in_seconds=-1)
        svc.expire_stale_offers()
        # EPG-23: callback now receives LoanOfferExpiry, not bare offer_id string
        assert any(str(e.offer_id) == offer_id for e in fired)

    def test_expire_removes_from_pending(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc, expires_in_seconds=-1)
        svc.expire_stale_offers()
        assert all(str(d.offer_id) != offer_id for d in svc.get_pending_deliveries())

    def test_accept_after_sweep_raises_expired(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc, expires_in_seconds=-1)
        svc.expire_stale_offers()
        with pytest.raises(OfferExpiredException):
            svc.accept(offer_id, elo_operator_id="OPS-001")

    def test_expire_multiple_only_stale_ones(self):
        svc = OfferDeliveryService()
        stale_id, _ = _deliver_offer(svc, expires_in_seconds=-1)
        fresh_id, _ = _deliver_offer(svc, expires_in_seconds=3600)
        expiries = svc.expire_stale_offers()
        expired_ids = [str(e.offer_id) for e in expiries]
        assert stale_id in expired_ids
        assert fresh_id not in expired_ids
        assert svc.get_outcome(stale_id) == OfferDeliveryOutcome.EXPIRED
        assert svc.get_outcome(fresh_id) == OfferDeliveryOutcome.PENDING

    def test_expire_returns_empty_when_nothing_stale(self):
        svc = OfferDeliveryService()
        _deliver_offer(svc, expires_in_seconds=3600)
        assert svc.expire_stale_offers() == []

    def test_expiry_record_has_reason_and_timestamp(self):
        """EPG-23: expired offer must have structured LoanOfferExpiry with reason and ts."""
        from lip.common.schemas import LoanOfferExpiry, OfferExpiryReason
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc, expires_in_seconds=-1)
        svc.expire_stale_offers()
        record = svc.get_expiry(offer_id)
        assert isinstance(record, LoanOfferExpiry)
        assert record.expiry_reason == OfferExpiryReason.TIMEOUT
        assert record.expired_at is not None
        assert record.class_b_eligible is False

    def test_class_b_eligible_defaults_false_on_delivery(self):
        """EPG-23/EPG-19: class_b_eligible must default False until B1 is unlocked."""
        svc = OfferDeliveryService()
        _, delivery = _deliver_offer(svc, expires_in_seconds=-1)
        assert delivery.class_b_eligible is False


# ---------------------------------------------------------------------------
# OfferDeliveryService — query methods
# ---------------------------------------------------------------------------

class TestOfferDeliveryServiceQueries:
    def test_get_outcome_unknown_raises(self):
        svc = OfferDeliveryService()
        with pytest.raises(OfferNotFoundException):
            svc.get_outcome(str(uuid.uuid4()))

    def test_get_acceptance_none_if_pending(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        assert svc.get_acceptance(offer_id) is None

    def test_get_rejection_none_if_pending(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        assert svc.get_rejection(offer_id) is None

    def test_get_acceptance_none_if_rejected(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.reject(offer_id, elo_operator_id="OPS-001", rejection_reason="Test")
        assert svc.get_acceptance(offer_id) is None

    def test_get_rejection_none_if_accepted(self):
        svc = OfferDeliveryService()
        offer_id, _ = _deliver_offer(svc)
        svc.accept(offer_id, elo_operator_id="OPS-001")
        assert svc.get_rejection(offer_id) is None

    def test_pending_excludes_accepted(self):
        svc = OfferDeliveryService()
        o1, _ = _deliver_offer(svc)
        o2, _ = _deliver_offer(svc)
        svc.accept(o1, elo_operator_id="OPS-001")
        pending_ids = [str(d.offer_id) for d in svc.get_pending_deliveries()]
        assert o1 not in pending_ids
        assert o2 in pending_ids

    def test_pending_excludes_rejected(self):
        svc = OfferDeliveryService()
        o1, _ = _deliver_offer(svc)
        o2, _ = _deliver_offer(svc)
        svc.reject(o1, elo_operator_id="OPS-001", rejection_reason="Test")
        pending_ids = [str(d.offer_id) for d in svc.get_pending_deliveries()]
        assert o1 not in pending_ids
        assert o2 in pending_ids

    def test_pending_is_snapshot_not_live_reference(self):
        svc = OfferDeliveryService()
        _deliver_offer(svc)
        snap1 = svc.get_pending_deliveries()
        _deliver_offer(svc)
        snap2 = svc.get_pending_deliveries()
        # snap1 should still have 1 element (it's a copy)
        assert len(snap1) == 1
        assert len(snap2) == 2


# ---------------------------------------------------------------------------
# ExecutionAgent integration
# ---------------------------------------------------------------------------

class TestAgentWithDeliveryService:
    def test_offer_result_includes_delivery_id(self):
        svc = OfferDeliveryService()
        agent = _make_agent(offer_delivery=svc)
        result = agent.process_payment(_make_payment_context())
        assert result["status"] == "OFFER"
        assert result["delivery_id"] is not None

    def test_delivery_id_none_without_service(self):
        agent = _make_agent(offer_delivery=None)
        result = agent.process_payment(_make_payment_context())
        assert result["status"] == "OFFER"
        assert result.get("delivery_id") is None

    def test_delivery_id_matches_pending_offer(self):
        svc = OfferDeliveryService()
        agent = _make_agent(offer_delivery=svc)
        result = agent.process_payment(_make_payment_context())
        loan_offer_id = result["loan_offer"]["loan_id"]
        assert svc.get_outcome(loan_offer_id) == OfferDeliveryOutcome.PENDING

    def test_accept_after_agent_offer(self):
        accepted = []
        svc = OfferDeliveryService(on_accept=accepted.append)
        agent = _make_agent(offer_delivery=svc)
        result = agent.process_payment(_make_payment_context())
        loan_offer_id = result["loan_offer"]["loan_id"]
        svc.accept(loan_offer_id, elo_operator_id="TREASURY-001")
        assert len(accepted) == 1
        assert svc.get_outcome(loan_offer_id) == OfferDeliveryOutcome.ACCEPTED

    def test_aml_block_does_not_trigger_delivery(self):
        svc = OfferDeliveryService()
        agent = _make_agent(offer_delivery=svc)
        ctx = _make_payment_context()
        ctx["aml_passed"] = False
        result = agent.process_payment(ctx)
        assert result["status"] == "BLOCK"
        assert len(svc.get_pending_deliveries()) == 0

    def test_dispute_block_does_not_trigger_delivery(self):
        svc = OfferDeliveryService()
        agent = _make_agent(offer_delivery=svc)
        ctx = _make_payment_context()
        ctx["dispute_class"] = "DISPUTE_CONFIRMED"
        result = agent.process_payment(ctx)
        assert result["status"] == "BLOCK"
        assert len(svc.get_pending_deliveries()) == 0

    def test_decline_does_not_trigger_delivery(self):
        svc = OfferDeliveryService()
        agent = _make_agent(offer_delivery=svc)
        # failure_prob < 0.10 → DECLINE
        result = agent.process_payment(_make_payment_context(failure_prob=0.05))
        assert result["status"] == "DECLINE"
        assert len(svc.get_pending_deliveries()) == 0

    def test_multiple_payments_each_get_unique_delivery_id(self):
        svc = OfferDeliveryService()
        agent = _make_agent(offer_delivery=svc)
        results = [agent.process_payment(_make_payment_context()) for _ in range(3)]
        delivery_ids = [r["delivery_id"] for r in results if r["status"] == "OFFER"]
        assert len(set(delivery_ids)) == 3   # all unique


# ---------------------------------------------------------------------------
# End-to-end: agent → accept → C3 registration callback simulation
# ---------------------------------------------------------------------------

class TestGap01EndToEnd:
    def test_offer_accept_triggers_c3_registration(self):
        """GAP-01 resolved: offer delivered → ELO accepts → C3 receives ActiveLoan."""
        c3_registered = []

        def on_accept_register_c3(acceptance: LoanOfferAcceptance) -> None:
            # In production: create ActiveLoan from acceptance and call
            # repayment_loop.register_loan(loan). Here we record the offer_id.
            c3_registered.append(str(acceptance.offer_id))

        svc = OfferDeliveryService(on_accept=on_accept_register_c3)
        agent = _make_agent(offer_delivery=svc)
        result = agent.process_payment(_make_payment_context())
        loan_offer_id = result["loan_offer"]["loan_id"]

        svc.accept(loan_offer_id, elo_operator_id="TREASURY-DESK-01")

        assert loan_offer_id in c3_registered
        assert svc.get_outcome(loan_offer_id) == OfferDeliveryOutcome.ACCEPTED

    def test_offer_reject_does_not_trigger_c3(self):
        """Rejected offers must not appear in C3 registration."""
        c3_registered = []

        svc = OfferDeliveryService(on_accept=lambda a: c3_registered.append(str(a.offer_id)))
        agent = _make_agent(offer_delivery=svc)
        result = agent.process_payment(_make_payment_context())
        loan_offer_id = result["loan_offer"]["loan_id"]

        svc.reject(loan_offer_id, elo_operator_id="TREASURY-DESK-01", rejection_reason="Capacity")

        assert loan_offer_id not in c3_registered
        assert svc.get_outcome(loan_offer_id) == OfferDeliveryOutcome.REJECTED

    def test_offer_expiry_does_not_trigger_c3(self):
        """Expired offers must not result in any C3 registration."""
        c3_registered = []

        svc = OfferDeliveryService(on_accept=lambda a: c3_registered.append(str(a.offer_id)))
        agent = _make_agent(offer_delivery=svc)

        ctx = _make_payment_context()
        agent.process_payment(ctx)

        # Manually expire all pending offers
        svc.expire_stale_offers()

        # No C3 registration should occur
        assert c3_registered == []

    def test_delivery_id_in_response_is_string_uuid(self):
        svc = OfferDeliveryService()
        agent = _make_agent(offer_delivery=svc)
        result = agent.process_payment(_make_payment_context())
        delivery_id = result["delivery_id"]
        # Must be parseable as UUID
        parsed = uuid.UUID(delivery_id)
        assert str(parsed) == delivery_id
