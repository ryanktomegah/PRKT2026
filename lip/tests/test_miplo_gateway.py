"""
test_miplo_gateway.py — TDD tests for Sprint 2c: C7 MIPLO API Gateway.

Tests cover:
  - DecisionLogEntryData tenant_id field and HMAC integrity
  - Pipeline.process() tenant_context threading to C6 and payment_context
  - MIPLOService BIC validation and tenant-scoped pipeline execution
  - MIPLO router HTTP endpoints
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.c7_execution_agent.decision_log import DecisionLogEntryData, DecisionLogger
from lip.c8_license_manager.license_token import ProcessorLicenseeContext

_HMAC_KEY = b"test_hmac_key_for_miplo_tests_32"


def _make_normalized_event(
    sending_bic: str = "COBADEFF",
    receiving_bic: str = "DEUTDEFF",
    amount: Decimal = Decimal("1000000"),
    rejection_code: str = "AC04",
    uetr: str = "test-uetr-001",
) -> NormalizedEvent:
    return NormalizedEvent(
        uetr=uetr,
        individual_payment_id="pay-001",
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount=amount,
        currency="EUR",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code=rejection_code,
        narrative="Test payment",
    )


def _make_processor_context(
    licensee_id: str = "FINASTRA_EU_001",
    sub_licensee_bics: list | None = None,
    deployment_phase: str = "LICENSOR",
) -> ProcessorLicenseeContext:
    return ProcessorLicenseeContext(
        licensee_id=licensee_id,
        max_tps=1000,
        aml_dollar_cap_usd=0,
        aml_count_cap=0,
        permitted_components=["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"],
        token_expiry="2027-12-31",
        licensee_type="PROCESSOR",
        sub_licensee_bics=sub_licensee_bics or ["COBADEFF", "DEUTDEFF"],
        annual_minimum_usd=500000,
        performance_premium_pct=0.15,
        platform_take_rate_pct=0.20,
        deployment_phase=deployment_phase,
    )


# ── Decision Log: tenant_id Field Tests ─────────────────────────────────────


class TestDecisionLogTenantId:

    def test_tenant_id_field_exists(self):
        """DecisionLogEntryData has tenant_id field with empty string default."""
        entry = DecisionLogEntryData(
            entry_id="e1",
            uetr="u1",
            individual_payment_id="p1",
            decision_type="OFFER",
            decision_timestamp="2027-01-01T00:00:00Z",
            failure_probability=0.8,
            pd_score=0.05,
            fee_bps=300,
            loan_amount="1000000",
            dispute_class="NOT_DISPUTE",
            aml_passed=True,
        )
        assert entry.tenant_id == ""

    def test_tenant_id_set_explicitly(self):
        entry = DecisionLogEntryData(
            entry_id="e1",
            uetr="u1",
            individual_payment_id="p1",
            decision_type="OFFER",
            decision_timestamp="2027-01-01T00:00:00Z",
            failure_probability=0.8,
            pd_score=0.05,
            fee_bps=300,
            loan_amount="1000000",
            dispute_class="NOT_DISPUTE",
            aml_passed=True,
            tenant_id="FINASTRA_EU_001",
        )
        assert entry.tenant_id == "FINASTRA_EU_001"

    def test_tenant_id_in_hmac_signature(self):
        """Tampering with tenant_id after logging must fail verification."""
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = DecisionLogEntryData(
            entry_id="e1",
            uetr="u1",
            individual_payment_id="p1",
            decision_type="OFFER",
            decision_timestamp="2027-01-01T00:00:00Z",
            failure_probability=0.8,
            pd_score=0.05,
            fee_bps=300,
            loan_amount="1000000",
            dispute_class="NOT_DISPUTE",
            aml_passed=True,
            tenant_id="FINASTRA_EU_001",
        )
        dl.log(entry)
        assert dl.verify("e1")

        # Tamper with tenant_id
        entry.tenant_id = "EVIL_TENANT"
        assert not dl.verify("e1")

    def test_backward_compatible_empty_tenant_id(self):
        """Entries with empty tenant_id still sign and verify correctly."""
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = DecisionLogEntryData(
            entry_id="e2",
            uetr="u2",
            individual_payment_id="p2",
            decision_type="DECLINE",
            decision_timestamp="2027-01-01T00:00:00Z",
            failure_probability=0.5,
            pd_score=0.1,
            fee_bps=300,
            loan_amount="500000",
            dispute_class="NOT_DISPUTE",
            aml_passed=True,
        )
        dl.log(entry)
        assert dl.verify("e2")
        assert entry.tenant_id == ""


# ── C7 Agent: tenant_id Threading Tests ─────────────────────────────────────


class TestAgentTenantIdThreading:

    def _make_agent(self):
        from lip.c7_execution_agent.agent import ExecutionAgent
        from lip.c7_execution_agent.degraded_mode import DegradedModeManager
        from lip.c7_execution_agent.human_override import HumanOverrideInterface
        from lip.c7_execution_agent.kill_switch import KillSwitch

        ks = KillSwitch()
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        ho = HumanOverrideInterface()
        dm = DegradedModeManager()
        return ExecutionAgent(ks, dl, ho, dm)

    def test_tenant_id_from_payment_context(self):
        """When payment_context has tenant_id, decision log entry includes it."""
        agent = self._make_agent()
        ctx = {
            "uetr": "test-uetr-tenant",
            "individual_payment_id": "pay-001",
            "sending_bic": "COBADEFF",
            "failure_probability": 0.85,
            "pd_score": 0.05,
            "fee_bps": 400,
            "loan_amount": Decimal("1000000"),
            "original_payment_amount_usd": "1000000",
            "dispute_class": "NOT_DISPUTE",
            "aml_passed": True,
            "maturity_days": 7,
            "rejection_code": "AC04",
            "rejection_class": "CLASS_B",
            "corridor": "EUR_USD",
            "currency": "EUR",
            "aml_anomaly_flagged": False,
            "human_override_decision": None,
            "anomaly_flagged": False,
            "tenant_id": "FINASTRA_EU_001",
        }
        result = agent.process_payment(ctx)
        entry_id = result.get("decision_entry_id")
        assert entry_id is not None, f"Expected decision_entry_id but got {result}"
        entry = agent.decision_logger.get(entry_id)
        assert entry is not None
        assert entry.tenant_id == "FINASTRA_EU_001"

    def test_empty_tenant_id_when_not_in_context(self):
        """When payment_context lacks tenant_id, decision log entry has empty string."""
        agent = self._make_agent()
        ctx = {
            "uetr": "test-uetr-no-tenant",
            "individual_payment_id": "pay-002",
            "sending_bic": "COBADEFF",
            "failure_probability": 0.85,
            "pd_score": 0.05,
            "fee_bps": 400,
            "loan_amount": Decimal("1000000"),
            "original_payment_amount_usd": "1000000",
            "dispute_class": "NOT_DISPUTE",
            "aml_passed": True,
            "maturity_days": 7,
            "rejection_code": "AC04",
            "rejection_class": "CLASS_B",
            "corridor": "EUR_USD",
            "currency": "EUR",
            "aml_anomaly_flagged": False,
            "human_override_decision": None,
            "anomaly_flagged": False,
        }
        result = agent.process_payment(ctx)
        entry_id = result.get("decision_entry_id")
        assert entry_id is not None, f"Expected decision_entry_id but got {result}"
        entry = agent.decision_logger.get(entry_id)
        assert entry is not None
        assert entry.tenant_id == ""


# ── Pipeline: tenant_context Threading Tests ────────────────────────────────


class _MockC1:
    """Returns configurable failure probability."""
    def __init__(self, fp: float = 0.80):
        self._fp = fp

    def predict(self, payment_dict):
        return {"failure_probability": self._fp, "shap_top20": []}


class _MockC2:
    """Returns configurable PD/fee/tier."""
    def predict(self, payment_dict, borrower):
        return {"pd_score": 0.05, "fee_bps": 400, "tier": 2, "shap_values": []}


class _MockC4:
    """Returns NOT_DISPUTE."""
    def classify(self, **kwargs):
        return {"dispute_class": "NOT_DISPUTE"}


class _SpyC6:
    """Spy that records all check() call arguments."""
    def __init__(self):
        self.calls = []

    def check(self, entity_id, amount, beneficiary_id, **kwargs):
        self.calls.append({
            "entity_id": entity_id,
            "amount": amount,
            "beneficiary_id": beneficiary_id,
            **kwargs,
        })
        result = MagicMock()
        result.passed = True
        result.anomaly_flagged = False
        result.structuring_flagged = False
        return result


class _SpyC7:
    """Spy that captures payment_context from process_payment()."""
    def __init__(self):
        self.captured_contexts = []
        self.aml_dollar_cap_usd = 0
        self.aml_count_cap = 0

    def process_payment(self, payment_context):
        self.captured_contexts.append(dict(payment_context))
        return {
            "status": "DECLINE",
            "loan_offer": None,
            "decision_entry_id": "test-entry-id",
            "halt_reason": None,
        }


class TestPipelineTenantContext:

    def _make_pipeline(self, spy_c6=None, spy_c7=None):
        from lip.pipeline import LIPPipeline

        c6 = spy_c6 or _SpyC6()
        c7 = spy_c7 or _SpyC7()
        return LIPPipeline(
            c1_engine=_MockC1(fp=0.80),
            c2_engine=_MockC2(),
            c4_classifier=_MockC4(),
            c6_checker=c6,
            c7_agent=c7,
            threshold=0.11,
        ), c6, c7

    def test_c6_receives_tenant_id(self):
        """When tenant_context is provided, C6 check() is called with tenant_id."""
        from lip.common.schemas import TenantContext

        spy_c6 = _SpyC6()
        pipeline, _, _ = self._make_pipeline(spy_c6=spy_c6)
        event = _make_normalized_event()
        tenant_ctx = TenantContext(
            tenant_id="FINASTRA_EU_001",
            sub_licensee_bics=["COBADEFF", "DEUTDEFF"],
        )

        pipeline.process(event, tenant_context=tenant_ctx)

        assert len(spy_c6.calls) == 1
        assert spy_c6.calls[0]["tenant_id"] == "FINASTRA_EU_001"

    def test_c6_no_tenant_id_without_context(self):
        """When tenant_context is None, C6 check() is called with tenant_id=None."""
        spy_c6 = _SpyC6()
        pipeline, _, _ = self._make_pipeline(spy_c6=spy_c6)
        event = _make_normalized_event()

        pipeline.process(event)

        assert len(spy_c6.calls) == 1
        assert spy_c6.calls[0].get("tenant_id") is None

    def test_payment_context_has_tenant_id(self):
        """When tenant_context is provided, C7 payment_context has tenant_id."""
        from lip.common.schemas import TenantContext

        spy_c7 = _SpyC7()
        pipeline, _, _ = self._make_pipeline(spy_c7=spy_c7)
        event = _make_normalized_event()
        tenant_ctx = TenantContext(
            tenant_id="FINASTRA_EU_001",
            sub_licensee_bics=["COBADEFF"],
        )

        pipeline.process(event, tenant_context=tenant_ctx)

        assert len(spy_c7.captured_contexts) == 1
        assert spy_c7.captured_contexts[0]["tenant_id"] == "FINASTRA_EU_001"

    def test_payment_context_empty_tenant_id_without_context(self):
        """When tenant_context is None, C7 payment_context has tenant_id=''."""
        spy_c7 = _SpyC7()
        pipeline, _, _ = self._make_pipeline(spy_c7=spy_c7)
        event = _make_normalized_event()

        pipeline.process(event)

        assert len(spy_c7.captured_contexts) == 1
        assert spy_c7.captured_contexts[0]["tenant_id"] == ""

    def test_backward_compatible_without_tenant_context(self):
        """Pipeline works exactly as before when tenant_context is not provided."""
        spy_c7 = _SpyC7()
        pipeline, _, _ = self._make_pipeline(spy_c7=spy_c7)
        event = _make_normalized_event()

        result = pipeline.process(event)

        assert result.outcome == "DECLINED"
        assert len(spy_c7.captured_contexts) == 1
        assert spy_c7.captured_contexts[0]["tenant_id"] == ""


# ── MIPLO Service Tests ─────────────────────────────────────────────────────


class TestMIPLOService:

    def _make_service(self, sub_licensee_bics=None, metrics=None):
        from lip.api.miplo_service import MIPLOService

        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = MagicMock(
            outcome="DECLINED",
            uetr="test-uetr",
            failure_probability=0.8,
            above_threshold=True,
            loan_offer=None,
            decision_entry_id="entry-001",
            pd_estimate=0.05,
            fee_bps=400,
            total_latency_ms=12.5,
        )
        ctx = _make_processor_context(
            sub_licensee_bics=sub_licensee_bics or ["COBADEFF", "DEUTDEFF"],
        )
        return MIPLOService(mock_pipeline, ctx, metrics), mock_pipeline

    def test_validate_bic_authorized(self):
        service, _ = self._make_service()
        assert service.validate_bic("COBADEFF") is True
        assert service.validate_bic("DEUTDEFF") is True

    def test_validate_bic_unauthorized(self):
        service, _ = self._make_service()
        assert service.validate_bic("HSBCGB2L") is False
        assert service.validate_bic("BNPAFRPP") is False

    def test_process_authorized_bic(self):
        """Authorized BIC → pipeline.process() called with tenant_context."""
        from lip.common.schemas import TenantContext

        service, mock_pipeline = self._make_service()
        event = _make_normalized_event(sending_bic="COBADEFF")

        service.process_payment(event)

        mock_pipeline.process.assert_called_once()
        call_kwargs = mock_pipeline.process.call_args
        tenant_ctx = call_kwargs.kwargs.get("tenant_context") or call_kwargs[1].get("tenant_context")
        assert tenant_ctx is not None
        assert isinstance(tenant_ctx, TenantContext)
        assert tenant_ctx.tenant_id == "FINASTRA_EU_001"

    def test_process_unauthorized_bic_raises(self):
        """Unauthorized BIC → UnauthorizedBICError."""
        from lip.api.miplo_service import UnauthorizedBICError

        service, _ = self._make_service()
        event = _make_normalized_event(sending_bic="HSBCGB2L")

        with pytest.raises(UnauthorizedBICError) as exc_info:
            service.process_payment(event)
        assert "HSBCGB2L" in str(exc_info.value)
        assert "FINASTRA_EU_001" in str(exc_info.value)

    def test_tenant_context_matches_processor_context(self):
        """TenantContext fields match ProcessorLicenseeContext."""
        service, _ = self._make_service(
            sub_licensee_bics=["COBADEFF", "DEUTDEFF", "BNPAFRPP"],
        )
        ctx = service.tenant_context
        assert ctx.tenant_id == "FINASTRA_EU_001"
        assert ctx.sub_licensee_bics == ["COBADEFF", "DEUTDEFF", "BNPAFRPP"]
        assert ctx.deployment_phase == "LICENSOR"

    def test_get_status(self):
        service, _ = self._make_service()
        status = service.get_status()
        assert status["tenant_id"] == "FINASTRA_EU_001"
        assert "COBADEFF" in status["sub_licensee_bics"]
        assert "DEUTDEFF" in status["sub_licensee_bics"]
        assert status["deployment_phase"] == "LICENSOR"

    def test_metrics_incremented_on_request(self):
        """Request counter incremented on successful process call."""
        from lip.infrastructure.monitoring.metrics import METRIC_MIPLO_REQUEST_COUNT

        mock_metrics = MagicMock()
        service, _ = self._make_service(metrics=mock_metrics)
        event = _make_normalized_event(sending_bic="COBADEFF")

        service.process_payment(event)

        mock_metrics.increment.assert_called()
        call_args_list = [str(c) for c in mock_metrics.increment.call_args_list]
        assert any(METRIC_MIPLO_REQUEST_COUNT in s for s in call_args_list)

    def test_violation_metric_on_unauthorized_bic(self):
        """Tenant isolation violation metric incremented on unauthorized BIC."""
        from lip.api.miplo_service import UnauthorizedBICError
        from lip.infrastructure.monitoring.metrics import METRIC_TENANT_ISOLATION_VIOLATION

        mock_metrics = MagicMock()
        service, _ = self._make_service(metrics=mock_metrics)
        event = _make_normalized_event(sending_bic="HSBCGB2L")

        with pytest.raises(UnauthorizedBICError):
            service.process_payment(event)

        mock_metrics.increment.assert_called()
        call_args_list = [str(c) for c in mock_metrics.increment.call_args_list]
        assert any(METRIC_TENANT_ISOLATION_VIOLATION in s for s in call_args_list)
