"""
test_c7_execution.py — Tests for C7 Execution Agent
"""
from datetime import datetime, timezone

import pytest

from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogEntryData, DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager, DegradedReason
from lip.c7_execution_agent.human_override import HumanOverrideInterface, OverrideDecision
from lip.c7_execution_agent.kill_switch import KillSwitch, KillSwitchState, KMSState

_HMAC_KEY = b"test_hmac_key_for_unit_tests_32b"


def _make_agent(config=None):
    ks = KillSwitch()
    logger = DecisionLogger(hmac_key=_HMAC_KEY)
    override = HumanOverrideInterface()
    degraded = DegradedModeManager()
    return ExecutionAgent(ks, logger, override, degraded, config or ExecutionConfig())


def _make_entry(**kwargs):
    defaults = dict(
        entry_id="", uetr="uetr-001", individual_payment_id="pid-001",
        decision_type="OFFER", decision_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        failure_probability=0.6, pd_score=0.05, fee_bps=300,
        loan_amount="100000", dispute_class="NOT_DISPUTE", aml_passed=True,
    )
    defaults.update(kwargs)
    return DecisionLogEntryData(**defaults)


class TestKillSwitch:
    def test_initially_inactive(self):
        ks = KillSwitch()
        assert ks.is_active() is False

    def test_activate_and_check(self):
        ks = KillSwitch()
        ks.activate("test reason")
        assert ks.is_active() is True

    def test_deactivate(self):
        ks = KillSwitch()
        ks.activate()
        ks.deactivate()
        assert ks.is_active() is False

    def test_should_halt_when_active(self):
        ks = KillSwitch()
        ks.activate()
        assert ks.should_halt_new_offers() is True

    def test_should_not_halt_when_inactive(self):
        ks = KillSwitch()
        assert ks.should_halt_new_offers() is False

    def test_kms_unavailable_gap_none_when_available(self):
        ks = KillSwitch()
        assert ks.kms_unavailable_gap_seconds() is None

    def test_get_status_returns_status(self):
        ks = KillSwitch()
        status = ks.get_status()
        assert status.kill_switch_state == KillSwitchState.INACTIVE
        assert status.kms_state == KMSState.AVAILABLE


class TestDecisionLogger:
    def test_log_returns_entry_id(self):
        logger = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_entry()
        eid = logger.log(entry)
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_verify_valid_entry(self):
        logger = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_entry()
        eid = logger.log(entry)
        assert logger.verify(eid) is True

    def test_verify_tampered_entry_fails(self):
        logger = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_entry()
        eid = logger.log(entry)
        # Tamper with stored entry
        stored = logger.get(eid)
        stored.pd_score = 0.99  # tamper
        assert logger.verify(eid) is False

    def test_entry_signature_non_empty(self):
        logger = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_entry()
        logger.log(entry)
        assert entry.entry_signature != ""

    def test_get_by_uetr(self):
        logger = DecisionLogger(hmac_key=_HMAC_KEY)
        e1 = _make_entry(uetr="uetr-A", individual_payment_id="pid-A")
        e2 = _make_entry(uetr="uetr-A", individual_payment_id="pid-B")
        logger.log(e1)
        logger.log(e2)
        results = logger.get_by_uetr("uetr-A")
        assert len(results) == 2

    def test_get_by_uetr_empty(self):
        logger = DecisionLogger(hmac_key=_HMAC_KEY)
        assert logger.get_by_uetr("nonexistent") == []

    def test_decision_log_includes_kms_gap_field(self):
        entry = _make_entry(kms_unavailable_gap=15.5, degraded_mode=True)
        assert entry.kms_unavailable_gap == 15.5
        assert entry.degraded_mode is True


class TestHumanOverrideInterface:
    def test_request_override(self):
        interface = HumanOverrideInterface()
        req = interface.request_override(
            uetr="uetr-001", original_decision="OFFER",
            ai_confidence=0.6, reason="PD above threshold",
        )
        assert req.request_id is not None
        assert interface.is_pending(req.request_id) is True

    def test_submit_approve(self):
        interface = HumanOverrideInterface()
        req = interface.request_override("uetr-001", "OFFER", 0.6, "High PD")
        resp = interface.submit_response(
            req.request_id, OverrideDecision.APPROVE, "operator_1", "Looks fine"
        )
        assert resp.decision == OverrideDecision.APPROVE
        assert interface.is_pending(req.request_id) is False

    def test_reject_requires_justification(self):
        interface = HumanOverrideInterface()
        req = interface.request_override("uetr-001", "OFFER", 0.6, "High PD")
        with pytest.raises(ValueError, match="justification"):
            interface.submit_response(req.request_id, OverrideDecision.REJECT, "op1", "")

    def test_empty_operator_id_raises(self):
        interface = HumanOverrideInterface()
        req = interface.request_override("uetr-001", "OFFER", 0.6, "reason")
        with pytest.raises(ValueError, match="operator_id"):
            interface.submit_response(req.request_id, OverrideDecision.APPROVE, "", "ok")

    def test_get_pending_overrides(self):
        interface = HumanOverrideInterface()
        interface.request_override("u1", "OFFER", 0.5, "reason1")
        interface.request_override("u2", "OFFER", 0.7, "reason2")
        assert len(interface.get_pending_overrides()) == 2


class TestDegradedModeManager:
    def test_initially_not_degraded(self):
        mgr = DegradedModeManager()
        assert mgr.is_degraded() is False

    def test_enter_gpu_failure(self):
        mgr = DegradedModeManager()
        mgr.enter_degraded_mode(DegradedReason.GPU_FAILURE, gpu_fallback=True)
        assert mgr.is_degraded() is True
        assert mgr.should_use_cpu() is True
        assert mgr.should_halt_new_offers() is False

    def test_enter_kms_failure_halts_offers(self):
        mgr = DegradedModeManager()
        mgr.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        assert mgr.should_halt_new_offers() is True
        assert mgr.should_use_cpu() is False

    def test_exit_degraded_mode(self):
        mgr = DegradedModeManager()
        mgr.enter_degraded_mode(DegradedReason.GPU_FAILURE)
        mgr.exit_degraded_mode()
        assert mgr.is_degraded() is False

    def test_get_state_dict_fields(self):
        mgr = DegradedModeManager()
        mgr.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        d = mgr.get_state_dict()
        assert "degraded_mode" in d
        assert "gpu_fallback" in d
        assert "kms_unavailable_gap" in d


class TestExecutionAgent:
    def test_kill_switch_halts_processing(self):
        agent = _make_agent()
        agent.kill_switch.activate("test")
        ctx = {"uetr": "u1", "individual_payment_id": "p1", "failure_probability": 0.8,
               "pd_score": 0.05, "fee_bps": 300, "loan_amount": "100000",
               "dispute_class": "NOT_DISPUTE", "aml_passed": True}
        result = agent.process_payment(ctx)
        assert result["status"] == "HALT"

    def test_aml_blocked_payment(self):
        agent = _make_agent()
        ctx = {"uetr": "u2", "individual_payment_id": "p2", "failure_probability": 0.8,
               "pd_score": 0.05, "fee_bps": 300, "loan_amount": "100000",
               "dispute_class": "NOT_DISPUTE", "aml_passed": False}
        result = agent.process_payment(ctx)
        assert result["status"] == "BLOCK"
        assert result["halt_reason"] == "aml_blocked"

    def test_dispute_blocked_payment(self):
        agent = _make_agent()
        ctx = {"uetr": "u3", "individual_payment_id": "p3", "failure_probability": 0.8,
               "pd_score": 0.05, "fee_bps": 300, "loan_amount": "100000",
               "dispute_class": "DISPUTE_CONFIRMED", "aml_passed": True}
        result = agent.process_payment(ctx)
        assert result["status"] == "BLOCK"
        assert result["halt_reason"] == "dispute_blocked"

    def test_normal_payment_gets_offer(self):
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)  # disable human review
        agent = _make_agent(cfg)
        ctx = {"uetr": "u4", "individual_payment_id": "p4", "failure_probability": 0.8,
               "pd_score": 0.05, "fee_bps": 300, "loan_amount": "1000000",
               "maturity_days": 7, "dispute_class": "NOT_DISPUTE", "aml_passed": True}
        result = agent.process_payment(ctx)
        assert result["status"] in ("OFFER", "DECLINE")

    def test_decision_logged(self):
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        agent = _make_agent(cfg)
        ctx = {"uetr": "u5", "individual_payment_id": "p5", "failure_probability": 0.8,
               "pd_score": 0.05, "fee_bps": 300, "loan_amount": "1000000",
               "maturity_days": 7, "dispute_class": "NOT_DISPUTE", "aml_passed": True}
        result = agent.process_payment(ctx)
        assert result["decision_entry_id"] is not None
        # Verify the log entry is retrievable and signature is valid
        eid = result["decision_entry_id"]
        assert agent.decision_logger.verify(eid) is True

    def test_get_status_fields(self):
        agent = _make_agent()
        status = agent.get_status()
        assert "kill_switch" in status
        assert "kms" in status
        assert "degraded" in status
        assert "pending_overrides" in status

    def test_licensee_id_stamped_on_decision_log(self):
        """C8 integration: licensee_id must appear in every decision log entry."""
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        ks = KillSwitch()
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        agent = ExecutionAgent(
            ks, dl, HumanOverrideInterface(), DegradedModeManager(), cfg,
            licensee_id="HSBC_UK_001",
        )
        ctx = {"uetr": "u-lic-1", "individual_payment_id": "p-lic-1",
               "failure_probability": 0.8, "pd_score": 0.05, "fee_bps": 300,
               "loan_amount": "1000000", "maturity_days": 7,
               "dispute_class": "NOT_DISPUTE", "aml_passed": True}
        result = agent.process_payment(ctx)
        eid = result["decision_entry_id"]
        assert eid is not None
        entry = dl.get(eid)
        assert entry.licensee_id == "HSBC_UK_001"

    def test_tps_cap_halts_excess_calls(self):
        """C8 integration: calls exceeding max_tps return HALT with tps_limit_exceeded."""
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        ks = KillSwitch()
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        agent = ExecutionAgent(
            ks, dl, HumanOverrideInterface(), DegradedModeManager(), cfg,
            licensee_id="TEST_BANK", max_tps=2,
        )
        ctx = {"uetr": "u-tps", "individual_payment_id": "p-tps",
               "failure_probability": 0.8, "pd_score": 0.05, "fee_bps": 300,
               "loan_amount": "100000", "dispute_class": "NOT_DISPUTE", "aml_passed": True}
        results = [agent.process_payment(ctx) for _ in range(5)]
        halt_count = sum(1 for r in results if r.get("halt_reason") == "tps_limit_exceeded")
        assert halt_count >= 1

    def test_zero_max_tps_means_unlimited(self):
        """max_tps=0 (default) imposes no TPS limit."""
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        agent = ExecutionAgent(
            KillSwitch(), DecisionLogger(hmac_key=_HMAC_KEY),
            HumanOverrideInterface(), DegradedModeManager(), cfg,
            max_tps=0,
        )
        ctx = {"uetr": "u-unl", "individual_payment_id": "p-unl",
               "failure_probability": 0.8, "pd_score": 0.05, "fee_bps": 300,
               "loan_amount": "1000000", "maturity_days": 7,
               "dispute_class": "NOT_DISPUTE", "aml_passed": True}
        results = [agent.process_payment(ctx) for _ in range(20)]
        tps_halts = sum(1 for r in results if r.get("halt_reason") == "tps_limit_exceeded")
        assert tps_halts == 0


class TestLoanAmountAndFeeGates:
    """Tests for minimum loan amount gate (4c) and minimum cash fee gate (4d)."""

    def _make_agent_no_review(self, min_loan_amount_usd: int = 500000):
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        ks = KillSwitch()
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        return ExecutionAgent(
            ks, dl, HumanOverrideInterface(), DegradedModeManager(), cfg,
            min_loan_amount_usd=min_loan_amount_usd,
        )

    def _ctx(self, loan_amount: str, maturity_days: int = 7, fee_bps: int = 300):
        return {
            "uetr": "u-amt", "individual_payment_id": "p-amt",
            "failure_probability": 0.8, "pd_score": 0.05,
            "fee_bps": fee_bps, "loan_amount": loan_amount,
            "maturity_days": maturity_days,
            "dispute_class": "NOT_DISPUTE", "aml_passed": True,
        }

    def test_below_min_loan_amount_declined(self):
        """Principals below $500K are declined with BELOW_MIN_LOAN_AMOUNT."""
        agent = self._make_agent_no_review()
        result = agent.process_payment(self._ctx("100000"))
        assert result["status"] == "BELOW_MIN_LOAN_AMOUNT"
        assert result["halt_reason"] == "below_min_loan_amount"
        assert result["decision_entry_id"] is not None

    def test_exactly_min_loan_amount_passes_gate(self):
        """A principal exactly equal to the minimum must pass the gate."""
        agent = self._make_agent_no_review()
        result = agent.process_payment(self._ctx("500000", maturity_days=21))
        assert result["status"] not in ("BELOW_MIN_LOAN_AMOUNT",)

    def test_above_min_loan_amount_passes_gate(self):
        """$1M is well above the $500K floor; gate must not trigger."""
        agent = self._make_agent_no_review()
        result = agent.process_payment(self._ctx("1000000"))
        assert result["status"] not in ("BELOW_MIN_LOAN_AMOUNT", "BELOW_MIN_CASH_FEE")

    def test_licensee_override_min_loan_amount(self):
        """C8 token can lower the minimum for a specific licensee."""
        agent = self._make_agent_no_review(min_loan_amount_usd=100000)
        result = agent.process_payment(self._ctx("150000", maturity_days=21))
        assert result["status"] not in ("BELOW_MIN_LOAN_AMOUNT",)

    def test_below_min_cash_fee_declined(self):
        """$500K for 3 days at 500bps = ~$205 cash fee, below $500 minimum."""
        agent = self._make_agent_no_review()
        # $500K × 500bps × 3/365 ≈ $205 — below MIN_CASH_FEE_USD=$500
        result = agent.process_payment(self._ctx("500000", maturity_days=3, fee_bps=300))
        assert result["status"] == "BELOW_MIN_CASH_FEE"
        assert result["halt_reason"] == "below_min_cash_fee"
        assert result["decision_entry_id"] is not None

    def test_large_amount_clears_min_cash_fee(self):
        """$3M for 7 days at 300bps = ~$1726 — well above $500 minimum."""
        agent = self._make_agent_no_review()
        result = agent.process_payment(self._ctx("3000000", maturity_days=7, fee_bps=300))
        assert result["status"] not in ("BELOW_MIN_LOAN_AMOUNT", "BELOW_MIN_CASH_FEE")

    def test_tiered_fee_floor_mid_tier_applied(self):
        """$1M loan should use 400bps floor (mid tier), not 300bps."""
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        ks = KillSwitch()
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        agent = ExecutionAgent(ks, dl, HumanOverrideInterface(), DegradedModeManager(), cfg)
        ctx = self._ctx("1000000", maturity_days=7, fee_bps=100)  # C2 returns low fee_bps
        result = agent.process_payment(ctx)
        # If an offer is made, the fee_bps in the offer must be ≥ 400 (mid-tier floor)
        if result["status"] == "OFFER":
            assert result["loan_offer"]["fee_bps"] >= 400

    def test_tiered_fee_floor_large_tier_applied(self):
        """$5M loan should use the canonical 300bps floor (large tier)."""
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        ks = KillSwitch()
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        agent = ExecutionAgent(ks, dl, HumanOverrideInterface(), DegradedModeManager(), cfg)
        ctx = self._ctx("5000000", maturity_days=7, fee_bps=100)
        result = agent.process_payment(ctx)
        if result["status"] == "OFFER":
            assert result["loan_offer"]["fee_bps"] >= 300
