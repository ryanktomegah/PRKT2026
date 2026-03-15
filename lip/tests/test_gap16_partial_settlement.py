"""
test_gap16_partial_settlement.py — Tests for GAP-16:
Partial settlement handling in RepaymentLoop.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from lip.c3_repayment_engine.repayment_loop import (
    ActiveLoan,
    RepaymentLoop,
    RepaymentTrigger,
)
from lip.common.partial_settlement import PartialSettlementPolicy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loan(principal="1000000.00", loan_id=None) -> ActiveLoan:
    return ActiveLoan(
        loan_id=loan_id or str(uuid.uuid4()),
        uetr=str(uuid.uuid4()),
        individual_payment_id="pid-001",
        principal=Decimal(principal),
        fee_bps=300,
        maturity_date=datetime.now(tz=timezone.utc) + timedelta(days=7),
        rejection_class="CLASS_B",
        corridor="USD_USD",
        funded_at=datetime.now(tz=timezone.utc) - timedelta(hours=24),
        licensee_id="bank-test",
    )


def _make_loop(policy=None) -> RepaymentLoop:
    monitor = MagicMock()
    monitor.get_active_loans.return_value = []
    loop = RepaymentLoop(
        monitor=monitor,
        repayment_callback=lambda r: None,
        partial_settlement_policy=policy,
    )
    return loop


# ---------------------------------------------------------------------------
# 1: PartialSettlementPolicy enum
# ---------------------------------------------------------------------------

class TestPartialSettlementPolicyEnum:
    def test_enum_values_exist(self):
        """Both REQUIRE_FULL and ACCEPT_PARTIAL enum values are present."""
        assert PartialSettlementPolicy.REQUIRE_FULL == "REQUIRE_FULL"
        assert PartialSettlementPolicy.ACCEPT_PARTIAL == "ACCEPT_PARTIAL"


# ---------------------------------------------------------------------------
# 2–5: REQUIRE_FULL policy
# ---------------------------------------------------------------------------

class TestRequireFullPolicy:
    def test_require_full_returns_partial_pending(self):
        """REQUIRE_FULL: partial settlement returns PARTIAL_PENDING status."""
        loop = _make_loop(policy=PartialSettlementPolicy.REQUIRE_FULL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        result = loop.trigger_repayment(
            loan,
            RepaymentTrigger.SETTLEMENT_CONFIRMED,
            Decimal("900000.00"),  # 10% short
        )
        assert result["status"] == "PARTIAL_PENDING"
        assert result["loan_id"] == loan.loan_id

    def test_require_full_shortfall_amount_correct(self):
        """REQUIRE_FULL: shortfall_amount = principal - settlement_amount."""
        loop = _make_loop(policy=PartialSettlementPolicy.REQUIRE_FULL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("750000.00")
        )
        assert result["shortfall_amount"] == "250000.00"
        assert abs(result["shortfall_pct"] - 0.25) < 0.001

    def test_require_full_does_not_deregister_loan(self):
        """REQUIRE_FULL: loan stays active in the loop after PARTIAL_PENDING."""
        loop = _make_loop(policy=PartialSettlementPolicy.REQUIRE_FULL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("900000.00")
        )
        # Loan should still be registered
        active_ids = {lo.loan_id for lo in loop.get_active_loans()}
        assert loan.loan_id in active_ids

    def test_require_full_does_not_consume_idempotency_token(self):
        """REQUIRE_FULL: idempotency token not consumed, so full repayment can follow."""
        loop = _make_loop(policy=PartialSettlementPolicy.REQUIRE_FULL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        # Partial — should return PARTIAL_PENDING without consuming the token
        partial_result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("900000.00")
        )
        assert partial_result["status"] == "PARTIAL_PENDING"

        # Full settlement following the partial — must succeed (not idempotency-blocked)
        full_result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("1000000.00")
        )
        assert full_result.get("loan_id") == loan.loan_id
        assert "status" not in full_result  # normal repayment record, not PARTIAL_PENDING


# ---------------------------------------------------------------------------
# 6–9: ACCEPT_PARTIAL policy
# ---------------------------------------------------------------------------

class TestAcceptPartialPolicy:
    def test_accept_partial_proceeds_with_partial_settlement(self):
        """ACCEPT_PARTIAL: partial amount returns a normal repayment record."""
        loop = _make_loop(policy=PartialSettlementPolicy.ACCEPT_PARTIAL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("800000.00")
        )
        assert "loan_id" in result
        assert result["loan_id"] == loan.loan_id
        assert result.get("status") != "PARTIAL_PENDING"

    def test_accept_partial_marks_is_partial_true(self):
        """ACCEPT_PARTIAL repayment record has is_partial=True."""
        loop = _make_loop(policy=PartialSettlementPolicy.ACCEPT_PARTIAL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("800000.00")
        )
        assert result["is_partial"] is True

    def test_accept_partial_records_shortfall(self):
        """ACCEPT_PARTIAL repayment record includes shortfall_amount and shortfall_pct."""
        loop = _make_loop(policy=PartialSettlementPolicy.ACCEPT_PARTIAL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("800000.00")
        )
        assert result["shortfall_amount"] == "200000.00"
        assert abs(result["shortfall_pct"] - 0.20) < 0.001

    def test_accept_partial_deregisters_loan(self):
        """ACCEPT_PARTIAL closes the loan — it is deregistered after settlement."""
        loop = _make_loop(policy=PartialSettlementPolicy.ACCEPT_PARTIAL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("800000.00")
        )
        active_ids = {lo.loan_id for lo in loop.get_active_loans()}
        assert loan.loan_id not in active_ids


# ---------------------------------------------------------------------------
# 10–11: No policy (default behaviour)
# ---------------------------------------------------------------------------

class TestNoPartialPolicy:
    def test_no_policy_treats_partial_as_full_repayment(self):
        """Without a policy, partial settlement is treated as full repayment."""
        loop = _make_loop(policy=None)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        # Should not return PARTIAL_PENDING — just proceed normally
        result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("500000.00")
        )
        assert result.get("status") != "PARTIAL_PENDING"
        assert "loan_id" in result

    def test_full_settlement_is_not_partial(self):
        """Full settlement always sets is_partial=False regardless of policy."""
        loop = _make_loop(policy=PartialSettlementPolicy.ACCEPT_PARTIAL)
        loan = _make_loan("1000000.00")
        loop.register_loan(loan)

        result = loop.trigger_repayment(
            loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, Decimal("1000000.00")
        )
        assert result["is_partial"] is False
        assert result["shortfall_amount"] == "0"
        assert result["shortfall_pct"] == 0.0
